# -*- coding: utf-8 -*-
"""Субъекты истории: одна система для крестьянина, дракона, демона и бога.

Здесь нет второго генератора личностей. Вес в истории по-прежнему считает
`systems/renown`, людские цели — `systems/lifepath`, зверей ведёт
`systems/monsters`, богов — `systems/divinity`. Эта система делает другое:
из всех, кто оставил след, собирает **единый исторический дossier** и
доводит до конца то, чего в остальных реестрах нет.

* **повышение, а не выдача.** Субъектом истории не назначают: им
  становятся. Безымянный демон, которого убил крестьянин, не получает
  записи вовсе. Тот, кто выжил, получил имя, собрал последователей и
  вернулся через пятьдесят лет, — получает;
* **появление не равно рождению.** Демона призвали, древнего разбудили,
  дух выделился из чужой смерти. И первое появление в летописи — это
  третье, отдельное событие: дракон жил четыре тысячи лет, а в летопись
  вошёл в тот год, когда напал на караван;
* **сроки деятельности.** Бессмертный существует тысячи лет, а
  вмешивается сорок. Между ними он спал, был запечатан или счёл смертных
  недостойными войны — и это названо;
* **возвращение.** Запечатанный не выбывает из истории: печать чинят
  каждый век, а потом её рвёт землетрясение. Вернувшийся — тот же самый
  субъект, и он может начать вторую свою войну;
* **нрав меняется с причиной.** Не «стал осторожен», а «проиграл тому,
  кого не считал за противника → потерял уверенность → перешёл от
  войны к сговору»;
* **цель не равна результату.** Хотел взять мир, не взял — и всё же
  извёл три державы, породил веру и оставил проклятую землю;
* **наследие и ступень памяти.** Смерть не убирает субъекта из истории:
  легендарным становятся после неё.
"""

from __future__ import annotations

from .. import narrative_subject as texts
from .. import races as races_mod
from .. import subject as sub


# Кого вообще заносить. Порог нарочно высокий: летопись на сорок тысяч
# имён — это не летопись, а перепись.
FROM_LEVEL = 5              # людей — от «государственного человека»
MONSTER_DEEDS = 3           # зверя — от трёх набегов или убитого героя
INVASION_FROM = 2           # вождя нашествия — от второй тяжести

# Как часто субъект вообще меняется: раз в век его перечитывают заново.
TURN_CHANCE = 0.3
TEMPER_MAX = 3
WISH_MAX = 3

# Возвращение. Запечатанный ждёт долго — и это должно быть долго.
RETURN_AFTER = 150
RETURN_CHANCE = 0.05
RETURN_MAX = 2
RETURN_KINDS = (sub.DEMON, sub.ANCIENT, sub.UNDEAD, sub.DRAGON, sub.VAMPIRE,
                sub.MAGICAL, sub.SPIRIT, sub.BEAST, sub.GOD)

# Поздняя опознанность: кто вёл ту войну, выясняют и через двести лет.
NAMED_LATE_CHANCE = 0.18


# ---------------------------------------------------------------------------
# Повышение: субъектом истории становятся
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    """Раз в десятилетие: кого занести, кого вести дальше, кто вернулся."""
    world = ctx.world
    # Кто уже занесён — одним просмотром реестра. Иначе на каждую тысячу
    # взвешенных имён пришлось бы столько же проходов по субъектам.
    taken = _taken(world)
    _from_invasions(ctx, year, taken)
    _from_monsters(ctx, year, taken)
    _from_deities(ctx, year, taken)
    _from_figures(ctx, year, taken)

    for subject in list(world.subjects.values()):
        rng = ctx.rng("subject", subject.id, year)
        _advance(ctx, subject, rng, year, period)
        _maybe_return(ctx, subject, rng, year)


def _taken(world) -> dict:
    """Привязки, за которыми субъект в летописи уже есть."""
    taken = {"figure_id": set(), "monster_id": set(),
             "deity_id": set(), "invasion_id": set()}
    for subject in world.subjects.values():
        for field, seen in taken.items():
            value = getattr(subject, field, "")
            if value:
                seen.add(value)
    return taken


