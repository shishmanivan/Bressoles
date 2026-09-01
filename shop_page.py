import os
import sys

import pygame

import game_state
from card_catalog import CARD_IMAGE_BASE_IDS, MARKET_CARD_TURNS, PRICE_CARD_ACTIONS, get_card_image_base_id
from gameplay_card_rendering import (
    draw_bear_modifier_text,
    draw_bid_modifier_text,
    draw_preview_card_action,
    draw_preview_card_turns,
)
from round_page_assets import load_round_page_static_assets
from shared_utils import wrap_text
from shop_card_stats import record_shop_card_offers
from silver_black_page import ReplicationGoldPage, ReplicationSilverPage


SCREEN_WIDTH = 1680
SCREEN_HEIGHT = 1050
FPS = 60

PAPER_COLOR = (83, 76, 70)
BUTTON_COLOR = (238, 228, 205)
BUTTON_HOVER_COLOR = (248, 239, 216)
SOLD_COLOR = (78, 112, 82)
DISABLED_OVERLAY = (238, 228, 205, 170)
PANEL_SIZE = (1440, 900)
PANEL_POS = ((SCREEN_WIDTH - PANEL_SIZE[0]) // 2, (SCREEN_HEIGHT - PANEL_SIZE[1]) // 2)
GAMEPLAY_CARD_SIZE = (142, 244)

SPECIAL_ASSETS = {
    "delisting": ("Делистинг", os.path.join("Shop", "Delisting.png")),
    "trader": ("Трейдер", os.path.join("Shop", "Trader.png")),
    "profit": ("Прибыль", os.path.join("Shop", "Profit.png")),
    "underwriter": ("Андеррайтер", os.path.join("Shop", "Underwriter.png")),
    "bailout": ("Бейлаут", os.path.join("Shop", "Bailout.png")),
    "long": ("Лонг", os.path.join("Shop", "Long.png")),
    "derivative": ("Дериватив", os.path.join("Shop", "Derivative.png")),
    "junk_bond": ("Джанк-бонд", os.path.join("Shop", "Junk Bond.png")),
    "issuer": ("Эмитент", os.path.join("Shop", "Issuer.png")),
    "bank": ("Банк", os.path.join("Shop", "Bank.png")),
    "multibagger": ("Мультбэггер", os.path.join("Shop", "Multibagger.png")),
    "variance": ("Дисперсия", os.path.join("Shop", "Variance.png")),
    "loan": ("Ссуда", os.path.join("Shop", "Loan.png")),
    "correction": ("Коррекция", os.path.join("Shop", "Correction.png")),
    "diversification": ("Диверсификация", os.path.join("Shop", "Diversification.png")),
    "expansion": ("Экспансия", os.path.join("Shop", "Expansion.png")),
    "bill_of_exchange": (
        "Вексель",
        os.path.join("Shop", "Bill of Exchange.png"),
    ),
    "disclosure": ("Disclousure", os.path.join("Shop", "Disclousure.png")),
    "compounding": ("Compounding", os.path.join("Shop", "Compouding.png")),
    "replication": ("Репликация", os.path.join("Shop", "Replication.png")),
    "replication_plus": ("Репликация Плюс", os.path.join("Shop", "Replication+.png")),
    "screening": ("Скрининг", os.path.join("Shop", "Screening.png")),
    "capital_preservation": (
        "Сохранение капитала",
        os.path.join("Shop", "Capital Preservation.png"),
    ),
    "mirroring": ("Зеркалирование", os.path.join("Shop", "Mirroring.png")),
    "retention": ("Удержание", os.path.join("Shop", "Retention.png")),
    "deal_flow": ("Deal Flow", os.path.join("Shop", "Deal Flow.png")),
}

SPECIAL_DESCRIPTIONS = {
    "delisting": "Удаляет одну выбранную карту из колоды.",
    "trader": "Позволяет продать одну карту из колоды.",
    "profit": "Увеличивает награду за каждую следующую победу на 1 наполеондор.",
    "underwriter": "Даёт две разные случайные редкие серебряные карты.",
    "bailout": "Снижает цель следующих 5 раундов на 20%. Пока действует, не появляется в магазине.",
    "long": "Вложите 2 наполеондора сейчас и получите 6 наполеондоров через 4 раунда.",
    "derivative": "Увеличивает руку на одну карту до конца забега.",
    "junk_bond": "Вложите 2 наполеондора: 60% получить 6, 30% потерять ставку, 10% вернуть 2.",
    "issuer": "Открывает новый слот для чёрных, серебряных и золотых карт. Максимум 5 слотов.",
    "bank": "Начисляет 25% на остаток наполеондоров перед следующим магазином. Проценты кратны 0.5.",
    "multibagger": "Добавляет случайную золотую карту в текущем забеге.",
    "variance": "Усиливает все карты Upside и Downside на 1 процентный пункт до конца забега.",
    "loan": "Сразу даёт 5 наполеондоров, но повышает цели текущего босса на 20%.",
    "correction": "Позволяет продать до трёх карт: серебряные по 2, золотые по 4 наполеондора. Чёрные карты продать нельзя.",
    "diversification": "Увеличивает количество карт, предлагаемых в каждом следующем магазине, с одной до двух.",
    "expansion": "Добавляет ещё одно предложение в каждый следующий магазин.",
    "bill_of_exchange": "Сразу снижает цены в текущем магазине и до конца забега даёт скидку 25% на карты, предложения, лицензии и инвестиции. Цены округляются до 0,5 наполеондора.",
    "disclosure": "Показывает игровые вероятности в течение следующих 5 раундов.",
    "compounding": "Увеличивает каждое следующее усиление в разделе инвестиций с 1 до 2.",
    "replication": "Позволяет выбрать и скопировать одну имеющуюся серебряную карту, если в хранилище есть свободное место.",
    "replication_plus": "Позволяет выбрать и скопировать одну имеющуюся золотую карту, если в хранилище есть свободное место.",
    "screening": "Показывает пять случайных доступных предложений. Одно из них можно выбрать бесплатно.",
    "capital_preservation": "После поражения сохраняет все золотые карты и переносит их в следующий забег.",
    "mirroring": "Дублирует любую выбранную карту текущей колоды. Дубликат сохраняется после победы над боссом.",
    "retention": "После победы над текущим боссом позволяет сохранить одну временную карту для следующего босса.",
    "deal_flow": "Добавляет 10 процентных пунктов к вероятности появления редких золотых карт и предложений.",
}

INVESTMENT_ASSET = ("Инвестиции", os.path.join("Shop", "Investment.png"))
INVESTMENT_DESCRIPTION = (
    "Усиливает одну постоянную карту роста, падения, взлёта или снижения на {amount} до конца забега. "
    "Доступно одно усиление за магазин."
)

CARD_DESCRIPTIONS = {
    118: "Устанавливает цены всех акций на 10.",
    119: "Устанавливает цены всех акций на 20.",
    120: "Устанавливает цены всех акций на 30.",
    121: "Устанавливает цены всех акций на 50.",
    122: "Устанавливает цены всех акций на 100.",
    123: "Parity: устанавливает цены всех трёх акций на их среднее значение, округлённое до ближайшего целого.",
    124: "Accumulation: удваивает номинал и длительность следующей выложенной Gain/Drop-карты. Ожидание не ограничено по ходам, но усиление не переходит в следующий раунд.",
    125: "Breakout: на последнем игровом ходу даёт 50% шанс удвоить цены акций, которыми владеет игрок.",
    17: "Умножает цену выбранной акции на 2 на один ход.",
    18: "Умножает цену выбранной акции на 2 на два хода.",
    20: "Regulation: случайный рыночный бросок выбранной акции будет Flat 2 хода.",
    21: "Regulation: случайный рыночный бросок выбранной акции будет Flat 3 хода.",
    22: "Выбранные акции никогда не будут падать. Никакие карты не смогут опустить их цену. Всегда приходит в стартовой руке.",
    117: "Крах: после розыгрыша устанавливает цены всех акций на 2.",
    401: "Медведь: снижает цель на 2%. После каждой победы снижение увеличивается ещё на 2%.",
    402: "Форвардная торговля: каждый сыгранный Shareholder добавляет один ход.",
    403: "Грант: добавляет 8 к стартовым деньгам.",
    404: "Flat: отключает случайные падения и взлёты акций. Рыночный бросок всегда Flat.",
    405: "Insider: первые два хода акции C гарантированно растут.",
    406: "Gambling: усиливает карты Upside и Downside.",
    409: "Momentum: после случайного роста или падения акция повторяет то же движение ещё раз. Изменения цен от карт не учитываются.",
}

CARD_NAMES = {
    118: "BID 10",
    119: "BID 20",
    120: "BID 30",
    121: "BID 50",
    122: "BID 100",
    123: "Parity",
    124: "Accumulation",
    125: "Breakout",
    212: "Манипуляция",
    213: "Concentration",
    110: "Рибейт",
    111: "Снижение долга",
    112: "Ролловер",
    113: "Банкротство A",
    114: "Банкротство B",
    115: "Банкротство C",
    116: "Продление",
    201: "Рибейт",
    202: "Фьючерс",
    203: "Фьючерс",
    204: "Контанго",
    205: "Controlling Stake",
    206: "Корзинная торговля",
    207: "Форвардная торговля",
    208: "Ролловер",
    209: "Frugality",
    210: "Catalyst",
    211: "Short Seller",
    214: "Грант",
    215: "Вексель",
    217: "Облигация",
    218: "Облигация",
    219: "Облигация",
    220: "Страхование",
    17: "Рост",
    18: "Рост",
    20: "Regulation",
    21: "Regulation",
    22: "Blue Chips",
    117: "Крах",
    401: "Медведь",
    402: "Форвардная торговля",
    403: "Грант",
    404: "Flat",
    405: "Insider",
    406: "Gambling",
}

CARD_DESCRIPTIONS.update(
    {
        407: "Продаёт акции за 130% от их стоимости. Каждый раз, когда акции A падают, это число увеличивается ещё на 2%.",
        408: "Hedger: один раз за раунд позволяет взять любую карту из колоды в руку, если есть место.",
        410: "Добавляет к эффекту Rebate по 2% за каждый имеющийся наполеондор.",
        411: "На четвёртом ходу акции, которыми владеет игрок, гарантированно растут.",
        412: "На четвёртом и восьмом ходах акции, которыми владеет игрок, гарантированно растут.",
        413: "Удваивает вероятность падения акций, которыми игрок не владеет.",
        414: "Усиливает числовые процентные эффекты карт на 15 процентных пунктов.",
        415: "Если игрок четыре хода подряд ничего не покупает и не продаёт, в конце четвёртого такого хода цена акций A увеличивается в 3 раза.",
        416: "Даёт 5 наполеондоров если на на всех трёх рынках выпал Flat (цена не изменилась).",
        417: "Перед началом раунда позволяет выбрать 2 карты, которые гарантированно попадут в стартовую руку.",
        418: "Перед началом раунда позволяет выбрать 3 карты, которые гарантированно попадут в стартовую руку.",
        419: "После первого роста удерживаемой акции каждый следующий последовательный рост дополнительно умножает её цену на 1.2. Flat, падение или продажа акции прерывают её серию.",
        420: "С шансом 15% удваивает цены всех акций, которыми владеет игрок.",
        421: "В начале раунда устанавливает стартовую цену акций A на 6 долларов.",
        422: "Снижает цель третьего и четвёртого обычных раундов на 30%. В остальных раундах и боях с боссами не действует.",
        423: "Каждый Shareholder в руке добавляет 20 процентных пунктов к итоговому эффекту Rebate.",
        424: "Увеличивает шаг роста и падения каждого рынка на 2.",
        425: "Увеличивает шаг роста и падения каждого рынка на 4.",
        426: "После каждой победы над боссом добавляет 50 процентных пунктов к итоговому эффекту Rebate.",
        427: "Показывает игровые вероятности и немного усиливает все карты с вероятностями",
        428: "Даёт 7 наполеондоров, если все карты из колоды выложены на плейсхолдеры.",
        429: "Пока активна, убирает из игры все Upside и Downside, а также стартового Shareholder. Полученные позднее Shareholder остаются.",
        430: "С вероятностью 15% показывает следующий рыночный бросок и позволяет переиграть ход.",
        431: "Каждый начатый раунд H добавляет 10 процентных пунктов к итоговому эффекту Rebate.",
    }
)
CARD_NAMES.update(
    {
        407: "Rebate",
        408: "Hedger",
        409: "Momentum",
        410: "Uptrend",
        411: "Spoofing",
        412: "Spoofing+",
        413: "Shakeout",
        414: "Catalyst",
        415: "Surge",
        416: "Sideway",
        417: "Positioning",
        418: "Positioning+",
        419: "Continuation",
        420: "Advance",
        421: "Issue Price",
        422: "Markdown",
        423: "Stewardship",
        424: "Volatility",
        425: "Volatility+",
        426: "Windfall",
        427: "Disclosure",
        428: "Full Deployment",
        429: "Concentration",
        430: "Waterloo",
        431: "Risk Premium",
    }
)

LICENSE_EFFECT_DESCRIPTIONS = {
    123: "Устанавливает цены всех трёх акций на их среднее значение, округлённое до ближайшего целого.",
    124: "Удваивает номинал и количество ходов следующей выложенной Gain/Drop-карты. Действует, пока такая карта не будет выложена, но усиление не переходит в следующий раунд.",
    125: "Можно сыграть только на последнем игровом ходу. С шансом 50% удваивает цены акций, которыми владеет игрок.",
    212: "Если игрок владеет акциями C и цена C упала в этом ходу, сразу даёт 4 акции A.",
    213: "Пока активна, убирает из игры все Upside и Downside.",
    118: "Устанавливает цены всех акций на 10.",
    119: "Устанавливает цены всех акций на 20.",
    120: "Устанавливает цены всех акций на 30.",
    121: "Устанавливает цены всех акций на 50.",
    122: "Устанавливает цены всех акций на 100.",
    112: "Продлевает действие всех карт роста и падения на 1 ход, включая уже сыгранные.",
    113: "Устанавливает цену акций компании A на 2.",
    114: "Устанавливает цену акций компании B на 2.",
    115: "Устанавливает цену акций компании C на 2.",
    203: "Добавляет 2 хода к длительности раунда.",
    204: "Удваивает силу всех карт роста и падения. Несколько копий умножают эффект повторно.",
    205: "Контрольный пакет: акционеры больше не могут отключать кнопки торговли акциями.",
    207: "За каждые две сыгранные карты акционера добавляет 1 ход к раунду.",
    209: "Переносит все неиспользованные ходы в следующий раунд.",
    210: "Усиливает числовые процентные эффекты карт на 10 процентных пунктов.",
    211: "Если вы вложили все деньги в акции, которые упали 5 раз, вы сразу выигрываете. Не работает на боссах",
    214: "Добавляет 4 к стартовым деньгам в начале раунда.",
    215: "После победы снижает цены всех предложений в следующем магазине на 50%.",
    217: "После победы приносит дополнительно 5 наполеондоров.",
    218: "После победы приносит дополнительно 10 наполеондоров.",
    219: "После победы приносит дополнительно 15 наполеондоров.",
    220: "В обычном раунде превращает поражение в победу. Недостающая сумма добавляется к цели следующего обычного раунда. Не работает против боссов.",
}

SHOP_CARD_ACTIONS = dict(PRICE_CARD_ACTIONS)
SHOP_CARD_TURNS = dict(MARKET_CARD_TURNS)
DECK_CARD_BASES = dict(CARD_IMAGE_BASE_IDS)
DECK_CARD_ACTIONS = dict(PRICE_CARD_ACTIONS)
DECK_CARD_TURNS = dict(MARKET_CARD_TURNS)


def format_napoleondors(value):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.1f}".rstrip("0").rstrip(".")


