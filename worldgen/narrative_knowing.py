# -*- coding: utf-8 -*-
"""Слова о познании мира: походы, находки, карты, встречи, освоение.

Тут два правила языка, из которых всё остальное следствия. Первое:
имена собственные стоят в именительном падеже и входят в текст только
оборотом — «земля по имени Высокий Край», «поход по имени «Третья
Проба»», «народ по имени каменные люди». Второе: о знании говорится от
того, кто знает, а не от мира: не «на той земле жили эльфы, но о них
не знали», а «о живущих там в державе не знали ничего» — разница в том,
чья это неосведомлённость.
"""

from __future__ import annotations

from . import knowing as cat
from .timeline import plural


# ---------------------------------------------------------------------------
# Имена
# ---------------------------------------------------------------------------

PROBE_WORDS = ("Поход", "Проба", "Дорога", "Хождение", "Выход", "Посылка")
PROBE_MARKS = ("Первый", "Второй", "Третий", "Долгий", "Тихий", "Спешный",
               "Зимний", "Летний", "Дальний", "Малый", "Большой", "Поздний")


def probe_name(rng, goal, mark) -> str:
    """Как этот поход назовут в бумагах: по цели, по сроку или по земле.

    Имя по земле («Выход к земле по имени Туманный Лес») выходит самым
    длинным, потому что имя в нём стоит оборотом, — поэтому оно и
    встречается реже прочих.
    """
    word = rng.choice(PROBE_WORDS)
    shapes = (
        ("%s к %s" % (word, _to_mark(mark)), 0.6),
        ("%s %s" % (rng.choice(PROBE_MARKS), word.lower()), 1.4),
        ("%s за %s" % (word, _after(goal)), 1.2),
        ("%s %s" % (word, _of_goal(goal)), 1.2),
    )
    return rng.weighted(shapes)


# Имя собственное в этом генераторе стоит только в именительном падеже,
# поэтому после предлога идёт оборот — а падеж берёт на себя
# **родовое слово** оборота: «к земле по имени Туманный Лес», «до земли
# по имени Туманный Лес». Без этой таблицы выходило «к земля по имени
# Туманный Лес»: имя уцелело, а язык сломался.
WORD_CASES = {
    cat.T_REGION: ("земля", "земли", "земле", "земле"),
    cat.T_SITE: ("место", "места", "месту", "месте"),
    cat.T_FOLK: ("народ", "народа", "народу", "народе"),
    cat.T_DOMINION: ("владение", "владения", "владению", "владении"),
    cat.T_ROUTE: ("путь", "пути", "пути", "пути"),
    cat.T_WONDER: ("чудо", "чуда", "чуду", "чуде"),
    cat.T_SPECIES: ("вид существ", "вида существ", "виду существ",
                    "виде существ"),
    cat.T_SCAR: ("шрам", "шрама", "шраму", "шраме"),
    cat.T_TOWN: ("поселение", "поселения", "поселению", "поселении"),
    cat.T_EDGE: ("край света", "края света", "краю света", "крае света"),
}

CASES = {"nom": 0, "gen": 1, "dat": 2, "pre": 3}


def _to_mark(mark, case: str = "dat") -> str:
    """«к земле по имени X» — косвенный падеж только оборотом."""
    return named(mark.kind, mark.name, case)


def named(kind: str, name: str, case: str = "nom") -> str:
    """«земля по имени Высокий Край» — единственный способ поставить имя.

    Падеж берёт родовое слово: имя остаётся в именительном всегда.
    """
    return "%s по имени %s" % (_mark_word_of(kind, case), name)


def _mark_word_of(kind: str, case: str = "nom") -> str:
    forms = WORD_CASES.get(kind) or WORD_CASES[cat.T_SITE]
    return forms[CASES.get(case, 0)]


def side_said(side, upper: bool = False) -> str:
    """Как назвать общество в тексте: державу — по имени, народ — народом.

    Без этого оборота выходит «низинцы впервые сошлись» с малой буквы в
    начале фразы и «Дети Белого Прибоя ставит» с рассогласованием: имя
    народа бывает любого числа и рода, а сказуемое к нему подбирать
    нельзя.
    """
    if side is None:
        return "Неизвестно кто" if upper else "неизвестно кто"
    if side.kind == "folk":
        said = "народ по имени %s" % side.name
    else:
        said = "держава по имени %s" % side.name
    return said[0].upper() + said[1:] if upper else said


