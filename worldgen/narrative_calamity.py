# -*- coding: utf-8 -*-
"""Тексты бедствий: приход беды, сражения, конец, тёмные века и следы.

Правила прежние: имена в именительном падеже, глаголы настоящего времени,
никаких причастий, которые пришлось бы согласовывать с придуманным словом.
"""

from __future__ import annotations

from .catastrophe import INVASION, KIND_NAMES, SEVERITY_NAMES
from .morph import genitive_phrase, phrase
from .narrative import cap
from .timeline import plural, years_text


# ---------------------------------------------------------------------------
# Мелкие помощники
# ---------------------------------------------------------------------------

def number(value) -> str:
    """1240000 -> «1 240 000»."""
    text = "%d" % int(value)
    groups = []
    while len(text) > 3:
        groups.insert(0, text[-3:])
        text = text[:-3]
    groups.insert(0, text)
    return " ".join(groups)


def souls(value) -> str:
    value = int(value)
    return "%s %s" % (number(value), plural(value, "душа", "души", "душ"))


def _rough(value: int) -> str:
    """«несколько миллионов», «сотни тысяч» — на глаз, как в летописи."""
    value = int(value)
    if value >= 3000000:
        return "миллионы"
    if value >= 1000000:
        return "несколько миллионов"
    if value >= 300000:
        return "сотни тысяч"
    if value >= 100000:
        return "многие десятки тысяч"
    if value >= 20000:
        return "десятки тысяч"
    if value >= 3000:
        return "тысячи"
    return "сотни"


def region_list(world, region_ids, limit: int = 4) -> str:
    names = []
    for region_id in region_ids[:limit]:
        region = world.regions.get(region_id)
        if region is not None:
            names.append(region.name)
    if not names:
        return "неизвестные земли"
    rest = len(region_ids) - len(names)
    text = ", ".join(names)
    if rest > 0:
        text += " и ещё %d %s" % (rest, plural(rest, "земля", "земли", "земель"))
    return text


def with_title(figure) -> str:
    if figure is None:
        return "неизвестный"
    if figure.titles:
        return "%s %s" % (figure.titles[0].lower(), figure.name)
    return figure.name


def host_phrase(calamity) -> str:
    return calamity.notes[0] if calamity.notes else calamity.name


# ---------------------------------------------------------------------------
# Имя бедствия
# ---------------------------------------------------------------------------

def make_host(rng, spec, style_adjectives) -> tuple:
    """Имя вражьего войска: («Пепельный», «Легион», род)."""
    words = spec.host_words or ("Воинство",)
    noun = rng.choice(words)
    gender = "n" if noun in ("Воинство", "Полчище", "Скопище", "Гнездо") else \
             ("f" if noun in ("Стая", "Орда", "Туча", "Тень", "Тьма",
                              "Пасть", "Погибель", "Свора") else "m")
    adjectives = spec.adjectives or style_adjectives or ("Чёрный",)
    return rng.choice(adjectives), noun, gender


# У каждого вида беды свои четыре-пять прилагательных, и на десять миров
# этого не хватало: «Долгая Война» выпадала в каждом. Свои остаются
# главными — они про суть беды, — но к ним подмешивается общий запас.
# Все формы мужские: род подбирается под слово беды сам.
COMMON_ADJECTIVES = (
    "Великий", "Чёрный", "Долгий", "Тихий", "Багровый", "Горький",
    "Серый", "Немой", "Холодный", "Жестокий", "Страшный", "Проклятый",
    "Голодный", "Дикий", "Медный", "Ржавый", "Мутный", "Глухой",
    "Слепой", "Пёстрый", "Бледный", "Жгучий", "Костяной", "Пепельный",
    "Смутный", "Лютый", "Сухой", "Мёрзлый", "Тяжёлый", "Последний",
    "Безымянный", "Гиблый", "Тусклый", "Злой", "Нечистый", "Полынный",
    "Волчий", "Соляной", "Свинцовый", "Кривой", "Дымный", "Осиный",
)


