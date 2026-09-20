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
ONGOING = "длится"
ENDED = "завершено"
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
    faith_id: str = ""           # во что верил(а)
    patron_deity_id: str = ""    # кто покровительствовал или проклял
    divine_mark: str = ""        # «благословение», «проклятие»
    folk_id: str = ""            # народ внутри расы

    # --- нрав, умения и брак (блок 8) ---
    # Заполняется у тех, кто садится на престол: для прочих всё среднее.
    alignment: int = 0           # от 3 (праведный) до -3 (бесчеловечный)
    skills: dict = field(default_factory=dict)    # война/правление/двор/вера
    traits: list = field(default_factory=list)    # черты нрава, мужская форма
    married: Date = None         # когда был заключён брак
    posthumous: str = ""         # прозвище, данное потомками: «Грозный»

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
        data["married"] = _date_out(self.married)
        data["name"] = self.name
        return data


@dataclass
class Region:
    """Географическая область мира.

    Если мир построен по карте, земля помнит свои гексы и всё, что карта
    о них знает: плодородие, магию, дикость, чем грозит округа.
    """

    id: str
    name: str
    terrain: str
    x: int = 0
    y: int = 0
    neighbors: list = field(default_factory=list)      # соседи по суше
    sea_links: list = field(default_factory=list)      # куда только доплыть
    capacity: float = 1.0
    discovered_by: str = ""
    known: bool = False           # ведома ли земля обитаемому миру
    discovered_year: int = 0
    discovered_by_id: str = ""    # кто открыл: id личности

    # --- данные карты (пусто, если земля создана процедурно) ---
    hexes: list = field(default_factory=list)
    center_hex: int = -1
    habitat: float = 0.0        # насколько тут вообще можно жить, 0…1
    fertility: float = 0.0
    magic: float = 0.0          # минус — тёмная, плюс — светлая
    savagery: float = 0.0
    richness: float = 0.0       # руды и камень
    risk: float = 0.0           # как часто тут беда
    risk_kinds: list = field(default_factory=list)   # чем земля грозит
    boons: list = field(default_factory=list)        # и чем одаривает
    coastal: bool = False
    river: bool = False
    island: bool = False
    elev_m: int = 0
    temp: float = 0.0
    moist: float = 0.0
    # --- география с карты: имена, которые дал сам картогенератор ---
    landmass: str = ""            # материк или остров, «Вайрен»
    landmass_kind: str = ""       # «материк», «большой остров», «архипелаг»
    sea: str = ""                 # ближайшая большая вода, «Коранен»
    sea_kind: str = ""            # «океан», «море», «залив»
    range_name: str = ""          # хребет, если земля горная
    rivers: list = field(default_factory=list)   # реки, текущие через землю

    @property
    def from_map(self) -> bool:
        return bool(self.hexes)

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
    faith_id: str = ""
    hex_index: int = -1            # гекс карты, если мир построен по карте
    folk_id: str = ""              # народ внутри расы

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
    faith_id: str = ""             # во что верят жители
    hex_index: int = -1            # гекс карты, если мир построен по карте
    folk_id: str = ""              # народ внутри расы
    landmarks: list = field(default_factory=list)   # чем город отличается
                                                    # от соседнего: стена,
                                                    # мост, маяк, ярмарка

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
    population: int = 0            # полное население: города и сельская округа
    peak_population: int = 0
    faith_id: str = ""             # государственная вера

    # --- народы страны (блок 6) ---
    # race_id выше — титульный народ, тот, чья знать сидит на престоле.
    # Здесь же живут все прочие: завоёванные, пришлые, осевшие.
    peoples: dict = field(default_factory=dict)      # раса -> душ
    policy: str = ""               # как держава обходится с иными народами
    policy_since: int = 0
    titular_since: int = 0         # с какого года престол у нынешнего народа
    grievance: dict = field(default_factory=dict)    # раса -> обида, 0…1
    conquests: list = field(default_factory=list)    # id событий завоеваний

    # --- хозяйство (блок 7) ---
    goods: dict = field(default_factory=dict)        # товар -> (есть, надо)
    shortages: list = field(default_factory=list)    # чего не хватает
    surpluses: list = field(default_factory=list)    # чем торгует
    routes: list = field(default_factory=list)       # id торговых путей
    roads: list = field(default_factory=list)        # проложенные дороги
    hunger: float = 0.0        # насколько державе нечего есть, 0…1
    last_famine: int = 0       # год последнего голода

    # --- язык (блок 11) ---
    tongue_id: str = ""        # язык двора и грамот

    # --- политика (блок 10) ---
    relations: dict = field(default_factory=dict)    # держава -> отношение −1…1
    pact_ids: list = field(default_factory=list)     # договоры
    league_id: str = ""                              # союз, если состоит

    union_id: str = ""                               # династическая уния
    intrigue: float = 0.0      # оплаченная соседом смута при дворе, 0…1

    # --- умения (блок 12) ---
    known: list = field(default_factory=list)        # открытия, какими владеет

    # --- обиды (блок 11) ---
    # держава -> {повод: год}. Кровь посла, пойманный соглядатай, яд при
    # дворе: то, что помнят поимённо и припоминают при объявлении войны.
    grudges: dict = field(default_factory=dict)

    # --- война (блок 9) ---
    war_ids: list = field(default_factory=list)      # все войны страны
    tribute_to: str = ""       # кому платит дань
    tribute_until: int = 0     # до какого года
    overlord_id: str = ""      # чьё старшинство признано
    weariness: float = 0.0     # усталость от войн, 0…1
    last_war: int = 0          # год окончания последней войны
    wars_won: int = 0
    wars_lost: int = 0

    @property
    def multiethnic(self) -> bool:
        return len([race for race, souls in self.peoples.items() if souls > 0]) > 1

    def share_of(self, race_id: str) -> float:
        total = float(sum(self.peoples.values())) or 1.0
        return self.peoples.get(race_id, 0) / total

    def minorities(self) -> list:
        """Народы страны, кроме титульного, от большего к меньшему."""
        rows = [(race, souls) for race, souls in self.peoples.items()
                if race != self.race_id and souls > 0]
        rows.sort(key=lambda pair: (-pair[1], pair[0]))
        return rows

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
    faith_id: str = ""
    hex_index: int = -1            # гекс карты, если мир построен по карте

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

    # --- нрав, достаток и место на лестнице знати (блок 8) ---
    alignment: int = 0         # от 3 (безупречный) до -3 (гнилой)
    wealth: float = 1.0        # достаток рода
    ambition: float = 1.0      # насколько род тянется к венцу
    motto: str = ""            # девиз над воротами
    rung: int = -1             # ступень титула; -1 — ещё не размечен
    style: str = ""            # сам титул: «граф», «тан», «ярл»
    discontent: float = 0.0    # накопленное недовольство властью
    charters: int = 0          # сколько вольностей вырвано у короны

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
    # --- каким был государь и что после него осталось (блок 8) ---
    relation: str = ""         # кем приходился предшественнику
    alignment: int = 0
    skills: dict = field(default_factory=dict)
    traits: list = field(default_factory=list)
    opening: dict = field(default_factory=dict)   # держава в начале правления
    closing: dict = field(default_factory=dict)   # и в конце
    verdict: str = ""          # «великое» … «гибельное»
    score: float = 0.0         # во сколько раз держава выросла или ужалась

    @property
    def length(self) -> int:
        if self.end is None:
            return 0
        return max(0, self.end.year - self.start.year)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = _date_out(self.start)
        data["end"] = _date_out(self.end)
        return data


