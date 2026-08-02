import copy
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from card_catalog import (
    BID_CARD_VALUES,
    CARD_IMAGE_BASE_IDS,
    MARKET_CARD_TURNS,
    PRICE_CARD_ACTIONS,
    PRICE_CARD_IDS,
    PRICE_CARD_TURNS,
    SUPPORTED_CARD_IDS_BY_TYPE,
    get_card_image_base_id,
    validate_card_catalog,
)
from game_data import load_cards_config
from gameplay_assets import _build_card_actions, _build_card_base_mapping, _build_card_turns
from gameplay_deck import InvestedCard
from gameplay_page import GameplayPage
from gameplay_turn import apply_price_card_action, build_price_cards_processing_queue
from round_reward_preview import load_round_reward_assets
from shop_page import DECK_CARD_ACTIONS, DECK_CARD_BASES, DECK_CARD_TURNS


class CardCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_every_card_resolves_to_an_existing_base_image(self):
        self.assertEqual(validate_card_catalog(load_cards_config()), [])

    def test_rendering_consumers_share_the_same_price_card_metadata(self):
        round_assets = load_round_reward_assets()

        self.assertEqual(_build_card_base_mapping(), CARD_IMAGE_BASE_IDS)
        self.assertEqual(_build_card_actions(), PRICE_CARD_ACTIONS)
        self.assertEqual(_build_card_turns(), MARKET_CARD_TURNS)
        self.assertEqual(round_assets["card_base_mapping"], CARD_IMAGE_BASE_IDS)
        self.assertEqual(round_assets["card_actions"], PRICE_CARD_ACTIONS)
        self.assertEqual(round_assets["card_turns"], PRICE_CARD_TURNS)
        self.assertEqual(DECK_CARD_BASES, CARD_IMAGE_BASE_IDS)
        self.assertEqual(DECK_CARD_ACTIONS, PRICE_CARD_ACTIONS)
        self.assertEqual(DECK_CARD_TURNS, MARKET_CARD_TURNS)

    def test_price_card_queue_uses_the_catalog_instead_of_a_numeric_range(self):
        card_ids = sorted(PRICE_CARD_IDS)
        market_cards = {
            0: {0: card_ids[0], 1: card_ids[-1], 2: None},
            1: {0: None, 1: None, 2: None},
            2: {0: None, 1: None, 2: None},
        }
        market_turns = {
            0: {0: 1, 1: 1},
            1: {},
            2: {},
        }

        self.assertEqual(
            build_price_cards_processing_queue(market_cards, market_turns),
            [(0, 0), (0, 1)],
        )

    def test_price_card_operation_comes_from_the_catalog(self):
        prices = {"Aprice": 5, "BPrice": 5, "CPrice": 5}

        added = apply_price_card_action(prices, 0, 11, PRICE_CARD_ACTIONS[11])
        multiplied = apply_price_card_action(prices, 0, 17, PRICE_CARD_ACTIONS[17])

        self.assertEqual(added["Aprice"], 7)
        self.assertEqual(multiplied["Aprice"], 10)

    def test_gain_drop_modifiers_do_not_extend_non_gain_drop_durations(self):
        page = GameplayPage.__new__(GameplayPage)
        page.card_actions = {11: 2, 99: 3}
        page.card_turns = {11: 1, 99: 4}
        page._get_contango_gain_drop_multiplier = lambda: 2
        page._count_active_silver_card = lambda card_id: 1 if card_id == 208 else 0

        page._apply_contango_gain_drop_bonuses()
        page._apply_silver_rollover_bonus()

        self.assertEqual(page.card_actions, {11: 4, 99: 6})
        self.assertEqual(page.card_turns, {11: 2, 99: 4})

    def test_investment_changes_only_the_tagged_card_instance(self):
        page = GameplayPage.__new__(GameplayPage)
        page.card_actions = {15: -2}
        page._get_contango_gain_drop_multiplier = lambda: 1

        self.assertEqual(page._get_card_action(InvestedCard(15, 1)), -3)
        self.assertEqual(page._get_card_action(15), -2)
        self.assertEqual(page.card_actions, {15: -2})

    def test_contango_multiplies_an_invested_cards_complete_nominal(self):
        page = GameplayPage.__new__(GameplayPage)
        page.card_actions = {15: -4}
        page._get_contango_gain_drop_multiplier = lambda: 2

        self.assertEqual(page._get_card_action(InvestedCard(15, 1)), -6)
        self.assertEqual(page._get_card_action(15), -4)

    def test_missing_catalog_card_is_reported(self):
        cards = copy.deepcopy(load_cards_config())
        cards.pop(18)

        errors = validate_card_catalog(cards, check_assets=False)

        self.assertIn("Card catalog: price card 18 is absent from Cards.csv", errors)

    def test_new_lifecycle_card_cannot_enter_a_pool_without_an_effect_contract(self):
        cards = copy.deepcopy(load_cards_config())
        cards[499] = {"Type": 5, "Open": 1, "Variable": 100}

        errors = validate_card_catalog(cards, check_assets=False)

        self.assertIn(
            "Card catalog: card 499 Type=5 has no implemented gameplay contract",
            errors,
        )

    def test_every_configured_card_has_an_explicit_gameplay_contract(self):
        configured_ids = set(load_cards_config())
        supported_ids = set().union(*SUPPORTED_CARD_IDS_BY_TYPE.values())

        self.assertEqual(configured_ids, supported_ids)

    def test_shared_art_variants_resolve_to_the_expected_base(self):
        self.assertEqual(get_card_image_base_id(12), 11)
        self.assertEqual(get_card_image_base_id(16), 15)
        self.assertEqual(get_card_image_base_id(18), 17)
        self.assertEqual(get_card_image_base_id(21), 20)
        self.assertEqual(get_card_image_base_id(122), 118)

    def test_regulation_cards_have_market_durations_without_price_actions(self):
        self.assertEqual(MARKET_CARD_TURNS[20], 2)
        self.assertEqual(MARKET_CARD_TURNS[21], 3)
        self.assertNotIn(20, PRICE_CARD_ACTIONS)
        self.assertNotIn(21, PRICE_CARD_ACTIONS)

    def test_bid_values_match_the_printed_card_variants(self):
        self.assertEqual(
            BID_CARD_VALUES,
            {118: 10, 119: 20, 120: 30, 121: 50, 122: 100},
        )


if __name__ == "__main__":
    unittest.main()
