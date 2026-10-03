import os
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from app_settings import save_selected_language,load_selected_language,save_music_volume,load_music_volume
from game_data import load_language
from localization import set_language,translate
from languages_page import LanguagesPage,EMPIRE_NAMES
from gameplay_assets import load_end_turn_button
from asset_loaders import find_font_path_or_exit

class FrenchLocalizationTests(unittest.TestCase):
    def tearDown(self):
        set_language('RU')

    def test_french_persists_without_changing_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,'settings.json')
            save_music_volume(.45,path);save_selected_language('FR',path)
            self.assertEqual(load_selected_language(path),'FR')
            self.assertEqual(load_music_volume(path),.45)
            self.assertEqual(load_language(load_selected_language(path))['LanguageFR'],'Français')

    def test_mainland_corsica_and_plaque_hover_click_at_multiple_sizes(self):
        pygame.init()
        for size in ((1680,1050),(1280,720),(2560,1080)):
            page=LanguagesPage(pygame.display.set_mode(size),None,None,load_language('FR'),'FR')
            def pos(x,y):return (page.map_rect.x+round(x*page.map_rect.width/1678),page.map_rect.y+round(y*page.map_rect.height/937))
            self.assertEqual(EMPIRE_NAMES['FR'],'République française')
            for point in ((860,640),(815,592),(870,700),(972,746)):
                self.assertEqual(page.region_at(pos(*point)),'FR')
            for point in ((935,549),(973,682),(840,772),(972,780),(745,641),(1050,615)):
                self.assertNotEqual(page.region_at(pos(*point)),'FR')
            for rect in page.title_rects.values():self.assertFalse(rect.colliderect(page.compass_rect))
            self.assertFalse(page.back_rect.colliderect(page.compass_rect))
            self.assertLess(page.title_surfaces['FR'].get_width(),page.title_rects['FR'].width)
            for target in (pos(860,640),pos(972,746),page.title_rects['FR'].center):
                with patch('pygame.event.get',return_value=[pygame.event.Event(pygame.MOUSEMOTION,pos=target)]):page.handle_input()
                self.assertEqual(page.hovered,'FR')
                with patch('pygame.event.get',return_value=[pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=target,button=1)]):self.assertEqual(page.handle_input(),'FR')
            page.focus='ENG'
            with patch('pygame.event.get',return_value=[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_TAB,mod=0)]):page.handle_input()
            self.assertEqual(page.focus,'FR')
            with patch('pygame.event.get',return_value=[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN)]):self.assertEqual(page.handle_input(),'FR')

    def test_names_effects_and_switching(self):
        from shop_page import CARD_NAMES,SPECIAL_ASSETS,CARD_DESCRIPTIONS,SPECIAL_DESCRIPTIONS
        from silver_black_page import CARD_TOOLTIPS
        from gameplay_page import FIELD_CARD_TOOLTIPS,DISCLOSURE_CARD_TOOLTIPS
        names=list(CARD_NAMES.values())+[v[0] for v in SPECIAL_ASSETS.values()]
        descriptions=list(CARD_DESCRIPTIONS.values())+list(SPECIAL_DESCRIPTIONS.values())
        for table in (CARD_TOOLTIPS,FIELD_CARD_TOOLTIPS,DISCLOSURE_CARD_TOOLTIPS):
            names.extend(v[0] for v in table.values());descriptions.extend(v[1] for v in table.values())
        invariant={'25%','100%','Gain','Gain ×2','Contango','Manipulation','Obligation','Concentration','Accumulation','Diversification','Expansion','Correction','Waterloo','Variance'}
        set_language('FR')
        for name in names:
            self.assertNotRegex(translate(name),'[А-Яа-яЁё]')
            if name not in invariant:self.assertNotEqual(translate(name),name,name)
        for text in descriptions:self.assertNotRegex(translate(text),'[А-Яа-яЁё]')
        self.assertEqual(translate('Standardization'),'Standardisation')
        self.assertEqual(translate('Карта усилена на 3'),'Carte renforcée de 3')
        for code,expected in [('FR','Manche 2 sur 5'),('ENG','Round 2 of 5'),('FR','Manche 2 sur 5')]:
            set_language(code);self.assertEqual(translate('Раунд 2 из 5'),expected)

    def test_accents_button_and_long_shop_labels(self):
        from shop_page import ShopPage,CARD_NAMES,SPECIAL_ASSETS
        pygame.init();pygame.display.set_mode((1680,1050));font_path=find_font_path_or_exit()
        font=pygame.font.Font(font_path,28)
        self.assertTrue(all(m is not None for m in font.metrics('Ééèêàâùûôçœ')))
        set_language('FR');fr,_=load_end_turn_button(1680,1050)
        set_language('ENG');en,_=load_end_turn_button(1680,1050)
        self.assertIsNot(fr,en)
        set_language('FR');self.assertIs(load_end_turn_button(1680,1050)[0],fr)
        page=ShopPage.__new__(ShopPage);page.font_path=font_path;page.small_font=pygame.font.Font(font_path,30);page._offer_label_surface_cache={}
        for name in list(CARD_NAMES.values())+[v[0] for v in SPECIAL_ASSETS.values()]:
            for width in (136,160,190):self.assertLessEqual(page._offer_label_surface(name,width).get_width(),width)
