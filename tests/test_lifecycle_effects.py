import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import gameplay_page
from gameplay_page import GameplayPage
from shop_page import CARD_DESCRIPTIONS
from silver_black_page import CARD_TOOLTIPS


class LifecycleEffectTests(unittest.TestCase):
    def setUp(self):
        self.original_state = {
            "bear_goal_reduction_steps": game_state.bear_goal_reduction_steps,
            "insurance_goal_debt": game_state.insurance_goal_debt,
            "napoleondors": game_state.napoleondors,
            "napoleondor_level": game_state.napoleondor_level,
            "pending_shop_discount_percent": game_state.pending_shop_discount_percent,
        }
        game_state.bear_goal_reduction_steps = 0
        game_state.insurance_goal_debt = 0
        game_state.napoleondors = 0
        game_state.napoleondor_level = 1
        game_state.pending_shop_discount_percent = 0

    def tearDown(self):
        for name, value in self.original_state.items():
            setattr(game_state, name, value)

    @staticmethod
    def _page(silver=None, black=None, gold=None):
        page = GameplayPage.__new__(GameplayPage)
        page.active_silver_cards = list(silver or [])
        page.active_black_cards = list(black or [])
        page.active_gold_cards = list(gold or [])
        page.active_lifecycle_card_order = []
        page.profile_slot = None
        page.test_mode = True
        page.level_number = 1
        return page

    def test_futures_cards_add_their_declared_turns(self):
        page = self._page(silver=[202, 203], black=[301])
        page.LastTurn = 8

        page._apply_silver_last_turn_bonuses()

        self.assertEqual(page.LastTurn, 12)

    def test_grant_synergy_upgrades_each_silver_grant(self):
        page = self._page(silver=[214, 214], gold=[403])
        page.Money = 0

        page._apply_grant_start_money_bonus()

        self.assertEqual(page.Money, 24)

    def test_contango_and_rollover_stack_with_multiple_copies(self):
        page = self._page(silver=[204, 204, 208, 208])
        page.card_actions = {11: 2, 15: -2}
        page.card_turns = {11: 1, 15: 1}

        page._apply_contango_gain_drop_bonuses()
        page._apply_silver_rollover_bonus()

        self.assertEqual(page.card_actions, {11: 8, 15: -8})
        self.assertEqual(page.card_turns, {11: 3, 15: 3})

    def test_silver_rollover_doubles_a_fresh_red_rollover(self):
        page = self._page(silver=[208])
        page.side_cards_top = [112, None, None, None, None, None]
        page.side_cards_locked_top = {0: False}
        page.card_turns = {11: 1}
        page.market_cards = {0: {0: 11}, 1: {}, 2: {}}
        page.market_card_turns = {0: {0: 1}, 1: {}, 2: {}}
        page.side_card_jump_animations = {}

        self.assertTrue(page._apply_extended_gain_drop_effect_if_needed())

        self.assertEqual(page.card_turns[11], 3)
        self.assertEqual(page.market_card_turns[0][0], 3)

    def test_basket_trading_uses_the_documented_stack_values(self):
        page = self._page(silver=[206, 206])
        page.stock_price_turn_results = [
            {"market": 0, "type": "rise"},
            {"market": 1, "type": "rise"},
            {"market": 2, "type": "rise"},
        ]
        page.Aprice = page.BPrice = page.CPrice = 10
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_basket_trading_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (16, 16, 16))

    def test_forward_trading_synergy_awards_four_turns_per_pair(self):
        page = self._page(silver=[207], gold=[402])
        page.side_cards_top = [100, 100, None, None, None, None]
        page.side_cards_locked_top = {0: False, 1: False}
        page.forward_trading_shareholder_count = 0
        page.LastTurn = 8

        self.assertTrue(page._apply_forward_trading_effect_if_needed())

        self.assertEqual(page.LastTurn, 12)
        self.assertEqual(page.forward_trading_shareholder_count, 0)

    def test_insurance_carries_only_a_regular_round_shortfall(self):
        page = self._page(silver=[220])
        page.Goal = 100
        page.Money = 65
        page.is_boss_fight = False

        self.assertEqual(page._apply_insurance_if_needed("lose", "last_turn"), ("win", "insurance"))
        self.assertEqual(game_state.get_insurance_goal_debt(), 35)

        game_state.insurance_goal_debt = 0
        page.is_boss_fight = True
        self.assertEqual(page._apply_insurance_if_needed("lose", "last_turn"), ("lose", "last_turn"))
        self.assertEqual(game_state.get_insurance_goal_debt(), 0)

    def test_victory_rewards_and_bill_effects_stack(self):
        page = self._page(silver=[215, 217, 218, 219])

        page._apply_bill_of_exchange_shop_discount()
        page._apply_obligation_win_bonus()

        self.assertEqual(game_state.pending_shop_discount_percent, 50)
        self.assertEqual(game_state.napoleondors, 30)

    def test_bear_flat_insider_and_gambling_contracts(self):
        page = self._page(gold=[401, 404, 405, 406])
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertEqual(game_state.get_bear_goal_discount_percent([401]), 2)
        self.assertTrue(game_state.record_bear_victory([401]))
        self.assertEqual(game_state.get_bear_goal_discount_percent([401]), 4)
        self.assertTrue(page._is_flat_random_active())
        self.assertEqual(page._get_gambling_probability_bonus(), gameplay_page.GAMBLING_PROBABILITY_BONUS)
        self.assertTrue(page._consume_insider_c_growth_turn())
        self.assertEqual(page.insider_c_growth_turns_remaining, 1)

    def test_synergies_stay_hidden_in_player_facing_descriptions(self):
        self.assertNotIn("красную Rollover", CARD_TOOLTIPS[208][1])
        self.assertNotIn("серебряной", CARD_TOOLTIPS[402][1])
        self.assertNotIn("серебряную", CARD_TOOLTIPS[403][1])
        self.assertNotIn("серебряной", CARD_DESCRIPTIONS[402])
        self.assertNotIn("серебряную", CARD_DESCRIPTIONS[403])


if __name__ == "__main__":
    unittest.main()
