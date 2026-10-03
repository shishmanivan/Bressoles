import csv
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from string import Formatter
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
from app_settings import save_selected_language, load_selected_language, save_music_volume, load_music_volume
from game_data import load_language
from languages_page import LanguagesPage, EMPIRE_NAMES
from localization import set_language, translate


class GermanLocalizationTests(unittest.TestCase):
    def tearDown(self):
        set_language('RU')

    def test_every_catalog_entry_has_german_and_preserves_placeholders(self):
        fields = lambda text: {field for _, field, _, _ in Formatter().parse(text) if field is not None}
        with open('Lang.csv', encoding='utf-8-sig', newline='') as source:
            rows = list(csv.DictReader(source, delimiter=';'))
        for row in rows:
            with self.subTest(key=row['Key']):
                self.assertTrue(row['DE'].strip())
                self.assertFalse(re.search('[А-Яа-я]', row['DE']))
                self.assertEqual(fields(row['ENG']), fields(row['DE']))
        legacy = json.loads(Path('locales/ui.json').read_text(encoding='utf-8'))
        for row in legacy:
            for code in ('RU', 'ENG', 'DE'):
                self.assertTrue(row[code].strip())
                self.assertEqual(fields(row['Source']), fields(row[code]), row['Source'])
                if code != 'RU':
                    self.assertNotRegex(row[code], '[А-Яа-яЁё]')
        self.assertEqual(load_language('DE')['MenuLanguages'], 'Sprachen')

    def test_dynamic_effects_and_language_switching(self):
        set_language('DE')
        self.assertEqual(translate('Раунд 3 из 5'), 'Runde 3 von 5')
        self.assertEqual(translate('Карта 401'), 'Karte 401')
        self.assertEqual(translate('Выбрано: 2 из 3. Получите: 4'), 'Ausgewählt: 2 von 3. Erlös: 4')
        combined = 'Показывает следующий рыночный бросок и позволяет переиграть текущий ход. Текущая вероятность каждой проверки: 25%.'
        translated = translate(combined)
        self.assertIn('25 %', translated)
        self.assertNotRegex(translated, '[А-Яа-я]')
        set_language('ENG')
        self.assertEqual(translate('Раунд 3 из 5'), 'Round 3 of 5')

    def test_all_live_card_and_shop_descriptions_are_translated(self):
        from shop_page import SPECIAL_DESCRIPTIONS, CARD_DESCRIPTIONS
        from silver_black_page import CARD_TOOLTIPS
        from gameplay_page import FIELD_CARD_TOOLTIPS, DISCLOSURE_CARD_TOOLTIPS
        set_language('DE')
        texts = list(SPECIAL_DESCRIPTIONS.values()) + list(CARD_DESCRIPTIONS.values())
        texts += [description for table in (CARD_TOOLTIPS, FIELD_CARD_TOOLTIPS, DISCLOSURE_CARD_TOOLTIPS) for _, description in table.values()]
        for code in ('ENG', 'DE'):
            set_language(code)
            for source in texts:
                with self.subTest(source=source, language=code):
                    self.assertNotRegex(translate(source), '[А-Яа-яЁё]')

    def test_german_persists_without_changing_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'settings.json')
            save_music_volume(.4, path)
            save_selected_language('DE', path)
            self.assertEqual(load_selected_language(path), 'DE')
            self.assertEqual(load_music_volume(path), .4)

    def test_empire_order_keyboard_and_german_region_at_multiple_sizes(self):
        pygame.init()
        for size in ((1680,1050), (1280,720), (2560,1080)):
            page = LanguagesPage(pygame.display.set_mode(size), None, None, load_language('DE'), 'DE')
            self.assertEqual(list(page.title_rects), ['ENG','FR','DE','RU','HU'])
            self.assertEqual(EMPIRE_NAMES['RU'], 'Российская империя')
            self.assertEqual(EMPIRE_NAMES['DE'], 'Deutsches Reich')
            for x, y, code in [(1030,535,'DE'), (1160,530,'RU'), (870,640,'FR'), (700,400,None)]:
                pos = (page.map_rect.x+round(x*page.map_rect.width/1678), page.map_rect.y+round(y*page.map_rect.height/937))
                self.assertEqual(page.region_at(pos), code)
            for expected in ('ENG','FR','DE','RU','HU','ENG'):
                with patch('pygame.event.get', return_value=[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_TAB,mod=0)]):
                    page.handle_input()
                self.assertEqual(page.focus, expected)
            with patch('pygame.event.get', return_value=[pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=page.title_rects['DE'].center)]):
                self.assertEqual(page.handle_input(), 'DE')


    def test_end_turn_asset_cache_is_separate_for_german(self):
        from gameplay_assets import load_end_turn_button, _end_turn_button_cache
        pygame.init()
        pygame.display.set_mode((1680, 1050))
        _end_turn_button_cache.clear()
        set_language('ENG')
        english, _ = load_end_turn_button(1680, 1050)
        set_language('DE')
        german, _ = load_end_turn_button(1680, 1050)
        self.assertIsNot(german, english)
        self.assertGreater(german.get_width(), 0)
        set_language('ENG')
        self.assertIs(load_end_turn_button(1680, 1050)[0], english)
