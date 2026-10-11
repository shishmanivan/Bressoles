"""Level-wide conditions shared by the rules engine and the conditions menu."""

SHAREHOLDERS = "shareholders"
LEVEL_CONDITIONS = {4: (SHAREHOLDERS,)}
CONDITIONS = {
    SHAREHOLDERS: {
        "title": "Шейрхолдеры",
        "paragraphs": (
            "Акционеры могут на один ход закрыть один случайный рынок. На закрытом рынке нельзя ни покупать, ни продавать. Остальные рынки работают как обычно.",
            "Эффект зависит от числа карт Shareholder в колоде на начало раунда, а не от числа карт в руке. При 0-2 картах блокировки нет. При 3 картах шанс составляет 20% на ход.",
            "Каждая следующая карта Shareholder добавляет 5 процентных пунктов: 4 карты — 25%, 5 карт — 30%, 6 карт — 35%. Максимальный шанс — 100%.",
            "В начале каждого хода проводится новая проверка. Предыдущая блокировка снимается; при новом срабатывании снова выбирается один из трёх рынков. Один и тот же рынок может закрыться несколько ходов подряд.",
            "Активная карта «Контрольный пакет» или Golden Stake полностью отключает блокировку рынков шейрхолдерами на время своего действия.",
        ),
    },
}


def conditions_for_level(level):
    try:
        return LEVEL_CONDITIONS.get(int(level), ())
    except (TypeError, ValueError):
        return ()


def has_condition(level, condition):
    return condition in conditions_for_level(level)