def calamity_adjective(rng, spec) -> str:
    """Прилагательное для имени беды: сперва своё, иначе из общего запаса."""
    own = spec.adjectives or ()
    pairs = [(word, 3.0) for word in own]
    pairs += [(word, 1.0) for word in COMMON_ADJECTIVES if word not in own]
    return rng.weighted(pairs) if pairs else "Великий"


def calamity_name(rng, spec, host=None, polity=None) -> str:
    if spec.kind == INVASION and host is not None:
        adj, noun, gender = host
        return "%s %s" % (spec.noun[0], genitive_phrase(adj, noun, gender))
    if polity is not None:
        return "%s %s" % (spec.noun[0], polity_gen(polity))
    return phrase(calamity_adjective(rng, spec), spec.noun[0], spec.noun[1])


def polity_gen(polity) -> str:
    from .narrative_dynasty import polity_gen as _gen
    return _gen(polity)


# Порядковые по родам: летопись так и нумерует повторившуюся беду —
# «Вторая Великая Война», «Третий Чёрный Мор».
ORDINALS = {
    "m": ("", "Второй", "Третий", "Четвёртый", "Пятый", "Шестой", "Седьмой",
          "Восьмой", "Девятый"),
    "f": ("", "Вторая", "Третья", "Четвёртая", "Пятая", "Шестая", "Седьмая",
          "Восьмая", "Девятая"),
    "n": ("", "Второе", "Третье", "Четвёртое", "Пятое", "Шестое", "Седьмое",
          "Восьмое", "Девятое"),
}


def unique_calamity_name(name: str, gender: str, taken) -> str:
    """Если такая беда уже была, летопись нумерует новую по счёту."""
    if name not in taken:
        return name
    forms = ORDINALS.get(gender or "m", ORDINALS["m"])
    for index in range(1, len(forms)):
        candidate = "%s %s" % (forms[index], name)
        if candidate not in taken:
            return candidate
    index = len(forms)
    while "%s (%d)" % (name, index) in taken:
        index += 1
    return "%s (%d)" % (name, index)


# ---------------------------------------------------------------------------
# Приход беды
# ---------------------------------------------------------------------------

NATURAL_OPENINGS = (
    "Беда приходит тихо и не сразу получает имя.",
    "Сперва это принимают за обычный дурной год.",
    "Старики говорят, что такое уже бывало; старики ошибаются.",
    "Год начинается как всякий другой и кончается не как всякий другой.",
    "Знамения были, но их, как всегда, толковали неверно.",
)

INVASION_OPENINGS = (
    "Мир узнаёт, что он не один.",
    "Границы, которые считали надёжными, оказываются линиями на карте.",
    "Первыми гибнут те, кто не поверил гонцам.",
    "Известие идёт медленнее беды.",
    "Дозорные жгут костры всю ночь, но жечь их уже некому.",
)

POLITICAL_OPENINGS = (
    "Держава трещит не снаружи, а изнутри.",
    "Всё держалось на одном имени, и имени не стало.",
    "Никто не собирался этого делать; так вышло.",
    "Сперва это называют недоразумением, потом — войной.",
)

MAGIC_OPENINGS = (
    "Сила, которой пользовались веками, ведёт себя иначе.",
    "Первыми чувствуют звери, потом дети, потом все остальные.",
    "Чародеи спорят о причинах, пока спорить становится не о чем.",
)

CLIMATE_OPENINGS = (
    "Перемену замечают не сразу: она приходит на срок человеческой жизни.",
    "Сперва это списывают на пару неудачных лет.",
    "Летописец сравнивает записи столетней давности и хватается за голову.",
)

OPENINGS = {
    "natural": NATURAL_OPENINGS,
    "invasion": INVASION_OPENINGS,
    "political": POLITICAL_OPENINGS,
    "magic": MAGIC_OPENINGS,
    "climate": CLIMATE_OPENINGS,
}


