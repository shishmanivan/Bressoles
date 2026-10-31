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
    def test_available_from_level_three_and_in_later_boss_pools(self):
        self.assertNotIn("16_Whitney.png", [boss for step in LEVEL_BOSS_ROUNDS[1] for boss in step])
        self.assertEqual(LEVEL_BOSS_ROUNDS[2], [
            ["2_AdamSmith.png", "3_RobertFulton.png"],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
        ])
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
            "Reward": "DisclosureUntilRunEnd",
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

    def test_reward_survives_winning_round_and_has_no_round_limit(self):
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
            mock.patch.object(game_state, "whitney_disclosure_active", False),
            mock.patch.object(game_state, "active_gold_cards", []),
            mock.patch.object(game_state, "ensure_napoleondor_level"),
            mock.patch.object(game_state, "consume_finance_report_income", return_value=[]),
            mock.patch.object(game_state, "apply_bank_interest", return_value=0),
            mock.patch.object(game_state, "advance_bailout_round"),
        ):
            GameplayPage._finish_win_lose_result(page, "win", "last_turn")
            self.assertTrue(game_state.whitney_disclosure_active)
            self.assertTrue(profile_manager._capture_progress()["whitney_disclosure_active"])
            page._add_reward_card_to_deck.side_effect = None
            for _ in range(20):
                self.assertTrue(game_state.is_disclosure_active())
                GameplayPage._finish_win_lose_result(page, "win", "last_turn")
                self.assertTrue(game_state.whitney_disclosure_active)
            self.assertTrue(game_state.is_disclosure_active())
            self.assertFalse(game_state.is_disclosure_offer_available())
            game_state.clear_disclosure()
            self.assertFalse(game_state.is_disclosure_active())

    def test_disclosure_offers_and_gold_card_excluded_only_after_reward(self):
        config = {427: {"Type": 5, "Open": 1, "Variable": "100"}}
        pools = (
            game_state.build_gold_cards_pool,
            game_state.build_open_gold_cards_pool,
            game_state.build_golden_stocks_reward_pool,
            game_state.build_multibagger_gold_fallback_pool,
            game_state.build_shop_card_offer_pool,
            game_state.build_all_available_shop_cards,
        )
        with (
            mock.patch.object(game_state, "whitney_disclosure_active", False),
            mock.patch.object(game_state, "disclosure_rounds_remaining", 0),
            mock.patch.object(game_state, "active_gold_cards", []),
            mock.patch.object(game_state, "load_cards_config", return_value=config),
            mock.patch.object(game_state, "get_bought_shop_card_ids", return_value=set()),
            mock.patch.object(game_state, "get_active_moratoriums", return_value=[]),
        ):
            self.assertTrue(game_state.is_disclosure_offer_available())
            for pool in pools:
                self.assertIn(427, pool(5), pool.__name__)
            apply_boss_reward("DisclosureUntilRunEnd", SimpleNamespace())
            self.assertFalse(game_state.is_disclosure_offer_available())
            self.assertEqual(game_state.buy_disclosure(), 0)
            for pool in pools:
                self.assertNotIn(427, pool(5), pool.__name__)
            self.assertFalse(game_state.is_gold_card_available_for_level("427"))
            game_state.clear_disclosure()
            self.assertTrue(game_state.is_disclosure_offer_available())
            for pool in pools:
                self.assertIn(427, pool(5), pool.__name__)

    def test_reward_profile_round_trip_and_old_save_default(self):
        original = profile_manager._default_profile(1)
        original["progress"] = profile_manager._capture_progress()
        try:
            apply_boss_reward("DisclosureUntilRunEnd", SimpleNamespace())
            profile = profile_manager._default_profile(1)
            profile["progress"] = profile_manager._capture_progress()
            game_state.whitney_disclosure_active = False
            profile_manager.apply_profile_to_game_state(profile)
            self.assertTrue(game_state.whitney_disclosure_active)
            del profile["progress"]["whitney_disclosure_active"]
            profile_manager.apply_profile_to_game_state(profile)
            self.assertFalse(game_state.whitney_disclosure_active)
            for finish in (game_state.reset_level_attempt, game_state.complete_level_run):
                apply_boss_reward("DisclosureUntilRunEnd", SimpleNamespace())
                finish(5)
                self.assertFalse(game_state.whitney_disclosure_active)
        finally:
            profile_manager.apply_profile_to_game_state(original)

    def test_reward_refreshes_existing_visibility_without_shortening_it(self):
        for existing, expected in ((0, 5), (2, 5), (5, 5), (7, 7)):
            with self.subTest(existing=existing), mock.patch.object(
                game_state, "disclosure_rounds_remaining", existing
            ):
                apply_boss_reward("Disclosure5Rounds", SimpleNamespace())
                self.assertEqual(game_state.get_disclosure_rounds_remaining(), expected)


if __name__ == "__main__":
    unittest.main()
