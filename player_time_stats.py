"""Private play-time counters for newly created profiles."""
from copy import deepcopy


def empty_stats():
    return {"version": 1, "total_seconds": 0.0, "levels": {}, "rounds": {}}


def record(stats, level, round_id, seconds):
    key = str(round_id)
    if key in stats["rounds"]:
        return
    seconds = max(0.0, float(seconds or 0))
    stats["rounds"][key] = {"level": int(level), "seconds": seconds}
    level_data = stats["levels"].setdefault(str(int(level)), {"seconds": 0.0, "rounds": 0})
    level_data["seconds"] += seconds
    level_data["rounds"] += 1
    stats["total_seconds"] += seconds


def copy_stats(stats):
    return deepcopy(stats)
