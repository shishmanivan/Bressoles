"""Level-wide conditions shared by the rules engine and the conditions menu."""

SHAREHOLDERS = "shareholders"
BOSS_SHARES = "boss_shares"
BOSS_TRADING = "boss_trading"
BOSS_SHARES_QUANTITY = 50
# Content 8 is campaign level 6; content 6 is the isolated test duel.
LEVEL_CONDITIONS = {4: (SHAREHOLDERS,), 6: (BOSS_TRADING,), 8: (BOSS_SHARES,)}
CONDITIONS = {
    BOSS_SHARES: {
        "title": "Boss Shares",
        "paragraphs": (
            "В начале каждого раунда у босса есть 50 акций A. Он не покупает и не продаёт акции в течение раунда.",
            "В конце раунда босс продаёт все 50 акций A по итоговой цене. Для победы выполните денежную цель раунда и получите итоговый капитал строго больше выручки босса. Равенство считается поражением.",
            "Раунд нельзя завершить раньше последнего хода, даже если денежная цель уже выполнена. На последнем ходу босс продаёт свои 50 акций A. Акции игрока продаются только за счёт действующего Rebate, по правилам этой карты. Без действующего Rebate игрок проигрывает, даже если денежная цель уже выполнена. Boss Shares не даёт автоматической продажи акций игрока. Итоги подводятся только на последнем ходу.",
            "Boss Shares действует в каждом раунде уровня, включая бой с боссом. Условие не исчезает после победы над боссом или перехода к следующему раунду. Отключить его могут только специальные карты, прямо отменяющие это условие.",
        ),
    },
    BOSS_TRADING: {
        "title": "Boss Trading",
        "paragraphs": (
            "Босс торгует с первого раунда независимо от своей категории. В экспериментальной дуэли действует бот «Перевложение».",
        ),
    },
    SHAREHOLDERS: {
        "title": "Шейрхолдеры",
        "paragraphs": (
            "Акционеры могут на один ход закрыть один случайный рынок. На закрытом рынке нельзя ни покупать, ни продавать. Остальные рынки работают как обычно.",
            "Эффект зависит от числа карт Shareholder в колоде на начало раунда, а не от числа карт в руке. При 0-2 картах блокировки нет. При 3 картах шанс составляет 20% на ход.",
            "Каждая следующая карта Shareholder добавляет 5 процентных пунктов: 4 карты — 25%, 5 карт — 30%, 6 карт — 35%. Максимальный шанс — 100%.",
            "В начале каждого хода проводится новая проверка. Предыдущая блокировка снимается; при новом срабатывании снова выбирается один из трёх рынков. Один и тот же рынок может закрыться несколько ходов подряд.",
            "Активная карта Controlling Stake или Golden Stake отключает все Conditions уровня на время своего действия.",
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


def conditions_disabled(page):
    """Equipped stakes suppress level conditions for their active round."""
    for attribute, stake_id in (("active_silver_cards", 205), ("active_gold_cards", 436)):
        for card_id in getattr(page, attribute, ()) or ():
            try:
                if int(card_id) == stake_id:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def active_conditions_for_page(page):
    if conditions_disabled(page):
        return ()
    return conditions_for_level(getattr(page, "level_number", None))


def has_active_condition(page, condition):
    return condition in active_conditions_for_page(page)
