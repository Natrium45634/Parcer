# -*- coding: utf-8 -*-
"""Чтение карты мира в формате .world (TECTONIC WORLDFORGE, контракт v1).

Файл — это плотные послойные массивы по гексам плюс JSON-хвост с
разреженными объектами: именованные моря и хребты, вершины, вулканы,
племенные стоянки, логова, лента долгосрочного климата.

Раскладка (см. worldexport.js генератора карт):

    0..63     заголовок
    64..      слои: 4 байта шапки (id, dtype, 0, 0) + 4 байта длины + данные
    jsonOff   JSON-хвост длиной jsonLen

Заголовок:

    0   "WRLD"          сигнатура
    4   u16 версия      = 1
    6   u16 wrap        карта замкнута по долготе
    8   u32 W           ширина в гексах
    12  u32 H           высота в гексах
    16  u64 masterSeed  сид карты (xmur3 от строки)
    24  u32 layerCount
    28  f32 SEA         уровень моря в единицах высоты 0..1
    32  f32 minAlt      метры дна
    36  f32 maxAlt      метры вершины
    40  u32 jsonOffset
    44  u32 jsonLength

Сетка гексовая, odd-r: у чётных и нечётных рядов смещение разное.
Зависимостей нет — только стандартная библиотека.
"""

from __future__ import annotations

import json
import struct
from array import array

MAGIC = b"WRLD"
HEADER_SIZE = 64

# --- типы данных слоёв ---
DT_U8, DT_I16, DT_I32, DT_F32 = 0, 1, 2, 3
_DT_CODE = {DT_U8: "B", DT_I16: "h", DT_I32: "i", DT_F32: "f"}
_DT_SIZE = {DT_U8: 1, DT_I16: 2, DT_I32: 4, DT_F32: 4}

# --- идентификаторы слоёв ---
L_ELEV = 0          # f32, высота 0..1 (SEA — граница воды и суши)
L_TEMP = 1          # f32, средняя температура, °C
L_MOIST = 2         # f32, влажность 0..1
L_BIOME = 3         # u8,  индекс в biomeNames
L_FLAGS = 4         # u8,  1 океан, 2 озеро, 4 река, 8 берег
L_FERTILITY = 5     # f32, плодородие 0..1
L_PLATE = 6         # i16, номер тектонической плиты
L_STRESS = 7        # f32, тектоническое напряжение
L_DISTV = 8         # u8,  расстояние до вулкана в гексах (99 — далеко)
L_FLOWTO = 9        # i32, куда течёт вода (-1 — никуда)
L_ACCUM = 10        # f32, водосбор
L_RICHNESS = 11     # u8,  ресурсная насыщенность
L_RESFLAGS = 12     # u8,  флаги ресурсов и живности
L_EVENTMASK = 13    # i16, битовая маска возможных местных бедствий
L_EVENTCHANCE = 14  # u8,  суммарный риск 0..255
L_MAGIC = 15        # f32, магия: минус — тёмная, плюс — светлая
L_AQUIFER = 16      # u8,  водоносный слой
L_SAVAGERY = 17     # u8,  дикость округи
L_LANDREG = 20      # i32, номер массива суши (материк или остров)
L_WATERREG = 21     # i32, номер водоёма
L_RANGEREG = 22     # i32, номер горного хребта
L_RIVERREG = 23     # i32, номер речного бассейна

FLAG_OCEAN = 1
FLAG_LAKE = 2
FLAG_RIVER = 4
FLAG_COAST = 8

# Смещения соседей для odd-r: [чётный ряд][6], [нечётный ряд][6].
ODDR = (
    ((+1, 0), (0, -1), (-1, -1), (-1, 0), (-1, +1), (0, +1)),
    ((+1, 0), (+1, -1), (0, -1), (-1, 0), (0, +1), (+1, +1)),
)


class WorldMapError(Exception):
    """Файл карты не читается."""


