# -*- coding: utf-8 -*-
"""Расширения Worldforge: живность, бедствия, вода, дичь, логова, племена.

Ядро даёт физику мира — где горы, где дождь, где река. Эти надстройки
говорят, что на этой земле водится, чем она грозит и кто на ней уже
живёт к началу истории. Всё считается от того же сида и той же карты,
так что один сид даёт одну и ту же землю с теми же логовами.

Каждый раздел ложится в .world своим слоем или своей секцией хвоста —
ровно теми номерами, которые ждёт движок истории.
"""

from __future__ import annotations

import math
from array import array
from collections import deque

from .core import _round, make_namer
from .rng import rng_from

# ---------------------------------------------------------------------------
# Живность и добро земли
# ---------------------------------------------------------------------------

PRODUCTS = ('мясо', 'шкуры', 'пушнина', 'кость', 'бивни', 'рога', 'шерсть',
            'молоко', 'кожа', 'китовый жир', 'рыба', 'моллюски', 'жемчуг',
            'перо', 'яд', 'чешуя', 'эссенция маны')

(MEAT, HIDE, FUR, BONE, TUSK, HORN, WOOL, MILK, LEATHER, OIL,
 FISH, SHELL, PEARL, FEATHER, VENOM, SCALE, MANA) = range(17)

# биом: (обычные звери, скот, крупная дичь, магические, что даёт)
LAND = {
    10: ('ондатры, цапли, лягушки', 'утки, буйволы', 'лоси, аллигаторы',
         'болотный дракон, гидра', (MEAT, HIDE, FEATHER, VENOM, FISH)),
    11: ('—', '—', '—', 'ледяной змей', (MANA,)),
    12: ('песцы, белые куропатки', '—', '—', 'снежный призрак',
         (FUR, MEAT, MANA)),
    13: ('песцы, лемминги, куропатки', 'северные олени, овцебыки', '—',
         'инеистый волк', (FUR, MEAT, HIDE, HORN)),
    14: ('песцы, зайцы-беляки', 'северные олени, овцебыки', 'мамонты',
         'ледяной тролль, шерстистый носорог',
         (FUR, MEAT, HIDE, TUSK, HORN)),
    15: ('пищухи, сурки, орлы', 'горные козы, бараны', '—', 'грифон',
         (MEAT, HIDE, WOOL, HORN, FEATHER)),
    16: ('ласточки, ящерицы', '—', '—', 'каменный голем, виверна',
         (BONE, SCALE, MANA)),
    17: ('соболь, куница, рябчик', 'лоси, олени', 'медведи, кабаны',
         'амурский тигр, древний лось', (FUR, MEAT, HIDE, HORN)),
    18: ('суслики, сайгаки, хорьки', 'куланы, дикие лошади', '—',
         'степной носорог', (FUR, MEAT, HIDE)),
    19: ('сурки, степные лисы, дрофы', 'лошади, овцы, туры', 'сайгаки, туры',
         'степной мамонт, гигантский тур',
         (MEAT, HIDE, WOOL, MILK, TUSK, HORN)),
    20: ('олени, лисы, барсуки', 'свиньи, коровы', 'зубры, медведи',
         'вепрь-исполин, белый олень', (MEAT, HIDE, LEATHER, HORN, FUR)),
    21: ('олени, выдры, кабаны', 'свиньи, козы', 'лоси, медведи',
         'гигантский лось, единорог', (MEAT, HIDE, FUR, HORN)),
    22: ('зайцы, дикие козы, орлы', 'козы, овцы, муфлоны', 'кабаны',
         'химера', (MEAT, HIDE, WOOL, MILK)),
    23: ('тушканчики, вараны, скорпионы', 'верблюды', 'аддаксы',
         'песчаный червь, гигантский скорпион', (MEAT, HIDE, VENOM, SCALE)),
    24: ('газели, шакалы, бородавочники', 'зебу, козы',
         'слоны, носороги, жирафы', 'боевой слон, саблезубый кот',
         (MEAT, HIDE, TUSK, HORN, LEATHER)),
    25: ('антилопы, гиены', 'буйволы, зебу', 'слоны, бегемоты',
         'носорог-исполин, мантикора', (MEAT, HIDE, TUSK, HORN)),
    26: ('обезьяны, павлины', 'зебу, буйволы', 'слоны, гауры, тигры',
         'королевский тигр, нага', (MEAT, HIDE, TUSK, FEATHER, VENOM)),
    27: ('тапиры, пекари, попугаи', 'свиньи', 'слоны, носороги, тигры',
         'золотой тигр, грифон', (MEAT, HIDE, TUSK, FEATHER)),
    28: ('обезьяны, ягуары, удавы', '—', 'лесные слоны, гориллы',
         'исполинский удав, василиск', (MEAT, HIDE, TUSK, VENOM, SCALE)),
    29: ('крабы, цапли, выдры', '—', 'крокодилы, тигры', 'морской змей',
         (SHELL, FISH, HIDE, SCALE)),
    30: ('скорпионы, ящерицы', '—', '—', 'соляной элементаль',
         (VENOM, MANA)),
    31: ('ящерицы, грызуны', 'верблюды', '—', 'песчаный червь',
         (HIDE, SCALE, MEAT)),
    32: ('скорпионы, грифы, змеи', '—', '—', 'каменный голем',
         (VENOM, BONE, MANA)),
    33: ('козы, птицы, ящерицы', 'козы, верблюды', '—', 'джинн оазиса',
         (MEAT, MILK, HIDE, MANA)),
    34: ('—', '—', '—', 'пепельный демон', (MANA,)),
    35: ('зайцы, белки, тетерева', 'северные олени, лоси', 'медведи',
         'росомаха, мамонты', (FUR, MEAT, HIDE, TUSK, HORN)),
    36: ('лисы, зайцы, перепела', 'коровы, овцы, кони', 'олени, туры',
         'золоторунный баран', (MEAT, HIDE, WOOL, MILK, HORN)),
    37: ('лемуры, козы, птицы', 'козы', 'туры, медведи',
         'облачный левиафан', (MEAT, HIDE, FEATHER, MANA)),
    38: ('зайцы, тетерева, гадюки', '—', 'олени, кабаны',
         'блуждающий огонёк', (MEAT, FUR, VENOM, MANA)),
    39: ('зайцы, куропатки, гадюки', 'овцы', 'олени', 'вересковый дух',
         (MEAT, WOOL, HIDE, MANA)),
}
DEFLAND = ('мелкая дичь', '—', '—', 'неведомый зверь', (MEAT, HIDE))

