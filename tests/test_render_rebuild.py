import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import random
import unittest
from unittest.mock import patch
import pygame
import native_render as native
from adaptive_page import AdaptivePage, adaptive_draw, draw_modal_shade
from gameplay_composition import GameplayComposition
from gameplay_animation_clock import sync_animation_clock
from gameplay_page import GameplayPage
from gameplay_turn import advance_price_animation_frame


class RenderRebuildTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def tearDown(self):
        native.clear_cache()
        pygame.quit()

    def pixels(self, surface):
        return pygame.image.tostring(surface, 'RGBA')

    def test_gameplay_run_reaches_first_frame_with_selected_lifecycle_cards(self):
        from asset_loaders import find_font_path_or_exit
        page = GameplayPage(
            pygame.Surface((1366, 768)), find_font_path_or_exit(), test_mode=True,
            active_black_cards=[301], active_gold_cards=[401],
        )
        # Exercise the real run entry, including all tutorial hooks, update and
        # draw. Rendering alone does not cover the transition after Start.
        with patch.object(page, 'handle_input', side_effect=[None, 'back']), \
                patch('pygame.key.get_focused', return_value=True), \
                patch.object(page, 'update_gameplay', wraps=page.update_gameplay) as update, \
                patch.object(page, 'draw', wraps=page.draw) as draw:
            self.assertEqual(page.run(), 'back')
        update.assert_called_once()
        draw.assert_called_once()

    def test_retained_sequence_matches_full_with_overlap_clip_mutation_and_modal(self):
        class Page(AdaptivePage):
            retain_gameplay_composition = True
            @adaptive_draw
            def draw(self):
                self.screen.blit(self.card, (self.x, 250))
                self.screen.blit(self.card, (self.x + 75, 275))
                self.screen.set_clip((160, 180, 600, 240))
                self.screen.blit(self.label, (210, 300))
                self.screen.set_clip(None)
                native.draw.rect(self.screen, (30, 90, 20, 100), (180, 350, 430, 100), 3)
                if self.modal:
                    draw_modal_shade(self.screen, (0, 0, 0, 142))
                    native.draw.rect(self.screen, 'white', (200, 200, 700, 400))
                    if self.x == 139:
                        draw_modal_shade(self.screen, (0, 0, 0, 80))
                        native.draw.rect(self.screen, 'yellow', (300, 300, 300, 100))
        with patch('adaptive_page.load_scaled_image', return_value=None):
            page = Page()
            page.init_viewport(pygame.Surface((731, 457)))
        page.card = native.Surface((260, 320), pygame.SRCALPHA)
        page.card.fill((255, 50, 60, 130))
        page.label = native.Font(None, 38).render('Turns: 3', True, 'white')
        cache = page.screen.composition
        for i in range(22):
            page.x, page.modal = 100 + (i % 7)*13, i in (8, 9, 10)
            if i == 5:
                page.label = native.Font(None, 38).render('Turns: 2 / цена 19', True, 'yellow')
            if i == 12:
                page.card.fill((20, 80, 230, 180))
            if i == 15:
                page.viewport = pygame.Surface((1031, 644))
            page.screen.composition = cache
            page.draw()
            retained = self.pixels(page.viewport)
            page.screen.composition = None
            page.draw()
            self.assertEqual(retained, self.pixels(page.viewport), f'frame {i}')
        self.assertGreater(cache.partial_redraws, 0)

    def test_plain_surface_is_not_cached_by_identity_and_wrap_owns_source(self):
        raw = pygame.Surface((20, 20), pygame.SRCALPHA)
        raw.fill('red')
        owned = native.Surface.wrap(raw)
        canvas = native.Canvas((30, 30))
        raw.fill('blue')
        canvas.blit(owned, (0, 0))
        self.assertEqual(canvas.get_at((5, 5)), pygame.Color('red'))
        canvas.blit(raw, (0, 0))
        self.assertEqual(canvas.get_at((5, 5)), pygame.Color('blue'))
        raw.fill('green')
        canvas.blit(raw, (0, 0))
        self.assertEqual(canvas.get_at((5, 5)), pygame.Color('green'))
        owned.set_at((5, 5), 'yellow')
        canvas.blit(owned, (0, 0))
        self.assertEqual(canvas.get_at((5, 5)), pygame.Color('yellow'))

    def test_repeated_scale_reuses_recipe_but_returned_surface_is_editable(self):
        source = native.Surface((50, 50), pygame.SRCALPHA)
        source.fill('red')
        one = native.transform.smoothscale(source, (30, 30))
        two = native.transform.smoothscale(source, (30, 30))
        self.assertIs(one.recipe(), two.recipe())
        expected = self.pixels(two)
        one.fill('blue')
        self.assertEqual(self.pixels(two), expected)
        source.fill('green')
        three = native.transform.smoothscale(source, (30, 30))
        self.assertIsNot(two.recipe(), three.recipe())
        self.assertEqual(self.pixels(three), self.pixels(pygame.transform.smoothscale(source, (30, 30))))

    def test_unchanged_composition_does_not_rasterize_again(self):
        canvas = native.Canvas((100, 100))
        canvas.configure((137, 137))
        canvas.composition = GameplayComposition()
        card = native.Surface((20, 30), pygame.SRCALPHA)
        card.fill('red')
        for index in range(3):
            canvas.composition.begin(canvas.pixels.get_size())
            canvas.blit(card, (10, 10))
            canvas.composition.flush(canvas.pixels)
            if index == 0:
                misses = native.cache_info()['misses']
        self.assertEqual(misses, native.cache_info()['misses'])
        self.assertEqual(canvas.composition.dirty, [])

    def test_real_gameplay_sequence_preserves_pixels_rules_and_random_state(self):
        from asset_loaders import find_font_path_or_exit
        page = GameplayPage(pygame.Surface((1366, 768)), find_font_path_or_exit(), test_mode=True)
        page.market_cards = {m: {0: 11, 1: 15, 2: 17} for m in range(3)}
        page.market_card_turns = {m: {0: 3, 1: 2, 2: 1} for m in range(3)}
        page.hand_draw_anim = []
        cache = page.screen.composition
        with patch('pygame.time.get_ticks', return_value=10000), patch.object(page, 'mouse_pos', return_value=(-100, -100)):
            for frame in range(12):
                page.card_jump_animations[0] = {0: dict(offset_y=-5*frame)} if frame < 7 else {}
                page.pause_menu_active = frame in (3, 4)
                page.deck_view_active = frame in (6, 7)
                if frame == 5:
                    page.market_card_turns[0][0] = 1
                    page.Aprice += 5
                if frame == 9:
                    page.viewport = pygame.Surface((1280, 800))
                state, seed = page._serialize_gameplay_state(), random.getstate()
                page.screen.composition = cache
                page.draw()
                retained = self.pixels(page.viewport)
                self.assertEqual(state, page._serialize_gameplay_state())
                self.assertEqual(seed, random.getstate())
                page.screen.composition = None
                page.draw()
                self.assertEqual(retained, self.pixels(page.viewport), f'gameplay frame {frame}')

    def test_button_press_remains_visible_after_slow_first_frame(self):
        page = GameplayPage.__new__(GameplayPage)
        page.end_button = pygame.Surface((100, 50))
        page.end_button_pressed_image = pygame.Surface((96, 48))
        page.end_button_rect = pygame.Rect(100, 200, 100, 50)
        with patch('pygame.time.get_ticks', return_value=1000):
            page._start_end_button_press_animation(150)
        with patch('pygame.time.get_ticks', return_value=5000):
            self.assertIs(page._get_end_button_draw_state()[0], page.end_button_pressed_image)
        with patch('pygame.time.get_ticks', return_value=5149):
            self.assertIs(page._get_end_button_draw_state()[0], page.end_button_pressed_image)
        with patch('pygame.time.get_ticks', return_value=5150):
            self.assertIs(page._get_end_button_draw_state()[0], page.end_button)

    def test_variant_memory_is_bounded_and_resize_releases_old_variants(self):
        source = native.Surface((100, 100), pygame.SRCALPHA)
        source.fill('red')
        for size in range(10, 110):
            scaled = native.transform.smoothscale(source, (size, size))
            native.render(scaled.recipe(), (size * 2, size * 2))
        info = native.cache_info()
        self.assertLessEqual(info['logical_variant_bytes'], 8*1024**2)
        self.assertLessEqual(info['logical_variants'], 64)
        self.assertLessEqual(info['bytes'], 64*1024**2)
        self.assertLessEqual(info['entries'], 512)
        canvas = native.Canvas((100, 100))
        canvas.configure((137, 137))
        self.assertEqual(native.cache_info()['bytes'], 0)
        self.assertEqual(native.cache_info()['logical_variant_bytes'], 0)