class WorldMap:
    """Карта мира: слои по гексам и именованные объекты."""

    def __init__(self, width, height, wrap, sea, min_alt, max_alt,
                 seed_value, layers, tail):
        self.width = int(width)
        self.height = int(height)
        self.wrap = bool(wrap)
        self.sea = float(sea)
        self.min_alt = float(min_alt)
        self.max_alt = float(max_alt)
        self.seed_value = int(seed_value)
        self.layers = layers            # id -> array
        self.tail = tail or {}
        self.size = self.width * self.height

    # ------------------------------------------------------------------
    # Доступ к слоям
    # ------------------------------------------------------------------

    def layer(self, layer_id, default=None):
        """Слой целиком; None, если его нет в файле."""
        return self.layers.get(layer_id, default)

    def has(self, layer_id) -> bool:
        return layer_id in self.layers

    def value(self, layer_id, index, default=0):
        data = self.layers.get(layer_id)
        if data is None:
            return default
        return data[index]

    # ------------------------------------------------------------------
    # Геометрия
    # ------------------------------------------------------------------

    def index(self, col, row) -> int:
        return row * self.width + col

    def col_row(self, index):
        return index % self.width, index // self.width

    def neighbors(self, index) -> list:
        """Шесть соседей гекса; по краям меньше, если карта не замкнута."""
        width, height = self.width, self.height
        col, row = index % width, index // width
        out = []
        for dcol, drow in ODDR[row & 1]:
            ncol, nrow = col + dcol, row + drow
            if nrow < 0 or nrow >= height:
                continue
            if ncol < 0 or ncol >= width:
                if not self.wrap:
                    continue
                ncol %= width
            out.append(nrow * width + ncol)
        return out

    def latitude(self, index) -> float:
        """Широта от -1 (юг) до +1 (север)."""
        row = index // self.width
        return 1.0 - 2.0 * (row + 0.5) / self.height

    def elevation_m(self, index) -> float:
        """Высота в метрах: выше уровня моря — плюс, ниже — минус."""
        elev = self.value(L_ELEV, index, self.sea)
        if elev >= self.sea:
            span = max(1e-6, 1.0 - self.sea)
            return (elev - self.sea) / span * self.max_alt
        return -(self.sea - elev) / max(1e-6, self.sea) * (-self.min_alt)

    # ------------------------------------------------------------------
    # Признаки гекса
    # ------------------------------------------------------------------

    def flags(self, index) -> int:
        return self.value(L_FLAGS, index, 0)

    def is_ocean(self, index) -> bool:
        return bool(self.flags(index) & FLAG_OCEAN)

    def is_lake(self, index) -> bool:
        return bool(self.flags(index) & FLAG_LAKE)

    def is_river(self, index) -> bool:
        return bool(self.flags(index) & FLAG_RIVER)

    def is_coast(self, index) -> bool:
        return bool(self.flags(index) & FLAG_COAST)

    def is_land(self, index) -> bool:
        return not (self.flags(index) & FLAG_OCEAN)

    # ------------------------------------------------------------------
    # JSON-хвост
    # ------------------------------------------------------------------

    @property
    def biome_names(self) -> list:
        return self.tail.get("biomeNames") or []

    def biome_name(self, biome_id) -> str:
        names = self.biome_names
        if 0 <= biome_id < len(names):
            return names[biome_id]
        return "биом %d" % biome_id

    @property
    def features(self) -> list:
        """Именованные объекты: океаны, моря, заливы, материки, хребты, реки."""
        return self.tail.get("features") or []

    @property
    def peaks(self) -> list:
        return self.tail.get("peaks") or []

    @property
    def volcanoes(self) -> list:
        return self.tail.get("volcanoes") or []

    @property
    def lairs(self) -> list:
        """Логова существ — откуда в мир приходит беда."""
        return self.tail.get("lairs") or []

    @property
    def map_tribes(self) -> list:
        """Стоянки племён, размеченные картой."""
        section = self.tail.get("tribes")
        if isinstance(section, dict):
            return section.get("list") or []
        return section or []

    @property
    def climate(self) -> dict:
        """Лента долгосрочного климата: оледенения, потепления, вулканические зимы."""
        return self.tail.get("climate") or {}

    @property
    def event_catalog(self) -> list:
        """Каталог местных бедствий: имя, полярность, базовый шанс."""
        section = self.tail.get("events")
        if isinstance(section, dict):
            return section.get("list") or section.get("catalog") or []
        return section or []

    @property
    def minerals(self) -> dict:
        return self.tail.get("minerals") or {}

    @property
    def seed_text(self) -> str:
        seeds = self.tail.get("seeds") or {}
        return str(seeds.get("master", ""))

    def describe(self) -> dict:
        """Короткая сводка — для окна настроек и отчётов."""
        land = sum(1 for i in range(self.size) if self.is_land(i))
        return {
            "Размер": "%d×%d гексов" % (self.width, self.height),
            "Всего гексов": self.size,
            "Суша": "%d (%.1f%%)" % (land, land * 100.0 / max(1, self.size)),
            "Замкнута по долготе": "да" if self.wrap else "нет",
            "Сид карты": self.seed_text or str(self.seed_value),
            "Слоёв": len(self.layers),
            "Биомов в таблице": len(self.biome_names),
            "Именованных объектов": len(self.features),
            "Вершин": len(self.peaks),
            "Вулканов": len(self.volcanoes),
            "Логовов": len(self.lairs),
            "Стоянок племён": len(self.map_tribes),
            "Климат-событий": len(self.climate.get("events") or []),
        }


