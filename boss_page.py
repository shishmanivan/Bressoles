import os
import sys

import pygame

from asset_loaders import load_scaled_background, load_scaled_image
from shared_utils import _clamp_dt_seconds, clamp_popup_y, move_towards, wrap_text


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

BLACK = (0, 0, 0)
PAPER_COLOR = (83, 76, 70)

ANIMATION_FRAME_SIZE = (100, 100)
ANIMATION_SCALE_OVERRIDES = {
    "9_Laffitte": 0.95,
}
_boss_animation_frames_cache = {}
POPUP_FONT_MAX_SIZE = 24
POPUP_FONT_MIN_SIZE = 18
POPUP_TEXT_TOP = 120
POPUP_TEXT_BOTTOM_PADDING = 14
POPUP_TEXT_WIDTH = 200


def normalize_boss_animation_frame(frame_image, base_name):
    scale = ANIMATION_SCALE_OVERRIDES.get(base_name, 1.0)
    if scale == 1.0:
        return pygame.transform.smoothscale(frame_image, ANIMATION_FRAME_SIZE).convert_alpha()

    target_size = (
        max(1, int(round(ANIMATION_FRAME_SIZE[0] * scale))),
        max(1, int(round(ANIMATION_FRAME_SIZE[1] * scale))),
    )
    scaled = pygame.transform.smoothscale(frame_image, target_size).convert_alpha()
    canvas = pygame.Surface(ANIMATION_FRAME_SIZE, pygame.SRCALPHA)
    canvas.blit(
        scaled,
        (
            (ANIMATION_FRAME_SIZE[0] - target_size[0]) // 2,
            (ANIMATION_FRAME_SIZE[1] - target_size[1]) // 2,
        ),
    )
    return canvas


def build_boss_popup_text_layout(font_path, popup_height, condition_text, reward_header, reward_text):
    last_layout = None
    for font_size in range(POPUP_FONT_MAX_SIZE, POPUP_FONT_MIN_SIZE - 1, -1):
        font = pygame.font.Font(font_path, font_size)
        line_height = font.get_height() + 4
        condition_lines = wrap_text(condition_text, font, POPUP_TEXT_WIDTH)
        reward_lines = wrap_text(reward_text, font, POPUP_TEXT_WIDTH) if reward_text else []

        condition_y = POPUP_TEXT_TOP
        cursor_y = condition_y + len(condition_lines) * line_height
        header_y = None
        reward_y = None
        if reward_lines:
            cursor_y += 10
            header_y = cursor_y
            cursor_y += line_height
            reward_y = cursor_y
            cursor_y += len(reward_lines) * line_height

        last_layout = {
            "font": font,
            "font_size": font_size,
            "line_height": line_height,
            "condition_lines": condition_lines,
            "condition_y": condition_y,
            "header_y": header_y,
            "reward_lines": reward_lines,
            "reward_y": reward_y,
            "content_bottom": cursor_y,
        }
        if cursor_y <= popup_height - POPUP_TEXT_BOTTOM_PADDING:
            return last_layout
    return last_layout


def _load_boss_animation_frames(boss_filename):
    cached = _boss_animation_frames_cache.get(boss_filename)
    if cached is not None:
        return list(cached)

    base_name = os.path.splitext(boss_filename)[0]
    boss_folder = os.path.join("Bosses", base_name)
    if not os.path.isdir(boss_folder):
        matching_folders = sorted(
            folder_name
            for folder_name in os.listdir("Bosses")
            if os.path.isdir(os.path.join("Bosses", folder_name))
            and folder_name.lower().endswith(f"_{base_name.lower()}")
        )
        if matching_folders:
            boss_folder = os.path.join("Bosses", matching_folders[0])

    animation_frames = []
    if os.path.isdir(boss_folder):
        for frame_num in range(7):
            frame_filename = f"{base_name}{frame_num}.png"
            frame_path = os.path.join(boss_folder, frame_filename)
            if not os.path.exists(frame_path):
                matching_frames = sorted(
                    filename
                    for filename in os.listdir(boss_folder)
                    if filename.lower().endswith(f"{frame_num}.png")
                )
                if matching_frames:
                    frame_path = os.path.join(boss_folder, matching_frames[0])
            if os.path.exists(frame_path):
                frame_image = pygame.image.load(frame_path).convert_alpha()
                animation_frames.append(normalize_boss_animation_frame(frame_image, base_name))
            else:
                print(f"WARNING: Animation frame not found: {frame_path}")
    else:
        print(f"WARNING: Boss animation folder not found: {boss_folder}")

    cached_frames = tuple(animation_frames)
    _boss_animation_frames_cache[boss_filename] = cached_frames
    return list(cached_frames)


