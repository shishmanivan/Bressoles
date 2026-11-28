import disk_storage
import copy
import errno
import json
import math
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from contextlib import AbstractContextManager, ExitStack, contextmanager
from contextvars import ContextVar
from threading import local

import pygame

import game_state
from gameplay_deck import restore_card_instance, serialize_card_instance
from player_market_stats import empty_stats, accumulate
from player_other_stats import empty_stats as empty_other_stats, record as record_other_stats
from player_time_stats import empty_stats as empty_time_stats, record as record_time_stats
from runtime_diagnostics import logger


PROFILES_DIR = "Profiles"
INDEX_FILE = os.path.join(PROFILES_DIR, "index.json")
MAX_PROFILES = 6
_recovered_profile_paths = set()
save_error_handler = None
_round_result_profile = ContextVar("round_result_profile", default=None)


class ProfileLoadError(OSError):
    """An existing profile cannot safely be loaded or overwritten."""


class ProfileBusyError(ProfileLoadError):
    """Another game holds the profile open."""


_thread_locks = local()


@contextmanager
def _file_lock(path, *, wait=False):
    # A stable sidecar survives atomic JSON replacement. Closing the handle
    # releases the OS lock even when the game is forcibly terminated.
    path = os.path.normcase(os.path.abspath(path + ".lock"))
    held = vars(_thread_locks).setdefault("paths", set())
    if path in held:
        yield
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handle = open(path, "a+b")
    except OSError as error:
        raise ProfileLoadError(f"Cannot open profile lock: {path}") from error
    with handle:
        try:
            disk_storage.lock_file_handle(handle, wait=wait)
        except OSError as error:
            if not wait and error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise ProfileBusyError(f"Profile is in use: {path}") from error
            raise ProfileLoadError(f"Cannot lock profile: {path}") from error
        held.add(path)
        try:
            yield
        finally:
            held.remove(path)


class ProfileSession(AbstractContextManager):
    """Hold the selected slot from its first load until a switch or game exit."""

    def __init__(self):
        self.slot = None
        self._lock = ExitStack()

    def activate(self, slot, operation, *args):
        slot = int(slot)
        if slot == self.slot:
            return operation(slot, *args)
        with ExitStack() as candidate:
            candidate.enter_context(_file_lock(get_profile_path(slot)))
            result = operation(slot, *args)
            self.release()
            self._lock = candidate.pop_all()
            self.slot = slot
            return result

    def release(self):
        self._lock.close()
        self.slot = None

    def __exit__(self, *exc_info):
        self.release()


def was_profile_recovered(slot):
    return os.path.abspath(get_profile_path(slot)) in _recovered_profile_paths


# Older profiles may omit these fields. When present, the restore code reads
# them directly; null cannot stand for an empty collection or a run counter.
_NON_NULL_PROGRESS_FIELDS = {
    "seen_gold_card_ids", "gold_cards", "moratorium_expirations", "moratorium_run_number",
    "price_cut_assistance_shown_levels", "price_cut_assistance_milestones",
}


def _check_optional_type(source, field, expected_type):
    value = source.get(field)
    if value is not None and not isinstance(value, expected_type):
        raise ValueError(f"{field} must be a {expected_type.__name__}")


def _check_number(value, number_type, field):
    try:
        if math.isfinite(number_type(value)):
            return
    except (TypeError, ValueError, OverflowError):
        pass
    raise ValueError(f"{field} must be a finite number")


