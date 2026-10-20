"""Other report statistics: only ordinary cards committed with End count."""
from copy import deepcopy
from uuid import uuid4

import game_state
import profile_manager
from player_other_stats import empty_stats, record


class OtherStatsMixin:
    def _init_other_stats(self):
        slot = getattr(self, "profile_slot", None)
        profile = profile_manager.load_profile(slot) if slot and not self.test_mode else {}
        self.other_stats_enabled = profile.get("other_stats") is not None
        self.other_stats_lifecycle_enabled = profile.get("lifecycle_card_stats") is not None
        self.other_stats_lifecycle_committed = False
        self.other_stats_round_id = uuid4().hex
        self.other_stats_cards = 0
        self.other_stats_committed_day = None
        self.other_stats_finished = False
        self.other_stats_run = (
            deepcopy(game_state.boss_progress.get(self.level_number, {}).get("other_stats"))
            or empty_stats()) if self.other_stats_enabled else None
        self.other_stats_lifetime = deepcopy(profile.get("other_stats"))

    def _commit_other_stats_cards(self):
        self._commit_lifecycle_card_stats()
        if not getattr(self, "other_stats_enabled", False) or self.test_mode:
            return
        if self.other_stats_committed_day == self.Day:
            return
        cards = []
        for market, slots in self.market_cards.items():
            cards.extend(card for slot, card in slots.items()
                         if card is not None and not self.market_cards_locked.get(market, {}).get(slot))
        cards.extend(card for slot, card in enumerate(self.side_cards_top)
                     if card is not None and not self.side_cards_locked_top.get(slot))
        self.other_stats_cards += sum(0 < int(card) < 200 for card in cards)
        self.other_stats_committed_day = self.Day
        self._persist_other_stats()

    def _commit_lifecycle_card_stats(self):
        if (not getattr(self, "other_stats_lifecycle_enabled", False)
                or self.test_mode or self.other_stats_lifecycle_committed):
            return
        cards = [card for field in ("active_silver_cards", "active_gold_cards", "active_black_cards")
                 for card in (getattr(self, field, None) or [])]
        profile_manager.record_player_lifecycle_cards(
            self.profile_slot, self.other_stats_round_id, cards, test_mode=self.test_mode)
        self.other_stats_lifecycle_committed = True

    def _persist_other_stats(self, earned=None):
        label = {"level": self.level_number, "round": self.round_num,
                 "boss": bool(self.is_boss_fight), "boss_number": self._get_active_boss_number()}
        record(self.other_stats_run, self.other_stats_round_id, self.other_stats_cards,
               earned=earned, label=label)
        progress = game_state.boss_progress.setdefault(self.level_number, game_state.new_boss_progress_state())
        progress["other_stats"] = deepcopy(self.other_stats_run)
        self.other_stats_lifetime = profile_manager.record_player_other_stats(
            self.profile_slot, self.other_stats_round_id, self.other_stats_cards,
            earned=earned, label=label)

    def _finish_other_stats(self):
        if not getattr(self, "other_stats_enabled", False) or self.test_mode or self.other_stats_finished:
            return
        # A portfolio with unsold shares is not a cash result, even on victory.
        earned = float(self.Money) if not any(
            (self.Aquantity, self.Bquantity, self.Cquantity)) else None
        self._persist_other_stats(earned)
        self.other_stats_finished = True

    def _serialize_other_stats(self):
        return deepcopy({key: value for key, value in self.__dict__.items()
                         if key.startswith("other_stats_")})

    def _restore_other_stats(self, state):
        saved = state.get("other_stats")
        if isinstance(saved, dict):
            for key in tuple(self.__dict__):
                if key.startswith("other_stats_") and key in saved:
                    setattr(self, key, deepcopy(saved[key]))
        else:
            self.other_stats_enabled = False
            self.other_stats_lifecycle_enabled = False
            self.other_stats_run = None
            self.other_stats_lifetime = None
