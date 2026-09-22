# -*- coding: utf-8 -*-
"""Worldforge — генератор гексовых карт мира.

Перенос исходного картогенератора (TECTONIC WORLDFORGE v5.2) на Python:
тектоника, эрозия, климат, реки, биомы, недра, живность, бедствия,
логова и племена. Перенос точный — при том же сиде и тех же ползунках
карта выходит та же, что у исходного генератора, гекс в гекс.

Отсюда берут карту и мастер создания мира, и командная строка:

    wmap = worldforge.forge("Ясень-7", size="medium")
    worldforge.save_map(wmap, "мой-мир.world")
"""

from __future__ import annotations

from . import biomes, export, extras, geology
from .biomes import COLORS as BIOME_COLORS
from .biomes import NAMES as BIOME_NAMES
from .core import (DEFAULT_K, K_NAMES, SIZE_NAMES, SIZES, Config,
                   ForgedWorld, _round, generate)
from .rng import rng_from

DEFAULT_SIZE = "medium"

__all__ = ("forge", "forge_world", "save_map", "color_grid", "random_knobs",
           "Config", "ForgedWorld", "generate", "SIZES", "SIZE_NAMES",
           "DEFAULT_K", "K_NAMES", "DEFAULT_SIZE", "BIOME_NAMES",
           "BIOME_COLORS", "biomes", "export", "extras", "geology")


def forge_world(seed, size=DEFAULT_SIZE, continents=4, wrap=True, k=None,
                progress=None, **older) -> ForgedWorld:
    """Собирает мир целиком — со всеми слоями, но без упаковки в карту.

    Лишние ключи молча пропускаются: в старых сохранениях лежат настройки
    прежнего генератора карт, и мир по ним всё равно должен собраться.
    """
    size = size if size in SIZES else DEFAULT_SIZE
    cfg = Config(seed=seed, size=size, continents=continents, wrap=wrap, k=k)
    return generate(cfg, progress)


# Последняя собранная карта держится в памяти байтами: мастер делает её
# для предпросмотра, а движок просит ту же самую при создании мира —
# считать её дважды незачем, а байты гарантируют чистую копию.
_LAST = {"entry": None}


def _cache_key(seed, size, continents, wrap, k):
    knobs = tuple(sorted((str(a), int(b)) for a, b in (k or {}).items()))
    return (str(seed), str(size), int(continents), bool(wrap), knobs)


def forge(seed, size=DEFAULT_SIZE, continents=4, wrap=True, k=None,
          progress=None, with_minerals=True, **older):
    """Готовая гексовая карта: то же, что читается из файла .world."""
    size = size if size in SIZES else DEFAULT_SIZE
    key = _cache_key(seed, size, continents, wrap, k)
    entry = _LAST["entry"]
    if entry is not None and entry[0] == key:
        from .. import worldmap as _wm
        return _wm.loads(entry[1])
    # Ход счёта идёт в одну сторону: сперва сам мир, потом слои и хвост.
    def stage(low, high):
        if progress is None:
            return None
        return lambda part, note: progress(low + (high - low) * part, note)

    world = forge_world(seed, size=size, continents=continents, wrap=wrap,
                        k=k, progress=stage(0.0, 0.72))
    wmap = export.worldmap_of(world, with_minerals=with_minerals,
                              progress=stage(0.72, 1.0))
    try:
        # Ключ и байты кладём одной парой: иначе два потока успели бы
        # смешать ключ одной карты с байтами другой.
        _LAST["entry"] = (key, export.dumps_map(wmap))
    except Exception:            # не вышло сберечь — просто посчитаем снова
        _LAST["entry"] = None
    return wmap


def save_map(wmap, path) -> int:
    """Пишет готовую карту файлом .world."""
    return export.save_map(wmap, path)


def color_grid(wmap) -> list:
    """Цвета биомов построчно — для предпросмотра карты в окне."""
    biome_layer = wmap.layer(3)
    colors = BIOME_COLORS
    out = []
    for row in range(wmap.height):
        base = row * wmap.width
        line = []
        for col in range(wmap.width):
            value = biome_layer[base + col] if biome_layer is not None else 0
            line.append(colors[value] if value < len(colors) else "#888888")
        out.append(line)
    return out


def random_knobs(seed, locked=None) -> dict:
    """Случайные положения ползунков карты — как кнопка «кости» в исходнике.

    Считается от сида, поэтому показанный сид полностью описывает
    результат: те же кости выпадут и в следующий раз.
    """
    rng = rng_from("%s:knobs" % seed)
    locked = set(locked or ())
    out = {}
    for key, _name in K_NAMES:
        if key in locked:
            continue          # закреплённая шкала не тратит и броска костей
        if key == "temperature":
            out[key] = _round((rng() - 0.5) * 60)
        else:
            out[key] = _round(rng() * 100)
    if "peaks" not in locked:
        out["peaks"] = _round(rng() * 30)
    if "continents" not in locked:
        out["continents"] = 1 + _round(rng() * 7)
    return out
