# -*- coding: utf-8 -*-
"""Земли мира.

Землю можно получить двумя путями.

* **Процедурно.** Простая сетка областей: тип местности, соседи, имя.
  Этого хватает, чтобы народы селились осмысленно — дворфы в горах,
  ящеролюды в болотах.
* **По карте.** Если перед генерацией указан файл ``.world`` из
  TECTONIC WORLDFORGE, земли режутся из настоящей гексовой карты со всей
  её географией: хребтами, реками, климатом, рудами и магией. Тогда
  история опирается не на выдумку движка, а на данные карты.
"""

from __future__ import annotations

import math

from .. import mapworld
from .. import races as races_mod
from .. import worldmap as wmod

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
    """Создаёт земли мира — из файла карты либо процедурно."""
    path = str(getattr(ctx.settings, "map_path", "") or "")
    if path:
        _build_from_map(ctx, path)
        return
    _build_grid(ctx)


def _build_from_map(ctx, path: str) -> None:
    """Земли берутся из гексовой карты .world."""
    world = ctx.world
    rng = ctx.rng("geography")
    wmap = wmod.load(path)
    link = mapworld.MapLink(wmap, path)

    # На настоящей карте земель нужно больше, иначе степь и пустыня
    # растворятся в лесу, который их окружает.
    land = sum(1 for i in range(wmap.size) if wmap.is_land(i))
    asked = max(6, int(getattr(ctx.settings, "regions", 18)))
    count = max(asked, min(60, int(land / 200.0)))

    link.build(ctx, rng, count)
    ctx.map = link
    world.map_source = path
    world.notes["карта"] = {
        "файл": path.rsplit("/", 1)[-1],
        "сид карты": wmap.seed_text,
        "размер": "%d×%d" % (wmap.width, wmap.height),
        "земель": len(world.regions),
    }
    _record_geography(world, wmap)
    ctx.set_world_scale(len(world.regions))
    ctx.build_region_weights()


def _record_geography(world, wmap) -> None:
    """Сохраняет имена, которые карта дала океанам, материкам и хребтам.

    Летопись должна звать их так же, как карта: «океан Коранен»,
    «материк Вайрен», «хребет Вириран». Имя всегда стоит следом
    в именительном падеже, поэтому оборот годится в любом месте фразы.
    """
    from ..mapregions import FEATURE_NOUNS, translit

    catalogue = {}
    for feature in wmap.features:
        kind = feature.get("type")
        noun = FEATURE_NOUNS.get(kind)
        if not noun:
            continue
        name = translit(feature.get("name", ""))
        if not name:
            continue
        catalogue.setdefault(noun, []).append(
            {"name": name, "area": int(feature.get("area", 0))})
    for rows in catalogue.values():
        rows.sort(key=lambda row: (-row["area"], row["name"]))
    world.geography = catalogue


def _build_grid(ctx) -> None:
    """Процедурная сетка областей — когда карта не задана."""
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
    _cut_off_islands(world)
    ctx.set_world_scale(len(world.regions))
    ctx.build_region_weights()


def _cut_off_islands(world) -> None:
    """Острова отрезаются от суши: до них теперь только вплавь.

    На процедурной сетке всё связано со всем, и мореплавателям нечего было
    бы открывать. Поэтому островные земли теряют сухопутных соседей и
    получают морские: они остаются неведомыми, пока туда не доплывут.
    """
    islands = [region for region in world.regions.values()
               if region.terrain == races_mod.ISLANDS]
    if not islands:
        return
    island_ids = {region.id for region in islands}
    for region in world.regions.values():
        if region.id in island_ids:
            region.sea_links = [rid for rid in region.neighbors
                                if rid not in island_ids] or \
                [r.id for r in world.regions.values()
                 if r.id != region.id and r.id not in island_ids][:2]
            region.neighbors = [rid for rid in region.neighbors
                                if rid in island_ids]
        else:
            keep, sea = [], list(region.sea_links)
            for rid in region.neighbors:
                (sea if rid in island_ids else keep).append(rid)
            region.neighbors = keep
            region.sea_links = sea


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
