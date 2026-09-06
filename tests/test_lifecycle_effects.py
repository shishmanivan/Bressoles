import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
import gameplay_page
from gameplay_page import GameplayPage
from shop_page import CARD_DESCRIPTIONS
from silver_black_page import CARD_TOOLTIPS, get_positioning_selection_limit


class LifecycleEffectTests(unittest.TestCase):
    def setUp(self):
        self.original_state = {
            "bear_goal_reduction_steps": game_state.bear_goal_reduction_steps,
            "windfall_boss_victories": game_state.windfall_boss_victories,
            "risk_premium_h_rounds": game_state.risk_premium_h_rounds,
            "insurance_goal_debt": game_state.insurance_goal_debt,
            "Frugality": game_state.Frugality,
            "napoleondors": game_state.napoleondors,
            "napoleondor_level": game_state.napoleondor_level,
            "pending_shop_discount_percent": game_state.pending_shop_discount_percent,
            "silver_cards": list(game_state.silver_cards),
        }
        game_state.bear_goal_reduction_steps = 0
        game_state.windfall_boss_victories = 0
        game_state.risk_premium_h_rounds = 0
        game_state.insurance_goal_debt = 0
        game_state.Frugality = 0
        game_state.napoleondors = 0
        game_state.napoleondor_level = 1
        game_state.pending_shop_discount_percent = 0
        game_state.silver_cards = []

    def tearDown(self):
        for name, value in self.original_state.items():
            setattr(game_state, name, value)

    @staticmethod
    def _page(silver=None, black=None, gold=None):
        page = GameplayPage.__new__(GameplayPage)
        page.active_silver_cards = list(silver or [])
        page.active_black_cards = list(black or [])
        page.active_gold_cards = list(gold or [])
        page.active_lifecycle_card_order = []
        page.profile_slot = None
        page.test_mode = True
        page.level_number = 1
        return page

    def test_futures_cards_add_their_declared_turns(self):
        page = self._page(silver=[202, 203], black=[301])
        page.LastTurn = 8

        page._apply_silver_last_turn_bonuses()

        self.assertEqual(page.LastTurn, 12)

    def test_frugality_banks_unused_turns_and_consumes_them_next_round(self):
        game_state.silver_cards = [209]
        page = self._page(silver=[209])
        page.Day = 3
        page.LastTurn = 8
        page.active_silver_cards_spent = False

        self.assertEqual(page._settle_frugality_for_finished_round(), 5)
        page._spend_active_silver_cards_if_needed()

        self.assertEqual(game_state.silver_cards, [])
        self.assertEqual(game_state.Frugality, 5)

        next_round = self._page()
        next_round.LastTurn = 8
        next_round._initial_saved_state = None
        self.assertEqual(next_round._apply_frugality_turn_bonus(), 5)
        self.assertEqual(next_round.LastTurn, 13)
        self.assertEqual(game_state.Frugality, 0)

        next_round.active_silver_cards = []
        self.assertEqual(next_round._settle_frugality_for_finished_round(), 0)
        self.assertEqual(game_state.Frugality, 0)

    def test_restored_finished_frugality_round_preserves_carry_for_next_round(self):
        game_state.Frugality = 5
        page = self._page(silver=[209])
        page.LastTurn = 8
        page._initial_saved_state = {"Day": 3, "win_lose_state": "win"}

        self.assertEqual(page._apply_frugality_turn_bonus(), 0)
        self.assertEqual(page.LastTurn, 8)
        self.assertEqual(game_state.Frugality, 5)

    def test_grant_synergy_upgrades_each_silver_grant(self):
        page = self._page(silver=[214, 214], gold=[403])
        page.Money = 0

        page._apply_grant_start_money_bonus()

        self.assertEqual(page.Money, 24)

    def test_pending_victory_reward_matches_round_difficulty_and_boss_rate(self):
        page = self._page()
        page.level_number = 3
        page.is_boss_fight = False
        page.difficulty = "m"
        page.boss_filename = "2_AdamSmith.png"

        with mock.patch.object(game_state, "profit_reward_bonus", 0):
            self.assertEqual(page._get_pending_victory_napoleondor_reward(), 2)

            page.is_boss_fight = True
            self.assertEqual(page._get_pending_victory_napoleondor_reward(), 5)

    def test_pending_victory_reward_includes_profit_and_peabody(self):
        page = self._page()
        page.level_number = 5
        page.is_boss_fight = False
        page.difficulty = "h"
        page.boss_filename = "14_Peabody.png"

        with mock.patch.object(game_state, "profit_reward_bonus", 2):
            self.assertEqual(page._get_pending_victory_napoleondor_reward(), 3.5)

    def test_nabob_doubles_all_round_income_but_not_the_carried_balance(self):
        page = self._page(silver=[216])
        page.level_number = 2
        page.difficulty = "m"
        page.is_boss_fight = False
        page.boss_filename = None
        page.lang_dict = {}
        game_state.napoleondor_level = 2
        game_state.napoleondors = 1

        entries = page._build_finance_report_entries(
            [],
            opening_balance=1,
            commission_amount=1,
            long_amount=6,
        )
        nabob_amount = page._apply_nabob_win_bonus(entries)
        report = page._build_finance_report_entries(
            [],
            opening_balance=1,
            commission_amount=1,
            long_amount=6,
            nabob_amount=nabob_amount,
        )

        self.assertEqual(nabob_amount, 9)
        self.assertEqual(game_state.napoleondors, 10)
        self.assertEqual(
            [entry["source"] for entry in report],
            ["account_balance", "victory_reward", "commission", "long_profit", "nabob", "total"],
        )
        self.assertEqual(report[-2]["label"], "Бонус Набоба")
        self.assertEqual(report[-2]["amount"], 9)
        self.assertEqual(report[-1]["amount"], 19)

    def test_contango_and_rollover_stack_with_multiple_copies(self):
        page = self._page(silver=[204, 204, 208, 208])
        page.card_actions = {11: 2, 15: -2}
        page.card_turns = {11: 1, 15: 1}

        page._apply_contango_gain_drop_bonuses()
        page._apply_silver_rollover_bonus()

        self.assertEqual(page.card_actions, {11: 8, 15: -8})
        self.assertEqual(page.card_turns, {11: 3, 15: 3})

    def test_silver_rollover_doubles_a_fresh_red_rollover(self):
        page = self._page(silver=[208])
        page.side_cards_top = [112, None, None, None, None, None]
        page.side_cards_locked_top = {0: False}
        page.card_turns = {11: 1}
        page.market_cards = {0: {0: 11}, 1: {}, 2: {}}
        page.market_card_turns = {0: {0: 1}, 1: {}, 2: {}}
        page.side_card_jump_animations = {}

        self.assertTrue(page._apply_extended_gain_drop_effect_if_needed())

        self.assertEqual(page.card_turns[11], 3)
        self.assertEqual(page.market_card_turns[0][0], 3)

    def test_basket_trading_queues_equal_growth_animations_for_all_markets(self):
        page = self._page(silver=[206, 206])
        page.stock_price_turn_results = [
            {"market": 0, "type": "rise"},
            {"market": 1, "type": "rise"},
            {"market": 2, "type": "rise"},
        ]
        page.Aprice = page.BPrice = page.CPrice = 10
        page.price_animation_queue = []
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_basket_trading_if_needed())

        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (10, 10, 10))
        self.assertEqual(
            page.price_animation_queue,
            [
                {
                    "market": (0, 1, 2),
                    "type": "rise",
                    "price_change": 6,
                    "source": "basket_trading",
                },
            ],
        )
        page.typewriter_sound = None
        self.assertTrue(page._start_next_price_animation(now=100))
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (16, 16, 16))
        self.assertEqual(page.current_price_animation["market"], (0, 1, 2))
        self.assertEqual(page.current_price_animation["frame_idx"], 0)
        self.assertFalse(page._apply_basket_trading_if_needed())

    def test_forward_trading_synergy_awards_four_turns_per_pair(self):
        page = self._page(silver=[207], gold=[402])
        page.side_cards_top = [100, 100, None, None, None, None]
        page.side_cards_locked_top = {0: False, 1: False}
        page.forward_trading_shareholder_count = 0
        page.LastTurn = 8

        self.assertTrue(page._apply_forward_trading_effect_if_needed())

        self.assertEqual(page.LastTurn, 12)
        self.assertEqual(page.forward_trading_shareholder_count, 0)

    def test_duplicate_gold_forward_trading_doubles_both_effect_paths(self):
        page = self._page(gold=[402, 402])
        page.side_cards_top = [100, None, None, None, None, None]
        page.side_cards_locked_top = {0: False}
        page.forward_trading_shareholder_count = 0
        page.LastTurn = 8

        self.assertTrue(page._apply_forward_trading_effect_if_needed())
        self.assertEqual(page.LastTurn, 10)

        page.active_silver_cards = [207]
        page.side_cards_top = [100, 100, None, None, None, None]
        page.side_cards_locked_top = {0: False, 1: False}
        self.assertTrue(page._apply_forward_trading_effect_if_needed())
        self.assertEqual(page.LastTurn, 18)

    def test_insurance_carries_only_a_regular_round_shortfall(self):
        page = self._page(silver=[220])
        page.Goal = 100
        page.Money = 65
        page.is_boss_fight = False

        self.assertEqual(page._apply_insurance_if_needed("lose", "last_turn"), ("win", "insurance"))
        self.assertEqual(game_state.get_insurance_goal_debt(), 35)

        game_state.insurance_goal_debt = 0
        page.is_boss_fight = True
        self.assertEqual(page._apply_insurance_if_needed("lose", "last_turn"), ("lose", "last_turn"))
        self.assertEqual(game_state.get_insurance_goal_debt(), 0)

    def test_victory_rewards_and_bill_effects_stack(self):
        page = self._page(silver=[215, 217, 218, 219])

        page._apply_bill_of_exchange_shop_discount()
        page._apply_obligation_win_bonus()

        self.assertEqual(game_state.pending_shop_discount_percent, 50)
        self.assertEqual(game_state.napoleondors, 30)

    def test_duplicate_obligations_each_award_their_full_bonus(self):
        page = self._page(silver=[218, 218])

        page._apply_obligation_win_bonus()

        self.assertEqual(game_state.napoleondors, 20)

    def test_silver_manipulation_applies_again_on_each_qualifying_turn(self):
        page = self._page(silver=[212])
        page.Aquantity = 2
        page.Cquantity = 1
        page.c_price_fell_this_resolution = True
        page.manipulation_applied_this_resolution = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_manipulation_effect_if_needed())
        self.assertEqual(page.Aquantity, 6)
        self.assertFalse(page._apply_manipulation_effect_if_needed())
        self.assertEqual(page.Aquantity, 6)

        page.c_price_fell_this_resolution = True
        page.manipulation_applied_this_resolution = False
        self.assertTrue(page._apply_manipulation_effect_if_needed())
        self.assertEqual(page.Aquantity, 10)
        self.assertEqual(page._start_card_jump_animation.call_count, 2)

    def test_silver_manipulation_stacks_multiple_copies(self):
        page = self._page(silver=[212, 212])
        page.Aquantity = 2
        page.Cquantity = 1
        page.c_price_fell_this_resolution = True
        page.manipulation_applied_this_resolution = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_manipulation_effect_if_needed())

        self.assertEqual(page.Aquantity, 10)
        self.assertEqual(page._start_card_jump_animation.call_count, 2)

    def test_silver_manipulation_requires_owned_c_and_an_actual_c_fall(self):
        page = self._page(silver=[212])
        page.Aquantity = 2
        page.Cquantity = 0
        page.c_price_fell_this_resolution = True
        page.manipulation_applied_this_resolution = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertFalse(page._apply_manipulation_effect_if_needed())
        page.Cquantity = 1
        page.c_price_fell_this_resolution = False
        self.assertFalse(page._apply_manipulation_effect_if_needed())
        self.assertEqual(page.Aquantity, 2)
        page._start_card_jump_animation.assert_not_called()

    def test_issue_price_sets_only_a_starting_price_to_six(self):
        page = self._page(gold=[421])
        page.Aprice = page.BPrice = page.CPrice = 2

        self.assertTrue(page._apply_issue_price_start())
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (6, 2, 2))

        page.active_gold_cards = []
        page.Aprice = 2
        self.assertFalse(page._apply_issue_price_start())
        self.assertEqual(page.Aprice, 2)

    def test_markdown_reduces_only_third_and_fourth_regular_round_goals(self):
        for round_num, expected_goal in ((1, 100), (2, 100), (3, 70), (4, 70), (5, 100)):
            with self.subTest(round_num=round_num):
                page = self._page(gold=[422])
                page.Goal = 100
                page.round_num = round_num
                page.is_boss_fight = False

                applied = page._apply_markdown_goal_modifier()

                self.assertEqual(applied, round_num in (3, 4))
                self.assertEqual(page.Goal, expected_goal)

    def test_markdown_never_reduces_a_boss_round_goal(self):
        page = self._page(gold=[422])
        page.Goal = 100
        page.round_num = 3
        page.is_boss_fight = True

        self.assertFalse(page._apply_markdown_goal_modifier())
        self.assertEqual(page.Goal, 100)

    def test_duplicate_markdown_reduces_eligible_goal_by_sixty_percent(self):
        page = self._page(gold=[422, 422])
        page.Goal = 100
        page.round_num = 3
        page.is_boss_fight = False

        self.assertTrue(page._apply_markdown_goal_modifier())
        self.assertEqual(page.Goal, 40)

    def test_volatility_cards_modify_all_market_steps_and_use_their_synergy(self):
        cases = (
            ([424], 2, (4, 6, 8)),
            ([425], 4, (6, 8, 10)),
            ([424, 425], 10, (12, 14, 16)),
            ([424, 424, 425], 12, (14, 16, 18)),
            ([], 0, (2, 4, 6)),
        )
        for gold_cards, expected_bonus, expected_steps in cases:
            with self.subTest(gold_cards=gold_cards):
                page = self._page(gold=gold_cards)
                page.StepA, page.StepB, page.StepC = 2, 4, 6

                self.assertEqual(page._apply_volatility_steps(), expected_bonus)
                self.assertEqual((page.StepA, page.StepB, page.StepC), expected_steps)

    def test_bear_flat_insider_and_gambling_contracts(self):
        page = self._page(gold=[401, 404, 405, 406])
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertEqual(game_state.get_bear_goal_discount_percent([401]), 2)
        self.assertTrue(game_state.record_bear_victory([401]))
        self.assertEqual(game_state.get_bear_goal_discount_percent([401]), 4)
        self.assertTrue(page._is_flat_random_active())
        self.assertEqual(page._get_gambling_probability_bonus(), gameplay_page.GAMBLING_PROBABILITY_BONUS)
        self.assertTrue(page._consume_insider_c_growth_turn())
        self.assertEqual(page.insider_c_growth_turns_remaining, 1)

    def test_duplicate_count_based_gold_cards_stack_their_full_values(self):
        self.assertEqual(game_state.get_bear_goal_discount_percent([401, 401]), 4)

        grant_page = self._page(gold=[403, 403])
        grant_page.Money = 0
        grant_page._apply_grant_start_money_bonus()
        self.assertEqual(grant_page.Money, 16)

        gambling_page = self._page(gold=[406, 406])
        self.assertEqual(gambling_page._get_gambling_probability_bonus(), 14)

        catalyst_page = self._page(gold=[414, 414])
        self.assertEqual(catalyst_page._get_gold_catalyst_percentage_bonus(), 30)

        stewardship_page = self._page(gold=[407, 423, 423])
        stewardship_page.rebate_a_fall_bonus_percent = 0
        stewardship_page.side_cards_top = []
        stewardship_page.hand_cards = [100]
        self.assertEqual(stewardship_page._get_current_rebate_sale_percent(), 170)

    def test_windfall_adds_fifty_points_per_boss_victory_after_rebate_synergies(self):
        page = self._page(silver=[201], gold=[407, 407, 426])
        page.is_boss_fight = True
        page.rebate_a_fall_bonus_percent = 0
        page.side_cards_top = [110]
        page.hand_cards = []

        self.assertTrue(page._record_windfall_boss_victory_progress())
        self.assertTrue(page._record_windfall_boss_victory_progress())
        self.assertEqual(game_state.get_windfall_boss_victories(), 2)

        # Two gold Rebates with red and silver synergies total 180%, then
        # Windfall adds 100 percentage points for two boss victories.
        self.assertEqual(page._get_current_rebate_sale_percent(), 280)

        page.active_gold_cards.append(426)
        self.assertEqual(page._get_current_rebate_sale_percent(), 380)

    def test_windfall_progress_requires_a_boss_fight_and_an_active_card(self):
        page = self._page(gold=[426])
        page.is_boss_fight = False
        self.assertFalse(page._record_windfall_boss_victory_progress())

        page.is_boss_fight = True
        page.active_gold_cards = []
        self.assertFalse(page._record_windfall_boss_victory_progress())
        self.assertEqual(game_state.get_windfall_boss_victories(), 0)

    def test_risk_premium_records_h_round_immediately_and_not_on_restore(self):
        page = self._page(gold=[431])
        page.difficulty = "h"
        page._initial_saved_state = None

        self.assertTrue(page._apply_risk_premium_round_start_bonus())
        self.assertEqual(game_state.get_risk_premium_card_bonus_percent(), 10)

        resumed = self._page(gold=[431])
        resumed.difficulty = "h"
        resumed._initial_saved_state = {"Day": 1}
        self.assertFalse(resumed._apply_risk_premium_round_start_bonus())
        self.assertEqual(game_state.get_risk_premium_card_bonus_percent(), 10)

    def test_risk_premium_ignores_non_h_rounds_and_requires_an_active_copy(self):
        page = self._page(gold=[431])
        page.difficulty = "m"
        page._initial_saved_state = None
        self.assertFalse(page._apply_risk_premium_round_start_bonus())

        page.active_gold_cards = []
        page.difficulty = "h"
        self.assertFalse(page._apply_risk_premium_round_start_bonus())
        self.assertEqual(game_state.get_risk_premium_card_bonus_percent(), 0)

    def test_risk_premium_adds_ten_per_h_round_for_each_active_copy(self):
        game_state.risk_premium_h_rounds = 2
        page = self._page(gold=[407, 431])
        page.rebate_a_fall_bonus_percent = 0
        page.side_cards_top = []
        page.hand_cards = []

        self.assertEqual(page._get_risk_premium_rebate_bonus_percent(), 20)
        self.assertEqual(page._get_current_rebate_sale_percent(), 150)

        page.active_gold_cards.append(431)
        self.assertEqual(page._get_risk_premium_rebate_bonus_percent(), 40)
        self.assertEqual(page._get_current_rebate_sale_percent(), 170)

    def test_risk_premium_field_description_shows_current_bonus(self):
        game_state.risk_premium_h_rounds = 2
        page = self._page(gold=[431])

        title, description = page._get_field_card_tooltip_content(431)

        self.assertEqual(title, "Risk Premium")
        self.assertIn("Текущий бонус карты: +20%", description)

    def test_gold_disclosure_stacks_only_with_probability_effects(self):
        page = self._page(gold=[427, 427])

        self.assertEqual(page._get_disclosure_probability_bonus(), 4)
        self.assertEqual(page._get_probability_amplifier_bonus(), 4)
        self.assertEqual(page._get_probability_card_bonus(), 4)
        self.assertEqual(page._get_percentage_amplifier_bonus(), 0)

        gambling_page = self._page(gold=[406, 427])
        self.assertEqual(gambling_page._get_gambling_probability_bonus(), 9)
        self.assertEqual(gambling_page._get_probability_card_bonus(), 11)

    def test_gold_disclosure_increases_advance_chance(self):
        page = self._page(gold=[420, 427])
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 0, 0
        page.lifecycle_card_jump_animations = {}

        with mock.patch("gameplay_page.random.randint", return_value=17):
            self.assertEqual(len(page._build_advance_movements()), 1)
        with mock.patch("gameplay_page.random.randint", return_value=18):
            self.assertEqual(page._build_advance_movements(), [])

    def test_duplicate_insider_adds_two_c_growth_movements_on_each_active_turn(self):
        page = self._page(gold=[404, 405, 405])
        page.Day = 1
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        movements = page.update_stock_prices()
        c_movements = [entry for entry in movements if entry["market"] == 2]

        self.assertEqual(
            [(entry["type"], entry["price_change"]) for entry in c_movements],
            [("rise", 6), ("rise", 6)],
        )
        self.assertEqual(
            [(entry.get("source"), entry.get("card_slot")) for entry in c_movements],
            [("insider", 1), ("insider", 2)],
        )
        self.assertEqual(page.insider_c_growth_turns_remaining, 1)

    def test_insider_jumps_only_when_c_growth_animation_starts(self):
        page = self._page(gold=[404, 405])
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.Day = 1
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page._apply_price_change = mock.Mock(return_value=False)
        page.typewriter_sound = None

        page.price_animation_queue = page.update_stock_prices()
        page._start_card_jump_animation.assert_not_called()

        self.assertTrue(page._start_next_price_animation(now=100))
        page._start_card_jump_animation.assert_not_called()
        self.assertTrue(page._start_next_price_animation(now=200))
        page._start_card_jump_animation.assert_not_called()
        self.assertTrue(page._start_next_price_animation(now=300))
        page._start_card_jump_animation.assert_called_once_with(
            page.lifecycle_card_jump_animations,
            1,
        )

    def test_catalyst_strengthens_bear_gambling_bill_rebate_and_uptrend(self):
        page = self._page(silver=[210, 215], gold=[401, 406, 407, 410])
        page.Goal = 100
        page.rebate_a_fall_bonus_percent = 0
        page.side_cards_top = []

        self.assertEqual(page._get_catalyst_percentage_bonus(), 10)
        self.assertEqual(page._get_gambling_probability_bonus(), 17)
        self.assertEqual(page._get_probability_card_bonus(), 27)

        page._apply_bear_goal_modifier()
        self.assertEqual(page.Goal, 88)

        page._apply_bill_of_exchange_shop_discount()
        self.assertEqual(game_state.pending_shop_discount_percent, 60)

        game_state.napoleondors = 5
        self.assertEqual(page._get_uptrend_rebate_bonus_percent(), 20)
        self.assertEqual(page._get_current_rebate_sale_percent(), 160)

    def test_each_downside_risk_copy_guarantees_two_drop_cards(self):
        page = self._page(gold=[433, 433])

        self.assertEqual(page._get_downside_risk_guaranteed_drop_count(), 4)

    def test_gold_catalyst_stacks_with_silver_catalyst_for_twenty_five_points(self):
        page = self._page(silver=[210, 215], gold=[401, 406, 407, 410, 414])
        page.Goal = 100
        page.rebate_a_fall_bonus_percent = 0
        page.side_cards_top = []

        self.assertEqual(page._get_gold_catalyst_percentage_bonus(), 15)
        self.assertEqual(page._get_percentage_amplifier_bonus(), 25)
        self.assertEqual(page._get_gambling_probability_bonus(), 32)
        self.assertEqual(page._get_probability_card_bonus(), 57)

        page._apply_bear_goal_modifier()
        self.assertEqual(page.Goal, 73)

        page._apply_bill_of_exchange_shop_discount()
        self.assertEqual(game_state.pending_shop_discount_percent, 75)

        game_state.napoleondors = 5
        self.assertEqual(page._get_uptrend_rebate_bonus_percent(), 35)
        self.assertEqual(page._get_current_rebate_sale_percent(), 190)

    @staticmethod
    def _short_seller_page():
        page = LifecycleEffectTests._page(silver=[211])
        page.is_boss_fight = False
        page.Money = 1
        page.Aquantity, page.Bquantity, page.Cquantity = 5, 0, 0
        page.Aprice, page.BPrice, page.CPrice = 8, 12, 14
        page.short_seller_fall_counts = [0, 0, 0]
        page.short_seller_counted_markets_this_resolution = set()
        page.lifecycle_card_jump_animations = {}
        page._finish_short_seller_victory = mock.Mock(return_value=True)
        return page

    def test_short_seller_wins_after_five_qualifying_falls_of_one_market(self):
        page = self._short_seller_page()

        for expected_count in range(1, 5):
            self.assertFalse(page._record_short_seller_falls((10, 12, 14), "test"))
            self.assertEqual(page.short_seller_fall_counts, [expected_count, 0, 0])
            page.short_seller_counted_markets_this_resolution = set()
        self.assertTrue(page._record_short_seller_falls((10, 12, 14), "test"))

        self.assertEqual(page.short_seller_fall_counts, [5, 0, 0])
        page._finish_short_seller_victory.assert_called_once_with()

    def test_short_seller_requires_one_market_and_no_affordable_share(self):
        page = self._short_seller_page()
        page.Money = 10
        self.assertFalse(page._record_short_seller_falls((10, 12, 14), "cash remains"))

        page.Money = 9
        page.Bquantity = 1
        self.assertFalse(page._record_short_seller_falls((10, 12, 14), "two markets"))

        page.Bquantity = 0
        page.Aprice = 10
        page.BPrice = 10
        self.assertFalse(page._record_short_seller_falls((10, 12, 14), "other market fell"))
        self.assertEqual(page.short_seller_fall_counts, [0, 0, 0])

    def test_short_seller_does_not_combine_different_markets(self):
        page = self._short_seller_page()
        for _ in range(3):
            page._record_short_seller_falls((10, 12, 14), "A fall")
            page.short_seller_counted_markets_this_resolution = set()

        page.Aquantity, page.Bquantity = 0, 5
        page.Aprice, page.BPrice = 10, 10
        for _ in range(2):
            page._record_short_seller_falls((10, 12, 14), "B fall")
            page.short_seller_counted_markets_this_resolution = set()

        self.assertEqual(page.short_seller_fall_counts, [3, 2, 0])
        page._finish_short_seller_victory.assert_not_called()

    def test_short_seller_counts_at_most_one_fall_per_turn(self):
        page = self._short_seller_page()

        self.assertFalse(page._record_short_seller_falls((10, 12, 14), "natural fall"))
        self.assertFalse(page._record_short_seller_falls((10, 12, 14), "momentum fall"))

        self.assertEqual(page.short_seller_fall_counts, [1, 0, 0])

    def test_short_seller_is_disabled_in_boss_fights(self):
        page = self._short_seller_page()
        page.is_boss_fight = True
        page.short_seller_fall_counts = [4, 0, 0]

        self.assertFalse(page._record_short_seller_falls((10, 12, 14), "boss fall"))
        self.assertEqual(page.short_seller_fall_counts, [4, 0, 0])
        page._finish_short_seller_victory.assert_not_called()

    def test_short_seller_is_connected_to_actual_market_price_changes(self):
        page = self._short_seller_page()
        page.short_seller_fall_counts = [4, 0, 0]
        page.Aprice = 10

        self.assertTrue(page._apply_price_change(0, -2))
        self.assertEqual(page.Aprice, 8)
        self.assertEqual(page.short_seller_fall_counts, [5, 0, 0])
        page._finish_short_seller_victory.assert_called_once_with()

    def test_catalyst_adds_ten_points_to_golden_stocks_roll_without_storing_them(self):
        original_chance = game_state.golden_stocks_chance_percent
        original_triggered = game_state.golden_stocks_triggered
        original_trigger_count = game_state.golden_stocks_trigger_count
        original_gold_cards = list(game_state.gold_cards)
        try:
            game_state.golden_stocks_chance_percent = 10
            game_state.golden_stocks_triggered = False
            game_state.golden_stocks_trigger_count = 0
            game_state.gold_cards = []
            with (
                mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[402]),
                mock.patch.object(game_state.random, "randint", return_value=15),
                mock.patch.object(game_state.random, "choice", return_value=402),
            ):
                self.assertEqual(
                    game_state.resolve_golden_stocks_round([302, 210], chance_bonus=10),
                    402,
                )
            self.assertEqual(game_state.golden_stocks_chance_percent, 10)
            self.assertEqual(game_state.golden_stocks_trigger_count, 1)
        finally:
            game_state.golden_stocks_chance_percent = original_chance
            game_state.golden_stocks_triggered = original_triggered
            game_state.golden_stocks_trigger_count = original_trigger_count
            game_state.gold_cards = original_gold_cards

    def test_golden_stocks_miss_adds_two_points_and_success_is_counted(self):
        original_chance = game_state.golden_stocks_chance_percent
        original_triggered = game_state.golden_stocks_triggered
        original_trigger_count = game_state.golden_stocks_trigger_count
        original_gold_cards = list(game_state.gold_cards)
        try:
            game_state.golden_stocks_chance_percent = 10
            game_state.golden_stocks_triggered = False
            game_state.golden_stocks_trigger_count = 0
            game_state.gold_cards = []
            with (
                mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[402]),
                mock.patch.object(game_state.random, "randint", return_value=50),
            ):
                self.assertIsNone(game_state.resolve_golden_stocks_round([302]))

            self.assertEqual(game_state.golden_stocks_chance_percent, 12)
            self.assertEqual(game_state.golden_stocks_trigger_count, 0)

            with (
                mock.patch.object(game_state, "build_golden_stocks_reward_pool", return_value=[402]),
                mock.patch.object(game_state.random, "randint", return_value=12),
                mock.patch.object(game_state.random, "choice", return_value=402),
            ):
                self.assertEqual(game_state.resolve_golden_stocks_round([302]), 402)

            self.assertEqual(game_state.golden_stocks_trigger_count, 1)
        finally:
            game_state.golden_stocks_chance_percent = original_chance
            game_state.golden_stocks_triggered = original_triggered
            game_state.golden_stocks_trigger_count = original_trigger_count
            game_state.gold_cards = original_gold_cards

    def test_golden_stocks_legacy_chance_is_raised_to_new_minimum(self):
        original_chance = game_state.golden_stocks_chance_percent
        try:
            game_state.golden_stocks_chance_percent = 5
            self.assertEqual(game_state.get_golden_stocks_chance_percent(), 10)
        finally:
            game_state.golden_stocks_chance_percent = original_chance

    def test_gold_momentum_repeats_rises_and_falls_including_forced_growth(self):
        page = self._page(gold=[409])
        movements = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 1, "type": "fall", "price_change": -3},
            {"market": 2, "type": "rise", "price_change": 4},
        ]

        expected = [
            movements[0],
            {**movements[0], "source": "momentum"},
            movements[1],
            {**movements[1], "source": "momentum"},
            movements[2],
            {**movements[2], "source": "momentum"},
        ]
        self.assertEqual(page._apply_momentum_to_random_movements(movements), expected)

    def test_momentum_repeats_insider_growth_on_both_active_turns(self):
        page = self._page(gold=[404, 405, 409])
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        for day, remaining in ((1, 1), (2, 0)):
            with self.subTest(day=day):
                page.Day = day
                movements = page.update_stock_prices()
                c_movements = [entry for entry in movements if entry["market"] == 2]

                self.assertEqual(
                    [(entry["type"], entry["price_change"]) for entry in c_movements],
                    [("rise", 6), ("rise", 6)],
                )
                self.assertEqual(c_movements[1].get("source"), "momentum")
                self.assertEqual(page.insider_c_growth_turns_remaining, remaining)

    def test_duplicate_momentum_repeats_each_qualifying_movement_twice(self):
        page = self._page(gold=[409, 409])
        movement = {"market": 0, "type": "rise", "price_change": 2}

        self.assertEqual(
            page._apply_momentum_to_random_movements([movement]),
            [
                movement,
                {**movement, "source": "momentum"},
                {**movement, "source": "momentum"},
            ],
        )

    def test_momentum_is_inactive_when_not_selected(self):
        page = self._page()
        movements = [{"market": 0, "type": "rise", "price_change": 2}]

        self.assertEqual(page._apply_momentum_to_random_movements(movements), movements)

    def test_spoofing_targets_only_held_stocks_on_turn_four(self):
        page = self._page(gold=[411])
        page.Day = 4
        page.Aquantity = 3
        page.Bquantity = 0
        page.Cquantity = 1
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertEqual(page._get_spoofing_forced_rise_markets(), {0, 2})
        page._start_card_jump_animation.assert_called_once()

        page.Day = 3
        self.assertEqual(page._get_spoofing_forced_rise_markets(), set())

    def test_spoofing_cards_shake_at_the_start_of_their_trigger_turns(self):
        page = self._page(gold=[411, 412])
        page.Day = 4
        page.lifecycle_card_shake_animations = {}
        page.lifecycle_reminder_days_started = set()

        self.assertEqual(page._start_lifecycle_turn_reminder(now=100), [0, 1])
        self.assertEqual(set(page.lifecycle_card_shake_animations), {0, 1})
        self.assertEqual(page._start_lifecycle_turn_reminder(now=200), [])

        page.Day = 8
        self.assertEqual(page._start_lifecycle_turn_reminder(now=300), [1])
        self.assertEqual(page.lifecycle_reminder_days_started, {4, 8})

    def test_insider_shakes_at_the_start_of_its_first_two_turns(self):
        page = self._page(gold=[405])
        page.Day = 1
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_shake_animations = {}
        page.lifecycle_reminder_days_started = set()

        self.assertEqual(page._start_lifecycle_turn_reminder(now=100), [0])
        self.assertEqual(page._start_lifecycle_turn_reminder(now=200), [])

        page.Day = 2
        page.insider_c_growth_turns_remaining = 1
        self.assertEqual(page._start_lifecycle_turn_reminder(now=300), [0])
        self.assertEqual(page.lifecycle_reminder_days_started, {1, 2})

        page.Day = 3
        self.assertEqual(page._start_lifecycle_turn_reminder(now=400), [])

    def test_spoofing_reminder_shakes_without_using_effect_jump_animation(self):
        page = self._page(gold=[411])
        page.Day = 4
        page.lifecycle_card_shake_animations = {}
        page.lifecycle_reminder_days_started = set()
        page.lifecycle_card_jump_animations = {}

        page._start_lifecycle_turn_reminder(now=100)

        self.assertEqual(page._get_lifecycle_card_shake_offset(0, now=100), (-6, 0))
        self.assertEqual(page.lifecycle_card_jump_animations, {})
        self.assertEqual(page.update_lifecycle_card_shake_animations(now=2299), [])
        self.assertEqual(page.update_lifecycle_card_shake_animations(now=2300), [0])
        self.assertEqual(page.lifecycle_card_shake_animations, {})

    def test_spoofing_overrides_flat_for_held_stocks_only(self):
        page = self._page(gold=[404, 411])
        page.Day = 4
        page.Aquantity = 2
        page.Bquantity = 0
        page.Cquantity = 1
        page.Aprice = page.BPrice = page.CPrice = 10
        page.StepA = 2
        page.StepB = 3
        page.StepC = 4
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        movements = page.update_stock_prices()

        self.assertEqual(
            [(entry["market"], entry["type"], entry["price_change"]) for entry in movements],
            [(0, "rise", 2), (1, "unchanged", 0), (2, "rise", 4)],
        )

    def test_spoofing_plus_triggers_on_turns_four_and_eight_only(self):
        page = self._page(gold=[412])
        page.Aquantity = 1
        page.Bquantity = 2
        page.Cquantity = 0
        page.LastTurn = 8
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        for day in (4, 8):
            page.Day = day
            self.assertEqual(page._get_spoofing_forced_rise_markets(), {0, 1})

        page.LastTurn = 7
        page.Day = 7
        self.assertEqual(page._get_spoofing_forced_rise_markets(), set())
        self.assertEqual(page._start_card_jump_animation.call_count, 2)

    def test_momentum_repeats_spoofing_guaranteed_growth(self):
        page = self._page(gold=[404, 409, 412])
        page.Day = 4
        page.Aquantity = 2
        page.Bquantity = 0
        page.Cquantity = 1
        page.StepA = 2
        page.StepB = 3
        page.StepC = 4
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        movements = page.update_stock_prices()

        self.assertEqual(
            [
                (entry["market"], entry["type"], entry["price_change"], entry.get("source"))
                for entry in movements
            ],
            [
                (0, "rise", 2, None),
                (0, "rise", 2, "momentum"),
                (1, "unchanged", 0, None),
                (2, "rise", 4, None),
                (2, "rise", 4, "momentum"),
            ],
        )

    def test_duplicate_spoofing_growths_are_each_repeated_by_momentum(self):
        page = self._page(gold=[404, 409, 411, 411])
        page.Day = 4
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 0, 0
        page.StepA, page.StepB, page.StepC = 2, 3, 4
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        movements = page.update_stock_prices()
        a_rises = [entry for entry in movements if entry["market"] == 0]

        self.assertEqual(len(a_rises), 4)
        self.assertEqual([entry.get("source") for entry in a_rises], [None, "momentum", "spoofing", "momentum"])

    def test_selling_pressure_forces_one_market_fall_and_jumps_with_that_graph(self):
        page = self._page(gold=[404, 432])
        page.Day = 1
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page._apply_price_change = mock.Mock(return_value=False)
        page.typewriter_sound = None

        with mock.patch.object(gameplay_page.random, "randint", return_value=2):
            page.price_animation_queue = page.update_stock_prices()

        self.assertEqual(
            [
                (entry["market"], entry["type"], entry["price_change"], entry.get("source"))
                for entry in page.price_animation_queue
            ],
            [
                (0, "unchanged", 0, None),
                (1, "fall", -4, "selling_pressure"),
                (2, "unchanged", 0, None),
            ],
        )
        self.assertTrue(page._start_next_price_animation(now=100))
        page._start_card_jump_animation.assert_not_called()
        self.assertTrue(page._start_next_price_animation(now=200))
        page._start_card_jump_animation.assert_called_once_with(
            page.lifecycle_card_jump_animations,
            1,
        )

    def test_duplicate_selling_pressure_cards_each_force_a_fall(self):
        page = self._page(gold=[432, 432])
        page.Day = 1
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        with mock.patch.object(gameplay_page.random, "randint", side_effect=[1, 1]) as roll:
            movements = page.update_stock_prices()

        a_falls = [entry for entry in movements if entry["market"] == 0]
        self.assertEqual(roll.call_count, 2)
        self.assertEqual(
            [(entry["type"], entry["price_change"], entry.get("card_slot")) for entry in a_falls],
            [("fall", -2, 0), ("fall", -2, 1)],
        )

    def test_selling_pressure_and_insider_both_resolve_on_market_c(self):
        page = self._page(gold=[404, 405, 432])
        page.Day = 1
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page.StepA, page.StepB, page.StepC = 2, 4, 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 2
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        with mock.patch.object(gameplay_page.random, "randint", return_value=3):
            movements = page.update_stock_prices()

        c_movements = [entry for entry in movements if entry["market"] == 2]
        self.assertEqual(
            [(entry["type"], entry["price_change"], entry.get("source")) for entry in c_movements],
            [("fall", -6, "selling_pressure"), ("rise", 6, "insider")],
        )

    def test_shakeout_targets_only_markets_without_player_shares(self):
        page = self._page(gold=[413])
        page.Aquantity = 2
        page.Bquantity = 0
        page.Cquantity = 0

        self.assertEqual(page._get_shakeout_markets(), {1, 2})

        page.active_gold_cards = []
        self.assertEqual(page._get_shakeout_markets(), set())

    def test_surge_triples_a_after_any_four_consecutive_turns_without_trades(self):
        page = self._page(gold=[404, 415])
        page.Day = 7
        page.surge_turns_without_trade = 3
        page.surge_traded_this_turn = False
        page.surge_triggered = False
        page.Aquantity = 2
        page.Bquantity = 0
        page.Cquantity = 0
        page.Aprice = 8
        page.BPrice = 10
        page.CPrice = 12
        page.StepA = 2
        page.StepB = 4
        page.StepC = 6
        page.market_cards = {0: {}, 1: {}, 2: {}}
        page.insider_c_growth_turns_remaining = 0
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.typewriter_sound = None

        movements = page.update_stock_prices()

        self.assertEqual(movements[-1].get("source"), "surge")
        page.price_animation_queue = [movements[-1]]
        self.assertTrue(page._start_next_price_animation(now=100))
        self.assertEqual(page.Aprice, 24)
        self.assertEqual(page.current_price_animation["type"], "rise")

    def test_surge_counter_resets_on_trade_and_can_trigger_later(self):
        page = self._page(gold=[415])
        page.surge_turns_without_trade = 0
        page.surge_traded_this_turn = False
        page.surge_triggered = False

        self.assertFalse(page._advance_surge_counter())
        self.assertFalse(page._advance_surge_counter())
        self.assertEqual(page.surge_turns_without_trade, 2)

        page.surge_traded_this_turn = True
        self.assertFalse(page._advance_surge_counter())
        self.assertEqual(page.surge_turns_without_trade, 0)

        for _ in range(3):
            self.assertFalse(page._advance_surge_counter())
        self.assertTrue(page._advance_surge_counter())
        self.assertTrue(page.surge_triggered)

        self.assertFalse(page._advance_surge_counter())

    def test_duplicate_surge_applies_each_triple_multiplier(self):
        page = self._page(gold=[415, 415])
        page.Aprice, page.BPrice, page.CPrice = 8, 10, 12
        page.price_animation_queue = [
            {"market": 0, "type": "rise", "price_change": 0, "source": "surge"}
        ]
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.typewriter_sound = None

        self.assertTrue(page._start_next_price_animation(now=100))
        self.assertEqual(page.Aprice, 72)

    def test_advance_doubles_owned_markets_and_uses_catalyst_bonus(self):
        page = self._page(silver=[210], gold=[420])
        page.Aquantity, page.Bquantity, page.Cquantity = 2, 0, 1
        page.Aprice, page.BPrice, page.CPrice = 10, 20, 30
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.typewriter_sound = None

        with mock.patch("gameplay_page.random.randint", return_value=25) as roll:
            movements = page._build_advance_movements()

        roll.assert_called_once_with(1, 100)
        self.assertEqual(
            movements,
            [
                {
                    "market": (0, 2),
                    "type": "rise",
                    "price_change": 0,
                    "source": "advance",
                    "card_slot": 1,
                }
            ],
        )
        page.price_animation_queue = movements
        self.assertTrue(page._start_next_price_animation(now=100))
        self.assertEqual((page.Aprice, page.BPrice, page.CPrice), (20, 20, 60))
        page._start_card_jump_animation.assert_called_once_with(
            page.lifecycle_card_jump_animations,
            1,
        )

    def test_advance_combines_both_catalysts_and_can_miss(self):
        page = self._page(silver=[210], gold=[414, 420])
        page.Aquantity = page.Bquantity = page.Cquantity = 1
        page.lifecycle_card_jump_animations = {}

        with mock.patch("gameplay_page.random.randint", return_value=41) as roll:
            self.assertEqual(page._build_advance_movements(), [])

        roll.assert_called_once_with(1, 100)

    def test_advance_does_not_roll_without_owned_stocks(self):
        page = self._page(gold=[420])
        page.Aquantity = page.Bquantity = page.Cquantity = 0

        with mock.patch("gameplay_page.random.randint") as roll:
            self.assertEqual(page._build_advance_movements(), [])

        roll.assert_not_called()

    def test_duplicate_advance_rolls_and_doubles_independently(self):
        page = self._page(gold=[420, 420])
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 0, 0
        page.Aprice = page.BPrice = page.CPrice = 10
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.typewriter_sound = None

        with mock.patch("gameplay_page.random.randint", return_value=1) as roll:
            movements = page._build_advance_movements()

        self.assertEqual(roll.call_count, 2)
        self.assertEqual(len(movements), 2)
        page.price_animation_queue = movements
        self.assertTrue(page._start_next_price_animation(now=100))
        self.assertTrue(page._start_next_price_animation(now=200))
        self.assertEqual(page.Aprice, 40)

    def test_sideway_rewards_all_flat_base_market_results_once(self):
        page = self._page(gold=[416])
        page.stock_price_turn_results = [
            {"market": 0, "type": "unchanged", "price_change": 0},
            {"market": 1, "type": "unchanged", "price_change": 0},
            {"market": 2, "type": "unchanged", "price_change": 0},
            {"market": 0, "type": "rise", "price_change": 2, "source": "surge"},
        ]
        page.sideway_applied_this_resolution = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_sideway_reward_if_needed())
        self.assertEqual(game_state.napoleondors, 5)
        self.assertFalse(page._apply_sideway_reward_if_needed())
        self.assertEqual(game_state.napoleondors, 5)
        page._start_card_jump_animation.assert_called_once_with(
            page.lifecycle_card_jump_animations,
            0,
        )

    def test_sideway_does_not_reward_when_any_base_market_moved(self):
        page = self._page(gold=[416])
        page.stock_price_turn_results = [
            {"market": 0, "type": "unchanged", "price_change": 0},
            {"market": 1, "type": "rise", "price_change": 2},
            {"market": 2, "type": "unchanged", "price_change": 0},
        ]
        page.sideway_applied_this_resolution = False

        self.assertFalse(page._apply_sideway_reward_if_needed())
        self.assertEqual(game_state.napoleondors, 0)

    def test_duplicate_sideway_awards_ten_napoleondors(self):
        page = self._page(gold=[416, 416])
        page.stock_price_turn_results = [
            {"market": market, "type": "unchanged", "price_change": 0}
            for market in range(3)
        ]
        page.sideway_applied_this_resolution = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_sideway_reward_if_needed())
        self.assertEqual(game_state.napoleondors, 10)

    def test_full_deployment_requires_empty_deck_and_empty_hand(self):
        page = self._page(gold=[428])
        page.deck = [11]
        page.hand_cards = [12, None]
        page.full_deployment_reward_applied = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertEqual(page._draw_next_deck_card(), 11)
        self.assertEqual(game_state.napoleondors, 0)
        self.assertFalse(page._apply_full_deployment_reward_if_needed())

        page.hand_cards = [None, None]
        self.assertTrue(page._apply_full_deployment_reward_if_needed())
        self.assertEqual(game_state.napoleondors, 7)
        self.assertTrue(page.full_deployment_reward_applied)
        self.assertFalse(page._apply_full_deployment_reward_if_needed())
        self.assertEqual(game_state.napoleondors, 7)
        page._start_card_jump_animation.assert_called_once_with(
            page.lifecycle_card_jump_animations,
            0,
        )

    def test_duplicate_full_deployment_awards_fourteen_napoleondors(self):
        page = self._page(gold=[428, 428])
        page.deck = []
        page.hand_cards = []
        page.full_deployment_reward_applied = False
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._apply_full_deployment_reward_if_needed())

        self.assertEqual(game_state.napoleondors, 14)
        self.assertEqual(page._start_card_jump_animation.call_count, 2)

    def test_waterloo_stores_the_roll_without_ending_the_turn(self):
        page = self._page(gold=[430])
        page.waterloo_preview_movements = None
        page.lifecycle_card_scale_animations = {}
        movements = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 1, "type": "fall", "price_change": -4},
            {"market": 2, "type": "unchanged", "price_change": 0},
        ]
        page.update_stock_prices = mock.Mock(return_value=movements)
        page._reset_boss_turn_timer = mock.Mock()
        page._save_active_game = mock.Mock()

        with mock.patch.object(gameplay_page.random, "randint", return_value=25):
            self.assertTrue(page._try_start_waterloo_preview())

        self.assertEqual(page.waterloo_preview_movements, movements)
        page.update_stock_prices.assert_called_once_with()
        page._reset_boss_turn_timer.assert_called_once_with()
        page._save_active_game.assert_called_once_with()
        self.assertIn(0, page.lifecycle_card_scale_animations)

    def test_duplicate_waterloo_cards_each_get_a_check(self):
        page = self._page(gold=[430, 430])
        page.waterloo_preview_movements = None
        page.lifecycle_card_scale_animations = {}
        page.update_stock_prices = mock.Mock(return_value=[])
        page._reset_boss_turn_timer = mock.Mock()
        page._save_active_game = mock.Mock()

        with mock.patch.object(gameplay_page.random, "randint", side_effect=[26, 25]) as roll:
            self.assertTrue(page._try_start_waterloo_preview())

        self.assertEqual(roll.call_count, 2)
        self.assertIn(1, page.lifecycle_card_scale_animations)

    def test_waterloo_chance_is_strengthened_by_catalyst_and_disclosure(self):
        page = self._page(silver=[210], gold=[414, 427, 430])

        self.assertEqual(page._get_waterloo_chance(), 52)

    def test_second_waterloo_end_turn_uses_the_saved_roll(self):
        page = self._page(gold=[430])
        movements = [{"market": 2, "type": "rise", "price_change": 6}]
        page.waterloo_preview_movements = movements
        page.update_stock_prices = mock.Mock()

        self.assertEqual(page._take_waterloo_preview_or_roll(), movements)
        self.assertIsNone(page.waterloo_preview_movements)
        page.update_stock_prices.assert_not_called()

    def test_waterloo_forecast_calculates_additive_and_multiplier_movements(self):
        page = self._page(gold=[415, 420, 430])
        page.Aprice, page.BPrice, page.CPrice = 4, 8, 12
        movements = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 1, "type": "fall", "price_change": -10},
            {"market": (0, 2), "type": "rise", "price_change": 0, "source": "advance"},
            {"market": 0, "type": "rise", "price_change": 0, "source": "surge"},
        ]

        self.assertEqual(page._calculate_waterloo_preview_prices(movements), (36, 2, 24))

    def test_continuation_rewards_second_and_later_consecutive_growth(self):
        page = self._page(gold=[419])
        page.Aquantity, page.Bquantity, page.Cquantity = 2, 0, 1
        page.Aprice, page.BPrice, page.CPrice = 12, 10, 16
        page.continuation_growth_streaks = [0, 0, 0]
        page.continuation_held_markets_this_turn = {0, 2}
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.stock_price_turn_results = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 1, "type": "unchanged", "price_change": 0},
            {"market": 2, "type": "rise", "price_change": 3},
        ]

        self.assertEqual(page._build_continuation_bonus_movements(), [])
        self.assertEqual(page.continuation_growth_streaks, [1, 0, 1])

        movements = page._build_continuation_bonus_movements()

        self.assertEqual(
            movements,
            [
                {"market": 0, "type": "rise", "price_change": 2, "source": "continuation"},
                {"market": 2, "type": "rise", "price_change": 3, "source": "continuation"},
            ],
        )
        self.assertEqual(page.continuation_growth_streaks, [2, 0, 2])
        page._start_card_jump_animation.assert_called_once_with(
            page.lifecycle_card_jump_animations,
            0,
        )

    def test_continuation_counts_momentum_copy_and_resets_interrupted_streaks(self):
        page = self._page(gold=[419])
        page.Aquantity = page.Bquantity = page.Cquantity = 1
        page.Aprice = page.BPrice = page.CPrice = 10
        page.continuation_growth_streaks = [0, 2, 2]
        page.continuation_held_markets_this_turn = {0, 1, 2}
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.stock_price_turn_results = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 0, "type": "rise", "price_change": 2, "source": "momentum"},
            {"market": 1, "type": "unchanged", "price_change": 0},
            {"market": 2, "type": "fall", "price_change": -2},
        ]

        self.assertEqual(
            page._build_continuation_bonus_movements(),
            [{"market": 0, "type": "rise", "price_change": 2, "source": "continuation"}],
        )
        self.assertEqual(page.continuation_growth_streaks, [2, 0, 0])

    def test_continuation_applies_each_momentum_growth_to_an_existing_streak(self):
        page = self._page(gold=[409, 419])
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 0, 0
        page.Aprice = page.BPrice = page.CPrice = 10
        page.continuation_growth_streaks = [1, 0, 0]
        page.continuation_held_markets_this_turn = {0}
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.stock_price_turn_results = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 0, "type": "rise", "price_change": 2, "source": "momentum"},
            {"market": 1, "type": "unchanged", "price_change": 0},
            {"market": 2, "type": "unchanged", "price_change": 0},
        ]

        self.assertEqual(
            page._build_continuation_bonus_movements(),
            [{"market": 0, "type": "rise", "price_change": 4, "source": "continuation"}],
        )
        self.assertEqual(page.continuation_growth_streaks, [3, 0, 0])

    def test_continuation_streak_resets_when_held_shares_are_sold(self):
        page = self._page(gold=[419])
        page.Money = 0
        page.Aquantity, page.Bquantity, page.Cquantity = 2, 1, 0
        page.Aprice = page.BPrice = page.CPrice = 4
        page.continuation_growth_streaks = [3, 2, 0]
        page.surge_turns_without_trade = 2
        page.surge_traded_this_turn = False
        page._is_arrow_disabled = mock.Mock(return_value=False)
        page._blocked_buy_prices = mock.Mock(return_value=set())
        page._check_win_lose = mock.Mock()

        self.assertTrue(page._apply_arrow_trade(0, 2))
        self.assertEqual(page.continuation_growth_streaks, [0, 2, 0])

    def test_duplicate_continuation_applies_both_multipliers(self):
        page = self._page(gold=[419, 419])
        page.Aquantity, page.Bquantity, page.Cquantity = 1, 0, 0
        page.Aprice = page.BPrice = page.CPrice = 10
        page.continuation_growth_streaks = [1, 0, 0]
        page.continuation_held_markets_this_turn = {0}
        page.lifecycle_card_jump_animations = {}
        page._start_card_jump_animation = mock.Mock()
        page.stock_price_turn_results = [
            {"market": 0, "type": "rise", "price_change": 2},
            {"market": 1, "type": "unchanged", "price_change": 0},
            {"market": 2, "type": "unchanged", "price_change": 0},
        ]

        self.assertEqual(
            page._build_continuation_bonus_movements(),
            [{"market": 0, "type": "rise", "price_change": 4, "source": "continuation"}],
        )

    def test_positioning_cards_use_six_card_synergy_limit(self):
        self.assertEqual(get_positioning_selection_limit([417]), 2)
        self.assertEqual(get_positioning_selection_limit([418]), 3)
        self.assertEqual(get_positioning_selection_limit([417, 418]), 6)
        self.assertEqual(get_positioning_selection_limit([]), 0)

    def test_duplicate_positioning_cards_add_their_full_selection_limits(self):
        self.assertEqual(get_positioning_selection_limit([417, 417]), 4)
        self.assertEqual(get_positioning_selection_limit([418, 418]), 6)
        self.assertEqual(get_positioning_selection_limit([417, 417, 418, 418]), 12)

    def test_duplicate_hedger_provides_two_successful_draws(self):
        page = self._page(gold=[408, 408])
        page.hedger_used_this_round = 0
        page.hedger_selected_card_id = None
        page.hedger_confirm_active = False
        page.hedger_message = ""
        page.deck = [11, 12]
        page.hand_cards = [None, None]
        page._save_active_game = mock.Mock()

        self.assertTrue(page._select_hedger_deck_card(page.deck[0]))
        self.assertTrue(page._add_hedger_selected_card_to_hand())
        self.assertTrue(page._select_hedger_deck_card(page.deck[0]))
        self.assertTrue(page._add_hedger_selected_card_to_hand())

        self.assertEqual(page.hand_cards, [11, 12])
        self.assertEqual(page.hedger_used_this_round, 2)
        self.assertFalse(page._is_hedger_available())

    def test_synergies_stay_hidden_in_player_facing_descriptions(self):
        self.assertNotIn("красную Rollover", CARD_TOOLTIPS[208][1])
        self.assertNotIn("серебряной", CARD_TOOLTIPS[402][1])
        self.assertNotIn("серебряную", CARD_TOOLTIPS[403][1])
        self.assertNotIn("серебряной", CARD_DESCRIPTIONS[402])
        self.assertNotIn("серебряную", CARD_DESCRIPTIONS[403])


if __name__ == "__main__":
    unittest.main()
