# -*- coding: utf-8 -*-
"""Сборка гексовой карты в земли, на которых живёт история.

Карта TECTONIC WORLDFORGE — это десятки тысяч гексов. История такими
мелочами не оперирует: страна размером в один гекс бессмысленна, а
перебирать сто пятьдесят тысяч клеток каждый год незачем. Поэтому гексы
собираются в два-три десятка земель, и дальше движок работает с ними.

Порядок работы:

1. суша делится на массивы (материки и острова) — генератор карты уже
   пометил их слоем landReg;
2. каждому массиву выделяется доля земель по его площади;
3. внутри массива ставятся опорные точки как можно дальше друг от друга,
   и каждый гекс отходит ближайшей — получаются связные куски;
4. по куску считаются его свойства: местность, пригодность для жизни,
   плодородие, магия, дикость, опасность, берег и реки;
5. имя берётся у самой карты — у хребта, острова или материка, — а если
   именованного объекта рядом нет, имя придумывает кузница имён.

Всё детерминировано: одна и та же карта с тем же сидом даёт те же земли.
"""

from __future__ import annotations

from collections import Counter, deque

from . import races as races_mod
from . import worldmap as wm

# --- 40 биомов карты -> 12 типов местности движка -----------------------
# Океанские биомы (0..8) в землю не попадают: история живёт на суше.
BIOME_TERRAIN = {
    9:  races_mod.COAST,        # Озеро
    10: races_mod.SWAMP,        # Болото и марши
    11: races_mod.TUNDRA,       # Ледник и снега
    12: races_mod.TUNDRA,       # Полярная пустыня
    13: races_mod.TUNDRA,       # Арктическая тундра
    14: races_mod.TUNDRA,       # Тундра
    15: races_mod.MOUNTAIN,     # Альпийские луга
    16: races_mod.MOUNTAIN,     # Голые скалы
    17: races_mod.FOREST,       # Тайга
    18: races_mod.DESERT,       # Холодная пустыня
    19: races_mod.STEPPE,       # Степь
    20: races_mod.FOREST,       # Широколиственный лес
    21: races_mod.FOREST,       # Умеренный дождевой лес
    22: races_mod.HILLS,        # Маквис
    23: races_mod.DESERT,       # Жаркая пустыня
    24: races_mod.STEPPE,       # Саванна
    25: races_mod.STEPPE,       # Тропические луга
    26: races_mod.JUNGLE,       # Муссонный лес
    27: races_mod.JUNGLE,       # Тропический сезонный лес
    28: races_mod.JUNGLE,       # Тропический дождевой лес
    29: races_mod.SWAMP,        # Мангры
    30: races_mod.DESERT,       # Солончак
    31: races_mod.DESERT,       # Дюнный эрг
    32: races_mod.DESERT,       # Каменистая хамада
    33: races_mod.PLAIN,        # Оазис
    34: races_mod.DESERT,       # Выжженная пустошь
    35: races_mod.TUNDRA,       # Лесотундра
    36: races_mod.PLAIN,        # Лесостепь
    37: races_mod.FOREST,       # Облачный лес
    38: races_mod.SWAMP,        # Торфяник
    39: races_mod.HILLS,        # Верещатник
}

MOUNTAIN_METERS = 1500.0        # выше этого земля считается горной
HILL_METERS = 700.0
ISLAND_HEXES = 60               # массив меньше этого — остров, а не материк
COAST_SHARE = 0.5               # доля береговых гексов, после которой земля — побережье
UNDERGROUND_SHARE = 0.22        # какую часть горных земель отдать под подземья

