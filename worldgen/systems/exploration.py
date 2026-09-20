# -*- coding: utf-8 -*-
"""Походы в неизведанное: за море, за лёд, за край карты.

Пока земли связаны сушей, молва расходится сама: сосед ведомой земли тоже
становится ведом. Но за водой молва не идёт. Остров, архипелаг, дальний
материк остаются пустыми пятнами, пока кто-нибудь не рискнёт туда доплыть.

Что здесь происходит:

1. **Снаряжение.** Держава с гаванью посылает корабли. У мореходов это
   выходит чаще, у горных народов — почти никогда.
2. **Поход.** Он длится годы. Кончиться может по-разному: землёй,
   которую нанесут на карту; берегом, который видели, но не достали;
   пустым горизонтом; или молчанием — когда не возвращается никто.
3. **Память.** Каждая попытка что-то оставляет: следующий поход к той же
   цели идёт увереннее. Третья попытка находит то, на чём сгинули две
   первые.
4. **Колонии.** Открытая земля становится ведомой, и туда можно селиться.
   Заморское владение со временем перестаёт слушаться метрополии.
"""

from __future__ import annotations

from .. import narrative_exploration as texts
from .. import races as races_mod
from ..models import ACTIVE
from . import succession

EXPEDITION_RATE = 0.012        # годовая вероятность снарядить поход
FREE_SHARE = 0.18              # доля вольных походов, без казны
MIN_SPONSOR_POPULATION = 6000
ATTEMPT_BONUS = 0.13           # насколько легче идти по чужим следам
INDEPENDENCE_RATE = 0.010      # годовая вероятность отложиться от метрополии
COLONY_AFTER_DISCOVERY = 0.45

SEAFARING_TRAITS = ("мореходы", "рыбаки", "китобои", "торговцы")
LANDBOUND = ("подземья", "горы")


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    _advance(ctx, year)
    _maybe_launch(ctx, year)


def upkeep(ctx, year: int, period: int) -> None:
    _maybe_independence(ctx, year)


# ---------------------------------------------------------------------------
# Снаряжение
# ---------------------------------------------------------------------------

def _maybe_launch(ctx, year: int) -> None:
    world = ctx.world
    if not world.active_settlements:
        return
    rng = ctx.rng("expedition", year)

    unknown = [region for region in world.regions.values()
               if not region.known and not region.drowned]
    # Чем позже эпоха и чем больше белых пятен, тем чаще снаряжают корабли.
    urge = 0.4 + 0.22 * world.era_index_at(year)
    if not unknown:
        urge *= 0.12          # открывать больше нечего: остаётся край света
    if not rng.chance(ctx.rate(EXPEDITION_RATE) * urge):
        return

    sponsor, port = _pick_sponsor(ctx, rng)
    if port is None:
        return

    race = races_mod.get_race(port.race_id)
    target, kind = _pick_target(ctx, rng, port, unknown)
    if target is None and kind != "ice":
        return

    date = ctx.date_in(rng, year)
    sex = "f" if rng.chance(0.3) else "m"
    leader = ctx.make_figure(
        rng, race, year, role="мореплаватель" if kind != "land" else "первопроходец",
        region_id=port.region_id,
        title="кормчий" if sex == "m" else "кормчая", sex=sex,
        epithet_chance=0.85)
    leader.home_id = port.id

    ships = rng.randint(1, 3) + (1 if world.era_index_at(year) >= 3 else 0)
    crew = ships * rng.randint(30, 90)
    target_id = target.id if target is not None else ""
    attempt = ctx.expedition_attempts.get(target_id or "ice", 0) + 1
    ctx.expedition_attempts[target_id or "ice"] = attempt

    expedition = world.add_expedition(
        name=ctx.forge.unique(
            "expedition", lambda: texts.expedition_name(rng, kind, leader), rng),
        kind=kind, leader_id=leader.id, race_id=race.id,
        start=date, polity_id=sponsor.id if sponsor is not None else "",
        from_region=port.region_id, target_region=target_id,
        target_name=target.name if target is not None else "Ледяной Предел",
        crew=crew, attempt=attempt)
    leader.roles.append("глава похода")

    region = world.regions.get(port.region_id)
    title, text = texts.launch(rng, expedition, leader, sponsor, region, ships)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="expedition_start",
        title=title, text=text, importance=3, actors=[leader.id],
        subjects=[expedition.id] + ([sponsor.id] if sponsor is not None else []),
        region_id=port.region_id, race_id=race.id)
    leader.deeds.append(event.id)

    # Сколько лет их не будет.
    span = {"ice": rng.randint(2, 6), "deep": rng.randint(2, 5)}.get(
        kind, rng.randint(1, 7))
    ctx.expedition_due[expedition.id] = year + span


