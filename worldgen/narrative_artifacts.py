# -*- coding: utf-8 -*-
"""Тексты о вещах, у которых есть имя: ковка, дары, потери и находки.

Правила прежние: сгенерированные имена стоят в именительном падеже,
косвенные падежи берутся готовыми оборотами («меч по имени X»), глаголы —
в настоящем времени третьего лица.
"""

from __future__ import annotations

from .morph import accusative_noun
from .narrative import cap


def thing(artifact) -> str:
    """«меч по имени Гламдринг» — как о вещи говорят в косвенном падеже.

    Если имя и так начинается с рода вещи («Клинок Белого Пламени»),
    слово второй раз не ставится: «клинок клинок» — это опечатка.
    """
    if artifact.word.lower() in artifact.name.lower():
        return artifact.name
    return "%s по имени %s" % (artifact.word.lower(), artifact.name)


def its(artifact) -> str:
    """«его», «её» — местоимение по роду слова, а не наугад."""
    return {"f": "её", "n": "его"}.get(artifact.gender, "его")


def thing_nom(artifact) -> str:
    if artifact.word.lower() in artifact.name.lower():
        return artifact.name
    return "%s %s" % (artifact.word, artifact.name)


def thing_acc(artifact) -> str:
    """«чашу по имени X» — винительный падеж, но только у слова рода.

    Имя вещи остаётся как есть: склоняется только «чаша», «меч», «венец».
    """
    if artifact.word.lower() in artifact.name.lower():
        return artifact.name
    return "%s по имени %s" % (accusative_noun(artifact.word).lower(),
                               artifact.name)


# ---------------------------------------------------------------------------
# Ковка
# ---------------------------------------------------------------------------

FORGE_TEMPLATES = (
    "%(maker)s заканчивает работу, которой отдал не один год: %(what)s, "
    "%(material)s. %(power)s",
    "В кузне города по имени %(city)s рождается %(what)s — %(material)s. "
    "%(power)s",
    "%(maker)s берётся за заказ, от которого отказались все прочие, и "
    "выходит %(what)s, %(material)s. %(power)s",
    "Работу ведут в тайне и заканчивают к сроку: %(what)s, %(material)s. "
    "%(power)s",
    "%(maker)s кладёт последний удар молота, и на свет выходит новая "
    "вещь: %(what)s, %(material)s. %(power)s",
    "О такой работе потом говорят, что она удалась один раз и больше не "
    "повторилась: %(what)s, %(material)s. %(power)s",
)

POWER_LINES = (
    "Говорят, вещь %(power)s.",
    "За ней числится одно: %(power)s.",
    "Мастер клянётся, что вещь %(power)s, — и врёт он или нет, проверят "
    "другие.",
    "Свидетели уверяют: вещь %(power)s.",
)

CURSE_LINES = (
    "Через поколение заметят и другое: вещь %(curse)s.",
    "Чего мастер не сказал: вещь %(curse)s.",
    "Худшее узнают позже — вещь %(curse)s.",
    "К славе прилагается цена: вещь %(curse)s.",
)


def forged(rng, artifact, maker, settlement) -> tuple:
    power = rng.choice(POWER_LINES) % {
        "power": artifact.powers[0] if artifact.powers else "сделана на совесть"}
    text = rng.choice(FORGE_TEMPLATES) % {
        "maker": maker.name if maker is not None else "безвестный мастер",
        "what": thing_nom(artifact),
        "material": artifact.material_gen,
        "city": settlement.name if settlement is not None else "безымянного города",
        "power": power,
    }
    if artifact.curse:
        text = "%s %s" % (text, rng.choice(CURSE_LINES)
                          % {"curse": artifact.curse})
    return ("Работа мастера: %s" % artifact.name), cap(text)


GIFT_TEMPLATES = (
    "%(deity)s оставляет на алтаре то, чего там не было вечером: "
    "%(what)s, %(material)s. %(power)s",
    "Дар приходит во сне, а наутро лежит наяву: %(what)s, %(material)s. "
    "%(power)s",
    "Жрецы выносят к народу %(what_acc)s и говорят, что вещь дана свыше. "
    "%(power)s",
    "За выстроенный храм бог платит щедро: %(what)s, %(material)s. "
    "%(power)s",
)


def gifted(rng, artifact, deity, temple) -> tuple:
    power = rng.choice(POWER_LINES) % {
        "power": artifact.powers[0] if artifact.powers else "не знает износа"}
    text = rng.choice(GIFT_TEMPLATES) % {
        "deity": deity.name if deity is not None else "Бог",
        "what": thing_nom(artifact), "what_acc": thing_acc(artifact),
        "material": artifact.material_gen,
        "power": power,
    }
    if artifact.curse:
        text = "%s %s" % (text, rng.choice(CURSE_LINES)
                          % {"curse": artifact.curse})
    return ("Дар богов: %s" % artifact.name), cap(text)


# ---------------------------------------------------------------------------
# Из рук в руки
# ---------------------------------------------------------------------------

GRANT_TEMPLATES = (
    "%(who)s получает %(what_acc)s из державной сокровищницы — за дело, а не "
    "за родство.",
    "Государь жалует %(who)s вещь, о которой говорят все: %(what_nom)s. "
    "Такие дают перед войной, а не после.",
    "%(what_nom)s переходит в другие руки: принимает её %(who)s, и при "
    "дворе это считают знаком.",
    "%(who)s принимает вещь из державной казны — %(what_nom)s — и "
    "клянётся вернуть её или не вернуться самому.",
)


