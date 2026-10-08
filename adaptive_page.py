"""Independent cover background and fitted, interactive foreground layer."""
from functools import wraps

import pygame

from adaptive_ui import cover_geometry
from asset_loaders import load_scaled_image
from display_runtime import LOGICAL_SCREEN_SIZE
from native_render import Canvas


ContentSurface = Canvas


def draw_modal_shade(screen, color):
    """Dim the composed scene, preserving transparency in foreground artwork."""
    layers = getattr(screen, "modal_layers", None)
    if layers is None:
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill(color)
        screen.blit(shade, (0, 0))
        return
    layers.append((screen.pixels.copy(), color))
    screen.fill((0, 0, 0, 0))


def content_rect(viewport_size):
    scale = min(viewport_size[0] / LOGICAL_SCREEN_SIZE[0],
                viewport_size[1] / LOGICAL_SCREEN_SIZE[1])
    size = tuple(max(1, round(value * scale)) for value in LOGICAL_SCREEN_SIZE)
    return pygame.Rect((viewport_size[0] - size[0]) // 2,
                       (viewport_size[1] - size[1]) // 2, *size)


def adaptive_draw(draw):
    """Composite once, including when a subclass extends its parent's draw."""
    @wraps(draw)
    def wrapped(self, *args, **kwargs):
        # Support isolated layout tests constructing pages without __init__.
        if not hasattr(self, "viewport"):
            return draw(self, *args, **kwargs)
        depth = getattr(self, "_draw_depth", 0)
        self._draw_depth = depth + 1
        if depth == 0:
            self.screen.configure(content_rect(self.viewport.get_size()).size)
            self.screen.modal_layers.clear()
            self.screen.fill((0, 0, 0, 0))
        try:
            result = draw(self, *args, **kwargs)
        finally:
            self._draw_depth = depth
        if depth == 0:
            self.present()
        return result
    return wrapped


class AdaptivePage:
    master_background_path = "RoundPage/Master background.png"

    def init_viewport(self, viewport):
        self.viewport = viewport
        self.screen = ContentSurface(LOGICAL_SCREEN_SIZE)
        self.screen.modal_layers = []
        self._background_size = None
        self._master_background = load_scaled_image(self.master_background_path)

    def to_content(self, position):
        if not hasattr(self, "viewport"):
            return position
        rect = content_rect(self.viewport.get_size())
        return ((position[0] - rect.x) * LOGICAL_SCREEN_SIZE[0] / rect.width,
                (position[1] - rect.y) * LOGICAL_SCREEN_SIZE[1] / rect.height)

    def mouse_pos(self):
        return self.to_content(pygame.mouse.get_pos())

    def events(self):
        for event in pygame.event.get():
            if hasattr(event, "pos"):
                attributes = dict(event.dict)
                attributes["pos"] = self.to_content(event.pos)
                if hasattr(event, "rel") and hasattr(self, "viewport"):
                    rect = content_rect(self.viewport.get_size())
                    attributes["rel"] = (event.rel[0] * LOGICAL_SCREEN_SIZE[0] / rect.width,
                                         event.rel[1] * LOGICAL_SCREEN_SIZE[1] / rect.height)
                event = pygame.event.Event(event.type, attributes)
            yield event

    def present(self):
        if getattr(self, "_draw_depth", 0):
            return
        if not hasattr(self, "viewport"):
            pygame.display.flip()
            return
        size = self.viewport.get_size()
        if size != self._background_size:
            self._background = pygame.Surface(size)
            self._background.fill((235, 220, 190))
            if self._master_background is not None:
                scaled_size, position = cover_geometry(self._master_background.get_size(), size)
                self._background.blit(pygame.transform.smoothscale(
                    self._master_background, scaled_size), position)
            self._background_size = size
        self.viewport.blit(self._background, (0, 0))
        rect = content_rect(size)
        # Composite artwork onto the opaque background before applying each
        # shade. Dimming an RGBA layer directly changes its alpha as well,
        # revealing light halos once that layer is placed over the background.
        for layer, color in [*self.screen.modal_layers, (self.screen.pixels, None)]:
            self.viewport.blit(layer, rect)
            if color is not None:
                shade = pygame.Surface(size, pygame.SRCALPHA)
                shade.fill(color)
                self.viewport.blit(shade, (0, 0))
        pygame.display.flip()