@dataclass
class Deity:
    """Божество: имя, титул, сферы покровительства и мировоззрение."""

    id: str
    given_name: str
    title: str                 # «Владыка», «Мать», «Око»
    sex: str = "m"             # m / f / n — есть и безликие
    race_id: str = ""          # народ, которому бог явился первым
    faith_id: str = ""
    domains: list = field(default_factory=list)     # ключи сфер
    alignment: int = 0         # от 3 (всеблагой) до -3 (злой)
    symbol: str = ""
    festival_name: str = ""
    festival_month: int = 1
    festival_day: int = 1
    revealed: Date = None
    status: str = "почитается"  # почитается / забыт / низвергнут
    epithet: str = ""          # «Владыка Леса»
    # --- покровительство и первородство (блок 8) ---
    primordial: bool = False   # был ли при сотворении мира
    maker: bool = False        # творец ли этого мира
    patron_kind: str = ""      # «народ», «ремесло», «сословие», «земля»
    patron_name: str = ""      # кому или чему покровительствует
    notes: list = field(default_factory=list)

    @property
    def full_name(self) -> str:
        if self.epithet:
            return "%s, %s" % (self.given_name, self.epithet)
        return self.given_name

    @property
    def name(self) -> str:
        return self.given_name

    def to_dict(self) -> dict:
        data = asdict(self)
        data["revealed"] = _date_out(self.revealed)
        data["full_name"] = self.full_name
        return data


