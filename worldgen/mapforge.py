# -*- coding: utf-8 -*-
"""Свой картогенератор: гексовая карта мира без посторонних программ.

Раньше карту приходилось брать из TECTONIC WORLDFORGE и класть файлом
рядом с программой. Теперь карту умеет делать сам «Хронист» — в том же
формате, который читает движок, и с тем же набором слоёв.

Как делается карта:

1. **Плиты.** По сетке разбрасываются тектонические плиты; у каждой свой
   ход. Там, где плиты сходятся, растут хребты; там, где расходятся, —
   впадины и рифты.
2. **Высота.** Поверх плит ложится шум: несколько слоёв всё более мелкой
   ряби, сглаженных по гексам. Уровень моря режет сушу от воды.
3. **Тепло.** От широты, за вычетом высоты: на каждый километр вверх —
   шесть с половиной градусов вниз.
4. **Влага.** Ветер несёт её с воды вглубь суши и теряет на хребтах:
   за горой остаётся дождевая тень.
5. **Реки.** Вода стекает по уклону, сливается и там, где её собирается
   много, прорезает русло. Замкнутые впадины становятся озёрами.
6. **Биомы.** Тепло и влага кладутся на таблицу Уиттекера, и получается
   тайга, степь, тропический лес или солончак.
7. **Остальное.** Плодородие, руды, магия, дикость, местные угрозы,
   логова древних существ и лента климата на всю историю мира.

Сетка odd-r, как в формате .world: у чётных и нечётных рядов разное
смещение соседей. Зависимостей нет — только стандартная библиотека и
наш же детерминированный генератор случайных чисел.
"""

from __future__ import annotations

import json
import struct
from array import array

from . import worldmap as wm
from .rng import Rng, seed_to_int

# --- размеры карты -----------------------------------------------------

SIZES = {
    "малая": (96, 56),
    "средняя": (128, 76),
    "большая": (160, 96),
    "огромная": (208, 124),
}
DEFAULT_SIZE = "средняя"

SEA_LEVEL = 0.42
MIN_ALT = -8000.0
MAX_ALT = 7000.0

# --- биомы: те же имена и номера, что у карт .world --------------------

BIOME_NAMES = [
    "Морской лёд", "Коралловый риф", "Ламинариевый лес",
    "Прибрежное мелководье", "Континентальный шельф", "Сумеречная зона",
    "Батиаль", "Абиссаль", "Ультраабиссаль", "Озеро", "Болото и марши",
    "Ледник и снега", "Полярная пустыня", "Арктическая тундра", "Тундра",
    "Альпийские луга", "Голые скалы", "Тайга", "Холодная пустыня", "Степь",
    "Широколиственный лес", "Умеренный дождевой лес", "Маквис (средиземном.)",
    "Жаркая пустыня", "Саванна", "Тропические луга", "Муссонный лес",
    "Тропический сезонный лес", "Тропический дождевой лес", "Мангры",
    "Солончак", "Дюнный эрг", "Каменистая хамада", "Оазис",
    "Выжженная пустошь", "Лесотундра", "Лесостепь", "Облачный лес",
    "Торфяник", "Верещатник",
]

# --- местные угрозы: каталог тот же, что читает движок -----------------

EVENT_CATALOG = [
    {"id": 0, "name": "Ураган", "polarity": -1, "base": 0.18},
    {"id": 1, "name": "Песчаная буря", "polarity": -1, "base": 0.20},
    {"id": 2, "name": "Снежный буран", "polarity": -1, "base": 0.22},
    {"id": 3, "name": "Извержение", "polarity": -1, "base": 0.12},
    {"id": 4, "name": "Паводок", "polarity": -1, "base": 0.20},
    {"id": 5, "name": "Лесной пожар", "polarity": -1, "base": 0.18},
    {"id": 6, "name": "Лавина", "polarity": -1, "base": 0.16},
    {"id": 7, "name": "Цунами", "polarity": -1, "base": 0.10},
    {"id": 8, "name": "Засуха", "polarity": -1, "base": 0.22},
    {"id": 9, "name": "Поветрие", "polarity": -1, "base": 0.14},
    {"id": 10, "name": "Землетрясение", "polarity": -1, "base": 0.14},
    {"id": 11, "name": "Богатый урожай", "polarity": 1, "base": 0.20},
    {"id": 12, "name": "Рыбный ход", "polarity": 1, "base": 0.18},
    {"id": 13, "name": "Цветение", "polarity": 1, "base": 0.16},
    {"id": 14, "name": "Тихие годы", "polarity": 1, "base": 0.16},
    {"id": 15, "name": "Щедрая жила", "polarity": 1, "base": 0.10},
]

# --- логова: виды и то, чем они однажды обернутся ----------------------

LAIR_KINDS = (
    ("dragon", "Дракон", "dragon-incursion", 1),
    ("leviathan", "Левиафан", "leviathan-surge", 2),
    ("worm", "Червь глубин", "serpent-coil", 1),
    ("thunderbird", "Громовая птица", "storm-of-wings", 1),
    ("colossus", "Колосс", "colossus-march", 2),
    ("titan", "Титан", "titan-fall", 3),
)
LAIR_ROLES = ("ancient", "dormant", "remnant")

