# -*- coding: utf-8 -*-
"""Стандартный тест генератора: создать мир и разобрать его.

Один прогон отвечает на два вопроса: интересно ли читать этот мир и нет
ли в нём поломок. Сам разбор живёт не здесь, а в движке
(`worldgen/review.py`) — потому что тот же разбор человек запускает
кнопкой из окна программы, по готовому миру, и два разбора на один
вопрос неизбежно разошлись бы. Здесь остаётся работа инструмента:
прочитать ключи, создать мир и напечатать разбор.

Запуск:

    python tools/worldtest.py                        случайный сид и даты
    python tools/worldtest.py --seed Ясень-7         свой сид
    python tools/worldtest.py --map maps/aurora-7.world
    python tools/worldtest.py --dates 500,2000,5000,7000,9500
    python tools/worldtest.py --spin 0               даты от сида, те же
    python tools/worldtest.py --years 4000 --out отчёт.txt
    python tools/worldtest.py --quiet                только разбор, без срезов

Выход не нулевой, если разбор нашёл хотя бы одну серьёзную аномалию —
так тест годится и для быстрой проверки после правок.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import review                                      # noqa: E402
from worldgen.engine import Settings, generate                   # noqa: E402
from worldgen.rng import random_seed_text                        # noqa: E402


def main(argv) -> int:
    options = {"--seed": "", "--years": "10000", "--map": "", "--dates": "",
               "--out": "", "--regions": "18", "--spin": ""}
    flags = set()
    index = 0
    while index < len(argv):
        key = argv[index]
        if key in options and index + 1 < len(argv):
            options[key] = argv[index + 1]
            index += 2
        else:
            flags.add(key)
            index += 1

    seed = options["--seed"] or random_seed_text()
    years = int(float(options["--years"]))
    settings = Settings(seed=seed, years=years, map_path=options["--map"],
                        regions=int(float(options["--regions"])))
    world = generate(settings)

    # Даты: названные прямо, от сида мира или случайные. По умолчанию
    # случайные — за много прогонов тест так обходит все века; но тот же
    # разбор с «--spin 0» повторяется в точности, и его можно сравнить.
    if options["--dates"]:
        dates = [int(x) for x in options["--dates"].split(",")]
    else:
        spin = (int(options["--spin"]) if options["--spin"]
                else review.random_spin())
        dates = review.dates_for(world, spin)

    parts = [key for key in review.ALL_PARTS
             if key != review.DATES or "--quiet" not in flags]
    findings = review.audit(world)
    text = review.report(world, parts, dates, findings=findings)
    serious = review.serious_count(findings)

    if options["--out"]:
        with open(options["--out"], "w", encoding="utf-8") as handle:
            handle.write(text)
        print("Записано в %s (серьёзных аномалий: %d)"
              % (options["--out"], serious))
    else:
        print(text)
    return 1 if serious else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
