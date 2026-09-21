# -*- coding: utf-8 -*-
"""Заговоры: обида, которая растёт годами и однажды бьёт.

Тайное дело в этом мире не случается по броску кости. У него есть
ступени, и на каждой оно может кончиться ничем:

    обида → сговор → клятва → ожидание → удар → награда или плаха

Заговор начинается там, где есть кому обижаться: обойдённый престолом
родич, дом, у которого корона отняла вольности, проповедник старого
обряда, городской старшина, которому подняли сбор. Он растёт
участниками — и с каждым новым человеком тайна становится тоньше.
Удар наносят не когда захотят, а когда государь слаб: смута, война,
голод, долгое правление старика.

Раскрывают заговоры соглядатаи и свои же: выдавший получает больше,
чем терял. Раскрытое дело кончается плахой, а память об этом остаётся
у всех, кого казнили не до конца.
"""

from __future__ import annotations

from . import memory as memory_sys
from . import strife as strife_sys
from . import succession
from .. import dynasty
from .. import history
from .. import narrative
from .. import narrative_cabal as texts
from .. import races as races_mod
from .. import recall
from .. import rulers as rulers_mod
from ..models import ACTIVE

# Ступени.
GRUDGE = "обида"
PLOT = "сговор"
OATH = "клятва"
WAIT = "ожидание"
STRIKE = "удар"
STAGES = (GRUDGE, PLOT, OATH, WAIT, STRIKE)

# Чего хотят.
AIMS = ("престол", "месть", "вера", "воля городов")

BIRTH_RATE = 0.045         # как часто при дворе заводится новое дело
STEP_RATE = 0.45           # как охотно оно переходит на следующую ступень
EXPOSE_RATE = 0.10         # как часто его раскрывают за десятилетие
FADE_YEARS = 220           # дольше этого не ждут даже эльфы
MIN_REIGN = 5              # только что севшего государя не трогают
SECRECY_STEP = 0.08        # сколько тайны уносит каждый новый человек


# ---------------------------------------------------------------------------
# Медленный такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("cabals", year)
    for cabal_id in list(world.live_cabals):
        cabal = world.cabals.get(cabal_id)
        if cabal is not None:
            _advance(ctx, cabal, year, period, rng)
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        if world.cabal_of(polity) is not None:
            continue
        _maybe_born(ctx, polity, year, period, rng)


# ---------------------------------------------------------------------------
# Как заводится
# ---------------------------------------------------------------------------

def _grudge_holders(world, polity, year: int) -> list:
    """Те, кому есть на что обижаться при этом дворе."""
    out = []
    house = world.houses.get(polity.house_id)
    seen = set()
    for item in ([house] if house is not None else []) \
            + world.houses_of_polity(polity):
        if item is None or item.id in seen or item.status != ACTIVE:
            continue
        seen.add(item.id)
        for figure_id in item.living[-10:]:
            figure = world.figures.get(figure_id)
            if figure is None or not figure.alive_at(year):
                continue
            if figure.id == polity.ruler_id:
                continue
            race = races_mod.RACES_BY_ID.get(figure.race_id)
            if race is None or not dynasty.is_adult(figure, race, year):
                continue        # дети в заговоры не вступают
            weight = 0.0
            if world.memories_of(figure.id, recall.PASSED_OVER):
                weight += 1.2
            if world.memories_of(figure.id, recall.KIN_DEATH):
                weight += 0.5
            weight += 0.8 * item.discontent
            if item.charters == 0 and item.rank != "правящий":
                weight += 0.1
            if weight > 0.4:
                out.append((figure, item, weight))
    return out


