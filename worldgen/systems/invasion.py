# -*- coding: utf-8 -*-
"""Нашествие: подсистема внутри бедствий, а не один из их видов.

`systems/calamity` ведёт вторжение как беду: тяжесть, земли, срок, урон.
`systems/disaster` добавил ему причину, фазы и фронт. Это — про то, что
делает нашествие историей, а не сводкой:

* **кто и отчего** — род пришедших согласован с причиной прихода, а
  причина не равна цели: изгнанные из своего мира ищут землю, вызванные
  магом жгут одну державу, а вернувшиеся требуют своё;
* **как это началось** — не «в тот год вторглись», а «пропали трое
  пастухов»; первая встреча часто вовсе не битва;
* **как шло** — цель меняется по ходу (столицу не взяли — стали брать
  деревни — сели на них), скрытый вождь открывается поздно;
* **как отвечали** — у каждой задетой державы своя стратегия, и соседи
  помнят, кто воевал, а кто платил;
* **чем кончилось** — шестнадцать исходов, и «истреблены» лишь один из
  них; двадцать три способа победы, из которых убить вождя — тоже один;
* **что осталось** — гнёзда, кладки, культы, смешанные дети и
  непризнанные права: из этого через века растут новые беды;
* **как назвали** — несколько имён на одно событие, каждое своим голосом.

Главное правило: захватчики не обязаны проиграть.
"""

from __future__ import annotations

from .. import catastrophe as cat
from .. import history
from .. import invasion as inv
from .. import narrative_invasion as texts


# Доля нашествий, у которых вождь сперва скрыт: годы идут как набеги
# чудовищ, а потом выясняется, что ими кто-то правит.
HIDDEN_LEADER = 0.3
HIDDEN_SHOW = (0.25, 0.7)   # в какой доле срока он открывается

# Как часто цель меняется по ходу и сколько раз.
GOAL_TURN_CHANCE = 0.45
GOAL_TURN_MAX = 2

# Сколько держав вообще успевают ответить и сколько остатков остаётся.
ANSWER_MAX = 4
REMNANT_MAX = 3
REMNANT_CHANCE = 0.55


# ---------------------------------------------------------------------------
# Рождение
# ---------------------------------------------------------------------------

def begin(ctx, calamity, spec, rng, year: int, date):
    """Нашествие рождается вместе с бедой — и сразу знает свою историю."""
    if spec.kind != cat.INVASION and spec.key not in inv.KIND_BY_SPEC:
        return None
    world = ctx.world

    kind_key = rng.weighted(list(inv.KIND_BY_SPEC.get(
        spec.key, ((inv.UNKNOWN_KIND, 1.0),))))
    nature = inv.INVADERS_BY_KEY[kind_key]

    cause = rng.weighted(list(inv.causes_for(kind_key)))
    goal = rng.weighted(list(inv.goals_for(kind_key, cause.key)))
    host = rng.weighted([(item, item.weight) for item in inv.HOSTS])
    entry, entry_about = rng.choice(inv.ENTRIES)
    sign = rng.choice(inv.FIRST_SIGNS)
    meet_key, meet_about, peaceful = rng.choice(inv.FIRST_MEETINGS)
    behavior, behavior_about = rng.choice(inv.BEHAVIORS)
    spread = rng.choice(inv.SPREAD_BY_KIND.get(kind_key, ("фронтом",)))

    # Ум и устроенность берутся от природы рода, но их сдвигает размер:
    # народ целиком идёт со старейшинами, а поток без конца — без всего.
    mind = nature.mind
    order = nature.order
    if host.key in ("поток без конца", "стая"):
        order = max(0, order - 1)
    if host.ranks:
        order = min(3, order + 1)
    if host.key == "один":
        order = 0

    invasion = world.add_invasion(
        calamity_id=calamity.id, kind=kind_key, started=date,
        mind=mind, order=order, host=host.key, ranks=list(host.ranks),
        cause=cause.key, cause_theirs=cause.theirs,
        goal=goal.key, goal_first=goal.key,
        entry=entry, entry_region=calamity.region_ids[0]
        if calamity.region_ids else "",
        first_sign=sign, first_meeting=meet_key, peaceful_start=peaceful,
        behavior=behavior, spread=spread,
    )
    invasion.notes.append("вошли так: %s" % entry_about)
    invasion.notes.append("первая встреча: %s" % meet_about)
    invasion.notes.append("вели себя так: %s" % behavior_about)
    invasion.notes.append("расходились так: %s"
                          % inv.SPREAD_BY_KEY.get(spread, ("", 1.0))[0])
    invasion.notes.append(inv.mind_line(mind, order))

    # Виноватый человек — только если причина человеческая. И он может
    # не понимать, что делает: маг открыл дверь, чтобы спасти город.
    if cause.human_fault:
        culprit, deed = rng.choice(inv.CULPRITS)
        invasion.culprit = culprit
        invasion.culprit_meant = culprit in ("культ", "сосед")
        invasion.notes.append("это устроил %s: %s" % (culprit, deed))

    # Вождь: он есть, если род держится вождя. Иногда он скрыт, и годы
    # идут как набеги, пока не выяснится, что ими правят.
    if calamity.leader_id and order >= 1:
        invasion.leader_id = calamity.leader_id
        if mind >= 2 and rng.chance(HIDDEN_LEADER):
            invasion.leader_hidden = True

    # Имя даётся по тому, что видно сразу: по месту, по явлению, по вождю
    # или сухо, по-державному. Остальные имена придут, когда всё кончится.
    invasion.title = _first_name(ctx, invasion, calamity, rng, year)
    if invasion.title:
        calamity.name = invasion.title
    return invasion


