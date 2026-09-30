"""Render the display face specimen. Build-only dependency: Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "bressoles-font"
FONT = ROOT / "Fonts" / "BressolesDisplay-Regular.ttf"


def render():
    OUT.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1800, 2050), "#eee0c6")
    draw = ImageDraw.Draw(image)
    ink, secondary = "#3d3328", "#806f55"
    plain = "C:/Windows/Fonts/segoeui.ttf"
    label = ImageFont.truetype(plain, 26)
    small = ImageFont.truetype(plain, 23)
    font = lambda size: ImageFont.truetype(str(FONT), size)
    draw.rectangle((30, 30, 1770, 2020), outline=secondary, width=2)
    draw.text((85, 69), "БРЕСОЛЬ  /  BRESSOLES DISPLAY  /  ВЕРСИЯ 0.11", font=label, fill=secondary)
    draw.text((85, 117), "Шрифт меню · новые векторные буквы · строчные как малая капитель", font=small, fill=secondary)
    draw.line((85, 174, 1715, 174), fill=secondary, width=1)
    # The French phrases are deliberately the same as the reference menu.
    draw.text((90, 210), "МЕНЮ ИЗ РЕФЕРЕНСА", font=label, fill=secondary)
    for y, text in [(256,"Commencer"), (379,"Mode Campagne"), (502,"Multijoueur"),
                    (625,"Options"), (748,"Quitter")]:
        draw.text((90, y), text, font=font(101), fill=ink)
    draw.text((1000, 210), "КИРИЛЛИЦА", font=label, fill=secondary)
    for y, text in [(256,"Начать игру"), (379,"Кампания"), (502,"Настройки"),
                    (625,"Языки"), (748,"Выход")]:
        draw.text((1000, y), text, font=font(87), fill=ink)
    draw.line((85, 882, 1715, 882), fill=secondary, width=1)
    sections = [
        (915, "ФРАНЦУЗСКИЙ", "Édition · Français · Cœur · Œuvre · Ça", 73),
        (1055, "ВЕНГЕРСКИЙ", "Játék · Beállítások · Árvíztűrő tükörfúrógép", 70),
        (1195, "КИРИЛЛИЦА / ХАРАКТЕРНЫЕ БУКВЫ", "Дд Жж Лл Фф Цц Щщ Ъъ Ыы Ьь Ёё Йй", 72),
        (1340, "ПРОПИСНЫЕ", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", 68),
        (1455, "", "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ", 57),
        (1580, "МАЛАЯ КАПИТЕЛЬ", "abcdefghijklmnopqrstuvwxyz", 70),
        (1690, "", "абвгдеёжзийклмнопрстуфхцчшщъыьэюя", 63),
        (1812, "ЦИФРЫ / ЗНАКИ", "0123456789  ·  №  ₽  €  £  %  &  «»  ! ?", 76),
    ]
    for y, title, text, size in sections:
        if title:
            draw.text((90, y), title, font=small, fill=secondary)
            y += 29
        draw.text((90, y), text, font=font(size), fill=ink)
    draw.text((90, 1965), "Латиница + кириллица · É À Ç Œ Æ · Á É Í Ó Ö Ő Ú Ü Ű · Ё Й І Ї Є Ґ", font=small, fill=secondary)
    target = OUT / "Bressoles-Display-specimen.png"
    image.save(target)
    print(target)
    previous = OUT / "v0100/BressolesDisplay-Regular.ttf"
    if previous.exists():
        comparison = Image.new("RGB", (1800, 1430), "#eee0c6")
        comp = ImageDraw.Draw(comparison)
        comp.text((70, 42), "БРЕСОЛЬ / СМЯГЧЕНИЕ КОНТУРОВ", font=label, fill=ink)
        comp.text((70, 99), "БЫЛО · 0.100", font=label, fill=secondary)
        comp.text((950, 99), "СТАЛО · 0.110", font=label, fill=secondary)
        comp.line((890, 99, 890, 1340), fill=secondary)
        rows = [("A M N V W Y", 154, 340), ("Е Н Б Д Ж", 156, 565),
                ("Commencer", 116, 750), ("Mode Campagne", 100, 930),
                ("Настройки", 116, 1110), ("É À Ç Ő Ű Ё Й", 97, 1285)]
        for text, size, baseline in rows:
            for x, source in ((70, previous), (950, FONT)):
                comp.text((x, baseline), text, font=ImageFont.truetype(str(source), size),
                          fill=ink, anchor="ls")
        comp.text((70, 1370), "Сравнение при одинаковом размере: плавные стыки, скруглённые засечки и внутренние углы.", font=small, fill=secondary)
        comparison.save(OUT / "Bressoles-rounded-comparison.png")


if __name__ == "__main__":
    render()
