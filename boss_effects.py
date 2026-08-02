import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BossEffect:
    raw: str
    normalized: str
    kind: str
    target: str = None
    source: str = None
    operator: str = None
    value: int = None


def normalize_boss_effect(value):
    return str(value or "").strip().replace(" ", "").replace("_", "").replace("-", "").lower()


REWARD_KINDS = {
    "redcard": "red_card",
    "freeshop": "free_shop",
    "nextshopfree": "free_shop",
    "shopfree": "free_shop",
    "shopdiscount100": "free_shop",
    "updownplus4": "updown_plus4",
    "updownsideplus4": "updown_plus4",
    "upsideanddownsideplus4": "updown_plus4",
    "upsidedownsideplus4": "updown_plus4",
    "upside/downside+4": "updown_plus4",
    "probabilitycardsplus4": "updown_plus4",
    "startcsharesplus2": "start_c_plus2",
    "startcplus2": "start_c_plus2",
    "csharesplus2": "start_c_plus2",
    "cshares=cshares+2": "start_c_plus2",
    "cquantity=cquantity+2": "start_c_plus2",
    "gaindropcard": "gain_drop_card",
    "randomgaindrop": "gain_drop_card",
    "randomgaindropcard": "gain_drop_card",
    "silvercard": "silver_card",
    "randomsilver": "silver_card",
    "randomsilvercard": "silver_card",
    "randsilver": "silver_card",
    "lifecycleslotplus1": "lifecycle_slot_plus1",
    "cardslotplus1": "lifecycle_slot_plus1",
    "randomgoldcard": "gold_card",
    "goldcard": "gold_card",
    "sayrandomreward": "say_random_reward",
    "randomprize": "say_random_reward",
    "shopofferplus1": "shop_offer_plus1",
    "extrashopoffer": "shop_offer_plus1",
}

FUNCTIONALITY_KINDS = {
    "arkwrightstealshares": "arkwright_steal",
    "stealshares": "arkwright_steal",
    "sharesteal": "arkwright_steal",
    "oddturntradingonly": "odd_turn_trading",
    "kolbeoddturntrading": "odd_turn_trading",
    "tradingoddturnsonly": "odd_turn_trading",
    "noprice2buys": "no_price2_buys",
    "nobuyprice2": "no_price2_buys",
    "cannotbuyprice2": "no_price2_buys",
    "forbidprice2buys": "no_price2_buys",
    "blockprice2buys": "no_price2_buys",
    "oneredonegaindropperturn": "card_limit",
    "limitredgaindrop": "card_limit",
    "stephensoncardlimit": "card_limit",
    "blockcardturnextensions": "block_card_turn_extensions",
    "malthusnoturncards": "block_card_turn_extensions",
    "twomarketslots": "market_slot_limit",
    "ricardomarketslots": "market_slot_limit",
    "seventurnseconds": "turn_timer",
    "sayturntimer": "turn_timer",
    "halfroundnapoleondors": "half_round_napoleondors",
    "peabodyhalfroundreward": "half_round_napoleondors",
    "simplestockbot": "simple_stock_bot",
    "stockbot": "simple_stock_bot",
    "bot": "simple_stock_bot",
    "liststockbot": "list_stock_bot",
    "friedrichliststockbot": "list_stock_bot",
    "listbot": "list_stock_bot",
    "bot2": "advanced_stock_bot",
    "bot2percent": "advanced_stock_bot",
    "bot2percentage": "advanced_stock_bot",
    "bot2procent": "advanced_stock_bot",
    "bot2procentny": "advanced_stock_bot",
    "bot2procentnyi": "advanced_stock_bot",
    "bot2percentbot": "advanced_stock_bot",
    "bot2percentagebot": "advanced_stock_bot",
    "advancedstockbot": "advanced_stock_bot",
    "probabilitystockbot": "advanced_stock_bot",
    "advancedliststockbot": "advanced_stock_bot",
    "probabilityliststockbot": "advanced_stock_bot",
    "listprobabilitybot": "advanced_stock_bot",
    "laffittebot": "advanced_stock_bot",
    "laffittepercentbot": "advanced_stock_bot",
    "goal=goal*1.3": "goal_multiplier",
}

ASSIGNMENT_PATTERN = re.compile(
    r"^(?P<target>(?:Self\.)?[A-Za-z][A-Za-z0-9]*)="
    r"(?:(?P<source>(?:Self\.)?[A-Za-z][A-Za-z0-9]*)(?P<operator>[+-]))?"
    r"(?P<value>\d+)$"
)


def _parse_assignment(raw, normalized, allowed_targets):
    match = ASSIGNMENT_PATTERN.fullmatch(str(raw).strip().replace(" ", ""))
    if not match:
        return None
    target = match.group("target").removeprefix("Self.")
    source = (match.group("source") or "").removeprefix("Self.") or None
    operator = match.group("operator")
    if target not in allowed_targets:
        raise ValueError(f"unsupported assignment target '{target}'")
    if operator and source != target:
        raise ValueError(f"assignment source '{source}' must match target '{target}'")
    return BossEffect(
        raw=str(raw).strip(),
        normalized=normalized,
        kind="assignment",
        target=target,
        source=source,
        operator=operator,
        value=int(match.group("value")),
    )


def _parse_single_reward(raw):
    normalized = normalize_boss_effect(raw)
    if normalized.startswith("guaranteeredstart="):
        count = normalized.split("=", 1)[1]
        if not count.isdigit():
            raise ValueError(f"invalid GuaranteeRedStart count in '{raw}'")
        return BossEffect(str(raw).strip(), normalized, "guarantee_red_start", value=int(count))
    if normalized in REWARD_KINDS:
        return BossEffect(str(raw).strip(), normalized, REWARD_KINDS[normalized])
    assignment = _parse_assignment(raw, normalized, {"Dobor", "Money", "LastTurn", "hand"})
    if assignment:
        return assignment
    raise ValueError(f"unknown boss reward effect '{raw}'")


def _parse_single_functionality(raw):
    normalized = normalize_boss_effect(raw)
    if normalized in FUNCTIONALITY_KINDS:
        return BossEffect(str(raw).strip(), normalized, FUNCTIONALITY_KINDS[normalized])
    assignment = _parse_assignment(raw, normalized, {"LastTurn", "hand", "LevelRounds"})
    if assignment:
        return assignment
    raise ValueError(f"unknown boss functionality effect '{raw}'")


def _parse_spec(spec, parser):
    return [parser(raw.strip()) for raw in str(spec or "").split(",") if raw.strip()]


def parse_boss_reward_spec(spec):
    return _parse_spec(spec, _parse_single_reward)


def parse_boss_functionality_spec(spec):
    return _parse_spec(spec, _parse_single_functionality)
