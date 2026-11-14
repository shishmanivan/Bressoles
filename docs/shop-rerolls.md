# Shop rerolls

Rerolls are profile currency, independent of napoleondors and retained across
run resets and defeats. New and legacy profiles without a saved balance start
with `STARTING_SHOP_REROLLS` (0); existing balances are preserved. Every new
campaign level-six attempt (content ID 8) grants one reroll, capped at 10.
A saved per-attempt marker prevents duplicate grants on resume; defeat cleanup
preserves the balance and resets the marker for the next attempt.
An explicitly saved zero stays zero. Rewards, bonuses and future shop packs can
grant currency with `game_state.add_shop_rerolls(amount)` and save progress through
the normal profile flow. All grants and profile loads cap the balance at 10.
The button and reroll action are available only from level 6 (including campaign
level 6's content ID 8); levels 1–5 hide the button and cannot spend rerolls.

Market Refresh uses `Shop/Market Refresh.png`, costs 4 napoleondors before normal
shop discounts and grants 5 rerolls. Its base chance to enter the offer pool is
20%, using the same chance modifiers as other offers. It is eligible from level 6
only when the balance is at most 5. The same eligibility applies to Screening and
is rechecked when buying, so a stale offer cannot overflow the cap or charge money.
Future reward and bonus sources are not yet connected.

The shop button spends one reroll and regenerates the assortment using the
current level, discounts, bonus slots and remaining-round eligibility. Owned
purchases stay owned. Rerolls exclude cards, special offers and licenses from the
last three displayed assortments, including the current one. The fourth reroll
can reuse the initial assortment. Investment stays available. History is saved
per run, and includes ordinary shop visits and offers added during a visit.
When a category has too few fresh products, fill its remaining slots with still
eligible products from history, oldest last appearance first. Cards, offers and
licenses relax independently; purchased or otherwise ineligible products never
return. Only a genuinely empty replacement pool does not cost a reroll.
The first shop with unlocked rerolls shows a localized tutorial, remembered on
closing it. Rerolls do not advance the
Correction cooldown measured in shop visits. Input is blocked during the press
and assortment animations. The press uses Next's sound, 96% scale, 3px downward
offset and 110ms visible duration.

Artwork: `Shop/Other/Reroll.png`, actual PNG alpha, made with the built-in imagegen
tool from the user's supplied vintage emblem. Final prompt:

> Use case: background-extraction. Edit target: attached vintage reroll button.
> Remove only the parchment background OUTSIDE the ornamental rectangular button
> perimeter. Preserve the full button, its inner parchment fill, engraved double
> arrows, ornamental frame, warm sepia colors, proportions and fine details
> unchanged. Output a clean cutout on genuine alpha transparency, no added
> shadows, no text, no background. Keep entire button visible.
