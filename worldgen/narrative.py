# -*- coding: utf-8 -*-
"""Тексты летописи.

Каждая функция возвращает пару (заголовок, текст). Дату подставляет уже
сам летописец (chronicle.py), поэтому здесь её нет.

Формулировки намеренно избыточны: на десять тысяч лет истории приходятся
сотни оснований городов, и они не должны читаться под копирку.
"""

from __future__ import annotations

from .morph import accusative_noun, adjective_for, genitive_noun
from .timeline import years_text

# ---------------------------------------------------------------------------
# Общие обороты
# ---------------------------------------------------------------------------

# Только предложные обороты: деепричастия и причастия требуют запятых
# и согласования, а шаблоны собираются автоматически.
MOTIVES = (
    "в поисках лучших земель",
    "от лютых зим",
    "по вещему сну старейшин",
    "после раздора у общего костра",
    "от долгого голода",
    "по слову оракула",
    "вслед за уходящими стадами",
    "от чужих набегов",
    "из-за спора об охотничьих угодьях",
    "по упрямству вождя",
    "от вечных склок",
    "в поисках земли из старых песен",
)

# Только предложные обороты — их можно ставить в начало фразы без запятой.
OMENS = (
    "в ночь двойной луны",
    "под кровавой зарёй",
    "в год небывалого урожая",
    "в разгар долгой суши",
    "в первый день оттепели",
    "под крик перелётных птиц",
    "при столбе света над лесом",
    "после семи дней непрерывного дождя",
    "под погасшей звездой",
    "в небывалой тишине",
    "на исходе третьей зимы",
    "в разгар листопада",
)

# Обороты без придаточных: их можно ставить в середину предложения,
# не боясь пропущенной запятой.
WHERE_TEMPLATES = (
    "в землях под именем %s",
    "в краю по имени %s",
    "в месте под названием %s",
    "на землях по имени %s",
    "в стороне под названием %s",
)

# Обороты направления (винительный падеж) — для глаголов движения.
WHITHER_TEMPLATES = (
    "в земли под именем %s",
    "в край по имени %s",
    "в сторону под названием %s",
    "на земли по имени %s",
)

FROM_TEMPLATES = (
    "из земель под именем %s",
    "из края по имени %s",
    "с земель по имени %s",
)

# «в горном краю по имени Кхаз-Морад» — чуть живее сухого перечисления.
TERRAIN_ADJECTIVES = {
    "лес": "лесном", "горы": "горном", "холмы": "холмистом",
    "степь": "степном", "равнина": "равнинном", "болото": "болотистом",
    "побережье": "прибрежном", "тундра": "студёном", "пустыня": "пустынном",
    "джунгли": "душном", "подземья": "подземном", "острова": "островном",
}


def cap(text: str) -> str:
    """Первая буква — заглавная, и после каждой точки тоже.

    Шаблоны часто начинаются с титула («вождь Гхор…»), а склеенные фразы
    дают строчную букву в начале нового предложения.
    """
    if not text:
        return text
    chars = list(text)
    chars[0] = chars[0].upper()
    for i in range(1, len(chars) - 2):
        if chars[i] in ".!?" and chars[i + 1] == " ":
            chars[i + 2] = chars[i + 2].upper()
    return "".join(chars)


def where(rng, region) -> str:
    """«в горном краю по имени Кхаз-Морад» — без ошибок в падежах."""
    if region is None:
        return "в неведомых землях"
    adjective = TERRAIN_ADJECTIVES.get(region.terrain)
    if adjective and rng.chance(0.4):
        return "в %s краю по имени %s" % (adjective, region.name)
    return rng.choice(WHERE_TEMPLATES) % region.name


def whither(rng, region) -> str:
    """«уходит в земли под именем Кривые Отмели» — винительный падеж."""
    if region is None:
        return "в неведомые земли"
    return rng.choice(WHITHER_TEMPLATES) % region.name


def from_where(rng, region) -> str:
    if region is None:
        return "из неведомых земель"
    return rng.choice(FROM_TEMPLATES) % region.name


def souls_prep(count: int) -> str:
    """«о 71 душе», «о 110 душах» — предложный падеж."""
    from .timeline import plural
    return "%d %s" % (count, plural(count, "душе", "душах", "душах"))


