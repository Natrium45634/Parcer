# -*- coding: utf-8 -*-
"""Календарь мира: 12 месяцев по 30 дней, год = 360 дней."""

from __future__ import annotations

MONTHS_IN_YEAR = 12
DAYS_IN_MONTH = 30
DAYS_IN_YEAR = MONTHS_IN_YEAR * DAYS_IN_MONTH

# Внутримировые названия месяцев.
MONTH_NAMES = (
    "Хладень",      # 1
    "Ледолом",      # 2
    "Первоцвет",    # 3
    "Травень",      # 4
    "Светлень",     # 5
    "Зарник",       # 6
    "Златень",      # 7
    "Жнивень",      # 8
    "Листопад",     # 9
    "Туманник",     # 10
    "Стылень",      # 11
    "Долгоночь",    # 12
)

SEASONS = (
    "зима", "зима", "весна", "весна", "весна", "лето",
    "лето", "лето", "осень", "осень", "осень", "зима",
)


def day_ordinal(name: int) -> str:
    """Порядковое числительное для дня: 1 -> «1-й»."""
    return "%d-й" % name


class Date:
    """Дата мира. Хранит год/месяц/день, умеет сравниваться и печататься."""

    __slots__ = ("year", "month", "day")

    def __init__(self, year: int, month: int = 1, day: int = 1):
        self.year = int(year)
        self.month = int(month)
        self.day = int(day)

    # --- конструкторы ---------------------------------------------------

    @classmethod
    def from_ordinal(cls, ordinal: int) -> "Date":
        """Из общего количества дней от начала мира (день 0 = 1.1.1)."""
        year, rest = divmod(int(ordinal), DAYS_IN_YEAR)
        month, day = divmod(rest, DAYS_IN_MONTH)
        return cls(year + 1, month + 1, day + 1)

    @classmethod
    def random_in_year(cls, rng, year: int) -> "Date":
        return cls(year, rng.randint(1, MONTHS_IN_YEAR), rng.randint(1, DAYS_IN_MONTH))

    # --- свойства -------------------------------------------------------

    @property
    def ordinal(self) -> int:
        return (self.year - 1) * DAYS_IN_YEAR + (self.month - 1) * DAYS_IN_MONTH + (self.day - 1)

    @property
    def month_name(self) -> str:
        return MONTH_NAMES[(self.month - 1) % MONTHS_IN_YEAR]

    @property
    def season(self) -> str:
        return SEASONS[(self.month - 1) % MONTHS_IN_YEAR]

    # --- форматирование -------------------------------------------------

    def short(self) -> str:
        return "%d.%02d.%02d" % (self.year, self.month, self.day)

    def long(self) -> str:
        return "%s день месяца %s %d года" % (
            day_ordinal(self.day), self.month_name, self.year)

    def year_text(self) -> str:
        return "%d год" % self.year

    # --- служебное ------------------------------------------------------

    def __str__(self) -> str:
        return self.short()

    def __repr__(self) -> str:
        return "Date(%d, %d, %d)" % (self.year, self.month, self.day)

    def __eq__(self, other) -> bool:
        return isinstance(other, Date) and self.ordinal == other.ordinal

    def __lt__(self, other) -> bool:
        return self.ordinal < other.ordinal

    def __le__(self, other) -> bool:
        return self.ordinal <= other.ordinal

    def __hash__(self) -> int:
        return hash(self.ordinal)

    def to_dict(self) -> dict:
        return {"year": self.year, "month": self.month, "day": self.day}

    @classmethod
    def from_dict(cls, data) -> "Date":
        if data is None:
            return None
        return cls(data["year"], data["month"], data["day"])


def years_text(count: int) -> str:
    """«1 год», «3 года», «10 лет» — правильная форма слова."""
    count = abs(int(count))
    tail = count % 100
    if 11 <= tail <= 14:
        return "%d лет" % count
    tail = count % 10
    if tail == 1:
        return "%d год" % count
    if tail in (2, 3, 4):
        return "%d года" % count
    return "%d лет" % count


def plural(count: int, one: str, few: str, many: str) -> str:
    """Универсальный выбор формы числительного."""
    count = abs(int(count))
    tail = count % 100
    if 11 <= tail <= 14:
        return many
    tail = count % 10
    if tail == 1:
        return one
    if tail in (2, 3, 4):
        return few
    return many
