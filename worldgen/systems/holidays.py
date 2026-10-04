# -*- coding: utf-8 -*-
"""Жизнь праздника: как событие становится днём, а день — чем-то другим.

Раз в десять лет система делает две вещи.

**Ищет повод.** Не придумывает праздник, а смотрит, не случилось ли в
мире за последние десятилетия чего-то, к чему люди захотят возвращаться:
кончилась война, отступил мор, отбили нашествие, основали державу,
убили чудовище, явился бог, умер тот, кого после сочли праведником.
Если повод нашёлся — заводится **поминовение**. Ещё не праздник: просто
в этот день приходят на то же место.

**Ведёт тех, что уже есть.** Поминовение либо дорастает до обычая,
обряда, праздника и установления, либо тает вместе с теми, кто помнил, —
и тает чаще, чем дорастает. Дошедший до верха день живёт дальше своей
жизнью: его присваивает держава или храм, переправляют, запрещают, он
уходит в подполье, возрождается, раскалывается из-за спора о счёте,
сливается с чужим днём, сжимается до одного села.

Отдельно и важнее всего — **потеря повода**. Спросить становится
некого, запись горит, приходит другой народ и объясняет день по-своему.
Обряды при этом не исчезают: костёр жгут, маски надевают, третий хлеб
кладут нетронутым — только зачем, уже не говорят, а если говорят, то
неправду. Это не поломка памяти, а её обычная работа; и именно тут
берутся загадки для былей.

Что система нарочно **не** делает: не заводит праздник на каждое
событие (повод берётся редко и по весу), не держит дни вечно (без
держателя и без людей день гаснет) и не трогает богов — у божества
праздник уже есть в `religion.py`, и божественный день его **берёт
себе**, а не ставит второй рядом.
"""

from __future__ import annotations

from .. import holidays as cat
from .. import monsters as monsters_mod
from .. import narrative_holiday as texts
from ..models import ACTIVE, ONGOING
from ..timeline import DAYS_IN_MONTH, MONTHS_IN_YEAR

# На сколько лет назад система смотрит, когда ищет повод. Больше такта:
# иначе события, случившиеся в середине десятилетия, терялись бы, а
# праздник из них вырастает не в тот же год — люди сперва должны понять,
# что это был за день.
LOOK_BACK = 40

# Шанс, что за такт в мире завёлся новый день памяти. Выходит примерно
# один на сорок лет на весь мир: за десять тысяч лет это две-три сотни
# поминовений, из которых до конца истории доживают десятки. Так и
# задумано: праздник — редкость, иначе календарь перестаёт что-то
# значить.
BIRTH_CHANCE = 0.26

# Сколько дней мир несёт одновременно. Упор не для скорости, а для
# смысла: если праздников триста, то праздника нет ни одного.
MAX_KEPT = 140

# Сколько лет поминовение держится, прежде чем начнёт таять, если не
# поднялось ступенью. Два поколения — столько живёт живая память.
MEMORY_PATIENCE = 90

# Шансы за такт.
CLIMB_CHANCE = 0.07        # подняться ступенью (пока день молод и жив)
FADE_MEMORY = 0.10         # растаять, оставшись поминовением
FADE_FEAST = 0.004         # угаснуть, будучи настоящим праздником
TURN_CHANCE = 0.030        # один поворот судьбы — раз в несколько веков
LOSE_WHY_FROM = 300        # с какого возраста повод вообще может забыться
LOSE_WHY_CHANCE = 0.016    # и с каким шансом за такт
VARIANT_CHANCE = 0.02      # что день переняли на свой лад
DOING_CHANCE = 0.012       # что на самом празднике что-то случилось
MARK_CHANCE = 0.03         # что ради дня в мире что-то построили
SIDES_FROM = 2             # со скольких правд день считается спорным

# Сколько душ нужно, чтобы день держался своим ходом. Ниже этого он
# угасает не от запрета, а просто потому, что приходить стало некому.
SOULS_FLOOR = 400

# Какие ступени считаются «настоящим праздником» для меры угасания.
_YOUNG = (cat.STEP_MEMORY, cat.STEP_CUSTOM)


# ---------------------------------------------------------------------------
# Такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("holiday-born", year)
    kept = len(world.holidays_kept())
    if kept < MAX_KEPT and rng.chance(BIRTH_CHANCE):
        _born(ctx, rng, year)
    # Порядок обхода — по идентификатору: он не зависит ни от словаря, ни
    # от того, в каком году что завелось.
    for holiday_id in sorted(world.holidays, key=_id_key):
        _live(ctx, world.holidays[holiday_id], year, period)


def _id_key(holiday_id: str):
    return (len(holiday_id), holiday_id)


# ---------------------------------------------------------------------------
# Поиск повода
# ---------------------------------------------------------------------------

class Node:
    """Повод, из которого может вырасти день памяти.

    `about` — имя того поля, которое и есть повод. Узел знает это сам:
    день, заведённый на находку, помнит и беду, от которой след остался,
    но поминает он находку. Без этого на одну беду заводилось два
    праздника, и оба говорили, что поминают именно её.
    """

    __slots__ = ("origin", "what", "year", "links", "about", "holder",
                 "region_id", "weight")

    def __init__(self, origin, what, year, links=None, about="", holder="",
                 region_id="", weight=1.0):
        self.origin = origin
        self.what = what
        self.year = int(year)
        self.links = dict(links or {})
        # Если узел не назвал повод, им считается его единственная
        # привязка. Когда привязок несколько, догадываться нельзя — и
        # поводом не считается ничто: у сезонного дня события и нет, он
        # заводится оттого, что народу нужен хоть один день в году.
        self.about = about or (sorted(self.links)[0]
                               if len(self.links) == 1 else "")
        self.holder = holder
        self.region_id = region_id
        self.weight = float(weight)


def _fresh(date, year: int) -> bool:
    """Случилось ли это достаточно недавно, чтобы помнить."""
    return date is not None and 0 <= year - date.year <= LOOK_BACK