DENSITY_BUCKETS = ('скудная', 'умеренная', 'высокая', 'обильная')


def _ocean_profile(world, i: int) -> dict:
    """Что даёт море: от рифа до полярного льда."""
    b = world.biome[i]
    t = world.temp[i]
    cold = t < 6
    polar = t < -1
    if b == 0:
        wild = ['тюлени, нерпа']
        if polar:
            wild.append('моржи')
        return {"common": 'белухи, нарвалы', "wild": ', '.join(wild) or '—',
                "magic": 'левиафан подо льдом',
                "prod": (FUR, OIL, MEAT, HIDE, TUSK)}
    if b == 1:
        return {"common": 'рифовые рыбы, моллюски', "wild": 'морские черепахи',
                "magic": 'риф-страж', "prod": (FISH, SHELL, PEARL, SCALE)}
    if b == 2:
        return {"common": 'крабы, кальмары',
                "wild": 'тюлени, каланы' if cold else '—',
                "magic": 'кракен', "prod": (FISH, SHELL, FUR, OIL)}
    if b in (3, 4):
        harvest = 'киты, моржи, тюлени' if cold else 'дельфины, тунец'
        prod = [FISH, OIL, HIDE, MEAT]
        if cold:
            prod.extend((TUSK, FUR))
        return {"common": 'сельдь, треска, кальмар', "wild": harvest,
                "magic": 'морской змей' if cold else 'сирена',
                "prod": tuple(prod)}
    if b == 9:
        return {"common": 'рыба, раки, тростник', "wild": '—',
                "magic": 'озёрный дух', "prod": (FISH, FEATHER, MEAT)}
    return {"common": 'глубоководная рыба', "wild": '—',
            "magic": 'абиссальная тварь', "prod": (FISH, OIL)}


def _land_density(world, i: int) -> float:
    """Насколько густо земля кормит зверя."""
    m = world.moist[i]
    d = 0.35 + 0.45 * world.fertility[i] + 0.20 * min(1.0, m * 1.4)
    b = world.biome[i]
    if b in (11, 34):
        d *= 0.05
    if b in (31, 12):
        d *= 0.25
    if b in (23, 30, 32):
        d *= 0.45
    if b in (24, 25):
        d *= 1.15
    return max(0.0, min(1.0, d))


