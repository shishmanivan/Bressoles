import copy
import unittest
from unittest import mock

import game_state
import profile_manager
from boss_logic import apply_boss_reward, get_boss_number_from_index
from gameplay_deck import setup_starting_deck_and_hand
from gameplay_winlose import apply_win_reward


STATE_FIELDS = (
    "level_1_boss_defeated",
    "level_2_boss_defeated",
    "level_3_boss_defeated",
    "level_4_boss_defeated",
    "level_5_boss_defeated",
    "boss_progress",
    "global_dobor",
    "global_start_money_bonus",
    "global_last_turn_bonus",
    "global_hand_bonus",
    "global_start_c_shares_bonus",
    "napoleondors",
    "napoleondor_level",
    "earned_reward_cards",
    "round_reward_cards",
    "shop_deck_cards",
    "removed_deck_cards_by_level",
    "investment_card_bonuses",
    "profit_reward_bonus",
    "updown_probability_bonus",
    "boss_rare_card_pool_bonus_percent",
    "deal_flow_bonus_percent",
    "variance_offer_bought_count",
    "pending_shop_discount_percent",
    "bailout_rounds_remaining",
    "active_long_investments",
    "golden_stocks_chance_percent",
    "golden_stocks_triggered",
    "golden_stocks_trigger_count",
    "derivative_bought",
    "issuer_bought_count",
    "boss_lifecycle_slot_bonus",
    "boss_shop_offer_bonus",
    "multibagger_bought",
    "diversification_bought",
    "expansion_bought",
    "bill_of_exchange_offer_bought",
    "compounding_bought",
    "bank_bought",
    "bank_interest_base",
    "licensed_card_ids",
    "silver_cards",
    "black_cards",
    "active_black_cards",
    "gold_cards",
    "active_gold_cards",
    "active_lifecycle_card_order",
    "forced_start_hand_cards_by_level",
    "guaranteed_start_hand_cards_by_level",
    "active_red_cards_level",
    "active_red_cards_deck",
    "active_silver_cards_level",
    "active_silver_cards_deck",
    "Frugality",
    "capital_preservation_bought",
    "mirroring_bought_count",
    "mirrored_deck_cards",
    "retention_active",
    "retention_pending_level",
    "retention_pending_cards",
    "windfall_boss_victories",
    "risk_premium_h_rounds",
)


class GameStateTestCase(unittest.TestCase):
    def setUp(self):
        self._state_snapshot = {
            name: copy.deepcopy(getattr(game_state, name))
            for name in STATE_FIELDS
        }

    def tearDown(self):
        for name, value in self._state_snapshot.items():
            setattr(game_state, name, value)


