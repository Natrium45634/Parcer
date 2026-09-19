# -*- coding: utf-8 -*-
"""Войны держав: объявление, ход кампании, мир и вековые распри.

Война здесь — не бросок кости, а событие с длиной. У неё есть причина
(warfare.py), войско, посчитанное от числа душ, полководцы, годовой ход
и конец, который не всегда зависит от того, кто сильнее.

Годовой такт войны:

1. **Сбор.** Раз в год стороны считают, что у них осталось: людей,
   хлеба, воли. Истощение растёт, и с ним растёт желание сесть за стол.
2. **Кампания.** Год может пройти в манёврах и не дать ничего, а может
   кончиться сражением или осадой. Чем крупнее война, тем чаще бьются.
3. **Случай.** Вдвое сильнейшее войско проигрывает примерно каждое пятое
   сражение: туман, брод, предавший проводник и упрямый гарнизон весят
   не меньше лишней тысячи копий.
4. **Обрыв.** Смерть государя, мор, мировое бедствие или мятеж дома —
   и поход сворачивают, ничего не добившись. Это не редкость, а норма.
5. **Мир.** Победитель берёт то, за чем шёл, — города, дань, веру,
   покорность. Мир называют по месту, где его подписали. Если побеждённой
   державы больше нет, мира не заключают: не с кем.
"""

from __future__ import annotations

from . import houses as houses_mod
from . import nations as nations_mod
from . import soldiery
from . import spies
from .. import espionage
from .. import narrative_soldiery as fort_texts
from .. import narrative_spies as spy_texts
from .. import diplomacy as dip
from .. import narrative
from .. import narrative_diplomacy as dip_texts
from .. import narrative_war as texts
from .. import races as races_mod
from .. import rulers as rulers_mod
from .. import troops as troops_mod
from .. import warfare
from ..models import ACTIVE, MINOR, ONGOING, RUINED

WAR_RATE = 0.055            # годовая вероятность, что где-то вспыхнет война
MIN_WAR_CITIES = 2          # с чем не воюют: слишком мало городов
MIN_EDGE = 0.55             # на кого не нападают: слишком силён
PEACE_COOLDOWN = 10         # сколько лет после мира не трогают того же соседа
WEARINESS_DECAY = 0.12      # усталость от войн сходит за десятилетия
FEUD_WARS = 3               # со скольких войн подряд вражду называют по имени
FEUD_WINDOW = 600           # в каком окне лет войны считаются одной распрёй
KING_LEADS = 0.35           # как часто государь идёт с войском сам
ENNOBLE_CHANCE = 0.18       # шанс, что решившего битву простолюдина возвысят
CONTINGENT = 0.55           # какую долю войска союзник шлёт на чужую войну
DEFEND_CALL = 0.82          # как часто союзник отзывается на оборонительный зов
ATTACK_CALL = 0.38          # и как часто — на наступательный


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    _advance(ctx, year)
    _maybe_declare(ctx, year)


def upkeep(ctx, year: int, period: int) -> None:
    """Усталость от войн сходит сама собой."""
    world = ctx.world
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        if not world.wars_of(polity, only_active=True):
            polity.weariness = max(0.0, polity.weariness
                                   - WEARINESS_DECAY * (period / 10.0))
        if polity.tribute_until and year >= polity.tribute_until:
            polity.tribute_to = ""
            polity.tribute_until = 0
            polity.overlord_id = ""

    # Вражда, о которой не вспоминали четыре века, считается изжитой.
    rng = ctx.rng("war", "feuds", year)
    for feud in list(world.feuds.values()):
        if feud.status != ONGOING:
            continue
        last = 0
        for war_id in feud.war_ids:
            item = world.wars.get(war_id)
            if item is not None and item.end is not None:
                last = max(last, item.end.year)
            elif item is not None and item.status == ONGOING:
                last = year
        if last and year - last >= FEUD_WINDOW:
            _retire_feud(ctx, feud, year, rng)


# ---------------------------------------------------------------------------
# Объявление войны
# ---------------------------------------------------------------------------

def _live_cities(world, polity) -> list:
    return [world.settlements[sid] for sid in polity.settlement_ids
            if sid in world.settlements
            and world.settlements[sid].status == ACTIVE]


def _neighbours(world, polity) -> list:
    """Державы, до которых дотягивается войско: соседи по земле."""
    reach = set(polity.region_ids)
    for region_id in list(polity.region_ids):
        region = world.regions.get(region_id)
        if region is not None:
            reach.update(region.neighbors)

    out = []
    for other_id in world.active_polities:
        if other_id == polity.id:
            continue
        other = world.polities[other_id]
        if reach & set(other.region_ids):
            out.append(other)
    return out


def _can_fight(world, polity, year: int) -> bool:
    if polity.status != ACTIVE:
        return False
    if len(_live_cities(world, polity)) < MIN_WAR_CITIES:
        return False
    if world.wars_of(polity, only_active=True):
        return False            # на две войны разом сил не хватает
    if polity.weariness >= 0.8:
        return False
    return True


def _maybe_declare(ctx, year: int) -> None:
    world = ctx.world
    if len(world.active_polities) < 2:
        return
    rng = ctx.rng("war", "declare", year)
    pairs = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if not _can_fight(world, polity, year):
            continue
        # Кто чаще берётся за оружие: воинственный народ, злая политика,
        # государь-полководец, держава с обидами и без хлеба.
        race = races_mod.get_race(polity.race_id)
        weight = float(polity.population) ** 0.55
        weight *= warfare.martial(race)
        weight *= rulers_mod.war_edge(world, polity)
        weight *= max(0.3, 1.0 - polity.weariness)
        pairs.append((polity, weight))
    if len(pairs) < 2:
        return

    # Чем больше держав способны воевать, тем чаще где-нибудь да воюют:
    # при одном броске на весь мир войны в летописи почти не встречались.
    chance = ctx.rate(WAR_RATE) * (0.7 + ctx.era_spec(year).turmoil) \
        * (0.35 + 0.05 * len(pairs))
    if not rng.chance(min(0.65, chance)):
        return

    attacker = rng.weighted(pairs)
    defender = _pick_target(ctx, world, attacker, year, rng)
    if defender is None:
        return
    _declare(ctx, attacker, defender, year, rng)


def _reachable(ctx, world, attacker) -> list:
    """До кого вообще дотянется войско: соседи по суше и соседи по воде.

    Морская держава воюет не только с теми, с кем делит межу: флот
    делает соседом любого, у кого есть гавань на том же море.
    """
    out = {other.id: other for other in _neighbours(world, attacker)}
    race = races_mod.get_race(attacker.race_id)
    if not warfare.ports(world, attacker):
        return list(out.values())
    if warfare.fleet(world, attacker, race) < 2:
        return list(out.values())
    for other_id in world.active_polities:
        if other_id == attacker.id or other_id in out:
            continue
        other = world.polities[other_id]
        if warfare.can_reach_by_sea(world, attacker, other):
            out[other_id] = other
    return list(out.values())


def _pick_target(ctx, world, attacker, year: int, rng):
    """На кого пойдут: на того, до кого дотянутся и с кем есть счёты."""
    options = []
    for other in _reachable(ctx, world, attacker):
        if other.status != ACTIVE or not _live_cities(world, other):
            continue
        if world.war_between(attacker.id, other.id) is not None:
            continue
        if other.tribute_to == attacker.id or other.overlord_id == attacker.id:
            continue            # на своего данника не ходят
        pact = world.pact_between(attacker.id, other.id)
        if pact is not None:
            continue            # со связанными словом не воюют
        if attacker.league_id and attacker.league_id == other.league_id:
            continue            # и с товарищем по союзу тоже
        if attacker.union_id and attacker.union_id == other.union_id:
            continue            # держава не воюет сама с собой
        if (attacker.tribute_to == other.id or attacker.overlord_id == other.id) \
                and attacker.population < other.population * 0.8:
            continue            # иго сбрасывают, когда есть чем
        # Недавно замирились — пока не трогают.
        recent = 0
        for war in world.wars_of(attacker):
            if war.status == ONGOING or war.end is None:
                continue
            if other.id in (war.attacker_id, war.defender_id):
                recent = max(recent, war.end.year)
        if recent and year - recent < PEACE_COOLDOWN:
            continue
        edge = (attacker.population + 1.0) / (other.population + 1.0)
        edge *= (rulers_mod.war_edge(world, attacker)
                 / max(0.5, rulers_mod.war_edge(world, other)))
        if edge < MIN_EDGE:
            continue            # на того, кто вчетверо сильнее, не ходят
        # Слабого соседа предпочитают, но не настолько, чтобы весь мир
        # веками бил одного и того же.
        weight = min(3.0, edge) + 0.4 * len(warfare.reasons(ctx, attacker,
                                                            other, year))
        # Старая вражда тянет сильнее свежего расчёта: к тому, с кем уже
        # воевали деды, возвращаются охотнее, чем ищут нового врага.
        weight *= 1.0 + 0.9 * _feud_weight(world, attacker, other, year)
        options.append((other, weight))
    if not options:
        return None
    return rng.weighted(options)


