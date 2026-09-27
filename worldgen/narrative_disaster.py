# -*- coding: utf-8 -*-
"""Тексты живой катастрофы: знаки, приготовления, переломы, шрамы.

Тексты бедствий как таких лежат в `narrative_calamity`. Здесь — то, что
появилось вместе с живой катастрофой: предвестники и их чтение,
предотвращённая беда, переломы, решения власти, шрамы на земле,
потерянное знание, четыре исхода, шесть версий и катастрофические эпохи.
"""

from __future__ import annotations

from . import disaster as dis
from .narrative_calamity import cap, region_list


# ---------------------------------------------------------------------------
# Предвестники
# ---------------------------------------------------------------------------

OMEN_FRAMES = (
    "В землях %(where)s %(sign)s.",
    "%(where_cap)s: %(sign)s.",
    "Тем годом в краю %(where)s %(sign)s.",
)

READ_RIGHT_FRAMES = (
    "Нашлись те, кто понял: %(right)s.",
    "Книжники сверили старые своды и сказали прямо: %(right)s.",
    "Один голос был верным: %(right)s, — и его на этот раз послушали.",
)

READ_WRONG_FRAMES = (
    "Прочли иначе: %(wrong)s.",
    "Толковать взялись те, кто был громче: %(wrong)s.",
    "Объяснение нашлось быстро и не то: %(wrong)s.",
)

READ_NONE_FRAMES = (
    "Знак заметили и не стали думать, к чему он.",
    "Об этом говорили неделю и забыли.",
    "Никто не взялся объяснять, и объяснения не нашлось.",
)


def omen(rng, item, reading: str, world, region_ids) -> tuple:
    """Знак, который видели заранее, и как его прочли."""
    where = region_list(world, region_ids, limit=2)
    data = {"where": where, "where_cap": cap(where), "sign": item.sign,
            "right": item.right,
            "wrong": rng.choice(item.wrong) if item.wrong else item.right}
    lines = [cap(rng.choice(OMEN_FRAMES) % data)]
    if reading == dis.READ_RIGHT:
        lines.append(rng.choice(READ_RIGHT_FRAMES) % data)
    elif reading == dis.READ_WRONG:
        lines.append(rng.choice(READ_WRONG_FRAMES) % data)
    else:
        lines.append(rng.choice(READ_NONE_FRAMES))
    title = "Знак: %s" % cap(item.sign)
    return title, " ".join(lines)


# ---------------------------------------------------------------------------
# Предотвращённая беда
# ---------------------------------------------------------------------------

STOP_FRAMES = (
    "Беды, которая шла на земли %(where)s, не случилось: %(about)s.",
    "То, что должно было прийти в край %(where)s, не пришло — %(about)s.",
    "В землях %(where)s ждали худшего, и худшее не пришло: %(about)s.",
)

STOP_TAILS = (
    "Летопись записала это коротко, и через век уже спорили, было ли чему "
    "приходить.",
    "Тех, кто это сделал, помнили недолго: не случившееся помнят хуже "
    "случившегося.",
    "Через сто лет об этом говорили как о пустом страхе — и зря.",
    "В своде осталась одна строка, и по ней не понять, чего избежали.",
)


def prevented(rng, spec, way: str, about: str, world, region_ids) -> tuple:
    """Беда, которую отвели до начала."""
    where = region_list(world, region_ids, limit=2)
    text = rng.choice(STOP_FRAMES) % {"where": where, "about": about}
    return ("Отведённая беда: %s" % spec.title,
            "%s %s" % (cap(text), rng.choice(STOP_TAILS)))


# ---------------------------------------------------------------------------
# Переломы
# ---------------------------------------------------------------------------

TURN_WORSE = (
    "И тут стало хуже: %(what)s.",
    "Дальше пошло вниз: %(what)s.",
    "Тот год переломил всё не в свою сторону: %(what)s.",
)

