# -*- coding: utf-8 -*-
"""Жизненные пути: чего человек хотел, что делал и что вышло.

Движок до сих пор записывал за людьми только удавшееся: основал державу,
выиграл битву, составил свод. Человек от этого выходил послужным списком.
Здесь ведётся другое — разница между желанием, попытками и итогом.

Как это работает. Раз в десять лет у каждого ведомого человека может
случиться одно из немногого: он берётся за очередную подцель, с ним
происходит обычная житейская радость или неудача, ему выпадает случай не
в том месте, или его что-то ломает — и тогда он начинает хотеть другого.
Попытка сравнивается не с желанием, а с возможностями: умения, нрав
случая и то, что мешает. Поэтому способный человек проигрывает, а цель
чаще остаётся незавершённой, чем достигнутой.

Ведутся не все. Большинство живёт обычно и в истории не остаётся; путь
заводится тем, кто уже чем-то заметен, и разом их немного. Великими
становятся по ходу жизни, а не назначаются заранее: ступень известности
поднимается за удавшееся и опускается, когда о человеке забывают.

Смерть закрывает путь и сводит четыре правды: что он сделал, чем считал
это сам, что записала летопись и что поют через сто лет. Они редко
совпадают — в этом всё и дело.
"""

from __future__ import annotations

from .. import lifepaths as cat
from .. import narrative_life as texts
from .. import races as races_mod
from .. import recall
from .. import rulers as rulers_mod
from . import memory as memory_mod

MAX_ALIVE = 30             # столько жизней мир ведёт подробно разом
START_RATE = 0.85          # шанс за такт, что заведётся новый путь
ATTEMPT_RATE = 0.66        # шанс, что за десятилетие человек снова взялся
EVERYDAY_RATE = 0.55       # обычная жизнь между делом
CHANCE_RATE = 0.10         # не то место, не то время
WINDFALL_RATE = 0.07       # то, чего не собирался
TURN_RATE = 0.30           # перелом после тяжёлой памяти
MAX_TURNS = 3              # больше трёх раз жизнь не переламывается
TURN_GAP = 4               # и не чаще, чем раз в сорок лет
# Век у рас разный: человек живёт восемьдесят лет, а иной народ полторы
# тысячи. Если вести обоих раз в десять лет, у долгоживущего выйдет не
# биография, а летопись эпохи. Поэтому шаг жизни считается от её длины.
YEARS_PER_STEP = 75.0
GIVE_UP_AFTER = 5          # столько неудач подряд — и человек отступается
IRONY_RATE = 0.14          # ирония судьбы должна быть редкой
UNSUNG_RATE = 0.12
FALSE_FAME_RATE = 0.07

# Кому биографии не пишут: вождь вторжения — не человек со своей целью,
# а само бедствие, и жизненный путь у него не складывается.
SKIP_ROLES = ("бедствие мира", "вождь вторжения")
# И слишком долгий век в биографию не уместить: у тысячелетнего вождя
# между двумя строками проходит по четыре века.
MAX_TRACKED_SPAN = 1300

# Роли, за которые мир вообще начинает следить за человеком.
WATCHED = (
    "правитель", "основатель страны", "основатель поселения", "полководец",
    "чародей", "жрец", "учёный", "летописец", "звездочёт", "лекарь",
    "зодчий", "законник", "рудознатец", "сказитель", "картограф",
    "охотник на чудовищ", "мореход", "путешественник", "вождь",
    "герой сказания", "вождь похода", "знать",
)


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    rng = ctx.rng("lifepath", year)
    _close_departed(ctx, rng, year)
    _advance(ctx, rng, year, period)
    _open_new(ctx, rng, year)


# ---------------------------------------------------------------------------
# Кому мир начинает вести путь
# ---------------------------------------------------------------------------

def _living(world, year: int) -> list:
    out = []
    for path in world.lifepaths.values():
        if path.ended_year:
            continue
        figure = world.figures.get(path.figure_id)
        if figure is not None and figure.alive_at(year):
            out.append((path, figure))
    return out


def _open_new(ctx, rng, year: int) -> None:
    world = ctx.world
    alive = len(_living(world, year))
    if alive >= MAX_ALIVE:
        return
    # Пока места свободны, мир берёт под присмотр нескольких разом:
    # иначе за век заводится один путь и половина слотов пустует.
    room = min(3, MAX_ALIVE - alive)
    for _ in range(room):
        if not rng.chance(START_RATE * ctx.density()):
            return
        _open_one(ctx, rng, year)


def _open_one(ctx, rng, year: int) -> None:
    world = ctx.world

    # Кандидаты: живые, взрослые, чем-то уже заметные и ещё не ведомые.
    pool = []
    for figure in world.figures.values():
        if not figure.alive_at(year) or world.path_of(figure.id) is not None:
            continue
        age = figure.age_at(year)
        if age < 16:
            continue
        if any(role in SKIP_ROLES for role in figure.roles):
            continue          # у пришедшей из-за края беды биографии нет
        watched = [role for role in figure.roles if role in WATCHED]
        if not watched and not figure.deeds:
            continue
        if _own_span(figure) > MAX_TRACKED_SPAN:
            continue          # тысячелетнюю жизнь не уместить в биографию
        # Путь заводят смолоду: у прожитой жизни начинать его поздно.
        span = _own_span(figure)
        part = min(1.0, age / float(max(1, span)))
        if part > 0.5:
            continue
        weight = (1.0 + len(watched)) * max(0.15, 1.4 - part * 1.6)
        pool.append((figure, weight))
    if not pool:
        return
    pool.sort(key=lambda pair: pair[0].id)
    figure = rng.weighted(pool)
    _begin(ctx, rng, figure, year)


