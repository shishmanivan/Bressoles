import os

import pygame


_scaled_background_cache = {}
_scaled_image_cache = {}
_fitted_image_cache = {}


def find_first_existing_path(paths):
    """Return the first existing path from a list, or None."""
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None


def load_scaled_background(image_path, screen_size, fallback_surface=None, warning_message=None):
    """Load a background image and scale it to the screen."""
    if os.path.exists(image_path):
        cache_key = (image_path, tuple(screen_size))
        cached = _scaled_background_cache.get(cache_key)
        if cached is not None:
            return cached
        background = pygame.image.load(image_path).convert()
        scaled = pygame.transform.smoothscale(background, screen_size).convert()
        _scaled_background_cache[cache_key] = scaled
        return scaled
    if warning_message:
        print(warning_message, image_path)
    return fallback_surface if fallback_surface else None


def load_scaled_image(image_path, scale_factor=None, target_size=None, warning_message=None):
    """Load an alpha image and scale it by factor or explicit size."""
    if not os.path.exists(image_path):
        if warning_message:
            print(warning_message, image_path)
        return None

    cache_key = (image_path, scale_factor, tuple(target_size) if target_size is not None else None)
    cached = _scaled_image_cache.get(cache_key)
    if cached is not None:
        return cached

    image = pygame.image.load(image_path).convert_alpha()
    if target_size is None and scale_factor is not None:
        width = int(image.get_width() * scale_factor)
        height = int(image.get_height() * scale_factor)
        target_size = (width, height)

    if target_size is not None:
        image = pygame.transform.smoothscale(image, target_size).convert_alpha()
    _scaled_image_cache[cache_key] = image
    return image


def load_fitted_image(candidate_paths, box_size=262, padding_scale=0.9, warning_message=None):
    """Load an alpha image and fit it proportionally inside a square box."""
    image_path = find_first_existing_path(candidate_paths)
    if not image_path:
        if warning_message:
            print(warning_message)
        return None

    cache_key = (tuple(candidate_paths), box_size, padding_scale)
    cached = _fitted_image_cache.get(cache_key)
    if cached is not None:
        return cached

    image = pygame.image.load(image_path).convert_alpha()
    original_width = image.get_width()
    original_height = image.get_height()
    scale_factor = min(box_size / original_width, box_size / original_height) * padding_scale
    target_size = (int(original_width * scale_factor), int(original_height * scale_factor))
    fitted = pygame.transform.smoothscale(image, target_size).convert_alpha()
    _fitted_image_cache[cache_key] = fitted
    return fitted


def load_animation_frames(folder_path, target_size=None):
    """Load all PNG frames from a folder, sorted by filename."""
    frames = []
    if not os.path.exists(folder_path):
        print("WARNING: Level1Animation folder not found:", folder_path)
        return frames

    frame_files = sorted([file_name for file_name in os.listdir(folder_path) if file_name.lower().endswith(".png")])
    for frame_file in frame_files:
        frame_path = os.path.join(folder_path, frame_file)
        try:
            frame_img = pygame.image.load(frame_path).convert_alpha()
            if target_size is not None:
                frame_img = pygame.transform.smoothscale(frame_img, target_size).convert_alpha()
            frames.append(frame_img)
        except Exception as e:
            print(f"WARNING: Could not load animation frame {frame_file}: {e}")
    return frames


def load_main_background(screen_size):
    """Load the shared main background image."""
    bg_path = os.path.join("UI", "Background.png")
    return load_scaled_background(
        bg_path,
        screen_size,
        warning_message="WARNING: Background not found:",
    )


def find_font_path_or_exit():
    """Return the first available project font path, or exit like the legacy entrypoint."""
    font_paths = [
        "egyptiennemncyr_condensedbold.ttf",
        "Egyptienne MN CYR.ttf",
        "EgyptienneMN-CYR.ttf",
        "egyptiennemn-cyr.ttf",
        os.path.join("UI", "egyptiennemncyr_condensedbold.ttf"),
        os.path.join("UI", "Egyptienne MN CYR.ttf"),
        os.path.join("UI", "EgyptienneMN-CYR.ttf"),
    ]

    font_path = find_first_existing_path(font_paths)
    if font_path:
        return font_path

    print("ERROR: Font file not found in project folder. Tried:", font_paths)
    raise SystemExit
