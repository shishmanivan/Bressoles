import copy
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import game_state
import profile_manager
from boss_logic import LEVEL_BOSS_ROUNDS
from boss_progress import complete_boss_position, remember_current_boss
from game_data import load_language
from game_state import new_boss_progress_state
from gameplay_page import GameplayPage


class BossVictoryProgressTests(unittest.TestCase):
    def _build_state_and_context(self):
        context = {
            "defeated_count": 0,
            "boss_index": 1,
            "boss_filename": "3_RobertFulton.png",
            "clicked_boss_filename": "3_RobertFulton.png",
            "clicked_boss_rect": [420, 260, 100, 100],
            "saved_lines": [(100, 100, 420, 260)],
        }
        state = new_boss_progress_state()
        state["round_progress"]["0:1:3_RobertFulton.png"] = {
            "completed_rounds": [1, 2],
            "round_selections": {1: {"key": "e"}, 2: {"key": "m"}},
            "saved_lines": [],
        }
        state["current_boss"] = dict(context)
        return state, context

    def test_live_and_resumed_victories_produce_the_same_map_state(self):
        live_state, context = self._build_state_and_context()
        resumed_state = copy.deepcopy(live_state)
        boss_page = SimpleNamespace(
            clicked_boss_filename="3_RobertFulton.png",
            clicked_boss_rect=pygame.Rect(420, 260, 100, 100),
            saved_lines=[(100, 100, 420, 260)],
        )

        complete_boss_position(live_state, context, boss_page=boss_page)
        complete_boss_position(resumed_state, context)

        self.assertEqual(
            profile_manager._serialize_boss_progress({2: live_state}),
            profile_manager._serialize_boss_progress({2: resumed_state}),
        )
        self.assertEqual(resumed_state["defeated"], 1)
        self.assertEqual(resumed_state["last_rect"], pygame.Rect(420, 260, 100, 100))
        self.assertEqual(resumed_state["lines"], [(100, 100, 420, 260)])
        self.assertEqual(
            resumed_state["defeated_bosses"],
            [{"filename": "3_RobertFulton.png", "rect": pygame.Rect(420, 260, 100, 100)}],
        )
        self.assertEqual(resumed_state["round_progress"], {})
        self.assertIsNone(resumed_state["current_boss"])

    def test_repeated_transition_does_not_duplicate_progress(self):
        state, context = self._build_state_and_context()

        complete_boss_position(state, context)
        complete_boss_position(state, context)

        self.assertEqual(state["defeated"], 1)
        self.assertEqual(len(state["defeated_bosses"]), 1)

    def test_resumed_round_completion_preserves_active_boss_map_metadata(self):
        state, context = self._build_state_and_context()

        remembered = remember_current_boss(
            state,
            context["defeated_count"],
            context["boss_index"],
            context["boss_filename"],
        )
        complete_boss_position(state, remembered)

        self.assertEqual(state["defeated"], 1)
        self.assertEqual(state["last_rect"], pygame.Rect(420, 260, 100, 100))
        self.assertEqual(state["lines"], [(100, 100, 420, 260)])
        self.assertEqual(
            state["defeated_bosses"],
            [{"filename": "3_RobertFulton.png", "rect": pygame.Rect(420, 260, 100, 100)}],
        )

    def test_legacy_partial_encounter_recovers_missing_boss_geometry(self):
        state = new_boss_progress_state()
        state["current_boss"] = {
            "defeated_count": 0,
            "boss_index": 1,
            "boss_filename": "3_RobertFulton.png",
            "clicked_boss_filename": "3_RobertFulton.png",
            "clicked_boss_rect": None,
            "saved_lines": [],
        }

        remembered = remember_current_boss(state, 0, 1, "3_RobertFulton.png")
        complete_boss_position(state, remembered)

        self.assertEqual(state["last_rect"], pygame.Rect(350, 500, 100, 100))
        self.assertEqual(state["lines"], [(235, 832, 400, 550)])
        self.assertEqual(
            state["defeated_bosses"],
            [{"filename": "3_RobertFulton.png", "rect": pygame.Rect(350, 500, 100, 100)}],
        )

    def test_resumed_boss_victory_advances_category_and_deck_reward_marker(self):
        original_progress = game_state.boss_progress
        original_rewards = game_state.earned_reward_cards
        self.addCleanup(setattr, game_state, "boss_progress", original_progress)
        self.addCleanup(setattr, game_state, "earned_reward_cards", original_rewards)
        state, context = self._build_state_and_context()
        game_state.boss_progress = {2: state}
        game_state.earned_reward_cards = {2: [11]}

        remembered = remember_current_boss(
            state,
            context["defeated_count"],
            context["boss_index"],
            context["boss_filename"],
        )
        complete_boss_position(state, remembered)

        self.assertEqual(state["defeated"], 1)
        self.assertEqual(
            LEVEL_BOSS_ROUNDS[2][state["defeated"]],
            ["4_NicolasApper.png", "5_SamuelSlater.png"],
        )
        self.assertEqual(game_state.earned_reward_cards[2], [11])

        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 2
        page.lang_dict = load_language("RU")
        entries = page._collect_defeated_boss_rewards()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["filename"], "3_RobertFulton.png")
        self.assertEqual(entries[0]["boss_number"], 3)
        self.assertEqual(entries[0]["reward_text"], page.lang_dict["Boss3Reward"])


if __name__ == "__main__":
    unittest.main()
