# -*- coding: utf-8 -*-
"""Основание поселений, стран и лагерей.

Правила жёсткие и заданы расами:

* цивилизованные народы оседают, строят города и со временем страны;
* зверолюды остаются племенами — никаких городов и государств;
* злые расы ставят лагеря, логова и орды, но страной не становятся никогда.
"""

from __future__ import annotations

from . import houses as houses_mod
from . import peoples
from . import succession
from . import upheaval
from .. import crafts as crafts_mod
from .. import laws as laws_mod
from .. import narrative
from .. import narrative_town as town_texts
from .. import township as town_cat
from .. import races as races_mod
from .. import rulers as rulers_mod
from ..models import ACTIVE, GONE, GREAT, MINOR, RUINED, SETTLED

SETTLE_MIN_POPULATION = 380

# Сколько душ кормит земля на единицу своей ёмкости — не одному своему
# городу, а всем им вместе.
#
# Прежде ёмкость считалась каждому городу отдельно, а соседей он учитывал
# «легко»: делителем стояло число городов земли в степени 0,12. На земле
# с тридцатью городами это 1,46 — каждый получал две трети полного куска,
# и земля кормила вдвадцатеро больше, чем кормит. Отсюда и выходило то,
# что видно в мире: городов много, а больших среди них нет ни одного.
# Каждому хватало, и ни одному не доставалось вдоволь.
#
# Теперь хлеб у земли один, и города его делят. Новый город берёт хлеб у
# соседей, а не добывает свой из ничего, — и потому встаёт не всякий
# год, а только там, где есть чем кормиться.
REGION_BREAD = 63000.0

# Сколько душ держит один город на единицу ёмкости своей земли — до
# поправок на расу, державу и прочее. Прежде это число стояло в движке
# без имени и было в семь раз меньше, но при нём каждый город получал
# почти всю ёмкость земли целиком, и выходило то же самое. Теперь, когда
# хлеб делится, число названо и поднято: городов стало меньше, а людей в
# мире столько же — значит, в каждом городе их больше. В этом и был смысл.
#
# Поднято оно трижды: 7000 без имени, потом 11600, потом 15000 и теперь
# 22000. Последний раз — за людностью мира. У мира по карте аппетит и
# есть то единственное, что держит его города: хлеба своих земель он
# занимает четверть, и прибавка хлеба ему ничего не даёт. У процедурного
# мира наоборот: хлеб занят весь, и аппетит там упирается в делёж. Отсюда
# и выбор этого числа, а не REGION_BREAD: оно поднимает тот мир, который
# отстал, и почти не трогает тот, который и так полон, — а мир по карте
# был вдвое малолюднее процедурного при тех же настройках.
TOWN_APPETITE = 22000.0

# Насколько хлеб достаётся тому, кто уже велик. Ноль — всем поровну, и
# тогда в мире одни середняки. Единица — ровно по людности: кто больше,
# тот и берёт больше, и это то, что видно в настоящей истории. Больше
# своего аппетита город всё равно не возьмёт — съесть больше, чем кормит
# его собственная округа, нельзя, и потому первый город землю не съедает.
#
# Мерено на трёх делениях шкалы по двум миров. На половине пирамида
# поселений стояла на вершине: шесть сёл, четыре городка, двадцать два
# города, шестнадцать больших. На единице она встала как надо: выселок,
# пять сёл, тринадцать городков, двадцать четыре города, восемь больших
# и один великий. Разница в том, что на половине хлеб достаётся середняку
# почти так же, как первому, и середняк дорастает до большого города.
PRIMACY = 1.0

# Сколько хлеба нужно оставить незанятым, чтобы на земле встал ещё один
# город, — в долях людности большого города (`township.RANK_FROM`).
# Порог взят оттуда с умыслом: город ставят там, где он может стать
# большим городом, а не остаться деревней при чужих стенах. Оттого на
# скудной земле стоит один город, а на тучной — десяток: число городов
# идёт по богатству земли, а не поровну всем.
#
# Считать свободное по нынешней людности нельзя — это и была первая
# попытка. В молодом мире города ещё малы, свободного хлеба на земле
# будто бы вдоволь, и новые встают один за другим; а когда они вырастут,
# окажется, что земли на всех не хватило, и останутся на ней не города, а
# деревни при чужих городах. Поэтому занятым считается не то, что города
# съели, а то, что они съедят, когда вырастут.
TOWN_SHARE = 1.0

# Чем больше у расы городов, тем меньше шанс, что следующий город будет её же.
# Без этого один удачливый народ (обычно люди) застраивает весь мир.
CROWDING = 0.12
POLITY_CROWDING = 0.6


