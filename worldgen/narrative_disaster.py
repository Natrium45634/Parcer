# -*- coding: utf-8 -*-
"""Тексты живой катастрофы: знаки, приготовления, переломы, шрамы.

Тексты бедствий как таких лежат в `narrative_calamity`. Здесь — то, что
появилось вместе с живой катастрофой: предвестники и их чтение,
предотвращённая беда, переломы, решения власти, шрамы на земле,
потерянное знание, четыре исхода, шесть версий и катастрофические эпохи.
"""

from __future__ import annotations

from . import disaster as dis
from .narrative_calamity import cap, region_list, souls
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
    4: "Вернуть это было некому: последний, кто умел, умер, и учить он "
       "никого не успел.",
}


def lore_lost(rng, lore, kind, calamity, world) -> tuple:
    """Знание, погибшее вместе с теми, кто умел."""
    region = world.regions.get(lore.region_id)
    where = region.name if region is not None else "—"
    lines = [cap(rng.choice(LOST_FRAMES) % {"about": kind.about}),
             LOST_HARD.get(min(4, max(1, lore.hardness)), ""),
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


# ---------------------------------------------------------------------------
# Фронт
# ---------------------------------------------------------------------------

HOLD_FRAMES = (
    "Дальше они не пошли: %(about)s.",
    "Ход остановился, и остановило его вот что: %(about)s.",
    "Тот год они простояли на месте — %(about)s.",
)

HOLD_TAILS = (
    "Земля по имени %(where)s получила %(years)s, и это были не пустые годы.",
    "%(where_cap)s выиграла %(years)s — в них успели вывезти и хлеб, и людей.",
    "Земля по имени %(where)s держалась %(years)s, и держалась не войском.",
)


def front_hold(rng, calamity, hold, region, years: int, role: str = "",
               city_name: str = "") -> tuple:
    """Фронт встал, и у этого есть названная причина."""
    where = region.name if region is not None else "—"
    data = {"about": hold.about, "where": where, "where_cap": cap(where),
            "years": years_text(years)}
    parts = [cap(rng.choice(HOLD_FRAMES) % data),
             rng.choice(HOLD_TAILS) % data]
    if city_name and role:
        line = front_city(rng, role, city_name)
        if line:
            parts.append(line)
    parts.append("Речь о беде по имени «%s»." % calamity.name)
    return ("Их задержало: %s" % hold.key, " ".join(parts))


STEP_HELD = (
    "Землю по имени %(where)s заняли и стали держать.",
    "%(where_cap)s перешла к ним, и они в ней остались.",
    "Землю по имени %(where)s взяли без большого шума и посадили своих.",
)

STEP_RUINED = (
    "Землю по имени %(where)s прошли насквозь и оставили пустой.",
    "%(where_cap)s разорили и не стали держать: держать было нечего.",
    "По земле по имени %(where)s прошли, взяли что взяли и ушли дальше.",
)

ROLE_LINES = {
    dis.ROLE_GATE: "Через город по имени %s они и вошли: эти ворота потом "
                   "поминали в каждом своде.",
    dis.ROLE_FIRST: "Первым взяли город по имени %s, и весть о нём успела "
                    "дойти дальше, чем они.",
    dis.ROLE_KEEP: "Город по имени %s стал последним: за ним уже никого "
                   "не было.",
    dis.ROLE_SHELTER: "В город по имени %s сошлись те, кто ушёл, и город "
                      "стал вдвое больше себя.",
    dis.ROLE_STOOD: "Город по имени %s выстоял — и с этого дня считал себя "
                    "не таким, как соседи.",
    dis.ROLE_BOUGHT: "Город по имени %s откупился, и соседи не забыли ему "
                     "этого никогда.",
}


def front_step(rng, calamity, region, state: str, role: str,
               city_name: str = "") -> tuple:
    """Фронт сдвинулся на одну землю — и у главного города своя роль."""
    where = region.name if region is not None else "—"
    data = {"where": where, "where_cap": cap(where)}
    frames = STEP_RUINED if state == dis.LAND_RUINED else STEP_HELD
    lines = [cap(rng.choice(frames) % data)]
    if city_name and role:
        line = front_city(rng, role, city_name)
        if line:
            lines.append(line)
    lines.append("Шла тогда беда по имени «%s»." % calamity.name)
    return ("%s: %s" % (calamity.name, where), " ".join(lines))


def front_city(rng, role: str, city_name: str) -> str:
    """Строка о роли города — её вставляют туда, где о городе речь."""
    frame = ROLE_LINES.get(role)
    return (frame % city_name) if frame else ""


END_WON = (
    "Их выбили, но не отовсюду: %(where)s так и осталась за ними.",
    "Победу записали, а земли по имени %(where)s в ней не было.",
    "Отбились — и на том сошлись, что дальние земли уже не вернуть: %(where)s.",
)

END_LOST = (
    "Они остались: %(where)s теперь их, и это признали молча.",
    "Землю по имени %(where)s не вернули ни тогда, ни после.",
    "Кончилось тем, что границу передвинули: %(where)s отошла им.",
)

END_TAILS = (
    "Через век там говорили уже на другом наречии.",
    "Те, кто ушёл оттуда, звали себя по старой земле ещё триста лет.",
    "На картах это исправили не сразу и не везде.",
    "Своды обеих сторон считают этот год по-разному.",
)


def front_end(rng, calamity, kept, world, won: bool) -> tuple:
    """Чем кончился фронт: что осталось за чужими."""
    where = region_list(world, kept, limit=3)
    frames = END_WON if won else END_LOST
    text = "%s %s" % (cap(rng.choice(frames) % {"where": where}),
                      rng.choice(END_TAILS))
    return ("Что осталось за ними: %s" % where, text)


# ---------------------------------------------------------------------------
# Катастрофическая эпоха
# ---------------------------------------------------------------------------

ERA_FRAMES = (
    "Годы с %(from)d по %(to)d слились в одно время, и у времени нашлось "
    "имя: %(name)s.",
    "Позже эти годы перестали разбирать по бедам и стали звать одним "
    "словом: %(name)s (%(from)d–%(to)d).",
    "%(name)s — так назвали то, что шло с %(from)d по %(to)d год.",
)

ERA_COUNTS = (
    "Бед в нём было %(count)d, и каждая следующая ложилась на то, что "
    "оставила прежняя.",
    "Считают в нём %(count)d беды, но живших тогда это деление не "
    "занимало.",
    "Из %(count)d бед ни одна не была последней, и это и делало их одним "
    "временем.",
)

ERA_TOLLS = (
    "Не досчитались за это время %(souls)s.",
    "Счёт ушедших за эти годы — %(souls)s.",
    "Людей за это время не стало на %(souls)s.",
)

ERA_TAILS = (
    "Начало его в сводах разных народов стоит в разных годах, и спорить "
    "об этом перестали.",
    "Кончилось оно не победой, а тем, что беды перестали приходить.",
    "Тех, кто помнил его начало, к концу уже не было.",
    "Всё, что мир умел до него, он потом собирал заново.",
)


def era_closed(rng, era, world) -> tuple:
    """Время бед кончилось и получило имя."""
    data = {"name": era.name, "count": len(era.calamity_ids),
            "from": era.start.year,
            "to": era.end.year if era.end else era.start.year,
            "souls": souls(era.deaths)}
    lines = [cap(rng.choice(ERA_FRAMES) % data),
             rng.choice(ERA_COUNTS) % data]
    if era.deaths > 0:
        lines.append(rng.choice(ERA_TOLLS) % data)
    if era.regions:
        lines.append("Земли: %s." % region_list(world, era.regions, limit=4))
    if era.voices:
        said = "; ".join(item["оборот"] for item in era.voices[:4])
        lines.append("Имя у него не одно: %s." % said)
    lines.append(rng.choice(ERA_TAILS))
    return ("Время бед: %s" % era.name, " ".join(lines))


VERSION_FRAMES = (
    "О том, что это было, спорят до сих пор.",
    "Одного рассказа об этом нет и не было.",
    "Свести это к одной истории не удалось никому.",
)


def versions(rng, calamity, told: dict) -> tuple:
    """Шесть рассказов об одном, и ни один не отменяет остальных.

    Первая строка — правда, и она стоит первой не потому, что победила:
    просто с чем-то надо сравнивать остальные пять.
    """
    lines = [rng.choice(VERSION_FRAMES)]
    truth = told.get(dis.V_TRUE)
    if truth and truth != dis.UNKNOWN_CAUSE:
        lines.append("На деле причиной было вот что: %s." % truth)
        if not calamity.cause_known:
            lines.append("Этого мир так и не узнал.")
    else:
        # Бывает и так: настоящей причины не знал никто, и спорить было
        # не с чем — спорили всё равно.
        lines.append("Настоящей причины не назвал никто, и это не помешало "
                     "спорить.")
    for voice in dis.VERSIONS:
        if voice == dis.V_TRUE or voice not in told:
            continue
        lines.append("%s — %s." % (cap(voice), told[voice]))
    return ("Шесть рассказов о беде по имени «%s»" % calamity.name,
            " ".join(lines))


# ---------------------------------------------------------------------------
# Правило мира, исход и старый враг
# ---------------------------------------------------------------------------

RULE_FRAMES = (
    "После этого в мире переменилось само правило: %(rule)s.",
    "Считают, что с того года мир стал другим: %(rule)s.",
    "И это оказалось не последствием, а переменой: %(rule)s.",
)

RULE_TAILS = (
    "Спорить об этом было не с кем: видели все.",
    "Старые книги с того года стали врать, и переписать их не сумели.",
    "Те, кто помнил прежний порядок, к концу века вымерли.",
    "Дальше и вера, и обычай ссылались уже на это.",
)


def rule_changed(rng, calamity, rule: str, world) -> tuple:
    """Беда, после которой в мире переменилось само правило."""
    where = region_list(world, calamity.region_ids, limit=3)
    text = "%s %s Всё это — беда по имени «%s», прошедшая по землям %s." % (
        cap(rng.choice(RULE_FRAMES) % {"rule": rule}),
        rng.choice(RULE_TAILS), calamity.name, where)
    return ("Переменилось правило мира: %s" % rule, text)


REFUGE_FRAMES = (
    "Из земли по имени %(where)s ушли %(souls)s — и ушли не назад.",
    "%(where_cap)s опустела не только мёртвыми: %(souls)s снялись и пошли "
    "искать, где живут.",
    "Уходили семьями и целыми концами: из земли по имени %(where)s ушли "
    "%(souls)s.",
)

REFUGE_HOST = (
    "Приняли их в городе по имени %(host)s, и город стал больше себя.",
    "Дошли до города по имени %(host)s — дальше идти было некуда.",
    "Город по имени %(host)s открыл ворота, и об этом потом спорили.",
)

REFUGE_TAILS = (
    "Своими их там считали не сразу и не все.",
    "Через два поколения об этом помнили только по наречию в одном конце "
    "города.",
    "Тем, кто пришёл, дела не хватило, и это вышло городу боком.",
    "Половину пути не прошли, и о них летопись не говорит.",
    "Из тех, кто дошёл, назад не вернулся почти никто.",
)


def refuge(rng, calamity, region, host, leaving: int, world) -> tuple:
    """Исход из разорённой земли и город, который его принял."""
    where = region.name if region is not None else "—"
    data = {"where": where, "where_cap": cap(where),
            "souls": souls(leaving), "host": host.name}
    text = "%s %s %s Гнала их беда по имени «%s»." % (
        cap(rng.choice(REFUGE_FRAMES) % data),
        rng.choice(REFUGE_HOST) % data, rng.choice(REFUGE_TAILS),
        calamity.name)
    return ("Исход: %s" % where, text)


__all__ = ["omen", "prevented", "turn_point", "phase_turn", "response",
           "rule_changed", "refuge",
           "era_closed", "versions",
           "front_hold", "front_step", "front_city", "front_end",
           "scar_left", "scar_turn", "lore_lost", "lore_fragments",
           "lore_found"]
