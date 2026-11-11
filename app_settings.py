import disk_storage
from localization import SUPPORTED_LANGUAGES
import json
import os


SETTINGS_FILE = os.path.join("Profiles", "settings.json")
DEFAULT_MUSIC_VOLUME = 0.8
DEFAULT_SOUND_VOLUME = 1.0


def _clamp_volume(value, default=DEFAULT_MUSIC_VOLUME):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def load_music_volume(path=SETTINGS_FILE):
    try:
        with disk_storage.open_text(path, "r", encoding="utf-8") as source_file:
            data = json.load(source_file)
    except (OSError, ValueError, TypeError):
        return DEFAULT_MUSIC_VOLUME
    if not isinstance(data, dict):
        return DEFAULT_MUSIC_VOLUME
    return _clamp_volume(data.get("music_volume", DEFAULT_MUSIC_VOLUME))


def save_music_volume(volume, path=SETTINGS_FILE):
    normalized_volume = _clamp_volume(volume)
    _save_setting("music_volume", normalized_volume, path)
    return normalized_volume


def load_selected_language(path=SETTINGS_FILE):
    data = _read_settings(path)
    return data.get("language") if data.get("language") in SUPPORTED_LANGUAGES else "RU"


def save_selected_language(language, path=SETTINGS_FILE):
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language")
    _save_setting("language", language, path)
    return language


def _read_settings(path):
    try:
        with disk_storage.open_text(path, encoding="utf-8") as source:
            data = json.load(source)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, TypeError):
        return {}


def _save_setting(key, value, path):
    _save_values({key: value}, path)


def _save_values(values, path):
    data = _read_settings(path)
    data.update(values)
    disk_storage.write_json(path, data)


RESOLUTIONS = ((1280, 800), (1440, 900), (1680, 1050), (1920, 1080), (1920, 1200), (2560, 1440))
_card_information_enabled = True


def load_settings(path=SETTINGS_FILE):
    data = _read_settings(path)
    resolution = data.get("resolution", [1680, 1050])
    if not isinstance(resolution, (list, tuple)) or tuple(resolution) not in RESOLUTIONS:
        resolution = (1680, 1050)
    return {
        "resolution": tuple(resolution),
        "fullscreen": data.get("fullscreen") is True,
        "music_volume": _clamp_volume(data.get("music_volume", DEFAULT_MUSIC_VOLUME)),
        "sound_volume": _clamp_volume(data.get("sound_volume", DEFAULT_SOUND_VOLUME), DEFAULT_SOUND_VOLUME),
        "show_card_info": data.get("show_card_info") is not False,
        "always_lose_unlocked": data.get("always_lose_unlocked") is True,
        "always_lose_warning_locked": data.get("always_lose_warning_locked") is True,
    }


def save_settings(values, path=SETTINGS_FILE):
    _save_values(values, path)


def set_card_information_enabled(enabled):
    global _card_information_enabled
    _card_information_enabled = bool(enabled)


def card_information_enabled():
    return _card_information_enabled
