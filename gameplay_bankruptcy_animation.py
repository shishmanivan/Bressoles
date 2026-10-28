"""Short-lived bankruptcy stamp and share particles in design coordinates."""
import math

import native_render as pygame
import gameplay_bankruptcy_audio as crowd


PREPARE_MS = 500
DURATION_MS = 2400
CRASH_STAGGER_MS = 450
VELOCITIES = ((-190, -230, -160), (-105, -310, 120),
              (20, -260, -95), (125, -330, 180), (215, -190, 230))


def start(page, market):
    start_sequence(page, (market,))


def start_sequence(page, markets):
    """One crowd clip; staggered impacts with overlapping falling shares."""
    markets = tuple(markets)
    if not markets:
        return
    crowd.start(page, DURATION_MS + CRASH_STAGGER_MS * (len(markets) - 1))
    animations = getattr(page, 'bankruptcy_animations', None)
    if animations is None:
        animations = page.bankruptcy_animations = {}
    now = pygame.time.get_ticks()
    for index, market in enumerate(markets):
        delay = index * CRASH_STAGGER_MS
        animations[market] = {'start_time': now, 'delay': delay,
                              'elapsed': -delay, 'impacted': False}


def update(page):
    animations = getattr(page, 'bankruptcy_animations', {})
    now = pygame.time.get_ticks()
    if animations:
        crowd.update(page, now - min(a['start_time'] for a in animations.values()))
    for market, animation in list(animations.items()):
        elapsed = now - animation['start_time'] - animation.get('delay', 0)
        animation['elapsed'] = elapsed
        if elapsed >= PREPARE_MS and not animation['impacted']:
            animation['impacted'] = True
            sound = getattr(page, 'stamp_sound', None)
            if sound:
                sound.play()
        if elapsed >= DURATION_MS:
            del animations[market]


def shake(page, market):
    animation = getattr(page, 'bankruptcy_animations', {}).get(market)
    if not animation:
        return 0, 0
    elapsed = animation['elapsed'] - PREPARE_MS
    if not 0 <= elapsed < 420:
        return 0, 0
    amplitude = 12 * (1 - elapsed / 420) ** 2
    return round(math.cos(elapsed * .09) * amplitude), round(math.sin(elapsed * .12) * amplitude * .65)


def draw(page, layout):
    for frame in layout['frame_rects']:
        animation = getattr(page, 'bankruptcy_animations', {}).get(frame['market'])
        if not animation:
            continue
        elapsed = animation['elapsed']
        if elapsed < 0:
            continue
        rect = frame['rect']
        dx, dy = shake(page, frame['market'])
        base = rect.move(-dx, -dy)
        bundle = getattr(page, 'bundle_image', None)
        if bundle:
            ghost = getattr(page, '_bankruptcy_share_ghost', None)
            if ghost is None:
                ghost = bundle.copy()
                ghost.fill((35, 35, 35, 0), special_flags=pygame.BLEND_RGB_ADD)
                ghost.set_alpha(105)
                page._bankruptcy_share_ghost = ghost
            origin = (base.x + 25 + bundle.get_width() / 2,
                      base.y + 183 + bundle.get_height() / 2)
            t = max(0, elapsed - PREPARE_MS) / 1000
            fade = min(1, max(0, (DURATION_MS - elapsed) / 650))
            for vx, vy, spin in VELOCITIES:
                particle = pygame.transform.rotate(ghost, spin * t)
                particle.set_alpha(round(105 * fade * min(1, elapsed / 180)))
                center = (round(origin[0] + vx * t),
                          round(origin[1] + vy * t + 420 * t * t))
                page.screen.blit(particle, particle.get_rect(center=center))
        stamp = getattr(page, 'bankrupt_stamp_image', None)
        if stamp and elapsed >= PREPARE_MS - 160:
            approach = min(1, max(0, (elapsed - PREPARE_MS + 160) / 160))
            scale = 1 + .65 * (1 - approach)
            image = pygame.transform.smoothscale(stamp, (round(stamp.get_width() * scale),
                                                        round(stamp.get_height() * scale)))
            image.set_alpha(round(255 * approach * min(1, (DURATION_MS - elapsed) / 450)))
            page.screen.blit(image, image.get_rect(center=rect.center))
