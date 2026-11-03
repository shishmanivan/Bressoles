import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from gameplay_conditions import BOSS_SHARES, BOSS_TRADING, LEVEL_CONDITIONS, has_condition
from gameplay_page import GameplayPage
from level_routes import get_campaign_content_level


class BossSharesTests(unittest.TestCase):
    def setUp(self):
        # Exercise the reusable condition explicitly, independent of campaign assignments.
        assignment = mock.patch.dict(LEVEL_CONDITIONS, {get_campaign_content_level(6): (BOSS_SHARES,)})
        assignment.start()
        self.addCleanup(assignment.stop)

    def page(self, money=201, goal=150, day=8, boss_fight=False):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = get_campaign_content_level(6)
        page.is_boss_fight = boss_fight
        page.boss_index = 0
        page.Money, page.Goal, page.Day, page.LastTurn = money, goal, day, 8
        page.Aprice, page.BPrice, page.CPrice = 4, 8, 12
        page.Aquantity = page.Bquantity = page.Cquantity = 0
        page._get_current_rebate_sale_percent = mock.Mock(return_value=100)
        page.stock_bot_enabled = False
        page.win_lose_state = None
        page._is_boss_penalty_animating = mock.Mock(return_value=False)
        page._is_final_auto_liquidation_animating = mock.Mock(return_value=False)
        page._apply_final_auto_liquidation_if_needed = mock.Mock(return_value=False)
        page._apply_insurance_if_needed = mock.Mock(side_effect=lambda state, reason: (state, reason))
        page._finish_win_lose_result = mock.Mock()
        return page

    def test_both_objectives_are_required_in_regular_and_boss_rounds(self):
        for boss_fight in (False, True):
            for money, goal, result in ((201, 150, "win"), (200, 150, "lose"),
                                        (199, 150, "lose"), (201, 250, "lose")):
                with self.subTest(boss_fight=boss_fight, money=money, goal=goal):
                    page = self.page(money, goal, boss_fight=boss_fight)
                    self.assertTrue(has_condition(page.level_number, BOSS_SHARES))
                    page._check_win_lose()
                    self.assertEqual(page._finish_win_lose_result.call_args.args[0], result)

    def test_unassigned_condition_restores_normal_round_without_rebate(self):
        with mock.patch.dict(LEVEL_CONDITIONS, {get_campaign_content_level(6): ()}):
            for boss_fight in (False, True):
                page = self.page(money=150, goal=150, day=6, boss_fight=boss_fight)
                page._get_current_rebate_sale_percent.return_value = None
                page._check_win_lose()
                self.assertEqual(page._finish_win_lose_result.call_args.args[0], "win")
                self.assertIsNone(page._stock_bot_status_text())

    def test_boss_shares_can_be_assigned_to_a_different_level(self):
        with mock.patch.dict(LEVEL_CONDITIONS, {3: (BOSS_SHARES,)}):
            page = self.page(money=201, goal=150, day=6)
            page.level_number = 3
            page._check_win_lose()
            page._finish_win_lose_result.assert_not_called()
            page.Day = page.LastTurn
            page._check_win_lose()
            self.assertEqual(page._finish_win_lose_result.call_args.args[0], "win")

    def test_goal_reached_early_still_waits_for_final_price(self):
        page = self.page(day=3)
        page._check_win_lose()
        page._finish_win_lose_result.assert_not_called()
        page.Aprice = 6
        page.Day = page.LastTurn
        page._check_win_lose()
        self.assertEqual(page._boss_shares_sale_value(), 300)
        self.assertEqual(page._finish_win_lose_result.call_args.args[0], "lose")

    def test_no_early_finish_on_any_turn_including_extended_rounds(self):
        for boss_fight in (False, True):
            for last_turn in (8, 10):
                page = self.page(money=1000, boss_fight=boss_fight)
                page.LastTurn = last_turn
                for day in range(1, last_turn):
                    page.Day = day
                    page._check_win_lose()
                    page._finish_win_lose_result.assert_not_called()
                page.Day = last_turn
                page._check_win_lose()
                self.assertEqual(page._finish_win_lose_result.call_args.args[0], "win")

    def test_final_sale_requires_rebate_and_preserves_its_percentage(self):
        for rebate, expected_proceeds in ((100, 260), (90, 234), (130, 338)):
            page = self.page(money=0, goal=230, day=6)
            del page._apply_final_auto_liquidation_if_needed
            page.final_auto_liquidation_applied = False
            page.Aquantity, page.Bquantity, page.Cquantity = 50, 3, 3
            page._get_current_rebate_sale_percent = mock.Mock(return_value=rebate)
            page._start_final_auto_liquidation_animation = mock.Mock()
            page._check_win_lose()
            page._start_final_auto_liquidation_animation.assert_not_called()
            page._finish_win_lose_result.assert_not_called()

            page.Day = page.LastTurn
            def start_sale(liquidation):
                page._is_final_auto_liquidation_animating.return_value = True
            page._start_final_auto_liquidation_animation.side_effect = start_sale
            page._check_win_lose()
            sale = page._start_final_auto_liquidation_animation.call_args.args[0]
            self.assertEqual(sale["proceeds"], expected_proceeds)
            page._finish_win_lose_result.assert_not_called()

            # Finish the existing sale animation and recheck the round result.
            page.Money = sale["target_money"]
            page.Aquantity = page.Bquantity = page.Cquantity = 0
            page.final_auto_liquidation_applied = True
            page._is_final_auto_liquidation_animating.return_value = False
            page._check_win_lose()
            self.assertEqual(page._finish_win_lose_result.call_args.args[0], "win")
            page._start_final_auto_liquidation_animation.assert_called_once()

    def test_other_conditions_do_not_gain_automatic_sale(self):
        page = self.page()
        page.level_number = 4
        del page._apply_final_auto_liquidation_if_needed
        page.final_auto_liquidation_applied = False
        page._get_current_rebate_sale_percent = mock.Mock(return_value=None)
        self.assertFalse(page._apply_final_auto_liquidation_if_needed())

    def test_without_rebate_no_sale_and_final_loss_even_with_cash_or_insurance(self):
        for boss_fight in (False, True):
            for money in (0, 1000):
                with self.subTest(boss_fight=boss_fight, money=money):
                    page = self.page(money=money, day=6, boss_fight=boss_fight)
                    del page._apply_final_auto_liquidation_if_needed
                    page.final_auto_liquidation_applied = False
                    page.Aquantity = 100
                    page._get_current_rebate_sale_percent.return_value = None
                    page._start_final_auto_liquidation_animation = mock.Mock()
                    page._apply_insurance_if_needed.side_effect = None
                    page._apply_insurance_if_needed.return_value = ("win", "insurance")

                    page._check_win_lose()
                    page._finish_win_lose_result.assert_not_called()
                    page.Day = page.LastTurn
                    page._check_win_lose()
                    self.assertEqual(page._finish_win_lose_result.call_args.args[0], "lose")
                    page._start_final_auto_liquidation_animation.assert_not_called()
                    self.assertEqual(page.Money, money)
                    self.assertEqual(page.Aquantity, 100)

    def test_insurance_cannot_bypass_boss_shares(self):
        page = self.page(money=100, goal=150)
        page._apply_insurance_if_needed.return_value = ("win", "insurance")
        page._apply_insurance_if_needed.side_effect = None
        page._check_win_lose()
        self.assertEqual(page._finish_win_lose_result.call_args.args[0], "lose")

    def test_stale_bot_portfolio_is_removed_without_affecting_fixed_holding(self):
        page = self.page()
        page.stock_bot_enabled = True
        page.stock_bot = mock.Mock()
        page._stock_bot_saved_state = {"money": 99999}
        page.stock_bot_trade_history = [{"action": "trade"}]
        page._configure_boss_stock_bot()
        self.assertFalse(page.stock_bot_enabled)
        self.assertIsNone(page.stock_bot)
        self.assertIsNone(page._stock_bot_saved_state)
        self.assertEqual(page.stock_bot_trade_history, [])
        self.assertEqual(page._boss_shares_sale_value(), 200)
        self.assertEqual(page._stock_bot_status_text(), "Boss Shares: 50 A = 200")

    def test_trading_condition_enables_first_category_from_first_round(self):
        page = self.page(day=1)
        page._get_active_boss_number = mock.Mock(return_value=2)
        with mock.patch.dict(LEVEL_CONDITIONS, {page.level_number: (BOSS_TRADING,)}):
            page._configure_boss_stock_bot()
        self.assertTrue(page.stock_bot_enabled)

    def test_stakes_disable_every_boss_shares_restriction_for_active_round(self):
        for attribute, card in (("active_silver_cards", 205), ("active_gold_cards", 436)):
            for boss_fight in (False, True):
                with self.subTest(card=card, boss_fight=boss_fight):
                    # Goal met, but below the boss's 200 and without Rebate.
                    page = self.page(money=150, day=6, boss_fight=boss_fight)
                    setattr(page, attribute, [card])
                    page._get_current_rebate_sale_percent.return_value = None
                    page._check_win_lose()
                    self.assertEqual(page._finish_win_lose_result.call_args.args[0], "win")
                    self.assertIsNone(page._stock_bot_status_text())

                    # A new round without the card restores all restrictions.
                    setattr(page, attribute, [])
                    page._finish_win_lose_result.reset_mock()
                    page._check_win_lose()
                    page._finish_win_lose_result.assert_not_called()
                    page.Day = page.LastTurn
                    page._check_win_lose()
                    self.assertEqual(page._finish_win_lose_result.call_args.args[0], "lose")

    def test_stakes_do_not_remove_normal_cash_goal(self):
        for attribute, card in (("active_silver_cards", 205), ("active_gold_cards", 436)):
            page = self.page(money=100, goal=150)
            setattr(page, attribute, [card])
            page._check_win_lose()
            self.assertEqual(page._finish_win_lose_result.call_args.args[0], "lose")


if __name__ == "__main__":
    unittest.main()
