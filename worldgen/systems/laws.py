# -*- coding: utf-8 -*-
"""Реформы держав: чем правление остаётся в памяти, кроме войн.

Государь, умеющий править, однажды меняет не границу, а порядок: вводит
единую монету, записывает закон, отпускает рабов, запрещает знати
воевать между собой. Это стоит ему части знати и части казны, зато
держава после него живёт иначе.

Удачная реформа не остаётся в одной державе. Соседи перенимают то, что у
других вышло, и через век порядок становится общим — а первого поминают
и через тысячу лет.
"""

from __future__ import annotations

from .. import history
from .. import laws as laws_mod
from .. import narrative_laws as texts
from .. import nations as pol
from .. import races as races_mod
from .. import rulers as rulers_mod
from ..models import ACTIVE

REFORM_RATE = 0.045         # шанс, что держава за такт что-то переменит
COPY_RATE = 0.12            # и что переймёт порядок у соседа
FAMOUS_AT = 6               # со скольких держав порядок считается общим
MIN_CITIES = 2


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("laws", year)
    era_index = world.era_index_at(year)
    scale = period / 10.0

    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        if polity.status != ACTIVE or polity.interregnum:
            continue
        if len(polity.settlement_ids) < MIN_CITIES:
            continue
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states:
            continue
        # Реформу проводит тот, кто умеет править: у воина руки в другом.
        urge = REFORM_RATE * scale * rulers_mod.stewardship(world, polity)
        urge *= max(0.35, 1.0 - polity.weariness)
        if rng.chance(min(0.4, urge)):
            _reform(ctx, polity, era_index, year, rng)
        elif rng.chance(COPY_RATE * scale):
            _copy(ctx, polity, era_index, year, rng)


# Беды, на которые отвечают порядком: свежая, но уже прожитая.
TROUBLE_KINDS = (history.HUNGER, history.SHAME, history.YOKE, history.LOSS,
                 history.DREAD)
TROUBLE_AGE = 120


def _trouble(ctx_world, polity, year: int):
    """Самая тяжёлая свежая беда державы — или ничего."""
    best, best_power = None, 0.25
    for kind in TROUBLE_KINDS:
        for fact in ctx_world.facts_of(polity.id, year, kind):
            if year - fact.year > TROUBLE_AGE:
                continue
            value = fact.power(year)
            if value > best_power:
                best, best_power = fact, value
    return best


def _reform(ctx, polity, era_index: int, year: int, rng) -> None:
    world = ctx.world
    options = laws_mod.possible(polity, era_index, set(polity.known))
    if not options:
        return
    reform = rng.weighted(options)
    ruler = world.figures.get(polity.ruler_id)
    date = ctx.date_in(rng, year)
    _apply(ctx, polity, reform, year)

    record = world.law_of(reform.key)
    first = record is None
    if first:
        record = world.add_law(
            key=reform.key, name=reform.name, family=reform.family,
            made=date, polity_id=polity.id,
            ruler_id=ruler.id if ruler is not None else "",
            race_id=polity.race_id, copied_by=[polity.id])
    elif polity.id not in record.copied_by:
        record.copied_by.append(polity.id)

    title, text = texts.reform_made(rng, reform, polity, ruler)
    # Порядок заводят не от хорошей жизни: если за державой числится
    # свежая беда, летопись помнит, что реформа была ответом на неё.
    trouble = _trouble(world, polity, year)
    event = world.add_event(
        date=date, era_index=era_index, kind="reform", title=title,
        text=text, importance=4 if first else 3,
        actors=[ruler.id] if ruler is not None else [],
        subjects=[record.id, polity.id],
        region_id=polity.region_ids[0] if polity.region_ids else "",
        race_id=polity.race_id,
        facts=[trouble.id] if trouble is not None else [],
        causes=[trouble.event_id] if trouble is not None
        and trouble.event_id else [],
        trace=history.trace_of(4 if first else 3))
    if ruler is not None:
        ruler.deeds.append(event.id)
    _maybe_famous(ctx, record, year, date, rng)


