# -*- coding: utf-8 -*-
"""Следы беды: как мир копит собственную археологию.

Беда кончилась — и дальше начинается её вторая жизнь. Она ложится в
землю братскими могилами, в стену — половиной фрески, в говор — чужим
словом, в деревню — запретом входить в пещеру. Летопись ветшает, имена
стираются, а следы остаются и живут своей жизнью: ветшают, находятся,
толкуются вкривь и изредка просыпаются.

Три правила держат эту систему:

* **След не обязан объяснять беду — он обязан позволить её
  восстановить.** Поэтому у следа есть вес свидетельства и отдельно —
  правдивость: державный рельеф говорит много и врёт тоже много.
* **Чем дальше беда, тем меньше от неё вещей и тем больше эха.** Стена
  рушится за века, а праздник, табу и имя рода живут дольше самой памяти
  о причине. Это прямо в скорости ветшания по родам.
* **Не всякий след — приключение.** Девять следов из десяти просто
  исторические. Живой — тот, за которым что-то стоит, — редкость, и
  проснуться он может лишь однажды.

Соседние системы здесь не повторяются: шрам земли ставит
`systems/disaster`, спящую угрозу — `systems/calamity` (реликвии), место
истории — `systems/sites`. Эта система добавляет к ним слой, который
никто не вёл: что из беды дойдёт до потомков и что они смогут из этого
вычитать.
"""

from __future__ import annotations

from .. import narrative_remains as texts
from .. import remains as cat


# Сколько следов оставляет беда. Лёгкая не оставляет ничего: через век о
# ней не помнит даже соседняя земля.
IMPRINT_FROM = 2
TRACE_COUNT = {2: (1, 2), 3: (2, 4), 4: (4, 6), 5: (5, 8)}

# Ступень «живости»: за большинством следов не стоит ничего.
LIVE_WEIGHTS = ((0, 5.0), (1, 2.5), (2, 1.2), (3, 0.9), (4, 0.9),
                (6, 0.25))
LIVE_KINDS = (cat.SEAL, cat.SURVIVOR, cat.THING, cat.BUILT, cat.GROUND)

# Ветшание. За тысячу лет камень теряет полтора шага из четырёх, а
# обычай — меньше полушага: в этих двух числах и лежит всё правило «чем
# дальше беда, тем меньше от неё вещей и тем больше эха».
DECAY_RATE = 0.015          # шагов за десятилетие при обычной скорости
DECAY_AGE = 3000.0          # насколько старость ускоряет распад

# Находки. Забытый след находят тем чаще, чем ближе к нему живут.
FIND_BASE = 0.0025
FIND_PER_TOWN = 0.001
FIND_MAX = 0.03
# Обычай не находят — им живут. Учёный не откапывает праздник, он
# докапывается, откуда тот пошёл, и это случается куда реже.
LIVING_KINDS = (cat.CUSTOM, cat.BLOOD, cat.FAITH_MARK)
EXPLAIN_CHANCE = 0.0004

# Толкование. Найденный след сперва понимают как придётся.
READING_CHANCE = 0.55
QUARREL_CHANCE = 0.3

# Эхо: живой след просыпается — но только однажды и не сразу.
ECHO_AFTER = 200
ECHO_CHANCE = {4: 0.22, 5: 0.3, 6: 0.4}
ECHO_SLOW = 0.006           # и потом раз в десятилетие, пока не отзовётся

# Сколько веса нужно, чтобы вопрос считался решённым.
SURE_AT = 0.9
LIKELY_AT = 0.45
DISPUTED_AT = 0.18

# Пока беду помнят живые и читается свод, восстанавливать нечего: и так
# известно. Память держится век-полтора, свод — дольше, но не вечно.
MEMORY_SPAN = 800.0
MEMORY_WEIGHTS = {
    cat.Q_WHEN: 1.6, cat.Q_SCALE: 1.3, cat.Q_WHO: 1.2, cat.Q_END: 1.2,
    cat.Q_WHERE: 1.1, cat.Q_LEADER: 0.8, cat.Q_WHY: 0.7, cat.Q_NOW: 0.6,
}