def _pick_sponsor(ctx, rng):
    """Кто снаряжает поход и из какой гавани."""
    world = ctx.world
    ports = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        region = world.regions.get(settlement.region_id)
        if region is None:
            continue
        # Из подгорного чертога в море не выйти.
        if region.terrain in LANDBOUND:
            continue
        race = races_mod.RACES_BY_ID.get(settlement.race_id)
        if race is None:
            continue
        weight = float(settlement.population)
        if region.coastal or region.island or region.terrain in (
                races_mod.COAST, races_mod.ISLANDS):
            weight *= 3.0
        for trait in race.traits:
            if trait in SEAFARING_TRAITS:
                weight *= 1.8
        ports.append((settlement, weight))
    if not ports:
        return None, None
    port = rng.weighted(ports)
    polity = world.polities.get(port.polity_id)
    if polity is not None and polity.population < MIN_SPONSOR_POPULATION:
        polity = None
    if polity is not None and rng.chance(FREE_SHARE):
        polity = None
    return polity, port


def _pick_target(ctx, rng, port, unknown):
    """Куда идти: за неведомой землёй или за край света."""
    world = ctx.world
    home = world.regions.get(port.region_id)
    if home is None:
        return None, "sea"

    # Ближние неведомые земли — те, с которыми есть морская связь.
    reachable = []
    for region in unknown:
        if home.id in region.sea_links or region.id in home.sea_links:
            reachable.append((region, 3.0))
        else:
            reachable.append((region, 0.6))
    if reachable and rng.chance(0.93):
        return rng.weighted(reachable), "sea"
    # Иначе — поход ради самого похода: к ледяной границе мира. Это редкость:
    # подвиг, повторённый двадцать раз, перестаёт быть подвигом.
    reached = ctx.world.notes.get("край света") or []
    if len(reached) >= 2 and rng.chance(0.75):
        return (rng.weighted(reachable) if reachable else None), "sea"
    return None, "ice"


# ---------------------------------------------------------------------------
# Возвращение
# ---------------------------------------------------------------------------

def _advance(ctx, year: int) -> None:
    world = ctx.world
    for expedition_id in list(world.active_expeditions):
        due = ctx.expedition_due.get(expedition_id)
        if due is None or due > year:
            continue
        _finish(ctx, world.expeditions[expedition_id], year)
        ctx.expedition_due.pop(expedition_id, None)


def _finish(ctx, expedition, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("expedition", "end", expedition.id)
    leader = world.figures.get(expedition.leader_id)
    if leader is None:
        world.end_expedition(expedition, ctx.date_in(rng, year), "empty")
        return

    race = races_mod.RACES_BY_ID.get(expedition.race_id)
    chance = 0.22 + ATTEMPT_BONUS * (expedition.attempt - 1)
    chance += 0.04 * world.era_index_at(year)
    if race is not None:
        for trait in race.traits:
            if trait in SEAFARING_TRAITS:
                chance += 0.10
    chance -= 0.12 * ctx.gloom(expedition.from_region)
    chance = max(0.05, min(0.88, chance))

    date = ctx.date_in(rng, year)
    target = world.regions.get(expedition.target_region)
    roll = rng.random()

    if expedition.kind == "ice":
        # Дойти до края света труднее, чем найти остров: льду нет конца,
        # и большинство поворачивает раньше.
        outcome = "discovered" if roll < chance * 0.45 else (
            "lost" if rng.chance(0.45) else "empty")
    elif roll < chance:
        outcome = "discovered"
    elif roll < chance + 0.18:
        outcome = "sighted"
    elif rng.chance(0.42):
        outcome = "lost"
    else:
        outcome = "empty"

    if outcome == "lost":
        survivors = 0
        expedition.deaths = expedition.crew
    elif outcome == "discovered":
        survivors = max(1, int(expedition.crew * rng.uniform(0.35, 0.85)))
        expedition.deaths = expedition.crew - survivors
    else:
        survivors = max(1, int(expedition.crew * rng.uniform(0.5, 0.95)))
        expedition.deaths = expedition.crew - survivors

    world.end_expedition(expedition, date, outcome)

    if outcome == "lost":
        world.schedule_death(leader, date, "сгинул в походе"
                             if leader.sex == "m" else "сгинула в походе")
        title, text = texts.failure(rng, expedition, leader, outcome,
                                    expedition.crew)
        importance = 3
    elif expedition.kind == "ice" and outcome == "discovered":
        title, text = texts.ice_edge(rng, expedition, leader, survivors)
        importance = 5
        _crown(ctx, leader, "Ледяной Предел", rng)
        world.notes.setdefault("край света", []).append(
            "%d: %s (%s)" % (year, leader.name, expedition.name))
    elif outcome == "discovered" and target is not None:
        world.discover_region(target, year, figure_id=leader.id,
                              race_id=expedition.race_id)
        ctx.spread_knowledge()
        expedition.discovered.append(target.id)
        title, text = texts.discovery(rng, expedition, leader, target,
                                      survivors, expedition.crew)
        importance = 5
        _crown(ctx, leader, target.name, rng)
    elif outcome == "sighted":
        # Виденную землю в следующий раз найдут быстрее.
        title, text = texts.failure(rng, expedition, leader, outcome,
                                    expedition.crew)
        importance = 2
    else:
        title, text = texts.failure(rng, expedition, leader, "empty",
                                    expedition.crew)
        importance = 2

    event = world.add_event(
        date=date, era_index=world.era_index_at(year),
        kind="expedition_end", title=title, text=text, importance=importance,
        actors=[leader.id], subjects=[expedition.id] + expedition.discovered,
        region_id=expedition.target_region or expedition.from_region,
        race_id=expedition.race_id)
    leader.deeds.append(event.id)

    if outcome == "discovered" and target is not None \
            and rng.chance(COLONY_AFTER_DISCOVERY):
        _plant_colony(ctx, expedition, target, rng, year)


def _crown(ctx, leader, what: str, rng) -> None:
    """Открывателя запоминают: у него появляется прозвище по его делу."""
    leader.notes.append("открыл: %s" % what)
    if leader.epithet:
        return
    pool = ("Мореход", "Дальнобродец", "Тот, Кто Дошёл", "Открыватель",
            "Морской Волк", "Первый Берег")
    female = ("Мореходка", "Дальнобродка", "Та, Кто Дошла", "Открывательница",
              "Морская Волчица", "Первый Берег")
    leader.epithet = rng.choice(female if leader.sex == "f" else pool)


def _plant_colony(ctx, expedition, region, rng, year: int) -> None:
    """Первое поселение на открытой земле."""
    world = ctx.world
    polity = world.polities.get(expedition.polity_id)
    race = races_mod.RACES_BY_ID.get(expedition.race_id)
    if race is None or not race.settles:
        return
    if region.terrain not in race.terrains and rng.chance(0.6):
        return

    date = ctx.date_in(rng, year)
    sex = "f" if rng.chance(0.4) else "m"
    founder = ctx.make_figure(
        rng, race, year, role="основатель", region_id=region.id,
        title=ctx.title_for(race, "founder", sex), sex=sex)
    hex_index = ctx.map.place(region.id, rng, kind="city") if ctx.map else -1
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race), kind="Колония",
        race_id=race.id, founded=date, founder_id=founder.id,
        region_id=region.id, population=rng.randint(80, 320),
        polity_id=polity.id if polity is not None else "",
        hex_index=hex_index)
    if ctx.map is not None and hex_index >= 0:
        ctx.map.claim(hex_index, settlement.id)
    founder.home_id = settlement.id
    if polity is not None:
        polity.settlement_ids.append(settlement.id)
        if region.id not in polity.region_ids:
            polity.region_ids.append(region.id)

    title, text = texts.colony(rng, polity, settlement, region)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="colony_overseas",
        title=title, text=text, importance=3, actors=[founder.id],
        subjects=[settlement.id] + ([polity.id] if polity is not None else []),
        region_id=region.id, race_id=race.id)


