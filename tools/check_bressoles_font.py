"""Validate the font export and actual project localization coverage."""
from pathlib import Path
import csv
import json
import string
import unicodedata

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]


def check():
    font = TTFont(ROOT / "Fonts/BressolesDisplay-Regular.ttf", checkChecksums=2)
    cmap = font.getBestCmap()
    required = set(string.printable.strip() + "Ёё" + "ŒœÆæÇçẞß" +
                   "ÀÂÉÈÊËÎÏÔÙÛÜŸàâéèêëîïôùûüÿ" +
                   "ÁÉÍÓÖŐÚÜŰáéíóöőúüű" + "ІіЇїЄєҐґ" +
                   "№₽€£«»‘’“”„–—…·")
    required.update(chr(cp) for cp in range(0x410, 0x450))
    required.difference_update("\r\n\t\v\f")
    missing = sorted(c for c in required if ord(c) not in cmap)
    assert not missing, f"Required characters missing: {missing}"

    catalog_chars = set()
    with (ROOT / "Lang.csv").open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, delimiter=";"):
            for key, text in row.items():
                if key != "Key":
                    catalog_chars.update(text)
    for row in json.loads((ROOT / "locales/ui.json").read_text(encoding="utf-8")):
        for text in row.values():
            catalog_chars.update(text)
    missing = sorted(c for c in catalog_chars if not c.isspace() and ord(c) not in cmap)
    assert not missing, f"Localization characters missing: {missing}"

    for cp, name in cmap.items():
        char = chr(cp)
        glyph = font["glyf"][name]
        advance, bearing = font["hmtx"][name]
        assert not glyph.isComposite(), f"Unresolved components in {char!r}"
        if char.isspace() or cp in (0x200B,):
            assert glyph.numberOfContours == 0
            continue
        assert glyph.numberOfContours > 0, f"Empty outline for {char!r}"
        assert advance > 0 or unicodedata.combining(char), f"Zero advance for {char!r}"
        assert bearing == glyph.xMin, f"Inconsistent sidebearing for {char!r}"
        assert glyph.yMax <= font["hhea"].ascent, f"Clipped top for {char!r}"
        assert glyph.yMin >= font["hhea"].descent, f"Clipped bottom for {char!r}"

    for a, b in [("O", "Ö"), ("Ö", "Ő"), ("Ü", "Ű"), ("o", "ö"),
                 ("ö", "ő"), ("ü", "ű"), ("Е", "Ё"), ("И", "Й")]:
        assert font["glyf"][cmap[ord(a)]].coordinates != font["glyf"][cmap[ord(b)]].coordinates
    assert font["kern"].kernTables[0].kernTable
    assert "GPOS" in font and "GDEF" in font
    assert font["name"].getDebugName(1) == "Bressoles Display"

    web = TTFont(ROOT / "Fonts/BressolesDisplay-Regular.woff2")
    assert web.getBestCmap() == cmap, "Web and game fonts have different coverage"
    for name in font.getGlyphOrder():
        assert web["glyf"][name].compile(web["glyf"]) == font["glyf"][name].compile(font["glyf"])
    print(f"PASS: {len(cmap)} characters; Russian/French/Hungarian alphabets; "
          f"{len(catalog_chars)} catalog characters; safe metrics; matching TTF/WOFF2 outlines.")


if __name__ == "__main__":
    check()