def _feud_weight(world, first, second, year: int) -> float:
    count = 0
    for war in world.wars_of(first):
        if war.end is None or second.id not in (war.attacker_id, war.defender_id):
            continue
        if year - war.end.year <= FEUD_WINDOW:
            count += 1
    return min(4.0, count)


def _war_title(rng, ctx, attacker, defender, cause, year: int) -> str:
    """Название войны из шаблона повода — всё в именительном падеже."""
    world = ctx.world
    cities = _live_cities(world, defender)
    city = rng.choice(sorted(cities, key=lambda s: -s.population)[:3]) \
        if cities else None
    region = None
    for region_id in defender.region_ids:
        candidate = world.regions.get(region_id)
        if candidate is not None:
            region = candidate
            break
    folk = None
    for folk_id in sorted(world.folks):
        item = world.folks[folk_id]
        if item.race_id == attacker.race_id:
            folk = item
            break

    data = {
        "city": city.name if city is not None else defender.name,
        "region": region.name if region is not None else defender.name,
        "folk": folk.name if folk is not None else defender.name,
        "foe": defender.name,
    }
    options = [item for item in cause.titles]
    taken = {war.name for war in world.wars.values()}
    for _ in range(6):
        title = rng.choice(options) % data
        if title not in taken:
            return title
    # Одноимённые войны нумеруют, как в нашей истории: сперва «Война за
    # межу», потом «Вторая война за межу», и так до тринадцатой.
    base = rng.choice(options) % data
    for index in range(2, 14):
        title = texts.numbered(base, index)
        if title not in taken:
            return title
    return "%s (%d год)" % (base, year)


def _declare(ctx, attacker, defender, year: int, rng) -> None:
    world = ctx.world
    causes = warfare.reasons(ctx, attacker, defender, year)
    cause = rng.weighted(causes)

    attacker_race = races_mod.get_race(attacker.race_id)
    defender_race = races_mod.get_race(defender.race_id)
    era_index = world.era_index_at(year)
    attacker_men = warfare.levy(world, attacker, attacker_race, era_index)
    defender_men = warfare.levy(world, defender, defender_race, era_index)

    attacker_ships = warfare.fleet(world, attacker, attacker_race, era_index)
    defender_ships = warfare.fleet(world, defender, defender_race, era_index)
    by_land = bool({other.id for other in _neighbours(world, attacker)}
                   & {defender.id})
    at_sea = (not by_land) or (attacker_ships >= 2 and defender_ships >= 1
                               and rng.chance(0.5))

    scale = warfare.war_scale(attacker_men, defender_men)
    parity = min(attacker_men, defender_men) / float(max(1, max(attacker_men,
                                                                defender_men)))
    date = ctx.date_in(rng, year)
    war = world.add_war(
        name=_war_title(rng, ctx, attacker, defender, cause, year), start=date,
        attacker_id=attacker.id, defender_id=defender.id, cause=cause.key,
        aim=cause.aim, scale=scale,
        planned_years=warfare.expected_length(rng, scale, cause.zeal, parity),
        attacker_men=attacker_men, defender_men=defender_men,
        at_sea=at_sea, attacker_ships=attacker_ships,
        defender_ships=defender_ships,
    )
    _join_feud(ctx, war, attacker, defender, year, rng)

    leader = _commander(ctx, war, attacker, year, rng, side="attacker",
                        allow_ruler=True)
    _commander(ctx, war, defender, year, rng, side="defender", allow_ruler=True)

    joined_defence = _call_allies(ctx, war, defender, "defender", year, rng)
    joined_attack = _call_allies(ctx, war, attacker, "attacker", year, rng)

    ruler = world.figures.get(attacker.ruler_id)
    leads = leader is not None and ruler is not None and leader.id == ruler.id
    title, text = texts.declare(rng, war, attacker, defender, cause,
                                attacker_men, defender_men,
                                leader=leader if leads else None)
    for side in (joined_attack, joined_defence):
        line = dip_texts.allies_joined(rng, war, "", side)
        if line:
            text = "%s %s" % (text, line)
    region_id = attacker.region_ids[0] if attacker.region_ids else ""
    world.add_event(
        date=date, era_index=era_index, kind="war_start", title=title,
        text=text, importance=3 + min(2, scale // 2),
        actors=[leader.id] if leader is not None else [],
        subjects=[war.id, attacker.id, defender.id], region_id=region_id,
        race_id=attacker.race_id)


# ---------------------------------------------------------------------------
# Союзники
# ---------------------------------------------------------------------------

def _call_allies(ctx, war, polity, side: str, year: int, rng) -> list:
    """Зовёт на войну тех, кто клялся прийти.

    Оборонительный зов исполняют почти всегда: на том союзы и держатся.
    Наступательный — как придётся: чужая война редко бывает своей. Тот,
    кто не пришёл, ломает клятву, и это помнят дольше самой войны.
    """
    world = ctx.world
    pool = war.defender_allies if side == "defender" else war.attacker_allies
    foe_id = war.attacker_id if side == "defender" else war.defender_id
    joined = []

    for pact in world.pacts_of(polity):
        if pact.kind != dip.ALLIANCE:
            continue
        ally = world.polities.get(pact.other(polity.id))
        if ally is None or ally.status != ACTIVE or ally.id == foe_id:
            continue
        if world.pact_between(ally.id, foe_id) is not None:
            continue            # связан словом и с другой стороной — не идёт
        if world.wars_of(ally, only_active=True):
            continue            # своя война ближе чужой
        if len(_live_cities(world, ally)) < 1:
            continue

        chance = DEFEND_CALL if side == "defender" else ATTACK_CALL
        league = world.leagues.get(ally.league_id)
        if league is not None and league.id == world.polities[polity.id].league_id:
            chance += 0.12 if league.kind != dip.OFFENSIVE else 0.22
        chance += 0.25 * dip.relation(ally, polity.id)
        ruler = world.figures.get(ally.ruler_id)
        if ruler is not None:
            chance += 0.03 * int(getattr(ruler, "alignment", 0) or 0)

        if not rng.chance(max(0.05, min(0.95, chance))):
            _betray(ctx, war, pact, ally, polity, year, rng)
            continue

        race = races_mod.get_race(ally.race_id)
        men = int(warfare.levy(world, ally, race, world.era_index_at(year))
                  * CONTINGENT)
        if men < warfare.LEVY_MIN:
            continue
        pool.append(ally.id)
        pact.wars_together += 1
        if war.id not in ally.war_ids:
            ally.war_ids.append(war.id)
        if league is not None and league.id not in war.league_ids:
            war.league_ids.append(league.id)
            if war.id not in league.war_ids:
                league.war_ids.append(war.id)
        joined.append((ally, men))
    return joined


def _betray(ctx, war, pact, ally, polity, year: int, rng) -> None:
    """Не пришедший на зов теряет больше, чем сберёг."""
    world = ctx.world
    pact.betrayals += 1
    dip.set_relation(ally, polity, dip.relation(ally, polity.id) - 0.35)
    if pact.betrayals < 2 and not rng.chance(0.45):
        return
    date = ctx.date_in(rng, year,
                       pact.signed if pact.signed.year == year else None)
    world.end_pact(pact, date, "клятву не исполнили")
    title, text = dip_texts.betrayal(rng, pact, ally, polity, war.name)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="betrayal",
        title=title, text=text, importance=3,
        subjects=[war.id, ally.id, polity.id], race_id=ally.race_id)


