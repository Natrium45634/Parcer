# -*- coding: utf-8 -*-
"""Были: как мир сам рассказывает свои маленькие истории.

Главное здесь — не «придумать приключение», а **найти историю, которая
естественным образом могла случиться в этом мире**. Поэтому начинается
всё не с сюжета, а с поиска исторического узла: следа, который мир
оставил и забыл.

    погибший город → руины → местное предание → монета не той державы
    → кто-то замечает несовпадение → быль

и наоборот:

    ссора из-за межи → удар → месть → вмешалась родня → волнение в
    городе → это попало в летопись

Вверх и вниз — одна система масштаба.

Устройство. Раз в десять лет движок перебирает узлы (`_nodes`), взвешивает
их по месту, эпохе и тому, чего давно не рассказывали, выбирает костяк
(`localstory.SHAPES`), набирает людей из живых обитателей округи —
пахарей, кузнецов, писцов, отставных солдат, а не государей, — и
разводит дело по актам. Видимое и скрытое хранятся врозь: люди считают
одно, было другое, подсказки ведут к правде, ложные следы — мимо.
Поворот разрешается только тот, который уже подготовлен подсказкой.

Девять из десяти былей не спасают мир, и это не недоработка, а условие:
если каждая вторая история будет про древнее зло, живого мира не
получится. Эпичность держится долями (`EPICITY_SHARE`) и антиповтором —
редкий костяк со временем получает больше шансов, заезженный меньше.
"""

from __future__ import annotations

from .. import history
from .. import localstory as cat
from .. import lore as lore_cat
from .. import narrative_local as texts
from .. import narrative_lore as lore_texts
from .. import races as races_mod
from .. import sites as sites_mod
from ..models import RUINED

STORY_RATE = 0.55          # шанс, что за десятилетний такт найдётся быль
MAX_PER_UPKEEP = 2         # больше двух за раз мир не рассказывает
# Сколько находок одного вида берётся в жеребьёвку. Умерших с
# именем в мире тысячи, а закрывшихся трактов десяток: без
# уравнивания о мёртвых рассказывалось бы вдесятеро чаще.
PER_KIND = 30
ECHO_MIN_AGE = 25          # эхо должно отстояться: свежее — это ещё не эхо
LEGEND_FROM = 3            # с какой эпичности быль может стать преданием
LEGEND_DELAY = 60          # и через сколько лет: при свидетелях песни нет
LEGEND_FORGET = 420        # позже о ней уже не поют, а забывают
SONG_RATE = 0.5            # не всякая громкая быль доживает до песни


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.active_settlements:
        return
    rng = ctx.rng("stories", year)
    told = 0
    for _ in range(MAX_PER_UPKEEP):
        if not rng.chance(STORY_RATE * (period / 10.0) * ctx.density()):
            break
        node = _pick_node(ctx, rng, year)
        if node is None:
            break
        if _tell(ctx, rng, year, node):
            told += 1
    if told:
        world.story_marks["всего"] = world.story_marks.get("всего", 0) + told
    _grow_legend(ctx, year)


# ---------------------------------------------------------------------------
# Узел: след, который мир оставил и забыл
# ---------------------------------------------------------------------------

class Node:
    """Исторический узел: откуда тянется быль."""

    __slots__ = ("kind", "what", "year", "ref", "region_id",
                 "settlement_id", "site_id", "weight")

    def __init__(self, kind, what, year, ref="", region_id="",
                 settlement_id="", site_id="", weight=1.0):
        self.kind = kind
        self.what = what          # одной строкой: что это было
        self.year = int(year)
        self.ref = ref            # id сущности мира, если она есть
        self.region_id = region_id
        self.settlement_id = settlement_id
        self.site_id = site_id
        self.weight = float(weight)


