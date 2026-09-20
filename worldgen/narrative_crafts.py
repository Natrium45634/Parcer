# -*- coding: utf-8 -*-
"""Тексты об открытиях: как их делают и как они расходятся по свету."""

from __future__ import annotations

from .narrative import cap


DISCOVER_TEMPLATES = (
    "%(who)s доводит до ума то, о чём говорили давно: %(what)s. %(note)s",
    "В городе %(city)s впервые делают %(what)s — и делают не для "
    "забавы. %(note)s",
    "%(who)s показывает %(what)s тем, кто платит, и находит "
    "покупателя. %(note)s",
    "Работа, начатая от нужды, кончается открытием: %(what)s. %(note)s",
    "О том, кто придумал %(what)s, спорят уже в следующем поколении. "
    "Пока же имя известно: %(who)s. %(note)s",
    "%(city_cap)s получает то, чего нет больше ни у кого: %(what)s. "
    "%(note)s",
)

DISCOVER_NOTES = (
    "Соседи узнают об этом позже, чем хотели бы.",
    "Первые годы этим пользуются немногие, потом — все.",
    "Жрецы сомневаются, купцы считают выгоду.",
    "Старые мастера ворчат, молодые переучиваются.",
    "Для летописи это мелочь; для века — нет.",
)


def discovered(rng, craft, figure, settlement, polity) -> tuple:
    note = rng.choice(craft.notes) if craft.notes else ""
    text = rng.choice(DISCOVER_TEMPLATES) % {
        "who": figure.name if figure is not None else "безвестный мастер",
        "what": craft.name,
        "city": settlement.name if settlement is not None else "неизвестном",
        "city_cap": settlement.name if settlement is not None else "Город",
        "note": note,
    }
    text = "%s %s" % (text, rng.choice(DISCOVER_NOTES))
    return ("Открытие: %s" % craft.name), cap(text)


SPREAD_TEMPLATES = (
    "То, что придумали за морем, приходит с купцами: в %(polity)s "
    "осваивают %(what)s.",
    "%(polity)s перенимает %(what)s у соседей — не сразу и не даром.",
    "Мастера, переманенные щедростью, привозят с собой %(what)s.",
    "%(what)s доходит и сюда: переняли, переделали и стали считать своим.",
    "Посольство возвращается не только с грамотой: в %(polity)s "
    "появляется %(what)s.",
)


def spread(rng, craft, polity, source) -> tuple:
    text = rng.choice(SPREAD_TEMPLATES) % {
        "polity": polity.full_name, "what": craft.name}
    if source is not None:
        text = "%s Переняли у %s." % (text, source.name)
    return ("Переняли: %s" % craft.name), cap(text)
