# -*- coding: utf-8 -*-
"""Гильдии: деньги как третья сила в политике.

Гильдия заводится там, где торг богаче податей: в портовом городе, на
соляном пути, у рудничных ворот. Дальше она живёт своим счётом — растёт
с каждого действующего торгового пути и худеет от всякой войны.

Деньги эти не лежат мёртвым грузом. Гильдия покупает вольности при чужих
дворах, нанимает роту, когда война подходит к её обозам, выкупает мир,
когда война обходится дороже мира, и требует войны, когда чужие пошлины
разоряют торг. Престол отвечает тем же: накладывает руку на кассу.

А если город богатеет быстрее, чем крепнет корона, он однажды объявляет
себя вольным — и в мире появляется торговая республика, где правит не
государь, а выборный глава купеческого совета.
"""

from __future__ import annotations

from . import soldiery
from . import succession as succession_mod
from . import war as war_system
from .. import diplomacy as dip
from .. import guilds as guilds_mod
from .. import narrative_guilds as texts
from .. import races as races_mod
from .. import rulers
from ..models import ACTIVE

FOUND_RATE = 0.10           # шанс, что богатый город заведёт гильдию за такт
MIN_CITY = 2200             # и с какого размера города об этом вообще речь
MIN_ERA = 2                 # раньше эпохи Мифов торг слишком мелок
MAX_PER_POLITY = 2
CHARTER_RATE = 0.28
HIRE_RATE = 0.35
PEACE_RATE = 0.22
PRESS_RATE = 0.25
SEIZE_RATE = 0.10
REPUBLIC_RATE = 0.14


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("guilds", year)
    _found(ctx, year, period, rng)

    for guild_id in list(world.active_guilds):
        guild = world.guilds[guild_id]
        polity = world.polities.get(guild.polity_id)
        seat = world.settlements.get(guild.seat_id)
        if polity is None or polity.status != ACTIVE or seat is None \
                or seat.status != ACTIVE:
            _close(ctx, guild, year, rng,
                   guilds_mod.GONE if seat is None or seat.status != ACTIVE
                   else "держава, где она сидела, пала")
            continue

        guild.wealth += guilds_mod.income(world, guild, polity, period)
        guild.wealth -= guilds_mod.upkeep_cost(world, guild, polity, period)
        if guild.wealth <= 0:
            _close(ctx, guild, year, rng, guilds_mod.RUIN)
            continue
        guild.wealth = round(min(guild.wealth, 40000.0), 2)

        _act(ctx, guild, polity, seat, year, period, rng)


def _found(ctx, year: int, period: int, rng) -> None:
    """Где заводится гильдия: в богатом городе торгующей державы."""
    world = ctx.world
    if world.era_index_at(year) < MIN_ERA:
        return
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states or race.is_evil:
            continue
        if len(world.guilds_of(polity)) >= MAX_PER_POLITY:
            continue
        if not polity.routes and not polity.surpluses:
            continue
        cities = [world.settlements[sid] for sid in polity.settlement_ids
                  if sid in world.settlements
                  and world.settlements[sid].status == ACTIVE
                  and world.settlements[sid].population >= MIN_CITY]
        if not cities:
            continue
        chance = FOUND_RATE * (period / 10.0) * (0.6 + 0.2 * len(polity.routes))
        if not rng.chance(min(0.5, chance)):
            continue
        seat = rng.weighted([(city, float(city.population)) for city in cities])
        _raise(ctx, polity, seat, year, rng)


def _raise(ctx, polity, seat, year: int, rng) -> None:
    world = ctx.world
    race = races_mod.get_race(seat.race_id or polity.race_id)
    kind = guilds_mod.kind_for(rng, world, polity, seat)
    good = guilds_mod.main_good(polity)
    date = ctx.date_in(rng, year)
    sex = "f" if rng.chance(0.40) else "m"
    head = ctx.make_figure(
        rng, race, year, role="старшина гильдии", region_id=seat.region_id,
        title="старшина" if sex == "m" else "старшина", sex=sex,
        home_id=seat.id, epithet_chance=0.6,
        folk=world.folks.get(seat.folk_id))
    guild = world.add_guild(
        name=guilds_mod.guild_name(rng, kind, good, seat), kind=kind,
        good=good, seat_id=seat.id, polity_id=polity.id, founded=date,
        head_id=head.id,
        wealth=float(rng.randint(*guilds_mod.FOUND_WEALTH)))
    title, text = texts.guild_found(rng, guild, seat, head)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="guild",
        title=title, text=text, importance=2, actors=[head.id],
        subjects=[guild.id, polity.id, seat.id], region_id=seat.region_id,
        race_id=seat.race_id or polity.race_id)