# Как переложить латиницу карты на кириллицу летописи.
_TRANSLIT_PAIRS = (
    ("sch", "ш"), ("tch", "ч"), ("kh", "х"), ("th", "т"), ("ch", "ч"),
    ("sh", "ш"), ("ph", "ф"), ("gh", "г"), ("ck", "к"), ("qu", "кв"),
    ("ae", "э"), ("oe", "ё"), ("ee", "и"), ("oo", "у"), ("ou", "у"),
    ("ya", "я"), ("yu", "ю"), ("ja", "я"), ("ju", "ю"), ("dj", "дж"),
    ("fj", "фь"), ("bj", "бь"), ("hj", "хь"), ("nj", "нь"), ("sj", "сь"),
    ("tj", "ть"), ("kj", "кь"), ("gj", "гь"), ("lj", "ль"), ("mj", "мь"),
    ("rj", "рь"), ("vj", "вь"),
    ("a", "а"), ("b", "б"), ("c", "к"), ("d", "д"), ("e", "е"), ("f", "ф"),
    ("g", "г"), ("h", "х"), ("i", "и"), ("j", "й"), ("k", "к"), ("l", "л"),
    ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("q", "к"), ("r", "р"),
    ("s", "с"), ("t", "т"), ("u", "у"), ("v", "в"), ("w", "в"), ("x", "кс"),
    ("y", "и"), ("z", "з"),
)


def translit(name: str) -> str:
    """Латинское имя карты — кириллицей, чтобы читалось вместе с летописью."""
    if not name:
        return ""
    if any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in name):
        return name           # уже кириллица
    source = str(name).lower()
    out = []
    position = 0
    while position < len(source):
        for latin, cyrillic in _TRANSLIT_PAIRS:
            if source.startswith(latin, position):
                out.append(cyrillic)
                position += len(latin)
                break
        else:
            if source[position].isalpha():
                out.append(source[position])
            elif source[position] in " -'":
                out.append(source[position])
            position += 1
    result = "".join(out).strip()
    return result[:1].upper() + result[1:] if result else ""


class MapRegion:
    """Кусок карты, ставший землёй мира."""

    __slots__ = ("hexes", "terrain", "name", "capacity", "neighbors",
                 "habitat", "fertility", "magic", "savagery", "richness",
                 "risk", "risk_kinds", "boons", "temp", "moist", "elev_m",
                 "coastal", "river", "island", "landmass", "features",
                 "center", "x", "y")

    def __init__(self):
        self.hexes = []
        self.terrain = races_mod.PLAIN
        self.name = ""
        self.capacity = 1.0
        self.neighbors = set()
        self.habitat = 0.5
        self.fertility = 0.5
        self.magic = 0.0
        self.savagery = 0.0
        self.richness = 0.0
        self.risk = 0.0
        self.risk_kinds = []
        self.boons = []
        self.temp = 10.0
        self.moist = 0.5
        self.elev_m = 200.0
        self.coastal = False
        self.river = False
        self.island = False
        self.landmass = ""
        self.features = []
        self.center = 0
        self.x = 0
        self.y = 0


# ----------------------------------------------------------------------
# Разбиение
# ----------------------------------------------------------------------

def _landmasses(wmap) -> dict:
    """Массивы суши: номер -> список гексов. Приписки без номера сводим сами."""
    land_reg = wmap.layer(wm.L_LANDREG)
    groups = {}
    if land_reg is not None:
        loose = []
        for index in range(wmap.size):
            if not wmap.is_land(index):
                continue
            key = land_reg[index]
            if key < 0:
                loose.append(index)
            else:
                groups.setdefault(key, []).append(index)
        if loose:
            groups.update(_components(wmap, loose, start_key=10 ** 6))
        if groups:
            return groups
    # Слоя нет — размечаем сами обходом в ширину.
    land = [i for i in range(wmap.size) if wmap.is_land(i)]
    return _components(wmap, land)


def _components(wmap, hexes, start_key: int = 0) -> dict:
    """Связные куски внутри списка гексов."""
    pool = set(hexes)
    groups = {}
    key = start_key
    while pool:
        start = min(pool)
        pool.discard(start)
        chunk = [start]
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in wmap.neighbors(current):
                if neighbor in pool:
                    pool.discard(neighbor)
                    chunk.append(neighbor)
                    queue.append(neighbor)
        groups[key] = chunk
        key += 1
    return groups


