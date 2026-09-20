# -*- coding: utf-8 -*-
"""Каталог бедствий мира.

Бедствия — главный источник неповторимости. Один мир переживёт две засухи
и распад империи, другой — трёхсотлетнее нашествие глубоководных, ледники
и пробуждение дракона, оставшегося от войска, разбитого четыре тысячи лет
назад.

Пять семейств:

* ``natural``   — засухи, наводнения, пожары, моры, землетрясения;
* ``climate``   — ледники, потепления, вулканические зимы: медленно и надолго;
* ``invasion``  — демоны, драконы, нежить, глубоководные, рои, Пустота;
* ``political`` — распады держав, раздробленность, завоевания племенами;
* ``magic``     — магические бури, разломы, проклятия, войны чародеев.

Тяжесть — от 1 (местная беда) до 5 (апокалипсис). Природа редко доходит
до пятого уровня: только извержение, выстудившее мир на век. Пятый уровень —
это почти всегда вторжение.
"""

from __future__ import annotations

from dataclasses import dataclass

NATURAL = "natural"
CLIMATE = "climate"
INVASION = "invasion"
POLITICAL = "political"
MAGIC = "magic"
RELIGIOUS = "religious"

KIND_NAMES = {
    NATURAL: "Природное бедствие",
    CLIMATE: "Долгая перемена климата",
    INVASION: "Вторжение",
    POLITICAL: "Политическая катастрофа",
    MAGIC: "Магический катаклизм",
    RELIGIOUS: "Война за веру",
}

SEVERITY_NAMES = {
    1: "лёгкое",
    2: "заметное",
    3: "тяжёлое",
    4: "великое",
    5: "апокалиптическое",
}

SEVERITY_ADJECTIVES = {
    1: ("местная беда", "неурядица"),
    2: ("настоящее бедствие", "тяжёлый год"),
    3: ("тяжкое бедствие", "чёрные времена"),
    4: ("великое бедствие", "погибель целых народов"),
    5: ("конец света, как его понимали", "апокалипсис"),
}

# Доля населения, которую бедствие уносит за всё время (до множителей).
TOLL_BY_SEVERITY = {
    1: (0.004, 0.018),
    2: (0.018, 0.065),
    3: (0.065, 0.19),
    4: (0.19, 0.40),
    5: (0.40, 0.72),
}


@dataclass(frozen=True)
class CalamitySpec:
    key: str
    kind: str
    title: str                    # «Засуха»
    noun: tuple                   # ("Засуха", "f") — для составного названия
    severities: tuple             # ((уровень, вес), …)
    duration: tuple = (1, 3)      # длительность при первом уровне
    duration_scale: float = 1.8   # во сколько раз растёт с каждым уровнем
    toll: float = 1.0             # множитель смертности
    scope: tuple = (1, 2)         # сколько земель охватывает при первом уровне
    scope_scale: float = 1.55
    terrains: tuple = ()          # где случается (пусто — где угодно)
    race_id: str = ""             # раса захватчика
    generals: tuple = (0, 0)      # сколько военачальников у вторжения
    resolutions: tuple = ()       # ((путь, вес), …)
    relics: tuple = ()            # ((вид следа, вес), …)
    era_range: tuple = (0, 4)
    weight: float = 1.0
    needs_polity: bool = False
    host_words: tuple = ()        # «Легион», «Воинство», «Орда»
    spawns: tuple = ()            # ((ключ, вероятность), …) — что может породить
    adjectives: tuple = ()
    flavor: tuple = ()
    worldwide: bool = False       # беда приходит ко всем сразу, а не к землям
    from_relic_only: bool = False  # сама не случается: её поднимает след прошлого

    # Большие беды должны быть редкими: иначе конец света перестаёт
    # быть концом света.
    SEVERITY_DAMPENER = {1: 1.0, 2: 1.0, 3: 0.8, 4: 0.45, 5: 0.3}

    def severity(self, rng) -> int:
        pairs = [(level, weight * self.SEVERITY_DAMPENER.get(level, 1.0))
                 for level, weight in self.severities]
        return rng.weighted(pairs)

    def years(self, rng, severity: int) -> int:
        low, high = self.duration
        factor = self.duration_scale ** (severity - 1)
        return max(1, int(round(rng.uniform(low, high) * factor)))

    def regions_count(self, rng, severity: int) -> int:
        low, high = self.scope
        factor = self.scope_scale ** (severity - 1)
        return max(1, int(round(rng.uniform(low, high) * factor)))

    def toll_share(self, rng, severity: int) -> float:
        low, high = TOLL_BY_SEVERITY[severity]
        return max(0.001, min(0.9, rng.uniform(low, high) * self.toll))


def _s(*pairs) -> tuple:
    return tuple(pairs)


