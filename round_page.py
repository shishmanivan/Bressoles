import sys

import pygame

import game_state
from boss_effects import parse_boss_functionality_spec
from boss_logic import resolve_boss_number
from round_page_assets import (
    build_round_button_base_rects,
    load_boss_icon_assets,
    load_round_page_static_assets,
)
from round_page_helpers import (
    build_completed_round_lines,
    refresh_button_goals_for_round,
    resolve_boss_goal,
    resolve_boss_reward_text,
    resolve_boss_selection,
    resolve_initial_button_goals,
)
from round_reward_preview import (
    load_reward_card_preview,
    load_round_reward_assets,
)
from shared_utils import _clamp_dt_seconds, clamp_popup_y, move_towards, wrap_text


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

BLACK = (0, 0, 0)
PAPER_COLOR = (83, 76, 70)


class RoundPage:
    def __init__(
        self,
        screen,
        font_path,
        level_number,
        boss_index,
        boss_filename=None,
        test_mode=False,
        defeated_count=0,
        lang_dict=None,
        load_rounds_config=None,
        load_levels_config=None,
        load_boss_rewards=None,
        load_rewards_config=None,
        get_level2_goal=None,
        get_level3_goal=None,
        get_level4_goal=None,
        get_boss_number_from_index=None,
        get_boss_number_from_filename=None,
        apper_goal_boost=None,
        reward_token_random_red=None,
        round_progress=None,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.level_number = level_number
        self.boss_index = boss_index
        self.boss_filename = boss_filename
        self.test_mode = test_mode
        self.font_path = font_path
        self.defeated_count = defeated_count
        self.lang = lang_dict or {}

        self._load_rounds_config = load_rounds_config
        self._load_levels_config = load_levels_config
        self._load_boss_rewards = load_boss_rewards
        self._load_rewards_config = load_rewards_config
        self._get_level2_goal = get_level2_goal
        self._get_level3_goal = get_level3_goal
        self._get_level4_goal = get_level4_goal
        self._get_boss_number_from_index = get_boss_number_from_index
        self._get_boss_number_from_filename = get_boss_number_from_filename
        self._apper_goal_boost = apper_goal_boost
        self.reward_token_random_red = reward_token_random_red

        self.boss_number = resolve_boss_number(
            self.level_number,
            self.boss_index,
            self.defeated_count,
            self.boss_filename,
        )
        self.is_apper_boss = self.boss_number == 4

        round_page_assets = load_round_page_static_assets()
        self.background = round_page_assets["background"]
        self.koordinates = round_page_assets["koordinates"]
        self.button_e = round_page_assets["button_e"]
        self.button_m = round_page_assets["button_m"]
        self.button_h = round_page_assets["button_h"]
        self.napoleondor_image = round_page_assets["napoleondor_image"]

        self.rounds_config = self._load_rounds_config()
        level_cfg = self.rounds_config.get(self.level_number, {})
        levels_cfg = self._load_levels_config()

        self.boss_selection = resolve_boss_selection(self.level_number, self.defeated_count)

        rounds_cfg_value = (levels_cfg.get(self.level_number, {}) or {}).get("Rounds")
        if rounds_cfg_value is None:
            rounds_cfg_value = level_cfg.get("Rounds")
        if self.level_number == 6 and rounds_cfg_value == 0:
            self.rounds_required = 0
        else:
            self.rounds_required = rounds_cfg_value if rounds_cfg_value and rounds_cfg_value > 0 else 1

        if self.boss_number:
            boss_rewards = self._load_boss_rewards()
            boss_entry = boss_rewards.get(self.boss_number)
            if boss_entry and isinstance(boss_entry, dict):
                func_string = boss_entry.get("Functionalities", "").strip()
                if func_string:
                    self._apply_level_rounds_functionality(func_string)

        round_progress = round_progress or {}
        self.completed_rounds = {
            int(round_num)
            for round_num in (round_progress.get("completed_rounds") or [])
            if str(round_num).isdigit()
        }
        self.round_selections = {}
        for round_key, selection in (round_progress.get("round_selections") or {}).items():
            try:
                round_num = int(round_key)
            except (TypeError, ValueError):
                continue
            if isinstance(selection, dict):
                key = selection.get("key")
            else:
                key = selection
            if key in ("e", "m", "h"):
                self.round_selections[round_num] = {"key": key}
        self.Goal = None
        self.last_selected_round = None

        self.base_button_goals = resolve_initial_button_goals(
            self.level_number,
            level_cfg,
            self.boss_selection,
            self.defeated_count,
            self.is_apper_boss,
            self._get_level2_goal,
            self._get_level3_goal,
            self._get_level4_goal,
            self._apper_goal_boost,
        )
        self.button_goals = self._build_display_button_goals()

        bosses_cfg_value = (levels_cfg.get(self.level_number, {}) or {}).get("Bosses")
        if bosses_cfg_value is None:
            bosses_cfg_value = level_cfg.get("Bosses")
        self.bosses_required = bosses_cfg_value if bosses_cfg_value and bosses_cfg_value > 0 else 1

        if self.level_number != 2:
            if self.button_goals["e"] is None:
                self.button_e = None
            if self.button_goals["m"] is None:
                self.button_m = None
        if self.button_goals["h"] is None:
            self.button_h = None

        self.button_e_rect = None
        self.button_m_rect = None
        self.button_h_rect = None
        self.button_base_rects = build_round_button_base_rects(
            self.button_goals,
            {"e": self.button_e, "m": self.button_m, "h": self.button_h},
        )
        self._refresh_button_rects()

        self.popup_image = round_page_assets["popup_image"]
        self.popup_width = round_page_assets["popup_width"]
        self.popup_hidden_y = -float(self.popup_image.get_height()) - 50.0 if self.popup_image else -450.0
        self.popup_y = float(self.popup_hidden_y)
        self.popup_x = 0
        self.popup_target_y = float(self.popup_hidden_y)
        self.popup_speed_pps = 1400.0
        self._popup_last_tick = pygame.time.get_ticks()
        self.popup_button = None

        self.popup_font = pygame.font.Font(font_path, 24)
        self.popup_round_text = self._get_text("PopUpRound", "PopUpRound")
        self.popup_reward_text = self._get_text("PopUpReward", "PopUpReward")

        self.boss_text = resolve_boss_reward_text(
            self.boss_filename,
            self.level_number,
            self.boss_index,
            self.defeated_count,
            self.bosses_required,
            self._get_boss_number_from_filename,
            self._get_boss_number_from_index,
            self._get_text,
        )

        self.rewards = dict(self._load_rewards_config())

        round_reward_assets = load_round_reward_assets()
        self.random_drop_image = round_reward_assets["random_drop_image"]
        self.random_red_image = round_reward_assets["random_red_image"]
        self.random_silver_image = round_reward_assets["random_silver_image"]
        self.card_base_mapping = round_reward_assets["card_base_mapping"]
        self.card_actions = round_reward_assets["card_actions"]
        self.card_turns = round_reward_assets["card_turns"]
        self.reward_card_images = {}
        self._scaled_reward_surface_cache = {}

        self.pen_sound = round_page_assets["pen_sound"]

        self.line_color = (100, 82, 64)
        self.line_width = 10
        self.current_line = None
        self.boss_current_line = None
        self.saved_lines = [
            tuple(line)
            for line in (round_progress.get("saved_lines") or [])
            if isinstance(line, (list, tuple)) and len(line) == 4
        ]
        rebuilt_lines = build_completed_round_lines(
            self.completed_rounds,
            self.round_selections,
            self.button_base_rects,
            self._get_round_offset,
            origin=(235, SCREEN_HEIGHT - 218),
        )
        if len(self.saved_lines) < len(rebuilt_lines):
            self.saved_lines = rebuilt_lines
        self.last_hovered_button = None
        self.round_button_hover_scale = 0.96
        self._round_button_hover_images = {}

        self.hovered_button = None
        self.last_selected_round = None

        self.boss_icon = None
        self.boss_icon_rect = None
        self.boss_animation_frames = []
        self.boss_hover_state = None
        self.animation_sequence = [0, 1, 2, 3, 2, 1, 0, 4, 5, 6, 5, 4]
        self.animation_frame_duration = 100

        self.boss_goals = {
            (1, 0): 60,
        }

        self._load_boss_icon_if_needed()

    def export_round_progress(self):
        return {
            "completed_rounds": sorted(int(round_num) for round_num in self.completed_rounds),
            "round_selections": {
                str(round_num): {"key": selection.get("key")}
                for round_num, selection in sorted(self.round_selections.items())
                if selection.get("key") in ("e", "m", "h")
            },
            "saved_lines": [list(line) for line in self.saved_lines if line],
        }

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang.get(key, default)

    def _get_round_offset(self, round_num):
        if not round_num or round_num <= 1:
            return 0, 0
        shift = round_num - 1
        offset_x = 150 * shift
        offset_y = -100 * shift
        try:
            tops = []
            for key in ("h", "m", "e"):
                base_rect = self.button_base_rects.get(key)
                if base_rect:
                    tops.append(base_rect.move(offset_x, offset_y).top)
            if tops:
                min_top = min(tops)
                if min_top < 0:
                    offset_y += -min_top
        except Exception:
            pass
        return offset_x, offset_y

    def _get_button_image_for_key(self, key):
        if key == "e":
            return self.button_e
        if key == "m":
            return self.button_m
        if key == "h":
            return self.button_h
        return None

    def _draw_round_button(self, key, rect, shrink_on_hover=False):
        img = self._get_button_image_for_key(key)
        if not img or not rect:
            return

        if shrink_on_hover and key == self.hovered_button:
            cache_key = (key, img.get_width(), img.get_height(), self.round_button_hover_scale)
            hover_img = self._round_button_hover_images.get(cache_key)
            if hover_img is None:
                hover_size = (
                    max(1, int(img.get_width() * self.round_button_hover_scale)),
                    max(1, int(img.get_height() * self.round_button_hover_scale)),
                )
                hover_img = pygame.transform.smoothscale(img, hover_size).convert_alpha()
                self._round_button_hover_images[cache_key] = hover_img
            hover_rect = hover_img.get_rect(center=rect.center)
            self.screen.blit(hover_img, hover_rect.topleft)
            return

        self.screen.blit(img, rect.topleft)

    def _refresh_button_goals(self):
        if self.level_number in (2, 3, 4, 5, 8):
            current_round = self.get_current_active_round()
            if current_round is not None:
                self.base_button_goals = refresh_button_goals_for_round(
                    self.level_number,
                    current_round,
                    self.boss_selection,
                    self.defeated_count,
                    self.is_apper_boss,
                    self.base_button_goals,
                    self._get_level2_goal,
                    self._get_level3_goal,
                    self._get_level4_goal,
                    self._apper_goal_boost,
                )
        self.button_goals = self._build_display_button_goals()

    def _build_display_button_goals(self):
        debt = game_state.get_insurance_goal_debt()
        return {
            key: (
                game_state.apply_loan_goal_modifier(
                    game_state.apply_bailout_goal_modifier(value),
                    self.level_number,
                    self.defeated_count,
                )
                + debt
                if value is not None
                else None
            )
            for key, value in self.base_button_goals.items()
        }

    def _refresh_button_rects(self):
        current_round = self.get_current_active_round()
        if current_round is None:
            current_round = self.rounds_required
        offset_x, offset_y = self._get_round_offset(current_round)

        def shift_rect(base_rect):
            if base_rect is None:
                return None
            return base_rect.move(offset_x, offset_y)

        self.button_e_rect = shift_rect(self.button_base_rects.get("e"))
        self.button_m_rect = shift_rect(self.button_base_rects.get("m"))
        self.button_h_rect = shift_rect(self.button_base_rects.get("h"))

    def _get_prev_selection_rect(self):
        if not self.round_selections:
            return None
        prev_round = max(self.round_selections.keys())
        sel = self.round_selections.get(prev_round)
        if sel:
            key = sel.get("key")
            base_rect = self.button_base_rects.get(key)
            if base_rect:
                offset_x, offset_y = self._get_round_offset(prev_round)
                return base_rect.move(offset_x, offset_y)
        return None

    def _load_reward_card(self, card_number):
        return load_reward_card_preview(
            card_number,
            self.reward_card_images,
            self.random_red_image,
            self.random_silver_image,
            self.card_base_mapping,
            self.card_actions,
            self.card_turns,
            self.font_path,
            self.reward_token_random_red,
            paper_color=PAPER_COLOR,
        )

    def _get_scaled_reward_surface(self, surface, size):
        if surface is None:
            return None
        size = (int(size[0]), int(size[1]))
        cache_key = (id(surface), size)
        scaled = self._scaled_reward_surface_cache.get(cache_key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(surface, size).convert_alpha()
            self._scaled_reward_surface_cache[cache_key] = scaled
        return scaled

    def _get_reward_preview_surface(self, reward_list):
        reward_list = reward_list if isinstance(reward_list, list) else ([reward_list] if reward_list is not None else [])
        if not reward_list:
            return None
        if self.reward_token_random_red in reward_list:
            return self.random_red_image
        if len(reward_list) > 1 and any(isinstance(card, int) and 10 <= card <= 19 for card in reward_list):
            return self.random_drop_image
        return self._load_reward_card(reward_list[0])

    def _draw_reward_preview_cards(self, reward_data, card_y):
        surfaces = []
        for reward_key in ("reward1", "reward2", "reward3"):
            surface = self._get_reward_preview_surface(reward_data.get(reward_key))
            if surface is not None:
                surfaces.append(surface)
        if not surfaces:
            return

        scale = 0.75
        spacing = 10
        scaled_surfaces = []
        total_width = 0
        for surface in surfaces:
            width = int(surface.get_width() * scale)
            height = int(surface.get_height() * scale)
            scaled = self._get_scaled_reward_surface(surface, (width, height))
            if scaled is None:
                continue
            scaled_surfaces.append((scaled, width))
            total_width += width
        if not scaled_surfaces:
            return
        total_width += spacing * (len(scaled_surfaces) - 1)

        card_x = self.popup_x + (self.popup_width - total_width) // 2
        for surface, width in scaled_surfaces:
            self.screen.blit(surface, (card_x, card_y))
            card_x += width + spacing

    def _get_popup_napoleondor_reward(self):
        if self.popup_button == "boss":
            base_reward = game_state.get_boss_victory_napoleondor_reward(self.level_number)
        elif self.popup_button in ("e", "m", "h"):
            base_reward = game_state.get_round_victory_napoleondor_reward(
                self.level_number,
                self.popup_button,
                self.boss_number,
            )
        else:
            return 0
        if base_reward <= 0:
            return 0
        return game_state.get_victory_napoleondor_reward(base_reward)

    def _draw_popup_napoleondor_reward(self, amount, x, y):
        amount_value = float(amount or 0)
        amount_text = str(int(amount_value)) if amount_value.is_integer() else f"{amount_value:g}"
        coin_x = x
        if self.napoleondor_image:
            coin_rect = self.napoleondor_image.get_rect(midleft=(x, y + self.popup_font.get_height() // 2))
            self.screen.blit(self.napoleondor_image, coin_rect.topleft)
            coin_x = coin_rect.right + 8
        amount_surface = self.popup_font.render(amount_text, True, PAPER_COLOR)
        self.screen.blit(amount_surface, (coin_x, y))

    def _load_boss_icon_if_needed(self):
        self._refresh_button_rects()
        level_rounds = self.rounds_required
        if level_rounds < 0:
            return
        completed_count = len(self.completed_rounds)
        fallback_anchor_rect = self.button_e_rect or self.button_m_rect or self.button_h_rect
        if level_rounds == 0 and fallback_anchor_rect is None:
            fallback_anchor_rect = pygame.Rect(234, 831, 2, 2)
        self.boss_icon, self.boss_icon_rect, self.boss_animation_frames = load_boss_icon_assets(
            self.level_number,
            self.boss_index,
            self.boss_filename,
            completed_count,
            level_rounds,
            self._get_prev_selection_rect(),
            fallback_anchor_rect,
        )

    def _apply_level_rounds_functionality(self, func_string: str):
        if self.level_number == 6:
            return
        for effect in parse_boss_functionality_spec(func_string):
            if effect.kind != "assignment" or effect.target != "LevelRounds":
                continue
            if effect.operator == "+":
                self.rounds_required += effect.value
            elif effect.operator == "-":
                self.rounds_required -= effect.value
            elif effect.value > 0:
                self.rounds_required = effect.value
            if self.level_number == 2:
                self.rounds_required = max(1, min(self.rounds_required, 4))

    def mark_round_completed(self, round_num):
        if round_num is None:
            round_num = self.get_current_active_round()
        if round_num is not None and round_num <= self.rounds_required:
            self.completed_rounds.add(round_num)
        self._load_boss_icon_if_needed()

    def is_round_active(self, round_num):
        if round_num > self.rounds_required:
            return False
        return round_num not in self.completed_rounds

    def get_current_active_round(self):
        for round_num in range(1, self.rounds_required + 1):
            if self.is_round_active(round_num):
                return round_num
        return None

    def handle_input(self):
        self._refresh_button_rects()
        self._refresh_button_goals()
        mouse_pos = pygame.mouse.get_pos()

        current_active_round = self.get_current_active_round()
        all_rounds_completed = current_active_round is None

        self.hovered_button = None
        hovered_boss = False
        can_play_round = current_active_round is not None

        if can_play_round and self.button_e_rect and self.button_goals.get("e") is not None and self.button_e_rect.collidepoint(mouse_pos):
            self.hovered_button = "e"
        elif can_play_round and self.button_m_rect and self.button_goals.get("m") is not None and self.button_m_rect.collidepoint(mouse_pos):
            self.hovered_button = "m"
        elif can_play_round and self.button_h_rect and self.button_goals.get("h") is not None and self.button_h_rect.collidepoint(mouse_pos):
            self.hovered_button = "h"
        elif self.boss_icon_rect and self.boss_icon_rect.collidepoint(mouse_pos):
            if all_rounds_completed:
                hovered_boss = True

        if hovered_boss:
            base_button_rect = self.button_e_rect or self.button_m_rect or self.button_h_rect
            prev_rect = self._get_prev_selection_rect()
            line_start_rect = prev_rect or base_button_rect
            if self.boss_icon_rect and line_start_rect:
                desired_y = float(self.boss_icon_rect.y - 250)
                self.popup_target_y = clamp_popup_y(desired_y, self.popup_image, SCREEN_HEIGHT, margin=10.0)
                self.popup_x = self.boss_icon_rect.x + 100
                self.popup_button = "boss"

                line_start_x = line_start_rect.centerx
                line_start_y = line_start_rect.centery
                line_end_x = self.boss_icon_rect.centerx
                line_end_y = self.boss_icon_rect.centery
                self.boss_current_line = (line_start_x, line_start_y, line_end_x, line_end_y)

                if self.boss_hover_state is None:
                    self.boss_hover_state = {
                        "sequence_index": 0,
                        "last_frame_time": pygame.time.get_ticks(),
                    }
                    if self.pen_sound:
                        self.pen_sound.play()
        elif self.hovered_button is not None:
            button_rect = None
            if self.hovered_button == "e" and self.button_e_rect:
                button_rect = self.button_e_rect
            elif self.hovered_button == "m" and self.button_m_rect:
                button_rect = self.button_m_rect
            elif self.hovered_button == "h" and self.button_h_rect:
                button_rect = self.button_h_rect

            if button_rect:
                desired_y = float(button_rect.y - 250)
                self.popup_target_y = clamp_popup_y(desired_y, self.popup_image, SCREEN_HEIGHT, margin=10.0)
                self.popup_x = button_rect.x + 100
                self.popup_button = self.hovered_button

                prev_rect = self._get_prev_selection_rect()
                if prev_rect:
                    line_start_x = prev_rect.centerx
                    line_start_y = prev_rect.centery
                else:
                    line_start_x = 235
                    line_start_y = SCREEN_HEIGHT - 218
                line_end_x = button_rect.centerx
                line_end_y = button_rect.centery
                self.current_line = (line_start_x, line_start_y, line_end_x, line_end_y)

                if self.last_hovered_button != self.hovered_button:
                    if self.pen_sound:
                        self.pen_sound.play()
                    self.last_hovered_button = self.hovered_button
        else:
            self.popup_target_y = float(getattr(self, "popup_hidden_y", -450.0))
            self.current_line = None
            self.boss_current_line = None
            self.last_hovered_button = None
            if self.boss_hover_state is not None:
                self.boss_hover_state = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if can_play_round and self.button_e_rect and self.button_e_rect.collidepoint(mouse_pos) and self.button_goals.get("e") is not None:
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        if self.test_mode:
                            self.Goal = 2
                        else:
                            goal_value = self.button_goals.get("e")
                            if goal_value is not None:
                                self.Goal = goal_value
                        self.last_selected_round = current_active_round
                        self.round_selections[current_active_round] = {"key": "e"}
                        return "button_e"
                    if can_play_round and self.button_m_rect and self.button_m_rect.collidepoint(mouse_pos) and self.button_goals.get("m") is not None:
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        if self.test_mode:
                            self.Goal = 2
                        else:
                            goal_value = self.button_goals.get("m")
                            if goal_value is not None:
                                self.Goal = goal_value
                        self.last_selected_round = current_active_round
                        self.round_selections[current_active_round] = {"key": "m"}
                        return "button_m"
                    if can_play_round and self.button_h_rect and self.button_h_rect.collidepoint(mouse_pos) and self.button_goals.get("h") is not None:
                        if self.current_line:
                            self.saved_lines.append(self.current_line)
                        if self.test_mode:
                            self.Goal = 2
                        else:
                            goal_value = self.button_goals.get("h")
                            if goal_value is not None:
                                self.Goal = goal_value
                        self.last_selected_round = current_active_round
                        self.round_selections[current_active_round] = {"key": "h"}
                        return "button_h"
                    current_active_round = self.get_current_active_round()
                    all_rounds_completed = current_active_round is None
                    if self.boss_icon_rect and self.boss_icon_rect.collidepoint(mouse_pos) and all_rounds_completed:
                        if self.test_mode:
                            self.Goal = 2
                        else:
                            self.Goal = resolve_boss_goal(
                                self.level_number,
                                self.boss_index,
                                self.boss_selection,
                                self.defeated_count,
                                self.is_apper_boss,
                                self.boss_goals,
                                self._get_level2_goal,
                                self._get_level3_goal,
                                self._get_level4_goal,
                                self._apper_goal_boost,
                            )
                            self.Goal = game_state.apply_bailout_goal_modifier(self.Goal)
                            self.Goal = game_state.apply_loan_goal_modifier(
                                self.Goal,
                                self.level_number,
                                self.defeated_count,
                            )
                        return "boss_clicked"
        return None

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(BLACK)

        if self.koordinates:
            self.screen.blit(self.koordinates, (0, 0))

        self._refresh_button_rects()
        self._refresh_button_goals()

        if self.round_selections:
            for round_num in sorted(self.round_selections.keys()):
                sel = self.round_selections[round_num]
                key = sel.get("key")
                base_rect = self.button_base_rects.get(key)
                if not base_rect:
                    continue
                offset_x, offset_y = self._get_round_offset(round_num)
                rect = base_rect.move(offset_x, offset_y)
                self._draw_round_button(key, rect)

        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_popup_last_tick", now)) / 1000.0
        self._popup_last_tick = now
        dt = _clamp_dt_seconds(dt)
        max_delta = float(getattr(self, "popup_speed_pps", 0.0)) * dt
        self.popup_y = move_towards(float(self.popup_y), float(self.popup_target_y), max_delta)

        current_active_round = self.get_current_active_round()
        all_rounds_completed = current_active_round is None

        for line in self.saved_lines:
            if line:
                start_x, start_y, end_x, end_y = line
                pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)

        if self.current_line:
            start_x, start_y, end_x, end_y = self.current_line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)

        if self.boss_current_line:
            start_x, start_y, end_x, end_y = self.boss_current_line
            pygame.draw.line(self.screen, self.line_color, (start_x, start_y), (end_x, end_y), self.line_width)

        if self.round_selections:
            for round_num in sorted(self.round_selections.keys()):
                sel = self.round_selections[round_num]
                key = sel.get("key")
                base_rect = self.button_base_rects.get(key)
                if not base_rect:
                    continue
                offset_x, offset_y = self._get_round_offset(round_num)
                rect = base_rect.move(offset_x, offset_y)
                self._draw_round_button(key, rect)

        if not all_rounds_completed:
            self._draw_round_button("e", self.button_e_rect, shrink_on_hover=True)
            self._draw_round_button("m", self.button_m_rect, shrink_on_hover=True)
            self._draw_round_button("h", self.button_h_rect, shrink_on_hover=True)

        if self.boss_icon and self.boss_icon_rect:
            if self.boss_hover_state is not None and len(self.boss_animation_frames) > 0:
                current_time = pygame.time.get_ticks()
                hover_state = self.boss_hover_state
                time_since_last_frame = current_time - hover_state["last_frame_time"]
                if time_since_last_frame >= self.animation_frame_duration:
                    hover_state["sequence_index"] = (hover_state["sequence_index"] + 1) % len(self.animation_sequence)
                    hover_state["last_frame_time"] = current_time
                frame_index = self.animation_sequence[hover_state["sequence_index"]]
                if frame_index < len(self.boss_animation_frames):
                    self.screen.blit(self.boss_animation_frames[frame_index], self.boss_icon_rect.topleft)
                else:
                    self.screen.blit(self.boss_icon, self.boss_icon_rect.topleft)
            else:
                self.screen.blit(self.boss_icon, self.boss_icon_rect.topleft)

        if self.popup_image and self.popup_y > -self.popup_image.get_height():
            popup_y_draw = int(round(self.popup_y))
            self.screen.blit(self.popup_image, (self.popup_x, popup_y_draw))

            if self.popup_button is not None:
                if self.popup_button == "boss":
                    goal_value = resolve_boss_goal(
                        self.level_number,
                        self.boss_index,
                        self.boss_selection,
                        self.defeated_count,
                        self.is_apper_boss,
                        self.boss_goals,
                        self._get_level2_goal,
                        self._get_level3_goal,
                        self._get_level4_goal,
                        self._apper_goal_boost,
                    )
                    goal_value = game_state.apply_bailout_goal_modifier(goal_value)
                    goal_value = game_state.apply_loan_goal_modifier(
                        goal_value,
                        self.level_number,
                        self.defeated_count,
                    )
                    full_text = f"{self.popup_round_text} {goal_value}$"
                else:
                    goal_value = self.button_goals.get(self.popup_button, 0) or 0
                    full_text = f"{self.popup_round_text} {goal_value}$"

                popup_text_width = self.popup_width - 60
                lines = wrap_text(full_text, self.popup_font, popup_text_width)
                text_start_x = self.popup_x + 30
                text_start_y = popup_y_draw + 115
                line_height = self.popup_font.get_height() + 5

                for i, line in enumerate(lines):
                    text_surface = self.popup_font.render(line, True, PAPER_COLOR)
                    self.screen.blit(text_surface, (text_start_x, text_start_y + i * line_height))

                if self.popup_button == "boss":
                    reward_text_y = text_start_y + len(lines) * line_height
                    reward_text_surface = self.popup_font.render(self.popup_reward_text, True, PAPER_COLOR)
                    self.screen.blit(reward_text_surface, (text_start_x, reward_text_y))
                    napoleondor_reward = self._get_popup_napoleondor_reward()
                    if napoleondor_reward > 0:
                        self._draw_popup_napoleondor_reward(
                            napoleondor_reward,
                            text_start_x + reward_text_surface.get_width() + 12,
                            reward_text_y,
                        )
                    if self.boss_text:
                        boss_reward_lines = wrap_text(self.boss_text, self.popup_font, popup_text_width)
                        reward_text_y += line_height
                        for i, line in enumerate(boss_reward_lines):
                            reward_surface = self.popup_font.render(line, True, PAPER_COLOR)
                            self.screen.blit(reward_surface, (text_start_x, reward_text_y + i * line_height))

                if self.popup_button != "boss" and self.popup_button in ["e", "m", "h"]:
                    round_num = self.get_current_active_round()
                    if round_num is None:
                        if self.level_number == 2:
                            round_num = self.rounds_required if hasattr(self, "rounds_required") else 1
                        else:
                            if self.popup_button == "e":
                                round_num = 1
                            elif self.popup_button == "m":
                                round_num = 2
                            else:
                                round_num = 3
                    reward_key = (self.level_number, round_num, self.popup_button.upper())
                    reward_data = self.rewards.get(reward_key)

                    reward_text_y = text_start_y + len(lines) * line_height
                    reward_text_surface = self.popup_font.render(self.popup_reward_text, True, PAPER_COLOR)
                    self.screen.blit(reward_text_surface, (text_start_x, reward_text_y))

                    napoleondor_reward = self._get_popup_napoleondor_reward()
                    if napoleondor_reward > 0:
                        self._draw_popup_napoleondor_reward(
                            napoleondor_reward,
                            text_start_x + reward_text_surface.get_width() + 12,
                            reward_text_y,
                        )

                    if reward_data:
                        additional_text = reward_data.get("text")
                        if additional_text:
                            additional_text_key = additional_text.strip()
                            additional_text_value = self._get_text(additional_text_key, additional_text_key)
                            additional_text_lines = wrap_text(additional_text_value, self.popup_font, popup_text_width)
                            reward_text_y += line_height
                            for i, line in enumerate(additional_text_lines):
                                additional_text_surface = self.popup_font.render(line, True, PAPER_COLOR)
                                self.screen.blit(additional_text_surface, (text_start_x, reward_text_y + i * line_height))

                if self.popup_button != "boss" and self.popup_button in ["e", "m", "h"]:
                    round_num = self.get_current_active_round()
                    if round_num is None:
                        if self.level_number == 2:
                            round_num = self.rounds_required if hasattr(self, "rounds_required") else 1
                        else:
                            if self.popup_button == "e":
                                round_num = 1
                            elif self.popup_button == "m":
                                round_num = 2
                            else:
                                round_num = 3
                    reward_key = (self.level_number, round_num, self.popup_button.upper())
                    reward_data = self.rewards.get(reward_key)

                    if reward_data:
                        reward1_list = reward_data.get("reward1", [])

                        if reward1_list:
                            reward_text_y = text_start_y + len(lines) * line_height
                            additional_text_lines_count = 0
                            if reward_data.get("text"):
                                additional_text_key = reward_data.get("text").strip()
                                additional_text_value = self._get_text(additional_text_key, additional_text_key)
                                additional_text_lines_list = wrap_text(additional_text_value, self.popup_font, popup_text_width)
                                additional_text_lines_count = len(additional_text_lines_list)
                            card_spacing = 5
                            card_y = (
                                reward_text_y
                                + line_height
                                + (additional_text_lines_count * line_height)
                                + card_spacing
                            )
                            self._draw_reward_preview_cards(reward_data, card_y)
        else:
            if self.popup_button is not None:
                self.popup_button = None

        pygame.display.flip()

    def run(self):
        self.popup_y = float(getattr(self, "popup_hidden_y", -450.0))
        self.popup_target_y = float(getattr(self, "popup_hidden_y", -450.0))
        self.popup_button = None
        self._popup_last_tick = pygame.time.get_ticks()

        while True:
            result = self.handle_input()
            if result == "quit":
                pygame.quit()
                sys.exit()
            if result == "back":
                return "back"
            if result in ("button_e", "button_m", "button_h"):
                return result
            if result == "boss_clicked":
                return "boss_clicked"
            self.draw()
            self.clock.tick(FPS)
