"""Separate deck, offer, and defeated-boss views for the gameplay footer."""

import math

import pygame

import game_state
from shared_utils import wrap_text
from shop_page import SPECIAL_ASSETS


INK = (85, 73, 55)
ACCENT = (170, 130, 66)
VIEW_LABELS = {"deck": ("CollectionDeck", "Колода"), "offers": ("CollectionOffers", "Офферы"),
               "bosses": ("CollectionBosses", "Боссы")}
OFFER_GROUPS = (
    ("permanent", "OffersPermanent", "До конца забега"),
    ("temporary", "OffersTemporary", "Временные эффекты"),
    ("pending", "OffersPending", "Ожидают срабатывания"),
)
DECK_GROUPS = (
    ("permanent", "DeckPermanentCards", "Карты постоянной колоды"),
    ("temporary", "DeckTemporaryCards", "Временные карты (пропадут после победы над боссом)"),
    ("purchased", "DeckPurchasedCards", "Купленные карты (пропадут после поражения)"),
)


def group_deck_cards(cards):
    groups = {key: [] for key, _label, _fallback in DECK_GROUPS}
    for card in cards:
        origin = getattr(card, "deck_origin", None) or "permanent"
        groups.get(origin, groups["permanent"]).append(card)
    return groups


def group_offers(entries):
    groups = {key: [] for key, _label, _fallback in OFFER_GROUPS}
    for entry in entries:
        if entry.get("special_id") in ("long", "retention"):
            group = "pending"
        elif entry.get("remaining") is not None:
            group = "temporary"
        else:
            group = "permanent"
        groups[group].append(entry)
    return groups


def navigation_rects(page):
    anchor = page.deck_toggle_rect
    modes = ["deck"]
    if game_state.get_active_shop_offer_effects(page.level_number, page.defeated_count):
        modes.append("offers")
    if page._collect_defeated_boss_rewards():
        modes.append("bosses")
    slots = sorted(page.bottom_placeholders or [], key=lambda entry: entry["slot"])
    rects = {}
    for index, mode in enumerate(modes):
        center_x = slots[index]["rect"].centerx if index < len(slots) else anchor.centerx + index * 154
        rects[mode] = pygame.Rect(center_x - 48, anchor.y, 96, 120)
    return rects


def draw_navigation(page):
    if page._is_level6_alternating_battle():
        return
    for mode, rect in navigation_rects(page).items():
        icon = page.collection_icons.get(mode)
        if icon is not None:
            if rect.collidepoint(pygame.mouse.get_pos()):
                icon = pygame.transform.smoothscale(icon, (106, 106))
            page.screen.blit(icon, icon.get_rect(center=(rect.centerx, rect.y + 48)))
        key, fallback = VIEW_LABELS[mode]
        label = page.deck_toggle_font.render(page._get_text(key, fallback), True, INK)
        page.screen.blit(label, label.get_rect(center=(rect.centerx, rect.y + 106)))
        if page.deck_view_active and page.collection_view == mode:
            pygame.draw.line(page.screen, ACCENT, (rect.x + 10, rect.bottom),
                             (rect.right - 10, rect.bottom), 3)


def scroll_offset(page, content, total_height):
    mode = page.collection_view
    maximum = max(0, total_height - content.height)
    page.collection_scroll_max[mode] = maximum
    offset = max(0, min(page.collection_scroll.get(mode, 0), maximum))
    page.collection_scroll[mode] = offset
    page.collection_content_rect = content
    return offset


def draw_scrollbar(page, panel):
    mode = page.collection_view
    maximum = page.collection_scroll_max.get(mode, 0)
    if not maximum:
        return
    content = page.collection_content_rect
    track = pygame.Rect(panel.right - 19, content.top, 5, content.height)
    pygame.draw.rect(page.screen, (204, 191, 168), track, border_radius=2)
    thumb_h = max(30, round(track.height * content.height / (content.height + maximum)))
    top = track.top + round((track.height - thumb_h) * page.collection_scroll[mode] / maximum)
    pygame.draw.rect(page.screen, ACCENT, (track.x, top, track.width, thumb_h), border_radius=2)


def draw_empty(page, rect, key="CollectionEmpty", fallback="Пока пусто"):
    text = page.collection_font.render(page._get_text(key, fallback), True, INK)
    page.screen.blit(text, text.get_rect(midtop=(rect.centerx, rect.top + 24)))