def _colony_folk(world, mother, polity, race) -> str:
    """Народ новой колонии: тот же, что у её матери-города или столицы.

    Народ обязан быть своей расы. После завоевания или смены титульного
    народа столица державы может оказаться совсем другой крови — тогда
    колония переселенцев к её народу отношения не имеет.
    """
    def fits(folk_id):
        folk = world.folks.get(folk_id)
        return folk is not None and folk.race_id == race.id

    if mother is not None and fits(getattr(mother, "folk_id", "")):
        return mother.folk_id
    if polity is not None:
        capital = world.settlements.get(polity.capital_id)
        if capital is not None and fits(capital.folk_id):
            return capital.folk_id
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is not None and fits(settlement.folk_id):
                return settlement.folk_id
    # Иначе — самый многочисленный народ этой расы в мире.
    kin = [folk for folk in world.folks.values() if folk.race_id == race.id]
    if kin:
        return max(kin, key=lambda f: (f.population, f.id)).id
    return ""


def _crowding(count: int, factor: float = CROWDING) -> float:
    return 1.0 / (1.0 + count * factor)
# С какой людности один город собирает вокруг себя державу. Порог взят по
# людности большого города (`township.RANK_FROM`): держава рождается или
# вокруг двух соседних городов, или вокруг одного, но такого, которому
# есть что держать, — Венеция и Новгород бывали, город на две тысячи душ
# державой не бывал. Прежде тут стояло 2200: при тогдашних мелких городах
# это была половина заметных, а когда города выросли, тот же порог стал
# означать державу на каждый город — и восемь держав из десяти состояли
# из одного города.
POLITY_MIN_CAPITAL = 12000
CAMP_MIN = 40
CAMP_MAX = 220


def _kind_for(rng, race):
    words = race.settlement_words or ("Город",)
    pairs = [(word, 3.0 if index == 0 else 1.0) for index, word in enumerate(words)]
    return rng.weighted(pairs)


# Ключ роли — для титулов, слово — для летописи.
ROLE_WORDS = {"chief": "вождь племени", "founder": "основатель",
              "ruler": "правитель"}


def _leader_of(ctx, rng, race, year, settlement=None, tribe=None, kind="founder"):
    """Берёт живого вождя/основателя или создаёт нового."""
    world = ctx.world
    existing_id = ""
    if tribe is not None:
        existing_id = tribe.chief_id or tribe.founder_id
    elif settlement is not None:
        existing_id = settlement.founder_id
    figure = world.figures.get(existing_id)
    if figure is not None and figure.alive_at(year):
        return figure, False

    sex = "f" if rng.chance(0.42) else "m"
    title = ctx.title_for(race, kind, sex)
    region_id = (tribe.region_id if tribe is not None
                 else settlement.region_id if settlement is not None else "")
    # Ключ роли («ruler») годится для выбора титула, но в летопись он
    # уходит как есть — и в карточке человека читается «чем был занят:
    # ruler». Поэтому роль записывается словом.
    figure = ctx.make_figure(rng, race, year, role=ROLE_WORDS.get(kind, kind),
                             region_id=region_id, title=title, sex=sex)
    return figure, True


def _join_town(ctx, rng, tribe, year: int) -> None:
    """Племя приходит в готовый город, потому что своей земли уже нет.

    Это и есть то, из чего растут большие города. Прежде племя в такой
    год ставило рядом ещё одно поселение — и в мире копились деревни,
    которым негде было вырасти. Теперь люди идут туда, где город уже
    стоит, и город становится больше: доля хлеба земли считается по
    людности, так что пришедшие не просто прибавляются числом, а
    перетягивают хлеб у соседей.

    Город выбирается в своей земле и своей крови: племя не растворяется в
    чужом народе за один год. Если такого города нет — племя кочует
    дальше, и это честный исход, а не недоработка.
    """
    world = ctx.world
    here = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id != tribe.region_id:
            continue
        if settlement.race_id != tribe.race_id:
            continue
        # Свой народ впереди соседней крови той же расы.
        same_folk = 0 if settlement.folk_id == tribe.folk_id else 1
        here.append((same_folk, -settlement.population,
                     len(settlement.id), settlement.id))
    if not here:
        return
    here.sort()
    settlement = world.settlements[here[0][3]]
    came = max(1, int(tribe.population * 0.92))
    settlement.population += came
    settlement.notes.append("%d: сюда пришло племя по имени %s — %d душ"
                            % (year, tribe.name, came))
    date = ctx.date_in(rng, year)
    world.end_tribe(tribe, date,
                    "влилось в город по имени %s" % settlement.name, SETTLED)
    tribe.settlement_id = settlement.id
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="tribe_joined",
        title="Племя влилось в город: %s" % settlement.name,
        text=town_texts.joined_text(rng, tribe.name, settlement.name, came),
        importance=2, subjects=[settlement.id, tribe.id],
        region_id=settlement.region_id, race_id=tribe.race_id,
    )


