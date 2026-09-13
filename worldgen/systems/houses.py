# -*- coding: utf-8 -*-
"""Знатные роды: рождение, возвышение, младшие ветви и угасание.

Род заводит тот, кто основал город или страну: его потомки носят общее
родовое имя. У простолюдинов фамилии нет — она и есть знак знатности.

У каждой расы свои обычаи: люди заводят дома, дворфы — кланы, волколюды —
стаи, птицелюды — гнёзда. Зверолюды и злые расы знати не знают вовсе.
"""

from __future__ import annotations

from .. import narrative_dynasty as texts
from .. import races as races_mod
from ..models import ACTIVE, EXTINCT, GREAT, MINOR, ROYAL

CADET_CHANCE = 0.012          # шанс отделения младшей ветви за проверку
PRESTIGE_DECAY = 0.06         # престиж без подпитки сползает к единице


def found_house(ctx, figure, year: int, date, seat=None, rank: str = MINOR,
                polity=None, parent=None, announce: bool = True,
                importance: int = 2):
    """Заводит новый род во главе с указанной личностью."""
    world = ctx.world
    race = races_mod.get_race(figure.race_id)
    if not race.has_nobility:
        return None
    if figure.house_id:
        return world.houses.get(figure.house_id)

    rng = ctx.rng("house", year, figure.id)
    house = world.add_house(
        name=ctx.forge.house(rng, race), word=rng.choice(race.house_words),
        race_id=race.id, founded=date, founder_id=figure.id,
        seat_id=seat.id if seat is not None else "",
        rank=rank, head_id=figure.id,
        parent_id=parent.id if parent is not None else "",
        prestige=1.0 + (1.5 if rank == ROYAL else 0.0),
    )
    _join(world, figure, house)
    if polity is not None:
        attach(world, house, polity)

    if announce:
        if parent is not None:
            title, text = texts.cadet_branch(rng, house, parent, figure)
            kind = "house_cadet"
        else:
            title, text = texts.house_found(rng, house, figure, seat, race)
            kind = "house_found"
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind=kind,
            title=title, text=text, importance=importance, actors=[figure.id],
            subjects=[house.id] + ([seat.id] if seat is not None else []),
            region_id=seat.region_id if seat is not None else figure.origin_region,
            race_id=race.id,
        )
    return house


def _join(world, figure, house) -> None:
    """Принимает личность в род: фамилия, знатность, учёт."""
    figure.house_id = house.id
    figure.surname = house.name
    figure.noble = True
    if figure.id not in house.members:
        house.members.append(figure.id)
        house.living.append(figure.id)
        house.alive_count = len(house.living)


def attach(world, house, polity) -> None:
    house.polity_id = polity.id
    if house.id not in polity.house_ids:
        polity.house_ids.append(house.id)


def detach(world, house, polity) -> None:
    if polity is not None and house.id in polity.house_ids:
        polity.house_ids.remove(house.id)
    if house.polity_id == (polity.id if polity is not None else ""):
        house.polity_id = ""


def make_royal(ctx, house, polity, year: int, date, announce: bool = True) -> None:
    """Возводит род в правящую династию страны."""
    world = ctx.world
    previous = world.houses.get(polity.house_id)
    if previous is not None and previous.id != house.id and previous.rank == ROYAL:
        previous.rank = GREAT
    house.rank = ROYAL
    house.thrones += 1
    house.prestige += 2.5
    polity.house_id = house.id
    attach(world, house, polity)
    if announce:
        rng = ctx.rng("royal", year, house.id)
        title, text = texts.house_royal(rng, house, polity)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="house_royal",
            title=title, text=text, importance=3,
            subjects=[house.id, polity.id], race_id=house.race_id,
        )


# ---------------------------------------------------------------------------
# Смерть члена рода
# ---------------------------------------------------------------------------

def note_death(ctx, figure, date, year: int) -> None:
    """Учитывает смерть знатного лица: глава рода, пресечение рода."""
    world = ctx.world
    house = world.houses.get(figure.house_id)
    if house is None or house.status != ACTIVE:
        return
    if figure.id in house.living:
        house.living.remove(figure.id)
    house.alive_count = len(house.living)

    if house.head_id == figure.id:
        heir = _next_head(world, house, year)
        house.head_id = heir.id if heir is not None else ""

    if world.house_members(house, alive_in_year=year + 1):
        return

    rng = ctx.rng("house_end", year, house.id)
    world.end_house(house, date, "не осталось наследников", EXTINCT)
    # Малые роды угасают постоянно — о них летопись молчит.
    if house.rank == MINOR and house.thrones == 0 and not rng.chance(0.12):
        return
    title, text = texts.house_extinct(rng, house, figure)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="house_extinct",
        title=title, text=text,
        importance=3 if (house.rank == ROYAL or house.thrones) else 2,
        actors=[figure.id], subjects=[house.id], race_id=house.race_id,
    )


def _next_head(world, house, year: int):
    race = races_mod.get_race(house.race_id)
    people = [f for f in world.house_members(house, alive_in_year=year)
              if f.age_at(year) >= race.adulthood]
    if not people:
        people = world.house_members(house, alive_in_year=year)
    if not people:
        return None
    if race.succession == races_mod.MATRILINEAL:
        women = [f for f in people if f.sex == "f"]
        people = women or people
    people.sort(key=lambda f: (f.birth.ordinal, f.id))
    return people[0]


# ---------------------------------------------------------------------------
# Медленные процессы
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    """Престиж родов и отделение младших ветвей."""
    world = ctx.world
    rng = ctx.rng("house_upkeep", year)

    for house_id in list(world.active_houses):
        house = world.houses[house_id]
        race = races_mod.get_race(house.race_id)

        # Престиж тянется к единице, но трон и города держат его наверху.
        target = 1.0 + 0.6 * house.thrones
        seat = world.settlements.get(house.seat_id)
        if seat is not None and seat.status == ACTIVE:
            target += 0.4
        else:
            target -= 0.3
            house.seat_id = ""      # родовое гнездо потеряно
        house.prestige += (target - house.prestige) * PRESTIGE_DECAY * (period / 10.0)
        house.prestige = max(0.15, min(12.0, house.prestige))

        # Младшая ветвь: у большого рода младшие дети заводят свой дом.
        if house.alive_count >= 4 and rng.chance(CADET_CHANCE * (period / 10.0)):
            _split_cadet(ctx, house, race, year, rng)


def _split_cadet(ctx, house, race, year: int, rng) -> None:
    world = ctx.world
    people = [f for f in world.house_members(house, alive_in_year=year)
              if f.age_at(year) >= race.adulthood and f.id != house.head_id]
    if not people:
        return
    people.sort(key=lambda f: (-f.birth.ordinal, f.id))     # младшие первыми
    founder = people[0]

    polity = world.polities.get(house.polity_id)
    seat = None
    if polity is not None:
        free = [world.settlements[sid] for sid in polity.settlement_ids
                if sid in world.settlements
                and world.settlements[sid].status == ACTIVE]
        free = [s for s in free if s.id != house.seat_id]
        if free:
            seat = rng.choice(sorted(free, key=lambda s: s.id))

    # Уходя, основатель уносит фамилию: его учёт переходит в новый род.
    house.alive_count = max(0, house.alive_count - 1)
    if founder.id in house.members:
        house.members.remove(founder.id)
    founder.house_id = ""
    founder.surname = ""

    date = ctx.date_in(rng, year)
    found_house(ctx, founder, year, date, seat=seat, rank=MINOR,
                polity=polity, parent=house, importance=2)
