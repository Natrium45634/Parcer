# -*- coding: utf-8 -*-
"""Жизнь чудовищ: логово, разор, охота, конец и то, что остаётся.

Чудовище с именем — это не бедствие, а сосед. Оно заводится в глухой
земле, разоряет одну и ту же долину, копит золото в логове и убивает
одного героя за другим, пока не приходит тот, кто его убьёт. После этого
остаются три вещи: клад, песня и кость, из которой куют оружие.

Ночные твари живут иначе: не в логове, а среди людей. Они кормятся тихо
и держатся поколениями — пока кто-нибудь не сведёт счёт пропавших с
чьим-то именем.
"""

from __future__ import annotations

from .. import artifacts as art
from .. import monsters as mon
from .. import narrative_artifacts as art_texts
from .. import narrative_monsters as texts
from .. import races as races_mod
from .. import rulers as rulers_mod
from .. import sites as sites_mod
from ..models import ACTIVE

SPAWN_RATE = 0.10           # шанс, что за такт в мире заведётся чудовище
NIGHT_SHARE = 0.35          # какая доля из них — ночные твари
RAID_RATE = 0.38            # как часто чудовище выходит из логова
HUNT_RATE = 0.3             # и как часто на него собирают охоту
FEED_RATE = 0.45
EXPOSE_RATE = 0.07
BONE_CHANCE = 0.35          # шанс, что из убитого выкуют вещь
MAX_ALIVE = 12              # больше в одном мире разом не водится
MAX_HOARD = 400000          # золота в логове не бывает больше, чем в казне
RAID_TOLL_CAP = 500         # сколько душ чудовище берёт за один налёт


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("monsters", year)
    scale = period / 10.0

    if len(world.living_monsters) < MAX_ALIVE and rng.chance(SPAWN_RATE * scale):
        _spawn(ctx, year, rng)

    for monster_id in list(world.living_monsters):
        monster = world.monsters[monster_id]
        if monster.family == mon.NIGHT:
            _night_tick(ctx, monster, year, period, rng)
        else:
            _beast_tick(ctx, monster, year, period, rng)


# ---------------------------------------------------------------------------
# Появление
# ---------------------------------------------------------------------------

def _spawn(ctx, year: int, rng) -> None:
    world = ctx.world
    era_index = world.era_index_at(year)
    night = rng.chance(NIGHT_SHARE) and era_index >= 1
    if night:
        _spawn_night(ctx, year, era_index, rng)
        return

    # Чудовище заводится в глуши: там, где мало людей и много места.
    pairs = []
    for region in world.regions.values():
        if region.drowned:
            continue
        souls = _souls_in(world, region.id)
        wild = 1.0 + getattr(region, "savagery", 0.0) * 2.0
        pairs.append((region, wild / (1.0 + souls / 4000.0)))
    if not pairs:
        return
    region = rng.weighted(pairs)
    breed = mon.breed_for(rng, region.terrain, era_index, family=mon.BEAST)
    if breed is None:
        return
    monster = _make(ctx, breed, region, year, rng)
    lair = _dig_lair(ctx, monster, breed, region, year, rng)
    monster.site_id = lair.id if lair is not None else ""

    note = rng.choice(breed.notes) if breed.notes else ""
    title, text = texts.awoken(rng, monster, region, note)
    world.add_event(
        date=monster.born, era_index=era_index, kind="monster_wakes",
        title=title, text=text, importance=3, subjects=[monster.id],
        region_id=region.id)


def _spawn_night(ctx, year: int, era_index: int, rng) -> None:
    """Ночная тварь селится не в глуши, а в городе — так сытнее."""
    world = ctx.world
    cities = [world.settlements[sid] for sid in world.active_settlements
              if world.settlements[sid].population >= 800]
    if not cities:
        return
    city = rng.weighted([(item, float(item.population)) for item in cities])
    region = world.regions.get(city.region_id)
    breed = mon.breed_for(rng, region.terrain if region else "", era_index,
                          family=mon.NIGHT)
    if breed is None:
        return
    monster = _make(ctx, breed, region, year, rng)
    monster.settlement_id = city.id
    note = rng.choice(breed.notes) if breed.notes else ""
    title, text = texts.hidden(rng, monster, city, note)
    world.add_event(
        date=monster.born, era_index=era_index, kind="monster_hides",
        title=title, text=text, importance=2, subjects=[monster.id, city.id],
        region_id=city.region_id)


