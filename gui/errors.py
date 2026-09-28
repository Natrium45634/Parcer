# -*- coding: utf-8 -*-
"""Что сказать человеку, когда что-то сломалось.

Программа для человека, а не для программиста: разбор вызовов и
английское имя класса ему ничего не объясняют. Свои поломки уже написаны
по-русски — их и показываем как есть. У чужих объяснения нет, и
придумать его нельзя; тогда хотя бы называем беду, её род и то, что
можно попробовать.
"""

from __future__ import annotations

from worldgen.worldmap import WorldMapError


def human_error(error: Exception) -> str:
    note = str(error).strip()
    if isinstance(error, WorldMapError):
        return "Карта не читается: %s." % note
    if isinstance(error, MemoryError):
        return "Не хватило памяти. Возьмите меньше лет или карту помельче."
    if isinstance(error, OSError):
        return "Не вышло с файлом: %s." % (note or "ошибка чтения или записи")
    return "Сбой в работе: %s (%s)." % (note or "без пояснения",
                                        error.__class__.__name__)
