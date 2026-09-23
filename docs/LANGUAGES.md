# Empire language selection

The main-menu Languages action opens `LanguagesPage`. Test Mode is now inside Settings.
RU, ENG and DE have translations and can be selected. The choice is stored
in `Profiles/settings.json` independently of music volume.

Product language scope: Russian (Russian Empire), English (British Empire), Hungarian
(Austro-Hungarian Empire), French (French Empire), German (German Empire). Turkish
(Ottoman Empire) and Chinese (Qing Empire) are possible later additions. Do not add
languages outside this product scope. Future languages require actual translations
before being enabled; they must not silently use the English fallback.

`UI/Languages Map.png` is 1678 x 937, matching `UI/Menu3_1.png`. The underlying main
master `UI/Master Background.png` is 3440 x 1440. The map uses proportional fitting.
The current traced interaction polygons are in `languages_page.py`; they include
Ireland, Finland and Poland as shown in the supplied artwork. They are illustration
hit regions, not a historical boundary dataset.

Image source: user-supplied `ChatGPT Image 20 сент. 2026 г., 16_18_13.png`.
Created with the built-in imagegen tool. Final prompt:

> Edit target: attached antique map. Create landscape canvas exactly 1678 x 937 pixels for game language selection. Preserve entire original square map intact, undistorted, proportionally fit at center full height, including its border and every country's geometry and lettering. Extend canvas LEFT and RIGHT with matching antique parchment, fine cartographic grid lines and restrained engraved compass decoration. Do not stretch or crop original map. Side extensions are quiet parchment suitable for UI text, no additional countries or lettering. Keep original center map unchanged. Save resulting image locally.


## Layout revision

The framed map is shifted 216 native pixels to the right. The language buttons are
stacked on the left in this order: British Empire, Deutsches Reich, Российская империя. Empire names are endonyms independent of the
active UI translation: «British Empire», «Deutsches Reich» and «Российская империя».
Both date cartouches have been removed. The corresponding hit regions move with
the map; viewport scaling remains proportional.

Revision made with the built-in imagegen tool. Prompt:

> Precise edit of attached game map background. Output exactly 1678x937. Remove BOTH date cartouches entirely: upper-right black '1875' plaque and lower-right 'Europe in 1875 / 22 Countries / 12 Dependencies' box. Seamlessly reconstruct map drawing, coastlines, sea and parchment beneath them, no dates remain. Move the entire framed square map exactly 200 pixels RIGHT, without scaling, distortion or changing any existing country boundaries/labels. Its outer frame should now occupy x568..1477, y19..913 (previously x368..1277). Fill vacated left area with continuous matching parchment and grid. Remove the right-side compass because it would overlap the shifted map; retain the left compass in its existing location. Preserve antique colors, paper texture, country shapes and all other labels exactly. Left area will hold game UI controls rendered separately, do not add any buttons or text there. No red annotations.


The page now clips the unchanged map artwork to its original outer frame at
(584, 18, 912, 896). All surrounding space shows the existing master background;
side parchment and its compass are not rendered. Small language/status captions
are removed. A darker language button indicates the current selection.


The compass is restored below the language buttons as a separate transparent asset,
`UI/Languages Compass.png`, rendered over the master background. The map remains
unchanged. Extraction used the built-in imagegen tool with this prompt:

> Background extraction. Extract ONLY the small antique compass rose on the LEFT of this image (center approx x153 y470; complete artwork including N and fleur-de-lis at y320 and S at y566, W x50 and E x248). Return this SAME compass, with all its fine brown engraved lines and shaded star points preserved, as an isolated transparent PNG asset, tightly framed with a small transparent margin. Truly transparent background, no parchment, no paper rectangle, no map, no cartographic grid lines. Keep its exact vintage sepia appearance, cardinal letters N E S W and fleur-de-lis. Do not redesign. Compass should occupy most of image, retain original proportions.


## German localization

German is stored as `DE` in `Lang.csv` and in the language setting. UI text that
predates the keyed catalog is translated at display boundaries by `localization.py`,
using the shared `locales/ui.json` catalog (RU/ENG/DE). This does not alter card IDs, saved data, game rules or
player-entered profile names. The application sets the display locale explicitly;
reading a language catalog has no side effects. German descriptions are translated
before line wrapping. The end-turn image cache includes the locale.