def begins(rng, world, calamity, spec, leader, generals, victim_polity=None):
    parts = [rng.choice(OPENINGS.get(spec.kind, NATURAL_OPENINGS))]

    if spec.kind == INVASION and leader is not None:
        host = host_phrase(calamity)
        parts.append("%s ведёт %s." % (cap(host), with_title(leader)))
        if generals:
            names = ", ".join(figure.name for figure in generals[:4])
            parts.append("При нём военачальники: %s." % names)
    elif victim_polity is not None:
        parts.append("Беда обрушивается на страну: %s." % victim_polity.full_name)

    if calamity.host_size:
        parts.append(rng.choice((
            "Их не меньше %s." % souls(calamity.host_size),
            "Счёт врагов идёт на %s." % _rough(calamity.host_size),
            "Тех, кто пришёл, насчитывают %s." % souls(calamity.host_size),
        )))
    parts.append(rng.choice(spec.flavor) if spec.flavor else "")
    parts.append("Охвачены земли: %s." % region_list(world, calamity.region_ids))
    parts.append("Летописцы назовут это так: %s (%s, %s)." % (
        calamity.name, KIND_NAMES.get(spec.kind, "бедствие"),
        SEVERITY_NAMES.get(calamity.severity, "")))
    return ("%s: %s" % (spec.title, calamity.name),
            cap(" ".join(part for part in parts if part)))


# ---------------------------------------------------------------------------
# Ход бедствия
# ---------------------------------------------------------------------------

ONGOING_TEMPLATES = (
    "%(nth)s год бедствия под именем %(name)s. %(flavor)s",
    "Беда не кончается: идёт %(nth)s год, как %(name)s держит эти земли. %(flavor)s",
    "%(name)s не отступает. %(flavor)s Счёт погибших к этому году — %(dead)s.",
    "Летописец отмечает %(nth)s год беды. %(flavor)s",
)


def ongoing(rng, calamity, spec, year_number: int):
    data = {
        "nth": "%d-й" % year_number,
        "name": calamity.name,
        "flavor": rng.choice(spec.flavor) if spec.flavor else "",
        "dead": souls(calamity.deaths),
    }
    return ("%s продолжается" % calamity.name,
            cap(rng.choice(ONGOING_TEMPLATES) % data))


CITY_LOST_TEMPLATES = (
    "%(city)s не переживает беду: %(name)s не оставляет от него ничего.",
    "%(city)s гибнет. Тех, кто успел уйти, считают счастливцами.",
    "%(name)s стирает с карты %(city_acc)s.",
    "От %(city_gen)s остаются стены и имя, потом только имя.",
    "%(city)s пустеет насовсем: беда по имени %(name)s не оставляет живых.",
)


def city_lost(rng, settlement, calamity):
    from .morph import accusative_noun, genitive_noun
    data = {
        "city": cap(settlement.full_name),
        "city_acc": "%s %s" % (accusative_noun(settlement.kind).lower(),
                               settlement.name),
        "city_gen": "%s %s" % (genitive_noun(settlement.kind).lower(),
                               settlement.name),
        "name": calamity.name,
    }
    return ("Гибель города: %s" % settlement.name,
            cap(rng.choice(CITY_LOST_TEMPLATES) % data))


BATTLE_TEMPLATES_ENEMY = (
    "%(battle)s: войско защитников встречает врага и не удерживает поле. "
    "%(losses)s %(fallen)s",
    "%(battle)s кончается разгромом защитников. %(losses)s %(fallen)s",
    "%(battle)s: строй ломается к полудню. %(losses)s %(fallen)s",
)

BATTLE_TEMPLATES_DEFENDERS = (
    "%(battle)s: враг впервые откатывается назад. %(losses)s %(fallen)s",
    "%(battle)s остаётся за защитниками — дорогой ценой. %(losses)s %(fallen)s",
    "%(battle)s: поле остаётся за живыми. %(losses)s %(fallen)s",
)

DECISIVE_TEMPLATES = (
    "%(battle)s решает всё. %(losses)s %(fallen)s",
    "%(battle)s — та самая битва, которой заканчивают рассказ. %(losses)s %(fallen)s",
)


