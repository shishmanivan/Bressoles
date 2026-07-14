import os

import pygame

from card_catalog import BID_CARD_VALUES, get_card_image_base_id
from game_data import REWARD_TOKEN_RANDOM_SILVER


def is_bid_card(card_id):
    try:
        return int(card_id) in BID_CARD_VALUES
    except (TypeError, ValueError):
        return False
def load_winlose_card_preview(
    card_number,
    winlose_card_images,
    card_actions,
    card_turns,
    font_path,
    paper_color,
):
    """Load and cache a reward card image for the Win/Lose window."""
    if card_number == 0:
        card_number = 100
    if card_number in winlose_card_images:
        return winlose_card_images[card_number]

    target_width = 100
    market_card_ratio = 99 / 171.0
    target_height = int(target_width / market_card_ratio)

    if card_number == REWARD_TOKEN_RANDOM_SILVER or 200 < int(card_number) < 300:
        card_path = os.path.join("Cards", f"Card_{int(card_number)}.png")
        if not os.path.exists(card_path):
            card_path = os.path.join("RoundPage", "RandSilver.png")
        if not os.path.exists(card_path):
            card_path = os.path.join("Cards", "Card_201.png")
        if not os.path.exists(card_path):
            print(f"WARNING: WinLose silver card not found: {card_path}")
            winlose_card_images[card_number] = None
            return None
        card_image = pygame.image.load(card_path).convert_alpha()
        card_surface = pygame.transform.smoothscale(card_image, (target_width, target_height)).convert_alpha()
        winlose_card_images[card_number] = card_surface
        return card_surface

    base_card_id = get_card_image_base_id(card_number)

    card_path = os.path.join("Cards", f"Card_{base_card_id}.png")
    if not os.path.exists(card_path):
        print(f"WARNING: WinLose card base not found: {card_path}")
        winlose_card_images[card_number] = None
        return None

    card_image = pygame.image.load(card_path).convert_alpha()
    card_surface = pygame.transform.smoothscale(card_image, (target_width, target_height)).convert_alpha()
    draw_bid_modifier_text(card_surface, card_number, 0, 0, (target_width, target_height), font_path)

    if card_number in card_actions:
        draw_preview_card_action(
            card_surface,
            card_actions[card_number],
            card_number,
            target_width,
            target_height,
            font_path,
            paper_color,
        )
    if card_number in card_turns:
        draw_preview_card_turns(
            card_surface,
            card_turns[card_number],
            card_number,
            target_width,
            target_height,
            font_path,
            paper_color,
            adjust_mode="preview",
        )

    winlose_card_images[card_number] = card_surface
    return card_surface


def draw_preview_card_action(
    surface,
    action_value,
    card_id,
    card_width,
    card_height,
    font_path,
    paper_color,
    adjust_mode="preview",
):
    """Draw CardAction value on a scaled preview card surface."""
    base_market_width = 99
    scale_factor = card_width / base_market_width
    base_font_size = 36
    scaled_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
    if scaled_font_size < 1:
        scaled_font_size = 1

    font_path_use = _resolve_effect_font_path(font_path)
    try:
        font = pygame.font.Font(font_path_use, scaled_font_size)
        action_text = font.render(str(action_value), True, paper_color)
        plus_x = card_width - 25 * scale_factor
        plus_y = 10 * scale_factor
        action_x = plus_x - 29 * scale_factor
        action_y = plus_y + 14 * scale_factor
        if card_id in (15, 16):
            action_x -= 11 * scale_factor
        surface.blit(action_text, (int(action_x), int(action_y)))
    except Exception as e:
        print(f"ERROR drawing CardAction on preview card: {e}")


def draw_preview_card_turns(surface, turns_value, card_id, card_width, card_height, font_path, paper_color, adjust_mode="preview"):
    """Draw CardTurns value on a scaled preview card surface."""
    base_market_width = 99
    scale_factor = card_width / base_market_width
    base_font_size = 36
    card_action_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
    turns_font_size = int(card_action_font_size * 0.648)
    if turns_font_size < 1:
        turns_font_size = 1

    font_path_use = _resolve_effect_font_path(font_path)
    try:
        font = pygame.font.Font(font_path_use, turns_font_size)
        turns_text = font.render(str(turns_value), True, paper_color)
        base_bottom_height = 244.0
        height_scale = card_height / base_bottom_height if base_bottom_height > 0 else 1.0
        offset_from_bottom = 75.0 * height_scale
        card_center_x = card_width / 2
        turns_x = card_center_x + 10 * scale_factor
        turns_y = card_height - offset_from_bottom

        surface.blit(turns_text, (int(turns_x), int(turns_y)))
    except Exception as e:
        print(f"ERROR drawing CardTurns on preview card: {e}")


