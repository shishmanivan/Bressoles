"""Regression audit for all supported display locales."""
import ast
import csv
import json
import re
import unittest
from pathlib import Path
from string import Formatter
from unittest.mock import mock_open, patch

from game_data import load_language
from localization import SUPPORTED_LANGUAGES, set_language, translate

ROOT = Path(__file__).resolve().parents[1]
CYRILLIC = re.compile('[А-Яа-яЁё]')


class LanguageParityTests(unittest.TestCase):
    def tearDown(self):
        set_language('RU')

    def test_catalogs_complete_and_placeholder_equivalent(self):
        with (ROOT / 'Lang.csv').open(encoding='utf-8-sig', newline='') as file:
            keyed = list(csv.DictReader(file, delimiter=';'))
        legacy = json.loads((ROOT / 'locales/ui.json').read_text(encoding='utf-8'))
        self.assertEqual(len({r['Key'] for r in keyed}), len(keyed))
        self.assertEqual(len({r['Source'] for r in legacy}), len(legacy))
        for row in keyed + legacy:
            expected = {f for _, f, _, _ in Formatter().parse(row['RU']) if f is not None}
            for code in SUPPORTED_LANGUAGES:
                with self.subTest(key=row.get('Key', row.get('Source')), language=code):
                    self.assertTrue(row[code].strip())
                    self.assertEqual(expected, {f for _, f, _, _ in Formatter().parse(row[code]) if f is not None})
                    if code != 'RU':
                        self.assertNotRegex(row[code], CYRILLIC)
                    set_language(code)
                    self.assertEqual(translate(row[code]), row[code])
                    if row in legacy:
                        self.assertEqual(translate(row['Source']), row[code])

    def test_all_ui_russian_literals_and_templates_have_translations(self):
        # Fixed endonyms on the map are intentional; logs, save schemas and
        # player-entered profile names are not display translation sources.
        files = list(ROOT.glob('*_page.py')) + [ROOT / 'game_screen.py', ROOT / 'gameplay_pause.py', ROOT / 'gameplay_collection_views.py']
        for path in files:
            if path.name == 'languages_page.py':
                continue
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
            for node in ast.walk(tree):
                text = None
                if isinstance(node, ast.JoinedStr):
                    text = ''.join(part.value if isinstance(part, ast.Constant) else '913' for part in node.values)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if not isinstance(parents.get(node), (ast.JoinedStr, ast.Expr)):
                        text = node.value
                if text and CYRILLIC.search(text):
                    for code in ('ENG', 'DE', 'HU', 'FR'):
                        set_language(code)
                        with self.subTest(file=path.name, line=node.lineno, language=code):
                            self.assertNotRegex(translate(text), CYRILLIC)

    def test_switching_dynamic_text_has_no_stale_locale(self):
        cases = {
            'RU': ('День: 4 /12', 'Карта усилена на 3', 'Деньги:'),
            'ENG': ('Day: 4 /12', 'Card upgraded by 3', 'Money:'),
            'DE': ('Tag: 4 /12', 'Karte um 3 verstärkt', 'Bargeld:'),
        }
        for code in ('RU', 'DE', 'ENG', 'RU', 'ENG', 'DE'):
            set_language(code)
            self.assertEqual(tuple(map(translate, ('Day: 4 /12', 'Карта усилена на 3', 'Money:'))), cases[code])

    def test_missing_locale_is_not_silently_replaced_with_russian(self):
        with patch('builtins.open', mock_open(read_data='Key;RU;ENG;DE\nExample;Пример;Example;\n')):
            with self.assertRaisesRegex(ValueError, 'missing DE translation'):
                load_language('DE')
        with self.assertRaises(ValueError):
            load_language('XX')
    def test_long_reward_layout_and_boss_popups_in_every_locale(self):
        import os
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        import pygame
        from asset_loaders import find_font_path_or_exit
        from gameplay_winlose import build_win_result_layout
        from boss_page import build_boss_popup_text_layout, POPUP_TEXT_BOTTOM_PADDING
        pygame.init()
        font = find_font_path_or_exit()
        window = pygame.Rect(560, 350, 560, 350)
        button = pygame.Rect(1010, 628, 80, 42)
        for code in SUPPORTED_LANGUAGES:
            set_language(code)
            lang = load_language(code)
            with self.subTest(language=code):
                layout = build_win_result_layout(font, [lang['RewardLevel5FinalBoss'], lang['BossVictoryDeckReset'], 'Long: +5'], window, button, 2, extra_text_lines=1)
                cards = pygame.Rect(layout['card_start_x'], layout['card_y'], 2 * layout['card_width'] + layout['card_gap'], layout['card_height'])
                self.assertGreaterEqual(cards.top, layout['text_bottom'] + 5)
                self.assertTrue(window.contains(cards))
                self.assertFalse(cards.colliderect(button))
                for number in range(1, 17):
                    if f'Boss{number}Text' not in lang:
                        continue
                    popup = build_boss_popup_text_layout(font, 375, lang[f'Boss{number}Text'], lang['PopUpReward'], lang[f'Boss{number}Reward'])
                    self.assertLessEqual(popup['content_bottom'], 375 - POPUP_TEXT_BOTTOM_PADDING)
