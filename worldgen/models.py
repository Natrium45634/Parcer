# -*- coding: utf-8 -*-
"""Сущности мира: личности, земли, племена, города, страны, лагеря, события.

Всё, что попадает в летопись, сохраняется здесь и доступно последующим
блокам генератора (войны, религии, артефакты и так далее).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .morph import roman
from .timeline import Date

# --- состояния ---------------------------------------------------------

ACTIVE = "активно"
SETTLED = "осело"
GONE = "исчезло"
RUINED = "разрушено"
FALLEN = "пало"
EXTINCT = "пресёкся"

# Ранги знатных родов.
ROYAL = "правящий"
GREAT = "великий"
MINOR = "малый"


def _date_out(value):
    return value.to_dict() if isinstance(value, Date) else None


@dataclass
class Figure:
    """Историческая личность."""

    id: str
    given_name: str
    epithet: str
    race_id: str
    sex: str                       # "m" / "f"
    birth: Date
    death: Date = None
    origin_region: str = ""
    titles: list = field(default_factory=list)
    roles: list = field(default_factory=list)
    deeds: list = field(default_factory=list)     # id событий
    home_id: str = ""                             # где жил(а): племя/город
    notes: list = field(default_factory=list)

    # --- знатность и родство (блок 2) ---
    surname: str = ""            # родовое имя; у простолюдинов его нет
    house_id: str = ""
    father_id: str = ""
    mother_id: str = ""
    spouse_id: str = ""
    children: list = field(default_factory=list)
    birth_order: int = 0         # порядок рождения среди детей
    regnal_number: int = 0       # «Ронвальд II»
    noble: bool = False
    death_cause: str = ""

    @property
    def name(self) -> str:
        parts = [self.given_name]
        if self.regnal_number >= 2:
            parts.append(roman(self.regnal_number))
        if self.surname:
            parts.append(self.surname)
        if self.epithet:
            parts.append(self.epithet)
        return " ".join(part for part in parts if part)

    @property
    def plain_name(self) -> str:
        """Имя без прозвища — для таблиц и перечислений."""
        parts = [self.given_name]
        if self.regnal_number >= 2:
            parts.append(roman(self.regnal_number))
        if self.surname:
            parts.append(self.surname)
        return " ".join(part for part in parts if part)

    def age_at(self, year: int) -> int:
        if self.birth is None:
            return 0
        return max(0, year - self.birth.year)

    def alive_at(self, year: int) -> bool:
        """Жив(а) ли персонаж в указанном году."""
        if self.birth is not None and year < self.birth.year:
            return False
        return self.death is None or year < self.death.year

    def lifespan_text(self) -> str:
        start = self.birth.year if self.birth else "?"
        end = self.death.year if self.death else "…"
        return "%s — %s" % (start, end)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["birth"] = _date_out(self.birth)
        data["death"] = _date_out(self.death)
        data["name"] = self.name
        return data


@dataclass
class Region:
    """Географическая область мира."""

    id: str
    name: str
    terrain: str
    x: int = 0
    y: int = 0
    neighbors: list = field(default_factory=list)
    capacity: float = 1.0
    discovered_by: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Tribe:
    """Племя — исходная форма общества."""

    id: str
    name: str
    word: str                 # «Племя», «Клан», «Стая»
    race_id: str
    founded: Date
    founder_id: str
    region_id: str
    population: int = 100
    chief_id: str = ""
    status: str = ACTIVE
    ended: Date = None
    settlement_id: str = ""   # если племя осело и построило поселение
    parent_id: str = ""       # от какого племени откололось
    end_reason: str = ""

    @property
    def full_name(self) -> str:
        return "%s «%s»" % (self.word, self.name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        data["full_name"] = self.full_name
        return data


@dataclass
class Settlement:
    """Город, крепость, чертог — постоянное поселение."""

    id: str
    name: str
    kind: str                 # «Город», «Крепость», «Чертог» …
    race_id: str
    founded: Date
    founder_id: str
    region_id: str
    population: int = 500
    polity_id: str = ""
    is_capital: bool = False
    status: str = ACTIVE
    ended: Date = None
    origin_tribe_id: str = ""
    end_reason: str = ""

    @property
    def full_name(self) -> str:
        return "%s %s" % (self.kind.lower(), self.name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Polity:
    """Страна: королевство, держава, владение."""

    id: str
    name: str
    form: str                 # «Королевство», «Подгорное Королевство» …
    race_id: str
    founded: Date
    founder_id: str
    capital_id: str = ""
    region_ids: list = field(default_factory=list)
    settlement_ids: list = field(default_factory=list)
    ruler_id: str = ""
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""
    predecessor_id: str = ""
    # --- династия (блок 2) ---
    house_id: str = ""             # правящий род
    succession: str = ""           # закон наследования
    reign_ids: list = field(default_factory=list)
    house_ids: list = field(default_factory=list)   # знатные роды страны
    interregnum: bool = False      # престол пуст

    @property
    def full_name(self) -> str:
        return "%s %s" % (self.form, self.name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        data["full_name"] = self.full_name
        return data


@dataclass
class Camp:
    """Лагерь, логово или орда злой расы. Страной никогда не становится."""

    id: str
    name: str
    word: str                 # «Лагерь», «Логово», «Орда»
    race_id: str
    founded: Date
    founder_id: str
    region_id: str
    population: int = 80
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""

    @property
    def full_name(self) -> str:
        return "%s «%s»" % (self.word, self.name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        data["full_name"] = self.full_name
        return data


@dataclass
class House:
    """Знатный род: королевская династия, великий дом или малый род."""

    id: str
    name: str                  # родовое имя, оно же фамилия членов
    word: str                  # «Дом», «Клан», «Род», «Стая», «Гнездо»
    race_id: str
    founded: Date
    founder_id: str
    seat_id: str = ""          # родовое гнездо — поселение
    polity_id: str = ""        # страна, где род правит (если правит)
    rank: str = MINOR
    head_id: str = ""
    members: list = field(default_factory=list)   # все, кто когда-либо был в роду
    living: list = field(default_factory=list)    # ещё не умершие
    alive_count: int = 0
    prestige: float = 1.0
    parent_id: str = ""        # от какого дома отделилась младшая ветвь
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""
    thrones: int = 0           # сколько раз род всходил на престол

    @property
    def full_name(self) -> str:
        return "%s %s" % (self.word, self.name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        data["full_name"] = self.full_name
        return data


@dataclass
class Reign:
    """Одно правление: кто, где, когда и чем кончилось."""

    id: str
    polity_id: str
    ruler_id: str
    house_id: str
    start: Date
    number: int = 1            # какое по счёту правление в этой стране
    end: Date = None
    end_reason: str = ""       # «смерть», «переворот», «низложение», …
    regent_id: str = ""        # если правитель был малолетним
    regency_until: int = 0     # год совершеннолетия
    legitimacy: str = "законное"   # «законное», «узурпация», «избрание»
    title: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = _date_out(self.start)
        data["end"] = _date_out(self.end)
        return data


@dataclass
class Event:
    """Запись летописи."""

    id: str
    date: Date
    era_index: int
    kind: str                  # машинный тип: "founding_city", "era_end" …
    title: str
    text: str
    importance: int = 2        # 1 — мелочь, 5 — событие мирового масштаба
    actors: list = field(default_factory=list)    # id личностей
    subjects: list = field(default_factory=list)  # id стран, городов и т.д.
    region_id: str = ""
    race_id: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["date"] = _date_out(self.date)
        return data


@dataclass
class EraSpan:
    """Отрезок времени — эпоха."""

    index: int
    key: str
    name: str
    start_year: int
    end_year: int
    description: str = ""
    end_event_id: str = ""
    end_title: str = ""

    @property
    def length(self) -> int:
        return self.end_year - self.start_year + 1

    def contains(self, year: int) -> bool:
        return self.start_year <= year <= self.end_year

    def to_dict(self) -> dict:
        return asdict(self)