def _nodes(ctx, year: int) -> list:
    """Всё, из чего в этом мире прямо сейчас может вырасти быль."""
    world = ctx.world
    out = []

    # --- погибшие города и нетронутые места ---------------------------
    for settlement in world.settlements.values():
        if settlement.status != RUINED or settlement.ended is None:
            continue
        age = year - settlement.ended.year
        if age < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.RUIN, "город по имени %s опустел" % settlement.name,
            settlement.ended.year, ref=settlement.id,
            region_id=settlement.region_id,
            weight=1.0 + min(2.0, age / 700.0)))

    for site in world.sites.values():
        if site.status not in (sites_mod.UNTOUCHED, sites_mod.ROBBED):
            continue
        age = year - site.created.year
        if age < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.PLACE, "%s по имени %s" % (site.kind, site.name),
            site.created.year, ref=site.id, region_id=site.region_id,
            site_id=site.id, weight=0.8 + min(1.6, age / 800.0)))

    # --- вещи, ушедшие из рук ------------------------------------------
    for artifact in world.artifacts.values():
        if artifact.where not in ("потерян", "в кургане", "в логове"):
            continue
        when = artifact.lost.year if artifact.lost else artifact.made.year
        if year - when < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.THING, "вещь по имени %s пропала" % artifact.name, when,
            ref=artifact.id, region_id=artifact.region_id, weight=0.8))

    # --- следы бедствий -------------------------------------------------
    for relic_id in world.sleeping_relics:
        relic = world.relics.get(relic_id)
        if relic is None or relic.created is None:
            continue
        if year - relic.created.year < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.TRACE, "после беды осталось: %s" % relic.name,
            relic.created.year, ref=relic.id, region_id=relic.region_id,
            weight=0.5))

    # --- войны и бедствия, которые отгремели ---------------------------
    for war in world.wars.values():
        if war.end is None:
            continue
        age = year - war.end.year
        if age < ECHO_MIN_AGE or age > 400:
            continue
        out.append(Node(
            cat.WAR_END, "война по имени %s кончилась" % war.name,
            war.end.year, ref=war.id,
            region_id=_war_region(world, war),
            weight=1.6 * max(0.3, 1.0 - age / 400.0)))

    for calamity in world.calamities.values():
        if calamity.end is None:
            continue
        age = year - calamity.end.year
        if age < ECHO_MIN_AGE or age > 600:
            continue
        out.append(Node(
            cat.CALAMITY, "бедствие по имени %s отступило" % calamity.name,
            calamity.end.year, ref=calamity.id,
            region_id=(calamity.region_ids or [""])[0],
            weight=1.2 * max(0.3, 1.0 - age / 600.0)))

    # --- умершие люди и павшие рода ------------------------------------
    for figure in world.figures.values():
        if figure.death is None or not figure.roles:
            continue
        age = year - figure.death.year
        if age < ECHO_MIN_AGE or age > 220:
            continue
        out.append(Node(
            cat.DEAD, "%s %s" % ("умерла" if figure.sex == "f" else "умер",
                                 figure.plain_name), figure.death.year,
            ref=figure.id, region_id=figure.origin_region,
            weight=1.3 * max(0.3, 1.0 - age / 220.0)))

    for house in world.houses.values():
        if house.status == "активно" or house.ended is None:
            continue
        age = year - house.ended.year
        if age < ECHO_MIN_AGE or age > 500:
            continue
        out.append(Node(
            cat.HOUSE_FALL, "род по имени %s пресёкся" % house.name,
            house.ended.year, ref=house.id,
            region_id=_seat_region(world, house.seat_id), weight=0.9))

    # --- наречия, пути, переселения ------------------------------------
    for tongue in world.tongues.values():
        if tongue.id in world.living_tongues:
            continue
        if tongue.ended is None or year - tongue.ended.year < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.TONGUE, "наречие по имени %s смолкло" % tongue.name,
            tongue.ended.year, ref=tongue.id, weight=0.6))

    for route in world.routes.values():
        if route.closed is None:
            continue
        age = year - route.closed.year
        if age < ECHO_MIN_AGE or age > 300:
            continue
        seller = world.polities.get(route.seller_id)
        out.append(Node(
            cat.ROUTE, "торговый путь закрылся", route.closed.year,
            ref=route.id,
            region_id=_polity_region(world, seller), weight=0.9))

    for migration in world.migrations.values():
        when = getattr(migration, "year", 0)
        if not when or year - when < ECHO_MIN_AGE or year - when > 400:
            continue
        out.append(Node(
            cat.MIGRATION, "народ снялся с места и пришёл сюда", when,
            ref=migration.id,
            region_id=getattr(migration, "to_region", ""), weight=1.0))

    # --- живые обиды и новые порядки -----------------------------------
    for fact in list(world.open_facts)[:400]:
        if fact.kind != history.GRUDGE or year - fact.year < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.GRUDGE, fact.note or "старая обида", fact.year,
            ref=fact.id, region_id=_holder_region(world, fact.holder_id),
            weight=1.5))

    for law in world.laws.values():
        age = year - law.made.year
        if age < ECHO_MIN_AGE or age > 200:
            continue
        polity = world.polities.get(law.polity_id)
        out.append(Node(
            cat.LAW, "завели новый порядок: %s" % law.name, law.made.year,
            ref=law.id, region_id=_polity_region(world, polity),
            weight=0.8))

    # --- звери и вера ---------------------------------------------------
    for monster_id in world.living_monsters:
        monster = world.monsters[monster_id]
        if year - monster.born.year < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.BEAST, "%s по имени %s живёт рядом"
            % (monster.word.lower(), monster.name), monster.born.year,
            ref=monster.id, region_id=monster.region_id, weight=0.7))

    for faith in world.faiths.values():
        if faith.founded is None or year - faith.founded.year < ECHO_MIN_AGE:
            continue
        out.append(Node(
            cat.HOLY, "вера по имени %s утвердилась" % faith.name,
            faith.founded.year, ref=faith.id, weight=0.7))

    for discovery in world.discoveries.values():
        age = year - discovery.made.year
        if age < ECHO_MIN_AGE or age > 300:
            continue
        out.append(Node(
            cat.CRAFT, "завелось ремесло: %s" % discovery.name,
            discovery.made.year, ref=discovery.id, weight=0.9))

    return out


