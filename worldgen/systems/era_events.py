# -*- coding: utf-8 -*-
"""Начало и конец эпох.

Эпоха не просто кончается по календарю: её обрывает событие мирового
масштаба. Оно уносит часть стран, городов, племён и лагерей — и именно
по нему эпоху потом называют.
"""

from __future__ import annotations

from .. import narrative
from ..eras import spec_for
from ..models import FALLEN, GONE, RUINED
from ..narrative_calamity import souls as _souls
from ..timeline import DAYS_IN_MONTH, MONTHS_IN_YEAR, Date


def begin(ctx, era) -> None:
    world = ctx.world
    rng = ctx.rng("era_begin", era.index)
    spec = spec_for(era.index)
    title, text = narrative.era_begin(rng, era, spec)
    world.add_event(
        date=Date(era.start_year, 1, 1), era_index=era.index, kind="era_begin",
        title=title, text=text, importance=5,
    )


def finish(ctx, era, is_last: bool) -> None:
    world = ctx.world
    rng = ctx.rng("era_end", era.index)
    spec = spec_for(era.index)
    date = Date(era.end_year, MONTHS_IN_YEAR, DAYS_IN_MONTH)

    losses = {"polities": 0, "settlements": 0, "tribes": 0, "camps": 0}
    if not is_last:
        losses = _cataclysm(ctx, era, rng, date)

    title, text = narrative.era_end(rng, era, spec, losses, is_last=is_last)
    # Численность живых на конец эпохи — чтобы было видно, растёт мир или
    # только хоронит.
    world.refresh_populations()
    population = world.world_population()
    if population:
        text += " К концу эпохи в мире живёт %s." % _souls(population)
    event = world.add_event(
        date=date, era_index=era.index, kind="era_end", title=title, text=text,
        importance=5,
    )
    era.end_event_id = event.id
    era.end_title = title


def _cataclysm(ctx, era, rng, date) -> dict:
    """Уносит часть мира. Чем позже эпоха, тем больше терять."""
    world = ctx.world
    losses = {"polities": 0, "settlements": 0, "tribes": 0, "camps": 0}

    # Страны — поимённо, это событие заметное.
    polity_share = rng.uniform(0.10, 0.34)
    doomed = _pick(rng, list(world.active_polities), polity_share)
    for polity_id in doomed:
        polity = world.polities[polity_id]
        world.end_polity(polity, date, "гибель в конце эпохи", FALLEN)
        world.add_event(
            date=date, era_index=era.index, kind="polity_fall",
            title="Падение: %s" % polity.name,
            text="Конец эпохи не пощадил и эту страну. %s" % (
                narrative.polity_fall_text(rng, polity),),
            importance=3, subjects=[polity.id], race_id=polity.race_id,
        )
        losses["polities"] += 1

    for settlement_id in _pick(rng, list(world.active_settlements),
                               rng.uniform(0.04, 0.15)):
        settlement = world.settlements[settlement_id]
        world.end_settlement(settlement, date, "гибель в конце эпохи", RUINED)
        losses["settlements"] += 1

    for tribe_id in _pick(rng, list(world.active_tribes), rng.uniform(0.06, 0.20)):
        tribe = world.tribes[tribe_id]
        world.end_tribe(tribe, date, "гибель в конце эпохи", GONE)
        losses["tribes"] += 1

    for camp_id in _pick(rng, list(world.active_camps), rng.uniform(0.10, 0.35)):
        camp = world.camps[camp_id]
        world.end_camp(camp, date, "гибель в конце эпохи", GONE)
        losses["camps"] += 1

    return losses


def _pick(rng, items, share: float) -> list:
    if not items:
        return []
    count = int(round(len(items) * share))
    if count <= 0:
        return []
    return rng.shuffled(items)[:count]
