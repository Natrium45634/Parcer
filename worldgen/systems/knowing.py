# -*- coding: utf-8 -*-
"""Познание мира: как меняется знание о нём, а не сам мир.

Остров стоит, где стоит, за три тысячи лет до первого чужого корабля.
Эта система не ставит островов — она двигает **знание**: кто о чём
узнал, от кого, насколько верно и что из этого вышло.

Что она делает раз в десять лет.

**Заводит местное знание.** Народ, проснувшийся в своей земле, знает
её подробно — воду, сезоны, запреты, что было тут прежде — и знает это
безо всяких походов. Это первое, что делается в такте, и оттого
«неизвестная земля» в этом генераторе всегда чья-то неизвестная: та же
земля в тот же год хорошо известна живущим и неведома державе за
морем.

**Снаряжает поход — но только когда есть повод.** Поход не берётся из
воздуха: в руки попала карта трёхвековой давности, не вернулся обоз,
кончилась жила, храм вспомнил предание о земле за морем, сосед привёз
оттуда товар и молчит о дороге. Нет повода — похода не будет вовсе, и
это условие, а не недоработка: без него модуль выродился бы в череду
сообщений «в таком-то году открыли гору».

**Разводит поход и его исход.** Исход зависит от состава отряда,
снаряжения, трудности задачи и того, что встретилось по дороге, — а не
от одного броска. И удачей считается не только новое: подтвердить, что
в той долине ничего нет, уточнить берег, найти ошибку в старой карте,
найти стоянку прежнего похода — это тоже работа, и чаще всего поход
приносит именно её.

**Различает находку и понимание.** Войти в руины и понять, чем они
были, — два разных дела с разницей в век. Поэтому у находки бывает
ошибочное толкование с названным годом исправления.

**Разводит три первенства.** Кто дошёл на самом деле, чья запись
уцелела раньше всех и кого принято считать первым — три разных
ответа, и расходятся они постоянно: по-настоящему первым обычно был
тот, кто там жил, а признание получает тот, чьи бумаги сохранились.

**Разносит сведения не мгновенно и не всем.** Весть идёт по каналу —
обозом, кораблём, посольством, с переселенцами, — и по дороге
усыхает: о людях рассказывают как о чудовищах, подробности о дороге
теряются, весть получает божье толкование. Позднейший поход это
исправляет или не исправляет.

**Теряет знание и даёт открыть его заново.** Сгорело книгохранилище,
распалась держава, закрылся путь — и ответ, который был, снова стал
вопросом. Через три века туда идут опять, не зная о прежних.

**Отделяет освоение от обнаружения.** Нанесённая на карту земля не
становится чьей-то. На ней бывает сезонная охота, пастбище, кладбище
старше любого города, хозяин, которому не нужны подданные, — и
попытка освоения идёт отдельной записью со своими условиями и своим
правом провалиться.

Чего система нарочно **не** делает: не ищет землю за морем (это делает
`systems/exploration.py`, и её походы тут только дополняются знанием),
не заводит отдельной географии, не превращает каждый гекс в задание и
не делает из каждого исследователя легенду.
"""

from __future__ import annotations

from .. import knowing as cat
from .. import landlore
from .. import narrative_knowing as texts
from .. import races as races_mod
from ..models import ACTIVE


# За сколько лет назад система ищет повод для похода. Век — слишком
# много: человек снаряжает корабли не из-за того, что случилось при его
# прадеде, а из-за того, что случилось при нём.
LOOK_BACK = 70

# Походов за такт. Число малое нарочно: за десять тысяч лет это две-три
# сотни походов, то есть один на три-четыре десятилетия на весь мир, и
# почти каждый из них — обычная работа без великих открытий.
PROBE_CHANCE = 0.30
PROBE_IN_FLIGHT = 5           # сколько походов бывает в пути разом
PROBE_PER_SIDE = 7            # сколько походов за историю на одно общество

# Сколько записей о знании держится в мире. Это не предел знания, а
# предел счёта: записи заводятся на то, о чём кто-то думал, а не на
# каждую пару «общество — гекс».
KNOWING_CAP = 2600

# Сведения расходятся медленно: за такт переходит от силы одна весть,
# и то не всегда. Иначе всякое открытие к концу века знает весь мир, и
# мир перестаёт быть большим.
SPREAD_CHANCE = 0.55
SPREAD_PER_TICK = 2
WARP_CHANCE = 0.40            # что весть по дороге исказится

# Знание пропадает редко, но пропадает — и это главный источник
# повторных открытий.
FORGET_CHANCE = 0.22
FORGET_AGE = 200              # раньше этого знание ещё живо в людях

# Встречи вне походов: переселенцы, обоз, пастухи за хребтом.
MEET_CHANCE = 0.14

# Карты: составляются при походах, а тут с ними происходит жизнь —
# списки, исправления, ветхость, пожары.
CHART_TURN_CHANCE = 0.30

# Споры о первенстве и присвоение заслуг.
CREDIT_CHANCE = 0.22

# Исследовательский облик заводится только главам походов, и то не всем:
# иначе карточки распухают, а «исследователь» перестаёт что-либо значить.
EXPLORER_CHANCE = 0.75

# Освоение: попытка заводится не после всякой удачи.
HOLD_CHANCE = 0.45

# Какой узел для были старше этого возраста уже не тревожат.
STORY_AGE = 40

# Насколько охотно мир спрашивает о предмете того или иного рода. Это не
# важность предмета, а поправка на его количество: земель в мире десятки,
# а мест истории сотни.
KIND_URGE = {
    cat.T_REGION: 2.4, cat.T_ROUTE: 1.3, cat.T_FOLK: 1.2, cat.T_SITE: 0.8,
    cat.T_DOMINION: 0.9, cat.T_WONDER: 0.8, cat.T_SPECIES: 0.8,
    cat.T_SCAR: 0.6, cat.T_TOWN: 0.7, cat.T_EDGE: 0.4,
}


# ---------------------------------------------------------------------------
# Кто знает: общества, у которых бывает знание и бывают походы
# ---------------------------------------------------------------------------


class Side:
    """Общество как хранитель знания: держава или народ.

    Третьей сущности «культура» тут нет по той же причине, что в
    обычаях: носитель культуры в этом генераторе — народ. Держава
    стоит рядом с народом, а не над ним: у неё свои карты, свои
    грамоты и своя заинтересованность, и знает она часто меньше, чем
    живущие в её же землях.
    """

    __slots__ = ("kind", "id", "name", "folk_id", "race_id", "regions",
                 "can", "souls", "home")

    def __init__(self, kind, key, name, folk_id, race_id, regions, can,
                 souls, home):
        self.kind = kind
        self.id = key
        self.name = name
        self.folk_id = folk_id
        self.race_id = race_id
        self.regions = regions
        self.can = can
        self.souls = souls
        self.home = home

    def __repr__(self) -> str:        # для отладки, в летопись не идёт
        return "Side(%s %s)" % (self.kind, self.id)


def _lands(world) -> dict:
    """Какие земли под каким народом — одним проходом на весь такт."""
    rows = {}
    for settlement_id in world.active_settlements:
        item = world.settlements[settlement_id]
        if item.folk_id:
            rows.setdefault(item.folk_id, set()).add(item.region_id)
    for tribe_id in world.active_tribes:
        item = world.tribes[tribe_id]
        if item.folk_id:
            rows.setdefault(item.folk_id, set()).add(item.region_id)
    return rows


def _sides(world, year: int, lands: dict) -> list:
    """Все общества мира, какие на этот год есть."""
    out = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        regions = set(polity.region_ids)
        can = set()
        if polity.population >= 20000:
            can.add("money")
        if polity.population >= 6000:
            can.add("arms")
        tongue = world.tongues.get(polity.tongue_id)
        if tongue is not None and getattr(tongue, "script", ""):
            can.add("letters")
        if polity.routes:
            can.add("trade")
        capital = world.settlements.get(polity.capital_id)
        folk_id = capital.folk_id if capital is not None else ""
        for settlement_id in polity.settlement_ids:
            town = world.settlements.get(settlement_id)
            if town is None or town.status != ACTIVE:
                continue
            region = world.regions.get(town.region_id)
            if region is not None and (region.coastal or region.island):
                can.add("ships")
                break
        if world.guilds_of(polity):
            can.add("tools")
        out.append(Side("polity", polity.id, polity.full_name, folk_id,
                        polity.race_id, regions, can, polity.population,
                        capital.region_id if capital is not None else ""))
    for folk in world.folks.values():
        if folk.status != ACTIVE:
            continue
        regions = set(lands.get(folk.id, ())) or {folk.cradle_region}
        can = {"people", "guide"}
        tongue = world.tongues.get(folk.tongue_id)
        if tongue is not None and getattr(tongue, "script", ""):
            can.add("letters")
        out.append(Side("folk", folk.id, folk.name, folk.id, folk.race_id,
                        regions, can, folk.population, folk.cradle_region))
    return out


def _race_of(side) -> object:
    return races_mod.RACES_BY_ID.get(side.race_id)


# ---------------------------------------------------------------------------
# О чём можно узнавать: предметы познания
# ---------------------------------------------------------------------------


class Mark:
    """Предмет познания: то, о чём бывает знание, — и где оно лежит."""

    __slots__ = ("kind", "id", "name", "region_id", "hex_index", "since",
                 "hard", "folk_id")

    def __init__(self, kind, key, name, region_id, hex_index=-1, since=0,
                 hard=0.0, folk_id=""):
        self.kind = kind
        self.id = key
        self.name = name
        self.region_id = region_id
        self.hex_index = hex_index
        self.since = since
        self.hard = hard
        self.folk_id = folk_id


