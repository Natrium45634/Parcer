# -*- coding: utf-8 -*-
"""Детерминированный генератор псевдослучайных чисел.

Используется собственный SplitMix64, а не стандартный ``random``: так
результат генерации гарантированно одинаков на любой версии Python и на
любой операционной системе. Один и тот же сид всегда даёт один и тот же мир.

Ключевая идея — «потоки» (substreams). Вместо одного общего генератора
движок создаёт отдельные потоки для каждой подсистемы и каждого года:

    rng = hub.stream("founding", year)

Благодаря этому добавление новой подсистемы в будущем не «сдвигает»
случайные числа у всех остальных, и старые сиды продолжают работать
предсказуемо.
"""

from __future__ import annotations

import hashlib

MASK64 = (1 << 64) - 1
GOLDEN = 0x9E3779B97F4A7C15


def seed_to_int(seed) -> int:
    """Превращает любой сид (строку, число) в 64-битное целое."""
    if isinstance(seed, int):
        value = seed & MASK64
        if value:
            return value
        return GOLDEN
    text = str(seed)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value or GOLDEN


def mix_seed(seed: int, parts) -> int:
    """Смешивает базовый сид с меткой потока."""
    label = "|".join(str(p) for p in parts)
    payload = seed.to_bytes(8, "big") + label.encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    value = int.from_bytes(digest[:8], "big")
    return value or GOLDEN


class Rng:
    """SplitMix64 с удобными методами."""

    __slots__ = ("_seed", "_state")

    def __init__(self, seed=0):
        self._seed = seed_to_int(seed)
        self._state = self._seed

    # --- базовые источники ---------------------------------------------

    def next_u64(self) -> int:
        self._state = (self._state + GOLDEN) & MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return (z ^ (z >> 31)) & MASK64

    def random(self) -> float:
        """Вещественное число в [0, 1)."""
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    # --- производные ----------------------------------------------------

    def randint(self, low: int, high: int) -> int:
        """Целое из диапазона [low, high] включительно."""
        if high <= low:
            return low
        return low + int(self.next_u64() % (high - low + 1))

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.random()

    def chance(self, probability: float) -> bool:
        if probability <= 0.0:
            return False
        if probability >= 1.0:
            return True
        return self.random() < probability

    def choice(self, seq):
        seq = list(seq) if not isinstance(seq, (list, tuple)) else seq
        if not seq:
            raise ValueError("Rng.choice: пустая последовательность")
        return seq[int(self.next_u64() % len(seq))]

    def weighted(self, pairs):
        """Выбор из списка пар (значение, вес)."""
        pairs = [(item, float(weight)) for item, weight in pairs if weight > 0]
        if not pairs:
            raise ValueError("Rng.weighted: нет вариантов с положительным весом")
        total = sum(weight for _, weight in pairs)
        roll = self.random() * total
        upto = 0.0
        for item, weight in pairs:
            upto += weight
            if roll < upto:
                return item
        return pairs[-1][0]

    def shuffled(self, seq) -> list:
        items = list(seq)
        for i in range(len(items) - 1, 0, -1):
            j = int(self.next_u64() % (i + 1))
            items[i], items[j] = items[j], items[i]
        return items

    def sample(self, seq, count: int) -> list:
        items = list(seq)
        if count >= len(items):
            return self.shuffled(items)
        return self.shuffled(items)[:count]

    def bell(self, low: float, high: float) -> float:
        """Треугольное распределение: значения ближе к середине вероятнее."""
        return low + (high - low) * (self.random() + self.random()) * 0.5

    def jitter(self, value: float, spread: float) -> float:
        """Значение ± spread (в долях), распределение колоколом."""
        return value * (1.0 + self.bell(-spread, spread))

    # --- потоки ---------------------------------------------------------

    def spawn(self, *parts) -> "Rng":
        """Новый независимый генератор, детерминированно выведенный из этого."""
        child = Rng.__new__(Rng)
        child._seed = mix_seed(self._seed, parts)
        child._state = child._seed
        return child

    @property
    def seed(self) -> int:
        return self._seed


