import random

import pygame

import game_state
from game_data import REWARD_TOKEN_RANDOM_SILVER
from shared_utils import wrap_text


GAIN_DROP_REWARD_WEIGHTS = {
    11: 25,  # +2, 1 turn
    12: 25,  # +2, 2 turns
    15: 20,  # -2, 1 turn
    16: 10,  # -2, 2 turns
    13: 10,  # +4, 1 turn
    14: 10,  # +4, 2 turns
}


WIN_RESULT_CARD_RATIO = 99 / 171.0


def build_win_result_layout(
    font_path,
    text_blocks,
    window_rect,
    ok_button_rect,
    card_count,
    max_font_size=36,
    min_font_size=22,
    extra_text_lines=0,
):
    """Fit result text and reward cards inside the newspaper window."""
    text_top = window_rect.top + 75
    text_width = window_rect.width - 40
    card_bottom = window_rect.bottom - 18
    card_area_left = window_rect.left + 20
    card_area_right = min(window_rect.right - 20, ok_button_rect.left - 15)
    card_gap = 10
    normalized_card_count = max(0, int(card_count or 0))

    selected = None
    for font_size in range(max_font_size, min_font_size - 1, -2):
        font = pygame.font.Font(font_path, font_size)
        lines = []
        for text in text_blocks:
            if text:
                lines.extend(wrap_text(str(text), font, text_width))
        line_height = font.get_height() + 5
        text_bottom = text_top + (len(lines) + max(0, int(extra_text_lines or 0))) * line_height

        card_width = 0
        card_height = 0
        if normalized_card_count:
            horizontal_width = (
                card_area_right
                - card_area_left
                - card_gap * (normalized_card_count - 1)
            ) // normalized_card_count
            vertical_height = card_bottom - text_bottom - 5
            card_width = min(100, horizontal_width, int(vertical_height * WIN_RESULT_CARD_RATIO))
            card_height = int(card_width / WIN_RESULT_CARD_RATIO) if card_width > 0 else 0
            if card_width < 48:
                continue

        selected = {
            "font": font,
            "font_size": font_size,
            "lines": lines,
            "line_height": line_height,
            "text_top": text_top,
            "text_bottom": text_bottom,
            "card_width": card_width,
            "card_height": card_height,
            "card_gap": card_gap,
            "card_bottom": card_bottom,
            "card_area_left": card_area_left,
            "card_area_right": card_area_right,
        }
        break

    if selected is None:
        font = pygame.font.Font(font_path, min_font_size)
        lines = []
        for text in text_blocks:
            if text:
                lines.extend(wrap_text(str(text), font, text_width))
        line_height = font.get_height() + 5
        text_bottom = text_top + (len(lines) + max(0, int(extra_text_lines or 0))) * line_height
        horizontal_width = (
            card_area_right
            - card_area_left
            - card_gap * max(0, normalized_card_count - 1)
        ) // max(1, normalized_card_count)
        vertical_height = max(1, card_bottom - text_bottom - 5)
        card_width = max(1, min(100, horizontal_width, int(vertical_height * WIN_RESULT_CARD_RATIO)))
        selected = {
            "font": font,
            "font_size": min_font_size,
            "lines": lines,
            "line_height": line_height,
            "text_top": text_top,
            "text_bottom": text_bottom,
            "card_width": card_width if normalized_card_count else 0,
            "card_height": int(card_width / WIN_RESULT_CARD_RATIO) if normalized_card_count else 0,
            "card_gap": card_gap,
            "card_bottom": card_bottom,
            "card_area_left": card_area_left,
            "card_area_right": card_area_right,
        }

    total_cards_width = (
        normalized_card_count * selected["card_width"]
        + max(0, normalized_card_count - 1) * selected["card_gap"]
    )
    selected["card_start_x"] = card_area_left + (
        card_area_right - card_area_left - total_cards_width
    ) // 2
    selected["card_y"] = selected["card_bottom"] - selected["card_height"]
    return selected


def resolve_win_lose_state(current_state, money, goal, day, last_turn):
    """Return the next win/lose state and reason, or (None, None)."""
    if current_state is not None:
        return None, None
    if day >= last_turn:
        if money >= goal:
            return "win", "last_turn"
        return "lose", "last_turn"
    if money >= goal:
        return "win", "early"
    return None, None


def get_win_lose_start_y(win_lose_image):
    """Return the slide-in start Y for a WinLose image."""
    if not win_lose_image:
        return None
    return float(-win_lose_image.get_height())


