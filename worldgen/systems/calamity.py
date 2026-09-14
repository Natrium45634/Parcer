# -*- coding: utf-8 -*-
"""Бедствия: приход, ход, разрешение и долгий след.

Бедствие живёт по расписанию, составленному в день его начала: сколько
лет продлится, каких земель коснётся, скольких унесёт и чем кончится.
Дальше движок год за годом приводит приговор в исполнение: убивает людей,
рушит города, устраивает сражения, а в конце выводит на сцену тех, кто
всё это остановил.

Три вещи делают миры непохожими друг на друга:

* у каждого мира своя предрасположенность к бедам — один живёт под
  драконами, другой изо льда не вылезает;
* беды накладываются друг на друга и усиливают одна другую;
* после себя они оставляют следы, которые через тысячи лет просыпаются
  и дают начало новым, уже небольшим бедам.
"""

from __future__ import annotations

from . import houses as houses_mod
from . import succession
from .. import catastrophe as cat
from .. import narrative_calamity as texts
from .. import races as races_mod
from ..models import ACTIVE, MINOR, RUINED
from ..morph import accusative_noun, genitive_phrase, phrase
from ..timeline import Date
from ..world import RURAL_FACTOR

CALAMITY_RATE = 0.011          # годовой шанс, что где-то начнётся беда
RELIC_WAKE_RATE = 0.0013       # годовой шанс пробуждения на один спящий след
MIN_SETTLEMENT = 45            # ниже этого поселение считается погибшим

# Прозвища победителей по виду врага.
HERO_EPITHETS = {
    "demon": (("Демоноборец", "Демоноборица"), ("Багровый Щит", "Багровый Щит")),
    "dragon": (("Драконоборец", "Драконоборица"), ("Змеевержец", "Змеевержица")),
    "undead": (("Упокоитель", "Упокоительница"), ("Светоносный", "Светоносная")),
    "deep_one": (("Отлив", "Отлив"), ("Береговой Щит", "Береговой Щит")),
    "swarm": (("Жнец Роя", "Жница Роя"), ("Хитинолом", "Хитинолом")),
    "void": (("Швейный Мастер", "Швейная Мастерица"), ("Молчащий", "Молчащая")),
    "": (("Победитель", "Победительница"), ("Заступник", "Заступница")),
}

# Слова для названий следов бедствий: вид -> (существительное, род, нужен ли враг).
RELIC_FORMS = {
    "печать": ("Печать", "f", False),
    "разлом": ("Разлом", "m", False),
    "прореха": ("Прореха", "f", False),
    "логово": ("Логово", "n", False),
    "драконье логово": ("Логово", "n", False),
    "кладка": ("Кладка", "f", False),
    "кладка яиц": ("Кладка", "f", False),
    "гробница": ("Гробница", "f", False),
    "затонувший храм": ("Затонувший храм", "m", False),
    "затонувший город": ("Затонувший город", "m", False),
    "вмёрзший город": ("Вмёрзший город", "m", False),
    "проклятое место": ("Проклятое место", "n", False),
    "проклятое поле": ("Проклятое поле", "n", False),
    "проклятая бухта": ("Проклятая бухта", "f", False),
    "мёртвая зона": ("Мёртвая зона", "f", False),
    "изменённые земли": ("Изменённые земли", "p", False),
    "выжженная земля": ("Выжженная земля", "f", False),
    "выеденные земли": ("Выеденные земли", "p", False),
    "пепельная пустошь": ("Пепельная пустошь", "f", False),
    "ледяная пустошь": ("Ледяная пустошь", "f", False),
    "наступающая пустыня": ("Наступающая пустыня", "f", False),
    "высохшее море": ("Высохшее море", "n", False),
    "затопленные земли": ("Затопленные земли", "p", False),
    "разлом в земле": ("Разлом в земле", "m", False),
    "руины": ("Руины", "p", False),
    "новый остров": ("Новый остров", "m", False),
    "клад": ("Клад", "m", False),
    "опасная реликвия": ("Реликвия", "f", False),
    "осколок бури": ("Осколок бури", "m", False),
    "башня без хозяина": ("Башня без хозяина", "f", False),
    "моровое кладбище": ("Моровое кладбище", "n", False),
    "чумной город": ("Чумной город", "m", False),
    "разбитый флот": ("Разбитый флот", "m", False),
    "год без солнца в памяти": ("Память о годе без солнца", "f", False),
    "недобитый военачальник": ("Уцелевший военачальник", "m", True),
    "уцелевший дракон": ("Уцелевший дракон", "m", True),
    "уцелевший жрец": ("Уцелевший жрец", "m", True),
    "спящая матка": ("Спящая матка", "f", True),
    "уцелевшая тварь": ("Уцелевшая тварь", "f", True),
    "говорящий зверь": ("Говорящий зверь", "m", False),
    "осколок державы": ("Осколок державы", "m", False),
    "обида наследников": ("Обида наследников", "f", False),
    "вольный город": ("Вольный город", "m", False),
    "старые притязания": ("Старые притязания", "p", False),
    "новая знать": ("Новая знать", "f", False),
    "выжженный предел": ("Выжженный предел", "m", False),
    "оспоренный престол": ("Оспоренный престол", "m", False),
    "память о бунте": ("Память о бунте", "f", False),
    "проклятый род": ("Проклятый род", "m", False),
    "выжженное капище": ("Выжженное капище", "n", False),
    "память о мучениках": ("Память о мучениках", "f", False),
    "спорная земля": ("Спорная земля", "f", False),
    "разорённый храм": ("Разорённый храм", "m", False),
    "храм забытой веры": ("Храм забытой веры", "m", False),
    "идол забытого бога": ("Идол забытого бога", "m", False),
}