# --- перемены климата --------------------------------------------------

CLIMATE_KINDS = (
    ("ice_age", "Ледниковый период", -6.0, 0.15, 0.0, (900, 2600)),
    ("grand_winter", "Великая зима", -3.5, 0.05, 0.0, (300, 900)),
    ("warming", "Долгое потепление", 4.0, -0.05, 0.0, (700, 2200)),
    ("volcanic_winter", "Вулканическая зима", -4.5, 0.1, 0.0, (80, 400)),
    ("megadrought", "Великая засуха", 1.5, -0.35, 0.0, (300, 1200)),
    ("pluvial", "Плювиал", 0.5, 0.35, 0.0, (400, 1500)),
    ("mana_surge", "Всплеск маны", -0.1, 0.0, 0.45, (150, 600)),
)

# --- имена для карты ---------------------------------------------------

SYLL_A = ("ar", "el", "kor", "mir", "vel", "thar", "ul", "gan", "sae", "dor",
          "ner", "bal", "kaz", "rin", "ost", "hal", "syl", "tor", "vun", "esk")
SYLL_B = ("an", "en", "or", "il", "un", "ar", "eth", "is", "ol", "ur", "ad",
          "em", "yn", "ath", "ir", "os")
SYLL_C = ("", "", "", "dor", "mar", "heim", "gard", "wyn", "fell", "reth",
          "moor", "hal", "vik", "stad")

ODDR = wm.ODDR


def make_name(rng) -> str:
    name = rng.choice(SYLL_A) + rng.choice(SYLL_B) + rng.choice(SYLL_C)
    return name[0].upper() + name[1:]


# ---------------------------------------------------------------------------
# Сама постройка
# ---------------------------------------------------------------------------

