# -*- coding: utf-8 -*-
"""Жизнь чудес света: найти, прославить, потерять и вспомнить.

Главное правило тут — из присланного задания и из здравого смысла:
**не создавать десять красивых объектов, а находить в уже готовом мире
то, что само собой стало исключительным.** Поэтому природные чудеса
берутся не с потолка, а из карты: вот эта вершина, выше которой нет
ничего, вот это озеро, другого берега которого не видно, вот этот
водопад — река, у которой под ногами обрыв. А рукотворные — из истории:
держава, у которой к этому веку хватило людей и денег, город, в котором
было кому строить, и названная причина, зачем.

Четыре вещи, которые тут происходят по-настоящему.

**Находится.** Чудо не ставится, а отыскивается: движок перебирает то,
что карта и реестры уже знают, и спрашивает, есть ли среди этого
исключительное. Если нет — чуда не будет, и мир от этого не обеднеет. И
находится оно не в первый год мира: карта даёт только притязания, а
чудом место делают люди — тем десятилетием, когда в эту землю пришли
жить. Иное чудо и вовсе написала история, а не карта: шрам беды, на
который через век с лишним стали ходить смотреть.

**Прославляется.** Величина не равна известности: о крупнейшем озере
можно не знать вовсе, если рядом никто не живёт. Слава ходит вверх и
вниз сама — от того, живут ли рядом, цела ли дорога и есть ли кому
рассказывать.

**Кончается.** Беда рушит, море топит, держава падает и уводит за собой
тех, кто ходил. Утраченное остаётся в списках и в спорах, а через века
его иногда находят снова.

**Оспаривается.** У одного чуда пять правд — своя, народная, храмовая,
чужая и та, что у знающих, — и шестая, которую знает только генератор.
А иное чудо и не было чудом: его просто так назвали.
"""

from __future__ import annotations

from .. import narrative_wonders as texts
from .. import wonders as cat
from ..mapregions import translit
from ..models import ACTIVE
from ..timeline import Date, plural

# Сколько чудес мир заводит сам. Числом это не задаётся: сколько
# исключительного нашлось, столько и будет. Потолок стоит только затем,
# чтобы на богатой карте их не оказалось три десятка — тогда слово
# «чудо» перестанет что-либо значить.
NATURAL_CAP = 11
NATURAL_CHANCE = 0.62
NAME_RATE = 0.22            # как скоро его назовут, когда рядом поселились

# Рукотворное чудо — дело редкое: за десять тысяч лет их выходит
# полдюжины. Чаще — и всякая держава строит себе по чуду, а это уже не
# чудо, а обычай.
BUILT_RATE = 0.006
MIXED_CHANCE = 0.3          # и если в земле уже есть чудо — строят при нём

BUILT_SOULS = 60000         # меньшей державе такое не поднять
BUILT_AGE = 120             # и моложе этого она ещё не успевает

# Чудо, которое оставила беда. Редкое: шрамов много, чудес из них мало.
SCAR_RATE = 0.004
SCAR_QUIET = 150            # пока беду помнят, это место не чудо, а горе

# Слава ходит сама. Вверх — пока есть кому рассказывать; вниз — когда
# рассказывать стало некому.
FAME_RATE = 0.04
FORGET_RATE = 0.05
# Утраченное находят снова, но не скоро и не всякое.
FOUND_RATE = 0.004
FOUND_QUIET = 400           # сколько лет оно должно пролежать забытым
FIX_RATE = 0.012            # и не всякое найденное поднимают

# Список чудес («Семь чудес такой-то державы») составляют редко, и для
# этого надо, чтобы было что считать.
LIST_RATE = 0.012
LIST_LEAST = 4              # из трёх выбирать нечего: это не список, а счёт
LIST_CAP = 3                # и списков в мире единицы, иначе они не в счёт

# Ложное чудо: его так зовут, а оно им не было. Оспорить можно не
# всякое: высочайшую гору измерят и без летописи, а вот красоту,
# древность, тайну и святость доказать нечем.
FALSE_RATE = 0.003
DOUBTFUL = ("story", "riddle", "magic", "faith", "beauty", "age", "custom",
            "alone")

# Разные правды об одном чуде заводятся, когда о нём знают достаточно
# далеко, чтобы было кому пересказывать по-своему.
VOICE_FAME = 3

# Что беда может испортить и в природе: лес горит, озеро мелеет, древо
# валится. Гора, ущелье и остров ей не по зубам.
MARRABLE = ("forest", "tree", "lake", "river", "falls", "spring", "garden",
            "waste")


# ---------------------------------------------------------------------------
# Начало мира: что в нём исключительно само по себе
# ---------------------------------------------------------------------------

def prepare(ctx) -> None:
    """Ищет природные чудеса в том, что карта уже нарисовала."""
    world = ctx.world
    rng = ctx.rng("wonders", "prepare")
    link = getattr(world, "map_link", None)
    wmap = getattr(link, "wmap", None) if link is not None else None
    if wmap is None:
        _prepare_flat(ctx, rng)
        return

    found = []
    found.extend(_from_peaks(wmap))
    found.extend(_from_volcanoes(wmap))
    found.extend(_from_features(wmap))
    found.extend(_from_rivers(world, wmap))
    found.extend(_from_biomes(world, wmap))
    found.extend(_from_lairs(wmap))
    found.extend(_from_magic(world, wmap))

    # Порядок перебора закреплён: иначе одна и та же карта дала бы разные
    # чудеса от перестановки словаря.
    found.sort(key=lambda row: (row["нужда"], -row["вес"], row["гекс"]))
    taken = set()
    rows = []
    for row in found:
        if len(rows) >= NATURAL_CAP:
            break
        if row["нужда"] in taken:
            continue        # по одному чуду на вид: двух «высочайших» не бывает
        if not rng.chance(NATURAL_CHANCE):
            taken.add(row["нужда"])
            continue
        taken.add(row["нужда"])
        rows.append(row)
    world.notes["чудеса впереди"] = rows


