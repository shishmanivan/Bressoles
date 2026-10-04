"""Hover copies of the original engraved ribbon lettering (no replacement font)."""
import pygame


RIBBON_HOVER_SCALE = 1.12
RIBBON_ANIMATION_SECONDS = 0.13
# Individual glyph bounds in UI/Menu3_1.png, including the accent and punctuation.
RIBBON_LETTER_BOUNDS = (
    (538, 838, 21, 35), (559, 844, 24, 30), (584, 847, 9, 29),
    (593, 848, 24, 29), (618, 848, 10, 29), (628, 847, 24, 30),
    (653, 845, 27, 30),
    (699, 835, 29, 38), (730, 832, 28, 37), (758, 828, 25, 38),
    (783, 823, 28, 40), (811, 816, 27, 40), (833, 811, 27, 35),
    (858, 805, 32, 36), (893, 800, 29, 40), (923, 798, 15, 39),
    (939, 794, 30, 41), (969, 791, 30, 41), (1000, 789, 15, 40),
    (1015, 786, 30, 41), (1045, 785, 30, 41), (1083, 779, 14, 47),
)


def _extract_letter(image, bounds, isolated_components=0):
    """Copy ink pixels and reconstruct only their small patch of paper beneath."""
    source = image.subsurface(bounds).copy()
    width, height = source.get_size()
    colors = {(x, y): tuple(source.get_at((x, y))[:3])
              for y in range(height) for x in range(width)}
    ink = {point for point, color in colors.items() if sum(color) / 3 < 175}
    if isolated_components:
        # Only É and the close O/R pair need precise isolation. Select their
        # connected dark strokes (plus É's detached accent), not ribbon lines
        # or fragments of neighboring glyphs inside the rectangular crop.
        pending_ink = {point for point, color in colors.items() if sum(color) / 3 < 125}
        components = []
        while pending_ink:
            seed = pending_ink.pop()
            component, stack = {seed}, [seed]
            while stack:
                x, y = stack.pop()
                for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if point in pending_ink:
                        pending_ink.remove(point)
                        component.add(point)
                        stack.append(point)
            components.append(component)
        core = set().union(*sorted(components, key=len, reverse=True)[:isolated_components])
        edge = {(x + dx, y + dy) for x, y in core
                for dx in range(-2, 3) for dy in range(-2, 3)}
        ink.intersection_update(edge)
    # Include antialiased edges in the removal patch. Nearby untouched paper
    # supplies its color/gradient, without replacing the rest of the ribbon.
    missing = {(x + dx, y + dy) for x, y in ink
               for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
               if 0 <= x + dx < width and 0 <= y + dy < height}
    paper = {point: color for point, color in colors.items() if point not in missing}
    pending = set(missing)
    while pending:
        fill = {}
        for x, y in pending:
            neighbors = [paper[p] for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                         if p in paper]
            if neighbors:
                fill[x, y] = tuple(round(sum(c[channel] for c in neighbors) / len(neighbors))
                                   for channel in range(3))
        if not fill:
            fill = {point: (204, 178, 139) for point in pending}
        paper.update(fill)
        pending.difference_update(fill)
    glyph = pygame.Surface((width, height), pygame.SRCALPHA)
    patch = pygame.Surface((width, height), pygame.SRCALPHA)
    for point in missing:
        patch.set_at(point, (*paper[point], 255))
        original = colors[point]
        # Separate ink from paper before scaling, avoiding a beige halo around
        # the enlarged glyph. Reconstruct its original color when composited.
        background = paper[point]
        paper_light = sum(background) / 3
        alpha = max(0.0, min(1.0, (paper_light - sum(original) / 3) / max(1, paper_light - 35)))
        if alpha > 0:
            foreground = tuple(max(0, min(255, round(b + (o - b) / alpha)))
                               for b, o in zip(background, original))
            glyph.set_at(point, (*foreground, round(255 * alpha)))
    return glyph, patch


class RibbonLetterHover:
    def __init__(self, image):
        self.letters = []
        if image is not None and image.get_size() == (1678, 937):
            for index, bounds in enumerate(RIBBON_LETTER_BOUNDS):
                isolated = 2 if index == 0 else 1 if index in (12, 13) else 0
                glyph, patch = _extract_letter(image, pygame.Rect(bounds), isolated)
                self.letters.append((pygame.Rect(bounds), glyph, patch))
        self.amounts = [0.0] * len(self.letters)
        self.hovered = None
        self.last_ticks = None
        self.cache_size = None
        self.scaled = []

    def hit_test(self, mouse_pos, artwork):
        x = (mouse_pos[0] - artwork.left) * 1678 / artwork.width
        y = (mouse_pos[1] - artwork.top) * 937 / artwork.height
        for index, (bounds, _, _) in enumerate(self.letters):
            if bounds.collidepoint(x, y):
                return index
        return None

    def draw(self, screen, artwork, mouse_pos, ticks, play_sound):
        target = self.hit_test(mouse_pos, artwork)
        if target != self.hovered:
            if target is not None:
                play_sound()
            self.hovered = target
        dt = min(0.05, max(0, (ticks - self.last_ticks) / 1000)) if self.last_ticks is not None else 1 / 60
        self.last_ticks = ticks
        sx, sy = artwork.width / 1678, artwork.height / 937
        if self.cache_size != artwork.size:
            self.scaled = []
            for bounds, glyph, patch in self.letters:
                rect = pygame.Rect(round(bounds.x * sx), round(bounds.y * sy),
                                   max(1, round(bounds.width * sx)), max(1, round(bounds.height * sy)))
                self.scaled.append((rect, pygame.transform.smoothscale(glyph, rect.size),
                                    pygame.transform.smoothscale(patch, rect.size)))
            self.cache_size = artwork.size
        active = []
        for index, (rect, glyph, patch) in enumerate(self.scaled):
            direction = 1 if index == target else -1
            self.amounts[index] = max(0, min(1, self.amounts[index] + direction * dt / RIBBON_ANIMATION_SECONDS))
            amount = self.amounts[index]
            if amount <= 0:
                continue
            ease = amount * amount * (3 - 2 * amount)
            scale = 1 + (RIBBON_HOVER_SCALE - 1) * ease
            grown = pygame.transform.smoothscale(glyph, (max(1, round(rect.width * scale)),
                                                        max(1, round(rect.height * scale))))
            positioned = rect.move(artwork.left, artwork.top)
            screen.blit(patch, positioned)
            active.append((grown, grown.get_rect(center=positioned.center)))
        for glyph, rect in active:
            screen.blit(glyph, rect)