def _copy(ctx, polity, era_index: int, year: int, rng) -> None:
    """Порядок, удавшийся соседям, перенимают — не сразу и не целиком."""
    world = ctx.world
    options = []
    for other_id in world.active_polities:
        if other_id == polity.id:
            continue
        other = world.polities[other_id]
        if not other.reforms or world.war_between(polity.id, other.id):
            continue
        near = _neighbours(world, polity, other)
        if not near:
            continue
        for key in other.reforms:
            if key in polity.reforms:
                continue
            reform = laws_mod.REFORMS_BY_KEY.get(key)
            if reform is None or reform.era_from > era_index:
                continue
            if any(need not in polity.known for need in reform.needs):
                continue
            if key == "freedom" and polity.policy != pol.SLAVERY:
                continue
            options.append(((reform, other), near))
    if not options:
        return
    reform, source = rng.weighted(options)
    _apply(ctx, polity, reform, year)
    record = world.law_of(reform.key)
    if record is not None and polity.id not in record.copied_by:
        record.copied_by.append(polity.id)
    date = ctx.date_in(rng, year)
    title, text = texts.reform_copied(rng, reform, polity, source)
    world.add_event(
        date=date, era_index=era_index, kind="reform_copied", title=title,
        text=text, importance=2, subjects=[polity.id],
        region_id=polity.region_ids[0] if polity.region_ids else "",
        race_id=polity.race_id)
    if record is not None:
        _maybe_famous(ctx, record, year, date, rng)


def _apply(ctx, polity, reform, year: int) -> None:
    """Что реформа меняет в самой державе, помимо записи в летописи."""
    world = ctx.world
    polity.reforms.append(reform.key)
    if reform.key == "freedom":
        polity.policy = pol.SUBJECTS
        polity.policy_since = year
        for race_id in list(polity.grievance):
            polity.grievance[race_id] = max(
                0.0, polity.grievance[race_id] - 0.35)
    elif reform.key == "equal":
        polity.policy = pol.EQUAL
        polity.policy_since = year
        for race_id in list(polity.grievance):
            polity.grievance[race_id] = max(
                0.0, polity.grievance[race_id] - 0.25)
    elif reform.key == "tolerance":
        for race_id in list(polity.grievance):
            polity.grievance[race_id] = max(
                0.0, polity.grievance[race_id] - 0.15)
    # Знать отзывается на всякий порядок, который её ограничивает.
    if reform.nobles:
        for house in world.houses_of_polity(polity):
            house.discontent = max(0.0, min(2.0, house.discontent
                                            + reform.nobles))


def _maybe_famous(ctx, record, year: int, date, rng) -> None:
    """Порядок, дошедший до многих держав, становится общим."""
    world = ctx.world
    if record.famous or len(record.copied_by) < FAMOUS_AT:
        return
    record.famous = True
    reform = laws_mod.REFORMS_BY_KEY.get(record.key)
    first = world.polities.get(record.polity_id)
    if reform is None or first is None:
        return
    title, text = texts.reform_famous(rng, reform, first,
                                      len(record.copied_by))
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="reform_common",
        title=title, text=text, importance=4,
        subjects=[record.id, first.id], race_id=record.race_id)


def _neighbours(world, polity, other) -> float:
    """Насколько близко держава к чужому порядку: торгуют ли, граничат ли."""
    for route_id in polity.routes:
        route = world.routes.get(route_id)
        if route is None or route_id not in world.active_routes:
            continue
        if other.id in (route.seller_id, route.buyer_id):
            return 1.0
    reach = set()
    for region_id in polity.region_ids:
        region = world.regions.get(region_id)
        if region is not None:
            reach.update(region.neighbors)
    if any(region_id in reach for region_id in other.region_ids):
        return 0.6
    return 0.0


# ---------------------------------------------------------------------------
# Что порядки дают
# ---------------------------------------------------------------------------

def order_edge(polity) -> float:
    """Насколько крепче держится престол: ниже единицы — крепче."""
    value = laws_mod.bonus(polity.reforms if polity is not None else (),
                           "order")
    return max(0.4, 2.0 - value)


def growth_edge(polity) -> float:
    return laws_mod.bonus(polity.reforms if polity is not None else (),
                          "growth")


def war_edge(polity) -> float:
    return laws_mod.bonus(polity.reforms if polity is not None else (), "war")


def lore_edge(polity) -> float:
    return laws_mod.bonus(polity.reforms if polity is not None else (), "lore")


__all__ = ["upkeep", "order_edge", "growth_edge", "war_edge", "lore_edge"]
