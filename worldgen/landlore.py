# -*- coding: utf-8 -*-
"""Земля под ногами: условия места и его вес в истории — прозой.

Беда, которую это лечит: карта отвечала на вопрос «что тут нарисовано», а
не «что это за место». В карточке гекса стояли числа — высота, тепло,
влага, плодородие, — и по ним человек должен был сам догадаться, можно ли
тут жить и стоит ли тут что-нибудь искать. Числа знает движок; человеку
нужна фраза.

Тут три разные вещи, и держатся они врозь.

**Условия.** Что это за место и каково в нём: крут ли склон, какая разница
между летом и зимой, хватает ли воды, родит ли земля, чем кормиться, что
под ногами, каков нрав округи и чем она грозит. Всё — из того, что карта
про гекс и так знает; выдумки тут нет ни одной.

**Вес в истории.** Девять гексов из десяти — это место, где не случилось
ничего, и так и должно быть. Поэтому вес считается по настоящим
следам (годы города, битвы, осады, беды, шрамы творения, места истории,
были) и честно говорит «ничего», когда ничего и не было. Если весомым
объявить каждый камень, весомого в мире не останется.

**Летопись места.** Всё, что в этом гексе случилось, по годам: от
основания города до того, как его оставили, от битвы до раскопанной
могилы. Летопись мира и реестры мира знают об одном и том же, и строка
тут не повторяется: где о факте сказала летопись, реестр молчит.

Текст собирается по сиду мира и номеру гекса: один и тот же гекс читается
одинаково, сколько бы раз его ни открывали, — но два похожих гекса
описаны разными словами. Своего ГСЧ у мира это не трогает: поток тут
отдельный и к порядку мировых бросков отношения не имеет.

Считается всё на лету и только по запросу. Держать страницу в памяти
незачем: гексов на большой карте полтораста тысяч, и открывают из них по
одному.
"""

from __future__ import annotations

from . import worldmap as wm
from .mapregions import FEATURE_NOUNS, translit
from .rng import RngHub
from .timeline import plural
from .worldforge import BIOME_NAMES

# Те же слова, что в карточке карты: расходиться им нельзя.
AQUIFER_NAMES = ("нет", "лёгкий", "тяжёлый")
SAVAGERY_NAMES = ("кроткое", "вольное", "лютое")
SPIRIT_NAMES = ("злое", "нейтральное", "доброе")
RIVER_CLASSES = ("—", "ручей", "река", "большая река")
EVENT_NAMES = (
    "Ураган", "Песчаная буря", "Снежный буран", "Извержение", "Паводок",
    "Лесной пожар", "Лавина", "Цунами", "Засуха", "Поветрие",
    "Землетрясение", "Урожайный год", "Рыбный ход", "Мягкий сезон",
    "Северное сияние", "Цветение",
)


def cap(line: str) -> str:
    return line[:1].upper() + line[1:] if line else line


# Род слова, которым зовут поселение. У каждой расы свои слова, и
# «оставленный чертог» с «оставленной гаванью» — разные слова. Поэтому
# род хранится рядом со словом, как и везде в этом проекте: гадать по
# окончанию нельзя, «пристань» и «оазис» кончаются по-разному, чем
# выглядят.
PLACE_GENDER = {
    "город": "m", "городище": "n", "крепость": "f", "порт": "m",
    "застава": "f", "торжище": "n", "чертог": "m", "твердыня": "f",
    "рудник": "m", "город-кузня": "m", "приют": "m", "святилище": "n",
    "пристань": "f", "башня": "f", "гавань": "f", "яма": "f",
    "подземный город": "m", "оазис": "m", "стойбище": "n",
    "медвежий двор": "m", "гнездовье": "n", "утёсный город": "m",
    "дозор": "m", "колония": "f", "выселок": "m", "село": "n",
    "городок": "m", "большой город": "m", "великий город": "m",
}


def gender_of(word: str) -> str:
    """Какого рода это слово. Неизвестное считается мужским."""
    return PLACE_GENDER.get((word or "").strip().lower(), "m")


def agree(gender: str, forms) -> str:
    """Поставить прилагательное или глагол в нужный род.

    `forms` — четвёрка (м, ж, с, мн). Четвёртое нужно оттого, что
    «руины» — слово множественное, и «руины стоял» не говорят.
    """
    return {"m": forms[0], "f": forms[1], "n": forms[2],
            "p": forms[3] if len(forms) > 3 else forms[2]}.get(gender,
                                                               forms[0])


# Нрав округи — своими словами, согласованными с «нравом», а не теми,
# какими карта метит сам слой: там это пометка, а тут — фраза.
TEMPER_WORDS = ("кроткий", "вольный", "лютый")


def _map_of(world):
    """Карта мира — или ничего, если мир построен без карты."""
    link = getattr(world, "map_link", None)
    return getattr(link, "wmap", None) if link is not None else None


def _rng(world, index: int, mark: str = ""):
    """Свой поток: текст о месте не должен двигать мировые броски."""
    return RngHub(getattr(world, "seed_value", 0)).stream("land", mark, index)


def _value(wmap, layer_id, index, default=0.0):
    data = wmap.layer(layer_id)
    return float(data[index]) if data is not None else default


# ---------------------------------------------------------------------------
# Условия: каково в этом месте
# ---------------------------------------------------------------------------

# Склон считается по разнице с соседями: это единственное, чего в слоях
# прямо не записано, а человеку оно важнее самой высоты — по крутизне
# видно, пройдёт ли тут обоз и встанет ли город.
SLOPE_WORDS = (
    (420, "обрыв: пешему тут не пройти, не говоря об обозе"),
    (220, "крутой склон — тропа есть, дороги не будет"),
    (90, "косогор: идти можно, но телегу придётся вести"),
    (30, "пологий склон"),
    (0, "ровное место"),
)

