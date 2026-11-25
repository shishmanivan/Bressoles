import os
import copy
import json
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
    @classmethod
    def setUpClass(cls):
        if not pygame.display.get_init():
            pygame.display.init()
            cls.addClassCleanup(pygame.display.quit)

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
            patch.object(Main, "assert_valid_game_content"),
            patch.object(Main.pygame.display, "set_caption"),
            patch.object(Main.pygame, "quit"),
            patch.object(Main.sys, "exit"),
            patch.object(Main, "set_stats_file"),
            patch.object(Main, "set_shop_card_stats_file"),
            patch.object(Main, "configure_card_acquisition_stats"),
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

    def test_unrecoverable_selected_profile_opens_profile_page_without_overwriting(self):
        path = profile_manager.get_profile_path(1)
        for target in (path, path + ".bak"):
            with open(target, "wb") as output:
                output.write(b"broken")
        profile_pages, start_pages = [], []
        with (
            patch.object(Main, "ProfilePage", self._sequenced_page(["back"], profile_pages)),
            patch.object(Main, "StartPage", self._sequenced_page(["quit"], start_pages)),
        ):
            Main.main()
        self.assertEqual(len(profile_pages), 1)
        self.assertIsNone(start_pages[0].kwargs["profile_name"])
        with open(path, "rb") as source:
            self.assertEqual(source.read(), b"broken")

    def test_recovered_selected_profile_shows_notice_before_main_menu(self):
        path = profile_manager.get_profile_path(1)
        damaged = profile_manager.load_profile(1)
        damaged["progress"]["seen_gold_card_ids"] = None
        with open(path, "w", encoding="utf-8") as output:
            json.dump(damaged, output)
        profile_pages, start_pages = [], []
        with (
            patch.object(Main.pygame.display, "get_driver", return_value="dummy"),
            patch.object(Main, "ProfilePage", self._sequenced_page(["back"], profile_pages)),
            patch.object(Main, "StartPage", self._sequenced_page(["quit"], start_pages)),
        ):
            Main.main()
        self.assertEqual(len(profile_pages), 1)
        self.assertEqual(start_pages[0].kwargs["profile_name"], "Integration")
        self.assertTrue(profile_manager.was_profile_recovered(1))
        self.assertEqual(profile_manager.load_profile(1)["name"], "Integration")

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

    def test_balance_rollback_reopens_level_selector_with_restored_flags(self):
        profile_manager.capture_balance_checkpoint(1, 1)
        game_state.level_1_boss_defeated = True
        profile_manager.save_progress_from_game_state(1)
        pages = []
        with (
            patch.object(Main, "StartPage", self._sequenced_page(["start"])),
            patch.object(Main, "GameScreen", self._sequenced_page(["balance_rollback", "quit"], pages)),
        ):
            Main.main()
        self.assertEqual(pages[0].kwargs["balance_replay_level"], 1)
        self.assertTrue(pages[0].kwargs["progress_flags"]["level_1_boss_defeated"])
        self.assertFalse(pages[1].kwargs["progress_flags"]["level_1_boss_defeated"])
        self.assertFalse(profile_manager.load_profile(1)["progress"]["level_1_boss_defeated"])

    def test_options_page_owns_saving_and_returns_to_main_menu(self):
        settings_pages = []

        class FakeSettingsPage:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs
                self.screen = args[0]
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
        save_volume.assert_not_called()

    def test_level_six_finishes_only_after_four_bosses(self):
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

        def pin_level6(level, state, bosses_required):
            state["roster"] = copy.deepcopy(roster)
            return state["roster"]

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["level_6", "quit"])
        with (
            patch.object(Main.pygame.display, "get_driver", return_value="dummy"),
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "BossPage", SingleBossPage),
            patch.object(Main, "RoundPage", FakeRoundPage),
            patch.object(Main, "GameplayPage", WinningGameplayPage),
            patch.object(Main, "ShopPage", CountingShopPage),
            patch.object(Main, "get_level_boss_roster", side_effect=pin_level6),
        ):
            Main.main()

        self.assertEqual(len(gameplay_contexts), 16)
        bosses = [context for context in gameplay_contexts if context.get("is_boss_fight")]
        self.assertEqual([context["boss_filename"] for context in bosses], [row[0] for row in roster])
        self.assertEqual([context["defeated_count"] for context in bosses], [0, 1, 2, 3])
        from boss_logic import get_boss_level_from_number
        self.assertEqual([
            get_boss_level_from_number(Main.get_boss_number_from_filename(context["boss_filename"]),
                                       level_number=context["level_number"], defeated_count=context["defeated_count"])
            for context in bosses
        ], [1, 1, 2, 2])
        self.assertEqual(shop_visits, [6] * 15)
        profile_manager.apply_profile_to_game_state(1)
        self.assertTrue(game_state.get_progress_flags()["level_7_unlocked"])
        self.assertEqual(game_state.get_shop_rerolls(), 5)
        self.assertEqual(game_state.boss_progress[6]["defeated"], 4)
        self.assertIsNone(game_state.boss_progress[6]["current_boss"])
        self.assertIsNone(profile_manager.get_active_game(1))

    def test_saved_level_six_final_boss_grants_permanent_rewards_once(self):
        game_state.boss_progress[6] = game_state.new_boss_progress_state()
        game_state.boss_progress[6].update(defeated=3, run_stats_started=True)
        game_state.shop_rerolls = 2
        game_state.level_5_boss_defeated = True
        game_state.level_6_boss_defeated = False
        before_slots = game_state.get_lifecycle_card_slot_limit()
        before_money = game_state.get_starting_napoleondors_for_level(7)
        profile_manager.save_active_game(1, {
            "level_number": 6, "is_boss_fight": True, "boss_index": 0, "defeated_count": 3,
            "boss_filename": "9_Laffitte.png",
        }, {"Day": 3})
        with (
            patch.object(Main.pygame.display, "get_driver", return_value="dummy"),
            patch.object(Main, "StartPage", self._sequenced_page(["start", "quit"])),
            patch.object(Main, "GameplayPage", self._sequenced_page(["round_select"])),
            patch.object(Main, "ShopPage", self._sequenced_page([])),
        ):
            Main.main()
        profile_manager.apply_profile_to_game_state(1)
        self.assertIsNone(profile_manager.get_active_game(1))
        self.assertEqual(game_state.boss_progress[6]["defeated"], 4)
        self.assertTrue(game_state.get_progress_flags()["level_7_unlocked"])
        self.assertEqual(game_state.get_shop_rerolls(), 7)
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), before_slots)
        self.assertEqual(game_state.get_silver_only_slot_count(), 1)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(7), before_money + 2)
        self.assertTrue(game_state.is_level_unlocked(7))
        self.assertEqual(game_state.build_current_level_deck(7).count(113), 1)
        game_state.reset_level_attempt(7)
        self.assertEqual(game_state.build_current_level_deck(7).count(113), 1)
        game_state.unlock_level_seven()
        self.assertEqual(game_state.get_shop_rerolls(), 7)

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
                    ["16_Whitney.png", "10_Stephenson.png"],
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
                content_level = level
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

                def pin_roster(level, state, bosses_required):
                    state["roster"] = copy.deepcopy(roster)
                    return state["roster"]

                start_page = self._sequenced_page(["start"])
                level_page = self._sequenced_page([f"level_{level}", "quit"])
                with (
                    patch.dict(Main.LEVEL_BOSS_ROUNDS, {content_level: copy.deepcopy(roster)}, clear=False),
                    patch.object(Main, "StartPage", start_page),
                    patch.object(Main, "GameScreen", level_page),
                    patch.object(Main, "BossPage", FakeBossPage),
                    patch.object(Main, "RoundPage", FakeRoundPage),
                    patch.object(Main, "GameplayPage", FakeGameplayPage),
                    patch.object(Main, "ShopPage", FakeShopPage),
                    patch.object(Main, "get_level_boss_roster", side_effect=pin_roster),
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
                self.assertEqual(game_state.boss_progress[content_level]["defeated"], len(roster))
                self.assertEqual(
                    [entry["filename"] for entry in game_state.boss_progress[content_level]["defeated_bosses"]],
                    selected_bosses,
                )
                self.assertTrue(getattr(game_state, f"level_{content_level}_boss_defeated"))
                if campaign["completion_card"] is not None:
                    self.assertIn(campaign["completion_card"], game_state.get_completed_level_reward_cards())
                self.assertIsNone(profile_manager.get_active_game(1))
                saved_progress = profile_manager.load_profile(1)["progress"]
                self.assertEqual(saved_progress["boss_progress"][str(content_level)]["defeated"], len(roster))
                self.assertTrue(saved_progress[f"level_{content_level}_boss_defeated"])

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

    def _check_regular_round_victory(self, level, resumed=False, test_mode=False):
        profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
        context = {
            "level_number": level, "difficulty": "h", "round_num": 1,
            "boss_index": 0, "boss_filename": "1_Watt.png", "defeated_count": 0,
        }
        progress_key = "0:0:1_Watt.png"
        game_state.ensure_napoleondor_level(level)
        game_state.boss_progress[level] = game_state.new_boss_progress_state()
        game_state.boss_progress[level]["run_stats_started"] = True
        game_state.boss_progress[level]["round_progress"][progress_key] = {
            "completed_rounds": [], "round_selections": {1: {"key": "h"}},
            "saved_lines": [[1, 2, 3, 4]],
        }
        game_state.boss_progress[level]["current_boss"] = {
            "defeated_count": 0, "boss_index": 0, "boss_filename": "1_Watt.png",
        }
        profile_manager.save_progress_from_game_state(1)
        if resumed:
            profile_manager.save_active_game(1, context, {"Day": 2})
        profile_before = profile_manager.load_profile(1)
        events = []
        recording = False
        round_results = deque(["quit"] if resumed else ["button_h", "quit"])
        test = self

        class FakeRoundPage:
            Goal = 10
            rounds_required = 2
            last_selected_round = 1

            def __init__(self, *args, **kwargs):
                self.progress = copy.deepcopy(kwargs.get("round_progress") or {
                    "completed_rounds": [], "round_selections": {1: {"key": "h"}},
                    "saved_lines": [[1, 2, 3, 4]],
                })

            def run(self):
                nonlocal recording
                result = round_results.popleft()
                if result == "quit":
                    events.append("round_page")
                    recording = False
                    test.assertEqual(self.progress["completed_rounds"], [1])
                return result

            def get_current_active_round(self):
                return 1

            def mark_round_completed(self, round_num):
                self.progress["completed_rounds"].append(round_num)

            def export_round_progress(self):
                return copy.deepcopy(self.progress)

        class FakeGameplayPage:
            def __init__(self, *args, **kwargs):
                pass

            def run(self):
                nonlocal recording
                if not resumed and not test_mode:
                    profile_manager.save_active_game(1, context, {"Day": 2})
                game_state.profit_reward_bonus = 2
                game_state.set_pending_shop_discount(25)
                recording = True
                return "round_select"

        class FakeShopPage:
            def __init__(self, *args, **kwargs):
                test.assertEqual(kwargs["discount_percent"], 25)
                test.assertEqual(kwargs["stats_enabled"], not test_mode)
                if not test_mode:
                    saved = profile_manager.load_profile(1)
                    test.assertIsNone(saved["active_game"])
                    test.assertEqual(saved["progress"]["napoleondors"], game_state.napoleondors)
                    test.assertEqual(saved["progress"]["boss_progress"][str(level)]["shop_visit"],
                                     {"discount_percent": 25})

            def run(self):
                events.append("shop")

        def trace(name, operation):
            def wrapped(*args, **kwargs):
                if recording:
                    events.append(name)
                return operation(*args, **kwargs)
            return wrapped

        with (
            patch.object(Main, "StartPage", self._sequenced_page(["test_mode" if test_mode else "start"])),
            patch.object(Main, "GameScreen", self._sequenced_page([f"level_{level}"])),
            patch.object(Main, "RoundPage", FakeRoundPage),
            patch.object(Main, "GameplayPage", FakeGameplayPage),
            patch.object(Main, "ShopPage", FakeShopPage),
            patch.object(profile_manager, "save_progress_from_game_state", side_effect=trace("save", profile_manager.save_progress_from_game_state)),
            patch.object(profile_manager, "clear_active_game", side_effect=trace("clear", profile_manager.clear_active_game)),
            patch.object(game_state, "add_napoleondors", side_effect=trace("reward", game_state.add_napoleondors)) as reward,
            patch.object(game_state, "update_bank_interest_base", side_effect=trace("interest", game_state.update_bank_interest_base)),
        ):
            Main.main()

        reward.assert_called_once_with(level, 5 if level == 2 else 0)
        expected = ["save"] if not resumed and not test_mode else []
        expected += ["reward"] + ([] if test_mode else ["clear"])
        if level == 2:
            expected += ["shop", "interest"]
            expected += [] if test_mode else ["save"]
        if resumed:
            # Existing resume flow clears again, then saves on reentering the level.
            expected += ["clear", "save"]
        self.assertEqual(events, expected + ["round_page"])
        self.assertEqual(game_state.pending_shop_discount_percent, 0)
        saved = profile_manager.load_profile(1)
        if test_mode:
            self.assertEqual(saved, profile_before)
        else:
            self.assertIsNone(saved["active_game"])
            progress = game_state.boss_progress[level]["round_progress"][progress_key]
            self.assertEqual(progress["completed_rounds"], [1])
            self.assertEqual(progress["round_selections"], {1: {"key": "h"}})
            if not resumed:
                self.assertEqual([list(line) for line in progress["saved_lines"]], [[1, 2, 3, 4]])

    def test_regular_round_victory_preserves_reward_and_save_order(self):
        for level in (1, 2):
            for resumed in (False, True):
                with self.subTest(level=level, resumed=resumed):
                    self._check_regular_round_victory(level, resumed=resumed)

    def test_test_mode_regular_victory_does_not_write_profile(self):
        self._check_regular_round_victory(2, test_mode=True)

    def test_purchase_survives_window_close_and_start_returns_to_the_same_shop(self):
        level = 2
        game_state.ensure_napoleondor_level(level)
        game_state.napoleondors = 10
        game_state.bank_bought = True
        state = game_state.new_boss_progress_state()
        game_state.boss_progress[level] = state
        state.update(run_stats_started=True, shop_visit={"discount_percent": 25},
                     round_progress={"0:0:2_AdamSmith.png": {"completed_rounds": [1]}},
                     current_boss={"boss_filename": "2_AdamSmith.png", "boss_index": 0, "defeated_count": 0})
        profile_manager.save_progress_from_game_state(1)
        shelf = [{"kind": "special", "special_id": "derivative", "cost": 2}]
        if not pygame.display.get_init():
            pygame.display.init()
            self.addCleanup(pygame.display.quit)
        if not pygame.font.get_init():
            pygame.font.init()
            self.addCleanup(pygame.font.quit)
        viewport = pygame.display.set_mode(Main.LOGICAL_SCREEN_SIZE)
        visits = []
        page_class = Main.ShopPage

        def shop(*args, **kwargs):
            page = page_class(viewport, "egyptiennemncyr_condensedbold.ttf", *args[2:], **kwargs)
            visits.append(page)
            page._offer_animation = None
            pygame.event.clear()
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=page.offer_rects[0].center))
            if len(visits) == 1:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            else:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
            return page

        round_pages = []
        with (
            patch.object(Main, "StartPage", self._sequenced_page(["start", "start"])),
            patch.object(Main, "ShopPage", side_effect=shop),
            patch.object(Main, "RoundPage", self._sequenced_page(["quit"], round_pages)),
            patch.object(Main, "GameScreen", side_effect=AssertionError("lost current level")),
            patch.object(Main, "GameplayPage", side_effect=AssertionError("replayed finished round")),
            patch.object(profile_manager, "is_tutorial_pending", return_value=False),
            patch.object(game_state, "generate_shop_offers", return_value=shelf) as generate,
            patch("shop_page.record_card_offers") as record_offers,
            patch("shop_page.record_shop_card_offers"),
        ):
            with patch.object(Main.sys, "exit", side_effect=SystemExit), self.assertRaises(SystemExit):
                Main.main()
            saved = profile_manager.load_profile(1)["progress"]
            visit = saved["boss_progress"]["2"]["shop_visit"]
            self.assertEqual((saved["napoleondors"], saved["global_hand_bonus"]), (8, 1))
            self.assertEqual((visit["discount_percent"], visit["offers"], visit["sold_offer_indexes"]),
                             (25, shelf, [0]))
            self.assertIsNone(saved["bank_interest_base"])
            profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
            Main.main()

        self.assertEqual(len(visits), 2)
        self.assertEqual(len(round_pages), 1)
        generate.assert_called_once()
        record_offers.assert_called_once()
        saved = profile_manager.load_profile(1)["progress"]
        self.assertIsNone(saved["boss_progress"]["2"]["shop_visit"])
        self.assertEqual((saved["napoleondors"], saved["bank_interest_base"], saved["global_hand_bonus"]), (8, 8, 1))

    def test_pre_boss_run_bonuses_survive_every_resume_path(self):
        level = 4
        boss = "2_AdamSmith.png"
        progress_key = f"0:0:{boss}"
        expected = {"global_hand_bonus": 1, "derivative_bought": True,
                    "updown_probability_bonus": 5, "variance_offer_bought_count": 2,
                    "global_dobor": 2, "global_start_money_bonus": 3, "global_start_c_shares_bonus": 4}
        for entry in ("map", "saved_round", "shop"):
            for legacy in (False, True):
                with self.subTest(entry=entry, legacy=legacy):
                    profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
                    game_state.ensure_napoleondor_level(level)
                    state = game_state.new_boss_progress_state()
                    game_state.boss_progress[level] = state
                    state["run_stats_started"] = True
                    state["round_progress"][progress_key] = {"completed_rounds": [1]}
                    game_state.buy_derivative_hand_bonus()
                    game_state.add_updown_probability_bonus(3)
                    game_state.buy_variance_offer()
                    game_state.buy_variance_offer()
                    game_state.global_dobor = 2
                    game_state.global_start_money_bonus = 3
                    game_state.add_start_c_shares_bonus(4)
                    if entry == "saved_round":
                        profile_manager.save_active_game(1, {
                            "level_number": level, "boss_index": 0, "boss_filename": boss,
                            "round_num": 2, "defeated_count": 0, "difficulty": "e",
                        }, {"Day": 2})
                    else:
                        if entry == "shop":
                            state["shop_visit"] = {"discount_percent": 0}
                        profile_manager.save_progress_from_game_state(1)
                    if legacy:
                        profile = profile_manager.load_profile(1)
                        del profile["progress"]["boss_progress"]["4"]["run_stats_started"]
                        profile_manager.save_profile(profile)
                    round_pages = []
                    with (
                        patch.object(Main.pygame.display, "get_driver", return_value="dummy"),
                        patch.object(Main, "StartPage", self._sequenced_page(["start"])),
                        patch.object(Main, "GameScreen", self._sequenced_page(["level_4"] if entry == "map" else [])),
                        patch.object(Main, "GameplayPage", self._sequenced_page(["round_select"] if entry == "saved_round" else [])),
                        patch.object(Main, "ShopPage", self._sequenced_page(["next"] if entry != "map" else [])),
                        patch.object(Main, "RoundPage", self._sequenced_page(["quit"], round_pages)),
                    ):
                        Main.main()
                    self.assertEqual(len(round_pages), 1)
                    self.assertEqual(round_pages[0].kwargs["round_progress"]["completed_rounds"],
                                     [1, 2] if entry == "saved_round" else [1])
                    saved = profile_manager.load_profile(1)["progress"]
                    self.assertEqual({key: saved[key] for key in expected}, expected)

    def test_fresh_level_clears_stale_bonus_values_and_purchase_flags_together(self):
        game_state.buy_derivative_hand_bonus()
        game_state.buy_variance_offer()
        profile_manager.save_progress_from_game_state(1)
        with (
            patch.object(Main.pygame.display, "get_driver", return_value="dummy"),
            patch.object(Main, "StartPage", self._sequenced_page(["start"])),
            patch.object(Main, "GameScreen", self._sequenced_page(["level_1"])),
            patch.object(Main, "BossPage", self._sequenced_page(["quit"])),
        ):
            Main.main()
        saved = profile_manager.load_profile(1)["progress"]
        self.assertEqual((saved["global_hand_bonus"], saved["derivative_bought"]), (0, False))
        self.assertEqual((saved["updown_probability_bonus"], saved["variance_offer_bought_count"]), (0, 0))

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
        game_state.buy_derivative_hand_bonus()
        game_state.buy_variance_offer()
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
        saved = profile_manager.load_profile(1)["progress"]
        self.assertEqual((saved["global_hand_bonus"], saved["derivative_bought"]), (0, False))
        self.assertEqual((saved["updown_probability_bonus"], saved["variance_offer_bought_count"]), (0, 0))

    def test_restart_from_boss_selection_resets_attempt_and_rerolls_boss_screen(self):
        game_state.round_reward_cards[1] = [11]
        game_state.shop_deck_cards[:] = [12]
        game_state.boss_progress[1] = game_state.new_boss_progress_state()
        game_state.boss_progress[1]["roster"] = ["old_boss.png"]
        boss_results = deque(["restart_level", "quit"])
        boss_rosters = []

        class RestartingBossPage:
            def __init__(self, *args, **kwargs):
                boss_rosters.append(game_state.boss_progress[1].get("roster"))

            def run(self):
                result = boss_results.popleft()
                if result == "restart_level":
                    game_state.boss_progress[1]["roster"] = ["first_roll.png"]
                return result

        start_page = self._sequenced_page(["start"])
        level_page = self._sequenced_page(["level_1"])
        with (
            patch.object(Main, "StartPage", start_page),
            patch.object(Main, "GameScreen", level_page),
            patch.object(Main, "BossPage", RestartingBossPage),
        ):
            Main.main()

        self.assertEqual(boss_rosters, [None, None])
        self.assertEqual(game_state.round_reward_cards.get(1, []), [])
        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertIsNone(profile_manager.get_active_game(1))


if __name__ == "__main__":
    unittest.main()
