MARKETS = {
    0: {
        "price_key": "Aprice",
        "quantity_key": "Aquantity",
        "label": "A",
    },
    1: {
        "price_key": "BPrice",
        "quantity_key": "Bquantity",
        "label": "B",
    },
    2: {
        "price_key": "CPrice",
        "quantity_key": "Cquantity",
        "label": "C",
    },
}

QUALITATIVE_MARKET_RULES = {
    0: {"growth": 1.0, "risk": 0.15, "price_penalty": 0.08},
    1: {"growth": 1.45, "risk": 0.45, "price_penalty": 0.11},
    2: {"growth": 2.0, "risk": 0.9, "price_penalty": 0.16},
}


class SimpleStockBot:
    """A minimal stock-only bot with no exact probability knowledge."""

    display_name = "Босс"

    def __init__(self, money=0, quantities=None, last_prices=None, blocked_buy_prices=None):
        self.money = int(money or 0)
        quantities = quantities or {}
        self.quantities = {
            "Aquantity": int(quantities.get("Aquantity", 10) or 0),
            "Bquantity": int(quantities.get("Bquantity", 0) or 0),
            "Cquantity": int(quantities.get("Cquantity", 0) or 0),
        }
        self.last_prices = dict(last_prices or {})
        self.blocked_buy_prices = set(blocked_buy_prices or [])
        self.last_decision = None

    @classmethod
    def from_state(cls, state=None):
        if not isinstance(state, dict):
            return cls()
        bot = cls(
            money=state.get("money", 0),
            quantities=state.get("quantities") or {},
            last_prices=state.get("last_prices") or {},
            blocked_buy_prices=state.get("blocked_buy_prices") or [],
        )
        bot.last_decision = state.get("last_decision")
        return bot

    def to_dict(self):
        return {
            "money": int(self.money or 0),
            "quantities": dict(self.quantities),
            "last_prices": dict(self.last_prices),
            "blocked_buy_prices": sorted(self.blocked_buy_prices),
            "last_decision": self.last_decision,
        }

    def portfolio_value(self, prices):
        total = int(self.money or 0)
        for market in MARKETS.values():
            price = int(prices.get(market["price_key"], 0) or 0)
            quantity = int(self.quantities.get(market["quantity_key"], 0) or 0)
            total += price * quantity
        return total

    def status_line(self, prices):
        return (
            f"{self.display_name}: {self.portfolio_value(prices)} | "
            f"A{self.quantities['Aquantity']} "
            f"B{self.quantities['Bquantity']} "
            f"C{self.quantities['Cquantity']}"
        )

    def trade(self, prices):
        scores = self._score_markets(prices)
        return self._trade_with_scores(prices, scores)

    def _trade_with_scores(self, prices, scores):
        if not scores:
            self.last_decision = {"action": "skip"}
            return self.last_decision

        best_market = max(scores, key=lambda market: scores[market]["score"])
        best_score = scores[best_market]
        sold = {}
        sold_value = {}
        bought = {}
        bought_cost = {}

        for market_id, market in MARKETS.items():
            quantity_key = market["quantity_key"]
            quantity = int(self.quantities.get(quantity_key, 0) or 0)
            if quantity <= 0:
                continue

            current_score = scores.get(market_id, {})
            should_sell_all = best_score["score"] <= 0
            should_switch = market_id != best_market and current_score.get("score", 0.0) < best_score["score"]
            if should_sell_all or should_switch:
                price = int(prices.get(market["price_key"], 0) or 0)
                self.money += quantity * price
                self.quantities[quantity_key] = 0
                sold[market["label"]] = quantity
                sold_value[market["label"]] = quantity * price

        if best_score["score"] > 0:
            best = MARKETS[best_market]
            price = int(prices.get(best["price_key"], 0) or 0)
            if price > 0 and price not in self.blocked_buy_prices:
                count = int(self.money // price)
                if count > 0:
                    self.money -= count * price
                    self.quantities[best["quantity_key"]] += count
                    bought[best["label"]] = count
                    bought_cost[best["label"]] = count * price

        self.last_decision = {
            "action": "trade" if sold or bought else "hold",
            "best_market": MARKETS[best_market]["label"],
            "sold": sold,
            "sold_value": sold_value,
            "bought": bought,
            "bought_cost": bought_cost,
            "scores": self._serialize_scores(scores),
            "money": self.money,
            "quantities": dict(self.quantities),
        }
        self._remember_prices(prices)
        return self.last_decision

    def sell_all(self, prices):
        sold = {}
        sold_value = {}
        for market in MARKETS.values():
            quantity_key = market["quantity_key"]
            quantity = int(self.quantities.get(quantity_key, 0) or 0)
            if quantity <= 0:
                continue
            price = int(prices.get(market["price_key"], 0) or 0)
            self.money += quantity * price
            self.quantities[quantity_key] = 0
            sold[market["label"]] = quantity
            sold_value[market["label"]] = quantity * price

        self.last_decision = {
            "action": "liquidate" if sold else "hold",
            "sold": sold,
            "sold_value": sold_value,
            "bought": {},
            "bought_cost": {},
            "money": self.money,
            "quantities": dict(self.quantities),
        }
        self._remember_prices(prices)
        return self.last_decision

    def _score_markets(self, prices):
        scores = {}
        for market_id, market in MARKETS.items():
            price = int(prices.get(market["price_key"], 0) or 0)
            rules = QUALITATIVE_MARKET_RULES.get(market_id, {})
            previous_price = self._last_price_for(market)
            if previous_price is None:
                trend = "unknown"
                trend_score = 0.0
            elif price > previous_price:
                trend = "rise"
                trend_score = 0.45
            elif price < previous_price:
                trend = "fall"
                trend_score = -0.65
            else:
                trend = "flat"
                trend_score = 0.0
            score = (
                float(rules.get("growth", 0.0))
                - float(rules.get("risk", 0.0))
                - max(0, price - 2) * float(rules.get("price_penalty", 0.0))
                + trend_score
            )
            scores[market_id] = {
                "score": score,
                "trend": trend,
            }
        return scores

    def _serialize_scores(self, scores):
        serialized = {}
        for market_id, score in scores.items():
            entry = {
                "score": round(score["score"], 3),
                "trend": score["trend"],
            }
            for key in ("rise", "flat", "fall"):
                if key in score:
                    entry[key] = score[key]
            serialized[MARKETS[market_id]["label"]] = entry
        return serialized

    def _last_price_for(self, market):
        key = market["price_key"]
        if key not in self.last_prices:
            return None
        try:
            return int(self.last_prices.get(key))
        except (TypeError, ValueError):
            return None

    def _remember_prices(self, prices):
        self.last_prices = {
            market["price_key"]: int(prices.get(market["price_key"], 0) or 0)
            for market in MARKETS.values()
        }
