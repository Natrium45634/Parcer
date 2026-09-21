# -*- coding: utf-8 -*-
"""Переселения народов.

Люди снимаются с места не от хорошей жизни. Голод, война, мор, холода,
теснота, чужой закон — у каждого ухода есть причина, и она уже записана
в мире следами: голодная память державы, рубец земли от бедствия, обида
покорённого народа.

Как это работает:

1. **Давление.** Раз в десятилетие мир смотрит, где тесно, где голодно и
   где беда, и складывает из этого силу, выталкивающую людей с места.
2. **Дорога.** Идут не куда попало: земля должна быть желанной этому
   народу (блок 14), не переполненной и не слишком опасной. Дворфы идут
   в горы, эльфы в леса, люди — туда, где родится хлеб.
3. **Приём.** Пустая земля не отказывает никому. Если же земля чужая,
   принимающая держава решает сама: единокровцев примут охотнее, злой
   народ не примут вовсе, голодная держава не примет никого.
4. **Последствия.** Принятые меняют расовый состав державы и однажды
   вспомнят, чья это была земля. Непринятые оставляют обиду — свою и
   чужую, — которая переживёт всех участников.
"""

from __future__ import annotations

from . import peoples
from .. import demography as demo
from .. import history
from .. import narrative_migration as texts
from .. import races as races_mod
from ..world import RURAL_FACTOR

RATE = 0.30                # как часто за десятилетие мир вообще трогается
MAX_PER_TICK = 2           # сколько переселений разом — больше похоже на хаос
MIN_SOULS = 400            # меньше этого — не переселение, а переезд
LEAVE_SHARE = (0.12, 0.35)  # какую долю уводит исход из города
REFUSED_LOSS = (0.25, 0.6)  # сколько теряют те, кого не приняли
WELCOME_LINE = 0.45        # с какого расположения принимают

# Кто уходит и за море: у прочих дорога кончается берегом.
SEAFARING = ("мореходы", "рыбаки", "китобои", "торговцы", "рыболовы",
             "собиратели прибоя")


# ---------------------------------------------------------------------------
# Медленный такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if len(world.regions) < 3:
        return
    rng = ctx.rng("migration", year)
    if not rng.chance(min(0.9, RATE * period / 10.0)):
        return

    loads = demo.loads(world)
    movers = _who_leaves(ctx, loads, year)
    if not movers:
        return
    for _ in range(rng.randint(1, MAX_PER_TICK)):
        if not movers:
            break
        choice = rng.weighted([(item, item[2]) for item in movers])
        source, cause = choice[0], choice[1]
        movers = [item for item in movers if item[0] is not source]
        _move(ctx, source, cause, loads, year, rng)


def _who_leaves(ctx, loads: dict, year: int) -> list:
    """Кого гонит с места — и насколько сильно."""
    world = ctx.world
    out = []

    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.population < MIN_SOULS:
            continue
        cause, force = _pressure(ctx, tribe.region_id, year, None)
        load = loads.get(tribe.region_id, 1.0)
        if load > demo.TIGHT:
            crowd = 0.75 * (load - demo.TIGHT) * demo.PUSH_WEIGHT[demo.CROWD]
            if crowd > force:
                cause, force = demo.CROWD, crowd
            else:
                force += 0.3 * crowd
        if not cause or force < 0.35:
            continue
        out.append((tribe, cause, force * (tribe.population / 2000.0 + 0.5)))

    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if world.settlement_realm(settlement) < MIN_SOULS * 2:
            continue
        polity = world.polities.get(settlement.polity_id)
        cause, force = _pressure(ctx, settlement.region_id, year, polity,
                                 races_mod.RACES_BY_ID.get(settlement.race_id))
        load = loads.get(settlement.region_id, 1.0)
        if load > demo.TIGHT:
            crowd = 0.6 * (load - demo.TIGHT) * demo.PUSH_WEIGHT[demo.CROWD]
            if crowd > force:
                cause, force = demo.CROWD, crowd
            else:
                force += 0.3 * crowd
        if not cause or force < 0.45:
            continue
        out.append((settlement, cause, force))
    return out


