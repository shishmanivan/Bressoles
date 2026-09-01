from advanced_stock_bot import AdvancedStockBot
from simple_stock_bot import MARKETS


class ReinvestmentStockBot(AdvancedStockBot):
    """Probability-aware bot that prioritizes growing its share count."""

    display_name = "Бот3 - Перевложение"

    def trade(self, prices, probabilities):
        base_decision = super().trade(prices, probabilities)
        reinvestment = self.reinvest_for_more_shares(prices, probabilities)
        if reinvestment["action"] != "reinvest":
            decision = dict(base_decision)
            decision["reinvestment"] = reinvestment
            self.last_decision = decision
            return decision

        decision = {
            "action": "reinvest",
            "base_decision": base_decision,
            "reinvestment": reinvestment,
            "sold": self._merge_amounts(
                base_decision.get("sold"), reinvestment.get("sold")
            ),
            "sold_value": self._merge_amounts(
                base_decision.get("sold_value"), reinvestment.get("sold_value")
            ),
            "bought": self._merge_amounts(
                base_decision.get("bought"), reinvestment.get("bought")
            ),
            "bought_cost": self._merge_amounts(
                base_decision.get("bought_cost"), reinvestment.get("bought_cost")
            ),
            "money": self.money,
            "quantities": dict(self.quantities),
        }
        self.last_decision = decision
        return decision

    def reinvest_for_more_shares(self, prices, probabilities=None):
        """Move the whole portfolio into a cheaper stock if share count grows."""
        target_market = self._cheapest_available_market(prices, probabilities or {})
        if target_market is None:
            return self._reinvestment_hold("no_available_market")

        target = MARKETS[target_market]
        target_price = self._market_price(prices, target)
        held_markets = [
            market
            for market in MARKETS.values()
            if int(self.quantities.get(market["quantity_key"], 0) or 0) > 0
        ]
        if not held_markets:
            return self._reinvestment_hold("no_shares")

        has_more_expensive_shares = any(
            self._market_price(prices, market) > target_price for market in held_markets
        )
        if not has_more_expensive_shares:
            return self._reinvestment_hold("no_cheaper_stock")

        current_share_count = sum(
            int(self.quantities.get(market["quantity_key"], 0) or 0)
            for market in MARKETS.values()
        )
        portfolio_value = self.portfolio_value(prices)
        projected_share_count = portfolio_value // target_price
        if projected_share_count <= current_share_count:
            return self._reinvestment_hold("share_count_would_not_grow")

        sold = {}
        sold_value = {}
        for market in MARKETS.values():
            quantity_key = market["quantity_key"]
            quantity = int(self.quantities.get(quantity_key, 0) or 0)
            if quantity <= 0:
                continue
            value = quantity * self._market_price(prices, market)
            self.money += value
            self.quantities[quantity_key] = 0
            sold[market["label"]] = quantity
            sold_value[market["label"]] = value

        bought_count = self.money // target_price
        bought_cost = bought_count * target_price
        self.money -= bought_cost
        self.quantities[target["quantity_key"]] += bought_count

        return {
            "action": "reinvest",
            "target_market": target["label"],
            "target_price": target_price,
            "shares_before": current_share_count,
            "shares_after": bought_count,
            "sold": sold,
            "sold_value": sold_value,
            "bought": {target["label"]: bought_count},
            "bought_cost": {target["label"]: bought_cost},
            "money": self.money,
            "quantities": dict(self.quantities),
        }

    def _cheapest_available_market(self, prices, probabilities):
        available = []
        for market_id, market in MARKETS.items():
            price = self._market_price(prices, market)
            if price > 0 and price not in self.blocked_buy_prices:
                available.append((market_id, price))
        if not available:
            return None

        cheapest_price = min(price for _market_id, price in available)
        cheapest_markets = [
            market_id for market_id, price in available if price == cheapest_price
        ]
        if len(cheapest_markets) == 1:
            return cheapest_markets[0]

        scores = self._score_markets(prices, probabilities)
        return max(cheapest_markets, key=lambda market_id: scores[market_id]["score"])

    @staticmethod
    def _market_price(prices, market):
        try:
            return max(0, int(prices.get(market["price_key"], 0) or 0))
        except (TypeError, ValueError):
            return 0

    def _reinvestment_hold(self, reason):
        return {
            "action": "hold",
            "reason": reason,
            "money": self.money,
            "quantities": dict(self.quantities),
        }

    @staticmethod
    def _merge_amounts(first, second):
        merged = {}
        for source in (first or {}, second or {}):
            for label, amount in source.items():
                merged[label] = merged.get(label, 0) + int(amount or 0)
        return merged


# A concise alias for experiments that refer to bots by level.
StockBotLevel3 = ReinvestmentStockBot
