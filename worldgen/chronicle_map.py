# -*- coding: utf-8 -*-
"""Обратный мост: политическая карта истории для TECTONIC WORLDFORGE.

Картогенератор умеет проигрывать историю по годам — во вкладке «Страны»
границы держав растут, делятся и гаснут. Данные он ждёт в файле
``chronicle.json``, в секции ``map``.

Здесь эта секция и собирается:

* **frames** — кто владел каждым гексом в такой-то год. Кадр снимается
  раз в несколько десятилетий и обязательно на границе эпохи;
* **cities** — города с годом основания и годом гибели, столицы отдельно;
* **realmColors** — цвет каждой державы, взятый от её народа: эльфийские
  земли зелены, дворфские рыжи, орочьи — цвета ржавчины.

Владение считается так: каждый живой город тянет к себе округу по числу
жителей, гекс отходит ближайшему городу, а через него — его державе.
Земли, до которых не дотянулся никто, остаются ничьими.

Тянется город не куда легче, а **куда хочется**. Цена шага делится на
желание народа (``homelands.py``): дворф идёт в горы и в ближние долины,
эльф держится леса, человек берёт всё, где родится хлеб. Без этого
граница ложилась лентой — волна шла вдоль рек и по равнинам, и держава
дворфов вытягивалась через степь на пол-материка просто потому, что по
степи идти дешевле, чем по своим же горам.
"""

from __future__ import annotations

import heapq
import json

from . import homelands
from . import races as races_mod
from .mapregions import BIOME_TERRAIN
from . import worldmap as wm

DEFAULT_INTERVAL = 50          # как часто снимать кадр границ
# Округа города меряется не в гексах по прямой, а в цене пути: за хребтом
# она обрывается, вдоль реки тянется далеко. Так держава на карте получает
# настоящие очертания, а не круг.
BASE_REACH = 8.5               # округа даже у самого малого города
REACH_PER_SOUL = 0.0014        # насколько дальше тянется город за жителя
MAX_REACH = 30.0

# Цвет народа: тон в градусах и насыщенность. Держава получает оттенок
# своего народа, чтобы карта читалась по расам, а не по номерам.
RACE_HUE = {
    "human": 45, "dwarf": 22, "elf": 120, "high_elf": 170, "dark_elf": 285,
    "catfolk": 35, "wolfkin": 205, "bearkin": 15, "foxkin": 28, "birdkin": 190,
    "lizardfolk": 95, "snakefolk": 85, "frogfolk": 150, "turtlefolk": 165,
    "shellfolk": 180, "orc": 0, "goblin": 75, "troll": 260, "ogre": 320,
    "kobold": 300, "gnoll": 55,
}


