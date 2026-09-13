# -*- coding: utf-8 -*-
"""Быстрая самопроверка движка.

Запуск:  python tools/selfcheck.py

Проверяет три вещи, которые легко сломать при добавлении новых блоков:

1. детерминированность — один сид даёт побайтово одну и ту же летопись;
2. сохранение и загрузка мира не теряют ни одной записи;
3. правила рас соблюдаются: зверолюды живут племенами, злые расы не
   строят государств и городов;
4. устройство знати: фамилии только у знатных, роды только у тех рас,
   у которых знать бывает, правления идут по порядку.
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
from worldgen.races import BEASTFOLK, EVIL, get_race          # noqa: E402

SEEDS = ("Ясень-7", "Первый мир", "проверка", "1234")


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

        print("  сид «%-12s»  событий %5d  городов %4d  стран %3d  родов %4d  "
              "правлений %4d  (%.1f c на два мира)"
              % (seed, len(events), len(first.settlements), len(first.polities),
                 len(first.houses), len(first.reigns), spent))

    if failures:
        print("\nОШИБКИ:")
        for line in failures:
            print("  -", line)
        return 1
    print("\nВсё в порядке.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
