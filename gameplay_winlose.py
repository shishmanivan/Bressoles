import random

import game_state
from game_data import REWARD_TOKEN_RANDOM_SILVER


GAIN_DROP_REWARD_WEIGHTS = {
    11: 25,  # +2, 1 turn
    12: 25,  # +2, 2 turns
    15: 20,  # -2, 1 turn
    16: 10,  # -2, 2 turns
    13: 10,  # +4, 1 turn
    14: 10,  # +4, 2 turns
}


def resolve_win_lose_state(current_state, money, goal, day, last_turn):
    """Return the next win/lose state and reason, or (None, None)."""
    if current_state is not None:
        return None, None
    if day == last_turn:
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
):
    """Apply boss or regular round reward after a win."""
    if gameplay_instance.is_boss_fight and gameplay_instance.boss_index is not None:
        if getattr(gameplay_instance, "is_final_boss", False):
            level_reward_cards = game_state.get_level_completion_reward_cards(gameplay_instance.level_number)
            if level_reward_cards and hasattr(gameplay_instance, "last_earned_cards"):
                gameplay_instance.last_earned_cards.extend(level_reward_cards)
            game_state.clear_round_reward_cards(gameplay_instance.level_number)
            print(
                f"Skipped personal boss reward for final boss on level {gameplay_instance.level_number}; "
                f"level reward cards: {level_reward_cards}"
            )
            return

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
            allow_missing_random_red=index > 0,
        )
        if reward_card_number is None:
            if index == 0:
                return
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


def reset_level_loss_state(
    level_number,
    earned_reward_cards,
    forced_start_hand_cards_by_level,
    guaranteed_start_hand_cards_by_level=None,
):
    """Reset level-scoped rewards after defeat and return default Dobor."""
    if level_number in earned_reward_cards:
        earned_reward_cards[level_number] = []
        print(f"Reset earned cards for level {level_number} due to defeat")
    if level_number in forced_start_hand_cards_by_level:
        forced_start_hand_cards_by_level[level_number] = []
        print(f"Reset forced starting-hand cards for level {level_number} due to defeat")
    if guaranteed_start_hand_cards_by_level is not None and level_number in guaranteed_start_hand_cards_by_level:
        guaranteed_start_hand_cards_by_level[level_number] = []
        print(f"Reset guaranteed starting-hand cards for level {level_number} due to defeat")
    print("Reset Dobor to 1 due to defeat")
    return 1


def _select_reward_card(reward_list, level_number, reward_token_random_red, pick_random_red_card_for_level, allow_missing_random_red=False):
    reward_card_number = _choose_reward_card(reward_list)
    if reward_card_number == reward_token_random_red:
        picked = pick_random_red_card_for_level(level_number)
        if picked is None:
            print(f"WARNING: 'Red Card' reward requested but no available red cards for level {level_number}.")
            return None if allow_missing_random_red else None
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
