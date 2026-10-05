# -*- coding: utf-8 -*-
"""Быстрая самопроверка движка.

Запуск:  python tools/selfcheck.py

Проверяет три вещи, которые легко сломать при добавлении новых блоков:

1. детерминированность — один сид даёт побайтово одну и ту же летопись;
2. сохранение и загрузка мира не теряют ни одной записи;
3. правила рас соблюдаются: зверолюды живут племенами, злые расы не
   строят государств и городов;
4. устройство знати: фамилии только у знатных, роды только у тех рас,
   у которых знать бывает, правления идут по порядку;
5. бедствия: у каждого есть исход, следы и битвы ссылаются на своё
   бедствие, потери не превышают населения, тёмные века не вечны;
6. вера: у каждого бога есть вера и праздник, имена вер не повторяются,
   верующие ссылаются на существующие веры;
7. карта: мир, построенный по файлу .world, детерминирован так же, земли
   покрывают всю сушу без пересечений, поселения стоят в своих землях,
   а политическая карта для картогенератора собирается без изъянов;
8. народы и походы: доли народов в державе сходятся с её населением,
   титульный народ живёт в стране, заморские земли открыты до того, как
   в них поселились, а труды учёных не повторяются.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import chronicle, espionage, storage, warfare   # noqa: E402
from worldgen.engine import Settings, generate                # noqa: E402
from worldgen.models import ACTIVE, ONGOING as ONGOING_STATE                             # noqa: E402
from worldgen.races import BEASTFOLK, EVIL, RACES, get_race   # noqa: E402

RACE_IDS = {race.id for race in RACES}

SEEDS = ("Ясень-7", "Первый мир", "проверка", "1234")
FORGE_SEEDS = ("Своя земля",)
MAP_SEEDS = ("карта-1", "карта-2")
SAMPLE_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "maps", "aurora-7.world")


def check_lives(world, seed: str) -> list:
    """Жизненные пути: цель имеет причину, а человек не действует мёртвым.

    Проверяется то, что перечислено в задании: цели могут кончаться и
    проваливаться, никто не добивается всего, события не случаются до
    рождения и после смерти, великих не слишком много и биографии не
    повторяются слово в слово.
    """
    from worldgen import lifepaths as cat

    problems = []
    seen_ids = set()
    for path in world.lifepaths.values():
        figure = world.figures.get(path.figure_id)
        if figure is None:
            problems.append("сид «%s»: путь %s ведёт человека, которого нет"
                            % (seed, path.id))
            continue
        if path.figure_id in seen_ids:
            problems.append("сид «%s»: у %s два жизненных пути"
                            % (seed, figure.plain_name))
        seen_ids.add(path.figure_id)
        if not path.wish:
            problems.append("сид «%s»: у %s путь без цели"
                            % (seed, figure.plain_name))
        if path.state not in cat.STATES:
            problems.append("сид «%s»: у %s неведомое состояние цели «%s»"
                            % (seed, figure.plain_name, path.state))
        if path.fame not in cat.FAME_LADDER:
            problems.append("сид «%s»: у %s неведомая ступень известности"
                            % (seed, figure.plain_name))
        birth = figure.birth.year if figure.birth else 0
        death = figure.death.year if figure.death else 10 ** 9
        for item in path.steps:
            year = int(item.get("год", 0))
            if year < birth:
                problems.append("сид «%s»: в жизни %s есть год до рождения"
                                % (seed, figure.plain_name))
                break
            if year > death:
                problems.append("сид «%s»: %s действует после смерти"
                                % (seed, figure.plain_name))
                break
        for item in path.legacy:
            if int(item.get("год", 0)) < death:
                problems.append("сид «%s»: наследие %s началось раньше его "
                                "смерти" % (seed, figure.plain_name))
                break
        if path.ended_year and path.ended_year < birth:
            problems.append("сид «%s»: путь %s кончился до рождения"
                            % (seed, figure.plain_name))

    total = len(world.lifepaths)
    if total:
        done = sum(1 for path in world.lifepaths.values()
                   if path.state in cat.GOOD_ENDS)
        if done == total:
            problems.append("сид «%s»: все до единого добились своего — "
                            "так не бывает" % seed)
        great = sum(1 for path in world.lifepaths.values()
                    if path.fame == cat.GREAT)
        if great > total * 0.35:
            problems.append("сид «%s»: великих людей %d из %d — слишком "
                            "много" % (seed, great, total))
        wishes = [path.wish for path in world.lifepaths.values()]
        if total >= 12 and len(set(wishes)) < 3:
            problems.append("сид «%s»: все жизни об одном и том же" % seed)
        # Биографии не должны совпадать слово в слово.
        prints = set()
        for path in world.lifepaths.values():
            mark = tuple(item["строка"] for item in path.steps)
            if len(mark) >= 6 and mark in prints:
                problems.append("сид «%s»: две жизни написаны одинаково"
                                % seed)
                break
            prints.add(mark)
    return problems


def check_tales(world, seed: str) -> list:
    """Сказания: дружина настоящая, дорога по своим землям, след честный."""
    problems = []
    for tale in world.tales.values():
        if not tale.name:
            problems.append("сид «%s»: у сказания %s нет имени"
                            % (seed, tale.id))
        if not tale.outcome:
            problems.append("сид «%s»: сказание «%s» без исхода"
                            % (seed, tale.name))
        if tale.ended is not None and tale.ended.ordinal < tale.began.ordinal:
            problems.append("сид «%s»: сказание «%s» кончилось раньше, чем "
                            "началось" % (seed, tale.name))
        if len(tale.company) < 2:
            problems.append("сид «%s»: в сказании «%s» некому идти"
                            % (seed, tale.name))
        seen = set()
        for item in tale.company:
            figure = world.figures.get(item.get("кто", ""))
            if figure is None:
                problems.append("сид «%s»: в сказании «%s» идёт тот, кого "
                                "нет" % (seed, tale.name))
                continue
            if figure.id in seen:
                problems.append("сид «%s»: в сказании «%s» человек идёт "
                                "дважды" % (seed, tale.name))
            seen.add(figure.id)
            if figure.birth is not None \
                    and figure.birth.year > tale.began.year:
                problems.append("сид «%s»: в сказании «%s» идёт тот, кто ещё "
                                "не родился" % (seed, tale.name))
            if item.get("судьба") in ("пал в пути", "пал у цели",
                                      "пропал без вести"):
                if figure.death is None:
                    problems.append("сид «%s»: в сказании «%s» павший остался "
                                    "жив" % (seed, tale.name))
                elif figure.death.year < tale.began.year:
                    problems.append("сид «%s»: в сказании «%s» павший умер "
                                    "до похода" % (seed, tale.name))
        if tale.region_id and tale.region_id not in world.regions:
            problems.append("сид «%s»: сказание «%s» идёт в землю, которой "
                            "нет" % (seed, tale.name))
        for leg in tale.road:
            if leg.get("земля") and leg["земля"] not in world.regions:
                problems.append("сид «%s»: дорога сказания «%s» ведёт через "
                                "землю, которой нет" % (seed, tale.name))
                break
        if tale.legend_id and tale.legend_id not in world.legends:
            problems.append("сид «%s»: у сказания «%s» песня без записи"
                            % (seed, tale.name))
        if tale.site_id and tale.site_id not in world.sites:
            problems.append("сид «%s»: сказание «%s» помнит место, которого "
                            "нет" % (seed, tale.name))
        if tale.prize_id and tale.prize_id not in world.artifacts:
            problems.append("сид «%s»: сказание «%s» шло за вещью, которой "
                            "нет" % (seed, tale.name))
    names = [tale.name for tale in world.tales.values()]
    if len(set(names)) != len(names):
        problems.append("сид «%s»: имена сказаний повторяются" % seed)
    return problems


def check_stories(world, seed: str) -> list:
    """Были: история найдена, а не выдумана.

    Проверяется то, на чём держится весь раздел: участники живы и
    настоящие, место существует, корень лежит раньше самой были, поворот
    подготовлен подсказкой, последствия не больше размаха истории — и
    девять из десяти былей не спасают мир. Последнее — не вкусовщина: без
    этого правила мир превращается в череду древних зол.
    """
    from worldgen import localstory as cat

    problems = []
    sizes, shapes = {}, {}
    for story in world.stories.values():
        where = "быль «%s»" % (story.title or story.id)
        if not story.title:
            problems.append("сид «%s»: у были %s нет имени" % (seed, story.id))
        if not story.outcome:
            problems.append("сид «%s»: %s без исхода" % (seed, where))
        if story.ended is not None and story.ended.ordinal < story.began.ordinal:
            problems.append("сид «%s»: %s кончилась раньше, чем началась"
                            % (seed, where))
        sizes[story.epicity] = sizes.get(story.epicity, 0) + 1
        shapes[story.shape] = shapes.get(story.shape, 0) + 1
        if story.shape not in cat.SHAPES_BY_KEY:
            problems.append("сид «%s»: у %s костяк, которого нет в каталоге"
                            % (seed, where))
        if story.node not in cat.NODES:
            problems.append("сид «%s»: %s выросла из узла, которого нет"
                            % (seed, where))

        # Люди: настоящие, живые и по одному разу.
        if len(story.cast) < 2:
            problems.append("сид «%s»: в %s некому участвовать" % (seed, where))
        seen = set()
        for item in story.cast:
            figure = world.figures.get(item.get("кто", ""))
            if figure is None:
                problems.append("сид «%s»: в %s замешан тот, кого нет"
                                % (seed, where))
                continue
            if figure.id in seen:
                problems.append("сид «%s»: в %s человек участвует дважды"
                                % (seed, where))
            seen.add(figure.id)
            if figure.birth is not None \
                    and figure.birth.year > story.began.year:
                problems.append("сид «%s»: в %s участвует тот, кто ещё не "
                                "родился" % (seed, where))
            if figure.death is not None \
                    and figure.death.year < story.began.year:
                problems.append("сид «%s»: в %s участвует тот, кто уже умер"
                                % (seed, where))

        # Место: оно должно быть в мире.
        if story.region_id and story.region_id not in world.regions:
            problems.append("сид «%s»: %s случилась в земле, которой нет"
                            % (seed, where))
        if story.settlement_id and story.settlement_id not in world.settlements:
            problems.append("сид «%s»: %s случилась в городе, которого нет"
                            % (seed, where))
        if story.site_id and story.site_id not in world.sites:
            problems.append("сид «%s»: %s помнит место, которого нет"
                            % (seed, where))
        if story.legend_id and story.legend_id not in world.legends:
            problems.append("сид «%s»: у %s предание без записи"
                            % (seed, where))

        # Корень: он лежит в прошлом, иначе быль выросла из будущего.
        for anchor in story.anchors:
            if int(anchor.get("год", 0)) > story.began.year:
                problems.append("сид «%s»: корень %s лежит позже самой были"
                                % (seed, where))
                break

        # Поворот: только подготовленный.
        if story.twist and not story.twist_seeded:
            problems.append("сид «%s»: в %s поворот не подготовлен подсказкой"
                            % (seed, where))

        # Акты: после корня время идёт только вперёд.
        last = None
        for act in story.acts:
            if act.get("вид") == "якорь":
                continue
            year = int(act.get("год", 0))
            if year < story.began.year:
                problems.append("сид «%s»: в %s действие идёт раньше начала"
                                % (seed, where))
                break
            if story.ended is not None and year > story.ended.year:
                problems.append("сид «%s»: в %s действие идёт после конца"
                                % (seed, where))
                break
            if last is not None and year < last:
                problems.append("сид «%s»: в %s годы идут вспять"
                                % (seed, where))
                break
            last = year

        # Последствия не больше размаха: бытовое дело не переворачивает
        # державу.
        if story.epicity <= 1:
            wide = [item.get("уровень") for item in story.consequences
                    if item.get("уровень") in (cat.POLITY, cat.HISTORIC)]
            if wide:
                problems.append("сид «%s»: у %s последствия больше её размаха"
                                % (seed, where))

        # Громкая быль обязана попасть в летопись, тихая — не обязана.
        if story.epicity >= 1 and not story.event_ids:
            problems.append("сид «%s»: %s не попала в летопись, хотя вышла за "
                            "пределы двора" % (seed, where))

    names = [story.title for story in world.stories.values()]
    if len(set(names)) != len(names):
        problems.append("сид «%s»: имена былей повторяются" % seed)

    total = len(world.stories)
    if total >= 30:
        small = sum(count for size, count in sizes.items() if size <= 2)
        if small < 0.7 * total:
            problems.append("сид «%s»: слишком много былей о судьбе мира: "
                            "%d из %d не про неё" % (seed, small, total))
        worst = max(shapes.values())
        if worst > 0.3 * total:
            key = [k for k, v in shapes.items() if v == worst][0]
            problems.append("сид «%s»: костяк «%s» занял %d былей из %d"
                            % (seed, key, worst, total))
    return problems


def check_renown(world, seed: str) -> list:
    """Вес имён: собран из настоящих следов и не спорит с жизнью.

    Проверяется главное: вес не назначен по титулу, а собран из того,
    что человек оставил; ступень лежит в своих пределах и не спорит с
    пиком; пересмотры идут после смерти, а не до; слава и память —
    разные числа; и мир не взвешивает всех подряд.
    """
    from worldgen import renown as cat

    problems = []
    for weight in world.renowns.values():
        figure = world.figures.get(weight.figure_id)
        if figure is None:
            problems.append("сид «%s»: вес без человека (%s)"
                            % (seed, weight.id))
            continue
        where = "человек по имени %s" % figure.plain_name
        if not 0 <= weight.level <= 10:
            problems.append("сид «%s»: у %s ступень вне десяти"
                            % (seed, where))
        if weight.peak_level < weight.level:
            problems.append("сид «%s»: у %s пик ниже нынешнего"
                            % (seed, where))
        if not 0 <= weight.fame <= 100 or not 0 <= weight.memory <= 100:
            problems.append("сид «%s»: у %s слава или память вне ста"
                            % (seed, where))
        if not 0.0 <= weight.unique <= 1.0:
            problems.append("сид «%s»: у %s незаменимость вне меры"
                            % (seed, where))
        if weight.died_year and figure.death is not None \
                and weight.died_year != figure.death.year:
            problems.append("сид «%s»: у %s год смерти не сходится с жизнью"
                            % (seed, where))
        if figure.birth is not None and weight.born_year \
                and weight.born_year != figure.birth.year:
            problems.append("сид «%s»: у %s год рождения не сходится"
                            % (seed, where))
        for name in (weight.influence or {}):
            if name not in cat.INFLUENCES:
                problems.append("сид «%s»: у %s влияние, которого нет"
                                % (seed, where))
                break
        for name, value in (weight.influence or {}).items():
            if not 0 <= int(value) <= 100:
                problems.append("сид «%s»: у %s влияние вне ста"
                                % (seed, where))
                break
        for role in weight.roles:
            if role not in cat.ROLES:
                problems.append("сид «%s»: у %s роль не из списка"
                                % (seed, where))
                break
        if weight.destiny and weight.destiny not in cat.DESTINIES_BY_KEY:
            problems.append("сид «%s»: у %s судьба не из списка"
                            % (seed, where))
        if weight.aura and weight.aura not in cat.AURAS_BY_KEY:
            problems.append("сид «%s»: у %s аура не из списка" % (seed, where))
        for item in weight.footprint:
            if item.get("вид") not in cat.FOOTPRINTS:
                problems.append("сид «%s»: у %s след не из списка"
                                % (seed, where))
                break
        for voice in (weight.voices or {}):
            if voice not in cat.VOICES:
                problems.append("сид «%s»: у %s голос не из списка"
                                % (seed, where))
                break
        last = 0
        for item in weight.reviews:
            year = int(item.get("год", 0))
            if weight.died_year and year < weight.died_year:
                problems.append("сид «%s»: %s пересмотрен раньше смерти"
                                % (seed, where))
                break
            if year > world.total_years:
                problems.append("сид «%s»: %s пересмотрен после конца мира"
                                % (seed, where))
                break
            if year < last:
                problems.append("сид «%s»: у %s пересмотры идут вспять"
                                % (seed, where))
                break
            last = year

    rows = list(world.renowns.values())
    if len(rows) >= 40:
        # Вес должен браться из дел: если у всех одна ступень, значит,
        # его всё-таки назначили, а не сосчитали.
        levels = {item.level for item in rows}
        if len(levels) < 3:
            problems.append("сид «%s»: у всех имён одна цена (%d ступени)"
                            % (seed, len(levels)))
        top = [item for item in rows if item.level >= 8]
        if len(top) > max(6, len(rows) // 12):
            problems.append("сид «%s»: слишком много имён мирового веса: %d"
                            % (seed, len(top)))
        moved = sum(1 for item in rows
                    for row in item.reviews
                    if row.get("стало") != row.get("было"))
        if not moved:
            problems.append("сид «%s»: ни одно имя не переменилось в цене"
                            % seed)
    return problems


def check_gods(world, seed: str) -> list:
    """Боги: биография не спорит ни с миром, ни сама с собой.

    Проверяется то, ради чего всё затевалось: у бога есть принцип и мера
    чужих дел, покровительство лежит в своих пределах и всегда с
    причиной, запреты и дары настоящие, отношения указывают на
    существующих богов, пророчества помнят свою правду, а следы
    первородных лежат в землях, которые в мире есть.
    """
    from worldgen import divinity as cat

    problems = []
    for head in world.godheads.values():
        deity = world.deities.get(head.deity_id)
        if deity is None:
            problems.append("сид «%s»: биография без бога (%s)"
                            % (seed, head.id))
            continue
        where = "бог по имени %s" % deity.given_name
        if head.origin not in cat.ORIGINS_BY_KEY:
            problems.append("сид «%s»: у %s происхождение не из списка"
                            % (seed, where))
        if not head.principle:
            problems.append("сид «%s»: у %s нет главной мысли"
                            % (seed, where))
        for name, value in (head.values or {}).items():
            if name not in cat.VALUES:
                problems.append("сид «%s»: у %s мера, которой нет" % (seed, where))
                break
            if not -3 <= int(value) <= 3:
                problems.append("сид «%s»: у %s мера вышла за предел"
                                % (seed, where))
                break

        for race_id, row in (head.favour or {}).items():
            value = float(row.get("сила", 0.0))
            if not -1.0 <= value <= 1.0:
                problems.append("сид «%s»: у %s покровительство вышло за меру"
                                % (seed, where))
                break
            if not row.get("почему"):
                problems.append("сид «%s»: у %s покровительство без причины"
                                % (seed, where))
                break
            year = int(row.get("год", 0))
            if year > world.total_years:
                problems.append("сид «%s»: у %s покровительство изменилось "
                                "после конца мира" % (seed, where))
                break

        for item in head.bonds:
            if item.get("связь") not in cat.BONDS:
                problems.append("сид «%s»: у %s связь с богом не из списка"
                                % (seed, where))
                break
            if item.get("кто") and item["кто"] not in world.deities:
                problems.append("сид «%s»: у %s связь с богом, которого нет"
                                % (seed, where))
                break

        for item in head.prophecies:
            if not item.get("слова") or not item.get("правда"):
                problems.append("сид «%s»: у %s пророчество без смысла"
                                % (seed, where))
                break
            if int(item.get("сбылось", 0)) and \
                    int(item["сбылось"]) < int(item.get("год", 0)):
                problems.append("сид «%s»: у %s пророчество поняли раньше, "
                                "чем сказали" % (seed, where))
                break

        for item in head.chosen:
            if item.get("кто") and item["кто"] not in world.figures:
                problems.append("сид «%s»: у %s избранник, которого нет"
                                % (seed, where))
                break
            if item.get("конец") and int(item["конец"]) < int(item.get("год", 0)):
                problems.append("сид «%s»: у %s избранник кончил раньше, чем "
                                "начал" % (seed, where))
                break

        if not 0.0 <= float(head.drift) <= 1.0:
            problems.append("сид «%s»: у %s расхождение с культом вне меры"
                            % (seed, where))
        for mark in head.marks:
            if int(mark.get("год", 0)) > world.total_years:
                problems.append("сид «%s»: у %s веха позже конца мира"
                                % (seed, where))
                break
        if head.gone_year and head.back_year \
                and head.back_year < head.gone_year:
            problems.append("сид «%s»: %s вернулся раньше, чем ушёл"
                            % (seed, where))

    # Мифический век: следы должны лежать в настоящих землях.
    for myth in world.myths:
        if not myth.get(cat.AS_IT_WAS):
            problems.append("сид «%s»: у мифа нет того, как было" % seed)
        for trace in myth.get("следы", ()):
            if trace.get("земля") and trace["земля"] not in world.regions:
                problems.append("сид «%s»: след первородных лежит в земле, "
                                "которой нет" % seed)
                break
            if trace.get("место") and trace["место"] not in world.sites:
                problems.append("сид «%s»: след первородных указывает на "
                                "место, которого нет" % seed)
                break
        for deity_id in myth.get("кто", ()):
            if deity_id not in world.deities:
                problems.append("сид «%s»: в мифе назван бог, которого нет"
                                % seed)
                break

    heads = list(world.godheads.values())
    if len(heads) >= 10:
        # Мир, где все боги об одном, читается как один бог с разными
        # именами. Проверяем, что это не так.
        ideas = {head.principle for head in heads}
        if len(ideas) < 4:
            problems.append("сид «%s»: боги все об одном (%d разных мысли)"
                            % (seed, len(ideas)))
    return problems


def check_land(world, seed: str) -> list:
    """Страница места: собирается ли она и не врёт ли.

    Тут ловится то, что ломается тихо. Страница, которая падает на пустом
    гексе или на открытой воде, — а таких гексов в мире девять из десяти.
    Летопись места не по порядку или с годом за концом истории. Одна и та
    же строка дважды. Город, показанный в год, когда его ещё не
    основали. Признак места не в том роде — «Новый Усыпальница»: такое
    имя разъезжается с русским языком, а ловится только счётом. И
    латиница в русском выводе: один забытый английский корень в
    пояснении — и текст выдаёт машину.
    """
    from worldgen import landlore
    from worldgen.names import PLACE_MARKS, _place_gender, _in_gender

    problems = []
    total = world.total_years
    link = getattr(world, "map_link", None)
    wmap = getattr(link, "wmap", None) if link is not None else None

    # --- признак места согласован с головным словом ---------------------
    # Проверяется на всём мире, а не на странице: имена-то в реестрах.
    for table in (world.sites, world.settlements):
        for item in table.values():
            first = (item.name or "").split(" ")[0]
            for forms in PLACE_MARKS:
                if first not in forms:
                    continue
                rest = item.name[len(first):].strip()
                gender = _place_gender(rest)
                if not gender:
                    break       # рода не знаем — и придираться не к чему
                want = _in_gender(forms, gender)
                if first != want:
                    problems.append(
                        "сид «%s»: имя места «%s» не согласовано — должно "
                        "быть «%s %s»" % (seed, item.name, want, rest))
                break
        if problems:
            break

    if wmap is None:
        # Мир без карты: страница обязана сказать это, а не упасть.
        said = landlore.chapter(world, 0)
        if not said or "без карты" not in " ".join(said):
            problems.append("сид «%s»: мир без карты, а страница места о "
                            "этом молчит" % seed)
        if landlore.best_hex(world) != -1 or landlore.notable(world):
            problems.append("сид «%s»: мир без карты, а места в нём "
                            "нашлись" % seed)
        return problems

    size = wmap.width * wmap.height
    busy = landlore.best_hex(world)
    if not 0 <= busy < size:
        problems.append("сид «%s»: самое весомое место — гекс %d, а гексов "
                        "всего %d" % (seed, busy, size))
        return problems
    for index, said in landlore.notable(world):
        if not 0 <= index < size:
            problems.append("сид «%s»: в списке мест гекс %d, а гексов "
                            "всего %d" % (seed, index, size))
            break
        if not said.strip():
            problems.append("сид «%s»: место на гексе %d без подписи"
                            % (seed, index))
            break

    # Пустая суша и открытая вода: страница должна собираться и на них.
    taken = {item.hex_index for item in world.settlements.values()}
    taken |= {getattr(item, "hex_index", -1) for item in world.sites.values()}
    empty = next((i for i in range(size)
                  if wmap.is_land(i) and i not in taken), -1)
    water = next((i for i in range(size) if wmap.is_ocean(i)), -1)
    look = [index for index in (busy, empty, water, 0, size - 1) if index >= 0]

    # Римское число в имени государя — это по-русски: «Пётр I»,
    # «Людовик XIV». Поэтому латиница ищется не по буквам, а по словам:
    # слово из одних только IVXLCDM — число, всё прочее — чужой язык.
    roman = set("IVXLCDM")

    def alien(text: str) -> str:
        for word in re.findall("[A-Za-z]+", text):
            if not set(word) <= roman:
                return word
        return ""
    for index in look:
        try:
            page = landlore.blocks(world, index, total)
        except Exception as error:
            problems.append("сид «%s»: страница гекса %d не собралась: %s"
                            % (seed, index, error))
            break
        tags = {tag for tag, _line in page}
        if not tags <= {"title", "head", "line", "dim", "dated"}:
            problems.append("сид «%s»: у страницы гекса %d метка не из "
                            "списка: %s" % (seed, index, sorted(tags)))
            break
        wrong = alien(" ".join(line for _tag, line in page))
        if wrong:
            problems.append("сид «%s»: в странице гекса %d чужое слово: "
                            "«%s»" % (seed, index, wrong))
            break

        # Летопись места: по порядку, в пределах истории, без повторов.
        told = landlore.timeline(world, index)
        seen = set()
        last = 0
        for year, _kind, line in told:
            if year < last:
                problems.append("сид «%s»: летопись гекса %d идёт не по "
                                "порядку: %d после %d"
                                % (seed, index, year, last))
                break
            last = year
            if not 1 <= year <= total:
                problems.append("сид «%s»: в летописи гекса %d год %d, а "
                                "история идёт до %d"
                                % (seed, index, year, total))
                break
            if (year, line) in seen:
                problems.append("сид «%s»: в летописи гекса %d одно и то же "
                                "дважды: %d, «%s»" % (seed, index, year, line))
                break
            seen.add((year, line))
        if problems:
            break

        # Вес: пустое место весит ноль и так и названо.
        score, verdict, why = landlore.weight(world, index)
        if score < 0:
            problems.append("сид «%s»: вес гекса %d отрицателен (%.1f)"
                            % (seed, index, score))
            break
        if score == 0 and why:
            problems.append("сид «%s»: гекс %d весит ноль, а причины веса "
                            "названы: %s" % (seed, index, why[0]))
            break
        if not verdict:
            problems.append("сид «%s»: у гекса %d нет приговора о весе"
                            % (seed, index))
            break

    # Год на странице соблюдается: в первый год не стоит то, чего ещё нет.
    if not problems:
        young = [item for item in world.settlements.values()
                 if item.hex_index >= 0 and item.founded is not None
                 and item.founded.year > 1]
        if young:
            item = min(young, key=lambda row: (len(row.id), row.id))
            said = " ".join(landlore.standing(world, item.hex_index, 1))
            if item.name in said:
                problems.append("сид «%s»: на первый год на гексе %d уже "
                                "стоит %s, а основан он в %d году"
                                % (seed, item.hex_index, item.full_name,
                                   item.founded.year))
    return problems


def check_origin(world, seed: str) -> list:
    """Начало мира: сходится ли оно само с собой и с миром.

    Тут ловится то, что ломается тихо и портит самую первую страницу.
    Слой, положенный дважды или не положенный, но и не записанный в
    отсутствующие. Черёд с дырой или с двумя одинаковыми номерами. Закон
    с ключом, которого нет в каталоге, — такой закон в тексте встанет
    пустой строкой. Шрам в земле, которой нет в мире, или в месте,
    которого не создавали. Мотив, не подходящий укладу: мир-тюрьму не
    строят там, где творца не было вовсе. Версия народа, которого в
    мире не было. И противоречие без второй стороны — то есть не
    противоречие.
    """
    from worldgen import origin as cat
    from worldgen import narrative_origin as texts

    problems = []
    origin = world.origin
    if origin is None:
        # Мир без начала — это законно: он мог просто быть. Но тогда и
        # ссылок на начало нигде быть не должно.
        if world.notes.get("начало мира"):
            problems.append("сид «%s»: начала мира нет, а запись о нём есть"
                            % seed)
        return problems

    motif = cat.MOTIFS.get(origin.motif)
    if motif is None:
        problems.append("сид «%s»: у начала мира неведомый мотив «%s»"
                        % (seed, origin.motif))
        return problems
    if motif.needs and origin.model not in motif.needs:
        problems.append("сид «%s»: мотив «%s» не идёт укладу «%s»"
                        % (seed, motif.name, origin.model))
        return problems
    if origin.certainty not in cat.CERTAINTY:
        problems.append("сид «%s»: у начала мира неведомая достоверность "
                        "«%s»" % (seed, origin.certainty))
        return problems
    if not 0.0 < origin.known <= 1.0:
        problems.append("сид «%s»: у начала мира доля известного %s"
                        % (seed, origin.known))
        return problems

    # --- слои ----------------------------------------------------------
    laid = [row.get("слой") for row in origin.layers]
    if len(laid) != len(set(laid)):
        problems.append("сид «%s»: слой мира положен дважды" % seed)
        return problems
    for key in laid:
        if key not in cat.LAYERS:
            problems.append("сид «%s»: в мире положен неведомый слой «%s»"
                            % (seed, key))
            return problems
    for key in origin.missing:
        if key not in cat.LAYERS:
            problems.append("сид «%s»: в мире не хватает неведомого слоя "
                            "«%s»" % (seed, key))
            return problems
        if key in laid:
            problems.append("сид «%s»: слой «%s» и положен, и не положен"
                            % (seed, key))
            return problems
    for key in cat.MUST:
        if key not in laid:
            problems.append("сид «%s»: в мире нет слоя «%s», без которого "
                            "мира не бывает" % (seed, key))
            return problems
    missed = set(cat.LAYERS) - set(laid) - set(origin.missing)
    if missed:
        problems.append("сид «%s»: о слое «%s» не сказано ни что он есть, "
                        "ни что его нет" % (seed, sorted(missed)[0]))
        return problems
    order = sorted(int(row.get("черёд", 0)) for row in origin.layers)
    if order != list(range(1, len(order) + 1)):
        problems.append("сид «%s»: черёд слоёв мира идёт с дырой или с "
                        "повтором" % seed)
        return problems
    # Пространство кладут первым всегда: материи, положенной прежде
    # места, негде лежать.
    first = origin.order[0]["слой"] if origin.order else ""
    if first != cat.SPACE:
        problems.append("сид «%s»: первым слоем мира положено «%s», а не "
                        "пространство" % (seed, first))
        return problems

    # --- законы --------------------------------------------------------
    keys = [row.get("ключ") for row in origin.laws]
    if len(keys) != len(set(keys)):
        problems.append("сид «%s»: один закон мира назван дважды" % seed)
        return problems
    for row in origin.laws:
        law = cat.LAWS.get(row.get("ключ"))
        if law is None:
            problems.append("сид «%s»: у мира закон с неведомым ключом «%s»"
                            % (seed, row.get("ключ")))
            return problems
        if row.get("закон") != law.text:
            problems.append("сид «%s»: закон «%s» записан не тем словом, "
                            "что в каталоге" % (seed, law.key))
            return problems
    if not any(row.get("известен") for row in origin.laws) \
            and origin.known > 0.5:
        problems.append("сид «%s»: мир знает о себе много, а ни одного "
                        "закона назвать не может" % seed)
        return problems

    # --- спор ----------------------------------------------------------
    if origin.quarrel:
        if origin.quarrel not in laid:
            problems.append("сид «%s»: спорили о слое «%s», которого в мире "
                            "не положили" % (seed, origin.quarrel))
            return problems
        for field in ("winner_id", "loser_id"):
            value = getattr(origin, field, "")
            if value and value not in world.deities:
                problems.append("сид «%s»: в первом споре участвовал тот, "
                                "кого в мире нет" % seed)
                return problems
    if origin.sealed and not origin.sealed_how:
        problems.append("сид «%s»: что-то заперто, а как — не сказано"
                        % seed)
        return problems

    # --- жизнь ---------------------------------------------------------
    if origin.life_way not in cat.LIFE_WAYS:
        problems.append("сид «%s»: жизнь завелась неведомым путём «%s»"
                        % (seed, origin.life_way))
        return problems
    way = cat.LIFE_WAYS[origin.life_way]
    for need in way.needs:
        if need in origin.missing:
            problems.append("сид «%s»: жизнь вышла из слоя «%s», которого "
                            "в мире нет" % (seed, need))
            return problems
    if origin.first_kind not in cat.FIRST_KINDS:
        problems.append("сид «%s»: первыми были неведомо кто «%s»"
                        % (seed, origin.first_kind))
        return problems
    if origin.split and not origin.one_root:
        problems.append("сид «%s»: народы разошлись, не имея общего корня"
                        % seed)
        return problems

    # --- шрамы ---------------------------------------------------------
    for row in origin.scars:
        if row.get("вид") not in cat.SCARS:
            problems.append("сид «%s»: шрам творения неведомого вида «%s»"
                            % (seed, row.get("вид")))
            return problems
        land = row.get("земля", "")
        if land and land not in world.regions:
            problems.append("сид «%s»: шрам творения лежит в земле, "
                            "которой нет" % seed)
            return problems
        place = row.get("место", "")
        if place and place not in world.sites:
            problems.append("сид «%s»: шрам творения привязан к месту, "
                            "которого не создавали" % seed)
            return problems

    # --- что об этом знают ---------------------------------------------
    for row in origin.versions:
        whose = row.get("чей", "")
        if whose and whose not in world.folks and whose not in world.faiths:
            problems.append("сид «%s»: о начале мира рассказывает тот, "
                            "кого в мире не было" % seed)
            return problems
        if not row.get("как"):
            problems.append("сид «%s»: у версии начала нет самой версии"
                            % seed)
            return problems
    for row in origin.clashes:
        if not row.get("кто") or not row.get("против"):
            problems.append("сид «%s»: у противоречия о начале нет второй "
                            "стороны" % seed)
            return problems
        if row.get("кто") == row.get("против"):
            problems.append("сид «%s»: источник о начале спорит сам с "
                            "собой" % seed)
            return problems
        # То, о чём спорят, должно уметь встать в падеж: иначе в тексте
        # выйдет «о время».
        about = row.get("о чём", "")
        if about and texts.about_prep(about) == about \
                and about in cat.LAYERS:
            problems.append("сид «%s»: о слое «%s» нельзя сказать «о ...» — "
                            "нет падежа" % (seed, about))
            return problems

    # --- событие о начале есть и стоит первым года --------------------
    marks = [event for event in world.events
             if event.kind in ("world_origin", "world_laws")]
    if not marks:
        problems.append("сид «%s»: начало мира есть, а записи о нём в "
                        "летописи нет" % seed)
        return problems
    for event in marks:
        if event.date.year != 1:
            problems.append("сид «%s»: запись о начале мира стоит в %d году"
                            % (seed, event.date.year))
            return problems
    return problems


def check_holidays(world, seed: str) -> list:
    """Праздники: день памяти не спорит ни с миром, ни с собой.

    Тут ловится то, что ломается тихо. Праздник, заведённый раньше
    события, которое он поминает. Поворот судьбы, случившийся до его
    рождения или после конца летописи. Забытый повод без года забвения —
    то есть забытый неизвестно когда. Имя, у которого головное слово не
    склоняется, — такое имя в тексте встанет в именительном посреди
    предложения. Запрет без причины: запрет без причины — это произвол
    движка, а не истории. Обряд без объяснения: каждый обряд обязан
    знать, отчего он такой, иначе вся система теряет смысл. И два
    праздника на одно и то же событие — мир не поминает одну войну
    дважды.
    """
    from worldgen import holidays as cat
    from worldgen import narrative_holiday as texts

    problems = []
    total = world.total_years
    seen_links = {}
    link_fields = ("war_id", "calamity_id", "invasion_id", "monster_id",
                   "figure_id", "deity_id", "guild_id", "trace_id",
                   "subject_id", "temple_id", "law_id", "settlement_id",
                   "polity_id")
    tables = {"war_id": world.wars, "calamity_id": world.calamities,
              "invasion_id": world.invasions, "monster_id": world.monsters,
              "figure_id": world.figures, "deity_id": world.deities,
              "guild_id": world.guilds, "trace_id": world.traces,
              "subject_id": world.subjects, "polity_id": world.polities,
              "settlement_id": world.settlements, "folk_id": world.folks,
              "faith_id": world.faiths, "house_id": world.houses,
              "temple_id": world.temples, "law_id": world.laws,
              "region_id": world.regions}

    for holiday in world.holidays.values():
        name = holiday.name or holiday.id
        origin = cat.ORIGINS.get(holiday.origin)
        if origin is None:
            problems.append("сид «%s»: праздник «%s» неведомого повода «%s»"
                            % (seed, name, holiday.origin))
            break
        if holiday.group != origin.group:
            problems.append("сид «%s»: у праздника «%s» группа не та, что в "
                            "каталоге" % (seed, name))
            break
        if holiday.step not in cat.STEPS:
            problems.append("сид «%s»: у праздника «%s» неведомая ступень "
                            "«%s»" % (seed, name, holiday.step))
            break
        if holiday.state not in cat.STATES:
            problems.append("сид «%s»: у праздника «%s» неведомое состояние "
                            "«%s»" % (seed, name, holiday.state))
            break
        if holiday.holder not in cat.HOLDERS:
            problems.append("сид «%s»: праздник «%s» держит неведомо кто "
                            "«%s»" % (seed, name, holiday.holder))
            break
        if holiday.reach not in cat.REACH:
            problems.append("сид «%s»: у праздника «%s» неведомый охват «%s»"
                            % (seed, name, holiday.reach))
            break
        if not holiday.first_meaning:
            problems.append("сид «%s»: у праздника «%s» не названо, отчего "
                            "он есть" % (seed, name))
            break

        # --- даты ------------------------------------------------------
        if holiday.born is None or not 1 <= holiday.born.year <= total:
            problems.append("сид «%s»: праздник «%s» заведён вне летописи"
                            % (seed, name))
            break
        if holiday.month and not 1 <= holiday.month <= 12:
            problems.append("сид «%s»: у праздника «%s» месяц %d"
                            % (seed, name, holiday.month))
            break
        if holiday.day and not 1 <= holiday.day <= 30:
            problems.append("сид «%s»: у праздника «%s» число %d"
                            % (seed, name, holiday.day))
            break
        if not holiday.month and holiday.rule not in cat.MOVING_RULES:
            problems.append("сид «%s»: у праздника «%s» нет числа, а счёт "
                            "твёрдый" % (seed, name))
            break
        if holiday.event_year and holiday.event_year > holiday.born.year:
            problems.append("сид «%s»: праздник «%s» заведён раньше того, "
                            "что поминает" % (seed, name))
            break
        for turn in holiday.turns:
            when = int(turn.get("год", 0))
            if not holiday.born.year <= when <= total:
                problems.append("сид «%s»: у праздника «%s» поворот «%s» в "
                                "%d году, а сам он с %d"
                                % (seed, name, turn.get("поворот", ""), when,
                                   holiday.born.year))
                break
            if turn.get("поворот") not in cat.TURNS:
                problems.append("сид «%s»: у праздника «%s» неведомый "
                                "поворот «%s»"
                                % (seed, name, turn.get("поворот", "")))
                break
        if problems:
            break

        # --- забытый повод ---------------------------------------------
        if holiday.lost_why:
            if not holiday.forgot_year:
                problems.append("сид «%s»: у праздника «%s» повод забыт, а "
                                "когда — не сказано" % (seed, name))
                break
            if not holiday.born.year <= holiday.forgot_year <= total:
                problems.append("сид «%s»: праздник «%s» забыл повод в %d "
                                "году" % (seed, name, holiday.forgot_year))
                break
            if not holiday.forgot_why:
                problems.append("сид «%s»: у праздника «%s» повод забыт без "
                                "причины" % (seed, name))
                break

        # --- имя склоняется --------------------------------------------
        # Послабление ровно одно: божественный день берёт себе готовое
        # имя праздника божества, а те имена лежат в `pantheon.py` и
        # бывают одним словом («Солнцеворот»). Но послабление именно на
        # это имя, а не на всякое имя дня, у которого есть бог: иначе
        # через ту же щель пройдёт и настоящая поломка.
        head = texts.head_of(holiday.name)
        if head not in texts.HEAD_FORMS:
            deity = world.deities.get(holiday.deity_id)
            feast = deity.festival_name if deity is not None else ""
            if holiday.name != feast:
                problems.append("сид «%s»: имя праздника «%s» не "
                                "склоняется — головное слово «%s» не в "
                                "таблице падежей" % (seed, name, head))
                break
        for row in holiday.names:
            if not row.get("имя") or not row.get("по"):
                problems.append("сид «%s»: у праздника «%s» прежнее имя без "
                                "имени или без года" % (seed, name))
                break
        if problems:
            break

        # --- запреты и обряды ------------------------------------------
        for ban in holiday.bans:
            if not ban.get("отчего"):
                problems.append("сид «%s»: праздник «%s» запретили без "
                                "причины" % (seed, name))
                break
            begun, over = int(ban.get("с", 0)), int(ban.get("по", 0))
            if over and over < begun:
                problems.append("сид «%s»: у праздника «%s» запрет снят "
                                "раньше, чем наложен" % (seed, name))
                break
        if problems:
            break
        for rite in holiday.rites:
            if rite.get("обряд") not in cat.RITES:
                problems.append("сид «%s»: у праздника «%s» неведомый обряд "
                                "«%s»" % (seed, name, rite.get("обряд", "")))
                break
            if not rite.get("зачем"):
                problems.append("сид «%s»: у праздника «%s» обряд «%s» без "
                                "объяснения" % (seed, name,
                                                rite.get("обряд", "")))
                break
            if int(rite.get("с", 0)) < holiday.born.year:
                problems.append("сид «%s»: у праздника «%s» обряд завёлся "
                                "раньше самого дня" % (seed, name))
                break
        if problems:
            break

        # --- привязки существуют ---------------------------------------
        bad = ""
        for field, table in tables.items():
            value = getattr(holiday, field, "")
            if value and value not in table:
                bad = field
                break
        if bad:
            problems.append("сид «%s»: праздник «%s» привязан к тому, чего в "
                            "мире нет (%s)" % (seed, name, bad))
            break

        # --- одно событие — один праздник ------------------------------
        # Сверяется только повод (`about`): остальные привязки — родня.
        # День находки знает и беду, от которой след остался, но поминает
        # он находку, а это другое событие. Событием считается пара
        # «привязка + повод»: венчание государя и его смерть — два разных
        # дня об одном человеке, и мир вправе держать оба.
        if holiday.about and holiday.about in link_fields:
            value = getattr(holiday, holiday.about, "")
            key = (holiday.about, value, holiday.origin)
            if value and key in seen_links:
                problems.append("сид «%s»: одно и то же поминают дважды — "
                                "«%s» и «%s»"
                                % (seed, seen_links[key], name))
                break
            if value:
                seen_links[key] = name

        # --- следы и ступень -------------------------------------------
        if holiday.marks and not cat.is_feast(holiday.step):
            problems.append("сид «%s»: «%s» ещё не праздник, а уже оставил "
                            "по себе постройку" % (seed, name))
            break
        for row in holiday.variants:
            if not row.get("кто") or not row.get("чем"):
                problems.append("сид «%s»: у праздника «%s» пустой чужой "
                                "вариант" % (seed, name))
                break
        if problems:
            break

    return problems


def check_towns(world, seed: str) -> list:
    """Города: биография не спорит сама с собой и с миром.

    Проверяется то, на чём она держится: город не заводит концов раньше
    себя, слои не ложатся из будущего, доли уклада сходятся, занятие
    возможно в этой земле, а оставленный город не продолжает жить.
    """
    from worldgen import township as cat
    from worldgen.models import ACTIVE

    problems = []
    for town in world.townships.values():
        settlement = world.settlements.get(town.settlement_id)
        where = "город по имени %s" % (settlement.name if settlement
                                       else town.settlement_id)
        if settlement is None:
            problems.append("сид «%s»: биография без города (%s)"
                            % (seed, town.id))
            continue
        if town.origin not in cat.ORIGINS_BY_KEY:
            problems.append("сид «%s»: у %s причина, которой нет в списке"
                            % (seed, where))
        born = town.born.year if town.born else settlement.founded.year

        for item in town.districts:
            if int(item.get("год", 0)) < born:
                problems.append("сид «%s»: у %s конец города старше самого "
                                "города" % (seed, where))
                break
            if item.get("конец") not in cat.DISTRICTS_BY_KEY:
                problems.append("сид «%s»: у %s конец города, которого нет "
                                "в списке" % (seed, where))
                break
        for item in town.layers:
            if int(item.get("год", 0)) > world.total_years:
                problems.append("сид «%s»: под %s лежит слой из будущего"
                                % (seed, where))
                break
        for item in town.marks:
            if int(item.get("год", 0)) > world.total_years:
                problems.append("сид «%s»: у %s веха позже конца мира"
                                % (seed, where))
                break
        for item in town.trades:
            if item.get("чем") not in cat.TRADES_BY_KEY:
                problems.append("сид «%s»: у %s занятие, которого нет в "
                                "списке" % (seed, where))
                break
            if item.get("по") and int(item["по"]) < int(item.get("с", 0)):
                problems.append("сид «%s»: у %s занятие кончилось раньше, "
                                "чем началось" % (seed, where))
                break
        for item in town.troubles:
            if item.get("тягота") not in cat.TROUBLES_BY_KEY:
                problems.append("сид «%s»: у %s тягота, которой нет в списке"
                                % (seed, where))
                break
            if item.get("по") and int(item["по"]) < int(item.get("с", 0)):
                problems.append("сид «%s»: у %s тягота кончилась раньше, "
                                "чем началась" % (seed, where))
                break
        for item in town.secrets:
            if item.get("уровень") not in cat.SECRET_LEVELS:
                problems.append("сид «%s»: у %s тайна без уровня"
                                % (seed, where))
                break
            if not item.get(cat.TRUTH):
                problems.append("сид «%s»: у %s тайна без правды"
                                % (seed, where))
                break

        # Доли уклада — это доли: они обязаны сходиться к единице.
        for name, rows in (town.mix or {}).items():
            if not rows:
                continue
            total = sum(rows.values())
            if abs(total - 1.0) > 0.03:
                problems.append("сид «%s»: у %s доли «%s» не сходятся (%.2f)"
                                % (seed, where, name, total))
                break

        for name, value in (town.temper or {}).items():
            if name not in cat.TEMPERS:
                problems.append("сид «%s»: у %s шкала нрава, которой нет"
                                % (seed, where))
                break
            if not 0.0 <= float(value) <= 1.0:
                problems.append("сид «%s»: у %s нрав вышел за меру"
                                % (seed, where))
                break

        # Оставленный город не растёт и не заводит новых дел.
        if settlement.status != ACTIVE and town.life != cat.EMPTY:
            problems.append("сид «%s»: %s оставлен, а биография его "
                            "продолжается" % (seed, where))
        if settlement.status != ACTIVE and settlement.ended is not None:
            late = [item for item in town.marks
                    if int(item.get("год", 0)) > settlement.ended.year]
            if late:
                problems.append("сид «%s»: у %s веха позже его конца"
                                % (seed, where))

    live = [town for town in world.townships.values()
            if world.settlements.get(town.settlement_id) is not None
            and world.settlements[town.settlement_id].status == ACTIVE]
    if len(live) >= 12:
        # Мир, где все города одинаковы, — это не мир, а список.
        trades = {town.trade for town in live}
        if len(trades) < 4:
            problems.append("сид «%s»: живые города кормятся одним и тем же "
                            "(%d занятия)" % (seed, len(trades)))
        origins = {town.origin for town in live}
        if len(origins) < 4:
            problems.append("сид «%s»: все города возникли по одной причине"
                            % seed)
    return problems


def check_souls(world, seed: str) -> list:
    """Людность мира: судьба записана, а числа не ушли в бессмыслицу."""
    problems = []
    fate = (world.notes or {}).get("судьба") or {}
    if not fate.get("имя"):
        problems.append("сид «%s»: у мира не записана судьба" % seed)
    souls = world.world_population()
    if souls <= 0:
        problems.append("сид «%s»: в мире не осталось ни души" % seed)
    if souls > 300000000:
        problems.append("сид «%s»: население мира ушло за всякий предел: %d"
                        % (seed, souls))
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.population > 4000000:
            problems.append("сид «%s»: в городе %s %d жителей — это уже не "
                            "город, а держава"
                            % (seed, settlement.name, settlement.population))
            break
    for region in world.regions.values():
        if region.capacity < 0:
            problems.append("сид «%s»: у земли %s ёмкость ушла в минус"
                            % (seed, region.name))
            break
    return problems


def check_tribes(world, seed: str) -> list:
    """Племя: живое ведёт живой вождь, и никто не старше своей расы.

    Племя стоит тысячи лет, а вождь смертен. Прежде вождь ставился раз
    при основании и числился живым до конца истории — в летописи выходили
    главари гоблинов по две тысячи лет от рождения.

    Предел века считается с оглядкой на особенности мира: в части миров
    высшим эльфам век не отмерен вовсе, и пятитысячелетний эльф там не
    поломка, а задуманное свойство, названное в «Итогах» вслух.
    """
    problems = []
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        chief = world.figures.get(tribe.chief_id)
        if chief is None:
            continue
        if not chief.alive_at(world.total_years):
            problems.append("сид «%s»: племя %s ведёт мёртвый вождь %s"
                            % (seed, tribe.full_name, chief.name))
            break
    # Раса, которой в этом мире век не отмерен, живёт дольше своего же
    # предела — на то и особенность. Предел для неё считается по тому, что
    # обещано в mortality.UNAGING_SPAN, иначе проверка ловит не ошибку, а
    # задуманное свойство мира.
    from worldgen import mortality
    gifts = getattr(world, "race_gifts", None) or {}
    stretch = mortality.UNAGING_SPAN[1]
    for figure in world.figures.values():
        race = get_race(figure.race_id)
        if race is None or figure.birth is None:
            continue
        end = (figure.death.year if figure.death is not None
               else world.total_years)
        limit = race.lifespan[1] * 2
        if gifts.get(figure.race_id) == mortality.UNAGING:
            limit = int(race.lifespan[1] * stretch)
        # Дар богов — это годы: благословлённому смерть отодвигают на долю
        # его остатка (religion.py), и для него предел законно выше. Это и
        # поймала проверка в первый свой прогон: высшая эльфийка прожила
        # 10 942 года при собственном пределе расы в 7200 — потому что была
        # благословлена. Теперь годы такому не прибавляются вовсе, но у
        # благословлённых прежних миров запас оставлен.
        if figure.divine_mark == "благословение":
            limit = int(limit * 2.2)
        if end - figure.birth.year > limit:
            problems.append("сид «%s»: %s (%s) прожил%s %d лет при пределе "
                            "расы %d"
                            % (seed, figure.name, race.name,
                               "а" if figure.sex == "f" else "",
                               end - figure.birth.year, limit))
            break
    return problems


def check_capitals(world, seed: str) -> list:
    """Престол державы: он должен быть живым городом этой самой державы."""
    problems = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if not polity.capital_id:
            if polity.settlement_ids:
                problems.append("сид «%s»: у державы %s есть города, но нет "
                                "престола" % (seed, polity.name))
                break
            continue
        capital = world.settlements.get(polity.capital_id)
        if capital is None:
            problems.append("сид «%s»: престол державы %s — несуществующий "
                            "город" % (seed, polity.name))
            break
        if capital.status != ACTIVE:
            problems.append("сид «%s»: престол державы %s стоит в руинах (%s)"
                            % (seed, polity.name, capital.name))
            break
        if capital.id not in polity.settlement_ids:
            problems.append("сид «%s»: престол державы %s ей не принадлежит "
                            "(%s)" % (seed, polity.name, capital.name))
            break
        if not capital.is_capital:
            problems.append("сид «%s»: город %s держит престол, но не знает "
                            "об этом" % (seed, capital.name))
            break
    return problems


def check_nations(world, seed: str) -> list:
    """Проверяет народы держав и походы в неизведанное."""
    problems = []

    for polity in world.polities.values():
        if polity.status != ACTIVE or not polity.peoples:
            continue
        total = sum(polity.peoples.values())
        if abs(total - polity.population) > max(50, polity.population * 0.02):
            problems.append("сид «%s»: у страны %s народов на %d душ, а "
                            "населения %d" % (seed, polity.name, total,
                                              polity.population))
            break
        if polity.race_id not in polity.peoples:
            problems.append("сид «%s»: титульный народ страны %s в ней не живёт"
                            % (seed, polity.name))
            break
        for value in polity.grievance.values():
            if not (0.0 <= value <= 1.0):
                problems.append("сид «%s»: обида в стране %s вышла за пределы"
                                % (seed, polity.name))
                break

    for expedition in world.expeditions.values():
        if expedition.end is not None and expedition.end.ordinal < expedition.start.ordinal:
            problems.append("сид «%s»: поход «%s» вернулся раньше, чем вышел"
                            % (seed, expedition.name))
            break
        if expedition.deaths > expedition.crew:
            problems.append("сид «%s»: в походе «%s» погибло больше, чем ушло"
                            % (seed, expedition.name))
            break
        for region_id in expedition.discovered:
            region = world.regions.get(region_id)
            if region is None or not region.known:
                problems.append("сид «%s»: поход «%s» открыл землю, которая "
                                "так и не стала ведомой" % (seed, expedition.name))
                break

    # Города не ставят в землях, о которых никто не знает.
    for settlement in world.settlements.values():
        region = world.regions.get(settlement.region_id)
        if region is not None and not region.known:
            problems.append("сид «%s»: город %s стоит в неведомой земле %s"
                            % (seed, settlement.name, region.name))
            break

    # Народы: имя своё, колыбель настоящая, раса совпадает с носителями.
    names = [folk.name for folk in world.folks.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена народов повторяются" % seed)
    for folk in world.folks.values():
        if folk.cradle_region and folk.cradle_region not in world.regions:
            problems.append("сид «%s»: у народа %s колыбель в несуществующей земле"
                            % (seed, folk.name))
            break
    for settlement in world.settlements.values():
        folk = world.folks.get(settlement.folk_id)
        if folk is not None and folk.race_id != settlement.race_id:
            problems.append("сид «%s»: город %s приписан народу чужой расы"
                            % (seed, settlement.name))
            break

    # Торговые пути: настоящие, связные и не через пики.
    link = getattr(world, "map_link", None)
    if link is not None:
        wmap = link.wmap
        for route in world.routes.values():
            if not route.path:
                continue
            broken = False
            for first, second in zip(route.path, route.path[1:]):
                if second not in wmap.neighbors(first):
                    broken = True
                    break
            if broken:
                problems.append("сид «%s»: торговый путь %s рвётся"
                                % (seed, route.id))
                break
            wrong = any(wmap.is_ocean(index) for index in route.path) \
                if not route.by_sea else \
                any(wmap.is_land(index) for index in route.path[1:-1])
            if wrong:
                problems.append("сид «%s»: путь %s идёт не своей стихией"
                                % (seed, route.id))
                break

    # Один труд — один раз за всю историю мира.
    works = [note for figure in world.figures.values() for note in figure.notes
             if note.startswith("труд: ")]
    if len(works) != len(set(works)):
        problems.append("сид «%s»: труды учёных повторяются" % seed)
    return problems


def check_map_world(world, wmap, seed: str) -> list:
    """Проверяет мир, построенный по карте.

    Карту надо передать ту самую, на которой мир и строился: своя карта
    Worldforge и карта из файла — это разные земли, и сверять мир с
    чужой картой значит искать города в чужом море.
    """
    from worldgen import worldmap as wm

    problems = []
    if wmap is None:
        wmap = wm.load(SAMPLE_MAP)

    seen = {}
    for region in world.regions.values():
        if not region.hexes:
            problems.append("сид «%s»: земля %s без гексов" % (seed, region.name))
            continue
        for index in region.hexes:
            if index in seen:
                problems.append("сид «%s»: гекс %d поделили %s и %s"
                                % (seed, index, seen[index], region.name))
                break
            seen[index] = region.name
    land = sum(1 for i in range(wmap.size) if wmap.is_land(i))
    if len(seen) != land:
        problems.append("сид «%s»: земли покрывают %d гексов суши из %d"
                        % (seed, len(seen), land))

    for settlement in world.settlements.values():
        index = settlement.hex_index
        if index < 0:
            continue
        if not wmap.is_land(index):
            problems.append("сид «%s»: город %s стоит в воде"
                            % (seed, settlement.name))
            break
        region = world.regions.get(settlement.region_id)
        if region is not None and region.hexes and index not in region.hexes:
            problems.append("сид «%s»: город %s стоит вне своей земли %s"
                            % (seed, settlement.name, region.name))
            break

    for camp in world.camps.values():
        if camp.hex_index >= 0 and not wmap.is_land(camp.hex_index):
            problems.append("сид «%s»: лагерь %s стоит в воде" % (seed, camp.name))
            break

    recorder = world.map_recorder
    if recorder is None:
        problems.append("сид «%s»: политическая карта не записана" % seed)
        return problems

    section = recorder.build()
    if section["w"] != wmap.width or section["h"] != wmap.height:
        problems.append("сид «%s»: размер политической карты не совпал с картой" % seed)
    if not section["frames"]:
        problems.append("сид «%s»: в политической карте нет ни одного кадра" % seed)
    for frame in section["frames"]:
        total = sum(frame["rle"][i] for i in range(1, len(frame["rle"]), 2))
        if total != wmap.size:
            problems.append("сид «%s»: кадр %d развернулся в %d гексов вместо %d"
                            % (seed, frame["y"], total, wmap.size))
            break
    years = [frame["y"] for frame in section["frames"]]
    if years != sorted(years):
        problems.append("сид «%s»: кадры политической карты идут не по годам" % seed)
    slots = len(section["realmColors"])
    for frame in section["frames"]:
        worst = max((frame["rle"][i] for i in range(0, len(frame["rle"]), 2)),
                    default=-1)
        if worst >= slots:
            problems.append("сид «%s»: в кадре %d держава %d без цвета"
                            % (seed, frame["y"], worst))
            break
    return problems


def digest(world) -> str:
    return hashlib.sha256(chronicle.full_text(world).encode("utf-8")).hexdigest()


def check_nobility(world, seed: str) -> list:
    """Проверяет устройство знати и престолонаследия."""
    problems = []

    for figure in world.figures.values():
        if figure.surname and not figure.house_id:
            problems.append("сид «%s»: у %s есть фамилия без рода"
                            % (seed, figure.name))
            break
    for figure in world.figures.values():
        if figure.house_id and not figure.surname:
            problems.append("сид «%s»: %s состоит в роду, но без фамилии"
                            % (seed, figure.given_name))
            break
    for figure in world.figures.values():
        if figure.surname and not figure.noble:
            problems.append("сид «%s»: %s с фамилией, но не знатен"
                            % (seed, figure.name))
            break

    for house in world.houses.values():
        race = get_race(house.race_id)
        if not race.has_nobility:
            problems.append("сид «%s»: у расы «%s» завёлся род %s"
                            % (seed, race.name, house.name))
            break

    for polity in world.polities.values():
        previous = None
        for index, reign_id in enumerate(polity.reign_ids, start=1):
            reign = world.reigns.get(reign_id)
            if reign is None:
                problems.append("сид «%s»: у страны %s потеряно правление"
                                % (seed, polity.name))
                break
            if reign.ruler_id not in world.figures:
                problems.append("сид «%s»: правление без правителя в %s"
                                % (seed, polity.name))
                break
            if reign.number != index:
                problems.append("сид «%s»: сбит счёт правлений в %s"
                                % (seed, polity.name))
                break
            if previous is not None and reign.start.ordinal < previous.start.ordinal:
                problems.append("сид «%s»: правления идут не по порядку в %s"
                                % (seed, polity.name))
                break
            previous = reign
        if problems:
            break

    return problems


def check_wars(world, seed: str) -> list:
    """Проверяет связность войн: стороны, сражения, мир, добыча."""
    problems = []

    for war in world.wars.values():
        if war.attacker_id == war.defender_id:
            problems.append("сид «%s»: война «%s» ведётся сама с собой"
                            % (seed, war.name))
            break
        if war.attacker_id not in world.polities \
                or war.defender_id not in world.polities:
            problems.append("сид «%s»: у войны «%s» потеряна сторона"
                            % (seed, war.name))
            break
        if war.end is not None and war.end.ordinal < war.start.ordinal:
            problems.append("сид «%s»: война «%s» кончилась раньше, чем началась"
                            % (seed, war.name))
            break
        if war.deaths < 0 or war.attacker_losses < 0 or war.defender_losses < 0:
            problems.append("сид «%s»: у войны «%s» отрицательные потери"
                            % (seed, war.name))
            break
        for battle_id in war.battle_ids:
            if battle_id not in world.battles:
                problems.append("сид «%s»: у войны «%s» потеряно сражение"
                                % (seed, war.name))
                break
        if problems:
            break
        if war.status == "длится" and war.id not in world.active_wars:
            problems.append("сид «%s»: идущая война «%s» не в списке идущих"
                            % (seed, war.name))
            break
        if war.status != "длится" and war.id in world.active_wars:
            problems.append("сид «%s»: законченная война «%s» числится идущей"
                            % (seed, war.name))
            break

    # Взятые города должны принадлежать победителю или быть разорены.
    for war in world.wars.values():
        if war.outcome != "победа нападавших":
            continue
        for settlement_id in war.taken_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is None:
                problems.append("сид «%s»: война «%s» взяла несуществующий город"
                                % (seed, war.name))
                break
        if problems:
            break

    for feud in world.feuds.values():
        if len(feud.polity_ids) != 2:
            problems.append("сид «%s»: у распри «%s» не две стороны"
                            % (seed, feud.name))
            break
        if feud.end is not None and feud.start is not None \
                and feud.end.ordinal < feud.start.ordinal:
            problems.append("сид «%s»: распря «%s» кончилась раньше начала"
                            % (seed, feud.name))
            break
        for war_id in feud.war_ids:
            if war_id not in world.wars:
                problems.append("сид «%s»: у распри «%s» потеряна война"
                                % (seed, feud.name))
                break
        if problems:
            break

    # Дань и покорность должны указывать на живые державы.
    for polity in world.polities.values():
        for key in ("tribute_to", "overlord_id"):
            other_id = getattr(polity, key)
            if other_id and other_id not in world.polities:
                problems.append("сид «%s»: страна %s платит несуществующей державе"
                                % (seed, polity.name))
                break
        if problems:
            break

    return problems


def check_politics(world, seed: str) -> list:
    """Проверяет связность политики: договоры, союзы, крепости, роты."""
    problems = []

    for pact in world.pacts.values():
        if pact.first_id == pact.second_id:
            problems.append("сид «%s»: договор заключён сам с собой" % seed)
            break
        if pact.first_id not in world.polities \
                or pact.second_id not in world.polities:
            problems.append("сид «%s»: у договора потеряна сторона" % seed)
            break
        if pact.ended is not None and pact.ended.ordinal < pact.signed.ordinal:
            problems.append("сид «%s»: договор расторгнут раньше, чем заключён"
                            % seed)
            break
        if pact.status == "активно" and pact.id not in world.active_pacts:
            problems.append("сид «%s»: действующий договор не в списке" % seed)
            break

    # Между одной парой держав не может быть двух действующих договоров.
    seen = set()
    for pact_id in world.active_pacts:
        pact = world.pacts[pact_id]
        key = tuple(sorted((pact.first_id, pact.second_id)))
        if key in seen:
            problems.append("сид «%s»: у пары держав два договора разом" % seed)
            break
        seen.add(key)

    for league in world.leagues.values():
        if league.ended is not None and league.founded is not None \
                and league.ended.ordinal < league.founded.ordinal:
            problems.append("сид «%s»: союз «%s» распался раньше, чем сложился"
                            % (seed, league.name))
            break
        if league.status == "активно":
            if len(league.member_ids) < 2:
                problems.append("сид «%s»: в союзе «%s» некому состоять"
                                % (seed, league.name))
                break
            if league.leader_id and league.leader_id not in league.member_ids:
                problems.append("сид «%s»: во главе союза «%s» тот, кто в нём "
                                "не состоит" % (seed, league.name))
                break

    for fortress in world.fortresses.values():
        if fortress.region_id not in world.regions:
            problems.append("сид «%s»: крепость %s стоит в несуществующей земле"
                            % (seed, fortress.name))
            break
        if fortress.polity_id and fortress.polity_id not in world.polities:
            problems.append("сид «%s»: крепость %s держит несуществующая держава"
                            % (seed, fortress.name))
            break
        if fortress.ended is not None \
                and fortress.ended.ordinal < fortress.built.ordinal:
            problems.append("сид «%s»: крепость %s разрушена раньше постройки"
                            % (seed, fortress.name))
            break

    for company in world.companies.values():
        if company.men <= 0:
            problems.append("сид «%s»: в роте «%s» нет людей"
                            % (seed, company.name))
            break
        if company.employer_id and company.employer_id not in world.polities:
            problems.append("сид «%s»: роту «%s» нанял никто"
                            % (seed, company.name))
            break

    # Союзники войны должны быть настоящими державами и не воевать сами с собой.
    for war in world.wars.values():
        both = set(war.attacker_allies) & set(war.defender_allies)
        if both:
            problems.append("сид «%s»: в войне «%s» союзник на обеих сторонах"
                            % (seed, war.name))
            break
        for ally_id in war.attacker_allies + war.defender_allies:
            if ally_id not in world.polities:
                problems.append("сид «%s»: в войне «%s» союзник-призрак"
                                % (seed, war.name))
                break
        if war.attacker_id in war.defender_allies \
                or war.defender_id in war.attacker_allies:
            problems.append("сид «%s»: в войне «%s» сторона союзничает сама с "
                            "собой" % (seed, war.name))
            break

    return problems


def check_tongues(world, seed: str) -> list:
    """Проверяет связность языков: родство, носителей, письменность."""
    from worldgen import tongues as tng

    problems = []
    for tongue in world.tongues.values():
        if tongue.parent_id and tongue.parent_id not in world.tongues:
            problems.append("сид «%s»: у языка «%s» потерян родитель"
                            % (seed, tongue.name))
            break
        if tongue.parent_id == tongue.id:
            problems.append("сид «%s»: язык «%s» происходит сам от себя"
                            % (seed, tongue.name))
            break
        if tongue.ended is not None and tongue.ended.ordinal < tongue.born.ordinal:
            problems.append("сид «%s»: язык «%s» умолк раньше, чем родился"
                            % (seed, tongue.name))
            break
        if tongue.status == tng.LIVING and tongue.id not in world.living_tongues:
            problems.append("сид «%s»: живой язык «%s» не в списке живых"
                            % (seed, tongue.name))
            break
        if tongue.status != tng.LIVING and tongue.id in world.living_tongues:
            problems.append("сид «%s»: умолкший язык «%s» числится живым"
                            % (seed, tongue.name))
            break
        if tongue.script_from and tongue.script_from not in world.tongues:
            problems.append("сид «%s»: письмо языка «%s» взято ниоткуда"
                            % (seed, tongue.name))
            break
        if tongue.script_from and not tongue.script:
            problems.append("сид «%s»: у языка «%s» есть источник письма, но "
                            "нет письма" % (seed, tongue.name))
            break

    # Круг в родословной языков невозможен.
    for tongue in world.tongues.values():
        seen, walk = set(), tongue
        while walk is not None and walk.parent_id:
            if walk.id in seen:
                problems.append("сид «%s»: языки «%s» ходят по кругу"
                                % (seed, tongue.name))
                break
            seen.add(walk.id)
            walk = world.tongues.get(walk.parent_id)
        else:
            continue
        break

    # Народ и его язык должны знать друг о друге.
    for folk in world.folks.values():
        if not folk.tongue_id:
            continue
        tongue = world.tongues.get(folk.tongue_id)
        if tongue is None:
            problems.append("сид «%s»: народ %s говорит на несуществующем языке"
                            % (seed, folk.name))
            break
        if folk.id not in tongue.folk_ids:
            problems.append("сид «%s»: народ %s не числится среди говорящих на "
                            "«%s»" % (seed, folk.name, tongue.name))
            break

    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if polity.tongue_id and polity.tongue_id not in world.tongues:
            problems.append("сид «%s»: у державы %s язык двора неизвестен"
                            % (seed, polity.name))
            break

    # Живой язык без единого говорящего — это мёртвый язык.
    for tongue_id in world.living_tongues:
        tongue = world.tongues[tongue_id]
        alive = [fid for fid in tongue.folk_ids
                 if fid in world.folks and world.folks[fid].population > 0]
        if not alive and world.total_years - tongue.born.year > 400:
            problems.append("сид «%s»: на живом языке «%s» никто не говорит"
                            % (seed, tongue.name))
            break

    return problems


def check_embassies(world, seed: str) -> list:
    """Проверяет связность посольств, уний и записанных обид."""
    problems = []
    for record in world.embassies.values():
        if record.sender_id == record.host_id:
            problems.append("сид «%s»: посольство отправлено самим себе" % seed)
            break
        for key in (record.sender_id, record.host_id):
            if key not in world.polities:
                problems.append("сид «%s»: у посольства потеряна сторона" % seed)
                break
        if record.envoy_id and record.envoy_id not in world.figures:
            problems.append("сид «%s»: посольство без посла" % seed)
            break
        if record.returned is not None \
                and record.returned.ordinal < record.sent.ordinal:
            problems.append("сид «%s»: посольство вернулось раньше, чем выехало"
                            % seed)
            break
        if record.pact_id and record.pact_id not in world.pacts:
            problems.append("сид «%s»: договор посольства не найден" % seed)
            break

    for guild in world.guilds.values():
        if guild.seat_id and guild.seat_id not in world.settlements:
            problems.append("сид «%s»: гильдия %s сидит в несуществующем городе"
                            % (seed, guild.name))
            break
        if guild.polity_id and guild.polity_id not in world.polities:
            problems.append("сид «%s»: гильдия %s в несуществующей державе"
                            % (seed, guild.name))
            break
        if guild.ended is not None \
                and guild.ended.ordinal < guild.founded.ordinal:
            problems.append("сид «%s»: гильдия %s кончилась раньше, чем "
                            "завелась" % (seed, guild.name))
            break
        if guild.status == ACTIVE and guild.id not in world.active_guilds:
            problems.append("сид «%s»: живая гильдия %s не в списке живых"
                            % (seed, guild.name))
            break
        if guild.republic_id and guild.republic_id not in world.polities:
            problems.append("сид «%s»: вольный город гильдии %s не найден"
                            % (seed, guild.name))
            break
        for polity_id in guild.charters:
            if polity_id not in world.polities:
                problems.append("сид «%s»: вольности гильдии %s при "
                                "несуществующем дворе" % (seed, guild.name))
                break

    for plot in world.plots.values():
        if plot.sender_id == plot.target_id:
            problems.append("сид «%s»: тайное дело затеяно против себя" % seed)
            break
        if plot.agent_id and plot.agent_id not in world.figures:
            problems.append("сид «%s»: тайное дело без исполнителя" % seed)
            break
        if plot.victim_id and plot.victim_id not in world.figures:
            problems.append("сид «%s»: у тайного дела жертва-призрак" % seed)
            break
        if plot.kind not in espionage.DEEDS_BY_KEY:
            problems.append("сид «%s»: тайное дело неизвестного рода (%s)"
                            % (seed, plot.kind))
            break
        if plot.war_id and plot.war_id not in world.wars:
            problems.append("сид «%s»: тайное дело в несуществующей войне" % seed)
            break

    for union in world.unions.values():
        if union.first_id == union.second_id:
            problems.append("сид «%s»: держава в унии сама с собой" % seed)
            break
        for key in (union.first_id, union.second_id):
            if key not in world.polities:
                problems.append("сид «%s»: у унии потеряна держава" % seed)
                break
        if union.ended is not None \
                and union.ended.ordinal < union.started.ordinal:
            problems.append("сид «%s»: уния распалась раньше, чем сложилась"
                            % seed)
            break
        if union.status == ACTIVE:
            first = world.polities.get(union.first_id)
            second = world.polities.get(union.second_id)
            if first is None or second is None:
                continue
            if first.ruler_id != second.ruler_id:
                problems.append("сид «%s»: в действующей унии два государя"
                                % seed)
                break
            if first.union_id != union.id or second.union_id != union.id:
                problems.append("сид «%s»: держава не помнит своей унии" % seed)
                break

    for polity in world.polities.values():
        for other_id, items in (polity.grudges or {}).items():
            if other_id == polity.id:
                problems.append("сид «%s»: держава %s держит обиду на себя"
                                % (seed, polity.name))
                break
            for key, when in items.items():
                if key not in warfare.CAUSES_BY_KEY:
                    problems.append("сид «%s»: обида без повода (%s)"
                                    % (seed, key))
                    break
                if when < 1 or when > world.total_years:
                    problems.append("сид «%s»: обида записана вне истории"
                                    % seed)
                    break
    return problems


def check_mortality(world, seed: str) -> list:
    """Отчего они умерли: причина названа, согласована и не противоречит веку.

    Четыре вещи, каждая из которых однажды была сломана.

    Первая: причина должна быть у тех, кого летопись заметила. Прежде она
    стояла только у казнённых — у одного умершего из девяти.

    Вторая: «умерла в родах» не бывает у мужчины. Формы хранятся парами, и
    перепутать их проще всего там, где пара вырожденная.

    Третья: от старости не умирают молодыми. Доля отмеренного расе срока —
    та самая мера, по которой причина и выбирается, и она не должна
    расходиться с написанным.

    Четвёртая: раса, которой в этом мире век не отмерен, от старости не
    умирает вовсе — она уходит. Если в таком мире нашлась смерть «в
    глубокой старости», значит особенность мира до свода причин не дошла.
    """
    from worldgen import mortality

    problems = []
    gifts = getattr(world, "race_gifts", None) or {}
    old_set = set()
    for pair in mortality.OLD_AGE:
        old_set.update(pair)
    birth_set = set()
    for pair in mortality.CHILDBIRTH:
        birth_set.add(pair[1])
    departure = set()
    for pair in mortality.DEPARTURE:
        departure.update(pair)

    seen = named = 0
    for figure in world.figures.values():
        if figure.death is None or figure.birth is None:
            continue
        if not (figure.deeds or figure.titles or figure.posthumous):
            continue
        seen += 1
        cause = figure.death_cause
        if not cause:
            continue
        named += 1
        if cause in birth_set and figure.sex != "f":
            problems.append("сид «%s»: %s — мужчина, а умер в родах"
                            % (seed, figure.name))
            break
        race = get_race(figure.race_id)
        if race is None:
            continue
        share = (figure.death.year - figure.birth.year) / float(
            max(1, race.lifespan[1]))
        if cause in old_set:
            if share < mortality.PRIME_FROM:
                problems.append("сид «%s»: %s умер от старости, прожив %d%% "
                                "своего века"
                                % (seed, figure.name, round(share * 100)))
                break
            if gifts.get(figure.race_id) == mortality.UNAGING:
                problems.append("сид «%s»: %s умер от старости, хотя его "
                                "расе век в этом мире не отмерен"
                                % (seed, figure.name))
                break
        if cause in departure \
                and gifts.get(figure.race_id) != mortality.UNAGING:
            problems.append("сид «%s»: %s ушёл, как не умирающий от "
                            "старости, — а его раса в этом мире стареет"
                            % (seed, figure.name))
            break
    # Треть — заведомо достижимый порог: на пробах выходит около девяти
    # десятых. Проверка ловит обрыв связи, а не калибровку.
    if seen >= 50 and named < seen * 0.33:
        problems.append("сид «%s»: причина смерти названа лишь у %d из %d "
                        "замеченных летописью" % (seed, named, seen))
    return problems


def check_town_bread(world, seed: str) -> list:
    """Хлеб земли: города делят его, а не выдумывают каждый свой.

    Тут ловится то, что ломается тихо. Племя, записанное влившимся в
    город, которого нет, — или в город чужой земли и чужой крови: тогда
    летопись говорит об одном, а реестры о другом. Поселение, которое
    одно на всю землю держит больше душ, чем земля кормит во всех своих
    городах вместе: это значит, что делёж хлеба обошли стороной.

    Запас взят с умыслом. Хлеб земли считается на год такта, а людность
    города — на конец истории; за век между ними земля могла и оскудеть.
    Поэтому проверка срабатывает не на превышение, а на превышение в
    разы: это уже не колебание, а обход правила.

    Чего тут нарочно не проверяется — крови города. Племя приходит в
    город своего народа, но город потом берут, переименовывают и
    переселяют, и через триста лет он другой расы. Сторож на это
    срабатывал и был неправ: запись летописи верна для своего года, а не
    для конца истории. По той же причине имя годится и прежнее.
    """
    from worldgen.systems import founding
    from worldgen.models import SETTLED

    problems = []
    # --- племя пришло в готовый город ---------------------------------
    for tribe in world.tribes.values():
        if tribe.status != SETTLED or not tribe.settlement_id:
            continue
        settlement = world.settlements.get(tribe.settlement_id)
        if settlement is None:
            problems.append("сид «%s»: племя %s осело в городе, которого в "
                            "мире нет" % (seed, tribe.name))
            break
        said = tribe.end_reason or ""
        if "влилось в город" not in said:
            continue        # своё поселение построило — это другой исход
        # Имя годится и прежнее. Город переименовывают победители, и
        # запись летописи остаётся с тем именем, какое было в её год:
        # племя пришло в Голодный Костёр, а через сто лет город зовётся
        # Эонатиэлем. Это не расхождение, а память.
        names = [settlement.name] + list(settlement.old_names or ())
        if not any(name and name in said for name in names):
            problems.append("сид «%s»: племя %s влилось в город «%s», а в "
                            "летописи назван другой, и прежним именем он "
                            "так не звался: %s"
                            % (seed, tribe.name, settlement.name, said))
            break
        if tribe.region_id and settlement.region_id != tribe.region_id:
            problems.append("сид «%s»: племя %s влилось в город на другой "
                            "земле (%s)" % (seed, tribe.name, settlement.name))
            break

    # --- хлеб земли ----------------------------------------------------
    if not problems:
        alone = {}
        for settlement_id in world.active_settlements:
            settlement = world.settlements[settlement_id]
            alone[settlement.region_id] = alone.get(settlement.region_id,
                                                    0) + 1
        for settlement_id in world.active_settlements:
            settlement = world.settlements[settlement_id]
            if alone.get(settlement.region_id, 0) != 1:
                continue    # делёж проверяется на том, кто на земле один
            region = world.regions.get(settlement.region_id)
            if region is None or region.capacity <= 0:
                continue
            # Полный хлеб земли в самые тучные годы: с запасом на эпоху и
            # на урожайность карты.
            bread = founding.REGION_BREAD * region.capacity * 3.0
            if settlement.population > bread * 3.0:
                problems.append(
                    "сид «%s»: %s держит %d душ, а земля по имени %s кормит "
                    "в своих городах около %d"
                    % (seed, settlement.full_name, settlement.population,
                       region.name, int(bread)))
                break
    return problems


def check_ranks(world, seed: str) -> list:
    """Ступень поселения: она считается из людности и не врёт о нём.

    Беда, которую это сторожит: вид поселения ставился при основании и не
    менялся никогда, и в мире жила «Застава» на сто двадцать тысяч душ.
    Теперь вид и ступень — разные вещи, и проверяется обе стороны:
    малый по виду не бывает городским по ступени, а ступень сходится с
    людностью (с запасом на гистерезис, без которого поселение у порога
    прыгало туда-обратно каждые десять лет).

    Заодно кривая людности: годы в ней идут вперёд, а наибольшее число не
    меньше нынешнего.
    """
    from worldgen import township as cat

    problems = []
    for settlement in world.settlements.values():
        if settlement.kind in cat.OUTGROWN and cat.is_city(settlement.rank):
            problems.append("сид «%s»: %s — %s по виду, но %s по ступени"
                            % (seed, settlement.name,
                               settlement.kind.lower(), settlement.rank))
            break
    for settlement in world.settlements.values():
        if settlement.status != ACTIVE:
            continue
        proper = cat.rank_of(settlement.population)
        if abs(cat.rank_index(proper)
               - cat.rank_index(settlement.rank)) > 1:
            problems.append("сид «%s»: у %s ступень «%s» при %d душах "
                            "(по людности — «%s»)"
                            % (seed, settlement.name, settlement.rank,
                               settlement.population, proper))
            break
    for settlement in world.settlements.values():
        rows = settlement.census or []
        for index in range(len(rows) - 1):
            if rows[index][0] > rows[index + 1][0]:
                problems.append("сид «%s»: у %s кривая людности идёт вспять: "
                                "%d после %d"
                                % (seed, settlement.name, rows[index + 1][0],
                                   rows[index][0]))
                break
        if problems:
            break
        if rows and settlement.peak_population < max(row[1] for row in rows):
            problems.append("сид «%s»: у %s наибольшая людность меньше той, "
                            "что стоит в кривой" % (seed, settlement.name))
            break
    return problems


def check_war_cost(world, seed: str) -> list:
    """Цена войны: ратные и мирные считаются врозь и складываются верно.

    Прежде убитые при взятии города шли в потери державы, а разорение
    округи не считалось вовсе — война двух княжеств выходила в сто
    двадцать человек. Проверяется, что числа сходятся, что размах лежит в
    своих пределах и что у распри позднее имя появляется только тогда,
    когда первое и правда разошлось со сроком.
    """
    from worldgen import narrative_war as war_texts

    problems = []
    for war in world.wars.values():
        if war.civil_losses < 0 or war.attacker_losses < 0 \
                or war.defender_losses < 0:
            problems.append("сид «%s»: у войны «%s» потери ниже нуля"
                            % (seed, war.name))
            break
        if war.deaths != war.soldiers + war.civil_losses:
            problems.append("сид «%s»: у войны «%s» итог потерь не сходится "
                            "со слагаемыми" % (seed, war.name))
            break
        if not 1 <= war.scale <= 5:
            problems.append("сид «%s»: у войны «%s» размах %d вне 1…5"
                            % (seed, war.name, war.scale))
            break
    for feud in world.feuds.values():
        if not feud.late_name:
            continue
        word = war_texts.feud_span_word(feud.years)
        if word.lower() in (feud.first_name or "").lower():
            problems.append("сид «%s»: распрю «%s» переименовали, хотя срок "
                            "в первом имени назван верно"
                            % (seed, feud.first_name))
            break
    return problems


def check_world_code(world, seed: str) -> list:
    """Код мира: он собирается и разбирается обратно без потерь.

    Код — это обещание: вставил — получил тот самый мир. Если он не
    разбирается или теряет настройки, обещание нарушено молча, и человек
    узнает об этом, только построив другой мир.
    """
    from worldgen import worldcode

    settings = world.settings or {}
    if not settings:
        return []
    problems = []
    try:
        code = worldcode.encode(settings)
        got = worldcode.decode(code)
    except Exception as error:
        return ["сид «%s»: код мира не собрался или не разобрался: %s"
                % (seed, error)]
    if got.get("seed") != settings.get("seed"):
        problems.append("сид «%s»: код мира потерял сид: «%s» вместо «%s»"
                        % (seed, got.get("seed"), settings.get("seed")))
    if int(got.get("years", 10000)) != int(settings.get("years", 10000)):
        problems.append("сид «%s»: код мира потерял длительность" % seed)
    if dict(got.get("map_make") or {}) != dict(settings.get("map_make") or {}):
        problems.append("сид «%s»: код мира потерял настройки карты" % seed)
    if dict(got.get("tuning") or {}) != dict(settings.get("tuning") or {}):
        problems.append("сид «%s»: код мира потерял шкалы движка" % seed)
    return problems


def check_after_end(world, seed: str) -> list:
    """Записей позже последнего года истории быть не должно.

    Люди, живые к концу, умирают уже за краем — это верно и нарочно. Но
    само событие летописи за краем означает, что кто-то посчитал год не
    от мира, а от своей мерки.
    """
    problems = []
    total = int(world.total_years)
    for event in world.events:
        if event.date.year > total:
            problems.append("сид «%s»: запись «%s» датирована %d годом, а "
                            "история кончается на %d"
                            % (seed, event.title, event.date.year, total))
            break
    for figure in world.figures.values():
        if figure.birth is not None and figure.birth.year > total:
            problems.append("сид «%s»: %s родился в %d году, а история "
                            "кончается на %d"
                            % (seed, figure.name, figure.birth.year, total))
            break
    return problems


def check_calamities(world, seed: str) -> list:
    """Проверяет связность бедствий, их следов и сражений."""
    problems = []

    for calamity in world.calamities.values():
        if calamity.end is None and calamity.status != "длится":
            problems.append("сид «%s»: бедствие «%s» без даты конца"
                            % (seed, calamity.name))
            break
        if calamity.end is not None and calamity.end.ordinal < calamity.start.ordinal:
            problems.append("сид «%s»: бедствие «%s» кончилось раньше начала"
                            % (seed, calamity.name))
            break
        for region_id in calamity.region_ids:
            if region_id not in world.regions:
                problems.append("сид «%s»: бедствие «%s» ссылается на пустую землю"
                                % (seed, calamity.name))
                break
        if calamity.parent_id and calamity.parent_id not in world.calamities:
            problems.append("сид «%s»: у бедствия «%s» потерян родитель"
                            % (seed, calamity.name))
            break

    faith_relics = ("храм забытой веры", "идол забытого бога")
    for relic in world.relics.values():
        if relic.kind in faith_relics:
            continue          # следы забытых вер остаются не от бедствий
        if any("логово с карты" in note for note in relic.notes):
            continue          # логова лежали в мире ещё до первых бедствий
        if relic.calamity_id not in world.calamities:
            problems.append("сид «%s»: след «%s» без своего бедствия"
                            % (seed, relic.name))
            break

    for battle in world.battles.values():
        if battle.war_id:
            continue          # сражения держав принадлежат войне, а не беде
        if battle.calamity_id not in world.calamities:
            problems.append("сид «%s»: сражение «%s» без своего бедствия"
                            % (seed, battle.name))
            break

    for settlement in world.settlements.values():
        if settlement.population < 0:
            problems.append("сид «%s»: у поселения %s отрицательное население"
                            % (seed, settlement.name))
            break

    for record in world.dark_ages:
        if record["end"] <= record["start"]:
            problems.append("сид «%s»: тёмные века нулевой длины" % seed)
            break

    monsters = {race.id for race in __import__(
        "worldgen.races", fromlist=["MONSTERS"]).MONSTERS}
    for settlement in world.settlements.values():
        if settlement.race_id in monsters:
            problems.append("сид «%s»: чудовища построили город %s"
                            % (seed, settlement.name))
            break
    for house in world.houses.values():
        if house.race_id in monsters:
            problems.append("сид «%s»: у чудовищ завёлся знатный род" % seed)
            break

    return problems


def check_disasters(world, seed: str) -> list:
    """Живая катастрофа: причины, фронт, шрамы, утраты и времена бед.

    Смысловые правила, которые нельзя нарушать: причина не позже беды,
    шрам не в утонувшей земле, знание не найдено раньше, чем потеряно,
    роль города не спорит с тем, что стало с землёй, и эпоха не короче
    своей первой беды.
    """
    from worldgen import disaster as dis

    problems = []

    for calamity in world.calamities.values():
        if calamity.cause_year and calamity.cause_year > calamity.start.year:
            problems.append("сид «%s»: у беды «%s» причина позже самой беды"
                            % (seed, calamity.name))
            break
        for omen in calamity.omens:
            if int(omen.get("год", 0)) > calamity.start.year:
                problems.append("сид «%s»: знак беды «%s» позже её начала"
                                % (seed, calamity.name))
                break
        for scar_id in calamity.scar_ids:
            if scar_id not in world.scars:
                problems.append("сид «%s»: у беды «%s» потерян шрам"
                                % (seed, calamity.name))
                break
        for lore_id in calamity.lore_ids:
            if lore_id not in world.lost_lore:
                problems.append("сид «%s»: у беды «%s» потеряна утрата"
                                % (seed, calamity.name))
                break
        for kind, value in (calamity.damage or {}).items():
            if kind not in dis.DAMAGE_KINDS or not 0.0 <= value <= 1.0:
                problems.append("сид «%s»: у беды «%s» ущерб вида «%s» вне "
                                "меры" % (seed, calamity.name, kind))
                break

    for scar in world.scars.values():
        region = world.regions.get(scar.region_id)
        if region is None:
            problems.append("сид «%s»: шрам «%s» стоит в пустой земле"
                            % (seed, scar.name))
            break
        if region.drowned and scar.state != dis.SCAR_FORGOTTEN:
            # Утонувшая земля забирает шрам с собой: помнить его некому.
            # Не забытый шрам под водой — это недоведённая запись.
            problems.append("сид «%s»: шрам «%s» остался под водой, а мир его "
                            "всё ещё помнит" % (seed, scar.name))
            break
        if scar.state not in dis.SCAR_STATES:
            problems.append("сид «%s»: у шрама «%s» неведомое состояние «%s»"
                            % (seed, scar.name, scar.state))
            break
        if scar.calamity_id and scar.calamity_id not in world.calamities:
            problems.append("сид «%s»: у шрама «%s» нет своей беды"
                            % (seed, scar.name))
            break
        if scar.kind not in dis.SCARS_BY_KEY:
            problems.append("сид «%s»: у шрама «%s» неведомый вид"
                            % (seed, scar.name))
            break

    for lore in world.lost_lore.values():
        if lore.kind not in dis.LORE_BY_KEY:
            problems.append("сид «%s»: утрата «%s» неведомого вида"
                            % (seed, lore.kind))
            break
        if lore.state not in dis.LORE_STATES:
            problems.append("сид «%s»: у утраты «%s» неведомое состояние"
                            % (seed, lore.kind))
            break
        if lore.found is not None and lore.lost is not None \
                and lore.found.ordinal < lore.lost.ordinal:
            problems.append("сид «%s»: утрата «%s» найдена раньше, чем "
                            "потеряна" % (seed, lore.kind))
            break
        if lore.state == dis.LORE_FOUND and lore.found is None:
            problems.append("сид «%s»: утрата «%s» найдена без года"
                            % (seed, lore.kind))
            break

    for calamity in world.calamities.values():
        for row in calamity.front:
            state = row.get("состояние", "")
            if state not in dis.LAND_STATES:
                problems.append("сид «%s»: у земли в фронте беды «%s» "
                                "неведомое состояние «%s»"
                                % (seed, calamity.name, state))
                break
            if row["земля"] not in world.regions:
                problems.append("сид «%s»: фронт беды «%s» идёт по пустой "
                                "земле" % (seed, calamity.name))
                break
            if int(row.get("год", 0)) < calamity.start.year:
                problems.append("сид «%s»: фронт беды «%s» пошёл раньше самой "
                                "беды" % (seed, calamity.name))
                break
            role = row.get("роль", "")
            if role and role not in dis.CITY_ROLES:
                problems.append("сид «%s»: у города в фронте беды «%s» "
                                "неведомая роль «%s»"
                                % (seed, calamity.name, role))
                break
            if role == dis.ROLE_STOOD and state == dis.LAND_HELD:
                problems.append("сид «%s»: город «выстоял» в земле, которую "
                                "заняли (беда «%s»)" % (seed, calamity.name))
                break

    for era in world.crisis_eras.values():
        if era.end is not None and era.end.ordinal < era.start.ordinal:
            problems.append("сид «%s»: время бед «%s» кончилось раньше начала"
                            % (seed, era.name or era.id))
            break
        if era.end is not None and not era.name:
            problems.append("сид «%s»: закрытое время бед осталось без имени"
                            % seed)
            break
        if len(era.calamity_ids) < 2:
            problems.append("сид «%s»: время бед «%s» из одной беды"
                            % (seed, era.name or era.id))
            break
        for calamity_id in era.calamity_ids:
            calamity = world.calamities.get(calamity_id)
            if calamity is None:
                problems.append("сид «%s»: у времени бед «%s» потеряна беда"
                                % (seed, era.name or era.id))
                break
            if calamity.start.year < era.start.year - 1:
                problems.append("сид «%s»: беда «%s» старше своего времени бед"
                                % (seed, calamity.name))
                break

    names = [era.name for era in world.crisis_eras.values() if era.name]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: у двух времён бед одно имя" % seed)

    for region in world.regions.values():
        for kind, value in (region.vulnerability or {}).items():
            # У земли уязвимость хранится по роду беды («голод», «мор»), а
            # не по ключу бедствия: `VULNERABLE_BY_KEY` — это другое.
            if kind not in dis.VULNERABILITIES or not 0.0 <= value <= 1.0:
                problems.append("сид «%s»: у земли %s уязвимость «%s» вне меры"
                                % (seed, region.name, kind))
                break

    # Правило мира переменяется один раз и только самой глубокой бедой.
    changed = world.notes.get("правила мира") or []
    seen = set()
    for row in changed:
        rule = row.get("что", "")
        if rule not in dis.WORLD_RULES:
            problems.append("сид «%s»: переменилось неведомое правило мира "
                            "«%s»" % (seed, rule))
            break
        if rule in seen:
            problems.append("сид «%s»: правило мира «%s» переменилось дважды"
                            % (seed, rule))
            break
        seen.add(rule)
        if int(row.get("год", 0)) > world.total_years:
            problems.append("сид «%s»: правило мира переменилось после конца "
                            "истории" % seed)
            break
    deep = {item.name for item in world.calamities.values()
            if item.depth >= 5}
    for row in changed:
        if row.get("беда") and row["беда"] not in deep:
            problems.append("сид «%s»: правило мира переменила беда «%s», "
                            "которая для этого недостаточно глубока"
                            % (seed, row["беда"]))
            break

    return problems


def check_invasions(world, seed: str) -> list:
    """Нашествия: сходится ли история прихода сама с собой.

    Смысловые правила: у нашествия есть своя беда; род, причина, цель и
    исход — из каталога; цель, с которой пришли, стоит в начале цепочки
    перемен; вождь не может открыться раньше, чем всё началось; город
    «выстоял» не спорит с землёй (это проверяет `check_disasters`), а
    здесь — что имя события не повторяет чужое и что остатки лежат в
    настоящих землях.
    """
    from worldgen import invasion as inv

    problems = []
    names = []
    for item in world.invasions.values():
        calamity = world.calamities.get(item.calamity_id)
        if calamity is None:
            problems.append("сид «%s»: у нашествия «%s» нет своей беды"
                            % (seed, item.title or item.id))
            break
        if item.kind not in inv.INVADERS_BY_KEY:
            problems.append("сид «%s»: у нашествия «%s» неведомый род «%s»"
                            % (seed, item.title or item.id, item.kind))
            break
        if item.cause and item.cause not in inv.CAUSES_BY_KEY:
            problems.append("сид «%s»: у нашествия «%s» неведомая причина «%s»"
                            % (seed, item.title or item.id, item.cause))
            break
        if item.goal and item.goal not in inv.GOALS_BY_KEY:
            problems.append("сид «%s»: у нашествия «%s» неведомая цель «%s»"
                            % (seed, item.title or item.id, item.goal))
            break
        if item.host and item.host not in inv.HOSTS_BY_KEY:
            problems.append("сид «%s»: у нашествия «%s» неведомый размер «%s»"
                            % (seed, item.title or item.id, item.host))
            break
        if item.outcome and item.outcome not in inv.OUTCOMES:
            problems.append("сид «%s»: у нашествия «%s» неведомый исход «%s»"
                            % (seed, item.title or item.id, item.outcome))
            break
        if item.way and item.way not in inv.WAYS_BY_KEY:
            problems.append("сид «%s»: у нашествия «%s» неведомый способ «%s»"
                            % (seed, item.title or item.id, item.way))
            break
        if item.surrender and item.surrender not in {
                key for key, _ in inv.SURRENDERS}:
            problems.append("сид «%s»: у нашествия «%s» неведомая сдача «%s»"
                            % (seed, item.title or item.id, item.surrender))
            break
        if item.ended is not None and item.ended.ordinal < item.started.ordinal:
            problems.append("сид «%s»: нашествие «%s» кончилось раньше начала"
                            % (seed, item.title or item.id))
            break
        if item.leader_shown and item.leader_shown < item.started.year:
            problems.append("сид «%s»: у нашествия «%s» вождь открылся раньше "
                            "начала" % (seed, item.title or item.id))
            break
        if item.leader_shown and item.leader_hidden:
            problems.append("сид «%s»: у нашествия «%s» вождь открылся и всё "
                            "ещё скрыт" % (seed, item.title or item.id))
            break
        for turn in item.goal_turns:
            if int(turn.get("год", 0)) < item.started.year:
                problems.append("сид «%s»: у нашествия «%s» цель сменилась "
                                "раньше начала" % (seed, item.title or item.id))
                break
        if item.goal_turns and item.goal_turns[0].get("было") != item.goal_first:
            problems.append("сид «%s»: у нашествия «%s» первая перемена цели "
                            "начинается не с той цели, с какой пришли"
                            % (seed, item.title or item.id))
            break
        if item.goal_turns and item.goal != item.goal_turns[-1].get("стало"):
            problems.append("сид «%s»: у нашествия «%s» нынешняя цель не "
                            "та, к которой пришли по переменам"
                            % (seed, item.title or item.id))
            break
        for row in item.remnants:
            region_id = row.get("земля", "")
            if region_id and region_id not in world.regions:
                problems.append("сид «%s»: остаток нашествия «%s» лежит в "
                                "пустой земле" % (seed, item.title or item.id))
                break
        for voice in item.names:
            if voice not in inv.VOICES:
                problems.append("сид «%s»: у нашествия «%s» имя неведомым "
                                "голосом «%s»"
                                % (seed, item.title or item.id, voice))
                break
        if item.title:
            names.append(item.title)
        if item.title and calamity.name != item.title:
            problems.append("сид «%s»: нашествие «%s» и его беда зовутся "
                            "по-разному" % (seed, item.title))
            break

    if len(names) != len(set(names)):
        problems.append("сид «%s»: у двух нашествий одно имя" % seed)
    return problems


def check_subjects(world, seed: str) -> list:
    """Субъекты истории: сходится ли биография сама с собой.

    Здесь ловится то, что ломается тихо: мертвец, который продолжает
    менять нрав; возвращение раньше, чем он умолк; срок деятельности,
    выходящий за пределы истории; мифическая ступень при жизни; две
    записи об одном и том же человеке; наследие из несуществующего рода.
    """
    from worldgen import subject as cat

    problems = []
    bound = {"figure_id": set(), "monster_id": set(),
             "deity_id": set(), "invasion_id": set()}
    wishes = {wish for wish, _ in cat.WISHES}
    tellers = {who for who, _ in cat.TELLERS}

    for item in world.subjects.values():
        name = item.name or item.id
        if item.kind not in cat.KINDS:
            problems.append("сид «%s»: у субъекта «%s» неведомый род «%s»"
                            % (seed, name, item.kind))
            break
        if item.origin and item.origin not in cat.ORIGINS:
            problems.append("сид «%s»: у субъекта «%s» неведомое появление "
                            "«%s»" % (seed, name, item.origin))
            break
        if item.status not in cat.STATUSES:
            problems.append("сид «%s»: у субъекта «%s» неведомое положение "
                            "«%s»" % (seed, name, item.status))
            break
        if item.end and item.end not in cat.ENDS:
            problems.append("сид «%s»: у субъекта «%s» неведомый конец «%s»"
                            % (seed, name, item.end))
            break
        if item.rung not in cat.RUNGS:
            problems.append("сид «%s»: у субъекта «%s» неведомая ступень "
                            "памяти «%s»" % (seed, name, item.rung))
            break
        if item.wish_state and item.wish_state not in cat.GOAL_STATES:
            problems.append("сид «%s»: у субъекта «%s» неведомое состояние "
                            "цели «%s»" % (seed, name, item.wish_state))
            break
        for fact, state in item.facts.items():
            if state not in cat.FACT_STATES:
                problems.append("сид «%s»: у субъекта «%s» факт «%s» в "
                                "неведомом состоянии «%s»"
                                % (seed, name, fact, state))
                break

        if not 1 <= item.entered.year <= world.total_years:
            problems.append("сид «%s»: субъект «%s» вошёл в летопись вне "
                            "истории" % (seed, name))
            break
        if item.origin_year and item.origin_year > item.entered.year:
            problems.append("сид «%s»: субъект «%s» появился позже, чем "
                            "попал в летопись" % (seed, name))
            break
        if item.ended is not None and item.ended.ordinal < item.entered.ordinal:
            problems.append("сид «%s»: субъект «%s» кончился раньше, чем "
                            "начался" % (seed, name))
            break
        if item.named_year and item.named_year < item.entered.year:
            problems.append("сид «%s»: субъекта «%s» опознали раньше, чем "
                            "он появился" % (seed, name))
            break

        last_end = 0
        broken = False
        for span in item.spans:
            since, until = int(span.get("с", 0)), int(span.get("по", 0))
            if until < since or since < item.entered.year \
                    or until > world.total_years:
                problems.append("сид «%s»: у субъекта «%s» срок деятельности "
                                "%d–%d не сходится" % (seed, name, since, until))
                broken = True
                break
            if since < last_end:
                problems.append("сид «%s»: у субъекта «%s» сроки "
                                "деятельности налезают друг на друга"
                                % (seed, name))
                broken = True
                break
            last_end = until
        if broken:
            break

        # Мертвец не действует: ни нрав, ни цель после смерти не меняются.
        died = item.ended.year if item.ended else None
        if died is not None:
            late = [int(turn.get("год", 0)) for turn in item.temper_turns
                    if int(turn.get("год", 0)) > died]
            late += [int(turn.get("год", 0)) for turn in item.wish_turns
                     if int(turn.get("год", 0)) > died]
            if late:
                problems.append("сид «%s»: субъект «%s» переменился после "
                                "своего конца (%d год)"
                                % (seed, name, sorted(late)[0]))
                break
            if item.spans and int(item.spans[-1].get("по", 0)) > died:
                problems.append("сид «%s»: субъект «%s» действовал после "
                                "своего конца" % (seed, name))
                break

        if item.wish_turns:
            if item.wish_turns[0].get("было") != item.wish_first:
                problems.append("сид «%s»: у субъекта «%s» первая перемена "
                                "цели начинается не с той, с какой он вошёл"
                                % (seed, name))
                break
            if item.wish != item.wish_turns[-1].get("стало"):
                problems.append("сид «%s»: у субъекта «%s» нынешняя цель не "
                                "та, к которой он пришёл по переменам"
                                % (seed, name))
                break
            unknown = [turn for turn in item.wish_turns
                       if turn.get("стало") not in wishes]
            if unknown:
                problems.append("сид «%s»: у субъекта «%s» цель переменилась "
                                "на неведомую" % (seed, name))
                break
        for turn in item.temper_turns:
            if turn.get("стало") not in cat.TEMPER_WORDS:
                problems.append("сид «%s»: у субъекта «%s» неведомый нрав "
                                "«%s»" % (seed, name, turn.get("стало")))
                break

        if item.rung == cat.RUNG_MYTH and item.status in (cat.ALIVE,
                                                          cat.ACTING):
            problems.append("сид «%s»: субъект «%s» стал мифом при жизни"
                            % (seed, name))
            break

        for row in item.legacy:
            kind = row.get("род", "")
            if kind not in cat.LEGACY_KINDS \
                    or row.get("что") not in cat.LEGACY_WORDS.get(kind, ()):
                problems.append("сид «%s»: у субъекта «%s» наследие "
                                "неведомого рода" % (seed, name))
                break
        for who in item.told:
            if who not in tellers:
                problems.append("сид «%s»: о субъекте «%s» рассказывает "
                                "неведомый голос «%s»" % (seed, name, who))
                break

        for field, seen in bound.items():
            value = getattr(item, field, "")
            if not value:
                continue
            if value in seen:
                problems.append("сид «%s»: о «%s» в своде две записи сразу"
                                % (seed, name))
                break
            seen.add(value)
        if item.figure_id and item.figure_id not in world.figures:
            problems.append("сид «%s»: субъект «%s» привязан к пустой "
                            "личности" % (seed, name))
            break
        if item.monster_id and item.monster_id not in world.monsters:
            problems.append("сид «%s»: субъект «%s» привязан к пустому зверю"
                            % (seed, name))
            break
        if item.deity_id and item.deity_id not in world.deities:
            problems.append("сид «%s»: субъект «%s» привязан к пустому богу"
                            % (seed, name))
            break
        if item.invasion_id and item.invasion_id not in world.invasions:
            problems.append("сид «%s»: субъект «%s» привязан к пустому "
                            "нашествию" % (seed, name))
            break
    return problems


def check_traces(world, seed: str) -> list:
    """Следы бед: сходится ли археология мира сама с собой.

    Здесь ловится то, что ломается тихо: след, появившийся раньше своей
    беды; находка раньше самого следа; найденный след, о котором никто
    не знает; слои руины, идущие вспять; печать с причиной, которой нет
    в каталоге.
    """
    from worldgen import remains as cat

    problems = []
    readings = set(cat.READINGS)
    findings = set(cat.FINDINGS) | set(cat.FIND_BY_GROUND)

    for trace in world.traces.values():
        name = trace.name or trace.id
        row = cat.TRACES_BY_KEY.get(trace.key)
        if row is None:
            problems.append("сид «%s»: след «%s» неведомого вида «%s»"
                            % (seed, name, trace.key))
            break
        if trace.kind != row.kind:
            problems.append("сид «%s»: у следа «%s» род не тот, что в "
                            "каталоге" % (seed, name))
            break
        if trace.state not in cat.STATES:
            problems.append("сид «%s»: у следа «%s» неведомое состояние «%s»"
                            % (seed, name, trace.state))
            break
        if trace.knowledge not in cat.KNOWLEDGE:
            problems.append("сид «%s»: о следе «%s» знают неведомо как «%s»"
                            % (seed, name, trace.knowledge))
            break
        if not 0 <= int(trace.life) <= 6:
            problems.append("сид «%s»: у следа «%s» немыслимая живость %s"
                            % (seed, name, trace.life))
            break

        calamity = world.calamities.get(trace.calamity_id)
        if calamity is None:
            problems.append("сид «%s»: след «%s» остался от беды, которой "
                            "не было" % (seed, name))
            break
        if trace.made is None or trace.made.ordinal < calamity.start.ordinal:
            problems.append("сид «%s»: след «%s» появился раньше своей беды"
                            % (seed, name))
            break
        if trace.made.year > world.total_years:
            problems.append("сид «%s»: след «%s» появился после конца "
                            "летописи" % (seed, name))
            break
        if trace.found is not None:
            if trace.found.ordinal < trace.made.ordinal:
                problems.append("сид «%s»: след «%s» нашли раньше, чем он "
                                "появился" % (seed, name))
                break
            if trace.knowledge == cat.FORGOTTEN:
                problems.append("сид «%s»: след «%s» нашли, и о нём всё ещё "
                                "не знают" % (seed, name))
                break

        if trace.region_id and trace.region_id not in world.regions:
            problems.append("сид «%s»: след «%s» лежит в пустой земле"
                            % (seed, name))
            break
        if trace.relic_id and trace.relic_id not in world.relics:
            problems.append("сид «%s»: след «%s» держится за пустую реликвию"
                            % (seed, name))
            break

        unknown = [item for item in trace.answers
                   if item not in cat.QUESTIONS]
        if unknown:
            problems.append("сид «%s»: след «%s» отвечает на вопрос, "
                            "которого нет" % (seed, name))
            break
        if trace.kind == cat.SEAL and trace.reason \
                and trace.reason not in cat.SEAL_REASONS:
            problems.append("сид «%s»: у печати «%s» причина не из каталога"
                            % (seed, name))
            break
        if trace.kind == cat.SURVIVOR and trace.reason \
                and trace.reason not in cat.SURVIVAL_REASONS:
            problems.append("сид «%s»: у уцелевшего «%s» причина не из "
                            "каталога" % (seed, name))
            break
        if trace.reading and trace.reading not in readings:
            problems.append("сид «%s»: след «%s» толкуют неведомо как"
                            % (seed, name))
            break
        if trace.quarrel and trace.quarrel not in cat.QUARRELS:
            problems.append("сид «%s»: у следа «%s» неведомое расхождение"
                            % (seed, name))
            break
        if trace.found_how and trace.found_how not in findings:
            problems.append("сид «%s»: след «%s» нашли неведомо как"
                            % (seed, name))
            break
        if trace.lost and trace.lost not in cat.LOST_STATES:
            problems.append("сид «%s»: у следа «%s» неведомое состояние "
                            "места" % (seed, name))
            break

        last = 0
        broken = False
        for row_layer in trace.layers:
            when = int(row_layer.get("год", 0))
            if when < last or when > trace.made.year:
                problems.append("сид «%s»: у следа «%s» слои идут вспять"
                                % (seed, name))
                broken = True
                break
            last = when
        if broken:
            break
    return problems


def check_year_slices(world, seed: str) -> list:
    """Срез мира на год собирается для любого года, а не только для конца.

    Вкладка «Временная шкала» строит этот текст на лету, и человек может
    назвать любой год — первый, последний и любой между. Проверяем края и
    середину: пустой срез или поломка на первом году мира заметна только
    здесь, потому что летопись целиком собирается другим путём.
    """
    from worldgen import chronicle

    problems = []
    total = max(1, world.total_years)
    for year in (1, total // 3, total // 2, total):
        try:
            text = chronicle.render_year(world, year)
        except Exception as error:          # noqa: BLE001 — сообщаем, а не падаем
            problems.append("сид «%s»: срез на %d год не собрался: %s"
                            % (seed, year, error))
            break
        if not text or "ГОД %d" % year not in text:
            problems.append("сид «%s»: срез на %d год вышел пустым"
                            % (seed, year))
            break
    return problems


def check_causes(world, seed: str) -> list:
    """Причинность: следы, зёрна и цепи событий.

    Проверяем то, что ломается незаметно: след, ссылающийся на событие,
    которого нет; зерно, взошедшее раньше, чем посеяно; причина, которая
    случилась позже следствия; цепь причин, замкнутая в кольцо.
    """
    from worldgen import history

    problems = []
    events = {event.id: event for event in world.events}

    for fact in world.facts.values():
        if fact.event_id and fact.event_id not in events:
            problems.append("сид «%s»: след «%s» ссылается на несуществующее "
                            "событие" % (seed, fact.kind))
            break
        if fact.closed and fact.closed < fact.year:
            problems.append("сид «%s»: след «%s» закрыт раньше, чем появился"
                            % (seed, fact.kind))
            break
        if fact.holder_id and not (fact.holder_id in world.polities
                                   or fact.holder_id in world.regions
                                   or fact.holder_id in world.settlements
                                   or fact.holder_id in world.figures
                                   or fact.holder_id in RACE_IDS):
            problems.append("сид «%s»: след «%s» принадлежит неизвестно кому"
                            % (seed, fact.kind))
            break

    for item in world.seeds.values():
        if item.due < item.born:
            problems.append("сид «%s»: зерно «%s» созревает раньше, чем "
                            "посеяно" % (seed, item.kind))
            break
        if item.state == "сбылось" and item.result_id \
                and item.result_id not in events:
            problems.append("сид «%s»: зерно «%s» взошло в несуществующее "
                            "событие" % (seed, item.kind))
            break
        if item.settled and item.settled < item.born:
            problems.append("сид «%s»: зерно «%s» разрешилось раньше, чем "
                            "посеяно" % (seed, item.kind))
            break
        if item.state != "ждёт" and not history.known_seed(item.kind):
            problems.append("сид «%s»: у зерна «%s» нет обработчика"
                            % (seed, item.kind))
            break

    deep = 0
    for event in world.events:
        for parent_id in event.causes:
            parent = events.get(parent_id)
            if parent is None:
                problems.append("сид «%s»: событие «%s» ссылается на "
                                "несуществующую причину" % (seed, event.title))
                break
            if parent.date.ordinal > event.date.ordinal:
                problems.append("сид «%s»: причина события «%s» случилась "
                                "позже него" % (seed, event.title))
                break
        else:
            deep = max(deep, history.depth_of(world, event, 30))
            continue
        break
    if deep >= 29:
        problems.append("сид «%s»: цепь причин не кончается — похоже на "
                        "кольцо" % seed)
    return problems


def check_people_memory(world, seed: str) -> list:
    """Память людей и связи: не помнит ли кто того, чего не было."""
    problems = []
    events = {event.id: event for event in world.events}

    for memory in world.memories.values():
        figure = world.figures.get(memory.figure_id)
        if figure is None:
            problems.append("сид «%s»: воспоминание принадлежит "
                            "несуществующему человеку" % seed)
            break
        if figure.birth is not None and memory.year < figure.birth.year:
            problems.append("сид «%s»: %s помнит то, что было до его "
                            "рождения" % (seed, figure.plain_name))
            break
        if figure.death is not None and memory.year > figure.death.year:
            problems.append("сид «%s»: %s помнит то, что случилось после "
                            "его смерти" % (seed, figure.plain_name))
            break
        if memory.event_id and memory.event_id not in events:
            problems.append("сид «%s»: воспоминание ссылается на событие, "
                            "которого не было" % seed)
            break
        if memory.about_id and not (memory.about_id in world.figures
                                    or memory.about_id in world.polities
                                    or memory.about_id in RACE_IDS):
            problems.append("сид «%s»: воспоминание о том, кого нет" % seed)
            break

    for bond in world.bonds.values():
        if bond.a_id not in world.figures or bond.b_id not in world.figures:
            problems.append("сид «%s»: связь с несуществующим человеком" % seed)
            break
        if bond.a_id == bond.b_id:
            problems.append("сид «%s»: человек связан сам с собой" % seed)
            break
        if bond.ended and bond.ended < bond.since:
            problems.append("сид «%s»: связь оборвалась раньше, чем "
                            "завязалась" % seed)
            break
    return problems


def check_migrations(world, seed: str) -> list:
    """Переселения: не ушли ли люди в никуда и не пришли ли ниоткуда."""
    problems = []
    events = {event.id: event for event in world.events}
    for item in world.migrations.values():
        if item.from_region and item.from_region not in world.regions:
            problems.append("сид «%s»: переселение из несуществующей земли"
                            % seed)
            break
        if item.to_region and item.to_region not in world.regions:
            problems.append("сид «%s»: переселение в несуществующую землю"
                            % seed)
            break
        target = world.regions.get(item.to_region)
        # Земля могла утонуть и после того, как в неё пришли: беда
        # переселению не помеха, если она случилась позже.
        if target is not None and target.drowned \
                and target.drowned_year and item.year > target.drowned_year:
            problems.append("сид «%s»: переселение в землю, ушедшую под воду"
                            % seed)
            break
        if item.souls <= 0:
            problems.append("сид «%s»: переселение без единой души" % seed)
            break
        if item.year < 1 or item.year > world.total_years:
            problems.append("сид «%s»: переселение вне времени мира" % seed)
            break
        if item.event_id and item.event_id not in events:
            problems.append("сид «%s»: переселение без записи в летописи"
                            % seed)
            break
        if item.to_polity and item.to_polity not in world.polities:
            problems.append("сид «%s»: переселение в несуществующую державу"
                            % seed)
            break
        if item.race_id not in RACE_IDS:
            problems.append("сид «%s»: переселение народа, которого нет"
                            % seed)
            break
    return problems


def check_strifes(world, seed: str) -> list:
    """Смуты и заговоры: не воюет ли держава с тем, кого нет."""
    problems = []
    for item in world.strifes.values():
        if item.polity_id not in world.polities:
            problems.append("сид «%s»: смута в несуществующей державе" % seed)
            break
        if item.end is not None and item.end.ordinal < item.start.ordinal:
            problems.append("сид «%s»: смута «%s» кончилась раньше, чем "
                            "началась" % (seed, item.name))
            break
        if item.status != ONGOING_STATE and not item.outcome:
            problems.append("сид «%s»: у смуты «%s» нет исхода"
                            % (seed, item.name))
            break
        both = set(item.crown_cities) & set(item.rebel_cities)
        if both:
            problems.append("сид «%s»: город смуты «%s» держат обе стороны "
                            "разом" % (seed, item.name))
            break
        if item.rebel_id and item.rebel_id not in world.figures:
            problems.append("сид «%s»: смуту «%s» поднял тот, кого нет"
                            % (seed, item.name))
            break
        if item.heir_polity_id and item.heir_polity_id not in world.polities:
            problems.append("сид «%s»: из смуты «%s» вышла несуществующая "
                            "держава" % (seed, item.name))
            break

    for item in world.cabals.values():
        if item.polity_id not in world.polities:
            problems.append("сид «%s»: заговор в несуществующей державе" % seed)
            break
        if item.leader_id not in world.figures:
            problems.append("сид «%s»: заговор ведёт тот, кого нет" % seed)
            break
        if item.target_id and item.target_id not in world.figures:
            problems.append("сид «%s»: заговор против того, кого нет" % seed)
            break
        if item.ended and item.ended < item.born:
            problems.append("сид «%s»: заговор кончился раньше, чем начался"
                            % seed)
            break
        if item.ended and not item.outcome:
            problems.append("сид «%s»: у кончившегося заговора нет исхода"
                            % seed)
            break
        if any(member not in world.figures for member in item.members):
            problems.append("сид «%s»: в заговоре числится тот, кого нет"
                            % seed)
            break
    return problems


def check_things(world, seed: str) -> list:
    """Вещи, места и чудовища: всё ли на месте и ни у кого ли нет лишнего.

    Главное правило блока: подземелье берёт факты из истории, а не наоборот.
    Значит, у каждой вещи должна быть цепочка рук, у каждого места — то,
    от чего оно осталось, а у каждого чудовища — год, когда его убили,
    если оно мертво.
    """
    problems = []

    names = [item.name for item in world.artifacts.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена вещей повторяются" % seed)

    for artifact in world.artifacts.values():
        if artifact.made is None:
            problems.append("сид «%s»: вещь «%s» никогда не делали"
                            % (seed, artifact.name))
            break
        if artifact.gender not in ("m", "f", "n", "p"):
            problems.append("сид «%s»: у вещи «%s» нет рода"
                            % (seed, artifact.name))
            break
        if artifact.owner_id and artifact.owner_id not in world.figures:
            problems.append("сид «%s»: вещь «%s» у несуществующего владельца"
                            % (seed, artifact.name))
            break
        if artifact.site_id and artifact.site_id not in world.sites:
            problems.append("сид «%s»: вещь «%s» лежит в несуществующем месте"
                            % (seed, artifact.name))
            break
        if not artifact.trail:
            problems.append("сид «%s»: у вещи «%s» пустая цепочка рук"
                            % (seed, artifact.name))
            break
        years = [int(step.get("year", 0)) for step in artifact.trail]
        if any(years[i] > years[i + 1] for i in range(len(years) - 1)):
            problems.append("сид «%s»: цепочка рук вещи «%s» идёт вспять"
                            % (seed, artifact.name))
            break
        if years and years[0] < artifact.made.year:
            problems.append("сид «%s»: вещь «%s» сменила владельца до ковки"
                            % (seed, artifact.name))
            break

    names = [site.name for site in world.sites.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена мест повторяются" % seed)

    for site in world.sites.values():
        if site.region_id and site.region_id not in world.regions:
            problems.append("сид «%s»: место «%s» лежит вне земель"
                            % (seed, site.name))
            break
        if not (1 <= site.depth <= 5):
            problems.append("сид «%s»: у места «%s» немыслимая глубина"
                            % (seed, site.name))
            break
        if site.riches < 0:
            problems.append("сид «%s»: у места «%s» отрицательное добро"
                            % (seed, site.name))
            break
        if site.opened is not None and site.opened.ordinal < site.created.ordinal:
            problems.append("сид «%s»: место «%s» вскрыли до того, как оно "
                            "появилось" % (seed, site.name))
            break
        if site.figure_id and site.figure_id not in world.figures:
            problems.append("сид «%s»: в месте «%s» лежит неизвестно кто"
                            % (seed, site.name))
            break
        for artifact_id in site.artifact_ids:
            if artifact_id not in world.artifacts:
                problems.append("сид «%s»: в месте «%s» лежит несуществующая вещь"
                                % (seed, site.name))
                break
        if not (site.figure_id or site.settlement_id or site.battle_id
                or site.calamity_id or site.monster_id or site.polity_id
                or site.artifact_ids or site.story):
            problems.append("сид «%s»: место «%s» появилось ниоткуда"
                            % (seed, site.name))
            break

    names = [monster.name for monster in world.monsters.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена чудовищ повторяются" % seed)

    for monster in world.monsters.values():
        if monster.status != "жив" and monster.ended is None:
            problems.append("сид «%s»: чудовище «%s» мертво без года смерти"
                            % (seed, monster.name))
            break
        if monster.ended is not None and monster.ended.ordinal < monster.born.ordinal:
            problems.append("сид «%s»: чудовище «%s» умерло до рождения"
                            % (seed, monster.name))
            break
        if monster.slayer_id and monster.slayer_id not in world.figures:
            problems.append("сид «%s»: чудовище «%s» убил никто"
                            % (seed, monster.name))
            break
        if monster.hoard < 0 or monster.kills < 0:
            problems.append("сид «%s»: у чудовища «%s» отрицательный счёт"
                            % (seed, monster.name))
            break
        if monster.site_id and monster.site_id not in world.sites:
            problems.append("сид «%s»: у чудовища «%s» логово в пустоте"
                            % (seed, monster.name))
            break

    return problems


def check_lore(world, seed: str) -> list:
    """Ремёсла, своды, легенды и законы: связность и здравый смысл."""
    problems = []

    for discovery in world.discoveries.values():
        if discovery.polity_id and discovery.polity_id not in world.polities:
            problems.append("сид «%s»: открытие «%s» сделала несуществующая страна"
                            % (seed, discovery.name))
            break
        for polity_id in discovery.known_by:
            if polity_id not in world.polities:
                problems.append("сид «%s»: открытие «%s» перенял никто"
                                % (seed, discovery.name))
                break
        if len(discovery.known_by) != len(set(discovery.known_by)):
            problems.append("сид «%s»: открытие «%s» переняли дважды"
                            % (seed, discovery.name))
            break
        if discovery.polity_id and discovery.polity_id not in discovery.known_by:
            problems.append("сид «%s»: страна забыла своё же открытие «%s»"
                            % (seed, discovery.name))
            break

    for polity in world.polities.values():
        if len(polity.known) != len(set(polity.known)):
            problems.append("сид «%s»: страна %s знает одно ремесло дважды"
                            % (seed, polity.name))
            break
        if len(polity.reforms) != len(set(polity.reforms)):
            problems.append("сид «%s»: страна %s провела одну реформу дважды"
                            % (seed, polity.name))
            break

    for codex in world.codices.values():
        if codex.seat_id and codex.seat_id not in world.settlements:
            problems.append("сид «%s»: свод «%s» пишут в несуществующем городе"
                            % (seed, codex.name))
            break
        if not (0.0 <= codex.accuracy <= 1.0):
            problems.append("сид «%s»: у свода «%s» немыслимая точность"
                            % (seed, codex.name))
            break
        if codex.ended is not None and codex.ended.ordinal < codex.started.ordinal:
            problems.append("сид «%s»: свод «%s» закрыли до того, как начали"
                            % (seed, codex.name))
            break
        if codex.status != "ведётся" and codex.ended is None:
            problems.append("сид «%s»: свод «%s» оборван без года"
                            % (seed, codex.name))
            break
        years = [int(entry.get("year", 0)) for entry in codex.entries]
        if any(years[i] > years[i + 1] for i in range(len(years) - 1)):
            problems.append("сид «%s»: записи свода «%s» идут вспять"
                            % (seed, codex.name))
            break
        if years and years[0] < codex.started.year:
            problems.append("сид «%s»: в своде «%s» есть запись до его начала"
                            % (seed, codex.name))
            break
        seen = set()
        for keeper in codex.keepers:
            figure_id = keeper.get("figure")
            if figure_id and figure_id not in world.figures:
                problems.append("сид «%s»: свод «%s» ведёт неизвестно кто"
                                % (seed, codex.name))
                break
            if figure_id in seen:
                problems.append("сид «%s»: летописец свода «%s» садится за него "
                                "дважды" % (seed, codex.name))
                break
            seen.add(figure_id)

    names = [legend.name for legend in world.legends.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена легенд повторяются" % seed)

    for legend in world.legends.values():
        if legend.tellings < 1:
            problems.append("сид «%s»: легенду «%s» никто не рассказывал"
                            % (seed, legend.name))
            break
        if not legend.truth:
            problems.append("сид «%s»: у легенды «%s» нет правды под ней"
                            % (seed, legend.name))
            break
        shift_years = [int(shift.get("year", 0)) for shift in legend.shifts]
        if any(year < legend.born.year for year in shift_years):
            problems.append("сид «%s»: легенда «%s» изменилась до рождения"
                            % (seed, legend.name))
            break

    for law in world.laws.values():
        if law.polity_id and law.polity_id not in world.polities:
            problems.append("сид «%s»: закон «%s» завела несуществующая страна"
                            % (seed, law.name))
            break
        if law.polity_id and law.polity_id not in law.copied_by:
            problems.append("сид «%s»: страна забыла свой же закон «%s»"
                            % (seed, law.name))
            break
        if len(law.copied_by) != len(set(law.copied_by)):
            problems.append("сид «%s»: закон «%s» переняли дважды"
                            % (seed, law.name))
            break
        if law.ruler_id and law.ruler_id not in world.figures:
            problems.append("сид «%s»: закон «%s» завёл никто"
                            % (seed, law.name))
            break

    return problems


def check_upheavals(world, seed: str) -> list:
    """Великие бедствия: что они сделали с картой — и осталось ли согласовано."""
    from worldgen.systems import upheaval as upheaval_mod

    problems = []

    for region in world.regions.values():
        if not region.drowned:
            continue
        if region.capacity or region.habitat:
            problems.append("сид «%s»: затопленная земля %s всё ещё кормит"
                            % (seed, region.name))
            break
        for settlement_id in world.active_settlements:
            if world.settlements[settlement_id].region_id == region.id:
                problems.append("сид «%s»: город стоит в затопленной земле %s"
                                % (seed, region.name))
                break
        for tribe_id in world.active_tribes:
            if world.tribes[tribe_id].region_id == region.id:
                problems.append("сид «%s»: племя живёт в затопленной земле %s"
                                % (seed, region.name))
                break

    for region in world.regions.values():
        for other_id in region.neighbors:
            other = world.regions.get(other_id)
            if other is None:
                problems.append("сид «%s»: земля %s соседит с пустотой"
                                % (seed, region.name))
                break
            if region.id not in other.neighbors:
                problems.append("сид «%s»: соседство %s и %s держится в одну "
                                "сторону" % (seed, region.name, other.name))
                break
        for other_id in region.sea_links:
            other = world.regions.get(other_id)
            if other is None:
                problems.append("сид «%s»: у земли %s морской путь в пустоту"
                                % (seed, region.name))
                break
            if other_id in region.neighbors:
                problems.append("сид «%s»: %s и %s соседят и по суше, и по морю "
                                "разом" % (seed, region.name, other.name))
                break

    gone = world.notes.get(upheaval_mod.GONE_NOTE) or {}
    alive = world.population_by_race()
    for race_id in gone:
        if alive.get(race_id):
            problems.append("сид «%s»: вымерший народ «%s» всё ещё жив"
                            % (seed, race_id))
            break

    great = [item for item in world.calamities.values()
             if item.key in upheaval_mod.GREAT]
    if len(great) > 8:
        problems.append("сид «%s»: великих бедствий %d — это уже погода, "
                        "а не конец света" % (seed, len(great)))
    for calamity in great:
        if calamity.key == "deep_waking" and not calamity.parent_id:
            problems.append("сид «%s»: «%s» поднялось ниоткуда, а должно было "
                            "быть осколком прошлого" % (seed, calamity.name))
            break

    peak = int(world.notes.get(upheaval_mod.PEAK_NOTE) or 0)
    if peak and world.world_population() * 200 < peak:
        problems.append("сид «%s»: мир опустел — от лучшего века осталась "
                        "двухсотая доля" % seed)

    return problems


def check_faiths(world, seed: str) -> list:
    """Проверяет устройство веры."""
    problems = []

    names = [faith.name for faith in world.faiths.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена вер повторяются" % seed)

    for deity in world.deities.values():
        if deity.faith_id and deity.faith_id not in world.faiths:
            problems.append("сид «%s»: бог %s принадлежит несуществующей вере"
                            % (seed, deity.given_name))
            break
        if not (1 <= deity.festival_month <= 12 and 1 <= deity.festival_day <= 30):
            problems.append("сид «%s»: у бога %s праздник вне календаря"
                            % (seed, deity.given_name))
            break
        if not (-3 <= deity.alignment <= 3):
            problems.append("сид «%s»: у бога %s немыслимое мировоззрение"
                            % (seed, deity.given_name))
            break

    for faith in world.faiths.values():
        for deity_id in faith.deity_ids:
            if deity_id not in world.deities:
                problems.append("сид «%s»: у веры «%s» потерян бог"
                                % (seed, faith.name))
                break
        if faith.parent_id and faith.parent_id not in world.faiths:
            problems.append("сид «%s»: у ереси «%s» нет родительской веры"
                            % (seed, faith.name))
            break

    for settlement in world.settlements.values():
        if settlement.faith_id and settlement.faith_id not in world.faiths:
            problems.append("сид «%s»: город %s верит в несуществующее"
                            % (seed, settlement.name))
            break

    for temple in world.temples.values():
        if temple.faith_id not in world.faiths:
            problems.append("сид «%s»: храм «%s» без веры" % (seed, temple.name))
            break

    return problems


def check_catalogues() -> list:
    """Сходятся ли каталоги живой беды между собой.

    Мир тут не нужен: это проверка договора. Ответ, которого правитель
    «хочет», должен ссылаться на настоящую черту нрава; задержка фронта —
    на настоящее название земли; дело людей и забытое умение — на
    настоящий род уязвимости. Ссылка в пустоту не ломает генератор — она
    тише: такая запись просто не срабатывает ни разу, и целый кусок
    каталога лежит мёртвым.
    """
    from worldgen import disaster as dis
    from worldgen import catastrophe as cat
    from worldgen import races as races_mod
    from worldgen import rulers as rulers_mod

    problems = []
    keys = {spec.key for spec in cat.CATALOG}
    traits = {pair[0] for pair in (list(rulers_mod.TRAITS_GOOD)
                                   + list(rulers_mod.TRAITS_BAD)
                                   + list(rulers_mod.TRAITS_NEUTRAL))}
    lands = set(races_mod.TERRAINS)
    vulns = set(dis.VULNERABILITIES)

    def miss(what, rows, known):
        bad = sorted(set(rows) - set(known))
        if bad:
            problems.append("каталог беды: %s — нет такого: %s"
                            % (what, ", ".join(bad)))

    miss("ключи бед у шрамов",
         [key for item in dis.SCARS for key in item.keys], keys)
    miss("ключи бед у утрат",
         [key for item in dis.LOST_LORE for key in item.keys], keys)
    miss("ключи бед у знаков",
         [key for item in dis.OMENS for key in item.keys], keys)
    miss("ключи бед в цепях",
         [item.parent for item in dis.CHAINS]
         + [item.child for item in dis.CHAINS], keys)
    miss("черты нрава в ответах власти",
         [want for item in dis.RESPONSES for want in item.wants], traits)
    miss("земли в задержках фронта",
         [land for row in dis.HOLD_TERRAINS.values() for land in row], lands)
    miss("род уязвимости у дел людей", list(dis.WORKS.values()), vulns)
    miss("род уязвимости у утрат",
         [item.hurts for item in dis.LOST_LORE if item.hurts], vulns)
    miss("семьи бед у фаз", list(dis.PHASES), set(cat.KIND_NAMES))
    miss("что держит фронт",
         [item.needs for item in dis.HOLDS if item.needs],
         set(dis.HOLD_TERRAINS) | {"крепость"})

    # Каталог субъектов истории: ссылка в пустоту здесь так же тиха —
    # целый род существ просто никогда не получит ни цели, ни конца.
    from worldgen import subject as sub
    from worldgen.systems import subject as sub_sys

    wishes = {wish for wish, _ in sub.WISHES}
    miss("роды у происхождения", list(sub.ORIGIN_BY_KIND), set(sub.KINDS))
    miss("происхождение у родов",
         [name for rows in sub.ORIGIN_BY_KIND.values() for name, _ in rows],
         set(sub.ORIGINS))
    miss("роды у концов", list(sub.END_BY_KIND), set(sub.KINDS))
    miss("концы у родов",
         [name for rows in sub.END_BY_KIND.values() for name, _ in rows],
         set(sub.ENDS))
    miss("концы в переводе в положение", list(sub.END_TO_STATUS), set(sub.ENDS))
    miss("положения в переводе из концов",
         list(sub.END_TO_STATUS.values()), set(sub.STATUSES))
    miss("положения, из которых возвращаются", list(sub.CAN_RETURN),
         set(sub.STATUSES))
    miss("роды у целей",
         [kind for _, kinds in sub.WISHES for kind in kinds], set(sub.KINDS))
    miss("цели в переменах целей",
         [was for _, was, _ in sub.WISH_TURNS]
         + [now for _, _, now in sub.WISH_TURNS], wishes)
    miss("роды в вопросе о рождении", list(sub.ASKS_BIRTH), set(sub.KINDS))
    miss("роды наследия", list(sub.LEGACIES), set(sub.LEGACY_KINDS))
    miss("ступени памяти по весу", list(sub.RUNG_BY_LEVEL.values()),
         set(sub.RUNGS))
    miss("голоса в пересказах", list(sub.TELLER_TWISTS),
         {who for who, _ in sub.TELLERS})
    miss("роды, которые возвращаются", list(sub_sys.RETURN_KINDS),
         set(sub.KINDS))

    # Следы бед: ключ беды, семья и род должны существовать, иначе целый
    # вид следа никогда не выпадет.
    from worldgen import remains as rem
    miss("ключи бед у следов",
         [key for item in rem.TRACES for key in item.keys], keys)
    miss("семьи бед у следов",
         [name for item in rem.TRACES for name in item.families],
         set(cat.KIND_NAMES))
    miss("роды следов",
         [item.kind for item in rem.TRACES], set(rem.KINDS))
    miss("вопросы у следов",
         [name for item in rem.TRACES for name in item.answers],
         set(rem.QUESTIONS))
    miss("что нужно следу",
         [item.needs for item in rem.TRACES if item.needs],
         {"город", "держава", "войско", "вождь", "вера"})
    miss("роды в скорости ветшания", list(rem.DECAY_BY_KIND), set(rem.KINDS))
    if set(rem.KINDS) - set(rem.DECAY_BY_KIND):
        problems.append("каталог следов: у рода нет скорости ветшания")
    if len({item.key for item in rem.TRACES}) != len(rem.TRACES):
        problems.append("каталог следов: два следа с одним ключом")

    # Досягаемость: вид следа, который не выпадет ни одной беде, — мёртвая
    # запись. То же и у субъектов: род без происхождения, цели или конца
    # никогда не соберётся целиком.
    reachable, kinds_seen = set(), set()
    for spec in cat.CATALOG:
        for item, _ in rem.traces_for(spec.key, spec.kind,
                                      ("город", "держава", "войско",
                                       "вождь", "вера")):
            reachable.add(item.key)
            kinds_seen.add(item.kind)
    dead = sorted({item.key for item in rem.TRACES} - reachable)
    if dead:
        problems.append("каталог следов: ни одной беде не достанется — %s"
                        % ", ".join(dead[:4]))
    if set(rem.KINDS) - kinds_seen:
        problems.append("каталог следов: род следа недосягаем — %s"
                        % ", ".join(sorted(set(rem.KINDS) - kinds_seen)))

    for kind in sub.KINDS:
        if not sub.ORIGIN_BY_KIND.get(kind):
            problems.append("каталог субъектов: у рода «%s» нет появления"
                            % kind)
        if not sub.END_BY_KIND.get(kind):
            problems.append("каталог субъектов: у рода «%s» нет конца" % kind)
        if kind != sub.PEOPLE and not [one for one, kinds in sub.WISHES
                                       if kind in kinds]:
            problems.append("каталог субъектов: у рода «%s» нет цели" % kind)

    # Имена нашествий привязаны к роду пришедших: ссылка на несуществующий
    # род сделала бы имя общим, и рой снова звался бы «Разбитой Короной».
    from worldgen import invasion as inv
    miss("роды у имён нашествий",
         [kind for pool in (inv.NAME_BY_MARK, inv.NAME_BY_SIGN,
                            inv.NAME_BY_TOKEN)
          for _, kinds in pool for kind in kinds],
         set(inv.KINDS))
    return problems


def parts() -> list:
    """Из каких частей состоит полная самопроверка.

    Разбивка нужна не для красоты. Проверка целиком идёт около полутора
    часов, а окружение, в котором её гоняют, перезапускается — и тогда
    полтора часа работы пропадают до последнего мира. Разбитая на части,
    она переживает перезапуск: сделанные миры отмечены, и следующий запуск
    начинает с того, где оборвалось.
    """
    rows = ["catalogues"]
    rows.extend("seed:%s" % seed for seed in SEEDS)
    rows.extend("map:%s" % seed for seed in MAP_SEEDS)
    rows.extend("own:%s" % seed for seed in FORGE_SEEDS)
    return rows


def main(only: str = "") -> int:
    failures = []

    if not only or only == "catalogues":
        failures.extend(check_catalogues())
    if only == "catalogues":
        return _report(failures)

    for seed in SEEDS:
        if only and only != "seed:%s" % seed:
            continue
        started = time.time()
        first = generate(Settings(seed=seed, years=10000))
        second = generate(Settings(seed=seed, years=10000))
        spent = time.time() - started

        if digest(first) != digest(second):
            failures.append("сид «%s»: две генерации разошлись" % seed)

        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        try:
            storage.save_world(first, path)
            restored = storage.load_world(path)
        finally:
            os.remove(path)
        if digest(restored) != digest(first):
            failures.append("сид «%s»: мир изменился после сохранения" % seed)

        for settlement in first.settlements.values():
            race = get_race(settlement.race_id)
            if race.category in (BEASTFOLK, EVIL):
                failures.append("сид «%s»: %s построили город %s"
                                % (seed, race.name, settlement.name))
                break
        for polity in first.polities.values():
            race = get_race(polity.race_id)
            if race.category in (BEASTFOLK, EVIL):
                failures.append("сид «%s»: %s основали страну %s"
                                % (seed, race.name, polity.name))
                break
        for camp in first.camps.values():
            if not get_race(camp.race_id).is_evil:
                failures.append("сид «%s»: лагерь %s принадлежит не злой расе"
                                % (seed, camp.name))
                break

        events = first.events
        if any(events[i].date.ordinal > events[i + 1].date.ordinal
               for i in range(len(events) - 1)):
            failures.append("сид «%s»: события идут не по порядку" % seed)

        failures.extend(check_nobility(first, seed))
        failures.extend(check_wars(first, seed))
        failures.extend(check_politics(first, seed))
        failures.extend(check_calamities(first, seed))
        failures.extend(check_disasters(first, seed))
        failures.extend(check_after_end(first, seed))
        failures.extend(check_mortality(first, seed))
        failures.extend(check_ranks(first, seed))
        failures.extend(check_town_bread(first, seed))
        failures.extend(check_war_cost(first, seed))
        failures.extend(check_world_code(first, seed))
        failures.extend(check_invasions(first, seed))
        failures.extend(check_subjects(first, seed))
        failures.extend(check_traces(first, seed))
        failures.extend(check_year_slices(first, seed))
        failures.extend(check_faiths(first, seed))
        failures.extend(check_nations(first, seed))
        failures.extend(check_tongues(first, seed))
        failures.extend(check_embassies(first, seed))
        failures.extend(check_things(first, seed))
        failures.extend(check_causes(first, seed))
        failures.extend(check_people_memory(first, seed))
        failures.extend(check_migrations(first, seed))
        failures.extend(check_strifes(first, seed))
        failures.extend(check_lore(first, seed))
        failures.extend(check_upheavals(first, seed))
        failures.extend(check_tribes(first, seed))
        failures.extend(check_capitals(first, seed))
        failures.extend(check_souls(first, seed))
        failures.extend(check_tales(first, seed))
        failures.extend(check_lives(first, seed))
        failures.extend(check_stories(first, seed))
        failures.extend(check_towns(first, seed))
        failures.extend(check_holidays(first, seed))
        failures.extend(check_origin(first, seed))
        failures.extend(check_land(first, seed))
        failures.extend(check_gods(first, seed))
        failures.extend(check_renown(first, seed))

        print("  сид «%-12s» событий %5d | города %4d | страны %3d | роды %4d | "
              "бедствия %3d | боги %3d | веры %3d | население %8d (%.1f c)"
              % (seed, len(events), len(first.settlements), len(first.polities),
                 len(first.houses), len(first.calamities), len(first.deities),
                 len(first.faiths), first.world_population(), spent))

    if not os.path.exists(SAMPLE_MAP):
        print("\n  карта для примера не найдена — проверка по карте пропущена")
    else:
        from worldgen import worldmap as wm_mod
        sample = wm_mod.load(SAMPLE_MAP)
        print()
        for seed in MAP_SEEDS:
            if only and only != "map:%s" % seed:
                continue
            started = time.time()
            settings = Settings(seed=seed, years=10000, map_path=SAMPLE_MAP)
            first = generate(settings)
            second = generate(settings)
            spent = time.time() - started

            if digest(first) != digest(second):
                failures.append("карта, сид «%s»: две генерации разошлись" % seed)

            handle, path = tempfile.mkstemp(suffix=".json")
            os.close(handle)
            try:
                storage.save_world(first, path)
                restored = storage.load_world(path)
            finally:
                os.remove(path)
            if digest(restored) != digest(first):
                failures.append("карта, сид «%s»: мир изменился после сохранения" % seed)

            failures.extend(check_nobility(first, "карта/" + seed))
            failures.extend(check_wars(first, "карта/" + seed))
            failures.extend(check_politics(first, "карта/" + seed))
            failures.extend(check_calamities(first, "карта/" + seed))
            failures.extend(check_disasters(first, "карта/" + seed))
            failures.extend(check_after_end(first, "карта/" + seed))
            failures.extend(check_mortality(first, "карта/" + seed))
            failures.extend(check_ranks(first, "карта/" + seed))
            failures.extend(check_town_bread(first, "карта/" + seed))
            failures.extend(check_war_cost(first, "карта/" + seed))
            failures.extend(check_world_code(first, "карта/" + seed))
            failures.extend(check_invasions(first, "карта/" + seed))
            failures.extend(check_subjects(first, "карта/" + seed))
            failures.extend(check_traces(first, "карта/" + seed))
            failures.extend(check_year_slices(first, "карта/" + seed))
            failures.extend(check_faiths(first, "карта/" + seed))
            failures.extend(check_nations(first, "карта/" + seed))
            failures.extend(check_tongues(first, "карта/" + seed))
            failures.extend(check_embassies(first, "карта/" + seed))
            failures.extend(check_things(first, "карта/" + seed))
            failures.extend(check_causes(first, "карта/" + seed))
            failures.extend(check_people_memory(first, "карта/" + seed))
            failures.extend(check_migrations(first, "карта/" + seed))
            failures.extend(check_strifes(first, "карта/" + seed))
            failures.extend(check_lore(first, "карта/" + seed))
            failures.extend(check_upheavals(first, "карта/" + seed))
            failures.extend(check_tribes(first, "карта/" + seed))
            failures.extend(check_capitals(first, "карта/" + seed))
            failures.extend(check_souls(first, "карта/" + seed))
            failures.extend(check_tales(first, "карта/" + seed))
            failures.extend(check_lives(first, "карта/" + seed))
            failures.extend(check_stories(first, "карта/" + seed))
            failures.extend(check_towns(first, "карта/" + seed))
            failures.extend(check_holidays(first, "карта/" + seed))
            failures.extend(check_origin(first, "карта/" + seed))
            failures.extend(check_land(first, "карта/" + seed))
            failures.extend(check_gods(first, "карта/" + seed))
            failures.extend(check_renown(first, "карта/" + seed))
            failures.extend(check_map_world(first, sample, "карта/" + seed))

            print("  карта, сид «%-8s» земель %3d | города %4d | страны %3d | "
                  "кадров %3d | население %8d (%.1f c)"
                  % (seed, len(first.regions), len(first.settlements),
                     len(first.polities),
                     len(first.map_recorder.frames) if first.map_recorder else 0,
                     first.world_population(), spent))

    # Мир на карте, которую программа делает сама: Worldforge должен
    # держать те же проверки, что и карта из файла.
    print()
    for seed in FORGE_SEEDS:
        if only and only != "own:%s" % seed:
            continue
        started = time.time()
        settings = Settings(seed=seed, years=4000,
                            map_make={"seed": seed, "size": "small"})
        first = generate(settings)
        second = generate(settings)
        spent = time.time() - started

        if digest(first) != digest(second):
            failures.append("своя карта, сид «%s»: две генерации разошлись"
                            % seed)
        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        try:
            storage.save_world(first, path)
            restored = storage.load_world(path)
        finally:
            os.remove(path)
        if digest(restored) != digest(first):
            failures.append("своя карта, сид «%s»: мир изменился после "
                            "сохранения" % seed)
        for check in (check_nobility, check_wars, check_politics,
                      check_calamities, check_disasters, check_after_end,
                      check_mortality, check_ranks, check_war_cost,
                      check_town_bread,
                      check_world_code,
                      check_invasions, check_subjects,
                      check_traces, check_year_slices,
                      check_faiths, check_nations,
                      check_tongues, check_embassies, check_things,
                      check_causes, check_people_memory, check_migrations,
                      check_strifes, check_lore, check_upheavals,
                      check_tribes, check_capitals, check_souls,
                      check_tales,
                      check_lives, check_stories, check_towns,
                      check_holidays, check_origin, check_land,
                      check_gods, check_renown):
            failures.extend(check(first, "своя/" + seed))
        from worldgen import worldforge
        failures.extend(check_map_world(
            first, worldforge.forge(seed, size="small"), "своя/" + seed))
        print("  своя карта, сид «%-8s» земель %3d | города %4d | страны %3d "
              "| население %8d (%.1f c)"
              % (seed, len(first.regions), len(first.settlements),
                 len(first.polities), first.world_population(), spent))

    return _report(failures)


def _report(failures) -> int:
    if failures:
        print("\nОШИБКИ:")
        for line in failures:
            print("  -", line)
        return 1
    print("\nВсё в порядке.")
    return 0


def _usage() -> int:
    print("Самопроверка целиком:")
    print("    python3 tools/selfcheck.py")
    print()
    print("Или по частям — тогда перезапуск теряет одну часть, а не всё:")
    print("    python3 tools/selfcheck.py --only <часть>")
    print()
    print("Части:")
    for name in parts():
        print("    %s" % name)
    print()
    print("    python3 tools/selfcheck.py --parts   — только их перечень")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        sys.exit(_usage())
    if "--parts" in argv:
        for name in parts():
            print(name)
        sys.exit(0)
    chosen = ""
    if "--only" in argv:
        index = argv.index("--only")
        if index + 1 >= len(argv):
            print("После --only нужна часть. Их перечень: --parts")
            sys.exit(2)
        chosen = argv[index + 1]
        if chosen not in parts():
            print("Нет такой части: %s" % chosen)
            print("Перечень: %s" % ", ".join(parts()))
            sys.exit(2)
    sys.exit(main(chosen))
