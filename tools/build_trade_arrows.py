"""Build the game's trade sprites from New Arrow.png and the generated stop bar.

Requires Pillow only when rebuilding artwork; the game still uses just Pygame.
Run from any directory: python tools/build_trade_arrows.py
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "GameplayPage" / "Arrows"
SPRITE_SIZE = (512, 512)
HINGE_Y = 690  # Everything below this point stays pixel-identical in each frame.
HEAD_OFFSETS = (0, 36, 72)


def clean_source(image):
    """Remove isolated faint export specks while retaining antialiased edges."""
    alpha = image.getchannel("A")
    support = alpha.point(lambda value: 255 if value > 16 else 0)
    ImageDraw.floodfill(support, (627, 900), 128)
    support = support.point(lambda value: 255 if value == 128 else 0)
    support = support.filter(ImageFilter.MaxFilter(3))
    image.putalpha(ImageChops.multiply(alpha, support))
    return image


def build_sprites():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original = clean_source(
        Image.open(ROOT / "GameplayPage" / "New Arrow.png").convert("RGBA")
    )
    bar = Image.open(OUTPUT / "Stop Bar.png").convert("RGBA")
    bar = bar.resize((520, 38), Image.Resampling.LANCZOS)
    width, height = original.size
    head = original.crop((0, 0, width, HINGE_Y))
    shaft = original.crop((0, HINGE_Y, width, height))

    for index, offset in enumerate(HEAD_OFFSETS):
        frame = Image.new("RGBA", original.size)
        if offset:
            # Foreshorten the head toward the stationary shoulder/shaft join.
            tilted = head.resize((width, HINGE_Y - offset), Image.Resampling.LANCZOS)
            frame.paste(tilted, (0, offset))
        else:
            frame.paste(head, (0, 0))
        frame.paste(shaft, (0, HINGE_Y))

        for kind in ("single", "all"):
            sprite = frame.copy()
            if kind == "all":
                sprite.alpha_composite(bar, ((width - bar.width) // 2, 2))
            sprite = sprite.resize(SPRITE_SIZE, Image.Resampling.LANCZOS)
            sprite.save(OUTPUT / f"{kind}-up-{index}.png", optimize=True)
            sprite.transpose(Image.Transpose.ROTATE_180).save(
                OUTPUT / f"{kind}-down-{index}.png", optimize=True,
            )


if __name__ == "__main__":
    build_sprites()