# ---------------------------------------------------------------------------
# Племя оседает и строит поселение
# ---------------------------------------------------------------------------

def tick_settling(ctx, year: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    if not spec.allow_settlements:
        return
    rng = ctx.rng("settling", year)
    if not rng.chance(ctx.spread_rate(spec.settle_rate)):
        return

    settled_by_race = {}
    for settlement_id in world.active_settlements:
        race_id = world.settlements[settlement_id].race_id
        settled_by_race[race_id] = settled_by_race.get(race_id, 0) + 1

    # Хлеб земель: на занятой земле новый город не встаёт. Прежде он
    # встал бы — и стал бы тринадцатой деревней там, где кормиться уже
    # нечем.
    free = _room_for_towns(ctx, year)

    roomy, crowded = [], []
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        race = races_mod.get_race(tribe.race_id)
        if not race.settles or tribe.population < SETTLE_MIN_POPULATION:
            continue
        weight = float(tribe.population) * _crowding(settled_by_race.get(race.id, 0))
        where = world.regions.get(tribe.region_id)
        (roomy if _has_room(free, where)
         else crowded).append((tribe, weight))
    if not roomy and not crowded:
        return

    if not roomy:
        # Свободной земли нет нигде. Тогда племя не строит своего, а идёт
        # в готовый город — и город от этого растёт. Из таких приходов
        # большие города и складываются.
        _join_town(ctx, rng, rng.weighted(crowded), year)
        return

    tribe = rng.weighted(roomy)
    race = races_mod.get_race(tribe.race_id)
    region = world.regions.get(tribe.region_id)
    if region is None:
        return

    leader, _ = _leader_of(ctx, rng, race, year, tribe=tribe, kind="founder")
    date = ctx.date_in(rng, year)
    hex_index = tribe.hex_index if tribe.hex_index >= 0 else -1
    if ctx.map is not None and hex_index < 0:
        hex_index = ctx.map.place(region.id, rng, kind="city")

    speech = ctx.tongue_of(tribe.folk_id)
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race, speech), kind=_kind_for(rng, race),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=region.id, population=max(120, int(tribe.population * 0.92)),
        hex_index=hex_index, folk_id=tribe.folk_id,
        origin_tribe_id=tribe.id,
    )
    if ctx.map is not None and hex_index >= 0:
        ctx.map.claim(hex_index, settlement.id)
    leader.roles.append("основатель поселения")
    leader.home_id = settlement.id

    world.end_tribe(tribe, date, "осело и построило %s" % settlement.name, SETTLED)
    tribe.settlement_id = settlement.id

    title, text = narrative.settlement_found(rng, settlement, leader, region,
                                             race, tribe=tribe)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="settlement_found",
        title=title, text=text, importance=3, actors=[leader.id],
        subjects=[settlement.id, tribe.id], region_id=region.id, race_id=race.id,
    )
    # Основатель города кладёт начало знатному роду — так рождается знать.
    houses_mod.found_house(ctx, leader, year, date, seat=settlement, rank=MINOR)

    # Не все согласны жить за стенами: часть племени уходит кочевать дальше.
    if rng.chance(0.38) and settlement.population > 500:
        leaving = int(settlement.population * rng.uniform(0.12, 0.25))
        settlement.population -= leaving
        spot = ctx.pick_region(rng, race, near=region.id, spread=0.4) or region
        peoples.found_tribe(ctx, race, spot, year, rng, parent=tribe,
                            population=leaving, after=date)


# ---------------------------------------------------------------------------
# Страна расширяется новым городом
# ---------------------------------------------------------------------------

