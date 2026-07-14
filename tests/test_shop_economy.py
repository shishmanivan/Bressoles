import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager
from shop_page import ShopPage


SHOP_STATE_FIELDS = (
    "level_1_boss_defeated",
    "level_2_boss_defeated",
    "level_3_boss_defeated",
    "level_4_boss_defeated",
    "global_hand_bonus",
    "napoleondors",
    "napoleondor_level",
    "shop_deck_cards",
    "removed_deck_cards_by_level",
    "investment_card_bonuses",
    "profit_reward_bonus",
    "updown_probability_bonus",
    "pending_shop_discount_percent",
    "bailout_rounds_remaining",
    "active_long_investments",
    "derivative_bought",
    "issuer_bought_count",
    "bank_bought",
    "bank_interest_base",
    "licensed_card_ids",
    "silver_cards",
    "gold_cards",
    "active_gold_cards",
    "bear_goal_reduction_steps",
)


class ShopEconomyTestCase(unittest.TestCase):
    def setUp(self):
        self._snapshot = {
            field: copy.deepcopy(getattr(game_state, field))
            for field in SHOP_STATE_FIELDS
        }
        game_state.napoleondors = 0
        game_state.napoleondor_level = 5
        game_state.level_4_boss_defeated = False
        game_state.shop_deck_cards = []
        game_state.removed_deck_cards_by_level = {}
        game_state.investment_card_bonuses = {}
        game_state.profit_reward_bonus = 0
        game_state.updown_probability_bonus = 0
        game_state.pending_shop_discount_percent = 0
        game_state.bailout_rounds_remaining = 0
        game_state.active_long_investments = []
        game_state.derivative_bought = False
        game_state.issuer_bought_count = 0
        game_state.bank_bought = False
        game_state.bank_interest_base = None
        game_state.licensed_card_ids = set(game_state.DEFAULT_LICENSED_CARDS)
        game_state.silver_cards = []
        game_state.gold_cards = []
        game_state.active_gold_cards = []
        game_state.bear_goal_reduction_steps = 0

    def tearDown(self):
        for field, value in self._snapshot.items():
            setattr(game_state, field, value)

    @staticmethod
    def _shop(offer):
        page = ShopPage.__new__(ShopPage)
        page.offers = [offer]
        page.sold_offer_indexes = set()
        page.level_number = 5
        page.napoleondors = float(game_state.napoleondors)
        page.message = ""
        return page


