# -*- coding: utf-8 -*-
"""Ремёсла и открытия: чем век отличается от века.

Эпохи до сих пор различались темпом, но не умением: держава железного
века воевала тем же, чем племя на заре мира. Здесь появляется то, что
копится, — знание, у которого есть год, город и имя того, кто его
добыл.

Открытие делают в одном месте, а расходится оно по торговым путям: то,
что придумали за морем, приходит с купцами, а не само собой. Поэтому
держава без дорог и без гаваней отстаёт — и однажды встречает в поле
войско, вооружённое лучше.

Числа здесь — это множители, и они намеренно невелики: три открытия не
должны превращать княжество в непобедимое. Но десять — уже заметны.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- к чему относится ----------------------------------------------------
FIELD = "земля"
METAL = "металл"
WAR = "война"
SEA = "море"
BUILD = "строительство"
LORE = "знание"

FAMILY_NAMES = {
    FIELD: "Земля и хлеб", METAL: "Металл", WAR: "Война", SEA: "Море",
    BUILD: "Строительство", LORE: "Знание",
}


@dataclass(frozen=True)
class Craft:
    """Открытие: что даёт, когда возможно и на чём стоит."""

    key: str
    name: str
    family: str
    era_from: int = 0
    needs: tuple = ()          # без этого не придумаешь
    growth: float = 0.0        # прибавка к тому, сколько земля прокормит
    war: float = 0.0           # прибавка к выучке войска
    siege: float = 0.0         # прибавка под стенами
    sea: float = 0.0           # прибавка флоту
    trade: float = 0.0         # прибавка торговле
    weight: float = 1.0
    hard: float = 1.0          # насколько трудно додуматься
    notes: tuple = ()


CRAFTS = (
    # --- земля и хлеб ---------------------------------------------------
    Craft("plough", "тяжёлый плуг", FIELD, era_from=1, growth=0.10,
          weight=1.4, notes=("одна упряжка подымает то, что прежде не "
                             "поднимали втроём",
                             "под пашню уходят земли, которые считали "
                             "негодными")),
    Craft("rotation", "трёхполье", FIELD, era_from=2, needs=("plough",),
          growth=0.12, weight=1.2,
          notes=("поле отдыхает треть времени и родит вдвое",
                 "голодные годы перестают следовать один за другим")),
    Craft("watermill", "водяное колесо", FIELD, era_from=2, growth=0.09,
          trade=0.06, weight=1.1,
          notes=("мельница мелет за десятерых и не просит хлеба",
                 "у каждой реки заводится свой мельник и своя вражда")),
    Craft("irrigation", "отводные каналы", FIELD, era_from=1, growth=0.11,
          weight=1.0, notes=("воду ведут туда, где её отродясь не было",
                             "за канал спорят охотнее, чем за межу")),
    Craft("windmill", "ветряная мельница", FIELD, era_from=3,
          needs=("watermill",), growth=0.07, weight=0.8,
          notes=("там, где нет реки, теперь есть мельница",)),
    # --- металл ----------------------------------------------------------
    Craft("bronze", "выплавка бронзы", METAL, era_from=0, war=0.06,
          trade=0.05, weight=1.6,
          notes=("медь с оловом дают то, чего не даёт ни медь, ни олово",)),
    Craft("iron", "выплавка железа", METAL, era_from=1, needs=("bronze",),
          war=0.10, growth=0.05, weight=1.5,
          notes=("железо дешевле бронзы, и оружие получают все",
                 "с этого дня войско считают тысячами, а не сотнями")),
    Craft("steel", "закалка стали", METAL, era_from=2, needs=("iron",),
          war=0.12, weight=1.1,
          notes=("клинок держит удар, которого не держал прежний",)),
    Craft("furnace", "доменная печь", METAL, era_from=3, needs=("steel",),
          war=0.08, trade=0.10, weight=0.8,
          notes=("металл льют, а не куют, и льют помногу",)),
    # --- война -----------------------------------------------------------
    Craft("compositebow", "составной лук", WAR, era_from=1, war=0.08,
          weight=1.2, notes=("бьёт дальше, чем видит глаз",)),
    Craft("stirrup", "стремя", WAR, era_from=1, war=0.11, weight=1.3,
          notes=("всадник бьёт копьём с седла и остаётся в седле",
                 "конница из подмоги становится главной силой")),
    Craft("crossbow", "самострел", WAR, era_from=2, needs=("iron",),
          war=0.09, weight=1.0,
          notes=("мужику хватает недели выучки, чтобы бить рыцаря",)),
    Craft("siegetower", "осадная башня", WAR, era_from=1, siege=0.14,
          weight=1.1, notes=("стены перестают быть решающим доводом",)),
    Craft("trebuchet", "требушет", WAR, era_from=2, needs=("siegetower",),
          siege=0.18, weight=0.9,
          notes=("камень весом в быка летит на триста шагов",)),
    Craft("powder", "огневой порошок", WAR, era_from=4, needs=("furnace",),
          war=0.14, siege=0.22, weight=0.5,
          notes=("первый же залп решает спор о том, нужны ли стены",
                 "рыцарское сословие получает свой приговор")),
    # --- море ------------------------------------------------------------
    Craft("keel", "киль и прямой парус", SEA, era_from=0, sea=0.12,
          trade=0.06, weight=1.4,
          notes=("корабль идёт против ветра, а не только по нему",)),
    Craft("compass", "магнитная стрелка", SEA, era_from=2, sea=0.14,
          trade=0.10, weight=1.0,
          notes=("берег перестаёт быть обязательным",)),
    Craft("astrolabe", "астролябия", SEA, era_from=3, needs=("compass",),
          sea=0.12, weight=0.8,
          notes=("широту считают по звёздам и почти не ошибаются",)),
    Craft("caravel", "океанский корабль", SEA, era_from=3, needs=("keel",),
          sea=0.16, trade=0.12, weight=0.8,
          notes=("на таком уходят за край карты и иногда возвращаются",)),
    # --- строительство ---------------------------------------------------
    Craft("arch", "каменная арка", BUILD, era_from=1, growth=0.05,
          siege=0.05, weight=1.3,
          notes=("свод держит сам себя, и здания растут вверх",)),
    Craft("aqueduct", "акведук", BUILD, era_from=2, needs=("arch",),
          growth=0.12, weight=1.0,
          notes=("вода приходит в город сама и приходит чистой",
                 "города растут там, где прежде было негде жить")),
    Craft("mortar", "кладка на растворе", BUILD, era_from=1, siege=-0.08,
          growth=0.04, weight=1.2,
          notes=("стена держит удар, которого не держала сухая кладка",)),
    Craft("road", "мощёная дорога", BUILD, era_from=2, trade=0.14,
          war=0.04, weight=1.1,
          notes=("войско идёт втрое быстрее, и купцы за ним",)),
    # --- знание ----------------------------------------------------------
    Craft("paper", "бумага", LORE, era_from=2, trade=0.06, weight=1.1,
          notes=("грамота дешевеет, и писать начинают не только жрецы",)),
    Craft("print", "печатный станок", LORE, era_from=4, needs=("paper",),
          trade=0.10, growth=0.05, weight=0.5,
          notes=("книга перестаёт стоить деревню",
                 "ересь расходится быстрее, чем её успевают запрещать")),
    Craft("zero", "счёт с нулём", LORE, era_from=2, trade=0.09, weight=0.9,
          notes=("счетоводство перестаёт быть колдовством",)),
    Craft("quarantine", "карантин", LORE, era_from=3, growth=0.08,
          weight=0.9, notes=("запертый порт спасает больше жизней, чем "
                             "все лекари вместе",)),
    Craft("glass", "прозрачное стекло", LORE, era_from=3, trade=0.07,
          growth=0.04, weight=0.8,
          notes=("сквозь окно видно улицу, а сквозь стекло — звёзды",)),
)

CRAFTS_BY_KEY = {item.key: item for item in CRAFTS}


def available(known, era_index: int) -> list:
    """Что эта держава может открыть прямо сейчас."""
    out = []
    for craft in CRAFTS:
        if craft.key in known or craft.era_from > era_index:
            continue
        if any(need not in known for need in craft.needs):
            continue
        out.append((craft, craft.weight / max(0.4, craft.hard)))
    return out


def bonus(known, field: str) -> float:
    """Сумма прибавок по этому делу: множитель к тому, что было."""
    value = 0.0
    for key in known:
        craft = CRAFTS_BY_KEY.get(key)
        if craft is not None:
            value += getattr(craft, field, 0.0)
    return 1.0 + value


def level(known) -> int:
    """Грубая мера умелости: сколько открытий за державой."""
    return len([key for key in known if key in CRAFTS_BY_KEY])
