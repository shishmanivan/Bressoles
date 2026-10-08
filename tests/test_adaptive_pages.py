import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from native_render import draw as native_draw
import game_data
import boss_logic
from adaptive_page import AdaptivePage, adaptive_draw, content_rect
from asset_loaders import find_font_path_or_exit
from boss_page import BossPage
from round_page import RoundPage
from gameplay_page import GameplayPage
from gameplay_layout import compute_bottom_hand_layout
from profile_page import ProfilePage
from shop_page import ShopPage, InvestmentDeckPage
from silver_black_page import SilverBlackPage


class AdaptivePagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.font = find_font_path_or_exit()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_background_fills_viewport_independently_of_foreground(self):
        class Page(AdaptivePage):
            @adaptive_draw
            def draw(self):
                native_draw.rect(self.screen, "red", (1640, 1010, 40, 40))

        page = Page()
        page.init_viewport(pygame.Surface((1366, 768)))
        page._master_background = pygame.Surface((3000, 2000))
        page._master_background.fill("blue")
        page.draw()
        rect = content_rect(page.viewport.get_size())
        self.assertGreaterEqual(page.viewport.get_at((0, 0)).b, 250)
        self.assertEqual(page.viewport.get_at((0, 0)).r, 0)
        self.assertGreaterEqual(page.viewport.get_at((rect.right-3, rect.bottom-3)).r, 250)

    def test_click_motion_and_hover_share_transform_after_resize(self):
        page = AdaptivePage()
        page.init_viewport(pygame.Surface((1366, 768)))
        for size in ((1366, 768), (1280, 800), (1920, 1080), (2560, 1440), (3440, 1440)):
            page.viewport = pygame.Surface(size)
            rect = content_rect(size)
            position = (rect.x + rect.width * .8, rect.y + rect.height * .9)
            event = pygame.event.Event(pygame.MOUSEMOTION, pos=position, rel=(10, 5), buttons=(1, 0, 0))
            with mock.patch("pygame.event.get", return_value=[event]), mock.patch("pygame.mouse.get_pos", return_value=position):
                mapped = next(page.events())
                self.assertEqual(mapped.pos, page.mouse_pos())
                self.assertAlmostEqual(mapped.pos[0], 1344)
                self.assertAlmostEqual(mapped.pos[1], 945)
                self.assertAlmostEqual(mapped.rel[0], 10 * 1680 / rect.width)
            self.assertLess(page.to_content((rect.left - 1, rect.top))[0], 0)

    def test_real_pages_render_at_small_large_and_ultrawide_sizes(self):
        viewport = pygame.Surface((1366, 768))
        factories = (
            lambda: GameplayPage(viewport, self.font, test_mode=True),
            lambda: BossPage(viewport, self.font, 1, test_mode=True,
                level_boss_rounds=boss_logic.LEVEL_BOSS_ROUNDS,
                load_rounds_config=game_data.load_rounds_config,
                get_bosses_required=boss_logic.get_bosses_required,
                get_boss_number_from_filename=boss_logic.get_boss_number_from_filename),
            lambda: RoundPage(viewport, self.font, 1, 0, test_mode=True,
                load_rounds_config=game_data.load_rounds_config,
                load_levels_config=game_data.load_levels_config,
                load_boss_rewards=game_data.load_boss_rewards,
                load_rewards_config=game_data.load_rewards_config,
                get_level2_goal=game_data.get_level2_goal,
                get_level3_goal=game_data.get_level3_goal,
                get_level4_goal=game_data.get_level4_goal,
                get_boss_number_from_index=boss_logic.get_boss_number_from_index,
                get_boss_number_from_filename=boss_logic.get_boss_number_from_filename,
                apper_goal_boost=boss_logic.apper_goal_boost,
                reward_token_random_red=game_data.REWARD_TOKEN_RANDOM_RED),
            lambda: ShopPage(viewport, self.font),
            lambda: SilverBlackPage(viewport, self.font, []),
            lambda: ProfilePage(viewport, None, self.font),
            lambda: InvestmentDeckPage(viewport, self.font, 1),
        )
        for factory in factories:
            page = factory()
            for size in ((1366, 768), (1280, 800), (1920, 1080), (2560, 1440), (3440, 1440)):
                with self.subTest(page=type(page).__name__, size=size):
                    page.viewport = pygame.Surface(size)
                    with mock.patch("pygame.display.flip") as flip:
                        page.draw()
                        flip.assert_called_once()
                    self.assertEqual(page.screen.get_size(), (1680, 1050))
                    self.assertEqual(page.screen.pixels.get_size(), content_rect(size).size)
                    self.assertTrue(page.viewport.get_rect().contains(content_rect(size)))
                    self.assertNotEqual(page.viewport.get_at((0, 0))[:3], (0, 0, 0))
                    if isinstance(page, BossPage):
                        self.assertTrue(page.boss_rects)
                        self.assertEqual(self.click(page, page.boss_rects[0].center), "boss_1_0")
                    if isinstance(page, RoundPage):
                        page.round_selections.clear()
                        self.assertIsNotNone(page.button_e_rect)
                        self.assertEqual(self.click(page, page.button_e_rect.center), "button_e")
                    if isinstance(page, GameplayPage):
                        with mock.patch.object(page, "_is_hand_transition_active", return_value=False), mock.patch.object(page, "_start_turn_resolution") as end_turn:
                            self.click(page, page.end_button_rect.center)
                            end_turn.assert_called_once()
            if isinstance(page, GameplayPage):
                self.assertTrue(page.screen.get_rect().contains(page.end_button_rect))

    def click(self, page, logical_position):
        rect = content_rect(page.viewport.get_size())
        position = (rect.x + logical_position[0] * rect.width / 1680,
                    rect.y + logical_position[1] * rect.height / 1050)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position)
        with mock.patch("pygame.mouse.get_pos", return_value=position), mock.patch("pygame.event.get", return_value=[event]):
            return page.handle_input()

    def test_drag_from_hand_to_market_on_laptop(self):
        page = GameplayPage(pygame.Surface((1366, 768)), self.font, test_mode=True)
        page.hand_cards[0] = 11
        page.draw()
        layout = compute_bottom_hand_layout(page.bottom_frame, page.hand, 1680, 1050)
        x, y = layout["slot_positions"][0]
        with mock.patch.object(page, "_is_hand_transition_active", return_value=False):
            self.click(page, (x + 30, y + 60))
            self.assertEqual(page.dragged_card_source, "hand")
            self.assertEqual(page.dragged_card_index, 0)
            target = next(p for p in page.market_placeholders if p["market"] == 0 and p["slot"] == 0)
            rect = content_rect(page.viewport.get_size())
            position = (rect.x + target["rect"].centerx * rect.width / 1680,
                        rect.y + target["rect"].centery * rect.height / 1050)
            event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=position)
            with mock.patch("pygame.event.get", return_value=[event]), mock.patch("pygame.mouse.get_pos", return_value=position):
                page.handle_input()
            self.assertEqual(page.market_cards[0][0], 11)
            self.assertIsNone(page.hand_cards[0])


if __name__ == "__main__":
    unittest.main()
