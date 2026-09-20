# -*- coding: utf-8 -*-
"""Бедствия, после которых мир уже не тот.

Обычная беда убивает людей и уходит. Эти четыре меняют саму землю: одна
уводит её под воду, другая рвёт надвое, третья гасит солнце над всеми
разом, четвёртая поднимает из глубины то, что не добили в прошлый раз.

После них на карте остаются следы, которые видно и через тысячу лет:
затонувший город, пролив там, где был перешеек, запечатанный чертог, из
которого никто не вышел, — и, если беда была совсем тяжёлой, народ,
которого больше нет.
"""

from __future__ import annotations

from .. import narrative_upheaval as texts
from .. import races as races_mod
from .. import sites as sites_mod
from ..models import ACTIVE, GONE, RUINED
from ..world import RURAL_FACTOR

# Какие беды меняют мир и что именно они с ним делают.
GREAT = ("drowning", "sundering", "long_dark", "deep_waking")

# Море не забирает всё. Даже за десять тысяч лет под воду уходит не больше
# четверти суши: мир, наполовину ставший океаном, — это уже не тот мир,
# для которого писалось всё остальное.
MAX_DROWNED_SHARE = 0.25


def aftermath(ctx, calamity, spec, rng, year: int, date) -> None:
    """Вызывается при начале беды: то, что она делает с самой землёй."""
    if spec.key == "drowning":
        _drown(ctx, calamity, rng, year, date)
    elif spec.key == "sundering":
        _sunder(ctx, calamity, rng, year, date)
    elif spec.key == "deep_waking":
        _empty_hall(ctx, calamity, rng, year, date)


# ---------------------------------------------------------------------------
# Погружение
# ---------------------------------------------------------------------------

def _drown(ctx, calamity, rng, year: int, date) -> None:
    """Земля уходит под воду за одну ночь. Уцелевшие уплывают."""
    world = ctx.world
    drowned = []
    survivors = []          # (поселение, сколько душ успело в лодки)
    already = sum(1 for item in world.regions.values() if item.drowned)
    limit = max(1, int(len(world.regions) * MAX_DROWNED_SHARE))
    for region_id in calamity.region_ids:
        if already >= limit:
            calamity.notes.append("море остановилось у прежних берегов")
            break
        region = world.regions.get(region_id)
        if region is None or region.drowned:
            continue
        already += 1
        region.drowned = True
        region.capacity = 0.0
        region.habitat = 0.0
        drowned.append(region)
        for settlement_id in list(world.active_settlements):
            settlement = world.settlements[settlement_id]
            if settlement.region_id != region_id:
                continue
            # Спасаются те, кто был в море или успел к лодкам: шестая часть
            # города, и то если повезёт с погодой.
            saved = max(1, int(settlement.population * rng.uniform(0.08, 0.2)))
            survivors.append((settlement, saved))
            lost = max(0, world.settlement_realm(settlement)
                       - int(saved * RURAL_FACTOR))
            _toll(calamity, lost, settlement.polity_id, settlement.race_id)
            _sink_city(ctx, calamity, settlement, region, date, year, rng)
            calamity.settlements_lost += 1
        for tribe_id in list(world.active_tribes):
            tribe = world.tribes[tribe_id]
            if tribe.region_id == region_id:
                _toll(calamity, tribe.population, "", tribe.race_id)
                world.end_tribe(tribe, date, "ушло под воду", GONE)
        for camp_id in list(world.active_camps):
            camp = world.camps[camp_id]
            if camp.region_id == region_id:
                _toll(calamity, camp.population, "", camp.race_id)
                world.end_camp(camp, date, "ушло под воду", GONE)
    if not drowned:
        return
    calamity.notes.append("под воду ушло земель: %d" % len(drowned))
    ctx.build_region_weights()

    refuge = _refuge(world, drowned, rng)
    title, text = texts.drowning(rng, drowned, refuge, survivors)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="land_drowned",
        title=title, text=text, importance=5,
        subjects=[calamity.id], region_id=drowned[0].id)
    _exodus(ctx, calamity, survivors, refuge, rng, year, date)