@dataclass
class Faith:
    """Вера: пантеон, культ одного бога, ересь или вера предков."""

    id: str
    name: str
    kind: str                  # пантеон / культ / ересь / вера предков
    founded: Date
    founder_id: str = ""       # пророк или основатель
    deity_ids: list = field(default_factory=list)
    chief_deity_id: str = ""
    race_ids: list = field(default_factory=list)    # народы-носители
    polity_ids: list = field(default_factory=list)  # где она государственная
    temple_ids: list = field(default_factory=list)
    high_priest_id: str = ""
    alignment: int = 0
    status: str = "зарождается"
    forbidden: bool = False
    followers: int = 0
    peak_followers: int = 0
    parent_id: str = ""        # от какой веры откололась
    ended: Date = None
    end_reason: str = ""
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Temple:
    """Храм или святилище. Разрушенный храм остаётся в летописи руинами."""

    id: str
    name: str
    faith_id: str
    deity_id: str = ""
    settlement_id: str = ""
    region_id: str = ""
    founded: Date = None
    founder_id: str = ""
    grandeur: int = 1          # 1 — святилище, 3 — великий храм
    status: str = "действует"  # действует / заброшен / в руинах
    ended: Date = None
    end_reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Calamity:
    """Бедствие: от засухи до вторжения владыки демонов."""

    id: str
    key: str                   # ключ вида бедствия в каталоге
    kind: str                  # natural / invasion / political / climate / magic
    name: str                  # «Нашествие Пепельного Роя»
    severity: int              # 1 — лёгкое, 5 — апокалиптическое
    start: Date
    end: Date = None
    status: str = ONGOING
    region_ids: list = field(default_factory=list)
    polity_ids: list = field(default_factory=list)
    race_id: str = ""          # раса захватчика, если есть
    leader_id: str = ""        # вождь вторжения
    general_ids: list = field(default_factory=list)
    hero_ids: list = field(default_factory=list)      # кто одолел
    commander_ids: list = field(default_factory=list)  # правители-союзники
    resolution: str = ""       # «убит героем», «запечатан», «иссякло само»
    deaths: int = 0
    deaths_by_polity: dict = field(default_factory=dict)
    deaths_by_race: dict = field(default_factory=dict)
    settlements_lost: int = 0
    polities_lost: int = 0
    parent_id: str = ""        # из какого бедствия выросло
    relic_ids: list = field(default_factory=list)
    compounded_with: list = field(default_factory=list)
    dark_age_until: int = 0
    battle_ids: list = field(default_factory=list)
    strength: float = 1.0      # запас сил захватчика, 1.0 — полон
    host_size: int = 0         # сколько их было
    notes: list = field(default_factory=list)

    @property
    def years(self) -> int:
        if self.end is None:
            return 0
        return max(0, self.end.year - self.start.year)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = _date_out(self.start)
        data["end"] = _date_out(self.end)
        return data


@dataclass
class Relic:
    """След бедствия: недобитый генерал, печать, проклятое место.

    Через века такой след могут потревожить — и старая беда напомнит о себе.
    """

    id: str
    name: str
    kind: str                  # «логово», «печать», «проклятое место», …
    calamity_id: str
    region_id: str
    created: Date
    potency: int = 1           # насколько опасно пробуждение
    status: str = "спит"       # спит / потревожен / исчерпан
    awakened: Date = None
    figure_id: str = ""        # уцелевший вождь, если он есть
    race_id: str = ""
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created"] = _date_out(self.created)
        data["awakened"] = _date_out(self.awakened)
        return data