def _hop_distances(wmap, sources, allowed) -> dict:
    """Расстояния в гексах от набора точек, не выходя за пределы allowed."""
    distance = {}
    queue = deque()
    for source in sources:
        distance[source] = 0
        queue.append(source)
    while queue:
        current = queue.popleft()
        step = distance[current] + 1
        for neighbor in wmap.neighbors(current):
            if neighbor in allowed and neighbor not in distance:
                distance[neighbor] = step
                queue.append(neighbor)
    return distance


def _pick_seeds(wmap, hexes, count, rng, habitat) -> list:
    """Опорные точки будущих земель.

    Сначала по одной на каждую заметную местность массива — иначе степь и
    пустыня растворятся в лесу, который их окружает, и мир выйдет
    однообразным. Оставшиеся ставим как можно дальше от уже взятых.
    """
    allowed = set(hexes)
    if count >= len(hexes):
        return sorted(hexes)[:max(1, count)]

    biome = wmap.layer(wm.L_BIOME)
    by_kind = {}
    for index in hexes:
        kind = BIOME_TERRAIN.get(biome[index], races_mod.PLAIN) if biome else races_mod.PLAIN
        by_kind.setdefault(kind, []).append(index)

    seeds = []
    # Местности идут от самой обширной к самой редкой; мелкие клочки пропускаем.
    floor = max(4, len(hexes) // 120)
    for kind in sorted(by_kind, key=lambda k: (-len(by_kind[k]), k)):
        if len(seeds) >= count:
            break
        group = by_kind[kind]
        if len(group) < floor and seeds:
            continue
        seeds.append(max(group, key=lambda i: (habitat[i], -i)))

    if not seeds:
        seeds = [max(hexes, key=lambda i: (habitat[i], -i))]

    spread = _hop_distances(wmap, seeds, allowed)
    taken = set(seeds)
    while len(seeds) < count:
        far, far_score = -1, -1.0
        for index in hexes:
            if index in taken:
                continue
            # Далеко от уже взятых, но всё же пригодно для жизни.
            score = spread.get(index, 0) + habitat[index] * 1.5
            if score > far_score:
                far, far_score = index, score
        if far < 0:
            break
        seeds.append(far)
        taken.add(far)
        fresh = _hop_distances(wmap, [far], allowed)
        for index, value in fresh.items():
            if value < spread.get(index, 10 ** 9):
                spread[index] = value
    return seeds


def _grow(wmap, hexes, seeds) -> dict:
    """Каждый гекс отходит ближайшей опорной точке.

    Растём не по чистому расстоянию, а вдоль похожей местности: переход в
    чужой биом стоит дороже трёх шагов. Тогда граница земли ложится по
    кромке леса или подножию хребта, а не режет их пополам.
    """
    import heapq

    biome = wmap.layer(wm.L_BIOME)
    allowed = set(hexes)

    def kind(index):
        return BIOME_TERRAIN.get(biome[index], races_mod.PLAIN) if biome else races_mod.PLAIN

    owner = {}
    cost = {}
    heap = []
    for slot, seed in enumerate(seeds):
        owner[seed] = slot
        cost[seed] = 0.0
        heapq.heappush(heap, (0.0, seed, slot, kind(seed)))
    while heap:
        spent, current, slot, home_kind = heapq.heappop(heap)
        if cost.get(current, 1e18) < spent or owner.get(current) != slot:
            continue
        for neighbor in wmap.neighbors(current):
            if neighbor not in allowed:
                continue
            step = 1.0 if kind(neighbor) == home_kind else 4.0
            fresh = spent + step
            if fresh < cost.get(neighbor, 1e18):
                cost[neighbor] = fresh
                owner[neighbor] = slot
                heapq.heappush(heap, (fresh, neighbor, slot, home_kind))
    # Что не дотянулось (отрезано водой внутри массива) — к первой точке.
    for index in hexes:
        owner.setdefault(index, 0)
    return owner


def _budget(sizes, total) -> list:
    """Делит общее число земель между массивами суши по их площади."""
    grand = float(sum(sizes)) or 1.0
    shares = [max(1, int(round(total * size / grand))) for size in sizes]
    # Подгоняем сумму под заказ, срезая с самых больших и добавляя им же.
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i])
    while sum(shares) > total:
        changed = False
        for i in order:
            if sum(shares) <= total:
                break
            if shares[i] > 1:
                shares[i] -= 1
                changed = True
        if not changed:
            break
    while sum(shares) < total:
        for i in order:
            if sum(shares) >= total:
                break
            shares[i] += 1
    return shares