def _toll(calamity, dead: int, polity_id: str, race_id: str) -> None:
    """Счёт беды: утонувшие — такие же её жертвы, как убитые."""
    dead = int(dead)
    if dead <= 0:
        return
    calamity.deaths += dead
    if polity_id:
        calamity.deaths_by_polity[polity_id] = \
            calamity.deaths_by_polity.get(polity_id, 0) + dead
    if race_id:
        calamity.deaths_by_race[race_id] = \
            calamity.deaths_by_race.get(race_id, 0) + dead


def _sink_city(ctx, calamity, settlement, region, date, year: int, rng) -> None:
    """Город уходит под воду вместе со всем, что в нём было."""
    world = ctx.world
    riches = int(world.settlement_realm(settlement) * rng.uniform(0.1, 0.4))
    world.end_settlement(settlement, date, "ушёл под воду", RUINED)
    name = ctx.forge.unique(
        "site", lambda: "Затонувший %s" % settlement.name, rng)
    site = world.add_site(
        kind=sites_mod.SUNKEN, name=name, region_id=region.id, created=date,
        settlement_id=settlement.id, polity_id=settlement.polity_id,
        calamity_id=calamity.id,
        guards=rng.choice(sites_mod.GUARDS[sites_mod.SUNKEN]),
        riches=riches, hex_index=settlement.hex_index)
    site.depth = 5
    site.story = "здесь стоял город %s, пока море не пришло за ним" \
        % settlement.name


def _refuge(world, drowned, rng):
    """Куда плывут уцелевшие: ближайшая земля, где ещё можно жить."""
    if not drowned:
        return None
    home = drowned[0]
    options = []
    for region in world.regions.values():
        if region.drowned or region.id in {item.id for item in drowned}:
            continue
        gap = abs(region.x - home.x) ** 2 + abs(region.y - home.y) ** 2
        options.append((region, 1.0 / (1.0 + gap ** 0.5)))
    if not options:
        return None
    return rng.weighted(options)


def _exodus(ctx, calamity, survivors, refuge, rng, year: int, date) -> None:
    """Уцелевшие высаживаются на чужом берегу и ставят город заново.

    Это важнее, чем кажется: держава, потерявшая родину, продолжается
    в одном-единственном поселении, и через тысячу лет её потомки всё ещё
    зовут себя по имени земли, которой нет на карте.
    """
    world = ctx.world
    if refuge is None or not survivors:
        return
    spec = ctx.era_spec(year)
    if not spec.allow_settlements:
        return
    mother, saved = max(survivors, key=lambda item: item[1])
    if saved < 60:
        return
    race = races_mod.get_race(mother.race_id)
    polity = world.polities.get(mother.polity_id)
    if polity is not None and polity.status != ACTIVE:
        polity = None

    sex = "f" if rng.chance(0.42) else "m"
    leader = ctx.make_figure(rng, race, year, role="основатель",
                             region_id=refuge.id,
                             title=ctx.title_for(race, "founder", sex), sex=sex)
    new_hex = ctx.map.place(refuge.id, rng, kind="city") if ctx.map else -1
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race, ctx.tongue_of(mother.folk_id)),
        kind=rng.choice(race.settlement_words or ("Поселение",)),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=refuge.id, population=saved,
        polity_id=polity.id if polity is not None else "",
        hex_index=new_hex, folk_id=mother.folk_id)
    if ctx.map is not None and new_hex >= 0:
        ctx.map.claim(new_hex, settlement.id)
    leader.roles.append("основатель поселения")
    leader.home_id = settlement.id
    settlement.landmarks.append("памятный камень по утонувшей родине")
    refuge.known = True
    subjects = [settlement.id, calamity.id]
    if polity is not None:
        polity.settlement_ids.append(settlement.id)
        if refuge.id not in polity.region_ids:
            polity.region_ids.append(refuge.id)
        subjects.append(polity.id)
    calamity.notes.append("исход: %s" % settlement.name)

    title, text = texts.exodus(rng, mother, settlement, refuge, leader, saved)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="sea_exodus",
        title=title, text=text, importance=4, actors=[leader.id],
        subjects=subjects, region_id=refuge.id, race_id=race.id)


# ---------------------------------------------------------------------------
# Раскол суши
# ---------------------------------------------------------------------------

