import os
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from languages_page import LanguagesPage, MAP_SHIFT_X
from app_settings import load_music_volume, save_music_volume, load_selected_language, save_selected_language
from game_data import load_language
from start_page import StartPage
from settings_page import SettingsPage

class LanguagePickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1680,1050))

    def test_language_and_volume_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory,'settings.json')
            save_music_volume(.35,path)
            save_selected_language('ENG',path)
            self.assertEqual(load_music_volume(path),.35)
            save_music_volume(.8,path)
            self.assertEqual(load_selected_language(path),'ENG')
            with self.assertRaises(ValueError):
                save_selected_language('FR',path)

    def test_regions_resize_click_and_ocean(self):
        for size in [(1680,1050),(1280,720),(2560,1080)]:
            screen = pygame.display.set_mode(size)
            page = LanguagesPage(screen,None,None,load_language('RU'))
            def pos(x,y):
                return (page.map_rect.x + int((x+MAP_SHIFT_X)*page.map_rect.width/1678), page.map_rect.y + int(y*page.map_rect.height/937))
            for point, expected in [((620,490),'ENG'),((1150,380),'RU'),((970,295),'RU'),((945,540),'RU'),((690,330),None),((657,635),None)]:
                self.assertEqual(page.region_at(pos(*point)),expected,(size,point))
            click=pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos(620,490))
            with patch('pygame.event.get',return_value=[click]):
                self.assertEqual(page.handle_input(),'ENG')
            page.hovered='RU'
            page.draw()

    def test_navigation_to_languages_and_test_mode(self):
        page = StartPage.__new__(StartPage)
        page.button_sound=None
        self.assertEqual(page._activate_menu_item(3),'languages')
        screen=pygame.display.set_mode((1680,1050))
        settings=SettingsPage(screen,None,None,load_language('RU'))
        event=pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=settings.test_mode_rect.center)
        with patch('pygame.event.get',return_value=[event]):
            self.assertEqual(settings.handle_input(),'test_mode')

if __name__=='__main__':
    unittest.main()
