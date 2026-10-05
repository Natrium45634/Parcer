# -*- coding: utf-8 -*-
"""Смотр мира: получился ли он таким, каким задуман.

Самопроверка (`selfcheck.py`) отвечает на вопрос «не сломалось ли»:
сходятся ли даты, не действует ли мертвец, не стоит ли город в воде.
Этот смотр отвечает на другой вопрос — **похож ли получившийся мир на
тот, ради которого всё писалось**. Поломки он не ищет; он меряет.

    ОБРАЗ, К КОТОРОМУ МЫ РАВНЯЕМСЯ

    *Были.* Девять из десяти малых историй не спасают мир. Все костяки
    в ходу, ни один не занимает больше четверти. Каждый поворот
    подготовлен подсказкой — без исключений. Треть историй растёт из
    городов, богов и людской памяти, а не из общего списка.

    *Города.* У каждого живого города есть причина, по которой он тут
    стоит, и причины эти разные. Занятия меняются: город, потерявший
    кормильца, ищет новое дело или мельчает. У старых городов под ногами
    лежат слои, и хотя бы у половины есть своя тайна. Новые города
    иногда встают на костях старых.

    *Боги.* У каждого бога есть главная мысль и мера чужих дел.
    Покровительство — число с причиной, и оно движется. Культ уходит от
    воли бога, и у ереси названа причина. Пророчества иногда разгадывают
    были.

    *Вес людей.* Взвешены единицы из тысяч. Ступени лежат пирамидой:
    высших — считаные на весь мир. Имена и поднимаются, и оседают;
    великие бывают забыты. Слава при жизни и нынешняя память — разные
    числа. И среди тяжёлых имён есть люди без титулов: вес считается по
    делам, а не по должности.

Запуск:

    /usr/bin/python3.12 tools/audit.py                  один случайный мир
    /usr/bin/python3.12 tools/audit.py --worlds 5       пять миров подряд
    /usr/bin/python3.12 tools/audit.py --seed Ясень-7 --years 4000
    /usr/bin/python3.12 tools/audit.py --map            на случайной карте

Выход не нулевой, если хоть одна мера вышла за свои границы.
"""

from __future__ import annotations

import argparse
import collections
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import localstory as story_cat                  # noqa: E402
from worldgen import township as town_cat                     # noqa: E402
from worldgen.engine import Settings, generate                # noqa: E402
from worldgen.models import ACTIVE                            # noqa: E402
from worldgen.rng import Rng, make_seed_text, random_seed_text  # noqa: E402


# ---------------------------------------------------------------------------
# Меры
# ---------------------------------------------------------------------------

class Measure:
    """Одна мера: что считаем, в каких границах ждём и зачем."""

    __slots__ = ("group", "name", "func", "low", "high", "unit", "about",
                 "min_years")

    def __init__(self, group, name, func, low=None, high=None, unit="",
                 about="", min_years=0):
        self.group = group
        self.name = name
        self.func = func
        self.low = low
        self.high = high
        self.unit = unit
        self.about = about
        # Иные меры имеют смысл только на долгой истории: память тает
        # веками, и на тысяче лет её убыли просто не видно.
        self.min_years = int(min_years)

    def verdict(self, value):
        if value is None:
            return "—"
        if self.low is not None and value < self.low:
            return "НИЖЕ"
        if self.high is not None and value > self.high:
            return "ВЫШЕ"
        return "в норме"


def _share(part, whole):
    return round(float(part) / whole, 3) if whole else None


# --- были -------------------------------------------------------------------

def m_story_small(world):
    rows = list(world.stories.values())
    return _share(sum(1 for item in rows if item.epicity <= 2), len(rows))


def m_story_shapes(world):
    return len({item.shape for item in world.stories.values()})


def m_story_top_shape(world):
    rows = collections.Counter(item.shape for item in world.stories.values())
    return _share(max(rows.values()), sum(rows.values())) if rows else None


def m_story_seeded(world):
    rows = [item for item in world.stories.values() if item.twist]
    return _share(sum(1 for item in rows if item.twist_seeded), len(rows))


def m_story_unique(world):
    names = [item.title for item in world.stories.values()]
    return _share(len(set(names)), len(names))


def m_story_world_nodes(world):
    """Доля былей, выросших из городов, богов и людской памяти."""
    grown = (story_cat.TOWN_ACHE, story_cat.TOWN_SECRET, story_cat.UNDERCITY,
             story_cat.DIVINE_BAN, story_cat.LOST_GOD, story_cat.PROPHECY,
             story_cat.FIRST_TRACE, story_cat.LOST_NAME, story_cat.UNDONE,
             story_cat.FALSE_HERO)
    rows = list(world.stories.values())
    return _share(sum(1 for item in rows if item.node in grown), len(rows))


def m_story_top_node(world):
    rows = collections.Counter(item.node for item in world.stories.values())
    return _share(max(rows.values()), sum(rows.values())) if rows else None


# --- города -----------------------------------------------------------------

def _live_towns(world):
    out = []
    for town in world.townships.values():
        settlement = world.settlements.get(town.settlement_id)
        if settlement is not None and settlement.status == ACTIVE:
            out.append((town, settlement))
    return out


def m_town_covered(world):
    live = [world.settlements[sid] for sid in world.active_settlements]
    big = [item for item in live if item.population >= 300]
    have = sum(1 for item in big if world.town_of(item.id) is not None)
    return _share(have, len(big))


def m_town_origins(world):
    return len({town.origin for town in world.townships.values()})


def m_town_top_origin(world):
    rows = collections.Counter(town.origin for town in world.townships.values())
    return _share(max(rows.values()), sum(rows.values())) if rows else None


def m_town_trades(world):
    return len({town.trade for town in world.townships.values() if town.trade})


def m_town_changed(world):
    rows = list(world.townships.values())
    return _share(sum(1 for item in rows if len(item.trades) > 1), len(rows))


def m_town_districts(world):
    rows = _live_towns(world)
    if not rows:
        return None
    return round(sum(len(town.districts) for town, _ in rows) / len(rows), 2)


def m_town_layers(world):
    rows = [town for town in world.townships.values()
            if town.born and world.total_years - town.born.year >= 300]
    if not rows:
        return None
    return round(sum(len(town.layers) for town in rows) / len(rows), 2)


def m_town_secrets(world):
    rows = list(world.townships.values())
    return _share(sum(1 for item in rows if item.secrets), len(rows))


def m_town_secrets_open(world):
    return sum(1 for town in world.townships.values()
               for item in town.secrets if item.get("раскрыта"))


def m_town_reborn(world):
    rows = list(world.townships.values())
    return _share(sum(1 for item in rows
                      if any(mark.get("вид") == town_cat.RESETTLED
                             for mark in item.marks)), len(rows))


# --- боги -------------------------------------------------------------------

def m_god_covered(world):
    return _share(len(world.godheads), len(world.deities))


def m_god_origins(world):
    return len({head.origin for head in world.godheads.values()})


def m_god_favour(world):
    rows = list(world.godheads.values())
    if not rows:
        return None
    return round(sum(len(head.favour) for head in rows) / len(rows), 2)


def m_god_drift(world):
    rows = list(world.godheads.values())
    if not rows:
        return None
    return round(sum(head.drift for head in rows) / len(rows), 3)


def m_heresy_reason(world):
    rows = [item for item in world.faiths.values() if item.kind == "ересь"]
    with_reason = sum(1 for item in rows
                      if any(note.startswith("с чего началось")
                             for note in item.notes))
    return _share(with_reason, len(rows))


def m_prophecy_read(world):
    return sum(1 for head in world.godheads.values()
               for item in head.prophecies if item.get("сбылось"))


def m_myth_traces(world):
    return sum(len(myth.get("следы", ())) for myth in world.myths)


# --- беда и её след ---------------------------------------------------------

def _heavy_calamities(world):
    return [item for item in world.calamities.values() if item.severity >= 3]


def m_cause_named(world):
    """У беды названа причина, а не «случилось само»."""
    from worldgen import disaster as dis
    rows = list(world.calamities.values())
    known = sum(1 for item in rows
                if item.cause and item.cause != dis.UNKNOWN_CAUSE)
    return _share(known, len(rows))


