import os
import tempfile
import unittest
from unittest.mock import patch, Mock
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
import app_settings
from settings_page import SettingsPage
from localization import set_language
from game_data import load_language
from sound_assets import load_sound, set_effects_volume


class SettingsPageTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1680, 1050))
        self.defaults = {'resolution': (1680,1050), 'fullscreen': False,
                         'music_volume': 1., 'sound_volume': 1., 'show_card_info': True}
        self.settings_patch = patch('settings_page.load_settings', side_effect=lambda: dict(self.defaults))
        self.settings_patch.start()

    def tearDown(self):
        self.settings_patch.stop()
        app_settings.set_card_information_enabled(True)
        set_effects_volume(1)
        set_language('RU')

    def page(self, code='RU'):
        return SettingsPage(self.screen, None, None, load_language(code))

    def test_save_preserves_language_and_other_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'settings.json')
            app_settings.save_selected_language('DE', path)
            values = dict(self.defaults, sound_volume=.2, show_card_info=False)
            app_settings.save_settings(values, path)
            self.assertEqual(app_settings.load_selected_language(path), 'DE')
            self.assertEqual(app_settings.load_settings(path), values)

    def test_cancel_restores_preview_without_writing(self):
        changed = Mock()
        page = SettingsPage(self.screen, None, None, music_volume=.7, on_volume_change=changed)
        page._set_volume(.1)
        page.values['sound_volume'] = .2
        with patch('settings_page.save_settings') as save, patch('settings_page.set_effects_volume') as effects:
            self.assertEqual(page._cancel(), 'back')
        save.assert_not_called()
        changed.assert_called_with(.7)
        effects.assert_called_once_with(1.)

    def test_save_applies_display_and_tooltip_preference(self):
        page = self.page()
        page.values.update(resolution=(1440,900), show_card_info=False)
        with patch('settings_page.apply_display_settings', return_value=self.screen) as display, patch('settings_page.save_settings') as save:
            self.assertEqual(page._save(), 'back')
        display.assert_called_once()
        save.assert_called_once()
        self.assertFalse(app_settings.card_information_enabled())

    def test_failed_save_keeps_page_open_and_original_preferences(self):
        page = self.page()
        page.values['show_card_info'] = False
        with patch('settings_page.save_settings', side_effect=OSError('disk full')):
            self.assertIsNone(page._save())
        self.assertTrue(page.error)
        self.assertTrue(app_settings.card_information_enabled())

    def test_resized_mouse_coordinates_and_locales(self):
        for size in ((1680,1050), (1280,800), (1920,1080)):
            self.screen = pygame.display.set_mode(size)
            for code in ('RU','ENG','DE','HU'):
                page = self.page(code)
                page.draw()
                x,y=page.info_rect.center
                point=(round(page.panel_rect.x+x*page.panel_rect.width/1680),
                       round(page.panel_rect.y+y*page.panel_rect.height/1050))
                event=pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=point)
                with patch('pygame.event.get',return_value=[event]):
                    page.handle_input()
                self.assertFalse(page.values['show_card_info'])

    def test_tooltip_disabled_returns_before_accessing_card_data(self):
        from gameplay_page import GameplayPage
        from shop_page import DeckCardPage
        from silver_black_page import SilverBlackPage
        app_settings.set_card_information_enabled(False)
        GameplayPage._draw_card_tooltip(object(), 1, (0,0))
        DeckCardPage._draw_card_tooltip(object())
        SilverBlackPage._draw_card_tooltip(object())

    def test_effect_volume_updates_cached_and_future_sounds(self):
        import sound_assets
        old = Mock()
        new = Mock()
        with patch.dict(sound_assets._sound_cache, {'old':old}, clear=True), patch('sound_assets.os.path.exists',return_value=True), patch('sound_assets.pygame.mixer.Sound',return_value=new):
            set_effects_volume(.3)
            self.assertIs(load_sound('new'),new)
            old.set_volume.assert_called_with(.3)
            new.set_volume.assert_called_with(.3)

    def test_fullscreen_checkbox_changes_display_before_save(self):
        page = self.page()
        x, y = page.fullscreen_rect.center
        point = (round(page.panel_rect.x + x * page.panel_rect.width / 1680),
                 round(page.panel_rect.y + y * page.panel_rect.height / 1050))
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point)
        with patch('pygame.event.get', return_value=[event]), patch(
                'settings_page.apply_display_settings', return_value=self.screen) as display, patch(
                'settings_page.save_settings') as save:
            self.assertIsNone(page.handle_input())
        display.assert_called_once_with({'resolution': (1680,1050), 'fullscreen': True})
        self.assertTrue(page.values['fullscreen'])
        save.assert_not_called()

    def test_window_mode_and_escape_restore_original_display(self):
        page = self.page()
        original = dict(page.original_display)
        with patch('settings_page.apply_display_settings', return_value=self.screen) as display:
            page._activate('fullscreen')
            page._activate('window')
            self.assertFalse(page.values['fullscreen'])
            page._activate('fullscreen')
            event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
            with patch('pygame.event.get', return_value=[event]):
                self.assertEqual(page.handle_input(), 'back')
        self.assertEqual(display.call_args_list[1].args[0]['fullscreen'], False)
        self.assertEqual(display.call_args_list[-1].args[0], original)

    def test_saving_preview_does_not_recreate_display(self):
        page = self.page()
        with patch('settings_page.apply_display_settings', return_value=self.screen) as display, patch(
                'settings_page.save_settings') as save:
            page._activate('fullscreen')
            self.assertEqual(page._save(), 'back')
        display.assert_called_once()
        self.assertTrue(save.call_args.args[0]['fullscreen'])
        self.assertFalse(page.video_previewed)

    def test_failed_mode_change_restores_selection_and_display(self):
        page = self.page()
        with patch('settings_page.apply_display_settings', side_effect=[
                pygame.error('unsupported mode'), self.screen]) as display:
            page._activate('fullscreen')
        self.assertFalse(page.values['fullscreen'])
        self.assertFalse(page.video_previewed)
        self.assertTrue(page.error)
        self.assertEqual(display.call_args.args[0], page.original_display)

    def test_resolution_selection_previews_immediately(self):
        page = self.page()
        page.focus = 'resolution'
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
        with patch('pygame.event.get', return_value=[event]), patch(
                'settings_page.apply_display_settings', return_value=self.screen) as display:
            page.handle_input()
        display.assert_called_once_with({'resolution': (1920,1080), 'fullscreen': False})
