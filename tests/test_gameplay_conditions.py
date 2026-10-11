import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from gameplay_conditions import CONDITIONS, SHAREHOLDERS, conditions_for_level
from gameplay_collection_views import draw_conditions
from gameplay_page import GameplayPage
from localization import get_language, set_language, translate


class ConditionsTests(unittest.TestCase):
    def test_only_fourth_level_has_shareholders(self):
        for level in range(1, 14):
            self.assertEqual(conditions_for_level(level), (SHAREHOLDERS,) if level == 4 else ())

    def test_stale_shutdown_cannot_disable_another_levels_market(self):
        page = GameplayPage.__new__(GameplayPage)
        page.shareholder_blocked_market = 1
        page._is_arrow_trading_disabled = mock.Mock(return_value=False)
        page._is_arrow_buy_blocked = mock.Mock(return_value=False)
        for level in (1, 5, 8):
            page.level_number = level
            self.assertFalse(page._is_arrow_disabled(1, 0))

    def test_descriptions_translate_and_overflow_scrolls(self):
        pygame.font.init()
        self.addCleanup(pygame.font.quit)
        language = get_language()
        self.addCleanup(set_language, language)
        page = SimpleNamespace(
            level_number=4, collection_view="conditions", collection_scroll={},
            collection_scroll_max={}, collection_font=pygame.font.SysFont("arial", 22),
            screen=pygame.Surface((800, 600)), _get_text=lambda key, fallback: fallback,
        )
        content = pygame.Rect(30, 30, 550, 200)
        for language in ("RU", "ENG", "DE", "HU", "FR"):
            set_language(language)
            for paragraph in CONDITIONS[SHAREHOLDERS]["paragraphs"]:
                if language != "RU":
                    self.assertNotRegex(translate(paragraph), "[А-Яа-яЁё]")
            draw_conditions(page, content, content)
            self.assertGreater(page.collection_scroll_max["conditions"], 0)
            page.collection_scroll["conditions"] = 99999
            draw_conditions(page, content, content)
            self.assertEqual(page.collection_scroll["conditions"], page.collection_scroll_max["conditions"])
            self.assertEqual(page.screen.get_clip(), page.screen.get_rect())
        page.level_number = 5
        draw_conditions(page, content, content)
        self.assertEqual(page.collection_scroll_max["conditions"], 0)
        self.assertEqual(page.collection_scroll["conditions"], 0)