def res_at(world, i: int) -> dict:
    """Итог по гексу: густота живности, что добывают, есть ли диковина."""
    ocean = world.is_ocean[i]
    lake = world.is_lake[i]
    products = []
    rare = big = marine = False
    if ocean or lake:
        op = _ocean_profile(world, i)
        dens = 0.4 + 0.3 * (1 if world.biome[i] in (3, 4) else 0.4)
        for p in op["prod"]:
            if p not in products:
                products.append(p)
        if op["wild"] and op["wild"] != '—':
            marine = True
        rng = rng_from("%s:res:%d" % (world.cfg.seed, i))
        if op["magic"] and op["magic"] != '—' and rng() < 0.05:
            rare = True
    else:
        pr = LAND.get(world.biome[i], DEFLAND)
        dens = _land_density(world, i)
        for p in pr[4]:
            if p not in products:
                products.append(p)
        if pr[2] and pr[2] != '—' and dens > 0.34:
            big = True
        if pr[3] and pr[3] != '—':
            mg = world.magic[i]
            wild = min(1.0, world.continental[i] * 0.7 + abs(mg) * 0.6)
            chance = 0.10 + wild * 0.30 + (0.20 if abs(mg) > 0.4 else 0)
            rng = rng_from("%s:res:%d" % (world.cfg.seed, i))
            if rng() < chance:
                rare = True
    return {"dens": dens, "products": products, "rare": rare, "big": big,
            "marine": marine, "ocean": bool(ocean or lake)}


def dense_resources(world):
    """Слой 11 (насыщенность) и слой 12 (флаги живности)."""
    n = world.W * world.H
    rich = array('B', [0]) * n
    flags = array('B', [0]) * n
    for i in range(n):
        r = res_at(world, i)
        dens = r["dens"]
        rich[i] = max(0, min(255, _round(dens * 255)))
        bucket = 3 if dens > 0.75 else 2 if dens > 0.5 else 1 if dens > 0.3 else 0
        f = bucket & 3
        if r["big"]:
            f |= 4
        if r["rare"]:
            f |= 8
        if r["marine"]:
            f |= 16
        if r["ocean"]:
            f |= 32
        flags[i] = f
    return rich, flags


def resources_json() -> dict:
    biomes = {}
    for key, p in LAND.items():
        biomes[str(key)] = {"common": p[0], "livestock": p[1], "wild": p[2],
                            "magical": p[3], "products": list(p[4])}
    return {
        "products": list(PRODUCTS),
        "richnessLayer": 11, "faunaFlagsLayer": 12,
        "flagBits": {"densityBucket": "0-1", "bigGame": 2, "rareMagical": 3,
                     "marineHarvest": 4, "oceanHex": 5},
        "densityBuckets": list(DENSITY_BUCKETS),
        "biomes": biomes,
        "ocean": 'см. oceanProfile: холодные шельфы (biome 3,4 при t<6°C) '
                 'дают киты/моржи/тюлени (мясо,жир,шкуры,бивни,мех)',
    }


# ---------------------------------------------------------------------------
# Местные бедствия
# ---------------------------------------------------------------------------

EVENTS = (
    (0, 'Ураган', -1, 0.18), (1, 'Песчаная буря', -1, 0.20),
    (2, 'Снежный буран', -1, 0.22), (3, 'Извержение', -1, 0.12),
    (4, 'Паводок', -1, 0.15), (5, 'Лесной пожар', -1, 0.14),
    (6, 'Лавина', -1, 0.16), (7, 'Цунами', -1, 0.06),
    (8, 'Засуха', -1, 0.12), (9, 'Поветрие', -1, 0.10),
    (10, 'Землетрясение', -1, 0.10), (11, 'Урожайный год', 1, 0.20),
    (12, 'Рыбный ход', 1, 0.25), (13, 'Мягкий сезон', 1, 0.30),
    (14, 'Северное сияние', 1, 0.35), (15, 'Цветение', 1, 0.15),
)


