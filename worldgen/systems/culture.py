# -*- coding: utf-8 -*-
"""Ассимиляция: как народы растворяются друг в друге.

Завоевание кончается не миром. Через три поколения внуки побеждённых
говорят на языке победителей — или, наоборот, двор победителя переходит
на здешнюю речь, потому что здешних вдесятеро больше. Иногда из двух
народов выходит третий, которого своим не считают ни те ни эти.

Что здесь решается раз в десятилетие для каждой многонародной державы:

1. **Тяга.** Сколько весит язык двора: доля титульного народа, письмо,
   богатство, годы под одной короной.
2. **Упор.** Сколько весит своё: доля меньшинства, накопленная обида,
   иная раса, отдельная вера, дальняя земля.
3. **Исход.** Растворение меньшинства, переход двора на здешнюю речь,
   рождение смешанного народа или запрет чужой речи указом.

Ничего из этого не случается быстро: сроки здесь мерятся не годами, а
поколениями, и обиду запрет оставляет такую, что она переживёт державу.
"""

from __future__ import annotations

from . import tongues as tongues_mod
from .. import folk as folk_mod
from .. import history
from .. import narrative_culture as texts
from .. import nations as pol
from .. import races as races_mod
from ..models import ACTIVE

MIN_YEARS = 120            # раньше этого срока никто никого не переваривает
BLEND_RATE = 0.10          # годится ли этот такт для растворения
NATIVE_SHARE = 0.22        # доля титульных, ниже которой двор переходит
NATIVE_RATE = 0.08
BAN_RATE = 0.06
MIX_SHARE = 0.12           # изредка растворение даёт новый народ
MIX_MIN_CITY = 600         # в малом посаде новому народу не из кого взяться
GRIEVANCE_BAN = 0.3        # сколько обиды добавляет запрет речи

# Почему перенимают чужую речь.
WHYS = ("торг", "двор", "вера", "брак", "закон", "время")


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("culture", year)
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        if year - polity.founded.year < MIN_YEARS:
            continue
        if not polity.multiethnic:
            continue
        _digest(ctx, polity, year, period, rng)


def _digest(ctx, polity, year: int, period: int, rng) -> None:
    world = ctx.world
    share = polity.share_of(polity.race_id)
    scale = period / 10.0

    # Двор среди чужих: если своих осталась горсть, переходит на здешнюю речь.
    if share < NATIVE_SHARE and rng.chance(NATIVE_RATE * scale):
        if _go_native(ctx, polity, year, rng):
            return

    minorities = polity.minorities()
    if not minorities:
        return
    race_id, souls = minorities[0]
    anger = polity.grievance.get(race_id, 0.0)

    # Указ о единой речи: жестокая держава торопит то, что и так идёт.
    if pol.is_harsh(polity.policy) and rng.chance(BAN_RATE * scale):
        if _forbid(ctx, polity, race_id, year, rng):
            return

    weight = _pull(world, polity, share) - _resist(world, polity, race_id,
                                                   anger, year)
    if weight <= 0:
        return
    if not rng.chance(min(0.6, BLEND_RATE * scale * weight)):
        return
    if rng.chance(MIX_SHARE):
        _blend_folks(ctx, polity, race_id, year, rng)
    else:
        _assimilate(ctx, polity, race_id, year, rng)


def _pull(world, polity, share: float) -> float:
    """Насколько тяжело весит язык двора."""
    value = 0.4 + 1.2 * share
    tongue = world.tongues.get(polity.tongue_id)
    if tongue is not None and tongue.script:
        value += 0.25               # у письменной речи выгода очевидна
    if polity.policy == pol.EQUAL:
        value += 0.1
    value += min(0.4, len(polity.known) / 60.0)
    return value