def _nodes(ctx, year: int) -> list:
    """Всё, к чему мир прямо сейчас может захотеть возвращаться."""
    world = ctx.world
    out = []
    taken = _already(world)
    # Устройство мира тут не справка, а запрет. Если магии в мир не
    # положили, то и чудес в нём не бывает — значит и праздника чуда
    # завести нельзя, сколько бы богов ни было.
    missing = set(world.origin.missing) if world.origin is not None else set()
    barred = set()
    if "магия" in missing:
        barred.update(("чудо", "обретение святыни", "закрытие провала"))
    if "душа" in missing:
        barred.add("смерть праведника")

    # --- войны ---------------------------------------------------------
    for war in world.wars.values():
        if war.status == ONGOING or not _fresh(war.end, year):
            continue
        won = war.outcome in ("победа нападавших", "победа оборонявшихся")
        winner = war.attacker_id if war.outcome == "победа нападавших" \
            else war.defender_id
        polity = world.polities.get(winner)
        links = {"war_id": war.id, "polity_id": winner}
        if won and polity is not None:
            out.append(Node("победа в войне",
                            "война по имени %s кончилась победой" % war.name,
                            war.end.year, links, about="war_id",
                            region_id=_first(polity.region_ids),
                            weight=1.0 + 0.4 * max(0, war.scale - 2)))
        if war.peace_name:
            out.append(Node("заключение мира",
                            "был заключён мир под именем %s" % war.peace_name,
                            war.end.year, links, about="war_id",
                            weight=0.7))
        out.append(Node("конец войны",
                        "война по имени %s наконец кончилась" % war.name,
                        war.end.year, links, about="war_id",
                        weight=0.8 + 0.3 * max(0, war.scale - 3)))
        if war.civil_losses + war.attacker_losses + war.defender_losses > 0:
            out.append(Node("день павших",
                            "с войны по имени %s не вернулось слишком много"
                            % war.name, war.end.year, links, about="war_id",
                            weight=0.7))

    # --- беды -----------------------------------------------------------
    for woe in world.calamities.values():
        if woe.end is None or not _fresh(woe.end, year):
            continue
        links = {"calamity_id": woe.id}
        region = _first(woe.region_ids)
        heavy = 1.0 + 0.5 * max(0, woe.severity - 3)
        if woe.key == "plague":
            origin = "пережитый мор"
        elif woe.key == "famine":
            origin = "конец голода"
        elif woe.kind == "invasion":
            origin = "изгнание пришедших"
        else:
            origin = "конец беды"
        out.append(Node(origin,
                        "беда по имени %s отступила" % woe.name,
                        woe.end.year, links, region_id=region, weight=heavy))
        if woe.severity >= 4:
            out.append(Node("спасение народа",
                            "от беды по имени %s народ едва уцелел" % woe.name,
                            woe.end.year, links, region_id=region,
                            weight=0.8))
        if woe.kind == "magic" and woe.severity >= 3:
            out.append(Node("закрытие провала",
                            "то, откуда шла беда по имени %s, закрыли"
                            % woe.name, woe.end.year, links,
                            region_id=region, weight=0.7))

    # --- нашествия ------------------------------------------------------
    for raid in world.invasions.values():
        if raid.ended is None or not _fresh(raid.ended, year):
            continue
        if raid.outcome not in ("истреблены", "разбиты", "отбиты", "заперты",
                                "изгнаны"):
            continue
        out.append(Node("изгнание пришедших",
                        "пришедших под именем %s выгнали с этой земли"
                        % _invasion_name(raid),
                        raid.ended.year,
                        {"invasion_id": raid.id,
                         "calamity_id": raid.calamity_id},
                        about="invasion_id",
                        region_id=raid.entry_region, weight=1.3))

    # --- державы и государи ---------------------------------------------
    for polity in world.polities.values():
        if _fresh(polity.founded, year):
            out.append(Node("основание державы",
                            "держава по имени %s стала державой" % polity.name,
                            polity.founded.year, {"polity_id": polity.id},
                            region_id=_first(polity.region_ids), weight=1.0))
    for reign in world.reigns.values():
        polity = world.polities.get(reign.polity_id)
        if polity is None:
            continue
        # Законность — слово, а не число: праздник венчания заводят
        # только там, где венец взяли по праву. На узурпации праздника
        # не бывает — бывает запрет чужого.
        if _fresh(reign.start, year) \
                and reign.legitimacy in ("законное", "избрание",
                                         "основание", "по брачному праву"):
            out.append(Node("венчание государя",
                            "на голову нового государя державы по имени %s"
                            " положили венец" % polity.name,
                            reign.start.year,
                            {"polity_id": polity.id,
                             "figure_id": reign.ruler_id},
                            about="figure_id", weight=0.5))
        if reign.end is not None and _fresh(reign.end, year):
            # Слова взяты те же, какими правление закрывают на деле:
            # «свергнут восставшими», «заговор», «смута», «междоусобица».
            if reign.end_reason in ("свергнут восставшими", "заговор",
                                    "смута", "междоусобица"):
                out.append(Node("падение тирана",
                                "того, кто правил державой по имени %s,"
                                " сбросили" % polity.name,
                                reign.end.year,
                                {"polity_id": polity.id,
                                 "figure_id": reign.ruler_id},
                                about="figure_id", weight=0.9))
            elif reign.end_reason == "смерть" and reign.score >= 1.0:
                out.append(Node("смерть государя",
                                "государь державы по имени %s умер, и его"
                                " помнят добром" % polity.name,
                                reign.end.year,
                                {"polity_id": polity.id,
                                 "figure_id": reign.ruler_id},
                                about="figure_id", weight=0.5))

    # --- города ---------------------------------------------------------
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if not _fresh(settlement.founded, year):
            continue
        if settlement.population < 900:
            continue
        out.append(Node("основание города",
                        "на этом месте встал город по имени %s"
                        % settlement.name,
                        settlement.founded.year,
                        {"settlement_id": settlement.id,
                         "polity_id": settlement.polity_id,
                         "folk_id": settlement.folk_id},
                        about="settlement_id",
                        region_id=settlement.region_id, weight=0.8))

    # --- боги и храмы ---------------------------------------------------
    for deity in world.deities.values():
        if not _fresh(deity.revealed, year):
            continue
        origin = "рождение бога" if deity.primordial else "явление бога"
        if origin in barred:
            continue
        out.append(Node(origin,
                        "божество по имени %s открылось людям"
                        % deity.given_name,
                        deity.revealed.year,
                        {"deity_id": deity.id, "faith_id": deity.faith_id},
                        about="deity_id", weight=1.1))
    for temple in world.temples.values():
        if not _fresh(temple.founded, year):
            continue
        if temple.grandeur < 2:
            continue
        out.append(Node("основание храма",
                        "храм по имени %s поставили на этом месте"
                        % temple.name,
                        temple.founded.year,
                        {"temple_id": temple.id,
                         "faith_id": temple.faith_id,
                         "deity_id": temple.deity_id,
                         "settlement_id": temple.settlement_id},
                        # Повод тут — сам храм, а не вера: иначе второй
                        # храм той же веры поминался бы как первый, и
                        # выходило, что одно событие помнят дважды.
                        about="temple_id",
                        region_id=temple.region_id, weight=0.5))

    # --- чудовища -------------------------------------------------------
    for beast in world.monsters.values():
        if beast.status != monsters_mod.SLAIN or not _fresh(beast.ended, year):
            continue
        origin = "победа над чудовищем" if beast.power >= 3 \
            else "чудовище у села"
        out.append(Node(origin,
                        "%s по имени %s был убит" % (beast.word, beast.name),
                        beast.ended.year,
                        {"monster_id": beast.id,
                         "figure_id": beast.slayer_id,
                         "settlement_id": beast.settlement_id},
                        about="monster_id", region_id=beast.region_id,
                        weight=0.8 + 0.2 * beast.power))

    # --- те, кого смертными не назовёшь ---------------------------------
    for subject in world.subjects.values():
        if subject.kind in ("человек", "народ мира"):
            continue
        if not subject.end:
            continue
        if not _fresh(subject.ended, year):
            continue
        out.append(Node("падение владыки",
                        "того, кого звали %s, не стало" % subject.name,
                        subject.ended.year, {"subject_id": subject.id},
                        about="subject_id", weight=1.0))

    # --- люди, которых помнят -------------------------------------------
    for renown in world.renowns.values():
        figure = world.figures.get(renown.figure_id)
        if figure is None or figure.death is None:
            continue
        if not _fresh(figure.death, year):
            continue
        if renown.level < 6:
            continue
        holy = figure.divine_mark or figure.patron_deity_id
        origin = "смерть праведника" if holy else "местный герой"
        out.append(Node(origin,
                        "тот, кого звали %s, умер" % figure.given_name,
                        figure.death.year,
                        {"figure_id": figure.id,
                         "settlement_id": figure.home_id,
                         "faith_id": figure.faith_id},
                        about="figure_id", region_id=figure.origin_region,
                        weight=0.5 + 0.12 * (renown.level - 5)))

    # --- цеха -----------------------------------------------------------
    for guild in world.guilds.values():
        if not _fresh(guild.founded, year):
            continue
        out.append(Node("основание цеха",
                        "ремесло собралось в цех по имени %s" % guild.name,
                        guild.founded.year,
                        {"guild_id": guild.id, "polity_id": guild.polity_id,
                         "settlement_id": guild.seat_id},
                        about="guild_id", weight=0.4))

    # --- законы ---------------------------------------------------------
    for law in world.laws.values():
        if not _fresh(law.made, year):
            continue
        if not law.famous:
            continue        # праздник заводят не на всякую приписку
        out.append(Node("великая перемена закона",
                        "закон по имени %s переменил то, как тут живут"
                        % law.name,
                        law.made.year, {"law_id": law.id,
                                        "polity_id": law.polity_id},
                        # И тут повод — сам закон: «law» именем поля не
                        # было, и сторож на него не срабатывал вовсе.
                        about="law_id", weight=0.3))

    # --- старые находки -------------------------------------------------
    for trace in world.traces.values():
        if trace.found is None or not _fresh(trace.found, year):
            continue
        out.append(Node("старая находка",
                        "из земли достали %s" % trace.name,
                        trace.found.year,
                        {"trace_id": trace.id,
                         "calamity_id": trace.calamity_id},
                        about="trace_id",
                        region_id=trace.region_id, weight=0.4))

    # --- времена года и людское -----------------------------------------
    # Эти дни ни от какого события не растут: их заводит сам народ,
    # которому нужен хоть один день в году. Поэтому берутся они только у
    # тех, у кого такого дня ещё нет.
    for folk in world.folks.values():
        if folk.status != ACTIVE or folk.population < 12000:
            continue
        if _folk_has_season(world, folk.id):
            continue
        for key in ("жатва", "самая долгая ночь", "начало весны",
                    "день предков", "первый снег", "совершеннолетие",
                    "первая борозда", "свадебная пора", "день рода",
                    "начало охоты"):
            out.append(Node(key,
                            "народу по имени %s нужен был свой день в году"
                            % folk.name, max(1, year - 10),
                            {"folk_id": folk.id, "race_id": folk.race_id},
                            region_id=folk.cradle_region, weight=0.26))

    # Отсев один и в самом конце — так его не забыть добавить к новому
    # поводу. Отсеивается то, чего в этом мире быть не может, и то, что
    # уже заведено на то же самое событие.
    return [node for node in out
            if node.origin not in barred
            and (node.about, node.links.get(node.about, ""), node.origin)
            not in taken]