def _maybe_born(ctx, polity, year: int, period: int, rng) -> None:
    world = ctx.world
    ruler = world.figures.get(polity.ruler_id)
    if ruler is None:
        return
    reign = world.current_reign(polity)
    if reign is not None and year - reign.start.year < MIN_REIGN:
        return

    holders = _grudge_holders(world, polity, year)
    if not holders:
        return
    figure, house, weight = rng.weighted([(item, item[2]) for item in holders])
    chance = ctx.rate(BIRTH_RATE) * weight * (period / 10.0)
    chance *= 1.0 + 1.5 * polity.intrigue
    chance /= max(0.4, rulers_mod.court_grip(world, polity))
    if not rng.chance(min(0.5, chance)):
        return

    aim = _aim_for(world, polity, figure, house, rng)
    cabal = world.add_cabal(
        polity_id=polity.id, target_id=ruler.id, leader_id=figure.id,
        born=year, stage=GRUDGE, stage_year=year, aim=aim,
        members=[figure.id],
        houses=[house.id] if house is not None else [],
        patron_id="", secrecy=1.0)
    # Заговор не бывает делом одного: рядом с обиженным сразу стоит тот,
    # кто его слушает.
    _recruit(ctx, cabal, polity, year, rng)
    date = ctx.date_in(rng, year)
    title, text = texts.cabal_born(rng, figure, aim)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="cabal_born",
        title=title, text=text, importance=1, actors=[figure.id],
        subjects=[cabal.id, polity.id], race_id=polity.race_id,
        trace=history.trace_of(1))


def _aim_for(world, polity, figure, house, rng) -> str:
    pairs = [("месть", 1.0)]
    if house is not None and house.id == polity.house_id:
        pairs.append(("престол", 2.5))
    elif house is not None:
        pairs.append(("престол", 1.2))
    faiths = {}
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is not None and settlement.faith_id:
            faiths[settlement.faith_id] = faiths.get(settlement.faith_id, 0) + 1
    if len(faiths) > 1:
        pairs.append(("вера", 1.0))
    if world.guilds_of(polity):
        pairs.append(("воля городов", 0.8))
    return rng.weighted(pairs)


# ---------------------------------------------------------------------------
# Как растёт
# ---------------------------------------------------------------------------

def _advance(ctx, cabal, year: int, period: int, rng) -> None:
    world = ctx.world
    polity = world.polities.get(cabal.polity_id)
    leader = world.figures.get(cabal.leader_id)
    ruler = world.figures.get(cabal.target_id)

    if polity is None or polity.status != ACTIVE:
        world.end_cabal(cabal, year, "державы не стало")
        return
    if leader is None or not leader.alive_at(year):
        # Смерть вожака — не конец дела: у клятвы есть и другие руки.
        leader = _pass_the_oath(ctx, cabal, year)
        if leader is None:
            _fade(ctx, cabal, polity, year, rng, "вожака не стало")
            return
    if ruler is None or not ruler.alive_at(year) or polity.ruler_id != ruler.id:
        # Государь умер сам. Обида на престол от этого не проходит: дело
        # чаще всего переписывают на нового, а месть — нет, мстить уже
        # некому.
        heir = world.figures.get(polity.ruler_id)
        if heir is not None and heir.id == cabal.leader_id:
            # Престол достался самому заговорщику — и без всякого удара.
            world.end_cabal(cabal, year, "сбылось само")
            return
        if cabal.aim != "месть" and heir is not None \
                and heir.id != cabal.leader_id and rng.chance(0.55):
            cabal.target_id = heir.id
            cabal.notes.append("%d: дело переписано на нового государя" % year)
        else:
            _fade(ctx, cabal, polity, year, rng, "опередили")
            return
    if year - cabal.born > FADE_YEARS:
        _fade(ctx, cabal, polity, year, rng, "выдохся")
        return

    if _exposed(ctx, cabal, polity, year, period, rng):
        return

    scale = period / 10.0
    if cabal.stage == GRUDGE:
        # Обида становится сговором быстро: для этого хватает разговора.
        if rng.chance(min(0.9, 1.4 * STEP_RATE * scale)):
            _recruit(ctx, cabal, polity, year, rng)
            cabal.stage, cabal.stage_year = PLOT, year
    elif cabal.stage == PLOT:
        _recruit(ctx, cabal, polity, year, rng)
        if len(cabal.members) >= 3 and rng.chance(STEP_RATE * scale):
            cabal.stage, cabal.stage_year = OATH, year
            date = ctx.date_in(rng, year)
            title, text = texts.cabal_oath(rng, cabal, len(cabal.members))
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="cabal_oath", title=title, text=text, importance=2,
                actors=cabal.members[:3], subjects=[cabal.id, polity.id],
                race_id=polity.race_id)
    elif cabal.stage == OATH:
        if rng.chance(STEP_RATE * scale):
            cabal.stage, cabal.stage_year = WAIT, year
    elif cabal.stage == WAIT:
        if rng.chance(min(0.8, _moment(ctx, polity, year) * scale)):
            _strike(ctx, cabal, polity, year, rng)


