# -*- coding: utf-8 -*-
"""Движок генерации истории.

Порядок работы:

1. по сиду раскладываются эпохи;
2. создаётся карта земель;
3. составляется расписание пробуждения рас;
4. год за годом прокручиваются подсистемы;
5. каждые несколько лет — «медленный такт»: рост населения, упадок, гибель.

Всё, что происходит, пишется в World. Никакой недетерминированности:
один и тот же сид даёт побайтово одну и ту же историю.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field

from .chronicle_map import MapRecorder
from .context import GenContext
from .eras import build_eras
from .rng import normalize_seed, seed_to_int
from .systems import (aristocracy, artifacts, cabals, calamity, causes,
                      citylife,
                      crafts, culture,
                      diplomacy, embassy,
                      era_events,
                      exploration, founding, geography, guilds, houses,
                      laws, legacy, lives, lore, memory, migration, monsters,
                      nations,
                      notables,
                      peoples,
                      religion,
                      sites, soldiery, spies, strife, succession, tongues,
                      trade,
                      unions, upheaval, war)
from .timeline import Date
from .world import World
from . import tuning
from . import narrative

UPKEEP_PERIOD = 10          # раз во столько лет пересчитываются население и упадок


class GenerationCancelled(Exception):
    """Генерацию прервали снаружи."""


@dataclass
class Settings:
    """Настройки, задаваемые перед генерацией."""

    seed: str = "Начало"
    years: int = 10000
    regions: int = 18
    density: float = 1.0
    map_path: str = ""          # файл .world; пусто — процедурная карта
    map_interval: int = 50      # раз во столько лет снимается кадр границ
    # Положения шкал настроек: ключ -> деление 0…100. Пусто — движок
    # работает так, как задуман.
    tuning: dict = field(default_factory=dict)
    # Своя карта: если заполнено, гексовая карта делается на месте, а не
    # берётся файлом. Ключи — как у mapforge.forge: seed, size, land_share,
    # roughness, warmth, wetness, magic.
    map_make: dict = field(default_factory=dict)

    def normalized(self) -> "Settings":
        years = max(50, min(100000, int(self.years)))
        regions = max(6, min(60, int(self.regions)))
        density = max(0.2, min(3.0, float(self.density)))
        knobs = {}
        for key, value in (self.tuning or {}).items():
            try:
                knobs[str(key)] = max(0, min(100, int(value)))
            except (TypeError, ValueError):
                continue
        # Код сида приводится к единому виду: «kr7m93xd» и «KR7M-93XD» —
        # один и тот же мир. Обычные слова остаются как написаны.
        return Settings(seed=normalize_seed(self.seed), years=years,
                        regions=regions,
                        density=density, map_path=str(self.map_path or ""),
                        map_interval=max(5, min(1000, int(self.map_interval))),
                        tuning=knobs,
                        map_make=dict(self.map_make or {}))

    def to_dict(self) -> dict:
        return asdict(self)


def generate(settings: Settings, progress=None, should_stop=None) -> World:
    """Создаёт мир целиком. progress(доля, подпись) вызывается по ходу дела."""
    settings = settings.normalized()
    # Числа движка расставляются по шкалам настроек целиком, даже если
    # настроек нет: так одно и то же положение шкал всегда даёт один и
    # тот же мир, что бы ни крутили в этом окне до него.
    tuning.apply(settings.tuning)
    world = World(
        seed_text=str(settings.seed),
        seed_value=seed_to_int(settings.seed),
        total_years=settings.years,
        settings=settings.to_dict(),
    )
    ctx = GenContext(world, settings)

    world.eras = build_eras(ctx.rng("eras"), settings.years)
    geography.build(ctx)

    rng = ctx.rng("world_begin")
    title, text = narrative.world_begin(rng, world)
    world.add_event(date=Date(1, 1, 1), era_index=0, kind="world_begin",
                    title=title, text=text, importance=5)

    peoples.plan_awakenings(ctx)
    calamity.prepare(ctx)
    religion.prepare(ctx)

    # По настоящей карте ведём ещё и политическую летопись: кто чем владел
    # в такой-то год. Её потом читает вкладка «Страны» картогенератора.
    recorder = None
    if ctx.map is not None:
        recorder = MapRecorder(ctx.map, world, settings.map_interval,
                               travel=ctx.travel)
        world.map_recorder = recorder

    total = settings.years
    step = max(1, total // 120)
    era_ends = {era.end_year: era for era in world.eras}
    era_starts = {era.start_year: era for era in world.eras}
    last_era_index = len(world.eras) - 1

    for year in range(1, total + 1):
        era = era_starts.get(year)
        if era is not None:
            era_events.begin(ctx, era)

        peoples.tick_awakening(ctx, year)
        peoples.tick_tribes(ctx, year)
        founding.tick_settling(ctx, year)
        founding.tick_polities(ctx, year)
        founding.tick_colonies(ctx, year)
        founding.tick_camps(ctx, year)
        succession.tick(ctx, year)
        exploration.tick(ctx, year)
        nations.tick(ctx, year)
        # Прежде чем мир начнёт новый год, он вспоминает старые долги:
        # созревшие последствия прошлого входят в него первыми.
        causes.tick(ctx, year)
        strife.tick(ctx, year)
        war.tick(ctx, year)
        notables.tick(ctx, year)
        calamity.tick(ctx, year)
        legacy.tick(ctx, year)
        religion.tick(ctx, year)
        lives.tick(ctx, year)

        if year % UPKEEP_PERIOD == 0:
            ctx.refresh_darkness(year)
            peoples.upkeep(ctx, year, UPKEEP_PERIOD)
            founding.upkeep(ctx, year, UPKEEP_PERIOD)
            houses.upkeep(ctx, year, UPKEEP_PERIOD)
            aristocracy.upkeep(ctx, year, UPKEEP_PERIOD)
            succession.upkeep(ctx, year, UPKEEP_PERIOD)
            nations.upkeep(ctx, year, UPKEEP_PERIOD)
            diplomacy.upkeep(ctx, year, UPKEEP_PERIOD)
            embassy.upkeep(ctx, year, UPKEEP_PERIOD)
            unions.upkeep(ctx, year, UPKEEP_PERIOD)
            spies.upkeep(ctx, year, UPKEEP_PERIOD)
            war.upkeep(ctx, year, UPKEEP_PERIOD)
            strife.upkeep(ctx, year, UPKEEP_PERIOD)
            cabals.upkeep(ctx, year, UPKEEP_PERIOD)
            soldiery.upkeep(ctx, year, UPKEEP_PERIOD)
            tongues.upkeep(ctx, year, UPKEEP_PERIOD)
            exploration.upkeep(ctx, year, UPKEEP_PERIOD)
            trade.upkeep(ctx, year, UPKEEP_PERIOD)
            guilds.upkeep(ctx, year, UPKEEP_PERIOD)
            artifacts.upkeep(ctx, year, UPKEEP_PERIOD)
            crafts.upkeep(ctx, year, UPKEEP_PERIOD)
            laws.upkeep(ctx, year, UPKEEP_PERIOD)
            citylife.upkeep(ctx, year, UPKEEP_PERIOD)
            monsters.upkeep(ctx, year, UPKEEP_PERIOD)
            sites.upkeep(ctx, year, UPKEEP_PERIOD)
            lore.upkeep(ctx, year, UPKEEP_PERIOD)
            calamity.upkeep(ctx, year, UPKEEP_PERIOD)
            causes.upkeep(ctx, year, UPKEEP_PERIOD)
            memory.upkeep(ctx, year, UPKEEP_PERIOD)
            migration.upkeep(ctx, year, UPKEEP_PERIOD)
            culture.upkeep(ctx, year, UPKEEP_PERIOD)
            upheaval.upkeep(ctx, year, UPKEEP_PERIOD)
            religion.upkeep(ctx, year, UPKEEP_PERIOD)

        era = era_ends.get(year)
        if era is not None:
            era_events.finish(ctx, era, is_last=(era.index == last_era_index))

        if recorder is not None:
            boundary = era is not None or year in era_starts or year == total
            if recorder.should_record(year, boundary):
                recorder.record(year, boundary)

        if progress is not None and year % step == 0:
            span = world.era_at(year)
            progress(year / float(total),
                     "%s, %d год" % (span.name if span else "", year))
        if should_stop is not None and year % 50 == 0 and should_stop():
            raise GenerationCancelled()

    tongues.close(ctx, total)
    _finalize(world)
    if progress is not None:
        progress(1.0, "Готово")
    return world


def _finalize(world: World) -> None:
    """Приводит летопись в порядок: строгий хронологический порядок событий."""
    world.refresh_populations()
    world.refresh_faiths()
    world.events.sort(key=lambda event: (event.date.ordinal, int(event.id[1:])))