def _level_out(found: list) -> list:
    """По стольку находок каждого вида — не больше.

    Иначе вид, которого в мире тысячи (умершие с именем), забивает те,
    которых десяток (закрывшиеся тракты), и мир рассказывает об одном.
    """
    by_kind = {}
    for node in found:
        by_kind.setdefault(node.kind, []).append(node)
    out = []
    for kind in sorted(by_kind):
        rows = by_kind[kind]
        rows.sort(key=lambda item: (-item.weight, item.what))
        out.extend(rows[:PER_KIND])
    return out


def _pick_node(ctx, rng, year: int):
    """Какой узел мир возьмёт в работу.

    Вес узла — это не «лучше или хуже», а «насколько это здесь уместно»:
    давно ли было, есть ли рядом люди и часто ли о таком уже рассказывали.
    """
    world = ctx.world
    found = _level_out(_nodes(ctx, year))
    if not found:
        return None
    told = world.story_marks
    pairs = []
    for node in found:
        weight = node.weight * cat.NODE_WEIGHT.get(node.kind, 0.6)
        # О чём рассказывали часто — о том реже: редкое со временем
        # получает больше шансов само.
        weight /= 1.0 + told.get("узел:%s" % node.kind, 0) * 0.35
        if node.region_id and not _souls_near(world, node.region_id):
            weight *= 0.15      # рассказывать некому
        pairs.append((node, max(0.02, weight)))
    pairs.sort(key=lambda pair: (pair[0].kind, pair[0].what, pair[0].year))
    return rng.weighted(pairs)


# ---------------------------------------------------------------------------
# Сборка были
# ---------------------------------------------------------------------------

def _tell(ctx, rng, year: int, node: Node) -> bool:
    world = ctx.world
    shape = _pick_shape(ctx, rng, node)
    if shape is None:
        return False
    home = _home(ctx, rng, node)
    if home is None:
        return False

    cast = _cast(ctx, rng, shape, home, year)
    if len(cast) < 2:
        return False

    began = ctx.date_in(rng, year)
    story = world.add_story(
        title="", shape=shape.key, node=node.kind, began=began,
        region_id=home.region_id, settlement_id=home.id,
        site_id=node.site_id, epicity=shape.epicity,
        tone=rng.weighted([(name, cat.TONE_WEIGHT.get(name, 1.0))
                           for name in cat.TONES]),
        genres=list(shape.genres),
        driver=rng.choice(cat.DRIVERS), cast=cast)
    story.anchors.append({"вид": node.kind, "что": node.what,
                          "год": node.year, "id": node.ref,
                          # Причины ведутся по событиям, а узел — это
                          # город, человек или война. Связать одно с
                          # другим можно только через летопись: берём
                          # последнее событие о нём, и цепочка «почему»
                          # уходит с него дальше в глубь веков.
                          "событие": world.event_about(node.ref)})

    _open(ctx, rng, story, shape, node, home, year)
    _middle(ctx, rng, story, shape, year)
    _turn(ctx, rng, story, shape, year)
    _close(ctx, rng, story, shape, home, year)
    _after(ctx, rng, story, shape, node, home, year)
    _name_it(ctx, rng, story, shape, home)
    _record(ctx, story, shape, home, year)

    marks = world.story_marks
    marks["узел:%s" % node.kind] = marks.get("узел:%s" % node.kind, 0) + 1
    marks["костяк:%s" % shape.key] = marks.get("костяк:%s" % shape.key, 0) + 1
    marks["эпичность:%d" % shape.epicity] = \
        marks.get("эпичность:%d" % shape.epicity, 0) + 1
    return True


