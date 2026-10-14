"""Three repeating pencil charts over the original engraved grid."""
import os
import random

import pygame


CHART_RECT = pygame.Rect(1194, 59, 185, 121)
CHART_CLEAN_PATH = os.path.join('UI', 'Animation', 'Chart Clean.png')
CHART_START_DELAY = 0.8
CHART_SEGMENT_SECONDS = 0.55
CHART_HOLD_SECONDS = 2.0
# Left-to-right stops follow the existing plotted points. Include the width of
# the first/last round markers so neither is cut off at the ends of the reveal.
CHART_REVEAL_STOPS = (1195, 1208, 1222, 1240, 1254, 1280, 1304,
                      1320, 1332, 1341, 1349, 1355, 1378)
CHART_DRAW_SECONDS = (len(CHART_REVEAL_STOPS) - 1) * CHART_SEGMENT_SECONDS
# Foreground newspaper silhouette in chart-local pixels. Ink stays behind it.
CHART_NEWSPAPER = ((161, 80), (173, 75), (185, 71), (185, 121), (172, 121))
# Coordinates inside the clean patch; keep the plot away from its border.
CHART_NEW_POINTS = (
    ((8, 12), (28, 25), (46, 20), (60, 42), (86, 35), (110, 62),
     (126, 54), (138, 72), (147, 67), (155, 88), (161, 82), (176, 108)),
    ((8, 112), (28, 91), (46, 72), (60, 55), (86, 66), (110, 53),
     (126, 64), (138, 57), (147, 63), (155, 55), (161, 60), (176, 57)),
)


def chart_phase(seconds):
    elapsed = max(0.0, seconds - CHART_START_DELAY)
    duration = CHART_DRAW_SECONDS + CHART_HOLD_SECONDS
    return int(elapsed / duration) % 3, elapsed % duration


def pencil_chart(clean, points, seed):
    """Stable, softly feathered graphite strokes with fine paper grain."""
    rng = random.Random(seed)
    scale = 4
    ink = pygame.Surface((clean.get_width() * scale, clean.get_height() * scale), pygame.SRCALPHA)
    path = [(x * scale, y * scale) for x, y in points]
    # Layer the soft edge and darker core, matching the sepia original ink.
    for width, alpha in ((4.0, 25), (2.8, 65), (1.6, 205)):
        pygame.draw.lines(ink, (65, 57, 43, alpha), False, path, round(width * scale))
    for point in path:
        for radius, alpha in ((4.5, 25), (3.7, 90), (2.9, 225)):
            pygame.draw.circle(ink, (65, 57, 43, alpha), point, round(radius * scale))
    ink = pygame.transform.smoothscale(ink, clean.get_size())
    for y in range(ink.get_height()):
        for x in range(ink.get_width()):
            color = ink.get_at((x, y))
            if color.a:
                ink.set_at((x, y), (*color[:3], round(color.a * rng.uniform(0.68, 1.0))))
    foreground = pygame.Surface((clean.get_width() * scale, clean.get_height() * scale), pygame.SRCALPHA)
    foreground.fill((255, 255, 255, 255))
    pygame.draw.polygon(foreground, (255, 255, 255, 0),
                        [(x * scale, y * scale) for x, y in CHART_NEWSPAPER])
    ink.blit(pygame.transform.smoothscale(foreground, clean.get_size()), (0, 0),
             special_flags=pygame.BLEND_RGBA_MULT)
    result = clean.copy()
    result.blit(ink, (0, 0))
    return result


def chart_reveal_x(seconds):
    progress = max(0.0, (seconds - CHART_START_DELAY) / CHART_SEGMENT_SECONDS)
    segment = int(progress)
    if segment >= len(CHART_REVEAL_STOPS) - 1:
        return CHART_RECT.right
    fraction = progress - segment
    return (CHART_REVEAL_STOPS[segment]
            + (CHART_REVEAL_STOPS[segment + 1] - CHART_REVEAL_STOPS[segment]) * fraction)


class MenuChartReveal:
    def __init__(self, menu_image):
        self.clean = None
        self.charts = []
        # Synthetic/fallback menu art has no chart at these coordinates.
        if menu_image is not None and menu_image.get_size() == (1678, 937):
            if os.path.exists(CHART_CLEAN_PATH):
                self.clean = pygame.image.load(CHART_CLEAN_PATH).convert()
                self.charts = [menu_image.subsurface(CHART_RECT).copy()]
                self.charts.extend(pencil_chart(self.clean, points, 1800 + index)
                                   for index, points in enumerate(CHART_NEW_POINTS))
        self.started_at = None
        self.cached_size = None
        self.scaled = None
        self.scaled_charts = []

    def draw(self, screen, artwork, ticks):
        if self.clean is None:
            return
        if self.started_at is None:
            self.started_at = ticks
        seconds = max(0.0, (ticks - self.started_at) / 1000)
        chart, phase = chart_phase(seconds)
        revealed = chart_reveal_x(phase + CHART_START_DELAY)
        sx, sy = artwork.width / 1678, artwork.height / 937
        target = pygame.Rect(artwork.left + round(CHART_RECT.x * sx),
                             artwork.top + round(CHART_RECT.y * sy),
                             max(1, round(CHART_RECT.width * sx)),
                             max(1, round(CHART_RECT.height * sy)))
        if self.cached_size != target.size:
            self.scaled = pygame.transform.smoothscale(self.clean, target.size)
            self.scaled_charts = [pygame.transform.smoothscale(image, target.size)
                                  for image in self.charts]
            self.cached_size = target.size
        offset = max(0, min(target.width, round((revealed - CHART_RECT.x) * sx)))
        # All three charts use the same crop, scaling and position. Switching
        # between the full-menu scale and a separately scaled crop shifts grid
        # sampling by a fraction of a pixel on non-native window sizes.
        screen.blit(self.scaled, target)
        if offset:
            screen.blit(self.scaled_charts[chart], target, (0, 0, offset, target.height))