def tick_colonies(ctx, year: int) -> None:
    """Расселение: страны и крупные вольные города ставят новые поселения."""
    world = ctx.world
    spec = ctx.era_spec(year)
    if not spec.allow_settlements:
        return
    rng = ctx.rng("colonies", year)
    if not rng.chance(ctx.spread_rate(spec.colony_rate)):
        return

    settled_by_race = {}
    for settlement_id in world.active_settlements:
        race_id = world.settlements[settlement_id].race_id
        settled_by_race[race_id] = settled_by_race.get(race_id, 0) + 1

    candidates = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        race = races_mod.get_race(polity.race_id)
        weight = ((1.0 + len(polity.settlement_ids)) * race.expansion
                  * _crowding(settled_by_race.get(race.id, 0)))
        candidates.append((("polity", polity), weight))
    for settlement_id in world.active_settlements:
        mother = world.settlements[settlement_id]
        if mother.polity_id or mother.population < 900:
            continue
        race = races_mod.get_race(mother.race_id)
        candidates.append((("free", mother), 0.7 * race.expansion
                           * _crowding(settled_by_race.get(race.id, 0))))
    if not candidates:
        return

    kind, source = rng.weighted(candidates)
    if kind == "polity":
        polity = source
        race = races_mod.get_race(polity.race_id)
        home_id = rng.choice(polity.region_ids) if polity.region_ids else ""
    else:
        polity = None
        race = races_mod.get_race(source.race_id)
        home_id = source.region_id
    # Колонию ставят туда, где есть чем кормиться. Три попытки, а не
    # одна: земля выбирается с оглядкой на родную, и первая подвернувшаяся
    # бывает уже занята. Если места нет и на третий раз — не ставят вовсе,
    # и держава растёт теми городами, какие у неё есть. Так и бывало:
    # расселение кончается не указом, а тем, что селиться стало некуда.
    free = _room_for_towns(ctx, year)
    region = None
    for _ in range(3):
        spot = ctx.pick_region(rng, race, near=home_id, spread=0.25)
        if spot is None:
            break
        if _has_room(free, spot):
            region = spot
            break
    if region is None:
        return

    sex = "f" if rng.chance(0.42) else "m"
    leader = ctx.make_figure(rng, race, year, role="основатель",
                             region_id=region.id,
                             title=ctx.title_for(race, "founder", sex), sex=sex)
    date = ctx.date_in(rng, year)
    colony_hex = ctx.map.place(region.id, rng, kind="city") if ctx.map else -1
    colony_folk = _colony_folk(world, source if kind == "free" else None,
                               polity, race)
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race, ctx.tongue_of(colony_folk)),
        kind=_kind_for(rng, race),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=region.id, population=rng.randint(150, 600),
        polity_id=polity.id if polity else "", hex_index=colony_hex,
        folk_id=colony_folk,
    )
    if ctx.map is not None and colony_hex >= 0:
        ctx.map.claim(colony_hex, settlement.id)
    leader.roles.append("основатель поселения")
    leader.home_id = settlement.id
    subjects = [settlement.id]
    if polity is not None:
        world.hold_settlement(polity, settlement.id)
        if region.id not in polity.region_ids:
            polity.region_ids.append(region.id)
        subjects.append(polity.id)

    title, text = narrative.settlement_found(rng, settlement, leader, region,
                                             race, polity=polity)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="colony_found",
        title=title, text=text, importance=3, actors=[leader.id],
        subjects=subjects, region_id=region.id, race_id=race.id,
    )
    houses_mod.found_house(ctx, leader, year, date, seat=settlement, rank=MINOR,
                           polity=polity)


# ---------------------------------------------------------------------------
# Рождение страны
# ---------------------------------------------------------------------------

