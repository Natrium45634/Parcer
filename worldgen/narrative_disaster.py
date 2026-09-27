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
from .timeline import years_text


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


# ---------------------------------------------------------------------------
# Шрамы мира
# ---------------------------------------------------------------------------

SCAR_FRAMES = (
    "В земле по имени %(where)s осталось то, чего до беды не было: %(about)s.",
    "Беда ушла, а это осталось: %(about)s — в земле по имени %(where)s.",
    "%(where_cap)s несёт след той беды: %(about)s.",
)

SCAR_TAILS = (
    "Место назвали так: %(name)s.",
    "У места быстро завелось имя — %(name)s.",
    "На картах его подписали позже, и подпись держится: %(name)s.",
)

SCAR_DANGER = {
    0: "Ходить туда не запрещали.",
    1: "Ходить туда не любили, но ходили.",
    2: "Скота туда не гоняли и детей не пускали.",
    3: "Туда не ходили вовсе, и того, кто ходил, не расспрашивали.",
}


def scar_left(rng, scar, kind, calamity, region) -> tuple:
    """След, который беда оставила на земле."""
    where = region.name if region is not None else "—"
    data = {"where": where, "where_cap": cap(where), "about": kind.about,
            "name": scar.name}
    lines = [cap(rng.choice(SCAR_FRAMES) % data),
             rng.choice(SCAR_TAILS) % data,
             SCAR_DANGER.get(min(3, max(0, kind.danger)), "")]
    lines.append("Оставила его беда по имени «%s»." % calamity.name)
    return ("След беды: %s" % scar.name, " ".join(part for part in lines if part))


SCAR_TURNS = {
    dis.SCAR_SHUNNED: (
        "Место стали обходить: дорогу повели в стороне, и обход прижился.",
        "За два поколения место обросло запретами, и запреты никто не отменял.",
        "Туда перестали ходить — сперва из осторожности, потом по привычке.",
    ),
    dis.SCAR_SETTLED: (
        "Место обжили заново: земля нашлась, а земли всегда мало.",
        "Пришли те, кому больше некуда, и стали жить прямо здесь.",
        "Запрет держался, пока не пришли голодные годы; потом здесь пахали.",
    ),
    dis.SCAR_HOLY: (
        "Место объявили святым, и над ним стали служить раз в год.",
        "Жрецы взяли место себе: то, что помнит беду, легко объяснить волей.",
        "Здесь поставили знак и стали ходить к нему со просьбами.",
    ),
    dis.SCAR_FORGOTTEN: (
        "Откуда взялось это место, помнить перестали.",
        "Имя осталось, а за именем — ничего: беду забыли начисто.",
        "Спрашивали стариков, и старики уже не знали.",
    ),
}

SCAR_FORGOT_FROM = {
    dis.SCAR_SETTLED: (
        "Здесь пахали и не знали, отчего земля такая.",
        "Дети тех, кто пришёл, считали это место обычным.",
    ),
    dis.SCAR_HOLY: (
        "Служить не перестали — перестали помнить, над чем служат.",
        "Обряд остался, а причина обряда потерялась.",
    ),
    dis.SCAR_SHUNNED: (
        "Обход остался на дорогах, а запрет — без объяснения.",
        "Ходить туда так и не стали, и уже не помнили почему.",
    ),
}


def scar_turn(rng, scar, kind, was: str, state: str, region, age: int) -> tuple:
    """Что стало с местом через века."""
    where = region.name if region is not None else "—"
    lines = [rng.choice(SCAR_TURNS.get(state, ("Место переменилось.",)))]
    if state == dis.SCAR_FORGOTTEN and was in SCAR_FORGOT_FROM:
        lines.append(rng.choice(SCAR_FORGOT_FROM[was]))
    if state == dis.SCAR_SETTLED and scar.boon:
        lines.append("И оказалось, что %s." % scar.boon)
    lines.append("Речь о месте по имени %s в земле по имени %s; беде к тому "
                 "году было %s." % (scar.name, where, years_text(age)))
    return ("%s: %s" % (scar.name, state), " ".join(lines))