# Беды, от которых бегут как от заразы, а не как от разорения.
PLAGUE_KEYS = ("plague", "great_plague", "blight", "rot", "fever")


def _pressure(ctx, region_id: str, year: int, polity, race=None) -> tuple:
    """Что гонит людей из этой земли и насколько сильно."""
    world = ctx.world
    best, force = "", 0.0

    def add(cause, value):
        nonlocal best, force
        value *= demo.PUSH_WEIGHT.get(cause, 1.0)
        if value > force:
            best, force = cause, value

    for calamity_id in world.active_calamities:
        calamity = world.calamities.get(calamity_id)
        if calamity is None or region_id not in calamity.region_ids:
            continue
        kind = calamity.kind
        if kind == "climate":
            add(demo.COLD, 0.12 * calamity.severity)
        elif calamity.key in PLAGUE_KEYS:
            add(demo.PLAGUE, 0.14 * calamity.severity)
        elif kind == "natural":
            add(demo.RUIN, 0.10 * calamity.severity)
        else:
            add(demo.WAR, 0.10 * calamity.severity)

    gloom = ctx.gloom(region_id)
    if gloom > 0.35:
        # Тёмный век гонит людей, но не так верно, как пустой амбар:
        # иначе все переселения мира оказывались бы от одного и того же.
        add(demo.RUIN, 0.30 * gloom)

    if polity is not None:
        if polity.hunger > 0.2:
            add(demo.HUNGER, 0.9 * polity.hunger)
        if world.wars_of(polity, only_active=True):
            add(demo.WAR, 0.35)
        # Чужой закон гонит вернее голода: уходят с тем, что унесут.
        if race is not None and race.id != polity.race_id:
            from .. import nations as pol
            anger = polity.grievance.get(race.id, 0.0)
            if pol.is_harsh(polity.policy) or anger > 0.3:
                add(demo.PERSECUTION,
                    0.35 + 0.6 * anger + (0.3 if pol.is_harsh(polity.policy)
                                          else 0.0))
    for fact in world.live_facts(region_id):
        if fact.kind == history.SCAR:
            add(demo.RUIN, 0.35 * fact.power(year))
    return best, force


# ---------------------------------------------------------------------------
# Сам уход
# ---------------------------------------------------------------------------

def _move(ctx, source, cause: str, loads: dict, year: int, rng) -> None:
    world = ctx.world
    race = races_mod.RACES_BY_ID.get(source.race_id)
    if race is None:
        return
    home = world.regions.get(source.region_id)
    if home is None:
        return
    target = _destination(ctx, race, home, loads, year, rng)
    if target is None:
        return

    if source.id in world.tribes:
        _move_tribe(ctx, source, race, home, target, cause, year, rng)
    else:
        _move_from_city(ctx, source, race, home, target, cause, year, rng)


def _destination(ctx, race, home, loads: dict, year: int, rng):
    """Куда пойдут: желанная земля по соседству, не переполненная."""
    world = ctx.world
    reach = list(home.neighbors)
    if any(trait in SEAFARING for trait in race.traits):
        reach.extend(home.sea_links)     # мореходам вода не помеха
    pairs = []
    for region_id in reach:
        region = world.regions.get(region_id)
        if region is None or region.drowned:
            continue
        if not region.known and rng.chance(0.7):
            continue          # в неведомую землю идут редко и отчаянно
        load = loads.get(region_id, 1.0)
        weight = demo.attraction(ctx, race, region, year, load)
        if weight <= 0.05:
            continue
        pairs.append((region, weight))
    if not pairs:
        return None
    return rng.weighted(pairs)


