# -*- coding: utf-8 -*-
"""Народы внутри державы: титульные, покорённые, пришлые.

Страна редко бывает одного народа. Империя людей берёт горы дворфов —
и вот в ней уже два народа, а через век, взяв лес эльфов, три. Что будет
дальше, зависит от того, какова эта империя.

Здесь описано, как держава обходится с иными народами, и чем это для неё
оборачивается: от равных прав и мирного врастания до рабства, резни,
восстаний и смены титульного народа, когда вчерашнее меньшинство садится
на престол.
"""

from __future__ import annotations

from . import races as races_mod

# --- как держава обходится с иными народами ----------------------------
EQUAL = "равные права"
SUBJECTS = "подданство"
UNEQUAL = "неравные"
SLAVERY = "рабство"
PURGE = "истребление"

POLICY_ORDER = (EQUAL, SUBJECTS, UNEQUAL, SLAVERY, PURGE)

POLICY_NAMES = {
    EQUAL: "равные права",
    SUBJECTS: "подданство",
    UNEQUAL: "неравное положение",
    SLAVERY: "рабство",
    PURGE: "истребление",
}

POLICY_DESCRIPTIONS = {
    EQUAL: "иные народы здесь равны титульному: их знать садится в совет, "
           "их язык звучит на площадях",
    SUBJECTS: "иные народы — подданные: живут по своим обычаям, но власть "
              "им не принадлежит",
    UNEQUAL: "иные народы поражены в правах: подати выше, суд строже, "
             "оружие носить запрещено",
    SLAVERY: "иные народы обращены в рабство: их продают, ими платят, "
             "их считают скотом",
    PURGE: "иные народы подлежат искоренению: их города жгут, их имена "
           "вычёркивают",
}

# Насколько каждая политика растит обиду за десятилетие и насколько
# растворяет меньшинство в титульном народе.
POLICY_GRIEVANCE = {EQUAL: -0.035, SUBJECTS: 0.004, UNEQUAL: 0.030,
                    SLAVERY: 0.055, PURGE: 0.090}
# Врастание идёт веками и редко доходит до конца: большой народ не
# растворяется, как ни старайся, а малый теряет себя и без указов.
POLICY_ASSIMILATION = {EQUAL: 0.022, SUBJECTS: 0.010, UNEQUAL: 0.004,
                       SLAVERY: 0.002, PURGE: 0.0}
# Какую долю меньшинства держава изводит за десятилетие.
POLICY_BLEED = {EQUAL: 0.0, SUBJECTS: 0.0, UNEQUAL: 0.0,
                SLAVERY: 0.012, PURGE: 0.045}

# Народы, у которых обращение с чужими в крови.
CRUEL_TRAITS = ("работорговцы", "налётчики", "костоломы", "отравители",
                "почитатели войны", "людоеды")
KIND_TRAITS = ("торговцы", "хлебопашцы", "певцы леса", "звездочёты",
               "хранители рун", "строители дорог", "целители")

MIN_MINORITY_SHARE = 0.04       # ниже этого народ в державе не замечают
REVOLT_SHARE = 0.10             # с какой доли меньшинство способно подняться
TAKEOVER_SHARE = 0.45           # с какой доли оно может сесть на престол


def default_policy(rng, race, faith_alignment: float = 0.0,
                   dark_tilt: float = 0.0) -> str:
    """С чем держава начинает: от равных прав до искоренения.

    Решают нрав народа, вера державы и её собственный жребий. Орочья
    орда и светлый эльфийский дом относятся к чужим по-разному, но
    исключения бывают у обоих.
    """
    weights = {EQUAL: 2.0, SUBJECTS: 4.0, UNEQUAL: 2.0,
               SLAVERY: 0.5, PURGE: 0.15}

    cruel = sum(1 for trait in race.traits if trait in CRUEL_TRAITS)
    kind = sum(1 for trait in race.traits if trait in KIND_TRAITS)
    if cruel:
        weights[UNEQUAL] *= 1.0 + cruel * 0.8
        weights[SLAVERY] *= 1.0 + cruel * 2.2
        weights[PURGE] *= 1.0 + cruel * 1.6
        weights[EQUAL] *= 0.45
    if kind:
        weights[EQUAL] *= 1.0 + kind * 0.7
        weights[SUBJECTS] *= 1.15
        weights[SLAVERY] *= 0.4
        weights[PURGE] *= 0.25
    if race.category == races_mod.EVIL:
        weights[SLAVERY] *= 3.0
        weights[PURGE] *= 3.0
        weights[EQUAL] *= 0.2

    # Тёмная вера развязывает руки, светлая — связывает.
    if faith_alignment <= -2:
        weights[PURGE] *= 3.0
        weights[SLAVERY] *= 2.2
        weights[EQUAL] *= 0.3
    elif faith_alignment >= 2:
        weights[EQUAL] *= 2.2
        weights[PURGE] *= 0.2
        weights[SLAVERY] *= 0.35
    if dark_tilt > 0:
        weights[PURGE] *= 1.0 + dark_tilt
        weights[SLAVERY] *= 1.0 + dark_tilt * 0.7

    return rng.weighted([(key, max(0.01, value)) for key, value in weights.items()])


def harsher(policy: str) -> str:
    index = POLICY_ORDER.index(policy) if policy in POLICY_ORDER else 1
    return POLICY_ORDER[min(len(POLICY_ORDER) - 1, index + 1)]


def softer(policy: str) -> str:
    index = POLICY_ORDER.index(policy) if policy in POLICY_ORDER else 1
    return POLICY_ORDER[max(0, index - 1)]


def is_harsh(policy: str) -> bool:
    return policy in (UNEQUAL, SLAVERY, PURGE)


def describe(polity, world) -> str:
    """Строка о народах державы — для карточки и летописи."""
    if not polity.peoples:
        return ""
    total = float(sum(polity.peoples.values())) or 1.0
    rows = sorted(polity.peoples.items(), key=lambda pair: (-pair[1], pair[0]))
    parts = []
    for race_id, souls in rows:
        race = races_mod.RACES_BY_ID.get(race_id)
        if race is None or souls <= 0:
            continue
        mark = " (титульный)" if race_id == polity.race_id else ""
        parts.append("%s — %d (%.0f%%)%s"
                     % (race.name, souls, souls * 100.0 / total, mark))
    return "; ".join(parts)
