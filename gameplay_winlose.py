import random


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
):
    """Apply boss or regular round reward after a win."""
    if gameplay_instance.is_boss_fight and gameplay_instance.boss_index is not None:
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

        if gameplay_instance.level_number in earned_reward_cards:
            earned_reward_cards[gameplay_instance.level_number] = []
            print(
                f"Reset earned cards for level {gameplay_instance.level_number} "
                "after boss victory - deck returns to initial state"
            )
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

    reward1_list = reward_data.get("reward1", [])
    reward2 = reward_data.get("reward2")
    reward2_list = reward2 if isinstance(reward2, list) else ([reward2] if reward2 is not None else [])

    if not reward1_list:
        print(
            f"No reward cards in Reward1 for level {gameplay_instance.level_number}, "
            f"round {round_num}, button {button}"
        )
        return

    reward_card_number1 = _select_reward_card(
        reward1_list,
        gameplay_instance.level_number,
        reward_token_random_red,
        pick_random_red_card_for_level,
    )
    if reward_card_number1 is None:
        return

    earned_reward_cards.setdefault(gameplay_instance.level_number, [])
    earned_reward_cards[gameplay_instance.level_number].append(reward_card_number1)
    gameplay_instance.last_earned_cards.append(reward_card_number1)

    if reward2_list:
        reward_card_number2 = _select_reward_card(
            reward2_list,
            gameplay_instance.level_number,
            reward_token_random_red,
            pick_random_red_card_for_level,
            allow_missing_random_red=True,
        )
        if reward_card_number2 is not None:
            earned_reward_cards[gameplay_instance.level_number].append(reward_card_number2)
            gameplay_instance.last_earned_cards.append(reward_card_number2)
            print(
                f"Earned reward cards {reward_card_number1} (from Reward1) and {reward_card_number2} "
                f"(from Reward2) for level {gameplay_instance.level_number}, round {round_num}, button {button}"
            )
        else:
            print(
                f"Earned reward card {reward_card_number1} (Reward2 skipped) "
                f"for level {gameplay_instance.level_number}, round {round_num}, button {button}"
            )
    else:
        print(
            f"Earned reward card {reward_card_number1} (randomly selected from {reward1_list}) "
            f"for level {gameplay_instance.level_number}, round {round_num}, button {button}"
        )

    print(f"Earned cards for level {gameplay_instance.level_number}: {earned_reward_cards[gameplay_instance.level_number]}")


def reset_level_loss_state(level_number, earned_reward_cards, forced_start_hand_cards_by_level):
    """Reset level-scoped rewards after defeat and return default Dobor."""
    if level_number in earned_reward_cards:
        earned_reward_cards[level_number] = []
        print(f"Reset earned cards for level {level_number} due to defeat")
    if level_number in forced_start_hand_cards_by_level:
        forced_start_hand_cards_by_level[level_number] = []
        print(f"Reset forced starting-hand cards for level {level_number} due to defeat")
    print("Reset Dobor to 1 due to defeat")
    return 1


def _select_reward_card(reward_list, level_number, reward_token_random_red, pick_random_red_card_for_level, allow_missing_random_red=False):
    reward_card_number = random.choice(reward_list)
    if reward_card_number == reward_token_random_red:
        picked = pick_random_red_card_for_level(level_number)
        if picked is None:
            print(f"WARNING: 'Red Card' reward requested but no available red cards for level {level_number}.")
            return None if allow_missing_random_red else None
        reward_card_number = picked
    if reward_card_number == 0:
        reward_card_number = 100
    return reward_card_number
