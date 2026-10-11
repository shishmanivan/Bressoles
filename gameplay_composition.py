"""Retain the native gameplay foreground between frames.

Keys are the actual ordered paint operations (resource version, destination,
clip and visual arguments), never a hash of game state. This deliberately has
no game logic. A changed operation restores its old and new bounds and replays
intersecting artwork in the original order, including translucent overlaps.
Modals flush the table first and use the normal immediate composition path.
"""
import pygame


class GameplayComposition:
    def __init__(self):
        self.previous = []
        self.pending = []
        self.pixels = None
        self.active = False
        self.dirty = []
        self.full_redraws = 0
        self.partial_redraws = 0
        self.generation = 0

    def begin(self, size):
        if self.pixels is None or self.pixels.get_size() != size:
            self.pixels = pygame.Surface(size, pygame.SRCALPHA)
            self.previous = []
        self.pending = []
        self.active = True

    def add(self, key, bounds, paint):
        self.pending.append((key, bounds.copy(), paint))

    def flush(self, target):
        if not self.active:
            return
        self.active = False
        pending = self.pending
        dirty = []
        for index in range(max(len(pending), len(self.previous))):
            old = self.previous[index] if index < len(self.previous) else None
            new = pending[index] if index < len(pending) else None
            if old is not None and new is not None and old[0] == new[0]:
                continue
            for entry in (old, new):
                if entry is not None:
                    rect = entry[1].clip(target.get_rect())
                    if rect.width and rect.height:
                        dirty.append(rect)
        # Coalesce intersections. Disjoint moving cards do not force a full table.
        merged = []
        for rect in dirty:
            index = 0
            while index < len(merged):
                if rect.colliderect(merged[index]):
                    rect = rect.union(merged.pop(index))
                    index = 0
                else:
                    index += 1
            merged.append(rect)
        if not self.previous or sum(r.w*r.h for r in merged) > target.get_width()*target.get_height()*.45:
            merged = [target.get_rect()]
            self.full_redraws += 1
        elif merged:
            self.partial_redraws += 1
        if merged:
            self.generation += 1
        for rect in merged:
            self.pixels.set_clip(rect)
            self.pixels.fill((0, 0, 0, 0), rect)
            for _, bounds, paint in pending:
                if bounds.colliderect(rect):
                    paint(self.pixels, rect)
        self.pixels.set_clip(None)
        # Copy exact RGBA pixels, not alpha-blend onto last frame's foreground.
        # PixelArray assignment preserves transparent edges bit for bit.
        target.set_clip(None)
        with pygame.PixelArray(target) as dest, pygame.PixelArray(self.pixels) as source:
            dest[:] = source
        self.previous = pending
        self.pending = []
        self.dirty = merged

    @property
    def bytes(self):
        return 0 if self.pixels is None else self.pixels.get_pitch()*self.pixels.get_height()