def _hsl_to_hex(hue: float, saturation: float, light: float) -> str:
    """Цвет в той же записи, что понимает картогенератор."""
    hue = (hue % 360) / 360.0

    def channel(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6.0:
            return p + (q - p) * 6 * t
        if t < 0.5:
            return q
        if t < 2 / 3.0:
            return p + (q - p) * (2 / 3.0 - t) * 6
        return p

    q = light * (1 + saturation) if light < 0.5 else light + saturation - light * saturation
    p = 2 * light - q
    red = channel(p, q, hue + 1 / 3.0)
    green = channel(p, q, hue)
    blue = channel(p, q, hue - 1 / 3.0)
    return "#%02x%02x%02x" % (int(red * 255), int(green * 255), int(blue * 255))


def realm_color(polity, slot: int) -> str:
    """Цвет державы: тон от народа, оттенок — свой у каждой страны."""
    hue = RACE_HUE.get(polity.race_id, (slot * 137) % 360)
    hue = (hue + ((slot * 53) % 40) - 20) % 360
    light = 0.50 + ((slot * 29) % 7 - 3) * 0.022
    return _hsl_to_hex(hue, 0.52, light)


def _encode_rle(values) -> list:
    """Плоские пары [значение, сколько раз] — как ждёт decodeRLE в оверлее."""
    out = []
    if not values:
        return out
    current = values[0]
    run = 1
    for value in values[1:]:
        if value == current and run < 32000:
            run += 1
        else:
            out.append(current)
            out.append(run)
            current, run = value, 1
    out.append(current)
    out.append(run)
    return out


class MapRecorder:
    """Снимает кадры политической карты по ходу генерации."""

    def __init__(self, link, world, interval: int = DEFAULT_INTERVAL,
                 travel=None):
        self.link = link
        self.world = world
        self.travel = travel or getattr(link, "travel", None)
        self.interval = max(5, int(interval))
        self.frames = []            # [{"y": год, "key": веха, "rle": [...]}]
        self.slots = {}             # polity_id -> номер державы на карте
        self.city_seen = {}         # settlement_id -> последняя известная держава
        self._terrain_cache = None  # местность каждого гекса, считается раз

    # ------------------------------------------------------------------

    def slot_of(self, polity_id: str) -> int:
        if not polity_id:
            return -1
        if polity_id not in self.slots:
            self.slots[polity_id] = len(self.slots)
        return self.slots[polity_id]

    def should_record(self, year: int, key: bool = False) -> bool:
        return key or year == 1 or year % self.interval == 0

    def record(self, year: int, key: bool = False) -> None:
        """Снимает кадр: кто чем владеет прямо сейчас."""
        owner = self._ownership()
        self.frames.append({"y": int(year), "key": 1 if key else 0,
                            "rle": _encode_rle(owner)})

    # ------------------------------------------------------------------

    def _ownership(self) -> list:
        """Владение по гексам: номер державы или -1, если земля ничья.

        Волна идёт не по числу шагов, а по цене пути: через болото держава
        дотягивается вдвое хуже, чем по равнине, через хребет — почти
        никак, а вдоль реки — далеко. Поэтому граница на карте ложится по
        рельефу, как ей и положено.
        """
        wmap = self.link.wmap
        size = wmap.size
        owner = [-1] * size
        best = [1e18] * size
        costs = self.travel.land if self.travel is not None else None
        ground = self._ground()

        heap = []
        for settlement_id in self.world.active_settlements:
            settlement = self.world.settlements[settlement_id]
            index = settlement.hex_index
            if index is None or index < 0 or index >= size:
                continue
            slot = self.slot_of(settlement.polity_id)
            if settlement.polity_id:
                self.city_seen[settlement_id] = slot
            reach = min(MAX_REACH,
                        BASE_REACH + settlement.population * REACH_PER_SOUL)
            owner[index] = slot
            best[index] = 0.0
            heapq.heappush(heap, (0.0, index, reach, slot,
                                  settlement.race_id))

        while heap:
            spent, index, reach, slot, race_id = heapq.heappop(heap)
            if spent > best[index] or spent >= reach:
                continue
            race = races_mod.RACES_BY_ID.get(race_id)
            for neighbor in wmap.neighbors(index):
                if not wmap.is_land(neighbor):
                    continue
                step = costs[neighbor] if costs is not None else 1.0
                if step >= 1e8:
                    continue        # через пики держава не тянется
                # Своя земля даётся даром, чужая — втрое-впятеро дороже.
                terrain, fertility, river = ground[neighbor]
                step *= homelands.cost_scale(race, terrain, fertility, river)
                fresh = spent + step
                if fresh < reach and fresh < best[neighbor]:
                    best[neighbor] = fresh
                    owner[neighbor] = slot
                    heapq.heappush(heap, (fresh, neighbor, reach, slot,
                                          race_id))
        return owner

    def _ground(self) -> list:
        """Что за земля в каждом гексе: местность, плодородие, река.

        Считается один раз на весь прогон: слои карты не меняются.
        """
        if self._terrain_cache is not None:
            return self._terrain_cache
        wmap = self.link.wmap
        size = wmap.size
        biome = wmap.layer(wm.L_BIOME)
        fert = wmap.layer(wm.L_FERTILITY)
        flags = wmap.layer(wm.L_FLAGS)
        rows = []
        for index in range(size):
            terrain = races_mod.PLAIN
            if biome is not None:
                terrain = BIOME_TERRAIN.get(biome[index], races_mod.PLAIN)
            value = float(fert[index]) if fert is not None else 0.4
            river = bool(flags[index] & 4) if flags is not None else False
            rows.append((terrain, value, river))
        self._terrain_cache = rows
        return rows

    # ------------------------------------------------------------------

    def trade_routes(self) -> list:
        """Торговые пути для карты: настоящий путь по гексам, не прямая."""
        wmap = self.link.wmap
        out = []
        for route in self.world.routes.values():
            if not route.path:
                continue
            flat = []
            for index in route.path:
                column, row = wmap.col_row(index)
                flat.append(int(column))
                flat.append(int(row))
            seller = self.world.polities.get(route.seller_id)
            buyer = self.world.polities.get(route.buyer_id)
            out.append({
                "a": self.slot_of(route.seller_id),
                "b": self.slot_of(route.buyer_id),
                "sea": 1 if route.by_sea else 0,
                "est": int(route.opened.year) if route.opened else 0,
                "sev": int(route.closed.year) if route.closed else -1,
                "name": "%s — %s" % (seller.name if seller else "?",
                                     buyer.name if buyer else "?"),
                "goods": route.good,
                "path": flat,
            })
        return out

    def roads(self) -> list:
        """Дороги внутри держав: от столицы к каждому своему городу."""
        if self.travel is None:
            return []
        wmap = self.link.wmap
        out = []
        for polity_id in self.world.active_polities:
            polity = self.world.polities[polity_id]
            capital = self.world.settlements.get(polity.capital_id)
            if capital is None or capital.hex_index < 0:
                continue
            slot = self.slot_of(polity_id)
            for settlement_id in polity.settlement_ids:
                settlement = self.world.settlements.get(settlement_id)
                if settlement is None or settlement.id == capital.id:
                    continue
                if settlement.status != "активно" or settlement.hex_index < 0:
                    continue
                path, cost = self.travel.route(capital.hex_index,
                                               settlement.hex_index,
                                               limit=300.0)
                if not path:
                    continue
                flat = []
                for index in path:
                    column, row = wmap.col_row(index)
                    flat.append(int(column))
                    flat.append(int(row))
                out.append({
                    "sea": 0, "int": 1,
                    "est": int(settlement.founded.year),
                    "path": flat, "pA": slot, "pB": slot,
                })
        return out

    # ------------------------------------------------------------------

    def cities(self) -> list:
        """Города для карты: где, когда основан, когда погиб, чей."""
        wmap = self.link.wmap
        out = []
        for settlement in self.world.settlements.values():
            index = settlement.hex_index
            if index is None or index < 0 or index >= wmap.size:
                continue
            column, row = wmap.col_row(index)
            slot = self.city_seen.get(settlement.id, -1)
            if settlement.polity_id:
                slot = self.slot_of(settlement.polity_id)
            out.append({
                "x": int(column), "y": int(row),
                "f": int(settlement.founded.year),
                "r": int(settlement.ended.year) if settlement.ended else -1,
                "cap": 1 if settlement.is_capital else 0,
                "pc": 1 if (not settlement.is_capital
                            and settlement.population >= 4000) else 0,
                "s": int(slot),
                "n": settlement.name,
            })
        out.sort(key=lambda city: (city["f"], city["n"]))
        return out

    def tribes_section(self) -> dict:
        """Живые племена — их тоже показывает оверлей."""
        wmap = self.link.wmap
        listing = []
        territory = [-1] * wmap.size
        for slot, tribe_id in enumerate(sorted(self.world.active_tribes)):
            tribe = self.world.tribes[tribe_id]
            index = tribe.hex_index
            if index is None or index < 0 or index >= wmap.size:
                continue
            column, row = wmap.col_row(index)
            listing.append({
                "id": slot, "x": int(column), "y": int(row),
                "name": tribe.name, "marine": 0, "mammoth": 0,
                "supplies": [],
            })
            territory[index] = slot
            for neighbor in wmap.neighbors(index):
                if wmap.is_land(neighbor) and territory[neighbor] < 0:
                    territory[neighbor] = slot
        return {"list": listing, "territory": _encode_rle(territory)}

    # ------------------------------------------------------------------

    def build(self) -> dict:
        """Готовая секция map для chronicle.json."""
        wmap = self.link.wmap
        colors = {}
        for polity_id, slot in self.slots.items():
            polity = self.world.polities.get(polity_id)
            if polity is not None:
                colors[str(slot)] = realm_color(polity, slot)
        return {
            "w": wmap.width, "h": wmap.height, "wrap": 1 if wmap.wrap else 0,
            "seed": self.world.seed_text,
            "mapSeed": wmap.seed_text,
            "realmColors": colors,
            "realmNames": {str(slot): self.world.polities[pid].full_name
                           for pid, slot in self.slots.items()
                           if pid in self.world.polities},
            "cities": self.cities(),
            "routes": self.trade_routes(),
            "roads": self.roads(),
            "frames": self.frames,
            "tribes": self.tribes_section(),
        }


def export(world, recorder, path: str) -> dict:
    """Пишет chronicle.json рядом с летописью."""
    payload = {
        "seed": world.seed_text,
        "years": world.total_years,
        "eras": [{"name": era.name, "start": era.start_year, "end": era.end_year}
                 for era in world.eras],
        "map": recorder.build(),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return payload


def race_legend() -> list:
    """Расшифровка цветов — какой народ каким тоном обозначен."""
    out = []
    for race in races_mod.RACES:
        hue = RACE_HUE.get(race.id)
        if hue is None:
            continue
        out.append((race.name, _hsl_to_hex(hue, 0.52, 0.5)))
    return out
