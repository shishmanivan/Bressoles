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
The native image/text cache is bounded to 64 MiB and 512 entries. Glyph recipes
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