# Какое поле праздника в каком реестре мира проверяется. Нужно потому,
# что привязки приходят из чужих рук: `figure.home_id`, например, держит
# то поселение, где человек жил, — а у основателя колонии дома ещё нет, и
# там лежит номер земли (`systems/founding`). Слепо переложить это в
# `settlement_id` значит привязать праздник к городу, которого нет; эту
# дыру нашла собственная проверка на десятитысячелетнем мире.
LINK_TABLES = {
    "war_id": "wars", "calamity_id": "calamities",
    "invasion_id": "invasions", "monster_id": "monsters",
    "figure_id": "figures", "deity_id": "deities", "guild_id": "guilds",
    "trace_id": "traces", "subject_id": "subjects", "polity_id": "polities",
    "settlement_id": "settlements", "folk_id": "folks",
    "faith_id": "faiths", "house_id": "houses", "race_id": "",
    "temple_id": "temples", "law_id": "laws",
}


def _clean_links(world, links: dict) -> dict:
    """Выбрасывает привязки к тому, чего в мире нет.

    Чистится после жребия, а не до: порядок обращений к ГСЧ от этого не
    меняется, и миры остаются теми же — меняется только то, что праздник
    больше не ссылается в пустоту.
    """
    out = {}
    for field, value in links.items():
        if not value:
            continue
        table = LINK_TABLES.get(field)
        if table is None:
            continue            # такого поля у праздника нет
        if table and value not in getattr(world, table, {}):
            continue            # ссылка в пустоту
        out[field] = value
    return out


def _already(world) -> set:
    """Что мир уже поминает: второй день на то же событие не заводят.

    Событие — это не лицо и не повод врознь, а их пара. Одного лица мало:
    венчание государя и его смерть — два разных дня об одном человеке, и
    мир вправе держать оба. Одного повода мало тоже: храмов у одной веры
    много, и день каждого — свой. Поэтому ключ тройной: к чему привязан
    день, что это за привязка и из какого повода он вырос.

    В счёт идёт только повод (`about`), а не вся родня: иначе праздник
    находки закрывал бы дорогу празднику той беды, от которой след
    остался, — а это два разных дня о двух разных вещах.
    """
    out = set()
    for holiday in world.holidays.values():
        if not holiday.about:
            continue
        value = getattr(holiday, holiday.about, "")
        if value:
            out.add((holiday.about, value, holiday.origin))
    return out


def _folk_has_season(world, folk_id: str) -> bool:
    for holiday in world.holidays.values():
        if holiday.folk_id != folk_id:
            continue
        if holiday.group in (cat.SEASONAL, cat.HUMAN) and holiday.kept:
            return True
    return False


def _first(rows) -> str:
    return rows[0] if rows else ""


def _invasion_name(raid) -> str:
    """Как нашествие звали. Имён у него несколько — берём любое, но
    всегда одно и то же: словарь обходится по отсортированным голосам."""
    if raid.names:
        for voice in sorted(raid.names):
            return raid.names[voice]
    return raid.title


# ---------------------------------------------------------------------------
# Рождение
# ---------------------------------------------------------------------------