def _make(ctx, breed, region, year: int, rng):
    world = ctx.world
    race = mon.race_for(breed)
    name = "%s %s" % (ctx.forge.monster(rng, race), mon.epithet_for(rng, breed))
    return world.add_monster(
        name=name, breed=breed.key, word=breed.word, gender=breed.gender,
        family=breed.family, born=ctx.date_in(rng, year),
        region_id=region.id if region is not None else "",
        power=round(breed.power * rng.uniform(0.85, 1.25), 2))


def _dig_lair(ctx, monster, breed, region, year: int, rng):
    world = ctx.world
    name = ctx.forge.unique(
        "site", lambda: "%s %s" % (rng.choice(sites_mod.LAIR_WORDS),
                                   monster.name.split()[0]), rng)
    site = world.add_site(
        kind=sites_mod.LAIR, name=name, region_id=region.id if region else "",
        created=monster.born, monster_id=monster.id,
        guards=rng.choice(sites_mod.GUARDS[sites_mod.LAIR]),
        riches=int(sites_mod.riches_for(rng, sites_mod.LAIR, 1.0) * breed.hoard),
        status=sites_mod.INHABITED)
    site.depth = min(5, sites_mod.depth_for(sites_mod.LAIR, site.riches, True))
    site.story = "логово, в котором живёт %s" % monster.name
    monster.hoard = site.riches
    return site


# ---------------------------------------------------------------------------
# Чудовище в логове
# ---------------------------------------------------------------------------

def _beast_tick(ctx, monster, year: int, period: int, rng) -> None:
    scale = period / 10.0
    if rng.chance(RAID_RATE * scale):
        _raid(ctx, monster, year, rng)
    if rng.chance(HUNT_RATE * scale):
        _hunt(ctx, monster, year, rng)


def _raid(ctx, monster, year: int, rng) -> None:
    """Выходит из логова и берёт своё."""
    world = ctx.world
    region = world.regions.get(monster.region_id)
    dead = 0
    # Чудовище — это ужас округи, а не мор: оно берёт хутора и обозы, а
    # не выкашивает державу. Потолок за налёт держит его в своих берегах.
    budget = RAID_TOLL_CAP
    for settlement_id in list(world.active_settlements):
        settlement = world.settlements[settlement_id]
        if settlement.region_id != monster.region_id or budget <= 0:
            continue
        toll = int(world.settlement_realm(settlement)
                   * rng.uniform(0.002, 0.008) * monster.power / 3.0)
        toll = min(toll, budget)
        if toll <= 0:
            continue
        budget -= toll
        settlement.population = max(40, settlement.population
                                    - int(toll / 5.5))
        dead += toll
    for tribe_id in list(world.active_tribes):
        tribe = world.tribes[tribe_id]
        if tribe.region_id != monster.region_id or budget <= 0:
            continue
        toll = min(budget, int(tribe.population * rng.uniform(0.01, 0.04)))
        tribe.population = max(0, tribe.population - toll)
        budget -= toll
        dead += toll
    monster.kills += dead
    monster.raids += 1
    # Клад растёт прибавлением, а не ростом на проценты: иначе за триста
    # лет в логове оказывается больше золота, чем во всём мире.
    monster.hoard = min(MAX_HOARD, monster.hoard + dead // 3
                        + rng.randint(30, 260))
    site = world.sites.get(monster.site_id)
    if site is not None:
        site.riches = monster.hoard

    if dead <= 0 and rng.chance(0.6):
        return
    date = ctx.date_in(rng, year)
    title, text = texts.raided(rng, monster, region, dead)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="monster_raid",
        title=title, text=text, importance=2 if dead < 400 else 3,
        subjects=[monster.id], region_id=monster.region_id)


