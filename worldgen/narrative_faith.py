# -*- coding: utf-8 -*-
"""Тексты о вере: откровения, храмы, расколы, гонения, чудеса и забвение.

Правила прежние: имена в именительном падеже, глаголы настоящего времени,
падежи — только там, где формы заданы заранее (сферы покровительства
хранятся сразу в трёх падежах, титулы божеств — со своим родительным).
"""

from __future__ import annotations

from .morph import phrase
from .narrative import cap
from .pantheon import ALIGNMENT_NAMES, DOMAINS_BY_KEY, title_genitive
from .timeline import MONTH_NAMES, years_text

NUMERAL_GEN = {
    1: "Одного", 2: "Двух", 3: "Трёх", 4: "Четырёх", 5: "Пяти",
    6: "Шести", 7: "Семи", 8: "Восьми", 9: "Девяти", 10: "Десяти",
    11: "Одиннадцати", 12: "Двенадцати",
}

FAITH_ADJECTIVES = ("Светлый", "Старший", "Тихий", "Вечный", "Первый",
                    "Истинный", "Единый", "Открытый", "Каменный", "Древний")

# Слово «вера» в имени не используем: в косвенных падежах получалось бы
# «веры „Вера Двух“».
FAITH_HEADS = (("Круг", "m"), ("Путь", "m"), ("Завет", "m"), ("Дом", "m"),
               ("Слово", "n"), ("Свет", "m"), ("Обычай", "m"), ("Устав", "m"))

DARK_FAITH_HEADS = (("Круг", "m"), ("Путь", "m"), ("Обряд", "m"),
                    ("Шёпот", "m"), ("Ночь", "f"), ("Голод", "m"))


# ---------------------------------------------------------------------------
# Имена и описания
# ---------------------------------------------------------------------------

def f_nom(faith) -> str:
    """«вера „Старшие Духи“» — безопасное подлежащее любого рода и числа."""
    return "вера «%s»" % faith.name


def f_gen(faith) -> str:
    return "веры «%s»" % faith.name


def f_dat(faith) -> str:
    return "вере «%s»" % faith.name


def f_acc(faith) -> str:
    return "веру «%s»" % faith.name


def f_ins(faith) -> str:
    return "верой «%s»" % faith.name


def f_prep(faith) -> str:
    return "вере «%s»" % faith.name


def _faith_data(faith) -> dict:
    return {
        "faith": faith.name,
        "faith_nom": f_nom(faith),
        "faith_nom_cap": cap(f_nom(faith)),
        "faith_gen": f_gen(faith),
        "faith_dat": f_dat(faith),
        "faith_acc": f_acc(faith),
        "faith_ins": f_ins(faith),
        "faith_prep": f_prep(faith),
    }


def deity_epithet(rng, title: str, domains) -> str:
    """«Владыка Леса», «Мать Урожая»."""
    if not domains:
        return title
    domain = DOMAINS_BY_KEY[domains[0]]
    return "%s %s" % (title, domain.gen)


def domains_text(domains) -> str:
    """«покровительствует лесу, ветру и зверям»."""
    words = [DOMAINS_BY_KEY[key].dat for key in domains if key in DOMAINS_BY_KEY]
    if not words:
        return "ничему в особенности"
    if len(words) == 1:
        return words[0]
    return "%s и %s" % (", ".join(words[:-1]), words[-1])


def domains_list(domains) -> str:
    """«Лес, Ветер, Звери» — для справочников."""
    return ", ".join(DOMAINS_BY_KEY[key].name for key in domains
                     if key in DOMAINS_BY_KEY)


