# -*- coding: utf-8 -*-
"""Рода войск: кем воюет народ и где это помогает.

Войско — не однородная масса. Дворф выводит тяжёлую пехоту и осадные
машины, эльф — лучников и застрельщиков, степняк — конницу, а
болотный народ — зверей и отравленные дротики. Состав войска у каждого
народа свой и складывается из того, что о нём и так известно: из его
промыслов и из земель, в которых он живёт.

Местность решает не меньше. Конница на равнине стоит полутора себя, в
лесу — двух третей. Тяжёлая пехота в теснине непобедима и вязнет в
болоте. Поэтому дворф, встретивший степняка в горах, бьёт его при
любом раскладе сил, а в степи всё наоборот — и это видно в летописи.
"""

from __future__ import annotations

# --- рода войск ----------------------------------------------------------
FOOT = "пехота"
HEAVY = "тяжёлая пехота"
ARCHERS = "лучники"
HORSE = "конница"
SKIRMISH = "застрельщики"
SIEGE = "осадные машины"
MAGES = "чародеи"
BEASTS = "боевые звери"

KINDS = (FOOT, HEAVY, ARCHERS, HORSE, SKIRMISH, SIEGE, MAGES, BEASTS)

# Как род войск себя чувствует в разных землях. Чего нет в таблице —
# то и не мешает, и не помогает.
TERRAIN_BONUS = {
    HORSE: {"равнина": 1.35, "степь": 1.50, "пустыня": 1.20, "холмы": 0.95,
            "лес": 0.60, "джунгли": 0.50, "горы": 0.45, "болото": 0.45,
            "тундра": 1.05, "побережье": 0.95, "острова": 0.70,
            "подземелье": 0.35},
    HEAVY: {"горы": 1.25, "холмы": 1.15, "подземелье": 1.30, "равнина": 1.05,
            "болото": 0.65, "джунгли": 0.70, "пустыня": 0.80,
            "острова": 0.90},
    ARCHERS: {"лес": 1.35, "холмы": 1.25, "горы": 1.15, "джунгли": 1.15,
              "равнина": 0.90, "степь": 0.85, "подземелье": 0.80},
    SKIRMISH: {"лес": 1.30, "болото": 1.35, "джунгли": 1.35, "холмы": 1.15,
               "острова": 1.10, "равнина": 0.80, "степь": 0.75},
    FOOT: {"равнина": 1.05, "болото": 0.90, "горы": 0.95},
    SIEGE: {"равнина": 1.15, "побережье": 1.10, "горы": 0.70, "болото": 0.55,
            "джунгли": 0.60, "острова": 0.75},
    MAGES: {"подземелье": 1.15, "пустыня": 1.10},
    BEASTS: {"джунгли": 1.30, "болото": 1.25, "лес": 1.20, "тундра": 1.10,
             "пустыня": 0.85, "подземелье": 0.80},
}

# Что каждый род стоит сам по себе, помимо местности.
BASE_WORTH = {FOOT: 1.00, HEAVY: 1.30, ARCHERS: 1.10, HORSE: 1.25,
              SKIRMISH: 0.90, SIEGE: 0.85, MAGES: 1.55, BEASTS: 1.15}

# Насколько род войск полезен под стенами, а не в поле.
SIEGE_WORTH = {FOOT: 1.0, HEAVY: 1.15, ARCHERS: 1.05, HORSE: 0.45,
               SKIRMISH: 0.70, SIEGE: 2.20, MAGES: 1.40, BEASTS: 0.75}

# --- из чего складывается состав ----------------------------------------
# Промысел народа тянет войско в свою сторону.
TRAIT_MIX = {
    "лучники": {ARCHERS: 0.25},
    "следопыты": {ARCHERS: 0.10, SKIRMISH: 0.12},
    "воители": {HEAVY: 0.18, FOOT: 0.08},
    "берсерки": {HEAVY: 0.22, FOOT: 0.06},
    "танцоры клинка": {FOOT: 0.10, SKIRMISH: 0.14},
    "налётчики": {HORSE: 0.16, SKIRMISH: 0.12},
    "караванщики": {HORSE: 0.20},
    "кузнецы": {HEAVY: 0.14, SIEGE: 0.08},
    "камнерезы": {SIEGE: 0.16, HEAVY: 0.06},
    "рудознатцы": {SIEGE: 0.10, HEAVY: 0.06},
    "зодчие света": {SIEGE: 0.10, MAGES: 0.08},
    "строители дорог": {SIEGE: 0.10},
    "чародеи": {MAGES: 0.22},
    "тенемаги": {MAGES: 0.20, SKIRMISH: 0.06},
    "заклинатели": {MAGES: 0.16},
    "шаманы тины": {MAGES: 0.12, BEASTS: 0.08},
    "хранители рун": {MAGES: 0.12, HEAVY: 0.06},
    "звездочёты": {MAGES: 0.08},
    "загонщики": {BEASTS: 0.18},
    "хохочущие охотники": {BEASTS: 0.14, SKIRMISH: 0.08},
    "болотные охотники": {SKIRMISH: 0.16, BEASTS: 0.08},
    "ловушечники": {SKIRMISH: 0.16},
    "отравители": {SKIRMISH: 0.14},
    "ядотворцы": {SKIRMISH: 0.12, BEASTS: 0.06},
    "падальщики": {SKIRMISH: 0.12},
    "дубиноносцы": {FOOT: 0.16},
    "костоломы": {HEAVY: 0.14},
    "пожиратели": {BEASTS: 0.12, HEAVY: 0.08},
    "людоеды": {BEASTS: 0.10},
    "небесные дозорные": {SKIRMISH: 0.14, ARCHERS: 0.10},
    "мореходы": {SKIRMISH: 0.08},
    "хлебопашцы": {FOOT: 0.16},
    "рыболовы": {FOOT: 0.08, SKIRMISH: 0.06},
    "сторожа драконьих троп": {BEASTS: 0.12, HEAVY: 0.06},
    "певцы леса": {ARCHERS: 0.10, MAGES: 0.08},
    "лунные певцы": {MAGES: 0.10, ARCHERS: 0.06},
}

