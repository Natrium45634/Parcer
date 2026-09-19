# -*- coding: utf-8 -*-
"""Династические унии: когда две короны сходятся на одной голове.

Брачный договор двух держав — не бумага, а свадьба, и внуки этой свадьбы
однажды оказываются ближайшими по крови к чужому пустому престолу. Тогда
державы не воюют и не сливаются: у них просто становится один государь.

Уния держится ровно до тех пор, пока обе короны достаются одному
наследнику. Разошлись наследники — разошлись и державы. А если под одной
короной выросло второе поколение, младшая держава может и вовсе
раствориться в старшей: без войска, одной грамотой.
"""

from __future__ import annotations

from . import houses as houses_mod
from . import nations as nations_mod
from .. import diplomacy as dip
from .. import narrative_union as texts
from ..models import ACTIVE, ENDED

MERGE_AFTER = 80            # раньше этого о слиянии речи нет
MERGE_RATE = 0.07           # и потом — не вдруг
UNION_RELATION = 0.55       # ниже этого отношения у державы с самой собой не бывает


# ---------------------------------------------------------------------------
# Право на пустой престол
# ---------------------------------------------------------------------------

def claim(ctx, polity, race, year: int):
    """Чужой государь, у которого есть право на этот опустевший престол.

    Право даёт брак: кто-то из здешнего правящего дома был женат на
    члене чужого дома, а тот дом сидит на престоле за межой. Корону
    чужой расы так не наследуют — знать её попросту не примет.
    """
    world = ctx.world
    house = world.houses.get(polity.house_id)
    if house is None:
        return None

    thrones = {}
    for other_id in world.active_polities:
        other = world.polities[other_id]
        if other.id == polity.id or not other.house_id:
            continue
        if other.race_id != polity.race_id:
            continue
        thrones.setdefault(other.house_id, []).append(other)
    if not thrones:
        return None

    seen, options = set(), []
    for member in world.house_members(house):
        spouse = world.figures.get(member.spouse_id)
        if spouse is None or not spouse.house_id \
                or spouse.house_id == house.id:
            continue
        for other in thrones.get(spouse.house_id, ()):
            king = world.figures.get(other.ruler_id)
            if king is None or not king.alive_at(year):
                continue
            if king.age_at(year) < race.adulthood:
                continue
            if king.id == polity.ruler_id or (other.id, king.id) in seen:
                continue
            if world.war_between(polity.id, other.id) is not None:
                continue
            seen.add((other.id, king.id))
            kin = world.houses.get(other.house_id)
            options.append(((other, king), max(0.3, kin.prestige if kin
                                               else 1.0)))
    if not options:
        return None
    return ctx.rng("union", polity.id, year).weighted(options)


def form(ctx, first, second, monarch, year: int, date, rng):
    """Записывает унию: first — держава государя, second — вторая корона.

    Третьей короны на той же голове не бывает: если какая-то из держав
    уже состоит в унии, прежняя уния при этом кончается — иначе держава
    числилась бы разом в двух, а помнила бы только последнюю.
    """
    world = ctx.world
    for polity in (first, second):
        running = world.unions.get(polity.union_id)
        if running is not None and running.status == ACTIVE:
            _close(ctx, running, world.polities.get(running.first_id),
                   world.polities.get(running.second_id), year, rng,
                   reason="корона ушла в новую унию", absorbed=True)
    union = world.add_union(
        first_id=first.id, second_id=second.id, monarch_id=monarch.id,
        started=date, monarchs=[monarch.id])
    dip.set_relation(first, second,
                     max(UNION_RELATION, dip.relation(first, second.id)))
    title, text = texts.union_formed(rng, first, second, monarch)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="union",
        title=title, text=text, importance=4, actors=[monarch.id],
        subjects=[union.id, first.id, second.id],
        region_id=second.region_ids[0] if second.region_ids else "",
        race_id=second.race_id)
    return union


# ---------------------------------------------------------------------------
# Жизнь унии
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("unions", year)
    for union_id in list(world.active_unions):
        union = world.unions[union_id]
        first = world.polities.get(union.first_id)
        second = world.polities.get(union.second_id)
        if first is None or second is None or first.status != ACTIVE \
                or second.status != ACTIVE:
            _close(ctx, union, first, second, year, rng, gone=True)
            continue
        if not first.ruler_id or first.ruler_id != second.ruler_id:
            _close(ctx, union, first, second, year, rng)
            continue

        # Корона перешла к новому государю, и он снова носит обе: уния
        # пережила смерть — это и есть второе поколение.
        if union.monarch_id != first.ruler_id:
            union.monarch_id = first.ruler_id
            union.monarchs.append(first.ruler_id)
        dip.set_relation(first, second,
                         max(UNION_RELATION, dip.relation(first, second.id)))

        if year - union.started.year < MERGE_AFTER or len(union.monarchs) < 2:
            continue
        if rng.chance(MERGE_RATE * (period / 10.0)):
            _merge(ctx, union, first, second, year, rng)


def _close(ctx, union, first, second, year: int, rng, gone: bool = False,
           reason: str = "", absorbed: bool = False) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year, union.started
                       if union.started.year == year else None)
    world.end_union(union, date, reason or
                    ("одной из держав не стало" if gone else "короны разошлись"))
    if absorbed:
        title, text = texts.union_absorbed(rng, union, first, second)
    else:
        title, text = texts.union_split(rng, union, first, second, gone=gone)
    subjects = [union.id] + [p.id for p in (first, second) if p is not None]
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="union_end",
        title=title, text=text, importance=3, subjects=subjects,
        race_id=(first or second).race_id if (first or second) else "")


def _merge(ctx, union, first, second, year: int, rng) -> None:
    """Младшая держава растворяется в старшей — без единого выстрела."""
    from . import succession as succession_mod

    world = ctx.world
    date = ctx.date_in(rng, year)
    monarch = world.figures.get(first.ruler_id)

    for settlement_id in list(second.settlement_ids):
        settlement = world.settlements.get(settlement_id)
        if settlement is None:
            continue
        second.settlement_ids.remove(settlement_id)
        if settlement.status not in (ACTIVE,):
            continue
        settlement.polity_id = first.id
        settlement.is_capital = False
        if settlement_id not in first.settlement_ids:
            first.settlement_ids.append(settlement_id)
        if settlement.region_id not in first.region_ids:
            first.region_ids.append(settlement.region_id)
    for house_id in list(second.house_ids):
        house = world.houses.get(house_id)
        if house is not None and house.id != second.house_id:
            houses_mod.attach(world, house, first)

    # Правление младшей короны закрывают по чести: держава не погибла,
    # а слилась, и государь у неё остался тот же.
    reign = world.current_reign(second)
    if reign is not None and reign.end is None:
        succession_mod.close_reign(ctx, reign, date, "короны слились")
    # Дом остаётся правящим в старшей державе — отвязываем его, чтобы
    # конец младшей не разжаловал его из правящих.
    second.house_id = ""
    world.end_union(union, date, "державы слились", merged=True)
    world.end_polity(second, date,
                     "слилась с державой %s" % first.name, status=ENDED)
    world.refresh_populations()
    nations_mod.ensure_titular(ctx, first, year)

    title, text = texts.union_merged(rng, union, first, second)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="union_merge",
        title=title, text=text, importance=4,
        actors=[monarch.id] if monarch is not None else [],
        subjects=[union.id, first.id, second.id],
        region_id=first.region_ids[0] if first.region_ids else "",
        race_id=first.race_id)


__all__ = ["claim", "form", "upkeep"]
