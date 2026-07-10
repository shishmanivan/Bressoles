from simple_stock_bot import MARKETS, SimpleStockBot


class AdvancedStockBot(SimpleStockBot):
    """Stock bot that knows exact market probabilities, but not cards."""

    display_name = "Босс"

    def trade(self, prices, probabilities):
        scores = self._score_markets(prices, probabilities)
        return self._trade_with_scores(prices, scores)

    def _score_markets(self, prices, probabilities):
        scores = super()._score_markets(prices)
        for market_id, market in MARKETS.items():
            probs = probabilities.get(market_id, {}) or {}
            rise = self._probability_value(probs.get("rise", 0.0))
            flat = self._probability_value(probs.get("flat", 0.0))
            fall = self._probability_value(probs.get("fall", 0.0))

            probability_score = ((rise - fall) / 100.0) * 1.8 + (flat / 100.0) * 0.15
            scores[market_id]["score"] += probability_score
            scores[market_id]["rise"] = round(rise, 2)
            scores[market_id]["flat"] = round(flat, 2)
            scores[market_id]["fall"] = round(fall, 2)

        return scores

    def _probability_value(self, value):
        try:
            return max(0.0, float(value or 0.0))
        except (TypeError, ValueError):
            return 0.0
