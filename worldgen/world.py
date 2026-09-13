# -*- coding: utf-8 -*-
"""Мир и его база данных.

World — единственное хранилище состояния. Все подсистемы генератора читают
и пишут только сюда, поэтому мир целиком сохраняется в файл и целиком
восстанавливается из него.
"""

from __future__ import annotations

import heapq

from . import races as races_mod
from .models import (ACTIVE, FALLEN, GONE, RUINED, Camp, Event, Figure,
                     Polity, Region, Settlement, Tribe)
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
        self.events = []               # список Event в хронологическом порядке

        # Быстрые списки активных сущностей (поддерживаются в актуальном виде).
        self.active_tribes = []
        self.active_settlements = []
        self.active_polities = []
        self.active_camps = []

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
        if figure.death is not None:
            self._death_order += 1
            heapq.heappush(self._death_queue,
                           (figure.death.ordinal, self._death_order, figure.id))
        return figure

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
        """Личности, чей срок вышел к концу указанного года."""
        limit = year * 360
        result = []
        while self._death_queue and self._death_queue[0][0] < limit:
            _, _, figure_id = heapq.heappop(self._death_queue)
            result.append(self.figures[figure_id])
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

    # ------------------------------------------------------------------
    # Выборки
    # ------------------------------------------------------------------

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
        }.get(prefix)
        return table.get(entity_id) if table else None

    def entity_name(self, entity_id: str) -> str:
        item = self.entity(entity_id)
        if item is None:
            return "?"
        return getattr(item, "full_name", None) or item.name

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