def _first_name(ctx, invasion, calamity, rng, year: int) -> str:
    """Имя, под которым это шло при современниках.

    Тёзок не нумеруем: «Третье Годы, Когда Небо Горело» — это не имя, а
    рассогласование. Занято — берём другое имя, у моделей их хватает.
    """
    world = ctx.world
    region = world.regions.get(invasion.entry_region)
    where = region.name if region is not None else ""
    leader = world.figures.get(invasion.leader_id)
    # Имена, которые стоят сами по себе («Годы Чёрного Дождя»), берутся
    # чаще: имя по месту потом вкладывается в оборот «беда по имени …», и
    # два «по имени» в одной строке читаются плохо.
    pairs = [("явление", 1.8), ("след", 1.2), ("знак", 1.0)]
    if where:
        pairs.append(("место", 0.9))
    if leader is not None and not invasion.leader_hidden:
        pairs.append(("вождь", 1.0))
    if world.active_polities:
        pairs.append(("держава", 1.0))

    taken = {item.name for item in world.calamities.values()
             if item.id != calamity.id}
    for _ in range(14):
        model = rng.weighted(pairs)
        if model == "место":
            name = texts.place_name(rng, where, invasion.kind)
        elif model == "вождь":
            name = texts.leader_name(rng, leader, invasion.kind)
        elif model == "держава":
            name = texts.state_name(rng, where, year)
        elif model == "след":
            name = rng.weighted(inv.names_for(inv.NAME_BY_MARK,
                                              invasion.kind))
        elif model == "знак":
            name = rng.weighted(inv.names_for(inv.NAME_BY_TOKEN,
                                              invasion.kind))
        else:
            name = rng.weighted(inv.names_for(inv.NAME_BY_SIGN,
                                              invasion.kind))
        if name and name not in taken:
            return name
    # Все имена разобраны — тогда имя даёт год, а не счёт по порядку.
    return texts.state_name(rng, where, year)


# ---------------------------------------------------------------------------
# Ход
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    """Год нашествия: цель может смениться, а скрытый вождь — открыться."""
    world = ctx.world
    for calamity_id in list(world.active_calamities):
        calamity = world.calamities[calamity_id]
        invasion = world.invasion_of(calamity_id)
        if invasion is None:
            continue
        plan = ctx.calamity_plans.get(calamity_id) or {}
        rng = ctx.rng("invasion", invasion.id, year)

        _show_leader(ctx, invasion, calamity, plan, rng, year)
        _turn_goal(ctx, invasion, calamity, rng, year)


