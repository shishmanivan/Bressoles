import os
import sys

import pygame

import profile_manager
from asset_loaders import load_scaled_image
from shared_utils import wrap_text


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)
LIGHT_GOLD = (255, 235, 150)
PAPER_COLOR = (83, 76, 70)


class ProfilePage:
    def __init__(self, screen, background, font_path, lang_dict=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.background = background
        self.lang = lang_dict or {}
        self.font_title = pygame.font.Font(font_path, 64)
        self.font_medium = pygame.font.Font(font_path, 44)
        self.font_small = pygame.font.Font(font_path, 30)
        self.status_font = pygame.font.Font(font_path, 24)
        self.profiles = profile_manager.list_profiles()
        self.selected_slot = profile_manager.get_selected_slot()
        self.editing_slot = None
        self.input_text = ""
        self._text_cache = {}
        self.status_message = ""
        unavailable = [str(p["slot"]) for p in self.profiles if p.get("_load_error")]
        recovered = [str(p["slot"]) for p in self.profiles if profile_manager.was_profile_recovered(p["slot"])]
        if unavailable:
            self.status_message = self._unavailable_message(", ".join(unavailable))
        elif recovered:
            self.status_message = self._recovered_message(", ".join(recovered))

        window_path = os.path.join("GameplayPage", "WinLose.png")
        self.window_image = load_scaled_image(
            window_path,
            target_size=(900, 620),
            warning_message="WARNING: WinLose.png not found:",
        )
        self.window_rect = pygame.Rect(0, 0, 900, 620)
        self.window_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

        self.button_rects = []
        button_w = 310
        button_h = 95
        gap_x = 54
        gap_y = 42
        grid_w = button_w * 2 + gap_x
        grid_h = button_h * 2 + gap_y
        start_x = self.window_rect.centerx - grid_w // 2
        start_y = self.window_rect.y + 170
        for row in range(2):
            for col in range(2):
                self.button_rects.append(
                    pygame.Rect(
                        start_x + col * (button_w + gap_x),
                        start_y + row * (button_h + gap_y),
                        button_w,
                        button_h,
                    )
                )

        self.input_rect = pygame.Rect(
            self.window_rect.centerx - 310,
            self.window_rect.bottom - 145,
            620,
            62,
        )

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang.get(key, default)

    def _render_text_cached(self, font, text, color):
        cache_key = (id(font), str(text), tuple(color))
        surface = self._text_cache.get(cache_key)
        if surface is None:
            surface = font.render(str(text), True, color)
            self._text_cache[cache_key] = surface
        return surface

    def _profile_name_for_slot(self, slot):
        profile = self.profiles[slot - 1] if 1 <= slot <= len(self.profiles) else {}
        return (profile.get("name") or "").strip()

    def _start_editing(self, slot):
        if self.profiles[slot - 1].get("_load_error"):
            self.editing_slot = None
            self.status_message = self._unavailable_message(slot)
            return
        self.status_message = (
            self._recovered_message(slot) if profile_manager.was_profile_recovered(slot) else ""
        )
        self.editing_slot = slot
        self.input_text = self._profile_name_for_slot(slot)

    def _unavailable_message(self, slots):
        return self._get_text(
            "ProfileUnavailableMessage",
            "Профиль {slots} недоступен. Восстановление не удалось. Исходные файлы сохранены. Выберите другой профиль.",
        ).format(slots=slots)

    def _recovered_message(self, slots):
        return self._get_text(
            "ProfileRecoveredMessage",
            "Профиль {slots} восстановлен из резервной копии. Последнее сохранение могло быть потеряно.",
        ).format(slots=slots)

    def _confirm_selection(self):
        if self.editing_slot is None:
            return None
        try:
            profile = profile_manager.select_profile(self.editing_slot, self.input_text)
        except profile_manager.ProfileLoadError:
            self.status_message = self._unavailable_message(self.editing_slot)
            self.profiles = profile_manager.list_profiles()
            self.editing_slot = None
            return None
        except OSError:
            self.status_message = self._get_text(
                "ProfileSaveFailed", "Не удалось сохранить профиль. Проверьте доступ к папке Profiles и свободное место.",
            )
            return None
        return {"slot": int(profile["slot"]), "name": profile.get("name", "")}

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back" if self.selected_slot else None
                if self.editing_slot is not None:
                    if event.key == pygame.K_RETURN:
                        return self._confirm_selection()
                    if event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(self.input_text) < 24:
                        self.input_text += event.unicode
                    continue

                if pygame.K_1 <= event.key <= pygame.K_4:
                    self._start_editing(event.key - pygame.K_0)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                for index, rect in enumerate(self.button_rects):
                    if rect.collidepoint(mouse_pos):
                        self._start_editing(index + 1)
                        break
                if self.editing_slot is not None and self.input_rect.collidepoint(mouse_pos):
                    continue

        return None

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 90))
        self.screen.blit(dim, (0, 0))

        if self.window_image:
            self.screen.blit(self.window_image, self.window_rect.topleft)
        else:
            pygame.draw.rect(self.screen, WHITE, self.window_rect)
            pygame.draw.rect(self.screen, PAPER_COLOR, self.window_rect, 4)

        title = self._render_text_cached(self.font_title, self._get_text("Profile", "Profile"), PAPER_COLOR)
        title_rect = title.get_rect(center=(self.window_rect.centerx, self.window_rect.y + 92))
        self.screen.blit(title, title_rect)

        for index, rect in enumerate(self.button_rects):
            slot = index + 1
            is_selected = slot == self.selected_slot
            is_editing = slot == self.editing_slot
            color = LIGHT_GOLD if is_editing else ((235, 220, 165) if is_selected else (228, 213, 176))
            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            pygame.draw.rect(self.screen, PAPER_COLOR, rect, 3, border_radius=6)

            number = self._render_text_cached(self.font_medium, str(slot), PAPER_COLOR)
            number_rect = number.get_rect(midleft=(rect.x + 24, rect.centery))
            self.screen.blit(number, number_rect)

            name = self._profile_name_for_slot(slot) or self._get_text("Profile", "Profile")
            if self.profiles[index].get("_load_error"):
                name = self._get_text("ProfileUnavailable", "Недоступен")
            name_surface = self._render_text_cached(self.font_small, name, PAPER_COLOR)
            max_name_width = rect.width - 95
            if name_surface.get_width() > max_name_width:
                clipped = str(name)[:18] + "..."
                name_surface = self._render_text_cached(self.font_small, clipped, PAPER_COLOR)
            name_rect = name_surface.get_rect(midleft=(rect.x + 86, rect.centery))
            self.screen.blit(name_surface, name_rect)

        if self.editing_slot is not None:
            pygame.draw.rect(self.screen, (244, 232, 196), self.input_rect, border_radius=6)
            pygame.draw.rect(self.screen, PAPER_COLOR, self.input_rect, 3, border_radius=6)
            text = self.input_text
            if (pygame.time.get_ticks() // 450) % 2 == 0:
                text += "|"
            input_surface = self._render_text_cached(self.font_medium, text, PAPER_COLOR)
            input_rect = input_surface.get_rect(midleft=(self.input_rect.x + 18, self.input_rect.centery))
            self.screen.blit(input_surface, input_rect)

        for index, line in enumerate(wrap_text(self.status_message, self.status_font, self.window_rect.width - 60)):
            surface = self._render_text_cached(self.status_font, line, PAPER_COLOR)
            self.screen.blit(surface, (self.window_rect.x + 30, self.window_rect.bottom - 70 + index * 26))

        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()
            if result == "quit":
                pygame.quit()
                sys.exit()
            if result == "back":
                return "back"
            if isinstance(result, dict):
                return result
            self.draw()
            self.clock.tick(FPS)