def _born(ctx, rng, year: int) -> None:
    world = ctx.world
    rows = _nodes(ctx, year)
    if not rows:
        return
    pairs = []
    for node in rows:
        origin = cat.ORIGINS.get(node.origin)
        if origin is None:
            continue
        pairs.append((node, node.weight * origin.weight))
    if not pairs:
        return
    node = rng.weighted(pairs)
    origin = cat.ORIGINS[node.origin]

    mood = origin.mood
    also = ""
    # День после большой беды бывает радостным и траурным сразу — и это
    # самое верное, что о нём можно сказать.
    if origin.group == cat.AFTER_WOE and rng.chance(0.45):
        also = cat.MOURNFUL if mood != cat.MOURNFUL else cat.GLAD

    holder = node.holder or origin.holder
    holder = _fit_holder(world, holder, node.links)
    taken = {item.name for item in world.holidays.values()}
    deity = world.deities.get(node.links.get("deity_id", ""))

    # У божества праздник уже есть: божественный день берёт его себе, а
    # не ставит второй рядом. Иначе у одного бога окажется два праздника,
    # и ни один не будет его.
    if deity is not None and deity.festival_name \
            and deity.festival_name not in taken \
            and origin.group == cat.DIVINE:
        name = deity.festival_name
        month, day = deity.festival_month, deity.festival_day
        rule = cat.DATE_MOVING if rng.chance(0.3) else cat.DATE_FIXED
    else:
        name = texts.make_name(rng, origin, mood, taken)
        month, day, rule = _pick_date(rng, origin, node, world)

    links = _clean_links(world, node.links)
    if node.about and node.about in LINK_TABLES \
            and not links.get(node.about):
        return      # повода нет в мире: такого дня и быть не может

    holiday = world.add_holiday(
        name=name, origin=origin.key, group=origin.group,
        born=ctx.date_in(rng, year), step=cat.STEP_MEMORY, state=cat.ALIVE,
        holder=holder, reach=_first_reach(origin, holder),
        mood=mood, also_mood=also,
        event_year=node.year, month=month, day=day, rule=rule,
        days=1 if rng.chance(0.78) else rng.randint(2, 4),
        first_meaning=origin.meaning, now_meaning=origin.meaning,
        about=node.about,
        region_id=node.region_id if node.region_id in world.regions else "",
        **links)
    holiday.top_reach = holiday.reach
    holiday.top_year = year
    holiday.last_seen = year
    holiday.souls = _souls(world, holiday)
    _fill(ctx, rng, holiday, origin)
    _maybe_sides(ctx, rng, holiday, origin, year)

    title, text = texts.born_text(rng, holiday, node.what)
    _write(ctx, holiday, year, "holiday_born", title, text, 2)


def _fit_holder(world, holder: str, links: dict) -> str:
    """Держатель должен существовать: нет державы — день держит народ."""
    if holder == cat.BY_STATE and not links.get("polity_id"):
        return cat.BY_FOLK
    if holder == cat.BY_TEMPLE and not (links.get("faith_id")
                                        or links.get("deity_id")):
        return cat.BY_FOLK
    if holder == cat.BY_GUILD and not links.get("guild_id"):
        return cat.BY_TOWN
    if holder == cat.BY_TOWN and not links.get("settlement_id"):
        return cat.BY_FOLK
    if holder == cat.BY_HOUSE and not links.get("house_id"):
        return cat.BY_FOLK
    return holder


def _first_reach(origin, holder: str) -> str:
    """С чего день начинается. Не с того, до чего дорастёт: сперва это
    дело одного места, даже если повод был на весь свет."""
    small = {cat.BY_TOWN: cat.REACH_CITY, cat.BY_GUILD: cat.REACH_GUILD,
             cat.BY_HOUSE: cat.REACH_HOUSE, cat.BY_FOLK: cat.REACH_VILLAGE,
             cat.BY_MEMORY: cat.REACH_CITY}
    start = small.get(holder, cat.REACH_CITY)
    if cat.reach_index(origin.reach) < cat.reach_index(start):
        return origin.reach
    return start


def _pick_date(rng, origin, node, world) -> tuple:
    """Какого числа его держат — и отчего именно этого.

    У дня, выросшего из события, число взято от события и дальше не
    двигается; у сезонного числа нет вовсе — он приходит, когда приходит.
    """
    if origin.group == cat.SEASONAL:
        rule = {"жатва": cat.DATE_HARVEST, "первый снег": cat.DATE_SNOW,
                "начало весны": cat.DATE_SEASON,
                "первая борозда": cat.DATE_SEASON,
                "самая долгая ночь": cat.DATE_STARS,
                "открытие воды": cat.DATE_SEASON,
                "начало охоты": cat.DATE_SEASON}.get(origin.key,
                                                     cat.DATE_SEASON)
        month = {"жатва": 8, "первый снег": 11, "начало весны": 3,
                 "первая борозда": 4, "самая долгая ночь": 12,
                 "открытие воды": 5, "начало охоты": 9}.get(origin.key, 0)
        return month, rng.randint(1, DAYS_IN_MONTH) if month else 0, rule
    if origin.group == cat.DIVINE and rng.chance(0.4):
        rule = cat.DATE_MOVING
    elif rng.chance(0.12):
        rule = cat.DATE_MOON
    elif origin.group == cat.RULING and rng.chance(0.1):
        rule = cat.DATE_RULER
    else:
        rule = cat.DATE_FIXED
    return (rng.randint(1, MONTHS_IN_YEAR), rng.randint(1, DAYS_IN_MONTH),
            rule)


def _fill(ctx, rng, holiday, origin) -> None:
    """Чем день наполнен: обряды, игры, угощение, наряд, знак, песня.

    Берётся не вслепую: у каждого повода свой набор, и каждый обряд
    объяснён событием. Поэтому на дне мора не пляшут, а на дне победы
    не читают имён в тишине.
    """
    year = holiday.born.year
    rites = [key for key in origin.rites if _rite_fits(ctx.world, holiday, key)]
    keep = rites[:1 + (1 if rng.chance(0.8) else 0)
                 + (1 if rng.chance(0.45) else 0)]
    for key in keep:
        rite = cat.RITES.get(key)
        if rite is None:
            continue
        holiday.rites.append({"обряд": key, "с": year, "по": 0,
                              "зачем": rite.why})
    if origin.games and rng.chance(0.55):
        key = rng.choice(list(origin.games))
        game = cat.GAMES.get(key)
        if game is not None:
            holiday.games.append({"игра": key, "с": year,
                                  "зачем": game.why})
    if origin.treats and rng.chance(0.6):
        key = rng.choice(list(origin.treats))
        treat = cat.TREATS.get(key)
        if treat is not None:
            holiday.treats.append({"блюдо": key, "с": year,
                                   "зачем": treat.why})
    if origin.wears and rng.chance(0.5):
        key = rng.choice(list(origin.wears))
        wear = cat.WEARS.get(key)
        if wear is not None:
            holiday.wears.append({"наряд": key, "с": year,
                                  "зачем": wear.why})
    if origin.tokens and rng.chance(0.65):
        key = rng.choice(list(origin.tokens))
        token = cat.TOKENS.get(key)
        if token is not None:
            holiday.tokens.append({"знак": key, "с": year,
                                   "зачем": token.why})
    if origin.songs and rng.chance(0.5):
        key = rng.choice(list(origin.songs))
        song = cat.SONGS.get(key)
        if song is not None:
            holiday.songs.append({"песня": key, "с": year,
                                  "держит": song.holds, "врёт": song.lies})


def _rite_fits(world, holiday, key: str) -> bool:
    rite = cat.RITES.get(key)
    if rite is None:
        return False
    if not rite.needs:
        return True
    if rite.needs == "бог":
        return bool(holiday.deity_id or holiday.faith_id)
    if rite.needs == "держава":
        return bool(holiday.polity_id)
    if rite.needs == "цех":
        return bool(holiday.guild_id)
    if rite.needs == "берег":
        region = world.regions.get(holiday.region_id)
        return region is not None and region.coastal
    return True


def _maybe_sides(ctx, rng, holiday, origin, year: int) -> None:
    """Разные правды об одном дне.

    Заводятся только там, где у события и правда были стороны: у войны,
    нашествия, свергнутого государя. У дня первой борозды сторон нет.
    """
    if origin.group not in (cat.RULING, cat.AFTER_WOE):
        return
    if not (holiday.war_id or holiday.invasion_id or holiday.calamity_id):
        return
    if not rng.chance(0.55):
        return
    rows = list(cat.SIDES)
    count = 2 if rng.chance(0.6) else 3
    for who, how in rows[:count]:
        holiday.sides.append({"кто": who, "как": how, "с": int(year)})


