# -*- coding: utf-8 -*-
"""Из мира Worldforge — в карту .world, которую читает движок истории.

Формат тот же, что у исходного генератора: шапка «WRLD», плотные слои по
гексам подряд и JSON-хвост с именованными объектами. Сюда же собраны все
надстройки: живность, бедствия, водоносность, дикость, логова, племена,
долгий климат и недра.

Карту можно отдать двумя путями. save() пишет файл — его открывает и
картогенератор, и программа. worldmap_of() собирает ту же карту прямо в
памяти: при создании мира из мастера файл ни к чему.
"""

from __future__ import annotations

import json
import struct
from array import array

from .. import worldmap as wm
from . import biomes as biome_table
from . import extras, geology
from .rng import xmur3

DT_OF = {
    0: wm.DT_F32, 1: wm.DT_F32, 2: wm.DT_F32, 3: wm.DT_U8, 4: wm.DT_U8,
    5: wm.DT_F32, 6: wm.DT_I16, 7: wm.DT_F32, 8: wm.DT_U8, 9: wm.DT_I32,
    10: wm.DT_F32, 11: wm.DT_U8, 12: wm.DT_U8, 13: wm.DT_I16, 14: wm.DT_U8,
    15: wm.DT_F32, 16: wm.DT_U8, 17: wm.DT_U8, 20: wm.DT_I32, 21: wm.DT_I32,
    22: wm.DT_I32, 23: wm.DT_I32,
}

_PACK = {wm.DT_U8: "B", wm.DT_I16: "h", wm.DT_I32: "i", wm.DT_F32: "f"}


def seed_to_u64(seed) -> int:
    """Числовой сид для движка — тем же хэшем, что и в исходнике."""
    step = xmur3(str(seed))
    lo = step()
    hi = step()
    return (hi << 32) | lo


def _flags(world):
    """Слой 4: океан, озеро, река, берег — по одному биту на признак."""
    n = world.W * world.H
    out = array('B', [0]) * n
    for i in range(n):
        f = 0
        if world.is_ocean[i]:
            f |= 1
        if world.is_lake[i]:
            f |= 2
        if world.is_river[i]:
            f |= 4
        if not world.is_ocean[i]:
            for j in world.neighbors(i):
                if world.is_ocean[j]:
                    f |= 8
                    break
        out[i] = f
    return out


def _dist_v_u8(world):
    n = world.W * world.H
    out = array('B', [0]) * n
    for i in range(n):
        out[i] = min(99, int(world.dist_v[i] + 0.5))
    return out


def build_layers(world, progress=None) -> dict:
    """Все плотные слои карты: номер слоя -> массив по гексам."""

    def say(part, note):
        if progress is not None:
            progress(part, note)

    say(0.0, "слои карты")
    rich, fauna = extras.dense_resources(world)
    say(0.3, "бедствия земель")
    mask, chance = extras.dense_events(world)
    say(0.5, "вода и дикость")
    layers = {
        0: world.elev,
        1: world.temp,
        2: world.moist,
        3: world.biome,
        4: _flags(world),
        5: world.fertility,
        6: world.plate_of,
        7: world.stress,
        8: _dist_v_u8(world),
        9: world.flowto,
        10: world.accum,
        11: rich,
        12: fauna,
        13: mask,
        14: chance,
        15: world.magic,
        16: extras.aquifer(world),
        17: extras.savagery(world),
        20: world.land_reg,
        21: world.water_reg,
        22: world.range_reg,
        23: world.river_reg,
    }
    return layers


def build_tail(world, with_minerals: bool = True, progress=None) -> dict:
    """JSON-хвост: имена, объекты, каталоги и всё разреженное."""

    def say(part, note):
        if progress is not None:
            progress(part, note)

    say(0.6, "логова и племена")
    tail = {
        "seeds": {"master": str(world.cfg.seed)},
        "biomeNames": list(biome_table.NAMES),
        "features": [{"id": f["id"], "type": f["type"], "name": f["name"],
                      "cx": int(f["cx"] + 0.5), "cy": int(f["cy"] + 0.5),
                      "area": f["area"]} for f in world.features],
        "peaks": [{"i": p["i"], "name": p["name"], "m": p["m"]}
                  for p in world.peaks],
        "volcanoes": [{"i": v["i"], "name": v["name"],
                       "status": _status_en(v["status"]), "m": v["m"]}
                      for v in world.volcanoes],
        "resources": extras.resources_json(),
        "events": extras.events_json(),
        "naming": extras.naming_json(),
        "hydrology": extras.hydro_json(world),
        "surroundings": extras.surroundings_json(),
        "lairs": extras.lairs(world),
        "tribes": extras.tribes(world),
        "climate": extras.climate(world.cfg.seed),
    }
    if with_minerals:
        say(0.8, "недра")
        tail["minerals"] = geology.minerals_json(world)
    else:
        tail["minerals"] = {}
    return tail


