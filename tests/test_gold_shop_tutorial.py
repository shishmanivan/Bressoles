import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame
import game_state
import profile_manager
from shop_page import ShopPage
from gameplay_tutorial import (GOLD_SHOP_HINT_ID, GOLD_SHOP_HINT_TEXT, TutorialHint,
                               INVESTMENT_HINT_ID, INVESTMENT_HINT_TEXT)
from localization import SUPPORTED_LANGUAGES, get_language, set_language


class GoldShopTutorialTests(unittest.TestCase):
    def test_investment_hint_requires_visible_section_and_respects_seen_flag(self):
        for offers, seen, gold, expected in (
            ([], False, False, []),
            ([{"kind": "license"}], False, False, []),
            ([{"kind": "investment"}], False, False, [INVESTMENT_HINT_ID]),
            ([{"kind": "investment"}], True, False, []),
            ([{"kind": "investment"}], False, True, [GOLD_SHOP_HINT_ID, INVESTMENT_HINT_ID]),
        ):
            with self.subTest(offers=offers, seen=seen, gold=gold):
                page = ShopPage.__new__(ShopPage)
                page.offers, page.first_level3_shop, page.profile_slot = offers, gold, 1
                page.screen, page.font_path = mock.Mock(), "unused"
                with mock.patch("shop_page.profile_manager.is_tutorial_pending",
                                return_value=not seen), mock.patch(
                    "shop_page.load_scaled_image"
                ), mock.patch("shop_page.TutorialHint") as hint:
                    page._prepare_tutorial()
                    while page._tutorial_queue:
                        page._show_next_tutorial()
                    self.assertEqual([call.kwargs["hint_id"] for call in hint.call_args_list], expected)

    def test_guarantee_replaces_red_card_and_preserves_price_rules(self):
        with mock.patch.object(game_state, "build_shop_card_offer_pool", return_value=[117]), mock.patch.object(
            game_state, "build_all_available_shop_cards", return_value=[117, 401]
        ), mock.patch.object(game_state, "build_shop_special_offer_pool", return_value=[]), mock.patch.object(
            game_state, "build_license_offer_pool", return_value=[]
        ), mock.patch.object(game_state, "correction_shop_cooldown", 0):
            for level, guarantee, expected in ((3, True, 401), (3, False, 117), (4, True, 117)):
                offers = game_state.generate_shop_offers(level, card_slots=1, guarantee_gold=guarantee,
                                                          discount_percent=25)
                cards = [offer for offer in offers if offer["kind"] == "card"]
                self.assertEqual(len(cards), 1)
                self.assertEqual(cards[0]["card_id"], expected)
                self.assertEqual(cards[0]["cost"], game_state.get_discounted_shop_price(
                    game_state.SHOP_CARD_COSTS[expected], 25))

    def test_first_shop_visit_is_saved_and_hint_has_two_paragraphs_in_every_language(self):
        pygame.init()
        original_language = get_language()
        try:
            screen = pygame.display.set_mode((1680, 1050))
            with tempfile.TemporaryDirectory() as directory, mock.patch.object(
                profile_manager, "PROFILES_DIR", directory
            ), mock.patch.object(game_state, "generate_shop_offers", return_value=[]) as generate:
                page = ShopPage(screen, "egyptiennemncyr_condensedbold.ttf", 3, profile_slot=1)
                self.assertTrue(generate.call_args.kwargs["guarantee_gold"])
                # End after the first drawn frame, after its visit marker was saved.
                page.clock = mock.Mock()
                page.clock.tick.side_effect = RuntimeError("stop preview")
                with mock.patch.object(pygame.event, "get", return_value=[]):
                    with self.assertRaisesRegex(RuntimeError, "stop preview"):
                        page.run()
                self.assertTrue(profile_manager.load_profile(1)["level3_shop_visited"])
                ShopPage(screen, "egyptiennemncyr_condensedbold.ttf", 3, profile_slot=1)
                self.assertFalse(generate.call_args.kwargs["guarantee_gold"])
                ShopPage(screen, "egyptiennemncyr_condensedbold.ttf", 3, profile_slot=2)
                self.assertTrue(generate.call_args.kwargs["guarantee_gold"])
            for language in SUPPORTED_LANGUAGES:
                set_language(language)
                hint = TutorialHint(screen.get_size(), None, "egyptiennemncyr_condensedbold.ttf",
                                    hint_id=GOLD_SHOP_HINT_ID, text=GOLD_SHOP_HINT_TEXT)
                self.assertEqual(hint.lines.count(""), 1)
                self.assertLessEqual(len(hint.lines) * (hint.font.get_linesize() + 8),
                                     hint.checkbox_row.top - hint.panel.top - 65, language)
        finally:
            set_language(original_language)
            pygame.quit()