# Пути разрешения. Ключ -> (описание для летописи, нужны ли герои).
RESOLUTIONS = {
    "hero": ("сражён героем", True),
    "heroes": ("сражён отрядом героев", True),
    "coalition": ("разбит всемирной коалицией", True),
    "sealed": ("запечатан", True),
    "driven_back": ("отброшен за пределы мира", True),
    "tribute": ("откуплен данью", False),
    "faded": ("ушёл сам, насытившись", False),
    "burned_out": ("выжег всё и схлынул", False),
    "endured": ("пережито", False),
    "rains": ("кончилось с переменой погоды", False),
    "adapted": ("мир приспособился", False),
    "dispersed": ("развеяно чародеями", True),
    "reunited": ("страна собрана заново", True),
    "shattered": ("распалось окончательно", False),
    "suppressed": ("подавлено силой", True),
    "absorbed": ("завоеватели осели и стали своими", False),
}

NATURAL_ADJECTIVES = ("Великий", "Чёрный", "Долгий", "Страшный", "Багровый",
                      "Серый", "Голодный", "Горький", "Немилосердный", "Гнилой")


CATALOG = (
    # ------------------------------------------------------------------
    # Природные бедствия
    # ------------------------------------------------------------------
    CalamitySpec(
        key="drought", kind=NATURAL, title="Засуха", noun=("Засуха", "f"),
        severities=_s((1, 5.0), (2, 3.0), (3, 1.0)),
        duration=(2, 5), duration_scale=1.7, toll=1.0,
        terrains=("степь", "равнина", "пустыня", "холмы", "побережье"),
        resolutions=_s(("rains", 5.0), ("endured", 3.0)),
        relics=_s(("выжженная земля", 1.0),),
        adjectives=NATURAL_ADJECTIVES,
        flavor=("Реки мелеют, колодцы показывают дно.",
                "Скот гонят за сотни вёрст к воде, и половина не доходит.",
                "Зерно продают на вес серебра.",
                "Пастбища трескаются, как старая кожа."),
        weight=3.0,
    ),
    CalamitySpec(
        key="flood", kind=NATURAL, title="Наводнение", noun=("Наводнение", "n"),
        severities=_s((1, 5.0), (2, 3.0), (3, 0.8)),
        duration=(1, 2), duration_scale=1.5, toll=0.9,
        terrains=("равнина", "побережье", "болото", "джунгли"),
        resolutions=_s(("endured", 4.0), ("rains", 2.0)),
        relics=_s(("затопленные земли", 1.0),),
        adjectives=NATURAL_ADJECTIVES,
        flavor=("Вода стоит там, где была пашня.",
                "Мосты уносит, дороги превращаются в топи.",
                "Соль отравляет поля у моря на годы вперёд."),
        weight=2.6,
    ),
    CalamitySpec(
        key="wildfire", kind=NATURAL, title="Великий пожар", noun=("Пожар", "m"),
        severities=_s((1, 5.0), (2, 2.5)),
        duration=(1, 3), duration_scale=1.5, toll=0.8,
        terrains=("лес", "джунгли", "степь", "холмы"),
        resolutions=_s(("rains", 4.0), ("endured", 3.0)),
        relics=_s(("выжженная земля", 1.0),),
        adjectives=NATURAL_ADJECTIVES,
        flavor=("Дым стоит так, что в полдень темно.",
                "Огонь идёт быстрее всадника.",
                "Пепел засыпает крыши за сто вёрст от огня."),
        weight=2.2,
    ),
    CalamitySpec(
        key="plague", kind=NATURAL, title="Мор", noun=("Мор", "m"),
        severities=_s((2, 4.0), (3, 3.0), (4, 1.0)),
        duration=(2, 6), duration_scale=1.6, toll=1.6,
        resolutions=_s(("endured", 5.0), ("dispersed", 1.0)),
        relics=_s(("моровое кладбище", 1.0), ("чумной город", 0.6)),
        adjectives=("Чёрный", "Багровый", "Красный", "Серый", "Тихий",
                    "Великий", "Гнилой"),
        flavor=("Мёртвых не успевают хоронить и сжигают вместе с домами.",
                "Города запирают ворота и не пускают никого.",
                "Лекари бегут первыми, за ними — стража.",
                "Целые деревни находят через год, и находят одни кости."),
        weight=2.4,
    ),
    CalamitySpec(
        key="earthquake", kind=NATURAL, title="Землетрясение",
        noun=("Землетрясение", "n"),
        severities=_s((1, 4.0), (2, 3.0), (3, 1.2)),
        duration=(1, 1), duration_scale=1.3, toll=1.1,
        terrains=("горы", "холмы", "побережье", "подземья", "острова"),
        resolutions=_s(("endured", 5.0),),
        relics=_s(("разлом в земле", 1.0), ("руины", 0.8)),
        adjectives=NATURAL_ADJECTIVES,
        flavor=("Земля идёт волнами, и каменные дома складываются внутрь.",
                "Колодцы мутнеют за три дня до первого толчка.",
                "Целые улицы уходят под землю."),
        weight=1.8,
    ),
    CalamitySpec(
        key="eruption", kind=NATURAL, title="Извержение",
        noun=("Извержение", "n"),
        severities=_s((2, 4.0), (3, 2.5), (4, 1.0)),
        duration=(1, 2), duration_scale=1.4, toll=1.2,
        terrains=("горы", "острова"),
        resolutions=_s(("endured", 5.0),),
        relics=_s(("пепельная пустошь", 1.2), ("новый остров", 0.4)),
        spawns=_s(("volcanic_winter", 0.55),),
        adjectives=("Великое", "Чёрное", "Багровое", "Огненное"),
        flavor=("Гора раскрывается, и небо становится рыжим.",
                "Пепел ложится на поля слоем в ладонь.",
                "Река огня доходит до самого моря и кипятит его."),
        weight=1.4,
    ),
    CalamitySpec(
        key="storm_years", kind=NATURAL, title="Годы бурь", noun=("Буря", "f"),
        severities=_s((1, 4.0), (2, 2.5)),
        duration=(3, 8), duration_scale=1.5, toll=0.7,
        terrains=("побережье", "острова", "тундра"),
        resolutions=_s(("rains", 3.0), ("endured", 4.0)),
        relics=_s(("разбитый флот", 0.8),),
        adjectives=("Долгий", "Злой", "Солёный", "Серый"),
        flavor=("Ни одна лодка не выходит в море три года подряд.",
                "Ветер срывает крыши и уносит их за версту.",
                "Рыба уходит, и берег голодает."),
        weight=1.5,
    ),
    CalamitySpec(
        key="locust", kind=NATURAL, title="Нашествие саранчи",
        noun=("Саранча", "f"),
        severities=_s((1, 4.0), (2, 3.0)),
        duration=(1, 4), duration_scale=1.5, toll=0.9,
        terrains=("степь", "равнина", "пустыня"),
        resolutions=_s(("faded", 4.0), ("endured", 3.0)),
        relics=_s(),
        adjectives=("Великая", "Серая", "Голодная", "Бесчисленная"),
        flavor=("Туча идёт с юга и садится на поля, как снег.",
                "После неё не остаётся ни колоса, ни листа.",
                "Саранчу едят, пока не начинают умирать и от неё."),
        weight=1.6,
    ),
    CalamitySpec(
        key="beast_plague", kind=NATURAL, title="Падёж скота",
        noun=("Падёж", "m"),
        severities=_s((1, 5.0), (2, 2.0)),
        duration=(1, 4), duration_scale=1.4, toll=0.6,
        resolutions=_s(("endured", 5.0),),
        relics=_s(),
        adjectives=("Великий", "Чёрный", "Тихий"),
        flavor=("Стада ложатся и не встают.",
                "Пахать становится не на чем, и поле уходит под траву."),
        weight=1.4,
    ),

    # ------------------------------------------------------------------
    # Долгие перемены климата
    # ------------------------------------------------------------------
    CalamitySpec(
        key="glaciation", kind=CLIMATE, title="Наступление ледников",
        noun=("Ледник", "m"),
        severities=_s((3, 3.0), (4, 2.0), (5, 0.6)),
        duration=(30, 70), duration_scale=2.2, toll=0.8,
        scope=(3, 5), scope_scale=1.5,
        resolutions=_s(("adapted", 4.0), ("endured", 2.0)),
        relics=_s(("ледяная пустошь", 1.2), ("вмёрзший город", 0.6)),
        adjectives=("Великий", "Долгий", "Белый", "Немой"),
        flavor=("Лето перестаёт приходить: снег лежит и в месяце Травень.",
                "Северные земли пустеют, народы идут на юг и упираются в чужие границы.",
                "Лёд ползёт по долинам медленнее человека, но не останавливается."),
        weight=0.5, era_range=(1, 4),
    ),
    CalamitySpec(
        key="long_warming", kind=CLIMATE, title="Долгое потепление",
        noun=("Зной", "m"),
        severities=_s((3, 3.0), (4, 1.5)),
        duration=(40, 90), duration_scale=2.0, toll=0.7,
        scope=(3, 5), scope_scale=1.5,
        resolutions=_s(("adapted", 5.0),),
        relics=_s(("наступающая пустыня", 1.2), ("высохшее море", 0.5)),
        adjectives=("Великий", "Долгий", "Медный", "Сухой"),
        flavor=("Зимы становятся тёплыми, а лето — нестерпимым.",
                "Пески идут на север и заносят межи.",
                "Там, где пасли стада, теперь солончак."),
        weight=0.5, era_range=(1, 4),
    ),
    CalamitySpec(
        key="volcanic_winter", kind=CLIMATE, title="Вулканическая зима",
        noun=("Зима", "f"),
        severities=_s((3, 3.0), (4, 2.5), (5, 1.0)),
        duration=(5, 15), duration_scale=2.4, toll=1.4,
        scope=(4, 8), scope_scale=1.4,
        resolutions=_s(("adapted", 3.0), ("endured", 4.0)),
        relics=_s(("год без солнца в памяти", 1.0),),
        adjectives=("Долгая", "Серая", "Пепельная", "Немая"),
        flavor=("Солнце висит бледным пятном и не греет.",
                "Урожая нет три года подряд, потом ещё три.",
                "Снег идёт летом и пахнет гарью."),
        weight=0.35, era_range=(0, 4),
    ),
    CalamitySpec(
        key="sea_rise", kind=CLIMATE, title="Наступление моря",
        noun=("Прилив", "m"),
        severities=_s((2, 3.0), (3, 2.0), (4, 0.8)),
        duration=(20, 60), duration_scale=2.0, toll=0.8,
        terrains=("побережье", "острова", "болото"),
        scope=(2, 4),
        resolutions=_s(("adapted", 4.0), ("endured", 2.0)),
        relics=_s(("затонувший город", 1.2),),
        adjectives=("Долгий", "Солёный", "Тихий", "Жадный"),
        flavor=("Вода поднимается на ладонь в год, и это замечают не сразу.",
                "Порты приходится переносить выше, потом ещё выше.",
                "Старые улицы стоят по колено в море."),
        weight=0.4,
    ),

    # ------------------------------------------------------------------
    # Вторжения
    # ------------------------------------------------------------------
    CalamitySpec(
        key="demon_invasion", kind=INVASION, title="Вторжение демонов",
        noun=("Нашествие", "n"), race_id="demon",
        severities=_s((3, 3.0), (4, 2.5), (5, 1.2)),
        duration=(3, 9), duration_scale=2.6, toll=1.5,
        scope=(2, 3), scope_scale=1.7,
        generals=(2, 5),
        host_words=("Легион", "Орда", "Воинство", "Полчище"),
        resolutions=_s(("hero", 2.2), ("heroes", 2.5), ("coalition", 2.5),
                       ("sealed", 2.0), ("driven_back", 1.2), ("burned_out", 0.6)),
        relics=_s(("печать", 1.6), ("недобитый военачальник", 1.2),
                  ("разлом", 1.0), ("проклятое место", 1.0)),
        adjectives=("Багровый", "Пепельный", "Медный", "Жгучий", "Чёрный"),
        spawns=_s(("plague", 0.3), ("wild_magic", 0.25)),
        flavor=("Небо над землёй идёт трещинами, и в трещины лезут.",
                "Города горят изнутри — огонь не тушится водой.",
                "Пленных не берут, и это милосерднее того, что делают с пленными.",
                "Там, где прошёл легион, земля родит только серу."),
        weight=1.0, era_range=(1, 4),
    ),
    CalamitySpec(
        key="dragon_flight", kind=INVASION, title="Драконье нашествие",
        noun=("Нашествие", "n"), race_id="dragon",
        severities=_s((2, 2.0), (3, 3.0), (4, 2.0), (5, 0.5)),
        duration=(2, 8), duration_scale=2.4, toll=1.2,
        scope=(2, 3), scope_scale=1.6,
        generals=(1, 4),
        host_words=("Выводок", "Стая", "Крыло"),
        resolutions=_s(("hero", 3.0), ("heroes", 2.2), ("tribute", 1.8),
                       ("coalition", 1.5), ("driven_back", 1.0), ("faded", 0.8)),
        relics=_s(("драконье логово", 1.8), ("кладка яиц", 1.2),
                  ("уцелевший дракон", 1.4), ("клад", 1.0)),
        adjectives=("Золотой", "Багряный", "Обсидиановый", "Пепельный", "Древний"),
        flavor=("Тень накрывает поле, и поле начинает гореть.",
                "Стада уводят в пещеры, но это не помогает.",
                "Башни плавятся и текут, как свечи.",
                "Дань золотом собирают со всех, у кого оно есть."),
        weight=1.0, era_range=(0, 4),
    ),
    CalamitySpec(
        key="undead_tide", kind=INVASION, title="Нашествие нежити",
        noun=("Нашествие", "n"), race_id="undead",
        severities=_s((3, 3.0), (4, 2.2), (5, 0.9)),
        duration=(4, 12), duration_scale=2.5, toll=1.4,
        scope=(2, 4), scope_scale=1.6,
        generals=(2, 5),
        host_words=("Воинство", "Легион", "Полчище"),
        resolutions=_s(("heroes", 2.5), ("hero", 2.0), ("coalition", 2.2),
                       ("sealed", 2.5), ("burned_out", 0.5)),
        relics=_s(("гробница", 1.8), ("печать", 1.4), ("проклятое поле", 1.2),
                  ("недобитый военачальник", 1.0)),
        adjectives=("Костяной", "Бледный", "Тихий", "Холодный", "Серый"),
        spawns=_s(("plague", 0.35),),
        flavor=("Мёртвые встают на второй день после похорон и идут на юг.",
                "Кладбища вскрываются сами, изнутри.",
                "Войско не спит, не ест и не отступает.",
                "Убитые защитники наутро оказываются в чужих рядах."),
        weight=1.0, era_range=(1, 4),
    ),
    CalamitySpec(
        key="deep_ones", kind=INVASION, title="Восстание глубоководных",
        noun=("Восстание", "n"), race_id="deep_one",
        severities=_s((2, 3.0), (3, 3.0), (4, 1.5)),
        duration=(5, 14), duration_scale=2.4, toll=1.1,
        scope=(2, 3), scope_scale=1.5,
        terrains=("побережье", "острова", "болото"),
        generals=(1, 4),
        host_words=("Воинство", "Косяк", "Полчище"),
        resolutions=_s(("heroes", 2.2), ("coalition", 2.0), ("sealed", 2.2),
                       ("driven_back", 2.0), ("tribute", 1.0), ("faded", 1.0)),
        relics=_s(("затонувший храм", 1.6), ("проклятая бухта", 1.2),
                  ("уцелевший жрец", 1.0)),
        adjectives=("Солёный", "Придонный", "Слепой", "Ледяной", "Немой"),
        flavor=("Море отступает на версту, а потом возвращается не водой.",
                "Прибрежные деревни находят пустыми, с распахнутыми дверями.",
                "По ночам с берега слышно пение, и слушать его нельзя.",
                "Рыбаки возвращаются другими — и их приходится жечь."),
        weight=0.9,
    ),
    CalamitySpec(
        key="hellish_swarm", kind=INVASION, title="Рой адских насекомых",
        noun=("Рой", "m"), race_id="swarm",
        severities=_s((2, 3.0), (3, 3.0), (4, 1.2)),
        duration=(3, 10), duration_scale=2.3, toll=1.3,
        scope=(2, 4), scope_scale=1.7,
        generals=(1, 3),
        host_words=("Рой", "Туча", "Гнездо"),
        resolutions=_s(("faded", 2.2), ("heroes", 2.0), ("coalition", 2.0),
                       ("burned_out", 1.2), ("hero", 1.5), ("driven_back", 1.0)),
        relics=_s(("кладка", 1.8), ("выеденные земли", 1.2),
                  ("спящая матка", 1.4)),
        adjectives=("Хитиновый", "Чёрный", "Голодный", "Жужжащий", "Бесчисленный"),
        spawns=_s(("crop_failure_echo", 0.0),),
        flavor=("Туча закрывает солнце и гудит так, что не слышно крика.",
                "Они едят не только зерно.",
                "Кладки находят в стенах домов, в колодцах, в людях.",
                "Огонь помогает, но огня не хватает."),
        weight=0.9, era_range=(1, 4),
    ),
    CalamitySpec(
        key="void_incursion", kind=INVASION, title="Прорыв Пустоты",
        noun=("Прорыв", "m"), race_id="void",
        severities=_s((3, 2.5), (4, 2.5), (5, 1.5)),
        duration=(3, 10), duration_scale=2.5, toll=1.5,
        scope=(2, 3), scope_scale=1.7,
        generals=(1, 4),
        host_words=("Скопище", "Полчище", "Стая"),
        resolutions=_s(("sealed", 3.0), ("heroes", 2.2), ("dispersed", 2.0),
                       ("coalition", 1.5), ("hero", 1.2), ("burned_out", 0.8)),
        relics=_s(("прореха", 1.8), ("мёртвая зона", 1.4), ("печать", 1.2),
                  ("изменённые земли", 1.0)),
        adjectives=("Тусклый", "Неправильный", "Беззвучный", "Изнаночный"),
        spawns=_s(("wild_magic", 0.4),),
        flavor=("В воздухе появляется шов, и шов расходится.",
                "То, что выходит, не имеет ни имени, ни правильной формы.",
                "Люди, посмотревшие в прореху, перестают быть людьми.",
                "Земля вокруг теряет цвет и больше его не возвращает."),
        weight=0.7, era_range=(1, 4),
    ),
    CalamitySpec(
        key="beast_tide", kind=INVASION, title="Нашествие чудовищ",
        noun=("Нашествие", "n"), race_id="",
        severities=_s((2, 4.0), (3, 2.0)),
        duration=(2, 7), duration_scale=2.0, toll=0.9,
        scope=(1, 3), scope_scale=1.5,
        resolutions=_s(("heroes", 2.5), ("hero", 2.5), ("faded", 2.0),
                       ("suppressed", 1.5)),
        relics=_s(("логово", 1.4), ("уцелевшая тварь", 1.0)),
        adjectives=("Дикий", "Голодный", "Ночной", "Серый"),
        flavor=("Твари выходят из глухих мест разом, будто их что-то выгнало.",
                "Дороги становятся непроезжими после заката.",
                "Охотники уходят и не возвращаются."),
        weight=1.2,
    ),

    # ------------------------------------------------------------------
    # Политические катастрофы
    # ------------------------------------------------------------------
    CalamitySpec(
        key="empire_collapse", kind=POLITICAL, title="Распад державы",
        noun=("Распад", "m"),
        severities=_s((2, 3.0), (3, 3.0), (4, 1.2)),
        duration=(2, 6), duration_scale=1.7, toll=0.5,
        scope=(1, 2), scope_scale=1.4,
        needs_polity=True,
        resolutions=_s(("shattered", 4.0), ("reunited", 1.2)),
        relics=_s(("осколок державы", 1.4), ("обида наследников", 1.0)),
        adjectives=("Великий", "Долгий", "Горький"),
        flavor=("Наместники перестают слать подати и начинают чеканить свою монету.",
                "Каждый город вспоминает, что когда-то был сам по себе.",
                "Границы перерисовывают трижды за десять лет."),
        weight=1.3, era_range=(2, 4),
    ),
    CalamitySpec(
        key="feudal_fracture", kind=POLITICAL, title="Феодальная раздробленность",
        noun=("Раздробленность", "f"),
        severities=_s((1, 3.0), (2, 3.0), (3, 1.5)),
        duration=(10, 40), duration_scale=1.8, toll=0.45,
        scope=(1, 2), scope_scale=1.3,
        needs_polity=True,
        resolutions=_s(("reunited", 2.5), ("shattered", 2.5), ("endured", 1.0)),
        relics=_s(("вольный город", 1.2), ("старые притязания", 1.0)),
        adjectives=("Долгая", "Горькая", "Тихая"),
        flavor=("Знать перестаёт слушать столицу, но не перестаёт собирать подати.",
                "Дороги между владениями становятся опасными.",
                "Каждый барон судит по своему обычаю."),
        weight=1.4, era_range=(2, 4),
    ),
    CalamitySpec(
        key="tribal_conquest", kind=POLITICAL, title="Нашествие племён",
        noun=("Нашествие", "n"),
        severities=_s((2, 3.0), (3, 2.5), (4, 1.0)),
        duration=(3, 10), duration_scale=1.9, toll=1.0,
        scope=(1, 3), scope_scale=1.5,
        needs_polity=True,
        resolutions=_s(("absorbed", 2.5), ("suppressed", 2.0), ("coalition", 1.5),
                       ("tribute", 1.2), ("shattered", 1.0)),
        relics=_s(("новая знать", 1.2), ("выжженный предел", 1.0)),
        adjectives=("Великое", "Дикое", "Голодное"),
        flavor=("Те, у кого нет ни городов, ни законов, приходят за тем и другим.",
                "Пограничные крепости падают одна за другой.",
                "Оседлые вспоминают, что когда-то и сами кочевали."),
        weight=1.3, era_range=(1, 4),
    ),
    CalamitySpec(
        key="succession_war", kind=POLITICAL, title="Война за наследство",
        noun=("Война", "f"),
        severities=_s((2, 3.0), (3, 2.0)),
        duration=(3, 12), duration_scale=1.7, toll=0.8,
        scope=(1, 2), scope_scale=1.3,
        needs_polity=True,
        resolutions=_s(("suppressed", 2.5), ("shattered", 1.5), ("reunited", 2.0)),
        relics=_s(("оспоренный престол", 1.2),),
        adjectives=("Долгая", "Кровавая", "Горькая", "Великая"),
        flavor=("Две родни выводят дружины и зовут одно и то же право.",
                "Города берут и сдают по три раза.",
                "Знать делится надвое, и обе половины клянутся в верности."),
        weight=1.1, era_range=(2, 4),
    ),
    CalamitySpec(
        key="great_revolt", kind=POLITICAL, title="Великое восстание",
        noun=("Восстание", "n"),
        severities=_s((1, 3.0), (2, 3.0), (3, 1.2)),
        duration=(2, 8), duration_scale=1.6, toll=0.7,
        needs_polity=True,
        resolutions=_s(("suppressed", 3.0), ("shattered", 1.2), ("reunited", 1.0)),
        relics=_s(("память о бунте", 1.0),),
        adjectives=("Великое", "Голодное", "Чёрное"),
        flavor=("Подати поднимают в третий раз за десять лет, и терпение кончается.",
                "Усадьбы горят, а амбары открывают.",
                "Вожака восстания знают по имени во всех тавернах."),
        weight=1.0, era_range=(2, 4),
    ),

    # ------------------------------------------------------------------
    # Магические катаклизмы
    # ------------------------------------------------------------------
    CalamitySpec(
        key="mana_storm", kind=MAGIC, title="Магическая буря",
        noun=("Буря", "f"),
        severities=_s((2, 3.0), (3, 2.5), (4, 1.0)),
        duration=(1, 4), duration_scale=2.0, toll=1.0,
        scope=(1, 3), scope_scale=1.6,
        resolutions=_s(("dispersed", 3.0), ("faded", 2.5), ("sealed", 1.5)),
        relics=_s(("мёртвая зона", 1.4), ("изменённые земли", 1.2),
                  ("осколок бури", 1.0)),
        adjectives=("Дикая", "Багровая", "Беззвучная", "Великая"),
        flavor=("Заклинания перестают слушаться и делают не то, что велено.",
                "Камень течёт, вода горит, тени отстают от хозяев.",
                "Башни чародеев рушатся первыми."),
        weight=0.9, era_range=(1, 4),
    ),
    CalamitySpec(
        key="planar_rift", kind=MAGIC, title="Разлом иных пределов",
        noun=("Разлом", "m"),
        severities=_s((3, 3.0), (4, 2.0), (5, 0.7)),
        duration=(2, 8), duration_scale=2.3, toll=1.3,
        scope=(1, 3), scope_scale=1.6,
        resolutions=_s(("sealed", 3.5), ("dispersed", 2.0), ("heroes", 2.0),
                       ("burned_out", 0.8)),
        relics=_s(("прореха", 1.8), ("печать", 1.5), ("проклятое место", 1.2)),
        spawns=_s(("void_incursion", 0.3), ("demon_invasion", 0.2)),
        adjectives=("Великий", "Тусклый", "Багровый", "Неправильный"),
        flavor=("Небо расходится по шву, и из шва тянет холодом.",
                "Через разлом идёт то, чему здесь не место.",
                "Чародеи закрывают его собой — и не возвращаются."),
        weight=0.7, era_range=(1, 4),
    ),
    CalamitySpec(
        key="great_curse", kind=MAGIC, title="Великое проклятие",
        noun=("Проклятие", "n"),
        severities=_s((2, 3.0), (3, 2.5), (4, 0.8)),
        duration=(5, 20), duration_scale=1.9, toll=0.9,
        scope=(1, 2), scope_scale=1.4,
        resolutions=_s(("dispersed", 2.5), ("heroes", 2.2), ("sealed", 1.5),
                       ("endured", 1.5)),
        relics=_s(("проклятое место", 1.6), ("проклятый род", 1.2)),
        adjectives=("Великое", "Тихое", "Чёрное", "Родовое"),
        flavor=("Дети рождаются мёртвыми, а скот — двухголовым.",
                "Слово, сказанное над городом, работает лучше осадных машин.",
                "Снять проклятие берутся многие; возвращаются немногие."),
        weight=0.8, era_range=(1, 4),
    ),
    CalamitySpec(
        key="mage_war", kind=MAGIC, title="Война чародеев",
        noun=("Война", "f"),
        severities=_s((2, 3.0), (3, 2.5), (4, 1.0)),
        duration=(3, 12), duration_scale=1.9, toll=1.1,
        scope=(2, 3), scope_scale=1.5,
        resolutions=_s(("dispersed", 2.5), ("suppressed", 2.0), ("heroes", 1.8),
                       ("burned_out", 1.2)),
        relics=_s(("мёртвая зона", 1.4), ("башня без хозяина", 1.2),
                  ("опасная реликвия", 1.4)),
        adjectives=("Долгая", "Багровая", "Тихая", "Великая"),
        flavor=("Две школы спорят о природе силы, и спор выходит за стены.",
                "Города достаются тем, кто в споре не участвовал.",
                "После победителей приходится разбирать и победителей."),
        weight=0.8, era_range=(2, 4),
    ),
    CalamitySpec(
        key="wild_magic", kind=MAGIC, title="Всплеск дикой магии",
        noun=("Всплеск", "m"),
        severities=_s((1, 4.0), (2, 3.0), (3, 1.0)),
        duration=(1, 5), duration_scale=1.7, toll=0.7,
        scope=(1, 2),
        resolutions=_s(("faded", 3.0), ("dispersed", 2.5), ("endured", 1.5)),
        relics=_s(("изменённые земли", 1.4), ("говорящий зверь", 0.8)),
        adjectives=("Дикий", "Пёстрый", "Беззвучный"),
        flavor=("Звери начинают говорить, и говорят неприятное.",
                "Урожай всходит за ночь и гниёт к утру.",
                "Каждый третий ребёнок этого года рождается с даром."),
        weight=1.0, era_range=(1, 4),
    ),
)


