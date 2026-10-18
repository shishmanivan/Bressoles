"""Lifetime random-roll statistics owned by a newly created player profile.

Counts describe sampled directions, before price limits or card reactions.
Forced movements and guaranteed distributions are excluded by the sampler.
"""

OUTCOMES = ("rise", "fall", "flat")
SCOPES = ("all", "invested")


def empty_stats():
    return {
        "version": 1,
        **{scope: {
            stock: {
                "rolls": 0,
                "actual": dict.fromkeys(OUTCOMES, 0),
                "expected": dict.fromkeys(OUTCOMES, 0.0),
            }
            for stock in "ABC"
        } for scope in SCOPES},
    }


def accumulate(stats, rolls, quantities):
    """Use holdings at sampling time; every roll has equal weight."""
    for roll in rolls:
        market = roll["market"]
        for scope in SCOPES:
            if scope == "invested" and quantities[market] <= 0:
                continue
            totals = stats[scope]["ABC"[market]]
            totals["rolls"] += 1
            totals["actual"][roll["outcome"]] += 1
            for outcome in OUTCOMES:
                totals["expected"][outcome] += roll["probabilities"][outcome] / 100


def summarize(stats, scope="all"):
    """Return display-ready counts and percentages; no trials means no percent.

    None denotes a legacy profile with no lifetime tracking. Expected counts
    sum each trial's probability, so changing card effects are weighted fairly.
    """
    if stats is None:
        return None
    result = {}
    for stock, totals in stats[scope].items():
        count = totals["rolls"]
        result[stock] = {
            "rolls": count,
            "outcomes": {
                outcome: {
                    "actual": totals["actual"][outcome],
                    "expected": totals["expected"][outcome],
                    "actual_percent": 100 * totals["actual"][outcome] / count if count else None,
                    "expected_percent": 100 * totals["expected"][outcome] / count if count else None,
                } for outcome in OUTCOMES
            },
        }
    return result
