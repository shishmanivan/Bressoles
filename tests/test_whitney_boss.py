import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager
from boss_logic import (
    BOSS_LEVELS, LEVEL_BOSS_ROUNDS, _ensure_level3_roster,
    _generate_level3_boss_roster, apply_boss_functionality, apply_boss_reward,
    get_bosses_for_boss_level,
)
from game_data import load_boss_rewards
from gameplay_page import GameplayPage


class WhitneyBossTests(unittest.TestCase):
    def test_available_from_level_two_and_in_later_boss_pools(self):
        self.assertNotIn("16_Whitney.png", [boss for step in LEVEL_BOSS_ROUNDS[1] for boss in step])
        self.assertIn("16_Whitney.png", LEVEL_BOSS_ROUNDS[2][0])
        # Levels 3 and 4 share this random roster generator.
        with mock.patch("boss_logic.random.shuffle", side_effect=lambda pool: pool.reverse()):
            roster = _generate_level3_boss_roster(3)
        self.assertEqual(roster[0], ["16_Whitney.png"])
        state = {"roster": roster}
        with mock.patch("boss_logic._generate_level3_boss_roster") as regenerate:
            self.assertEqual(_ensure_level3_roster(state, 3), roster)
            regenerate.assert_not_called()
        self.assertIn("16_Whitney.png", get_bosses_for_boss_level(1))

    def test_category_and_only_configured_effects(self):
        self.assertEqual(BOSS_LEVELS["16_Whitney.png"], 1)
        self.assertEqual(load_boss_rewards()[16], {
            "Reward": "Disclosure5Rounds",
            "Functionalities": "NoFirstTurnTrading",
        })
        page = SimpleNamespace()
        apply_boss_functionality("NoFirstTurnTrading", page)
        self.assertEqual(vars(page), {"boss_no_first_turn_trading": True})

    def test_all_buy_and_sell_arrows_blocked_only_on_first_turn(self):
        page = GameplayPage.__new__(GameplayPage)
        page.Day = 1
        page.Money = 100
        page.Aquantity = page.Bquantity = page.Cquantity = 5
        page.Aprice = page.BPrice = page.CPrice = 10
        page._check_win_lose = mock.Mock()
        page._reset_continuation_growth_streak = mock.Mock()
        apply_boss_functionality("NoFirstTurnTrading", page)
        for market in range(3):
            for arrow in range(4):
                self.assertTrue(page._is_arrow_disabled(market, arrow))
                self.assertFalse(page._apply_arrow_trade(market, arrow))
        self.assertEqual((page.Money, page.Aquantity, page.Bquantity, page.Cquantity),
                         (100, 5, 5, 5))
        for day in (2, 3, 4):
            page.Day = day
            for market in range(3):
                for arrow in range(4):
                    self.assertFalse(page._is_arrow_disabled(market, arrow))
        page.Day = 2
        self.assertTrue(page._apply_arrow_trade(0, 1))
        self.assertEqual((page.Money, page.Aquantity), (90, 6))

    def test_reward_survives_winning_round_then_expires_after_five_rounds(self):
        page = mock.MagicMock()
        page.level_number = 5
        page.is_final_boss = False
        page.win_lose_image = None
        page.finance_report_image = None
        page._get_pending_victory_napoleondor_reward.return_value = 0
        page._apply_nabob_win_bonus.return_value = 0
        page._count_active_card_safely.return_value = 0
        page._add_reward_card_to_deck.side_effect = lambda: apply_boss_reward(
            load_boss_rewards()[16]["Reward"], page
        )
        with (
            mock.patch.object(game_state, "disclosure_rounds_remaining", 0),
            mock.patch.object(game_state, "active_gold_cards", []),
            mock.patch.object(game_state, "ensure_napoleondor_level"),
            mock.patch.object(game_state, "consume_finance_report_income", return_value=[]),
            mock.patch.object(game_state, "apply_bank_interest", return_value=0),
            mock.patch.object(game_state, "advance_bailout_round"),
        ):
            GameplayPage._finish_win_lose_result(page, "win", "last_turn")
            self.assertEqual(game_state.get_disclosure_rounds_remaining(), 5)
            self.assertEqual(profile_manager._capture_progress()["disclosure_rounds_remaining"], 5)
            page._add_reward_card_to_deck.side_effect = None
            for remaining in (4, 3, 2, 1, 0):
                self.assertTrue(game_state.is_disclosure_active())
                GameplayPage._finish_win_lose_result(page, "win", "last_turn")
                self.assertEqual(game_state.get_disclosure_rounds_remaining(), remaining)
            self.assertFalse(game_state.is_disclosure_active())

    def test_reward_refreshes_existing_visibility_without_shortening_it(self):
        for existing, expected in ((0, 5), (2, 5), (5, 5), (7, 7)):
            with self.subTest(existing=existing), mock.patch.object(
                game_state, "disclosure_rounds_remaining", existing
            ):
                apply_boss_reward("Disclosure5Rounds", SimpleNamespace())
                self.assertEqual(game_state.get_disclosure_rounds_remaining(), expected)


if __name__ == "__main__":
    unittest.main()