# ----------------------------------------------------------------------
# Свойства земли
# ----------------------------------------------------------------------

def _norm(values):
    """Приводит показатель к 0…1 по его же разбросу на этой карте."""
    if not values:
        return lambda v: 0.5
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return lambda v: 0.5
    span = float(high - low)
    return lambda v: (v - low) / span


def _terrain_of(region, wmap, underground_pool) -> str:
    """Какая это местность с точки зрения движка."""
    biome = wmap.layer(wm.L_BIOME)
    tally = Counter()
    for index in region.hexes:
        terrain = BIOME_TERRAIN.get(biome[index] if biome else 36)
        if terrain:
            tally[terrain] += 1
    terrain = tally.most_common(1)[0][0] if tally else races_mod.PLAIN

    mountain_share = (tally.get(races_mod.MOUNTAIN, 0)) / float(len(region.hexes) or 1)
    if region.elev_m >= MOUNTAIN_METERS or mountain_share >= 0.4:
        terrain = races_mod.MOUNTAIN
    elif region.elev_m >= HILL_METERS and terrain in (races_mod.PLAIN, races_mod.STEPPE):
        terrain = races_mod.HILLS

    if region.island:
        return races_mod.ISLANDS
    if terrain not in (races_mod.MOUNTAIN, races_mod.SWAMP, races_mod.JUNGLE) \
            and region.coastal:
        return races_mod.COAST
    if terrain == races_mod.MOUNTAIN and region.center in underground_pool:
        return races_mod.UNDERGROUND
    return terrain


def _name_of(region, wmap, used, ctx, rng) -> str:
    """Имя земли: сначала спрашиваем карту, потом придумываем сами."""
    # Материк даёт имя только тогда, когда он сам с ладонь: иначе все земли
    # получатся «Верхний Вирен», «Нижний Вирен», «Малый Вирен».
    priority = {"range": 5, "bigisland": 4, "island": 4, "archipelago": 4,
                "lake": 3, "bay": 3, "river": 3}
    best, best_score = None, -1.0
    column, row = wmap.col_row(region.center)
    for feature in wmap.features:
        kind = feature.get("type")
        if kind not in priority:
            continue
        weight = priority.get(kind, 1)
        dx = abs(feature.get("cx", 0) - column)
        if wmap.wrap:
            dx = min(dx, wmap.width - dx)
        dy = abs(feature.get("cy", 0) - row)
        # Чем объект крупнее, тем дальше «слышно» его имя, но не безгранично.
        reach = min(26.0, max(5.0, (feature.get("area", 1) ** 0.5) * 1.1))
        distance = (dx * dx + dy * dy) ** 0.5
        if distance > reach:
            continue
        score = weight * (1.0 - distance / (reach + 1.0))
        if score > best_score:
            best, best_score = feature, score
    if best is not None:
        name = translit(best.get("name", ""))
        if name and name not in used:
            return name
    for _ in range(12):
        candidate = ctx.forge.region(rng, region.terrain)
        if candidate not in used:
            return candidate
    return ctx.forge.region(rng, region.terrain)