# ---------------------------------------------------------------------------
# Десятилетие в жизни дня
# ---------------------------------------------------------------------------

def _live(ctx, holiday, year: int, period: int) -> None:
    world = ctx.world
    if holiday.state in (cat.FORGOTTEN, cat.GONE_FEAST, cat.ABSORBED,
                         cat.REPLACED):
        return
    rng = ctx.rng("holiday-live", holiday.id, year)
    age = year - holiday.born.year
    holiday.souls = _souls(world, holiday)
    if holiday.kept:
        holiday.last_seen = year

    # Держателя может не стать: держава пала, город опустел, вера ушла.
    if not _holder_alive(world, holiday):
        _orphan(ctx, rng, holiday, year)
        return

    # Запрет — не конец: день либо уходит в подполье, либо тает, либо
    # возвращается, когда власть переменится.
    if holiday.state == cat.BANNED:
        _under_ban(ctx, rng, holiday, year)
        return
    if holiday.state == cat.HIDDEN:
        _in_hiding(ctx, rng, holiday, year)
        return

    # Пока день молод, всё решается просто: он или поднимается ступенью,
    # или тает вместе с теми, кто помнил.
    if holiday.step in _YOUNG:
        if rng.chance(CLIMB_CHANCE * _climb_help(world, holiday)):
            _climb(ctx, rng, holiday, year)
            return
        if age > MEMORY_PATIENCE and rng.chance(FADE_MEMORY):
            _fade(ctx, rng, holiday, year)
            return
    elif rng.chance(CLIMB_CHANCE * 0.45 * _climb_help(world, holiday)):
        _climb(ctx, rng, holiday, year)
        return

    # Повод теряется не сразу и не у всех: живая память держится веками,
    # а дальше остаётся то, что несут обряд и песня.
    if holiday.knows_why and age >= LOSE_WHY_FROM \
            and rng.chance(LOSE_WHY_CHANCE * _forget_help(world, holiday, age)):
        _lose_why(ctx, rng, holiday, year)
        return

    if holiday.souls < SOULS_FLOOR and rng.chance(0.12):
        _fade(ctx, rng, holiday, year)
        return

    if rng.chance(VARIANT_CHANCE) and cat.reach_index(holiday.reach) >= 3:
        _variant(ctx, rng, holiday, year)
        return

    if rng.chance(DOING_CHANCE * _crowd(holiday)):
        _doing(ctx, rng, holiday, year)
        return

    if rng.chance(MARK_CHANCE) and len(holiday.marks) < 2 \
            and cat.is_feast(holiday.step):
        _leave_mark(ctx, rng, holiday, year)
        return

    if rng.chance(TURN_CHANCE):
        _turn(ctx, rng, holiday, year)
        return

    if cat.is_feast(holiday.step) and rng.chance(FADE_FEAST):
        _fade(ctx, rng, holiday, year)


def _climb_help(world, holiday) -> float:
    """Что помогает дню подняться: люди, власть и храм."""
    help_it = 1.0
    if holiday.holder in (cat.BY_STATE, cat.BY_TEMPLE):
        help_it += 0.6
    if holiday.souls >= 40000:
        help_it += 0.5
    elif holiday.souls < SOULS_FLOOR:
        help_it -= 0.5
    if holiday.state == cat.FADING:
        help_it -= 0.4
    return max(0.1, help_it)


def _forget_help(world, holiday, age: int) -> float:
    """Что помогает забыть повод: века, запреты и смена хозяев.

    И что мешает: тот, кто ещё стоит. Пока цела держава, назвавшая день,
    или храм, вписавший его в книгу, повод держится.
    """
    help_it = 0.6 + min(2.2, age / 900.0)
    if holiday.bans:
        help_it += 0.7
    if holiday.holder == cat.BY_MEMORY:
        help_it += 0.5
    if holiday.holder in (cat.BY_STATE, cat.BY_TEMPLE):
        help_it -= 0.35
    if holiday.songs:
        help_it -= 0.25        # песня держит имена дольше всего
    return max(0.1, help_it)


def _crowd(holiday) -> float:
    """Насколько день собирает людей в одно место: там и случается."""
    total = 0.0
    for item in holiday.live_rites:
        rite = cat.RITES.get(item.get("обряд", ""))
        if rite is not None:
            total += rite.crowd
    total += 0.3 * cat.reach_index(holiday.reach)
    return max(0.2, min(4.0, total))


def _souls(world, holiday) -> int:
    """Сколько людей его держит. Отсюда и угасание: приходить стало некому."""
    polity = world.polities.get(holiday.polity_id)
    if polity is not None and polity.status == ACTIVE:
        return int(polity.population)
    folk = world.folks.get(holiday.folk_id)
    if folk is not None and folk.status == ACTIVE:
        return int(folk.population)
    faith = world.faiths.get(holiday.faith_id)
    if faith is not None and faith.status == ACTIVE:
        return int(faith.followers)
    settlement = world.settlements.get(holiday.settlement_id)
    if settlement is not None and settlement.status == ACTIVE:
        return int(settlement.population)
    return 0


def _holder_alive(world, holiday) -> bool:
    """Есть ли ещё тот, кто его держит."""
    if holiday.holder == cat.BY_STATE:
        polity = world.polities.get(holiday.polity_id)
        return polity is not None and polity.status == ACTIVE
    if holiday.holder == cat.BY_TEMPLE:
        faith = world.faiths.get(holiday.faith_id)
        if faith is not None:
            return faith.status == ACTIVE
        return bool(holiday.deity_id)
    if holiday.holder == cat.BY_TOWN:
        settlement = world.settlements.get(holiday.settlement_id)
        return settlement is not None and settlement.status == ACTIVE
    if holiday.holder == cat.BY_GUILD:
        guild = world.guilds.get(holiday.guild_id)
        return guild is not None and guild.status == ACTIVE
    if holiday.holder == cat.BY_HOUSE:
        house = world.houses.get(holiday.house_id)
        return house is not None and house.status == ACTIVE
    # Народ и память не падают: они или есть, или день уже угас сам.
    return True


# ---------------------------------------------------------------------------
# Что с ним случается
# ---------------------------------------------------------------------------

def _climb(ctx, rng, holiday, year: int) -> None:
    was = holiday.step
    index = cat.step_index(was)
    if index >= len(cat.STEPS) - 1:
        return
    # Установление — это запись в календаре, и её кто-то делает. Народный
    # обычай может жить веками и установлением не стать: вписывать его
    # некому. Без этого условия половина дней мира доходила до верха, и
    # верх перестал что-то значить.
    if cat.STEPS[index + 1] == cat.STEP_SET \
            and holiday.holder not in (cat.BY_STATE, cat.BY_TEMPLE,
                                       cat.BY_TOWN, cat.BY_GUILD):
        return
    holiday.step = cat.STEPS[index + 1]
    _note_turn(holiday, year,
               cat.SET_UP if holiday.step == cat.STEP_SET else cat.ROSE,
               "что было %s, то стало %s" % (cat.step_tv(was),
                                             cat.step_tv(holiday.step)))
    # Поднявшись, день обычно и расходится шире.
    if rng.chance(0.65):
        was_reach = holiday.reach
        _widen(holiday, year)
        if holiday.reach != was_reach:
            _note_turn(holiday, year, cat.GREW,
                       "теперь отмечают %s" % holiday.reach)
    if holiday.step == cat.STEP_SET and holiday.holder == cat.BY_FOLK \
            and rng.chance(0.6):
        holiday.holder = cat.BY_STATE if holiday.polity_id else cat.BY_TOWN
    title, text = texts.step_text(rng, holiday, was)
    weight = 3 if holiday.step in (cat.STEP_FEAST, cat.STEP_SET) else 1
    _write(ctx, holiday, year, "holiday_step", title, text, weight)
    if holiday.step == cat.STEP_FEAST:
        _quarrel_over_day(ctx, rng, holiday, year)


