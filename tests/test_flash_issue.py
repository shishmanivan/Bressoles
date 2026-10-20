import json
import unittest
from unittest import mock

import game_state
import profile_manager
from gameplay_page import GameplayPage
from shop_page import ShopPage


class FlashIssueTests(unittest.TestCase):
    def setUp(self):
        self.progress = profile_manager._capture_progress()
        game_state.flash_issue_slots = 0
        game_state.deal_flow_bonus_percent = 0
        game_state.issuer_bought_count = 0
        game_state.boss_lifecycle_slot_bonus = 0
        game_state.level_5_boss_defeated = False
        game_state.black_cards = [301, 302]
        game_state.gold_cards = [401, 401]
        game_state.silver_cards = [201, 201]

    def tearDown(self):
        profile_manager.apply_profile_to_game_state({"progress": self.progress})

    def test_price_level_and_chance(self):
        self.assertEqual(game_state.get_shop_special_cost("flash_issue", 4), 2)
        self.assertFalse(game_state.buy_flash_issue(3))
        for level in (1, 3, 4, 6):
            for roll in (20, 21):
                with mock.patch.object(game_state.random, "randint", return_value=roll):
                    pool = game_state.build_shop_special_offer_pool(level, max_offers=100)
                self.assertEqual("flash_issue" in pool, level >= 4 and roll == 20)
            self.assertEqual("flash_issue" in game_state._available_screening_offer_ids(level), level >= 4)

    def test_purchase_and_save_preserve_slot_until_round_end(self):
        page = ShopPage.__new__(ShopPage)
        page.level_number = 4
        page.offers = [{"kind": "special", "special_id": "flash_issue", "cost": 2}]
        page.sold_offer_indexes = set()
        game_state.napoleondors = 2
        page._buy_offer(0)
        self.assertEqual(game_state.napoleondors, 0)
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 4)
        saved = json.loads(json.dumps(profile_manager._capture_progress()))
        profile_manager.apply_profile_to_game_state({"progress": saved})
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 4)
        effect = next(e for e in game_state.get_active_shop_offer_effects(4) if e["special_id"] == "flash_issue")
        self.assertEqual(effect["remaining"], 1)

    def test_last_slot_by_actual_position_returns_gold_or_black_but_discards_silver(self):
        for kind, card_id in (("gold", 401), ("black", 302), ("silver", 201)):
            with self.subTest(kind=kind):
                game_state.buy_flash_issue(4)
                order = [{"kind": "black", "card_id": 301},
                         {"kind": "gold", "card_id": 401},
                         {"kind": "empty", "card_id": None},
                         {"kind": kind, "card_id": card_id}]
                retained = game_state.expire_flash_issue(order)
                self.assertEqual(retained, order[:3])
                self.assertEqual(game_state.active_black_cards, [301])
                self.assertEqual(game_state.active_gold_cards, [401])
                self.assertEqual(game_state.gold_cards, [401, 401])
                self.assertEqual(game_state.black_cards, [301, 302])
                self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 3)
        self.assertEqual(game_state.silver_cards, [201])

    def test_round_cleanup_does_not_spend_a_second_silver_copy(self):
        game_state.buy_flash_issue(4)
        page = GameplayPage.__new__(GameplayPage)
        page.active_silver_cards = [201]
        page.active_gold_cards = [401]
        page.active_black_cards = [301]
        page.active_lifecycle_card_order = [
            {"kind": "black", "card_id": 301}, {"kind": "gold", "card_id": 401},
            {"kind": "empty", "card_id": None}, {"kind": "silver", "card_id": 201}]
        game_state.spend_silver_cards([201])
        page.active_silver_cards_spent = True
        page.profile_slot = None
        page._expire_flash_issue()
        page._expire_flash_issue()
        self.assertEqual(game_state.silver_cards, [201])
        self.assertEqual(page.active_silver_cards, [])
        self.assertEqual(len(page.active_lifecycle_card_order), 3)

    def test_issuer_and_boss_slots_remain_after_stacked_flash_issues_expire(self):
        game_state.buy_issuer_slot()
        game_state.add_boss_lifecycle_card_slot_bonus()
        for _ in range(2):
            game_state.buy_flash_issue(4)
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 7)
        game_state.expire_flash_issue([])
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 5)
        game_state.buy_flash_issue(4)
        game_state.reset_level_attempt(4)
        self.assertEqual(game_state.flash_issue_slots, 0)
