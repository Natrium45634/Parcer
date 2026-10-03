# -*- coding: utf-8 -*-
"""Код мира: всё, из чего он сделан, одной строкой.

Беда, которую это лечит: сид у мира был не один. Отдельно сид истории,
отдельно сид карты, отдельно восемнадцать ползунков картогенератора,
отдельно шестьдесят девять шкал движка, отдельно длительность и густота.
Человек, которому понравился мир, не мог передать его другому: назвать сид
недостаточно, потому что сид — только часть.

Теперь есть код мира — одна строка, в которой лежит **всё**. Вставил —
получил тот самый мир на той самой карте, до последней даты и последнего
имени.

Как он устроен и почему так:

* внутри — обычный JSON с настройками, сжатый и переписанный печатными
  буквами. Зачем сжатие: шестьдесят девять шкал и восемнадцать ползунков в
  открытом виде дают полторы тысячи знаков, и такое не вставляют, а теряют;
* **пишется только то, что отличается от обычного.** Мир на стандартных
  настройках даёт короткий код в несколько десятков знаков, и это главное:
  чаще всего крутят две ручки из семидесяти, и код должен быть коротким
  ровно настолько, насколько мир необычен;
* буквы только латинские и цифры: код диктуют, пишут в письмах и
  вставляют в чужие окна, а кириллица в таких переездах ломается;
* впереди стоит `HR1` — это метка вида. Если однажды состав настроек
  переменится, старые коды всё равно будут читаться: по метке видно, чего
  ждать.

Сам сид истории в коде хранится как есть, а не в сжатом виде: так его
видно глазом, и человек, которому дали код, узнаёт своё слово.
"""

from __future__ import annotations

import base64
import json
import zlib

# Метка вида кода. Меняется, только если меняется состав настроек.
MARK = "HR1"

# Что считается обычным. Совпало с обычным — в код не пишется.
DEFAULTS = {
    "years": 10000,
    "regions": 18,
    "density": 1.0,
    "map_path": "",
    "map_interval": 50,
    "tuning": {},
    "map_make": {},
}

# Ключи покороче: в сжатом виде это мелочь, но код и без того не украшение.
SHORT = {
    "seed": "s", "years": "y", "regions": "r", "density": "d",
    "map_path": "p", "map_interval": "i", "tuning": "t", "map_make": "m",
}
LONG = {value: key for key, value in SHORT.items()}


class BadCode(ValueError):
    """Код не читается: не тот вид, испорчен или не код вовсе."""


def _trim(value, default):
    """Пусто и равно обычному — значит писать нечего."""
    if isinstance(default, dict):
        return dict(value or {}) or None
    if value == default:
        return None
    return value


def encode(settings) -> str:
    """Собрать код мира из настроек.

    Путь к файлу карты в код не идёт: у того, кому код достанется, этого
    файла нет, и ссылаться на чужой диск бессмысленно. Если мир построен на
    файле карты, об этом сказано отдельно — кодом его не передать.
    """
    data = settings.to_dict() if hasattr(settings, "to_dict") else dict(settings)
    out = {SHORT["seed"]: str(data.get("seed", ""))}
    for key, default in DEFAULTS.items():
        if key == "map_path":
            continue                    # чужой путь на чужом диске
        value = _trim(data.get(key), default)
        if value is None:
            continue
        out[SHORT[key]] = value
    raw = json.dumps(out, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    packed = zlib.compress(raw, 9)
    body = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
    return "%s-%s" % (MARK, body)


def decode(text: str) -> dict:
    """Разобрать код мира обратно в настройки.

    Возвращает словарь, годный для Settings(**...). Всё, чего в коде нет,
    остаётся обычным: код короток именно потому, что об обычном молчит.
    """
    text = (text or "").strip()
    if not text:
        raise BadCode("код пустой")
    # Из письма код часто приезжает с переносами и пробелами внутри.
    text = "".join(text.split())
    head, _, body = text.partition("-")
    if head.upper() != MARK or not body:
        raise BadCode("это не код мира: в начале должно стоять «%s-»" % MARK)
    pad = "=" * (-len(body) % 4)
    try:
        packed = base64.urlsafe_b64decode(body + pad)
        raw = zlib.decompress(packed)
        got = json.loads(raw.decode("utf-8"))
    except Exception:
        raise BadCode("код испорчен: его не удалось разобрать")
    if not isinstance(got, dict):
        raise BadCode("код испорчен: внутри не настройки")
    out = {}
    for short, value in got.items():
        key = LONG.get(short)
        if key is None:
            continue                    # ключ из будущего вида — пропускаем
        out[key] = value
    if not out.get("seed"):
        raise BadCode("в коде нет сида мира")
    return out


def describe(text: str) -> str:
    """Короткая человеческая сводка о том, что в коде лежит."""
    got = decode(text)
    parts = ["сид «%s»" % got["seed"]]
    if "years" in got:
        parts.append("лет %s" % got["years"])
    make = got.get("map_make") or {}
    if make:
        parts.append("карта: сид «%s», размер %s, материков %s"
                     % (make.get("seed", "—"), make.get("size", "—"),
                        make.get("continents", "—")))
        if make.get("k"):
            parts.append("ползунков карты переставлено %d" % len(make["k"]))
    if got.get("tuning"):
        parts.append("шкал движка переставлено %d" % len(got["tuning"]))
    return "; ".join(parts)


__all__ = ["MARK", "BadCode", "encode", "decode", "describe"]
