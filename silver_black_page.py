import os
import sys

import pygame

from game_data import REWARD_TOKEN_RANDOM_SILVER
from round_page_assets import load_round_page_static_assets


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

PAPER_COLOR = (83, 76, 70)
GOLD = (184, 134, 11)
SILVER = (165, 165, 170)
BLACK_CARD_TINT = (18, 16, 16, 125)
GOLD_CARD_TINT = (184, 134, 11, 70)
PANEL_SIZE = (1440, 900)
PANEL_POS = ((SCREEN_WIDTH - PANEL_SIZE[0]) // 2, (SCREEN_HEIGHT - PANEL_SIZE[1]) // 2)
CARD_ROW_SLOTS = 8
ACTIVE_CARD_SLOTS = 3
CARD_WIDTH = 102
CARD_ASPECT_RATIO = 99 / 171.0
ACTIVE_ROW_Y = 42
SILVER_ROW_Y = 253
BLACK_ROW_Y = 464
GOLD_ROW_Y = 675
INVENTORY_ROW_GAP = 34
ACTIVE_ROW_GAP = 42


class SilverBlackPage:
    """Intermediate card-selection screen before a round starts."""

    def __init__(self, screen, font_path, silver_cards, black_cards=None, gold_cards=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_path = font_path
        self.silver_cards = list(silver_cards or [])[:CARD_ROW_SLOTS]
        self.black_cards = list(black_cards or [])[:CARD_ROW_SLOTS]
        self.gold_cards = list(gold_cards or [])[:CARD_ROW_SLOTS]
        self.selected_entries = []

        round_page_assets = load_round_page_static_assets()
        self.round_background = round_page_assets["background"]
        self.round_koordinates = round_page_assets["koordinates"]

        self.card_width = CARD_WIDTH
        self.card_height = int(self.card_width / CARD_ASPECT_RATIO)
        self.panel_rect = pygame.Rect(PANEL_POS, PANEL_SIZE)
        self.background = self._load_image(os.path.join("RoundPage", "SilverBlack.png"), PANEL_SIZE)
        self.placeholder = self._load_placeholder()
        self.card_images = {}

        self.active_rects = self._build_row_rects(ACTIVE_CARD_SLOTS, y=ACTIVE_ROW_Y, gap=ACTIVE_ROW_GAP)
        self.silver_rects = self._build_row_rects(CARD_ROW_SLOTS, y=SILVER_ROW_Y, gap=INVENTORY_ROW_GAP)
        self.black_rects = self._build_row_rects(CARD_ROW_SLOTS, y=BLACK_ROW_Y, gap=INVENTORY_ROW_GAP)
        self.gold_rects = self._build_row_rects(CARD_ROW_SLOTS, y=GOLD_ROW_Y, gap=INVENTORY_ROW_GAP)
        self.drag_source = None
        self.drag_entry = None
        self.drag_active_slot = None
        self.drag_card_id = None
        self.drag_offset = (0, 0)
        self.drag_pos = (0, 0)

    def _load_image(self, path, size=None):
        if not os.path.exists(path):
            print(f"WARNING: SilverBlack asset not found: {path}")
            return None
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.smoothscale(image, size).convert_alpha()
        return image

    def _load_placeholder(self):
        path = os.path.join("GameplayPage", "Placeholder.png")
        image = self._load_image(path)
        if image is None:
            return None
        return pygame.transform.smoothscale(image, (self.card_width, self.card_height)).convert_alpha()

    def _build_row_rects(self, count, y, gap):
        total_width = count * self.card_width + (count - 1) * gap
        start_x = self.panel_rect.x + (self.panel_rect.width - total_width) // 2
        row_y = self.panel_rect.y + y
        return [
            pygame.Rect(start_x + idx * (self.card_width + gap), row_y, self.card_width, self.card_height)
            for idx in range(count)
        ]

    def _get_card_image(self, card_id):
        if card_id in self.card_images:
            return self.card_images[card_id]

        if card_id == REWARD_TOKEN_RANDOM_SILVER:
            path = os.path.join("RoundPage", "RandSilver.png")
            if not os.path.exists(path):
                path = os.path.join("Cards", "Card_201.png")
        else:
            path = os.path.join("Cards", f"Card_{int(card_id)}.png")
            if not os.path.exists(path) and 200 < int(card_id) < 300:
                path = os.path.join("RoundPage", "RandSilver.png")

        image = self._load_image(path, (self.card_width, self.card_height))
        self.card_images[card_id] = image
        return image

    def _row_cards(self, kind):
        if kind == "silver":
            return self.silver_cards
        if kind == "black":
            return self.black_cards
        if kind == "gold":
            return self.gold_cards
        return []

    def _card_id_for_entry(self, entry):
        if not entry:
            return None
        kind, index = entry
        cards = self._row_cards(kind)
        return cards[index] if 0 <= index < len(cards) else None

    def _selected_cards_by_kind(self, kind):
        return [
            self._card_id_for_entry(entry)
            for entry in self.selected_entries
            if entry[0] == kind and self._card_id_for_entry(entry) is not None
        ]

    def _selected_payload(self):
        return {
            "active_silver_cards": self._selected_cards_by_kind("silver"),
            "active_black_cards": self._selected_cards_by_kind("black"),
            "active_gold_cards": self._selected_cards_by_kind("gold"),
        }

    def _active_slot_at(self, pos):
        for active_slot, rect in enumerate(self.active_rects):
            if rect.collidepoint(pos):
                return active_slot
        return None

    def _inventory_entry_at(self, pos):
        for kind, rects in (
            ("silver", self.silver_rects),
            ("black", self.black_rects),
            ("gold", self.gold_rects),
        ):
            cards = self._row_cards(kind)
            for index, rect in enumerate(rects):
                if index < len(cards) and rect.collidepoint(pos):
                    return kind, index
        return None

    def _begin_drag(self, pos):
        active_slot = self._active_slot_at(pos)
        if active_slot is not None and active_slot < len(self.selected_entries):
            entry = self.selected_entries[active_slot]
            rect = self.active_rects[active_slot]
            self.drag_source = "active"
            self.drag_entry = entry
            self.drag_active_slot = active_slot
            self.drag_card_id = self._card_id_for_entry(entry)
            self.drag_offset = (pos[0] - rect.x, pos[1] - rect.y)
            self.drag_pos = pos
            return

        entry = self._inventory_entry_at(pos)
        if entry is None or entry in self.selected_entries:
            return

        kind, index = entry
        rects = {"silver": self.silver_rects, "black": self.black_rects, "gold": self.gold_rects}[kind]
        rect = rects[index]
        self.drag_source = "inventory"
        self.drag_entry = entry
        self.drag_active_slot = None
        self.drag_card_id = self._card_id_for_entry(entry)
        self.drag_offset = (pos[0] - rect.x, pos[1] - rect.y)
        self.drag_pos = pos

    def _move_drag(self, pos):
        if self.drag_source is not None:
            self.drag_pos = pos

    def _finish_drag(self, pos):
        if self.drag_source is None:
            return

        target_slot = self._active_slot_at(pos)
        if self.drag_source == "inventory":
            if (
                target_slot is not None
                and self.drag_entry is not None
                and self.drag_entry not in self.selected_entries
                and len(self.selected_entries) < len(self.active_rects)
            ):
                target_slot = min(target_slot, len(self.selected_entries))
                self.selected_entries.insert(target_slot, self.drag_entry)
        elif self.drag_source == "active":
            if self.drag_active_slot is not None and 0 <= self.drag_active_slot < len(self.selected_entries):
                moving_entry = self.selected_entries.pop(self.drag_active_slot)
                if target_slot is not None:
                    target_slot = min(target_slot, len(self.selected_entries))
                    self.selected_entries.insert(target_slot, moving_entry)

        self._clear_drag()

    def _clear_drag(self):
        self.drag_source = None
        self.drag_entry = None
        self.drag_active_slot = None
        self.drag_card_id = None
        self.drag_offset = (0, 0)
        self.drag_pos = (0, 0)

    def _draw_placeholder(self, rect, border_color=PAPER_COLOR):
        if self.placeholder:
            self.screen.blit(self.placeholder, rect.topleft)
        else:
            pygame.draw.rect(self.screen, (238, 228, 205), rect)
        pygame.draw.rect(self.screen, border_color, rect, 2)

    def _draw_card(self, card_id, rect):
        image = self._get_card_image(card_id)
        if image:
            self.screen.blit(image, rect.topleft)

    def _draw_tint(self, rect, color):
        tint = pygame.Surface(rect.size, pygame.SRCALPHA)
        tint.fill(color)
        self.screen.blit(tint, rect.topleft)

    def _active_border_color(self, entry):
        if not entry:
            return PAPER_COLOR
        kind = entry[0]
        if kind == "silver":
            return SILVER
        if kind == "gold":
            return GOLD
        return PAPER_COLOR

    def _draw_inventory_row(self, kind, rects, border_color, tint_color=None):
        cards = self._row_cards(kind)
        for index, rect in enumerate(rects):
            self._draw_placeholder(rect, border_color)
            if tint_color and index >= len(cards):
                self._draw_tint(rect, tint_color)
            entry = (kind, index)
            if (
                index < len(cards)
                and entry not in self.selected_entries
                and not (self.drag_source == "inventory" and self.drag_entry == entry)
            ):
                self._draw_card(cards[index], rect)

    def draw(self):
        if self.round_background:
            self.screen.blit(self.round_background, (0, 0))
        else:
            self.screen.fill((235, 220, 190))
        if self.round_koordinates:
            self.screen.blit(self.round_koordinates, (0, 0))

        if self.background:
            self.screen.blit(self.background, self.panel_rect.topleft)
        else:
            pygame.draw.rect(self.screen, (235, 220, 190), self.panel_rect)
            pygame.draw.rect(self.screen, PAPER_COLOR, self.panel_rect, 3)

        for slot, rect in enumerate(self.active_rects):
            entry = self.selected_entries[slot] if slot < len(self.selected_entries) else None
            self._draw_placeholder(rect, self._active_border_color(entry))
            if entry and not (self.drag_source == "active" and self.drag_active_slot == slot):
                card_id = self._card_id_for_entry(entry)
                if card_id is not None:
                    self._draw_card(card_id, rect)

        self._draw_inventory_row("silver", self.silver_rects, SILVER)
        self._draw_inventory_row("black", self.black_rects, PAPER_COLOR, BLACK_CARD_TINT)
        self._draw_inventory_row("gold", self.gold_rects, GOLD, GOLD_CARD_TINT)

        if self.drag_card_id is not None:
            draw_x = self.drag_pos[0] - self.drag_offset[0]
            draw_y = self.drag_pos[1] - self.drag_offset[1]
            self._draw_card(self.drag_card_id, pygame.Rect(draw_x, draw_y, self.card_width, self.card_height))

        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "back"
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        return self._selected_payload()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._begin_drag(event.pos)
                if event.type == pygame.MOUSEMOTION:
                    self._move_drag(event.pos)
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._finish_drag(event.pos)

            self.draw()
            self.clock.tick(FPS)