def _mark_word(mark, case: str = "nom") -> str:
    return _mark_word_of(mark.kind, case)


def _after(goal) -> str:
    return {
        cat.G_LAND: "дорогой", cat.G_WILD: "диковиной", cat.G_OLD: "прошлым",
        cat.G_FOLK: "речью", cat.G_GOODS: "товаром", cat.G_WAR: "вестями",
    }.get(goal.group, "вестями")


def _of_goal(goal) -> str:
    return {
        cat.G_LAND: "землемеров", cat.G_WILD: "описателей",
        cat.G_OLD: "книжников", cat.G_FOLK: "толмачей",
        cat.G_GOODS: "купцов", cat.G_WAR: "дозорных",
    }.get(goal.group, "ходоков")


CHART_WORDS = ("Чертёж", "Роспись", "Лист", "Свиток", "Опись")


def chart_name(rng, spec, mark) -> str:
    where = mark.name if mark is not None and mark.name else "неведомых мест"
    shapes = (
        "%s по имени %s" % (rng.choice(CHART_WORDS), where),
        "%s земель у %s" % (rng.choice(CHART_WORDS), where),
        "%s: %s" % (rng.choice(CHART_WORDS), spec.said),
    )
    return rng.choice(shapes)


def route_name(world, route) -> str:
    """Торговый путь словами: между какими державами он идёт."""
    seller = world.polities.get(route.seller_id)
    buyer = world.polities.get(route.buyer_id)
    if seller is None or buyer is None:
        return "торговый ход"
    return "ход от %s к %s" % (seller.name, buyer.name)


# ---------------------------------------------------------------------------
# Поход: зачин
# ---------------------------------------------------------------------------


def launch(rng, world, expedition, leader, side, mark, goal, spur,
           spur_ref: str) -> tuple:
    title = "%s: %s" % (expedition.name, goal.said)
    rows = []
    who = "%s (%s)" % (leader.name, ", ".join(leader.roles[:2])) \
        if leader is not None else "безымянный вожак"
    rows.append("%s снаряжает %s: цель — %s."
                % (_host_said(expedition, side), expedition.name.lower()
                   if expedition.name[:1].islower() else "поход", goal.said))
    rows.append("Отчего собрались: %s." % spur.line)
    rows.append("Чего ждут: %s." % spur.hope)
    rows.append("Ведёт %s." % who)
    haze = cat.HAZES_BY_KEY.get(expedition.haze)
    if haze is not None:
        rows.append("Насколько известно, куда идти: %s — %s."
                    % (haze.said, haze.about))
    rows.append("В отряде: %s." % _party_said(expedition))
    if expedition.gear:
        rows.append("Взяли с собой: %s." % _gear_said(expedition))
    blind = cat.blind_spots(expedition.roles)
    if blind:
        who_blind, what = blind[rng.randint(0, len(blind) - 1)]
        rows.append("Слабое место отряда: %s не увидит %s."
                    % (who_blind, what))
    if expedition.secret_aim:
        rows.append("У начальника похода своё: %s." % expedition.secret_aim)
    rows.append("Людей в отряде: %d %s."
                % (expedition.crew,
                   plural(expedition.crew, "человек", "человека",
                          "человек")))
    return title, " ".join(rows)


def _host_said(expedition, side) -> str:
    said = expedition.host_said or "держава"
    return "%s — %s" % (said[0].upper() + said[1:], side_said(side))


def _party_said(expedition) -> str:
    names = []
    for key in expedition.roles:
        role = cat.ROLES_BY_KEY.get(key)
        if role is not None:
            names.append(role.man)
    return ", ".join(names) if names else "кто попало"


def _gear_said(expedition) -> str:
    names = []
    for key in expedition.gear:
        gear = cat.GEAR_BY_KEY.get(key)
        if gear is not None:
            names.append(gear.said)
    return ", ".join(names)


# ---------------------------------------------------------------------------
# Поход: исход
# ---------------------------------------------------------------------------


