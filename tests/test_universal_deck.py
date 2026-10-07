import os
import unittest
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import pygame
import game_state
from asset_loaders import find_font_path_or_exit
from gameplay_deck import InvestedCard
from shop_page import (DeckCardPage, DelistingDeckPage, InvestmentDeckPage,
                       TraderDeckPage, CorrectionDeckPage, RetentionDeckPage,
                       MoratoriumDeckPage, MirroringDeckPage)


class UniversalDeckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1680, 1050))
        cls.font = find_font_path_or_exit()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_every_shop_deck_action_uses_the_same_renderer(self):
        for page_type in (DelistingDeckPage, InvestmentDeckPage, TraderDeckPage,
                          CorrectionDeckPage, RetentionDeckPage, MoratoriumDeckPage, MirroringDeckPage):
            self.assertIs(page_type.draw, DeckCardPage.draw)
            self.assertIs(page_type.run, DeckCardPage.run)

    def test_long_deck_scrolls_to_last_card_without_covering_controls(self):
        cards = [InvestedCard(11, 0) for _ in range(100)]
        page = DelistingDeckPage(self.screen, self.font, 1, deck=cards)
        self.assertGreater(page.scroll_max, 0)
        self.assertLess(page.content_rect.bottom, page.confirm_rect.top)
        for rect in page.card_rects:
            self.assertGreaterEqual(rect.left, page.content_rect.left)
            self.assertLessEqual(rect.right, page.content_rect.right)
        self.assertIsNone(page._card_at(page.card_rects[-1].center))
        page._scroll(100000)
        self.assertEqual(page._card_at(page.card_rects[-1].center), 99)
        page._handle_click(page.card_rects[-1].center)
        self.assertIs(page._handle_click(page.confirm_rect.center), cards[-1])
        page.draw()

    def test_drag_scroll_does_not_select_a_card(self):
        page = DelistingDeckPage(self.screen, self.font, 1, deck=[11] * 100)
        x, y = page.card_rects[0].center
        for event in (pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y)),
                      pygame.event.Event(pygame.MOUSEMOTION, pos=(x, y - 40)),
                      pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(x, y - 40))):
            page._handle_event(event)
        self.assertEqual(page.scroll_y, 40)
        self.assertIsNone(page.selected_index)

    def test_sale_labels_select_but_locked_cards_cannot_be_sold(self):
        page = TraderDeckPage(self.screen, self.font, 1, deck=[11, 15])
        with mock.patch.object(page, '_sale_value', side_effect=lambda card: None if card == 11 else 1):
            page._handle_click(page.card_rects[0].center)
            self.assertIsNone(page.selected_index)
            rect = page.card_rects[1]
            page._handle_click((rect.centerx, rect.bottom + 10))
            self.assertEqual(page.selected_index, 1)
            page.draw()
            self.assertEqual(page._handle_click(page.confirm_rect.center), 15)

    def test_correction_selection_survives_scrolling_and_obeys_limit(self):
        with mock.patch.object(game_state, 'silver_cards', [201] * 100), mock.patch.object(game_state, 'gold_cards', []):
            page = CorrectionDeckPage(self.screen, self.font, 1)
        page._handle_click(page.card_rects[0].center)
        page._scroll(100000)
        for index in (97, 98, 99):
            page._handle_click(page.card_rects[index].center)
        self.assertEqual(page.selected_indices, [0, 97, 98])
        self.assertEqual(len(page._handle_click(page.confirm_rect.center)), 3)
        page.draw()

    def test_retention_cannot_be_dismissed(self):
        page = RetentionDeckPage(self.screen, self.font, [11])
        self.assertIsNone(page._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)))
        self.assertIsNone(page._handle_click(page.close_rect.center))
        page._handle_click(page.card_rects[0].center)
        page._handle_click(page.cancel_rect.center)
        self.assertFalse(page.confirming)
        self.assertIsNone(page.selected_index)


if __name__ == '__main__':
    unittest.main()