def _sunder(ctx, calamity, rng, year: int, date) -> None:
    """Суша рвётся: там, где ходили посуху, теперь ходят кораблём."""
    world = ctx.world
    torn = []
    for region_id in calamity.region_ids:
        region = world.regions.get(region_id)
        if region is None or not region.neighbors:
            continue
        # Рвутся не все связи, а половина: иначе земля остаётся островом
        # посреди мира, и караванам некуда идти вовсе.
        cut = [item for item in region.neighbors
               if item in world.regions and rng.chance(0.5)]
        if not cut:
            continue
        for other_id in cut:
            other = world.regions[other_id]
            if other_id in region.neighbors:
                region.neighbors.remove(other_id)
            if region.id in other.neighbors:
                other.neighbors.remove(region.id)
            if other_id not in region.sea_links:
                region.sea_links.append(other_id)
            if region.id not in other.sea_links:
                other.sea_links.append(region.id)
            other.coastal = True
        region.sundered = True
        region.coastal = True
        torn.append((region, cut))
    if not torn:
        return
    calamity.notes.append("порвано связей: %d"
                          % sum(len(cut) for _, cut in torn))
    title, text = texts.sundering(rng, torn, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="land_sundered",
        title=title, text=text, importance=5, subjects=[calamity.id],
        region_id=torn[0][0].id)


# ---------------------------------------------------------------------------
# Пробуждение в глубине
# ---------------------------------------------------------------------------

def _empty_hall(ctx, calamity, rng, year: int, date) -> None:
    """Великий чертог пустеет и остаётся запечатанным на века."""
    world = ctx.world
    best, best_size = None, 0
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id not in calamity.region_ids:
            continue
        if settlement.population > best_size:
            best, best_size = settlement, settlement.population
    if best is None or best_size < 900:
        return

    riches = int(world.settlement_realm(best) * rng.uniform(0.2, 0.6))
    polity = world.polities.get(best.polity_id)
    world.end_settlement(best, date, "оставлен жителями", RUINED)
    name = ctx.forge.unique(
        "site", lambda: "%s %s" % (rng.choice(sites_mod.SEALED_WORDS),
                                   best.name), rng)
    site = world.add_site(
        kind=sites_mod.SEALED, name=name, region_id=best.region_id,
        created=date, settlement_id=best.id,
        polity_id=best.polity_id, calamity_id=calamity.id,
        guards=rng.choice(sites_mod.GUARDS[sites_mod.SEALED]),
        riches=riches, hex_index=best.hex_index)
    site.depth = 5
    site.story = "здесь стоял %s, пока из глубины не поднялось то, что там спало" \
        % best.full_name
    calamity.notes.append("оставлен город: %s" % best.name)
    calamity.settlements_lost += 1

    title, text = texts.deep_waking(rng, best, site, polity)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="hall_sealed",
        title=title, text=text, importance=5,
        subjects=[calamity.id, site.id], region_id=best.region_id,
        race_id=best.race_id)


# ---------------------------------------------------------------------------
# Мир, который нельзя добить
# ---------------------------------------------------------------------------

# Всемирная беда должна быть страшной, но не последней. Мир, у которого
# отняли девять десятых, — это тёмные века, легенды о лучших временах и
# долгий подъём; мир, у которого отняли всё, — это пустая книга.
# Поэтому у бед есть предел: чем ближе мир ко дну, тем слабее их рука.
FLOOR_SHARE = 0.10          # доля от лучшего века, ниже которой не опускают
FLOOR_SOULS = 2500          # и просто нижний предел, пока мир ещё молод
PEAK_NOTE = "людей в лучший век"
PEAK_BY_RACE = "народ в лучший век"
GONE_NOTE = "народов больше нет"
ZERO_NOTE = "последний раз видели"
# Мир не сразу понимает, что народа больше нет: пустые два века — ещё не
# приговор. Горстка, отсидевшаяся в глуши, за это время выходит обратно.
ZERO_GRACE = 200
# Ниже этого народ считается не вымершим, а так и не поднявшимся: мир
# помнит о нём, но отдельного события не пишет. Уходят из мира многие;
# событием становится уход тех, кто успел стать народом.
NOTABLE_PEAK = 20000
# Какую долю своего лучшего века народ должен потерять в одной беде,
# чтобы летопись назвала виновника.
BLAME_SHARE = 0.35
HURT_SHARE = 0.10


