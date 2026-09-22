# -*- coding: utf-8 -*-
"""Worldforge: физическая генерация мира — тектоника, климат, реки, биомы.

Это перенос исходного генератора карт (TECTONIC WORLDFORGE v5.2) с
JavaScript на Python, шаг за шагом, в том же порядке и с той же
арифметикой. Порядок важен дважды: во-первых, каждый следующий слой
опирается на предыдущий; во-вторых, ГСЧ один на весь мир, и стоит
поменять местами два обращения к нему — получится другой мир.

Что здесь происходит по порядку:

  1. Ядра континентов — повёрнутые эллипсы, размытые доменным
     искажением, чтобы материки не были кругами.
  2. Плиты — искажённая мозаика Вороного; на стыках считается
     напряжение: сходятся плиты или расходятся.
  3. Высоты — континентальный шельф, горные пояса по стыкам плит,
     острова, горячие точки, вулканические конусы.
  4. Гидравлическая эрозия — капли воды точат рельеф.
  5. Уровень моря — перцентиль высот, а не абсолютное число.
  6. Океанские течения, температура, влага с переносом ветром.
  7. Озёра и реки — заполнение впадин по Пристли, порядок Штралера,
     дельты в устьях больших рек.
  8. Биомы — по температуре и осадкам с поправкой на испарение.
  9. Области и имена, пики, вулканы, плодородие, магия.

Числа с плавающей точкой хранятся в array('f') — это те же 32 бита,
что Float32Array в исходнике, и округление при записи здесь такое же.
"""

from __future__ import annotations

import math
from array import array

from .rng import make_noise, rng_from

# Соседи в odd-r гексовой сетке: отдельно для чётных и нечётных строк.
ODDR = (
    ((+1, 0), (0, -1), (-1, -1), (-1, 0), (-1, +1), (0, +1)),
    ((+1, 0), (+1, -1), (0, -1), (-1, 0), (0, +1), (+1, +1)),
)

SIZES = {
    "small": (160, 96),
    "medium": (280, 168),
    "large": (500, 300),
}

SIZE_NAMES = {
    "small": "малая",
    "medium": "средняя",
    "large": "большая",
}

# Ползунки исходного генератора со значениями по умолчанию.
DEFAULT_K = {
    "seaLevel": 50, "coastline": 55, "oceanDepth": 50, "tectonics": 50,
    "mountains": 60, "volcanism": 40, "erosion": 45, "peaks": 10,
    "volcanoes": 35, "islands": 45, "archipelago": 50, "coastIslets": 45,
    "temperature": 0, "humidity": 50, "rivers": 50, "lakes": 50,
    "magic": 35, "alignment": 50,
}

# Имена ползунков по-русски — для окна настроек.
K_NAMES = (
    ("seaLevel", "Уровень моря"),
    ("coastline", "Изрезанность берегов"),
    ("oceanDepth", "Перепады глубин океана"),
    ("tectonics", "Тектоника"),
    ("mountains", "Горы"),
    ("volcanism", "Вулканизм"),
    ("erosion", "Эрозия"),
    ("peaks", "Именных вершин"),
    ("volcanoes", "Вулканов"),
    ("islands", "Острова"),
    ("archipelago", "Архипелаги"),
    ("coastIslets", "Прибрежные островки"),
    ("temperature", "Тепло мира"),
    ("humidity", "Влажность"),
    ("rivers", "Реки"),
    ("lakes", "Озёра"),
    ("magic", "Магия"),
    ("alignment", "Светлая или тёмная магия"),
)

PALETTES = (
    {"o": ('Kor', 'Vael', 'Thal', 'Mor', 'Aer', 'Dra', 'Sol', 'Bryn',
           'Cael', 'Tor', 'Vyr', 'Os'),
     "m": ('a', 'o', 'e', 'an', 'or', 'el', 'ad', 'ir', 'os'),
     "e": ('ia', 'eth', 'os', 'an', 'ar', 'or', 'un', 'ys', 'en', 'al')},
    {"o": ('Ish', 'Zan', 'Mei', 'Tao', 'Rho', 'Xan', 'Qel', 'Vish', 'Nor',
           'Suo', 'Kai'),
     "m": ('a', 'i', 'u', 'en', 'ai', 'ou', 'an'),
     "e": ('ara', 'un', 'eth', 'io', 'aan', 'esh', 'ur', 'ai')},
    {"o": ('Brann', 'Fjor', 'Sten', 'Vald', 'Holm', 'Grun', 'Skar', 'Eld',
           'Norn', 'Hael'),
     "m": ('a', 'o', 'e', 'u'),
     "e": ('gard', 'heim', 'vik', 'fell', 'dal', 'stad', 'mark', 'ness')},
)

# Плодородие по биомам — из исходника (FERTB).
FERTB = {
    10: 0.72, 11: 0.01, 12: 0.04, 13: 0.06, 14: 0.12, 15: 0.18, 16: 0.02,
    17: 0.22, 18: 0.07, 19: 0.95, 20: 0.72, 21: 0.58, 22: 0.48, 23: 0.04,
    24: 0.52, 25: 0.58, 26: 0.62, 27: 0.55, 28: 0.42, 29: 0.58, 30: 0.03,
    31: 0.01, 32: 0.02, 33: 0.95, 34: 0.0, 35: 0.30, 36: 0.92, 37: 0.50,
    38: 0.30, 39: 0.35,
}


def _sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def make_namer(rng):
    """Имена мест — тем же перебором палитр, что в исходнике."""

    def pick(items):
        return items[int(rng() * len(items))]

    def namer(style_hint=None):
        if style_hint is None:
            style_hint = int(rng() * len(PALETTES))
        p = PALETTES[style_hint % len(PALETTES)]
        name = pick(p["o"])
        if rng() < 0.55:
            name += pick(p["m"])
        name += pick(p["e"])
        return name[0].upper() + name[1:]

    return namer


class Config:
    """Настройки карты: сид, размер, замыкание по долготе и ползунки."""

    # Пределы ползунков: как в окне исходного генератора. Числа за этими
    # краями не делают карту интереснее, зато счёт может уйти в часы —
    # тысяча материков или пять тысяч именных вершин никому не нужны.
    LIMITS = {"temperature": (-60, 60), "peaks": (0, 60)}
    LIMIT_DEFAULT = (0, 100)

    def __init__(self, seed="aurora-7", size="medium", wrap=True,
                 continents=4, min_alt=-11000.0, max_alt=8849.0, k=None):
        self.seed = str(seed)
        self.size = size if size in SIZES else "medium"
        self.wrap = bool(wrap)
        self.continents = max(1, min(12, int(continents)))
        self.min_alt = float(min_alt)
        self.max_alt = float(max_alt)
        self.k = dict(DEFAULT_K)
        if k:
            for key, value in k.items():
                if key not in self.k:
                    continue
                low, high = self.LIMITS.get(key, self.LIMIT_DEFAULT)
                try:
                    self.k[key] = max(low, min(high, int(value)))
                except (TypeError, ValueError):
                    continue          # мусор в настройках — берём задуманное

    def to_dict(self) -> dict:
        return {"seed": self.seed, "size": self.size, "wrap": self.wrap,
                "continents": self.continents, "minAlt": self.min_alt,
                "maxAlt": self.max_alt, "k": dict(self.k)}


class ForgedWorld:
    """Готовый мир: плотные слои по гексам и разреженные объекты."""

    def __init__(self):
        self.W = 0
        self.H = 0
        self.wrap = True
        self.sea = 0.0
        self.cfg = None
        self.layers = {}
        self.peaks = []
        self.volcanoes = []
        self.features = []
        self.land_frac = 0.0
        self.seconds = 0.0

    # --- то, что нужно расширениям и экспорту ---

    def idx(self, col: int, row: int) -> int:
        return row * self.W + col

    def col_row(self, index: int):
        return index % self.W, index // self.W

    def neighbors(self, index: int):
        return self._nb[index]

    def elev_to_m(self, value: float) -> float:
        sea = self.sea
        if value >= sea:
            return (value - sea) / (1 - sea) * self.cfg.max_alt
        return -(sea - value) / sea * (-self.cfg.min_alt)

    def meters(self, index: int) -> float:
        return self.elev_to_m(self.elev[index])


def _f32(n: int, fill: float = 0.0):
    return array('f', [fill]) * n


def _i32(n: int, fill: int = 0):
    return array('i', [fill]) * n


def _i16(n: int, fill: int = 0):
    return array('h', [fill]) * n


def _u8(n: int, fill: int = 0):
    return array('B', [fill]) * n


def _i8(n: int, fill: int = 0):
    return array('b', [fill]) * n


def _round(value: float) -> int:
    """Math.round: половина округляется вверх, а не к чётному."""
    return int(math.floor(value + 0.5))