# --- великие бедствия, меняющие сам мир ---------------------------------
# Эти четыре беды тем и отличаются от прочих, что после них мир уже не
# тот: земля уходит под воду, суша раскалывается, солнце меркнет над
# всеми разом, а из глубины поднимается то, что не добили в прошлый раз.
GREAT_SPECS = (
    CalamitySpec(
        key="drowning", kind=NATURAL, title="Погружение",
        noun=("Погружение", "n"),
        severities=_s((4, 2.0), (5, 1.0)),
        duration=(1, 2), duration_scale=1.2, toll=1.9,
        scope=(1, 2), scope_scale=1.15,
        terrains=("побережье", "острова"),
        resolutions=_s(("endured", 3.0), ("adapted", 1.0)),
        relics=_s(("затонувший город", 2.0), ("проклятое место", 0.6)),
        adjectives=("Великое", "Чёрное", "Тихое", "Последнее"),
        flavor=("Море приходит за одну ночь и больше не уходит.",
                "Спасаются те, кто был в море; тем, кто был дома, не спастись.",
                "Колокол затонувшего храма, говорят, слышно и теперь.",
                "Уцелевшие уплывают на всём, что держится на воде."),
        weight=0.28, era_range=(1, 4),
    ),
    CalamitySpec(
        key="sundering", kind=NATURAL, title="Раскол суши",
        noun=("Раскол", "m"),
        severities=_s((4, 2.0), (5, 1.2)),
        duration=(1, 3), duration_scale=1.4, toll=1.4,
        scope=(2, 3), scope_scale=1.2,
        terrains=("горы", "холмы", "равнина", "побережье"),
        resolutions=_s(("endured", 3.0), ("adapted", 1.5)),
        relics=_s(("разлом", 1.8), ("проклятое место", 0.8)),
        adjectives=("Великий", "Чёрный", "Долгий", "Первый"),
        flavor=("Земля идёт трещиной от края до края, и трещина не закрывается.",
                "Там, где был перешеек, встаёт пролив, и по нему уже ходят "
                "корабли.",
                "Деревни по обе стороны разлома с этого дня — разные народы.",
                "Дороги обрываются в пустоту, и караваны идут в обход триста лет."),
        weight=0.25, era_range=(1, 4),
    ),
    CalamitySpec(
        key="long_dark", kind=CLIMATE, title="Долгая Тьма",
        noun=("Тьма", "f"),
        severities=_s((4, 2.0), (5, 1.4)),
        duration=(8, 25), duration_scale=1.8, toll=1.5,
        scope=(12, 20), scope_scale=1.6,
        resolutions=_s(("endured", 3.0), ("adapted", 2.0),
                       ("dispersed", 1.0), ("heroes", 1.2)),
        relics=_s(("год без солнца в памяти", 1.6), ("проклятое место", 0.6)),
        adjectives=("Долгая", "Великая", "Немая", "Первая", "Беззвёздная"),
        flavor=("Солнце меркнет и не светит: день теперь отличается от ночи "
                "только тем, что чуть серее.",
                "Хлеб не родится нигде — ни на юге, ни на севере.",
                "Это первая беда, которая пришла ко всем разом: спрятаться "
                "от неё негде.",
                "Народы, у которых не было запасов, не переживают её вовсе."),
        weight=0.22, era_range=(0, 4), worldwide=True,
    ),
    CalamitySpec(
        key="deep_waking", kind=INVASION, title="Пробуждение в глубине",
        noun=("Пробуждение", "n"), race_id="demon",
        severities=_s((3, 2.0), (4, 2.4), (5, 1.0)),
        duration=(2, 6), duration_scale=2.2, toll=1.6,
        scope=(1, 2), scope_scale=1.4,
        terrains=("горы", "подземья"),
        generals=(0, 2),
        host_words=("Выводок", "Тень", "Голод", "Сонм"),
        resolutions=_s(("sealed", 3.0), ("heroes", 2.0), ("hero", 1.2),
                       ("driven_back", 1.0), ("burned_out", 0.8)),
        relics=_s(("запечатанный чертог", 2.2), ("печать", 1.4),
                  ("недобитый военачальник", 0.8)),
        adjectives=("Глубинный", "Древний", "Чёрный", "Забытый"),
        flavor=("Копали слишком глубоко и достучались до того, что там спало.",
                "Это не новое зло, а остаток старого: то, что не добили в "
                "прошлый раз.",
                "Великий чертог пустеет за один сезон и стоит пустым века.",
                "Уходя, жители запечатывают ворота — и просят потомков их "
                "не открывать."),
        weight=0.3, era_range=(1, 4), from_relic_only=True,
    ),
)

