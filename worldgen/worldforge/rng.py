# -*- coding: utf-8 -*-
"""Случайность и шум Worldforge — тот же счёт, что в исходном генераторе.

Здесь нарочно повторена арифметика JavaScript: xmur3 и mulberry32 считают
в 32 битах, а шум Перлина — в обычных числах двойной точности. Python и JS
считают такие числа одинаково, поэтому карта, собранная этим кодом, выходит
той же, что у исходного генератора.

Правило простое: всё, что в JS было побитовым (^, <<, >>>, Math.imul),
здесь считается по 32-битной маске; всё остальное — обычные числа.
"""

from __future__ import annotations

import math

MASK32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """Math.imul: умножение 32×32 с отбрасыванием старших битов."""
    return (a * b) & MASK32


def _signed(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value >= 0x80000000 else value


def xmur3(text: str):
    """Хэш строки в поток 32-битных чисел — из него растёт сид."""
    h = (1779033703 ^ len(text)) & MASK32
    for char in text:
        h = _imul(h ^ (ord(char) & 0xFFFF), 3432918353)
        h = (((h << 13) & MASK32) | (h >> 19)) & MASK32

    state = [h]

    def step() -> int:
        value = state[0]
        value = _imul(value ^ (value >> 16), 2246822507)
        value = _imul(value ^ (value >> 13), 3266489909)
        value = (value ^ (value >> 16)) & MASK32
        state[0] = value
        return value

    return step


class Rng:
    """mulberry32: то же число из того же состояния, что и в исходнике."""

    __slots__ = ("a",)

    def __init__(self, seed: int):
        self.a = seed & MASK32

    def __call__(self) -> float:
        a = (self.a + 0x6D2B79F5) & MASK32
        self.a = a
        t = _imul(a ^ (a >> 15), (1 | a) & MASK32)
        inner = _imul(t ^ (t >> 7), (61 | t) & MASK32)
        t = ((_signed(t) + _signed(inner)) ^ _signed(t)) % 0x100000000
        return ((t ^ (t >> 14)) & MASK32) / 4294967296.0


def rng_from(seed) -> "Rng":
    """Сид из строки — ровно как rngFrom в исходнике."""
    return Rng(xmur3(str(seed))())


# ---------------------------------------------------------------------------
# Шум Перлина
# ---------------------------------------------------------------------------

_GRAD = (
    (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
    (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
    (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1),
)


def make_noise(rng):
    """Шум Перлина с перестановкой, засеянной этим же ГСЧ."""
    table = list(range(256))
    for i in range(255, 0, -1):
        j = int(rng() * (i + 1))
        table[i], table[j] = table[j], table[i]
    perm = [table[i & 255] for i in range(512)]

    def noise(x: float, y: float, z: float) -> float:
        # Всё расписано в одну строку без вложенных функций: шум зовут
        # миллионы раз, и каждый лишний вызов стоит минуты на большой карте.
        fx = math.floor(x)
        fy = math.floor(y)
        fz = math.floor(z)
        xi = int(fx) & 255
        yi = int(fy) & 255
        zi = int(fz) & 255
        x -= fx
        y -= fy
        z -= fz
        u = x * x * x * (x * (x * 6 - 15) + 10)
        v = y * y * y * (y * (y * 6 - 15) + 10)
        w = z * z * z * (z * (z * 6 - 15) + 10)
        a = perm[xi] + yi
        aa = perm[a] + zi
        ab = perm[a + 1] + zi
        b = perm[xi + 1] + yi
        ba = perm[b] + zi
        bb = perm[b + 1] + zi
        x1 = x - 1
        y1 = y - 1
        z1 = z - 1
        g = _GRAD
        q = g[perm[aa] % 12]
        n1 = q[0] * x + q[1] * y + q[2] * z
        q = g[perm[ba] % 12]
        n2 = q[0] * x1 + q[1] * y + q[2] * z
        q = g[perm[ab] % 12]
        n3 = q[0] * x + q[1] * y1 + q[2] * z
        q = g[perm[bb] % 12]
        n4 = q[0] * x1 + q[1] * y1 + q[2] * z
        q = g[perm[aa + 1] % 12]
        n5 = q[0] * x + q[1] * y + q[2] * z1
        q = g[perm[ba + 1] % 12]
        n6 = q[0] * x1 + q[1] * y + q[2] * z1
        q = g[perm[ab + 1] % 12]
        n7 = q[0] * x + q[1] * y1 + q[2] * z1
        q = g[perm[bb + 1] % 12]
        n8 = q[0] * x1 + q[1] * y1 + q[2] * z1
        la = n1 + u * (n2 - n1)
        lb = n3 + u * (n4 - n3)
        lc = n5 + u * (n6 - n5)
        ld = n7 + u * (n8 - n7)
        ma = la + v * (lb - la)
        mb = lc + v * (ld - lc)
        return ma + w * (mb - ma)

    return noise
