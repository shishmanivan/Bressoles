"""Artwork and typography for the individual campaign card templates."""

import os

import pygame

from asset_loaders import load_scaled_image
from shared_utils import wrap_text


class LevelCardStyle:
    def __init__(self, card_size, level_num=1):
        source = load_scaled_image(os.path.join("LevelPage", f"Card_{level_num}.png"))
        # Keep the soft shadow around the opaque paper, excluding stray alpha
        # pixels in the exported canvas. Coordinates below describe this asset.
        crop = source.get_bounding_rect(min_alpha=32).inflate(48, 48)
        crop.clamp_ip(source.get_rect())
        self.card = pygame.transform.smoothscale(source.subsurface(crop), card_size)
        sx, sy = card_size[0] / crop.width, card_size[1] / crop.height

        def art_rect(x, y, width, height):
            return pygame.Rect(round((x - crop.x) * sx), round((y - crop.y) * sy),
                               round(width * sx), round(height * sy))

        self.picture_rect = art_rect(178, 135, 548, 534)
        self.year_rect = art_rect(1050, 90, 330, 108)
        self.text_rect = art_rect(800, 242, 830, 380)
        self.button_bottomright = art_rect(1695, 714, 0, 0).topleft
        if level_num == 2:
            self.picture_rect = art_rect(153, 145, 542, 541)
            self.year_rect = art_rect(1010, 100, 330, 108)
            self.text_rect = art_rect(768, 252, 820, 395)
            self.button_bottomright = art_rect(1660, 739, 0, 0).topleft
        elif level_num >= 3:
            picture_boxes = {
                3: (165, 132, 576, 534),
                4: (174, 127, 574, 541),
                5: (169, 125, 574, 544),
                6: (183, 117, 555, 542),
            }
            self.picture_rect = art_rect(*picture_boxes[level_num])
            self.year_rect = art_rect(1090, 77 if level_num != 3 else 91, 330, 108)
            self.text_rect = art_rect(822, 235, 876, 395)
            self.button_bottomright = art_rect(1770, 714, 0, 0).topleft
        self.pin_center = (round(card_size[0] * 0.49), 29)
        pin = load_scaled_image(os.path.join("LevelPage", "Bulavka.png"))
        self.pin = pygame.transform.smoothscale(
            pin.subsurface(pin.get_bounding_rect(min_alpha=32)), (28, 28)
        )
        self.year_font = pygame.font.Font(os.path.join("Fonts", "BodoniModa-ExtraBold.ttf"), 44)
        self.body_fonts = {
            size: pygame.font.Font(os.path.join("Fonts", "OldStandard-Regular.ttf"), size)
            for size in range(18, 27)
        }
        self._text_cache = {}
        self._pictures = {}

    def button_rect(self, position, size):
        rect = pygame.Rect((0, 0), tuple(round(d * 1.2) for d in size))
        rect.bottomright = (position[0] + self.button_bottomright[0],
                            position[1] + self.button_bottomright[1])
        return rect

    def _text(self, year, description):
        key = (year, description)
        if key not in self._text_cache:
            ink = (32, 26, 20)
            # Tight tracking for the headline; crop font ascender padding so
            # the visible digits sit between the printed ornaments and rule.
            glyphs = [self.year_font.render(char, True, ink) for char in year]
            width = max(1, sum(glyph.get_width() for glyph in glyphs) - max(0, len(glyphs) - 1))
            heading = pygame.Surface((width, self.year_font.get_height()), pygame.SRCALPHA)
            x = 0
            for glyph in glyphs:
                heading.blit(glyph, (x, 0))
                x += glyph.get_width() - 1
            heading = heading.subsurface(heading.get_bounding_rect()).copy()
            for size in range(26, 17, -1):
                font = self.body_fonts[size]
                lines = wrap_text(description, font, self.text_rect.width)
                leading = round(size * 1.2)
                if ((len(lines) - 1) * leading + font.get_height() <= self.text_rect.height
                        and all(font.size(line)[0] <= self.text_rect.width for line in lines)):
                    break
            body = [font.render(line, True, ink) for line in lines]
            self._text_cache[key] = heading, body, leading
        return self._text_cache[key]

    def draw(self, surface, position, picture, year, description):
        surface.blit(self.card, position)
        if picture is not None:
            key = id(picture)
            if key not in self._pictures:
                scale = min(self.picture_rect.width / picture.get_width(),
                            self.picture_rect.height / picture.get_height())
                self._pictures[key] = pygame.transform.smoothscale(
                    picture, tuple(round(d * scale) for d in picture.get_size())
                )
            fitted = self._pictures[key]
            surface.blit(fitted, fitted.get_rect(center=self.picture_rect.move(position).center))
        heading, body, leading = self._text(year, description)
        surface.blit(heading, heading.get_rect(center=self.year_rect.move(position).center))
        for index, line in enumerate(body):
            surface.blit(line, (position[0] + self.text_rect.x,
                                position[1] + self.text_rect.y + index * leading))
        surface.blit(self.pin, self.pin.get_rect(center=(position[0] + self.pin_center[0],
                                                       position[1] + self.pin_center[1])))
