import pygame
import random
import sys
import os

import game_state
import profile_manager
from asset_loaders import load_scaled_image, load_scaled_image_variants
from boss_logic import (
    apply_boss_functionality,
    apply_boss_reward,
    get_boss_level_from_number,
    get_category_two_start_b_shares,
    get_bosses_required,
    get_boss_number_from_filename,
    get_boss_number_from_index,
)
from card_catalog import (
    BID_CARD_VALUES,
    BLUE_CHIPS_CARD_ID,
    CATALYST_PERCENTAGE_POINTS,
    GOLD_CATALYST_PERCENTAGE_POINTS,
    GOLD_DISCLOSURE_PERCENTAGE_POINTS,
    GOLD_DOWNSIDE_RISK_CARD_ID,
    GOLD_ADVANCE_BASE_CHANCE,
    GOLD_CONCENTRATION_CARD_ID,
    GOLD_FULL_DEPLOYMENT_CARD_ID,
    GOLD_FULL_DEPLOYMENT_REWARD,
    GOLD_UPTREND_PERCENT_PER_NAPOLEONDOR,
    GOLD_SELLING_PRESSURE_CARD_ID,
    GOLD_SHAREHOLDER_BASE_CARD_ID,
    GOLD_WATERLOO_BASE_CHANCE,
    GOLD_WATERLOO_CARD_ID,
    PRICE_CARD_IDS,
    REGULATION_CARD_IDS,
    SILVER_CONCENTRATION_CARD_ID,
    SILVER_NABOB_CARD_ID,
)
from game_data import (
    REWARD_TOKEN_RANDOM_RED,
    REWARD_TOKEN_RANDOM_SILVER,
    load_boss_rewards,
    load_cards_config,
    load_rewards_config,
    load_rounds_config,
)
from game_stats import (
    build_difficulty_label,
    build_round_label,
    build_sequential_round_number,
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
    load_winlose_card_preview,
)
from gameplay_deck import (
    get_card_investment_bonus,
    restore_card_instance,
    serialize_card_instance,
    setup_starting_deck_and_hand,
)
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
    GAMBLING_PROBABILITY_BONUS,
    apply_market_price_change,
    build_market_probabilities,
    build_stock_price_animation_queue,
    calculate_price_setting_card_prices,
    compute_slide_position,
    get_card_type_from_config,
    protect_market_prices,
    update_arrow_animation_entries,
)
from gameplay_pause import build_pause_menu_layout, draw_pause_menu, get_pause_menu_action
from gameplay_trade_actions import apply_arrow_trade, calculate_rebate_sale_percent
from gameplay_turn import (
    advance_price_animation_frame,
    build_price_cards_processing_queue,
    calculate_price_card_prices,
    get_price_animation_frames,
    lock_market_cards,
    lock_side_cards,
    start_next_price_animation,
)
from gameplay_winlose import (
    apply_win_reward,
    build_win_result_layout,
    get_win_lose_start_y,
    resolve_win_lose_state,
)
from shared_utils import _clamp_dt_seconds, move_towards, wrap_text
from silver_black_page import (
    CARD_TOOLTIPS as LIFECYCLE_CARD_TOOLTIPS,
    is_markdown_effective_for_round,
)
from shop_page import SPECIAL_ASSETS as SHOP_SPECIAL_ASSETS
from shop_page import SPECIAL_DESCRIPTIONS as SHOP_SPECIAL_DESCRIPTIONS


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60
SPOOFING_REMINDER_DURATION_MS = 2200
SPOOFING_REMINDER_FRAME_MS = 45
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
PAPER_COLOR = (83, 76, 70)
LEVEL6_STARTING_A_SHARES = 2
LEVEL6_EXPERIMENT_TURNS = 8
LEVEL6_BOT_THINK_MS = 600
LEVEL6_BOT_ACTION_MS = 2000
LEVEL6_BOT_END_PRESS_MS = 650

FIELD_CARD_TOOLTIPS = {
    1: ("Upside", "Немного усиливает вероятность роста выбранной акции."),
    2: ("Upside", "Усиливает вероятность роста выбранной акции."),
    3: ("Downside", "Немного усиливает вероятность падения выбранной акции."),
    4: ("Downside", "Усиливает вероятность падения выбранной акции."),
    11: ("Gain", "Увеличивает цену выбранной акции на 2 в течение 1 хода."),
    12: ("Gain", "Увеличивает цену выбранной акции на 2 в течение 2 ходов."),
    13: ("Gain", "Увеличивает цену выбранной акции на 4 в течение 1 хода."),
    14: ("Gain", "Увеличивает цену выбранной акции на 4 в течение 2 ходов."),
    15: ("Drop", "Снижает цену выбранной акции на 2 в течение 1 хода."),
    16: ("Drop", "Снижает цену выбранной акции на 2 в течение 2 ходов."),
    17: ("Gain ×2", "Умножает цену выбранной акции на 2 в течение 1 хода."),
    18: ("Gain ×2", "Умножает цену выбранной акции на 2 в течение 2 ходов."),
    20: ("Regulation", "Случайное движение выбранной акции будет Flat в течение 2 ходов."),
    21: ("Regulation", "Случайное движение выбранной акции будет Flat в течение 3 ходов."),
    22: ("Blue Chips", "Выбранные акции никогда не будут падать. Никакие карты не смогут опустить их цену. Всегда приходит в стартовой руке."),
    100: ("Shareholder", "Это бесполезная карта. Она ничего не делает и только занимает место."),
    110: ("Rebate", "В последний ход автоматически продаёт все оставшиеся акции за 90% их стоимости."),
    111: ("Deleverage", "Удаляет все карты, выложенные на трёх рынках."),
    112: ("Rollover", "Добавляет 1 ход всем Gain, Drop и Regulation-картам, включая уже выложенные."),
    113: ("Bankruptcy A", "Устанавливает цену акций компании A на 2."),
    114: ("Bankruptcy B", "Устанавливает цену акций компании B на 2."),
    115: ("Bankruptcy C", "Устанавливает цену акций компании C на 2."),
    116: ("Futures", "Добавляет 1 ход к длительности раунда."),
    117: ("Crash", "Устанавливает цены всех трёх акций на 2."),
    118: ("BID 10", "Устанавливает цены всех трёх акций на 10."),
    119: ("BID 20", "Устанавливает цены всех трёх акций на 20."),
    120: ("BID 30", "Устанавливает цены всех трёх акций на 30."),
    121: ("BID 50", "Устанавливает цены всех трёх акций на 50."),
    122: ("BID 100", "Устанавливает цены всех трёх акций на 100."),
    123: ("Parity", "Устанавливает цены всех трёх акций на их среднее значение с округлением до целого."),
    124: ("Accumulation", "Удваивает номинал и длительность следующей выложенной Gain или Drop-карты. Эффект не переносится в следующий раунд."),
    125: ("Breakout", "На последнем игровом ходу с шансом 50% удваивает цены акций, которыми владеет игрок."),
}
FIELD_CARD_TOOLTIPS.update(LIFECYCLE_CARD_TOOLTIPS)