class ShopPage:
    """Intermediate shop screen shown after a completed round."""

    def __init__(
        self,
        screen,
        font_path,
        level_number=1,
        napoleondors=0,
        lang_dict=None,
        discount_percent=0,
        stats_enabled=False,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_path = font_path
        self.level_number = int(level_number or 1)
        self.lang_dict = lang_dict or {}
        self.napoleondors = float(napoleondors or 0)
        self.discount_percent = max(0, min(100, int(discount_percent or 0)))
        self.offers = game_state.generate_shop_offers(
            level_number=self.level_number,
            discount_percent=self.discount_percent,
        )
        if stats_enabled:
            record_shop_card_offers(self.level_number, self.offers, CARD_NAMES)
        self.sold_offer_indexes = set()
        self.message = ""
        self.offer_image_cache = {}

        assets = load_round_page_static_assets()
        self.round_background = assets["background"]
        self.round_koordinates = assets["koordinates"]
        self.panel_rect = pygame.Rect(PANEL_POS, PANEL_SIZE)
        self.background = self._load_image(os.path.join("RoundPage", "SilverBlack.png"), PANEL_SIZE)
        self.coin_image = self._load_image(os.path.join("Shop", "Napoleondor.png"), (54, 54))
        self._coin_image_cache = {}
        if self.coin_image:
            self._coin_image_cache[self.coin_image.get_size()] = self.coin_image
        self._coin_text_cache = {}

        self.title_font = pygame.font.Font(font_path, 72)
        self.balance_font = pygame.font.Font(font_path, 48)
        self.small_font = pygame.font.Font(font_path, 30)
        self.button_font = pygame.font.Font(font_path, 42)
        self.button_rect = pygame.Rect(0, 0, 260, 86)
        self.button_rect.center = (self.panel_rect.centerx, self.panel_rect.bottom - 120)
        self.offer_image_box = (200, 296)
        self.card_offer_size = GAMEPLAY_CARD_SIZE
        self._offer_label_surface_cache = {}
        self.offer_rects = self._build_offer_rects()

    def _load_image(self, path, size=None):
        if not os.path.exists(path):
            print(f"WARNING: Shop asset not found: {path}")
            return None
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.smoothscale(image, size).convert_alpha()
        return image

    def _draw_centered_text(self, text, font, center, color=PAPER_COLOR):
        surface = font.render(str(text), True, color)
        rect = surface.get_rect(center=center)
        self.screen.blit(surface, rect)

    def _build_offer_rects(self):
        width = 176
        height = 380
        y = self.panel_rect.y + 265
        slot_gap = 22
        group_gap = 120
        groups = [
            ("card", [offer for offer in self.offers if offer.get("kind") == "card"]),
            ("special", [offer for offer in self.offers if offer.get("kind") == "special"]),
            ("license", [offer for offer in self.offers if offer.get("kind") == "license"]),
            ("investment", [offer for offer in self.offers if offer.get("kind") == "investment"]),
        ]
        groups = [(kind, offers) for kind, offers in groups if offers]
        offer_count = sum(len(offers) for _kind, offers in groups)
        if offer_count >= 8:
            width = 142
            slot_gap = 12
            group_gap = 50
            self.offer_image_box = (136, 296)
        elif offer_count >= 7:
            width = 158
            slot_gap = 16
            group_gap = 60
            self.offer_image_box = (150, 296)
        elif offer_count >= 6:
            group_gap = 80
        total_width = sum(len(offers) * width + max(0, len(offers) - 1) * slot_gap for _kind, offers in groups)
        total_width += max(0, len(groups) - 1) * group_gap
        x = self.panel_rect.centerx - total_width // 2
        rects = []
        self.category_rects = []
        for kind, offers in groups:
            group_width = len(offers) * width + max(0, len(offers) - 1) * slot_gap
            self.category_rects.append((kind, pygame.Rect(x, y - 54, group_width, 44)))
            for _offer in offers:
                rects.append(pygame.Rect(x, y, width, height))
                x += width + slot_gap
            x += group_gap - slot_gap
        return rects

    def _offer_label_surface(self, text, max_width):
        cache_key = (str(text), int(max_width))
        cached = self._offer_label_surface_cache.get(cache_key)
        if cached is not None:
            return cached
        for size in range(30, 17, -2):
            font = self.small_font if size == 30 else pygame.font.Font(self.font_path, size)
            surface = font.render(str(text), True, PAPER_COLOR)
            if surface.get_width() <= max_width or size == 18:
                self._offer_label_surface_cache[cache_key] = surface
                return surface

    def _offer_label(self, offer):
        if offer.get("kind") in ("card", "license"):
            card_id = int(offer.get("card_id", 0) or 0)
            name = CARD_NAMES.get(card_id, f"Карта {card_id}")
            if offer.get("kind") == "license":
                return name
            return name
        if offer.get("kind") == "investment":
            return INVESTMENT_ASSET[0]
        return SPECIAL_ASSETS.get(offer.get("special_id"), (str(offer.get("special_id")), None))[0]

    def _offer_image(self, offer):
        card_id = None
        if offer.get("kind") in ("card", "license"):
            card_id = int(offer.get("card_id", 0) or 0)
            path = os.path.join("Cards", f"Card_{get_card_image_base_id(card_id)}.png")
        elif offer.get("kind") == "investment":
            _label, path = INVESTMENT_ASSET
        else:
            _label, path = SPECIAL_ASSETS.get(offer.get("special_id"), ("", None))
            if not path:
                return None

        cache_key = (offer.get("kind"), card_id) if card_id is not None else ("special", path)
        if cache_key in self.offer_image_cache:
            return self.offer_image_cache[cache_key]
        image = self._load_image(path)
        if image:
            if card_id is not None:
                size = self.card_offer_size
            else:
                box_width, box_height = self.offer_image_box
                scale = min(box_width / image.get_width(), box_height / image.get_height())
                size = (
                    max(1, round(image.get_width() * scale)),
                    max(1, round(image.get_height() * scale)),
                )
            image = pygame.transform.smoothscale(image, size).convert_alpha()
            if card_id in SHOP_CARD_ACTIONS:
                draw_preview_card_action(
                    image,
                    SHOP_CARD_ACTIONS[card_id],
                    card_id,
                    size[0],
                    size[1],
                    self.font_path,
                    PAPER_COLOR,
                    adjust_mode="shop",
                )
            if card_id in SHOP_CARD_TURNS:
                draw_preview_card_turns(
                    image,
                    SHOP_CARD_TURNS[card_id],
                    card_id,
                    size[0],
                    size[1],
                    self.font_path,
                    PAPER_COLOR,
                )
            draw_bid_modifier_text(image, card_id, 0, 0, size, self.font_path)
            draw_bear_modifier_text(
                image,
                card_id,
                0,
                0,
                size,
                self.font_path,
                PAPER_COLOR,
                adjust_mode="shop",
            )
        self.offer_image_cache[cache_key] = image
        return image

    def _offer_description(self, offer):
        if offer.get("kind") == "license":
            card_id = int(offer.get("card_id", 0) or 0)
            card_name = CARD_NAMES.get(card_id, f"Карта {card_id}")
            effect_text = LICENSE_EFFECT_DESCRIPTIONS.get(
                card_id,
                "Добавляет эту карту в пул будущих забегов.",
            )
            return (
                f"Открывает карту {card_name}: теперь она может появляться "
                f"в следующих забегах. {effect_text}"
            )
        if offer.get("kind") == "card":
            card_id = int(offer.get("card_id", 0) or 0)
            description = CARD_DESCRIPTIONS.get(card_id, f"Добавляет карту {card_id} в вашу колоду.")
            if card_id == 431:
                description = (
                    f"{description} Текущий бонус карты: "
                    f"+{game_state.get_risk_premium_card_bonus_percent()}%."
                )
            return description
        if offer.get("kind") == "investment":
            return INVESTMENT_DESCRIPTION.format(
                amount=game_state.get_investment_upgrade_amount()
            )
        return SPECIAL_DESCRIPTIONS.get(offer.get("special_id"), "")

    def _draw_hover_description(self):
        offer_index = self._offer_at(pygame.mouse.get_pos())
        text = ""
        if offer_index is not None and offer_index not in self.sold_offer_indexes:
            text = self._offer_description(self.offers[offer_index])
        elif self.message:
            text = self.message
        if not text:
            return

        lines = wrap_text(text, self.small_font, 1080, color=PAPER_COLOR)
        line_height = self.small_font.get_linesize()
        center_y = self.panel_rect.bottom - 202
        start_y = center_y - ((len(lines) - 1) * line_height) // 2
        for line_index, line in enumerate(lines):
            self._draw_centered_text(
                line,
                self.small_font,
                (self.panel_rect.centerx, start_y + line_index * line_height),
            )

    def _draw_coin_amount(self, amount, center, font):
        amount_text = format_napoleondors(amount)
        text_key = (id(font), amount_text)
        text = self._coin_text_cache.get(text_key)
        if text is None:
            text = font.render(amount_text, True, PAPER_COLOR)
            self._coin_text_cache[text_key] = text
        coin_width = 0
        if self.coin_image:
            coin_width = 54 if font is self.balance_font else 30
        total_width = text.get_width() + (coin_width + 12 if coin_width else 0)
        start_x = center[0] - total_width // 2
        if self.coin_image:
            coin_size = (coin_width, coin_width)
            coin = self._coin_image_cache.get(coin_size)
            if coin is None:
                coin = pygame.transform.smoothscale(self.coin_image, coin_size).convert_alpha()
                self._coin_image_cache[coin_size] = coin
            coin_rect = coin.get_rect(midleft=(start_x, center[1]))
            self.screen.blit(coin, coin_rect.topleft)
            start_x = coin_rect.right + 12
        self.screen.blit(text, text.get_rect(midleft=(start_x, center[1])))

    def _draw_offer(self, index, offer, rect):
        image = self._offer_image(offer)
        image_rect = image.get_rect() if image else pygame.Rect(0, 0, *self.offer_image_box)
        image_rect.center = (rect.centerx, rect.y + 148)
        if image:
            self.screen.blit(image, image_rect.topleft)

        label = self._offer_label_surface(self._offer_label(offer), rect.width + 12)
        self.screen.blit(label, label.get_rect(center=(rect.centerx, rect.y + 318)))
        self._draw_coin_amount(offer.get("cost", 0), (rect.centerx, rect.y + 360), self.small_font)

        if index in self.sold_offer_indexes:
            overlay = pygame.Surface(image_rect.size, pygame.SRCALPHA)
            overlay.fill((238, 228, 205, 190))
            self.screen.blit(overlay, image_rect.topleft)
            sold = self.small_font.render("Куплено", True, SOLD_COLOR)
            self.screen.blit(sold, sold.get_rect(center=image_rect.center))

    def _offer_at(self, pos):
        for index, rect in enumerate(self.offer_rects):
            if index < len(self.offers) and rect.collidepoint(pos):
                return index
        return None

    def _sync_balance(self):
        self.napoleondors = float(game_state.napoleondors or 0)

    def _refresh_current_shop_prices(self):
        temporary_discount = getattr(self, "discount_percent", 0)
        for index, offer in enumerate(self.offers):
            if index in self.sold_offer_indexes:
                continue
            base_cost = game_state.get_shop_offer_base_cost(offer, self.level_number)
            offer["cost"] = game_state.get_discounted_shop_price(
                base_cost,
                temporary_discount,
            )

    def _activate_free_special_offer(self, special_id):
        temporary_index = len(self.offers)
        self.offers.append(
            {"kind": "special", "special_id": special_id, "cost": 0}
        )
        try:
            self._buy_offer(temporary_index)
            return temporary_index in self.sold_offer_indexes
        finally:
            self.sold_offer_indexes.discard(temporary_index)
            self.offers.pop()

    def _buy_offer(self, index):
        if index in self.sold_offer_indexes or index >= len(self.offers):
            return
        offer = self.offers[index]
        cost = float(offer.get("cost", 0) or 0)
        if game_state.napoleondors < cost:
            self.message = "Недостаточно монет"
            return

        if offer.get("kind") == "card":
            card_id = int(offer.get("card_id", 0) or 0)
            if game_state.is_shop_card_already_bought(card_id):
                self.message = "Карта уже куплена"
                self.sold_offer_indexes.add(index)
                return
            added = game_state.add_shop_card_to_level(self.level_number, card_id)
            if added is None:
                self.message = "Нет места для карты"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Карта куплена"
            return

        if offer.get("kind") == "license":
            card_id = int(offer.get("card_id", 0) or 0)
            if game_state.is_card_licensed(card_id):
                self.message = "Лицензия уже куплена"
                self.sold_offer_indexes.add(index)
                return
            if not game_state.unlock_card_license(card_id):
                self.message = "Лицензия уже куплена"
                self.sold_offer_indexes.add(index)
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = f"Лицензия куплена: {CARD_NAMES.get(card_id, f'Карта {card_id}')}"
            return

        if offer.get("kind") == "investment":
            selected_card = InvestmentDeckPage(self.screen, self.font_path, self.level_number).run()
            if selected_card is None:
                self.message = ""
                return
            if game_state.invest_gain_drop_card(selected_card, self.level_number):
                game_state.spend_napoleondors(cost)
                self._sync_balance()
                self.sold_offer_indexes.add(index)
                amount = game_state.get_investment_upgrade_amount()
                self.message = "Карта усилена" if amount == 1 else f"Карта усилена на {amount}"
            return

        special_id = offer.get("special_id")
        if special_id == "delisting":
            selected_card = DelistingDeckPage(self.screen, self.font_path, self.level_number).run()
            if selected_card is None:
                self.message = ""
                return
            if game_state.remove_card_from_level_deck(self.level_number, selected_card):
                game_state.spend_napoleondors(cost)
                self._sync_balance()
                self.sold_offer_indexes.add(index)
                self.message = "Карта удалена"
            return

        if special_id == "trader":
            selected_card = TraderDeckPage(self.screen, self.font_path, self.level_number).run()
            if selected_card is None:
                self.message = ""
                return
            total_value, sold_cards = game_state.sell_cards_from_level_deck(
                self.level_number,
                [selected_card],
            )
            if sold_cards:
                self._sync_balance()
                self.sold_offer_indexes.add(index)
                self.message = f"Продано: {format_napoleondors(total_value)}"
            return

        if special_id == "profit":
            game_state.spend_napoleondors(cost)
            game_state.buy_profit_bonus()
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Премия увеличена"
            return

        if special_id == "underwriter":
            received_cards = game_state.buy_underwriter_cards(level_number=self.level_number)
            if not received_cards:
                self.message = "Нужно два свободных места"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            cards_text = ", ".join(str(card_id) for card_id in received_cards)
            self.message = f"Получены карты: {cards_text}"
            return

        if special_id == "bailout":
            game_state.spend_napoleondors(cost)
            game_state.buy_bailout()
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Bailout активирован на 5 раундов"
            return

        if special_id == "long":
            if not game_state.is_long_offer_available():
                self.message = "Уже активны два Long"
                self.sold_offer_indexes.add(index)
                return
            if not game_state.buy_long_investment():
                self.message = "Уже активны два Long"
                self.sold_offer_indexes.add(index)
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Long активирован"
            return

        if special_id == "junk_bond":
            game_state.spend_napoleondors(cost)
            outcome = game_state.resolve_junk_bond(self.level_number)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = {
                "win": "Ваша ставка сыграла",
                "refund": "Ставка возвращена",
            }.get(outcome, "Не повезло")
            return

        if special_id == "issuer":
            new_slot_limit = game_state.buy_issuer_slot()
            if new_slot_limit is None:
                self.sold_offer_indexes.add(index)
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = f"Открыто слотов: {new_slot_limit}"
            return

        if special_id == "bank":
            if not game_state.buy_bank_offer():
                self.sold_offer_indexes.add(index)
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Банк открыт"
            return

        if special_id == "multibagger":
            awarded_card = game_state.buy_multibagger_gold_card(self.level_number)
            if awarded_card is None:
                self.message = "Нет доступных золотых карт"
                self.sold_offer_indexes.add(index)
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Карта добавлена"
            return

        if special_id == "variance":
            game_state.spend_napoleondors(cost)
            game_state.buy_variance_offer(1)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Все карты усилены на 1%"
            return

        if special_id == "deal_flow":
            game_state.spend_napoleondors(cost)
            bonus = game_state.buy_deal_flow()
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = f"Шанс редких карт и предложений увеличен на {bonus}%"
            return

        if special_id == "diversification":
            if not game_state.buy_diversification():
                self.sold_offer_indexes.add(index)
                self.message = "Диверсификация уже куплена"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "В магазине теперь предлагаются две карты"
            return

        if special_id == "expansion":
            if not game_state.buy_expansion():
                self.sold_offer_indexes.add(index)
                self.message = "Экспансия уже куплена"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "В магазине теперь больше предложений"
            return

        if special_id == "bill_of_exchange":
            if not game_state.buy_bill_of_exchange_offer():
                self.sold_offer_indexes.add(index)
                self.message = "Вексель уже куплен"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self._refresh_current_shop_prices()
            self.message = "Цены снижены на 25%"
            return

        if special_id == "disclosure":
            if not game_state.buy_disclosure():
                self.sold_offer_indexes.add(index)
                self.message = "Disclousure уже действует"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Вероятности открыты на 5 раундов"
            return

        if special_id == "compounding":
            if not game_state.buy_compounding(self.level_number):
                self.sold_offer_indexes.add(index)
                self.message = "Compounding уже куплен"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Инвестиции теперь усиливают карты на 2"
            return

        if special_id == "replication":
            if not game_state.is_replication_offer_available():
                self.sold_offer_indexes.add(index)
                self.message = "Нет серебряной карты или свободного места"
                return
            selected_card = ReplicationSilverPage(
                self.screen,
                self.font_path,
                game_state.silver_cards,
                lang_dict=getattr(self, "lang_dict", None),
            ).run()
            if selected_card is None:
                self.message = ""
                return
            if game_state.buy_replication_card(selected_card) is None:
                self.message = "Карта недоступна"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Серебряная карта добавлена"
            return

        if special_id == "replication_plus":
            if not game_state.is_replication_plus_offer_available():
                self.sold_offer_indexes.add(index)
                self.message = "Нет золотой карты или свободного места"
                return
            selected_card = ReplicationGoldPage(
                self.screen,
                self.font_path,
                game_state.gold_cards,
                lang_dict=getattr(self, "lang_dict", None),
            ).run()
            if selected_card is None:
                self.message = ""
                return
            if game_state.buy_replication_plus_card(selected_card) is None:
                self.message = "Карта недоступна"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Золотая карта добавлена"
            return

        if special_id == "mirroring":
            if not game_state.is_mirroring_offer_available(self.level_number):
                self.sold_offer_indexes.add(index)
                self.message = "Зеркалирование больше недоступно"
                return
            selected_card = MirroringDeckPage(
                self.screen,
                self.font_path,
                self.level_number,
            ).run()
            if selected_card is None:
                self.message = ""
                return
            if game_state.buy_mirroring_card(self.level_number, selected_card) is None:
                self.message = "Карта недоступна"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Карта продублирована"
            return

        if special_id == "retention":
            if not game_state.buy_retention():
                self.sold_offer_indexes.add(index)
                self.message = "Удержание уже активно"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Удержание активно до победы над боссом"
            return

        if special_id == "screening":
            choices = game_state.build_screening_offer_pool(
                self.level_number,
                offer_count=5,
            )
            if len(choices) < 5:
                self.sold_offer_indexes.add(index)
                self.message = "Недостаточно доступных предложений"
                return
            selected_offer = ScreeningOfferPage(
                self.screen,
                self.font_path,
                self.level_number,
                choices,
            ).run()
            if selected_offer is None:
                self.message = ""
                return
            if not self._activate_free_special_offer(selected_offer):
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            return

        if special_id == "capital_preservation":
            if not game_state.buy_capital_preservation():
                self.sold_offer_indexes.add(index)
                self.message = "Сохранение капитала уже куплено"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Золотые карты защищены"
            return

        if special_id == "loan":
            if not game_state.buy_loan(self.level_number):
                self.sold_offer_indexes.add(index)
                self.message = "Ссуда недоступна"
                return
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Получено 5 наполеондоров"
            return

        if special_id == "correction":
            selected_cards = CorrectionDeckPage(self.screen, self.font_path, self.level_number).run()
            if not selected_cards:
                self.message = ""
                return
            sale_value, sold_cards = game_state.sell_correction_cards(
                self.level_number,
                selected_cards,
            )
            if not sold_cards:
                self.message = "Карта недоступна"
                return
            game_state.spend_napoleondors(cost)
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = (
                f"Продано карт: {len(sold_cards)} на сумму "
                f"{format_napoleondors(sale_value)}"
            )
            return

        if special_id == "derivative":
            if not game_state.is_derivative_offer_available():
                self.sold_offer_indexes.add(index)
                return
            game_state.spend_napoleondors(cost)
            if game_state.buy_derivative_hand_bonus() is None:
                self._sync_balance()
                self.sold_offer_indexes.add(index)
                return
            self._sync_balance()
            self.sold_offer_indexes.add(index)
            self.message = "Дериватив увеличил руку"
            return

        self.message = "Скоро"

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

        self._draw_centered_text("Магазин", self.title_font, (self.panel_rect.centerx, self.panel_rect.y + 145))
        self._draw_coin_amount(self.napoleondors, (self.panel_rect.right - 170, self.panel_rect.y + 150), self.balance_font)

        category_labels = {
            "card": "Карты",
            "special": "Предложения",
            "license": "Лицензии",
            "investment": "Инвестиции",
        }
        for kind, rect in getattr(self, "category_rects", []):
            self._draw_centered_text(category_labels.get(kind, kind.title()), self.small_font, rect.center)

        for index, offer in enumerate(self.offers):
            self._draw_offer(index, offer, self.offer_rects[index])
        self._draw_hover_description()

        mouse_pos = pygame.mouse.get_pos()
        button_color = BUTTON_HOVER_COLOR if self.button_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, button_color, self.button_rect, border_radius=8)
        pygame.draw.rect(self.screen, PAPER_COLOR, self.button_rect, 3, border_radius=8)
        self._draw_centered_text("Дальше", self.button_font, self.button_rect.center)

        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        return "next"
                    if event.key == pygame.K_ESCAPE:
                        return "next"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.button_rect.collidepoint(event.pos):
                        return "next"
                    offer_index = self._offer_at(event.pos)
                    if offer_index is not None:
                        self._buy_offer(offer_index)

            self.draw()
            self.clock.tick(FPS)


