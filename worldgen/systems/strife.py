# -*- coding: utf-8 -*-
"""Смуты: война державы с самой собой.

Прежде междоусобица решалась одним броском: дом поднимался, и тут же
становилось известно, чем всё кончилось. Теперь у смуты есть то же, что
и у войны с соседом, — стороны, города, годы и перебежчики, — но идёт
она иначе, потому что обе стороны свои.

Порядок такой:

1. **Причина.** Спор наследников, раскол веры, борьба знати, сепаратизм
   окраин, голодный бунт, мятеж неоплаченного войска, ночной переворот
   или города, не желающие платить новый сбор.
2. **Раздел.** Держава делится надвое не по случайности: за мятежом идут
   города вокруг родового гнезда вожака, за короной — столица и те, кто
   от неё близко.
3. **Годы.** Каждый год — стычка, переход города на другую сторону или
   просто убыль людей. Войско, которому не платят, уходит к тому, кто
   платит.
4. **Исход.** Корона удерживается, престол переходит к мятежнику,
   держава раскалывается надвое или стороны садятся за стол, потому что
   воевать больше нечем.

Пока смута идёт, держава не начинает войн с соседями: ей не до них.
"""

from __future__ import annotations

from . import memory as memory_sys
from . import succession
from .. import dynasty
from .. import history
from .. import narrative
from .. import narrative_strife as texts
from .. import races as races_mod
from .. import recall
from .. import rulers as rulers_mod
from ..models import ACTIVE, ONGOING
from ..world import RURAL_FACTOR

# Причины смуты.
HEIRS = "спор наследников"
FAITH = "раскол веры"
NOBLES = "борьба знати"
BREAKAWAY = "сепаратизм"
RIOT = "бунт"
MUTINY = "мятеж войска"
COUP = "переворот"
TOWNS = "города против короны"

CAUSES = (HEIRS, FAITH, NOBLES, BREAKAWAY, RIOT, MUTINY, COUP, TOWNS)

MIN_CITIES = 3             # с двумя городами делить нечего
CLASH_RATE = 0.55          # как часто год смуты приносит стычку
TURN_RATE = 0.22           # как часто город меняет сторону
TOLL = (0.01, 0.05)        # какую долю душ съедает год смуты
MAX_YEARS = 40             # дольше этого не воюют — договариваются
TALK_AFTER = 10            # с какого года смуты садятся за стол
TALK_RATE = 0.09           # и как часто после этого договариваются
ZEAL = (1.15, 1.55)        # мятеж силён не числом, а решимостью
WEARY_STEP = 0.07
START_RATE = 0.012         # годовая вероятность при полной напряжённости


# ---------------------------------------------------------------------------
# Где зреет
# ---------------------------------------------------------------------------

def tension(ctx, polity, year: int) -> tuple:
    """Насколько держава близка к смуте и по какой причине."""
    world = ctx.world
    rows = []

    reign = world.current_reign(polity)
    if polity.interregnum:
        rows.append((HEIRS, 1.3))
    elif reign is not None and reign.legitimacy == "узурпация" \
            and year - reign.start.year < 60:
        rows.append((COUP, 0.9))
    # Обойдённые престолом ждут своего часа.
    passed = 0
    house = world.houses.get(polity.house_id)
    if house is not None:
        for figure_id in house.living[-12:]:
            figure = world.figures.get(figure_id)
            if figure is None or not figure.alive_at(year):
                continue
            if world.memories_of(figure.id, recall.PASSED_OVER):
                passed += 1
    if passed:
        rows.append((HEIRS, 0.5 + 0.4 * min(3, passed)))

    angry = [item for item in world.houses_of_polity(polity)
             if item.status == ACTIVE and item.id != polity.house_id
             and item.discontent >= 0.5]
    if angry:
        rows.append((NOBLES, 0.6 + 0.5 * min(4, len(angry))))

    # Вера: в державе служат двум алтарям.
    faiths = {}
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        if settlement.faith_id:
            faiths[settlement.faith_id] = faiths.get(settlement.faith_id, 0) + 1
    if polity.faith_id and len(faiths) > 1:
        others = sum(count for key, count in faiths.items()
                     if key != polity.faith_id)
        if others >= 2:
            rows.append((FAITH, 0.4 + 0.25 * min(5, others)))

    if polity.hunger > 0.3:
        rows.append((RIOT, 0.5 + 1.2 * polity.hunger))
    if polity.weariness > 0.6 and world.wars_of(polity, only_active=True):
        rows.append((MUTINY, 0.4 + 0.8 * polity.weariness))
    elif polity.weariness > 0.7:
        rows.append((MUTINY, 0.3 + 0.6 * polity.weariness))

    live = _live_cities(world, polity)
    if len(live) >= 6:
        far = [item for item in live
               if item.region_id not in polity.region_ids[:1]]
        if len(far) >= 3:
            rows.append((BREAKAWAY, 0.3 + 0.1 * min(6, len(far))))
    wealthy = [item for item in live if item.population > 1400]
    if len(wealthy) >= 2 and world.guilds_of(polity):
        rows.append((TOWNS, 0.3 + 0.2 * len(world.guilds_of(polity))))

    # Чужое серебро при дворе подогревает любую из причин.
    if polity.intrigue > 0.2 and rows:
        rows.append((rows[0][0], 0.8 * polity.intrigue))

    if not rows:
        return "", 0.0
    best = max(rows, key=lambda pair: pair[1])
    total = sum(weight for _, weight in rows)
    return best[0], total