@dataclass
class Artifact:
    """Вещь, у которой есть имя, и потому есть история.

    Артефакт никогда не висит в пустоте: у него либо владелец, либо
    место — курган, сокровищница, храм, логово, руины. Цепочка рук
    (``trail``) хранится целиком: кто держал, в каком году и как получил.
    """

    id: str
    name: str
    shape: str                 # ключ рода вещи: sword, crown, book …
    word: str                  # «Меч», «Венец» — как называть в летописи
    gender: str                # род слова: m / f / n — для согласования
    sort: str                  # оружие / доспех / регалия / утварь / книга
    material: str
    material_gen: str          # «из звёздного железа»
    made: Date
    origin: str                # выкован / дарован богом / взят у чудовища …
    maker_id: str = ""
    race_id: str = ""
    powers: list = field(default_factory=list)
    curse: str = ""
    where: str = "у владельца"  # у владельца / в кургане / в логове / потерян …
    owner_id: str = ""
    polity_id: str = ""
    site_id: str = ""
    region_id: str = ""
    trail: list = field(default_factory=list)   # [{year, who, how}]
    deeds: list = field(default_factory=list)   # id событий
    fame: float = 1.0
    lost: Date = None
    status: str = ACTIVE
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["made"] = _date_out(self.made)
        data["lost"] = _date_out(self.lost)
        return data


@dataclass
class Codex:
    """Летописный свод: кто ведёт, как долго и насколько врёт."""

    id: str
    name: str
    seat_id: str               # город, где его пишут
    region_id: str
    started: Date
    polity_id: str = ""
    faith_id: str = ""
    bias: str = "сухой"
    accuracy: float = 0.8
    keeper_id: str = ""        # нынешний летописец
    keepers: list = field(default_factory=list)   # [{figure, from, to}]
    entries: list = field(default_factory=list)   # [{year, event, kind}]
    span: int = 0              # сколько лет охватывает
    status: str = "ведётся"
    ended: Date = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["started"] = _date_out(self.started)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Legend:
    """Легенда: то, что рассказывают о событии, а не то, что было."""

    id: str
    name: str
    born: Date
    event_id: str = ""
    about: str = ""            # чудовище / герой / вещь / битва
    subject_id: str = ""
    race_id: str = ""
    region_id: str = ""
    truth: str = ""            # как было на самом деле, одной строкой
    shifts: list = field(default_factory=list)    # [{year, shift}]
    tellings: int = 1
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["born"] = _date_out(self.born)
        return data


@dataclass
class Discovery:
    """Открытие: что, где, кем и когда сделано и кто это перенял."""

    id: str
    key: str                   # ключ из каталога ремёсел
    name: str
    family: str
    made: Date
    polity_id: str = ""
    settlement_id: str = ""
    figure_id: str = ""
    race_id: str = ""
    known_by: list = field(default_factory=list)     # державы, перенявшие его
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["made"] = _date_out(self.made)
        return data


@dataclass
class Monster:
    """Чудовище с именем: логово, счёт убитых и тот, кто его прикончил."""

    id: str
    name: str
    breed: str                 # ключ породы: dragon, wyrm, vampire …
    word: str                  # «Дракон», «Кровопийца»
    gender: str
    family: str                # чудовище / ночная тварь
    born: Date
    region_id: str = ""
    settlement_id: str = ""    # где прячется ночная тварь
    site_id: str = ""          # логово
    power: float = 1.0
    kills: int = 0
    raids: int = 0
    hoard: int = 0
    heroes_eaten: list = field(default_factory=list)
    status: str = "жив"
    slayer_id: str = ""
    ended: Date = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["born"] = _date_out(self.born)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Site:
    """Место, у которого есть содержимое и история.

    Курган героя, клад в логове, руины павшего города, запечатанный
    чертог. Всё, что нужно, чтобы построить по нему подземелье: кто
    здесь лежит, что здесь спрятано, кто это стережёт и когда сюда в
    последний раз входили.
    """

    id: str
    kind: str                  # курган / руины / логово / клад / поле битвы …
    name: str
    region_id: str
    created: Date
    hex_index: int = -1
    figure_id: str = ""        # чей курган
    polity_id: str = ""        # чья держава его оставила
    settlement_id: str = ""    # если это руины города
    calamity_id: str = ""      # если это след бедствия
    monster_id: str = ""       # кто там поселился
    battle_id: str = ""
    artifact_ids: list = field(default_factory=list)
    guards: str = ""           # кто стережёт
    riches: int = 0            # сколько там добра, в условном счёте
    depth: int = 1             # насколько глубоко и опасно, 1…5
    story: str = ""            # одна строка: чем это место памятно
    status: str = "нетронуто"  # нетронуто / разграблено / обитаемо / обрушено
    opened: Date = None
    opened_by: str = ""
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created"] = _date_out(self.created)
        data["opened"] = _date_out(self.opened)
        return data