def _from_invasions(ctx, year: int, taken: dict) -> None:
    """Вождь нашествия — субъект истории с того часа, как его увидели."""
    world = ctx.world
    for invasion in world.invasions.values():
        if invasion.started.year > year or not invasion.leader_id:
            continue
        if invasion.leader_hidden:
            continue          # его ещё не знают, значит и в летописи нет
        calamity = world.calamities.get(invasion.calamity_id)
        if calamity is None or calamity.severity < INVASION_FROM:
            continue
        if invasion.id in taken["invasion_id"]:
            continue
        figure = world.figures.get(invasion.leader_id)
        if figure is None:
            continue
        rng = ctx.rng("subject", "invader", invasion.id)
        kind = _kind_of_invader(invasion.kind)
        subject = _make(ctx, rng, year, taken,
                        name=figure.name, kind=kind,
                        figure_id=figure.id, invasion_id=invasion.id,
                        race_id=figure.race_id,
                        entry_why="повёл нашествие по имени «%s»"
                                  % (invasion.title or calamity.name))
        subject.wish_first = subject.wish = _wish_for(rng, kind, invasion.goal)
        subject.notes.append("пришёл с бедой по имени «%s»" % calamity.name)
        _tell_event(ctx, subject, rng, year)


def _from_monsters(ctx, year: int, taken: dict) -> None:
    """Именной зверь — субъект, если за ним есть дела, а не одно имя."""
    world = ctx.world
    for monster in world.monsters.values():
        if monster.born is None or monster.born.year > year:
            continue
        deeds = monster.raids + len(monster.heroes_eaten) * 2
        if deeds < MONSTER_DEEDS:
            continue
        if monster.id in taken["monster_id"]:
            continue
        rng = ctx.rng("subject", "beast", monster.id)
        kind = sub.DRAGON if "дракон" in (monster.breed or "") else sub.BEAST
        subject = _make(ctx, rng, year, taken,
                        name=monster.name, kind=kind,
                        monster_id=monster.id,
                        entry_why=texts.beast_entry(rng, monster))
        subject.wish_first = subject.wish = _wish_for(rng, kind, "")
        _tell_event(ctx, subject, rng, year)


def _from_deities(ctx, year: int, taken: dict) -> None:
    """Божество — субъект истории с первого своего явления."""
    world = ctx.world
    for deity in world.deities.values():
        if deity.revealed is None or deity.revealed.year > year:
            continue
        if deity.id in taken["deity_id"]:
            continue
        faith = world.faiths.get(deity.faith_id)
        if faith is None or faith.followers < 3000:
            continue          # бог без людей истории не делает
        rng = ctx.rng("subject", "god", deity.id)
        subject = _make(ctx, rng, year, taken,
                        name=deity.full_name, kind=sub.GOD,
                        deity_id=deity.id,
                        entry_why="впервые явился, и об этом записали")
        # Бог хочет не «веры вообще»: у него есть одна мысль, ради
        # которой он есть, и её ведёт `systems/divinity`.
        head = world.godhead_of(deity.id)
        subject.wish_first = subject.wish = (
            head.principle if head is not None and head.principle
            else "распространить свою веру")
        _tell_event(ctx, subject, rng, year)


def _from_figures(ctx, year: int, taken: dict) -> None:
    """Человек — субъект, если вес его дел уже сосчитан и он высок."""
    world = ctx.world
    for record in world.renowns.values():
        if record.level < FROM_LEVEL:
            continue
        if record.figure_id in taken["figure_id"]:
            continue
        figure = world.figures.get(record.figure_id)
        if figure is None:
            continue
        rng = ctx.rng("subject", "person", record.figure_id)
        race = races_mod.RACES_BY_ID.get(figure.race_id)
        subject = _make(ctx, rng, year, taken,
                        name=figure.name, kind=sub.PEOPLE,
                        figure_id=figure.id, race_id=figure.race_id,
                        entry_why=texts.person_entry(rng, record))
        subject.wish_first = subject.wish = _person_wish(ctx, figure)
        subject.rung = sub.RUNG_BY_LEVEL.get(record.level, sub.RUNG_HISTORIC)
        if race is not None:
            subject.notes.append("из народа: %s" % race.name)
        _lived_through(ctx, subject, rng, figure, year)


