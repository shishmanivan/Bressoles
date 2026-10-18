"""Extract a registered, feathered crowd sequence; offline-only dependencies.

Usage: python tools/build_menu_crowd.py path/to/generated_video.mp4
Requires opencv-python-headless, numpy, Pillow and imageio-ffmpeg.
Runtime only needs pygame.
"""
import json
import sys
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'UI/Animation/Crowd'
# Outline traced from the supplied 1680x1050 screenshot (no generated artwork).
OUTLINE = [(25,283),(70,277),(132,278),(205,280),(277,279),(349,282),
           (421,286),(472,286),(516,290),(529,299),(530,446),(538,462),
           (553,467),(560,459),(574,460),(579,470),(589,477),(592,490),
           (602,486),(605,475),(615,474),(632,482),(643,490),(652,500),
           (654,510),(642,523),(653,530),(670,540),(682,554),(689,578),
           (691,600),(684,622),(672,635),(651,646),(628,656),(603,660),
           (579,664),(556,666),(532,673),(505,679),(477,681),(448,684),
           (419,684),(393,685),(365,682),(340,682),(318,684),(291,685),
           (269,683),(248,686),(224,681),(200,681),(174,683),(149,679),
           (126,677),(107,678),(87,672),(65,669),(48,657),(32,646),
           (25,624),(24,597),(25,568),(24,542),(29,526),(26,508),
           (29,487),(27,465),(25,442),(24,415),(25,385),(24,350)]


def build(path):
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS)
    ok, first = capture.read()
    if not ok or fps <= 0:
        raise ValueError('Cannot read the input video')
    original = cv2.imread(str(ROOT / 'UI/Menu3_1.png'))
    sift = cv2.SIFT_create()
    ka, da = sift.detectAndCompute(first, None)
    kb, db = sift.detectAndCompute(original, None)
    matches = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [a for a, b in matches if a.distance < 0.68 * b.distance]
    source = np.float32([ka[m.queryIdx].pt for m in good])
    target = np.float32([kb[m.trainIdx].pt for m in good])
    transform, inliers = cv2.estimateAffinePartial2D(source, target, method=cv2.RANSAC,
                                                   ransacReprojThreshold=2)
    if transform is None or inliers.sum() < 100:
        raise ValueError('Video does not reliably match the menu artwork')
    # Small native-artwork patch enclosing the source vignette.
    rect = (22, 219, 672, 414)
    x, y, width, height = rect
    transform[:, 2] -= (x, y)
    mask = np.zeros((height, width), np.uint8)
    polygon = np.array([((px * 1678 / 1680) - x,
                         ((py - 56) * 937 / 938) - y) for px, py in OUTLINE], np.int32)
    cv2.fillPoly(mask, [polygon], 255)
    # Fade inward only; outside this silhouette the original menu stays intact.
    padded = np.pad(mask, 1)
    distance = cv2.distanceTransform(padded, cv2.DIST_L2, 5)[1:-1, 1:-1]
    alpha = np.uint8(np.clip(distance / 12, 0, 1) * 255)
    reference = cv2.warpAffine(first, transform, (width, height))
    # The corrected video has a black matte outside its cutout. Exclude it
    # instead of letting black pixels darken the original menu at the edges.
    valid = np.uint8(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY) > 25) * 255
    valid_distance = cv2.distanceTransform(np.pad(valid, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    alpha = np.uint8(alpha.astype(np.float32) * np.clip(valid_distance / 6, 0, 1))
    base = original[y:y+height, x:x+width]
    # Fixed broad correction removes video compression/color cast at the seam.
    correction = cv2.GaussianBlur(base.astype(np.float32) - reference.astype(np.float32),
                                  (0, 0), 8)
    # Match edges only: an interior correction would reintroduce ghosts of the
    # removed triangle and malformed hats from the original illustration.
    correction *= np.clip(1 - distance / 30, 0, 1)[:, :, None]
    DESTINATION.mkdir(parents=True, exist_ok=True)
    alpha_image = Image.new('RGBA', (width, height), (255, 255, 255, 255))
    alpha_image.putalpha(Image.fromarray(alpha))
    alpha_image.save(DESTINATION / 'mask.png')
    frame, count = first, 0
    while True:
        warped = cv2.warpAffine(frame, transform, (width, height))
        rgb = cv2.cvtColor(np.uint8(np.clip(warped.astype(np.float32) + correction, 0, 255)),
                           cv2.COLOR_BGR2RGB)
        # JPEG decodes much faster in SDL than WebP; a shared lossless mask
        # retains the exact same alpha for every frame without duplication.
        Image.fromarray(rgb).save(DESTINATION / f'{count:04d}.jpg', quality=96, subsampling=0)
        count += 1
        ok, frame = capture.read()
        if not ok:
            break
    capture.release()
    metadata = dict(rect=rect, fps=fps, frames=count, source_size=[1678, 937],
                    start_seconds=1.0, end_seconds=12.0)
    (DESTINATION / 'sequence.json').write_text(json.dumps(metadata, indent=2) + '\n')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(path), '-vn',
                    '-af', 'afade=t=in:d=0.25,afade=t=out:st=11.65:d=0.25',
                    '-ac', '2', '-ar', '44100', '-c:a', 'libvorbis', '-q:a', '5',
                    str(ROOT / 'Sounds/Menu Crowd.ogg')], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print(f'{count} frames at {fps} fps, {inliers.sum()} registration matches; {DESTINATION}')


if __name__ == '__main__':
    build(Path(sys.argv[1]))
