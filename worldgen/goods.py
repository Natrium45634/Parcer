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


# Промысел расы — то, чем народ славен независимо от земли. Дворф и на
# равнине останется рудознатцем: он найдёт болотное железо там, где
# человек пройдёт мимо. Эльф и в степи разведёт сад.
#
# Это не про землю, а про руки: числа здесь вдвое-втрое меньше, чем у
# местности, и с голой пустыни дворф хлеба не снимет. Но там, где земля
# и промысел сходятся — дворфы в горах, эльфы в лесу, — получается то,
# чем эта держава живёт и чем её знают у соседей.
RACE_YIELD = {
    "human":      {GRAIN: 0.30, TIMBER: 0.12, WOOL: 0.10},
    "dwarf":      {METAL: 0.45, STONE: 0.35, GEMS: 0.25},
    "elf":        {WINE: 0.30, TIMBER: 0.25, REAGENTS: 0.25, FURS: 0.12},
    "high_elf":   {REAGENTS: 0.45, GEMS: 0.20, WINE: 0.15},
    "dark_elf":   {REAGENTS: 0.40, GEMS: 0.15, SPICE: 0.12},
    "catfolk":    {SPICE: 0.35, WOOL: 0.15, GEMS: 0.10},
    "wolfkin":    {FURS: 0.35, MEAT: 0.25},
    "bearkin":    {WINE: 0.25, FURS: 0.20, REAGENTS: 0.18, MEAT: 0.15},
    "foxkin":     {REAGENTS: 0.25, FURS: 0.20, WINE: 0.15},
    "birdkin":    {SPICE: 0.20, WOOL: 0.15, FISH: 0.12},
    "lizardfolk": {FISH: 0.30, REAGENTS: 0.18, MEAT: 0.15},
    "serpentfolk": {REAGENTS: 0.40, SPICE: 0.15},
    "toadfolk":   {FISH: 0.30, REAGENTS: 0.25},
    "turtlefolk": {FISH: 0.40, SALT: 0.18},
    "crabfolk":   {SALT: 0.40, FISH: 0.30, GEMS: 0.10},
    "orc":        {MEAT: 0.25, METAL: 0.15},
    "goblin":     {METAL: 0.15, FURS: 0.12},
    "troll":      {STONE: 0.30, MEAT: 0.15},
    "ogre":       {MEAT: 0.30, STONE: 0.15},
    "kobold":     {METAL: 0.30, GEMS: 0.15, STONE: 0.15},
    "gnoll":      {MEAT: 0.30, FURS: 0.20},
}

