# -*- coding: utf-8 -*-
"""Политика держав: отношения, договоры, союзы и их распад.

Раз в десятилетие каждая пара соседей смотрит друг на друга заново.

1. **Отношение** сдвигается к тому, каким ему следует быть по нынешнему
   положению дел: по родству народов, вере, торговле, общему врагу,
   родству домов, старым войнам и дани. Сдвигается медленно — обиды и
   приязнь живут дольше причин, их породивших.
2. **Договор.** Если отношение доросло до следующей ступени, её берут:
   сначала ненападение, потом торговый договор, потом брачный союз домов,
   и лишь потом союз. Через ступень не прыгают.
3. **Разрыв.** Если отношение упало ниже той черты, на которой договор
   держался, его рвут — и это событие для летописи.
4. **Союз.** Три державы, связанные союзными договорами между собой,
   сводят их в один союз с именем и целью. Союз распадается от общей
   беды, от нового государя, от измены и просто от времени.
"""

from __future__ import annotations

from .. import diplomacy as dip
from .. import narrative_diplomacy as texts
from .. import races as races_mod
from ..models import ACTIVE

DRIFT = 0.22                # какую долю пути отношение проходит за такт
PACT_CHANCE = 0.55          # шанс, что созревший договор действительно подпишут
BREAK_CHANCE = 0.55         # и что просроченный разорвут
LEAGUE_MIN = 3              # со скольких союзников складывается союз
LEAGUE_DECAY = 0.02         # шанс, что союз рассыплется сам за такт
MAX_PAIRS = 10              # с кем держава вообще имеет дело
TICK_EVERY = 20             # раз во столько лет державы пересматривают дела


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    # Политика движется медленнее хозяйства: пересматривать дела каждое
    # десятилетие незачем, а считать — дорого.
    if year % TICK_EVERY:
        return
    period = TICK_EVERY
    rng = ctx.rng("diplomacy", year)
    index = dip.Index(world)
    owners = {}
    for polity_id in world.active_polities:
        for region_id in world.polities[polity_id].region_ids:
            owners.setdefault(region_id, []).append(polity_id)
    seen = set()

    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states or race.is_evil:
            continue
        for other in circle(ctx, world, polity, year, owners):
            key = tuple(sorted((polity.id, other.id)))
            if key in seen:
                continue
            seen.add(key)
            _tend(ctx, polity, other, year, period, rng, index)

    _tend_leagues(ctx, year, period, rng)


def circle(ctx, world, polity, year: int, owners=None) -> list:
    """С кем эта держава вообще имеет дело: соседи, торговые партнёры, родня.

    Мир в сто держав — это пять тысяч пар; политика между теми, кто друг
    о друге и не слышал, не нужна никому.
    """
    out = {}
    reach = set(polity.region_ids)
    for region_id in polity.region_ids:
        region = world.regions.get(region_id)
        if region is not None:
            reach.update(region.neighbors)
            reach.update(region.sea_links)

    own_race = races_mod.get_race(polity.race_id)
    candidates = set()
    if owners is not None:
        for region_id in reach:
            candidates.update(owners.get(region_id, ()))
    else:
        candidates = set(world.active_polities)
    for other_id in candidates:
        if other_id == polity.id or other_id not in world.polities:
            continue
        other = world.polities[other_id]
        if other.status != ACTIVE:
            continue
        if not dip.can_deal(own_race, races_mod.get_race(other.race_id)):
            continue
        out[other_id] = other
    for route_id in polity.routes:
        route = world.routes.get(route_id)
        if route is None:
            continue
        other = world.polities.get(route.seller_id if route.buyer_id == polity.id
                                   else route.buyer_id)
        if other is not None and other.status == ACTIVE \
                and dip.can_deal(own_race, races_mod.get_race(other.race_id)):
            out[other.id] = other

    # С теми, с кем уже связаны словом, дела ведут в первую очередь:
    # иначе договор может остаться без присмотра и никогда не порваться.
    bound = set()
    for pact in world.pacts_of(polity):
        other = world.polities.get(pact.other(polity.id))
        if other is not None and other.status == ACTIVE:
            out[other.id] = other
            bound.add(other.id)

    rows = sorted(out.values(),
                  key=lambda p: (p.id not in bound, -p.population, p.id))
    return rows[:MAX_PAIRS]