def _prepare_flat(ctx, rng) -> None:
    """Мир без карты: гексов нет, но земли есть, и у них есть крайности."""
    world = ctx.world
    regions = sorted(world.regions.values(), key=lambda item: item.id)
    if not regions:
        return
    picks = (
        ("peak", "горы", lambda item: item.richness, "size"),
        ("forest", "лес", lambda item: item.capacity, "size"),
        ("anomaly", "", lambda item: abs(item.magic), "magic"),
        ("waste", "пустыня", lambda item: -item.habitat, "danger"),
    )
    rows = []
    for need, terrain, score, ground in picks:
        pool = [item for item in regions
                if not terrain or item.terrain == terrain]
        if not pool or not rng.chance(NATURAL_CHANCE):
            continue
        best = max(pool, key=lambda item: (score(item), item.id))
        if not cat.SHAPES_BY_NEED.get(need):
            continue
        rows.append({"нужда": need, "гекс": -1, "вес": float(score(best)),
                     "имя": "", "мера": "", "основание": ground,
                     "земля": best.id})
    world.notes["чудеса впереди"] = rows


def _hex_of(wmap, feature) -> int:
    column = int(feature.get("cx", 0))
    row = int(feature.get("cy", 0))
    column = max(0, min(wmap.width - 1, column))
    row = max(0, min(wmap.height - 1, row))
    return row * wmap.width + column


def _from_peaks(wmap) -> list:
    """Высочайшая вершина — и самая одинокая, если она не та же самая."""
    peaks = list(wmap.peaks or ())
    if not peaks:
        return []
    best = max(peaks, key=lambda item: (item.get("m", 0), item.get("i", 0)))
    return [{"нужда": "peak", "гекс": int(best.get("i", -1)),
             "вес": float(best.get("m", 0)),
             "имя": translit(str(best.get("name", "")).replace("г. ", "")),
             # Метры и гексы — слова карты, а не летописи. Мера тут
             # сравнением: эта гора выше всех, и это её и делает чудом.
             "мера": "выше её в этом мире не поднимается ничто",
             "основание": "size"}]


def _from_volcanoes(wmap) -> list:
    rows = list(wmap.volcanoes or ())
    if not rows:
        return []
    # Дышащий вперёд потухшего: о потухшем не рассказывают.
    order = {"active": 2, "dormant": 1, "extinct": 0}
    best = max(rows, key=lambda item: (order.get(item.get("status"), 0),
                                       item.get("m", 0), item.get("i", 0)))
    status = best.get("status")
    return [{"нужда": "volcano", "гекс": int(best.get("i", -1)),
             "вес": float(best.get("m", 0)) + 9000 * order.get(status, 0),
             "имя": translit(str(best.get("name", "")).replace("влк. ", "")),
             "мера": ("она дышит и поныне: пепел её ложится на три земли"
                      if status == "active" else
                      "она молчит, но молчит не насовсем"
                      if status == "dormant" else
                      "она выгорела дотла, и в жерле её стоит вода"),
             "основание": "danger" if status == "active" else "rare"}]


def _from_features(wmap) -> list:
    """Крупнейшее озеро, крупнейший остров, величайший хребет."""
    want = {"lake": ("lake", "других таких озёр в этом мире нет, и "
                             "другого берега с него не видно"),
            "bigisland": ("isle", "он велик настолько, что на нём "
                                  "умещается целая земля"),
            "island": ("isle", "он лежит один посреди воды"),
            "range": ("peak", "хребет этот тянется через полмира")}
    best = {}
    for feature in (wmap.features or ()):
        kind = feature.get("type")
        if kind not in want:
            continue
        need = want[kind][0]
        area = float(feature.get("area", 0))
        if area <= 0:
            continue
        # Озеро в девять гексов — не чудо, а озеро. Порог тут не на
        # красоту, а на здравый смысл: «другого берега не видно» о луже
        # читается как ложь.
        if kind == "lake" and area < 12:
            continue
        if need not in best or area > best[need][0]:
            best[need] = (area, feature, want[kind][1])
    rows = []
    for need, (area, feature, measure) in best.items():
        if need == "peak":
            continue        # вершина уже взята по высоте, хребет — не чудо сам
        rows.append({"нужда": need, "гекс": _hex_of(wmap, feature),
                     "вес": area,
                     "имя": translit(str(feature.get("name", ""))),
                     "мера": measure,
                     "основание": "size"})
    return rows