def _widen(holiday, year: int) -> None:
    index = cat.reach_index(holiday.reach)
    if index + 1 >= len(cat.REACH):
        return
    holiday.reach = cat.REACH[index + 1]
    if cat.reach_index(holiday.reach) > cat.reach_index(holiday.top_reach
                                                        or ""):
        holiday.top_reach = holiday.reach
        holiday.top_year = int(year)


def _narrow(holiday) -> None:
    index = cat.reach_index(holiday.reach)
    if index > 0:
        holiday.reach = cat.REACH[index - 1]


def _turn(ctx, rng, holiday, year: int) -> None:
    """Один поворот судьбы из тех, что этому дню сейчас доступны."""
    world = ctx.world
    rows = []
    reach = cat.reach_index(holiday.reach)
    if reach < len(cat.REACH) - 1 and holiday.souls > SOULS_FLOOR:
        rows.append((cat.GREW, 1.0))
    if holiday.holder not in cat.CAN_FORBID:
        if holiday.polity_id and cat.is_feast(holiday.step):
            rows.append((cat.TAKEN, 1.1))
        elif holiday.faith_id or holiday.deity_id:
            rows.append((cat.TAKEN, 0.8))
    if holiday.holder in cat.CAN_FORBID or holiday.polity_id:
        # Запрещают не что попало. Под запрет идёт то, что помнит
        # свергнутый род или чужого бога: державный и храмовый день — это
        # политика, а день первой борозды никому не мешает.
        weight = 0.6
        if holiday.group in (cat.RULING, cat.DIVINE):
            weight = 1.6
        if holiday.state == cat.REVIVED:
            weight *= 1.4      # однажды запрещённое запрещают снова
        rows.append((cat.FORBIDDEN, weight))
    rows.append((cat.REFORMED, 0.9))
    if holiday.live_rites:
        rows.append((cat.RITE_CHANGED, 1.2))
    if not holiday.knows_why or holiday.holder in (cat.BY_STATE,
                                                   cat.BY_TEMPLE):
        rows.append((cat.MEANING_CHANGED, 1.0))
    if holiday.rule in cat.MOVING_RULES and cat.is_feast(holiday.step):
        rows.append((cat.SPLIT_UP, 0.7))
    if reach > 1:
        rows.append((cat.SHRANK, 0.8))
    if _same_day_rival(world, holiday) is not None:
        rows.append((cat.SWALLOWED, 0.5))
    turn = rng.weighted(rows)

    what = ""
    if turn == cat.GREW:
        _widen(holiday, year)
        what = "теперь отмечают %s" % holiday.reach
    elif turn == cat.TAKEN:
        was = holiday.holder
        holiday.holder = cat.BY_STATE if holiday.polity_id else cat.BY_TEMPLE
        what = "было делом %s" % texts.holder_gen(was)
        if rng.chance(0.5):
            _retell(ctx, rng, holiday, year)
    elif turn == cat.REFORMED:
        # Одну и ту же реформу дважды не проводят: «праздновать стали три
        # дня вместо одного» второй раз — это не история, а повтор.
        done = {row.get("отчего", "") for row in holiday.turns}
        free = [line for line in (
            "порядок дня переписали заново",
            "день перенесли на другое число и объяснили это древним счётом",
            "праздновать стали три дня вместо одного",
            "от обряда отрезали всё, что сочли лишним",
            "в день внесли то, чего в нём раньше не было",
            "день сократили до одного утра",
            "праздновать велели всем, а не только своим",
        ) if line not in done]
        if not free:
            return
        what = rng.choice(free)
        if "три дня" in what:
            holiday.days = max(holiday.days, 3)
        if "одного утра" in what:
            holiday.days = 1
        if "перенесли" in what:
            holiday.month = max(1, (holiday.month % MONTHS_IN_YEAR) + 1)
    elif turn == cat.RITE_CHANGED:
        what = _change_rite(ctx, rng, holiday, year)
    elif turn == cat.MEANING_CHANGED:
        what = _retell(ctx, rng, holiday, year)
        if not what:
            return      # смысл не переменился — и писать, что переменился, незачем
    elif turn == cat.SPLIT_UP:
        what = _split(ctx, rng, holiday, year)
        if holiday.state != cat.SPLIT:
            return
    elif turn == cat.FORBIDDEN:
        _forbid(ctx, rng, holiday, year)
        return
    elif turn == cat.SHRANK:
        _narrow(holiday)
    elif turn == cat.SWALLOWED:
        _swallow(ctx, rng, holiday, year)
        return

    _note_turn(holiday, year, turn, what)
    title, text = texts.turn_text(rng, holiday, turn, what)
    _write(ctx, holiday, year, "holiday_turn", title, text,
           3 if turn in (cat.TAKEN, cat.MEANING_CHANGED) else 1)


def _change_rite(ctx, rng, holiday, year: int) -> str:
    """Старое делать перестали, завелось новое."""
    live = holiday.live_rites
    if not live:
        return ""
    old = rng.choice(live)
    old["по"] = int(year)
    free = [key for key in cat.RITES
            if key not in {item.get("обряд") for item in holiday.rites}
            and _rite_fits(ctx.world, holiday, key)]
    if not free:
        return "от обряда осталось меньше, чем было"
    key = rng.choice(sorted(free))
    rite = cat.RITES[key]
    holiday.rites.append({"обряд": key, "с": int(year), "по": 0,
                          "зачем": "так сложилось, прежнего уже не делали"})
    # Обряды в каталоге записаны готовыми оборотами («жгут большой
    # костёр до утра»), и склеивать их через «перестали» нельзя: выйдет
    # «перестали первый хлеб делят на всех». Поэтому оборот ставится
    # целиком, а смена показывается двумя половинами.
    was = cat.RITES.get(old.get("обряд", ""))
    return "прежде было так: %s. Теперь так: %s" % (
        was.what if was else "делали по-старому", rite.what)


def _god_frowns(world, holiday, year: int, meaning: str) -> None:
    """Бог не равен своему культу — и своему празднику тоже.

    Если культ уже разошёлся с волей божества, перемена смысла его дня
    эту трещину только расширяет: жрецы объясняют день по-своему, а бог
    своего праздника больше не узнаёт. Запись ложится в биографию бога,
    а не праздника: это его обида, не людская.
    """
    if not holiday.deity_id:
        return
    for head in world.godheads.values():
        if head.deity_id != holiday.deity_id:
            continue
        if head.drift < 0.35:
            return
        head.marks.append({
            "год": int(year), "вид": "праздник",
            "строка": "Праздник по имени %s стали объяснять иначе: теперь"
                      " это %s. Воли божества тут уже не спрашивали."
                      % (holiday.name, meaning)})
        return