def _risk_kinds(wmap, hexes):
    """Чем земля грозит и чем одаривает — по маске событий карты.

    Возвращает две подписи: беды и добрые приметы. Карта помечает и то и
    другое одной маской, но в летописи это совсем разные вещи.
    """
    mask_layer = wmap.layer(wm.L_EVENTMASK)
    if mask_layer is None:
        return [], []
    catalog = wmap.tail.get("events") or {}
    names = {}
    good = set()
    for item in (catalog.get("events") or []):
        if isinstance(item, dict) and "id" in item:
            bit = int(item["id"])
            names[bit] = item.get("n") or item.get("name") or ""
            if int(item.get("polarity", -1)) > 0:
                good.add(bit)
    # Считаем только то, чем земля грозит всерьёз: единственный гекс с
    # вулканом посреди степи ещё не делает её вулканической.
    floor = max(1, int(len(hexes) * 0.12))
    tally = [0] * 16
    for index in hexes:
        mask = mask_layer[index] & 0xFFFF
        if not mask:
            continue
        for bit in range(16):
            if mask & (1 << bit):
                tally[bit] += 1
    risks, boons = [], []
    for bit in sorted(range(16), key=lambda b: (-tally[b], b)):
        if tally[bit] < floor:
            continue
        label = names.get(bit)
        if not label:
            continue
        (boons if bit in good else risks).append(label)
    return risks, boons


# ----------------------------------------------------------------------
# Главная сборка
# ----------------------------------------------------------------------

def build_regions(wmap, ctx, rng, target: int) -> list:
    """Гексовая карта -> список земель, готовых лечь в мир."""
    groups = _landmasses(wmap)
    if not groups:
        raise ValueError("на карте нет суши — истории негде случиться")

    keys = sorted(groups, key=lambda k: (-len(groups[k]), k))

    # Совсем мелкие островки не заслуживают отдельной земли, пока есть куда расти.
    major = [k for k in keys if len(groups[k]) >= 8] or keys[:1]
    target = max(len(major), min(int(target), 80))
    shares = _budget([len(groups[k]) for k in major], target)

    habitat_layer = wmap.layer(wm.L_FERTILITY)
    land_indices = [i for i in range(wmap.size) if wmap.is_land(i)]
    if habitat_layer is None:
        habitat = {i: 0.5 for i in land_indices}
    else:
        habitat = {i: float(habitat_layer[i]) for i in land_indices}

    regions = []
    owner_of_hex = {}
    for key, share in zip(major, shares):
        hexes = groups[key]
        seeds = _pick_seeds(wmap, hexes, share, rng, habitat)
        owner = _grow(wmap, hexes, seeds)
        buckets = {}
        for index, slot in owner.items():
            buckets.setdefault(slot, []).append(index)
        for slot in sorted(buckets):
            region = MapRegion()
            region.hexes = sorted(buckets[slot])
            region.island = len(hexes) < ISLAND_HEXES
            regions.append(region)
            for index in region.hexes:
                owner_of_hex[index] = len(regions) - 1

    # Островки, не попавшие в разбиение, отходят ближайшей земле.
    leftovers = [k for k in keys if k not in major]
    for key in leftovers:
        for index in groups[key]:
            nearest = _nearest_region(wmap, index, owner_of_hex)
            if nearest is None:
                continue
            regions[nearest].hexes.append(index)
            owner_of_hex[index] = nearest

    _measure(regions, wmap, owner_of_hex)
    _classify(regions, wmap, ctx, rng)
    return regions


def _nearest_region(wmap, index, owner_of_hex):
    """Кому отдать оторванный островок — ищем по прямой, с учётом замыкания карты."""
    column, row = wmap.col_row(index)
    best, best_distance = None, 1e18
    for other, region_slot in owner_of_hex.items():
        ocolumn, orow = wmap.col_row(other)
        dx = abs(ocolumn - column)
        if wmap.wrap:
            dx = min(dx, wmap.width - dx)
        dy = abs(orow - row)
        distance = dx * dx + dy * dy
        if distance < best_distance:
            best, best_distance = region_slot, distance
    return best


