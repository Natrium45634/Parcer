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
"""

from __future__ import annotations

import json
from collections import deque

from . import races as races_mod

DEFAULT_INTERVAL = 50          # как часто снимать кадр границ
BASE_REACH = 2.0               # округа даже у самого малого города
REACH_PER_SOUL = 0.016         # насколько дальше тянется город за каждого жителя
MAX_REACH = 14.0

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

    def __init__(self, link, world, interval: int = DEFAULT_INTERVAL):
        self.link = link
        self.world = world
        self.interval = max(5, int(interval))
        self.frames = []            # [{"y": год, "key": веха, "rle": [...]}]
        self.slots = {}             # polity_id -> номер державы на карте
        self.city_seen = {}         # settlement_id -> последняя известная держава

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
        """Владение по гексам: номер державы или -1, если земля ничья."""
        wmap = self.link.wmap
        size = wmap.size
        owner = [-1] * size
        best = [1e9] * size

        queue = deque()
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
            queue.append((index, 0.0, reach, slot))

        # Волна от каждого города: ближе — значит его.
        while queue:
            index, distance, reach, slot = queue.popleft()
            if distance >= reach:
                continue
            step = distance + 1.0
            for neighbor in wmap.neighbors(index):
                if not wmap.is_land(neighbor):
                    continue
                if step < best[neighbor]:
                    best[neighbor] = step
                    owner[neighbor] = slot
                    queue.append((neighbor, step, reach, slot))
        return owner

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
            "routes": [],
            "roads": [],
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