def _begin(ctx, rng, figure, year: int):
    """Заводит человеку жизненную цель и всё, что вокруг неё."""
    world = ctx.world
    race = races_mod.RACES_BY_ID.get(figure.race_id)
    if race is None:
        return None
    # Умения нужны, чтобы цель сравнивалась с возможностями, а не с
    # желанием. У тех, кто не сидел на престоле, их могло не быть.
    rulers_mod.endow(rng, figure, race)

    goal = _pick_goal(rng, figure)
    about = _bind_goal(ctx, rng, goal, figure)
    limits = _pick_limits(rng, figure)
    luck_name, luck_shift, luck_note = rng.choice(cat.LUCK)

    path = world.add_lifepath(
        figure_id=figure.id, goal_key=goal.key, wish=goal.wish, about=about,
        hidden=texts.pick(rng.choice(cat.HIDDEN), figure.sex),
        state=cat.STARTED,
        subgoals=[{"что": step, "состояние": cat.NOT_STARTED, "год": 0}
                  for step in goal.steps],
        limits=[name for name, _weight in limits],
        luck=luck_name, luck_note=luck_note,
        signature=rng.choice(cat.SIGNATURES),
        habits=[rng.choice(cat.HABITS),
                "боится %s" % rng.choice(cat.FEARS),
                rng.choice(cat.SUPERSTITIONS)],
        fear=rng.choice(cat.FEARS),
        secret=rng.choice(cat.SECRETS) if rng.chance(0.42) else "",
        contradiction=rng.choice(cat.CONTRADICTIONS)
        if rng.chance(0.55) else "",
        born_year=figure.birth.year if figure.birth else year,
        fame=cat.UNKNOWN)
    if path.secret:
        path.secret_fate = rng.choice(cat.SECRET_FATES)
    path.notes.append("удача: %s" % luck_note)
    _step(path, year, "желание", texts.wish(rng, goal.wish, figure.sex))
    if about:
        _step(path, year, "желание",
              rng.choice(texts.ABOUT_FRAMES) % about)
    _step(path, year, "желание", texts.hidden(rng, path.hidden, figure.sex))
    if path.limits:
        _step(path, year, "помеха",
              texts.limits(rng, path.limits, figure.sex))
    _maybe_rival(ctx, rng, path, figure, year)
    return path


def _maybe_rival(ctx, rng, path, figure, year: int) -> None:
    """Двое хотят одного и того же — и это их сталкивает.

    Цель одного меняет вероятность цели другого: там, где двое идут к
    одному престолу или за одним чудовищем, дорога у каждого становится
    труднее, а вражда у неё появляется история.
    """
    world = ctx.world
    for other_path in world.lifepaths.values():
        if other_path.id == path.id or other_path.ended_year:
            continue
        if other_path.goal_key != path.goal_key:
            continue
        rival = world.figures.get(other_path.figure_id)
        if rival is None or not rival.alive_at(year):
            continue
        if rival.origin_region != figure.origin_region:
            continue
        if not rng.chance(0.6):
            continue
        memory_mod.bind(ctx, figure, rival, recall.B_RIVALRY, year,
                        value=-0.4, note="оба хотят одного и того же")
        line = "Того же хотел и %s." % rival.plain_name
        _step(path, year, "соперник", line, why=other_path.id)
        _step(other_path, year, "соперник",
              "Того же захотел и %s." % figure.plain_name, why=path.id)
        path.notes.append("соперник по цели: %s" % rival.plain_name)
        other_path.notes.append("соперник по цели: %s" % figure.plain_name)
        # Соперничество мешает обоим: место наверху одно.
        for item in (path, other_path):
            if "соперник у цели" not in item.limits:
                item.limits.append("соперник у цели")
        return


def _pick_goal(rng, figure):
    """Цель по тому, кто этот человек. Одна категория — разные цели.

    Если отец умер, не доделав своего, и сын взялся за то же, цель
    достаётся ему готовой: так она переживает человека.
    """
    for note in figure.notes:
        if note.startswith("наследует цель: "):
            goal = cat.GOALS_BY_KEY.get(note.split(": ", 1)[1])
            if goal is not None:
                return goal
    pairs = []
    for goal in cat.GOALS:
        weight = goal.weight
        if goal.roles:
            if any(role in figure.roles for role in goal.roles):
                weight *= 3.2
            else:
                weight *= 0.35      # взяться можно и не за своё
        if goal.skill and figure.skills:
            # К чему человек способен, к тому его и тянет — но не всегда.
            weight *= 0.6 + 0.12 * int(figure.skills.get(goal.skill, 5))
        if figure.alignment <= -2 and goal.key in ("saint", "protect",
                                                   "free_folk"):
            weight *= 0.25
        if figure.alignment >= 2 and goal.key in ("throne", "rich"):
            weight *= 0.6
        pairs.append((goal, max(0.02, weight)))
    return rng.weighted(pairs)


