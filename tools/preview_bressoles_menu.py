"""Render the actual pygame menu and verify localized labels fit its frame."""
from pathlib import Path
import csv
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

ROOT = Path(__file__).resolve().parents[1]
# Game asset paths are relative to the project's root.
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
from start_page import StartPage


def render():
    out = ROOT / "output/bressoles-font"
    out.mkdir(parents=True, exist_ok=True)
    with (ROOT / "Lang.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source, delimiter=";"))
    pygame.init()
    pygame.display.set_mode((1, 1))
    checks = 0
    try:
        for language in ("RU", "ENG", "DE", "HU"):
            lang = {row["Key"]: row[language] for row in rows}
            for size in ((800, 600), (1280, 720), (1920, 1080), (3440, 1440)):
                screen = pygame.Surface(size)
                page = StartPage(screen, None, None, lang_dict=lang, profile_name="Бресоль")
                page.draw()
                layout = page._get_layout()
                font = page._get_font(layout.font_size)
                for label in page.menu_items:
                    metrics = font.metrics(label)
                    assert all(m is not None for m in metrics), f"Missing glyph: {label}"
                    rendered = page._render_text_cached(font, label, (77, 63, 50))
                    assert rendered.get_width() * 1.02 <= layout.menu_rect.width * .92, (
                        language, size, label, rendered.get_size(), layout.menu_rect)
                    assert rendered.get_height() * 1.02 < layout.menu_rect.height * .19
                    checks += 1
                if size == (1920, 1080):
                    pygame.image.save(screen, str(out / f"Bressoles-menu-{language}.png"))
                if size == (1280, 720) and language == "RU":
                    pygame.image.save(screen, str(out / "Bressoles-menu-RU-1280.png"))
        # Check that every supplied Cyrillic/French/Hungarian letter rasterizes.
        alphabet = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯŒÆÇÀÂÉÈÊËÎÏÔÙÛÜŸÁÉÍÓÖŐÚÜŰ"
        for size in (24, 32, 50):
            font = page._get_font(size)
            for char in alphabet + alphabet.lower():
                raster = font.render(char, True, (0, 0, 0))
                assert raster.get_bounding_rect().width > 0, (char, size)
        print(f"PASS: {checks} localized menu labels fit across 4 resolutions; "
              "Cyrillic/French/Hungarian render at 24/32/50 px. Menu previews saved.")
    finally:
        pygame.quit()


if __name__ == "__main__":
    render()