class RngHub:
    """Фабрика именованных потоков от одного корневого сида."""

    __slots__ = ("root_seed", "root_label")

    def __init__(self, seed):
        self.root_label = str(seed)
        self.root_seed = seed_to_int(seed)

    def stream(self, *parts) -> Rng:
        rng = Rng.__new__(Rng)
        rng._seed = mix_seed(self.root_seed, parts)
        rng._state = rng._seed
        return rng


# ---------------------------------------------------------------------------
# Сиды: коды, которые не жалко диктовать вслух
# ---------------------------------------------------------------------------
#
# Сид — это имя мира, и его переписывают от руки, диктуют и вставляют в
# письма. Поэтому код собран из букв и цифр, которые нельзя перепутать:
# ни нуля рядом с «O», ни единицы рядом с «I», ни пятёрки рядом с «S».
# Пишется он двумя четвёрками через дефис — «KR7M-93XD»: так и читается
# легче, и на слух разбирается.

# В коде нет букв, которые путают с цифрами: вместо «O» пишется ноль,
# вместо «I» — единица, а «B», «S», «Z» и «Q» не встречаются вовсе.
SEED_LETTERS = "ACDEFGHJKLMNPRTUVWXY"      # без B, I, O, Q, S, Z
SEED_DIGITS = "0123456789"
SEED_ALPHABET = SEED_LETTERS + SEED_DIGITS
SEED_GROUP = 4
SEED_GROUPS = 2
SEED_LENGTH = SEED_GROUP * SEED_GROUPS

# Что во что превращается, если сид набрали как услышали или как увидели:
# спорные латинские буквы и кириллица, неотличимая от латиницы на вид.
SEED_FIXES = {
    "B": "8", "I": "1", "O": "0", "Q": "0", "S": "5", "Z": "2",
    "А": "A", "В": "8", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "0",
    "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X", "Ё": "E",
    "І": "1", "Ѕ": "5", "Ј": "J",
}


def make_seed_text(raw: int) -> str:
    """Собирает код сида из 64-битного числа."""
    letters = []
    value = raw
    for _ in range(SEED_LENGTH):
        letters.append(SEED_ALPHABET[value % len(SEED_ALPHABET)])
        value //= len(SEED_ALPHABET)
    # В каждой четвёрке должна быть и буква, и цифра: иначе код читается
    # то как слово, то как число, и глазу не за что зацепиться.
    for group in range(SEED_GROUPS):
        start = group * SEED_GROUP
        chunk = letters[start:start + SEED_GROUP]
        if not any(item in SEED_DIGITS for item in chunk):
            letters[start + (raw >> group) % SEED_GROUP] = \
                SEED_DIGITS[(raw >> (group * 3)) % len(SEED_DIGITS)]
        elif not any(item in SEED_LETTERS for item in chunk):
            letters[start + (raw >> group) % SEED_GROUP] = \
                SEED_LETTERS[(raw >> (group * 5)) % len(SEED_LETTERS)]
    return "-".join("".join(letters[i:i + SEED_GROUP])
                    for i in range(0, SEED_LENGTH, SEED_GROUP))


def normalize_seed(text) -> str:
    """Приводит набранный код к единому виду — и только код.

    «kr7m93xd», «KR7M-93XD» и «КR7М 93ХD» набранное вперемешку с
    кириллицей — это один и тот же мир. А вот «Начало», «карта-1» и
    любое другое слово остаются как есть: их никто не диктует по буквам,
    и трогать их — значит ломать старые сиды.
    """
    raw = str(text).strip()
    if not raw:
        return "Начало"          # пустое поле — мир по умолчанию
    body = []
    for letter in raw.upper():
        if letter in " -_.":
            continue
        body.append(SEED_FIXES.get(letter, letter))
    code = "".join(body)
    if len(code) != SEED_LENGTH:
        return raw
    if any(letter not in SEED_ALPHABET for letter in code):
        return raw
    return "-".join(code[i:i + SEED_GROUP]
                    for i in range(0, SEED_LENGTH, SEED_GROUP))


def random_seed_text() -> str:
    """Случайный сид для кнопки «перемешать».

    Единственное недетерминированное место во всём движке.
    """
    import os

    return make_seed_text(int.from_bytes(os.urandom(8), "big"))
