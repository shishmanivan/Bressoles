"""Decorative clockwork: no controls or connection to gameplay state."""
import math
import native_render as pygame
from localization import translate
from shared_utils import wrap_text
from gameplay_assets import build_hand_frame

CAPTION = (
    "Окно с шестерёнками — это движок игры. Ничего в нём не меняйте, "
    "если не разбираетесь в этом."
)
BUTTON = pygame.Rect(12, 10, 48, 34)
PANEL = pygame.Rect(170, 85, 1340, 880)
CLOSE = pygame.Rect(735, 870, 210, 58)


def gear(surface, center, radius, teeth, angle, color):
    cx, cy = center
    points = []
    for i in range(teeth * 4):
        a = angle + i * math.tau / (teeth * 4)
        r = radius * (1 if i % 4 in (1, 2) else .87)
        points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    pygame.draw.polygon(surface, (44, 33, 23), points)
    pygame.draw.polygon(surface, color, points, 3)
    pygame.draw.circle(surface, color, center, round(radius * .73), max(2, round(radius * .13)))
    for i in range(5):
        a = angle + i * math.tau / 5
        tip = (cx + math.cos(a) * radius * .66, cy + math.sin(a) * radius * .66)
        pygame.draw.line(surface, color, center, tip, max(3, round(radius * .12)))
    pygame.draw.circle(surface, (183, 148, 85), center, max(4, round(radius * .19)))
    pygame.draw.circle(surface, (48, 38, 27), center, max(2, round(radius * .07)))


def draw_button(screen):
    pygame.draw.rect(screen, (209, 190, 148), BUTTON, border_radius=4)
    pygame.draw.rect(screen, (89, 67, 38), BUTTON, 2, border_radius=4)
    gear(screen, (29, 24), 11, 10, 0, (139, 103, 52))
    gear(screen, (46, 32), 8, 8, .2, (139, 103, 52))


class ClockworkWindow:
    def __init__(self, frame, font_path):
        self.frame = build_hand_frame(frame, PANEL.size) if frame is not None else None
        self.font = pygame.font.Font(font_path, 29)
        self.lines = wrap_text(translate(CAPTION), self.font, PANEL.width - 140)
        self.close_label = self.font.render(translate("Закрыть"), True, (67, 49, 31))

    def accepts_close(self, event):
        return ((event.type == pygame.KEYDOWN and event.key in
                 (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE))
                or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and CLOSE.collidepoint(event.pos)))

    def draw(self, screen, ticks=None):
        shade = pygame.Surface((1680, 1050), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (224, 208, 173), PANEL)
        if self.frame is not None:
            screen.blit(self.frame, PANEL)
        bed = pygame.Rect(220, 135, 1240, 595)
        pygame.draw.rect(screen, (53, 43, 32), bed, border_radius=12)
        pygame.draw.rect(screen, (151, 116, 64), bed, 4, border_radius=12)
        # Four trains of nine wheels. Each tick moves one tooth in a brief burst.
        seconds = (pygame.time.get_ticks() if ticks is None else ticks) / 1000
        fraction = min(1, (seconds % 1) / .14)
        step = math.floor(seconds) + fraction * fraction * (3 - 2 * fraction)
        colors = [(167, 124, 61), (195, 155, 88), (138, 117, 83), (166, 155, 124)]
        for row in range(4):
            for col in range(9):
                cx, cy = 305 + col * 130 + (12 if row % 2 else 0), 215 + row * 145
                radius = (74, 57, 68, 62, 76, 54)[(col + row) % 6]
                # Brass drive rods visually join the wheel trains.
                if col < 8:
                    pygame.draw.line(screen, (112, 86, 49), (cx, cy), (cx + 130, cy), 6)
                if row < 3:
                    pygame.draw.line(screen, (112, 86, 49), (cx, cy), (cx, cy + 145), 5)
                teeth = (12, 16, 20)[(col + row) % 3]
                angle = step * math.tau / teeth * (-1 if (row + col) % 2 else 1)
                gear(screen, (cx, cy), radius, teeth, angle, colors[(col + row * 2) % 4])
        for x in (235, 1445):
            for y in (150, 715):
                pygame.draw.circle(screen, (194, 157, 95), (x, y), 7)
                pygame.draw.line(screen, (60, 44, 28), (x - 4, y), (x + 4, y), 2)
        for index, line in enumerate(self.lines):
            label = self.font.render(line, True, (67, 49, 31))
            screen.blit(label, label.get_rect(center=(840, 777 + index * 36)))
        pygame.draw.rect(screen, (192, 163, 112), CLOSE, border_radius=5)
        pygame.draw.rect(screen, (94, 67, 35), CLOSE, 3, border_radius=5)
        screen.blit(self.close_label, self.close_label.get_rect(center=CLOSE.center))
