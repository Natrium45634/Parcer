# -*- coding: utf-8 -*-
"""Рисует иконку приложения без сторонних библиотек.

Создаёт assets/icon.png (256x256) и assets/icon.ico (16/32/48/64) —
свиток летописи на тёмном круге. Запускать вручную не нужно: файлы уже
лежат в репозитории. Скрипт оставлен, чтобы иконку можно было изменить.
"""

from __future__ import annotations

import math
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")

BACK = (36, 31, 54, 255)        # тёмный фон круга
RIM = (198, 161, 74, 255)       # золотой обод
PAPER = (233, 221, 193, 255)    # пергамент
PAPER_DARK = (204, 186, 148, 255)
INK = (74, 60, 44, 255)
STAR = (245, 224, 150, 255)


class Canvas:
    def __init__(self, size: int):
        self.size = size
        self.pixels = [(0, 0, 0, 0)] * (size * size)

    def blend(self, x: int, y: int, color, alpha: float = 1.0) -> None:
        if not (0 <= x < self.size and 0 <= y < self.size) or alpha <= 0:
            return
        index = y * self.size + x
        src_r, src_g, src_b, src_a = color
        alpha = min(1.0, alpha) * (src_a / 255.0)
        dst_r, dst_g, dst_b, dst_a = self.pixels[index]
        out_a = alpha + (dst_a / 255.0) * (1 - alpha)
        if out_a <= 0:
            self.pixels[index] = (0, 0, 0, 0)
            return
        def mix(src, dst):
            return int(round((src * alpha + dst * (dst_a / 255.0) * (1 - alpha)) / out_a))
        self.pixels[index] = (mix(src_r, dst_r), mix(src_g, dst_g),
                              mix(src_b, dst_b), int(round(out_a * 255)))

    def circle(self, cx: float, cy: float, radius: float, color) -> None:
        for y in range(int(cy - radius) - 1, int(cy + radius) + 2):
            for x in range(int(cx - radius) - 1, int(cx + radius) + 2):
                distance = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                alpha = max(0.0, min(1.0, radius - distance + 0.5))
                if alpha > 0:
                    self.blend(x, y, color, alpha)

    def ring(self, cx: float, cy: float, radius: float, thickness: float, color) -> None:
        for y in range(int(cy - radius) - 1, int(cy + radius) + 2):
            for x in range(int(cx - radius) - 1, int(cx + radius) + 2):
                distance = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                alpha = min(max(0.0, radius - distance + 0.5),
                            max(0.0, distance - (radius - thickness) + 0.5), 1.0)
                if alpha > 0:
                    self.blend(x, y, color, alpha)

    def rect(self, x0: float, y0: float, x1: float, y1: float, color) -> None:
        for y in range(int(y0), int(math.ceil(y1))):
            for x in range(int(x0), int(math.ceil(x1))):
                self.blend(x, y, color)

    def resized(self, size: int) -> "Canvas":
        """Уменьшение с усреднением — иначе мелкие размеры выглядят рвано."""
        out = Canvas(size)
        factor = self.size / float(size)
        for y in range(size):
            for x in range(size):
                r = g = b = a = 0.0
                count = 0
                for sy in range(int(y * factor), int((y + 1) * factor)):
                    for sx in range(int(x * factor), int((x + 1) * factor)):
                        pr, pg, pb, pa = self.pixels[sy * self.size + sx]
                        weight = pa / 255.0
                        r += pr * weight
                        g += pg * weight
                        b += pb * weight
                        a += pa
                        count += 1
                if not count:
                    continue
                alpha_sum = a / 255.0
                if alpha_sum <= 0:
                    out.pixels[y * size + x] = (0, 0, 0, 0)
                else:
                    out.pixels[y * size + x] = (
                        int(r / alpha_sum), int(g / alpha_sum), int(b / alpha_sum),
                        int(a / count))
        return out


def draw(size: int) -> Canvas:
    canvas = Canvas(size)
    scale = size / 256.0
    center = size / 2.0

    canvas.circle(center, center, 124 * scale, BACK)
    canvas.ring(center, center, 124 * scale, 9 * scale, RIM)

    # Пергамент
    left, right = 74 * scale, 182 * scale
    top, bottom = 62 * scale, 194 * scale
    canvas.rect(left, top, right, bottom, PAPER)
    canvas.rect(left, top, right, top + 10 * scale, PAPER_DARK)
    canvas.rect(left, bottom - 10 * scale, right, bottom, PAPER_DARK)

    # Строки «летописи»
    for index in range(6):
        y = top + (24 + index * 19) * scale
        width = (right - left) - (18 + (index % 3) * 20) * scale
        canvas.rect(left + 12 * scale, y, left + 12 * scale + width, y + 6 * scale, INK)

    # Звезда над свитком — знак эпохи
    canvas.circle(center, 46 * scale, 11 * scale, STAR)
    canvas.rect(center - 2 * scale, 26 * scale, center + 2 * scale, 66 * scale, STAR)
    canvas.rect(center - 20 * scale, 44 * scale, center + 20 * scale, 48 * scale, STAR)
    return canvas


def write_png(canvas: Canvas, path: str) -> None:
    raw = bytearray()
    for y in range(canvas.size):
        raw.append(0)
        for x in range(canvas.size):
            raw.extend(bytes(canvas.pixels[y * canvas.size + x]))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", canvas.size, canvas.size, 8, 6, 0, 0, 0)
    blob = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(blob)


def write_ico(canvases, path: str) -> None:
    """ICO из BMP-кадров: такой формат понимают все версии Windows."""
    entries = []
    blobs = []
    offset = 6 + 16 * len(canvases)
    for canvas in canvases:
        size = canvas.size
        header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                             size * size * 4, 0, 0, 0, 0)
        body = bytearray()
        for y in range(size - 1, -1, -1):           # BMP хранит строки снизу вверх
            for x in range(size):
                r, g, b, a = canvas.pixels[y * size + x]
                body.extend((b, g, r, a))
        mask_row = ((size + 31) // 32) * 4
        body.extend(b"\x00" * (mask_row * size))
        blob = header + bytes(body)
        blobs.append(blob)
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0,
                                   size if size < 256 else 0, 0, 0, 1, 32,
                                   len(blob), offset))
        offset += len(blob)

    with open(path, "wb") as handle:
        handle.write(struct.pack("<HHH", 0, 1, len(canvases)))
        for entry in entries:
            handle.write(entry)
        for blob in blobs:
            handle.write(blob)


def main() -> None:
    if not os.path.isdir(ASSETS):
        os.makedirs(ASSETS)
    big = draw(256)
    write_png(big, os.path.join(ASSETS, "icon.png"))
    write_png(big.resized(64), os.path.join(ASSETS, "icon_64.png"))
    write_ico([big.resized(size) for size in (16, 32, 48, 64)],
              os.path.join(ASSETS, "icon.ico"))
    print("Иконки записаны в", ASSETS)


if __name__ == "__main__":
    main()
