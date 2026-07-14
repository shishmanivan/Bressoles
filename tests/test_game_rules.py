import unittest

from boss_logic import apply_boss_functionality, apper_goal_boost
from game_data import (
    get_level2_goal,
    get_level3_goal,
    get_level4_goal,
    get_level5_goal,
    load_levels_config,
    load_rewards_config,
)
from gameplay_deck import build_initial_deck, deal_starting_hand
from gameplay_price_helpers import build_market_probabilities
from gameplay_winlose import resolve_win_lose_state


class DummyGameplay:
    def __init__(self):
        self.LastTurn = 8
        self.hand = 7


class LevelAndGoalRulesTests(unittest.TestCase):
    def test_level_structure_matches_the_documented_campaign(self):
        config = load_levels_config()
        self.assertEqual(
            {level: (row["Rounds"], row["Bosses"]) for level, row in config.items()},
            {1: (1, 1), 2: (2, 2), 3: (3, 3), 4: (3, 3), 5: (3, 4)},
        )

    def test_level2_goals_have_two_progression_stages(self):
        self.assertEqual(get_level2_goal(1, "e", 0), 50)
        self.assertEqual(get_level2_goal(2, "m", 1), 160)
        self.assertEqual(get_level2_goal(None, "e", 0, True), 160)
        self.assertEqual(get_level2_goal(None, "m", 1, True), 300)

    def test_level3_goals_cover_regular_and_boss_rounds(self):
        self.assertEqual(get_level3_goal(1, "e", 0), 70)
        self.assertEqual(get_level3_goal(5, "h", 0), 300)
        self.assertEqual(get_level3_goal(None, "e", 0, True), 350)
        self.assertEqual(get_level3_goal(None, "m", 2, True), 500)

    def test_level4_goals_match_level3(self):
        self.assertEqual(
            [get_level4_goal(None, "e", defeated_count, True) for defeated_count in range(3)],
            [350, 400, 500],
        )

    def test_level5_data_preserves_the_former_level4_boss_goals(self):
        self.assertEqual(
            [get_level5_goal(None, "e", defeated_count, True) for defeated_count in range(4)],
            [320, 400, 500, 600],
        )

    def test_apper_goal_is_rounded_up_to_tens(self):
        self.assertEqual(apper_goal_boost(50), 70)
        self.assertEqual(apper_goal_boost(120), 160)

    def test_reward_data_covers_every_reachable_regular_round(self):
        rewards = load_rewards_config()
        expected_coverage = {
            2: (3, "EM"),
            3: (4, "EMH"),
            4: (4, "EMH"),
            5: (4, "EMH"),
        }
        for level, (maximum_round, difficulties) in expected_coverage.items():
            for round_number in range(1, maximum_round + 1):
                for difficulty in difficulties:
                    with self.subTest(level=level, round=round_number, difficulty=difficulty):
                        self.assertIn((level, round_number, difficulty), rewards)


class MarketRulesTests(unittest.TestCase):
    def test_base_market_probabilities_match_the_rules(self):
        self.assertEqual(
            build_market_probabilities(),
            {
                0: {"fall": 0.0, "flat": 15.0, "rise": 85.0},
                1: {"fall": 10.0, "flat": 20.0, "rise": 70.0},
                2: {"fall": 30.0, "flat": 20.0, "rise": 50.0},
            },
        )

    def test_probability_cards_keep_every_market_at_one_hundred_percent(self):
        cards = {
            0: {0: 1, 1: 2, 2: 3},
            1: {0: 4, 1: 4},
            2: {0: 1, 1: 3},
        }
        for bonus in (0, 4, 7, 11, 100):
            probabilities = build_market_probabilities(cards, probability_card_bonus=bonus)
            for market, values in probabilities.items():
                with self.subTest(bonus=bonus, market=market):
                    self.assertAlmostEqual(sum(values.values()), 100.0)
                    self.assertTrue(all(value >= 0 for value in values.values()))


class DeckRulesTests(unittest.TestCase):
    def test_red_cards_are_deduplicated_across_all_deck_sources(self):
        deck = build_initial_deck(
            level_number=4,
            earned_reward_cards={4: [112, 112, 113, 113]},
            level_completion_reward_cards=[12],
            removed_cards_by_level={},
            shop_deck_cards=[117, 117],
            temporary_reward_cards=[112, 15],
        )
        red_cards = [card_id for card_id in deck if 100 < card_id < 200]
        self.assertEqual(len(red_cards), len(set(red_cards)))
        self.assertEqual(set(red_cards), {112, 113, 117})
        self.assertEqual(deck.count(1), 2)

    def test_available_guaranteed_cards_are_dealt_first(self):
        remaining, hand = deal_starting_hand([100, 1, 2, 112, 113], 3, [112, 113])
        self.assertEqual(hand[:2], [112, 113])
        self.assertNotIn(112, remaining)
        self.assertNotIn(113, remaining)


class TurnAndBossRulesTests(unittest.TestCase):
    def test_early_goal_completion_is_a_win(self):
        self.assertEqual(resolve_win_lose_state(None, 100, 100, 3, 8), ("win", "early"))

    def test_play_continues_below_goal_before_terminal_counter(self):
        self.assertEqual(resolve_win_lose_state(None, 99, 100, 7, 8), (None, None))

    def test_reaching_the_eighth_day_ends_the_game(self):
        self.assertEqual(resolve_win_lose_state(None, 99, 100, 8, 8), ("lose", "last_turn"))
        self.assertEqual(resolve_win_lose_state(None, 100, 100, 8, 8), ("win", "last_turn"))

    def test_futures_moves_the_terminal_day_to_nine(self):
        self.assertEqual(resolve_win_lose_state(None, 99, 100, 8, 9), (None, None))
        self.assertEqual(resolve_win_lose_state(None, 99, 100, 9, 9), ("lose", "last_turn"))

    def test_boss_functionality_parser_applies_each_modifier_once(self):
        gameplay = DummyGameplay()
        apply_boss_functionality("LastTurn=LastTurn-1", gameplay)
        apply_boss_functionality("Self.hand=Self.hand-1", gameplay)
        self.assertEqual(gameplay.LastTurn, 7)
        self.assertEqual(gameplay.hand, 6)


if __name__ == "__main__":
    unittest.main()