def events_at(world, i: int) -> list:
    """Чем эта земля грозит и что на ней бывает доброго."""
    out = []

    def add(event_id, chance):
        if chance > 0.02:
            out.append((event_id, min(0.95, chance)))

    b = world.biome[i]
    t = world.temp[i]
    m = world.moist[i]
    t_min = world.temp_min[i]
    dv = world.dist_v[i]
    vs = world.volc_status[i]
    meters = max(0.0, world.elev_to_m(world.elev[i]))
    coast = shelf_n = deep_n = False
    for j in world.neighbors(i):
        if world.is_ocean[j]:
            coast = True
            if world.biome[j] in (3, 4):
                shelf_n = True
            if world.biome[j] >= 6:
                deep_n = True

    if world.is_ocean[i] or world.is_lake[i]:
        if b in (3, 4):
            add(12, 0.25)
        return out

    if coast and t > 20 and 24 <= b <= 29:
        add(0, 0.18 + m * 0.12)
    if b in (23, 30, 31, 32, 34):
        add(1, 0.20 + (0.30 - min(0.30, m)) * 0.4)
    if t_min < -5 or b in (11, 12, 13, 14, 17, 35):
        add(2, 0.22 + max(0.0, -t_min - 5) * 0.01)
    if dv <= (6 if vs == 2 else 3):
        add(3, 0.12 * (1.6 if vs == 2 else 1.0 if vs == 1 else 0.6)
            * max(0.2, 1 - dv / 8))
    if (world.is_river[i] or b == 10 or world.accum[i] > 6
            or (m > 0.7 and 26 <= b <= 28)):
        add(4, 0.15 + (0.10 if world.is_river[i] else 0))
    if b in (19, 22, 24, 25, 36) and t > 16 and m < 0.5:
        add(5, 0.14 + (0.5 - m) * 0.2)
    if meters > 2000 and (b in (15, 16) or t_min < 0):
        add(6, 0.16 + min(0.2, (meters - 2000) / 4000))
    if coast and (deep_n or dv < 5):
        add(7, 0.06 + (0.05 if dv < 5 else 0))
    if b in (18, 23, 24, 30) or m < 0.25:
        add(8, 0.12 + (0.25 - min(0.25, m)) * 0.5)
    if b in (10, 28, 29) and t > 18:
        add(9, 0.10 + m * 0.08)
    if abs(world.stress[i]) > 0.5:
        add(10, 0.10 + min(0.15, (abs(world.stress[i]) - 0.5) * 0.2))
    if b in (20, 36, 19, 21) and world.fertility[i] > 0.55:
        add(11, 0.20 + world.fertility[i] * 0.15)
    if shelf_n:
        add(12, 0.25)
    if 5 < t < 24 and 0.3 < m < 0.8:
        add(13, 0.30)
    if t_min < -10 or b in (12, 13, 14):
        add(14, 0.35)
    if b in (23, 30, 31) and m > 0.12:
        add(15, 0.15)
    return out


def dense_events(world):
    """Слой 13 (какие беды возможны) и слой 14 (общий риск)."""
    n = world.W * world.H
    mask = array('h', [0]) * n
    chance = array('B', [0]) * n
    for i in range(n):
        mk = 0
        top = 0.0
        for event_id, ch in events_at(world, i):
            mk |= (1 << event_id)
            if ch > top:
                top = ch
        mask[i] = mk - 0x10000 if mk >= 0x8000 else mk
        chance[i] = _round(min(1.0, top) * 255)
    return mask, chance


def events_json() -> dict:
    return {"maskLayer": 13, "chanceLayer": 14,
            "events": [{"id": e[0], "name": e[1], "polarity": e[2],
                        "base": e[3]} for e in EVENTS]}


# ---------------------------------------------------------------------------
# Вода под землёй
# ---------------------------------------------------------------------------

RIVER_CLASS_TH = {"brook": 4, "stream": 20, "river": 120}
RIVER_CLASSES = ('—', 'ручей', 'река', 'большая река')
AQUIFER_LEVELS = ('нет', 'лёгкий', 'тяжёлый')


def _aquifer_at(world, i: int) -> int:
    if world.is_ocean[i] or world.is_lake[i]:
        return 0
    gw = world.groundwater[i]
    m = max(0.0, world.elev_to_m(world.elev[i]))
    b = world.biome[i]
    sl = 0.0
    for j in world.neighbors(i):
        sl += abs(world.elev[j] - world.elev[i])
    sl /= 6
    porous = b in (10, 19, 20, 24, 36, 29, 31, 38)
    level = 0
    if gw > 0.30 and m < 1500 and sl < 0.05:
        level = 1
    if gw > 0.58 and m < 800 and sl < 0.035 and (porous or gw > 0.7):
        level = 2
    return level


def aquifer(world):
    """Слой 16: где вода стоит близко к поверхности."""
    n = world.W * world.H
    out = array('B', [0]) * n
    for i in range(n):
        out[i] = _aquifer_at(world, i)
    return out


