import json
import os

import pygame

import game_state


PROFILES_DIR = "Profiles"
INDEX_FILE = os.path.join(PROFILES_DIR, "index.json")
MAX_PROFILES = 4


def ensure_profiles_dir():
    os.makedirs(PROFILES_DIR, exist_ok=True)


def get_profile_path(slot):
    return os.path.join(PROFILES_DIR, f"profile_{int(slot)}.json")


def get_stats_file(slot):
    ensure_profiles_dir()
    return os.path.join(PROFILES_DIR, f"GameStats_profile_{int(slot)}.csv")


def load_index():
    ensure_profiles_dir()
    if not os.path.exists(INDEX_FILE):
        return {"selected_slot": None}
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as index_file:
            data = json.load(index_file)
            return data if isinstance(data, dict) else {"selected_slot": None}
    except Exception:
        return {"selected_slot": None}


def save_index(index_data):
    ensure_profiles_dir()
    with open(INDEX_FILE, "w", encoding="utf-8") as index_file:
        json.dump(index_data, index_file, ensure_ascii=False, indent=2)


def get_selected_slot():
    slot = load_index().get("selected_slot")
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return None
    return slot if 1 <= slot <= MAX_PROFILES else None


def set_selected_slot(slot):
    save_index({"selected_slot": int(slot)})


def _default_profile(slot):
    return {
        "version": 1,
        "slot": int(slot),
        "name": "",
        "progress": _empty_progress(),
        "active_game": None,
    }


def _empty_progress():
    return {
        "level_1_boss_defeated": False,
        "level_2_boss_defeated": False,
        "level_3_boss_defeated": False,
        "boss_progress": {},
        "global_dobor": 1,
        "global_start_money_bonus": 0,
        "earned_reward_cards": {},
        "forced_start_hand_cards_by_level": {},
        "active_red_cards_level": None,
        "active_red_cards_deck": [],
    }


def load_profile(slot):
    ensure_profiles_dir()
    slot = int(slot)
    path = get_profile_path(slot)
    if not os.path.exists(path):
        return _default_profile(slot)
    try:
        with open(path, "r", encoding="utf-8") as profile_file:
            data = json.load(profile_file)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    profile = _default_profile(slot)
    profile.update(data)
    profile["slot"] = slot
    profile.setdefault("progress", _capture_progress())
    profile.setdefault("active_game", None)
    return profile


def save_profile(profile):
    ensure_profiles_dir()
    slot = int(profile.get("slot") or 1)
    profile["slot"] = slot
    with open(get_profile_path(slot), "w", encoding="utf-8") as profile_file:
        json.dump(profile, profile_file, ensure_ascii=False, indent=2)


def list_profiles():
    return [load_profile(slot) for slot in range(1, MAX_PROFILES + 1)]


def select_profile(slot, name=None):
    profile = load_profile(slot)
    if name is not None:
        cleaned_name = str(name).strip()
        if cleaned_name:
            profile["name"] = cleaned_name
    if not profile.get("name"):
        profile["name"] = f"Profile {int(slot)}"
    save_profile(profile)
    set_selected_slot(slot)
    apply_profile_to_game_state(profile)
    return profile


def get_selected_profile():
    slot = get_selected_slot()
    return load_profile(slot) if slot else None


def apply_profile_to_game_state(profile_or_slot):
    profile = load_profile(profile_or_slot) if isinstance(profile_or_slot, int) else profile_or_slot
    progress = profile.get("progress") or {}

    game_state.level_1_boss_defeated = bool(progress.get("level_1_boss_defeated", False))
    game_state.level_2_boss_defeated = bool(progress.get("level_2_boss_defeated", False))
    game_state.level_3_boss_defeated = bool(progress.get("level_3_boss_defeated", False))
    game_state.boss_progress = _restore_boss_progress(progress.get("boss_progress") or {})
    game_state.global_dobor = int(progress.get("global_dobor", 1) or 1)
    game_state.global_start_money_bonus = int(progress.get("global_start_money_bonus", 0) or 0)
    game_state.earned_reward_cards = _restore_int_key_lists(progress.get("earned_reward_cards") or {})
    game_state.forced_start_hand_cards_by_level = _restore_int_key_lists(
        progress.get("forced_start_hand_cards_by_level") or {}
    )
    game_state.active_red_cards_level = progress.get("active_red_cards_level")
    game_state.active_red_cards_deck = list(progress.get("active_red_cards_deck") or [])


def save_progress_from_game_state(slot):
    if not slot:
        return None
    profile = load_profile(slot)
    profile["progress"] = _capture_progress()
    save_profile(profile)
    return profile


def save_active_game(slot, context, state):
    if not slot:
        return
    profile = load_profile(slot)
    profile["progress"] = _capture_progress()
    profile["active_game"] = {
        "context": context or {},
        "state": state or {},
    }
    save_profile(profile)


def clear_active_game(slot):
    if not slot:
        return
    profile = load_profile(slot)
    profile["progress"] = _capture_progress()
    profile["active_game"] = None
    save_profile(profile)


def get_active_game(slot):
    if not slot:
        return None
    profile = load_profile(slot)
    active_game = profile.get("active_game")
    return active_game if isinstance(active_game, dict) else None


