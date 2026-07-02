import pygame
import sys
import game_state
import profile_manager
from asset_loaders import find_font_path_or_exit, load_main_background
from boss_logic import (
    LEVEL_BOSS_ROUNDS,
    apper_goal_boost,
    get_boss_number_from_filename,
    get_boss_number_from_index,
    get_bosses_required,
    validate_levels_and_rounds_config,
    _ensure_level3_roster,
)
from game_data import (
    REWARD_TOKEN_RANDOM_RED,
    load_boss_rewards,
    load_language,
    load_levels_config,
    load_rewards_config,
    load_rounds_config,
    get_level2_goal,
    get_level3_goal,
)
from game_stats import (
    set_stats_file,
    update_level_boss_position_stats,
    update_level_run_loss_stage_stats,
    update_level_run_result,
    update_level_run_started,
)
from boss_page import BossPage
from game_screen import GameScreen
from gameplay_page import GameplayPage
from profile_page import ProfilePage
from round_page import RoundPage
from silver_black_page import SilverBlackPage
from shop_page import ShopPage
from start_page import StartPage

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

# Language system
Lang = {}  # Dictionary to store language strings
CURRENT_LANGUAGE = "RU"  # Default language (RUS in user's terms, but file uses RU)


def main():
    global Lang

    # Initialize screen
    display_flags = pygame.HWSURFACE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), display_flags)
    pygame.display.set_caption("Bressoles")
    
    # Load shared resources
    background = load_main_background((SCREEN_WIDTH, SCREEN_HEIGHT))
    font_path = find_font_path_or_exit()
    
    # Load language (default: RU/RUS)
    Lang = load_language(CURRENT_LANGUAGE)
    
    # Validate levels and rounds config (RoundsData.csv vs LEVEL_BOSS_ROUNDS)
    validate_levels_and_rounds_config()

    selected_slot = profile_manager.get_selected_slot()
    selected_profile = profile_manager.load_profile(selected_slot) if selected_slot else None
    if selected_profile:
        profile_manager.apply_profile_to_game_state(selected_profile)
        set_stats_file(profile_manager.get_stats_file(selected_slot))

    def choose_profile():
        nonlocal selected_slot, selected_profile
        profile_page = ProfilePage(screen, background, font_path, Lang)
        profile_result = profile_page.run()
        if isinstance(profile_result, dict):
            selected_slot = int(profile_result["slot"])
            selected_profile = profile_manager.load_profile(selected_slot)
            profile_manager.apply_profile_to_game_state(selected_profile)
            set_stats_file(profile_manager.get_stats_file(selected_slot))
            return True
        return False

    def save_progress_if_needed(test_mode=False):
        if selected_slot and not test_mode:
            profile_manager.save_progress_from_game_state(selected_slot)

    def open_shop(level_number, test_mode=False):
        discount_percent = game_state.consume_pending_shop_discount()
        save_progress_if_needed(test_mode)
        shop_page = ShopPage(
            screen,
            font_path,
            level_number,
            game_state.napoleondors,
            Lang,
            discount_percent=discount_percent,
        )
        shop_page.run()
        save_progress_if_needed(test_mode)

    def award_napoleondors_and_open_shop(level_number, amount, test_mode=False, show_shop=True):
        reward_amount = game_state.get_victory_napoleondor_reward(amount)
        game_state.add_napoleondors(level_number, reward_amount)
        if show_shop:
            save_progress_if_needed(test_mode)
            open_shop(level_number, test_mode)
        else:
            game_state.clear_pending_shop_discount()

    def should_open_shop_after_regular_round(level_number):
        return int(level_number or 0) != 1

    def run_saved_gameplay(active_game):
        context = dict((active_game or {}).get("context") or {})
        saved_state = dict((active_game or {}).get("state") or {})
        if not context:
            return None
        gameplay_page = GameplayPage(
            screen,
            font_path,
            context.get("difficulty", "e"),
            goal=context.get("goal"),
            level_number=context.get("level_number", 1),
            is_boss_fight=bool(context.get("is_boss_fight", False)),
            boss_index=context.get("boss_index"),
            round_num=context.get("round_num"),
            defeated_count=context.get("defeated_count", 0),
            lang_dict=Lang,
            test_mode=bool(context.get("test_mode", False)),
            profile_slot=selected_slot,
            saved_state=saved_state,
            boss_filename=context.get("boss_filename"),
            active_silver_cards=context.get("active_silver_cards") or [],
            active_black_cards=context.get("active_black_cards") or [],
            active_gold_cards=context.get("active_gold_cards") or [],
            rounds_required=context.get("rounds_required"),
        )
        return gameplay_page.run()

    def new_boss_progress_state():
        return game_state.new_boss_progress_state()

    def rect_to_list(rect):
        if rect is None:
            return None
        return [int(rect.x), int(rect.y), int(rect.width), int(rect.height)]

    def list_to_rect(value):
        if not value or len(value) != 4:
            return None
        try:
            return pygame.Rect(int(value[0]), int(value[1]), int(value[2]), int(value[3]))
        except (TypeError, ValueError):
            return None

    def set_current_boss(bp_state, defeated_count, boss_index, boss_filename, boss_page=None):
        try:
            boss_index_value = int(boss_index)
        except (TypeError, ValueError):
            boss_index_value = 0
        bp_state["current_boss"] = {
            "defeated_count": int(defeated_count or 0),
            "boss_index": boss_index_value,
            "boss_filename": boss_filename,
            "clicked_boss_filename": getattr(boss_page, "clicked_boss_filename", None) if boss_page else boss_filename,
            "clicked_boss_rect": rect_to_list(getattr(boss_page, "clicked_boss_rect", None)) if boss_page else None,
            "saved_lines": [list(line) for line in (getattr(boss_page, "saved_lines", []) if boss_page else [])],
        }

    def start_red_deck_for_boss(level_number):
        game_state.start_red_cards_deck_for_level(level_number)
        print(f"Built red cards deck for level {level_number}: {game_state.active_red_cards_deck}")

    def clear_current_boss(bp_state):
        bp_state["current_boss"] = None

    def reset_level_attempt(level_number):
        game_state.clear_investment_card_bonuses()
        game_state.clear_profit_bonus()
        game_state.clear_round_reward_cards(level_number)
        game_state.clear_shop_deck_cards()
        game_state.clear_gold_cards()
        game_state.clear_silver_cards_deck()
        game_state.clear_bailout_bonus()
        game_state.clear_long_investments()
        return game_state.reset_level_attempt(level_number)

    def get_current_boss(bp_state):
        current_boss = bp_state.get("current_boss")
        if not isinstance(current_boss, dict):
            return None
        if int(current_boss.get("defeated_count", -1)) != int(bp_state.get("defeated", 0)):
            clear_current_boss(bp_state)
            return None
        progress_key = get_round_progress_key(
            current_boss.get("defeated_count", 0),
            current_boss.get("boss_index"),
            current_boss.get("boss_filename"),
        )
        if progress_key not in (bp_state.get("round_progress") or {}):
            clear_current_boss(bp_state)
            return None
        return current_boss

    def infer_current_boss_from_round_progress(bp_state):
        defeated_count = int(bp_state.get("defeated", 0) or 0)
        for key in (bp_state.get("round_progress") or {}).keys():
            parts = str(key).split(":", 2)
            if len(parts) != 3:
                continue
            try:
                key_defeated = int(parts[0])
                boss_index = int(parts[1])
            except (TypeError, ValueError):
                continue
            if key_defeated == defeated_count:
                return {
                    "defeated_count": defeated_count,
                    "boss_index": boss_index,
                    "boss_filename": parts[2] or None,
                }
        return None

    def infer_legacy_current_boss(level_number, bp_state):
        if int(level_number or 0) != 1:
            return None
        if int(bp_state.get("defeated", 0) or 0) != 0:
            return None
        if not game_state.earned_reward_cards.get(1):
            return None
        return {
            "defeated_count": 0,
            "boss_index": 0,
            "boss_filename": "1_Watt.png",
        }

    def get_round_progress_key(defeated_count, boss_index, boss_filename):
        return f"{int(defeated_count or 0)}:{boss_index if boss_index is not None else ''}:{boss_filename or ''}"

    def get_saved_round_progress(bp_state, defeated_count, boss_index, boss_filename):
        progress_key = get_round_progress_key(defeated_count, boss_index, boss_filename)
        return (bp_state.get("round_progress") or {}).get(progress_key, {})

    def infer_legacy_round_progress(level_number, defeated_count, boss_index, boss_filename):
        if int(level_number or 0) != 1:
            return {}
        if int(defeated_count or 0) != 0 or int(boss_index or 0) != 0:
            return {}
        if boss_filename and boss_filename != "1_Watt.png":
            return {}
        if not game_state.earned_reward_cards.get(1):
            return {}
        return {
            "completed_rounds": [1],
            "round_selections": {1: {"key": "e"}},
            "saved_lines": [],
        }

    def save_round_page_progress(bp_state, round_page, defeated_count, boss_index, boss_filename):
        progress_key = get_round_progress_key(defeated_count, boss_index, boss_filename)
        bp_state.setdefault("round_progress", {})[progress_key] = round_page.export_round_progress()

    def clear_round_page_progress(bp_state, defeated_count, boss_index, boss_filename):
        progress_key = get_round_progress_key(defeated_count, boss_index, boss_filename)
        bp_state.setdefault("round_progress", {}).pop(progress_key, None)

    def mark_context_round_completed(bp_state, context):
        round_num = context.get("round_num")
        if round_num is None:
            return
        try:
            round_num = int(round_num)
        except (TypeError, ValueError):
            return
        difficulty = (context.get("difficulty") or "e").lower()
        if difficulty not in ("e", "m", "h"):
            difficulty = "e"
        boss_index = context.get("boss_index")
        boss_filename = context.get("boss_filename")
        defeated_count = context.get("defeated_count", bp_state.get("defeated", 0))
        progress_key = get_round_progress_key(defeated_count, boss_index, boss_filename)
        progress = bp_state.setdefault("round_progress", {}).setdefault(
            progress_key,
            {"completed_rounds": [], "round_selections": {}, "saved_lines": []},
        )
        completed = set(int(value) for value in progress.get("completed_rounds", []) if str(value).isdigit())
        completed.add(round_num)
        progress["completed_rounds"] = sorted(completed)
        progress.setdefault("round_selections", {})[round_num] = {"key": difficulty}
        set_current_boss(bp_state, defeated_count, boss_index, boss_filename)

    def choose_active_lifecycle_cards(is_boss_fight=False):
        if not game_state.has_selectable_lifecycle_cards():
            return "ok", {}
        silver_page = SilverBlackPage(
            screen,
            font_path,
            game_state.silver_cards,
            game_state.black_cards,
            game_state.gold_cards,
            active_gold_cards=game_state.active_gold_cards,
            is_boss_fight=is_boss_fight,
        )
        silver_result = silver_page.run()
        if silver_result == "back":
            return "back", {}
        if isinstance(silver_result, dict):
            active_gold_cards = game_state.set_active_gold_cards(silver_result.get("active_gold_cards") or [])
            return "ok", {
                "active_silver_cards": list(silver_result.get("active_silver_cards") or []),
                "active_black_cards": list(silver_result.get("active_black_cards") or []),
                "active_gold_cards": active_gold_cards,
            }
        return "ok", {}

    def mark_level_run_started(bp_state, level_number):
        if test_mode or not selected_slot or not isinstance(bp_state, dict):
            return
        if bp_state.get("run_stats_started"):
            return
        update_level_run_started(level_number)
        bp_state["run_stats_started"] = True
        bp_state["run_stats_finished"] = False

    def mark_level_run_result(bp_state, level_number, won):
        if test_mode or not selected_slot or not isinstance(bp_state, dict):
            return
        if not bp_state.get("run_stats_started"):
            update_level_run_started(level_number)
            bp_state["run_stats_started"] = True
        if bp_state.get("run_stats_finished"):
            return
        update_level_run_result(level_number, won)
        bp_state["run_stats_finished"] = True

    def mark_level_boss_position_result(level_number, defeated_count, won):
        if test_mode or not selected_slot:
            return
        try:
            boss_position = int(defeated_count or 0) + 1
        except (TypeError, ValueError):
            boss_position = 1
        update_level_boss_position_stats(level_number, boss_position, won)

    def mark_level_run_loss_stage(level_number, stage_label, stage_number=None):
        if test_mode or not selected_slot:
            return
        update_level_run_loss_stage_stats(level_number, stage_label, stage_number)
    
    # Main game loop
    while True:
        # Start page
        profile_name = selected_profile.get("name") if selected_profile else None
        start_page = StartPage(screen, background, font_path, Lang, profile_name=profile_name)
        result = start_page.run()
        
        # Track test mode flag
        test_mode = False
        
        if result == "profile":
            choose_profile()
            continue

        if result in ("start", "test_mode"):
            if not selected_slot and result == "start":
                choose_profile()
                continue

            if selected_slot:
                selected_profile = profile_manager.load_profile(selected_slot)
                profile_manager.apply_profile_to_game_state(selected_profile)
                set_stats_file(profile_manager.get_stats_file(selected_slot))

            if result == "start" and selected_slot:
                active_game = profile_manager.get_active_game(selected_slot)
                if active_game:
                    active_context = dict(active_game.get("context") or {})
                    resume_result = run_saved_gameplay(active_game)
                    if resume_result == "quit":
                        result = "quit"
                        break
                    if resume_result in ("round_select", "level_select"):
                        if resume_result == "round_select" and active_context.get("is_boss_fight"):
                            level = int(active_context.get("level_number", 1) or 1)
                            rounds_config = load_rounds_config()
                            bosses_required = get_bosses_required(level, rounds_config)
                            bp_state = game_state.boss_progress.setdefault(level, new_boss_progress_state())
                            bp_state.setdefault("round_progress", {})
                            mark_level_boss_position_result(level, active_context.get("defeated_count", 0), True)
                            if bp_state["defeated"] < bosses_required:
                                bp_state["defeated"] += 1
                            clear_round_page_progress(
                                bp_state,
                                active_context.get("defeated_count", 0),
                                active_context.get("boss_index"),
                                active_context.get("boss_filename"),
                            )
                            clear_current_boss(bp_state)
                            if bp_state["defeated"] >= bosses_required:
                                award_napoleondors_and_open_shop(level, 3, show_shop=False)
                                mark_level_run_result(bp_state, level, True)
                                game_state.complete_level_run(level)
                                if level == 1:
                                    game_state.level_1_boss_defeated = True
                                elif level == 2:
                                    game_state.level_2_boss_defeated = True
                                elif level == 3:
                                    game_state.level_3_boss_defeated = True
                            else:
                                award_napoleondors_and_open_shop(level, 3)
                        elif resume_result == "round_select":
                            level = int(active_context.get("level_number", 1) or 1)
                            bp_state = game_state.boss_progress.setdefault(level, new_boss_progress_state())
                            mark_context_round_completed(bp_state, active_context)
                            award_napoleondors_and_open_shop(
                                level,
                                1,
                                show_shop=should_open_shop_after_regular_round(level),
                            )
                        elif resume_result == "level_select":
                            level = int(active_context.get("level_number", 1) or 1)
                            bp_state = game_state.boss_progress.setdefault(level, new_boss_progress_state())
                            if active_context.get("is_boss_fight"):
                                mark_level_boss_position_result(level, active_context.get("defeated_count", 0), False)
                                mark_level_run_loss_stage(
                                    level,
                                    f"Босс уровня {int(active_context.get('defeated_count', 0) or 0) + 1}",
                                    int(active_context.get("defeated_count", 0) or 0) + 1,
                                )
                            else:
                                round_num = active_context.get("round_num")
                                mark_level_run_loss_stage(level, f"Раунд {round_num}", round_num)
                            mark_level_run_result(bp_state, level, False)
                            reset_level_attempt(level)
                        profile_manager.save_progress_from_game_state(selected_slot)
                    continue

            rounds_config = load_rounds_config()
            test_mode = (result == "test_mode")

            # Level selection loop
            while True:
                level_page = GameScreen(
                    screen,
                    background,
                    font_path,
                    test_mode=test_mode,
                    lang_dict=Lang,
                    progress_flags=game_state.get_progress_flags(),
                )
                level_result = level_page.run()

                if level_result == "back":
                    break  # Return to start page
                if level_result == "quit":
                    result = "quit"
                    break
                if not (level_result and level_result.startswith("level_")):
                    continue

                try:
                    level_num = int(level_result.split("_")[1])
                except Exception:
                    continue

                bosses_required = get_bosses_required(level_num, rounds_config)
                bp_state = game_state.boss_progress.setdefault(level_num, new_boss_progress_state())
                bp_state.setdefault("round_progress", {})
                if bp_state["defeated"] >= bosses_required:
                    bp_state.update(new_boss_progress_state())
                    game_state.reset_napoleondors(level_num)
                    if selected_slot and not test_mode:
                        profile_manager.save_progress_from_game_state(selected_slot)
                run_stats_started_before = bool(bp_state.get("run_stats_started"))
                round_progress_entries = (bp_state.get("round_progress") or {}).values()
                has_level_run_progress = (
                    int(bp_state.get("defeated", 0) or 0) > 0
                    or bool(bp_state.get("current_boss"))
                    or any(
                        bool((entry or {}).get("completed_rounds") or (entry or {}).get("round_selections"))
                        for entry in round_progress_entries
                        if isinstance(entry, dict)
                    )
                )

                # Build per-run card pools on LEVEL selection.
                # A fresh level run must roll optional silver cards once; an already
                # active run keeps its rolled silver pool stable.
                if game_state.active_red_cards_level != level_num:
                    game_state.active_red_cards_level = level_num
                    game_state.active_red_cards_deck = []
                if run_stats_started_before and has_level_run_progress:
                    game_state.ensure_silver_cards_deck_for_level(level_num)
                else:
                    game_state.start_silver_cards_deck_for_level(level_num)
                game_state.ensure_napoleondor_level(level_num)
                if selected_slot and not test_mode:
                    profile_manager.save_progress_from_game_state(selected_slot)

                mark_level_run_started(bp_state, level_num)
                if int(bp_state.get("defeated", 0) or 0) == 0:
                    bonuses_reset = False
                    if game_state.global_start_money_bonus != 0:
                        game_state.global_start_money_bonus = 0
                        bonuses_reset = True
                    if game_state.global_dobor != 1:
                        game_state.global_dobor = 1
                        bonuses_reset = True
                    if game_state.global_hand_bonus != 0:
                        game_state.global_hand_bonus = 0
                        bonuses_reset = True
                    if bonuses_reset and selected_slot and not test_mode:
                        profile_manager.save_progress_from_game_state(selected_slot)
                if selected_slot and not test_mode and not run_stats_started_before and bp_state.get("run_stats_started"):
                    profile_manager.save_progress_from_game_state(selected_slot)

                # Level 3: generate and pin 3 mandatory bosses (no choice) for this run
                if level_num == 3:
                    roster = _ensure_level3_roster(bp_state, bosses_required=bosses_required)
                    LEVEL_BOSS_ROUNDS[3] = roster

                # Boss selection loop
                while True:
                    current_boss = get_current_boss(bp_state)
                    boss_page = None
                    if current_boss is None:
                        current_boss = infer_current_boss_from_round_progress(bp_state)
                        if current_boss is None:
                            current_boss = infer_legacy_current_boss(level_num, bp_state)
                        if current_boss is not None:
                            bp_state["current_boss"] = dict(current_boss)
                            if selected_slot and not test_mode:
                                profile_manager.save_progress_from_game_state(selected_slot)

                    if current_boss is not None:
                        boss_level = level_num
                        boss_index = int(current_boss.get("boss_index", 0))
                        boss_filename = current_boss.get("boss_filename")
                    else:
                        boss_page = BossPage(
                            screen,
                            font_path,
                            level_num,
                            defeated_count=bp_state["defeated"],
                            last_defeated_rect=bp_state["last_rect"],
                            saved_lines=bp_state["lines"],
                            defeated_bosses=bp_state["defeated_bosses"],
                            lang_dict=Lang,
                            level_boss_rounds=LEVEL_BOSS_ROUNDS,
                            load_rounds_config=load_rounds_config,
                            get_bosses_required=get_bosses_required,
                            get_boss_number_from_filename=get_boss_number_from_filename,
                        )
                        boss_result = boss_page.run()

                        if boss_result == "back":
                            break
                        if boss_result == "quit":
                            result = "quit"
                            break
                        if not (boss_result and boss_result.startswith("boss_")):
                            continue

                        parts = boss_result.split("_")
                        boss_level = int(parts[1])
                        boss_index = int(parts[2])

                        boss_filename = None
                        if hasattr(boss_page, "current_boss_filenames") and boss_index < len(boss_page.current_boss_filenames):
                            boss_filename = boss_page.current_boss_filenames[boss_index]
                        set_current_boss(bp_state, bp_state["defeated"], boss_index, boss_filename, boss_page)
                        start_red_deck_for_boss(boss_level)
                        if selected_slot and not test_mode:
                            profile_manager.save_progress_from_game_state(selected_slot)

                    saved_round_progress = get_saved_round_progress(
                        bp_state,
                        bp_state["defeated"],
                        boss_index,
                        boss_filename,
                    )
                    if not saved_round_progress:
                        saved_round_progress = infer_legacy_round_progress(
                            boss_level,
                            bp_state["defeated"],
                            boss_index,
                            boss_filename,
                        )
                        if saved_round_progress:
                            bp_state.setdefault("round_progress", {})[
                                get_round_progress_key(bp_state["defeated"], boss_index, boss_filename)
                            ] = saved_round_progress
                            if selected_slot and not test_mode:
                                profile_manager.save_progress_from_game_state(selected_slot)
                    round_page = RoundPage(
                        screen,
                        font_path,
                        boss_level,
                        boss_index,
                        boss_filename=boss_filename,
                        test_mode=test_mode,
                        defeated_count=bp_state["defeated"],
                        lang_dict=Lang,
                        load_rounds_config=load_rounds_config,
                        load_levels_config=load_levels_config,
                        load_boss_rewards=load_boss_rewards,
                        load_rewards_config=load_rewards_config,
                        get_level2_goal=get_level2_goal,
                        get_level3_goal=get_level3_goal,
                        get_boss_number_from_index=get_boss_number_from_index,
                        get_boss_number_from_filename=get_boss_number_from_filename,
                        apper_goal_boost=apper_goal_boost,
                        reward_token_random_red=REWARD_TOKEN_RANDOM_RED,
                        round_progress=saved_round_progress,
                    )
                    round_result = round_page.run()
                    gameplay_result = None

                    # Round buttons (E/M/H)
                    while round_result in ("button_e", "button_m", "button_h"):
                        difficulty = round_result.replace("button_", "")
                        goal = round_page.Goal if getattr(round_page, "Goal", None) is not None else (2 if test_mode else None)
                        round_num = round_page.get_current_active_round()
                        silver_status, active_cards = choose_active_lifecycle_cards()
                        if silver_status == "back":
                            round_result = round_page.run()
                            continue
                        insurance_goal_debt = game_state.consume_insurance_goal_debt()
                        if insurance_goal_debt:
                            goal = max(0, goal - insurance_goal_debt)

                        gameplay_page = GameplayPage(
                            screen,
                            font_path,
                            difficulty,
                            goal=goal,
                            level_number=boss_level,
                            boss_index=boss_index,
                            round_num=round_num,
                            defeated_count=bp_state["defeated"],  # Pass defeated_count for regular rounds too
                            lang_dict=Lang,
                            test_mode=test_mode,
                            profile_slot=selected_slot,
                            boss_filename=boss_filename,
                            active_silver_cards=active_cards.get("active_silver_cards") or [],
                            active_black_cards=active_cards.get("active_black_cards") or [],
                            active_gold_cards=active_cards.get("active_gold_cards") or [],
                            insurance_goal_debt=insurance_goal_debt,
                            rounds_required=round_page.rounds_required,
                        )
                        gameplay_result = gameplay_page.run()

                        if gameplay_result == "back":
                            if insurance_goal_debt:
                                game_state.add_insurance_goal_debt(insurance_goal_debt)
                            round_result = round_page.run()
                        elif gameplay_result == "round_select":
                            if round_page.last_selected_round is not None:
                                round_page.mark_round_completed(round_page.last_selected_round)
                            if selected_slot and not test_mode:
                                save_round_page_progress(
                                    bp_state,
                                    round_page,
                                    bp_state["defeated"],
                                    boss_index,
                                    boss_filename,
                                )
                                profile_manager.save_progress_from_game_state(selected_slot)
                            award_napoleondors_and_open_shop(
                                boss_level,
                                1,
                                test_mode=test_mode,
                                show_shop=should_open_shop_after_regular_round(boss_level),
                            )
                            round_result = round_page.run()
                        elif gameplay_result == "level_select":
                            mark_level_run_loss_stage(boss_level, f"Раунд {round_num}", round_num)
                            mark_level_run_result(bp_state, boss_level, False)
                            reset_level_attempt(boss_level)
                            if selected_slot and not test_mode:
                                profile_manager.save_progress_from_game_state(selected_slot)
                            break
                        else:
                            round_result = round_page.run()

                    if gameplay_result == "level_select":
                        break
                    if round_result == "back":
                        clear_current_boss(bp_state)
                        if selected_slot and not test_mode:
                            profile_manager.save_progress_from_game_state(selected_slot)
                        continue
                    if round_result == "quit":
                        result = "quit"
                        break

                    # Boss fight
                    if round_result == "boss_clicked":
                        boss_goal = round_page.Goal if getattr(round_page, "Goal", None) is not None else (2 if test_mode else None)
                        silver_status, active_cards = choose_active_lifecycle_cards(is_boss_fight=True)
                        if silver_status == "back":
                            round_result = round_page.run()
                            continue
                        # Pass defeated_count to determine if this is the final boss
                        gameplay_page = GameplayPage(
                            screen,
                            font_path,
                            "e",
                            goal=boss_goal,
                            level_number=boss_level,
                            is_boss_fight=True,
                            boss_index=boss_index,
                            defeated_count=bp_state["defeated"],
                            lang_dict=Lang,
                            test_mode=test_mode,
                            profile_slot=selected_slot,
                            boss_filename=boss_filename,
                            active_silver_cards=active_cards.get("active_silver_cards") or [],
                            active_black_cards=active_cards.get("active_black_cards") or [],
                            active_gold_cards=active_cards.get("active_gold_cards") or [],
                            rounds_required=round_page.rounds_required,
                        )
                        gameplay_result = gameplay_page.run()

                        if gameplay_result == "round_select":
                            current_boss = get_current_boss(bp_state) or {}
                            mark_level_boss_position_result(
                                boss_level,
                                current_boss.get("defeated_count", bp_state["defeated"]),
                                True,
                            )
                            bp_state["defeated"] += 1
                            saved_lines = getattr(boss_page, "saved_lines", None) if boss_page else None
                            if saved_lines is None:
                                saved_lines = [tuple(line) for line in (current_boss.get("saved_lines") or [])]
                            bp_state["last_rect"] = (
                                getattr(boss_page, "clicked_boss_rect", None)
                                if boss_page
                                else list_to_rect(current_boss.get("clicked_boss_rect"))
                            )
                            bp_state["lines"] = saved_lines[:]

                            clicked_filename = (
                                getattr(boss_page, "clicked_boss_filename", None)
                                if boss_page
                                else current_boss.get("clicked_boss_filename") or current_boss.get("boss_filename")
                            )
                            clicked_rect = (
                                getattr(boss_page, "clicked_boss_rect", None)
                                if boss_page
                                else list_to_rect(current_boss.get("clicked_boss_rect"))
                            )
                            if clicked_filename and clicked_rect:
                                bp_state["defeated_bosses"].append(
                                    {"filename": clicked_filename, "rect": clicked_rect.copy()}
                                )
                            clear_round_page_progress(
                                bp_state,
                                current_boss.get("defeated_count", bp_state["defeated"] - 1),
                                current_boss.get("boss_index", boss_index),
                                current_boss.get("boss_filename", boss_filename),
                            )
                            clear_current_boss(bp_state)
                            if bp_state["defeated"] >= bosses_required:
                                award_napoleondors_and_open_shop(
                                    boss_level,
                                    3,
                                    test_mode=test_mode,
                                    show_shop=False,
                                )
                                mark_level_run_result(bp_state, boss_level, True)
                                game_state.complete_level_run(boss_level)
                                if boss_level == 1:
                                    game_state.level_1_boss_defeated = True
                                    print("Level 1 boss defeated! Unlocking level 2")
                                elif boss_level == 2:
                                    game_state.level_2_boss_defeated = True
                                    print("Level 2 completed! Unlocking level 3")
                                elif boss_level == 3:
                                    game_state.level_3_boss_defeated = True
                                    print("Level 3 completed! Unlocking level 4")
                                if selected_slot and not test_mode:
                                    profile_manager.save_progress_from_game_state(selected_slot)
                                break

                            award_napoleondors_and_open_shop(boss_level, 3, test_mode=test_mode)

                            if selected_slot and not test_mode:
                                profile_manager.save_progress_from_game_state(selected_slot)

                            continue

                        if gameplay_result == "level_select":
                            mark_level_boss_position_result(boss_level, bp_state["defeated"], False)
                            mark_level_run_loss_stage(
                                boss_level,
                                f"Босс уровня {int(bp_state.get('defeated', 0) or 0) + 1}",
                                int(bp_state.get("defeated", 0) or 0) + 1,
                            )
                            mark_level_run_result(bp_state, boss_level, False)
                            reset_level_attempt(boss_level)
                            if selected_slot and not test_mode:
                                profile_manager.save_progress_from_game_state(selected_slot)

                        if gameplay_result in ("level_select", "back"):
                            break

                        continue

                    continue

                if result == "quit":
                    break

            if result == "quit":
                break
        elif result == "quit":
            break
    
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
