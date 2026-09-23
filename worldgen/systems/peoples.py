# -*- coding: utf-8 -*-
"""Пробуждение рас и жизнь племён.

В начале истории нет ни городов, ни стран — только племена. Они растут,
дробятся, расходятся по землям и лишь позже оседают (этим занимается
модуль founding).
"""

from __future__ import annotations

from . import tongues as tongues_mod
from .. import folk as folk_mod
from .. import mapworld
from .. import narrative
from .. import races as races_mod
from ..models import GONE
from ..timeline import Date

# Племя делится не по круглому числу, а когда земля под ним начинает
# тесниться: пока прокормиться можно, никто никуда не уходит. Раньше
# здесь стояло глухое «320», и племена всю первобытную эпоху топтались
# на трёх сотнях душ — до потолка земли (TRIBE_CAPACITY) они не доживали
# никогда, а мир за тысячу лет набирал едва десяток тысяч.
SPLIT_SHARE_OF_LAND = 0.30     # доля прокорма, после которой откалываются
MIN_SPLIT_POPULATION = 320     # и всё же меньше этого племя не делится
# Сколько душ кормит земля под одним племенем. Тысяча двести — это
# стойбище охотников, а не народ Первой эпохи: мир за первую тысячу лет
# набирал полтора десятка тысяч душ и выглядел пустым. В фэнтези народы
# не выводятся из зверей — их будят разом и целыми племенами, и земля
# под ними держит куда больше.
TRIBE_CAPACITY = 5200.0
# Землю делят все, кто на ней живёт: десять племён в одной долине
# прокормятся хуже, чем одно. Доля каждого падает как корень из их
# числа — земля всё же кормит тем больше, чем больше на ней рук.
CROWD_POWER = 0.55

# Доли расколов по категориям рас. Без этого зверолюды и злые расы —
# самые плодовитые — вытеснили бы из летописи все прочие народы.
CATEGORY_SPLIT_WEIGHT = {
    races_mod.CIVILIZED: 0.5,
    races_mod.BEASTFOLK: 0.3,
    races_mod.EVIL: 0.2,
}
# Народ просыпается народом, а не горсткой. Сорок душ — это семья,
# и первые пятьсот лет мира уходили на то, чтобы эта семья доросла до
# племени. В фэнтези народы не выводятся из зверей: их будят разом,
# целыми родами, и с первого же дня их тысячи.
FIRST_TRIBE_MIN = 520
FIRST_TRIBE_MAX = 2400


# ---------------------------------------------------------------------------
# Расписание пробуждений
# ---------------------------------------------------------------------------

def plan_awakenings(ctx) -> None:
    """Раскладывает расы по годам: кто когда впервые появится в мире.

    На настоящей карте расе может быть просто негде жить: мир без гор
    остаётся без дворфов, мир без болот — без ящеролюдов. Такие народы
    не просыпаются вовсе, и это честнее, чем селить их в чужой земле.
    """
    world = ctx.world
    rng = ctx.rng("awakening", "plan")
    era_count = len(world.eras)

    homeless = []
    for race in races_mod.RACES:
        if ctx.map is not None and mapworld.homeland_score(ctx.map, race) <= 0.0:
            homeless.append(race.name)
            continue
        index = min(race.first_era, era_count - 1)
        era = world.eras[index]
        # Появляются в первых двух третях своей эпохи.
        window = max(1, int(era.length * 0.66))
        year = era.start_year + rng.randint(0, window - 1)
        if index == 0 and race.first_era == 0:
            # Древнейшие расы приходят в мир почти сразу.
            year = era.start_year + rng.randint(0, max(1, int(era.length * 0.35)))
        ctx.schedule.setdefault(year, []).append(race.id)

    # Порядок внутри года фиксирован — детерминированность превыше всего.
    for year in ctx.schedule:
        ctx.schedule[year].sort()

    if homeless:
        world.notes["не пробудились"] = sorted(homeless)


def tick_awakening(ctx, year: int) -> None:
    for race_id in ctx.schedule.get(year, ()):
        _awaken(ctx, races_mod.get_race(race_id), year)


def _cradles(ctx, race, rng) -> list:
    """Где раса просыпается: один-три очага в лучших для неё землях.

    Очаги нарочно разносятся по карте. Два очага людей на разных берегах —
    это не одно племя, а два народа, которые за тысячу лет разойдутся
    настолько, что будут воевать между собой.
    """
    world = ctx.world
    scored = []
    for region in world.regions.values():
        if region.terrain not in race.terrains:
            continue
        rank = race.terrains.index(region.terrain)
        value = (1.0 / (1.0 + rank)) * (0.4 + region.habitat)
        if region.from_map:
            value *= 0.5 + region.fertility
        scored.append((value, region))
    if not scored:
        return []
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))

    # Сколько очагов: у многочисленных и расселяющихся рас их больше.
    limit = 1
    if len(scored) >= 3 and race.settles:
        limit = rng.weighted(((1, 2.0), (2, 3.0), (3, 1.6)))
    limit = min(limit, len(scored))

    chosen = [scored[0][1]]
    for _ in range(limit - 1):
        best, best_score = None, -1.0
        for value, region in scored:
            if region in chosen:
                continue
            # Чем дальше от уже выбранных очагов, тем лучше.
            apart = min(_gap(region, other) for other in chosen)
            score = value * (0.5 + min(3.0, apart) * 0.6)
            if score > best_score:
                best, best_score = region, score
        if best is None:
            break
        chosen.append(best)
    return chosen