def _lived_through(ctx, subject, rng, figure, year: int) -> None:
    """Человека заносят в свод после смерти: его перемены уже позади.

    Вес дел считается по прожитой жизни, поэтому к часу записи человек
    обычно уже мёртв. Значит, и нрав его менялся при жизни, а не через
    двести лет после неё, и срок его деятельности кончился тогда же.
    """
    born = figure.birth.year if figure.birth else subject.entered.year
    died = figure.death.year if figure.death else year
    first = max(born, min(died, born + max(1, (died - born) // 4)))
    # Вошёл в летопись он не тогда, когда о нём вспомнили, а тогда, когда
    # впервые сделал что-то, о чём записали.
    event = ctx.world.event(ctx.world.event_about(figure.id))
    if event is not None and born <= event.date.year <= died:
        subject.entered = event.date
        first = event.date.year
    else:
        # Своего события у него не нашлось, но в свод он всё равно попал
        # при жизни, а не через век после смерти: вес дел считают потом,
        # а дела делались тогда.
        subject.entered = ctx.date_in(rng, first)
    subject.spans = [{"с": int(first), "по": int(died),
                      "чем занят": "делал то, за что его и помнят"}]

    span = max(0, died - first)
    turns = 0
    if span >= 12 and rng.chance(0.55):
        turns = 1 + (1 if span >= 40 and rng.chance(0.35) else 0)
    for step in range(turns):
        when = first + int(span * (step + 1) / float(turns + 1))
        _turn_temper(ctx, subject, rng, max(first, min(died, when)))
    if span >= 25 and rng.chance(0.3):
        _turn_wish(ctx, subject, rng, first + span // 2)

    if figure.death is not None and figure.death.year <= year:
        subject.status = sub.DEAD
        subject.ended = figure.death


def _mark(subject, year: int, what: str, world_w: int, self_w: int,
          future_w: int) -> None:
    """Одно дело — три разные оценки, и они нарочно не совпадают.

    Владыка демонов встретил девочку: мир этого не заметил, а он через
    семьдесят лет впервые усомнился в своей ненависти. Поэтому у всякого
    заметного дела стоит вес для мира, вес для него самого и вес для
    того, что будет после.
    """
    subject.marks.append({"год": int(year), "что": what,
                          "мир": int(world_w), "себе": int(self_w),
                          "вперёд": int(future_w)})


def _tie(subject, who: str, how: str, year: int) -> None:
    """Связь с тем, кто его позвал, держал или остановил."""
    if not who:
        return
    for row in subject.ties:
        if row.get("кто") == who and row.get("чем") == how:
            return
    subject.ties.append({"кто": who, "чем": how, "с какого года": int(year)})


def _tell_event(ctx, subject, rng, year: int) -> None:
    """Первая запись о субъекте: кто это, откуда и чем он попал в летопись."""
    world = ctx.world
    title, text = texts.subject_entered(rng, subject, world)
    world.add_event(
        date=subject.entered, era_index=world.era_index_at(year),
        kind="subject_entered", title=title, text=text, importance=3,
        actors=[subject.figure_id] if subject.figure_id else None,
        subjects=[subject.id], race_id=subject.race_id)


def _make(ctx, rng, year: int, taken: dict = None, **kwargs):
    """Общая часть всякого субъекта: появление, факты и первый срок."""
    world = ctx.world
    date = ctx.date_in(rng, year)
    subject = world.add_subject(entered=date, **kwargs)
    kind = subject.kind

    pairs = list(sub.ORIGIN_BY_KIND.get(kind, ((sub.ORIGIN_UNKNOWN, 1.0),)))
    subject.origin = rng.weighted(pairs)
    # Год появления известен только у тех, чьё появление вообще событие:
    # рождение, призыв, создание. Пробуждение древнего — нет.
    if subject.origin in (sub.BORN, sub.SUMMONED, sub.CREATED, sub.CONJURED,
                          sub.TRANSFORMED, sub.ASCENDED):
        figure = world.figures.get(subject.figure_id)
        if figure is not None and figure.birth is not None:
            subject.origin_year = figure.birth.year
        else:
            subject.origin_year = max(1, year - rng.randint(5, 60))
    if subject.origin in (sub.SUMMONED, sub.CREATED, sub.CONJURED):
        subject.origin_by, subject.origin_why = texts.caller(rng)

    # «Неизвестно» не значит «нет»: у каждого факта своё состояние.
    asks = sub.ASKS_BIRTH.get(kind, False)
    subject.facts = {
        "появление на свет": sub.FACT_KNOWN if subject.origin_year
        else (sub.FACT_UNKNOWN if asks else sub.FACT_NONE),
        "откуда он": sub.FACT_KNOWN if subject.origin_by
        else rng.weighted([(sub.FACT_UNKNOWN, 2.0), (sub.FACT_MYTH, 1.0),
                           (sub.FACT_DISPUTED, 0.8)]),
        "первое появление в летописи": sub.FACT_KNOWN,
        "чего он хотел": rng.weighted([(sub.FACT_KNOWN, 2.0),
                                       (sub.FACT_DISPUTED, 1.0),
                                       (sub.FACT_UNKNOWN, 0.5)]),
    }
    if not subject.entry_why:
        subject.entry_why = rng.weighted(list(sub.ENTRIES))
    _mark(subject, year, "вошёл в летопись: %s" % subject.entry_why,
          rng.randint(1, 3), rng.randint(1, 2), rng.randint(1, 2))
    if subject.origin_by:
        _tie(subject, subject.origin_by, "позвал его в мир",
             subject.origin_year or year)
    subject.temper = rng.choice(sub.TEMPERS)
    subject.status = sub.ACTING
    subject.spans.append({"с": int(year), "по": int(year),
                          "чем занят": "вошёл в летопись"})
    if taken is not None:
        # Вождь нашествия — заодно и человек из реестра: иначе его занесли
        # бы дважды, вторым разом как просто тяжёлое имя.
        for field, seen in taken.items():
            value = getattr(subject, field, "")
            if value:
                seen.add(value)
    return subject


def _kind_of_invader(kind: str) -> str:
    """Род пришедшего в понятиях нашествия — в понятия субъектов."""
    return {"драконы": sub.DRAGON, "демоны": sub.DEMON,
            "нежить": sub.UNDEAD, "великаны": sub.PEOPLE,
            "глубоководные": sub.PEOPLE, "древние": sub.ANCIENT,
            "дивный народ": sub.PEOPLE, "стихии": sub.MAGICAL,
            "пустота": sub.OTHER_KIND, "рой": sub.BEAST,
            "чудовища": sub.BEAST}.get(kind, sub.OTHER_KIND)


def _wish_for(rng, kind: str, goal: str) -> str:
    """Чего он хочет. У пришедшего с нашествием — то же, что у нашествия."""
    fits = [(wish, 1.0) for wish, kinds in sub.WISHES if kind in kinds]
    if goal:
        for wish, kinds in sub.WISHES:
            if kind in kinds and goal in wish:
                return wish
    if not fits:
        fits = [(wish, 1.0) for wish, _ in sub.WISHES]
    return rng.weighted(fits)


def _person_wish(ctx, figure) -> str:
    """У человека цель уже есть — её ведёт `systems/lifepath`.

    Своей цели сюда не выдумывают: если человек прожил свой путь, его
    желание взято оттуда целиком, вместе со всеми переменами.
    """
    path = ctx.world.path_of(figure.id)
    if path is not None and path.wish:
        return path.wish
    return "остаться в памяти тем, кем себя считал"


# ---------------------------------------------------------------------------
# Ход
# ---------------------------------------------------------------------------

def _advance(ctx, subject, rng, year: int, period: int) -> None:
    """Век субъекта: срок деятельности, перемена нрава, перемена цели."""
    if subject.status in (sub.DEAD, sub.RISEN):
        return
    if _gone(ctx.world, subject, year):
        return
    _keep_span(subject, year)
    if subject.status == sub.ACTING and rng.chance(TURN_CHANCE / 3.0):
        _turn_temper(ctx, subject, rng, year)
    if subject.status == sub.ACTING and rng.chance(TURN_CHANCE / 4.0):
        _turn_wish(ctx, subject, rng, year)
    # Бессмертный не воюет тысячу лет подряд: он умолкает, и у молчания
    # есть причина.
    if subject.status == sub.ACTING and subject.kind != sub.PEOPLE \
            and year - int(subject.spans[-1].get("с", year)) > 60 \
            and rng.chance(0.25):
        _go_quiet(ctx, subject, rng, year)


def _gone(world, subject, year: int) -> bool:
    """Тот, кого уже убили, ничего больше не решает.

    Человек попадает в свод после смерти, зверя убивают на глазах у
    летописца — и ни тот, ни другой не должны после этого менять нрав.
    """
    figure = world.figures.get(subject.figure_id)
    monster = world.monsters.get(subject.monster_id)
    for died in (figure.death if figure is not None else None,
                 monster.ended if monster is not None else None):
        if died is not None and died.year <= year:
            # Если он к тому часу уже молчал, срок деятельности не
            # продлевается смертью: его убили спящим, а не за делом.
            if subject.status == sub.ACTING and subject.spans:
                subject.spans[-1]["по"] = int(died.year)
            if subject.quiet and not subject.quiet[-1].get("по"):
                subject.quiet[-1]["по"] = int(died.year)
            subject.status = sub.DEAD
            subject.ended = died
            return True
    return False


def _keep_span(subject, year: int) -> None:
    if subject.status != sub.ACTING or not subject.spans:
        return
    subject.spans[-1]["по"] = int(year)


def _turn_temper(ctx, subject, rng, year: int) -> None:
    """Нрав переменился, и названо, отчего именно."""
    if len(subject.temper_turns) >= TEMPER_MAX:
        return
    was = subject.temper
    now = rng.choice([item for item in sub.TEMPERS if item != was])
    inner = rng.choice(sub.INNER)
    why = rng.choice(texts.TEMPER_CAUSES)
    subject.temper_turns.append({"год": int(year), "было": was, "стало": now,
                                 "отчего": why, "внутри": inner})
    subject.temper = now
    _mark(subject, year, "переменился: %s" % why,
          rng.randint(0, 1), 3, rng.randint(1, 2))
    world = ctx.world
    title, text = texts.temper_turned(rng, subject, was, now, why, inner)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="subject_temper", title=title, text=text, importance=2,
        actors=[subject.figure_id] if subject.figure_id else None,
        subjects=[subject.id])


def _turn_wish(ctx, subject, rng, year: int) -> None:
    """Цель переменилась — и это путь, даже если субъект бессмертен."""
    if len(subject.wish_turns) >= WISH_MAX:
        return
    fits = [row for row in sub.WISH_TURNS if row[1] == subject.wish]
    if not fits:
        return
    why, was, now = rng.choice(fits)
    subject.wish_turns.append({"год": int(year), "было": was, "стало": now,
                               "отчего": why})
    subject.wish = now
    subject.wish_state = sub.GOAL_SWAPPED
    _mark(subject, year, "стал хотеть другого: %s" % now,
          rng.randint(1, 2), 3, rng.randint(2, 3))
    world = ctx.world
    title, text = texts.wish_turned(rng, subject, why, was, now)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="subject_wish", title=title, text=text, importance=3,
        actors=[subject.figure_id] if subject.figure_id else None,
        subjects=[subject.id])


def _go_quiet(ctx, subject, rng, year: int) -> None:
    """Он умолк — и это не смерть, а перерыв с причиной."""
    # Дважды подряд «был не в этом мире» — не история, а заевшая кость.
    used = {row.get("отчего", "") for row in subject.quiet}
    left = [item for item in sub.QUIET_REASONS if item not in used]
    why = rng.choice(left or list(sub.QUIET_REASONS))
    subject.spans[-1]["по"] = int(year)
    subject.quiet.append({"с": int(year), "по": 0, "отчего": why})
    subject.status = rng.weighted([(sub.DORMANT, 2.0), (sub.MISSING, 1.2),
                                   (sub.EXILED, 0.8)])
    subject.notes.append("%d: %s" % (year, why))
    _mark(subject, year, "умолк: %s" % why,
          rng.randint(2, 3), rng.randint(0, 2), 3)
    world = ctx.world
    title, text = texts.went_quiet(rng, subject, why)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="subject_quiet", title=title, text=text, importance=2,
        subjects=[subject.id])


# ---------------------------------------------------------------------------
# Возвращение
# ---------------------------------------------------------------------------

def _maybe_return(ctx, subject, rng, year: int) -> None:
    """Запечатанный не выбывает из истории — он ждёт.

    Вернувшийся не второй персонаж через четыреста лет, а тот же самый: у
    него новый срок деятельности и старая цель, к которой он шёл.
    """
    if subject.status not in sub.CAN_RETURN or subject.kind not in RETURN_KINDS:
        return
    if len(subject.spans) > RETURN_MAX:
        return          # третье возвращение обесценивает первые два
    since = int(subject.quiet[-1]["с"]) if subject.quiet else \
        subject.entered.year
    if year - since < RETURN_AFTER or not rng.chance(RETURN_CHANCE):
        return
    world = ctx.world
    if subject.quiet:
        subject.quiet[-1]["по"] = int(year)
    subject.status = sub.ACTING
    subject.spans.append({"с": int(year), "по": int(year),
                          "чем занят": "вернулся"})
    how = rng.choice(texts.RETURN_WAYS)
    subject.notes.append("%d: вернулся — %s" % (year, how))
    _mark(subject, year, "вернулся: %s" % how, 3, rng.randint(2, 3),
          rng.randint(1, 3))

    title, text = texts.returned(rng, subject, how, world)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="subject_return", title=title, text=text, importance=4,
        actors=[subject.figure_id] if subject.figure_id else None,
        subjects=[subject.id])

    # Тот, кто приходил с войском, приходит с войском и во второй раз.
    if subject.invasion_id and rng.chance(0.5):
        _second_coming(ctx, subject, rng, year)


