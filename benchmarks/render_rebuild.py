"""Deterministic real-window render benchmark; never uses player profiles.

python benchmarks/render_rebuild.py --output benchmarks/render_before.json
Use --dummy only for correctness, not performance claims. Times exclude tick.
"""
import argparse
import contextlib
import cProfile
import ctypes
import hashlib
import gc
import io
import json
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'


def distribution(values):
    ordered = sorted(values)
    return {**{f'p{p}_ms': ordered[min(len(ordered)-1, int((len(ordered)-1)*p/100))]
               for p in (50, 95, 99)},
            'over_16_7': sum(x > 16.7 for x in values),
            'over_33_3': sum(x > 33.3 for x in values)}


def main(args):
    if args.code_root:
        sys.path.insert(0, str(Path(args.code_root).resolve()))
    if args.dummy:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
    import pygame
    import native_render as native
    import asset_loaders
    import gameplay_page
    import game_state
    import profile_manager
    import game_stats
    import shop_card_stats
    from shop_page import ShopPage
    from silver_black_page import SilverBlackPage
    from gameplay_tutorial import TutorialHint
    pygame.init()
    result = {'environment': {'os': platform.platform(), 'processor': platform.processor(),
              'python': sys.version, 'pygame': pygame.version.ver, 'sdl': pygame.get_sdl_version(),
              'driver': pygame.display.get_driver(), 'dummy': args.dummy,
              'dpi': ctypes.windll.user32.GetDpiForSystem() if os.name == 'nt' else None,
              'desktop': pygame.display.get_desktop_sizes(), 'seed': 7,
              'frames': args.frames, 'runs': args.runs, 'present_mode': args.present,
              'tick_fps': args.tick}, 'samples': []}
    font = asset_loaders.find_font_path_or_exit()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    profiler = cProfile.Profile()
    with tempfile.TemporaryDirectory(prefix='bressoles-render-') as tmp, contextlib.ExitStack() as stack:
        profile_manager.PROFILES_DIR = tmp
        profile_manager.INDEX_FILE = os.path.join(tmp, 'index.json')
        game_stats.set_stats_file(os.path.join(tmp, 'stats.csv'))
        game_stats.set_level6_experiment_stats_file(os.path.join(tmp, 'level6.csv'))
        shop_card_stats.set_shop_card_stats_file(os.path.join(tmp, 'shop.csv'))
        game_state.GOLDEN_STOCKS_AUDIT_PATH = Path(tmp) / 'golden.log'
        original_roll_stats = gameplay_page.MarketRollStats
        stack.enter_context(patch.object(gameplay_page, 'MarketRollStats',
            lambda: original_roll_stats(os.path.join(tmp, 'rolls.csv'), os.path.join(tmp, 'roll_summary.csv'))))
        # test_mode disables profile persistence; these guards catch accidental writes.
        stack.enter_context(patch.object(gameplay_page.GameplayPage, '_save_active_game'))
        stack.enter_context(patch('pygame.mouse.get_pos', return_value=(-100, -100)))
        for resolution in args.sizes.split(','):
            size = tuple(map(int, resolution.split('x')))
            viewport = pygame.display.set_mode(size)
            pygame.display.set_caption('Bressoles render benchmark — synthetic data')
            for scenario in args.scenes.split(','):
                for run in range(args.runs):
                    if args.collect:
                        gc.collect()
                    profile_manager.apply_profile_to_game_state(profile_manager._default_profile(1))
                    random.seed(7)
                    init_start = time.perf_counter()
                    page = gameplay_page.GameplayPage(viewport, font, 'e', goal=100,
                        level_number=2, round_num=1, boss_index=0, boss_filename='1_Watt.png',
                        rounds_required=2, test_mode=True, profile_slot=None)
                    page.market_cards = {m: {s: (11, 15, 17)[s % 3] for s in range(3)} for m in range(3)}
                    page.market_card_turns = {m: {s: 3 for s in range(3)} for m in range(3)}
                    page.hand_cards = ([11, 15, 17, 11, 15] * 3)[:page.hand]
                    page.side_cards_top = [100] * 6
                    page.hand_draw_anim = []
                    if scenario == 'shop':
                        page = ShopPage(viewport, font)
                    elif scenario == 'selection':
                        page = SilverBlackPage(viewport, font, [])
                    elif scenario == 'deck':
                        page.deck_view_active = True
                    elif scenario == 'pause':
                        page.pause_menu_active = True
                    elif scenario == 'tutorial':
                        page.tutorial_hint = TutorialHint(page.screen.get_size(), page.frame, font, page.ok1_button)
                    elif scenario == 'result':
                        page.win_lose_state = 'lose'
                        page.win_lose_y = page.win_lose_target_y
                    elif scenario == 'drag':
                        page.dragged_card_source, page.dragged_card_index = 'hand', 0
                        page.dragged_card_pos = (700, 500)
                    elif scenario == 'tooltip':
                        page.mouse_pos = lambda: (100, 135)
                    init_ms = (time.perf_counter()-init_start)*1000
                    first = time.perf_counter()
                    page.draw()
                    first_ms = (time.perf_counter()-first)*1000
                    if scenario == 'tooltip':
                        page.mouse_pos = lambda: page.stock_logo_rects[0].center
                    for _ in range(5):
                        page.draw()
                    turn_start = None
                    turn_duration = None
                    if scenario == 'end_turn':
                        turn_start = pygame.time.get_ticks()
                        page._start_turn_resolution()
                    counters = {'snapshots': 0, 'scale': 0, 'font_calls': 0, 'surface_copy': 0,
                                'image_load': 0, 'render_calls': 0, 'raw_recipe_key_miss': 0}
                    prep = [0.0]
                    depth = [0]
                    def counted(name, function):
                        def call(*a, **kw):
                            counters[name] += 1
                            return function(*a, **kw)
                        return call
                    old_render = native.render
                    def render(recipe, render_size):
                        counters['render_calls'] += 1
                        key = (recipe, tuple(max(1, round(v)) for v in render_size))
                        counters['raw_recipe_key_miss'] += key not in native._cache
                        start = time.perf_counter()
                        depth[0] += 1
                        try:
                            return old_render(recipe, render_size)
                        finally:
                            depth[0] -= 1
                            if depth[0] == 0:
                                prep[0] += (time.perf_counter()-start)*1000
                    frames, inputs, updates, presents, preparations, displays = [], [], [], [], [], []
                    original_present = page.present
                    present_ms = [0.0]
                    def present():
                        start = time.perf_counter()
                        original_present()
                        present_ms[0] += (time.perf_counter()-start)*1000
                    page.present = present
                    original_flip = pygame.display.flip
                    display_ms = [0.0]
                    def display_present():
                        start = time.perf_counter()
                        composition = getattr(page.screen, 'composition', None)
                        if args.present == 'update' and composition is not None and not page.screen.modal_layers:
                            from adaptive_page import content_rect
                            offset = content_rect(page.viewport.get_size()).topleft
                            dirty = [rect.move(offset) for rect in composition.dirty]
                            pygame.display.update(dirty)
                        else:
                            original_flip()
                        display_ms[0] += (time.perf_counter()-start)*1000
                    clock = pygame.time.Clock()
                    waits = []
                    jump_started, jump_durations = None, []
                    memory_samples = []
                    cache_before = native.cache_info() if hasattr(native, 'cache_info') else {}
                    cpu_start, wall_start = time.process_time(), time.perf_counter()
                    with contextlib.ExitStack() as measured:
                        measured.enter_context(patch('pygame.display.flip', display_present))
                        measured.enter_context(patch.object(native, 'render', render))
                        for owner, name, counter in ((native, '_snapshot', 'snapshots'),
                                (pygame.transform, 'smoothscale', 'scale'), (native.Font, 'render', 'font_calls'),
                                (native.Surface, 'copy', 'surface_copy'), (pygame.image, 'load', 'image_load')):
                            measured.enter_context(patch.object(owner, name, counted(counter, getattr(owner, name))))
                        for frame in range(args.frames):
                            start = time.perf_counter()
                            pygame.event.pump()
                            if args.handle_input and hasattr(page, 'handle_input'):
                                # Exercise input dispatch with no synthetic click.
                                with patch.object(page, 'events', return_value=iter(())):
                                    page.handle_input()
                            inputs.append((time.perf_counter()-start)*1000)
                            ustart = time.perf_counter()
                            if scenario in ('jump', 'effects'):
                                now = pygame.time.get_ticks() if args.realtime_jumps else 1000 + frame % 24 * 17
                                # Fixed trajectory samples by default; opt into real
                                # clocks for observed jump duration and output cadence.
                                with patch('pygame.time.get_ticks', return_value=now):
                                    if (jump_started is None if args.realtime_jumps else frame % 24 == 0):
                                        for m in (range(3) if scenario == 'effects' else (0,)):
                                            page._start_card_jump_animation(page.card_jump_animations[m], 0)
                                        jump_started = now
                                    page.update_card_jump_animations()
                                    if args.realtime_jumps and not any(page.card_jump_animations.values()):
                                        jump_durations.append(now - jump_started)
                                        jump_started = None
                            if scenario == 'drag':
                                page.dragged_card_pos = (700 + frame % 24, 500 - frame % 24)
                            if scenario == 'lifecycle':
                                phase = frame % 6
                                page.pause_menu_active = phase == 0
                                page.deck_view_active = phase == 1
                                if phase in (3, 4):
                                    viewport = pygame.display.set_mode((1920, 1080) if phase == 3 else size)
                                    page.viewport = viewport
                                if phase == 5:
                                    page.market_card_turns[0][0] = 1 + frame // 6 % 3
                                    page.Aprice = 2 + frame // 6 % 20
                            if scenario == 'end_turn':
                                # Same public update order for baseline and rebuilt page.
                                for method in ('update_arrow_animation', 'update_price_animation',
                                        'update_level6_bot_turn', 'update_card_jump_animations',
                                        'update_side_card_jump_animations', 'update_lifecycle_card_scale_animations',
                                        'update_lifecycle_card_shake_animations', 'update_market_clear_animations',
                                        'update_final_auto_liquidation_animation', 'update_astor_cash_burn_animation',
                                        'update_arkwright_share_theft_animation', 'update_price_card_processing',
                                        '_maybe_finalize_after_effect_animations', 'update_hand_compact_animation',
                                        'update_hand_draw_animation', 'update_win_lose_animation'):
                                    getattr(page, method)()
                                if turn_duration is None and not page._is_turn_resolution_active() and not page._is_hand_transition_active():
                                    turn_duration = pygame.time.get_ticks() - turn_start
                            updates.append((time.perf_counter()-ustart)*1000)
                            prep[0] = present_ms[0] = display_ms[0] = 0.0
                            if args.profile and run == 0:
                                profiler.enable()
                            page.draw()
                            profiler.disable()
                            preparations.append(prep[0])
                            presents.append(present_ms[0])
                            displays.append(display_ms[0])
                            frames.append((time.perf_counter()-start)*1000)
                            wstart = time.perf_counter()
                            if args.tick:
                                clock.tick(args.tick)
                            waits.append((time.perf_counter()-wstart)*1000)
                            if scenario == 'lifecycle' and frame % 6 == 5:
                                gc.collect()
                                memory_samples.append(process_memory())
                    wall = time.perf_counter()-wall_start
                    entry = {'size': size, 'actual_window': pygame.display.get_window_size(),
                        'scenario': scenario, 'run': run, 'init_ms': init_ms, 'first_frame_ms': first_ms,
                        'frame': distribution(frames), 'input': distribution(inputs),
                        'update': distribution(updates), 'prepare': distribution(preparations),
                        'present': distribution(presents), 'draw': distribution([
                            f-i-u-p-r for f,i,u,p,r in zip(frames,inputs,updates,preparations,presents)]),
                        'display': distribution(displays),
                        'composition': distribution([p-d for p,d in zip(presents, displays)]),
                        'cpu_percent_one_core': (time.process_time()-cpu_start)/wall*100,
                        'tick_wait': distribution(waits), 'counters': counters,
                        'output_fps': args.frames / wall,
                        'memory': process_memory(),
                        'end_turn_duration_ms': turn_duration,
                        'jump_durations_ms': jump_durations,
                        'memory_cycles': memory_samples,
                        'cache_bytes': native._cache_bytes, 'cache_entries': len(native._cache),
                        'hash': hashlib.sha256(pygame.image.tostring(viewport, 'RGBA')).hexdigest()}
                    if hasattr(native, 'cache_info'):
                        entry['cache_info'] = native.cache_info()
                        entry['warm_cache_delta'] = {key: entry['cache_info'][key] - cache_before[key]
                            for key in ('hits', 'misses', 'evictions', 'snapshots', 'scales', 'text_rasters')}
                    if args.screenshots and run == 0:
                        folder = ROOT / 'output' / 'render_rebuild' / output.stem
                        folder.mkdir(parents=True, exist_ok=True)
                        pygame.image.save(viewport, str(folder / f'{resolution}-{scenario}.png'))
                    result['samples'].append(entry)
                    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
                    print(f'{resolution} {scenario} {run}: p95 {entry["frame"]["p95_ms"]:.2f} ms', flush=True)
                    del page.present
                    del original_present
                    del page
    if args.profile:
        profiler.dump_stats(str(output.with_suffix('.prof')))
    pygame.quit()