def ending(rng, world, expedition, leader, mark, goal, end: str,
           survivors: int, finding) -> tuple:
    spec = cat.ENDS_BY_KEY.get(end)
    title = "%s: %s" % (expedition.name, end)
    rows = []
    rows.append("Поход по имени «%s» кончился так: %s."
                % (expedition.name, spec.about if spec is not None else end))
    if expedition.snags:
        rows.append("По дороге: %s." % "; ".join(expedition.snags))
    if expedition.turn:
        rows.append("Цель переменилась в %d году: %s."
                    % (expedition.turn_year, expedition.turn))
    if end == cat.E_GONE:
        rows.append("Из %d %s не вернулся никто."
                    % (expedition.crew,
                       plural(expedition.crew, "человека", "человек",
                              "человек")))
    elif expedition.deaths:
        rows.append("Вернулось %d %s, недосчитались %d."
                    % (survivors,
                       plural(survivors, "человек", "человека", "человек"),
                       expedition.deaths))
    else:
        rows.append("Вернулись все.")
    if finding is not None:
        rows.append(finding_said(world, finding))
    elif cat.end_tells(end):
        rows.append("Великого в этом нет: прибавилось точности, и только.")
    if expedition.told:
        rows.append("Сведения достались: %s."
                    % ", ".join(world.entity_name(key)
                                for key in expedition.told))
    return title, " ".join(rows)


def finding_said(world, finding) -> str:
    """Находка одной фразой — с тем, что о ней думают неверно."""
    rows = ["Записано как открытие: %s (%s)."
            % (finding.kind, finding.about_name)]
    if finding.about_name:
        rows[0] = "Записано как открытие: %s — %s." \
            % (finding.kind, named(finding.about_kind, finding.about_name))
    if finding.gained:
        rows.append("Что выяснили: %s."
                    % ", ".join(cat.aspect_name(key)
                                for key in finding.gained))
    fact = finding.prime.get(cat.P_FACT, "")
    fame = finding.prime.get(cat.P_FAME, "")
    if fact and fame and fact != fame:
        rows.append("Первым тут был не тот, кого таковым считают: по делу — "
                    "%s, по признанию — %s." % (fact, fame))
    if finding.twist:
        rows.append("Отчего так: %s." % finding.twist)
    if finding.wrong:
        rows.append("Поняли при этом неверно: %s." % finding.wrong)
    return " ".join(rows)


def finding_line(world, finding) -> str:
    """Строка о находке для летописи."""
    year = finding.found.year if finding.found is not None else 0
    line = "%d — %s: %s" % (year, finding.about_name, finding.kind)
    if finding.wrong and not finding.wrong_fixed:
        line += "; и до сих пор думают, что %s" % finding.wrong
    elif finding.wrong_fixed:
        line += "; ошибку выправили в %d году (%s)" % (finding.wrong_fixed,
                                                       finding.wrong_by)
    return line


# ---------------------------------------------------------------------------
# Встреча двух обществ
# ---------------------------------------------------------------------------


def first_read(rng, barrier: float, host) -> str:
    """Как пришедшие поняли то, что увидели, — и чаще всего неверно.

    Чем хуже объяснились, тем вероятнее, что в бумагах останется не
    народ, а чудовища, не просьба не входить, а вражда, не пастбище, а
    пустая земля.
    """
    if barrier > 0.65:
        return rng.choice((
            "решили, что перед ними не люди вовсе",
            "решили, что их прогоняют, хотя их просили не входить дальше",
            "решили, что земля пуста, а те, кого видели, — проходящие",
            "решили, что им грозят, потому что не разобрали ни слова"))
    if barrier > 0.35:
        return rng.choice((
            "поняли общее и переврали частности",
            "поняли, что тут живут, но не поняли, кто у них старший",
            "записали их имя так, как услышали, и имя получилось чужое",
            "сочли их обряд торгом, а торг — обрядом"))
    return rng.choice((
        "поняли, с кем говорят, и запомнили это верно",
        "разобрались, кто у них старший и о чём с ним говорить",
        "записали их имя так, как они сами себя называют",
        "поняли, что им тут не рады, и поняли, отчего"))


