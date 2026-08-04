import os
import unittest
from unittest import mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import game_state
from boss_logic import apply_boss_functionality
from gameplay_page import GameplayPage
from gameplay_trade_actions import apply_arrow_trade
from simple_stock_bot import SimpleStockBot


class ArrowTradeTests(unittest.TestCase):
    def setUp(self):
        self.quantities = {
            "Aquantity": 2,
            "Bquantity": 3,
            "Cquantity": 4,
        }
        self.prices = {
            "Aprice": 6,
            "BPrice": 10,
            "CPrice": 14,
        }

    def test_buy_maximum_spends_only_complete_share_prices(self):
        result = apply_arrow_trade(25, self.quantities, self.prices, 0, 0)

        self.assertTrue(result["changed"])
        self.assertEqual(result["money"], 1)
        self.assertEqual(result["quantities"]["Aquantity"], 6)

    def test_buy_one_respects_blocked_price(self):
        self.prices["Aprice"] = 2

        result = apply_arrow_trade(
            20,
            self.quantities,
            self.prices,
            0,
            1,
            blocked_buy_prices={2},
        )

        self.assertFalse(result["changed"])
        self.assertEqual(result["money"], 20)
        self.assertEqual(result["quantities"], self.quantities)

    def test_sell_one_and_sell_all_preserve_portfolio_value(self):
        before_value = 5 + sum(
            quantity * price
            for quantity, price in zip(
                self.quantities.values(),
                self.prices.values(),
            )
        )

        sell_one = apply_arrow_trade(5, self.quantities, self.prices, 1, 2)
        sell_all = apply_arrow_trade(
            sell_one["money"],
            sell_one["quantities"],
            self.prices,
            2,
            3,
        )
        after_value = sell_all["money"] + sum(
            quantity * price
            for quantity, price in zip(
                sell_all["quantities"].values(),
                self.prices.values(),
            )
        )

        self.assertEqual(after_value, before_value)
        self.assertEqual(sell_one["quantities"]["Bquantity"], 2)
        self.assertEqual(sell_all["quantities"]["Cquantity"], 0)

    def test_sell_all_with_no_shares_is_not_a_trade(self):
        self.quantities["Cquantity"] = 0

        result = apply_arrow_trade(12, self.quantities, self.prices, 2, 3)

        self.assertFalse(result["changed"])
        self.assertEqual(result["money"], 12)
        self.assertEqual(result["quantities"], self.quantities)

    def test_successful_player_trade_resets_surge_counter_but_failed_trade_does_not(self):
        page = GameplayPage.__new__(GameplayPage)
        page.Money = 10
        page.Aquantity = 2
        page.Bquantity = 0
        page.Cquantity = 0
        page.Aprice = page.BPrice = page.CPrice = 4
        page.surge_turns_without_trade = 2
        page.surge_traded_this_turn = False
        page._is_arrow_disabled = mock.Mock(return_value=False)
        page._blocked_buy_prices = mock.Mock(return_value=set())
        page._check_win_lose = mock.Mock()

        self.assertTrue(page._apply_arrow_trade(0, 1))
        self.assertEqual(page.surge_turns_without_trade, 0)
        self.assertTrue(page.surge_traded_this_turn)

        page.Money = 0
        page.surge_turns_without_trade = 2
        page.surge_traded_this_turn = False
        self.assertFalse(page._apply_arrow_trade(1, 1))
        self.assertEqual(page.surge_turns_without_trade, 2)
        self.assertFalse(page.surge_traded_this_turn)


