"""Shared geometry and stacking for hand and lifecycle card hover effects."""

import pygame


HAND_HOVER_SCALE = 1.10


def hand_card_rect(slot_position, card_size, hovered=False, card_offset=-2):
    rect = pygame.Rect(slot_position[0] + card_offset, slot_position[1] + card_offset, *card_size)
    if hovered:
        center = rect.center
        rect.size = tuple(round(size * HAND_HOVER_SCALE) for size in card_size)
        rect.center = center
    return rect


class HandHover:
    def __init__(self, card_offset=-2, on_hover=None):
        self.card_offset = card_offset
        self.on_hover = on_hover
        self.cards = ()
        self.order = []
        self.hovered_slot = None

    def sync(self, cards):
        # Slot identities change on compaction/dealing; discard stale layering.
        snapshot = tuple(cards)
        if snapshot != self.cards:
            self.cards = snapshot
            self.order = [slot for slot, card in enumerate(cards) if card is not None]
            self.hovered_slot = None

    def pick(self, mouse_pos, positions, card_size, excluded_slot=None):
        for slot in reversed(self.order):
            if slot == excluded_slot or slot >= len(positions):
                continue
            rect = hand_card_rect(
                positions[slot], card_size, slot == self.hovered_slot, self.card_offset,
            )
            if rect.collidepoint(mouse_pos):
                return slot
        return None

    def update(self, mouse_pos, positions, card_size, enabled=True):
        slot = self.pick(mouse_pos, positions, card_size) if enabled else None
        if slot is not None and slot != self.hovered_slot and self.on_hover is not None:
            self.on_hover()
        self.hovered_slot = slot
        if slot is not None and self.order[-1] != slot:
            self.order.remove(slot)
            self.order.append(slot)
        return slot
