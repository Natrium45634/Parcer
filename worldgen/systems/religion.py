# -*- coding: utf-8 -*-
"""Вера: рождение богов, храмы, миссионерство, расколы, гонения и забвение.

Религия появляется не сразу: в первые века мир обходится безымянными
духами, и лишь потом кто-то впервые слышит имена богов. Дальше вера
растёт, обрастает храмами, становится государственной, раскалывается на
ереси, воюет за правоту, ветшает — и однажды её забывают, оставив пустые
храмы. Эти храмы можно найти через тысячу лет и поднять веру заново.

У каждого мира свой религиозный нрав: в одном девять богов на общий круг,
в другом десяток мелких родовых культов, в третьем — суровое единобожие,
а тёмные боги почти не встречаются.
"""

from __future__ import annotations

from . import calamity as calamity_mod
from .. import narrative_faith as texts
from .. import pantheon as pan
from .. import races as races_mod
from ..models import ACTIVE
from ..timeline import DAYS_IN_MONTH, MONTHS_IN_YEAR

FAITH_RATE = 0.0075         # годовой шанс рождения новой веры
SPREAD_RATE = 0.075         # миссионерство
TEMPLE_RATE = 0.03
SCHISM_RATE = 0.0045
BLESS_RATE = 0.02
PERSECUTION_RATE = 0.010
FESTIVAL_RATE = 0.006

PANTHEON_STYLES = ("многобожие", "родовые культы", "единобожие")


# ---------------------------------------------------------------------------
# Нрав мира
# ---------------------------------------------------------------------------

def prepare(ctx) -> None:
    world = ctx.world
    rng = ctx.rng("faith", "bias")

    ctx.piety = rng.uniform(0.45, 1.9)
    ctx.dark_tilt = rng.uniform(-0.6, 0.7)
    ctx.faith_style = rng.weighted((("многобожие", 3.0), ("родовые культы", 2.0),
                                    ("единобожие", 1.2)))
    # Вера рождается не в первый день мира: обычно во вторую-третью эпоху.
    era_index = rng.weighted(((0, 1.0), (1, 4.0), (2, 2.0)))
    era = world.eras[min(era_index, len(world.eras) - 1)]
    ctx.faith_dawn = era.start_year + rng.randint(0, max(1, int(era.length * 0.6)))
    ctx.faith_seen = set()

    world.notes["вера мира"] = {
        "устройство": ctx.faith_style,
        "набожность": round(ctx.piety, 2),
        "склонность к тьме": round(ctx.dark_tilt, 2),
        "первая вера": ctx.faith_dawn,
    }


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    if year < getattr(ctx, "faith_dawn", 10 ** 9):
        return
    _maybe_new_faith(ctx, year)
    _maybe_spread(ctx, year)
    _maybe_temple(ctx, year)
    _maybe_schism(ctx, year)
    _maybe_blessing(ctx, year)
    _maybe_persecution(ctx, year)
    _maybe_festival(ctx, year)
    _blame_calamities(ctx, year)
    _bless_champions(ctx, year)
    _check_revivals(ctx, year)


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    world.refresh_faiths()
    _inherit_faiths(ctx, year)
    _update_states(ctx, year)
    _state_religions(ctx, year)
    _ruined_temples(ctx, year)
    _high_priests(ctx, year)


# ---------------------------------------------------------------------------
# Рождение веры
# ---------------------------------------------------------------------------

def _race_alignment(ctx, rng, race) -> int:
    """К какому мировоззрению тянет народ."""
    tilt = ctx.dark_tilt
    if race.category == races_mod.EVIL:
        return rng.weighted(((-3, 3.0), (-2, 3.0), (-1, 1.0)))
    if race.id == "dark_elf":
        return rng.weighted(((-3, 2.0), (-2, 3.0), (-1, 2.0), (0, 1.0)))
    if race.category == races_mod.BEASTFOLK:
        return rng.weighted(((2, 1.5), (1, 2.0), (0, 2.5), (-1, 1.5)))
    pairs = [(3, 1.2), (2, 2.5), (1, 2.5), (0, 2.0), (-1, 1.5), (-2, 0.8), (-3, 0.3)]
    shifted = []
    for level, weight in pairs:
        if tilt > 0 and level < 0:
            weight *= 1.0 + tilt * 2.0
        elif tilt < 0 and level > 0:
            weight *= 1.0 - tilt * 1.5
        shifted.append((level, max(0.05, weight)))
    return rng.weighted(shifted)


def _pick_faith_race(ctx, rng):
    world = ctx.world
    populations = world.population_by_race()
    pairs = []
    for race in races_mod.RACES:
        people = populations.get(race.id, 0)
        if people < 200:
            continue
        weight = float(people) ** 0.55
        if not world.faiths_of_race(race.id):
            weight *= 3.5          # народ без веры её скорее и обретёт
        else:
            weight *= 0.35
        pairs.append((race, weight))
    if not pairs:
        return None
    return rng.weighted(pairs)