def _from_rivers(world, wmap) -> list:
    """Водопад и ущелье: их на карте не отмечено, но они на ней есть.

    Водопад — речной гекс, у которого под ногами обрыв; ущелье — речной
    гекс, зажатый соседями много выше себя. Перебираются только речные
    гексы: их на карте считаные тысячи, а не сто тысяч.
    """
    rows = []
    best_fall = (0.0, -1)
    best_gorge = (0.0, -1)
    best_flow = (0.0, -1)
    size = wmap.width * wmap.height
    for index in range(size):
        if not wmap.is_river(index):
            continue
        here = wmap.elevation_m(index)
        near = [wmap.elevation_m(other) for other in wmap.neighbors(index)]
        if not near:
            continue
        drop = here - min(near)
        rise = max(near) - here
        if drop > best_fall[0]:
            best_fall = (drop, index)
        if rise > best_gorge[0]:
            best_gorge = (rise, index)
        flow = float(wmap.value(9, index, 0)) if wmap.has(9) else 0.0
        if flow > best_flow[0]:
            best_flow = (flow, index)
    if best_fall[1] >= 0 and best_fall[0] >= 180:
        rows.append({"нужда": "falls", "гекс": best_fall[1],
                     "вес": best_fall[0], "имя": "",
                     "мера": "вода падает тут с высоты, с какой не падает "
                             "больше нигде: до низа долетает один туман",
                     "основание": "beauty"})
    if best_gorge[1] >= 0 and best_gorge[0] >= 400:
        rows.append({"нужда": "canyon", "гекс": best_gorge[1],
                     "вес": best_gorge[0], "имя": "",
                     "мера": "стены над рекой стоят так высоко, что солнце "
                             "заглядывает на дно на час в день",
                     "основание": "size"})
    if best_flow[1] >= 0 and best_flow[0] > 0:
        rows.append({"нужда": "river", "гекс": best_flow[1],
                     "вес": best_flow[0], "имя": "",
                     "мера": "она собирает воду со всей этой стороны мира",
                     "основание": "size"})
    return rows


