# -*- coding: utf-8 -*-
"""Тайная политика: кто, против кого и чьими руками.

Раз в такт двор, у которого есть враг или соперник, посылает за межу
человека без грамот. Что он там делает, решает ``espionage``: подкупает
воеводу накануне битвы, вьёт заговор среди недовольной знати, подбивает
на смуту притесняемый народ, выправляет подложную родословную или несёт
яд к столу государя.

Тайное дело либо срабатывает, либо срывается втуне, либо раскрывается —
и тогда о нём узнаёт весь свет, соглядатая казнят, а обиду записывают в
грамоты, откуда её потом достают при объявлении войны.
"""

from __future__ import annotations

from . import diplomacy as dip_system
from .. import diplomacy as dip
from .. import espionage as spy
from .. import narrative
from .. import narrative_spies as texts
from .. import races as races_mod
from .. import rulers
from ..models import ACTIVE

PLOT_RATE = 0.10            # шанс, что двор за такт возьмётся за тайное дело
WAR_BONUS = 2.6             # на войне за них берутся куда охотнее
COLD_RELATION = 0.25        # против тех, к кому нет приязни


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("spies", year)
    owners = {}
    for polity_id in world.active_polities:
        for region_id in world.polities[polity_id].region_ids:
            owners.setdefault(region_id, []).append(polity_id)

    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        # Смута, оплаченная соседом, со временем оседает сама.
        if polity.intrigue:
            polity.intrigue = round(polity.intrigue * spy.INTRIGUE_DECAY, 4)
            if polity.intrigue < 0.02:
                polity.intrigue = 0.0

    for polity in rng.shuffled([world.polities[pid]
                                for pid in world.active_polities]):
        if polity.status != ACTIVE or not polity.ruler_id:
            continue
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states or race.is_evil:
            continue
        # На войне тайные дела ведут против того, с кем воюют: купить
        # чужого воеводу дешевле, чем разбить его войско.
        target = _enemy(world, polity, rng)
        if target is None or rng.chance(0.25):
            target = _target(ctx, polity, year, rng, owners) or target
        if target is None:
            continue
        rate = PLOT_RATE * (period / 10.0)
        if world.war_between(polity.id, target.id) is not None:
            rate *= WAR_BONUS
        # Государь, умеющий держать двор, и тайные дела ведёт охотнее.
        rate *= max(0.4, 2.0 - rulers.court_grip(world, polity))
        if not rng.chance(min(0.7, rate)):
            continue
        _plot(ctx, polity, target, year, rng)


def _enemy(world, polity, rng):
    """Тот, с кем эта держава воюет прямо сейчас."""
    options = []
    for fight in world.wars_of(polity, only_active=True):
        if polity.id in fight.attacker_allies or fight.defender_id == polity.id:
            foe_id = fight.attacker_id
        else:
            foe_id = fight.defender_id
        foe = world.polities.get(foe_id)
        if foe is None or foe.status != ACTIVE or foe.id == polity.id:
            continue
        if not foe.ruler_id:
            continue
        options.append(foe)
    if not options:
        return None
    return rng.choice(sorted(options, key=lambda p: p.id))


def _target(ctx, sender, year: int, rng, owners):
    """Против кого затевают: против врага, соперника или недруга по вере."""
    world = ctx.world
    options = []
    for other in dip_system.circle(ctx, world, sender, year, owners):
        if other.status != ACTIVE or not other.ruler_id:
            continue
        relation = dip.relation(sender, other.id)
        at_war = world.war_between(sender.id, other.id) is not None
        if not at_war and relation > COLD_RELATION:
            continue           # за спиной друга не шпионят — по крайней мере пока
        weight = 1.0 + 2.0 * max(0.0, -relation)
        if at_war:
            weight += 3.0
        options.append((other, weight))
    if not options:
        return None
    return rng.weighted(options)


# ---------------------------------------------------------------------------
# Дело
# ---------------------------------------------------------------------------