def battle_text(rng, world, battle, calamity, attacker, defenders):
    names = ", ".join(with_title(figure) for figure in defenders[:3])
    if names:
        head = "Защитников ведут: %s." % names
    else:
        head = "Защитников ведут безымянные сотники."
    fallen = ""
    if battle.fallen_ids:
        dead_names = ", ".join(world.figures[fid].name for fid in battle.fallen_ids
                               if fid in world.figures)
        if dead_names:
            fallen = "Пали: %s." % dead_names
    data = {
        "battle": battle.name,
        "losses": "Полегло %s. %s" % (souls(battle.deaths), head),
        "fallen": fallen,
    }
    if battle.decisive:
        templates = DECISIVE_TEMPLATES
    elif battle.winner == "защитники":
        templates = BATTLE_TEMPLATES_DEFENDERS
    else:
        templates = BATTLE_TEMPLATES_ENEMY
    lead = ""
    if attacker is not None:
        lead = "Врага ведёт %s. " % with_title(attacker)
    return (battle.name, cap(lead + rng.choice(templates) % data))


# ---------------------------------------------------------------------------
# Конец бедствия
# ---------------------------------------------------------------------------

RESOLUTION_TEMPLATES = {
    "hero": (
        "Всё решает один человек: %(hero)s находит врага и убивает его.",
        "%(hero_cap)s идёт туда, откуда не возвращаются, и возвращается — один.",
        "Имя победителя запомнят дольше, чем имя беды: %(hero)s.",
    ),
    "heroes": (
        "Отряд, который потом назовут героями, доходит до конца: %(heroes)s.",
        "Их было немного, и вернулись не все: %(heroes)s.",
        "Вместе они делают то, чего не смогли армии: %(heroes)s.",
    ),
    "coalition": (
        "Страны, враждовавшие век, впервые собирают общее войско. "
        "Во главе — %(commanders)s.",
        "Всемирная коалиция ломает врага в общем поле. Знамёна ведут: %(commanders)s.",
        "Общее войско собирают со всего мира, и во главе его — %(commanders)s.",
    ),
    "sealed": (
        "Беду не убивают — её запирают. Печать ставят ценой жизни те, "
        "кто её ставил: %(heroes)s.",
        "Чародеи и жрецы запечатывают источник беды. Печать держит — пока держит.",
        "Врата закрывают изнутри. Кто закрывал, остаётся с той стороны.",
    ),
    "driven_back": (
        "Врага выталкивают туда, откуда он пришёл, и закладывают дорогу камнем.",
        "Отброшенные уходят за край мира и больше не показываются — пока.",
    ),
    "tribute": (
        "Дело решают не мечом, а золотом: врагу платят, и враг уходит.",
        "Собирают дань со всех, у кого что-то осталось, и беда отступает.",
    ),
    "faded": (
        "Беда уходит сама, насытившись.",
        "Однажды утром обнаруживают, что врага больше нет. Никто не знает почему.",
    ),
    "burned_out": (
        "Беда выжигает всё, до чего дотянулась, и гаснет за ненадобностью.",
        "Врага никто не побеждает: ему просто перестаёт хватать живых.",
    ),
    "endured": (
        "Беду переживают. Это всё, что можно о ней сказать.",
        "Она кончается сама, оставив выживших считать своих.",
    ),
    "rains": (
        "Всё кончается с переменой погоды — так же буднично, как началось.",
        "Приходят дожди, и беда отступает.",
    ),
    "adapted": (
        "Мир приспосабливается: новые земли распахивают, старые бросают.",
        "Перемену перестают считать бедой и начинают считать погодой.",
    ),
    "dispersed": (
        "Чародеи развеивают беду, и половина из них не переживает работу: %(heroes)s.",
        "Круг магов гасит источник. Имена тех, кто держал круг: %(heroes)s.",
    ),
    "reunited": (
        "Страну собирают заново — по кускам и не всю.",
        "Новый правитель приводит отпавшие земли к присяге.",
    ),
    "shattered": (
        "Собрать обратно не удаётся. То, что было одним, остаётся многим.",
        "Держава не возрождается: на её месте теперь несколько имён.",
    ),
    "suppressed": (
        "Мятеж давят силой, и памяти об этом хватает надолго.",
        "Восстание кончается на плахе, и подати остаются прежними.",
    ),
    "absorbed": (
        "Пришедшие оседают, берут себе города и через поколение зовутся местными.",
        "Завоеватели остаются и становятся новой знатью.",
    ),
}