def _bind_goal(ctx, rng, goal, figure) -> str:
    """Цель не вообще, а ради чего-то в этом мире.

    Два охотника на чудовищ — это две разные жизни, если один идёт за
    драконом по имени такой-то, а другой за тем, кто взял его брата.
    """
    world = ctx.world
    region = world.regions.get(figure.origin_region)
    if goal.key in ("monster_slayer",):
        alive = [world.monsters[mid] for mid in world.living_monsters]
        if alive:
            beast = rng.choice(sorted(alive, key=lambda m: m.id))
            return "%s по имени %s" % (beast.word.lower(), beast.name)
        return "тот, кого ещё никто не видел"
    if goal.key in ("relic",):
        lost = [item for item in world.artifacts.values()
                if item.where in ("потерян", "в логове", "в кургане")]
        if lost:
            thing = rng.choice(sorted(lost, key=lambda a: a.id))
            return "вещь по имени %s" % thing.name
        return "вещь, о которой помнит только род"
    if goal.key in ("lost_city", "new_land", "prove"):
        unknown = [item for item in world.regions.values()
                   if not item.known and not item.drowned]
        if unknown:
            land = rng.choice(sorted(unknown, key=lambda r: r.id))
            return "земля по имени %s" % land.name
        return "место, которого нет на картах"
    if goal.key in ("avenge", "forgiven", "love"):
        return "человек, которого он называет про себя" \
            if figure.sex == "m" else "человек, которого она называет про себя"
    if goal.key in ("house_honour",):
        house = world.houses.get(figure.house_id)
        return "род по имени %s" % house.name if house else "свой род"
    if goal.key in ("throne", "free_folk", "unite"):
        polity = None
        for polity_id in world.active_polities:
            item = world.polities[polity_id]
            seat = world.settlements.get(item.capital_id)
            if seat is not None and seat.region_id == figure.origin_region:
                polity = item
                break
        return "держава по имени %s" % polity.name if polity else "своя земля"
    if region is not None:
        return "земля по имени %s" % region.name
    return ""


def _pick_limits(rng, figure) -> list:
    """Что мешает. Без этого цель сравнивалась бы только с желанием."""
    count = rng.weighted(((1, 3.0), (2, 2.2), (3, 0.8), (0, 0.6)))
    out, used = [], set()
    for _ in range(count):
        name, weight = rng.choice(cat.LIMITS)
        if name in used:
            continue
        used.add(name)
        out.append((name, weight))
    return out


# ---------------------------------------------------------------------------
# Ход жизни
# ---------------------------------------------------------------------------

def _own_span(figure) -> int:
    """Сколько лет отпущено именно этому человеку, а не его расе вообще."""
    if figure.birth is None or figure.death is None:
        return 80
    return max(1, figure.death.year - figure.birth.year)


def _stride(figure, period: int) -> int:
    """Через сколько тактов у этого человека случается следующий шаг.

    Человек живёт восемьдесят лет, иной народ — полторы тысячи. Если
    вести обоих раз в десять лет, у долгоживущего выйдет не биография, а
    летопись эпохи, а у человека — три строки.
    """
    return max(1, int(round(_own_span(figure) / YEARS_PER_STEP)))


def _turn_of(path) -> int:
    """Свой сдвиг у каждого пути: иначе все долгожители ходят в ногу."""
    value = 0
    for char in path.id:
        value = (value * 31 + ord(char)) & 0xFFFF
    return value


def _advance(ctx, rng, year: int, period: int) -> None:
    world = ctx.world
    beat = year // max(1, period)
    for path, figure in _living(world, year):
        span = _own_span(figure)
        stride = _stride(figure, period)
        if stride > 1 and (beat + _turn_of(path)) % stride:
            continue
        age = figure.age_at(year)
        stage, _note = cat.stage_of(age, span)

        if stage == "старость":
            # В старости человек уже не берётся за новое: он или доживает,
            # или доделывает начатое. Новых целей здесь не бывает.
            _late_life(ctx, rng, path, figure, year)
            continue

        if _maybe_turn(ctx, rng, path, figure, year):
            continue          # перелом занимает этот десяток целиком

        if stage in ("поздние годы",):
            # Последние годы у человека свои: ученик, записки, примирение
            # или просто тишина. Смерть не обязана быть вершиной жизни.
            if _late_life(ctx, rng, path, figure, year):
                continue
        elif path.state not in (cat.STARTED, cat.GOING, cat.PAUSED) \
                and rng.chance(0.5):
            # Цель кончилась, а жизнь нет: человек хочет уже другого.
            if _new_wish(ctx, rng, path, figure, year):
                continue

        # Жизнь идёт не по одному делу за раз: между двумя приходами к
        # человеку проходят годы, и за них с ним случается несколько
        # вещей. Иначе цель из семи подцелей не взять никому.
        deeds = rng.weighted(((2, 2.0), (3, 3.0), (4, 1.6)))
        acted = False
        for _ in range(deeds):
            if path.state not in (cat.STARTED, cat.GOING, cat.PAUSED):
                break
            if not rng.chance(ATTEMPT_RATE):
                continue
            _try_step(ctx, rng, path, figure, year, stage)
            acted = True
        # Обычная жизнь идёт не вместо дела, а рядом с ним: человек
        # женится и теряет скопленное в те же годы, когда добивается
        # своего. Иначе биография выходит сплошным послужным списком.
        if not acted and rng.chance(EVERYDAY_RATE):
            _ordinary(rng, path, figure, year)
        elif acted and rng.chance(0.34):
            _ordinary(rng, path, figure, year)
        if rng.chance(CHANCE_RATE):
            _chance(rng, path, figure, year)
        if rng.chance(WINDFALL_RATE):
            _windfall(ctx, rng, path, figure, year)
        _refresh_fame(world, path, figure, year)