def faith_name(rng, kind: str, deities, alignment: int, race=None) -> str:
    """Имя веры — без склонения чужих имён."""
    dark = alignment <= -2
    heads = DARK_FAITH_HEADS if dark else FAITH_HEADS
    head, gender = rng.choice(heads)

    if kind == "культ" and deities:
        deity = deities[0]
        return "Культ %s" % _deity_genitive(deity)
    if kind == "вера предков":
        return rng.choice((
            "Завет Предков", "Тропа Предков", "Старшие Духи", "Круг Костров",
            "Голоса Земли", "Древний Обычай", "Дым и Кость",
        ))
    if len(deities) >= 2 and rng.chance(0.45):
        numeral = NUMERAL_GEN.get(len(deities), "Многих")
        return "%s %s" % (head, numeral)
    if deities and rng.chance(0.45):
        # В имя веры идёт та сфера, что не спорит с её мировоззрением.
        keys = [key for key in deities[0].domains if key in DOMAINS_BY_KEY]
        fitting = [key for key in keys
                   if (DOMAINS_BY_KEY[key].light >= 0) == (alignment >= 0)]
        chosen = (fitting or keys)
        if chosen:
            return "%s %s" % (head, DOMAINS_BY_KEY[chosen[0]].gen)
    return phrase(rng.choice(FAITH_ADJECTIVES), head, gender)


def _deity_genitive(deity) -> str:
    """«Владыки Бурь» — для «Культ Владыки Бурь»."""
    if deity.epithet:
        parts = deity.epithet.split(" ", 1)
        head = title_genitive(parts[0])
        if len(parts) == 2:
            return "%s %s" % (head, parts[1])
        return head
    return title_genitive(deity.title)


def festival_line(deity) -> str:
    """«Пахота — 2-й день месяца Стылень»: название праздника не склоняется."""
    return "%s — %d-й день месяца %s." % (
        deity.festival_name, deity.festival_day,
        MONTH_NAMES[(deity.festival_month - 1) % 12])


# ---------------------------------------------------------------------------
# Рождение веры
# ---------------------------------------------------------------------------

REVELATION_TEMPLATES = (
    "%(prophet)s видит сон, который снится трижды, и на третий раз ему верят. "
    "Так у %(race_gen)s появляется новая вера — %(faith)s.",
    "%(prophet)s уходит в пустошь и возвращается через сорок дней с именами "
    "богов на устах. Имя новой веры — %(faith)s.",
    "На пепелище сгоревшего дома %(prophet)s говорит то, чего прежде не "
    "говорил никто. Слушателей набирается немного, но они запоминают. "
    "Так начинается вера под именем %(faith)s.",
    "Жрецов ещё нет, храмов тоже. Есть только %(prophet)s и слова, которые "
    "он повторяет всем встречным. Из этих слов вырастет %(faith_nom)s.",
    "%(prophet)s объявляет, что боги назвали себя. Народ %(race_gen)s слушает "
    "и мало-помалу начинает верить. Имя новой веры — %(faith)s.",
    "Старые обряды перестают помогать, и %(prophet)s предлагает новые. "
    "Так приходит вера по имени %(faith)s.",
    "Никто не помнит, кто был первым слушателем. Помнят только, что "
    "%(prophet)s говорил, а потом это записали. Вера получает имя: %(faith)s.",
)

PANTHEON_INTRO = (
    "В пантеоне %(count)d: %(names)s.",
    "Богов называют по именам: %(names)s — всего %(count)d.",
    "Имён в новом пантеоне %(count)d: %(names)s.",
)


def faith_born(rng, faith, prophet, deities, race, world):
    data = _faith_data(faith)
    data.update({"prophet": _with_title(prophet), "race_gen": race.gen_plural})
    parts = [rng.choice(REVELATION_TEMPLATES) % data]
    if len(deities) > 1:
        names = "; ".join(deity.full_name for deity in deities)
        parts.append(rng.choice(PANTHEON_INTRO) % {"count": len(deities),
                                                   "names": names})
    elif deities:
        deity = deities[0]
        parts.append("Бог один, и зовут его так: %s." % deity.full_name)
    if deities:
        chief = deities[0]
        parts.append("%s покровительствует %s." % (chief.given_name,
                                                   domains_text(chief.domains)))
        parts.append("Праздник: %s" % festival_line(chief))
    parts.append("Мировоззрение новой веры — %s." % ALIGNMENT_NAMES.get(
        faith.alignment, "непостижимое"))
    if faith.forbidden:
        parts.append("В большинстве стран такую веру объявят запретной.")
    return ("Новая вера: %s" % faith.name, cap(" ".join(parts)))