# ---------------------------------------------------------------------------
# Что гильдия делает с деньгами
# ---------------------------------------------------------------------------

def _act(ctx, guild, polity, seat, year: int, period: int, rng) -> None:
    world = ctx.world
    fights = world.wars_of(polity, only_active=True)
    scale = period / 10.0

    if fights:
        fight = fights[0]
        if guild.wealth >= guilds_mod.COMPANY_COST \
                and rng.chance(HIRE_RATE * scale):
            _hire(ctx, guild, polity, year, rng)
        elif guild.wealth >= guilds_mod.PEACE_COST \
                and rng.chance(PEACE_RATE * scale):
            _buy_peace(ctx, guild, polity, fight, year, rng)
    else:
        if guild.wealth >= guilds_mod.CHARTER_COST \
                and rng.chance(CHARTER_RATE * scale):
            _charter(ctx, guild, polity, year, rng)
        elif rng.chance(PRESS_RATE * scale):
            _press(ctx, guild, polity, year, rng)

    # Престол смотрит на чужую кассу тем охотнее, чем она полнее и чем
    # круче нрав государя.
    greed = SEIZE_RATE * scale * (1.0 + 1.6 * max(0.0,
                                                  rulers.harshness(world,
                                                                   polity)))
    if guild.wealth > 400 and rng.chance(min(0.4, greed)):
        _seize(ctx, guild, polity, year, rng)
        return

    if guild.wealth >= guilds_mod.REPUBLIC_WEALTH \
            and rng.chance(REPUBLIC_RATE * scale):
        _republic(ctx, guild, polity, seat, year, rng)


def _hire(ctx, guild, polity, year: int, rng) -> None:
    world = ctx.world
    free = [world.companies[cid] for cid in world.active_companies
            if not world.companies[cid].employer_id]
    if not free:
        return
    company = rng.choice(sorted(free, key=lambda c: c.id))
    guild.wealth -= guilds_mod.COMPANY_COST
    guild.deeds += 1
    if company.id not in guild.companies:
        guild.companies.append(company.id)
    soldiery.hire(ctx, company, polity, year, rng)
    title, text = texts.guild_deed(rng, guild, "наём")
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="guild_deed", title=title, text=text, importance=2,
        subjects=[guild.id, polity.id, company.id],
        race_id=polity.race_id)


def _buy_peace(ctx, guild, polity, fight, year: int, rng) -> None:
    world = ctx.world
    guild.wealth -= guilds_mod.PEACE_COST
    guild.deeds += 1
    title, text = texts.guild_deed(rng, guild, "мир")
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="guild_deed", title=title, text=text, importance=3,
        subjects=[guild.id, polity.id, fight.id], race_id=polity.race_id)
    war_system.sue_for_peace(ctx, fight, year,
                             "Мир оплачен купеческой кассой, а не выигран "
                             "войском.")


def _charter(ctx, guild, polity, year: int, rng) -> None:
    """Вольности при чужом дворе: свой склад, свои весы, своя пошлина."""
    world = ctx.world
    options = []
    for route_id in polity.routes:
        route = world.routes.get(route_id)
        if route is None or route_id not in world.active_routes:
            continue
        other_id = route.seller_id if route.buyer_id == polity.id \
            else route.buyer_id
        other = world.polities.get(other_id)
        if other is None or other.status != ACTIVE or other.id == polity.id:
            continue
        if other.id in guild.charters:
            continue
        options.append(other)
    if not options:
        return
    host = rng.choice(sorted(options, key=lambda p: p.id))
    guild.wealth -= guilds_mod.CHARTER_COST
    guild.charters.append(host.id)
    guild.deeds += 1
    dip.set_relation(polity, host, dip.relation(polity, host.id) + 0.08)
    title, text = texts.charter(rng, guild, host)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="guild_charter", title=title, text=text, importance=2,
        subjects=[guild.id, polity.id, host.id], race_id=polity.race_id)


def _press(ctx, guild, polity, year: int, rng) -> None:
    """Гильдия требует войны: чужие пошлины разоряют торг."""
    world = ctx.world
    options = []
    for other_id, value in (polity.relations or {}).items():
        other = world.polities.get(other_id)
        if other is None or other.status != ACTIVE or value > 0.0:
            continue
        if world.pact_between(polity.id, other.id) is not None:
            continue
        options.append((other, 1.0 + 2.0 * abs(value)))
    if not options:
        return
    target = rng.weighted(options)
    guild.deeds += 1
    world.add_grudge(polity, target.id, "tolls", year)
    title, text = texts.guild_deed(rng, guild, "война", target)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="guild_deed", title=title, text=text, importance=2,
        subjects=[guild.id, polity.id, target.id], race_id=polity.race_id)


def _seize(ctx, guild, polity, year: int, rng) -> None:
    """Престол накладывает руку на кассу — и запоминают это надолго."""
    world = ctx.world
    guild.wealth = round(guild.wealth * rng.uniform(0.25, 0.55), 2)
    guild.notes.append("казну отбирал престол в %d году" % year)
    title, text = texts.guild_deed(rng, guild, "поборы")
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="guild_seized", title=title, text=text, importance=2,
        subjects=[guild.id, polity.id], race_id=polity.race_id)


# ---------------------------------------------------------------------------
# Вольный город
# ---------------------------------------------------------------------------

def _republic(ctx, guild, polity, seat, year: int, rng) -> None:
    """Богатый город выкупает вольность и правит собой сам."""
    world = ctx.world
    if seat.is_capital or seat.polity_id != polity.id:
        return
    race = races_mod.get_race(seat.race_id or polity.race_id)
    if not race.builds_states:
        return
    others = [world.settlements[sid] for sid in polity.settlement_ids
              if sid in world.settlements
              and world.settlements[sid].status == ACTIVE]
    if len(others) < 2:
        return
    head = world.figures.get(guild.head_id)
    if head is None or not head.alive_at(year) \
            or head.age_at(year) < race.adulthood:
        head = _new_head(ctx, guild, seat, race, year, rng)
    if head is None:
        return

    date = ctx.date_in(rng, year)
    form = "Торговая Республика" if rng.chance(0.6) else "Вольный Город"
    republic = world.add_polity(
        name=ctx.forge.polity(rng, race), form=form, race_id=race.id,
        founded=date, founder_id=head.id, capital_id=seat.id,
        ruler_id="", region_ids=[], settlement_ids=[],
        predecessor_id=polity.id)
    cities = [seat]
    for settlement in others:
        if settlement.id == seat.id or settlement.is_capital:
            continue
        if settlement.region_id == seat.region_id and rng.chance(0.45):
            cities.append(settlement)
    for settlement in cities:
        if settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)
        settlement.polity_id = republic.id
        settlement.is_capital = settlement.id == seat.id
        republic.settlement_ids.append(settlement.id)
        if settlement.region_id not in republic.region_ids:
            republic.region_ids.append(settlement.region_id)

    guild.polity_id = republic.id
    guild.republic_id = republic.id
    guild.head_id = head.id
    guild.deeds += 1
    guild.wealth = round(guild.wealth * 0.55, 2)   # вольность стоит дорого
    succession_mod.install_founder(ctx, republic, head, seat, date, year)
    world.refresh_populations()

    title, text = texts.republic(rng, guild, seat, republic, head)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="republic",
        title=title, text=text, importance=4, actors=[head.id],
        subjects=[guild.id, polity.id, republic.id], region_id=seat.region_id,
        race_id=race.id)


def _new_head(ctx, guild, seat, race, year: int, rng):
    """Старшина умер — совет выбирает нового."""
    sex = "f" if rng.chance(0.40) else "m"
    head = ctx.make_figure(
        ctx.rng("guilds", "head", guild.id, year), race, year,
        role="старшина гильдии", region_id=seat.region_id, title="старшина",
        sex=sex, home_id=seat.id, epithet_chance=0.6,
        folk=ctx.world.folks.get(seat.folk_id))
    guild.head_id = head.id
    return head


def _close(ctx, guild, year: int, rng, reason: str) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year, guild.founded
                       if guild.founded.year == year else None)
    years = max(0, year - guild.founded.year)
    world.end_guild(guild, date, reason)
    title, text = texts.guild_end(rng, guild, years)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="guild_end",
        title=title, text=text, importance=1, subjects=[guild.id])


__all__ = ["upkeep"]