def hydro_json(world) -> dict:
    """Водопады и солёные озёра — для летописи."""
    n = world.W * world.H
    waterfalls = []
    saline = []
    for i in range(n):
        if not world.is_river[i]:
            continue
        d = world.flowto[i]
        if d < 0 or d >= n:
            continue
        drop = world.elev[i] - world.elev[d]
        if drop > 0.045 and world.accum[i] > 6:
            waterfalls.append(i)
    for i in range(n):
        if not world.is_lake[i]:
            continue
        river_n = False
        arid = count = 0
        for j in world.neighbors(i):
            if world.is_river[j]:
                river_n = True
            if world.biome[j] in (18, 23, 30, 31, 32, 34):
                arid += 1
            count += 1
        if not river_n and arid >= max(1, int(math.floor(count * 0.4))):
            saline.append(i)
    return {"aquiferLayer": 16, "aquiferLevels": list(AQUIFER_LEVELS),
            "riverClassThresholds": dict(RIVER_CLASS_TH),
            "riverClasses": list(RIVER_CLASSES),
            "waterfalls": waterfalls, "salineLakes": saline}


# ---------------------------------------------------------------------------
# Дикость округи
# ---------------------------------------------------------------------------

SAV_TH = (0.33, 0.66)
SPIRIT_NEUTRAL = 0.12
SAV_NAMES = ('кроткое', 'вольное', 'лютое')
SPIRIT_NAMES = ('злое', 'нейтральное', 'доброе')
SURROUND_GRID = (
    ('Унылые Пустоши', 'Тихий Край', 'Благие Кущи'),
    ('Морочная Чаща', 'Вольная Глухомань', 'Лучезарная Глушь'),
    ('Кошмарные Урочища', 'Лютая Дичь', 'Дивный Вертоград'),
)


def _savagery_at(world, i: int) -> float:
    if world.is_ocean[i]:
        return 0.0
    cont = world.continental[i]
    m = max(0.0, world.elev_to_m(world.elev[i]))
    t = world.temp[i]
    mg = abs(world.magic[i])
    b = world.biome[i]
    s = 0.15 + 0.42 * cont
    s += min(0.25, m / 4000 * 0.25)
    if t < -10 or t > 34:
        s += 0.18
    elif t < -2 or t > 30:
        s += 0.08
    s += 0.30 * mg
    if b in (26, 27, 28, 29, 10):
        s += 0.10
    if b in (15, 16):
        s += 0.10
    if b in (19, 20, 24, 36):
        s -= 0.10
    s -= 0.12 * world.fertility[i]
    return max(0.0, min(1.0, s))


def savagery(world):
    """Слой 17: насколько округа дика и опасна."""
    n = world.W * world.H
    out = array('B', [0]) * n
    for i in range(n):
        out[i] = _round(_savagery_at(world, i) * 255)
    return out


def surroundings_json() -> dict:
    names = []
    for row in SURROUND_GRID:
        names.extend(row)
    return {"savageryLayer": 17, "savageryThresholds": list(SAV_TH),
            "spiritNeutral": SPIRIT_NEUTRAL,
            "savageryNames": list(SAV_NAMES),
            "spiritNames": list(SPIRIT_NAMES), "names": names}


# ---------------------------------------------------------------------------
# Имена по магии
# ---------------------------------------------------------------------------

ALIGN_TH = (0.12, 0.28, 0.45, 0.62, 0.78, 0.93)
GOOD_FORMS = (
    ('Благодатный', 'Благодатная', 'Благодатное', 'Благодатные'),
    ('Освящённый', 'Освящённая', 'Освящённое', 'Освящённые'),
    ('Благословенный', 'Благословенная', 'Благословенное', 'Благословенные'),
    ('Святой', 'Святая', 'Святое', 'Святые'),
    ('Небесный', 'Небесная', 'Небесное', 'Небесные'),
    ('Божественный', 'Божественная', 'Божественное', 'Божественные'),
)
EVIL_FORMS = (
    ('Сумрачный', 'Сумрачная', 'Сумрачное', 'Сумрачные'),
    ('Зловещий', 'Зловещая', 'Зловещее', 'Зловещие'),
    ('Проклятый', 'Проклятая', 'Проклятое', 'Проклятые'),
    ('Осквернённый', 'Осквернённая', 'Осквернённое', 'Осквернённые'),
    ('Демонический', 'Демоническая', 'Демоническое', 'Демонические'),
    ('Адский', 'Адская', 'Адское', 'Адские'),
)
BIOME_GENDER = (0, 0, 2, 2, 0, 1, 0, 1, 1, 2, 2, 0, 1, 1, 1, 3, 3, 1, 1, 1,
                0, 0, 0, 1, 1, 3, 0, 0, 0, 3, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0)


