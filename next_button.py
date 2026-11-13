import os

import pygame

from asset_loaders import load_scaled_image
from localization import get_language, translate


def create_next_button(font_path):
    label = {"RU": "Далее", "ENG": "Next", "DE": "Weiter",
             "HU": "Tovább", "FR": "Suivant"}[get_language()]
    return create_ornate_button(font_path, label)


def create_ornate_button(font_path, label, button_width=167):
    font = pygame.font.Font(font_path, 28)
    artwork = load_scaled_image(os.path.join("UI", "Ornate Button Blank.png"))
    artwork = artwork.subsurface(artwork.get_bounding_rect())
    button = pygame.transform.smoothscale(
        artwork, (button_width, round(button_width * artwork.get_height() / artwork.get_width()))
    )
    for size in range(28, 9, -1):
        font = pygame.font.Font(font_path, size)
        text = font.render(label, True, (62, 36, 9))
        if text.get_bounding_rect().width <= button_width * .70:
            break
    # Align visible letters, excluding the font's empty line margins.
    text = text.subsurface(text.get_bounding_rect())
    text_center = (button.get_width() // 2, button.get_height() // 2 - 7)
    button.blit(text, text.get_rect(center=text_center))
    pressed = pygame.transform.smoothscale(
        button,
        tuple(max(1, int(size * 0.96)) for size in button.get_size()),
    )
    return button, pressed


def draw_ornate_action(page, rect, label, enabled=True):
    """Shared shop action buttons, with the same artwork as Next/End Turn."""
    cache = getattr(page, "_ornate_action_cache", None)
    if cache is None:
        cache = page._ornate_action_cache = {}
    key = (get_language(), label)
    if key not in cache:
        cache[key] = create_ornate_button(page.font_path, translate(label))
    normal, pressed = cache[key]
    center = rect.center
    rect.size = normal.get_size()
    rect.center = center
    hovered = enabled and rect.collidepoint(page.mouse_pos())
    down = hovered and pygame.mouse.get_pressed()[0]
    image = pressed if down else normal
    if not enabled or hovered:
        image = image.copy()
        image.fill((170, 170, 170, 255) if not enabled else (230, 230, 230, 255),
                   special_flags=pygame.BLEND_RGBA_MULT)
    page.screen.blit(image, image.get_rect(center=(center[0], center[1] + (3 if down else 0))))