def _marks(world, year: int, rng) -> list:
    """Предметы, о которых в этом такте вообще может пойти речь.

    Весь мир тут не перебирается: место истории в мире бывает сотнями, и
    спрашивать о каждом каждые десять лет незачем. Берётся горсть —
    земли все (их десятки), а прочее по жребию, — и этого довольно,
    чтобы за историю мира дошла очередь до всякого.
    """
    out = []
    for region in world.regions.values():
        if region.drowned:
            continue
        out.append(Mark(cat.T_REGION, region.id, region.name, region.id,
                        region.center_hex, 0,
                        0.25 + 0.5 * (1.0 - float(region.habitat or 0.4))))

    def sample(items, limit):
        items = sorted(items, key=lambda item: item.id)
        if len(items) <= limit:
            return items
        step = max(1, len(items) // limit)
        start = rng.randint(0, step - 1) if step > 1 else 0
        return items[start::step][:limit]

    from .. import sites as sites_mod
    worth = (sites_mod.RUIN, sites_mod.TOMB, sites_mod.CRYPT, sites_mod.LAIR,
             sites_mod.HOARD, sites_mod.FIELD, sites_mod.SEALED,
             sites_mod.SUNKEN, sites_mod.SHRINE)
    for site in sample([item for item in world.sites.values()
                        if item.kind in worth], 30):
        out.append(Mark(cat.T_SITE, site.id, site.name, site.region_id,
                        site.hex_index, site.created.year if site.created else 0,
                        0.3 + 0.1 * int(getattr(site, "depth", 1) or 1)))
    for folk in world.folks.values():
        if folk.status != ACTIVE:
            continue
        out.append(Mark(cat.T_FOLK, folk.id, folk.name, folk.cradle_region,
                        -1, folk.born.year if folk.born else 0, 0.35,
                        folk.id))
    for hold in world.dominions.values():
        if not hold.alive:
            continue
        where = (hold.region_ids or [""])[0]
        out.append(Mark(cat.T_DOMINION, hold.id, hold.name, where, -1,
                        hold.began.year if hold.began else 0, 0.6))
    for route in sample([world.routes[key] for key in world.active_routes],
                        12):
        seller = world.polities.get(route.seller_id)
        where = (seller.region_ids[0] if seller is not None
                 and seller.region_ids else "")
        out.append(Mark(cat.T_ROUTE, route.id,
                        texts.route_name(world, route), where, -1,
                        route.opened.year if route.opened else 0, 0.35))
    for wonder in world.wonders.values():
        out.append(Mark(cat.T_WONDER, wonder.id, wonder.name,
                        wonder.region_id, wonder.hex_index,
                        wonder.born.year if wonder.born else 0, 0.3))
    for scar in sample(list(world.scars.values()), 10):
        out.append(Mark(cat.T_SCAR, scar.id, scar.name, scar.region_id, -1,
                        scar.created.year if scar.created else 0, 0.5))
    for kin in sample([item for item in world.species.values()
                       if kin_wild(item)], 8):
        out.append(Mark(cat.T_SPECIES, kin.id, kin.name,
                        (kin.regions or [""])[0] if kin.regions else "",
                        -1, kin.origin_year, 0.45))
    return out


def kin_wild(kin) -> bool:
    """Вид, о котором вообще спрашивают: живой и не народ.

    О народе спрашивают как о народе (`T_FOLK`): у него есть имя, земля
    и своя история. Тут — звери и твари, про которых знают, что их
    видели трижды и трижды описали по-разному.
    """
    return kin.status == "живёт" and not kin.is_people


# ---------------------------------------------------------------------------
# Такт
# ---------------------------------------------------------------------------


def tick(ctx, year: int) -> None:
    """Годовой такт: возвращаются те, кому срок вернуться."""
    _come_back(ctx, year)


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.folks:
        return
    lands = _lands(world)
    sides = _sides(world, year, lands)
    if not sides:
        return
    rng = ctx.rng("knowing", year)
    marks = _marks(world, year, rng)
    by_id = {mark.id: mark for mark in marks}
    _seed_local(ctx, year, rng, sides, marks)
    _launch(ctx, year, rng, sides, marks)
    _chart_life(ctx, year, rng)
    _spread(ctx, year, rng, sides, by_id)
    _unwarp(ctx, year, rng, sides)
    _forget(ctx, year, rng)
    _meet_outside(ctx, year, rng, sides, lands)
    _hold_life(ctx, year, rng)
    _credit(ctx, year, rng)


# ---------------------------------------------------------------------------
# Знание: заведение и подъём
# ---------------------------------------------------------------------------


def _fill(level: str, keys) -> dict:
    return {key: level for key in keys or ()}


def _note_knowing(ctx, year: int, side, mark, level: str, source: str,
                  aspects=None, trust: float = 0.0, truth: float = 0.0,
                  from_id: str = "", muddle: str = "", access: str = "открыто",
                  secret_why: str = ""):
    """Заводит или поднимает запись о знании.

    Поднимает, а не перезаписывает: общество, однажды побывавшее на
    той земле, не становится от чужого рассказа знающим о ней по
    слухам. А если знание было потеряно, та же запись оживает — и в
    ней остаётся год, когда его теряли: именно это и делает повторное
    открытие повторным.
    """
    world = ctx.world
    record = world.knowing_of(side.id, mark.id)
    if record is None:
        if len(world.knowings) >= KNOWING_CAP:
            return None
        record = world.add_knowing(
            about_kind=mark.kind, about_id=mark.id, about_name=mark.name,
            group_kind=side.kind, group_id=side.id, level=level,
            since=ctx.date_in(ctx.rng("knowing", "since", side.id, mark.id),
                              year),
            source=source, aspects=dict(aspects or {}),
            trust=round(float(trust), 2), truth=round(float(truth), 2),
            from_id=from_id, muddle=muddle, access=access,
            secret_why=secret_why, confirmed=year)
        return record

    if record.lost_year and cat.is_known(level):
        record.notes.append("%d: знание вернулось — %s"
                            % (year, cat.source_said(source)))
        record.lost_year = 0
        record.lost_why = ""
        record.kept = ""
    if cat.level_depth(level) > cat.level_depth(record.level):
        record.level = level
        record.source = source
        if from_id:
            record.from_id = from_id
    for key, value in (aspects or {}).items():
        if cat.level_depth(value) > cat.level_depth(record.aspects.get(key, "")):
            record.aspects[key] = value
    # Независимое подтверждение выправляет искажение: весть, дошедшая
    # через третьи руки как рассказ о нелюдях, перестаёт быть таким
    # рассказом, когда до того места доходят сами. Это и есть история
    # избавления мира от неверных представлений — и она тут отдельно от
    # истории находок.
    if record.muddle and float(trust) >= 0.7 \
            and cat.level_depth(level) >= 0.55:
        record.notes.append(
            "%d: %s" % (year, cat.WARP_FIXES.get(record.warp,
                                                 "сведения проверили заново")))
        record.muddle = ""
        record.warp = ""
    record.trust = round(max(record.trust, float(trust)), 2)
    record.truth = round(max(record.truth, float(truth)), 2)
    if muddle:
        record.muddle = muddle
    if access != "открыто":
        record.access = access
        record.secret_why = secret_why or record.secret_why
    record.confirmed = year
    return record


def _seed_local(ctx, year: int, rng, sides, marks) -> None:
    """Живущие знают свою землю — и знают её лучше всех.

    Это основание всего модуля: пока местное знание не заведено,
    «неизвестная земля» читается как объективно пустая, и история
    познания мира превращается в историю одной державы, вокруг которой
    все прочие ждут, пока их откроют.
    """
    world = ctx.world
    by_region = {}
    for mark in marks:
        if mark.kind == cat.T_REGION:
            by_region[mark.id] = mark
    for side in sides:
        if side.kind != "folk":
            continue
        folk = world.folks.get(side.id)
        if folk is None:
            continue
        own = sorted(side.regions)[:5]
        for region_id in own:
            mark = by_region.get(region_id)
            if mark is None:
                continue
            if world.knowing_of(side.id, region_id) is not None:
                continue
            # Что живущие знают о своей земле: почти всё, кроме её
            # прошлого. Что было тут до них, помнит не всякий народ.
            keys = [cat.EXIST, cat.WAY, cat.WATER, cat.PEOPLE, cat.DANGER,
                    cat.SEASON, cat.BACK, cat.BOUNDS, cat.RICHES, cat.BAN]
            aspects = _fill(cat.LOCAL, keys)
            deep = rng.chance(0.35)
            aspects[cat.OLD] = cat.LOCAL if deep else cat.RUMOUR
            _note_knowing(ctx, year, side, mark, cat.LOCAL, "eyes",
                          aspects=aspects, trust=0.85, truth=0.9)
        # И о соседней земле — то, что доносят ходящие туда.
        for region_id in own[:2]:
            region = world.regions.get(region_id)
            if region is None:
                continue
            for neighbor_id in sorted(region.neighbors)[:3]:
                mark = by_region.get(neighbor_id)
                if mark is None or world.knowing_of(side.id, neighbor_id):
                    continue
                _note_knowing(
                    ctx, year, side, mark, cat.FOREIGN, "walker",
                    aspects=_fill(cat.FOREIGN, (cat.EXIST, cat.WAY,
                                                cat.PEOPLE)),
                    trust=0.5, truth=0.55)


# ---------------------------------------------------------------------------
# Повод: отчего вообще собрались идти
# ---------------------------------------------------------------------------


def _spurs_for(ctx, year: int, side, mark) -> list:
    """Какие поводы идти к этому предмету есть у этого общества сейчас.

    Каждый повод тут опирается на то, что в мире уже случилось: карта в
    руках, пропавший поход, иссякшая жила, проигранная война, чужой
    успех. Пустой список значит, что похода не будет, — и это
    правильный ответ куда чаще, чем непустой.
    """
    world = ctx.world
    polity = world.polities.get(side.id) if side.kind == "polity" else None
    out = []

    # Старая карта на руках — и чем старше, тем больше охоты проверить.
    for chart in world.charts_of(side.id):
        if chart.made is not None and year - chart.made.year >= 150 \
                and (not chart.covers or mark.region_id in chart.covers):
            out.append(("chart", chart.id))
            break

    # Пропавший поход к той же цели: о нём помнят и за ним идут.
    for expedition in world.expeditions.values():
        if expedition.aim_id != mark.id:
            continue
        if expedition.result in (cat.E_GONE, cat.E_DARK):
            out.append(("lost", expedition.id))
            break

    # Чужой успех: о находке знают, дороги не знают.
    for finding in world.findings_about(mark.id):
        if finding.group_id and finding.group_id != side.id:
            out.append(("rival", finding.id))
            break

    if polity is not None:
        if polity.ruler_id and world.era_index_at(year) >= 1:
            out.append(("order", polity.ruler_id))
        if polity.shortages or polity.hunger > 0.3:
            out.append(("need", ""))
        if polity.known and world.era_index_at(year) >= 2:
            out.append(("craft", ""))
        if polity.wars_lost and polity.last_war >= year - LOOK_BACK:
            out.append(("defeat", ""))
        if polity.routes and mark.kind in (cat.T_ROUTE, cat.T_REGION,
                                           cat.T_FOLK):
            out.append(("merchant", ""))
        faith = world.faiths.get(polity.faith_id)
        if faith is not None and mark.kind in (cat.T_SITE, cat.T_WONDER,
                                               cat.T_SCAR, cat.T_REGION):
            out.append(("holy", faith.id))

    # Переселенцы, пришедшие с той стороны: они бегут от чего-то.
    for migration in world.migrations.values():
        if migration.year < year - LOOK_BACK or migration.year > year:
            continue
        if migration.to_region in side.regions \
                and migration.from_region == mark.region_id:
            out.append(("flight", migration.id))
            break

    # Земля переменилась: после беды прежние приметы не годятся.
    for calamity in world.calamities.values():
        if calamity.start is None or calamity.start.year < year - LOOK_BACK \
                or calamity.start.year > year:
            continue
        if mark.region_id and mark.region_id in (calamity.region_ids or ()):
            out.append(("coast", calamity.id))
            break

    # Вещь без родины и предание о месте.
    if mark.kind in (cat.T_SITE, cat.T_SCAR, cat.T_WONDER):
        site = world.sites.get(mark.id)
        if site is not None and getattr(site, "story", ""):
            out.append(("tale", mark.id))
        for artifact in world.artifacts.values():
            if artifact.made is not None \
                    and year - artifact.made.year >= 300 \
                    and getattr(artifact, "region_id", "") == mark.region_id:
                out.append(("find", artifact.id))
                break

    # Складная догадка: опоры в мире у неё нет вовсе, и это её
    # отличительная черта. Поэтому она возможна только там, где есть
    # кому её высказать, — у общества с грамотой и не в первый век.
    if "letters" in side.can and world.era_index_at(year) >= 2:
        out.append(("guess", ""))

    # Знание было и пропало: о нём помнят, что оно было.
    record = world.knowing_of(side.id, mark.id)
    if record is not None and record.lost_year:
        out.append(("tale", record.id))

    return out


def _goals_for(ctx, side, mark, race) -> list:
    """Какие задачи этому обществу по силам у этого предмета."""
    out = []
    for goal in cat.GOALS:
        if goal.want != mark.kind:
            continue
        if "sea" in goal.needs and "ships" not in side.can:
            continue
        if "under" in goal.needs:
            if race is None or races_mod.UNDERGROUND not in race.terrains:
                continue
        if "ore" in goal.needs and not side.can.intersection(("money",
                                                              "tools")):
            continue
        if "guide" in goal.needs and not mark.folk_id:
            continue
        if "ruins" in goal.needs and mark.kind != cat.T_SITE:
            continue
        if "beast" in goal.needs and mark.kind not in (cat.T_DOMINION,
                                                       cat.T_SPECIES):
            continue
        weight = 1.0
        host_aims = ()
        for host in cat.HOSTS:
            if host.of == side.kind:
                host_aims = host.aims
                break
        if goal.group in host_aims:
            weight *= 1.4
        weight *= 1.3 - 0.6 * goal.hard
        out.append((goal, weight))
    return out


def _plan(ctx, year: int, rng, side, marks):
    """Что это общество может пойти узнавать — и отчего именно сейчас."""
    world = ctx.world
    race = _race_of(side)
    pool = []
    step = max(1, len(marks) // 30)
    start = rng.randint(0, step - 1) if step > 1 else 0
    for mark in sorted(marks, key=lambda item: item.id)[start::step]:
        record = world.knowing_of(side.id, mark.id)
        if record is not None and record.known \
                and cat.level_depth(record.level) >= 0.8:
            continue          # знают и так: искать тут нечего
        if mark.kind == cat.T_FOLK and mark.folk_id == side.folk_id:
            continue          # сам себя народ не открывает
        spurs = _spurs_for(ctx, year, side, mark)
        if not spurs:
            continue
        goals = _goals_for(ctx, side, mark, race)
        if not goals:
            continue
        near = 1.0
        if mark.region_id and mark.region_id in side.regions:
            near = 1.5        # своя земля: туда ходят охотнее
        elif mark.region_id:
            region = world.regions.get(mark.region_id)
            home = world.regions.get(side.home)
            if region is not None and home is not None \
                    and mark.region_id in home.neighbors:
                near = 1.2
        lost = 1.6 if (record is not None and record.lost_year) else 1.0
        # Мест истории в мире сотни, а земель десятки, и без этой
        # поправки мир спрашивал бы только о руинах: на первом замере
        # «прошлое» забирало себе почти половину всех походов.
        pool.append(((mark, spurs, goals),
                     near * lost * len(spurs) * KIND_URGE.get(mark.kind, 1.0)))
    if not pool:
        return None
    mark, spurs, goals = rng.weighted(pool)
    spur_key, spur_ref = rng.choice(sorted(spurs))
    goal = rng.weighted(goals)
    record = world.knowing_of(side.id, mark.id)
    haze = _haze_for(record, spur_key)
    return mark, goal, spur_key, spur_ref, haze


def _haze_for(record, spur_key: str) -> str:
    """Насколько заранее известно, куда идут."""
    if spur_key == "chart":
        return "oldmap"
    if spur_key == "find":
        return "thing"
    if spur_key == "lost":
        return "gone"
    if record is None or not record.known:
        return "tale"
    if cat.level_depth(record.level) >= 0.5:
        return "known"
    return "rough"


# ---------------------------------------------------------------------------
# Снаряжение похода
# ---------------------------------------------------------------------------


def _party(rng, goal, side, mark) -> list:
    """Из кого собрали отряд.

    Собирается он под вопросы задачи, а не по списку званий, — и
    нарочно собирается неполным: кого-то не нашли, на кого-то не хватило
    денег. Именно отсюда берутся потом неверные толкования: отряд без
    толмача привозит рассказ о враждебности, которой не было.
    """
    roles = ["head"]
    wanted = list(goal.gives)
    for aspect in wanted:
        if rng.chance(0.28):
            continue          # этого в отряде не будет, и это скажется
        picks = [role for role in cat.ROLES
                 if aspect in role.gives and role.key not in roles]
        if not picks:
            continue
        roles.append(rng.choice(sorted(picks, key=lambda item: item.key)).key)
        if len(roles) >= 6:
            break
    if "guide" in goal.needs and mark.folk_id and "local" not in roles:
        roles.append("local")
    if "sea" in goal.needs and "sailor" not in roles:
        roles.append("sailor")
    if "arms" in side.can and rng.chance(0.5) and "guard" not in roles:
        roles.append("guard")
    if "letters" in side.can and rng.chance(0.55) and "scribe" not in roles:
        roles.append("scribe")
    if "money" in side.can and rng.chance(0.4) and "bearer" not in roles:
        roles.append("bearer")
    return roles[:8]


def _gear(rng, goal, side, charts) -> list:
    """Что взяли с собой."""
    gear = ["food"]
    if "sea" in goal.needs:
        gear.append("ships")
    if "under" in goal.needs or "ruins" in goal.needs:
        gear.extend(("ropes", "lamps"))
    if "guide" in goal.needs:
        gear.append("gifts")
    if "money" in side.can:
        gear.append("money")
    if "tools" in side.can and rng.chance(0.7):
        gear.append("tools")
    if "letters" in side.can and rng.chance(0.8):
        gear.append("writing")
    if charts:
        gear.append("charts")
    if rng.chance(0.4):
        gear.append("beasts")
    if rng.chance(0.3):
        gear.append("cure")
    if rng.chance(0.2):
        gear.append("spells")
    return sorted(set(gear))


def _probe_kind(goal) -> str:
    if goal.key == "edge":
        return "ice"
    if "sea" in goal.needs:
        return "sea"
    if "under" in goal.needs:
        return "deep"
    return "land"


def _launch(ctx, year: int, rng, sides, marks) -> None:
    world = ctx.world
    flying = [key for key in world.active_expeditions
              if world.expeditions[key].goal]
    if len(flying) >= PROBE_IN_FLIGHT:
        return
    era = world.era_index_at(year)
    chance = PROBE_CHANCE * ctx.density() * (0.55 + 0.20 * era)
    if not rng.chance(min(0.92, chance)):
        return

    pool = []
    for side in sides:
        if ctx.probe_count.get(side.id, 0) >= PROBE_PER_SIDE:
            continue
        weight = 0.4 + min(3.0, side.souls / 150000.0)
        if side.kind == "polity":
            weight *= 1.5
            if "money" in side.can:
                weight *= 1.3
            if "letters" in side.can:
                weight *= 1.2
        else:
            # Народ ходит по своей земле и к соседям, и ходит чаще, чем
            # о том пишут: своих походов у него больше, чем державных,
            # но они тише.
            weight *= 0.7
        pool.append((side, weight))
    if not pool:
        return
    side = rng.weighted(pool)
    plan = _plan(ctx, year, rng, side, marks)
    if plan is None:
        return
    mark, goal, spur_key, spur_ref, haze = plan

    race = _race_of(side)
    if race is None:
        return
    charts = world.charts_of(side.id)
    roles = _party(rng, goal, side, mark)
    gear = _gear(rng, goal, side, charts)
    host = _host_for(rng, side, goal)

    date = ctx.date_in(rng, year)
    sex = "f" if rng.chance(0.38) else "m"
    trade = _trade_for(rng, goal)
    leader = ctx.make_figure(
        rng, race, year, role=cat.trade_name(trade, sex),
        region_id=side.home or mark.region_id, sex=sex, epithet_chance=0.7)
    crew = _crew(rng, goal, side)
    attempt = ctx.expedition_attempts.get(mark.id, 0) + 1
    ctx.expedition_attempts[mark.id] = attempt
    ctx.probe_count[side.id] = ctx.probe_count.get(side.id, 0) + 1

    spur = cat.SPURS_BY_KEY[spur_key]
    expedition = world.add_expedition(
        name=ctx.forge.unique("expedition",
                              lambda: texts.probe_name(rng, goal, mark), rng),
        kind=_probe_kind(goal), leader_id=leader.id, race_id=race.id,
        start=date,
        polity_id=side.id if side.kind == "polity" else "",
        from_region=side.home, target_region=(
            mark.region_id if mark.kind == cat.T_REGION else ""),
        target_name=mark.name, crew=crew, attempt=attempt,
        goal=goal.key, goal_group=goal.group, spur=spur_key, haze=haze,
        hope=spur.hope, aim_kind=mark.kind, aim_id=mark.id,
        aim_name=mark.name, host_kind=side.kind, host_id=side.id,
        host_said=host.said, roles=roles, gear=gear,
        plan=_route_plan(world, side, mark),
        marks=[{"что": "снарядились", "год": year}])
    if rng.chance(0.22):
        expedition.secret_aim = rng.choice(sorted(cat.DRIVE_NAMES.values()))
    leader.roles.append("глава похода")

    title, text = texts.launch(rng, world, expedition, leader, side, mark,
                               goal, spur, spur_ref)
    event = world.add_event(
        date=date, era_index=era, kind="probe_start", title=title, text=text,
        importance=2 if goal.hard < 0.5 else 3, actors=[leader.id],
        subjects=[expedition.id, mark.id]
        + ([side.id] if side.kind == "polity" else []),
        region_id=mark.region_id or side.home, race_id=race.id)
    expedition.notes.append("зачин: %s" % event.id)

    span = 1 + int(round(goal.hard * 7)) + (2 if "sea" in goal.needs else 0)
    ctx.probe_due[expedition.id] = year + max(1, min(14, span))


def _host_for(rng, side, goal):
    """Кто именно снарядил: держава, цех, храм, вольные, сам народ."""
    pool = []
    for host in cat.HOSTS:
        if host.of != side.kind:
            continue
        weight = host.weight
        if goal.group in host.aims:
            weight *= 1.6
        if host.can and not side.can.issuperset(
                set(host.can).intersection(("money", "ships", "arms",
                                            "letters", "tools"))):
            weight *= 0.5
        pool.append((host, weight))
    if not pool:
        return cat.HOSTS_BY_KEY["free"]
    return rng.weighted(pool)


def _trade_for(rng, goal) -> str:
    """Чем занимается тот, кто такой поход ведёт."""
    by_group = {
        cat.G_LAND: ("opener", "charter", "sailor", "earth"),
        cat.G_WILD: ("nature", "wonder", "earth", "deep"),
        cat.G_OLD: ("digger", "chron", "collect", "walker"),
        cat.G_FOLK: ("tongues", "envoy", "walker", "chron"),
        cat.G_GOODS: ("walker", "charter", "master", "guide"),
        cat.G_WAR: ("scout", "charter", "envoy", "opener"),
    }
    return rng.choice(by_group.get(goal.group, ("walker",)))


def _crew(rng, goal, side) -> int:
    base = rng.randint(6, 30)
    if "money" in side.can:
        base += rng.randint(10, 60)
    if "sea" in goal.needs:
        base += rng.randint(20, 90)
    if "people" in side.can:
        base += rng.randint(5, 25)
    return int(base)


def _route_plan(world, side, mark) -> list:
    """Какой путь намечали — по землям, а не по гексам.

    Намечают его по тому, что известно: от своей земли к соседней и
    дальше. Неизвестные участки в план не попадают — в них и начинается
    то, из-за чего походы не возвращаются.
    """
    home = world.regions.get(side.home)
    if home is None or not mark.region_id:
        return []
    if mark.region_id == home.id:
        return [home.id]
    if mark.region_id in home.neighbors:
        return [home.id, mark.region_id]
    for neighbor_id in sorted(home.neighbors):
        region = world.regions.get(neighbor_id)
        if region is not None and mark.region_id in region.neighbors:
            return [home.id, neighbor_id, mark.region_id]
    return [home.id, mark.region_id]


# ---------------------------------------------------------------------------
# Возвращение и исход
# ---------------------------------------------------------------------------


def _side_by_id(world, kind: str, key: str, year: int):
    """Общество по номеру — на тот час, когда поход вернулся.

    Держава могла и пасть, пока отряд ходил, и это не ошибка: сведения
    всё равно куда-то попадают — к народу, который её составлял.
    """
    if kind == "polity":
        polity = world.polities.get(key)
        if polity is not None and polity.status == ACTIVE:
            capital = world.settlements.get(polity.capital_id)
            return Side("polity", polity.id, polity.full_name,
                        capital.folk_id if capital is not None else "",
                        polity.race_id, set(polity.region_ids), {"money"},
                        polity.population,
                        capital.region_id if capital is not None else "")
        if polity is not None:
            capital = world.settlements.get(polity.capital_id)
            folk_id = capital.folk_id if capital is not None else ""
            folk = world.folks.get(folk_id)
            if folk is not None and folk.status == ACTIVE:
                return Side("folk", folk.id, folk.name, folk.id, folk.race_id,
                            {folk.cradle_region}, {"people"}, folk.population,
                            folk.cradle_region)
        return None
    folk = world.folks.get(key)
    if folk is None or folk.status != ACTIVE:
        return None
    return Side("folk", folk.id, folk.name, folk.id, folk.race_id,
                {folk.cradle_region}, {"people", "guide"}, folk.population,
                folk.cradle_region)


def _mark_by_id(world, kind: str, key: str, name: str):
    """Предмет познания по номеру."""
    if kind == cat.T_REGION:
        region = world.regions.get(key)
        if region is not None:
            return Mark(kind, region.id, region.name, region.id,
                        region.center_hex)
    elif kind == cat.T_SITE:
        site = world.sites.get(key)
        if site is not None:
            return Mark(kind, site.id, site.name, site.region_id,
                        site.hex_index)
    elif kind == cat.T_FOLK:
        folk = world.folks.get(key)
        if folk is not None:
            return Mark(kind, folk.id, folk.name, folk.cradle_region, -1, 0,
                        0.35, folk.id)
    elif kind == cat.T_DOMINION:
        hold = world.dominions.get(key)
        if hold is not None:
            return Mark(kind, hold.id, hold.name,
                        (hold.region_ids or [""])[0])
    elif kind == cat.T_ROUTE:
        route = world.routes.get(key)
        if route is not None:
            return Mark(kind, route.id, texts.route_name(world, route), "")
    elif kind == cat.T_WONDER:
        wonder = world.wonders.get(key)
        if wonder is not None:
            return Mark(kind, wonder.id, wonder.name, wonder.region_id,
                        wonder.hex_index)
    elif kind == cat.T_SCAR:
        scar = world.scars.get(key)
        if scar is not None:
            return Mark(kind, scar.id, scar.name, scar.region_id)
    elif kind == cat.T_SPECIES:
        kin = world.species.get(key)
        if kin is not None:
            return Mark(kind, kin.id, kin.name,
                        (kin.regions or [""])[0] if kin.regions else "")
    return Mark(kind, key, name or "?", "")


def _locals_of(world, mark) -> list:
    """Кто знает это место как свой дом.

    Отсюда и берётся главная поправка модуля: «первым дошёл» —
    первым из своих, а не первым вообще. Если тут живут, фактическое
    первенство принадлежит живущим, и в записи это так и стоит.
    """
    rows = []
    for record in world.knowings_about(mark.id):
        if record.level == cat.LOCAL and record.group_kind == "folk":
            folk = world.folks.get(record.group_id)
            if folk is not None:
                rows.append(folk)
    if not rows and mark.folk_id:
        folk = world.folks.get(mark.folk_id)
        if folk is not None:
            rows.append(folk)
    return rows


def _snag_fits(snag_key: str, goal, kind: str) -> bool:
    """Не всякая помеха годится всякой дороге."""
    sea_only = ("storm", "ice")
    under_only = ("dark",)
    ruins_only = ("trap",)
    if snag_key in sea_only:
        return kind == "sea" or goal.key == "edge"
    if snag_key in under_only:
        return kind == "deep" or "under" in goal.needs
    if snag_key in ruins_only:
        return "ruins" in goal.needs
    if snag_key == "flood":
        return kind != "sea"
    return True


def _luck(ctx, expedition, goal, side, mark, year: int) -> float:
    """Чего стоит ждать от этого похода — до того, как брошен жребий.

    Считается по подготовке, а не по жребию: отвечает ли состав
    вопросам задачи, взято ли нужное, насколько задача трудна, который
    это раз и не идут ли они в тёмные века по разорённой земле.
    """
    world = ctx.world
    luck = 0.42
    luck *= 0.6 + 0.8 * cat.role_fit(goal, expedition.roles)
    luck *= 0.6 + 0.6 * cat.gear_fit(goal, expedition.gear)
    luck *= 1.25 - 0.7 * goal.hard
    luck += 0.05 * min(3, max(0, expedition.attempt - 1))
    luck += 0.035 * world.era_index_at(year)
    if mark.region_id:
        region = world.regions.get(mark.region_id)
        if region is not None:
            luck -= 0.12 * float(region.savagery or 0.0)
            luck -= 0.10 * float(region.risk or 0.0)
    luck -= 0.12 * ctx.gloom(mark.region_id or expedition.from_region)
    if side is not None and "guide" in side.can:
        luck += 0.05
    if "local" in expedition.roles:
        luck += 0.08         # местный проводник стоит дороже любой карты
    return max(0.05, min(0.93, luck))


def _answers(rng, goal, expedition, luck: float) -> list:
    """На какие вопросы поход всё-таки принёс ответ."""
    covered = set()
    for key in expedition.roles:
        role = cat.ROLES_BY_KEY.get(key)
        if role is not None:
            covered.update(role.gives)
    out = []
    for aspect in goal.gives:
        spec = cat.ASPECTS_BY_KEY.get(aspect)
        hard = spec.hard if spec is not None else 0.4
        chance = luck * (1.25 - 0.7 * hard)
        if aspect in covered:
            chance += 0.25
        if rng.chance(max(0.05, min(0.95, chance))):
            out.append(aspect)
    return out


def _end_for(rng, goal, mark, expedition, luck: float, spur: str,
             locals_known: bool) -> str:
    """Чем кончился поход. Удача тут — не одно только новое."""
    bad = 1.0 - luck
    pairs = [
        (cat.E_WON, 1.5 * luck * luck),
        (cat.E_PART, 1.3 * luck),
        (cat.E_SAME, 0.45 + 0.35 * bad),
        (cat.E_FIXED, 0.60),
        (cat.E_WRONG, 0.45 if expedition.haze == "oldmap" else 0.12),
        (cat.E_SAFER, 0.30),
        (cat.E_SHORT, 1.10 * bad),
        (cat.E_TRACES, 0.55 if spur == "lost" else 0.12),
        (cat.E_MUDDLE, 0.22 + 0.30 * bad),
        (cat.E_MET, 0.75 if locals_known else 0.10),
        (cat.E_GONE, 0.85 * bad * bad),
        (cat.E_STAYED, 0.14 if goal.key in ("habitable", "harbour", "ore",
                                            "deep") else 0.04),
        (cat.E_DARK, 0.28 * bad),
    ]
    return rng.weighted(pairs)


def _evidence_for(rng, expedition, end: str) -> str:
    """Чем это дошло до потомков: записью, камнем, преданием, выводом.

    Свой свод тут не заводится: на этот вопрос в генераторе отвечает
    `landlore.EVIDENCE`, и ответ должен быть один.
    """
    if "writing" in expedition.gear and end not in (cat.E_GONE, cat.E_DARK):
        return landlore.RECORD
    if end in (cat.E_GONE, cat.E_DARK):
        return rng.choice((landlore.TALE, landlore.GUESS))
    if "scribe" in expedition.roles:
        return landlore.CHRON
    return rng.choice((landlore.TALE, landlore.CHRON))


def _level_for(end: str, answers, goal) -> str:
    """Каким стало знание после такого похода."""
    if end == cat.E_WON:
        return cat.STUDIED if len(answers) >= max(1, len(goal.gives) - 1) \
            else cat.PARTLY
    if end in (cat.E_PART, cat.E_MET, cat.E_SAFER, cat.E_TRACES):
        return cat.PARTLY
    if end == cat.E_FIXED:
        return cat.SKETCH
    if end in (cat.E_SAME, cat.E_WRONG):
        return cat.VISITED
    if end == cat.E_MUDDLE:
        return cat.MUDDLED
    if end == cat.E_STAYED:
        return cat.STUDIED
    if end in (cat.E_GONE, cat.E_DARK):
        return cat.TRACES
    return cat.RUMOUR


def _come_back(ctx, year: int) -> None:
    world = ctx.world
    for expedition_id in sorted(ctx.probe_due):
        if ctx.probe_due[expedition_id] > year:
            continue
        ctx.probe_due.pop(expedition_id, None)
        expedition = world.expeditions.get(expedition_id)
        if expedition is not None and expedition.end is None:
            _finish(ctx, expedition, year)


def _finish(ctx, expedition, year: int) -> None:
    world = ctx.world
    rng = ctx.rng("knowing", "end", expedition.id)
    goal = cat.GOALS_BY_KEY.get(expedition.goal)
    if goal is None:
        return
    side = _side_by_id(world, expedition.host_kind, expedition.host_id, year)
    mark = _mark_by_id(world, expedition.aim_kind, expedition.aim_id,
                       expedition.aim_name)
    leader = world.figures.get(expedition.leader_id)
    date = ctx.date_in(rng, year)
    luck = _luck(ctx, expedition, goal, side, mark, year)

    # --- что помешало ---------------------------------------------------
    picks = [snag for snag in cat.SNAGS
             if _snag_fits(snag.key, goal, expedition.kind)]
    count = 0 if rng.chance(0.32) else rng.weighted(((1, 3.0), (2, 1.3),
                                                     (3, 0.45)))
    toll = 0.0
    taken = []
    for _step in range(int(count)):
        left = [snag for snag in picks if snag.key not in taken]
        if not left:
            break
        snag = rng.choice(sorted(left, key=lambda item: item.key))
        taken.append(snag.key)
        luck = max(0.03, luck - snag.cost)
        toll += snag.kills
        expedition.snags.append(snag.said)
        expedition.marks.append({"что": snag.said, "год": year})

    # --- не передумали ли по дороге -------------------------------------
    haze = cat.HAZES_BY_KEY.get(expedition.haze)
    if haze is not None and rng.chance(haze.turn):
        key, line = rng.choice(cat.TURNS)
        expedition.turn = line
        expedition.turn_year = max(expedition.start.year,
                                   year - rng.randint(0, 2))
        expedition.marks.append({"что": line, "год": expedition.turn_year})
        if key in ("better", "prior", "folk"):
            luck = min(0.9, luck + 0.06)
        else:
            luck = max(0.04, luck - 0.10)

    locals_known = bool(_locals_of(world, mark))
    end = _end_for(rng, goal, mark, expedition, luck, expedition.spur,
                   locals_known)
    answers = _answers(rng, goal, expedition, luck) \
        if cat.end_tells(end) else []

    # --- кого недосчитались ---------------------------------------------
    if end == cat.E_GONE:
        expedition.deaths = expedition.crew
        survivors = 0
    else:
        share = max(0.0, min(0.85, toll * 0.35 + (1.0 - luck) * 0.25))
        if end == cat.E_DARK:
            share = max(share, 0.5)
        expedition.deaths = int(expedition.crew * share)
        survivors = expedition.crew - expedition.deaths

    # Что об этом знали до похода — запоминается до того, как знание
    # поднимут: иначе повторное открытие нельзя отличить от первого.
    before = world.knowing_of(side.id, mark.id) if side is not None else None
    before_level = before.level if before is not None else cat.DARK
    was_lost = bool(before is not None and before.lost_year)

    expedition.result = end
    expedition.went = list(expedition.plan)
    expedition.marks.append({"что": end, "год": year})
    world.end_expedition(expedition, date, end)

    # --- знание --------------------------------------------------------
    level = _level_for(end, answers, goal)
    trust = min(0.95, 0.45 + 0.45 * luck)
    truth = min(0.95, 0.35 + 0.55 * luck)
    if end == cat.E_MUDDLE:
        truth = min(truth, 0.45)
    learners = []
    if side is not None:
        learners.append(side)
    folk = world.folks.get(leader.folk_id if leader is not None else "")
    if folk is not None and folk.status == ACTIVE \
            and (side is None or folk.id != side.id):
        learners.append(Side("folk", folk.id, folk.name, folk.id,
                             folk.race_id, {folk.cradle_region}, {"people"},
                             folk.population, folk.cradle_region))
    secret_why = ""
    if side is not None and side.kind == "polity" \
            and goal.group in (cat.G_WAR, cat.G_GOODS) \
            and cat.end_good(end) >= 0.5 and rng.chance(0.30):
        # Кто один знает дорогу, тот один и везёт товар. Такое знание
        # по каналам не пойдёт: `_spread` берёт только открытое.
        key = "trade" if goal.group == cat.G_GOODS else "war"
        secret_why = cat.SECRET_NAMES[key]
    for learner in learners:
        _note_knowing(
            ctx, year, learner, mark, level, "probe",
            aspects=_fill(level, answers), trust=trust, truth=truth,
            access="тайна" if secret_why and learner is side else "открыто",
            secret_why=secret_why if learner is side else "",
            muddle=("источники похода расходятся между собой"
                    if end == cat.E_MUDDLE else ""))
        if learner.id not in expedition.told:
            expedition.told.append(learner.id)

    # --- земля, до которой дошли ногами ---------------------------------
    if mark.kind == cat.T_REGION and end in (cat.E_WON, cat.E_PART,
                                             cat.E_MET, cat.E_STAYED):
        region = world.regions.get(mark.id)
        if region is not None and not region.known:
            world.discover_region(region, year,
                                  figure_id=leader.id if leader else "",
                                  race_id=expedition.race_id)
            ctx.spread_knowledge()
            if region.id not in expedition.discovered:
                expedition.discovered.append(region.id)

    # --- находка --------------------------------------------------------
    finding = None
    worth = end in (cat.E_WON, cat.E_PART, cat.E_MET)
    if not worth and end in (cat.E_WRONG, cat.E_SAFER, cat.E_TRACES) \
            and rng.chance(0.5):
        worth = True
    if worth and side is not None:
        finding = _make_finding(ctx, year, rng, expedition, leader, side,
                                mark, goal, end, answers, trust, truth, date,
                                before_level, was_lost)

    # --- карта ----------------------------------------------------------
    chart = None
    # Карту составляет не всякий поход: нужен тот, кто умеет её
    # составить, и то, чем записать. Но и книжник с бумагой годится —
    # иначе карт в мире выходит одна на тысячу лет.
    can_draw = ("chart" in expedition.roles or "scribe" in expedition.roles
                or "writing" in expedition.gear)
    if side is not None and can_draw and cat.end_good(end) >= 0.40 \
            and rng.chance(0.70):
        chart = _make_chart(ctx, year, rng, expedition, leader, side, mark,
                            luck)

    # --- встреча --------------------------------------------------------
    if side is not None and (end == cat.E_MET
                             or (locals_known and cat.end_good(end) >= 0.45
                                 and rng.chance(0.45))):
        _make_meeting(ctx, year, rng, expedition, side, mark, end, leader)

    # --- не вернулись ---------------------------------------------------
    if end in (cat.E_GONE, cat.E_DARK) and leader is not None:
        if end == cat.E_GONE:
            world.schedule_death(
                leader, date,
                "сгинул в походе" if leader.sex == "m" else "сгинула в походе")
        expedition.notes.append(
            "о судьбе похода известно только по косвенному")
        if side is not None:
            _note_knowing(ctx, year, side, mark, cat.TRACES, "walker",
                          aspects={cat.DANGER: cat.TRACES}, trust=0.3,
                          truth=0.5)

    # --- остались там ---------------------------------------------------
    if end == cat.E_STAYED and side is not None:
        _start_settling(ctx, year, rng, side, mark, expedition,
                        forced=cat.H_BASE)
    elif side is not None and cat.end_good(end) >= 0.45 \
            and goal.key in ("habitable", "harbour", "ore", "road", "deep",
                             "market", "vein", "shore", "isles", "pass",
                             "ruins", "life") and rng.chance(HOLD_CHANCE):
        _start_settling(ctx, year, rng, side, mark, expedition)

    # --- вес и летопись -------------------------------------------------
    weight = 1
    if finding is not None:
        weight = finding.weight
    elif cat.end_good(end) >= 0.5:
        weight = 2
    expedition.weight = weight

    if leader is not None and rng.chance(EXPLORER_CHANCE):
        _profile(ctx, year, rng, expedition, leader, side, finding, chart,
                 goal)

    title, text = texts.ending(rng, world, expedition, leader, mark, goal,
                               end, survivors, finding)
    importance = 2
    if end == cat.E_GONE:
        importance = 3
    if finding is not None:
        importance = min(5, 2 + finding.weight)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="probe_end",
        title=title, text=text, importance=importance,
        actors=[leader.id] if leader is not None else [],
        subjects=[expedition.id, mark.id]
        + ([finding.id] if finding is not None else [])
        + ([chart.id] if chart is not None else []),
        region_id=mark.region_id or expedition.from_region,
        race_id=expedition.race_id)
    expedition.notes.append("исход: %s" % event.id)


# ---------------------------------------------------------------------------
# Находка: чем именно отличился поход и кому это зачтётся
# ---------------------------------------------------------------------------


def _find_kind(world, rng, expedition, goal, mark, end: str, answers,
               was_lost: bool, locals_folk, known_before: bool) -> str:
    if was_lost:
        return cat.F_BACK
    if end == cat.E_MET or (goal.group == cat.G_FOLK and locals_folk):
        return cat.F_MET
    if goal.key in ("road", "pass", "around", "oldroad", "currents",
                    "desert", "strait") and end in (cat.E_WON, cat.E_SAFER):
        return cat.F_WAY
    if end == cat.E_WRONG:
        return cat.F_DENIED
    if goal.group == cat.G_OLD and cat.OLD in answers:
        return cat.F_NAMED
    if expedition.spur == "tale" and end == cat.E_WON:
        return cat.F_PROVED
    if "chart" in expedition.roles and "writing" in expedition.gear:
        return cat.F_CHART
    if not known_before and not locals_folk:
        return cat.F_FOOT
    if expedition.spur == "rival":
        return cat.F_GATHER
    return cat.F_TOLD


def _wrong_for(rng, goal, expedition, mark) -> str:
    """Чего поход не понял — и из-за кого именно.

    Неверное толкование тут не случайность: оно берётся из слепоты
    отряда. Отряд без толмача привозит рассказ о вражде, отряд без
    книжника приписывает постройку не тому народу.
    """
    roles = set(expedition.roles)
    pool = []
    if goal.group == cat.G_OLD or mark.kind in (cat.T_SITE, cat.T_SCAR):
        hard = not roles.intersection(("scribe", "digger"))
        for key in ("whose", "temple", "fort", "signs", "date", "relic",
                    "literal"):
            pool.append((key, 1.4 if hard else 0.35))
    if cat.PEOPLE in goal.gives or cat.SPEECH in goal.gives \
            or mark.kind == cat.T_FOLK:
        hard = "tongue" not in roles and "local" not in roles
        for key in ("hostile", "empty", "literal"):
            pool.append((key, 1.6 if hard else 0.3))
    if goal.group in (cat.G_GOODS, cat.G_WILD):
        hard = not roles.intersection(("trader", "smith", "hunter"))
        for key in ("riches", "danger", "one"):
            pool.append((key, 1.2 if hard else 0.3))
    if not pool:
        pool = [("one", 1.0), ("date", 0.6)]
    return rng.weighted(pool)


def _fruits_for(rng, goal, weight: int) -> list:
    """Что из находки вышло. Чаще всего — строка в своде, и только."""
    by_group = {
        cat.G_LAND: ("chart", "way", "bounds", "link"),
        cat.G_WILD: ("chart", "ore", "fear", "doubt"),
        cat.G_OLD: ("date", "house", "proved", "denied", "doubt"),
        cat.G_FOLK: ("words", "custom", "trade", "faith", "push"),
        cat.G_GOODS: ("trade", "market", "cheap", "mono", "old_road", "ore"),
        cat.G_WAR: ("crisis", "ally", "claim", "outpost", "war"),
    }
    pool = list(by_group.get(goal.group, ("chart",)))
    out = []
    if weight <= 1 and rng.chance(0.62):
        return ["none"]
    count = 1 if weight <= 2 else (2 if weight <= 4 else 3)
    for _step in range(count):
        left = [key for key in pool if key not in out]
        if not left:
            break
        out.append(rng.choice(sorted(left)))
    if weight >= 4 and rng.chance(0.45):
        out.append(rng.choice(("settle", "move", "plague", "faith")))
    return out


def _make_finding(ctx, year: int, rng, expedition, leader, side, mark, goal,
                  end: str, answers, trust: float, truth: float, date,
                  before_level: str, was_lost: bool):
    world = ctx.world
    locals_folk = _locals_of(world, mark)
    known_before = cat.is_known(before_level) or bool(
        [record for record in world.knowings_about(mark.id)
         if record.group_id != side.id])
    kind = _find_kind(world, rng, expedition, goal, mark, end, answers,
                      was_lost, locals_folk, known_before)

    # --- три первенства -------------------------------------------------
    leader_name = leader.name if leader is not None else "неизвестный"
    prime = {}
    if locals_folk:
        prime[cat.P_FACT] = "народ по имени %s — они тут жили" \
            % locals_folk[0].name
    elif not known_before:
        prime[cat.P_FACT] = leader_name
    else:
        prime[cat.P_FACT] = "неизвестно кто: до них тут бывали"
    wrote = "writing" in expedition.gear or "scribe" in expedition.roles
    prime[cat.P_WRIT] = leader_name if wrote else "не записано никем"

    twist = ""
    chance = 0.16 + (0.26 if not wrote else 0.0) \
        + (0.22 if "local" in expedition.roles else 0.0)
    if rng.chance(min(0.7, chance)):
        key = rng.weighted([(item, 1.0 if item != "guide" else
                             (2.0 if "local" in expedition.roles else 0.0))
                            for item, _said in cat.CREDIT_TWISTS])
        twist = cat.CREDIT_NAMES[key]
        if key in ("crown", "theft", "letters"):
            prime[cat.P_FAME] = side.name
        elif key in ("silence", "papers", "ban", "doubt"):
            prime[cat.P_FAME] = "никого: об этом узнали позже и от других"
        else:
            prime[cat.P_FAME] = leader_name
    else:
        prime[cat.P_FAME] = leader_name

    basis = "own" if wrote else rng.choice(("witness", "later", "local"))
    finding = world.add_finding(
        about_kind=mark.kind, about_id=mark.id, about_name=mark.name,
        kind=kind, found=date, group_kind=side.kind, group_id=side.id,
        expedition_id=expedition.id,
        figure_ids=[leader.id] if leader is not None else [],
        before=cat.level_about(before_level) or "об этом не знали ничего",
        gained=list(answers), evidence=_evidence_for(rng, expedition, end),
        trust=round(trust, 2), prime=prime, twist=twist,
        claims=[{"кто": side.name, "год": year,
                 "на чём": cat.CLAIM_BASIS_NAMES[basis]}],
        known_by=[side.id])

    # --- поняли ли, что нашли -------------------------------------------
    if rng.chance(0.30 + 0.25 * (1.0 - truth)):
        finding.wrong = cat.WRONGS_BY_KEY[
            _wrong_for(rng, goal, expedition, mark)].said

    weight = cat.FINDS_BY_KEY[kind].weight * (0.55 + 0.85 * cat.end_good(end))
    if not known_before and not locals_folk:
        weight *= 1.35
    if mark.kind in (cat.T_WONDER, cat.T_DOMINION):
        weight *= 1.2
    finding.weight = max(1, min(5, int(round(weight * 2.3))))
    finding.fruits = [cat.FRUIT_NAMES[key]
                      for key in _fruits_for(rng, goal, finding.weight)
                      if key in cat.FRUIT_NAMES]
    if finding.id not in expedition.findings:
        expedition.findings.append(finding.id)
    if leader is not None:
        leader.notes.append("%d: %s — %s" % (year, kind, mark.name))
    return finding


# ---------------------------------------------------------------------------
# Карта
# ---------------------------------------------------------------------------


def _make_chart(ctx, year: int, rng, expedition, leader, side, mark,
                luck: float):
    """Карта, составленная по итогам похода.

    Точность у неё по параметрам: торговая отлично знает пристани и
    врёт в горах. И у всякой карты сразу названы её ошибки — не потому,
    что составитель плох, а потому, что он отвечал на свой вопрос.
    """
    world = ctx.world
    kind = _chart_kind(rng, expedition, side)
    spec = cat.CHART_KINDS_BY_KEY[kind]
    marks = {}
    for key in cat.CHART_MARKS:
        base = 0.30 + 0.45 * luck
        if key in spec.good:
            base += 0.30
        if key in spec.bad:
            base -= 0.30
        if key == cat.M_POLIT:
            base -= 0.05
        marks[key] = round(max(0.05, min(0.97, base)), 2)
    errors = []
    for key, value in sorted(marks.items()):
        if value < 0.35 and rng.chance(0.6):
            errors.append({"что": key, "замечено": 0})
    date = ctx.date_in(rng, year)
    chart = world.add_chart(
        name=ctx.forge.unique("chart",
                              lambda: texts.chart_name(rng, spec, mark), rng),
        kind=kind, made=date, maker_id=leader.id if leader is not None else "",
        group_kind=side.kind, group_id=side.id, purpose=spec.purpose,
        covers=[mark.region_id] if mark.region_id else [],
        sources=[cat.source_said("probe")], marks=marks, errors=errors,
        turns=[{"что": "составлена", "год": year}])
    if "secret" in side.can and rng.chance(0.2):
        key = rng.choice([item for item, _said in cat.SECRET_WHYS])
        chart.secret = cat.SECRET_NAMES[key]
    return chart


def _chart_kind(rng, expedition, side) -> str:
    group = expedition.goal_group
    by_group = {
        cat.G_LAND: ("sea", "trade", "war", "local"),
        cat.G_WILD: ("peril", "ore", "local"),
        cat.G_OLD: ("ruins", "deep", "ancient"),
        cat.G_FOLK: ("folk", "local", "trade"),
        cat.G_GOODS: ("trade", "ore", "sea"),
        cat.G_WAR: ("war", "lord", "peril"),
    }
    pool = by_group.get(group, ("trade",))
    if side.kind == "folk":
        pool = pool + ("local",)
    return rng.choice(sorted(set(pool)))


# ---------------------------------------------------------------------------
# Встреча двух обществ
# ---------------------------------------------------------------------------


def _shut_why(world, folk, rng) -> str:
    """Отчего этот народ оказался в стороне от всех.

    Затворничество — не отставание: у затворившихся бывает подробнейшее
    знание своей округи и никакого — о мире за хребтом. Поэтому причина
    ищется в мире: горы, льды, война по соседству, мор, обрушенный
    мост, собственное решение.
    """
    region = world.regions.get(folk.cradle_region)
    pool = []
    if region is not None:
        if region.island:
            pool.append(("wall", 2.0))
        if region.terrain in (races_mod.MOUNTAIN, races_mod.UNDERGROUND,
                              races_mod.TUNDRA, races_mod.SWAMP):
            pool.append(("wall", 1.6))
            pool.append(("harsh", 1.4))
        if float(region.savagery or 0.0) > 0.5:
            pool.append(("foes", 1.2))
    if folk.population < 40000:
        pool.append(("few", 1.3))
    for calamity in world.calamities.values():
        if folk.cradle_region in (calamity.region_ids or ()):
            pool.append(("plague", 1.0))
            break
    pool.extend([("choice", 0.8), ("holy", 0.6), ("roads", 0.7),
                 ("hide", 0.5), ("way", 0.9), ("bridge", 0.4),
                 ("ward", 0.4)])
    return cat.SHUT_NAMES[rng.weighted(pool)]


def _meet_outcome(rng, barrier: float, armed: bool, stronger: bool,
                  gifts: bool) -> str:
    """Чем встреча кончилась — по тому, как она шла, а не по жребию."""
    pool = []
    for key, _said, _mood in cat.MEET_ENDS:
        weight = 1.0
        if key in ("swap", "trade", "craft"):
            weight = 1.6 * (1.0 - barrier) + (0.6 if gifts else 0.0)
        elif key == "watch":
            weight = 1.0 + 0.8 * barrier
        elif key == "muddle":
            weight = 0.4 + 1.8 * barrier
        elif key == "fight":
            weight = (0.5 + 1.2 * barrier) * (1.6 if armed else 0.5)
        elif key == "seize":
            weight = (0.7 if stronger else 0.05) * (1.4 if armed else 0.4)
        elif key == "plague":
            weight = 0.35
        elif key == "mix":
            weight = 0.8 * (1.0 - barrier)
        elif key == "ally":
            weight = 0.5 * (1.0 - barrier)
        elif key == "shut":
            weight = 0.6 + 0.6 * barrier
        elif key == "gone":
            weight = 0.12 if stronger else 0.02
        elif key == "between":
            weight = 0.4 * (1.0 - barrier)
        elif key == "faith":
            weight = 0.4
        pool.append((key, max(0.01, weight)))
    return rng.weighted(pool)


def _make_meeting(ctx, year: int, rng, expedition, side, mark, end: str,
                  leader, host=None):
    """Встреча двух обществ — с походом или без него.

    Без похода она случается сама: переселенцы вышли за хребет,
    пастухи дошли до чужого стойбища, обоз сбился с пути. Такие
    встречи важны не меньше снаряжённых: именно так народы узнают друг
    о друге чаще всего.
    """
    world = ctx.world
    if host is None:
        hosts = _locals_of(world, mark)
        host = hosts[0] if hosts else world.folks.get(mark.folk_id)
    if host is None or host.id == side.folk_id:
        return None
    date = ctx.date_in(rng, year)
    roles = set(expedition.roles) if expedition is not None else set()
    gear = set(expedition.gear) if expedition is not None else set()

    # Чем объяснялись.
    ways = []
    if "tongue" in roles or "words" in gear:
        ways.append("learn")
    if "local" in roles:
        ways.append("third")
    if "spells" in gear and rng.chance(0.3):
        ways.append("spell")
    if not ways:
        ways.append(rng.choice(("hands", "draw", "things", "doing")))
    if "trade" in side.can and rng.chance(0.5):
        ways.append("trade")
    # Посредник из третьего народа: если пришедшие уже знают кого-то
    # ещё, толмача ищут у него. Без этого всякая встреча без похода
    # шла на пальцах, и языковой барьер выходил почти у всех.
    if "third" not in ways:
        known_folks = len([record for record
                           in world.knowings_of_group(side.id)
                           if record.about_kind == cat.T_FOLK])
        if known_folks >= 2 and rng.chance(0.45):
            ways.append("third")
    reach = max(cat.SPEECHES_BY_KEY[key].reach for key in ways)
    barrier = round(max(0.0, 1.0 - reach), 2)

    steps = [key for key, _said in cat.MEET_STEPS]
    depth = 7 if end == cat.E_MET else 4
    if barrier > 0.6:
        depth = min(depth, 5)
    steps = steps[:max(3, depth)]

    armed = "guard" in roles or "armour" in gear
    stronger = side.souls > host.population * 3
    outcome = _meet_outcome(rng, barrier, armed, stronger, "gifts" in gear)
    eyes_pool = [("first", 1.4), ("trespass", 1.0 if armed else 0.5),
                 ("return", 0.5), ("omen", 0.5), ("chance", 0.9),
                 ("threat", 1.2 if armed or stronger else 0.4),
                 ("talk", 0.8), ("nothing", 0.6)]
    meeting = world.add_meeting(
        date=date, kind=_meet_kind(rng, expedition, outcome),
        comer_kind=side.kind, comer_id=side.id, host_folk=host.id,
        region_id=mark.region_id, hex_index=mark.hex_index,
        expedition_id=expedition.id if expedition is not None else "",
        starter=side.name, steps=steps,
        speech=[cat.SPEECHES_BY_KEY[key].said for key in ways],
        barrier=barrier,
        read_as=texts.first_read(rng, barrier, host),
        local_eyes=cat.LOCAL_EYES_NAMES[rng.weighted(eyes_pool)],
        shut_why=_shut_why(world, host, rng),
        outcome=cat.MEET_END_NAMES[outcome],
        after=texts.after_meeting(rng, outcome, barrier))
    meeting.versions = texts.meeting_versions(world, meeting, side, host)

    # Оба общества узнаю́т друг о друге — и узнаю́т по-разному.
    guest_mark = Mark(cat.T_FOLK, host.id, host.name, host.cradle_region,
                      -1, 0, 0.35, host.id)
    _note_knowing(ctx, year, side, guest_mark,
                  cat.PARTLY if barrier < 0.5 else cat.FOREIGN, "eyes",
                  aspects={cat.PEOPLE: cat.PARTLY,
                           cat.SPEECH: cat.PARTLY if barrier < 0.4
                           else cat.RUMOUR},
                  trust=0.7, truth=round(0.85 - 0.5 * barrier, 2))
    host_side = Side("folk", host.id, host.name, host.id, host.race_id,
                     {host.cradle_region}, {"people"}, host.population,
                     host.cradle_region)
    comer_mark = Mark(cat.T_FOLK, side.folk_id or side.id, side.name,
                      side.home, -1, 0, 0.35, side.folk_id)
    _note_knowing(ctx, year, host_side, comer_mark, cat.FOREIGN, "eyes",
                  aspects={cat.PEOPLE: cat.FOREIGN}, trust=0.6,
                  truth=round(0.8 - 0.4 * barrier, 2))

    title, text = texts.meeting(rng, world, meeting, side, host, leader)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="folk_meeting",
        title=title, text=text,
        importance=3 if outcome in ("fight", "seize", "plague", "gone")
        else 2,
        actors=[leader.id] if leader is not None else [],
        subjects=[meeting.id, host.id]
        + ([expedition.id] if expedition is not None else []),
        region_id=mark.region_id, race_id=host.race_id)
    return meeting