def mercy(ctx) -> float:
    """Множитель к силе беды: 1.0 — бьёт полной мерой, 0.0 — уже не бьёт.

    Работает не как запрет, а как сопротивление: у самого дна беда
    выдыхается сама. Народ, которого и так осталось мало, вымереть всё
    равно может — но целый мир от одной беды не кончается.
    """
    world = ctx.world
    peak = int(world.notes.get(PEAK_NOTE) or 0)
    alive = world.world_population()
    floor = max(FLOOR_SOULS, int(peak * FLOOR_SHARE))
    if alive <= floor:
        return 0.0
    # Между дном и двойным дном рука слабеет плавно.
    if alive < floor * 2:
        return (alive - floor) / float(floor)
    return 1.0


def upkeep(ctx, year: int, period: int) -> None:
    """Раз в несколько лет: запоминаем лучший век и проверяем, все ли живы."""
    world = ctx.world
    alive = world.world_population()
    if alive > int(world.notes.get(PEAK_NOTE) or 0):
        world.notes[PEAK_NOTE] = alive
    check_extinction(ctx, year, ctx.date_in(ctx.rng("extinction", year), year),
                     ctx.rng("extinction_text", year))


# ---------------------------------------------------------------------------
# Гибель народа
# ---------------------------------------------------------------------------

def check_extinction(ctx, year: int, date, rng) -> None:
    """Раса, которой больше нет: последний народ угас, и это конец.

    Такое случается редко и почти всегда после тяжёлой беды — поэтому
    вместе с гибелью народа летопись называет и ту беду, что взяла его
    больше всех. Народы, которые так и не поднялись выше горстки душ,
    уходят тихо: мир записывает их, но не оплакивает.
    """
    world = ctx.world
    alive = world.population_by_race()
    peaks = world.notes.setdefault(PEAK_BY_RACE, {})
    gone = world.notes.setdefault(GONE_NOTE, {})
    zeros = world.notes.setdefault(ZERO_NOTE, {})
    for race in races_mod.RACES:
        if race.id not in world.race_awakening:
            continue
        souls = int(alive.get(race.id, 0))
        if souls > int(peaks.get(race.id, 0)):
            peaks[race.id] = souls
        if race.id in gone:
            continue
        if souls > 0:
            zeros.pop(race.id, None)
            continue
        first = zeros.setdefault(race.id, year)
        if year - int(first) < ZERO_GRACE:
            continue
        gone[race.id] = year
        zeros.pop(race.id, None)
        if int(peaks.get(race.id, 0)) < NOTABLE_PEAK:
            continue          # народ, который так и не стал народом
        peak = int(peaks.get(race.id, 0))
        killer, toll = _worst_calamity(world, race.id)
        # Летопись не валит всё на первую попавшуюся беду: если народ
        # ушёл сам, так и будет записано.
        if killer is not None and toll >= peak * BLAME_SHARE:
            blame = "убит"
        elif killer is not None and toll >= peak * HURT_SHARE:
            blame = "подкошен"
        else:
            killer, blame = None, "угас"
        title, text = texts.race_gone(rng, race, year, killer, blame)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="race_gone",
            title=title, text=text, importance=5, race_id=race.id,
            subjects=[killer.id] if killer is not None else [])


def is_gone(world, race_id: str) -> bool:
    """Народ, которого больше нет: назад такие не возвращаются."""
    return race_id in (world.notes.get(GONE_NOTE) or {})


def _worst_calamity(world, race_id: str):
    """Беда, которая взяла этот народ больше всех прочих, и её счёт."""
    best, best_toll = None, 0
    for calamity in world.calamities.values():
        toll = calamity.deaths_by_race.get(race_id, 0)
        if toll > best_toll:
            best, best_toll = calamity, toll
    return best, best_toll


__all__ = ["aftermath", "check_extinction", "is_gone", "mercy",
           "upkeep", "GREAT"]