class StockBotTurnTests(unittest.TestCase):
    @staticmethod
    def _page(day, last_turn):
        page = GameplayPage.__new__(GameplayPage)
        page.stock_bot_enabled = True
        page.stock_bot_type = "simple"
        page.level_number = 5
        page.stock_bot = mock.Mock()
        page.stock_bot.display_name = "Boss"
        page.stock_bot.trade.return_value = {"action": "hold"}
        page.stock_bot.sell_all.return_value = {"action": "liquidate"}
        page.Day = day
        page.LastTurn = last_turn
        page.Aprice = 4
        page.BPrice = 8
        page.CPrice = 12
        page.stock_bot_trade_history = []
        page._record_stock_bot_trade = mock.Mock()
        return page

    def test_bot_liquidates_before_transition_to_terminal_day(self):
        page = self._page(day=7, last_turn=8)

        self.assertTrue(page._run_stock_bot_turn())

        page.stock_bot.sell_all.assert_called_once_with(page._current_prices())
        page.stock_bot.trade.assert_not_called()

    def test_bot_keeps_trading_before_its_final_playable_day(self):
        page = self._page(day=6, last_turn=8)

        self.assertTrue(page._run_stock_bot_turn())

        page.stock_bot.trade.assert_called_once_with(page._current_prices())
        page.stock_bot.sell_all.assert_not_called()

    def test_stock_bot_state_round_trip_preserves_its_portfolio(self):
        bot = SimpleStockBot(
            money=13,
            quantities={"Aquantity": 2, "Bquantity": 3, "Cquantity": 4},
            last_prices={"Aprice": 6, "BPrice": 10, "CPrice": 14},
            blocked_buy_prices={2},
        )
        bot.last_decision = {"action": "hold", "best_market": "B"}

        restored = SimpleStockBot.from_state(bot.to_dict())

        self.assertEqual(restored.to_dict(), bot.to_dict())
        self.assertEqual(
            restored.portfolio_value({"Aprice": 6, "BPrice": 10, "CPrice": 14}),
            111,
        )

    def test_player_wins_a_tie_against_the_stock_bot(self):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 5
        page.stock_bot_enabled = True
        page.Money = 20
        page.Goal = 40
        page.Aquantity = 2
        page.Bquantity = 0
        page.Cquantity = 0
        page.Aprice = 10
        page.BPrice = 6
        page.CPrice = 8
        page._stock_bot_portfolio_value = mock.Mock(return_value=40)

        self.assertTrue(page._can_win_against_current_boss())

        page._stock_bot_portfolio_value.return_value = 41
        self.assertFalse(page._can_win_against_current_boss())


class BossTradingConstraintTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.boss_odd_turn_trading_only = False
        page.boss_forbid_price_2_buys = False
        page.Day = 1
        page.Aprice = 2
        page.BPrice = 6
        page.CPrice = 2
        return page

    def test_kolbe_disables_every_trade_arrow_on_even_days(self):
        page = self._page()
        page.boss_odd_turn_trading_only = True

        page.Day = 2
        self.assertTrue(page._is_arrow_disabled(1, 0))
        self.assertTrue(page._is_arrow_disabled(1, 3))

        page.Day = 3
        self.assertFalse(page._is_arrow_disabled(1, 0))
        self.assertFalse(page._is_arrow_disabled(1, 3))

    def test_laffitte_blocks_only_buying_stocks_priced_at_two(self):
        page = self._page()
        page.boss_forbid_price_2_buys = True

        self.assertTrue(page._is_arrow_disabled(0, 0))
        self.assertTrue(page._is_arrow_disabled(2, 1))
        self.assertFalse(page._is_arrow_disabled(0, 2))
        self.assertFalse(page._is_arrow_disabled(0, 3))
        self.assertFalse(page._is_arrow_disabled(1, 0))

    def test_list_effect_starts_with_twelve_b_shares(self):
        page = self._page()
        page.level_number = 5
        page.stock_bot_enabled = False
        page._get_active_boss_number = mock.Mock(return_value=8)

        apply_boss_functionality("ListStockBot", page)

        self.assertTrue(page.stock_bot_enabled)
        self.assertEqual(page.stock_bot_type, "simple")
        self.assertEqual(
            page.stock_bot_start_quantities,
            {"Aquantity": 0, "Bquantity": 12, "Cquantity": 0},
        )

    def test_laffitte_effect_enables_advanced_bot_and_price_two_block(self):
        page = self._page()
        page.level_number = 5
        page.stock_bot_enabled = False
        page.stock_bot_blocked_buy_prices = set()
        page._get_active_boss_number = mock.Mock(return_value=9)

        apply_boss_functionality("Bot2Percent,NoPrice2Buys", page)

        self.assertTrue(page.stock_bot_enabled)
        self.assertEqual(page.stock_bot_type, "advanced")
        self.assertEqual(
            page.stock_bot_start_quantities,
            {"Aquantity": 0, "Bquantity": 4, "Cquantity": 0},
        )
        self.assertTrue(page.boss_forbid_price_2_buys)
        self.assertEqual(page.stock_bot_blocked_buy_prices, {2})

    def test_level5_first_boss_starts_even_with_player_on_two_a_shares(self):
        page = self._page()
        page.level_number = 5
        page.boss_index = 0
        page.defeated_count = 0
        page._get_active_boss_number = mock.Mock(return_value=2)

        page._configure_level5_boss_stock_bot()

        self.assertTrue(page.stock_bot_enabled)
        self.assertEqual(page.stock_bot_type, "simple")
        self.assertEqual(
            page.stock_bot_start_quantities,
            {"Aquantity": 2, "Bquantity": 0, "Cquantity": 0},
        )

    def test_category_two_bosses_use_their_balanced_b_shares_on_level5(self):
        for boss_number, expected_b_shares in ((8, 12), (9, 4), (11, 4), (12, 4), (13, 4), (14, 4)):
            with self.subTest(boss_number=boss_number):
                page = self._page()
                page.level_number = 5
                page.boss_index = 0
                page.defeated_count = 2
                page._get_active_boss_number = mock.Mock(return_value=boss_number)

                page._configure_boss_stock_bot()

                self.assertTrue(page.stock_bot_enabled)
                self.assertEqual(page.stock_bot_type, "advanced")
                self.assertEqual(
                    page.stock_bot_start_quantities,
                    {"Aquantity": 0, "Bquantity": expected_b_shares, "Cquantity": 0},
                )

    def test_category_one_bosses_start_with_two_a_shares_on_level5(self):
        page = self._page()
        page.level_number = 5
        page.boss_index = 0
        page.defeated_count = 1
        page._get_active_boss_number = mock.Mock(return_value=4)

        page._configure_boss_stock_bot()

        self.assertTrue(page.stock_bot_enabled)
        self.assertEqual(page.stock_bot_type, "simple")
        self.assertEqual(
            page.stock_bot_start_quantities,
            {"Aquantity": 2, "Bquantity": 0, "Cquantity": 0},
        )

    def test_level4_does_not_enable_boss_stock_trading(self):
        page = self._page()
        page.level_number = 4
        page.boss_index = 0
        page._get_active_boss_number = mock.Mock(return_value=8)

        page._configure_boss_stock_bot()

        self.assertFalse(getattr(page, "stock_bot_enabled", False))