def load(path) -> WorldMap:
    """Читает .world с диска."""
    with open(path, "rb") as handle:
        return loads(handle.read())


def loads(blob: bytes) -> WorldMap:
    """Разбирает .world из памяти."""
    if len(blob) < HEADER_SIZE:
        raise WorldMapError("файл слишком короткий для карты .world")
    if blob[:4] != MAGIC:
        raise WorldMapError("это не файл .world: нет подписи WRLD")

    (version, wrap, width, height, seed_value, layer_count,
     sea, min_alt, max_alt, json_offset, json_length) = struct.unpack_from(
        "<HHIIQIfffII", blob, 4)

    if version != 1:
        raise WorldMapError("версия формата %d не поддерживается" % version)
    if width <= 0 or height <= 0:
        raise WorldMapError("испорченный заголовок: размер %dx%d" % (width, height))

    count = width * height
    layers = {}
    offset = HEADER_SIZE
    for _ in range(layer_count):
        if offset + 8 > len(blob):
            raise WorldMapError("обрыв файла на шапке слоя")
        layer_id = blob[offset]
        dtype = blob[offset + 1]
        (length,) = struct.unpack_from("<I", blob, offset + 4)
        offset += 8
        if offset + length > len(blob):
            raise WorldMapError("обрыв файла в данных слоя %d" % layer_id)
        code = _DT_CODE.get(dtype)
        if code is None:
            offset += length
            continue
        expected = count * _DT_SIZE[dtype]
        if length != expected:
            # Слой не по размеру карты — пропускаем, но не роняем чтение.
            offset += length
            continue
        data = array(code)
        data.frombytes(blob[offset:offset + length])
        if _BIG_ENDIAN:
            data.byteswap()
        layers[layer_id] = data
        offset += length

    tail = {}
    if json_length:
        if json_offset + json_length > len(blob):
            raise WorldMapError("обрыв файла в JSON-хвосте")
        raw = blob[json_offset:json_offset + json_length].decode("utf-8", "replace")
        try:
            tail = json.loads(raw)
        except ValueError as error:
            raise WorldMapError("JSON-хвост не разбирается: %s" % error)

    return WorldMap(width, height, wrap, sea, min_alt, max_alt,
                    seed_value, layers, tail)


_BIG_ENDIAN = struct.pack("=H", 1) != struct.pack("<H", 1)
