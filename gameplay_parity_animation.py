"""Copies of the settled prices pop toward the viewer and fade away."""
import native_render as pygame

DURATION_MS = 550


def start(page):
    page.parity_animation = {'start_time': pygame.time.get_ticks(), 'elapsed': 0}


def update(page):
    animation = getattr(page, 'parity_animation', None)
    if animation:
        animation['elapsed'] = pygame.time.get_ticks() - animation['start_time']
        if animation['elapsed'] >= DURATION_MS:
            page.parity_animation = None


def draw(page, labels):
    animation = getattr(page, 'parity_animation', None)
    if not animation:
        return
    progress = max(0, min(1, animation['elapsed'] / DURATION_MS))
    expansion = 1 - (1 - progress) ** 2
    scale = 1 + 3.5 * expansion
    alpha = round(255 * (1 - progress) ** 1.4)
    for original, rect in labels:
        enlarged = pygame.transform.smoothscale(original, (
            max(1, round(original.get_width() * scale)),
            max(1, round(original.get_height() * scale)),
        ))
        enlarged.set_alpha(alpha)
        center = (rect.centerx, rect.centery - round(42 * expansion))
        page.screen.blit(enlarged, enlarged.get_rect(center=center))
