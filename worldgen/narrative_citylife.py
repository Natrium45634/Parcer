# -*- coding: utf-8 -*-
"""Тексты о городских случаях: пожары, стены, ярмарки, суды."""

from __future__ import annotations

from .narrative import cap
from .narrative_war import souls_text


# Имена городов не склоняются, поэтому косвенные падежи берутся
# оборотом: «в городе по имени X», а не «в X».
LEAD = (
    "%(city_cap)s: %(line)s",
    "В городе по имени %(city)s %(lower)s",
    "%(line)s Это %(city)s, и год этот там помнят.",
    "%(city_cap)s — %(lower)s",
    "Год этот в городе по имени %(city)s запоминают так: %(lower)s",
)

TOLL_LINES = (
    "Хоронят %(dead)s душ.",
    "Город теряет %(dead)s душ и долго не может собраться.",
    "Счёт погибших доходит до %(dead)s.",
)

LANDMARK_LINES = (
    "С этого года у города есть то, чего нет у соседей: %(what)s.",
    "%(what_cap)s остаётся городу надолго — дольше, чем держава, которая "
    "его строила.",
    "О том, во что это обошлось, спорят ещё поколение. %(what_cap)s стоит.",
)


def happening(rng, item, settlement, dead: int) -> tuple:
    line = rng.choice(item.lines) if item.lines else ""
    lower = line[:1].lower() + line[1:] if line else ""
    text = rng.choice(LEAD) % {
        "city": settlement.name, "city_cap": settlement.name,
        "line": line, "lower": lower,
    }
    if dead > 0:
        text = "%s %s" % (text, rng.choice(TOLL_LINES)
                          % {"dead": souls_text(dead)})
    if item.landmark:
        text = "%s %s" % (text, rng.choice(LANDMARK_LINES)
                          % {"what": item.landmark,
                             "what_cap": cap(item.landmark)})
    return ("%s: %s" % (item.title, settlement.name)), cap(text)