def m_cause_hidden(world):
    """И у части бед известная причина — не настоящая."""
    rows = list(world.calamities.values())
    return _share(sum(1 for item in rows if item.cause_hidden), len(rows))


def m_omens_read(world):
    """Знаки читают верно не всегда — иначе мир перестаёт быть опасным."""
    from worldgen import disaster as dis
    right = seen = 0
    for calamity in world.calamities.values():
        for omen in calamity.omens:
            seen += 1
            if omen.get("прочтение") == dis.READ_RIGHT:
                right += 1
    return _share(right, seen)


def m_prevented(world):
    """Беды, отведённые до начала: их должно быть мало, но должно быть."""
    from worldgen import disaster as dis
    rows = [item for item in world.calamities.values()
            if item.prevented and item.prevented != dis.STOP_NONE]
    return len(rows)


def m_responses(world):
    """Власть отвечает на беду делом, а не только терпит."""
    rows = _heavy_calamities(world)
    return _share(sum(1 for item in rows if item.responses), len(rows))


def m_mistakes(world):
    """И ошибается: беду делают бедой решения в столицах."""
    rows = _heavy_calamities(world)
    return _share(sum(1 for item in rows if item.mistakes), len(rows))


def m_chained(world):
    """Беда рождает беду — но цепь затухает, а не съедает мир."""
    rows = list(world.calamities.values())
    grown = sum(1 for item in rows
                if any("выросло из беды" in note for note in item.notes))
    return _share(grown, len(rows))


def m_scar_kinds(world):
    """Шрамы разные: в ходу не два вида на весь мир."""
    return len({item.kind for item in world.scars.values()})


def m_scar_top(world):
    """И ни один вид не занимает больше четверти всех шрамов."""
    rows = list(world.scars.values())
    if not rows:
        return None
    counts = {}
    for item in rows:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    return _share(max(counts.values()), len(rows))


def m_scar_states(world):
    """Шрам живёт: его обходят, обживают, освящают, забывают."""
    return len({item.state for item in world.scars.values()})


def m_scar_remembered(world):
    """Часть шрамов мир всё-таки помнит — не всё уходит в забвение."""
    from worldgen import disaster as dis
    rows = list(world.scars.values())
    kept = sum(1 for item in rows if item.state != dis.SCAR_FORGOTTEN)
    return _share(kept, len(rows))


def m_lore_lost(world):
    """Знание гибнет: у большой беды это главный убыток."""
    return len(world.lost_lore)


def m_lore_kept(world):
    """И не всё возвращается: иначе утрата ничего не значит."""
    from worldgen import disaster as dis
    rows = list(world.lost_lore.values())
    lost = sum(1 for item in rows if item.state != dis.LORE_FOUND)
    return _share(lost, len(rows))


def m_versions(world):
    """О большой беде рассказывают по-разному, и это записано."""
    rows = _heavy_calamities(world)
    return _share(sum(1 for item in rows if len(item.versions) >= 4), len(rows))


def m_eras(world):
    """Времена бед — редкость: не всякое столетие зовётся Веком Пепла."""
    return len([item for item in world.crisis_eras.values() if item.name])


def m_era_length(world):
    """И они сгущение, а не полтысячи лет с бедой раз в век."""
    rows = [item for item in world.crisis_eras.values()
            if item.name and item.end is not None]
    if not rows:
        return None
    spans = [item.end.year - item.start.year for item in rows]
    return round(sum(spans) / float(len(spans)))


def m_era_voices(world):
    """У времени бед не одно имя: у каждого народа своё."""
    rows = [item for item in world.crisis_eras.values() if item.name]
    return _share(sum(1 for item in rows if item.voices), len(rows))


def m_front_lands(world):
    """У нашествия есть ход по землям, а не список сразу."""
    rows = [item for item in world.calamities.values() if item.front]
    if not rows:
        return None
    return round(sum(len(item.front) for item in rows) / float(len(rows)), 1)


def m_front_kept(world):
    """И победой возвращают не всё: часть земель остаётся за чужими."""
    from worldgen import disaster as dis
    kept = 0
    for calamity in world.calamities.values():
        if any(row.get("состояние") == dis.LAND_LOST
               for row in calamity.front):
            kept += 1
    rows = [item for item in world.calamities.values() if item.front]
    return _share(kept, len(rows))


def m_learned(world):
    """Земля учится: после беды в ней появляются дамбы и амбары."""
    rows = list(world.regions.values())
    return _share(sum(1 for item in rows if item.works), len(rows))


def m_habits(world):
    """А город оставляет это в укладе и держит, забыв причину."""
    from worldgen import township as town_cat
    rows = list(world.townships.values())
    with_habit = sum(1 for item in rows
                     if any(mark.get("вид") == town_cat.HABIT
                            for mark in item.marks))
    return _share(with_habit, len(rows))


# --- нашествия --------------------------------------------------------------

def _invasions(world):
    return list(world.invasions.values())


def m_inv_kinds(world):
    """Пришедших разных родов, а не одни драконы на весь мир."""
    return len({item.kind for item in _invasions(world)})


def m_inv_causes(world):
    """И приходят они по разным причинам, а не все воевать."""
    return len({item.cause for item in _invasions(world) if item.cause})


def m_inv_goals(world):
    """Цели тоже разные: не всякий пришедший хочет взять землю."""
    return len({item.goal_first for item in _invasions(world)
                if item.goal_first})


def m_inv_war_share(world):
    """Доля тех, кто пришёл именно воевать. Больше половины — однообразие."""
    rows = _invasions(world)
    war = sum(1 for item in rows
              if item.goal_first in ("взять землю", "извести державу",
                                     "отомстить", "очистить землю"))
    return _share(war, len(rows))


def m_inv_peaceful_start(world):
    """Началось не с битвы: переговоры, торг, спор о меже."""
    rows = _invasions(world)
    return _share(sum(1 for item in rows if item.peaceful_start), len(rows))


def m_inv_outcomes(world):
    """Исходов в ходу: «истреблены» — только один из шестнадцати."""
    return len({item.outcome for item in _invasions(world) if item.outcome})


def m_inv_win_share(world):
    """Доля нашествий, кончившихся не победой людей."""
    from worldgen import invasion as inv
    rows = [item for item in _invasions(world) if item.outcome]
    theirs = sum(1 for item in rows
                 if item.outcome in (inv.OUT_VASSAL, inv.OUT_SETTLED,
                                     inv.OUT_JOINED, inv.OUT_BECAME,
                                     inv.OUT_HELD, inv.OUT_DEAL,
                                     inv.OUT_GOING, inv.OUT_HALF))
    return _share(theirs, len(rows))


def m_inv_ways(world):
    """Способов победы в ходу: убить вождя — не единственный."""
    return len({item.way for item in _invasions(world) if item.way})


def m_inv_goal_turns(world):
    """Доля нашествий, у которых цель переменилась по ходу."""
    rows = _invasions(world)
    return _share(sum(1 for item in rows if item.goal_turns), len(rows))


def m_inv_names(world):
    """Сколько имён в среднем у одного нашествия сверх своего."""
    rows = _invasions(world)
    if not rows:
        return None
    return round(sum(len(item.names) for item in rows) / float(len(rows)), 1)


def m_inv_remnants(world):
    """Доля нашествий, после которых что-то осталось."""
    rows = _invasions(world)
    return _share(sum(1 for item in rows if item.remnants), len(rows))


def m_inv_answers(world):
    """Доля нашествий, на которые державы отвечали по-разному."""
    rows = _invasions(world)
    mixed = 0
    for item in rows:
        kinds = {row.get("ответ") for row in item.answers}
        if len(kinds) >= 2:
            mixed += 1
    return _share(mixed, len(rows))


def m_rules_changed(world):
    """Правил мира, переменившихся от самой глубокой беды."""
    return len(world.notes.get("правила мира") or [])


def m_exodus(world):
    """Исходов из разорённых земель: беда не только убивает, но и гонит."""
    return sum(1 for calamity in world.calamities.values()
               for note in calamity.notes if note.startswith("исход из земли"))