def tick_polities(ctx, year: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    if not spec.allow_polities:
        return
    rng = ctx.rng("polities", year)
    if not rng.chance(ctx.spread_rate(spec.polity_rate)):
        return

    by_race = {}
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.polity_id:
            continue
        race = races_mod.get_race(settlement.race_id)
        if not race.builds_states:
            continue
        by_race.setdefault(race.id, []).append(settlement)

    polities_by_race = {}
    for polity_id in world.active_polities:
        race_id = world.polities[polity_id].race_id
        polities_by_race[race_id] = polities_by_race.get(race_id, 0) + 1

    candidates = []
    for race_id, items in sorted(by_race.items()):
        best = max(item.population for item in items)
        if len(items) >= 2 or best >= POLITY_MIN_CAPITAL:
            weight = (float(len(items)) * 2.0 + best / 1000.0) * _crowding(
                polities_by_race.get(race_id, 0), POLITY_CROWDING)
            candidates.append((race_id, weight))
    if not candidates:
        return

    race = races_mod.get_race(rng.weighted(candidates))
    free = sorted(by_race[race.id], key=lambda s: (-s.population, s.id))
    capital = free[0]
    region = world.regions.get(capital.region_id)

    members = [capital]
    nearby = set(region.neighbors) | {region.id} if region else {capital.region_id}
    limit = rng.randint(1, 4)
    for settlement in free[1:]:
        if len(members) - 1 >= limit:
            break
        if settlement.region_id in nearby or rng.chance(0.2):
            members.append(settlement)

    leader, is_new = _leader_of(ctx, rng, race, year, settlement=capital, kind="ruler")
    sex = leader.sex
    # Форму выбираем до титула: империей правит император, а не король.
    form = rng.choice(race.polity_words or ("Королевство",))
    ruler_title = races_mod.title_for_form(form, sex, race.ruler_titles)
    if ruler_title not in leader.titles:
        leader.titles.insert(0, ruler_title)
    leader.roles.append("основатель страны")

    date = ctx.date_in(rng, year)
    polity = world.add_polity(
        name=ctx.forge.polity(rng, race, ctx.tongue_of(capital.folk_id)),
        form=form,
        race_id=race.id, founded=date, founder_id=leader.id,
        capital_id=capital.id, ruler_id=leader.id,
        region_ids=[], settlement_ids=[],
    )
    for settlement in members:
        settlement.polity_id = polity.id
        world.hold_settlement(polity, settlement.id)
        if settlement.region_id not in polity.region_ids:
            polity.region_ids.append(settlement.region_id)
    capital.is_capital = True
    leader.home_id = capital.id

    title, text = narrative.polity_found(rng, polity, leader, capital, race, members)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="polity_found",
        title=title, text=text, importance=4, actors=[leader.id],
        subjects=[polity.id, capital.id], region_id=capital.region_id,
        race_id=race.id,
    )

    # Роды основателей вошедших городов становятся знатью новой страны.
    for settlement in members:
        house = world.houses.get(
            world.figures[settlement.founder_id].house_id
            if settlement.founder_id in world.figures else "")
        if house is not None and house.status == ACTIVE:
            house.rank = GREAT if settlement.id == capital.id else house.rank
            houses_mod.attach(world, house, polity)
    succession.install_founder(ctx, polity, leader, capital, date, year)


# ---------------------------------------------------------------------------
# Лагеря злых рас
# ---------------------------------------------------------------------------

def tick_camps(ctx, year: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    rng = ctx.rng("camps", year)
    if not rng.chance(ctx.spread_rate(spec.camp_rate)):
        return

    evil = [race for race in ctx.awakened
            if race.is_evil and not upheaval.is_gone(world, race.id)]
    if not evil:
        return
    race = rng.weighted([(race, race.expansion) for race in evil])
    region = ctx.pick_region(rng, race)
    if region is None:
        return

    sex = "f" if rng.chance(0.3) else "m"
    leader = ctx.make_figure(rng, race, year, role="вожак", region_id=region.id,
                             title=ctx.title_for(race, "chief", sex), sex=sex,
                             epithet_chance=0.75)
    date = ctx.date_in(rng, year)
    camp_hex = ctx.map.place(region.id, rng, kind="camp") if ctx.map else -1
    camp = world.add_camp(
        name=ctx.forge.camp(rng, race), word=rng.choice(race.camp_words or ("Лагерь",)),
        race_id=race.id, founded=date, founder_id=leader.id,
        region_id=region.id, population=rng.randint(CAMP_MIN, CAMP_MAX),
        hex_index=camp_hex,
    )
    if ctx.map is not None and camp_hex >= 0:
        ctx.map.claim(camp_hex, camp.id, kind="camp")
    leader.home_id = camp.id
    leader.roles.append("основатель лагеря")

    title, text = narrative.camp_found(rng, camp, leader, region, race)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="camp_found",
        title=title, text=text, importance=1, actors=[leader.id],
        subjects=[camp.id], region_id=region.id, race_id=race.id,
    )


# ---------------------------------------------------------------------------
# Рост и упадок поселений, стран и лагерей
# ---------------------------------------------------------------------------

def _tributaries(world) -> dict:
    """Сколько данников у каждой державы — считается раз за такт."""
    counts = {}
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        lord = polity.tribute_to or polity.overlord_id
        if lord:
            counts[lord] = counts.get(lord, 0) + 1
    return counts

def _region_bread(ctx, era_index: int, bounty: float) -> dict:
    """Сколько душ кормит каждая земля во всех своих городах вместе.

    Считается раз за такт: земель десятки, а городов сотни, и спрашивать
    землю о её хлебе на каждый город незачем.
    """
    world = ctx.world
    out = {}
    for region in world.regions.values():
        bread = REGION_BREAD * max(0.0, region.capacity) * bounty
        bread *= 0.75 + 0.14 * era_index
        if ctx.map is not None and region.from_map:
            bread *= 0.85 + 0.5 * ctx.map.bounty(region.id)
        out[region.id] = bread
    return out


