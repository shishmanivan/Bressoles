import pygame
import random
import sys
import os

import game_state
import profile_manager
from boss_logic import (
    apply_boss_functionality,
    apply_boss_reward,
    get_bosses_required,
    get_boss_number_from_filename,
    get_boss_number_from_index,
)
from game_data import (
    REWARD_TOKEN_RANDOM_RED,
    load_boss_rewards,
    load_cards_config,
    load_rewards_config,
    load_rounds_config,
)
from game_stats import (
    build_difficulty_label,
    build_round_label,
    ensure_stats_file,
    update_arkwright_stats,
    update_game_stats,
)
from gameplay_assets import (
    load_deck_view_assets,
    load_end_turn_button,
    load_gameplay_card_assets,
    load_gameplay_core_assets,
    load_gameplay_placeholders,
    load_winlose_assets,
)
from gameplay_card_rendering import (
    draw_bear_modifier_text,
    draw_card_action_text,
    draw_card_turns_text,
    draw_preview_card_action,
    draw_preview_card_turns,
    load_winlose_card_preview,
)
from gameplay_deck import setup_starting_deck_and_hand
from gameplay_drag import (
    cleared_drag_state,
    find_hand_drag_start,
    find_market_drag_start,
    find_side_top_drag_start,
)
from gameplay_draw_helpers import (
    draw_dragged_cards,
    draw_hand_compact_animations,
    draw_hand_draw_animations,
)
from gameplay_layout import (
    build_bottom_placeholders,
    build_market_placeholders,
    build_side_panel_placeholders,
    compute_bottom_hand_layout,
    compute_market_frames_layout,
    compute_right_panel_layout,
)
from gameplay_price_helpers import (
    apply_market_price_change,
    build_market_probabilities,
    build_stock_price_animation_queue,
    compute_slide_position,
    get_card_type_from_config,
    update_arrow_animation_entries,
)
from gameplay_trade_actions import apply_arrow_trade
from gameplay_turn import (
    advance_price_animation_frame,
    apply_price_card_action,
    build_price_cards_processing_queue,
    get_price_animation_frames,
    lock_market_cards,
    lock_side_cards,
    start_next_price_animation,
)
from gameplay_winlose import (
    apply_win_reward,
    get_win_lose_start_y,
    reset_level_loss_state,
    resolve_win_lose_state,
)
from shared_utils import _clamp_dt_seconds, move_towards, wrap_text


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
PAPER_COLOR = (83, 76, 70)