def _second_coming(ctx, subject, rng, year: int) -> None:
    """Вторая его война: та же беда, тот же вождь, другая летопись."""
    world = ctx.world
    old = world.invasions.get(subject.invasion_id)
    calamity = world.calamities.get(old.calamity_id) if old else None
    if calamity is None:
        return
    from . import calamity as calamity_system
    fresh = calamity_system.start_named(
        ctx, year, calamity.key, rng,
        severity=max(2, calamity.severity - 1),
        note="вернулся тот же: %s" % subject.name)
    if fresh is None:
        return
    fresh.leader_id = subject.figure_id
    invasion = world.invasion_of(fresh.id)
    if invasion is not None:
        invasion.leader_id = subject.figure_id
        invasion.notes.append("это второй его приход")
        subject.invasion_id = invasion.id
    subject.notes.append("%d: начал свою вторую войну" % year)


# ---------------------------------------------------------------------------
# Итог
# ---------------------------------------------------------------------------

def close(ctx, total: int) -> None:
    """Конец истории: чем кончил, что оставил и на какой ступени памяти.

    Цель не равна результату: хотел взять мир, не взял — и всё же оставил
    державу, веру, проклятую землю и последователей.
    """
    world = ctx.world
    for subject in world.subjects.values():
        rng = ctx.rng("subject", "close", subject.id)
        _keep_span(subject, min(total, subject.spans[-1].get("по", total))
                   if subject.spans else total)
        _end_of(ctx, subject, rng, total)
        _fix_entry(subject)
        _ties_of(ctx, subject)
        _legacy_of(ctx, subject, rng)
        _rung_of(ctx, subject, rng, total)
        _wish_end_of(subject, rng)
        _told_of(ctx, subject, rng)
        _named_late(ctx, subject, rng, total)


