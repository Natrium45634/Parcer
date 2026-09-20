# -*- coding: utf-8 -*-
"""Тексты о законах и реформах: указ, его цена и его слава."""

from __future__ import annotations

from .morph import genitive_noun
from .narrative import cap


def polity_gen(polity) -> str:
    return "%s %s" % (genitive_noun(polity.form).lower(), polity.name)


REFORM_TEMPLATES = (
    "%(ruler)s проводит то, о чём прежние государи только говорили: "
    "%(what)s. %(line)s",
    "Указ читают на площадях всех городов державы: в %(polity)s вводят "
    "%(what)s. %(line)s",
    "%(polity)s заводит %(what)s — первым в этих краях. %(line)s",
    "Дело, начатое %(ruler)s, называют %(what)s и спорят о нём ещё "
    "поколение. %(line)s",
    "%(what_cap)s — то, чем это правление запомнят вернее, чем войнами. "
    "%(line)s",
)

COST_LINES = (
    "Знать принимает это тяжело.",
    "Первые годы указ исполняют скверно, потом привыкают.",
    "Противников у указа больше, чем сторонников, — но указ остаётся.",
    "Половина совета считает это ошибкой и говорит об этом вслух.",
    "Казне это стоит дорого, и казна об этом напоминает.",
)

GOOD_LINES = (
    "Соседи присматриваются.",
    "Через поколение никто уже не помнит, как жили иначе.",
    "Купцы первыми замечают выгоду и первыми хвалят.",
    "Летописцы отметят это отдельной строкой.",
)


def reform_made(rng, reform, polity, ruler) -> tuple:
    line = rng.choice(reform.lines) if reform.lines else ""
    text = rng.choice(REFORM_TEMPLATES) % {
        "ruler": ruler.name if ruler is not None else "государь",
        "polity": polity.full_name, "what": reform.name,
        "what_cap": cap(reform.name), "line": line,
    }
    tail = rng.choice(COST_LINES) if reform.nobles > 0 \
        else rng.choice(GOOD_LINES)
    return ("Реформа: %s" % reform.name), cap("%s %s" % (text, tail))


COPY_TEMPLATES = (
    "То, что удалось соседям, перенимают: в %(polity)s вводят %(what)s.",
    "%(polity)s заводит %(what)s по чужому примеру — и не скрывает, по "
    "чьему.",
    "Посольство привозит не только грамоту, но и порядок: в %(polity)s "
    "появляется %(what)s.",
    "Спорили двадцать лет и сделали как у соседей: %(what)s.",
)


def reform_copied(rng, reform, polity, source) -> tuple:
    text = rng.choice(COPY_TEMPLATES) % {
        "polity": polity.full_name, "what": reform.name}
    if source is not None:
        text = "%s Образцом считают %s." % (text, source.full_name)
    return ("Переняли порядок: %s" % reform.name), cap(text)


FAME_TEMPLATES = (
    "%(what_cap)s, заведённая в %(polity)s, к этому году стоит уже в "
    "%(count)d державах. О том, кто был первым, помнят все.",
    "То, что начиналось как указ одной державы, стало общим порядком: "
    "%(what)s знают в %(count)d державах.",
    "%(what_cap)s расходится по свету: %(count)d держав живут по этому "
    "порядку, и первой была %(polity)s.",
)


def reform_famous(rng, reform, polity, count: int) -> tuple:
    text = rng.choice(FAME_TEMPLATES) % {
        "what": reform.name, "what_cap": cap(reform.name),
        "polity": polity.full_name, "count": count,
    }
    return ("Общий порядок: %s" % reform.name), cap(text)
