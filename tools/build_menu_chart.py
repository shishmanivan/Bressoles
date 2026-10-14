"""Prepare a small clean graph patch; Pillow is only needed to rebuild this asset.

The runtime reveals the original Menu3 pixels, so the drawn line never loses
its engraved texture. Only the traced curve and its round markers are removed.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BOUNDS = (1194, 59, 1379, 180)
POINTS = ((1202, 171), (1222, 150), (1240, 150), (1254, 171),
          (1280, 135), (1304, 102), (1320, 120), (1332, 110),
          (1341, 95), (1349, 111), (1355, 97), (1370, 67))


def build():
    original = Image.open(ROOT / 'UI/Menu3_1.png').convert('RGB').crop(BOUNDS)
    points = [(x - BOUNDS[0], y - BOUNDS[1]) for x, y in POINTS]
    mask = Image.new('L', original.size)
    draw = ImageDraw.Draw(mask)
    draw.line(points, fill=255, width=9)
    for x, y in points:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=255)
    w, h = original.size
    pixels = original.load()
    missing = {(x, y) for y in range(h) for x in range(w) if mask.getpixel((x, y))}
    # Estimate paper separately from ink, then continue the grid through the
    # removed curve. Diffusing dark boundary pixels would leave a ghost curve.
    values = {(x, y): tuple(map(float, pixels[x, y])) for y in range(h) for x in range(w)
              if (x, y) not in missing and sum(pixels[x, y]) / 3 > 185}
    pending = {(x, y) for y in range(h) for x in range(w)} - values.keys()
    while pending:
        fill = {}
        for x, y in pending:
            neighbors = [values[p] for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)) if p in values]
            if neighbors:
                fill[x, y] = tuple(sum(c[k] for c in neighbors) / len(neighbors) for k in range(3))
        values.update(fill)
        pending.difference_update(fill)

    for _ in range(180):
        updates = {}
        for x, y in missing:
            neighbors = [values[p] for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)) if p in values]
            updates[x,y] = tuple(sum(c[k] for c in neighbors)/len(neighbors) for k in range(3))
        values.update(updates)

    def fit_grid(vertical, start, end):
        samples = []
        for t in range(82, 177) if vertical else range(1203, 1376):
            prediction = start + (end - start) * ((t - 80) / 100 if vertical else (t - 1200) / 175)
            candidates = []
            for c in range(round(prediction)-3, round(prediction)+4):
                gx, gy = (c, t) if vertical else (t, c)
                x, y = gx - BOUNDS[0], gy - BOUNDS[1]
                if 1 <= x < w-1 and 1 <= y < h-1 and (x, y) not in missing:
                    candidates.append((sum(pixels[x, y]), c))
            if candidates:
                darkness, c = min(candidates)
                if darkness / 3 < 180:
                    samples.append((t, c))
        # Least squares follows the original tilted grid, without straightening it.
        mt = sum(t for t, c in samples) / len(samples)
        mc = sum(c for t, c in samples) / len(samples)
        slope = sum((t-mt)*(c-mc) for t,c in samples) / sum((t-mt)**2 for t,c in samples)
        return slope, mc - slope * mt

    verticals = [fit_grid(True, a, b) for a,b in
                 ((1204,1206),(1223,1223),(1243,1241),(1263,1260),(1282,1278),
                  (1302,1297),(1321,1316),(1341,1335),(1359,1354),(1379,1374))]
    horizontals = [fit_grid(False, a, b) for a,b in ((80,74),(98,91),(116,110),(134,129),(151,148),(170,167))]
    restored = original.copy()
    import math
    for x, y in missing:
        gx, gy = x + BOUNDS[0], y + BOUNDS[1]
        distances = [abs(gx - (a*gy+b)) for a,b in verticals] if gy >= 80 else []
        distances += [abs(gy - (a*gx+b)) for a,b in horizontals]
        grid = max(0, 1 - min(distances, default=10) / 1.45)
        strength = grid * (0.28 + 0.025 * math.sin(gx * 0.7 + gy * 0.3))
        paper = values[x, y]
        restored.putpixel((x, y), tuple(round(c*(1-strength)) for c in paper))
    # Feather inside the traced mask, leaving every unrelated pixel unchanged.
    feather = mask.filter(ImageFilter.GaussianBlur(0.55))
    clean = Image.composite(restored, original, feather)
    destination = ROOT / 'UI/Animation/Chart Clean.png'
    clean.save(destination)
    print(destination)


if __name__ == '__main__':
    build()