def draw_card_action_text(screen, card_id, card_actions, card_x, card_y, card_size, font_path, paper_color, font_cache):
    """Draw CardAction value next to the + sign on a gameplay card."""
    if card_id is None or card_id not in card_actions:
        return
    if not card_size or len(card_size) < 2 or card_size[0] <= 0:
        return

    action_value = card_actions[card_id]
    base_market_width = 99
    scale_factor = card_size[0] / base_market_width
    base_font_size = 36
    scaled_font_size = int(int(base_font_size * 0.85 * 0.9) * scale_factor)
    if scaled_font_size < 1:
        scaled_font_size = 1

    scaled_font = font_cache.get(scaled_font_size)
    if scaled_font is None:
        try:
            scaled_font = pygame.font.Font(_resolve_effect_font_path(font_path), scaled_font_size)
            font_cache[scaled_font_size] = scaled_font
        except Exception as e:
            print(f"ERROR creating font for CardAction (size {scaled_font_size}): {e}")
            return

    plus_x = card_x + card_size[0] - 25 * scale_factor
    plus_y = card_y + 10 * scale_factor
    action_x = plus_x - 29 * scale_factor
    action_y = plus_y + 14 * scale_factor
    if card_id in (15, 16):
        action_x -= 11 * scale_factor

    try:
        action_text = scaled_font.render(str(action_value), True, paper_color)
        if action_text:
            screen.blit(action_text, (action_x, action_y))
    except Exception as e:
        print(f"ERROR rendering CardAction text: {e}")


def draw_card_turns_text(
    screen,
    card_id,
    card_turns,
    card_x,
    card_y,
    card_size,
    font_path,
    paper_color,
    font_cache,
    turns_remaining=None,
):
    """Draw CardTurns value on a gameplay card."""
    if card_id is None or card_id not in card_turns:
        return
    if not card_size or len(card_size) < 2 or card_size[0] <= 0:
        return

    turns_value = turns_remaining if turns_remaining is not None else card_turns[card_id]
    base_market_width = 99
    scale_factor = card_size[0] / base_market_width
    base_font_size = 36
    card_action_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
    turns_font_size = int(card_action_font_size * 0.648)
    if turns_font_size < 1:
        turns_font_size = 1

    scaled_font = font_cache.get(turns_font_size)
    if scaled_font is None:
        try:
            scaled_font = pygame.font.Font(_resolve_effect_font_path(font_path), turns_font_size)
            font_cache[turns_font_size] = scaled_font
        except Exception as e:
            print(f"ERROR creating font for CardTurns (size {turns_font_size}): {e}")
            return

    try:
        turns_text = scaled_font.render(str(turns_value), True, paper_color)
        if turns_text:
            card_center_x = card_x + card_size[0] / 2
            turns_x = card_center_x + 10 * scale_factor
            base_bottom_height = 244.0
            current_height = float(card_size[1])
            height_scale = current_height / base_bottom_height if base_bottom_height > 0 else 1.0
            offset_from_bottom = 75.0 * height_scale
            turns_y = card_y + card_size[1] - offset_from_bottom

            screen.blit(turns_text, (turns_x, turns_y))
    except Exception as e:
        print(f"ERROR rendering CardTurns text: {e}")


def draw_bear_modifier_text(
    screen,
    card_id,
    card_x,
    card_y,
    card_size,
    font_path,
    paper_color,
    adjust_mode="default",
    modifier_percent=None,
):
    """Draw Bear's visible goal modifier next to the card title."""
    try:
        if int(card_id) != 401:
            return
    except (TypeError, ValueError):
        return
    if not card_size or len(card_size) < 2 or card_size[0] <= 0:
            return

    if adjust_mode == "shop":
        font_size = max(1, int(card_size[0] * 0.18))
        x_ratio = 0.53
        y_ratio = 0.07
    else:
        font_size = max(1, int(card_size[0] * 0.20))
        x_ratio = 0.57
        y_ratio = 0.075
    try:
        try:
            percent = int(modifier_percent)
        except (TypeError, ValueError):
            percent = 2
        percent = max(2, percent)
        font = pygame.font.Font(_resolve_effect_font_path(font_path), font_size)
        text = font.render(f"-{percent}%", True, paper_color)
        x = card_x + card_size[0] * x_ratio
        y = card_y + card_size[1] * y_ratio
        screen.blit(text, (int(x), int(y)))
    except Exception as e:
        print(f"ERROR rendering Bear modifier text: {e}")


def draw_bid_modifier_text(
    screen,
    card_id,
    card_x,
    card_y,
    card_size,
    font_path,
):
    """Draw the BID amount on card variants that share Card_118.png."""
    try:
        amount = BID_CARD_VALUES[int(card_id)]
    except (TypeError, ValueError, KeyError):
        return
    if not card_size or len(card_size) < 2 or card_size[0] <= 0:
        return

    font_size = max(1, int(card_size[0] * 0.18))
    try:
        font = pygame.font.Font(_resolve_effect_font_path(font_path), font_size)
        text = font.render(str(amount), True, (18, 18, 18))
        x = card_x + card_size[0] * 0.56
        y = card_y + card_size[1] * 0.055
        screen.blit(text, (int(x), int(y)))
    except Exception as e:
        print(f"ERROR rendering BID modifier text: {e}")


def _resolve_effect_font_path(font_path):
    gadugib_path = "Gadugib.ttf"
    if os.path.exists(gadugib_path):
        return gadugib_path
    return font_path