def m_held_known(world):
    """Доля павших держав, о которых записано, чем они владели."""
    rows = [item for item in world.polities.values()
            if not item.settlement_ids]
    if not rows:
        return None
    return _share(sum(1 for item in rows if item.held_ids), len(rows))


def m_thin_codices(world):
    """Доля летописей, в которых нет и двух записей."""
    rows = list(world.codices.values())
    return _share(sum(1 for item in rows if len(item.entries) <= 1), len(rows))


def m_old_enemies(world):
    """Держав, у которых после беды завёлся старый враг."""
    return sum(1 for polity in world.polities.values()
               for note in polity.notes if note.startswith("старый враг"))


# --- расы ---------------------------------------------------------------------
# Мир, где одна раса заняла всё, а от прочих осталось по деревне, —
# это не история мира, а история одного народа. Меры ниже и есть
# записанный образ: рас в мире много, у главных из них есть числом
# народ, и вымирание — исключение, а не правило.

def _race_souls(world):
    from worldgen.races import RACES_BY_ID
    souls = world.population_by_race()
    return {race_id: value for race_id, value in souls.items()
            if race_id in RACES_BY_ID
            and RACES_BY_ID[race_id].first_era < 9 and value > 0}


def m_races_alive(world):
    return len(_race_souls(world))


def m_races_gone(world):
    return len(world.notes.get("народов больше нет") or {})


def m_race_top_share(world):
    souls = _race_souls(world)
    if not souls:
        return 0.0
    return _share(max(souls.values()), sum(souls.values()))


def m_races_weighty(world):
    """Сколько рас держит хотя бы сотую долю мира."""
    souls = _race_souls(world)
    total = sum(souls.values())
    if not total:
        return 0
    return sum(1 for value in souls.values() if value >= total * 0.01)


def m_race_towns(world):
    """У скольких оседлых рас есть хотя бы по три своих города."""
    from worldgen.races import RACES_BY_ID
    counts = {}
    for settlement_id in world.active_settlements:
        race_id = world.settlements[settlement_id].race_id
        counts[race_id] = counts.get(race_id, 0) + 1
    return sum(1 for race_id, count in counts.items()
               if count >= 3 and race_id in RACES_BY_ID
               and RACES_BY_ID[race_id].settles)


# --- вес людей ---------------------------------------------------------------

def m_weighed(world):
    return _share(len(world.renowns), len(world.figures))


def m_weigh_top(world):
    return sum(1 for item in world.renowns.values() if item.level >= 9)


def m_weigh_risen(world):
    return sum(1 for item in world.renowns.values()
               for row in item.reviews if row.get("стало") > row.get("было"))


def m_weigh_fallen(world):
    return sum(1 for item in world.renowns.values()
               for row in item.reviews if row.get("стало") < row.get("было"))


def m_weigh_forgotten(world):
    return sum(1 for item in world.renowns.values() if item.forgotten)


def m_weigh_memory_gap(world):
    rows = list(world.renowns.values())
    if not rows:
        return None
    fame = sum(item.fame for item in rows) / len(rows)
    memory = sum(item.memory for item in rows) / len(rows)
    return round(fame - memory, 1)


def m_weigh_untitled(world):
    """Сколько тяжёлых имён принадлежит людям без титулов.

    Это главная мера всей затеи: если вес и титул совпадают, значит, его
    всё-таки назначили по должности.
    """
    # Порог взят пятой ступенью, а не шестой: выше шестой имён в мире
    # считаные единицы, и ноль без титула выходит там случайностью сида, а
    # не приговором самой затее. Смысл меры от этого не меняется.
    count = 0
    for item in world.renowns.values():
        if item.level < 5:
            continue
        figure = world.figures.get(item.figure_id)
        if figure is not None and not figure.titles:
            count += 1
    return count


# --- субъекты истории --------------------------------------------------------

def _subjects(world):
    return list(world.subjects.values())


def _beast_ends(world):
    """Небывалые с названной причиной конца и сами эти причины."""
    from worldgen import mortality, races
    own = set()
    for pair in mortality.MONSTER_ANY:
        own.update(pair)
    for rows in mortality.MONSTER_END.values():
        for pair in rows:
            own.update(pair)
    named = []
    for figure in world.figures.values():
        kin = races.RACES_BY_ID.get(figure.race_id)
        if kin is None or kin.category != races.MONSTER:
            continue
        if figure.death_cause:
            named.append(figure.death_cause)
    return named, own


def m_beast_own_end(world):
    """Доля небывалых, кончивших по своей графе, а не по смертной.

    Не единица и не должна быть единицей: владыку вторжения часто
    сражают в бою, и это записано там, где случилось. Но если доля
    близка к нулю, значит своя графа до небывалых не доходит — а это та
    самая поломка, когда великий демон гибнет в обвале в горах.
    """
    named, own = _beast_ends(world)
    return _share(sum(1 for item in named if item in own), len(named))


def m_beast_end_kinds(world):
    """Сколько разных концов у небывалых: один на всех — не конец."""
    named, own = _beast_ends(world)
    if not named:
        return None
    return len({item for item in named if item in own})


def m_sub_kinds(world):
    """В своде не одни люди: дракон и бог проходят ту же систему."""
    return len({item.kind for item in _subjects(world)})


def m_sub_nonhuman(world):
    """Доля тех, кто вообще не человек."""
    from worldgen import subject as cat
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.kind != cat.PEOPLE),
                  len(rows))


def m_sub_not_born(world):
    """Доля тех, кто появился не рождением: призван, разбужен, сделан."""
    from worldgen import subject as cat
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.origin != cat.BORN),
                  len(rows))


def m_sub_unclear(world):
    """Доля тех, о ком хоть что-то неизвестно, спорно или обросло мифом."""
    from worldgen import subject as cat
    rows = _subjects(world)
    unclear = sum(1 for item in rows
                  if any(state not in (cat.FACT_KNOWN, cat.FACT_NONE)
                         for state in item.facts.values()))
    return _share(unclear, len(rows))


def m_sub_returned(world):
    """Доля вернувшихся: запечатанный не выбывает из истории."""
    rows = _subjects(world)
    return _share(sum(1 for item in rows if len(item.spans) > 1), len(rows))


def m_sub_quiet(world):
    """Доля тех, у кого между делами были годы молчания."""
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.quiet), len(rows))


def m_sub_turned(world):
    """Доля тех, у кого нрав переменился, и у перемены названа причина."""
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.temper_turns), len(rows))


def m_sub_got_it(world):
    """Доля добившихся своего: цель не равна результату."""
    from worldgen import subject as cat
    rows = _subjects(world)
    return _share(sum(1 for item in rows
                      if item.wish_state == cat.GOAL_DONE), len(rows))


def m_sub_rungs(world):
    """Ступеней памяти в ходу: не все же мифические."""
    return len({item.rung for item in _subjects(world)})


def m_sub_myth(world):
    """Доля мифических имён: их должно быть мало."""
    from worldgen import subject as cat
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.rung == cat.RUNG_MYTH),
                  len(rows))


def m_sub_named_late(world):
    """Доля тех, кого опознали через века после дела."""
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.named_year), len(rows))


def m_sub_legacy(world):
    """Доля тех, после кого что-то осталось."""
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.legacy), len(rows))


def m_sub_told(world):
    """Доля тех, о чьём конце рассказывают врозь."""
    rows = _subjects(world)
    return _share(sum(1 for item in rows if item.told), len(rows))


def m_sub_inner(world):
    """Доля тех, у кого есть дело, значившее для них больше, чем для мира."""
    rows = _subjects(world)
    inner = sum(1 for item in rows
                if any(int(mark.get("себе", 0)) > int(mark.get("мир", 0))
                       for mark in item.marks))
    return _share(inner, len(rows))


# --- следы бед ---------------------------------------------------------------

def _traces(world):
    return list(world.traces.values())


def m_tr_per_calamity(world):
    """Сколько следов остаётся от одной заметной беды."""
    from worldgen.systems import remains as engine
    heavy = [item for item in world.calamities.values()
             if item.severity >= engine.IMPRINT_FROM]
    if not heavy:
        return None
    return round(len(_traces(world)) / float(len(heavy)), 2)