def souls_acc(count: int) -> str:
    """«ведёт 71 душу», «ведёт 110 душ» — винительный падеж."""
    from .timeline import plural
    return "%d %s" % (count, plural(count, "душу", "души", "душ"))


SITE_WORDS = {
    "лес": ("на лесной прогалине", "у корней древнего дуба", "под пологом вековых сосен"),
    "горы": ("у подножия хребта", "на горном уступе", "у входа в глубокое ущелье"),
    "холмы": ("на вершине холма", "меж двух пологих увалов", "над старым курганом"),
    "степь": ("у одинокого кургана", "на берегу степной реки", "посреди ковыльного моря"),
    "равнина": ("у широкой излучины реки", "на плодородной пойме", "у брода через реку"),
    "болото": ("на твёрдом островке среди топей", "у чёрной воды", "на гати посреди трясины"),
    "побережье": ("в защищённой бухте", "на высоком берегу над прибоем", "у песчаной косы"),
    "тундра": ("у горячего источника", "под защитой скальной гряды", "на краю вечных снегов"),
    "пустыня": ("у единственного колодца", "в тени скального навеса", "у пальмового оазиса"),
    "джунгли": ("на расчищенной от лиан поляне", "у водопада", "на речном обрыве"),
    "подземья": ("в просторной пещере", "у подземного озера", "там, где своды уходят во тьму"),
    "острова": ("на приглядной бухте острова", "у скалистого мыса", "на отмели меж островов"),
}

DEFAULT_SITES = ("на приглядном месте", "у чистой воды", "там, где земля показалась доброй")


def site(rng, region) -> str:
    pool = SITE_WORDS.get(region.terrain if region else "", DEFAULT_SITES)
    return rng.choice(pool)


def who(figure, title: str = "") -> str:
    """«вождь Гхор Каменный Клык»."""
    if title:
        return "%s %s" % (title.lower(), figure.name)
    return figure.name


def race_person(race, figure) -> str:
    """«эльфийка Силаэль» — раса + имя."""
    return "%s %s" % (race.noun(figure.sex), figure.name)


def race_adj(race, gender: str) -> str:
    return adjective_for(race.adj, gender)


# ---------------------------------------------------------------------------
# Начало мира и эпохи
# ---------------------------------------------------------------------------

def world_begin(rng, world):
    openings = (
        "Мир пробуждается из безмолвия. Земли ещё безымянны, и некому "
        "назвать ни рек, ни гор.",
        "Первое утро мира. Ветер ходит над пустыми землями, и нет никого, "
        "кто бы удивился ему.",
        "Мир только что создан. Он ещё не знает ни имён, ни границ, ни могил.",
        "Начало всех начал: земля тверда, вода холодна, и ни одна тропа "
        "ещё не протоптана.",
    )
    tail = "Земель в этом мире — %d. Летопись охватит %d лет." % (
        len(world.regions), world.total_years)
    return "Сотворение мира", cap("%s %s" % (rng.choice(openings), tail))


def era_begin(rng, era, spec):
    lead = rng.choice((
        "Начинается",
        "Открывается",
        "Отсчёт ведут от этого года:",
        "Летописцы позже назовут это время так:",
    ))
    return ("Начало: %s" % era.name,
            cap("%s %s. %s" % (lead, era.name, spec.description)))


LAST_ERA_INTROS = (
    "Летопись догоняет настоящее.",
    "Дальше — только слухи и догадки.",
    "Записи доведены до последнего известного года.",
)

ERA_END_INTROS = (
    "Всё кончается, и эпоха тоже.",
    "То, что казалось вечным, оборвалось.",
    "Летописцы расходятся в подробностях, но сходятся в главном.",
    "Мир содрогнулся, и счёт лет начали заново.",
    "После этого года ничто уже не было прежним.",
)

