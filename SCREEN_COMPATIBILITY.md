# Screen compatibility

The native window and the UI coordinate system are independent. Master images
fill the viewport using proportional cover scaling. `AdaptivePage` composites
a transparent 1680×1050 foreground fitted inside that viewport. UI art keeps
its proportions; excess space shows the master background. The existing start,
level, settings and language screens retain their own adaptive layouts.

New fixed-composition pages should inherit `AdaptivePage`, call `init_viewport`,
decorate `draw` with `adaptive_draw`, and use `events()` and `mouse_pos()` for
input. Draw to `self.screen`; pass `self.viewport` to child pages. Backgrounds
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