def granted(rng, artifact, figure, polity) -> tuple:
    text = rng.choice(GRANT_TEMPLATES) % {
        "who": figure.name, "what": thing(artifact),
        "what_acc": thing_acc(artifact), "what_nom": thing_nom(artifact),
    }
    return ("Вещь в новых руках: %s" % artifact.name), cap(text)


INHERIT_TEMPLATES = (
    "%(what_nom)s достаётся наследнику: %(who)s принимает её вместе с "
    "долгами прежнего хозяина.",
    "Вещь остаётся в роду: %(what_nom)s принимает %(who)s.",
    "%(who)s берёт вещь из рук умирающего — %(what_nom)s, — и это видят "
    "все, кому нужно было увидеть.",
)


def inherited(rng, artifact, figure) -> tuple:
    text = rng.choice(INHERIT_TEMPLATES) % {
        "what_nom": thing_nom(artifact), "what_acc": thing_acc(artifact),
        "who": figure.name,
    }
    return ("Наследство: %s" % artifact.name), cap(text)


SEIZED_TEMPLATES = (
    "%(what_nom)s достаётся победителю: %(who)s снимает его с павшего.",
    "Вещь меняет хозяина прямо на поле: %(what_nom)s берёт %(who)s.",
    "%(who)s уносит добычу с собой — %(what_nom)s, — и спорить с этим "
    "некому.",
)


def seized(rng, artifact, figure) -> tuple:
    text = rng.choice(SEIZED_TEMPLATES) % {
        "what_nom": thing_nom(artifact), "what_acc": thing_acc(artifact),
        "who": figure.name,
    }
    return ("Добыча: %s" % artifact.name), cap(text)


# ---------------------------------------------------------------------------
# Утрата и находка
# ---------------------------------------------------------------------------

LOST_TEMPLATES = (
    "%(what_nom)s пропадает вместе с хозяином, и где искать — не знает "
    "никто.",
    "После этого дня вещь по имени %(name)s никто не видит: ищут долго "
    "и не находят.",
    "%(what_nom)s уходит на дно вместе с кораблём.",
    "Вещь теряется в суматохе отхода: %(what_nom)s остаётся где-то там, "
    "где стояли шатры.",
    "%(what_nom)s исчезает так тихо, что пропажу замечают через год.",
)


def lost(rng, artifact, region) -> tuple:
    text = rng.choice(LOST_TEMPLATES) % {
        "what_nom": thing_nom(artifact), "what_acc": thing_acc(artifact),
        "name": artifact.name}
    if region is not None:
        text = "%s Последний раз %s видели в земле по имени %s." % (
            text, its(artifact), region.name)
    return ("Пропажа: %s" % artifact.name), cap(text)


FOUND_TEMPLATES = (
    "%(who)s выносит из %(place)s то, что считали сгинувшим: %(what_nom)s.",
    "Находка случайна и оттого громка: %(what_nom)s снова на свету. "
    "Нашёл его %(who)s.",
    "%(place_cap)s отдаёт своё: %(what_nom)s возвращается в мир спустя "
    "%(years)s.",
    "%(who)s спускается туда, куда не советовали, и возвращается не с "
    "пустыми руками: %(what_nom)s снова на свету.",
)


def found(rng, artifact, figure, place: str, years: int) -> tuple:
    from .timeline import years_text

    text = rng.choice(FOUND_TEMPLATES) % {
        "who": figure.name if figure is not None else "неизвестный",
        "place": place, "place_cap": cap(place),
        "what_nom": thing_nom(artifact), "what_acc": thing_acc(artifact),
        "years": years_text(max(1, years)),
    }
    return ("Находка: %s" % artifact.name), cap(text)


DESTROYED_TEMPLATES = (
    "%(what_nom)s ломают намеренно: иначе от него было не избавиться.",
    "Вещь бросают в огонь горы, и на этом её история кончается.",
    "%(what_nom)s разбивают на куски и развозят их в разные стороны.",
    "Жрецы берутся извести вещь по имени %(name)s — и, к общему "
    "удивлению, у них выходит.",
)


def destroyed(rng, artifact) -> tuple:
    text = rng.choice(DESTROYED_TEMPLATES) % {
        "what_nom": thing_nom(artifact), "what_acc": thing_acc(artifact),
        "name": artifact.name}
    return ("Конец вещи: %s" % artifact.name), cap(text)


# ---------------------------------------------------------------------------
# Проклятие в действии
# ---------------------------------------------------------------------------

CURSE_STRIKES = (
    "Хозяин %(what_gen)s умирает не вовремя и не своей смертью — вещь "
    "%(curse)s.",
    "Цена сказывается: %(who)s гибнет, а %(what_nom)s остаётся ждать "
    "следующего.",
    "О проклятии знали и всё равно взяли. %(who)s расплачивается первым.",
)


def curse_strikes(rng, artifact, figure) -> tuple:
    text = rng.choice(CURSE_STRIKES) % {
        "what_gen": thing(artifact), "what_nom": thing_nom(artifact),
        "who": figure.name if figure is not None else "хозяин",
        "curse": artifact.curse or "берёт своё",
    }
    return ("Проклятие: %s" % artifact.name), cap(text)