TURN_BETTER = (
    "Тогда же и переломилось: %(what)s.",
    "С этого и начался обратный ход: %(what)s.",
    "Дальше стало легче: %(what)s.",
)


def turn_point(rng, calamity, what: str, shift: float, world) -> tuple:
    frames = TURN_WORSE if shift > 0 else TURN_BETTER
    text = cap(rng.choice(frames) % {"what": what})
    where = region_list(world, calamity.region_ids, limit=2)
    tail = "Беда по имени «%s» шла тогда по землям %s." % (calamity.name, where)
    return ("Перелом: %s" % cap(what), "%s %s" % (text, tail))


# ---------------------------------------------------------------------------
# Фазы
# ---------------------------------------------------------------------------

PHASE_FRAMES = (
    "Беда по имени «%(name)s» переменилась: %(about)s.",
    "К этому году с бедой по имени «%(name)s» стало иначе: %(about)s.",
    "«%(name)s» вошла в новую полосу: %(about)s.",
)


def phase_turn(rng, calamity, phase, world) -> tuple:
    """Беда перешла в новую фазу."""
    text = rng.choice(PHASE_FRAMES) % {"name": calamity.name,
                                       "about": phase.about}
    where = region_list(world, calamity.region_ids, limit=2)
    return ("%s: %s" % (calamity.name, phase.key),
            "%s Земли: %s." % (cap(text), where))


# ---------------------------------------------------------------------------
# Решения власти
# ---------------------------------------------------------------------------

ANSWER_FRAMES = (
    "%(who)s: %(about)s.",
    "В %(state)s решили так: %(about)s.",
    "%(who)s — и держава сделала это: %(about)s.",
)

OUT_HELPED = (
    "Это помогло: тех, кого не досчитались, было меньше, чем боялись.",
    "Помогло — и об этом помнили дольше, чем о самой беде.",
    "Сработало, хотя никто не мог сказать, насколько.",
)

OUT_LATE = (
    "Сделано было поздно: помогло тем, кто ещё был жив.",
    "Решение пришло, когда половина уже случилась.",
    "Поздно — но не бесполезно.",
)

OUT_FAILED = (
    "Не вышло: сделали, и ничего не переменилось.",
    "Из этого не получилось ничего, кроме потраченного времени.",
    "Не помогло, и объяснить это никто не смог.",
)

OUT_WORSE = (
    "И вот это сделало хуже всего остального.",
    "Именно после этого беда перестала быть просто бедой.",
    "Стало хуже — и хуже стало от своих же, а не от беды.",
)

MISTAKE_TAIL = (
    "Позже своды сойдутся на том, что державу кончило не бедствие.",
    "Через век это назовут не бедой, а ошибкой столицы.",
    "О самой беде забудут раньше, чем об этом решении.",
)


def response(rng, calamity, polity, ruler, item, outcome: str) -> tuple:
    """Решение власти перед лицом беды и чем оно кончилось."""
    who = "Государь" if ruler is None else cap(_ruler_word(ruler))
    data = {"who": who, "state": polity.full_name, "about": item.about}
    lines = [cap(rng.choice(ANSWER_FRAMES) % data)]
    if outcome == dis.DONE_HELPED:
        lines.append(rng.choice(OUT_HELPED))
    elif outcome == dis.DONE_LATE:
        lines.append(rng.choice(OUT_LATE))
    elif outcome == dis.DONE_FAILED:
        lines.append(rng.choice(OUT_FAILED))
    else:
        lines.append(rng.choice(OUT_WORSE))
        if item.mistake:
            lines.append(rng.choice(MISTAKE_TAIL))
    title = "%s: %s" % (polity.name, item.key)
    return title, " ".join(lines)


def _ruler_word(figure) -> str:
    """«Государыня Х» или «государь Х» — кто это решил."""
    word = "государыня" if figure.sex == "f" else "государь"
    return "%s %s" % (word, figure.plain_name)


__all__ = ["omen", "prevented", "turn_point", "phase_turn", "response"]