def _meet_kind(rng, expedition, outcome: str) -> str:
    if outcome in ("fight", "seize", "gone"):
        return cat.C_CLASH
    if outcome in ("trade", "swap"):
        return cat.C_TRADE
    if outcome == "ally":
        return cat.C_PACT
    if expedition is not None and "envoy" in expedition.roles:
        return cat.C_EMBASSY
    if outcome == "watch":
        return cat.C_WATCH
    if outcome in ("mix", "between"):
        return cat.C_STEADY
    return cat.C_PRIVATE


# ---------------------------------------------------------------------------
# Освоение
# ---------------------------------------------------------------------------


def _local_use(world, region_id: str, rng) -> tuple:
    """Кто этой землёй уже пользуется — и как.

    Отсутствие построек не значит отсутствия прав: по той земле ходят
    на охоту, пасут скот, хоронят, идут перегоном. Пустая земля бывает,
    но реже, чем кажется пришедшим.
    """
    if not region_id:
        return "none", ""
    for hold in world.dominions.values():
        if hold.alive and region_id in (hold.region_ids or ()):
            return "lord", ""
    dwellers = []
    for settlement_id in world.active_settlements:
        town = world.settlements[settlement_id]
        if town.region_id == region_id and town.folk_id:
            dwellers.append(town.folk_id)
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.region_id == region_id and tribe.folk_id:
            dwellers.append(tribe.folk_id)
    if dwellers:
        folk_id = sorted(dwellers)[0]
        pool = [("graze", 1.2), ("hunt", 1.2), ("holy", 0.7),
                ("graves", 0.7), ("gather", 0.9), ("drive", 0.8),
                ("shared", 0.6)]
        return rng.weighted(pool), folk_id
    pool = [("none", 2.0), ("hunt", 0.8), ("drive", 0.5), ("holy", 0.4)]
    return rng.weighted(pool), ""


