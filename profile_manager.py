import json
import math
import os
import shutil
import tempfile

import pygame

import game_state
from gameplay_deck import restore_card_instance, serialize_card_instance


PROFILES_DIR = "Profiles"
INDEX_FILE = os.path.join(PROFILES_DIR, "index.json")
MAX_PROFILES = 4
_recovered_profile_paths = set()


class ProfileLoadError(OSError):
    """An existing profile cannot safely be loaded or overwritten."""


def was_profile_recovered(slot):
    return os.path.abspath(get_profile_path(slot)) in _recovered_profile_paths


def _validate_profile_data(data):
    # Missing optional fields are supported for older saves. A missing progress
    # object is not an empty slot: only a missing file represents a new profile.
    if not isinstance(data, dict) or not isinstance(data.get("progress"), dict):
        raise ValueError("profile must contain a progress object")
    if "name" in data and not isinstance(data["name"], str):
        raise ValueError("profile name must be text")
    progress = data["progress"]
    for field, default in _empty_progress().items():
        if field not in progress:
            continue
        value = progress[field]
        if isinstance(default, (dict, list)) and value is not None and not isinstance(value, type(default)):
            raise ValueError(f"progress.{field} has an invalid container type")
        if type(default) in (int, float) and value is not None:
            # Numeric strings in legacy profiles are still accepted.
            try:
                numeric = type(default)(value)
                if not math.isfinite(numeric):
                    raise ValueError("non-finite number")
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(f"progress.{field} must be numeric") from error
    for state in (progress.get("boss_progress") or {}).values():
        if not isinstance(state, dict):
            raise ValueError("boss progress entries must be objects")
        defeated_bosses = state.get("defeated_bosses") or []
        if not isinstance(defeated_bosses, list) or any(not isinstance(boss, dict) for boss in defeated_bosses):
            raise ValueError("defeated bosses must be a list of objects")
        rounds = state.get("round_progress") or {}
        if not isinstance(rounds, dict) or any(not isinstance(round_state, dict) for round_state in rounds.values()):
            raise ValueError("round progress entries must be objects")
    active_game = data.get("active_game")
    if active_game is not None:
        if not isinstance(active_game, dict):
            raise ValueError("active_game must be an object or null")
        for field in ("context", "state"):
            if not isinstance(active_game.get(field), dict):
                raise ValueError(f"active_game.{field} must be an object")
    if data.get("_load_error"):
        raise ValueError("unavailable profile cannot be saved")


def _read_profile_data(path):
    def reject_nonfinite(value):
        raise ValueError(f"non-finite JSON number: {value}")

    with open(path, "r", encoding="utf-8") as source:
        data = json.load(source, parse_constant=reject_nonfinite)
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


def _load_profile_data_with_recovery(path):
    missing = False
    try:
        return _read_profile_data(path)
    except FileNotFoundError:
        missing = True
    except (ValueError, UnicodeError):
        pass
    except OSError as error:
        # Access errors are not evidence of corruption. Never replace that file.
        raise ProfileLoadError(f"Cannot read profile: {path}") from error

    try:
        backup = _read_profile_data(path + ".bak")
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
    os.makedirs(PROFILES_DIR, exist_ok=True)


def _write_json_atomically(path, data):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output_file:
            json.dump(data, output_file, ensure_ascii=False, indent=2, allow_nan=False)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise


def get_profile_path(slot):
    return os.path.join(PROFILES_DIR, f"profile_{int(slot)}.json")


def get_stats_file(slot):
    ensure_profiles_dir()
    return os.path.join(PROFILES_DIR, f"GameStats_profile_{int(slot)}.csv")


def get_level6_experiment_stats_file(slot):
    ensure_profiles_dir()
    return os.path.join(PROFILES_DIR, f"Level6ExperimentStats_profile_{int(slot)}.csv")


def get_shop_card_stats_file(slot):
    ensure_profiles_dir()
    return os.path.join(PROFILES_DIR, f"ShopCardStats_profile_{int(slot)}.csv")


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
    _write_json_atomically(INDEX_FILE, index_data)


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
        "version": 2,
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
        "boss_lifecycle_slot_bonus": 0,
        "boss_shop_offer_bonus": 0,
        "boss_rare_card_pool_bonus_percent": 0,
        "deal_flow_bonus_percent": 0,
        "bank_bought": False,
        "bank_interest_base": None,
        "multibagger_bought": False,
        "diversification_bought": False,
        "expansion_bought": False,
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
        "bailout_rounds_remaining": 0,
        "disclosure_rounds_remaining": 0,
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
        "risk_premium_h_rounds": 0,
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


def load_profile(slot):
    ensure_profiles_dir()
    slot = int(slot)
    path = get_profile_path(slot)
    data = _load_profile_data_with_recovery(path)
    if data is None:
        return _default_profile(slot)
    profile = _default_profile(slot)
    profile.update(data)
    profile["slot"] = slot
    profile["version"] = data.get("version", 1)
    profile.setdefault("active_game", None)
    migrated = _migrate_campaign_v2(profile)
    if _migrate_completed_black_rewards(profile):
        migrated = True
    if migrated:
        save_profile(profile)
    return profile


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
            if normalized in black_cards or len(black_cards) >= game_state.MAX_BLACK_CARDS:
                continue
            black_cards.append(normalized)
            added.append(normalized)

    if not added:
        return False
    progress["black_cards"] = sorted(black_cards)
    return True


def save_profile(profile):
    ensure_profiles_dir()
    slot = int(profile.get("slot") or 1)
    profile["slot"] = slot
    _validate_profile_data(profile)
    path = get_profile_path(slot)
    try:
        previous = _read_profile_data(path)
    except FileNotFoundError:
        if os.path.exists(path + ".bak"):
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
            profiles.append(unavailable)
    return profiles


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


def apply_profile_to_game_state(profile_or_slot):
    profile = load_profile(profile_or_slot) if isinstance(profile_or_slot, int) else profile_or_slot
    _migrate_completed_black_rewards(profile)
    progress = profile.get("progress") or {}

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
        game_state.windfall_boss_victories = max(
            0,
            int(progress.get("windfall_boss_victories", 0) or 0),
        )
    except (TypeError, ValueError):
        game_state.windfall_boss_victories = 0
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
        "boss_lifecycle_slot_bonus": max(0, int(game_state.boss_lifecycle_slot_bonus or 0)),
        "boss_shop_offer_bonus": game_state.get_boss_shop_offer_bonus(),
        "boss_rare_card_pool_bonus_percent": game_state.get_boss_rare_card_pool_bonus(),
        "deal_flow_bonus_percent": game_state.get_deal_flow_bonus(),
        "bank_bought": bool(game_state.bank_bought),
        "bank_interest_base": game_state.bank_interest_base,
        "multibagger_bought": bool(game_state.multibagger_bought),
        "diversification_bought": bool(game_state.diversification_bought),
        "expansion_bought": bool(game_state.expansion_bought),
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
        "bailout_rounds_remaining": game_state.get_bailout_rounds_remaining(),
        "disclosure_rounds_remaining": game_state.get_disclosure_rounds_remaining(),
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
        "risk_premium_h_rounds": game_state.get_risk_premium_h_rounds(),
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
            "run_stats_finished": bool(state.get("run_stats_finished", False)),
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
            "run_stats_finished": bool(state.get("run_stats_finished", False)),
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