def _pick_shape(ctx, rng, node: Node):
    """Костяк под этот узел — с оглядкой на то, чего уже много.

    Доли по эпичности заданы заранее: бытовых историй должно быть
    вчетверо больше, чем историй на державу. Держатся они не пожеланием,
    а этим весом.
    """
    world = ctx.world
    marks = world.story_marks
    total = max(1, sum(marks.get("эпичность:%d" % level, 0)
                       for level in range(6)))
    pairs = []
    for shape in cat.SHAPES:
        if node.kind not in shape.nodes:
            continue
        weight = shape.weight
        weight /= 1.0 + marks.get("костяк:%s" % shape.key, 0) * 0.3
        # Насколько этой эпичности уже набрано против положенной доли.
        have = marks.get("эпичность:%d" % shape.epicity, 0) / float(total)
        want = cat.EPICITY_SHARE.get(shape.epicity, 0.05)
        # Доли держатся этим и только этим: без сильной поправки бытовых
        # историй выходит вчетверо меньше, чем положено, а миру от этого
        # кажется, что он всё время в кризисе.
        weight *= max(0.03, min(8.0, (want / max(0.004, have)) ** 1.6))
        pairs.append((shape, weight))
    if not pairs:
        return None
    pairs.sort(key=lambda pair: pair[0].key)
    return rng.weighted(pairs)


def _home(ctx, rng, node: Node):
    """Где это случилось: живое поселение рядом с узлом."""
    world = ctx.world
    near, far = [], []
    region = world.regions.get(node.region_id)
    close = {node.region_id} | set(region.neighbors or ()) if region else set()
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.population < 80:
            continue
        (near if settlement.region_id in close else far).append(settlement)
    pool = near or far
    if not pool:
        return None
    pool.sort(key=lambda item: item.id)
    # Маленькие сёла рассказывают о себе не реже больших городов.
    return rng.weighted([(item, 1.0 + (item.population ** 0.35) * 0.05)
                         for item in pool])


def _cast(ctx, rng, shape, home, year: int) -> list:
    """Кто в этом участвовал. Обычные люди, а не государи.

    Живых людей мира берём первыми — у них уже есть память, связи и
    прошлое. Кого не хватает, тех приводим: пахарей, кузнецов, писцов.
    """
    world = ctx.world
    race = races_mod.RACES_BY_ID.get(home.race_id)
    if race is None:
        return []
    size = rng.weighted(((2, 2.0), (3, 3.0), (4, 2.0), (5, 1.0)))
    roles = _roles(rng, size)
    known = _local_folk(world, home, year)
    used, cast = set(), []
    for role in roles:
        figure = None
        if known and rng.chance(0.5):
            figure = known.pop()
        if figure is None:
            sex = "f" if rng.chance(0.45) else "m"
            figure = ctx.make_figure(
                rng, race, year, role=rng.choice(cat.TRADES),
                region_id=home.region_id, title="", sex=sex,
                home_id=home.id, epithet_chance=0.2,
                folk=world.folks.get(home.folk_id))
        if figure.id in used:
            continue
        used.add(figure.id)
        trade = next((item for item in figure.roles
                      if item in cat.TRADES), rng.choice(cat.TRADES))
        if figure.sex == "m" and trade in cat.TRADES_WOMEN:
            trade = cat.TRADES_WOMEN[trade]   # мужчина не травница
        cast.append({
            "кто": figure.id, "имя": figure.plain_name, "пол": figure.sex,
            "роль": role, "ремесло": trade,
            "зачем": rng.choice(cat.MOTIVES),
            "а на деле": rng.choice(cat.HIDDEN_MOTIVES)
            if rng.chance(0.4) else "",
        })
    return cast