class ShareholderMarketShutdownTests(unittest.TestCase):
    def test_probability_progression_starts_at_three_and_continues(self):
        expected = {0: 0.0, 2: 0.0, 3: 0.20, 4: 0.25, 5: 0.30, 6: 0.35, 7: 0.40}
        for count, probability in expected.items():
            with self.subTest(count=count):
                self.assertAlmostEqual(
                    GameplayPage.shareholder_market_shutdown_probability(count),
                    probability,
                )

    def test_successful_roll_disables_every_arrow_of_one_market_only(self):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 4
        page.win_lose_state = None
        page.shareholder_effect_count = 3
        page.shareholder_blocked_market = None
        page.boss_odd_turn_trading_only = False
        page.boss_forbid_price_2_buys = False
        page.Day = 2
        page.Aprice = page.BPrice = page.CPrice = 10
        page.side_cards_top = [100, 110, 100, None, None, None]
        page.side_card_jump_animations = {}
        page.market_cards = {
            0: {0: 100, 1: 11},
            1: {},
            2: {1: 100},
        }
        page.card_jump_animations = {0: {}, 1: {}, 2: {}}

        with (
            mock.patch("gameplay_page.random.random", return_value=0.19),
            mock.patch("gameplay_page.random.choice", return_value=1),
        ):
            self.assertEqual(page._roll_shareholder_market_shutdown(), 1)

        for arrow_type in range(4):
            self.assertTrue(page._is_arrow_disabled(1, arrow_type))
            self.assertFalse(page._is_arrow_disabled(0, arrow_type))
            self.assertFalse(page._is_arrow_disabled(2, arrow_type))
        self.assertEqual(set(page.side_card_jump_animations), {0, 2})
        self.assertEqual(set(page.card_jump_animations[0]), {0})
        self.assertEqual(set(page.card_jump_animations[1]), set())
        self.assertEqual(set(page.card_jump_animations[2]), {1})

    def test_disabled_shareholder_market_uses_dimmed_arrow_images(self):
        page = GameplayPage.__new__(GameplayPage)
        page.shareholder_blocked_market = 1
        page.boss_odd_turn_trading_only = False
        page.boss_forbid_price_2_buys = False
        original = object()
        dimmed = object()
        page._get_dimmed_arrow = mock.Mock(return_value=dimmed)

        for arrow_type in range(4):
            self.assertIs(page._get_trade_arrow_image(1, arrow_type, original), dimmed)
        self.assertIs(page._get_trade_arrow_image(0, 0, original), original)
        self.assertIs(page._get_trade_arrow_image(2, 3, original), original)
        self.assertEqual(page._get_dimmed_arrow.call_count, 4)

    def test_effect_never_runs_outside_level_four(self):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 5
        page.win_lose_state = None
        page.shareholder_effect_count = 6
        page.shareholder_blocked_market = 1

        with mock.patch("gameplay_page.random.random") as roll:
            self.assertIsNone(page._roll_shareholder_market_shutdown())

        roll.assert_not_called()
        self.assertIsNone(page.shareholder_blocked_market)

    def test_controlling_stake_prevents_and_clears_shareholder_button_lockout(self):
        page = GameplayPage.__new__(GameplayPage)
        page.level_number = 4
        page.win_lose_state = None
        page.shareholder_effect_count = 7
        page.shareholder_blocked_market = 1
        page.active_silver_cards = [205]
        page.boss_odd_turn_trading_only = False
        page.boss_forbid_price_2_buys = False
        page.Day = 2
        page.Aprice = page.BPrice = page.CPrice = 10

        with mock.patch("gameplay_page.random.random") as roll:
            self.assertIsNone(page._roll_shareholder_market_shutdown())

        roll.assert_not_called()
        self.assertIsNone(page.shareholder_blocked_market)
        for arrow_type in range(4):
            self.assertFalse(page._is_arrow_disabled(1, arrow_type))


class RebateLiquidationTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.final_auto_liquidation_applied = False
        page.win_lose_state = None
        page.Day = 8
        page.LastTurn = 8
        page.Money = 7
        page.Aquantity = 2
        page.Bquantity = 1
        page.Cquantity = 0
        page.Aprice = 10
        page.BPrice = 20
        page.CPrice = 30
        page._start_final_auto_liquidation_animation = mock.Mock()
        return page

    def test_silver_rebate_liquidates_at_full_current_value(self):
        page = self._page()
        page._has_active_silver_card = mock.Mock(
            side_effect=lambda card_id: card_id == 201,
        )
        page._has_played_side_card = mock.Mock(return_value=False)

        self.assertTrue(page._apply_final_auto_liquidation_if_needed())

        liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
        self.assertEqual(liquidation["gross_value"], 40)
        self.assertEqual(liquidation["proceeds"], 40)
        self.assertEqual(liquidation["target_money"], 47)

    def test_matching_red_and_silver_rebates_keep_the_hidden_synergy(self):
        page = self._page()
        page._has_active_silver_card = mock.Mock(
            side_effect=lambda card_id: card_id == 201,
        )
        page._has_played_side_card = mock.Mock(
            side_effect=lambda card_id: card_id == 110,
        )

        self.assertTrue(page._apply_final_auto_liquidation_if_needed())

        liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
        self.assertEqual(liquidation["gross_value"], 40)
        self.assertEqual(liquidation["proceeds"], 48)
        self.assertEqual(liquidation["target_money"], 55)

    def test_gold_rebate_uses_base_synergies_and_a_fall_bonus(self):
        cases = (
            (False, False, 0, 52),
            (True, False, 0, 56),
            (False, True, 0, 56),
            (True, True, 0, 60),
            (True, True, 4, 61),
        )
        for red_rebate, silver_rebate, fall_bonus, expected_proceeds in cases:
            with self.subTest(
                red_rebate=red_rebate,
                silver_rebate=silver_rebate,
                fall_bonus=fall_bonus,
            ):
                page = self._page()
                page.rebate_a_fall_bonus_percent = fall_bonus
                page._has_active_silver_card = mock.Mock(
                    side_effect=lambda card_id: card_id == 407 or (card_id == 201 and silver_rebate),
                )
                page._has_played_side_card = mock.Mock(
                    side_effect=lambda card_id: card_id == 110 and red_rebate,
                )

                self.assertTrue(page._apply_final_auto_liquidation_if_needed())

                liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
                self.assertEqual(liquidation["gross_value"], 40)
                self.assertEqual(liquidation["proceeds"], expected_proceeds)

    def test_catalyst_is_added_once_after_combining_all_rebate_synergies(self):
        page = self._page()
        page.rebate_a_fall_bonus_percent = 0
        page.active_silver_cards = [201, 210]
        page.active_black_cards = []
        page.active_gold_cards = [407]
        page.active_lifecycle_card_order = []
        page.side_cards_top = [110]

        # Gold Rebate 130% + red synergy 10% + silver synergy 10%
        # + one Catalyst bonus 10% = 160% total, not 180% per three Rebates.
        self.assertEqual(page._get_current_rebate_sale_percent(), 160)

        self.assertTrue(page._apply_final_auto_liquidation_if_needed())
        liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
        self.assertEqual(liquidation["gross_value"], 40)
        self.assertEqual(liquidation["proceeds"], 64)

    def test_both_catalysts_are_added_once_to_combined_rebate_effect(self):
        page = self._page()
        page.rebate_a_fall_bonus_percent = 0
        page.active_silver_cards = [201, 210]
        page.active_black_cards = []
        page.active_gold_cards = [407, 414]
        page.active_lifecycle_card_order = []
        page.side_cards_top = [110]

        # Gold Rebate 130% + red synergy 10% + silver synergy 10%
        # + silver Catalyst 10% + gold Catalyst 15% = 175% total.
        self.assertEqual(page._get_current_rebate_sale_percent(), 175)

        self.assertTrue(page._apply_final_auto_liquidation_if_needed())
        liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
        self.assertEqual(liquidation["gross_value"], 40)
        self.assertEqual(liquidation["proceeds"], 70)

    def test_gold_rebate_adds_two_percent_only_when_a_actually_falls(self):
        page = GameplayPage.__new__(GameplayPage)
        page.rebate_a_fall_bonus_percent = 0
        page.lifecycle_card_jump_animations = {}
        page._has_active_silver_card = mock.Mock(return_value=True)
        page._active_lifecycle_cards = mock.Mock(return_value=[407])
        page._start_card_jump_animation = mock.Mock()

        self.assertTrue(page._record_rebate_a_fall(10, 8, "test"))
        self.assertEqual(page.rebate_a_fall_bonus_percent, 2)
        self.assertFalse(page._record_rebate_a_fall(2, 2, "minimum"))
        self.assertEqual(page.rebate_a_fall_bonus_percent, 2)
        page._start_card_jump_animation.assert_called_once()

    def test_uptrend_adds_current_napoleondors_after_rebate_synergies(self):
        cases = (
            (True, False, False, 0, 38),
            (True, True, False, 0, 50),
            (True, True, True, 4, 63),
        )
        with mock.patch.object(game_state, "napoleondors", 5):
            for red_rebate, silver_rebate, gold_rebate, fall_bonus, expected_proceeds in cases:
                with self.subTest(
                    red_rebate=red_rebate,
                    silver_rebate=silver_rebate,
                    gold_rebate=gold_rebate,
                ):
                    page = self._page()
                    page.rebate_a_fall_bonus_percent = fall_bonus
                    page._has_active_silver_card = mock.Mock(
                        side_effect=lambda card_id: (
                            card_id == 410
                            or (card_id == 201 and silver_rebate)
                            or (card_id == 407 and gold_rebate)
                        ),
                    )
                    page._has_played_side_card = mock.Mock(
                        side_effect=lambda card_id: card_id == 110 and red_rebate,
                    )

                    self.assertTrue(page._apply_final_auto_liquidation_if_needed())

                    liquidation = page._start_final_auto_liquidation_animation.call_args.args[0]
                    self.assertEqual(liquidation["proceeds"], expected_proceeds)

    def test_uptrend_requires_rebate_and_counts_only_whole_napoleondors(self):
        page = self._page()
        page._has_active_silver_card = mock.Mock(
            side_effect=lambda card_id: card_id == 410,
        )
        page._has_played_side_card = mock.Mock(return_value=False)

        with mock.patch.object(game_state, "napoleondors", 5.5):
            self.assertEqual(page._get_uptrend_rebate_bonus_percent(), 5)
            self.assertFalse(page._apply_final_auto_liquidation_if_needed())

    def test_no_rebate_leaves_terminal_shares_for_the_normal_loss_check(self):
        page = self._page()
        page._has_active_silver_card = mock.Mock(return_value=False)
        page._has_played_side_card = mock.Mock(return_value=False)

        self.assertFalse(page._apply_final_auto_liquidation_if_needed())

        page._start_final_auto_liquidation_animation.assert_not_called()
        self.assertEqual((page.Aquantity, page.Bquantity, page.Cquantity), (2, 1, 0))


