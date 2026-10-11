# Screen compatibility

The native window and the UI coordinate system are independent. Master images
fill the viewport using proportional cover scaling. `AdaptivePage` composites
a foreground rendered at the final fitted pixel size. The 1680×1050 design
coordinate system is only used for layout and input; it is not a framebuffer
that gets resized for presentation. UI art keeps its proportions; excess space
shows the master background. The existing start,
level, settings and language screens retain their own adaptive layouts.

New fixed-composition pages should inherit `AdaptivePage`, call `init_viewport`,
decorate `draw` with `adaptive_draw`, and use `events()` and `mouse_pos()` for
input. Draw to `self.screen`; pass `self.viewport` to child pages.

Adaptive pages and their artwork helpers use `import native_render as pygame`.
This scoped facade leaves the real pygame module unchanged. It preserves image
sources, font descriptions, and operations on composite widgets. The Canvas
maps coordinates and clip rectangles onto `screen.pixels`, a surface at the
final display size. Font glyphs are freshly rasterized at the scaled font size;
image variants are sampled from original pixels rather than smaller variants.
Adjacent tile endpoints share rounded pixel boundaries to prevent frame seams.
The native image/text cache is bounded to 64 MiB and 512 entries. Scale aliases
share one native entry. A separate logical transform cache is capped at 8 MiB /
64 entries; it prevents repeated hover scaling and returns editable copies.
Glyph recipes
are cached per font (64 strings); no SDL font handles survive via a global cache.

Use facade drawing, loading, and scaling helpers for this path. Keep input and
layout in design coordinates. `draw_modal_shade` captures native layers, dims
the entire viewport after background composition, and preserves bright dialogs.
`present()` blits these native layers directly, without rescaling them.

Backgrounds
belong in `master_background_path`, not in the foreground layer. Do not read
raw mouse coordinates in page helpers. Resize is picked up at each frame.

From the repository root, run:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m unittest discover -s tests
```

`tests/test_adaptive_pages.py` exercises real page drawing and button input at
1366×768, 1280×800, 1920×1080, 2560×1440 and 3440×1440, plus card drag/drop.
The display tests check fitting inside laptop work areas including decorations.

## Windows release check

Headless Linux tests do not validate native Windows DPI, monitor switching or
the packaged executable. Before publishing the Steam build, check on the laptop
and workstation with Windows scaling at 100%, 125% and 150%:

- Start in windowed mode; the complete window must fit above the taskbar.
- Resize, maximize, switch fullscreen/windowed and change resolution.
- Visit profiles, levels, bosses, rounds, card selection, gameplay and shop.
- Click the end-turn button, choose a boss/round, drag a card, scroll collections,
  dismiss tutorials and result dialogs, and return from shop subpages.
- Check that text is readable and hit areas follow the visible controls.
- Move the window between monitors with different DPI and restart with saved settings.

The minimum window is 640×400 to avoid an oversized native window; this is not
a claim of release-quality readability at that size. Validate readability at
the actual minimum display size advertised in the release requirements.

## Native-render regression checks

`tests/test_native_render.py` verifies direct-source image sampling, native
font pixels (including composite widgets), fractional-scale tile seams, clipping,
and presentation without any framebuffer scaling. `test_modal_composition.py`
checks that full-viewport shading remains independent of artwork alpha.

Visual checks cover gameplay and tutorial frames at 1920×1080 and 1366×768.

## Gameplay composition and invalidation

`GameplayPage.draw` delegates to table/panels, hand, moving cards, controls,
and overlays, in that order. `update_gameplay` owns effect progression. Drawing
may refresh hit rectangles and hover presentation; it must not apply card
effects, advance RNG, or save a profile. Tests compare serialized gameplay and
RNG state around actual drawing.

Gameplay alone opts into `GameplayComposition`. It retains a native RGBA table
and compares the small ordered paint keys: immutable recipe/version, final
destination, source area, clip, color and blend flags. This covers card/slot,
price, Turns, money, localization, highlights and animation position without
hashing saves. Unchanged commands do not repaint. Changed old/new rectangles
are merged, cleared and repainted with every intersecting layer in original
order. Above 45% damaged area (or on first frame/resize), repaint the whole
table. This preserves overlaps, transparent edges, and moving card labels.
Final presentation remains a full native frame unless a measured experiment
explicitly selects a different display path; no completed frame is scaled.

The immediate reference path remains available by setting
`page.screen.composition = None`. Use it for pixel comparisons and debugging.
New artwork must use the facade; direct writes to `screen.pixels` bypass damage
tracking. Flush the composition before reading its pixels mid-frame. Primitive
rectangles/ellipses use conservative bounds; other primitives conservatively
invalidate their clip. Native fonts use actual hinted bounds.

Facade Surfaces own immutable pixel sources and publish a new recipe after
recorded edits. Never cache plain mutable pygame Surfaces by `id`; those are
snapshotted per use. `Surface.wrap(raw)` takes ownership of a pixel copy. After
raw PixelArray/surfarray writes to a facade Surface, call `invalidate_pixels()`;
`fill`, `blit`, drawing, `set_at`, alpha and colorkey edits invalidate normally.
Keep loaded resources and Font objects on their page or in the existing asset
loaders. `Font.render` still returns an editable copy for pygame compatibility.
Position-dependent rounding retains the existing tile geometry; native size
variants are bounded by the cache, not by the number of positions.

Resize and page activation clear shared native/transform variants. The retained
table holds one current command list and one fitted native Surface, replaced on
resize and released with the page. Account for this memory separately from the
64 MiB cache, together with the background, Canvas, source asset caches and
optional modal surfaces. A single modal borrows the retained table and caches
its opaque shaded background; nested modals use reusable native snapshots.
Dialogs stay bright and shade is applied after background composition.

Animation time stops during pause, tutorial, deck view and lost keyboard focus.
The explicit timestamp registry is in `gameplay_animation_clock.py`; register
new animation clocks there. A long active stall advances at most 250 ms per
loop, retaining the existing sequential effect order. Jump/scatter trajectories
use the original 60 Hz recurrence, price/arrow frames catch up by elapsed time,
and hand/scale/shake/result animations retain their existing time-based paths.

Run `python benchmarks/render_rebuild.py --output benchmarks/render_after.json
--screenshots` in a real desktop session for six sizes and three runs per scene.
`--dummy` is only a correctness check. `--profile` writes cProfile data;
`--present update` compares dirty display updates with the normal full flip;
`--scenes end_turn --frames 600 --tick 60` measures a real sequential turn.
PNG output is under `output/render_rebuild/`. Machine-readable timings include
first draw and warm percentiles, stage timing, CPU, memory, cache counters and
frame hashes. See `benchmarks/RENDER_REBUILD_REPORT.md` for measured scope and
limitations; these numbers do not certify a different laptop or DPI setting.
`--scenes lifecycle --frames 120 --collect` exercises repeated modal/resize
cycles and records process memory after each cycle. `--realtime-jumps --tick 60`
records observed jump durations and output cadence instead of fixed trajectory
samples. Longer runs and their limitations are in
`benchmarks/RENDER_REBUILD_RUNTIME.md`; the 1080p p95 target is not consistently
met across sessions on the current machine, despite the large improvement.