def after_meeting(rng, outcome: str, barrier: float) -> str:
    good = cat.MEET_END_MOOD.get(outcome, 0.0)
    if good <= -0.6:
        return rng.choice((
            "отношений не завелось: одни помнят обиду, другие — страх",
            "с того дня к ним ходят с оружием, а они встречают так же"))
    if good <= -0.1:
        return rng.choice((
            "ходить друг к другу стали редко и с оглядкой",
            "о них говорят дурно, и они о пришедших тоже"))
    if barrier > 0.5:
        return rng.choice((
            "договорились о малом и разошлись, не поняв большего",
            "обменялись дарами и остались каждый при своём"))
    return rng.choice((
        "с того года между ними завелись постоянные дела",
        "стали ходить друг к другу, и дорога перестала быть страшной",
        "поставили обычай встречаться в одном и том же месте"))


def meeting_versions(world, meeting, side, host) -> list:
    """Одно событие, две памяти — и обе остаются в летописи."""
    rows = [
        {"кто": side.name,
         "как помнит": "открытие народа по имени %s" % host.name},
        {"кто": host.name,
         "как помнит": "появление чужаков: %s" % meeting.local_eyes},
    ]
    if meeting.barrier > 0.5:
        rows.append({"кто": "позднейшие книжники",
                     "как помнит": "первая встреча, о которой обе стороны "
                                   "рассказывают несовместимое"})
    return rows


def meeting(rng, world, meeting_row, side, host, leader) -> tuple:
    title = "Встреча: %s и народ по имени %s" % (side.name, host.name)
    rows = ["%s впервые сошёлся с народом по имени %s: %s."
            % (side_said(side, upper=True), host.name, meeting_row.kind)]
    if meeting_row.shut_why:
        rows.append("Отчего о них не знали: %s." % meeting_row.shut_why)
    rows.append("Объяснялись так: %s." % ", ".join(meeting_row.speech))
    rows.append("Поняли при этом так: %s." % meeting_row.read_as)
    rows.append("Для живущих там это было вот что: %s."
                % meeting_row.local_eyes)
    rows.append("Кончилось это так: %s." % meeting_row.outcome)
    rows.append("А дальше — %s." % meeting_row.after)
    return title, " ".join(rows)


# ---------------------------------------------------------------------------
# Освоение
# ---------------------------------------------------------------------------


def hold_purpose(rng, kind: str, expedition) -> str:
    base = {
        cat.H_CAMP: "перезимовать и уйти",
        cat.H_STATION: "описать округу, пока помнят дорогу",
        cat.H_POST: "держать место, куда свозят товар",
        cat.H_PORT: "дать кораблям, где стать",
        cat.H_FORT: "держать землю, пока её не займёт другой",
        cat.H_SETTLE: "посадить на землю тех, кому дома тесно",
        cat.H_MINE: "брать из земли то, за чем шли",
        cat.H_MISSION: "поставить обитель и учить вере",
        cat.H_BASE: "иметь, откуда ходить дальше",
        cat.H_COLONY: "жить по-своему вдали от прежней власти",
        cat.H_JOINED: "записать землю за державой",
        cat.H_GUEST: "жить тут с дозволения хозяев",
        cat.H_SHARED: "жить вместе с теми, кто тут уже живёт",
    }.get(kind, "держать место")
    if expedition is not None and expedition.goal:
        goal = cat.GOALS_BY_KEY.get(expedition.goal)
        if goal is not None and rng.chance(0.5):
            return "%s — то, зачем ходил поход (%s)" % (base, goal.said)
    return base


def locals_answer(rng, use_key: str, kind: str, folk) -> str:
    """Чем ответили те, кто этой землёй пользовался до прихода."""
    name = folk.name if folk is not None else ""
    if use_key == "none":
        return "спрашивать было некого: той землёй не пользовался никто"
    if use_key == "lord":
        return rng.choice((
            "хозяин той земли потребовал дани и получил её",
            "хозяин той земли позволил стоять, пока платят",
            "хозяин той земли не позволил ничего, и это узнали сразу"))
    who = "народ по имени %s" % name if name else "живущие там"
    heavy = kind in (cat.H_FORT, cat.H_JOINED, cat.H_MINE, cat.H_SETTLE)
    pool = [
        ("с %s договорились о земле и о границах" % who, 1.2),
        ("%s позволил стоять, но не пахать" % who, 1.0),
        ("с %s сговорились на доле добытого" % who, 0.9),
        ("%s не потерпел пришедших и выжил их через поколение" % who,
         1.4 if heavy else 0.6),
        ("%s ушёл с той земли дальше, не вступая в спор" % who, 0.8),
        ("о %s не спрашивали вовсе, и это потом припомнили" % who,
         1.3 if heavy else 0.5),
        ("пришедшие и %s стали жить вместе и перемешались" % who, 0.7),
    ]
    return rng.weighted(pool)