def _with_title(figure) -> str:
    if figure is None:
        return "безымянный проповедник"
    if figure.titles:
        return "%s %s" % (figure.titles[0].lower(), figure.name)
    return figure.name


DEITY_REVEALED_TEMPLATES = (
    "Пантеон прирастает: %(deity)s встаёт рядом с прежними богами. "
    "Покровительствует %(domains)s.",
    "Жрецы объявляют о новом имени: %(deity)s. Покровительствует %(domains)s.",
    "К старым богам добавляют ещё одного: %(deity)s, покровитель %(gen)s.",
)


def deity_revealed(rng, faith, deity):
    domain = DOMAINS_BY_KEY.get(deity.domains[0]) if deity.domains else None
    data = {
        "deity": deity.full_name,
        "domains": domains_text(deity.domains),
        "gen": domain.gen.lower() if domain is not None else "многого",
        "faith": faith.name,
    }
    return ("Новый бог: %s" % deity.given_name,
            cap(rng.choice(DEITY_REVEALED_TEMPLATES) % data + " Праздник: " +
                festival_line(deity)))


# ---------------------------------------------------------------------------
# Распространение
# ---------------------------------------------------------------------------

CONVERT_TEMPLATES = (
    "Проповедники %(faith_gen)s доходят до места под именем %(where)s, "
    "и там принимают новую веру.",
    "%(where_cap)s переходит в %(faith_acc)s: старые алтари разбирают на камень.",
    "После долгих споров %(where_cap)s принимает %(faith_acc)s.",
    "Купцы приносят не только товар: %(where_cap)s принимает %(faith_acc)s.",
    "%(preacher)s обращает жителей места под именем %(where)s в %(faith_acc)s.",
)

TRIBE_CONVERT_TEMPLATES = (
    "Миссионеры находят кочевье под именем %(where)s и остаются в нём "
    "зимовать. К весне там принимают %(faith_acc)s.",
    "%(where_cap)s меняет духов предков на новых богов: теперь это "
    "%(faith_nom)s.",
    "%(preacher)s живёт среди кочевья под именем %(where)s три года "
    "и уводит его в %(faith_acc)s.",
)


def conversion(rng, faith, target_name, preacher, tribal: bool = False):
    data = _faith_data(faith)
    data.update({
        "where": target_name,
        "where_cap": cap(target_name),
        "preacher": _with_title(preacher),
    })
    templates = TRIBE_CONVERT_TEMPLATES if tribal else CONVERT_TEMPLATES
    return ("Обращение: %s" % target_name,
            cap(rng.choice(templates) % data))


STATE_FAITH_TEMPLATES = (
    "%(ruler)s объявляет государственной верой такую: %(faith)s. Другие "
    "обряды терпят, но не любят.",
    "%(polity)s принимает государственную веру: %(faith)s. Храмы получают "
    "землю и освобождение от податей.",
    "Совет и корона сходятся в одном: отныне вера страны — %(faith)s.",
    "%(ruler)s принимает новую веру первым, и страна следует за ним: "
    "%(faith)s.",
    "Указ читают на площадях: вера государства теперь одна — %(faith)s.",
)


