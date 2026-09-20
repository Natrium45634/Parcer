# -*- coding: utf-8 -*-
"""Проверка разнообразия: похожи ли миры друг на друга.

Генератор делает миры по сиду, и главная его обязанность — чтобы два
разных сида дали две разные истории. Этот инструмент прогоняет несколько
миров подряд и отвечает на четыре вопроса:

**Не повторяются ли имена.** Сколько придуманных имён — земель, народов,
держав, богов, вещей, личностей — встречается больше чем в одном мире.
Одно и то же имя в двух мирах — не поломка (звуковые законы у расы одни),
но если таких имён много, кузница имён работает вхолостую.

**Не повторяются ли фразы.** Все тексты событий всех миров сводятся в
одну кучу и считается, сколько раз повторена самая частая фраза и какая
доля фраз уникальна. Здесь же видно шаблоны, которые выскакивают чаще
прочих.

**Разные ли миры по устройству.** Население, страны, войны, веры, языки,
бедствия, великие беды, вымершие народы — по каждому показателю разброс
от худшего мира к лучшему. Если разброс мал, миры на одно лицо.

**Нет ли зацикленности внутри мира.** История делится на три части, и
считается, насколько набор событий второй и третьей части повторяет
первую. Мир, у которого третья тысяча лет неотличима от первой, читать
неинтересно.

Запуск:

    python tools/variety.py                  шесть миров по 4000 лет
    python tools/variety.py --worlds 10 --years 6000
    python tools/variety.py --out отчёт.txt
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen.engine import Settings, generate            # noqa: E402
from worldgen.rng import Rng, make_seed_text              # noqa: E402

# Показатели, по которым сравниваются миры. Ключ -> как достать.
SHAPE = (
    ("душ на конец", lambda w: w.world_population()),
    ("в лучший век", lambda w: int(w.notes.get("людей в лучший век") or 0)),
    ("событий", lambda w: len(w.events)),
    ("племён", lambda w: len(w.tribes)),
    ("городов", lambda w: len(w.settlements)),
    ("держав", lambda w: len(w.polities)),
    ("войн", lambda w: len(w.wars)),
    ("сражений", lambda w: len(w.battles)),
    ("бедствий", lambda w: len(w.calamities)),
    ("великих бед", lambda w: _great(w)),
    ("тёмных веков", lambda w: len(w.dark_ages)),
    ("богов", lambda w: len(w.deities)),
    ("вер", lambda w: len(w.faiths)),
    ("языков", lambda w: len(w.tongues)),
    ("народов", lambda w: len(w.folks)),
    ("вещей", lambda w: len(w.artifacts)),
    ("мест", lambda w: len(w.sites)),
    ("чудовищ", lambda w: len(w.monsters)),
    ("сводов", lambda w: len(w.codices)),
    ("легенд", lambda w: len(w.legends)),
    ("реформ", lambda w: len(w.laws)),
    ("вымерло народов", lambda w: len(w.notes.get("народов больше нет") or {})),
)


def _great(world) -> int:
    from worldgen.systems.upheaval import GREAT
    return sum(1 for item in world.calamities.values() if item.key in GREAT)


def names_of(world) -> dict:
    """Все придуманные имена мира, разложенные по видам."""
    return {
        "земли": {item.name for item in world.regions.values()},
        "народы": {item.name for item in world.folks.values()},
        "племена": {item.name for item in world.tribes.values()},
        "города": {item.name for item in world.settlements.values()},
        "державы": {item.name for item in world.polities.values()},
        "боги": {item.given_name for item in world.deities.values()},
        "веры": {item.name for item in world.faiths.values()},
        "языки": {item.name for item in world.tongues.values()},
        "вещи": {item.name for item in world.artifacts.values()},
        "чудовища": {item.name for item in world.monsters.values()},
        "места": {item.name for item in world.sites.values()},
        "бедствия": {item.name for item in world.calamities.values()},
        "личности": {item.given_name for item in world.figures.values()},
    }


# Имена из текста выбрасываются: сравниваются сами фразы, а не то,
# кого в них зовут. Иначе всё уникально всегда и мерить нечего.
_NAME = re.compile(r"[А-ЯЁ][а-яё'’\-]+")
_NUM = re.compile(r"\d+")


def phrases(world) -> list:
    out = []
    for event in world.events:
        for piece in event.text.split(". "):
            piece = piece.strip()
            if len(piece) < 25:
                continue
            piece = _NAME.sub("_", piece)
            piece = _NUM.sub("#", piece)
            out.append(piece)
    return out


def loopiness(world) -> float:
    """Насколько поздняя история повторяет раннюю, 0…1.

    Считается по долям видов событий: если в первой трети истории те же
    виды и в тех же долях, что в последней, мир ходит по кругу.
    """
    events = [event for event in world.events if event.date.year > 0]
    if len(events) < 60:
        return 0.0
    third = len(events) // 3
    early = Counter(event.kind for event in events[:third])
    late = Counter(event.kind for event in events[-third:])
    keys = set(early) | set(late)
    early_total = max(1, sum(early.values()))
    late_total = max(1, sum(late.values()))
    # Пересечение долей: 1.0 — распределения совпали полностью.
    return sum(min(early[key] / early_total, late[key] / late_total)
               for key in keys)


def main(argv) -> int:
    options = {"--worlds": "6", "--years": "4000", "--out": "", "--tag": "разнообразие"}
    index = 0
    while index < len(argv):
        key = argv[index]
        if key in options and index + 1 < len(argv):
            options[key] = argv[index + 1]
            index += 2
        else:
            index += 1

    count = int(options["--worlds"])
    years = int(options["--years"])
    lines = []

    def out(line=""):
        lines.append(line)
        print(line)

    rng = Rng(options["--tag"])
    seeds, worlds = [], []
    out("#" * 78)
    out("ПРОВЕРКА РАЗНООБРАЗИЯ")
    out("  миров: %d, по %d лет" % (count, years))
    out("#" * 78)
    out("")

    digests = {}
    for _ in range(count):
        seed = make_seed_text(rng.randint(1, 10 ** 15))
        world = generate(Settings(seed=seed, years=years))
        seeds.append(seed)
        worlds.append(world)
        mark = "|".join("%s" % item.name for item in world.regions.values())
        if mark in digests:
            out("  !! сиды «%s» и «%s» дали один и тот же мир"
                % (digests[mark], seed))
        digests[mark] = seed
        out("  %-10s душ %9d | стран %3d | войн %3d | вер %2d | бед %3d"
            % (seed, world.world_population(), len(world.polities),
               len(world.wars), len(world.faiths), len(world.calamities)))
    out("")

    # --- имена --------------------------------------------------------
    out("=" * 78)
    out("ИМЕНА: сколько повторяется между мирами")
    out("=" * 78)
    for kind in names_of(worlds[0]):
        pool = Counter()
        for world in worlds:
            for name in names_of(world)[kind]:
                pool[name] += 1
        total = len(pool)
        shared = sum(1 for name, seen in pool.items() if seen > 1)
        if not total:
            continue
        worst = pool.most_common(1)[0]
        out("  %-10s имён %5d, в двух и более мирах %4d (%4.1f%%); чаще "
            "всего «%s» — в %d мирах"
            % (kind, total, shared, shared * 100.0 / total, worst[0], worst[1]))
    out("")

    # --- фразы --------------------------------------------------------
    out("=" * 78)
    out("ФРАЗЫ: повторы по всем мирам разом")
    out("=" * 78)
    pool = Counter()
    for world in worlds:
        pool.update(phrases(world))
    total = sum(pool.values())
    unique = len(pool)
    out("  всего фраз %d, различных %d (%.1f%%)"
        % (total, unique, unique * 100.0 / max(1, total)))
    out("  самые заезженные:")
    for phrase, seen in pool.most_common(6):
        out("    %5d x  %s" % (seen, phrase[:90]))
    out("")

    # --- устройство ---------------------------------------------------
    out("=" * 78)
    out("УСТРОЙСТВО: разброс от мира к миру")
    out("=" * 78)
    for label, getter in SHAPE:
        values = sorted(getter(world) for world in worlds)
        low, high = values[0], values[-1]
        mid = values[len(values) // 2]
        spread = "%.1f" % (high / float(low)) if low else "—"
        out("  %-16s от %8d до %8d (середина %8d, разброс x%s)"
            % (label, low, high, mid, spread))
    out("")

    # --- зацикленность ------------------------------------------------
    out("=" * 78)
    out("ЗАЦИКЛЕННОСТЬ: насколько конец истории повторяет её начало")
    out("=" * 78)
    for seed, world in zip(seeds, worlds):
        value = loopiness(world)
        mark = "мир ходит по кругу" if value > 0.85 else \
               ("поздние века похожи на ранние" if value > 0.7 else "в порядке")
        out("  %-10s совпадение %.2f — %s" % (seed, value, mark))
    out("")

    if options["--out"]:
        with open(options["--out"], "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        print("Записано в %s" % options["--out"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