def supply_line(rng, world, side, region) -> str:
    home = world.regions.get(side.home)
    if home is None or home.id == region.id:
        return "кормятся тем, что берут тут же"
    if region.id in home.sea_links or home.id in region.sea_links:
        return "всё везут морем от земли по имени %s" % home.name
    return "всё везут по суше от земли по имени %s" % home.name


def settling(rng, world, settling_row, side, region) -> tuple:
    spec = cat.HOLDS_BY_KEY.get(settling_row.kind)
    title = "%s: земля по имени %s" % (settling_row.kind.capitalize(),
                                       region.name)
    rows = ["%s ставит в земле по имени %s: %s."
            % (side_said(side, upper=True), region.name,
               spec.about if spec is not None else settling_row.kind)]
    rows.append("Зачем: %s." % settling_row.purpose)
    rows.append("Как землёй пользовались до них: %s."
                % settling_row.locals_use)
    rows.append("Чем ответили здешние: %s." % settling_row.locals_answer)
    rows.append("Снабжение: %s." % settling_row.supply)
    rows.append("Людей: %d." % settling_row.settlers)
    rows.append("Нанесённая на карту земля своей от этого не становится: "
                "тут ещё надо прижиться.")
    return title, " ".join(rows)


def settling_failed(rng, world, settling_row) -> tuple:
    region = world.regions.get(settling_row.region_id)
    where = region.name if region is not None else "той земле"
    title = "Не прижилось: %s в земле по имени %s" \
        % (settling_row.kind, where)
    years = 0
    if settling_row.started is not None and settling_row.ended is not None:
        years = settling_row.ended.year - settling_row.started.year
    rows = ["То, что ставили в земле по имени %s, брошено через %d %s."
            % (where, years, plural(years, "год", "года", "лет"))]
    rows.append("Отчего: %s." % settling_row.fail_why)
    rows.append("Знание при этом осталось: дорогу туда теперь знают, и "
                "знают, чего там делать нельзя.")
    return title, " ".join(rows)


def settling_rooted(rng, world, settling_row) -> tuple:
    region = world.regions.get(settling_row.region_id)
    where = region.name if region is not None else "той земле"
    title = "Прижилось: %s в земле по имени %s (%s)" \
        % (settling_row.kind, where, settling_row.result)
    rows = ["То, что ставили в земле по имени %s, прижилось: %s."
            % (where, settling_row.result)]
    town = world.settlements.get(settling_row.settlement_id)
    if town is not None:
        rows.append("Теперь это поселение по имени %s." % town.name)
    if settling_row.locals_folk:
        folk = world.folks.get(settling_row.locals_folk)
        if folk is not None:
            rows.append("Для народа по имени %s это значит, что землю "
                        "придётся делить." % folk.name)
    return title, " ".join(rows)


# ---------------------------------------------------------------------------
# Утрата знания, споры и исправления
# ---------------------------------------------------------------------------


def knowledge_lost(rng, world, record) -> tuple:
    title = "Забыто: %s" % record.about_name
    rows = ["То, что знали о %s по имени %s, потеряно: %s."
            % (_kind_word(record.about_kind), record.about_name,
               record.lost_why)]
    if record.group_id:
        rows.append("Потеряно у тех, кто знал: %s."
                    % world.entity_name(record.group_id))
    if record.kept:
        rows.append("Уцелело вот что: %s." % record.kept)
    rows.append("Через век туда пойдут снова и назовут это открытием.")
    return title, " ".join(rows)


def _kind_word(kind: str) -> str:
    """Родовое слово в предложном падеже: «о земле», «о месте»."""
    return _mark_word_of(kind, "pre")


