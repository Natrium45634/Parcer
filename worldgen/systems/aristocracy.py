# -*- coding: utf-8 -*-
"""Знать как политическая сила.

Раз в десятилетие держава смотрит на свою аристократию, а аристократия —
на державу. Происходит три вещи.

1. **Лестница.** Чем крупнее и старше страна, тем больше в ней ступеней
   знатности. Молодое княжество знает две, тысячелетняя империя — шесть.
   Дома расставляются по ним по силе: наверху единицы, внизу большинство.
   Переход на высшую ступень — событие для летописи.
2. **Счёт обид.** Богатый, честолюбивый и чуждый государю по нраву род
   копит недовольство. Государь, умеющий держать двор, гасит его; слабый
   и вздорный — растит.
3. **Дело.** Накопив довольно, знать переходит к действию: требует
   вольностей, поднимает междоусобицу за венец или уводит свою вотчину
   из состава державы вовсе.
"""

from __future__ import annotations

from . import houses as houses_mod
from . import succession
from .. import aristocracy as arist
from .. import narrative
from .. import narrative_aristocracy as texts
from .. import races as races_mod
from .. import rulers as rulers_mod
from ..dynasty import HeirChoice, house_adults
from ..models import ACTIVE, GREAT, MINOR
from ..timeline import years_text

FRONDA_RATE = 0.30          # шанс за десятилетие для достаточно злого рода
WAR_RATE = 0.16
SECESSION_RATE = 0.12
MIN_CITIES_TO_SPLIT = 4     # державу в три города знать не делит


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        race = races_mod.get_race(polity.race_id)
        if not race.has_nobility:
            continue
        houses = [world.houses[house_id] for house_id in polity.house_ids
                  if house_id in world.houses
                  and world.houses[house_id].status == ACTIVE]
        if not houses:
            continue
        rng = ctx.rng("aristocracy", polity.id, year)
        _ranks(ctx, polity, race, houses, year, rng)
        _politics(ctx, polity, race, houses, year, period, rng)


# ---------------------------------------------------------------------------
# Лестница знатности
# ---------------------------------------------------------------------------

def _live_cities(world, polity) -> list:
    return [world.settlements[sid] for sid in polity.settlement_ids
            if sid in world.settlements
            and world.settlements[sid].status == ACTIVE]


def _weight(world, house) -> float:
    """Чем измеряется вес рода: слава, достаток, вольности и гнездо.

    Гнездо считается мягко: род, потерявший замок, не становится от этого
    последним в державе — у него остаются память, деньги и грамоты.
    """
    seat = world.settlements.get(house.seat_id)
    size = float(seat.population) ** 0.25 if (seat is not None
                                              and seat.status == ACTIVE) else 2.0
    return (max(0.1, house.prestige) * (0.7 + 0.3 * house.wealth) * size
            * (1.0 + 0.15 * house.charters))


def _ranks(ctx, polity, race, houses, year: int, rng) -> None:
    """Расставляет дома по ступеням и отмечает возвышения."""
    world = ctx.world
    vassals = [house for house in houses if house.id != polity.house_id]
    if not vassals:
        return
    steps = arist.depth(polity, race, len(_live_cities(world, polity)), year)
    vassals.sort(key=lambda h: (-_weight(world, h), h.id))
    sizes = arist.spread(len(vassals), steps)

    index = 0
    for offset, count in enumerate(sizes):
        rung = steps - 1 - offset          # сверху вниз
        for house in vassals[index:index + count]:
            _set_rung(ctx, polity, race, house, rung, steps, year, rng)
        index += count

    # Правящий дом стоит вне лестницы: его глава носит венец.
    ruling = world.houses.get(polity.house_id)
    if ruling is not None and ruling.status == ACTIVE:
        ruling.rung = steps
        ruling.style = ctx.ruler_title(polity, race, "m")


def _set_rung(ctx, polity, race, house, rung: int, steps: int, year: int,
              rng) -> None:
    world = ctx.world
    was = house.rung
    house.rung = rung
    house.style = arist.style_text(race, rung, "m")
    if was < 0 or rung <= was:
        return
    # О мелких перестановках летопись молчит: пишем о входе в высшую знать,
    # да и то лишь там, где эта знать чего-то стоит — в державе с лестницей
    # в две ступени «возвышение» означает только, что род не последний.
    if rung < 2 or rung < steps - 2 or house.alive_count <= 0:
        return
    head = world.figures.get(house.head_id)
    style = arist.style_text(race, rung, head.sex if head is not None else "m")
    date = ctx.date_in(rng, year)
    title, text = texts.elevation(rng, polity, house, style)
    if house.rank == MINOR and rung >= steps - 1:
        house.rank = GREAT
    house.prestige = min(12.0, house.prestige + 0.8)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="house_elevated",
        title=title, text=text, importance=2,
        actors=[head.id] if head is not None else [],
        subjects=[house.id, polity.id], race_id=race.id,
        region_id=world.settlements[house.seat_id].region_id
        if house.seat_id in world.settlements else "")


