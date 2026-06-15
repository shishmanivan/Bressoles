import os

import pygame


PAPER_COLOR = (83, 76, 70)


def load_round_reward_assets():
    """Load RoundPage reward preview assets and metadata."""
    target_width = 100
    market_card_ratio = 99 / 171.0
    target_height = int(target_width / market_card_ratio)

    random_drop_image = None
    random_drop_path = os.path.join("RoundPage", "RandomDropGain.png")
    if os.path.exists(random_drop_path):
        random_drop_original = pygame.image.load(random_drop_path).convert_alpha()
        random_drop_image = pygame.transform.smoothscale(random_drop_original, (target_width, target_height)).convert_alpha()
    else:
        print(f"WARNING: RandomDropGain.png not found: {random_drop_path}")

    random_red_image = None
    random_red_path = os.path.join("RoundPage", "RandomRed.png")
    if os.path.exists(random_red_path):
        random_red_original = pygame.image.load(random_red_path).convert_alpha()
        random_red_image = pygame.transform.smoothscale(random_red_original, (target_width, target_height)).convert_alpha()
    else:
        print(f"WARNING: RandomRed.png not found: {random_red_path}")

    card_base_mapping = {}
    for card_id in (1, 2, 3, 4, 100):
        card_base_mapping[card_id] = card_id
    card_base_mapping[11] = 11
    card_base_mapping[12] = 11
    card_base_mapping[13] = 11
    card_base_mapping[14] = 11
    card_base_mapping[15] = 15
    card_base_mapping[16] = 15
    card_base_mapping[17] = 17
    card_base_mapping[18] = 17

    card_actions = {
        11: 2, 12: 2, 13: 4, 14: 4,
        15: -2, 16: -2, 17: 2, 18: 2,
    }
    card_turns = {
        11: 1, 13: 1, 12: 2, 14: 2,
        15: 1, 16: 2, 17: 1, 18: 2,
    }

    return {
        "random_drop_image": random_drop_image,
        "random_red_image": random_red_image,
        "card_base_mapping": card_base_mapping,
        "card_actions": card_actions,
        "card_turns": card_turns,
    }


def draw_card_action_on_surface(surface, action_value, card_id, card_width, card_height, font_path, paper_color=PAPER_COLOR):
    """Draw CardAction value on a card surface."""
    base_market_width = 99
    scale_factor = card_width / base_market_width
    base_font_size = 36
    scaled_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
    if scaled_font_size < 1:
        scaled_font_size = 1

    gadugib_path = "Gadugib.ttf"
    font_path_use = gadugib_path if os.path.exists(gadugib_path) else font_path

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
        print(f"ERROR drawing CardAction on reward card: {e}")


def draw_card_turns_on_surface(surface, turns_value, card_id, card_width, card_height, font_path, paper_color=PAPER_COLOR):
    """Draw CardTurns value on a card surface."""
    base_market_width = 99
    scale_factor = card_width / base_market_width
    base_font_size = 36
    card_action_font_size = int(base_font_size * 0.85 * 0.9 * scale_factor)
    turns_font_size = int(card_action_font_size * 0.648)
    if turns_font_size < 1:
        turns_font_size = 1

    gadugib_path = "Gadugib.ttf"
    font_path_use = gadugib_path if os.path.exists(gadugib_path) else font_path

    try:
        font = pygame.font.Font(font_path_use, turns_font_size)
        turns_text = font.render(str(turns_value), True, paper_color)
        base_bottom_height = 244.0
        height_scale = card_height / base_bottom_height if base_bottom_height > 0 else 1.0
        offset_from_bottom = 75.0 * height_scale
        card_center_x = card_width / 2
        turns_x = card_center_x + 10 * scale_factor
        turns_y = card_height - offset_from_bottom

        if card_id in (17, 18):
            base_market_width = 99.0
            base_market_height = 171.0
            x_scale = card_width / base_market_width if card_width else 1.0
            y_scale = card_height / base_market_height if card_height else 1.0
            turns_x -= 7.0 * x_scale
            turns_y += 2.0 * y_scale

        surface.blit(turns_text, (int(turns_x), int(turns_y)))
    except Exception as e:
        print(f"ERROR drawing CardTurns on reward card: {e}")


def load_reward_card_preview(
    card_number,
    reward_card_images,
    random_red_image,
    card_base_mapping,
    card_actions,
    card_turns,
    font_path,
    reward_token_random_red,
    paper_color=PAPER_COLOR,
):
    """Load and cache a reward card preview image."""
    if card_number == reward_token_random_red:
        return random_red_image
    if card_number == 0:
        card_number = 100
    if card_number in reward_card_images:
        return reward_card_images[card_number]

    target_width = 100
    market_card_ratio = 99 / 171.0
    target_height = int(target_width / market_card_ratio)
    base_card_id = card_base_mapping.get(card_number, card_number)
    card_path = os.path.join("Cards", f"Card_{base_card_id}.png")

    if not os.path.exists(card_path):
        print(f"WARNING: Reward card base not found: {card_path}")
        reward_card_images[card_number] = None
        return None

    card_image = pygame.image.load(card_path).convert_alpha()
    card_surface = pygame.transform.smoothscale(card_image, (target_width, target_height)).convert_alpha()

    if card_number in card_actions:
        draw_card_action_on_surface(
            card_surface,
            card_actions[card_number],
            card_number,
            target_width,
            target_height,
            font_path,
            paper_color=paper_color,
        )
    if card_number in card_turns:
        draw_card_turns_on_surface(
            card_surface,
            card_turns[card_number],
            card_number,
            target_width,
            target_height,
            font_path,
            paper_color=paper_color,
        )

    reward_card_images[card_number] = card_surface
    return card_surface