def _resist(world, polity, race_id: str, anger: float, year: int) -> float:
    """И насколько упорно держатся за своё."""
    value = 0.3 + 1.1 * polity.share_of(race_id) + 0.9 * anger
    race = races_mod.RACES_BY_ID.get(race_id)
    titular = races_mod.RACES_BY_ID.get(polity.race_id)
    if race is not None and titular is not None:
        if race.category != titular.category:
            value += 0.3            # чужая кровь мешается медленнее
        if race.is_evil != titular.is_evil:
            value += 0.2
    value += 0.5 * min(1.0, history.power(world, polity.id, history.GRUDGE,
                                          year, race_id))
    return value


# ---------------------------------------------------------------------------
# Исходы
# ---------------------------------------------------------------------------

def _minority_cities(world, polity, race_id: str) -> list:
    out = []
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        if settlement.race_id == race_id:
            out.append(settlement)
    return out


def _host_folk(world, polity):
    """Народ двора — тот, чьим языком пишут грамоты."""
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        if settlement.race_id != polity.race_id:
            continue
        folk = world.folks.get(settlement.folk_id)
        if folk is not None and folk.status == ACTIVE:
            return folk
    return None


def _assimilate(ctx, polity, race_id: str, year: int, rng) -> bool:
    """Город меньшинства перенимает речь и обычаи двора.

    Кровь при этом не меняется: город остаётся городом своего народа.
    Если двор той же крови, два народа сливаются в один; если крови
    разной — сливается только речь, а народ остаётся при своём имени.
    Дворф не становится эльфом оттого, что заговорил по-эльфийски.
    """
    world = ctx.world
    cities = _minority_cities(world, polity, race_id)
    if not cities:
        return False
    city = rng.choice(sorted(cities, key=lambda item: item.id))
    folk = world.folks.get(city.folk_id)
    host = _host_folk(world, polity)
    if host is None or folk is None or folk.id == host.id:
        return False

    if host.race_id == folk.race_id:
        city.folk_id = host.id           # свои со своими сливаются целиком
    else:
        tongue = world.tongues.get(host.tongue_id)
        if tongue is None or folk.tongue_id == tongue.id:
            return False                 # перенимать уже нечего
        old_tongue = world.tongues.get(folk.tongue_id)
        if old_tongue is not None and folk.id in old_tongue.folk_ids:
            old_tongue.folk_ids.remove(folk.id)
        tongues_mod.attach(world, tongue, folk)
        folk.notes.append("%d: перенял речь народа по имени %s"
                          % (year, host.name))
    why = "закон" if pol.is_harsh(polity.policy) else rng.choice(WHYS)
    date = ctx.date_in(rng, year)
    title, text = texts.blended(rng, folk, host, city, why)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="assimilation",
        title=title, text=text, importance=2,
        subjects=[polity.id, folk.id, city.id],
        region_id=city.region_id, race_id=race_id,
        trace=history.trace_of(2))
    # Растворение оставляет след: народ помнит, что когда-то говорил иначе.
    history.leave(world, history.SCAR, year, city.id, weight=0.4,
                  place_id=city.id, event_id=event.id,
                  note="город по имени %s переменил речь" % city.name)
    world.refresh_folks()
    return True


def _go_native(ctx, polity, year: int, rng) -> bool:
    """Двор переходит на язык покорённых: их попросту больше."""
    world = ctx.world
    minorities = polity.minorities()
    if not minorities:
        return False
    race_id = minorities[0][0]
    cities = _minority_cities(world, polity, race_id)
    if not cities:
        return False
    folk = world.folks.get(cities[0].folk_id)
    if folk is None or not folk.tongue_id:
        return False
    old = world.tongues.get(polity.tongue_id)
    new = world.tongues.get(folk.tongue_id)
    if new is None or (old is not None and old.id == new.id):
        return False

    polity.tongue_id = new.id
    date = ctx.date_in(rng, year)
    title, text = texts.went_native(rng, polity, old, new)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="court_tongue",
        title=title, text=text, importance=3,
        subjects=[polity.id, new.id], race_id=polity.race_id,
        region_id=polity.region_ids[0] if polity.region_ids else "",
        trace=history.trace_of(3))
    polity.notes.append("%d: двор перешёл на язык по имени %s"
                        % (year, new.name))
    return True