# ---------------------------------------------------------------------------
# Отпечаток: что беда оставляет после себя
# ---------------------------------------------------------------------------

def imprint(ctx, calamity, spec, rng, year: int, date) -> None:
    """Беда кончилась — мир получает её отпечаток.

    Следов тем больше, чем тяжелее была беда, но набор их решает не
    тяжесть, а природа: у мора нет оружия чужой ковки, у роя — надгробия
    с именем вождя, а у державы, которой не было, — указа о запрете.
    """
    world = ctx.world
    if calamity.severity < IMPRINT_FROM:
        return
    if world.traces_of(calamity.id):
        return                      # отпечаток кладётся один раз

    has = _what_there_was(world, calamity)
    rows = cat.traces_for(calamity.key, calamity.kind, has)
    if not rows:
        return
    low, high = TRACE_COUNT.get(min(5, calamity.severity), (1, 2))
    want = rng.randint(low, high)

    made = []
    used = set()
    for _ in range(want * 3):
        if len(made) >= want:
            break
        kind = rng.weighted(rows)
        if kind.key in used:
            continue
        used.add(kind.key)
        made.append(_lay(ctx, calamity, kind, rng, year, date))

    if not made:
        return
    # Одно событие на весь отпечаток: летопись не пишет по записи на
    # каждый черепок, она пишет, что после этого осталось.
    title, text = texts.imprint_left(rng, calamity, made, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="calamity_traces",
        title=title, text=text, importance=2,
        subjects=[calamity.id], region_id=calamity.region_ids[0],
        race_id=calamity.race_id, causes=_roots(world, calamity))


def _roots(world, calamity) -> list:
    """Причина события — событие, а не сама беда.

    В ткани причин стоят номера событий: беда попадает туда через то
    событие, в котором её впервые назвали. Номер самой беды здесь был бы
    ссылкой в пустоту — и проверка причин её честно ловила.
    """
    if calamity is None:
        return []
    root = world.event_about(calamity.id)
    return [root] if root else []


def _what_there_was(world, calamity) -> tuple:
    """Что вообще было в этой беде: город, держава, войско, вождь, вера.

    След не может остаться от того, чего не было. Проверяется по самому
    миру, а не по виду беды: держава могла и не дожить до того года.
    """
    has = []
    lands = set(calamity.region_ids)
    year = calamity.end.year if calamity.end else calamity.start.year
    for settlement in world.settlements.values():
        # Город должен был стоять там и тогда: развалины, выросшие через
        # век после беды, её следов не оставляют.
        if settlement.region_id in lands \
                and settlement.founded.year <= year:
            has.append("город")
            break
    if calamity.polity_ids or world.active_polities:
        has.append("держава")
    if calamity.kind in ("invasion", "religious", "political"):
        has.append("войско")
    if calamity.leader_id:
        has.append("вождь")
    if world.faiths:
        has.append("вера")
    return tuple(has)


def _lay(ctx, calamity, kind, rng, year: int, date):
    """Один след: что это, где лежит и что за ним стоит."""
    world = ctx.world
    region_id = rng.choice(calamity.region_ids) if calamity.region_ids else ""
    trace = world.add_trace(
        key=kind.key, kind=kind.kind, name=texts.trace_name(rng, kind, world,
                                                            region_id),
        calamity_id=calamity.id, region_id=region_id, made=date,
        direct=kind.direct, evidence=kind.evidence, truth=kind.truth,
        says=kind.says, answers=list(kind.answers))

    # Печать и уцелевший — не просто следы: у них есть причина, по
    # которой они вообще есть, и она переживает саму память о беде.
    if kind.kind == cat.SEAL:
        trace.reason = rng.choice(cat.SEAL_REASONS)
        trace.belief = rng.choice(cat.SEAL_BELIEFS)
    elif kind.kind == cat.SURVIVOR:
        trace.reason = rng.choice(cat.SURVIVAL_REASONS)
    elif kind.key == "руина многих жизней":
        _stack_layers(trace, rng, year)

    if kind.kind in LIVING_KINDS:
        # Праздник, род и обряд не лежат в земле: ими живут, не помня
        # отчего. Забыта тут не сама вещь, а её причина.
        trace.knowledge = cat.LOCAL
        trace.belief = rng.choice(cat.READINGS)
    trace.life = _life_for(kind, calamity, rng)
    # Спящая угроза в мире уже есть — реликвия беды. Живой след не заводит
    # вторую, а берёт ту же: угроза в мире должна быть одна.
    if trace.life >= 4:
        for relic in world.relics.values():
            if relic.calamity_id == calamity.id:
                trace.relic_id = relic.id
                break
    if trace.life >= 4 and rng.chance(0.4):
        trace.lost = rng.weighted([(cat.LOST_UNKNOWN, 2.0),
                                   (cat.LOST_LEGEND, 1.2),
                                   (cat.LOST_SHUT, 1.5)])
    return trace