def _allied_force(ctx, war, side: str, year: int) -> tuple:
    """Что добавляют к войску союзники этой стороны."""
    world = ctx.world
    pool = war.attacker_allies if side == "attacker" else war.defender_allies
    men, power = 0, 0.0
    for ally_id in list(pool):
        ally = world.polities.get(ally_id)
        if ally is None or ally.status != ACTIVE:
            continue
        race = races_mod.get_race(ally.race_id)
        share = int(warfare.levy(world, ally, race,
                                 world.era_index_at(year)) * CONTINGENT)
        if share < warfare.LEVY_MIN:
            continue
        men += share
        power += warfare.host_power(share, warfare.quality(world, ally, race))
    return men, power


# ---------------------------------------------------------------------------
# Полководцы
# ---------------------------------------------------------------------------

def _commander(ctx, war, polity, year: int, rng, side: str,
               allow_ruler: bool = False):
    """Кто ведёт войско: государь, знатный воевода или новое имя.

    Государь идёт сам, если умеет воевать и если ему это по нраву. Это
    опасно: государи гибнут в битвах чаще, чем в постелях.
    """
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    pool = war.attacker_generals if side == "attacker" else war.defender_generals

    ruler = world.figures.get(polity.ruler_id)
    if allow_ruler and ruler is not None and ruler.alive_at(year) \
            and ruler.age_at(year) >= race.adulthood:
        skill = warfare._general_skill(ruler)
        chance = KING_LEADS * (0.4 + 0.12 * skill)
        if ruler.age_at(year) > race.lifespan[0] * 0.8:
            chance *= 0.3
        if rng.chance(min(0.85, chance)):
            if "полководец" not in ruler.roles:
                ruler.roles.append("полководец")
            if ruler.id not in pool:
                pool.append(ruler.id)
            return ruler

    general = nations_mod.pick_general(ctx, rng, polity, race, year)
    if general is not None and general.id not in pool:
        pool.append(general.id)
    return general


def _live_commander(world, war, side: str, year: int):
    pool = war.attacker_generals if side == "attacker" else war.defender_generals
    for figure_id in reversed(pool):
        figure = world.figures.get(figure_id)
        if figure is None:
            continue
        if figure.alive_at(year) and figure.id not in war.captured_ids:
            return figure
    return None


# ---------------------------------------------------------------------------
# Ход кампании
# ---------------------------------------------------------------------------

def _advance(ctx, year: int) -> None:
    world = ctx.world
    for war_id in list(world.active_wars):
        war = world.wars.get(war_id)
        if war is None or war.status != ONGOING:
            continue
        if war.start.year >= year:
            continue            # в год объявления ещё только собираются
        _campaign_year(ctx, war, year)


def _sides(world, war):
    return (world.polities.get(war.attacker_id),
            world.polities.get(war.defender_id))


