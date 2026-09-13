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

from dataclasses import dataclass, asdict

from .context import GenContext
from .eras import build_eras
from .rng import seed_to_int
from .systems import (calamity, era_events, founding, geography, houses, lives,
                      peoples, succession)
from .timeline import Date
from .world import World
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

    def normalized(self) -> "Settings":
        years = max(50, min(100000, int(self.years)))
        regions = max(6, min(60, int(self.regions)))
        density = max(0.2, min(3.0, float(self.density)))
        return Settings(seed=str(self.seed), years=years, regions=regions,
                        density=density)

    def to_dict(self) -> dict:
        return asdict(self)


def generate(settings: Settings, progress=None, should_stop=None) -> World:
    """Создаёт мир целиком. progress(доля, подпись) вызывается по ходу дела."""
    settings = settings.normalized()
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
        calamity.tick(ctx, year)
        lives.tick(ctx, year)

        if year % UPKEEP_PERIOD == 0:
            ctx.refresh_darkness(year)
            peoples.upkeep(ctx, year, UPKEEP_PERIOD)
            founding.upkeep(ctx, year, UPKEEP_PERIOD)
            houses.upkeep(ctx, year, UPKEEP_PERIOD)
            succession.upkeep(ctx, year, UPKEEP_PERIOD)
            calamity.upkeep(ctx, year, UPKEEP_PERIOD)

        era = era_ends.get(year)
        if era is not None:
            era_events.finish(ctx, era, is_last=(era.index == last_era_index))

        if progress is not None and year % step == 0:
            span = world.era_at(year)
            progress(year / float(total),
                     "%s, %d год" % (span.name if span else "", year))
        if should_stop is not None and year % 50 == 0 and should_stop():
            raise GenerationCancelled()

    _finalize(world)
    if progress is not None:
        progress(1.0, "Готово")
    return world


def _finalize(world: World) -> None:
    """Приводит летопись в порядок: строгий хронологический порядок событий."""
    world.refresh_populations()
    world.events.sort(key=lambda event: (event.date.ordinal, int(event.id[1:])))
