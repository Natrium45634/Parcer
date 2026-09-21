# -*- coding: utf-8 -*-
"""Демография: сколько народу где живёт и насколько ему там тесно.

Движок и раньше считал население — по племенам, городам и державам. Не
хватало взгляда сверху: какая земля переполнена, какая пуста, куда пойдут
люди, если с места их сгонит голод или война.

Тесноту считаем не абсолютом, а долей: сколько душ приходится на землю по
сравнению с тем, сколько эта земля тянет. Так одна и та же мера работает и
в мире на тридцать тысяч душ, и в мире на семь миллионов, и на карте, и на
выдуманной географии.

Модуль ничего не меняет: он только считает и отвечает на вопросы — где
тесно, где безопасно, куда потянет этот народ.
"""

from __future__ import annotations

from . import homelands
from . import races as races_mod

# Почему люди снимаются с места.
HUNGER = "голод"
WAR = "война"
PLAGUE = "мор"
COLD = "холода"
CROWD = "теснота"
PERSECUTION = "гонения"
RUIN = "разорённая земля"
CALL = "зов новой земли"

PUSHES = (HUNGER, WAR, PLAGUE, COLD, CROWD, PERSECUTION, RUIN, CALL)

# Как тяжело давит каждая причина: голод гонит вернее тесноты.
PUSH_WEIGHT = {
    HUNGER: 1.6, WAR: 1.3, PLAGUE: 1.4, COLD: 1.2, CROWD: 1.0,
    PERSECUTION: 1.5, RUIN: 1.2, CALL: 0.7,
}

TIGHT = 1.85               # с какой тесноты земля начинает выталкивать
ROOMY = 0.75               # и до какой она зовёт к себе


def region_souls(world) -> dict:
    """Сколько душ живёт в каждой земле."""
    out = {}
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        out[settlement.region_id] = out.get(settlement.region_id, 0) \
            + world.settlement_realm(settlement)
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        out[tribe.region_id] = out.get(tribe.region_id, 0) + tribe.population
    for camp_id in world.active_camps:
        camp = world.camps[camp_id]
        out[camp.region_id] = out.get(camp.region_id, 0) + camp.population
    return out


def land_worth(region) -> float:
    """Сколько эта земля тянет народу — в условных долях."""
    if region is None or region.drowned:
        return 0.0
    worth = max(0.15, float(region.capacity or 1.0))
    if region.from_map:
        worth *= 0.35 + 1.3 * max(0.0, min(1.0, region.habitat))
        worth *= 0.7 + 0.8 * max(0.0, min(1.0, region.fertility))
    return max(0.05, worth)


def loads(world) -> dict:
    """Теснота каждой земли: 1.0 — как в среднем по миру, 2.0 — вдвое тесней."""
    souls = region_souls(world)
    total_souls = float(sum(souls.values())) or 1.0
    worth = {}
    for region in world.regions.values():
        value = land_worth(region)
        if value > 0:
            worth[region.id] = value
    total_worth = float(sum(worth.values())) or 1.0

    out = {}
    for region_id, value in worth.items():
        share = value / total_worth
        living = souls.get(region_id, 0) / total_souls
        out[region_id] = living / share if share > 0 else 0.0
    return out


def safety(ctx, region_id: str, year: int) -> float:
    """Насколько спокойно в земле: 1.0 — тихо, 0.0 — беда на беде."""
    world = ctx.world
    region = world.regions.get(region_id)
    if region is None or region.drowned:
        return 0.0
    value = 1.0 - 0.6 * ctx.gloom(region_id)
    if region.from_map:
        value -= 0.3 * max(0.0, min(1.0, region.risk))
        value -= 0.2 * max(0.0, min(1.0, region.savagery))
    for calamity_id in world.active_calamities:
        calamity = world.calamities.get(calamity_id)
        if calamity is not None and region_id in calamity.region_ids:
            value -= 0.12 * calamity.severity
    return max(0.0, min(1.0, value))


def attraction(ctx, race, region, year: int, load: float) -> float:
    """Насколько эта земля манит этот народ."""
    if region is None or region.drowned or region.sundered:
        return 0.0
    fertility = region.fertility if region.from_map else 0.0
    want = homelands.desire(race, region.terrain, fertility, region.river)
    if want <= 0.05:
        return 0.0
    room = max(0.05, 2.2 - load)          # чем тесней, тем меньше манит
    return want * room * (0.35 + 0.65 * safety(ctx, region.id, year))


def host_of(world, region_id: str):
    """Чья это земля: держава, которой принадлежит большинство городов."""
    counts = {}
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id != region_id or not settlement.polity_id:
            continue
        counts[settlement.polity_id] = counts.get(settlement.polity_id, 0) + 1
    if not counts:
        return None
    best = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
    return world.polities.get(best)


def welcome(world, host, race, year: int) -> float:
    """Как примут пришлых: 1.0 — с хлебом, 0.0 — стрелами."""
    from . import diplomacy as dip
    from . import nations as pol

    if host is None:
        return 1.0                     # пустая земля никому не отказывает
    own = races_mod.get_race(host.race_id)
    value = 0.5 + 0.5 * dip.racial_affinity(own, race)
    if race.id == host.race_id:
        value += 0.35                  # единокровцев принимают охотнее всех
    if pol.is_harsh(host.policy):
        value -= 0.35
    if host.policy == pol.EQUAL:
        value += 0.15
    value -= 0.4 * max(0.0, host.hunger)
    value -= 0.25 * min(1.0, host.weariness)
    if race.is_evil:
        value -= 0.6
    return max(0.0, min(1.0, value))
