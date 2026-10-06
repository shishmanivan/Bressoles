"""Profile-scoped onboarding shown over the first playable screen."""

from pathlib import Path

import pygame

from gameplay_assets import build_hand_frame
from localization import get_language, translate
from shared_utils import wrap_text


FIRST_HINT_ID = "stock_cards"
SHAREHOLDER_HINT_ID = "level4_shareholders"
SHAREHOLDER_HINT_TEXT = (
    "На 4-ом уровне действует эффект акционеров. Если у вас в колоде есть 3 карты Shareholder, "
    "есть 20% шанс того, что они запретят вам торговать на каком-то одном рынке. "
    "Запрет действует один ход. Чем больше карт Shareholder у вас в колоде, тем больше "
    "вероятность того, что они будут запрещать торговать. Но в игре можно встретить карты, "
    "которые отключают этот эффект."
)
STORAGE_HINT_ID = "card_storage"
BLACK_STORAGE_HINT_ID = "black_card_storage"
BLACK_STORAGE_HINT_TEXT = (
    "Вы получили свою первую чёрную карту. Эти карты не пропадают после поражения "
    "или после использования - вы получаете их раз и навсегда"
)
STORAGE_HINT_TEXT = (
    "Это хранилище ваших золотых, чёрных и серебряных карт. "
    "Эти карты оказывают сильное влияние на ход игры. "
    "Подбирайте комбинации, которые соответствуют вашему стилю игры. "
    "Перед началом следующего раунда вы сможете поменять комбинацию. "
    "Полученные золотые карты пропадут после поражения"
)
SILVER_STORAGE_HINT_ID = "silver_card_storage"
SILVER_STORAGE_HINT_TEXT = (
    "В хранилище появилась ваша первая серебряная карта. Серебряные карты действуют "
    "один раунд и исчезают после использования. "
    "Но неиспользованные серебряные карты не пропадают после поражения. "
    "Даже когда вы проиграете, все собранные серебряные карты сохранятся."
)
GOLD_SHOP_HINT_ID = "gold_shop"
INVESTMENT_HINT_ID = "investment_shop"
INVESTMENT_HINT_TEXT = (
    "Теперь вам доступен раздел инвестиций. В нём вы можете усиливать Gain и Drop карты, "
    "чтобы они оказывали большее влияние на цену акций"
)
GOLD_SHOP_HINT_TEXT = (
    "Теперь вы можете покупать золотые карты. Золотые карты действуют на протяжении всей игры. "
    "Это как джокеры в балатро, если вы понимаете, о чём я.\n\n"
    "Также вам теперь доступен раздел лицензий, где вы можете купить лицензию. "
    "Купить лицензию значит сделать так, чтобы карта появлялась в игре."
)
LATE_END_TURN_HINT_ID = "late_end_turn"
LATE_END_TURN_HINT_TEXT = (
    "Для того чтобы закончить ход, нажмите кнопку закончить ход. "
    "Да, подсказка запоздала, но лучше поздно, чем никогда."
)
RED_CARD_HINT_ID = "first_red_card"
RED_CARD_HINT_TEXT = (
    "Вы получили первую красную карту. Как правило, они влияют на все акции сразу. "
    "Хотя не всегда. В дальнейшем вы будете получать красные карты, "
    "которые оказывают очень большое влияние на ход игры."
)
ROUND_CHOICE_HINT_ID = "round_choice"
ROUND_CHOICE_HINT_TEXT = (
    "Это экран выбора раунда. Вы можете выбрать лёгкий раунд и получить меньшую награду, "
    "или выбрать раунд тяжелее и получить награду побольше."
)
BOSS_CHOICE_HINT_ID = "boss_choice"
BOSS_CHOICE_HINT_TEXT = (
    "Это экран выбора боссов. На некоторых уровнях вы сможете выбрать одного из нескольких боссов. "
    "На некоторых уровнях такой возможности не будет."
)
FIRST_HINT_TEXT = (
    "Акции растут и падают. "
    "Влияйте на рост и падение цен с помощью карт."
)
SELL_HINT_ID = "sell_before_last_turn"
LOGO_HINT_ID = "stock_logo_hover"
LOGO_HINT_TEXT = "Наведите мышь на логотип акции для того, чтобы узнать более подробную информацию."
SELL_HINT_TEXT = (
    "Перед последним ходом вы должны обналичить свои акции. "
    "Карты, позволяющие автоматически продавать акции на последнем ходу, появятся позже. "
    "Пока их нет, продавать акции нужно вручную."
)
INK = (83, 76, 70)