@dataclass
class Battle:
    """Сражение: кто, с кем, где и чем кончилось."""

    id: str
    name: str
    date: Date
    calamity_id: str = ""
    region_id: str = ""
    attacker_id: str = ""              # вождь нападающих
    defender_ids: list = field(default_factory=list)
    polity_ids: list = field(default_factory=list)
    winner: str = "враг"               # «враг» или «защитники»
    fallen_ids: list = field(default_factory=list)
    deaths: int = 0
    decisive: bool = False
    # --- сражения держав (блок 9) ---
    war_id: str = ""
    kind: str = "битва"                # битва / осада / штурм / набег
    settlement_id: str = ""            # если дрались за город
    attacker_polity: str = ""
    defender_polity: str = ""
    attacker_men: int = 0
    defender_men: int = 0
    captured_ids: list = field(default_factory=list)   # взятые в плен

    def to_dict(self) -> dict:
        data = asdict(self)
        data["date"] = _date_out(self.date)
        return data


@dataclass
class War:
    """Война держав: за что, как шла и чем кончилась."""

    id: str
    name: str
    start: Date
    attacker_id: str
    defender_id: str
    cause: str                 # ключ повода из warfare.py
    aim: str                   # чего хотел нападающий
    end: Date = None
    status: str = ONGOING
    scale: int = 1             # 1 — стычка, 5 — война империй
    outcome: str = ""
    peace_name: str = ""       # «Мир в городе Роэнберг»
    feud_id: str = ""          # если война входит в вековую распрю
    planned_years: int = 1     # сколько ей отмерено, если ничто не оборвёт
    battle_ids: list = field(default_factory=list)
    attacker_generals: list = field(default_factory=list)
    defender_generals: list = field(default_factory=list)
    attacker_allies: list = field(default_factory=list)   # кто пришёл на помощь
    defender_allies: list = field(default_factory=list)
    league_ids: list = field(default_factory=list)        # союзы, втянутые в войну
    # --- море (блок 10) ---
    at_sea: bool = False       # война идёт через воду, а не через межу
    attacker_ships: int = 0
    defender_ships: int = 0
    attacker_ships_lost: int = 0
    defender_ships_lost: int = 0
    blockades: dict = field(default_factory=dict)         # гавань -> лет в блокаде
    landings: int = 0          # сколько раз высаживались за морем
    attacker_men: int = 0      # под знамёнами на начало
    defender_men: int = 0
    attacker_losses: int = 0
    defender_losses: int = 0
    momentum: float = 0.0      # -1 берут верх оборонявшиеся, +1 нападавшие
    exhaustion: float = 0.0    # насколько обе стороны выдохлись
    taken_ids: list = field(default_factory=list)     # перешедшие города
    razed: int = 0
    sieges: dict = field(default_factory=dict)        # город -> лет в осаде
    fallen_ids: list = field(default_factory=list)    # погибшие имена
    captured_ids: list = field(default_factory=list)  # пленённые
    notes: list = field(default_factory=list)

    @property
    def years(self) -> int:
        if self.end is None:
            return 0
        return max(0, self.end.year - self.start.year)

    @property
    def deaths(self) -> int:
        return self.attacker_losses + self.defender_losses

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = _date_out(self.start)
        data["end"] = _date_out(self.end)
        return data