def _from_biomes(world, wmap) -> list:
    """Величайший лес, величайшая пустыня, древнее древо.

    Считается по числу гексов биома: что занимает больше всех, то и
    величайшее. Гекс берётся не случайный, а срединный по счёту — так он
    всякий раз один и тот же.
    """
    from ..worldforge.biomes import GROUPS
    buckets = {}
    size = wmap.width * wmap.height
    for index in range(size):
        if not wmap.is_land(index):
            continue
        biome = int(wmap.value(3, index, 0))
        group = GROUPS[biome] if biome < len(GROUPS) else ""
        if group in ("Тропические", "Умеренные", "Бореальные"):
            buckets.setdefault("forest", []).append(index)
        elif group == "Засушливые":
            buckets.setdefault("waste", []).append(index)
    rows = []
    for need, measure, ground in (
            ("forest", "больше леса в этом мире нет: вошедший идёт им "
                        "неделями и не видит края", "size"),
            ("waste", "суше и шире этого в мире нет, и воды в ней не "
                      "найдёт даже знающий", "danger")):
        hexes = buckets.get(need) or []
        if len(hexes) < 40:
            continue
        rows.append({"нужда": need, "гекс": hexes[len(hexes) // 2],
                     "вес": float(len(hexes)), "имя": "",
                     "мера": measure, "основание": ground})
    return rows


def _from_lairs(wmap) -> list:
    rows = list(wmap.lairs or ())
    if not rows:
        return []
    best = max(rows, key=lambda item: (item.get("suggestedAgeYears", 0),
                                       item.get("i", 0)))
    years = int(best.get("suggestedAgeYears", 0))
    return [{"нужда": "lair", "гекс": int(best.get("i", -1)),
             "вес": float(years),      # возрастом логова мерится, какое древнее
             "имя": translit(str(best.get("name", ""))),
             # Сколько ему лет, в летописи не стоит: счёт его годам
             # шёл до первой записи, и свести его не с чем.
             "мера": "оно старше всех держав этого мира, и сколько ему "
                     "лет — не знает никто",
             "основание": "age"}]


def _from_magic(world, wmap) -> list:
    """Место, где сила стоит гуще всего: его и зовут местом, где всё не так."""
    best = (0.0, -1)
    size = wmap.width * wmap.height
    for index in range(0, size, 7):     # не всякий гекс: шаг тут не портит
        if not wmap.is_land(index):
            continue
        value = abs(float(wmap.value(15, index, 0.0))) if wmap.has(15) else 0.0
        if value > best[0]:
            best = (value, index)
    if best[1] < 0 or best[0] < 0.5:
        return []
    return [{"нужда": "anomaly", "гекс": best[1], "вес": best[0], "имя": "",
             "мера": "сила стоит тут гуще, чем где бы то ни было",
             "основание": "magic"}]


def _region_of_row(world, row):
    """Земля притязания: по гексу на карте или прямо по записи."""
    if row.get("земля"):
        return world.regions.get(row["земля"])
    index = int(row.get("гекс", -1))
    link = getattr(world, "map_link", None)
    if link is None or index < 0:
        return None
    region_id = (getattr(link, "region_of_hex", {}) or {}).get(index)
    return world.regions.get(region_id) if region_id else None


def _witness(world, region, year: int):
    """Кто в этой земле живёт к этому году — тот, кто и назовёт чудом.

    Возвращается не просто «да», а именно он: племя или город. Его номер
    ложится в отметку, и по нему потом можно проверить, что чудо назвали
    не раньше, чем в эту землю пришли. Иначе проверить это уже нельзя:
    племена кочуют, и к концу истории в земле стоят совсем другие.
    """
    if region is None:
        return None
    best = None
    for table in (world.settlements, getattr(world, "tribes", {})):
        for item in table.values():
            if getattr(item, "region_id", "") != region.id:
                continue
            if item.founded.year > year:
                continue
            if best is None or (item.founded.year, item.id) \
                    < (best.founded.year, best.id):
                best = item
    return best


def _name_natural(ctx, year: int, rng, scale: float) -> None:
    """Притязание становится чудом, когда рядом появляется кому рассказать.

    В первый год мира величайший водопад уже стоит, а чуда света в нём
    нет: чудом место делают люди. Поэтому карта даёт только притязания,
    а имя и слава приходят к ним тем веком, когда в эту землю пришли
    жить.
    """
    world = ctx.world
    rows = world.notes.get("чудеса впереди") or []
    if not rows:
        return
    left = []
    for row in rows:
        region = _region_of_row(world, row)
        witness = _witness(world, region, year)
        if witness is None or not rng.chance(NAME_RATE * scale):
            left.append(row)
            continue
        if _make_natural(ctx, rng, row, year, region, witness) is None:
            left.append(row)
    world.notes["чудеса впереди"] = left


def _make_natural(ctx, rng, row, year: int, region, witness):
    shapes = cat.SHAPES_BY_NEED.get(row["нужда"]) or ()
    if not shapes:
        return None
    shape = rng.choice(list(shapes))
    wonder = _add(ctx, rng, shape, row.get("основание", "size"), region,
                  int(row.get("гекс", -1)),
                  row.get("мера", "") or rng.choice(shape.about),
                  born_year=year, given=row.get("имя", ""))
    if wonder is not None:
        wonder.marks.append({
            "год": year, "что": "названо чудом", "кто": witness.id,
            # Род тут от слова облика: гора стояла, и назвали её.
            "отчего": "%s и прежде, а чудом %s назвали те, кто поселился "
                      "рядом: %s"
                      % (texts.pair(shape.gender, "стоял", "стояла",
                                    "стояло"),
                         texts.pair(shape.gender, "его", "её", "его"),
                         witness.name)})
    return wonder


def _add(ctx, rng, shape, ground, region, index, measure, born_year=1,
         given="", polity=None, figure=None, motive="", cost=""):
    """Завести чудо. Имя берётся с карты, если карта его уже дала."""
    world = ctx.world
    name = given.strip()
    if not name and " " not in shape.word:
        # Односложному облику имя собирается оборотом («Вечная Твердыня»),
        # но прилагательных в обороте немного — имя надо сверить с занятыми.
        name = ctx.forge.unique(
            "wonder", lambda: cat.make_name(rng, shape), rng)
    if not name:
        # Многословному облику оборот не годится, и имя ему даёт кузница —
        # звучанием тех, кто тут живёт: «башня чародея по имени Эльдарин».
        name = ctx.forge.place_word(rng, _race_near(world, region))
    access, why = _access_for(rng, world, index, region)
    wonder = world.add_wonder(
        name=name, kind=shape.kind, shape=shape.key, ground=ground,
        born=Date(max(1, int(born_year)), rng.randint(1, 12),
                  rng.randint(1, 28)),
        region_id=region.id if region is not None else "",
        hex_index=int(index),
        polity_id=polity.id if polity is not None else "",
        figure_id=figure.id if figure is not None else "",
        motive=motive, cost=cost,
        measure=measure or rng.choice(shape.about),
        # Построенное знают хотя бы соседи — его только что строили на
        # их глазах. Природное же надо ещё разнести по свету.
        fame=0 if shape.kind == cat.NATURAL else 1,
        access=access, access_why=why)
    wonder.peak_fame = wonder.fame
    wonder.truth = wonder.measure
    title, text = texts.found(rng, wonder, region)
    world.add_event(
        date=wonder.born, era_index=world.era_index_at(wonder.born.year),
        kind="wonder_found", title=title, text=text,
        importance=3 if shape.kind == cat.BUILT else 2,
        region_id=wonder.region_id, subjects=[wonder.id])
    return wonder


def _race_near(world, region):
    """Чьей фонетикой звучит имя: тех, кто тут живёт, а не первых попавшихся."""
    from .. import races as races_mod
    if region is not None:
        for item in sorted(world.settlements.values(),
                           key=lambda row: (len(row.id), row.id)):
            if item.region_id == region.id:
                return races_mod.get_race(item.race_id)
    for folk in sorted(world.folks.values(), key=lambda row: (len(row.id),
                                                              row.id)):
        return races_mod.get_race(folk.race_id)
    return races_mod.RACES[0]


def _access_for(rng, world, index, region):
    """Дойти до него легко или нельзя — и отчего."""
    link = getattr(world, "map_link", None)
    wmap = getattr(link, "wmap", None) if link is not None else None
    near = 0
    if region is not None:
        near = sum(1 for item in world.settlements.values()
                   if item.region_id == region.id)
    rough = 0.0
    if wmap is not None and index >= 0:
        rough = abs(wmap.elevation_m(index)) / 1000.0
        if not wmap.is_land(index):
            rough += 2.0
    score = near - rough
    if score >= 4:
        return "easy", ""
    if score >= 1:
        return "fair", ""
    why = rng.choice(cat.ACCESS_WHYS)
    if score >= -1:
        return "hard", why
    return ("grim" if rng.chance(0.7) else "none"), why


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("wonders", year)
    scale = period / 10.0

    _name_natural(ctx, year, rng, scale)
    if rng.chance(SCAR_RATE * scale):
        _from_scar(ctx, year, rng)
    if rng.chance(BUILT_RATE * scale):
        _build(ctx, year, rng)

    for wonder in sorted(world.wonders.values(), key=lambda item: item.id):
        _tick(ctx, wonder, year, rng, scale)

    if rng.chance(LIST_RATE * scale):
        _compile_list(ctx, year, rng)
    if rng.chance(FALSE_RATE * scale):
        _expose(ctx, year, rng)


# ---------------------------------------------------------------------------
# Чудо, которое сделала беда
# ---------------------------------------------------------------------------
#
# Беда не только рушит чудеса — иногда она их и оставляет. Земля
# разошлась, и через век в разлом ходят смотреть; город ушёл под воду, и
# озеро на его месте стали звать по имени города. Такое чудо нельзя
# найти на карте: карты эти шрамы не знала, их написала история.

# Из какого шрама что выходит. Шрамов видов больше, но чудом становится
# не всякий: сгоревший лес — беда, а не чудо.
SCAR_SHAPES = {
    "новый каньон": ("canyon", "ущелье это разошлось на глазах живших, и "
                               "дна его с тех пор никто не достал"),
    "новая гора": ("peak", "её не было при дедах, и это помнят"),
    "озеро на месте города": ("lake", "на дне его стоит город, и в тихую "
                                      "воду видно крыши"),
    "лавовое поле": ("waste", "камень тут остыл не весь, и по нему не "
                              "растёт ничего"),
    "пепельная пустошь": ("waste", "пепел лежал тут десятки лет, а теперь "
                                   "на нём сады, каких нет нигде"),
}


def _from_scar(ctx, year: int, rng) -> None:
    """Шрам беды, на который стали ходить смотреть.

    Нужно, чтобы шрам отстоял от беды на век с лишним: пока беда
    помнится, место это не чудо, а горе. И нужно, чтобы в земле жили —
    иначе смотреть на него некому.
    """
    world = ctx.world
    pool = []
    for scar in sorted(world.scars.values(), key=lambda item: item.id):
        if scar.created is None or year - scar.created.year < SCAR_QUIET:
            continue
        if scar.kind not in SCAR_SHAPES:
            continue
        if _witness(world, world.regions.get(scar.region_id), year) is None:
            continue
        if any(item.scar_id == scar.id for item in world.wonders.values()):
            continue
        pool.append(scar)
    if not pool:
        return
    scar = rng.choice(pool)
    key, measure = SCAR_SHAPES[scar.kind]
    shapes = [item for item in cat.SHAPES_BY_NEED.get(key, ())]
    if not shapes:
        return
    shape = rng.choice(shapes)
    calamity = world.calamities.get(scar.calamity_id)
    region = world.regions.get(scar.region_id)
    wonder = _add(ctx, rng, shape, "story", region, -1, measure,
                  born_year=year)
    if wonder is None:
        return
    wonder.scar_id = scar.id
    witness = _witness(world, region, year)
    wonder.marks.append({
        "год": year, "что": "названо чудом",
        "кто": witness.id if witness is not None else "",
        "отчего": "его оставила беда по имени %s" % calamity.name
        if calamity is not None else "его оставила давняя беда"})
    scar.notes.append("%d: на него стали ходить смотреть как на чудо" % year)


# ---------------------------------------------------------------------------
# Рукотворное
# ---------------------------------------------------------------------------

def _build(ctx, year: int, rng) -> None:
    """Державе хватило людей, денег и повода — и она строит."""
    world = ctx.world
    pairs = []
    for polity in world.polities.values():
        if polity.status != ACTIVE or polity.population < BUILT_SOULS:
            continue
        if year - polity.founded.year < BUILT_AGE:
            continue
        pairs.append((polity, float(polity.population)))
    if not pairs:
        return
    polity = rng.weighted(pairs)
    city = world.settlements.get(polity.capital_id)
    if city is None or city.status != ACTIVE:
        return
    region = world.regions.get(city.region_id)

    link = getattr(world, "map_link", None)
    wmap = getattr(link, "wmap", None) if link is not None else None
    coast = bool(wmap is not None and city.hex_index >= 0
                 and wmap.is_coast(city.hex_index))
    river = bool(wmap is not None and city.hex_index >= 0
                 and wmap.is_river(city.hex_index))

    # Смешанное чудо не ставят на пустом месте: оно вырастает вокруг
    # уже названного природного. Храм обходит стенами то, ради чего его
    # ставили, а лестница только и нужна затем, чтобы туда дойти, —
    # поэтому до самого чуда после этого добираться легче.
    grown = _natural_near(world, city)
    if grown is not None and rng.chance(MIXED_CHANCE):
        shape = rng.choice(list(cat.SHAPES_BY_NEED["shrine"]))
        ruler = world.figures.get(getattr(polity, "ruler_id", ""))
        motive = "faith" if shape.key == "shrine" else "glory"
        wonder = _add(ctx, rng, shape, rng.choice(list(shape.grounds)),
                      world.regions.get(grown.region_id), grown.hex_index,
                      rng.choice(shape.about), born_year=year,
                      polity=polity, figure=ruler, motive=motive,
                      cost=rng.choice([key for key, _n, _a in cat.COSTS]))
        if wonder is not None:
            wonder.settlement_id = city.id
            wonder.faith_id = polity.faith_id or ""
            wonder.marks.append({
                "год": year, "что": "построено",
                "отчего": "выросло вокруг чуда по имени %s" % grown.name})
            _ease_access(grown, year)
        return

    pairs = []
    for shape in cat.SHAPES:
        if shape.kind != cat.BUILT:
            continue
        if shape.need == "beacon" and not coast:
            continue
        if shape.need in ("canal", "bridge") and not (river or coast):
            continue
        if shape.need == "temple" and not polity.faith_id:
            continue
        if shape.need == "fortress" and not any(
                item.polity_id == polity.id for item in world.fortresses.values()):
            continue
        if shape.need == "city" and city.population < 20000:
            continue
        pairs.append((shape, shape.weight))
    if not pairs:
        return
    shape = rng.weighted(pairs)
    ground = rng.choice(list(shape.grounds))
    motive = rng.weighted([(key, 2.0 if key in ("faith", "glory", "power")
                            else 1.0) for key, _n, _a in cat.MOTIVES])
    cost = rng.choice([key for key, _n, _a in cat.COSTS])
    ruler = world.figures.get(getattr(polity, "ruler_id", ""))
    wonder = _add(ctx, rng, shape, ground, region,
                  city.hex_index if city.hex_index is not None else -1,
                  rng.choice(shape.about), born_year=year,
                  polity=polity, figure=ruler, motive=motive, cost=cost)
    if wonder is None:
        return
    wonder.settlement_id = city.id
    wonder.faith_id = polity.faith_id or ""
    wonder.marks.append({"год": year, "что": "построено",
                         "отчего": cat.MOTIVES_BY_KEY.get(
                             motive, ("", ""))[0]})
    wonder.effects = [key for key, _n, _a in cat.EFFECTS
                      if rng.chance(0.3)][:3]


# ---------------------------------------------------------------------------
# Жизнь чуда
# ---------------------------------------------------------------------------

def _natural_near(world, city):
    """Природное чудо в той же земле, если о нём уже знают.

    Храм ставят при том, к чему уже ходят: у безымянной горы, о которой
    не знает никто, храма не будет.
    """
    for wonder in sorted(world.wonders.values(), key=lambda item: item.id):
        shape = cat.SHAPES_BY_KEY.get(wonder.shape)
        if shape is None or shape.kind != cat.NATURAL:
            continue
        if wonder.state in cat.LOST_STATES or wonder.fame < 2:
            continue
        if wonder.region_id and wonder.region_id == city.region_id:
            return wonder
    return None


EASIER = {"none": "grim", "grim": "hard", "hard": "fair", "fair": "easy"}


def _ease_access(wonder, year: int) -> None:
    """Лестница и дорога делают своё: дойти стало проще, чем было."""
    step = EASIER.get(wonder.access)
    if step is None:
        return
    wonder.access = step
    if step in ("fair", "easy"):
        wonder.access_why = ""
    wonder.marks.append({"год": year, "что": "дорога",
                         "отчего": "к нему проложили путь, и ходить стало "
                                   "проще"})


def _tick(ctx, wonder, year: int, rng, scale: float) -> None:
    world = ctx.world
    if wonder.born.year > year:
        return
    if wonder.state in (cat.GONE,):
        return

    # --- беда может его сломать ----------------------------------------
    hurt = _woe_here(world, wonder, year)
    if hurt is not None and wonder.state not in cat.LOST_STATES:
        _break(ctx, wonder, year, rng, hurt)
        return

    # --- держава пала — ходить стало некому -----------------------------
    if wonder.polity_id and wonder.state == cat.STANDS:
        polity = world.polities.get(wonder.polity_id)
        if polity is not None and polity.status != ACTIVE \
                and rng.chance(0.25 * scale):
            _move_state(ctx, wonder, year, rng, cat.LEFT,
                        "держава, что его держала, кончилась")
            return

    # --- слава ходит сама ----------------------------------------------
    if wonder.state in (cat.STANDS, cat.FIXED, cat.FOUND, cat.HURT):
        if rng.chance(FAME_RATE * scale) \
                and wonder.fame < _fame_cap(world, wonder):
            wonder.fame += 1
            wonder.peak_fame = max(wonder.peak_fame, wonder.fame)
            if wonder.fame >= 4:
                title, text = texts.fame_moved(rng, wonder, True)
                world.add_event(
                    date=ctx.date_in(rng, year),
                    era_index=world.era_index_at(year),
                    kind="wonder_fame", title=title, text=text,
                    importance=2, region_id=wonder.region_id,
                    subjects=[wonder.id])
        if wonder.fame >= VOICE_FAME and len(wonder.voices) < 3 \
                and rng.chance(0.08 * scale):
            _add_voice(world, wonder, rng)
    else:
        if rng.chance(FORGET_RATE * scale) and wonder.fame > 0:
            wonder.fame -= 1
            if wonder.fame == 0 and wonder.state not in cat.LOST_STATES:
                _move_state(ctx, wonder, year, rng, cat.FORGOT,
                            "о нём перестали рассказывать, а потом и помнить")

    # --- утраченное находят снова ---------------------------------------
    if wonder.state in cat.LOST_STATES:
        last = wonder.marks[-1].get("год", wonder.born.year) \
            if wonder.marks else wonder.born.year
        rate = FOUND_RATE * (5.0 if _peopled(world, wonder.region_id) else 1.0)
        if year - int(last) >= FOUND_QUIET and rng.chance(rate * scale):
            _move_state(ctx, wonder, year, rng, cat.FOUND,
                        "в эту землю вернулись жить, и вернулись к нему"
                        if _peopled(world, wonder.region_id)
                        else "его нашли те, кто искал совсем не его")
    elif wonder.state in (cat.RUINS, cat.HURT) \
            and rng.chance(FIX_RATE * scale):
        # Поднять заново можно стену и храм. Лес и озеро никто не
        # «восстанавливает» — они оправляются сами, и причина у этого
        # своя, а не державная.
        shape = cat.SHAPES_BY_KEY.get(wonder.shape)
        if shape is not None and shape.kind == cat.NATURAL:
            _move_state(ctx, wonder, year, rng, cat.STANDS,
                        "прошло столько лет, что следов беды уже не видно")
        else:
            _move_state(ctx, wonder, year, rng, cat.FIXED,
                        "нашлась держава, которой это понадобилось")


def _fame_cap(world, wonder) -> int:
    """Выше этого о нём не узнают, сколько бы оно ни стояло.

    Слава не растёт сама по себе: её разносят люди. О крупнейшем озере
    мира можно не знать вовсе, если вокруг него не живёт никто, а до
    места, куда за век дошли единицы, слава доходит так же редко, как
    эти единицы.
    """
    near = 0
    if wonder.region_id:
        near = sum(1 for item in world.settlements.values()
                   if item.region_id == wonder.region_id)
    level = 2 + min(3, near // 3)
    if wonder.ground in ("alone", "size", "danger"):
        level += 1
    if wonder.access in ("grim", "none"):
        level -= 1
    # Верхняя ступень — «о нём поют, и половина спетого неправда». До
    # неё доходит не всякое чудо, а то, которое занесли в свои списки
    # сразу несколько народов: песню надо кому-то спеть.
    if len(wonder.lists) >= 2:
        level += 1
    return max(1, min(cat.TOP_FAME, level))


def _woe_here(world, wonder, year: int):
    """Беда, которая в этом десятилетии прошла по земле чуда."""
    if not wonder.region_id:
        return None
    for item in world.calamities.values():
        if wonder.region_id not in (item.region_ids or ()):
            continue
        begin = item.start.year if item.start else 0
        end = item.end.year if item.end else year
        if begin <= year <= end and year - begin < 20:
            return item
    return None


# Насколько далеко зашла порча. Беда двигает чудо только вниз по этой
# лестнице; наверх его поднимают люди — находкой или починкой.
HARM = {cat.STANDS: 0, cat.FIXED: 0, cat.FOUND: 0, cat.FORGOT: 1,
        cat.LEFT: 1, cat.HURT: 2, cat.SEALED: 2, cat.BURIED: 3,
        cat.SUNK: 3, cat.RUINS: 3, cat.GONE: 4}


def _worse(state: str, than: str) -> bool:
    return HARM.get(state, 0) > HARM.get(than, 0)


def _peopled(world, region_id: str) -> bool:
    """Живут ли в этой земле сейчас — то есть есть ли кому помнить."""
    if not region_id:
        return False
    for item in world.settlements.values():
        if item.region_id == region_id and item.status == ACTIVE:
            return True
    return False


def _break(ctx, wonder, year: int, rng, woe) -> None:
    """Беда берёт чудо — и берёт по-разному, смотря какое оно."""
    world = ctx.world
    shape = cat.SHAPES_BY_KEY.get(wonder.shape)
    heavy = getattr(woe, "severity", 2)
    # Гору нельзя «разрушить до основания», а храм можно: у природного
    # чуда свой список концов, и «от него не осталось ничего» в него не
    # входит. Иначе беда сносит реку, и летопись врёт вслух.
    built = shape is not None and shape.kind == cat.BUILT
    if built:
        pairs = [(cat.HURT, 3.0)]
        if heavy >= 3:
            pairs.append((cat.RUINS, 2.0))
        if heavy >= 4:
            pairs.append((cat.GONE, 1.0))
            pairs.append((cat.BURIED, 0.8))
            if shape.need in ("city", "beacon", "canal", "bridge"):
                pairs.append((cat.SUNK, 1.4))
        chance = min(0.8, 0.12 + 0.12 * heavy)
    else:
        # Беда уносит не гору, а тех, кто о ней рассказывал. Поэтому у
        # природного чуда обычный исход беды — забвение, а испортить
        # беда может только то, что горит, сохнет и мелеет.
        pairs = []
        # Забыть гору можно только одним способом: уйти от неё. Пока в
        # земле живут, о величайшей реке мира рассказывать есть кому,
        # сколько бы бед по ней ни прошло.
        if heavy >= 3 and not _peopled(world, wonder.region_id):
            pairs.append((cat.FORGOT, 2.0))
        if heavy >= 3 and shape is not None and shape.need in MARRABLE:
            pairs.append((cat.HURT, 1.5))
        if heavy >= 4 and shape is not None and shape.need in ("isle", "cave",
                                                               "lair"):
            pairs.append((cat.SUNK if shape.need == "isle" else cat.BURIED,
                          1.0))
        if not pairs:
            return
        chance = min(0.4, 0.05 * heavy)
    # Беда не чинит. Если от чуда уже остались стены, следующая беда
    # может его добить или занести, но «повреждено» после «в руинах» —
    # это шаг назад, и в летописи он читается как ошибка.
    pairs = [(state, weight) for state, weight in pairs
             if _worse(state, wonder.state)]
    if not pairs or not rng.chance(chance):
        return
    state = rng.weighted(pairs)
    _move_state(ctx, wonder, year, rng, state,
                "по этой земле прошло бедствие по имени %s" % woe.name)


def _move_state(ctx, wonder, year: int, rng, state: str, why: str) -> None:
    world = ctx.world
    if wonder.state == state:
        return
    wonder.state = state
    wonder.marks.append({"год": year, "что": state, "отчего": why})
    if state in cat.LOST_STATES:
        wonder.fame = max(0, wonder.fame - 1)
    title, text = texts.state_moved(rng, wonder, why)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="wonder_state", title=title, text=text,
        importance=4 if state in (cat.GONE, cat.SUNK) else 3,
        region_id=wonder.region_id, subjects=[wonder.id])


def _add_voice(world, wonder, rng) -> None:
    """Ещё одна правда о том же самом."""
    said = {row.get("чей") for row in wonder.voices}
    pool = [key for key, _n, _a in cat.VOICES if key not in said]
    if not pool:
        return
    whose = rng.choice(pool)
    about = cat.VOICES_BY_KEY[whose][1]
    wonder.voices.append({"чей": whose, "что": about})


# ---------------------------------------------------------------------------
# Списки чудес
# ---------------------------------------------------------------------------

COUNT_WORDS = {3: "Три", 4: "Четыре", 5: "Пять", 6: "Шесть", 7: "Семь",
               8: "Восемь", 9: "Девять"}


def _list_name(count: int, said: str) -> str:
    """«Семь чудес державы по имени X» — числительное словом и в падеже."""
    return "%s %s %s" % (COUNT_WORDS.get(count, "Несколько"),
                         plural(count, "чудо", "чуда", "чудес"), said)


def _holders(world, year: int) -> list:
    """Кому считать чудеса: державам и народам, у которых есть что считать.

    Список чудес составляет не всякий: нужна держава в силе или народ,
    расселившийся так широко, что ему есть чем мериться с соседями.
    Поэтому счёт идёт не по одному из них, а по всем, у кого на земле
    нашлось хотя бы три чуда.

    Оборотов о составителе два: один для имени списка («Семь чудес
    державы по имени X»), другой для самого текста («в державе по имени
    X» — или «у народа по имени X», потому что народ не держава).
    """
    rows = []
    for polity in world.polities.values():
        if polity.status != ACTIVE or polity.population < BUILT_SOULS:
            continue
        lands = {item.region_id for item in world.settlements.values()
                 if item.polity_id == polity.id and item.region_id}
        rows.append(("держава", polity.id,
                     "державы по имени %s" % polity.full_name,
                     "в державе по имени %s" % polity.full_name,
                     lands, float(polity.population)))
    for folk in world.folks.values():
        if folk.status != ACTIVE or folk.population < BUILT_SOULS:
            continue
        lands = {item.region_id for item in world.settlements.values()
                 if item.folk_id == folk.id and item.region_id}
        rows.append(("народ", folk.id, "народа по имени %s" % folk.name,
                     "у народа по имени %s" % folk.name,
                     lands, float(folk.population)))
    rows.sort(key=lambda row: (-row[5], row[1]))
    return rows


def _compile_list(ctx, year: int, rng) -> None:
    """«Семь чудес такой-то державы» — и спор, переживший составителей."""
    world = ctx.world
    rows = world.notes.setdefault("списки чудес", [])
    if len(rows) >= LIST_CAP:
        return
    taken = {row.get("чей") for row in rows}
    for kind, holder_id, said, where, lands, _souls in _holders(world, year):
        if holder_id in taken:
            continue
        mine = [wonder for wonder in sorted(world.wonders.values(),
                                            key=lambda item: (-item.fame,
                                                              item.id))
                if wonder.region_id in lands and wonder.born.year <= year]
        if len(mine) < LIST_LEAST:
            continue
        count = min(len(mine), rng.randint(LIST_LEAST, 9))
        chosen = mine[:count]
        name = _list_name(count, said)
        why = rng.choice(texts.LIST_WHYS)
        rows.append({"имя": name, "чей": holder_id, "род": kind,
                     "год": year, "почему": why,
                     "чудеса": [item.id for item in chosen]})
        for wonder in chosen:
            wonder.lists.append(name)
            # Прибавку даёт только первый список: во второй и третий его
            # вносят потому, что о нём уже знают, а не наоборот.
            if len(wonder.lists) == 1:
                wonder.fame = min(_fame_cap(world, wonder), wonder.fame + 1)
                wonder.peak_fame = max(wonder.peak_fame, wonder.fame)
        title, text = texts.wonder_list(rng, name, where, count, why)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="wonder_list", title=title, text=text, importance=3,
            subjects=[item.id for item in chosen])
        return