German wording uses modern, natural game language and consistent informal `du`.
Glossary: Zug = turn, Runde = round, Durchlauf = run, Zielbetrag = monetary goal,
Aktienkurs = share price, Prozentpunkt = percentage point, Starthand = initial hand,
Silberkarte/Goldkarte/schwarze Karte = card categories, Napoleondor = game currency.
Names printed on card artwork (Gain, Drop, Shareholder, Rebate, etc.) are retained
as identifiers in descriptions, so players can match effects to their cards.
The map artwork and compass remain unchanged. The German region is an interaction
polygon following the supplied drawing. The historical machine-translation notice
is intentionally deferred at the user's request.

Checks cover all nonempty German catalog entries, placeholder parity, live card
and shop descriptions, dynamic strings, saved language/volume independence, empire
order, keyboard traversal, hit regions and viewport scaling.


German end-turn asset: `GameplayPage/End Turn DE.png`. Created with built-in imagegen.
Prompt: Change ONLY the English lettering 'End Turn' to the German word 'Zugende'.
Keep the same heavy antique serif typography, sepia brown ink, centered composition,
same decorative frame, colors and parchment, same button proportions. Preserve
transparent background around the button as real alpha transparency. No other text,
no redesign. Asset will be shown small, lettering must remain large and legible.


Validation of the German rollout: 176 keyed strings and 329 legacy UI strings.
49 focused localization/content/menu/asset-cache tests pass after the final image
integration. Earlier visual checks covered the main menu, level selector, shop and
gameplay. The full suite ran 718 tests with one error:
`test_bot_turn_finishes_before_market_resolution_starts` accesses
`end_button_press_until` before the deferred button-press drawing initializes it.
This animation timing issue is outside the localization changes.

## Symmetric localization audit

See `docs/LANGUAGE_AUDIT.md` for fixes, validation and outstanding image text.
The runtime catalog is now `locales/ui.json`, with explicit Source/RU/ENG/DE fields;
the obsolete German-only JSON has been removed. Generic templates are matched
after more specific ones. Add all three translations together when adding a row.
`tests/test_language_parity.py` guards source-string coverage and language parity.
Russian end-turn asset: `GameplayPage/End Turn RU.png`, generated using imagegen
from the English reference, preserving the frame and replacing the text with
«Конец хода»; transparent PNG. Embedded card labels still need a separate art pass.

## Hungarian / Osztrák–Magyar Monarchia (2026-09-23)

Added locale `HU` throughout language selection, saved settings, runtime translation,
content validation and the end-turn image cache. The picker order is British Empire,
Deutsches Reich, Российская империя, Osztrák–Magyar Monarchia; all titles remain
endonyms. Hovering either the Hungarian plaque or Austria-Hungary darkens the
territory traced from the displayed map. Clicking either selects Hungarian.
The compass sits slightly lower to clear the fourth plaque. Long plaque names use
fitted text. The original map artwork is unchanged.

The Hungarian translation covers 178 keyed entries and 331 legacy UI entries,
including card effects, shops, boss rules, campaign rewards, profile errors and
dynamic messages. Terminology: kör = turn, forduló = round, menet = run,
célösszeg = monetary goal, árfolyam = stock price, napóleonarany = Napoleondor.
The language uses natural informal singular address. Card and offer names remain
consistent with their printed artwork. Existing image-embedded text exceptions
listed in LANGUAGE_AUDIT.md still apply.

`GameplayPage/End Turn HU.png` was created with imagegen using the English button
as a reference. Prompt: replace End Turn with Kör vége, retaining the original
ornamental frame, parchment, brown/gold palette, proportions and alpha transparency.

Coverage: tests/test_hungarian_localization.py checks persistence, hover/click on
both plaque and territory at three viewport sizes, negative map hit cases, plaque
fit, compass clearance, Hungarian glyphs, dynamic language switching and distinct
cached button assets. The shared language parity audit now includes HU and checks
all four catalogs and long boss/reward layouts. Previews: output/hungarian/.

Hungarian validation result: 33 focused tests passed. Full suite: 728 tests,
727 passed; the pre-existing end_button_press_until initialization error remains
in test_bot_turn_finishes_before_market_resolution_starts. No new failures.
Menu, shop and highlighted empire picker were rendered and visually checked.
