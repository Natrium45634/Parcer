# -*- coding: utf-8 -*-
"""Проходимость карты: во что обходится путь по гексу и как ходят дороги.

Прежняя беда торговых путей была в том, что они соединяли города по
прямой. Прямая через хребет — это не путь, а линия на бумаге: по ней
никто не пойдёт. Настоящая дорога идёт в обход — долиной, вдоль реки,
через перевал, — и потому она длиннее по карте, но дешевле по времени.

Здесь задана цена шага по каждому гексу и поиск дешёвого пути между
двумя точками. Правила простые и все следуют из здравого смысла:

* **равнина и степь** — самый дешёвый ход;
* **лес, холмы** — дороже вдвое, **болото и джунгли** — вчетверо;
* **горы** — очень дорого, а **высокие пики непроходимы вовсе**: дорога
  их обходит или ищет перевал, то есть самый низкий гекс в хребте;
* **вдоль реки** дешевле: река кормит, поит и показывает направление;
* **переправа через реку** стоит отдельно — брод или мост есть не везде;
* **берег** удобен: по нему идут и посуху, и каботажем;
* **море** для сухого пути закрыто, но по нему есть свой, морской путь,
  и он дёшев вдали от льдов.
"""

from __future__ import annotations

import heapq

from . import races as races_mod
from . import worldmap as wm
from .mapregions import BIOME_TERRAIN

# Цена шага по местности. Единица — переход по ровному месту.
TERRAIN_COST = {
    races_mod.PLAIN: 1.0,
    races_mod.STEPPE: 1.1,
    races_mod.COAST: 1.2,
    races_mod.HILLS: 1.8,
    races_mod.FOREST: 2.0,
    races_mod.TUNDRA: 2.2,
    races_mod.DESERT: 2.6,
    races_mod.ISLANDS: 1.5,
    races_mod.JUNGLE: 4.0,
    races_mod.SWAMP: 4.5,
    races_mod.UNDERGROUND: 3.0,
    races_mod.MOUNTAIN: 7.0,
}

IMPASSABLE = 1e9
PEAK_METERS = 2600.0        # выше этого через хребет не ходят вовсе
HARD_METERS = 1500.0        # выше этого ход дорожает круто
RIVER_BONUS = 0.55          # насколько дешевле идти вдоль реки
FORD_COST = 2.5             # переправа: брод, паром, мост
COAST_BONUS = 0.85
SEA_COST = 1.0              # ход под парусом по открытой воде
ICE_SEA_COST = 6.0          # у льдов парус почти бесполезен


def land_cost(wmap, index: int) -> float:
    """Во что обходится шаг на этот гекс по суше."""
    if wmap.is_ocean(index):
        return IMPASSABLE
    meters = wmap.elevation_m(index)
    if meters >= PEAK_METERS:
        return IMPASSABLE           # пики обходят, а не штурмуют
    biome = wmap.layer(wm.L_BIOME)
    terrain = BIOME_TERRAIN.get(biome[index], races_mod.PLAIN) if biome \
        else races_mod.PLAIN
    cost = TERRAIN_COST.get(terrain, 2.0)
    if meters >= HARD_METERS:
        # Между тысячей и двумя с половиной — уже настоящие горы.
        cost *= 1.0 + (meters - HARD_METERS) / 900.0
    if wmap.is_river(index):
        cost *= RIVER_BONUS
    elif wmap.is_coast(index):
        cost *= COAST_BONUS
    if wmap.is_lake(index):
        return IMPASSABLE
    return cost


def sea_cost(wmap, index: int) -> float:
    """Во что обходится шаг по воде."""
    if not wmap.is_ocean(index):
        return IMPASSABLE
    biome = wmap.layer(wm.L_BIOME)
    if biome is not None and biome[index] == 0:      # морской лёд
        return ICE_SEA_COST
    return SEA_COST