def _gap(region, other) -> float:
    """Грубое расстояние между землями — по их координатам на карте."""
    return (abs(region.x - other.x) ** 2 + abs(region.y - other.y) ** 2) ** 0.5


def _awaken(ctx, race, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("awakening", race.id, year)
    cradles = _cradles(ctx, race, rng)
    if not cradles:
        # Подходящей земли нет — пусть народ появится хоть где-нибудь.
        region = ctx.pick_region(rng, race, known_only=False)
        if region is None:
            return
        cradles = [region]

    awakening_date = Date(year, rng.randint(1, 7), rng.randint(1, 30))
    world.race_awakening[race.id] = year
    ctx.awakened.append(race)
    ctx.awakened_ids.add(race.id)

    used_names = {folk.name for folk in world.folks.values()}
    for index, region in enumerate(cradles):
        world.discover_region(region, year, race_id=race.id)
        if not region.discovered_by:
            region.discovered_by = race.id

        name, kind = folk_mod.folk_name(rng, race, region, used_names)
        used_names.add(name)
        folk = world.add_folk(
            name=name, name_kind=kind, race_id=race.id,
            cradle_region=region.id, born=awakening_date,
            traits=folk_mod.folk_traits(rng, region))
        # Все народы расы сперва говорят на одном праязыке; расходятся
        # они потом, прожив врозь несколько веков.
        tongues_mod.attach(world, tongues_mod.proto_for(
            ctx, race, folk, year, awakening_date, rng), folk)

        if index == 0:
            title, text = narrative.race_awakening(rng, race, region)
            world.add_event(
                date=awakening_date, era_index=world.era_index_at(year),
                kind="race_awakening", title=title, text=text, importance=4,
                region_id=region.id, race_id=race.id)
        else:
            title, text = narrative.folk_awakening(rng, race, folk, region)
            world.add_event(
                date=awakening_date, era_index=world.era_index_at(year),
                kind="folk_awakening", title=title, text=text, importance=3,
                subjects=[folk.id], region_id=region.id, race_id=race.id)

        count = rng.randint(2, 3) if index == 0 else rng.randint(1, 2)
        for i in range(count):
            spot = region if i == 0 else (
                ctx.pick_region(rng, race, near=region.id, spread=0.2) or region)
            found_tribe(ctx, race, spot, year, rng, first=(index == 0 and i == 0),
                        after=awakening_date, folk=folk)
    ctx.spread_knowledge()


# ---------------------------------------------------------------------------
# Племена
# ---------------------------------------------------------------------------

def found_tribe(ctx, race, region, year: int, rng, first: bool = False,
                 parent=None, population: int = 0, after=None, folk=None):
    world = ctx.world
    sex = "f" if rng.chance(0.42) else "m"
    title = ctx.title_for(race, "chief", sex)
    leader = ctx.make_figure(rng, race, year, role="вождь", region_id=region.id,
                             title=title, sex=sex, folk=folk)

    if not population:
        population = rng.randint(FIRST_TRIBE_MIN, FIRST_TRIBE_MAX)

    hex_index = -1
    if ctx.map is not None:
        hex_index = ctx.map.place(region.id, rng, kind="tribe")

    tribe = world.add_tribe(
        name=ctx.forge.tribe(rng, race), word=rng.choice(race.tribe_words),
        race_id=race.id, founded=ctx.date_in(rng, year, after), founder_id=leader.id,
        region_id=region.id, population=population, chief_id=leader.id,
        parent_id=parent.id if parent else "", hex_index=hex_index,
        folk_id=(folk.id if folk is not None else
                 (parent.folk_id if parent is not None else "")),
    )
    leader.folk_id = tribe.folk_id
    if ctx.map is not None and hex_index >= 0:
        ctx.map.claim(hex_index, tribe.id)
    leader.home_id = tribe.id
    leader.roles.append("основатель племени")

    title_text, text = narrative.tribe_found(rng, tribe, leader, region, race,
                                             parent=parent, first=first)
    world.add_event(
        date=tribe.founded, era_index=world.era_index_at(year),
        kind="tribe_found", title=title_text, text=text,
        importance=3 if first else 1,
        actors=[leader.id], subjects=[tribe.id], region_id=region.id,
        race_id=race.id,
    )
    return tribe


def _crowding(world) -> dict:
    """Сколько племён сидит на каждой земле — считается раз за такт."""
    counts = {}
    for tribe_id in world.active_tribes:
        region_id = world.tribes[tribe_id].region_id
        counts[region_id] = counts.get(region_id, 0) + 1
    return counts


def _tribe_capacity(ctx, tribe, crowd: int, year: int) -> float:
    """Сколько душ кормит земля под этим племенем.

    Ёмкость земли делится между всеми, кто на ней сидит, и на неё же
    ложится судьба мира: в годы, когда мир кормит плохо, племена мельчают
    сами собой, а не мрут по броску костей.
    """
    world = ctx.world
    race = races_mod.get_race(tribe.race_id)
    region = world.regions.get(tribe.region_id)
    capacity = TRIBE_CAPACITY * (region.capacity if region else 1.0)
    if race.category == races_mod.BEASTFOLK:
        capacity *= 1.4          # зверолюдам города не нужны, племена крупнее
    capacity *= ctx.fate_bounty(year)
    return max(1.0, capacity / (max(1, crowd) ** CROWD_POWER))


def _split_at(ctx, tribe, crowd: int, year: int) -> int:
    """Сколько душ должно набраться, чтобы племя раскололось.

    Считается от того, сколько народу кормит эта земля: на равнине
    расходятся поздно и большими родами, в тундре — рано и малыми.
    """
    capacity = _tribe_capacity(ctx, tribe, crowd, year)
    return max(MIN_SPLIT_POPULATION, int(capacity * SPLIT_SHARE_OF_LAND))


def tick_tribes(ctx, year: int) -> None:
    """Раз в год — возможность появления новых племён (обычно отколов).

    Раскол — дело каждого племени, а не мира: пока племя одно, новое
    появляется редко, а когда их четыре десятка, за год расходится
    несколько. Прежде бросок был один на весь мир, и племена прибывали
    по одному в год, как бы ни был велик и пуст мир вокруг.
    """
    world = ctx.world
    spec = ctx.era_spec(year)
    if not world.active_tribes:
        return
    rate = ctx.rate(spec.tribe_rate)
    rng = ctx.rng("tribes", year)
    tries = 1 + len(world.active_tribes) // 10
    for _ in range(min(6, tries)):
        if not rng.chance(rate):
            continue
        _split_once(ctx, world, rng, year)


def _split_once(ctx, world, rng, year: int) -> None:
    """Одно племя отпускает часть своих в новую землю."""
    crowding = _crowding(world)
    tribes_by_race = {}
    for tribe_id in world.active_tribes:
        race_id = world.tribes[tribe_id].race_id
        tribes_by_race[race_id] = tribes_by_race.get(race_id, 0) + 1

    by_category = {}
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        crowd = crowding.get(tribe.region_id, 1)
        if tribe.population < _split_at(ctx, tribe, crowd, year):
            continue
        category = races_mod.get_race(tribe.race_id).category
        weight = float(tribe.population) / (
            1.0 + tribes_by_race.get(tribe.race_id, 0) * 0.35)
        by_category.setdefault(category, []).append((tribe, weight))
    if not by_category:
        return

    # Сначала выбираем категорию, потом племя внутри неё.
    category = rng.weighted([(key, CATEGORY_SPLIT_WEIGHT.get(key, 0.3))
                             for key in sorted(by_category)])
    parent = rng.weighted(by_category[category])
    race = races_mod.get_race(parent.race_id)
    share = rng.uniform(0.25, 0.45)
    moving = int(parent.population * share)
    if moving < 30:
        return
    parent.population -= moving

    region = ctx.pick_region(rng, race, near=parent.region_id, spread=0.35)
    if region is None:
        region = world.regions[parent.region_id]
    found_tribe(ctx, race, region, year, rng, parent=parent, population=moving)


# ---------------------------------------------------------------------------
# Рост и угасание (раз в несколько лет)
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    rng = ctx.rng("tribe_upkeep", year)

    crowding = _crowding(world)
    for tribe_id in list(world.active_tribes):
        tribe = world.tribes[tribe_id]
        race = races_mod.get_race(tribe.race_id)
        capacity = _tribe_capacity(ctx, tribe,
                                   crowding.get(tribe.region_id, 1), year)

        growth = ctx.growth(race.growth, tribe.region_id) * period
        population = tribe.population
        population += population * growth * (1.0 - population / capacity)
        population *= rng.uniform(0.985, 1.02)
        tribe.population = max(0, int(population))

        if tribe.population < 25 or rng.chance(0.0022 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            world.end_tribe(tribe, date, "угасание", GONE)
            world.add_event(
                date=date, era_index=world.era_index_at(year), kind="tribe_end",
                title="Конец племени: %s" % tribe.name,
                text=narrative.tribe_end_text(rng, tribe), importance=1,
                subjects=[tribe.id], region_id=tribe.region_id,
                race_id=tribe.race_id,
            )
