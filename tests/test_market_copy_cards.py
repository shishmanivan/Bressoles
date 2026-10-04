import copy
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import game_state
from game_data import load_cards_config
from gameplay_assets import load_gameplay_card_assets
from gameplay_deck import build_initial_deck
from gameplay_drag import find_market_drag_start
from tests import test_red_card_effects


class MarketCopyCardTests(unittest.TestCase):
    @staticmethod
    def page():
        page = test_red_card_effects.RedCardEffectTests._page()
        page.Aprice, page.BPrice, page.CPrice = 12, 24, 36
        page.Aquantity = page.Bquantity = page.Cquantity = 1
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.Day = 1
        page.insider_c_growth_turns_remaining = 0
        page.typewriter_sound = None
        page._start_card_jump_animation = mock.Mock()
        return page

    def play(self, page, card_id, market):
        slot = next(s for s in range(3) if page.market_cards[market].get(s) is None)
        self.assertTrue(page._can_play_dragged_hand_card_on_market(card_id, market))
        page.market_cards[market][slot] = card_id
        self.assertTrue(page._apply_market_copy_card(card_id, market, slot))
        return slot

    def test_all_four_allowed_placements_copy_price_and_effective_probabilities(self):
        for card_id, target, source in ((23, 1, 0), (23, 2, 1), (24, 0, 1), (24, 1, 2)):
            with self.subTest(card=card_id, target=target):
                page = self.page()
                page.market_cards[source][0] = 4
                page.market_cards[target][0] = 2
                before = page._stock_bot_probabilities()
                prices = [page.Aprice, page.BPrice, page.CPrice]
                expected = prices.copy()
                expected[target] = prices[source]
                self.play(page, card_id, target)
                self.assertEqual([page.Aprice, page.BPrice, page.CPrice], expected)
                self.assertEqual(page._stock_bot_probabilities()[target], before[source])
                self.assertEqual(page._stock_bot_probabilities()[source], before[source])
                self.assertEqual((page.StepA, page.StepB, page.StepC), (2, 4, 6))

    def test_edge_markets_reject_cards_without_mutation(self):
        for card_id, market in ((23, 0), (24, 2)):
            page = self.page()
            before = page._stock_bot_probabilities()
            self.assertFalse(page._can_play_dragged_hand_card_on_market(card_id, market))
            self.assertFalse(page._apply_market_copy_card(card_id, market, 0))
            self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (12, 24, 36))
            self.assertEqual(page._stock_bot_probabilities(), before)

    def test_snapshot_is_independent_and_later_target_cards_still_apply(self):
        page = self.page()
        self.play(page, 23, 1)
        copied = dict(page._stock_bot_probabilities()[1])
        page.market_cards[0][0] = 4
        page._apply_price_change(0, 10)
        self.assertEqual(page.BPrice, 12)
        self.assertEqual(page._stock_bot_probabilities()[1], copied)
        page.market_cards[1][1] = 3
        self.assertEqual(page._stock_bot_probabilities()[1]["fall"], copied["fall"] + 5)
        page._apply_price_change(1, 4)
        self.assertEqual((page.Aprice, page.BPrice), (22, 16))

    def test_committed_card_cannot_be_dragged_or_triggered_again(self):
        page = self.page()
        slot = self.play(page, 24, 1)
        page.CPrice = 90
        self.assertFalse(page._apply_market_copy_card(24, 1, slot))
        self.assertEqual(page.BPrice, 36)
        self.assertIsNone(find_market_drag_start(
            (10, 10), [{"market": 1, "slot": slot, "rect": pygame.Rect(0, 0, 30, 40)}],
            page.market_cards, page.market_cards_locked,
        ))

    def test_opposing_copies_are_ordered_snapshots_without_recursion(self):
        page = self.page()
        self.play(page, 24, 0)
        self.play(page, 23, 1)
        self.assertEqual((page.Aprice, page.BPrice), (24, 24))
        self.assertEqual(page._stock_bot_probabilities()[0], page._stock_bot_probabilities()[1])
        page.market_cards[1][1] = 4
        self.assertNotEqual(page._stock_bot_probabilities()[0], page._stock_bot_probabilities()[1])

    def test_copying_a_copied_market_uses_its_current_parameters(self):
        page = self.page()
        self.play(page, 23, 1)
        page.market_cards[1][1] = 4
        page.BPrice = 48
        before = page._stock_bot_probabilities()[1]
        self.play(page, 23, 2)
        self.assertEqual(page.CPrice, 48)
        self.assertEqual(page._stock_bot_probabilities()[2], before)

    def test_source_regulation_is_snapshotted_even_after_its_expiry(self):
        page = self.page()
        page.market_cards[0][0] = 20
        page.market_card_turns[0][0] = 1
        self.play(page, 23, 1)
        page.market_card_turns[0][0] = 0
        self.assertEqual(page._stock_bot_probabilities()[1], {"fall": 0, "flat": 100, "rise": 0})
        self.assertNotEqual(page._stock_bot_probabilities()[0], page._stock_bot_probabilities()[1])

    def test_destination_blue_chips_still_protects_price_and_fall_chance(self):
        page = self.page()
        page.market_cards[1][0] = 22
        self.play(page, 23, 1)
        self.assertEqual(page.BPrice, 24)
        self.assertEqual(page._stock_bot_probabilities()[1]["fall"], 0)

    def test_existing_shakeout_does_not_double_the_copy_again(self):
        page = self.page()
        page.active_gold_cards = [413]
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        before = page._stock_bot_probabilities()[2]
        self.play(page, 24, 1)
        self.assertEqual(page._stock_bot_probabilities()[1], before)

    def test_deleverage_keeps_snapshot_but_new_cards_in_reused_slots_work(self):
        page = self.page()
        page.market_cards[1][0] = 4
        self.play(page, 23, 1)
        copied = page._stock_bot_probabilities()[1]
        page.side_cards_top[0] = 111
        page._start_market_clear_animation = mock.Mock()
        self.assertTrue(page._apply_deleverage_effect_if_needed())
        self.assertEqual(page._stock_bot_probabilities()[1], copied)
        page.market_cards[1][0] = 3
        self.assertEqual(page._stock_bot_probabilities()[1]["fall"], copied["fall"] + 5)

    def test_json_snapshot_restore_does_not_recopy_prices(self):
        page = self.page()
        page.market_cards[2][0] = 4
        self.play(page, 24, 1)
        state = json.loads(json.dumps({"market_copy_snapshots": page.market_copy_snapshots}))
        resumed = self.page()
        resumed.market_cards = copy.deepcopy(page.market_cards)
        resumed._restore_market_copy_state(state)
        self.assertEqual(resumed._stock_bot_probabilities(), page._stock_bot_probabilities())
        self.assertEqual(resumed.BPrice, 24)
        resumed.market_copy_snapshots[1]["probabilities"]["fall"] = 0
        self.assertNotEqual(resumed.market_copy_snapshots, page.market_copy_snapshots)
        resumed._restore_market_copy_state({})
        self.assertEqual(resumed.market_copy_snapshots, {})

    def test_random_resolution_uses_snapshot_with_independent_rolls_and_steps(self):
        page = self.page()
        self.play(page, 24, 0)
        with mock.patch("gameplay_price_helpers.random.random", side_effect=[0.05, 0.9, 0.9]):
            queue = page.update_stock_prices()
        self.assertEqual([entry["price_change"] for entry in queue], [-2, 4, 6])

    def test_immediately_locked_copies_count_as_plays_for_efficiency(self):
        page = self.page()
        page.active_gold_cards = [435]
        self.play(page, 23, 1)
        self.play(page, 24, 0)
        self.assertEqual(page._record_efficiency_turn_bonus(), 2)
        page._lock_market_cards()
        page.Day += 1
        self.assertEqual(page._record_efficiency_turn_bonus(), 0)

    def test_copy_c_fall_is_preserved_for_the_turn_and_across_save(self):
        page = self.page()
        self.play(page, 23, 2)
        state = json.loads(json.dumps({"market_copy_turn_state": page.market_copy_turn_state}))
        self.assertTrue(state["market_copy_turn_state"]["c_fell"])
        resumed = self.page()
        resumed._restore_market_copy_state(state)
        self.assertEqual(resumed.market_copy_turn_state, page.market_copy_turn_state)
        page._lock_market_cards()
        self.assertEqual(page.market_copy_turn_state, {})

    def test_stephenson_limit_counts_immediately_committed_copy(self):
        page = self.page()
        page.boss_limit_red_gain_drop_per_turn = True
        self.play(page, 23, 1)
        self.assertFalse(page._can_play_dragged_hand_card_on_market(24, 0))
        self.assertFalse(page._can_play_dragged_hand_card_on_market(11, 0))
        page._lock_market_cards()
        self.assertTrue(page._can_play_dragged_hand_card_on_market(24, 0))


class MarketCopyShopTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("shop_deck_cards", []), ("get_bought_shop_card_ids", mock.Mock(return_value=set())),
                            ("build_gold_cards_pool", mock.Mock(return_value=[])),
                            ("get_rare_card_pool_chance", mock.Mock(side_effect=lambda chance: chance))):
            patcher = mock.patch.object(game_state, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_level_gate_applies_to_random_pool_catalog_and_purchase(self):
        for level in range(1, 5):
            with mock.patch.object(game_state.random, "randint", return_value=1):
                self.assertTrue({23, 24}.isdisjoint(game_state.build_shop_card_offer_pool(level)))
            self.assertTrue({23, 24}.isdisjoint(game_state.build_all_available_shop_cards(level)))
            self.assertIsNone(game_state.add_shop_card_to_level(level, 23))
        self.assertTrue({23, 24}.issubset(game_state.build_all_available_shop_cards(5)))

    def test_independent_ten_percent_inclusion_boundaries(self):
        for rolls, expected in (((10, 11), [23]), ((11, 10), [24]), ((10, 10), [23, 24]), ((11, 11), [])):
            with mock.patch.object(game_state.random, "randint", side_effect=[100] * 6 + list(rolls)):
                self.assertEqual(game_state.build_shop_card_offer_pool(5), expected)

    def test_bought_cards_leave_pool_and_enter_playable_deck(self):
        self.assertEqual(game_state.add_shop_card_to_level(5, 23), 23)
        self.assertEqual(game_state.add_shop_card_to_level(5, 24), 24)
        deck = build_initial_deck(5, {}, shop_deck_cards=game_state.shop_deck_cards)
        self.assertIn(23, deck)
        self.assertIn(24, deck)
        game_state.get_bought_shop_card_ids.return_value = {23, 24}
        with mock.patch.object(game_state.random, "randint", return_value=1):
            self.assertTrue({23, 24}.isdisjoint(game_state.build_shop_card_offer_pool(5)))
        self.assertTrue({23, 24}.isdisjoint(game_state.build_all_available_shop_cards(5)))

    def test_cards_are_shop_exclusive_and_not_starting_or_reward_cards(self):
        config = load_cards_config()
        for card_id in (23, 24):
            self.assertEqual(config[card_id], {"Type": 1, "Open": 0, "Variable": "10"})
            self.assertEqual(game_state.SHOP_CARD_COSTS[card_id], 5)
        self.assertTrue({23, 24}.isdisjoint(build_initial_deck(5, {})))
        for pool in (game_state.build_gain_drop_cards_pool(), game_state.build_red_cards_deck_for_level(5),
                     game_state.build_silver_cards_pool(5)):
            self.assertTrue({23, 24}.isdisjoint(pool))

    def test_both_images_load_for_hand_market_and_shop_sizes(self):
        pygame.init()
        try:
            pygame.display.set_mode((1, 1))
            assets = load_gameplay_card_assets({23: 1, 24: 1}, (90, 140), (60, 93), (70, 108))
            for key, size in (("card_images_bottom", (90, 140)), ("card_images_market", (60, 93)),
                              ("card_images_side", (70, 108))):
                for card_id in (23, 24):
                    self.assertEqual(assets[key][card_id].get_size(), size)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