def _life_for(kind, calamity, rng) -> int:
    """Насколько за следом что-то стоит. Обычно — ничего."""
    if kind.kind not in LIVE_KINDS:
        return rng.weighted([(0, 8.0), (1, 2.0), (2, 0.8)])
    pairs = [(value, weight * (1.0 + calamity.severity / 8.0))
             if value >= 4 else (value, weight)
             for value, weight in LIVE_WEIGHTS]
    return rng.weighted(pairs)


def _stack_layers(trace, rng, year: int) -> None:
    """Слои одной руины: храм, крепость, обитель — одно поверх другого."""
    left = list(cat.RUIN_LAYERS)
    count = rng.randint(3, 5)
    # У мира нет годов до первого: руина, заложенная «за девятьсот лет
    # до», в молодом мире упёрлась бы в отрицательный год.
    when = max(1, year - rng.randint(200, 900))
    for _ in range(count):
        if not left:
            break
        row = left.pop(0) if rng.chance(0.55) else rng.choice(left)
        if row in [item.get("что") for item in trace.layers]:
            continue
        trace.layers.append({"год": int(when), "что": row})
        when += rng.randint(40, 260)
        if when > year:
            break


# ---------------------------------------------------------------------------
# Ветшание
# ---------------------------------------------------------------------------

def age(ctx, year: int, period: int) -> None:
    """Век за веком: камень ветшает, обычай держится.

    Это и есть главное правило всей системы: чем дальше беда, тем меньше
    от неё вещей и тем больше эха. Скорость ветшания взята по роду следа,
    поэтому братская могила переживает стену, а пословица — их обеих.
    """
    world = ctx.world
    scale = period / 10.0
    for trace in world.traces.values():
        if trace.state == cat.GONE or trace.made is None:
            continue
        span = year - trace.made.year
        if span < 60:
            continue
        rng = ctx.rng("remains", "age", trace.id, year)
        speed = cat.DECAY_BY_KIND.get(trace.kind, 1.0)
        chance = DECAY_RATE * speed * (0.6 + span / DECAY_AGE) * scale
        if not rng.chance(min(0.4, chance)):
            continue
        order = list(cat.STATES)
        index = order.index(trace.state) if trace.state in order else 0
        if index + 1 >= len(order):
            continue
        # Найденный и разобранный учёными след не теряется бесследно:
        # с него хотя бы сняли список.
        if order[index + 1] == cat.GONE and trace.knowledge == cat.STUDIED \
                and rng.chance(0.6):
            trace.notes.append("сам он утрачен, но списан учёными до того")
        trace.state = order[index + 1]
        if trace.state == cat.GONE:
            trace.notes.append("%d: от него не осталось ничего" % year)
            # Рассыпавшаяся печать — это не «следа не стало». Это то, что
            # она держала, перестало быть удержанным.
            if trace.kind == cat.SEAL and trace.life >= 4:
                trace.notes.append("и держать стало нечем")
                _echo(ctx, trace, rng, year, ctx.date_in(rng, year))

    # Живой след отзывается не только в час находки: печать могут
    # потревожить и через триста лет после того, как её нашли.
    for trace in list(world.traces.values()):
        if trace.life not in (4, 6) or trace.made is None:
            continue
        if trace.knowledge == cat.FORGOTTEN or trace.state == cat.GONE:
            continue
        if year - trace.made.year < ECHO_AFTER:
            continue
        rng = ctx.rng("remains", "echo", trace.id, year)
        if rng.chance(ECHO_SLOW * scale):
            _echo(ctx, trace, rng, year, ctx.date_in(rng, year))