def _move_tribe(ctx, tribe, race, home, target, cause: str, year: int,
                rng) -> None:
    """Племя снимается целиком и уходит в соседнюю землю."""
    world = ctx.world
    host = demo.host_of(world, target.id)
    if host is not None and demo.welcome(world, host, race, year) < WELCOME_LINE:
        _refused(ctx, tribe, race, home, target, host, cause, year, rng,
                 souls=tribe.population)
        return

    old_region = tribe.region_id
    tribe.region_id = target.id
    if ctx.map is not None:
        tribe.hex_index = ctx.map.place(target.id, rng, kind="tribe")
        if tribe.hex_index >= 0:
            ctx.map.claim(tribe.hex_index, tribe.id)
    tribe.population = max(60, int(tribe.population
                                   * rng.uniform(0.82, 0.96)))

    date = ctx.date_in(rng, year)
    title, text = texts.tribe_move(rng, tribe, home, target, cause)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="migration",
        title=title, text=text, importance=2, subjects=[tribe.id],
        region_id=target.id, race_id=race.id,
        facts=_cause_facts(world, old_region, year),
        trace=history.trace_of(2))
    _record(ctx, race, cause, home, target, tribe.population, True,
            host, year, event, kind="племя ушло")


def _move_from_city(ctx, settlement, race, home, target, cause: str,
                    year: int, rng) -> None:
    """Часть городской округи уходит искать другую землю."""
    world = ctx.world
    realm = world.settlement_realm(settlement)
    souls = int(realm * rng.uniform(*LEAVE_SHARE))
    if souls < MIN_SOULS:
        return
    host = demo.host_of(world, target.id)
    welcomed = host is None or demo.welcome(world, host, race, year) >= WELCOME_LINE

    settlement.population = max(60, settlement.population
                                - int(souls / RURAL_FACTOR))
    if not welcomed:
        _refused(ctx, settlement, race, home, target, host, cause, year, rng,
                 souls=souls)
        return

    # Пришедших принимает свой же город, если он там есть; иначе они
    # ставят своё поселение — а народ, городов не знающий, садится на
    # землю племенем.
    joined = None
    for other_id in world.active_settlements:
        other = world.settlements[other_id]
        if other.region_id == target.id and other.race_id == race.id:
            joined = other
            break
    if joined is not None:
        joined.population += max(20, int(souls / RURAL_FACTOR))
    elif race.settles:
        _plant_town(ctx, settlement, race, target, souls, host, year, rng)
    else:
        peoples.found_tribe(ctx, race, target, year, rng, population=souls,
                            folk=world.folks.get(settlement.folk_id))

    date = ctx.date_in(rng, year)
    title, text = texts.migration(rng, race, cause, home, target, souls,
                                  True, host.name if host is not None else "")
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="migration",
        title=title, text=text, importance=3,
        subjects=[settlement.id] + ([host.id] if host is not None else []),
        region_id=target.id, race_id=race.id,
        facts=_cause_facts(world, home.id, year, settlement.polity_id),
        trace=history.trace_of(3))
    world.refresh_populations()
    _record(ctx, race, cause, home, target, souls, True, host, year, event,
            kind="исход из города")