def _try_step(ctx, rng, path, figure, year: int, stage: str) -> None:
    """Очередная попытка. Способный человек тоже проигрывает."""
    goal = cat.GOALS_BY_KEY.get(path.goal_key)
    if goal is None:
        return
    todo = None
    for item in path.subgoals:
        if item["состояние"] == cat.NOT_STARTED:
            todo = item
            break
    if todo is None:
        _reach(ctx, rng, path, figure, year)
        return
    # В одну и ту же стену бьются трижды, не больше: на четвёртый раз
    # человек либо обходит её, либо признаёт, что дальше ему не пройти.
    if todo.get("попыток", 0) >= 3:
        if rng.chance(0.7):
            todo["состояние"] = cat.PART_DONE
            path.steps_done += 1
            _step(path, year, "обход",
                  "Обошёл это стороной и пошёл дальше." if figure.sex == "m"
                  else "Обошла это стороной и пошла дальше.")
        else:
            todo["состояние"] = cat.IMPOSSIBLE
            _step(path, year, "стена",
                  "Понял, что через это ему не перейти." if figure.sex == "m"
                  else "Поняла, что через это ей не перейти.")
            path.state = cat.PAUSED
        return

    if path.tries and rng.chance(0.4):
        _step(path, year, "снова", texts.again(rng, figure.sex))
    path.tries += 1
    todo["попыток"] = todo.get("попыток", 0) + 1
    result = _roll(ctx, rng, path, figure, goal, stage)
    todo["год"] = year
    if result in (cat.TRY_WON, cat.TRY_COST):
        todo["состояние"] = cat.DONE
        path.steps_done += 1
        path.wins += 1
        path.losses = 0
        if result == cat.TRY_COST:
            path.notes.append("за «%s» заплатил дорого" % todo["что"])
    elif result == cat.TRY_HALF:
        todo["состояние"] = cat.PART_DONE
        path.wins += 1
        path.losses = 0
    else:
        todo["состояние"] = cat.NOT_STARTED
        path.losses += 1
    path.state = cat.GOING
    _step(path, year, "попытка",
          texts.attempt(rng, todo["что"], result, figure.sex))
    if result in (cat.TRY_WON, cat.TRY_COST):
        _maybe_master(ctx, rng, path, figure, todo["что"], year)

    if result == cat.TRY_NEAR:
        path.notes.append("был в шаге от «%s»" % todo["что"])
    if path.losses >= GIVE_UP_AFTER:
        _stop(ctx, rng, path, figure, year)
        return
    # Дорога кончилась, когда не осталось ненач��тых подцелей. Раньше
    # здесь стояло «все пройдены», и одна обойдённая стороной подцель
    # навсегда лишала человека возможности добиться своего.
    if not any(item["состояние"] == cat.NOT_STARTED
               for item in path.subgoals):
        _reach(ctx, rng, path, figure, year)


# По каким подцелям у человека и правда появляется наставник.
LEARNING = ("наставник", "учител", "выучиться", "научит", "учителя",
            "мастера в учителя", "морскому делу", "лекарскому делу")


def _maybe_master(ctx, rng, path, figure, subgoal: str, year: int) -> None:
    """Нашёл наставника — значит, наставник должен быть настоящим.

    Иначе «найти наставника» остаётся строкой, а цепочка «учитель —
    ученик — ученики ученика» не заводится никогда.
    """
    if not any(word in subgoal for word in LEARNING):
        return
    world = ctx.world
    best = None
    for other in world.figures.values():
        if other.id == figure.id or not other.alive_at(year):
            continue
        if other.origin_region != figure.origin_region:
            continue
        if other.age_at(year) <= figure.age_at(year) + 15:
            continue          # наставник должен быть старше
        if not other.roles:
            continue
        if best is None or other.id < best.id:
            best = other
    if best is None:
        return
    memory_mod.taught(ctx, figure, best, year, note=subgoal)
    _step(path, year, "наставник",
          "Учил его %s." % best.plain_name if figure.sex == "m"
          else "Учил её %s." % best.plain_name)
    path.notes.append("наставник: %s" % best.plain_name)


def _maybe_pupil(ctx, rng, path, figure, year: int) -> None:
    """Под конец человек берёт ученика — и ученик тоже настоящий."""
    world = ctx.world
    best = None
    for other in world.figures.values():
        if other.id == figure.id or not other.alive_at(year):
            continue
        if other.origin_region != figure.origin_region:
            continue
        age = other.age_at(year)
        if age < 14 or age > figure.age_at(year) - 20:
            continue
        if best is None or other.id < best.id:
            best = other
    if best is None:
        return
    memory_mod.taught(ctx, best, figure, year, note="ученичество")
    _step(path, year, "ученик", "Учеником его стал %s." % best.plain_name
          if figure.sex == "m"
          else "Учеником её стал %s." % best.plain_name)
    path.notes.append("ученик: %s" % best.plain_name)


def _roll(ctx, rng, path, figure, goal, stage: str) -> str:
    """Чем кончилась попытка.

    Умение — не всё. Считаются ещё: что мешает, нрав случая, возраст,
    сколько раз уже брался и насколько цель вообще достижима.
    """
    skill = rulers_mod.skill_of(figure, goal.skill) if goal.skill else 5
    edge = 0.32 + skill * 0.045
    for name in path.limits:
        for limit, weight in cat.LIMITS:
            if limit == name:
                edge -= weight * 0.5
                break
    for luck, shift, _note in cat.LUCK:
        if luck == path.luck:
            edge += shift
            break
    if path.luck == "поздний":
        # У этого всё выходит под конец: в молодости не выходит ничего.
        edge += -0.12 if stage in ("юность", "молодость") else 0.14
    if stage in ("поздние годы", "старость"):
        edge -= 0.08
    edge += 0.05 * min(4, path.wins)      # опыт что-нибудь да значит
    edge /= max(0.6, goal.hard)
    edge = max(0.05, min(0.86, edge))

    if not rng.chance(edge):
        # Не вышло — но иногда не хватает одного шага, и это помнят
        # дольше, чем чистый проигрыш.
        return cat.TRY_NEAR if rng.chance(0.24) else cat.TRY_LOST
    if path.luck == "дорогая удача" and rng.chance(0.55):
        return cat.TRY_COST
    if rng.chance(0.24):
        return cat.TRY_HALF
    return cat.TRY_WON