# ---------------------------------------------------------------------------
# Потерянное знание
# ---------------------------------------------------------------------------

LOST_FRAMES = (
    "Вместе с людьми ушло умение: %(about)s.",
    "Считать убытки начали с мёртвых и не сразу заметили другое: %(about)s.",
    "Самое дорогое, что взяла эта беда, не считается в душах: %(about)s.",
)

LOST_HARD = {
    1: "Вернуть это было можно, и лет через сто вернули бы.",
    2: "Чтобы вернуть это, нужен был человек, которого не было.",
    3: "Вернуть это было почти нельзя: умели немногие, и не осталось никого.",
}


def lore_lost(rng, lore, kind, calamity, world) -> tuple:
    """Знание, погибшее вместе с теми, кто умел."""
    region = world.regions.get(lore.region_id)
    where = region.name if region is not None else "—"
    lines = [cap(rng.choice(LOST_FRAMES) % {"about": kind.about}),
             LOST_HARD.get(min(3, max(1, kind.hardness)), ""),
             "Это случилось в земле по имени %s, в беде по имени «%s»."
             % (where, calamity.name)]
    if kind.fragment:
        lines.append("Осталось от него вот что: %s." % kind.fragment)
    return ("Утрата: %s" % lore.kind, " ".join(part for part in lines if part))


FRAGMENT_FRAMES = (
    "От утраченного нашлись обрывки: %(fragment)s.",
    "Кто-то собрал остатки: %(fragment)s — и стало ясно, что целое было.",
    "Обрывки лежали на виду и век ничего не значили: %(fragment)s.",
)

FRAGMENT_TAILS = (
    "Собрать из этого целое пока не сумел никто.",
    "Читать это взялись многие, понять — никто.",
    "Спорили, подделка это или память, и не сошлись.",
)


def lore_fragments(rng, lore, world) -> tuple:
    """Обрывки нашлись, а целого ещё нет."""
    region = world.regions.get(lore.region_id)
    where = region.name if region is not None else "—"
    text = "%s %s %s" % (
        cap(rng.choice(FRAGMENT_FRAMES) % {"fragment": lore.fragment
                                          or "несколько записей"}),
        rng.choice(FRAGMENT_TAILS),
        "Речь о том, что %s, — в земле по имени %s." % (lore.about, where))
    return ("Обрывки: %s" % lore.kind, text)


FOUND_FRAMES = (
    "Утраченное вернули: %(about)s — и снова умеют.",
    "То, что забыли, собрали заново по обрывкам: %(about)s.",
    "Через века нашлось целое: %(about)s, и это больше не тайна.",
)

FOUND_TAILS = (
    "Того, кто это сделал, помнили меньше, чем следовало бы.",
    "Новое умение считали своим, а не возвращённым.",
    "Спорили, то ли это самое умение или только похожее.",
    "И уже через поколение никто не верил, что этого не знали.",
)


def lore_found(rng, lore, finder: str, age: int, world, sex: str = "") -> tuple:
    """Знание вернулось — по обрывкам и через века.

    Вернул его человек или вернул сам город: если это человек, слово
    согласуется с его полом, иначе выходит «вернул Сильмет», а Сильмет —
    она.
    """
    region = world.regions.get(lore.region_id)
    where = region.name if region is not None else "—"
    word = "Вернула" if sex == "f" else "Вернул"
    text = "%s %s %s" % (
        cap(rng.choice(FOUND_FRAMES) % {"about": lore.about}),
        "%s его %s; от утраты прошло %s, земля — %s."
        % (word, finder, years_text(age), where),
        rng.choice(FOUND_TAILS))
    return ("Найдено заново: %s" % lore.kind, text)


__all__ = ["omen", "prevented", "turn_point", "phase_turn", "response",
           "scar_left", "scar_turn", "lore_lost", "lore_fragments",
           "lore_found"]
