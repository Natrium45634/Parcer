# -*- coding: utf-8 -*-
"""Открытия: как их делают и как они расходятся по свету.

Открытие делают там, где для него есть повод и возможность: в большом
городе богатой державы, а не в первой попавшейся деревне. Дальше оно
идёт не само — его везут купцы, привозят послы и переманенные мастера.
Держава без дорог и гаваней узнаёт о нём последней и однажды встречает
в поле войско, вооружённое лучше.
"""

from __future__ import annotations

from .. import crafts as crafts_mod
from .. import laws as laws_mod
from .. import narrative_crafts as texts
from .. import races as races_mod
from ..models import ACTIVE

DISCOVER_RATE = 0.035       # шанс, что держава за такт что-то откроет
SPREAD_RATE = 0.10          # и что переймёт у соседа по торговому пути
MIN_CITY = 1200


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("crafts", year)
    era_index = world.era_index_at(year)
    scale = period / 10.0

    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        if polity.status != ACTIVE:
            continue
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states:
            continue
        # Открывают там, где есть кому и на что: большой город, торговля,
        # спокойные времена.
        urge = DISCOVER_RATE * scale
        urge *= 0.5 + 0.5 * min(3.0, len(polity.settlement_ids) / 4.0)
        urge *= 1.0 + 0.12 * len(polity.routes)
        urge *= max(0.4, 1.0 - polity.hunger)
        # Школа и почта — это не украшение: там, где их завели, открывают
        # чаще.
        urge *= laws_mod.bonus(polity.reforms, "lore")
        if rng.chance(min(0.6, urge)):
            _discover(ctx, polity, era_index, year, rng)

    _spread(ctx, year, period, rng)


def _discover(ctx, polity, era_index: int, year: int, rng) -> None:
    world = ctx.world
    options = crafts_mod.available(set(polity.known), era_index)
    if not options:
        return
    craft = rng.weighted(options)
    cities = [world.settlements[sid] for sid in polity.settlement_ids
              if sid in world.settlements
              and world.settlements[sid].status == ACTIVE
              and world.settlements[sid].population >= MIN_CITY]
    if not cities:
        return
    city = rng.weighted([(item, float(item.population)) for item in cities])
    race = races_mod.RACES_BY_ID.get(city.race_id) or \
        races_mod.get_race(polity.race_id)
    sex = "f" if rng.chance(0.38) else "m"
    maker = ctx.make_figure(
        rng, race, year, role="изобретатель", region_id=city.region_id,
        title="мастер" if sex == "m" else "мастерица", sex=sex,
        home_id=city.id, epithet_chance=0.5,
        folk=world.folks.get(city.folk_id))

    polity.known.append(craft.key)
    date = ctx.date_in(rng, year)
    record = world.discovery_of(craft.key)
    if record is None:
        record = world.add_discovery(
            key=craft.key, name=craft.name, family=craft.family, made=date,
            polity_id=polity.id, settlement_id=city.id, figure_id=maker.id,
            race_id=race.id, known_by=[polity.id])
        importance = 3
    else:
        # Открыли во второй раз и независимо — бывает чаще, чем думают.
        if polity.id not in record.known_by:
            record.known_by.append(polity.id)
        record.notes.append("заново открыто в %d году державой %s"
                            % (year, polity.name))
        importance = 2

    title, text = texts.discovered(rng, craft, maker, city, polity)
    event = world.add_event(
        date=date, era_index=era_index, kind="discovery", title=title,
        text=text, importance=importance, actors=[maker.id],
        subjects=[record.id, polity.id, city.id], region_id=city.region_id,
        race_id=race.id)
    maker.deeds.append(event.id)


def _spread(ctx, year: int, period: int, rng) -> None:
    """Открытие идёт по торговым путям и через межу — но не само собой."""
    world = ctx.world
    scale = period / 10.0
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        if polity.status != ACTIVE:
            continue
        neighbours = _teachers(world, polity)
        if not neighbours:
            continue
        missing = []
        for other, closeness in neighbours:
            for key in other.known:
                if key not in polity.known:
                    missing.append((key, other, closeness))
        if not missing:
            continue
        key, source, closeness = rng.weighted(
            [((item[0], item[1], item[2]), item[2]) for item in missing])
        if not rng.chance(min(0.75, SPREAD_RATE * scale * closeness)):
            continue
        craft = crafts_mod.CRAFTS_BY_KEY.get(key)
        if craft is None:
            continue
        polity.known.append(key)
        record = world.discovery_of(key)
        if record is not None and polity.id not in record.known_by:
            record.known_by.append(polity.id)
        if rng.chance(0.45):
            date = ctx.date_in(rng, year)
            title, text = texts.spread(rng, craft, polity, source)
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="discovery_spread", title=title, text=text, importance=1,
                subjects=[polity.id], race_id=polity.race_id,
                region_id=polity.region_ids[0] if polity.region_ids else "")


def _teachers(world, polity) -> list:
    """У кого эта держава может перенять: торговые партнёры и соседи."""
    out = {}
    for route_id in polity.routes:
        route = world.routes.get(route_id)
        if route is None or route_id not in world.active_routes:
            continue
        other_id = route.seller_id if route.buyer_id == polity.id \
            else route.buyer_id
        other = world.polities.get(other_id)
        if other is not None and other.status == ACTIVE and other.known:
            out[other.id] = (other, 1.0)
    reach = set()
    for region_id in polity.region_ids:
        region = world.regions.get(region_id)
        if region is not None:
            reach.update(region.neighbors)
    for other_id in world.active_polities:
        if other_id == polity.id or other_id in out:
            continue
        other = world.polities[other_id]
        if not other.known:
            continue
        if any(region_id in reach for region_id in other.region_ids):
            out[other.id] = (other, 0.4)
    # У врага не учатся: с тем, с кем воюешь, мастерами не меняются.
    trimmed = []
    for other, closeness in out.values():
        if world.war_between(polity.id, other.id) is not None:
            continue
        value = (polity.relations or {}).get(other.id, 0.0)
        trimmed.append((other, closeness * max(0.25, 1.0 + value)))
    return trimmed


# ---------------------------------------------------------------------------
# Что открытия дают
# ---------------------------------------------------------------------------

def war_edge(polity) -> float:
    return crafts_mod.bonus(polity.known if polity is not None else (), "war")


def siege_edge(polity) -> float:
    return crafts_mod.bonus(polity.known if polity is not None else (), "siege")


def growth_edge(polity) -> float:
    return crafts_mod.bonus(polity.known if polity is not None else (),
                            "growth")


def sea_edge(polity) -> float:
    return crafts_mod.bonus(polity.known if polity is not None else (), "sea")


def trade_edge(polity) -> float:
    return crafts_mod.bonus(polity.known if polity is not None else (),
                            "trade")


__all__ = ["upkeep", "war_edge", "siege_edge", "growth_edge", "sea_edge",
           "trade_edge"]
