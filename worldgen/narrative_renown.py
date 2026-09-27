# -*- coding: utf-8 -*-
"""Слова об историческом весе: ступени, роли, след и шесть голосов.

Имена людей в этом мире не склоняются, поэтому всюду обороты: «человек
по имени X», «о человеке по имени X». Прошедшее время согласуется парами
через окончание, как и везде.
"""

from __future__ import annotations

from . import renown as cat

DID = {"m": "", "f": "а", "n": "о"}
HE = {"m": "он", "f": "она", "n": "оно"}
HIM = {"m": "его", "f": "её", "n": "его"}
MAN = {"m": "человек", "f": "женщина", "n": "человек"}


def cap(line: str) -> str:
    return line[:1].upper() + line[1:] if line else line


def forms(figure) -> dict:
    sex = figure.sex if figure.sex in DID else "m"
    return {"he": HE[sex], "him": HIM[sex], "was": DID[sex], "man": MAN[sex]}


def man_ref(figure) -> str:
    return "%s по имени %s" % (MAN.get(figure.sex, "человек"),
                               figure.plain_name)


# ---------------------------------------------------------------------------
# Ступень
# ---------------------------------------------------------------------------

LEVEL_FRAMES = (
    "Вес его в истории — %(level)d из десяти: %(about)s.",
    "По счёту дел это %(level)d ступень из десяти — %(about)s.",
    "История ставит его на %(level)d ступень: %(about)s.",
)


def level_line(rng, level: int) -> str:
    return rng.choice(LEVEL_FRAMES) % {
        "level": level, "about": cat.LEVEL_ABOUT.get(level, "")}


RISE_FRAMES = (
    "С %(from)d ступени он поднялся до %(to)d: %(why)s.",
    "Имя его выросло с %(from)d до %(to)d — %(why)s.",
)

FALL_FRAMES = (
    "С %(from)d ступени он осел до %(to)d: %(why)s.",
    "Имя его осыпалось с %(from)d до %(to)d — %(why)s.",
)


def review_line(rng, before: int, after: int, why: str) -> str:
    rows = RISE_FRAMES if after > before else FALL_FRAMES
    return rng.choice(rows) % {"from": before, "to": after, "why": why}


# ---------------------------------------------------------------------------
# Роли и судьба
# ---------------------------------------------------------------------------

ROLE_FRAMES = (
    "Для истории он %(role)s: %(about)s.",
    "Чем он оказался для истории — %(role)s, %(about)s.",
)


def role_line(rng, role: str) -> str:
    return rng.choice(ROLE_FRAMES) % {"role": role,
                                      "about": cat.ROLE_ABOUT.get(role, "")}


DESTINY_FRAMES = (
    "Жизнь его вышла такой формы: %(key)s — %(about)s.",
    "Судьба его из тех, что зовут «%(key)s»: %(about)s.",
)


def destiny_line(rng, key: str) -> str:
    return rng.choice(DESTINY_FRAMES) % {
        "key": key, "about": cat.DESTINIES_BY_KEY.get(key, "")}


# ---------------------------------------------------------------------------
# След
# ---------------------------------------------------------------------------

FOOT_FRAMES = {
    cat.FOOT_STATE: "после него осталась держава по имени %s",
    cat.FOOT_HOUSE: "после него остался род по имени %s",
    cat.FOOT_LAW: "после него остался закон: %s",
    cat.FOOT_FAITH: "после него осталась вера по имени %s",
    cat.FOOT_SCHOOL: "после него осталось учение: %s",
    cat.FOOT_CITY: "после него остался город по имени %s",
    cat.FOOT_FORT: "после него осталась крепость по имени %s",
    cat.FOOT_GUILD: "после него осталось товарищество по имени %s",
    cat.FOOT_CRAFT: "после него осталось ремесло: %s",
    cat.FOOT_SPELL: "после него остались чары: %s",
    cat.FOOT_THING: "после него осталась вещь по имени %s",
    cat.FOOT_KIN: "после него остались потомки: %s",
    cat.FOOT_FOES: "после него остались враги: %s",
    cat.FOOT_FRIENDS: "после него остались те, кто пошёл за ним: %s",
    cat.FOOT_CUSTOM: "после него остался обычай: %s",
    cat.FOOT_FEAST: "после него остался праздник по имени %s",
    cat.FOOT_STONE: "после него остался памятный камень: %s",
    cat.FOOT_WORK: "после него осталось написанное: %s",
    cat.FOOT_LEGEND: "после него осталось предание по имени %s",
    cat.FOOT_CURSE: "после него осталось проклятие: %s",
    cat.FOOT_UNDONE: "после него осталось неоконченное: %s",
}


def foot_line(kind: str, what: str) -> str:
    frame = FOOT_FRAMES.get(kind, "после него осталось: %s")
    return frame % what


# ---------------------------------------------------------------------------
# Шесть голосов
# ---------------------------------------------------------------------------

def voice_line(rng, voice: str, was: str) -> str:
    """Что говорит об этом каждый из шести голосов."""
    if voice == cat.AS_WAS:
        return was
    rows = cat.VOICE_TWIST.get(voice)
    return rng.choice(rows) if rows else was


DEEDS_AS_WAS = (
    "делал он то, что мог, и вышло не всё",
    "сделанного за ним числится меньше, чем сказано",
    "главное он сделал один раз и больше не повторил",
    "дел за ним много, и половина вышла боком",
    "он сделал ровно то, о чём его просили, и не больше",
)


# ---------------------------------------------------------------------------
# Пик жизни и аура
# ---------------------------------------------------------------------------

CLIMAX_FRAMES = (
    "Вершина его жизни — %(what)s (%(year)d год).",
    "Выше всего он поднялся в %(year)d году: %(what)s.",
)


def climax_line(rng, what: str, year: int) -> str:
    return rng.choice(CLIMAX_FRAMES) % {"what": what, "year": year}


def aura_line(key: str) -> str:
    return "%s: %s" % (cap(key), cat.AURAS_BY_KEY.get(key, ""))


__all__ = ["cap", "forms", "man_ref", "level_line", "review_line",
           "role_line", "destiny_line", "foot_line", "voice_line",
           "DEEDS_AS_WAS", "climax_line", "aura_line"]
