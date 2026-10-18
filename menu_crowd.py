"""Registered crowd cutout, played backwards/forwards without endpoint jumps."""
from collections import OrderedDict
import json
from pathlib import Path

import pygame

SEQUENCE_PATH = Path(__file__).resolve().parent / 'UI/Animation/Crowd'
CROWD_CACHE_FRAMES = 12
CROWD_PLAYBACK_SPEED = 2 / 3


def ping_pong_frame(elapsed, fps, count, start_seconds=1.0, end_seconds=12.0):
    if count <= 1:
        return 0
    last = min(count - 1, max(0, round(end_seconds * fps)))
    start = min(last, max(0, round(start_seconds * fps)))
    span = last - start
    if span == 0:
        return start
    phase = int(max(0, elapsed) * fps + 1e-7) % (2 * span)
    return start + (phase if phase <= span else 2 * span - phase)


class MenuCrowdAnimation:
    def __init__(self, menu_image):
        self.sequence = None
        self.started_at = None
        self.frames = OrderedDict()
        self.scaled_key = None
        self.scaled = None
        self.mask = None
        manifest = SEQUENCE_PATH / 'sequence.json'
        if menu_image is not None and menu_image.get_size() == (1678, 937) and manifest.exists():
            self.sequence = json.loads(manifest.read_text())
            self.mask = pygame.image.load(str(SEQUENCE_PATH / 'mask.png')).convert_alpha()

    def draw(self, screen, artwork, ticks):
        if self.sequence is None:
            return
        if self.started_at is None:
            self.started_at = ticks
        sequence = self.sequence
        index = ping_pong_frame((ticks - self.started_at) / 1000 * CROWD_PLAYBACK_SPEED, sequence['fps'],
                               sequence['frames'], sequence['start_seconds'], sequence['end_seconds'])
        x, y, width, height = sequence['rect']
        sx, sy = artwork.width / 1678, artwork.height / 937
        target = pygame.Rect(artwork.x + round(x * sx), artwork.y + round(y * sy),
                             max(1, round(width * sx)), max(1, round(height * sy)))
        key = index, target.size
        if key != self.scaled_key:
            if index not in self.frames:
                frame = pygame.image.load(str(SEQUENCE_PATH / f'{index:04d}.jpg')).convert_alpha()
                frame.blit(self.mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                self.frames[index] = frame
                if len(self.frames) > CROWD_CACHE_FRAMES:
                    self.frames.popitem(last=False)
            self.frames.move_to_end(index)
            self.scaled = pygame.transform.smoothscale(self.frames[index], target.size)
            self.scaled_key = key
        screen.blit(self.scaled, target)
