# -*- coding: utf-8 -*-
"""Чем земля богата и чего ей не хватает.

Дворфы сидят на руде, но хлеб у них не растёт. Люди пашут равнину, а
металл им взять негде. Эльфы живут в лесу, где нет ни того, ни другого,
зато есть всё остальное. Отсюда и начинается торговля — не от доброй воли,
а от нужды.

Здесь описано, что земля даёт и что народу нужно. Дальше этим занимается
``systems/trade.py``: считает баланс державы, ищет, у кого взять
недостающее, и прокладывает путь — настоящий, по гексам, в обход хребтов.
"""

from __future__ import annotations

from . import races as races_mod
from .models import ACTIVE

# --- что бывает --------------------------------------------------------
# staple: без этого голодают. strategic: без этого слабеет войско.
GRAIN = "хлеб"
MEAT = "скот"
FISH = "рыба"
TIMBER = "лес"
STONE = "камень"
METAL = "металл"
SALT = "соль"
WOOL = "шерсть"
FURS = "меха"
WINE = "вино"
SPICE = "пряности"
GEMS = "самоцветы"
REAGENTS = "чародейные снадобья"

GOODS = (GRAIN, MEAT, FISH, TIMBER, STONE, METAL, SALT, WOOL, FURS, WINE,
         SPICE, GEMS, REAGENTS)
STAPLES = (GRAIN, MEAT, FISH)        # еда: без неё мрут
STRATEGIC = (METAL, TIMBER, STONE)   # без этого не строят и не воюют
LUXURY = (WINE, SPICE, GEMS, FURS, REAGENTS)

GOOD_NOTES = {
    GRAIN: "зерно", MEAT: "мясо и молоко", FISH: "рыба и соль моря",
    TIMBER: "корабельный лес", STONE: "тёсаный камень", METAL: "руда и железо",
    SALT: "соль", WOOL: "шерсть и полотно", FURS: "меха", WINE: "вино и масло",
    SPICE: "пряности", GEMS: "самоцветы", REAGENTS: "чародейные снадобья",
}

# Что даёт местность. Число — сколько товара с одной души населения.
TERRAIN_YIELD = {
    races_mod.PLAIN: {GRAIN: 1.30, MEAT: 0.35, WOOL: 0.15},
    races_mod.STEPPE: {MEAT: 1.10, WOOL: 0.55, GRAIN: 0.30},
    races_mod.HILLS: {WOOL: 0.70, WINE: 0.45, STONE: 0.35, MEAT: 0.40,
                      METAL: 0.20},
    races_mod.FOREST: {TIMBER: 1.00, FURS: 0.45, MEAT: 0.25, GRAIN: 0.20},
    races_mod.JUNGLE: {SPICE: 0.80, TIMBER: 0.60, REAGENTS: 0.20},
    races_mod.COAST: {FISH: 1.10, SALT: 0.55, GRAIN: 0.35, TIMBER: 0.20},
    races_mod.ISLANDS: {FISH: 1.20, SALT: 0.45, SPICE: 0.20},
    races_mod.SWAMP: {FISH: 0.45, REAGENTS: 0.40, TIMBER: 0.25},
    races_mod.TUNDRA: {FURS: 0.90, MEAT: 0.35, FISH: 0.25},
    races_mod.DESERT: {SALT: 0.70, GEMS: 0.25, SPICE: 0.20},
    races_mod.MOUNTAIN: {STONE: 1.00, METAL: 0.85, GEMS: 0.30, MEAT: 0.15},
    races_mod.UNDERGROUND: {METAL: 1.20, STONE: 0.90, GEMS: 0.50},
}

# Сколько нужно на душу. Еда — в сумме; прочее — сколько просит хозяйство.
NEED_PER_SOUL = {GRAIN: 0.55, MEAT: 0.20, FISH: 0.15,
                 TIMBER: 0.22, STONE: 0.16, METAL: 0.24, SALT: 0.10,
                 WOOL: 0.12}

# Промыслы народа добавляют к тому, что даёт земля.
TRAIT_YIELD = {
    "рыбаки": {FISH: 0.45}, "китобои": {FISH: 0.35, SALT: 0.15},
    "солевары": {SALT: 0.45}, "горняки": {METAL: 0.40, STONE: 0.25},
    "рудознатцы": {METAL: 0.45, GEMS: 0.20}, "камнетёсы": {STONE: 0.45},
    "древоделы": {TIMBER: 0.40}, "смолокуры": {TIMBER: 0.30},
    "охотники": {FURS: 0.35, MEAT: 0.20}, "звероловы": {FURS: 0.40},
    "оленеводы": {MEAT: 0.40, FURS: 0.25}, "коневоды": {MEAT: 0.45},
    "овцеводы": {WOOL: 0.45, MEAT: 0.20}, "хлебопашцы": {GRAIN: 0.45},
    "виноградари": {WINE: 0.50}, "медовары": {WINE: 0.30},
    "травники": {REAGENTS: 0.35}, "знахари": {REAGENTS: 0.30},
    "грибоводы": {GRAIN: 0.25}, "караванщики": {SPICE: 0.25},
    "мореходы": {FISH: 0.20, SPICE: 0.15}, "птицеловы": {MEAT: 0.20},
    "ныряльщики": {GEMS: 0.25, FISH: 0.20}, "козопасы": {MEAT: 0.30, WOOL: 0.25},
    "лодочники": {FISH: 0.25}, "мельники": {GRAIN: 0.30},
    "виноделы": {WINE: 0.45}, "древолазы": {SPICE: 0.20, TIMBER: 0.20},
    "болотники": {REAGENTS: 0.25, FISH: 0.15},
    "костерезы": {FURS: 0.20}, "следопыты": {FURS: 0.25},
}