# Основа: то, что есть у всякого войска, пока промыслы его не перекроили.
BASE_MIX = {FOOT: 0.46, ARCHERS: 0.16, HEAVY: 0.14, HORSE: 0.10,
            SKIRMISH: 0.09, SIEGE: 0.03, MAGES: 0.01, BEASTS: 0.01}

# Земля, в которой народ живёт, тоже учит его воевать по-своему.
TERRAIN_MIX = {
    "степь": {HORSE: 0.16, ARCHERS: 0.06},
    "равнина": {HORSE: 0.08, FOOT: 0.06},
    "лес": {ARCHERS: 0.12, SKIRMISH: 0.08},
    "джунгли": {SKIRMISH: 0.12, BEASTS: 0.08},
    "болото": {SKIRMISH: 0.14, BEASTS: 0.06},
    "горы": {HEAVY: 0.10, ARCHERS: 0.08},
    "подземелье": {HEAVY: 0.14, SIEGE: 0.06},
    "холмы": {ARCHERS: 0.08, FOOT: 0.06},
    "пустыня": {HORSE: 0.12, SKIRMISH: 0.06},
    "тундра": {SKIRMISH: 0.08, ARCHERS: 0.06},
    "побережье": {FOOT: 0.08, SKIRMISH: 0.06},
    "острова": {SKIRMISH: 0.10, ARCHERS: 0.06},
}

_CACHE = {}


def composition(race) -> dict:
    """Состав войска народа: род войск -> доля. Сумма равна единице."""
    cached = _CACHE.get(race.id)
    if cached is not None:
        return cached

    mix = dict(BASE_MIX)
    for trait in race.traits:
        for kind, weight in TRAIT_MIX.get(trait, {}).items():
            mix[kind] = mix.get(kind, 0.0) + weight
    home = race.terrains[0] if race.terrains else ""
    for kind, weight in TERRAIN_MIX.get(home, {}).items():
        mix[kind] = mix.get(kind, 0.0) + weight * 0.6

    total = sum(mix.values()) or 1.0
    mix = {kind: round(value / total, 4) for kind, value in mix.items()
           if value > 0.004}
    total = sum(mix.values()) or 1.0
    mix = {kind: value / total for kind, value in mix.items()}
    _CACHE[race.id] = mix
    return mix


def worth(race, terrain: str = "", under_walls: bool = False) -> float:
    """Чего стоит войско этого народа на такой земле.

    Единица — обычное войско в обычном поле. Полтора — конница в степи
    или дворфы в теснине; две трети — та же конница в болоте.
    """
    mix = composition(race)
    value = 0.0
    for kind, share in mix.items():
        item = BASE_WORTH.get(kind, 1.0)
        if under_walls:
            item *= SIEGE_WORTH.get(kind, 1.0)
        else:
            item *= TERRAIN_BONUS.get(kind, {}).get(terrain, 1.0)
        value += share * item
    return max(0.45, min(2.0, value))


def main_arms(race, count: int = 2) -> list:
    """Чем этот народ воюет прежде всего."""
    mix = composition(race)
    rows = sorted(mix.items(), key=lambda pair: (-pair[1], pair[0]))
    return [kind for kind, share in rows[:count] if share >= 0.08]


def describe(race) -> str:
    """«тяжёлая пехота и осадные машины» — для летописи и справочников."""
    arms = main_arms(race)
    if not arms:
        return "ополчение"
    if len(arms) == 1:
        return arms[0]
    return "%s и %s" % (arms[0], arms[1])


def advantage(first_race, second_race, terrain: str) -> str:
    """Кому земля помогает больше — для одной строки в описании битвы."""
    ours = worth(first_race, terrain)
    theirs = worth(second_race, terrain)
    if ours >= theirs * 1.18:
        return "first"
    if theirs >= ours * 1.18:
        return "second"
    return ""
