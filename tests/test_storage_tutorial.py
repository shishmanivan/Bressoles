import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from silver_black_page import SilverBlackPage
from gameplay_tutorial import (
    STORAGE_HINT_ID, STORAGE_HINT_TEXT,
    SILVER_STORAGE_HINT_ID, SILVER_STORAGE_HINT_TEXT, TutorialHint,
    BLACK_STORAGE_HINT_ID, BLACK_STORAGE_HINT_TEXT,
    INVESTMENT_HINT_ID, INVESTMENT_HINT_TEXT,
)
from localization import SUPPORTED_LANGUAGES, get_language, set_language, translate


class StorageTutorialTests(unittest.TestCase):
    def test_inventory_gates_hints_and_gold_precedes_silver(self):
        for gold, silver, seen, expected in (
            ([], [], set(), []),
            ([401], [], set(), [STORAGE_HINT_ID]),
            ([], [201], set(), [SILVER_STORAGE_HINT_ID]),
            ([401], [201], set(), [STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID]),
            ([401], [201], {STORAGE_HINT_ID}, [SILVER_STORAGE_HINT_ID]),
            ([401], [201], {SILVER_STORAGE_HINT_ID}, [STORAGE_HINT_ID]),
            ([401], [201], {STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID}, []),
        ):
            with self.subTest(gold=gold, silver=silver, seen=seen):
                page = SilverBlackPage.__new__(SilverBlackPage)
                page.gold_cards, page.silver_cards = gold, silver
                page.black_cards = []
                page.profile_slot = 1
                page.screen = Mock()
                page.font_path = "unused"
                page.tutorial_hint = None
                with patch("silver_black_page.profile_manager.is_tutorial_pending",
                           side_effect=lambda slot, hint: hint not in seen), patch(
                    "silver_black_page.load_scaled_image"
                ), patch("silver_black_page.TutorialHint") as hint:
                    page._prepare_tutorial()
                    while page._tutorial_queue:
                        page._show_next_tutorial()
                    self.assertEqual([call.kwargs["hint_id"] for call in hint.call_args_list], expected)

    def test_translations_fit(self):
        pygame.font.init()
        previous = get_language()
        self.addCleanup(set_language, previous)
        for language in SUPPORTED_LANGUAGES:
            set_language(language)
            for hint_id, text in ((STORAGE_HINT_ID, STORAGE_HINT_TEXT),
                                  (SILVER_STORAGE_HINT_ID, SILVER_STORAGE_HINT_TEXT),
                                  (BLACK_STORAGE_HINT_ID, BLACK_STORAGE_HINT_TEXT),
                                  (INVESTMENT_HINT_ID, INVESTMENT_HINT_TEXT)):
                with self.subTest(language=language, hint_id=hint_id):
                    if language != "RU":
                        self.assertNotEqual(translate(text), text)
                    hint = TutorialHint((1680, 1050), None, "egyptiennemncyr_condensedbold.ttf",
                                        hint_id=hint_id, text=text)
                    self.assertLessEqual(len(hint.lines) * (hint.font.get_linesize() + 8),
                                         hint.checkbox_row.top - hint.panel.top - 65)

    def test_black_hint_requires_inventory_and_follows_other_hints(self):
        for black, seen, expected in (
            ([], set(), [STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID]),
            ([301], set(), [STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID, BLACK_STORAGE_HINT_ID]),
            ([301], {BLACK_STORAGE_HINT_ID}, [STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID]),
            ([301], {STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID}, [BLACK_STORAGE_HINT_ID]),
        ):
            with self.subTest(black=black, seen=seen):
                page = SilverBlackPage.__new__(SilverBlackPage)
                page.gold_cards, page.silver_cards, page.black_cards = [401], [201], black
                page.profile_slot, page.font_path, page.screen = 1, "unused", Mock()
                with patch("silver_black_page.profile_manager.is_tutorial_pending",
                           side_effect=lambda slot, hint: hint not in seen), patch(
                    "silver_black_page.load_scaled_image"
                ), patch("silver_black_page.TutorialHint") as hint:
                    page._prepare_tutorial()
                    while page._tutorial_queue:
                        page._show_next_tutorial()
                    self.assertEqual([call.kwargs["hint_id"] for call in hint.call_args_list], expected)