def _pass_the_oath(ctx, cabal, year: int):
    """Дело переходит к тому, кто ещё жив и ещё помнит, ради чего всё."""
    world = ctx.world
    for figure_id in cabal.members:
        if figure_id == cabal.leader_id:
            continue
        figure = world.figures.get(figure_id)
        if figure is None or not figure.alive_at(year):
            continue
        cabal.leader_id = figure.id
        cabal.notes.append("%d: дело перешло к другому" % year)
        return figure
    return None


def _recruit(ctx, cabal, polity, year: int, rng) -> None:
    """Каждый новый человек — сила, и он же дыра в тайне."""
    world = ctx.world
    holders = _grudge_holders(world, polity, year)
    rng_pool = [item for item in holders if item[0].id not in cabal.members]
    if not rng_pool:
        return
    figure, house, _ = rng.weighted([(item, item[2]) for item in rng_pool])
    cabal.members.append(figure.id)
    if house is not None and house.id not in cabal.houses:
        cabal.houses.append(house.id)
    cabal.secrecy = max(0.15, cabal.secrecy - SECRECY_STEP)
    leader = world.figures.get(cabal.leader_id)
    memory_sys.bind(ctx, figure, leader, recall.B_FRIEND, year, value=0.4,
                    note="общее тайное дело")


def _moment(ctx, polity, year: int) -> float:
    """Насколько сейчас удобно бить."""
    world = ctx.world
    value = 0.12
    if world.strife_of(polity) is not None:
        value += 0.35
    if world.wars_of(polity, only_active=True):
        value += 0.2
    if polity.hunger > 0.3:
        value += 0.15
    reign = world.current_reign(polity)
    ruler = world.figures.get(polity.ruler_id)
    race = races_mod.get_race(polity.race_id)
    if ruler is not None and ruler.age_at(year) > race.lifespan[0] * 0.8:
        value += 0.2
    if reign is not None and reign.regent_id:
        value += 0.25
    value /= max(0.4, rulers_mod.court_grip(world, polity))
    return value


# ---------------------------------------------------------------------------
# Развязки
# ---------------------------------------------------------------------------

def _exposed(ctx, cabal, polity, year: int, period: int, rng) -> bool:
    """Раскрытие: соглядатаи, донос или чья-то несдержанность."""
    world = ctx.world
    if cabal.stage == GRUDGE:
        return False
    # Пока о деле знают двое, его не раскрыть; каждый новый человек —
    # это ещё одна щель, через которую оно выходит наружу.
    risk = EXPOSE_RATE * (0.35 + 1.8 * (1.0 - cabal.secrecy)) * (period / 10.0)
    risk *= max(0.5, rulers_mod.court_grip(world, polity))
    if not rng.chance(min(0.6, risk)):
        return False

    date = ctx.date_in(rng, year)
    span = year - cabal.born
    title, text = texts.cabal_exposed(rng, cabal, span)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="cabal_exposed",
        title=title, text=text, importance=3, actors=cabal.members[:3],
        subjects=[cabal.id, polity.id], race_id=polity.race_id,
        trace=history.trace_of(3))
    # Казнят не всех, но помнят всех.
    for figure_id in cabal.members:
        figure = world.figures.get(figure_id)
        if figure is None or not figure.alive_at(year):
            continue
        if figure_id == cabal.leader_id or rng.chance(0.45):
            figure.death_cause = "казнён по делу о заговоре"
            world.schedule_death(figure, date, narrative.fate(
                ("казнён по делу о заговоре", "казнена по делу о заговоре"),
                figure.sex))
            memory_sys.fallen(ctx, figure, polity.id, year, event_id=event.id,
                              note="казнён по делу о заговоре")
    for house_id in cabal.houses:
        house = world.houses.get(house_id)
        if house is None:
            continue
        house.prestige = max(0.15, house.prestige * 0.5)
        house.discontent = min(1.0, house.discontent + 0.25)
    history.leave(world, history.DREAD, year, polity.id, weight=0.5,
                  note="раскрытый заговор", event_id=event.id)
    world.end_cabal(cabal, year, "раскрыт")
    cabal.strike_id = event.id
    return True