def _hunt(ctx, monster, year: int, rng) -> None:
    """На чудовище собирают охоту. Возвращаются не всегда."""
    world = ctx.world
    polity = _neighbour_polity(world, monster)
    hero, race = _hero(ctx, monster, polity, year, rng)
    if hero is None:
        return
    # Чудовище, заведшееся в этом же году, нельзя убить до того, как оно
    # завелось: охота идёт после, а не раньше.
    date = ctx.date_in(rng, year, after=monster.born)

    host = 1.0 + rng.uniform(0.0, 1.6)
    if polity is not None:
        host += 0.5 * (len(polity.settlement_ids) ** 0.4)
        host *= rulers_mod.war_edge(world, polity)
    blessed = polity is not None and bool(polity.faith_id)
    if not rng.chance(mon.hero_odds(monster.power, host, blessed)):
        world.schedule_death(hero, date, "погиб в охоте на чудовище"
                             if hero.sex == "m" else "погибла в охоте на чудовище")
        monster.kills += 1
        monster.heroes_eaten.append(hero.id)
        monster.power = round(min(7.0, monster.power * 1.05), 2)
        title, text = texts.hunt_failed(rng, monster, hero)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="monster_hunt_failed", title=title, text=text, importance=2,
            actors=[hero.id], subjects=[monster.id],
            region_id=monster.region_id)
        return

    _slain(ctx, monster, hero, race, polity, year, date, rng)


def _slain(ctx, monster, hero, race, polity, year: int, date, rng) -> None:
    """Чудовище убито: клад, слава и кость, из которой куют оружие."""
    world = ctx.world
    years = max(1, year - monster.born.year)
    riches = monster.hoard
    world.end_monster(monster, date, mon.SLAIN, slayer=hero)
    hero.roles.append("победитель чудовища")
    hero.notes.append("убил %s в %d году" % (monster.name, year)
                      if hero.sex == "m"
                      else "убила %s в %d году" % (monster.name, year))

    site = world.sites.get(monster.site_id)
    if site is not None:
        site.status = sites_mod.CLEARED
        site.opened = date
        site.opened_by = hero.id
        site.riches = int(riches * rng.uniform(0.05, 0.25))
        site.guards = "кости прежних охотников"
        site.story = "здесь жил %s, пока его не убил %s" % (monster.name,
                                                            hero.name)

    title, text = texts.hunt_won(rng, monster, hero, years, riches)
    text = "%s %s" % (text, texts.legacy(rng))
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="monster_slain",
        title=title, text=text, importance=4, actors=[hero.id],
        subjects=[monster.id] + ([site.id] if site is not None else []),
        region_id=monster.region_id, race_id=hero.race_id)
    hero.deeds.append(event.id)

    # Из костей побеждённого куют вещь — и у неё сразу есть история.
    if race is not None and rng.chance(BONE_CHANCE):
        _bone_relic(ctx, monster, hero, race, polity, year, date, rng, event)


def _bone_relic(ctx, monster, hero, race, polity, year: int, date, rng,
                event) -> None:
    from . import artifacts as artifacts_system

    world = ctx.world
    artifact = artifacts_system._make(
        ctx, rng, race, year, art.TAKEN,
        region_id=monster.region_id, sort=art.WEAPON)
    artifact.material = "кость %s" % monster.name
    artifact.material_gen = "из кости, взятой у чудовища по имени %s" \
        % monster.name
    artifact.notes.append("сделана из убитого в %d году %s"
                          % (year, monster.name))
    world.put_artifact(artifact, art.WITH_FIGURE, date, figure=hero,
                       how="выкована из кости убитого чудовища")
    artifact.deeds.append(event.id)
    title, text = art_texts.forged(rng, artifact, hero, None)
    made = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="artifact_made",
        title=title, text=text, importance=3, actors=[hero.id],
        subjects=[artifact.id, monster.id], region_id=monster.region_id,
        race_id=race.id)
    artifact.deeds.append(made.id)


# ---------------------------------------------------------------------------
# Ночные твари
# ---------------------------------------------------------------------------

