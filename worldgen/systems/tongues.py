# -*- coding: utf-8 -*-
"""Языки народов: рождение, расхождение, письменность и смерть.

Праязык рождается вместе с расой. Каждый народ, отделившийся от неё,
сперва говорит на том же языке, но, прожив врозь несколько веков,
обзаводится собственным наречием — и наречие это слышно в именах его
городов и людей.

Дальше язык живёт своей жизнью: перенимает слова у тех, с кем торгует,
обзаводится письменностью (своей или чужой), а с гибелью народа
умолкает — если только жрецы не оставят его для обряда.
"""

from __future__ import annotations

from .. import narrative
from .. import narrative_tongues as texts
from .. import races as races_mod
from .. import tongues as tng
from ..models import ACTIVE

FOLK_GRACE = 60             # столько лет народу дают, чтобы расселиться
SCRIPT_RATE = 0.05          # шанс изобрести письмо за такт
SCRIPT_MIN_SOULS = 4000     # раньше этого письмо некому и незачем
BORROW_RATE = 0.06
SACRED_SHARE = 0.35         # доля мёртвых языков, уходящих в храм


# ---------------------------------------------------------------------------
# Рождение
# ---------------------------------------------------------------------------

def proto_for(ctx, race, folk, year: int, date, rng):
    """Праязык расы — общий для всех её народов при пробуждении."""
    world = ctx.world
    for tongue_id in world.living_tongues:
        tongue = world.tongues[tongue_id]
        if tongue.race_id == race.id and not tongue.parent_id:
            return tongue
    cradle = world.regions.get(folk.cradle_region) if folk is not None else None
    # Две расы, проснувшиеся в одной земле, не могут звать свой праязык
    # одинаково: имя берётся через кузницу, а она повторов не отдаёт.
    name = ctx.forge.unique(
        "tongue",
        lambda: tng.proto_name(rng, race, cradle.name if cradle else ""), rng)
    tongue = world.add_tongue(
        name=name, race_id=race.id, born=date,
        laws=tng.pick_laws(rng, count=rng.randint(1, 2)))
    title, text = texts.proto_born(rng, tongue, race)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="tongue_born",
        title=title, text=text, importance=2, subjects=[tongue.id],
        region_id=folk.cradle_region if folk is not None else "",
        race_id=race.id)
    return tongue


def attach(world, tongue, folk) -> None:
    if tongue is None or folk is None:
        return
    folk.tongue_id = tongue.id
    if folk.id not in tongue.folk_ids:
        tongue.folk_ids.append(folk.id)


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("tongues", year)
    # Народы считаются по городам и племенам; без этого пересчёта все
    # народы числятся пустыми, а языки — мёртвыми с первого же такта.
    world.refresh_folks()
    _fade_folks(ctx, year, rng)
    _count_speakers(world)
    _maybe_split(ctx, year, period, rng)
    _maybe_script(ctx, year, period, rng)
    _maybe_borrow(ctx, year, period, rng)
    _maybe_die(ctx, year, period, rng)
    _state_tongues(world)


# Народ, за которым не осталось ни одного живого, кончился. Назад такие
# не возвращаются: новые народы рождаются только при пробуждении расы,
# а раса просыпается один раз. Раньше такой народ оставался «активным»
# навсегда — с мёртвым языком и нулём душ.
def _fade_folks(ctx, year: int, rng) -> None:
    world = ctx.world
    for folk in world.folks.values():
        if folk.status != ACTIVE or folk.population > 0:
            continue
        if year - folk.born.year < FOLK_GRACE:
            continue          # только что проснулись, людей ещё не расселили
        date = ctx.date_in(rng, year)
        world.end_folk(folk, date, "не осталось ни одной живой души")
        race = races_mod.RACES_BY_ID.get(folk.race_id)
        title, text = narrative.folk_end(rng, folk, race,
                                         year - folk.born.year)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="folk_end",
            title=title, text=text, importance=2, subjects=[folk.id],
            region_id=folk.cradle_region, race_id=folk.race_id)


def _count_speakers(world) -> None:
    speakers = {}
    for folk in world.folks.values():
        if folk.status != ACTIVE or not folk.tongue_id:
            continue
        speakers[folk.tongue_id] = speakers.get(folk.tongue_id, 0) \
            + max(0, folk.population)
    for tongue_id, tongue in world.tongues.items():
        tongue.speakers = speakers.get(tongue_id, 0)


def _state_tongues(world) -> None:
    """Язык двора — язык титульного народа державы."""
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        best, best_souls = "", 0
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is None or settlement.status != ACTIVE:
                continue
            folk = world.folks.get(settlement.folk_id)
            if folk is None or not folk.tongue_id:
                continue
            if settlement.race_id != polity.race_id:
                continue
            if settlement.population > best_souls:
                best, best_souls = folk.tongue_id, settlement.population
        if best:
            polity.tongue_id = best


