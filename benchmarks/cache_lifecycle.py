"""Measure retained caches across page transitions and resizing (headless).

Uses synthetic state and temporary runtime files. Windows memory counters describe
this benchmark process; pixel-buffer counts describe only the inspected objects.
"""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import time
import weakref


ROOT = Path(__file__).resolve().parents[1]


def process_memory():
    if os.name != "nt":
        return {"working_set_mib": None, "private_mib": None}

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                "PagefileUsage", "PeakPagefileUsage", "PrivateUsage",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"working_set_mib": counters.WorkingSetSize / 1024**2, "private_mib": counters.PrivateUsage / 1024**2}


def run(cycles, resize_steps, legacy_menu_cache=False):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame
    import asset_loaders
    import gameplay_assets
    import round_page_assets
    import boss_page
    import sound_assets
    import game_state
    import profile_manager
    import game_stats
    import shop_card_stats
    from gameplay_page import GameplayPage
    from start_page import StartPage

    if legacy_menu_cache:
        class LegacyStartPage(StartPage):
            def _scaled(self, image, target_size):
                if image is None:
                    return None
                key = (id(image), tuple(target_size))
                scaled = self._scaled_image_cache.get(key)
                if scaled is None:
                    scaled = pygame.transform.smoothscale(image, target_size)
                    self._scaled_image_cache[key] = scaled
                return scaled
        StartPage = LegacyStartPage

    pygame.init()
    screen = pygame.display.set_mode((1680, 1050))
    background = asset_loaders.load_main_background((1680, 1050))
    font_path = asset_loaders.find_font_path_or_exit()
    modules = (asset_loaders, gameplay_assets, round_page_assets, boss_page, sound_assets)
    retired = []
    results = []

    def snapshot(label, live=None, **extra):
        gc.collect()
        seen = set()
        surface_count = 0

        def walk(value):
            nonlocal surface_count
            if id(value) in seen:
                return 0
            seen.add(id(value))
            if isinstance(value, pygame.Surface):
                surface_count += 1
                return value.get_pitch() * value.get_height()
            if isinstance(value, dict):
                return sum(walk(item) for item in value.values())
            if isinstance(value, (list, tuple)):
                return sum(walk(item) for item in value)
            return 0

        caches = {
            f"{module.__name__}.{name}": value for module in modules
            for name, value in vars(module).items() if "cache" in name and isinstance(value, (dict, list, tuple))
        }
        global_bytes = sum(walk(value) for value in caches.values())
        global_count = surface_count
        live_bytes = walk(vars(live)) if live is not None else 0
        results.append({
            "label": label, "viewport": list(screen.get_size()),
            "global_surface_mib": global_bytes / 1024**2, "global_surface_count": global_count,
            "live_extra_surface_mib": live_bytes / 1024**2,
            "cache_entries": {name: len(value) for name, value in caches.items()},
            "live_cache_entries": {name: len(value) for name, value in vars(live).items()
                                   if "cache" in name and isinstance(value, dict)} if live is not None else {},
            "retired_pages_alive": sum(ref() is not None for ref in retired),
            **process_memory(), **extra,
        })

    with tempfile.TemporaryDirectory(prefix="bressoles-cache-lifecycle-") as tmp:
        profile_manager.PROFILES_DIR = tmp
        profile_manager.INDEX_FILE = os.path.join(tmp, "index.json")
        game_stats.set_stats_file(os.path.join(tmp, "stats.csv"))
        game_stats.set_level6_experiment_stats_file(os.path.join(tmp, "level6.csv"))
        shop_card_stats.set_shop_card_stats_file(os.path.join(tmp, "shop.csv"))
        game_state.GOLDEN_STOCKS_AUDIT_PATH = Path(tmp) / "golden.log"
        sizes = [(1680, 1050)] * cycles + [(1280, 720), (1920, 1080), (1680, 1050)] * 2
        for index, size in enumerate(sizes):
            screen = pygame.display.set_mode(size)
            profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
            random.seed(7)
            menu = StartPage(screen, background, font_path, profile_name="Benchmark")
            menu.draw()
            retired.append(weakref.ref(menu))
            del menu
            start = time.perf_counter()
            page = GameplayPage(screen, font_path, "e", goal=100, level_number=2,
                                round_num=1, boss_index=0, boss_filename="1_Watt.png",
                                rounds_required=2, test_mode=True, profile_slot=None)
            page.draw()
            gameplay_ms = (time.perf_counter() - start) * 1000
            page.deck_view_active = True
            page.draw()
            page.deck_view_active = False
            page.draw()
            retired.append(weakref.ref(page))
            del page
            menu = StartPage(screen, background, font_path, profile_name="Benchmark")
            menu.draw()
            snapshot(f"route_{index + 1}", menu, gameplay_ms=gameplay_ms)
            retired.append(weakref.ref(menu))
            del menu

        menu = StartPage(screen, background, font_path, profile_name="Benchmark")
        menu.draw()
        snapshot("resize_start", menu)
        for index in range(resize_steps):
            screen = pygame.display.set_mode((1280 + 16 * index, 720 + 9 * index))
            menu.screen = screen
            start = time.perf_counter()
            menu.draw()
            draw_ms = (time.perf_counter() - start) * 1000
            snapshot(f"resize_{index + 1}", menu, menu_draw_ms=draw_ms)
            results[-1]["frame_hash"] = hashlib.sha256(pygame.image.tostring(screen, "RGBA")).hexdigest()
        screen = pygame.display.set_mode((1680, 1050))
        menu.screen = screen
        start = time.perf_counter()
        menu.draw()
        draw_ms = (time.perf_counter() - start) * 1000
        snapshot("resize_return", menu, menu_draw_ms=draw_ms)
        results[-1]["frame_hash"] = hashlib.sha256(pygame.image.tostring(screen, "RGBA")).hexdigest()
        retired.append(weakref.ref(menu))
        del menu
        snapshot("all_pages_released")
    pygame.quit()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--resize-steps", type=int, default=12)
    parser.add_argument("--legacy-menu-cache", action="store_true", help="Compare the previous cache retaining all window sizes")
    args = parser.parse_args()
    if args.cycles < 1 or args.resize_steps < 0:
        parser.error("cycles must be positive and resize-steps nonnegative")
    with contextlib.redirect_stdout(io.StringIO()):
        result = run(args.cycles, args.resize_steps, args.legacy_menu_cache)
    print(json.dumps(result, indent=2))