class RunResetRulesTests(GameStateTestCase):
    def test_bonus_slots_reset_before_retained_gold_loadout_is_trimmed(self):
        for finish_run in (game_state.reset_level_attempt, game_state.complete_level_run):
            with self.subTest(outcome=finish_run.__name__):
                game_state.level_3_boss_defeated = True
                game_state.level_5_boss_defeated = False
                game_state.issuer_bought_count = 2
                game_state.boss_lifecycle_slot_bonus = 2
                game_state.black_cards = [301]
                game_state.active_black_cards = [301]
                game_state.silver_cards = [201]
                game_state.licensed_card_ids = {110, 121}
                game_state.gold_cards = [401, 402, 403, 404, 405]
                game_state.active_gold_cards = list(game_state.gold_cards)
                game_state.active_lifecycle_card_order = []
                game_state.capital_preservation_bought = True

                finish_run(5)

                self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 3)
                if finish_run is game_state.reset_level_attempt:
                    self.assertEqual(game_state.gold_cards, [401, 402, 403, 404, 405])
                    self.assertEqual(game_state.active_gold_cards, [401, 402])
                else:
                    self.assertEqual(game_state.gold_cards, [])
                    self.assertEqual(game_state.active_gold_cards, [])
                self.assertFalse(game_state.capital_preservation_bought)
                self.assertTrue(game_state.level_3_boss_defeated)
                self.assertEqual(game_state.licensed_card_ids, {110, 121})
                self.assertEqual(game_state.silver_cards, [201])
                self.assertEqual(game_state.black_cards, [301])
                self.assertEqual(game_state.active_black_cards, [301])

    def test_completion_keeps_route_history_while_restart_creates_a_new_attempt(self):
        for finish_run in (game_state.reset_level_attempt, game_state.complete_level_run):
            with self.subTest(outcome=finish_run.__name__):
                previous = game_state.new_boss_progress_state()
                previous["defeated"] = 3
                previous["run_stats_finished"] = True
                game_state.boss_progress[4] = previous
                game_state.global_dobor = 3
                game_state.global_start_money_bonus = 8

                finish_run(4)

                self.assertEqual(game_state.global_dobor, 1)
                self.assertEqual(game_state.global_start_money_bonus, 0)
                if finish_run is game_state.reset_level_attempt:
                    self.assertIsNot(game_state.boss_progress[4], previous)
                    self.assertEqual(game_state.boss_progress[4], game_state.new_boss_progress_state())
                else:
                    self.assertIs(game_state.boss_progress[4], previous)
                    self.assertEqual(previous["defeated"], 3)
                    self.assertTrue(previous["run_stats_finished"])

    def test_golden_stocks_can_trigger_once_in_each_consecutive_run(self):
        game_state.golden_stocks_chance_percent = game_state.GOLDEN_STOCKS_BASE_CHANCE
        game_state.golden_stocks_triggered = False
        game_state.golden_stocks_trigger_count = 0
        game_state.gold_cards = []

        with (
            mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[402]),
            mock.patch.object(game_state.random, "randint", return_value=1),
            mock.patch.object(game_state.random, "choice", return_value=402),
        ):
            self.assertEqual(game_state.resolve_golden_stocks_round([302]), 402)
            self.assertIsNone(game_state.resolve_golden_stocks_round([302]))

            game_state.reset_level_attempt(6)

            self.assertEqual(game_state.resolve_golden_stocks_round([302]), 402)

        self.assertEqual(game_state.golden_stocks_trigger_count, 2)

    def test_golden_stocks_resets_for_next_run_but_keeps_lifetime_trigger_count(self):
        game_state.golden_stocks_chance_percent = 18
        game_state.golden_stocks_triggered = True
        game_state.golden_stocks_trigger_count = 7

        game_state.reset_level_attempt(6)

        self.assertEqual(
            game_state.golden_stocks_chance_percent,
            game_state.GOLDEN_STOCKS_BASE_CHANCE,
        )
        self.assertFalse(game_state.golden_stocks_triggered)
        self.assertEqual(game_state.golden_stocks_trigger_count, 7)

    def test_mirroring_copy_survives_boss_progress_but_clears_with_the_run(self):
        level = 4
        game_state.round_reward_cards[level] = [112]
        self.assertEqual(game_state.buy_mirroring_card(level, 112), 112)

        game_state.round_reward_cards.pop(level)

        self.assertEqual(game_state.build_current_level_deck(level).count(112), 1)
        self.assertEqual(game_state.mirroring_bought_count, 1)
        game_state.reset_level_attempt(level)
        self.assertEqual(game_state.mirrored_deck_cards, [])
        self.assertEqual(game_state.mirroring_bought_count, 0)

    def test_capital_preservation_keeps_gold_cards_through_one_defeat(self):
        game_state.gold_cards[:] = [401, 405]
        game_state.set_active_gold_cards([401])
        game_state.bear_goal_reduction_steps = 3
        game_state.capital_preservation_bought = True

        game_state.reset_level_attempt(4)

        self.assertEqual(game_state.gold_cards, [401, 405])
        self.assertEqual(game_state.active_gold_cards, [401])
        self.assertEqual(game_state.bear_goal_reduction_steps, 0)
        self.assertFalse(game_state.capital_preservation_bought)

        game_state.reset_level_attempt(4)
        self.assertEqual(game_state.gold_cards, [])
        self.assertEqual(game_state.active_gold_cards, [])

    def test_windfall_progress_resets_with_gold_run_effects(self):
        game_state.gold_cards[:] = [426]
        game_state.set_active_gold_cards([426])
        game_state.windfall_boss_victories = 3

        game_state.reset_level_attempt(5)

        self.assertEqual(game_state.get_windfall_boss_victories(), 0)

    def test_risk_premium_progress_resets_with_gold_run_effects(self):
        game_state.gold_cards[:] = [431]
        game_state.set_active_gold_cards([431])
        game_state.risk_premium_h_rounds = 3

        game_state.reset_level_attempt(5)

        self.assertEqual(game_state.get_risk_premium_h_rounds(), 0)

    def test_capital_preservation_does_not_keep_gold_after_level_completion(self):
        game_state.gold_cards[:] = [401]
        game_state.capital_preservation_bought = True

        game_state.complete_level_run(4)

        self.assertEqual(game_state.gold_cards, [])
        self.assertFalse(game_state.capital_preservation_bought)

    def test_starting_napoleondors_follow_completed_level_progression(self):
        game_state.level_2_boss_defeated = False
        game_state.level_3_boss_defeated = False
        game_state.level_4_boss_defeated = False
        game_state.level_5_boss_defeated = False
        self.assertEqual(game_state.get_starting_napoleondors_for_level(1), 0)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(2), 0)

        game_state.level_2_boss_defeated = True
        self.assertEqual(game_state.get_starting_napoleondors_for_level(3), 2)

        game_state.level_3_boss_defeated = True
        self.assertEqual(game_state.get_starting_napoleondors_for_level(4), 5)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(5), 5)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(6), 5)

        game_state.level_4_boss_defeated = True
        self.assertEqual(game_state.get_starting_napoleondors_for_level(5), 7)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(6), 7)

        game_state.level_5_boss_defeated = True
        self.assertEqual(game_state.get_starting_napoleondors_for_level(6), 9)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(7), 9)
        self.assertEqual(game_state.get_starting_napoleondors_for_level(8), 9)

    def test_victory_napoleondors_start_on_level_two_and_scale_by_difficulty(self):
        for difficulty in ("e", "m", "h"):
            with self.subTest(level=1, difficulty=difficulty):
                self.assertEqual(
                    game_state.get_round_victory_napoleondor_reward(1, difficulty),
                    0,
                )
        self.assertEqual(game_state.get_boss_victory_napoleondor_reward(1), 0)

        for level in (2, 3, 4, 5):
            with self.subTest(level=level):
                self.assertEqual(game_state.get_round_victory_napoleondor_reward(level, "e"), 1)
                self.assertEqual(game_state.get_round_victory_napoleondor_reward(level, "m"), 2)
                self.assertEqual(game_state.get_round_victory_napoleondor_reward(level, "h"), 3)
                self.assertEqual(game_state.get_boss_victory_napoleondor_reward(level), 5)

    def test_peabody_halves_the_new_difficulty_reward(self):
        self.assertEqual(game_state.get_round_victory_napoleondor_reward(5, "e", 14), 0.5)
        self.assertEqual(game_state.get_round_victory_napoleondor_reward(5, "m", 14), 1)
        self.assertEqual(game_state.get_round_victory_napoleondor_reward(5, "h", 14), 1.5)

    def test_kolbe_personal_reward_is_separate_from_the_boss_victory_reward(self):
        game_state.napoleondors = 0
        game_state.napoleondor_level = 4
        gameplay = mock.Mock(level_number=4)

        self.assertEqual(game_state.get_boss_victory_napoleondor_reward(4), 5)
        apply_boss_reward("Napoleondors20", gameplay)

        self.assertEqual(game_state.napoleondors, 20)

    def test_level5_completion_unlocks_levels7_and8_and_awards_commission(self):
        game_state.level_5_boss_defeated = False
        self.assertFalse(game_state.get_progress_flags()["level_6_unlocked"])
        self.assertFalse(game_state.get_progress_flags()["level_7_unlocked"])
        self.assertFalse(game_state.get_progress_flags()["level_8_unlocked"])
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 3)

        game_state.level_5_boss_defeated = True

        self.assertTrue(game_state.get_progress_flags()["level_6_unlocked"])
        self.assertTrue(game_state.get_progress_flags()["level_7_unlocked"])
        self.assertTrue(game_state.get_progress_flags()["level_8_unlocked"])
        self.assertEqual(game_state.get_lifecycle_card_slot_limit(), 4)
        self.assertEqual(game_state.get_level_completion_black_reward_cards(4), [302])
        self.assertEqual(game_state.get_level_completion_black_reward_cards(5), [303])

    def test_golden_stocks_already_owned_is_not_removed_by_the_new_level5_reward(self):
        game_state.black_cards[:] = [301, 302]

        game_state.complete_level_run(5)

        self.assertEqual(game_state.black_cards, [301, 302])

    def test_loss_clears_run_state_but_preserves_profile_inventory(self):
        level = 4
        game_state.level_2_boss_defeated = True
        game_state.level_3_boss_defeated = True
        game_state.boss_progress[level] = {"defeated": 2}
        game_state.global_dobor = 2
        game_state.global_start_money_bonus = 2
        game_state.napoleondors = 12
        game_state.napoleondor_level = level
        game_state.earned_reward_cards[level] = [112]
        game_state.round_reward_cards[level] = [11, 15]
        game_state.shop_deck_cards[:] = [117]
        game_state.removed_deck_cards_by_level[level] = [1]
        game_state.investment_card_bonuses[11] = 2
        game_state.gold_cards[:] = [401]
        game_state.forced_start_hand_cards_by_level[level] = [112]
        game_state.guaranteed_start_hand_cards_by_level[level] = [112]
        game_state.licensed_card_ids = {110, 112}
        game_state.silver_cards[:] = [201]
        game_state.black_cards[:] = [301]
        game_state.Frugality = 4

        game_state.reset_level_attempt(level)

        self.assertEqual(game_state.boss_progress[level]["defeated"], 0)
        self.assertEqual(game_state.global_dobor, 1)
        self.assertEqual(game_state.napoleondors, 5)
        self.assertEqual(game_state.earned_reward_cards[level], [])
        self.assertNotIn(level, game_state.round_reward_cards)
        self.assertEqual(game_state.shop_deck_cards, [])
        self.assertNotIn(level, game_state.removed_deck_cards_by_level)
        self.assertEqual(game_state.investment_card_bonuses, {})
        self.assertEqual(game_state.gold_cards, [])
        self.assertEqual(game_state.forced_start_hand_cards_by_level[level], [])
        self.assertEqual(game_state.guaranteed_start_hand_cards_by_level[level], [])

        self.assertTrue(game_state.level_2_boss_defeated)
        self.assertTrue(game_state.level_3_boss_defeated)
        self.assertEqual(game_state.licensed_card_ids, {110, 112})
        self.assertEqual(game_state.silver_cards, [201])
        self.assertEqual(game_state.black_cards, [301])
        self.assertEqual(game_state.Frugality, 0)

    def test_direct_attempt_restart_clears_all_temporary_level_rewards(self):
        level = 3
        game_state.earned_reward_cards[level] = [112]
        game_state.round_reward_cards[level] = [11]
        game_state.forced_start_hand_cards_by_level[level] = [112]
        game_state.guaranteed_start_hand_cards_by_level[level] = [112]
        game_state.shop_deck_cards[:] = [117]
        game_state.boss_progress[level] = {"defeated": 2}

        state = game_state.reset_level_attempt(level)

        self.assertEqual(state, game_state.new_boss_progress_state())
        self.assertEqual(game_state.earned_reward_cards[level], [])
        self.assertNotIn(level, game_state.round_reward_cards)
        self.assertEqual(game_state.forced_start_hand_cards_by_level[level], [])
        self.assertEqual(game_state.guaranteed_start_hand_cards_by_level[level], [])
        self.assertEqual(game_state.shop_deck_cards, [])


