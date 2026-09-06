import copy
import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import profile_manager
from round_page import RoundPage
from shop_page import CARD_DESCRIPTIONS, CARD_NAMES, LICENSE_EFFECT_DESCRIPTIONS, ShopPage


SHOP_STATE_FIELDS = (
    "level_1_boss_defeated",
    "level_2_boss_defeated",
    "level_3_boss_defeated",
    "level_4_boss_defeated",
    "boss_progress",
    "global_hand_bonus",
    "napoleondors",
    "napoleondor_level",
    "shop_deck_cards",
    "removed_deck_cards_by_level",
    "investment_card_bonuses",
    "profit_reward_bonus",
    "updown_probability_bonus",
    "variance_offer_bought_count",
    "pending_shop_discount_percent",
    "correction_shop_cooldown",
    "bailout_rounds_remaining",
    "disclosure_rounds_remaining",
    "active_long_investments",
    "derivative_bought",
    "issuer_bought_count",
    "boss_shop_offer_bonus",
    "boss_rare_card_pool_bonus_percent",
    "deal_flow_bonus_percent",
    "bank_bought",
    "bank_interest_base",
    "multibagger_bought",
    "diversification_bought",
    "expansion_bought",
    "bill_of_exchange_offer_bought",
    "compounding_bought",
    "capital_preservation_bought",
    "mirroring_bought_count",
    "mirrored_deck_cards",
    "retention_active",
    "retention_pending_level",
    "retention_pending_cards",
    "loan_boss_positions_by_level",
    "insurance_goal_debt",
    "Frugality",
    "licensed_card_ids",
    "silver_cards",
    "black_cards",
    "active_black_cards",
    "gold_cards",
    "active_gold_cards",
    "active_lifecycle_card_order",
    "bear_goal_reduction_steps",
    "windfall_boss_victories",
    "risk_premium_h_rounds",
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
        game_state.boss_progress = {5: game_state.new_boss_progress_state()}
        game_state.shop_deck_cards = []
        game_state.removed_deck_cards_by_level = {}
        game_state.investment_card_bonuses = {}
        game_state.profit_reward_bonus = 0
        game_state.updown_probability_bonus = 0
        game_state.variance_offer_bought_count = 0
        game_state.pending_shop_discount_percent = 0
        game_state.correction_shop_cooldown = 0
        game_state.bailout_rounds_remaining = 0
        game_state.disclosure_rounds_remaining = 0
        game_state.active_long_investments = []
        game_state.derivative_bought = False
        game_state.issuer_bought_count = 0
        game_state.boss_shop_offer_bonus = 0
        game_state.boss_rare_card_pool_bonus_percent = 0
        game_state.deal_flow_bonus_percent = 0
        game_state.bank_bought = False
        game_state.bank_interest_base = None
        game_state.multibagger_bought = False
        game_state.diversification_bought = False
        game_state.expansion_bought = False
        game_state.bill_of_exchange_offer_bought = False
        game_state.compounding_bought = False
        game_state.capital_preservation_bought = False
        game_state.mirroring_bought_count = 0
        game_state.mirrored_deck_cards = []
        game_state.retention_active = False
        game_state.retention_pending_level = None
        game_state.retention_pending_cards = []
        game_state.loan_boss_positions_by_level = {}
        game_state.insurance_goal_debt = 0
        game_state.Frugality = 0
        game_state.licensed_card_ids = set(game_state.DEFAULT_LICENSED_CARDS)
        game_state.silver_cards = []
        game_state.black_cards = []
        game_state.active_black_cards = []
        game_state.gold_cards = []
        game_state.active_gold_cards = []
        game_state.active_lifecycle_card_order = []
        game_state.bear_goal_reduction_steps = 0
        game_state.windfall_boss_victories = 0
        game_state.risk_premium_h_rounds = 0

    def tearDown(self):
        for field, value in self._snapshot.items():
            setattr(game_state, field, value)

    @staticmethod
    def _shop(offer):
        page = ShopPage.__new__(ShopPage)
        page.offers = [offer]
        page.sold_offer_indexes = set()
        page.screen = None
        page.font_path = None
        page.level_number = 5
        page.napoleondors = float(game_state.napoleondors)
        page.message = ""
        page.discount_percent = 0
        return page


class ShopTransactionTests(ShopEconomyTestCase):
    def test_active_shop_offer_effects_include_timers_and_persistent_upgrades(self):
        game_state.bailout_rounds_remaining = 3
        game_state.disclosure_rounds_remaining = 2
        game_state.active_long_investments = [4, 1]
        game_state.loan_boss_positions_by_level = {5: [2]}
        game_state.retention_active = True
        game_state.profit_reward_bonus = 1
        game_state.derivative_bought = True
        game_state.issuer_bought_count = 1
        game_state.bank_bought = True
        game_state.updown_probability_bonus = 1
        game_state.variance_offer_bought_count = 1
        game_state.diversification_bought = True
        game_state.expansion_bought = True
        game_state.bill_of_exchange_offer_bought = True
        game_state.compounding_bought = True
        game_state.capital_preservation_bought = True
        game_state.deal_flow_bonus_percent = 10

        entries = game_state.get_active_shop_offer_effects(5, defeated_count=2)
        timed = [
            (entry["special_id"], entry["remaining"], entry.get("remaining_kind"))
            for entry in entries
            if entry["remaining"] is not None
        ]

        self.assertEqual(
            timed,
            [
                ("bailout", 3, "rounds"),
                ("disclosure", 2, "rounds"),
                ("long", 4, "rounds"),
                ("long", 1, "rounds"),
                ("loan", 1, "bosses"),
                ("retention", 1, "bosses"),
            ],
        )
        self.assertTrue(
            {
                "profit",
                "derivative",
                "issuer",
                "bank",
                "variance",
                "diversification",
                "expansion",
                "bill_of_exchange",
                "compounding",
                "capital_preservation",
                "deal_flow",
            }.issubset({entry["special_id"] for entry in entries})
        )
        self.assertNotIn(
            "loan",
            {
                entry["special_id"]
                for entry in game_state.get_active_shop_offer_effects(5, defeated_count=3)
            },
        )

    def test_issuer_first_slot_costs_eight_and_second_still_costs_fifteen(self):
        self.assertEqual(game_state.get_shop_special_cost("issuer", 3), 8)

        game_state.issuer_bought_count = 1
        self.assertEqual(game_state.get_shop_special_cost("issuer", 3), 15)

    def test_deal_flow_costs_four_and_stacks_by_ten_points(self):
        game_state.napoleondors = 10
        first_shop = self._shop(
            {"kind": "special", "special_id": "deal_flow", "cost": 4}
        )

        first_shop._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(game_state.get_deal_flow_bonus(), 10)
        self.assertEqual(
            first_shop.message,
            "Шанс редких карт и предложений увеличен на 10%",
        )

        second_shop = self._shop(
            {"kind": "special", "special_id": "deal_flow", "cost": 4}
        )
        second_shop._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 2)
        self.assertEqual(game_state.get_deal_flow_bonus(), 20)

    def test_deal_flow_has_twenty_one_percent_pool_chance(self):
        with mock.patch.object(game_state.random, "randint", return_value=21):
            self.assertNotIn(
                "deal_flow",
                game_state.build_shop_special_offer_pool(3, max_offers=30),
            )
            offers = game_state.build_shop_special_offer_pool(4, max_offers=30)
        self.assertIn("deal_flow", offers)

        game_state.deal_flow_bonus_percent = 10
        with mock.patch.object(game_state.random, "randint", return_value=22):
            missed_offers = game_state.build_shop_special_offer_pool(4, max_offers=30)
        self.assertNotIn("deal_flow", missed_offers)

    def test_deal_flow_starts_at_level_four_in_regular_and_screening_pools(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                self.assertFalse(game_state.is_deal_flow_offer_available(level))
                self.assertNotIn(
                    "deal_flow",
                    game_state._available_screening_offer_ids(level),
                )

        self.assertTrue(game_state.is_deal_flow_offer_available(4))
        self.assertIn("deal_flow", game_state._available_screening_offer_ids(4))

    def test_deal_flow_boosts_only_offers_at_or_below_twenty_percent(self):
        game_state.deal_flow_bonus_percent = 10

        self.assertEqual(game_state.get_shop_special_offer_chance(20), 30)
        self.assertEqual(game_state.get_shop_special_offer_chance(21), 21)
        self.assertEqual(game_state.get_shop_special_offer_chance(5), 15)

    def test_deal_flow_boosts_rare_gold_cards_and_stacks_with_astor(self):
        game_state.deal_flow_bonus_percent = 10
        game_state.boss_rare_card_pool_bonus_percent = 10
        cards = {
            401: {"Type": 5, "Open": 1, "Variable": 20},
            402: {"Type": 5, "Open": 1, "Variable": 21},
            201: {"Type": 3, "Open": 1, "Variable": 20},
        }
        game_state.licensed_card_ids.add(201)

        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state.random, "randint", return_value=40),
        ):
            self.assertEqual(game_state.build_gold_cards_pool(5), [401])
            self.assertEqual(game_state.build_silver_cards_pool(5), [])

    def test_disclosure_costs_three_and_returns_after_five_rounds(self):
        game_state.napoleondors = 10
        page = self._shop(
            {"kind": "special", "special_id": "disclosure", "cost": 3}
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 7)
        self.assertEqual(game_state.get_disclosure_rounds_remaining(), 5)
        self.assertTrue(game_state.is_disclosure_active())
        self.assertFalse(game_state.is_disclosure_offer_available())
        self.assertEqual(page.message, "Вероятности открыты на 5 раундов")

        for expected_remaining in (4, 3, 2, 1):
            self.assertEqual(
                game_state.advance_disclosure_round(),
                expected_remaining,
            )
            self.assertFalse(game_state.is_disclosure_offer_available())

        self.assertEqual(game_state.advance_disclosure_round(), 0)
        self.assertTrue(game_state.is_disclosure_offer_available())

    def test_disclosure_has_thirty_five_percent_pool_roll(self):
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_correction_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 100, 100, 35, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(2, max_offers=2)

        self.assertIn("disclosure", offers)
        self.assertEqual(game_state.get_shop_special_cost("disclosure", 2), 3)

    def test_expansion_costs_five_and_combines_with_peabody_bonus(self):
        game_state.napoleondors = 10
        page = self._shop(
            {"kind": "special", "special_id": "expansion", "cost": 5}
        )

        self.assertEqual(game_state.get_shop_special_offer_slots(), 2)
        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 5)
        self.assertTrue(game_state.expansion_bought)
        self.assertEqual(game_state.get_shop_special_offer_slots(), 3)
        self.assertEqual(page.message, "В магазине теперь больше предложений")

        self.assertEqual(game_state.add_boss_shop_offer_bonus(), 4)
        self.assertEqual(game_state.get_shop_special_offer_slots(), 4)
        self.assertEqual(game_state.add_boss_shop_offer_bonus(), 4)
        self.assertEqual(game_state.boss_shop_offer_bonus, 1)

        repeated_offer = self._shop(
            {"kind": "special", "special_id": "expansion", "cost": 5}
        )
        repeated_offer._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 5)
        self.assertEqual(repeated_offer.message, "Экспансия уже куплена")

    def test_expansion_has_twenty_percent_pool_roll_and_then_disappears(self):
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_correction_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                return_value=20,
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(4, max_offers=30)

        self.assertIn("expansion", offers)
        self.assertEqual(game_state.get_shop_special_cost("expansion", 4), 5)
        self.assertFalse(game_state.is_expansion_offer_available(3))
        self.assertTrue(game_state.is_expansion_offer_available(4))
        self.assertNotIn("expansion", game_state._available_screening_offer_ids(3))
        self.assertIn("expansion", game_state._available_screening_offer_ids(4))

        game_state.expansion_bought = True
        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers_after_purchase = game_state.build_shop_special_offer_pool(4, max_offers=20)
        self.assertNotIn("expansion", offers_after_purchase)

    def test_bill_of_exchange_costs_four_and_is_bought_only_once(self):
        game_state.napoleondors = 10
        page = self._shop(
            {"kind": "special", "special_id": "bill_of_exchange", "cost": 4}
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 6)
        self.assertTrue(game_state.bill_of_exchange_offer_bought)
        self.assertFalse(game_state.is_bill_of_exchange_offer_available())
        self.assertEqual(page.message, "Цены снижены на 25%")

        repeated = self._shop(
            {"kind": "special", "special_id": "bill_of_exchange", "cost": 4}
        )
        repeated._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(repeated.message, "Вексель уже куплен")

    def test_bill_of_exchange_immediately_reprices_current_shop(self):
        game_state.napoleondors = 10
        game_state.level_4_boss_defeated = True
        page = self._shop(
            {"kind": "special", "special_id": "bill_of_exchange", "cost": 4}
        )
        page.offers.extend(
            [
                {"kind": "card", "card_id": 117, "cost": 7},
                {"kind": "special", "special_id": "profit", "cost": 6},
                {
                    "kind": "license",
                    "card_id": 121,
                    "cost": game_state.get_license_cost(121),
                },
                {"kind": "investment", "cost": game_state.INVESTMENT_SECTION_COST},
            ]
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(
            [offer["cost"] for offer in page.offers[1:]],
            [
                game_state.get_discounted_shop_price(game_state.SHOP_CARD_COSTS[117]),
                game_state.get_discounted_shop_price(
                    game_state.get_shop_special_cost("profit", 5)
                ),
                game_state.get_discounted_shop_price(game_state.get_license_cost(121)),
                game_state.get_discounted_shop_price(game_state.INVESTMENT_SECTION_COST),
            ],
        )

    def test_bill_of_exchange_immediately_stacks_with_current_shop_discount(self):
        game_state.napoleondors = 5
        page = self._shop(
            {"kind": "special", "special_id": "bill_of_exchange", "cost": 2}
        )
        page.discount_percent = 50
        page.offers.append(
            {"kind": "special", "special_id": "profit", "cost": 3}
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 3)
        self.assertEqual(page.offers[1]["cost"], 1.5)

    def test_bill_of_exchange_discounts_every_future_shop_section_and_rounds_to_half(self):
        game_state.bill_of_exchange_offer_bought = True
        game_state.level_4_boss_defeated = True
        with (
            mock.patch.object(game_state, "build_shop_card_offer_pool", return_value=[117]),
            mock.patch.object(game_state, "build_shop_special_offer_pool", return_value=["profit"]),
            mock.patch.object(game_state, "build_license_offer_pool", return_value=[121]),
        ):
            offers = game_state.generate_shop_offers(
                5,
                card_slots=1,
                special_slots=1,
                license_slots=1,
            )

        expected_base_costs = {
            "card": game_state.SHOP_CARD_COSTS[117],
            "special": game_state.SHOP_SPECIAL_COSTS["profit"],
            "license": game_state.get_license_cost(121),
            "investment": game_state.INVESTMENT_SECTION_COST,
        }
        self.assertEqual({offer["kind"] for offer in offers}, set(expected_base_costs))
        for offer in offers:
            expected = game_state.round_shop_price_to_step(
                expected_base_costs[offer["kind"]] * 0.75
            )
            self.assertEqual(offer["cost"], expected)
            self.assertEqual((offer["cost"] * 2) % 1, 0)

    def test_next_shop_discount_stacks_with_bill_of_exchange(self):
        game_state.bill_of_exchange_offer_bought = True

        self.assertEqual(game_state.get_effective_shop_discount_percent(50), 75)
        self.assertEqual(game_state.get_effective_shop_discount_percent(100), 100)
        self.assertEqual(game_state.round_shop_price_to_step(4 * 0.25), 1.0)

        with mock.patch.object(
            game_state,
            "build_shop_special_offer_pool",
            return_value=["profit"],
        ):
            offers = game_state.generate_shop_offers(
                3,
                card_slots=0,
                special_slots=1,
                license_slots=0,
                discount_percent=50,
            )
        self.assertEqual(offers[0]["cost"], 1.5)

    def test_bill_of_exchange_has_eighteen_percent_pool_roll_then_disappears(self):
        with mock.patch.object(game_state.random, "randint", return_value=18):
            self.assertNotIn(
                "bill_of_exchange",
                game_state.build_shop_special_offer_pool(2, max_offers=30),
            )
            offers = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertIn("bill_of_exchange", offers)
        self.assertEqual(game_state.get_shop_special_cost("bill_of_exchange", 3), 4)
        self.assertNotIn(
            "bill_of_exchange",
            game_state._available_screening_offer_ids(2),
        )
        self.assertIn(
            "bill_of_exchange",
            game_state._available_screening_offer_ids(3),
        )

        with mock.patch.object(game_state.random, "randint", return_value=19):
            missed_offers = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertNotIn("bill_of_exchange", missed_offers)

        game_state.bill_of_exchange_offer_bought = True
        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers_after_purchase = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertNotIn("bill_of_exchange", offers_after_purchase)

    def test_diversification_costs_five_and_is_bought_only_once(self):
        game_state.napoleondors = 10
        page = self._shop(
            {"kind": "special", "special_id": "diversification", "cost": 5}
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 5)
        self.assertTrue(game_state.diversification_bought)
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(page.message, "В магазине теперь предлагаются две карты")
        self.assertFalse(game_state.is_diversification_offer_available())

        repeated_offer = self._shop(
            {"kind": "special", "special_id": "diversification", "cost": 5}
        )
        repeated_offer._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 5)
        self.assertEqual(repeated_offer.message, "Диверсификация уже куплена")

    def test_diversification_increases_only_default_card_slots_to_two(self):
        card_pool = [401, 402, 403]
        with (
            mock.patch.object(game_state, "build_shop_card_offer_pool", return_value=card_pool),
            mock.patch.object(
                game_state.random,
                "sample",
                side_effect=lambda population, count: list(population)[:count],
            ),
        ):
            before = game_state.generate_shop_offers(
                3,
                special_slots=0,
                license_slots=0,
            )
            game_state.diversification_bought = True
            after = game_state.generate_shop_offers(
                3,
                special_slots=0,
                license_slots=0,
            )
            explicit_one = game_state.generate_shop_offers(
                3,
                card_slots=1,
                special_slots=0,
                license_slots=0,
            )

        self.assertEqual(len([offer for offer in before if offer["kind"] == "card"]), 1)
        self.assertEqual(len([offer for offer in after if offer["kind"] == "card"]), 2)
        self.assertEqual(len([offer for offer in explicit_one if offer["kind"] == "card"]), 1)

    def test_expanded_diversified_shop_layout_keeps_eight_offers_inside_panel(self):
        page = ShopPage.__new__(ShopPage)
        page.panel_rect = mock.Mock(left=120, right=1560, centerx=840, y=75)
        page.offer_image_box = (200, 296)
        page.offers = [
            {"kind": "card", "card_id": 401},
            {"kind": "card", "card_id": 402},
            {"kind": "special", "special_id": "diversification"},
            {"kind": "special", "special_id": "bank"},
            {"kind": "special", "special_id": "multibagger"},
            {"kind": "special", "special_id": "expansion"},
            {"kind": "license", "card_id": 121},
            {"kind": "investment"},
        ]

        rects = page._build_offer_rects()

        self.assertGreaterEqual(min(rect.left for rect in rects), page.panel_rect.left)
        self.assertLessEqual(max(rect.right for rect in rects), page.panel_rect.right)
        self.assertEqual(page.offer_image_box, (136, 296))

    def test_diversification_has_thirty_percent_pool_roll_and_then_disappears(self):
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 100, 100, 30, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(3, max_offers=2)

        self.assertIn("diversification", offers)
        self.assertEqual(game_state.get_shop_special_cost("diversification", 3), 5)

        game_state.diversification_bought = True
        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers_after_purchase = game_state.build_shop_special_offer_pool(3, max_offers=20)
        self.assertNotIn("diversification", offers_after_purchase)

    def test_correction_sells_silver_for_two_after_its_two_coin_cost(self):
        game_state.napoleondors = 5
        game_state.silver_cards = [201, 203]
        game_state.black_cards = [301]
        game_state.gold_cards = [401]
        page = self._shop({"kind": "special", "special_id": "correction", "cost": 2})

        with mock.patch("shop_page.CorrectionDeckPage") as correction_page:
            correction_page.return_value.run.return_value = [("silver", 201)]
            page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 5)
        self.assertEqual(game_state.silver_cards, [203])
        self.assertEqual(game_state.black_cards, [301])
        self.assertEqual(game_state.gold_cards, [401])
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(page.message, "Продано карт: 1 на сумму 2")

    def test_correction_sells_three_cards_for_one_offer_price(self):
        game_state.napoleondors = 2
        game_state.silver_cards = [201, 203]
        game_state.black_cards = [301]
        game_state.active_black_cards = [301]
        game_state.gold_cards = [401, 402]
        game_state.active_gold_cards = [401]
        game_state.active_lifecycle_card_order = [
            {"kind": "black", "card_id": 301},
            {"kind": "gold", "card_id": 401},
        ]
        page = self._shop({"kind": "special", "special_id": "correction", "cost": 2})

        with mock.patch("shop_page.CorrectionDeckPage") as correction_page:
            correction_page.return_value.run.return_value = [
                ("silver", 201),
                ("silver", 203),
                ("gold", 401),
            ]
            page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 8)
        self.assertEqual(game_state.silver_cards, [])
        self.assertEqual(game_state.gold_cards, [402])
        self.assertEqual(game_state.active_gold_cards, [])
        self.assertEqual(game_state.black_cards, [301])
        self.assertEqual(game_state.active_black_cards, [301])
        self.assertEqual(
            game_state.active_lifecycle_card_order,
            [{"kind": "black", "card_id": 301}],
        )
        self.assertEqual(page.message, "Продано карт: 3 на сумму 8")

    def test_correction_never_sells_black_cards(self):
        game_state.black_cards = [301]

        self.assertIsNone(game_state.sell_correction_card(5, "black", 301))
        self.assertEqual(game_state.black_cards, [301])
        self.assertFalse(game_state.is_correction_offer_available())

    def test_correction_rejects_more_than_three_cards_without_partial_sale(self):
        game_state.silver_cards = [201, 202]
        game_state.gold_cards = [401, 402]

        total_value, sold_cards = game_state.sell_correction_cards(
            5,
            [
                ("silver", 201),
                ("silver", 202),
                ("gold", 401),
                ("gold", 402),
            ],
        )

        self.assertEqual((total_value, sold_cards), (0, []))
        self.assertEqual(game_state.silver_cards, [201, 202])
        self.assertEqual(game_state.gold_cards, [401, 402])

    def test_correction_has_twenty_five_percent_pool_roll_and_costs_two(self):
        game_state.silver_cards = [201]
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(game_state, "is_replication_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 100, 100, 25, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(2)

        self.assertIn("correction", offers)
        self.assertEqual(game_state.get_shop_special_cost("correction", 2), 2)

    def test_successful_correction_roll_survives_the_two_offer_limit(self):
        game_state.silver_cards = [201]
        with (
            mock.patch.object(game_state.random, "randint", return_value=1),
            mock.patch.object(
                game_state.random,
                "sample",
                side_effect=lambda population, count: population[-count:],
            ) as sample,
        ):
            offers = game_state.build_shop_special_offer_pool(5, max_offers=2)

        sampled_pool, sampled_count = sample.call_args.args
        self.assertNotIn("correction", sampled_pool)
        self.assertEqual(sampled_count, 1)
        self.assertEqual(offers[0], "correction")
        self.assertEqual(len(offers), 2)

    def test_correction_skips_the_next_two_shops_after_being_offered(self):
        game_state.silver_cards = [201]
        with (
            mock.patch.object(game_state, "build_shop_card_offer_pool", return_value=[]),
            mock.patch.object(game_state, "build_all_available_shop_cards", return_value=[]),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state.random, "randint", return_value=1),
            mock.patch.object(
                game_state.random,
                "sample",
                side_effect=lambda population, count: list(population)[:count],
            ),
        ):
            shops = [
                game_state.generate_shop_offers(5, card_slots=0, license_slots=0)
                for _ in range(4)
            ]

        correction_presence = [
            any(
                offer.get("kind") == "special"
                and offer.get("special_id") == "correction"
                for offer in offers
            )
            for offers in shops
        ]
        self.assertEqual(correction_presence, [True, False, False, True])
        self.assertEqual(
            game_state.get_correction_shop_cooldown(),
            game_state.CORRECTION_SHOP_COOLDOWN,
        )

    def test_correction_shop_cooldown_is_saved(self):
        game_state.correction_shop_cooldown = 2

        progress = profile_manager._capture_progress()
        game_state.correction_shop_cooldown = 0
        profile_manager.apply_profile_to_game_state({"progress": progress})

        self.assertEqual(progress["correction_shop_cooldown"], 2)
        self.assertEqual(game_state.get_correction_shop_cooldown(), 2)

    def test_replication_requires_an_owned_silver_card_and_a_free_slot(self):
        self.assertFalse(game_state.is_replication_offer_available())

        game_state.silver_cards = [201]
        self.assertTrue(game_state.is_replication_offer_available())

        game_state.silver_cards = [201] * game_state.MAX_SILVER_CARDS
        self.assertFalse(game_state.is_replication_offer_available())

    def test_replication_duplicates_selected_silver_card_for_two(self):
        game_state.napoleondors = 6
        game_state.silver_cards = [201, 203]
        page = self._shop(
            {"kind": "special", "special_id": "replication", "cost": 2}
        )

        with mock.patch("shop_page.ReplicationSilverPage") as replication_page:
            replication_page.return_value.run.return_value = 203
            page._buy_offer(0)

        self.assertEqual(game_state.silver_cards, [201, 203, 203])
        self.assertEqual(game_state.napoleondors, 4)
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(page.message, "Серебряная карта добавлена")

    def test_replication_cancel_does_not_spend_or_add_a_card(self):
        game_state.napoleondors = 6
        game_state.silver_cards = [201]
        page = self._shop(
            {"kind": "special", "special_id": "replication", "cost": 2}
        )

        with mock.patch("shop_page.ReplicationSilverPage") as replication_page:
            replication_page.return_value.run.return_value = None
            page._buy_offer(0)

        self.assertEqual(game_state.silver_cards, [201])
        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(page.sold_offer_indexes, set())

    def test_replication_has_twenty_percent_pool_roll_and_costs_two(self):
        game_state.silver_cards = [201]
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bailout_active", return_value=True),
            mock.patch.object(game_state, "is_long_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_correction_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(game_state, "is_compounding_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 20, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(2, max_offers=20)

        self.assertIn("replication", offers)
        self.assertEqual(game_state.get_shop_special_cost("replication", 2), 2)

    def test_replication_plus_requires_owned_gold_and_free_storage_slot(self):
        self.assertFalse(game_state.is_replication_plus_offer_available())

        game_state.gold_cards = [401]
        self.assertTrue(game_state.is_replication_plus_offer_available())

        game_state.gold_cards = [401] * game_state.MAX_GOLD_CARDS
        self.assertFalse(game_state.is_replication_plus_offer_available())

    def test_replication_plus_duplicates_selected_gold_card_for_six(self):
        game_state.napoleondors = 10
        game_state.gold_cards = [401, 405]
        page = self._shop(
            {"kind": "special", "special_id": "replication_plus", "cost": 6}
        )

        with mock.patch("shop_page.ReplicationGoldPage") as replication_page:
            replication_page.return_value.run.return_value = 405
            page._buy_offer(0)

        self.assertEqual(game_state.gold_cards, [401, 405, 405])
        self.assertEqual(game_state.napoleondors, 4)
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(page.message, "Золотая карта добавлена")

    def test_replication_plus_cancel_does_not_spend_or_duplicate(self):
        game_state.napoleondors = 10
        game_state.gold_cards = [401]
        page = self._shop(
            {"kind": "special", "special_id": "replication_plus", "cost": 6}
        )

        with mock.patch("shop_page.ReplicationGoldPage") as replication_page:
            replication_page.return_value.run.return_value = None
            page._buy_offer(0)

        self.assertEqual(game_state.gold_cards, [401])
        self.assertEqual(game_state.napoleondors, 10)
        self.assertEqual(page.sold_offer_indexes, set())

    def test_replication_plus_has_two_percent_pool_roll_and_costs_six(self):
        game_state.gold_cards = [401]
        with mock.patch.object(game_state.random, "randint", return_value=2):
            offers = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertIn("replication_plus", offers)

        with mock.patch.object(game_state.random, "randint", return_value=3):
            offers = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertNotIn("replication_plus", offers)
        self.assertEqual(game_state.get_shop_special_cost("replication_plus", 3), 6)

    def test_mirroring_duplicates_selected_current_deck_card_for_four(self):
        game_state.napoleondors = 10
        game_state.round_reward_cards = {5: [112]}
        page = self._shop(
            {"kind": "special", "special_id": "mirroring", "cost": 4}
        )

        with mock.patch("shop_page.MirroringDeckPage") as mirroring_page:
            mirroring_page.return_value.run.return_value = 112
            page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(game_state.mirrored_deck_cards, [112])
        self.assertEqual(game_state.get_mirroring_bought_count(), 1)
        self.assertEqual(game_state.build_current_level_deck(5).count(112), 2)
        self.assertEqual(page.sold_offer_indexes, {0})

    def test_mirroring_is_limited_to_two_purchases_with_25_then_10_percent_chance(self):
        self.assertEqual(game_state.get_mirroring_shop_chance(), 25)
        self.assertTrue(game_state.is_mirroring_offer_available(5))
        self.assertIsNotNone(game_state.buy_mirroring_card(5, 1))
        self.assertEqual(game_state.get_mirroring_shop_chance(), 10)
        self.assertTrue(game_state.is_mirroring_offer_available(5))
        self.assertIsNotNone(game_state.buy_mirroring_card(5, 1))
        self.assertFalse(game_state.is_mirroring_offer_available(5))
        self.assertIsNone(game_state.buy_mirroring_card(5, 1))
        self.assertEqual(game_state.mirrored_deck_cards, [1, 1])
        self.assertEqual(game_state.get_shop_special_cost("mirroring", 5), 4)

    def test_mirroring_pool_roll_uses_purchase_dependent_chance(self):
        with mock.patch.object(game_state.random, "randint", return_value=25):
            first_pool = game_state.build_shop_special_offer_pool(5, max_offers=30)
        self.assertIn("mirroring", first_pool)

        game_state.mirroring_bought_count = 1
        with mock.patch.object(game_state.random, "randint", return_value=11):
            missed_pool = game_state.build_shop_special_offer_pool(5, max_offers=30)
        self.assertNotIn("mirroring", missed_pool)

        with mock.patch.object(game_state.random, "randint", return_value=10):
            second_pool = game_state.build_shop_special_offer_pool(5, max_offers=30)
        self.assertIn("mirroring", second_pool)

    def test_retention_costs_three_and_stays_unavailable_until_boss_victory(self):
        game_state.napoleondors = 8
        page = self._shop(
            {"kind": "special", "special_id": "retention", "cost": 3}
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 5)
        self.assertTrue(game_state.retention_active)
        self.assertFalse(game_state.is_retention_offer_available())
        self.assertEqual(page.message, "Удержание активно до победы над боссом")

    def test_retention_has_twenty_percent_pool_roll(self):
        with mock.patch.object(game_state.random, "randint", return_value=20):
            offers = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertIn("retention", offers)

        with mock.patch.object(game_state.random, "randint", return_value=21):
            offers = game_state.build_shop_special_offer_pool(3, max_offers=30)
        self.assertNotIn("retention", offers)
        self.assertEqual(game_state.get_shop_special_cost("retention", 3), 3)

    def test_retention_is_unavailable_before_the_final_boss(self):
        self.assertTrue(
            game_state.is_retention_offer_available(
                defeated_count=1,
                bosses_required=3,
            )
        )
        self.assertFalse(
            game_state.is_retention_offer_available(
                defeated_count=2,
                bosses_required=3,
            )
        )

        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers = game_state.build_shop_special_offer_pool(
                4,
                max_offers=30,
                defeated_count=2,
                bosses_required=3,
            )
        self.assertNotIn("retention", offers)

    def test_screening_excludes_retention_before_the_final_boss(self):
        choices = game_state._available_screening_offer_ids(
            4,
            defeated_count=2,
            bosses_required=3,
        )

        self.assertNotIn("retention", choices)

    def test_stale_final_boss_retention_cannot_be_bought(self):
        game_state.napoleondors = 8
        page = self._shop(
            {"kind": "special", "special_id": "retention", "cost": 3}
        )
        page.defeated_count = 2
        page.bosses_required = 3

        page._buy_offer(0)

        self.assertFalse(game_state.retention_active)
        self.assertEqual(game_state.napoleondors, 8)
        self.assertEqual(page.message, "Удержание недоступно")

    def test_loan_is_free_pays_five_and_is_limited_per_boss_and_run(self):
        first_shop = self._shop({"kind": "special", "special_id": "loan", "cost": 0})

        first_shop._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 5)
        self.assertEqual(game_state.loan_boss_positions_by_level, {5: [0]})
        self.assertEqual(first_shop.sold_offer_indexes, {0})
        self.assertEqual(first_shop.message, "Получено 5 наполеондоров")
        self.assertFalse(game_state.is_loan_offer_available(5))

        game_state.boss_progress[5]["defeated"] = 1
        second_shop = self._shop({"kind": "special", "special_id": "loan", "cost": 0})
        second_shop._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 10)
        self.assertEqual(game_state.loan_boss_positions_by_level, {5: [0, 1]})
        self.assertFalse(game_state.is_loan_offer_available(5))

        game_state.boss_progress[5]["defeated"] = 2
        self.assertFalse(game_state.is_loan_offer_available(5))
        self.assertFalse(game_state.buy_loan(5))
        self.assertEqual(game_state.napoleondors, 10)

    def test_loan_raises_only_its_boss_goals_by_fifty_percent(self):
        game_state.loan_boss_positions_by_level = {5: [1]}

        self.assertEqual(game_state.apply_loan_goal_modifier(100, 5, 1), 120)
        self.assertEqual(game_state.apply_loan_goal_modifier(100, 5, 0), 100)
        self.assertEqual(game_state.apply_loan_goal_modifier(100, 4, 1), 100)

        round_page = RoundPage.__new__(RoundPage)
        round_page.level_number = 5
        round_page.defeated_count = 1
        round_page.base_button_goals = {"e": 100}
        self.assertEqual(round_page._build_display_button_goals(), {"e": 120})

    def test_loan_successful_roll_gets_a_shop_slot_and_costs_zero(self):
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 100, 100, 1, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(2)

        self.assertIn("loan", offers)
        self.assertEqual(game_state.get_shop_special_cost("loan", 2), 0)

    def test_variance_costs_one_and_stacks_upside_downside_bonus(self):
        game_state.napoleondors = 8
        game_state.updown_probability_bonus = 2
        page = self._shop({"kind": "special", "special_id": "variance", "cost": 1})

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 7)
        self.assertEqual(game_state.get_updown_probability_bonus(), 3)
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(page.message, "Все карты усилены на 1%")

        second_shop = self._shop({"kind": "special", "special_id": "variance", "cost": 1})
        second_shop._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 6)
        self.assertEqual(game_state.get_updown_probability_bonus(), 4)
        self.assertEqual(game_state.variance_offer_bought_count, 2)

    def test_variance_successful_roll_enters_the_random_selection_pool(self):
        with (
            mock.patch.object(game_state.random, "randint", return_value=1),
            mock.patch.object(
                game_state.random,
                "sample",
                side_effect=lambda population, count: (
                    ["variance"] + [offer for offer in population if offer != "variance"]
                )[:count],
            ) as sample,
        ):
            offers = game_state.build_shop_special_offer_pool(3)

        self.assertIn("variance", sample.call_args.args[0])
        self.assertIn("variance", offers)
        self.assertEqual(game_state.get_shop_special_cost("variance", 3), 1)

    def test_screening_costs_one_and_has_ten_percent_pool_roll(self):
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bailout_active", return_value=True),
            mock.patch.object(game_state, "is_long_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_correction_offer_available", return_value=False),
            mock.patch.object(game_state, "is_diversification_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(game_state, "is_compounding_offer_available", return_value=False),
            mock.patch.object(game_state, "is_replication_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=True),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 10, 100, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(4, max_offers=20)

        self.assertIn("screening", offers)
        self.assertEqual(game_state.get_shop_special_cost("screening", 4), 1)

    def test_screening_offer_starts_at_level_four(self):
        with mock.patch.object(
            game_state,
            "_available_screening_offer_ids",
            return_value=["trader", "profit", "junk_bond", "variance", "bailout"],
        ):
            self.assertFalse(game_state.is_screening_offer_available(3))
            self.assertTrue(game_state.is_screening_offer_available(4))

        with mock.patch.object(game_state.random, "randint", return_value=1):
            self.assertNotIn(
                "screening",
                game_state.build_shop_special_offer_pool(3, max_offers=30),
            )

    def test_screening_builds_five_unique_choices_and_excludes_itself(self):
        available = [
            "trader",
            "profit",
            "junk_bond",
            "variance",
            "bailout",
            "screening",
        ]
        with (
            mock.patch.object(
                game_state,
                "_available_screening_offer_ids",
                return_value=available,
            ),
            mock.patch.object(
                game_state,
                "build_shop_special_offer_pool",
                return_value=[
                    "screening",
                    "variance",
                    "trader",
                    "profit",
                    "junk_bond",
                    "bailout",
                ],
            ),
        ):
            choices = game_state.build_screening_offer_pool(3)

        self.assertEqual(
            choices,
            ["variance", "trader", "profit", "junk_bond", "bailout"],
        )
        self.assertEqual(len(choices), len(set(choices)))
        self.assertNotIn("screening", choices)

    def test_screening_applies_one_selected_offer_for_free(self):
        game_state.napoleondors = 4
        game_state.updown_probability_bonus = 0
        page = self._shop(
            {"kind": "special", "special_id": "screening", "cost": 1}
        )
        choices = ["trader", "profit", "junk_bond", "variance", "bailout"]

        with (
            mock.patch.object(
                game_state,
                "build_screening_offer_pool",
                return_value=choices,
            ),
            mock.patch("shop_page.ScreeningOfferPage") as screening_page,
        ):
            screening_page.return_value.run.return_value = "variance"
            page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 3)
        self.assertEqual(game_state.get_updown_probability_bonus(), 1)
        self.assertEqual(page.sold_offer_indexes, {0})
        self.assertEqual(screening_page.call_args.args[3], choices)

    def test_screening_cancel_does_not_spend_or_consume_the_offer(self):
        game_state.napoleondors = 4
        page = self._shop(
            {"kind": "special", "special_id": "screening", "cost": 1}
        )

        with (
            mock.patch.object(
                game_state,
                "build_screening_offer_pool",
                return_value=["trader", "profit", "junk_bond", "variance", "bailout"],
            ),
            mock.patch("shop_page.ScreeningOfferPage") as screening_page,
        ):
            screening_page.return_value.run.return_value = None
            page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 4)
        self.assertEqual(page.sold_offer_indexes, set())

    def test_capital_preservation_costs_five_and_is_bought_once_per_attempt(self):
        game_state.napoleondors = 12
        page = self._shop(
            {
                "kind": "special",
                "special_id": "capital_preservation",
                "cost": 5,
            }
        )

        page._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 7)
        self.assertTrue(game_state.capital_preservation_bought)
        self.assertFalse(game_state.is_capital_preservation_offer_available())
        self.assertEqual(page.message, "Золотые карты защищены")

        repeated = self._shop(
            {
                "kind": "special",
                "special_id": "capital_preservation",
                "cost": 5,
            }
        )
        repeated._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 7)

    def test_capital_preservation_has_five_percent_pool_roll(self):
        with (
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bailout_active", return_value=True),
            mock.patch.object(game_state, "is_long_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_correction_offer_available", return_value=False),
            mock.patch.object(game_state, "is_diversification_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(game_state, "is_compounding_offer_available", return_value=False),
            mock.patch.object(game_state, "is_replication_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 5, 100, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(4, max_offers=20)

        self.assertIn("capital_preservation", offers)
        self.assertEqual(
            game_state.get_shop_special_cost("capital_preservation", 4),
            5,
        )
        self.assertFalse(game_state.is_capital_preservation_offer_available(3))
        self.assertTrue(game_state.is_capital_preservation_offer_available(4))
        self.assertNotIn(
            "capital_preservation",
            game_state._available_screening_offer_ids(3),
        )
        self.assertIn(
            "capital_preservation",
            game_state._available_screening_offer_ids(4),
        )

    def test_bank_offer_costs_three_napoleondors(self):
        self.assertEqual(game_state.get_shop_special_cost("bank", 3), 3)

    def test_multibagger_shop_chance_is_70_only_on_level3(self):
        self.assertEqual(game_state.get_multibagger_shop_chance(3), 70)
        for level in (1, 2, 4, 5):
            with self.subTest(level=level):
                self.assertEqual(game_state.get_multibagger_shop_chance(level), 10)

    def test_multibagger_cost_is_3_on_level3_and_5_elsewhere(self):
        self.assertEqual(game_state.get_multibagger_shop_cost(3), 3)
        for level in (1, 2, 4, 5):
            with self.subTest(level=level):
                self.assertEqual(game_state.get_multibagger_shop_cost(level), 5)

        with mock.patch.object(game_state, "build_shop_special_offer_pool", return_value=["multibagger"]):
            discounted_offer = game_state.generate_shop_offers(
                3,
                card_slots=0,
                special_slots=1,
                license_slots=0,
                discount_percent=50,
            )
        self.assertEqual(discounted_offer, [{"kind": "special", "special_id": "multibagger", "cost": 1.5}])

    def test_multibagger_starts_at_level_three_in_regular_and_screening_pools(self):
        with mock.patch.object(
            game_state,
            "build_multibagger_gold_fallback_pool",
            return_value=[401],
        ):
            for level in (1, 2):
                with self.subTest(level=level):
                    self.assertFalse(game_state.is_multibagger_offer_available(level))
                    self.assertNotIn(
                        "multibagger",
                        game_state._available_screening_offer_ids(level),
                    )

            self.assertTrue(game_state.is_multibagger_offer_available(3))
            self.assertIn("multibagger", game_state._available_screening_offer_ids(3))

        with mock.patch.object(game_state.random, "randint", return_value=1):
            self.assertNotIn(
                "multibagger",
                game_state.build_shop_special_offer_pool(2, max_offers=30),
            )

    def test_special_offer_selection_samples_the_complete_rolled_pool(self):
        with (
            mock.patch.object(game_state.random, "randint", return_value=1),
            mock.patch.object(
                game_state.random,
                "sample",
                side_effect=lambda population, count: population[-count:],
            ) as sample,
        ):
            offers = game_state.build_shop_special_offer_pool(3)

        sampled_pool, sampled_count = sample.call_args.args
        self.assertIn("multibagger", sampled_pool)
        self.assertIn("delisting", sampled_pool)
        self.assertEqual(sampled_count, 2)
        self.assertEqual(offers, sampled_pool[-2:])

        game_state.multibagger_bought = True
        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers_after_purchase = game_state.build_shop_special_offer_pool(3)
        self.assertNotIn("multibagger", offers_after_purchase)

    def test_multibagger_uses_probability_pool_and_is_bought_only_once(self):
        game_state.napoleondors = 20
        page = self._shop({"kind": "special", "special_id": "multibagger", "cost": 5})

        with (
            mock.patch.object(game_state, "build_gold_cards_pool", return_value=[401, 405]),
            mock.patch.object(game_state.random, "choice", return_value=405),
        ):
            page._buy_offer(0)

        self.assertEqual(game_state.gold_cards, [405])
        self.assertTrue(game_state.multibagger_bought)
        self.assertEqual(game_state.napoleondors, 15)
        self.assertEqual(page.message, "Карта добавлена")
        self.assertFalse(game_state.is_multibagger_offer_available())

    def test_multibagger_falls_back_to_all_open_unowned_gold_cards(self):
        game_state.gold_cards = [401]
        with (
            mock.patch.object(game_state, "build_gold_cards_pool", return_value=[]),
            mock.patch.object(game_state, "build_open_gold_cards_pool", return_value=[401, 402, 403]),
            mock.patch.object(game_state.random, "choice", return_value=403),
        ):
            awarded = game_state.buy_multibagger_gold_card()

        self.assertEqual(awarded, 403)
        self.assertEqual(game_state.gold_cards, [401, 403])

    def test_investments_are_a_separate_section_unlocked_by_level4_completion(self):
        game_state.level_4_boss_defeated = False
        locked_offers = game_state.generate_shop_offers(5, card_slots=0, special_slots=0, license_slots=0)
        self.assertFalse(any(offer["kind"] == "investment" for offer in locked_offers))

        game_state.level_4_boss_defeated = True
        level4_offers = game_state.generate_shop_offers(4, card_slots=0, special_slots=0, license_slots=0)
        level5_offers = game_state.generate_shop_offers(5, card_slots=0, special_slots=0, license_slots=0)

        self.assertFalse(any(offer["kind"] == "investment" for offer in level4_offers))
        self.assertEqual(level5_offers, [{"kind": "investment", "cost": 3}])

    def test_compounding_is_locked_with_investments_and_has_ten_percent_roll(self):
        game_state.level_4_boss_defeated = False
        with mock.patch.object(game_state.random, "randint", return_value=1):
            locked_offers = game_state.build_shop_special_offer_pool(5, max_offers=20)
        self.assertNotIn("compounding", locked_offers)

        game_state.level_4_boss_defeated = True
        with (
            mock.patch.object(game_state, "is_capital_preservation_offer_available", return_value=False),
            mock.patch.object(game_state, "is_mirroring_offer_available", return_value=False),
            mock.patch.object(game_state, "is_retention_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bill_of_exchange_offer_available", return_value=False),
            mock.patch.object(game_state, "is_screening_offer_available", return_value=False),
            mock.patch.object(game_state, "is_underwriter_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bailout_active", return_value=True),
            mock.patch.object(game_state, "is_long_offer_available", return_value=False),
            mock.patch.object(game_state, "is_issuer_offer_available", return_value=False),
            mock.patch.object(game_state, "is_bank_offer_available", return_value=False),
            mock.patch.object(game_state, "is_derivative_offer_available", return_value=False),
            mock.patch.object(game_state, "is_multibagger_offer_available", return_value=False),
            mock.patch.object(game_state, "is_loan_offer_available", return_value=False),
            mock.patch.object(game_state, "is_correction_offer_available", return_value=False),
            mock.patch.object(game_state, "is_diversification_offer_available", return_value=False),
            mock.patch.object(game_state, "is_expansion_offer_available", return_value=False),
            mock.patch.object(game_state, "is_disclosure_offer_available", return_value=False),
            mock.patch.object(
                game_state.random,
                "randint",
                side_effect=[100, 100, 100, 100, 10, 100, 100],
            ),
        ):
            offers = game_state.build_shop_special_offer_pool(5, max_offers=20)

        self.assertIn("compounding", offers)
        self.assertEqual(game_state.get_shop_special_cost("compounding", 5), 7)

    def test_compounding_makes_future_investments_add_two_and_is_one_time(self):
        game_state.level_4_boss_defeated = True
        game_state.napoleondors = 13
        game_state.shop_deck_cards = [15]
        compounding = self._shop(
            {"kind": "special", "special_id": "compounding", "cost": 7}
        )

        compounding._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 6)
        self.assertTrue(game_state.compounding_bought)
        self.assertFalse(game_state.is_compounding_offer_available(5))
        self.assertEqual(compounding.message, "Инвестиции теперь усиливают карты на 2")

        investment = self._shop({"kind": "investment", "cost": 3})
        investment.screen = object()
        investment.font_path = "font.ttf"
        with mock.patch("shop_page.InvestmentDeckPage") as deck_page:
            deck_page.return_value.run.return_value = 15
            investment._buy_offer(0)

        self.assertEqual(game_state.napoleondors, 3)
        self.assertEqual(game_state.get_investment_bonus(15), 2)
        self.assertEqual(investment.message, "Карта усилена на 2")
        self.assertIn("на 2", investment._offer_description({"kind": "investment"}))

        game_state.napoleondors = 10
        repeated = self._shop(
            {"kind": "special", "special_id": "compounding", "cost": 7}
        )
        repeated._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 10)
        self.assertEqual(repeated.message, "Compounding уже куплен")

    def test_investor_is_not_a_random_special_offer_anymore(self):
        with mock.patch.object(game_state.random, "randint", return_value=1):
            offers = game_state.build_shop_special_offer_pool(5)

        self.assertNotIn("investment", offers)

    def test_level2_shop_only_offers_short_level_specials(self):
        allowed = {
            "bailout",
            "junk_bond",
            "trader",
            "variance",
            "loan",
            "correction",
            "disclosure",
            "replication",
            "replication_plus",
            "capital_preservation",
            "mirroring",
            "retention",
        }

        for roll in (1, 100):
            with self.subTest(roll=roll), mock.patch.object(
                game_state.random, "randint", return_value=roll
            ):
                offers = game_state.build_shop_special_offer_pool(2)

            self.assertEqual(len(offers), 2)
            unexpected = set(offers) - allowed
            self.assertFalse(unexpected, f"Unexpected level-2 offers: {unexpected}")

    def test_level2_has_no_licenses_and_its_license_pool_starts_at_level3(self):
        level2_offers = game_state.generate_shop_offers(
            2, card_slots=0, special_slots=0, license_slots=None
        )
        self.assertFalse(any(offer["kind"] == "license" for offer in level2_offers))

        level3_license_pool = game_state.build_license_offer_pool(3)
        self.assertTrue({112, 113, 114, 115}.issubset(level3_license_pool))

    def test_controlling_stake_license_unlocks_from_level_four_and_remains_available(self):
        self.assertNotIn(205, game_state.build_license_offer_pool(3))
        self.assertIn(205, game_state.build_license_offer_pool(4))
        with mock.patch.object(game_state, "level_5_boss_defeated", False):
            self.assertIn(205, game_state.build_license_offer_pool(5))
        with mock.patch.object(game_state, "level_4_boss_defeated", True):
            self.assertIn(205, game_state.build_license_offer_pool(6))
        self.assertEqual(game_state.get_license_cost(205), 5)
        self.assertEqual(CARD_NAMES[205], "Controlling Stake")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[205])

    def test_frugality_license_costs_five_and_enters_the_level_three_pool(self):
        self.assertIn(209, game_state.build_license_offer_pool(3))
        self.assertIn(209, game_state.build_license_offer_pool(4))
        self.assertEqual(game_state.get_license_cost(209), 5)
        self.assertEqual(CARD_NAMES[209], "Frugality")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[209])

    def test_catalyst_license_costs_five_and_enters_the_level_three_pool(self):
        self.assertIn(210, game_state.build_license_offer_pool(3))
        self.assertIn(210, game_state.build_license_offer_pool(4))
        self.assertEqual(game_state.get_license_cost(210), 5)
        self.assertEqual(CARD_NAMES[210], "Catalyst")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[210])

    def test_nabob_license_costs_five_and_unlocks_from_level_five(self):
        self.assertNotIn(216, game_state.build_license_offer_pool(3))
        self.assertNotIn(216, game_state.build_license_offer_pool(4))
        with mock.patch.object(game_state, "level_5_boss_defeated", False):
            self.assertIn(216, game_state.build_license_offer_pool(5))
        self.assertIn(216, game_state.build_license_offer_pool(6))
        self.assertEqual(game_state.get_license_cost(216), 5)
        self.assertEqual(CARD_NAMES[216], "Набоб")
        self.assertEqual(
            LICENSE_EFFECT_DESCRIPTIONS[216],
            "Удваивает всю прибыль, полученную за раунд, после применения остальных бонусов.",
        )

    def test_short_seller_unlocks_from_level_four_and_has_seven_percent_chance(self):
        self.assertNotIn(211, game_state.build_license_offer_pool(3))
        self.assertIn(211, game_state.build_license_offer_pool(4))
        with mock.patch.object(game_state, "level_5_boss_defeated", False):
            self.assertIn(211, game_state.build_license_offer_pool(5))
        self.assertEqual(game_state.get_license_cost(211), 5)
        self.assertEqual(CARD_NAMES[211], "Short Seller")
        self.assertEqual(
            LICENSE_EFFECT_DESCRIPTIONS[211],
            "Если вы вложили все деньги в акции, которые упали 5 раз, вы сразу выигрываете. Не работает на боссах",
        )

        cards = {211: {"Type": 3, "Open": 1, "Variable": 7}}
        game_state.licensed_card_ids.add(211)
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=7):
                self.assertEqual(game_state.build_silver_cards_pool(), [211])
            with mock.patch.object(game_state.random, "randint", return_value=8):
                self.assertEqual(game_state.build_silver_cards_pool(), [])

    def test_gold_catalyst_costs_five_and_has_three_percent_pool_chance(self):
        self.assertNotIn(414, game_state.build_license_offer_pool(3))
        self.assertIsNone(game_state.get_license_cost(414))
        self.assertEqual(game_state.SHOP_CARD_COSTS[414], 5)
        self.assertEqual(CARD_NAMES[414], "Catalyst")

        cards = {414: {"Type": 5, "Open": 1, "Variable": 3}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=3):
                self.assertEqual(game_state.build_gold_cards_pool(), [414])
            with mock.patch.object(game_state.random, "randint", return_value=4):
                self.assertEqual(game_state.build_gold_cards_pool(), [])

    def test_windfall_costs_six_has_twelve_percent_chance_and_starts_at_level_five(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[426], 6)
        self.assertEqual(CARD_NAMES[426], "Windfall")

        cards = {426: {"Type": 5, "Open": 1, "Variable": 12}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=1) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(4), [])
                roll.assert_not_called()

            with mock.patch.object(game_state.random, "randint", return_value=12):
                self.assertEqual(game_state.build_gold_cards_pool(5), [426])
                self.assertEqual(game_state.build_gold_cards_pool(6), [426])

            with mock.patch.object(game_state.random, "randint", return_value=13):
                self.assertEqual(game_state.build_gold_cards_pool(5), [])

            self.assertNotIn(426, game_state.build_all_available_shop_cards(4))
            self.assertIn(426, game_state.build_all_available_shop_cards(5))

        self.assertNotIn("12%", CARD_DESCRIPTIONS[426])

    def test_gold_disclosure_costs_five_and_has_thirty_percent_pool_chance(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[427], 5)
        self.assertEqual(CARD_NAMES[427], "Disclosure")
        self.assertEqual(
            CARD_DESCRIPTIONS[427],
            "Показывает игровые вероятности и немного усиливает все карты с вероятностями",
        )

        cards = {427: {"Type": 5, "Open": 1, "Variable": 30}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=30):
                self.assertEqual(game_state.build_gold_cards_pool(3), [427])
            with mock.patch.object(game_state.random, "randint", return_value=31):
                self.assertEqual(game_state.build_gold_cards_pool(3), [])

    def test_gold_disclosure_matches_shop_visibility_without_consuming_rounds(self):
        game_state.disclosure_rounds_remaining = 0
        game_state.gold_cards = [427]
        game_state.set_active_gold_cards([427])

        self.assertTrue(game_state.is_disclosure_active())
        self.assertFalse(game_state.is_disclosure_offer_available())
        self.assertEqual(game_state.advance_disclosure_round(), 0)
        self.assertTrue(game_state.is_disclosure_active())

    def test_full_deployment_costs_four_and_has_twenty_five_percent_pool_chance(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[428], 4)
        self.assertEqual(CARD_NAMES[428], "Full Deployment")
        self.assertEqual(
            CARD_DESCRIPTIONS[428],
            "Даёт 7 наполеондоров, если все карты из колоды выложены на плейсхолдеры.",
        )

        cards = {428: {"Type": 5, "Open": 1, "Variable": 25}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=25):
                self.assertEqual(game_state.build_gold_cards_pool(3), [428])
            with mock.patch.object(game_state.random, "randint", return_value=26):
                self.assertEqual(game_state.build_gold_cards_pool(3), [])

    def test_concentration_costs_seven_and_has_ten_percent_pool_chance(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[429], 7)
        self.assertEqual(CARD_NAMES[429], "Concentration")
        self.assertNotIn("10%", CARD_DESCRIPTIONS[429])

        cards = {429: {"Type": 5, "Open": 1, "Variable": 10}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=10) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(4), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(5), [429])
            with mock.patch.object(game_state.random, "randint", return_value=11):
                self.assertEqual(game_state.build_gold_cards_pool(5), [])

    def test_waterloo_costs_five_and_has_fifteen_percent_pool_chance(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[430], 5)
        self.assertEqual(CARD_NAMES[430], "Waterloo")
        self.assertEqual(
            CARD_DESCRIPTIONS[430],
            "С вероятностью 25% показывает следующий рыночный бросок и позволяет переиграть ход.",
        )

        cards = {430: {"Type": 5, "Open": 1, "Variable": 15}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=15):
                self.assertEqual(game_state.build_gold_cards_pool(1), [430])
            with mock.patch.object(game_state.random, "randint", return_value=16):
                self.assertEqual(game_state.build_gold_cards_pool(1), [])

    def test_risk_premium_costs_five_and_has_twenty_percent_pool_chance(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[431], 5)
        self.assertEqual(CARD_NAMES[431], "Risk Premium")
        self.assertNotIn("попад", CARD_DESCRIPTIONS[431].lower())

        game_state.risk_premium_h_rounds = 2
        page = self._shop({"kind": "card", "card_id": 431, "cost": 5})
        self.assertIn("Текущий бонус карты: +20%", page._offer_description(page.offers[0]))

        cards = {431: {"Type": 5, "Open": 1, "Variable": 20}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=20):
                self.assertEqual(game_state.build_gold_cards_pool(4), [])
                self.assertEqual(game_state.build_gold_cards_pool(5), [431])
            with mock.patch.object(game_state.random, "randint", return_value=21):
                self.assertEqual(game_state.build_gold_cards_pool(5), [])

        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            self.assertNotIn(431, game_state.build_all_available_shop_cards(4))
            self.assertIn(431, game_state.build_all_available_shop_cards(5))

    def test_selling_pressure_costs_four_and_unlocks_from_level_three(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[432], 4)
        self.assertEqual(CARD_NAMES[432], "Selling Pressure")
        self.assertNotIn("30%", CARD_DESCRIPTIONS[432])

        cards = {432: {"Type": 5, "Open": 1, "Variable": 30}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=30) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(2), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(3), [432])
            with mock.patch.object(game_state.random, "randint", return_value=31):
                self.assertEqual(game_state.build_gold_cards_pool(3), [])

        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            self.assertNotIn(432, game_state.build_all_available_shop_cards(2))
            self.assertIn(432, game_state.build_all_available_shop_cards(3))

    def test_downside_risk_costs_four_and_unlocks_from_level_three(self):
        self.assertEqual(game_state.SHOP_CARD_COSTS[433], 4)
        self.assertEqual(CARD_NAMES[433], "Downside Risk")
        self.assertNotIn("30%", CARD_DESCRIPTIONS[433])

        cards = {433: {"Type": 5, "Open": 1, "Variable": 30}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=30) as roll:
                self.assertEqual(game_state.build_gold_cards_pool(2), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_gold_cards_pool(3), [433])
            with mock.patch.object(game_state.random, "randint", return_value=31):
                self.assertEqual(game_state.build_gold_cards_pool(3), [])

        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            self.assertNotIn(433, game_state.build_all_available_shop_cards(2))
            self.assertIn(433, game_state.build_all_available_shop_cards(3))

    def test_gold_card_level_gates_match_the_current_progression(self):
        level_four_cards = {401, 402, 403, 407, 418, 420, 422}
        level_five_cards = {410, 413, 414, 423, 426, 429, 431}

        for card_id in level_four_cards:
            with self.subTest(card_id=card_id):
                self.assertFalse(game_state.is_gold_card_available_for_level(card_id, 3))
                self.assertTrue(game_state.is_gold_card_available_for_level(card_id, 4))

        for card_id in level_five_cards:
            with self.subTest(card_id=card_id):
                self.assertFalse(game_state.is_gold_card_available_for_level(card_id, 4))
                self.assertTrue(game_state.is_gold_card_available_for_level(card_id, 5))

    def test_silver_concentration_starts_at_level_five_and_has_fifteen_percent_pool_chance(self):
        with mock.patch.object(game_state, "level_5_boss_defeated", False):
            self.assertNotIn(213, game_state.build_license_offer_pool(4))
            self.assertIn(213, game_state.build_license_offer_pool(5))
        self.assertEqual(game_state.get_license_cost(213), 7)
        self.assertEqual(CARD_NAMES[213], "Concentration")
        self.assertNotIn("15%", LICENSE_EFFECT_DESCRIPTIONS[213])

        game_state.licensed_card_ids.add(213)
        cards = {213: {"Type": 3, "Open": 1, "Variable": 15}}
        with mock.patch.object(game_state, "load_cards_config", return_value=cards):
            with mock.patch.object(game_state.random, "randint", return_value=15) as roll:
                self.assertEqual(game_state.build_silver_cards_pool(4), [])
                roll.assert_not_called()
                self.assertEqual(game_state.build_silver_cards_pool(5), [213])
            with mock.patch.object(game_state.random, "randint", return_value=16):
                self.assertEqual(game_state.build_silver_cards_pool(5), [])

    def test_parity_license_costs_four_and_enters_the_level_three_pool(self):
        self.assertIn(123, game_state.build_license_offer_pool(3))
        self.assertIn(123, game_state.build_license_offer_pool(4))
        self.assertEqual(game_state.get_license_cost(123), 4)
        self.assertEqual(CARD_NAMES[123], "Parity")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[123])

    def test_accumulation_license_costs_seven_and_has_ten_percent_chance(self):
        self.assertIn(124, game_state.build_license_offer_pool(3))
        self.assertEqual(game_state.get_license_cost(124), 7)
        self.assertEqual(CARD_NAMES[124], "Accumulation")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[124])

    def test_breakout_license_costs_six_and_has_twenty_percent_pool_chance(self):
        self.assertIn(125, game_state.build_license_offer_pool(3))
        self.assertEqual(game_state.get_license_cost(125), 6)
        self.assertEqual(CARD_NAMES[125], "Breakout")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[125])

    def test_silver_manipulation_license_costs_four_and_keeps_its_pool_chance(self):
        self.assertNotIn(126, game_state.build_license_offer_pool(3))
        self.assertIn(212, game_state.build_license_offer_pool(3))
        self.assertEqual(game_state.get_license_cost(212), 4)
        self.assertEqual(CARD_NAMES[212], "Манипуляция")
        self.assertNotIn("Шанс попадания в пул", LICENSE_EFFECT_DESCRIPTIONS[212])

    def test_legacy_red_manipulation_license_migrates_to_silver_card(self):
        normalized = game_state.normalize_license_ids([126])

        self.assertIn(212, normalized)
        self.assertNotIn(126, normalized)

    def test_card_descriptions_never_disclose_pool_probabilities(self):
        for card_id, description in LICENSE_EFFECT_DESCRIPTIONS.items():
            with self.subTest(card_id=card_id):
                self.assertNotIn("Шанс попадания в пул", description)

    def test_momentum_is_a_five_cost_gold_shop_card_not_a_license(self):
        self.assertNotIn(409, game_state.build_license_offer_pool(3))
        self.assertIsNone(game_state.get_license_cost(409))
        self.assertEqual(game_state.SHOP_CARD_COSTS[409], 5)
        self.assertEqual(CARD_NAMES[409], "Momentum")

        cards = {409: {"Type": 5, "Open": 1, "Variable": 35}}
        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state.random, "randint", side_effect=[100, 100, 100, 100, 100, 100, 35]),
        ):
            self.assertEqual(game_state.build_shop_card_offer_pool(3), [409])

        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state.random, "randint", side_effect=[100, 100, 100, 100, 100, 100, 36]),
        ):
            self.assertEqual(game_state.build_shop_card_offer_pool(3), [])

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

    def test_investment_excludes_multiply_cards_and_ignores_legacy_bonuses(self):
        game_state.shop_deck_cards = [17, 18, 15]
        game_state.investment_card_bonuses = {17: 2, 18: 1, 15: 1}

        eligible_cards = game_state.get_current_gain_drop_deck_cards(5)
        self.assertIn(11, eligible_cards)
        self.assertIn(15, eligible_cards)
        self.assertNotIn(17, eligible_cards)
        self.assertNotIn(18, eligible_cards)
        self.assertFalse(game_state.invest_gain_drop_card(17, 5))
        self.assertFalse(game_state.invest_gain_drop_card(18, 5))
        self.assertEqual(game_state.get_investment_bonus(17), 0)
        self.assertEqual(game_state.get_investment_bonus(18), 0)
        self.assertEqual(game_state.get_active_investment_card_bonuses(), {15: 1})

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

        self.assertEqual(offers, [{"kind": "card", "card_id": 401, "cost": 9}])
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

        self.assertEqual(offers, [{"kind": "card", "card_id": 405, "cost": 5}])
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
    def test_junk_bond_has_win_loss_and_refund_outcomes(self):
        game_state.napoleondors = 0
        with mock.patch.object(game_state.random, "randint", side_effect=[60, 61, 91]):
            self.assertEqual(game_state.resolve_junk_bond(5), "win")
            self.assertEqual(game_state.napoleondors, 6)
            self.assertEqual(game_state.resolve_junk_bond(5), "loss")
            self.assertEqual(game_state.napoleondors, 6)
            self.assertEqual(game_state.resolve_junk_bond(5), "refund")
            self.assertEqual(game_state.napoleondors, 8)

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

    def test_bank_uses_current_pre_victory_balance_at_round_end(self):
        game_state.napoleondors = 10
        self.assertTrue(game_state.buy_bank_offer())
        self.assertEqual(game_state.update_bank_interest_base(), 10)

        self.assertTrue(game_state.spend_napoleondors(4))
        self.assertEqual(
            game_state.apply_bank_interest(5, base_amount=game_state.napoleondors),
            1.5,
        )
        self.assertEqual(game_state.napoleondors, 7.5)


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
        game_state.variance_offer_bought_count = 2
        game_state.pending_shop_discount_percent = 50
        game_state.bailout_rounds_remaining = 3
        game_state.disclosure_rounds_remaining = 4
        game_state.active_long_investments = [2, 4]
        game_state.derivative_bought = True
        game_state.global_hand_bonus = 1
        game_state.issuer_bought_count = 1
        game_state.bank_bought = True
        game_state.bank_interest_base = 7.5
        game_state.multibagger_bought = True
        game_state.diversification_bought = True
        game_state.expansion_bought = True
        game_state.bill_of_exchange_offer_bought = True
        game_state.compounding_bought = True
        game_state.capital_preservation_bought = True
        game_state.deal_flow_bonus_percent = 20
        game_state.mirroring_bought_count = 1
        game_state.mirrored_deck_cards = [112]
        game_state.retention_active = True
        game_state.retention_pending_level = None
        game_state.retention_pending_cards = []
        game_state.loan_boss_positions_by_level = {5: [0]}
        game_state.licensed_card_ids.add(121)
        game_state.gold_cards = [401]
        game_state.bear_goal_reduction_steps = 2
        game_state.Frugality = 4
        progress = profile_manager._capture_progress()

        game_state.napoleondors = 0
        game_state.shop_deck_cards = []
        game_state.removed_deck_cards_by_level = {}
        game_state.investment_card_bonuses = {}
        game_state.profit_reward_bonus = 0
        game_state.updown_probability_bonus = 0
        game_state.variance_offer_bought_count = 0
        game_state.pending_shop_discount_percent = 0
        game_state.bailout_rounds_remaining = 0
        game_state.disclosure_rounds_remaining = 0
        game_state.active_long_investments = []
        game_state.derivative_bought = False
        game_state.global_hand_bonus = 0
        game_state.issuer_bought_count = 0
        game_state.bank_bought = False
        game_state.bank_interest_base = None
        game_state.multibagger_bought = False
        game_state.diversification_bought = False
        game_state.expansion_bought = False
        game_state.bill_of_exchange_offer_bought = False
        game_state.compounding_bought = False
        game_state.capital_preservation_bought = False
        game_state.deal_flow_bonus_percent = 0
        game_state.mirroring_bought_count = 0
        game_state.mirrored_deck_cards = []
        game_state.retention_active = False
        game_state.retention_pending_level = None
        game_state.retention_pending_cards = []
        game_state.loan_boss_positions_by_level = {}
        game_state.licensed_card_ids = set(game_state.DEFAULT_LICENSED_CARDS)
        game_state.gold_cards = []
        game_state.bear_goal_reduction_steps = 0
        game_state.Frugality = 0

        profile_manager.apply_profile_to_game_state({"progress": progress})

        self.assertEqual(game_state.napoleondors, 9.5)
        self.assertEqual(game_state.shop_deck_cards, [117])
        self.assertEqual(game_state.removed_deck_cards_by_level, {4: [1]})
        self.assertEqual(game_state.investment_card_bonuses, {11: 2})
        self.assertEqual(game_state.profit_reward_bonus, 2)
        self.assertEqual(game_state.get_updown_probability_bonus(), 4)
        self.assertEqual(game_state.variance_offer_bought_count, 2)
        self.assertEqual(game_state.pending_shop_discount_percent, 50)
        self.assertEqual(game_state.get_bailout_rounds_remaining(), 3)
        self.assertEqual(game_state.get_disclosure_rounds_remaining(), 4)
        self.assertEqual(game_state.get_active_long_investments(), [2, 4])
        self.assertTrue(game_state.derivative_bought)
        self.assertEqual(game_state.global_hand_bonus, 1)
        self.assertEqual(game_state.get_issuer_bought_count(), 1)
        self.assertTrue(game_state.bank_bought)
        self.assertEqual(game_state.bank_interest_base, 7.5)
        self.assertTrue(game_state.multibagger_bought)
        self.assertTrue(game_state.diversification_bought)
        self.assertTrue(game_state.expansion_bought)
        self.assertTrue(game_state.bill_of_exchange_offer_bought)
        self.assertTrue(game_state.compounding_bought)
        self.assertTrue(game_state.capital_preservation_bought)
        self.assertEqual(game_state.get_deal_flow_bonus(), 20)
        self.assertEqual(game_state.mirroring_bought_count, 1)
        self.assertEqual(game_state.mirrored_deck_cards, [112])
        self.assertTrue(game_state.retention_active)
        self.assertEqual(game_state.loan_boss_positions_by_level, {5: [0]})
        self.assertTrue(game_state.is_card_licensed(121))
        self.assertEqual(game_state.gold_cards, [401])
        self.assertEqual(game_state.bear_goal_reduction_steps, 2)
        self.assertEqual(game_state.Frugality, 4)

    def test_attempt_reset_clears_shop_upgrades_but_keeps_licenses(self):
        game_state.napoleondors = 30
        game_state.shop_deck_cards = [117]
        game_state.removed_deck_cards_by_level = {4: [1]}
        game_state.investment_card_bonuses = {11: 2}
        game_state.profit_reward_bonus = 3
        game_state.variance_offer_bought_count = 2
        game_state.pending_shop_discount_percent = 50
        game_state.correction_shop_cooldown = 2
        game_state.bailout_rounds_remaining = 4
        game_state.disclosure_rounds_remaining = 2
        game_state.active_long_investments = [2]
        game_state.derivative_bought = True
        game_state.global_hand_bonus = 1
        game_state.issuer_bought_count = 2
        game_state.bank_bought = True
        game_state.bank_interest_base = 20
        game_state.multibagger_bought = True
        game_state.diversification_bought = True
        game_state.expansion_bought = True
        game_state.bill_of_exchange_offer_bought = True
        game_state.compounding_bought = True
        game_state.deal_flow_bonus_percent = 20
        game_state.loan_boss_positions_by_level = {4: [0, 1]}
        game_state.licensed_card_ids.add(121)
        game_state.gold_cards = [401]
        game_state.bear_goal_reduction_steps = 3

        game_state.reset_level_attempt(4)

        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertEqual(game_state.removed_deck_cards_by_level, {})
        self.assertEqual(game_state.investment_card_bonuses, {})
        self.assertEqual(game_state.profit_reward_bonus, 0)
        self.assertEqual(game_state.variance_offer_bought_count, 0)
        self.assertEqual(game_state.pending_shop_discount_percent, 0)
        self.assertEqual(game_state.get_correction_shop_cooldown(), 0)
        self.assertEqual(game_state.get_bailout_rounds_remaining(), 0)
        self.assertEqual(game_state.get_disclosure_rounds_remaining(), 0)
        self.assertEqual(game_state.get_active_long_investments(), [])
        self.assertFalse(game_state.derivative_bought)
        self.assertEqual(game_state.global_hand_bonus, 0)
        self.assertEqual(game_state.get_issuer_bought_count(), 0)
        self.assertFalse(game_state.bank_bought)
        self.assertIsNone(game_state.bank_interest_base)
        self.assertFalse(game_state.multibagger_bought)
        self.assertFalse(game_state.diversification_bought)
        self.assertFalse(game_state.expansion_bought)
        self.assertFalse(game_state.bill_of_exchange_offer_bought)
        self.assertFalse(game_state.compounding_bought)
        self.assertEqual(game_state.get_deal_flow_bonus(), 0)
        self.assertEqual(game_state.loan_boss_positions_by_level, {})
        self.assertEqual(game_state.gold_cards, [])
        self.assertEqual(game_state.bear_goal_reduction_steps, 0)
        self.assertTrue(game_state.is_card_licensed(121))


if __name__ == "__main__":
    unittest.main()