class BossPage:
    def __init__(
        self,
        screen,
        font_path,
        level_number,
        defeated_count=0,
        last_defeated_rect=None,
        saved_lines=None,
        defeated_bosses=None,
        lang_dict=None,
        level_boss_rounds=None,
        load_rounds_config=None,
        get_bosses_required=None,
        get_boss_number_from_filename=None,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.level_number = level_number
        self.defeated_count = defeated_count
        self.last_defeated_rect = last_defeated_rect
        self.saved_lines = list(saved_lines) if saved_lines else []
        self.defeated_bosses = list(defeated_bosses) if defeated_bosses else []
        self.clicked_boss_filename = None
        self.boss_image_cache = {}
        self.clicked_boss_rect = None
        self.lang = lang_dict or {}
        self.level_boss_rounds = level_boss_rounds or {}
        self._load_rounds_config = load_rounds_config
        self._get_bosses_required = get_bosses_required
        self._get_boss_number_from_filename = get_boss_number_from_filename

        back3_path = os.path.join("UI", "Back3.png")
        self.background = load_scaled_background(
            back3_path,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            fallback_surface=None,
            warning_message="WARNING: Back3.png not found:",
        )

        koordinates_path = os.path.join("RoundPage", "Koordinates.png")
        self.koordinates = load_scaled_image(
            koordinates_path,
            target_size=(SCREEN_WIDTH, SCREEN_HEIGHT),
            warning_message="WARNING: Koordinates.png not found:",
        )

        round_index = self.defeated_count if self.defeated_count >= 0 else 0
        bosses_for_round = self.level_boss_rounds.get(self.level_number, [[]])
        if round_index >= len(bosses_for_round):
            round_index = len(bosses_for_round) - 1 if bosses_for_round else 0
        self.current_boss_filenames = bosses_for_round[round_index] if bosses_for_round else []

        self.bosses = []
        self.boss_rects = []
        self.boss_animation_frames = []
        self.boss_base_names = []

        self.animation_sequence = [0, 1, 2, 3, 2, 1, 0, 4, 5, 6, 5, 4]
        self.animation_frame_duration = 100
        self.boss_hover_states = {}

        popup_path = os.path.join("Bosses", "PopUp.png")
        self.popup_image = load_scaled_image(
            popup_path,
            target_size=(250, 375),
            warning_message="WARNING: PopUp.png not found:",
        )

        self.popup_hidden_y = -float(self.popup_image.get_height()) - 50.0 if self.popup_image else -400.0
        self.popup_y = float(self.popup_hidden_y)
        self.popup_x = 0
        self.popup_target_y = float(self.popup_hidden_y)
        self.popup_speed_pps = 1400.0
        self._popup_last_tick = pygame.time.get_ticks()
        self.current_hovered_boss_index = None
        self.popup_boss_index = None

        self.popup_font = pygame.font.Font(font_path, 24)
        self.popup_reward_header = self._get_text("PopUpReward", "PopUpReward")

        rounds_config = self._load_rounds_config() if self._load_rounds_config else {}
        self.bosses_required = (
            self._get_bosses_required(self.level_number, rounds_config) if self._get_bosses_required else 1
        )

        self.boss_texts = {}
        self.boss_rewards = {}
        self.boss_popup_text_layouts = {}

        for boss_idx, boss_filename in enumerate(self.current_boss_filenames):
            is_last_boss = self.defeated_count == self.bosses_required - 1
            boss_number = self._get_boss_number_from_filename(boss_filename) if self._get_boss_number_from_filename else None
            if boss_number:
                text_key = f"Boss{boss_number}Text"
                self.boss_texts[boss_idx] = self._get_text(text_key, text_key)
                if is_last_boss:
                    self.boss_rewards[boss_idx] = self._get_text("LastBossReward", "LastBossReward")
                else:
                    reward_key = f"Boss{boss_number}Reward"
                    self.boss_rewards[boss_idx] = self._get_text(reward_key, reward_key)

        popup_height = self.popup_image.get_height() if self.popup_image else 375
        for boss_idx, condition_text in self.boss_texts.items():
            self.boss_popup_text_layouts[boss_idx] = build_boss_popup_text_layout(
                font_path,
                popup_height,
                condition_text,
                self.popup_reward_header,
                self.boss_rewards.get(boss_idx, ""),
            )

        pen_sound_path = os.path.join("Sounds", "Pen.mp3")
        if os.path.exists(pen_sound_path):
            self.pen_sound = pygame.mixer.Sound(pen_sound_path)
        else:
            print(f"WARNING: Pen.mp3 not found at {pen_sound_path}")
            self.pen_sound = None

        self.line_color = (110, 90, 70)
        self.line_width = 10
        self.current_line = None
        self.last_hovered_boss = None

        if self.current_boss_filenames:
            for boss_filename in self.current_boss_filenames:
                boss_path = os.path.join("Bosses", boss_filename)
                if os.path.exists(boss_path):
                    boss_image = load_scaled_image(boss_path, target_size=(100, 100))
                    self.bosses.append(boss_image)

                    base_name = os.path.splitext(boss_filename)[0]
                    self.boss_base_names.append(base_name)
                    self.boss_animation_frames.append(_load_boss_animation_frames(boss_filename))
                else:
                    print(f"WARNING: Boss file not found: {boss_path}")
                    self.bosses.append(None)
                    self.boss_base_names.append(None)
                    self.boss_animation_frames.append([])

        if saved_lines and isinstance(saved_lines, dict) and saved_lines.get("defeated_bosses"):
            self.defeated_bosses = list(saved_lines.get("defeated_bosses"))
        elif hasattr(self, "saved_defeated_bosses"):
            self.defeated_bosses = list(self.saved_defeated_bosses)

        self.boss_vertical_spacing = 150
        start_x = 350
        start_y = SCREEN_HEIGHT - 400

        if self.defeated_count > 0 and self.last_defeated_rect:
            anchor_cx, anchor_cy = self.last_defeated_rect.centerx, self.last_defeated_rect.centery
            positions = []
            if len(self.bosses) >= 1:
                positions.append((anchor_cx + 200, anchor_cy - self.boss_vertical_spacing))
            if len(self.bosses) >= 2:
                prev_cx, prev_cy = positions[0]
                positions.append((prev_cx, prev_cy - self.boss_vertical_spacing))

            for i, boss_image in enumerate(self.bosses):
                cx, cy = positions[i]
                self.boss_rects.append(pygame.Rect(cx - 50, cy - 50, 100, 100))

            self.fixed_line_start_x = anchor_cx
            self.fixed_line_start_y = anchor_cy
        else:
            for i, boss_image in enumerate(self.bosses):
                boss_x = start_x
                boss_y = start_y - (i * self.boss_vertical_spacing)
                self.boss_rects.append(pygame.Rect(boss_x, boss_y, 100, 100))

            if len(self.boss_rects) > 0:
                first_boss_rect = self.boss_rects[0]
                self.fixed_line_start_x = first_boss_rect.centerx - 165
                self.fixed_line_start_y = first_boss_rect.centery + 132
            else:
                self.fixed_line_start_x = 350 + 50 - 165
                self.fixed_line_start_y = SCREEN_HEIGHT - 400 + 50 + 132

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang.get(key, default)

    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()

        hovered_boss = None
        for i, boss_rect in enumerate(self.boss_rects):
            if boss_rect.collidepoint(mouse_pos):
                hovered_boss = i
                break

        if hovered_boss is not None:
            boss_rect = self.boss_rects[hovered_boss]
            desired_y = float(boss_rect.y - 250)
            self.popup_target_y = clamp_popup_y(desired_y, self.popup_image, SCREEN_HEIGHT, margin=10.0)
            self.popup_x = boss_rect.x + 100
            self.current_hovered_boss_index = hovered_boss
            self.popup_boss_index = hovered_boss

            line_start_x = self.fixed_line_start_x
            line_start_y = self.fixed_line_start_y
            line_end_x = boss_rect.centerx
            line_end_y = boss_rect.centery
            self.current_line = (line_start_x, line_start_y, line_end_x, line_end_y)

            if self.last_hovered_boss != hovered_boss:
                if self.pen_sound:
                    self.pen_sound.play()
                self.last_hovered_boss = hovered_boss
        else:
            self.popup_target_y = float(getattr(self, "popup_hidden_y", -400.0))
            self.current_hovered_boss_index = None
            self.current_line = None
            self.last_hovered_boss = None

        for i in range(len(self.boss_rects)):
            if i == hovered_boss:
                if i not in self.boss_hover_states:
                    self.boss_hover_states[i] = {
                        "sequence_index": 0,
                        "last_frame_time": pygame.time.get_ticks(),
                    }
            else:
                if i in self.boss_hover_states:
                    del self.boss_hover_states[i]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "back"

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, boss_rect in enumerate(self.boss_rects):
                    if boss_rect.collidepoint(mouse_pos):
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        self.clicked_boss_rect = boss_rect.copy()
                        if i < len(self.current_boss_filenames):
                            self.clicked_boss_filename = self.current_boss_filenames[i]
                        return f"boss_{self.level_number}_{i}"

        return None

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

        if self.koordinates:
            self.screen.blit(self.koordinates, (0, 0))

        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_popup_last_tick", now)) / 1000.0
        self._popup_last_tick = now
        dt = _clamp_dt_seconds(dt)
        max_delta = float(getattr(self, "popup_speed_pps", 0.0)) * dt
        self.popup_y = move_towards(float(self.popup_y), float(self.popup_target_y), max_delta)

        for line in self.saved_lines:
            if line:
                start_x, start_y, end_x, end_y = line
                pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)

        if self.current_line:
            start_x, start_y, end_x, end_y = self.current_line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)

        for defeated in self.defeated_bosses:
            filename = defeated.get("filename")
            rect = defeated.get("rect")
            if not filename or not rect:
                continue
            if filename in self.boss_image_cache:
                img = self.boss_image_cache[filename]
            else:
                path = os.path.join("Bosses", filename)
                img = None
                if os.path.exists(path):
                    img = load_scaled_image(path, target_size=(100, 100))
                self.boss_image_cache[filename] = img
            if img:
                self.screen.blit(img, rect.topleft)

        current_time = pygame.time.get_ticks()
        for i, (boss_image, boss_rect) in enumerate(zip(self.bosses, self.boss_rects)):
            if boss_image is None:
                continue
            if i in self.boss_hover_states and len(self.boss_animation_frames[i]) > 0:
                hover_state = self.boss_hover_states[i]
                time_since_last_frame = current_time - hover_state["last_frame_time"]
                if time_since_last_frame >= self.animation_frame_duration:
                    hover_state["sequence_index"] = (hover_state["sequence_index"] + 1) % len(self.animation_sequence)
                    hover_state["last_frame_time"] = current_time

                frame_index = self.animation_sequence[hover_state["sequence_index"]]
                if frame_index < len(self.boss_animation_frames[i]):
                    self.screen.blit(self.boss_animation_frames[i][frame_index], boss_rect.topleft)
                else:
                    self.screen.blit(boss_image, boss_rect.topleft)
            else:
                self.screen.blit(boss_image, boss_rect.topleft)

        if self.popup_image and self.popup_y > -self.popup_image.get_height():
            popup_y_draw = int(round(self.popup_y))
            self.screen.blit(self.popup_image, (self.popup_x, popup_y_draw))

            if self.popup_boss_index is not None and self.popup_boss_index in self.boss_texts:
                layout = self.boss_popup_text_layouts.get(self.popup_boss_index)
                font = layout["font"] if layout else self.popup_font
                lines = layout["condition_lines"] if layout else wrap_text(
                    self.boss_texts[self.popup_boss_index], font, POPUP_TEXT_WIDTH
                )
                text_start_x = self.popup_x + 15
                text_start_y = popup_y_draw + (layout["condition_y"] if layout else POPUP_TEXT_TOP)
                line_height = layout["line_height"] if layout else font.get_height() + 4

                for i, line in enumerate(lines):
                    text_surface = font.render(line, True, PAPER_COLOR)
                    self.screen.blit(text_surface, (text_start_x, text_start_y + i * line_height))

                if self.popup_boss_index in self.boss_rewards:
                    reward_header_y = popup_y_draw + layout["header_y"]
                    header_surface = font.render(self.popup_reward_header, True, PAPER_COLOR)
                    self.screen.blit(header_surface, (text_start_x, reward_header_y))
                    reward_lines = layout["reward_lines"]
                    reward_start_y = popup_y_draw + layout["reward_y"]

                    for i, line in enumerate(reward_lines):
                        reward_surface = font.render(line, True, PAPER_COLOR)
                        self.screen.blit(reward_surface, (text_start_x, reward_start_y + i * line_height))
        else:
            if self.popup_boss_index is not None:
                self.popup_boss_index = None

        pygame.display.flip()

    def run(self):
        while True:
            result = self.handle_input()

            if result == "quit":
                pygame.quit()
                sys.exit()

            if result == "back":
                return "back"

            if result and result.startswith("boss_"):
                return result

            self.draw()
            self.clock.tick(FPS)