def _roles(rng, size: int) -> list:
    """Роли: первый — тот, кто заметил, дальше без повторов."""
    rest = [role for role in cat.ROLES if role != cat.ROLES[0]]
    chosen = [cat.ROLES[0]]
    while len(chosen) < size and rest:
        role = rng.choice(rest)
        rest.remove(role)
        chosen.append(role)
    return chosen


def _local_folk(world, home, year: int) -> list:
    """Живые люди этой округи, которых можно взять в быль."""
    crowns = {world.polities[pid].ruler_id for pid in world.active_polities}
    out = []
    for figure in world.figures.values():
        if figure.id in crowns or not figure.alive_at(year):
            continue
        if figure.origin_region != home.region_id:
            continue
        if figure.age_at(year) < 15:
            continue
        out.append(figure)
    out.sort(key=lambda item: item.id)
    return out[:4]


# ---------------------------------------------------------------------------
# Акты
# ---------------------------------------------------------------------------

def _open(ctx, rng, story, shape, node, home, year: int) -> None:
    """Завязка: якорь, место, что заметили, что об этом подумали."""
    _act(story, node.year, "якорь",
         texts.anchor(rng, node.kind, node.what, node.year))
    _act(story, year, "место", texts.where(
        rng, texts.place_in(home.kind, home.name)))
    _act(story, year, "завязка", texts.opener(rng))

    # Люди считают одно, было другое: видимое и скрытое врозь.
    story.belief = rng.choice(cat.BELIEFS)
    story.truth = rng.choice(cat.TRUTHS)
    _act(story, year, "молва", texts.belief(rng, story.belief))

    # Подсказки: часть ведёт к правде, часть — мимо.
    for _ in range(rng.weighted(((1, 1.5), (2, 3.0), (3, 1.5)))):
        kind = rng.choice(cat.CLUE_KINDS)
        story.clues.append({"вид": kind, "строка": kind, "верна": True})
    if rng.chance(0.62):
        lead = rng.choice(cat.FALSE_LEADS)
        story.clues.append({"вид": "ложный след", "строка": lead,
                            "верна": False})
        _act(story, year, "ложный след", texts.false_lead(rng, lead))
    for clue in story.clues:
        if clue["верна"]:
            _act(story, year, "подсказка", texts.clue(rng, clue["строка"]))
            break


def _middle(ctx, rng, story, shape, year: int) -> None:
    """Развитие: столько шагов, сколько просит размах истории."""
    low, high = shape.acts
    steps = rng.randint(low, high)
    when = year
    used = set()
    for number in range(steps):
        for _ in range(5):
            line = texts.step(rng)
            if line not in used:
                used.add(line)
                break
        _act(story, when, "ход", line)
        if rng.chance(0.35):
            when += rng.randint(1, 3)


def _turn(ctx, rng, story, shape, year: int) -> None:
    """Поворот. Разрешён только подготовленный.

    Без этого правила поворот превращается в произвол: «и вдруг всё было
    иначе». Поэтому каждый поворот привязан к уже названной подсказке.
    """
    if not story.clues:
        return
    if not rng.chance(0.72):
        return
    key, line = rng.choice(cat.TWISTS)
    story.twist = line
    story.twist_seeded = any(item["верна"] for item in story.clues)
    when = story.acts[-1]["год"] if story.acts else year
    _act(story, when, "поворот", texts.twist(rng, line),
         why=story.clues[0]["строка"])


def _close(ctx, rng, story, shape, home, year: int) -> None:
    """Кульминация и исход. Драка — один способ из семнадцати."""
    pairs = []
    for key, line, weight in cat.CLIMAXES:
        if key == "драка":
            weight *= shape.fight * 5.0
        pairs.append(((key, line), weight))
    key, line = rng.weighted(pairs)
    story.climax = line
    when = story.acts[-1]["год"] if story.acts else year
    _act(story, when, "кульминация", texts.climax(rng, line))

    name, weight, line = rng.weighted(
        [((item[0], item[1], item[2]), item[1]) for item in cat.OUTCOMES])
    story.outcome = name
    _act(story, when, "исход", texts.outcome(rng, line))
    story.ended = ctx.date_in(rng, max(year, when), after=story.began)

    # Правду узнали не всегда: тайна имеет право остаться тайной.
    if story.outcome in ("тайна осталась", "не сладилось", "тянется дальше"):
        _act(story, when, "правда", "Как было на самом деле, так и не "
                                    "узнали.")
    else:
        _act(story, when, "правда", texts.truth(rng, story.truth))