class GameplayPage:
    def __init__(
        self,
        screen,
        font_path,
        difficulty="e",
        goal=None,
        level_number=1,
        is_boss_fight=False,
        boss_index=None,
        round_num=None,
        defeated_count=0,
        lang_dict=None,
        test_mode=False,
        profile_slot=None,
        saved_state=None,
        boss_filename=None,
        active_silver_cards=None,
        active_black_cards=None,
        active_gold_cards=None,
        insurance_goal_debt=0,
        rounds_required=None,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.lang_dict = lang_dict or {}
        self.test_mode = test_mode
        self.profile_slot = profile_slot
        self._initial_saved_state = saved_state if isinstance(saved_state, dict) else None
        self._stats_recorded = False
        ensure_stats_file()
        self.difficulty = difficulty  # "e", "m", or "h"
        self.Goal = goal  # Goal for this round
        self.level_number = level_number  # Level number for deck initialization
        self.is_boss_fight = is_boss_fight
        self.boss_index = boss_index  # Boss index (0-based) for applying boss modifiers
        self.boss_filename = boss_filename
        self.defeated_count = defeated_count  # Number of bosses already defeated on this level
        try:
            self.rounds_required = max(1, int(rounds_required or 1))
        except (TypeError, ValueError):
            self.rounds_required = 1
        self.active_silver_cards = list(active_silver_cards or [])
        self.active_black_cards = list(active_black_cards or [])
        self.active_gold_cards = list(active_gold_cards or [])
        try:
            self.insurance_goal_debt = max(0, int(insurance_goal_debt or 0))
        except (TypeError, ValueError):
            self.insurance_goal_debt = 0
        if active_gold_cards is not None:
            game_state.set_active_gold_cards(self.active_gold_cards)
        self.active_silver_cards_spent = False
        self.forward_trading_shareholder_count = 0
        self.boss_steals_shares = False
        self.stock_bot_enabled = False
        self.stock_bot = None
        self._stock_bot_saved_state = None
        
        # Determine if this is the final boss on the level
        # Logic: if defeated_count == bosses_required - 1, then the next boss (this one) is the last boss
        # For level 2: 
        #   - First boss: defeated_count = 0, bosses_required = 2, so 0 != 2-1, NOT final
        #   - Second boss: defeated_count = 1, bosses_required = 2, so 1 == 2-1, IS final
        if self.is_boss_fight:
            rounds_config = load_rounds_config()
            bosses_required = get_bosses_required(self.level_number, rounds_config)
            # If we've defeated (bosses_required - 1) bosses, then the next one is the final boss
            self.is_final_boss = (self.defeated_count == bosses_required - 1)
        else:
            self.is_final_boss = False
        
        self.round_num = round_num  # Current round number for reward lookup
        
        # Save font path for dynamic font creation
        self.font_path = font_path
        
        # Load fonts
        self.font_large = pygame.font.Font(font_path, 72)
        self.font_medium = pygame.font.Font(font_path, 48)
        self.font_small = pygame.font.Font(font_path, 36)
        self.boss_round_label_font = pygame.font.Font(font_path, 30)
        
        gameplay_assets = load_gameplay_core_assets(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.background = gameplay_assets["background"]
        self.frame = gameplay_assets["frame"]
        self._scaled_frame_cache = {}
        self.arrow_anim_frames = gameplay_assets["arrow_anim_frames"]
        self.arrow_up = gameplay_assets["arrow_up"]
        self.arrow_down_frames = gameplay_assets["arrow_down_frames"]
        self.arrow_down = gameplay_assets["arrow_down"]
        self.arrow_mid_up_frames = gameplay_assets["arrow_mid_up_frames"]
        self.arrow_mid_up = gameplay_assets["arrow_mid_up"]
        self.arrow_mid_down_frames = gameplay_assets["arrow_mid_down_frames"]
        self.arrow_mid_down = gameplay_assets["arrow_mid_down"]

        # Arrow animation state (per clickable arrow)
        self.arrow_anim_interval = 120  # ms
        self.arrow_anim_sequence = [0, 1, 2, 1, 0]  # ping-pong once
        self.arrow_entries = []  # populated each draw: [{'rect':Rect,'animating':bool,'idx':int,'last':ms}]

        self.bottom_frame = gameplay_assets["bottom_frame"]
        self.arrow_sound = gameplay_assets["arrow_sound"]
        self.typewriter_sound = gameplay_assets["typewriter_sound"]
        self.animation_width = gameplay_assets["animation_width"]
        self.animation_height = gameplay_assets["animation_height"]
        self.price_unchanged_frames = gameplay_assets["price_unchanged_frames"]
        self.price_rise_frames = gameplay_assets["price_rise_frames"]
        self.price_fall_frames = gameplay_assets["price_fall_frames"]

        # Price animation state (for sequential playback)
        self.price_animation_queue = []  # List of {'market': 0-2, 'type': 'unchanged'|'rise'} that need animation
        self.stock_price_turn_results = []
        self.current_price_animation = None  # Current animation: {'market': 0-2, 'type': 'unchanged'|'rise', 'frame_idx': int, 'last_update': ms}
        self.price_animation_speed = 12  # frames per second (increased by 30% from 9 to 12, approximately 83ms per frame)
        self.price_animation_interval = 1000 // self.price_animation_speed  # ms per frame

        self.logo_a = gameplay_assets["logo_a"]
        self.logo_b = gameplay_assets["logo_b"]
        self.logo_c = gameplay_assets["logo_c"]

        # Shared rewards config keeps the existing shape but removes duplicated CSV parsing.
        self.rewards = dict(load_rewards_config())

        self.bundle_image = gameplay_assets["bundle_image"]
        self.dollar_image = gameplay_assets["dollar_image"]

        # Initialize quantity variables
        self.Aquantity = 2
        self.Bquantity = 0
        self.Cquantity = 0

        # Initialize price variables
        self.Aprice = 2
        self.BPrice = 2
        self.CPrice = 2

        # Initialize step variables (price change steps)
        self.StepA = 2
        self.StepB = 4
        self.StepC = 6

        # Initialize game state variables
        self.Goal = goal if goal is not None else 0  # Use passed goal or default to 0
        self._apply_bear_goal_modifier()
        if self.insurance_goal_debt:
            self.Goal += self.insurance_goal_debt
            print(
                f"Insurance increased the regular-round Goal by {self.insurance_goal_debt}: "
                f"Goal={self.Goal}"
            )
        # Base start money is 0, plus any persistent bonus from boss rewards (e.g., Robert Fulton)
        self.Money = 0 + game_state.global_start_money_bonus
        self._apply_grant_start_money_bonus()
        self.Day = 1  # Current day/turn (starts at 1)
        
        # Apply boss modifiers to LastTurn
        # IMPORTANT: Modifiers apply ONLY during boss fight, not to regular rounds
        # After boss victory, modifiers are reset - next boss/rounds use default values
        # Note: Hand size and other functionalities are applied after hand initialization (see below)
        base_last_turn = 8 + game_state.global_last_turn_bonus  # Default LastTurn value plus boss reward bonuses
        if self.is_boss_fight and self.boss_index is not None:
            # Legacy: Boss 2 (Adam Smith) - Level 2, boss_index 0: LastTurn - 1
            # This is now handled by apply_boss_functionality, but keep for backward compatibility
            # Check if LastTurn was already modified by functionality (will be checked after hand init)
            if self.level_number == 2 and self.boss_index == 0:
                # Will be handled by apply_boss_functionality, but set default if not modified
                self.LastTurn = base_last_turn - 1  # 7 turns
            else:
                self.LastTurn = base_last_turn
        else:
            self.LastTurn = base_last_turn  # Default: 8 turns (for regular rounds and after boss victory)

        self.end_button, self.end_button_rect = load_end_turn_button(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.end_button_press_until = 0
        self.end_button_pressed_image = None
        if self.end_button:
            pressed_size = (
                max(1, int(self.end_button.get_width() * 0.96)),
                max(1, int(self.end_button.get_height() * 0.96)),
            )
            self.end_button_pressed_image = pygame.transform.smoothscale(self.end_button, pressed_size).convert_alpha()

        # Hand state and placeholder
        self.hand = max(1, 7 + int(game_state.global_hand_bonus or 0))  # initial hand size
        
        # Apply boss functionalities AFTER hand is initialized (e.g., "Self.hand=Self.hand-1", "LastTurn=LastTurn-1")
        # IMPORTANT: Functionalities apply to ALL rounds (regular E/M/H rounds AND boss round) after boss selection
        # After boss victory, modifiers are reset - next boss/rounds use default values
        if self.boss_index is not None:  # Boss was selected (applies to both regular rounds and boss fight)
            boss_number = self._get_active_boss_number()
            if boss_number:
                boss_rewards = load_boss_rewards()
                boss_entry = boss_rewards.get(boss_number) or {}
                func_string = boss_entry.get("Functionalities", "").strip()
                
                # Apply functionalities (e.g., "Self.hand=Self.hand-1", "LastTurn=LastTurn-1")
                if func_string:
                    apply_boss_functionality(func_string, self)
                    print(f"Applied boss functionality for boss {boss_number} (applies to all rounds): {func_string}")
                else:
                    # Legacy: Boss 2 (Adam Smith) - Level 2, boss_index 0: LastTurn - 1
                    # If no functionality string, apply legacy behavior
                    if self.level_number == 2 and self.boss_index == 0:
                        self.LastTurn = base_last_turn - 1  # 7 turns

        self._apply_silver_last_turn_bonuses()

        deck_view_assets = load_deck_view_assets(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.deck_view_background = deck_view_assets["deck_view_background"]
        self.deck_toggle_card = deck_view_assets["deck_toggle_card"]
        self.deck_toggle_font = pygame.font.Font(self.font_path, 18)
        self.deck_view_active = False
        self.deck_toggle_rect = self._build_deck_toggle_rect()
        self.deck_view_panel_rect = pygame.Rect(
            int(SCREEN_WIDTH * 0.1),
            int(SCREEN_HEIGHT * 0.1),
            int(SCREEN_WIDTH * 0.8),
            int(SCREEN_HEIGHT * 0.8),
        )
        self.deck_view_panel_background = None
        if self.deck_view_background:
            self.deck_view_panel_background = pygame.transform.smoothscale(
                self.deck_view_background,
                self.deck_view_panel_rect.size,
            ).convert()
        self.defeated_boss_icon_cache = {}
        self.current_boss_icon_cache = {}
        self.deck_view_silver_card_cache = {}
        
        # Use global Dobor value (can be modified by boss rewards)
        self.Dobor = game_state.global_dobor
        placeholder_assets = load_gameplay_placeholders()
        self.placeholder = placeholder_assets["placeholder"]
        self.placeholder_bottom = placeholder_assets["placeholder_bottom"]
        self.placeholder_market = placeholder_assets["placeholder_market"]
        self.placeholder_side = placeholder_assets["placeholder_side"]

        # Cards config (Card -> Type, etc.)
        self.cards_config = load_cards_config() or {}
        # Keep a compact lookup for Card Type (defaults to 1)
        self.card_types = {cid: (cfg.get("Type", 1) if isinstance(cfg, dict) else 1) for cid, cfg in self.cards_config.items()}

        # Right-side played cards state:
        # Top area: 6 slots (2 rows x 3 columns) for Type=2 cards
        # Bottom area: 3 slots exists in UI but Type=2 must NOT use it
        self.side_cards_top = [None] * 6
        self.side_cards_bottom = [None] * 3
        # Original hand slot for each side card (top area only): {slot: hand_index}
        self.side_card_origins_top = {}
        # Locked state for side cards after end turn (top area only): {slot: bool}
        self.side_cards_locked_top = {}
        
        self.card_size_bottom = (142, 244)  # 4 pixels larger than bottom placeholder (138+4, 240+4)
        self.card_size_market = (99, 171)  # 3 pixels larger than market placeholder (96+3, 168+3)
        # Right-side cards are slightly smaller; keep a small border like other zones
        if self.placeholder_side:
            self.card_size_side = (self.placeholder_side.get_width() + 3, self.placeholder_side.get_height() + 3)
        else:
            self.card_size_side = (int(self.card_size_market[0] * 0.85), int(self.card_size_market[1] * 0.85))

        # Right-side placeholder areas (top: 6 slots, bottom: 3 slots)
        # These are populated in draw() for hit-testing / future drag&drop.
        self.side_placeholders_top = []   # [{'slot': int, 'rect': Rect}]
        self.side_placeholders_bottom = []  # [{'slot': int, 'rect': Rect}]
        
        card_assets = load_gameplay_card_assets(
            self.card_types,
            self.card_size_bottom,
            self.card_size_market,
            self.card_size_side,
        )
        self.card_images_original = card_assets["card_images_original"]
        self.card_images_bottom = card_assets["card_images_bottom"]
        self.card_images_market = card_assets["card_images_market"]
        self.card_images_side = card_assets["card_images_side"]
        self.card_actions = card_assets["card_actions"]
        self.card_turns = card_assets["card_turns"]
        self._apply_investment_card_bonuses()
        self._apply_silver_rollover_bonus()
        
        self.deck, self.hand_cards = setup_starting_deck_and_hand(
            self.level_number,
            self.hand,
            game_state.earned_reward_cards,
            game_state.forced_start_hand_cards_by_level,
            game_state.get_completed_level_reward_cards(),
            game_state.removed_deck_cards_by_level,
            game_state.shop_deck_cards,
            game_state.round_reward_cards,
            game_state.guaranteed_start_hand_cards_by_level,
        )
        
        # Drag and drop state
        self.dragged_card_index = None  # Index of card being dragged, or None
        self.drag_offset = (0, 0)  # Offset from mouse to card top-left corner
        self.dragged_card_pos = (0, 0)  # Current position of dragged card
        self.dragged_card_source = None  # 'hand' or 'market'
        self.dragged_card_market = None  # market index when dragging from market
        self.dragged_card_market_slot = None  # slot index when dragging from market
        self.dragged_card_side_slot = None  # slot index when dragging from right-side top panel (Type=2)

        # Card draw state
        self.pending_draws = 0  # Cards to draw after end-turn animations finish
        
        # Market placeholders positions (for drop detection)
        self.market_placeholders = []  # Will be populated in draw method: [{'market': 0-2, 'slot': 0-2, 'rect': Rect}]
        # Bottom hand placeholders positions
        self.bottom_placeholders = []  # Populated in draw: [{'slot': int, 'rect': Rect}]
        
        # Cards placed on market placeholders: {market: {slot: card_id}}
        self.market_cards = {0: {}, 1: {}, 2: {}}  # Store cards on market placeholders
        # Original hand slot for each card on market: {market: {slot: hand_index}}
        self.market_card_origins = {0: {}, 1: {}, 2: {}}
        # Locked state for market cards after end turn: {market: {slot: bool}}
        self.market_cards_locked = {0: {}, 1: {}, 2: {}}
        # CardTurns tracking for cards on market: {market: {slot: turns_remaining}}
        self.market_card_turns = {0: {}, 1: {}, 2: {}}

        # Card jump animation state for cards 11-18: {market: {slot: {'offset_y': float, 'velocity': float, 'start_time': int}}}
        self.card_jump_animations = {0: {}, 1: {}, 2: {}}
        self.side_card_jump_animations = {}
        self.lifecycle_card_jump_animations = {}
        self.market_clear_animations = []
        self.market_clear_animation_duration = 520
        
        # Queue for processing cards 11-18 sequentially: list of (market, slot) tuples
        self.cards_11_14_queue = []
        self.current_card_processing = None  # (market, slot) currently being processed
        self.card_processing_start_time = 0
        self.card_processing_delay = 300  # ms delay between processing each card
        self.turn_resolution_active = False
        self.effect_finalize_pending = False
        self.red_effects_applied_this_resolution = False

        # Hand compaction animation state (after end turn)
        self.hand_compact_anim = []  # [{'card_id', 'from_index', 'to_index', 'from_pos', 'to_pos', 'progress'}]
        self.hand_compact_target_hand = None  # final hand_cards order after compaction
        self.hand_compact_draw_count = 0  # how many cards to draw after compaction
        self.hand_compact_start_time = 0
        self.hand_compact_duration = 300  # ms
        
        # Hand draw animation state (cards flying in from bottom of screen)
        self.hand_draw_anim = []  # [{'card_id', 'target_slot', 'target_pos', 'from_pos', 'progress'}]
        self.hand_draw_start_time = 0
        self.hand_draw_duration = 400  # ms
        
        # Win/Lose state
        self.win_lose_state = None  # None, "win", or "lose"
        self.final_auto_liquidation_applied = False
        self.ok_button_rect = None  # Will be calculated in draw method
        winlose_assets = load_winlose_assets(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.win_lose_image = winlose_assets["win_lose_image"]
        self.win_lose_x = winlose_assets["win_lose_x"]
        self.win_lose_y = winlose_assets["win_lose_y"]
        self.win_lose_target_y = winlose_assets["win_lose_target_y"]
        self.win_lose_speed_pps = winlose_assets["win_lose_speed_pps"]
        self._winlose_last_tick = winlose_assets["_winlose_last_tick"]
        self.ok1_button = winlose_assets["ok1_button"]
        self.ok2_button = winlose_assets["ok2_button"]
        self.ok_button_base_size = winlose_assets["ok_button_base_size"]
        
        # Store last earned reward cards for WinLose window display
        self.last_earned_cards = []  # List of card numbers earned in this round
        self.long_payout_amount = 0
        
        # Load WinLose window texts from Lang.csv
        self.reward_window_text = self._get_text("RewardWindowText", "RewardWindowText")
        self.reward_final_boss_text = self._get_text("RewardFinalBoss", "RewardWindowText")
        self.reward_level1_final_boss_text = self._get_text(
            "RewardLevel1FinalBoss",
            "Вы разблокировали магазин. Теперь в игре будут попадаться красные карты.",
        )
        self.reward_level2_final_boss_text = self._get_text(
            "RewardLevel2FinalBoss",
            "Теперь в игре будут попадаться серебряные карты.",
        )
        self.boss_victory_deck_reset_text = self._get_text(
            "BossVictoryDeckReset",
            "Колода сброшена до базовой.",
        )
        self.lose_window_text = self._get_text("LoseWindowText", "LoseWindowText")
        
        # Cache for WinLose window reward card images
        self.winlose_card_images = {}
        self._restore_saved_state(self._initial_saved_state)
        if not self._is_stock_bot_allowed():
            self.stock_bot_enabled = False
            self.stock_bot = None
            self._stock_bot_saved_state = None
        self._activate_stock_bot_if_needed()
        self._apply_contango_gain_drop_bonuses()

    def _build_deck_toggle_rect(self):
        width = self.deck_toggle_card.get_width() if self.deck_toggle_card else 64
        height = self.deck_toggle_card.get_height() if self.deck_toggle_card else 104
        hand_layout = compute_bottom_hand_layout(self.bottom_frame, self.hand, SCREEN_WIDTH, SCREEN_HEIGHT)
        if hand_layout:
            x = int(hand_layout["frame_x"])
            y = int(hand_layout["frame_y"] + hand_layout["frame_height"] + 14)
        else:
            x = 60
            y = SCREEN_HEIGHT - height - 32
        if y + height > SCREEN_HEIGHT - 12:
            y = SCREEN_HEIGHT - height - 12
        return pygame.Rect(x, y, width, height)

    def _collect_current_deck_cards(self):
        return sorted(card_id for card_id in self.deck if card_id is not None)

    def _load_defeated_boss_icon(self, boss_filename):
        if not boss_filename:
            return None
        if boss_filename in self.defeated_boss_icon_cache:
            return self.defeated_boss_icon_cache[boss_filename]

        path = os.path.join("Bosses", boss_filename)
        icon = None
        if os.path.exists(path):
            image = pygame.image.load(path).convert_alpha()
            icon = pygame.transform.smoothscale(image, (102, 102)).convert_alpha()
        self.defeated_boss_icon_cache[boss_filename] = icon
        return icon

    def _load_current_boss_icon(self, boss_filename):
        if not boss_filename:
            return None
        if boss_filename in self.current_boss_icon_cache:
            return self.current_boss_icon_cache[boss_filename]

        path = os.path.join("Bosses", boss_filename)
        icon = None
        if os.path.exists(path):
            image = pygame.image.load(path).convert_alpha()
            icon = pygame.transform.smoothscale(image, (74, 74)).convert_alpha()
        self.current_boss_icon_cache[boss_filename] = icon
        return icon

    def _get_current_boss_condition_entry(self):
        if not self.boss_filename:
            return None
        boss_number = get_boss_number_from_filename(self.boss_filename)
        if not boss_number:
            boss_number = get_boss_number_from_index(self.level_number, self.boss_index, self.defeated_count)
        if not boss_number:
            return None
        return {
            "filename": self.boss_filename,
            "boss_number": boss_number,
            "condition_text": self._get_text(f"Boss{boss_number}Text", f"Boss {boss_number}"),
        }

    def _collect_defeated_boss_rewards(self):
        level_state = game_state.boss_progress.get(int(self.level_number or 0), {}) or {}
        defeated_bosses = level_state.get("defeated_bosses") or []
        entries = []
        seen = set()
        for item in defeated_bosses:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename")
            if not filename or filename in seen:
                continue
            seen.add(filename)
            boss_number = get_boss_number_from_filename(filename)
            reward_text = (
                self._get_text(f"Boss{boss_number}Reward", f"Boss {boss_number} reward")
                if boss_number
                else self._get_text("Boss1Reward", "Reward")
            )
            entries.append(
                {
                    "filename": filename,
                    "boss_number": boss_number,
                    "reward_text": reward_text,
                }
            )
        return entries

    def _play_deck_toggle_sound(self):
        if self.arrow_sound:
            self.arrow_sound.play()

    def _start_end_button_press_animation(self):
        self.end_button_press_until = pygame.time.get_ticks() + 110

    def _get_end_button_draw_state(self):
        if (
            self.end_button_pressed_image
            and pygame.time.get_ticks() < self.end_button_press_until
        ):
            pressed_rect = self.end_button_pressed_image.get_rect(center=self.end_button_rect.center)
            pressed_rect.move_ip(3, 3)
            return self.end_button_pressed_image, pressed_rect
        return self.end_button, self.end_button_rect

    def _draw_deck_toggle(self):
        rect = self.deck_toggle_rect
        if self.deck_toggle_card:
            self.screen.blit(self.deck_toggle_card, rect.topleft)
        else:
            pygame.draw.rect(self.screen, WHITE, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

        label = self.deck_toggle_font.render("Upside", True, PAPER_COLOR)
        label_rect = label.get_rect(center=rect.center)
        self.screen.blit(label, label_rect)

    def _draw_deck_view(self):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 85))
        self.screen.blit(dim, (0, 0))

        panel = self.deck_view_panel_rect
        if self.deck_view_panel_background:
            self.screen.blit(self.deck_view_panel_background, panel.topleft)
        else:
            pygame.draw.rect(self.screen, WHITE, panel)
        pygame.draw.rect(self.screen, PAPER_COLOR, panel, 3)

        cards = self._collect_current_deck_cards()
        card_w, card_h = self.card_size_market
        gap_x = 22
        gap_y = 34
        padding_x = 70
        padding_y = 55
        footer_strip_height = 300 if game_state.active_silver_cards_deck else 160
        available_width = panel.width - padding_x * 2
        columns = max(1, int((available_width + gap_x) // (card_w + gap_x)))
        total_width = columns * card_w + (columns - 1) * gap_x
        start_x = int(panel.x + (panel.width - total_width) // 2)
        start_y = panel.y + padding_y
        bottom_limit = panel.bottom - padding_y - footer_strip_height

        for index, card_id in enumerate(cards):
            row = index // columns
            col = index % columns
            card_x = start_x + col * (card_w + gap_x)
            card_y = start_y + row * (card_h + gap_y)
            if card_y + card_h > bottom_limit:
                continue

            image = self.card_images_market.get(card_id) or self.card_images_bottom.get(card_id)
            if not image:
                continue
            self.screen.blit(image, (card_x, card_y))
            self.draw_card_action(card_id, card_x, card_y, self.card_size_market)
            self.draw_card_turns(card_id, card_x, card_y, self.card_size_market)

        self._draw_silver_deck_preview(panel)
        self._draw_defeated_boss_rewards(panel)
        self._draw_deck_toggle()

    def _get_deck_view_silver_card_image(self, card_id, size):
        cache_key = (int(card_id), int(size[0]), int(size[1]))
        if cache_key in self.deck_view_silver_card_cache:
            return self.deck_view_silver_card_cache[cache_key]

        source = (
            self.card_images_original.get(card_id)
            or self.card_images_market.get(card_id)
            or self.card_images_bottom.get(card_id)
        )
        if source:
            image = pygame.transform.smoothscale(source, size).convert_alpha()
        else:
            image = None
        self.deck_view_silver_card_cache[cache_key] = image
        return image

    def _draw_silver_deck_preview(self, panel):
        silver_deck = []
        for card_id in game_state.active_silver_cards_deck or []:
            try:
                silver_deck.append(int(card_id))
            except (TypeError, ValueError):
                continue
        if not silver_deck:
            return

        side_padding = 76
        gap = 16
        available_width = panel.width - side_padding * 2
        desired_width = 64
        if len(silver_deck) > 1:
            max_width = (available_width - gap * (len(silver_deck) - 1)) // len(silver_deck)
            card_w = max(42, min(desired_width, int(max_width)))
        else:
            card_w = desired_width
        card_h = int(card_w / (99 / 171.0))
        total_width = len(silver_deck) * card_w + (len(silver_deck) - 1) * gap
        start_x = panel.x + (panel.width - total_width) // 2
        y = panel.bottom - 280

        for index, card_id in enumerate(silver_deck):
            card_x = start_x + index * (card_w + gap)
            image = self._get_deck_view_silver_card_image(card_id, (card_w, card_h))
            if image:
                self.screen.blit(image, (card_x, y))

    def _draw_defeated_boss_rewards(self, panel):
        entries = self._collect_defeated_boss_rewards()
        if not entries:
            return

        icon_size = 102
        max_boss_icons = 10
        side_padding = 76
        available_width = panel.width - side_padding * 2
        visible_count = min(len(entries), max_boss_icons)
        gap = 0
        if visible_count > 1:
            gap = max(12, (available_width - visible_count * icon_size) // (visible_count - 1))
        start_x = panel.x + side_padding
        y = panel.bottom - 150
        mouse_pos = pygame.mouse.get_pos()
        hovered = None

        for index, entry in enumerate(entries[:max_boss_icons]):
            rect = pygame.Rect(start_x + index * (icon_size + gap), y, icon_size, icon_size)
            icon = self._load_defeated_boss_icon(entry.get("filename"))
            if icon:
                self.screen.blit(icon, rect.topleft)
            else:
                pygame.draw.rect(self.screen, (238, 228, 205), rect)
            if rect.collidepoint(mouse_pos):
                hovered = (entry, rect)

        if hovered:
            self._draw_boss_reward_tooltip(hovered[0], hovered[1], panel)

    def _draw_boss_reward_tooltip(self, entry, icon_rect, panel):
        text = entry.get("reward_text") or ""
        max_width = 360
        lines = wrap_text(text, self.font_small, max_width)
        if not lines:
            return

        line_height = self.font_small.get_height() + 4
        width = min(
            max_width + 28,
            max(self.font_small.size(line)[0] for line in lines) + 28,
        )
        height = len(lines) * line_height + 24
        x = icon_rect.centerx - width // 2
        y = icon_rect.top - height - 12
        if x < panel.x + 18:
            x = panel.x + 18
        if x + width > panel.right - 18:
            x = panel.right - width - 18
        if y < panel.y + 18:
            y = icon_rect.bottom + 12

        tooltip_rect = pygame.Rect(int(x), int(y), int(width), int(height))
        pygame.draw.rect(self.screen, (238, 228, 205), tooltip_rect)
        pygame.draw.rect(self.screen, PAPER_COLOR, tooltip_rect, 2)
        for index, line in enumerate(lines):
            surface = self.font_small.render(line, True, PAPER_COLOR)
            self.screen.blit(surface, (tooltip_rect.x + 14, tooltip_rect.y + 12 + index * line_height))

    def _draw_current_boss_marker(self):
        entry = self._get_current_boss_condition_entry()
        if not entry:
            return

        rect = pygame.Rect(SCREEN_WIDTH - 130, 38, 74, 74)
        icon = self._load_current_boss_icon(entry.get("filename"))
        if icon:
            self.screen.blit(icon, rect.topleft)
        else:
            pygame.draw.rect(self.screen, (238, 228, 205), rect)

        self._draw_boss_round_label(rect)

        if rect.collidepoint(pygame.mouse.get_pos()):
            self._draw_current_boss_condition_tooltip(entry, rect)

    def _draw_boss_round_label(self, boss_rect):
        if self.is_boss_fight:
            round_label = "Босс раунд"
        else:
            try:
                current_round = max(1, int(self.round_num or 1))
            except (TypeError, ValueError):
                current_round = 1
            round_label = f"Раунд {current_round} из {self.rounds_required}"

        label_surface = self.boss_round_label_font.render(round_label, True, PAPER_COLOR)
        padding_x = 12
        padding_y = 7
        label_rect = label_surface.get_rect()

        lifecycle_rects = [
            entry.get("rect")
            for entry in self.side_placeholders_bottom
            if entry.get("rect") is not None
        ]
        if lifecycle_rects:
            section_rect = lifecycle_rects[0].unionall(lifecycle_rects[1:])
            label_center_x = section_rect.centerx
            label_y = min(
                section_rect.bottom + 14,
                SCREEN_HEIGHT - label_rect.height - padding_y * 2 - 8,
            )
        else:
            label_center_x = boss_rect.left - label_rect.width // 2
            label_y = boss_rect.centery - (label_rect.height + padding_y * 2) // 2

        background_rect = pygame.Rect(
            label_center_x - (label_rect.width + padding_x * 2) // 2,
            label_y,
            label_rect.width + padding_x * 2,
            label_rect.height + padding_y * 2,
        )
        pygame.draw.rect(self.screen, (238, 228, 205), background_rect, border_radius=7)
        pygame.draw.rect(self.screen, PAPER_COLOR, background_rect, 2, border_radius=7)
        self.screen.blit(label_surface, label_surface.get_rect(center=background_rect.center))

    def _draw_current_boss_condition_tooltip(self, entry, icon_rect):
        text = entry.get("condition_text") or ""
        max_width = 440
        lines = wrap_text(text, self.font_small, max_width)
        if not lines:
            return

        line_height = self.font_small.get_height() + 4
        width = min(
            max_width + 28,
            max(self.font_small.size(line)[0] for line in lines) + 28,
        )
        height = len(lines) * line_height + 24
        x = icon_rect.right - width
        y = icon_rect.bottom + 12
        if x < 20:
            x = 20
        if y + height > SCREEN_HEIGHT - 20:
            y = icon_rect.top - height - 12

        tooltip_rect = pygame.Rect(int(x), int(y), int(width), int(height))
        pygame.draw.rect(self.screen, (238, 228, 205), tooltip_rect)
        pygame.draw.rect(self.screen, PAPER_COLOR, tooltip_rect, 2)
        for index, line in enumerate(lines):
            surface = self.font_small.render(line, True, PAPER_COLOR)
            self.screen.blit(surface, (tooltip_rect.x + 14, tooltip_rect.y + 12 + index * line_height))

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang_dict.get(key, default)

    def _get_final_boss_reward_text(self):
        try:
            level = int(self.level_number or 0)
        except (TypeError, ValueError):
            level = 0
        if level == 1:
            return self.reward_level1_final_boss_text
        if level == 2:
            return self.reward_level2_final_boss_text
        return self.reward_final_boss_text

    def _apply_investment_card_bonuses(self):
        for card_id, bonus in (game_state.investment_card_bonuses or {}).items():
            try:
                card_id = int(card_id)
                bonus = int(bonus or 0)
            except (TypeError, ValueError):
                continue
            if bonus <= 0 or card_id not in self.card_actions:
                continue
            base_value = int(self.card_actions.get(card_id, 0) or 0)
            if base_value < 0:
                self.card_actions[card_id] = base_value - bonus
            else:
                self.card_actions[card_id] = base_value + bonus
            print(
                f"Applied Investment bonus to card {card_id}: "
                f"{base_value} -> {self.card_actions[card_id]}"
            )

    def _resume_context(self):
        return {
            "difficulty": self.difficulty,
            "goal": self.Goal,
            "level_number": self.level_number,
            "is_boss_fight": self.is_boss_fight,
            "boss_index": self.boss_index,
            "round_num": self.round_num,
            "rounds_required": self.rounds_required,
            "defeated_count": self.defeated_count,
            "test_mode": self.test_mode,
            "boss_filename": self.boss_filename,
            "active_silver_cards": list(self.active_silver_cards or []),
            "active_black_cards": list(self.active_black_cards or []),
            "active_gold_cards": list(self.active_gold_cards or []),
        }

    def _current_prices(self):
        return {
            "Aprice": self.Aprice,
            "BPrice": self.BPrice,
            "CPrice": self.CPrice,
        }

    def _current_steps(self):
        return {
            "StepA": self.StepA,
            "StepB": self.StepB,
            "StepC": self.StepC,
        }

    def _is_stock_bot_allowed(self):
        try:
            return int(self.level_number or 0) == 4
        except (TypeError, ValueError):
            return False

    def _get_active_boss_number(self):
        boss_number = get_boss_number_from_filename(self.boss_filename)
        if boss_number:
            return boss_number
        return get_boss_number_from_index(self.level_number, self.boss_index, self.defeated_count)

    def _activate_stock_bot_if_needed(self):
        if not self._is_stock_bot_allowed():
            self.stock_bot_enabled = False
            self.stock_bot = None
            self._stock_bot_saved_state = None
            return
        if not self.stock_bot_enabled or self.stock_bot is not None:
            return
        try:
            import importlib

            bot_module = importlib.import_module("simple_stock_bot")
            self.stock_bot = bot_module.SimpleStockBot.from_state(self._stock_bot_saved_state)
            print("Simple stock bot activated")
        except Exception as exc:
            print(f"ERROR activating simple stock bot: {exc}")
            self.stock_bot_enabled = False

    def _run_stock_bot_turn(self):
        if not self.stock_bot_enabled:
            return False
        self._activate_stock_bot_if_needed()
        if self.stock_bot is None:
            return False
        decision = self.stock_bot.trade(
            self._current_prices(),
            build_market_probabilities(self.market_cards),
            self._current_steps(),
        )
        print(f"Simple stock bot decision: {decision}")
        return True

    def _stock_bot_status_text(self):
        if not self.stock_bot_enabled:
            return None
        self._activate_stock_bot_if_needed()
        if self.stock_bot is None:
            return None
        return self.stock_bot.status_line(self._current_prices())

    def _serialize_nested_int_dict(self, source):
        result = {}
        for outer_key, inner in (source or {}).items():
            result[str(outer_key)] = {str(k): v for k, v in (inner or {}).items()}
        return result

    def _restore_nested_int_dict(self, source):
        result = {0: {}, 1: {}, 2: {}}
        for outer_key, inner in (source or {}).items():
            try:
                outer = int(outer_key)
            except (TypeError, ValueError):
                continue
            result[outer] = {}
            for key, value in (inner or {}).items():
                try:
                    result[outer][int(key)] = value
                except (TypeError, ValueError):
                    continue
        return result

    def _serialize_gameplay_state(self):
        return {
            "Goal": self.Goal,
            "Money": self.Money,
            "Day": self.Day,
            "LastTurn": self.LastTurn,
            "Dobor": self.Dobor,
            "hand": self.hand,
            "Aquantity": self.Aquantity,
            "Bquantity": self.Bquantity,
            "Cquantity": self.Cquantity,
            "Aprice": self.Aprice,
            "BPrice": self.BPrice,
            "CPrice": self.CPrice,
            "StepA": self.StepA,
            "StepB": self.StepB,
            "StepC": self.StepC,
            "deck": list(self.deck or []),
            "hand_cards": list(self.hand_cards or []),
            "side_cards_top": list(self.side_cards_top or []),
            "side_card_origins_top": {str(k): v for k, v in self.side_card_origins_top.items()},
            "side_cards_locked_top": {str(k): bool(v) for k, v in self.side_cards_locked_top.items()},
            "market_cards": self._serialize_nested_int_dict(self.market_cards),
            "market_card_origins": self._serialize_nested_int_dict(self.market_card_origins),
            "market_cards_locked": self._serialize_nested_int_dict(self.market_cards_locked),
            "market_card_turns": self._serialize_nested_int_dict(self.market_card_turns),
            "card_turns": {str(k): v for k, v in self.card_turns.items()},
            "pending_draws": self.pending_draws,
            "final_auto_liquidation_applied": self.final_auto_liquidation_applied,
            "win_lose_state": self.win_lose_state,
            "win_lose_y": self.win_lose_y,
            "last_earned_cards": list(self.last_earned_cards or []),
            "long_payout_amount": int(self.long_payout_amount or 0),
            "active_silver_cards": list(self.active_silver_cards or []),
            "active_black_cards": list(self.active_black_cards or []),
            "active_gold_cards": list(self.active_gold_cards or []),
            "active_silver_cards_spent": bool(self.active_silver_cards_spent),
            "forward_trading_shareholder_count": int(self.forward_trading_shareholder_count),
            "stock_bot_enabled": bool(self.stock_bot_enabled),
            "stock_bot": self.stock_bot.to_dict() if self.stock_bot is not None else self._stock_bot_saved_state,
            "stats_recorded": self._stats_recorded,
        }

    def _restore_saved_state(self, state):
        if not state:
            return

        scalar_fields = (
            "Goal",
            "Money",
            "Day",
            "LastTurn",
            "Dobor",
            "hand",
            "Aquantity",
            "Bquantity",
            "Cquantity",
            "Aprice",
            "BPrice",
            "CPrice",
            "StepA",
            "StepB",
            "StepC",
            "pending_draws",
            "win_lose_y",
        )
        for field in scalar_fields:
            if field in state:
                setattr(self, field, state[field])

        self.deck = list(state.get("deck", self.deck) or [])
        self.hand_cards = list(state.get("hand_cards", self.hand_cards) or [])
        if len(self.hand_cards) < self.hand:
            self.hand_cards += [None] * (self.hand - len(self.hand_cards))
        self.hand_cards = self.hand_cards[: self.hand]

        self.side_cards_top = list(state.get("side_cards_top", self.side_cards_top) or [])
        if len(self.side_cards_top) < 6:
            self.side_cards_top += [None] * (6 - len(self.side_cards_top))
        self.side_cards_top = self.side_cards_top[:6]
        self.side_card_origins_top = {
            int(k): v for k, v in (state.get("side_card_origins_top") or {}).items()
        }
        self.side_cards_locked_top = {
            int(k): bool(v) for k, v in (state.get("side_cards_locked_top") or {}).items()
        }

        self.market_cards = self._restore_nested_int_dict(state.get("market_cards") or {})
        self.market_card_origins = self._restore_nested_int_dict(state.get("market_card_origins") or {})
        self.market_cards_locked = self._restore_nested_int_dict(state.get("market_cards_locked") or {})
        self.market_card_turns = self._restore_nested_int_dict(state.get("market_card_turns") or {})
        self.card_turns.update({int(k): v for k, v in (state.get("card_turns") or {}).items()})

        self.final_auto_liquidation_applied = bool(state.get("final_auto_liquidation_applied", False))
        self.win_lose_state = state.get("win_lose_state")
        if self.win_lose_state == "win" and self.is_final_boss:
            self.reward_window_text = self._get_final_boss_reward_text()
        self.last_earned_cards = list(state.get("last_earned_cards") or [])
        self.long_payout_amount = int(state.get("long_payout_amount", self.long_payout_amount) or 0)
        self.active_silver_cards = list(state.get("active_silver_cards", self.active_silver_cards) or [])
        self.active_black_cards = list(state.get("active_black_cards", self.active_black_cards) or [])
        self.active_gold_cards = list(state.get("active_gold_cards", self.active_gold_cards) or [])
        game_state.set_active_gold_cards(self.active_gold_cards)
        self.active_silver_cards_spent = bool(state.get("active_silver_cards_spent", self.active_silver_cards_spent))
        self.forward_trading_shareholder_count = int(
            state.get("forward_trading_shareholder_count", self.forward_trading_shareholder_count) or 0
        )
        self.stock_bot_enabled = bool(state.get("stock_bot_enabled", self.stock_bot_enabled))
        self._stock_bot_saved_state = state.get("stock_bot")
        self._stats_recorded = bool(state.get("stats_recorded", self._stats_recorded))
        self.turn_resolution_active = False
        self.price_animation_queue = []
        self.stock_price_turn_results = []
        self.current_price_animation = None
        self.cards_11_14_queue = []
        self.current_card_processing = None
        self.card_jump_animations = {0: {}, 1: {}, 2: {}}
        self.side_card_jump_animations = {}
        self.lifecycle_card_jump_animations = {}
        self.effect_finalize_pending = False
        self.red_effects_applied_this_resolution = False
        self.hand_compact_anim = []
        self.hand_draw_anim = []
        self.market_clear_animations = []
        self._reset_drag_state()

    def _save_active_game(self):
        if not self.profile_slot or self.test_mode:
            return
        profile_manager.save_active_game(
            self.profile_slot,
            self._resume_context(),
            self._serialize_gameplay_state(),
        )

    def _clear_active_game(self):
        if not self.profile_slot or self.test_mode:
            return
        profile_manager.clear_active_game(self.profile_slot)
    
    def _load_winlose_card(self, card_number):
        """Load and cache a reward card image for WinLose window."""
        return load_winlose_card_preview(
            card_number,
            self.winlose_card_images,
            self.card_actions,
            self.card_turns,
            self.font_path,
            PAPER_COLOR,
        )
    
    def _draw_winlose_card_action(self, surface, action_value, card_id, card_width, card_height):
        """Draw CardAction value on a WinLose card surface."""
        draw_preview_card_action(surface, action_value, card_id, card_width, card_height, self.font_path, PAPER_COLOR)
    
    def _draw_winlose_card_turns(self, surface, turns_value, card_id, card_width, card_height):
        """Draw CardTurns value on a WinLose card surface."""
        draw_preview_card_turns(
            surface,
            turns_value,
            card_id,
            card_width,
            card_height,
            self.font_path,
            PAPER_COLOR,
            adjust_mode="preview",
        )
    
    def get_card_type(self, card_id):
        """Return card Type from Cards.csv (defaults to 1)."""
        return get_card_type_from_config(self.card_types, card_id)

    def _apply_arrow_trade(self, frame_idx, arrow_type):
        trade_result = apply_arrow_trade(
            self.Money,
            {
                "Aquantity": self.Aquantity,
                "Bquantity": self.Bquantity,
                "Cquantity": self.Cquantity,
            },
            {
                "Aprice": self.Aprice,
                "BPrice": self.BPrice,
                "CPrice": self.CPrice,
            },
            frame_idx,
            arrow_type,
        )

        quantities = trade_result["quantities"]
        self.Money = trade_result["money"]
        self.Aquantity = quantities["Aquantity"]
        self.Bquantity = quantities["Bquantity"]
        self.Cquantity = quantities["Cquantity"]

        if trade_result["changed"]:
            self._check_win_lose()
        return trade_result["changed"]

    def _apply_drag_state(self, drag_state):
        for key, value in drag_state.items():
            setattr(self, key, value)

    def _apply_new_drag_state(self, drag_state):
        self._apply_drag_state(cleared_drag_state())
        self._apply_drag_state(drag_state)

    def _start_card_drag(self, mouse_pos):
        hand_layout = compute_bottom_hand_layout(self.bottom_frame, self.hand, SCREEN_WIDTH, SCREEN_HEIGHT)
        drag_state = find_hand_drag_start(mouse_pos, hand_layout, self.hand_cards, self.card_size_bottom)
        if drag_state:
            self._apply_new_drag_state(drag_state)
            return True

        drag_state = find_market_drag_start(
            mouse_pos,
            self.market_placeholders,
            self.market_cards,
            self.market_cards_locked,
        )
        if drag_state:
            self._apply_new_drag_state(drag_state)
            return True

        drag_state = find_side_top_drag_start(
            mouse_pos,
            self.side_placeholders_top,
            self.side_cards_top,
            self.side_cards_locked_top,
        )
        if drag_state:
            self._apply_new_drag_state(drag_state)
            return True

        return False

    def _reset_drag_state(self):
        self._apply_drag_state(cleared_drag_state())
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if self.deck_view_active:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.deck_view_active = False
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.deck_toggle_rect.collidepoint(event.pos):
                        self._play_deck_toggle_sound()
                        self.deck_view_active = False
                    continue
                continue
            
            # Handle Ok button click if WinLose screen is shown
            if self.win_lose_state is not None and self.win_lose_image:
                # Determine which button to show based on win/lose state
                ok_button = None
                if self.win_lose_state == "win" and self.ok1_button:
                    ok_button = self.ok1_button
                elif self.win_lose_state == "lose" and self.ok2_button:
                    ok_button = self.ok2_button
                
                if ok_button:
                    # Use ok_button_rect from draw method (calculated there)
                    # If not set yet, calculate it (same calculation as in draw method)
                    if not hasattr(self, 'ok_button_rect') or self.ok_button_rect is None:
                        winlose_width = self.win_lose_image.get_width()
                        winlose_height = self.win_lose_image.get_height()
                        ok_margin_right = 30
                        ok_margin_bottom = 30
                        ok_x = self.win_lose_x + winlose_width - self.ok_button_base_size[0] - ok_margin_right
                        win_lose_y_draw = int(round(self.win_lose_y))
                        ok_y = win_lose_y_draw + winlose_height - self.ok_button_base_size[1] - ok_margin_bottom
                        self.ok_button_rect = pygame.Rect(int(ok_x), int(ok_y), self.ok_button_base_size[0], self.ok_button_base_size[1])
                    
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # Left click
                            # Check if click is on Ok button
                            if self.ok_button_rect.collidepoint(event.pos):
                                print(f"Ok button clicked! State: {self.win_lose_state}, Button: {'Ok1' if self.win_lose_state == 'win' else 'Ok2'}")
                                if self.win_lose_state == "lose":
                                    # Lost: return to level selection screen
                                    print("Returning to level_select")
                                    self._clear_active_game()
                                    return "level_select"
                                elif self.win_lose_state == "win":
                                    # Won: return to round selection (boss victory handling is done in main loop)
                                    # The main loop will check if it's a boss fight and handle level 1 boss defeat
                                    print("Returning to round_select")
                                    self._clear_active_game()
                                    return "round_select"
                            else:
                                # Debug: print click position and button rect
                                print(f"WinLose screen active. Click at: {event.pos}, Ok button rect: {self.ok_button_rect if hasattr(self, 'ok_button_rect') else 'None'}, win_lose_y: {self.win_lose_y}, State: {self.win_lose_state}")
                    
                    # Skip other events when WinLose screen is shown (but allow QUIT and MOUSEBUTTONDOWN which are handled above)
                    if event.type != pygame.QUIT and event.type != pygame.MOUSEBUTTONDOWN:
                        continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "back"
            
            # Handle drag and drop
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.win_lose_state is None and self.deck_toggle_rect.collidepoint(event.pos):
                        self._play_deck_toggle_sound()
                        self.deck_view_active = True
                        self._reset_drag_state()
                        continue

                    # Check if clicking on a card in hand (only if not already dragging)
                    if self.dragged_card_index is None:
                        self._start_card_drag(mouse_pos)
                    
                    # Only process arrows/buttons if not dragging a card.
                    # Trading is locked while EndTurn market/card effects are still resolving.
                    if self.dragged_card_index is None and not self._is_turn_resolution_active():
                        mouse_pos = event.pos
                        for entry in self.arrow_entries:
                            if not entry["rect"].collidepoint(mouse_pos):
                                continue
                            
                            frame_idx = entry.get("frame_index")
                            if frame_idx is None:
                                continue
                            self._apply_arrow_trade(frame_idx, entry.get("arrow_type"))
                            
                            # Start animation (if entry has frames)
                            if entry.get("frames"):
                                entry["animating"] = True
                                entry["idx"] = 0
                                entry["last"] = pygame.time.get_ticks()
                                if self.arrow_sound:
                                    self.arrow_sound.play()
                            break
                    
                    # Check if End Turn button was clicked (outside arrow loop)
                    if self.end_button_rect and self.end_button_rect.collidepoint(mouse_pos):
                        # Don't allow EndTurn while a previous EndTurn is still resolving.
                        if self._is_turn_resolution_active():
                            break

                        self._start_end_button_press_animation()
                        
                        # Play sound
                        if self.arrow_sound:
                            self.arrow_sound.play()
                        self.turn_resolution_active = True
                        self.effect_finalize_pending = False
                        self.red_effects_applied_this_resolution = False
                        # Calculate price changes based on probability distributions
                        animation_queue = self.update_stock_prices()
                        self.stock_price_turn_results = list(animation_queue or [])
                        # Lock all currently played market cards for future turns
                        self._lock_market_cards()
                        # Queue animations for markets
                        if animation_queue:
                            self.price_animation_queue = animation_queue.copy()
                            self._start_next_price_animation()
                        else:
                            self._process_cards_11_14()
                            if self.current_card_processing is None and not self.cards_11_14_queue:
                                self._begin_effect_finalize_or_wait()
                        break  # Exit event processing after button click
            
            # MOUSEMOTION events are handled in run() loop for smoother updates
            
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and (
                    self.dragged_card_index is not None
                    or self.dragged_card_source in ("market", "side_top")
                ):
                    dropped = False
                    # Determine dragged hand card type (if dragging from hand)
                    dragged_hand_card_id = None
                    dragged_hand_card_type = 1
                    if self.dragged_card_source == "hand" and self.dragged_card_index is not None:
                        if self.dragged_card_index < len(self.hand_cards):
                            dragged_hand_card_id = self.hand_cards[self.dragged_card_index]
                            dragged_hand_card_type = self.get_card_type(dragged_hand_card_id)

                    # Returning a Type=2 card from the right-side TOP panel back to hand
                    if not dropped and self.dragged_card_source == "side_top":
                        src_slot = self.dragged_card_side_slot
                        # Cancel drag if dropped back onto the same side placeholder
                        for ph_info in self.side_placeholders_top:
                            if ph_info["rect"].collidepoint(event.pos):
                                if ph_info.get("slot") == src_slot:
                                    dropped = True
                                break
                        if not dropped:
                            # Only allow drop to the ORIGINAL hand slot of this card
                            for ph_info in self.bottom_placeholders:
                                if not ph_info["rect"].collidepoint(event.pos):
                                    continue
                                slot = ph_info["slot"]
                                origin_slot = self.side_card_origins_top.get(src_slot)
                                if origin_slot is not None and slot == origin_slot and self.hand_cards[slot] is None:
                                    card_id = self.side_cards_top[src_slot] if src_slot is not None else None
                                    if card_id is not None:
                                        self.hand_cards[slot] = card_id
                                        self.side_cards_top[src_slot] = None
                                        self.side_card_origins_top.pop(src_slot, None)
                                        self.side_cards_locked_top.pop(src_slot, None)
                                        if self.pending_draws > 0:
                                            self.pending_draws -= 1
                                        dropped = True
                                        break

                    # Type=2 cards are played ONLY on the top right-side panel (6 slots), not on markets.
                    if (
                        not dropped
                        and self.dragged_card_source == "hand"
                        and self.dragged_card_index is not None
                        and dragged_hand_card_type == 2
                    ):
                        for ph_info in self.side_placeholders_top:
                            if ph_info["rect"].collidepoint(event.pos):
                                slot = ph_info["slot"]
                                # Only allow drop to the FIRST free slot
                                first_free = None
                                for s in range(len(self.side_cards_top)):
                                    if self.side_cards_top[s] is None:
                                        first_free = s
                                        break
                                if first_free is None or slot != first_free:
                                    continue
                                card_id = dragged_hand_card_id
                                if card_id is not None:
                                    self.side_cards_top[slot] = card_id
                                    # Remember original hand slot and mark as not locked for this turn
                                    self.side_card_origins_top[slot] = self.dragged_card_index
                                    self.side_cards_locked_top[slot] = False
                                    self.hand_cards[self.dragged_card_index] = None
                                    self.pending_draws += 1
                                    dropped = True
                                    break

                    # Try to drop card on market placeholder (only if NOT dragging a Type=2 card from hand)
                    if not (
                        self.dragged_card_source == "side_top"
                        or (self.dragged_card_source == "hand" and dragged_hand_card_type == 2)
                    ):
                        for ph_info in self.market_placeholders:
                            if ph_info['rect'].collidepoint(event.pos):
                                # Drop card on market placeholder
                                market = ph_info['market']
                                slot = ph_info['slot']
                                # If slot is already occupied, skip (except for original source slot when dragging from market)
                                if not (
                                    self.dragged_card_source == "market"
                                    and market == self.dragged_card_market
                                    and slot == self.dragged_card_market_slot
                                ):
                                    if slot in self.market_cards[market] and self.market_cards[market][slot] is not None:
                                        continue
                                # Moving from hand to market
                                if self.dragged_card_source == "hand" and self.dragged_card_index is not None:
                                    # Only allow drop to the FIRST free placeholder of this market
                                    # (index of the first empty slot or None if market full)
                                    first_free = None
                                    for s in range(3):
                                        if self.market_cards[market].get(s) is None:
                                            first_free = s
                                            break
                                    if first_free is None or slot != first_free:
                                        continue
                                    if self.dragged_card_index < len(self.hand_cards):
                                        card_id = self.hand_cards[self.dragged_card_index]
                                        if card_id is not None:
                                            self.market_cards[market][slot] = card_id
                                            # Remember original hand slot for this market card
                                            self.market_card_origins[market][slot] = self.dragged_card_index
                                            # Новая сыгранная карта пока НЕ заблокирована
                                            self.market_cards_locked[market][slot] = False
                                            # Initialize CardTurns for cards 11-18
                                            if card_id in self.card_turns:
                                                self.market_card_turns[market][slot] = self.card_turns[card_id]
                                            # Remove from hand slot
                                            self.hand_cards[self.dragged_card_index] = None
                                            # Mark pending draw for empty slot
                                            self.pending_draws += 1
                                            dropped = True
                                            break
                                # Moving from market to market
                                elif self.dragged_card_source == "market":
                                    src_market = self.dragged_card_market
                                    src_slot = self.dragged_card_market_slot
                                    # If dropping back onto the same placeholder, do nothing (just cancel drag)
                                    if market == src_market and slot == src_slot:
                                        dropped = True
                                        break
                                    # Only allow drop to FIRST free placeholder of other markets
                                    if market == src_market:
                                        continue
                                    first_free = None
                                    for s in range(3):
                                        if self.market_cards[market].get(s) is None:
                                            first_free = s
                                            break
                                    if first_free is None or slot != first_free:
                                        continue
                                    card_id = self.market_cards[src_market].get(src_slot)
                                    if card_id is not None:
                                        self.market_cards[market][slot] = card_id
                                        self.market_cards[src_market][src_slot] = None
                                        # Move origin info along with the card
                                        origin_slot = self.market_card_origins[src_market].pop(src_slot, None)
                                        if origin_slot is not None:
                                            self.market_card_origins[market][slot] = origin_slot
                                        # Переносим флаг заблокированности вместе с картой
                                        locked_flag = self.market_cards_locked[src_market].pop(src_slot, False)
                                        self.market_cards_locked[market][slot] = locked_flag
                                        # Move CardTurns along with the card
                                        turns = self.market_card_turns[src_market].pop(src_slot, None)
                                        if turns is not None:
                                            self.market_card_turns[market][slot] = turns
                                        dropped = True
                                        break
                    # Try to drop card on hand placeholder (return or move to another hand slot)
                    if not dropped:
                        for ph_info in self.bottom_placeholders:
                            if ph_info['rect'].collidepoint(event.pos):
                                slot = ph_info['slot']
                                # From hand to another hand slot (reposition)
                                if self.dragged_card_source == "hand" and self.dragged_card_index is not None:
                                    # Only drop if target slot is empty
                                    if self.hand_cards[slot] is None:
                                        card_id = self.hand_cards[self.dragged_card_index]
                                        if card_id is not None:
                                            self.hand_cards[slot] = card_id
                                            self.hand_cards[self.dragged_card_index] = None
                                            dropped = True
                                            break
                                # From market back to hand
                                elif self.dragged_card_source == "market":
                                    # Only allow drop to the ORIGINAL hand slot of this card
                                    src_market = self.dragged_card_market
                                    src_slot = self.dragged_card_market_slot
                                    origin_slot = self.market_card_origins[src_market].get(src_slot)
                                    if origin_slot is not None and slot == origin_slot and self.hand_cards[slot] is None:
                                        card_id = self.market_cards[src_market].get(src_slot)
                                        if card_id is not None:
                                            self.hand_cards[slot] = card_id
                                            self.market_cards[src_market][src_slot] = None
                                            # Clear origin mapping
                                            self.market_card_origins[src_market].pop(src_slot, None)
                                            # Слот на рынке освобождается и больше не заблокирован
                                            self.market_cards_locked[src_market].pop(src_slot, None)
                                            # Clear CardTurns when card returns to hand
                                            self.market_card_turns[src_market].pop(src_slot, None)
                                            if self.pending_draws > 0:
                                                self.pending_draws -= 1
                                            dropped = True
                                            break
                    # Reset drag state (even if not dropped, card returns to source)
                    self._reset_drag_state()
        
        return None
    
    def _check_win_lose(self):
        """Check win/lose conditions and trigger WinLose screen if needed"""
        self._apply_final_auto_liquidation_if_needed()
        next_state, reason = resolve_win_lose_state(
            self.win_lose_state,
            self.Money,
            self.Goal,
            self.Day,
            self.LastTurn,
        )
        if next_state is None:
            return

        next_state, reason = self._apply_insurance_if_needed(next_state, reason)
        self._finish_win_lose_result(next_state, reason)

    def _finish_win_lose_result(self, next_state, reason):
        self.win_lose_state = next_state
        self._record_stats_result(next_state == "win")
        self._spend_active_silver_cards_if_needed()
        self.long_payout_amount = 0
        if next_state == "win":
            if self.is_final_boss:
                self.reward_window_text = self._get_final_boss_reward_text()
            self.win_lose_y = get_win_lose_start_y(self.win_lose_image) or self.win_lose_y
            if reason == "insurance":
                print(
                    f"WIN by Insurance: Money={self.Money}, Goal={self.Goal}, "
                    f"Day={self.Day}, LastTurn={self.LastTurn}"
                )
            elif reason == "last_turn":
                print(f"WIN on LastTurn: Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
            else:
                print(f"WIN (early): Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
            self._apply_bill_of_exchange_shop_discount()
            self._add_reward_card_to_deck()
            self._apply_obligation_win_bonus()
            self._record_bear_victory_progress()
            self.long_payout_amount = self._apply_long_investment_payout()
            game_state.advance_bailout_round()
        else:
            self._reset_earned_cards_for_level()
            self.win_lose_y = get_win_lose_start_y(self.win_lose_image) or self.win_lose_y
            print(f"LOSE on LastTurn: Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")

    def _has_played_side_card(self, target_card_id):
        return any(card_id == target_card_id for card_id in self.side_cards_top)

    def _active_lifecycle_cards(self):
        return (
            list(self.active_silver_cards or [])
            + list(self.active_black_cards or [])
            + list(self.active_gold_cards or [])
        )

    def _has_active_silver_card(self, target_card_id):
        for card_id in self._active_lifecycle_cards():
            try:
                if int(card_id) == int(target_card_id):
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _count_active_silver_card(self, target_card_id):
        count = 0
        for card_id in self._active_lifecycle_cards():
            try:
                if int(card_id) == int(target_card_id):
                    count += 1
            except (TypeError, ValueError):
                continue
        return count

    def _apply_insurance_if_needed(self, next_state, reason):
        if next_state != "lose" or self.is_boss_fight or not self._has_active_silver_card(220):
            return next_state, reason
        try:
            shortfall = max(0, int(self.Goal) - int(self.Money))
        except (TypeError, ValueError):
            shortfall = 0
        if shortfall <= 0:
            return next_state, reason

        game_state.add_insurance_goal_debt(shortfall)
        print(
            f"Active card 220 Insurance converted defeat to victory: "
            f"Money={self.Money}, Goal={self.Goal}, carried debt={shortfall}"
        )
        return "win", "insurance"

    def _apply_grant_start_money_bonus(self):
        silver_count = self._count_active_silver_card(214)
        gold_count = self._count_active_silver_card(403)
        silver_value = 8 if gold_count > 0 else 4
        bonus = silver_value * silver_count + 8 * gold_count
        if bonus <= 0:
            return
        self.Money += bonus
        print(
            f"Grant cards increased starting Money by {bonus}: "
            f"silver={silver_count}x{silver_value}, gold={gold_count}x8, Money={self.Money}"
        )

    def _apply_bear_goal_modifier(self):
        discount_percent = game_state.get_bear_goal_discount_percent(self.active_gold_cards)
        if discount_percent <= 0:
            return
        try:
            base_goal = float(self.Goal)
        except (TypeError, ValueError):
            return
        if base_goal <= 0:
            return

        self.Goal = max(1, int(base_goal * (100 - discount_percent) / 100))
        print(
            f"Active card 401 Bear reduced Goal by {discount_percent}%: "
            f"{base_goal:g} -> {self.Goal}"
        )

    def _get_contango_gain_drop_multiplier(self):
        return 2 ** self._count_active_silver_card(204)

    def _get_basket_trading_bonus(self):
        count = self._count_active_silver_card(206)
        if count <= 0:
            return 0
        if count == 1:
            return 2
        if count == 2:
            return 6
        return 10

    def _apply_contango_gain_drop_bonuses(self):
        multiplier = self._get_contango_gain_drop_multiplier()
        if multiplier <= 1:
            return
        for card_id in range(11, 19):
            if card_id in self.card_actions:
                self.card_actions[card_id] *= multiplier
        print(f"Active card 204 Contango multiplied Gain/Drop values by {multiplier}.")

    def _apply_silver_rollover_bonus(self):
        bonus = self._count_active_silver_card(208)
        if bonus <= 0:
            return
        for card_id in range(11, 19):
            if card_id in self.card_turns:
                self.card_turns[card_id] += bonus
        print(f"Active card 208 Rollover extended Gain/Drop durations by {bonus}.")

    def _apply_silver_last_turn_bonuses(self):
        turn_bonuses = {
            202: 1,
            203: 2,
        }
        bonus = 0
        for card_id in self._active_lifecycle_cards():
            try:
                bonus += turn_bonuses.get(int(card_id), 0)
            except (TypeError, ValueError):
                continue
        if bonus <= 0:
            return
        self.LastTurn += bonus
        print(f"Active lifecycle cards increased LastTurn by {bonus}: LastTurn={self.LastTurn}")

    def _apply_final_auto_liquidation_if_needed(self):
        """Sell remaining shares before the final result check."""
        if self.final_auto_liquidation_applied:
            return False
        if self.win_lose_state is not None or self.Day != self.LastTurn:
            return False

        full_price = self._has_active_silver_card(201)
        discounted = self._has_played_side_card(110)
        if not full_price and not discounted:
            return False

        gross_value = (
            self.Aquantity * self.Aprice
            + self.Bquantity * self.BPrice
            + self.Cquantity * self.CPrice
        )
        if gross_value <= 0:
            self.final_auto_liquidation_applied = True
            return False

        if full_price and discounted:
            proceeds = (gross_value * 120) // 100
            source = "Cards 110+201 Rebate"
        elif full_price:
            proceeds = gross_value
            source = "Active card 201"
        else:
            proceeds = (gross_value * 80) // 100
            source = "Card 110"

        self.Money += proceeds
        print(
            f"{source} auto-liquidation: gross={gross_value}, proceeds={proceeds}, "
            f"Money={self.Money}"
        )
        self.Aquantity = 0
        self.Bquantity = 0
        self.Cquantity = 0
        self.final_auto_liquidation_applied = True
        return True
    
    def _add_reward_card_to_deck(self):
        """Add reward card to global earned cards list after winning a round, or apply boss reward for boss fights"""
        apply_win_reward(
            self,
            game_state.round_reward_cards,
            self.rewards,
            REWARD_TOKEN_RANDOM_RED,
            load_boss_rewards,
            get_boss_number_from_index,
            apply_boss_reward,
            game_state.pick_random_red_card_for_level,
            game_state.add_silver_card,
        )
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)

    def _spend_active_silver_cards_if_needed(self):
        if self.active_silver_cards_spent or not self.active_silver_cards:
            return
        game_state.spend_silver_cards(self.active_silver_cards)
        self.active_silver_cards_spent = True
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)

    def _apply_obligation_win_bonus(self):
        obligation_rewards = {
            217: 5,
            218: 10,
            219: 15,
        }
        earned = sum(
            reward
            for card_id, reward in obligation_rewards.items()
            if self._has_active_silver_card(card_id)
        )
        if earned <= 0:
            return
        game_state.add_napoleondors(self.level_number, earned)
        print(f"Active Obligation cards awarded {earned} napoleondors after victory.")
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)

    def _apply_long_investment_payout(self):
        payout = game_state.advance_long_investments(self.level_number)
        if payout <= 0:
            return 0
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return int(payout)

    def _apply_bill_of_exchange_shop_discount(self):
        if not self._has_active_silver_card(215):
            return
        game_state.set_pending_shop_discount(50)

    def _record_bear_victory_progress(self):
        if not game_state.record_bear_victory(self.active_gold_cards):
            return
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
    
    def _reset_earned_cards_for_level(self):
        """Reset earned reward cards for current level when player loses"""
        game_state.clear_insurance_goal_debt()
        game_state.clear_investment_card_bonuses()
        game_state.clear_profit_bonus()
        game_state.clear_pending_shop_discount()
        game_state.clear_round_reward_cards(self.level_number)
        game_state.clear_shop_deck_cards()
        game_state.clear_gold_cards()
        game_state.clear_silver_cards_deck()
        game_state.clear_bailout_bonus()
        game_state.clear_long_investments()

        game_state.global_dobor = reset_level_loss_state(
            self.level_number,
            game_state.earned_reward_cards,
            game_state.forced_start_hand_cards_by_level,
            game_state.guaranteed_start_hand_cards_by_level,
        )
        if game_state.global_start_money_bonus != 0:
            print(
                f"Reset starting money bonus from {game_state.global_start_money_bonus} "
                f"to 0 due to defeat on level {self.level_number}"
            )
        game_state.global_start_money_bonus = 0
        if game_state.global_last_turn_bonus != 0:
            print(
                f"Reset LastTurn bonus from {game_state.global_last_turn_bonus} "
                f"to 0 due to defeat on level {self.level_number}"
            )
        game_state.global_last_turn_bonus = 0
        if game_state.global_hand_bonus != 0:
            print(
                f"Reset hand bonus from {game_state.global_hand_bonus} "
                f"to 0 due to defeat on level {self.level_number}"
            )
        game_state.global_hand_bonus = 0
        game_state.reset_level_attempt(self.level_number)
        self.Dobor = game_state.global_dobor
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)

    def _record_stats_result(self, won):
        if self.test_mode or self._stats_recorded:
            return

        boss_number = get_boss_number_from_index(
            self.level_number,
            self.boss_index,
            self.defeated_count,
        )
        round_label = build_round_label(self.round_num, is_boss_fight=self.is_boss_fight)
        difficulty_label = build_difficulty_label(self.difficulty, is_boss_fight=self.is_boss_fight)
        update_game_stats(
            self.level_number,
            boss_number,
            round_label,
            won,
            difficulty_label,
        )
        self._stats_recorded = True
    
    def update_win_lose_animation(self):
        """Update WinLose screen slide animation"""
        if self.win_lose_state is None or not self.win_lose_image:
            return

        # dt-based slide from top (smooth regardless of FPS)
        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_winlose_last_tick", now)) / 1000.0
        self._winlose_last_tick = now
        dt = _clamp_dt_seconds(dt)
        self.win_lose_y = compute_slide_position(
            self.win_lose_y,
            self.win_lose_target_y,
            getattr(self, "win_lose_speed_pps", 0.0),
            dt,
            move_towards,
        )

    def update_stock_prices(self):
        """Calculate price changes based on probability distributions after EndTurn.
        Returns list of {'market': 0-2, 'type': 'unchanged'|'rise'|'fall', 'price_change': int} 
        Prices are NOT updated here - they will be updated when animation starts."""
        return build_stock_price_animation_queue(
            self.StepA,
            self.StepB,
            self.StepC,
            self.market_cards,
        )

    def _start_next_price_animation(self, now=None):
        if now is None:
            now = pygame.time.get_ticks()
        next_anim, current_animation = start_next_price_animation(self.price_animation_queue, now)
        if not next_anim:
            return False

        self._apply_price_change(next_anim["market"], next_anim["price_change"])
        self.current_price_animation = current_animation
        if self.typewriter_sound:
            self.typewriter_sound.play()
        return True

    def update_arrow_animation(self):
        if not self.arrow_entries or not self.arrow_anim_frames:
            return
        now = pygame.time.get_ticks()
        update_arrow_animation_entries(
            self.arrow_entries,
            self.arrow_anim_sequence,
            self.arrow_anim_interval,
            now,
        )

    def _is_turn_resolution_active(self):
        return (
            self.turn_resolution_active
            or self.effect_finalize_pending
            or self.current_price_animation is not None
            or bool(self.price_animation_queue)
            or self.current_card_processing is not None
            or bool(self.cards_11_14_queue)
            or any(bool(slots) for slots in self.card_jump_animations.values())
            or bool(self.side_card_jump_animations)
            or bool(self.lifecycle_card_jump_animations)
            or bool(self.market_clear_animations)
        )

    def _finish_price_animations(self):
        """Finish regular market movement and start Gain/Drop card processing."""
        self.current_price_animation = None
        self._apply_basket_trading_if_needed()
        self._process_cards_11_14()

        if self.current_card_processing is None and not self.cards_11_14_queue:
            self._begin_effect_finalize_or_wait()

    def _apply_basket_trading_if_needed(self):
        bonus = self._get_basket_trading_bonus()
        if bonus <= 0:
            return False

        movements = list(getattr(self, "stock_price_turn_results", []) or [])
        rose_markets = {
            entry.get("market")
            for entry in movements
            if entry.get("type") == "rise"
        }
        if rose_markets != {0, 1, 2}:
            return False

        self.Aprice = max(2, self.Aprice + bonus)
        self.BPrice = max(2, self.BPrice + bonus)
        self.CPrice = max(2, self.CPrice + bonus)
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_basket_trading = int(card_id) == 206
            except (TypeError, ValueError):
                is_basket_trading = False
            if is_basket_trading:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        print(
            f"Silver card 206 Basket Trading applied: bonus={bonus}, "
            f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
        )
        return True

    def _begin_effect_finalize_or_wait(self):
        """Apply red cards after market card animations, then draw cards."""
        if not self.turn_resolution_active:
            return

        if not self.red_effects_applied_this_resolution:
            if any(bool(slots) for slots in self.card_jump_animations.values()):
                self.effect_finalize_pending = True
                return

            self._apply_red_card_effects_if_needed()
            self._lock_side_cards()
            self.red_effects_applied_this_resolution = True

        if self._has_effect_animations():
            self.effect_finalize_pending = True
            return

        self._finalize_turn_resolution()

    def _finalize_turn_resolution(self):
        """Advance/check the day and only then draw replacement cards."""
        if not self.turn_resolution_active:
            return

        self.effect_finalize_pending = False
        self._apply_boss_share_theft_if_needed()
        self._run_stock_bot_turn()
        self._check_win_lose()

        if self.win_lose_state is None:
            if self.Day < self.LastTurn:
                self.Day += 1
                self._check_win_lose()
            else:
                print(f"ERROR: Day==LastTurn but game didn't end! Forcing end.")
                if self.Money >= self.Goal:
                    next_state, reason = "win", "last_turn"
                else:
                    next_state, reason = self._apply_insurance_if_needed("lose", "last_turn")
                self._finish_win_lose_result(next_state, reason)

        self._draw_pending_cards()
        self.turn_resolution_active = False
        self.red_effects_applied_this_resolution = False
        if not self.hand_compact_anim and not self.hand_draw_anim:
            self._save_active_game()

    def _apply_boss_share_theft_if_needed(self):
        """Arkwright: sometimes steal a percentage of owned shares at end of turn."""
        if not getattr(self, "boss_steals_shares", False) or self.win_lose_state is not None:
            return False

        total_shares = int(self.Aquantity or 0) + int(self.Bquantity or 0) + int(self.Cquantity or 0)
        if total_shares <= 10:
            self._record_arkwright_stat("none")
            return False

        roll = random.random()
        if roll < 0.01:
            percent = 0.90
            outcome = "steal_90"
        elif roll < 0.06:
            percent = 0.50
            outcome = "steal_50"
        elif roll < 0.21:
            percent = 0.30
            outcome = "steal_30"
        else:
            self._record_arkwright_stat("none")
            return False

        shares_to_steal = min(total_shares, max(1, int(total_shares * percent)))
        stolen = {"Aquantity": 0, "Bquantity": 0, "Cquantity": 0}

        for _ in range(shares_to_steal):
            available = [
                ("Aquantity", int(self.Aquantity or 0)),
                ("Bquantity", int(self.Bquantity or 0)),
                ("Cquantity", int(self.Cquantity or 0)),
            ]
            available = [(key, quantity) for key, quantity in available if quantity > 0]
            if not available:
                break

            pick = random.randint(1, sum(quantity for _, quantity in available))
            cursor = 0
            for key, quantity in available:
                cursor += quantity
                if pick <= cursor:
                    setattr(self, key, getattr(self, key) - 1)
                    stolen[key] += 1
                    break

        stolen_total = sum(stolen.values())
        if stolen_total <= 0:
            self._record_arkwright_stat("none")
            return False

        self._record_arkwright_stat(outcome)
        print(
            "Arkwright stole shares: "
            f"A={stolen['Aquantity']}, B={stolen['Bquantity']}, C={stolen['Cquantity']} "
            f"({int(percent * 100)}%, total={stolen_total})"
        )
        return True

    def _record_arkwright_stat(self, outcome):
        if self.test_mode:
            return
        boss_number = get_boss_number_from_index(
            self.level_number,
            self.boss_index,
            self.defeated_count,
        )
        if boss_number != 6:
            return
        round_label = build_round_label(self.round_num, is_boss_fight=self.is_boss_fight)
        difficulty_label = build_difficulty_label(self.difficulty, is_boss_fight=self.is_boss_fight)
        update_arkwright_stats(
            self.level_number,
            boss_number,
            round_label,
            difficulty_label,
            outcome,
        )

    def update_price_animation(self):
        """Update price animation - plays sequentially for each market"""
        if not self.current_price_animation:
            # Check if there are more animations in queue
            self._start_next_price_animation()
            return
        
        frames = get_price_animation_frames(
            self.current_price_animation,
            self.price_unchanged_frames,
            self.price_rise_frames,
            self.price_fall_frames,
        )
        
        if not frames:
            # No frames available, skip to next animation
            if not self._start_next_price_animation():
                self._finish_price_animations()
            return
        
        now = pygame.time.get_ticks()
        animation_completed = advance_price_animation_frame(
            self.current_price_animation,
            len(frames),
            self.price_animation_interval,
            now,
        )
        if animation_completed and not self._start_next_price_animation(now):
            self._finish_price_animations()
    
    def _process_cards_11_14(self):
        """Queue cards 11-18 for sequential processing after all price animations finish."""
        self.cards_11_14_queue = build_price_cards_processing_queue(
            self.market_cards,
            self.market_card_turns,
        )
        
        # Start processing first card if queue is not empty
        if self.cards_11_14_queue:
            self.current_card_processing = self.cards_11_14_queue.pop(0)
            self.card_processing_start_time = pygame.time.get_ticks()
    
    def update_cards_11_14_processing(self):
        """Update sequential processing of cards 11-18. Process one card at a time with delay."""
        if self.current_card_processing is None:
            # Check if there are more cards in queue
            if self.cards_11_14_queue:
                self.current_card_processing = self.cards_11_14_queue.pop(0)
                self.card_processing_start_time = pygame.time.get_ticks()
            return
        
        now = pygame.time.get_ticks()
        if now - self.card_processing_start_time < self.card_processing_delay:
            # Still waiting for delay
            return
        
        # Process current card
        market, slot = self.current_card_processing
        card_id = self.market_cards[market].get(slot)
        
        if card_id is not None:
            # Check CardTurns again (in case it changed)
            turns_remaining = self.market_card_turns[market].get(slot)
            if turns_remaining is not None and turns_remaining > 0:
                # Apply CardAction to price
                card_action = self.card_actions.get(card_id, 0)
                prices = apply_price_card_action(
                    {"Aprice": self.Aprice, "BPrice": self.BPrice, "CPrice": self.CPrice},
                    market,
                    card_id,
                    card_action,
                )
                self.Aprice = prices["Aprice"]
                self.BPrice = prices["BPrice"]
                self.CPrice = prices["CPrice"]
                
                # Start jump animation for the card
                self._start_card_jump_animation(self.card_jump_animations[market], slot)
                
                # Decrement CardTurns
                self.market_card_turns[market][slot] = turns_remaining - 1
        
        # Move to next card
        self.current_card_processing = None
        if self.cards_11_14_queue:
            self.current_card_processing = self.cards_11_14_queue.pop(0)
            self.card_processing_start_time = pygame.time.get_ticks()
        else:
            self._begin_effect_finalize_or_wait()
    
    def _start_card_jump_animation(self, animation_map, key):
        animation_map[key] = {
            'offset_y': 0.0,
            'velocity': -8.7,
            'start_time': pygame.time.get_ticks()
        }

    def _advance_jump_animation_map(self, animation_map, gravity=0.8):
        slots_to_remove = []
        for key, anim in list(animation_map.items()):
            anim['velocity'] += gravity
            anim['offset_y'] += anim['velocity']

            if anim['offset_y'] >= 0 and anim['velocity'] > 0:
                slots_to_remove.append(key)
            if anim['offset_y'] > 0:
                anim['offset_y'] = 0

        for key in slots_to_remove:
            animation_map.pop(key, None)

    def _has_effect_animations(self):
        return (
            any(bool(slots) for slots in self.card_jump_animations.values())
            or bool(self.side_card_jump_animations)
            or bool(self.lifecycle_card_jump_animations)
            or bool(self.market_clear_animations)
        )

    def _maybe_finalize_after_effect_animations(self):
        if (
            self.effect_finalize_pending
            and self.turn_resolution_active
            and self.current_price_animation is None
            and not self.price_animation_queue
            and self.current_card_processing is None
            and not self.cards_11_14_queue
            and not self._has_effect_animations()
        ):
            self._begin_effect_finalize_or_wait()

    def update_card_jump_animations(self):
        """Update jump animations for cards 11-18. Simple physics: velocity decreases due to gravity."""
        for market in (0, 1, 2):
            self._advance_jump_animation_map(self.card_jump_animations[market])

    def update_side_card_jump_animations(self):
        """Update jump animations for freshly played red cards."""
        self._advance_jump_animation_map(self.side_card_jump_animations)
        self._advance_jump_animation_map(self.lifecycle_card_jump_animations)
    
    def _apply_price_change(self, market, price_change):
        """Apply price change to the specified market. Ensures price doesn't drop below 2."""
        prices = apply_market_price_change(
            {"Aprice": self.Aprice, "BPrice": self.BPrice, "CPrice": self.CPrice},
            market,
            price_change,
        )
        self.Aprice = prices["Aprice"]
        self.BPrice = prices["BPrice"]
        self.CPrice = prices["CPrice"]

    def _lock_market_cards(self):
        """Помечает все текущие карты на рынке как сыгранные и заблокированные до конца игры."""
        lock_market_cards(self.market_cards, self.market_cards_locked)

    def _lock_side_cards(self):
        """Lock all currently played Type=2 cards on the right-side TOP panel for future turns."""
        lock_side_cards(self.side_cards_top, self.side_cards_locked_top)

    def _count_fresh_side_card(self, target_card_id):
        """Return how many target Type=2 cards were played this turn and are still unlocked."""
        count = 0
        for slot, card_id in enumerate(self.side_cards_top):
            if card_id == target_card_id and not self.side_cards_locked_top.get(slot):
                count += 1
        return count

    def _has_fresh_side_card(self, target_card_id):
        return self._count_fresh_side_card(target_card_id) > 0

    def _apply_red_card_effects_if_needed(self):
        """Apply one-shot effects for freshly played Type=2 red cards."""
        self._apply_extended_gain_drop_effect_if_needed()
        self._apply_forward_trading_effect_if_needed()
        self._apply_bankruptcy_effects_if_needed()
        self._apply_extra_turn_effect_if_needed()
        self._apply_market_crash_effect_if_needed()
        self._apply_deleverage_effect_if_needed()

    def _start_fresh_side_card_jump_animation_for_card(self, target_card_id):
        for slot, card_id in enumerate(self.side_cards_top):
            if (
                card_id == target_card_id
                and not self.side_cards_locked_top.get(slot)
            ):
                self._start_card_jump_animation(self.side_card_jump_animations, slot)

    def _apply_extended_gain_drop_effect_if_needed(self):
        """Card 112: extend all Gain/Drop durations, including cards already in play."""
        red_rollover_count = self._count_fresh_side_card(112)
        if red_rollover_count <= 0:
            return False

        bonus_per_red_rollover = 2 if self._has_active_silver_card(208) else 1
        bonus = red_rollover_count * bonus_per_red_rollover

        for card_id in range(11, 19):
            if card_id in self.card_turns:
                self.card_turns[card_id] += bonus

        for market in (0, 1, 2):
            for slot, card_id in self.market_cards[market].items():
                if card_id in self.card_turns:
                    current = self.market_card_turns[market].get(slot, self.card_turns[card_id] - bonus)
                    self.market_card_turns[market][slot] = current + bonus

        source = "Card 112 Rollover"
        print(f"{source} extended Gain/Drop durations by {bonus}.")
        return True

    def _apply_forward_trading_effect_if_needed(self):
        """Cards 207/402: extend the round when fresh Shareholders are played."""
        shareholder_count = self._count_fresh_side_card(100)
        if shareholder_count <= 0:
            return False

        has_silver_forward = self._count_active_silver_card(207) > 0
        gold_forward_count = self._count_active_silver_card(402)

        if has_silver_forward:
            self.forward_trading_shareholder_count += shareholder_count
            pairs = self.forward_trading_shareholder_count // 2
            self.forward_trading_shareholder_count %= 2
            if pairs <= 0:
                print(
                    "Active card 207 Forward Trading stored one Shareholder; "
                    f"pending={self.forward_trading_shareholder_count}"
                )
                return False

            bonus_per_pair = 4 if gold_forward_count > 0 else 1
            bonus = pairs * bonus_per_pair
            self.LastTurn += bonus
            source = "207+402 Forward Trading" if gold_forward_count > 0 else "207 Forward Trading"
            print(
                f"Active card {source} extended LastTurn by {bonus} "
                f"({pairs} Shareholder pair(s)): LastTurn={self.LastTurn}"
            )
            return True

        if gold_forward_count <= 0:
            return False

        bonus = shareholder_count * gold_forward_count
        self.LastTurn += bonus
        print(
            f"Active card 402 Forward Trading extended LastTurn by {bonus} "
            f"({shareholder_count} Shareholder, {gold_forward_count} Forward Trading): LastTurn={self.LastTurn}"
        )
        return True

    def _set_market_price_to_minimum(self, market):
        if market == 0:
            changed = self.Aprice != 2
            self.Aprice = 2
            return changed
        elif market == 1:
            changed = self.BPrice != 2
            self.BPrice = 2
            return changed
        elif market == 2:
            changed = self.CPrice != 2
            self.CPrice = 2
            return changed
        return False

    def _apply_bankruptcy_effects_if_needed(self):
        """Cards 113-115: set A/B/C stock prices to 2."""
        applied = False
        for card_id, market in ((113, 0), (114, 1), (115, 2)):
            if self._has_fresh_side_card(card_id):
                changed = self._set_market_price_to_minimum(market)
                if changed:
                    self._start_fresh_side_card_jump_animation_for_card(card_id)
                    applied = True
        if applied:
            print(
                "Bankruptcy cards applied: "
                f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
            )
        return applied

    def _apply_extra_turn_effect_if_needed(self):
        """Card 116: increase turns before round end by 1 per fresh 116."""
        bonus = self._count_fresh_side_card(116)
        if bonus <= 0:
            return False
        self.LastTurn += bonus
        print(f"Card 116 increased LastTurn by {bonus}: LastTurn={self.LastTurn}")
        return True

    def _apply_market_crash_effect_if_needed(self):
        """Card 117: set all stock prices to the minimum value of 2."""
        count = self._count_fresh_side_card(117)
        if count <= 0:
            return False
        changed = any(price != 2 for price in (self.Aprice, self.BPrice, self.CPrice))
        self.Aprice = 2
        self.BPrice = 2
        self.CPrice = 2
        if not changed:
            return False
        self._start_fresh_side_card_jump_animation_for_card(117)
        print(
            f"Card 117 market crash applied: count={count}, "
            f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
        )
        return True

    def _find_market_placeholder_rect(self, market, slot):
        for ph_info in self.market_placeholders:
            if ph_info.get("market") == market and ph_info.get("slot") == slot:
                return ph_info.get("rect")
        return None

    def _start_market_clear_animation(self):
        """Create a temporary scatter animation for cards removed by Deleverage."""
        now = pygame.time.get_ticks()
        animations = []
        for market in (0, 1, 2):
            for slot in (0, 1, 2):
                card_id = self.market_cards[market].get(slot)
                if card_id is None:
                    continue
                rect = self._find_market_placeholder_rect(market, slot)
                if rect is None:
                    continue
                direction = -1 if market == 0 else (1 if market == 2 else (-1 if slot == 0 else 1))
                animations.append(
                    {
                        "card_id": card_id,
                        "x": float(rect.x - 1),
                        "y": float(rect.y - 1),
                        "vx": float(direction * (4.0 + slot * 1.2)),
                        "vy": float(-9.0 - market * 0.8 - slot * 0.9),
                        "rotation": 0.0,
                        "spin": float(direction * (8.0 + slot * 2.0)),
                        "start": now,
                        "turns_remaining": self.market_card_turns[market].get(slot),
                    }
                )
        if animations:
            self.market_clear_animations.extend(animations)

    def _apply_deleverage_effect_if_needed(self):
        """Apply card 111: remove all cards from the three market rows."""
        if not self._has_fresh_side_card(111):
            return False

        has_market_cards = any(
            self.market_cards[market].get(slot) is not None
            for market in (0, 1, 2)
            for slot in (0, 1, 2)
        )
        if not has_market_cards:
            return False

        self._start_market_clear_animation()
        for market in (0, 1, 2):
            self.market_cards[market].clear()
            self.market_card_origins[market].clear()
            self.market_cards_locked[market].clear()
            self.market_card_turns[market].clear()
            self.card_jump_animations[market].clear()

        self.cards_11_14_queue = []
        self.current_card_processing = None
        return True

    def update_market_clear_animations(self):
        """Advance temporary card scatter animations started by Deleverage."""
        if not self.market_clear_animations:
            return
        now = pygame.time.get_ticks()
        active = []
        for anim in self.market_clear_animations:
            elapsed = now - anim.get("start", now)
            if elapsed >= self.market_clear_animation_duration:
                continue
            anim["vy"] += 0.38
            anim["x"] += anim["vx"]
            anim["y"] += anim["vy"]
            anim["rotation"] += anim["spin"]
            active.append(anim)
        self.market_clear_animations = active

    def _draw_pending_cards(self):
        """Prepare hand compaction animation and subsequent draw after end-turn animations.

        1) Планируем плавное смещение несыгранных карт влево (без мгновенной перемотки).
        2) После завершения анимации добираем Dobor карт в ближайшие свободные слоты.
        """
        # Сбросим старую анимацию, если по какой‑то причине она ещё есть
        self.hand_compact_anim = []
        self.hand_compact_target_hand = None
        self.hand_compact_draw_count = 0

        # Нечего делать, если нет добора, колода пуста или в руке нет слотов
        if self.hand <= 0:
            self.pending_draws = 0
            return

        # 1) Подготовка данных о текущем расположении слотов руки
        if not self.bottom_frame:
            # Без нижней рамки корректно анимировать не получится — просто применяем мгновенно
            existing_cards = [card for card in self.hand_cards if card is not None][: self.hand]
            self.hand_cards = existing_cards + [None] * (self.hand - len(existing_cards))

            # Добор без анимации — всегда добраем, если есть свободные слоты и карты в колоде
            start_idx = len(existing_cards)
            slots_available = self.hand - start_idx
            if self.Dobor > 0 and self.deck and slots_available > 0:
                draw_limit = min(self.Dobor, len(self.deck), slots_available)
                for offset in range(draw_limit):
                    card_id = self.deck.pop(0)
                    if card_id == 0:
                        card_id = 100
                    self.hand_cards[start_idx + offset] = card_id
                self.pending_draws = 0
            return

        # Геометрия нижней рамки и плейсхолдеров (как в draw)
        bf_w = self.bottom_frame.get_width()
        bf_h = self.bottom_frame.get_height()
        bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
        bf_y = SCREEN_HEIGHT - bf_h - 150

        ph_w = 138
        ph_h = 240
        margin_x = 20
        available_width = bf_w - margin_x * 2
        if self.hand > 1:
            spacing = max(5, (available_width - ph_w * self.hand) // (self.hand - 1))
        else:
            spacing = 0
        total_width = ph_w * self.hand + spacing * (self.hand - 1)
        start_x = bf_x + (bf_w - total_width) // 2
        # Slightly lower hand area so cards don't overlap the top edge of the bottom frame
        start_y = bf_y + (bf_h - ph_h) // 2 + 10

        # Координаты слотов руки
        slot_positions = []
        for i in range(self.hand):
            slot_x = start_x + i * (ph_w + spacing)
            slot_y = start_y
            slot_positions.append((slot_x, slot_y))

        # 2) Текущее содержимое и целевой порядок (уплотнение влево)
        existing = [(idx, card) for idx, card in enumerate(self.hand_cards) if card is not None]
        if not existing:
            # В руке вообще нет карт — просто добираем без анимации - всегда добраем, если есть карты в колоде
            if self.Dobor > 0 and len(self.deck) > 0 and self.hand > 0:
                draw_limit = min(self.Dobor, len(self.deck), self.hand)
                self.hand_cards = [None] * self.hand
                for i in range(draw_limit):
                    card_id = self.deck.pop(0)
                    if card_id == 0:
                        card_id = 100
                    self.hand_cards[i] = card_id
                self.pending_draws = 0
            return

        # Обрезаем по размеру руки
        existing = existing[: self.hand]
        # Целевая рука: те же карты, но слева без дыр
        target_hand = [card for (_, card) in existing]
        target_hand += [None] * (self.hand - len(target_hand))

        # 3) Планируем перемещения карт для анимации
        moves = []
        for new_index, (old_index, card_id) in enumerate(existing):
            if old_index == new_index:
                continue  # карта уже на своём месте, не анимируем
            from_pos = slot_positions[old_index]
            to_pos = slot_positions[new_index]
            moves.append(
                {
                    "card_id": card_id,
                    "from_index": old_index,
                    "to_index": new_index,
                    "from_pos": from_pos,
                    "to_pos": to_pos,
                    "progress": 0.0,
                }
            )

        # 4) Считаем, сколько карт нужно добрать после компактации - всегда добраем, если есть свободные слоты и карты в колоде
        free_slots_after = self.hand - len(existing)
        max_draw_by_slots = free_slots_after
        draw_limit = min(self.Dobor, len(self.deck), max_draw_by_slots) if free_slots_after > 0 and len(self.deck) > 0 else 0

        if not moves:
            # Ничего не двигается — применяем целевой порядок и запускаем анимацию добора
            self.hand_cards = target_hand
            if draw_limit > 0 and len(self.deck) > 0:
                start_idx = len(existing)
                # Запускаем анимацию добора вместо мгновенного добора
                if self.bottom_frame:
                    self.hand_draw_anim = []
                    for offset in range(draw_limit):
                        target_slot = start_idx + offset
                        target_x = slot_positions[target_slot][0]
                        target_y = slot_positions[target_slot][1]
                        # Стартовая позиция: снизу экрана, по центру целевого слота по X
                        from_x = target_x
                        from_y = SCREEN_HEIGHT + 100  # За экраном снизу
                        
                        card_id = self.deck.pop(0)  # Извлекаем карту из колоды
                        if card_id == 0:
                            card_id = 100
                        self.hand_draw_anim.append({
                            'card_id': card_id,
                            'target_slot': target_slot,
                            'target_pos': (target_x, target_y),
                            'from_pos': (from_x, from_y),
                            'progress': 0.0,
                        })
                    self.hand_draw_start_time = pygame.time.get_ticks()
                else:
                    # Без рамки — мгновенный добор
                    for offset in range(draw_limit):
                        card_id = self.deck.pop(0)
                        if card_id == 0:
                            card_id = 100
                        self.hand_cards[start_idx + offset] = card_id
            self.pending_draws = 0
            return

        # Есть движения — сохраняем состояние анимации, саму руку пока не меняем
        self.hand_compact_anim = moves
        self.hand_compact_target_hand = target_hand
        self.hand_compact_draw_count = draw_limit
        self.hand_compact_start_time = pygame.time.get_ticks()

    def update_hand_compact_animation(self):
        """Обновление анимации сдвига карт в руке после конца хода."""
        if not self.hand_compact_anim:
            return

        now = pygame.time.get_ticks()
        elapsed = now - self.hand_compact_start_time
        progress = min(1.0, max(0.0, elapsed / max(1, self.hand_compact_duration)))

        # Обновляем прогресс для всех движений
        for entry in self.hand_compact_anim:
            entry["progress"] = progress

        # Если анимация завершена, применяем итоговое состояние
        if progress >= 1.0:
            # 1) Применяем целевой порядок руки
            if self.hand_compact_target_hand is not None:
                self.hand_cards = self.hand_compact_target_hand

            # 2) Запускаем анимацию добора карт (вместо мгновенного добора)
            if (
                self.hand_compact_draw_count > 0
                and len(self.deck) > 0
                and any(card is None for card in self.hand_cards)
            ):
                # Ищем первый свободный слот
                first_free = next(
                    (i for i, card in enumerate(self.hand_cards) if card is None), None
                )
                if first_free is not None:
                    slots_available = self.hand - first_free
                    draw_count = min(
                        self.hand_compact_draw_count, slots_available, len(self.deck)
                    )
                    
                # Подготовка геометрии для анимации (как в draw, с тем же более плотным spacing и центрированием)
                    if self.bottom_frame:
                        bf_w = self.bottom_frame.get_width()
                        bf_h = self.bottom_frame.get_height()
                        bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
                        bf_y = SCREEN_HEIGHT - bf_h - 150
                        
                        ph_w = 138
                        ph_h = 240
                        base_spacing = (bf_w - ph_w * self.hand) / (self.hand + 1)
                        spacing = base_spacing * 0.7
                        total_width = ph_w * self.hand + spacing * (self.hand - 1)
                        start_x = bf_x + (bf_w - total_width) / 2
                        start_y = bf_y + (bf_h - ph_h) // 2
                        
                        # Создаём анимации для каждой новой карты
                        self.hand_draw_anim = []
                        for offset in range(draw_count):
                            target_slot = first_free + offset
                            target_x = start_x + target_slot * (ph_w + spacing)
                            target_y = start_y
                            # Стартовая позиция: снизу экрана, по центру целевого слота по X
                            from_x = target_x
                            from_y = SCREEN_HEIGHT + 100  # За экраном снизу
                            
                            card_id = self.deck.pop(0)  # Извлекаем карту из колоды
                            if card_id == 0:
                                card_id = 100
                            self.hand_draw_anim.append({
                                'card_id': card_id,
                                'target_slot': target_slot,
                                'target_pos': (target_x, target_y),
                                'from_pos': (from_x, from_y),
                                'progress': 0.0,
                            })
                        self.hand_draw_start_time = pygame.time.get_ticks()
                    else:
                        # Без рамки — мгновенный добор
                        for offset in range(draw_count):
                            card_id = self.deck.pop(0)
                            if card_id == 0:
                                card_id = 100
                            self.hand_cards[first_free + offset] = card_id

            # 3) Сбрасываем состояние анимации компактирования (добор запущен отдельно)
            self.pending_draws = 0
            self.hand_compact_anim = []
            self.hand_compact_target_hand = None
            self.hand_compact_draw_count = 0
            if not self.hand_draw_anim:
                self._save_active_game()
    
    def update_hand_draw_animation(self):
        """Обновление анимации добора карт (карты прилетают снизу экрана)."""
        if not self.hand_draw_anim:
            return
        
        now = pygame.time.get_ticks()
        elapsed = now - self.hand_draw_start_time
        progress = min(1.0, max(0.0, elapsed / max(1, self.hand_draw_duration)))
        
        # Обновляем прогресс для всех анимаций добора
        for entry in self.hand_draw_anim:
            entry["progress"] = progress
        
        # Если анимация завершена, физически добавляем карты в руку
        if progress >= 1.0:
            for entry in self.hand_draw_anim:
                target_slot = entry['target_slot']
                if target_slot < len(self.hand_cards):
                    card_id = entry['card_id']
                    if card_id == 0:
                        card_id = 100
                    self.hand_cards[target_slot] = card_id
            
            # Сбрасываем состояние анимации добора
            self.hand_draw_anim = []
            self._save_active_game()
    
    def draw_card_action(self, card_id, card_x, card_y, card_size):
        if not hasattr(self, "card_action_font_cache"):
            self.card_action_font_cache = {}
        draw_card_action_text(
            self.screen,
            card_id,
            self.card_actions,
            card_x,
            card_y,
            card_size,
            self.font_path,
            PAPER_COLOR,
            self.card_action_font_cache,
        )
    
    def draw_card_turns(self, card_id, card_x, card_y, card_size, turns_remaining=None):
        if not hasattr(self, "card_turns_font_cache"):
            self.card_turns_font_cache = {}
        draw_card_turns_text(
            self.screen,
            card_id,
            self.card_turns,
            card_x,
            card_y,
            card_size,
            self.font_path,
            PAPER_COLOR,
            self.card_turns_font_cache,
            turns_remaining=turns_remaining,
        )

    def _draw_market_probability_debug(self, market, x, y):
        probs = build_market_probabilities(self.market_cards).get(market)
        if not probs:
            return

        def fmt(value):
            return f"{int(value)}" if float(value).is_integer() else f"{value:.1f}"

        lines = (
            f"Fall {fmt(probs['fall'])}%",
            f"Flat {fmt(probs['flat'])}%",
            f"Rise {fmt(probs['rise'])}%",
        )
        line_height = self.font_small.get_height() + 2
        for index, line in enumerate(lines):
            text_surface = self.font_small.render(line, True, PAPER_COLOR)
            self.screen.blit(text_surface, (x, y + index * line_height))

    def _draw_market_clear_animations(self):
        if not self.market_clear_animations:
            return
        now = pygame.time.get_ticks()
        for anim in self.market_clear_animations:
            card_id = anim.get("card_id")
            image = self.card_images_market.get(card_id)
            if not image:
                continue

            elapsed = now - anim.get("start", now)
            progress = max(0.0, min(1.0, elapsed / max(1, self.market_clear_animation_duration)))
            alpha = max(0, min(255, int(255 * (1.0 - progress))))

            card_surface = image.copy()
            card_surface.set_alpha(alpha)
            rotated = pygame.transform.rotate(card_surface, anim.get("rotation", 0.0))
            center_x = anim.get("x", 0.0) + self.card_size_market[0] / 2
            center_y = anim.get("y", 0.0) + self.card_size_market[1] / 2
            draw_rect = rotated.get_rect(center=(int(center_x), int(center_y)))
            self.screen.blit(rotated, draw_rect.topleft)
    
    def draw(self):
        # Clear market placeholders list at start of draw
        self.market_placeholders = []

        # Determine dragged hand card type (for zone highlight / drop rules)
        dragged_hand_card_id = None
        dragged_hand_card_type = 1
        if (
            self.dragged_card_source == "hand"
            and self.dragged_card_index is not None
            and self.dragged_card_index < len(self.hand_cards)
        ):
            dragged_hand_card_id = self.hand_cards[self.dragged_card_index]
            dragged_hand_card_type = self.get_card_type(dragged_hand_card_id)
        
        # Draw background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill(PAPER_COLOR)
        
        # Draw three top frames (for columns A, B, C)
        if self.frame:
            market_layout = compute_market_frames_layout(self.frame, SCREEN_WIDTH)
            frame_width = market_layout["frame_width"]
            frame_height = market_layout["frame_height"]

            side_ph = self.placeholder_side or self.placeholder_market
            right_panel_layout = compute_right_panel_layout(
                market_layout,
                SCREEN_WIDTH,
                SCREEN_HEIGHT,
                side_ph,
                bottom_frame=self.bottom_frame,
            )
            right_frame_x = right_panel_layout["x"]
            right_frame_w = right_panel_layout["width"]
            right_bot_y = right_panel_layout["bottom_y"]
            right_bot_h = right_panel_layout["bottom_height"]

            # Draw Goal and Money ABOVE the right-side areas (as in screenshot)
            label_start_x = right_panel_layout["label_start_x"]
            # Move labels down so they don't sit over the playfield.
            margin_top = 90
            label_spacing = 15  # Spacing between Goal and Money
            value_spacing = 10  # Spacing between label and value
            min_right_margin = 20  # Minimum margin from right edge to prevent overflow
            
            # Draw Goal label and value
            goal_label = self.font_medium.render("Goal:", True, PAPER_COLOR)
            goal_value = self.font_medium.render(str(self.Goal), True, PAPER_COLOR)
            goal_label_x = label_start_x
            goal_label_y = margin_top
            goal_value_x = goal_label_x + goal_label.get_width() + value_spacing
            goal_value_y = margin_top
            # Ensure value doesn't go off screen
            if goal_value_x + goal_value.get_width() > SCREEN_WIDTH - min_right_margin:
                goal_value_x = SCREEN_WIDTH - min_right_margin - goal_value.get_width()
            self.screen.blit(goal_label, (goal_label_x, goal_label_y))
            self.screen.blit(goal_value, (goal_value_x, goal_value_y))
            
            # Draw Money label and value (below Goal)
            money_label = self.font_medium.render("Money:", True, PAPER_COLOR)
            money_value = self.font_medium.render(str(self.Money), True, PAPER_COLOR)
            money_label_x = label_start_x
            money_label_y = margin_top + goal_label.get_height() + label_spacing
            money_value_x = money_label_x + money_label.get_width() + value_spacing
            money_value_y = money_label_y
            # Ensure value doesn't go off screen
            if money_value_x + money_value.get_width() > SCREEN_WIDTH - min_right_margin:
                money_value_x = SCREEN_WIDTH - min_right_margin - money_value.get_width()

            bot_status_text = self._stock_bot_status_text()
            bot_status = self.font_small.render(bot_status_text, True, PAPER_COLOR) if bot_status_text else None
            bot_status_x = label_start_x
            bot_status_y = money_label_y + money_label.get_height() + 8
            if bot_status and bot_status_x + bot_status.get_width() > SCREEN_WIDTH - min_right_margin:
                bot_status_x = SCREEN_WIDTH - min_right_margin - bot_status.get_width()
            
            # Now that we know the label block height, move ONLY the top edge of the 6-slot frame down
            # so it sits neatly under the text, while preserving its bottom edge.
            label_bottom_y = bot_status_y + bot_status.get_height() if bot_status else money_label_y + money_label.get_height()
            desired_top_y = label_bottom_y + 30
            right_panel_layout = compute_right_panel_layout(
                market_layout,
                SCREEN_WIDTH,
                SCREEN_HEIGHT,
                side_ph,
                bottom_frame=self.bottom_frame,
                desired_top_y=desired_top_y,
            )
            right_top_y = right_panel_layout["top_y"]
            right_top_h = right_panel_layout["top_height"]

            # Draw frames (reuse Frame.png scaled to desired sizes)
            try:
                top_key = (int(right_frame_w), int(right_top_h))
                bot_key = (int(right_frame_w), int(right_bot_h))
                right_frame_top_img = self._scaled_frame_cache.get(top_key)
                if right_frame_top_img is None:
                    right_frame_top_img = pygame.transform.smoothscale(self.frame, top_key).convert_alpha()
                    self._scaled_frame_cache[top_key] = right_frame_top_img
                right_frame_bot_img = self._scaled_frame_cache.get(bot_key)
                if right_frame_bot_img is None:
                    right_frame_bot_img = pygame.transform.smoothscale(self.frame, bot_key).convert_alpha()
                    self._scaled_frame_cache[bot_key] = right_frame_bot_img
                self.screen.blit(right_frame_top_img, (right_frame_x, right_top_y))
                self.screen.blit(right_frame_bot_img, (right_frame_x, right_bot_y))
            except Exception:
                # Fallback: simple rects if scaling fails
                pygame.draw.rect(self.screen, BLACK, (right_frame_x, right_top_y, right_frame_w, right_top_h), 2)
                pygame.draw.rect(self.screen, BLACK, (right_frame_x, right_bot_y, right_frame_w, right_bot_h), 2)

            # Draw labels AFTER frames so text is never covered by the frame art
            self.screen.blit(goal_label, (goal_label_x, goal_label_y))
            self.screen.blit(goal_value, (goal_value_x, goal_value_y))
            self.screen.blit(money_label, (money_label_x, money_label_y))
            self.screen.blit(money_value, (money_value_x, money_value_y))
            if bot_status:
                self.screen.blit(bot_status, (bot_status_x, bot_status_y))
            
            # Draw three frames at the top, moved down 20px
            for frame_info in market_layout["frame_rects"]:
                i = frame_info["market"]
                frame_x = frame_info["x"]
                frame_y = frame_info["y"]
                self.screen.blit(self.frame, (frame_x, frame_y))
                # Draw corresponding logo in top-left corner of the frame
                logo = None
                if i == 0:
                    logo = self.logo_a
                elif i == 1:
                    logo = self.logo_b
                elif i == 2:
                    logo = self.logo_c
                if logo:
                    # Move logo 10px right and 10px down
                    logo_x = frame_x + 25
                    logo_y = frame_y + 20
                    self.screen.blit(logo, (logo_x, logo_y))
                    self._draw_market_probability_debug(
                        i,
                        logo_x + logo.get_width() + 8,
                        logo_y + 8,
                    )
                    
                    # ============================================================
                    # QP BLOCK - Quantity and Price Block
                    # ============================================================
                    # This block consists of 4 elements that must stay together:
                    # 1. Bundle of shares image (base position: bundle_x, bundle_y)
                    # 2. Quantity field (right of bundle, vertically centered)
                    # 3. Dollar image (10px right, 5px below bundle)
                    # 4. Price field (same X as quantity, vertically centered with Dollar)
                    # 
                    # IMPORTANT: To move the QP Block, only change bundle_x and bundle_y.
                    # All other positions are calculated relative to these coordinates.
                    # ============================================================
                    if self.bundle_image:
                        # Base position for QP Block - change these to move the entire block
                        # Use fixed logo height (128) to ensure all QP Blocks are at the same level
                        bundle_x = logo_x
                        bundle_y = logo_y + 128 + 5 + 30  # Fixed logo height (128) + 5px spacing + 30px down
                        self.screen.blit(self.bundle_image, (bundle_x, bundle_y))
                        
                        # Calculate text_x position (used for both quantity and price)
                        text_x = bundle_x + self.bundle_image.get_width() + 10  # 10px spacing from bundle image
                        
                        # Draw quantity text next to the bundle image (related data)
                        quantity = None
                        if i == 0:
                            quantity = self.Aquantity
                        elif i == 1:
                            quantity = self.Bquantity
                        elif i == 2:
                            quantity = self.Cquantity
                        
                        if quantity is not None:
                            # Position text to the right of the bundle image, vertically centered
                            quantity_text = self.font_small.render(str(quantity), True, PAPER_COLOR)
                            # Center text vertically with bundle image
                            text_y = bundle_y + (self.bundle_image.get_height() - quantity_text.get_height()) // 2
                            self.screen.blit(quantity_text, (text_x, text_y))
                        
                        # Draw Dollar image below the bundle image
                        if self.dollar_image:
                            dollar_x = bundle_x + 10  # 10px to the right
                            dollar_y = bundle_y + self.bundle_image.get_height() + 5  # 5px spacing below bundle image
                            self.screen.blit(self.dollar_image, (dollar_x, dollar_y))
                            
                            # Draw price text at the same level as Dollar image
                            price = None
                            if i == 0:
                                price = self.Aprice
                            elif i == 1:
                                price = self.BPrice
                            elif i == 2:
                                price = self.CPrice
                            
                            if price is not None:
                                price_text = self.font_small.render(str(price), True, PAPER_COLOR)
                                price_text_x = text_x  # Same x position as quantity field
                                # Center text vertically with Dollar image
                                price_text_y = dollar_y + (self.dollar_image.get_height() - price_text.get_height()) // 2
                                self.screen.blit(price_text, (price_text_x, price_text_y))

                # Draw arrows inside each frame (stacked vertically), size 60x60, start 25px from top
                if self.arrow_up and self.arrow_down and self.arrow_mid_up and self.arrow_mid_down:
                    arrow_size = 60
                    spacing_outer = 8  # spacing between 1-2 and 3-4
                    spacing_middle = 4  # reduced spacing between middle arrows (2-3)
                    # Order: top outer up, middle Arrow1 up, middle Arrow1 down, bottom outer down
                    arrows = [self.arrow_up, self.arrow_mid_up, self.arrow_mid_down, self.arrow_down]
                    total_height = (
                        len(arrows) * arrow_size
                        + spacing_outer * 2
                        + spacing_middle
                    )
                    arrow_x = frame_x + frame_width - arrow_size - 20  # inset from right edge
                    start_y = frame_y + 25  # place top arrow 25px below top of frame
                    # collect hitboxes for clickable outer arrows (two per frame)
                    for idx, arrow_img in enumerate(arrows):
                        if idx == 0:
                            ay = start_y
                        elif idx == 1:
                            ay = start_y + arrow_size + spacing_outer
                        elif idx == 2:
                            ay = start_y + arrow_size * 2 + spacing_outer + spacing_middle
                        else:  # idx == 3
                            ay = start_y + arrow_size * 3 + spacing_outer * 2 + spacing_middle
                        # Choose animated frame for outer arrows if animating
                        # Determine image (animated only for outer arrows per entry state)
                        img_to_draw = arrow_img
                        if idx == 0 and self.arrow_anim_frames:
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_anim_frames, "arrow_type": 0, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        elif idx == 1 and self.arrow_mid_up_frames:
                            # Middle up arrow with animation
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_mid_up_frames, "arrow_type": 1, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            else:
                                img_to_draw = arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        elif idx == 2 and self.arrow_mid_down_frames:
                            # Middle down arrow with animation
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_mid_down_frames, "arrow_type": 2, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            else:
                                img_to_draw = arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        elif idx == 3 and self.arrow_down_frames:
                            rect = pygame.Rect(arrow_x, ay, arrow_size, arrow_size)
                            entry = next((e for e in self.arrow_entries if e["rect"].topleft == rect.topleft), None)
                            if not entry:
                                entry = {"rect": rect, "animating": False, "idx": 0, "last": 0, "frames": self.arrow_down_frames, "arrow_type": 3, "frame_index": i}
                                self.arrow_entries.append(entry)
                            if entry["animating"]:
                                frame_idx = self.arrow_anim_sequence[entry["idx"]]
                                img_to_draw = entry["frames"][frame_idx] if entry["frames"] else arrow_img
                            self.screen.blit(img_to_draw, rect.topleft)
                        else:
                            self.screen.blit(img_to_draw, (arrow_x, ay))
                
                # Draw three placeholders at the bottom of each market frame (A, B, C)
                if self.placeholder_market:
                    market_placeholders = build_market_placeholders(frame_info["rect"], i)
                    self.market_placeholders.extend(market_placeholders)
                    for ph_info in market_placeholders:
                        ph_idx = ph_info["slot"]
                        ph_rect = ph_info["rect"]
                        ph_x, ph_y = ph_rect.topleft
                        self.screen.blit(self.placeholder_market, (ph_x, ph_y))
                        
                        # Draw card on market placeholder if one is placed there
                        if (
                            ph_idx in self.market_cards[i]
                            and self.market_cards[i][ph_idx] is not None
                            and not (
                                self.dragged_card_source == "market"
                                and self.dragged_card_market == i
                                and self.dragged_card_market_slot == ph_idx
                            )
                        ):
                            card_id = self.market_cards[i][ph_idx]
                            if card_id in self.card_images_market and self.card_images_market[card_id]:
                                # Use pre-scaled market card (no scaling on every frame)
                                # Center card on placeholder
                                card_x = ph_x - 1  # Center horizontally
                                card_y = ph_y - 1  # Center vertically
                                # Apply jump animation offset if card is jumping
                                jump_anim = self.card_jump_animations[i].get(ph_idx)
                                if jump_anim:
                                    card_y += int(jump_anim['offset_y'])
                                self.screen.blit(self.card_images_market[card_id], (card_x, card_y))
                                # Draw CardAction if this card has one
                                self.draw_card_action(card_id, card_x, card_y, self.card_size_market)
                                # Draw CardTurns if this card has one - use remaining turns from market_card_turns
                                remaining_turns = self.market_card_turns[i].get(ph_idx)
                                self.draw_card_turns(card_id, card_x, card_y, self.card_size_market, turns_remaining=remaining_turns)
                        # Highlight available market placeholder for dropping a card
                        highlight = False
                        # When dragging from hand: only FIRST free slot in each market is valid
                        if self.dragged_card_source == "hand" and dragged_hand_card_type != 2:
                            # find first free slot for this market
                            first_free = None
                            for s in range(len(market_placeholders)):
                                if self.market_cards[i].get(s) is None:
                                    first_free = s
                                    break
                            if first_free is not None and ph_idx == first_free:
                                highlight = True
                        # When dragging from market:
                        elif self.dragged_card_source == "market":
                            src_market = self.dragged_card_market
                            src_slot = self.dragged_card_market_slot
                            # 1) highlight the placeholder we dragged from (it becomes logically free)
                            if i == src_market and ph_idx == src_slot:
                                highlight = True
                            else:
                                # 2) for other markets, highlight only their FIRST free placeholder
                                if i != src_market:
                                    first_free = None
                                    for s in range(len(market_placeholders)):
                                        if self.market_cards[i].get(s) is None:
                                            first_free = s
                                            break
                                    if first_free is not None and ph_idx == first_free:
                                        highlight = True
                        if highlight:
                            pygame.draw.rect(self.screen, GOLD, ph_rect, 4)

                # Draw price animation in center of frame if currently animating this market
                if (self.current_price_animation and 
                    self.current_price_animation['market'] == i):
                    anim_frame_idx = self.current_price_animation['frame_idx']
                    anim_type = self.current_price_animation.get('type', 'unchanged')
                    
                    # Select frames based on animation type
                    if anim_type == 'unchanged' and self.price_unchanged_frames:
                        frames = self.price_unchanged_frames
                    elif anim_type == 'rise' and self.price_rise_frames:
                        frames = self.price_rise_frames
                    elif anim_type == 'fall' and self.price_fall_frames:
                        frames = self.price_fall_frames
                    else:
                        frames = []
                    
                    if frames and anim_frame_idx < len(frames):
                        anim_img = frames[anim_frame_idx]
                        # Center animation in frame (84x72) and move up by 20 pixels
                        anim_x = frame_x + (frame_width - self.animation_width) // 2
                        anim_y = frame_y + (frame_height - self.animation_height) // 2 - 20
                        self.screen.blit(anim_img, (anim_x, anim_y))

            self._draw_market_clear_animations()

            # ------------------------------------------------------------
            # Draw placeholders inside the right-side framed areas
            # ------------------------------------------------------------
            self.side_placeholders_top = []
            self.side_placeholders_bottom = []
            ph_img = self.placeholder_side or self.placeholder_market
            if ph_img:
                self.side_placeholders_top, self.side_placeholders_bottom = build_side_panel_placeholders(
                    right_panel_layout,
                    ph_img,
                )

                # If dragging a Type=2 card from hand, highlight ONLY the first free slot
                # on the TOP right-side panel (6 slots). Bottom (3 slots) must NOT be used.
                first_free_side_top = None
                if self.dragged_card_source == "hand" and dragged_hand_card_type == 2:
                    for s in range(len(self.side_cards_top)):
                        if self.side_cards_top[s] is None:
                            first_free_side_top = s
                            break

                for ph_info in self.side_placeholders_top:
                    slot = ph_info["slot"]
                    rect = ph_info["rect"]
                    self.screen.blit(ph_img, rect.topleft)

                    # Draw card if placed in this top slot
                    if 0 <= slot < len(self.side_cards_top):
                        card_id = self.side_cards_top[slot]
                    else:
                        card_id = None
                    if card_id is not None and not (
                        self.dragged_card_source == "side_top" and self.dragged_card_side_slot == slot
                    ):
                        img = (
                            self.card_images_side.get(card_id)
                            or self.card_images_market.get(card_id)
                            or self.card_images_bottom.get(card_id)
                        )
                        if img:
                            card_x = rect.x - 1
                            card_y = rect.y - 1
                            jump_anim = self.side_card_jump_animations.get(slot)
                            if jump_anim:
                                card_y += int(jump_anim['offset_y'])
                            self.screen.blit(img, (card_x, card_y))
                            self.draw_card_action(card_id, card_x, card_y, self.card_size_side)
                            self.draw_card_turns(card_id, card_x, card_y, self.card_size_side)

                    # Highlight first free top slot for Type=2 cards
                    if first_free_side_top is not None and slot == first_free_side_top:
                        pygame.draw.rect(self.screen, GOLD, rect, 4)

                for ph_info in self.side_placeholders_bottom:
                    slot = ph_info["slot"]
                    rect = ph_info["rect"]
                    self.screen.blit(ph_img, rect.topleft)
                    active_bottom_cards = self._active_lifecycle_cards()
                    if slot < len(active_bottom_cards):
                        card_id = active_bottom_cards[slot]
                        img = (
                            self.card_images_side.get(card_id)
                            or self.card_images_market.get(card_id)
                            or self.card_images_bottom.get(card_id)
                        )
                        if img:
                            card_x = rect.x - 1
                            card_y = rect.y - 1
                            jump_anim = self.lifecycle_card_jump_animations.get(slot)
                            if jump_anim:
                                card_y += int(jump_anim["offset_y"])
                            self.screen.blit(img, (card_x, card_y))
                            draw_bear_modifier_text(
                                self.screen,
                                card_id,
                                card_x,
                                card_y,
                                self.card_size_side,
                                self.font_path,
                                PAPER_COLOR,
                                modifier_percent=game_state.get_bear_goal_discount_percent(self.active_gold_cards),
                            )

        # Draw bottom frame (strategy cards area)
        if self.bottom_frame:
            hand_layout = compute_bottom_hand_layout(self.bottom_frame, self.hand, SCREEN_WIDTH, SCREEN_HEIGHT)
            bf_x = hand_layout["frame_x"] if hand_layout else (SCREEN_WIDTH - self.bottom_frame.get_width()) // 2 - 200
            bf_y = hand_layout["frame_y"] if hand_layout else SCREEN_HEIGHT - self.bottom_frame.get_height() - 150
            self.screen.blit(self.bottom_frame, (bf_x, bf_y))

            # Draw hand placeholders evenly inside bottom frame
            if hand_layout:
                self.bottom_placeholders = build_bottom_placeholders(hand_layout)
                ph_w = hand_layout["placeholder_width"]
                ph_h = hand_layout["placeholder_height"]

                for ph_info in self.bottom_placeholders:
                    i = ph_info["slot"]
                    slot_x, slot_y = ph_info["rect"].topleft
                    # Draw placeholder
                    if self.placeholder_bottom:
                        self.screen.blit(self.placeholder_bottom, (slot_x, slot_y))
                    else:
                        pygame.draw.rect(self.screen, WHITE, (slot_x, slot_y, ph_w, ph_h))
                        pygame.draw.rect(self.screen, BLACK, (slot_x, slot_y, ph_w, ph_h), 2)
                    
                    # Draw card on placeholder if available and not being dragged
                    if i < len(self.hand_cards) and i != self.dragged_card_index:
                        card_id = self.hand_cards[i]
                        # Если для этой карты есть анимация сдвига, не рисуем её в стандартной позиции
                        moving_from_this_slot = False
                        if self.hand_compact_anim:
                            for move in self.hand_compact_anim:
                                if move["from_index"] == i and move["card_id"] == card_id:
                                    moving_from_this_slot = True
                                    break
                        # Если для этого слота есть анимация добора, не рисуем карту в стандартной позиции
                        drawing_to_this_slot = False
                        if self.hand_draw_anim:
                            for draw_entry in self.hand_draw_anim:
                                if draw_entry["target_slot"] == i:
                                    drawing_to_this_slot = True
                                    break
                        if (
                            not moving_from_this_slot
                            and not drawing_to_this_slot
                            and card_id is not None
                            and card_id in self.card_images_bottom
                            and self.card_images_bottom[card_id]
                        ):
                            # Center card on placeholder (card is 4px larger)
                            card_x = slot_x - 2  # Center horizontally
                            card_y = slot_y - 2  # Center vertically
                            self.screen.blit(self.card_images_bottom[card_id], (card_x, card_y))
                            # Draw CardAction if this card has one
                            self.draw_card_action(card_id, card_x, card_y, self.card_size_bottom)
                            # Draw CardTurns if this card has one
                            self.draw_card_turns(card_id, card_x, card_y, self.card_size_bottom)
                    # Highlight available hand placeholder when dragging from market:
                    # only the ORIGINAL hand slot of this card
                    if self.dragged_card_source == "market":
                        src_market = self.dragged_card_market
                        src_slot = self.dragged_card_market_slot
                        origin_slot = self.market_card_origins[src_market].get(src_slot)
                        if origin_slot is not None and i == origin_slot and self.hand_cards[i] is None:
                            ph_rect = pygame.Rect(slot_x, slot_y, ph_w, ph_h)
                            pygame.draw.rect(self.screen, GOLD, ph_rect, 4)
                    # Highlight available hand placeholder when dragging from side-top:
                    # only the ORIGINAL hand slot of this card
                    if self.dragged_card_source == "side_top":
                        src_slot = self.dragged_card_side_slot
                        origin_slot = self.side_card_origins_top.get(src_slot)
                        if origin_slot is not None and i == origin_slot and self.hand_cards[i] is None:
                            ph_rect = pygame.Rect(slot_x, slot_y, ph_w, ph_h)
                            pygame.draw.rect(self.screen, GOLD, ph_rect, 4)
        
        # Draw dragged card on top of everything
        draw_dragged_cards(
            self.screen,
            self.dragged_card_source,
            self.dragged_card_index,
            self.dragged_card_market,
            self.dragged_card_market_slot,
            self.dragged_card_side_slot,
            self.dragged_card_pos,
            self.drag_offset,
            self.hand_cards,
            self.market_cards,
            self.side_cards_top,
            self.card_images_bottom,
            self.card_images_market,
            self.card_images_side,
            self.card_size_bottom,
            self.card_size_market,
            self.card_size_side,
            self.market_card_turns,
            self.draw_card_action,
            self.draw_card_turns,
        )

        # Draw hand compaction animations on top (когда карты плавно сдвигаются влево)
        if self.hand_compact_anim:
            draw_hand_compact_animations(
                self.screen,
                self.hand_compact_anim,
                self.card_images_bottom,
                self.card_size_bottom,
                self.draw_card_action,
                self.draw_card_turns,
            )
        
        # Draw hand draw animations on top (когда карты прилетают снизу экрана)
        if self.hand_draw_anim:
            draw_hand_draw_animations(
                self.screen,
                self.hand_draw_anim,
                self.card_images_bottom,
                self.card_size_bottom,
                self.draw_card_action,
                self.draw_card_turns,
            )
        
        # Draw Day counter and End Turn button in bottom-right corner
        if self.end_button and self.end_button_rect:
            end_button_image, end_button_draw_rect = self._get_end_button_draw_state()
            self.screen.blit(end_button_image, end_button_draw_rect)
            
            # Draw Day counter to the left of the button
            day_text = self.font_medium.render(f"Day: {self.Day} /{self.LastTurn}", True, PAPER_COLOR)
            day_text_x = self.end_button_rect.x - day_text.get_width() - 20  # 20px spacing from button
            day_text_y = self.end_button_rect.y + (self.end_button_rect.height - day_text.get_height()) // 2  # Vertically centered with button
            self.screen.blit(day_text, (day_text_x, day_text_y))

        self._draw_deck_toggle()
        self._draw_current_boss_marker()
        
        # Draw WinLose screen if win/lose state is active
        if self.win_lose_state is not None and self.win_lose_image:
            win_lose_y_draw = int(round(self.win_lose_y))
            # Draw WinLose window at centered position
            self.screen.blit(self.win_lose_image, (self.win_lose_x, win_lose_y_draw))
            
            # Draw appropriate Ok button based on win/lose state
            ok_button = None
            if self.win_lose_state == "win" and self.ok1_button:
                ok_button = self.ok1_button
            elif self.win_lose_state == "lose" and self.ok2_button:
                ok_button = self.ok2_button
            
            if ok_button:
                # Calculate button position relative to WinLose window
                winlose_width = self.win_lose_image.get_width()
                winlose_height = self.win_lose_image.get_height()
                ok_margin_right = 30
                ok_margin_bottom = 30
                ok_x = self.win_lose_x + winlose_width - self.ok_button_base_size[0] - ok_margin_right
                ok_y = win_lose_y_draw + winlose_height - self.ok_button_base_size[1] - ok_margin_bottom
                self.ok_button_rect = pygame.Rect(int(ok_x), int(ok_y), self.ok_button_base_size[0], self.ok_button_base_size[1])
                self.screen.blit(ok_button, (int(ok_x), int(ok_y)))
            
            # Draw text and cards on WinLose window
            winlose_width = self.win_lose_image.get_width()
            winlose_height = self.win_lose_image.get_height()
            
            if self.win_lose_state == "win":
                # Draw reward text - split into multiple lines if needed
                text_y = win_lose_y_draw + 75  # Top padding (40 + 35)
                max_text_width = winlose_width - 40  # Leave 20px margin on each side
                
                # Split text into lines if it's too long
                lines = wrap_text(self.reward_window_text, self.font_small, max_text_width)
                if self.is_boss_fight:
                    lines.extend(
                        wrap_text(
                            self.boss_victory_deck_reset_text,
                            self.font_small,
                            max_text_width,
                        )
                    )
                if self.long_payout_amount:
                    lines.extend(
                        wrap_text(
                            f"Long принес прибыль: {self.long_payout_amount} наполеондоров",
                            self.font_small,
                            max_text_width,
                        )
                    )
                
                # Draw text lines
                line_height = self.font_small.get_height() + 5
                for i, line in enumerate(lines):
                    text_surface = self.font_small.render(line, True, PAPER_COLOR)
                    text_x = self.win_lose_x + (winlose_width - text_surface.get_width()) // 2
                    self.screen.blit(text_surface, (text_x, text_y + i * line_height))
                
                # Draw reward cards below text
                if self.last_earned_cards:
                    text_bottom_y = text_y + len(lines) * line_height
                    card_start_y = text_bottom_y + 5  # 5px spacing (20 - 15)
                    card_width_winlose = 100  # Increased card size
                    card_spacing = 10  # Spacing between cards
                    total_cards_width = len(self.last_earned_cards) * card_width_winlose + (len(self.last_earned_cards) - 1) * card_spacing
                    card_start_x = self.win_lose_x + (winlose_width - total_cards_width) // 2  # Center cards
                    
                    for i, card_number in enumerate(self.last_earned_cards):
                        card_image = self._load_winlose_card(card_number)
                        if card_image:
                            card_x = card_start_x + i * (card_width_winlose + card_spacing)
                            self.screen.blit(card_image, (card_x, card_start_y))
            elif self.win_lose_state == "lose":
                # Draw lose text
                text_y = win_lose_y_draw + 85  # Top padding (50 + 35)
                text_surface = self.font_small.render(self.lose_window_text, True, PAPER_COLOR)
                text_x = self.win_lose_x + (winlose_width - text_surface.get_width()) // 2  # Center horizontally
                self.screen.blit(text_surface, (text_x, text_y))
            
            if not ok_button:
                # Debug: why button is not shown
                if self.win_lose_state == "lose":
                    print(f"DEBUG: Ok2 button not shown. ok2_button exists: {self.ok2_button is not None}, win_lose_state: {self.win_lose_state}")

        if self.deck_view_active:
            self._draw_deck_view()
        
        pygame.display.flip()
    
    def run(self):
        while True:
            result = self.handle_input()
            
            if result == "quit":
                pygame.quit()
                sys.exit()
            
            if result == "back":
                return "back"
            
            if result == "round_select":
                return "round_select"
            
            if result == "level_select":
                return "level_select"

            if self.deck_view_active:
                self.draw()
                self.clock.tick(FPS)
                continue
            
            # Update dragged card position every frame for maximum smoothness
            # This ensures position is updated even if MOUSEMOTION events are missed
            if self.dragged_card_source is not None:
                self.dragged_card_pos = pygame.mouse.get_pos()
            
            # Update arrow animation timing
            self.update_arrow_animation()
            
            # Update price animation timing
            self.update_price_animation()

            # Update card jump animations
            self.update_card_jump_animations()
            self.update_side_card_jump_animations()
            self.update_market_clear_animations()
            
            # Update sequential processing of cards 11-18
            self.update_cards_11_14_processing()
            self._maybe_finalize_after_effect_animations()

            # Update hand compaction animation after end turn
            self.update_hand_compact_animation()
            
            # Update hand draw animation (cards flying in from bottom)
            self.update_hand_draw_animation()
            
            # Update win/lose screen animation
            self.update_win_lose_animation()

            self.draw()
            self.clock.tick(FPS)