class ShopTransactionTests(ShopEconomyTestCase):
    def test_investments_are_a_separate_section_unlocked_by_level4_completion(self):
        game_state.level_4_boss_defeated = False
        locked_offers = game_state.generate_shop_offers(5, card_slots=0, special_slots=0, license_slots=0)
        self.assertFalse(any(offer["kind"] == "investment" for offer in locked_offers))

        game_state.level_4_boss_defeated = True
        level4_offers = game_state.generate_shop_offers(4, card_slots=0, special_slots=0, license_slots=0)
        level5_offers = game_state.generate_shop_offers(5, card_slots=0, special_slots=0, license_slots=0)

        self.assertFalse(any(offer["kind"] == "investment" for offer in level4_offers))
        self.assertEqual(level5_offers, [{"kind": "investment", "cost": 3}])

    def test_investor_is_not_a_random_special_offer_anymore(self):
        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers = game_state.build_shop_special_offer_pool(5)

        self.assertNotIn("investment", offers)

    def test_investment_section_upgrades_one_card_and_returns_to_shop(self):
        game_state.napoleondors = 6
        game_state.shop_deck_cards = [15]
        page = self._shop({"kind": "investment", "cost": 3})
        page.screen = object()
        page.font_path = "font.ttf"

        with mock.patch("shop_page.InvestmentDeckPage") as deck_page:
            deck_page.return_value.run.return_value = 15
            page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 3)
        self.assertEqual(game_state.get_investment_bonus(15), 1)
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(page.message, "Карта усилена")

        page._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 3)
        self.assertEqual(game_state.get_investment_bonus(15), 1)

    def test_card_offer_category_is_available_from_level3(self):
        for level in (1, 2):
            with self.subTest(level=level):
                offers = game_state.generate_shop_offers(level, special_slots=0, license_slots=0)
                self.assertEqual([offer for offer in offers if offer["kind"] == "card"], [])

        for level in (3, 4, 5):
            with self.subTest(level=level):
                available = game_state.build_all_available_shop_cards(level)
                offers = game_state.generate_shop_offers(level, special_slots=0, license_slots=0)
                card_offers = [offer for offer in offers if offer["kind"] == "card"]
                self.assertEqual(len(card_offers), 1)
                self.assertIn(card_offers[0]["card_id"], available)

    def test_insufficient_funds_do_not_mutate_card_or_license_state(self):
        game_state.napoleondors = 6
        card_shop = self._shop({"kind": "card", "card_id": 117, "cost": 7})

        card_shop._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertEqual(card_shop.sold_offer_indexes, set())

        license_shop = self._shop({"kind": "license", "card_id": 121, "cost": 12})
        license_shop._buy_offer(0)
        self.assertFalse(game_state.is_card_licensed(121))
        self.assertEqual(game_state.napoleondors, 6)

    def test_free_shop_purchase_applies_effect_without_spending_balance(self):
        game_state.napoleondors = 5
        page = self._shop({"kind": "card", "card_id": 117, "cost": 0})

        page._buy_offer(0)

        self.assertEqual(game_state.shop_deck_cards, [117])
        self.assertEqual(game_state.napoleondors, 5)
        self.assertEqual(page.sold_offer_indexes, {0})

    def test_discount_is_applied_to_every_offer_kind(self):
        offers = game_state.generate_shop_offers(
            5,
            card_slots=1,
            special_slots=2,
            license_slots=1,
            discount_percent=100,
        )

        self.assertTrue(offers)
        self.assertTrue(all(offer["cost"] == 0 for offer in offers))

    def test_card_offer_is_randomly_selected_from_successful_rolls(self):
        with (
            mock.patch.object(
                game_state,
                "build_shop_card_offer_pool",
                return_value=[17, 401, 406],
            ),
            mock.patch.object(game_state.random, "sample", return_value=[401]) as select,
        ):
            offers = game_state.generate_shop_offers(
                5,
                card_slots=1,
                special_slots=0,
                license_slots=0,
            )

        self.assertEqual(offers, [{"kind": "card", "card_id": 401, "cost": 15}])
        select.assert_called_once_with([17, 401, 406], 1)

    def test_empty_rolled_pool_selects_from_every_available_shop_card(self):
        fallback = [17, 18, 117, 401, 402, 403, 404, 405, 406]
        with (
            mock.patch.object(game_state, "build_shop_card_offer_pool", return_value=[]),
            mock.patch.object(
                game_state,
                "build_all_available_shop_cards",
                return_value=fallback,
            ),
            mock.patch.object(game_state.random, "sample", return_value=[405]) as select,
        ):
            offers = game_state.generate_shop_offers(
                5,
                card_slots=1,
                special_slots=0,
                license_slots=0,
            )

        self.assertEqual(offers, [{"kind": "card", "card_id": 405, "cost": 15}])
        select.assert_called_once_with(fallback, 1)

    def test_underwriter_does_not_charge_without_two_inventory_slots(self):
        game_state.napoleondors = 10
        game_state.silver_cards = [201] * (game_state.MAX_SILVER_CARDS - 1)
        page = self._shop({"kind": "special", "special_id": "underwriter", "cost": 4})

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 10)
        self.assertEqual(len(game_state.silver_cards), game_state.MAX_SILVER_CARDS - 1)
        self.assertEqual(page.sold_offer_indexes, set())


class TimedShopEffectTests(ShopEconomyTestCase):
    def test_bailout_discounts_exactly_five_won_rounds(self):
        self.assertEqual(game_state.buy_bailout(), 5)
        self.assertEqual(game_state.apply_bailout_goal_modifier(100), 80)

        for expected_remaining in (4, 3, 2, 1, 0):
            self.assertEqual(game_state.advance_bailout_round(), expected_remaining)

        self.assertEqual(game_state.apply_bailout_goal_modifier(100), 100)

    def test_long_pays_after_four_wins_and_allows_two_investments(self):
        game_state.napoleondors = 4
        self.assertTrue(game_state.buy_long_investment())
        self.assertTrue(game_state.buy_long_investment())
        self.assertFalse(game_state.buy_long_investment())

        for _ in range(3):
            self.assertEqual(game_state.advance_long_investments(5), 0)
        self.assertEqual(game_state.advance_long_investments(5), 12)
        self.assertEqual(game_state.napoleondors, 16)
        self.assertEqual(game_state.get_active_long_investments(), [])

    def test_bank_uses_balance_left_after_previous_shop(self):
        game_state.napoleondors = 10
        self.assertTrue(game_state.buy_bank_offer())
        self.assertEqual(game_state.update_bank_interest_base(), 10)

        self.assertTrue(game_state.spend_napoleondors(4))
        self.assertEqual(game_state.apply_bank_interest(5), 2.5)
        self.assertEqual(game_state.napoleondors, 8.5)


