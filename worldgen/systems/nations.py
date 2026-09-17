# -*- coding: utf-8 -*-
"""Народы державы: завоевания, притеснения, восстания, врастание.

Раз в десятилетие держава смотрит на себя: кто в ней живёт и что с этими
людьми делать. А сильная держава при случае смотрит и на соседа.

Порядок такой:

1. **Война.** Сильная страна берёт у соседа города. Жители остаются на
   месте — меняется только то, чьи они. Так однонародная держава
   становится многонародной.
2. **Указ.** Правитель решает, как обходиться с иными народами: от равных
   прав до искоренения. Решение зависит от нрава народа, веры державы
   и самого правителя, и может меняться со сменой престола.
3. **Плата.** Жестокая держава изводит меньшинства — и копит их обиду.
   Держава равных прав растворяет их в себе мирно.
4. **Ответ.** Накопленная обида поднимает восстание. Оно кончается
   по-разному: его давят, оно отделяет часть страны, или — если народ
   уже многочислен — сажает на престол своего.
"""

from __future__ import annotations

from .. import nations as pol
from .. import narrative
from .. import narrative_nations as texts
from .. import races as races_mod
from .. import rulers as rulers_mod
from ..models import ACTIVE, GREAT
from ..world import RURAL_FACTOR
from . import houses as houses_mod
from . import succession

REVOLT_RATE = 0.9           # множитель к накопленной обиде
DECREE_CHANCE = 0.22        # шанс, что новый правитель меняет закон
ASSIMILATE_CHANCE = 0.55
# Между сменами титульного народа должно пройти хотя бы несколько веков:
# иначе престол начинает ходить туда-обратно каждые двести лет.
TITULAR_COOLDOWN = 500


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    """Войны за землю переехали в systems/war.py — здесь их больше нет.

    Прежде завоевание было одним броском: сильный забирал города и на
    этом всё кончалось. Теперь у войны есть причина, длина, сражения и
    мир, а этот модуль занят тем, что происходит внутри державы.
    """
    return


def _live_cities(world, polity) -> list:
    return [world.settlements[sid] for sid in polity.settlement_ids
            if sid in world.settlements
            and world.settlements[sid].status == ACTIVE]


def pick_general(ctx, rng, polity, race, year: int):
    """Полководец похода: живой воин державы или новое имя.

    Сначала смотрят на знать: у великого дома всегда найдётся младший
    сын, которому нужна слава. Если знати нет — поднимают человека со
    стороны, и он может основать собственный род.
    """
    world = ctx.world
    houses = [world.houses[hid] for hid in polity.house_ids
              if hid in world.houses and world.houses[hid].status == ACTIVE]
    for house in sorted(houses, key=lambda h: -h.prestige):
        members = [world.figures[fid] for fid in house.living
                   if fid in world.figures and world.figures[fid].alive_at(year)
                   and world.figures[fid].age_at(year) >= race.adulthood]
        fighters = [f for f in members if "правитель" not in f.roles]
        if fighters:
            general = rng.choice(sorted(fighters, key=lambda f: f.id))
            if "полководец" not in general.roles:
                general.roles.append("полководец")
            return general
    sex = "f" if rng.chance(0.35) else "m"
    region_id = polity.region_ids[0] if polity.region_ids else ""
    return ctx.make_figure(rng, race, year, role="полководец",
                           region_id=region_id, title="воевода" if sex == "m"
                           else "воеводша", sex=sex, epithet_chance=0.8)


def _fresh_policy(ctx, rng, polity) -> str:
    race = races_mod.get_race(polity.race_id)
    faith = ctx.world.faiths.get(polity.faith_id)
    return pol.default_policy(rng, race,
                              faith.alignment if faith is not None else 0.0,
                              ctx.dark_tilt)


# ---------------------------------------------------------------------------
# Медленный такт: обида, притеснение, врастание, восстания
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    world.refresh_populations()
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None:
            continue
        _tend(ctx, polity, year, period)


