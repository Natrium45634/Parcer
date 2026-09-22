#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка картогенератора с эталонной картой.

`maps/aurora-7.world` сделана исходным TECTONIC WORLDFORGE: сид
«aurora-7», размер «малая», ползунки по умолчанию. Перенос генератора на
Python обязан давать ровно её — гекс в гекс, слой в слой, вместе со всем
JSON-хвостом.

Эта проверка и есть договор о точности переноса. Если она упала, значит
в `worldgen/worldforge/` что-то разошлось с оригиналом: смотреть надо на
порядок обращений к ГСЧ и на арифметику, а не «подправить, чтобы
сошлось».

    python3 tools/mapcheck.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import worldmap                                    # noqa: E402
from worldgen.worldforge import export                           # noqa: E402
from worldgen.worldforge.core import Config, generate            # noqa: E402

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "maps", "aurora-7.world")
SEED, SIZE = "aurora-7", "small"

LAYER_NAMES = {
    0: "высоты", 1: "температура", 2: "влага", 3: "биомы", 4: "флаги",
    5: "плодородие", 6: "плиты", 7: "напряжение", 8: "близость вулкана",
    9: "сток", 10: "водосбор", 11: "насыщенность", 12: "живность",
    13: "маска бедствий", 14: "риск", 15: "магия", 16: "водоносность",
    17: "дикость", 20: "земли", 21: "водоёмы", 22: "хребты",
    23: "речные бассейны",
}


def main() -> int:
    if not os.path.exists(SAMPLE):
        print("Эталонной карты нет: %s" % SAMPLE)
        return 2
    reference = worldmap.load(SAMPLE)

    began = time.time()
    world = generate(Config(seed=SEED, size=SIZE))
    mine = export.worldmap_of(world, with_minerals=True)
    spent = time.time() - began

    problems = []
    print("сверка с %s (%d×%d), собрано за %.1f c"
          % (os.path.basename(SAMPLE), reference.width, reference.height,
             spent))

    if (mine.width, mine.height) != (reference.width, reference.height):
        problems.append("размер карты разошёлся")
    if mine.sea != reference.sea:
        problems.append("уровень моря разошёлся: %r против %r"
                        % (mine.sea, reference.sea))
    if mine.seed_value != reference.seed_value:
        problems.append("числовой сид разошёлся")

    for layer_id in sorted(reference.layers):
        theirs = reference.layers[layer_id]
        ours = mine.layers.get(layer_id)
        name = LAYER_NAMES.get(layer_id, "слой %d" % layer_id)
        if ours is None:
            problems.append("нет слоя %d (%s)" % (layer_id, name))
            continue
        bad = sum(1 for a, b in zip(ours, theirs) if a != b)
        if bad:
            problems.append("слой %d (%s): расхождений %d из %d"
                            % (layer_id, name, bad, len(theirs)))
    extra = sorted(set(mine.layers) - set(reference.layers))
    if extra:
        problems.append("лишние слои: %s" % ", ".join(map(str, extra)))

    for key in sorted(reference.tail):
        if mine.tail.get(key) != reference.tail[key]:
            problems.append("хвост «%s» разошёлся" % key)
    extra = sorted(set(mine.tail) - set(reference.tail))
    if extra:
        problems.append("лишние разделы хвоста: %s" % ", ".join(extra))

    if problems:
        print("\nРАСХОЖДЕНИЯ:")
        for line in problems:
            print("  -", line)
        return 1
    print("  слоёв сверено: %d, разделов хвоста: %d"
          % (len(reference.layers), len(reference.tail)))
    print("\nКарта совпадает с эталоном бит в бит.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