def _capture_progress():
    return {
        "level_1_boss_defeated": bool(game_state.level_1_boss_defeated),
        "level_2_boss_defeated": bool(game_state.level_2_boss_defeated),
        "level_3_boss_defeated": bool(game_state.level_3_boss_defeated),
        "boss_progress": _serialize_boss_progress(game_state.boss_progress),
        "global_dobor": int(game_state.global_dobor),
        "global_start_money_bonus": int(game_state.global_start_money_bonus),
        "earned_reward_cards": _serialize_int_key_lists(game_state.earned_reward_cards),
        "forced_start_hand_cards_by_level": _serialize_int_key_lists(game_state.forced_start_hand_cards_by_level),
        "active_red_cards_level": game_state.active_red_cards_level,
        "active_red_cards_deck": list(game_state.active_red_cards_deck or []),
    }


def _serialize_int_key_lists(source):
    result = {}
    for key, value in (source or {}).items():
        try:
            result[str(int(key))] = list(value or [])
        except (TypeError, ValueError):
            continue
    return result


def _restore_int_key_lists(source):
    result = {}
    for key, value in (source or {}).items():
        try:
            result[int(key)] = list(value or [])
        except (TypeError, ValueError):
            continue
    return result


def _rect_to_list(rect):
    if rect is None:
        return None
    return [int(rect.x), int(rect.y), int(rect.width), int(rect.height)]


def _list_to_rect(value):
    if not value or len(value) != 4:
        return None
    try:
        return pygame.Rect(int(value[0]), int(value[1]), int(value[2]), int(value[3]))
    except (TypeError, ValueError):
        return None


def _serialize_boss_progress(source):
    result = {}
    for level, state in (source or {}).items():
        try:
            level_key = str(int(level))
        except (TypeError, ValueError):
            continue
        state = state or {}
        defeated_bosses = []
        for item in state.get("defeated_bosses", []) or []:
            defeated_bosses.append(
                {
                    "filename": item.get("filename"),
                    "rect": _rect_to_list(item.get("rect")),
                }
            )
        result[level_key] = {
            "defeated": int(state.get("defeated", 0) or 0),
            "last_rect": _rect_to_list(state.get("last_rect")),
            "lines": [list(line) for line in (state.get("lines") or [])],
            "defeated_bosses": defeated_bosses,
            "roster": state.get("roster"),
            "round_progress": _serialize_round_progress(state.get("round_progress") or {}),
            "current_boss": _serialize_current_boss(state.get("current_boss")),
        }
    return result


def _restore_boss_progress(source):
    result = {}
    for level, state in (source or {}).items():
        try:
            level_key = int(level)
        except (TypeError, ValueError):
            continue
        state = state or {}
        defeated_bosses = []
        for item in state.get("defeated_bosses", []) or []:
            defeated_bosses.append(
                {
                    "filename": item.get("filename"),
                    "rect": _list_to_rect(item.get("rect")),
                }
            )
        result[level_key] = {
            "defeated": int(state.get("defeated", 0) or 0),
            "last_rect": _list_to_rect(state.get("last_rect")),
            "lines": [tuple(line) for line in (state.get("lines") or [])],
            "defeated_bosses": defeated_bosses,
            "roster": state.get("roster"),
            "round_progress": _restore_round_progress(state.get("round_progress") or {}),
            "current_boss": _restore_current_boss(state.get("current_boss")),
        }
    return result


def _serialize_current_boss(source):
    if not isinstance(source, dict):
        return None
    result = dict(source)
    rect = result.get("clicked_boss_rect")
    if isinstance(rect, pygame.Rect):
        result["clicked_boss_rect"] = _rect_to_list(rect)
    result["saved_lines"] = [list(line) for line in (result.get("saved_lines") or [])]
    return result


def _restore_current_boss(source):
    if not isinstance(source, dict):
        return None
    result = dict(source)
    result["saved_lines"] = [
        tuple(line)
        for line in (result.get("saved_lines") or [])
        if isinstance(line, (list, tuple)) and len(line) == 4
    ]
    return result


def _serialize_round_progress(source):
    result = {}
    for key, progress in (source or {}).items():
        progress = progress or {}
        selections = {}
        for round_num, selection in (progress.get("round_selections") or {}).items():
            if isinstance(selection, dict):
                selection_key = selection.get("key")
            else:
                selection_key = selection
            if selection_key in ("e", "m", "h"):
                selections[str(round_num)] = {"key": selection_key}
        result[str(key)] = {
            "completed_rounds": [int(round_num) for round_num in (progress.get("completed_rounds") or [])],
            "round_selections": selections,
            "saved_lines": [list(line) for line in (progress.get("saved_lines") or [])],
        }
    return result


def _restore_round_progress(source):
    result = {}
    for key, progress in (source or {}).items():
        progress = progress or {}
        selections = {}
        for round_num, selection in (progress.get("round_selections") or {}).items():
            if isinstance(selection, dict):
                selection_key = selection.get("key")
            else:
                selection_key = selection
            if str(round_num).isdigit() and selection_key in ("e", "m", "h"):
                selections[int(round_num)] = {"key": selection_key}
        result[str(key)] = {
            "completed_rounds": [
                int(round_num)
                for round_num in (progress.get("completed_rounds") or [])
                if str(round_num).isdigit()
            ],
            "round_selections": selections,
            "saved_lines": [
                tuple(line)
                for line in (progress.get("saved_lines") or [])
                if isinstance(line, (list, tuple)) and len(line) == 4
            ],
        }
    return result