def naming_json() -> dict:
    flat_good = [form for row in GOOD_FORMS for form in row]
    flat_evil = [form for row in EVIL_FORMS for form in row]
    return {"alignLayer": 15, "thresholds": list(ALIGN_TH),
            "goodForms": flat_good, "evilForms": flat_evil,
            "biomeGender": list(BIOME_GENDER),
            "note": 'имя = форма[(level-1)*4 + gender] + " " + biomeName; '
                    'level из |alignment| по thresholds; знак alignment = '
                    'сторона; свет lvl6 = Божественный'}


# ---------------------------------------------------------------------------
# Логова
# ---------------------------------------------------------------------------

def _meters(world, i):
    return max(0.0, world.elev_to_m(world.elev[i]))


LAIR_KINDS = (
    ("dragon", "Дракон", -1, "dragon-incursion", 3,
     lambda w, i: not w.is_ocean[i] and (_meters(w, i) > 1800
                                         or w.dist_v[i] < 4
                                         or w.biome[i] == 16)),
    ("titan", "Титан", 0, "titan-fall", 2,
     lambda w, i: not w.is_ocean[i] and (abs(w.magic[i]) > 0.5
                                         or _meters(w, i) > 2600)),
    ("colossus", "Колосс", 0, "colossus-march", 2,
     lambda w, i: not w.is_ocean[i] and w.biome[i] in (16, 23, 30, 32, 34)),
    ("leviathan", "Левиафан", -1, "leviathan-surge", 2,
     lambda w, i: w.is_ocean[i] and w.biome[i] >= 5),
    ("thunderbird", "Птица-гром", 0, "storm-of-wings", 2,
     lambda w, i: (not w.is_ocean[i] and _meters(w, i) > 2200
                   and w.biome[i] in (15, 16))),
    ("worm", "Великий змей", -1, "serpent-coil", 2,
     lambda w, i: not w.is_ocean[i] and w.biome[i] in (23, 31, 18, 19)),
    ("hydra", "Гидра", -1, "hydra-bloom", 2,
     lambda w, i: not w.is_ocean[i] and (w.biome[i] in (10, 29)
                                         or w.is_lake[i]
                                         or (w.is_river[i] and w.moist[i] > 0.6))),
    ("phoenix", "Феникс", 1, "phoenix-pyre", 1,
     lambda w, i: not w.is_ocean[i] and (w.dist_v[i] < 3 or w.biome[i] == 34)),
    ("treant", "Древний лесной владыка", 1, "wildwood-wrath", 2,
     lambda w, i: (not w.is_ocean[i] and w.biome[i] in (20, 21, 28, 37)
                   and w.fertility[i] > 0.5)),
    ("frost", "Ледяной властелин", -1, "long-winter", 2,
     lambda w, i: not w.is_ocean[i] and (w.biome[i] in (11, 12, 13)
                                         or w.temp[i] < -12)),
    ("behemoth", "Степной бехемот", 0, "great-stampede", 2,
     lambda w, i: not w.is_ocean[i] and w.biome[i] in (19, 24, 25)),
    ("kraken", "Кракен", -1, "maelstrom", 2,
     lambda w, i: w.is_ocean[i] and w.biome[i] >= 4),
    ("sandlord", "Пожиратель песков", -1, "sand-devourer", 2,
     lambda w, i: not w.is_ocean[i] and w.biome[i] in (31, 23)),
)


