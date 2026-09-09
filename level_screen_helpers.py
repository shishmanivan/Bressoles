import os

import pygame

from asset_loaders import load_fitted_image


LEVEL_CONTENT_SIZE = (1680, 1050)
LEVEL_BUTTON_ANCHOR_WIDTH = 40


def level_content_rect(viewport_size):
    """Fit the existing card composition, without enlarging it on ultrawide."""
    width, height = viewport_size
    scale = min(width / LEVEL_CONTENT_SIZE[0], height / LEVEL_CONTENT_SIZE[1], 1.0)
    size = tuple(max(1, round(dimension * scale)) for dimension in LEVEL_CONTENT_SIZE)
    rect = pygame.Rect((0, 0), size)
    rect.center = (width // 2, height // 2)
    return rect


def compute_arrow_position(card_position, card_size, arrow_size, padding=15):
    """Anchor the button's left edge at the original 40px button position."""
    card_x, card_y = card_position
    card_width, card_height = card_size
    arrow_width, arrow_height = arrow_size
    return (
        card_x + card_width - LEVEL_BUTTON_ANCHOR_WIDTH - padding,
        card_y + card_height - arrow_height - padding,
    )


def make_arrow_rect(card_position, card_size, arrow_size, padding=15):
    """Create a Rect for a bottom-right arrow on a card."""
    arrow_position = compute_arrow_position(card_position, card_size, arrow_size, padding=padding)
    return arrow_position, pygame.Rect(arrow_position[0], arrow_position[1], arrow_size[0], arrow_size[1])


def compute_picture_position(card_position, card_height, picture):
    """Return the blit position for a level picture inside the card art box."""
    dark_square_size = 262
    picture_x = card_position[0] + dark_square_size // 2
    picture_y = card_position[1] + card_height // 2
    picture_x -= picture.get_width() // 2
    picture_y -= picture.get_height() // 2
    picture_x -= 4
    picture_y -= 11
    return picture_x, picture_y


def load_primary_level_assets():
    """Load the level pictures shown in the normal campaign selector."""
    level1_picture = load_fitted_image(
        [os.path.join("LevelPage", "Level1Picture.png"), os.path.join("LevelPage", "Level1Picture.jpg")],
        warning_message="WARNING: Level1Picture.png and Level1Picture.jpg not found in LevelPage folder",
    )
    level2_picture = load_fitted_image(
        [os.path.join("LevelPage", "Level2Picture.jpg")],
        warning_message="WARNING: Level2Picture.jpg not found: LevelPage/Level2Picture.jpg",
    )
    level3_picture = load_fitted_image(
        [os.path.join("LevelPage", "Level3Picture.png"), os.path.join("LevelPage", "Level3Picture.jpg")],
        warning_message="WARNING: Level3Picture.png and Level3Picture.jpg not found in LevelPage folder",
    )
    level4_picture = load_fitted_image(
        [os.path.join("LevelPage", "Level4Picture.png"), os.path.join("LevelPage", "Level4Picture.jpg")],
        warning_message=None,
    )
    level5_picture = load_fitted_image(
        [os.path.join("LevelPage", "Level5Picture.png"), os.path.join("LevelPage", "Level5Picture.jpg")],
        warning_message=None,
    )
    level6_picture = load_fitted_image(
        [os.path.join("LevelPage", "Level6Picture.png"), os.path.join("LevelPage", "Level6Picture.jpg")],
        warning_message=None,
    )

    return {
        "level1_picture": level1_picture,
        "level2_picture": level2_picture,
        "level3_picture": level3_picture,
        "level4_picture": level4_picture,
        "level5_picture": level5_picture,
        "level6_picture": level6_picture,
    }


def load_test_level_pictures(num_levels):
    """Load per-level pictures for test mode cards."""
    pictures = []
    for level_num in range(1, num_levels + 1):
        pictures.append(
            load_fitted_image(
                [
                    os.path.join("LevelPage", f"Level{level_num}Picture.png"),
                    os.path.join("LevelPage", f"Level{level_num}Picture.jpg"),
                ],
                warning_message=None,
            )
        )
    return pictures


def build_test_mode_layout(levelcard_image, startarrow_image, screen_width, screen_height, padding_y):
    """Build positions, click rects, and scroll bounds for test mode."""
    if not levelcard_image:
        return {
            "num_levels": 13,
            "cards_per_row": 2,
            "cards_per_col": 7,
            "test_card_positions": [],
            "test_card_rects": [],
            "max_scroll_y": 0,
        }

    num_levels = 13
    cards_per_row = 2
    cards_per_col = 7
    card_width = levelcard_image.get_width()
    card_height = levelcard_image.get_height()
    card_spacing = 50
    total_cards_width = 2 * card_width + card_spacing
    grid_start_x = (screen_width - total_cards_width) // 2
    grid_start_y = padding_y

    test_card_positions = []
    test_card_rects = []
    arrow_size = None
    if startarrow_image:
        arrow_size = (startarrow_image.get_width(), startarrow_image.get_height())

    for level_num in range(1, num_levels + 1):
        row = (level_num - 1) // cards_per_row
        col = (level_num - 1) % cards_per_row
        card_x = grid_start_x + col * (card_width + card_spacing)
        card_y = grid_start_y + row * (card_height + card_spacing)
        card_position = (card_x, card_y)
        test_card_positions.append(card_position)

        if arrow_size:
            _, arrow_rect = make_arrow_rect(card_position, (card_width, card_height), arrow_size)
            test_card_rects.append(arrow_rect)
        else:
            test_card_rects.append(None)

    total_content_height = cards_per_col * (card_height + card_spacing) - card_spacing
    available_height = screen_height - padding_y - padding_y
    max_scroll_y = total_content_height - available_height if total_content_height > available_height else 0

    return {
        "num_levels": num_levels,
        "cards_per_row": cards_per_row,
        "cards_per_col": cards_per_col,
        "test_card_positions": test_card_positions,
        "test_card_rects": test_card_rects,
        "max_scroll_y": max_scroll_y,
    }


def build_normal_mode_layout(levelcard_image, startarrow_image, screen_width, padding_y):
    """Build positions and click rects for normal mode."""
    layout = {
        "card_position": (40, padding_y),
        "card2_position": None,
        "card3_position": None,
        "card4_position": None,
        "card5_position": None,
        "card6_position": None,
        "arrow_position": (0, 0),
        "arrow2_position": (0, 0),
        "arrow3_position": (0, 0),
        "arrow4_position": (0, 0),
        "arrow5_position": (0, 0),
        "arrow6_position": (0, 0),
        "arrow_rect": None,
        "arrow2_rect": None,
        "arrow3_rect": None,
        "arrow4_rect": None,
        "arrow5_rect": None,
        "arrow6_rect": None,
        "card1_rect": None,
        "max_scroll_y": 0,
    }
    if not levelcard_image:
        return layout

    card_width = levelcard_image.get_width()
    card_height = levelcard_image.get_height()
    card_spacing = 50
    total_cards_width = 2 * card_width + card_spacing
    centered_x = (screen_width - total_cards_width) // 2
    card_position = (centered_x, padding_y)
    card2_position = (centered_x + card_width + card_spacing, padding_y)
    card3_position = (centered_x, padding_y + card_height + card_spacing)
    card4_position = (centered_x + card_width + card_spacing, padding_y + card_height + card_spacing)
    card5_position = (centered_x, padding_y + 2 * (card_height + card_spacing))
    card6_position = (centered_x + card_width + card_spacing, padding_y + 2 * (card_height + card_spacing))

    layout.update(
        {
            "card_position": card_position,
            "card2_position": card2_position,
            "card3_position": card3_position,
            "card4_position": card4_position,
            "card5_position": card5_position,
            "card6_position": card6_position,
            "max_scroll_y": max(0, card6_position[1] + card_height + padding_y - 1050),
            "card1_rect": pygame.Rect(card_position[0], card_position[1], card_width, card_height),
        }
    )

    if startarrow_image:
        arrow_size = (startarrow_image.get_width(), startarrow_image.get_height())
        layout["arrow_position"], layout["arrow_rect"] = make_arrow_rect(card_position, (card_width, card_height), arrow_size)
        layout["arrow2_position"], layout["arrow2_rect"] = make_arrow_rect(card2_position, (card_width, card_height), arrow_size)
        layout["arrow3_position"], layout["arrow3_rect"] = make_arrow_rect(card3_position, (card_width, card_height), arrow_size)
        layout["arrow4_position"], layout["arrow4_rect"] = make_arrow_rect(card4_position, (card_width, card_height), arrow_size)
        layout["arrow5_position"], layout["arrow5_rect"] = make_arrow_rect(card5_position, (card_width, card_height), arrow_size)
        layout["arrow6_position"], layout["arrow6_rect"] = make_arrow_rect(card6_position, (card_width, card_height), arrow_size)

    return layout