def _retell(ctx, rng, holiday, year: int) -> str:
    """Смысл дня сменился: о чём он, отвечают иначе — и имя может уехать."""
    origin = cat.ORIGINS.get(holiday.origin)
    drifts = list(origin.drifts) if origin is not None else []
    if not drifts:
        return ""
    meaning = rng.choice(drifts)
    if holiday.now_meaning == meaning:
        return ""
    holiday.now_meaning = meaning
    _god_frowns(ctx.world, holiday, year, meaning)
    if holiday.holder == cat.BY_STATE:
        holiday.said_meaning = meaning
    elif holiday.holder == cat.BY_TEMPLE:
        holiday.said_meaning = meaning
    else:
        holiday.folk_meaning = meaning
    if rng.chance(0.55):
        taken = {item.name for item in ctx.world.holidays.values()}
        new_name = texts.drift_name(rng, meaning, holiday.mood, taken)
        # Имя должно быть своё: два праздника с одним именем — это не
        # история, а сбой. Если свободного сочетания не нашлось, день
        # остаётся под старым именем, и это честнее подделки.
        if new_name != holiday.name and new_name not in taken:
            holiday.names.append({"имя": holiday.name, "с": holiday.born.year,
                                  "по": int(year)})
            holiday.name = new_name
            _note_turn(holiday, year, cat.RENAMED, "теперь это %s" % meaning)
    return meaning


def _split(ctx, rng, holiday, year: int) -> str:
    """Спор о счёте раскалывает день надвое."""
    holiday.state = cat.SPLIT
    why = rng.choice((
        "одни считают по луне, другие по книге",
        "храм положил одно число, города держат другое",
        "старый счёт шёл от государя, а государя не стало",
        "две земли разошлись в том, когда начинать",
    ))
    holiday.notes.append("%d: раскол — %s" % (year, why))
    if rng.chance(0.5):
        holiday.rule = cat.DATE_MOVING
    return why


def _swallow(ctx, rng, holiday, year: int) -> None:
    """День сошёлся с соседом по числу и в нём растворился."""
    rival = _same_day_rival(ctx.world, holiday)
    if rival is None:
        return
    holiday.state = cat.ABSORBED
    holiday.notes.append("%d: слился с другим днём того же числа" % year)
    # Обряды не пропадают: их забирает тот, кто поглотил.
    had = {row.get("обряд") for row in rival.rites}
    for item in holiday.live_rites:
        if len(rival.rites) >= 6:
            break
        key = item.get("обряд", "")
        if key in had:
            continue        # этот обряд у него и так есть
        had.add(key)
        rival.rites.append({"обряд": key, "с": int(year), "по": 0,
                            "зачем": "пришло от другого дня, который сошёлся"
                                     " с этим"})
    rival.notes.append("%d: забрал себе обряды дня, что стоял на том же"
                       " числе" % year)
    _note_turn(holiday, year, cat.SWALLOWED, "")
    title, text = texts.turn_text(rng, holiday, cat.SWALLOWED, "")
    _write(ctx, holiday, year, "holiday_turn", title, text, 2)


def _same_day_rival(world, holiday):
    """Праздник, стоящий на том же числе или рядом, — и сильнее этого.

    Рядом, а не точно в тот же день: сливаются как раз соседние дни.
    Два праздника через сутки друг от друга превращаются в один
    длинный, и младший в нём растворяется — обряды остаются, повод
    становится чужим.
    """
    if holiday.month <= 0:
        return None
    best = None
    near = []
    for shift in (-2, -1, 0, 1, 2):
        day = holiday.day + shift
        if 1 <= day <= 30:
            near.extend(world.holidays_on(holiday.month, day))
    for other in near:
        if other.id == holiday.id or not other.kept:
            continue
        if not cat.is_feast(other.step):
            continue
        if cat.reach_index(other.reach) <= cat.reach_index(holiday.reach):
            continue
        if best is None or cat.reach_index(other.reach) > cat.reach_index(
                best.reach):
            best = other
    return best


def _quarrel_over_day(ctx, rng, holiday, year: int) -> None:
    """Два праздника на одно число — повод для ссоры, а не совпадение."""
    rival = None
    for other in ctx.world.holidays_on(holiday.month, holiday.day):
        if other.id != holiday.id and other.kept and cat.is_feast(other.step):
            rival = other
            break
    if rival is None or rival.faith_id == holiday.faith_id:
        return
    line = "в это же число держат другой день, и о том, чей он, спорят"
    holiday.notes.append("%d: %s" % (year, line))
    rival.notes.append("%d: %s" % (year, line))
    holiday.sides.append({"кто": "те, кто держит соседний день",
                          "как": "считают это число своим", "с": int(year)})


def _forbid(ctx, rng, holiday, year: int) -> None:
    """Запрет. У него названа причина, и причина остаётся в летописи."""
    why = rng.choice(cat.BAN_WHY)
    by = cat.BY_STATE if holiday.polity_id else cat.BY_TEMPLE
    holiday.state = cat.BANNED
    holiday.bans.append({"с": int(year), "по": 0, "отчего": why,
                         "кем": texts.holder_word(by)})
    _note_turn(holiday, year, cat.FORBIDDEN, why)
    title, text = texts.turn_text(ctx.rng("holiday-ban", holiday.id, year),
                                  holiday, cat.FORBIDDEN, why)
    _write(ctx, holiday, year, "holiday_ban", title, text, 3)


def _under_ban(ctx, rng, holiday, year: int) -> None:
    """Запрещённый день: прячется, тает или возвращается."""
    if rng.chance(0.4):
        holiday.state = cat.HIDDEN
        _note_turn(holiday, year, cat.WENT_UNDER, "")
        title, text = texts.turn_text(rng, holiday, cat.WENT_UNDER, "")
        _write(ctx, holiday, year, "holiday_turn", title, text, 2)
        return
    if rng.chance(0.16):
        _revive(ctx, rng, holiday, year)
        return
    if rng.chance(0.2):
        _fade(ctx, rng, holiday, year)


def _in_hiding(ctx, rng, holiday, year: int) -> None:
    """Тайный день: держится в домах, пока не переменится власть."""
    if rng.chance(0.1):
        _revive(ctx, rng, holiday, year)
        return
    if rng.chance(0.06):
        _fade(ctx, rng, holiday, year)
        return
    # Под запретом повод теряется быстрее всего: говорить о нём нельзя.
    if holiday.knows_why and rng.chance(LOSE_WHY_CHANCE * 2.5):
        _lose_why(ctx, rng, holiday, year)


def _revive(ctx, rng, holiday, year: int) -> None:
    why = rng.choice(cat.REVIVE_WHY)
    holiday.state = cat.REVIVED
    for row in holiday.bans:
        if not row.get("по"):
            row["по"] = int(year)
    _note_turn(holiday, year, cat.BROUGHT_BACK, why)
    # Вернувшийся день — уже не тот: за годы запрета у него сменился и
    # смысл, и часто имя.
    if rng.chance(0.5):
        _retell(ctx, rng, holiday, year)
    title, text = texts.turn_text(rng, holiday, cat.BROUGHT_BACK, why)
    _write(ctx, holiday, year, "holiday_revive", title, text, 3)


