import os
import threading
import time

import pygame


DEFAULT_MENU_MUSIC_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Music",
    "Mendelssohn - Venetian Boat Song No. 1.ogg",
)
KOLBE_BOSS_MUSIC_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Music",
    "01 Allegro con brio.flac",
)
MENU_MUSIC_FADE_MS = 800


class MenuMusic:
    """Keep one looping music track active outside gameplay."""

    def __init__(self, path=DEFAULT_MENU_MUSIC_PATH, fade_ms=MENU_MUSIC_FADE_MS, volume=1.0):
        self.menu_path = path
        self.path = None
        self.fade_ms = max(0, int(fade_ms))
        self._loaded = False
        self._paused = False
        self._disabled = False
        self._menu_active = False
        self._volume = 0.0
        self._target_volume = max(0.0, min(1.0, float(volume)))
        self._fade_generation = 0
        self._lock = threading.Lock()

    def _fade_to(self, target_volume, pause_at_end=False):
        target_volume = max(0.0, min(1.0, float(target_volume)))
        with self._lock:
            self._fade_generation += 1
            generation = self._fade_generation
            start_volume = self._volume

        def perform_fade():
            steps = max(1, self.fade_ms // 20)
            step_delay = self.fade_ms / steps / 1000.0 if self.fade_ms else 0.0

            for step in range(1, steps + 1):
                if step_delay:
                    time.sleep(step_delay)
                with self._lock:
                    if generation != self._fade_generation or not self._loaded:
                        return
                    progress = step / steps
                    volume = start_volume + (target_volume - start_volume) * progress
                    try:
                        pygame.mixer.music.set_volume(volume)
                    except pygame.error:
                        return
                    self._volume = volume

            if pause_at_end:
                with self._lock:
                    if generation != self._fade_generation or self._menu_active or not self._loaded:
                        return
                    try:
                        pygame.mixer.music.pause()
                        self._paused = True
                    except pygame.error:
                        pass

        if self.fade_ms:
            threading.Thread(target=perform_fade, daemon=True).start()
        else:
            perform_fade()

    def play(self, path=None):
        if self._disabled:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            requested_path = os.path.abspath(path or self.menu_path)
            track_changed = (
                self._loaded
                and os.path.normcase(self.path or "") != os.path.normcase(requested_path)
            )
            if track_changed:
                with self._lock:
                    self._fade_generation += 1
                pygame.mixer.music.stop()
                self._loaded = False
                self._paused = False
                self._menu_active = False
                self._volume = 0.0

            if not self._loaded:
                pygame.mixer.music.load(requested_path)
                pygame.mixer.music.set_volume(0.0)
                pygame.mixer.music.play(-1)
                self.path = requested_path
                self._loaded = True
                self._paused = False
                self._menu_active = True
                self._volume = 0.0
                self._fade_to(self._target_volume)
            elif not self._menu_active:
                self._menu_active = True
                if self._paused:
                    pygame.mixer.music.unpause()
                elif not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(-1)
                self._paused = False
                self._fade_to(self._target_volume)
            elif not pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(0.0)
                pygame.mixer.music.play(-1)
                self._volume = 0.0
                self._fade_to(self._target_volume)
        except (OSError, pygame.error) as error:
            self._disabled = True
            print(f"WARNING: Menu music could not be played: {error}")

    @property
    def volume(self):
        return self._target_volume

    def set_volume(self, volume):
        target_volume = max(0.0, min(1.0, float(volume)))
        with self._lock:
            self._target_volume = target_volume
            self._fade_generation += 1
            if not self._loaded or not self._menu_active:
                return target_volume
            try:
                pygame.mixer.music.set_volume(target_volume)
                self._volume = target_volume
            except pygame.error:
                pass
        return target_volume

    def pause(self):
        if not self._loaded or not self._menu_active:
            return
        self._menu_active = False
        self._fade_to(0.0, pause_at_end=True)

    def stop(self):
        if not self._loaded:
            return
        with self._lock:
            self._fade_generation += 1
            self._loaded = False
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self._paused = False
        self._menu_active = False
        self._volume = 0.0
        self.path = None