def _tend(ctx, polity, year: int, period: int) -> None:
    minorities = [(race_id, souls) for race_id, souls in polity.minorities()
                  if polity.share_of(race_id) >= pol.MIN_MINORITY_SHARE]
    if not minorities:
        polity.grievance = {}
        return

    rng = ctx.rng("nations", polity.id, year)
    if not polity.policy:
        polity.policy = _fresh_policy(ctx, rng, polity)
        polity.policy_since = year

    _maybe_decree(ctx, polity, rng, year)

    drift = pol.POLICY_GRIEVANCE.get(polity.policy, 0.01) * (period / 10.0)
    # Один и тот же закон при добром государе жжёт слабее, при звере —
    # сильнее: подданные помнят не букву указа, а руку, которая его держит.
    harsh = rulers_mod.harshness(ctx.world, polity)
    if drift > 0:
        drift *= max(0.25, 1.0 + harsh * 0.45)       # зверь растравляет
    else:
        drift *= max(0.25, 1.0 - harsh * 0.35)       # добрый залечивает
    for race_id, souls in minorities:
        share = polity.share_of(race_id)
        # Чем многочисленнее народ, тем громче он помнит обиду.
        value = polity.grievance.get(race_id, 0.0) + drift * (0.6 + share)
        polity.grievance[race_id] = max(0.0, min(1.0, value))

    _bleed(ctx, polity, rng, year, period, minorities)
    _assimilate(ctx, polity, rng, year, period, minorities)
    if _maybe_shift_titular(ctx, polity, rng, year, minorities):
        return
    _maybe_revolt(ctx, polity, rng, year, minorities)


def _maybe_decree(ctx, polity, rng, year: int) -> None:
    """Новый правитель может переписать закон о народах."""
    world = ctx.world
    reign = world.current_reign(polity)
    if reign is None or reign.start.year > year:
        return
    # Указ выходит в первые годы правления, и не каждое правление.
    if year - reign.start.year > 12:
        return
    if polity.policy_since >= reign.start.year:
        return
    if not rng.chance(DECREE_CHANCE):
        return

    ruler = world.figures.get(reign.ruler_id)
    faith = world.faiths.get(polity.faith_id)
    alignment = faith.alignment if faith is not None else 0
    # Указ пишет не держава, а человек: жестокий закручивает, добрый
    # отпускает, и вера с духом эпохи лишь подталкивают его руку.
    own = int(getattr(ruler, "alignment", 0) or 0) if ruler is not None else 0
    toward_harsh = rng.chance(0.5 + 0.12 * (-alignment) + 0.11 * (-own)
                              + 0.3 * ctx.dark_tilt)
    old = polity.policy
    new = pol.harsher(old) if toward_harsh else pol.softer(old)
    if new == old:
        return
    polity.policy = new
    polity.policy_since = year
    # Смягчение гасит обиду, ужесточение её подстёгивает.
    for race_id in list(polity.grievance):
        if toward_harsh:
            polity.grievance[race_id] = min(1.0, polity.grievance[race_id] + 0.08)
        else:
            polity.grievance[race_id] = max(0.0, polity.grievance[race_id] - 0.2)

    title, text = texts.decree(rng, polity, ruler, old, new, toward_harsh)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="policy_decree", title=title, text=text,
        importance=3 if pol.is_harsh(new) else 2,
        actors=[ruler.id] if ruler is not None else [],
        subjects=[polity.id], race_id=polity.race_id)


def _bleed(ctx, polity, rng, year: int, period: int, minorities) -> None:
    """Рабство и резня: держава изводит собственных подданных."""
    world = ctx.world
    rate = pol.POLICY_BLEED.get(polity.policy, 0.0) * (period / 10.0)
    if rate <= 0:
        return
    for race_id, souls in minorities:
        cities = [world.settlements[sid] for sid in polity.settlement_ids
                  if sid in world.settlements
                  and world.settlements[sid].status == ACTIVE
                  and world.settlements[sid].race_id == race_id]
        if not cities:
            continue
        dead = 0
        for settlement in cities:
            loss = int(settlement.population * rate * rng.uniform(0.6, 1.5))
            if loss <= 0:
                continue
            settlement.population = max(20, settlement.population - loss)
            dead += int(loss * RURAL_FACTOR)
        if dead < 200 or not rng.chance(0.6):
            continue
        race = races_mod.RACES_BY_ID.get(race_id)
        if race is None:
            continue
        region = world.regions.get(cities[0].region_id)
        title, text = texts.oppression(rng, polity, race, region, dead,
                                       polity.policy)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="oppression", title=title, text=text,
            importance=4 if polity.policy == pol.PURGE else 3,
            subjects=[polity.id], region_id=cities[0].region_id,
            race_id=race_id)
        polity.grievance[race_id] = min(1.0, polity.grievance.get(race_id, 0) + 0.12)


