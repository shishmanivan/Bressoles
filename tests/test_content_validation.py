import copy
import os
import tempfile
import unittest
from unittest import mock

import game_state
from boss_effects import parse_boss_functionality_spec, parse_boss_reward_spec
from boss_logic import BOSS_LEVELS, _generate_level6_boss_roster, get_configured_levels, resolve_boss_number
from content_validation import _read_csv_rows, validate_game_content
from game_data import load_boss_rewards, load_cards_config, load_goals_level5, load_goals_level8, load_language
from round_page import RoundPage
from round_page_helpers import resolve_boss_goal


class ContentValidationTests(unittest.TestCase):
    def test_level8_goals_and_roster_match_the_testing_contract(self):
        goals = load_goals_level8()
        self.assertEqual([goals[key][1] for key in ("E", "M", "H")], [100, 120, 150])
        self.assertEqual(
            [[goals[key][round_number] for key in ("E", "M", "H")] for round_number in range(1, 5)],
            [[100, 120, 150], [250, 300, 400], [350, 450, 550], [450, 550, 650]],
        )
        self.assertEqual(
            [[goals[key][(2, round_number)] for key in ("E", "M", "H")] for round_number in range(1, 5)],
            [[250, 350, 500], [500, 600, 750], [900, 1000, 1150], [1000, 1100, 1250]],
        )
        self.assertEqual(
            [[goals[key][(3, round_number)] for key in ("E", "M", "H")] for round_number in range(1, 5)],
            [[350, 450, 600], [650, 750, 900], [1000, 1100, 1250], [1000, 1100, 1250]],
        )
        self.assertEqual(goals["E"][("boss", 1)], 900)
        self.assertEqual(goals["E"][("boss", 2)], 1500)
        self.assertEqual(goals["E"][("boss", 3)], 2000)

        with mock.patch("boss_logic.random.shuffle", side_effect=lambda values: None):
            roster = _generate_level6_boss_roster(4)
        self.assertEqual(len(roster), 4)
        self.assertTrue(all(len(step) == 1 for step in roster))
        self.assertTrue(all(BOSS_LEVELS[step[0]] == 1 for step in roster[:2]))
        self.assertTrue(all(BOSS_LEVELS[step[0]] == 2 for step in roster[2:]))

    def test_current_content_is_complete(self):
        self.assertEqual(validate_game_content(), [])

    def test_every_unlockable_license_has_a_positive_cost(self):
        licensed_offer_ids = {
            card_id
            for card_ids in game_state.LICENSES_BY_LEVEL.values()
            for card_id in card_ids
        }

        self.assertEqual(set(game_state.LICENSE_COSTS), licensed_offer_ids)
        self.assertTrue(all(cost > 0 for cost in game_state.LICENSE_COSTS.values()))

    def test_missing_required_card_is_reported(self):
        cards = copy.deepcopy(load_cards_config())
        cards.pop(100)

        errors = validate_game_content(cards=cards, check_source_csvs=False)

        self.assertTrue(any("required card 100 is missing" in error for error in errors))

    def test_missing_runtime_translation_is_reported_for_each_language(self):
        languages = {"RU": load_language("RU"), "ENG": load_language("ENG")}
        languages["ENG"].pop("PauseContinue")

        errors = validate_game_content(languages=languages, check_source_csvs=False)

        self.assertIn("Lang.csv: PauseContinue is missing for ENG", errors)

    def test_extra_csv_column_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "Sample.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as output_file:
                output_file.write("Key;RU;ENG\nExample;Текст;Text;unexpected\n")
            errors = []

            _read_csv_rows(temp_dir, "Sample.csv", ("Key", "RU", "ENG"), ("Key",), errors)

        self.assertIn("Sample.csv:2: unexpected extra columns", errors)

    def test_missing_fifth_level_boss_goal_is_reported(self):
        goals = copy.deepcopy(load_goals_level5())
        for difficulty in ("E", "M", "H"):
            goals[difficulty].pop(("boss", 4), None)

        errors = validate_game_content(goals_level5=goals, check_source_csvs=False)

        self.assertIn("GoalsLevel5.csv: missing boss goal for position 4", errors)

    def test_missing_boss_goal_is_not_replaced_by_a_hidden_fallback(self):
        with self.assertRaisesRegex(ValueError, "Missing level 4 boss goal"):
            resolve_boss_goal(
                level_number=4,
                boss_index=0,
                boss_selection=0,
                defeated_count=3,
                is_apper_boss=False,
                boss_goals={},
                get_level2_goal=lambda *args: None,
                get_level3_goal=lambda *args: None,
                get_level4_goal=lambda *args: None,
                apper_goal_boost=lambda value: value,
            )

    def test_saved_boss_filename_has_priority_over_roster_index(self):
        self.assertEqual(
            resolve_boss_number(3, boss_index=0, defeated_count=0, boss_filename="6_Arkwright.png"),
            6,
        )

    def test_empty_legacy_level_rows_are_not_treated_as_configured_levels(self):
        levels = {1: {"Rounds": 1}, 4: {"Rounds": 3}}
        rounds = {
            1: {"Rounds": 1},
            4: {"Rounds": 3},
            5: {"Rounds": None},
            10: {"Rounds": None},
        }

        self.assertEqual(get_configured_levels(rounds, levels), [1, 4])

    def test_every_configured_boss_effect_has_a_known_format(self):
        for boss_number, entry in load_boss_rewards().items():
            with self.subTest(boss=boss_number, field="Reward"):
                parse_boss_reward_spec(entry.get("Reward"))
            with self.subTest(boss=boss_number, field="Functionalities"):
                parse_boss_functionality_spec(entry.get("Functionalities"))

    def test_arkwright_reward_does_not_increase_hand_size(self):
        reward = load_boss_rewards()[6]["Reward"]

        self.assertEqual(reward, "ArkwrightSilverCards")

    def test_unknown_boss_effect_is_reported_by_content_validation(self):
        boss_rewards = copy.deepcopy(load_boss_rewards())
        boss_rewards[2]["Functionalities"] = "LastTrun=LastTrun-1"

        errors = validate_game_content(boss_rewards=boss_rewards, check_source_csvs=False)

        self.assertTrue(any("LastTrun" in error for error in errors))

    def test_level_rounds_effect_is_structured(self):
        effect = parse_boss_functionality_spec("LevelRounds=LevelRounds+1")[0]
        self.assertEqual(
            (effect.kind, effect.target, effect.operator, effect.value),
            ("assignment", "LevelRounds", "+", 1),
        )

    def test_level_two_round_modifier_keeps_existing_limits(self):
        page = RoundPage.__new__(RoundPage)
        page.level_number = 2
        page.rounds_required = 3

        page._apply_level_rounds_functionality("LevelRounds=LevelRounds+2")
        self.assertEqual(page.rounds_required, 4)

        page._apply_level_rounds_functionality("LevelRounds=LevelRounds-10")
        self.assertEqual(page.rounds_required, 1)


if __name__ == "__main__":
    unittest.main()
