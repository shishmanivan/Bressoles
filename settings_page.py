"""Localized settings on the shared menu parchment, designed at 1680 x 1050."""
import pygame

from adaptive_ui import cover_geometry
from app_settings import (RESOLUTIONS, load_settings, save_settings,
                          set_card_information_enabled)
from display_runtime import apply_display_settings
from localization import translate as tr, get_language
from game_data import load_language
from sound_assets import load_card_hover_sound, set_effects_volume, play_action_click
from start_page import MASTER_BACKGROUND_PATH, MENU_FONT_PATH

INK = (77, 63, 50)
BORDER = (89, 73, 55)
PAPER = (218, 201, 173)
SELECTED = (181, 160, 128)


class SettingsPage:
    def __init__(self, screen, background, font_path, lang_dict=None,
                 music_volume=1.0, on_volume_change=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.menu_sound = load_card_hover_sound()
        self.lang = lang_dict or load_language(get_language())
        russian = load_language("RU")
        self.text_keys = {value: key for key, value in russian.items()}
        self.on_volume_change = on_volume_change
        self.values = load_settings()
        self.music_volume = self._clamp_volume(music_volume)
        self.values['music_volume'] = self.music_volume
        self.original = dict(self.values)
        self.original_display = {
            'resolution': self.screen.get_size(),
            'fullscreen': bool(self.screen.get_flags() & pygame.FULLSCREEN),
        }
        self.values['fullscreen'] = self.original_display['fullscreen']
        self.original['fullscreen'] = self.values['fullscreen']
        self.applied_video = {key: self.values[key] for key in ('resolution', 'fullscreen')}
        self.video_previewed = False
        self.master = pygame.image.load(MASTER_BACKGROUND_PATH).convert()
        self.art = pygame.transform.smoothscale(
            pygame.image.load('UI/Settings Frame Straight Bottom.png').convert_alpha(), (1680, 1050))
        self.canvas = pygame.Surface((1680, 1050), pygame.SRCALPHA)
        self.fonts = {}
        self.slider_rect = pygame.Rect(320, 650, 208, 10)
        self.sound_slider_rect = pygame.Rect(320, 715, 208, 10)
        self.back_rect = pygame.Rect(119, 110, 183, 40)
        self.save_rect = pygame.Rect(701, 904, 266, 50)
        self.resolution_rect = pygame.Rect(316, 322, 230, 48)
        self.window_rect = pygame.Rect(485, 409, 30, 30)
        self.fullscreen_rect = pygame.Rect(485, 464, 30, 30)
        self.info_rect = pygame.Rect(1040, 330, 30, 30)
        self.controls = {
            'back': self.back_rect, 'resolution': self.resolution_rect,
            'window': pygame.Rect(91, 402, 454, 44),
            'fullscreen': pygame.Rect(91, 457, 454, 44),
            'music': self.slider_rect.inflate(12, 60),
            'sound': self.sound_slider_rect.inflate(12, 60),
            'info': self.info_rect, 'save': self.save_rect,
            'test_mode': pygame.Rect(1290, 112, 300, 46),
        }
        self.focus = 'music'
        self.dragging_volume = False
        self.dragging = None
        self.dropdown = False
        self.error = ''
        self._size = None
        self._layout()

    @staticmethod
    def _clamp_volume(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 1.0

    def _set_volume(self, value):
        normalized = self._clamp_volume(value)
        if abs(normalized - self.music_volume) < .0001:
            return
        self.music_volume = normalized
        if self.on_volume_change:
            self.on_volume_change(normalized)

    def _set_volume_from_x(self, mouse_x):
        self._set_volume((float(mouse_x) - self.slider_rect.left) / self.slider_rect.width)

    def _layout(self):
        size = self.screen.get_size()
        if size == self._size:
            return
        self._size = size
        scale = min(size[0] / 1680, size[1] / 1050) * .95
        self.panel_rect = pygame.Rect(0, 0, round(1680 * scale), round(1050 * scale))
        self.panel_rect.center = self.screen.get_rect().center
        bg_size, self.bg_pos = cover_geometry(self.master.get_size(), size)
        self.background = pygame.transform.smoothscale(self.master, bg_size)

    @property
    def test_mode_rect(self):
        rect = self.controls["test_mode"]
        sx = self.panel_rect.width / 1680
        sy = self.panel_rect.height / 1050
        return pygame.Rect(self.panel_rect.x + round(rect.x*sx), self.panel_rect.y + round(rect.y*sy), round(rect.width*sx), round(rect.height*sy))

    def _point(self, pos):
        return ((pos[0] - self.panel_rect.x) * 1680 / self.panel_rect.width,
                (pos[1] - self.panel_rect.y) * 1050 / self.panel_rect.height)

    def _text(self, text, rect, size=26, centered=False, color=INK, ink_centered=False):
        rect = pygame.Rect(rect)
        text = self.lang.get(self.text_keys.get(text), tr(text))
        while True:
            if size not in self.fonts:
                self.fonts[size] = pygame.font.Font(MENU_FONT_PATH, size)
            label = self.fonts[size].render(text, True, color)
            if label.get_width() <= rect.width or size <= 14:
                break
            size -= 1
        if ink_centered:
            # Align visible glyphs, excluding the font ascent/descent padding.
            label = label.subsurface(label.get_bounding_rect()).copy()
        target = label.get_rect(center=rect.center) if centered else label.get_rect(midleft=rect.midleft)
        self.canvas.blit(label, target)

    def _box(self, rect, checked=False, disabled=False):
        pygame.draw.rect(self.canvas, PAPER, rect, border_radius=3)
        pygame.draw.rect(self.canvas, SELECTED if disabled else BORDER, rect, 2, border_radius=3)
        if checked:
            pygame.draw.lines(self.canvas, INK, False,
                              [(rect.x+6, rect.y+15), (rect.x+12, rect.y+22), (rect.x+25, rect.y+7)], 3)

    def _slide(self, rect, volume):
        pygame.draw.rect(self.canvas, SELECTED, rect, border_radius=5)
        fill = rect.copy()
        fill.width = round(rect.width * volume)
        pygame.draw.rect(self.canvas, BORDER, fill, border_radius=5)
        center = (rect.x + fill.width, rect.centery)
        pygame.draw.circle(self.canvas, PAPER, center, 13)
        pygame.draw.circle(self.canvas, BORDER, center, 13, 2)
        self._text(f'{round(volume * 100)}%', (rect.x, rect.y+18, rect.width, 25), 19, True)

    def _change_slider(self, name, x):
        if name == 'music':
            self._set_volume_from_x(x)
        else:
            self.values['sound_volume'] = self._clamp_volume(
                (x - self.sound_slider_rect.x) / self.sound_slider_rect.width)
            set_effects_volume(self.values['sound_volume'])

    def _preview_video(self):
        requested = {key: self.values[key] for key in ('resolution', 'fullscreen')}
        if requested == self.applied_video:
            return True
        previous = {
            'resolution': self.screen.get_size(),
            'fullscreen': bool(self.screen.get_flags() & pygame.FULLSCREEN),
        }
        try:
            self.screen = apply_display_settings(requested)
        except pygame.error:
            self.values.update(self.applied_video)
            # A failed mode change can invalidate the old display surface.
            self.screen = apply_display_settings(previous)
            self.error = 'Не удалось изменить режим экрана'
            self._size = None
            self._layout()
            return False
        self.applied_video = requested
        self.video_previewed = True
        self.error = ''
        self.dragging = None
        self._size = None
        self._layout()
        return True

    def _cancel(self):
        if self.video_previewed:
            try:
                self.screen = apply_display_settings(self.original_display)
            except pygame.error:
                self.error = 'Не удалось изменить режим экрана'
                return None
            self.video_previewed = False
            self._size = None
            self._layout()
        self._set_volume(self.original['music_volume'])
        set_effects_volume(self.original['sound_volume'])
        return 'back'

    def _save(self):
        self.values['music_volume'] = self.music_volume
        if not self._preview_video():
            return None
        try:
            save_settings(self.values)
        except OSError:
            self.error = 'Не удалось сохранить настройки'
            return None
        set_card_information_enabled(self.values['show_card_info'])
        self.original = dict(self.values)
        self.video_previewed = False
        return 'back'

    def _play_menu_sound(self):
        sound = getattr(self, 'menu_sound', None)
        if sound is not None:
            sound.play()

    def _activate(self, name):
        self._play_menu_sound()
        if name == 'test_mode':
            return 'test_mode' if self._cancel() else None
        if name == 'back':
            return self._cancel()
        if name == 'save':
            return self._save()
        if name == 'resolution':
            self.dropdown = not self.dropdown
        elif name in ('window', 'fullscreen'):
            self.values['fullscreen'] = name == 'fullscreen'
            self._preview_video()
        elif name == 'info':
            self.values['show_card_info'] = not self.values['show_card_info']
        return None

    def handle_input(self):
        self._layout()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._cancel()
                return 'quit'
            if event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.get_surface() or self.screen
                self._layout()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.dropdown:
                        self.dropdown = False
                    else:
                        return self._cancel()
                elif event.key == pygame.K_TAB:
                    names = list(self.controls)
                    step = -1 if getattr(event, 'mod', 0) & pygame.KMOD_SHIFT else 1
                    self.focus = names[(names.index(self.focus)+step) % len(names)]
                    self.dropdown = False
                elif event.key in (pygame.K_LEFT, pygame.K_DOWN, pygame.K_RIGHT, pygame.K_UP):
                    step = -1 if event.key in (pygame.K_LEFT, pygame.K_DOWN) else 1
                    if self.focus == 'music':
                        self._set_volume(round(self.music_volume*20+step)/20)
                    elif self.focus == 'sound':
                        self.values['sound_volume'] = self._clamp_volume(round(self.values['sound_volume']*20+step)/20)
                        set_effects_volume(self.values['sound_volume'])
                    elif self.focus == 'resolution':
                        index = RESOLUTIONS.index(self.values['resolution'])
                        self.values['resolution'] = RESOLUTIONS[(index+step) % len(RESOLUTIONS)]
                        self._preview_video()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    result = self._activate(self.focus)
                    if result:
                        return result
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = self._point(event.pos)
                if self.dropdown:
                    for index, resolution in enumerate(RESOLUTIONS):
                        row = pygame.Rect(316, 372+index*44, 230, 44)
                        if row.collidepoint(pos):
                            self._play_menu_sound()
                            self.values['resolution'] = resolution
                            self._preview_video()
                            break
                    self.dropdown = False
                    continue
                for name, rect in self.controls.items():
                    if rect.collidepoint(pos):
                        self.focus = name
                        if name in ('music', 'sound'):
                            self.dragging = name
                            self._change_slider(name, pos[0])
                        else:
                            result = self._activate(name)
                            if result:
                                return result
                        break
            if event.type == pygame.MOUSEMOTION and self.dragging:
                self._change_slider(self.dragging, self._point(event.pos)[0])
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.dragging == 'sound':
                    play_action_click()
                self.dragging = None
        return None

    def draw(self):
        self._layout()
        self.canvas.fill((0, 0, 0, 0))
        self.canvas.blit(self.art, (0, 0))
        self._text('Настройки', (625, 73, 435, 85), 62, True)
        self._text('Закрыть', self.back_rect, 28, True, ink_centered=True)
        self._text('Тестовый режим', self.controls['test_mode'], 22, True)
        for text, rect in [('Видео', (105, 225, 425, 55)),
                           ('Звуки', (105, 552, 425, 55)),
                           ('Настройки игры', (638, 225, 420, 55)),
                           ('Дополнительно', (1160, 225, 415, 55))]:
            self._text(text, rect, 35, True)
        self._text('Разрешение', (91, 323, 215, 46))
        self._box(self.resolution_rect)
        w, h = self.values['resolution']
        self._text(f'{w} × {h}', (326, 322, 186, 48), 25, True)
        pygame.draw.polygon(self.canvas, INK, [(524,342), (536,342), (530,351)])
        self._text('Оконный режим', (91, 402, 365, 44))
        self._text('Полноэкранный', (91, 457, 365, 44))
        self._box(self.window_rect, not self.values['fullscreen'])
        self._box(self.fullscreen_rect, self.values['fullscreen'])
        self._text('Громкость музыки', (91, 626, 218, 46), 24)
        self._text('Громкость звуков', (91, 691, 218, 46), 24)
        self._slide(self.slider_rect, self.music_volume)
        self._slide(self.sound_slider_rect, self.values['sound_volume'])
        self._text('Историческая музыка', (91, 763, 360, 40), 24)
        self._text('Нормальная музыка', (91, 808, 360, 40), 24, color=(126, 105, 78))
        self._box(pygame.Rect(485, 768, 30, 30), True, True)
        self._box(pygame.Rect(485, 813, 30, 30), False, True)
        self._text('Показывать информацию', (636, 322, 390, 35), 25)
        self._text('по картам', (636, 358, 390, 35), 25)
        self._box(self.info_rect, self.values['show_card_info'])
        self._text('Сохранить', self.save_rect, 32, True, ink_centered=True)
        if self.error:
            self._text(self.error, (1090, 924, 510, 40), 21, color=(110, 42, 22))
        hovered = self._point(pygame.mouse.get_pos())
        for name, rect in self.controls.items():
            if name not in ('back', 'save') and (name == self.focus or rect.collidepoint(hovered)):
                pygame.draw.rect(self.canvas, SELECTED, rect.inflate(8, 8), 2, border_radius=4)
        if self.dropdown:
            for index, resolution in enumerate(RESOLUTIONS):
                row = pygame.Rect(316, 372+index*44, 230, 44)
                pygame.draw.rect(self.canvas, SELECTED if row.collidepoint(hovered) else PAPER, row)
                pygame.draw.rect(self.canvas, BORDER, row, 1)
                self._text(f'{resolution[0]} × {resolution[1]}', row, 25, True)
        self.screen.blit(self.background, self.bg_pos)
        self.screen.blit(pygame.transform.smoothscale(self.canvas, self.panel_rect.size), self.panel_rect)
        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()
            if result:
                return result, self.music_volume
            self.draw()
            self.clock.tick(60)