class MapForge:
    """Постройка карты по сиду. Результат — обычный WorldMap."""

    def __init__(self, seed: str, size=DEFAULT_SIZE, land_share: float = 0.34,
                 roughness: float = 0.5, warmth: float = 0.5,
                 wetness: float = 0.5, magic: float = 0.5,
                 wrap: bool = True):
        self.seed_text = str(seed)
        self.rng = Rng(seed_to_int("mapforge:%s" % seed))
        if isinstance(size, str):
            self.width, self.height = SIZES.get(size, SIZES[DEFAULT_SIZE])
        else:
            self.width, self.height = int(size[0]), int(size[1])
        self.size = self.width * self.height
        self.land_share = max(0.12, min(0.72, float(land_share)))
        self.roughness = max(0.0, min(1.0, float(roughness)))
        self.warmth = max(0.0, min(1.0, float(warmth)))
        self.wetness = max(0.0, min(1.0, float(wetness)))
        self.magic_level = max(0.0, min(1.0, float(magic)))
        self.wrap = bool(wrap)

    # --- служебное ------------------------------------------------------

    def index(self, x: int, y: int) -> int:
        return y * self.width + x

    def neighbors(self, index: int) -> list:
        x = index % self.width
        y = index // self.width
        out = []
        for dx, dy in ODDR[y & 1]:
            nx, ny = x + dx, y + dy
            if ny < 0 or ny >= self.height:
                continue
            if nx < 0 or nx >= self.width:
                if not self.wrap:
                    continue
                nx %= self.width
            out.append(ny * self.width + nx)
        return out

    def _noise(self, octaves: int = 5, smooth: int = 2) -> array:
        """Слоистый шум по гексам: крупные пятна плюс мелкая рябь."""
        field = array("f", [0.0]) * self.size
        weight = 1.0
        total = 0.0
        for octave in range(octaves):
            step = max(2, int(self.width / (2 ** (octave + 1))))
            grid = {}
            for y in range(0, self.height + step, step):
                for x in range(0, self.width + step, step):
                    grid[(x // step, y // step)] = self.rng.random()
            for index in range(self.size):
                x, y = index % self.width, index // self.width
                gx, gy = x / float(step), y / float(step)
                x0, y0 = int(gx), int(gy)
                fx, fy = gx - x0, gy - y0
                fx = fx * fx * (3 - 2 * fx)
                fy = fy * fy * (3 - 2 * fy)
                v00 = grid.get((x0, y0), 0.5)
                v10 = grid.get((x0 + 1, y0), 0.5)
                v01 = grid.get((x0, y0 + 1), 0.5)
                v11 = grid.get((x0 + 1, y0 + 1), 0.5)
                top = v00 + (v10 - v00) * fx
                bottom = v01 + (v11 - v01) * fx
                field[index] += weight * (top + (bottom - top) * fy)
            total += weight
            weight *= 0.55
        for index in range(self.size):
            field[index] /= total
        for _ in range(smooth):
            field = self._smooth(field)
        return field

    def _smooth(self, field: array) -> array:
        out = array("f", field)
        for index in range(self.size):
            total, count = field[index], 1
            for other in self.neighbors(index):
                total += field[other]
                count += 1
            out[index] = total / count
        return out

    # --- шаги -----------------------------------------------------------

    def build(self) -> wm.WorldMap:
        plates, stress = self._plates()
        elev = self._elevation(stress)
        flags, water_reg, land_reg = self._water(elev)
        temp = self._temperature(elev)
        moist = self._moisture(elev, flags, temp)
        flow, accum, rivers = self._rivers(elev, flags)
        biome = self._biomes(elev, temp, moist, flags)
        fert = self._fertility(biome, moist, flags, elev)
        rich, resflags = self._riches(elev, stress, biome)
        magic = self._magic()
        savage = self._savagery(elev, biome, flags)
        distv, volcanoes = self._volcanoes(elev, stress, flags)
        mask, chance = self._events(elev, temp, moist, flags, distv, biome)
        range_reg, ranges = self._ranges(elev, flags)
        tail = self._tail(elev, flags, land_reg, water_reg, ranges, volcanoes,
                          biome, savage, rich)

        layers = {
            wm.L_ELEV: elev, wm.L_TEMP: temp, wm.L_MOIST: moist,
            wm.L_BIOME: biome, wm.L_FLAGS: flags, wm.L_FERTILITY: fert,
            wm.L_PLATE: plates, wm.L_STRESS: stress, wm.L_DISTV: distv,
            wm.L_FLOWTO: flow, wm.L_ACCUM: accum, wm.L_RICHNESS: rich,
            wm.L_RESFLAGS: resflags, wm.L_EVENTMASK: mask,
            wm.L_EVENTCHANCE: chance, wm.L_MAGIC: magic,
            wm.L_AQUIFER: self._aquifer(moist, flags), wm.L_SAVAGERY: savage,
            wm.L_LANDREG: land_reg, wm.L_WATERREG: water_reg,
            wm.L_RANGEREG: range_reg, wm.L_RIVERREG: rivers,
        }
        return wm.WorldMap(self.width, self.height, self.wrap, SEA_LEVEL,
                           MIN_ALT, MAX_ALT, seed_to_int(self.seed_text),
                           layers, tail)

    # --- плиты ----------------------------------------------------------

    def _plates(self) -> tuple:
        count = max(6, int(self.size / 1400) + self.rng.randint(2, 6))
        seeds = []
        for _ in range(count):
            seeds.append((self.rng.randint(0, self.width - 1),
                          self.rng.randint(0, self.height - 1),
                          self.rng.uniform(-1.0, 1.0),
                          self.rng.uniform(-1.0, 1.0),
                          self.rng.chance(0.45)))      # континентальная?
        plates = array("h", [0]) * self.size
        for index in range(self.size):
            x, y = index % self.width, index // self.width
            best, best_dist = 0, 1e18
            for number, (sx, sy, _, _, _) in enumerate(seeds):
                dx = abs(x - sx)
                if self.wrap:
                    dx = min(dx, self.width - dx)
                dist = dx * dx + (y - sy) * (y - sy) * 1.3
                if dist < best_dist:
                    best, best_dist = number, dist
            plates[index] = best

        stress = array("f", [0.0]) * self.size
        for index in range(self.size):
            mine = plates[index]
            for other in self.neighbors(index):
                if plates[other] == mine:
                    continue
                a, b = seeds[mine], seeds[plates[other]]
                # Сходятся или расходятся: знак скалярного произведения хода.
                push = -(a[2] * b[2] + a[3] * b[3])
                stress[index] = max(stress[index], push)
        stress = self._smooth(stress)
        self._plate_seeds = seeds
        return plates, stress

    # --- высота ---------------------------------------------------------

    def _elevation(self, stress) -> array:
        base = self._noise(octaves=6, smooth=1)
        ridge = self._noise(octaves=4, smooth=0)
        elev = array("f", [0.0]) * self.size
        seeds = self._plate_seeds
        for index in range(self.size):
            value = base[index]
            # Континентальные плиты выше океанических.
            value += 0.12 if seeds[0][4] else 0.0
            value += 0.30 * max(0.0, stress[index]) * (0.5 + self.roughness)
            value += 0.18 * (ridge[index] - 0.5) * (0.4 + self.roughness)
            # У полюсов и у края карты — глубокая вода, чтобы мир не
            # упирался в сушу на самой кромке.
            y = index // self.width
            edge = min(y, self.height - 1 - y) / float(self.height * 0.5)
            value *= 0.55 + 0.45 * min(1.0, edge * 1.6)
            elev[index] = value

        low, high = min(elev), max(elev)
        span = (high - low) or 1.0
        for index in range(self.size):
            elev[index] = (elev[index] - low) / span

        # Подгоняем уровень моря так, чтобы суши вышло сколько заказано.
        order = sorted(elev)
        cut = order[max(0, min(self.size - 1,
                               int(self.size * (1.0 - self.land_share))))]
        shift = SEA_LEVEL - cut
        for index in range(self.size):
            elev[index] = max(0.0, min(1.0, elev[index] + shift))
        return elev

    # --- вода ------------------------------------------------------------

    def _water(self, elev) -> tuple:
        flags = array("B", [0]) * self.size
        water_reg = array("i", [-1]) * self.size
        land_reg = array("i", [-1]) * self.size

        # Океан — вода, связанная с краем карты; всё прочее — озёра.
        ocean = set()
        stack = []
        for x in range(self.width):
            for y in (0, self.height - 1):
                index = self.index(x, y)
                if elev[index] < SEA_LEVEL:
                    stack.append(index)
        while stack:
            index = stack.pop()
            if index in ocean:
                continue
            ocean.add(index)
            for other in self.neighbors(index):
                if other not in ocean and elev[other] < SEA_LEVEL:
                    stack.append(other)

        water_number, land_number = 0, 0
        seen = set()
        for index in range(self.size):
            if elev[index] < SEA_LEVEL:
                flags[index] |= wm.FLAG_OCEAN if index in ocean \
                    else wm.FLAG_LAKE
        for index in range(self.size):
            if elev[index] >= SEA_LEVEL:
                for other in self.neighbors(index):
                    if elev[other] < SEA_LEVEL:
                        flags[index] |= wm.FLAG_COAST
                        break

        # Нумеруем массивы суши и водоёмы — из них потом выйдут материки,
        # острова, моря и озёра.
        for index in range(self.size):
            if index in seen:
                continue
            water = elev[index] < SEA_LEVEL
            group, stack = [], [index]
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                if (elev[current] < SEA_LEVEL) != water:
                    continue
                seen.add(current)
                group.append(current)
                stack.extend(self.neighbors(current))
            if water:
                for item in group:
                    water_reg[item] = water_number
                water_number += 1
            else:
                for item in group:
                    land_reg[item] = land_number
                land_number += 1
        return flags, water_reg, land_reg

    # --- тепло и влага ---------------------------------------------------

    def metres_of(self, height: float) -> float:
        """Высота гекса над уровнем моря в метрах."""
        if height < SEA_LEVEL:
            return 0.0
        return (height - SEA_LEVEL) / (1.0 - SEA_LEVEL) * MAX_ALT

    def _temperature(self, elev) -> array:
        """Тепло: от широты, минус высота, плюс погодная рябь.

        На экваторе около +27, у полюсов около −28, и на каждый километр
        вверх — шесть с половиной градусов вниз. Ползунок тепла сдвигает
        обе крайности разом: мир-ледник и мир-парник.
        """
        temp = array("f", [0.0]) * self.size
        wobble = self._noise(octaves=3, smooth=2)
        equator = (self.height - 1) / 2.0
        hot = 27.0 + 12.0 * (self.warmth - 0.5)
        cold = -28.0 + 20.0 * (self.warmth - 0.5)
        for index in range(self.size):
            y = index // self.width
            lat = min(1.0, abs(y - equator) / equator)
            share = 1.0 - lat ** 1.55
            value = cold + (hot - cold) * share
            value -= self.metres_of(elev[index]) / 1000.0 * 6.5
            value += (wobble[index] - 0.5) * 7.0
            temp[index] = value
        return temp

    # Пояса влаги по широте: экватор мокрый, тропики сухие, умеренные
    # широты снова мокрые, полюса сухие от холода.
    def _belt(self, lat: float) -> float:
        if lat < 0.18:
            return 1.0
        if lat < 0.38:
            return 0.28
        if lat < 0.72:
            return 0.85
        return 0.35

    def _moisture(self, elev, flags, temp) -> array:
        """Влага: ветер несёт её с воды, хребты отбирают, солнце сушит."""
        moist = array("f", [0.0]) * self.size
        spots = self._noise(octaves=4, smooth=2)
        equator = (self.height - 1) / 2.0
        for index in range(self.size):
            if elev[index] < SEA_LEVEL:
                moist[index] = 1.0
                continue
            y = index // self.width
            lat = min(1.0, abs(y - equator) / equator)
            moist[index] = 0.02 + 0.22 * spots[index] * self._belt(lat)

        # Ветер идёт от воды вглубь суши, теряя влагу на подъёмах: за
        # хребтом остаётся дождевая тень.
        for _ in range(2):
            for y in range(self.height):
                lat = min(1.0, abs(y - equator) / equator)
                belt = self._belt(lat)
                carry = belt
                for step in range(self.width):
                    x = step if (y & 1) == 0 else self.width - 1 - step
                    index = self.index(x, y)
                    if elev[index] < SEA_LEVEL:
                        carry = belt
                        continue
                    climb = max(0.0, elev[index] - SEA_LEVEL)
                    take = 0.10 + 0.9 * climb
                    got = carry * min(0.8, take)
                    moist[index] = min(1.0, moist[index] + got * 0.9)
                    carry = max(0.0, carry - got)
                    carry = min(belt, carry + 0.02 * belt)
        moist = self._smooth(moist)

        land = [index for index in range(self.size) if elev[index] >= SEA_LEVEL]
        for index in land:
            value = moist[index]
            # В жару влага испаряется быстрее, в мороз её просто мало.
            if temp[index] > 24:
                value *= 0.72
            if temp[index] < -5:
                value *= 0.6
            moist[index] = value

        # Карта, посчитанная честно, почти всегда выходит либо сплошной
        # степью, либо сплошным лесом: всё зависит от того, как легли
        # хребты. Поэтому влагу ещё и выравниваем по порядку — самый
        # сухой гекс остаётся самым сухим, но между сухим и мокрым
        # появляется весь промежуток, а с ним и все биомы.
        if land:
            order = sorted(land, key=lambda index: moist[index])
            last = max(1, len(order) - 1)
            middle = 0.38 + 0.30 * self.wetness
            for rank, index in enumerate(order):
                spread = rank / float(last)
                even = spread ** (1.0 if self.wetness >= 0.5 else 1.4)
                even = even * (0.55 + 0.9 * middle)
                moist[index] = max(0.0, min(1.0,
                                            0.35 * moist[index] + 0.65 * even))
        return moist

    # --- реки -------------------------------------------------------------

    def _rivers(self, elev, flags) -> tuple:
        flow = array("i", [-1]) * self.size
        accum = array("f", [1.0]) * self.size
        basins = array("i", [-1]) * self.size

        land = [index for index in range(self.size) if elev[index] >= SEA_LEVEL]
        land.sort(key=lambda index: -elev[index])
        for index in land:
            best, best_elev = -1, elev[index]
            for other in self.neighbors(index):
                if elev[other] < best_elev:
                    best, best_elev = other, elev[other]
            flow[index] = best
        for index in land:
            target = flow[index]
            if target >= 0:
                accum[target] += accum[index]

        number = 0
        mouths = {}
        for index in land:
            if flow[index] >= 0 and elev[flow[index]] >= SEA_LEVEL:
                continue
            mouths[index] = number
            number += 1
        for index in land:
            current, guard = index, 0
            while current >= 0 and guard < 4 * self.width:
                if current in mouths:
                    basins[index] = mouths[current]
                    break
                current = flow[current]
                guard += 1

        threshold = max(12.0, self.size / 900.0)
        for index in land:
            if accum[index] >= threshold:
                flags[index] |= wm.FLAG_RIVER
        return flow, accum, basins

    # --- биомы -------------------------------------------------------------

    def _biomes(self, elev, temp, moist, flags) -> array:
        biome = array("B", [0]) * self.size
        for index in range(self.size):
            if elev[index] < SEA_LEVEL:
                if flags[index] & wm.FLAG_LAKE:
                    biome[index] = 9
                    continue
                depth = (SEA_LEVEL - elev[index]) / SEA_LEVEL
                if temp[index] < -2:
                    biome[index] = 0
                elif depth < 0.12:
                    biome[index] = 3
                elif depth < 0.3:
                    biome[index] = 4
                elif depth < 0.5:
                    biome[index] = 5
                elif depth < 0.75:
                    biome[index] = 6
                else:
                    biome[index] = 7
                continue

            metres = self.metres_of(elev[index])
            heat, wet = temp[index], moist[index]
            if metres > 3200:
                biome[index] = 16 if heat < 2 else 15
            elif heat < -8:
                biome[index] = 11
            elif heat < -3:
                biome[index] = 12 if wet < 0.3 else 13
            elif heat < 2:
                biome[index] = 14 if wet > 0.25 else 18
            elif heat < 7:
                if wet > 0.62:
                    biome[index] = 17
                elif wet > 0.35:
                    biome[index] = 35
                else:
                    biome[index] = 18
            elif heat < 15:
                if wet > 0.75:
                    biome[index] = 21
                elif wet > 0.5:
                    biome[index] = 20
                elif wet > 0.3:
                    biome[index] = 36
                else:
                    biome[index] = 19
            elif heat < 22:
                if wet > 0.78:
                    biome[index] = 37
                elif wet > 0.55:
                    biome[index] = 20
                elif wet > 0.33:
                    biome[index] = 22
                elif wet > 0.18:
                    biome[index] = 19
                else:
                    biome[index] = 32
            else:
                if wet > 0.8:
                    biome[index] = 28
                elif wet > 0.62:
                    biome[index] = 27
                elif wet > 0.45:
                    biome[index] = 26
                elif wet > 0.3:
                    biome[index] = 24
                elif wet > 0.17:
                    biome[index] = 25
                else:
                    biome[index] = 23 if self.rng.chance(0.6) else 31

            # Низины у воды заболачиваются, у моря в тепле растут мангры.
            if flags[index] & wm.FLAG_RIVER and moist[index] > 0.6 \
                    and metres < 300:
                biome[index] = 10
            elif flags[index] & wm.FLAG_COAST and heat > 21 and wet > 0.55:
                biome[index] = 29
            elif wet < 0.12 and flags[index] & wm.FLAG_COAST and heat > 18:
                biome[index] = 30
        return biome

    # --- прочие слои -------------------------------------------------------

    def _fertility(self, biome, moist, flags, elev) -> array:
        rich = {10: 0.6, 17: 0.45, 19: 0.55, 20: 0.75, 21: 0.8, 22: 0.5,
                24: 0.5, 25: 0.45, 26: 0.7, 27: 0.72, 28: 0.7, 29: 0.5,
                33: 0.8, 35: 0.35, 36: 0.75, 37: 0.6, 38: 0.4, 39: 0.35,
                14: 0.25, 13: 0.15, 18: 0.12, 23: 0.05, 31: 0.03, 32: 0.05,
                30: 0.05, 34: 0.02, 15: 0.3, 16: 0.05, 11: 0.0, 12: 0.02}
        out = array("f", [0.0]) * self.size
        for index in range(self.size):
            if elev[index] < SEA_LEVEL:
                continue
            value = rich.get(biome[index], 0.3)
            value += 0.18 if flags[index] & wm.FLAG_RIVER else 0.0
            value += 0.06 if flags[index] & wm.FLAG_COAST else 0.0
            value *= 0.75 + 0.5 * moist[index]
            out[index] = max(0.0, min(1.0, value))
        return out

    def _riches(self, elev, stress, biome) -> tuple:
        ore = self._noise(octaves=5, smooth=1)
        rich = array("B", [0]) * self.size
        resflags = array("B", [0]) * self.size
        for index in range(self.size):
            if elev[index] < SEA_LEVEL:
                continue
            value = 0.35 * ore[index] + 0.5 * max(0.0, stress[index])
            value += 0.25 * max(0.0, (elev[index] - SEA_LEVEL) * 2.0)
            rich[index] = int(max(0, min(255, value * 255)))
            bits = 0
            if biome[index] in (17, 20, 21, 26, 27, 28, 37):
                bits |= 1               # лес
            if biome[index] in (19, 24, 25, 36):
                bits |= 2               # выпас
            if rich[index] > 150:
                bits |= 4               # руда
            resflags[index] = bits
        return rich, resflags

    def _magic(self) -> array:
        field = self._noise(octaves=4, smooth=2)
        out = array("f", [0.0]) * self.size
        strength = 0.3 + 1.4 * self.magic_level
        for index in range(self.size):
            out[index] = (field[index] - 0.5) * 2.0 * strength
        return out

    def _savagery(self, elev, biome, flags) -> array:
        wild = self._noise(octaves=4, smooth=1)
        out = array("B", [0]) * self.size
        harsh = {11, 12, 16, 23, 31, 32, 34, 10, 28, 29, 38}
        for index in range(self.size):
            if elev[index] < SEA_LEVEL:
                continue
            value = 0.35 + 0.5 * wild[index]
            if biome[index] in harsh:
                value += 0.25
            if flags[index] & wm.FLAG_COAST:
                value -= 0.1
            out[index] = int(max(0, min(255, value * 255)))
        return out

    def _aquifer(self, moist, flags) -> array:
        out = array("B", [0]) * self.size
        for index in range(self.size):
            value = moist[index] * 200
            if flags[index] & wm.FLAG_RIVER:
                value += 55
            out[index] = int(max(0, min(255, value)))
        return out

    def _volcanoes(self, elev, stress, flags) -> tuple:
        distv = array("B", [99]) * self.size
        spots = []
        count = max(3, int(self.size / 2200))
        pairs = []
        for index in range(self.size):
            if elev[index] < SEA_LEVEL or stress[index] < 0.25:
                continue
            pairs.append((index, stress[index] + elev[index]))
        pairs.sort(key=lambda pair: -pair[1])
        step = max(1, len(pairs) // max(1, count * 6))
        for number, (index, _) in enumerate(pairs[::step][:count]):
            spots.append({"id": number, "i": index,
                          "name": make_name(self.rng)})
        # Расстояние до ближайшего вулкана — волной по соседям.
        front = [(item["i"], 0) for item in spots]
        for index, value in front:
            distv[index] = value
        while front:
            index, value = front.pop(0)
            if value >= 12:
                continue
            for other in self.neighbors(index):
                if distv[other] > value + 1:
                    distv[other] = value + 1
                    front.append((other, value + 1))
        return distv, spots

    def _events(self, elev, temp, moist, flags, distv, biome) -> tuple:
        mask = array("h", [0]) * self.size
        chance = array("B", [0]) * self.size
        for index in range(self.size):
            bits, risk = 0, 0.0
            land = elev[index] >= SEA_LEVEL
            if not land:
                continue
            metres = self.metres_of(elev[index])
            if flags[index] & wm.FLAG_COAST:
                bits |= 1 << 0          # ураган
                bits |= 1 << 7          # цунами
                risk += 0.25
            if moist[index] < 0.2:
                bits |= 1 << 1 | 1 << 8  # песчаная буря, засуха
                risk += 0.3
            if temp[index] < 0:
                bits |= 1 << 2          # буран
                risk += 0.2
            if distv[index] < 4:
                bits |= 1 << 3          # извержение
                risk += 0.35
            if flags[index] & wm.FLAG_RIVER:
                bits |= 1 << 4          # паводок
                risk += 0.2
            if biome[index] in (17, 19, 20, 24, 36):
                bits |= 1 << 5          # лесной пожар
                risk += 0.15
            if metres > 1800:
                bits |= 1 << 6 | 1 << 10  # лавина, землетрясение
                risk += 0.25
            if moist[index] > 0.6 and temp[index] > 18:
                bits |= 1 << 9          # поветрие
                risk += 0.2
            # Добрые приметы: там, где живётся легко.
            if moist[index] > 0.35 and 6 < temp[index] < 24:
                bits |= 1 << 11 | 1 << 13
            if flags[index] & wm.FLAG_COAST:
                bits |= 1 << 12
            mask[index] = bits
            chance[index] = int(max(0, min(255, risk * 180)))
        return mask, chance

    def _ranges(self, elev, flags) -> tuple:
        reg = array("i", [-1]) * self.size
        ranges = []
        seen = set()
        limit = SEA_LEVEL + (1.0 - SEA_LEVEL) * 0.32
        for index in range(self.size):
            if index in seen or elev[index] < limit:
                continue
            group, stack = [], [index]
            while stack:
                current = stack.pop()
                if current in seen or elev[current] < limit:
                    continue
                seen.add(current)
                group.append(current)
                stack.extend(self.neighbors(current))
            if len(group) < 8:
                continue
            number = len(ranges)
            for item in group:
                reg[item] = number
            middle = group[len(group) // 2]
            ranges.append({"id": number, "hexes": group,
                           "cx": middle % self.width,
                           "cy": middle // self.width,
                           "area": len(group)})
        return reg, ranges

    # --- хвост ------------------------------------------------------------

    def _tail(self, elev, flags, land_reg, water_reg, ranges, volcanoes,
              biome, savage, rich) -> dict:
        features = []
        number = 0

        def add(kind, hexes):
            nonlocal number
            if not hexes:
                return
            middle = hexes[len(hexes) // 2]
            features.append({
                "id": number, "type": kind, "name": make_name(self.rng),
                "cx": middle % self.width, "cy": middle // self.width,
                "area": len(hexes)})
            number += 1

        waters, lands = {}, {}
        for index in range(self.size):
            if water_reg[index] >= 0:
                waters.setdefault(water_reg[index], []).append(index)
            if land_reg[index] >= 0:
                lands.setdefault(land_reg[index], []).append(index)
        for key in sorted(waters, key=lambda k: -len(waters[k]))[:6]:
            group = waters[key]
            kind = "ocean" if len(group) > self.size * 0.08 else "sea"
            if len(group) < 30:
                kind = "lake"
            add(kind, group)
        for key in sorted(lands, key=lambda k: -len(lands[k]))[:8]:
            group = lands[key]
            add("continent" if len(group) > 300 else "island", group)
        for item in sorted(ranges, key=lambda r: -r["area"])[:8]:
            add("range", item["hexes"])

        peaks = []
        highest = sorted((index for index in range(self.size)
                          if elev[index] >= SEA_LEVEL),
                         key=lambda index: -elev[index])[:10]
        for order, index in enumerate(highest[::max(1, len(highest) // 8 or 1)]):
            metres = self.metres_of(elev[index])
            peaks.append({"id": order, "i": index, "name": make_name(self.rng),
                          "alt": int(metres)})

        lairs = self._lairs(elev, savage, biome)
        tribes = self._tribe_spots(elev, flags, biome)
        minerals = {}
        for index in range(self.size):
            if rich[index] > 190:
                minerals[str(index)] = int(rich[index])

        return {
            "biomeNames": list(BIOME_NAMES),
            "features": features,
            "peaks": peaks,
            "volcanoes": [{"id": item["id"], "i": item["i"],
                           "name": item["name"]} for item in volcanoes],
            "lairs": lairs,
            "tribes": tribes,
            "minerals": minerals,
            "events": {"maskLayer": wm.L_EVENTMASK,
                       "chanceLayer": wm.L_EVENTCHANCE,
                       "events": [dict(item) for item in EVENT_CATALOG]},
            "climate": self._climate(),
            "seeds": {"master": self.seed_text},
            "naming": {"source": "Хронист"},
        }

    def _lairs(self, elev, savage, biome) -> list:
        spots = []
        wild = [index for index in range(self.size)
                if elev[index] >= SEA_LEVEL and savage[index] > 150]
        if not wild:
            wild = [index for index in range(self.size)
                    if elev[index] >= SEA_LEVEL]
        count = max(3, min(9, int(self.size / 2600)))
        for number in range(count):
            if not wild:
                break
            index = self.rng.choice(wild)
            wild = [item for item in wild if abs(item - index) > self.width]
            kind, kind_name, klass, tier = self.rng.choice(LAIR_KINDS)
            role = self.rng.choice(LAIR_ROLES)
            spots.append({
                "id": number, "hookId": "lair:%d" % number, "kind": kind,
                "kindName": kind_name, "name": make_name(self.rng),
                "i": index, "biome": int(biome[index]),
                "alignment": round(self.rng.uniform(-1.0, 0.4), 2),
                "tier": tier, "role": role, "catastropheClass": klass,
                "suggestedAgeYears": self.rng.randint(600, 6000),
            })
        return spots

    def _tribe_spots(self, elev, flags, biome) -> list:
        spots = []
        good = [index for index in range(self.size)
                if elev[index] >= SEA_LEVEL
                and (flags[index] & (wm.FLAG_RIVER | wm.FLAG_COAST))]
        count = max(3, min(10, len(good) // 220))
        for number in range(count):
            if not good:
                break
            index = self.rng.choice(good)
            good = [item for item in good if abs(item - index) > self.width * 2]
            spots.append({"id": number, "anchor": index,
                          "name": make_name(self.rng),
                          "marine": bool(flags[index] & wm.FLAG_COAST),
                          "mammoth": biome[index] in (13, 14, 35)})
        return spots

    def _climate(self) -> dict:
        events = []
        span = 10000
        year = self.rng.randint(200, 1200)
        number = 0
        while year < span - 300 and number < 7:
            kind, name, d_t, d_p, d_mag, length = self.rng.choice(CLIMATE_KINDS)
            duration = self.rng.randint(*length)
            events.append({
                "id": number, "type": kind, "name": name, "start": year,
                "dur": duration,
                "dT": round(d_t * self.rng.uniform(0.6, 1.2), 3),
                "dP": round(d_p * self.rng.uniform(0.6, 1.2), 3),
                "dMag": round(d_mag * self.rng.uniform(0.6, 1.2), 3),
                "profile": self.rng.choice(("ramp", "trap", "spike")),
            })
            number += 1
            year += duration + self.rng.randint(300, 1800)
        return {"worldSpan": span, "currentYear": 0, "latSensitivity": 0.6,
                "events": events}


# --- как карта выглядит ------------------------------------------------

# Цвет каждого биома — чтобы карту можно было посмотреть глазами, а не
# только числами. Вода уходит в синеву, лес в зелень, пустыня в охру.
BIOME_COLORS = {
    0: "#dbe7f0", 1: "#2e9fa8", 2: "#1f7f86", 3: "#3aa6c8", 4: "#2b7fae",
    5: "#1f6796", 6: "#164f77", 7: "#0f3a5c", 8: "#0a2a44", 9: "#4aa3d8",
    10: "#5c7a4a", 11: "#f2f6fa", 12: "#dfe6ec", 13: "#c9d6cf", 14: "#a8bba6",
    15: "#9fae8a", 16: "#8d8a86", 17: "#2f6b4a", 18: "#c2bda2", 19: "#bfc06a",
    20: "#3f8d43", 21: "#2c7a4e", 22: "#94a05a", 23: "#e0c584",
    24: "#c7b558", 25: "#b7bd63", 26: "#2f7f57", 27: "#347a4a", 28: "#1f6b3c",
    29: "#4b7d63", 30: "#d9d2b8", 31: "#e6cf98", 32: "#cbb98a", 33: "#6fae62",
    34: "#9b8a72", 35: "#6f8f6a", 36: "#8fae5c", 37: "#3b8f6a", 38: "#6a7f5a",
    39: "#8c9a6a",
}
WATER_COLOR = "#2b6ea8"
LAND_COLOR = "#7a8a5a"


def color_of(biome_id: int) -> str:
    return BIOME_COLORS.get(int(biome_id), LAND_COLOR)


def color_grid(wmap) -> list:
    """Карта строками цветов — как её рисует окно программы."""
    biome = wmap.layer(wm.L_BIOME)
    flags = wmap.layer(wm.L_FLAGS)
    rows = []
    for y in range(wmap.height):
        row = []
        for x in range(wmap.width):
            index = y * wmap.width + x
            colour = color_of(biome[index]) if biome is not None else LAND_COLOR
            if flags is not None and flags[index] & wm.FLAG_RIVER:
                colour = "#4f9bd6"
            row.append(colour)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Снаружи
# ---------------------------------------------------------------------------

def forge(seed: str, size=DEFAULT_SIZE, **kwargs) -> wm.WorldMap:
    """Сделать карту по сиду."""
    return MapForge(seed, size=size, **kwargs).build()


_DT_FOR_LAYER = {
    wm.L_ELEV: wm.DT_F32, wm.L_TEMP: wm.DT_F32, wm.L_MOIST: wm.DT_F32,
    wm.L_BIOME: wm.DT_U8, wm.L_FLAGS: wm.DT_U8, wm.L_FERTILITY: wm.DT_F32,
    wm.L_PLATE: wm.DT_I16, wm.L_STRESS: wm.DT_F32, wm.L_DISTV: wm.DT_U8,
    wm.L_FLOWTO: wm.DT_I32, wm.L_ACCUM: wm.DT_F32, wm.L_RICHNESS: wm.DT_U8,
    wm.L_RESFLAGS: wm.DT_U8, wm.L_EVENTMASK: wm.DT_I16,
    wm.L_EVENTCHANCE: wm.DT_U8, wm.L_MAGIC: wm.DT_F32, wm.L_AQUIFER: wm.DT_U8,
    wm.L_SAVAGERY: wm.DT_U8, wm.L_LANDREG: wm.DT_I32,
    wm.L_WATERREG: wm.DT_I32, wm.L_RANGEREG: wm.DT_I32,
    wm.L_RIVERREG: wm.DT_I32,
}


def save(wmap: wm.WorldMap, path: str) -> str:
    """Записать карту файлом .world — тем же, что читает движок."""
    chunks = []
    for layer_id in sorted(wmap.layers):
        data = wmap.layers[layer_id]
        dtype = _DT_FOR_LAYER.get(layer_id, wm.DT_F32)
        blob = data.tobytes()
        chunks.append(struct.pack("<BBBBI", layer_id, dtype, 0, 0, len(blob))
                      + blob)
    body = b"".join(chunks)
    tail = json.dumps(wmap.tail, ensure_ascii=False).encode("utf-8")
    json_offset = wm.HEADER_SIZE + len(body)
    header = bytearray(wm.HEADER_SIZE)
    header[0:4] = wm.MAGIC
    struct.pack_into("<HHIIQIfffII", header, 4, 1, int(wmap.wrap),
                     wmap.width, wmap.height, wmap.seed_value & 0xFFFFFFFFFFFFFFFF,
                     len(wmap.layers), wmap.sea, wmap.min_alt, wmap.max_alt,
                     json_offset, len(tail))
    with open(path, "wb") as handle:
        handle.write(bytes(header))
        handle.write(body)
        handle.write(tail)
    return path
