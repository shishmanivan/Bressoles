import os
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
from app_settings import save_selected_language, load_selected_language, save_music_volume, load_music_volume
from game_data import load_language
from languages_page import LanguagesPage, EMPIRE_NAMES
from localization import set_language, translate
from gameplay_assets import load_end_turn_button
from asset_loaders import find_font_path_or_exit

class HungarianTests(unittest.TestCase):
    def tearDown(self):
        set_language('RU')

    def test_language_survives_restart_and_volume_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'settings.json')
            save_selected_language('HU', path)
            save_music_volume(.7, path)
            self.assertEqual(load_selected_language(path), 'HU')
            self.assertEqual(load_music_volume(path), .7)
            self.assertEqual(load_language(load_selected_language(path))['MenuLanguages'], 'Nyelvek')

    def test_dynamic_messages_switch_without_russian_leaks(self):
        for _ in range(2):
            set_language('HU')
            self.assertEqual(translate('Раунд 3 из 5'), 'Forduló: 3 / 5')
            self.assertEqual(translate('Карта усилена на 2'), 'A kártya ennyivel erősödött: 2')
            self.assertEqual(translate('Day: 3 /8'), 'Nap: 3 /8')
            set_language('ENG')
            self.assertEqual(translate('Раунд 3 из 5'), 'Round 3 of 5')

    def test_map_hover_selection_and_label_layout(self):
        pygame.init()
        for size in ((1680,1050), (1280,720), (2560,1080)):
            page = LanguagesPage(pygame.display.set_mode(size), None, None, load_language('HU'), 'HU')
            def point(x,y):
                return (page.map_rect.x + round(x*page.map_rect.width/1678), page.map_rect.y + round(y*page.map_rect.height/937))
            self.assertEqual(EMPIRE_NAMES['HU'], 'Osztrák–Magyar Monarchia')
            for x,y in ((1100,625), (1045,585), (1180,620), (1080,701)):
                self.assertEqual(page.region_at(point(x,y)), 'HU')
            for x,y in ((1030,535),(1160,530),(1230,690),(1165,711),(1020,743),(960,650),(930,350)):
                self.assertNotEqual(page.region_at(point(x,y)), 'HU')
            for code,rect in page.title_rects.items():
                self.assertLess(page.title_surfaces[code].get_width(), rect.width)
                self.assertFalse(rect.colliderect(page.compass_rect))
            for pos in (page.title_rects['HU'].center,point(1100,625)):
                with patch('pygame.event.get',return_value=[pygame.event.Event(pygame.MOUSEMOTION,pos=pos)]):
                    page.handle_input()
                self.assertEqual(page.hovered,'HU')
                with patch('pygame.event.get',return_value=[pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos)]):
                    self.assertEqual(page.handle_input(),'HU')
            page.draw()

    def test_hungarian_font_and_end_turn_asset(self):
        pygame.init();pygame.display.set_mode((1680,1050))
        font=pygame.font.Font(find_font_path_or_exit(),28)
        self.assertTrue(all(metric is not None for metric in font.metrics('ÁÉÍÓÖŐÚÜŰáéíóöőúüű')))
        set_language('HU');hu,_=load_end_turn_button(1680,1050)
        set_language('ENG');en,_=load_end_turn_button(1680,1050)
        self.assertIsNot(hu,en)
        self.assertEqual(hu.get_width(),en.get_width())
        set_language('HU');self.assertIs(load_end_turn_button(1680,1050)[0],hu)