def _tend(ctx, first, second, year: int, period: int, rng, index=None) -> None:
    world = ctx.world
    reasons = dip.reasons(world, first, second, year, index)
    target = max(-1.0, min(1.0, sum(weight for _, weight in reasons)))
    value = dip.relation(first, second.id)

    # Война перевешивает всё: пока воюют, о приязни речи нет.
    if world.war_between(first.id, second.id) is not None:
        target = min(target, -0.55)
    value += (target - value) * DRIFT * (period / 10.0)
    dip.set_relation(first, second, value)

    pact = world.pact_between(first.id, second.id)
    if pact is not None:
        if value < dip.PACT_BREAK[pact.kind] and rng.chance(BREAK_CHANCE):
            _break_pact(ctx, pact, first, second, reasons, year, rng)
            return
        # Договор не потолок, а ступень: если приязнь выросла, поднимаются
        # выше. Без этого державы навеки застревали бы на ненападении.
        higher = dip.pact_kind_for(value, pact.kind)
        if higher and rng.chance(PACT_CHANCE) \
                and world.war_between(first.id, second.id) is None:
            world.end_pact(pact, ctx.date_in(rng, year), "перерос в %s"
                           % dip.PACT_NAMES[higher])
            league = world.leagues.get(pact.league_id)
            if league is not None and league.status == ACTIVE:
                pact.league_id = ""
            make_pact(ctx, higher, first, second, reasons, year, rng)
        return

    kind = dip.pact_kind_for(value, _last_kind(world, first, second))
    if not kind or not rng.chance(PACT_CHANCE):
        return
    if world.war_between(first.id, second.id) is not None:
        return
    make_pact(ctx, kind, first, second, reasons, year, rng)


def _last_kind(world, first, second) -> str:
    """До какой ступени эти двое доходили прежде."""
    best = ""
    for pact_id in first.pact_ids:
        pact = world.pacts.get(pact_id)
        if pact is None or second.id not in (pact.first_id, pact.second_id):
            continue
        if not best or dip.PACT_ORDER.index(pact.kind) > dip.PACT_ORDER.index(best):
            best = pact.kind
    return best


# ---------------------------------------------------------------------------
# Договоры
# ---------------------------------------------------------------------------

def make_pact(ctx, kind: str, first, second, reasons, year: int, rng):
    world = ctx.world
    date = ctx.date_in(rng, year)
    pact = world.add_pact(
        kind=kind, first_id=first.id, second_id=second.id, signed=date,
        reasons=[name for name, weight in reasons if weight > 0.05][:3])

    # Брачный союз — это не бумага, а свадьба: её играют по-настоящему.
    if kind == dip.MARRIAGE:
        _wed_houses(ctx, first, second, year, date, rng)
    # Подписанный договор сам по себе греет отношения.
    dip.set_relation(first, second,
                     dip.relation(first, second.id) + 0.10)

    title, text = texts.pact_made(rng, pact, first, second, reasons)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="pact",
        title=title, text=text,
        importance=3 if kind in (dip.ALLIANCE, dip.MARRIAGE) else 2,
        subjects=[pact.id, first.id, second.id],
        region_id=first.region_ids[0] if first.region_ids else "",
        race_id=first.race_id)
    if kind == dip.ALLIANCE:
        _maybe_league(ctx, first, year, rng)
    return pact


def _wed_houses(ctx, first, second, year: int, date, rng) -> None:
    """Брачный договор женит наследников двух правящих домов.

    Это и есть «союз аристократии разных стран»: родство домов живёт
    дольше любого договора и потом само становится поводом к войне за
    наследство.
    """
    world = ctx.world
    groom = _marriageable(world, first, year)
    bride = _marriageable(world, second, year)
    if groom is None or bride is None:
        return
    if groom.sex == bride.sex:
        return
    groom.spouse_id = bride.id
    bride.spouse_id = groom.id
    groom.married = date
    bride.married = date
    for figure in (groom, bride):
        figure.notes.append("брак по договору держав, %d год" % year)


def _marriageable(world, polity, year: int):
    """Незанятый взрослый из правящего дома."""
    house = world.houses.get(polity.house_id)
    if house is None:
        return None
    race = races_mod.get_race(polity.race_id)
    people = [figure for figure in world.house_members(house, alive_in_year=year)
              if not figure.spouse_id
              and figure.age_at(year) >= race.adulthood
              and figure.id != polity.ruler_id]
    if not people:
        return None
    people.sort(key=lambda f: (f.birth.ordinal, f.id))
    return people[0]


def _break_pact(ctx, pact, first, second, reasons, year: int, rng) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year)
    world.end_pact(pact, date, "отношения испортились")
    league = world.leagues.get(pact.league_id)
    if league is not None and league.status == ACTIVE:
        _shrink_league(ctx, league, first, year, date, rng)
    title, text = texts.pact_broken(rng, pact, first, second, reasons)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="pact_broken",
        title=title, text=text,
        importance=3 if pact.kind == dip.ALLIANCE else 2,
        subjects=[pact.id, first.id, second.id], race_id=first.race_id)


# ---------------------------------------------------------------------------
# Союзы
# ---------------------------------------------------------------------------

def _allies_of(world, polity) -> list:
    out = []
    for pact in world.pacts_of(polity):
        if pact.kind != dip.ALLIANCE:
            continue
        other = world.polities.get(pact.other(polity.id))
        if other is not None and other.status == ACTIVE:
            out.append((other, pact))
    return out