def _end_of(ctx, subject, rng, total: int) -> None:
    world = ctx.world
    figure = world.figures.get(subject.figure_id)
    if figure is not None and figure.death is not None:
        subject.end = sub.END_KILLED if figure.death_cause else sub.END_OLD
        subject.ended = figure.death
        subject.status = sub.DEAD
        _mark(subject, figure.death.year, "кончил так: %s" % subject.end,
              rng.randint(2, 3), 3, rng.randint(1, 3))
        return
    monster = world.monsters.get(subject.monster_id)
    if monster is not None and monster.ended is not None:
        subject.end = sub.END_KILLED
        subject.ended = monster.ended
        subject.status = sub.DEAD
        _mark(subject, monster.ended.year, "кончил так: убит", 3, 3,
              rng.randint(1, 3))
        return
    if subject.status in (sub.DORMANT, sub.MISSING, sub.EXILED):
        subject.end = {sub.DORMANT: sub.END_SEALED,
                       sub.MISSING: sub.END_UNKNOWN,
                       sub.EXILED: sub.END_BANISHED}[subject.status]
        return
    pairs = list(sub.END_BY_KIND.get(subject.kind, ((sub.END_UNKNOWN, 1.0),)))
    subject.end = rng.weighted(pairs)
    subject.status = sub.END_TO_STATUS.get(subject.end, subject.status)
    _mark(subject, subject.ended.year if subject.ended else total,
          "кончил так: %s" % subject.end, 3, 3, rng.randint(1, 3))


