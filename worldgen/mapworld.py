# -*- coding: utf-8 -*-
"""Связь движка истории с картой мира.

Карта отвечает на вопрос «где и как тут живётся», история — на вопрос
«что с народами случилось». Этот модуль переводит первое во второе:

* земли карты становятся землями мира со своей ёмкостью и местностью;
* поселения садятся не «в землю вообще», а в конкретный гекс — тот, где
  карта обещает лучшую жизнь; поэтому их потом можно нанести на карту;
* лента долгосрочного климата карты превращается в расписание бедствий:
  ледниковый период случится ровно в тот год, который вшит в сид карты;
* логова существ ложатся спящими следами — тысячелетия спустя их разбудят;
* маска местных бедствий решает, чем именно грозит каждая земля: где
  вулкан — извержением, где сухо — засухой, где море — цунами.

Ничего случайного сверх наших же потоков ГСЧ: одна карта плюс один сид
дают одну и ту же историю.
"""

from __future__ import annotations

from . import mapregions
from . import worldmap as wm

# --- местные бедствия карты -> виды бедствий движка ---------------------
MAP_EVENT_CALAMITY = {
    0: "storm_years",      # Ураган
    1: "drought",          # Песчаная буря
    2: "storm_years",      # Снежный буран
    3: "eruption",         # Извержение
    4: "flood",            # Паводок
    5: "wildfire",         # Лесной пожар
    6: "earthquake",       # Лавина
    7: "flood",            # Цунами
    8: "drought",          # Засуха
    9: "plague",           # Поветрие
    10: "earthquake",      # Землетрясение
}
BOUNTY_EVENTS = (11, 12, 13, 14, 15)     # добрые приметы: урожай, рыбный ход, цветение

# --- лента климата карты -> долгие бедствия движка ----------------------
CLIMATE_CALAMITY = {
    "ice_age": "glaciation",
    "grand_winter": "glaciation",
    "warming": "long_warming",
    "volcanic_winter": "volcanic_winter",
    "impact_winter": "volcanic_winter",
    "megadrought": "drought",
    "pluvial": "sea_rise",
    "mana_surge": "wild_magic",
}

# --- логова карты -> чем они обернутся, когда проснутся ------------------
LAIR_CALAMITY = {
    "dragon-incursion": "dragon_flight",
    "leviathan-surge": "deep_ones",
    "serpent-coil": "beast_tide",
    "storm-of-wings": "beast_tide",
    "colossus-march": "beast_tide",
    "titan-fall": "planar_rift",
}
LAIR_RELIC_KIND = {
    "dragon": "драконье логово",
    "leviathan": "затонувший храм",
    "worm": "логово",
    "thunderbird": "логово",
    "colossus": "проклятое место",
    "titan": "разлом",
}
# Насколько давно логово лежит: «ancient» просыпается неохотно, но страшно.
LAIR_POTENCY = {"ancient": 5, "dormant": 3, "remnant": 2}