def ends(rng, world, calamity, spec, resolution: str, heroes, commanders):
    lines = []
    templates = RESOLUTION_TEMPLATES.get(resolution, RESOLUTION_TEMPLATES["endured"])
    data = {
        "hero": with_title(heroes[0]) if heroes else "безымянный герой",
        "hero_cap": cap(with_title(heroes[0])) if heroes else "Безымянный герой",
        "heroes": ", ".join(figure.name for figure in heroes[:5]) or "имена их забыты",
        "commanders": ", ".join(with_title(figure) for figure in commanders[:4])
                      or "неизвестные полководцы",
        "commanders_verb": "ведут" if len(commanders) > 1 else "ведёт",
    }
    lines.append(rng.choice(templates) % data)
    lines.append("Беда по имени «%s» держала мир %s." % (
        calamity.name, years_text(max(1, calamity.years))))
    if calamity.host_size:
        lines.append(rng.choice((
            "Врагов было %s; ушли немногие." % souls(calamity.host_size),
            "Их насчитывали %s." % souls(calamity.host_size),
            "Из %s не возвращается почти никто." % souls(calamity.host_size),
        )))
    lines.append(toll_text(world, calamity, rng))
    return ("Конец бедствия: %s" % calamity.name, cap(" ".join(lines)))


# Беда бывает страшной и при малом счёте погибших: если она приходит в
# пустые земли или тянется веками, её работа не в убитых, а в том, что
# земля так и не поднялась. Летопись должна это сказать, иначе
# «апокалиптическое бедствие, погибло 124» читается как ошибка.
EMPTY_TOLL = (
    "Считать оказалось почти некого: беда пришла в земли, где и так никто "
    "не жил.",
    "Счёт погибших вышел малым — но там, где она прошла, после неё долго "
    "никто не селился.",
    "Убитых немного: губить было почти некого.",
)
SLOW_TOLL = (
    "Убитых меньше, чем нерождённых: за эти века земля просто перестала "
    "родить людей.",
    "Счёт погибших мал для такого срока — беда брала не кровью, а тем, что "
    "не давала подняться.",
    "Она убивала медленно и почти незаметно, но после неё эти земли "
    "считали жителей десятками там, где прежде считали тысячами.",
)


def toll_text(world, calamity, rng=None) -> str:
    # Мелкий счёт при большой тяжести — не ошибка, а свойство беды.
    if calamity.severity >= 3 and calamity.deaths < 2000:
        pool = SLOW_TOLL if calamity.years >= 300 else EMPTY_TOLL
        line = (rng.choice(pool) if rng is not None else pool[0])
        if calamity.deaths > 0:
            return "Всего погибло %s. %s" % (souls(calamity.deaths), line)
        return line
    if calamity.deaths <= 0:
        return "Обошлось без большой крови."
    parts = ["Всего погибло %s." % souls(calamity.deaths)]

    by_polity = sorted(calamity.deaths_by_polity.items(),
                       key=lambda pair: (-pair[1], pair[0]))[:4]
    named = []
    for polity_id, dead in by_polity:
        polity = world.polities.get(polity_id)
        if polity is not None and dead > 0:
            named.append("%s — %s" % (polity.full_name, number(dead)))
    if named:
        parts.append("По странам: %s." % "; ".join(named))

    by_race = sorted(calamity.deaths_by_race.items(),
                     key=lambda pair: (-pair[1], pair[0]))[:3]
    race_named = []
    for race_id, dead in by_race:
        from .races import RACES_BY_ID
        race = RACES_BY_ID.get(race_id)
        if race is not None and dead > 0:
            race_named.append("%s — %s" % (race.name.lower(), number(dead)))
    if race_named:
        parts.append("По народам: %s." % "; ".join(race_named))

    if calamity.settlements_lost:
        parts.append("Поселений потеряно: %d." % calamity.settlements_lost)
    if calamity.polities_lost:
        parts.append("Стран не стало: %d." % calamity.polities_lost)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Наложение бедствий и голод