# ---------------------------------------------------------------------------
# Счёт обид и дело
# ---------------------------------------------------------------------------

def _politics(ctx, polity, race, houses, year: int, period: int, rng) -> None:
    world = ctx.world
    ruler = world.figures.get(polity.ruler_id)
    angry = []
    for house in houses:
        house.discontent = arist.discontent(world, polity, house, ruler, race,
                                            period)
        if house.id != polity.house_id and house.discontent >= arist.FRONDA_LEVEL:
            angry.append(house)
    if not angry:
        return

    house = rng.weighted([(item, item.discontent ** 2 * 4.0) for item in angry])

    # Род, дошедший до края, грамот уже не пишет: он либо уводит вотчину,
    # либо идёт за венцом. Потому фронда и разбирается последней —
    # иначе она год за годом спускала бы пар тем, кому пора воевать.
    if house.discontent >= arist.WAR_LEVEL:
        if len(_live_cities(world, polity)) >= MIN_CITIES_TO_SPLIT \
                and rng.chance(SECESSION_RATE * (period / 10.0)) \
                and _secede(ctx, polity, race, house, year, rng):
            return
        if rng.chance(WAR_RATE * (period / 10.0)):
            _civil_war(ctx, polity, race, house, year, rng)
        return
    if rng.chance(FRONDA_RATE * (period / 10.0)):
        _fronda(ctx, polity, race, house, ruler, year, rng)


def _fronda(ctx, polity, race, house, ruler, year: int, rng) -> None:
    """Знать требует вольностей — и корона решает, есть ли чем отказать."""
    world = ctx.world
    # Уступает тот, у кого слабее двор и меньше сил против богатого рода.
    resolve = 1.0 / max(0.3, rulers_mod.court_grip(world, polity))
    yielded = not rng.chance(min(0.85, 0.35 + 0.22 * resolve
                                 - 0.12 * house.wealth))
    date = ctx.date_in(rng, year)
    if yielded:
        house.charters += 1
        house.prestige = min(12.0, house.prestige + 0.6)
        house.discontent = max(0.0, house.discontent - 0.3)
    else:
        house.prestige = max(0.15, house.prestige - 0.3)
        house.discontent = min(1.0, house.discontent + 0.18)

    title, text = texts.fronda(rng, polity, house, ruler, yielded)
    head = world.figures.get(house.head_id)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="noble_fronda",
        title=title, text=text, importance=2,
        actors=[head.id] if head is not None else [],
        subjects=[house.id, polity.id], race_id=race.id)