class ShopPersistenceTests(ShopEconomyTestCase):
    def test_trader_sells_only_one_copy_and_supports_half_coins(self):
        game_state.napoleondors = 0

        first_value, first_cards = game_state.sell_cards_from_level_deck(4, [1])
        second_value, second_cards = game_state.sell_cards_from_level_deck(4, [1])
        third_value, third_cards = game_state.sell_cards_from_level_deck(4, [1])

        self.assertEqual((first_value, first_cards), (0.5, [1]))
        self.assertEqual((second_value, second_cards), (0.5, [1]))
        self.assertEqual((third_value, third_cards), (0.0, []))
        self.assertEqual(game_state.napoleondors, 1.0)

    def test_shop_economy_round_trip_preserves_run_and_license_state(self):
        game_state.napoleondors = 9.5
        game_state.shop_deck_cards = [117]
        game_state.removed_deck_cards_by_level = {4: [1]}
        game_state.investment_card_bonuses = {11: 2}
        game_state.profit_reward_bonus = 2
        game_state.updown_probability_bonus = 4
        game_state.pending_shop_discount_percent = 50
        game_state.bailout_rounds_remaining = 3
        game_state.active_long_investments = [2, 4]
        game_state.derivative_bought = True
        game_state.global_hand_bonus = 1
        game_state.issuer_bought_count = 1
        game_state.bank_bought = True
        game_state.bank_interest_base = 7.5
        game_state.licensed_card_ids.add(121)
        game_state.gold_cards = [401]
        game_state.bear_goal_reduction_steps = 2
        progress = profile_manager._capture_progress()

        game_state.napoleondors = 0
        game_state.shop_deck_cards = []
        game_state.removed_deck_cards_by_level = {}
        game_state.investment_card_bonuses = {}
        game_state.profit_reward_bonus = 0
        game_state.updown_probability_bonus = 0
        game_state.pending_shop_discount_percent = 0
        game_state.bailout_rounds_remaining = 0
        game_state.active_long_investments = []
        game_state.derivative_bought = False
        game_state.global_hand_bonus = 0
        game_state.issuer_bought_count = 0
        game_state.bank_bought = False
        game_state.bank_interest_base = None
        game_state.licensed_card_ids = set(game_state.DEFAULT_LICENSED_CARDS)
        game_state.gold_cards = []
        game_state.bear_goal_reduction_steps = 0

        profile_manager.apply_profile_to_game_state({"progress": progress})

        self.assertEqual(game_state.napoleondors, 9.5)
        self.assertEqual(game_state.shop_deck_cards, [117])
        self.assertEqual(game_state.removed_deck_cards_by_level, {4: [1]})
        self.assertEqual(game_state.investment_card_bonuses, {11: 2})
        self.assertEqual(game_state.profit_reward_bonus, 2)
        self.assertEqual(game_state.get_updown_probability_bonus(), 4)
        self.assertEqual(game_state.pending_shop_discount_percent, 50)
        self.assertEqual(game_state.get_bailout_rounds_remaining(), 3)
        self.assertEqual(game_state.get_active_long_investments(), [2, 4])
        self.assertTrue(game_state.derivative_bought)
        self.assertEqual(game_state.global_hand_bonus, 1)
        self.assertEqual(game_state.get_issuer_bought_count(), 1)
        self.assertTrue(game_state.bank_bought)
        self.assertEqual(game_state.bank_interest_base, 7.5)
        self.assertTrue(game_state.is_card_licensed(121))
        self.assertEqual(game_state.gold_cards, [401])
        self.assertEqual(game_state.bear_goal_reduction_steps, 2)

    def test_attempt_reset_clears_shop_upgrades_but_keeps_licenses(self):
        game_state.napoleondors = 30
        game_state.shop_deck_cards = [117]
        game_state.removed_deck_cards_by_level = {4: [1]}
        game_state.investment_card_bonuses = {11: 2}
        game_state.profit_reward_bonus = 3
        game_state.pending_shop_discount_percent = 50
        game_state.bailout_rounds_remaining = 4
        game_state.active_long_investments = [2]
        game_state.derivative_bought = True
        game_state.global_hand_bonus = 1
        game_state.issuer_bought_count = 2
        game_state.bank_bought = True
        game_state.bank_interest_base = 20
        game_state.licensed_card_ids.add(121)
        game_state.gold_cards = [401]
        game_state.bear_goal_reduction_steps = 3

        game_state.reset_level_attempt(4)

        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertEqual(game_state.removed_deck_cards_by_level, {})
        self.assertEqual(game_state.investment_card_bonuses, {})
        self.assertEqual(game_state.profit_reward_bonus, 0)
        self.assertEqual(game_state.pending_shop_discount_percent, 0)
        self.assertEqual(game_state.get_bailout_rounds_remaining(), 0)
        self.assertEqual(game_state.get_active_long_investments(), [])
        self.assertFalse(game_state.derivative_bought)
        self.assertEqual(game_state.global_hand_bonus, 0)
        self.assertEqual(game_state.get_issuer_bought_count(), 0)
        self.assertFalse(game_state.bank_bought)
        self.assertIsNone(game_state.bank_interest_base)
        self.assertEqual(game_state.gold_cards, [])
        self.assertEqual(game_state.bear_goal_reduction_steps, 0)
        self.assertTrue(game_state.is_card_licensed(121))


if __name__ == "__main__":
    unittest.main()
