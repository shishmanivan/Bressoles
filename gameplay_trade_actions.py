MARKET_KEYS = {
    0: ("Aprice", "Aquantity"),
    1: ("BPrice", "Bquantity"),
    2: ("CPrice", "Cquantity"),
}


def apply_arrow_trade(money, quantities, prices, frame_idx, arrow_type, blocked_buy_prices=None):
    """Apply a buy/sell arrow action and return updated trade state."""
    if frame_idx not in MARKET_KEYS:
        return {
            "money": money,
            "quantities": dict(quantities),
            "changed": False,
        }

    price_key, quantity_key = MARKET_KEYS[frame_idx]
    price = prices.get(price_key)
    blocked_buy_prices = set(blocked_buy_prices or [])
    updated_quantities = dict(quantities)
    updated_money = money
    changed = False

    # Top arrow: buy as many shares as possible in this market.
    if arrow_type == 0:
        if price and price > 0 and price not in blocked_buy_prices:
            shares_to_buy = updated_money // price
            if shares_to_buy > 0:
                updated_money -= shares_to_buy * price
                updated_quantities[quantity_key] += shares_to_buy
                changed = True

    # Second arrow: buy one share in this market.
    elif arrow_type == 1:
        if price and price > 0 and price not in blocked_buy_prices and updated_money >= price:
            updated_money -= price
            updated_quantities[quantity_key] += 1
            changed = True

    # Third arrow: sell one share from this market.
    elif arrow_type == 2:
        if updated_quantities[quantity_key] > 0:
            updated_money += price
            updated_quantities[quantity_key] -= 1
            changed = True

    # Bottom arrow: sell all shares from this market.
    elif arrow_type == 3:
        updated_money += updated_quantities[quantity_key] * price
        updated_quantities[quantity_key] = 0
        changed = True

    return {
        "money": updated_money,
        "quantities": updated_quantities,
        "changed": changed,
    }