def _plot(ctx, sender, target, year: int, rng) -> None:
    world = ctx.world
    fight = world.war_between(sender.id, target.id)
    deed = spy.choose(rng, world, sender, target, fight is not None)
    if deed is None:
        return
    agent = _agent(ctx, sender, year, rng)
    date = ctx.date_in(rng, year)

    # Превосходство: чей государь лучше держит двор — у того и тайная
    # служба крепче. К соседу, с которым ещё вчера торговали, подобраться
    # проще, чем к тому, кто триста лет ждёт удара.
    edge = (rulers.court_grip(world, target)
            - rulers.court_grip(world, sender)) * 0.8
    edge += 0.35 * dip.relation(sender, target.id)
    outcome = spy.verdict(rng, deed, max(-1.0, min(1.0, edge)),
                          world.era_index_at(year))

    record = world.add_plot(
        kind=deed.key, sender_id=sender.id, target_id=target.id,
        agent_id=agent.id, date=date, outcome=outcome,
        war_id=fight.id if fight is not None else "")

    note = ""
    if outcome == spy.DONE:
        note = _succeed(ctx, record, deed, sender, target, year, date, rng,
                        fight)
    elif outcome == spy.CAUGHT:
        _expose(ctx, record, sender, target, agent, year, date, rng)

    title, text = texts.plot_text(rng, deed, sender, target, agent, outcome)
    if note:
        text = "%s %s" % (text, note)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="plot",
        title=title, text=text,
        importance=3 if outcome != spy.FAILED else 1,
        actors=[agent.id], subjects=[record.id, sender.id, target.id],
        region_id=target.region_ids[0] if target.region_ids else "",
        race_id=sender.race_id)


def _agent(ctx, sender, year: int, rng):
    """Соглядатая берут из тех, кого не жалко и кого никто не хватится."""
    world = ctx.world
    race = races_mod.get_race(sender.race_id)
    sex = "f" if rng.chance(0.42) else "m"
    settlement = world.settlements.get(sender.capital_id)
    return ctx.make_figure(
        rng, race, year, role="соглядатай",
        region_id=settlement.region_id if settlement is not None else
        (sender.region_ids[0] if sender.region_ids else ""),
        title="", sex=sex, home_id=sender.id, epithet_chance=0.55,
        folk=world.folks.get(settlement.folk_id) if settlement is not None
        else None)


def _succeed(ctx, record, deed, sender, target, year: int, date, rng,
             fight) -> str:
    """Что меняет в мире удавшееся тайное дело."""
    world = ctx.world
    key = deed.key

    if key == "подкуп" and fight is not None:
        # Подкупленный воевода отработает серебро в ближайшем сражении.
        _remember(ctx, fight, target, spy.BRIBE_EDGE)
        record.war_id = fight.id
    elif key == "выведывание" and fight is not None:
        _remember(ctx, fight, target, spy.SCOUT_EDGE)
        record.war_id = fight.id
    elif key == "заговор":
        target.intrigue = min(1.0, target.intrigue + spy.INTRIGUE_STEP)
    elif key == "смута":
        minorities = target.minorities()
        if minorities:
            race_id = minorities[0][0]
            target.grievance[race_id] = min(
                1.0, target.grievance.get(race_id, 0.0) + spy.GRIEVANCE_STEP)
    elif key == "подлог":
        # Бумага не корона, но повод к войне из неё выходит отменный.
        world.add_grudge(sender, target.id, "claim", year)
    elif key == "яд":
        ruler = world.figures.get(target.ruler_id)
        if ruler is not None and ruler.alive_at(year):
            record.victim_id = ruler.id
            world.schedule_death(ruler, date, narrative.fate(
                ("отравлен", "отравлена"), ruler.sex))
            world.add_grudge(target, sender.id, "poison", year)
    return texts.aftermath(rng, key)


def _expose(ctx, record, sender, target, agent, year: int, date, rng) -> None:
    """Раскрытое дело: соглядатая казнят, а обиду записывают."""
    world = ctx.world
    world.schedule_death(agent, date, narrative.fate(
        ("казнён как соглядатай", "казнена как соглядатай"), agent.sex))
    world.add_grudge(target, sender.id, "spy", year)
    dip.set_relation(sender, target,
                     dip.relation(sender, target.id) - 0.30)


# ---------------------------------------------------------------------------
# Подкупленный воевода
# ---------------------------------------------------------------------------

def _remember(ctx, war, victim, weight: float) -> None:
    key = (war.id, victim.id)
    ctx.secrets[key] = max(ctx.secrets.get(key, 0.0), weight)


def leverage(ctx, war, polity) -> float:
    """Насколько чужое серебро ослабило это войско в ближайшей битве."""
    return ctx.secrets.get((war.id, polity.id), 0.0)


def spend(ctx, war, polity) -> None:
    """Серебро отрабатывается один раз — в одном сражении."""
    ctx.secrets.pop((war.id, polity.id), None)


__all__ = ["upkeep", "leverage", "spend"]
