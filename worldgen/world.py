# -*- coding: utf-8 -*-
"""Мир и его база данных.

World — единственное хранилище состояния. Все подсистемы генератора читают
и пишут только сюда, поэтому мир целиком сохраняется в файл и целиком
восстанавливается из него.
"""

from __future__ import annotations

import heapq

from . import races as races_mod
from .models import (ACTIVE, ENDED, EXTINCT, FALLEN, GONE, ONGOING, RUINED,
                     Battle, Calamity, Camp, Event, Figure, House, Polity,
                     Region, Reign, Relic, Settlement, Tribe)

# Поселение в летописи — это город и кормящая его округа. Чтобы потери от
# бедствий считались в людях, а не в условных единицах, население страны
# считается с этим множителем.
RURAL_FACTOR = 5.5
from .timeline import Date


class World:
    """Состояние мира и вся накопленная летопись."""

    def __init__(self, seed_text: str, seed_value: int, total_years: int, settings=None):
        self.seed_text = seed_text
        self.seed_value = seed_value
        self.total_years = total_years
        self.settings = settings

        self.eras = []                 # список EraSpan
        self.regions = {}              # id -> Region
        self.figures = {}              # id -> Figure
        self.tribes = {}               # id -> Tribe
        self.settlements = {}          # id -> Settlement
        self.polities = {}             # id -> Polity
        self.camps = {}                # id -> Camp
        self.houses = {}               # id -> House  (знатные роды)
        self.reigns = {}               # id -> Reign  (правления)
        self.calamities = {}           # id -> Calamity (бедствия)
        self.relics = {}               # id -> Relic (следы бедствий)
        self.battles = {}              # id -> Battle (сражения)
        self.dark_ages = []            # тёмные века: последствия бедствий
        self.events = []               # список Event в хронологическом порядке

        # Быстрые списки активных сущностей (поддерживаются в актуальном виде).
        self.active_tribes = []
        self.active_settlements = []
        self.active_polities = []
        self.active_camps = []
        self.active_houses = []
        self.active_calamities = []
        self.sleeping_relics = []

        # Служебное
        self._counters = {}
        self._death_queue = []         # куча (год смерти, порядок, id личности)
        self._death_order = 0
        self.race_awakening = {}       # race_id -> год пробуждения
        self.notes = {}                # свободные заметки для будущих блоков

    # ------------------------------------------------------------------
    # Идентификаторы
    # ------------------------------------------------------------------

    def next_id(self, prefix: str) -> str:
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return "%s%d" % (prefix, value)

    # ------------------------------------------------------------------
    # Добавление сущностей
    # ------------------------------------------------------------------

    def add_region(self, **kwargs) -> Region:
        region = Region(id=self.next_id("R"), **kwargs)
        self.regions[region.id] = region
        return region

    def add_figure(self, **kwargs) -> Figure:
        figure = Figure(id=self.next_id("F"), **kwargs)
        self.figures[figure.id] = figure
        self._queue_death(figure)
        if figure.house_id:
            house = self.houses.get(figure.house_id)
            if house is not None:
                house.members.append(figure.id)
                house.living.append(figure.id)
                house.alive_count = len(house.living)
        return figure

    def _queue_death(self, figure) -> None:
        if figure.death is None:
            return
        self._death_order += 1
        heapq.heappush(self._death_queue,
                       (figure.death.ordinal, self._death_order, figure.id))

    def schedule_death(self, figure, date: Date, cause: str = "") -> None:
        """Переносит дату смерти (убийство, казнь, гибель) и обновляет очередь."""
        figure.death = date
        if cause:
            figure.death_cause = cause
        self._queue_death(figure)

    def add_house(self, **kwargs) -> House:
        house = House(id=self.next_id("H"), **kwargs)
        self.houses[house.id] = house
        self.active_houses.append(house.id)
        return house

    def add_calamity(self, **kwargs) -> Calamity:
        calamity = Calamity(id=self.next_id("D"), **kwargs)
        self.calamities[calamity.id] = calamity
        self.active_calamities.append(calamity.id)
        return calamity

    def add_relic(self, **kwargs) -> Relic:
        relic = Relic(id=self.next_id("L"), **kwargs)
        self.relics[relic.id] = relic
        if relic.status == "спит":
            self.sleeping_relics.append(relic.id)
        return relic

    def add_battle(self, **kwargs) -> Battle:
        battle = Battle(id=self.next_id("B"), **kwargs)
        self.battles[battle.id] = battle
        calamity = self.calamities.get(battle.calamity_id)
        if calamity is not None:
            calamity.battle_ids.append(battle.id)
        return battle

    def end_calamity(self, calamity, date: Date, resolution: str) -> None:
        if calamity.status != ONGOING:
            return
        calamity.status = ENDED
        calamity.end = date
        calamity.resolution = resolution
        if calamity.id in self.active_calamities:
            self.active_calamities.remove(calamity.id)

    def wake_relic(self, relic, date: Date) -> None:
        relic.status = "потревожен"
        relic.awakened = date
        if relic.id in self.sleeping_relics:
            self.sleeping_relics.remove(relic.id)

    def add_reign(self, **kwargs) -> Reign:
        reign = Reign(id=self.next_id("G"), **kwargs)
        self.reigns[reign.id] = reign
        polity = self.polities.get(reign.polity_id)
        if polity is not None:
            polity.reign_ids.append(reign.id)
        return reign

    def add_tribe(self, **kwargs) -> Tribe:
        tribe = Tribe(id=self.next_id("T"), **kwargs)
        self.tribes[tribe.id] = tribe
        self.active_tribes.append(tribe.id)
        return tribe

    def add_settlement(self, **kwargs) -> Settlement:
        settlement = Settlement(id=self.next_id("C"), **kwargs)
        self.settlements[settlement.id] = settlement
        self.active_settlements.append(settlement.id)
        return settlement

    def add_polity(self, **kwargs) -> Polity:
        polity = Polity(id=self.next_id("P"), **kwargs)
        self.polities[polity.id] = polity
        self.active_polities.append(polity.id)
        return polity

    def add_camp(self, **kwargs) -> Camp:
        camp = Camp(id=self.next_id("K"), **kwargs)
        self.camps[camp.id] = camp
        self.active_camps.append(camp.id)
        return camp

    def add_event(self, date: Date, era_index: int, kind: str, title: str,
                  text: str, importance: int = 2, actors=None, subjects=None,
                  region_id: str = "", race_id: str = "") -> Event:
        event = Event(
            id=self.next_id("V"), date=date, era_index=era_index, kind=kind,
            title=title, text=text, importance=importance,
            actors=list(actors or ()), subjects=list(subjects or ()),
            region_id=region_id, race_id=race_id,
        )
        self.events.append(event)
        for actor_id in event.actors:
            figure = self.figures.get(actor_id)
            if figure is not None:
                figure.deeds.append(event.id)
        return event

    # ------------------------------------------------------------------
    # Смерти по расписанию
    # ------------------------------------------------------------------

    def due_deaths(self, year: int) -> list:
        """Личности, чей срок вышел к концу указанного года.

        Запись могла устареть: если персонажа убили раньше срока, в очереди
        осталась его прежняя дата. Такие записи отбрасываются.
        """
        limit = year * 360
        result = []
        while self._death_queue and self._death_queue[0][0] < limit:
            ordinal, _, figure_id = heapq.heappop(self._death_queue)
            figure = self.figures[figure_id]
            if figure.death is not None and figure.death.ordinal == ordinal:
                result.append(figure)
        return result

    # ------------------------------------------------------------------
    # Изменение состояния
    # ------------------------------------------------------------------

    def end_tribe(self, tribe, date: Date, reason: str, status: str = GONE) -> None:
        if tribe.status not in (ACTIVE,):
            return
        tribe.status = status
        tribe.ended = date
        tribe.end_reason = reason
        if tribe.id in self.active_tribes:
            self.active_tribes.remove(tribe.id)

    def end_settlement(self, settlement, date: Date, reason: str,
                       status: str = RUINED) -> None:
        if settlement.status != ACTIVE:
            return
        settlement.status = status
        settlement.ended = date
        settlement.end_reason = reason
        if settlement.id in self.active_settlements:
            self.active_settlements.remove(settlement.id)
        polity = self.polities.get(settlement.polity_id)
        if polity is not None and settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)

    def end_polity(self, polity, date: Date, reason: str, status: str = FALLEN) -> None:
        if polity.status != ACTIVE:
            return
        reign = self.current_reign(polity)
        if reign is not None and reign.end is None:
            reign.end = date
            reign.end_reason = "гибель страны"
        house = self.houses.get(polity.house_id)
        if house is not None and house.rank == "правящий":
            house.rank = "великий"
        polity.status = status
        polity.ended = date
        polity.end_reason = reason
        if polity.id in self.active_polities:
            self.active_polities.remove(polity.id)
        for settlement_id in list(polity.settlement_ids):
            settlement = self.settlements.get(settlement_id)
            if settlement is not None and settlement.status == ACTIVE:
                settlement.polity_id = ""
                settlement.is_capital = False

    def end_camp(self, camp, date: Date, reason: str, status: str = GONE) -> None:
        if camp.status != ACTIVE:
            return
        camp.status = status
        camp.ended = date
        camp.end_reason = reason
        if camp.id in self.active_camps:
            self.active_camps.remove(camp.id)

    def end_house(self, house, date: Date, reason: str,
                  status: str = EXTINCT) -> None:
        if house.status != ACTIVE:
            return
        house.status = status
        house.ended = date
        house.end_reason = reason
        if house.id in self.active_houses:
            self.active_houses.remove(house.id)
        polity = self.polities.get(house.polity_id)
        if polity is not None and house.id in polity.house_ids:
            polity.house_ids.remove(house.id)

    # ------------------------------------------------------------------
    # Выборки
    # ------------------------------------------------------------------

    def house_members(self, house, alive_in_year: int = 0) -> list:
        """Члены рода; при указании года — только живые в этом году.

        Для живых перебирается короткий список house.living, а не вся
        история рода: за десять тысяч лет она вырастает до сотен имён.
        """
        source = house.living if alive_in_year else house.members
        people = [self.figures[fid] for fid in source if fid in self.figures]
        if alive_in_year:
            people = [p for p in people if p.alive_at(alive_in_year)]
        return people

    def current_reign(self, polity):
        if not polity.reign_ids:
            return None
        return self.reigns.get(polity.reign_ids[-1])

    def houses_of_polity(self, polity) -> list:
        return [self.houses[hid] for hid in polity.house_ids
                if hid in self.houses and self.houses[hid].status == ACTIVE]

    def houses_of_race(self, race_id: str) -> list:
        return [self.houses[hid] for hid in self.active_houses
                if self.houses[hid].race_id == race_id]

    def era_at(self, year: int):
        for span in self.eras:
            if span.contains(year):
                return span
        return self.eras[-1] if self.eras else None

    def era_index_at(self, year: int) -> int:
        span = self.era_at(year)
        return span.index if span else 0

    def tribes_of_race(self, race_id: str) -> list:
        return [self.tribes[tid] for tid in self.active_tribes
                if self.tribes[tid].race_id == race_id]

    def settlements_of_race(self, race_id: str) -> list:
        return [self.settlements[sid] for sid in self.active_settlements
                if self.settlements[sid].race_id == race_id]

    def free_settlements_of_race(self, race_id: str) -> list:
        """Города расы, ещё не входящие ни в одну страну."""
        return [s for s in self.settlements_of_race(race_id) if not s.polity_id]

    def polities_of_race(self, race_id: str) -> list:
        return [self.polities[pid] for pid in self.active_polities
                if self.polities[pid].race_id == race_id]

    def region(self, region_id: str):
        return self.regions.get(region_id)

    def entity(self, entity_id: str):
        """Универсальный доступ по идентификатору."""
        if not entity_id:
            return None
        prefix = entity_id[0]
        table = {
            "R": self.regions, "F": self.figures, "T": self.tribes,
            "C": self.settlements, "P": self.polities, "K": self.camps,
            "H": self.houses, "G": self.reigns, "D": self.calamities,
            "L": self.relics, "B": self.battles,
        }.get(prefix)
        return table.get(entity_id) if table else None

    def entity_name(self, entity_id: str) -> str:
        item = self.entity(entity_id)
        if item is None:
            return "?"
        return getattr(item, "full_name", None) or item.name

    # ------------------------------------------------------------------
    # Население
    # ------------------------------------------------------------------

    def settlement_realm(self, settlement) -> int:
        """Город вместе с кормящей его округой."""
        return int(settlement.population * RURAL_FACTOR)

    def refresh_populations(self) -> None:
        """Пересчитывает население стран по их поселениям."""
        totals = {}
        for settlement_id in self.active_settlements:
            settlement = self.settlements[settlement_id]
            if not settlement.polity_id:
                continue
            totals[settlement.polity_id] = totals.get(settlement.polity_id, 0) + \
                self.settlement_realm(settlement)
        for polity_id in self.active_polities:
            polity = self.polities[polity_id]
            polity.population = totals.get(polity_id, 0)
            polity.peak_population = max(polity.peak_population, polity.population)

    def world_population(self) -> int:
        total = 0
        for settlement_id in self.active_settlements:
            total += self.settlement_realm(self.settlements[settlement_id])
        for tribe_id in self.active_tribes:
            total += self.tribes[tribe_id].population
        for camp_id in self.active_camps:
            total += self.camps[camp_id].population
        return total

    def population_by_race(self) -> dict:
        totals = {}
        for settlement_id in self.active_settlements:
            settlement = self.settlements[settlement_id]
            totals[settlement.race_id] = totals.get(settlement.race_id, 0) + \
                self.settlement_realm(settlement)
        for tribe_id in self.active_tribes:
            tribe = self.tribes[tribe_id]
            totals[tribe.race_id] = totals.get(tribe.race_id, 0) + tribe.population
        for camp_id in self.active_camps:
            camp = self.camps[camp_id]
            totals[camp.race_id] = totals.get(camp.race_id, 0) + camp.population
        return totals

    # ------------------------------------------------------------------
    # Тёмные века
    # ------------------------------------------------------------------

    def add_dark_age(self, calamity_id: str, start: int, end: int,
                     region_ids, intensity: float, worldwide: bool = False) -> dict:
        record = {
            "calamity_id": calamity_id, "start": int(start), "end": int(end),
            "regions": list(region_ids), "intensity": float(intensity),
            "worldwide": bool(worldwide),
        }
        self.dark_ages.append(record)
        return record

    def darkness_snapshot(self, year: int) -> dict:
        """Карта тьмы на год: земля -> насколько тяжело в ней живётся (0…1).

        Ключ "" хранит общемировую тяжесть.
        """
        snapshot = {}
        for record in self.dark_ages:
            if not (record["start"] <= year <= record["end"]):
                continue
            value = record["intensity"]
            # К концу тёмных веков становится легче.
            span = max(1, record["end"] - record["start"])
            value *= max(0.25, 1.0 - (year - record["start"]) / float(span) * 0.75)
            if record["worldwide"]:
                snapshot[""] = max(snapshot.get("", 0.0), value)
            for region_id in record["regions"]:
                snapshot[region_id] = max(snapshot.get(region_id, 0.0), value)
        return snapshot

    # ------------------------------------------------------------------
    # Итоги
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        final_year = self.total_years
        alive_figures = sum(1 for f in self.figures.values()
                            if f.alive_at(final_year))
        return {
            "Сид": self.seed_text,
            "Длительность": "%d лет" % self.total_years,
            "Эпох": len(self.eras),
            "Земель": len(self.regions),
            "Событий": len(self.events),
            "Личностей": len(self.figures),
            "Живых на конец истории": alive_figures,
            "Племён (всего)": len(self.tribes),
            "Племён (живых)": len(self.active_tribes),
            "Поселений (всего)": len(self.settlements),
            "Поселений (живых)": len(self.active_settlements),
            "Стран (всего)": len(self.polities),
            "Стран (живых)": len(self.active_polities),
            "Лагерей (всего)": len(self.camps),
            "Лагерей (живых)": len(self.active_camps),
            "Знатных родов (всего)": len(self.houses),
            "Знатных родов (живых)": len(self.active_houses),
            "Правлений": len(self.reigns),
            "Бедствий": len(self.calamities),
            "Сражений": len(self.battles),
            "Следов бедствий": len(self.relics),
            "Тёмных веков": len(self.dark_ages),
            "Население мира": "%d" % self.world_population(),
            "Погибло от бедствий": "%d" % sum(
                c.deaths for c in self.calamities.values()),
        }

    def race_summary(self) -> list:
        """Сводка по расам: когда пробудились, что основали и что уцелело."""
        blank = {"tribes": [0, 0], "settlements": [0, 0], "polities": [0, 0],
                 "camps": [0, 0], "figures": [0, 0]}
        counts = {race.id: {key: list(value) for key, value in blank.items()}
                  for race in races_mod.RACES}

        def tally(items, key):
            for item in items:
                row = counts.get(item.race_id)
                if row is None:
                    continue
                row[key][0] += 1
                if getattr(item, "status", ACTIVE) == ACTIVE:
                    row[key][1] += 1

        tally(self.tribes.values(), "tribes")
        tally(self.settlements.values(), "settlements")
        tally(self.polities.values(), "polities")
        tally(self.camps.values(), "camps")
        final_year = self.total_years
        for figure in self.figures.values():
            row = counts.get(figure.race_id)
            if row is None:
                continue
            row["figures"][0] += 1
            if figure.alive_at(final_year):
                row["figures"][1] += 1

        rows = []
        for race in races_mod.RACES:
            row = dict(counts[race.id])
            row["race"] = race
            row["awakening"] = self.race_awakening.get(race.id)
            rows.append(row)
        return rows