# Следы, которые способны сами породить новую беду.
LIVING_RELICS = (
    "недобитый военачальник", "уцелевший дракон", "уцелевший жрец",
    "спящая матка", "уцелевшая тварь", "кладка", "кладка яиц", "логово",
    "драконье логово", "гробница", "печать", "прореха", "разлом",
    "затонувший храм", "проклятое место",
)

# Следы веры не порождают новых бедствий: их пробуждение возвращает
# к жизни забытую религию (этим занимается systems/religion.py).
FAITH_RELICS = ("храм забытой веры", "идол забытого бога")


# ---------------------------------------------------------------------------
# Подготовка: характер мира
# ---------------------------------------------------------------------------

def prepare(ctx) -> None:
    """Задаёт миру его собственный нрав.

    Один мир изводят драконы, другой — лёд и мор, третий за десять тысяч
    лет не увидит ни одного демона. Без этого все миры походили бы друг
    на друга, как две одинаково перемешанные колоды.
    """
    rng = ctx.rng("calamity", "bias")
    bias = {}
    for spec in cat.CATALOG:
        bias[spec.key] = rng.uniform(0.3, 1.9)

    # Две-три беды становятся бичом именно этого мира.
    keys = sorted(bias)
    for _ in range(rng.randint(2, 3)):
        key = rng.choice(keys)
        bias[key] *= rng.uniform(2.4, 4.5)
    # А одна-две почти не встречаются.
    for _ in range(rng.randint(1, 3)):
        key = rng.choice(keys)
        bias[key] *= rng.uniform(0.05, 0.25)

    ctx.calamity_bias = bias
    ctx.calamity_last = {}
    ctx.calamity_plans = {}
    ctx.world.notes["нрав мира"] = sorted(
        bias, key=lambda key: -bias[key])[:4]


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    _advance(ctx, year)
    _maybe_start(ctx, year)
    _maybe_wake_relic(ctx, year)


def upkeep(ctx, year: int, period: int) -> None:
    ctx.world.refresh_populations()
    _close_dark_ages(ctx, year)


# ---------------------------------------------------------------------------
# Начало бедствия
# ---------------------------------------------------------------------------

def _pick_spec(ctx, year: int, rng):
    world = ctx.world
    era_index = world.era_index_at(year)
    pairs = []
    for spec in cat.CATALOG:
        low, high = spec.era_range
        if not (low <= era_index <= high):
            continue
        if spec.needs_polity and not world.active_polities:
            continue
        if spec.kind == cat.INVASION and not world.active_settlements:
            continue
        weight = spec.weight * ctx.calamity_bias.get(spec.key, 1.0)
        # Одно и то же подряд не случается: беде нужно время, чтобы забыться.
        last = ctx.calamity_last.get(spec.key)
        if last is not None:
            gap = year - last
            weight *= min(1.0, (gap / 400.0) ** 0.8 + 0.05)
        if weight > 0:
            pairs.append((spec, weight))
    if not pairs:
        return None
    return rng.weighted(pairs)


def _pick_regions(ctx, rng, spec, count: int, victim=None):
    world = ctx.world
    if victim is not None and victim.region_ids:
        chosen = list(victim.region_ids)
        rest = count - len(chosen)
        if rest > 0:
            chosen = _grow_regions(world, rng, chosen, count)
        return chosen[:max(1, count)]

    pool = list(world.regions.values())
    if spec.terrains:
        fitting = [region for region in pool if region.terrain in spec.terrains]
        if fitting:
            pool = fitting
    if not pool:
        return []
    seed_region = rng.choice(sorted(pool, key=lambda region: region.id))
    return _grow_regions(world, rng, [seed_region.id], count)


def _grow_regions(world, rng, start_ids, count: int) -> list:
    chosen = list(start_ids)
    seen = set(chosen)
    frontier = list(chosen)
    while len(chosen) < count and frontier:
        current = world.regions.get(frontier.pop(0))
        if current is None:
            continue
        for neighbor_id in rng.shuffled(current.neighbors):
            if neighbor_id in seen:
                continue
            seen.add(neighbor_id)
            chosen.append(neighbor_id)
            frontier.append(neighbor_id)
            if len(chosen) >= count:
                break
    if len(chosen) < count:
        for region_id in sorted(world.regions):
            if region_id not in seen:
                chosen.append(region_id)
                seen.add(region_id)
            if len(chosen) >= count:
                break
    return chosen


