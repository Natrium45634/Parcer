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
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import chronicle, storage                       # noqa: E402
from worldgen.engine import Settings, generate                # noqa: E402
from worldgen.models import ACTIVE                             # noqa: E402
from worldgen.races import BEASTFOLK, EVIL, get_race          # noqa: E402

SEEDS = ("Ясень-7", "Первый мир", "проверка", "1234")
MAP_SEEDS = ("карта-1", "карта-2")
SAMPLE_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "maps", "aurora-7.world")


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

    # Один труд — один раз за всю историю мира.
    works = [note for figure in world.figures.values() for note in figure.notes
             if note.startswith("труд: ")]
    if len(works) != len(set(works)):
        problems.append("сид «%s»: труды учёных повторяются" % seed)
    return problems


def check_map_world(world, link_regions, seed: str) -> list:
    """Проверяет мир, построенный по карте."""
    from worldgen import worldmap as wm

    problems = []
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


def main() -> int:
    failures = []

    for seed in SEEDS:
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
        failures.extend(check_calamities(first, seed))
        failures.extend(check_faiths(first, seed))
        failures.extend(check_nations(first, seed))

        print("  сид «%-12s» событий %5d | города %4d | страны %3d | роды %4d | "
              "бедствия %3d | боги %3d | веры %3d | население %8d (%.1f c)"
              % (seed, len(events), len(first.settlements), len(first.polities),
                 len(first.houses), len(first.calamities), len(first.deities),
                 len(first.faiths), first.world_population(), spent))

    if not os.path.exists(SAMPLE_MAP):
        print("\n  карта для примера не найдена — проверка по карте пропущена")
    else:
        print()
        for seed in MAP_SEEDS:
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
            failures.extend(check_calamities(first, "карта/" + seed))
            failures.extend(check_faiths(first, "карта/" + seed))
            failures.extend(check_nations(first, "карта/" + seed))
            failures.extend(check_map_world(first, None, "карта/" + seed))

            print("  карта, сид «%-8s» земель %3d | города %4d | страны %3d | "
                  "кадров %3d | население %8d (%.1f c)"
                  % (seed, len(first.regions), len(first.settlements),
                     len(first.polities),
                     len(first.map_recorder.frames) if first.map_recorder else 0,
                     first.world_population(), spent))

    if failures:
        print("\nОШИБКИ:")
        for line in failures:
            print("  -", line)
        return 1
    print("\nВсё в порядке.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