def _reach(ctx, rng, path, figure, year: int) -> None:
    """Дорога пройдена — но «добился» бывает разным.

    Если половину подцелей человек обошёл стороной или уткнулся в них
    лбом, это не «добился», а «сделал, что смог».
    """
    share = _share(path)
    costly = any("заплатил дорого" in note for note in path.notes)
    if share >= 0.72:
        path.state = cat.DEAR if costly else cat.DONE
    elif share >= 0.45:
        path.state = cat.PART_DONE
    else:
        path.state = cat.ALMOST if share >= 0.28 else cat.FAILED
    _step(path, year, "итог", texts.ending(rng, path.state, figure.sex))
    if path.state in (cat.DONE, cat.DEAR) \
            and "добился своего" not in figure.roles:
        figure.roles.append("добился своего")


def _share(path) -> float:
    """Насколько дорога пройдена. Обойдённое стороной — это половина."""
    live = [item for item in path.subgoals
            if item["состояние"] != cat.REPLACED]
    if not live:
        return 0.0
    score = 0.0
    for item in live:
        if item["состояние"] == cat.DONE:
            score += 1.0
        elif item["состояние"] == cat.PART_DONE:
            score += 0.5
    return score / float(len(live))


def _stop(ctx, rng, path, figure, year: int) -> None:
    """Человек отступается. Это такой же итог жизни, как успех."""
    # Отступаются реже, чем откладывают: большинство возвращается к
    # своему через годы, и только часть говорит себе «больше не хочу».
    if rng.chance(0.34):
        path.state = cat.GIVEN_UP
        _step(path, year, "отказ", texts.give_up(rng, figure.sex))
    else:
        path.state = cat.PAUSED
        path.losses = 0
        _step(path, year, "передышка",
              "Отложил это на потом." if figure.sex == "m"
              else "Отложила это на потом.")


def _maybe_turn(ctx, rng, path, figure, year: int) -> bool:
    """Перелом: значимое событие — новое понимание — новая цель.

    Поводом служит не бросок костей, а то, что человек и правда пережил:
    предательство, гибель родича, плен, поражение, обойдённый престол.
    """
    if path.state not in (cat.STARTED, cat.GOING, cat.PAUSED):
        return False
    turns = [item for item in path.steps if item["вид"] == "перелом"]
    if len(turns) >= MAX_TURNS:
        return False
    if turns and year - turns[-1]["год"] < TURN_GAP * 10:
        return False          # жизнь не ломается каждое десятилетие
    world = ctx.world
    heavy = None
    for memory in world.memories_of(figure.id):
        if memory.kind not in (recall.BETRAYAL, recall.KIN_DEATH,
                               recall.DEFEAT, recall.CAPTIVITY,
                               recall.PASSED_OVER, recall.HOME_LOST,
                               recall.REVELATION):
            continue
        if year - memory.year > 12 or memory.year < path.born_year:
            continue
        heavy = memory
        break
    # Цель меняют не только чужие удары. Её меняют возраст, длинная
    # полоса неудач и нежданно свалившееся: «я хотел не этого».
    own = ""
    if heavy is None:
        if path.losses >= 3 and rng.chance(0.22):
            own = "долгая полоса неудач"
        elif any("получил не то, чего добивался" in note
                 for note in path.notes[-2:]) and rng.chance(0.3):
            own = "нежданное, которое оказалось важнее"
        elif rng.chance(0.015):
            own = "возраст"
        if not own:
            return False
    elif not rng.chance(TURN_RATE):
        return False
    why = heavy.kind if heavy is not None else own
    when = heavy.year if heavy is not None else year

    old = cat.GOALS_BY_KEY.get(path.goal_key)
    fresh = _pick_goal(rng, figure)
    if old is not None and fresh.key == old.key:
        return False
    path.notes.append("перелом в %d году: %s" % (when, why))
    _step(path, year, "перелом", texts.turn(rng, figure.sex), why=why)
    # Всё недоделанное по прежней цели закрывается, иначе человек будет
    # годами добивать подцели того, чего уже не хочет.
    for item in path.subgoals:
        if item["состояние"] in (cat.NOT_STARTED, cat.PART_DONE):
            item["состояние"] = cat.REPLACED
            item["год"] = year
    path.subgoals.append({"что": "прежнее: %s" % path.wish,
                          "состояние": cat.REPLACED, "год": year})
    path.goal_key = fresh.key
    path.wish = fresh.wish
    path.about = _bind_goal(ctx, rng, fresh, figure)
    path.subgoals.extend({"что": step, "состояние": cat.NOT_STARTED,
                          "год": 0} for step in fresh.steps)
    path.steps_done = 0
    path.losses = 0
    path.state = cat.STARTED
    _step(path, year, "желание", texts.turn_to(rng, fresh.wish, figure.sex))
    return True