def _taken_bread(world) -> dict:
    """Сколько хлеба земли уже съедено её городами."""
    out = {}
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        out[settlement.region_id] = (out.get(settlement.region_id, 0.0)
                                     + settlement.population)
    return out


def _town_needs() -> float:
    """Сколько свободного хлеба нужно под новый город.

    Не доля земли, а людность большого города: ставить город там, где он
    обречён остаться деревней, незачем. Отсюда само собой выходит, что
    городов на скудной земле один-два, а на тучной — десяток.
    """
    return TOWN_SHARE * town_cat.rank_edge(town_cat.BIG_TOWN)


def _room_for_towns(ctx, year: int) -> dict:
    """Сколько хлеба свободно на каждой земле: (земля -> душ).

    Один вызов на такт основания: земель десятки, городов сотни, и
    спрашивать землю о хлебе на каждый город незачем.
    """
    world = ctx.world
    era_index = world.era_index_at(year)
    bounty = ctx.fate_bounty(year)
    bread = _region_bread(ctx, era_index, bounty)
    tributaries = _tributaries(world)
    free = dict(bread)
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        region = world.regions.get(settlement.region_id)
        want = _appetite(ctx, settlement,
                         races_mod.get_race(settlement.race_id), region,
                         era_index, bounty, tributaries)
        free[settlement.region_id] = (free.get(settlement.region_id, 0.0)
                                      - want)
    return free


def _has_room(free, region) -> bool:
    """Хватит ли на этой земле хлеба ещё на один город.

    Город — это не двести душ: ему нужна своя округа и свой кормилец.
    Поэтому спрашивается не «осталась ли крошка», а «хватит ли на город,
    из которого может вырасти большой».
    """
    if region is None:
        return False
    return free.get(region.id, 0.0) >= _town_needs()


# Насколько заметно поселению шагнуть по ступени, чтобы летопись об этом
# написала. Каждое село, дорастающее до городка, событием быть не должно —
# таких за историю тысячи; а вот город, ставший великим, или большой город,
# осевший в село, — событие.
RANK_NEWS_FROM = 3          # с этой ступени и выше о переменах пишут

# Насколько надо перешагнуть порог, чтобы ступень сменилась.
RANK_MARGIN = 0.08


def _restep(ctx, settlement, race, year: int, era_index: int, rng) -> None:
    """Пересчитать ступень поселения и, если надо, переименовать его.

    Две беды разом. Первая: вид поселения ставился при основании и не менялся
    никогда, поэтому в мире заводилась «Застава» на сто двадцать тысяч душ.
    Вторая: словом «город» звалось и поселение на триста душ — а если городом
    зовётся всё, то города в мире нет ни одного.

    Теперь ступень считается из людности каждое десятилетие и живёт своей
    жизнью: поселение растёт по ступеням и оседает обратно. А то, что
    доросло до города, но названо заставой или рудником, своё прежнее имя
    теряет: застава — это застава, а не город на сорок тысяч душ. Имя при
    этом не выдумывается заново, меняется только слово перед ним, и прежнее
    остаётся в памяти поселения.
    """
    world = ctx.world
    was = settlement.rank
    souls = settlement.population
    now = town_cat.rank_of(souls)
    step_up = town_cat.rank_index(now) > town_cat.rank_index(was)
    if now != was:
        # Гистерезис. Без него поселение, стоящее у самого порога, каждые
        # десять лет прыгает туда и обратно: «Рунная Жила — город», через
        # двадцать лет «уже городок», через десять снова город. Летопись от
        # этого превращается в перепись скота, поэтому ступень меняется
        # только тогда, когда порог перешагнут заметно.
        edge = town_cat.rank_edge(now if step_up else was)
        if edge and abs(souls - edge) < edge * RANK_MARGIN:
            now = was
            step_up = False
        else:
            settlement.rank = now
    # Проверка имени идёт дальше даже тогда, когда ступень не менялась, и
    # это не лишняя работа. Поселение бывает основано уже крупным — племя
    # садится на землю всем числом, — и тогда ступень у него городская с
    # первого дня и не меняется ни разу. Такая «Застава» на сорок тысяч
    # душ прежде оставалась заставой навсегда: самопроверка её и нашла.
    outgrown = (town_cat.is_city(settlement.rank)
                and settlement.kind in town_cat.OUTGROWN)
    if now == was and not outgrown:
        return
    top = max(town_cat.rank_index(now), town_cat.rank_index(was))
    # Как называть это место в записи. Если вид поселения — общее слово
    # «Город», называть его видом нельзя: выйдет «город такой-то стал
    # городом». Тогда говорим оборотом.
    if settlement.kind in ("Город", "Городище"):
        place = "поселение по имени %s" % settlement.name
    else:
        place = "%s %s" % (settlement.kind.lower(), settlement.name)

    # Переросло своё имя: то, что ставили заставой, городом зваться заставой
    # уже не может.
    renamed = ""
    if outgrown:
        words = race.settlement_words or ("Город",)
        renamed = settlement.kind
        settlement.kind = words[0]
        settlement.notes.append(
            "%d: перестало быть %s — выросло в %s"
            % (year, renamed.lower(), settlement.kind.lower()))

    if top < RANK_NEWS_FROM and not renamed:
        return          # выселок, ставший селом, — не новость для летописи
    date = ctx.date_in(rng, year)
    if renamed:
        title = "Переросло своё имя: %s" % settlement.name
        text = town_texts.renamed_text(rng, settlement.name, renamed,
                                       settlement.kind, souls)
    elif step_up:
        title = "%s: %s" % (now.capitalize(), settlement.name)
        text = town_texts.grew_text(rng, place, settlement.name, was,
                                    now, souls)
    else:
        title = "Измельчало: %s" % settlement.name
        text = town_texts.shrank_text(rng, place, settlement.name,
                                      was, now, souls)
    world.add_event(
        date=date, era_index=era_index,
        kind="settlement_rank" if not renamed else "settlement_renamed",
        title=title, text=text,
        importance=2 if top >= len(town_cat.RANKS) - 1 else 1,
        subjects=[settlement.id], region_id=settlement.region_id,
        race_id=settlement.race_id,
    )


