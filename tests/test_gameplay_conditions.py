import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from gameplay_conditions import CONDITIONS, BANKRUPTCY, SHAREHOLDERS, BOSS_SHARES, BOSS_TRADING, conditions_for_level
from gameplay_collection_views import draw_conditions
from gameplay_page import GameplayPage
from localization import get_language, set_language, translate
from gameplay_conditions import LEVEL_CONDITIONS, active_conditions_for_page, has_active_condition


class ConditionsTests(unittest.TestCase):
    def test_stakes_disable_all_conditions_including_future_conditions(self):
        for attribute, card in (("active_silver_cards", 205), ("active_gold_cards", 436)):
            page = SimpleNamespace(level_number=8)
            with mock.patch.dict(LEVEL_CONDITIONS, {8: (BOSS_SHARES, SHAREHOLDERS, BOSS_TRADING, "future")}):
                setattr(page, attribute, [str(card)])
                self.assertEqual(active_conditions_for_page(page), ())
                for condition in LEVEL_CONDITIONS[8]:
                    self.assertFalse(has_active_condition(page, condition))
                setattr(page, attribute, [])
                self.assertEqual(active_conditions_for_page(page), LEVEL_CONDITIONS[8])

    def test_stakes_prevent_trading_and_clear_stale_bot(self):
        for attribute, card in (("active_silver_cards", 205), ("active_gold_cards", 436)):
            page = GameplayPage.__new__(GameplayPage)
            page.level_number = 6
            page.is_boss_fight = True
            setattr(page, attribute, [card])
            page.stock_bot_enabled = True
            page.stock_bot = mock.Mock()
            page._stock_bot_saved_state = {"money": 1000}
            page._configure_boss_stock_bot()
            self.assertFalse(page.stock_bot_enabled)
            self.assertIsNone(page.stock_bot)
            self.assertIsNone(page._stock_bot_saved_state)
            self.assertFalse(page._is_level6_alternating_battle())

    def test_only_fourth_level_has_shareholders(self):
        for level in range(1, 14):
            self.assertEqual(conditions_for_level(level), {4: (SHAREHOLDERS,), 6: (BOSS_TRADING,), 8: (BANKRUPTCY,)}.get(level, ()))

    def test_all_condition_descriptions_are_translated(self):
        language = get_language()
        self.addCleanup(set_language, language)
        for language in ("ENG", "DE", "HU", "FR"):
            set_language(language)
            for condition in CONDITIONS.values():
                for paragraph in condition["paragraphs"]:
                    self.assertNotRegex(translate(paragraph), "[А-Яа-яЁё]")

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
