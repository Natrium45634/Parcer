# -*- coding: utf-8 -*-
"""Земли мира.

Карта — простая сетка областей. Каждая область имеет тип местности,
соседей и имя. Этого достаточно, чтобы народы селились осмысленно
(дворфы — в горах, ящеролюды — в болотах), и хватит как основа для
будущих блоков: границ, войн, торговых путей.
"""

from __future__ import annotations

import math

from .. import races as races_mod

TERRAIN_WEIGHTS = (
    (races_mod.PLAIN, 1.40),
    (races_mod.FOREST, 1.35),
    (races_mod.HILLS, 1.15),
    (races_mod.MOUNTAIN, 1.05),
    (races_mod.COAST, 1.00),
    (races_mod.STEPPE, 0.95),
    (races_mod.SWAMP, 0.70),
    (races_mod.JUNGLE, 0.70),
    (races_mod.TUNDRA, 0.65),
    (races_mod.DESERT, 0.65),
    (races_mod.UNDERGROUND, 0.55),
    (races_mod.ISLANDS, 0.50),
)

EDGE_BONUS = {
    races_mod.COAST: 2.2,
    races_mod.ISLANDS: 2.0,
    races_mod.TUNDRA: 1.6,
}

NEIGHBOR_BONUS = 1.8       # тяготение одинаковых земель друг к другу


def build(ctx) -> None:
    """Создаёт области мира и раскладывает их по сетке."""
    world = ctx.world
    rng = ctx.rng("geography")
    count = max(6, int(getattr(ctx.settings, "regions", 18)))

    columns = max(2, int(round(math.sqrt(count * 1.6))))
    rows = int(math.ceil(count / float(columns)))

    grid = {}
    cells = []
    for y in range(rows):
        for x in range(columns):
            if len(cells) >= count:
                break
            cells.append((x, y))

    for (x, y) in cells:
        pairs = []
        for terrain, weight in TERRAIN_WEIGHTS:
            value = weight
            if x in (0, columns - 1) or y in (0, rows - 1):
                value *= EDGE_BONUS.get(terrain, 0.9)
            for neighbor in ((x - 1, y), (x, y - 1)):
                found = grid.get(neighbor)
                if found is not None and found.terrain == terrain:
                    value *= NEIGHBOR_BONUS
            pairs.append((terrain, value))
        terrain = rng.weighted(pairs)
        region = world.add_region(
            name=ctx.forge.region(rng, terrain),
            terrain=terrain, x=x, y=y,
            capacity=races_mod.TERRAIN_CAPACITY.get(terrain, 1.0),
        )
        grid[(x, y)] = region

    # Соседство — по четырём сторонам света.
    for (x, y), region in grid.items():
        for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            other = grid.get(neighbor)
            if other is not None:
                region.neighbors.append(other.id)

    _guarantee_homelands(ctx, rng)
    ctx.build_region_weights()


def _guarantee_homelands(ctx, rng) -> None:
    """Каждой расе — хотя бы одна подходящая земля.

    Иначе на маленькой карте дворфы могли бы остаться без гор, а
    ящеролюды — без болот.
    """
    world = ctx.world
    present = {}
    for region in world.regions.values():
        present.setdefault(region.terrain, []).append(region)

    for race in races_mod.RACES:
        favorites = race.terrains[:2]
        if any(terrain in present for terrain in favorites):
            continue
        # Переделываем самую «обычную» область под нужды расы.
        candidates = [r for r in world.regions.values()
                      if len(present.get(r.terrain, ())) > 1]
        if not candidates:
            candidates = list(world.regions.values())
        victim = rng.choice(sorted(candidates, key=lambda r: r.id))
        present.get(victim.terrain, []).remove(victim)
        victim.terrain = favorites[0]
        victim.capacity = races_mod.TERRAIN_CAPACITY.get(victim.terrain, 1.0)
        victim.name = ctx.forge.region(rng, victim.terrain)
        present.setdefault(victim.terrain, []).append(victim)
