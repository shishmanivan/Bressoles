import unittest
from unittest import mock

from advanced_stock_bot import AdvancedStockBot
from reinvestment_stock_bot import ReinvestmentStockBot, StockBotLevel3


PRICES = {"Aprice": 2, "BPrice": 5, "CPrice": 7}
PROBABILITIES = {
    0: {"rise": 30, "flat": 40, "fall": 30},
    1: {"rise": 40, "flat": 30, "fall": 30},
    2: {"rise": 50, "flat": 20, "fall": 30},
}


class ReinvestmentStockBotTests(unittest.TestCase):
    def test_reinvests_into_cheaper_stock_when_total_share_count_grows(self):
        bot = ReinvestmentStockBot(
            quantities={"Aquantity": 0, "Bquantity": 10, "Cquantity": 0}
        )

        decision = bot.reinvest_for_more_shares(PRICES, PROBABILITIES)

        self.assertEqual(decision["action"], "reinvest")
        self.assertEqual(decision["target_market"], "A")
        self.assertEqual(decision["shares_before"], 10)
        self.assertEqual(decision["shares_after"], 25)
        self.assertEqual(bot.quantities, {"Aquantity": 25, "Bquantity": 0, "Cquantity": 0})
        self.assertEqual(bot.money, 0)

    def test_does_not_reinvest_when_cheaper_stock_cannot_add_a_share(self):
        bot = ReinvestmentStockBot(
            quantities={"Aquantity": 0, "Bquantity": 1, "Cquantity": 0}
        )
        prices = {"Aprice": 4, "BPrice": 5, "CPrice": 8}

        decision = bot.reinvest_for_more_shares(prices, PROBABILITIES)

        self.assertEqual(decision["action"], "hold")
        self.assertEqual(decision["reason"], "share_count_would_not_grow")
        self.assertEqual(bot.quantities["Bquantity"], 1)

    def test_ignores_blocked_buy_price_and_uses_next_cheapest_stock(self):
        bot = ReinvestmentStockBot(
            quantities={"Aquantity": 0, "Bquantity": 10, "Cquantity": 0},
            blocked_buy_prices={2},
        )
        prices = {"Aprice": 2, "BPrice": 5, "CPrice": 3}

        decision = bot.reinvest_for_more_shares(prices, PROBABILITIES)

        self.assertEqual(decision["target_market"], "C")
        self.assertEqual(bot.quantities["Cquantity"], 16)
        self.assertEqual(bot.money, 2)

    def test_trade_runs_reinvestment_after_probability_decision(self):
        bot = ReinvestmentStockBot(
            quantities={"Aquantity": 0, "Bquantity": 10, "Cquantity": 0}
        )
        base_decision = {
            "action": "hold",
            "sold": {},
            "sold_value": {},
            "bought": {},
            "bought_cost": {},
        }

        with mock.patch.object(AdvancedStockBot, "trade", return_value=base_decision):
            decision = bot.trade(PRICES, PROBABILITIES)

        self.assertEqual(decision["action"], "reinvest")
        self.assertEqual(decision["reinvestment"]["shares_after"], 25)

    def test_state_round_trip_preserves_bot3_type_and_portfolio(self):
        bot = ReinvestmentStockBot(
            money=1,
            quantities={"Aquantity": 3, "Bquantity": 4, "Cquantity": 5},
            blocked_buy_prices={2},
        )

        restored = ReinvestmentStockBot.from_state(bot.to_dict())

        self.assertIsInstance(restored, ReinvestmentStockBot)
        self.assertIs(StockBotLevel3, ReinvestmentStockBot)
        self.assertEqual(restored.money, 1)
        self.assertEqual(restored.quantities, bot.quantities)
        self.assertEqual(restored.blocked_buy_prices, {2})


if __name__ == "__main__":
    unittest.main()