_STATUS_EN = {"активный": "active", "спящий": "dormant",
              "потухший": "extinct"}


def _status_en(status: str) -> str:
    return _STATUS_EN.get(status, status)


def worldmap_of(world, with_minerals: bool = False, progress=None):
    """Карта прямо в памяти — без записи на диск."""
    layers = build_layers(world, progress)
    tail = build_tail(world, with_minerals, progress)
    return wm.WorldMap(
        width=world.W, height=world.H, wrap=world.wrap, sea=world.sea,
        min_alt=world.cfg.min_alt, max_alt=world.cfg.max_alt,
        seed_value=seed_to_u64(world.cfg.seed), layers=layers, tail=tail)


def dumps(world, with_minerals: bool = True, progress=None) -> bytes:
    """Карта в байтах формата .world версии 1."""
    layers = build_layers(world, progress)
    tail = build_tail(world, with_minerals, progress)
    json_bytes = json.dumps(tail, ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8")

    blocks = []
    for layer_id in sorted(layers):
        dtype = DT_OF[layer_id]
        data = layers[layer_id]
        code = _PACK[dtype]
        if data.typecode == code:
            raw = data.tobytes()
        else:                     # на всякий случай: перекладываем по типу
            raw = array(code, [int(v) for v in data]).tobytes()
        blocks.append((layer_id, dtype, raw))

    header = 64
    body = sum(8 + len(raw) for _, _, raw in blocks)
    json_offset = header + body
    out = bytearray(json_offset + len(json_bytes))
    struct.pack_into("<4sHHIIQIfffII", out, 0, b"WRLD", 1,
                     1 if world.wrap else 0, world.W, world.H,
                     seed_to_u64(world.cfg.seed), len(blocks), world.sea,
                     world.cfg.min_alt, world.cfg.max_alt, json_offset,
                     len(json_bytes))
    offset = header
    for layer_id, dtype, raw in blocks:
        struct.pack_into("<BBBBI", out, offset, layer_id, dtype, 0, 0,
                         len(raw))
        offset += 8
        out[offset:offset + len(raw)] = raw
        offset += len(raw)
    out[json_offset:json_offset + len(json_bytes)] = json_bytes
    return bytes(out)


def save(world, path, with_minerals: bool = True, progress=None) -> int:
    """Записывает карту файлом .world и возвращает его размер."""
    blob = dumps(world, with_minerals, progress)
    with open(path, "wb") as handle:
        handle.write(blob)
    return len(blob)


def dumps_map(wmap) -> bytes:
    """Готовая карта (та же, что читается из файла) — снова в байты."""
    json_bytes = json.dumps(wmap.tail, ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8")
    blocks = []
    for layer_id in sorted(wmap.layers):
        dtype = DT_OF.get(layer_id)
        if dtype is None:
            continue
        blocks.append((layer_id, dtype, wmap.layers[layer_id].tobytes()))
    header = 64
    body = sum(8 + len(raw) for _, _, raw in blocks)
    json_offset = header + body
    out = bytearray(json_offset + len(json_bytes))
    struct.pack_into("<4sHHIIQIfffII", out, 0, b"WRLD", 1,
                     1 if wmap.wrap else 0, wmap.width, wmap.height,
                     wmap.seed_value, len(blocks), wmap.sea,
                     wmap.min_alt, wmap.max_alt, json_offset, len(json_bytes))
    offset = header
    for layer_id, dtype, raw in blocks:
        struct.pack_into("<BBBBI", out, offset, layer_id, dtype, 0, 0,
                         len(raw))
        offset += 8
        out[offset:offset + len(raw)] = raw
        offset += len(raw)
    out[json_offset:json_offset + len(json_bytes)] = json_bytes
    return bytes(out)


def save_map(wmap, path) -> int:
    """Записывает готовую карту файлом .world."""
    blob = dumps_map(wmap)
    with open(path, "wb") as handle:
        handle.write(blob)
    return len(blob)