def _show_leader(ctx, invasion, calamity, plan, rng, year: int) -> None:
    """Скрытый вождь открывается — и война становится другой войной."""
    if not invasion.leader_hidden or invasion.leader_shown:
        return
    start = calamity.start.year
    span = max(1, int(plan.get("duration", 10)))
    part = (year - start) / float(span)
    low, high = HIDDEN_SHOW
    if part < low or not rng.chance(0.3 if part < high else 0.8):
        return
    world = ctx.world
    invasion.leader_hidden = False
    invasion.leader_shown = int(year)
    leader = world.figures.get(invasion.leader_id)
    invasion.notes.append("%d: открылось, что ими правят" % year)
    title, text = texts.leader_shown(rng, invasion, calamity, leader, world)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="invasion_leader", title=title, text=text, importance=4,
        actors=[invasion.leader_id] if invasion.leader_id else None,
        subjects=[invasion.id, calamity.id],
        region_id=calamity.region_ids[0] if calamity.region_ids else "")


def _turn_goal(ctx, invasion, calamity, rng, year: int) -> None:
    """Цель меняется по ходу: это и есть развитие нашествия."""
    if len(invasion.goal_turns) >= GOAL_TURN_MAX:
        return
    if year - calamity.start.year < 4 or not rng.chance(GOAL_TURN_CHANCE / 10.0):
        return
    fits = [row for row in inv.GOAL_TURNS if row[1] == invasion.goal]
    if not fits:
        return
    why, was, now = rng.choice(fits)
    invasion.goal_turns.append({"год": int(year), "было": was, "стало": now,
                                "отчего": why})
    invasion.goal = now
    world = ctx.world
    title, text = texts.goal_turned(rng, invasion, calamity, why, was, now)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="invasion_goal", title=title, text=text, importance=3,
        subjects=[invasion.id, calamity.id],
        region_id=calamity.region_ids[0] if calamity.region_ids else "")


# ---------------------------------------------------------------------------
# Как отвечают державы
# ---------------------------------------------------------------------------

def answer(ctx, invasion, calamity, rng, year: int, date) -> None:
    """Каждая задетая держава отвечает по-своему — и соседи это помнят.

    Здесь не считается урон: его считает `systems/disaster.respond`. Здесь
    считается политика. Тот, кто воевал, не простит тому, кто платил; тот,
    кто навёл их на соседа, получит за это через век.
    """
    world = ctx.world
    nature = inv.INVADERS_BY_KEY.get(invasion.kind)
    talks = bool(nature and nature.talks and invasion.mind >= 2)

    hurt = [pid for pid in world.active_polities
            if pid in calamity.deaths_by_polity]
    if not hurt:
        hurt = [pid for pid in world.active_polities
                if set(world.polities[pid].region_ids) & set(calamity.region_ids)]
    if not hurt:
        return
    hurt = sorted(hurt)[:ANSWER_MAX]

    for polity_id in hurt:
        polity = world.polities.get(polity_id)
        if polity is None or polity.ended is not None:
            continue
        if any(row.get("держава") == polity_id for row in invasion.answers):
            continue
        pairs = []
        for item in inv.ANSWERS:
            if item.talks and not talks:
                continue
            if not _can(world, polity, item.needs):
                continue
            pairs.append((item, item.weight))
        if not pairs:
            continue
        item = rng.weighted(pairs)
        invasion.answers.append({"год": int(year), "держава": polity_id,
                                 "ответ": item.key, "вышло": ""})
        # Тот, кто откупился или навёл беду на соседа, платит за это не
        # деньгами: след ложится в ткань причин и держится веками.
        if item.grudge > 0:
            for other_id in hurt:
                if other_id == polity_id:
                    continue
                history.leave(world, history.GRUDGE, year, other_id, polity_id,
                              weight=min(1.0, 0.25 * item.grudge + 0.2),
                              note="как повели себя в беду по имени «%s»"
                                   % calamity.name)
        elif item.grudge < 0:
            for other_id in hurt:
                if other_id == polity_id:
                    continue
                history.leave(world, history.FAVOUR, year, other_id, polity_id,
                              weight=0.3,
                              note="звали на помощь в беду по имени «%s»"
                                   % calamity.name)
        line = "%s: %s" % (polity.name, item.about)
        if line not in invasion.notes:
            invasion.notes.append(line)

    if len(invasion.answers) >= 2:
        title, text = texts.answers_told(rng, invasion, calamity, world)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="invasion_answer", title=title, text=text, importance=3,
            subjects=[invasion.id, calamity.id],
            region_id=calamity.region_ids[0] if calamity.region_ids else "")