# ---------------------------------------------------------------------------

COMPOUND_TEMPLATES = (
    "Две беды сходятся разом: %(first)s и %(second)s. Порознь их пережили бы; "
    "вместе — нет.",
    "%(first_cap)s накладывается на беду по имени %(second)s, и счёт потерь "
    "идёт вдвое быстрее.",
    "Худшее, что может случиться с бедой, — другая беда. %(first_cap)s встречается "
    "с %(second)s.",
)

FAMINE_TEMPLATES = (
    "Начинается голод, какого не помнят: поля брошены, а те, что не брошены, "
    "вытоптаны.",
    "Хлеба нет ни у кого. Голод убивает больше, чем то, из-за чего он начался.",
    "Города съедают запасы за зиму и выходят на дороги.",
)


def compound(rng, first, second):
    data = {"first": first.name, "first_cap": cap(first.name), "second": second.name}
    text = rng.choice(COMPOUND_TEMPLATES) % data
    text += " " + rng.choice(FAMINE_TEMPLATES)
    return ("Беда на беду: %s и %s" % (first.name, second.name), cap(text))


# ---------------------------------------------------------------------------
# Тёмные века
# ---------------------------------------------------------------------------

DARK_AGE_TEMPLATES = (
    "После такого мир не встаёт сразу: наступают тёмные века. Дороги зарастают, "
    "города не растут, летопись ведут урывками.",
    "Начинаются годы, которые потом назовут тёмными. Считать перестают не только "
    "погибших, но и годы.",
    "Тёмные века: что уцелело, то держится за стены и не высовывается.",
    "Мир замолкает. Следующие поколения будут собирать по крохам то, "
    "что было общим местом.",
)


def dark_age(rng, calamity, years: int, world):
    text = rng.choice(DARK_AGE_TEMPLATES)
    text += " Тьма ляжет на %s." % years_text(years)
    return ("Тёмные века после бедствия «%s»" % calamity.name, cap(text))


DARK_AGE_END_TEMPLATES = (
    "Тёмные века кончаются. Первые за долгое время караваны доходят целыми.",
    "Мир выбирается из тьмы: снова строят, снова считают годы, снова спорят о границах.",
    "Тёмные времена отступают — не вдруг, но заметно.",
)


def dark_age_end(rng, calamity):
    return ("Конец тёмных веков",
            cap(rng.choice(DARK_AGE_END_TEMPLATES)))


# ---------------------------------------------------------------------------
# Следы бедствий
# ---------------------------------------------------------------------------

RELIC_LEFT_TEMPLATES = (
    "Беда уходит, но оставляет по себе след: %(relic)s.",
    "После неё остаётся %(relic_acc)s — и память о том, чем это было.",
    "След беды никуда не девается: %(relic)s.",
)


def relic_left(rng, relic, calamity, world):
    region = world.regions.get(relic.region_id)
    where = (" (земли: %s)" % region.name) if region is not None else ""
    data = {"relic": relic.name + where, "relic_acc": relic.name + where}
    return ("След бедствия: %s" % relic.name,
            cap(rng.choice(RELIC_LEFT_TEMPLATES) % data))


AWAKEN_TEMPLATES = (
    "%(who)s тревожит то, что лучше было не трогать: %(relic)s. "
    "Это след давнего бедствия — %(origin)s, %(ago)s назад.",
    "В землях под именем %(where)s находят %(relic)s. Старики помнят, "
    "чем это было: %(origin)s, %(ago)s назад.",
    "%(relic_cap)s просыпается. Последний раз об этом слышали, когда мир "
    "держала беда по имени %(origin)s — %(ago)s назад.",
    "Никто уже не помнил, что здесь было. Зря: %(relic)s подаёт голос. "
    "Начало этому положила беда по имени %(origin)s, %(ago)s назад.",
)