def _maybe_start(ctx, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("calamity", "start", year)
    spec_era = ctx.era_spec(year)
    chance = ctx.rate(CALAMITY_RATE) * (0.65 + spec_era.turmoil)
    # Пока мир пуст, бедствиям некого изводить.
    if not world.active_settlements and not world.active_tribes:
        return
    if not rng.chance(chance):
        return

    spec = _pick_spec(ctx, year, rng)
    if spec is None:
        return
    _start_calamity(ctx, year, spec, rng)


def _start_calamity(ctx, year: int, spec, rng, severity: int = 0,
                    parent=None, relic=None, region_ids=None):
    world = ctx.world
    severity = severity or spec.severity(rng)
    duration = spec.years(rng, severity)
    count = min(len(world.regions), spec.regions_count(rng, severity))

    victim = None
    if spec.needs_polity:
        victim = _pick_victim_polity(ctx, rng, spec, severity)
        if victim is None:
            return None
    if not region_ids:
        region_ids = _pick_regions(ctx, rng, spec, count, victim)
    region_ids = [rid for rid in region_ids if rid in world.regions]
    if not region_ids:
        return None

    host = None
    race = None
    leader = None
    generals = []
    host_size = 0
    if spec.kind == cat.INVASION:
        race, leader, generals, host = _summon_host(ctx, rng, spec, year,
                                                    region_ids, severity)
        host_size = _host_size(rng, spec, severity)

    date = ctx.date_in(rng, year)
    name = texts.calamity_name(rng, spec, host, victim)
    calamity = world.add_calamity(
        key=spec.key, kind=spec.kind, name=name, severity=severity,
        start=date, region_ids=list(region_ids),
        race_id=race.id if race is not None else "",
        leader_id=leader.id if leader is not None else "",
        general_ids=[figure.id for figure in generals],
        parent_id=parent.id if parent is not None else "",
        host_size=host_size,
    )
    if host is not None:
        calamity.notes.append(phrase(host[0], host[1], host[2]))
    calamity.notes.append("длительность: %d" % duration)
    ctx.calamity_last[spec.key] = year

    _bind_polities(ctx, calamity)
    _plan(ctx, calamity, spec, rng, duration, severity)
    if spec.kind == cat.CLIMATE:
        # Пока лёд идёт, мир не растёт: это чувствуется сразу, а не потом.
        world.add_dark_age(calamity.id, year, year + duration, region_ids,
                           min(0.85, 0.16 * severity), worldwide=(severity >= 4))
    _check_compound(ctx, calamity, rng, year)

    title, text = texts.begins(rng, world, calamity, spec, leader, generals, victim)
    importance = min(5, 2 + severity // 2 + (1 if spec.kind == cat.INVASION else 0))
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="calamity_begins",
        title=title, text=text, importance=max(3, importance),
        actors=[figure.id for figure in ([leader] if leader else []) + generals[:3]],
        subjects=[calamity.id] + ([victim.id] if victim is not None else []),
        region_id=region_ids[0], race_id=race.id if race is not None else "",
    )
    if relic is not None:
        calamity.notes.append("пробуждение следа: %s" % relic.name)
    return calamity


def start_named(ctx, year: int, spec_key: str, rng, severity: int = 0,
                region_ids=None, note: str = ""):
    """Запускает бедствие заданного вида — для войн за веру и походов."""
    spec = cat.get_spec(spec_key)
    calamity = _start_calamity(ctx, year, spec, rng, severity=severity,
                               region_ids=region_ids)
    if calamity is not None and note:
        calamity.notes.append(note)
    return calamity


def _pick_victim_polity(ctx, rng, spec, severity: int):
    world = ctx.world
    pairs = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        size = len(polity.settlement_ids)
        if spec.key == "empire_collapse" and size < 3:
            continue
        if spec.key == "feudal_fracture" and size < 2:
            continue
        pairs.append((polity, float(1 + size)))
    if not pairs:
        return None
    return rng.weighted(pairs)


# Сколько врагов приходит: от отряда чудовищ до миллионных роёв.
HOST_SIZE = {
    1: (900, 6000),
    2: (8000, 60000),
    3: (60000, 400000),
    4: (350000, 2200000),
    5: (2000000, 9000000),
}


def _host_size(rng, spec, severity: int) -> int:
    low, high = HOST_SIZE.get(min(5, severity), HOST_SIZE[2])
    value = rng.randint(low, high)
    if spec.key == "hellish_swarm":
        value *= rng.randint(6, 14)          # рой не считают поголовно
    elif spec.key == "dragon_flight":
        value = max(4, value // rng.randint(1500, 6000))   # драконов мало
    return int(value)


def _summon_host(ctx, rng, spec, year: int, region_ids, severity: int):
    """Создаёт вождя вторжения и его военачальников."""
    race = races_mod.RACES_BY_ID.get(spec.race_id) if spec.race_id else None
    mortal_lich = False
    if spec.key == "undead_tide" and rng.chance(0.4):
        # Во главе мёртвого воинства может стоять и бывший смертный.
        options = [r for r in races_mod.RACES if r.category == races_mod.CIVILIZED]
        race = rng.choice(sorted(options, key=lambda r: r.id))
        mortal_lich = True

    leader = None
    generals = []
    style_adjectives = ()
    if race is not None:
        style = ctx.forge.style_of(race)
        style_adjectives = style.adjectives
        sex = "f" if rng.chance(0.35) else "m"
        if mortal_lich:
            title = "великий лич" if sex == "m" else "великая личесса"
        else:
            pair = race.chief_titles or ("владыка", "владычица")
            title = pair[1] if (sex == "f" and len(pair) > 1) else pair[0]
        leader = ctx.make_figure(
            rng, race, year, role="вождь вторжения", region_id=region_ids[0],
            title=title, sex=sex, epithet_chance=0.95)
        leader.roles.append("бедствие мира")
        if mortal_lich:
            leader.notes.append("при жизни принадлежал(а) к смертным народам")

        low, high = spec.generals
        for _ in range(rng.randint(low, max(low, high))):
            gsex = "f" if rng.chance(0.35) else "m"
            general = ctx.make_figure(
                rng, race, year, role="военачальник вторжения",
                region_id=rng.choice(region_ids),
                title="военачальник" if gsex == "m" else "военачальница",
                sex=gsex, epithet_chance=0.8)
            generals.append(general)

    host = texts.make_host(rng, spec, style_adjectives)
    return race, leader, generals, host


def _bind_polities(ctx, calamity) -> None:
    world = ctx.world
    affected = set(calamity.region_ids)
    polities = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is not None and settlement.region_id in affected:
                polities.append(polity_id)
                break
    calamity.polity_ids = polities


def _plan(ctx, calamity, spec, rng, duration: int, severity: int) -> None:
    """Расписывает беду по годам: сколько продлится, чем кончится, где битвы."""
    end_year = calamity.start.year + max(1, duration)
    toll = spec.toll_share(rng, severity)
    resolution = rng.weighted(spec.resolutions) if spec.resolutions else "endured"

    doomed = {1: (0, 1), 2: (0, 2), 3: (1, 4), 4: (3, 8), 5: (6, 15)}[
        min(5, severity)]
    plan = {
        "end_year": end_year,
        "toll": toll,
        "resolution": resolution,
        "duration": max(1, duration),
        "battles": [],
        # Сколько поселений беда сотрёт с карты. Больше не сотрёт: иначе
        # каждое великое бедствие оставляло бы после себя пустыню.
        "doomed": rng.randint(*doomed),
    }
    if spec.kind == cat.INVASION and severity >= 2:
        count = min(6, 1 + severity)
        span = max(1, end_year - calamity.start.year)
        for index in range(count):
            share = (index + 1) / float(count + 1)
            plan["battles"].append(calamity.start.year + max(1, int(span * share)))
        if resolution in ("coalition", "heroes", "hero", "driven_back", "sealed"):
            plan["battles"].append(end_year)
    ctx.calamity_plans[calamity.id] = plan


def _check_compound(ctx, calamity, rng, year: int) -> None:
    """Беда на беду: пересечение земель усиливает обе."""
    world = ctx.world
    mine = set(calamity.region_ids)
    for other_id in list(world.active_calamities):
        if other_id == calamity.id:
            continue
        other = world.calamities[other_id]
        if not mine & set(other.region_ids):
            continue
        calamity.compounded_with.append(other.id)
        other.compounded_with.append(calamity.id)
        boost = rng.uniform(1.25, 1.7)
        calamity.strength *= boost
        other.strength *= boost
        if min(calamity.severity, other.severity) < 2:
            break
        title, text = texts.compound(rng, other, calamity)
        world.add_event(
            date=calamity.start, era_index=world.era_index_at(year),
            kind="calamity_compound", title=title, text=text,
            importance=max(3, min(5, 2 + max(calamity.severity, other.severity) // 2)),
            subjects=[calamity.id, other.id], region_id=calamity.region_ids[0],
        )
        break


# ---------------------------------------------------------------------------
# Ход бедствия
# ---------------------------------------------------------------------------

def _advance(ctx, year: int) -> None:
    world = ctx.world
    for calamity_id in list(world.active_calamities):
        calamity = world.calamities[calamity_id]
        plan = ctx.calamity_plans.get(calamity_id)
        if plan is None:
            continue
        spec = cat.get_spec(calamity.key)
        rng = ctx.rng("calamity", calamity_id, year)

        _damage(ctx, calamity, spec, plan, rng, year)

        if year in plan["battles"]:
            _fight(ctx, calamity, spec, plan, rng, year,
                   decisive=(year >= plan["end_year"]))

        elapsed = year - calamity.start.year
        if elapsed and elapsed % max(8, plan["duration"] // 3) == 0 and \
                plan["duration"] > 12 and rng.chance(0.5):
            title, text = texts.ongoing(rng, calamity, spec, elapsed)
            world.add_event(
                date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
                kind="calamity_ongoing", title=title, text=text,
                importance=2, subjects=[calamity.id],
                region_id=calamity.region_ids[0])

        if year >= plan["end_year"]:
            _resolve(ctx, calamity, spec, plan, rng, year)


def _targets(world, calamity) -> tuple:
    affected = set(calamity.region_ids)
    settlements = [world.settlements[sid] for sid in world.active_settlements
                   if world.settlements[sid].region_id in affected]
    tribes = [world.tribes[tid] for tid in world.active_tribes
              if world.tribes[tid].region_id in affected]
    camps = [world.camps[cid] for cid in world.active_camps
             if world.camps[cid].region_id in affected]
    return settlements, tribes, camps


def _damage(ctx, calamity, spec, plan, rng, year: int) -> None:
    world = ctx.world
    duration = max(1, plan["duration"])
    total = min(0.92, plan["toll"] * calamity.strength)
    annual = 1.0 - (1.0 - total) ** (1.0 / duration)
    if annual <= 0:
        return

    settlements, tribes, camps = _targets(world, calamity)
    if not settlements and not tribes and not camps:
        plan["end_year"] = min(plan["end_year"], year + 1)
        return

    for settlement in settlements:
        share = annual * rng.uniform(0.5, 1.6)
        realm = world.settlement_realm(settlement)
        dead = int(realm * min(0.85, share))
        if dead <= 0:
            continue
        settlement.population = max(0, settlement.population
                                    - int(dead / RURAL_FACTOR))
        _record_deaths(calamity, dead, settlement.polity_id, settlement.race_id)
        # Часть городов не просто теряет жителей, а гибнет целиком:
        # сожжён, вырезан, брошен. Число таких заранее ограничено планом.
        if settlement.population < MIN_SETTLEMENT:
            _destroy_settlement(ctx, calamity, settlement, rng, year)
        elif plan["doomed"] > 0 and rng.chance(min(0.12, annual * 1.2)):
            plan["doomed"] -= 1
            _destroy_settlement(ctx, calamity, settlement, rng, year)

    for group in (tribes, camps):
        for item in group:
            share = annual * rng.uniform(0.4, 1.5)
            dead = int(item.population * min(0.85, share))
            if dead <= 0:
                continue
            item.population = max(0, item.population - dead)
            _record_deaths(calamity, dead, "", item.race_id)


def _record_deaths(calamity, dead: int, polity_id: str, race_id: str) -> None:
    calamity.deaths += dead
    if polity_id:
        calamity.deaths_by_polity[polity_id] = \
            calamity.deaths_by_polity.get(polity_id, 0) + dead
    if race_id:
        calamity.deaths_by_race[race_id] = \
            calamity.deaths_by_race.get(race_id, 0) + dead


def _destroy_settlement(ctx, calamity, settlement, rng, year: int) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year)
    world.end_settlement(settlement, date, "гибель от бедствия «%s»" % calamity.name,
                         RUINED)
    calamity.settlements_lost += 1
    if calamity.severity >= 3 or rng.chance(0.35):
        title, text = texts.city_lost(rng, settlement, calamity)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="city_lost",
            title=title, text=text, importance=3,
            subjects=[settlement.id, calamity.id],
            region_id=settlement.region_id, race_id=settlement.race_id)

    polity = world.polities.get(settlement.polity_id)
    if polity is not None and not [sid for sid in polity.settlement_ids
                                   if world.settlements[sid].status == ACTIVE]:
        world.end_polity(polity, date, "погибла в бедствии «%s»" % calamity.name)
        calamity.polities_lost += 1
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="polity_fall",
            title="Гибель страны: %s" % polity.name,
            text="%s не переживает бедствие «%s»: не остаётся ни одного города."
                 % (polity.full_name, calamity.name),
            importance=4, subjects=[polity.id, calamity.id],
            race_id=polity.race_id)


# ---------------------------------------------------------------------------
# Сражения
# ---------------------------------------------------------------------------

def _battle_name(rng, world, calamity, region) -> str:
    settlements = [world.settlements[sid] for sid in world.active_settlements
                   if world.settlements[sid].region_id == (region.id if region else "")]
    if settlements and rng.chance(0.7):
        settlement = rng.choice(sorted(settlements, key=lambda s: s.id))
        form = rng.choice((
            "Битва за %s %s" % (accusative_noun(settlement.kind).lower(),
                                settlement.name),
            "Битва у стен города %s" % settlement.name,
            "Сеча под городом %s" % settlement.name,
        ))
        return form
    where = region.name if region is not None else "неведомых землях"
    return rng.choice((
        "Битва в краю по имени %s" % where,
        "Сражение на землях по имени %s" % where,
        "Битва у рубежей земли по имени %s" % where,
    ))


def _defenders(ctx, calamity, rng, year: int) -> list:
    world = ctx.world
    people = []
    for polity_id in calamity.polity_ids:
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        ruler = world.figures.get(polity.ruler_id)
        if ruler is not None and ruler.alive_at(year):
            people.append(ruler)
        else:
            house = world.houses.get(polity.house_id)
            head = world.figures.get(house.head_id) if house else None
            if head is not None and head.alive_at(year):
                people.append(head)
    return people[:5]


def _fight(ctx, calamity, spec, plan, rng, year: int, decisive: bool) -> None:
    world = ctx.world
    region = world.regions.get(rng.choice(calamity.region_ids))
    defenders = _defenders(ctx, calamity, rng, year)
    attacker = world.figures.get(calamity.leader_id)
    if calamity.general_ids and not decisive and rng.chance(0.6):
        attacker = world.figures.get(rng.choice(calamity.general_ids)) or attacker

    defender_wins = decisive and plan["resolution"] in (
        "coalition", "heroes", "hero", "driven_back", "sealed", "suppressed")
    if not decisive:
        defender_wins = rng.chance(0.3)

    deaths = int(max(400, calamity.deaths * rng.uniform(0.02, 0.08)
                     + 900 * calamity.severity))
    date = ctx.date_in(rng, year)
    battle = world.add_battle(
        name=_battle_name(rng, world, calamity, region), date=date,
        calamity_id=calamity.id, region_id=region.id if region else "",
        attacker_id=attacker.id if attacker is not None else "",
        defender_ids=[figure.id for figure in defenders],
        polity_ids=list(calamity.polity_ids),
        winner="защитники" if defender_wins else "враг",
        deaths=deaths, decisive=decisive,
    )

    # Полководцы гибнут — и это меняет судьбу их стран.
    for figure in defenders:
        if rng.chance(0.35 if not defender_wins else 0.18):
            world.schedule_death(figure, date, "пал в битве «%s»" % battle.name)
            battle.fallen_ids.append(figure.id)
    if defender_wins and calamity.general_ids and rng.chance(0.6):
        general = world.figures.get(rng.choice(calamity.general_ids))
        if general is not None and general.alive_at(year):
            world.schedule_death(general, date, "убит в битве «%s»" % battle.name)
            battle.fallen_ids.append(general.id)

    _record_deaths(calamity, deaths, "", "")
    title, text = texts.battle_text(rng, world, battle, calamity, attacker, defenders)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="battle",
        title=title, text=text,
        importance=4 if decisive else 3,
        actors=([attacker.id] if attacker else []) + battle.defender_ids[:3],
        subjects=[calamity.id, battle.id],
        region_id=battle.region_id, race_id=calamity.race_id)


# ---------------------------------------------------------------------------
# Разрешение
# ---------------------------------------------------------------------------

def _resolve(ctx, calamity, spec, plan, rng, year: int) -> None:
    world = ctx.world
    resolution = plan["resolution"]
    date = ctx.date_in(rng, year)

    heroes = []
    commanders = []
    needs_heroes = cat.RESOLUTIONS.get(resolution, ("", False))[1]
    if needs_heroes:
        heroes, commanders = _raise_heroes(ctx, calamity, spec, rng, year, resolution)

    leader = world.figures.get(calamity.leader_id)
    if leader is not None and leader.alive_at(year) and resolution in (
            "hero", "heroes", "coalition", "dispersed", "suppressed"):
        world.schedule_death(leader, date, "сражён при разгроме вторжения")
    elif leader is not None and resolution == "sealed":
        leader.notes.append("запечатан(а), но не убит(а)")

    _political_outcome(ctx, calamity, spec, plan, rng, year, date)

    world.end_calamity(calamity, date, cat.RESOLUTIONS.get(
        resolution, ("кончилось", False))[0])
    calamity.hero_ids = [figure.id for figure in heroes]
    calamity.commander_ids = [figure.id for figure in commanders]

    title, text = texts.ends(rng, world, calamity, spec, resolution, heroes, commanders)
    importance = min(5, 3 + calamity.severity // 2)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="calamity_ends",
        title=title, text=text, importance=importance,
        actors=[figure.id for figure in heroes[:4] + commanders[:2]],
        subjects=[calamity.id], region_id=calamity.region_ids[0],
        race_id=calamity.race_id)

    _leave_relics(ctx, calamity, spec, rng, year, date)
    _start_dark_age(ctx, calamity, spec, rng, year, date)
    ctx.calamity_plans.pop(calamity.id, None)


def _raise_heroes(ctx, calamity, spec, rng, year: int, resolution: str) -> tuple:
    world = ctx.world
    heroes = []
    commanders = []

    if resolution == "coalition":
        commanders = _defenders(ctx, calamity, rng, year)
        for figure in commanders:
            if "полководец коалиции" not in figure.roles:
                figure.roles.append("полководец коалиции")

    count = {"hero": 1, "heroes": rng.randint(3, 5), "coalition": rng.randint(1, 2),
             "sealed": rng.randint(2, 4), "dispersed": rng.randint(2, 4),
             "driven_back": rng.randint(1, 3), "suppressed": rng.randint(1, 2),
             "reunited": 1}.get(resolution, 1)

    races = _hero_races(ctx, calamity)
    epithets = HERO_EPITHETS.get(calamity.race_id or "", HERO_EPITHETS[""])
    for index in range(count):
        race = rng.choice(races)
        sex = "f" if rng.chance(0.4) else "m"
        hero = ctx.make_figure(
            rng, race, year, role="герой", region_id=rng.choice(calamity.region_ids),
            title="герой" if sex == "m" else "героиня", sex=sex, epithet_chance=0.0)
        pair = rng.choice(epithets)
        hero.epithet = pair[1] if sex == "f" else pair[0]
        hero.roles.append("победитель бедствия")
        heroes.append(hero)

        # Часть героев не переживает победу.
        if resolution in ("sealed", "dispersed") and rng.chance(0.55):
            world.schedule_death(hero, ctx.date_in(rng, year),
                                 "погиб(ла), запечатывая беду")
        elif rng.chance(0.2):
            world.schedule_death(hero, ctx.date_in(rng, year),
                                 "пал(а) в последней битве")

    # Уцелевший герой может положить начало знатному роду.
    for hero in heroes:
        if hero.alive_at(year + 1) and rng.chance(0.4):
            seat = _hero_seat(ctx, calamity, rng)
            houses_mod.found_house(ctx, hero, year, ctx.date_in(rng, year),
                                   seat=seat, rank=MINOR, importance=2)
    return heroes, commanders


def _hero_races(ctx, calamity) -> list:
    world = ctx.world
    races = []
    for polity_id in calamity.polity_ids:
        polity = world.polities.get(polity_id)
        if polity is not None:
            races.append(races_mod.get_race(polity.race_id))
    if not races:
        for settlement_id in world.active_settlements:
            settlement = world.settlements[settlement_id]
            if settlement.region_id in calamity.region_ids:
                races.append(races_mod.get_race(settlement.race_id))
    if not races:
        races = [races_mod.get_race("human")]
    return sorted(set(races), key=lambda race: race.id)


def _hero_seat(ctx, calamity, rng):
    world = ctx.world
    options = [world.settlements[sid] for sid in world.active_settlements
               if world.settlements[sid].region_id in calamity.region_ids]
    if not options:
        return None
    return rng.choice(sorted(options, key=lambda s: s.id))


# ---------------------------------------------------------------------------
# Политические последствия
# ---------------------------------------------------------------------------

def _political_outcome(ctx, calamity, spec, plan, rng, year: int, date) -> None:
    if spec.kind != cat.POLITICAL:
        return
    world = ctx.world
    victims = [world.polities[pid] for pid in calamity.polity_ids
               if pid in world.polities and world.polities[pid].status == ACTIVE]
    if not victims:
        return
    victim = victims[0]
    resolution = plan["resolution"]

    if spec.key == "empire_collapse" and resolution == "shattered":
        _split_polity(ctx, calamity, victim, rng, year, date)
    elif spec.key == "feudal_fracture" and resolution == "shattered":
        _free_cities(ctx, calamity, victim, rng, year, date)
    elif spec.key == "tribal_conquest" and resolution in ("absorbed", "shattered"):
        _tribal_takeover(ctx, calamity, victim, rng, year, date)


def _split_polity(ctx, calamity, polity, rng, year: int, date) -> None:
    """Держава распадается на несколько стран — по числу сильных родов."""
    world = ctx.world
    settlements = [world.settlements[sid] for sid in polity.settlement_ids
                   if sid in world.settlements
                   and world.settlements[sid].status == ACTIVE]
    if len(settlements) < 3:
        return
    race = races_mod.get_race(polity.race_id)
    pieces = min(len(settlements) - 1, rng.randint(2, 4))
    settlements = rng.shuffled(sorted(settlements, key=lambda s: s.id))
    chunk = max(1, len(settlements) // (pieces + 1))

    for index in range(pieces):
        part = settlements[index * chunk:(index + 1) * chunk]
        if not part:
            continue
        capital = part[0]
        founder = world.figures.get(capital.founder_id)
        house = world.houses.get(founder.house_id) if founder is not None else None
        head = world.figures.get(house.head_id) if house is not None else None
        if head is None or not head.alive_at(year):
            sex = "f" if rng.chance(0.4) else "m"
            head = ctx.make_figure(
                rng, race, year, role="правитель", region_id=capital.region_id,
                title=ctx.title_for(race, "ruler", sex), sex=sex,
                home_id=capital.id, epithet_chance=0.7)

        new_polity = world.add_polity(
            name=ctx.forge.polity(rng, race),
            form=rng.choice(race.polity_words or ("Королевство",)),
            race_id=race.id, founded=date, founder_id=head.id,
            capital_id=capital.id, ruler_id="", region_ids=[], settlement_ids=[],
            predecessor_id=polity.id)
        for settlement in part:
            if settlement.polity_id and settlement.id in polity.settlement_ids:
                polity.settlement_ids.remove(settlement.id)
            settlement.polity_id = new_polity.id
            settlement.is_capital = settlement.id == capital.id
            new_polity.settlement_ids.append(settlement.id)
            if settlement.region_id not in new_polity.region_ids:
                new_polity.region_ids.append(settlement.region_id)
        succession.install_founder(ctx, new_polity, head, capital, date, year)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="polity_split",
            title="Осколок державы: %s" % new_polity.name,
            text="Из распавшейся страны %s выделяется %s. Во главе — %s."
                 % (polity.full_name, new_polity.full_name, head.name),
            importance=4, actors=[head.id],
            subjects=[new_polity.id, polity.id, calamity.id],
            region_id=capital.region_id, race_id=race.id)

    if not [sid for sid in polity.settlement_ids
            if world.settlements[sid].status == ACTIVE]:
        world.end_polity(polity, date, "распалась на части")
        calamity.polities_lost += 1


def _free_cities(ctx, calamity, polity, rng, year: int, date) -> None:
    world = ctx.world
    _ = calamity
    settlements = [world.settlements[sid] for sid in list(polity.settlement_ids)
                   if sid in world.settlements
                   and world.settlements[sid].status == ACTIVE
                   and not world.settlements[sid].is_capital]
    if not settlements:
        return
    freed = rng.sample(sorted(settlements, key=lambda s: s.id),
                       max(1, len(settlements) // 2))
    for settlement in freed:
        if settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)
        settlement.polity_id = ""
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="polity_fracture",
        title="Раздробленность: %s" % polity.name,
        text="Города выходят из-под руки столицы. %s теряет %d %s — "
             "теперь они сами по себе."
             % (polity.full_name, len(freed),
                "город" if len(freed) == 1 else "городов"),
        importance=3, subjects=[polity.id, calamity.id], race_id=polity.race_id)


def _tribal_takeover(ctx, calamity, polity, rng, year: int, date) -> None:
    """Племена берут города и садятся на них сами."""
    world = ctx.world
    candidates = []
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.region_id in calamity.region_ids and tribe.population > 200:
            candidates.append(tribe)
    if not candidates:
        return
    tribe = rng.weighted([(t, float(t.population)) for t in candidates])
    race = races_mod.get_race(tribe.race_id)
    settlements = [world.settlements[sid] for sid in list(polity.settlement_ids)
                   if sid in world.settlements
                   and world.settlements[sid].status == ACTIVE]
    if not settlements:
        return

    taken = rng.sample(sorted(settlements, key=lambda s: s.id),
                       max(1, len(settlements) // 2))
    chief = world.figures.get(tribe.chief_id)
    if chief is None or not chief.alive_at(year):
        sex = "f" if rng.chance(0.4) else "m"
        chief = ctx.make_figure(rng, race, year, role="вождь",
                                region_id=tribe.region_id,
                                title=ctx.title_for(race, "chief", sex), sex=sex)

    if race.builds_states and len(taken) >= 1:
        capital = taken[0]
        new_polity = world.add_polity(
            name=ctx.forge.polity(rng, race),
            form=rng.choice(race.polity_words or ("Вождество",)),
            race_id=race.id, founded=date, founder_id=chief.id,
            capital_id=capital.id, ruler_id="", region_ids=[], settlement_ids=[],
            predecessor_id=polity.id)
        for settlement in taken:
            if settlement.id in polity.settlement_ids:
                polity.settlement_ids.remove(settlement.id)
            settlement.polity_id = new_polity.id
            settlement.race_id = settlement.race_id     # жители остаются прежними
            settlement.is_capital = settlement.id == capital.id
            new_polity.settlement_ids.append(settlement.id)
            if settlement.region_id not in new_polity.region_ids:
                new_polity.region_ids.append(settlement.region_id)
        world.end_tribe(tribe, date, "село на завоёванные города", "осело")
        succession.install_founder(ctx, new_polity, chief, capital, date, year)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="conquest",
            title="Завоевание: %s" % new_polity.name,
            text="Племя «%s» берёт города страны %s и садится на них само. "
                 "Так появляется %s во главе с %s."
                 % (tribe.name, polity.full_name, new_polity.full_name, chief.name),
            importance=4, actors=[chief.id],
            subjects=[new_polity.id, polity.id, calamity.id],
            region_id=capital.region_id, race_id=race.id)

    if not [sid for sid in polity.settlement_ids
            if world.settlements[sid].status == ACTIVE]:
        world.end_polity(polity, date, "завоёвана племенами")
        calamity.polities_lost += 1


# ---------------------------------------------------------------------------
# Следы и тёмные века
# ---------------------------------------------------------------------------

def _leave_relics(ctx, calamity, spec, rng, year: int, date) -> None:
    world = ctx.world
    if not spec.relics:
        return
    count = {1: 0, 2: 1, 3: 1, 4: 2, 5: 3}.get(calamity.severity, 1)
    if calamity.severity <= 2 and rng.chance(0.45):
        count = max(0, count - 1)

    used = set()
    for _ in range(count):
        kind = rng.weighted(spec.relics)
        if kind in used:
            continue
        used.add(kind)
        noun, gender, needs_figure = RELIC_FORMS.get(kind, (kind.capitalize(), "m", False))

        figure = None
        if needs_figure:
            survivors = [world.figures[fid] for fid in calamity.general_ids
                         if fid in world.figures]
            survivors = [f for f in survivors if f.alive_at(year)]
            if survivors:
                figure = rng.choice(survivors)
            elif calamity.race_id:
                race = races_mod.RACES_BY_ID.get(calamity.race_id)
                if race is not None:
                    figure = ctx.make_figure(
                        rng, race, year, role="уцелевший враг",
                        region_id=rng.choice(calamity.region_ids),
                        title="уцелевший", epithet_chance=0.8)
            if figure is not None:
                name = "%s %s" % (noun, figure.name)
            else:
                name = noun
        elif calamity.notes and calamity.kind == cat.INVASION:
            host = calamity.notes[0]
            parts = host.split(" ", 1)
            if len(parts) == 2:
                adj_forms = rng.choice((parts[0],))
                name = "%s %s" % (noun, genitive_phrase(
                    adj_forms, parts[1], _guess_gender(parts[1])))
            else:
                name = noun
        else:
            name = noun

        relic = world.add_relic(
            name=name, kind=kind, calamity_id=calamity.id,
            region_id=rng.choice(calamity.region_ids), created=date,
            potency=max(1, min(5, calamity.severity - rng.randint(0, 1))),
            figure_id=figure.id if figure is not None else "",
            race_id=calamity.race_id)
        calamity.relic_ids.append(relic.id)

        if calamity.severity >= 3 or rng.chance(0.4):
            title, text = texts.relic_left(rng, relic, calamity, world)
            world.add_event(
                date=date, era_index=world.era_index_at(year), kind="relic_left",
                title=title, text=text, importance=2,
                subjects=[relic.id, calamity.id], region_id=relic.region_id)


def _guess_gender(noun: str) -> str:
    if noun.endswith(("а", "я")):
        return "f"
    if noun.endswith(("о", "е")):
        return "n"
    if noun.endswith(("ы", "и")):
        return "p"
    return "m"


def _start_dark_age(ctx, calamity, spec, rng, year: int, date) -> None:
    world = ctx.world
    if calamity.severity < 3:
        return
    # Тёмные века — редкость, иначе мир никогда не вылезает из темноты.
    if calamity.severity == 3 and not rng.chance(0.3):
        return
    if calamity.deaths < 20000 and calamity.severity < 4:
        return

    plan = ctx.calamity_plans.get(calamity.id, {})
    base = {3: (40, 160), 4: (120, 450), 5: (300, 1200)}[min(5, calamity.severity)]
    length = int(rng.uniform(*base) * (0.6 + 0.4 * min(2.0, plan.get("duration", 10) / 60.0)))
    length = max(20, length)
    intensity = min(0.9, 0.18 * calamity.severity + rng.uniform(-0.06, 0.12))
    worldwide = calamity.severity >= 5 or (
        calamity.severity == 4 and len(calamity.region_ids) >= len(world.regions) * 0.6)

    world.add_dark_age(calamity.id, year, year + length, calamity.region_ids,
                       intensity, worldwide)
    calamity.dark_age_until = year + length

    title, text = texts.dark_age(rng, calamity, length, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="dark_age",
        title=title, text=text, importance=5 if worldwide else 4,
        subjects=[calamity.id], region_id=calamity.region_ids[0])


def _close_dark_ages(ctx, year: int) -> None:
    world = ctx.world
    for record in world.dark_ages:
        if record.get("closed"):
            continue
        if year < record["end"]:
            continue
        record["closed"] = True
        calamity = world.calamities.get(record["calamity_id"])
        if calamity is None or record["intensity"] < 0.5:
            continue
        rng = ctx.rng("dark_end", record["calamity_id"])
        title, text = texts.dark_age_end(rng, calamity)
        world.add_event(
            date=Date(record["end"], 12, 29), era_index=world.era_index_at(year),
            kind="dark_age_end", title=title, text=text, importance=3,
            subjects=[calamity.id])


# ---------------------------------------------------------------------------
# Пробуждение следов
# ---------------------------------------------------------------------------

def _maybe_wake_relic(ctx, year: int) -> None:
    world = ctx.world
    if not world.sleeping_relics:
        return
    rng = ctx.rng("relic", year)
    chance = min(0.35, RELIC_WAKE_RATE * len(world.sleeping_relics) * ctx.density())
    if not rng.chance(chance):
        return

    pairs = []
    for relic_id in world.sleeping_relics:
        relic = world.relics[relic_id]
        age = max(1, year - relic.created.year)
        # Чем старше след, тем легендарнее его пробуждение.
        pairs.append((relic, relic.potency * min(3.0, age / 500.0)))
    if not pairs:
        return
    relic = rng.weighted(pairs)
    origin = world.calamities.get(relic.calamity_id)
    date = ctx.date_in(rng, year)
    world.wake_relic(relic, date)

    title, text = texts.relic_awakens(rng, relic, origin, world, year)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="relic_awakens",
        title=title, text=text, importance=3,
        actors=[relic.figure_id] if relic.figure_id else [],
        subjects=[relic.id] + ([origin.id] if origin is not None else []),
        region_id=relic.region_id, race_id=relic.race_id)

    # Опасный след даёт начало новой, уже меньшей беде.
    if relic.kind in FAITH_RELICS:
        return            # забытую веру поднимает система религии
    if relic.kind in LIVING_RELICS and relic.potency >= 2 and rng.chance(0.45):
        spec = cat.get_spec(origin.key) if origin is not None else None
        if spec is not None:
            severity = max(1, min(3, relic.potency - 1))
            child = _start_calamity(ctx, year, spec, rng, severity=severity,
                                    parent=origin, relic=relic)
            if child is not None:
                child.notes.append("выросло из следа: %s" % relic.name)
                relic.status = "исчерпан"
    else:
        title, text = texts.relic_echo(rng, relic, origin, world)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="relic_echo",
            title=title, text=text, importance=2,
            subjects=[relic.id], region_id=relic.region_id)
        relic.status = "исчерпан"