def _ties_of(ctx, subject) -> None:
    """С кем он связан: кто его звал и кто ему отвечал.

    Державы, которые решали, что с ним делать, — такая же часть его
    истории, как его собственные дела: именно они его и остановили.
    """
    world = ctx.world
    invasion = world.invasions.get(subject.invasion_id)
    if invasion is None:
        return
    for row in invasion.answers:
        polity = world.polities.get(row.get("держава", ""))
        if polity is None:
            continue
        _tie(subject, polity.name, "отвечала ему делом",
             int(row.get("год", subject.entered.year)))


def _fix_entry(subject) -> None:
    """Сторож: в летопись нельзя попасть позже собственного конца.

    Бывает, что первой записью о существе стала весть о его гибели —
    тогда день гибели и есть день, когда о нём узнали.
    """
    if subject.ended is not None \
            and subject.ended.ordinal < subject.entered.ordinal:
        subject.entered = subject.ended
        if subject.spans:
            subject.spans[0]["с"] = int(subject.ended.year)


def _legacy_of(ctx, subject, rng) -> None:
    """Смерть не убирает субъекта из истории: она оставляет наследие."""
    if subject.legacy:
        return
    world = ctx.world
    if rng.chance(0.12):
        # Бывает и так: гремел, а не осталось ничего, кроме имени в своде.
        subject.notes.append("следа за ним не осталось никакого")
        return
    want = 1 + (1 if rng.chance(0.55) else 0) + (1 if rng.chance(0.3) else 0)
    seen = set()
    for _ in range(want * 3):
        if len(subject.legacy) >= want:
            break
        kind = rng.choice(sub.LEGACY_KINDS)
        if kind in seen:
            continue
        seen.add(kind)
        subject.legacy.append({"род": kind,
                               "что": rng.choice(sub.LEGACIES[kind])})
    if subject.legacy:
        title, text = texts.legacy_told(rng, subject, world)
        year = subject.ended.year if subject.ended else world.total_years
        world.add_event(
            date=subject.ended or ctx.date_in(rng, year),
            era_index=world.era_index_at(year), kind="subject_legacy",
            title=title, text=text, importance=3,
            actors=[subject.figure_id] if subject.figure_id else None,
            subjects=[subject.id])


