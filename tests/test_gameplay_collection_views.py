import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from gameplay_collection_views import group_offers, group_deck_cards
from gameplay_deck import (build_initial_deck, deal_starting_hand, InvestedCard,
                           serialize_card_instance, restore_card_instance, restore_legacy_deck_origins)
from gameplay_page import GameplayPage


class CollectionViewTests(unittest.TestCase):
    def test_equal_cards_keep_their_categories_through_dealing_and_saving(self):
        deck = build_initial_deck(1, {}, shop_deck_cards=[11], temporary_reward_cards=[11])
        copies = [card for card in deck if card == 11]
        self.assertEqual([card.deck_origin for card in copies], ["permanent", "purchased", "temporary"])
        with mock.patch("gameplay_deck.random.shuffle"):
            remaining, hand = deal_starting_hand(copies, 1, [11])
        self.assertIs(hand[0], copies[0])
        restored = [restore_card_instance(serialize_card_instance(card)) for card in remaining]
        groups = group_deck_cards(restored)
        self.assertEqual(len(groups["permanent"]), 0)
        self.assertEqual(len(groups["temporary"]), 1)
        self.assertEqual(len(groups["purchased"]), 1)

    def test_legacy_origin_migration_keeps_bonus_and_respects_tagged_copies(self):
        deck = [InvestedCard(11, 3), InvestedCard(11, 0, "temporary")]
        hand = [11]
        template = [InvestedCard(11, 0, origin) for origin in ("permanent", "temporary", "purchased")]
        restore_legacy_deck_origins([deck, hand], template)
        self.assertEqual([card.deck_origin for card in deck + hand], ["permanent", "temporary", "purchased"])
        self.assertEqual(deck[0].investment_bonus, 3)

    def test_drag_scroll_does_not_select_card_but_click_does(self):
        page = self.make_page()
        page.collection_content_rect = pygame.Rect(200, 200, 1000, 600)
        page.collection_scroll_max["deck"] = 500
        page.deck_view_card_entries = [{"card_id": 11, "rect": pygame.Rect(250, 250, 100, 150)}]
        page._is_hedger_available = mock.Mock(return_value=True)
        page._select_hedger_deck_card = mock.Mock()
        down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(300, 300))
        page._handle_deck_view_event(down)
        page._handle_deck_view_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(300, 210)))
        page._handle_deck_view_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(300, 210)))
        self.assertEqual(page.collection_scroll["deck"], 90)
        page._select_hedger_deck_card.assert_not_called()
        page._handle_deck_view_event(down)
        page._handle_deck_view_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(300, 300)))
        page._select_hedger_deck_card.assert_called_once_with(11)

    def make_page(self):
        page = GameplayPage.__new__(GameplayPage)
        page.deck_toggle_rect = pygame.Rect(63, 914, 96, 96)
        page.level_number = 1
        page.defeated_count = 0
        page.bottom_placeholders = [
            {"slot": i, "rect": pygame.Rect(105 + i * 154, 640, 138, 240)} for i in range(7)
        ]
        page._collect_defeated_boss_rewards = mock.Mock(return_value=[{"filename": "1_Watt.png"}])
        offers_patch = mock.patch("gameplay_collection_views.game_state.get_active_shop_offer_effects",
                                  return_value=[{"special_id": "bank"}])
        page.test_offers = offers_patch.start()
        self.addCleanup(offers_patch.stop)
        page.deck_view_active = False
        page.collection_view = "deck"
        page.collection_scroll = dict.fromkeys(("deck", "offers", "bosses"), 0)
        page.collection_scroll_max = dict.fromkeys(("deck", "offers", "bosses"), 0)
        page.collection_close_rect = pygame.Rect(1454, 119, 40, 40)
        page._play_deck_toggle_sound = mock.Mock()
        page._reset_drag_state = mock.Mock()
        page._clear_hedger_selection = mock.Mock()
        return page

    def test_empty_icons_are_not_clickable_and_visible_icons_align_with_hand(self):
        page = self.make_page()
        rects = page._collection_navigation_rects()
        for index, rect in enumerate(rects.values()):
            self.assertEqual(rect.centerx, page.bottom_placeholders[index]["rect"].centerx)
        page.test_offers.return_value = []
        page._collect_defeated_boss_rewards.return_value = []
        self.assertEqual(list(page._collection_navigation_rects()), ["deck"])
        self.assertFalse(page._handle_collection_navigation(rects["offers"].center))
        self.assertFalse(page._handle_collection_navigation(rects["bosses"].center))
        page._collect_defeated_boss_rewards.return_value = [{"filename": "1_Watt.png"}]
        visible = page._collection_navigation_rects()
        self.assertEqual(list(visible), ["deck", "bosses"])
        self.assertEqual(visible["bosses"].centerx, page.bottom_placeholders[1]["rect"].centerx)

    def test_offer_categories_preserve_duplicate_pending_investments_and_timers(self):
        entries = [
            {"special_id": "bank", "remaining": None},
            {"special_id": "bailout", "remaining": 3, "remaining_kind": "rounds"},
            {"special_id": "loan", "remaining": 1, "remaining_kind": "bosses"},
            {"special_id": "long", "remaining": 4, "remaining_kind": "rounds"},
            {"special_id": "long", "remaining": 1, "remaining_kind": "rounds"},
            {"special_id": "retention", "remaining": 1, "remaining_kind": "bosses"},
        ]
        groups = group_offers(entries)
        self.assertEqual(groups["permanent"], entries[:1])
        self.assertEqual(groups["temporary"], entries[1:3])
        self.assertEqual(groups["pending"], entries[3:])

    def test_icons_open_distinct_views_switch_and_close(self):
        page = self.make_page()
        rects = page._collection_navigation_rects()
        self.assertEqual(len(rects), 3)
        self.assertFalse(rects["deck"].colliderect(rects["offers"]))
        for mode in ("deck", "offers", "bosses"):
            page.deck_view_card_entries = [{"card_id": 11}]
            self.assertTrue(page._handle_collection_navigation(rects[mode].center))
            self.assertTrue(page.deck_view_active)
            self.assertEqual(page.collection_view, mode)
            self.assertEqual(page.deck_view_card_entries, [])
        page._handle_collection_navigation(rects["bosses"].center)
        self.assertFalse(page.deck_view_active)
        self.assertEqual(page._play_deck_toggle_sound.call_count, 4)

    def test_offers_and_bosses_cannot_trigger_deck_selection(self):
        page = self.make_page()
        page._is_hedger_available = mock.Mock(return_value=True)
        page._select_hedger_deck_card = mock.Mock()
        page.deck_view_active = True
        for mode in ("offers", "bosses"):
            page.collection_view = mode
            page._handle_deck_view_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=(600, 300),
            ))
        page._is_hedger_available.assert_not_called()
        page._select_hedger_deck_card.assert_not_called()

    def test_scroll_is_bounded_and_independent_for_each_screen(self):
        page = self.make_page()
        page.collection_view = "offers"
        page.collection_scroll_max["offers"] = 500
        page._handle_deck_view_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-20))
        self.assertEqual(page.collection_scroll["offers"], 500)
        self.assertEqual(page.collection_scroll["deck"], 0)
        page._handle_deck_view_event(pygame.event.Event(pygame.MOUSEWHEEL, y=20))
        self.assertEqual(page.collection_scroll["offers"], 0)

    def test_escape_and_close_button_close_every_view(self):
        for mode in ("deck", "offers", "bosses"):
            page = self.make_page()
            page.collection_view = mode
            for event in (
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
                pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                   pos=page.collection_close_rect.center),
            ):
                page.deck_view_active = True
                page._handle_deck_view_event(event)
                self.assertFalse(page.deck_view_active)


if __name__ == "__main__":
    unittest.main()