class ScreeningOfferPage(ShopPage):
    """Five-offer choice screen opened after buying Screening."""

    def __init__(self, screen, font_path, level_number, special_ids):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_path = font_path
        self.level_number = int(level_number or 1)
        self.offers = [
            {
                "kind": "special",
                "special_id": special_id,
                "cost": 0,
            }
            for special_id in list(special_ids or [])[:5]
        ]
        self.selected_index = None
        self.offer_image_cache = {}
        self._offer_label_surface_cache = {}
        self.offer_image_box = (176, 296)
        self.card_offer_size = GAMEPLAY_CARD_SIZE

        assets = load_round_page_static_assets()
        self.round_background = assets["background"]
        self.round_koordinates = assets["koordinates"]
        self.panel_rect = pygame.Rect(PANEL_POS, PANEL_SIZE)
        self.background = self._load_image(
            os.path.join("RoundPage", "SilverBlack.png"),
            PANEL_SIZE,
        )
        self.title_font = pygame.font.Font(font_path, 58)
        self.small_font = pygame.font.Font(font_path, 27)
        self.button_font = pygame.font.Font(font_path, 34)

        width = 176
        gap = 34
        total_width = len(self.offers) * width + max(0, len(self.offers) - 1) * gap
        start_x = self.panel_rect.centerx - total_width // 2
        y = self.panel_rect.y + 235
        self.offer_rects = [
            pygame.Rect(start_x + index * (width + gap), y, width, 380)
            for index in range(len(self.offers))
        ]
        self.confirm_rect = pygame.Rect(0, 0, 230, 70)
        self.confirm_rect.center = (
            self.panel_rect.centerx - 135,
            self.panel_rect.bottom - 90,
        )
        self.back_rect = pygame.Rect(0, 0, 230, 70)
        self.back_rect.center = (
            self.panel_rect.centerx + 135,
            self.panel_rect.bottom - 90,
        )

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

    def _draw_button(self, rect, label, enabled=True):
        hovered = enabled and rect.collidepoint(pygame.mouse.get_pos())
        color = BUTTON_HOVER_COLOR if hovered else BUTTON_COLOR
        if not enabled:
            color = (218, 210, 194)
        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        pygame.draw.rect(self.screen, PAPER_COLOR, rect, 3, border_radius=4)
        text_color = PAPER_COLOR if enabled else (145, 138, 130)
        self._draw_centered_text(label, self.button_font, rect.center, text_color)

    def _draw_choice(self, index, offer, rect):
        image = self._offer_image(offer)
        image_rect = image.get_rect() if image else pygame.Rect(0, 0, *self.offer_image_box)
        image_rect.center = (rect.centerx, rect.y + 148)
        if image:
            self.screen.blit(image, image_rect.topleft)
        label = self._offer_label_surface(self._offer_label(offer), rect.width + 12)
        self.screen.blit(label, label.get_rect(center=(rect.centerx, rect.y + 318)))
        self._draw_centered_text("Бесплатно", self.small_font, (rect.centerx, rect.y + 360))
        if index == self.selected_index:
            pygame.draw.rect(
                self.screen,
                (184, 134, 11),
                image_rect.inflate(10, 10),
                4,
                border_radius=4,
            )

    def _handle_mouse_down(self, position):
        if self.back_rect.collidepoint(position):
            return "back"
        if self.confirm_rect.collidepoint(position):
            if self.selected_index is not None:
                return self.offers[self.selected_index]["special_id"]
            return None
        selected_index = self._offer_at(position)
        if selected_index is not None:
            self.selected_index = selected_index
        return None

    def draw(self):
        self._draw_background()
        self._draw_centered_text(
            "Скрининг",
            self.title_font,
            (self.panel_rect.centerx, self.panel_rect.y + 100),
        )
        self._draw_centered_text(
            "Выберите одно бесплатное предложение",
            self.small_font,
            (self.panel_rect.centerx, self.panel_rect.y + 165),
        )
        for index, offer in enumerate(self.offers):
            self._draw_choice(index, offer, self.offer_rects[index])

        hover_index = self._offer_at(pygame.mouse.get_pos())
        description_index = hover_index if hover_index is not None else self.selected_index
        if description_index is not None:
            description = self._offer_description(self.offers[description_index])
            lines = wrap_text(description, self.small_font, 1080, color=PAPER_COLOR)
            line_height = self.small_font.get_linesize()
            center_y = self.panel_rect.bottom - 185
            start_y = center_y - ((len(lines) - 1) * line_height) // 2
            for line_index, line in enumerate(lines):
                self._draw_centered_text(
                    line,
                    self.small_font,
                    (self.panel_rect.centerx, start_y + line_index * line_height),
                )

        self._draw_button(
            self.confirm_rect,
            "Выбрать",
            enabled=self.selected_index is not None,
        )
        self._draw_button(self.back_rect, "Назад")
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
                        return self.offers[self.selected_index]["special_id"]
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._handle_mouse_down(event.pos)
                    if result == "back":
                        return None
                    if result is not None:
                        return result

            self.draw()
            self.clock.tick(FPS)