def _maybe_split(ctx, year: int, period: int, rng) -> None:
    """Народ, проживший врозь несколько веков, обзаводится своим наречием."""
    world = ctx.world
    for folk in list(world.folks.values()):
        if folk.status != ACTIVE or folk.population < 400:
            continue
        parent = world.tongues.get(folk.tongue_id)
        if parent is None:
            continue
        # Пока народ один на язык, расходиться не с кем.
        kin = [item for item in parent.folk_ids
               if item != folk.id and item in world.folks
               and world.folks[item].status == ACTIVE]
        if not kin:
            continue
        apart = year - max(folk.born.year, parent.born.year)
        if apart < tng.SPLIT_YEARS:
            continue
        if not rng.chance(tng.SPLIT_CHANCE * (period / 10.0)):
            continue

        date = ctx.date_in(rng, year)
        tongue = world.add_tongue(
            name=tng.folk_tongue_name(rng, folk), race_id=folk.race_id,
            born=date, parent_id=parent.id,
            laws=tng.pick_laws(rng, parent.laws),
            script=parent.script,
            script_year=parent.script_year if parent.script else 0,
            script_from=parent.id if parent.script else "")
        if folk.id in parent.folk_ids:
            parent.folk_ids.remove(folk.id)
        attach(world, tongue, folk)

        title, text = texts.tongue_split(rng, tongue, parent, folk)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="tongue_split",
            title=title, text=text, importance=2,
            subjects=[tongue.id, folk.id], region_id=folk.cradle_region,
            race_id=folk.race_id)


def _maybe_script(ctx, year: int, period: int, rng) -> None:
    """Письменность изобретают один раз, а потом одалживают у соседей."""
    world = ctx.world
    era_index = world.era_index_at(year)
    for tongue_id in list(world.living_tongues):
        tongue = world.tongues[tongue_id]
        if tongue.script or tongue.speakers < SCRIPT_MIN_SOULS:
            continue
        folk = _first_folk(world, tongue)
        if folk is None:
            continue
        chance = SCRIPT_RATE * (period / 10.0) * (0.5 + 0.25 * era_index)
        borrowed = _script_neighbour(world, tongue, year)
        if borrowed is not None:
            chance *= 1.7          # одолжить проще, чем выдумать
        if not rng.chance(min(0.6, chance)):
            continue

        # Даже при готовом чужом письме народ нередко заводит своё:
        # иначе весь мир пишет рунами и больше ничем.
        if borrowed is not None and rng.chance(0.30):
            borrowed = None
        if borrowed is not None:
            tongue.script = borrowed.script
            tongue.script_from = borrowed.id
        else:
            taken = {item.script for item in world.tongues.values()
                     if item.script}
            options = [item for item in tng.SCRIPTS if item not in taken] \
                or list(tng.SCRIPTS)
            tongue.script = rng.choice(options)
        tongue.script_year = year

        date = ctx.date_in(rng, year)
        title, text = texts.script_found(rng, tongue, folk, borrowed)
        world.add_event(
            date=date, era_index=era_index, kind="script_found", title=title,
            text=text, importance=3 if borrowed is None else 2,
            subjects=[tongue.id, folk.id], region_id=folk.cradle_region,
            race_id=tongue.race_id)


def _first_folk(world, tongue):
    for folk_id in tongue.folk_ids:
        folk = world.folks.get(folk_id)
        if folk is not None and folk.status == ACTIVE:
            return folk
    return None


def _script_neighbour(world, tongue, year: int):
    """Соседний язык с укоренившимся письмом, у которого можно одолжить буквы.

    Одалживают не у всякого: письмо должно уже отстояться, а сосед —
    быть настоящим соседом или роднёй по языку.
    """
    folk = _first_folk(world, tongue)
    if folk is None:
        return None
    region = world.regions.get(folk.cradle_region)
    reach = set(region.neighbors) | {region.id} if region is not None else set()
    for other_id in world.living_tongues:
        other = world.tongues[other_id]
        if other.id == tongue.id or not other.script:
            continue
        if other.script_year and year - other.script_year < 200:
            continue
        if other.parent_id and other.parent_id == tongue.parent_id:
            return other          # родня по праязыку пишет одинаково
        neighbour = _first_folk(world, other)
        if neighbour is not None and neighbour.cradle_region in reach:
            return other
    return None


def _maybe_borrow(ctx, year: int, period: int, rng) -> None:
    """Торговля приносит чужие слова вернее любого указа."""
    world = ctx.world
    for route_id in list(world.active_routes):
        route = world.routes[route_id]
        seller = world.polities.get(route.seller_id)
        buyer = world.polities.get(route.buyer_id)
        if seller is None or buyer is None:
            continue
        ours = world.tongues.get(seller.tongue_id)
        theirs = world.tongues.get(buyer.tongue_id)
        if ours is None or theirs is None or ours.id == theirs.id:
            continue
        if theirs.id in ours.borrowed:
            continue
        if not rng.chance(BORROW_RATE * (period / 10.0)):
            continue
        ours.borrowed.append(theirs.id)
        date = ctx.date_in(rng, year)
        title, text = texts.borrowing(rng, ours, theirs)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="tongue_borrow",
            title=title, text=text, importance=1,
            subjects=[ours.id, theirs.id], race_id=ours.race_id)


def _maybe_die(ctx, year: int, period: int, rng) -> None:
    """Язык умирает вместе с народом — или уходит в храм."""
    world = ctx.world
    for tongue_id in list(world.living_tongues):
        tongue = world.tongues[tongue_id]
        alive = [world.folks[fid] for fid in tongue.folk_ids
                 if fid in world.folks and world.folks[fid].status == ACTIVE
                 and world.folks[fid].population > 0]
        if alive:
            continue
        if year - tongue.born.year < 50:
            continue
        date = ctx.date_in(rng, year)
        sacred = tongue.script and rng.chance(SACRED_SHARE)
        world.end_tongue(tongue, date,
                         "говорить стало некому",
                         tng.SACRED if sacred else tng.DEAD)
        if sacred:
            tongue.name = tng.sacred_name(rng, tongue)
        title, text = texts.tongue_dead(rng, tongue, bool(sacred),
                                        year - tongue.born.year)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="tongue_dead",
            title=title, text=text, importance=2 if sacred else 1,
            subjects=[tongue.id], race_id=tongue.race_id)