def lairs(world) -> list:
    """Логова древних существ — откуда в мир приходит беда.

    Роды расставляются по кругу, чтобы в мире был не выводок драконов,
    а разные твари; каждое логово стоит поодаль от прочих.
    """
    n = world.W * world.H
    by_kind = []
    for ki, kind in enumerate(LAIR_KINDS):
        habitable = kind[5]
        align = kind[2]
        listed = []
        for i in range(n):
            if not habitable(world, i):
                continue
            m = world.magic[i]
            if align != 0 and abs(m) > 0.25:
                sign = 1 if m > 0 else (-1 if m < 0 else 0)
                if sign != align:
                    continue
            listed.append(i)
        keys = {}
        for i in listed:
            keys[i] = rng_from("%s:lair:%d:%d" % (world.cfg.seed, ki, i))()
        listed.sort(key=lambda i: keys[i])
        by_kind.append(listed)

    min_dist = max(7, _round(world.W / 16))
    max_lairs = min(22, max(6, _round((world.land_frac * n) / 9000)))
    per_kind = [0] * len(LAIR_KINDS)
    ptr = [0] * len(LAIR_KINDS)
    placed = []
    namer = make_namer(rng_from("%s:lair:names" % world.cfg.seed))

    def far_enough(i):
        c, r = i % world.W, i // world.W
        for q in placed:
            qc, qr = q["i"] % world.W, q["i"] // world.W
            dx = abs(qc - c)
            if world.wrap:
                dx = min(dx, world.W - dx)
            if max(dx, abs(qr - r)) < min_dist:
                return False
        return True

    progress = True
    while len(placed) < max_lairs and progress:
        progress = False
        for ki, kind in enumerate(LAIR_KINDS):
            if len(placed) >= max_lairs:
                break
            if per_kind[ki] >= kind[4]:
                continue
            chosen = -1
            while ptr[ki] < len(by_kind[ki]):
                i = by_kind[ki][ptr[ki]]
                ptr[ki] += 1
                if far_enough(i):
                    chosen = i
                    break
            if chosen < 0:
                continue
            per_kind[ki] += 1
            lair_id = len(placed)
            age_rng = rng_from("%s:lair:age:%d" % (world.cfg.seed, lair_id))
            age_years = 600 + int(math.floor(age_rng() * 3000))
            tier = 1 + int(math.floor(age_rng() * 3))
            role = ("ancient" if tier >= 3
                    else ("remnant" if age_years > 2000 else "dormant"))
            placed.append({
                "id": lair_id, "hookId": "lair:%d" % lair_id,
                "kind": kind[0], "kindName": kind[1], "name": namer(ki % 3),
                "i": chosen, "biome": world.biome[chosen],
                "alignment": round(world.magic[chosen], 3), "tier": tier,
                "role": role, "catastropheClass": kind[3],
                "suggestedAgeYears": age_years, "remnantOf": None,
                "boundFaction": None,
            })
            progress = True
    return placed


# ---------------------------------------------------------------------------
# Племена, уже живущие на карте
# ---------------------------------------------------------------------------

def tribes(world) -> list:
    """Стоянки племён: равномерно по всей обитаемой земле, в любых биомах."""
    W, n = world.W, world.W * world.H
    score = array('f', [0.0]) * n
    for i in range(n):
        if world.is_ocean[i] or world.is_lake[i]:
            score[i] = -1
            continue
        s = res_at(world, i)["dens"]
        for j in world.neighbors(i):
            if world.is_ocean[j] and world.biome[j] in (3, 4):
                s += 0.10
                break
        score[i] = s

    cand = [i for i in range(n) if score[i] > 0.22]
    keys = {}
    for i in cand:
        keys[i] = rng_from("%s:tribe:pos:%d" % (world.cfg.seed, i))()
    cand.sort(key=lambda i: keys[i])
    min_dist = max(5, _round(W / 30))
    max_tribes = min(40, max(6, _round((world.land_frac * n) / 3000)))
    anchors = []
    for i in cand:
        if len(anchors) >= max_tribes:
            break
        c, r = i % W, i // W
        ok = True
        for a in anchors:
            ac, ar = a % W, a // W
            dx = abs(ac - c)
            if world.wrap:
                dx = min(dx, W - dx)
            if max(dx, abs(ar - r)) < min_dist:
                ok = False
                break
        if ok:
            anchors.append(i)

    owner = array('i', [-1]) * n
    budget = max(10, min(70, _round(n / max(1, len(anchors) * 180))))
    namer = make_namer(rng_from("%s:tribe:names" % world.cfg.seed))
    out = []
    for ti, anchor in enumerate(anchors):
        if owner[anchor] != -1:
            continue
        cells = [anchor]
        owner[anchor] = ti
        queue = deque([anchor])
        while queue and len(cells) < budget:
            cur = queue.popleft()
            nbs = [j for j in world.neighbors(cur)
                   if owner[j] == -1 and score[j] > 0.18
                   and not (world.is_ocean[j] or world.is_lake[j])]
            nbs.sort(key=lambda j: -score[j])
            for j in nbs:
                if len(cells) >= budget:
                    break
                if owner[j] == -1:
                    owner[j] = ti
                    cells.append(j)
                    queue.append(j)
        prod = []
        marine = mammoth = False
        for i in cells:
            r = res_at(world, i)
            for p in r["products"]:
                if p not in prod:
                    prod.append(p)
            if world.biome[i] in (14, 35):
                mammoth = True
            for j in world.neighbors(i):
                if world.is_ocean[j]:
                    op = res_at(world, j)
                    if op["marine"]:
                        marine = True
                        for p in op["products"]:
                            if p not in prod:
                                prod.append(p)
        ab = world.biome[anchor]
        style = 2 if (ab <= 14 or ab == 35) else (1 if 24 <= ab <= 29 else 0)
        out.append({"id": ti, "name": namer(style), "anchor": anchor,
                    "biome": ab, "supplies": sorted(prod),
                    "marine": 1 if marine else 0,
                    "mammoth": 1 if mammoth else 0, "cells": cells})
    return out


