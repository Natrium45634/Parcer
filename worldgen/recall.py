# -*- coding: utf-8 -*-
"""Память людей и связи между ними.

Держава помнит войны, а человек помнит свою жизнь. Государь, у которого
на чужой войне погиб отец, иначе смотрит на посольство оттуда, чем тот,
у кого с этой державой связаны только выгодные обозы. Спасённый остаётся
должен спасителю, преданный не забывает предателя, а тот, кого обошли
престолом, помнит это до смерти.

Модуль держит разборы памяти и связей, считает их силу и переводит её в
то, что понимают прочие подсистемы: насколько один человек расположен к
другому и насколько государь расположен к соседней державе.

Память слабеет, но у разных людей по-разному: мстительный помнит обиду
до могилы, не помнящий обид прощает за десять лет.
"""

from __future__ import annotations

# --- разборы памяти ---------------------------------------------------

KIN_DEATH = "гибель родича"
RESCUE = "спасение"
BETRAYAL = "предательство"
INSULT = "оскорбление"
DEBT = "долг"
PROMISE = "обещание"
LOVE = "любовь"
FRIENDSHIP = "дружба"
HATRED = "ненависть"
FEAR = "страх"
GRATITUDE = "благодарность"
COURT_FEUD = "распря при дворе"
DEFEAT = "поражение"
VICTORY = "победа"
REVELATION = "прикосновение божества"
BLUNDER = "своя ошибка"
CAPTIVITY = "плен"
HOME_LOST = "гибель дома"
PASSED_OVER = "обойдён престолом"

KINDS = (KIN_DEATH, RESCUE, BETRAYAL, INSULT, DEBT, PROMISE, LOVE, FRIENDSHIP,
         HATRED, FEAR, GRATITUDE, COURT_FEUD, DEFEAT, VICTORY, REVELATION,
         BLUNDER, CAPTIVITY, HOME_LOST, PASSED_OVER)

# Чем это отзывается: холодом (−) или теплом (+) к тому, о ком память.
SIGN = {
    KIN_DEATH: -1.0, RESCUE: 1.0, BETRAYAL: -1.0, INSULT: -0.7, DEBT: 0.8,
    PROMISE: 0.6, LOVE: 1.0, FRIENDSHIP: 0.8, HATRED: -1.0, FEAR: -0.5,
    GRATITUDE: 0.9, COURT_FEUD: -0.6, DEFEAT: -0.6, VICTORY: 0.3,
    REVELATION: 0.0, BLUNDER: 0.0, CAPTIVITY: -0.9, HOME_LOST: -0.8,
    PASSED_OVER: -0.7,
}

TONE = {
    KIN_DEATH: "скорбь", RESCUE: "благодарность", BETRAYAL: "гнев",
    INSULT: "гнев", DEBT: "долг", PROMISE: "долг", LOVE: "любовь",
    FRIENDSHIP: "приязнь", HATRED: "ненависть", FEAR: "страх",
    GRATITUDE: "благодарность", COURT_FEUD: "гнев", DEFEAT: "стыд",
    VICTORY: "гордость", REVELATION: "трепет", BLUNDER: "стыд",
    CAPTIVITY: "страх", HOME_LOST: "скорбь", PASSED_OVER: "обида",
}

# Сколько памяти уходит за сто лет у обычного человека.
FADE = {
    KIN_DEATH: 0.22, RESCUE: 0.28, BETRAYAL: 0.20, INSULT: 0.45, DEBT: 0.35,
    PROMISE: 0.40, LOVE: 0.25, FRIENDSHIP: 0.35, HATRED: 0.18, FEAR: 0.40,
    GRATITUDE: 0.38, COURT_FEUD: 0.40, DEFEAT: 0.35, VICTORY: 0.30,
    REVELATION: 0.15, BLUNDER: 0.35, CAPTIVITY: 0.25, HOME_LOST: 0.20,
    PASSED_OVER: 0.22,
}

# --- разборы связей ---------------------------------------------------

B_FRIEND = "дружба"
B_ENMITY = "вражда"
B_RIVALRY = "соперничество"
B_LOVE = "любовь"
B_RESPECT = "уважение"
B_FEAR = "страх"
B_ENVY = "зависть"
B_DEBT = "долг"
B_MENTOR = "наставничество"
B_TREASON = "предательство"
B_KIN = "родство"

BOND_KINDS = (B_FRIEND, B_ENMITY, B_RIVALRY, B_LOVE, B_RESPECT, B_FEAR,
              B_ENVY, B_DEBT, B_MENTOR, B_TREASON, B_KIN)