def _assimilate(ctx, polity, rng, year: int, period: int, minorities) -> None:
    """Мирное врастание: город перестаёт числиться чужим."""
    world = ctx.world
    rate = pol.POLICY_ASSIMILATION.get(polity.policy, 0.0) * (period / 10.0)
    if rate <= 0 or not rng.chance(min(0.8, rate)):
        return
    race_id, souls = minorities[-1]        # растворяется прежде всего малый народ
    # Заметный народ не растворяется: у него свои города, свой храм и своя
    # память. Врастают только те, кого и так почти не осталось.
    if polity.share_of(race_id) > 0.15:
        return
    cities = [world.settlements[sid] for sid in polity.settlement_ids
              if sid in world.settlements
              and world.settlements[sid].status == ACTIVE
              and world.settlements[sid].race_id == race_id]
    if not cities:
        return
    settlement = rng.choice(sorted(cities, key=lambda s: s.id))
    settlement.race_id = polity.race_id
    # Город сменил кровь — значит, сменил и народ: прежний ему больше
    # не родня. Берём тот народ титульной расы, что и у столицы.
    settlement.folk_id = ""
    capital = world.settlements.get(polity.capital_id)
    if capital is not None:
        kin = world.folks.get(capital.folk_id)
        if kin is not None and kin.race_id == polity.race_id:
            settlement.folk_id = capital.folk_id
    race = races_mod.RACES_BY_ID.get(race_id)
    if race is None or not rng.chance(ASSIMILATE_CHANCE):
        return
    region = world.regions.get(settlement.region_id)
    title, text = texts.assimilation(rng, polity, race, region)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="assimilation", title=title, text=text, importance=2,
        subjects=[polity.id, settlement.id], region_id=settlement.region_id,
        race_id=race_id)


def _maybe_shift_titular(ctx, polity, rng, year: int, minorities) -> bool:
    """Престол переходит к большинству без крови.

    Если в державе равные права, а титульный народ давно стал меньшинством
    в собственной стране, рано или поздно на престол сядет кто-то из тех,
    кого больше. Ни мятежа, ни резни — просто выборы, брак или завещание.
    """
    world = ctx.world
    if polity.policy != pol.EQUAL:
        return False
    if polity.titular_since and year - polity.titular_since < TITULAR_COOLDOWN:
        return False
    race_id, souls = minorities[0]
    if polity.share_of(race_id) < 0.55 or polity.share_of(polity.race_id) > 0.35:
        return False
    race = races_mod.RACES_BY_ID.get(race_id)
    if race is None or not race.builds_states:
        return False
    if not rng.chance(0.25):
        return False

    running = world.current_reign(polity)
    date = ctx.date_in(rng, year,
                       running.start if running is not None else None)
    capital = world.settlements.get(polity.capital_id)
    region_id = capital.region_id if capital is not None else (
        polity.region_ids[0] if polity.region_ids else "")
    sex = "f" if rng.chance(0.45) else "m"
    heir = ctx.make_figure(
        rng, race, year, role="правитель", region_id=region_id,
        title=ctx.ruler_title(polity, race, sex), sex=sex, epithet_chance=0.6)
    old_race = polity.race_id
    polity.race_id = race.id
    polity.titular_since = year

    reign = world.current_reign(polity)
    if reign is not None and reign.end is None:
        succession.close_reign(ctx, reign, date, "престол перешёл к большинству")
    houses_mod.found_house(ctx, heir, year, date, seat=capital, rank=GREAT,
                           polity=polity, importance=2)
    succession.install_founder(ctx, polity, heir, capital, date, year)

    old = races_mod.RACES_BY_ID.get(old_race)
    title, text = texts.titular_shift(rng, polity, old or race, race, heir)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="titular_shift",
        title=title, text=text, importance=4, actors=[heir.id],
        subjects=[polity.id], region_id=region_id, race_id=race.id)
    world.notes.setdefault("смены титульного народа", []).append(
        "%d: %s -> %s в стране %s" % (year, old.name if old else old_race,
                                      race.name, polity.name))
    return True