def _rung_of(ctx, subject, rng, total: int) -> None:
    """Ступень памяти. Легендарным становятся после смерти, а не до."""
    world = ctx.world
    record = world.renown_of(subject.figure_id) if subject.figure_id else None
    level = max(record.level, record.peak_level) if record is not None else 0
    if not level:
        # У нелюдей веса по делам никто не считал: ступень берётся от
        # того, сколько за ним следов и сколько он вообще действовал.
        level = min(10, 2 + len(subject.legacy) + len(subject.spans)
                    + (2 if subject.kind in (sub.GOD, sub.ANCIENT) else 0))
    subject.rung = sub.RUNG_BY_LEVEL.get(level, sub.RUNG_HISTORIC)
    # Мифическим не становятся при жизни: для этого нужно, чтобы не
    # осталось тех, кто помнил.
    if subject.rung == sub.RUNG_MYTH and subject.status in (sub.ALIVE,
                                                            sub.ACTING):
        subject.rung = sub.RUNG_LEGEND
    # И не раньше, чем пройдут века: пока живы внуки очевидцев, человек
    # остаётся человеком, о котором спорят, а не мифом.
    if subject.rung == sub.RUNG_MYTH:
        since = total - (subject.ended.year if subject.ended
                         else subject.entered.year)
        if since < 500:
            subject.rung = sub.RUNG_LEGEND