class TravelMap:
    """Цены хода по всей карте, посчитанные один раз."""

    def __init__(self, wmap):
        self.wmap = wmap
        size = wmap.size
        self.land = [0.0] * size
        self.sea = [0.0] * size
        for index in range(size):
            self.land[index] = land_cost(wmap, index)
            self.sea[index] = sea_cost(wmap, index)
        self._paths = {}

    # ------------------------------------------------------------------

    def route(self, start: int, goal: int, by_sea: bool = False,
              limit: float = 4000.0):
        """Самый дешёвый путь из одного гекса в другой.

        Возвращает (список гексов, цена) или (None, 0), если пути нет.
        Считается Дейкстрой: она и даёт кратчайший путь, и сама обходит
        пики, потому что через них дороги просто нет.
        """
        if start == goal:
            return [start], 0.0
        key = (start, goal, by_sea)
        if key in self._paths:
            return self._paths[key]

        costs = self.sea if by_sea else self.land
        wmap = self.wmap
        # Переправу через реку считаем при входе с суши на сушу.
        best = {start: 0.0}
        came = {}
        heap = [(0.0, start)]
        found = False
        while heap:
            spent, current = heapq.heappop(heap)
            if spent > best.get(current, 1e18):
                continue
            if current == goal:
                found = True
                break
            if spent > limit:
                break
            for neighbor in wmap.neighbors(current):
                step = costs[neighbor]
                if step >= IMPASSABLE:
                    # В конечную точку заходим даже если она «дорогая»:
                    # город может стоять и на скале.
                    if neighbor != goal:
                        continue
                    step = 12.0
                if not by_sea and wmap.is_river(neighbor) \
                        and not wmap.is_river(current):
                    step += FORD_COST
                fresh = spent + step
                if fresh < best.get(neighbor, 1e18):
                    best[neighbor] = fresh
                    came[neighbor] = current
                    heapq.heappush(heap, (fresh, neighbor))

        if not found:
            self._paths[key] = (None, 0.0)
            return None, 0.0

        path = [goal]
        node = goal
        while node != start:
            node = came[node]
            path.append(node)
        path.reverse()
        result = (path, best[goal])
        self._paths[key] = result
        return result

    # ------------------------------------------------------------------

    def reachable(self, start: int, budget: float, by_sea: bool = False) -> dict:
        """Все гексы, до которых можно добраться за такую цену.

        Это и есть настоящая округа города: за хребтом она обрывается,
        а вдоль реки тянется далеко.
        """
        costs = self.sea if by_sea else self.land
        wmap = self.wmap
        best = {start: 0.0}
        heap = [(0.0, start)]
        while heap:
            spent, current = heapq.heappop(heap)
            if spent > best.get(current, 1e18) or spent > budget:
                continue
            for neighbor in wmap.neighbors(current):
                step = costs[neighbor]
                if step >= IMPASSABLE:
                    continue
                if not by_sea and wmap.is_river(neighbor) \
                        and not wmap.is_river(current):
                    step += FORD_COST
                fresh = spent + step
                if fresh <= budget and fresh < best.get(neighbor, 1e18):
                    best[neighbor] = fresh
                    heapq.heappush(heap, (fresh, neighbor))
        return best

    # ------------------------------------------------------------------

    def site_score(self, index: int) -> float:
        """Насколько гекс хорош под город.

        Хорошее место — не самое плодородное, а самое удобное: где сходятся
        пути. Слияние рек, устье, брод, выход из перевала к равнине — на
        таких местах города стоят тысячи лет.
        """
        wmap = self.wmap
        if self.land[index] >= IMPASSABLE:
            return 0.0
        score = 1.0
        if wmap.is_river(index):
            score += 1.6
        if wmap.is_coast(index):
            score += 1.2
        if wmap.is_river(index) and wmap.is_coast(index):
            score += 0.8                        # устье: река плюс море

        neighbours = wmap.neighbors(index)
        rivers = sum(1 for n in neighbours if wmap.is_river(n))
        if rivers >= 2 and wmap.is_river(index):
            score += 1.0                        # слияние
        if rivers and not wmap.is_river(index):
            score += 0.4                        # брод у самой воды

        # Ворота в горы: ровное место, с которого начинается дорога наверх.
        highs = sum(1 for n in neighbours
                    if wmap.elevation_m(n) >= HARD_METERS)
        if 0 < highs < len(neighbours) and wmap.elevation_m(index) < HARD_METERS:
            score += 0.7

        fertility = wmap.layer(wm.L_FERTILITY)
        if fertility is not None:
            score += float(fertility[index]) * 1.2
        return score

    def pass_through(self, region_hexes) -> int:
        """Самый дешёвый гекс земли — им она и соединяется с соседями.

        Для горной земли это перевал: то место, через которое только и
        можно пройти.
        """
        best, best_cost = -1, 1e18
        for index in region_hexes:
            cost = self.land[index]
            if cost < best_cost:
                best, best_cost = index, cost
        return best