def state_faith(rng, polity, faith, ruler):
    data = _faith_data(faith)
    data.update({
        "polity": polity.full_name,
        "ruler": _with_title(ruler) if ruler is not None else "правитель",
    })
    return ("Государственная вера: %s" % polity.name,
            cap(rng.choice(STATE_FAITH_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Храмы
# ---------------------------------------------------------------------------

TEMPLE_TEMPLATES = (
    "%(founder)s закладывает %(temple)s — %(where)s.",
    "В городе по имени %(city)s поднимается %(temple)s. Строит его %(founder)s.",
    "%(temple)s освящают на месте старого капища. Первый камень кладёт "
    "%(founder)s.",
    "Купола видно с трёх дней пути: строительство кончено. Это %(temple)s, "
    "и строил его %(founder)s.",
)

GRAND_TEMPLE_NOTE = (
    "Строили его три поколения.",
    "Такого не видели ни в одной соседней стране.",
    "Золота на купол ушло больше, чем на войско.",
    "Паломники идут к нему со всего света.",
)


def temple_built(rng, temple, faith, deity, settlement, founder):
    data = _faith_data(faith)
    data.update({
        "temple": temple.name,
        "city": settlement.name if settlement is not None else "неизвестном",
        "where": "храм %s" % f_gen(faith),
        "founder": _with_title(founder),
        "founder_gen": founder.name if founder is not None else "неизвестных людей",
    })
    text = rng.choice(TEMPLE_TEMPLATES) % data
    if temple.grandeur >= 3:
        text += " " + rng.choice(GRAND_TEMPLE_NOTE)
    if deity is not None:
        text += " Посвящён: %s." % deity.full_name
    return ("Храм: %s" % temple.name, cap(text))


TEMPLE_RUIN_TEMPLATES = (
    "%(temple)s стоит пустым: служить в нём больше некому.",
    "%(temple)s разорён, и камень его растаскивают на ограды.",
    "Крыша %(temple_gen)s проваливается внутрь. Больше её не чинят.",
)


def temple_ruined(rng, temple):
    data = {"temple": temple.name, "temple_gen": temple.name}
    return ("Заброшенный храм: %s" % temple.name,
            cap(rng.choice(TEMPLE_RUIN_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Раскол, запрет, гонения
# ---------------------------------------------------------------------------

SCHISM_TEMPLATES = (
    "%(heretic)s читает старые тексты иначе, чем принято, и находит "
    "сторонников. Из %(parent_gen)s выходит новая вера: %(faith)s.",
    "Спор о природе богов кончается расколом: %(faith_nom_cap)s отделяется "
    "от %(parent_gen)s. Во главе — %(heretic)s.",
    "Собор не приходит к согласию. Меньшинство уходит и объявляет свою "
    "веру истинной: %(faith)s.",
    "%(heretic)s объявляет, что жрецы %(parent_gen)s лгут уже триста лет. "
    "Так рождается %(faith)s.",
    "Две половины одного собора расходятся по домам и больше не сходятся. "
    "Меньшая берёт себе имя: %(faith)s.",
)


def schism(rng, faith, parent, heretic):
    data = _faith_data(faith)
    data.update({
        "parent": parent.name,
        "parent_gen": f_gen(parent),
        "heretic": _with_title(heretic),
    })
    return ("Раскол веры: %s" % faith.name,
            cap(rng.choice(SCHISM_TEMPLATES) % data))


BAN_TEMPLATES = (
    "%(ruler)s объявляет %(faith_acc)s запретной. Алтари велено разбить, "
    "жрецов — выдать.",
    "%(polity)s запрещает %(faith_acc)s под страхом смерти.",
    "Указ короток: за %(faith_acc)s — плаха. %(polity)s больше не терпит "
    "этих обрядов.",
)


def faith_banned(rng, polity, faith, ruler):
    data = _faith_data(faith)
    data.update({"polity": polity.full_name,
                 "ruler": _with_title(ruler) if ruler is not None else "правитель"})
    return ("Запрет веры: %s" % faith.name,
            cap(rng.choice(BAN_TEMPLATES) % data))


PERSECUTION_TEMPLATES = (
    "Гонения: приверженцев %(faith_gen)s ищут по домам. Найденных не судят.",
    "Костры горят в каждом городе: %(polity)s выжигает %(faith_acc)s.",
    "Дознаватели работают три года. После них от %(faith_gen)s остаются "
    "только слухи и тайные знаки на стенах.",
    "Храмы %(faith_gen)s ломают, жрецов вешают на их же воротах.",
)


def persecution(rng, polity, faith, dead: int):
    data = _faith_data(faith)
    data.update({"polity": polity.full_name if polity is not None else "страна"})
    text = rng.choice(PERSECUTION_TEMPLATES) % data
    if dead:
        text += " Счёт казнённых и умерших в бегах — %d." % dead
    return ("Гонения на веру: %s" % faith.name, cap(text))


# ---------------------------------------------------------------------------
# Упадок, забвение, возрождение
# ---------------------------------------------------------------------------

FADING_TEMPLATES = (
    "%(faith_nom_cap)s теряет последние города. Жрецы ещё служат, "
    "но по привычке.",
    "О %(faith_prep)s вспоминают всё реже. Праздники справляют, не помня, зачем.",
    "%(faith_nom_cap)s держится в двух-трёх глухих углах и медленно уходит.",
    "Молодые уже не знают обрядов %(faith_gen)s, а старые не спорят.",
)


def faith_fading(rng, faith):
    return ("Угасание веры: %s" % faith.name,
            cap(rng.choice(FADING_TEMPLATES) % _faith_data(faith)))


FORGOTTEN_TEMPLATES = (
    "%(faith_nom_cap)s забыта. Имена её богов больше никто не произносит "
    "вслух — не из страха, а потому что не помнит.",
    "Последний жрец %(faith_gen)s умирает, не оставив ученика. На этом всё.",
    "%(faith_nom_cap)s уходит из мира. Остаются пустые храмы и знаки, "
    "которых никто не читает.",
    "Имя «%(faith)s» перестают писать в списках вер. Никто не замечает.",
)


def faith_forgotten(rng, faith, temples: int):
    data = _faith_data(faith)
    text = rng.choice(FORGOTTEN_TEMPLATES) % data
    if temples:
        text += " Храмов после неё остаётся %d — все пустые." % temples
    return ("Забытая вера: %s" % faith.name, cap(text))


REVIVAL_TEMPLATES = (
    "В развалинах находят знаки старой веры, и кто-то решает, что их стоит "
    "прочесть. %(faith_nom_cap)s возвращается через %(ago)s забвения.",
    "%(faith_nom_cap)s поднимается из пепла: %(prophet)s объявляет себя "
    "наследником жрецов, которых не стало %(ago)s назад.",
    "Забытые боги оказываются терпеливыми. %(faith_nom_cap)s возвращается "
    "спустя %(ago)s.",
    "Старое имя снова звучит на площадях: %(faith)s. Возвращает его "
    "%(prophet)s, и слушают охотнее, чем ожидали.",
)


def faith_revived(rng, faith, prophet, years: int):
    data = _faith_data(faith)
    data.update({
        "prophet": _with_title(prophet),
        "ago": years_text(max(1, years)),
    })
    return ("Возвращение веры: %s" % faith.name,
            cap(rng.choice(REVIVAL_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Благословения, проклятия, чудеса
# ---------------------------------------------------------------------------

BLESSING_TEMPLATES = (
    "%(who)s получает дар от бога: %(gift)s. Сказано — %(reason)s.",
    "Боги отмечают смертного: %(who)s получает %(gift_acc)s %(reason)s. "
    "С этого дня %(effect)s.",
    "%(deity)s является во сне и оставляет знак. Дар получает %(who)s: "
    "%(gift)s, %(effect)s.",
    "%(reason_cap)s %(deity)s дарует %(gift_acc)s. Носит дар %(who)s.",
)

CURSE_TEMPLATES = (
    "%(deity)s проклинает смертного %(reason)s. %(who_cap)s получает "
    "%(curse_acc)s: %(effect)s.",
    "%(who)s навлекает проклятие %(reason)s. Наказание — %(curse)s, "
    "и %(effect)s.",
    "За такое не прощают: %(who)s проклят %(reason)s. %(effect_cap)s.",
)


def blessing(rng, figure, deity, gift, effect, reason):
    data = {
        "who": _with_title(figure),
        "who_cap": cap(_with_title(figure)),
        "deity": deity.full_name if deity is not None else "бог",
        "gift": gift,
        "gift_acc": gift,
        "effect": effect,
        "reason": reason,
        "reason_cap": cap(reason),
    }
    return ("Благословение: %s" % figure.plain_name,
            cap(rng.choice(BLESSING_TEMPLATES) % data))


def curse(rng, figure, deity, curse_name, effect, reason):
    data = {
        "who": _with_title(figure),
        "who_cap": cap(_with_title(figure)),
        "deity": deity.full_name if deity is not None else "бог",
        "curse": curse_name,
        "curse_acc": curse_name,
        "effect": effect,
        "effect_cap": cap(effect),
        "reason": reason,
    }
    return ("Проклятие: %s" % figure.plain_name,
            cap(rng.choice(CURSE_TEMPLATES) % data))


MIRACLE_TEMPLATES = (
    "В храме по имени %(temple)s происходит то, чему нет объяснения, "
    "и об этом говорят год.",
    "Статуя бога плачет три дня подряд. Паломников приходится разгонять "
    "стражей.",
    "Слепой прозревает на пороге храма. Жрецы записывают имена свидетелей.",
    "Над городом стоит свет, которого не даёт ни одна звезда.",
)


def miracle(rng, temple_name, deity):
    text = rng.choice(MIRACLE_TEMPLATES) % {"temple": temple_name}
    if deity is not None:
        text += " Чудо приписывают: %s." % deity.full_name
    return ("Чудо", cap(text))


HIGH_PRIEST_TEMPLATES = (
    "%(priest)s становится во главе %(faith_gen)s.",
    "Жребий и совет сходятся на одном имени: %(priest)s возглавляет "
    "%(faith_acc)s.",
    "После долгого спора %(faith_nom)s получает нового предстоятеля: "
    "%(priest)s.",
)


def high_priest(rng, faith, priest):
    data = _faith_data(faith)
    data["priest"] = _with_title(priest)
    return ("Глава веры: %s" % priest.plain_name,
            cap(rng.choice(HIGH_PRIEST_TEMPLATES) % data))


BLAME_TEMPLATES = (
    "Жрецы называют виновника беды: %(deity)s. Говорят, такова %(his)s воля, "
    "и оспорить некому.",
    "Беду списывают на божий гнев. Имя названо: %(deity)s. Приверженцев "
    "%(faith_gen)s бьют на улицах.",
    "Толкователи сходятся: беда по имени «%(calamity)s» — дело рук такого "
    "бога, как %(deity)s. Храмы других вер переполнены.",
)


def divine_blame(rng, calamity, deity, faith):
    data = _faith_data(faith) if faith is not None else {"faith_gen": "этой веры"}
    data.update({"deity": deity.full_name, "calamity": calamity.name,
                 "his": "её" if deity.sex == "f" else "его"})
    return ("Гнев богов: %s" % calamity.name,
            cap(rng.choice(BLAME_TEMPLATES) % data))


CHAMPION_TEMPLATES = (
    "%(hero)s выходит на битву не один: за плечом стоит %(deity)s. "
    "Так говорят те, кто видел.",
    "Перед последней битвой %(hero)s получает знак от бога — %(deity)s. "
    "Дальше всё известно.",
)


def champion(rng, hero, deity, calamity):
    data = {"hero": _with_title(hero), "deity": deity.full_name,
            "calamity": calamity.name}
    return ("Избранник богов: %s" % hero.plain_name,
            cap(rng.choice(CHAMPION_TEMPLATES) % data))


FESTIVAL_TEMPLATES = (
    "Праздник по имени %(feast)s в этом году справляют особенно широко: "
    "%(note)s",
    "Наступает праздник — %(feast)s. %(note)s",
    "В этот день отмечают %(feast_acc)s: %(note)s",
)

FESTIVAL_NOTES = (
    "на площадях жгут костры и раздают хлеб.",
    "город не спит три ночи подряд.",
    "в храмы не протолкнуться, а на улицах пляшут.",
    "нищим в этот день не отказывают ни в чём.",
    "должникам прощают долг, а ссоры мирят при свидетелях.",
)


def festival(rng, deity, faith):
    data = {"feast": deity.festival_name,
            "feast_acc": "праздник под именем %s" % deity.festival_name,
            "note": rng.choice(FESTIVAL_NOTES)}
    text = rng.choice(FESTIVAL_TEMPLATES) % data
    text += " Праздник посвящён: %s." % deity.full_name
    return ("Праздник: %s" % deity.festival_name, cap(text))
