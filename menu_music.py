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
# The Ogg files contain the prepared loop transitions.
BOSS_ROUND_MUSIC_PATHS = {
    1: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Tch 35-B -First Boss.ogg"),
    2: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Romanze Opus40.ogg"),
    3: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Anitas Dance.ogg"),
    4: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "DvorakSymph7.ogg"),
    5: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Shylock5.ogg"),
    6: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Grieg Hol 4.ogg"),
    8: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Chaikovsky Serenada.ogg"),
    9: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Sommernachtstraum.ogg"),
    10: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Bethoven Violin Concerto 2.ogg"),
    13: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Dvorzhak Serenada.ogg"),
    15: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Bethoven Opus 50.ogg"),
    16: os.path.join(os.path.dirname(DEFAULT_MENU_MUSIC_PATH), "Elegy Tchaikovsky.ogg"),
}
MENU_MUSIC_FADE_MS = 800
ROUND_END_FADE_MS = 2400
MUSIC_VOLUME_SCALE = 0.49


class MenuMusic:
    """Manage the looping menu and gameplay music."""

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
        self._lock = threading.RLock()
        self._boss_positions = {}
        self._boss_durations = {}
        self._play_start_offset = 0.0

    def _remember_boss_position(self):
        path = self.path
        if path not in BOSS_ROUND_MUSIC_PATHS.values() and path != KOLBE_BOSS_MUSIC_PATH:
            return
        elapsed_ms = pygame.mixer.music.get_pos()
        if elapsed_ms < 0:
            return
        if path not in self._boss_durations:
            self._boss_durations[path] = pygame.mixer.Sound(path).get_length()
        duration = self._boss_durations[path]
        # get_pos measures elapsed playback, excluding the original seek offset.
        self._boss_positions[path] = (self._play_start_offset + elapsed_ms / 1000) % duration

    def _start_playback(self, path):
        offset = self._boss_positions.get(path, 0.0)
        if offset:
            pygame.mixer.music.play(-1, start=offset)
        else:
            pygame.mixer.music.play(-1)
        self._play_start_offset = offset

    def _fade_to(self, target_volume, pause_at_end=False, duration_ms=None, on_complete=None):
        target_volume = max(0.0, min(1.0, float(target_volume)))
        duration_ms = self.fade_ms if duration_ms is None else duration_ms
        with self._lock:
            self._fade_generation += 1
            generation = self._fade_generation
            start_volume = self._volume

        def perform_fade():
            steps = max(1, duration_ms // 20)
            step_delay = duration_ms / steps / 1000.0

            for step in range(1, steps + 1):
                if step_delay:
                    time.sleep(step_delay)
                with self._lock:
                    if generation != self._fade_generation or not self._loaded:
                        return
                    progress = step / steps
                    progress = progress * progress * (3 - 2 * progress)
                    volume = start_volume + (target_volume - start_volume) * progress
                    try:
                        pygame.mixer.music.set_volume(volume * MUSIC_VOLUME_SCALE)
                    except pygame.error:
                        return
                    self._volume = volume

            if pause_at_end or on_complete:
                with self._lock:
                    if generation != self._fade_generation or self._menu_active or not self._loaded:
                        return
                    if on_complete:
                        on_complete()
                        return
                    try:
                        pygame.mixer.music.pause()
                        self._paused = True
                    except pygame.error:
                        pass

        if duration_ms:
            threading.Thread(target=perform_fade, daemon=True).start()
        else:
            perform_fade()

    def play(self, path=None):
        with self._lock:
            self._play(path)

    def _play(self, path):
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
                self._fade_generation += 1
                self._remember_boss_position()
                pygame.mixer.music.stop()
                self._loaded = False
                self._paused = False
                self._menu_active = False
                self._volume = 0.0

            if not self._loaded:
                pygame.mixer.music.load(requested_path)
                pygame.mixer.music.set_volume(0.0)
                self._start_playback(requested_path)
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
                    self._start_playback(requested_path)
                self._paused = False
                self._fade_to(self._target_volume)
            elif not pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(0.0)
                self._start_playback(requested_path)
                self._volume = 0.0
                self._fade_to(self._target_volume)
        except (OSError, ValueError, pygame.error) as error:
            self._disabled = True
            print(f"WARNING: Menu music could not be played: {error}")

    @property
    def volume(self):
        return self._target_volume

    def set_volume(self, volume):
        target_volume = max(0.0, min(1.0, float(volume)))
        with self._lock:
            self._target_volume = target_volume
            if not self._loaded or not self._menu_active:
                return target_volume
            self._fade_generation += 1
            try:
                pygame.mixer.music.set_volume(target_volume * MUSIC_VOLUME_SCALE)
                self._volume = target_volume
            except pygame.error:
                pass
        return target_volume

    def pause(self):
        with self._lock:
            if not self._loaded or self._paused:
                return
            self._menu_active = False
            self._fade_to(0.0, pause_at_end=True)

    def return_to_menu(self):
        """Fade out the round track while the next screen is already open."""
        with self._lock:
            menu_path = os.path.abspath(self.menu_path)
            if not self._loaded or self.path == menu_path or self._paused or not self._volume:
                self._play(None)
                return
            self._menu_active = False
            self._fade_to(0.0, duration_ms=ROUND_END_FADE_MS, on_complete=self.play)

    def stop(self):
        with self._lock:
            if not self._loaded:
                return
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