def m_tr_kinds(world):
    """Родов следа в ходу: не одни могилы на весь мир."""
    return len({trace.kind for trace in _traces(world)})


def m_tr_indirect(world):
    """Доля косвенных следов — тех, что не кричат о беде."""
    rows = _traces(world)
    return _share(sum(1 for trace in rows if not trace.direct), len(rows))


def m_tr_whole(world):
    """Доля следов, дошедших целыми."""
    from worldgen import remains as cat
    rows = _traces(world)
    return _share(sum(1 for trace in rows if trace.state == cat.FRESH),
                  len(rows))


def m_tr_gone(world):
    """Доля следов, от которых не осталось ничего."""
    from worldgen import remains as cat
    rows = _traces(world)
    return _share(sum(1 for trace in rows if trace.state == cat.GONE),
                  len(rows))


def m_tr_unknown(world):
    """Доля следов, о которых так и не узнали."""
    from worldgen import remains as cat
    rows = _traces(world)
    return _share(sum(1 for trace in rows
                      if trace.knowledge == cat.FORGOTTEN), len(rows))


def m_tr_studied(world):
    """Доля разобранных учёными: их не должно быть большинство."""
    from worldgen import remains as cat
    rows = _traces(world)
    return _share(sum(1 for trace in rows
                      if trace.knowledge == cat.STUDIED), len(rows))


def m_tr_live(world):
    """Доля следов, за которыми стоит что-то живое."""
    rows = _traces(world)
    return _share(sum(1 for trace in rows if trace.life >= 4), len(rows))


def m_tr_echo(world):
    """Много ли живых следов успело отозваться новой бедой.

    Считать эхо штуками нечестно: чем больше в мире бед, тем больше и
    живых следов, и восемь отзывов в бурном мире — та же редкость, что
    три в тихом. «Однажды отзовётся» записано в правило следа, и
    спрашивать надо не «сколько раз», а для многих ли этот раз наступил.
    """
    rows = [trace for trace in _traces(world) if trace.life >= 4]
    echoes = sum(1 for event in world.events if event.kind == "trace_echo")
    return _share(echoes, len(rows))


def m_tr_quarrel(world):
    """Доля следов, которые спорят с другими о том же дне."""
    rows = _traces(world)
    return _share(sum(1 for trace in rows if trace.quarrel), len(rows))


def m_tr_dark(world):
    """Доля бед, о которых к концу истории нельзя сказать почти ничего.

    Граница тут широкая не от щедрости, а по замеру. Мера считается по
    **всем** заметным бедам истории, а в десятитысячелетнем мире почти все
    они древние: шесть миров по 10 000 лет дали 0,851 0,864 0,908 0,921
    0,923 0,925 — разброс целиком лежит в девятом десятке, и граница 0,92
    резала бы его пополам, срабатывая на здоровом мире через раз. Чёрную
    дыру в прошлом стережёт не она, а счёт рядом (`m_tr_some`): доля тьмы
    в мире с двумя сотнями бед и в мире с двумя десятками — про разное.
    """
    from worldgen.systems import remains as engine
    heavy = [item for item in world.calamities.values()
             if item.severity >= engine.IMPRINT_FROM]
    if not heavy:
        return None
    dark = sum(1 for item in heavy
               if engine.known_share(world, item, world.total_years) <= 0.25)
    return _share(dark, len(heavy))


def m_tr_some(world):
    """Сколько бед числом ещё можно хоть отчасти восстановить.

    Доля сама по себе ничего не стережёт. Девять десятых тьмы в мире, где
    заметных бед две сотни, оставляют потомкам два десятка узлов — этого
    хватит на любую повесть; те же девять десятых в мире с двадцатью
    бедами оставляют две, и прошлое правда становится чёрным. Поэтому
    считаем не долю, а штуки: сколько бед к концу истории ещё отвечают
    хоть на один вопрос потомков.
    """
    from worldgen.systems import remains as engine
    heavy = [item for item in world.calamities.values()
             if item.severity >= engine.IMPRINT_FROM]
    if not heavy:
        return None
    return sum(1 for item in heavy
               if engine.known_share(world, item, world.total_years) > 0.25)


def m_tr_clear(world):
    """Доля бед, восстановленных почти целиком."""
    from worldgen.systems import remains as engine
    heavy = [item for item in world.calamities.values()
             if item.severity >= engine.IMPRINT_FROM]
    if not heavy:
        return None
    clear = sum(1 for item in heavy
                if engine.known_share(world, item, world.total_years) >= 0.75)
    return _share(clear, len(heavy))


# --- праздники --------------------------------------------------------------

def _feasts(world) -> list:
    return list(world.holidays.values())


def m_hol_rose(world):
    """Доля дней памяти, доросших до праздника.

    Праздником не становится всякий день: девять поминовений из десяти
    тают вместе с теми, кто помнил. Если доля велика, лестница ступеней
    ничего не значит; если мала — мир не умеет ничего запомнить.
    """
    from worldgen import holidays as cat
    rows = _feasts(world)
    if not rows:
        return None
    return _share(sum(1 for item in rows if cat.is_feast(item.step)),
                  len(rows))


def m_hol_origins(world):
    """Сколько поводов в ходу: мир возвращается к разному."""
    rows = _feasts(world)
    if not rows:
        return None
    return len({item.origin for item in rows})


def m_hol_top_origin(world):
    """Крупнейший повод: ни один не должен забивать остальные."""
    rows = _feasts(world)
    if not rows:
        return None
    counts = {}
    for item in rows:
        counts[item.origin] = counts.get(item.origin, 0) + 1
    return _share(max(counts.values()), len(rows))


def m_hol_lost(world):
    """Доля дней, у которых повод забыт.

    Это главная мера модуля: обряд обязан переживать свой смысл. Ноль
    значит, что мир помнит всё, — а так не бывает.
    """
    rows = _feasts(world)
    if not rows:
        return None
    return _share(sum(1 for item in rows if item.lost_why), len(rows))


def m_hol_retold(world):
    """Доля дней, у которых сменился смысл: день о другом, чем был."""
    rows = _feasts(world)
    if not rows:
        return None
    return _share(sum(1 for item in rows
                      if item.now_meaning
                      and item.now_meaning != item.first_meaning), len(rows))


def m_hol_banned(world):
    """Сколько дней запрещали: власть вмешивается в календарь."""
    rows = _feasts(world)
    if not rows:
        return None
    return sum(1 for item in rows if item.bans)


def m_hol_back(world):
    """Сколько вернулось после запрета: запрет не всегда конец."""
    from worldgen import holidays as cat
    rows = _feasts(world)
    if not rows:
        return None
    return sum(1 for item in rows
               if item.state == cat.REVIVED
               or any(row.get("по") for row in item.bans))


def m_hol_doings(world):
    """Случаи на самом празднике: он не декорация, на нём случается."""
    rows = _feasts(world)
    if not rows:
        return None
    return sum(len(item.doings) for item in rows)


def m_hol_variants(world):
    """Доля дней, которые кто-то держит на свой лад: одно число — разные
    смыслы. Без этого праздник одинаков у всех, чего не бывает."""
    rows = _feasts(world)
    if not rows:
        return None
    return _share(sum(1 for item in rows if item.variants), len(rows))


def m_hol_holders(world):
    """Сколько разных держателей в ходу: день держит не одна держава."""
    rows = _feasts(world)
    if not rows:
        return None
    return len({item.holder for item in rows})


def m_hol_marks(world):
    """Сколько дней оставили по себе постройку: площадь переживает праздник."""
    rows = _feasts(world)
    if not rows:
        return None
    return sum(1 for item in rows if item.marks)


def m_hol_stories(world):
    """Сколько былей выросло из праздников: обряд без причины — готовый
    исторический узел, и мир обязан его замечать."""
    from worldgen import localstory as cat
    feast_nodes = (cat.BLIND_RITE, cat.HID_FEAST, cat.FEAST_MARK)
    return sum(1 for item in world.stories.values()
               if item.node in feast_nodes)


# --- начало мира ------------------------------------------------------------

