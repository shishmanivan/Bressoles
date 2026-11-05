import os

import pygame

from asset_loaders import load_scaled_image
from localization import get_language


def create_next_button(font_path):
    font = pygame.font.Font(font_path, 28)
    artwork = load_scaled_image(os.path.join("UI", "Ornate Button Blank.png"))
    artwork = artwork.subsurface(artwork.get_bounding_rect())
    button_width = 167  # Same visible width as End Turn and the level Back button.
    button = pygame.transform.smoothscale(
        artwork, (button_width, round(button_width * artwork.get_height() / artwork.get_width()))
    )
    label = {"RU": "Далее", "ENG": "Next", "DE": "Weiter",
             "HU": "Tovább", "FR": "Suivant"}[get_language()]
    text = font.render(label, True, (62, 36, 9))
    # Align visible letters, excluding the font's empty line margins.
    text = text.subsurface(text.get_bounding_rect())
    text_center = (button.get_width() // 2, button.get_height() // 2 - 7)
    button.blit(text, text.get_rect(center=text_center))
    pressed = pygame.transform.smoothscale(
        button,
        tuple(max(1, int(size * 0.96)) for size in button.get_size()),
    )
    return button, pressed