class MapLink:
    """Всё, что движок истории берёт у карты."""

    def __init__(self, wmap, path: str = ""):
        self.wmap = wmap
        self.path = path
        self.regions = {}            # region_id -> MapRegion
        self.region_of_hex = {}      # индекс гекса -> region_id
        self.taken = set()           # занятые гексы: город, лагерь, стоянка
        self.hex_owner = {}          # индекс гекса -> id поселения или лагеря
        self._risk_index = None      # вид беды -> {земля: насколько она ей грозит}
        self._magic_span = None      # разброс магии на этой карте

    # ------------------------------------------------------------------
    # Постройка земель
    # ------------------------------------------------------------------

    def build(self, ctx, rng, target: int) -> list:
        """Режет карту на земли и заводит их в мире."""
        world = ctx.world
        pieces = mapregions.build_regions(self.wmap, ctx, rng, target)

        made = []
        for piece in pieces:
            region = world.add_region(
                name=piece.name, terrain=piece.terrain,
                x=piece.x, y=piece.y, capacity=piece.capacity,
            )
            region.hexes = piece.hexes
            region.center_hex = piece.center
            region.habitat = round(piece.habitat, 3)
            region.fertility = round(piece.fertility, 3)
            region.magic = round(piece.magic, 4)
            region.savagery = round(piece.savagery, 3)
            region.richness = round(piece.richness, 3)
            region.risk = round(piece.risk, 3)
            region.risk_kinds = piece.risk_kinds
            region.boons = piece.boons
            region.coastal = piece.coastal
            region.river = piece.river
            region.island = piece.island
            region.elev_m = int(piece.elev_m)
            region.temp = round(piece.temp, 1)
            region.moist = round(piece.moist, 3)
            region.landmass = piece.landmass
            made.append(region)
            self.regions[region.id] = piece
            for index in piece.hexes:
                self.region_of_hex[index] = region.id

        # Соседство переносим уже по настоящим идентификаторам.
        for slot, piece in enumerate(pieces):
            region = made[slot]
            region.neighbors = [made[other].id for other in sorted(piece.neighbors)
                                if 0 <= other < len(made)]
        return made

    # ------------------------------------------------------------------
    # Где селиться
    # ------------------------------------------------------------------

    def place(self, region_id: str, rng, kind: str = "city") -> int:
        """Гекс под поселение: там, где карта обещает лучшую жизнь.

        Города садятся на плодородное и по возможности у воды, лагеря злых
        народов — наоборот, в глушь подальше от чужих глаз.
        """
        piece = self.regions.get(region_id)
        if piece is None or not piece.hexes:
            return -1
        wmap = self.wmap
        fert = wmap.layer(wm.L_FERTILITY)
        savage = wmap.layer(wm.L_SAVAGERY)

        best, best_score = -1, -1e18
        for index in piece.hexes:
            if index in self.taken:
                continue
            score = float(fert[index]) if fert is not None else 0.5
            if kind == "camp":
                # Логово прячется: чем глуше и злее место, тем лучше.
                score = (savage[index] / 255.0 if savage is not None else 0.4) \
                    - 0.5 * score
            else:
                if wmap.is_river(index):
                    score += 0.35
                if wmap.is_coast(index):
                    score += 0.25
            # Небольшой разброс, чтобы города одной земли не жались в одну точку.
            score += rng.uniform(0.0, 0.12)
            if score > best_score:
                best, best_score = index, score
        if best < 0:
            best = piece.center
        return best

    def claim(self, index: int, owner_id: str) -> None:
        if index is None or index < 0:
            return
        self.taken.add(index)
        self.hex_owner[index] = owner_id
        # Ближайшие гексы тоже занимаем: два города вплотную не стоят.
        for neighbor in self.wmap.neighbors(index):
            self.taken.add(neighbor)

    def release(self, index: int) -> None:
        if index is None or index < 0:
            return
        self.hex_owner.pop(index, None)

    # ------------------------------------------------------------------
    # Чем грозит земля
    # ------------------------------------------------------------------

    def risk_weights(self, region_id: str) -> dict:
        """Виды бедствий, которых стоит ждать именно в этой земле."""
        piece = self.regions.get(region_id)
        if piece is None:
            return {}
        mask_layer = self.wmap.layer(wm.L_EVENTMASK)
        chance_layer = self.wmap.layer(wm.L_EVENTCHANCE)
        if mask_layer is None:
            return {}
        weights = {}
        hexes = piece.hexes
        count = float(len(hexes)) or 1.0
        for index in hexes:
            mask = mask_layer[index] & 0xFFFF
            if not mask:
                continue
            force = (chance_layer[index] / 255.0) if chance_layer is not None else 0.5
            for bit, key in MAP_EVENT_CALAMITY.items():
                if mask & (1 << bit):
                    weights[key] = weights.get(key, 0.0) + force
        return {key: value / count for key, value in weights.items()}

    def risk_index(self) -> dict:
        """Карта угроз по всему миру: какая беда какой земле грозит.

        Считается один раз: маска бедствий вшита в карту и не меняется.
        """
        if self._risk_index is None:
            index = {}
            for region_id in self.regions:
                for key, weight in self.risk_weights(region_id).items():
                    index.setdefault(key, {})[region_id] = weight
            self._risk_index = index
        return self._risk_index

    def risk_of(self, key: str, region_id: str) -> float:
        return self.risk_index().get(key, {}).get(region_id, 0.0)

    def world_risk(self, key: str) -> float:
        """Насколько такая беда вообще свойственна этому миру."""
        spread = self.risk_index().get(key)
        if not spread:
            return 0.0
        return sum(spread.values()) / float(len(self.regions) or 1)

    def bounty(self, region_id: str) -> float:
        """Насколько земля щедра: урожайные годы, рыбный ход, мягкие зимы."""
        piece = self.regions.get(region_id)
        mask_layer = self.wmap.layer(wm.L_EVENTMASK)
        if piece is None or mask_layer is None:
            return 0.0
        total = 0
        for index in piece.hexes:
            mask = mask_layer[index] & 0xFFFF
            total += sum(1 for bit in BOUNTY_EVENTS if mask & (1 << bit))
        return total / float(len(piece.hexes) * len(BOUNTY_EVENTS) or 1)

    # ------------------------------------------------------------------
    # Лента климата
    # ------------------------------------------------------------------

    def climate_schedule(self, total_years: int) -> list:
        """Климат-события карты, разложенные по годам истории.

        Карта считает свою ленту на десять тысяч лет. Если история короче
        или длиннее, лента растягивается вместе с ней.
        """
        climate = self.wmap.climate
        events = climate.get("events") or []
        span = float(climate.get("worldSpan") or 10000)
        scale = total_years / span if span else 1.0

        out = []
        for event in events:
            key = CLIMATE_CALAMITY.get(event.get("type"))
            if not key:
                continue
            start = int(round(event.get("start", 0) * scale))
            duration = max(1, int(round(event.get("dur", 1) * scale)))
            out.append({
                "key": key,
                "name": event.get("name", ""),
                "type": event.get("type", ""),
                "start": max(1, start),
                "years": duration,
                "dT": float(event.get("dT", 0.0)),
                "dP": float(event.get("dP", 0.0)),
                "dMag": float(event.get("dMag", 0.0)),
                "severity": _climate_severity(event),
            })
        out.sort(key=lambda item: (item["start"], item["key"]))
        return out

    def magic_of(self, region_id: str) -> float:
        """Магия земли, приведённая к -1…+1 по разбросу этой карты.

        Минус — земля дурная: там охотнее приживаются тёмные культы.
        Плюс — светлая, там чаще являются благие боги.
        """
        piece = self.regions.get(region_id)
        if piece is None:
            return 0.0
        scale = self._magic_scale()
        return max(-1.0, min(1.0, piece.magic / scale)) if scale else 0.0

    def _magic_scale(self) -> float:
        if self._magic_span is None:
            values = [abs(piece.magic) for piece in self.regions.values()]
            self._magic_span = max(values) if values else 0.0
        return self._magic_span

    def latitude_of(self, region_id: str) -> float:
        """Широта земли: +1 — полюс севера, -1 — юга."""
        piece = self.regions.get(region_id)
        if piece is None:
            return 0.0
        return self.wmap.latitude(piece.center)

    def regions_for_climate(self, kind: str, count: int) -> list:
        """Кого именно накроет эта перемена климата.

        Ледники ползут от полюсов, засуха выжигает и без того сухое,
        наступление моря топит побережья. Карта знает, где что.
        """
        scored = []
        for region_id, piece in self.regions.items():
            lat = abs(self.wmap.latitude(piece.center))
            if kind in ("ice_age", "grand_winter", "volcanic_winter", "impact_winter"):
                score = lat * 2.0 + max(0.0, (5.0 - piece.temp) / 20.0)
            elif kind == "warming":
                score = (1.0 - lat) * 1.4 + piece.temp / 40.0
            elif kind == "megadrought":
                score = (1.0 - piece.moist) * 2.0 + (1.0 - lat)
            elif kind == "pluvial":
                score = (1.6 if piece.coastal else 0.0) + piece.moist
            elif kind == "mana_surge":
                score = abs(piece.magic) * 6.0 + 0.2
            else:
                score = 1.0
            scored.append((score, region_id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [region_id for _, region_id in scored[:max(1, count)]]

    # ------------------------------------------------------------------
    # Логова
    # ------------------------------------------------------------------

    def lair_seeds(self, total_years: int) -> list:
        """Логова карты как будущие спящие следы."""
        span = 10000.0
        scale = total_years / span if span else 1.0
        out = []
        for lair in self.wmap.lairs:
            index = int(lair.get("i", -1))
            region_id = self.region_of_hex.get(index)
            if region_id is None:
                region_id = self._nearest_region(index)
            if region_id is None:
                continue
            klass = lair.get("catastropheClass") or ""
            age = int(round(float(lair.get("suggestedAgeYears") or 0) * scale))
            out.append({
                "name": mapregions.translit(lair.get("name", "")),
                "kind_name": lair.get("kindName") or "логово",
                "relic_kind": LAIR_RELIC_KIND.get(lair.get("kind"), "логово"),
                "calamity_key": LAIR_CALAMITY.get(klass, "beast_tide"),
                "region_id": region_id,
                "hex": index,
                "role": lair.get("role") or "dormant",
                "tier": int(lair.get("tier") or 1),
                "potency": LAIR_POTENCY.get(lair.get("role"), 3),
                "age": max(0, age),
                "alignment": float(lair.get("alignment") or 0.0),
            })
        out.sort(key=lambda item: (item["region_id"], item["name"]))
        return out

    def tribe_seeds(self) -> list:
        """Стоянки, которые карта заранее сочла пригодными для племён."""
        out = []
        for tribe in self.wmap.map_tribes:
            index = int(tribe.get("anchor", -1))
            region_id = self.region_of_hex.get(index) or self._nearest_region(index)
            if region_id is None:
                continue
            out.append({
                "name": mapregions.translit(tribe.get("name", "")),
                "region_id": region_id,
                "hex": index,
                "marine": bool(tribe.get("marine")),
                "mammoth": bool(tribe.get("mammoth")),
            })
        out.sort(key=lambda item: (item["region_id"], item["name"]))
        return out

    def _nearest_region(self, index: int):
        if index < 0 or not self.region_of_hex:
            return None
        wmap = self.wmap
        column, row = wmap.col_row(index)
        best, best_distance = None, 1e18
        for other, region_id in self.region_of_hex.items():
            ocolumn, orow = wmap.col_row(other)
            dx = abs(ocolumn - column)
            if wmap.wrap:
                dx = min(dx, wmap.width - dx)
            distance = dx * dx + (orow - row) ** 2
            if distance < best_distance:
                best, best_distance = region_id, distance
        return best

    # ------------------------------------------------------------------
    # Сводка
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        data = self.wmap.describe()
        data["Земель истории"] = len(self.regions)
        return data


def _climate_severity(event) -> int:
    """Насколько тяжело это климат-событие по меркам движка."""
    weight = abs(float(event.get("dT", 0.0))) / 2.0 \
        + abs(float(event.get("dP", 0.0))) * 3.0 \
        + abs(float(event.get("dMag", 0.0))) * 2.0
    duration = float(event.get("dur", 1))
    weight += min(2.0, duration / 900.0)
    return max(2, min(5, int(round(1.5 + weight))))


def homeland_score(link, race) -> float:
    """Есть ли этой расе где жить на этой карте.

    Ноль означает, что мир для неё не создан: ни одной подходящей земли.
    Тогда раса не просыпается вовсе — и мир без гор остаётся без дворфов.
    """
    best = 0.0
    for piece in link.regions.values():
        if piece.terrain in race.terrains:
            rank = race.terrains.index(piece.terrain)
            value = (1.0 / (1.0 + rank)) * (0.35 + piece.habitat)
            if piece.terrain in race.terrains[:2]:
                value *= 1.4
            best = max(best, value)
    return best