def _maybe_league(ctx, polity, year: int, rng) -> None:
    """Цепь союзных договоров однажды становится союзом с именем."""
    world = ctx.world
    if polity.league_id:
        return
    circle = [polity]
    pacts = []
    for other, pact in _allies_of(world, polity):
        if other.league_id:
            continue
        circle.append(other)
        pacts.append(pact)
    if len(circle) < LEAGUE_MIN:
        return

    date = ctx.date_in(rng, year)
    kind = dip.league_kind(world, circle)
    leader = dip.strongest(world, circle)
    place = ""
    region = world.regions.get(leader.region_ids[0]) if leader.region_ids else None
    if region is not None:
        place = region.landmass or region.sea or region.name
    league = world.add_league(
        name=texts.league_name(rng, kind, circle, place), kind=kind,
        founded=date, member_ids=[item.id for item in circle],
        leader_id=leader.id, pact_ids=[item.id for item in pacts])
    for pact in pacts:
        pact.league_id = league.id

    title, text = texts.league_open(rng, league, circle)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="league_start",
        title=title, text=text, importance=4,
        subjects=[league.id] + [item.id for item in circle],
        region_id=leader.region_ids[0] if leader.region_ids else "",
        race_id=leader.race_id)


def _shrink_league(ctx, league, leaver, year: int, date, rng) -> None:
    """Из союза выходят поодиночке; когда остаётся двое — союза нет."""
    world = ctx.world
    if leaver.id in league.member_ids:
        league.member_ids.remove(leaver.id)
    if leaver.league_id == league.id:
        leaver.league_id = ""
    members = [world.polities.get(pid) for pid in league.member_ids]
    members = [item for item in members if dip.alive(world, item)]
    if len(members) >= LEAGUE_MIN:
        # Ушедший мог быть и первым среди равных — тогда выбирают нового.
        if league.leader_id not in league.member_ids:
            leader = dip.strongest(world, members)
            league.leader_id = leader.id if leader is not None else ""
        return
    _close_league(ctx, league, "союзников осталось слишком мало", year, date, rng)


def _close_league(ctx, league, reason: str, year: int, date, rng) -> None:
    """Союз, сложившийся и распавшийся в один год, не должен кончаться
    раньше, чем начался: дата распада не бывает раньше даты клятвы."""
    world = ctx.world
    if league.status != ACTIVE:
        return
    if league.founded is not None and date.ordinal < league.founded.ordinal:
        date = league.founded
    years = year - league.founded.year
    world.end_league(league, date, reason)
    title, text = texts.league_close(rng, league, reason, years)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="league_end",
        title=title, text=text, importance=3, subjects=[league.id],
        race_id="")


def _tend_leagues(ctx, year: int, period: int, rng) -> None:
    """Союзы живут, пока есть кому их держать."""
    world = ctx.world
    for league_id in list(world.active_leagues):
        league = world.leagues.get(league_id)
        if league is None or league.status != ACTIVE:
            continue
        members = [world.polities.get(pid) for pid in league.member_ids]
        members = [item for item in members if dip.alive(world, item)]
        league.member_ids = [item.id for item in members]
        if members and league.leader_id not in league.member_ids:
            leader = dip.strongest(world, members)
            league.leader_id = leader.id if leader is not None else ""
        if len(members) < LEAGUE_MIN:
            _close_league(ctx, league, "союзников осталось слишком мало",
                          year, ctx.date_in(rng, year), rng)
            continue

        # Союзник, схватившийся с союзником, разваливает союз вернее врага.
        for index, first in enumerate(members):
            for second in members[index + 1:]:
                if world.war_between(first.id, second.id) is not None:
                    _close_league(ctx, league,
                                  "двое союзников сами сошлись в войне",
                                  year, ctx.date_in(rng, year), rng)
                    break
            if league.status != ACTIVE:
                break
        if league.status != ACTIVE:
            continue

        # Общая беда распускает союзы: каждый спасает своё.
        if ctx.world_darkness > 0.4 and rng.chance(0.35 * (period / 10.0)):
            _close_league(ctx, league,
                          "мир накрыла общая беда, и каждый стал спасать своё",
                          year, ctx.date_in(rng, year), rng)
            continue
        if rng.chance(LEAGUE_DECAY * (period / 10.0)):
            _close_league(ctx, league, rng.choice(texts.LEAGUE_BREAK_REASONS),
                          year, ctx.date_in(rng, year), rng)


# ---------------------------------------------------------------------------
# Смена государя пересматривает клятвы
# ---------------------------------------------------------------------------

def review_pacts(ctx, polity, year: int) -> None:
    """Новый государь не обязан держать клятвы прежнего.

    Вызывается при восшествии: чем круче нрав и чем хуже отношения, тем
    вернее союз доживает последние дни.
    """
    world = ctx.world
    ruler = world.figures.get(polity.ruler_id)
    if ruler is None:
        return
    rng = ctx.rng("pact_review", polity.id, year)
    alignment = int(getattr(ruler, "alignment", 0) or 0)
    for pact in world.pacts_of(polity):
        other = world.polities.get(pact.other(polity.id))
        if other is None or other.status != ACTIVE:
            continue
        value = dip.relation(polity, other.id)
        chance = 0.06 + 0.05 * max(0, -alignment) + max(0.0, 0.3 - value)
        if pact.kind == dip.MARRIAGE:
            chance *= 0.4              # родство рвать труднее, чем договор
        if not rng.chance(min(0.5, chance)):
            continue
        reasons = dip.reasons(world, polity, other, year)
        _break_pact(ctx, pact, polity, other, reasons, year, rng)
