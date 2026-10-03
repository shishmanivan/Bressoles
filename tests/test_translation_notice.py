import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import unittest
from unittest.mock import patch
import pygame
from languages_page import LanguagesPage
from translation_notice import TranslationNotice, NOTICES
from localization import set_language, get_language

class TranslationNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_target_text_fits_without_switching_locale(self):
        set_language('RU')
        for size in ((1680,1050),(1280,720),(1024,768),(2560,1080)):
            for code in NOTICES:
                with self.subTest(size=size,code=code):
                    notice=TranslationNotice(pygame.display.set_mode(size),code)
                    self.assertEqual(get_language(),'RU')
                    self.assertLessEqual(len(notice.lines)*notice.line_height,notice.text_rect.height)
                    self.assertTrue(all(line.get_width() <= notice.text_rect.width for line in notice.lines))
                    self.assertLess(notice.art_rect.bottom,notice.text_rect.top)
                    self.assertLess(notice.text_rect.bottom,notice.buttons[0].top)
                    notice.draw()

    def test_mouse_keyboard_decline_and_quit(self):
        notice=TranslationNotice(pygame.display.set_mode((1280,720)),'HU')
        for index,expected in ((0,'accept'),(1,'decline')):
            with patch('translation_notice.pygame.time.get_ticks', return_value=1000), patch.object(notice, 'click_sound') as sound:
                self.assertIsNone(notice.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=notice.buttons[index].center)))
                self.assertIsNone(notice.poll_decision())
                notice.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=notice.buttons[index].center))
                sound.play.assert_called_once()
                self.assertEqual(notice.pressed_index,index)
            with patch('translation_notice.pygame.time.get_ticks', return_value=1110):
                self.assertEqual(notice.poll_decision(),expected)
        self.assertEqual(notice.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE)),'decline')
        notice.focus=0
        notice.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_TAB))
        self.assertIsNone(notice.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN)))
        with patch('translation_notice.pygame.time.get_ticks', return_value=notice.press_until):
            self.assertEqual(notice.poll_decision(),'decline')
        self.assertEqual(notice.handle_event(pygame.event.Event(pygame.QUIT)),'quit')

    def test_picker_gates_all_machine_languages(self):
        for code in NOTICES:
            page=LanguagesPage(pygame.display.set_mode((1280,720)),None,None,current_language='RU')
            with patch.object(page,'handle_input',return_value=code),patch.object(page,'draw'),patch('pygame.event.get',return_value=[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN)]):
                self.assertEqual(page.run(),code)
                self.assertIsNotNone(page.notice)
                self.assertEqual(page.current_language,'RU')
            page.notice=None
            with patch.object(page,'handle_input',side_effect=[code,'back']),patch.object(page,'draw'),patch('pygame.event.get',return_value=[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE)]):
                self.assertEqual(page.run(),'back')
                self.assertIsNone(page.notice)
            for direct in ('RU','ENG'):
                with patch.object(page,'handle_input',return_value=direct):self.assertEqual(page.run(),direct)

if __name__=='__main__':unittest.main()