def _forces(ctx, war, polity, side: str, year: int) -> tuple:
    """Сколько людей под знамёнами сейчас и какова их сила."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    losses = war.attacker_losses if side == "attacker" else war.defender_losses
    raised = war.attacker_men if side == "attacker" else war.defender_men
    # Убыль пополняют, но не полностью: людей в державе не прибавляется.
    fresh = warfare.levy(world, polity, race, world.era_index_at(year))
    men = max(warfare.LEVY_MIN, min(fresh, raised - losses
                                    + int(fresh * 0.06)))
    general = _live_commander(world, war, side, year)
    value = warfare.quality(world, polity, race, general)
    power = warfare.host_power(men, value)
    extra_men, extra_power = _allied_force(ctx, war, side, year)
    hired_men, hired_power = soldiery.hired_force(world, polity)
    return (men + extra_men + hired_men, power + extra_power + hired_power,
            general)


def _campaign_year(ctx, war, year: int) -> None:
    world = ctx.world
    attacker, defender = _sides(world, war)
    if attacker is None or defender is None:
        _finish(ctx, war, year, warfare.ANNIHILATION)
        return
    if attacker.status != ACTIVE or defender.status != ACTIVE:
        _finish(ctx, war, year, warfare.ANNIHILATION)
        return

    rng = ctx.rng("war", war.id, year)

    # --- что могло оборвать войну помимо оружия ---
    # Первый год кампании не прерывают: война, в которой не было ни
    # одного сражения, войной не запомнится.
    broken = "" if year - war.start.year < 2 else \
        _interruption(ctx, war, attacker, defender, year, rng)
    if broken:
        _finish(ctx, war, year, warfare.INTERRUPTED, note=broken)
        return

    # Упрямые причины держат войско в поле дольше: за веру и за кровь
    # воюют до последнего, за пошлины — пока не надоест.
    zeal = warfare.CAUSES_BY_KEY[war.cause].zeal \
        if war.cause in warfare.CAUSES_BY_KEY else 1.0
    war.exhaustion = min(1.0, war.exhaustion
                         + rng.uniform(0.022, 0.065) / max(0.6, zeal))
    attacker.weariness = min(1.0, attacker.weariness + 0.035)
    defender.weariness = min(1.0, defender.weariness + 0.045)

    # --- чем занят год ---
    # Чем крупнее война, тем чаще сходятся: у больших держав и войск
    # больше, и поводов встретиться тоже.
    fight_chance = 0.34 + 0.10 * war.scale
    if war.sieges:
        _tick_sieges(ctx, war, attacker, defender, year, rng)
    # Войну без единого сражения потомки не назвали бы войной: первый год
    # кампании сходятся непременно.
    _maybe_hire(ctx, war, attacker, defender, year, rng)

    fought = False
    if war.at_sea:
        fought = _sea_year(ctx, war, attacker, defender, year, rng)
    if not war.battle_ids or (not fought
                              and rng.chance(min(0.88, fight_chance))):
        _battle(ctx, war, attacker, defender, year, rng)
        fought = True
    opened = False
    if len(war.sieges) < 1 + war.scale // 2 and rng.chance(0.34):
        _open_siege(ctx, war, attacker, defender, year, rng)
        opened = True
    # Год без единого дела — тоже год войны, и он тоже стоит денег.
    if not fought and not opened and not war.sieges and rng.chance(0.45):
        title, text = texts.manoeuvre_text(rng, war, year)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="war_lull", title=title, text=text, importance=1,
            subjects=[war.id, attacker.id, defender.id],
            race_id=attacker.race_id)

    # --- пора ли мириться ---
    over = year - war.start.year >= war.planned_years
    decisive = abs(war.momentum) >= 0.92
    spent = war.exhaustion >= 0.9
    if not (over or decisive or spent):
        return
    if decisive and war.momentum > 0:
        _finish(ctx, war, year, warfare.ATTACKER_WON)
    elif decisive:
        _finish(ctx, war, year, warfare.DEFENDER_WON)
    elif spent:
        _finish(ctx, war, year, warfare.EXHAUSTION)
    elif war.momentum >= 0.22:
        _finish(ctx, war, year, warfare.ATTACKER_WON)
    elif war.momentum <= -0.22:
        _finish(ctx, war, year, warfare.DEFENDER_WON)
    else:
        _finish(ctx, war, year, warfare.WHITE)


def _interruption(ctx, war, attacker, defender, year: int, rng) -> str:
    """Не всякая война кончается оружием. Иногда просто становится не до неё.

    Проверка идёт не каждый год: иначе у долгой войны набирается столько
    поводов сорваться, что до победы не доживает почти ни одна.
    """
    world = ctx.world
    if not rng.chance(0.35):
        return ""

    # Война обрывается, только если государь умер уже в походе: держава,
    # начавшая войну при живом короле, не бросает её оттого, что престол
    # пустовал ещё до объявления.
    ruler = world.figures.get(attacker.ruler_id)
    died = (ruler is not None and ruler.death is not None
            and war.start.year <= ruler.death.year <= year)
    if (ruler is None or died) and rng.chance(0.45):
        return ("Государь, начавший войну, мёртв, и наследнику она не "
                "нужна: войско отзывают.")
    if attacker.hunger > 0.5 or defender.hunger > 0.5:
        if rng.chance(0.30):
            return ("Голод в тылу оказывается страшнее неприятеля: обозы "
                    "пусты, и поход сворачивают.")
    for polity in (attacker, defender):
        for calamity_id in world.active_calamities:
            calamity = world.calamities[calamity_id]
            if polity.id in calamity.polity_ids and calamity.severity >= 4:
                if rng.chance(0.35):
                    return ("Война обрывается на середине: пришло бедствие "
                            "«%s», и стало не до межи." % calamity.name)
    if ctx.world_darkness > 0.45 and rng.chance(0.30):
        return ("Мир накрывают тёмные века: воевать больше незачем и не с кем — "
                "хватает и общей беды.")
    if attacker.weariness >= 0.95 and rng.chance(0.3):
        return "Войско расходится по домам само, не дожидаясь приказа."
    return ""


# ---------------------------------------------------------------------------
# Сражение
# ---------------------------------------------------------------------------

def _battle_place(ctx, war, attacker, defender, rng) -> tuple:
    """Где сошлись: у чьего-то города или в поле на спорной земле."""
    world = ctx.world
    # Воюют на земле обороняющегося, пока нападающий берёт верх.
    host = defender if war.momentum >= -0.2 else attacker
    cities = _live_cities(world, host)
    settlement = rng.choice(sorted(cities, key=lambda s: s.id)) \
        if cities and rng.chance(0.55) else None
    region = None
    if settlement is not None:
        region = world.regions.get(settlement.region_id)
    elif host.region_ids:
        region = world.regions.get(rng.choice(sorted(host.region_ids)))
    return region, settlement, host


def _battle(ctx, war, attacker, defender, year: int, rng) -> None:
    world = ctx.world
    a_men, a_power, a_general = _forces(ctx, war, attacker, "attacker", year)
    d_men, d_power, d_general = _forces(ctx, war, defender, "defender", year)
    region, settlement, host = _battle_place(ctx, war, attacker, defender, rng)

    # Земля решает не меньше числа: конница в степи стоит полутора себя,
    # в болоте — двух третей, а дворфийский строй в теснине непобедим.
    terrain = region.terrain if region is not None else ""
    a_race = races_mod.get_race(attacker.race_id)
    d_race = races_mod.get_race(defender.race_id)
    a_power *= troops_mod.worth(a_race, terrain)
    d_power *= troops_mod.worth(d_race, terrain)
    if region is not None:
        # Крепость в этой земле — это не только стены, но и склады,
        # дозоры и место, куда можно отойти.
        a_power *= soldiery.guard_of(world, attacker, region.id)
        d_power *= soldiery.guard_of(world, defender, region.id)

    # Серебро, заплаченное до битвы, отрабатывается в битве: купленный
    # воевода медлит, а выведанные замыслы стоят полка.
    a_sold = spies.leverage(ctx, war, attacker)
    d_sold = spies.leverage(ctx, war, defender)
    a_power *= 1.0 - a_sold
    d_power *= 1.0 - d_sold
    if a_sold or d_sold:
        spies.spend(ctx, war, attacker)
        spies.spend(ctx, war, defender)

    attacker_wins, margin = warfare.battle_odds(
        rng, a_power, d_power, home_ground=(host.id == defender.id),
        attack_general=a_general, defend_general=d_general)
    big = margin >= 0.45

    winner_men = a_men if attacker_wins else d_men
    loser_men = d_men if attacker_wins else a_men
    winner_dead, loser_dead = warfare.battle_losses(rng, winner_men, loser_men,
                                                    margin)
    if attacker_wins:
        war.attacker_losses += winner_dead
        war.defender_losses += loser_dead
    else:
        war.defender_losses += winner_dead
        war.attacker_losses += loser_dead

    shift = (0.08 + 0.21 * margin) * (1.0 if attacker_wins else -1.0)
    war.momentum = max(-1.0, min(1.0, war.momentum + shift))

    date = ctx.date_in(rng, year)
    battle = world.add_battle(
        name=texts.battle_name(rng, region, settlement), date=date,
        war_id=war.id, kind="битва",
        region_id=region.id if region is not None else "",
        settlement_id=settlement.id if settlement is not None else "",
        attacker_polity=attacker.id, defender_polity=defender.id,
        attacker_id=a_general.id if a_general is not None else "",
        defender_ids=[d_general.id] if d_general is not None else [],
        polity_ids=[attacker.id, defender.id],
        winner="нападавшие" if attacker_wins else "оборонявшиеся",
        attacker_men=a_men, defender_men=d_men,
        deaths=winner_dead + loser_dead, decisive=big,
    )
    title, text = texts.battle_text(rng, battle, attacker, defender, a_general,
                                    d_general, attacker_wins, big,
                                    winner_dead, loser_dead)
    arms = texts.arms_line(rng, a_race, d_race, attacker, defender, terrain)
    if arms:
        text = "%s %s" % (text, arms)
    if max(a_sold, d_sold) >= espionage.BRIBE_EDGE:
        text = "%s %s" % (text, spy_texts.bribed_line(rng))
    extra = _battle_fates(ctx, war, battle, attacker, defender, a_general,
                          d_general, attacker_wins, big, year, rng)
    if extra:
        text = "%s %s" % (text, " ".join(extra))
    _toll(ctx, settlement, winner_dead + loser_dead, rng)

    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="battle",
        title=title, text=text, importance=3 if big else 2,
        actors=[f.id for f in (a_general, d_general) if f is not None],
        subjects=[war.id, attacker.id, defender.id],
        region_id=battle.region_id, race_id=attacker.race_id)


def _battle_fates(ctx, war, battle, attacker, defender, a_general, d_general,
                  attacker_wins: bool, big: bool, year: int, rng) -> list:
    """Что стало с теми, кто вёл войска, и кто поднялся из безвестности."""
    world = ctx.world
    notes = []
    loser_general = d_general if attacker_wins else a_general
    winner_general = a_general if attacker_wins else d_general
    winner = attacker if attacker_wins else defender

    if loser_general is not None:
        risk = 0.30 if big else 0.14
        if rng.chance(risk):
            world.schedule_death(loser_general, battle.date, narrative.fate(
                ("пал в битве «%s»", "пала в битве «%s»"), loser_general.sex)
                % battle.name)
            battle.fallen_ids.append(loser_general.id)
            war.fallen_ids.append(loser_general.id)
        elif rng.chance(0.18):
            war.captured_ids.append(loser_general.id)
            battle.captured_ids.append(loser_general.id)
            loser_general.notes.append("в плену с %d года" % year)
            notes.append(texts.capture_text(rng, loser_general))
    if winner_general is not None and rng.chance(0.06):
        world.schedule_death(winner_general, battle.date, narrative.fate(
            ("пал в битве «%s»", "пала в битве «%s»"), winner_general.sex)
            % battle.name)
        battle.fallen_ids.append(winner_general.id)
        war.fallen_ids.append(winner_general.id)

    # Звезда из простых: решил битву — получил герб.
    if big and rng.chance(ENNOBLE_CHANCE):
        risen = _ennoble(ctx, winner, year, battle, rng)
        if risen is not None:
            notes.append(texts.rise_text(rng, risen))
            side = war.attacker_generals if winner.id == attacker.id \
                else war.defender_generals
            if risen.id not in side:
                side.append(risen.id)
    return notes


def _ennoble(ctx, polity, year: int, battle, rng):
    """Простолюдин, решивший сражение, получает землю и родовое имя."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    if not race.has_nobility:
        return None
    seats = _live_cities(world, polity)
    seat = rng.choice(sorted(seats, key=lambda s: s.id)) if seats else None
    sex = "f" if rng.chance(0.3) else "m"
    hero = ctx.make_figure(
        rng, race, year, role="полководец", region_id=battle.region_id,
        title=ctx.title_for(race, "founder", sex), sex=sex,
        home_id=seat.id if seat is not None else "", epithet_chance=0.9)
    hero.roles.append("возвысился на войне")
    houses_mod.found_house(ctx, hero, year, battle.date, seat=seat, rank=MINOR,
                           polity=polity, announce=False, importance=1)
    hero.deeds.append(battle.id)
    return hero


def _toll(ctx, settlement, deaths: int, rng) -> None:
    """Война выкашивает не только войско: округа сражения беднеет."""
    if settlement is None or settlement.status != ACTIVE:
        return
    loss = int(min(settlement.population * 0.12,
                   deaths * rng.uniform(0.2, 0.6)))
    settlement.population = max(50, settlement.population - loss)


# ---------------------------------------------------------------------------
# Осады
# ---------------------------------------------------------------------------

