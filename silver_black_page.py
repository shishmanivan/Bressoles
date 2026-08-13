import os
import sys

import pygame

import game_state
from card_catalog import MARKET_CARD_TURNS, PRICE_CARD_ACTIONS, get_card_image_base_id
from game_data import REWARD_TOKEN_RANDOM_SILVER
from gameplay_card_rendering import (
    draw_bear_modifier_text,
    draw_bid_modifier_text,
    draw_card_action_text,
    draw_card_turns_text,
)
from gameplay_deck import get_card_investment_bonus
from round_page_assets import load_round_page_static_assets
from shared_utils import wrap_text


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

PAPER_COLOR = (83, 76, 70)
GOLD = (184, 134, 11)
SILVER = (165, 165, 170)
BLACK_CARD_TINT = (18, 16, 16, 125)
GOLD_CARD_TINT = (184, 134, 11, 70)
BUTTON_COLOR = (238, 228, 205)
BUTTON_HOVER_COLOR = (248, 239, 216)
PANEL_SIZE = (1440, 900)
PANEL_POS = ((SCREEN_WIDTH - PANEL_SIZE[0]) // 2, (SCREEN_HEIGHT - PANEL_SIZE[1]) // 2)
CARD_ROW_SLOTS = 8
CARD_WIDTH = 102
CARD_ASPECT_RATIO = 99 / 171.0
ACTIVE_ROW_Y = 59
SILVER_ROW_Y = 252
BLACK_ROW_Y = 450
GOLD_ROW_Y = 648
INVENTORY_ROW_GAP = 34
ACTIVE_ROW_GAP = 42
POSITIONING_CARDS_PER_PAGE = 24
POSITIONING_GRID_COLUMNS = 8


def get_positioning_selection_limit(active_gold_cards):
    active_ids = set()
    for card_id in active_gold_cards or []:
        try:
            active_ids.add(int(card_id))
        except (TypeError, ValueError):
            continue
    if 417 in active_ids and 418 in active_ids:
        return 6
    if 418 in active_ids:
        return 3
    if 417 in active_ids:
        return 2
    return 0

CARD_TOOLTIPS = {
    201: (
        "Rebate",
        "В последний ход автоматически продаёт все оставшиеся акции по полной текущей цене.",
    ),
    202: ("Futures", "Добавляет 1 ход к длительности раунда."),
    203: ("Futures", "Добавляет 2 хода к длительности раунда."),
    204: (
        "Contango",
        "Удваивает силу всех Gain/Drop-карт. Несколько копий умножают эффект повторно.",
    ),
    206: (
        "Basket Trading",
        "Если за ход выросли все три рынка, дополнительно повышает цену каждой акции на 2.",
    ),
    207: (
        "Forward Trading",
        "За каждые две сыгранные карты Shareholder добавляет 1 ход к раунду.",
    ),
    208: (
        "Rollover",
        "Добавляет 1 ход всем Gain/Drop-картам.",
    ),
    209: (
        "Frugality",
        "Переносит все неиспользованные ходы в следующий раунд.",
    ),
    210: (
        "Catalyst",
        "Усиливает числовые процентные эффекты карт на 10 процентных пунктов, сохраняя полезное направление эффекта.",
    ),
    214: ("Grant", "Добавляет 4 к стартовым деньгам в начале раунда."),
    215: (
        "Bill of exchange",
        "После победы снижает цены всех предложений в следующем магазине на 50%.",
    ),
    217: ("Obligation", "После победы приносит дополнительно 5 наполеондоров."),
    218: ("Obligation", "После победы приносит дополнительно 10 наполеондоров."),
    219: ("Obligation", "После победы приносит дополнительно 15 наполеондоров."),
    220: (
        "Insurance",
        "В обычном раунде превращает поражение в победу. Недостающая сумма добавляется к цели следующего обычного раунда. Нельзя использовать против боссов.",
    ),
    301: ("Futures", "Добавляет 1 ход к длительности раунда."),
    302: (
        "Golden Stocks",
        "В конце победного раунда может дать случайную золотую карту. Базовый шанс 10%, после неудачи шанс растёт на 2%. После успеха больше не срабатывает.",
    ),
    303: (
        "Комиссия",
        "После победы даёт 1 наполеондор. За победу над боссом даёт 2 наполеондора.",
    ),
    401: (
        "Bear",
        "Снижает цель на 2%. После каждой победы снижение увеличивается ещё на 2 процентных пункта.",
    ),
    402: (
        "Forward Trading",
        "Каждая сыгранная карта Shareholder добавляет 1 ход.",
    ),
    403: (
        "Grant",
        "Добавляет 8 к стартовым деньгам.",
    ),
    405: (
        "Insider",
        "Первые два хода акции C гарантированно растут.",
    ),
}


CARD_TOOLTIPS.update(
    {
        404: (
            "Flat",
            "Отключает случайные падения и взлёты акций. Рыночный бросок всегда Flat.",
        ),
        406: (
            "Gambling",
            "Усиливает карты Upside и Downside на 7 процентных пунктов.",
        ),
    }
)


CARD_TOOLTIPS.update(
    {
        407: (
            "Rebate",
            "Продаёт акции за 130% от их стоимости. Каждый раз, когда акции A падают, это число увеличивается ещё на 2%.",
        ),
        408: (
            "Hedger",
            "Один раз за раунд позволяет взять любую карту из колоды в руку, если есть место.",
        ),
        409: (
            "Momentum",
            "После случайного роста или падения акция повторяет то же движение ещё раз. Изменения цен от карт не учитываются.",
        ),
        410: (
            "Uptrend",
            "Добавляет к эффекту Rebate по 1% за каждый имеющийся наполеондор.",
        ),
        411: (
            "Spoofing",
            "На четвёртом ходу акции, которыми владеет игрок, гарантированно растут.",
        ),
        412: (
            "Spoofing+",
            "На четвёртом и восьмом ходах акции, которыми владеет игрок, гарантированно растут.",
        ),
        413: (
            "Shakeout",
            "Удваивает вероятность падения акций, которыми игрок не владеет.",
        ),
        414: (
            "Catalyst",
            "Усиливает числовые процентные эффекты карт на 15 процентных пунктов, сохраняя полезное направление эффекта.",
        ),
        415: (
            "Surge",
            "Если игрок четыре хода подряд ничего не покупает и не продаёт, в конце четвёртого такого хода цена акций A увеличивается в 3 раза.",
        ),
        416: (
            "Sideway",
            "Даёт 5 наполеондоров если на на всех трёх рынках выпал Flat (цена не изменилась).",
        ),
        417: (
            "Positioning",
            "Перед началом раунда позволяет выбрать 2 карты, которые гарантированно попадут в стартовую руку.",
        ),
        418: (
            "Positioning+",
            "Перед началом раунда позволяет выбрать 3 карты, которые гарантированно попадут в стартовую руку.",
        ),
        419: (
            "Continuation",
            "После первого роста удерживаемой акции каждый следующий последовательный рост дополнительно умножает её цену на 1.2. Flat, падение или продажа акции прерывают её серию.",
        ),
        420: (
            "Advance",
            "С шансом 20% удваивает цены всех акций, которыми владеет игрок. Карты, добавляющие процентные пункты, повышают этот шанс.",
        ),
        421: (
            "Issue Price",
            "В начале раунда устанавливает стартовую цену акций A на 6 долларов.",
        ),
        422: (
            "Markdown",
            "Снижает цель третьего и четвёртого обычных раундов на 30%. В остальных раундах и боях с боссами не действует.",
        ),
        423: (
            "Stewardship",
            "Каждый Shareholder в руке добавляет 20 процентных пунктов к итоговому эффекту Rebate.",
        ),
    }
)


class SilverBlackPage:
    """Intermediate card-selection screen before a round starts."""

    def __init__(
        self,
        screen,
        font_path,
        silver_cards,
        black_cards=None,
        gold_cards=None,
        active_black_cards=None,
        active_gold_cards=None,
        active_lifecycle_card_order=None,
        is_boss_fight=False,
        lang_dict=None,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_path = font_path
        self.silver_cards = list(silver_cards or [])[:CARD_ROW_SLOTS]
        self.black_cards = list(black_cards or [])[:CARD_ROW_SLOTS]
        self.gold_cards = list(gold_cards or [])[:CARD_ROW_SLOTS]
        self.is_boss_fight = bool(is_boss_fight)
        self.lang = lang_dict or {}
        self.selected_entries = []
        self.active_slot_count = game_state.get_lifecycle_card_slot_limit()

        round_page_assets = load_round_page_static_assets()
        self.round_background = round_page_assets["background"]
        self.round_koordinates = round_page_assets["koordinates"]

        self.card_width = CARD_WIDTH
        self.card_height = int(self.card_width / CARD_ASPECT_RATIO)
        self.panel_rect = pygame.Rect(PANEL_POS, PANEL_SIZE)
        self.background = self._load_image(os.path.join("RoundPage", "SilverBlack.png"), PANEL_SIZE)
        self.placeholder = self._load_placeholder()
        self.card_images = {}
        self.tooltip_title_font = pygame.font.Font(self.font_path, 27)
        self.tooltip_text_font = pygame.font.Font(self.font_path, 22)
        self.row_label_font = pygame.font.Font(self.font_path, 23)
        self.continue_button_font = pygame.font.Font(self.font_path, 32)

        self.active_rects = self._build_row_rects(self.active_slot_count, y=ACTIVE_ROW_Y, gap=ACTIVE_ROW_GAP)
        self.silver_rects = self._build_row_rects(CARD_ROW_SLOTS, y=SILVER_ROW_Y, gap=INVENTORY_ROW_GAP)
        self.black_rects = self._build_row_rects(CARD_ROW_SLOTS, y=BLACK_ROW_Y, gap=INVENTORY_ROW_GAP)
        self.gold_rects = self._build_row_rects(CARD_ROW_SLOTS, y=GOLD_ROW_Y, gap=INVENTORY_ROW_GAP)
        self.row_label_surfaces = self._build_row_label_surfaces()
        self.row_label_rects = {
            kind: surface.get_rect(midright=(rects[0].left - 24, rects[0].centery))
            for kind, surface, rects in (
                ("active", self.row_label_surfaces["active"], self.active_rects),
                ("silver", self.row_label_surfaces["silver"], self.silver_rects),
                ("black", self.row_label_surfaces["black"], self.black_rects),
                ("gold", self.row_label_surfaces["gold"], self.gold_rects),
            )
            if rects
        }
        self.continue_button_rect = pygame.Rect(0, 0, 260, 54)
        self.continue_button_rect.midright = (self.panel_rect.right - 40, self.active_rects[0].centery)
        self.selected_entries = self._build_initial_selected_entries(
            active_black_cards,
            active_gold_cards,
            active_lifecycle_card_order,
        )
        self.drag_source = None
        self.drag_entry = None
        self.drag_active_slot = None
        self.drag_card_id = None
        self.drag_offset = (0, 0)
        self.drag_pos = (0, 0)

    def _get_text(self, key, default):
        return self.lang.get(key, default)

    def _build_row_label_surfaces(self):
        labels = {
            "active": self._get_text("LifecycleSelected", "Выбрано"),
            "silver": self._get_text("LifecycleSilver", "Серебряные карты"),
            "black": self._get_text("LifecycleBlack", "Чёрные карты"),
            "gold": self._get_text("LifecycleGold", "Золотые карты"),
        }
        return {
            kind: self.row_label_font.render(label, True, PAPER_COLOR)
            for kind, label in labels.items()
        }

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

    def _entry_for_card(self, kind, target, used_indices):
        inventory_cards = self._row_cards(kind)
        try:
            target = int(target)
        except (TypeError, ValueError):
            return None
        for index, card_id in enumerate(inventory_cards):
            if index in used_indices:
                continue
            try:
                if int(card_id) != target:
                    continue
            except (TypeError, ValueError):
                continue
            used_indices.add(index)
            return kind, index
        return None

    def _build_initial_selected_entries(self, active_black_cards, active_gold_cards, active_lifecycle_card_order=None):
        entries = []
        used_by_kind = {"black": set(), "gold": set()}
        for order_entry in active_lifecycle_card_order or []:
            if len(entries) >= self.active_slot_count:
                break
            if isinstance(order_entry, dict):
                kind = str(order_entry.get("kind") or "").lower()
                card_id = order_entry.get("card_id", order_entry.get("id"))
            elif isinstance(order_entry, (list, tuple)) and len(order_entry) >= 2:
                kind = str(order_entry[0] or "").lower()
                card_id = order_entry[1]
            else:
                continue
            if kind not in used_by_kind:
                continue
            entry = self._entry_for_card(kind, card_id, used_by_kind[kind])
            if entry is not None:
                entries.append(entry)

        for kind, active_cards, inventory_cards in (
            ("black", active_black_cards, self.black_cards),
            ("gold", active_gold_cards, self.gold_cards),
        ):
            used_indices = used_by_kind[kind]
            for active_card_id in active_cards or []:
                if len(entries) >= self.active_slot_count:
                    break
                entry = self._entry_for_card(kind, active_card_id, used_indices)
                if entry is None or entry in entries:
                    continue
                entries.append(entry)
        return entries

    def _get_card_image(self, card_id):
        if card_id in self.card_images:
            return self.card_images[card_id]

        if card_id == REWARD_TOKEN_RANDOM_SILVER:
            path = os.path.join("RoundPage", "RandSilver.png")
            if not os.path.exists(path):
                path = os.path.join("Cards", "Card_201.png")
        else:
            base_card_id = get_card_image_base_id(card_id)
            path = os.path.join("Cards", f"Card_{int(base_card_id)}.png")
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
            if (
                entry[0] == kind
                and self._card_id_for_entry(entry) is not None
                and not self._is_card_disabled(self._card_id_for_entry(entry))
            )
        ]

    def _selected_payload(self):
        return {
            "active_silver_cards": self._selected_cards_by_kind("silver"),
            "active_black_cards": self._selected_cards_by_kind("black"),
            "active_gold_cards": self._selected_cards_by_kind("gold"),
            "active_lifecycle_card_order": [
                {"kind": entry[0], "card_id": self._card_id_for_entry(entry)}
                for entry in self.selected_entries
                if (
                    self._card_id_for_entry(entry) is not None
                    and not self._is_card_disabled(self._card_id_for_entry(entry))
                )
            ],
        }

    def _handle_mouse_down(self, position):
        if self.continue_button_rect.collidepoint(position):
            return self._selected_payload()
        self._begin_drag(position)
        return None

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
            if self._is_card_disabled(self._card_id_for_entry(entry)):
                return
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
        if self._is_card_disabled(self._card_id_for_entry(entry)):
            return
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
            draw_bear_modifier_text(
                self.screen,
                card_id,
                rect.x,
                rect.y,
                (self.card_width, self.card_height),
                self.font_path,
                PAPER_COLOR,
                modifier_percent=game_state.get_bear_goal_discount_percent([card_id]),
            )

    def _draw_tint(self, rect, color):
        tint = pygame.Surface(rect.size, pygame.SRCALPHA)
        tint.fill(color)
        self.screen.blit(tint, rect.topleft)

    def _is_card_disabled(self, card_id):
        try:
            return self.is_boss_fight and int(card_id) == 220
        except (TypeError, ValueError):
            return False

    def _draw_disabled_card(self, rect):
        self._draw_tint(rect, (45, 38, 35, 165))
        label = self.tooltip_text_font.render("Нельзя", True, (244, 235, 211))
        label_rect = label.get_rect(center=rect.center)
        padding = 7
        background = label_rect.inflate(padding * 2, padding)
        pygame.draw.rect(self.screen, (83, 76, 70), background, border_radius=5)
        self.screen.blit(label, label_rect)

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
                if self._is_card_disabled(cards[index]):
                    self._draw_disabled_card(rect)

    def _hovered_card(self, pos):
        for slot, rect in enumerate(self.active_rects):
            if slot < len(self.selected_entries) and rect.collidepoint(pos):
                entry = self.selected_entries[slot]
                return self._card_id_for_entry(entry), entry[0]

        for kind, rects in (
            ("silver", self.silver_rects),
            ("black", self.black_rects),
            ("gold", self.gold_rects),
        ):
            cards = self._row_cards(kind)
            for index, rect in enumerate(rects):
                entry = (kind, index)
                if (
                    index < len(cards)
                    and entry not in self.selected_entries
                    and rect.collidepoint(pos)
                ):
                    return cards[index], kind
        return None, None

    def _tooltip_content(self, card_id, kind):
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            normalized = card_id

        if normalized == REWARD_TOKEN_RANDOM_SILVER:
            return "Случайная серебряная карта", "При получении превращается в случайную доступную серебряную карту."
        if normalized in CARD_TOOLTIPS:
            title, description = CARD_TOOLTIPS[normalized]
            if self._is_card_disabled(normalized):
                description = f"НЕДОСТУПНО ПЕРЕД БОССОМ. {description}"
            return title, description

        kind_names = {
            "silver": "Серебряная карта",
            "black": "Чёрная карта",
            "gold": "Золотая карта",
        }
        title = f"{kind_names.get(kind, 'Карта')} · Card {normalized}"
        return title, "Описание эффекта этой карты пока не задано."

    def _draw_card_tooltip(self):
        if self.drag_source is not None:
            return

        mouse_pos = pygame.mouse.get_pos()
        card_id, kind = self._hovered_card(mouse_pos)
        if card_id is None:
            return

        title, description = self._tooltip_content(card_id, kind)
        width = 460
        padding = 16
        text_width = width - padding * 2
        description_lines = wrap_text(
            description,
            self.tooltip_text_font,
            text_width,
            color=PAPER_COLOR,
        )
        title_height = self.tooltip_title_font.get_height()
        line_height = self.tooltip_text_font.get_height() + 4
        height = padding * 2 + title_height + 10 + line_height * len(description_lines)

        x = mouse_pos[0] + 20
        y = mouse_pos[1] + 20
        x = max(8, min(x, SCREEN_WIDTH - width - 8))
        if y + height > SCREEN_HEIGHT - 8:
            y = mouse_pos[1] - height - 20
        y = max(8, min(y, SCREEN_HEIGHT - height - 8))

        tooltip = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(tooltip, (244, 235, 211, 248), tooltip.get_rect(), border_radius=10)
        pygame.draw.rect(tooltip, PAPER_COLOR, tooltip.get_rect(), 3, border_radius=10)

        title_surface = self.tooltip_title_font.render(str(title), True, PAPER_COLOR)
        tooltip.blit(title_surface, (padding, padding))
        text_y = padding + title_height + 10
        for line in description_lines:
            line_surface = self.tooltip_text_font.render(line, True, PAPER_COLOR)
            tooltip.blit(line_surface, (padding, text_y))
            text_y += line_height

        self.screen.blit(tooltip, (x, y))

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
                    if self._is_card_disabled(card_id):
                        self._draw_disabled_card(rect)

        self._draw_inventory_row("silver", self.silver_rects, SILVER)
        self._draw_inventory_row("black", self.black_rects, PAPER_COLOR, BLACK_CARD_TINT)
        self._draw_inventory_row("gold", self.gold_rects, GOLD, GOLD_CARD_TINT)

        for kind, surface in self.row_label_surfaces.items():
            rect = self.row_label_rects.get(kind)
            if rect:
                self.screen.blit(surface, rect)

        mouse_pos = pygame.mouse.get_pos()
        button_color = BUTTON_HOVER_COLOR if self.continue_button_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, button_color, self.continue_button_rect, border_radius=4)
        pygame.draw.rect(self.screen, PAPER_COLOR, self.continue_button_rect, 3, border_radius=4)
        continue_label = self._get_text("LifecycleContinue", "Продолжить")
        continue_surface = self.continue_button_font.render(continue_label, True, PAPER_COLOR)
        self.screen.blit(continue_surface, continue_surface.get_rect(center=self.continue_button_rect.center))

        if self.drag_card_id is not None:
            draw_x = self.drag_pos[0] - self.drag_offset[0]
            draw_y = self.drag_pos[1] - self.drag_offset[1]
            self._draw_card(self.drag_card_id, pygame.Rect(draw_x, draw_y, self.card_width, self.card_height))

        self._draw_card_tooltip()
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
                    result = self._handle_mouse_down(event.pos)
                    if result is not None:
                        return result
                if event.type == pygame.MOUSEMOTION:
                    self._move_drag(event.pos)
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._finish_drag(event.pos)

            self.draw()
            self.clock.tick(FPS)