def apply_win_reward(
    gameplay_instance,
    earned_reward_cards,
    rewards,
    reward_token_random_red,
    load_boss_rewards,
    get_boss_number_from_index,
    apply_boss_reward,
    pick_random_red_card_for_level,
    add_silver_card,
    get_boss_number_from_filename=None,
):
    """Apply boss or regular round reward after a win."""
    if gameplay_instance.is_boss_fight and gameplay_instance.boss_index is not None:
        if getattr(gameplay_instance, "is_final_boss", False):
            level_reward_cards = game_state.get_level_completion_reward_cards(gameplay_instance.level_number)
            if level_reward_cards and hasattr(gameplay_instance, "last_earned_cards"):
                gameplay_instance.last_earned_cards.extend(level_reward_cards)
            black_reward_cards = game_state.get_level_completion_black_reward_cards(gameplay_instance.level_number)
            awarded_black_cards = []
            existing_black_cards = set()
            for existing_card_id in game_state.black_cards or []:
                try:
                    existing_black_cards.add(int(existing_card_id))
                except (TypeError, ValueError):
                    continue
            for card_id in black_reward_cards:
                try:
                    normalized = int(card_id)
                except (TypeError, ValueError):
                    continue
                if normalized in existing_black_cards:
                    continue
                awarded = game_state.add_black_card(normalized)
                if awarded is not None:
                    awarded_black_cards.append(awarded)
                    existing_black_cards.add(normalized)
            if awarded_black_cards and hasattr(gameplay_instance, "last_earned_cards"):
                gameplay_instance.last_earned_cards.extend(awarded_black_cards)
            game_state.clear_round_reward_cards(gameplay_instance.level_number)
            print(
                f"Skipped personal boss reward for final boss on level {gameplay_instance.level_number}; "
                f"level reward cards: {level_reward_cards}; black reward cards: {awarded_black_cards}"
            )
            return

        boss_number = None
        if get_boss_number_from_filename:
            boss_number = get_boss_number_from_filename(
                getattr(gameplay_instance, "boss_filename", None)
            )
        if not boss_number:
            boss_number = get_boss_number_from_index(
                gameplay_instance.level_number,
                gameplay_instance.boss_index,
                gameplay_instance.defeated_count,
            )
        if boss_number:
            boss_rewards = load_boss_rewards()
            boss_entry = boss_rewards.get(boss_number) or {}
            reward_string = boss_entry.get("Reward") if isinstance(boss_entry, dict) else None
            if reward_string:
                apply_boss_reward(reward_string, gameplay_instance)
                print(
                    f"Applied boss reward for boss {boss_number} "
                    f"(level {gameplay_instance.level_number}, index {gameplay_instance.boss_index}): {reward_string}"
                )
            else:
                print(
                    f"No boss reward found for boss {boss_number} "
                    f"(level {gameplay_instance.level_number}, index {gameplay_instance.boss_index})"
                )

        game_state.clear_round_reward_cards(gameplay_instance.level_number)
        return

    round_num = (
        gameplay_instance.round_num
        if gameplay_instance.round_num is not None
        else (1 if gameplay_instance.difficulty == "e" else (2 if gameplay_instance.difficulty == "m" else 3))
    )
    button = gameplay_instance.difficulty.upper()
    reward_key = (gameplay_instance.level_number, round_num, button)
    reward_data = rewards.get(reward_key)

    if not reward_data:
        print(
            f"No reward data found for level {gameplay_instance.level_number}, "
            f"round {round_num}, button {button}"
        )
        return

    reward_lists = []
    for reward_key_part in ("reward1", "reward2", "reward3"):
        reward_value = reward_data.get(reward_key_part)
        reward_list = reward_value if isinstance(reward_value, list) else ([reward_value] if reward_value is not None else [])
        if reward_list:
            reward_lists.append((reward_key_part, reward_list))

    if not reward_lists:
        print(
            f"No reward cards in Reward1 for level {gameplay_instance.level_number}, "
            f"round {round_num}, button {button}"
        )
        return

    earned_reward_cards.setdefault(gameplay_instance.level_number, [])
    selected_rewards = []
    for index, (reward_key_part, reward_list) in enumerate(reward_lists):
        reward_card_number = _select_reward_card(
            reward_list,
            gameplay_instance.level_number,
            reward_token_random_red,
            pick_random_red_card_for_level,
        )
        if reward_card_number is None:
            print(
                f"Skipped {reward_key_part} for level {gameplay_instance.level_number}, "
                f"round {round_num}, button {button}"
            )
            continue
        if reward_card_number == REWARD_TOKEN_RANDOM_SILVER:
            reward_card_number = add_silver_card(reward_card_number, gameplay_instance.level_number)
            if reward_card_number is None:
                continue
        else:
            earned_reward_cards[gameplay_instance.level_number].append(reward_card_number)
        gameplay_instance.last_earned_cards.append(reward_card_number)
        selected_rewards.append((reward_key_part, reward_card_number))

    if selected_rewards:
        selected_text = ", ".join(f"{card} ({key})" for key, card in selected_rewards)
        print(
            f"Earned reward cards {selected_text} "
            f"for level {gameplay_instance.level_number}, round {round_num}, button {button}"
        )
    else:
        print(
            f"No reward cards selected "
            f"for level {gameplay_instance.level_number}, round {round_num}, button {button}"
        )

    print(
        f"Temporary reward cards for level {gameplay_instance.level_number}: "
        f"{earned_reward_cards[gameplay_instance.level_number]}"
    )


def _select_reward_card(reward_list, level_number, reward_token_random_red, pick_random_red_card_for_level):
    reward_card_number = _choose_reward_card(reward_list)
    if reward_card_number == reward_token_random_red:
        picked = pick_random_red_card_for_level(level_number)
        if picked is None:
            print(f"WARNING: 'Red Card' reward requested but no available red cards for level {level_number}.")
            return None
        reward_card_number = picked
    if reward_card_number == REWARD_TOKEN_RANDOM_SILVER:
        return REWARD_TOKEN_RANDOM_SILVER
    if reward_card_number == 0:
        reward_card_number = 100
    return reward_card_number


def _choose_reward_card(reward_list):
    if _is_gain_drop_reward_list(reward_list):
        weighted_cards = []
        weighted_values = []
        for card_id in reward_list:
            try:
                normalized = int(card_id)
            except (TypeError, ValueError):
                continue
            weight = GAIN_DROP_REWARD_WEIGHTS.get(normalized, 0)
            if weight > 0:
                weighted_cards.append(normalized)
                weighted_values.append(weight)
        if weighted_cards:
            return random.choices(weighted_cards, weights=weighted_values, k=1)[0]
    return random.choice(reward_list)


def _is_gain_drop_reward_list(reward_list):
    if not reward_list:
        return False
    for card_id in reward_list:
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            return False
        if normalized not in GAIN_DROP_REWARD_WEIGHTS:
            return False
    return True