# ---------------------------------------------------------------------------
# Находки
# ---------------------------------------------------------------------------

def find(ctx, year: int, period: int) -> None:
    """Кто-то находит забытый след — и с этого часа он говорит.

    Находят тем чаще, чем ближе живут: в пустой земле хоть целый город
    под слоем пепла, а находить его некому.
    """
    world = ctx.world
    scale = period / 10.0
    for trace in list(world.traces.values()):
        if trace.knowledge == cat.STUDIED or trace.state == cat.GONE:
            continue
        if trace.made is None or year - trace.made.year < 80:
            continue
        rng = ctx.rng("remains", "find", trace.id, year)
        near = _towns_near(world, trace.region_id)
        if trace.knowledge == cat.LOCAL:
            # Этим живут — значит, речь не о находке, а о том, что
            # кто-то доискался причины. Без книжников этого не бывает.
            if near < 2:
                continue
            if not rng.chance(EXPLAIN_CHANCE * near * scale):
                continue
            _explained(ctx, trace, rng, year)
            continue
        chance = min(FIND_MAX, FIND_BASE + FIND_PER_TOWN * near) * scale
        # Едва различимый след находят реже: искать в нём уже нечего.
        if trace.state == cat.FAINT:
            chance *= 0.45
        if not rng.chance(chance):
            continue
        _found(ctx, trace, rng, year)


def _explained(ctx, trace, rng, year: int) -> None:
    """Кто-то доискался, откуда пошёл обычай, и связал его с бедой."""
    world = ctx.world
    date = ctx.date_in(rng, year)
    trace.knowledge = cat.STUDIED
    trace.found = date
    trace.found_how = rng.choice(cat.FINDINGS)
    calamity = world.calamities.get(trace.calamity_id)
    gap = year - trace.made.year
    title, text = texts.origin_traced(rng, trace, calamity, gap, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="trace_traced",
        title=title, text=text, importance=3, subjects=[trace.id],
        region_id=trace.region_id, causes=_roots(world, calamity))


def _towns_near(world, region_id: str) -> int:
    """Сколько живых городов стоит в той же земле."""
    if not region_id:
        return 0
    count = 0
    for settlement_id in world.active_settlements:
        settlement = world.settlements.get(settlement_id)
        if settlement is not None and settlement.region_id == region_id:
            count += 1
    return count


def _found(ctx, trace, rng, year: int) -> None:
    """След нашли: кто, как — и что из него вычитали."""
    world = ctx.world
    date = ctx.date_in(rng, year)
    trace.found = date
    trace.found_how = rng.choice(cat.FIND_BY_GROUND
                                 if trace.kind == cat.GROUND
                                 else cat.FINDINGS)
    trace.knowledge = cat.LOCAL if rng.chance(0.75) else cat.STUDIED
    if trace.lost in (cat.LOST_UNKNOWN, cat.LOST_LEGEND, cat.LOST_SHUT):
        trace.lost = cat.LOST_FOUND
    if trace.knowledge == cat.STUDIED and rng.chance(READING_CHANCE):
        trace.reading = rng.choice(cat.READINGS)

    calamity = world.calamities.get(trace.calamity_id)
    gap = year - trace.made.year
    title, text = texts.trace_found(rng, trace, calamity, gap, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="trace_found",
        title=title, text=text,
        importance=3 if trace.knowledge == cat.STUDIED else 2,
        subjects=[trace.id], region_id=trace.region_id,
        causes=_roots(world, calamity))

    # Найденное иногда спорит с тем, что уже знали.
    if calamity is not None and rng.chance(QUARREL_CHANCE):
        others = [item for item in world.traces_of(calamity.id)
                  if item.id != trace.id and item.knowledge != cat.FORGOTTEN]
        if others:
            trace.quarrel = rng.choice(cat.QUARRELS)

    if trace.life >= 4 and year - trace.made.year >= ECHO_AFTER:
        _echo(ctx, trace, rng, year, date)


