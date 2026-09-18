import os

import pygame

from asset_loaders import load_scaled_background, load_scaled_image
from adaptive_ui import cover_geometry, proportional_size


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050

# Center of the two ink strokes in the 1938 x 811 transparent PNG.
COORDINATES_SOURCE_ORIGIN = (159, 676)
ROUND_GRAPH_ORIGIN = (235, SCREEN_HEIGHT - 218)
# Muted warm brown ink, shared by the axes and routes on both selection pages.
GRAPH_INK_COLOR = (105, 92, 78)


def build_round_coordinates_layer(source, screen_size=(SCREEN_WIDTH, SCREEN_HEIGHT)):
    """Keep the axes proportional and align their intersection with the route."""
    source = source.copy()
    # Use the same ink as the routes; retain the soft outline of the artwork.
    source.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    source.fill((*GRAPH_INK_COLOR, 0), special_flags=pygame.BLEND_RGBA_ADD)
    core = pygame.mask.from_surface(source, 199).to_surface(
        setcolor=(*GRAPH_INK_COLOR, 255), unsetcolor=(0, 0, 0, 0)
    )
    source.blit(core, (0, 0))
    size = proportional_size(source.get_size(), width=1500)
    origin = (
        round(COORDINATES_SOURCE_ORIGIN[0] * size[0] / source.get_width()),
        round(COORDINATES_SOURCE_ORIGIN[1] * size[1] / source.get_height()),
    )
    position = tuple(target - local for target, local in zip(ROUND_GRAPH_ORIGIN, origin))
    layer = pygame.Surface(screen_size, pygame.SRCALPHA)
    layer.blit(pygame.transform.smoothscale(source, size), position)
    return layer


_round_page_static_assets_cache = None
_boss_visual_assets_cache = {}