class AnimationClockTests(unittest.TestCase):
    def page(self):
        page = GameplayPage.__new__(GameplayPage)
        page.deck_view_active = page.pause_menu_active = False
        page.tutorial_hint = None
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}
        return page

    def test_jump_duration_and_delayed_start_at_30_60_120_hz(self):
        for hz in (30, 60, 120):
            page = self.page()
            with patch('pygame.time.get_ticks', return_value=1000):
                page._start_card_jump_animation(page.card_jump_animations[0], 0, delay_ms=100)
            end = None
            for frame in range(hz):
                now = 1000 + round(frame * 1000/hz)
                with patch('pygame.time.get_ticks', return_value=now):
                    page.update_card_jump_animations()
                anim = page.card_jump_animations[0].get(0)
                if now < 1100:
                    self.assertEqual(anim['offset_y'], 0)
                if anim is None:
                    end = now - 1100
                    break
            self.assertIsNotNone(end)
            self.assertLessEqual(abs(end-350), 1000/hz + 1)

    def test_modal_focus_and_long_stall_preserve_animation_time(self):
        page = self.page()
        page.card_jump_animations[0][0] = {'start_time': 1000, 'offset_y': -10}
        page.current_price_animation = {'last_update': 1000, 'frame_idx': 0}
        sync_animation_clock(page, 1000)
        page.pause_menu_active = True
        sync_animation_clock(page, 1010)
        sync_animation_clock(page, 5010)
        page.pause_menu_active = False
        sync_animation_clock(page, 6010)
        self.assertEqual(page.card_jump_animations[0][0]['start_time'], 6000)
        self.assertEqual(page.current_price_animation['last_update'], 6000)
        sync_animation_clock(page, 6020, focused=False)
        sync_animation_clock(page, 7020, focused=True)
        self.assertEqual(page.current_price_animation['last_update'], 7000)
        sync_animation_clock(page, 8020)
        self.assertEqual(page.current_price_animation['last_update'], 7750)

    def test_price_frames_catch_up_without_losing_fractional_interval(self):
        anim = {'last_update': 1000, 'frame_idx': 0}
        self.assertFalse(advance_price_animation_frame(anim, 10, 70, 1220))
        self.assertEqual(anim, {'last_update': 1210, 'frame_idx': 3})
        self.assertTrue(advance_price_animation_frame(anim, 10, 70, 1800))

    def test_scatter_trajectory_matches_at_different_update_rates(self):
        results = []
        for hz in (30, 60, 120):
            page = self.page()
            page.market_clear_animation_duration = 1000
            page.market_clear_animations = [dict(start=1000, x=0., y=0., vx=4., vy=-9., rotation=0., spin=8.)]
            for frame in range(hz//2 + 1):
                with patch('pygame.time.get_ticks', return_value=1000+round(frame*1000/hz)):
                    page.update_market_clear_animations()
            results.append(page.market_clear_animations[0])
        for result in results[1:]:
            for key in ('x', 'y', 'vy', 'rotation'):
                self.assertAlmostEqual(result[key], results[0][key])


if __name__ == '__main__':
    unittest.main()