def _domain_pool(rng, race, alignment: int, used) -> list:
    """Подбирает сферы под мировоззрение и народ."""
    pairs = []
    race_name = race.name.lower()
    for domain in pan.DOMAINS:
        if domain.key in used:
            continue
        weight = 1.0
        # Совпадение по духу: светлый бог не берёт себе яд и страх.
        distance = abs(domain.light * 1.5 - alignment)
        weight *= max(0.03, 2.6 - distance)
        for tag in domain.tags:
            if tag in race_name or race_name.startswith(tag[:5]):
                weight *= 3.0
                break
        pairs.append((domain, weight))
    return pairs


def _make_deity(ctx, rng, race, faith_alignment: int, year: int, used_domains,
                faith_id: str = ""):
    world = ctx.world
    sex = rng.weighted((("m", 4.0), ("f", 4.0), ("n", 0.8)))
    alignment = max(-3, min(3, faith_alignment + rng.weighted(
        ((0, 4.0), (1, 1.2), (-1, 1.2)))))

    pairs = _domain_pool(rng, race, alignment, used_domains)
    domains = []
    for _ in range(rng.weighted(((1, 2.0), (2, 3.5), (3, 2.5), (4, 1.0)))):
        if not pairs:
            break
        domain = rng.weighted(pairs)
        domains.append(domain.key)
        used_domains.add(domain.key)
        pairs = [(d, w) for d, w in pairs if d.key != domain.key]

    titles = pan.DARK_TITLES if alignment <= -2 else pan.TITLES
    title = rng.choice(titles.get(sex, titles["m"]))
    first = pan.DOMAINS_BY_KEY[domains[0]] if domains else None
    deity = world.add_deity(
        given_name=ctx.forge.deity(rng, race, sex), title=title, sex=sex,
        race_id=race.id, faith_id=faith_id, domains=domains,
        alignment=alignment,
        symbol=rng.choice(first.symbols) if first and first.symbols else "знак",
        festival_name=(rng.choice(first.feast) if first and first.feast
                       else "День Бога"),
        festival_month=rng.randint(1, MONTHS_IN_YEAR),
        festival_day=rng.randint(1, DAYS_IN_MONTH),
        revealed=ctx.date_in(rng, year),
    )
    deity.epithet = texts.deity_epithet(rng, title, domains)
    return deity


def _maybe_new_faith(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("faith_born", year)
    chance = ctx.rate(FAITH_RATE) * ctx.piety
    if ctx.faith_style == "единобожие":
        chance *= 0.55
    elif ctx.faith_style == "родовые культы":
        chance *= 1.5
    roots = sum(1 for fid in world.living_faiths
                if world.faiths[fid].kind != pan.HERESY)
    chance *= max(0.25, 1.0 - roots * 0.11)
    if not rng.chance(chance):
        return
    race = _pick_faith_race(ctx, rng)
    if race is None:
        return
    _found_faith(ctx, rng, race, year)


def _found_faith(ctx, rng, race, year: int, revived_from=None):
    world = ctx.world
    alignment = _race_alignment(ctx, rng, race)

    if race.category == races_mod.BEASTFOLK or (
            race.category == races_mod.EVIL and rng.chance(0.3)):
        kind = pan.ANCESTRAL
        count = rng.randint(2, 4)
    elif ctx.faith_style == "единобожие":
        kind = pan.CULT if rng.chance(0.7) else pan.PANTHEON
        count = 1 if kind == pan.CULT else rng.randint(2, 3)
    elif ctx.faith_style == "родовые культы":
        kind = pan.CULT if rng.chance(0.55) else pan.PANTHEON
        count = 1 if kind == pan.CULT else rng.randint(2, 4)
    else:
        kind = pan.PANTHEON
        count = rng.randint(3, 9)

    date = ctx.date_in(rng, year)
    faith = world.add_faith(
        name="", kind=kind, founded=date, alignment=alignment,
        race_ids=[race.id], forbidden=alignment <= pan.FORBIDDEN_FROM,
    )

    used = set()
    deities = [_make_deity(ctx, rng, race, alignment, year, used, faith.id)
               for _ in range(count)]
    faith.deity_ids = [deity.id for deity in deities]
    faith.chief_deity_id = deities[0].id if deities else ""
    faith.name = ctx.forge.unique(
        "faith", lambda: texts.faith_name(rng, kind, deities, alignment, race), rng)

    prophet = _make_priest(ctx, rng, race, year, rank=2, role="пророк")
    prophet.faith_id = faith.id
    prophet.patron_deity_id = faith.chief_deity_id
    faith.founder_id = prophet.id
    faith.high_priest_id = prophet.id

    _seed_followers(ctx, rng, faith, race, prophet)

    title, text = texts.faith_born(rng, faith, prophet, deities, race, world)
    # Первые веры мира — событие эпохальное; сотый мелкий культ — уже нет.
    born_before = len(world.faiths)
    importance = 4 if born_before <= 4 or len(deities) >= 4 else 3
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="faith_born",
        title=title, text=text, importance=importance, actors=[prophet.id],
        subjects=[faith.id] + faith.deity_ids[:3],
        region_id=prophet.origin_region, race_id=race.id)
    return faith