def _appetite(ctx, settlement, race, region, era_index: int, bounty: float,
              tributaries: dict) -> float:
    """Сколько душ удержал бы этот город, стоя на своей земле один.

    Это его собственный предел: своя округа, свой уклад, своё ремесло и
    своя власть. Хлеба земли тут нет вовсе — он делится дальше, и ни один
    город не берёт больше своего аппетита.
    """
    world = ctx.world
    capacity = max(1.0, TOWN_APPETITE * (region.capacity if region else 1.0))
    # Земля кормит одинаково, а живут на ней по-разному: дворфский город
    # уходит вниз ярусами и держит вдвое больше людского при той же
    # округе, эльфийский стоит редким и малым.
    capacity *= race.density
    capacity *= bounty
    if ctx.map is not None and region is not None and region.from_map:
        # Урожайные годы и рыбный ход кормят больше ртов, чем голая земля.
        capacity *= 0.85 + 0.5 * ctx.map.bounty(region.id)
    polity = world.polities.get(settlement.polity_id)
    if polity is not None and polity.hunger:
        # Города державы, которой нечем кормить, просто не растут: это
        # честнее постоянного мора и куда точнее по сути.
        capacity *= max(0.35, 1.0 - polity.hunger * 0.8)
    if settlement.is_capital:
        capacity *= 2.1
    elif settlement.polity_id:
        capacity *= 1.35
    capacity *= 0.75 + 0.14 * era_index
    if polity is not None:
        # Плуг, трёхполье и акведук кормят больше народу, чем указ.
        capacity *= crafts_mod.bonus(polity.known, "growth")
        # Но и указ кое-что значит: отпущенные рабы пашут лучше рабов.
        capacity *= laws_mod.bonus(polity.reforms, "growth")
        # Хозяйская хватка государя кормит города или не кормит их:
        # отсюда и берутся «при нём страна поднялась» и наоборот.
        capacity *= rulers_mod.stewardship(world, polity)
        # Дань уходит хлебом и людьми: данник растёт хуже, сюзерен —
        # лучше. Без этого дань была бы строкой в договоре и только.
        if polity.tribute_to:
            capacity *= 0.90
        capacity *= 1.0 + 0.03 * min(4, tributaries.get(polity.id, 0))
    return max(1.0, capacity)


