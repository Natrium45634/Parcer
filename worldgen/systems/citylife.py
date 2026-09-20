# -*- coding: utf-8 -*-
"""Мелкие случаи городской жизни.

Между войнами город горит, строит стену, заводит ярмарку, судит вора и
встречает беженцев. Ни одно из этих событий не меняет судьбу мира — и
именно поэтому они нужны: без них летопись читается как список походов.

Большие города живут громче маленьких, и потому случаи выпадают им чаще.
Постройка остаётся в городе навсегда: стена, мост, маяк, книгохранилище —
это то, чем город отличается от соседнего.
"""

from __future__ import annotations

from .. import citylife as life
from .. import narrative_citylife as texts
from ..models import ACTIVE
from ..world import RURAL_FACTOR

EVENT_RATE = 0.020          # шанс случая на город за такт
MIN_SOULS = 400
SHORE = ("побережье", "острова")


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("citylife", year)
    era_index = world.era_index_at(year)
    scale = period / 10.0

    for settlement_id in list(world.active_settlements):
        settlement = world.settlements[settlement_id]
        if settlement.status != ACTIVE or settlement.population < MIN_SOULS:
            continue
        # Большой город живёт громче: в нём и горит чаще, и строят больше.
        chance = EVENT_RATE * scale * (0.6 + min(2.5, settlement.population
                                                 / 2600.0))
        if not rng.chance(min(0.35, chance)):
            continue
        _happen(ctx, settlement, era_index, year, rng)


def _happen(ctx, settlement, era_index: int, year: int, rng) -> None:
    world = ctx.world
    polity = world.polities.get(settlement.polity_id)
    known = set(polity.known) if polity is not None else set()
    region = world.regions.get(settlement.region_id)
    port = region is not None and (region.terrain in SHORE
                                   or getattr(region, "coastal", False))
    souls = world.settlement_realm(settlement)

    options = []
    for item in life.HAPPENINGS:
        if souls < item.min_souls or item.era_from > era_index:
            continue
        if item.port and not port:
            continue
        if any(need not in known for need in item.needs):
            continue
        if item.landmark and item.landmark in settlement.landmarks:
            continue
        weight = item.weight
        if item.key == "fire" and "mortar" in known:
            weight *= 0.5          # каменный город горит хуже деревянного
        if item.key == "sickness" and "quarantine" in known:
            weight *= 0.4
        if item.key == "refugees" and not _troubled_neighbours(world, region):
            weight *= 0.3
        options.append((item, weight))
    if not options:
        return

    happening = rng.weighted(options)
    date = ctx.date_in(rng, year)
    dead = 0
    if happening.toll:
        dead = int(souls * happening.toll * rng.uniform(0.5, 1.5))
        settlement.population = max(
            60, settlement.population - int(dead / RURAL_FACTOR))
    if happening.gain:
        settlement.population = int(settlement.population
                                    * (1.0 + happening.gain
                                       * rng.uniform(0.5, 1.5)))
    if happening.landmark:
        settlement.landmarks.append(happening.landmark)

    title, text = texts.happening(rng, happening, settlement, dead)
    world.add_event(
        date=date, era_index=era_index, kind="city_life", title=title,
        text=text, importance=2 if (happening.landmark or dead > 400) else 1,
        subjects=[settlement.id], region_id=settlement.region_id,
        race_id=settlement.race_id)


def _troubled_neighbours(world, region) -> bool:
    """Есть ли поблизости война или беда, от которой бегут."""
    if region is None:
        return False
    reach = set(region.neighbors) | {region.id}
    for calamity_id in world.active_calamities:
        calamity = world.calamities[calamity_id]
        if any(item in reach for item in calamity.region_ids):
            return True
    for war_id in world.active_wars:
        war = world.wars[war_id]
        for polity_id in (war.attacker_id, war.defender_id):
            polity = world.polities.get(polity_id)
            if polity is not None and any(item in reach
                                          for item in polity.region_ids):
                return True
    return False


__all__ = ["upkeep"]