def _make_priest(ctx, rng, race, year: int, rank: int = 1, role: str = "жрец",
                 region_id: str = "", home_id: str = ""):
    sex = "f" if rng.chance(0.45) else "m"
    title = pan.priest_title(race.id, rank, sex)
    figure = ctx.make_figure(
        rng, race, year, role=role, region_id=region_id, title=title, sex=sex,
        home_id=home_id, epithet_chance=0.5)
    return figure


def _seed_followers(ctx, rng, faith, race, prophet) -> None:
    """Первые верующие: родное поселение пророка и соседи того же народа."""
    world = ctx.world
    targets = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.race_id == race.id and not settlement.faith_id:
            targets.append(settlement)
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.race_id == race.id and not tribe.faith_id:
            targets.append(tribe)
    for camp_id in world.active_camps:
        camp = world.camps[camp_id]
        if camp.race_id == race.id and not camp.faith_id:
            targets.append(camp)
    if not targets:
        return
    count = max(1, min(len(targets), rng.randint(2, 7)))
    for item in rng.sample(sorted(targets, key=lambda x: x.id), count):
        item.faith_id = faith.id
        if prophet.home_id == "":
            prophet.home_id = item.id
            prophet.origin_region = getattr(item, "region_id", "")


# ---------------------------------------------------------------------------
# Миссионерство
# ---------------------------------------------------------------------------

def _faith_regions(world, faith) -> set:
    regions = set()
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.faith_id == faith.id:
            regions.add(settlement.region_id)
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.faith_id == faith.id:
            regions.add(tribe.region_id)
    return regions


def _maybe_spread(ctx, year: int) -> None:
    world = ctx.world
    if not world.living_faiths:
        return
    rng = ctx.rng("faith_spread", year)
    if not rng.chance(ctx.rate(SPREAD_RATE) * ctx.piety):
        return

    pairs = []
    for faith_id in world.living_faiths:
        faith = world.faiths[faith_id]
        if faith.status == pan.FADING:
            continue
        weight = max(1.0, float(faith.followers) ** 0.45)
        if faith.forbidden:
            weight *= 0.35          # запретная вера расходится тихо и медленно
        pairs.append((faith, weight))
    if not pairs:
        return
    faith = rng.weighted(pairs)

    home = _faith_regions(world, faith)
    if not home:
        return
    reachable = set(home)
    for region_id in home:
        region = world.regions.get(region_id)
        if region is not None:
            reachable.update(region.neighbors)

    candidates = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.faith_id == faith.id or settlement.region_id not in reachable:
            continue
        candidates.append((settlement, _affinity(world, faith, settlement.race_id,
                                                 settlement.faith_id, year)))
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.faith_id == faith.id or tribe.region_id not in reachable:
            continue
        candidates.append((tribe, _affinity(world, faith, tribe.race_id,
                                            tribe.faith_id, year) * 1.6))
    candidates = [(item, weight) for item, weight in candidates if weight > 0]
    if not candidates:
        return

    target = rng.weighted(candidates)
    is_tribe = hasattr(target, "word") and hasattr(target, "chief_id")
    foreign = target.race_id not in faith.race_ids
    target.faith_id = faith.id
    if foreign and target.race_id not in faith.race_ids:
        faith.race_ids.append(target.race_id)

    preacher = None
    if foreign or rng.chance(0.25):
        race = races_mod.get_race(faith.race_ids[0])
        preacher = _make_priest(ctx, rng, race, year, rank=1, role="миссионер",
                                region_id=getattr(target, "region_id", ""))
        preacher.faith_id = faith.id

    # Переход одного города в свою же веру — дело обычное; в летопись
    # попадают обращения чужого народа и крупных городов.
    notable = foreign or is_tribe or getattr(target, "is_capital", False)
    if not notable and not rng.chance(0.25):
        return
    date = ctx.date_in(rng, year)
    name = target.full_name if hasattr(target, "full_name") else target.name
    title, text = texts.conversion(rng, faith, name, preacher, tribal=is_tribe)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="faith_spread",
        title=title, text=text, importance=3 if foreign else 2,
        actors=[preacher.id] if preacher is not None else [],
        subjects=[faith.id, target.id],
        region_id=getattr(target, "region_id", ""), race_id=target.race_id)


def _affinity(world, faith, race_id: str, current_faith_id: str,
              year: int) -> float:
    """Насколько легко этому народу принять эту веру.

    Молодая вера держится своего народа. Древняя расходится по всему
    свету: за тысячу лет к ней привыкают и соседи.
    """
    age_bonus = min(0.55, max(0, year - faith.founded.year) / 4000.0)
    if race_id in faith.race_ids:
        weight = 3.0
    else:
        race = races_mod.RACES_BY_ID.get(race_id)
        home = races_mod.RACES_BY_ID.get(faith.race_ids[0]) if faith.race_ids else None
        if race is not None and home is not None and race.group == home.group:
            weight = 0.8 + age_bonus
        else:
            weight = 0.16 + age_bonus
    # Светлые народы неохотно идут в тёмную веру, и наоборот.
    race = races_mod.RACES_BY_ID.get(race_id)
    if faith.alignment <= -2:
        friendly = race is not None and (race.category == races_mod.EVIL
                                         or race.id == "dark_elf")
        weight *= 2.2 if friendly else 0.22
    elif faith.alignment >= 2:
        hostile = race is not None and race.category == races_mod.EVIL
        weight *= 0.3 if hostile else 1.1

    if current_faith_id:
        current = world.faiths.get(current_faith_id)
        weight *= 0.3
        # Совсем молодую веру не растаскивают: ей дают укорениться.
        if current is not None and year - current.founded.year < 200:
            weight *= 0.35
        if current is not None and current.status in (pan.FADING,):
            weight *= 2.5
        if current is not None and abs(current.alignment - faith.alignment) >= 4:
            weight *= 0.4
    if faith.followers > 400000:
        weight *= 1.4
    return weight


