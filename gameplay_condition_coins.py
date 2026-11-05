"""Transient condition medallions centered on the affected market."""

import math

import native_render as pygame

from asset_loaders import load_scaled_image
from gameplay_conditions import CONDITIONS


def show(page, condition, market):
    if not hasattr(page, "condition_coins"):
        page.condition_coins = {}
    page.condition_coins[market] = {"condition": condition, "start": None}


def draw(page, layout):
    coins = getattr(page, "condition_coins", None)
    if not coins:
        return
    now = pygame.time.get_ticks()
    for frame in layout["frame_rects"]:
        market = frame["market"]
        coin = coins.get(market)
        if coin is None:
            continue
        if coin["start"] is None:
            coin["start"] = now
        progress = (now - coin["start"]) / 1400
        if progress >= 1:
            del coins[market]
            continue
        rect = frame["rect"]
        size = min(110, rect.width, rect.height)
        width = round(size * math.sin(math.pi * progress))
        if width <= 0:
            continue
        face = load_scaled_image(CONDITIONS[coin["condition"]]["icon"], target_size=(size, size))
        if face is not None:
            pose = pygame.transform.smoothscale(face, (width, size))
            page.screen.blit(pose, pose.get_rect(center=rect.center))
