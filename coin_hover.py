"""Small hover copies of visible coin faces beside the franc sack."""
import math

import pygame


COIN_HOVER_SCALE = 1.18
COIN_ANIMATION_SECONDS = 0.15
# Native Menu3_1 coordinates: individual faces and rims, never whole stacks.
COIN_FACE_BOUNDS = (
    (765, 736, 48, 16),
    (765, 756, 51, 21),
    (845, 711, 52, 20),
    (877, 681, 48, 17),
    (927, 657, 50, 20),
    (966, 710, 40, 16),
    (866, 753, 67, 22),
    (886, 773, 39, 11),
)
COIN_SIDE_BOUNDS = (
    # Tall stack to the right of the sack, from top to bottom.
    (927, 675, 49, 7), (926, 682, 49, 7), (926, 689, 49, 7),
    (927, 696, 47, 7), (926, 703, 49, 7), (927, 710, 47, 7),
    (927, 717, 45, 7), (927, 724, 43, 7), (927, 731, 43, 7),
    (928, 738, 42, 7),
    # Middle and front stacks.
    (879, 698, 45, 6), (879, 704, 45, 7), (880, 711, 43, 7),
    (898, 719, 26, 6), (898, 725, 26, 7), (898, 733, 25, 7),
    (847, 730, 48, 7), (847, 737, 48, 7), (848, 744, 46, 8),
    # Short stack on the far right and the two stacks on the left.
    (970, 726, 35, 6), (970, 732, 35, 6), (972, 738, 31, 6),
    (767, 750, 45, 6), (768, 775, 45, 6),
)
COIN_LOWER_FACE_BOUNDS = (
    (759, 781, 32, 10), (795, 779, 25, 10), (810, 783, 20, 8),
)
COIN_BOUNDS = COIN_FACE_BOUNDS + COIN_SIDE_BOUNDS + COIN_LOWER_FACE_BOUNDS


class CoinHover:
    def __init__(self, image):
        self.coins = []
        if image is not None and image.get_size() == (1678, 937):
            for index, bounds in enumerate(COIN_BOUNDS):
                rect = pygame.Rect(bounds)
                coin = image.subsurface(rect).copy()
                width, height = coin.get_size()
                # A feathered silhouette excludes the rectangular background.
                for y in range(height):
                    for x in range(width):
                        nx = (x + 0.5 - width / 2) / (width / 2)
                        if len(COIN_FACE_BOUNDS) <= index < len(COIN_FACE_BOUNDS) + len(COIN_SIDE_BOUNDS):
                            # A narrow curved rim instead of an oval face: keep
                            # adjacent coins out of this coin's copied strip.
                            center_y = height * (0.58 - 0.22 * nx * nx)
                            edge_y = height * 0.30 - abs(y + 0.5 - center_y)
                            edge_x = (1 - abs(nx)) * width / 2
                            coverage = max(0, min(1, edge_x, edge_y))
                        else:
                            radius = math.hypot(nx, (y + 0.5 - height / 2) / (height / 2))
                            coverage = max(0, min(1, (1 - radius) * height / 1.2))
                        color = coin.get_at((x, y))
                        coin.set_at((x, y), (*color[:3], round(color.a * coverage)))
                self.coins.append((rect, coin))
        self.amounts = [0.0] * len(self.coins)
        self.hovered = None
        self.last_ticks = None
        self.cached_size = None
        self.scaled = []

    def hit_test(self, position, artwork):
        x = (position[0] - artwork.left) * 1678 / artwork.width
        y = (position[1] - artwork.top) * 937 / artwork.height
        nearest, distance = None, float('inf')
        for index, (rect, _) in enumerate(self.coins):
            radius = (((x - (rect.x + rect.width / 2)) / (rect.width / 2)) ** 2
                      + ((y - (rect.y + rect.height / 2)) / (rect.height / 2)) ** 2)
            if radius <= 1 and radius < distance:
                nearest, distance = index, radius
        return nearest

    def draw(self, screen, artwork, position, ticks):
        self.hovered = self.hit_test(position, artwork)
        dt = min(0.05, max(0, (ticks - self.last_ticks) / 1000)) if self.last_ticks is not None else 1 / 60
        self.last_ticks = ticks
        sx, sy = artwork.width / 1678, artwork.height / 937
        if self.cached_size != artwork.size:
            self.scaled = []
            for rect, coin in self.coins:
                target = pygame.Rect(round(rect.x * sx), round(rect.y * sy),
                                     max(1, round(rect.width * sx)), max(1, round(rect.height * sy)))
                self.scaled.append((target, pygame.transform.smoothscale(coin, target.size)))
            self.cached_size = artwork.size
        active = []
        for index, (rect, coin) in enumerate(self.scaled):
            direction = 1 if index == self.hovered else -1
            amount = max(0, min(1, self.amounts[index] + direction * dt / COIN_ANIMATION_SECONDS))
            self.amounts[index] = amount
            if amount == 0:
                continue
            ease = amount * amount * (3 - 2 * amount)
            scale = 1 + (COIN_HOVER_SCALE - 1) * ease
            grown = pygame.transform.smoothscale(coin, (max(1, round(rect.width * scale)),
                                                        max(1, round(rect.height * scale))))
            # The enlarged opaque face covers its original; unlike lettering,
            # there is no need to erase ink or reconstruct paper beneath it.
            active.append((index == self.hovered, grown,
                           grown.get_rect(center=(artwork.left + rect.centerx,
                                                  artwork.top + rect.centery))))
        # The coin under the pointer stays above neighboring coins shrinking back.
        for _, grown, rect in sorted(active, key=lambda item: item[0]):
            screen.blit(grown, rect)