def _plant_town(ctx, settlement, race, target, souls: int, host, year: int,
                rng) -> None:
    """Переселенцы ставят на новом месте свой посад.

    Считаем по-честному: город и его округа — это те же самые души, что
    ушли, а не впятеро больше. Иначе каждое переселение раздувало бы
    население мира.
    """
    world = ctx.world
    folk = world.folks.get(settlement.folk_id)
    speech = ctx.tongue_of(folk)
    hex_index = -1
    if ctx.map is not None:
        hex_index = ctx.map.place(target.id, rng, kind="city")
    date = ctx.date_in(rng, year)
    # У переселенцев есть тот, кто вёл их всю дорогу, — он и ставит посад.
    sex = "f" if rng.chance(0.4) else "m"
    leader = ctx.make_figure(
        rng, race, year, role="основатель поселения", region_id=target.id,
        title=ctx.title_for(race, "founder", sex), sex=sex,
        folk=folk, epithet_chance=0.5)
    town = world.add_settlement(
        name=ctx.forge.settlement(rng, race, speech),
        kind=rng.choice(race.settlement_words or ("Селение",)),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=target.id, population=max(60, int(souls / RURAL_FACTOR)),
        hex_index=hex_index, folk_id=settlement.folk_id)
    leader.home_id = town.id
    if ctx.map is not None and hex_index >= 0:
        ctx.map.claim(hex_index, town.id)
    # Принявшая держава берёт посад под свою руку — и становится
    # многонародной; вольный посад остаётся сам по себе.
    if host is not None:
        town.polity_id = host.id
        host.settlement_ids.append(town.id)
        if target.id not in host.region_ids:
            host.region_ids.append(target.id)


def _refused(ctx, source, race, home, target, host, cause: str, year: int,
             rng, souls: int) -> None:
    """Пришлых не приняли: часть гибнет, остальные садятся где придётся."""
    world = ctx.world
    left = max(0, int(souls * (1.0 - rng.uniform(*REFUSED_LOSS))))
    date = ctx.date_in(rng, year)
    title, text = texts.migration(rng, race, cause, home, target, souls,
                                  False, host.name if host is not None else "")
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="migration",
        title=title, text=text, importance=3,
        subjects=[source.id] + ([host.id] if host is not None else []),
        region_id=target.id, race_id=race.id,
        facts=_cause_facts(world, home.id, year),
        trace=history.trace_of(3))

    if source.id in world.tribes:
        source.population = max(40, left)
    elif left > 0:
        # Уцелевшие возвращаются туда, откуда вышли: своего города у них
        # больше нет, но и чужого им не дали.
        source.population += max(0, int(left / RURAL_FACTOR))

    if host is not None:
        # Отказ помнят обе стороны: пришлые — как обиду, хозяева — как
        # страх перед теми, кто однажды вернётся.
        origin = world.polities.get(getattr(source, "polity_id", ""))
        if origin is not None:
            history.leave(world, history.GRUDGE, year, origin.id, host.id,
                          weight=0.55, note="не приняли беженцев",
                          event_id=event.id)
        history.leave(world, history.DREAD, year, host.id,
                      weight=0.4, note="пришлые у межи", event_id=event.id)
        host.grievance[race.id] = min(1.0, host.grievance.get(race.id, 0.0)
                                      + 0.2)
    _record(ctx, race, cause, home, target, souls, False, host, year, event,
            kind="не приняли")


# ---------------------------------------------------------------------------
# Записи
# ---------------------------------------------------------------------------

def _cause_facts(world, region_id: str, year: int, polity_id: str = "") -> list:
    """Следы, из которых вырос этот уход."""
    out = []
    for fact in world.facts_of(region_id, year, history.SCAR)[:1]:
        out.append(fact.id)
    if polity_id:
        for kind in (history.HUNGER, history.GRUDGE):
            for fact in world.facts_of(polity_id, year, kind)[:1]:
                out.append(fact.id)
    return out


def _record(ctx, race, cause: str, home, target, souls: int, welcomed: bool,
            host, year: int, event, kind: str) -> None:
    """Запись о переселении — для летописи и для будущих блоков."""
    world = ctx.world
    world.add_migration(
        year=year, race_id=race.id, cause=cause, kind=kind,
        from_region=home.id if home is not None else "",
        to_region=target.id if target is not None else "",
        to_polity=host.id if host is not None else "",
        souls=int(souls), outcome="приняли" if welcomed else "отказали",
        event_id=event.id if event is not None else "")
    if welcomed and host is not None:
        history.leave(world, history.FAVOUR, year, host.id,
                      weight=0.35, note="приняли пришлых",
                      event_id=event.id if event is not None else "")