def _open_siege(ctx, war, attacker, defender, year: int, rng) -> None:
    """Войско садится под стенами. Города берут временем, а не силой."""
    world = ctx.world
    # Осаждает тот, кто наступает.
    if war.momentum >= 0:
        besieger, target = attacker, defender
    else:
        besieger, target = defender, attacker

    # Крепость на пути обойти нельзя: её берут прежде городов.
    forts = [item for item in world.fortresses_of(target)
             if item.id not in war.sieges]
    if forts and rng.chance(0.55):
        fortress = rng.choice(sorted(forts, key=lambda f: f.id))
        war.sieges[fortress.id] = {"years": 0, "besieger": besieger.id,
                                   "target": target.id, "fort": True}
        date = ctx.date_in(rng, year)
        title, text = fort_texts.fort_siege(rng, fortress, "начало")
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="siege_start",
            title=title, text=text, importance=2,
            subjects=[war.id, fortress.id, besieger.id, target.id],
            region_id=fortress.region_id, race_id=besieger.race_id)
        return
    cities = [city for city in _live_cities(world, target)
              if city.id not in war.sieges]
    if not cities:
        return
    # Если гавань врага уже заперта своим же флотом, войско идёт именно
    # туда: город без подвоза берут вдвое быстрее, и это знает всякий
    # воевода.
    sealed_ports = [city for city in cities if _sealed(war, city.id, besieger)]
    if sealed_ports and rng.chance(0.85):
        settlement = rng.choice(sorted(sealed_ports, key=lambda c: c.id))
        war.sieges[settlement.id] = {
            "years": 0, "besieger": besieger.id, "target": target.id,
        }
        date = ctx.date_in(rng, year)
        title, text = texts.siege_text(rng, besieger, settlement, "начало", 0)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="siege_start",
            title=title, text="%s %s" % (text, texts.sealed_line(rng)),
            importance=2,
            subjects=[war.id, settlement.id, besieger.id, target.id],
            region_id=settlement.region_id, race_id=besieger.race_id)
        return
    # Последний город добивают только в войне на искоренение или когда
    # исход уже решён: иначе держава за державой исчезают с карты, а
    # мира заключать становится не с кем.
    if len(_live_cities(world, target)) <= 1 \
            and war.aim != warfare.RUIN and abs(war.momentum) < 0.8:
        return
    # Берутся за то, что ближе и жирнее: столицу осаждают последней.
    settlement = rng.weighted([
        (city, float(max(80, city.population)) ** 0.5
         * (0.5 if city.is_capital else 1.0)
         * (2.5 if _sealed(war, city.id, besieger) else 1.0))
        for city in cities])

    war.sieges[settlement.id] = {
        "years": 0, "besieger": besieger.id, "target": target.id,
    }
    date = ctx.date_in(rng, year)
    title, text = texts.siege_text(rng, None, settlement, "начало", 0)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="siege_start",
        title=title, text=text, importance=2,
        subjects=[war.id, settlement.id, besieger.id, target.id],
        region_id=settlement.region_id, race_id=besieger.race_id)


def _tick_sieges(ctx, war, attacker, defender, year: int, rng) -> None:
    world = ctx.world
    for settlement_id in list(war.sieges):
        state = war.sieges[settlement_id]
        if state.get("fort"):
            _tick_fort_siege(ctx, war, settlement_id, state, year, rng)
            continue
        settlement = world.settlements.get(settlement_id)
        besieger = world.polities.get(state["besieger"])
        target = world.polities.get(state["target"])
        if settlement is None or settlement.status != ACTIVE \
                or besieger is None or target is None:
            war.sieges.pop(settlement_id, None)
            continue

        state["years"] += 1
        side = "attacker" if besieger.id == war.attacker_id else "defender"
        men, power, _ = _forces(ctx, war, besieger, side, year)
        # Под стенами решают машины и сапёры, а не конница.
        power *= troops_mod.worth(races_mod.get_race(besieger.race_id),
                                  under_walls=True)
        # Гарнизон невелик, но за стенами каждый стоит нескольких.
        garrison = warfare.host_power(
            max(warfare.LEVY_MIN, int(settlement.population * 0.07)), 1.65)
        starving = state["years"] >= 2 and rng.chance(0.5)
        # Гавань, запертую тем же врагом, что стоит под стенами, не
        # спасёт ни один подвоз: такой город падает вдвое быстрее.
        sealed = _sealed(war, settlement_id, besieger)
        result = warfare.siege_odds(rng, power, garrison, state["years"],
                                    starving, sealed=sealed)

        date = ctx.date_in(rng, year)
        if result == "держится":
            # Голод в осаждённом городе выкашивает жителей и без приступа.
            settlement.population = max(
                60, int(settlement.population * rng.uniform(0.90, 0.98)))
            if state["years"] % 2 == 0 or rng.chance(0.35):
                title, text = texts.siege_text(rng, None, settlement,
                                               "держится", state["years"])
                if sealed:
                    text = "%s %s" % (text, texts.sealed_line(rng))
                world.add_event(
                    date=date, era_index=world.era_index_at(year),
                    kind="siege_hold", title=title, text=text, importance=1,
                    subjects=[war.id, settlement.id],
                    region_id=settlement.region_id, race_id=target.race_id)
            continue

        war.sieges.pop(settlement_id, None)
        # Взятый или отбитый город блокадой больше не держат.
        if result == "пал":
            war.blockades.pop(settlement_id, None)
        if result == "снята":
            war.momentum = max(-1.0, min(1.0, war.momentum
                                         + (-0.18 if side == "attacker" else 0.18)))
            title, text = texts.siege_text(rng, None, settlement, "снята",
                                           state["years"])
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="siege_lifted", title=title, text=text, importance=2,
                subjects=[war.id, settlement.id],
                region_id=settlement.region_id, race_id=target.race_id)
            continue

        # Город пал.
        deaths = int(settlement.population * rng.uniform(0.10, 0.30))
        settlement.population = max(60, settlement.population - deaths)
        if side == "attacker":
            war.defender_losses += deaths
            war.momentum = min(1.0, war.momentum + 0.28)
        else:
            war.attacker_losses += deaths
            war.momentum = max(-1.0, war.momentum - 0.28)
        _seize_city(ctx, war, besieger, target, settlement, date, year, rng)

        battle = world.add_battle(
            name="Взятие города %s" % settlement.name, date=date,
            war_id=war.id, kind="штурм", region_id=settlement.region_id,
            settlement_id=settlement.id, attacker_polity=besieger.id,
            defender_polity=target.id, polity_ids=[besieger.id, target.id],
            winner="нападавшие", deaths=deaths, decisive=True)
        title, text = texts.siege_text(rng, battle, settlement, "пал",
                                       state["years"])
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="city_taken",
            title=title, text=text, importance=3,
            subjects=[war.id, settlement.id, besieger.id, target.id],
            region_id=settlement.region_id, race_id=besieger.race_id)


def _seize_city(ctx, war, winner, loser, settlement, date, year: int,
                rng) -> None:
    """Город переходит к победителю вместе с жителями."""
    world = ctx.world
    if settlement.id in loser.settlement_ids:
        loser.settlement_ids.remove(settlement.id)
    was_capital = settlement.is_capital
    settlement.polity_id = winner.id
    settlement.is_capital = False
    winner.settlement_ids.append(settlement.id)
    if settlement.region_id not in winner.region_ids:
        winner.region_ids.append(settlement.region_id)
    if settlement.id not in war.taken_ids:
        war.taken_ids.append(settlement.id)

    if was_capital:
        rest = _live_cities(world, loser)
        if rest:
            rest[0].is_capital = True
            loser.capital_id = rest[0].id
    if not _live_cities(world, loser):
        world.end_polity(loser, date, "завоёвана державой %s" % winner.name)
    world.refresh_populations()
    # Держава, у которой отняли все города её народа, меняет титульный
    # народ: иначе на престоле остаётся государь без единого подданного
    # своей крови.
    for polity in (winner, loser):
        if polity.status == ACTIVE:
            nations_mod.ensure_titular(ctx, polity, year)


# ---------------------------------------------------------------------------
# Мир
# ---------------------------------------------------------------------------

def _peace_place(ctx, war, attacker, defender, rng) -> tuple:
    """Где подписали мир — по нему договор и назовут.

    Выбирают место, где война и шла: взятый город, город у границы или
    землю, по которой прошли войска. Так в летописи и остаётся: «Мир в
    городе Роэнберг», «Мир в земле по имени Синяя Чащоба».
    """
    world = ctx.world
    options = []
    for settlement_id in war.taken_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is not None and settlement.status == ACTIVE:
            options.append((settlement.name, True, 3.0))
    for battle_id in war.battle_ids[-6:]:
        battle = world.battles.get(battle_id)
        if battle is None:
            continue
        settlement = world.settlements.get(battle.settlement_id)
        if settlement is not None and settlement.status == ACTIVE:
            options.append((settlement.name, True, 2.0))
        region = world.regions.get(battle.region_id)
        if region is not None:
            options.append((region.name, False, 1.2))
    for polity in (defender, attacker):
        cities = _live_cities(world, polity)
        if cities:
            options.append((cities[0].name, True, 0.8))
    if not options:
        return (defender.name, False)
    name, in_city = rng.weighted([((name, in_city), weight)
                                  for name, in_city, weight in options])
    return name, in_city