# ---------------------------------------------------------------------------
# Наследование веры и государственные религии
# ---------------------------------------------------------------------------

def _inherit_faiths(ctx, year: int) -> None:
    """Новые города наследуют веру своей страны, племена — веру сородичей."""
    world = ctx.world
    rng = ctx.rng("faith_inherit", year)
    by_race = {}
    for faith_id in world.living_faiths:
        faith = world.faiths[faith_id]
        for race_id in faith.race_ids:
            current = by_race.get(race_id)
            if current is None or faith.followers > current.followers:
                by_race[race_id] = faith

    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.faith_id:
            continue
        polity = world.polities.get(settlement.polity_id)
        if polity is not None and polity.faith_id:
            settlement.faith_id = polity.faith_id
            continue
        faith = by_race.get(settlement.race_id)
        if faith is not None and rng.chance(0.3):
            settlement.faith_id = faith.id

    for group in (world.active_tribes, world.active_camps):
        table = world.tribes if group is world.active_tribes else world.camps
        for item_id in group:
            item = table[item_id]
            if item.faith_id:
                continue
            faith = by_race.get(item.race_id)
            if faith is not None and rng.chance(0.18):
                item.faith_id = faith.id


def _state_religions(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("state_faith", year)
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        counts = {}
        total = 0
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is None or settlement.status != ACTIVE:
                continue
            total += 1
            if settlement.faith_id:
                counts[settlement.faith_id] = counts.get(settlement.faith_id, 0) + 1
        if not counts or not total:
            continue
        best_id, best = max(sorted(counts.items()), key=lambda pair: pair[1])
        if best / float(total) < 0.55 or polity.faith_id == best_id:
            continue
        faith = world.faiths.get(best_id)
        if faith is None or faith.status == pan.FORGOTTEN:
            continue

        old = polity.faith_id
        polity.faith_id = best_id
        if polity.id not in faith.polity_ids:
            faith.polity_ids.append(polity.id)
        previous = world.faiths.get(old)
        if previous is not None and polity.id in previous.polity_ids:
            previous.polity_ids.remove(polity.id)

        ruler = world.figures.get(polity.ruler_id)
        if ruler is not None:
            ruler.faith_id = best_id
        date = ctx.date_in(rng, year)
        title, text = texts.state_faith(rng, polity, faith, ruler)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="state_faith",
            title=title, text=text, importance=3,
            actors=[ruler.id] if ruler is not None else [],
            subjects=[polity.id, faith.id], race_id=polity.race_id)

        if faith.forbidden and rng.chance(0.5):
            world.add_event(
                date=date, era_index=world.era_index_at(year), kind="dark_state",
                title="Тёмная вера у власти: %s" % polity.name,
                text="Соседи узнают, что в стране по имени %s теперь молятся "
                     "открыто тому, кому молиться запрещено. Послов отзывают, "
                     "границы закрывают." % polity.name,
                importance=4, subjects=[polity.id, faith.id],
                race_id=polity.race_id)


# ---------------------------------------------------------------------------
# Храмы
# ---------------------------------------------------------------------------

TEMPLE_WORDS = (("Храм", 3.0), ("Святилище", 2.0), ("Капище", 1.0),
                ("Обитель", 1.0), ("Дом", 0.8))


def _maybe_temple(ctx, year: int) -> None:
    world = ctx.world
    if not world.living_faiths:
        return
    rng = ctx.rng("temple", year)
    if not rng.chance(ctx.rate(TEMPLE_RATE) * ctx.piety):
        return

    pairs = []
    for faith_id in world.living_faiths:
        faith = world.faiths[faith_id]
        if faith.followers <= 0:
            continue
        pairs.append((faith, max(1.0, float(faith.followers) ** 0.4)))
    if not pairs:
        return
    faith = rng.weighted(pairs)

    options = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.faith_id != faith.id:
            continue
        weight = float(max(50, settlement.population))
        if settlement.is_capital:
            weight *= 2.5
        options.append((settlement, weight))
    if not options:
        return
    settlement = rng.weighted(options)

    deity = world.deities.get(faith.chief_deity_id)
    if faith.deity_ids and rng.chance(0.5):
        deity = world.deities.get(rng.choice(faith.deity_ids)) or deity
    race = races_mod.get_race(settlement.race_id)
    founder = _make_priest(ctx, rng, race, year, rank=0, role="строитель храма",
                           region_id=settlement.region_id, home_id=settlement.id)
    founder.faith_id = faith.id
    if deity is not None:
        founder.patron_deity_id = deity.id

    grandeur = 1
    if settlement.is_capital and rng.chance(0.5):
        grandeur = 3
    elif settlement.population > 4000 or rng.chance(0.3):
        grandeur = 2
    word = rng.weighted(TEMPLE_WORDS)
    name = "%s %s" % (word, settlement.name)
    date = ctx.date_in(rng, year)
    temple = world.add_temple(
        name=name, faith_id=faith.id,
        deity_id=deity.id if deity is not None else "",
        settlement_id=settlement.id, region_id=settlement.region_id,
        founded=date, founder_id=founder.id, grandeur=grandeur)

    title, text = texts.temple_built(rng, temple, faith, deity, settlement, founder)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="temple_built",
        title=title, text=text, importance=3 if grandeur >= 3 else 2,
        actors=[founder.id], subjects=[temple.id, faith.id],
        region_id=settlement.region_id, race_id=settlement.race_id)