# ---------------------------------------------------------------------------
# Заморские владения отлагаются
# ---------------------------------------------------------------------------

def _maybe_independence(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("colony", year)
    if not rng.chance(ctx.rate(INDEPENDENCE_RATE)):
        return

    pairs = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        core = world.regions.get(
            world.settlements[polity.capital_id].region_id) \
            if polity.capital_id in world.settlements else None
        if core is None:
            continue
        overseas = []
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is None or settlement.status != ACTIVE:
                continue
            if settlement.region_id == core.id:
                continue
            region = world.regions.get(settlement.region_id)
            if region is None:
                continue
            # Заморским считается то, до чего от столицы не дойти посуху.
            if core.id in region.sea_links or region.id in core.sea_links:
                overseas.append(settlement)
        if len(overseas) >= 2:
            pairs.append(((polity, overseas), float(len(overseas))))
    if not pairs:
        return

    polity, overseas = rng.weighted(pairs)
    race = races_mod.RACES_BY_ID.get(overseas[0].race_id)
    if race is None or not race.builds_states:
        return

    date = ctx.date_in(rng, year)
    capital = max(overseas, key=lambda s: (s.population, s.id))
    sex = "f" if rng.chance(0.4) else "m"
    leader = ctx.make_figure(
        rng, race, year, role="правитель", region_id=capital.region_id,
        title=ctx.title_for(race, "ruler", sex), sex=sex, epithet_chance=0.7)
    new_polity = world.add_polity(
        name=ctx.forge.polity(rng, race),
        form=rng.choice(race.polity_words or ("Вольный Союз",)),
        race_id=race.id, founded=date, founder_id=leader.id,
        capital_id=capital.id, ruler_id="", region_ids=[], settlement_ids=[],
        predecessor_id=polity.id)
    for settlement in overseas:
        if settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)
        settlement.polity_id = new_polity.id
        settlement.is_capital = settlement.id == capital.id
        new_polity.settlement_ids.append(settlement.id)
        if settlement.region_id not in new_polity.region_ids:
            new_polity.region_ids.append(settlement.region_id)
    succession.install_founder(ctx, new_polity, leader, capital, date, year)
    world.refresh_populations()

    title, text = texts.independence(rng, polity, new_polity)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="colony_free",
        title=title, text=text, importance=4, actors=[leader.id],
        subjects=[new_polity.id, polity.id], region_id=capital.region_id,
        race_id=race.id)