def _start_settling(ctx, year: int, rng, side, mark, expedition,
                    forced: str = ""):
    world = ctx.world
    region = world.regions.get(mark.region_id)
    if region is None or region.drowned:
        return None
    use_key, folk_id = _local_use(world, region.id, rng)
    kind = forced
    if not kind:
        pool = []
        for hold in cat.HOLDS:
            weight = 1.0
            if hold.needs and not side.can.issuperset(set(hold.needs)):
                weight *= 0.3
            if hold.key in (cat.H_JOINED, cat.H_FORT) and side.kind != "polity":
                weight *= 0.2
            if hold.key == cat.H_SHARED and not folk_id:
                weight = 0.0
            if hold.key == cat.H_GUEST and not folk_id:
                weight = 0.0
            if hold.key == cat.H_MINE and expedition is not None \
                    and expedition.goal in ("ore", "vein", "deep"):
                weight *= 2.0
            if hold.key == cat.H_PORT and expedition is not None \
                    and expedition.goal == "harbour":
                weight *= 2.2
            pool.append((hold.key, max(0.01, weight)))
        kind = rng.weighted(pool)
    date = ctx.date_in(rng, year)
    settlers = rng.randint(12, 60)
    if kind in (cat.H_SETTLE, cat.H_COLONY, cat.H_JOINED):
        settlers = rng.randint(80, 600)
    settling = world.add_settling(
        kind=kind, started=date, host_kind=side.kind, host_id=side.id,
        region_id=region.id,
        hex_index=mark.hex_index if mark.hex_index is not None else -1,
        purpose=texts.hold_purpose(rng, kind, expedition),
        settlers=settlers, locals_use=cat.LOCAL_USE_NAMES[use_key],
        locals_folk=folk_id,
        locals_answer=texts.locals_answer(
            rng, use_key, kind,
            world.folks.get(folk_id) if folk_id else None),
        supply=texts.supply_line(rng, world, side, region),
        expedition_id=expedition.id if expedition is not None else "")
    title, text = texts.settling(rng, world, settling, side, region)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="settling_start",
        title=title, text=text, importance=2,
        subjects=[settling.id] + ([side.id] if side.kind == "polity" else []),
        region_id=region.id, race_id=side.race_id)
    return settling