def _wish_end_of(subject, rng) -> None:
    """Цель не равна итогу: чаще всего он получил не то, чего хотел.

    Тяжёлое имя чаще добивается своего — но и цена у него выше; лёгкое
    чаще оставляет дело на середине. Полностью добившийся своего —
    редкость, иначе история мира читалась бы как список исполненных
    желаний.
    """
    heavy = subject.rung in (sub.RUNG_LEGEND, sub.RUNG_MYTH)
    pairs = [
        (sub.GOAL_HALF, 3.0),
        (sub.GOAL_FAILED, 2.6 if not heavy else 1.4),
        (sub.GOAL_DONE, 1.6 if heavy else 0.7),
        (sub.GOAL_COST, 1.4 if heavy else 0.8),
        (sub.GOAL_LEFT, 1.2),
        (sub.GOAL_AFTER, 0.9),
        (sub.GOAL_IMPOSSIBLE, 0.7),
    ]
    if subject.status in (sub.ALIVE, sub.ACTING, sub.DORMANT, sub.MISSING):
        pairs.append((sub.GOAL_GOING, 2.0))
    subject.wish_state = rng.weighted(pairs)


def _told_of(ctx, subject, rng) -> None:
    """Как об этом рассказывают. Объективно он запечатан — а в народе убит."""
    if subject.told or not subject.end:
        return
    told = {"как было": subject.end}
    for who, _ in sub.TELLERS:
        if who == "как было":
            continue
        rows = sub.TELLER_TWISTS.get(who, ())
        if rows and rng.chance(0.6):
            told[who] = rng.choice(rows)
    if len(told) >= 3:
        subject.told = told


def _named_late(ctx, subject, rng, total: int) -> None:
    """Кто вёл ту войну, могли выяснить и через двести лет."""
    if subject.named_year or subject.kind == sub.PEOPLE:
        return
    if not rng.chance(NAMED_LATE_CHANCE):
        return
    world = ctx.world
    gap = rng.randint(80, 400)
    year = min(total, subject.entered.year + gap)
    if year <= subject.entered.year:
        return
    subject.named_year = int(year)
    subject.named_how = rng.choice(texts.NAMED_WAYS)
    subject.facts["кто это был"] = sub.FACT_DISPUTED
    title, text = texts.named_late(rng, subject)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="subject_named", title=title, text=text, importance=3,
        subjects=[subject.id])


__all__ = ["upkeep", "close", "FROM_LEVEL"]