def draw_deck(page, content, panel):
    full = getattr(page, "deck_view_scope", "remaining") == "full"
    cards = sorted(page.collection_full_deck) if full else page._collect_current_deck_cards()
    has_hedger = not full and bool(page._count_active_silver_card(408))
    if has_hedger:
        content.height -= 100
    card_h = 150
    card_w = round(card_h * page.card_size_market[0] / page.card_size_market[1])
    step_x, step_y = card_w + 22, card_h + 18
    columns = max(1, (content.width + 22) // step_x)
    groups = group_deck_cards(cards)
    sections = []
    total_height = 0
    for group, key, fallback in DECK_GROUPS:
        if not groups[group]:
            continue
        sections.append((group, key, fallback, total_height))
        total_height += 36 + math.ceil(len(groups[group]) / columns) * step_y
    offset = scroll_offset(page, content, total_height)
    start_x = content.centerx - (columns * step_x - 22) // 2
    old_clip = page.screen.get_clip()
    page.screen.set_clip(content.clip(old_clip))
    try:
        positioned_cards = []
        for group, key, fallback, top in sections:
            y = content.y + top - offset
            label = page.collection_font.render(page._get_text(key, fallback), True, INK)
            page.screen.blit(label, (start_x, y))
            positioned_cards.extend((index, card, y + 36) for index, card in enumerate(groups[group]))
        for index, card_id, y in positioned_cards:
            rect = pygame.Rect(start_x + index % columns * step_x,
                               y + index // columns * step_y, card_w, card_h)
            if not rect.colliderect(content):
                continue
            image = page.card_images_market.get(card_id) or page.card_images_bottom.get(card_id)
            if image:
                page.screen.blit(pygame.transform.smoothscale(image, rect.size), rect)
                page.draw_card_action(card_id, rect.x, rect.y, rect.size)
                page.draw_card_turns(card_id, rect.x, rect.y, rect.size)
            page.deck_view_card_entries.append({"card_id": card_id, "rect": rect.clip(content)})
            if not full and page._is_hedger_available() and page.hedger_selected_card_id is card_id:
                pygame.draw.rect(page.screen, ACCENT, rect.inflate(8, 8), 3, border_radius=4)
    finally:
        page.screen.set_clip(old_clip)
    if has_hedger and cards:
        page._draw_hedger_deck_controls(panel)


def offer_status(page, entry, pending=False):
    remaining = entry.get("remaining")
    if remaining is None:
        return page._get_text("OffersPermanent", "До конца забега")
    if entry.get("remaining_kind") == "bosses":
        key = "OfferAfterBoss" if pending else "OfferUntilBoss"
        return page._get_text(key, "После победы над боссом" if pending else "До победы над боссом")
    key = "OfferTriggersIn" if pending else "OfferRoundsLeft"
    template = page._get_text(key, "До срабатывания: {count} раунд." if pending else "Осталось: {count} раунд.")
    return template.format(count=remaining)


def draw_offers(page, content, panel):
    groups = group_offers(game_state.get_active_shop_offer_effects(page.level_number, page.defeated_count))
    card_w, card_h = 88, 139
    step_x, tile_h = 132, 240
    columns = max(1, (content.width + 22) // step_x)
    start_x = content.centerx - (columns * step_x - 22) // 2
    sections = []
    total_height = 0
    for group, key, fallback in OFFER_GROUPS:
        if not groups[group]:
            continue
        sections.append((group, key, fallback, total_height))
        total_height += 36 + math.ceil(len(groups[group]) / columns) * tile_h
    offset = scroll_offset(page, content, total_height)
    old_clip = page.screen.get_clip()
    page.screen.set_clip(content.clip(old_clip))
    hovered = None
    mouse = pygame.mouse.get_pos()
    try:
        for group, key, fallback, top in sections:
            heading_y = content.y + top - offset
            header = page.collection_font.render(page._get_text(key, fallback), True, INK)
            page.screen.blit(header, (start_x, heading_y))
            for index, entry in enumerate(groups[group]):
                center_x = start_x + index % columns * step_x + card_w // 2
                y = heading_y + 36 + index // columns * tile_h
                rect = pygame.Rect(center_x - 44, y, 88, 139)
                image = page._get_deck_view_offer_image(entry.get("special_id"), rect.size)
                if rect.colliderect(content):
                    if image:
                        page.screen.blit(image, rect)
                    else:
                        pygame.draw.rect(page.screen, (226, 214, 190), rect)
                    drawn = {**entry, "rect": rect.clip(content), "category": group}
                    page.deck_view_offer_entries.append(drawn)
                    if drawn["rect"].collidepoint(mouse):
                        hovered = drawn
                name = SPECIAL_ASSETS.get(entry.get("special_id"), (str(entry.get("special_id")), None))[0]
                for line_index, line in enumerate(wrap_text(name, page.deck_toggle_font, step_x - 12)):
                    text = page.deck_toggle_font.render(line, True, INK)
                    page.screen.blit(text, text.get_rect(midtop=(center_x, y + 143 + line_index * 21)))
                if entry.get("remaining") is None:
                    continue
                status = offer_status(page, entry, group == "pending")
                for line_index, line in enumerate(wrap_text(status, page.deck_toggle_font, step_x - 12)):
                    text = page.deck_toggle_font.render(line, True, INK)
                    page.screen.blit(text, text.get_rect(midtop=(center_x, y + 186 + line_index * 20)))
    finally:
        page.screen.set_clip(old_clip)
    if hovered:
        page._draw_active_shop_offer_tooltip(hovered, panel)


def draw_bosses(page, content, panel):
    entries = page._collect_defeated_boss_rewards()
    rows = []
    for entry in entries:
        lines = wrap_text(entry.get("reward_text", ""), page.collection_font, content.width - 148)
        height = max(124, len(lines) * 27 + 22)
        rows.append((entry, lines, height))
    offset = scroll_offset(page, content, sum(height for _entry, _lines, height in rows))
    old_clip = page.screen.get_clip()
    page.screen.set_clip(content.clip(old_clip))
    y = content.y - offset
    try:
        if not rows:
            draw_empty(page, content, "BossRewardsEmpty", "Пока нет побеждённых боссов")
        for entry, lines, height in rows:
            rect = pygame.Rect(content.x + 4, y + 5, 102, 102)
            icon = page._load_defeated_boss_icon(entry.get("filename"))
            if icon:
                page.screen.blit(icon, rect)
            for index, line in enumerate(lines):
                text = page.collection_font.render(line, True, INK)
                page.screen.blit(text, (content.x + 132, y + 12 + index * 27))
            y += height
    finally:
        page.screen.set_clip(old_clip)


def draw_collection_view(page):
    dim = pygame.Surface(page.screen.get_size(), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 85))
    page.screen.blit(dim, (0, 0))
    panel = page.deck_view_panel_rect
    if page.deck_view_panel_background:
        page.screen.blit(page.deck_view_panel_background, panel)
    else:
        pygame.draw.rect(page.screen, (241, 232, 210), panel)
    pygame.draw.rect(page.screen, INK, panel, 3)
    mode = page.collection_view
    key, fallback = VIEW_LABELS[mode]
    page.deck_scope_rects = {}
    if mode == "deck":
        for index, (scope, label_key, label_fallback) in enumerate((
            ("remaining", "DeckRemaining", "Оставшаяся колода"),
            ("full", "DeckFull", "Полная колода"),
        )):
            rect = pygame.Rect(panel.centerx - 330 + index * 340, panel.top + 34, 320, 44)
            page.deck_scope_rects[scope] = rect
            if rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(page.screen, (226, 214, 190), rect, border_radius=4)
            label = page.collection_font.render(page._get_text(label_key, label_fallback), True, INK)
            page.screen.blit(label, label.get_rect(center=rect.center))
            if getattr(page, "deck_view_scope", "remaining") == scope:
                pygame.draw.line(page.screen, ACCENT, (rect.left + 12, rect.bottom), (rect.right - 12, rect.bottom), 2)
    else:
        title = page.font_small.render(page._get_text(key, fallback), True, INK)
        page.screen.blit(title, title.get_rect(midtop=(panel.centerx, panel.top + 38)))
    page.collection_close_rect = pygame.Rect(panel.right - 64, panel.top + 34, 40, 40)
    close = page.collection_close_rect
    pygame.draw.line(page.screen, INK, (close.x + 12, close.y + 12), (close.right - 12, close.bottom - 12), 2)
    pygame.draw.line(page.screen, INK, (close.right - 12, close.y + 12), (close.x + 12, close.bottom - 12), 2)
    page.deck_view_card_entries = []
    page.deck_view_offer_entries = []
    page.hedger_add_button_rect = page.hedger_yes_button_rect = page.hedger_no_button_rect = None
    content = pygame.Rect(panel.x + 40, panel.y + 100, panel.width - 80, panel.height - 148)
    {"deck": draw_deck, "offers": draw_offers, "bosses": draw_bosses}[mode](page, content, panel)
    draw_scrollbar(page, panel)
    draw_navigation(page)