def _hold_life(ctx, year: int, rng) -> None:
    """Что сталось с теми, кто остался на новой земле."""
    world = ctx.world
    for settling in sorted(world.settlings.values(), key=lambda item: item.id):
        if not settling.alive or settling.started is None:
            continue
        age = year - settling.started.year
        if age < 10:
            continue
        spec = cat.HOLDS_BY_KEY.get(settling.kind)
        lasting = spec.lasting if spec is not None else 0.4
        region = world.regions.get(settling.region_id)
        risk = float(region.risk or 0.0) if region is not None else 0.3
        hostile = settling.locals_answer.startswith("их не потерпели") \
            or "выжил" in settling.locals_answer
        fail = 0.10 + 0.20 * (1.0 - lasting) + 0.12 * risk \
            + (0.12 if hostile else 0.0) + 0.10 * ctx.gloom(settling.region_id)
        take = 0.14 + 0.34 * lasting
        if age > 60:
            fail += 0.1
            take += 0.1
        roll = rng.random()
        if roll < fail:
            key = rng.choice([item for item, _said in cat.HOLD_FAILS])
            settling.fail_why = cat.HOLD_FAIL_NAMES[key]
            settling.result = "не прижилось"
            settling.ended = ctx.date_in(rng, year)
            title, text = texts.settling_failed(rng, world, settling)
            world.add_event(
                date=settling.ended, era_index=world.era_index_at(year),
                kind="settling_end", title=title, text=text, importance=2,
                subjects=[settling.id], region_id=settling.region_id)
        elif roll < fail + take:
            _settling_rooted(ctx, year, rng, settling)