def m_or_layers(world):
    """Сколько слоёв мира положено. Все двенадцать — скучно, пять — пусто."""
    origin = world.origin
    return len(origin.layers) if origin is not None else None


def m_or_missing(world):
    """Сколько слоёв в мире нет вовсе.

    Мир без сна, без души или без магии — не обеднённый мир, а другой.
    Если таких слоёв не бывает никогда, то и выбора никакого нет.
    """
    origin = world.origin
    return len(origin.missing) if origin is not None else None


def m_or_inverted(world):
    """Встал ли хоть один слой прежде того, на чём держится.

    Смерть прежде жизни, сознание прежде живого — самое заметное, что
    может случиться с порядком. Мера считает такие случаи штуками.
    """
    from worldgen import origin as cat
    origin = world.origin
    if origin is None:
        return None
    place = {row["слой"]: index
             for index, row in enumerate(origin.order)}
    count = 0
    for key, index in place.items():
        layer = cat.LAYERS.get(key)
        if layer is None:
            continue
        for need in layer.needs:
            if need in place and place[need] > index:
                count += 1
    return count


def m_or_named_laws(world):
    """Сколько законов мир называет вслух."""
    origin = world.origin
    if origin is None:
        return None
    return sum(1 for row in origin.laws if row.get("известен"))


def m_or_quiet_laws(world):
    """И сколько действует молча.

    Мир, который назвал все свои правила, знает о себе больше, чем
    бывает. Непоименованные законы — не умолчание, а честность.
    """
    origin = world.origin
    if origin is None:
        return None
    return sum(1 for row in origin.laws if not row.get("известен"))


def m_or_scars(world):
    """Шрамов творения на земле."""
    origin = world.origin
    return len(origin.scars) if origin is not None else None


def m_or_scar_places(world):
    """Доля шрамов, до которых можно дойти ногами.

    Шрам, к которому нет места на карте, остаётся строкой в мифе; шрам
    с местом однажды найдут, и это будет уже обычная быль.
    """
    origin = world.origin
    if origin is None or not origin.scars:
        return None
    return _share(sum(1 for row in origin.scars if row.get("место")),
                  len(origin.scars))


def m_or_versions(world):
    """Сколько народов рассказывают о начале по-своему."""
    origin = world.origin
    return len(origin.versions) if origin is not None else None


def m_or_open_clash(world):
    """Сколько противоречий о начале осталось нерешёнными.

    Генератор не обязан их разрешать: нерешённое — это то, до чего потом
    докапывается быль.
    """
    origin = world.origin
    return len(origin.open_clashes) if origin is not None else None


def m_or_unknown(world):
    """Сколько вопросов о начале осталось без ответа."""
    origin = world.origin
    return len(origin.unknown) if origin is not None else None


# ---------------------------------------------------------------------------
# Земля: вес мест
# ---------------------------------------------------------------------------

# Сколько гексов брать на пробу. Весь мир перебирать нельзя: вес одного
# места считается по всем битвам и всем бедам мира, и полтораста тысяч
# гексов обошлись бы в часы. Двести с лишним гексов вразбивку говорят о
# доле ровно то же, что весь мир.
LAND_SAMPLE = 220

# Сколько заметных мест взвешивать полным весом.
LAND_TOP = 120


