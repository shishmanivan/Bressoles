import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import localization
from gameplay_page import GameplayPage
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES
from silver_black_page import CARD_TOOLTIPS


class CashYieldTests(unittest.TestCase):
    def page(self, money=100, gold=(437,)):
        page = GameplayPage.__new__(GameplayPage)
        page.active_gold_cards = list(gold)
        page.Money = money
        page.Day = 1
        page.win_lose_state = None
        page.Aquantity = 1000
        page.Aprice = 1000
        return page

    def test_interest_uses_cash_only_and_rounds_down(self):
        for money, expected in [(100, 20), (19, 3), (5, 1), (4, 0), (0, 0), (-5, 0)]:
            with self.subTest(money=money):
                page = self.page(money)
                self.assertEqual(page._apply_cash_yield_turn_bonus(), expected)
                self.assertEqual(page.Money, money + expected)

    def test_once_per_turn_and_compounds_on_following_turn(self):
        page = self.page()
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 20)
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 0)
        page.Day += 1
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 24)
        self.assertEqual(page.Money, 144)

    def test_duplicates_add_rates_on_the_same_cash_balance(self):
        page = self.page(gold=(437, 437))
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 40)
        self.assertEqual(page.Money, 140)

    def test_no_interest_without_card_or_after_round_ends(self):
        page = self.page(gold=())
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 0)
        page = self.page()
        page.win_lose_state = "win"
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 0)

    def test_restored_day_guard_prevents_interest_on_rebate_proceeds(self):
        page = self.page(money=500)
        page.cash_yield_last_applied_day = 1
        self.assertEqual(page._apply_cash_yield_turn_bonus(), 0)
        self.assertEqual(page.Money, 500)

    def test_interest_is_available_to_end_turn_win_check(self):
        page = self.page()
        checked_balances = []
        page._check_win_lose = lambda: checked_balances.append(page.Money)
        # Stop the flow where a final Rebate animation would normally take over.
        page._is_final_auto_liquidation_animating = lambda: True
        page._finish_turn_after_astor_cash_burn()
        page._finish_turn_after_astor_cash_burn()
        self.assertEqual(checked_balances, [120, 120])

    def test_catalog_price_level_chance_and_translations(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[437], 5)
        self.assertEqual(CARD_NAMES[437], "Cash Yield")
        cards = {437: game_state.load_cards_config()[437]}
        self.assertEqual(cards[437], {"Type": 5, "Open": 1, "Variable": "15"})
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=15) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(5), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(6), [437])
            with mock.patch.object(game_state.random, "randint", return_value=16):
                self.assertEqual(game_state.build_gold_cards_pool(6), [])
            self.assertNotIn(437, game_state.build_all_available_shop_cards(5))
            self.assertIn(437, game_state.build_all_available_shop_cards(6))
        description = CARD_DESCRIPTIONS[437]
        self.assertEqual(CARD_TOOLTIPS[437], ("Cash Yield", description))
        for language in localization.SUPPORTED_LANGUAGES:
            catalog, _, _ = localization._catalog(language)
            self.assertRegex(catalog[description], r"20\s*%")
            if language != "RU":
                self.assertNotEqual(catalog[description], description)