def _settling_rooted(ctx, year: int, rng, settling) -> None:
    """Двор прижился — и дальше живёт как всякое поселение мира."""
    world = ctx.world
    settling.ended = ctx.date_in(rng, year)
    fate_pool = [("small", 1.6), ("torg", 0.8), ("town", 0.7), ("mixed", 0.7),
                 ("free", 0.4), ("war", 0.3), ("taken", 0.3)]
    if settling.kind in (cat.H_CAMP, cat.H_STATION, cat.H_BASE):
        fate_pool = [("small", 1.8), ("gone", 1.0), ("mixed", 0.5)]
    fate = rng.weighted(fate_pool)
    settling.result = cat.HOLD_FATE_NAMES[fate]

    lasting = settling.kind in (cat.H_POST, cat.H_PORT, cat.H_FORT,
                                cat.H_SETTLE, cat.H_MINE, cat.H_COLONY,
                                cat.H_JOINED, cat.H_SHARED, cat.H_MISSION)
    if lasting and fate in ("small", "torg", "town", "mixed", "free",
                            "taken", "war"):
        _plant(ctx, year, rng, settling)
    title, text = texts.settling_rooted(rng, world, settling)
    world.add_event(
        date=settling.ended, era_index=world.era_index_at(year),
        kind="settling_end", title=title, text=text,
        importance=3 if fate in ("town", "free") else 2,
        subjects=[settling.id]
        + ([settling.settlement_id] if settling.settlement_id else []),
        region_id=settling.region_id)


def _plant(ctx, year: int, rng, settling) -> None:
    """Из удавшегося двора выходит настоящее поселение.

    Делается это тем же способом, что и заморская колония
    (`systems/exploration._plant_colony`): поселение должно войти в мир
    как всякое другое — с кривой людности, ступенью по людности и
    записью владения, — иначе разбор мира найдёт город, которого нет ни
    в одной переписи.
    """
    world = ctx.world
    region = world.regions.get(settling.region_id)
    if region is None or region.drowned:
        return
    polity = world.polities.get(settling.host_id) \
        if settling.host_kind == "polity" else None
    race_id = polity.race_id if polity is not None else ""
    if not race_id:
        folk = world.folks.get(settling.host_id)
        race_id = folk.race_id if folk is not None else ""
    race = races_mod.RACES_BY_ID.get(race_id)
    if race is None or not race.settles:
        return
    date = settling.ended or ctx.date_in(rng, year)
    sex = "f" if rng.chance(0.4) else "m"
    founder = ctx.make_figure(
        rng, race, year, role="основатель", region_id=region.id,
        title=ctx.title_for(race, "founder", sex), sex=sex)
    hex_index = settling.hex_index
    if hex_index is None or hex_index < 0:
        hex_index = ctx.map.place(region.id, rng, kind="city") \
            if ctx.map else -1
    settlement = world.add_settlement(
        name=ctx.forge.settlement(rng, race),
        kind="Колония", race_id=race.id, founded=date,
        founder_id=founder.id, region_id=region.id,
        population=max(40, int(settling.settlers * rng.uniform(0.6, 1.4))),
        polity_id=polity.id if polity is not None else "",
        hex_index=hex_index,
        folk_id=settling.host_id if settling.host_kind == "folk" else "")
    if ctx.map is not None and hex_index >= 0:
        ctx.map.claim(hex_index, settlement.id)
    founder.home_id = settlement.id
    settling.settlement_id = settlement.id
    if polity is not None:
        world.hold_settlement(polity, settlement.id, year)
        if region.id not in polity.region_ids:
            polity.region_ids.append(region.id)
    world.refresh_populations()