def _night_tick(ctx, monster, year: int, period: int, rng) -> None:
    world = ctx.world
    scale = period / 10.0
    settlement = world.settlements.get(monster.settlement_id)
    if settlement is not None and settlement.status != ACTIVE:
        settlement = None
    if settlement is None:
        # Город опустел — тварь ищет другой, пока есть куда идти.
        options = [world.settlements[sid] for sid in world.active_settlements
                   if world.settlements[sid].population >= 600]
        if options and rng.chance(0.5):
            settlement = rng.weighted([(item, float(item.population))
                                       for item in options])
            monster.settlement_id = settlement.id
            monster.region_id = settlement.region_id
            monster.notes.append("перебрался в город %s" % settlement.name)
    if settlement is None:
        world.end_monster(monster, ctx.date_in(rng, year, after=monster.born),
                          mon.DRIVEN)
        monster.notes.append("ушёл, когда город опустел")
        return
    if rng.chance(FEED_RATE * scale):
        monster.kills += rng.randint(1, 4)
        monster.raids += 1
        if rng.chance(0.35):
            date = ctx.date_in(rng, year)
            title, text = texts.fed(rng, monster, settlement)
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="monster_feeds", title=title, text=text, importance=1,
                subjects=[monster.id, settlement.id],
                region_id=settlement.region_id)
    # Чем дольше живёт, тем вернее попадётся: счёт пропавших растёт.
    risk = EXPOSE_RATE * scale * (1.0 + monster.kills / 40.0)
    if rng.chance(min(0.6, risk)):
        _expose(ctx, monster, settlement, year, rng)


def _expose(ctx, monster, settlement, year: int, rng) -> None:
    world = ctx.world
    race = races_mod.RACES_BY_ID.get(settlement.race_id)
    if race is None:
        return
    date = ctx.date_in(rng, year, after=monster.born)
    sex = "f" if rng.chance(0.4) else "m"
    hunter = ctx.make_figure(
        rng, race, year, role="охотник на нечисть",
        region_id=settlement.region_id, title="", sex=sex,
        home_id=settlement.id, epithet_chance=0.7,
        folk=world.folks.get(settlement.folk_id))
    years = max(1, year - monster.born.year)
    if rng.chance(mon.hero_odds(monster.power, 1.0 + rng.uniform(0.4, 2.2))):
        world.end_monster(monster, date, mon.SLAIN, slayer=hunter)
        hunter.roles.append("победитель чудовища")
    else:
        world.end_monster(monster, date, mon.EXPOSED)
        monster.notes.append("ушёл, когда его раскрыли")
        world.schedule_death(hunter, date, "убит нечистью"
                             if hunter.sex == "m" else "убита нечистью")
    title, text = texts.exposed(rng, monster, hunter, years)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="monster_exposed",
        title=title, text=text, importance=3, actors=[hunter.id],
        subjects=[monster.id, settlement.id], region_id=settlement.region_id)


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _souls_in(world, region_id: str) -> int:
    total = 0
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id == region_id:
            total += world.settlement_realm(settlement)
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.region_id == region_id:
            total += tribe.population
    return total


def _neighbour_polity(world, monster):
    """Держава, которой это чудовище мешает жить."""
    best, best_size = None, 0
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if monster.region_id not in polity.region_ids:
            continue
        if polity.population > best_size:
            best, best_size = polity, polity.population
    return best


def _hero(ctx, monster, polity, year: int, rng):
    """Кто пойдёт: воин державы или местный, которому надоело."""
    from . import nations as nations_mod

    world = ctx.world
    if polity is not None:
        race = races_mod.get_race(polity.race_id)
        hero = nations_mod.pick_general(ctx, rng, polity, race, year)
        if hero is not None:
            return hero, race
    cities = [world.settlements[sid] for sid in world.active_settlements
              if world.settlements[sid].region_id == monster.region_id]
    if not cities:
        return None, None
    city = rng.choice(sorted(cities, key=lambda s: s.id))
    race = races_mod.RACES_BY_ID.get(city.race_id)
    if race is None:
        return None, None
    sex = "f" if rng.chance(0.3) else "m"
    hero = ctx.make_figure(
        rng, race, year, role="охотник на чудовищ", region_id=city.region_id,
        title="", sex=sex, home_id=city.id, epithet_chance=0.75,
        folk=world.folks.get(city.folk_id))
    return hero, race


__all__ = ["upkeep"]