def _can(world, polity, need: str) -> bool:
    """Есть ли у державы то, без чего такой ответ невозможен."""
    if not need:
        return True
    if need == "войско":
        return polity.population > 4000
    if need == "казна":
        return polity.population > 6000
    if need == "чародеи":
        return any(figure.alive_at(0) is not None
                   and "чародей" in figure.roles
                   for figure in world.figures.values()) or bool(world.faiths)
    if need == "жрецы":
        return bool(polity.faith_id)
    if need == "сосед":
        return len(world.active_polities) > 1
    return True


# ---------------------------------------------------------------------------
# Чем кончилось
# ---------------------------------------------------------------------------

# Какой исход возможен при таком разрешении беды. Слева — то, чем беда
# кончилась по счёту `systems/calamity`, справа — что это значит для
# истории нашествия.
BY_RESOLUTION = {
    "hero": ((inv.OUT_DEFEATED, 2.0), (inv.OUT_DESTROYED, 1.0),
             (inv.OUT_HALF, 0.8)),
    "heroes": ((inv.OUT_DEFEATED, 2.0), (inv.OUT_DESTROYED, 1.0),
               (inv.OUT_HALF, 0.8)),
    "coalition": ((inv.OUT_DEFEATED, 2.0), (inv.OUT_EXILED, 1.0),
                  (inv.OUT_HALF, 0.6)),
    "sealed": ((inv.OUT_SEALED, 3.0), (inv.OUT_HALF, 0.8)),
    "driven_back": ((inv.OUT_REPULSED, 2.5), (inv.OUT_EXILED, 1.2),
                    (inv.OUT_HALF, 0.8)),
    "dispersed": ((inv.OUT_DEFEATED, 1.6), (inv.OUT_SEALED, 1.0),
                  (inv.OUT_HALF, 0.8)),
    "suppressed": ((inv.OUT_DEFEATED, 2.0), (inv.OUT_HELD, 1.0)),
    "tribute": ((inv.OUT_DEAL, 2.0), (inv.OUT_VASSAL, 1.2),
                (inv.OUT_HELD, 0.8)),
    "faded": ((inv.OUT_LEFT, 2.5), (inv.OUT_HALF, 1.0), (inv.OUT_BROKE, 0.8)),
    "burned_out": ((inv.OUT_LEFT, 1.6), (inv.OUT_HALF, 1.2),
                   (inv.OUT_BROKE, 1.0)),
    "endured": ((inv.OUT_HELD, 1.6), (inv.OUT_HALF, 1.2), (inv.OUT_DEAL, 0.8)),
    "adapted": ((inv.OUT_JOINED, 1.6), (inv.OUT_SETTLED, 1.4),
                (inv.OUT_HELD, 0.8)),
    "absorbed": ((inv.OUT_BECAME, 2.5), (inv.OUT_SETTLED, 1.5),
                 (inv.OUT_JOINED, 1.0)),
    "rains": ((inv.OUT_LEFT, 1.5), (inv.OUT_HALF, 1.0)),
    "reunited": ((inv.OUT_DEFEATED, 1.5), (inv.OUT_REPULSED, 1.0)),
    "shattered": ((inv.OUT_VASSAL, 1.5), (inv.OUT_SETTLED, 1.2),
                  (inv.OUT_HALF, 1.0)),
}

# Исходы, при которых люди проиграли: тогда выбирается вид капитуляции.
HUMAN_LOSS = (inv.OUT_VASSAL, inv.OUT_SETTLED, inv.OUT_JOINED, inv.OUT_BECAME)