def _apply_terms(ctx, war, winner, loser, terms_map, date, year: int,
                 rng) -> dict:
    """Что победитель получает по миру."""
    world = ctx.world
    taken = []
    count = int(terms_map.get("cities", 0))
    if count:
        cities = _live_cities(world, loser)
        if war.aim == warfare.FREE:
            # Единокровцев забирают прежде прочих.
            cities.sort(key=lambda s: (s.race_id != winner.race_id, s.id))
        else:
            cities.sort(key=lambda s: (-s.population, s.id))
        # Побеждённого добивают только при подавляющем перевесе.
        keep = 0 if terms_map.get("raze") else 1
        count = min(count, max(0, len(cities) - keep))
        for settlement in cities[:count]:
            _seize_city(ctx, war, winner, loser, settlement, date, year, rng)
            taken.append(settlement)
            if terms_map.get("raze") and rng.chance(0.4):
                world.end_settlement(settlement, date, "срыт победителем",
                                     RUINED)
                war.razed += 1

    years = int(terms_map.get("tribute", 0))
    if years and loser.status == ACTIVE:
        loser.tribute_to = winner.id
        loser.tribute_until = year + years
    if terms_map.get("vassal") and loser.status == ACTIVE:
        loser.overlord_id = winner.id
    if terms_map.get("faith") and winner.faith_id and loser.status == ACTIVE:
        faith = world.faiths.get(winner.faith_id)
        if faith is not None:
            previous = world.faiths.get(loser.faith_id)
            loser.faith_id = faith.id
            if loser.id not in faith.polity_ids:
                faith.polity_ids.append(loser.id)
            if previous is not None and loser.id in previous.polity_ids:
                previous.polity_ids.remove(loser.id)
    # Победивший своего же сюзерена ига больше не несёт.
    if winner.tribute_to == loser.id or winner.overlord_id == loser.id:
        winner.tribute_to = ""
        winner.tribute_until = 0
        winner.overlord_id = ""
    if terms_map.get("plunder"):
        for settlement in _live_cities(world, loser):
            settlement.population = max(
                60, int(settlement.population * rng.uniform(0.86, 0.97)))
    if taken and war.id not in winner.conquests:
        winner.conquests.append(war.id)
    result = dict(terms_map)
    result["cities"] = len(taken)
    return result


def _finish(ctx, war, year: int, outcome: str, note: str = "") -> None:
    world = ctx.world
    attacker = world.polities.get(war.attacker_id)
    defender = world.polities.get(war.defender_id)
    rng = ctx.rng("war", "peace", war.id)
    date = ctx.date_in(rng, year, war.start if war.start.year == year else None)

    # Если побеждённой державы больше нет, мира не с кем заключать.
    gone = (attacker is None or attacker.status != ACTIVE
            or defender is None or defender.status != ACTIVE)
    if gone:
        outcome = warfare.ANNIHILATION

    terms_map = {}
    if outcome in (warfare.ATTACKER_WON, warfare.DEFENDER_WON):
        winner = attacker if outcome == warfare.ATTACKER_WON else defender
        loser = defender if outcome == warfare.ATTACKER_WON else attacker
        margin = min(1.0, abs(war.momentum))
        aim = war.aim if outcome == warfare.ATTACKER_WON else warfare.TRIBUTE
        terms_map = warfare.terms(aim, margin)
        terms_map = _apply_terms(ctx, war, winner, loser, terms_map, date,
                                 year, rng)
        winner.wars_won += 1
        loser.wars_lost += 1
        if loser.status != ACTIVE:
            outcome = warfare.ANNIHILATION

    peace = ""
    if outcome != warfare.ANNIHILATION and attacker is not None \
            and defender is not None:
        place, in_city = _peace_place(ctx, war, attacker, defender, rng)
        peace = texts.peace_name(rng, place, in_city,
                                 eternal=war.years >= 25 and rng.chance(0.5))
    world.end_war(war, date, outcome, peace)
    for polity in (attacker, defender):
        if polity is not None:
            polity.last_war = year
            polity.weariness = min(1.0, polity.weariness + 0.15)
    # Война, пройденная плечом к плечу, связывает крепче любого договора.
    for side, host in ((war.attacker_allies, attacker),
                       (war.defender_allies, defender)):
        if host is None:
            continue
        for ally_id in side:
            ally = world.polities.get(ally_id)
            if ally is None or ally.status != ACTIVE:
                continue
            ally.weariness = min(1.0, ally.weariness + 0.10)
            ally.last_war = year
            dip.set_relation(ally, host, dip.relation(ally, host.id) + 0.12)
            if war.id in ally.war_ids:
                ally.war_ids.remove(war.id)
    war.sieges = {}
    war.blockades = {}
    _release_captives(ctx, war, year, rng)
    _veterans(ctx, war, year, rng)

    title, text = texts.peace_text(rng, war, attacker or defender,
                                   defender or attacker, terms_map,
                                   war.deaths, note)
    subjects = [war.id] + [p.id for p in (attacker, defender) if p is not None]
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="war_end",
        title=title, text=text, importance=3 + min(2, war.scale // 2),
        subjects=subjects,
        region_id=(attacker.region_ids[0] if attacker is not None
                   and attacker.region_ids else ""),
        race_id=(attacker.race_id if attacker is not None else ""))
    _close_feud(ctx, war, year, rng)


NEGOTIATED = "мир выговорен, а не выигран"


def sue_for_peace(ctx, war, year: int, note: str = "") -> None:
    """Мир, выговоренный посольством: война кончается ничем.

    Этим пользуется ``systems/embassy``: удачное посольство разводит
    войска прежде, чем война доела обе стороны.
    """
    if war.end is not None:
        return
    if NEGOTIATED not in war.notes:
        war.notes.append(NEGOTIATED)
    _finish(ctx, war, year, warfare.WHITE, note)


def _release_captives(ctx, war, year: int, rng) -> None:
    """Пленных возвращают по миру — не всех и не сразу."""
    world = ctx.world
    for figure_id in list(war.captured_ids):
        figure = world.figures.get(figure_id)
        if figure is None or not figure.alive_at(year):
            continue
        if rng.chance(0.75):
            figure.notes.append("выкуплен из плена в %d году" % year
                                if figure.sex == "m"
                                else "выкуплена из плена в %d году" % year)
        else:
            world.schedule_death(figure, ctx.date_in(rng, year),
                                 narrative.fate(("умер в плену",
                                                 "умерла в плену"), figure.sex))


# ---------------------------------------------------------------------------
# Вековые распри
# ---------------------------------------------------------------------------

def _join_feud(ctx, war, attacker, defender, year: int, rng) -> None:
    """Третья война подряд между теми же — и у вражды появляется имя."""
    world = ctx.world
    pair = {attacker.id, defender.id}

    for feud in world.feuds.values():
        if set(feud.polity_ids) != pair or feud.status != ONGOING:
            continue
        # Если после последней войны прошло полтора срока памяти, это уже
        # не та распря, а новая: старую пора закрыть и назвать по длине.
        last = feud.start.year if feud.start else year
        for war_id in feud.war_ids:
            item = world.wars.get(war_id)
            if item is not None:
                last = max(last, (item.end or item.start).year)
        # Распря не может расти без конца: имя ей дали по её длине, и
        # оно не должно устареть. Слишком долгий перерыв или слишком
        # долгая жизнь — и это уже новая вражда, а не та же самая.
        span = year - (feud.start.year if feud.start else year)
        if year - last > FEUD_WINDOW // 2 or span > FEUD_WINDOW:
            _retire_feud(ctx, feud, year, rng)
            break
        feud.war_ids.append(war.id)
        war.feud_id = feud.id
        return

    previous = []
    for other in world.wars_of(attacker):
        if other.id == war.id or other.end is None:
            continue
        if defender.id not in (other.attacker_id, other.defender_id):
            continue
        if year - other.end.year <= FEUD_WINDOW:
            previous.append(other)
    if len(previous) < FEUD_WARS - 1:
        return

    previous.sort(key=lambda item: item.start.ordinal)
    span = year - previous[0].start.year
    if span > FEUD_WINDOW:
        # Три войны за тысячу лет — не распря, а просто соседство.
        return
    deaths = sum(item.deaths for item in previous)
    feud = world.add_feud(
        name=texts.feud_name(rng, span, deaths),
        polity_ids=sorted(pair), start=previous[0].start,
        war_ids=[item.id for item in previous] + [war.id], deaths=deaths)
    war.feud_id = feud.id
    for item in previous:
        item.feud_id = feud.id

    title, text = texts.feud_open(rng, feud, attacker, defender)
    world.add_event(
        date=war.start, era_index=world.era_index_at(year), kind="feud_start",
        title=title, text=text, importance=4,
        subjects=[feud.id, attacker.id, defender.id],
        race_id=attacker.race_id)