class RewardLifecycleRulesTests(GameStateTestCase):
    def test_retention_carries_one_selected_temporary_card_to_the_next_boss(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = True
        gameplay.is_final_boss = False
        gameplay.level_number = 2
        gameplay.boss_index = 0
        gameplay.defeated_count = 0
        gameplay.last_earned_cards = []
        game_state.round_reward_cards = {2: [11, 15]}
        game_state.retention_active = True

        apply_win_reward(
            gameplay,
            earned_reward_cards=game_state.round_reward_cards,
            rewards={},
            reward_token_random_red=-1001,
            load_boss_rewards=lambda: {},
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=mock.Mock(),
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
        )

        self.assertNotIn(2, game_state.round_reward_cards)
        self.assertEqual(game_state.get_retention_pending_cards(2), [11, 15])
        self.assertFalse(game_state.retention_active)
        self.assertFalse(game_state.is_retention_offer_available())
        self.assertEqual(game_state.complete_retention_selection(2, 15), 15)
        self.assertEqual(game_state.round_reward_cards, {2: [15]})
        self.assertTrue(game_state.is_retention_offer_available())

    def test_retention_reopens_without_selection_when_no_temporary_cards_exist(self):
        game_state.retention_active = True

        self.assertEqual(game_state.prepare_retention_after_boss_victory(3), [])
        self.assertFalse(game_state.retention_active)
        self.assertEqual(game_state.get_retention_pending_cards(3), [])
        self.assertTrue(game_state.is_retention_offer_available())

    def test_retention_is_consumed_without_transfer_after_final_boss(self):
        game_state.round_reward_cards = {3: [112]}
        game_state.retention_active = True

        self.assertEqual(
            game_state.prepare_retention_after_boss_victory(3, is_final_boss=True),
            [],
        )
        self.assertFalse(game_state.retention_active)
        self.assertEqual(game_state.get_retention_pending_cards(), [])

    def test_apper_guarantees_only_red_cards_already_in_the_level_deck(self):
        game_state.level_1_boss_defeated = False
        game_state.level_2_boss_defeated = False
        game_state.level_3_boss_defeated = False
        game_state.earned_reward_cards = {2: [112]}
        game_state.forced_start_hand_cards_by_level = {}
        game_state.guaranteed_start_hand_cards_by_level = {}

        with mock.patch.object(game_state.random, "shuffle"):
            selected = game_state.guarantee_existing_red_start_cards(2, 2)

        self.assertEqual(selected, [112])
        self.assertEqual(game_state.guaranteed_start_hand_cards_by_level, {2: [112]})
        self.assertEqual(game_state.build_current_level_deck(2).count(112), 1)

        with mock.patch("gameplay_deck.random.shuffle"):
            _remaining, hand = setup_starting_deck_and_hand(
                2,
                7,
                game_state.earned_reward_cards,
                guaranteed_cards_by_level=game_state.guaranteed_start_hand_cards_by_level,
            )

        self.assertEqual(hand[0], 112)

    def test_adam_smith_red_reward_is_randomly_dealt_from_the_level_deck(self):
        gameplay = mock.Mock()
        gameplay.level_number = 2
        gameplay.last_earned_cards = []
        game_state.earned_reward_cards = {}
        game_state.forced_start_hand_cards_by_level = {}

        with mock.patch.object(game_state, "draw_red_card_for_level", return_value=112):
            apply_boss_reward("RedCard", gameplay)

        self.assertEqual(game_state.earned_reward_cards, {2: [112]})
        self.assertEqual(game_state.forced_start_hand_cards_by_level, {})
        self.assertEqual(gameplay.last_earned_cards, [112])

        with mock.patch("gameplay_deck.random.shuffle"):
            remaining, hand = setup_starting_deck_and_hand(
                2,
                7,
                game_state.earned_reward_cards,
                guaranteed_cards_by_level={},
            )

        self.assertNotIn(112, hand)
        self.assertIn(112, remaining)

    def test_boss_silver_reward_stays_out_of_the_level_deck(self):
        gameplay = mock.Mock()
        gameplay.level_number = 3
        gameplay.last_earned_cards = []
        game_state.earned_reward_cards = {}
        game_state.silver_cards = []

        with mock.patch.object(game_state, "draw_silver_card_for_level", return_value=203):
            apply_boss_reward("SilverCard", gameplay)

        self.assertEqual(game_state.silver_cards, [203])
        self.assertEqual(game_state.earned_reward_cards, {})
        self.assertEqual(gameplay.last_earned_cards, [203])
        self.assertNotIn(203, game_state.build_current_level_deck(3))

    def test_arkwright_awards_three_silver_cards_with_one_sub_twenty_percent_card(self):
        gameplay = mock.Mock()
        gameplay.level_number = 3
        gameplay.last_earned_cards = []
        game_state.silver_cards = []
        cards = {
            201: {"Open": 1, "Variable": 50},
            202: {"Open": 1, "Variable": 10},
            203: {"Open": 1, "Variable": 20},
        }

        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state, "is_card_licensed", return_value=True),
            mock.patch.object(game_state.random, "choice", side_effect=[202, 201, 203]),
        ):
            apply_boss_reward("ArkwrightSilverCards", gameplay)

        self.assertEqual(game_state.silver_cards, [202, 201, 203])
        self.assertEqual(gameplay.last_earned_cards, [202, 201, 203])

    def test_arkwright_awards_three_any_silver_cards_when_no_rare_card_is_open(self):
        cards = {
            201: {"Open": 1, "Variable": 50},
            203: {"Open": 1, "Variable": 20},
        }
        game_state.silver_cards = []

        with (
            mock.patch.object(game_state, "load_cards_config", return_value=cards),
            mock.patch.object(game_state, "is_card_licensed", return_value=True),
            mock.patch.object(game_state.random, "choice", side_effect=[201, 203, 201]),
        ):
            awarded = game_state.award_arkwright_silver_cards(3)

        self.assertEqual(awarded, [201, 203, 201])

    def test_legacy_forced_reward_migrates_to_random_deck_pool(self):
        game_state.earned_reward_cards = {2: [11]}
        game_state.forced_start_hand_cards_by_level = {2: [112, 112]}

        migrated = game_state.migrate_legacy_forced_start_hand_cards(2)

        self.assertEqual(migrated, {2: [112]})
        self.assertEqual(game_state.earned_reward_cards[2], [11, 112])
        self.assertEqual(game_state.forced_start_hand_cards_by_level[2], [])
        self.assertNotIn("forced_start_hand_cards_by_level", profile_manager._capture_progress())

    def test_regular_round_reward_is_added_to_temporary_level_cards(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = False
        gameplay.level_number = 1
        gameplay.round_num = 1
        gameplay.difficulty = "e"
        gameplay.last_earned_cards = []
        temporary_cards = {}

        apply_win_reward(
            gameplay,
            earned_reward_cards=temporary_cards,
            rewards={(1, 1, "E"): {"reward1": [12]}},
            reward_token_random_red=-1001,
            load_boss_rewards=mock.Mock(),
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=mock.Mock(),
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
        )

        self.assertEqual(temporary_cards, {1: [12]})
        self.assertEqual(gameplay.last_earned_cards, [12])

    def test_empty_primary_red_pool_does_not_cancel_later_rewards(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = False
        gameplay.level_number = 3
        gameplay.round_num = 3
        gameplay.difficulty = "h"
        gameplay.last_earned_cards = []
        temporary_cards = {}
        add_silver = mock.Mock(return_value=201)

        apply_win_reward(
            gameplay,
            earned_reward_cards=temporary_cards,
            rewards={
                (3, 3, "H"): {
                    "reward1": [-1001],
                    "reward2": [100],
                    "reward3": [-1002],
                }
            },
            reward_token_random_red=-1001,
            load_boss_rewards=mock.Mock(),
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=mock.Mock(),
            pick_random_red_card_for_level=mock.Mock(return_value=None),
            add_silver_card=add_silver,
        )

        self.assertEqual(temporary_cards, {3: [100]})
        self.assertEqual(gameplay.last_earned_cards, [100, 201])
        add_silver.assert_called_once_with(-1002, 3)

    def test_nonfinal_boss_applies_personal_reward_and_clears_temporary_cards(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = True
        gameplay.is_final_boss = False
        gameplay.level_number = 2
        gameplay.boss_index = 0
        gameplay.defeated_count = 0
        gameplay.last_earned_cards = []
        game_state.round_reward_cards = {2: [11, 15]}
        apply_reward = mock.Mock()

        apply_win_reward(
            gameplay,
            earned_reward_cards=game_state.round_reward_cards,
            rewards={},
            reward_token_random_red=-1001,
            load_boss_rewards=lambda: {2: {"Reward": "Dobor=Dobor+1,RedCard"}},
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=apply_reward,
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
        )

        apply_reward.assert_called_once_with("Dobor=Dobor+1,RedCard", gameplay)
        self.assertNotIn(2, game_state.round_reward_cards)

    def test_final_boss_uses_level_reward_instead_of_personal_reward(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = True
        gameplay.is_final_boss = True
        gameplay.level_number = 1
        gameplay.boss_index = 0
        gameplay.defeated_count = 0
        gameplay.last_earned_cards = []
        game_state.round_reward_cards = {1: [11]}
        apply_reward = mock.Mock()

        apply_win_reward(
            gameplay,
            earned_reward_cards=game_state.round_reward_cards,
            rewards={},
            reward_token_random_red=-1001,
            load_boss_rewards=lambda: {1: {"Reward": "unexpected"}},
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=apply_reward,
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
        )

        apply_reward.assert_not_called()
        self.assertEqual(gameplay.last_earned_cards, [15])
        self.assertNotIn(1, game_state.round_reward_cards)

    def test_level5_final_boss_awards_commission_black_card(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = True
        gameplay.is_final_boss = True
        gameplay.level_number = 5
        gameplay.boss_index = 0
        gameplay.defeated_count = 3
        gameplay.last_earned_cards = []
        game_state.black_cards = [301, 302]

        apply_win_reward(
            gameplay,
            earned_reward_cards={},
            rewards={},
            reward_token_random_red=-1001,
            load_boss_rewards=mock.Mock(),
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=mock.Mock(),
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
        )

        self.assertEqual(game_state.black_cards, [301, 302, 303])
        self.assertEqual(gameplay.last_earned_cards, [303])

    def test_level4_final_boss_awards_golden_stocks_black_card(self):
        gameplay = mock.Mock()
        gameplay.is_boss_fight = True
        gameplay.is_final_boss = True
        gameplay.level_number = 4
        gameplay.boss_index = 0
        gameplay.defeated_count = 2
        gameplay.last_earned_cards = []
        game_state.black_cards = [301]

        apply_win_reward(
            gameplay,
            earned_reward_cards={},
            rewards={},
            reward_token_random_red=-1001,
            load_boss_rewards=mock.Mock(),
            get_boss_number_from_index=get_boss_number_from_index,
            apply_boss_reward=mock.Mock(),
            pick_random_red_card_for_level=mock.Mock(),
            add_silver_card=mock.Mock(),
        )

        self.assertEqual(game_state.black_cards, [301, 302])
        self.assertEqual(gameplay.last_earned_cards, [302])


if __name__ == "__main__":
    unittest.main()
