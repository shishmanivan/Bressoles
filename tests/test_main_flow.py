import os
import copy
import tempfile
import unittest
from collections import deque
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import Main
import game_state
import profile_manager


class MainFlowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_dir_patch = patch.object(profile_manager, "PROFILES_DIR", self.temp_dir.name)
        self.index_file_patch = patch.object(
            profile_manager,
            "INDEX_FILE",
            os.path.join(self.temp_dir.name, "index.json"),
        )
        self.profile_dir_patch.start()
        self.index_file_patch.start()

        profile_manager.select_profile(1, "Integration")
        self.common_patches = [
            patch.object(Main, "create_game_display", return_value=object()),
            patch.object(Main, "load_main_background", return_value=object()),
            patch.object(Main, "find_font_path_or_exit", return_value="unused.ttf"),
            patch.object(Main, "load_language", return_value={}),
            patch.object(Main, "validate_levels_and_rounds_config"),
            patch.object(Main, "assert_valid_game_content"),
            patch.object(Main.pygame.display, "set_caption"),
            patch.object(Main.pygame, "quit"),
            patch.object(Main.sys, "exit"),
            patch.object(Main, "set_stats_file"),
            patch.object(Main, "set_shop_card_stats_file"),
            patch.object(Main, "update_level_run_started"),
            patch.object(Main, "update_level_run_result"),
            patch.object(Main, "update_level_run_loss_stage_stats"),
            patch.object(Main, "update_level_boss_position_stats"),
        ]
        for patcher in self.common_patches:
            patcher.start()

    def tearDown(self):
        profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
        for patcher in reversed(self.common_patches):
            patcher.stop()
        self.index_file_patch.stop()
        self.profile_dir_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def _sequenced_page(results, instances=None):
        queue = deque(results)

        class SequencedPage:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs
                if instances is not None:
                    instances.append(self)

            def run(self):
                return queue.popleft()

        return SequencedPage

    def test_level_one_victory_completes_route_and_unlocks_level_two(self):
        gameplay_instances = []
        round_results = deque(["button_e", "boss_clicked"])

        class FakeBossPage:
            def __init__(self, *args, **kwargs):
                self.current_boss_filenames = ["1_Watt.png"]
                self.clicked_boss_filename = "1_Watt.png"
                self.clicked_boss_rect = pygame.Rect(300, 200, 100, 100)
                self.saved_lines = [(100, 100, 300, 200)]

            def run(self):
                return "boss_1_0"

        class FakeRoundPage:
            def __init__(self, *args, **kwargs):
                self.Goal = 10
                self.rounds_required = 1
                self.last_selected_round = None
                self.completed_rounds = []
                self.round_selections = {}

            def run(self):
                result = round_results.popleft()
                if result == "button_e":
                    self.last_selected_round = 1
                    self.round_selections[1] = {"key": "e"}
                return result

            def get_current_active_round(self):
                return 1 if 1 not in self.completed_rounds else None

            def mark_round_completed(self, round_num):
                if round_num not in self.completed_rounds:
                    self.completed_rounds.append(round_num)

            def export_round_progress(self):
                return {
                    "completed_rounds": list(self.completed_rounds),
                    "round_selections": dict(self.round_selections),
                    "saved_lines": [],
                }

        class FakeGameplayPage:
            def __init__(self, *args, **kwargs):
                self.is_boss_fight = bool(kwargs.get("is_boss_fight", False))
                gameplay_instances.append(self)

            def run(self):
                return "round_select"

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["level_1", "quit"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "BossPage", FakeBossPage),
            patch.object(Main, "RoundPage", FakeRoundPage),
            patch.object(Main, "GameplayPage", FakeGameplayPage),
        ):
            Main.main()

        self.assertEqual([page.is_boss_fight for page in gameplay_instances], [False, True])
        self.assertTrue(game_state.level_1_boss_defeated)
        self.assertEqual(game_state.boss_progress[1]["defeated"], 1)
        self.assertEqual(
            game_state.boss_progress[1]["defeated_bosses"][0]["filename"],
            "1_Watt.png",
        )
        profile = profile_manager.load_profile(1)
        self.assertTrue(profile["progress"]["level_1_boss_defeated"])
        self.assertIsNone(profile["active_game"])

    def test_options_page_saves_music_volume_and_returns_to_main_menu(self):
        settings_pages = []

        class FakeSettingsPage:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs
                settings_pages.append(self)

            def run(self):
                self.kwargs["on_volume_change"](0.35)
                return "back", 0.35

        start_page = self._sequenced_page(["options", "quit"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "SettingsPage", FakeSettingsPage),
            patch.object(Main, "save_music_volume") as save_volume,
        ):
            Main.main()

        self.assertEqual(len(settings_pages), 1)
        save_volume.assert_called_once_with(0.35)

    def test_level_six_shows_single_category_one_boss_before_round_page(self):
        roster = [
            ["4_NicolasApper.png"],
            ["2_AdamSmith.png"],
            ["8_List.png"],
            ["9_Laffitte.png"],
        ]
        boss_pages = []
        round_pages = []

        class SingleBossPage:
            def __init__(self, *args, **kwargs):
                self.level_number = int(args[2])
                self.current_boss_filenames = list(roster[int(kwargs.get("defeated_count", 0) or 0)])
                self.clicked_boss_filename = self.current_boss_filenames[0]
                self.clicked_boss_rect = pygame.Rect(300, 200, 100, 100)
                self.saved_lines = [(235, 832, 350, 250)]
                boss_pages.append(self)

            def run(self):
                return f"boss_{self.level_number}_0"

        class CapturingRoundPage:
            def __init__(self, *args, **kwargs):
                self.level_number = int(args[2])
                self.boss_index = int(args[3])
                self.boss_filename = kwargs.get("boss_filename")
                round_pages.append(self)

            def run(self):
                return "quit"

        def pin_level6(state, bosses_required):
            state["roster"] = copy.deepcopy(roster)
            return state["roster"]

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["level_6"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "BossPage", SingleBossPage),
            patch.object(Main, "RoundPage", CapturingRoundPage),
            patch.object(Main, "_ensure_level6_roster", side_effect=pin_level6),
        ):
            Main.main()

        self.assertEqual(len(boss_pages), 1)
        self.assertEqual(boss_pages[0].current_boss_filenames, ["4_NicolasApper.png"])
        self.assertEqual(len(round_pages), 1)
        self.assertEqual(round_pages[0].level_number, 6)
        self.assertEqual(round_pages[0].boss_index, 0)
        self.assertEqual(round_pages[0].boss_filename, "4_NicolasApper.png")
        self.assertEqual(game_state.boss_progress[6]["current_boss"]["boss_filename"], "4_NicolasApper.png")

    def test_level_six_first_boss_victory_returns_to_level_menu_and_resets_attempt(self):
        roster = [
            ["4_NicolasApper.png"],
            ["2_AdamSmith.png"],
            ["8_List.png"],
            ["9_Laffitte.png"],
        ]
        gameplay_contexts = []
        shop_visits = []

        class SingleBossPage:
            def __init__(self, *args, **kwargs):
                self.level_number = int(args[2])
                self.current_boss_filenames = list(roster[int(kwargs.get("defeated_count", 0) or 0)])
                self.clicked_boss_filename = self.current_boss_filenames[0]
                self.clicked_boss_rect = pygame.Rect(300, 200, 100, 100)
                self.saved_lines = [(235, 832, 350, 250)]

            def run(self):
                return f"boss_{self.level_number}_0"

        class FakeRoundPage:
            def __init__(self, *args, **kwargs):
                self.Goal = 10
                self.rounds_required = 3
                self.completed_rounds = set()
                self.round_selections = {}
                self.last_selected_round = None

            def get_current_active_round(self):
                for round_number in range(1, self.rounds_required + 1):
                    if round_number not in self.completed_rounds:
                        return round_number
                return None

            def run(self):
                round_number = self.get_current_active_round()
                if round_number is None:
                    return "boss_clicked"
                self.last_selected_round = round_number
                self.round_selections[round_number] = {"key": "e"}
                return "button_e"

            def mark_round_completed(self, round_number):
                self.completed_rounds.add(int(round_number))

            def export_round_progress(self):
                return {
                    "completed_rounds": sorted(self.completed_rounds),
                    "round_selections": dict(self.round_selections),
                    "saved_lines": [],
                }

        class WinningGameplayPage:
            def __init__(self, *args, **kwargs):
                gameplay_contexts.append(dict(kwargs))

            def run(self):
                return "round_select"

        class CountingShopPage:
            def __init__(self, *args, **kwargs):
                shop_visits.append(int(args[2]))

            def run(self):
                return "next"

        def pin_level6(state, bosses_required):
            state["roster"] = copy.deepcopy(roster)
            return state["roster"]

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["level_6", "quit"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "BossPage", SingleBossPage),
            patch.object(Main, "RoundPage", FakeRoundPage),
            patch.object(Main, "GameplayPage", WinningGameplayPage),
            patch.object(Main, "ShopPage", CountingShopPage),
            patch.object(Main, "_ensure_level6_roster", side_effect=pin_level6),
        ):
            Main.main()

        self.assertEqual(len(gameplay_contexts), 4)
        self.assertEqual(sum(bool(context.get("is_boss_fight")) for context in gameplay_contexts), 1)
        self.assertEqual(shop_visits, [6, 6, 6])
        self.assertEqual(game_state.boss_progress[6]["defeated"], 0)
        self.assertIsNone(game_state.boss_progress[6]["current_boss"])
        self.assertEqual(game_state.boss_progress[6]["round_progress"], {})
        self.assertIsNone(profile_manager.get_active_game(1))

    def test_levels_two_to_five_complete_every_campaign_position(self):
        campaigns = {
            2: {
                "roster": [
                    ["2_AdamSmith.png", "3_RobertFulton.png"],
                    ["4_NicolasApper.png", "5_SamuelSlater.png"],
                ],
                "choices": [1, 0],
                "rounds": [3, 2],
                "completion_card": 13,
            },
            3: {
                "roster": [
                    ["2_AdamSmith.png"],
                    ["5_SamuelSlater.png"],
                    ["6_Arkwright.png"],
                ],
                "choices": [0, 0, 0],
                "rounds": [3, 3, 3],
                "completion_card": 110,
            },
            4: {
                "roster": [
                    ["2_AdamSmith.png"],
                    ["5_SamuelSlater.png"],
                    ["6_Arkwright.png"],
                ],
                "choices": [0, 0, 0],
                "rounds": [3, 3, 3],
                "completion_card": None,
            },
            5: {
                "roster": [
                    ["7_Kolbe.png", "10_Stephenson.png"],
                    ["2_AdamSmith.png", "4_NicolasApper.png"],
                    ["8_List.png", "9_Laffitte.png"],
                    ["11_Malthus.png", "12_Ricardo.png"],
                ],
                "choices": [1, 1, 0, 1],
                "rounds": [3, 3, 3, 3],
                "completion_card": None,
            },
        }

        for level, campaign in campaigns.items():
            with self.subTest(level=level):
                profile = profile_manager._default_profile(1)
                profile["name"] = "Integration"
                profile_manager.save_profile(profile)
                profile_manager.apply_profile_to_game_state(profile)
                gameplay_contexts = []
                roster = copy.deepcopy(campaign["roster"])
                choices = list(campaign["choices"])

                class FakeBossPage:
                    def __init__(self, *args, **kwargs):
                        self.level_number = int(args[2])
                        self.defeated_count = int(kwargs.get("defeated_count", 0) or 0)
                        self.choice = choices[self.defeated_count]
                        self.current_boss_filenames = list(roster[self.defeated_count])
                        self.clicked_boss_filename = self.current_boss_filenames[self.choice]
                        self.clicked_boss_rect = pygame.Rect(
                            300 + self.defeated_count * 140,
                            700 - self.defeated_count * 120,
                            100,
                            100,
                        )
                        self.saved_lines = [
                            (235, 832, self.clicked_boss_rect.centerx, self.clicked_boss_rect.centery)
                        ]

                    def run(self):
                        return f"boss_{self.level_number}_{self.choice}"

                class FakeRoundPage:
                    def __init__(self, *args, **kwargs):
                        self.level_number = int(args[2])
                        self.boss_filename = kwargs.get("boss_filename")
                        self.rounds_required = {2: 2, 3: 3, 4: 3, 5: 3}[self.level_number]
                        if self.boss_filename == "3_RobertFulton.png":
                            self.rounds_required += 1
                        progress = kwargs.get("round_progress") or {}
                        self.completed_rounds = {
                            int(value) for value in (progress.get("completed_rounds") or [])
                        }
                        self.round_selections = dict(progress.get("round_selections") or {})
                        self.last_selected_round = None
                        self.Goal = 10

                    def get_current_active_round(self):
                        for round_number in range(1, self.rounds_required + 1):
                            if round_number not in self.completed_rounds:
                                return round_number
                        return None

                    def run(self):
                        round_number = self.get_current_active_round()
                        if round_number is None:
                            return "boss_clicked"
                        self.last_selected_round = round_number
                        self.round_selections[round_number] = {"key": "e"}
                        return "button_e"

                    def mark_round_completed(self, round_number):
                        self.completed_rounds.add(int(round_number))

                    def export_round_progress(self):
                        return {
                            "completed_rounds": sorted(self.completed_rounds),
                            "round_selections": dict(self.round_selections),
                            "saved_lines": [],
                        }

                class FakeGameplayPage:
                    def __init__(self, *args, **kwargs):
                        gameplay_contexts.append(dict(kwargs))

                    def run(self):
                        return "round_select"

                class FakeShopPage:
                    def __init__(self, *args, **kwargs):
                        pass

                    def run(self):
                        return "next"

                def pin_level3(state, bosses_required):
                    state["roster"] = copy.deepcopy(roster)
                    return state["roster"]

                def pin_level5(state, bosses_required):
                    state["roster"] = copy.deepcopy(roster)
                    return state["roster"]

                start_page = self._sequenced_page(["start"])
                level_page = self._sequenced_page([f"level_{level}", "quit"])
                with (
                    patch.dict(Main.LEVEL_BOSS_ROUNDS, {level: copy.deepcopy(roster)}, clear=False),
                    patch.object(Main, "StartPage", start_page),
                    patch.object(Main, "GameScreen", level_page),
                    patch.object(Main, "BossPage", FakeBossPage),
                    patch.object(Main, "RoundPage", FakeRoundPage),
                    patch.object(Main, "GameplayPage", FakeGameplayPage),
                    patch.object(Main, "ShopPage", FakeShopPage),
                    patch.object(Main, "_ensure_level3_roster", side_effect=pin_level3),
                    patch.object(Main, "_ensure_level5_roster", side_effect=pin_level5),
                ):
                    Main.main()

                selected_bosses = [
                    roster[position][choice]
                    for position, choice in enumerate(choices)
                ]
                boss_contexts = [context for context in gameplay_contexts if context.get("is_boss_fight")]
                regular_contexts = [context for context in gameplay_contexts if not context.get("is_boss_fight")]
                regular_counts = [
                    sum(context.get("boss_filename") == boss_filename for context in regular_contexts)
                    for boss_filename in selected_bosses
                ]

                self.assertEqual([context.get("boss_filename") for context in boss_contexts], selected_bosses)
                self.assertEqual(regular_counts, campaign["rounds"])
                self.assertEqual(game_state.boss_progress[level]["defeated"], len(roster))
                self.assertEqual(
                    [entry["filename"] for entry in game_state.boss_progress[level]["defeated_bosses"]],
                    selected_bosses,
                )
                if level in (2, 3, 4, 5):
                    self.assertTrue(getattr(game_state, f"level_{level}_boss_defeated"))
                if campaign["completion_card"] is not None:
                    self.assertIn(campaign["completion_card"], game_state.get_completed_level_reward_cards())
                self.assertIsNone(profile_manager.get_active_game(1))
                saved_progress = profile_manager.load_profile(1)["progress"]
                self.assertEqual(saved_progress["boss_progress"][str(level)]["defeated"], len(roster))
                if level in (2, 3, 4, 5):
                    self.assertTrue(saved_progress[f"level_{level}_boss_defeated"])

    def test_saved_regular_round_resumes_and_commits_map_progress(self):
        context = {
            "difficulty": "m",
            "goal": 80,
            "level_number": 1,
            "is_boss_fight": False,
            "boss_index": 0,
            "boss_filename": "1_Watt.png",
            "round_num": 1,
            "defeated_count": 0,
            "rounds_required": 1,
        }
        saved_state = {"Day": 5, "Money": 42, "hand_cards": [100, 11]}
        profile_manager.save_active_game(1, context, saved_state)
        gameplay_instances = []
        round_page_instances = []

        class FakeGameplayPage:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs
                gameplay_instances.append(self)

            def run(self):
                return "round_select"

        class FakeRoundPage:
            def __init__(self, *args, **kwargs):
                round_page_instances.append(self)

            def run(self):
                return "quit"

        start_page = self._sequenced_page(["start"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameplayPage", FakeGameplayPage),
            patch.object(Main, "RoundPage", FakeRoundPage),
        ):
            Main.main()

        self.assertEqual(len(gameplay_instances), 1)
        self.assertEqual(gameplay_instances[0].kwargs["saved_state"], saved_state)
        progress = game_state.boss_progress[1]["round_progress"]["0:0:1_Watt.png"]
        self.assertEqual(progress["completed_rounds"], [1])
        self.assertEqual(progress["round_selections"], {1: {"key": "m"}})
        self.assertIsNone(profile_manager.get_active_game(1))
        self.assertEqual(len(round_page_instances), 1)

    def test_resumed_loss_is_reset_once_by_the_main_flow(self):
        level = 2
        game_state.earned_reward_cards[level] = [112]
        game_state.round_reward_cards[level] = [11]
        game_state.shop_deck_cards[:] = [117]
        game_state.guaranteed_start_hand_cards_by_level[level] = [112]
        game_state.boss_progress[level] = game_state.new_boss_progress_state()
        profile_manager.save_progress_from_game_state(1)
        profile_manager.save_active_game(
            1,
            {
                "difficulty": "e",
                "goal": 100,
                "level_number": level,
                "is_boss_fight": False,
                "boss_index": 0,
                "boss_filename": "2_AdamSmith.png",
                "round_num": 1,
                "defeated_count": 0,
            },
            {"Day": 8, "Money": 0, "win_lose_state": "lose"},
        )

        losing_gameplay_page = self._sequenced_page(["level_select"])
        start_page = self._sequenced_page(["start", "quit"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameplayPage", losing_gameplay_page),
        ):
            Main.main()

        self.assertEqual(game_state.earned_reward_cards[level], [])
        self.assertNotIn(level, game_state.round_reward_cards)
        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertEqual(game_state.guaranteed_start_hand_cards_by_level[level], [])
        self.assertEqual(game_state.boss_progress[level]["defeated"], 0)
        self.assertIsNone(profile_manager.get_active_game(1))

    def test_insurance_debt_is_added_to_the_unmodified_next_round_goal(self):
        game_state.insurance_goal_debt = 25
        profile_manager.save_progress_from_game_state(1)
        gameplay_instances = []
        round_results = deque(["button_e", "quit"])

        class FakeBossPage:
            def __init__(self, *args, **kwargs):
                self.current_boss_filenames = ["1_Watt.png"]
                self.clicked_boss_filename = "1_Watt.png"
                self.clicked_boss_rect = pygame.Rect(300, 200, 100, 100)
                self.saved_lines = []

            def run(self):
                return "boss_1_0"

        class FakeRoundPage:
            def __init__(self, *args, **kwargs):
                self.Goal = 100
                self.rounds_required = 1
                self.last_selected_round = None

            def run(self):
                result = round_results.popleft()
                if result == "button_e":
                    self.last_selected_round = 1
                return result

            def get_current_active_round(self):
                return 1

        class ReturningGameplayPage:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs
                gameplay_instances.append(self)

            def run(self):
                return "back"

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["level_1"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "BossPage", FakeBossPage),
            patch.object(Main, "RoundPage", FakeRoundPage),
            patch.object(Main, "GameplayPage", ReturningGameplayPage),
        ):
            Main.main()

        self.assertEqual(len(gameplay_instances), 1)
        self.assertEqual(gameplay_instances[0].kwargs["goal"], 100)
        self.assertEqual(gameplay_instances[0].kwargs["insurance_goal_debt"], 25)
        self.assertEqual(game_state.get_insurance_goal_debt(), 25)

    def test_restart_from_saved_round_resets_attempt_and_reenters_same_level(self):
        game_state.round_reward_cards[1] = [11]
        game_state.shop_deck_cards[:] = [12]
        game_state.gold_cards[:] = [201]
        game_state.boss_progress[1] = game_state.new_boss_progress_state()
        game_state.boss_progress[1]["round_progress"] = {
            "0:0:1_Watt.png": {
                "completed_rounds": [1],
                "round_selections": {1: {"key": "e"}},
                "saved_lines": [],
            }
        }
        context = {
            "difficulty": "e",
            "goal": 50,
            "level_number": 1,
            "is_boss_fight": False,
            "boss_index": 0,
            "boss_filename": "1_Watt.png",
            "round_num": 1,
            "defeated_count": 0,
        }
        profile_manager.save_active_game(1, context, {"Day": 4, "Money": 12})
        level_page_instances = []

        class RestartingGameplayPage:
            def __init__(self, *args, **kwargs):
                pass

            def run(self):
                return "restart_level"

        class QuittingBossPage:
            def __init__(self, *args, **kwargs):
                pass

            def run(self):
                return "quit"

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["quit"], instances=level_page_instances)
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "GameplayPage", RestartingGameplayPage),
            patch.object(Main, "BossPage", QuittingBossPage),
        ):
            Main.main()

        self.assertEqual(level_page_instances, [])
        self.assertEqual(game_state.boss_progress[1]["defeated"], 0)
        self.assertEqual(game_state.boss_progress[1]["round_progress"], {})
        self.assertEqual(game_state.round_reward_cards.get(1, []), [])
        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertEqual(game_state.gold_cards, [])
        self.assertIsNone(profile_manager.get_active_game(1))


if __name__ == "__main__":
    unittest.main()