class TutorialHint:
    def __init__(self, screen_size, frame, font_path, ok_image=None,
                 hint_id=FIRST_HINT_ID, text=FIRST_HINT_TEXT, placement="center"):
        self.hint_id = hint_id
        self.has_checkbox = hint_id != FIRST_HINT_ID
        self.dont_show_again = False
        self.panel = pygame.Rect(0, 0, 760, 470 if self.has_checkbox else 340)
        if hint_id in (GOLD_SHOP_HINT_ID, STORAGE_HINT_ID, SILVER_STORAGE_HINT_ID, SHAREHOLDER_HINT_ID):
            self.panel.size = (900, 650)
        self.panel.center = (screen_size[0] // 2, screen_size[1] // 2)
        if placement == "right":
            self.panel.right = screen_size[0] - 60
        self.frame = build_hand_frame(frame, self.panel.size) if frame is not None else None
        # The legacy display font renders Hungarian double accents as blanks.
        if get_language() == "HU":
            font_path = str(Path(__file__).parent / "Fonts" / "OldStandard-Bold.ttf")
        self.font = pygame.font.Font(font_path, 32)
        self.lines = []
        for paragraph in translate(text).split("\n"):
            self.lines.extend(wrap_text(paragraph, self.font, self.panel.width - 120) if paragraph else [""])
        artwork = pygame.image.load(str(Path(__file__).parent / "UI" / "Ornate Button Blank.png"))
        bounds = max(pygame.mask.from_surface(artwork, 127).get_bounding_rects(),
                     key=lambda rect: rect.width * rect.height)
        artwork = artwork.subsurface(bounds).copy()
        size = (140, round(140 * artwork.get_height() / artwork.get_width()))
        self.ok_image = pygame.transform.smoothscale(artwork, size)
        label = pygame.font.Font(str(Path(__file__).parent / "Fonts" / "OldStandard-Bold.ttf"), 24).render(
            "OK", True, (57, 29, 12))
        self.ok_image.blit(label, label.get_rect(center=self.ok_image.get_rect().center))
        self.pressed_image = pygame.transform.smoothscale(
            self.ok_image, (round(size[0] * .96), round(size[1] * .96)))
        self.pressing = False
        self.press_until = None
        self.button = self.ok_image.get_rect()
        self.button.midbottom = (self.panel.centerx, self.panel.bottom - 35)
        self.checkbox_font = pygame.font.Font(font_path, 26)
        self.checkbox_label = self.checkbox_font.render(translate("Больше не показывать"), True, INK)
        row_width = 28 + 14 + self.checkbox_label.get_width()
        self.checkbox_row = pygame.Rect(0, 0, row_width, 32)
        self.checkbox_row.midbottom = (self.panel.centerx, self.button.top - 20)
        self.checkbox = pygame.Rect(self.checkbox_row.left, self.checkbox_row.top + 2, 28, 28)

    def accepts(self, event):
        if self.pressing:
            return False
        if (self.has_checkbox and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1 and self.checkbox_row.collidepoint(event.pos)):
            self.dont_show_again = not self.dont_show_again
            return False
        return (
            event.type == pygame.KEYDOWN
            and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE)
        ) or (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.button.collidepoint(event.pos)
        )

    def start_press(self, sound=None):
        if self.pressing:
            return
        self.pressing = True
        if sound is not None:
            sound.play()

    def ready_to_close(self):
        return self.press_until is not None and pygame.time.get_ticks() >= self.press_until

    def draw(self, screen):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 110))
        screen.blit(shade, (0, 0))
        pygame.draw.rect(screen, (236, 226, 201), self.panel.inflate(-18, -18))
        if self.frame is not None:
            screen.blit(self.frame, self.panel)
        else:
            pygame.draw.rect(screen, INK, self.panel, 3)
        line_height = self.font.get_linesize() + 8
        text_bottom = self.checkbox_row.top if self.has_checkbox else self.button.top
        text_area = pygame.Rect(self.panel.left, self.panel.top + 45,
                                self.panel.width, text_bottom - self.panel.top - 65)
        y = text_area.centery - len(self.lines) * line_height // 2
        for line in self.lines:
            rendered = self.font.render(line, True, INK)
            screen.blit(rendered, (self.panel.centerx - rendered.get_width() // 2, y))
            y += line_height
        if self.has_checkbox:
            pygame.draw.rect(screen, INK, self.checkbox, 2)
            if self.dont_show_again:
                pygame.draw.lines(screen, INK, False, [
                    (self.checkbox.left + 5, self.checkbox.centery),
                    (self.checkbox.left + 11, self.checkbox.bottom - 6),
                    (self.checkbox.right - 5, self.checkbox.top + 6),
                ], 3)
            screen.blit(self.checkbox_label, (self.checkbox.right + 14, self.checkbox_row.top))
        if self.ok_image is not None:
            if self.pressing and self.press_until is None:
                self.press_until = pygame.time.get_ticks() + 110
            button_image = self.pressed_image if self.pressing else self.ok_image
            screen.blit(button_image, button_image.get_rect(center=self.button.center))
        else:
            pygame.draw.rect(screen, INK, self.button, 2)
            label = self.font.render("OK", True, INK)
            screen.blit(label, label.get_rect(center=self.button.center))