def _check_coordinates(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("map coordinates must contain four numbers")
    for coordinate in value:
        _check_number(coordinate, int, "map coordinate")


def _check_map_lines(source, field):
    _check_optional_type(source, field, list)
    for line in source.get(field) or []:
        _check_coordinates(line)


def _validate_profile_data(data):
    # Missing optional fields are supported for older saves. A missing progress
    # object is not an empty slot: only a missing file represents a new profile.
    if not isinstance(data, dict) or not isinstance(data.get("progress"), dict):
        raise ValueError("profile must contain a progress object")
    if "name" in data and not isinstance(data["name"], str):
        raise ValueError("profile name must be text")
    if "tutorial_seen" in data and not isinstance(data["tutorial_seen"], list):
        raise ValueError("tutorial_seen must be a list")
    _check_optional_type(data, "balance_checkpoint", dict)
    checkpoint = data.get("balance_checkpoint") or {}
    for field in ("progress", "completed_progress"):
        if checkpoint.get(field) is not None:
            _validate_profile_data({"progress": checkpoint[field]})
    progress = data["progress"]
    for field, default in _empty_progress().items():
        if field not in progress:
            continue
        value = progress[field]
        if value is None and field in _NON_NULL_PROGRESS_FIELDS:
            raise ValueError(f"progress.{field} cannot be null")
        if isinstance(default, (dict, list)) and value is not None and not isinstance(value, type(default)):
            raise ValueError(f"progress.{field} has an invalid container type")
        if type(default) in (int, float) and value is not None:
            # Numeric strings in legacy profiles are still accepted.
            _check_number(value, float if field == "napoleondors" else type(default), field)
    # Legacy migration still reads this field even though new saves omit it.
    _check_optional_type(progress, "forced_start_hand_cards_by_level", dict)
    for field in ("earned_reward_cards", "round_reward_cards", "removed_deck_cards_by_level",
                  "guaranteed_start_hand_cards_by_level", "forced_start_hand_cards_by_level",
                  "loan_boss_positions_by_level"):
        for level in progress.get(field) or {}:
            _check_optional_type(progress[field], level, list)
    for field in ("retention_pending_level", "napoleondor_level", "active_red_cards_level", "active_silver_cards_level"):
        if progress.get(field) is not None:
            _check_number(progress[field], int, field)
    if progress.get("bank_interest_base") is not None:
        _check_number(progress["bank_interest_base"], float, "bank_interest_base")
    for entry in progress.get("pending_finance_report_entries") or []:
        if isinstance(entry, dict) and entry.get("amount") is not None:
            _check_number(entry["amount"], float, "finance report amount")
    for state in (progress.get("boss_progress") or {}).values():
        if not isinstance(state, dict):
            raise ValueError("boss progress entries must be objects")
        if state.get("defeated") is not None:
            _check_number(state["defeated"], int, "defeated")
        _check_map_lines(state, "lines")
        if state.get("last_rect") not in (None, []):
            _check_coordinates(state["last_rect"])
        _check_optional_type(state, "current_boss", dict)
        if state.get("current_boss") is not None:
            _check_map_lines(state["current_boss"], "saved_lines")
        _check_optional_type(state, "shop_history", list)
        _check_optional_type(state, "defeated_bosses", list)
        for boss in state.get("defeated_bosses") or []:
            if not isinstance(boss, dict):
                raise ValueError("defeated bosses must be a list of objects")
            if boss.get("rect") not in (None, []):
                _check_coordinates(boss["rect"])
        _check_optional_type(state, "round_progress", dict)
        for entry in (state.get("round_progress") or {}).values():
            if not isinstance(entry, dict):
                raise ValueError("round progress entries must be objects")
            _check_optional_type(entry, "completed_rounds", list)
            _check_optional_type(entry, "round_selections", dict)
            _check_map_lines(entry, "saved_lines")
        visit = state.get("shop_visit")
        if visit is not None:
            _validate_shop_visit(visit)
    active_game = data.get("active_game")
    if active_game is not None:
        if not isinstance(active_game, dict):
            raise ValueError("active_game must be an object or null")
        for field in ("context", "state"):
            if not isinstance(active_game.get(field), dict):
                raise ValueError(f"active_game.{field} must be an object")
    if data.get("_load_error"):
        raise ValueError("unavailable profile cannot be saved")


def _validate_shop_visit(visit):
    if not isinstance(visit, dict) or type(visit.get("discount_percent")) is not int:
        raise ValueError("shop visit must contain a discount")
    if "offers" not in visit:
        return  # The round is settled, but the first shelf has not been generated yet.
    offers = visit["offers"]
    if not isinstance(offers, list):
        raise ValueError("shop offers must be a list")
    for offer in offers:
        if not isinstance(offer, dict) or type(offer.get("cost")) not in (int, float) or offer["cost"] < 0:
            raise ValueError("shop offer must have a nonnegative price")
        kind = offer.get("kind")
        if kind in ("card", "license") and type(offer.get("card_id")) is int:
            continue
        if kind == "special" and isinstance(offer.get("special_id"), str):
            if "candidates" in offer and not (
                isinstance(offer["candidates"], list) and all(type(card) is int for card in offer["candidates"])
            ):
                raise ValueError("invalid shop card choices")
            continue
        if kind != "investment":
            raise ValueError("invalid shop offer")
    sold = visit.get("sold_offer_indexes")
    if not isinstance(sold, list) or any(type(i) is not int or not 0 <= i < len(offers) for i in sold):
        raise ValueError("invalid sold shop positions")
    if visit.get("pending_assortment") not in (None, "expansion", "diversification"):
        raise ValueError("invalid pending shop assortment")


def _read_profile_data(path):
    def reject_nonfinite(value):
        raise ValueError(f"non-finite JSON number: {value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            reject_nonfinite(value)
        return number

    with disk_storage.open_text(path, encoding="utf-8") as source:
        data = json.load(source, parse_constant=reject_nonfinite, parse_float=finite_float)
    _validate_profile_data(data)
    return data


def _archive_corrupt_profile(path):
    """Keep the original bytes before recovery; abort if this copy fails."""
    descriptor, archive_path = tempfile.mkstemp(
        prefix=f"{os.path.basename(path)}.corrupt-",
        suffix=".bak",
        dir=os.path.dirname(path) or ".",
    )
    try:
        with os.fdopen(descriptor, "wb") as target, open(path, "rb") as source:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        os.remove(archive_path)
        raise
    return archive_path


def _slot_generation(path):
    try:
        with disk_storage.open_text(path + ".generation", encoding="utf-8") as source:
            return str(uuid.UUID(json.load(source)))
    except FileNotFoundError:
        return None  # Existing slots from before deletion tracking.
    except (ValueError, TypeError, AttributeError) as error:
        raise ProfileLoadError(f"Invalid slot generation: {path}") from error


def _read_current_profile(path, generation):
    data = _read_profile_data(path)
    if data.get("generation") != generation:
        raise FileNotFoundError(path)  # This copy belongs to a deleted profile.
    return data


def _load_profile_data_with_recovery(path):
    generation = _slot_generation(path)
    missing = False
    try:
        return _read_current_profile(path, generation)
    except FileNotFoundError:
        missing = True
    except (ValueError, UnicodeError):
        pass
    except OSError as error:
        # Access errors are not evidence of corruption. Never replace that file.
        raise ProfileLoadError(f"Cannot read profile: {path}") from error

    try:
        backup = _read_current_profile(path + ".bak", generation)
    except FileNotFoundError as error:
        if missing:
            return None
        raise ProfileLoadError(f"Damaged profile has no backup: {path}") from error
    except (OSError, ValueError, UnicodeError) as error:
        raise ProfileLoadError(f"No readable backup for profile: {path}") from error

    try:
        if not missing:
            _archive_corrupt_profile(path)
        _write_json_atomically(path, backup)
    except OSError as error:
        raise ProfileLoadError(f"Cannot restore profile: {path}") from error
    _recovered_profile_paths.add(os.path.abspath(path))
    return backup


def ensure_profiles_dir():
    disk_storage.ensure_directory(PROFILES_DIR)


def _write_json_atomically(path, data):
    # save_profile owns recovery of the complete profile (including backups).
    disk_storage.write_json(path, data, interactive=False)


def get_profile_path(slot):
    return os.path.join(PROFILES_DIR, f"profile_{int(slot)}.json")


def get_stats_file(slot):
    ensure_profiles_dir()
    return os.path.join(PROFILES_DIR, f"GameStats_profile_{int(slot)}.csv")


def get_shop_card_stats_file(slot):
    ensure_profiles_dir()
    return os.path.join(PROFILES_DIR, f"ShopCardStats_profile_{int(slot)}.csv")


def load_index():
    ensure_profiles_dir()
    if not disk_storage.exists(INDEX_FILE):
        return {"selected_slot": None}
    try:
        with disk_storage.open_text(INDEX_FILE, encoding="utf-8") as index_file:
            data = json.load(index_file)
            return data if isinstance(data, dict) else {"selected_slot": None}
    except Exception:
        return {"selected_slot": None}


def save_index(index_data):
    ensure_profiles_dir()
    disk_storage.write_json(INDEX_FILE, index_data)


def get_selected_slot():
    slot = load_index().get("selected_slot")
    try:
        slot = int(slot)
    except (TypeError, ValueError):
        return None
    return slot if 1 <= slot <= MAX_PROFILES else None


def set_selected_slot(slot):
    with _file_lock(INDEX_FILE, wait=True):
        save_index({"selected_slot": int(slot)})


def _default_profile(slot):
    return {
        "version": 3,
        "slot": int(slot),
        "name": "",
        "progress": _empty_progress(),
        "active_game": None,
        "tutorial_seen": [],
        "market_roll_stats": empty_stats(),
        "other_stats": empty_other_stats(),
        "lifecycle_card_stats": {"version": 1, "counts": {}, "rounds": {}},
        "play_time_stats": empty_time_stats(),
    }


def _empty_progress():
    return {
        "level_1_boss_defeated": False,
        "level_2_boss_defeated": False,
        "level_3_boss_defeated": False,
        "level_4_boss_defeated": False,
        "level_5_boss_defeated": False,
        "level_6_boss_defeated": False,
        "boss_progress": {},
        "global_dobor": 1,
        "global_start_money_bonus": 0,
        "global_last_turn_bonus": 0,
        "global_hand_bonus": 0,
        "global_start_c_shares_bonus": 0,
        "derivative_bought": False,
        "issuer_bought_count": 0,
        "flash_issue_slots": 0,
        "boss_lifecycle_slot_bonus": 0,
        "boss_shop_offer_bonus": 0,
        "boss_rare_card_pool_bonus_percent": 0,
        "deal_flow_bonus_percent": 0,
        "seen_gold_card_ids": [],
        "moratorium_expirations": {},
        "moratorium_run_number": 0,
        "bank_bought": False,
        "bank_interest_base": None,
        "multibagger_bought": False,
        "diversification_bought": False,
        "expansion_bought": False,
        "opportunity_bought": False,
        "bill_of_exchange_offer_bought": False,
        "compounding_bought": False,
        "capital_preservation_bought": False,
        "retention_active": False,
        "retention_pending_level": None,
        "retention_pending_cards": [],
        "loan_boss_positions_by_level": {},
        "napoleondors": 0,
        "napoleondor_level": None,
        "pending_finance_report_entries": [],
        "earned_reward_cards": {},
        "round_reward_cards": {},
        "shop_deck_cards": [],
        "removed_deck_cards_by_level": {},
        "investment_card_bonuses": {},
        "profit_reward_bonus": 0,
        "updown_probability_bonus": 0,
        "variance_offer_bought_count": 0,
        "pending_shop_discount_percent": 0,
        "correction_shop_cooldown": 0,
        "shop_rerolls": game_state.STARTING_SHOP_REROLLS,
        "bailout_rounds_remaining": 0,
        "price_cut_purchases_by_level": {},
        "price_cut_assistance_shown_levels": [],
        "price_cut_assistance_milestones": {},
        "disclosure_rounds_remaining": 0,
        "whitney_disclosure_active": False,
        "active_price_support_rounds": [],
        "protective_put_charges": 0,
        "active_long_investments": [],
        "golden_stocks_chance_percent": game_state.GOLDEN_STOCKS_BASE_CHANCE,
        "golden_stocks_triggered": False,
        "golden_stocks_trigger_count": 0,
        "licensed_card_ids": _serialize_int_list(game_state.DEFAULT_LICENSED_CARDS),
        "silver_cards": [],
        "black_cards": [],
        "active_black_cards": [],
        "gold_cards": [],
        "active_gold_cards": [],
        "active_lifecycle_card_order": [],
        "bear_goal_reduction_steps": 0,
        "windfall_boss_victories": 0,
        "amplification_bonuses": {},
        "strategic_default_plays": 0,
        "overvaluation_multiplier": 1,
        "risk_premium_h_rounds": 0,
        "golden_stake_shareholder_parity": 0,
        "bankruptcy_condition_chance": 0,
        "insurance_goal_debt": 0,
        "Frugality": 0,
        "guaranteed_start_hand_cards_by_level": {},
        "active_red_cards_level": None,
        "active_red_cards_deck": [],
        "active_silver_cards_level": None,
        "active_silver_cards_deck": [],
        "mirroring_bought_count": 0,
        "mirrored_deck_cards": [],
    }


@contextmanager
def round_result_transaction(slot):
    """Share one profile draft among reward, tutorial and lifetime-stat callbacks."""
    profile = load_profile(slot)
    token = _round_result_profile.set(profile)
    try:
        yield
    finally:
        _round_result_profile.reset(token)
    # Reached only after the terminal board and its progress were both captured.
    save_profile(profile)


def load_profile(slot):
    draft = _round_result_profile.get()
    if draft is not None and draft["slot"] == int(slot):
        return draft
    with _file_lock(get_profile_path(slot)):
        return _load_profile(slot)


def _load_profile(slot):
    ensure_profiles_dir()
    slot = int(slot)
    path = get_profile_path(slot)
    data = _load_profile_data_with_recovery(path)
    if data is None:
        return _default_profile(slot)
    profile = _default_profile(slot)
    profile.update(data)
    # Never imply that a legacy profile has been tracked since its creation.
    profile["market_roll_stats"] = data.get("market_roll_stats")
    profile["other_stats"] = data.get("other_stats")
    profile["lifecycle_card_stats"] = data.get("lifecycle_card_stats")
    profile["play_time_stats"] = data.get("play_time_stats")
    # Existing profiles predate onboarding; only newly created profiles opt in.
    profile["tutorial_seen"] = data.get("tutorial_seen", ["stock_cards", "stock_logo_hover"])
    profile["slot"] = slot
    profile["version"] = data.get("version", 1)
    profile.setdefault("active_game", None)
    migrated = _migrate_campaign_v2(profile)
    if _migrate_campaign_v3(profile):
        migrated = True
    if _migrate_completed_black_rewards(profile):
        migrated = True
    if migrated:
        save_profile(profile)
    return profile


def is_tutorial_pending(slot, hint_id):
    return bool(slot) and hint_id not in load_profile(slot).get("tutorial_seen", [])


def mark_tutorial_seen(slot, hint_id):
    profile = load_profile(slot)
    seen = profile.setdefault("tutorial_seen", [])
    if hint_id not in seen:
        seen.append(hint_id)
        save_profile(profile)


def _migrate_campaign_v2(profile):
    """Move saved state from the former level 4 into its new level-5 slot."""
    try:
        version = int(profile.get("version", 1) or 1)
    except (TypeError, ValueError):
        version = 1
    if version >= 2:
        return False

    progress = profile.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        profile["progress"] = progress

    for field in (
        "boss_progress",
        "earned_reward_cards",
        "round_reward_cards",
        "removed_deck_cards_by_level",
        "forced_start_hand_cards_by_level",
        "guaranteed_start_hand_cards_by_level",
    ):
        values = progress.get(field)
        if isinstance(values, dict) and "4" in values and "5" not in values:
            values["5"] = values.pop("4")

    for field in ("napoleondor_level", "active_red_cards_level", "active_silver_cards_level"):
        try:
            if int(progress.get(field)) == 4:
                progress[field] = 5
        except (TypeError, ValueError):
            pass

    active_game = profile.get("active_game")
    if isinstance(active_game, dict):
        context = active_game.get("context")
        if isinstance(context, dict):
            try:
                if int(context.get("level_number")) == 4:
                    context["level_number"] = 5
            except (TypeError, ValueError):
                pass

    migrated_level5 = (progress.get("boss_progress") or {}).get("5") or {}
    try:
        level5_completed = int(migrated_level5.get("defeated", 0) or 0) >= 4
    except (TypeError, ValueError):
        level5_completed = False
    progress["level_4_boss_defeated"] = False
    progress["level_5_boss_defeated"] = level5_completed
    profile["version"] = 2
    return True


def _migrate_campaign_v3(profile):
    """Old builds saved the sixth campaign card as 8 and the retired duel as 6."""
    if int(profile["version"]) >= 3:
        return False

    # Before the duel existed, some saves already used 6 for this route.
    progress = profile["progress"]
    routes = progress.get("boss_progress") or {}
    old_six = routes.get("6") or {}
    active = profile.get("active_game") or {}
    context = active.get("context") or {}
    original_six = ("8" not in routes and "level_8_boss_defeated" not in progress
                    and ((isinstance(old_six.get("roster"), list) and len(old_six["roster"]) == 4)
                         or int(old_six.get("defeated") or 0) > 1
                         or (str(context.get("level_number")) == "6"
                             and context.get("is_boss_fight") is False)))

    def campaign_level(old):
        if str(old) == "8" or (original_six and str(old) == "6"):
            return 6
        if str(old) in ("1", "2", "3", "4", "5"):
            return int(old)
        return None

    def migrate_progress(progress):
        old_key = "6" if original_six else "8"
        route = (progress.get("boss_progress") or {}).get(old_key) or {}
        completed = int(route.get("defeated") or 0) >= 4
        progress["level_6_boss_defeated"] = bool(progress.pop("level_8_boss_defeated", completed))
        for field in ("boss_progress", "earned_reward_cards", "round_reward_cards",
                      "removed_deck_cards_by_level", "forced_start_hand_cards_by_level",
                      "guaranteed_start_hand_cards_by_level", "loan_boss_positions_by_level",
                      "price_cut_purchases_by_level", "price_cut_assistance_milestones"):
            if isinstance(progress.get(field), dict):
                progress[field] = {str(campaign_level(key)): value for key, value in progress[field].items()
                                   if campaign_level(key) is not None}
        for field in ("napoleondor_level", "active_red_cards_level", "active_silver_cards_level",
                      "retention_pending_level"):
            if field in progress:
                progress[field] = campaign_level(progress[field])
        if isinstance(progress.get("price_cut_assistance_shown_levels"), list):
            progress["price_cut_assistance_shown_levels"] = [
                campaign_level(level) for level in progress["price_cut_assistance_shown_levels"]
                if campaign_level(level) is not None
            ]

    migrate_progress(profile["progress"])
    active = profile.get("active_game")
    if active and "level_number" in active["context"]:
        level = campaign_level(active["context"]["level_number"])
        if level is None:
            profile["active_game"] = None
        else:
            active["context"]["level_number"] = level
            receipt = active["state"].get("pending_result_stats")
            if isinstance(receipt, dict) and isinstance(receipt.get("encounter"), list) and receipt["encounter"]:
                receipt["encounter"][0] = level
            if "level_number" in active["state"]:
                active["state"]["level_number"] = level
    checkpoint = profile.get("balance_checkpoint")
    if checkpoint:
        level = campaign_level(checkpoint.get("level"))
        if level is None:
            profile.pop("balance_checkpoint")
        else:
            checkpoint["level"] = level
            for field in ("progress", "completed_progress"):
                if isinstance(checkpoint.get(field), dict):
                    migrate_progress(checkpoint[field])
    times = profile.get("play_time_stats")
    if isinstance(times, dict) and not original_six:
        levels = times.get("levels")
        if isinstance(levels, dict):
            if "6" in levels:
                levels["archive"] = levels.pop("6")
            if "8" in levels:
                levels["6"] = levels.pop("8")
        rounds = times.get("rounds")
        for entry in rounds.values() if isinstance(rounds, dict) else ():
            if isinstance(entry, dict) and str(entry.get("level")) in ("6", "8"):
                entry["level"] = campaign_level(entry["level"])
    profile["version"] = 3
    return True


def _migrate_completed_black_rewards(profile):
    """Restore permanent black rewards implied by completed-level flags."""
    progress = profile.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        profile["progress"] = progress

    black_cards = _restore_int_list(progress.get("black_cards") or [])
    added = []
    for level_number, reward_cards in sorted(
        game_state.LEVEL_COMPLETION_BLACK_REWARD_CARDS.items()
    ):
        if not progress.get(f"level_{level_number}_boss_defeated", False):
            continue
        for card_id in reward_cards:
            normalized = int(card_id)
            if normalized == 304 and 305 in black_cards:
                continue
            if normalized in black_cards or len(black_cards) >= game_state.MAX_BLACK_CARDS:
                continue
            black_cards.append(normalized)
            added.append(normalized)

    if not added:
        return False
    progress["black_cards"] = sorted(black_cards)
    return True


def save_profile(profile):
    draft = _round_result_profile.get()
    if draft is not None and profile is draft:
        return
    with _file_lock(get_profile_path(profile.get("slot") or 1)):
        _save_profile(profile)


def _save_profile(profile):
    # Keep the exact requested state while the UI waits. Retrying the game
    # action itself could award money/cards twice.
    pending = copy.deepcopy(profile)
    recovery_path = None
    while True:
        try:
            _save_profile_once(pending)
            break
        except ProfileLoadError:
            raise  # Never overwrite an unreadable existing profile.
        except OSError as error:
            if save_error_handler is None:
                raise
            logger.exception("Profile save failed; holding progress for retry")
            if recovery_path is None:
                candidate = None
                try:
                    descriptor, candidate = tempfile.mkstemp(
                        prefix=f"profile_{pending.get('slot', 1)}.pending-",
                        suffix=".json", dir=PROFILES_DIR,
                    )
                    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                        json.dump(pending, output, ensure_ascii=False, indent=2, allow_nan=False)
                        output.flush()
                        os.fsync(output.fileno())
                    recovery_path = candidate
                    logger.warning("Pending progress preserved: %s", recovery_path)
                except OSError:
                    logger.exception("Could not write emergency progress snapshot")
                    if candidate is not None:
                        try:
                            os.remove(candidate)
                        except OSError:
                            pass
            save_error_handler(error, recovery_path)
    # Preserve the existing caller-visible normalization contract.
    profile.update(pending)
    if recovery_path is not None:
        try:
            os.remove(recovery_path)
        except OSError:
            logger.warning("Could not remove resolved snapshot: %s", recovery_path)


def _save_profile_once(profile):
    ensure_profiles_dir()
    slot = int(profile.get("slot") or 1)
    profile["slot"] = slot
    _validate_profile_data(profile)
    # Temporary balance tooling: keep the final state independently of autosaves.
    checkpoint = profile.get("balance_checkpoint")
    if isinstance(checkpoint, dict):
        level = checkpoint.get("level")
        if profile["progress"].get(f"level_{level}_boss_defeated"):
            checkpoint["completed_progress"] = copy.deepcopy(profile["progress"])
    path = get_profile_path(slot)
    generation = _slot_generation(path)
    if profile.get("generation") != generation:
        raise ProfileLoadError(f"Cannot save a deleted profile: {path}")
    try:
        previous = _read_current_profile(path, generation)
    except FileNotFoundError:
        try:
            _read_current_profile(path + ".bak", generation)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, UnicodeError) as error:
            raise ProfileLoadError(f"Unreadable backup: {path}") from error
        else:
            raise ProfileLoadError(f"Load the backup before saving profile: {path}")
        previous = profile
    except (OSError, ValueError, UnicodeError) as error:
        raise ProfileLoadError(f"Refusing to overwrite unreadable profile: {path}") from error
    # Store a valid recovery point before replacing the primary. On the first
    # save both files contain the new profile; later the backup is one save old.
    _write_json_atomically(path + ".bak", previous)
    _write_json_atomically(path, profile)


def list_profiles():
    profiles = []
    for slot in range(1, MAX_PROFILES + 1):
        try:
            profiles.append(load_profile(slot))
        except ProfileLoadError as error:
            unavailable = _default_profile(slot)
            unavailable["_load_error"] = str(error)
            if isinstance(error, ProfileBusyError):
                unavailable["_busy"] = True
            profiles.append(unavailable)
    return profiles


def delete_profile(slot):
    """Free a save slot; all CSV statistics remain cumulative and untouched."""
    slot = int(slot)
    if not 1 <= slot <= MAX_PROFILES:
        raise ValueError("Invalid profile slot")
    path = get_profile_path(slot)
    with _file_lock(path):
        _delete_profile(slot, path)


def _delete_profile(slot, path):
    with _file_lock(INDEX_FILE, wait=True):
        if get_selected_slot() == slot:
            save_index({"selected_slot": None})
    for pattern in (Path(path).name + ".corrupt-*.bak", f"profile_{slot}.pending-*.json"):
        for snapshot in Path(path).parent.glob(pattern):
            snapshot.unlink()
    try:
        disk_storage.disk_operation(lambda: os.remove(path + ".bak"), missing_ok=True)
    except FileNotFoundError:
        pass
    # Commit the deletion before removing the last playable copy. Even if an
    # old backup returns to disk, its generation can never be selected again.
    _write_json_atomically(path + ".generation", str(uuid.uuid4()))
    try:
        disk_storage.disk_operation(lambda: os.remove(path), missing_ok=True)
    except FileNotFoundError:
        pass
    _recovered_profile_paths.discard(os.path.abspath(path))


def select_profile(slot, name=None):
    with _file_lock(get_profile_path(slot)):
        return _select_profile(slot, name)


def _select_profile(slot, name):
    profile = load_profile(slot)
    generation = _slot_generation(get_profile_path(slot))
    if generation is not None:
        profile["generation"] = generation
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


def apply_profile_to_game_state(profile_or_slot):
    profile = load_profile(profile_or_slot) if isinstance(profile_or_slot, int) else profile_or_slot
    _validate_profile_data(profile)
    _migrate_completed_black_rewards(profile)
    progress = profile.get("progress") or {}
    game_state.seen_gold_card_ids = {
        int(value) for value in progress.get("seen_gold_card_ids", [])
        if str(value).isdecimal() and game_state.is_gold_card(int(value))
    }
    game_state.seen_gold_card_ids.update(
        int(value) for value in progress.get("gold_cards", [])
        if str(value).isdecimal() and game_state.is_gold_card(int(value))
    )
    game_state.moratorium_run_number = max(0, int(progress.get("moratorium_run_number", 0)))
    game_state.price_cut_purchases_by_level = {
        int(key): int(value)
        for key, value in (progress.get("price_cut_purchases_by_level") or {}).items()
        if str(key).isdecimal() and 1 <= int(key) <= 6
        and str(value).isdecimal() and int(value) > 0
    }
    game_state.price_cut_assistance_shown_levels = {
        int(level) for level in progress.get("price_cut_assistance_shown_levels", [])
        if str(level).isdecimal() and 1 <= int(level) <= 6
    }
    game_state.price_cut_assistance_milestones = {
        int(key): int(value)
        for key, value in progress.get("price_cut_assistance_milestones", {}).items()
        if str(key).isdecimal() and 1 <= int(key) <= 6
        and str(value).isdecimal() and int(value) > 0
    }
    for level in game_state.price_cut_assistance_shown_levels:
        game_state.price_cut_assistance_milestones.setdefault(level, 1)
    game_state.moratorium_expirations = {
        int(key): int(value)
        for key, value in progress.get("moratorium_expirations", {}).items()
        if str(key).isdecimal() and str(value).isdecimal() and game_state.is_gold_card(int(key))
    }

    game_state.level_1_boss_defeated = bool(progress.get("level_1_boss_defeated", False))
    game_state.level_2_boss_defeated = bool(progress.get("level_2_boss_defeated", False))
    game_state.level_3_boss_defeated = bool(progress.get("level_3_boss_defeated", False))
    game_state.level_4_boss_defeated = bool(progress.get("level_4_boss_defeated", False))
    game_state.level_5_boss_defeated = bool(progress.get("level_5_boss_defeated", False))
    game_state.level_6_boss_defeated = bool(progress.get("level_6_boss_defeated", False))
    game_state.boss_progress = _restore_boss_progress(progress.get("boss_progress") or {})
    game_state.global_dobor = int(progress.get("global_dobor", 1) or 1)
    game_state.global_start_money_bonus = int(progress.get("global_start_money_bonus", 0) or 0)
    game_state.global_last_turn_bonus = int(progress.get("global_last_turn_bonus", 0) or 0)
    game_state.global_hand_bonus = int(progress.get("global_hand_bonus", 0) or 0)
    game_state.global_start_c_shares_bonus = int(progress.get("global_start_c_shares_bonus", 0) or 0)
    game_state.derivative_bought = bool(progress.get("derivative_bought", False))
    try:
        game_state.flash_issue_slots = max(0, int(progress.get("flash_issue_slots", 0) or 0))
    except (TypeError, ValueError):
        game_state.flash_issue_slots = 0
    try:
        game_state.issuer_bought_count = max(
            0,
            min(game_state.ISSUER_MAX_PURCHASES, int(progress.get("issuer_bought_count", 0) or 0)),
        )
    except (TypeError, ValueError):
        game_state.issuer_bought_count = 0
    try:
        game_state.boss_lifecycle_slot_bonus = max(
            0,
            int(progress.get("boss_lifecycle_slot_bonus", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.boss_lifecycle_slot_bonus = 0
    try:
        game_state.boss_shop_offer_bonus = max(
            0,
            int(progress.get("boss_shop_offer_bonus", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.boss_shop_offer_bonus = 0
    try:
        game_state.boss_rare_card_pool_bonus_percent = max(
            0,
            min(10, int(progress.get("boss_rare_card_pool_bonus_percent", 0) or 0)),
        )
    except (TypeError, ValueError):
        game_state.boss_rare_card_pool_bonus_percent = 0
    try:
        game_state.deal_flow_bonus_percent = max(
            0,
            min(100, int(progress.get("deal_flow_bonus_percent", 0) or 0)),
        )
    except (TypeError, ValueError):
        game_state.deal_flow_bonus_percent = 0
    game_state.bank_bought = bool(progress.get("bank_bought", False))
    try:
        game_state.bank_interest_base = (
            float(progress.get("bank_interest_base"))
            if progress.get("bank_interest_base") is not None
            else None
        )
    except (TypeError, ValueError):
        game_state.bank_interest_base = None
    game_state.multibagger_bought = bool(progress.get("multibagger_bought", False))
    game_state.diversification_bought = bool(progress.get("diversification_bought", False))
    game_state.expansion_bought = bool(progress.get("expansion_bought", False))
    game_state.opportunity_bought = bool(progress.get("opportunity_bought", False))
    game_state.bill_of_exchange_offer_bought = bool(
        progress.get("bill_of_exchange_offer_bought", False)
    )
    game_state.compounding_bought = bool(progress.get("compounding_bought", False))
    game_state.capital_preservation_bought = bool(
        progress.get("capital_preservation_bought", False)
    )
    game_state.retention_active = bool(progress.get("retention_active", False))
    try:
        game_state.retention_pending_level = (
            int(progress.get("retention_pending_level"))
            if progress.get("retention_pending_level") is not None
            else None
        )
    except (TypeError, ValueError):
        game_state.retention_pending_level = None
    game_state.retention_pending_cards = _restore_int_list(
        progress.get("retention_pending_cards") or []
    )
    try:
        game_state.mirroring_bought_count = max(
            0,
            min(
                game_state.MIRRORING_MAX_PURCHASES,
                int(progress.get("mirroring_bought_count", 0) or 0),
            ),
        )
    except (TypeError, ValueError):
        game_state.mirroring_bought_count = 0
    game_state.mirrored_deck_cards = [
        restored
        for restored in (
            restore_card_instance(value)
            for value in (progress.get("mirrored_deck_cards") or [])
        )
        if restored is not None
    ][: game_state.MIRRORING_MAX_PURCHASES]
    game_state.loan_boss_positions_by_level = _restore_int_key_lists(
        progress.get("loan_boss_positions_by_level") or {}
    )
    game_state.napoleondors = float(progress.get("napoleondors", 0) or 0)
    try:
        game_state.napoleondor_level = int(progress.get("napoleondor_level"))
    except (TypeError, ValueError):
        game_state.napoleondor_level = None
    game_state.pending_finance_report_entries = []
    for entry in progress.get("pending_finance_report_entries") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("source") or "") == "starting_bonus":
            try:
                amount = max(0.0, float(entry.get("amount", 0) or 0))
            except (TypeError, ValueError):
                amount = 0.0
            game_state.pending_finance_report_entries.append(
                {"source": "starting_bonus", "amount": amount}
            )
        else:
            game_state.record_finance_report_income(entry.get("source"), entry.get("amount"))
    game_state.earned_reward_cards = _restore_int_key_lists(progress.get("earned_reward_cards") or {})
    game_state.round_reward_cards = _restore_int_key_lists(progress.get("round_reward_cards") or {})
    game_state.shop_deck_cards = _restore_int_list(progress.get("shop_deck_cards") or [])
    try:
        game_state.shop_rerolls = max(0, min(game_state.MAX_SHOP_REROLLS,
            int(progress.get("shop_rerolls", game_state.STARTING_SHOP_REROLLS))))
    except (TypeError, ValueError, OverflowError):
        game_state.shop_rerolls = 0
    game_state.removed_deck_cards_by_level = _restore_int_key_lists(progress.get("removed_deck_cards_by_level") or {})
    game_state.investment_card_bonuses = {
        card_id: bonus
        for card_id, bonus in _restore_int_value_dict(
            progress.get("investment_card_bonuses") or {}
        ).items()
        if game_state.is_investment_eligible_card(card_id)
    }
    game_state.profit_reward_bonus = int(progress.get("profit_reward_bonus", 0) or 0)
    game_state.updown_probability_bonus = max(0, int(progress.get("updown_probability_bonus", 0) or 0))
    game_state.variance_offer_bought_count = max(
        0,
        int(progress.get("variance_offer_bought_count", 0) or 0),
    )
    try:
        game_state.pending_shop_discount_percent = max(
            0,
            min(100, int(progress.get("pending_shop_discount_percent", 0) or 0)),
        )
    except (TypeError, ValueError):
        game_state.pending_shop_discount_percent = 0
    try:
        game_state.correction_shop_cooldown = max(
            0,
            int(progress.get("correction_shop_cooldown", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.correction_shop_cooldown = 0
    try:
        game_state.bailout_rounds_remaining = max(
            0,
            int(progress.get("bailout_rounds_remaining", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.bailout_rounds_remaining = 0
    try:
        game_state.disclosure_rounds_remaining = max(
            0,
            int(progress.get("disclosure_rounds_remaining", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.disclosure_rounds_remaining = 0
    game_state.whitney_disclosure_active = bool(progress.get("whitney_disclosure_active", False))
    game_state.active_price_support_rounds = [
        min(5, value) for value in _restore_int_list(progress.get("active_price_support_rounds") or []) if value > 0
    ][:3]
    try:
        game_state.protective_put_charges = max(0, min(3, int(progress.get("protective_put_charges", 0) or 0)))
    except (TypeError, ValueError):
        game_state.protective_put_charges = 0
    game_state.active_long_investments = _restore_int_list(progress.get("active_long_investments") or [])[
        : game_state.LONG_MAX_ACTIVE
    ]
    try:
        game_state.golden_stocks_chance_percent = max(
            game_state.GOLDEN_STOCKS_BASE_CHANCE,
            min(100, int(progress.get("golden_stocks_chance_percent", game_state.GOLDEN_STOCKS_BASE_CHANCE) or 0)),
        )
    except (TypeError, ValueError):
        game_state.golden_stocks_chance_percent = game_state.GOLDEN_STOCKS_BASE_CHANCE
    game_state.golden_stocks_triggered = bool(progress.get("golden_stocks_triggered", False))
    try:
        game_state.golden_stocks_trigger_count = max(
            0,
            int(progress.get("golden_stocks_trigger_count", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.golden_stocks_trigger_count = 0
    if "licensed_card_ids" in progress:
        game_state.licensed_card_ids = game_state.normalize_license_ids(progress.get("licensed_card_ids"))
    else:
        game_state.licensed_card_ids = game_state.get_legacy_open_license_ids()
    game_state.silver_cards = _restore_int_list(progress.get("silver_cards") or [])[: game_state.MAX_SILVER_CARDS]
    game_state.black_cards = _restore_int_list(progress.get("black_cards") or [])[: game_state.MAX_BLACK_CARDS]
    game_state.set_active_black_cards(_restore_int_list(progress.get("active_black_cards") or []))
    game_state.gold_cards = _restore_int_list(progress.get("gold_cards") or [])[: game_state.MAX_GOLD_CARDS]
    game_state.set_active_gold_cards(_restore_int_list(progress.get("active_gold_cards") or []))
    game_state.set_active_lifecycle_card_order(progress.get("active_lifecycle_card_order") or [])
    try:
        game_state.bear_goal_reduction_steps = max(0, int(progress.get("bear_goal_reduction_steps", 0) or 0))
    except (TypeError, ValueError):
        game_state.bear_goal_reduction_steps = 0
    try:
        game_state.overvaluation_multiplier = max(1, int(progress.get("overvaluation_multiplier", 1) or 1))
    except (TypeError, ValueError):
        game_state.overvaluation_multiplier = 1
    game_state.amplification_bonuses = {
        key: bonus for key, bonus in (progress.get("amplification_bonuses") or {}).items()
        if isinstance(bonus, int) and bonus > 0
    }
    try:
        game_state.strategic_default_plays = max(0, int(progress.get('strategic_default_plays', 0)))
    except (ValueError, TypeError):
        game_state.strategic_default_plays = 0
    try:
        game_state.windfall_boss_victories = max(
            0,
            int(progress.get("windfall_boss_victories", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.windfall_boss_victories = 0
    game_state.set_bankruptcy_condition_chance(progress.get("bankruptcy_condition_chance", 0))
    try:
        game_state.golden_stake_shareholder_parity = max(0, int(progress.get("golden_stake_shareholder_parity", 0) or 0)) % 2
    except (TypeError, ValueError):
        game_state.golden_stake_shareholder_parity = 0
    try:
        game_state.risk_premium_h_rounds = max(
            0,
            int(progress.get("risk_premium_h_rounds", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.risk_premium_h_rounds = 0
    try:
        game_state.insurance_goal_debt = max(0, int(progress.get("insurance_goal_debt", 0) or 0))
    except (TypeError, ValueError):
        game_state.insurance_goal_debt = 0
    try:
        game_state.Frugality = max(0, int(progress.get("Frugality", 0) or 0))
    except (TypeError, ValueError):
        game_state.Frugality = 0
    _migrate_silver_cards_from_earned_rewards()
    game_state.forced_start_hand_cards_by_level = _restore_int_key_lists(
        progress.get("forced_start_hand_cards_by_level") or {}
    )
    game_state.guaranteed_start_hand_cards_by_level = _restore_int_key_lists(
        progress.get("guaranteed_start_hand_cards_by_level") or {}
    )
    game_state.migrate_legacy_forced_start_hand_cards()
    game_state.active_red_cards_level = progress.get("active_red_cards_level")
    game_state.active_red_cards_deck = list(progress.get("active_red_cards_deck") or [])
    game_state.active_silver_cards_level = progress.get("active_silver_cards_level")
    game_state.active_silver_cards_deck = list(progress.get("active_silver_cards_deck") or [])


def capture_balance_checkpoint(slot, level):
    """Keep one replay boundary until the player starts a different level."""
    if not slot:
        return
    profile = load_profile(slot)
    checkpoint = profile.get("balance_checkpoint") or {}
    if checkpoint.get("level") == int(level):
        return
    # An old save already inside a run has no trustworthy pre-level snapshot.
    state = game_state.boss_progress.get(int(level)) or {}
    if state.get("run_stats_started") or state.get("defeated") or state.get("round_progress"):
        return
    profile["progress"] = _capture_progress()
    profile["balance_checkpoint"] = {
        "level": int(level),
        "progress": copy.deepcopy(profile["progress"]),
    }
    save_profile(profile)


def get_balance_replay_level(slot):
    if not slot:
        return None
    checkpoint = load_profile(slot).get("balance_checkpoint") or {}
    return checkpoint.get("level") if isinstance(checkpoint.get("progress"), dict) else None


def rollback_balance_level(slot):
    """Restore gameplay only; all CSV attempt statistics remain cumulative."""
    if not slot:
        return False
    profile = load_profile(slot)
    checkpoint = profile.get("balance_checkpoint") or {}
    if not isinstance(checkpoint.get("progress"), dict):
        return False
    profile["progress"] = copy.deepcopy(checkpoint["progress"])
    profile["active_game"] = None
    save_profile(profile)
    apply_profile_to_game_state(profile)
    return True


def record_player_market_rolls(slot, rolls, quantities, *, test_mode=False):
    """Persist lifetime counters independently of run resets and checkpoints."""
    if not slot or test_mode or not rolls:
        return
    # A gameplay callback must not create an unselected/missing profile.
    if not disk_storage.exists(get_profile_path(slot)):
        return
    profile = load_profile(slot)
    stats = profile.get("market_roll_stats")
    if stats is None:
        return
    accumulate(stats, rolls, quantities)
    save_profile(profile)


def record_player_other_stats(slot, round_id, cards, *, earned=None, label=None, result=None):
    if not slot or not disk_storage.exists(get_profile_path(slot)):
        return None
    profile = load_profile(slot)
    stats = profile.get("other_stats")
    if stats is None:
        return None
    record_other_stats(stats, round_id, cards, earned=earned, label=label, result=result)
    save_profile(profile)
    return copy.deepcopy(stats)


def record_player_time(slot, level, round_id, seconds, *, test_mode=False):
    if not slot or test_mode or not disk_storage.exists(get_profile_path(slot)):
        return None
    profile = load_profile(slot)
    stats = profile.get("play_time_stats")
    if stats is None:
        return None
    record_time_stats(stats, level, round_id, seconds)
    save_profile(profile)
    return copy.deepcopy(stats)


def record_player_lifecycle_cards(slot, round_id, cards, *, test_mode=False):
    """Count each equipped copy once per round; replaying a save adds nothing."""
    if not slot or test_mode or not round_id or not disk_storage.exists(get_profile_path(slot)):
        return
    from collections import Counter
    profile = load_profile(slot)
    stats = profile.get("lifecycle_card_stats")
    if stats is None:
        return
    current = Counter(str(int(card)) for card in cards if 200 <= int(card) < 500)
    if not current:
        return
    previous = stats["rounds"].setdefault(round_id, {})
    changed = False
    for card, count in current.items():
        delta = max(0, count - previous.get(card, 0))
        if delta:
            stats["counts"][card] = stats["counts"].get(card, 0) + delta
            previous[card] = count
            changed = True
    if changed:
        save_profile(profile)


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
        "level_4_boss_defeated": bool(game_state.level_4_boss_defeated),
        "level_5_boss_defeated": bool(game_state.level_5_boss_defeated),
        "level_6_boss_defeated": bool(game_state.level_6_boss_defeated),
        "boss_progress": _serialize_boss_progress(game_state.boss_progress),
        "global_dobor": int(game_state.global_dobor),
        "global_start_money_bonus": int(game_state.global_start_money_bonus),
        "global_last_turn_bonus": int(game_state.global_last_turn_bonus),
        "global_hand_bonus": int(game_state.global_hand_bonus),
        "global_start_c_shares_bonus": int(game_state.global_start_c_shares_bonus),
        "derivative_bought": bool(game_state.derivative_bought),
        "issuer_bought_count": game_state.get_issuer_bought_count(),
        "flash_issue_slots": game_state.flash_issue_slots,
        "boss_lifecycle_slot_bonus": max(0, int(game_state.boss_lifecycle_slot_bonus or 0)),
        "boss_shop_offer_bonus": game_state.get_boss_shop_offer_bonus(),
        "boss_rare_card_pool_bonus_percent": game_state.get_boss_rare_card_pool_bonus(),
        "deal_flow_bonus_percent": game_state.get_deal_flow_bonus(),
        "seen_gold_card_ids": sorted(game_state.seen_gold_card_ids),
        "moratorium_expirations": dict(game_state.moratorium_expirations),
        "moratorium_run_number": game_state.moratorium_run_number,
        "bank_bought": bool(game_state.bank_bought),
        "bank_interest_base": game_state.bank_interest_base,
        "multibagger_bought": bool(game_state.multibagger_bought),
        "diversification_bought": bool(game_state.diversification_bought),
        "expansion_bought": bool(game_state.expansion_bought),
        "opportunity_bought": bool(game_state.opportunity_bought),
        "bill_of_exchange_offer_bought": bool(game_state.bill_of_exchange_offer_bought),
        "compounding_bought": bool(game_state.compounding_bought),
        "capital_preservation_bought": bool(game_state.capital_preservation_bought),
        "retention_active": bool(game_state.retention_active),
        "retention_pending_level": game_state.retention_pending_level,
        "retention_pending_cards": _serialize_int_list(game_state.retention_pending_cards),
        "mirroring_bought_count": game_state.get_mirroring_bought_count(),
        "mirrored_deck_cards": [
            serialize_card_instance(card_id)
            for card_id in game_state.mirrored_deck_cards
        ],
        "loan_boss_positions_by_level": _serialize_int_key_lists(
            game_state.loan_boss_positions_by_level
        ),
        "napoleondors": float(game_state.napoleondors),
        "napoleondor_level": game_state.napoleondor_level,
        "pending_finance_report_entries": [
            dict(entry) for entry in game_state.pending_finance_report_entries
        ],
        "earned_reward_cards": _serialize_int_key_lists(game_state.earned_reward_cards),
        "round_reward_cards": _serialize_int_key_lists(game_state.round_reward_cards),
        "shop_deck_cards": _serialize_int_list(game_state.shop_deck_cards),
        "removed_deck_cards_by_level": _serialize_int_key_lists(game_state.removed_deck_cards_by_level),
        "investment_card_bonuses": _serialize_int_value_dict(
            game_state.get_active_investment_card_bonuses()
        ),
        "profit_reward_bonus": int(game_state.profit_reward_bonus),
        "updown_probability_bonus": game_state.get_updown_probability_bonus(),
        "variance_offer_bought_count": max(0, int(game_state.variance_offer_bought_count or 0)),
        "pending_shop_discount_percent": int(game_state.pending_shop_discount_percent or 0),
        "correction_shop_cooldown": game_state.get_correction_shop_cooldown(),
        "shop_rerolls": game_state.get_shop_rerolls(),
        "bailout_rounds_remaining": game_state.get_bailout_rounds_remaining(),
        "price_cut_purchases_by_level": dict(game_state.price_cut_purchases_by_level),
        "price_cut_assistance_shown_levels": sorted(game_state.price_cut_assistance_shown_levels),
        "price_cut_assistance_milestones": dict(game_state.price_cut_assistance_milestones),
        "disclosure_rounds_remaining": game_state.get_disclosure_rounds_remaining(),
        "whitney_disclosure_active": bool(game_state.whitney_disclosure_active),
        "active_price_support_rounds": game_state.get_active_price_support_rounds(),
        "protective_put_charges": game_state.get_protective_put_charges(),
        "active_long_investments": _serialize_int_list(game_state.get_active_long_investments()),
        "golden_stocks_chance_percent": game_state.get_golden_stocks_chance_percent(),
        "golden_stocks_triggered": game_state.is_golden_stocks_triggered(),
        "golden_stocks_trigger_count": game_state.get_golden_stocks_trigger_count(),
        "licensed_card_ids": _serialize_int_list(game_state.licensed_card_ids),
        "silver_cards": _serialize_int_list(game_state.silver_cards),
        "black_cards": _serialize_int_list(game_state.black_cards),
        "active_black_cards": _serialize_int_list(game_state.active_black_cards),
        "gold_cards": _serialize_int_list(game_state.gold_cards),
        "active_gold_cards": _serialize_int_list(game_state.active_gold_cards),
        "active_lifecycle_card_order": _serialize_lifecycle_card_order(game_state.active_lifecycle_card_order),
        "bear_goal_reduction_steps": int(game_state.bear_goal_reduction_steps or 0),
        "windfall_boss_victories": game_state.get_windfall_boss_victories(),
        "amplification_bonuses": dict(game_state.amplification_bonuses),
        "strategic_default_plays": game_state.strategic_default_plays,
        "overvaluation_multiplier": game_state.get_overvaluation_multiplier(),
        "risk_premium_h_rounds": game_state.get_risk_premium_h_rounds(),
        "golden_stake_shareholder_parity": game_state.get_golden_stake_shareholder_parity(),
        "bankruptcy_condition_chance": game_state.bankruptcy_condition_chance,
        "insurance_goal_debt": game_state.get_insurance_goal_debt(),
        "Frugality": max(0, int(game_state.Frugality or 0)),
        "guaranteed_start_hand_cards_by_level": _serialize_int_key_lists(
            game_state.guaranteed_start_hand_cards_by_level
        ),
        "active_red_cards_level": game_state.active_red_cards_level,
        "active_red_cards_deck": list(game_state.active_red_cards_deck or []),
        "active_silver_cards_level": game_state.active_silver_cards_level,
        "active_silver_cards_deck": list(game_state.active_silver_cards_deck or []),
    }


def _serialize_int_key_lists(source):
    result = {}
    for key, value in (source or {}).items():
        try:
            result[str(int(key))] = list(value or [])
        except (TypeError, ValueError):
            continue
    return result


def _serialize_int_list(source):
    result = []
    for value in source or []:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _restore_int_list(source):
    return _serialize_int_list(source)


def _serialize_lifecycle_card_order(source):
    result = []
    for entry in source or []:
        if isinstance(entry, dict):
            kind = entry.get("kind")
            card_id = entry.get("card_id", entry.get("id"))
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            kind, card_id = entry[0], entry[1]
        else:
            continue
        kind = str(kind or "").lower()
        if kind not in ("black", "gold"):
            continue
        try:
            result.append({"kind": kind, "card_id": int(card_id)})
        except (TypeError, ValueError):
            continue
    return result


def _serialize_int_value_dict(source):
    result = {}
    for key, value in (source or {}).items():
        try:
            result[str(int(key))] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def _restore_int_value_dict(source):
    result = {}
    for key, value in (source or {}).items():
        try:
            result[int(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def _migrate_silver_cards_from_earned_rewards():
    migrated = []
    for level, cards in list((game_state.earned_reward_cards or {}).items()):
        kept_cards = []
        for card_id in cards or []:
            if game_state.is_silver_card(card_id):
                migrated.append(int(card_id))
            else:
                kept_cards.append(card_id)
        game_state.earned_reward_cards[level] = kept_cards

    for card_id in migrated:
        if len(game_state.silver_cards) >= game_state.MAX_SILVER_CARDS:
            break
        game_state.silver_cards.append(card_id)


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
            "run_stats_started": bool(state.get("run_stats_started", False)),
            "shop_history": copy.deepcopy((state.get("shop_history") or [])[-3:]),
            "shop_visit": copy.deepcopy(state.get("shop_visit")),
            "run_stats_finished": bool(state.get("run_stats_finished", False)),
            "market_roll_stats": copy.deepcopy(state.get("market_roll_stats")),
            "other_stats": copy.deepcopy(state.get("other_stats")),
            "play_time": copy.deepcopy(state.get("play_time")),
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
            "run_stats_started": bool(state.get("run_stats_started", False)),
            "shop_history": copy.deepcopy((state.get("shop_history") or [])[-3:]),
            "shop_visit": copy.deepcopy(state.get("shop_visit")),
            "run_stats_finished": bool(state.get("run_stats_finished", False)),
            "market_roll_stats": copy.deepcopy(state.get("market_roll_stats")),
            "other_stats": copy.deepcopy(state.get("other_stats")),
            "play_time": copy.deepcopy(state.get("play_time")),
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
            if str(round_num).isdecimal() and selection_key in ("e", "m", "h"):
                selections[int(round_num)] = {"key": selection_key}
        result[str(key)] = {
            "completed_rounds": [
                int(round_num)
                for round_num in (progress.get("completed_rounds") or [])
                if str(round_num).isdecimal()
            ],
            "round_selections": selections,
            "saved_lines": [
                tuple(line)
                for line in (progress.get("saved_lines") or [])
                if isinstance(line, (list, tuple)) and len(line) == 4
            ],
        }
    return result