def _orphan(ctx, rng, holiday, year: int) -> None:
    """Держателя не стало. День переходит к народу или к одной памяти."""
    was = holiday.holder
    holiday.holder = cat.BY_FOLK if rng.chance(0.55) else cat.BY_MEMORY
    _narrow(holiday)
    holiday.state = cat.FADING
    holiday.notes.append("%d: держать стало некому — %s больше нет"
                         % (year, texts.holder_gen(was)))
    _note_turn(holiday, year, cat.SHRANK,
               "того, кто его держал, больше нет")
    title, text = texts.turn_text(rng, holiday, cat.SHRANK,
                                  "того, кто его держал, больше нет")
    _write(ctx, holiday, year, "holiday_turn", title, text, 1)


def _lose_why(ctx, rng, holiday, year: int) -> None:
    """Повод потерян: делают то же, а зачем — объясняют уже неправду."""
    why = rng.choice(cat.LOST_WHY)
    holiday.knows_why = False
    holiday.forgot_year = int(year)
    holiday.forgot_why = why
    # Обряд без причины не остаётся: ему придумывают новую.
    instead = ""
    live = holiday.live_rites
    if live:
        rite = cat.RITES.get(live[0].get("обряд", ""))
        if rite is not None:
            instead = rite.lost
            live[0]["зачем"] = instead or live[0].get("зачем", "")
    if rng.chance(0.6):
        _retell(ctx, rng, holiday, year)
    _note_turn(holiday, year, cat.MEANING_CHANGED, why)
    title, text = texts.lost_text(rng, holiday, why, instead)
    _write(ctx, holiday, year, "holiday_lost", title, text, 3)


def _variant(ctx, rng, holiday, year: int) -> None:
    """День переняли на свой лад: то же число, другой смысл."""
    world = ctx.world
    kin = [folk for folk in world.folks.values()
           if folk.status == ACTIVE and folk.id != holiday.folk_id
           and folk.population > 8000]
    if not kin:
        return
    folk = rng.weighted([(item, float(item.population)) for item in kin])
    if any(row.get("кто") == folk.name for row in holiday.variants):
        return
    origin = cat.ORIGINS.get(holiday.origin)
    options = list(origin.drifts) if origin is not None else []
    said = {row.get("чем") for row in holiday.variants} | {holiday.now_meaning}
    options = [item for item in options if item not in said]
    what = rng.choice(options) if options else "просто день отдыха"
    holiday.variants.append({"кто": folk.name, "чем": what, "с": int(year)})
    line = texts.variant_line(rng, "те, кого зовут %s" % folk.name,
                              "народа по имени %s" % folk.name, what)
    holiday.notes.append("%d: %s" % (year, line))
    title = "%s: у других это другой день" % texts.in_case(holiday.name, "им")
    _write(ctx, holiday, year, "holiday_variant", title, line, 1)


def _doing(ctx, rng, holiday, year: int) -> None:
    """Что случилось на самом празднике. Отсюда растут были."""
    what = rng.choice(cat.HAPPENINGS)
    holiday.doings.append({"год": int(year), "что": what})
    title, text = texts.doing_text(rng, holiday, what)
    _write(ctx, holiday, year, "holiday_doing", title, text, 2)


def _leave_mark(ctx, rng, holiday, year: int) -> None:
    """Ради дня в мире что-то строят — и это переживёт сам день."""
    what = rng.choice(cat.MARKS)
    if what in holiday.marks:
        return
    holiday.marks.append(what)
    if rng.chance(0.7):
        gain = rng.choice(cat.GAINS)
        if gain not in holiday.gains:
            holiday.gains.append(gain)
    if rng.chance(0.45):
        cost = rng.choice(cat.COSTS)
        if cost not in holiday.costs:
            holiday.costs.append(cost)
    line = texts.mark_line(rng, what)
    title = "%s: что он оставил по себе" % texts.in_case(holiday.name, "им")
    _write(ctx, holiday, year, "holiday_mark", title, line, 1)


def _fade(ctx, rng, holiday, year: int) -> None:
    """День выпал из года. Если он успел стать праздником — это заметно."""
    was_feast = cat.is_feast(holiday.step)
    if holiday.state != cat.FADING and rng.chance(0.5):
        holiday.state = cat.FADING
        holiday.notes.append("%d: приходить стало меньше" % year)
        return
    holiday.state = cat.FORGOTTEN
    _note_turn(holiday, year, cat.FADED, "")
    if not was_feast and not holiday.marks:
        # Поминовение, которое ничем не стало, уходит без летописи: о нём
        # и писать нечего, кроме того, что его больше нет.
        return
    title, text = texts.turn_text(rng, holiday, cat.FADED, "")
    _write(ctx, holiday, year, "holiday_fade", title, text,
           2 if was_feast else 1)


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _note_turn(holiday, year: int, turn: str, why: str) -> None:
    holiday.turns.append({"год": int(year), "поворот": turn, "отчего": why})


def _write(ctx, holiday, year: int, kind: str, title: str, text: str,
           weight: int) -> None:
    world = ctx.world
    rng = ctx.rng("holiday-date", holiday.id, year)
    subjects = [holiday.id]
    for field in ("polity_id", "settlement_id", "calamity_id", "war_id",
                  "deity_id", "faith_id", "invasion_id", "guild_id"):
        value = getattr(holiday, field, "")
        if value:
            subjects.append(value)
    actors = [holiday.figure_id] if holiday.figure_id else []
    event = world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind=kind, title=title, text=text, importance=weight,
        actors=actors, subjects=subjects, region_id=holiday.region_id)
    if event is not None:
        holiday.event_ids.append(event.id)


# ---------------------------------------------------------------------------
# Узлы для былей
# ---------------------------------------------------------------------------

def story_nodes(world, year: int) -> list:
    """Из чего праздник кормит малую историю.

    Три рода узлов, и все три — настоящие загадки, а не выдумка: обряд,
    которому никто не знает причины; день, который держат втайне, хотя
    он запрещён двести лет; и то, что было построено ради праздника,
    которого больше нет.
    """
    out = []
    for holiday in world.holidays.values():
        age = year - holiday.born.year
        if holiday.lost_why and holiday.kept and holiday.live_rites:
            rite = cat.RITES.get(holiday.live_rites[0].get("обряд", ""))
            if rite is not None:
                out.append(("обряд без причины",
                            "%s: %s, а зачем — не знает никто"
                            % (texts.in_case(holiday.name, "им"), rite.what),
                            holiday, 1.0 + min(1.5, age / 900.0)))
        if holiday.state == cat.HIDDEN:
            out.append(("запрещённый день",
                        "%s держат втайне, хотя за это берут"
                        % texts.in_case(holiday.name, "им"),
                        holiday, 1.2))
        if holiday.state in (cat.FORGOTTEN, cat.GONE_FEAST) and holiday.marks:
            out.append(("след праздника",
                        "в городе стоит %s, а дня, ради которого его"
                        " поставили, уже нет" % holiday.marks[0],
                        holiday, 1.0))
    out.sort(key=lambda row: row[2].id)
    return out


__all__ = ["upkeep", "story_nodes"]