class _Forge:
    """Один прогон генерации. Живёт ровно столько, сколько строится мир."""

    def __init__(self, cfg: Config, progress=None):
        self.cfg = cfg
        self.progress = progress
        self.W, self.H = SIZES[cfg.size]
        self.N = self.W * self.H
        self.wrap = cfg.wrap
        self.rng = rng_from(cfg.seed)
        self.noise = make_noise(self.rng)
        self.warp_noise = make_noise(self.rng)

        k = cfg.k
        self.k = k
        self.target_ocean = 0.34 + (k["seaLevel"] / 100.0) * 0.56
        self.n_plates = _round(6 + (k["tectonics"] / 100.0) * 34)
        self.mtn_amt = (k["mountains"] / 100.0) * 1.5
        self.stress_scale = 0.5 + (k["tectonics"] / 100.0) * 1.1
        self.warp_amt = 0.805           # закреплён в исходнике
        self.coast_rough = k["coastline"] / 100.0
        self.islet_amt = k["coastIslets"] / 100.0
        self.ocean_depth_var = k["oceanDepth"] / 100.0
        self.erosion = k["erosion"] / 100.0
        self.river_d = k["rivers"] / 100.0
        self.lake_d = k["lakes"] / 100.0
        self.global_t = k["temperature"]
        self.rainfall = 0.55 + (k["humidity"] / 100.0) * 0.9
        self.island_amt = k["islands"] / 100.0
        self.archi = k["archipelago"] / 100.0
        self.volc = k["volcanism"] / 100.0
        self.magic_amt = k["magic"] / 100.0
        self.align_bias = (k["alignment"] - 50) / 50.0
        self.min_alt = cfg.min_alt
        self.max_alt = cfg.max_alt

        self.sea = 0.0
        self._nb = None

    # ------------------------------------------------------------------
    # Общие мелочи
    # ------------------------------------------------------------------

    def idx(self, col: int, row: int) -> int:
        return row * self.W + col

    def wdx(self, a: float, b: float) -> float:
        """Разница по долготе с учётом того, что мир может замыкаться."""
        d = a - b
        if self.wrap:
            half = self.W / 2.0
            if d > half:
                d -= self.W
            if d < -half:
                d += self.W
        return d

    def fbm(self, x: float, y: float, f: float, oct_count: int) -> float:
        noise = self.noise
        a, s, nrm = 1.0, 0.0, 0.0
        if self.wrap:
            ang = (x / self.W) * 2 * math.pi
            radius = self.W / (2 * math.pi)
            ca, sa = math.cos(ang), math.sin(ang)
            for _ in range(oct_count):
                v = noise(ca * radius * f * 0.0628, y * f * 0.02,
                          sa * radius * f * 0.0628)
                s += v * a
                nrm += a
                a *= 0.5
                f *= 2
        else:
            for _ in range(oct_count):
                v = noise(x * f * 0.02, y * f * 0.02, 13.37)
                s += v * a
                nrm += a
                a *= 0.5
                f *= 2
        return s / nrm

    def warped_sample(self, c: float, r: float, f: float,
                      oct_count: int) -> float:
        """Шум по искажённым координатам — узор перестаёт быть решёткой."""
        wx = self.warp_amt * self.fbm(c + 131, r + 57, f * 0.5, 2) * 6
        wy = self.warp_amt * self.fbm(c + 311, r + 929, f * 0.5, 2) * 6
        return self.fbm(c + wx, r + wy, f, oct_count)

    def ridged(self, c: float, r: float, freq: float,
               oct_count: int) -> float:
        """Хребтовый шум: острые гребни вместо пологих холмов."""
        total, amp, f, w, norm = 0.0, 0.5, freq, 1.0, 0.0
        for o in range(oct_count):
            n = self.fbm(c + o * 37.3, r + o * 13.1, f, 1)
            n = 1 - abs(n)
            n *= n
            n *= w
            w = max(0.0, min(1.0, n * 2.2))
            total += n * amp
            norm += amp
            amp *= 0.5
            f *= 2
        return total / norm

    def build_neighbors(self) -> None:
        """Соседи каждого гекса считаются один раз и лежат готовыми."""
        W, H, wrap = self.W, self.H, self.wrap
        out = []
        for r in range(H):
            table = ODDR[r & 1]
            for c in range(W):
                cell = []
                for dc, dr in table:
                    nr = r + dr
                    if nr < 0 or nr >= H:
                        continue
                    nc = c + dc
                    if nc < 0 or nc >= W:
                        if wrap:
                            nc = (nc + W) % W
                        else:
                            continue
                    cell.append(nr * W + nc)
                out.append(tuple(cell))
        self._nb = out

    def elev_to_m(self, value: float) -> float:
        sea = self.sea
        if value >= sea:
            return (value - sea) / (1 - sea) * self.max_alt
        return -(sea - value) / sea * (-self.min_alt)

    def say(self, part: float, note: str) -> None:
        if self.progress is not None:
            self.progress(part, note)

    # ------------------------------------------------------------------
    # 1. Ядра континентов
    # ------------------------------------------------------------------

    def step_continents(self) -> None:
        """Поле континентальности: где суша вообще может быть.

        Материк начинается с эллипса, но к расстоянию до его ядра
        прибавляется крупное доменное искажение и многооктавный шум —
        поэтому у берега появляются заливы, полуострова и перешейки, а
        круг перестаёт быть кругом. Доля суши от этого не меняется:
        уровень моря берётся перцентилем, а не абсолютной высотой.
        """
        rng, W, H = self.rng, self.W, self.H
        cores = []
        for _ in range(self.cfg.continents):
            cores.append({
                "x": rng() * W,
                "y": 0.14 * H + rng() * 0.72 * H,
                "rad": (0.13 + rng() * 0.13) * H,
                "ax": 0.65 + rng() * 0.8,
                "ay": 0.65 + rng() * 0.8,
                "rot": rng() * 6.283,
            })
        self.cores = cores

        bigwarp = H * 0.17
        cont = _f32(self.N)
        rough = self.coast_rough
        warped, fbm, wdx = self.warped_sample, self.fbm, self.wdx
        for r in range(H):
            row = r * W
            for c in range(W):
                wx = warped(c + 417, r + 913, 0.55, 4) * bigwarp
                wy = warped(c + 1231, r + 77, 0.55, 4) * bigwarp
                sc, sr = c + wx, r + wy
                best = -2.0
                for co in cores:
                    dx = wdx(sc, co["x"])
                    dy = sr - co["y"]
                    ca, sa = math.cos(co["rot"]), math.sin(co["rot"])
                    rx = (dx * ca + dy * sa) / co["ax"]
                    ry = (-dx * sa + dy * ca) / co["ay"]
                    v = 1 - math.sqrt(rx * rx + ry * ry) / co["rad"]
                    if v > best:
                        best = v
                cn = (fbm(c + 700, r + 1300, 0.9, 5) * (0.30 + rough * 0.30)
                      + fbm(c + 2200, r + 640, 2.1, 4) * (0.05 + rough * 0.42))
                cont[row + c] = max(-1.0, best + cn)
        self.cont = cont

    # ------------------------------------------------------------------
    # 2. Плиты
    # ------------------------------------------------------------------

    def step_plates(self) -> None:
        """Мозаика плит и напряжение на стыках.

        Плита — это точка со своей скоростью; гекс принадлежит ближайшей.
        На стыке двух плит считается, сходятся они или расходятся: из
        этого потом вырастут горные пояса и рифтовые впадины.
        """
        rng, W, H, N = self.rng, self.W, self.H, self.N
        seeds = []
        for _ in range(self.n_plates):
            a = rng() * 6.283
            sp = 0.4 + rng() * 0.9
            seeds.append({"x": rng() * W, "y": rng() * H,
                          "vx": math.cos(a) * sp, "vy": math.sin(a) * sp})
        self.seeds = seeds

        plate_of = _i16(N)
        stress = _f32(N)
        pw = W * 0.045
        warp, wdx = self.warp_noise, self.wdx
        scale = self.stress_scale
        for r in range(H):
            row = r * W
            for c in range(W):
                i = row + c
                ox = pw * (warp(c * 0.05, r * 0.05, 1.3)
                           + 0.5 * warp(c * 0.11, r * 0.11, 4.1))
                oy = pw * (warp(c * 0.05 + 50, r * 0.05 + 50, 7.7)
                           + 0.5 * warp(c * 0.11 + 9, r * 0.11 + 9, 2.2))
                sc, sr = c + ox, r + oy
                b1, b2, d1, d2 = -1, -1, 1e9, 1e9
                for s in range(len(seeds)):
                    dx = wdx(sc, seeds[s]["x"])
                    dy = sr - seeds[s]["y"]
                    d = dx * dx + dy * dy
                    if d < d1:
                        d2, b2, d1, b1 = d1, b1, d, s
                    elif d < d2:
                        d2, b2 = d, s
                plate_of[i] = b1
                if b2 >= 0:
                    a_seed, b_seed = seeds[b1], seeds[b2]
                    nx = wdx(b_seed["x"], a_seed["x"])
                    ny = b_seed["y"] - a_seed["y"]
                    nl = math.hypot(nx, ny) or 1.0
                    nx /= nl
                    ny /= nl
                    rel = ((a_seed["vx"] - b_seed["vx"]) * nx
                           + (a_seed["vy"] - b_seed["vy"]) * ny)
                    edge = 1 - min(1.0, (math.sqrt(d2) - math.sqrt(d1)) / 7)
                    stress[i] = rel * max(0.0, edge) * scale
        self.plate_of = plate_of
        self.stress = stress

    # ------------------------------------------------------------------
    # 3. Высоты
    # ------------------------------------------------------------------

    def _cont_at(self, x: float, y: float) -> float:
        best = -2.0
        for co in self.cores:
            dx = self.wdx(x, co["x"])
            dy = y - co["y"]
            v = 1 - math.sqrt(dx * dx + dy * dy) / co["rad"]
            if v > best:
                best = v
        return max(-1.0, best)

    def step_elevation(self) -> None:
        """Высоты: шельф у берега, горные пояса по стыкам плит, острова.

        Внутренность материка нарочно низкая и плоская: высоту дают
        тектоника и хребтовый шум, а не расстояние до центра. Иначе
        каждый материк выходил бы куполом.
        """
        rng, W, H, N = self.rng, self.W, self.H, self.N
        cont, stress = self.cont, self.stress
        warped, fbm, ridged, wdx = (self.warped_sample, self.fbm,
                                    self.ridged, self.wdx)
        elev = _f32(N)

        # Горячие точки: цепочки вулканических островов в открытом океане.
        hotspots = []
        n_hot = _round(self.volc * 10)
        for _ in range(n_hot):
            x = y = 0.0
            tries = 0
            while True:
                x = rng() * W
                y = 0.12 * H + rng() * 0.76 * H
                tries += 1
                if not (tries < 20 and self._cont_at(x, y) > -0.15):
                    break
            ang = rng() * 6.283
            length = 4 + rng() * 10
            count = 2 + int(rng() * 5)
            hotspots.append({"x": x, "y": y, "ang": ang, "len": length,
                             "n": count, "h": 0.4 + rng() * 0.5})

        big_islands = []
        n_big = _round((self.island_amt * 0.5 + self.archi * 0.5) * 5)
        for _ in range(n_big):
            x = y = 0.0
            tries = 0
            while True:
                x = rng() * W
                y = 0.14 * H + rng() * 0.72 * H
                tries += 1
                if not (tries < 25 and self._cont_at(x, y) > -0.2):
                    break
            big_islands.append({"x": x, "y": y,
                                "rad": (0.03 + rng() * 0.06) * H,
                                "h": 0.25 + rng() * 0.4})

        depth_var = self.ocean_depth_var
        islet = self.islet_amt
        gate = 0.93 - islet * 0.75
        for r in range(H):
            row = r * W
            lat = r / (H - 1)
            polar = math.sin(lat * math.pi)
            for c in range(W):
                i = row + c
                detail = warped(c, r, 3, 5)
                med = warped(c + 90, r + 40, 7, 4)
                cv = cont[i]
                if cv <= -0.2:
                    e = cv * 0.9 + (detail * 0.3 + med * 0.12) * (depth_var * 2)
                else:
                    coast = min(1.0, (cv + 0.2) / 0.30)
                    base = 0.04 + coast * 0.30
                    base += warped(c + 260, r + 730, 1.0, 3) * 0.16
                    e = base + detail * 0.14 + med * 0.09
                if e < 0.04:
                    a_large = warped(c + 500, r + 300, 5, 3)
                    a_small = warped(c + 800, r + 650, 12, 3)
                    a_field = a_large * 0.6 + a_small * 0.5
                    if a_field > gate:
                        e += (a_field - gate) * (1.0 + islet * 2.0)
                    for b in big_islands:
                        dx = wdx(c, b["x"])
                        dy = r - b["y"]
                        d = math.sqrt(dx * dx + dy * dy) / b["rad"]
                        if d < 1.4:
                            e += max(0.0, 1 - d) * b["h"] * 1.3
                    for hs in hotspots:
                        for s in range(hs["n"]):
                            px = hs["x"] + math.cos(hs["ang"]) * hs["len"] * s
                            py = hs["y"] + math.sin(hs["ang"]) * hs["len"] * s
                            dx = wdx(c, px)
                            dy = r - py
                            d = math.hypot(dx, dy)
                            if d < 2.6:
                                e += (max(0.0, (2.6 - d) / 2.6) * hs["h"]
                                      * (1 - s / (hs["n"] + 1)))
                e *= (0.5 + 0.5 * polar)
                elev[i] = e

        mtn = self.mtn_amt
        island_amt = self.island_amt
        for r in range(H):
            row = r * W
            for c in range(W):
                i = row + c
                s = stress[i]
                land = cont[i] > -0.2
                if land:
                    if s > 0:
                        elev[i] = elev[i] + s * mtn * 1.28
                    else:
                        elev[i] = elev[i] + s * 0.3
                    mask = max(0.0, fbm(c + 1200, r + 800, 2.2, 3))
                    elev[i] = elev[i] + ridged(c + 15, r + 99, 4.5, 4) * mask * mtn * 0.82
                    plat = fbm(c + 640, r + 410, 1.5, 2)
                    if plat > 0.64:
                        elev[i] = elev[i] + (plat - 0.64) * mtn * 0.5
                else:
                    if s > 0:
                        elev[i] = elev[i] + s * mtn * 0.5
                    if s < 0:
                        elev[i] = elev[i] + (-s) * mtn * 0.7
                    sm = ridged(c + 900, r + 250, 6, 3)
                    elev[i] = elev[i] + sm * 0.16 + max(0.0, sm - 0.84) * 1.5 * island_amt

        ref_lo, rspan = -1.25, 2.7 - (-1.25)
        for i in range(N):
            elev[i] = max(0.0, min(1.0, (elev[i] - ref_lo) / rspan))
        self.elev = elev

    # ------------------------------------------------------------------
    # 4. Гидравлическая эрозия
    # ------------------------------------------------------------------

    def step_erosion(self) -> None:
        """Капли воды точат склоны и оставляют наносы в низинах."""
        if self.erosion <= 0:
            return
        rng, W, H, N = self.rng, self.W, self.H, self.N
        elev = self.elev
        wrap = self.wrap
        drops = int(math.floor(N * 0.5 * self.erosion))
        er = 0.3 * self.erosion
        inertia, cap, evap = 0.05, 4, 0.02
        for _ in range(drops):
            px = rng() * (W - 1)
            py = 1 + rng() * (H - 3)
            dx = dy = 0.0
            vel = water = 1.0
            sed = 0.0
            for _step in range(26):
                x0 = int(math.floor(px))
                y0 = int(math.floor(py))
                if y0 < 1 or y0 >= H - 1:
                    break
                fx, fy = px - x0, py - y0
                x1 = (x0 + 1) % W if wrap else min(x0 + 1, W - 1)
                h00 = elev[y0 * W + x0]
                h10 = elev[y0 * W + x1]
                h01 = elev[(y0 + 1) * W + x0]
                h11 = elev[(y0 + 1) * W + x1]
                gx = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
                gy = (h01 - h00) * (1 - fx) + (h11 - h10) * fx
                dx = dx * inertia - gx * (1 - inertia)
                dy = dy * inertia - gy * (1 - inertia)
                length = math.hypot(dx, dy) or 1.0
                dx /= length
                dy /= length
                h_old = (h00 * (1 - fx) * (1 - fy) + h10 * fx * (1 - fy)
                         + h01 * (1 - fx) * fy + h11 * fx * fy)
                px += dx
                py += dy
                if py < 1 or py >= H - 1:
                    break
                if wrap:
                    px = (px + W) % W
                elif px < 0 or px >= W - 1:
                    break
                nx0 = int(math.floor(px))
                ny0 = int(math.floor(py))
                nfx, nfy = px - nx0, py - ny0
                nx1 = (nx0 + 1) % W if wrap else min(nx0 + 1, W - 1)
                n00 = elev[ny0 * W + nx0]
                n10 = elev[ny0 * W + nx1]
                n01 = elev[(ny0 + 1) * W + nx0]
                n11 = elev[(ny0 + 1) * W + nx1]
                h_new = (n00 * (1 - nfx) * (1 - nfy) + n10 * nfx * (1 - nfy)
                         + n01 * (1 - nfx) * nfy + n11 * nfx * nfy)
                dh = h_new - h_old
                capac = max(-dh, 0.0005) * vel * water * cap
                if sed > capac or dh > 0:
                    drop = min(dh, sed) if dh > 0 else (sed - capac) * 0.25
                    sed -= drop
                    elev[y0 * W + x0] = elev[y0 * W + x0] + drop * (1 - fx) * (1 - fy)
                    elev[y0 * W + x1] = elev[y0 * W + x1] + drop * fx * (1 - fy)
                    elev[(y0 + 1) * W + x0] = elev[(y0 + 1) * W + x0] + drop * (1 - fx) * fy
                    elev[(y0 + 1) * W + x1] = elev[(y0 + 1) * W + x1] + drop * fx * fy
                else:
                    e2 = min((capac - sed) * er, -dh)
                    sed += e2
                    elev[y0 * W + x0] = elev[y0 * W + x0] - e2 * (1 - fx) * (1 - fy)
                    elev[y0 * W + x1] = elev[y0 * W + x1] - e2 * fx * (1 - fy)
                    elev[(y0 + 1) * W + x0] = elev[(y0 + 1) * W + x0] - e2 * (1 - fx) * fy
                    elev[(y0 + 1) * W + x1] = elev[(y0 + 1) * W + x1] - e2 * fx * fy
                vel = math.sqrt(max(0.0, vel * vel + dh * -0.49))
                water *= (1 - evap)
                if water < 0.01:
                    break
        for i in range(N):
            elev[i] = max(0.0, min(1.0, elev[i]))

    # ------------------------------------------------------------------
    # Одинокие стратовулканы
    # ------------------------------------------------------------------

    def step_cones(self) -> None:
        """Конусы, встающие прямо из равнины: 2,5–5 км над округой."""
        rng, W, H = self.rng, self.W, self.H
        elev, cont, wrap = self.elev, self.cont, self.wrap
        cone_sites = []
        count = _round((self.k["volcanoes"] / 100.0) * 7)
        flat_probe = ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0))
        for _ in range(count):
            x = y = 0
            ok = False
            tries = 0
            while tries < 60 and not ok:
                tries += 1
                x = int(rng() * W)
                y = int((0.12 + rng() * 0.74) * H)
                i0 = y * W + x
                if cont[i0] < 0:
                    continue
                if elev[i0] < 0.40 or elev[i0] > 0.58:
                    continue
                flat = True
                for dc, dr in flat_probe:
                    cc = x + dc
                    if cc < 0 or cc >= W:
                        if wrap:
                            cc = (cc + W) % W
                        else:
                            continue
                    rr = y + dr
                    if rr < 1 or rr >= H - 1:
                        continue
                    if abs(elev[rr * W + cc] - elev[i0]) > 0.03:
                        flat = False
                        break
                if flat:
                    ok = True
            if not ok:
                continue
            hgt = 0.17 + rng() * 0.13
            rad = 1.5 + rng() * 1.5
            for dr in range(-6, 7):
                rr = y + dr
                if rr < 1 or rr >= H - 1:
                    continue
                for dc in range(-6, 7):
                    cc = x + dc
                    if cc < 0 or cc >= W:
                        if wrap:
                            cc = (cc + W) % W
                        else:
                            continue
                    d = math.hypot(dc, dr) / rad
                    if d > 2.4:
                        continue
                    j = rr * W + cc
                    elev[j] = min(1.0, elev[j] + hgt * math.exp(-d * d * 1.35))
            cone_sites.append(y * W + x)
        self.cone_sites = cone_sites

    # ------------------------------------------------------------------
    # 5. Уровень моря и океанские течения
    # ------------------------------------------------------------------

    def step_sea(self) -> None:
        """Уровень моря — перцентиль высот: сколько воды, столько и воды."""
        N = self.N
        elev = self.elev
        ordered = sorted(elev)
        place = min(N - 1, max(0, int(math.floor(self.target_ocean * N))))
        self.sea = ordered[place]
        is_ocean = _u8(N)
        sea = self.sea
        for i in range(N):
            is_ocean[i] = 1 if elev[i] < sea else 0
        self.is_ocean = is_ocean
        self.build_neighbors()

    def step_currents(self) -> None:
        """Течения: тёплые несут воду к полюсам, холодные — к равнику.

        Дальше по этому полю считается, насколько море подогревает или
        студит берег, и насколько глубоко материк «не знает моря».
        """
        W, H, N = self.W, self.H, self.N
        is_ocean = self.is_ocean
        warped = self.warped_sample
        cur_anom, cur_vx, cur_vy = _f32(N), _f32(N), _f32(N)
        for i in range(N):
            if not is_ocean[i]:
                continue
            c, r = i % W, i // W
            lat = (r / (H - 1)) * 2 - 1
            swirl = warped(c + 1500, r + 1500, 1.2, 3)
            cur_vx[i] = math.cos(lat * math.pi) * 0.8 + swirl * 0.6
            cur_vy[i] = (-math.sin(lat * math.pi * 1.0) * 0.5
                         + warped(c + 220, r + 990, 1.0, 3) * 0.5)
            polewardness = cur_vy[i] if lat > 0 else -cur_vy[i]
            cur_anom[i] = (swirl * 4.5
                           + polewardness * -3.5 * _sign(lat if lat else 1))
        self.cur_anom, self.cur_vx, self.cur_vy = cur_anom, cur_vx, cur_vy

        # Насколько гекс далёк от моря: волна расходится от берега вглубь.
        dist_o = _f32(N, 1e9)
        origin_a = _f32(N)
        queue = []
        for i in range(N):
            if is_ocean[i]:
                dist_o[i] = 0
                origin_a[i] = cur_anom[i]
                queue.append(i)
        head = 0
        nb = self._nb
        while head < len(queue):
            i = queue[head]
            head += 1
            nd = dist_o[i] + 1
            for j in nb[i]:
                if nd < dist_o[j]:
                    dist_o[j] = nd
                    origin_a[j] = origin_a[i]
                    queue.append(j)
        cont_scale = max(6.0, W * 0.055)
        continental = _f32(N)
        for i in range(N):
            continental[i] = (0.0 if is_ocean[i]
                              else 1 - math.exp(-dist_o[i] / cont_scale))
        self.dist_o, self.origin_a, self.continental = (dist_o, origin_a,
                                                        continental)

    # ------------------------------------------------------------------
    # 6. Климат
    # ------------------------------------------------------------------

    def step_temperature(self) -> None:
        """Температура: широта, высота, море рядом и течения.

        Материковость подмешана слабее к высоким широтам — иначе нутро
        северного материка вымерзает начисто и жить там некому.
        """
        W, H, N = self.W, self.H, self.N
        warped = self.warped_sample
        elev, is_ocean = self.elev, self.is_ocean
        continental, cur_anom, origin_a = (self.continental, self.cur_anom,
                                           self.origin_a)
        elev_to_m = self.elev_to_m
        global_t = self.global_t
        temp = _f32(N)
        for r in range(H):
            row = r * W
            for c in range(W):
                i = row + c
                lat_e = (((r / (H - 1)) * 2 - 1)
                         + warped(c + 777, r + 333, 1.1, 3) * 0.42
                         + warped(c + 55, r + 912, 3.0, 2) * 0.12)
                lat = min(1.0, abs(lat_e))
                m = max(0.0, elev_to_m(elev[i]))
                t = 30 - lat * lat * 44
                t -= m / 1000 * 6.5
                cont_effect = (0.42 - lat) if lat < 0.4 else (0.42 - lat) * 0.55
                t += continental[i] * cont_effect * 17
                t += (cur_anom[i] if is_ocean[i]
                      else origin_a[i] * (1 - continental[i]) * 0.65)
                t += global_t
                t += warped(c + 11, r + 11, 7, 3) * 4.2
                t += warped(c + 311, r + 711, 17, 2) * 2.5
                temp[i] = t
        self.temp = temp

    def step_moisture(self) -> None:
        """Влага: ветер несёт её с моря, горы её отжимают.

        За один проход делается два прохода по строке — туда и обратно:
        в тропиках и у полюсов ветер восточный, в средних широтах
        западный, и без обратного хода нутро материка остаётся сухим.
        """
        W, H, N = self.W, self.H, self.N
        warped, ridged = self.warped_sample, self.ridged
        elev, is_ocean, temp = self.elev, self.is_ocean, self.temp
        elev_to_m = self.elev_to_m
        wrap = self.wrap
        rainfall = self.rainfall
        moist = _f32(N)
        for i in range(N):
            moist[i] = 1.0 if is_ocean[i] else 0.0

        for step in range(5):
            po = step * 379.3
            for sweep in range(2):
                for r in range(1, H - 1):
                    row = r * W
                    lat_a = abs((r / (H - 1)) * 2 - 1)
                    for c0 in range(W):
                        c = W - 1 - c0 if sweep else c0
                        i = row + c
                        if is_ocean[i]:
                            moist[i] = 1
                            continue
                        w_lat = (lat_a
                                 + warped(c + po + 401, r + po + 99, 1.4, 3) * 0.38
                                 + warped(c + po + 88, r + po + 55, 4.5, 2) * 0.14)
                        direction = -1 if w_lat < 0.28 else (1 if w_lat < 0.62 else -1)
                        if wrap:
                            sc = (c - direction + W) % W
                        else:
                            sc = max(0, min(W - 1, c - direction))
                        merid = 1 if warped(c + po + 701, r + po + 303, 2.2, 2) > 0 else -1
                        r_m = max(0, min(H - 1, r + merid))
                        up_w = (moist[row + sc] + moist[r_m * W + c] * 0.38) / 1.38
                        rise = max(0.0, elev[i] - max(elev[row + sc],
                                                      elev[r_m * W + c]))
                        conv = (max(0.0, warped(c + po + 150, r + po + 777, 6, 3))
                                * (0.18 + max(0.0, min(28.0, temp[i])) * 0.004))
                        mm = (up_w * 0.952 - rise * 1.55 + conv) * rainfall
                        mm = max(0.0, min(1.0, mm))
                        if mm > moist[i]:
                            moist[i] = mm

        hum_bias = (self.k["humidity"] - 50) / 50.0
        continental = self.continental
        for i in range(N):
            if is_ocean[i]:
                continue
            c, r = i % W, i // W
            province = (warped(c + 970, r + 1330, 0.9, 4) * 0.85
                        + warped(c + 213, r + 876, 4.0, 3) * 0.26
                        + warped(c + 512, r + 221, 11.0, 2) * 0.15)
            mm = moist[i] * (1 - 0.52 * continental[i])
            mm = mm * (0.76 + 0.46 * (province * 0.5 + 0.5))
            lat_z = abs(((r / (H - 1)) * 2 - 1)
                        + warped(c + 777, r + 333, 1.1, 3) * 0.3)
            mm += math.exp(-((lat_z / 0.13) ** 2)) * 0.15          # дожди равника
            mm -= math.exp(-(((lat_z - 0.35) / 0.14) ** 2)) * 0.18  # сухой пояс
            mm += hum_bias * 0.18
            mtr = max(0.0, elev_to_m(elev[i]))
            if mtr > 900:
                mm += (min(0.22, (mtr - 900) / 4200)
                       * (0.5 + 0.5 * max(0.0, province)))
            mm += max(0.0, ridged(c + 311, r + 177, 3.5, 3) - 0.55) * 0.5
            tt = temp[i]
            if tt < 0:
                capw = 0.08 if tt <= -22 else 0.08 + (tt + 22) / 22 * 0.30
                mm = min(mm, capw)
            moist[i] = max(0.0, min(1.0, mm))

        # Сглаживание по соседям — резкие границы климата не бывают.
        nb = self._nb
        tmp_m = moist[:]
        tmp_t = self.temp[:]
        temp = self.temp
        for i in range(N):
            if is_ocean[i]:
                continue
            sm = tmp_m[i]
            st = tmp_t[i]
            count = 1
            for j in nb[i]:
                sm += tmp_m[j]
                st += tmp_t[j]
                count += 1
            moist[i] = sm / count
            temp[i] = st / count
        self.moist = moist

    def step_seasons(self) -> None:
        """Лето и зима: чем дальше от моря и от равника, тем резче разница."""
        W, N = self.W, self.N
        H = self.H
        temp, continental, elev = self.temp, self.continental, self.elev
        elev_to_m = self.elev_to_m
        t_min, t_max = _f32(N), _f32(N)
        for i in range(N):
            r = i // W
            lat = abs((r / (H - 1)) * 2 - 1)
            meters = max(0.0, elev_to_m(elev[i]))
            amp = (lat * lat * 28 * (0.5 + continental[i] * 0.85)
                   + meters / 520)
            t_max[i] = temp[i] + amp / 2
            t_min[i] = temp[i] - amp / 2
        self.temp_min, self.temp_max = t_min, t_max

        # Для выбора биома влажность берётся размытой: иначе биомы
        # рассыпаются в крап по каждому пятнышку шума.
        moist_b = self.moist[:]
        nb = self._nb
        is_ocean = self.is_ocean
        for _ in range(3):
            tmp = moist_b[:]
            for i in range(N):
                if is_ocean[i]:
                    continue
                sm = tmp[i] * 2
                count = 2
                for j in nb[i]:
                    sm += tmp[j]
                    count += 1
                moist_b[i] = sm / count
        self.moist_b = moist_b

    # ------------------------------------------------------------------
    # 7. Озёра и реки
    # ------------------------------------------------------------------

    def step_water(self) -> None:
        """Впадины заливаются, вода находит путь к морю, реки растут.

        Сначала приоритетным заполнением считается уровень, до которого
        поднялась бы вода в каждой впадине: где она стоит выше земли —
        там озеро. Потом каждый гекс отдаёт воду самому низкому соседу,
        и по накопленному стоку проводятся реки. Порядок Штралера
        считается сверху вниз: два потока одного порядка дают поток
        следующего.
        """
        W, H, N = self.W, self.H, self.N
        elev, is_ocean, moist = self.elev, self.is_ocean, self.moist
        nb = self._nb
        filled = _f32(N)
        vis = _u8(N)
        hv, hi = [], []

        def hpush(value, index):
            hv.append(value)
            hi.append(index)
            n = len(hv) - 1
            while n > 0:
                p = (n - 1) >> 1
                if hv[p] <= hv[n]:
                    break
                hv[p], hv[n] = hv[n], hv[p]
                hi[p], hi[n] = hi[n], hi[p]
                n = p

        def hpop():
            value, index = hv[0], hi[0]
            last = len(hv) - 1
            hv[0], hi[0] = hv[last], hi[last]
            hv.pop()
            hi.pop()
            n, length = 0, len(hv)
            while True:
                s, a, b = n, 2 * n + 1, 2 * n + 2
                if a < length and hv[a] < hv[s]:
                    s = a
                if b < length and hv[b] < hv[s]:
                    s = b
                if s == n:
                    break
                hv[s], hv[n] = hv[n], hv[s]
                hi[s], hi[n] = hi[n], hi[s]
                n = s
            return value, index

        drain_to = _i32(N, -1)
        for r in range(H):
            row = r * W
            for c in range(W):
                i = row + c
                if is_ocean[i] or r == 0 or r == H - 1:
                    filled[i] = elev[i]
                    vis[i] = 1
                    hpush(elev[i], i)
        while hv:
            e, i = hpop()
            for j in nb[i]:
                if vis[j]:
                    continue
                ne = max(elev[j], e)
                filled[j] = ne
                vis[j] = 1
                drain_to[j] = i
                hpush(ne, j)

        is_lake = _u8(N)
        lt = 0.012 * (1.4 - self.lake_d)
        for i in range(N):
            if not is_ocean[i] and filled[i] - elev[i] > lt:
                is_lake[i] = 1

        flowto = _i32(N, -1)
        for i in range(N):
            if is_ocean[i]:
                continue
            best, be = -1, filled[i]
            for j in nb[i]:
                if filled[j] < be:
                    be = filled[j]
                    best = j
            if best < 0:
                best = drain_to[i]
            flowto[i] = best

        order = sorted(range(N), key=lambda i: -filled[i])
        accum = _f32(N)
        for i in range(N):
            accum[i] = 0.0 if is_ocean[i] else (0.15 + moist[i] * 1.1)
        for i in order:
            t = flowto[i]
            if t >= 0 and not is_ocean[t]:
                accum[t] = accum[t] + accum[i]
        max_a = 1.0
        for i in range(N):
            if accum[i] > max_a:
                max_a = accum[i]

        is_river = _u8(N)
        rt = max_a * (0.17 - self.river_d * 0.155) + 6
        for i in range(N):
            if not is_ocean[i] and not is_lake[i] and accum[i] > rt:
                is_river[i] = 1
        for i in range(N):
            if not is_river[i]:
                continue
            j = flowto[i]
            guard = 0
            while j >= 0 and not is_ocean[j] and not is_lake[j] and guard < 8000:
                guard += 1
                is_river[j] = 1
                j = flowto[j]

        river_order = _u8(N)
        for i in order:
            if not is_river[i]:
                continue
            if river_order[i] == 0:
                river_order[i] = 1
            t = flowto[i]
            if t >= 0 and is_river[t]:
                o = river_order[i]
                if river_order[t] == 0:
                    river_order[t] = o
                elif river_order[t] == o:
                    river_order[t] = min(7, o + 1)
                else:
                    river_order[t] = max(river_order[t], o)

        self.filled, self.is_lake, self.flowto = filled, is_lake, flowto
        self.accum, self.is_river, self.river_order = accum, is_river, river_order
        self.max_a, self.rt = max_a, rt
        self._deltas()

    def _deltas(self) -> None:
        """Большая река в устье распадается на рукава."""
        W, N = self.W, self.N
        rng = self.rng
        elev, is_ocean, is_lake = self.elev, self.is_ocean, self.is_lake
        is_river, river_order, flowto = (self.is_river, self.river_order,
                                         self.flowto)
        accum, nb = self.accum, self._nb
        max_a, river_d = self.max_a, self.river_d
        forks = []

        mouths = []
        for i in range(N):
            if (is_river[i] and flowto[i] >= 0 and is_ocean[flowto[i]]
                    and (river_order[i] >= 2 or accum[i] > max_a * 0.08)):
                mouths.append(i)
        mouths.sort(key=lambda i: -accum[i])
        want = _round(1 + river_d * 9)
        taken = []
        made = 0
        for m in mouths:
            if made >= want:
                break
            mc, mr = m % W, m // W
            near = False
            for px, py in taken:
                dx = self.wdx(mc, px)
                dy = mr - py
                if dx * dx + dy * dy < 110:
                    near = True
                    break
            if near:
                continue
            if rng() > 0.30 + river_d * 0.65:
                continue
            f = m
            back = 2 + int(rng() * 3)
            for _ in range(back):
                best, ba = -1, -1.0
                for j in nb[f]:
                    if is_river[j] and flowto[j] == f and accum[j] > ba:
                        ba = accum[j]
                        best = j
                if best < 0:
                    break
                f = best
            n_ch = 1 + min(2, int(rng() * (0.8 + river_d * 2.4)))
            ord_here = max(2, river_order[m])
            carved = False
            for _ch in range(n_ch):
                path = []
                cur = f
                guard = 0
                reached = False
                while guard < 9:
                    guard += 1
                    best, bs, sea = -1, 1e9, -1
                    for j in nb[cur]:
                        if is_ocean[j]:
                            sea = j
                            continue
                        if is_river[j] or is_lake[j] or j in path:
                            continue
                        if elev[j] > elev[f] + 0.012:
                            continue
                        sc2 = elev[j] + rng() * 0.006
                        if sc2 < bs:
                            bs = sc2
                            best = j
                    if sea >= 0 and (best < 0 or (len(path) >= 2 and rng() < 0.6)):
                        path.append(sea)
                        reached = True
                        break
                    if best < 0:
                        break
                    path.append(best)
                    cur = best
                if not reached or len(path) < 2:
                    continue
                forks.append((f, path[0]))
                for s in range(len(path) - 1):
                    a = path[s]
                    if is_ocean[a]:
                        break
                    is_river[a] = 1
                    river_order[a] = max(river_order[a], ord_here)
                    flowto[a] = path[s + 1]
                carved = True
            if carved:
                made += 1
                taken.append((mc, mr))
        self.delta_forks = forks

    # ------------------------------------------------------------------
    # 8. Биомы
    # ------------------------------------------------------------------

    def _ocean_biome(self, e: float, t: float) -> int:
        d = -self.elev_to_m(e)
        if t < -1.7:
            return 0                      # морской лёд
        if d < 70:
            if 21 <= t < 33:
                return 1                  # коралловый риф
            if t <= 12:
                return 2                  # ламинариевый лес
            return 3
        if d < 200:
            return 4
        if d < 1000:
            return 5
        if d < 3000:
            return 6
        if d < 6000:
            return 7
        return 8

    def _land_biome(self, t: float, m: float, el: float, lat: float) -> int:
        """Биом по температуре и осадкам — с поправкой на испарение.

        Жара не только греет, но и сушит: чем теплее, тем больше дождя
        нужно тому же лесу. Выше сорока четырёх градусов средней за год
        не растёт уже ничего — выжженная пустошь.
        """
        meters = max(0.0, self.elev_to_m(el))
        p = (m ** 1.15) * 3000 + 40
        if t >= 19:
            sez = math.exp(-(((abs(lat) - 0.27) / 0.16) ** 2))
            p *= 1 - 0.38 * sez
        p = max(0.0, p - max(0.0, t - 27) * 34)
        if t > 44:
            return 34
        snow = 4900 - abs(lat) * 3600
        if meters > snow and t < 3:
            return 11
        if meters > snow - 650 and t < 6:
            return 16
        if meters > 2900 and 0 < t < 8:
            return 15
        if 1500 < meters < 2900 and 12 <= t < 22 and p > 1700:
            return 37
        if t < -13:
            return 11 if p > 230 else (12 if p < 100 else 13)
        if t < -7:
            return 12 if p < 110 else 13
        if t < 0:
            if p < 110:
                return 18
            return 35 if (t > -2.5 and p > 340) else 14
        if t < 7:
            if p < 110:
                return 18
            if p < 380:
                return 19
            return 35 if t < 1.5 else 17
        if t < 15:
            if p < 115:
                return 18
            if p < 380:
                return 19
            if p < 560:
                return 36
            return 20 if p < 1100 else 21
        if t < 22:
            if p < 150:
                return 23
            if p < 420:
                return 22
            return 20 if p < 1050 else 21
        if p < 150:
            return 23
        if p < 700:
            return 24
        if p < 1000:
            return 25
        if p < 1500:
            return 26
        if p < 2300:
            return 27
        return 28

    def step_biomes(self) -> None:
        """Биом каждого гекса и поправки на воду, дренаж и реки."""
        W, H, N = self.W, self.H, self.N
        elev, temp, moist_b = self.elev, self.temp, self.moist_b
        is_ocean, is_lake, is_river = self.is_ocean, self.is_lake, self.is_river
        river_order, filled, accum = self.river_order, self.filled, self.accum
        continental, nb = self.continental, self._nb
        warped = self.warped_sample
        elev_to_m = self.elev_to_m
        rt = self.rt
        biome = _u8(N)
        for i in range(N):
            if is_ocean[i]:
                biome[i] = self._ocean_biome(elev[i], temp[i])
                continue
            if is_lake[i]:
                lc, lr = i % W, i // W
                salty = (moist_b[i] < 0.17 and temp[i] > 6
                         and warped(lc + 1444, lr + 888, 5, 3) > -0.2)
                biome[i] = 30 if salty else 9
                continue
            c, r = i % W, i // W
            lat = (r / (H - 1)) * 2 - 1
            b = self._land_biome(temp[i], moist_b[i], elev[i], lat)
            meters = elev_to_m(elev[i])
            t = temp[i]
            nbs = nb[i]
            sl = 0.0
            lake_n = riv_n = ocean_n = False
            for j in nbs:
                sl += abs(elev[j] - elev[i])
                if is_lake[j]:
                    lake_n = True
                if is_river[j]:
                    riv_n = True
                if is_ocean[j]:
                    ocean_n = True
            sl /= len(nbs)
            dep = filled[i] - elev[i]
            bog = warped(c + 1444, r + 888, 5, 3)

            # Болота стоят там, где воде некуда деться, а не просто там,
            # где сыро; в холоде то же место становится торфяником.
            if t > -1 and meters < 420 and b not in (11, 16, 15, 34):
                wet = moist_b[i]
                if ((dep > 0.0010 and wet > 0.34 and bog > -0.08)
                        or (sl < 0.011 and wet > 0.47
                            and accum[i] > rt * 0.20 and bog > 0.16)
                        or ((lake_n or riv_n) and sl < 0.009 and wet > 0.52
                            and bog > 0.40)):
                    b = 38 if t < 8.5 else 10
            # Солончак: бессточная впадина в сухом краю.
            if t > 0 and moist_b[i] < 0.30 and b not in (38, 10):
                if ((dep > 0.0008 and bog > 0.05)
                        or (lake_n and moist_b[i] < 0.22 and bog > 0.25)):
                    b = 30
            if ((24 <= b <= 29) or b == 10) and t > 22 and meters < 60 and ocean_n:
                b = 29                              # мангры
            if b == 23:                             # узор жаркой пустыни
                dune = warped(c + 2222, r + 331, 2.6, 3)
                if sl < 0.012 and dune > 0.34:
                    b = 31                          # дюнный эрг
                elif meters > 1150 or sl > 0.05 or dune < -0.55:
                    b = 32                          # каменистая хамада
            if b in (23, 31, 32, 30, 18) and lake_n and t > 4 and bog > 0.05:
                b = 33                              # оазис
            # Река режет по пустыне зелёную ленту — пустыня перестаёт
            # быть однородной плитой.
            if b in (23, 18, 31, 32):
                on_riv = bool(is_river[i])
                big_nb = bool(is_river[i] and river_order[i] >= 2)
                if not big_nb:
                    for j in nbs:
                        if is_river[j] and river_order[j] >= 2:
                            big_nb = True
                            break
                if on_riv or big_nb:
                    b = 19 if b == 18 else (24 if t > 22 else 22)
                else:
                    for j in nbs:
                        if is_river[j]:
                            if b == 18:
                                b = 19
                            elif b in (23, 31, 32):
                                b = 33
                            break
            if (b in (20, 17, 36) and 4 <= t < 13 and continental[i] < 0.25
                    and 0.18 < moist_b[i] < 0.42 and bog < -0.18):
                b = 39                              # верещатник
            biome[i] = b
        self.biome = biome

    # ------------------------------------------------------------------
    # 9. Области, имена, пики и вулканы
    # ------------------------------------------------------------------

    def _flood(self, pred):
        """Связные области по условию — обходом в глубину."""
        W, N = self.W, self.N
        nb = self._nb
        seen = _u8(N)
        comps = []
        for s in range(N):
            if seen[s] or not pred(s):
                continue
            stack = [s]
            seen[s] = 1
            cells = []
            sx = sy = 0.0
            while stack:
                i = stack.pop()
                cells.append(i)
                c, r = i % W, i // W
                sx += c + (0.5 if r & 1 else 0)
                sy += r
                for j in nb[i]:
                    if not seen[j] and pred(j):
                        seen[j] = 1
                        stack.append(j)
            comps.append({"cells": cells, "cx": sx / len(cells),
                          "cy": sy / len(cells), "area": len(cells)})
        return comps

    def step_regions(self) -> None:
        """Океаны, моря, материки, острова, хребты и реки получают имена."""
        W, N = self.W, self.N
        is_ocean, is_lake, is_river = self.is_ocean, self.is_lake, self.is_river
        elev, accum, flowto = self.elev, self.accum, self.flowto
        elev_to_m = self.elev_to_m
        namer = make_namer(self.rng)
        land_reg, water_reg = _i32(N, -1), _i32(N, -1)
        range_reg, river_reg = _i32(N, -1), _i32(N, -1)
        features = []

        ocean_comps = sorted(self._flood(lambda s: is_ocean[s] == 1),
                             key=lambda cp: -cp["area"])
        for ci, cp in enumerate(ocean_comps):
            area = cp["area"]
            if area > N * 0.07:
                kind = "ocean"
            elif area > N * 0.008:
                kind = "sea"
            elif area > N * 0.0025:
                kind = "bay"
            else:
                continue
            fid = len(features)
            features.append({"id": fid, "type": kind, "name": namer(ci % 3),
                             "cx": cp["cx"], "cy": cp["cy"], "area": area})
            for i in cp["cells"]:
                water_reg[i] = fid

        for cp in self._flood(lambda s: is_lake[s] == 1):
            if cp["area"] < 6:
                continue
            kind = "inlandsea" if cp["area"] > N * 0.004 else "lake"
            fid = len(features)
            features.append({"id": fid, "type": kind, "name": namer(),
                             "cx": cp["cx"], "cy": cp["cy"],
                             "area": cp["area"]})
            for i in cp["cells"]:
                water_reg[i] = fid

        land_comps = sorted(
            self._flood(lambda s: is_ocean[s] == 0 and is_lake[s] == 0),
            key=lambda cp: -cp["area"])
        small_islands = []
        for ci, cp in enumerate(land_comps):
            area = cp["area"]
            if area > N * 0.04:
                kind = "continent"
            elif area > N * 0.004:
                kind = "bigisland"
            elif area > N * 0.0007:
                kind = "island"
            else:
                small_islands.append(cp)
                continue
            fid = len(features)
            features.append({"id": fid, "type": kind, "name": namer(ci % 3),
                             "cx": cp["cx"], "cy": cp["cy"], "area": area})
            for i in cp["cells"]:
                land_reg[i] = fid

        # Россыпь мелких островов рядом друг с другом — это архипелаг.
        used = [0] * len(small_islands)
        for a in range(len(small_islands)):
            if used[a]:
                continue
            cluster = [a]
            used[a] = 1
            for b in range(a + 1, len(small_islands)):
                if used[b]:
                    continue
                near = False
                for m in cluster:
                    dx = self.wdx(small_islands[m]["cx"], small_islands[b]["cx"])
                    dy = small_islands[m]["cy"] - small_islands[b]["cy"]
                    if dx * dx + dy * dy < (W * 0.09) ** 2:
                        near = True
                        break
                if near:
                    cluster.append(b)
                    used[b] = 1
            if len(cluster) >= 3:
                sx = sy = 0.0
                ar = 0
                fid = len(features)
                for m in cluster:
                    sx += small_islands[m]["cx"]
                    sy += small_islands[m]["cy"]
                    ar += small_islands[m]["area"]
                    for i in small_islands[m]["cells"]:
                        land_reg[i] = fid
                features.append({"id": fid, "type": "archipelago",
                                 "name": namer(), "cx": sx / len(cluster),
                                 "cy": sy / len(cluster), "area": ar})

        ranges = [cp for cp in self._flood(
            lambda s: not is_ocean[s] and elev_to_m(elev[s]) > 2200)
            if cp["area"] > max(8, N * 0.0009)]
        ranges = sorted(ranges, key=lambda cp: -cp["area"])[:12]
        for cp in ranges:
            fid = len(features)
            features.append({"id": fid, "type": "range", "name": namer(),
                             "cx": cp["cx"], "cy": cp["cy"],
                             "area": cp["area"]})
            for i in cp["cells"]:
                range_reg[i] = fid

        sources = [i for i in range(N) if is_river[i]]
        sources.sort(key=lambda i: -accum[i])
        named = 0
        vis_r = _u8(N)
        label_pts = []
        rmd = max(8.0, W * 0.07)
        want = min(16, _round(7 + self.river_d * 12))
        for s in sources:
            if named >= want:
                break
            if vis_r[s]:
                continue
            i = s
            cells = []
            guard = 0
            while (i >= 0 and not is_ocean[i] and is_river[i]
                   and not vis_r[i] and guard < 4000):
                guard += 1
                vis_r[i] = 1
                cells.append(i)
                i = flowto[i]
            if len(cells) < max(4, W * 0.022):
                continue
            mid = cells[len(cells) // 2]
            mc, mr = mid % W, mid // W
            clash = False
            for px, py in label_pts:
                dx = self.wdx(mc, px)
                dy = mr - py
                if dx * dx + dy * dy < rmd * rmd:
                    clash = True
                    break
            fid = len(features)
            item = {"id": fid, "type": "river", "name": namer(),
                    "cx": mc, "cy": mr, "area": len(cells)}
            if not clash:
                label_pts.append((mc, mr))
                named += 1
            else:
                item["nolabel"] = 1
            features.append(item)
            for cc in cells:
                river_reg[cc] = fid

        self.features = features
        self.land_reg, self.water_reg = land_reg, water_reg
        self.range_reg, self.river_reg = range_reg, river_reg

    def step_peaks(self) -> None:
        """Именные вершины и вулканы, а потом — близость к вулкану."""
        W, H, N = self.W, self.H, self.N
        elev, is_ocean, nb = self.elev, self.is_ocean, self._nb
        stress = self.stress
        elev_to_m = self.elev_to_m
        peaks = []
        want_peaks = int(self.k["peaks"])
        if want_peaks > 0:
            cand = []
            for r in range(1, H - 1):
                row = r * W
                for c in range(W):
                    i = row + c
                    if is_ocean[i]:
                        continue
                    top = True
                    for j in nb[i]:
                        if elev[j] > elev[i]:
                            top = False
                            break
                    if top:
                        cand.append(i)
            cand.sort(key=lambda i: -elev[i])
            md = max(6.0, W * 0.04)
            pn = make_namer(self.rng)
            for i in cand:
                if len(peaks) >= want_peaks:
                    break
                c, r = i % W, i // W
                ok = True
                for p in peaks:
                    dx = self.wdx(c, p["i"] % W)
                    dy = r - p["i"] // W
                    if dx * dx + dy * dy < md * md:
                        ok = False
                        break
                if ok:
                    peaks.append({"i": i, "name": "г. " + pn(),
                                  "m": _round(elev_to_m(elev[i]))})
        self.peaks = peaks

        volcanoes = []
        volc_n = _round((self.k["volcanoes"] / 100.0) * 32)
        if volc_n > 0:
            cand = []
            for r in range(1, H - 1):
                row = r * W
                for c in range(W):
                    i = row + c
                    if is_ocean[i]:
                        continue
                    m = elev_to_m(elev[i])
                    if m < 700:
                        continue
                    loc = True
                    for j in nb[i]:
                        if elev[j] > elev[i]:
                            loc = False
                            break
                    conv = stress[i]
                    score = ((2 if loc else 0) + (2.4 if conv > 0.4 else 0)
                             + (m / self.max_alt) * 2)
                    if score > 1.3:
                        cand.append({"i": i, "score": score, "conv": conv})
            cand.sort(key=lambda item: -item["score"])
            md = max(4.0, W * 0.022)
            vn = make_namer(self.rng)
            act = self.k["volcanoes"] / 100.0
            rng = self.rng
            for ci in self.cone_sites:
                if len(volcanoes) >= volc_n:
                    break
                c, r = ci % W, ci // W
                ok = True
                for v in volcanoes:
                    dx = self.wdx(c, v["i"] % W)
                    dy = r - v["i"] // W
                    if dx * dx + dy * dy < md * md:
                        ok = False
                        break
                if not ok:
                    continue
                roll = rng()
                if roll < 0.45 + act * 0.35:
                    status = "активный"
                elif roll < 0.78:
                    status = "спящий"
                else:
                    status = "потухший"
                volcanoes.append({"i": ci, "name": "влк. " + vn(),
                                  "status": status,
                                  "m": _round(elev_to_m(elev[ci])), "lone": 1})
            for cc in cand:
                if len(volcanoes) >= volc_n:
                    break
                c, r = cc["i"] % W, cc["i"] // W
                ok = True
                for v in volcanoes:
                    dx = self.wdx(c, v["i"] % W)
                    dy = r - v["i"] // W
                    if dx * dx + dy * dy < md * md:
                        ok = False
                        break
                if not ok:
                    continue
                roll = rng()
                if cc["conv"] > 0.55 and roll < 0.45 + act * 0.4:
                    status = "активный"
                elif roll < 0.4 + act * 0.25:
                    status = "спящий"
                else:
                    status = "потухший"
                volcanoes.append({"i": cc["i"], "name": "влк. " + vn(),
                                  "status": status,
                                  "m": _round(elev_to_m(elev[cc["i"]]))})
        self.volcanoes = volcanoes

        dist_v = _f32(N, 99)
        volc_status = _i8(N, -1)
        if volcanoes:
            queue = []
            for v in volcanoes:
                dist_v[v["i"]] = 0
                queue.append(v["i"])
                volc_status[v["i"]] = (2 if v["status"] == "активный"
                                       else 1 if v["status"] == "спящий" else 0)
            head = 0
            while head < len(queue):
                i = queue[head]
                head += 1
                nd = dist_v[i] + 1
                if nd > 13:
                    continue
                for j in nb[i]:
                    if nd < dist_v[j]:
                        dist_v[j] = nd
                        volc_status[j] = volc_status[i]
                        queue.append(j)
        self.dist_v, self.volc_status = dist_v, volc_status

    # ------------------------------------------------------------------
    # 10. Почва, вода под землёй, берега, магия и пригодность для жизни
    # ------------------------------------------------------------------

    def step_soil(self) -> None:
        """Плодородие, водоносность, тип берега, магическое поле, годность."""
        W, H, N = self.W, self.H, self.N
        elev, temp, moist = self.elev, self.temp, self.moist
        biome, is_ocean, is_lake = self.biome, self.is_ocean, self.is_lake
        is_river, filled, nb = self.is_river, self.filled, self._nb
        dist_v, volc_status = self.dist_v, self.volc_status
        elev_to_m = self.elev_to_m

        fertility = _f32(N)
        for i in range(N):
            if is_ocean[i] or is_lake[i]:
                fertility[i] = 0
                continue
            b = biome[i]
            f = FERTB.get(b, 0.0)
            t, m = temp[i], moist[i]
            meters = max(0.0, elev_to_m(elev[i]))
            tropical = (24 <= b <= 29) or b == 33
            if not tropical:
                f *= 0.45 + 0.55 * math.exp(-(((t - 14) / 14) ** 2))
            if b in (19, 20, 36):
                m_opt = 0.55
            elif b in (23, 18) or 30 <= b <= 33:
                m_opt = 0.15
            else:
                m_opt = 0.62
            f *= 0.5 + 0.5 * math.exp(-(((m - m_opt) / 0.34) ** 2))
            sl = 0.0
            for j in nb[i]:
                sl += abs(elev[j] - elev[i])
            sl /= 6
            f *= max(0.3, 1 - sl * 14)
            f *= max(0.25, 1 - meters / 5000)
            if sl < 0.015:
                for j in nb[i]:
                    if is_river[j]:
                        f = min(1.0, f + 0.20)
                        break
            if dist_v[i] < 11:
                f = min(1.0, f + (1 - dist_v[i] / 11) * 0.40)
            fertility[i] = max(0.0, min(1.0, f))
        self.fertility = fertility

        groundwater = _f32(N)
        for i in range(N):
            if is_ocean[i]:
                groundwater[i] = 1
                continue
            meters = max(0.0, elev_to_m(elev[i]))
            g = moist[i] * 0.5 + (1 - min(1.0, meters / 2500)) * 0.3
            for j in nb[i]:
                if is_river[j] or is_lake[j]:
                    g += 0.25
            if filled[i] - elev[i] > 0:
                g += 0.2
            groundwater[i] = max(0.0, min(1.0, g))
        self.groundwater = groundwater

        # Тип берега: 0 нет, 1 скалы, 2 пляж, 3 дельта, 4 фьорд.
        coast_type = _u8(N)
        for i in range(N):
            if is_ocean[i] or is_lake[i]:
                continue
            ocean_nb = False
            for j in nb[i]:
                if is_ocean[j]:
                    ocean_nb = True
            if not ocean_nb:
                continue
            meters = elev_to_m(elev[i])
            sl = 0.0
            for j in nb[i]:
                sl += abs(elev[j] - elev[i])
            sl /= 6
            river_mouth = False
            for j in nb[i]:
                if is_river[j]:
                    river_mouth = True
            if is_river[i] or river_mouth:
                coast_type[i] = 3
            elif meters > 600 and sl > 0.05:
                coast_type[i] = 4
            elif sl > 0.045:
                coast_type[i] = 1
            else:
                coast_type[i] = 2
        self.coast_type = coast_type

        # Магия: узлы, каждый светлый или тёмный; поле — сумма их сияний.
        magic = _f32(N)
        mag_nodes = []
        magic_amt = self.magic_amt
        rng = self.rng
        if magic_amt > 0:
            count = _round(3 + magic_amt * 22)
            for _ in range(count):
                x = rng() * W
                y = rng() * H
                rad = (0.04 + rng() * 0.12) * H * (0.6 + magic_amt * 0.8)
                a = self.align_bias * 0.6 + (rng() * 2 - 1) * 0.8
                sign = 1 if a >= 0 else -1
                strength = 0.4 + rng() * 0.6
                mag_nodes.append({"x": x, "y": y, "rad": rad, "sign": sign,
                                  "strength": strength})
            warped = self.warped_sample
            align_bias = self.align_bias
            for r in range(H):
                row = r * W
                for c in range(W):
                    i = row + c
                    v = 0.0
                    for nd in mag_nodes:
                        dx = self.wdx(c, nd["x"])
                        dy = r - nd["y"]
                        d = math.sqrt(dx * dx + dy * dy) / nd["rad"]
                        if d < 1.6:
                            v += (nd["sign"] * nd["strength"]
                                  * math.exp(-d * d * 1.4))
                    v += warped(c + 333, r + 1212, 2.0, 3) * magic_amt * 0.20
                    v += align_bias * magic_amt * 0.12
                    mv = v * magic_amt
                    mv = _sign(mv) * (min(1.0, abs(mv)) ** 1.9)
                    magic[i] = max(-1.0, min(1.0, mv))
        self.magic = magic
        self.mag_nodes = mag_nodes

        # Годность под поселение: почва, вода, ровная земля, климат.
        settle = _f32(N)
        for i in range(N):
            if is_ocean[i] or is_lake[i]:
                settle[i] = 0
                continue
            meters = max(0.0, elev_to_m(elev[i]))
            t = temp[i]
            s = fertility[i] * 0.40
            sl = 0.0
            for j in nb[i]:
                sl += abs(elev[j] - elev[i])
            sl /= 6
            s += max(0.0, 1 - sl * 16) * 0.12
            river = lake_n = ocean_n = False
            for j in nb[i]:
                if is_river[j]:
                    river = True
                if is_lake[j]:
                    lake_n = True
                if is_ocean[j]:
                    ocean_n = True
            if river:
                s += 0.18
            if lake_n:
                s += 0.06
            if ocean_n:
                s += 0.14
            s += groundwater[i] * 0.08
            s *= 0.45 + 0.55 * math.exp(-(((t - 16) / 16) ** 2))
            s *= max(0.25, 1 - meters / 4000)
            if dist_v[i] < 3 and volc_status[i] == 2:
                s *= 0.6
            s *= (1 - 0.25 * max(0.0, -magic[i]))
            s += max(0.0, magic[i]) * 0.05
            settle[i] = max(0.0, min(1.0, s))
        self.settle = settle

    # ------------------------------------------------------------------
    # Сборка
    # ------------------------------------------------------------------

    def run(self) -> ForgedWorld:
        self.say(0.02, "ядра континентов")
        self.step_continents()
        self.say(0.12, "плиты")
        self.step_plates()
        self.say(0.22, "высоты")
        self.step_elevation()
        self.say(0.38, "эрозия")
        self.step_erosion()
        self.step_cones()
        self.say(0.44, "уровень моря")
        self.step_sea()
        self.say(0.48, "течения")
        self.step_currents()
        self.say(0.54, "температура")
        self.step_temperature()
        self.say(0.62, "влага и ветры")
        self.step_moisture()
        self.step_seasons()
        self.say(0.80, "реки и озёра")
        self.step_water()
        self.say(0.86, "биомы")
        self.step_biomes()
        self.say(0.92, "земли и названия")
        self.step_regions()
        self.step_peaks()
        self.say(0.97, "почва и магия")
        self.step_soil()

        world = ForgedWorld()
        world.W, world.H = self.W, self.H
        world.wrap = self.wrap
        world.sea = self.sea
        world.cfg = self.cfg
        world._nb = self._nb
        land = 0
        for i in range(self.N):
            if not self.is_ocean[i]:
                land += 1
        world.land_frac = land / float(self.N)
        for name in ("elev", "temp", "moist", "moist_b", "temp_min", "temp_max",
                     "biome", "is_ocean", "is_lake", "is_river", "river_order",
                     "accum", "flowto", "filled", "stress", "plate_of",
                     "fertility", "dist_v", "volc_status", "continental",
                     "cur_anom", "cur_vx", "cur_vy", "groundwater",
                     "coast_type", "magic", "settle", "land_reg", "water_reg",
                     "range_reg", "river_reg", "cont"):
            setattr(world, name, getattr(self, name))
        world.peaks = self.peaks
        world.volcanoes = self.volcanoes
        world.features = self.features
        world.mag_nodes = self.mag_nodes
        world.delta_forks = self.delta_forks
        world.seeds = self.seeds
        return world


def generate(cfg: Config, progress=None) -> ForgedWorld:
    """Собрать мир по настройкам. Один сид — один и тот же мир."""
    import time
    began = time.time()
    world = _Forge(cfg, progress).run()
    world.seconds = time.time() - began
    return world
