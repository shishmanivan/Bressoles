import copy
import unittest
from unittest import mock

import game_state
from shop_purchases import buy_card_or_license


class ShopPurchaseTests(unittest.TestCase):
    def setUp(self):
        for field, value in (
            ("napoleondors", 15),
            ("shop_deck_cards", []),
            ("gold_cards", []),
            ("licensed_card_ids", set(game_state.DEFAULT_LICENSED_CARDS)),
        ):
            patch = mock.patch.object(game_state, field, value)
            patch.start()
            self.addCleanup(patch.stop)

    def snapshot(self):
        return copy.deepcopy((
            game_state.napoleondors, game_state.shop_deck_cards,
            game_state.gold_cards, game_state.licensed_card_ids,
        ))

    def test_regular_card_gold_card_and_license_are_granted_and_charged_once(self):
        for kind, card_id, inventory in (
            ("card", 117, game_state.shop_deck_cards),
            ("card", 401, game_state.gold_cards),
            ("license", 121, game_state.licensed_card_ids),
        ):
            with self.subTest(kind=kind, card_id=card_id):
                before = game_state.napoleondors
                with mock.patch.object(game_state, "spend_napoleondors", wraps=game_state.spend_napoleondors) as spend:
                    result = buy_card_or_license(5, {"kind": kind, "card_id": card_id, "cost": 3})
                self.assertTrue(result.purchased)
                self.assertTrue(result.offer_exhausted)
                self.assertEqual(result.card_id, card_id)
                self.assertIn(card_id, inventory)
                self.assertEqual(game_state.napoleondors, before - 3)
                spend.assert_called_once_with(3)

    def test_insufficient_funds_preserve_every_purchase_field(self):
        for kind in ("card", "license"):
            with self.subTest(kind=kind):
                before = self.snapshot()
                result = buy_card_or_license(5, {"kind": kind, "card_id": 121, "cost": 16})
                self.assertEqual(result.status, "insufficient_funds")
                self.assertFalse(result.offer_exhausted)
                self.assertEqual(self.snapshot(), before)

    def test_repeat_purchase_does_not_charge_or_grant_again(self):
        for kind, card_id in (("card", 117), ("card", 401), ("license", 121)):
            with self.subTest(kind=kind, card_id=card_id):
                offer = {"kind": kind, "card_id": card_id, "cost": 2}
                self.assertTrue(buy_card_or_license(5, offer).purchased)
                before = self.snapshot()
                result = buy_card_or_license(5, offer)
                self.assertEqual(result.status, "already_owned")
                self.assertTrue(result.offer_exhausted)
                self.assertFalse(result.purchased)
                self.assertEqual(self.snapshot(), before)

    def test_free_card_and_license_can_be_bought_with_zero_balance(self):
        game_state.napoleondors = 0
        for kind, card_id in (("card", 117), ("license", 121)):
            with self.subTest(kind=kind):
                result = buy_card_or_license(5, {"kind": kind, "card_id": card_id, "cost": 0})
                self.assertTrue(result.purchased)
                self.assertEqual(game_state.napoleondors, 0)
        self.assertEqual(game_state.shop_deck_cards, [117])
        self.assertIn(121, game_state.licensed_card_ids)

    def test_final_discounted_price_is_used_without_a_second_discount(self):
        with mock.patch.object(game_state, "bill_of_exchange_offer_bought", True):
            for kind, card_id in (("card", 117), ("license", 121)):
                with self.subTest(kind=kind):
                    before = game_state.napoleondors
                    result = buy_card_or_license(5, {"kind": kind, "card_id": card_id, "cost": 2.5})
                    self.assertTrue(result.purchased)
                    self.assertEqual(game_state.napoleondors, before - 2.5)

    def test_full_gold_inventory_preserves_balance_and_allows_retry(self):
        game_state.gold_cards = [401] * game_state.MAX_GOLD_CARDS
        offer = {"kind": "card", "card_id": 402, "cost": 8}
        before = self.snapshot()
        result = buy_card_or_license(5, offer)
        self.assertEqual(result.status, "no_space")
        self.assertFalse(result.offer_exhausted)
        self.assertEqual(self.snapshot(), before)
        game_state.gold_cards.pop()
        self.assertTrue(buy_card_or_license(5, offer).purchased)
        self.assertEqual(game_state.gold_cards.count(402), 1)
        self.assertEqual(game_state.napoleondors, 7)

    def test_insufficient_funds_still_takes_priority_over_existing_ownership(self):
        game_state.napoleondors = 0
        game_state.shop_deck_cards = [117]
        game_state.licensed_card_ids.add(121)
        for kind, card_id in (("card", 117), ("license", 121)):
            with self.subTest(kind=kind):
                before = self.snapshot()
                result = buy_card_or_license(5, {"kind": kind, "card_id": card_id, "cost": 1})
                self.assertEqual(result.status, "insufficient_funds")
                self.assertFalse(result.offer_exhausted)
                self.assertEqual(self.snapshot(), before)

    def test_special_offers_are_rejected_without_mutating_state(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            buy_card_or_license(5, {"kind": "special", "special_id": "profit", "cost": 6})
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