def _civil_war(ctx, polity, race, house, year: int, rng) -> None:
    """Междоусобица: дом идёт за венцом."""
    world = ctx.world
    leaders = house_adults(world, house, race, year)
    if not leaders:
        house.discontent = max(0.0, house.discontent - 0.3)
        return
    leader = world.figures.get(house.head_id) or leaders[0]
    if not leader.alive_at(year):
        leader = leaders[0]

    reign = world.current_reign(polity)
    date = ctx.date_in(rng, year, reign.start if reign is not None else None)
    length = rng.randint(2, max(3, int(race.adulthood * 0.7)))

    # Сила мятежа: богатство, слава и то, сколько домов пойдёт следом.
    friends = sum(1 for other in world.houses_of_polity(polity)
                  if other.id not in (house.id, polity.house_id)
                  and other.status == ACTIVE
                  and other.discontent >= arist.FRONDA_LEVEL)
    strength = 0.30 + 0.09 * friends + 0.08 * house.wealth + 0.05 * house.prestige
    strength /= max(0.4, rulers_mod.war_edge(world, polity)
                    * rulers_mod.court_grip(world, polity))
    crown_wins = not rng.chance(max(0.12, min(0.82, strength)))

    head = world.figures.get(house.head_id)
    title, text = texts.civil_war(rng, polity, house, leader,
                                  years_text(length), crown_wins)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="noble_war",
        title=title, text=text, importance=4,
        actors=[leader.id] + ([head.id] if head is not None
                              and head.id != leader.id else []),
        subjects=[house.id, polity.id], race_id=race.id)

    _war_toll(ctx, polity, length, rng)
    if crown_wins:
        house.discontent = 0.0
        house.prestige = max(0.15, house.prestige * 0.4)
        house.wealth = max(0.2, house.wealth * 0.6)
        house.rung = max(0, house.rung - 1)
        if house.rank == GREAT:
            house.rank = MINOR
        world.schedule_death(leader, date, narrative.fate(
            ("казнён за мятеж", "казнена за мятеж"), leader.sex))
        return

    # Мятеж удался: венец переходит к дому-победителю.
    house.discontent = 0.0
    house.prestige = min(12.0, house.prestige + 2.0)
    old_house = world.houses.get(polity.house_id)
    old_ruler = world.figures.get(polity.ruler_id)
    succession.close_reign(ctx, reign, date, "междоусобица")
    if old_ruler is not None and old_ruler.alive_at(year):
        world.schedule_death(old_ruler, date, narrative.fate(
            ("погиб в междоусобице", "погибла в междоусобице"), old_ruler.sex))
    polity.ruler_id = ""
    choice = HeirChoice(leader, "узурпатор", other_house=True,
                        law=polity.succession)
    succession.enthrone(ctx, polity, leader, date, year, choice,
                        legitimacy="узурпация", old_house=old_house, rng=rng,
                        announce=False)


def _war_toll(ctx, polity, length: int, rng) -> None:
    """Междоусобица дорого обходится городам, за которые дерутся."""
    world = ctx.world
    share = min(0.22, 0.015 * length)
    for settlement in _live_cities(world, polity):
        loss = int(settlement.population * share * rng.uniform(0.4, 1.4))
        settlement.population = max(40, settlement.population - loss)
    world.refresh_populations()


def _secede(ctx, polity, race, house, year: int, rng) -> bool:
    """Род уводит вотчину: часть городов объявляет себя отдельной державой."""
    world = ctx.world
    seat = world.settlements.get(house.seat_id)
    if seat is None or seat.status != ACTIVE or seat.is_capital:
        return False
    if seat.polity_id != polity.id:
        return False
    # Титульным народом новой державы будет народ самого рода, и родовое
    # гнездо должно быть его же: иначе выходит страна, в которой народ
    # её государя не живёт вовсе.
    race = races_mod.get_race(house.race_id)
    if seat.race_id != house.race_id or not race.builds_states:
        return False

    # Вотчина — родовое гнездо и соседние города той же земли.
    cities = [seat]
    for settlement in _live_cities(world, polity):
        if settlement.id == seat.id or settlement.is_capital:
            continue
        if settlement.region_id == seat.region_id and rng.chance(0.7):
            cities.append(settlement)
    if len(_live_cities(world, polity)) - len(cities) < 1:
        return False

    leaders = house_adults(world, house, race, year)
    leader = world.figures.get(house.head_id)
    if leader is None or not leader.alive_at(year):
        leader = leaders[0] if leaders else None
    if leader is None:
        return False

    date = ctx.date_in(rng, year)
    form = rng.choice(race.polity_words or ("Владение",))
    new_polity = world.add_polity(
        name=ctx.forge.polity(rng, race), form=form, race_id=race.id,
        founded=date, founder_id=leader.id, capital_id=seat.id,
        ruler_id="", region_ids=[], settlement_ids=[],
        predecessor_id=polity.id)
    for settlement in cities:
        if settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)
        settlement.polity_id = new_polity.id
        settlement.is_capital = settlement.id == seat.id
        new_polity.settlement_ids.append(settlement.id)
        if settlement.region_id not in new_polity.region_ids:
            new_polity.region_ids.append(settlement.region_id)

    houses_mod.detach(world, house, polity)
    house.discontent = 0.0
    house.charters = 0
    succession.install_founder(ctx, new_polity, leader, seat, date, year)
    world.refresh_populations()

    title, text = texts.secession(rng, polity, house, new_polity)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="house_secession",
        title=title, text=text, importance=4, actors=[leader.id],
        subjects=[house.id, polity.id, new_polity.id],
        region_id=seat.region_id, race_id=race.id)
    if not _live_cities(world, polity):
        world.end_polity(polity, date, "растащена вотчинами")
    return True