def _fade(ctx, cabal, polity, year: int, rng, reason: str) -> None:
    """Дело, которое так ничем и не кончилось."""
    world = ctx.world
    world.end_cabal(cabal, year, reason)
    if cabal.stage in (GRUDGE, PLOT) or not rng.chance(0.4):
        return
    date = ctx.date_in(rng, year)
    title, text = texts.cabal_faded(rng, cabal, year - cabal.born)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="cabal_faded",
        title=title, text=text, importance=1,
        subjects=[cabal.id, polity.id], race_id=polity.race_id,
        trace=history.trace_of(1))


def _strike(ctx, cabal, polity, year: int, rng) -> None:
    """Удар: та самая ночь, которой ждали."""
    world = ctx.world
    leader = world.figures.get(cabal.leader_id)
    ruler = world.figures.get(cabal.target_id)
    if leader is None or ruler is None:
        return
    reign = world.current_reign(polity)
    # Удар не может лечь в летопись раньше, чем началось правление, по
    # которому бьют.
    date = ctx.date_in(rng, year,
                       reign.start if reign is not None
                       and reign.start.year == year else None)
    span = year - cabal.born

    edge = 0.35 + 0.08 * len(cabal.members) + 0.25 * cabal.secrecy
    edge /= max(0.5, rulers_mod.court_grip(world, polity))
    done = rng.chance(max(0.15, min(0.85, edge)))

    title, text = texts.cabal_strike(rng, cabal, leader, ruler, span, done)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="cabal_strike",
        title=title, text=text, importance=4 if done else 3,
        actors=[leader.id, ruler.id], subjects=[cabal.id, polity.id],
        race_id=polity.race_id, trace=history.trace_of(4))
    cabal.strike_id = event.id

    if not done:
        leader.death_cause = "казнён после неудавшегося удара"
        world.schedule_death(leader, date, narrative.fate(
            ("казнён после неудавшегося удара",
             "казнена после неудавшегося удара"), leader.sex))
        memory_sys.fallen(ctx, leader, polity.id, year, event_id=event.id,
                          note="казнён после неудавшегося удара")
        world.end_cabal(cabal, year, "сорвалось")
        return

    # Государя не стало. Дальше — либо престол заговорщику, либо смута.
    world.schedule_death(ruler, date, narrative.fate(
        ("убит заговорщиками", "убита заговорщиками"), ruler.sex))
    memory_sys.fallen(ctx, ruler, polity.id, year, event_id=event.id,
                      note="убит заговорщиками")
    history.leave(world, history.GRUDGE, year, polity.id, weight=0.8,
                  note="кровь государя", event_id=event.id)
    world.end_cabal(cabal, year, "удалось")

    race = races_mod.get_race(polity.race_id)
    claims = cabal.aim == "престол" and leader.house_id \
        and dynasty.is_adult(leader, race, year)
    if claims and rng.chance(0.55):
        succession.close_reign(ctx, reign, date, "заговор")
        old_house = world.houses.get(polity.house_id)
        polity.ruler_id = ""
        choice = dynasty.HeirChoice(leader, "вождь заговора",
                                    other_house=True, law=polity.succession)
        succession.enthrone(ctx, polity, leader, date, year, choice,
                            legitimacy="узурпация", old_house=old_house,
                            rng=rng, announce=False)
    else:
        # Убить государя проще, чем сесть на его место: держава срывается
        # в смуту, и венец достаётся тому, кто её выиграет.
        strife_sys.start(ctx, polity, strife_sys.COUP, year, rng,
                         rebel=leader,
                         house=world.houses.get(leader.house_id),
                         origin_id=event.id)