def upkeep(ctx, year: int, period: int) -> None:
    """Раз в десятилетие смотрим, где держава вот-вот треснет."""
    world = ctx.world
    rng = ctx.rng("strife", year)
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        if world.strife_of(polity) is not None:
            continue
        if len(_live_cities(world, polity)) < MIN_CITIES:
            continue
        cause, heat = tension(ctx, polity, year)
        if not cause or heat < 0.8:
            continue
        chance = ctx.rate(START_RATE) * heat * (period / 10.0)
        chance /= max(0.5, rulers_mod.court_grip(world, polity))
        if not rng.chance(min(0.6, chance)):
            continue
        start(ctx, polity, cause, year, rng)


# ---------------------------------------------------------------------------
# Начало
# ---------------------------------------------------------------------------

def _live_cities(world, polity) -> list:
    return [world.settlements[sid] for sid in polity.settlement_ids
            if sid in world.settlements
            and world.settlements[sid].status == ACTIVE]


def _pick_rebel(ctx, polity, cause: str, year: int, rng, house=None):
    """Кто поднимает знамя."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    if house is not None:
        people = dynasty.house_adults(world, house, race, year)
        if people:
            return people[0], house

    if cause in (HEIRS, COUP):
        crown = world.houses.get(polity.house_id)
        if crown is not None:
            for figure_id in reversed(crown.living):
                figure = world.figures.get(figure_id)
                if figure is None or not figure.alive_at(year):
                    continue
                if figure.id == polity.ruler_id:
                    continue
                if world.memories_of(figure.id, recall.PASSED_OVER) \
                        or dynasty.is_adult(figure, race, year):
                    return figure, crown
    if cause == NOBLES:
        angry = [item for item in world.houses_of_polity(polity)
                 if item.status == ACTIVE and item.id != polity.house_id]
        angry.sort(key=lambda item: (-item.discontent, item.id))
        for item in angry[:3]:
            people = dynasty.house_adults(world, item, race, year)
            if people:
                return people[0], item

    # Прочие причины поднимают тех, у кого имени ещё нет: воеводу,
    # проповедника, городского старшину, вожака голодных.
    role = {FAITH: "проповедник", RIOT: "вожак восстания",
            MUTINY: "мятежный воевода", TOWNS: "городской старшина",
            BREAKAWAY: "наместник окраины"}.get(cause, "вожак мятежа")
    cities = _live_cities(world, polity)
    seat = rng.choice(sorted(cities, key=lambda item: item.id)) if cities else None
    sex = "f" if rng.chance(0.35) else "m"
    leader = ctx.make_figure(
        rng, race, year, role=role,
        region_id=seat.region_id if seat is not None else "",
        title=ctx.title_for(race, "chief", sex), sex=sex,
        home_id=seat.id if seat is not None else "", epithet_chance=0.8)
    return leader, None


def _split_cities(world, polity, rebel, house, cause: str, rng) -> tuple:
    """Кто за корону, кто за мятеж."""
    cities = _live_cities(world, polity)
    capital = world.settlements.get(polity.capital_id)
    seat = world.settlements.get(house.seat_id) if house is not None else None
    if seat is None:
        seat = world.settlements.get(rebel.home_id)
    home_region = seat.region_id if seat is not None else ""

    crown, rebels = [], []
    for city in cities:
        if capital is not None and city.id == capital.id and cause != COUP:
            crown.append(city.id)
            continue
        weight = 0.35
        if home_region and city.region_id == home_region:
            weight += 0.45
        if seat is not None and city.id == seat.id:
            weight = 0.95
        if cause == BREAKAWAY and city.region_id != (
                polity.region_ids[0] if polity.region_ids else ""):
            weight += 0.2
        if cause == TOWNS and city.population > 1400:
            weight += 0.25
        if cause == FAITH and city.faith_id and city.faith_id != polity.faith_id:
            weight += 0.35
        (rebels if rng.chance(min(0.9, weight)) else crown).append(city.id)
    if not rebels and cities:
        rebels.append(cities[-1].id)
        crown = [item for item in crown if item != cities[-1].id]
    return crown, rebels


def start(ctx, polity, cause: str, year: int, rng=None, rebel=None,
          house=None, origin_id: str = ""):
    """Поднять смуту. Возвращает запись о ней или None."""
    world = ctx.world
    if world.strife_of(polity) is not None:
        return None
    cities = _live_cities(world, polity)
    if len(cities) < MIN_CITIES:
        return None
    rng = rng or ctx.rng("strife", "start", polity.id, year)
    if rebel is None:
        rebel, house = _pick_rebel(ctx, polity, cause, year, rng, house)
    if rebel is None:
        return None

    crown_cities, rebel_cities = _split_cities(world, polity, rebel, house,
                                               cause, rng)
    if not crown_cities or not rebel_cities:
        return None

    reign = world.current_reign(polity)
    date = ctx.date_in(rng, year, reign.start if reign is not None else None)
    taken = {item.name for item in world.strifes.values()}
    strife = world.add_strife(
        polity_id=polity.id, cause=cause, start=date,
        name=texts.strife_name(rng, cause, polity, taken, year),
        crown_id=polity.ruler_id, rebel_id=rebel.id,
        rebel_house_id=house.id if house is not None else "",
        crown_cities=crown_cities, rebel_cities=rebel_cities,
        origin_id=origin_id)
    strife.crown_power = _power(ctx, polity, crown_cities, world.figures.get(
        polity.ruler_id), year)
    strife.rebel_power = _power(ctx, polity, rebel_cities, rebel, year,
                                house=house) * rng.uniform(*ZEAL)

    crown = world.figures.get(polity.ruler_id)
    title, text = texts.strife_begins(rng, strife, polity, rebel, crown, cause)
    marks = [fact.id for fact in world.facts_of(polity.id, year,
                                                history.HUNGER)[:1]]
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="strife_start",
        title=title, text=text, importance=4,
        actors=[item.id for item in (rebel, crown) if item is not None],
        subjects=[strife.id, polity.id], race_id=polity.race_id,
        region_id=polity.region_ids[0] if polity.region_ids else "",
        causes=[origin_id] if origin_id else [], facts=marks,
        trace=history.trace_of(4))
    strife.origin_id = event.id
    memory_sys.remember(ctx, rebel, recall.COURT_FEUD, year,
                        about_id=polity.id, weight=0.8, event_id=event.id,
                        note="поднял знамя против короны", told=True)
    return strife


def _power(ctx, polity, city_ids, leader, year: int, house=None) -> float:
    """Сила стороны: люди, воевода и деньги дома."""
    world = ctx.world
    souls = 0
    for city_id in city_ids:
        city = world.settlements.get(city_id)
        if city is not None and city.status == ACTIVE:
            souls += world.settlement_realm(city)
    value = (souls / 1000.0) ** 0.6
    if leader is not None:
        value *= 0.7 + 0.15 * float((leader.skills or {}).get("война", 2))
    if house is not None:
        value *= 0.8 + 0.25 * house.wealth
    return max(0.2, value)


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    world = ctx.world
    for strife_id in list(world.active_strifes):
        strife = world.strifes.get(strife_id)
        if strife is None or strife.status != ONGOING:
            continue
        polity = world.polities.get(strife.polity_id)
        if polity is None or polity.status != ACTIVE:
            world.end_strife(strife, ctx.date_in(
                ctx.rng("strife", strife.id, year), year), "державы не стало")
            continue
        if strife.start.year == year:
            continue                # в первый год только собираются
        _year(ctx, strife, polity, year)


def _year(ctx, strife, polity, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("strife", strife.id, year)
    crown_leader = world.figures.get(strife.crown_id) or \
        world.figures.get(polity.ruler_id)
    rebel = world.figures.get(strife.rebel_id)

    # Вожак может умереть своей смертью — и тогда смута кончается сама.
    if rebel is None or not rebel.alive_at(year):
        _finish(ctx, strife, polity, year, "корона удержалась", rng)
        return
    if crown_leader is None or not crown_leader.alive_at(year):
        strife.crown_id = polity.ruler_id

    city, winner, turned = None, "", None
    if rng.chance(CLASH_RATE):
        city, winner = _clash(ctx, strife, polity, year, rng)
    if rng.chance(TURN_RATE):
        turned = _turncoat(ctx, strife, polity, year, rng)

    strife.deaths += _toll(ctx, strife, polity, rng)
    polity.weariness = min(1.0, polity.weariness + WEARY_STEP)

    if city is not None or turned is not None:
        title, text = texts.strife_year(rng, strife, city, winner or "crown",
                                        turned)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="strife_year", title=title, text=text, importance=2,
            subjects=[strife.id, polity.id], race_id=polity.race_id,
            causes=[strife.origin_id] if strife.origin_id else [])

    if not strife.rebel_cities:
        _finish(ctx, strife, polity, year, "корона удержалась", rng)
        return
    if not strife.crown_cities:
        _finish(ctx, strife, polity, year, "престол взят", rng)
        return
    # Затянувшуюся смуту чаще кончают переговорами, чем победой: воевать
    # своих дорого, и обе стороны это понимают раньше, чем сдаются.
    span = year - strife.start.year
    if span >= TALK_AFTER and len(strife.rebel_cities) >= 2 \
            and len(strife.crown_cities) >= 2:
        weary = TALK_RATE * (1.0 + span / 40.0)
        if rng.chance(min(0.5, weary)):
            _finish(ctx, strife, polity, year, _tired_end(strife, rng), rng)
            return
    if span >= MAX_YEARS:
        _finish(ctx, strife, polity, year, _tired_end(strife, rng), rng)


def _clash(ctx, strife, polity, year: int, rng) -> tuple:
    """Стычка под чьими-нибудь стенами."""
    world = ctx.world
    pool = strife.rebel_cities + strife.crown_cities
    city = None
    for city_id in rng.shuffled(pool):
        found = world.settlements.get(city_id)
        if found is not None and found.status == ACTIVE:
            city = found
            break
    if city is None:
        return None, ""
    edge = strife.crown_power / max(0.2, strife.crown_power + strife.rebel_power)
    crown_wins = rng.chance(max(0.15, min(0.85, edge)))
    if crown_wins:
        strife.rebel_power = max(0.2, strife.rebel_power * rng.uniform(0.72, 0.93))
        if city.id in strife.rebel_cities and rng.chance(0.3):
            strife.rebel_cities.remove(city.id)
            strife.crown_cities.append(city.id)
            strife.turns.append([year, city.id, "корона"])
    else:
        strife.crown_power = max(0.2, strife.crown_power * rng.uniform(0.72, 0.93))
        if city.id in strife.crown_cities and rng.chance(0.3):
            strife.crown_cities.remove(city.id)
            strife.rebel_cities.append(city.id)
            strife.turns.append([year, city.id, "мятеж"])
    return city, "crown" if crown_wins else "rebel"


def _turncoat(ctx, strife, polity, year: int, rng):
    """Город переходит к тому, кто побеждает."""
    world = ctx.world
    winning = strife.crown_power >= strife.rebel_power
    donor = strife.rebel_cities if winning else strife.crown_cities
    taker = strife.crown_cities if winning else strife.rebel_cities
    if len(donor) < 2:
        return None
    city_id = rng.choice(sorted(donor))
    city = world.settlements.get(city_id)
    if city is None or city.status != ACTIVE:
        return None
    donor.remove(city_id)
    taker.append(city_id)
    strife.turns.append([year, city_id, "корона" if winning else "мятеж"])
    return city


def _toll(ctx, strife, polity, rng) -> int:
    """Смута съедает людей и там, где не дерутся."""
    world = ctx.world
    dead = 0
    share = rng.uniform(*TOLL)
    for city_id in strife.crown_cities + strife.rebel_cities:
        city = world.settlements.get(city_id)
        if city is None or city.status != ACTIVE:
            continue
        loss = int(city.population * share * rng.uniform(0.5, 1.5))
        if loss <= 0:
            continue
        city.population = max(40, city.population - loss)
        dead += int(loss * RURAL_FACTOR)
    world.refresh_populations()
    return dead


def _tired_end(strife, rng) -> str:
    """Чем кончается смута, которую никто не выиграл."""
    rebels, crown = len(strife.rebel_cities), len(strife.crown_cities)
    if rebels >= 2 and rebels >= crown * 0.6 and rng.chance(0.55):
        return "держава раскололась"
    return "мир сторон"


# ---------------------------------------------------------------------------
# Исход
# ---------------------------------------------------------------------------

def _finish(ctx, strife, polity, year: int, outcome: str, rng) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year, strife.start
                       if strife.start.year == year else None)
    rebel = world.figures.get(strife.rebel_id)
    new_polity = None

    if outcome == "корона удержалась":
        _crown_wins(ctx, strife, polity, rebel, year, date, rng)
    elif outcome == "престол взят":
        _rebel_wins(ctx, strife, polity, rebel, year, date, rng)
    elif outcome == "держава раскололась":
        new_polity = _split(ctx, strife, polity, rebel, year, date, rng)
        if new_polity is None:
            outcome = "мир сторон"
            _settled(ctx, strife, polity, year)
    else:
        _settled(ctx, strife, polity, year)

    world.end_strife(strife, date, outcome)
    if new_polity is not None:
        strife.heir_polity_id = new_polity.id
    title, text = texts.strife_ends(rng, strife, polity, outcome,
                                    strife.deaths, new_polity)
    subjects = [strife.id, polity.id]
    if new_polity is not None:
        subjects.append(new_polity.id)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="strife_end",
        title=title, text=text, importance=4, subjects=subjects,
        race_id=polity.race_id,
        causes=[strife.origin_id] if strife.origin_id else [],
        trace=history.trace_of(4, extra=0.1))
    # Смуту помнят дольше, чем войну с соседом: свои своих не прощают.
    history.leave(world, history.SCAR, year, polity.id, weight=0.8,
                  note="смута по имени %s" % strife.name, event_id=event.id)
    history.leave(world, history.SHAME, year, polity.id, weight=0.5,
                  note="держава воевала сама с собой", event_id=event.id)
    for other in world.houses_of_polity(polity):
        other.discontent = max(0.0, other.discontent * 0.4)
    polity.weariness = min(1.0, polity.weariness + 0.2)


def _crown_wins(ctx, strife, polity, rebel, year: int, date, rng) -> None:
    world = ctx.world
    if rebel is not None and rebel.alive_at(year):
        rebel.death_cause = "казнён после смуты"
        world.schedule_death(rebel, date, narrative.fate(
            ("казнён после смуты", "казнена после смуты"), rebel.sex))
    house = world.houses.get(strife.rebel_house_id)
    if house is not None:
        house.discontent = 0.0
        house.prestige = max(0.15, house.prestige * 0.45)
        house.wealth = max(0.2, house.wealth * 0.6)
    for city_id in strife.rebel_cities:
        if city_id not in strife.crown_cities:
            strife.crown_cities.append(city_id)
    strife.rebel_cities = []
    # Побеждённая сторона остаётся с обидой: она ещё поднимется.
    fact = history.leave(world, history.GRUDGE, year, polity.id,
                         weight=0.6, note="память о подавленной смуте")
    history.plant(world, "восстание", year, year + rng.randint(40, 260),
                  window=200, fact_id=fact.id if fact is not None else "",
                  event_id=strife.origin_id, holder_id=polity.id,
                  about_id=polity.race_id, chance=0.25,
                  note="недодавленная смута")


def _rebel_wins(ctx, strife, polity, rebel, year: int, date, rng) -> None:
    world = ctx.world
    if rebel is None:
        return
    reign = world.current_reign(polity)
    # Новое правление не может начаться раньше того, которое оно
    # сменяет: если нынешний государь сел на престол в этом же году,
    # день смены отсчитываем от его воцарения.
    if reign is not None and reign.start.year == year \
            and date.ordinal < reign.start.ordinal:
        date = ctx.date_in(rng, year, reign.start)
    old_ruler = world.figures.get(polity.ruler_id)
    old_house = world.houses.get(polity.house_id)
    succession.close_reign(ctx, reign, date, "смута")
    if old_ruler is not None and old_ruler.alive_at(year):
        world.schedule_death(old_ruler, date, narrative.fate(
            ("погиб в смуте", "погибла в смуте"), old_ruler.sex))
    polity.ruler_id = ""
    choice = dynasty.HeirChoice(rebel, "вождь мятежа", other_house=True,
                                law=polity.succession)
    succession.enthrone(ctx, polity, rebel, date, year, choice,
                        legitimacy="узурпация", old_house=old_house, rng=rng,
                        announce=False)
    for city_id in strife.crown_cities:
        if city_id not in strife.rebel_cities:
            strife.rebel_cities.append(city_id)
    strife.crown_cities = []


def _split(ctx, strife, polity, rebel, year: int, date, rng):
    """Стороны расходятся: на карте вместо одной державы две."""
    world = ctx.world
    cities = [world.settlements[cid] for cid in strife.rebel_cities
              if cid in world.settlements
              and world.settlements[cid].status == ACTIVE]
    if len(cities) < 1 or rebel is None:
        return None
    race = races_mod.get_race(rebel.race_id)
    if not race.builds_states:
        return None
    capital = max(cities, key=lambda item: (item.population, item.id))
    new_polity = world.add_polity(
        name=ctx.forge.polity(rng, race), form=rng.choice(
            race.polity_words or ("Вольная Земля",)),
        race_id=race.id, founded=date, founder_id=rebel.id,
        capital_id=capital.id, ruler_id="", region_ids=[], settlement_ids=[],
        predecessor_id=polity.id)
    for city in cities:
        if city.id in polity.settlement_ids:
            polity.settlement_ids.remove(city.id)
        city.polity_id = new_polity.id
        city.is_capital = city.id == capital.id
        new_polity.settlement_ids.append(city.id)
        if city.region_id not in new_polity.region_ids:
            new_polity.region_ids.append(city.region_id)
    if not _live_cities(world, polity):
        world.end_polity(polity, date, "распалась в смуте")
    succession.install_founder(ctx, new_polity, rebel, capital, date, year)
    world.refresh_populations()
    # Две половины одной державы помнят, чем разошлись.
    history.leave(world, history.CLAIM, year, new_polity.id, polity.id,
                  weight=0.7, note="отделились в смуте")
    history.leave(world, history.GRUDGE, year, polity.id, new_polity.id,
                  weight=0.7, note="увели половину державы")
    return new_polity


def _settled(ctx, strife, polity, year: int) -> None:
    """Мир сторон: мятежникам дают то, за чем они шли."""
    world = ctx.world
    house = world.houses.get(strife.rebel_house_id)
    if house is not None:
        house.charters += 1
        house.discontent = max(0.0, house.discontent - 0.5)
        house.prestige = min(12.0, house.prestige + 0.8)
    if strife.cause == RIOT:
        polity.hunger = max(0.0, polity.hunger - 0.2)
    for city_id in strife.rebel_cities:
        if city_id not in strife.crown_cities:
            strife.crown_cities.append(city_id)
    strife.rebel_cities = []