# ---------------------------------------------------------------------------
# Долгий климат мира
# ---------------------------------------------------------------------------

CLIMATE_SPAN = 10000
CLIMATE_TYPES = ('ice_age', 'warming', 'impact_winter', 'volcanic_winter',
                 'megadrought', 'pluvial', 'mana_surge', 'grand_winter')


def climate(seed: str) -> dict:
    """Лента больших климатических эпох: оледенения, потепления, зимы."""
    r = rng_from("%s:climate" % seed)

    def between(a, b):
        return a + r() * (b - a)

    def year():
        return int(math.floor(r() * CLIMATE_SPAN))

    events = []
    counter = [0]
    n_ice = (1 if r() < 0.55 else 0) + (1 if r() < 0.05 else 0)
    n_warm = (1 if r() < 0.40 else 0) + (1 if r() < 0.04 else 0)
    n_impact = 1 if r() < 0.18 else 0
    n_volc = 2 + int(math.floor(r() * 6))
    n_drought = 1 + int(math.floor(r() * 3))
    n_pluvial = 1 + int(math.floor(r() * 3))
    n_mana = int(math.floor(r() * 3))
    n_grand = int(math.floor(r() * 3))

    def emit(kind, name, count, gen):
        for _ in range(count):
            item = gen()
            item["type"] = kind
            item["name"] = name
            item["id"] = counter[0]
            counter[0] += 1
            events.append(item)

    def trap(lo, hi, dt_lo, dt_hi, dp_lo, dp_hi, sign_t=-1, sign_p=-1):
        dur = _round(between(lo, hi))
        return {"start": int(math.floor(r() * (CLIMATE_SPAN - dur * 0.5))),
                "dur": dur, "dT": sign_t * between(dt_lo, dt_hi),
                "dP": sign_p * between(dp_lo, dp_hi), "dMag": 0,
                "profile": "trap"}

    emit('ice_age', 'Ледниковый период', n_ice,
         lambda: trap(1500, 3500, 6, 11, 0.05, 0.20))
    emit('warming', 'Великое потепление', n_warm,
         lambda: trap(1200, 3000, 4, 8, 0, 0.15, sign_t=1, sign_p=1))

    def spike(lo, hi, dt_lo, dt_hi, dp_lo, dp_hi):
        dur = _round(between(lo, hi))
        return {"start": year(), "dur": dur, "dT": -between(dt_lo, dt_hi),
                "dP": -between(dp_lo, dp_hi), "dMag": 0, "profile": "spike"}

    emit('impact_winter', 'Импактная зима', n_impact,
         lambda: spike(150, 500, 7, 13, 0.05, 0.15))
    emit('volcanic_winter', 'Вулканическая зима', n_volc,
         lambda: spike(40, 160, 1.5, 4.5, 0, 0.10))

    def drought():
        dur = _round(between(200, 700))
        return {"start": year(), "dur": dur, "dT": between(0.5, 1.5),
                "dP": -between(0.25, 0.50), "dMag": 0, "profile": "trap"}

    emit('megadrought', 'Великая засуха', n_drought, drought)

    def pluvial():
        dur = _round(between(200, 700))
        return {"start": year(), "dur": dur, "dT": -between(0, 0.5),
                "dP": between(0.25, 0.50), "dMag": 0, "profile": "trap"}

    emit('pluvial', 'Плювиал (влажная эпоха)', n_pluvial, pluvial)

    def mana():
        dur = _round(between(150, 500))
        return {"start": year(), "dur": dur, "dT": between(-0.5, 0.5),
                "dP": 0, "dMag": between(0.2, 0.5), "profile": "trap"}

    emit('mana_surge', 'Всплеск маны', n_mana, mana)
    emit('grand_winter', 'Великая зима', n_grand,
         lambda: spike(200, 600, 3, 6, 0, 0.10))

    events.sort(key=lambda item: item["start"])
    return {"worldSpan": CLIMATE_SPAN, "currentYear": 0,
            "latSensitivity": 0.6,
            "events": [{"id": e["id"], "type": e["type"], "name": e["name"],
                        "start": e["start"], "dur": e["dur"],
                        "dT": round(e["dT"], 3), "dP": round(e["dP"], 3),
                        "dMag": round(e["dMag"], 3),
                        "profile": e["profile"]} for e in events]}
