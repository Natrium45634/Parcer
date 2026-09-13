# -*- coding: utf-8 -*-
"""Пробуждение рас и жизнь племён.

В начале истории нет ни городов, ни стран — только племена. Они растут,
дробятся, расходятся по землям и лишь позже оседают (этим занимается
модуль founding).
"""

from __future__ import annotations

from .. import narrative
from .. import races as races_mod
from ..models import GONE
from ..timeline import Date

MIN_SPLIT_POPULATION = 320
TRIBE_CAPACITY = 1200.0

# Доли расколов по категориям рас. Без этого зверолюды и злые расы —
# самые плодовитые — вытеснили бы из летописи все прочие народы.
CATEGORY_SPLIT_WEIGHT = {
    races_mod.CIVILIZED: 0.5,
    races_mod.BEASTFOLK: 0.3,
    races_mod.EVIL: 0.2,
}
FIRST_TRIBE_MIN = 40
FIRST_TRIBE_MAX = 180


# ---------------------------------------------------------------------------
# Расписание пробуждений
# ---------------------------------------------------------------------------

def plan_awakenings(ctx) -> None:
    """Раскладывает расы по годам: кто когда впервые появится в мире."""
    world = ctx.world
    rng = ctx.rng("awakening", "plan")
    era_count = len(world.eras)

    for race in races_mod.RACES:
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


def tick_awakening(ctx, year: int) -> None:
    for race_id in ctx.schedule.get(year, ()):
        _awaken(ctx, races_mod.get_race(race_id), year)


def _awaken(ctx, race, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("awakening", race.id, year)
    region = ctx.pick_region(rng, race)
    if region is None:
        return

    awakening_date = Date(year, rng.randint(1, 7), rng.randint(1, 30))
    world.race_awakening[race.id] = year
    ctx.awakened.append(race)
    ctx.awakened_ids.add(race.id)
    if region is not None and not region.discovered_by:
        region.discovered_by = race.id

    title, text = narrative.race_awakening(rng, race, region)
    world.add_event(
        date=awakening_date, era_index=world.era_index_at(year),
        kind="race_awakening", title=title, text=text, importance=4,
        region_id=region.id, race_id=race.id,
    )

    count = rng.randint(2, 3)
    for i in range(count):
        spot = region if i == 0 else (ctx.pick_region(rng, race, near=region.id, spread=0.2) or region)
        found_tribe(ctx, race, spot, year, rng, first=(i == 0), after=awakening_date)


# ---------------------------------------------------------------------------
# Племена
# ---------------------------------------------------------------------------

def found_tribe(ctx, race, region, year: int, rng, first: bool = False,
                 parent=None, population: int = 0, after=None):
    world = ctx.world
    sex = "f" if rng.chance(0.42) else "m"
    title = ctx.title_for(race, "chief", sex)
    leader = ctx.make_figure(rng, race, year, role="вождь", region_id=region.id,
                             title=title, sex=sex)

    if not population:
        population = rng.randint(FIRST_TRIBE_MIN, FIRST_TRIBE_MAX)

    tribe = world.add_tribe(
        name=ctx.forge.tribe(rng, race), word=rng.choice(race.tribe_words),
        race_id=race.id, founded=ctx.date_in(rng, year, after), founder_id=leader.id,
        region_id=region.id, population=population, chief_id=leader.id,
        parent_id=parent.id if parent else "",
    )
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


def tick_tribes(ctx, year: int) -> None:
    """Раз в год — возможность появления нового племени (обычно откол)."""
    world = ctx.world
    spec = ctx.era_spec(year)
    if not world.active_tribes:
        return
    rate = ctx.rate(spec.tribe_rate)
    rng = ctx.rng("tribes", year)
    if not rng.chance(rate):
        return

    tribes_by_race = {}
    for tribe_id in world.active_tribes:
        race_id = world.tribes[tribe_id].race_id
        tribes_by_race[race_id] = tribes_by_race.get(race_id, 0) + 1

    by_category = {}
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.population < MIN_SPLIT_POPULATION:
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

    for tribe_id in list(world.active_tribes):
        tribe = world.tribes[tribe_id]
        race = races_mod.get_race(tribe.race_id)
        region = world.regions.get(tribe.region_id)
        capacity = TRIBE_CAPACITY * (region.capacity if region else 1.0)
        if race.category == races_mod.BEASTFOLK:
            capacity *= 1.4          # зверолюдам города не нужны, племена крупнее

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