def credit_row(rng, world, finding, claimer) -> tuple:
    title = "Спор о первенстве: %s" % finding.about_name
    rows = ["О том, кто первым дошёл до %s, спорят: %s."
            % (named(finding.about_kind, finding.about_name, "gen"),
               " и ".join(str(row.get("кто")) for row in finding.claims))]
    for row in finding.claims:
        rows.append("%s — %s (%s год)." % (row.get("кто"), row.get("на чём"),
                                           row.get("год")))
    fact = finding.prime.get(cat.P_FACT, "")
    if fact:
        rows.append("По делу же первым был %s — и спорящих это не занимает."
                    % fact)
    return title, " ".join(rows)


def wrong_fixed(rng, world, finding) -> tuple:
    title = "Выправлено: %s" % finding.about_name
    rows = ["О том, что такое %s, думали неверно: %s."
            % (named(finding.about_kind, finding.about_name),
               finding.wrong)]
    rows.append("Выправил это %s." % finding.wrong_by)
    rows.append("Находка была сделана раньше, а поняли её только теперь — "
                "это два разных дела.")
    return title, " ".join(rows)


def personal_goal(rng, goal, expedition) -> str:
    """Своя цель человека: она не обязана совпадать с поручением."""
    pool = (
        "дойти туда, куда до него не доходил никто из своих",
        "положить на бумагу то, что до него описывали словами",
        "найти тех, кто ушёл и не вернулся",
        "доказать, что старая карта врёт",
        "разобрать язык, на котором с ним говорили знаками",
        "вернуться и быть выслушанным",
        "кончить то, что начал его учитель",
        "понять, чем было то, что он нашёл",
    )
    if expedition is not None and expedition.secret_aim and rng.chance(0.5):
        return expedition.secret_aim
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# Строки для карточек: что о месте знают и кто о нём ходил
# ---------------------------------------------------------------------------


def about(world, record) -> list:
    """Одна запись о знании словами — для страницы места и для летописи."""
    rows = []
    who = world.entity_name(record.group_id) or "неизвестно кто"
    state = "%s — %s" % (record.level, cat.level_about(record.level))
    rows.append("%s: %s" % (who, state))
    if record.source:
        rows.append("  откуда: %s" % cat.source_said(record.source))
    if record.since is not None:
        rows.append("  с какого года: %d" % record.since.year)
    if record.aspects:
        known = [cat.aspect_name(key) for key, value
                 in sorted(record.aspects.items()) if cat.is_known(value)]
        dark = [cat.aspect_name(key) for key, value
                in sorted(record.aspects.items()) if not cat.is_known(value)]
        if known:
            rows.append("  знают: %s" % ", ".join(known))
        if dark:
            rows.append("  не знают: %s" % ", ".join(dark))
    if record.muddle:
        rows.append("  по дороге исказилось: %s" % record.muddle)
    if record.trust or record.truth:
        rows.append("  верят на %d из 10, а верно это на %d из 10"
                    % (int(round(record.trust * 10)),
                       int(round(record.truth * 10))))
    if record.access != "открыто":
        rows.append("  доступ: %s%s" % (record.access,
                                        " — %s" % record.secret_why
                                        if record.secret_why else ""))
    if record.lost_year:
        rows.append("  знание потеряно в %d году: %s"
                    % (record.lost_year, record.lost_why))
        if record.kept:
            rows.append("  уцелело: %s" % record.kept)
    return rows