# Куда связь тянет отношения: от вражды к любви.
BOND_SIGN = {
    B_FRIEND: 0.8, B_ENMITY: -1.0, B_RIVALRY: -0.4, B_LOVE: 1.0,
    B_RESPECT: 0.5, B_FEAR: -0.3, B_ENVY: -0.5, B_DEBT: 0.6,
    B_MENTOR: 0.7, B_TREASON: -0.9, B_KIN: 0.4,
}

# Во что связь перерастает, если её портит политика или, наоборот, годы.
SOURS = {B_FRIEND: B_RIVALRY, B_RIVALRY: B_ENMITY, B_RESPECT: B_ENVY,
         B_LOVE: B_RIVALRY, B_MENTOR: B_RIVALRY, B_DEBT: B_ENVY,
         B_ENVY: B_ENMITY, B_TREASON: B_ENMITY}
MELLOWS = {B_RIVALRY: B_RESPECT, B_ENMITY: B_RIVALRY, B_ENVY: B_RESPECT,
           B_FEAR: B_RESPECT}


# --- нрав ---------------------------------------------------------------

# Кто как помнит: мстительный не забывает ничего, незлопамятный прощает.
VENGEFUL = {
    "мстительный": 1.7, "вспыльчивый": 1.3, "подозрительный": 1.25,
    "охотник до казней": 1.3, "завистливый": 1.2, "жестокий к пленным": 1.2,
    "неразборчивый в средствах": 1.15, "павший во зло": 1.5,
}
FORGIVING = {
    "не помнящий обид": 0.4, "милосердный": 0.6, "миротворец": 0.65,
    "терпеливый": 0.8, "богобоязненный": 0.85, "щедрый": 0.9,
    "справедливый в суде": 0.85,
}


def temper(figure) -> float:
    """Насколько тяжело этот человек помнит зло."""
    if figure is None:
        return 1.0
    value = 1.0
    for trait in (figure.traits or ()):
        value *= VENGEFUL.get(trait, 1.0)
        value *= FORGIVING.get(trait, 1.0)
    return max(0.25, min(2.4, value))


# --- сила памяти --------------------------------------------------------

def power(memory, year: int, figure=None) -> float:
    """Сколько в воспоминании осталось силы к этому году."""
    if memory is None or year < memory.year:
        return 0.0
    age = (year - memory.year) / 100.0
    fade = FADE.get(memory.kind, 0.3)
    if figure is not None and SIGN.get(memory.kind, 0.0) < 0:
        fade /= temper(figure)          # злопамятный забывает медленнее
    value = memory.weight * max(0.0, 1.0 - fade * age)
    if memory.twisted:
        value *= 1.15                   # переиначенная память жжёт сильнее
    return min(1.5, value)


def attitude(world, figure, about_id: str, year: int) -> float:
    """Как этот человек относится к тому, о ком речь, — по своему опыту.

    Число от −1 (кровный враг) до 1 (тот, кому обязан жизнью).
    """
    if figure is None or not about_id:
        return 0.0
    total = 0.0
    for memory in world.memories_of(figure.id, about_id=about_id):
        total += SIGN.get(memory.kind, 0.0) * power(memory, year, figure)
    bond = world.bond_between(figure.id, about_id)
    if bond is not None:
        total += bond.value if bond.value else BOND_SIGN.get(bond.kind, 0.0)
    return max(-1.0, min(1.0, total))


def grievance(world, figure, about_id: str, year: int) -> float:
    """Только холодная часть: сколько у человека счётов к этой стороне."""
    return max(0.0, -attitude(world, figure, about_id, year))


def strongest(world, figure, about_id: str, year: int, cold: bool = False):
    """Самое тяжёлое воспоминание об этой стороне — для летописи.

    С cold=True берётся самое тяжёлое из недобрых: государь, у которого
    с соседом связаны и победа, и гибель отца, на совете вспомнит второе.
    """
    best, best_power = None, 0.0
    for memory in world.memories_of(figure.id, about_id=about_id):
        if cold and SIGN.get(memory.kind, 0.0) >= 0:
            continue
        value = power(memory, year, figure)
        if value > best_power:
            best, best_power = memory, value
    return best


def ruler_attitude(world, polity, about_id: str, year: int) -> float:
    """Личное отношение государя к чужой державе."""
    if polity is None:
        return 0.0
    ruler = world.figures.get(polity.ruler_id)
    if ruler is None:
        return 0.0
    return attitude(world, ruler, about_id, year)


def bond_worth(bond) -> float:
    if bond is None:
        return 0.0
    return bond.value if bond.value else BOND_SIGN.get(bond.kind, 0.0)