def _ruined_temples(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("temple_ruin", year)
    for temple in world.temples.values():
        if temple.status != "действует":
            continue
        settlement = world.settlements.get(temple.settlement_id)
        faith = world.faiths.get(temple.faith_id)
        dead_city = settlement is not None and settlement.status != ACTIVE
        lost_faith = faith is not None and faith.status == pan.FORGOTTEN
        if not dead_city and not lost_faith:
            continue
        date = ctx.date_in(rng, year)
        world.end_temple(temple, date,
                         "город погиб" if dead_city else "веру забыли")
        if rng.chance(0.35):
            title, text = texts.temple_ruined(rng, temple)
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="temple_ruined", title=title, text=text, importance=2,
                subjects=[temple.id], region_id=temple.region_id)


# ---------------------------------------------------------------------------
# Расколы
# ---------------------------------------------------------------------------

def _maybe_schism(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("schism", year)
    if not rng.chance(ctx.rate(SCHISM_RATE) * ctx.piety):
        return

    pairs = []
    for faith_id in world.living_faiths:
        faith = world.faiths[faith_id]
        age = year - faith.founded.year
        if age < 120 or faith.followers < 40000:
            continue
        pairs.append((faith, float(age) ** 0.5 * (faith.followers ** 0.3)))
    if not pairs:
        return
    parent = rng.weighted(pairs)

    followers = [world.settlements[sid] for sid in world.active_settlements
                 if world.settlements[sid].faith_id == parent.id]
    if len(followers) < 3:
        return

    race_id = parent.race_ids[0] if parent.race_ids else "human"
    race = races_mod.RACES_BY_ID.get(race_id) or races_mod.get_race("human")
    heretic = _make_priest(ctx, rng, race, year, rank=2, role="ересиарх")
    shift = rng.weighted(((0, 2.0), (1, 2.0), (-1, 2.5), (-2, 1.0), (2, 0.8)))
    alignment = max(-3, min(3, parent.alignment + shift))

    date = ctx.date_in(rng, year)
    deities = [world.deities[did] for did in parent.deity_ids
               if did in world.deities]
    kept = rng.sample(deities, max(1, len(deities) // 2)) if deities else []
    faith = world.add_faith(
        name="", kind=pan.HERESY, founded=date, founder_id=heretic.id,
        deity_ids=[deity.id for deity in kept],
        chief_deity_id=kept[0].id if kept else "",
        race_ids=list(parent.race_ids), alignment=alignment,
        forbidden=alignment <= pan.FORBIDDEN_FROM, parent_id=parent.id,
        high_priest_id=heretic.id)
    faith.name = ctx.forge.unique(
        "faith", lambda: texts.faith_name(rng, pan.HERESY, kept, alignment, race),
        rng)
    heretic.faith_id = faith.id

    taken = rng.sample(sorted(followers, key=lambda s: s.id),
                       max(1, int(len(followers) * rng.uniform(0.2, 0.45))))
    for settlement in taken:
        settlement.faith_id = faith.id
    # Ересь уносит с собой только тех, кто за ней пошёл.
    faith.race_ids = sorted({settlement.race_id for settlement in taken}) or \
        list(parent.race_ids[:1])
    heretic.home_id = taken[0].id if taken else heretic.home_id
    heretic.origin_region = taken[0].region_id if taken else heretic.origin_region

    title, text = texts.schism(rng, faith, parent, heretic)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="schism",
        title=title, text=text, importance=4, actors=[heretic.id],
        subjects=[faith.id, parent.id], race_id=race.id)

    # Спор о вере нередко решают железом.
    if rng.chance(0.35):
        regions = sorted({s.region_id for s in taken})
        war = calamity_mod.start_named(
            ctx, year, "holy_war", rng,
            severity=rng.weighted(((2, 3.0), (3, 2.0), (4, 0.7))),
            region_ids=regions,
            note="война между верами «%s» и «%s»" % (parent.name, faith.name))
        if war is not None:
            war.notes.append("вера: %s" % faith.id)


# ---------------------------------------------------------------------------
# Гонения и походы
# ---------------------------------------------------------------------------

def _maybe_persecution(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("persecution", year)
    if not rng.chance(ctx.rate(PERSECUTION_RATE) * ctx.piety):
        return

    dark = [world.faiths[fid] for fid in world.living_faiths
            if world.faiths[fid].forbidden and world.faiths[fid].followers > 0]
    if not dark:
        return
    target = rng.weighted([(faith, float(max(1, faith.followers)) ** 0.4)
                           for faith in dark])

    hunters = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        faith = world.faiths.get(polity.faith_id)
        if faith is None or faith.id == target.id or faith.alignment < 1:
            continue
        hunters.append(polity)
    if not hunters:
        return
    hunter = rng.choice(sorted(hunters, key=lambda p: p.id))

    inside = [world.settlements[sid] for sid in hunter.settlement_ids
              if sid in world.settlements
              and world.settlements[sid].status == ACTIVE
              and world.settlements[sid].faith_id == target.id]
    date = ctx.date_in(rng, year)

    if inside:
        dead = 0
        for settlement in inside:
            losses = int(world.settlement_realm(settlement) * rng.uniform(0.01, 0.06))
            settlement.population = max(20, settlement.population
                                        - int(losses / 5.5))
            settlement.faith_id = hunter.faith_id
            dead += losses
        title, text = texts.persecution(rng, hunter, target, dead)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="persecution",
            title=title, text=text, importance=3,
            subjects=[hunter.id, target.id], race_id=hunter.race_id)
        return

    # Своих не нашлось — идут к чужим.
    regions = sorted(_faith_regions(world, target))
    if not regions or not rng.chance(0.5):
        return
    ruler = world.figures.get(hunter.ruler_id)
    crusade = calamity_mod.start_named(
        ctx, year, "crusade", rng,
        severity=rng.weighted(((2, 3.0), (3, 2.0), (4, 0.8))),
        region_ids=regions[:4],
        note="поход страны по имени %s против веры «%s»" % (hunter.name, target.name))
    if crusade is None:
        return
    if ruler is not None:
        crusade.commander_ids.append(ruler.id)
    world.add_event(
        date=crusade.start, era_index=world.era_index_at(year), kind="crusade",
        title="Священный поход против веры «%s»" % target.name,
        text="%s объявляет поход на тех, кто молится запретному. Знамёна "
             "поднимают в тот же год; охвачены земли, где держится «%s»."
             % (hunter.full_name, target.name),
        importance=4, actors=[ruler.id] if ruler is not None else [],
        subjects=[hunter.id, target.id, crusade.id], race_id=hunter.race_id)


# ---------------------------------------------------------------------------
# Благословения и проклятия
# ---------------------------------------------------------------------------

def _maybe_blessing(ctx, year: int) -> None:
    world = ctx.world
    if not world.living_faiths:
        return
    rng = ctx.rng("blessing", year)
    if not rng.chance(ctx.rate(BLESS_RATE) * ctx.piety):
        return

    faith = world.faiths[rng.weighted(
        [(fid, max(1.0, float(world.faiths[fid].followers) ** 0.4))
         for fid in world.living_faiths])]
    deity = world.deities.get(faith.chief_deity_id)
    if faith.deity_ids and rng.chance(0.6):
        deity = world.deities.get(rng.choice(faith.deity_ids)) or deity

    candidates = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if polity.faith_id != faith.id:
            continue
        ruler = world.figures.get(polity.ruler_id)
        if ruler is not None and ruler.alive_at(year):
            candidates.append((ruler, 2.0))
    priest = world.figures.get(faith.high_priest_id)
    if priest is not None and priest.alive_at(year):
        candidates.append((priest, 2.5))
    for figure_id in list(world.figures)[-400:]:
        figure = world.figures[figure_id]
        if figure.faith_id == faith.id and figure.alive_at(year) and figure.deeds:
            candidates.append((figure, 0.6))
    if not candidates:
        return

    figure = rng.weighted(candidates)
    if figure.divine_mark:
        return
    date = ctx.date_in(rng, year)
    dark = faith.alignment <= -2
    bless = rng.chance(0.3 if dark else 0.62)

    if bless:
        reason = rng.weighted([(item, float(weight))
                               for item, weight in pan.BLESSING_REASONS])
        gift, effect = rng.choice(pan.BLESSING_GIFTS)
        figure.divine_mark = "благословение"
        figure.patron_deity_id = deity.id if deity is not None else ""
        figure.roles.append("избранник богов")
        if not figure.epithet or rng.chance(0.6):
            figure.epithet = "Благословенный" if figure.sex != "f" \
                else "Благословенная"
        # Дар богов — это годы: смерть отодвигается.
        if figure.death is not None:
            extra = int(max(5, (figure.death.year - year) * rng.uniform(0.4, 1.2)))
            from ..timeline import Date
            world.schedule_death(figure, Date.random_in_year(
                rng, figure.death.year + extra), "прожил(а) дольше положенного")
        title, text = texts.blessing(rng, figure, deity, gift, effect, reason)
        kind = "blessing"
    else:
        reason = rng.weighted([(item, float(weight))
                               for item, weight in pan.CURSE_REASONS])
        curse_name, effect = rng.choice(pan.CURSES)
        figure.divine_mark = "проклятие"
        figure.patron_deity_id = deity.id if deity is not None else ""
        figure.roles.append("проклятый богами")
        if not figure.epithet or rng.chance(0.7):
            figure.epithet = "Проклятый" if figure.sex != "f" else "Проклятая"
        if figure.death is not None and figure.death.year - year > 3 and \
                rng.chance(0.6):
            from ..timeline import Date
            world.schedule_death(figure, Date.random_in_year(
                rng, year + rng.randint(1, max(2, (figure.death.year - year) // 2))),
                "умер(ла) под проклятием")
        house = world.houses.get(figure.house_id)
        if house is not None:
            house.prestige = max(0.15, house.prestige - 1.2)
        title, text = texts.curse(rng, figure, deity, curse_name, effect, reason)
        kind = "curse"

    world.add_event(
        date=date, era_index=world.era_index_at(year), kind=kind,
        title=title, text=text, importance=3, actors=[figure.id],
        subjects=[faith.id] + ([deity.id] if deity is not None else []),
        region_id=figure.origin_region, race_id=figure.race_id)


# ---------------------------------------------------------------------------
# Состояния вер, забвение и возрождение
# ---------------------------------------------------------------------------

def _update_states(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("faith_state", year)
    total = max(1, world.world_population())

    for faith_id in list(world.living_faiths):
        faith = world.faiths[faith_id]
        share = faith.followers / float(total)
        age = year - faith.founded.year
        previous = faith.status

        if faith.followers <= 0:
            if age > 60 or faith.peak_followers > 0:
                faith.status = pan.FADING
        elif share > 0.22 or (faith.polity_ids and share > 0.06):
            faith.status = pan.DOMINANT
        elif share > 0.02 or faith.followers > 20000 or faith.polity_ids:
            faith.status = pan.RISING
        elif faith.peak_followers > faith.followers * 4 and age > 200:
            faith.status = pan.FADING
        else:
            faith.status = pan.NASCENT if age < 80 else pan.RISING

        if faith.status == pan.FADING and previous != pan.FADING and \
                rng.chance(0.5):
            title, text = texts.faith_fading(rng, faith)
            world.add_event(
                date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
                kind="faith_fading", title=title, text=text, importance=3,
                subjects=[faith.id])

        # Забвение: верующих нет давно и вера уже немолода.
        if faith.followers <= 0 and faith.status == pan.FADING:
            faith.notes.append("пусто:%d" % year)
            empty = [note for note in faith.notes if note.startswith("пусто:")]
            if len(empty) >= 6 and age > 150:
                _forget_faith(ctx, rng, faith, year)


def _forget_faith(ctx, rng, faith, year: int) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year)
    temples = [world.temples[tid] for tid in faith.temple_ids
               if tid in world.temples]
    world.end_faith(faith, date, "не осталось верующих", pan.FORGOTTEN)

    # Пустые храмы становятся следами — их найдут через века.
    made = 0
    for temple in temples:
        if made >= 3:
            break
        if temple.status == "действует":
            world.end_temple(temple, date, "веру забыли")
        region_id = temple.region_id
        if not region_id:
            continue
        relic = world.add_relic(
            name="%s забытой веры «%s»" % (
                "Храм" if temple.grandeur >= 2 else "Святилище", faith.name),
            kind="храм забытой веры", calamity_id="", region_id=region_id,
            created=date, potency=min(5, 2 + temple.grandeur),
            race_id=faith.race_ids[0] if faith.race_ids else "")
        relic.notes.append("вера:%s" % faith.id)
        made += 1

    title, text = texts.faith_forgotten(rng, faith, len(temples))
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="faith_forgotten",
        title=title, text=text,
        importance=4 if faith.peak_followers > 50000 else 2,
        subjects=[faith.id])


def _check_revivals(ctx, year: int) -> None:
    """Потревоженный храм забытой веры возвращает её в мир."""
    world = ctx.world
    rng = ctx.rng("faith_revival", year)
    for relic in world.relics.values():
        if relic.kind != "храм забытой веры" or relic.status != "потревожен":
            continue
        if "поднято" in relic.notes:
            continue
        relic.notes.append("поднято")
        faith_id = ""
        for note in relic.notes:
            if note.startswith("вера:"):
                faith_id = note.split(":", 1)[1]
        faith = world.faiths.get(faith_id)
        if faith is None or faith.status != pan.FORGOTTEN:
            continue
        if not rng.chance(0.45):
            continue

        race_id = faith.race_ids[0] if faith.race_ids else "human"
        race = races_mod.RACES_BY_ID.get(race_id) or races_mod.get_race("human")
        prophet = _make_priest(ctx, rng, race, year, rank=2, role="возродитель веры",
                               region_id=relic.region_id)
        prophet.faith_id = faith.id
        faith.status = pan.RISING
        faith.high_priest_id = prophet.id
        faith.ended = None
        faith.end_reason = ""
        faith.notes.append("возрождена в %d году" % year)
        if faith.id not in world.living_faiths:
            world.living_faiths.append(faith.id)
        for deity_id in faith.deity_ids:
            deity = world.deities.get(deity_id)
            if deity is not None:
                deity.status = "почитается"

        for settlement_id in world.active_settlements:
            settlement = world.settlements[settlement_id]
            if settlement.region_id == relic.region_id and rng.chance(0.6):
                settlement.faith_id = faith.id
        relic.status = "исчерпан"

        gap = year - (faith.founded.year if faith.founded else year)
        date = ctx.date_in(rng, year)
        title, text = texts.faith_revived(rng, faith, prophet, gap)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="faith_revived",
            title=title, text=text, importance=4, actors=[prophet.id],
            subjects=[faith.id, relic.id], region_id=relic.region_id)
        return


# ---------------------------------------------------------------------------
# Мелочи: верховные жрецы, праздники, гнев богов
# ---------------------------------------------------------------------------

def _high_priests(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("high_priest", year)
    for faith_id in world.living_faiths:
        faith = world.faiths[faith_id]
        priest = world.figures.get(faith.high_priest_id)
        if priest is not None and priest.alive_at(year):
            continue
        if faith.followers <= 0:
            continue
        race_id = faith.race_ids[0] if faith.race_ids else "human"
        race = races_mod.RACES_BY_ID.get(race_id) or races_mod.get_race("human")
        new_priest = _make_priest(ctx, rng, race, year, rank=0,
                                  role="верховный жрец")
        new_priest.faith_id = faith.id
        new_priest.patron_deity_id = faith.chief_deity_id
        faith.high_priest_id = new_priest.id
        if rng.chance(0.25):
            title, text = texts.high_priest(rng, faith, new_priest)
            world.add_event(
                date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
                kind="high_priest", title=title, text=text, importance=2,
                actors=[new_priest.id], subjects=[faith.id], race_id=race.id)


def _maybe_festival(ctx, year: int) -> None:
    world = ctx.world
    if not world.living_faiths:
        return
    rng = ctx.rng("festival", year)
    if not rng.chance(ctx.rate(FESTIVAL_RATE) * ctx.piety):
        return
    faith = world.faiths[rng.choice(world.living_faiths)]
    if not faith.deity_ids or faith.followers <= 0:
        return
    deity = world.deities.get(rng.choice(faith.deity_ids))
    if deity is None:
        return
    from ..timeline import Date
    date = Date(year, deity.festival_month, deity.festival_day)
    title, text = texts.festival(rng, deity, faith)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="festival",
        title=title, text=text, importance=1, subjects=[faith.id, deity.id])


def _bless_champions(ctx, year: int) -> None:
    """Победитель большой беды нередко оказывается избранником бога."""
    world = ctx.world
    rng = ctx.rng("champion", year)
    light = [world.faiths[fid] for fid in world.living_faiths
             if world.faiths[fid].alignment >= 1 and world.faiths[fid].deity_ids]
    if not light:
        return
    for calamity in world.calamities.values():
        if calamity.end is None or calamity.end.year != year:
            continue
        if calamity.severity < 3 or not calamity.hero_ids:
            continue
        if any(note.startswith("избранник:") for note in calamity.notes):
            continue
        if not rng.chance(0.4):
            continue
        hero = world.figures.get(calamity.hero_ids[0])
        if hero is None:
            continue
        faith = rng.choice(light)
        deity = world.deities.get(rng.choice(faith.deity_ids))
        if deity is None:
            continue
        calamity.notes.append("избранник:%s" % hero.id)
        hero.faith_id = faith.id
        hero.patron_deity_id = deity.id
        if not hero.divine_mark:
            hero.divine_mark = "благословение"
            hero.roles.append("избранник богов")
        title, text = texts.champion(rng, hero, deity, calamity)
        world.add_event(
            date=calamity.end, era_index=world.era_index_at(year),
            kind="champion", title=title, text=text, importance=4,
            actors=[hero.id], subjects=[calamity.id, faith.id, deity.id],
            race_id=hero.race_id)
        return


def _blame_calamities(ctx, year: int) -> None:
    """Большую беду нередко приписывают воле тёмного бога."""
    world = ctx.world
    rng = ctx.rng("blame", year)
    dark_faiths = [world.faiths[fid] for fid in world.living_faiths
                   if world.faiths[fid].alignment <= -2]
    if not dark_faiths:
        return
    for calamity_id in world.active_calamities:
        calamity = world.calamities[calamity_id]
        if calamity.start.year != year or calamity.severity < 3:
            continue
        if calamity.kind == "religious":
            continue          # войну за веру на богов не спишешь
        if any(note.startswith("гнев:") for note in calamity.notes):
            continue
        if not rng.chance(0.4):
            continue
        faith = rng.choice(dark_faiths)
        if not faith.deity_ids:
            continue
        deity = world.deities.get(rng.choice(faith.deity_ids))
        if deity is None:
            continue
        calamity.notes.append("гнев:%s" % deity.id)
        title, text = texts.divine_blame(rng, calamity, deity, faith)
        world.add_event(
            date=calamity.start, era_index=world.era_index_at(year),
            kind="divine_blame", title=title, text=text, importance=3,
            subjects=[calamity.id, faith.id, deity.id])
        return