@dataclass
class Tongue:
    """Язык народа: звучание, письменность, родня и судьба."""

    id: str
    name: str
    race_id: str
    born: Date
    parent_id: str = ""        # от какого языка отошёл
    laws: list = field(default_factory=list)      # звуковые законы
    script: str = ""           # письменность, если изобретена
    script_year: int = 0
    script_from: str = ""      # у кого одолжили письмо
    folk_ids: list = field(default_factory=list)
    speakers: int = 0
    borrowed: list = field(default_factory=list)  # языки-источники слов
    status: str = "живой"      # живой / священный / мёртвый
    ended: Date = None
    end_reason: str = ""
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["born"] = _date_out(self.born)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Guild:
    """Гильдия: касса, склады и своё право между престолом и знатью."""

    id: str
    name: str
    kind: str                  # купеческая / мореходная / ремесленная / банкирская
    good: str                  # товар, на котором поднялась
    seat_id: str               # город, где сидит
    polity_id: str
    founded: Date
    head_id: str = ""          # старшина
    wealth: float = 0.0
    charters: list = field(default_factory=list)   # державы, где есть вольности
    companies: list = field(default_factory=list)  # нанятые роты
    deeds: int = 0             # сколько раз вмешивалась в дела держав
    republic_id: str = ""      # держава, которой гильдия стала
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Plot:
    """Тайное дело: кто, против кого, чьими руками и чем кончилось."""

    id: str
    kind: str                  # подкуп / яд / заговор / смута / подлог …
    sender_id: str
    target_id: str
    agent_id: str              # исполнитель
    date: Date
    outcome: str = ""          # удалось / сорвалось / раскрыто
    victim_id: str = ""        # кого подкупили или отравили
    war_id: str = ""           # война, ради которой всё затевалось
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["date"] = _date_out(self.date)
        return data


@dataclass
class Union:
    """Династическая уния: две короны на одной голове.

    Появляется, когда престол пустеет, а право на него есть у чужого
    государя — по брачному договору дедов. Держится, пока обе короны
    достаются одному наследнику, и кончается либо расхождением корон,
    либо тем, что младшая держава сливается со старшей навсегда.
    """

    id: str
    first_id: str              # держава, чей государь получил вторую корону
    second_id: str             # унаследованный престол
    monarch_id: str
    started: Date
    monarchs: list = field(default_factory=list)   # кто носил обе короны
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""
    merged: bool = False       # кончилась ли слиянием держав
    notes: list = field(default_factory=list)

    @property
    def years(self) -> int:
        if self.ended is None or self.started is None:
            return 0
        return max(0, self.ended.year - self.started.year)

    def other(self, polity_id: str) -> str:
        return self.second_id if polity_id == self.first_id else self.first_id

    def to_dict(self) -> dict:
        data = asdict(self)
        data["started"] = _date_out(self.started)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Embassy:
    """Посольство: кого, к кому, с чем послали и с чем оно вернулось."""

    id: str
    sender_id: str
    host_id: str
    envoy_id: str              # посол
    sent: Date
    purpose: str               # ключ наказа: «мир», «союз», «дань» …
    gift: str = ""
    answer: str = ""           # принято / отказано / выставили / убили
    pact_id: str = ""          # договор, если из посольства вышел договор
    returned: Date = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sent"] = _date_out(self.sent)
        data["returned"] = _date_out(self.returned)
        return data