def _land_scores(world):
    """Вес проб: (гексы вразбивку, заметные места). Считается один раз."""
    found = getattr(world, "_audit_land", None)
    if found is not None:
        return found
    from worldgen import landlore
    link = getattr(world, "map_link", None)
    wmap = getattr(link, "wmap", None) if link is not None else None
    if wmap is None:
        world._audit_land = ((), ())
        return world._audit_land
    size = wmap.width * wmap.height
    land = [index for index in range(size) if wmap.is_land(index)]
    step = max(1, len(land) // LAND_SAMPLE)
    spread = [landlore.weight(world, index) for index in land[::step]]
    top = [landlore.weight(world, index)
           for index, _said in landlore.notable(world, LAND_TOP)]
    world._audit_land = (tuple(spread), tuple(top))
    return world._audit_land


def m_land_dull(world):
    """Доля мест, о которых нечего сказать."""
    spread, _top = _land_scores(world)
    if not spread:
        return None
    from worldgen.landlore import WEIGHT_WORDS
    dull = WEIGHT_WORDS[-1][1]
    return sum(1 for _score, verdict, _why in spread
               if verdict == dull) / float(len(spread))


def m_land_pivot(world):
    """Сколько мест, вокруг которых повернулась история."""
    _spread, top = _land_scores(world)
    if not top:
        return None
    from worldgen.landlore import WEIGHT_WORDS
    edge = WEIGHT_WORDS[0][0]
    return sum(1 for score, _verdict, _why in top if score >= edge)


def m_land_voices(world):
    """Сколько разных приговоров о весе в ходу."""
    spread, top = _land_scores(world)
    if not spread and not top:
        return None
    return len({verdict for _score, verdict, _why in tuple(spread) + tuple(top)})


def m_land_reasons(world):
    """Доля весомых мест, у которых вес объяснён делом."""
    spread, top = _land_scores(world)
    rows = [row for row in tuple(spread) + tuple(top) if row[0] > 0]
    if not rows:
        return None
    return sum(1 for _score, _verdict, why in rows if why) / float(len(rows))


def m_land_told(world):
    """Сколько записей в летописи самого весомого места."""
    from worldgen import landlore
    best = landlore.best_hex(world)
    if best < 0:
        return None
    return len(landlore.timeline(world, best))


def m_land_words(world):
    """Сколько строк об условиях у самого скудного места пробы."""
    from worldgen import landlore
    link = getattr(world, "map_link", None)
    wmap = getattr(link, "wmap", None) if link is not None else None
    if wmap is None:
        return None
    size = wmap.width * wmap.height
    land = [index for index in range(size) if wmap.is_land(index)]
    if not land:
        return None
    step = max(1, len(land) // 40)
    return min(len(landlore.conditions(world, index))
               for index in land[::step])


# ---------------------------------------------------------------------------
# Города: сколько их и каковы они
# ---------------------------------------------------------------------------

# Смотр мерил у городов всё, кроме главного: сколько их и велики ли они.
# Оттого и вышло, что в мире копились середняки — сто с лишним поселений,
# из которых ни одно не доросло до великого города, — а ни одна мера на
# это не срабатывала.


def _alive_towns(world) -> list:
    return [world.settlements[sid] for sid in world.active_settlements]


def m_town_count(world):
    """Живых поселений на одну землю."""
    towns = _alive_towns(world)
    if not world.regions:
        return None
    return len(towns) / float(len(world.regions))


def m_town_is_city(world):
    """Доля живых поселений, доросших до города и выше."""
    towns = _alive_towns(world)
    if not towns:
        return None
    return sum(1 for item in towns
               if town_cat.is_city(item.rank)) / float(len(towns))


def m_town_biggest(world):
    """Людность самого большого города мира."""
    towns = _alive_towns(world)
    if not towns:
        return None
    return max(item.population for item in towns)


def m_town_primacy(world):
    """Во сколько раз первый город мира больше середняка.

    Если это число около единицы, в мире нет ни первого города, ни
    столицы — одни одинаковые поселения.
    """
    towns = sorted(item.population for item in _alive_towns(world))
    if len(towns) < 4:
        return None
    middle = towns[len(towns) // 2]
    return towns[-1] / float(max(1, middle))


def m_town_one_city(world):
    """Доля держав, у которых всего один город.

    Город-государство — дело обычное, и нулю эта доля быть не должна. Но
    когда из одного города состоит почти всякая держава, это уже не мир
    держав, а мир городов со стенами, между которыми ничего нет.
    """
    counts = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        counts.append(sum(1 for sid in polity.settlement_ids
                          if sid in world.active_settlements))
    if not counts:
        return None
    return sum(1 for value in counts if value <= 1) / float(len(counts))


def m_town_realm(world):
    """Сколько городов у самой большой державы мира.

    Доля держав из одного города зависит от того, сколько в мире городов
    вообще: когда их пятьдесят на тридцать держав, иначе и быть не может.
    А вот то, что в мире есть хоть одна настоящая держава, — отдельное
    утверждение, и от числа городов оно не зависит.
    """
    best = 0
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        best = max(best, sum(1 for sid in polity.settlement_ids
                             if sid in world.active_settlements))
    return best or None


def m_town_great(world):
    """Доля живых поселений, доросших до великого города.

    Великий город должен быть редкостью: когда их десяток, слово «великий»
    перестаёт что-либо значить.
    """
    towns = _alive_towns(world)
    if not towns:
        return None
    return sum(1 for item in towns
               if item.rank == town_cat.GREAT_CITY) / float(len(towns))


def m_town_urban(world):
    """Какая доля мира живёт в городах."""
    souls = world.world_population()
    if souls <= 0:
        return None
    return sum(item.population for item in _alive_towns(world)) / float(souls)


MEASURES = (
    Measure("были", "не про судьбу мира", m_story_small, 0.82, 0.98,
            "доля", "девять из десяти былей не спасают мир"),
    Measure("были", "костяков в ходу", m_story_shapes, 18, None, "из 24",
            "мир рассказывает разное, а не одно и то же"),
    Measure("были", "крупнейший костяк", m_story_top_shape, None, 0.28,
            "доля", "ни один сюжет не забивает остальные"),
    Measure("были", "поворот подготовлен", m_story_seeded, 1.0, None, "доля",
            "поворот разрешён только подготовленный"),
    Measure("были", "имена не повторяются", m_story_unique, 1.0, None, "доля",
            ""),
    Measure("были", "выросли из мира", m_story_world_nodes, 0.18, 0.65,
            "доля", "истории растут из городов, богов и памяти людей"),
    Measure("были", "крупнейший узел", m_story_top_node, None, 0.22, "доля",
            ""),
    Measure("города", "с биографией", m_town_covered, 0.9, None, "доля",
            "у всякого заметного города есть своя история"),
    Measure("города", "видов причин", m_town_origins, 8, None, "из 17",
            "города встают по разным причинам"),
    Measure("города", "крупнейшая причина", m_town_top_origin, None, 0.28,
            "доля", ""),
    Measure("города", "занятий в ходу", m_town_trades, 8, None, "из 20", ""),
    Measure("города", "меняли занятие", m_town_changed, 0.15, 0.9, "доля",
            "потерявший кормильца ищет новое дело"),
    Measure("города", "концов у живого", m_town_districts, 2.0, 11.0,
            "штук",
            "у большого города концов с десяток, но не весь каталог"),
    Measure("города", "слоёв у старого", m_town_layers, 1.2, 9.0, "штук",
            "под старым городом лежит старый город"),
    Measure("города", "со своей тайной", m_town_secrets, 0.35, None, "доля",
            ""),
    Measure("города", "тайн вскрыто былями", m_town_secrets_open, 1, None,
            "штук", "быль доходит до правды, и город узнаёт о себе",
            min_years=1500),
    Measure("города", "встали на старом месте", m_town_reborn, 0.02, 0.6,
            "доля", "города-призраки и те, кто пришёл после них"),
    Measure("города", "живых на землю", m_town_count, 1.0, 6.0, "штук",
            "земля держит столько городов, сколько кормит"),
    Measure("города", "доросли до города", m_town_is_city, 0.2, 0.95,
            "доля", "городом зовётся не всякое поселение"),
    Measure("города", "великих городов", m_town_great, None, 0.25, "доля",
            "великий город — редкость, иначе слово ничего не значит"),
    Measure("города", "людность первого города", m_town_biggest, 15000, None,
            "душ", "в мире есть хоть один настоящий город",
            min_years=3000),
    Measure("города", "первый город больше середняка", m_town_primacy, 3.0,
            None, "раз", "у мира есть главный город, а не сто одинаковых"),
    Measure("города", "держав из одного города", m_town_one_city, None, 0.9,
            "доля",
            "город-государство — дело обычное, когда городов в мире мало; "
            "но не всякая же держава"),
    Measure("города", "городов у крупнейшей державы", m_town_realm, 3, None,
            "штук", "в мире есть хоть одна настоящая держава, а не только "
            "города со стенами"),
    Measure("города", "живут в городах", m_town_urban, 0.04, 0.35, "доля",
            "город кормится деревней, и деревня больше города"),
    Measure("боги", "с биографией", m_god_covered, 1.0, None, "доля", ""),
    Measure("боги", "видов происхождения", m_god_origins, 5, None, "из 12",
            ""),
    Measure("боги", "народов в покровительстве", m_god_favour, 2.0, None,
            "штук", "покровительство — число с причиной, а не да/нет"),
    Measure("боги", "расхождение с культом", m_god_drift, 0.03, 0.65,
            "из 1", "жрецы читают волю по-своему, но не до неузнаваемости"),
    Measure("боги", "у ереси названа причина", m_heresy_reason, 0.6, None,
            "доля", "ересь рождается не из пустоты"),
    Measure("боги", "пророчеств истолковано", m_prophecy_read, 1, None,
            "штук", "разгадывает их быль, а не храм", min_years=1500),
    Measure("боги", "следов первородных", m_myth_traces, 0, None, "штук",
            "мифический век оставляет настоящие места"),
    Measure("вес", "взвешено от всех", m_weighed, 0.01, 0.2, "доля",
            "подробно ведутся не все"),
    Measure("вес", "высших имён (9–10)", m_weigh_top, 0, 6, "штук",
            "таких единицы за всю историю мира"),
    Measure("вес", "имён поднялось", m_weigh_risen, 1, None, "штук",
            "значение приходит и после смерти", min_years=1500),
    Measure("вес", "имён осело", m_weigh_fallen, 1, None, "штук",
            "и уходит тоже"),
    Measure("вес", "забытых великих", m_weigh_forgotten, 1, None, "штук",
            "слава и память — разные вещи", min_years=3000),
    Measure("вес", "слава выше памяти на", m_weigh_memory_gap, 5.0, None,
            "пунктов", "память тает, а слава остаётся записанной",
            min_years=3000),
    Measure("вес", "тяжёлых имён без титула", m_weigh_untitled, 1, None,
            "штук", "вес считается по делам, а не по должности",
            min_years=3000),
    Measure("расы", "дожило до конца", m_races_alive, 8, None, "из 21",
            "мир не сводится к трём народам"),
    Measure("расы", "ушло из мира", m_races_gone, None, 7, "штук",
            "вымирание — исключение, а не правило", min_years=3000),
    Measure("расы", "доля крупнейшей", m_race_top_share, None, 0.55, "доля",
            "одна раса не занимает весь мир"),
    Measure("расы", "держат сотую долю мира", m_races_weighty, 5, None,
            "штук", "у главных народов есть числом народ"),
    Measure("расы", "оседлых с тремя городами", m_race_towns, 4, None, "штук",
            "города строит не одна раса"),
    Measure("беда", "причина названа", m_cause_named, 0.8, None, "доля",
            "у беды есть причина, а не «случилось само»"),
    Measure("беда", "известная причина — не та", m_cause_hidden, 0.08, 0.6,
            "доля", "мир не всегда знает, отчего это было"),
    Measure("беда", "знаки прочли верно", m_omens_read, 0.1, 0.65, "доля",
            "предупреждение — не подарок: нужен тот, кто умеет читать"),
    Measure("беда", "отведено до начала", m_prevented, 1, None, "штук",
            "люди иногда успевают, иначе мир безнадёжен", min_years=3000),
    Measure("беда", "власть ответила делом", m_responses, 0.5, None, "доля",
            "на беду отвечают решениями, а не только терпят"),
    Measure("беда", "решения вышли ошибкой", m_mistakes, 0.03, 0.6, "доля",
            "беду делают бедой решения в столицах"),
    Measure("беда", "выросло из прежней", m_chained, 0.05, 0.45, "доля",
            "цепь бед затухает, а не съедает мир"),
    Measure("шрамы", "видов в ходу", m_scar_kinds, 8, None, "из 29",
            "следы бед разные, а не два на весь мир"),
    Measure("шрамы", "доля самого частого", m_scar_top, None, 0.3, "доля",
            "ни один след не занимает четверть всех"),
    Measure("шрамы", "состояний в ходу", m_scar_states, 3, None, "из 5",
            "шрам живёт: его обходят, обживают, освящают, забывают"),
    Measure("шрамы", "мир ещё помнит", m_scar_remembered, 0.12, None, "доля",
            "не всё уходит в забвение — место, которого боятся, помнят"),
    Measure("утраты", "знаний потеряно", m_lore_lost, 3, None, "штук",
            "большая беда уносит не только людей", min_years=3000),
    Measure("утраты", "так и не вернулось", m_lore_kept, 0.18, None, "доля",
            "если возвращается всё, утрата ничего не значит",
            min_years=3000),
    Measure("память", "о беде спорят", m_versions, 0.3, None, "доля",
            "одного рассказа о большой беде не бывает"),
    Measure("память", "времён бед", m_eras, 1, None, "штук",
            "цепь бед складывается в одно время с именем",
            min_years=3000),
    Measure("память", "длина времени бед", m_era_length, 30, 320, "лет",
            "эпоха — сгущение, а не полтысячи лет", min_years=3000),
    Measure("память", "у времени много имён", m_era_voices, 0.5, None, "доля",
            "держава помнит войну, деревня — голодные годы",
            min_years=3000),
    Measure("фронт", "записей о ходе", m_front_lands, 3.0, None, "штук",
            "нашествие идёт по землям, а не ложится сразу"),
    Measure("фронт", "земли остались за чужими", m_front_kept, 0.05, 0.5,
            "доля", "победой возвращают не всё, но и не теряют своих земель"),
    Measure("наука", "земель с делами людей", m_learned, 0.15, None, "доля",
            "земля учится: дамбы, амбары, стены, карантин"),
    Measure("наука", "городов с привычкой", m_habits, 0.1, None, "доля",
            "уклад держат веками, забыв причину"),
    Measure("нашествия", "родов пришедших", m_inv_kinds, 3, None, "из 12",
            "приходят разные, а не одни драконы", min_years=3000),
    Measure("нашествия", "причин прихода", m_inv_causes, 4, None, "из 16",
            "нашествие — не всегда война", min_years=3000),
    Measure("нашествия", "целей, с какими пришли", m_inv_goals, 4, None,
            "из 20", "не всякий пришедший хочет взять землю",
            min_years=3000),
    Measure("нашествия", "пришли воевать", m_inv_war_share, None, 0.6, "доля",
            "миграция, охота и бегство — тоже нашествия"),
    Measure("нашествия", "началось не с битвы", m_inv_peaceful_start, 0.25,
            None, "доля", "первая встреча часто переговоры, а не бой"),
    Measure("нашествия", "исходов в ходу", m_inv_outcomes, 4, None, "из 16",
            "«истреблены» — только один из шестнадцати", min_years=3000),
    Measure("нашествия", "кончилось не победой людей", m_inv_win_share, 0.15,
            None, "доля", "захватчики не обязаны проигрывать"),
    Measure("нашествия", "способов победы", m_inv_ways, 5, None, "из 23",
            "убить вождя — не единственный способ", min_years=3000),
    Measure("нашествия", "цель переменилась", m_inv_goal_turns, 0.08, None,
            "доля", "нашествие развивается, а не идёт по плану"),
    Measure("нашествия", "имён сверх своего", m_inv_names, 2.0, None, "штук",
            "одно событие зовут по-разному разные голоса"),
    Measure("нашествия", "что-то осталось после", m_inv_remnants, 0.35, None,
            "доля", "из остатков через века растут новые беды"),
    Measure("нашествия", "отвечали врозь", m_inv_answers, 0.2, None, "доля",
            "кто воевал, не простит тому, кто заплатил"),
    Measure("субъекты", "конец по своей графе", m_beast_own_end, 0.2, None,
            "доля", "демон не гибнет в обвале в горах"),
    Measure("субъекты", "разных концов у небывалых", m_beast_end_kinds, 4,
            None, "видов", "один конец на всех — не конец, а отписка",
            min_years=3000),
    Measure("субъекты", "родов в своде", m_sub_kinds, 3, None, "из 13",
            "дракон, бог и крестьянин проходят одну систему",
            min_years=3000),
    Measure("субъекты", "не люди", m_sub_nonhuman, 0.1, None, "доля",
            "историческая личность не обязана быть человеком"),
    Measure("субъекты", "появились не рождением", m_sub_not_born, 0.15, None,
            "доля", "призван, разбужен, сделан — тоже появление"),
    Measure("субъекты", "о ком что-то неясно", m_sub_unclear, 0.3, None,
            "доля", "«неизвестно» не значит «нет»"),
    Measure("субъекты", "вернулись после молчания", m_sub_returned, 0.03,
            0.5, "доля", "запечатанный не выбывает из истории",
            min_years=3000),
    Measure("субъекты", "молчали между делами", m_sub_quiet, 0.08, None,
            "доля", "бессмертный вмешивается не все свои тысячи лет",
            min_years=3000),
    Measure("субъекты", "нрав переменился", m_sub_turned, 0.15, None, "доля",
            "и у перемены названа причина"),
    Measure("субъекты", "добились своего", m_sub_got_it, None, 0.35, "доля",
            "цель не равна результату"),
    Measure("субъекты", "ступеней памяти в ходу", m_sub_rungs, 3, None,
            "из 5", "ступень собирается из дел, а не выдаётся"),
    Measure("субъекты", "мифических имён", m_sub_myth, None, 0.25, "доля",
            "мифом становятся немногие и не сразу"),
    Measure("субъекты", "опознаны позже", m_sub_named_late, 0.02, None,
            "доля", "кто вёл ту войну, выясняли и через двести лет",
            min_years=3000),
    Measure("субъекты", "оставили след", m_sub_legacy, 0.5, 0.97, "доля",
            "смерть не убирает из истории, но след держится не у всех"),
    Measure("субъекты", "рассказывают врозь", m_sub_told, 0.3, None, "доля",
            "объективно запечатан, а в народе убит"),
    Measure("субъекты", "дело важнее для него, чем для мира", m_sub_inner,
            0.2, None, "доля",
            "мир не заметил, а он после этого стал другим"),
    Measure("следы", "следов на беду", m_tr_per_calamity, 1.0, None, "штук",
            "всякая заметная беда оставляет по себе хоть что-то"),
    Measure("следы", "родов следа в ходу", m_tr_kinds, 6, None, "из 12",
            "не одни могилы: обычай и кровь тоже след", min_years=3000),
    Measure("следы", "косвенных", m_tr_indirect, 0.25, None, "доля",
            "самые интересные следы не кричат о беде"),
    Measure("следы", "дошло целыми", m_tr_whole, None, 0.8, "доля",
            "время берёт своё"),
    Measure("следы", "утрачено", m_tr_gone, 0.02, None, "доля",
            "часть следов не доживает ни до кого", min_years=3000),
    Measure("следы", "о которых не знают", m_tr_unknown, 0.15, None, "доля",
            "в земле лежит больше, чем находят"),
    Measure("следы", "разобрано учёными", m_tr_studied, None, 0.45, "доля",
            "объяснить удаётся не всё и не всем"),
    Measure("следы", "живых следов", m_tr_live, None, 0.18, "доля",
            "не в каждой пещере сидит древний демон"),
    Measure("следы", "живых следов отозвалось", m_tr_echo, None, 0.45,
            "доля", "спящая угроза чаще так и остаётся спящей",
            min_years=3000),
    Measure("следы", "спорят между собой", m_tr_quarrel, 0.01, None, "доля",
            "свидетельства не обязаны сходиться", min_years=3000),
    Measure("начало", "слоёв положено", m_or_layers, 5, 12, "из 12",
            "мир сложен по частям, и частей не две и не все"),
    Measure("начало", "слоёв нет вовсе", m_or_missing, None, 5, "штук",
            "мир без сна или без магии — не обеднённый, а другой"),
    Measure("начало", "слоёв не на своём месте", m_or_inverted, None, 3,
            "штук", "смерть прежде жизни — редкость, а не обычай"),
    Measure("начало", "законов названо", m_or_named_laws, 1, 7, "штук",
            "несколько правил говорят о мире больше, чем все"),
    Measure("начало", "законов действует молча", m_or_quiet_laws, 1, None,
            "штук", "мир не знает о себе всего"),
    Measure("начало", "шрамов творения", m_or_scars, 1, 5, "штук",
            "творение оставило следы, но мир не поле аномалий"),
    Measure("начало", "шрамов с местом", m_or_scar_places, 0.2, None, "доля",
            "до следа творения можно дойти ногами"),
    Measure("начало", "версий начала", m_or_versions, 1, None, "штук",
            "у каждого народа свой рассказ о том, как всё было"),
    Measure("начало", "споров не решено", m_or_open_clash, 1, None, "штук",
            "о начале спорят, и спор не всегда решается", min_years=1500),
    Measure("начало", "вопросов без ответа", m_or_unknown, None, None,
            "штук", "о начале известно ровно столько, сколько известно"),
    Measure("праздники", "доросли до праздника", m_hol_rose, 0.08, 0.6,
            "доля", "праздником становится не всякий день памяти"),
    Measure("праздники", "поводов в ходу", m_hol_origins, 12, None, "из 45",
            "мир возвращается к разному, а не к одному"),
    Measure("праздники", "крупнейший повод", m_hol_top_origin, None, 0.3,
            "доля", "ни один повод не забивает остальные"),
    Measure("праздники", "повод забыт", m_hol_lost, 0.12, 0.85, "доля",
            "обряд переживает свой смысл", min_years=3000),
    Measure("праздники", "смысл сменился", m_hol_retold, 0.1, None, "доля",
            "день со временем становится днём о другом", min_years=1500),
    Measure("праздники", "запрещали дней", m_hol_banned, 1, None, "штук",
            "власть вмешивается в календарь", min_years=3000),
    Measure("праздники", "вернулось после запрета", m_hol_back, None, None,
            "штук", "запрет не всегда конец", min_years=3000),
    Measure("праздники", "случаев на празднике", m_hol_doings, 1, None,
            "штук", "праздник не декорация: в тесноте что-то случается",
            min_years=1500),
    Measure("праздники", "держат на свой лад", m_hol_variants, 0.04, None,
            "доля", "одно число — разные смыслы", min_years=1500),
    Measure("праздники", "держателей в ходу", m_hol_holders, 3, None, "из 9",
            "день держит не одна держава"),
    Measure("праздники", "оставили постройку", m_hol_marks, 1, None, "штук",
            "площадь переживает праздник", min_years=3000),
    Measure("праздники", "былей из праздников", m_hol_stories, 1, None,
            "штук", "обряд без причины — готовый узел для были",
            min_years=3000),
    Measure("следы", "бед, о которых ничего не восстановить", m_tr_dark,
            0.1, 0.96, "доля", "прошлое темнеет, но не до черноты",
            min_years=3000),
    Measure("следы", "бед, о которых ещё можно узнать", m_tr_some, 3, None,
            "штук", "в прошлом остаются узлы, а не чёрная дыра",
            min_years=3000),
    Measure("следы", "бед, восстановленных целиком", m_tr_clear, None, 0.5,
            "доля", "полная ясность о древности — подделка",
            min_years=3000),
    Measure("мир", "правил переменилось", m_rules_changed, None, 5, "из 7",
            "мир меняется от самых глубоких бед, но не каждый век"),
    Measure("мир", "исходов из земель", m_exodus, 1, None, "штук",
            "разорённая земля пустеет не только мёртвыми", min_years=3000),
    Measure("мир", "держав со старым врагом", m_old_enemies, 1, None, "штук",
            "после беды остаётся тот, кто не пришёл", min_years=3000),
    Measure("мир", "павших держав, о которых известно, чем владели",
            m_held_known, 0.95, None, "доля",
            "держава остаётся тем, чем владела, даже когда не владеет ничем"),
    Measure("мир", "летописей в одну запись", m_thin_codices, None, 0.2,
            "доля", "свод начинают с того, что город ещё помнит",
            min_years=3000),
    Measure("земля", "мест, о которых нечего сказать", m_land_dull, 0.6,
            None, "доля",
            "если весомо всякое место, то весомого в мире нет"),
    Measure("земля", "мест, повернувших историю", m_land_pivot, 1, 30,
            "штук", "таких мест единицы, но они есть", min_years=6000),
    Measure("земля", "приговоров о весе в ходу", m_land_voices, 3, None,
            "из 5", "мера веса различает места, а не делит их надвое"),
    Measure("земля", "вес объяснён делом", m_land_reasons, 1.0, None,
            "доля", "число без названной причины — вес по приговору, а не "
            "по делам"),
    Measure("земля", "записей о самом весомом месте", m_land_told, 5, None,
            "штук", "у весомого места есть что рассказать"),
    Measure("земля", "строк об условиях у скудного места", m_land_words, 3,
            None, "штук", "о всяком месте есть что сказать прозой"),
)


# ---------------------------------------------------------------------------
# Прогон
# ---------------------------------------------------------------------------

def random_map(rng) -> dict:
    """Случайная карта: размер, сид, число материков и замкнутость."""
    return {
        "seed": make_seed_text(rng.randint(1, 2 ** 40)),
        "size": rng.weighted((("small", 3.0), ("medium", 1.0))),
        "continents": rng.randint(1, 6),
        "wrap": rng.chance(0.6),
    }


def run_one(seed: str, years: int, use_map: bool, rng) -> tuple:
    settings = Settings(seed=seed, years=years)
    if use_map:
        settings = Settings(seed=seed, years=years,
                            map_make=random_map(rng)).normalized()
    started = time.time()
    world = generate(settings)
    spent = time.time() - started
    rows = []
    for measure in MEASURES:
        if measure.min_years and world.total_years < measure.min_years:
            rows.append((measure, None, "коротко"))
            continue
        try:
            value = measure.func(world)
        except Exception as error:                        # noqa: BLE001
            rows.append((measure, None, "СБОЙ: %s" % error))
            continue
        rows.append((measure, value, measure.verdict(value)))
    return world, rows, spent


def print_world(seed: str, world, rows, spent: float, use_map: bool) -> int:
    print("=" * 78)
    print("МИР «%s»%s — %d лет за %.0f с" % (
        seed, ", своя карта" if use_map else "", world.total_years, spent))
    print("  событий %d | городов %d | держав %d | богов %d | былей %d | "
          "имён %d" % (len(world.events), len(world.settlements),
                       len(world.polities), len(world.deities),
                       len(world.stories), len(world.renowns)))
    print("-" * 78)
    bad = 0
    group = ""
    for measure, value, verdict in rows:
        if measure.group != group:
            group = measure.group
            print("  %s" % group.upper())
        if verdict not in ("в норме", "—", "коротко"):
            bad += 1
        shown = "—" if value is None else (
            "%.3f" % value if isinstance(value, float) else str(value))
        print("    %-28s %10s %-9s %-8s %s"
              % (measure.name, shown, measure.unit, verdict,
                 measure.about if verdict != "в норме" else ""))
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description="Смотр мира")
    parser.add_argument("--worlds", type=int, default=1)
    parser.add_argument("--years", type=int, default=10000)
    parser.add_argument("--seed", default="")
    parser.add_argument("--map", action="store_true",
                        help="строить миры на случайных картах")
    parser.add_argument("--mixed", action="store_true",
                        help="через один: с картой и без")
    args = parser.parse_args()

    # Сид смотра берётся случайным (единственное недетерминированное
    # место), но дальше всё считается от него: прогон повторяем.
    rng = Rng(args.seed or random_seed_text())
    total_bad = 0
    for number in range(args.worlds):
        seed = args.seed if args.seed and args.worlds == 1 \
            else make_seed_text(rng.randint(1, 2 ** 40))
        use_map = args.map or (args.mixed and number % 2 == 1)
        world, rows, spent = run_one(seed, args.years, use_map, rng)
        total_bad += print_world(seed, world, rows, spent, use_map)
    print("=" * 78)
    print("Мер вне границ: %d." % total_bad if total_bad
          else "Все меры в норме.")
    return 1 if total_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