def load_round_page_static_assets():
    """Load the static assets used by RoundPage."""
    global _round_page_static_assets_cache
    if _round_page_static_assets_cache is not None:
        return dict(_round_page_static_assets_cache)

    background_path = os.path.join("RoundPage", "Master background.png")
    master = load_scaled_image(
        background_path,
        warning_message="WARNING: RoundPage Master background.png not found:",
    )
    background = None
    if master is not None:
        size, position = cover_geometry(master.get_size(), (SCREEN_WIDTH, SCREEN_HEIGHT))
        background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        background.blit(load_scaled_background(background_path, size), position)

    koordinates = load_scaled_image(
        os.path.join("RoundPage", "Koordinates.png"),
        warning_message="WARNING: Koordinates.png not found:",
    )
    if koordinates is not None:
        koordinates = build_round_coordinates_layer(koordinates)

    button_e = _load_scaled_button(os.path.join("RoundPage", "LevelButtonE.png"), "WARNING: LevelButtonE not found:")
    button_m = _load_scaled_button(os.path.join("RoundPage", "LevelButtonM.png"), "WARNING: LevelButtonM not found:")
    button_h = _load_scaled_button(os.path.join("RoundPage", "LevelButtonH.png"), "WARNING: LevelButtonH not found:")

    napoleondor_image = load_scaled_image(
        os.path.join("Shop", "Napoleondor.png"),
        target_size=(28, 28),
        warning_message="WARNING: Napoleondor.png not found:",
    )

    popup_path = os.path.join("Bosses", "PopUp2.png")
    if not os.path.exists(popup_path):
        popup_path = os.path.join("Bosses", "PopUp2.jpg")
    popup_image = None
    popup_width = 250
    if os.path.exists(popup_path):
        popup_original = pygame.image.load(popup_path).convert_alpha()
        scaled_width = int((popup_original.get_width() // 2) * 0.8)
        scaled_height = int((popup_original.get_height() // 2) * 0.8)
        popup_image = pygame.transform.smoothscale(popup_original, (scaled_width, scaled_height)).convert_alpha()
        popup_width = scaled_width
    else:
        print(f"WARNING: PopUp2.png/PopUp2.jpg not found: {popup_path}")

    pen_sound_path = os.path.join("Sounds", "Pen.mp3")
    if os.path.exists(pen_sound_path):
        pen_sound = pygame.mixer.Sound(pen_sound_path)
    else:
        print(f"WARNING: Pen.mp3 not found at {pen_sound_path}")
        pen_sound = None

    assets = {
        "background": background,
        "koordinates": koordinates,
        "button_e": button_e,
        "button_m": button_m,
        "button_h": button_h,
        "napoleondor_image": napoleondor_image,
        "popup_image": popup_image,
        "popup_width": popup_width,
        "pen_sound": pen_sound,
    }
    _round_page_static_assets_cache = assets
    return dict(assets)


def build_round_button_base_rects(button_goals, button_images, button_x=350, base_y=SCREEN_HEIGHT - 400, icon_center_gap_y=100):
    """Build the base button rects for E/M/H icons."""
    button_base_rects = {"e": None, "m": None, "h": None}
    last_center_y = None

    for key in ["e", "m", "h"]:
        img = None
        if key == "e":
            img = button_images.get("e") if button_goals.get("e") is not None else None
        elif key == "m":
            img = button_images.get("m") if button_goals.get("m") is not None else None
        elif key == "h":
            img = button_images.get("h") if button_goals.get("h") is not None else None

        if not img:
            continue

        w, h = img.get_width(), img.get_height()
        if last_center_y is None:
            center_y = base_y + (h / 2.0)
        else:
            center_y = last_center_y - icon_center_gap_y

        y = int(round(center_y - (h / 2.0)))
        rect = pygame.Rect(button_x, y, w, h)
        button_base_rects[key] = rect
        last_center_y = rect.centery

    return button_base_rects


def load_boss_icon_assets(level_number, boss_index, boss_filename, completed_count, level_rounds, prev_selection_rect, fallback_anchor_rect):
    """Load the boss icon and its animation frames when boss becomes active."""
    if level_rounds < 0 or completed_count < level_rounds:
        return None, None, []

    resolved_boss_filename = boss_filename
    if not resolved_boss_filename:
        if level_number == 1 and boss_index == 0:
            resolved_boss_filename = "1_Watt.png"
        elif level_number == 2 and boss_index == 0:
            resolved_boss_filename = "2_AdamSmith.png"
        elif level_number == 2 and boss_index == 1:
            resolved_boss_filename = "3_RobertFulton.png"

    if not resolved_boss_filename:
        return None, None, []

    boss_icon, animation_frames = _load_boss_visual_assets(resolved_boss_filename)
    if boss_icon is None:
        return None, None, []

    boss_icon_rect = None
    anchor_rect = prev_selection_rect or fallback_anchor_rect
    if anchor_rect:
        boss_x = anchor_rect.centerx + 200
        boss_y = anchor_rect.centery - 70
        boss_icon_rect = pygame.Rect(boss_x - 50, boss_y - 50, 100, 100)
        if boss_icon_rect.top < 0:
            boss_icon_rect.top = 0

    return boss_icon, boss_icon_rect, list(animation_frames)


def _load_boss_visual_assets(resolved_boss_filename):
    cached = _boss_visual_assets_cache.get(resolved_boss_filename)
    if cached is not None:
        return cached

    boss_path = os.path.join("Bosses", resolved_boss_filename)
    if not os.path.exists(boss_path):
        return None, ()

    boss_icon = load_scaled_image(boss_path, target_size=(100, 100))
    base_name = os.path.splitext(resolved_boss_filename)[0]
    boss_folder = os.path.join("Bosses", base_name)
    if not os.path.isdir(boss_folder):
        matching_folders = sorted(
            folder_name
            for folder_name in os.listdir("Bosses")
            if os.path.isdir(os.path.join("Bosses", folder_name))
            and folder_name.lower().endswith(f"_{base_name.lower()}")
        )
        if matching_folders:
            boss_folder = os.path.join("Bosses", matching_folders[0])
    animation_frames = []
    if os.path.exists(boss_folder) and os.path.isdir(boss_folder):
        for frame_num in range(7):
            frame_filename = f"{base_name}{frame_num}.png"
            frame_path = os.path.join(boss_folder, frame_filename)
            if not os.path.exists(frame_path):
                matching_frames = sorted(
                    filename
                    for filename in os.listdir(boss_folder)
                    if filename.lower().endswith(f"{frame_num}.png")
                )
                if matching_frames:
                    frame_path = os.path.join(boss_folder, matching_frames[0])
            if os.path.exists(frame_path):
                frame_image = pygame.image.load(frame_path).convert_alpha()
                frame_image = pygame.transform.smoothscale(frame_image, (100, 100)).convert_alpha()
                animation_frames.append(frame_image)
            else:
                print(f"WARNING: Animation frame not found: {frame_path}")
    else:
        print(f"WARNING: Boss animation folder not found: {boss_folder}")

    assets = (boss_icon, tuple(animation_frames))
    _boss_visual_assets_cache[resolved_boss_filename] = assets
    return assets


def _load_scaled_button(button_path, warning_message):
    if os.path.exists(button_path):
        button_original = pygame.image.load(button_path).convert_alpha()
        new_width = button_original.get_width() // 5
        new_height = button_original.get_height() // 5
        return pygame.transform.smoothscale(button_original, (new_width, new_height)).convert_alpha()
    print(warning_message, button_path)
    return None