AWAKENERS = (
    "Пастухи", "Рудокопы", "Охотники за сокровищами", "Странствующий чародей",
    "Отряд наёмников", "Крестьяне, копавшие колодец", "Юный князь на охоте",
    "Артель каменотёсов", "Сборщик податей", "Заблудившийся караван",
)


def relic_awakens(rng, relic, origin, world, year: int):
    region = world.regions.get(relic.region_id)
    ago = years_text(max(1, year - relic.created.year))
    data = {
        "who": rng.choice(AWAKENERS),
        "relic": relic.name,
        "relic_cap": cap(relic.name),
        "origin": "«%s» (%d год)" % (origin.name, origin.start.year)
                  if origin is not None else "старое бедствие",
        "ago": ago,
        "where": region.name if region is not None else "глухих землях",
    }
    return ("Пробуждение: %s" % relic.name,
            cap(rng.choice(AWAKEN_TEMPLATES) % data))


# Логова с карты мира лежали здесь ещё до первых племён.
LAIR_WAKE_TEMPLATES = (
    "То, что спало в землях под именем %(where)s дольше, чем стоит любая "
    "страна, открывает глаза. Имя этому — %(relic)s.",
    "%(relic_cap)s пробуждается. Местные знали о нём из песен и обходили "
    "%(where)s стороной — теперь ясно, почему.",
    "В %(where)s рушится тишина, которой было больше веков, чем помнит "
    "летопись: %(relic)s выходит наружу.",
    "Старики говорили, что под %(where)s спит беда. Старики оказались правы: "
    "%(relic)s подаёт голос.",
    "%(relic_cap)s было здесь раньше городов, раньше племён, раньше имён. "
    "Теперь оно просыпается.",
)


def lair_awakens(rng, relic, world, year: int):
    """Пробуждение логова, которое карта положила в мир до начала истории."""
    region = world.regions.get(relic.region_id)
    data = {
        "relic": relic.name,
        "relic_cap": cap(relic.name),
        "where": region.name if region is not None else "глухих землях",
    }
    return ("Пробуждение: %s" % relic.name,
            cap(rng.choice(LAIR_WAKE_TEMPLATES) % data))


ECHO_TEMPLATES = (
    "Отголосок старой беды: %(relic)s не даёт покоя окрестным землям. "
    "Корень этого — %(origin)s.",
    "Из земель под именем %(where)s снова приходят дурные вести. Виной тому "
    "%(relic)s — то, что осталось от бедствия «%(origin_name)s».",
    "%(relic_cap)s собирает свою дань: несколько деревень, торговый обоз, "
    "отряд стражи. Всё это — наследство бедствия «%(origin_name)s».",
)


def relic_echo(rng, relic, origin, world):
    region = world.regions.get(relic.region_id)
    data = {
        "relic": relic.name,
        "relic_cap": cap(relic.name),
        "where": region.name if region is not None else "без имени",
        "origin": "«%s» (%d год)" % (origin.name, origin.start.year)
                  if origin is not None else "давнее бедствие",
        "origin_name": origin.name if origin is not None else "давнее бедствие",
    }
    return ("Отголосок: %s" % relic.name,
            cap(rng.choice(ECHO_TEMPLATES) % data))


HERO_TEMPLATES = (
    "Имя %(hero)s заносят в списки героев мира.",
    "О %(hero_bare)s начинают петь ещё при жизни.",
    "%(hero_cap)s получает то, что дают немногим: имя, которое переживёт страну.",
)


def hero_praise(rng, hero):
    data = {"hero": with_title(hero), "hero_cap": cap(with_title(hero)),
            "hero_bare": hero.name}
    return cap(rng.choice(HERO_TEMPLATES) % data)