class DeckCardPage:
    title = ""
    prompt = ""
    empty_text = ""
    confirm_text = ""
    cancel_text = "Отмена"
    back_text = "Назад"
    allow_back = True

    def __init__(self, screen, font_path, level_number, deck=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_path = font_path
        self.level_number = int(level_number or 1)
        self.deck = list(deck if deck is not None else game_state.build_permanent_level_deck(self.level_number))
        assets = load_round_page_static_assets()
        self.round_background = assets["background"]
        self.round_koordinates = assets["koordinates"]
        self.panel_rect = pygame.Rect(PANEL_POS, PANEL_SIZE)
        self.background = self._load_image(os.path.join("RoundPage", "SilverBlack.png"), PANEL_SIZE)
        self.title_font = pygame.font.Font(font_path, 58)
        self.button_font = pygame.font.Font(font_path, 34)
        self.small_font = pygame.font.Font(font_path, 26)
        self.card_size = getattr(self, "card_size_override", GAMEPLAY_CARD_SIZE)
        self.card_image_cache = {}
        self.selected_index = None
        self.confirming = False
        self.card_rects = self._build_card_rects()
        self.confirm_rect = pygame.Rect(self.panel_rect.centerx - 220, self.panel_rect.bottom - 130, 190, 70)
        self.cancel_rect = pygame.Rect(self.panel_rect.centerx + 30, self.panel_rect.bottom - 130, 190, 70)

    def _load_image(self, path, size=None):
        if not os.path.exists(path):
            print(f"WARNING: Shop asset not found: {path}")
            return None
        image = pygame.image.load(path).convert_alpha()
        if size:
            image = pygame.transform.smoothscale(image, size).convert_alpha()
        return image

    def _build_card_rects(self):
        columns = 8
        gap_x = 34
        gap_y = 34
        total_width = columns * self.card_size[0] + (columns - 1) * gap_x
        start_x = self.panel_rect.centerx - total_width // 2
        start_y = self.panel_rect.y + 210
        rects = []
        for index, _card_id in enumerate(self.deck):
            row = index // columns
            col = index % columns
            rects.append(
                pygame.Rect(
                    start_x + col * (self.card_size[0] + gap_x),
                    start_y + row * (self.card_size[1] + gap_y),
                    *self.card_size,
                )
            )
        return rects

    def _draw_centered_text(self, text, font, center, color=PAPER_COLOR):
        surface = font.render(str(text), True, color)
        self.screen.blit(surface, surface.get_rect(center=center))

    def _draw_button(self, rect, text):
        color = BUTTON_HOVER_COLOR if rect.collidepoint(pygame.mouse.get_pos()) else BUTTON_COLOR
        pygame.draw.rect(self.screen, color, rect, border_radius=8)
        pygame.draw.rect(self.screen, PAPER_COLOR, rect, 3, border_radius=8)
        self._draw_centered_text(text, self.button_font, rect.center)

    def _card_image(self, card_id):
        try:
            normalized = int(card_id)
        except (TypeError, ValueError):
            return None
        investment_bonus = game_state.get_investment_bonus(normalized)
        cache_key = (normalized, investment_bonus)
        if cache_key in self.card_image_cache:
            return self.card_image_cache[cache_key]

        base_card_id = DECK_CARD_BASES.get(normalized, normalized)
        image = self._load_image(os.path.join("Cards", f"Card_{base_card_id}.png"), self.card_size)
        if image:
            draw_bid_modifier_text(image, normalized, 0, 0, self.card_size, self.font_path)
        if image and normalized in DECK_CARD_ACTIONS:
            action_value = DECK_CARD_ACTIONS[normalized]
            if investment_bonus > 0:
                action_value = (
                    action_value - investment_bonus
                    if action_value < 0
                    else action_value + investment_bonus
                )
            draw_preview_card_action(
                image,
                action_value,
                normalized,
                self.card_size[0],
                self.card_size[1],
                self.font_path,
                PAPER_COLOR,
            )
        if image and normalized in DECK_CARD_TURNS:
            draw_preview_card_turns(
                image,
                DECK_CARD_TURNS[normalized],
                normalized,
                self.card_size[0],
                self.card_size[1],
                self.font_path,
                PAPER_COLOR,
            )

        self.card_image_cache[cache_key] = image
        return image

    def _card_at(self, pos):
        for index, rect in enumerate(self.card_rects):
            if index < len(self.deck) and rect.collidepoint(pos):
                return index
        return None

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

    def draw(self):
        self._draw_background()
        self._draw_centered_text(self.title, self.title_font, (self.panel_rect.centerx, self.panel_rect.y + 120))
        self._draw_centered_text(self.prompt, self.button_font, (self.panel_rect.centerx, self.panel_rect.y + 175))
        if not self.deck:
            self._draw_centered_text(self.empty_text, self.button_font, (self.panel_rect.centerx, self.panel_rect.centery))

        for index, card_id in enumerate(self.deck):
            rect = self.card_rects[index]
            image = self._card_image(card_id)
            if image:
                self.screen.blit(image, rect.topleft)
            else:
                pygame.draw.rect(self.screen, BUTTON_COLOR, rect)
                pygame.draw.rect(self.screen, PAPER_COLOR, rect, 2)
            if index == self.selected_index:
                pygame.draw.rect(self.screen, (184, 134, 11), rect.inflate(10, 10), 4, border_radius=4)

        if self.confirming and self.selected_index is not None:
            selected_card = self.deck[self.selected_index]
            self._draw_centered_text(
                self.confirm_message(selected_card),
                self.button_font,
                (self.panel_rect.centerx, self.panel_rect.bottom - 185),
            )
            self._draw_button(self.confirm_rect, self.confirm_text)
            self._draw_button(self.cancel_rect, self.cancel_text)
        elif self.allow_back:
            self._draw_button(self.cancel_rect, self.back_text)

        pygame.display.flip()

    def confirm_message(self, card_id):
        return f"Карта {card_id}?"

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.allow_back:
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.confirming:
                        if self.confirm_rect.collidepoint(event.pos) and self.selected_index is not None:
                            return self.deck[self.selected_index]
                        if self.cancel_rect.collidepoint(event.pos):
                            self.confirming = False
                            continue
                    elif self.allow_back and self.cancel_rect.collidepoint(event.pos):
                        return None

                    card_index = self._card_at(event.pos)
                    if card_index is not None:
                        self.selected_index = card_index
                        self.confirming = True

            self.draw()
            self.clock.tick(FPS)


class DelistingDeckPage(DeckCardPage):
    title = "Делистинг"
    prompt = "Выберите карту для удаления"
    empty_text = "В колоде нет карт"
    confirm_text = "Удалить"

    def confirm_message(self, card_id):
        return f"Удалить карту {card_id}?"


class MirroringDeckPage(DeckCardPage):
    title = "Зеркалирование"
    prompt = "Выберите карту для дублирования"
    empty_text = "В колоде нет доступных карт"
    confirm_text = "Дублировать"

    def __init__(self, screen, font_path, level_number):
        super().__init__(
            screen,
            font_path,
            level_number,
            deck=game_state.build_current_level_deck(level_number),
        )

    def confirm_message(self, card_id):
        return f"Дублировать карту {int(card_id)}?"


class RetentionDeckPage(DeckCardPage):
    title = "Удержание"
    prompt = "Выберите временную карту для следующего босса"
    empty_text = "Нет временных карт"
    confirm_text = "Сохранить"
    cancel_text = "Выбрать другую"
    allow_back = False

    def __init__(self, screen, font_path, cards):
        if len(cards) > 8:
            self.card_size_override = (116, 200)
        super().__init__(screen, font_path, level_number=1, deck=cards)

    def confirm_message(self, card_id):
        return f"Сохранить карту {int(card_id)}?"


class InvestmentDeckPage(DeckCardPage):
    title = "Инвестиции"
    prompt = "Выберите карту роста, падения, взлёта или снижения"
    empty_text = "В постоянной колоде нет доступных карт"
    confirm_text = "Усилить"

    def __init__(self, screen, font_path, level_number):
        super().__init__(
            screen,
            font_path,
            level_number,
            deck=game_state.get_current_gain_drop_deck_cards(level_number),
        )

    def draw(self):
        super().draw()
        for index, card_id in enumerate(self.deck):
            bonus = game_state.get_investment_bonus(card_id)
            if bonus <= 0 or index >= len(self.card_rects):
                continue
            rect = self.card_rects[index]
            bonus_surface = self.button_font.render(f"+{bonus}", True, (184, 134, 11))
            self.screen.blit(bonus_surface, bonus_surface.get_rect(center=(rect.right - 22, rect.y + 24)))
        pygame.display.flip()

    def confirm_message(self, card_id):
        return f"Усилить карту {card_id}?"


class TraderDeckPage(DeckCardPage):
    title = "Трейдер"
    card_size_override = (122, 211)
    sale_label_height = 30
    prompt = "Выберите одну карту для продажи"
    empty_text = "В колоде нет карт для продажи"
    confirm_text = "Продать"

    def _sale_value(self, card_id):
        return game_state.get_card_sale_value(card_id)

    def _is_sellable(self, card_id):
        return self._sale_value(card_id) is not None

    def _card_at(self, pos):
        for index, rect in enumerate(self.card_rects):
            if index >= len(self.deck):
                continue
            hit_rect = rect.copy()
            hit_rect.height += self.sale_label_height + 2
            if hit_rect.collidepoint(pos):
                return index
        return None

    def draw(self):
        self._draw_background()
        self._draw_centered_text(self.title, self.title_font, (self.panel_rect.centerx, self.panel_rect.y + 120))
        self._draw_centered_text(self.prompt, self.button_font, (self.panel_rect.centerx, self.panel_rect.y + 175))

        for index, card_id in enumerate(self.deck):
            rect = self.card_rects[index]
            image = self._card_image(card_id)
            if image:
                self.screen.blit(image, rect.topleft)
            else:
                pygame.draw.rect(self.screen, BUTTON_COLOR, rect)
                pygame.draw.rect(self.screen, PAPER_COLOR, rect, 2)

            sale_value = self._sale_value(card_id)
            if sale_value is None:
                overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                overlay.fill(DISABLED_OVERLAY)
                self.screen.blit(overlay, rect.topleft)
                locked = self.small_font.render("Нельзя", True, PAPER_COLOR)
                self.screen.blit(locked, locked.get_rect(center=rect.center))
            else:
                price = self.small_font.render(format_napoleondors(sale_value), True, PAPER_COLOR)
                label_rect = pygame.Rect(rect.x, rect.bottom + 2, rect.width, self.sale_label_height)
                pygame.draw.rect(self.screen, BUTTON_COLOR, label_rect)
                self.screen.blit(price, price.get_rect(center=label_rect.center))

            if index == self.selected_index:
                selected_rect = pygame.Rect(rect.x, rect.y, rect.width, rect.height + self.sale_label_height + 2)
                pygame.draw.rect(self.screen, (184, 134, 11), selected_rect.inflate(10, 10), 4, border_radius=4)

        if self.confirming and self.selected_index is not None:
            sale_value = self._sale_value(self.deck[self.selected_index])
            self._draw_centered_text(
                f"Продать карту за {format_napoleondors(sale_value)}?",
                self.button_font,
                (self.panel_rect.centerx, self.panel_rect.bottom - 185),
            )
            self._draw_button(self.confirm_rect, self.confirm_text)
            self._draw_button(self.cancel_rect, self.cancel_text)
        else:
            self._draw_button(self.cancel_rect, self.back_text)

        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.confirming:
                        if self.confirm_rect.collidepoint(event.pos) and self.selected_index is not None:
                            return self.deck[self.selected_index]
                        if self.cancel_rect.collidepoint(event.pos):
                            self.selected_index = None
                            self.confirming = False
                            continue
                    elif self.cancel_rect.collidepoint(event.pos):
                        return None

                    card_index = self._card_at(event.pos)
                    if card_index is None or not self._is_sellable(self.deck[card_index]):
                        continue
                    self.selected_index = card_index
                    self.confirming = True

            self.draw()
            self.clock.tick(FPS)


class CorrectionDeckPage(TraderDeckPage):
    title = "Коррекция"
    prompt = "Выберите до трёх серебряных или золотых карт"
    empty_text = "Нет серебряных или золотых карт для продажи"

    def __init__(self, screen, font_path, level_number):
        deck = (
            [("silver", card_id) for card_id in game_state.silver_cards]
            + [("gold", card_id) for card_id in game_state.gold_cards]
        )
        super().__init__(screen, font_path, level_number, deck=deck)
        self.selected_indices = []

    def _card_image(self, entry):
        return super()._card_image(entry[1])

    def _sale_value(self, entry):
        kind = entry[0]
        if kind == "silver":
            return game_state.CORRECTION_SILVER_SALE_VALUE
        if kind == "gold":
            return game_state.CORRECTION_GOLD_SALE_VALUE
        return None

    def _selected_sale_value(self):
        return sum(self._sale_value(self.deck[index]) or 0 for index in self.selected_indices)

    def draw(self):
        self._draw_background()
        self._draw_centered_text(self.title, self.title_font, (self.panel_rect.centerx, self.panel_rect.y + 120))
        self._draw_centered_text(self.prompt, self.button_font, (self.panel_rect.centerx, self.panel_rect.y + 175))
        if not self.deck:
            self._draw_centered_text(self.empty_text, self.button_font, (self.panel_rect.centerx, self.panel_rect.centery))

        for index, entry in enumerate(self.deck):
            rect = self.card_rects[index]
            image = self._card_image(entry)
            if image:
                self.screen.blit(image, rect.topleft)
            else:
                pygame.draw.rect(self.screen, BUTTON_COLOR, rect)
                pygame.draw.rect(self.screen, PAPER_COLOR, rect, 2)

            sale_value = self._sale_value(entry)
            price = self.small_font.render(format_napoleondors(sale_value), True, PAPER_COLOR)
            label_rect = pygame.Rect(rect.x, rect.bottom + 2, rect.width, self.sale_label_height)
            pygame.draw.rect(self.screen, BUTTON_COLOR, label_rect)
            self.screen.blit(price, price.get_rect(center=label_rect.center))

            if index in self.selected_indices:
                selected_rect = pygame.Rect(rect.x, rect.y, rect.width, rect.height + self.sale_label_height + 2)
                pygame.draw.rect(self.screen, (184, 134, 11), selected_rect.inflate(10, 10), 4, border_radius=4)

        if self.selected_indices:
            count = len(self.selected_indices)
            total = format_napoleondors(self._selected_sale_value())
            self._draw_centered_text(
                f"Выбрано: {count} из {game_state.CORRECTION_MAX_CARDS}. Получите: {total}",
                self.button_font,
                (self.panel_rect.centerx, self.panel_rect.bottom - 185),
            )
            self._draw_button(self.confirm_rect, self.confirm_text)
            self._draw_button(self.cancel_rect, self.cancel_text)
        else:
            self._draw_button(self.cancel_rect, self.back_text)

        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None
                if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                    continue

                if self.selected_indices and self.confirm_rect.collidepoint(event.pos):
                    return [self.deck[index] for index in self.selected_indices]
                if self.cancel_rect.collidepoint(event.pos):
                    if self.selected_indices:
                        self.selected_indices.clear()
                    else:
                        return None
                    continue

                card_index = self._card_at(event.pos)
                if card_index is None:
                    continue
                if card_index in self.selected_indices:
                    self.selected_indices.remove(card_index)
                elif len(self.selected_indices) < game_state.CORRECTION_MAX_CARDS:
                    self.selected_indices.append(card_index)

            self.draw()
            self.clock.tick(FPS)
