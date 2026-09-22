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
    --map ФАЙЛ        готовая карта .world; тогда история опирается на
                      настоящую географию, а не на выдумку
    --map-random РАЗМЕР  сделать свою гексовую карту Worldforge:
                      малая (160×96), средняя (280×168), большая (500×300)
    --map-seed СИД    сид карты (по умолчанию — сид мира)
    --map-cont N      сколько материков на карте, 1…8 (по умолчанию 4)
    --map-knobs ШКАЛЫ ползунки картогенератора: «mountains=80,rivers=30»
    --map-knob-list   показать все ползунки карты и выйти
    --save-map ФАЙЛ   записать сделанную карту в .world
    --tune ШКАЛЫ      настройки генератора: «war_rate=20,calamity_rate=80»;
                      шкала от 0 до 100, 50 — как задумано
    --tune-list       показать все шкалы настроек и выйти
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
               "--map": "", "--map-interval": "50", "--chronicle": "",
               "--map-random": "", "--map-seed": "", "--save-map": "",
               "--map-cont": "4", "--map-knobs": "", "--tune": ""}
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

    knobs = {}
    for pair in options["--tune"].replace(";", ",").split(","):
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        try:
            knobs[key.strip()] = max(0, min(100, int(float(value))))
        except ValueError:
            print("Не понял настройку: %s" % pair)
            return 2

    make = {}
    if options["--map-random"]:
        from worldgen import worldforge
        size = _map_size(options["--map-random"])
        if size is None:
            print("Размер карты бывает такой: %s"
                  % ", ".join(worldforge.SIZE_NAMES[key]
                              for key in ("small", "medium", "large")))
            return 2
        knobs = {}
        for pair in options["--map-knobs"].split(","):
            pair = pair.strip()
            if not pair:
                continue
            key, _, value = pair.partition("=")
            key = key.strip()
            if key not in worldforge.DEFAULT_K:
                print("Нет такого ползунка карты: %s" % key)
                return 2
            try:
                knobs[key] = int(float(value))
            except ValueError:
                print("Ползунок карты — число: %s" % pair)
                return 2
        make = {"size": size, "continents": int(float(options["--map-cont"])),
                "k": knobs,
                "seed": options["--map-seed"] or options["--seed"]}

    settings = Settings(seed=options["--seed"], years=int(float(options["--years"])),
                        regions=int(float(options["--regions"])),
                        density=float(options["--density"]),
                        map_path=map_path,
                        map_interval=int(float(options["--map-interval"])),
                        tuning=knobs, map_make=make)

    if options["--save-map"] and make:
        from worldgen import worldforge
        options_map = dict(make)
        seed = options_map.pop("seed")
        wmap = worldforge.forge(seed, **options_map)
        size = worldforge.save_map(wmap, options["--save-map"])
        print("Карта записана в %s (%.1f МБ)"
              % (options["--save-map"], size / 1048576.0))

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


def show_knobs() -> int:
    """Список всех шкал настроек — чтобы было что писать в --tune."""
    from worldgen import tuning
    for group, knobs in tuning.groups():
        print()
        print(group.upper())
        for knob in knobs:
            print("  %-18s %s" % (knob.key, knob.name))
            print("  %-18s   %s" % ("", knob.hint))
    print()
    print("Шкала от 0 до 100, 50 — как задумано. Пример:")
    print("  python main.py --cli --tune war_rate=15,calamity_rate=85")
    return 0


def _map_size(word: str):
    """Размер карты по-русски или по-английски — в ключ Worldforge."""
    from worldgen import worldforge
    word = (word or "").strip().lower()
    for key, name in worldforge.SIZE_NAMES.items():
        if word in (key, name):
            return key
    # «огромная» из прежних версий — теперь это «большая»
    if word in ("огромная", "huge"):
        return "large"
    return None


def show_map_knobs() -> int:
    """Список ползунков картогенератора — для --map-knobs."""
    from worldgen import worldforge
    print()
    print("ПОЛЗУНКИ КАРТЫ WORLDFORGE")
    for key, name in worldforge.K_NAMES:
        print("  %-14s %-28s по умолчанию %s"
              % (key, name, worldforge.DEFAULT_K[key]))
    print()
    print("Шкала от 0 до 100 (тепло мира — от -30 до 30). Пример:")
    print("  python main.py --cli --map-random средняя "
          "--map-knobs mountains=85,rivers=25")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--tune-list" in argv:
        return show_knobs()
    if "--map-knob-list" in argv:
        return show_map_knobs()
    if "--cli" in argv or "--help" in argv or "-h" in argv:
        if "--help" in argv or "-h" in argv:
            print(__doc__)
            return 0
        return run_cli(argv)
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
