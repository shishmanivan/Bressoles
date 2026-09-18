# Gameplay trade arrows

The twelve RGBA sprites use `../New Arrow.png` supplied by the user. `single`
means buy/sell one; `all` adds the horizontal stop bar. Frame 0 is idle and frames
1 and 2 nod forward. The game plays 0, 1, 2, 1, 0 at 120 ms per frame in its
existing 60 x 60 button hitboxes.

The shaft is shared unchanged across all three poses. Down arrows are exact
180-degree rotations of the corresponding up arrows. The stop bar stays still.
Only the upper arrowhead is foreshortened, so the original engraved detail is
retained without redrawing or shifting the base.

Rebuild with `python tools/build_trade_arrows.py` from the repository root
(requires Pillow for artwork preparation, not at game runtime). The source bar
is `Stop Bar.png`; all game sprites are 512 x 512 with real alpha transparency.

## Image generation provenance

The built-in image_gen tool drew the stop-bar variant using the user arrow as
its edit target. Its output had a baked checkerboard background. With the user's
explicit approval, the bar was isolated, given an alpha channel, and composited
with the original arrow. Generated full animation candidates were discarded in
favor of deterministic head foreshortening to keep the base pixel-identical.

Prompt used for the stop-bar variant:

Edit the attached ornamental arrow sprite. Image 1 is the edit target, the exact new arrow supplied by the user. Make ONE single up-arrow game button sprite, not a sheet. Preserve the exact arrow design, proportions, entire silhouette, floral engravings, antique silver/bronze metal colors and lighting. Keep the same square canvas and location of the arrow. The ONLY change is to ADD a thin horizontal metal stop bar directly above its upper pointed tip. The existing arrow occupies roughly x145..1105, y51..1165 on a 1254-square source canvas. Place the bar centered at x627, from roughly x390 to x864, y12..33, leaving a small transparent gap above the arrow tip. Bar should have the same beveled antique silver edge and dark inset, look like part of the same UI icon family, crisp and simple, no new flourishes. Do not move or resize the arrow. True transparent alpha background everywhere outside arrow and bar; no black/white/checkerboard background. Output only the individual ready-to-use PNG sprite.