def _measure(regions, wmap, owner_of_hex) -> None:
    """Считает по каждой земле её показатели и соседей."""
    temp = wmap.layer(wm.L_TEMP)
    moist = wmap.layer(wm.L_MOIST)
    fert = wmap.layer(wm.L_FERTILITY)
    magic = wmap.layer(wm.L_MAGIC)
    savage = wmap.layer(wm.L_SAVAGERY)
    rich = wmap.layer(wm.L_RICHNESS)
    chance = wmap.layer(wm.L_EVENTCHANCE)

    for slot, region in enumerate(regions):
        hexes = region.hexes
        count = float(len(hexes)) or 1.0

        def mean(layer, default=0.0):
            if layer is None:
                return default
            return sum(layer[i] for i in hexes) / count

        region.elev_m = sum(wmap.elevation_m(i) for i in hexes) / count
        region.temp = mean(temp, 10.0)
        region.moist = mean(moist, 0.5)
        region.fertility = mean(fert, 0.5)
        region.magic = mean(magic, 0.0)
        region.savagery = mean(savage, 0.0) / 255.0
        region.richness = mean(rich, 0.0) / 255.0
        region.risk = mean(chance, 0.0) / 255.0
        region.risk_kinds, region.boons = _risk_kinds(wmap, hexes)

        coast = sum(1 for i in hexes if wmap.is_coast(i))
        river = sum(1 for i in hexes if wmap.is_river(i))
        region.coastal = coast / count >= COAST_SHARE
        region.river = river / count >= 0.06

        # Середина земли — самый обжитой гекс: там и стоит столица.
        if fert is not None:
            region.center = max(hexes, key=lambda i: (float(fert[i]), -i))
        else:
            region.center = hexes[len(hexes) // 2]
        region.x, region.y = wmap.col_row(region.center)

        for index in hexes:
            for neighbor in wmap.neighbors(index):
                other = owner_of_hex.get(neighbor)
                if other is not None and other != slot:
                    region.neighbors.add(other)

    # Соседство через узкие проливы: остров без соседей всё же не край света.
    for slot, region in enumerate(regions):
        if region.neighbors:
            continue
        nearest, best = None, 1e18
        for other_slot, other in enumerate(regions):
            if other_slot == slot:
                continue
            dx = abs(other.x - region.x)
            if wmap.wrap:
                dx = min(dx, wmap.width - dx)
            distance = dx * dx + (other.y - region.y) ** 2
            if distance < best:
                nearest, best = other_slot, distance
        if nearest is not None:
            region.neighbors.add(nearest)
            regions[nearest].neighbors.add(slot)


def _classify(regions, wmap, ctx, rng) -> None:
    """Назначает местность, имя и ёмкость."""
    habitats = [region.fertility for region in regions]
    to_unit = _norm(habitats)

    # Сначала — местность по карте, без подземий.
    for region in regions:
        region.terrain = _terrain_of(region, wmap, frozenset())
        region.habitat = to_unit(region.fertility)

    # Подземья на карте не нарисованы: их выдают рудные горы, где на
    # поверхности жить нечем. Берём такие из уже размеченных горных земель.
    stone = [slot for slot, region in enumerate(regions)
             if region.terrain == races_mod.MOUNTAIN and not region.island]
    stone.sort(key=lambda s: (-(regions[s].richness - regions[s].habitat), s))
    quota = max(1, int(round(len(stone) * 0.5))) if stone else 0
    for slot in stone[:quota]:
        regions[slot].terrain = races_mod.UNDERGROUND

    used = set()
    for region in regions:
        base = races_mod.TERRAIN_CAPACITY.get(region.terrain, 1.0)  # noqa: E501
        # Ёмкость земли — её местность, помноженная на то, как в ней на деле живётся.
        region.capacity = round(base * (0.55 + 0.9 * region.habitat), 3)
        region.name = _name_of(region, wmap, used, ctx, rng)
        used.add(region.name)

    landmass_names = {}
    for feature in wmap.features:
        if feature.get("type") in ("continent", "bigisland", "island", "archipelago"):
            landmass_names[feature.get("id")] = translit(feature.get("name", ""))
    for region in regions:
        region.landmass = landmass_names.get(region.center, "")