DISCLOSURE_CARD_TOOLTIPS = {
    302: (
        "Golden Stocks",
        "В конце победного раунда может дать случайную золотую карту. После неудачи шанс увеличивается на 2 процентных пункта; в новом забеге сбрасывается до 10%.",
    ),
    407: (
        "Rebate",
        "Продаёт акции дороже их стоимости. Каждое падение акций A увеличивает процент продажи ещё на 2 пункта.",
    ),
    410: (
        "Uptrend",
        "Добавляет к эффекту Rebate по 2 процентных пункта за каждый целый имеющийся наполеондор.",
    ),
    430: (
        "Waterloo",
        "Показывает следующий рыночный бросок и позволяет переиграть текущий ход.",
    ),
}


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
        active_lifecycle_card_order=None,
        positioning_start_cards=None,
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
        self.round_start_napoleondors = float(game_state.napoleondors or 0)
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
        if int(self.level_number or 0) == 6 and self.is_boss_fight:
            self.active_silver_cards = []
            self.active_black_cards = []
            self.active_gold_cards = []
            active_lifecycle_card_order = []
            positioning_start_cards = []
        self.active_lifecycle_card_order = self._normalize_active_lifecycle_card_order(active_lifecycle_card_order)
        self.positioning_start_cards = list(positioning_start_cards or [])
        try:
            self.insurance_goal_debt = max(0, int(insurance_goal_debt or 0))
        except (TypeError, ValueError):
            self.insurance_goal_debt = 0
        if active_gold_cards is not None and not self._is_level6_alternating_battle():
            game_state.set_active_gold_cards(self.active_gold_cards)
        self.insider_c_growth_turns_remaining = 2 if self._count_active_silver_card(405) > 0 else 0
        self.rebate_a_fall_bonus_percent = 0
        self.short_seller_fall_counts = [0, 0, 0]
        self.short_seller_counted_markets_this_resolution = set()
        self.surge_turns_without_trade = 0
        self.surge_traded_this_turn = False
        self.surge_triggered = False
        self.continuation_growth_streaks = [0, 0, 0]
        self.continuation_held_markets_this_turn = set()
        self.continuation_applied_this_resolution = False
        self.continuation_animation_phase = False
        self.active_silver_cards_spent = False
        self.forward_trading_shareholder_count = 0
        self.boss_steals_shares = False
        self.boss_odd_turn_trading_only = False
        self.boss_forbid_price_2_buys = False
        self.boss_limit_red_gain_drop_per_turn = False
        self.boss_block_card_turn_extensions = False
        self.boss_market_slots_per_market = 3
        self.boss_round_napoleondor_multiplier = 1.0
        self.boss_burns_cash_end_turn = False
        self.boss_turn_time_limit_seconds = 0
        self.boss_turn_timer_remaining_ms = 0
        self.boss_turn_timer_last_tick = pygame.time.get_ticks()
        self.stock_bot_enabled = False
        self.stock_bot = None
        self._stock_bot_saved_state = None
        self.stock_bot_type = "simple"
        self.stock_bot_start_quantities = None
        self.stock_bot_blocked_buy_prices = set()
        self.stock_bot_trade_history = []
        self.level6_turn_owner = "player"
        self.level6_bot_turn_phase = None
        self.level6_bot_turn_started_at = 0
        self.level6_bot_turn_decision = None
        self.stock_bot_acted_this_resolution = False
        
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
        self.disclosure_tooltip_title_font = pygame.font.Font(font_path, 27)
        self.disclosure_tooltip_text_font = pygame.font.Font(font_path, 22)
        self.boss_round_label_font = pygame.font.Font(font_path, 30)
        self.pause_title_font = pygame.font.Font(font_path, 54)
        self.pause_button_font = pygame.font.Font(font_path, 38)
        self.pause_small_font = pygame.font.Font(font_path, 28)
        self.pause_menu_active = False
        self.pause_menu_requested = False
        self.pause_restart_confirmation = False
        
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
        self.dimmed_arrow_cache = {}

        self.bottom_frame = gameplay_assets["bottom_frame"]
        self.arrow_sound = gameplay_assets["arrow_sound"]
        self.typewriter_sound = gameplay_assets["typewriter_sound"]
        self.cash_register_sound = gameplay_assets.get("cash_register_sound")
        self.card_placing_sound = gameplay_assets.get("card_placing_sound")
        self.card_taking_sound = gameplay_assets.get("card_taking_sound")
        self.animation_width = gameplay_assets["animation_width"]
        self.animation_height = gameplay_assets["animation_height"]
        self.price_unchanged_frames = gameplay_assets["price_unchanged_frames"]
        self.price_rise_frames = gameplay_assets["price_rise_frames"]
        self.price_fall_frames = gameplay_assets["price_fall_frames"]

        # Price animation state (for sequential playback)
        self.price_animation_queue = []  # Price animations; grouped effects may target multiple markets at once.
        self.stock_price_turn_results = []
        self.waterloo_preview_movements = None
        self.current_price_animation = None  # Current animation: {'market': 0-2, 'type': 'unchanged'|'rise', 'frame_idx': int, 'last_update': ms}
        self.basket_trading_applied_this_resolution = False
        self.sideway_applied_this_resolution = False
        self.c_price_fell_this_resolution = False
        self.manipulation_applied_this_resolution = False
        self.price_animation_speed = 12  # frames per second (increased by 30% from 9 to 12, approximately 83ms per frame)
        self.price_animation_interval = 1000 // self.price_animation_speed  # ms per frame

        self.logo_a = gameplay_assets["logo_a"]
        self.logo_b = gameplay_assets["logo_b"]
        self.logo_c = gameplay_assets["logo_c"]

        # Shared rewards config keeps the existing shape but removes duplicated CSV parsing.
        self.rewards = dict(load_rewards_config())

        self.bundle_image = gameplay_assets["bundle_image"]
        self.dollar_image = gameplay_assets["dollar_image"]
        self.napoleondor_image = gameplay_assets["napoleondor_image"]

        # Initialize quantity variables
        self.Aquantity = LEVEL6_STARTING_A_SHARES if int(self.level_number or 0) == 6 else 2
        self.Bquantity = 0
        self.Cquantity = int(game_state.global_start_c_shares_bonus or 0)

        # Initialize price variables
        self.Aprice = 2
        self.BPrice = 2
        self.CPrice = 2
        self._apply_issue_price_start()

        # Initialize step variables (price change steps)
        self.StepA = 2
        self.StepB = 4
        self.StepC = 6
        self._apply_volatility_steps()

        # Initialize game state variables
        self.Goal = goal if goal is not None else 0  # Use passed goal or default to 0
        self._apply_bear_goal_modifier()
        self._apply_markdown_goal_modifier()
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
        
        # Boss modifiers are applied once from BossRewards.csv below.
        base_last_turn = 8 + game_state.global_last_turn_bonus  # Default LastTurn value plus boss reward bonuses
        self.LastTurn = (
            LEVEL6_EXPERIMENT_TURNS
            if self._is_level6_alternating_battle()
            else base_last_turn
        )

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
        self.hand = (
            0
            if self._is_level6_alternating_battle()
            else max(1, 7 + int(game_state.global_hand_bonus or 0))
        )
        
        # Apply boss functionalities AFTER hand is initialized (e.g., "Self.hand=Self.hand-1", "LastTurn=LastTurn-1")
        # IMPORTANT: Functionalities apply to ALL rounds (regular E/M/H rounds AND boss round) after boss selection
        # After boss victory, modifiers are reset - next boss/rounds use default values
        if self.boss_index is not None:  # Boss was selected (applies to both regular rounds and boss fight)
            boss_number = self._get_active_boss_number()
            if boss_number and not self._is_level6_alternating_battle():
                boss_rewards = load_boss_rewards()
                boss_entry = boss_rewards.get(boss_number) or {}
                func_string = boss_entry.get("Functionalities", "").strip()
                
                # Apply functionalities (e.g., "Self.hand=Self.hand-1", "LastTurn=LastTurn-1")
                if func_string:
                    apply_boss_functionality(func_string, self)
                    print(f"Applied boss functionality for boss {boss_number} (applies to all rounds): {func_string}")

            self._configure_boss_stock_bot()

        self._apply_frugality_turn_bonus()
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
        self.deck_view_offer_image_cache = {}
        self.deck_view_card_entries = []
        self.deck_view_offer_entries = []
        self.hedger_used_this_round = 0
        self.hedger_selected_card_id = None
        self.hedger_confirm_active = False
        self.hedger_message = ""
        self.hedger_message_until = 0
        self.hedger_add_button_rect = None
        self.hedger_yes_button_rect = None
        self.hedger_no_button_rect = None
        self.full_deployment_reward_applied = False
        
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

        negative_path = os.path.join("Cards", "Arts", "Negative.png")
        self.negative_card_overlays = load_scaled_image_variants(
            negative_path,
            (
                self.card_size_bottom,
                self.card_size_market,
                self.card_size_side,
            ),
            warning_message="WARNING: Negative card overlay not found:",
        )

        # Right-side placeholder areas (top: 6 slots, bottom: 3 slots)
        # These are populated in draw() for hit-testing / future drag&drop.
        self.side_placeholders_top = []   # [{'slot': int, 'rect': Rect}]
        self.side_placeholders_bottom = []  # [{'slot': int, 'rect': Rect}]
        
        card_assets = load_gameplay_card_assets(
            self.card_types,
            self.card_size_bottom,
            self.card_size_market,
            self.card_size_side,
            # Only the silver-deck preview scales directly from full-size originals.
            original_card_ids={
                REWARD_TOKEN_RANDOM_SILVER,
                *(card_id for card_id, card_type in self.card_types.items() if card_type == 3),
            },
        )
        self.card_images_original = card_assets["card_images_original"]
        self.card_images_bottom = card_assets["card_images_bottom"]
        self.card_images_market = card_assets["card_images_market"]
        self.card_images_side = card_assets["card_images_side"]
        self.card_actions = card_assets["card_actions"]
        self.card_turns = card_assets["card_turns"]
        self._apply_silver_rollover_bonus()
        
        game_state.migrate_legacy_forced_start_hand_cards(self.level_number)
        gold_concentration_active = any(
            int(card_id) == GOLD_CONCENTRATION_CARD_ID
            for card_id in self.active_gold_cards
        )
        silver_concentration_active = any(
            int(card_id) == SILVER_CONCENTRATION_CARD_ID
            for card_id in self.active_silver_cards
        )
        concentration_active = gold_concentration_active or silver_concentration_active
        self.deck, self.hand_cards = setup_starting_deck_and_hand(
            self.level_number,
            self.hand,
            game_state.earned_reward_cards,
            level_completion_reward_cards=game_state.get_completed_level_reward_cards(),
            removed_cards_by_level=game_state.removed_deck_cards_by_level,
            shop_deck_cards=game_state.shop_deck_cards,
            temporary_reward_cards_by_level=game_state.round_reward_cards,
            guaranteed_cards_by_level=game_state.guaranteed_start_hand_cards_by_level,
            investment_card_bonuses=game_state.get_active_investment_card_bonuses(),
            round_guaranteed_cards=self.positioning_start_cards,
            mirrored_cards=game_state.mirrored_deck_cards,
            concentration_active=concentration_active,
            concentration_removes_starting_shareholder=gold_concentration_active,
            guaranteed_drop_count=self._get_downside_risk_guaranteed_drop_count(),
        )
        if self._is_level6_alternating_battle():
            self.deck = []
            self.hand_cards = []
        self.shareholder_effect_count = sum(
            1 for card_id in list(self.deck or []) + list(self.hand_cards or []) if card_id == 100
        )
        self.shareholder_blocked_market = None
        
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
        # Per-instance action overrides, used by effects such as Accumulation.
        self.market_card_actions = {0: {}, 1: {}, 2: {}}
        # Side-panel slots whose Accumulation charge is still waiting to be consumed.
        self.accumulation_pending_sources = []
        self.accumulation_stephenson_card_played_this_turn = False

        # Jump animation state for persistent market cards.
        self.card_jump_animations = {0: {}, 1: {}, 2: {}}
        self.side_card_jump_animations = {}
        self.lifecycle_card_jump_animations = {}
        self.lifecycle_card_scale_animations = {}
        self.lifecycle_card_shake_animations = {}
        self.lifecycle_reminder_days_started = set()
        self.market_clear_animations = []
        self.market_clear_animation_duration = 520
        
        # Queue for processing persistent price-effect cards in market/slot order.
        self.price_card_queue = []
        self.current_card_processing = None  # (market, slot) currently being processed
        self.card_processing_start_time = 0
        self.card_processing_delay = 300  # ms delay between processing each card
        self.turn_resolution_active = False
        self.effect_finalize_pending = False
        self.red_effects_applied_this_resolution = False
        self.hand_negative_overlay_hold = {"red": False, "market": False}

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
        self.final_auto_liquidation_animation = None
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
        self.finance_report_image = winlose_assets.get("finance_report_image")
        self.card_report_image = winlose_assets.get("card_report_image")
        self.approve_stamp_image = winlose_assets.get("approve_stamp_image")
        self.stamp_on_paper_image = winlose_assets.get("stamp_on_paper_image")
        self.stamp_sound = winlose_assets.get("stamp_sound")
        self.report_rustle_sound = winlose_assets.get("report_rustle_sound")
        self.approve_stamp_rotated = (
            pygame.transform.rotate(self.approve_stamp_image, 10).convert_alpha()
            if self.approve_stamp_image else None
        )
        self.result_report_stage = "cards"
        self.finance_report_y = float(
            SCREEN_HEIGHT + 30 if self.finance_report_image else 0
        )
        self.finance_report_target_y = float(
            (SCREEN_HEIGHT - self.finance_report_image.get_height()) // 2
            if self.finance_report_image else 0
        )
        self.finance_report_entries = []
        self.finance_stamp_state = "idle"
        self.finance_stamp_started_at = 0
        self.finance_stamp_rect = None
        self.result_transition_ready = None
        
        # Store last earned reward cards for WinLose window display
        self.last_earned_cards = []  # List of card numbers earned in this round
        self.last_earned_napoleondors = 0
        self.long_payout_amount = 0
        self.golden_stocks_reward_card = None
        self.random_boss_reward_text = None
        
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
        self.reward_level3_final_boss_text = self._get_text(
            "RewardLevel3FinalBoss",
            "Вы разблокировали четвёртый уровень. Вы получили свою первую чёрную карту.",
        )
        self.reward_level4_final_boss_text = self._get_text(
            "RewardLevel4FinalBoss",
            "Вы завершили четвёртый уровень!",
        )
        self.reward_level5_final_boss_text = self._get_text(
            "RewardLevel5FinalBoss",
            "You completed level five!",
        )
        self.boss_victory_deck_reset_text = self._get_text(
            "BossVictoryDeckReset",
            "Временные награды обычных раундов сброшены.",
        )
        self.lose_window_text = self._get_text("LoseWindowText", "LoseWindowText")
        
        # Cache for WinLose window reward card images
        self.winlose_card_images = {}
        self.winlose_scaled_card_images = {}
        self._restore_saved_state(self._initial_saved_state)
        if not isinstance(self._initial_saved_state, dict) or "shareholder_blocked_market" not in self._initial_saved_state:
            self._roll_shareholder_market_shutdown()
        if self.boss_index is not None:
            # Normalize old saves that may have enabled a stock bot for a
            # level-5 category-one boss under the former blanket rule.
            self._configure_boss_stock_bot()
        if not self._is_stock_bot_allowed():
            self.stock_bot_enabled = False
            self.stock_bot = None
            self._stock_bot_saved_state = None
        self._activate_stock_bot_if_needed()
        self._apply_contango_gain_drop_bonuses()
        if not isinstance(self._initial_saved_state, dict) or "boss_turn_timer_remaining_ms" not in self._initial_saved_state:
            self._reset_boss_turn_timer()
        else:
            self.boss_turn_timer_last_tick = pygame.time.get_ticks()
        if self._apply_risk_premium_round_start_bonus():
            self._save_active_game()
        self._start_lifecycle_turn_reminder()

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

    def _is_hedger_available(self):
        return int(getattr(self, "hedger_used_this_round", 0) or 0) < self._count_active_silver_card(408)

    def _find_free_hand_slot(self):
        for index, card_id in enumerate(self.hand_cards):
            if card_id is None:
                return index
        return None

    def _set_hedger_message(self, text, duration_ms=1600):
        self.hedger_message = str(text or "")
        self.hedger_message_until = pygame.time.get_ticks() + int(duration_ms or 0)

    def _clear_hedger_selection(self):
        self.hedger_selected_card_id = None
        self.hedger_confirm_active = False
        self.hedger_add_button_rect = None
        self.hedger_yes_button_rect = None
        self.hedger_no_button_rect = None

    def _select_hedger_deck_card(self, card_id):
        if not self._is_hedger_available():
            return False
        try:
            int(card_id)
        except (TypeError, ValueError):
            return False
        if not any(candidate is card_id for candidate in self.deck):
            return False
        self.hedger_selected_card_id = card_id
        self.hedger_confirm_active = False
        self.hedger_message = ""
        return True

    def _add_hedger_selected_card_to_hand(self):
        if not self._is_hedger_available() or self.hedger_selected_card_id is None:
            return False
        free_slot = self._find_free_hand_slot()
        if free_slot is None:
            self._set_hedger_message("Нет места")
            self.hedger_confirm_active = False
            return False

        selected_index = next(
            (
                index
                for index, card_id in enumerate(self.deck)
                if card_id is self.hedger_selected_card_id
            ),
            None,
        )
        if selected_index is None:
            self._set_hedger_message("Карта не найдена")
            self._clear_hedger_selection()
            return False

        selected_card = self.deck.pop(selected_index)
        self.hand_cards[free_slot] = selected_card
        self.hedger_used_this_round = int(getattr(self, "hedger_used_this_round", 0) or 0) + 1
        self._set_hedger_message("Карта добавлена")
        self._clear_hedger_selection()
        self._save_active_game()
        return True

    def _load_defeated_boss_icon(self, boss_filename):
        if not boss_filename:
            return None
        if boss_filename in self.defeated_boss_icon_cache:
            return self.defeated_boss_icon_cache[boss_filename]

        path = os.path.join("Bosses", boss_filename)
        icon = None
        if os.path.exists(path):
            icon = load_scaled_image(path, target_size=(102, 102))
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
            icon = load_scaled_image(path, target_size=(74, 74))
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
        if getattr(self, "arrow_sound", None):
            self.arrow_sound.play()

    def _play_card_placing_sound(self):
        sound = getattr(self, "card_placing_sound", None)
        if sound:
            sound.play()

    def _play_card_taking_sound(self):
        sound = getattr(self, "card_taking_sound", None)
        if sound:
            sound.play()

    def _start_end_button_press_animation(self, duration_ms=110):
        self.end_button_press_until = pygame.time.get_ticks() + max(1, int(duration_ms or 0))

    def _enable_boss_turn_timer(self, seconds):
        try:
            self.boss_turn_time_limit_seconds = max(0, int(seconds or 0))
        except (TypeError, ValueError):
            self.boss_turn_time_limit_seconds = 0
        self._reset_boss_turn_timer()

    def _reset_boss_turn_timer(self):
        self.boss_turn_timer_remaining_ms = max(
            0,
            int(getattr(self, "boss_turn_time_limit_seconds", 0) or 0) * 1000,
        )
        self.boss_turn_timer_last_tick = pygame.time.get_ticks()
        return self.boss_turn_timer_remaining_ms

    def _is_boss_turn_timer_counting(self):
        return (
            int(getattr(self, "boss_turn_time_limit_seconds", 0) or 0) > 0
            and self.win_lose_state is None
            and not self.pause_menu_active
            and not self.deck_view_active
            and not self._is_turn_resolution_active()
            and not self._is_hand_transition_active()
        )

    def _update_boss_turn_timer(self):
        if int(getattr(self, "boss_turn_time_limit_seconds", 0) or 0) <= 0:
            return False
        now = pygame.time.get_ticks()
        try:
            last_tick = int(getattr(self, "boss_turn_timer_last_tick", now))
        except (TypeError, ValueError):
            last_tick = now
        self.boss_turn_timer_last_tick = now
        if not self._is_boss_turn_timer_counting():
            return False
        elapsed = max(0, now - last_tick)
        self.boss_turn_timer_remaining_ms = max(
            0,
            int(getattr(self, "boss_turn_timer_remaining_ms", 0) or 0) - elapsed,
        )
        if self.boss_turn_timer_remaining_ms > 0:
            return False
        return self._start_turn_resolution()

    def _get_boss_turn_timer_seconds(self):
        remaining_ms = max(0, int(getattr(self, "boss_turn_timer_remaining_ms", 0) or 0))
        return (remaining_ms + 999) // 1000

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
        if self._is_level6_alternating_battle():
            return
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
        self.deck_view_card_entries = []
        card_w, card_h = self.card_size_market
        gap_x = 22
        gap_y = 34
        padding_x = 70
        padding_y = 55
        active_offer_entries = game_state.get_active_shop_offer_effects(
            self.level_number,
            self.defeated_count,
        )
        footer_strip_height = 300 if game_state.active_silver_cards_deck or active_offer_entries else 160
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
            card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
            self.deck_view_card_entries.append({"card_id": card_id, "rect": card_rect})
            self.screen.blit(image, (card_x, card_y))
            self.draw_card_action(card_id, card_x, card_y, self.card_size_market)
            self.draw_card_turns(card_id, card_x, card_y, self.card_size_market)
            if self._is_hedger_available() and self.hedger_selected_card_id is card_id:
                pygame.draw.rect(self.screen, GOLD, card_rect.inflate(8, 8), 4, border_radius=4)

        self._draw_silver_deck_preview(panel)
        self._draw_defeated_boss_rewards(panel)
        self._draw_active_shop_offers(panel, active_offer_entries)
        self._draw_hedger_deck_controls(panel)
        self._draw_deck_toggle()

    def _draw_hedger_deck_controls(self, panel):
        self.hedger_add_button_rect = None
        self.hedger_yes_button_rect = None
        self.hedger_no_button_rect = None

        if not self._count_active_silver_card(408):
            return

        y = panel.bottom - 64
        hedger_count = self._count_active_silver_card(408)
        hedger_used = int(getattr(self, "hedger_used_this_round", 0) or 0)
        if hedger_used >= hedger_count:
            text = self.font_small.render("Hedger использован", True, PAPER_COLOR)
            self.screen.blit(text, text.get_rect(center=(panel.centerx, y)))
            return

        if self.hedger_message and pygame.time.get_ticks() < self.hedger_message_until:
            text = self.font_small.render(self.hedger_message, True, PAPER_COLOR)
            self.screen.blit(text, text.get_rect(center=(panel.centerx, y - 48)))

        if self.hedger_selected_card_id is None:
            prompt = self.font_small.render("Выберите карту из колоды", True, PAPER_COLOR)
            self.screen.blit(prompt, prompt.get_rect(center=(panel.centerx, y)))
            return

        if self.hedger_confirm_active:
            prompt = self.font_small.render(
                f"Добавить карту {self.hedger_selected_card_id} в руку?",
                True,
                PAPER_COLOR,
            )
            self.screen.blit(prompt, prompt.get_rect(center=(panel.centerx, y - 46)))
            self.hedger_yes_button_rect = pygame.Rect(panel.centerx - 150, y - 20, 120, 54)
            self.hedger_no_button_rect = pygame.Rect(panel.centerx + 30, y - 20, 120, 54)
            self._draw_deck_view_button(self.hedger_yes_button_rect, "Да")
            self._draw_deck_view_button(self.hedger_no_button_rect, "Нет")
            return

        self.hedger_add_button_rect = pygame.Rect(panel.centerx - 170, y - 24, 340, 58)
        self._draw_deck_view_button(self.hedger_add_button_rect, "Добавить в руку")

    def _draw_deck_view_button(self, rect, text):
        mouse_pos = pygame.mouse.get_pos()
        color = (248, 239, 216) if rect.collidepoint(mouse_pos) else (238, 228, 205)
        pygame.draw.rect(self.screen, color, rect, border_radius=7)
        pygame.draw.rect(self.screen, PAPER_COLOR, rect, 2, border_radius=7)
        label = self.font_small.render(text, True, PAPER_COLOR)
        self.screen.blit(label, label.get_rect(center=rect.center))

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

    def _build_active_shop_offer_rects(self, panel, offer_count):
        try:
            count = max(0, int(offer_count or 0))
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return []

        side_padding = 76
        gap = 12
        available_width = panel.width - side_padding * 2
        max_width = (available_width - gap * (count - 1)) // count
        card_w = max(34, min(50, int(max_width)))
        card_h = max(54, int(card_w / (561 / 886.0)))
        total_width = count * card_w + (count - 1) * gap
        start_x = panel.x + (panel.width - total_width) // 2
        y = panel.bottom - 365
        return [
            pygame.Rect(start_x + index * (card_w + gap), y, card_w, card_h)
            for index in range(count)
        ]

    def _get_deck_view_offer_image(self, special_id, size):
        cache_key = (str(special_id), int(size[0]), int(size[1]))
        if cache_key in self.deck_view_offer_image_cache:
            return self.deck_view_offer_image_cache[cache_key]

        _label, path = SHOP_SPECIAL_ASSETS.get(special_id, (str(special_id), None))
        image = load_scaled_image(path, target_size=size) if path and os.path.exists(path) else None
        self.deck_view_offer_image_cache[cache_key] = image
        return image

    def _draw_active_shop_offers(self, panel, entries=None):
        active_entries = list(
            entries
            if entries is not None
            else game_state.get_active_shop_offer_effects(self.level_number, self.defeated_count)
        )
        rects = self._build_active_shop_offer_rects(panel, len(active_entries))
        self.deck_view_offer_entries = []
        mouse_pos = pygame.mouse.get_pos()
        hovered = None

        for entry, rect in zip(active_entries, rects):
            special_id = entry.get("special_id")
            image = self._get_deck_view_offer_image(special_id, rect.size)
            if image:
                self.screen.blit(image, rect.topleft)
            else:
                pygame.draw.rect(self.screen, (238, 228, 205), rect)
                pygame.draw.rect(self.screen, PAPER_COLOR, rect, 2)

            remaining = entry.get("remaining")
            if remaining is not None:
                counter = self.font_small.render(str(remaining), True, PAPER_COLOR)
                self.screen.blit(counter, counter.get_rect(center=(rect.centerx, rect.top - 18)))

            drawn_entry = {**entry, "rect": rect}
            self.deck_view_offer_entries.append(drawn_entry)
            if rect.collidepoint(mouse_pos):
                hovered = drawn_entry

        if hovered:
            self._draw_active_shop_offer_tooltip(hovered, panel)

    def _draw_active_shop_offer_tooltip(self, entry, panel):
        special_id = entry.get("special_id")
        label = SHOP_SPECIAL_ASSETS.get(special_id, (str(special_id), None))[0]
        description = SHOP_SPECIAL_DESCRIPTIONS.get(special_id, "")
        status = ""
        remaining = entry.get("remaining")
        if remaining is not None:
            unit = "босс" if entry.get("remaining_kind") == "bosses" else "раундов"
            status = f" Осталось: {remaining} {unit}."
        text = f"{label}. {description}{status}".strip()
        self._draw_boss_reward_tooltip(
            {"reward_text": text},
            entry.get("rect"),
            panel,
        )

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
        rows = [{"kind": "text", "text": line} for line in wrap_text(text, self.font_small, max_width)]
        bot_status = self._stock_bot_status_text()
        if bot_status:
            rows.append({"kind": "spacer"})
            rows.extend({"kind": "text", "text": line} for line in wrap_text(bot_status, self.font_small, max_width))
        bot_entries = self._stock_bot_tooltip_entries()
        if bot_entries:
            rows.append({"kind": "spacer"})
            rows.extend({"kind": "arrow", **item} for item in bot_entries)
        if not rows:
            return

        line_height = self.font_small.get_height() + 4
        def _row_width(row):
            if row.get("kind") == "spacer":
                return 0
            text_width = self.font_small.size(str(row.get("text", "")))[0]
            if row.get("kind") == "arrow":
                return text_width + 24
            return text_width

        width = min(
            max_width + 28,
            max(_row_width(row) for row in rows) + 28,
        )
        height = sum(line_height // 2 if row.get("kind") == "spacer" else line_height for row in rows) + 24
        x = icon_rect.right - width
        y = icon_rect.bottom + 12
        if x < 20:
            x = 20
        if y + height > SCREEN_HEIGHT - 20:
            y = icon_rect.top - height - 12

        tooltip_rect = pygame.Rect(int(x), int(y), int(width), int(height))
        pygame.draw.rect(self.screen, (238, 228, 205), tooltip_rect)
        pygame.draw.rect(self.screen, PAPER_COLOR, tooltip_rect, 2)
        cursor_y = tooltip_rect.y + 12
        for row in rows:
            if row.get("kind") == "spacer":
                cursor_y += line_height // 2
                continue
            text_x = tooltip_rect.x + 14
            if row.get("kind") == "arrow":
                arrow_cx = text_x + 8
                arrow_cy = cursor_y + line_height // 2
                if row.get("direction") == "up":
                    points = [(arrow_cx, arrow_cy - 7), (arrow_cx - 7, arrow_cy + 6), (arrow_cx + 7, arrow_cy + 6)]
                else:
                    points = [(arrow_cx, arrow_cy + 7), (arrow_cx - 7, arrow_cy - 6), (arrow_cx + 7, arrow_cy - 6)]
                pygame.draw.polygon(self.screen, PAPER_COLOR, points)
                text_x += 24
            surface = self.font_small.render(str(row.get("text", "")), True, PAPER_COLOR)
            self.screen.blit(surface, (text_x, cursor_y))
            cursor_y += line_height

    def _get_text(self, key, default=None):
        if default is None:
            default = key
        return self.lang_dict.get(key, default)

    def _pause_menu_texts(self):
        return {
            "title": self._get_text("PauseTitle", "Пауза"),
            "continue": self._get_text("PauseContinue", "Продолжить"),
            "save_exit": self._get_text("PauseSaveExit", "Сохранить и выйти"),
            "restart": self._get_text("PauseRestartLevel", "Начать заново"),
            "restart_confirm": self._get_text("PauseRestartConfirm", "Начать уровень заново?"),
            "restart_warning": self._get_text(
                "PauseRestartWarning",
                "Прогресс текущей попытки будет потерян.",
            ),
            "cancel": self._get_text("PauseCancel", "Отмена"),
        }

    def _can_open_pause_menu(self):
        return (
            self.win_lose_state is None
            and not self._is_turn_resolution_active()
            and not self.hand_compact_anim
            and not self.hand_draw_anim
        )

    def _open_pause_menu(self):
        self.pause_menu_active = True
        self.pause_menu_requested = False
        self.pause_restart_confirmation = False
        self._reset_drag_state()

    def _close_pause_menu(self):
        self.pause_menu_active = False
        self.pause_menu_requested = False
        self.pause_restart_confirmation = False

    def _handle_pause_menu_action(self, action):
        if action == "continue":
            self._close_pause_menu()
        elif action == "save_exit":
            self._save_active_game()
            self._close_pause_menu()
            return "main_menu"
        elif action == "restart":
            self.pause_restart_confirmation = True
        elif action == "cancel":
            self.pause_restart_confirmation = False
        elif action == "restart_confirm":
            self._record_stats_result(False)
            self._close_pause_menu()
            return "restart_level"
        return None

    def _handle_pause_menu_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.pause_restart_confirmation:
                self.pause_restart_confirmation = False
            else:
                self._close_pause_menu()
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            layout = build_pause_menu_layout(
                self.screen.get_size(),
                confirmation=self.pause_restart_confirmation,
            )
            action = get_pause_menu_action(layout, event.pos)
            return self._handle_pause_menu_action(action)
        return None

    def _draw_pause_menu(self):
        layout = build_pause_menu_layout(
            self.screen.get_size(),
            confirmation=self.pause_restart_confirmation,
        )
        draw_pause_menu(
            self.screen,
            layout,
            self._pause_menu_texts(),
            self.pause_title_font,
            self.pause_button_font,
            self.pause_small_font,
            pygame.mouse.get_pos(),
        )

    def _get_final_boss_reward_text(self):
        try:
            level = int(self.level_number or 0)
        except (TypeError, ValueError):
            level = 0
        if level == 1:
            return self.reward_level1_final_boss_text
        if level == 2:
            return self.reward_level2_final_boss_text
        if level == 3:
            return self.reward_level3_final_boss_text
        if level == 4:
            return self.reward_level4_final_boss_text
        if level == 5:
            return self.reward_level5_final_boss_text
        return self.reward_final_boss_text

    def _get_card_action(self, card_id):
        if card_id is None or card_id not in self.card_actions:
            return None
        base_value = int(self.card_actions.get(card_id, 0) or 0)
        bonus = get_card_investment_bonus(card_id)
        if bonus <= 0:
            return base_value
        # Contango multiplies the complete nominal, including Investment.
        effective_bonus = bonus * self._get_contango_gain_drop_multiplier()
        return base_value - effective_bonus if base_value < 0 else base_value + effective_bonus

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
            "active_lifecycle_card_order": [
                {"kind": entry["kind"], "card_id": entry["card_id"]}
                for entry in self.active_lifecycle_card_order
            ],
        }

    def _current_prices(self):
        return {
            "Aprice": self.Aprice,
            "BPrice": self.BPrice,
            "CPrice": self.CPrice,
        }

    def _is_stock_bot_allowed(self):
        try:
            return int(self.level_number or 0) in (5, 6)
        except (TypeError, ValueError):
            return False

    def _configure_boss_stock_bot(self):
        """Configure stock trading only for bosses that explicitly own shares."""
        if not self._is_stock_bot_allowed() or self.boss_index is None:
            return

        boss_number = self._get_active_boss_number()
        boss_level = get_boss_level_from_number(boss_number)
        try:
            level_number = int(self.level_number or 0)
        except (TypeError, ValueError):
            level_number = 0
        if level_number == 5 and boss_level != 2:
            self.stock_bot_enabled = False
            self.stock_bot = None
            self._stock_bot_saved_state = None
            self.stock_bot_start_quantities = None
            self.stock_bot_blocked_buy_prices = set()
            print(
                f"Skipped level-5 stock bot for category-{boss_level or 1} boss {boss_number}: "
                "only category-two bosses trade against the player"
            )
            return

        self.stock_bot_enabled = True
        if level_number == 6:
            self.stock_bot_type = "reinvestment"
            start_quantities = {
                "Aquantity": LEVEL6_STARTING_A_SHARES,
                "Bquantity": 0,
                "Cquantity": 0,
            }
        elif boss_level == 2:
            self.stock_bot_type = "advanced"
            start_quantities = {
                "Aquantity": 0,
                "Bquantity": get_category_two_start_b_shares(boss_number),
                "Cquantity": 0,
            }
        else:
            self.stock_bot_type = "simple"
            start_quantities = {
                "Aquantity": 2,
                "Bquantity": 0,
                "Cquantity": 0,
            }
        self.stock_bot_start_quantities = start_quantities
        print(
            f"Configured level-{self.level_number} category-{boss_level or 1} boss {boss_number}"
            f": {self.stock_bot_type} stock bot with "
            f"A{start_quantities['Aquantity']} "
            f"B{start_quantities['Bquantity']} "
            f"C{start_quantities['Cquantity']}"
        )

    def _configure_level5_boss_stock_bot(self):
        """Compatibility wrapper for older tests and saved flow helpers."""
        self._configure_boss_stock_bot()

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

            if self.stock_bot_type == "reinvestment":
                bot_module = importlib.import_module("reinvestment_stock_bot")
                bot_class = bot_module.ReinvestmentStockBot
            elif self.stock_bot_type == "advanced":
                bot_module = importlib.import_module("advanced_stock_bot")
                bot_class = bot_module.AdvancedStockBot
            else:
                bot_module = importlib.import_module("simple_stock_bot")
                bot_class = bot_module.SimpleStockBot
            if self._stock_bot_saved_state:
                self.stock_bot = bot_class.from_state(self._stock_bot_saved_state)
            else:
                self.stock_bot = bot_class(
                    money=0,
                    quantities=self.stock_bot_start_quantities,
                )
            if hasattr(self.stock_bot, "blocked_buy_prices"):
                self.stock_bot.blocked_buy_prices = set(self.stock_bot_blocked_buy_prices or [])
            print(f"{self.stock_bot.display_name} activated")
        except Exception as exc:
            print(f"ERROR activating stock bot: {exc}")
            self.stock_bot_enabled = False

    def _stock_bot_probabilities(self):
        return build_market_probabilities(
            self.market_cards,
            probability_card_bonus=self._get_probability_card_bonus(),
            force_flat=self._is_flat_random_active(),
            force_flat_markets=self._get_regulation_flat_markets(),
            prevent_fall_markets=self._get_blue_chip_markets(),
            double_fall_markets=self._get_shakeout_markets(),
            double_fall_bonus=self._get_probability_amplifier_bonus(),
            double_fall_count=self._get_shakeout_count(),
        )

    def _run_stock_bot_turn(self):
        if not self.stock_bot_enabled:
            return False
        self._activate_stock_bot_if_needed()
        if self.stock_bot is None:
            return False
        # This runs before _finalize_turn_resolution advances Day, so the last
        # playable day is one below the terminal counter.
        final_bot_day = (
            self.Day >= self.LastTurn
            if self._is_level6_alternating_battle()
            else self.Day >= self.LastTurn - 1
        )
        if final_bot_day:
            decision = self.stock_bot.sell_all(self._current_prices())
        elif self.stock_bot_type in ("advanced", "reinvestment"):
            decision = self.stock_bot.trade(
                self._current_prices(),
                self._stock_bot_probabilities(),
            )
        else:
            decision = self.stock_bot.trade(self._current_prices())
        self._record_stock_bot_trade(decision)
        print(f"{self.stock_bot.display_name} decision: {decision}")
        return decision

    def _record_stock_bot_trade(self, decision):
        if not isinstance(decision, dict):
            return
        entry = {
            "day": int(self.Day or 0),
            "action": decision.get("action", "hold"),
            "sold": dict(decision.get("sold") or {}),
            "sold_value": dict(decision.get("sold_value") or {}),
            "bought": dict(decision.get("bought") or {}),
            "money": int(decision.get("money", 0) or 0),
        }
        if entry["action"] == "hold" and not entry["sold"] and not entry["bought"]:
            return
        self.stock_bot_trade_history.append(entry)
        self.stock_bot_trade_history = self.stock_bot_trade_history[-8:]

    def _stock_bot_status_text(self):
        if not self.stock_bot_enabled:
            return None
        self._activate_stock_bot_if_needed()
        if self.stock_bot is None:
            return None
        return self.stock_bot.status_line(self._current_prices())

    def _is_stock_bot_boss(self):
        try:
            return int(self.level_number or 0) in (4, 5, 6) and bool(self.stock_bot_enabled)
        except (TypeError, ValueError):
            return False

    def _is_capital_race_level(self):
        try:
            return int(getattr(self, "level_number", 0) or 0) == 6 and bool(
                getattr(self, "is_boss_fight", False)
            )
        except (TypeError, ValueError):
            return False

    def _is_level6_alternating_battle(self):
        return self._is_capital_race_level()

    def _player_portfolio_value(self):
        return int(self.Money or 0) + (
            int(self.Aquantity or 0) * int(self.Aprice or 0)
            + int(self.Bquantity or 0) * int(self.BPrice or 0)
            + int(self.Cquantity or 0) * int(self.CPrice or 0)
        )

    def _stock_bot_portfolio_value(self):
        if not self.stock_bot_enabled:
            return 0
        self._activate_stock_bot_if_needed()
        if self.stock_bot is None:
            return 0
        return int(self.stock_bot.portfolio_value(self._current_prices()) or 0)

    def _can_win_against_current_boss(self):
        if not self._is_stock_bot_boss():
            return True
        player_value = self._player_portfolio_value()
        boss_value = self._stock_bot_portfolio_value()
        can_win = player_value > boss_value if self._is_capital_race_level() else player_value >= boss_value
        if not can_win:
            print(
                f"Stock bot boss blocks victory: player_value={player_value}, "
                f"boss_value={boss_value}, Money={self.Money}, Goal={self.Goal}"
            )
        return can_win

    def _stock_bot_tooltip_entries(self):
        if not self.stock_bot_enabled:
            return []
        entries = []
        for item in list(self.stock_bot_trade_history or [])[-6:]:
            if not isinstance(item, dict):
                continue
            day = int(item.get("day", 0) or 0)
            for market, value in (item.get("sold_value") or {}).items():
                try:
                    amount = int(value or 0)
                except (TypeError, ValueError):
                    amount = 0
                if amount > 0:
                    entries.append({"direction": "down", "text": f"Day {day}: {market} +${amount}"})
            for market, count in (item.get("bought") or {}).items():
                try:
                    amount = int(count or 0)
                except (TypeError, ValueError):
                    amount = 0
                if amount > 0:
                    entries.append({"direction": "up", "text": f"Day {day}: {market} x{amount}"})
        return entries

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
            "deck": [serialize_card_instance(card_id) for card_id in (self.deck or [])],
            "hand_cards": [serialize_card_instance(card_id) for card_id in (self.hand_cards or [])],
            "side_cards_top": [serialize_card_instance(card_id) for card_id in (self.side_cards_top or [])],
            "side_card_origins_top": {str(k): v for k, v in self.side_card_origins_top.items()},
            "side_cards_locked_top": {str(k): bool(v) for k, v in self.side_cards_locked_top.items()},
            "market_cards": {
                str(market): {
                    str(slot): serialize_card_instance(card_id)
                    for slot, card_id in (cards or {}).items()
                }
                for market, cards in (self.market_cards or {}).items()
            },
            "market_card_origins": self._serialize_nested_int_dict(self.market_card_origins),
            "market_cards_locked": self._serialize_nested_int_dict(self.market_cards_locked),
            "market_card_turns": self._serialize_nested_int_dict(self.market_card_turns),
            "market_card_actions": self._serialize_nested_int_dict(self.market_card_actions),
            "card_turns": {str(k): v for k, v in self.card_turns.items()},
            "accumulation_pending_sources": list(self.accumulation_pending_sources or []),
            "accumulation_stephenson_card_played_this_turn": bool(
                self.accumulation_stephenson_card_played_this_turn
            ),
            "pending_draws": self.pending_draws,
            "final_auto_liquidation_applied": self.final_auto_liquidation_applied,
            "win_lose_state": self.win_lose_state,
            "win_lose_y": self.win_lose_y,
            "last_earned_cards": list(self.last_earned_cards or []),
            "last_earned_napoleondors": float(self.last_earned_napoleondors or 0),
            "long_payout_amount": int(self.long_payout_amount or 0),
            "golden_stocks_reward_card": self.golden_stocks_reward_card,
            "random_boss_reward_text": self.random_boss_reward_text,
            "result_report_stage": self.result_report_stage,
            "finance_report_y": float(self.finance_report_y),
            "finance_report_entries": [dict(entry) for entry in self.finance_report_entries],
            "finance_stamp_state": self.finance_stamp_state,
            "round_start_napoleondors": float(self.round_start_napoleondors or 0),
            "boss_turn_timer_remaining_ms": int(self.boss_turn_timer_remaining_ms or 0),
            "active_silver_cards": list(self.active_silver_cards or []),
            "active_black_cards": list(self.active_black_cards or []),
            "active_gold_cards": list(self.active_gold_cards or []),
            "insider_c_growth_turns_remaining": int(self.insider_c_growth_turns_remaining or 0),
            "rebate_a_fall_bonus_percent": int(self.rebate_a_fall_bonus_percent or 0),
            "short_seller_fall_counts": list(
                (getattr(self, "short_seller_fall_counts", None) or [0, 0, 0])[:3]
            ),
            "surge_turns_without_trade": int(self.surge_turns_without_trade or 0),
            "surge_traded_this_turn": bool(self.surge_traded_this_turn),
            "surge_triggered": bool(self.surge_triggered),
            "continuation_growth_streaks": list(
                (getattr(self, "continuation_growth_streaks", None) or [0, 0, 0])[:3]
            ),
            "hedger_used_this_round": int(self.hedger_used_this_round or 0),
            "full_deployment_reward_applied": bool(self.full_deployment_reward_applied),
            "waterloo_preview_movements": (
                [dict(movement) for movement in self.waterloo_preview_movements]
                if self.waterloo_preview_movements is not None
                else None
            ),
            "active_silver_cards_spent": bool(self.active_silver_cards_spent),
            "forward_trading_shareholder_count": int(self.forward_trading_shareholder_count),
            "shareholder_effect_count": int(self.shareholder_effect_count or 0),
            "shareholder_blocked_market": self.shareholder_blocked_market,
            "stock_bot_enabled": bool(self.stock_bot_enabled),
            "stock_bot_type": self.stock_bot_type,
            "stock_bot": self.stock_bot.to_dict() if self.stock_bot is not None else self._stock_bot_saved_state,
            "stock_bot_blocked_buy_prices": sorted(self.stock_bot_blocked_buy_prices or []),
            "stock_bot_trade_history": list(self.stock_bot_trade_history or []),
            "level6_turn_owner": self.level6_turn_owner,
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
            "insider_c_growth_turns_remaining",
            "rebate_a_fall_bonus_percent",
            "surge_turns_without_trade",
            "surge_traded_this_turn",
            "surge_triggered",
            "hedger_used_this_round",
            "full_deployment_reward_applied",
        )
        for field in scalar_fields:
            if field in state:
                setattr(self, field, state[field])

        self.deck = [restore_card_instance(card_id) for card_id in (state.get("deck", self.deck) or [])]
        self.hand_cards = [
            restore_card_instance(card_id) for card_id in (state.get("hand_cards", self.hand_cards) or [])
        ]
        if len(self.hand_cards) < self.hand:
            self.hand_cards += [None] * (self.hand - len(self.hand_cards))
        self.hand_cards = self.hand_cards[: self.hand]

        self.side_cards_top = [
            restore_card_instance(card_id) for card_id in (state.get("side_cards_top", self.side_cards_top) or [])
        ]
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
        for market, cards in self.market_cards.items():
            self.market_cards[market] = {
                slot: restore_card_instance(card_id) for slot, card_id in cards.items()
            }
        self.market_card_origins = self._restore_nested_int_dict(state.get("market_card_origins") or {})
        self.market_cards_locked = self._restore_nested_int_dict(state.get("market_cards_locked") or {})
        self.market_card_turns = self._restore_nested_int_dict(state.get("market_card_turns") or {})
        self.market_card_actions = self._restore_nested_int_dict(state.get("market_card_actions") or {})
        self.card_turns.update({int(k): v for k, v in (state.get("card_turns") or {}).items()})
        self.accumulation_pending_sources = []
        for raw_slot in state.get("accumulation_pending_sources") or []:
            try:
                slot = int(raw_slot)
            except (TypeError, ValueError):
                continue
            if 0 <= slot < len(self.side_cards_top) and self.side_cards_top[slot] == 124:
                self.accumulation_pending_sources.append(slot)
        self.accumulation_stephenson_card_played_this_turn = bool(
            state.get("accumulation_stephenson_card_played_this_turn", False)
        )

        self.final_auto_liquidation_applied = bool(state.get("final_auto_liquidation_applied", False))
        self.win_lose_state = state.get("win_lose_state")
        if self.win_lose_state == "win" and self.is_final_boss:
            self.reward_window_text = self._get_final_boss_reward_text()
        self.last_earned_cards = list(state.get("last_earned_cards") or [])
        self.last_earned_napoleondors = float(state.get("last_earned_napoleondors", 0) or 0)
        self.long_payout_amount = int(state.get("long_payout_amount", self.long_payout_amount) or 0)
        self.golden_stocks_reward_card = state.get("golden_stocks_reward_card")
        self.random_boss_reward_text = state.get("random_boss_reward_text")
        self.result_report_stage = state.get("result_report_stage", self.result_report_stage)
        self.finance_report_y = float(state.get("finance_report_y", self.finance_report_y) or 0)
        self.finance_report_entries = [
            dict(entry) for entry in state.get("finance_report_entries") or []
            if isinstance(entry, dict)
        ]
        self.finance_stamp_state = state.get("finance_stamp_state", self.finance_stamp_state)
        if (
            self.win_lose_state == "win"
            and self.result_report_stage not in ("finance", "card_report")
        ):
            self.result_report_stage = (
                "finance"
                if getattr(self, "finance_report_image", None)
                and self._should_show_finance_report()
                else "card_report"
            )
            self.finance_report_y = float(SCREEN_HEIGHT + 30)
            self.finance_stamp_state = "idle"
            self.finance_stamp_started_at = 0
            self._play_result_report_rustle()
        self.round_start_napoleondors = float(
            state.get("round_start_napoleondors", self.round_start_napoleondors) or 0
        )
        if "boss_turn_timer_remaining_ms" in state:
            try:
                maximum_ms = max(0, int(self.boss_turn_time_limit_seconds or 0) * 1000)
                self.boss_turn_timer_remaining_ms = max(
                    0,
                    min(maximum_ms, int(state.get("boss_turn_timer_remaining_ms") or 0)),
                )
            except (TypeError, ValueError):
                self._reset_boss_turn_timer()
        self.active_silver_cards = list(state.get("active_silver_cards", self.active_silver_cards) or [])
        self.active_black_cards = list(state.get("active_black_cards", self.active_black_cards) or [])
        self.active_gold_cards = list(state.get("active_gold_cards", self.active_gold_cards) or [])
        if self._is_level6_alternating_battle():
            self.hand = 0
            self.deck = []
            self.hand_cards = []
            self.market_cards = {0: {}, 1: {}, 2: {}}
            self.side_cards_top = [None] * 6
            self.active_silver_cards = []
            self.active_black_cards = []
            self.active_gold_cards = []
            self.active_lifecycle_card_order = []
        else:
            game_state.set_active_gold_cards(self.active_gold_cards)
        raw_waterloo_preview = state.get("waterloo_preview_movements")
        self.waterloo_preview_movements = (
            [dict(movement) for movement in raw_waterloo_preview if isinstance(movement, dict)]
            if isinstance(raw_waterloo_preview, list)
            else None
        )
        raw_short_seller_counts = list(state.get("short_seller_fall_counts") or [0, 0, 0])
        self.short_seller_fall_counts = []
        for value in (raw_short_seller_counts + [0, 0, 0])[:3]:
            try:
                self.short_seller_fall_counts.append(max(0, int(value)))
            except (TypeError, ValueError):
                self.short_seller_fall_counts.append(0)
        if not self._has_active_silver_card(211) or self.is_boss_fight:
            self.short_seller_fall_counts = [0, 0, 0]
        raw_continuation_streaks = list(state.get("continuation_growth_streaks") or [0, 0, 0])
        self.continuation_growth_streaks = []
        for value in (raw_continuation_streaks + [0, 0, 0])[:3]:
            try:
                self.continuation_growth_streaks.append(max(0, int(value)))
            except (TypeError, ValueError):
                self.continuation_growth_streaks.append(0)
        if not self._has_active_silver_card(419):
            self.continuation_growth_streaks = [0, 0, 0]
        if self._count_active_silver_card(405) <= 0:
            self.insider_c_growth_turns_remaining = 0
        self.active_silver_cards_spent = bool(state.get("active_silver_cards_spent", self.active_silver_cards_spent))
        self.forward_trading_shareholder_count = int(
            state.get("forward_trading_shareholder_count", self.forward_trading_shareholder_count) or 0
        )
        self.shareholder_effect_count = int(
            state.get("shareholder_effect_count", self.shareholder_effect_count) or 0
        )
        if self._is_level6_alternating_battle():
            self.shareholder_effect_count = 0
        blocked_market = state.get("shareholder_blocked_market", self.shareholder_blocked_market)
        self.shareholder_blocked_market = blocked_market if blocked_market in (0, 1, 2) else None
        self.stock_bot_enabled = bool(state.get("stock_bot_enabled", self.stock_bot_enabled))
        self.stock_bot_type = state.get("stock_bot_type", self.stock_bot_type) or "simple"
        self._stock_bot_saved_state = state.get("stock_bot")
        try:
            self.stock_bot_blocked_buy_prices = {
                int(price) for price in (state.get("stock_bot_blocked_buy_prices") or self.stock_bot_blocked_buy_prices or [])
            }
        except (TypeError, ValueError):
            self.stock_bot_blocked_buy_prices = set()
        self.stock_bot_trade_history = list(state.get("stock_bot_trade_history") or self.stock_bot_trade_history or [])
        self.level6_turn_owner = "player"
        self.level6_bot_turn_phase = None
        self.level6_bot_turn_started_at = 0
        self.level6_bot_turn_decision = None
        self.stock_bot_acted_this_resolution = False
        self._stats_recorded = bool(state.get("stats_recorded", self._stats_recorded))
        self.turn_resolution_active = False
        self.price_animation_queue = []
        self.stock_price_turn_results = []
        self.current_price_animation = None
        self.basket_trading_applied_this_resolution = False
        self.sideway_applied_this_resolution = False
        self.continuation_held_markets_this_turn = set()
        self.continuation_applied_this_resolution = False
        self.continuation_animation_phase = False
        self.c_price_fell_this_resolution = False
        self.manipulation_applied_this_resolution = False
        self.price_card_queue = []
        self.current_card_processing = None
        self.card_jump_animations = {0: {}, 1: {}, 2: {}}
        self.side_card_jump_animations = {}
        self.lifecycle_card_jump_animations = {}
        self.lifecycle_card_scale_animations = {}
        self.lifecycle_card_shake_animations = {}
        self.lifecycle_reminder_days_started = set()
        self.final_auto_liquidation_animation = None
        self.effect_finalize_pending = False
        self.red_effects_applied_this_resolution = False
        self.hand_negative_overlay_hold = {"red": False, "market": False}
        self.hand_compact_anim = []
        self.hand_draw_anim = []
        self.market_clear_animations = []
        self._reset_drag_state()
        self._start_lifecycle_turn_reminder()

    def _save_active_game(self):
        if not self.profile_slot or self.test_mode:
            return
        profile_manager.save_active_game(
            self.profile_slot,
            self._resume_context(),
            self._serialize_gameplay_state(),
        )

    def _load_winlose_card(self, card_number, target_width=100):
        """Load and cache a reward card image for WinLose window."""
        image = load_winlose_card_preview(
            card_number,
            self.winlose_card_images,
            self.card_actions,
            self.card_turns,
            self.font_path,
            PAPER_COLOR,
        )
        if image is None or target_width == image.get_width():
            return image
        cache_key = (int(card_number), int(target_width))
        scaled = self.winlose_scaled_card_images.get(cache_key)
        if scaled is None:
            target_height = int(target_width / (99 / 171.0))
            scaled = pygame.transform.smoothscale(image, (target_width, target_height)).convert_alpha()
            self.winlose_scaled_card_images[cache_key] = scaled
        return scaled
    
    def get_card_type(self, card_id):
        """Return card Type from Cards.csv (defaults to 1)."""
        return get_card_type_from_config(self.card_types, card_id)

    def _is_red_play_limit_reached(self):
        if not getattr(self, "boss_limit_red_gain_drop_per_turn", False):
            return False
        for slot, card_id in enumerate(self.side_cards_top):
            if card_id is None or self.side_cards_locked_top.get(slot):
                continue
            if self.get_card_type(card_id) == 2:
                return True
        return False

    def _is_gain_drop_play_limit_reached(self, card_id=None):
        if not getattr(self, "boss_limit_red_gain_drop_per_turn", False):
            return False
        if card_id is not None and not self._is_stephenson_market_card(card_id):
            return False
        if getattr(self, "accumulation_stephenson_card_played_this_turn", False):
            return True
        for market in (0, 1, 2):
            for slot, existing_card_id in self.market_cards[market].items():
                if existing_card_id is None or self.market_cards_locked[market].get(slot):
                    continue
                if self._is_stephenson_market_card(existing_card_id):
                    return True
        return False

    @staticmethod
    def _is_stephenson_market_card(card_id):
        try:
            normalized_card_id = int(card_id)
        except (TypeError, ValueError):
            return False
        return (
            game_state.is_gain_drop_card(normalized_card_id)
            or normalized_card_id in REGULATION_CARD_IDS
            or normalized_card_id == BLUE_CHIPS_CARD_ID
        )

    def _can_play_dragged_hand_card_on_market(self, card_id):
        return not self._is_gain_drop_play_limit_reached(card_id)

    def _can_play_dragged_hand_card_on_side_top(self, card_id):
        if self.get_card_type(card_id) != 2:
            return False
        try:
            is_breakout = int(card_id) == 125
        except (TypeError, ValueError):
            is_breakout = False
        if is_breakout:
            try:
                is_last_playable_turn = int(self.Day) == int(self.LastTurn) - 1
            except (TypeError, ValueError):
                is_last_playable_turn = False
            if not is_last_playable_turn:
                return False
        return not self._is_red_play_limit_reached()

    def _should_show_hand_card_negative(self, card_id):
        """Return whether a hand card is disabled by a rule that merits the overlay."""
        if card_id is None:
            return False
        try:
            if int(card_id) == 125:
                return False
        except (TypeError, ValueError):
            pass
        held = getattr(self, "hand_negative_overlay_hold", {}) or {}
        if self.get_card_type(card_id) == 2:
            return self._is_red_play_limit_reached() or bool(held.get("red"))
        if not self._is_stephenson_market_card(card_id):
            return False
        return self._is_gain_drop_play_limit_reached(card_id) or bool(held.get("market"))

    def _hold_hand_negative_overlays_until_next_turn(self):
        """Freeze per-turn disabled markers while end-turn effects are resolving."""
        self.hand_negative_overlay_hold = {
            "red": self._is_red_play_limit_reached(),
            "market": self._is_gain_drop_play_limit_reached(),
        }

    def _clear_hand_negative_overlay_hold(self):
        self.hand_negative_overlay_hold = {"red": False, "market": False}

    def _is_lifecycle_card_power_lost(self, card_id, slot=None):
        """Return whether a displayed lifecycle card has exhausted its one-shot effect."""
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            return False

        if normalized == 302:
            return game_state.is_golden_stocks_triggered()
        if normalized == 422:
            return not is_markdown_effective_for_round(
                getattr(self, "round_num", None),
                getattr(self, "is_boss_fight", False),
            )
        if normalized == 415:
            return bool(getattr(self, "surge_triggered", False))
        if normalized == GOLD_FULL_DEPLOYMENT_CARD_ID:
            return bool(getattr(self, "full_deployment_reward_applied", False))
        if normalized == 408:
            used_count = max(0, int(getattr(self, "hedger_used_this_round", 0) or 0))
            if used_count <= 0:
                return False
            active_cards = self._active_lifecycle_cards()
            occurrence = sum(
                1
                for previous in active_cards[: max(0, int(slot or 0))]
                if int(previous) == normalized
            )
            return occurrence < used_count
        return False

    def _draw_negative_card_overlay(self, card_x, card_y, card_size):
        overlay = getattr(self, "negative_card_overlays", {}).get(tuple(card_size))
        if overlay:
            self.screen.blit(overlay, (int(card_x), int(card_y)))

    def _placeholder_hit_candidates(self, placeholders, pos, margin=10):
        x, y = pos
        candidates = []
        for index, ph_info in enumerate(placeholders or []):
            rect = ph_info.get("rect")
            if rect is None:
                continue
            hit_rect = rect.inflate(margin * 2, margin * 2)
            if not hit_rect.collidepoint(pos):
                continue
            direct_hit = rect.collidepoint(pos)
            distance_sq = (rect.centerx - x) ** 2 + (rect.centery - y) ** 2
            candidates.append((0 if direct_hit else 1, distance_sq, index, ph_info))
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return [item[3] for item in candidates]

    def _is_arrow_trading_disabled(self):
        if not getattr(self, "boss_odd_turn_trading_only", False):
            return False
        try:
            return int(self.Day) % 2 == 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def shareholder_market_shutdown_probability(shareholder_count):
        """Return the per-turn market shutdown chance for a deck composition."""
        try:
            count = max(0, int(shareholder_count or 0))
        except (TypeError, ValueError):
            return 0.0
        if count < 3:
            return 0.0
        return min(1.0, (count + 1) * 0.05)

    def _has_controlling_stake(self):
        """Return whether silver card 205 neutralizes the Shareholder penalty."""
        for card_id in getattr(self, "active_silver_cards", []) or []:
            try:
                if int(card_id) == 205:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _roll_shareholder_market_shutdown(self):
        """Choose one market whose buy/sell arrows are disabled for this turn."""
        self.shareholder_blocked_market = None
        try:
            if int(self.level_number or 0) not in (4, 5, 8) or self.win_lose_state is not None:
                return None
        except (TypeError, ValueError):
            return None

        if self._has_controlling_stake():
            return None

        chance = self.shareholder_market_shutdown_probability(
            getattr(self, "shareholder_effect_count", 0)
        )
        if chance > 0 and random.random() < chance:
            self.shareholder_blocked_market = random.choice((0, 1, 2))
            self._start_shareholder_jump_animations()
            print(
                f"Level {self.level_number} Shareholder effect disabled market "
                f"{self.shareholder_blocked_market + 1} for day {self.Day} "
                f"(chance={chance:.0%})"
            )
        return self.shareholder_blocked_market

    def _start_shareholder_jump_animations(self):
        """Jump every Shareholder currently placed on the game field."""
        for slot, card_id in enumerate(self.side_cards_top):
            if card_id == 100:
                self._start_card_jump_animation(self.side_card_jump_animations, slot)

        for market in (0, 1, 2):
            for slot, card_id in self.market_cards.get(market, {}).items():
                if card_id == 100:
                    self._start_card_jump_animation(self.card_jump_animations[market], slot)

    def _blocked_buy_prices(self):
        return {2} if getattr(self, "boss_forbid_price_2_buys", False) else set()

    def _is_arrow_buy_blocked(self, frame_idx, arrow_type):
        if arrow_type not in (0, 1):
            return False
        blocked_prices = self._blocked_buy_prices()
        if not blocked_prices:
            return False
        prices = (self.Aprice, self.BPrice, self.CPrice)
        try:
            return int(prices[int(frame_idx)]) in blocked_prices
        except (TypeError, ValueError, IndexError):
            return False

    def _is_arrow_disabled(self, frame_idx, arrow_type):
        try:
            shareholder_blocked = (
                not self._has_controlling_stake()
                and int(frame_idx) == getattr(self, "shareholder_blocked_market", None)
            )
        except (TypeError, ValueError):
            shareholder_blocked = False
        return (
            shareholder_blocked
            or self._is_arrow_trading_disabled()
            or self._is_arrow_buy_blocked(frame_idx, arrow_type)
        )

    def _is_final_auto_liquidation_animating(self):
        return self.final_auto_liquidation_animation is not None

    def _is_hand_transition_active(self):
        return bool(self.hand_compact_anim or self.hand_draw_anim)

    def _get_dimmed_arrow(self, arrow_img):
        if not arrow_img:
            return arrow_img
        cache_key = id(arrow_img)
        cached = self.dimmed_arrow_cache.get(cache_key)
        if cached:
            return cached
        dimmed = arrow_img.copy()
        dimmed.fill((120, 120, 120, 145), special_flags=pygame.BLEND_RGBA_MULT)
        self.dimmed_arrow_cache[cache_key] = dimmed
        return dimmed

    def _get_trade_arrow_image(self, frame_idx, arrow_type, arrow_img):
        """Return the visibly dimmed arrow whenever that exact trade is disabled."""
        if self._is_arrow_disabled(frame_idx, arrow_type):
            return self._get_dimmed_arrow(arrow_img)
        return arrow_img

    def _apply_arrow_trade(self, frame_idx, arrow_type):
        if self._is_arrow_disabled(frame_idx, arrow_type):
            return False

        previous_quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
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
            blocked_buy_prices=self._blocked_buy_prices(),
        )

        quantities = trade_result["quantities"]
        self.Money = trade_result["money"]
        self.Aquantity = quantities["Aquantity"]
        self.Bquantity = quantities["Bquantity"]
        self.Cquantity = quantities["Cquantity"]

        if trade_result["changed"]:
            current_quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
            for market, (previous, current) in enumerate(zip(previous_quantities, current_quantities)):
                if current < previous:
                    self._reset_continuation_growth_streak(market)
            self.surge_turns_without_trade = 0
            self.surge_traded_this_turn = True
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

    def _close_deck_view(self):
        self.deck_view_active = False
        self._clear_hedger_selection()

    def _handle_deck_view_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._close_deck_view()
            return None

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None

        if self.deck_toggle_rect.collidepoint(event.pos):
            self._play_deck_toggle_sound()
            self._close_deck_view()
            return None

        if not self._is_hedger_available():
            return None

        if self.hedger_confirm_active:
            if self.hedger_yes_button_rect and self.hedger_yes_button_rect.collidepoint(event.pos):
                self._add_hedger_selected_card_to_hand()
                return None
            if self.hedger_no_button_rect and self.hedger_no_button_rect.collidepoint(event.pos):
                self._clear_hedger_selection()
                return None

        if self.hedger_add_button_rect and self.hedger_add_button_rect.collidepoint(event.pos):
            self.hedger_confirm_active = True
            return None

        for entry in reversed(self.deck_view_card_entries or []):
            rect = entry.get("rect")
            if rect and rect.collidepoint(event.pos):
                self._select_hedger_deck_card(entry.get("card_id"))
                return None

        return None
    
    def handle_input(self):
        mouse_pos = pygame.mouse.get_pos()
        if getattr(self, "result_transition_ready", None):
            result = self.result_transition_ready
            self.result_transition_ready = None
            return result
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if self.pause_menu_active:
                pause_result = self._handle_pause_menu_event(event)
                if pause_result:
                    return pause_result
                continue

            if self.deck_view_active:
                self._handle_deck_view_event(event)
                continue
            
            # Handle Ok button click if WinLose screen is shown
            if (
                self.win_lose_state == "win"
                and getattr(self, "result_report_stage", "cards") in ("finance", "card_report")
                and self._get_active_result_report_image()
            ):
                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and self.finance_stamp_state == "idle"
                    and self.finance_stamp_rect
                    and self.finance_stamp_rect.collidepoint(event.pos)
                ):
                    if self.stamp_sound:
                        self.stamp_sound.play()
                    self.finance_stamp_state = "pressing"
                    self.finance_stamp_started_at = pygame.time.get_ticks()
                continue

            if self.win_lose_state == "lose" and self.win_lose_image:
                # Determine which button to show based on win/lose state
                ok_button = None
                if self.ok2_button:
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
                                # Lost: return to level selection screen
                                return "level_select"
                    
                    # The result window owns all input until its button is pressed.
                    continue

            if self.win_lose_state is not None:
                continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self._can_open_pause_menu():
                        self._open_pause_menu()
                    else:
                        self.pause_menu_requested = not self.pause_menu_requested
                    continue

            if self._is_final_auto_liquidation_animating():
                continue

            if self._is_hand_transition_active():
                continue
            
            # Handle drag and drop
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if (
                        not self._is_level6_alternating_battle()
                        and self.win_lose_state is None
                        and self.deck_toggle_rect.collidepoint(event.pos)
                    ):
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

                            if self._is_arrow_trading_disabled():
                                break
                            
                            frame_idx = entry.get("frame_index")
                            if frame_idx is None:
                                continue

                            if self._is_arrow_disabled(frame_idx, entry.get("arrow_type")):
                                break
                            trade_changed = self._apply_arrow_trade(
                                frame_idx,
                                entry.get("arrow_type"),
                            )
                            
                            # Start animation (if entry has frames)
                            if trade_changed and entry.get("frames"):
                                entry["animating"] = True
                                entry["idx"] = 0
                                entry["last"] = pygame.time.get_ticks()
                                if self.arrow_sound:
                                    self.arrow_sound.play()
                            break
                    
                    # Check if End Turn button was clicked (outside arrow loop)
                    if self.end_button_rect and self.end_button_rect.collidepoint(mouse_pos):
                        self._start_turn_resolution()
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
                        for ph_info in self._placeholder_hit_candidates(self.side_placeholders_top, event.pos):
                            if ph_info.get("slot") == src_slot:
                                dropped = True
                                break
                        if not dropped:
                            # Only allow drop to the ORIGINAL hand slot of this card
                            for ph_info in self._placeholder_hit_candidates(self.bottom_placeholders, event.pos):
                                slot = ph_info["slot"]
                                origin_slot = self.side_card_origins_top.get(src_slot)
                                if origin_slot is not None and slot == origin_slot and self.hand_cards[slot] is None:
                                    card_id = self.side_cards_top[src_slot] if src_slot is not None else None
                                    if card_id is not None:
                                        self._cancel_accumulation_charge(card_id, src_slot)
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
                        for ph_info in self._placeholder_hit_candidates(self.side_placeholders_top, event.pos):
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
                                if not self._can_play_dragged_hand_card_on_side_top(card_id):
                                    continue
                                self.side_cards_top[slot] = card_id
                                # Remember original hand slot and mark as not locked for this turn
                                self.side_card_origins_top[slot] = self.dragged_card_index
                                self.side_cards_locked_top[slot] = False
                                self._activate_accumulation_charge(card_id, slot)
                                self.hand_cards[self.dragged_card_index] = None
                                self.pending_draws += 1
                                if self._apply_full_deployment_reward_if_needed():
                                    self._save_active_game()
                                dropped = True
                                break

                    # Try to drop card on market placeholder (only if NOT dragging a Type=2 card from hand)
                    if not (
                        self.dragged_card_source == "side_top"
                        or (self.dragged_card_source == "hand" and dragged_hand_card_type == 2)
                    ):
                        for ph_info in self._placeholder_hit_candidates(self.market_placeholders, event.pos):
                            if ph_info:
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
                                            if not self._can_play_dragged_hand_card_on_market(card_id):
                                                continue
                                            self.market_cards[market][slot] = card_id
                                            # Remember original hand slot for this market card
                                            self.market_card_origins[market][slot] = self.dragged_card_index
                                            # Новая сыгранная карта пока НЕ заблокирована
                                            self.market_cards_locked[market][slot] = False
                                            # Initialize duration for persistent price-effect cards.
                                            if card_id in self.card_turns:
                                                self.market_card_turns[market][slot] = self.card_turns[card_id]
                                            card_action = self._get_card_action(card_id)
                                            if card_action is not None:
                                                self.market_card_actions[market][slot] = card_action
                                            self._consume_accumulation_charge(card_id, market, slot)
                                            # Remove from hand slot
                                            self.hand_cards[self.dragged_card_index] = None
                                            # Mark pending draw for empty slot
                                            self.pending_draws += 1
                                            if self._apply_full_deployment_reward_if_needed():
                                                self._save_active_game()
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
                                        action = self.market_card_actions[src_market].pop(src_slot, None)
                                        if action is not None:
                                            self.market_card_actions[market][slot] = action
                                        dropped = True
                                        break
                    # Try to drop card on hand placeholder (return or move to another hand slot)
                    if not dropped:
                        for ph_info in self._placeholder_hit_candidates(self.bottom_placeholders, event.pos):
                            if ph_info:
                                slot = ph_info['slot']
                                # From hand to another hand slot (reposition)
                                if self.dragged_card_source == "hand" and self.dragged_card_index is not None:
                                    # Dropping onto the source placeholder still counts as placing the card.
                                    if slot == self.dragged_card_index:
                                        dropped = True
                                        break
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
                                            self.market_card_actions[src_market].pop(src_slot, None)
                                            if self.pending_draws > 0:
                                                self.pending_draws -= 1
                                            dropped = True
                                            break
                    # Reset drag state (even if not dropped, card returns to source)
                    if dropped:
                        self._play_card_placing_sound()
                    self._reset_drag_state()
        
        return None
    
    def _check_win_lose(self):
        """Check win/lose conditions and trigger WinLose screen if needed"""
        if self._is_final_auto_liquidation_animating():
            return
        if self._apply_final_auto_liquidation_if_needed():
            if self._is_final_auto_liquidation_animating():
                return
        if self._is_capital_race_level():
            if self.win_lose_state is not None or self.Day < self.LastTurn:
                return
            won = self._can_win_against_current_boss()
            self._finish_win_lose_result(
                "win" if won else "lose",
                "capital_race" if won else "stock_bot_ahead",
            )
            return
        next_state, reason = resolve_win_lose_state(
            self.win_lose_state,
            self.Money,
            self.Goal,
            self.Day,
            self.LastTurn,
        )
        if next_state is None:
            return

        if next_state == "win" and not self._can_win_against_current_boss():
            if self.Day >= self.LastTurn:
                next_state, reason = "lose", "list_boss_ahead"
            else:
                return

        if reason != "list_boss_ahead":
            next_state, reason = self._apply_insurance_if_needed(next_state, reason)
        self._finish_win_lose_result(next_state, reason)

    def _finish_win_lose_result(self, next_state, reason):
        self.win_lose_state = next_state
        self._settle_frugality_for_finished_round()
        self._record_stats_result(next_state == "win")
        self._spend_active_silver_cards_if_needed()
        self.long_payout_amount = 0
        self.golden_stocks_reward_card = None
        if next_state == "win":
            game_state.ensure_napoleondor_level(self.level_number)
            pending_report_entries = game_state.consume_finance_report_income()
            bank_interest_amount = game_state.apply_bank_interest(
                self.level_number,
                base_amount=game_state.napoleondors,
            )
            napoleondors_before_rewards = float(game_state.napoleondors or 0)
            if self.is_final_boss:
                self.reward_window_text = self._get_final_boss_reward_text()
            self.win_lose_y = get_win_lose_start_y(self.win_lose_image) or self.win_lose_y
            if reason == "insurance":
                print(
                    f"WIN by Insurance: Money={self.Money}, Goal={self.Goal}, "
                    f"Day={self.Day}, LastTurn={self.LastTurn}"
                )
            elif reason == "short_seller":
                print(
                    f"WIN by Short Seller: falls={self.short_seller_fall_counts}, "
                    f"Money={self.Money}, Day={self.Day}"
                )
            elif reason == "last_turn":
                print(f"WIN on LastTurn: Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
            else:
                print(f"WIN (early): Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")
            self._apply_bill_of_exchange_shop_discount()
            self._add_reward_card_to_deck()
            boss_reward_amount = max(
                0.0,
                float(game_state.napoleondors or 0) - napoleondors_before_rewards,
            )
            commission_amount = self._apply_commission_win_bonus()
            obligation_amount = self._apply_obligation_win_bonus()
            shareholder_base_amount = self._apply_shareholder_base_win_bonus()
            self._record_bear_victory_progress()
            self._record_windfall_boss_victory_progress()
            self.long_payout_amount = self._apply_long_investment_payout()
            self.golden_stocks_reward_card = self._apply_golden_stocks_reward()
            immediate_reward = max(
                0.0,
                float(game_state.napoleondors or 0) - napoleondors_before_rewards,
            )
            self.last_earned_napoleondors = (
                immediate_reward + self._get_pending_victory_napoleondor_reward()
            )
            finance_report_args = dict(
                pending_entries=pending_report_entries,
                opening_balance=self.round_start_napoleondors,
                interest_amount=bank_interest_amount,
                boss_reward_amount=boss_reward_amount,
                commission_amount=commission_amount,
                obligation_amount=obligation_amount,
                long_amount=self.long_payout_amount,
                shareholder_base_amount=shareholder_base_amount,
                shareholder_base_active=(
                    self._count_active_card_safely(GOLD_SHAREHOLDER_BASE_CARD_ID) > 0
                ),
            )
            finance_entries_before_nabob = self._build_finance_report_entries(
                **finance_report_args
            )
            nabob_amount = self._apply_nabob_win_bonus(finance_entries_before_nabob)
            self.last_earned_napoleondors += nabob_amount
            self.finance_report_entries = self._build_finance_report_entries(
                **finance_report_args,
                nabob_amount=nabob_amount,
            )
            self.result_report_stage = (
                "finance"
                if self.finance_report_image and self._should_show_finance_report()
                else "card_report"
            )
            self.finance_report_y = float(SCREEN_HEIGHT + 30)
            self.finance_stamp_state = "idle"
            self.finance_stamp_started_at = 0
            self._play_result_report_rustle()
            game_state.advance_bailout_round()
            game_state.advance_disclosure_round()
        else:
            self.win_lose_y = get_win_lose_start_y(self.win_lose_image) or self.win_lose_y
            print(f"LOSE on LastTurn: Money={self.Money}, Goal={self.Goal}, Day={self.Day}, LastTurn={self.LastTurn}")

    def _has_played_side_card(self, target_card_id):
        return any(card_id == target_card_id for card_id in self.side_cards_top)

    def _active_lifecycle_cards(self):
        if self.active_lifecycle_card_order:
            return [entry["card_id"] for entry in self.active_lifecycle_card_order]
        return list(self.active_silver_cards or []) + list(self.active_black_cards or []) + list(self.active_gold_cards or [])

    def _normalize_active_lifecycle_card_order(self, selected_order):
        available = {
            "silver": list(self.active_silver_cards or []),
            "black": list(self.active_black_cards or []),
            "gold": list(self.active_gold_cards or []),
        }
        ordered = []
        for entry in selected_order or []:
            if isinstance(entry, dict):
                kind = str(entry.get("kind") or "").lower()
                card_id = entry.get("card_id", entry.get("id"))
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                kind = str(entry[0] or "").lower()
                card_id = entry[1]
            else:
                continue
            if kind not in available:
                continue
            try:
                normalized_id = int(card_id)
            except (TypeError, ValueError):
                continue
            try:
                available[kind].remove(normalized_id)
            except ValueError:
                continue
            ordered.append({"kind": kind, "card_id": normalized_id})

        if not ordered:
            for kind in ("silver", "black", "gold"):
                ordered.extend({"kind": kind, "card_id": card_id} for card_id in available[kind])
        else:
            for kind in ("silver", "black", "gold"):
                ordered.extend({"kind": kind, "card_id": card_id} for card_id in available[kind])
        return ordered

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

    def _get_gambling_probability_bonus(self):
        gambling_count = self._count_active_card_safely(406)
        if gambling_count <= 0:
            return 0
        return gambling_count * (
            GAMBLING_PROBABILITY_BONUS + self._get_probability_amplifier_bonus()
        )

    def _get_catalyst_percentage_bonus(self):
        return self._count_active_card_safely(210) * CATALYST_PERCENTAGE_POINTS

    def _get_gold_catalyst_percentage_bonus(self):
        return self._count_active_card_safely(414) * GOLD_CATALYST_PERCENTAGE_POINTS

    def _get_percentage_amplifier_bonus(self):
        return self._get_catalyst_percentage_bonus() + self._get_gold_catalyst_percentage_bonus()

    def _get_disclosure_probability_bonus(self):
        return self._count_active_card_safely(427) * GOLD_DISCLOSURE_PERCENTAGE_POINTS

    def _get_probability_amplifier_bonus(self):
        return self._get_percentage_amplifier_bonus() + self._get_disclosure_probability_bonus()

    def _get_waterloo_chance(self):
        return min(100, GOLD_WATERLOO_BASE_CHANCE + self._get_probability_amplifier_bonus())

    def _count_active_card_safely(self, card_id):
        try:
            return self._count_active_silver_card(card_id)
        except AttributeError:
            return 1 if self._has_active_silver_card(card_id) else 0

    def _get_downside_risk_guaranteed_drop_count(self):
        return 2 * self._count_active_card_safely(GOLD_DOWNSIDE_RISK_CARD_ID)

    def _get_probability_card_bonus(self):
        return (
            self._get_probability_amplifier_bonus()
            + self._get_gambling_probability_bonus()
            + game_state.get_updown_probability_bonus()
        )

    def _is_flat_random_active(self):
        return self._count_active_silver_card(404) > 0

    def _get_regulation_flat_markets(self):
        """Return markets whose active Regulation card forces the random roll Flat."""
        regulated = set()
        for market in (0, 1, 2):
            for slot, card_id in self.market_cards.get(market, {}).items():
                if card_id not in REGULATION_CARD_IDS:
                    continue
                turns_remaining = self.market_card_turns.get(market, {}).get(slot, 0)
                if turns_remaining is not None and turns_remaining > 0:
                    regulated.add(market)
                    break
        return regulated

    def _get_blue_chip_markets(self):
        """Return markets whose price cannot fall while card 22 is present."""
        protected = set()
        for market in (0, 1, 2):
            if BLUE_CHIPS_CARD_ID in getattr(self, "market_cards", {}).get(market, {}).values():
                protected.add(market)
        return protected

    def _protect_blue_chip_prices(self, previous_prices, proposed_prices):
        """Keep protected markets unchanged when an effect proposes a lower price."""
        return protect_market_prices(
            previous_prices,
            proposed_prices,
            self._get_blue_chip_markets(),
        )

    def _record_rebate_a_fall(self, previous_price, current_price, source):
        rebate_count = self._count_active_card_safely(407)
        if rebate_count <= 0 or current_price >= previous_price:
            return False
        gained_percent = 2 * rebate_count
        self.rebate_a_fall_bonus_percent += gained_percent
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                if int(card_id) == 407:
                    self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
            except (TypeError, ValueError):
                continue
        print(
            f"Active card 407 Gold Rebate gained {gained_percent} percentage points from an A fall: "
            f"source={source}, A={previous_price}->{current_price}, "
            f"bonus={self.rebate_a_fall_bonus_percent}%"
        )
        return True

    def _record_c_price_fall(self, previous_price, current_price, source):
        """Remember any actual C-price decrease during the current turn resolution."""
        if current_price >= previous_price:
            return False
        self.c_price_fell_this_resolution = True
        print(f"C price fell this turn: source={source}, C={previous_price}->{current_price}")
        return True

    def _normalize_short_seller_fall_counts(self):
        raw_counts = list(getattr(self, "short_seller_fall_counts", []) or [])
        normalized = []
        for value in (raw_counts + [0, 0, 0])[:3]:
            try:
                normalized.append(max(0, int(value)))
            except (TypeError, ValueError):
                normalized.append(0)
        self.short_seller_fall_counts = normalized
        return normalized

    def _record_short_seller_falls(self, previous_prices, source):
        """Count an actual fall while the player is fully invested in one market."""
        has_short_seller = False
        for card_id in getattr(self, "active_silver_cards", []) or []:
            try:
                if int(card_id) == 211:
                    has_short_seller = True
                    break
            except (TypeError, ValueError):
                continue
        if getattr(self, "is_boss_fight", False) or not has_short_seller:
            return False

        quantities = (
            int(self.Aquantity or 0),
            int(self.Bquantity or 0),
            int(self.Cquantity or 0),
        )
        owned_markets = [market for market, quantity in enumerate(quantities) if quantity > 0]
        if len(owned_markets) != 1:
            return False

        try:
            old_prices = tuple(max(0, int(price or 0)) for price in previous_prices)
        except (TypeError, ValueError):
            return False
        if len(old_prices) != 3:
            return False

        # Judge the cash remainder against prices before the fall: the player
        # must already have invested as much as the market allowed.
        positive_prices = [price for price in old_prices if price > 0]
        if not positive_prices or int(self.Money or 0) >= min(positive_prices):
            return False

        market = owned_markets[0]
        current_prices = (int(self.Aprice or 0), int(self.BPrice or 0), int(self.CPrice or 0))
        if current_prices[market] >= old_prices[market]:
            return False

        counted_markets = set(
            getattr(self, "short_seller_counted_markets_this_resolution", set()) or set()
        )
        if market in counted_markets:
            return False
        counted_markets.add(market)
        self.short_seller_counted_markets_this_resolution = counted_markets

        counts = self._normalize_short_seller_fall_counts()
        counts[market] += 1
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_short_seller = int(card_id) == 211
            except (TypeError, ValueError):
                is_short_seller = False
            if is_short_seller:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        print(
            "Active card 211 Short Seller counted a qualifying fall: "
            f"source={source}, market={market}, falls={counts[market]}/5"
        )
        if counts[market] < 5:
            return False

        self._finish_short_seller_victory()
        return True

    def _finish_short_seller_victory(self):
        if getattr(self, "win_lose_state", None) is not None or getattr(self, "is_boss_fight", False):
            return False
        self.price_animation_queue = []
        self.current_price_animation = None
        self.price_card_queue = []
        self.current_card_processing = None
        self.effect_finalize_pending = False
        self.pending_draws = 0
        self.turn_resolution_active = False
        self._finish_win_lose_result("win", "short_seller")
        return True

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

    def _apply_issue_price_start(self):
        if not self._has_active_silver_card(421):
            return False
        self.Aprice = 6
        print("Gold card 421 Issue Price set the starting A price to 6.")
        return True

    def _apply_volatility_steps(self):
        volatility_count = self._count_active_card_safely(424)
        volatility_plus_count = self._count_active_card_safely(425)
        pair_count = min(volatility_count, volatility_plus_count)
        bonus = (
            pair_count * 10
            + (volatility_count - pair_count) * 2
            + (volatility_plus_count - pair_count) * 4
        )
        if bonus <= 0:
            return 0

        self.StepA += bonus
        self.StepB += bonus
        self.StepC += bonus
        print(
            f"Gold Volatility cards increased market steps by {bonus}: "
            f"A={self.StepA}, B={self.StepB}, C={self.StepC}"
        )
        return bonus

    def _apply_bear_goal_modifier(self):
        discount_percent = self._get_current_bear_goal_discount_percent()
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

    def _apply_markdown_goal_modifier(self):
        markdown_count = self._count_active_card_safely(422)
        if markdown_count <= 0 or not is_markdown_effective_for_round(
            getattr(self, "round_num", None),
            getattr(self, "is_boss_fight", False),
        ):
            return False
        try:
            round_num = int(self.round_num)
            base_goal = float(self.Goal)
        except (TypeError, ValueError):
            return False
        if base_goal <= 0:
            return False

        discount_percent = min(100, 30 * markdown_count)
        self.Goal = max(1, int(base_goal * (100 - discount_percent) / 100))
        print(
            f"Gold card 422 Markdown reduced round {round_num} Goal by {discount_percent}%: "
            f"{base_goal:g} -> {self.Goal}"
        )
        return True

    def _get_current_bear_goal_discount_percent(self):
        discount_percent = game_state.get_bear_goal_discount_percent(self.active_gold_cards)
        if discount_percent <= 0:
            return 0
        bear_count = self._count_active_card_safely(401)
        return min(
            100,
            discount_percent + bear_count * self._get_percentage_amplifier_bonus(),
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
        for card_id in self.card_actions:
            self.card_actions[card_id] *= multiplier
        print(f"Active card 204 Contango multiplied Gain/Drop values by {multiplier}.")

    def _apply_silver_rollover_bonus(self):
        bonus = self._count_active_silver_card(208)
        if bonus <= 0:
            return
        for card_id in PRICE_CARD_IDS:
            if card_id in self.card_turns:
                self.card_turns[card_id] += bonus
        print(f"Active card 208 Rollover extended Gain/Drop durations by {bonus}.")

    def _apply_silver_last_turn_bonuses(self):
        if getattr(self, "boss_block_card_turn_extensions", False):
            return 0
        turn_bonuses = {
            202: 1,
            203: 2,
            301: 1,
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

    def _apply_frugality_turn_bonus(self):
        """Apply and immediately clear turns banked for this round."""
        if getattr(self, "_initial_saved_state", None) is not None:
            return 0
        bonus = game_state.consume_frugality()
        if bonus <= 0:
            return 0
        if getattr(self, "boss_block_card_turn_extensions", False):
            print(f"Boss blocked Frugality from adding {bonus} turn(s).")
            return 0
        self.LastTurn += bonus
        print(f"Frugality added {bonus} turn(s): LastTurn={self.LastTurn}")
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return bonus

    def _settle_frugality_for_finished_round(self):
        """Bank a carry only when card 209 was active in the finished round."""
        game_state.clear_frugality()
        return self._store_frugality_for_next_round()

    def _store_frugality_for_next_round(self):
        """Card 209: preserve this round's unused turns after the card is spent."""
        if not self._has_active_silver_card(209):
            return 0
        try:
            remaining_turns = max(0, int(self.LastTurn) - int(self.Day))
        except (TypeError, ValueError):
            remaining_turns = 0
        return game_state.set_frugality(remaining_turns)

    def _apply_final_auto_liquidation_if_needed(self):
        """Sell remaining shares before the final result check."""
        if self.final_auto_liquidation_applied:
            return False
        if self.win_lose_state is not None or self.Day != self.LastTurn:
            return False

        sale_percent = self._get_current_rebate_sale_percent()
        if sale_percent is None:
            return False

        gross_value = (
            self.Aquantity * self.Aprice
            + self.Bquantity * self.BPrice
            + self.Cquantity * self.CPrice
        )
        if gross_value <= 0:
            self.final_auto_liquidation_applied = True
            return False

        proceeds = (gross_value * sale_percent) // 100
        source = f"Rebate auto-liquidation ({sale_percent}%)"

        self._start_final_auto_liquidation_animation(
            {
                "source": source,
                "gross_value": gross_value,
                "proceeds": proceeds,
                "start_money": int(self.Money),
                "target_money": int(self.Money) + proceeds,
                "start_quantities": {
                    "Aquantity": int(self.Aquantity),
                    "Bquantity": int(self.Bquantity),
                    "Cquantity": int(self.Cquantity),
                },
            }
        )
        return True

    def _get_uptrend_rebate_bonus_percent(self):
        uptrend_count = self._count_active_card_safely(410)
        if uptrend_count <= 0:
            return 0
        try:
            base_bonus = max(0, int(float(game_state.napoleondors or 0)))
        except (TypeError, ValueError):
            return 0
        return uptrend_count * (
            base_bonus * GOLD_UPTREND_PERCENT_PER_NAPOLEONDOR
            + self._get_percentage_amplifier_bonus()
        )

    def _get_stewardship_rebate_bonus_percent(self):
        stewardship_count = self._count_active_card_safely(423)
        if stewardship_count <= 0:
            return 0
        shareholder_count = 0
        for card_id in list(getattr(self, "hand_cards", []) or []):
            try:
                is_shareholder = int(card_id) == 100
            except (TypeError, ValueError):
                is_shareholder = False
            if is_shareholder:
                shareholder_count += 1
        return stewardship_count * shareholder_count * 20

    def _get_windfall_rebate_bonus_percent(self):
        windfall_count = self._count_active_card_safely(426)
        if windfall_count <= 0:
            return 0
        return (
            windfall_count
            * game_state.get_windfall_boss_victories()
            * game_state.WINDFALL_REBATE_BONUS_PER_BOSS
        )

    def _apply_risk_premium_round_start_bonus(self):
        if self._initial_saved_state is not None:
            return False
        return game_state.record_risk_premium_h_round(
            self.active_gold_cards,
            self.difficulty,
        )

    def _get_risk_premium_rebate_bonus_percent(self):
        return game_state.get_risk_premium_rebate_bonus_percent(
            getattr(self, "active_gold_cards", []) or []
        )

    def _get_current_rebate_sale_percent(self):
        full_price = self._has_active_silver_card(201)
        gold_rebate_count = self._count_active_card_safely(407)
        discounted = self._has_played_side_card(110)
        # Keep bonus getters inactive when no base card enables auto-liquidation.
        if gold_rebate_count <= 0 and not full_price and not discounted:
            return None
        return calculate_rebate_sale_percent(
            full_price=full_price,
            discounted=discounted,
            gold_rebate_count=gold_rebate_count,
            amplifier_bonus=self._get_percentage_amplifier_bonus() if gold_rebate_count > 0 else 0,
            fall_bonus=self.rebate_a_fall_bonus_percent if gold_rebate_count > 0 else 0,
            additional_bonus_percent=(
                self._get_uptrend_rebate_bonus_percent()
                + self._get_stewardship_rebate_bonus_percent()
                + self._get_windfall_rebate_bonus_percent()
                + self._get_risk_premium_rebate_bonus_percent()
            ),
        )

    def _start_final_auto_liquidation_animation(self, liquidation):
        duration_ms = 1200
        if self.cash_register_sound:
            try:
                duration_ms = max(1, int(self.cash_register_sound.get_length() * 1000))
            except Exception:
                duration_ms = 1200
            self.cash_register_sound.play()

        now = pygame.time.get_ticks()
        self.final_auto_liquidation_animation = {
            **liquidation,
            "start_time": now,
            "duration_ms": duration_ms,
        }
        self._start_rebate_card_jump_animations()

    def _start_rebate_card_jump_animations(self):
        jump_delay_ms = 500
        for slot, card_id in enumerate(self.side_cards_top):
            try:
                is_rebate = int(card_id) == 110
            except (TypeError, ValueError):
                is_rebate = False
            if is_rebate:
                self._start_card_jump_animation(self.side_card_jump_animations, slot, delay_ms=jump_delay_ms)

        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_rebate = int(card_id) in (201, 407, 410, 423)
            except (TypeError, ValueError):
                is_rebate = False
            if is_rebate:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot, delay_ms=jump_delay_ms)

    def update_final_auto_liquidation_animation(self):
        anim = self.final_auto_liquidation_animation
        if not anim:
            return

        now = pygame.time.get_ticks()
        duration_ms = max(1, int(anim.get("duration_ms", 1)))
        progress = min(1.0, max(0.0, (now - anim.get("start_time", now)) / duration_ms))
        eased = 1.0 - (1.0 - progress) * (1.0 - progress)

        start_money = int(anim.get("start_money", 0))
        target_money = int(anim.get("target_money", start_money))
        start_quantities = anim.get("start_quantities") or {}

        self.Money = int(round(start_money + (target_money - start_money) * eased))
        self.Aquantity = int(round(int(start_quantities.get("Aquantity", 0)) * (1.0 - eased)))
        self.Bquantity = int(round(int(start_quantities.get("Bquantity", 0)) * (1.0 - eased)))
        self.Cquantity = int(round(int(start_quantities.get("Cquantity", 0)) * (1.0 - eased)))

        if progress < 1.0:
            return

        self.Money = target_money
        self.Aquantity = 0
        self.Bquantity = 0
        self.Cquantity = 0
        self.final_auto_liquidation_applied = True
        self.final_auto_liquidation_animation = None
        print(
            f"{anim.get('source', 'Rebate')} auto-liquidation: "
            f"gross={anim.get('gross_value', 0)}, proceeds={anim.get('proceeds', 0)}, "
            f"Money={self.Money}"
        )
        self._check_win_lose()
        self._finish_deferred_turn_resolution_after_final_liquidation()

    def _finish_deferred_turn_resolution_after_final_liquidation(self):
        if not self.turn_resolution_active or self.win_lose_state is None:
            return
        self.pending_draws = 0
        self.turn_resolution_active = False
        self.red_effects_applied_this_resolution = False
        self._clear_hand_negative_overlay_hold()
        if not self.hand_compact_anim and not self.hand_draw_anim:
            self._save_active_game()
    
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
            get_boss_number_from_filename=get_boss_number_from_filename,
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
            reward * self._count_active_silver_card(card_id)
            for card_id, reward in obligation_rewards.items()
        )
        if earned <= 0:
            return 0
        game_state.add_napoleondors(self.level_number, earned)
        print(f"Active Obligation cards awarded {earned} napoleondors after victory.")
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return earned

    def _apply_commission_win_bonus(self):
        commission_count = self._count_active_silver_card(303)
        if commission_count <= 0:
            return 0
        bonus_per_card = 2 if self.is_boss_fight else 1
        earned = commission_count * bonus_per_card
        game_state.add_napoleondors(self.level_number, earned)
        print(
            f"Active Commission card awarded {earned} napoleondor(s) "
            f"after {'boss victory' if self.is_boss_fight else 'round victory'}."
        )
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return earned

    def _apply_nabob_win_bonus(self, finance_entries):
        nabob_count = self._count_active_silver_card(SILVER_NABOB_CARD_ID)
        if nabob_count <= 0:
            return 0

        excluded_sources = {"starting_bonus", "account_balance", "total", "nabob"}
        round_income = sum(
            max(0.0, float(entry.get("amount", 0) or 0))
            for entry in finance_entries or []
            if str(entry.get("source") or "") not in excluded_sources
        )
        if round_income <= 0:
            return 0

        # Each additional copy doubles the already increased result again.
        earned = round_income * ((2 ** nabob_count) - 1)
        game_state.add_napoleondors(self.level_number, earned)
        print(
            f"Active Nabob card(s) awarded {earned} napoleondor(s) "
            f"from {round_income} round income; copies={nabob_count}."
        )
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return earned

    def _apply_shareholder_base_win_bonus(self):
        card_count = self._count_active_card_safely(GOLD_SHAREHOLDER_BASE_CARD_ID)
        if card_count <= 0:
            return 0
        shareholder_count = max(
            0,
            int(getattr(self, "shareholder_effect_count", 0) or 0),
        )
        earned = card_count * shareholder_count
        if earned > 0:
            game_state.add_napoleondors(self.level_number, earned)
        print(
            "Active Shareholder Base card(s) awarded "
            f"{earned} napoleondor(s): cards={card_count}, "
            f"shareholders={shareholder_count}."
        )
        if earned > 0 and self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return earned

    def _build_finance_report_entries(
        self,
        pending_entries,
        opening_balance=0,
        interest_amount=0,
        boss_reward_amount=0,
        commission_amount=0,
        obligation_amount=0,
        long_amount=0,
        shareholder_base_amount=0,
        shareholder_base_active=False,
        nabob_amount=0,
    ):
        labels = {
            "starting_bonus": self._get_text("FinanceStartingBonus", "Стартовый бонус"),
            "account_balance": self._get_text("FinanceAccountBalance", "Остаток на счету"),
            "interest": self._get_text("FinanceInterest", "Проценты"),
            "loan_profit": self._get_text("FinanceLoanProfit", "Loan дал прибыль"),
            "sideway": self._get_text("FinanceSideway", "Бонус Sideway"),
            "full_deployment": self._get_text(
                "FinanceFullDeployment",
                "Бонус Full Deployment",
            ),
            "card_sales": self._get_text("FinanceCardSales", "Продажа карт"),
            "junk_bond": self._get_text("FinanceJunkBond", "Junk Bond дал прибыль"),
            "junk_bond_refund": self._get_text("FinanceJunkBondRefund", "Возврат Junk Bond"),
            "other_income": self._get_text("FinanceOtherIncome", "Прочий доход"),
        }
        accumulated = {}
        order = []

        def add(source, label, amount, allow_zero=False):
            try:
                value = float(amount or 0)
            except (TypeError, ValueError):
                return
            if value < 0 or (value == 0 and not allow_zero):
                return
            if source not in accumulated:
                order.append(source)
                accumulated[source] = {"source": source, "label": label, "amount": 0.0}
            accumulated[source]["amount"] += value

        is_first_report = any(
            str(entry.get("source") or "") == "starting_bonus"
            for entry in (pending_entries or [])
            if isinstance(entry, dict)
        )
        if is_first_report:
            for entry in pending_entries or []:
                if str(entry.get("source") or "") == "starting_bonus":
                    add("starting_bonus", labels["starting_bonus"], entry.get("amount"))
        else:
            add("account_balance", labels["account_balance"], opening_balance, allow_zero=True)

        add("interest", labels["interest"], interest_amount)

        if self.is_boss_fight:
            base_victory = game_state.get_boss_victory_napoleondor_reward(self.level_number)
        else:
            base_victory = game_state.get_round_victory_napoleondor_reward(
                self.level_number,
                self.difficulty,
                get_boss_number_from_filename(self.boss_filename),
            )
        add(
            "victory_reward",
            self._get_text("FinanceVictoryReward", "Награда за победу"),
            base_victory,
        )

        add(
            "profit_bonus",
            self._get_text("FinanceProfitBonus", "Бонус Profit"),
            game_state.profit_reward_bonus if base_victory > 0 else 0,
        )

        for entry in pending_entries or []:
            source = str(entry.get("source") or "other_income")
            if source == "starting_bonus":
                continue
            if source not in ("sideway", "full_deployment"):
                continue
            add(source, labels.get(source, labels["other_income"]), entry.get("amount"))

        add("boss_reward", self._get_text("FinanceBossReward", "Награда босса"), boss_reward_amount)
        add("commission", self._get_text("FinanceCommission", "Комиссия"), commission_amount)
        add("obligation", self._get_text("FinanceObligation", "Облигации"), obligation_amount)
        add("long_profit", self._get_text("FinanceLongProfit", "Long дал прибыль"), long_amount)
        add(
            "shareholder_base",
            self._get_text("FinanceShareholderBase", "Бонус Shareholder Base"),
            shareholder_base_amount,
            allow_zero=shareholder_base_active,
        )
        add("nabob", self._get_text("FinanceNabob", "Бонус Набоба"), nabob_amount)
        entries = [accumulated[source] for source in order]
        if entries:
            entries.append(
                {
                    "source": "total",
                    "label": self._get_text("FinanceTotal", "Всего"),
                    "amount": sum(float(entry.get("amount", 0) or 0) for entry in entries),
                }
            )
        return entries

    def _should_show_finance_report(self):
        try:
            return int(self.level_number or 0) > 1 and not bool(
                getattr(self, "is_final_boss", False)
            )
        except (TypeError, ValueError):
            return False

    def _get_active_result_report_image(self):
        stage = getattr(self, "result_report_stage", "cards")
        if stage == "finance":
            return getattr(self, "finance_report_image", None)
        if stage == "card_report":
            return getattr(self, "card_report_image", None)
        return None

    def _play_result_report_rustle(self):
        sound = getattr(self, "report_rustle_sound", None)
        if sound and self._get_active_result_report_image():
            sound.play()

    def _get_pending_victory_napoleondor_reward(self):
        if self.is_boss_fight:
            base_reward = game_state.get_boss_victory_napoleondor_reward(self.level_number)
        else:
            boss_number = get_boss_number_from_filename(self.boss_filename)
            base_reward = game_state.get_round_victory_napoleondor_reward(
                self.level_number,
                self.difficulty,
                boss_number,
            )
        if base_reward <= 0:
            return 0
        return game_state.get_victory_napoleondor_reward(base_reward)

    def _draw_win_napoleondor_reward(self, amount, font, center_x, center_y):
        amount_value = float(amount or 0)
        amount_text = str(int(amount_value)) if amount_value.is_integer() else f"{amount_value:g}"
        text_surface = font.render(amount_text, True, PAPER_COLOR)
        icon = self.napoleondor_image
        icon_width = icon.get_width() if icon else 0
        spacing = 10 if icon else 0
        total_width = icon_width + spacing + text_surface.get_width()
        start_x = center_x - total_width // 2
        if icon:
            icon_rect = icon.get_rect(midleft=(start_x, center_y))
            self.screen.blit(icon, icon_rect.topleft)
            start_x = icon_rect.right + spacing
        self.screen.blit(text_surface, text_surface.get_rect(midleft=(start_x, center_y)))

    @staticmethod
    def _format_finance_amount(amount):
        value = float(amount or 0)
        return str(int(value)) if value.is_integer() else f"{value:g}"

    @staticmethod
    def _get_finance_report_shake(stamp_state, elapsed_ms):
        if stamp_state != "flying" or elapsed_ms < 0 or elapsed_ms >= 180:
            return 0, 0
        fade = 1.0 - elapsed_ms / 180.0
        amplitude = max(1, int(round(5 * fade)))
        direction = -1 if (elapsed_ms // 30) % 2 else 1
        return direction * amplitude, -direction * max(1, amplitude // 2)

    @staticmethod
    def _get_stamp_camera_flight(progress):
        normalized = max(0.0, min(1.0, float(progress or 0)))
        eased = normalized * normalized
        return 1.0 + 3.2 * eased, max(0, min(255, int(round(255 * (1.0 - normalized)))))

    def _draw_finance_report_rows(self, report_rect):
        row_y = report_rect.top + int(report_rect.height * 0.43)
        row_count = max(1, len(self.finance_report_entries))
        row_area_bottom = report_rect.top + int(report_rect.height * 0.74)
        row_step = min(
            max(24, int(report_rect.height * 0.047)),
            max(24, (row_area_bottom - row_y) // row_count),
        )
        font = pygame.font.Font(self.font_path, max(18, min(27, row_step - 7)))
        label_x = report_rect.left + int(report_rect.width * 0.20)
        amount_right = report_rect.left + int(report_rect.width * 0.91)
        amount_x = report_rect.left + int(report_rect.width * 0.89)
        for index, entry in enumerate(self.finance_report_entries):
            y = row_y + index * row_step
            if entry.get("source") == "total":
                pygame.draw.line(
                    self.screen,
                    PAPER_COLOR,
                    (label_x, y - 5),
                    (amount_right, y - 5),
                    2,
                )
            label_surface = font.render(str(entry.get("label") or ""), True, PAPER_COLOR)
            amount_surface = font.render(
                self._format_finance_amount(entry.get("amount")),
                True,
                PAPER_COLOR,
            )
            self.screen.blit(label_surface, (label_x, y))
            self.screen.blit(amount_surface, (amount_x, y))

    def _get_card_report_rows(self):
        temporary_counts = {}
        for card_id in game_state.round_reward_cards.get(self.level_number, []) or []:
            try:
                normalized = int(card_id)
            except (TypeError, ValueError):
                continue
            temporary_counts[normalized] = temporary_counts.get(normalized, 0) + 1

        rows = []
        for card_id in self.last_earned_cards or []:
            try:
                normalized = int(card_id)
            except (TypeError, ValueError):
                normalized = card_id
            if game_state.is_silver_card(normalized):
                label = self._get_text(
                    "CardReportSilver",
                    "Серебряная карта. Пропадёт только тогда, когда вы её используете.",
                )
            elif game_state.is_gold_card(normalized):
                label = self._get_text(
                    "CardReportGold",
                    "Золотая карта. Пропадёт после поражения.",
                )
            elif temporary_counts.get(normalized, 0) > 0:
                temporary_counts[normalized] -= 1
                label = self._get_text(
                    "CardReportTemporary",
                    "Временная карта. Пропадёт после победы над боссом.",
                )
            elif getattr(self, "is_boss_fight", False) and not getattr(
                self,
                "is_final_boss",
                False,
            ):
                label = self._get_text(
                    "CardReportBossReward",
                    "Бонус за победу над боссом. Пропадёт после поражения.",
                )
            else:
                label = self._get_text(
                    "CardReportPermanent",
                    "Вы получили постоянную карту, теперь она всегда будет в вашей стартовой колоде",
                )
            rows.append({"card_id": normalized, "label": label})
        return rows

    def _get_card_report_notice(self):
        if getattr(self, "golden_stocks_reward_card", None) is None:
            return None
        return self._get_text(
            "CardReportGoldenStocksTriggered",
            "Golden Stocks сработал!",
        )

    def _get_card_report_boss_description(self):
        if not getattr(self, "is_boss_fight", False):
            return None
        if getattr(self, "is_final_boss", False):
            return getattr(self, "reward_window_text", None) or self._get_final_boss_reward_text()
        random_reward = getattr(self, "random_boss_reward_text", None)
        if random_reward:
            return random_reward
        boss_number = get_boss_number_from_filename(getattr(self, "boss_filename", None))
        if not boss_number and getattr(self, "boss_index", None) is not None:
            boss_number = get_boss_number_from_index(
                getattr(self, "level_number", 0),
                getattr(self, "boss_index", None),
                getattr(self, "defeated_count", 0),
            )
        if not boss_number:
            return None
        if boss_number == 5:
            return self._get_text(
                "CardReportBoss5Reward",
                "Игра длится на два хода дольше.",
            )
        # Arkwright's three silver cards are already displayed individually
        # above, so repeating the same reward sentence adds no information.
        if boss_number == 6:
            return None
        return self._get_text(f"Boss{boss_number}Reward", f"Boss {boss_number} reward")

    @staticmethod
    def _get_card_report_footer_ratio(row_count):
        return min(0.80, 0.68 + max(0, int(row_count or 0)) * 0.04)

    def _draw_card_report_boss_text(self, report_rect, description_top, text_x, row_count):
        title_font = pygame.font.Font(self.font_path, 29)
        if getattr(self, "is_final_boss", False):
            title = self._get_text(
                "CardReportLevelCompleteTitle",
                "Вы разблокировали новый уровень!",
            )
        else:
            title = self._get_text(
                "CardReportBossTitle",
                "Бонус за победу над боссом:",
            )
        title_surface = title_font.render(title, True, PAPER_COLOR)
        title_rect = title_surface.get_rect(
            left=text_x,
            top=report_rect.top + int(report_rect.height * 0.275),
        )
        self.screen.blit(title_surface, title_rect.topleft)

        footer = self._get_text(
            "CardReportTemporaryReset",
            "Временные карты обнулились",
        )
        footer_font = pygame.font.Font(self.font_path, 26)
        footer_surface = footer_font.render(footer, True, PAPER_COLOR)
        footer_rect = footer_surface.get_rect(
            left=text_x,
            top=report_rect.top + int(
                report_rect.height * self._get_card_report_footer_ratio(row_count)
            ),
        )

        description = self._get_card_report_boss_description()
        if description:
            text_width = report_rect.right - text_x - int(report_rect.width * 0.10)
            available_height = max(0, footer_rect.top - description_top - 12)
            for font_size in range(27, 16, -1):
                description_font = pygame.font.Font(self.font_path, font_size)
                lines = wrap_text(str(description), description_font, text_width)
                line_height = description_font.get_height() + 3
                if len(lines) * line_height <= available_height or font_size == 17:
                    break
            for line_index, line in enumerate(lines):
                surface = description_font.render(line, True, PAPER_COLOR)
                self.screen.blit(
                    surface,
                    (text_x, description_top + line_index * line_height),
                )
        self.screen.blit(footer_surface, footer_rect.topleft)

    @staticmethod
    def _get_card_report_card_width(slot_height):
        card_ratio = 99 / 171.0
        original_width = max(44, min(92, int((slot_height - 12) * card_ratio)))
        enlarged_width = int(round(original_width * 1.15))
        fit_width = max(1, int(slot_height * card_ratio))
        return max(1, int(round(min(enlarged_width, fit_width) * 0.85)))

    @staticmethod
    def _get_card_report_hover_width(card_width):
        return max(1, int(round(card_width * 1.20)))

    def _draw_card_report_rows(self, report_rect):
        rows = self._get_card_report_rows()
        is_boss_report = bool(getattr(self, "is_boss_fight", False))
        notice = self._get_card_report_notice()
        content_top_ratio = 0.325 if is_boss_report else (0.32 if notice else 0.27)
        content_top = report_rect.top + int(report_rect.height * content_top_ratio)
        if is_boss_report:
            cards_height = min(
                int(report_rect.height * 0.36),
                len(rows) * int(report_rect.height * 0.15),
            )
            content_bottom = content_top + cards_height
        else:
            content_top = report_rect.top + int(report_rect.height * (0.32 if notice else 0.29))
            content_bottom = report_rect.top + int(report_rect.height * 0.835)
        slot_height = max(70, (content_bottom - content_top) // max(1, len(rows)))
        card_ratio = 99 / 171.0
        card_width = self._get_card_report_card_width(slot_height)
        card_height = int(card_width / card_ratio)
        card_x = report_rect.left + int(report_rect.width * 0.14)
        text_x = report_rect.left + int(report_rect.width * 0.29)
        text_width = report_rect.right - text_x - int(report_rect.width * 0.10)
        font = pygame.font.Font(self.font_path, 27 if len(rows) <= 3 else 22)
        if not is_boss_report:
            title_font = pygame.font.Font(self.font_path, 29)
            title = self._get_text(
                "CardReportNewCardsTitle",
                "Вы получили новые карты:",
            )
            title_surface = title_font.render(title, True, PAPER_COLOR)
            self.screen.blit(
                title_surface,
                (
                    text_x,
                    report_rect.top + int(report_rect.height * 0.245),
                ),
            )
        if notice:
            notice_font = pygame.font.Font(self.font_path, 27)
            notice_surface = notice_font.render(notice, True, PAPER_COLOR)
            notice_rect = notice_surface.get_rect(
                left=text_x,
                bottom=content_top - 10,
            )
            self.screen.blit(notice_surface, notice_rect.topleft)
        hovered_card = None
        mouse_pos = pygame.mouse.get_pos()
        for index, row in enumerate(rows):
            slot_top = content_top + index * slot_height
            card_y = slot_top + max(0, (slot_height - card_height) // 2)
            card_image = self._load_winlose_card(row["card_id"], card_width)
            if card_image:
                self.screen.blit(card_image, (card_x, card_y))
                card_rect = card_image.get_rect(topleft=(card_x, card_y))
                if card_rect.collidepoint(mouse_pos):
                    hovered_card = {
                        "card_id": row["card_id"],
                        "rect": card_rect,
                    }
            lines = wrap_text(str(row["label"]), font, text_width)
            line_height = font.get_height() + 4
            text_y = slot_top + max(0, (slot_height - len(lines) * line_height) // 2)
            for line_index, line in enumerate(lines):
                surface = font.render(line, True, PAPER_COLOR)
                self.screen.blit(surface, (text_x, text_y + line_index * line_height))
        if is_boss_report:
            self._draw_card_report_boss_text(
                report_rect,
                content_bottom + int(report_rect.height * 0.018),
                text_x,
                len(rows),
            )
        if hovered_card:
            hover_width = self._get_card_report_hover_width(card_width)
            hover_image = self._load_winlose_card(hovered_card["card_id"], hover_width)
            if hover_image:
                hover_rect = hover_image.get_rect(center=hovered_card["rect"].center)
                self.screen.blit(hover_image, hover_rect.topleft)
            self.card_report_tooltip = (hovered_card["card_id"], mouse_pos)

    def _draw_finance_report(self):
        report_image = self._get_active_result_report_image()
        if not report_image:
            return
        self.card_report_tooltip = None
        now = pygame.time.get_ticks()
        stamp_elapsed = now - int(self.finance_stamp_started_at or now)
        shake_x, shake_y = self._get_finance_report_shake(
            self.finance_stamp_state,
            stamp_elapsed,
        )
        report_x = (SCREEN_WIDTH - report_image.get_width()) // 2 + shake_x
        report_y = int(round(self.finance_report_y)) + shake_y
        report_rect = report_image.get_rect(topleft=(report_x, report_y))
        self.screen.blit(report_image, report_rect.topleft)

        if self.result_report_stage == "card_report":
            self._draw_card_report_rows(report_rect)
        else:
            self._draw_finance_report_rows(report_rect)

        stamp_center = (
            report_x + int(report_rect.width * 0.80),
            report_y + int(report_rect.height * 0.93),
        )
        if self.finance_stamp_state in ("flying", "stamped", "closing") and self.stamp_on_paper_image:
            mark_rect = self.stamp_on_paper_image.get_rect(center=stamp_center)
            self.screen.blit(self.stamp_on_paper_image, mark_rect.topleft)

        if self.finance_stamp_state in ("idle", "pressing", "flying") and self.approve_stamp_rotated:
            stamp_image = self.approve_stamp_rotated
            stamp_draw_center = stamp_center
            if self.finance_stamp_state == "pressing":
                progress = min(1.0, (now - self.finance_stamp_started_at) / 170.0)
                stamp_draw_center = (stamp_center[0], stamp_center[1] + int(13 * progress))
            elif self.finance_stamp_state == "flying":
                progress = min(1.0, (now - self.finance_stamp_started_at) / 300.0)
                scale, alpha = self._get_stamp_camera_flight(progress)
                stamp_image = pygame.transform.smoothscale(
                    self.approve_stamp_rotated,
                    (
                        max(1, int(self.approve_stamp_rotated.get_width() * scale)),
                        max(1, int(self.approve_stamp_rotated.get_height() * scale)),
                    ),
                ).convert_alpha()
                stamp_image.set_alpha(alpha)
                eased = progress * progress
                camera_x, camera_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
                travel = 0.55 * eased
                stamp_draw_center = (
                    int(stamp_center[0] + (camera_x - stamp_center[0]) * travel),
                    int(stamp_center[1] + (camera_y - stamp_center[1]) * travel),
                )
            stamp_rect = stamp_image.get_rect(center=stamp_draw_center)
            self.finance_stamp_rect = stamp_rect
            self.screen.blit(stamp_image, stamp_rect.topleft)
        else:
            self.finance_stamp_rect = None
        if self.result_report_stage == "card_report" and self.card_report_tooltip:
            card_id, mouse_pos = self.card_report_tooltip
            self._draw_card_tooltip(card_id, mouse_pos)

    def _apply_long_investment_payout(self):
        payout = game_state.advance_long_investments(self.level_number)
        if payout <= 0:
            return 0
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return int(payout)

    def _apply_golden_stocks_reward(self):
        if self.is_boss_fight:
            return None
        golden_stocks_count = self._count_active_card_safely(302)
        chance_bonus = golden_stocks_count * self._get_probability_amplifier_bonus()
        awarded_card = game_state.resolve_golden_stocks_round(
            self._active_lifecycle_cards(),
            chance_bonus=chance_bonus,
            level_number=self.level_number,
            record_roll=not bool(getattr(self, "test_mode", False)),
        )
        if awarded_card is None:
            if self.profile_slot and not self.test_mode:
                profile_manager.save_progress_from_game_state(self.profile_slot)
            return None
        self.last_earned_cards.append(awarded_card)
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return awarded_card

    def _apply_bill_of_exchange_shop_discount(self):
        if not self._has_active_silver_card(215):
            return
        game_state.set_pending_shop_discount(50 + self._get_percentage_amplifier_bonus())

    def _record_bear_victory_progress(self):
        if not game_state.record_bear_victory(self.active_gold_cards):
            return
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)

    def _record_windfall_boss_victory_progress(self):
        if not self.is_boss_fight:
            return False
        if not game_state.record_windfall_boss_victory(self.active_gold_cards):
            return False
        if self.profile_slot and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        return True
    
    def _record_stats_result(self, won):
        if self.test_mode or self._stats_recorded:
            return

        boss_number = self._get_active_boss_number()
        round_label = build_round_label(self.round_num, is_boss_fight=self.is_boss_fight)
        difficulty_label = build_difficulty_label(self.difficulty, is_boss_fight=self.is_boss_fight)
        sequential_round_number = build_sequential_round_number(
            self.level_number,
            round_num=self.round_num,
            boss_position=int(self.defeated_count or 0) + 1,
            is_boss_fight=self.is_boss_fight,
            boss_number=boss_number,
        )
        earned_money = self._get_round_end_earned_money()
        update_game_stats(
            self.level_number,
            boss_number,
            round_label,
            won,
            difficulty_label,
            earned_money,
            sequential_round_number,
        )
        self._stats_recorded = True

    def _get_round_end_earned_money(self):
        return int(self.Money or 0) + self._get_round_end_share_value()

    def _get_round_end_share_value(self):
        return (
            int(self.Aquantity or 0) * int(self.Aprice or 0)
            + int(self.Bquantity or 0) * int(self.BPrice or 0)
            + int(self.Cquantity or 0) * int(self.CPrice or 0)
        )
    
    def update_win_lose_animation(self):
        """Update WinLose screen slide animation"""
        if self.win_lose_state is None:
            return

        # dt-based slide from top (smooth regardless of FPS)
        now = pygame.time.get_ticks()
        dt = (now - getattr(self, "_winlose_last_tick", now)) / 1000.0
        self._winlose_last_tick = now
        dt = _clamp_dt_seconds(dt)
        if (
            self.win_lose_state == "win"
            and getattr(self, "result_report_stage", "cards") in ("finance", "card_report")
        ):
            report_image = self._get_active_result_report_image()
            if not report_image:
                if self.result_report_stage == "finance":
                    self.result_report_stage = "card_report"
                    self.finance_report_y = float(SCREEN_HEIGHT + 30)
                    self.finance_stamp_state = "idle"
                    self._play_result_report_rustle()
                else:
                    self.result_transition_ready = "round_select"
                return
            if self.finance_stamp_state == "closing":
                target_y = float(-report_image.get_height() - 30)
            else:
                target_y = float((SCREEN_HEIGHT - report_image.get_height()) // 2)
            slide_speed = max(
                2400.0,
                float(getattr(self, "win_lose_speed_pps", 1200.0)),
            )
            self.finance_report_y = compute_slide_position(
                self.finance_report_y,
                target_y,
                slide_speed,
                dt,
                move_towards,
            )
            elapsed = now - int(self.finance_stamp_started_at or now)
            if self.finance_stamp_state == "pressing" and elapsed >= 170:
                self.finance_stamp_state = "flying"
                self.finance_stamp_started_at = now
            elif self.finance_stamp_state == "flying" and elapsed >= 300:
                self.finance_stamp_state = "stamped"
                self.finance_stamp_started_at = now
            elif self.finance_stamp_state == "stamped" and elapsed >= 360:
                self.finance_stamp_state = "closing"
            elif self.finance_stamp_state == "closing" and self.finance_report_y <= target_y:
                if self.result_report_stage == "finance":
                    self.result_report_stage = "card_report"
                    self.finance_report_y = float(SCREEN_HEIGHT + 30)
                    self.finance_stamp_state = "idle"
                    self.finance_stamp_started_at = 0
                    self.finance_stamp_rect = None
                    self._play_result_report_rustle()
                else:
                    self.result_transition_ready = "round_select"
            return

        if not self.win_lose_image:
            return
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
        is_flat_random_active = self._is_flat_random_active()
        regulation_flat_markets = self._get_regulation_flat_markets()
        blue_chip_markets = self._get_blue_chip_markets()
        shakeout_markets = self._get_shakeout_markets()
        insider_forced_rise_markets = set()
        insider_growth_count = 0
        if self._consume_insider_c_growth_turn():
            insider_forced_rise_markets.add(2)
            insider_growth_count = self._count_active_card_safely(405)
        spoofing_forced_rise_markets = self._get_spoofing_forced_rise_markets()
        spoofing_growth_count = self._get_spoofing_growth_count()
        forced_rise_markets = insider_forced_rise_markets | spoofing_forced_rise_markets
        selling_pressure_entries = self._roll_selling_pressure_markets()
        forced_fall_markets = {
            entry["market"] for entry in selling_pressure_entries
        }
        if is_flat_random_active:
            print("Active card 404 Flat forced all random stock movements to Flat.")
        elif regulation_flat_markets:
            print(
                "Regulation forced random stock movements to Flat for markets: "
                f"{sorted(regulation_flat_markets)}"
            )
        if shakeout_markets:
            self._start_shakeout_animation()
        animation_queue = build_stock_price_animation_queue(
            self.StepA,
            self.StepB,
            self.StepC,
            self.market_cards,
            forced_rise_markets=forced_rise_markets,
            forced_fall_markets=forced_fall_markets,
            probability_card_bonus=self._get_probability_card_bonus(),
            force_flat=is_flat_random_active,
            force_flat_markets=regulation_flat_markets,
            prevent_fall_markets=blue_chip_markets,
            double_fall_markets=shakeout_markets,
            double_fall_bonus=self._get_probability_amplifier_bonus() if shakeout_markets else 0,
            double_fall_count=self._get_shakeout_count(),
        )
        selling_pressure_by_market = {}
        for entry in selling_pressure_entries:
            selling_pressure_by_market.setdefault(entry["market"], []).append(entry)
        for market, entries in selling_pressure_by_market.items():
            base_movement = next(
                (
                    movement
                    for movement in animation_queue
                    if movement.get("market") == market
                    and movement.get("type") == "fall"
                ),
                None,
            )
            if base_movement is not None:
                base_movement.update(
                    source="selling_pressure",
                    card_slot=entries[0]["card_slot"],
                )
            for entry in entries[1:]:
                animation_queue.append(
                    {
                        "market": market,
                        "type": "fall",
                        "price_change": -(self.StepA, self.StepB, self.StepC)[market],
                        "source": "selling_pressure",
                        "card_slot": entry["card_slot"],
                    }
                )
        insider_slots = []
        insider_base_growth_count = 0
        if insider_forced_rise_markets:
            for slot, card_id in enumerate(self._active_lifecycle_cards()):
                try:
                    if int(card_id) == 405:
                        insider_slots.append(slot)
                except (TypeError, ValueError):
                    continue
            for movement in animation_queue:
                if movement.get("market") == 2 and movement.get("type") == "rise":
                    movement["source"] = "insider"
                    if insider_slots:
                        movement["card_slot"] = insider_slots[0]
                    insider_base_growth_count = 1
                    break
        market_steps = (self.StepA, self.StepB, self.StepC)
        for market in spoofing_forced_rise_markets:
            base_growth_count = 0 if market in forced_fall_markets else 1
            for _copy_index in range(max(0, spoofing_growth_count - base_growth_count)):
                animation_queue.append(
                    {
                        "market": market,
                        "type": "rise",
                        "price_change": market_steps[market],
                        "source": "spoofing",
                    }
                )
        for copy_index in range(insider_base_growth_count, insider_growth_count):
            movement = {
                "market": 2,
                "type": "rise",
                "price_change": self.StepC,
                "source": "insider",
            }
            if copy_index < len(insider_slots):
                movement["card_slot"] = insider_slots[copy_index]
            animation_queue.append(movement)
        animation_queue = self._apply_momentum_to_random_movements(animation_queue)
        animation_queue.extend(self._build_advance_movements())
        if self._advance_surge_counter():
            animation_queue.append(
                {
                    "market": 0,
                    "type": "rise",
                    "price_change": 0,
                    "source": "surge",
                }
            )
        return animation_queue

    def _roll_selling_pressure_markets(self):
        blue_chip_markets = self._get_blue_chip_markets()
        eligible_markets = [market for market in (0, 1, 2) if market not in blue_chip_markets]
        if not eligible_markets:
            return []
        entries = []
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_selling_pressure = int(card_id) == GOLD_SELLING_PRESSURE_CARD_ID
            except (TypeError, ValueError):
                is_selling_pressure = False
            if not is_selling_pressure:
                continue
            market = eligible_markets[random.randint(1, len(eligible_markets)) - 1]
            entries.append({"market": market, "card_slot": slot})
        if entries:
            print(
                "Gold card 432 Selling Pressure forced market falls: "
                f"markets={[entry['market'] for entry in entries]}"
            )
        return entries

    def _advance_surge_counter(self):
        if not self._has_active_silver_card(415) or self.surge_triggered:
            self.surge_traded_this_turn = False
            return False

        if self.surge_traded_this_turn:
            self.surge_turns_without_trade = 0
        else:
            self.surge_turns_without_trade += 1
        self.surge_traded_this_turn = False

        if self.surge_turns_without_trade < 4:
            return False
        self.surge_triggered = True
        return True

    def _get_shakeout_markets(self):
        if not self._has_active_silver_card(413):
            return set()
        quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
        return {
            market
            for market, quantity in enumerate(quantities)
            if int(quantity or 0) <= 0
        }

    def _get_shakeout_count(self):
        return self._count_active_card_safely(413)

    def _get_spoofing_growth_count(self):
        current_day = int(self.Day or 0)
        if current_day == 4:
            return (
                self._count_active_card_safely(411)
                + self._count_active_card_safely(412)
            )
        if current_day == 8:
            return self._count_active_card_safely(412)
        return 0

    def _start_shakeout_animation(self):
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_shakeout = int(card_id) == 413
            except (TypeError, ValueError):
                is_shakeout = False
            if is_shakeout:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)

    def _get_spoofing_forced_rise_markets(self):
        current_day = int(self.Day or 0)
        has_spoofing = current_day == 4 and self._count_active_card_safely(411) > 0
        has_spoofing_plus = current_day in (4, 8) and self._count_active_card_safely(412) > 0
        if not has_spoofing and not has_spoofing_plus:
            return set()

        quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
        forced_markets = {
            market
            for market, quantity in enumerate(quantities)
            if int(quantity or 0) > 0
        }
        if not forced_markets:
            return set()

        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                normalized_id = int(card_id)
            except (TypeError, ValueError):
                continue
            if (normalized_id == 411 and has_spoofing) or (
                normalized_id == 412 and has_spoofing_plus
            ):
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        print(
            "Spoofing forced growth for held markets: "
            f"day={current_day}, markets={sorted(forced_markets)}"
        )
        return forced_markets

    def _start_lifecycle_turn_reminder(self, day=None, now=None):
        try:
            current_day = int(self.Day if day is None else day)
        except (TypeError, ValueError):
            return []
        if current_day not in (1, 2, 4, 8):
            return []
        if current_day in self.lifecycle_reminder_days_started:
            return []

        if current_day in (1, 2):
            if int(getattr(self, "insider_c_growth_turns_remaining", 0) or 0) <= 0:
                return []
            target_ids = {405}
        elif current_day == 4:
            target_ids = {411, 412}
        else:
            target_ids = {412}
        if now is None:
            now = pygame.time.get_ticks()
        started_slots = []
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                normalized_id = int(card_id)
            except (TypeError, ValueError):
                continue
            if normalized_id not in target_ids:
                continue
            self.lifecycle_card_shake_animations[slot] = {
                "start_time": int(now),
                "duration": SPOOFING_REMINDER_DURATION_MS,
            }
            started_slots.append(slot)

        if started_slots:
            self.lifecycle_reminder_days_started.add(current_day)
            print(
                "Lifecycle card reminder started: "
                f"day={current_day}, lifecycle_slots={started_slots}"
            )
        return started_slots

    def _get_lifecycle_card_shake_offset(self, slot, now=None):
        animation = self.lifecycle_card_shake_animations.get(slot)
        if not animation:
            return 0, 0
        if now is None:
            now = pygame.time.get_ticks()
        elapsed = int(now) - int(animation.get("start_time", now))
        duration = max(1, int(animation.get("duration", SPOOFING_REMINDER_DURATION_MS)))
        if elapsed < 0 or elapsed >= duration:
            return 0, 0
        pattern = ((-6, 0), (5, -2), (-4, 1), (6, -1), (-5, 2), (3, 0))
        frame = (elapsed // SPOOFING_REMINDER_FRAME_MS) % len(pattern)
        return pattern[frame]

    def update_lifecycle_card_shake_animations(self, now=None):
        if now is None:
            now = pygame.time.get_ticks()
        expired_slots = []
        for slot, animation in list(self.lifecycle_card_shake_animations.items()):
            elapsed = int(now) - int(animation.get("start_time", now))
            duration = max(1, int(animation.get("duration", SPOOFING_REMINDER_DURATION_MS)))
            if elapsed >= duration:
                expired_slots.append(slot)
        for slot in expired_slots:
            self.lifecycle_card_shake_animations.pop(slot, None)
        return expired_slots

    def _apply_momentum_to_random_movements(self, animation_queue):
        """Gold card 409: repeat each resolved market rise or fall."""
        momentum_count = self._count_active_silver_card(409)
        if momentum_count <= 0:
            return list(animation_queue or [])

        expanded_queue = []
        for movement in animation_queue or []:
            expanded_queue.append(movement)
            if movement.get("type") not in ("rise", "fall"):
                continue
            for _copy_index in range(momentum_count):
                expanded_queue.append({**movement, "source": "momentum"})
        return expanded_queue

    def _consume_insider_c_growth_turn(self):
        remaining = int(getattr(self, "insider_c_growth_turns_remaining", 0) or 0)
        if remaining <= 0:
            return False

        self.insider_c_growth_turns_remaining = remaining - 1
        print(
            "Active card 405 Insider forced C stock growth: "
            f"remaining={self.insider_c_growth_turns_remaining}"
        )
        return True

    def _build_advance_movements(self):
        """Gold card 420: possibly double every market in which the player owns shares."""
        advance_slots = []
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_advance = int(card_id) == 420
            except (TypeError, ValueError):
                is_advance = False
            if is_advance:
                advance_slots.append(slot)
        if not advance_slots:
            return []

        quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
        owned_markets = tuple(
            market for market, quantity in enumerate(quantities) if int(quantity or 0) > 0
        )
        if not owned_markets:
            return []

        chance = min(100, GOLD_ADVANCE_BASE_CHANCE + self._get_probability_amplifier_bonus())
        movements = []
        for slot in advance_slots:
            roll = random.randint(1, 100)
            if roll > chance:
                print(f"Gold card 420 Advance missed: roll={roll}, chance={chance}%")
                continue
            movements.append(
                {
                    "market": owned_markets,
                    "type": "rise",
                    "price_change": 0,
                    "source": "advance",
                    "card_slot": slot,
                }
            )
            print(
                f"Gold card 420 Advance triggered: roll={roll}, chance={chance}%, "
                f"markets={list(owned_markets)}"
            )
        return movements

    def _start_next_price_animation(self, now=None):
        if now is None:
            now = pygame.time.get_ticks()
        next_anim, current_animation = start_next_price_animation(self.price_animation_queue, now)
        if not next_anim:
            return False

        target_markets = next_anim["market"]
        if not isinstance(target_markets, (list, tuple, set)):
            target_markets = (target_markets,)
        if next_anim.get("source") == "surge":
            surge_count = max(1, self._count_active_card_safely(415))
            self.Aprice = max(2, int(self.Aprice or 0) * (3 ** surge_count))
            for slot, card_id in enumerate(self._active_lifecycle_cards()):
                try:
                    is_surge = int(card_id) == 415
                except (TypeError, ValueError):
                    is_surge = False
                if is_surge:
                    self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
            print(f"Active card 415 Surge applied {surge_count} time(s): A={self.Aprice}")
        elif next_anim.get("source") == "advance":
            advance_slot = next_anim.get("card_slot")
            if isinstance(advance_slot, int):
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, advance_slot)
            for market in target_markets:
                if market == 0:
                    self.Aprice = max(2, int(self.Aprice or 0) * 2)
                elif market == 1:
                    self.BPrice = max(2, int(self.BPrice or 0) * 2)
                elif market == 2:
                    self.CPrice = max(2, int(self.CPrice or 0) * 2)
            print(
                "Gold card 420 Advance doubled owned stock prices: "
                f"markets={list(target_markets)}, A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
            )
        else:
            for market in target_markets:
                if self._apply_price_change(market, next_anim["price_change"]):
                    return True
        if next_anim.get("source") == "momentum":
            for slot, card_id in enumerate(self._active_lifecycle_cards()):
                try:
                    is_momentum = int(card_id) == 409
                except (TypeError, ValueError):
                    is_momentum = False
                if is_momentum:
                    self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        elif next_anim.get("source") in ("insider", "selling_pressure"):
            card_slot = next_anim.get("card_slot")
            if card_slot is not None:
                self._start_card_jump_animation(
                    self.lifecycle_card_jump_animations,
                    card_slot,
                )
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
            or self._is_final_auto_liquidation_animating()
            or self.current_price_animation is not None
            or bool(self.price_animation_queue)
            or self.current_card_processing is not None
            or bool(self.price_card_queue)
            or any(bool(slots) for slots in self.card_jump_animations.values())
            or bool(self.side_card_jump_animations)
            or bool(self.lifecycle_card_jump_animations)
            or bool(self.market_clear_animations)
        )

    def _start_turn_resolution(self):
        """Start the same end-turn flow for a button click or an expired boss timer."""
        if self.win_lose_state is not None or self._is_turn_resolution_active():
            return False
        self._reset_drag_state()
        self._start_end_button_press_animation()
        if self.arrow_sound:
            self.arrow_sound.play()
        if self._try_start_waterloo_preview():
            return True
        self.turn_resolution_active = True
        self.effect_finalize_pending = False
        self.red_effects_applied_this_resolution = False
        self.basket_trading_applied_this_resolution = False
        self.sideway_applied_this_resolution = False
        self.continuation_applied_this_resolution = False
        self.continuation_animation_phase = False
        self.c_price_fell_this_resolution = False
        self.manipulation_applied_this_resolution = False
        self.short_seller_counted_markets_this_resolution = set()
        self._hold_hand_negative_overlays_until_next_turn()
        quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
        self.continuation_held_markets_this_turn = {
            market for market, quantity in enumerate(quantities) if quantity > 0
        }
        self.stock_bot_acted_this_resolution = False
        if self._is_level6_alternating_battle():
            self._begin_level6_bot_turn()
            return True

        self._start_market_resolution_after_actions()
        return True

    def _start_market_resolution_after_actions(self):
        """Resolve the shared market after every participant has acted."""
        animation_queue = self._take_waterloo_preview_or_roll()
        self.stock_price_turn_results = list(animation_queue or [])
        self._lock_market_cards()
        if animation_queue:
            self.price_animation_queue = animation_queue.copy()
            self._start_next_price_animation()
        else:
            self._queue_price_cards()
            if self.current_card_processing is None and not self.price_card_queue:
                self._begin_effect_finalize_or_wait()

    def _begin_level6_bot_turn(self):
        self.level6_turn_owner = "bot"
        self.level6_bot_turn_phase = "thinking"
        self.level6_bot_turn_started_at = pygame.time.get_ticks()
        self.level6_bot_turn_decision = None

    @staticmethod
    def _level6_bot_has_activity(decision, key):
        if not isinstance(decision, dict):
            return False
        return any(int(value or 0) > 0 for value in (decision.get(key) or {}).values())

    def _start_level6_bot_ending(self, now):
        self.level6_bot_turn_phase = "ending"
        self.level6_bot_turn_started_at = now
        self._start_end_button_press_animation(LEVEL6_BOT_END_PRESS_MS)
        if getattr(self, "arrow_sound", None):
            self.arrow_sound.play()

    def update_level6_bot_turn(self):
        """Run Bot3 as a visible turn, then hand control to the market."""
        if not self._is_level6_alternating_battle() or not self.level6_bot_turn_phase:
            return False

        now = pygame.time.get_ticks()
        elapsed = now - int(self.level6_bot_turn_started_at)
        if self.level6_bot_turn_phase == "thinking":
            if elapsed < LEVEL6_BOT_THINK_MS:
                return False
            decision = self._run_stock_bot_turn()
            self.level6_bot_turn_decision = decision if isinstance(decision, dict) else {}
            self.stock_bot_acted_this_resolution = True
            if self._level6_bot_has_activity(self.level6_bot_turn_decision, "sold"):
                self.level6_bot_turn_phase = "selling"
            elif self._level6_bot_has_activity(self.level6_bot_turn_decision, "bought"):
                self.level6_bot_turn_phase = "buying"
            else:
                self.level6_bot_turn_phase = "holding"
            self.level6_bot_turn_started_at = now
            return True

        if self.level6_bot_turn_phase == "selling" and elapsed >= LEVEL6_BOT_ACTION_MS:
            if self._level6_bot_has_activity(self.level6_bot_turn_decision, "bought"):
                self.level6_bot_turn_phase = "buying"
                self.level6_bot_turn_started_at = now
            else:
                self._start_level6_bot_ending(now)
            return True

        if self.level6_bot_turn_phase in ("buying", "holding") and elapsed >= LEVEL6_BOT_ACTION_MS:
            self._start_level6_bot_ending(now)
            return True

        if self.level6_bot_turn_phase == "ending" and elapsed >= LEVEL6_BOT_END_PRESS_MS:
            self.level6_bot_turn_phase = None
            self.level6_turn_owner = "market"
            self._start_market_resolution_after_actions()
            return True
        return False

    def _try_start_waterloo_preview(self):
        if getattr(self, "waterloo_preview_movements", None) is not None:
            return False

        waterloo_slots = []
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                if int(card_id) == GOLD_WATERLOO_CARD_ID:
                    waterloo_slots.append(slot)
            except (TypeError, ValueError):
                continue
        if not waterloo_slots:
            return False

        chance = self._get_waterloo_chance()
        triggered_slot = None
        for slot in waterloo_slots:
            roll = random.randint(1, 100)
            if roll <= chance:
                triggered_slot = slot
                print(
                    f"Gold card 430 Waterloo triggered: roll={roll}, chance={chance}%, "
                    f"slot={slot}"
                )
                break
            print(f"Gold card 430 Waterloo missed: roll={roll}, chance={chance}%, slot={slot}")
        if triggered_slot is None:
            return False

        self.waterloo_preview_movements = list(self.update_stock_prices() or [])
        self._start_lifecycle_card_scale_animation(triggered_slot)
        self._reset_boss_turn_timer()
        self._save_active_game()
        return True

    def _take_waterloo_preview_or_roll(self):
        if getattr(self, "waterloo_preview_movements", None) is None:
            return self.update_stock_prices()
        movements = [dict(movement) for movement in self.waterloo_preview_movements]
        self.waterloo_preview_movements = None
        return movements

    def _calculate_waterloo_preview_prices(self, movements=None):
        prices = [int(self.Aprice or 0), int(self.BPrice or 0), int(self.CPrice or 0)]
        for movement in movements if movements is not None else (self.waterloo_preview_movements or []):
            markets = movement.get("market")
            if not isinstance(markets, (list, tuple, set)):
                markets = (markets,)
            source = movement.get("source")
            for market in markets:
                if market not in (0, 1, 2):
                    continue
                if source == "advance":
                    prices[market] = max(2, prices[market] * 2)
                elif source == "surge" and market == 0:
                    surge_count = max(1, self._count_active_card_safely(415))
                    prices[market] = max(2, prices[market] * (3 ** surge_count))
                else:
                    prices[market] = max(2, prices[market] + int(movement.get("price_change", 0) or 0))
        return tuple(prices)

    def _finish_price_animations(self):
        """Finish regular market movement and start Gain/Drop card processing."""
        self.current_price_animation = None
        if getattr(self, "continuation_animation_phase", False):
            self.continuation_animation_phase = False
            self._begin_effect_finalize_or_wait()
            return
        self._apply_sideway_reward_if_needed()
        if self._apply_basket_trading_if_needed():
            self._start_next_price_animation()
            return
        self._queue_price_cards()

        if self.current_card_processing is None and not self.price_card_queue:
            self._begin_effect_finalize_or_wait()

    def _apply_sideway_reward_if_needed(self):
        if getattr(self, "sideway_applied_this_resolution", False):
            return False
        sideway_count = self._count_active_card_safely(416)
        if sideway_count <= 0:
            return False

        base_results = {}
        for movement in list(getattr(self, "stock_price_turn_results", []) or []):
            if movement.get("source") is not None:
                continue
            market = movement.get("market")
            if market in (0, 1, 2) and market not in base_results:
                base_results[market] = movement.get("type")
        if base_results != {0: "unchanged", 1: "unchanged", 2: "unchanged"}:
            return False

        self.sideway_applied_this_resolution = True
        reward = 5 * sideway_count
        game_state.add_napoleondors(self.level_number, reward)
        game_state.record_finance_report_income("sideway", reward)
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_sideway = int(card_id) == 416
            except (TypeError, ValueError):
                is_sideway = False
            if is_sideway:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        if self.profile_slot is not None and not self.test_mode:
            profile_manager.save_progress_from_game_state(self.profile_slot)
        print(
            f"Active card 416 Sideway awarded {reward} napoleondors "
            "for three Flat market results."
        )
        return True

    def _apply_basket_trading_if_needed(self):
        if getattr(self, "basket_trading_applied_this_resolution", False):
            return False

        bonus = self._get_basket_trading_bonus()
        if bonus <= 0:
            return False

        movements = list(getattr(self, "stock_price_turn_results", []) or [])
        rose_markets = {
            entry.get("market")
            for entry in movements
            if entry.get("type") == "rise" and entry.get("source") != "surge"
        }
        if rose_markets != {0, 1, 2}:
            return False

        self.basket_trading_applied_this_resolution = True
        self.price_animation_queue.append(
            {
                "market": (0, 1, 2),
                "type": "rise",
                "price_change": bonus,
                "source": "basket_trading",
            }
        )
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_basket_trading = int(card_id) == 206
            except (TypeError, ValueError):
                is_basket_trading = False
            if is_basket_trading:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        print(
            f"Silver card 206 Basket Trading queued equal growth animations: bonus={bonus}"
        )
        return True

    def _normalize_continuation_growth_streaks(self):
        raw_streaks = list(getattr(self, "continuation_growth_streaks", []) or [])
        normalized = []
        for value in (raw_streaks + [0, 0, 0])[:3]:
            try:
                normalized.append(max(0, int(value)))
            except (TypeError, ValueError):
                normalized.append(0)
        self.continuation_growth_streaks = normalized
        return normalized

    def _reset_continuation_growth_streak(self, market):
        streaks = self._normalize_continuation_growth_streaks()
        if market in (0, 1, 2):
            streaks[market] = 0

    def _build_continuation_bonus_movements(self):
        streaks = self._normalize_continuation_growth_streaks()
        continuation_count = self._count_active_card_safely(419)
        if continuation_count <= 0:
            self.continuation_growth_streaks = [0, 0, 0]
            return []

        base_results = {}
        momentum_rise_counts = [0, 0, 0]
        for movement in list(getattr(self, "stock_price_turn_results", []) or []):
            market = movement.get("market")
            if movement.get("source") == "momentum":
                if market in (0, 1, 2) and movement.get("type") == "rise":
                    momentum_rise_counts[market] += 1
                continue
            if movement.get("source") is None and market in (0, 1, 2) and market not in base_results:
                base_results[market] = movement.get("type")

        held_markets = set(getattr(self, "continuation_held_markets_this_turn", set()) or set())
        current_quantities = (self.Aquantity, self.Bquantity, self.Cquantity)
        current_prices = (self.Aprice, self.BPrice, self.CPrice)
        bonus_movements = []

        for market in range(3):
            if market not in held_markets or current_quantities[market] <= 0:
                streaks[market] = 0
                continue
            if base_results.get(market) != "rise":
                streaks[market] = 0
                continue

            previous_streak = streaks[market]
            growth_count = 1 + momentum_rise_counts[market]
            streaks[market] += growth_count
            bonus_count = (
                max(0, streaks[market] - 1)
                - max(0, previous_streak - 1)
            )
            if bonus_count <= 0:
                continue

            current_price = max(0, int(current_prices[market] or 0))
            target_price = max(
                2,
                int(round(current_price * (1.2 ** (bonus_count * continuation_count)))),
            )
            price_change = target_price - current_price
            if price_change > 0:
                bonus_movements.append(
                    {
                        "market": market,
                        "type": "rise",
                        "price_change": price_change,
                        "source": "continuation",
                    }
                )

        if bonus_movements:
            for slot, card_id in enumerate(self._active_lifecycle_cards()):
                try:
                    is_continuation = int(card_id) == 419
                except (TypeError, ValueError):
                    is_continuation = False
                if is_continuation:
                    self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
            print(f"Gold card 419 Continuation queued bonuses: {bonus_movements}")
        return bonus_movements

    def _begin_effect_finalize_or_wait(self):
        """Apply red cards after market card animations, then draw cards."""
        if not self.turn_resolution_active:
            return

        if not self.red_effects_applied_this_resolution:
            if any(bool(slots) for slots in self.card_jump_animations.values()):
                self.effect_finalize_pending = True
                return

            self._apply_red_card_effects_if_needed()
            if getattr(self, "win_lose_state", None) is not None:
                return
            self._lock_side_cards()
            self.red_effects_applied_this_resolution = True

        if self._has_effect_animations():
            self.effect_finalize_pending = True
            return

        if not getattr(self, "continuation_applied_this_resolution", False):
            continuation_movements = self._build_continuation_bonus_movements()
            self.continuation_applied_this_resolution = True
            if continuation_movements:
                self.effect_finalize_pending = False
                self.continuation_animation_phase = True
                self.price_animation_queue.extend(continuation_movements)
                self._start_next_price_animation()
                return

        self._finalize_turn_resolution()

    def _finalize_turn_resolution(self):
        """Advance/check the day and only then draw replacement cards."""
        if not self.turn_resolution_active:
            return

        self.effect_finalize_pending = False
        self._apply_boss_share_theft_if_needed()
        if not self._is_level6_alternating_battle():
            self._run_stock_bot_turn()
        elif not self.stock_bot_acted_this_resolution:
            print("ERROR: Level 6 market resolved before Bot3 completed its turn.")
            return
        self._burn_cash_for_astor_if_needed()
        self._check_win_lose()
        if self._is_final_auto_liquidation_animating():
            return

        if self.win_lose_state is None:
            if self.Day < self.LastTurn:
                self.Day += 1
                self._check_win_lose()
                if self.win_lose_state is None:
                    self._start_lifecycle_turn_reminder()
                    self._roll_shareholder_market_shutdown()
            else:
                print(f"ERROR: Day==LastTurn but game didn't end! Forcing end.")
                if self.Money >= self.Goal and self._can_win_against_current_boss():
                    next_state, reason = "win", "last_turn"
                elif self.Money >= self.Goal and self._is_stock_bot_boss():
                    next_state, reason = "lose", "stock_bot_boss_ahead"
                else:
                    next_state, reason = self._apply_insurance_if_needed("lose", "last_turn")
                self._finish_win_lose_result(next_state, reason)

        self._clear_hand_negative_overlay_hold()
        if self.win_lose_state is None:
            self._draw_pending_cards()
            self._reset_boss_turn_timer()
        else:
            self.pending_draws = 0
        self.turn_resolution_active = False
        self.red_effects_applied_this_resolution = False
        self.basket_trading_applied_this_resolution = False
        self.sideway_applied_this_resolution = False
        self.continuation_applied_this_resolution = False
        self.continuation_animation_phase = False
        self.stock_bot_acted_this_resolution = False
        self.level6_bot_turn_phase = None
        self.level6_bot_turn_decision = None
        self.level6_turn_owner = "player"
        if not self.hand_compact_anim and not self.hand_draw_anim:
            self._save_active_game()

    def _burn_cash_for_astor_if_needed(self):
        if not getattr(self, "boss_burns_cash_end_turn", False):
            return 0
        if self.win_lose_state is not None:
            return 0
        try:
            burned = max(0, int(self.Money or 0))
        except (TypeError, ValueError):
            burned = 0
        self.Money = 0
        if burned:
            print(f"Astor burned {burned} cash left at end of turn.")
        return burned

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
        boss_number = self._get_active_boss_number()
        if boss_number != 6:
            return
        round_label = build_round_label(self.round_num, is_boss_fight=self.is_boss_fight)
        difficulty_label = build_difficulty_label(self.difficulty, is_boss_fight=self.is_boss_fight)
        sequential_round_number = build_sequential_round_number(
            self.level_number,
            round_num=self.round_num,
            boss_position=int(self.defeated_count or 0) + 1,
            is_boss_fight=self.is_boss_fight,
            boss_number=boss_number,
        )
        update_arkwright_stats(
            self.level_number,
            boss_number,
            round_label,
            difficulty_label,
            outcome,
            sequential_round_number,
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
    
    def _queue_price_cards(self):
        """Queue persistent price-effect cards after all market animations finish."""
        self.price_card_queue = build_price_cards_processing_queue(
            self.market_cards,
            self.market_card_turns,
        )
        
        # Start processing first card if queue is not empty
        if self.price_card_queue:
            self.current_card_processing = self.price_card_queue.pop(0)
            self.card_processing_start_time = pygame.time.get_ticks()
    
    def update_price_card_processing(self):
        """Process one queued price-effect card at a time with a short delay."""
        if self.current_card_processing is None:
            # Check if there are more cards in queue
            if self.price_card_queue:
                self.current_card_processing = self.price_card_queue.pop(0)
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
                if card_id in PRICE_CARD_IDS:
                    card_action = self.market_card_actions[market].get(
                        slot,
                        self.card_actions.get(card_id, 0),
                    )
                    previous_prices = (self.Aprice, self.BPrice, self.CPrice)
                    previous_a_price = previous_prices[0]
                    previous_c_price = previous_prices[2]
                    self.Aprice, self.BPrice, self.CPrice = calculate_price_card_prices(
                        previous_prices,
                        market,
                        card_id,
                        card_action,
                        protected_markets=self._get_blue_chip_markets(),
                    )
                    self._record_rebate_a_fall(previous_a_price, self.Aprice, f"card {card_id}")
                    self._record_c_price_fall(previous_c_price, self.CPrice, f"card {card_id}")
                    if self._record_short_seller_falls(previous_prices, f"card {card_id}"):
                        return

                    # Only cards that actually change a price animate here.
                    if (self.Aprice, self.BPrice, self.CPrice) != previous_prices:
                        self._start_card_jump_animation(self.card_jump_animations[market], slot)

                # Decrement CardTurns
                self.market_card_turns[market][slot] = turns_remaining - 1
        
        # Move to next card
        self.current_card_processing = None
        if self.price_card_queue:
            self.current_card_processing = self.price_card_queue.pop(0)
            self.card_processing_start_time = pygame.time.get_ticks()
        else:
            self._begin_effect_finalize_or_wait()
    
    def _start_card_jump_animation(self, animation_map, key, delay_ms=0):
        animation_map[key] = {
            'offset_y': 0.0,
            'velocity': -8.7,
            'start_time': pygame.time.get_ticks() + int(delay_ms or 0)
        }

    def _start_lifecycle_card_scale_animation(self, slot, now=None):
        if not hasattr(self, "lifecycle_card_scale_animations"):
            self.lifecycle_card_scale_animations = {}
        self.lifecycle_card_scale_animations[slot] = {
            "start_time": pygame.time.get_ticks() if now is None else int(now),
            "duration": 900,
        }

    def _get_lifecycle_card_scale(self, slot, now=None):
        animation = getattr(self, "lifecycle_card_scale_animations", {}).get(slot)
        if not animation:
            return 1.0
        if now is None:
            now = pygame.time.get_ticks()
        duration = max(1, int(animation.get("duration", 900)))
        progress = (int(now) - int(animation.get("start_time", now))) / duration
        if progress < 0 or progress >= 1:
            return 1.0
        pulse = 1.0 - abs(progress * 2.0 - 1.0)
        return 1.0 + 0.2 * pulse

    def update_lifecycle_card_scale_animations(self, now=None):
        if not hasattr(self, "lifecycle_card_scale_animations"):
            self.lifecycle_card_scale_animations = {}
        if now is None:
            now = pygame.time.get_ticks()
        expired = []
        for slot, animation in list(self.lifecycle_card_scale_animations.items()):
            duration = max(1, int(animation.get("duration", 900)))
            if int(now) - int(animation.get("start_time", now)) >= duration:
                expired.append(slot)
        for slot in expired:
            self.lifecycle_card_scale_animations.pop(slot, None)
        return expired

    def _advance_jump_animation_map(self, animation_map, gravity=0.8):
        now = pygame.time.get_ticks()
        slots_to_remove = []
        for key, anim in list(animation_map.items()):
            if now < anim.get('start_time', now):
                continue

            anim['velocity'] += gravity
            anim['offset_y'] += anim['velocity']

            if anim['offset_y'] >= 0 and anim['velocity'] > 0:
                slots_to_remove.append(key)
            if anim['offset_y'] > 0:
                anim['offset_y'] = 0

        for key in slots_to_remove:
            animation_map.pop(key, None)
        return slots_to_remove

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
            and not self.price_card_queue
            and not self._has_effect_animations()
        ):
            self._begin_effect_finalize_or_wait()

    def update_card_jump_animations(self):
        """Update jump animations for persistent price-effect cards."""
        for market in (0, 1, 2):
            self._advance_jump_animation_map(self.card_jump_animations[market])

    def update_side_card_jump_animations(self):
        """Update jump animations for freshly played red cards."""
        self._advance_jump_animation_map(self.side_card_jump_animations)
        self._advance_jump_animation_map(self.lifecycle_card_jump_animations)
    
    def _apply_price_change(self, market, price_change):
        """Apply price change to the specified market. Ensures price doesn't drop below 2."""
        previous_prices = (self.Aprice, self.BPrice, self.CPrice)
        previous_a_price = previous_prices[0]
        previous_c_price = previous_prices[2]
        prices = apply_market_price_change(
            {"Aprice": self.Aprice, "BPrice": self.BPrice, "CPrice": self.CPrice},
            market,
            price_change,
        )
        proposed_prices = (prices["Aprice"], prices["BPrice"], prices["CPrice"])
        self.Aprice, self.BPrice, self.CPrice = self._protect_blue_chip_prices(
            previous_prices,
            proposed_prices,
        )
        self._record_rebate_a_fall(previous_a_price, self.Aprice, "market movement")
        self._record_c_price_fall(previous_c_price, self.CPrice, "market movement")
        return self._record_short_seller_falls(previous_prices, "market movement")

    def _lock_market_cards(self):
        """Помечает все текущие карты на рынке как сыгранные и заблокированные до конца игры."""
        lock_market_cards(self.market_cards, self.market_cards_locked)
        self.accumulation_stephenson_card_played_this_turn = False

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

    def _activate_accumulation_charge(self, card_id, side_slot):
        try:
            is_accumulation = int(card_id) == 124
            slot = int(side_slot)
        except (TypeError, ValueError):
            return False
        if not is_accumulation or slot in self.accumulation_pending_sources:
            return False
        self.accumulation_pending_sources.append(slot)
        print(f"Card 124 Accumulation armed from side slot {slot}.")
        return True

    def _cancel_accumulation_charge(self, card_id, side_slot):
        try:
            is_accumulation = int(card_id) == 124
            slot = int(side_slot)
        except (TypeError, ValueError):
            return False
        if not is_accumulation or slot not in self.accumulation_pending_sources:
            return False
        self.accumulation_pending_sources.remove(slot)
        return True

    def _consume_accumulation_charge(self, card_id, market, slot):
        try:
            normalized_card = int(card_id)
        except (TypeError, ValueError):
            return False
        if normalized_card not in PRICE_CARD_IDS or not self.accumulation_pending_sources:
            return False

        source_slot = self.accumulation_pending_sources.pop(0)
        base_action = int(self.card_actions.get(normalized_card, 0) or 0)
        base_turns = int(self.market_card_turns[market].get(
            slot,
            self.card_turns.get(normalized_card, 0),
        ) or 0)
        self.market_card_actions[market][slot] = base_action * 2
        self.market_card_turns[market][slot] = base_turns * 2
        # The enhanced card is committed as soon as the waiting charge fires.
        self.market_cards_locked[market][slot] = True
        if getattr(self, "boss_limit_red_gain_drop_per_turn", False):
            self.accumulation_stephenson_card_played_this_turn = True
        if 0 <= source_slot < len(self.side_cards_top) and self.side_cards_top[source_slot] == 124:
            self.side_cards_locked_top[source_slot] = True
            self._start_card_jump_animation(self.side_card_jump_animations, source_slot)
        print(
            f"Card 124 Accumulation enhanced card {normalized_card}: "
            f"action={base_action}->{base_action * 2}, turns={base_turns}->{base_turns * 2}"
        )
        return True

    def _apply_red_card_effects_if_needed(self):
        """Apply one-shot effects for freshly played Type=2 red cards."""
        effects = (
            self._apply_forward_trading_effect_if_needed,
            self._apply_extended_gain_drop_effect_if_needed,
            self._apply_price_setting_red_card_effects_in_slot_order,
            self._apply_extra_turn_effect_if_needed,
            self._apply_manipulation_effect_if_needed,
            self._apply_deleverage_effect_if_needed,
        )
        for apply_effect in effects:
            apply_effect()
            if getattr(self, "win_lose_state", None) is not None:
                return

    def _apply_price_setting_red_card_effects_in_slot_order(self):
        """Resolve fresh price-setting red cards from left to right."""
        handlers = {
            113: self._apply_bankruptcy_effects_if_needed,
            114: self._apply_bankruptcy_effects_if_needed,
            115: self._apply_bankruptcy_effects_if_needed,
            117: self._apply_market_crash_effect_if_needed,
            118: self._apply_bid_effect_if_needed,
            119: self._apply_bid_effect_if_needed,
            120: self._apply_bid_effect_if_needed,
            121: self._apply_bid_effect_if_needed,
            122: self._apply_bid_effect_if_needed,
            123: self._apply_parity_effect_if_needed,
            125: self._apply_breakout_effect_if_needed,
        }
        applied = False
        for slot, card_id in enumerate(self.side_cards_top):
            if self.side_cards_locked_top.get(slot):
                continue
            try:
                normalized_card_id = int(card_id)
            except (TypeError, ValueError):
                continue
            handler = handlers.get(normalized_card_id)
            if handler is None:
                continue
            applied = handler(slots=(slot,)) or applied
            if getattr(self, "win_lose_state", None) is not None:
                return applied
        return applied

    def _start_fresh_side_card_jump_animation_for_card(self, target_card_id):
        for slot, card_id in enumerate(self.side_cards_top):
            if (
                card_id == target_card_id
                and not self.side_cards_locked_top.get(slot)
            ):
                self._start_card_jump_animation(self.side_card_jump_animations, slot)

    def _apply_extended_gain_drop_effect_if_needed(self):
        """Card 112: extend all Gain/Drop/Regulation durations, including cards in play."""
        red_rollover_count = self._count_fresh_side_card(112)
        if red_rollover_count <= 0:
            return False

        bonus_per_red_rollover = 2 if self._has_active_silver_card(208) else 1
        bonus = red_rollover_count * bonus_per_red_rollover

        rollover_card_ids = PRICE_CARD_IDS | REGULATION_CARD_IDS
        for card_id in rollover_card_ids:
            if card_id in self.card_turns:
                self.card_turns[card_id] += bonus

        for market in (0, 1, 2):
            for slot, card_id in self.market_cards[market].items():
                if card_id in rollover_card_ids and card_id in self.card_turns:
                    current = self.market_card_turns[market].get(slot, self.card_turns[card_id] - bonus)
                    self.market_card_turns[market][slot] = current + bonus

        self._start_fresh_side_card_jump_animation_for_card(112)
        source = "Card 112 Rollover"
        print(f"{source} extended Gain/Drop/Regulation durations by {bonus}.")
        return True

    def _apply_forward_trading_effect_if_needed(self):
        """Cards 207/402: extend the round when fresh Shareholders are played."""
        if getattr(self, "boss_block_card_turn_extensions", False):
            return False
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

            bonus_per_pair = 4 * gold_forward_count if gold_forward_count > 0 else 1
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
        previous_prices = (self.Aprice, self.BPrice, self.CPrice)
        proposed_prices = list(previous_prices)
        proposed_prices[market] = 2
        protected_prices = self._protect_blue_chip_prices(previous_prices, proposed_prices)
        if market == 0:
            previous_a_price = self.Aprice
            self.Aprice = protected_prices[0]
            changed = previous_a_price != self.Aprice
            self._record_rebate_a_fall(previous_a_price, self.Aprice, "Bankruptcy A")
            self._record_short_seller_falls(previous_prices, "Bankruptcy A")
            return changed
        elif market == 1:
            previous_b_price = self.BPrice
            self.BPrice = protected_prices[1]
            changed = previous_b_price != self.BPrice
            self._record_short_seller_falls(previous_prices, "Bankruptcy B")
            return changed
        elif market == 2:
            previous_c_price = self.CPrice
            self.CPrice = protected_prices[2]
            changed = previous_c_price != self.CPrice
            self._record_c_price_fall(previous_c_price, self.CPrice, "Bankruptcy C")
            self._record_short_seller_falls(previous_prices, "Bankruptcy C")
            return changed
        return False

    def _apply_bankruptcy_effects_if_needed(self, slots=None):
        """Cards 113-115: set A/B/C stock prices to 2."""
        applied = False
        market_by_card = {113: 0, 114: 1, 115: 2}
        target_slots = range(len(self.side_cards_top)) if slots is None else slots
        for slot in target_slots:
            if self.side_cards_locked_top.get(slot):
                continue
            try:
                card_id = int(self.side_cards_top[slot])
            except (IndexError, TypeError, ValueError):
                continue
            market = market_by_card.get(card_id)
            if market is None:
                continue
            changed = self._set_market_price_to_minimum(market)
            if changed:
                self._start_card_jump_animation(self.side_card_jump_animations, slot)
                applied = True
            if getattr(self, "win_lose_state", None) is not None:
                return applied
        if applied:
            print(
                "Bankruptcy cards applied: "
                f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
            )
        return applied

    def _apply_extra_turn_effect_if_needed(self):
        """Card 116: increase turns before round end by 1 per fresh 116."""
        if getattr(self, "boss_block_card_turn_extensions", False):
            return False
        bonus = self._count_fresh_side_card(116)
        if bonus <= 0:
            return False
        self.LastTurn += bonus
        print(f"Card 116 increased LastTurn by {bonus}: LastTurn={self.LastTurn}")
        return True

    def _apply_market_crash_effect_if_needed(self, slots=None):
        """Card 117: set all stock prices to the minimum value of 2."""
        target_slots = range(len(self.side_cards_top)) if slots is None else slots
        crash_slots = []
        for slot in target_slots:
            if self.side_cards_locked_top.get(slot):
                continue
            try:
                is_crash = int(self.side_cards_top[slot]) == 117
            except (IndexError, TypeError, ValueError):
                is_crash = False
            if is_crash:
                crash_slots.append(slot)
        if not crash_slots:
            return False
        applied = False
        for slot in crash_slots:
            previous_prices = (self.Aprice, self.BPrice, self.CPrice)
            previous_a_price = previous_prices[0]
            previous_c_price = previous_prices[2]
            self.Aprice, self.BPrice, self.CPrice = self._protect_blue_chip_prices(
                previous_prices,
                (2, 2, 2),
            )
            changed = (self.Aprice, self.BPrice, self.CPrice) != previous_prices
            self._record_rebate_a_fall(previous_a_price, self.Aprice, "Market Crash")
            self._record_c_price_fall(previous_c_price, self.CPrice, "Market Crash")
            self._record_short_seller_falls(previous_prices, "Market Crash")
            if changed:
                self._start_card_jump_animation(self.side_card_jump_animations, slot)
                applied = True
        print(
            f"Card 117 market crash applied: count={len(crash_slots)}, "
            f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
        )
        return applied

    def _apply_bid_effect_if_needed(self, slots=None):
        """Cards 118-122: set every stock price to the printed BID value."""
        applied_values = []
        target_slots = range(len(self.side_cards_top)) if slots is None else slots
        for slot in target_slots:
            if self.side_cards_locked_top.get(slot):
                continue
            try:
                card_id = self.side_cards_top[slot]
                bid_value = BID_CARD_VALUES.get(int(card_id))
            except (IndexError, TypeError, ValueError):
                bid_value = None
            if bid_value is None:
                continue

            previous_prices = (self.Aprice, self.BPrice, self.CPrice)
            previous_a_price = previous_prices[0]
            previous_c_price = previous_prices[2]
            self.Aprice, self.BPrice, self.CPrice = calculate_price_setting_card_prices(
                previous_prices,
                card_id,
                protected_markets=self._get_blue_chip_markets(),
            )
            self._record_rebate_a_fall(previous_a_price, self.Aprice, f"BID {bid_value}")
            self._record_c_price_fall(previous_c_price, self.CPrice, f"BID {bid_value}")
            if self._record_short_seller_falls(previous_prices, f"BID {bid_value}"):
                return True
            self._start_card_jump_animation(self.side_card_jump_animations, slot)
            applied_values.append(bid_value)

        if not applied_values:
            return False
        print(
            f"BID cards applied in slot order: values={applied_values}, "
            f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
        )
        return True

    def _apply_parity_effect_if_needed(self, slots=None):
        """Card 123: set A/B/C to their arithmetic mean, rounded to a whole price."""
        applied_count = 0
        target_slots = range(len(self.side_cards_top)) if slots is None else slots
        for slot in target_slots:
            if self.side_cards_locked_top.get(slot):
                continue
            try:
                card_id = self.side_cards_top[slot]
                is_parity = int(card_id) == 123
            except (IndexError, TypeError, ValueError):
                is_parity = False
            if not is_parity:
                continue

            previous_prices = (self.Aprice, self.BPrice, self.CPrice)
            previous_a_price = previous_prices[0]
            previous_c_price = previous_prices[2]
            self.Aprice, self.BPrice, self.CPrice = calculate_price_setting_card_prices(
                previous_prices,
                card_id,
                protected_markets=self._get_blue_chip_markets(),
            )
            self._record_rebate_a_fall(previous_a_price, self.Aprice, "Parity")
            self._record_c_price_fall(previous_c_price, self.CPrice, "Parity")
            if self._record_short_seller_falls(previous_prices, "Parity"):
                return True
            self._start_card_jump_animation(self.side_card_jump_animations, slot)
            applied_count += 1

        if applied_count <= 0:
            return False
        print(
            f"Card 123 Parity applied: count={applied_count}, "
            f"A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
        )
        return True

    def _apply_breakout_effect_if_needed(self, slots=None):
        """Card 125: possibly double prices of every market in which the player owns shares."""
        target_slots = range(len(self.side_cards_top)) if slots is None else slots
        breakout_slots = [
            slot
            for slot in target_slots
            if (
                0 <= slot < len(self.side_cards_top)
                and self.side_cards_top[slot] == 125
                and not self.side_cards_locked_top.get(slot)
            )
        ]
        if not breakout_slots:
            return False

        owned_markets = []
        if int(self.Aquantity or 0) > 0:
            owned_markets.append(0)
        if int(self.Bquantity or 0) > 0:
            owned_markets.append(1)
        if int(self.Cquantity or 0) > 0:
            owned_markets.append(2)

        chance = min(100, 50 + self._get_probability_amplifier_bonus())
        applied = False
        for slot in breakout_slots:
            self._start_card_jump_animation(self.side_card_jump_animations, slot)
            if not owned_markets:
                continue
            roll = random.randint(1, 100)
            if roll > chance:
                print(f"Card 125 Breakout missed: roll={roll}, chance={chance}%")
                continue
            if 0 in owned_markets:
                self.Aprice *= 2
            if 1 in owned_markets:
                self.BPrice *= 2
            if 2 in owned_markets:
                self.CPrice *= 2
            applied = True
            print(
                f"Card 125 Breakout applied: roll={roll}, chance={chance}%, "
                f"markets={owned_markets}, A={self.Aprice}, B={self.BPrice}, C={self.CPrice}"
            )
        return applied

    def _apply_manipulation_effect_if_needed(self):
        """Silver card 212: gain four A shares per copy after an owned C fall."""
        manipulation_count = self._count_active_silver_card(212)
        if (
            manipulation_count <= 0
            or getattr(self, "manipulation_applied_this_resolution", False)
            or int(getattr(self, "Cquantity", 0) or 0) <= 0
            or not getattr(
                self,
                "c_price_fell_this_resolution",
                False,
            )
        ):
            return False

        self.Aquantity += 4 * manipulation_count
        self.manipulation_applied_this_resolution = True
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_manipulation = int(card_id) == 212
            except (TypeError, ValueError):
                is_manipulation = False
            if is_manipulation:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        print(
            f"Silver card 212 Manipulation applied: count={manipulation_count}, "
            f"Aquantity={self.Aquantity}, Cquantity={self.Cquantity}"
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
            self.market_card_actions[market].clear()
            self.card_jump_animations[market].clear()

        self.price_card_queue = []
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

    def _apply_full_deployment_reward_if_needed(self):
        if (
            getattr(self, "full_deployment_reward_applied", False)
            or self.deck
            or any(card_id is not None for card_id in getattr(self, "hand_cards", []) or [])
        ):
            return False

        card_count = 0
        for card_id in getattr(self, "active_gold_cards", []) or []:
            try:
                if int(card_id) == GOLD_FULL_DEPLOYMENT_CARD_ID:
                    card_count += 1
            except (TypeError, ValueError):
                continue
        if card_count <= 0:
            return False

        self.full_deployment_reward_applied = True
        reward = GOLD_FULL_DEPLOYMENT_REWARD * card_count
        game_state.add_napoleondors(self.level_number, reward)
        game_state.record_finance_report_income("full_deployment", reward)
        for slot, card_id in enumerate(self._active_lifecycle_cards()):
            try:
                is_full_deployment = int(card_id) == GOLD_FULL_DEPLOYMENT_CARD_ID
            except (TypeError, ValueError):
                is_full_deployment = False
            if is_full_deployment:
                self._start_card_jump_animation(self.lifecycle_card_jump_animations, slot)
        print(
            f"Active card 428 Full Deployment awarded {reward} napoleondors "
            "after every deck card was played."
        )
        return True

    def _draw_next_deck_card(self):
        card_id = self.deck.pop(0)
        return 100 if card_id == 0 else card_id

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
                self._play_card_taking_sound()
                for offset in range(draw_limit):
                    card_id = self._draw_next_deck_card()
                    self.hand_cards[start_idx + offset] = card_id
            self.pending_draws = 0
            return

        # Use the exact same anchored geometry as draw(), so compaction and
        # draw animations never temporarily spread cards onto the frame.
        hand_layout = compute_bottom_hand_layout(
            self.bottom_frame,
            self.hand,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
        )
        slot_positions = hand_layout["slot_positions"]

        # 2) Текущее содержимое и целевой порядок (уплотнение влево)
        existing = [(idx, card) for idx, card in enumerate(self.hand_cards) if card is not None]
        if not existing:
            # В руке вообще нет карт — просто добираем без анимации - всегда добраем, если есть карты в колоде
            if self.Dobor > 0 and len(self.deck) > 0 and self.hand > 0:
                draw_limit = min(self.Dobor, len(self.deck), self.hand)
                self.hand_cards = [None] * self.hand
                self._play_card_taking_sound()
                for i in range(draw_limit):
                    card_id = self._draw_next_deck_card()
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
                self._play_card_taking_sound()
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
                        
                        card_id = self._draw_next_deck_card()
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
                        card_id = self._draw_next_deck_card()
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
                    if draw_count > 0:
                        self._play_card_taking_sound()
                    
                # Подготовка геометрии для анимации (как в draw, с тем же более плотным spacing и центрированием)
                    if self.bottom_frame:
                        bf_w = self.bottom_frame.get_width()
                        bf_h = self.bottom_frame.get_height()
                        bf_x = (SCREEN_WIDTH - bf_w) // 2 - 200
                        bf_y = SCREEN_HEIGHT - bf_h - 150
                        
                        ph_w = 138
                        ph_h = 240
                        available_width = bf_w - 40
                        spacing = ((available_width - ph_w) / (self.hand - 1)) - ph_w if self.hand > 1 else 0
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
                            
                            card_id = self._draw_next_deck_card()
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
                            card_id = self._draw_next_deck_card()
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
    
    def draw_card_action(self, card_id, card_x, card_y, card_size, action_override=None):
        if not hasattr(self, "card_action_font_cache"):
            self.card_action_font_cache = {}
        card_actions = dict(self.card_actions)
        action_value = self._get_card_action(card_id) if action_override is None else action_override
        if action_value is not None:
            card_actions[card_id] = action_value
        draw_card_action_text(
            self.screen,
            card_id,
            card_actions,
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

    def _get_disclosure_card_tooltip_content(self, card_id):
        if not game_state.is_disclosure_active():
            return None
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            return None
        content = DISCLOSURE_CARD_TOOLTIPS.get(normalized)
        if content is None:
            return None

        title, description = content
        if normalized == 302:
            if game_state.is_golden_stocks_triggered():
                detail = "В этом забеге карта уже сработала."
            else:
                current_value = min(
                    100,
                    game_state.get_golden_stocks_chance_percent()
                    + self._count_active_card_safely(302) * self._get_probability_amplifier_bonus(),
                )
                detail = f"Текущая вероятность: {current_value}%."
        elif normalized == 407:
            current_value = self._get_current_rebate_sale_percent()
            if current_value is None:
                current_value = 130 + int(self.rebate_a_fall_bonus_percent or 0)
            detail = f"Текущий процент продажи: {current_value}%."
        elif normalized == GOLD_WATERLOO_CARD_ID:
            current_value = self._get_waterloo_chance()
            detail = f"Текущая вероятность каждой проверки: {current_value}%."
        else:
            current_value = self._get_uptrend_rebate_bonus_percent()
            detail = f"Текущий бонус Uptrend: +{current_value}%."
        return title, f"{description} {detail}"

    def _get_field_card_tooltip_content(self, card_id):
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            return None

        if normalized == 431:
            content = FIELD_CARD_TOOLTIPS.get(normalized)
            if content is None:
                return None
            title, description = content
            return (
                title,
                f"{description} Текущий бонус карты: "
                f"+{game_state.get_risk_premium_card_bonus_percent()}%.",
            )

        disclosure_content = self._get_disclosure_card_tooltip_content(normalized)
        if disclosure_content is not None:
            return disclosure_content
        return FIELD_CARD_TOOLTIPS.get(normalized)

    def _get_hovered_field_card(self, mouse_pos):
        if self.deck_view_active:
            for entry in reversed(self.deck_view_card_entries or []):
                rect = entry.get("rect")
                if rect is not None and rect.collidepoint(mouse_pos):
                    return entry.get("card_id")
            return None

        for entry in reversed(self.bottom_placeholders or []):
            slot = entry.get("slot")
            rect = entry.get("rect")
            if (
                rect is not None
                and rect.collidepoint(mouse_pos)
                and isinstance(slot, int)
                and 0 <= slot < len(self.hand_cards)
                and not (self.dragged_card_source == "hand" and self.dragged_card_index == slot)
            ):
                card_id = self.hand_cards[slot]
                if card_id is not None:
                    return card_id

        for entry in reversed(self.side_placeholders_top or []):
            slot = entry.get("slot")
            rect = entry.get("rect")
            if (
                rect is not None
                and rect.collidepoint(mouse_pos)
                and isinstance(slot, int)
                and 0 <= slot < len(self.side_cards_top)
                and not (self.dragged_card_source == "side_top" and self.dragged_card_side_slot == slot)
            ):
                card_id = self.side_cards_top[slot]
                if card_id is not None:
                    return card_id

        active_cards = self._active_lifecycle_cards()
        for entry in reversed(self.side_placeholders_bottom or []):
            slot = entry.get("slot")
            rect = entry.get("rect")
            if (
                rect is not None
                and rect.collidepoint(mouse_pos)
                and isinstance(slot, int)
                and 0 <= slot < len(active_cards)
            ):
                return active_cards[slot]

        for entry in reversed(self.market_placeholders or []):
            market = entry.get("market")
            slot = entry.get("slot")
            rect = entry.get("rect")
            if rect is None or not rect.collidepoint(mouse_pos):
                continue
            if not isinstance(market, int) or market not in self.market_cards or not isinstance(slot, int):
                continue
            if (
                self.dragged_card_source == "market"
                and self.dragged_card_market == market
                and self.dragged_card_market_slot == slot
            ):
                continue
            card_id = self.market_cards[market].get(slot)
            if card_id is not None:
                return card_id
        return None

    def _draw_card_tooltip(self, card_id, mouse_pos):
        content = self._get_field_card_tooltip_content(card_id)
        if content is None:
            return
        title, description = content

        width = 460
        padding = 16
        text_width = width - padding * 2
        lines = wrap_text(
            description,
            self.disclosure_tooltip_text_font,
            text_width,
            color=PAPER_COLOR,
        )
        title_height = self.disclosure_tooltip_title_font.get_height()
        line_height = self.disclosure_tooltip_text_font.get_height() + 4
        height = padding * 2 + title_height + 10 + line_height * len(lines)

        x = mouse_pos[0] + 20
        if x + width > SCREEN_WIDTH - 8:
            x = mouse_pos[0] - width - 20
        y = mouse_pos[1] + 20
        if y + height > SCREEN_HEIGHT - 8:
            y = mouse_pos[1] - height - 20
        x = max(8, min(x, SCREEN_WIDTH - width - 8))
        y = max(8, min(y, SCREEN_HEIGHT - height - 8))

        tooltip = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(tooltip, (244, 235, 211, 248), tooltip.get_rect(), border_radius=8)
        pygame.draw.rect(tooltip, PAPER_COLOR, tooltip.get_rect(), 3, border_radius=8)
        title_surface = self.disclosure_tooltip_title_font.render(title, True, PAPER_COLOR)
        tooltip.blit(title_surface, (padding, padding))
        text_y = padding + title_height + 10
        for line in lines:
            line_surface = self.disclosure_tooltip_text_font.render(line, True, PAPER_COLOR)
            tooltip.blit(line_surface, (padding, text_y))
            text_y += line_height
        self.screen.blit(tooltip, (x, y))

    def _draw_field_card_tooltip(self):
        if (
            self.dragged_card_source is not None
            or self.pause_menu_active
            or self.win_lose_state is not None
        ):
            return

        mouse_pos = pygame.mouse.get_pos()
        hovered_card = self._get_hovered_field_card(mouse_pos)
        self._draw_card_tooltip(hovered_card, mouse_pos)

    def _draw_waterloo_forecast(self):
        if getattr(self, "waterloo_preview_movements", None) is None:
            return

        current_prices = (int(self.Aprice or 0), int(self.BPrice or 0), int(self.CPrice or 0))
        forecast_prices = self._calculate_waterloo_preview_prices()
        base_results = {}
        for movement in self.waterloo_preview_movements:
            market = movement.get("market")
            if movement.get("source") is None and market in (0, 1, 2) and market not in base_results:
                base_results[market] = movement.get("type")
        panel = pygame.Rect((SCREEN_WIDTH - 690) // 2, 18, 690, 96)
        surface = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, (244, 235, 211, 248), surface.get_rect(), border_radius=7)
        pygame.draw.rect(surface, PAPER_COLOR, surface.get_rect(), 3, border_radius=7)

        title = self.disclosure_tooltip_title_font.render(
            "Waterloo: прогноз рыночного броска",
            True,
            PAPER_COLOR,
        )
        surface.blit(title, title.get_rect(centerx=panel.width // 2, top=9))

        labels = ("A", "B", "C")
        column_width = panel.width // 3
        for market, (current_price, forecast_price) in enumerate(zip(current_prices, forecast_prices)):
            base_result = base_results.get(market)
            if base_result == "rise" or (base_result is None and forecast_price > current_price):
                result_text = "Рост"
                color = (52, 112, 68)
            elif base_result == "fall" or (base_result is None and forecast_price < current_price):
                result_text = "Падение"
                color = (148, 58, 48)
            else:
                result_text = "Flat"
                color = PAPER_COLOR
            text = self.disclosure_tooltip_text_font.render(
                f"{labels[market]}   {result_text} до {forecast_price}",
                True,
                color,
            )
            center_x = column_width * market + column_width // 2
            surface.blit(text, text.get_rect(center=(center_x, 64)))
            if market < 2:
                separator_x = column_width * (market + 1)
                pygame.draw.line(surface, (151, 137, 119), (separator_x, 48), (separator_x, 80), 1)
        self.screen.blit(surface, panel.topleft)

    def _draw_market_probability_debug(self, market, x, y):
        if not game_state.is_disclosure_active():
            return
        probs = build_market_probabilities(
            self.market_cards,
            probability_card_bonus=self._get_probability_card_bonus(),
            force_flat=self._is_flat_random_active(),
            force_flat_markets=self._get_regulation_flat_markets(),
            prevent_fall_markets=self._get_blue_chip_markets(),
            double_fall_markets=self._get_shakeout_markets(),
            double_fall_bonus=self._get_probability_amplifier_bonus(),
            double_fall_count=self._get_shakeout_count(),
        ).get(market)
        if not probs:
            return

        def fmt(value):
            return f"{int(value)}" if float(value).is_integer() else f"{value:.1f}"

        lines = (
            f"Падение {fmt(probs['fall'])}%",
            f"Флэт {fmt(probs['flat'])}%",
            f"Рост {fmt(probs['rise'])}%",
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

    def _draw_level6_bot_trade_action(self, frame_rect, market):
        if (
            not self._is_level6_alternating_battle()
            or self.level6_turn_owner != "bot"
        ):
            return

        phase = self.level6_bot_turn_phase
        if phase == "thinking":
            if market != 1:
                return
            text = self._get_text("Level6BotThinking", "Бот3 думает...")
            surface = self.font_small.render(text, True, PAPER_COLOR)
            self.screen.blit(surface, surface.get_rect(center=frame_rect.center))
            return

        decision = self.level6_bot_turn_decision or {}
        labels = ("A", "B", "C")
        label = labels[market]
        if phase in ("selling", "buying"):
            key = "sold" if phase == "selling" else "bought"
            try:
                count = int((decision.get(key) or {}).get(label, 0) or 0)
            except (TypeError, ValueError):
                count = 0
            if count <= 0:
                return

            action_text = self._get_text(
                "Level6BotSelling" if phase == "selling" else "Level6BotBuying",
                "Продаёт" if phase == "selling" else "Покупает",
            )
            action_surface = self.pause_small_font.render(action_text, True, PAPER_COLOR)
            action_rect = action_surface.get_rect(
                centerx=frame_rect.centerx,
                bottom=frame_rect.centery - 28,
            )
            self.screen.blit(action_surface, action_rect)

            arrow = self.arrow_down if phase == "selling" else self.arrow_up
            arrow_size = 92
            if arrow:
                arrow_image = pygame.transform.smoothscale(arrow, (arrow_size, arrow_size))
                arrow_rect = arrow_image.get_rect(
                    center=(frame_rect.centerx - 34, frame_rect.centery + 32)
                )
                self.screen.blit(arrow_image, arrow_rect)
                count_x = arrow_rect.right + 8
            else:
                count_x = frame_rect.centerx - 12
            count_surface = self.font_large.render(str(count), True, PAPER_COLOR)
            count_rect = count_surface.get_rect(
                left=count_x,
                centery=frame_rect.centery + 32,
            )
            self.screen.blit(count_surface, count_rect)
            return

        if phase != "holding":
            return

        quantities = getattr(getattr(self, "stock_bot", None), "quantities", {}) or {}
        quantity_keys = ("Aquantity", "Bquantity", "Cquantity")
        try:
            count = int(quantities.get(quantity_keys[market], 0) or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            if market != 1 or any(int(value or 0) > 0 for value in quantities.values()):
                return
            text = self._get_text("Level6BotNoTrades", "Без сделок")
        else:
            hold_text = self._get_text("Level6BotHolding", "Держит")
            text = f"{hold_text}: {count}"
        surface = self.font_small.render(text, True, PAPER_COLOR)
        self.screen.blit(surface, surface.get_rect(center=frame_rect.center))
    
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
                bottom_slots=game_state.get_lifecycle_card_slot_limit(),
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
            capital_race = self._is_capital_race_level()
            if capital_race:
                goal_label_text = self._get_text("CapitalRaceLabel", "Victory:")
                goal_value_text = self._get_text("CapitalRaceCondition", "capital above Bot3")
            else:
                goal_label_text = "Goal:"
                goal_value_text = str(self.Goal)
            goal_label = self.font_medium.render(goal_label_text, True, PAPER_COLOR)
            goal_value_font = self.font_small if capital_race else self.font_medium
            goal_value = goal_value_font.render(goal_value_text, True, PAPER_COLOR)
            goal_label_x = label_start_x
            goal_label_y = margin_top
            if capital_race:
                goal_value_x = label_start_x
                goal_value_y = goal_label_y + goal_label.get_height() + 2
            else:
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
            goal_block_bottom = max(
                goal_label_y + goal_label.get_height(),
                goal_value_y + goal_value.get_height(),
            )
            money_label_y = goal_block_bottom + label_spacing
            money_value_x = money_label_x + money_label.get_width() + value_spacing
            money_value_y = money_label_y
            # Ensure value doesn't go off screen
            if money_value_x + money_value.get_width() > SCREEN_WIDTH - min_right_margin:
                money_value_x = SCREEN_WIDTH - min_right_margin - money_value.get_width()

            bot_status_text = self._stock_bot_status_text()
            bot_status_font = self.pause_small_font if capital_race else self.font_small
            bot_status = bot_status_font.render(bot_status_text, True, PAPER_COLOR) if bot_status_text else None
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
                bottom_slots=game_state.get_lifecycle_card_slot_limit(),
            )
            right_top_y = right_panel_layout["top_y"]
            right_top_h = right_panel_layout["top_height"]

            # Draw card panels only in modes where cards are part of the battle.
            if not self._is_level6_alternating_battle():
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
                            img_to_draw = self._get_trade_arrow_image(i, idx, img_to_draw)
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
                            img_to_draw = self._get_trade_arrow_image(i, idx, img_to_draw)
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
                            img_to_draw = self._get_trade_arrow_image(i, idx, img_to_draw)
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
                            img_to_draw = self._get_trade_arrow_image(i, idx, img_to_draw)
                            self.screen.blit(img_to_draw, rect.topleft)
                        else:
                            img_to_draw = self._get_trade_arrow_image(i, idx, img_to_draw)
                            self.screen.blit(img_to_draw, (arrow_x, ay))
                
                # Draw three placeholders at the bottom of each market frame (A, B, C)
                if self.placeholder_market and not self._is_level6_alternating_battle():
                    market_placeholders = build_market_placeholders(
                        frame_info["rect"],
                        i,
                        num_placeholders=self.boss_market_slots_per_market,
                    )
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
                                self.draw_card_action(
                                    card_id,
                                    card_x,
                                    card_y,
                                    self.card_size_market,
                                    action_override=self.market_card_actions[i].get(ph_idx),
                                )
                                # Draw CardTurns if this card has one - use remaining turns from market_card_turns
                                remaining_turns = self.market_card_turns[i].get(ph_idx)
                                self.draw_card_turns(card_id, card_x, card_y, self.card_size_market, turns_remaining=remaining_turns)
                        # Highlight available market placeholder for dropping a card
                        highlight = False
                        # When dragging from hand: only FIRST free slot in each market is valid
                        if (
                            self.dragged_card_source == "hand"
                            and dragged_hand_card_type != 2
                            and self._can_play_dragged_hand_card_on_market(dragged_hand_card_id)
                        ):
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
                active_animation_markets = (
                    self.current_price_animation.get("market")
                    if self.current_price_animation
                    else None
                )
                if not isinstance(active_animation_markets, (list, tuple, set)):
                    active_animation_markets = (active_animation_markets,)
                if self.current_price_animation and i in active_animation_markets:
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

                self._draw_level6_bot_trade_action(frame_info["rect"], i)

            self._draw_market_clear_animations()

            # ------------------------------------------------------------
            # Draw placeholders inside the right-side framed areas
            # ------------------------------------------------------------
            self.side_placeholders_top = []
            self.side_placeholders_bottom = []
            ph_img = self.placeholder_side or self.placeholder_market
            if ph_img and not self._is_level6_alternating_battle():
                self.side_placeholders_top, self.side_placeholders_bottom = build_side_panel_placeholders(
                    right_panel_layout,
                    ph_img,
                )

                # If dragging a Type=2 card from hand, highlight ONLY the first free slot
                # on the TOP right-side panel (6 slots). Bottom (3 slots) must NOT be used.
                first_free_side_top = None
                if (
                    self.dragged_card_source == "hand"
                    and dragged_hand_card_type == 2
                    and self._can_play_dragged_hand_card_on_side_top(dragged_hand_card_id)
                ):
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

                # Placeholders are a background layer. Draw all of them before
                # any lifecycle card so overlapping slots can never cover a
                # previously drawn card.
                for ph_info in self.side_placeholders_bottom:
                    self.screen.blit(ph_img, ph_info["rect"].topleft)

                active_bottom_cards = self._active_lifecycle_cards()
                for ph_info in self.side_placeholders_bottom:
                    slot = ph_info["slot"]
                    rect = ph_info["rect"]
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
                            shake_x, shake_y = self._get_lifecycle_card_shake_offset(slot)
                            card_x += shake_x
                            card_y += shake_y
                            scale = self._get_lifecycle_card_scale(slot)
                            drawn_size = self.card_size_side
                            drawn_img = img
                            if scale > 1.0:
                                drawn_size = (
                                    max(1, int(self.card_size_side[0] * scale)),
                                    max(1, int(self.card_size_side[1] * scale)),
                                )
                                drawn_img = pygame.transform.smoothscale(img, drawn_size)
                                card_x = rect.centerx - drawn_size[0] // 2
                                card_y = rect.centery - drawn_size[1] // 2
                            self.screen.blit(drawn_img, (card_x, card_y))
                            draw_bear_modifier_text(
                                self.screen,
                                card_id,
                                card_x,
                                card_y,
                                drawn_size,
                                self.font_path,
                                PAPER_COLOR,
                                modifier_percent=self._get_current_bear_goal_discount_percent(),
                            )
                            if self._is_lifecycle_card_power_lost(card_id, slot=slot):
                                self._draw_negative_card_overlay(
                                    card_x,
                                    card_y,
                                    drawn_size,
                                )

        # Draw bottom frame (strategy cards area)
        if self.bottom_frame and not self._is_level6_alternating_battle():
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
                    slot_x, slot_y = ph_info["rect"].topleft
                    if self.placeholder_bottom:
                        self.screen.blit(self.placeholder_bottom, (slot_x, slot_y))
                    else:
                        pygame.draw.rect(self.screen, WHITE, (slot_x, slot_y, ph_w, ph_h))
                        pygame.draw.rect(self.screen, BLACK, (slot_x, slot_y, ph_w, ph_h), 2)

                for ph_info in self.bottom_placeholders:
                    i = ph_info["slot"]
                    slot_x, slot_y = ph_info["rect"].topleft
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
                            if self._should_show_hand_card_negative(card_id):
                                self._draw_negative_card_overlay(
                                    card_x,
                                    card_y,
                                    self.card_size_bottom,
                                )
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
        if (
            self.dragged_card_source == "hand"
            and self.dragged_card_index is not None
            and 0 <= self.dragged_card_index < len(self.hand_cards)
        ):
            dragged_card_id = self.hand_cards[self.dragged_card_index]
            if dragged_card_id is not None and self._should_show_hand_card_negative(dragged_card_id):
                card_x = self.dragged_card_pos[0] - self.drag_offset[0]
                card_y = self.dragged_card_pos[1] - self.drag_offset[1]
                self._draw_negative_card_overlay(
                    card_x,
                    card_y,
                    self.card_size_bottom,
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

            if self._is_level6_alternating_battle():
                turn_labels = {
                    "player": self._get_text("Level6PlayerTurn", "Ход игрока"),
                    "bot": self._get_text("Level6BotTurn", "Ход Бота3"),
                    "market": self._get_text("Level6MarketTurn", "Изменение рынка"),
                }
                turn_label = turn_labels.get(self.level6_turn_owner, turn_labels["player"])
                bot_phase_labels = {
                    "thinking": self._get_text("Level6BotThinking", "Бот3 думает..."),
                    "selling": self._get_text("Level6BotSelling", "Продаёт"),
                    "buying": self._get_text("Level6BotBuying", "Покупает"),
                    "holding": self._get_text("Level6BotHolding", "Держит"),
                    "ending": self._get_text("Level6BotEnding", "Бот3 завершает ход"),
                }
                if self.level6_turn_owner == "bot":
                    turn_label = bot_phase_labels.get(self.level6_bot_turn_phase, turn_label)
                turn_surface = self.font_small.render(turn_label, True, PAPER_COLOR)
                turn_rect = turn_surface.get_rect(
                    centerx=self.end_button_rect.centerx,
                    bottom=self.end_button_rect.y - 8,
                )
                self.screen.blit(turn_surface, turn_rect)

            if int(getattr(self, "boss_turn_time_limit_seconds", 0) or 0) > 0:
                timer_text = self.font_medium.render(
                    str(self._get_boss_turn_timer_seconds()),
                    True,
                    PAPER_COLOR,
                )
                timer_rect = timer_text.get_rect(
                    centerx=self.end_button_rect.centerx,
                    bottom=self.end_button_rect.y - 8,
                )
                self.screen.blit(timer_text, timer_rect)

        self._draw_deck_toggle()
        self._draw_current_boss_marker()
        self._draw_waterloo_forecast()
        
        # Victory reports are shown one after another: finances, then earned cards.
        if (
            self.win_lose_state == "win"
            and getattr(self, "result_report_stage", "cards") in ("finance", "card_report")
        ):
            self._draw_finance_report()

        # Defeat still uses the old result window; victory no longer does.
        if self.win_lose_state == "lose" and self.win_lose_image:
            win_lose_y_draw = int(round(self.win_lose_y))
            # Draw WinLose window at centered position
            self.screen.blit(self.win_lose_image, (self.win_lose_x, win_lose_y_draw))
            
            # Draw appropriate Ok button based on win/lose state
            ok_button = None
            if self.ok2_button:
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
            
            # Draw lose text
            text_y = win_lose_y_draw + 85  # Top padding (50 + 35)
            text_surface = self.font_small.render(self.lose_window_text, True, PAPER_COLOR)
            text_x = self.win_lose_x + (winlose_width - text_surface.get_width()) // 2  # Center horizontally
            self.screen.blit(text_surface, (text_x, text_y))
            
        if self.deck_view_active:
            self._draw_deck_view()

        if self.pause_menu_active:
            self._draw_pause_menu()

        self._draw_field_card_tooltip()
        
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

            if result == "main_menu":
                return "main_menu"

            if result == "restart_level":
                return "restart_level"

            self._update_boss_turn_timer()

            if self.deck_view_active or self.pause_menu_active:
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
            self.update_level6_bot_turn()

            # Update card jump animations
            self.update_card_jump_animations()
            self.update_side_card_jump_animations()
            self.update_lifecycle_card_scale_animations()
            self.update_lifecycle_card_shake_animations()
            self.update_market_clear_animations()
            self.update_final_auto_liquidation_animation()
            
            # Update sequential processing of persistent price-effect cards.
            self.update_price_card_processing()
            self._maybe_finalize_after_effect_animations()

            # Update hand compaction animation after end turn
            self.update_hand_compact_animation()
            
            # Update hand draw animation (cards flying in from bottom)
            self.update_hand_draw_animation()
            
            # Update win/lose screen animation
            self.update_win_lose_animation()

            if self.pause_menu_requested and self._can_open_pause_menu():
                self._open_pause_menu()

            self.draw()
            self.clock.tick(FPS)