ERA_END_BODIES = {
    "creation": (
        "Первые силы, что лепили сушу и воду, отступили за грань и больше "
        "не откликались на зов.",
        "Свет, из которого была соткана твердь, померк, и мир остался "
        "сам по себе.",
        "Творцы умолкли. Их следы остались только в камне и в песнях.",
    ),
    "gods": (
        "Боги отвернулись от смертных — или перебили друг друга, о том спорят "
        "до сих пор. Небо опустело.",
        "Небесные чертоги обрушились. Тех, кто говорил с богами, больше никто "
        "не слушал.",
        "Божественная кровь пролилась на землю, и там, где она пала, до сих пор "
        "ничего не растёт.",
    ),
    "myths": (
        "Древние чудовища ушли в глубины и легенды. Мир стал меньше и понятнее.",
        "Последние великаны легли в землю, и та осела под их весом.",
        "Чудеса измельчали: то, что раньше видел каждый, теперь считают враньём.",
    ),
    "heroes": (
        "Знамёна героев сгорели в одном огромном пожаре, и наследовать их "
        "оказалось некому.",
        "Клятвы, на которых держался век, были нарушены все разом.",
        "Герои кончились — остались полководцы, счетоводы и наследники.",
    ),
    "iron": (
        "Здесь запись обрывается: хронист отложил перо, и продолжать некому.",
        "Дальше летопись не ведут — до тех дней ещё никто не дожил.",
    ),
}


def era_end(rng, era, spec, losses: dict, is_last: bool = False):
    title = rng.choice(spec.end_titles)
    parts = [rng.choice(LAST_ERA_INTROS if is_last else ERA_END_INTROS)]
    parts.append(rng.choice(ERA_END_BODIES.get(era.key, ERA_END_BODIES["myths"])))

    tally = []
    if losses.get("polities"):
        tally.append("стран пало: %d" % losses["polities"])
    if losses.get("settlements"):
        tally.append("поселений обращено в руины: %d" % losses["settlements"])
    if losses.get("tribes"):
        tally.append("племён сгинуло: %d" % losses["tribes"])
    if losses.get("camps"):
        tally.append("логовищ разорено: %d" % losses["camps"])
    if tally:
        parts.append("Счёт потерь: %s." % ", ".join(tally))
    parts.append("Так завершилась %s, длившаяся %s." % (
        era.name, years_text(era.length)))
    return title, cap(" ".join(parts))


# ---------------------------------------------------------------------------
# Расы и племена
# ---------------------------------------------------------------------------

AWAKENING_TEMPLATES = (
    "%(race)s впервые открывают глаза %(where)s. О них ещё никто не знает, "
    "и они не знают никого.",
    "%(where_cap)s появляются %(race_low)s — %(trait)s, которых прежде "
    "не видел этот мир.",
    "%(race)s выходят на свет %(where)s. Первое, что они делают, — дают имя "
    "своей земле.",
    "%(from_where_cap)s приходит весть: там живут %(race_low)s, и они разумны.",
    "Земля родит новый народ: %(race_low)s. Их первые шаги — %(where)s.",
)


def race_awakening(rng, race, region):
    data = {
        "race": race.name,
        "race_low": race.name.lower(),
        "where": where(rng, region),
        "trait": rng.choice(race.traits) if race.traits else "новый народ",
    }
    data["where_cap"] = cap(data["where"])
    data["from_where_cap"] = cap(from_where(rng, region))
    return ("Пробуждение: %s" % race.name,
            cap(rng.choice(AWAKENING_TEMPLATES) % data))


FIRST_TRIBE_TEMPLATES = (
    "%(leader)s собирает вокруг себя первые семьи и даёт им общее имя — "
    "%(tribe)s. Так у %(race_gen)s появляется первое племя.",
    "У общего костра %(where)s рождается %(tribe)s: %(leader)s берёт на себя "
    "заботу о %(souls_prep)s.",
    "%(tribe)s — первое имя, которым %(race_nom)s назвали самих себя. "
    "Во главе встаёт %(leader)s.",
    "Первый союз семей у %(race_gen)s: %(tribe)s. Сложился он %(where)s, "
    "и ведёт его %(leader)s.",
)

