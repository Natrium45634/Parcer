# -*- coding: utf-8 -*-
"""Крепости и вольные роты — то, что остаётся от войны между войнами.

**Крепость** строят не там, где красиво, а там, где узко: на перевале,
у брода, на меже. Города гибнут и зарастают, а крепость стоит веками —
меняется только знамя над ней. Поэтому в летописи она и появляется
снова и снова: «взята», «отбита», «снова взята», «срыта до основания».

**Вольная рота** рождается из войны: после мира остаются люди, которые
ничего другого не умеют. Их нанимают — и тогда они прибавляют войску
силы, — а без найма они кормятся сами, и округе от этого плохо.
"""

from __future__ import annotations

from .. import narrative_soldiery as texts
from .. import races as races_mod
from .. import warfare
from ..models import ACTIVE

# --- крепости ------------------------------------------------------------
BUILD_RATE = 0.16           # шанс за десятилетие, что держава заложит крепость
MAX_PER_POLITY = 4
DECAY_RATE = 0.004          # заброшенная крепость однажды рассыпается

# --- вольные роты --------------------------------------------------------
BIRTH_AFTER_WAR = 0.30      # шанс, что после войны останется рота
HIRE_CHANCE = 0.45          # шанс найма в год войны
RAID_CHANCE = 0.22          # и шанс, что рота без найма пойдёт грабить
DISBAND_RATE = 0.10
CONTRACT_YEARS = 12


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    rng = ctx.rng("soldiery", year)
    _build_forts(ctx, year, period, rng)
    _tend_forts(ctx, year, period, rng)
    _tend_companies(ctx, year, period, rng)


# ---------------------------------------------------------------------------
# Крепости
# ---------------------------------------------------------------------------

def _border_regions(world, polity) -> list:
    """Земли, которыми держава граничит с чужими, — и теснины внутри них."""
    own = set(polity.region_ids)
    out = []
    for region_id in polity.region_ids:
        region = world.regions.get(region_id)
        if region is None:
            continue
        outside = [item for item in region.neighbors if item not in own]
        hard = region.terrain in ("горы", "холмы", "побережье", "острова")
        if outside or hard:
            out.append(region)
    return out


def _build_forts(ctx, year: int, period: int, rng) -> None:
    world = ctx.world
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states:
            continue
        held = world.fortresses_of(polity)
        if len(held) >= MAX_PER_POLITY:
            continue

        chance = BUILD_RATE * (period / 10.0)
        ruler = world.figures.get(polity.ruler_id)
        if ruler is not None:
            skills = getattr(ruler, "skills", None) or {}
            chance *= 0.6 + 0.12 * int(skills.get("война", 5))
            if "одержимый строительством" in (getattr(ruler, "traits", None) or ()):
                chance *= 2.2
        if world.wars_of(polity, only_active=True):
            chance *= 1.8            # строят, когда припекло
        if not rng.chance(min(0.8, chance)):
            continue

        taken = {item.region_id for item in held}
        options = [item for item in _border_regions(world, polity)
                   if item.id not in taken]
        if not options:
            continue
        region = rng.choice(sorted(options, key=lambda r: r.id))
        _raise_fort(ctx, polity, region, year, rng)


def _raise_fort(ctx, polity, region, year: int, rng):
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    date = ctx.date_in(rng, year)
    ruler = world.figures.get(polity.ruler_id)
    kind = texts.fort_kind(rng, race, region)
    strength = rng.weighted(((2, 2.0), (3, 4.0), (4, 2.0), (5, 0.6)))
    if region.terrain in ("горы", "холмы"):
        strength = min(5, strength + 1)
    fortress = world.add_fortress(
        name=ctx.forge.settlement(rng, race), region_id=region.id, built=date,
        founder_id=ruler.id if ruler is not None else "",
        polity_id=polity.id, builder_polity=polity.id, kind=kind,
        strength=strength)

    title, text = texts.fort_built(rng, fortress, polity, region, ruler)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="fortress_built",
        title=title, text=text, importance=2,
        actors=[ruler.id] if ruler is not None else [],
        subjects=[fortress.id, polity.id], region_id=region.id,
        race_id=polity.race_id)
    return fortress


def _tend_forts(ctx, year: int, period: int, rng) -> None:
    """Крепость без хозяина ветшает, но ветшает долго."""
    world = ctx.world
    for fortress_id in list(world.active_fortresses):
        fortress = world.fortresses[fortress_id]
        holder = world.polities.get(fortress.polity_id)
        if holder is not None and holder.status == ACTIVE:
            # Хозяин, владеющий землёй, крепость чинит.
            if fortress.region_id in holder.region_ids:
                continue
            # Земля ушла к другим — гарнизон уходит с ней.
            fortress.polity_id = ""
            fortress.notes.append("оставлена в %d году" % year)
            continue
        if fortress.polity_id:
            fortress.polity_id = ""
            fortress.holders.append([year, ""])
        # Пустая крепость может отойти тому, кто владеет землёй.
        for polity_id in world.active_polities:
            polity = world.polities[polity_id]
            if fortress.region_id in polity.region_ids:
                _hand_over(ctx, fortress, polity, year, rng, retaken=False)
                break
        else:
            if rng.chance(DECAY_RATE * (period / 10.0)):
                date = ctx.date_in(rng, year)
                world.end_fortress(fortress, date, "рассыпалась от времени",
                                   "заброшено")
                title, text = texts.fort_lost(rng, fortress)
                world.add_event(
                    date=date, era_index=world.era_index_at(year),
                    kind="fortress_gone", title=title, text=text, importance=1,
                    subjects=[fortress.id], region_id=fortress.region_id)


def _hand_over(ctx, fortress, polity, year: int, rng, retaken: bool = True):
    """Знамя над крепостью меняется — сама она остаётся."""
    world = ctx.world
    previous = world.polities.get(fortress.polity_id)
    fortress.polity_id = polity.id
    fortress.holders.append([year, polity.id])
    if retaken:
        fortress.times_taken += 1
    date = ctx.date_in(rng, year)
    title, text = texts.fort_taken(rng, fortress, polity, previous, retaken)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="fortress_taken",
        title=title, text=text, importance=3 if retaken else 1,
        subjects=[fortress.id, polity.id], region_id=fortress.region_id,
        race_id=polity.race_id)


def take_fortress(ctx, fortress, polity, year: int, rng) -> None:
    """Крепость берут с боя — так она и переходит из рук в руки веками."""
    fortress.sieges += 1
    _hand_over(ctx, fortress, polity, year, rng, retaken=True)


def raze_fortress(ctx, fortress, year: int, rng) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year)
    world.end_fortress(fortress, date, "срыта до основания", "разрушено")
    title, text = texts.fort_razed(rng, fortress)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="fortress_razed",
        title=title, text=text, importance=2, subjects=[fortress.id],
        region_id=fortress.region_id)


def guard_of(world, polity, region_id: str) -> float:
    """Насколько крепости помогают обороняющемуся в этой земле."""
    value = 1.0
    for fortress in world.active_fortresses:
        item = world.fortresses[fortress]
        if item.region_id != region_id or item.polity_id != polity.id:
            continue
        value += 0.05 * item.strength
    return min(1.45, value)


# ---------------------------------------------------------------------------
# Вольные роты
# ---------------------------------------------------------------------------

def spawn_company(ctx, polity, year: int, rng, reason: str = ""):
    """После войны остаются те, кто ничего другого не умеет."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    region_id = polity.region_ids[0] if polity.region_ids else ""
    date = ctx.date_in(rng, year)
    sex = "f" if rng.chance(0.28) else "m"
    captain = ctx.make_figure(
        rng, race, year, role="капитан вольной роты", region_id=region_id,
        title="капитан" if sex == "m" else "капитанша", sex=sex,
        epithet_chance=0.9)
    men = rng.randint(120, 900)
    company = world.add_company(
        name=ctx.forge.house(rng, race), race_id=race.id, founded=date,
        captain_id=captain.id, men=men,
        quality=round(rng.uniform(1.05, 1.5), 2), region_id=region_id)

    title, text = texts.company_born(rng, company, captain, polity, reason)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="company_born",
        title=title, text=text, importance=2, actors=[captain.id],
        subjects=[company.id], region_id=region_id, race_id=race.id)
    return company


def free_companies(world) -> list:
    return [world.companies[cid] for cid in world.active_companies
            if not world.companies[cid].employer_id]


def hire(ctx, company, polity, year: int, rng) -> None:
    world = ctx.world
    company.employer_id = polity.id
    company.contract_until = year + rng.randint(4, CONTRACT_YEARS)
    company.wars += 1
    date = ctx.date_in(rng, year)
    title, text = texts.company_hired(rng, company, polity)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="company_hired",
        title=title, text=text, importance=2,
        subjects=[company.id, polity.id],
        region_id=polity.region_ids[0] if polity.region_ids else "",
        race_id=polity.race_id)


def _tend_companies(ctx, year: int, period: int, rng) -> None:
    world = ctx.world
    for company_id in list(world.active_companies):
        company = world.companies[company_id]
        employer = world.polities.get(company.employer_id)
        if company.employer_id and (employer is None
                                    or employer.status != ACTIVE
                                    or year >= company.contract_until):
            company.employer_id = ""
            company.contract_until = 0
        if company.employer_id:
            continue

        # Без найма рота кормится сама — и округе это дорого обходится.
        if rng.chance(RAID_CHANCE * (period / 10.0)):
            _raid(ctx, company, year, rng)
        elif rng.chance(DISBAND_RATE * (period / 10.0)):
            date = ctx.date_in(rng, year)
            world.end_company(company, date, "разошлась по домам")
            title, text = texts.company_gone(rng, company)
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="company_gone", title=title, text=text, importance=1,
                subjects=[company.id], region_id=company.region_id)


def _raid(ctx, company, year: int, rng) -> None:
    """Рота без найма грабит ту землю, в которой стоит."""
    world = ctx.world
    targets = [world.settlements[sid] for sid in world.active_settlements
               if world.settlements[sid].region_id == company.region_id]
    if not targets:
        # Стоять негде — рота уходит туда, где есть кого грабить.
        alive = list(world.active_settlements)
        if not alive:
            return
        settlement = world.settlements[rng.choice(sorted(alive))]
        company.region_id = settlement.region_id
    else:
        settlement = rng.weighted([(item, float(max(80, item.population)))
                                   for item in targets])
    loss = int(min(settlement.population * 0.10,
                   company.men * rng.uniform(0.8, 2.5)))
    settlement.population = max(60, settlement.population - loss)
    company.raids += 1
    company.men = max(60, int(company.men * rng.uniform(0.95, 1.12)))

    date = ctx.date_in(rng, year)
    title, text = texts.company_raid(rng, company, settlement, loss)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="company_raid",
        title=title, text=text, importance=2, subjects=[company.id,
                                                        settlement.id],
        region_id=settlement.region_id, race_id=company.race_id)


def hired_force(world, polity) -> tuple:
    """Что добавляют державе нанятые ею роты."""
    men, power = 0, 0.0
    for company_id in world.active_companies:
        company = world.companies[company_id]
        if company.employer_id != polity.id:
            continue
        men += company.men
        power += warfare.host_power(company.men, company.quality)
    return men, power