# Немного камня, леса и руды найдётся почти везде: валун у дороги, болотное
# железо, роща за околицей. Без этого нехватка у всех выходит стопроцентной,
# а должна быть степенью — одному не хватает чуть, другому нечем ковать.
BASELINE = {STONE: 0.06, METAL: 0.05, TIMBER: 0.08, GRAIN: 0.10,
            WOOL: 0.05, SALT: 0.04, MEAT: 0.06}


def region_yield(region) -> dict:
    """Что даёт земля с одной души населения."""
    out = dict(TERRAIN_YIELD.get(region.terrain, {GRAIN: 0.5}))
    for good, value in BASELINE.items():
        out[good] = max(out.get(good, 0.0), value)
    if not region.from_map:
        return out

    # Карта уточняет: где плодороднее, там и хлеба больше.
    fertile = 0.5 + region.fertility
    rich = 0.4 + region.richness * 1.4
    for good in (GRAIN, MEAT, WOOL, WINE):
        if good in out:
            out[good] *= fertile
    for good in (METAL, STONE, GEMS):
        if good in out:
            out[good] *= rich
    if region.river:
        out[GRAIN] = out.get(GRAIN, 0.0) + 0.25
        out[FISH] = out.get(FISH, 0.0) + 0.15
    if region.coastal:
        out[FISH] = out.get(FISH, 0.0) + 0.30
        out[SALT] = out.get(SALT, 0.0) + 0.15
    if abs(region.magic) >= 0.02:
        out[REAGENTS] = out.get(REAGENTS, 0.0) + abs(region.magic) * 3.0
    return {key: round(value, 3) for key, value in out.items() if value > 0.01}


def folk_bonus(folk) -> dict:
    """Что добавляет к достатку промысел народа."""
    out = {}
    if folk is None:
        return out
    for trait in folk.traits:
        for good, value in TRAIT_YIELD.get(trait, {}).items():
            out[good] = out.get(good, 0.0) + value
    return out


def polity_balance(world, polity) -> dict:
    """Баланс державы: сколько чего производит и сколько ей нужно.

    Возвращает {товар: (производство, нужда)}. Отрицательная разница —
    дефицит: его придётся покупать, отнимать или терпеть.
    """
    produced = {}
    souls = 0
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        region = world.regions.get(settlement.region_id)
        if region is None:
            continue
        realm = world.settlement_realm(settlement)
        souls += realm
        rates = region_yield(region)
        extra = folk_bonus(world.folks.get(settlement.folk_id))
        for good, rate in rates.items():
            produced[good] = produced.get(good, 0.0) + rate * realm
        for good, rate in extra.items():
            produced[good] = produced.get(good, 0.0) + rate * realm

    balance = {}
    for good in GOODS:
        need = NEED_PER_SOUL.get(good, 0.0) * souls
        have = produced.get(good, 0.0)
        if have <= 0 and need <= 0:
            continue
        balance[good] = (int(have), int(need))
    return balance


def shortages(balance: dict, threshold: float = 0.75) -> list:
    """Чего державе не хватает: товар и насколько остро, от 0 до 1."""
    out = []
    for good, (have, need) in balance.items():
        if need <= 0:
            continue
        ratio = have / float(need)
        if ratio < threshold:
            out.append((good, round(1.0 - ratio, 3)))
    out.sort(key=lambda pair: (-pair[1], pair[0]))
    return out


def surpluses(balance: dict, threshold: float = 1.35) -> list:
    """Чем держава может торговать: товар и насколько он лишний."""
    out = []
    for good, (have, need) in balance.items():
        if have <= 0:
            continue
        if need <= 0:
            out.append((good, 1.0))
            continue
        ratio = have / float(need)
        if ratio > threshold:
            out.append((good, round(min(3.0, ratio - 1.0), 3)))
    out.sort(key=lambda pair: (-pair[1], pair[0]))
    return out


def famine_pressure(balance: dict) -> float:
    """Насколько державе нечего есть, от 0 (сыта) до 1 (голод)."""
    have = sum(balance.get(good, (0, 0))[0] for good in STAPLES)
    need = sum(balance.get(good, (0, 0))[1] for good in STAPLES)
    if need <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - have / float(need)))
