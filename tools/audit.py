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
    count = 0
    for item in world.renowns.values():
        if item.level < 6:
            continue
        figure = world.figures.get(item.figure_id)
        if figure is not None and not figure.titles:
            count += 1
    return count


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
    Measure("города", "концов у живого", m_town_districts, 2.0, 8.0, "штук",
            ""),
    Measure("города", "слоёв у старого", m_town_layers, 1.2, 9.0, "штук",
            "под старым городом лежит старый город"),
    Measure("города", "со своей тайной", m_town_secrets, 0.35, None, "доля",
            ""),
    Measure("города", "тайн вскрыто былями", m_town_secrets_open, 1, None,
            "штук", "быль доходит до правды, и город узнаёт о себе",
            min_years=1500),
    Measure("города", "встали на старом месте", m_town_reborn, 0.02, 0.6,
            "доля", "города-призраки и те, кто пришёл после них"),
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