def _after(ctx, rng, story, shape, node, home, year: int) -> None:
    """Последствия. Большинство былей дальше места не идёт."""
    when = story.ended.year if story.ended else year
    depth = 2 if shape.epicity <= 1 else min(5, 2 + shape.epicity - 1)
    levels = list(cat.LEVELS[:depth])
    for level in levels:
        if level != cat.PERSONAL and not rng.chance(0.55):
            continue
        line = rng.choice(cat.AFTER[level])
        story.consequences.append({"уровень": level, "что": line})
        _act(story, when, "после", "%s — %s." % (level.capitalize(), line))

    # Разные люди рассказывают это по-разному.
    for who in rng.shuffled(list(cat.VOICES))[:rng.randint(2, 3)]:
        story.voices.append({"кто": who, "версия": cat.VOICE_TILT[who]})

    _write_back(ctx, rng, story, shape, node, home, when)


def _write_back(ctx, rng, story, shape, node, home, year: int) -> None:
    """Что быль меняет в самом мире.

    Без этого она осталась бы рассказом сбоку. Место меняет состояние,
    вещь — руки, у людей появляется роль и след в ткани причин, а через
    поколение из громкой были вырастает предание.
    """
    world = ctx.world
    # Место: вскрытое остаётся вскрытым.
    site = world.sites.get(story.site_id) if story.site_id else None
    if site is not None and story.outcome in ("сладилось",
                                              "сладилось наполовину"):
        if site.status == sites_mod.UNTOUCHED:
            site.status = sites_mod.ROBBED
            site.opened = story.ended
            site.notes.append("вскрыто былью по имени «%s»" % story.title)

    # Люди: участие в деле запоминается.
    for item in story.cast:
        figure = world.figures.get(item["кто"])
        if figure is None:
            continue
        figure.notes.append("замешан в деле: %s" % (story.title or "быль")
                            if figure.sex == "m"
                            else "замешана в деле: %s"
                            % (story.title or "быль"))

    # След в ткани причин: обида, слава или долг остаётся у державы.
    polity_id = home.polity_id
    if polity_id and polity_id in world.polities and shape.epicity >= 2:
        kind = history.GRUDGE if story.outcome in (
            "новая вражда", "проиграли оба",
            "другая сторона взяла") else history.FAVOUR
        history.leave(world, kind, year, polity_id, weight=0.35,
                      note="быль по имени «%s»" % (story.title or "быль"))


def _name_it(ctx, rng, story, shape, home) -> None:
    """Имя по фактам этой были, а не из общего списка."""
    kinds = ["дело", "место"]        # эти два годятся всякой были
    if story.node == cat.THING:
        kinds.append("вещь")
    if story.node in (cat.DEAD, cat.HOUSE_FALL, cat.MIGRATION):
        kinds.append("человек")
    place = texts.place_in(home.kind, home.name)

    def make():
        # Вид названия выбирается заново на каждой попытке: если имя по
        # делу уже занято, следующая попытка возьмёт имя по месту, а
        # мест в мире столько же, сколько городов. Иначе кузница имён
        # начинала приставлять «Новый» и «Верхний», и половина былей
        # называлась одинаково.
        return texts.title(rng, rng.choice(kinds), place=place,
                           shape=shape.key)

    story.title = ctx.forge.unique("story", make, rng)


def _record(ctx, story, shape, home, year: int) -> None:
    """Запись в летописи — только если быль вышла за пределы двора."""
    world = ctx.world
    if shape.epicity < 1:
        return          # бытовое живёт в своём разделе, а не в летописи
    names = ", ".join(item["имя"] for item in story.cast[:3])
    body = "%s Считали, что %s. Участники: %s. Исход: %s." % (
        story.acts[0]["строка"] if story.acts else "",
        story.belief, names, story.outcome)
    roots = [anchor["событие"] for anchor in story.anchors
             if anchor.get("событие")]
    event = world.add_event(
        date=story.ended or story.began,
        era_index=world.era_index_at(year), kind="local_story",
        title=story.title, text=body,
        importance=min(4, 1 + shape.epicity),
        actors=[item["кто"] for item in story.cast[:4]],
        subjects=[story.id], region_id=story.region_id,
        race_id=home.race_id,
        causes=roots)          # быль всегда выросла из чего-то
    story.event_ids.append(event.id)


