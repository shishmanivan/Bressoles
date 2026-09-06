"""Small, reusable primitives for viewport-anchored Pygame interfaces."""

from dataclasses import dataclass
import math

import pygame


def clamp(minimum, preferred, maximum):
    """Return ``preferred`` constrained to the inclusive min/max range."""
    return max(minimum, min(preferred, maximum))


def cover_geometry(source_size, viewport_size):
    """Return the size and centered position for CSS-style ``cover`` rendering."""
    source_width, source_height = source_size
    viewport_width, viewport_height = viewport_size
    if min(source_width, source_height, viewport_width, viewport_height) <= 0:
        raise ValueError("source and viewport dimensions must be positive")

    scale = max(viewport_width / source_width, viewport_height / source_height)
    scaled_size = (
        int(math.ceil(source_width * scale)),
        int(math.ceil(source_height * scale)),
    )
    position = (
        (viewport_width - scaled_size[0]) // 2,
        (viewport_height - scaled_size[1]) // 2,
    )
    return scaled_size, position


def proportional_size(source_size, *, width=None, height=None):
    """Scale a size proportionally using exactly one requested dimension."""
    source_width, source_height = source_size
    if (width is None) == (height is None):
        raise ValueError("provide exactly one of width or height")
    if width is not None:
        return max(1, round(width)), max(1, round(width * source_height / source_width))
    return max(1, round(height * source_width / source_height)), max(1, round(height))


@dataclass(frozen=True)
class AnchoredElement:
    """A viewport anchor independent from the background image's coordinates."""

    horizontal: str
    vertical: str
    x_margin: int = 0
    y_margin: int = 0

    def rect(self, element_size, viewport_size):
        width, height = element_size
        viewport_width, viewport_height = viewport_size
        horizontal_positions = {
            "left": self.x_margin,
            "center": round((viewport_width - width) / 2) + self.x_margin,
            "right": viewport_width - width - self.x_margin,
        }
        vertical_positions = {
            "top": self.y_margin,
            "center": round((viewport_height - height) / 2) + self.y_margin,
            "bottom": viewport_height - height - self.y_margin,
        }
        try:
            return pygame.Rect(
                horizontal_positions[self.horizontal],
                vertical_positions[self.vertical],
                width,
                height,
            )
        except KeyError as error:
            raise ValueError(f"unsupported anchor: {error.args[0]}") from error