# ---------------------------------------------------------------------------
# Ложное чудо
# ---------------------------------------------------------------------------

def _expose(ctx, year: int, rng) -> None:
    """Чудом его звали, а чудом оно не было."""
    world = ctx.world
    pool = [wonder for wonder in sorted(world.wonders.values(),
                                        key=lambda item: item.id)
            if not wonder.claimed and wonder.born.year < year
            and wonder.ground in DOUBTFUL]
    if not pool:
        return
    wonder = rng.choice(pool)
    wonder.claimed = True
    wonder.truth = rng.choice((
        "это обычное место, и всё, что о нём говорят, сложили позже",
        "его назвали чудом нарочно: держава нуждалась в чуде",
        "его спутали с другим — тем, которого больше нет",
        "чудом было не оно, а то, что когда-то стояло рядом",
    ))
    wonder.marks.append({"год": year, "что": "оспорено",
                         "отчего": wonder.truth})
    title, text = texts.false_wonder(rng, wonder)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="wonder_doubt", title=title, text=text, importance=2,
        region_id=wonder.region_id, subjects=[wonder.id])


def at_hex(world, index: int) -> list:
    """Чудеса этого гекса — для страницы места."""
    if index < 0:
        return []
    return [wonder for wonder in sorted(world.wonders.values(),
                                        key=lambda item: item.id)
            if wonder.hex_index == index]


__all__ = ["prepare", "upkeep", "at_hex"]