# ---------------------------------------------------------------------------
# Предание, выросшее из были
# ---------------------------------------------------------------------------

# Чем быль оказывается в песне: от этого зависит, как песня будет врать
# (`lore.shifts_for`). Про руины врут кладом, про зверя — ростом, про
# всё остальное — королевской кровью героя.
SONG_ABOUT = {
    cat.RUIN: "место",
    cat.PLACE: "место",
    cat.THING: "вещь",
    cat.BEAST: "чудовище",
    cat.TRACE: "беда",
    cat.CALAMITY: "беда",
    cat.WAR_END: "война",
    cat.HOUSE_FALL: "престол",
}


def _grow_legend(ctx, year: int) -> None:
    """Громкая быль через поколение становится преданием.

    Пока живы те, кто помнит, рассказ держится факта: поправить его
    есть кому. Песню складывают позже — и с этого мига она живёт своей
    жизнью: дальше её уносит общий снос легенд (`systems/lore`), а
    правда остаётся записанной в `legend.truth` и расходится с
    пересказом. Так одно и то же дело в разделе «Были» и в разделе
    «Предания» читается по-разному, и это не рассогласование, а то, ради
    чего оба раздела есть.
    """
    world = ctx.world
    pairs = []
    for story in sorted(world.stories.values(), key=lambda item: item.id):
        if story.legend_id or story.epicity < LEGEND_FROM:
            continue
        if story.ended is None or not story.cast:
            continue
        age = year - story.ended.year
        if age < LEGEND_DELAY or age > LEGEND_FORGET:
            continue
        # Чем громче дело и чем дольше о нём помнят, тем вернее песня.
        pairs.append((story, story.epicity * (1.0 + min(1.0, age / 300.0))))
    if not pairs:
        return
    rng = ctx.rng("story-songs", year)
    if not rng.chance(SONG_RATE):
        return
    story = rng.weighted(pairs)
    leader = world.figures.get(story.cast[0]["кто"])
    date = ctx.date_in(rng, year)

    def name_it():
        word = rng.choice(lore_cat.LEGEND_WORDS)
        if leader is not None and rng.chance(0.45):
            about = ("о человеке по имени %s" if leader.sex == "m"
                     else "о женщине по имени %s") % leader.plain_name
        else:
            about = "о деле, которое зовут «%s»" % (story.title or "быль")
        return "%s %s" % (word, about)

    legend = world.add_legend(
        name=ctx.forge.unique("legend", name_it, rng), born=date,
        event_id=story.event_ids[0] if story.event_ids else "",
        about=SONG_ABOUT.get(story.node, "герой"),
        subject_id=story.cast[0]["кто"],
        race_id=leader.race_id if leader is not None else "",
        region_id=story.region_id,
        truth="%s — %s" % (story.title or "быль",
                           story.truth or story.outcome))
    story.legend_id = legend.id
    story.notes.append("об этом сложили предание по имени «%s»" % legend.name)
    title, text = lore_texts.legend_born(
        rng, legend, max(1, year - story.ended.year))
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="legend_born",
        title=title, text=text, importance=2,
        subjects=[legend.id, story.id], region_id=story.region_id,
        race_id=legend.race_id,
        causes=[story.event_ids[0]] if story.event_ids else [])


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _act(story, year: int, kind: str, line: str, why: str = "") -> None:
    if not line:
        return
    story.acts.append({"год": int(year), "вид": kind, "строка": line,
                       "из-за": why})


def _souls_near(world, region_id: str) -> int:
    total = 0
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id == region_id:
            total += settlement.population
    return total


def _war_region(world, war) -> str:
    polity = world.polities.get(getattr(war, "attacker_id", ""))
    return _polity_region(world, polity)


def _polity_region(world, polity) -> str:
    if polity is None:
        return ""
    seat = world.settlements.get(polity.capital_id)
    return seat.region_id if seat is not None else ""


def _holder_region(world, holder_id: str) -> str:
    polity = world.polities.get(holder_id)
    if polity is not None:
        return _polity_region(world, polity)
    house = world.houses.get(holder_id)
    if house is not None:
        return _seat_region(world, house.seat_id)
    return ""


def _seat_region(world, seat_id: str) -> str:
    """Земля родового гнезда: у самого рода такого поля нет."""
    seat = world.settlements.get(seat_id) if seat_id else None
    return seat.region_id if seat is not None else ""


__all__ = ["upkeep"]