CATALOG = CATALOG + GREAT_SPECS

# Эти две беды не выпадают сами: их начинает система веры.
RELIGIOUS_SPECS = (
    CalamitySpec(
        key="crusade", kind=RELIGIOUS, title="Священный поход",
        noun=("Поход", "m"),
        severities=_s((2, 3.0), (3, 2.5), (4, 1.0)),
        duration=(3, 9), duration_scale=1.9, toll=1.0,
        scope=(2, 3), scope_scale=1.5,
        resolutions=_s(("suppressed", 3.0), ("endured", 1.5), ("shattered", 1.2),
                       ("heroes", 1.5), ("absorbed", 1.0)),
        relics=_s(("выжженное капище", 1.4), ("память о мучениках", 1.2),
                  ("спорная земля", 1.0)),
        adjectives=("Священный", "Великий", "Багровый", "Праведный"),
        flavor=("Знамёна с чужим знаком идут на земли, где молятся иначе.",
                "Тех, кто отрёкся вовремя, щадят. Остальных — нет.",
                "Капища жгут вместе с теми, кто в них укрылся.",
                "Поход объявляют угодным богам, и спорить с этим опасно."),
        weight=0.0, era_range=(2, 4),
    ),
    CalamitySpec(
        key="holy_war", kind=RELIGIOUS, title="Война за веру",
        noun=("Война", "f"),
        severities=_s((2, 3.0), (3, 2.5), (4, 1.2)),
        duration=(5, 14), duration_scale=1.9, toll=1.0,
        scope=(2, 4), scope_scale=1.5,
        resolutions=_s(("suppressed", 2.0), ("shattered", 2.0), ("endured", 2.0),
                       ("coalition", 1.5), ("absorbed", 1.2)),
        relics=_s(("спорная земля", 1.4), ("память о мучениках", 1.2),
                  ("разорённый храм", 1.2)),
        adjectives=("Долгая", "Багровая", "Великая", "Братская"),
        flavor=("Две веры перестают спорить словами.",
                "Города переходят из рук в руки вместе с обрядами.",
                "Соседи, ходившие в один храм, режут друг друга за то, "
                "как именно в нём молиться.",
                "Мира не заключают: заключают перемирие до следующего повода."),
        weight=0.0, era_range=(2, 4),
    ),
)

CATALOG = CATALOG + RELIGIOUS_SPECS

CATALOG_BY_KEY = {spec.key: spec for spec in CATALOG}


def specs_for_kind(kind: str) -> tuple:
    return tuple(spec for spec in CATALOG if spec.kind == kind)


def get_spec(key: str) -> CalamitySpec:
    return CATALOG_BY_KEY[key]