def _late_life(ctx, rng, path, figure, year: int) -> bool:
    """Чем человек занят в последние годы."""
    said = [item["год"] for item in path.steps if item["вид"] == "поздние годы"]
    if said and year - said[-1] < 60:
        return False
    if len(said) >= 3 or not rng.chance(0.45):
        return False
    what = texts.pick(rng.choice(cat.LATE_LIFE), figure.sex)
    _step(path, year, "поздние годы", texts.late_life(rng, what))
    if "растил" in what or "растила" in what or "учил" in what \
            or "учила" in what:
        _maybe_pupil(ctx, rng, path, figure, year)
    return True


def _new_wish(ctx, rng, path, figure, year: int) -> bool:
    """Цель кончилась — человек хочет уже другого.

    Добился он или не добился, жизнь после этого продолжается, и
    записывать её одними случайностями нечестно.
    """
    fresh = _pick_goal(rng, figure)
    if fresh.key == path.goal_key:
        return False
    # Чем кончилось прежнее — запоминаем до того, как перепишем цель:
    # «добившись своего» и «не вышло» звучат по-разному.
    was_good = path.state in cat.GOOD_ENDS
    for item in path.subgoals:
        if item["состояние"] in (cat.NOT_STARTED, cat.PART_DONE):
            item["состояние"] = cat.REPLACED
            item["год"] = year
    path.subgoals.append({"что": "прежнее: %s" % path.wish,
                          "состояние": path.state, "год": year})
    path.goal_key = fresh.key
    path.wish = fresh.wish
    path.about = _bind_goal(ctx, rng, fresh, figure)
    path.subgoals.extend({"что": step, "состояние": cat.NOT_STARTED,
                          "год": 0} for step in fresh.steps)
    path.steps_done = 0
    path.losses = 0
    path.state = cat.STARTED
    _step(path, year, "желание",
          texts.again_wish(rng, figure.sex, won=was_good))
    _step(path, year, "желание", texts.turn_to(rng, fresh.wish, figure.sex))
    return True


def _ordinary(rng, path, figure, year: int) -> None:
    """Обычная жизнь между делом: она и делает человека человеком."""
    roll = rng.weighted((("радость", 1.0), ("неудача", 1.0), ("быт", 1.3)))
    if roll == "радость":
        line = texts.pick(rng.choice(cat.SMALL_JOYS), figure.sex)
        _step(path, year, "малое", line)
    elif roll == "неудача":
        line = texts.pick(rng.choice(cat.SMALL_WOES), figure.sex)
        _step(path, year, "малое", line)
    else:
        line = texts.pick(rng.choice(cat.EVERYDAY), figure.sex)
        _step(path, year, "быт", line)


def _said(path, line: str) -> bool:
    """Было ли уже сказано ровно это. Дважды одно и то же — опечатка."""
    return any(item["строка"] == line for item in path.steps)


def _chance(rng, path, figure, year: int) -> None:
    """Не то место, не то время. Замыслом это не объясняется."""
    for _ in range(4):
        line = texts.pick(rng.choice(cat.CHANCES), figure.sex)
        if not _said(path, line):
            _step(path, year, "случай", line)
            return


def _windfall(ctx, rng, path, figure, year: int) -> None:
    """То, чего человек не собирался, а вышло — и цели могут смениться."""
    for _ in range(4):
        line = texts.pick(rng.choice(cat.WINDFALLS), figure.sex)
        if not _said(path, line):
            _step(path, year, "нежданное", line)
            path.notes.append(
                "получил не то, чего добивался, в %d году" % year)
            return


# ---------------------------------------------------------------------------
# Известность
# ---------------------------------------------------------------------------

def _refresh_fame(world, path, figure, year: int) -> None:
    """Ступень известности. Великими становятся, а не назначаются."""
    score = min(8, len(figure.deeds)) * 1.0 + len(figure.roles) * 0.4
    # Долгая жизнь сама по себе не заслуга: эльф, который брался за своё
    # триста раз, не поэтому великий.
    score += min(6, path.wins) * 0.5
    score += 2.0 if path.state in cat.GOOD_ENDS else 0.0
    if "правитель" in figure.roles:
        score += 2.0
    if path.state in (cat.FAILED, cat.GIVEN_UP):
        score -= 0.5
    if score >= 9.0:
        level = cat.GREAT
    elif score >= 5.5:
        level = cat.HISTORIC
    elif score >= 3.0:
        level = cat.REGION
    elif score >= 1.2:
        level = cat.LOCAL
    else:
        level = cat.UNKNOWN
    if level != path.fame:
        path.fame = level
        path.fame_trail.append({"год": year, "ступень": level})


# ---------------------------------------------------------------------------
# Цель как источник сюжета
# ---------------------------------------------------------------------------

def seekers(world, kind: str, region_id: str = "", year: int = 0) -> list:
    """Кто прямо сейчас ищет именно такой беды.

    Человек, который всю жизнь хочет убить чудовище, и должен оказаться в
    той дружине, которая за чудовищем идёт. Без этого цели людей и
    местные истории остались бы двумя разными генераторами.
    """
    out = []
    for path in world.lifepaths.values():
        if path.ended_year or path.state not in (cat.STARTED, cat.GOING,
                                                 cat.PAUSED):
            continue
        goal = cat.GOALS_BY_KEY.get(path.goal_key)
        if goal is None or not goal.threat or goal.threat != kind:
            continue
        figure = world.figures.get(path.figure_id)
        if figure is None or (year and not figure.alive_at(year)):
            continue
        if region_id and figure.origin_region and \
                figure.origin_region != region_id:
            out.append(figure)          # придёт и издалека, но позже
            continue
        out.insert(0, figure)           # свой — первым
    return out