def _maybe_revolt(ctx, polity, rng, year: int, minorities) -> None:
    """Накопленная обида поднимает народ."""
    world = ctx.world
    pairs = []
    for race_id, souls in minorities:
        share = polity.share_of(race_id)
        anger = polity.grievance.get(race_id, 0.0)
        if share < pol.REVOLT_SHARE or anger < 0.35:
            continue
        pairs.append(((race_id, share, anger), anger * share * 12.0))
    if not pairs:
        return
    race_id, share, anger = rng.weighted(pairs)
    if not rng.chance(min(0.6, anger * share * REVOLT_RATE)):
        return

    race = races_mod.RACES_BY_ID.get(race_id)
    if race is None:
        return
    cities = [world.settlements[sid] for sid in polity.settlement_ids
              if sid in world.settlements
              and world.settlements[sid].status == ACTIVE
              and world.settlements[sid].race_id == race_id]
    if not cities:
        polity.grievance[race_id] = 0.0
        return

    # Восстание не может случиться раньше, чем началось нынешнее правление:
    # иначе новое правление открывается задом наперёд.
    running = world.current_reign(polity)
    date = ctx.date_in(rng, year,
                       running.start if running is not None else None)
    sex = "f" if rng.chance(0.4) else "m"
    leader = ctx.make_figure(
        rng, race, year, role="вождь восстания", region_id=cities[0].region_id,
        title=ctx.title_for(race, "chief", sex), sex=sex, epithet_chance=0.85)
    leader.home_id = cities[0].id

    # Чем больше народ и злее обида, тем вернее у него получится.
    success = anger * 0.6 + share * 0.9
    fresh = polity.titular_since and year - polity.titular_since < TITULAR_COOLDOWN
    if share >= pol.TAKEOVER_SHARE and race.builds_states \
            and not fresh and rng.chance(0.45):
        outcome = "takeover"
    elif rng.chance(min(0.75, success)) and race.builds_states:
        outcome = "freedom"
    else:
        outcome = "crushed"

    new_polity = None
    if outcome == "freedom":
        new_polity = _break_away(ctx, polity, race, leader, cities, date, year, rng)
        if new_polity is None:
            outcome = "crushed"
    elif outcome == "takeover":
        _take_over(ctx, polity, race, leader, date, year, rng)

    if outcome == "crushed":
        leader.death_cause = "казнён после мятежа"
        world.schedule_death(leader, date, narrative.fate(
            ("казнён после мятежа", "казнена после мятежа"), leader.sex))
        polity.grievance[race_id] = min(1.0, anger + 0.15)
    else:
        polity.grievance[race_id] = 0.0

    region = world.regions.get(cities[0].region_id)
    title, text = texts.revolt(rng, polity, race, leader, region, outcome,
                               new_polity)
    subjects = [polity.id] + ([new_polity.id] if new_polity is not None else [])
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="revolt",
        title=title, text=text,
        importance=5 if outcome == "takeover" else 4,
        actors=[leader.id], subjects=subjects,
        region_id=cities[0].region_id, race_id=race_id)


def _break_away(ctx, polity, race, leader, cities, date, year, rng):
    """Меньшинство уносит свои города и объявляет их вольными."""
    world = ctx.world
    if len(cities) < 1:
        return None
    capital = max(cities, key=lambda s: (s.population, s.id))
    form = rng.choice(race.polity_words or ("Вождество",))
    new_polity = world.add_polity(
        name=ctx.forge.polity(rng, race), form=form, race_id=race.id,
        founded=date, founder_id=leader.id, capital_id=capital.id,
        ruler_id="", region_ids=[], settlement_ids=[],
        predecessor_id=polity.id)
    for settlement in cities:
        if settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)
        settlement.polity_id = new_polity.id
        settlement.is_capital = settlement.id == capital.id
        new_polity.settlement_ids.append(settlement.id)
        if settlement.region_id not in new_polity.region_ids:
            new_polity.region_ids.append(settlement.region_id)
    if not _live_cities(world, polity):
        world.end_polity(polity, date, "распалась под восстанием")
    succession.install_founder(ctx, new_polity, leader, capital, date, year)
    world.refresh_populations()
    return new_polity


def _take_over(ctx, polity, race, leader, date, year, rng) -> None:
    """Меньшинство садится на престол: держава остаётся, народ в ней меняется."""
    world = ctx.world
    old_race = polity.race_id
    polity.race_id = race.id
    polity.titular_since = year
    # Форма державы остаётся, титул правителя меняется под новый народ.
    reign = world.current_reign(polity)
    if reign is not None and reign.end is None:
        succession.close_reign(ctx, reign, date, "свергнут восставшими")
        old_ruler = world.figures.get(reign.ruler_id)
        if old_ruler is not None and old_ruler.alive_at(year):
            world.schedule_death(old_ruler, date, narrative.fate(
                ("убит восставшими", "убита восставшими"), old_ruler.sex))
    capital = world.settlements.get(polity.capital_id)
    houses_mod.found_house(ctx, leader, year, date,
                           seat=capital, rank=GREAT, polity=polity, importance=2)
    succession.install_founder(ctx, polity, leader, capital, date, year)
    world.notes.setdefault("смены титульного народа", []).append(
        "%d: %s -> %s в стране %s" % (year,
                                      races_mod.RACES_BY_ID[old_race].name
                                      if old_race in races_mod.RACES_BY_ID else old_race,
                                      race.name, polity.name))