def _forbid(ctx, polity, race_id: str, year: int, rng) -> bool:
    """Указ о единой речи: чужой язык объявляют речью мятежников."""
    world = ctx.world
    cities = _minority_cities(world, polity, race_id)
    if not cities:
        return False
    folk = world.folks.get(cities[0].folk_id)
    tongue = world.tongues.get(folk.tongue_id) if folk is not None else None
    if tongue is None or tongue.id == polity.tongue_id:
        return False
    if any(note.startswith("запрет речи: %s" % tongue.id)
           for note in polity.notes):
        return False

    polity.notes.append("запрет речи: %s (%d год)" % (tongue.id, year))
    polity.grievance[race_id] = min(1.0, polity.grievance.get(race_id, 0.0)
                                    + GRIEVANCE_BAN)
    date = ctx.date_in(rng, year)
    title, text = texts.forbidden(rng, polity, tongue)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="tongue_ban",
        title=title, text=text, importance=3,
        subjects=[polity.id, tongue.id], race_id=race_id,
        region_id=cities[0].region_id, trace=history.trace_of(3))
    tongue.notes.append("под запретом в державе по имени %s с %d года"
                        % (polity.name, year))
    # Запрет речи помнят дольше, чем самого государя: это обида народа,
    # и однажды она поднимет его.
    fact = history.leave(world, history.GRUDGE, year, polity.id, race_id,
                         weight=0.7, event_id=event.id,
                         note="запрет родной речи")
    history.plant(world, "восстание", year, year + rng.randint(30, 220),
                  window=200, fact_id=fact.id if fact is not None else "",
                  event_id=event.id, holder_id=polity.id, about_id=race_id,
                  place_id=cities[0].id, chance=0.35,
                  note="запрещённая речь")
    return True


def _blend_folks(ctx, polity, race_id: str, year: int, rng) -> bool:
    """Из двух народов выходит третий — не свой ни тем ни этим."""
    world = ctx.world
    cities = _minority_cities(world, polity, race_id)
    if not cities:
        return False
    cities = [item for item in cities if item.population >= MIX_MIN_CITY]
    if not cities:
        return False
    city = rng.choice(sorted(cities, key=lambda item: item.id))
    first = world.folks.get(city.folk_id)
    second = _host_folk(world, polity)
    if first is None or second is None or first.id == second.id:
        return False
    race = races_mod.RACES_BY_ID.get(race_id)
    region = world.regions.get(city.region_id)
    if race is None:
        return False

    used = {item.name for item in world.folks.values()}
    name, kind = "", ""
    for _ in range(10):
        name, kind = folk_mod.folk_name(rng, race, region, used)
        if name not in used:
            break
    else:
        return False                     # имени не нашлось — и народа не будет
    if name in used:
        return False
    date = ctx.date_in(rng, year)
    folk = world.add_folk(
        name=name, name_kind=kind, race_id=race_id,
        cradle_region=city.region_id, born=date,
        traits=list(first.traits)[:2] + list(second.traits)[:1],
        parent_id=first.id)
    # Говорит смешанный народ на речи большинства, но помнит обе.
    tongue = world.tongues.get(second.tongue_id) or \
        world.tongues.get(first.tongue_id)
    tongues_mod.attach(world, tongue, folk)
    folk.notes.append("вышел из народов по имени %s и %s"
                      % (first.name, second.name))
    city.folk_id = folk.id

    title, text = texts.mixed(rng, folk, city, first, second)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="folk_blend",
        title=title, text=text, importance=3,
        subjects=[folk.id, polity.id, city.id],
        region_id=city.region_id, race_id=race_id,
        trace=history.trace_of(3))
    world.refresh_folks()
    return True
