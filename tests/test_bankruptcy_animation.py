import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import native_render as pygame
import gameplay_bankruptcy_animation as animation
from gameplay_animation_clock import shift_animation_clocks


class BankruptcyAnimationTests(unittest.TestCase):
    def test_crash_impacts_in_order_with_one_uninterrupted_crowd_clip(self):
        page = SimpleNamespace(stamp_sound=mock.Mock())
        with mock.patch.object(animation.crowd, 'start') as sound_start, \
                mock.patch.object(pygame.time, 'get_ticks', return_value=1000):
            animation.start_sequence(page, (0, 1, 2))
        duration = animation.DURATION_MS + 2 * animation.CRASH_STAGGER_MS
        sound_start.assert_called_once_with(page, duration)
        with mock.patch.object(animation.crowd, 'update') as sound_update:
            for index in range(3):
                elapsed = animation.PREPARE_MS + index * animation.CRASH_STAGGER_MS
                with mock.patch.object(pygame.time, 'get_ticks', return_value=1000 + elapsed):
                    animation.update(page)
                self.assertEqual(page.stamp_sound.play.call_count, index + 1)
                self.assertEqual([m for m, a in page.bankruptcy_animations.items() if a['impacted']],
                                 list(range(index + 1)))
                sound_update.assert_called_with(page, elapsed)
            with mock.patch.object(pygame.time, 'get_ticks', return_value=1000 + duration - 1):
                animation.update(page)
            self.assertEqual(list(page.bankruptcy_animations), [2])
            with mock.patch.object(pygame.time, 'get_ticks', return_value=1000 + duration):
                animation.update(page)
            sound_update.assert_called_with(page, duration)
            self.assertFalse(page.bankruptcy_animations)

    def test_impact_sound_once_pause_and_cleanup(self):
        page = SimpleNamespace(stamp_sound=mock.Mock())
        with mock.patch.object(pygame.time, 'get_ticks', return_value=1000):
            animation.start(page, 1)
        with mock.patch.object(pygame.time, 'get_ticks', return_value=1499):
            animation.update(page)
        page.stamp_sound.play.assert_not_called()
        self.assertEqual(animation.shake(page, 1), (0, 0))
        shift_animation_clocks(page, 2000)
        with mock.patch.object(pygame.time, 'get_ticks', return_value=3500):
            animation.update(page)
            animation.update(page)
        page.stamp_sound.play.assert_called_once()
        self.assertNotEqual(animation.shake(page, 1), (0, 0))
        self.assertEqual(animation.shake(page, 0), (0, 0))
        with mock.patch.object(pygame.time, 'get_ticks', return_value=5400):
            animation.update(page)
        self.assertFalse(page.bankruptcy_animations)

    def test_five_copies_start_on_icon_then_fall_without_changing_source(self):
        bundle = pygame.Surface((60, 40), pygame.SRCALPHA)
        bundle.fill((80, 70, 60, 255))
        page = SimpleNamespace(bundle_image=bundle, screen=mock.Mock(),
                               bankruptcy_animations={0: {'elapsed': 250}})
        layout = {'frame_rects': [{'market': 0, 'rect': pygame.Rect(100, 40, 350, 600)}]}
        animation.draw(page, layout)
        self.assertEqual(page.screen.blit.call_count, 5)
        centers = [call.args[1].center for call in page.screen.blit.call_args_list]
        self.assertEqual(centers, [(155, 243)] * 5)
        self.assertEqual(bundle.get_at((0, 0)), (80, 70, 60, 255))
        page.screen.reset_mock()
        page.bankruptcy_animations[0]['elapsed'] = 2000
        animation.draw(page, layout)
        centers = [call.args[1].center for call in page.screen.blit.call_args_list]
        self.assertEqual(len(set(centers)), 5)
        self.assertTrue(all(y > 243 for x, y in centers))