def _retire_feud(ctx, feud, year: int, rng) -> None:
    """Распря кончается тем, что о ней перестают вспоминать.

    Кончается она не в тот год, когда это заметили, а в год последней
    войны: молчание в счёт вражды не идёт.
    """
    world = ctx.world
    feud.status = "завершено"
    last = None
    for war_id in feud.war_ids:
        item = world.wars.get(war_id)
        if item is None:
            continue
        moment = item.end or item.start
        if last is None or moment.ordinal > last.ordinal:
            last = moment
    feud.end = last or ctx.date_in(rng, year)
    feud.deaths = sum(world.wars[wid].deaths for wid in feud.war_ids
                      if wid in world.wars)
    title, text = texts.feud_close(rng, feud, len(feud.war_ids), feud.deaths)
    first = world.polities.get(feud.polity_ids[0]) if feud.polity_ids else None
    world.add_event(
        date=feud.end, era_index=world.era_index_at(year), kind="feud_end",
        title=title, text=text, importance=3, subjects=[feud.id],
        race_id=first.race_id if first is not None else "")


def _close_feud(ctx, war, year: int, rng) -> None:
    """Распря кончается, когда одна из держав пала или устала насмерть."""
    world = ctx.world
    feud = world.feuds.get(war.feud_id)
    if feud is None or feud.status != ONGOING:
        return
    sides = [world.polities.get(pid) for pid in feud.polity_ids]
    alive = [item for item in sides if item is not None and item.status == ACTIVE]
    spent = all(item.weariness >= 0.75 for item in alive) if alive else True
    if len(alive) == 2 and not spent:
        return

    feud.status = "завершено"
    feud.end = war.end or ctx.date_in(rng, year)
    feud.deaths = sum(world.wars[wid].deaths for wid in feud.war_ids
                      if wid in world.wars)
    title, text = texts.feud_close(rng, feud, len(feud.war_ids), feud.deaths)
    world.add_event(
        date=feud.end, era_index=world.era_index_at(year), kind="feud_end",
        title=title, text=text, importance=4, subjects=[feud.id],
        race_id=sides[0].race_id if sides and sides[0] is not None else "")


# ---------------------------------------------------------------------------
# Морская война
# ---------------------------------------------------------------------------

STORM_CHANCE = 0.16         # доля морских сражений, которые решает буря
LANDING_CHANCE = 0.35       # шанс высадки, когда море за нами