# Ремесло меняет то, что земля и руки дают. Две державы одной расы на
# одной и той же земле были неразличимы до этой таблицы: считалось, что
# хозяйство зависит только от почвы и от крови. А оно зависит ещё и от
# того, что в державе успели придумать и перенять.
CRAFT_YIELD = {
    "plough":     {GRAIN: 0.22},
    "rotation":   {GRAIN: 0.18, MEAT: 0.10},
    "watermill":  {GRAIN: 0.16},
    "irrigation": {GRAIN: 0.26},
    "windmill":   {GRAIN: 0.14},
    "bronze":     {METAL: 0.14},
    "iron":       {METAL: 0.22},
    "steel":      {METAL: 0.26},
    "furnace":    {METAL: 0.34, STONE: 0.10},
    "keel":       {FISH: 0.18, SPICE: 0.10},
    "compass":    {SPICE: 0.14, FISH: 0.08},
    "astrolabe":  {SPICE: 0.16},
    "caravel":    {SPICE: 0.30, FISH: 0.12},
    "arch":       {STONE: 0.14},
    "aqueduct":   {GRAIN: 0.14, STONE: 0.10},
    "mortar":     {STONE: 0.20},
    "road":       {SALT: 0.12, WOOL: 0.10},
    "paper":      {REAGENTS: 0.10},
    "glass":      {GEMS: 0.20, REAGENTS: 0.12},
    "quarantine": {MEAT: 0.10},
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


def craft_bonus(known) -> dict:
    """Что добавляет к хозяйству то, что держава успела придумать."""
    out = {}
    for key in known or ():
        for good, value in CRAFT_YIELD.get(key, {}).items():
            out[good] = out.get(good, 0.0) + value
    return out


def race_bonus(race) -> dict:
    """Что народ даёт своими руками, где бы он ни жил."""
    if race is None:
        return {}
    out = dict(RACE_YIELD.get(race.id, {}))
    # Промыслы, вписанные расе как черты, работают наравне с народными.
    for trait in race.traits:
        for good, value in TRAIT_YIELD.get(trait, {}).items():
            out[good] = out.get(good, 0.0) + value * 0.5
    return out


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
        hands = race_bonus(races_mod.RACES_BY_ID.get(settlement.race_id))
        craft = craft_bonus(polity.known)
        for source in (rates, extra, hands, craft):
            for good, rate in source.items():
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


# ---------------------------------------------------------------------------
# Чем держава живёт
# ---------------------------------------------------------------------------

# Во сколько ценится товар против хлеба. Еда кормит, но богатеют не с неё:
# горсть самоцветов стоит обоза зерна, и на этом стоят все караванные пути.
GOOD_WORTH = {
    GRAIN: 1.0, MEAT: 1.3, FISH: 1.0, TIMBER: 1.1, STONE: 1.0,
    METAL: 2.4, SALT: 1.6, WOOL: 1.4, FURS: 3.0, WINE: 2.6,
    SPICE: 4.5, GEMS: 7.0, REAGENTS: 6.0,
}


def mainstay(balance: dict, limit: int = 3) -> list:
    """Чем держава живёт: товары, на которых держится её достаток.

    Считается не по тому, чего больше всего снимают, а по тому, что
    приносит: два обоза самоцветов весят больше, чем десять обозов
    камня, и держава знаменита именно ими.
    """
    rows = []
    for good, (have, need) in balance.items():
        spare = have - need
        if spare <= 0:
            continue
        rows.append((good, spare * GOOD_WORTH.get(good, 1.0)))
    if not rows:
        return []
    total = sum(value for _, value in rows) or 1.0
    rows.sort(key=lambda pair: -pair[1])
    return [(good, round(value / total, 3)) for good, value in rows[:limit]]


def wealth(balance: dict, souls: int) -> float:
    """Достаток на душу: сколько лишнего добра приходится на человека."""
    if souls <= 0:
        return 0.0
    spare = 0.0
    for good, (have, need) in balance.items():
        extra = have - need
        if extra > 0:
            spare += extra * GOOD_WORTH.get(good, 1.0)
    return round(spare / float(souls), 3)


# Достаток считается не в чём-то абсолютном, а относительно мира. Мир,
# где все освоили доменную печь, богаче первобытного в разы, и мерить их
# одной меркой бессмысленно: «богатой» держава бывает среди соседей.
WEALTH_STEPS = ((0.55, "бедно"), (0.85, "небогато"), (1.30, "в достатке"),
                (2.00, "богато"))


def wealth_label(value: float, middle: float = 0.0) -> str:
    """Достаток словом. middle — середина по миру; без неё судят грубо."""
    if middle <= 0:
        middle = 6.0
    share = value / float(middle)
    for edge, name in WEALTH_STEPS:
        if share < edge:
            return name
    return "очень богато"


def middle_wealth(world) -> float:
    """Достаток середняка этого мира — мерка, с которой сравнивают."""
    values = []
    for polity_id in world.active_polities:
        polity = world.polities.get(polity_id)
        if polity is None:
            continue
        souls = polity_souls(world, polity)
        if souls <= 0:
            continue
        values.append(wealth(polity_balance(world, polity), souls))
    if not values:
        return 0.0
    values.sort()
    return values[len(values) // 2]


def polity_souls(world, polity) -> int:
    total = 0
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is not None and settlement.status == ACTIVE:
            total += world.settlement_realm(settlement)
    return total


# Творительный падеж товаров: «живёт самоцветами», а не «живёт самоцветы».
# Товары не придумываются, а лежат списком, поэтому склонять их можно.
GOOD_INSTR = {
    GRAIN: "хлебом", MEAT: "скотом", FISH: "рыбой", TIMBER: "лесом",
    STONE: "камнем", METAL: "металлом", SALT: "солью", WOOL: "шерстью",
    FURS: "мехами", WINE: "вином", SPICE: "пряностями", GEMS: "самоцветами",
    REAGENTS: "чародейными снадобьями",
}


def instr(good: str) -> str:
    return GOOD_INSTR.get(good, good)


def living_line(balance: dict, souls: int, middle: float = 0.0) -> str:
    """Одной строкой: чем держава живёт и насколько ей хватает.

    «живёт самоцветами (46%) и металлом (31%); достаток: богато»
    """
    rows = mainstay(balance, 3)
    if not rows:
        return "живёт с того, что вырастит, и лишнего не имеет"
    parts = ["%s (%.0f%%)" % (instr(good), share * 100)
             for good, share in rows]
    if len(parts) > 1:
        head = ", ".join(parts[:-1]) + " и " + parts[-1]
    else:
        head = parts[0]
    return "живёт %s; достаток: %s" % (
        head, wealth_label(wealth(balance, souls), middle))
