import os

import pygame


_sound_cache = {}


def load_sound(path, warning_label=None):
    """Load and cache an optional sound without failing before mixer startup."""
    normalized_path = os.path.normpath(path)
    if normalized_path in _sound_cache:
        return _sound_cache[normalized_path]
    if not os.path.exists(normalized_path) or pygame.mixer.get_init() is None:
        return None
    try:
        sound = pygame.mixer.Sound(normalized_path)
    except pygame.error as error:
        label = warning_label or os.path.basename(normalized_path)
        print(f"WARNING: {label} sound unavailable: {error}")
        return None
    _sound_cache[normalized_path] = sound
    return sound


def load_button_sound():
    return load_sound(os.path.join("Sounds", "Button.wav"), "Button.wav")


def load_card_taking_sound():
    return load_sound(
        os.path.join("Sounds", "Taking-playing-card-522520.wav"),
        "Taking-playing-card-522520.wav",
    )