# То же самое одним словом — для карточки, где на строку отведено место
# в три пальца, а не в три фразы.
LIVE_SHORT = (
    (0.78, "привольно"),
    (0.58, "сносно"),
    (0.40, "впроголодь"),
    (0.22, "трудно"),
    (0.0, "нельзя"),
)

LIVE_WORDS = (
    (0.78, "Жить тут легко, и потому тут жили всегда"),
    (0.58, "Жить тут можно, и земля за труд платит"),
    (0.40, "Жить тут можно, но впроголодь"),
    (0.22, "Жить тут трудно: держатся те, кому некуда уйти"),
    (0.0, "Жить тут нельзя — приходят и уходят"),
)


def _slope(wmap, index: int) -> float:
    """Перепад с самым далёким по высоте соседом, в метрах."""
    here = wmap.elevation_m(index)
    best = 0.0
    for other in wmap.neighbors(index):
        best = max(best, abs(wmap.elevation_m(other) - here))
    return best


def _habitable(wmap, index: int) -> float:
    """Насколько тут вообще можно жить, 0…1.

    Считается из того же, из чего это считает всякий человек: тепло,
    вода, родит ли земля и насколько дика округа. Это не оценка красоты
    места, а ответ на вопрос «останусь ли я тут на зиму».
    """
    if not wmap.is_land(index):
        return 0.0
    temp = _value(wmap, wm.L_TEMP, index)
    moist = _value(wmap, wm.L_MOIST, index)
    fert = _value(wmap, wm.L_FERTILITY, index)
    savage = _value(wmap, wm.L_SAVAGERY, index) / 255.0
    # Тепло: лучше всего около +14, хуже — в обе стороны.
    warm = max(0.0, 1.0 - abs(temp - 14.0) / 32.0)
    wet = 1.0 - abs(moist - 0.55) / 0.7
    wet = max(0.0, min(1.0, wet))
    good = 0.34 * warm + 0.22 * wet + 0.3 * min(1.0, fert) \
        + 0.14 * (1.0 - savage)
    if _slope(wmap, index) > 300:
        good -= 0.12
    return max(0.0, min(1.0, good))


def _pick(rows, value):
    for edge, word in rows:
        if value >= edge:
            return word
    return rows[-1][1]


def live_word(wmap, index: int) -> str:
    """Можно ли тут жить — одним словом. Этим пользуется карточка карты.

    Нарочно одно место на две панели: если карточка и полная страница
    считают пригодность каждая по-своему, об одном месте они скажут
    разное, и доверия не будет ни той, ни другой.
    """
    return _pick(LIVE_SHORT, _habitable(wmap, index))