class PositioningPage(SilverBlackPage):
    """Choose cards that Positioning guarantees in the next starting hand."""

    def __init__(self, screen, font_path, deck_cards, selection_limit, lang_dict=None):
        super().__init__(
            screen,
            font_path,
            silver_cards=[],
            black_cards=[],
            gold_cards=[],
            lang_dict=lang_dict,
        )
        self.deck_cards = list(deck_cards or [])
        try:
            requested_limit = max(0, int(selection_limit or 0))
        except (TypeError, ValueError):
            requested_limit = 0
        self.selection_target = min(requested_limit, len(self.deck_cards))
        self.selected_card_indices = []
        self.positioning_page_index = 0
        self.title_font = pygame.font.Font(self.font_path, 54)
        self.prompt_font = pygame.font.Font(self.font_path, 27)
        self.selection_badge_font = pygame.font.Font(self.font_path, 21)
        self.positioning_action_font_cache = {}
        self.positioning_turns_font_cache = {}
        self.positioning_card_turns = dict(MARKET_CARD_TURNS)

        grid_gap_x = 34
        grid_gap_y = 20
        self.positioning_grid_gap_x = grid_gap_x
        self.positioning_grid_gap_y = grid_gap_y
        total_width = (
            POSITIONING_GRID_COLUMNS * self.card_width
            + (POSITIONING_GRID_COLUMNS - 1) * grid_gap_x
        )
        start_x = self.panel_rect.centerx - total_width // 2
        start_y = self.panel_rect.y + 205
        self.positioning_grid_start_y = start_y
        self.positioning_card_rects = []
        for local_index in range(POSITIONING_CARDS_PER_PAGE):
            row, column = divmod(local_index, POSITIONING_GRID_COLUMNS)
            self.positioning_card_rects.append(
                pygame.Rect(
                    start_x + column * (self.card_width + grid_gap_x),
                    start_y + row * (self.card_height + grid_gap_y),
                    self.card_width,
                    self.card_height,
                )
            )

        button_y = self.panel_rect.bottom - 82
        self.positioning_back_button_rect = pygame.Rect(self.panel_rect.x + 42, button_y, 210, 54)
        self.positioning_continue_button_rect = pygame.Rect(
            self.panel_rect.right - 302,
            button_y,
            260,
            54,
        )
        self.positioning_prev_button_rect = pygame.Rect(self.panel_rect.centerx - 190, button_y, 120, 54)
        self.positioning_next_button_rect = pygame.Rect(self.panel_rect.centerx + 70, button_y, 120, 54)

    @property
    def positioning_page_count(self):
        return max(
            1,
            (len(self.deck_cards) + POSITIONING_CARDS_PER_PAGE - 1)
            // POSITIONING_CARDS_PER_PAGE,
        )

    def _visible_positioning_entries(self):
        start = self.positioning_page_index * POSITIONING_CARDS_PER_PAGE
        visible_count = min(POSITIONING_CARDS_PER_PAGE, max(0, len(self.deck_cards) - start))
        entries = []
        for local_index in range(visible_count):
            deck_index = start + local_index
            row, column = divmod(local_index, POSITIONING_GRID_COLUMNS)
            cards_in_row = min(
                POSITIONING_GRID_COLUMNS,
                visible_count - row * POSITIONING_GRID_COLUMNS,
            )
            row_width = (
                cards_in_row * self.card_width
                + (cards_in_row - 1) * self.positioning_grid_gap_x
            )
            row_start_x = self.panel_rect.centerx - row_width // 2
            rect = pygame.Rect(
                row_start_x + column * (self.card_width + self.positioning_grid_gap_x),
                self.positioning_grid_start_y
                + row * (self.card_height + self.positioning_grid_gap_y),
                self.card_width,
                self.card_height,
            )
            entries.append((deck_index, self.deck_cards[deck_index], rect))
        return entries

    def _toggle_positioning_card(self, deck_index):
        if not 0 <= deck_index < len(self.deck_cards):
            return False
        if deck_index in self.selected_card_indices:
            self.selected_card_indices.remove(deck_index)
            return True
        if len(self.selected_card_indices) >= self.selection_target:
            return False
        self.selected_card_indices.append(deck_index)
        return True

    def _positioning_selection_complete(self):
        return len(self.selected_card_indices) == self.selection_target

    def _selected_positioning_cards(self):
        return [self.deck_cards[index] for index in self.selected_card_indices]

    def _draw_positioning_button(self, rect, label, enabled=True):
        hovered = enabled and rect.collidepoint(pygame.mouse.get_pos())
        color = BUTTON_HOVER_COLOR if hovered else BUTTON_COLOR
        if not enabled:
            color = (218, 210, 194)
        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        pygame.draw.rect(self.screen, PAPER_COLOR, rect, 3, border_radius=4)
        text_color = PAPER_COLOR if enabled else (145, 138, 130)
        surface = self.continue_button_font.render(label, True, text_color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_positioning_background(self):
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

    def _draw_positioning_card_values(self, card_id, rect):
        try:
            normalized_id = int(card_id)
        except (TypeError, ValueError):
            return

        action_value = PRICE_CARD_ACTIONS.get(normalized_id)
        if action_value is not None:
            investment_bonus = get_card_investment_bonus(card_id)
            if investment_bonus > 0:
                action_value = (
                    action_value - investment_bonus
                    if action_value < 0
                    else action_value + investment_bonus
                )
            draw_card_action_text(
                self.screen,
                normalized_id,
                {normalized_id: action_value},
                rect.x,
                rect.y,
                rect.size,
                self.font_path,
                PAPER_COLOR,
                self.positioning_action_font_cache,
            )
        draw_card_turns_text(
            self.screen,
            normalized_id,
            self.positioning_card_turns,
            rect.x,
            rect.y,
            rect.size,
            self.font_path,
            PAPER_COLOR,
            self.positioning_turns_font_cache,
        )
        draw_bid_modifier_text(
            self.screen,
            normalized_id,
            rect.x,
            rect.y,
            rect.size,
            self.font_path,
        )

    def draw(self):
        self._draw_positioning_background()
        title = self.title_font.render("Positioning", True, PAPER_COLOR)
        self.screen.blit(
            title,
            title.get_rect(center=(self.panel_rect.centerx, self.panel_rect.y + 72)),
        )
        prompt = (
            f"Выберите карты для стартовой руки: "
            f"{len(self.selected_card_indices)} / {self.selection_target}"
        )
        prompt_surface = self.prompt_font.render(prompt, True, PAPER_COLOR)
        self.screen.blit(
            prompt_surface,
            prompt_surface.get_rect(center=(self.panel_rect.centerx, self.panel_rect.y + 142)),
        )

        for deck_index, card_id, rect in self._visible_positioning_entries():
            self._draw_placeholder(rect, PAPER_COLOR)
            self._draw_card(card_id, rect)
            self._draw_positioning_card_values(card_id, rect)
            if deck_index not in self.selected_card_indices:
                continue
            pygame.draw.rect(self.screen, GOLD, rect.inflate(10, 10), 5, border_radius=4)
            selection_number = self.selected_card_indices.index(deck_index) + 1
            badge_center = (rect.right - 5, rect.top + 5)
            pygame.draw.circle(self.screen, GOLD, badge_center, 18)
            badge = self.selection_badge_font.render(str(selection_number), True, (255, 250, 230))
            self.screen.blit(badge, badge.get_rect(center=badge_center))

        self._draw_positioning_button(self.positioning_back_button_rect, "Назад")
        self._draw_positioning_button(
            self.positioning_continue_button_rect,
            "Продолжить",
            enabled=self._positioning_selection_complete(),
        )
        if self.positioning_page_count > 1:
            has_previous = self.positioning_page_index > 0
            has_next = self.positioning_page_index + 1 < self.positioning_page_count
            self._draw_positioning_button(self.positioning_prev_button_rect, "Пред.", has_previous)
            self._draw_positioning_button(self.positioning_next_button_rect, "След.", has_next)
            page_text = self.prompt_font.render(
                f"{self.positioning_page_index + 1} / {self.positioning_page_count}",
                True,
                PAPER_COLOR,
            )
            self.screen.blit(
                page_text,
                page_text.get_rect(center=(self.panel_rect.centerx, self.positioning_prev_button_rect.centery)),
            )
        pygame.display.flip()

    def _handle_positioning_mouse_down(self, position):
        if self.positioning_back_button_rect.collidepoint(position):
            return "back"
        if self.positioning_continue_button_rect.collidepoint(position):
            if self._positioning_selection_complete():
                return self._selected_positioning_cards()
            return None
        if self.positioning_prev_button_rect.collidepoint(position):
            if self.positioning_page_index > 0:
                self.positioning_page_index -= 1
            return None
        if self.positioning_next_button_rect.collidepoint(position):
            if self.positioning_page_index + 1 < self.positioning_page_count:
                self.positioning_page_index += 1
            return None
        for deck_index, _card_id, rect in self._visible_positioning_entries():
            if rect.collidepoint(position):
                self._toggle_positioning_card(deck_index)
                break
        return None

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
                        if self._positioning_selection_complete():
                            return self._selected_positioning_cards()
                    if event.key == pygame.K_LEFT and self.positioning_page_index > 0:
                        self.positioning_page_index -= 1
                    if (
                        event.key == pygame.K_RIGHT
                        and self.positioning_page_index + 1 < self.positioning_page_count
                    ):
                        self.positioning_page_index += 1
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._handle_positioning_mouse_down(event.pos)
                    if result is not None:
                        return result

            self.draw()
            self.clock.tick(FPS)


class ReplicationSilverPage(SilverBlackPage):
    """Silver-only storage view used to choose a card for Replication."""

    def __init__(self, screen, font_path, silver_cards, lang_dict=None):
        super().__init__(
            screen,
            font_path,
            silver_cards,
            black_cards=[],
            gold_cards=[],
            lang_dict=lang_dict,
        )
        self.selected_index = None
        self.title_font = pygame.font.Font(self.font_path, 58)
        self.prompt_font = pygame.font.Font(self.font_path, 30)
        self.silver_rects = self._build_row_rects(
            CARD_ROW_SLOTS,
            y=335,
            gap=INVENTORY_ROW_GAP,
        )
        self.silver_label_surface = self.row_label_font.render(
            self._get_text("LifecycleSilver", "Серебряные карты"),
            True,
            PAPER_COLOR,
        )
        self.silver_label_rect = self.silver_label_surface.get_rect(
            midbottom=(self.panel_rect.centerx, self.silver_rects[0].top - 24)
        )
        self.confirm_button_rect = pygame.Rect(0, 0, 230, 70)
        self.confirm_button_rect.center = (
            self.panel_rect.centerx - 135,
            self.panel_rect.bottom - 125,
        )
        self.back_button_rect = pygame.Rect(0, 0, 230, 70)
        self.back_button_rect.center = (
            self.panel_rect.centerx + 135,
            self.panel_rect.bottom - 125,
        )

    def _silver_index_at(self, position):
        for index, rect in enumerate(self.silver_rects):
            if index < len(self.silver_cards) and rect.collidepoint(position):
                return index
        return None

    def _handle_mouse_down(self, position):
        if self.back_button_rect.collidepoint(position):
            return "back"
        if self.confirm_button_rect.collidepoint(position):
            if self.selected_index is not None:
                return self.silver_cards[self.selected_index]
            return None
        selected_index = self._silver_index_at(position)
        if selected_index is not None:
            self.selected_index = selected_index
        return None

    def _hovered_card(self, pos):
        index = self._silver_index_at(pos)
        if index is None:
            return None, None
        return self.silver_cards[index], "silver"

    def _draw_background(self):
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

    def _draw_centered_text(self, text, font, center, color=PAPER_COLOR):
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=center))

    def _draw_button(self, rect, label, enabled=True):
        hovered = enabled and rect.collidepoint(pygame.mouse.get_pos())
        color = BUTTON_HOVER_COLOR if hovered else BUTTON_COLOR
        if not enabled:
            color = (218, 210, 194)
        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        pygame.draw.rect(self.screen, PAPER_COLOR, rect, 3, border_radius=4)
        text_color = PAPER_COLOR if enabled else (145, 138, 130)
        self._draw_centered_text(label, self.continue_button_font, rect.center, text_color)

    def draw(self):
        self._draw_background()
        self._draw_centered_text(
            "Репликация",
            self.title_font,
            (self.panel_rect.centerx, self.panel_rect.y + 125),
        )
        self._draw_centered_text(
            "Выберите серебряную карту, которую хотите скопировать",
            self.prompt_font,
            (self.panel_rect.centerx, self.panel_rect.y + 190),
        )
        self.screen.blit(self.silver_label_surface, self.silver_label_rect)

        for index, rect in enumerate(self.silver_rects):
            self._draw_placeholder(rect, SILVER)
            if index < len(self.silver_cards):
                self._draw_card(self.silver_cards[index], rect)
            if index == self.selected_index:
                pygame.draw.rect(
                    self.screen,
                    GOLD,
                    rect.inflate(10, 10),
                    4,
                    border_radius=4,
                )

        self._draw_button(
            self.confirm_button_rect,
            "Выбрать",
            enabled=self.selected_index is not None,
        )
        self._draw_button(self.back_button_rect, "Назад")
        self._draw_card_tooltip()
        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None
                    if (
                        event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
                        and self.selected_index is not None
                    ):
                        return self.silver_cards[self.selected_index]
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._handle_mouse_down(event.pos)
                    if result == "back":
                        return None
                    if result is not None:
                        return result

            self.draw()
            self.clock.tick(FPS)
