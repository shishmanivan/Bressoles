from localization import SUPPORTED_LANGUAGES
import json
import os
import tempfile


SETTINGS_FILE = os.path.join("Profiles", "settings.json")
DEFAULT_MUSIC_VOLUME = 1.0


def _clamp_volume(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return DEFAULT_MUSIC_VOLUME


def load_music_volume(path=SETTINGS_FILE):
    try:
        with open(path, "r", encoding="utf-8") as source_file:
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
        with open(path, encoding="utf-8") as source:
            data = json.load(source)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_setting(key, value, path):
    data = _read_settings(path)
    data[key] = value
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
            json.dump(data, output_file, ensure_ascii=False, indent=2)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise
