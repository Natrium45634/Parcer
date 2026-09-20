# -*- coding: utf-8 -*-
"""Основание поселений, стран и лагерей.

Правила жёсткие и заданы расами:

* цивилизованные народы оседают, строят города и со временем страны;
* зверолюды остаются племенами — никаких городов и государств;
* злые расы ставят лагеря, логова и орды, но страной не становятся никогда.
"""

from __future__ import annotations

from . import houses as houses_mod
from . import peoples
from . import succession
from .. import crafts as crafts_mod
from .. import narrative
from .. import races as races_mod
from .. import rulers as rulers_mod
from ..models import ACTIVE, GONE, GREAT, MINOR, RUINED, SETTLED

SETTLE_MIN_POPULATION = 380

# Чем больше у расы городов, тем меньше шанс, что следующий город будет её же.
# Без этого один удачливый народ (обычно люди) застраивает весь мир.
CROWDING = 0.12
POLITY_CROWDING = 0.6


def _colony_folk(world, mother, polity, race) -> str:
    """Народ новой колонии: тот же, что у её матери-города или столицы.

    Народ обязан быть своей расы. После завоевания или смены титульного
    народа столица державы может оказаться совсем другой крови — тогда
    колония переселенцев к её народу отношения не имеет.
    """
    def fits(folk_id):
        folk = world.folks.get(folk_id)
        return folk is not None and folk.race_id == race.id

    if mother is not None and fits(getattr(mother, "folk_id", "")):
        return mother.folk_id
    if polity is not None:
        capital = world.settlements.get(polity.capital_id)
        if capital is not None and fits(capital.folk_id):
            return capital.folk_id
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is not None and fits(settlement.folk_id):
                return settlement.folk_id
    # Иначе — самый многочисленный народ этой расы в мире.
    kin = [folk for folk in world.folks.values() if folk.race_id == race.id]
    if kin:
        return max(kin, key=lambda f: (f.population, f.id)).id
    return ""


def _crowding(count: int, factor: float = CROWDING) -> float:
    return 1.0 / (1.0 + count * factor)
POLITY_MIN_CAPITAL = 2200
CAMP_MIN = 40
CAMP_MAX = 220


def _kind_for(rng, race):
    words = race.settlement_words or ("Город",)
    pairs = [(word, 3.0 if index == 0 else 1.0) for index, word in enumerate(words)]
    return rng.weighted(pairs)


def _leader_of(ctx, rng, race, year, settlement=None, tribe=None, kind="founder"):
    """Берёт живого вождя/основателя или создаёт нового."""
    world = ctx.world
    existing_id = ""
    if tribe is not None:
        existing_id = tribe.chief_id or tribe.founder_id
    elif settlement is not None:
        existing_id = settlement.founder_id
    figure = world.figures.get(existing_id)
    if figure is not None and figure.alive_at(year):
        return figure, False

    sex = "f" if rng.chance(0.42) else "m"
    title = ctx.title_for(race, kind, sex)
    region_id = (tribe.region_id if tribe is not None
                 else settlement.region_id if settlement is not None else "")
    figure = ctx.make_figure(rng, race, year, role=kind, region_id=region_id,
                             title=title, sex=sex)
    return figure, True


# ---------------------------------------------------------------------------
# Племя оседает и строит поселение
# ---------------------------------------------------------------------------

def tick_settling(ctx, year: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    if not spec.allow_settlements:
        return
    rng = ctx.rng("settling", year)
    if not rng.chance(ctx.spread_rate(spec.settle_rate)):
        return

    settled_by_race = {}
    for settlement_id in world.active_settlements:
        race_id = world.settlements[settlement_id].race_id
        settled_by_race[race_id] = settled_by_race.get(race_id, 0) + 1

    candidates = []
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        race = races_mod.get_race(tribe.race_id)
        if not race.settles or tribe.population < SETTLE_MIN_POPULATION:
            continue
        weight = float(tribe.population) * _crowding(settled_by_race.get(race.id, 0))
        candidates.append((tribe, weight))
    if not candidates:
        return

    tribe = rng.weighted(candidates)
    race = races_mod.get_race(tribe.race_id)
    region = world.regions.get(tribe.region_id)
    if region is None:
        return

    leader, _ = _leader_of(ctx, rng, race, year, tribe=tribe, kind="founder")
    date = ctx.date_in(rng, year)
    hex_index = tribe.hex_index if tribe.hex_index >= 0 else -1
    if ctx.map is not None and hex_index < 0:
        hex_index = ctx.map.place(region.id, rng, kind="city")

    speech = ctx.tongue_of(tribe.folk_id)
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race, speech), kind=_kind_for(rng, race),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=region.id, population=max(120, int(tribe.population * 0.92)),
        hex_index=hex_index, folk_id=tribe.folk_id,
        origin_tribe_id=tribe.id,
    )
    if ctx.map is not None and hex_index >= 0:
        ctx.map.claim(hex_index, settlement.id)
    leader.roles.append("основатель поселения")
    leader.home_id = settlement.id

    world.end_tribe(tribe, date, "осело и построило %s" % settlement.name, SETTLED)
    tribe.settlement_id = settlement.id

    title, text = narrative.settlement_found(rng, settlement, leader, region,
                                             race, tribe=tribe)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="settlement_found",
        title=title, text=text, importance=3, actors=[leader.id],
        subjects=[settlement.id, tribe.id], region_id=region.id, race_id=race.id,
    )
    # Основатель города кладёт начало знатному роду — так рождается знать.
    houses_mod.found_house(ctx, leader, year, date, seat=settlement, rank=MINOR)

    # Не все согласны жить за стенами: часть племени уходит кочевать дальше.
    if rng.chance(0.38) and settlement.population > 500:
        leaving = int(settlement.population * rng.uniform(0.12, 0.25))
        settlement.population -= leaving
        spot = ctx.pick_region(rng, race, near=region.id, spread=0.4) or region
        peoples.found_tribe(ctx, race, spot, year, rng, parent=tribe,
                            population=leaving, after=date)


# ---------------------------------------------------------------------------
# Страна расширяется новым городом
# ---------------------------------------------------------------------------

def tick_colonies(ctx, year: int) -> None:
    """Расселение: страны и крупные вольные города ставят новые поселения."""
    world = ctx.world
    spec = ctx.era_spec(year)
    if not spec.allow_settlements:
        return
    rng = ctx.rng("colonies", year)
    if not rng.chance(ctx.spread_rate(spec.colony_rate)):
        return

    settled_by_race = {}
    for settlement_id in world.active_settlements:
        race_id = world.settlements[settlement_id].race_id
        settled_by_race[race_id] = settled_by_race.get(race_id, 0) + 1

    candidates = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        race = races_mod.get_race(polity.race_id)
        weight = ((1.0 + len(polity.settlement_ids)) * race.expansion
                  * _crowding(settled_by_race.get(race.id, 0)))
        candidates.append((("polity", polity), weight))
    for settlement_id in world.active_settlements:
        mother = world.settlements[settlement_id]
        if mother.polity_id or mother.population < 900:
            continue
        race = races_mod.get_race(mother.race_id)
        candidates.append((("free", mother), 0.7 * race.expansion
                           * _crowding(settled_by_race.get(race.id, 0))))
    if not candidates:
        return

    kind, source = rng.weighted(candidates)
    if kind == "polity":
        polity = source
        race = races_mod.get_race(polity.race_id)
        home_id = rng.choice(polity.region_ids) if polity.region_ids else ""
    else:
        polity = None
        race = races_mod.get_race(source.race_id)
        home_id = source.region_id
    region = ctx.pick_region(rng, race, near=home_id, spread=0.25)
    if region is None:
        return

    sex = "f" if rng.chance(0.42) else "m"
    leader = ctx.make_figure(rng, race, year, role="основатель",
                             region_id=region.id,
                             title=ctx.title_for(race, "founder", sex), sex=sex)
    date = ctx.date_in(rng, year)
    colony_hex = ctx.map.place(region.id, rng, kind="city") if ctx.map else -1
    colony_folk = _colony_folk(world, source if kind == "free" else None,
                               polity, race)
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race, ctx.tongue_of(colony_folk)),
        kind=_kind_for(rng, race),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=region.id, population=rng.randint(150, 600),
        polity_id=polity.id if polity else "", hex_index=colony_hex,
        folk_id=colony_folk,
    )
    if ctx.map is not None and colony_hex >= 0:
        ctx.map.claim(colony_hex, settlement.id)
    leader.roles.append("основатель поселения")
    leader.home_id = settlement.id
    subjects = [settlement.id]
    if polity is not None:
        polity.settlement_ids.append(settlement.id)
        if region.id not in polity.region_ids:
            polity.region_ids.append(region.id)
        subjects.append(polity.id)

    title, text = narrative.settlement_found(rng, settlement, leader, region,
                                             race, polity=polity)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="colony_found",
        title=title, text=text, importance=3, actors=[leader.id],
        subjects=subjects, region_id=region.id, race_id=race.id,
    )
    houses_mod.found_house(ctx, leader, year, date, seat=settlement, rank=MINOR,
                           polity=polity)


# ---------------------------------------------------------------------------
# Рождение страны
# ---------------------------------------------------------------------------

def tick_polities(ctx, year: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    if not spec.allow_polities:
        return
    rng = ctx.rng("polities", year)
    if not rng.chance(ctx.spread_rate(spec.polity_rate)):
        return

    by_race = {}
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.polity_id:
            continue
        race = races_mod.get_race(settlement.race_id)
        if not race.builds_states:
            continue
        by_race.setdefault(race.id, []).append(settlement)

    polities_by_race = {}
    for polity_id in world.active_polities:
        race_id = world.polities[polity_id].race_id
        polities_by_race[race_id] = polities_by_race.get(race_id, 0) + 1

    candidates = []
    for race_id, items in sorted(by_race.items()):
        best = max(item.population for item in items)
        if len(items) >= 2 or best >= POLITY_MIN_CAPITAL:
            weight = (float(len(items)) * 2.0 + best / 1000.0) * _crowding(
                polities_by_race.get(race_id, 0), POLITY_CROWDING)
            candidates.append((race_id, weight))
    if not candidates:
        return

    race = races_mod.get_race(rng.weighted(candidates))
    free = sorted(by_race[race.id], key=lambda s: (-s.population, s.id))
    capital = free[0]
    region = world.regions.get(capital.region_id)

    members = [capital]
    nearby = set(region.neighbors) | {region.id} if region else {capital.region_id}
    limit = rng.randint(1, 4)
    for settlement in free[1:]:
        if len(members) - 1 >= limit:
            break
        if settlement.region_id in nearby or rng.chance(0.2):
            members.append(settlement)

    leader, is_new = _leader_of(ctx, rng, race, year, settlement=capital, kind="ruler")
    sex = leader.sex
    # Форму выбираем до титула: империей правит император, а не король.
    form = rng.choice(race.polity_words or ("Королевство",))
    ruler_title = races_mod.title_for_form(form, sex, race.ruler_titles)
    if ruler_title not in leader.titles:
        leader.titles.insert(0, ruler_title)
    leader.roles.append("основатель страны")

    date = ctx.date_in(rng, year)
    polity = world.add_polity(
        name=ctx.forge.polity(rng, race, ctx.tongue_of(capital.folk_id)),
        form=form,
        race_id=race.id, founded=date, founder_id=leader.id,
        capital_id=capital.id, ruler_id=leader.id,
        region_ids=[], settlement_ids=[],
    )
    for settlement in members:
        settlement.polity_id = polity.id
        polity.settlement_ids.append(settlement.id)
        if settlement.region_id not in polity.region_ids:
            polity.region_ids.append(settlement.region_id)
    capital.is_capital = True
    leader.home_id = capital.id

    title, text = narrative.polity_found(rng, polity, leader, capital, race, members)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="polity_found",
        title=title, text=text, importance=4, actors=[leader.id],
        subjects=[polity.id, capital.id], region_id=capital.region_id,
        race_id=race.id,
    )

    # Роды основателей вошедших городов становятся знатью новой страны.
    for settlement in members:
        house = world.houses.get(
            world.figures[settlement.founder_id].house_id
            if settlement.founder_id in world.figures else "")
        if house is not None and house.status == ACTIVE:
            house.rank = GREAT if settlement.id == capital.id else house.rank
            houses_mod.attach(world, house, polity)
    succession.install_founder(ctx, polity, leader, capital, date, year)


# ---------------------------------------------------------------------------
# Лагеря злых рас
# ---------------------------------------------------------------------------

def tick_camps(ctx, year: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    rng = ctx.rng("camps", year)
    if not rng.chance(ctx.spread_rate(spec.camp_rate)):
        return

    evil = [race for race in ctx.awakened if race.is_evil]
    if not evil:
        return
    race = rng.weighted([(race, race.expansion) for race in evil])
    region = ctx.pick_region(rng, race)
    if region is None:
        return

    sex = "f" if rng.chance(0.3) else "m"
    leader = ctx.make_figure(rng, race, year, role="вожак", region_id=region.id,
                             title=ctx.title_for(race, "chief", sex), sex=sex,
                             epithet_chance=0.75)
    date = ctx.date_in(rng, year)
    camp_hex = ctx.map.place(region.id, rng, kind="camp") if ctx.map else -1
    camp = world.add_camp(
        name=ctx.forge.camp(rng, race), word=rng.choice(race.camp_words or ("Лагерь",)),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=region.id, population=rng.randint(CAMP_MIN, CAMP_MAX),
        hex_index=camp_hex,
    )
    if ctx.map is not None and camp_hex >= 0:
        ctx.map.claim(camp_hex, camp.id, kind="camp")
    leader.home_id = camp.id
    leader.roles.append("основатель лагеря")

    title, text = narrative.camp_found(rng, camp, leader, region, race)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="camp_found",
        title=title, text=text, importance=1, actors=[leader.id],
        subjects=[camp.id], region_id=region.id, race_id=race.id,
    )


# ---------------------------------------------------------------------------
# Рост и упадок поселений, стран и лагерей
# ---------------------------------------------------------------------------

def _tributaries(world) -> dict:
    """Сколько данников у каждой державы — считается раз за такт."""
    counts = {}
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        lord = polity.tribute_to or polity.overlord_id
        if lord:
            counts[lord] = counts.get(lord, 0) + 1
    return counts

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    rng = ctx.rng("settlement_upkeep", year)
    era_index = world.era_index_at(year)
    tributaries = _tributaries(world)

    for settlement_id in list(world.active_settlements):
        settlement = world.settlements[settlement_id]
        race = races_mod.get_race(settlement.race_id)
        region = world.regions.get(settlement.region_id)
        capacity = 7000.0 * (region.capacity if region else 1.0)
        if ctx.map is not None and region is not None and region.from_map:
            # Урожайные годы и рыбный ход кормят больше ртов, чем голая земля.
            capacity *= 0.85 + 0.5 * ctx.map.bounty(region.id)
        polity = world.polities.get(settlement.polity_id)
        if polity is not None and polity.hunger:
            # Города державы, которой нечем кормить, просто не растут:
            # это честнее постоянного мора и куда точнее по сути.
            capacity *= max(0.35, 1.0 - polity.hunger * 0.8)
        if settlement.is_capital:
            capacity *= 2.1
        elif settlement.polity_id:
            capacity *= 1.35
        capacity *= 0.75 + 0.14 * era_index
        if polity is not None:
            # Плуг, трёхполье и акведук кормят больше народу, чем указ.
            capacity *= crafts_mod.bonus(polity.known, "growth")
            # Хозяйская хватка государя кормит города или не кормит их:
            # отсюда и берутся «при нём страна поднялась» и наоборот.
            capacity *= rulers_mod.stewardship(world, polity)
            # Дань уходит хлебом и людьми: данник растёт хуже, сюзерен —
            # лучше. Без этого дань была бы строкой в договоре и только.
            if polity.tribute_to:
                capacity *= 0.90
            capacity *= 1.0 + 0.03 * min(4, tributaries.get(polity.id, 0))

        population = settlement.population
        population += (population * ctx.growth(race.growth, settlement.region_id)
                       * period * (1.0 - population / capacity))
        population *= rng.uniform(0.99, 1.015)
        settlement.population = max(0, int(population))

        if settlement.population < 60 or rng.chance(0.00009 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            world.end_settlement(settlement, date, "запустение", RUINED)
            world.add_event(
                date=date, era_index=era_index, kind="settlement_ruined",
                title="Запустение: %s" % settlement.name,
                text=narrative.ruin_text(rng, narrative.cap(settlement.full_name)),
                importance=2, subjects=[settlement.id],
                region_id=settlement.region_id, race_id=settlement.race_id,
            )

    for camp_id in list(world.active_camps):
        camp = world.camps[camp_id]
        race = races_mod.get_race(camp.race_id)
        population = camp.population * (
            1.0 + ctx.growth(race.growth, camp.region_id) * period
            * rng.uniform(-0.6, 1.0))
        camp.population = max(0, int(population))
        if camp.population < 20 or rng.chance(0.0022 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            world.end_camp(camp, date, "разорён", GONE)
            world.add_event(
                date=date, era_index=era_index, kind="camp_end",
                title="Конец лагеря: %s" % camp.name,
                text=narrative.camp_end_text(rng, camp), importance=1,
                subjects=[camp.id], region_id=camp.region_id, race_id=camp.race_id,
            )

    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        alive = [sid for sid in polity.settlement_ids
                 if world.settlements[sid].status == ACTIVE]
        polity.settlement_ids = alive
        if not alive or rng.chance(0.00018 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            reason = "распад" if alive else "не осталось ни одного города"
            world.end_polity(polity, date, reason)
            world.add_event(
                date=date, era_index=era_index, kind="polity_fall",
                title="Падение: %s" % polity.name,
                text=narrative.polity_fall_text(rng, polity), importance=3,
                subjects=[polity.id], race_id=polity.race_id,
            )
