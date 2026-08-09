import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceCardSpec:
    card_id: int
    image_base_id: int
    action: int
    turns: int
    operation: str = "add"


PRICE_CARD_SPECS = {
    spec.card_id: spec
    for spec in (
        PriceCardSpec(11, 11, 2, 1),
        PriceCardSpec(12, 11, 2, 2),
        PriceCardSpec(13, 11, 4, 1),
        PriceCardSpec(14, 11, 4, 2),
        PriceCardSpec(15, 15, -2, 1),
        PriceCardSpec(16, 15, -2, 2),
        PriceCardSpec(17, 17, 2, 1, "multiply"),
        PriceCardSpec(18, 17, 2, 2, "multiply"),
    )
}

REGULATION_CARD_TURNS = {
    20: 2,
    21: 3,
}

CATALYST_CARD_ID = 210
CATALYST_PERCENTAGE_POINTS = 10
GOLD_CATALYST_CARD_ID = 414
GOLD_CATALYST_PERCENTAGE_POINTS = 15
# Explicit contract shared by Catalyst cards 210 and 414. Pool inclusion chances
# from Cards.csv are intentionally not card effects and are not modified.
CATALYST_AFFECTED_CARD_IDS = frozenset({1, 2, 3, 4, 125, 215, 302, 401, 406, 407, 410, 413})
CATALYST_REVERSE_PERCENTAGE_CARD_IDS = frozenset({3, 4, 215, 401})

BID_CARD_VALUES = {
    118: 10,
    119: 20,
    120: 30,
    121: 50,
    122: 100,
}

CARD_IMAGE_BASE_IDS = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    100: 100,
    **{card_id: spec.image_base_id for card_id, spec in PRICE_CARD_SPECS.items()},
    20: 20,
    21: 20,
    **{card_id: 118 for card_id in BID_CARD_VALUES},
}
PRICE_CARD_IDS = frozenset(PRICE_CARD_SPECS)
PRICE_CARD_ACTIONS = {card_id: spec.action for card_id, spec in PRICE_CARD_SPECS.items()}
PRICE_CARD_TURNS = {card_id: spec.turns for card_id, spec in PRICE_CARD_SPECS.items()}
MARKET_CARD_TURNS = {**PRICE_CARD_TURNS, **REGULATION_CARD_TURNS}
MARKET_DURATION_CARD_IDS = frozenset(MARKET_CARD_TURNS)
REGULATION_CARD_IDS = frozenset(REGULATION_CARD_TURNS)
SUPPORTED_CARD_IDS_BY_TYPE = {
    1: frozenset({1, 2, 3, 4}) | PRICE_CARD_IDS | REGULATION_CARD_IDS,
    2: frozenset({100, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126}),
    3: frozenset({201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 214, 215, 217, 218, 219, 220}),
    4: frozenset({301, 302, 303}),
    5: frozenset({401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418}),
}


def get_card_image_base_id(card_id):
    try:
        normalized = int(card_id)
    except (TypeError, ValueError):
        return card_id
    return CARD_IMAGE_BASE_IDS.get(normalized, normalized)


def get_price_card_spec(card_id):
    try:
        return PRICE_CARD_SPECS.get(int(card_id))
    except (TypeError, ValueError):
        return None


def validate_card_catalog(cards, cards_dir="Cards", check_assets=True):
    errors = []
    configured_ids = {int(card_id) for card_id in cards}

    for card_id, spec in PRICE_CARD_SPECS.items():
        if card_id not in configured_ids:
            errors.append(f"Card catalog: price card {card_id} is absent from Cards.csv")
            continue
        if spec.operation not in ("add", "multiply"):
            errors.append(f"Card catalog: card {card_id} has unsupported operation '{spec.operation}'")
        if spec.action == 0:
            errors.append(f"Card catalog: card {card_id} must have a non-zero action")
        if spec.turns <= 0:
            errors.append(f"Card catalog: card {card_id} must have positive turns")
        card_row = cards.get(card_id) or cards.get(str(card_id)) or {}
        if card_row.get("Type") != 1:
            errors.append(f"Card catalog: price card {card_id} must have Type=1")

    for card_id, turns in REGULATION_CARD_TURNS.items():
        if card_id not in configured_ids:
            errors.append(f"Card catalog: regulation card {card_id} is absent from Cards.csv")
            continue
        if turns <= 0:
            errors.append(f"Card catalog: regulation card {card_id} must have positive turns")
        card_row = cards.get(card_id) or cards.get(str(card_id)) or {}
        if card_row.get("Type") != 1:
            errors.append(f"Card catalog: regulation card {card_id} must have Type=1")

    for card_id, card_row in cards.items():
        normalized_id = int(card_id)
        card_type = card_row.get("Type")
        supported_ids = SUPPORTED_CARD_IDS_BY_TYPE.get(card_type, frozenset())
        if normalized_id not in supported_ids:
            errors.append(
                f"Card catalog: card {normalized_id} Type={card_type} has no implemented gameplay contract"
            )

    supported_ids = set().union(*SUPPORTED_CARD_IDS_BY_TYPE.values())
    for card_id in sorted(supported_ids - configured_ids):
        errors.append(f"Card catalog: supported card {card_id} is absent from Cards.csv")

    if check_assets:
        checked_base_ids = set()
        for card_id in sorted(configured_ids):
            base_id = get_card_image_base_id(card_id)
            if base_id in checked_base_ids:
                continue
            checked_base_ids.add(base_id)
            card_path = os.path.join(cards_dir, f"Card_{base_id}.png")
            if not os.path.exists(card_path):
                errors.append(f"Card catalog: image base for card {card_id} is missing: {card_path}")
    return errors