def _share_bread(world, appetite: dict, bread: dict) -> dict:
    """Уложить аппетиты городов одной земли в её хлеб — по старшинству.

    Поровну делить нельзя: тогда в мире одни середняки, ни одного
    крупного города. По людности как есть — тоже нельзя: первый город
    съест землю целиком. Поэтому доля считается по аппетиту, помноженному
    на людность в степени `PRIMACY`, — большой город тянет к себе
    сильнее, но не бесконечно.

    Больше своего аппетита город не получает: хлеб чужой округи до него
    всё равно не доедет.
    """
    pull = {}
    total = {}
    for settlement_id, want in appetite.items():
        settlement = world.settlements[settlement_id]
        value = want * (max(1, settlement.population) ** PRIMACY)
        pull[settlement_id] = value
        total[settlement.region_id] = (total.get(settlement.region_id, 0.0)
                                       + value)
    out = {}
    for settlement_id, want in appetite.items():
        settlement = world.settlements[settlement_id]
        whole = total.get(settlement.region_id, 0.0)
        loaf = bread.get(settlement.region_id, 0.0)
        if whole <= 0 or loaf <= 0:
            out[settlement_id] = max(1.0, min(want, loaf))
            continue
        out[settlement_id] = max(1.0, min(want,
                                          loaf * pull[settlement_id] / whole))
    return out


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    spec = ctx.era_spec(year)
    rng = ctx.rng("settlement_upkeep", year)
    era_index = world.era_index_at(year)
    tributaries = _tributaries(world)
    # Судьба мира: во сколько раз земля кормит в этом году. У одного мира
    # она идёт ровно вверх, у другого поднимает великую державу в первые
    # века и потом тысячу лет опускает. Города сами мельчают и пустеют —
    # подделывать упадок не нужно.
    bounty = ctx.fate_bounty(year)

    # Два прохода, а не один. Сперва у каждого города спрашивается, сколько
    # он удержал бы, стоя на своей земле один; потом аппетиты всех городов
    # одной земли укладываются в её хлеб. Прежде этого второго прохода не
    # было, и земля с тридцатью городами кормила вдвадцатеро больше, чем
    # кормит: каждый считал её ёмкость почти целиком своей.
    order = list(world.active_settlements)
    appetite = {}
    for settlement_id in order:
        settlement = world.settlements[settlement_id]
        appetite[settlement_id] = _appetite(
            ctx, settlement, races_mod.get_race(settlement.race_id),
            world.regions.get(settlement.region_id), era_index, bounty,
            tributaries)
    shared = _share_bread(world, appetite, _region_bread(ctx, era_index,
                                                         bounty))

    for settlement_id in order:
        settlement = world.settlements[settlement_id]
        race = races_mod.get_race(settlement.race_id)
        capacity = shared[settlement_id]

        population = settlement.population
        population += (population * ctx.growth(race.growth, settlement.region_id)
                       * period * (1.0 - population / capacity))
        population *= rng.uniform(0.99, 1.015)
        settlement.population = max(0, int(population))
        # Кривая людности: по ней потом видно рост, расцвет и убыль.
        world.note_census(settlement, year)
        # И ступень: выселок это, село или великий город. Вид поселения
        # ставится при основании и говорит, что это такое; ступень говорит,
        # насколько велико, и меняется всю его жизнь.
        _restep(ctx, settlement, race, year, era_index, rng)

        if settlement.population < 60 or rng.chance(0.00009 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            world.end_settlement(settlement, date, "запустение", RUINED)
            world.add_event(
                date=date, era_index=era_index, kind="settlement_ruined",
                title="Запустение: %s" % settlement.name,
                text=narrative.ruin_text(rng, narrative.cap(settlement.full_name)),
                importance=2, subjects=[settlement.id],
                region_id=settlement.region_id, race_id=settlement.race_id,
            )

    for camp_id in list(world.active_camps):
        camp = world.camps[camp_id]
        race = races_mod.get_race(camp.race_id)
        population = camp.population * (
            1.0 + ctx.growth(race.growth, camp.region_id) * period
            * rng.uniform(-0.6, 1.0))
        camp.population = max(0, int(population))
        if camp.population < 20 or rng.chance(0.0022 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            world.end_camp(camp, date, "разорён", GONE)
            world.add_event(
                date=date, era_index=era_index, kind="camp_end",
                title="Конец лагеря: %s" % camp.name,
                text=narrative.camp_end_text(rng, camp), importance=1,
                subjects=[camp.id], region_id=camp.region_id, race_id=camp.race_id,
            )

    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        alive = [sid for sid in polity.settlement_ids
                 if world.settlements[sid].status == ACTIVE]
        polity.settlement_ids = alive
        if not alive or rng.chance(0.00018 * spec.turmoil * period * ctx.growth_scale):
            date = ctx.date_in(rng, year)
            reason = "распад" if alive else "не осталось ни одного города"
            world.end_polity(polity, date, reason)
            world.add_event(
                date=date, era_index=era_index, kind="polity_fall",
                title="Падение: %s" % polity.name,
                text=narrative.polity_fall_text(rng, polity), importance=3,
                subjects=[polity.id], race_id=polity.race_id,
            )