def after_tale(ctx, tale, figure, outcome: str, year: int) -> None:
    """Сказание кончилось — и оно записывается в жизнь того, кто ходил.

    Для одного это шаг к своей цели, для другого — та самая попытка, на
    которой всё и кончилось.
    """
    world = ctx.world
    path = world.path_of(figure.id)
    if path is None or path.ended_year:
        return
    # Дорога сказания отсчитывается назад от нынешнего года, и павший в
    # пути умер раньше, чем дружина вернулась. Записывать ему возвращение
    # нельзя: в летописи он уже мёртв.
    if figure.death is not None:
        if figure.death.year < year:
            year = figure.death.year
        if path.steps and year < path.steps[-1]["год"]:
            return
    goal = cat.GOALS_BY_KEY.get(path.goal_key)
    won = outcome in ("победа", "дорогая победа")
    line = "%s — %s" % (tale.name, outcome)
    _step(path, year, "сказание", line, why=tale.id)
    path.tries += 1
    if won:
        path.wins += 1
        path.losses = 0
    else:
        path.losses += 1
    # Если сказание было ровно про то, ради чего человек жил, оно
    # закрывает подцель: за этим он и шёл.
    if goal is not None and goal.threat and goal.threat == tale.kind:
        for item in path.subgoals:
            if item["состояние"] == cat.NOT_STARTED:
                item["состояние"] = cat.DONE if won else cat.NOT_STARTED
                item["год"] = year
                if won:
                    path.steps_done += 1
                break
        path.notes.append("сказание по имени %s легло в его цель"
                          % tale.name)


# ---------------------------------------------------------------------------
# Итог жизни
# ---------------------------------------------------------------------------

def _close_departed(ctx, rng, year: int) -> None:
    """Сводит путь тех, кто умер с прошлого такта."""
    world = ctx.world
    for path in list(world.lifepaths.values()):
        if path.ended_year:
            continue
        figure = world.figures.get(path.figure_id)
        if figure is None:
            path.ended_year = year
            continue
        if figure.alive_at(year):
            continue
        _close(ctx, rng, path, figure)


def _close(ctx, rng, path, figure) -> None:
    """Смерть закрывает путь и сводит четыре правды об одном человеке."""
    died = figure.death.year if figure.death else path.born_year
    path.ended_year = died

    _settle_goal(rng, path, figure, died)
    _death_note(rng, path, figure, died)
    _four_truths(ctx, rng, path, figure, died)
    _irony(rng, path, figure, died)
    _secret_out(rng, path, figure, died)
    _afterwards(ctx, rng, path, figure, died)

    # В общую летопись идут только те, кого она и правда запомнила.
    if path.fame in (cat.HISTORIC, cat.GREAT):
        _write_down(ctx, path, figure, died)


def _settle_goal(rng, path, figure, year: int) -> None:
    """Чем кончилось то, ради чего человек жил.

    Незавершённых должно быть заметно больше завершённых: так и в жизни.
    """
    if path.state in (cat.DONE, cat.DEAR, cat.GIVEN_UP):
        if not any(item["вид"] == "итог" for item in path.steps):
            _step(path, year, "итог",
                  texts.ending(rng, path.state, figure.sex))
        return

    part = _share(path)
    near = any("был в шаге" in note for note in path.notes)

    if part >= 0.72 and rng.chance(0.55):
        # Дошёл почти до конца и умер на дороге — это не провал.
        path.state = cat.DEAR if rng.chance(0.3) else cat.PART_DONE
    elif near and rng.chance(0.6):
        path.state = cat.ALMOST
        path.notes.append(texts.pick(rng.choice(cat.ALMOSTS), figure.sex))
    elif part >= 0.6:
        path.state = cat.ALMOST if rng.chance(0.45) else cat.PART_DONE
    elif part >= 0.3:
        path.state = cat.PART_DONE if rng.chance(0.4) else cat.FAILED
    elif path.state == cat.PAUSED and rng.chance(0.5):
        path.state = cat.FORGOTTEN
    elif rng.chance(0.18):
        path.state = cat.MOOT
        _step(path, year, "итог", texts.moot(rng, figure.sex))
    elif rng.chance(0.12):
        path.state = cat.IMPOSSIBLE
    else:
        path.state = cat.FAILED
    if path.state != cat.MOOT:
        _step(path, year, "итог",
              texts.ending(rng, path.state, figure.sex))


def _death_note(rng, path, figure, year: int) -> None:
    """Отчего умер. Смерть не обязана быть под стать жизни.

    Если человека убили на войне или казнили, причина уже записана — её
    и берём. Своей выдумкой её подменять нельзя.
    """
    if figure.death_cause:
        path.death_note = figure.death_cause
    else:
        path.death_note = rng.weighted(cat.DEATHS)
    _step(path, year, "смерть", texts.death(rng, path.death_note, figure.sex))