# ---------------------------------------------------------------------------
# Исследователь: добавка к биографии, а не вторая биография
# ---------------------------------------------------------------------------


def _profile(ctx, year: int, rng, expedition, leader, side, finding, chart,
             goal) -> None:
    world = ctx.world
    record = world.explorer_of(leader.id)
    trade = _trade_for(rng, goal)
    if record is None:
        drives = [cat.DRIVE_NAMES[rng.choice([key for key, _said
                                              in cat.DRIVES])]]
        if rng.chance(0.3):
            more = cat.DRIVE_NAMES[rng.choice([key for key, _said
                                               in cat.DRIVES])]
            if more not in drives:
                drives.append(more)
        record = world.add_explorer(
            figure_id=leader.id, trades=[trade], drives=drives,
            patrons=[side.name] if side is not None else [],
            goal=texts.personal_goal(rng, goal, expedition))
    elif trade not in record.trades:
        record.trades.append(trade)
    if expedition.id not in record.expeditions:
        record.expeditions.append(expedition.id)
    if finding is not None and finding.id not in record.findings:
        record.findings.append(finding.id)
    if chart is not None and chart.id not in record.charts:
        record.charts.append(chart.id)
    if side is not None and side.name not in record.patrons:
        record.patrons.append(side.name)
    tongue = world.tongues.get(
        world.folks.get(leader.folk_id).tongue_id
        if leader.folk_id and world.folks.get(leader.folk_id) else "")
    if tongue is not None and tongue.name not in record.tongues:
        record.tongues.append(tongue.name)

    # Признание: своё у каждого народа. Тот, кто у пославшей державы
    # «первый, кто дошёл», у тех, к кому он пришёл, бывает чужаком,
    # которого пустили и пожалели.
    if finding is not None:
        if side is not None:
            word = "first" if finding.prime.get(cat.P_FAME) == leader.name \
                else "useful"
            record.fame[side.id] = cat.FAME_WORD_NAMES[word]
        for folk in _locals_of(world, _mark_by_id(
                world, finding.about_kind, finding.about_id,
                finding.about_name)):
            pool = [("stranger", 1.2), ("thief", 0.6), ("useful", 0.6),
                    ("blamed", 0.5), ("forgotten", 0.9)]
            record.fame[folk.id] = cat.FAME_WORD_NAMES[rng.weighted(pool)]
        record.credit = "признан" if finding.prime.get(cat.P_FAME) \
            == leader.name else "признание досталось не ему"
    if expedition.result in (cat.E_GONE, cat.E_DARK):
        record.unsolved = "ушёл в %d году и не вернулся" % \
            expedition.start.year
        record.credit = record.credit or "судьба неизвестна"


# ---------------------------------------------------------------------------
# Жизнь карт
# ---------------------------------------------------------------------------


def _chart_life(ctx, year: int, rng) -> None:
    """Карты переписывают, исправляют, прячут и теряют.

    Старая карта при этом не исчезает от появления новой: она лежит в
    хранилище и продолжает быть основанием ошибочных представлений —
    по ней ходят ещё век после того, как проход на ней занесло.
    """
    world = ctx.world
    if not world.charts:
        return
    if not rng.chance(CHART_TURN_CHANCE * ctx.density()):
        return
    pool = []
    for chart in world.charts.values():
        if chart.made is None:
            continue
        age = year - chart.made.year
        if age <= 0:
            continue
        pool.append((chart, 1.0 + min(3.0, age / 400.0)))
    if not pool:
        return
    chart = rng.weighted(pool)
    age = year - chart.made.year
    keys = []
    if chart.alive:
        keys.extend([("copy", 1.2), ("fix", 1.0), ("add", 0.9),
                     ("rot", 1.4 if age > 150 else 0.4),
                     ("secret", 0.4), ("steal", 0.5),
                     ("burn", 0.5 if age > 200 else 0.15),
                     ("doubt", 0.4)])
    else:
        keys.append(("found", 1.0))
    key = rng.weighted(keys)
    chart.turns.append({"что": cat.CHART_TURN_NAMES[key], "год": year})
    if key == "copy":
        chart.spread += rng.randint(1, 3)
    elif key == "fix":
        for mark in sorted(chart.marks):
            if chart.marks[mark] < 0.6:
                chart.marks[mark] = round(min(0.95, chart.marks[mark] + 0.2), 2)
                break
        chart.errors = [row for row in chart.errors
                        if row.get("замечено")] or []
    elif key == "add":
        chart.sources.append(cat.source_said("walker"))
    elif key == "rot":
        chart.marks[cat.M_POLIT] = round(
            max(0.05, chart.marks.get(cat.M_POLIT, 0.4) - 0.25), 2)
        if not any(row.get("что") == cat.M_POLIT for row in chart.errors):
            chart.errors.append({"что": cat.M_POLIT, "замечено": 0})
    elif key == "secret":
        chart.secret = cat.SECRET_NAMES[
            rng.choice([item for item, _said in cat.SECRET_WHYS])]
    elif key == "steal":
        chart.spread += 1
        chart.notes.append("%d: список объявился у соседей" % year)
    elif key == "burn":
        chart.lost_year = year
    elif key == "doubt":
        chart.notes.append("%d: карту объявили подделкой" % year)
    elif key == "found":
        chart.lost_year = 0
        chart.notes.append("%d: карту нашли заново" % year)


# ---------------------------------------------------------------------------
# Как сведения расходятся — и во что превращаются по дороге
# ---------------------------------------------------------------------------


CHANNEL_SOURCE = {
    "walkers": "walker", "caravan": "trade", "ships": "trade",
    "envoy": "envoy", "movers": "walker", "hired": "walker",
    "pilgrim": "tale", "scribes": "archive", "charts": "chart",
    "books": "archive", "spies": "scout", "between": "locals",
    "spell": "envoy",
}


def _channels_between(world, holder, learner, record) -> list:
    """Чем эти двое вообще связаны. Нет связи — нет и вести."""
    out = []
    a = world.polities.get(holder.id) if holder.kind == "polity" else None
    b = world.polities.get(learner.id) if learner.kind == "polity" else None
    if a is not None and b is not None:
        for route_id in a.routes:
            route = world.routes.get(route_id)
            if route is None:
                continue
            if b.id in (route.seller_id, route.buyer_id):
                out.append(("ships" if route.by_sea else "caravan", 1.8))
                break
        for pact_id in a.pact_ids:
            pact = world.pacts.get(pact_id)
            if pact is None:
                continue
            if b.id in (getattr(pact, "first_id", ""),
                        getattr(pact, "second_id", "")):
                out.append(("envoy", 1.3))
                break
        if set(a.war_ids).intersection(b.war_ids):
            out.append(("spies", 1.0))
    if holder.regions.intersection(learner.regions):
        out.append(("between", 1.4))
    else:
        for region_id in sorted(holder.regions)[:4]:
            region = world.regions.get(region_id)
            if region is None:
                continue
            if learner.regions.intersection(region.neighbors):
                out.append(("walkers", 1.1))
                break
    for migration in world.migrations.values():
        if migration.from_region in holder.regions \
                and migration.to_region in learner.regions:
            out.append(("movers", 0.9))
            break
    if "letters" in holder.can and "letters" in learner.can:
        out.append(("books", 0.5))
        out.append(("scribes", 0.6))
    for chart in world.charts_of(holder.id):
        # Списками уходит не всякая карта, а разошедшаяся: чтобы весть
        # дошла картой, карта должна была выйти за хранилище.
        if chart.spread >= 3:
            out.append(("charts", 0.8))
            break
    return out


def _spread(ctx, year: int, rng, sides, by_id) -> None:
    """Весть идёт по каналу — и по дороге усыхает.

    Без этой части всякое открытие к концу века знал бы весь мир, и мир
    перестал бы быть большим. Поэтому вестей за такт — одна-две, и
    каждая идёт только туда, куда есть кому её донести.
    """
    world = ctx.world
    if len(world.knowings) >= KNOWING_CAP:
        return
    if not rng.chance(SPREAD_CHANCE * ctx.density()):
        return
    # Тайна не вечна: дорогу, которую один дом держал при себе сто лет,
    # однажды выдаёт кормчий, перешедший к сопернику. Поэтому
    # секретность — состояние, а не свойство знания.
    hidden = [record for record in world.knowings.values()
              if record.access == "тайна" and record.since is not None
              and year - record.since.year >= 100]
    if hidden and rng.chance(0.10):
        leaked = hidden[rng.randint(0, len(hidden) - 1)]
        leaked.access = "открыто"
        # Причину тайны при этом не вычёркиваем: «держали в тайне и
        # выдали» — такая же часть истории знания, как «держат до сих
        # пор», и по ней потом видно, что тайны в этом мире были.
        leaked.notes.append("%d: тайна вышла наружу — %s"
                            % (year, rng.choice((
                                "кормчий перешёл к соперникам",
                                "список карты выкрали",
                                "о ней проговорились на торгу",
                                "держава пала, и бумаги разошлись"))))

    rows = [record for record in world.knowings.values()
            if record.known and record.access == "открыто"
            and cat.level_depth(record.level) >= 0.45]
    if not rows:
        return
    by_side = {side.id: side for side in sides}
    for _step in range(SPREAD_PER_TICK):
        record = rows[rng.randint(0, len(rows) - 1)]
        holder = by_side.get(record.group_id)
        mark = by_id.get(record.about_id)
        if holder is None or mark is None:
            continue
        pool = []
        for learner in sides:
            if learner.id == holder.id:
                continue
            if world.knows(learner.id, record.about_id):
                continue
            links = _channels_between(world, holder, learner, record)
            if not links:
                continue
            key, weight = max(links, key=lambda row: row[1])
            channel = cat.CHANNELS_BY_KEY[key]
            pool.append(((learner, channel), weight * channel.speed))
        if not pool:
            continue
        learner, channel = rng.weighted(pool)
        level = cat.FOREIGN if channel.truth >= 0.6 else cat.RUMOUR
        trust = round(record.trust * channel.truth, 2)
        truth = round(record.truth * channel.truth, 2)
        aspects = {}
        for key, value in sorted(record.aspects.items()):
            if cat.level_depth(value) >= 0.5 and rng.chance(channel.truth):
                aspects[key] = level
        new = _note_knowing(
            ctx, year, learner, mark, level,
            CHANNEL_SOURCE.get(channel.key, "walker"), aspects=aspects,
            trust=trust, truth=truth, from_id=holder.id)
        if new is None:
            continue
        new.notes.append("%d: дошло %s от %s"
                         % (year, channel.said, holder.name))
        if rng.chance(WARP_CHANCE * (1.0 - channel.truth) * 2.0):
            key = rng.choice([item for item, _said, _fix in cat.WARPS])
            new.warp = key
            new.muddle = cat.WARP_NAMES[key]
            new.truth = round(max(0.05, new.truth - 0.25), 2)
            if key == "beasts" and mark.kind == cat.T_FOLK:
                new.notes.append(
                    "%d: о живущих там рассказывают как о нелюдях" % year)


def _unwarp(ctx, year: int, rng, sides) -> None:
    """Независимое подтверждение выправляет искажённую весть.

    Рассказ о нелюдях перестаёт быть рассказом о нелюдях не сам собой:
    кто-то должен прийти с теми же сведениями другой дорогой. Поэтому
    тут нужны двое — тот, у кого весть искажена, и тот, кто знает то же
    самое вернее, — и между ними должна быть связь.
    """
    world = ctx.world
    rows = [record for record in world.knowings.values()
            if record.muddle and record.since is not None
            and year - record.since.year >= 60]
    if not rows or not rng.chance(0.35 * ctx.density()):
        return
    by_side = {side.id: side for side in sides}
    record = rows[rng.randint(0, len(rows) - 1)]
    holder = by_side.get(record.group_id)
    if holder is None:
        return
    for other in world.knowings_about(record.about_id):
        if other.group_id == record.group_id:
            continue
        if other.truth < record.truth + 0.2:
            continue
        side = by_side.get(other.group_id)
        if side is None:
            continue
        if not _channels_between(world, side, holder, other):
            continue
        record.notes.append(
            "%d: %s — то же самое пришло от %s"
            % (year, cat.WARP_FIXES.get(record.warp,
                                        "сведения проверили заново"),
               side.name))
        record.muddle = ""
        record.warp = ""
        record.truth = round(min(0.95, (record.truth + other.truth) / 2.0), 2)
        record.trust = round(min(0.95, record.trust + 0.1), 2)
        return