def finish(ctx, invasion, calamity, spec, rng, year: int, date,
           resolution: str) -> None:
    """Исход, способ победы, капитуляция, остатки и остальные имена."""
    world = ctx.world
    nature = inv.INVADERS_BY_KEY.get(invasion.kind)
    talks = bool(nature and nature.talks and invasion.mind >= 2)

    pairs = list(BY_RESOLUTION.get(resolution, ((inv.OUT_HALF, 1.0),)))
    # Цель тянет исход за собой: пришедшие осесть и не выбитые — оседают,
    # а те, кто шёл насквозь, уходят сами.
    tug = {"осесть": (inv.OUT_SETTLED, 2.0),
           "поставить своё царство": (inv.OUT_VASSAL, 1.6),
           "пройти насквозь": (inv.OUT_LEFT, 2.0),
           "уйти домой": (inv.OUT_LEFT, 2.0),
           "взять дань": (inv.OUT_DEAL, 2.0),
           "забрать вещь": (inv.OUT_LEFT, 1.6),
           "найти одного": (inv.OUT_LEFT, 1.6),
           "вернуть своё": (inv.OUT_HELD, 1.6)}.get(invasion.goal)
    if tug is not None:
        pairs.append(tug)
    if nature is not None and nature.settles and talks:
        pairs.append((inv.OUT_BECAME, 0.7))
    if invasion.mind >= 2 and invasion.order >= 2 and rng.chance(0.25):
        pairs.append((inv.OUT_BROKE, 1.2))     # разумные ссорятся сами
    invasion.outcome = rng.weighted(pairs)

    invasion.way = _pick_way(invasion, rng, talks)
    invasion.decisive = rng.choice(texts.DECISIVE)
    if invasion.outcome in HUMAN_LOSS:
        invasion.surrender = rng.weighted(
            [(key, 1.0) for key, _ in inv.SURRENDERS])
        _surrender_hits(ctx, invasion, calamity, rng, year)

    _leave_remnants(ctx, invasion, calamity, rng, year)
    _later_names(ctx, invasion, calamity, rng, year)

    invasion.ended = date
    title, text = texts.invasion_ends(rng, invasion, calamity, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="invasion_ends",
        title=title, text=text,
        importance=min(5, 3 + calamity.severity // 2),
        subjects=[invasion.id, calamity.id],
        region_id=calamity.region_ids[0] if calamity.region_ids else "")


def _pick_way(invasion, rng, talks: bool) -> str:
    """Каким способом это кончилось. Убить вождя — только один из двадцати."""
    pairs = []
    for key, _, needs in inv.WAYS:
        if "вождь" in needs and not invasion.leader_id:
            continue
        if "речь" in needs and not talks:
            continue
        if "дверь" in needs and invasion.entry not in (
                "портал", "разлом", "призыв", "с той стороны", "из вещи"):
            continue
        if "гнездо" in needs and invasion.spread not in (
                "гнёздами", "размножением", "заражением"):
            continue
        weight = 1.0
        # Способ должен вязаться с исходом: запечатали — значит заперты.
        if invasion.outcome == inv.OUT_SEALED and key in ("запечатали",
                                                          "закрыли дверь"):
            weight = 6.0
        elif invasion.outcome == inv.OUT_DEAL and key in ("договорились",
                                                          "купили вождя",
                                                          "отвели в сторону"):
            weight = 6.0
        elif invasion.outcome == inv.OUT_BROKE and key in ("рассорили их",
                                                           "помогли они сами",
                                                           "переманили часть"):
            weight = 6.0
        elif invasion.outcome == inv.OUT_LEFT and key in ("дождались",
                                                          "перерезали корм",
                                                          "отвели в сторону"):
            weight = 5.0
        elif invasion.outcome in (inv.OUT_DESTROYED, inv.OUT_DEFEATED) \
                and key in ("убили вождя", "разорили гнездо", "сковали оружие",
                            "нашли слабое", "подняли древнее"):
            weight = 3.0
        elif invasion.outcome in HUMAN_LOSS and key in ("увели людей",
                                                        "вышло само",
                                                        "дождались"):
            weight = 4.0
        pairs.append((key, weight))
    return rng.weighted(pairs) if pairs else "вышло само"


def _surrender_hits(ctx, invasion, calamity, rng, year: int) -> None:
    """Капитуляция — это не слово в летописи, а положение дел."""
    world = ctx.world
    hurt = sorted(calamity.deaths_by_polity.items(),
                  key=lambda pair: (-pair[1], pair[0]))
    if not hurt:
        return
    polity = world.polities.get(hurt[0][0])
    if polity is None or polity.ended is not None:
        return
    line = "после беды по имени «%s»: %s" % (calamity.name, invasion.surrender)
    if line not in polity.notes:
        polity.notes.append(line)
    if invasion.surrender in ("дань", "вассалитет", "заложники"):
        polity.hunger = min(1.0, polity.hunger + 0.1)
    history.leave(world, history.YOKE, year, polity.id, weight=0.6,
                  note="чужое старшинство после беды по имени «%s»"
                       % calamity.name)


def _leave_remnants(ctx, invasion, calamity, rng, year: int) -> None:
    """Что осталось после них — и из чего через века вырастет новое."""
    _ = (ctx, year)
    if invasion.outcome == inv.OUT_DESTROYED and not rng.chance(0.25):
        return
    if not rng.chance(REMNANT_CHANCE + 0.1 * calamity.severity):
        return
    nature = inv.INVADERS_BY_KEY.get(invasion.kind)
    pairs = []
    for key, about, weight in inv.REMNANTS:
        if key == "кладка" and invasion.kind not in (inv.DRAGONS, inv.BEASTS,
                                                     inv.SWARM, inv.DEEP):
            continue
        if key == "смешанные" and not (nature and nature.settles):
            continue
        if key == "селение" and invasion.outcome in (inv.OUT_DESTROYED,
                                                     inv.OUT_EXILED):
            continue
        if key == "дверь" and invasion.entry not in (
                "портал", "разлом", "с той стороны", "призыв"):
            continue
        if key == "непризнанное право" and not (nature and nature.kin):
            continue
        pairs.append(((key, about), weight))
    if not pairs:
        return
    want = 1 + (1 if rng.chance(0.4) else 0) + (1 if calamity.severity >= 4
                                                and rng.chance(0.3) else 0)
    seen = set()
    for _ in range(min(REMNANT_MAX, want) * 2):
        if len(invasion.remnants) >= min(REMNANT_MAX, want):
            break
        key, about = rng.weighted(pairs)
        if key in seen:
            continue
        seen.add(key)
        region_id = rng.choice(calamity.region_ids) if calamity.region_ids \
            else ""
        invasion.remnants.append({"вид": key, "о чём": about,
                                  "земля": region_id})


def _later_names(ctx, invasion, calamity, rng, year: int) -> None:
    """Имена, которые дали, когда всё уже кончилось. У каждого свой голос."""
    world = ctx.world
    told = {}
    told[inv.VOICE_STATE] = texts.state_name(
        rng, _where(world, calamity), calamity.start.year)
    told[inv.VOICE_FOLK] = texts.folk_name(rng, invasion, calamity, world)
    ends = inv.NAME_BY_END.get(invasion.outcome)
    told[inv.VOICE_LATER] = rng.choice(ends) if ends else rng.weighted(
        inv.names_for(inv.NAME_BY_MARK, invasion.kind))
    if world.faiths and rng.chance(0.7):
        told[inv.VOICE_FAITH] = rng.choice(inv.NAME_FAITH_FRAMES)
    nature = inv.INVADERS_BY_KEY.get(invasion.kind)
    if nature is not None and nature.talks and rng.chance(0.8):
        told[inv.VOICE_ENEMY] = rng.choice(inv.NAME_ENEMY_FRAMES)
    if len(world.active_polities) > 1 and rng.chance(0.5):
        told[inv.VOICE_NEIGHBOUR] = rng.weighted(
            inv.names_for(inv.NAME_BY_MARK, invasion.kind))
    # Своё имя не повторяем чужим голосом: это было бы не «несколько
    # имён», а одно, записанное пять раз.
    invasion.names = {voice: name for voice, name in told.items()
                      if name and name != invasion.title}


def _where(world, calamity) -> str:
    for region_id in calamity.region_ids:
        region = world.regions.get(region_id)
        if region is not None:
            return region.name
    return ""


# ---------------------------------------------------------------------------
# Не кончилось
# ---------------------------------------------------------------------------

def close(ctx, total: int, date) -> None:
    """История кончилась, а нашествие — нет.

    Это лучше, чем закрывать всякий сюжет: мир, у которого на последнем
    году идёт война, честнее мира, где всё улажено к сроку.
    """
    world = ctx.world
    for calamity_id in list(world.active_calamities):
        invasion = world.invasion_of(calamity_id)
        if invasion is None or invasion.outcome:
            continue
        calamity = world.calamities.get(calamity_id)
        invasion.outcome = inv.OUT_GOING
        invasion.way = ""
        invasion.notes.append("на последнем году летописи это ещё шло")
        rng = ctx.rng("invasion", "close", invasion.id)
        _leave_remnants(ctx, invasion, calamity, rng, total)
        _later_names(ctx, invasion, calamity, rng, total)


__all__ = ["begin", "tick", "answer", "finish", "close"]
