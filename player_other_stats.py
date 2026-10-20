"""Profile and run summaries with idempotent per-round checkpoints."""
from copy import deepcopy


def empty_stats():
    return {"cards": 0, "rounds": 0, "earned": 0.0, "best": None, "checkpoints": {}}


def record(stats, round_id, cards, *, earned=None, label=None):
    """Commit cumulative cards and, once completed, the round's earnings."""
    previous = stats["checkpoints"].setdefault(round_id, {"cards": 0, "finished": False})
    cards = max(previous["cards"], int(cards))
    stats["cards"] += cards - previous["cards"]
    previous["cards"] = cards
    if earned is not None and not previous["finished"]:
        previous["finished"] = True
        stats["rounds"] += 1
        stats["earned"] += earned
        if stats["best"] is None or earned > stats["best"]["earned"]:
            stats["best"] = {"earned": earned, "label": deepcopy(label)}


def average(stats):
    return stats["earned"] / stats["rounds"] if stats["rounds"] else None