def _forget(ctx, year: int, rng) -> None:
    """Ответ, который был, снова становится вопросом.

    Это главный источник повторных открытий: через три века туда идут
    опять, не зная о прежних, — и для них это новое знание, для мира
    второе, а для позднейшего книжника, нашедшего старый свод, —
    возвращение утраченного.
    """
    world = ctx.world
    if not world.knowings:
        return
    if not rng.chance(FORGET_CHANCE * ctx.density()):
        return
    rows = []
    for record in world.knowings.values():
        if not record.known or record.level == cat.LOCAL:
            continue
        if record.since is None or year - record.since.year < FORGET_AGE:
            continue
        if year - record.confirmed < 120:
            continue
        rows.append(record)
    if not rows:
        return
    record = rows[rng.randint(0, len(rows) - 1)]
    why = _loss_why(world, record, year, rng)
    record.lost_year = year
    record.lost_why = cat.LOSS_NAMES[why]
    kept = rng.weighted([("mouth", 1.2), ("name", 1.0), ("rite", 0.6),
                         ("copy", 0.8), ("stone", 0.6), ("none", 1.0)])
    record.kept = cat.LOSS_SURVIVAL_NAMES[kept]
    record.notes.append("%d: знание потеряно — %s" % (year, record.lost_why))
    if cat.level_depth(record.level) >= 0.55 and rng.chance(0.45):
        title, text = texts.knowledge_lost(rng, world, record)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="knowing_lost", title=title, text=text, importance=2,
            subjects=[record.id, record.about_id],
            region_id=_region_of_record(world, record))


def _loss_why(world, record, year: int, rng) -> str:
    polity = world.polities.get(record.group_id) \
        if record.group_kind == "polity" else None
    folk = world.folks.get(record.group_id) \
        if record.group_kind == "folk" else None
    pool = []
    if polity is not None and polity.status != ACTIVE:
        pool.append(("fell", 2.5))
    if folk is not None and folk.status != ACTIVE:
        pool.append(("folk", 2.5))
    for calamity in world.calamities.values():
        if calamity.start is None or calamity.start.year > year:
            continue
        if calamity.start.year < year - 200:
            continue
        if record.about_id in (calamity.region_ids or ()):
            pool.append(("burnt", 1.4))
            break
    if record.about_kind == cat.T_ROUTE:
        pool.append(("road", 1.6))
        pool.append(("trade", 1.2))
    pool.extend([("dead", 1.4), ("tongue", 0.7), ("charts", 0.6),
                 ("ban", 0.5)])
    return rng.weighted(pool)


def _region_of_record(world, record) -> str:
    if record.about_kind == cat.T_REGION:
        return record.about_id
    for table in ("sites", "scars", "wonders"):
        item = getattr(world, table, {}).get(record.about_id)
        if item is not None:
            return getattr(item, "region_id", "")
    folk = world.folks.get(record.about_id)
    if folk is not None:
        return folk.cradle_region
    return ""


# ---------------------------------------------------------------------------
# Встречи без походов
# ---------------------------------------------------------------------------


def _meet_outside(ctx, year: int, rng, sides, lands) -> None:
    """Народы узнаю́т друг о друге и без снаряжённых отрядов."""
    world = ctx.world
    if not rng.chance(MEET_CHANCE * ctx.density()):
        return
    quiet = []
    for folk in world.folks.values():
        if folk.status != ACTIVE:
            continue
        seen = len([record for record in world.knowings_about(folk.id)
                    if record.group_id != folk.id])
        if seen >= 2:
            continue
        quiet.append((folk, 1.0 + (1.0 if seen == 0 else 0.0)))
    if not quiet:
        return
    host = rng.weighted(quiet)
    pool = []
    home = world.regions.get(host.cradle_region)
    for side in sides:
        if side.folk_id == host.id or side.id == host.id:
            continue
        if world.knows(side.id, host.id):
            continue
        near = 0.0
        if home is not None and side.regions.intersection(home.neighbors):
            near = 1.2
        if home is not None and home.id in side.regions:
            near = 1.6
        if not near:
            continue
        pool.append((side, near * (0.6 + min(2.0, side.souls / 200000.0))))
    if not pool:
        return
    side = rng.weighted(pool)
    mark = Mark(cat.T_FOLK, host.id, host.name, host.cradle_region, -1, 0,
                0.35, host.id)
    _make_meeting(ctx, year, rng, None, side, mark, cat.E_MET, None,
                  host=host)


# ---------------------------------------------------------------------------
# Споры о первенстве
# ---------------------------------------------------------------------------


def _credit(ctx, year: int, rng) -> None:
    """О том, кто был первым, спорят — и спор переживает спорящих."""
    world = ctx.world
    if not world.findings:
        return
    if not rng.chance(CREDIT_CHANCE * ctx.density()):
        return
    rows = [item for item in world.findings.values()
            if item.found is not None and year - item.found.year >= 60]
    if not rows:
        return
    finding = rows[rng.randint(0, len(rows) - 1)]
    keys = [("claim", 1.2), ("crown", 0.8), ("fix", 1.0), ("spread", 1.4),
            ("guide", 0.5)]
    if finding.wrong and not finding.wrong_fixed:
        keys.append(("wrong", 1.6))
    key = rng.weighted(keys)

    if key == "claim":
        others = [record.group_id for record in
                  world.knowings_about(finding.about_id)
                  if record.group_id != finding.group_id
                  and record.group_kind == "polity"]
        if not others:
            return
        claimer_id = sorted(others)[rng.randint(0, len(others) - 1)]
        claimer = world.polities.get(claimer_id)
        if claimer is None:
            return
        basis = rng.choice([item for item, _said in cat.CLAIM_BASIS])
        finding.claims.append({"кто": claimer.full_name, "год": year,
                               "на чём": cat.CLAIM_BASIS_NAMES[basis]})
        title, text = texts.credit_row(rng, world, finding, claimer)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="first_row", title=title, text=text, importance=2,
            subjects=[finding.id, claimer.id],
            region_id=_region_of_record(world, finding))
    elif key == "crown":
        holder = world.polities.get(finding.group_id)
        if holder is None:
            return
        finding.prime[cat.P_FAME] = holder.full_name
        finding.twist = cat.CREDIT_NAMES["crown"]
        finding.notes.append("%d: заслугу записала на себя держава" % year)
    elif key == "fix":
        finding.notes.append("%d: свидетельство сверили заново" % year)
        finding.trust = round(min(0.95, finding.trust + 0.1), 2)
    elif key == "spread":
        rows = [record.group_id for record in
                world.knowings_about(finding.about_id)]
        for group_id in sorted(set(rows)):
            if group_id not in finding.known_by:
                finding.known_by.append(group_id)
                break
    elif key == "guide":
        if cat.CREDIT_NAMES["guide"] in finding.twist:
            finding.notes.append(
                "%d: имя проводника наконец записали — поздно и с ошибкой"
                % year)
    elif key == "wrong":
        finding.wrong_fixed = year
        finding.wrong_by = rng.choice(
            ("позднейший поход", "книжник, сверивший записи",
             "раскоп на том же месте", "местные, которых наконец спросили"))
        for row in cat.WRONGS:
            if row.said == finding.wrong:
                finding.notes.append("%d: %s" % (year, row.fix))
                break
        title, text = texts.wrong_fixed(rng, world, finding)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="knowing_fixed", title=title, text=text, importance=2,
            subjects=[finding.id, finding.about_id],
            region_id=_region_of_record(world, finding))


# ---------------------------------------------------------------------------
# Старые походы за море: знание от них тоже остаётся
# ---------------------------------------------------------------------------


def landfall(ctx, expedition, region, leader, year: int) -> None:
    """Поход за море нашёл землю — запишем, чем это стало для знания.

    Старая система открытия заморских земель (`systems/exploration.py`)
    отвечает на вопрос «стала ли земля досягаема». Этот вызов отвечает
    на другой: кто теперь о ней знает, что именно знает, кому это
    зачтётся и жил ли там кто-нибудь до прихода корабля. Без него
    выходило бы, что земля, на которой три тысячи лет живут эльфы,
    «открыта» в тот год, когда к ней подошёл чужой парус.
    """
    world = ctx.world
    if region is None:
        return
    rng = ctx.rng("knowing", "landfall", expedition.id)
    side = _side_by_id(world, "polity" if expedition.polity_id else "folk",
                       expedition.polity_id
                       or (leader.folk_id if leader is not None else ""),
                       year)
    if side is None:
        folk = world.folks.get(leader.folk_id if leader is not None else "")
        if folk is None:
            return
        side = Side("folk", folk.id, folk.name, folk.id, folk.race_id,
                    {folk.cradle_region}, {"people"}, folk.population,
                    folk.cradle_region)
    mark = Mark(cat.T_REGION, region.id, region.name, region.id,
                region.center_hex)
    locals_folk = _locals_of(world, mark)
    date = expedition.end or ctx.date_in(rng, year)

    _note_knowing(ctx, year, side, mark, cat.VISITED, "probe",
                  aspects=_fill(cat.VISITED, (cat.EXIST, cat.WAY,
                                              cat.BOUNDS)),
                  trust=0.8, truth=0.75)
    prime = {}
    leader_name = leader.name if leader is not None else "неизвестный"
    if locals_folk:
        prime[cat.P_FACT] = "народ по имени %s — они тут жили" \
            % locals_folk[0].name
    else:
        prime[cat.P_FACT] = leader_name
    prime[cat.P_WRIT] = leader_name
    prime[cat.P_FAME] = leader_name
    finding = world.add_finding(
        about_kind=cat.T_REGION, about_id=region.id, about_name=region.name,
        kind=cat.F_MET if locals_folk else cat.F_FOOT, found=date,
        group_kind=side.kind, group_id=side.id, expedition_id=expedition.id,
        figure_ids=[leader.id] if leader is not None else [],
        before="об этой земле не знали ничего",
        gained=[cat.EXIST, cat.WAY], evidence=landlore.RECORD, trust=0.8,
        prime=prime,
        claims=[{"кто": side.name, "год": year,
                 "на чём": cat.CLAIM_BASIS_NAMES["crown"]}],
        known_by=[side.id], weight=4 if not locals_folk else 3,
        fruits=[cat.FRUIT_NAMES["chart"], cat.FRUIT_NAMES["way"]])
    if finding.id not in expedition.findings:
        expedition.findings.append(finding.id)
    if locals_folk and rng.chance(0.7):
        _make_meeting(ctx, year, rng, expedition, side, mark, cat.E_MET,
                      leader, host=locals_folk[0])
    if leader is not None and rng.chance(0.8):
        goal = cat.GOALS_BY_KEY["shore"]
        _profile(ctx, year, rng, expedition, leader, side, finding, None,
                 goal)


# ---------------------------------------------------------------------------
# Узлы для былей
# ---------------------------------------------------------------------------


def story_nodes(world, year: int) -> list:
    """То из познания мира, из чего прямо сейчас может вырасти быль.

    Узлов тут мало нарочно: не всякая пропавшая экспедиция обязана быть
    найдена, и не всякая ошибка на карте — приключение. Берутся три
    случая, в которых уже есть вопрос без ответа: отряд, не пришедший
    назад; первенство, о котором спорят две державы, когда живущие там
    помнят иначе; и карта, по которой ходят век, хотя проход на ней
    закрыт.
    """
    rows = []
    for expedition in sorted(world.expeditions.values(),
                             key=lambda item: item.id):
        if expedition.result not in (cat.E_GONE, cat.E_DARK):
            continue
        if expedition.end is None or year - expedition.end.year < STORY_AGE:
            continue
        rows.append((
            "пропавший поход",
            "поход по имени «%s» ушёл в %d году к %s и не вернулся"
            % (expedition.name, expedition.start.year,
               texts.named(expedition.aim_kind,
                           expedition.aim_name or expedition.target_name,
                           "dat")
               if (expedition.aim_name or expedition.target_name)
               else "неназванной цели"),
            expedition, expedition.aim_id or expedition.target_region, 1.3))
    for finding in sorted(world.findings.values(), key=lambda item: item.id):
        if finding.found is None or year - finding.found.year < STORY_AGE:
            continue
        if len(finding.claims) >= 2:
            rows.append((
                "спор о первенстве",
                "о том, кто первым дошёл до %s, спорят: %s"
                % (texts.named(finding.about_kind, finding.about_name,
                               "gen"),
                   " и ".join(str(row.get("кто")) for row in finding.claims[:2])),
                finding, _region_of_record(world, finding), 1.1))
        elif finding.wrong and not finding.wrong_fixed:
            rows.append((
                "ошибка в карте",
                "о том, что такое %s, думают неверно: %s"
                % (texts.named(finding.about_kind, finding.about_name),
                   finding.wrong),
                finding, _region_of_record(world, finding), 1.0))
    for chart in sorted(world.charts.values(), key=lambda item: item.id):
        if chart.made is None or year - chart.made.year < 150:
            continue
        if chart.errors and chart.spread >= 3 and chart.alive:
            rows.append((
                "ошибка в карте",
                "по карте «%s» ходят до сих пор, хотя в ней врёт %s"
                % (chart.name, chart.errors[0].get("что", "многое")),
                chart, (chart.covers or [""])[0], 1.0))
    return rows