SPLIT_TRIBE_TEMPLATES = (
    "%(leader)s уводит часть сородичей из %(parent_gen)s %(motive)s. "
    "Новое племя — %(tribe)s, и оседает оно %(where)s.",
    "%(tribe)s отделяется от %(parent_gen)s: %(leader)s ведёт "
    "%(souls_acc)s %(whither)s.",
    "%(motive_cap)s %(leader)s основывает %(tribe_acc)s. Старшие из "
    "%(parent_gen)s провожают ушедших молча.",
    "%(tribe)s откалывается от %(parent_gen)s и уходит %(whither)s. "
    "Во главе — %(leader)s.",
    "Общий костёр разделён надвое: из %(parent_gen)s выходит %(tribe)s. "
    "%(leader_cap)s уводит своих %(motive)s.",
)

NEW_TRIBE_TEMPLATES = (
    "%(where_cap)s складывается %(tribe)s: %(leader)s собирает разрозненные "
    "семьи под одно имя.",
    "%(leader)s объявляет о рождении племени %(tribe_short)s. К нему "
    "прибивается %(souls_acc)s.",
)


def tribe_found(rng, tribe, leader, region, race, parent=None, first=False):
    data = {
        "leader": who(leader, leader.titles[0] if leader.titles else ""),
        "tribe": tribe.full_name,
        "tribe_acc": "%s «%s»" % (accusative_noun(tribe.word).lower(), tribe.name),
        "tribe_short": "«%s»" % tribe.name,
        "parent_gen": ("%s «%s»" % (genitive_noun(parent.word).lower(), parent.name)
                       if parent else ""),
        "where": where(rng, region),
        "whither": whither(rng, region),
        "souls_prep": souls_prep(tribe.population),
        "souls_acc": souls_acc(tribe.population),
        "race_gen": race.gen_plural,
        "race_nom": race.name.lower(),
        "motive": rng.choice(MOTIVES),
    }
    data["leader_cap"] = cap(data["leader"])
    data["where_cap"] = cap(data["where"])
    data["motive_cap"] = cap(data["motive"])
    if first:
        template = rng.choice(FIRST_TRIBE_TEMPLATES)
        title = "Первое племя %s" % race.gen_plural
    elif parent is not None:
        template = rng.choice(SPLIT_TRIBE_TEMPLATES)
        title = "Раскол: %s" % tribe.name
    else:
        template = rng.choice(NEW_TRIBE_TEMPLATES)
        title = "Новое племя: %s" % tribe.name
    return title, cap(template % data)


# ---------------------------------------------------------------------------
# Поселения
# ---------------------------------------------------------------------------

SETTLE_TEMPLATES = (
    "%(leader)s велит больше не сниматься с места: %(site)s поднимается "
    "%(kind)s %(name)s — первые стены племени %(tribe_short)s.",
    "%(tribe)s перестаёт кочевать: %(site)s встаёт %(kind)s %(name)s. "
    "%(founder_word)s — %(leader_bare)s.",
    "%(omen_cap)s %(leader)s закладывает %(kind_acc)s %(name)s. Землю под "
    "стенами размечают по старому обычаю %(race_gen)s.",
    "Так племя %(tribe_short)s пускает корни: %(site)s встаёт %(kind)s "
    "%(name)s, а имя основателя — %(leader_bare)s.",
    "Кочевье кончилось: %(where)s поднимается %(kind)s %(name)s. "
    "Первый камень кладёт %(leader)s.",
    "%(site_cap)s появляется %(kind)s %(name)s. Так племя %(tribe_short)s "
    "перестаёт быть племенем.",
)

COLONY_TEMPLATES = (
    "%(polity)s шлёт поселенцев %(whither)s: %(site)s встаёт %(kind)s "
    "%(name)s; во главе — %(leader_bare)s.",
    "%(leader)s уводит %(count)d поселенцев на границу и основывает "
    "%(kind_acc)s %(name)s. Новая земля присягает: %(polity)s.",
    "На дальней окраине появляется %(kind)s %(name)s — владение, что "
    "признаёт над собой %(polity)s. Закладывает его %(leader)s %(motive)s.",
    "%(omen_cap)s %(where)s поднимается %(kind)s %(name)s — новое владение, "
    "и хозяин ему — %(polity)s. Основатель — %(leader_bare)s.",
    "Границы раздвигаются: %(site)s встаёт %(kind)s %(name)s. "
    "Владелец — %(polity)s, основатель — %(leader_bare)s.",
)

