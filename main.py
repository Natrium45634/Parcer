# -*- coding: utf-8 -*-
"""Хронист — генератор фэнтезийных историй.

Запуск двойным щелчком по ярлыку (см. README) или из консоли:

    python main.py                 — окно программы
    python main.py --cli           — генерация без окна, летопись в файл

Ключи консольного режима:
    --seed СИД        сид генерации: код вида KR7M-93XD или любое
                      слово (по умолчанию «Начало»)
    --years N         сколько лет истории (по умолчанию 10000)
    --regions N       сколько земель на карте (по умолчанию 18)
    --density X       плотность событий, 0.2…3.0 (по умолчанию 1.0)
    --importance N    что попадёт в текст: 1 — всё, 5 — только эпохальное
    --out ФАЙЛ        куда сохранить летопись (.txt) или мир (.json)
    --map ФАЙЛ        карта .world из TECTONIC WORLDFORGE; тогда история
                      опирается на настоящую географию, а не на выдумку
    --map-interval N  раз во столько лет снимать кадр границ (по умолчанию 50)
    --chronicle ФАЙЛ  записать chronicle.json — политическую карту по годам
                      для вкладки «Страны» картогенератора
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_cli(argv) -> int:
    from worldgen import chronicle, storage
    from worldgen.engine import Settings, generate

    options = {"--seed": "Начало", "--years": "10000", "--regions": "18",
               "--density": "1.0", "--out": "", "--importance": "3",
               "--map": "", "--map-interval": "50", "--chronicle": ""}
    index = 0
    while index < len(argv):
        key = argv[index]
        if key in options and index + 1 < len(argv):
            options[key] = argv[index + 1]
            index += 2
        else:
            index += 1

    map_path = options["--map"]
    if map_path and not os.path.exists(map_path):
        print("Карта не найдена: %s" % map_path)
        return 2

    settings = Settings(seed=options["--seed"], years=int(float(options["--years"])),
                        regions=int(float(options["--regions"])),
                        density=float(options["--density"]),
                        map_path=map_path,
                        map_interval=int(float(options["--map-interval"])))

    def progress(part, note):
        sys.stdout.write("\r  %3d%%  %-42s" % (int(part * 100), note))
        sys.stdout.flush()

    if map_path:
        print("Карта: %s" % os.path.basename(map_path))
    print("Генерация мира «%s»…" % settings.seed)
    world = generate(settings, progress=progress)
    print("\nГотово.")
    for key, value in world.stats().items():
        print("  %-26s %s" % (key + ":", value))

    chronicle_out = options["--chronicle"]
    if chronicle_out:
        if world.map_recorder is None:
            print("chronicle.json пишется только для мира по карте — задайте --map")
        else:
            from worldgen import chronicle_map
            payload = chronicle_map.export(world, world.map_recorder, chronicle_out)
            section = payload["map"]
            print("Политическая карта: %s (кадров %d, держав %d, городов %d)" % (
                chronicle_out, len(section["frames"]),
                len(section["realmColors"]), len(section["cities"])))

    out = options["--out"]
    if out:
        if out.lower().endswith(".json"):
            storage.save_world(world, out)
        else:
            storage.save_text(chronicle.full_text(world), out)
        print("Записано в %s" % out)
    else:
        print()
        print(chronicle.render_chronicle(world,
                                         min_importance=int(options["--importance"])))
    return 0


def run_gui() -> int:
    try:
        import tkinter
        del tkinter
    except ImportError:
        print("Не найден модуль tkinter — без него окно не открыть.\n"
              "В Windows и macOS он входит в обычную установку Python.\n"
              "В Linux поставьте пакет python3-tk, например:\n"
              "    sudo apt install python3-tk\n\n"
              "Пока можно пользоваться консольным режимом:\n"
              "    python3 main.py --cli --years 10000 --out летопись.txt")
        return 1

    from gui.app import run
    run()
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--cli" in argv or "--help" in argv or "-h" in argv:
        if "--help" in argv or "-h" in argv:
            print(__doc__)
            return 0
        return run_cli(argv)
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
