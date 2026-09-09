"""Headless first-frame benchmark; each sample runs in a fresh process.

Run from any directory: .venv/Scripts/python.exe benchmarks/gameplay_startup.py
Uses synthetic game state and temporary files. Windows' file cache is not cleared.
"""
import argparse
import contextlib
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def sample(legacy_overlays=False):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame
    import asset_loaders
    import gameplay_assets
    import gameplay_page
    import game_state
    import profile_manager
    import game_stats
    import shop_card_stats

    pygame.init()
    screen = pygame.display.set_mode((1680, 1050))
    font_path = asset_loaders.find_font_path_or_exit()
    stages = {}
    image_times = {}
    image_counts = {}

    def timed(name, operation, target):
        def wrapped(*args, **kwargs):
            start = time.perf_counter()
            try:
                return operation(*args, **kwargs)
            finally:
                key = str(args[0]) if name is None else name
                target[key] = target.get(key, 0) + (time.perf_counter() - start) * 1000
                if name is None:
                    image_counts[key] = image_counts.get(key, 0) + 1
        return wrapped

    def surfaces_bytes(page):
        seen = set()

        def walk(value):
            if id(value) in seen:
                return 0
            seen.add(id(value))
            if isinstance(value, pygame.Surface):
                return value.get_pitch() * value.get_height()
            if isinstance(value, dict):
                return sum(walk(item) for item in value.values())
            if isinstance(value, (tuple, list)):
                return sum(walk(item) for item in value)
            return 0

        return walk(vars(page)) + sum(
            walk(value) for module in (gameplay_assets, asset_loaders)
            for name, value in vars(module).items() if "cache" in name
        )

    def frame_hash():
        return hashlib.sha256(pygame.image.tostring(screen, "RGBA")).hexdigest()

    with tempfile.TemporaryDirectory(prefix="bressoles-startup-") as tmp, contextlib.ExitStack() as stack:
        profile_manager.PROFILES_DIR = tmp
        profile_manager.INDEX_FILE = os.path.join(tmp, "index.json")
        game_stats.set_stats_file(os.path.join(tmp, "stats.csv"))
        game_stats.set_level6_experiment_stats_file(os.path.join(tmp, "level6.csv"))
        shop_card_stats.set_shop_card_stats_file(os.path.join(tmp, "shop.csv"))
        game_state.GOLDEN_STOCKS_AUDIT_PATH = Path(tmp) / "golden.log"
        if legacy_overlays:
            def load_legacy_overlays(path, sizes, warning_message=None):
                return {tuple(size): asset_loaders.load_scaled_image(
                    path, target_size=size, warning_message=warning_message,
                ) for size in sizes}
            stack.enter_context(patch.object(gameplay_page, "load_scaled_image_variants", load_legacy_overlays))
        for name in (
            "load_gameplay_core_assets", "load_gameplay_card_assets", "load_winlose_assets",
            "load_deck_view_assets", "load_gameplay_placeholders", "load_end_turn_button",
            "load_scaled_image_variants",
        ):
            stack.enter_context(patch.object(gameplay_page, name, timed(name, getattr(gameplay_page, name), stages)))
        stack.enter_context(patch.object(pygame.image, "load", timed(None, pygame.image.load, image_times)))
        results = {}
        for label in ("cold", "warm"):
            profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
            random.seed(7)
            stages.clear()
            image_times.clear()
            image_counts.clear()
            start = time.perf_counter()
            page = gameplay_page.GameplayPage(
                screen, font_path, "e", goal=100, level_number=2, round_num=1,
                boss_index=0, boss_filename="1_Watt.png", rounds_required=2,
                test_mode=True, profile_slot=None,
            )
            init_ms = (time.perf_counter() - start) * 1000
            page.draw()
            first_frame_ms = (time.perf_counter() - start) * 1000
            result = {
                "init_ms": init_ms, "first_frame_ms": first_frame_ms,
                "stages_ms": dict(stages), "other_init_ms": init_ms - sum(stages.values()),
                "image_decode_ms": sum(image_times.values()),
                "overlay_load_count": image_counts.get(os.path.join("Cards", "Arts", "Negative.png"), 0),
                "top_image_loads_ms": sorted(image_times.items(), key=lambda item: item[1], reverse=True)[:5],
                "first_frame_hash": frame_hash(),
                "surface_mib": surfaces_bytes(page) / 1024**2,
            }
            page.deck_view_active = True
            start = time.perf_counter()
            page.draw()
            result["first_deck_frame_ms"] = (time.perf_counter() - start) * 1000
            result["deck_frame_hash"] = frame_hash()
            page.deck_view_active = False
            page.draw()
            result["return_frame_hash"] = frame_hash()
            results[label] = result
            del page
            gc.collect()
    pygame.quit()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--legacy-overlays", action="store_true", help="Compare the previous three-decode overlay path")
    args = parser.parse_args()
    if args.sample:
        with contextlib.redirect_stdout(io.StringIO()):
            result = sample(args.legacy_overlays)
        print(json.dumps(result))
    else:
        if args.samples < 1:
            parser.error("--samples must be positive")
        results = [json.loads(subprocess.check_output(
            [sys.executable, str(Path(__file__).resolve()), "--sample"]
            + (["--legacy-overlays"] if args.legacy_overlays else []), text=True,
        )) for _ in range(args.samples)]
        medians = {
            label: {
                key: statistics.median(result[label][key] for result in results)
                for key in ("init_ms", "first_frame_ms", "image_decode_ms", "other_init_ms", "surface_mib", "first_deck_frame_ms")
            } for label in ("cold", "warm")
        }
        print(json.dumps({"medians": medians, "samples": results}, indent=2))
