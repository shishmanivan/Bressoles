import os

import pygame


_sound_cache = {}
_effects_volume = 1.0


def set_effects_volume(value):
    global _effects_volume
    _effects_volume = max(0.0, min(1.0, float(value)))
    for sound in _sound_cache.values():
        try:
            sound.set_volume(_effects_volume)
        except pygame.error:
            # Tests and display restarts may temporarily tear down the mixer.
            pass
    return _effects_volume



def load_sound(path, warning_label=None):
    """Load and cache an optional sound without failing before mixer startup."""
    normalized_path = os.path.normpath(path)
    if not os.path.exists(normalized_path) or pygame.mixer.get_init() is None:
        return None
    cached = _sound_cache.get(normalized_path)
    if cached is not None:
        try:
            cached.set_volume(_effects_volume)
            return cached
        except pygame.error:
            # A mixer restart invalidates Sound instances created by the old mixer.
            del _sound_cache[normalized_path]
    try:
        sound = pygame.mixer.Sound(normalized_path)
    except pygame.error as error:
        label = warning_label or os.path.basename(normalized_path)
        print(f"WARNING: {label} sound unavailable: {error}")
        return None
    sound.set_volume(_effects_volume)
    _sound_cache[normalized_path] = sound
    return sound


def load_button_sound():
    return load_sound(os.path.join("Sounds", "Click2.wav"), "Click2.wav")


def load_card_hover_sound():
    """Load the soft card-browsing sound shared by menu navigation."""
    return load_sound(os.path.join("Sounds", "Card.wav"), "Card.wav")


def play_action_click():
    sound = load_sound(os.path.join("Sounds", "Cliack3.wav"))
    if sound is not None:
        sound.play()


def load_card_taking_sound():
    return load_sound(
        os.path.join("Sounds", "Taking Card.wav"),
        "Taking Card.wav",
    )
