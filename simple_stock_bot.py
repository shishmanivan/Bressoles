MARKETS = {
    0: {
        "price_key": "Aprice",
        "quantity_key": "Aquantity",
        "step_key": "StepA",
        "label": "A",
    },
    1: {
        "price_key": "BPrice",
        "quantity_key": "Bquantity",
        "step_key": "StepB",
        "label": "B",
    },
    2: {
        "price_key": "CPrice",
        "quantity_key": "Cquantity",
        "step_key": "StepC",
        "label": "C",
    },
}


class SimpleStockBot:
    """A minimal stock-only bot that reacts to revealed market facts."""

    def __init__(self, money=0, quantities=None):
        self.money = int(money or 0)
        quantities = quantities or {}
        self.quantities = {
            "Aquantity": int(quantities.get("Aquantity", 10) or 0),
            "Bquantity": int(quantities.get("Bquantity", 0) or 0),
            "Cquantity": int(quantities.get("Cquantity", 0) or 0),
        }
        self.last_decision = None

    @classmethod
    def from_state(cls, state=None):
        if not isinstance(state, dict):
            return cls()
        bot = cls(
            money=state.get("money", 0),
            quantities=state.get("quantities") or {},
        )
        bot.last_decision = state.get("last_decision")
        return bot

    def to_dict(self):
        return {
            "money": int(self.money or 0),
            "quantities": dict(self.quantities),
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
            f"Bot: {self.portfolio_value(prices)} | "
            f"A{self.quantities['Aquantity']} "
            f"B{self.quantities['Bquantity']} "
            f"C{self.quantities['Cquantity']}"
        )

    def trade(self, prices, probabilities, steps):
        scores = self._score_markets(prices, probabilities, steps)
        if not scores:
            self.last_decision = {"action": "skip"}
            return self.last_decision

        best_market = max(scores, key=lambda market: scores[market]["roi"])
        best_score = scores[best_market]
        sold = {}
        bought = {}

        for market_id, market in MARKETS.items():
            quantity_key = market["quantity_key"]
            quantity = int(self.quantities.get(quantity_key, 0) or 0)
            if quantity <= 0:
                continue

            current_score = scores.get(market_id, {})
            should_sell_all = best_score["expected_change"] <= 0
            should_switch = market_id != best_market and current_score.get("roi", 0.0) < best_score["roi"]
            if should_sell_all or should_switch:
                price = int(prices.get(market["price_key"], 0) or 0)
                self.money += quantity * price
                self.quantities[quantity_key] = 0
                sold[market["label"]] = quantity

        if best_score["expected_change"] > 0:
            best = MARKETS[best_market]
            price = int(prices.get(best["price_key"], 0) or 0)
            if price > 0:
                count = int(self.money // price)
                if count > 0:
                    self.money -= count * price
                    self.quantities[best["quantity_key"]] += count
                    bought[best["label"]] = count

        self.last_decision = {
            "action": "trade" if sold or bought else "hold",
            "best_market": MARKETS[best_market]["label"],
            "sold": sold,
            "bought": bought,
            "scores": {
                MARKETS[market_id]["label"]: {
                    "expected_change": round(score["expected_change"], 3),
                    "roi": round(score["roi"], 4),
                }
                for market_id, score in scores.items()
            },
            "money": self.money,
            "quantities": dict(self.quantities),
        }
        return self.last_decision

    def _score_markets(self, prices, probabilities, steps):
        scores = {}
        for market_id, market in MARKETS.items():
            price = int(prices.get(market["price_key"], 0) or 0)
            step = int(steps.get(market["step_key"], 0) or 0)
            probs = probabilities.get(market_id, {}) or {}
            rise = float(probs.get("rise", 0.0) or 0.0) / 100.0
            fall = float(probs.get("fall", 0.0) or 0.0) / 100.0
            expected_change = (rise - fall) * step
            roi = expected_change / price if price > 0 else 0.0
            scores[market_id] = {
                "expected_change": expected_change,
                "roi": roi,
            }
        return scores
