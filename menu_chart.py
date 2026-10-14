"""One-shot reveal of the original engraved chart, preserving its actual ink."""
import os

import pygame


CHART_RECT = pygame.Rect(1194, 59, 185, 121)
CHART_CLEAN_PATH = os.path.join('UI', 'Animation', 'Chart Clean.png')
CHART_START_DELAY = 0.8
CHART_SEGMENT_SECONDS = 0.55
# Left-to-right stops follow the existing plotted points. Include the width of
# the first/last round markers so neither is cut off at the ends of the reveal.
CHART_REVEAL_STOPS = (1195, 1208, 1222, 1240, 1254, 1280, 1304,
                      1320, 1332, 1341, 1349, 1355, 1378)


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
        # Synthetic/fallback menu art has no chart at these coordinates.
        if menu_image is not None and menu_image.get_size() == (1678, 937):
            if os.path.exists(CHART_CLEAN_PATH):
                self.clean = pygame.image.load(CHART_CLEAN_PATH).convert()
        self.started_at = None
        self.cached_size = None
        self.scaled = None

    def draw(self, screen, artwork, ticks):
        if self.clean is None:
            return
        if self.started_at is None:
            self.started_at = ticks
        seconds = max(0.0, (ticks - self.started_at) / 1000)
        revealed = chart_reveal_x(seconds)
        if revealed >= CHART_RECT.right:
            # Nothing is drawn after completion: the exact untouched menu art
            # is visible, and elapsed time never wraps back to the blank patch.
            return
        sx, sy = artwork.width / 1678, artwork.height / 937
        target = pygame.Rect(artwork.left + round(CHART_RECT.x * sx),
                             artwork.top + round(CHART_RECT.y * sy),
                             max(1, round(CHART_RECT.width * sx)),
                             max(1, round(CHART_RECT.height * sy)))
        if self.cached_size != target.size:
            self.scaled = pygame.transform.smoothscale(self.clean, target.size)
            self.cached_size = target.size
        # Keep the clean patch only AHEAD of the pencil. The pixels behind the
        # advancing edge are the original line, dots, paper and grid beneath.
        offset = max(0, min(target.width, round((revealed - CHART_RECT.x) * sx)))
        if offset < target.width:
            screen.blit(self.scaled, (target.x + offset, target.y),
                        (offset, 0, target.width - offset, target.height))
