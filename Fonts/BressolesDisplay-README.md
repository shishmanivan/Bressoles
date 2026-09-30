# Бресоль / Bressoles Display — 0.110

First working display face for the Bressoles main menu, inspired exclusively by
the menu lettering in the reference image dated 21 December 2025. The logo in
that image was not used. The game's separate title artwork is unchanged.

All outlines are original constructions in `tools/build_bressoles_font.py`.
No existing font is loaded, traced, renamed, or used as an outline source.
The historical direction is refined nineteenth-century print: vertical stress,
contrasting strokes, narrow oval counters, curved serif brackets and tapered
arm terminals. Lowercase code points deliberately render as small capitals,
with a 518-unit height against 700-unit full capitals. This reproduces the
capital initial / small-cap remainder seen in the reference menu. It is a
display design for menus and headings; ordinary lowercase body typography is
not part of this first version.

## Rounded contour revision — 0.110

Serif tips, bar-to-stem joins, counters and accent corners have tangent
fillets in the vector outlines. Concave joins use a larger radius than outer
tips; small capitals and marks receive proportionately smaller radii. Existing
smooth curves are retained, and the corner cuts are limited to protect thin
strokes. A/M/N/V/W/Y have continuous diagonal silhouettes, replacing the
overlapping stroke ends that produced projecting angular fragments. Cyrillic
equivalents, small capitals and accented derivatives inherit these changes.
Character advances, kerning, coverage and menu sizing remain the same.

## Files

- `BressolesDisplay-Regular.ttf`: the game font; no OS installation needed.
- `BressolesDisplay-Regular.woff2`: the same outlines for a browser preview.
- `../tools/build_bressoles_font.py`: editable drawings, character assembly,
  metrics, mark anchors, and kerning. All glyphs are resolved into simple
  TrueType contours, with overlapping parts united before export.
- `../tools/preview_bressoles_font.py`: renders the specimen into
  `output/bressoles-font/Bressoles-Display-specimen.png`. When the saved
  `output/bressoles-font/v0100/BressolesDisplay-Regular.ttf` is available,
  it also renders `Bressoles-rounded-comparison.png` at matching text sizes.
- `../tools/preview_bressoles_menu.py`: renders the actual pygame menu in
  RU/ENG/DE/HU and verifies that its labels fit four viewport sizes.
- `../tools/check_bressoles_font.py`: checks the export, required alphabets,
  metrics, and the characters used by the game's localization catalogs.

## Character coverage

Latin uppercase and small capitals; all 33 Russian letters in both cases;
Ukrainian І/Ї/Є/Ґ; French accents and Æ/æ, Œ/œ, Ç/ç; all Hungarian accents,
including separate designs for Ö/ö versus Ő/ő and Ü/ü versus Ű/ű; German ß/ẞ;
lining figures, basic punctuation, typographic quotes, №, currencies and maths.
Additional decomposable Latin/Cyrillic letters are generated from the same
base outlines and accent drawings. OpenType mark positioning supports
decomposed accents in shaping engines that implement GPOS. Precomposed
characters are included for SDL_ttf/pygame. The font includes GPOS kerning
and a legacy `kern` table for the game renderer.

## Rebuilding

Build-time tools are independent of the game's pygame runtime requirements:

```powershell
python -m pip install fonttools==4.66.1 skia-pathops==0.9.2 brotli==1.2.0 Pillow
python tools/build_bressoles_font.py
python tools/check_bressoles_font.py
python tools/preview_bressoles_font.py
```

The sources remain editable so proportions, weight, individual letters, and
spacing can be refined after comparing the specimen to the reference. This
first export has no custom TrueType hinting program. It is checked at
24/32/50 px; the main menu uses 28–88 px according to the frame's size.