def _four_truths(ctx, rng, path, figure, year: int) -> None:
    """Что сделал, чем считал сам, что записали и что поют.

    Это и есть главное: человек — не то, что о нём сказано, и не то, чего
    он хотел, а разница между тем и другим.
    """
    done = [item["что"] for item in path.subgoals
            if item["состояние"] == cat.DONE]
    if path.state in cat.GOOD_ENDS:
        path.did = ("сделал то, ради чего жил: %s" % path.wish
                    if figure.sex == "m"
                    else "сделала то, ради чего жила: %s" % path.wish)
    elif len(done) > 1:
        path.did = "из задуманного вышло немногое: %s" % ", ".join(done[-2:])
    elif done:
        path.did = "из задуманного вышло одно: %s" % done[0]
    else:
        path.did = ("того, ради чего жил, не сделал" if figure.sex == "m"
                    else "того, ради чего жила, не сделала")

    path.thought = texts.self_view(rng, figure.sex)

    written = rng.choice(texts.WRITTEN_SHORT)
    if path.fame == cat.UNKNOWN and rng.chance(UNSUNG_RATE * 3):
        path.written = texts.unsung(rng, figure.sex)
    else:
        path.written = texts.written_view(rng, written, figure.sex)
    if rng.chance(FALSE_FAME_RATE):
        path.written = texts.false_fame(rng, figure.sex)
        path.notes.append("в летописи за ним записано чужое")

    # Поют не то и не всегда: у безвестных песни нет вовсе.
    if path.fame in (cat.REGION, cat.HISTORIC, cat.GREAT)             and rng.chance(0.72):
        path.sung = texts.sung_view(rng, rng.choice(texts.SUNG_SHORT))


def _irony(rng, path, figure, year: int) -> None:
    """Ирония судьбы — редкое пересечение нрава, обстоятельств и случая."""
    if not rng.chance(IRONY_RATE):
        return
    fitting = [line for key, line in cat.IRONIES
               if not key or key == path.goal_key]
    if not fitting:
        return
    path.irony = rng.choice(fitting)
    _step(path, year, "ирония", "%s." % path.irony[:1].upper() + path.irony[1:])


def _secret_out(rng, path, figure, year: int) -> None:
    if not path.secret:
        return
    if path.secret_fate == "раскрылся после смерти":
        path.legacy.append({"год": year + rng.randint(1, 40),
                            "что": "открылось то, что он скрывал: %s"
                            % path.secret if figure.sex == "m"
                            else "открылось то, что она скрывала: %s"
                            % path.secret})


def _afterwards(ctx, rng, path, figure, year: int) -> None:
    """Что было после. Потомки распоряжаются наследием как хотят."""
    world = ctx.world
    for _ in range(rng.weighted(((0, 1.2), (1, 2.0), (2, 1.0)))):
        line = rng.weighted(cat.AFTERMATH)
        when = year + rng.randint(2, 120)
        path.legacy.append({"год": when, "что": line})
    # Ребёнок может взяться за то, чего не доделал отец: цель переживает
    # человека и достаётся следующему — иногда через полвека.
    if path.state in cat.BAD_ENDS and figure.children:
        for child_id in figure.children:
            child = world.figures.get(child_id)
            if child is None or not child.alive_at(year):
                continue
            child.notes.append("наследует цель: %s" % path.goal_key)
            path.legacy.append({"год": year + rng.randint(1, 30),
                                "что": "за то же взялся %s"
                                % child.plain_name})
            break

    # Наследие искажается: через век о человеке говорят обратное.
    if path.fame in (cat.HISTORIC, cat.GREAT) and rng.chance(0.3):
        line, was, became = rng.choice(cat.TWISTS)
        path.legacy.append({"год": year + rng.randint(60, 300),
                            "что": line})
        path.notes.append("наследие перевернулось: %s — %s" % (was, became))


def _write_down(ctx, path, figure, year: int) -> None:
    """Запись в летописи — только для тех, кого она и правда помнит."""
    world = ctx.world
    date = figure.death if figure.death else None
    if date is None:
        return
    goal = cat.GOALS_BY_KEY.get(path.goal_key)
    wish = goal.wish if goal is not None else path.wish
    body = "Хотел %s. %s %s" % (wish, path.did.capitalize()
                                if path.did else "", path.written)
    if figure.sex == "f":
        body = "Хотела %s. %s %s" % (wish, path.did.capitalize()
                                     if path.did else "", path.written)
    if path.irony:
        body = "%s И вот чем это кончилось: %s." % (body, path.irony)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="life_summed",
        title="Жизнь: %s" % figure.plain_name, text=body,
        importance=3 if path.fame == cat.HISTORIC else 4,
        actors=[figure.id], subjects=[path.id],
        region_id=figure.origin_region, race_id=figure.race_id)
    figure.deeds.append(event.id)
    path.notes.append("летопись подвела итог записью %s" % event.id)


# ---------------------------------------------------------------------------
# Узел жизненного пути
# ---------------------------------------------------------------------------

# Сколько узлов мир держит у одной жизни. У долгоживущих рас путь иначе
# растёт на полтораста записей, и биография перестаёт читаться.
MAX_STEPS = 54
# Что выбрасывается первым, когда записей слишком много: быт и мелочи.
SPARE_FIRST = ("быт", "малое", "снова")


def _step(path, year: int, kind: str, line: str, why: str = "") -> None:
    """Узел графа жизни: год, что это было и из-за чего."""
    if not line:
        return
    path.steps.append({"год": int(year), "вид": kind, "строка": line,
                       "из-за": why})
    if len(path.steps) <= MAX_STEPS:
        return
    # Прореживается только середина: начало биографии (желание, помехи) и
    # последние годы остаются целыми, иначе жизнь начинается с середины.
    head, tail = 6, 10
    if len(path.steps) <= head + tail + 1:
        return
    window = range(head, len(path.steps) - tail)
    for index in window:
        if path.steps[index]["вид"] in SPARE_FIRST:
            del path.steps[index]
            return
    del path.steps[head]


__all__ = ["upkeep"]