def process_memory():
    if os.name != 'nt':
        return {'unavailable': True}
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (key, ctypes.c_size_t) for key in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    function = ctypes.windll.psapi.GetProcessMemoryInfo
    function.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    handle = ctypes.windll.kernel32.GetCurrentProcess
    handle.restype = wintypes.HANDLE
    if not function(handle(), ctypes.byref(counters), counters.cb):
        return {'error': ctypes.get_last_error()}
    return {'rss': counters.WorkingSetSize, 'private_bytes': counters.PrivateUsage,
            'peak_rss': counters.PeakWorkingSetSize}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--sizes', default='1366x768,1920x1080,2560x1440,3840x2160,1280x800,3440x1440')
    parser.add_argument('--scenes', default='static,jump,effects,drag,tooltip,deck,pause,tutorial,result,shop,selection')
    parser.add_argument('--frames', type=int, default=36)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--dummy', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--screenshots', action='store_true')
    parser.add_argument('--present', choices=('flip', 'update'), default='flip')
    parser.add_argument('--tick', type=int, default=0)
    parser.add_argument('--code-root', help='Directory with original modules for a baseline replay')
    parser.add_argument('--collect', action='store_true', help='Collect old page cycles between samples')
    parser.add_argument('--handle-input', action='store_true', help='Include empty-event input dispatch')
    parser.add_argument('--realtime-jumps', action='store_true', help='Use real time for repeated jump durations')
    main(parser.parse_args())