def _ships(ctx, war, polity, side: str, year: int) -> tuple:
    """Сколько кораблей осталось у стороны и какова их сила."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    built = war.attacker_ships if side == "attacker" else war.defender_ships
    lost = war.attacker_ships_lost if side == "attacker" \
        else war.defender_ships_lost
    fresh = warfare.fleet(world, polity, race, world.era_index_at(year))
    ships = max(0, min(fresh, built - lost + max(0, fresh // 12)))
    admiral = _live_commander(world, war, side, year)
    return ships, warfare.sea_power(ships, race, admiral), admiral


def _sea_year(ctx, war, attacker, defender, year: int, rng) -> bool:
    """Год морской войны: бой на воде, блокада или высадка.

    Море решает не так, как суша: флот можно потерять за один день, и
    тогда заморская война кончается, не начавшись.
    """
    if war.blockades:
        _tick_blockades(ctx, war, attacker, defender, year, rng)

    a_ships, a_power, a_admiral = _ships(ctx, war, attacker, "attacker", year)
    d_ships, d_power, d_admiral = _ships(ctx, war, defender, "defender", year)
    if a_ships < 1 and d_ships < 1:
        return False

    # Флоты сходятся не каждый год: море велико.
    if a_ships >= 1 and d_ships >= 1 and rng.chance(0.55):
        _sea_battle(ctx, war, attacker, defender, a_ships, a_power, d_ships,
                    d_power, a_admiral, d_admiral, year, rng)
        return True
    # Море за нами — значит, можно запереть гавань или высадиться.
    if a_ships > d_ships * 1.4:
        if rng.chance(LANDING_CHANCE):
            return _landing(ctx, war, attacker, defender, year, rng)
        if len(war.blockades) < 2 and rng.chance(0.5):
            _open_blockade(ctx, war, attacker, defender, year, rng)
            return True
    elif d_ships > a_ships * 1.4 and len(war.blockades) < 2 \
            and rng.chance(0.35):
        _open_blockade(ctx, war, defender, attacker, year, rng)
        return True
    return False


def _sea_battle(ctx, war, attacker, defender, a_ships, a_power, d_ships,
                d_power, a_admiral, d_admiral, year: int, rng) -> None:
    world = ctx.world
    storm = rng.chance(STORM_CHANCE)
    attacker_wins, margin = warfare.sea_battle(
        rng, a_power, d_power, home_waters=True, storm=storm)

    winner_ships = a_ships if attacker_wins else d_ships
    loser_ships = d_ships if attacker_wins else a_ships
    won_lost, lost_lost = warfare.sea_losses(rng, winner_ships, loser_ships,
                                             margin, storm)
    if attacker_wins:
        war.attacker_ships_lost += won_lost
        war.defender_ships_lost += lost_lost
    else:
        war.defender_ships_lost += won_lost
        war.attacker_ships_lost += lost_lost

    deaths = (won_lost + lost_lost) * warfare.CREW_PER_SHIP
    if attacker_wins:
        war.attacker_losses += won_lost * warfare.CREW_PER_SHIP
        war.defender_losses += lost_lost * warfare.CREW_PER_SHIP
    else:
        war.defender_losses += won_lost * warfare.CREW_PER_SHIP
        war.attacker_losses += lost_lost * warfare.CREW_PER_SHIP

    shift = (0.06 + 0.16 * margin) * (1.0 if attacker_wins else -1.0)
    if storm:
        shift *= 0.3
    war.momentum = max(-1.0, min(1.0, war.momentum + shift))

    harbours = warfare.ports(world, defender if attacker_wins else attacker)
    settlement = rng.choice(sorted(harbours, key=lambda s: s.id)) \
        if harbours and rng.chance(0.7) else None
    region = world.regions.get(settlement.region_id) if settlement is not None \
        else (world.regions.get(defender.region_ids[0])
              if defender.region_ids else None)
    date = ctx.date_in(rng, year)
    battle = world.add_battle(
        name=texts.sea_battle_name(rng, region, settlement), date=date,
        war_id=war.id, kind="морской бой",
        region_id=region.id if region is not None else "",
        settlement_id=settlement.id if settlement is not None else "",
        attacker_polity=attacker.id, defender_polity=defender.id,
        attacker_id=a_admiral.id if a_admiral is not None else "",
        defender_ids=[d_admiral.id] if d_admiral is not None else [],
        polity_ids=[attacker.id, defender.id],
        winner="нападавшие" if attacker_wins else "оборонявшиеся",
        attacker_men=a_ships, defender_men=d_ships,
        deaths=deaths, decisive=margin >= 0.5)

    winner = attacker if attacker_wins else defender
    loser = defender if attacker_wins else attacker
    title, text = texts.sea_battle_text(rng, battle, winner, loser, won_lost,
                                        lost_lost, loser_ships, storm)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="sea_battle",
        title=title, text=text, importance=3 if margin >= 0.5 else 2,
        actors=[f.id for f in (a_admiral, d_admiral) if f is not None],
        subjects=[war.id, attacker.id, defender.id],
        region_id=battle.region_id, race_id=winner.race_id)


def _open_blockade(ctx, war, besieger, target, year: int, rng) -> None:
    """Флот запирает чужую гавань: торговля встаёт, город беднеет."""
    world = ctx.world
    harbours = [item for item in warfare.ports(world, target)
                if item.id not in war.blockades]
    if not harbours:
        return
    # Гавань осаждённого города запирают прежде прочих: флот и войско
    # вместе берут город вдвое быстрее, чем порознь.
    besieged = [item for item in harbours
                if _besieged_by(war, item.id, besieger)]
    if besieged and rng.chance(0.85):
        settlement = rng.choice(sorted(besieged, key=lambda s: s.id))
    else:
        settlement = rng.weighted([(item, float(max(80, item.population)))
                                   for item in harbours])
    war.blockades[settlement.id] = {"years": 0, "by": besieger.id,
                                    "target": target.id}
    date = ctx.date_in(rng, year)
    title, text = texts.blockade_text(rng, settlement, "начало", 0)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="blockade_start",
        title=title, text=text, importance=2,
        subjects=[war.id, settlement.id, besieger.id, target.id],
        region_id=settlement.region_id, race_id=besieger.race_id)


def _sealed(war, settlement_id: str, besieger) -> bool:
    """Заперта ли гавань этого города тем же, кто стоит под стенами."""
    state = war.blockades.get(settlement_id)
    return state is not None and state.get("by") == besieger.id


def _besieged_by(war, settlement_id: str, besieger) -> bool:
    """Осаждён ли этот город с суши тем же, кто подводит флот."""
    state = war.sieges.get(settlement_id)
    return state is not None and state.get("besieger") == besieger.id


def _tick_blockades(ctx, war, attacker, defender, year: int, rng) -> None:
    world = ctx.world
    for settlement_id in list(war.blockades):
        state = war.blockades[settlement_id]
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            war.blockades.pop(settlement_id, None)
            continue
        state["years"] += 1
        # Запертая гавань беднеет и пустеет — но медленнее, чем от осады.
        settlement.population = max(
            60, int(settlement.population * rng.uniform(0.95, 0.995)))
        side = "attacker" if state["by"] == war.attacker_id else "defender"
        war.momentum = max(-1.0, min(1.0, war.momentum
                                     + (0.05 if side == "attacker" else -0.05)))

        date = ctx.date_in(rng, year)
        # Пока под стенами стоит своё же войско, флот от гавани не уйдёт.
        lift = min(0.5, 0.12 + 0.10 * state["years"])
        if settlement_id in war.sieges:
            lift *= 0.3
        if rng.chance(lift):
            war.blockades.pop(settlement_id, None)
            title, text = texts.blockade_text(rng, settlement, "снята",
                                              state["years"])
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="blockade_end", title=title, text=text, importance=2,
                subjects=[war.id, settlement.id],
                region_id=settlement.region_id, race_id=settlement.race_id)
        elif state["years"] % 2 == 0:
            title, text = texts.blockade_text(rng, settlement, "держится",
                                              state["years"])
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="blockade_hold", title=title, text=text, importance=1,
                subjects=[war.id, settlement.id],
                region_id=settlement.region_id, race_id=settlement.race_id)


def _landing(ctx, war, attacker, defender, year: int, rng) -> bool:
    """Десант за морем: войско сходит на чужой берег и сразу принимает бой."""
    world = ctx.world
    harbours = warfare.ports(world, defender)
    if not harbours:
        return False
    settlement = rng.weighted([(item, float(max(80, item.population)))
                               for item in harbours])
    war.landings += 1
    date = ctx.date_in(rng, year)
    title, text = texts.landing_text(rng, settlement)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="landing",
        title=title, text=text, importance=3,
        subjects=[war.id, settlement.id, attacker.id, defender.id],
        region_id=settlement.region_id, race_id=attacker.race_id)
    # Высадившееся войско тут же и дерётся: отступать ему некуда.
    war.momentum = min(1.0, war.momentum + 0.08)
    _battle(ctx, war, attacker, defender, year, rng)
    if settlement.id not in war.sieges and rng.chance(0.55):
        war.sieges[settlement.id] = {"years": 0, "besieger": attacker.id,
                                     "target": defender.id}
    return True


# ---------------------------------------------------------------------------
# Крепости и наёмники на войне
# ---------------------------------------------------------------------------

def _tick_fort_siege(ctx, war, fortress_id: str, state: dict, year: int,
                     rng) -> None:
    """Осада крепости: дольше городской и вернее решает судьбу земли."""
    world = ctx.world
    fortress = world.fortresses.get(fortress_id)
    besieger = world.polities.get(state["besieger"])
    target = world.polities.get(state["target"])
    if fortress is None or fortress.status != ACTIVE \
            or besieger is None or target is None:
        war.sieges.pop(fortress_id, None)
        return

    state["years"] += 1
    side = "attacker" if besieger.id == war.attacker_id else "defender"
    men, power, _ = _forces(ctx, war, besieger, side, year)
    power *= troops_mod.worth(races_mod.get_race(besieger.race_id),
                              under_walls=True)
    garrison = warfare.host_power(max(120, 90 * fortress.strength),
                                  1.4 + 0.22 * fortress.strength)
    result = warfare.siege_odds(rng, power, garrison, state["years"],
                                starving=state["years"] >= 3 and rng.chance(0.4))

    date = ctx.date_in(rng, year)
    if result == "держится":
        if state["years"] % 3 == 0:
            title, text = fort_texts.fort_siege(
                rng, fortress, "держится", _years_word(state["years"]))
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="siege_hold", title=title, text=text, importance=1,
                subjects=[war.id, fortress.id],
                region_id=fortress.region_id, race_id=target.race_id)
        return

    war.sieges.pop(fortress_id, None)
    if result == "снята":
        war.momentum = max(-1.0, min(1.0, war.momentum
                                     + (-0.10 if side == "attacker" else 0.10)))
        title, text = fort_texts.fort_siege(rng, fortress, "снята")
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="siege_lifted",
            title=title, text=text, importance=2,
            subjects=[war.id, fortress.id], region_id=fortress.region_id,
            race_id=target.race_id)
        return

    # Крепость взята.
    deaths = int(90 * fortress.strength * rng.uniform(0.4, 1.1))
    if side == "attacker":
        war.defender_losses += deaths
        war.momentum = min(1.0, war.momentum + 0.22)
    else:
        war.attacker_losses += deaths
        war.momentum = max(-1.0, war.momentum - 0.22)
    soldiery.take_fortress(ctx, fortress, besieger, year, rng)
    world.add_battle(
        name="Взятие крепости %s" % fortress.name, date=date, war_id=war.id,
        kind="штурм", region_id=fortress.region_id,
        attacker_polity=besieger.id, defender_polity=target.id,
        polity_ids=[besieger.id, target.id], winner="нападавшие",
        deaths=deaths, decisive=True)
    # Крепость, взятую в войне на искоренение, не оставляют стоять.
    if war.aim == warfare.RUIN and rng.chance(0.4):
        soldiery.raze_fortress(ctx, fortress, year, rng)


def _years_word(years: int) -> str:
    from ..timeline import years_text
    return years_text(max(1, years))


def _maybe_hire(ctx, war, attacker, defender, year: int, rng) -> None:
    """Богатая держава воюет чужими руками, если есть кого нанять."""
    world = ctx.world
    free = soldiery.free_companies(world)
    if not free:
        return
    for polity in (attacker, defender):
        if polity is None or polity.status != ACTIVE:
            continue
        already = any(world.companies[cid].employer_id == polity.id
                      for cid in world.active_companies)
        if already:
            continue
        chance = soldiery.HIRE_CHANCE * 0.2
        # Тот, кому приходится туго, нанимает охотнее.
        losing = (war.momentum < -0.2) if polity.id == attacker.id \
            else (war.momentum > 0.2)
        if losing:
            chance *= 2.0
        if polity.hunger:
            chance *= max(0.3, 1.0 - polity.hunger)
        if not rng.chance(min(0.5, chance)):
            continue
        company = rng.choice(sorted(free, key=lambda c: c.id))
        soldiery.hire(ctx, company, polity, year, rng)
        free = [item for item in free if item.id != company.id]
        if not free:
            return


def _veterans(ctx, war, year: int, rng) -> None:
    """После войны остаются те, кому некуда возвращаться."""
    world = ctx.world
    if not rng.chance(soldiery.BIRTH_AFTER_WAR):
        return
    for polity_id in (war.attacker_id, war.defender_id):
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        if war.deaths < 200:
            return
        soldiery.spawn_company(ctx, polity, year, rng, reason=war.name)
        return