FREE_CITY_TEMPLATES = (
    "%(site_cap)s %(where)s встаёт %(kind)s %(name)s. Основывает его "
    "%(leader)s, никому не присягая.",
    "%(leader)s основывает %(kind_acc)s %(name)s %(where)s. Никому "
    "присягать это место не намерено.",
)


def settlement_found(rng, settlement, leader, region, race, tribe=None,
                     polity=None, kind_label=""):
    data = {
        "leader": who(leader, leader.titles[0] if leader.titles else ""),
        "leader_bare": leader.name,
        "kind": settlement.kind,
        "kind_low": settlement.kind.lower(),
        "kind_acc": accusative_noun(settlement.kind).lower(),
        "name": settlement.name,
        "tribe": tribe.full_name if tribe else "",
        "tribe_short": "«%s»" % tribe.name if tribe else "",
        "polity": polity.full_name if polity else "",
        "where": where(rng, region),
        "whither": whither(rng, region),
        "founder_word": "Основательница" if leader.sex == "f" else "Основатель",
        "race_gen": race.gen_plural,
        "count": max(20, settlement.population // 3),
        "site": site(rng, region),
        "motive": rng.choice(MOTIVES),
        "omen": rng.choice(OMENS),
    }
    data["site_cap"] = cap(data["site"])
    data["omen_cap"] = cap(data["omen"])
    data["where_cap"] = cap(data["where"])

    if tribe is not None:
        template = rng.choice(SETTLE_TEMPLATES)
        title = "Основание: %s" % settlement.name
    elif polity is not None:
        template = rng.choice(COLONY_TEMPLATES)
        title = "Новое поселение: %s" % settlement.name
    else:
        template = rng.choice(FREE_CITY_TEMPLATES)
        title = "Вольное поселение: %s" % settlement.name
    return title, cap(template % data)


# ---------------------------------------------------------------------------
# Страны
# ---------------------------------------------------------------------------

POLITY_TEMPLATES = (
    "%(leader)s объявляет о рождении новой страны — %(polity)s. "
    "Столица — %(capital)s. %(members)s",
    "Города %(race_gen)s сходятся на общий совет, и из этого совета выходит "
    "%(polity)s. Во главе — %(leader)s. %(members)s",
    "%(omen_cap)s %(leader)s принимает титул, которого прежде не носил никто "
    "из %(race_gen)s: так возникает %(polity)s. Столица — %(capital)s. %(members)s",
    "На карте мира появляется новое имя: %(polity)s. Земли вокруг города "
    "%(capital)s собирает под одну руку %(leader)s. %(members)s",
    "Долгие споры кончаются присягой, и страна получает имя: %(polity)s. "
    "Во главе — %(leader)s, столица — %(capital)s. %(members)s",
)


def polity_found(rng, polity, leader, capital, race, members):
    if len(members) > 1:
        joined = "Под его знамя встают и другие поселения — всего %d." % len(members)
        if leader.sex == "f":
            joined = "Под её знамя встают и другие поселения — всего %d." % len(members)
    else:
        joined = "Пока это всего один город и земли вокруг него."
    data = {
        "leader": who(leader, leader.titles[0] if leader.titles else ""),
        "leader_bare": leader.name,
        "polity": polity.full_name,
        "capital": capital.name if capital else "новом городе",
        "race_gen": race.gen_plural,
        "members": joined,
        "omen": rng.choice(OMENS),
    }
    data["omen_cap"] = data["omen"][0].upper() + data["omen"][1:]
    return ("Рождение страны: %s" % polity.name,
            cap(rng.choice(POLITY_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Лагеря злых рас
# ---------------------------------------------------------------------------

CAMP_TEMPLATES = (
    "%(leader)s сгоняет своих %(where)s и ставит %(camp_acc)s. "
    "Окрестные тропы становятся опасны.",
    "%(where_cap)s дымит %(camp)s: %(leader)s собрал под себя "
    "%(count)d глоток.",
    "%(camp)s вырастает %(site)s. Вожак — %(leader_bare)s, из тех, кого "
    "зовут «%(trait)s».",
    "%(leader)s объявляет своими угодьями всё, что лежит вокруг, и ставит "
    "%(camp_acc)s %(where)s.",
    "%(where_cap)s встаёт %(camp)s. Пришлых там не любят, а своих — не считают.",
)


def camp_found(rng, camp, leader, region, race):
    data = {
        "leader": who(leader, leader.titles[0] if leader.titles else ""),
        "leader_bare": leader.name,
        "camp": camp.full_name,
        "camp_acc": "%s «%s»" % (accusative_noun(camp.word).lower(), camp.name),
        "where": where(rng, region),
        "count": camp.population,
        "site": site(rng, region),
        "trait": rng.choice(race.traits) if race.traits else "лиходей",
    }
    data["where_cap"] = cap(data["where"])
    return ("Лагерь: %s" % camp.name, cap(rng.choice(CAMP_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Смерти и упадок
# ---------------------------------------------------------------------------

DEATH_TEMPLATES = (
    "%(who)s умирает в возрасте %(age_text)s. %(legacy)s",
    "Уходит из жизни %(who)s. Прожито — %(age_text)s. %(legacy)s",
    "%(who)s уходит, прожив %(age_text)s. %(legacy)s",
)

LEGACY_LINES = (
    "Основанное им переживает его.",
    "Основанное ею переживает её.",
    "Наследники делят его имя и его долги.",
    "Погребение длится девять дней.",
    "Имя заносят в родовые списки и больше не поминают всуе.",
    "Могилу отмечают камнем без надписи.",
)


def figure_death(rng, figure, race, age: int, achievement: str = ""):
    title = figure.titles[0] if figure.titles else ""
    legacy = achievement or rng.choice(LEGACY_LINES)
    if legacy.startswith("Основанное им") and figure.sex == "f":
        legacy = "Основанное ею переживает её."
    data = {
        "who": who(figure, title),
        "who_gen": figure.name,
        "age_text": years_text(max(1, age)),
        "legacy": legacy,
    }
    return ("Смерть: %s" % figure.name, cap(rng.choice(DEATH_TEMPLATES) % data))


RUIN_TEMPLATES = (
    "%(what)s пустеет: жители расходятся, и стены заносит землёй.",
    "%(what)s превращается в руины. Кто уцелел — уходит, не оглядываясь.",
    "%(what)s исчезает: остаются одни камни.",
    "%(what)s гибнет: %(cause)s.",
)

RUIN_CAUSES = (
    "мор выкосил три четверти жителей",
    "река ушла, и колодцы высохли",
    "земля затряслась и проглотила половину улиц",
    "пожар не оставил ни одного целого дома",
    "долгая осада кончилась ничем — и городом тоже",
    "зима стояла три года подряд",
)


def ruin_text(rng, label: str):
    data = {"what": label, "what_low": label.lower(), "cause": rng.choice(RUIN_CAUSES)}
    return cap(rng.choice(RUIN_TEMPLATES) % data)


POLITY_FALL_TEMPLATES = (
    "%(what)s распадается: наместники перестают слать дань, и никто их "
    "не принуждает.",
    "%(what)s прекращает существование. Печать ломают, знамёна сжигают.",
    "%(what)s исчезает с карт — остаются лишь города, каждый сам по себе.",
)


def polity_fall_text(rng, polity):
    return cap(rng.choice(POLITY_FALL_TEMPLATES) % {"what": polity.full_name})


TRIBE_END_TEMPLATES = (
    "%(what)s растворяется среди соседей — имя ещё помнят, костров уже не жгут.",
    "%(what)s вымирает: последние старики уходят, не оставив наследников.",
    "%(what)s рассеяно и больше не собирается вместе.",
)


def tribe_end_text(rng, tribe):
    return cap(rng.choice(TRIBE_END_TEMPLATES) % {"what": tribe.full_name})


CAMP_END_TEMPLATES = (
    "%(what)s исчезает после соседской облавы.",
    "%(what)s пустеет: вожак сгинул, свора разбежалась.",
    "%(what)s выгорает дотла.",
)


def camp_end_text(rng, camp):
    return cap(rng.choice(CAMP_END_TEMPLATES) % {"what": camp.full_name})