# ---------------------------------------------------------------------------
# Эхо: след просыпается
# ---------------------------------------------------------------------------

def _echo(ctx, trace, rng, year: int, date) -> None:
    """Живой след однажды отзывается — и беда прошлого начинает новую."""
    if not rng.chance(ECHO_CHANCE.get(trace.life, 0.05)):
        return
    world = ctx.world
    parent = world.calamities.get(trace.calamity_id)
    if parent is None:
        return
    from . import calamity as calamity_system

    fresh = calamity_system.start_named(
        ctx, year, parent.key, rng,
        severity=max(1, min(3, parent.severity - 1)),
        region_ids=[trace.region_id] if trace.region_id else None,
        note="разбужено следом по имени «%s»" % trace.name)
    if fresh is None:
        return
    fresh.parent_id = parent.id
    trace.life = 5
    trace.notes.append("%d: с него всё началось заново" % year)
    # Спящая реликвия той же беды считается разбуженной: угроза в мире
    # одна, и просыпается она один раз.
    relic = world.relics.get(trace.relic_id)
    if relic is not None and relic.status == "спит":
        relic.status = "пробуждён"
        relic.awakened = date
        if relic.id in world.sleeping_relics:
            world.sleeping_relics.remove(relic.id)

    title, text = texts.echo_woke(rng, trace, parent, fresh, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="trace_echo",
        title=title, text=text, importance=4,
        subjects=[trace.id, fresh.id], region_id=trace.region_id,
        causes=_roots(world, parent))


# ---------------------------------------------------------------------------
# Реконструкция: что потомки могут из этого восстановить
# ---------------------------------------------------------------------------

def reconstruct(world, calamity, year: int = 0) -> dict:
    """Что о беде можно узнать по её следам — по каждому вопросу отдельно.

    Считается не «узнали или нет», а восемь ответов врозь: когда —
    известно, размах — известен, кто пришёл — вероятно, отчего —
    неизвестно никогда. Считают только те следы, которые к этому году
    ещё есть и о которых знают: целая фреска в пещере, куда не заходили,
    не говорит никому ничего.
    """
    weights = {question: 0.0 for question in cat.QUESTIONS}

    # Живая память и свод, пока он читается: в первые века о беде знают
    # и без раскопок. Дальше остаётся только то, что несут следы.
    if year:
        since = year - (calamity.end.year if calamity.end
                        else calamity.start.year)
        memory = max(0.0, 1.0 - since / MEMORY_SPAN)
        if memory > 0.0:
            for question, value in MEMORY_WEIGHTS.items():
                weights[question] += value * memory

    for trace in world.traces_of(calamity.id):
        if trace.state == cat.GONE and "списан" not in " ".join(trace.notes):
            continue
        if trace.knowledge == cat.FORGOTTEN:
            continue
        value = trace.evidence * trace.truth
        if trace.state == cat.WORN:
            value *= 0.75
        elif trace.state == cat.FAINT:
            value *= 0.45
        if trace.knowledge == cat.STUDIED:
            value *= 1.35
        if trace.quarrel:
            value *= 0.7        # спорное свидетельство весит меньше
        for question in trace.answers:
            if question in weights:
                weights[question] += value

    answer = {}
    for question, value in weights.items():
        if value >= SURE_AT:
            answer[question] = cat.KNOWN_SURE
        elif value >= LIKELY_AT:
            answer[question] = cat.KNOWN_LIKELY
        elif value >= DISPUTED_AT:
            answer[question] = cat.KNOWN_DISPUTED
        else:
            answer[question] = cat.KNOWN_NONE
    return answer


def known_share(world, calamity, year: int = 0) -> float:
    """Какая доля вопросов о беде вообще имеет ответ."""
    answer = reconstruct(world, calamity, year)
    if not answer:
        return 0.0
    solid = sum(1 for value in answer.values()
                if value in (cat.KNOWN_SURE, cat.KNOWN_LIKELY))
    return solid / float(len(answer))


__all__ = ["imprint", "age", "find", "reconstruct", "known_share",
           "IMPRINT_FROM"]