class DisclosureGameplayTests(unittest.TestCase):
    @staticmethod
    def _page():
        page = GameplayPage.__new__(GameplayPage)
        page.rebate_a_fall_bonus_percent = 2
        page._has_active_silver_card = mock.Mock(
            side_effect=lambda card_id: card_id in (302, 407, 410),
        )
        page._has_played_side_card = mock.Mock(return_value=False)
        return page

    def test_market_probabilities_are_hidden_without_disclosure(self):
        page = GameplayPage.__new__(GameplayPage)
        with (
            mock.patch.object(game_state, "disclosure_rounds_remaining", 0),
            mock.patch("gameplay_page.build_market_probabilities") as build_probabilities,
        ):
            page._draw_market_probability_debug(0, 10, 10)

        build_probabilities.assert_not_called()

    def test_disclosure_tooltips_show_current_dynamic_percentages(self):
        page = self._page()
        with (
            mock.patch.object(game_state, "disclosure_rounds_remaining", 5),
            mock.patch.object(game_state, "golden_stocks_chance_percent", 9),
            mock.patch.object(game_state, "napoleondors", 12.5),
        ):
            golden = page._get_disclosure_card_tooltip_content(302)
            rebate = page._get_disclosure_card_tooltip_content(407)
            uptrend = page._get_disclosure_card_tooltip_content(410)

        self.assertIn("9%", golden[1])
        self.assertIn("144%", rebate[1])
        self.assertIn("+12%", uptrend[1])

    def test_disclosure_card_percentages_are_hidden_after_expiration(self):
        page = self._page()
        with mock.patch.object(game_state, "disclosure_rounds_remaining", 0):
            self.assertIsNone(page._get_disclosure_card_tooltip_content(302))
            self.assertIsNone(page._get_disclosure_card_tooltip_content(407))
            self.assertIsNone(page._get_disclosure_card_tooltip_content(410))


if __name__ == "__main__":
    unittest.main()