@dataclass
class Fortress:
    """Крепость: стоит веками и переходит из рук в руки.

    Города гибнут и зарастают, а крепость на перевале или у брода стоит
    там же, где стояла, — меняется только знамя над ней.
    """

    id: str
    name: str
    region_id: str
    built: Date
    founder_id: str = ""       # кто заложил
    polity_id: str = ""        # чьё знамя над ней сейчас
    builder_polity: str = ""   # кто её строил
    kind: str = "крепость"     # крепость / застава / твердыня / бастион
    strength: int = 3          # 1 — частокол, 5 — неприступная твердыня
    hex_index: int = -1
    status: str = ACTIVE       # активно / разрушено / заброшено
    ended: Date = None
    end_reason: str = ""
    holders: list = field(default_factory=list)   # [(год, id державы)]
    sieges: int = 0
    times_taken: int = 0
    notes: list = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return "%s %s" % (self.kind, self.name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["built"] = _date_out(self.built)
        data["ended"] = _date_out(self.ended)
        data["full_name"] = self.full_name
        return data


@dataclass
class Company:
    """Вольная рота: те, кто живёт войной и между войнами тоже."""

    id: str
    name: str
    race_id: str
    founded: Date
    captain_id: str = ""
    men: int = 0
    quality: float = 1.0
    region_id: str = ""
    employer_id: str = ""      # кто нанял сейчас
    contract_until: int = 0
    wars: int = 0
    raids: int = 0             # сколько раз грабили, оставшись без найма
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""
    notes: list = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return "Вольная рота «%s»" % self.name

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        data["full_name"] = self.full_name
        return data


@dataclass
class Pact:
    """Договор двух держав: от ненападения до союза."""

    id: str
    kind: str                  # ненападение / торговый / брачный / союз
    first_id: str
    second_id: str
    signed: Date
    ended: Date = None
    status: str = ACTIVE
    end_reason: str = ""
    league_id: str = ""
    reasons: list = field(default_factory=list)    # почему сошлись
    wars_together: int = 0     # сколько раз воевали плечом к плечу
    betrayals: int = 0         # и сколько раз не пришли на зов
    notes: list = field(default_factory=list)

    def other(self, polity_id: str) -> str:
        return self.second_id if polity_id == self.first_id else self.first_id

    def to_dict(self) -> dict:
        data = asdict(self)
        data["signed"] = _date_out(self.signed)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class League:
    """Союз нескольких держав: оборонительный, священный, торговый."""

    id: str
    name: str
    kind: str
    founded: Date
    member_ids: list = field(default_factory=list)
    leader_id: str = ""
    pact_ids: list = field(default_factory=list)
    war_ids: list = field(default_factory=list)
    target_id: str = ""        # против кого сложился, если против кого-то
    status: str = ACTIVE
    ended: Date = None
    end_reason: str = ""
    notes: list = field(default_factory=list)

    @property
    def years(self) -> int:
        if self.ended is None or self.founded is None:
            return 0
        return max(0, self.ended.year - self.founded.year)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["founded"] = _date_out(self.founded)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Feud:
    """Вековая распря: цепь войн между одной и той же парой держав."""

    id: str
    name: str
    polity_ids: list = field(default_factory=list)    # пара враждующих
    war_ids: list = field(default_factory=list)
    start: Date = None
    end: Date = None
    status: str = ONGOING
    deaths: int = 0

    @property
    def years(self) -> int:
        if self.end is None or self.start is None:
            return 0
        return max(0, self.end.year - self.start.year)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = _date_out(self.start)
        data["end"] = _date_out(self.end)
        return data


@dataclass
class TradeRoute:
    """Торговый путь между двумя державами — настоящий, по гексам."""

    id: str
    seller_id: str
    buyer_id: str
    good: str                  # что везут туда
    back: str = ""             # что везут обратно
    by_sea: bool = False
    path: list = field(default_factory=list)    # гексы карты
    length: int = 0            # длина пути в гексах
    cost: float = 0.0          # во что обходится дорога
    opened: Date = None
    closed: Date = None
    status: str = ACTIVE
    end_reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["opened"] = _date_out(self.opened)
        data["closed"] = _date_out(self.closed)
        return data


@dataclass
class Folk:
    """Народ внутри расы.

    Люди болот у большой реки и люди предгорий за тысячу вёрст — родня,
    но не один народ: свои имена, свои промыслы, свои враги.
    """

    id: str
    name: str
    name_kind: str             # как построено имя: ethnic / mark / landmark
    race_id: str
    cradle_region: str         # где проснулись
    born: Date
    traits: list = field(default_factory=list)
    population: int = 0
    settlements: int = 0
    tribes: int = 0
    polities: int = 0
    parent_id: str = ""
    tongue_id: str = ""        # на каком языке говорит (блок 11)
    status: str = ACTIVE
    ended: Date = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["born"] = _date_out(self.born)
        data["ended"] = _date_out(self.ended)
        return data


@dataclass
class Expedition:
    """Поход в неизведанное: за море, за горы, за край света."""

    id: str
    name: str
    kind: str                  # sea / land / ice / deep
    leader_id: str
    race_id: str
    start: Date
    polity_id: str = ""        # кто снарядил; пусто — вольный поход
    from_region: str = ""
    target_region: str = ""
    target_name: str = ""      # что искали: остров, архипелаг, край света
    end: Date = None
    outcome: str = ""          # discovered / sighted / lost / empty
    discovered: list = field(default_factory=list)
    crew: int = 0
    deaths: int = 0
    attempt: int = 1           # какая по счёту попытка дойти до этой цели
    notes: list = field(default_factory=list)

    @property
    def years(self) -> int:
        if self.end is None:
            return 0
        return max(0, self.end.year - self.start.year)

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