def place_knowing(world, about_id: str, limit: int = 4) -> list:
    """Что об этом месте знают разные общества — и кто не знает ничего.

    Это главный ответ модуля на странице места: не «земля известна», а
    «живущим известна подробно, соседям по рассказам, а державе за
    морем — никак». Показывается по одному голосу на состояние, а не
    все двадцать пять: двадцать пять одинаковых строк «знают живущие»
    говорят ровно то же, что одна, и прячут за собой единственную
    важную — ту, где знание расходится с правдой.
    """
    rows = []
    records = world.knowings_about(about_id, known_only=False)
    if not records:
        return rows
    live = [item for item in records if item.known]
    lost = [item for item in records if item.lost_year]
    if live:
        counts = {}
        for record in live:
            counts[record.level] = counts.get(record.level, 0) + 1
        rows.append("Знают о нём: %d %s — %s."
                    % (len(live),
                       plural(len(live), "общество", "общества", "обществ"),
                       ", ".join("%s %d" % pair for pair
                                 in sorted(counts.items(),
                                           key=lambda row: -row[1]))))
        # По одному голосу на состояние, от самого основательного знания
        # к самому слабому: так видно расстояние между теми, кто тут
        # живёт, и теми, кто слышал.
        seen = set()
        voices = []
        for record in sorted(live, key=lambda item:
                             (-cat.level_depth(item.level), item.id)):
            if record.level in seen:
                continue
            seen.add(record.level)
            voices.append(record)
            if len(voices) >= max(1, limit):
                break
        for record in voices:
            rows.append(_voice(world, record))
    for record in lost[:2]:
        line = "%s: знали и потеряли (%d год, %s)" \
            % (world.entity_name(record.group_id), record.lost_year,
               record.lost_why)
        if record.kept:
            line += "; уцелело: %s" % record.kept
        rows.append(line)
    return rows


def _voice(world, record) -> str:
    """Один голос о месте одной строкой: кто, насколько и откуда."""
    who = world.entity_name(record.group_id) or "неизвестно кто"
    parts = ["%s: %s" % (who, record.level)]
    tail = []
    if record.source:
        tail.append(cat.source_said(record.source))
    if record.since is not None:
        tail.append("с %d года" % record.since.year)
    if tail:
        parts.append("(%s)" % ", ".join(tail))
    dark = [cat.aspect_name(key) for key, value
            in sorted(record.aspects.items()) if not cat.is_known(value)]
    if dark:
        parts.append("— не знают: %s" % ", ".join(dark[:4]))
    if record.muddle:
        parts.append("— дошло искажённым: %s" % record.muddle)
    if record.access != "открыто":
        parts.append("— %s%s" % (record.access,
                                 ": %s" % record.secret_why
                                 if record.secret_why else ""))
    if record.trust or record.truth:
        parts.append("[верят на %d из 10, верно на %d]"
                     % (int(round(record.trust * 10)),
                        int(round(record.truth * 10))))
    return " ".join(parts)


def explorer_lines(world, explorer, figure) -> list:
    """Блок исследователя в карточке личности."""
    rows = []
    if explorer.trades:
        rows.append("Занятие: %s"
                    % ", ".join(cat.trade_name(key, figure.sex)
                                for key in explorer.trades))
    if explorer.drives:
        rows.append("Что вело: %s" % "; ".join(explorer.drives))
    if explorer.goal:
        rows.append("Своя цель: %s" % explorer.goal)
    for expedition_id in explorer.expeditions:
        expedition = world.expeditions.get(expedition_id)
        if expedition is None:
            continue
        rows.append("Поход «%s» (%d): %s"
                    % (expedition.name, expedition.start.year,
                       expedition.result or expedition.outcome or "в пути"))
    for finding_id in explorer.findings:
        finding = world.findings.get(finding_id)
        if finding is not None:
            rows.append("Открытие: %s" % finding_line(world, finding))
    for chart_id in explorer.charts:
        chart = world.charts.get(chart_id)
        if chart is None:
            continue
        # Род карты в записи лежит ключом («peril»), а в летопись идёт
        # словами: ключи справочников в русский вывод не выпускаются.
        spec = cat.CHART_KINDS_BY_KEY.get(chart.kind)
        rows.append("Карта «%s» (%s)"
                    % (chart.name, spec.said if spec is not None
                       else chart.kind))
    if explorer.patrons:
        rows.append("Снаряжали: %s" % ", ".join(explorer.patrons))
    if explorer.tongues:
        rows.append("Языки: %s" % ", ".join(explorer.tongues))
    if explorer.fame:
        parts = []
        for group_id, word in sorted(explorer.fame.items()):
            parts.append("%s — %s" % (world.entity_name(group_id), word))
        rows.append("Каким его помнят: %s" % "; ".join(parts))
    if explorer.credit:
        rows.append("Признание: %s" % explorer.credit)
    if explorer.unsolved:
        rows.append("Чем кончилось: %s" % explorer.unsolved)
    return rows
