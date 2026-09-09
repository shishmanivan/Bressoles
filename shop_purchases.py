"""Card and license purchases, independent of the shop screen."""

from dataclasses import dataclass
from typing import Literal

import game_state


@dataclass(frozen=True)
class PurchaseResult:
    status: Literal["purchased", "already_owned", "no_space", "insufficient_funds"]
    card_id: int | None = None

    @property
    def purchased(self):
        return self.status == "purchased"

    @property
    def offer_exhausted(self):
        return self.status in ("purchased", "already_owned")


def buy_card_or_license(level_number, offer):
    """Apply an offer using its final price, which already includes discounts."""
    kind = offer.get("kind")
    if kind not in ("card", "license"):
        raise ValueError("Only card and license offers are supported")

    cost = float(offer.get("cost", 0) or 0)
    # Keep the existing priority: insufficient funds is reported before ownership.
    if game_state.napoleondors < cost:
        return PurchaseResult("insufficient_funds")

    card_id = int(offer.get("card_id", 0) or 0)
    if kind == "card":
        if game_state.is_shop_card_already_bought(card_id):
            return PurchaseResult("already_owned", card_id)
        if game_state.add_shop_card_to_level(level_number, card_id) is None:
            return PurchaseResult("no_space", card_id)
    else:
        if game_state.is_card_licensed(card_id) or not game_state.unlock_card_license(card_id):
            return PurchaseResult("already_owned", card_id)

    # A zero-cost offer still succeeds; spending zero is a no-op in game_state.
    game_state.spend_napoleondors(cost)
    return PurchaseResult("purchased", card_id)