def conditions(world, index: int) -> list:
    """Каково в этом месте — абзацами, а не столбиком чисел."""
    wmap = _map_of(world)
    if wmap is None:
        return ["Этот мир построен без карты: гексов в нём нет, и говорить "
                "о месте нечего."]
    rng = _rng(world, index, "cond")
    rows = []

    # --- что это за место ---------------------------------------------
    biome = int(_value(wmap, wm.L_BIOME, index))
    name = BIOME_NAMES[biome] if biome < len(BIOME_NAMES) else "неведомая земля"
    height = round(wmap.elevation_m(index))
    if wmap.is_ocean(index):
        deep = abs(height)
        how = ("дно тут близко, и всё, что живёт в море, живёт на нём"
               if deep < 200 else
               "дна тут не достать ничем" if deep > 2000 else
               "глубина обычная для этих вод")
        rows.append("Это открытая вода: %s, глубина %d м — %s. Земли тут "
                    "нет и не было." % (name.lower(), deep, how))
    elif wmap.is_lake(index):
        rows.append("Это озеро: %s. Берег близко со всех сторон."
                    % name.lower())
    else:
        slope = _slope(wmap, index)
        rows.append("Это %s на высоте %d м над морем. %s."
                    % (name.lower(), height,
                       cap(_pick(SLOPE_WORDS, slope))))

    # --- времена года --------------------------------------------------
    temp = _value(wmap, wm.L_TEMP, index)
    swing = 4.0 + 26.0 * abs(wmap.latitude(index))
    summer, winter = temp + swing / 2.0, temp - swing / 2.0
    if not wmap.is_land(index):
        rows.append("Над водой лето около %+.0f, зима около %+.0f.%s"
                    % (summer, winter,
                       " Зимой вода тут встаёт, и до весны пути нет."
                       if winter <= -2 else
                       " Льда тут не бывает, и ходить можно круглый год."
                       if winter >= 6 else
                       " Лёд тут бывает не всякую зиму."))
    elif swing >= 30:
        rows.append("Год тут делится надвое: лето около %+.0f, зима около "
                    "%+.0f. Разница в %d градусов — это два разных уклада в "
                    "одном месте, и переход между ними всякий раз даётся "
                    "тяжело." % (summer, winter, round(swing)))
    elif swing >= 15:
        rows.append("Лето около %+.0f, зима около %+.0f: времена года тут "
                    "настоящие, и к каждому готовятся заранее."
                    % (summer, winter))
    elif swing >= 8:
        rows.append("Лето около %+.0f, зима около %+.0f: разница есть, но "
                    "зима тут — это не беда, а неудобство."
                    % (summer, winter))
    else:
        rows.append("Лето и зима тут почти не отличаются (%+.0f и %+.0f): "
                    "год идёт ровно, и считать его приходится не по погоде, "
                    "а по звёздам." % (summer, winter))

    # --- вода ----------------------------------------------------------
    water = []
    if wmap.is_river(index):
        flow = _value(wmap, wm.L_ACCUM, index)
        level = 3 if flow >= 120 else (2 if flow >= 20 else 1)
        water.append("через место идёт %s" % RIVER_CLASSES[level])
    if wmap.is_coast(index):
        water.append("тут берег")
    if wmap.is_lake(index):
        water.append("тут озеро")
    aqua = int(_value(wmap, wm.L_AQUIFER, index))
    moist = _value(wmap, wm.L_MOIST, index)
    if wmap.is_land(index):
        if aqua >= 2:
            water.append("грунтовая вода глубоко, и колодец тут — работа на "
                         "год")
        elif aqua == 1:
            water.append("колодец копать недолго")
        else:
            water.append("грунтовой воды нет вовсе")
        if moist >= 0.7:
            water.append("сырость стоит круглый год")
        elif moist <= 0.25:
            water.append("сухо: дождя ждут неделями")
        if water:
            rows.append(cap(", ".join(water)) + ".")

    # --- земля и чем кормиться -----------------------------------------
    if wmap.is_land(index):
        fert = _value(wmap, wm.L_FERTILITY, index)
        tail = wmap.tail.get("resources") or {}
        buckets = tail.get("densityBuckets") or ()
        rich = int(_value(wmap, wm.L_RICHNESS, index))
        food = []
        if fert >= 0.7:
            food.append("пашня тут родит без уговоров")
        elif fert >= 0.4:
            food.append("пахать можно, но с навозом и терпением")
        elif fert >= 0.15:
            food.append("пашня тут не кормит: разве что огород")
        else:
            food.append("землю тут не пашут вовсе")
        if buckets:
            level = min(len(buckets) - 1, rich * len(buckets) // 256)
            food.append("живность тут %s" % buckets[level].lower())
        by_biome = (tail.get("biomes") or {}).get(str(biome)) or {}
        products = tail.get("products") or []
        names = [products[number] for number in (by_biome.get("products") or ())
                 if 0 <= number < len(products)]
        if names:
            # Через двоеточие: товар хранится в именительном падеже, а
            # «берут мясо, шкуры, кожа» — не по-русски.
            food.append("а берут с этой земли вот что: %s"
                        % ", ".join(names[:4]))
        rows.append(cap("; ".join(food)) + ".")

    # --- можно ли тут жить ----------------------------------------------
    if wmap.is_land(index):
        good = _habitable(wmap, index)
        why = []
        if _value(wmap, wm.L_FERTILITY, index) < 0.2:
            why.append("земля не родит")
        if temp < -5:
            why.append("холод")
        elif temp > 28:
            why.append("жара")
        if moist <= 0.2:
            why.append("нет воды")
        if _value(wmap, wm.L_SAVAGERY, index) >= 168:
            why.append("округа дикая")
        line = _pick(LIVE_WORDS, good)
        if why and good < 0.58:
            line += ": " + ", ".join(why)
        rows.append(line + ".")

    # --- нрав округи ----------------------------------------------------
    if wmap.is_land(index):
        savage = _value(wmap, wm.L_SAVAGERY, index)
        magic = _value(wmap, wm.L_MAGIC, index)
        level = 2 if savage >= 168 else (1 if savage >= 84 else 0)
        spirit = 2 if magic > 0.12 else (0 if magic < -0.12 else 1)
        said = []
        names = (wmap.tail.get("surroundings") or {}).get("names") or ()
        place = level * 3 + spirit
        if 0 <= place < len(names):
            said.append("округу зовут так: %s" % names[place].lower())
        said.append("нрав её %s" % TEMPER_WORDS[level])
        if abs(magic) > 0.05:
            said.append("сила тут %s и стоит %s"
                        % ("светлая" if magic > 0 else "тёмная",
                           "густо" if abs(magic) > 0.25 else "негусто"))
        elif spirit == 1:
            said.append("силы тут нет ни той, ни другой")
        rows.append(cap("; ".join(said)) + ".")

    # --- чем грозит -----------------------------------------------------
    mask = int(_value(wmap, wm.L_EVENTMASK, index))
    if mask:
        threats, gifts = [], []
        for number in range(len(EVENT_NAMES)):
            if not mask & (1 << number):
                continue
            (gifts if number >= 11 else threats).append(
                EVENT_NAMES[number].lower())
        if threats:
            rows.append("Чего тут ждать: %s. %s"
                        % (", ".join(threats),
                           rng.choice((
                               "Местные знают это наперёд и строятся с "
                               "оглядкой.",
                               "Об этом тут помнят и приезжим не "
                               "рассказывают.",
                               "Раз в поколение это случается всерьёз."))))
        if gifts:
            rows.append("А ещё тут бывает доброе: %s." % ", ".join(gifts))

    # --- что под ногами --------------------------------------------------
    ores = wmap.minerals.get(str(index)) or ()
    if ores:
        parts = ["%s (%s)" % (item[0].lower(), item[1]) for item in ores[:6]]
        rows.append("Под ногами лежит: %s." % ", ".join(parts))
    elif wmap.is_land(index):
        rows.append("Недра тут пусты — по крайней мере, на той глубине, до "
                    "которой доходили.")
    return rows


# ---------------------------------------------------------------------------
# Что на этом месте стоит и стояло
# ---------------------------------------------------------------------------

def _anchors(world, index: int) -> dict:
    """Всё, что привязано к этому гексу: города, места, крепости, станы."""
    out = {"settlements": [], "sites": [], "fortresses": [], "camps": [],
           "tribes": []}
    for item in world.settlements.values():
        if item.hex_index == index:
            out["settlements"].append(item)
    for item in world.sites.values():
        if getattr(item, "hex_index", -1) == index:
            out["sites"].append(item)
    for item in world.fortresses.values():
        if getattr(item, "hex_index", -1) == index:
            out["fortresses"].append(item)
    for item in world.camps.values():
        if getattr(item, "hex_index", -1) == index:
            out["camps"].append(item)
    for item in world.tribes.values():
        if getattr(item, "hex_index", -1) == index:
            out["tribes"].append(item)
    for rows in out.values():
        rows.sort(key=lambda item: (len(item.id), item.id))
    return out


def _region_of(world, index: int):
    link = getattr(world, "map_link", None)
    region_id = (getattr(link, "region_of_hex", {}) or {}).get(index)
    return world.regions.get(region_id) if region_id else None


def features(world, index: int) -> list:
    """Что на этом гексе отмечено самой картой: хребет, вершина, логово."""
    wmap = _map_of(world)
    if wmap is None:
        return []
    out = []
    for feature in (wmap.features or ()):
        layer_id = {"ocean": wm.L_WATERREG, "sea": wm.L_WATERREG,
                    "bay": wm.L_WATERREG, "lake": wm.L_WATERREG,
                    "inlandsea": wm.L_WATERREG,
                    "continent": wm.L_LANDREG, "island": wm.L_LANDREG,
                    "bigisland": wm.L_LANDREG, "archipelago": wm.L_LANDREG,
                    "range": wm.L_RANGEREG,
                    "river": wm.L_RIVERREG}.get(feature.get("type"))
        if layer_id is None:
            continue
        data = wmap.layer(layer_id)
        if data is not None and data[index] == feature.get("id"):
            noun = FEATURE_NOUNS.get(feature.get("type"), "")
            said = translit(feature.get("name", ""))
            out.append("%s по имени %s" % (noun, said) if noun else said)
    for peak in (wmap.peaks or ()):
        if peak.get("i") == index:
            said = str(peak.get("name", ""))
            said = said[3:] if said.startswith("г. ") else said
            out.append("вершина по имени %s, %d м"
                       % (translit(said), peak.get("m", 0)))
    for volcano in (wmap.volcanoes or ()):
        if volcano.get("i") == index:
            out.append("вулкан по имени %s (%s)"
                       % (translit(volcano.get("name", "")),
                          volcano.get("status")))
    for lair in (wmap.lairs or ()):
        if lair.get("i") == index:
            out.append("логово: %s по имени %s"
                       % (lair.get("kindName"),
                          translit(lair.get("name", ""))))
    return out


def _alive_at(began, ended, year: int) -> bool:
    if began is not None and began.year > year:
        return False
    return ended is None or ended.year >= year


def standing(world, index: int, year: int = 0) -> list:
    """Что тут стоит на этот год — и что стояло прежде."""
    year = int(year or getattr(world, "total_years", 0))
    rows = []
    found = _anchors(world, index)
    region = _region_of(world, index)
    if region is not None:
        rows.append("Земля эта зовётся %s." % region.name)
    # Живое впереди мёртвого: человек спрашивает прежде всего, что тут
    # есть сейчас, а уж потом — что было до этого.
    alive = [item for item in found["settlements"]
             if _alive_at(item.founded, item.ended, year)]
    gone = [item for item in found["settlements"]
            if item not in alive and item.ended is not None
            and item.ended.year <= year]
    for item in alive:
        polity = world.polities.get(item.polity_id)
        line = "Тут стоит %s — %s" % (
            item.full_name,
            plural(item.population, "%d житель" % item.population,
                   "%d жителя" % item.population,
                   "%d жителей" % item.population))
        if item.is_capital:
            line += ", и это столица"
        if polity is not None:
            line += "; держава — %s" % polity.full_name
        rows.append(line + ".")
        # Прежние имена лежат списком слов без годов, поэтому стоят тут,
        # а не в летописи: сами переименования приходят в летопись
        # событиями, и год там свой.
        if item.old_names:
            rows.append("Прежде это звалось так: %s."
                        % ", ".join(item.old_names))
    for item in gone:
        rows.append("Тут %s %s, %s в %d году (%s)."
                    % (agree(gender_of(item.word),
                             ("стоял", "стояла", "стояло", "стояли")),
                       item.full_name,
                       agree(gender_of(item.word),
                             ("оставленный", "оставленная", "оставленное",
                              "оставленные")),
                       item.ended.year,
                       item.end_reason or "причина не названа"))
    for item in found["fortresses"]:
        if _alive_at(item.built, item.ended, year):
            holder = world.polities.get(item.polity_id)
            rows.append("Тут держат крепость по имени %s%s."
                        % (item.name,
                           " — держава %s" % holder.name if holder else ""))
    for item in found["camps"]:
        if _alive_at(item.founded, item.ended, year):
            rows.append("Тут стоит %s по имени %s."
                        % (item.word.lower(), item.name))
    for item in found["tribes"]:
        if _alive_at(item.founded, item.ended, year):
            rows.append("Тут кочует племя по имени %s — %d душ."
                        % (item.name, item.population))
    for item in found["sites"]:
        made = getattr(item, "created", None)
        if made is None or made.year > year:
            continue
        opened = getattr(item, "opened", None)
        # Отдельной фразой, а не причастием: «руины» — слово
        # множественное, «клад» — мужского рода, и одно причастие на
        # оба не встанет.
        rows.append("Тут есть %s по имени %s." % (item.kind, item.name))
        if getattr(item, "story", ""):
            rows.append("   %s" % item.story)
        rows.append("   %s" % ("внутрь входили в %d году" % opened.year
                               if opened is not None and opened.year <= year
                               else "внутрь никто не входил"))
    for line in features(world, index):
        rows.append(cap(line) + ".")
    if not rows:
        rows.append("На этом месте ничего нет и не было.")
    return rows


# ---------------------------------------------------------------------------
# Вес места в истории
# ---------------------------------------------------------------------------

# Потолок каждого вида следа. Без потолков вес на долгой истории
# рассыпается: за десять тысяч лет на одном гексе сменяется восемь
# городов, и одни их годы дают сотню. Мерено на Ясене-7: без потолков
# самое весомое место весило 496, а «мест, повернувших историю» выходило
# сорок шесть из ста двадцати — то есть приговор ничего уже не значил.
# С потолками больше сорока восьми не выходит ни у кого, и верхний
# приговор означает «почти все виды следа разом».
#
# Потолок не делает долгую историю равной короткой: место, где восемь
# веков стоял город, досчитывает свой потолок и останавливается, а место
# с одним хутором не досчитывает. Разница между ними остаётся; исчезает
# только разница между «очень много» и «ещё больше», которой человек
# всё равно не чувствует.
CAP_TOWN_YEARS = 12.0      # сколько весят годы всех городов этого места
CAP_CAPITAL = 4.0          # столичность, сколько бы столиц тут ни было
CAP_CROWD = 2.0            # людность в лучшие годы
CAP_BATTLES = 6.0          # битвы
CAP_SITES = 5.0            # места истории
CAP_FORTS = 3.0            # крепости
CAP_WOES = 2.0             # беды, прошедшие по этой земле
CAP_STORIES = 4.0          # были, выросшие отсюда
CAP_MARKS = 3.0            # то, что отметила сама карта: логово, вулкан
WEIGHT_SCAR = 7.0          # шрам творения — самое тяжёлое, и он один

# Девять мест из десяти — это место, где не случилось ничего. Если
# значимым объявить каждый камень, значимого в мире не останется.
WEIGHT_WORDS = (
    (26.0, "Это одно из тех мест, вокруг которых повернулась история мира."),
    (14.0, "Место известное: о нём знают далеко за пределами своей земли."),
    (7.0, "Место со своей историей — её хватит на целую повесть."),
    (2.5, "Место как место: кое-что тут было, но мир этого не заметил."),
    (0.0, "Тут не случилось ничего, о чём стоило бы писать, — и таких мест "
          "в мире больше всего."),
)


def weight(world, index: int) -> tuple:
    """Вес места: число, приговор и то, из чего он сложился.

    Считается по настоящим следам, а не по красоте земли: сколько лет тут
    стоял город и был ли он столицей, сколько тут было битв и осад, какие
    беды прошли, что из творения мира тут лежит, какие места истории тут
    есть и сколько былей отсюда выросло.
    """
    score = 0.0
    why = []
    found = _anchors(world, index)
    total = max(1, getattr(world, "total_years", 1))

    # --- годы городов, столичность, людность ---------------------------
    town_years = 0.0
    capital = 0.0
    crowd = 0.0
    for item in found["settlements"]:
        begin = item.founded.year if item.founded else 1
        end = item.ended.year if item.ended else total
        years = max(0, end - begin)
        town_years += years / 400.0
        if item.is_capital:
            capital += CAP_CAPITAL
            why.append("тут стояла столица — %s" % item.full_name)
        elif years:
            why.append("город по имени %s стоял тут %s"
                       % (item.name, plural(years, "%d год" % years,
                                            "%d года" % years,
                                            "%d лет" % years)))
        if item.peak_population >= 20000:
            crowd += CAP_CROWD
            why.append("в лучшие годы тут жило %d душ" % item.peak_population)
    score += min(CAP_TOWN_YEARS, town_years)
    score += min(CAP_CAPITAL, capital)
    score += min(CAP_CROWD, crowd)

    # --- битвы ---------------------------------------------------------
    here = {item.id for item in found["settlements"]}
    battles = sum(1 for row in world.battles.values()
                  if row.settlement_id in here)
    if battles:
        score += min(CAP_BATTLES, 1.6 * battles)
        why.append("тут билось войско, и не раз: битв %d" % battles)

    # --- места истории и крепости --------------------------------------
    sites_add = 0.0
    for item in found["sites"]:
        sites_add += 2.2 if getattr(item, "riches", 0) else 1.4
        why.append("%s по имени %s" % (item.kind, item.name))
    score += min(CAP_SITES, sites_add)
    if found["fortresses"]:
        score += min(CAP_FORTS, 1.2 * len(found["fortresses"]))
        why.append("тут держали крепость")

    # Шрам творения — самое тяжёлое, что может лежать в гексе: он старше
    # всякой державы.
    origin = getattr(world, "origin", None)
    if origin is not None:
        site_ids = {item.id for item in found["sites"]}
        for row in origin.scars:
            if row.get("место") and row["место"] in site_ids:
                score += WEIGHT_SCAR
                why.append("тут лежит шрам самого творения: %s"
                           % row.get("имя", ""))

    # Беда шла по всей земле, а не по этому гексу, и считается она только
    # тому месту, где что-то стояло: над пустым камнем беда прошла, и
    # пройти ей было не над кем. Иначе всякий камень в битой земле
    # оказывается «местом со своей историей», и весомого в мире нет.
    region = _region_of(world, index)
    lived = any(found[key] for key in ("settlements", "sites", "fortresses",
                                       "camps", "tribes"))
    if region is not None and lived:
        hits = sum(1 for row in world.calamities.values()
                   if region.id in (row.region_ids or ()))
        if hits:
            score += min(CAP_WOES, 0.25 * hits)
            why.append("по этой земле прошло %s"
                       % plural(hits, "%d бедствие" % hits,
                                "%d бедствия" % hits,
                                "%d бедствий" % hits))

    told = 0
    for item in found["settlements"] + found["sites"]:
        told += len(world.stories_at(item.id))
    if told:
        score += min(CAP_STORIES, 1.3 * told)
        why.append("былей отсюда выросло: %d" % told)

    marks = 0.0
    for line in features(world, index):
        if line.startswith("логово"):
            marks += 2.0
            why.append(line)
        elif line.startswith("вулкан"):
            marks += 1.4
            why.append(line)
        elif line.startswith("вершина"):
            marks += 0.8
    score += min(CAP_MARKS, marks)

    return round(score, 1), _pick(WEIGHT_WORDS, score), why


# ---------------------------------------------------------------------------
# Летопись места
# ---------------------------------------------------------------------------

# О чём говорит запись летописи, если говорит о том же, о чём знает сам
# реестр. Нужно оттого, что реестр и летопись знают об одном: город
# помнит год своего основания, и летопись в тот же год пишет
# «Основание». Печатать обе строки — значит удвоить страницу, не прибавив
# ни слова. Победа остаётся за летописью: она пишет живее.
EVENT_FACT = {
    "settlement_found": "начало", "colony_found": "начало",
    "colony_free": "начало", "colony_overseas": "начало",
    "settlement_ruined": "конец",
    "tribe_found": "начало", "tribe": "начало", "tribe_end": "конец",
    "camp_found": "начало", "camp": "начало", "camp_end": "конец",
    "fortress_built": "начало", "fortress_gone": "конец",
    "fortress_razed": "конец",
    "site_opened": "вскрытие",
}

# Записи о появлении места истории зовутся по виду места: site_tomb,
# site_hoard, site_ruin и так далее. Перечислять их все незачем — хватит
# начала имени и изъятия тех немногих, что говорят о другом.
_SITE_OTHER = ("site_opened", "site_settled", "site_failed")


def _fact_of(kind: str) -> str:
    """Какой факт реестра пересказывает эта запись летописи."""
    said = EVENT_FACT.get(kind, "")
    if said:
        return said
    if kind.startswith("site") and kind not in _SITE_OTHER:
        return "начало"
    return ""


def timeline(world, index: int) -> list:
    """Всё, что в этом гексе случилось, по годам.

    Берётся не по земле, а по самому гексу: записи летописи, привязанные
    к тому, что тут стоит, плюс рождение и конец этого самого. Записи по
    всей земле идут отдельным списком — иначе страница одного места
    превращается в историю целой области.
    """
    rows = []
    found = _anchors(world, index)
    ids = set()
    for kind, items in found.items():
        for item in items:
            ids.add(item.id)

    # Сперва летопись: она и живее, и тут же говорит, о чём уже сказано.
    told = set()
    for event in world.events:
        named = ids.intersection(event.subjects or ())
        if not named:
            continue
        rows.append((event.date.year, event.kind, event.title))
        fact = _fact_of(event.kind)
        if fact:
            for entity_id in named:
                told.add((entity_id, fact))

    def missing(item, fact: str) -> bool:
        return (item.id, fact) not in told

    for item in found["settlements"]:
        if item.founded is not None and missing(item, "начало"):
            rows.append((item.founded.year, "начало",
                         "основан %s" % item.full_name))
        if item.ended is not None and missing(item, "конец"):
            rows.append((item.ended.year, "конец",
                         "%s %s: %s"
                         % (item.full_name,
                            agree(gender_of(item.word),
                                  ("оставлен", "оставлена", "оставлено",
                                   "оставлены")),
                            item.end_reason or "причина не названа")))
    for item in found["fortresses"]:
        if item.built is not None and missing(item, "начало"):
            rows.append((item.built.year, "начало",
                         "поставлена крепость по имени %s" % item.name))
        if item.ended is not None and missing(item, "конец"):
            rows.append((item.ended.year, "конец",
                         "крепость по имени %s пала: %s"
                         % (item.name, item.end_reason or "неизвестно как")))
    for item in found["camps"]:
        if item.founded is not None and missing(item, "начало"):
            rows.append((item.founded.year, "начало",
                         "встал %s по имени %s"
                         % (item.word.lower(), item.name)))
    for item in found["tribes"]:
        if item.founded is not None and missing(item, "начало"):
            rows.append((item.founded.year, "начало",
                         "сюда пришло племя по имени %s" % item.name))
        if item.ended is not None and missing(item, "конец"):
            rows.append((item.ended.year, "конец",
                         "племя по имени %s: %s"
                         % (item.name, item.end_reason or "ушло")))
    for item in found["sites"]:
        made = getattr(item, "created", None)
        if made is not None and missing(item, "начало"):
            # Без глагола: «клад» мужского рода, «руины» —
            # множественного, и один глагол на оба не встанет.
            rows.append((made.year, "начало",
                         "новое место истории: %s по имени %s"
                         % (item.kind, item.name)))
        opened = getattr(item, "opened", None)
        if opened is not None and missing(item, "вскрытие"):
            rows.append((opened.year, "вскрытие",
                         "вскрыли %s по имени %s" % (item.kind, item.name)))
    for battle in world.battles.values():
        if battle.settlement_id in ids and battle.date is not None:
            rows.append((battle.date.year, "битва",
                         "%s: павших %d" % (battle.name, battle.deaths)))

    seen = set()
    out = []
    for year, kind, line in sorted(rows, key=lambda row: (row[0], row[2])):
        key = (year, line)
        if key in seen:
            continue
        seen.add(key)
        out.append((year, kind, line))
    return out


def around(world, index: int) -> list:
    """Что было по всей этой земле — то, что место пережило вместе с ней."""
    region = _region_of(world, index)
    if region is None:
        return []
    rows = []
    for item in world.calamities.values():
        if region.id not in (item.region_ids or ()):
            continue
        begin = item.start.year if item.start else 0
        if item.end is None:
            rows.append((begin, "беда",
                         "%s — началось в %d году и не кончилось"
                         % (item.name, begin)))
        else:
            rows.append((begin, "беда",
                         "%s, %d–%d" % (item.name, begin, item.end.year)))
    for scar in world.scars.values():
        if getattr(scar, "region_id", "") != region.id:
            continue
        made = getattr(scar, "created", None)
        rows.append((made.year if made else 0, "шрам",
                     "шрам на земле: %s" % scar.name))
    for trace in world.traces.values():
        if getattr(trace, "region_id", "") != region.id:
            continue
        made = getattr(trace, "made", None)
        rows.append((made.year if made else 0, "след",
                     "след беды: %s" % trace.full_name))
    return sorted(rows, key=lambda row: (row[0], row[2]))


# ---------------------------------------------------------------------------
# Готовые страницы
# ---------------------------------------------------------------------------

def brief(world, index: int, year: int = 0) -> list:
    """Коротко: что это за место и стоит ли тут что-нибудь. Для карточки."""
    wmap = _map_of(world)
    if wmap is None:
        return ["Мир построен без карты."]
    biome = int(_value(wmap, wm.L_BIOME, index))
    name = BIOME_NAMES[biome] if biome < len(BIOME_NAMES) else "неведомая земля"
    rows = ["## %s" % name,
            "гекс %d — столбец %d, строка %d"
            % (index, index % wmap.width, index // wmap.width),
            "высота ......... %d м" % round(wmap.elevation_m(index))]
    temp = _value(wmap, wm.L_TEMP, index)
    rows.append("тепло .......... %+.1f °C в среднем" % temp)
    if wmap.is_land(index):
        good = _habitable(wmap, index)
        rows.append("житьё .......... %s" % _pick(LIVE_SHORT, good))
    region = _region_of(world, index)
    if region is not None:
        rows.append("земля .......... %s" % region.name)
    score, verdict, _ = weight(world, index)
    rows.append("")
    rows.append("## ЧЕМ ЭТО МЕСТО ВАЖНО")
    rows.append("   вес %.1f — %s" % (score, verdict))
    rows.append("")
    rows.append("## ЧТО ТУТ ЕСТЬ")
    short = [line for line in standing(world, index, year)
             if not line.startswith(" ")]
    for line in short[:9]:
        rows.append("   %s" % line)
    if len(short) > 9:
        rows.append("   …и ещё %d — смотрите «Полные данные»."
                    % (len(short) - 9))
    return rows


def deep(world, index: int) -> list:
    """Продвинутое: числа слоёв, недра, угрозы. То, что скрыто под кнопкой."""
    wmap = _map_of(world)
    if wmap is None:
        return []
    rows = ["", "## ПОДРОБНО О ЗЕМЛЕ"]
    lat = abs(wmap.latitude(index))
    swing = 4.0 + 26.0 * lat
    temp = _value(wmap, wm.L_TEMP, index)
    rows.append("   широта ....... %.2f" % lat)
    rows.append("   лето/зима .... %+.0f / %+.0f" % (temp + swing / 2.0,
                                                     temp - swing / 2.0))
    rows.append("   влага ........ %d %%"
                % round(_value(wmap, wm.L_MOIST, index) * 100))
    if wmap.is_land(index):
        rows.append("   плодородие ... %.2f"
                    % _value(wmap, wm.L_FERTILITY, index))
        rows.append("   перепад ...... %d м" % round(_slope(wmap, index)))
        rows.append("   вода внизу ... %s"
                    % AQUIFER_NAMES[min(2, int(_value(wmap, wm.L_AQUIFER,
                                                      index)))])
        savage = _value(wmap, wm.L_SAVAGERY, index)
        rows.append("   дикость ...... %s"
                    % SAVAGERY_NAMES[2 if savage >= 168
                                     else (1 if savage >= 84 else 0)])
    magic = _value(wmap, wm.L_MAGIC, index)
    if abs(magic) > 0.05:
        rows.append("   магия ........ %+.2f (%s)"
                    % (magic, "светлая" if magic > 0 else "тёмная"))
    plate = wmap.layer(wm.L_PLATE)
    if plate is not None:
        stress = _value(wmap, wm.L_STRESS, index)
        mood = (" (плиты сходятся)" if stress > 0.25 else
                " (плиты расходятся)" if stress < -0.25 else "")
        rows.append("   литоплита .... №%d%s" % (int(plate[index]), mood))
    ores = wmap.minerals.get(str(index)) or ()
    if ores:
        rows.append("")
        rows.append("## НЕДРА")
        for item in ores[:8]:
            rows.append("   %s — %s" % (item[0], item[1]))
    mask = int(_value(wmap, wm.L_EVENTMASK, index))
    if mask:
        marks = [EVENT_NAMES[number] for number in range(len(EVENT_NAMES))
                 if mask & (1 << number)]
        rows.append("")
        rows.append("## СЛУЧАЕТСЯ ТУТ")
        rows.append("   %s" % ", ".join(marks))
    return rows


def blocks(world, index: int, year: int = 0) -> list:
    """Полная страница места кусками: (метка, строка).

    Метка нужна окну: заголовок там идёт другим цветом, а год в строке
    летописи — третьим. Летописи и командной строке метки не нужны, им
    хватает самих строк, и для них есть `chapter`.

    Метки: «title» — имя места, «head» — заголовок раздела, «line» —
    обычная строка, «dated» — строка, начинающаяся с года, «dim» —
    пояснение помельче.
    """
    wmap = _map_of(world)
    if wmap is None:
        return [("line", "Этот мир построен без карты, и говорить о месте "
                         "нечего: гексов в нём нет.")]
    biome = int(_value(wmap, wm.L_BIOME, index))
    name = BIOME_NAMES[biome] if biome < len(BIOME_NAMES) else "неведомая земля"
    region = _region_of(world, index)
    said = "Гекс %d — %s" % (index, name.lower())
    if region is not None:
        said += ", земля по имени %s" % region.name
    out = [("title", said), ("line", "")]

    out.append(("head", "УСЛОВИЯ"))
    out.append(("line", ""))
    for line in conditions(world, index):
        out.append(("line", "  %s" % line))
    out.append(("line", ""))

    score, verdict, why = weight(world, index)
    out.append(("head", "ЧЕМ ЭТО МЕСТО ВАЖНО"))
    out.append(("line", ""))
    out.append(("line", "  %s" % verdict))
    out.append(("dim", "  Вес места в истории: %.1f." % score))
    for line in why[:12]:
        out.append(("line", "  — %s" % cap(line)))
    out.append(("line", ""))

    out.append(("head", "ЧТО ТУТ ЕСТЬ"))
    out.append(("dim", "  на %d год" % (year or getattr(world, "total_years",
                                                        0))))
    out.append(("line", ""))
    for line in standing(world, index, year):
        out.append(("line", "  %s" % line))
    out.append(("line", ""))

    told = timeline(world, index)
    out.append(("head", "ЧТО ТУТ БЫЛО, ПО ГОДАМ"))
    out.append(("line", ""))
    if not told:
        out.append(("line", "  Ничего, о чём осталась бы запись."))
    else:
        # Века названы вехами. У места с долгой историей записей бывает
        # две тысячи, и без вех это стена строк, по которой не найти, где
        # кончилось одно время и началось другое.
        era = None
        for year_of, _kind, line in told:
            now = (year_of - 1) // 100
            if now != era:
                era = now
                if out[-1][1] != "":
                    out.append(("line", ""))
                out.append(("dim", "  %d–%d годы"
                            % (now * 100 + 1, now * 100 + 100)))
            out.append(("dated", "  %6d  %s" % (year_of, line)))
    out.append(("line", ""))

    near = around(world, index)
    if near:
        out.append(("head", "И ЧТО ПРОХОДИЛО ПО ЭТОЙ ЗЕМЛЕ"))
        out.append(("dim", "  это случилось не в самом гексе, а по всей "
                           "земле, к которой он причтён"))
        out.append(("line", ""))
        for year_of, _kind, line in near:
            out.append(("dated", "  %6d  %s" % (year_of, line)))
        out.append(("line", ""))

    for line in deep(world, index):
        if line.startswith("## "):
            out.append(("head", line[3:]))
        elif line:
            out.append(("line", line))
        else:
            out.append(("line", ""))
    while out and out[-1][1] == "":
        out.pop()
    return out


def chapter(world, index: int, year: int = 0) -> list:
    """То же самое строками — для летописи и командной строки."""
    return [text for _tag, text in blocks(world, index, year)]


def best_hex(world) -> int:
    """Самое значимое место мира — чтобы вкладке было что показать сразу.

    Считается не полным весом, а наскоро: полный вес перебирает все битвы
    и все беды мира, и помножить это на две тысячи занятых гексов — значит
    заставить человека ждать на пустом месте. Для первого показа довольно
    того, что видно сразу: сколько лет тут стоял город, был ли он
    столицей, сколько в нём жило в лучшие годы и сколько тут мест истории.
    """
    wmap = _map_of(world)
    if wmap is None:
        return -1
    total = max(1, getattr(world, "total_years", 1))
    score = {}
    for item in world.settlements.values():
        if item.hex_index < 0:
            continue
        begin = item.founded.year if item.founded else 1
        end = item.ended.year if item.ended else total
        add = min(9.0, max(0, end - begin) / 400.0)
        if item.is_capital:
            add += 4.0
        if item.peak_population >= 20000:
            add += 2.0
        score[item.hex_index] = score.get(item.hex_index, 0.0) + add
    # Места истории считаются, но с потолком: гекс с семью курганами не
    # весомее столицы, простоявшей четыреста лет.
    tombs = {}
    for item in world.sites.values():
        if getattr(item, "hex_index", -1) < 0:
            continue
        tombs[item.hex_index] = tombs.get(item.hex_index, 0) + 1
    for index, count in tombs.items():
        score[index] = score.get(index, 0.0) + min(3.0, 1.2 * count)
    if not score:
        return -1
    # По номеру гекса при равном счёте: иначе один и тот же мир открывался
    # бы на разных местах.
    best, best_score = -1, -1.0
    for index in sorted(score):
        if score[index] > best_score:
            best, best_score = index, score[index]
    return best


def notable(world, limit: int = 40) -> list:
    """Десятка-другая мест, с которых стоит начать: (гекс, подпись).

    Нужна вкладке: номер гекса человеку ничего не говорит, а список
    «город такой-то, земля такая-то» говорит сразу.
    """
    wmap = _map_of(world)
    if wmap is None:
        return []
    total = max(1, getattr(world, "total_years", 1))
    rows = {}
    for item in world.settlements.values():
        if item.hex_index < 0:
            continue
        begin = item.founded.year if item.founded else 1
        end = item.ended.year if item.ended else total
        years = max(0, end - begin)
        add = min(9.0, years / 400.0) + (4.0 if item.is_capital else 0.0)
        if item.peak_population >= 20000:
            add += 2.0
        said = item.full_name
        region = world.regions.get(item.region_id)
        if region is not None:
            said += " — земля по имени %s" % region.name
        if item.ended is not None:
            said += " (нет с %d года)" % item.ended.year
        old = rows.get(item.hex_index)
        if old is None or add > old[0]:
            rows[item.hex_index] = (add, said)
    best = sorted(rows.items(), key=lambda row: (-row[1][0], row[0]))
    return [(index, said) for index, (_add, said) in best[:limit]]


__all__ = ["cap", "gender_of", "agree", "live_word", "conditions",
           "standing", "features",
           "weight", "timeline", "around", "brief", "deep", "blocks",
           "chapter", "best_hex", "notable"]
