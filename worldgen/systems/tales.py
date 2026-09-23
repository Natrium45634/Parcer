# -*- coding: utf-8 -*-
"""Сказания: как из мира складывается героическая история.

Летопись рассказывает о мире: державы, войны, веры, переселения.
Сказание рассказывает о людях: пятеро вышли из города, перевалили
хребет, потеряли двоих на болоте и спустились туда, откуда до них не
возвращались. Мир от этого меняется мало — но без этого его незачем
читать.

Сказание не придумывает мир заново. Беду оно берёт из того, что уже
прожито: живое чудовище, спящий след старого бедствия, нетронутое
место, орду за межой, пропавшую вещь, порченую землю, государя, которого
терпеть больше нельзя. Дружину собирает из живых людей этой земли, а
кого не хватает — тех приводит в мир. Дорога идёт по настоящим землям, и
за каждую землю берётся своя плата.

Исход не предрешён. Дружина сильнее беды — ещё не значит, что все
вернутся; слабее — ещё не значит, что все лягут. Семь исходов, и три из
них не победа и не поражение: запечатать, сторговаться или самому стать
тем, с кем шёл драться.

Что остаётся: чудовище убито или осмелело, место очищено или
разграблено, вещь вернулась в чьи-то руки, над павшими встал курган, о
живых сложили песню, а в ткани причин остался след — слава, страх или
долг, с которым будут жить их дети.
"""

from __future__ import annotations

from .. import history
from .. import narrative_tales as texts
from .. import races as races_mod
from .. import sites as sites_mod
from .. import tales as cat
from .. import monsters as mon
from ..models import ACTIVE, GONE

# Сколько сказаний случается: шанс за десятилетний такт. Их не должно
# быть много — иначе героическое становится бытовым.
TALE_RATE = 0.34
MAX_PER_ERA = 14           # больше за эпоху мир не запоминает
COMPANY_MIN, COMPANY_MAX = 3, 6
ROAD_MIN, ROAD_MAX = 1, 4
LOSS_ON_ROAD = 0.38        # шанс, что тяжёлый переход стоит спутника
FAME_FOR_LEGEND = 1.9      # с какой славы о сказании складывают песню

# Насколько силён спутник каждой роли. Вождь и клинок тянут дружину,
# певец идёт не за этим.
ROLE_POWER = {
    "вождь похода": 1.5, "клинок": 1.6, "стрелок": 1.2, "следопыт": 0.9,
    "знаток": 0.8, "чародей": 1.5, "жрец": 1.0, "вор": 0.9, "лекарь": 0.7,
    "певец": 0.3, "проводник": 0.7, "кузнец": 0.6,
}


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.active_settlements:
        return          # некому собирать дружину: городов ещё нет
    era_index = world.era_index_at(year)
    told = sum(1 for tale in world.tales.values()
               if world.era_index_at(tale.began.year) == era_index)
    if told >= MAX_PER_ERA:
        return

    rng = ctx.rng("tales", year)
    if not rng.chance(TALE_RATE * (period / 10.0) * ctx.density()):
        return

    threat = _pick_threat(ctx, rng, year)
    if threat is None:
        return
    _tell(ctx, rng, year, threat)


# ---------------------------------------------------------------------------
# Беда
# ---------------------------------------------------------------------------

class Threat:
    """Беда, ради которой собирают дружину."""

    __slots__ = ("kind", "obj", "region_id", "name", "word", "power",
                 "prize_id", "about")

    def __init__(self, kind, obj, region_id, name, word, power, prize_id="",
                 about=""):
        self.kind = kind
        self.obj = obj
        self.region_id = region_id
        self.name = name
        self.word = word
        self.power = float(power)
        self.prize_id = prize_id
        # Оборот для заголовка в родительном падеже: у государыни он не
        # такой, как у государя.
        self.about = about or cat.THREAT_WORD.get(kind, "о походе")


def _pick_threat(ctx, rng, year: int):
    """Из чего в этом мире прямо сейчас может выйти сказание."""
    world = ctx.world
    found = {}

    for monster_id in world.living_monsters:
        monster = world.monsters[monster_id]
        if not monster.region_id:
            continue
        found.setdefault(cat.MONSTER, []).append(Threat(
            cat.MONSTER, monster, monster.region_id, monster.name,
            monster.word.lower(), 1.0 + monster.power))

    hidden = _hidden_things(world)
    for relic_id in world.sleeping_relics:
        relic = world.relics.get(relic_id)
        if relic is None or not relic.region_id:
            continue
        # Если в той же земле лежит потерянная вещь, старое зло её и
        # стережёт: за ней и идут, а не просто «покончить с бедой».
        found.setdefault(cat.RELIC, []).append(Threat(
            cat.RELIC, relic, relic.region_id, relic.name,
            relic.kind, 1.2 + relic.potency * 0.6,
            prize_id=hidden.get(relic.region_id, "")))

    for site in world.sites.values():
        if site.status != sites_mod.UNTOUCHED or site.depth < 2:
            continue
        if not site.region_id:
            continue
        found.setdefault(cat.SITE, []).append(Threat(
            cat.SITE, site, site.region_id, site.name,
            site.kind, 0.8 + site.depth * 0.5,
            # Если в месте что-то лежит, идут именно за этим.
            prize_id=site.artifact_ids[0] if site.artifact_ids else "",
            about=cat.SITE_ABOUT.get(site.kind, "о месте")))

    for camp_id in world.active_camps:
        camp = world.camps[camp_id]
        if camp.population < 400:
            continue
        found.setdefault(cat.HORDE, []).append(Threat(
            cat.HORDE, camp, camp.region_id, camp.name,
            camp.word.lower(), 1.4 + camp.population / 2600.0))

    for artifact in world.artifacts.values():
        if artifact.where not in ("потерян", "в логове", "в кургане"):
            continue
        if artifact.fame < 1.2 or not artifact.region_id:
            continue
        found.setdefault(cat.LOSS, []).append(Threat(
            cat.LOSS, artifact, artifact.region_id, artifact.name,
            artifact.word.lower(), 1.0 + artifact.fame * 0.4,
            prize_id=artifact.id))

    for region in world.regions.values():
        if region.drowned or not region.known:
            continue
        gloom = ctx.darkness.get(region.id, 0.0)
        if region.magic > -0.3 and region.savagery < 0.62 and gloom < 0.35:
            continue
        found.setdefault(cat.BLIGHT, []).append(Threat(
            cat.BLIGHT, region, region.id, region.name, "порча",
            1.3 + gloom * 2.0 + max(0.0, -region.magic)))

    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        ruler = world.figures.get(polity.ruler_id)
        if ruler is None or not ruler.alive_at(year) or ruler.alignment > -2:
            continue
        crowned = "государыня" if ruler.sex == "f" else "государь"
        found.setdefault(cat.TYRANT, []).append(Threat(
            cat.TYRANT, ruler, _seat_region(world, polity),
            ruler.plain_name, crowned,
            1.6 + len(polity.settlement_ids) * 0.12,
            about="о государыне" if ruler.sex == "f" else "о государе"))

    if not found:
        return None
    kind = rng.weighted([(key, cat.THREAT_WEIGHT.get(key, 0.5))
                         for key in sorted(found)])
    choices = sorted(found[kind], key=lambda item: item.name)
    return rng.choice(choices)


def _hidden_things(world) -> dict:
    """Потерянные вещи по землям: что где лежит и кем не найдено."""
    out = {}
    for artifact in world.artifacts.values():
        if artifact.where in ("потерян", "в логове", "в кургане") \
                and artifact.region_id and artifact.region_id not in out:
            out[artifact.region_id] = artifact.id
    return out


def _seat_region(world, polity) -> str:
    capital = world.settlements.get(polity.capital_id)
    if capital is not None:
        return capital.region_id
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is not None:
            return settlement.region_id
    return ""


# ---------------------------------------------------------------------------
# Само сказание
# ---------------------------------------------------------------------------

def _tell(ctx, rng, year: int, threat: Threat) -> None:
    """Складывает сказание целиком — и кончает его этим самым годом.

    Дорога занимает годы, и раньше эти годы прибавлялись к нынешнему:
    сказание кончалось на четыре года позже, чем мир до них дожил. От
    этого и песня рождалась в будущем, и след в ткани причин закрывался
    раньше, чем появлялся. Поэтому дорога отсчитывается назад: вышли
    тогда-то, дошли и кончили — теперь.
    """
    world = ctx.world
    home = _home_city(ctx, rng, threat)
    if home is None:
        return
    race = races_mod.RACES_BY_ID.get(home.race_id)
    if race is None:
        return

    legs, spent = _plan_road(ctx, rng, home.region_id, threat.region_id)
    began_year = max(1, year - spent)
    began = ctx.date_in(rng, began_year)
    _call_key, call_note = rng.choice(cat.CALLS)
    company = _company(ctx, rng, race, home, began_year, year)
    if len(company) < COMPANY_MIN:
        return

    tale = world.add_tale(
        name="", kind=threat.kind, began=began,
        home_region_id=home.region_id, region_id=threat.region_id,
        foe_id=getattr(threat.obj, "id", ""), foe_name=threat.name,
        foe_word=threat.word, call=call_note, prize_id=threat.prize_id,
        polity_id=home.polity_id, company=company)

    where = _region_name(world, threat.region_id)
    tale.stages.append({"вид": "беда", "год": began_year,
                        "строка": texts.threat(
                            rng, threat.kind, where, _foe_phrase(threat),
                            _foe_nom(threat), name=threat.name)})
    tale.stages.append({"вид": "зов", "год": began_year,
                        "строка": texts.call(rng, call_note)})
    tale.stages.append({"вид": "сбор", "год": began_year,
                        "строка": texts.gathering(rng, len(company))})

    _walk(ctx, rng, tale, legs, began_year)
    outcome = _resolve(ctx, rng, tale, threat, year)
    _finish(ctx, rng, tale, threat, home, outcome, year)


def _home_city(ctx, rng, threat):
    """Откуда выходит дружина: свой город рядом с бедой, а нет — любой."""
    world = ctx.world
    region = world.regions.get(threat.region_id)
    near = set()
    if region is not None:
        near = {threat.region_id} | set(region.neighbors or ())
    close, far = [], []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.population < 400:
            continue
        race = races_mod.RACES_BY_ID.get(settlement.race_id)
        if race is None or race.category != races_mod.CIVILIZED:
            continue
        (close if settlement.region_id in near else far).append(settlement)
    # Своя беда ближе: дальние города идут на неё только если рядом
    # никого не осталось.
    pool = close or far
    if not pool:
        return None
    pool.sort(key=lambda item: item.id)
    return rng.weighted([(item, float(item.population)) for item in pool])


def _company(ctx, rng, race, home, began_year: int, end_year: int) -> list:
    """Кто идёт и зачем. Своих берут первыми, недостающих зовут со стороны."""
    world = ctx.world
    year = began_year
    size = rng.randint(COMPANY_MIN, COMPANY_MAX)
    roles = _roles(rng, size)
    taken = _known_hands(world, home, began_year, end_year)
    motives = list(cat.MOTIVES)
    company = []
    for index, (role, note) in enumerate(roles):
        figure = None
        if taken and rng.chance(0.45):
            figure = taken.pop()
        if figure is None:
            sex = "f" if rng.chance(0.34) else "m"
            figure = ctx.make_figure(
                rng, race, year, role=role, region_id=home.region_id,
                title="", sex=sex, home_id=home.id, epithet_chance=0.7,
                folk=world.folks.get(home.folk_id))
        if any(item["кто"] == figure.id for item in company):
            continue
        known = figure.deeds or len(figure.roles) > 1
        if role not in figure.roles:
            figure.roles.append(role)
        # Побуждения не повторяются: двое, бегущие от одного и того же,
        # читаются как опечатка, а не как дружина.
        motive = rng.choice(motives) if motives else rng.choice(cat.MOTIVES)
        if motive in motives:
            motives.remove(motive)
        company.append({
            "кто": figure.id, "имя": figure.name, "пол": figure.sex,
            "роль": role, "чем полезен": cat.by_sex(note, figure.sex),
            "зачем": cat.by_sex(motive, figure.sex),
            "судьба": cat.RETURNED,
            "свой": bool(known),     # мир знал этого человека и раньше
        })
        if index == 0:
            figure.notes.append("собрал дружину в %d году" % year
                                if figure.sex == "m"
                                else "собрала дружину в %d году" % year)
    return company


def _roles(rng, size: int) -> list:
    """Роли дружины: вождь один, прочие без повторов."""
    lead = cat.ROLES[0]
    rest = list(cat.ROLES[1:])
    chosen = [(lead[0], lead[1])]
    while len(chosen) < size and rest:
        pick = rng.weighted([(item, item[2]) for item in rest])
        rest.remove(pick)
        chosen.append((pick[0], pick[1]))
    return chosen


def _known_hands(world, home, began_year: int, end_year: int) -> list:
    """Живые люди этой земли, которых не жалко отправить в поход.

    Государей не берём: сказание о короле, сгинувшем в болоте, ломает
    половину престолонаследия. И брать можно только того, кто прожил всю
    дорогу: и в год выхода был взрослым, и к возвращению ещё жив.
    """
    crowns = {world.polities[pid].ruler_id for pid in world.active_polities}
    out = []
    for figure in world.figures.values():
        if figure.id in crowns or not figure.alive_at(end_year):
            continue
        if figure.origin_region != home.region_id:
            continue
        age = figure.age_at(began_year)
        if age < 16:
            continue
        if not any(word in role for role in figure.roles
                   for word in ("воин", "вожд", "охотник", "путешест",
                                "мореход", "чароде", "жрец", "учён")):
            continue
        out.append(figure)
    out.sort(key=lambda item: item.id)
    return out[:3]


# ---------------------------------------------------------------------------
# Дорога
# ---------------------------------------------------------------------------

def _plan_road(ctx, rng, start: str, goal: str):
    """Раскладывает дорогу заранее: земли, беды и сколько лет на это ушло.

    Считается до того, как сказание записано, — иначе не узнать, каким
    годом оно началось.
    """
    world = ctx.world
    path = _road(world, start, goal, rng)
    legs, spent = [], 0
    for region_id in path:
        trial, cost = rng.choice(cat.TRIALS)
        legs.append({"земля": region_id, "что случилось": trial,
                     "цена": cost, "через сколько": spent})
        if rng.chance(0.3):
            spent += 1          # иной переход занимает больше года
    return legs, spent


def _walk(ctx, rng, tale, legs, began_year: int) -> None:
    """Проводит дружину по заранее расписанной дороге."""
    world = ctx.world
    for leg in legs:
        when = began_year + leg["через сколько"]
        line = texts.road_leg(rng, _region_name(world, leg["земля"]),
                              leg["что случилось"])
        lost = ""
        if leg["цена"] and rng.chance(LOSS_ON_ROAD):
            fallen = _lose_one(ctx, rng, tale, when, cat.FELL_ROAD)
            if fallen is not None:
                line = "%s %s" % (line, texts.road_loss(
                    rng, fallen["имя"], fallen["пол"]))
                lost = fallen["кто"]
        tale.road.append({"земля": leg["земля"],
                          "что случилось": leg["что случилось"],
                          "потеря": lost})
        tale.stages.append({"вид": "дорога", "год": when, "строка": line})


def _road(world, start: str, goal: str, rng) -> list:
    """Земли между домом и бедой — по соседству, а не по прямой."""
    if not start or not goal:
        return [goal] if goal else []
    if start == goal:
        return [goal]
    # Обход в ширину по соседям: дорога идёт по земле, а не по воздуху.
    seen = {start: None}
    queue = [start]
    while queue:
        current = queue.pop(0)
        if current == goal:
            break
        region = world.regions.get(current)
        for other in sorted((region.neighbors or ()) if region else ()):
            if other not in seen and other in world.regions:
                seen[other] = current
                queue.append(other)
    if goal not in seen:
        return [goal]           # заморская беда: дорога туда своя, морская
    path = []
    node = goal
    while node is not None and node != start:
        path.append(node)
        node = seen[node]
    path.reverse()
    return path[-ROAD_MAX:] if len(path) > ROAD_MAX else path


def _lose_one(ctx, rng, tale, year: int, fate: str):
    """Кто-то из дружины дальше не идёт."""
    world = ctx.world
    alive = [item for item in tale.company if item["судьба"] == cat.RETURNED]
    if len(alive) <= 1:
        return None          # последнего не забираем: некому рассказывать
    # Вождя берут последним: сказание без вождя разваливается.
    weights = [(item, 0.35 if item["роль"] == "вождь похода" else 1.0)
               for item in alive]
    chosen = rng.weighted(weights)
    chosen["судьба"] = fate
    figure = world.figures.get(chosen["кто"])
    if figure is not None and fate in cat.DEAD_FATES:
        date = ctx.date_in(rng, year)
        if figure.alive_at(year):
            world.schedule_death(figure, date, "сгинул в походе"
                                 if figure.sex == "m" else "сгинула в походе")
    return chosen


# ---------------------------------------------------------------------------
# Испытание и исход
# ---------------------------------------------------------------------------

def _resolve(ctx, rng, tale, threat, year: int) -> str:
    """Чем всё кончилось. Сила дружины смещает веса, но не решает."""
    world = ctx.world
    strength = 0.0
    for item in tale.company:
        if item["судьба"] != cat.RETURNED:
            continue
        strength += ROLE_POWER.get(item["роль"], 0.8)
        figure = world.figures.get(item["кто"])
        if figure is not None:
            strength += 0.1 * float(figure.skills.get("война", 0) or 0)
    # Слаженная дружина берёт почти всё, что ей по росту: чародей и
    # клинок стоят больше, чем кажется. Но «почти» тут решающее.
    edge = strength / max(0.8, threat.power * 1.6)

    weights = []
    for key in cat.OUTCOMES:
        weight = cat.OUTCOME_WEIGHT[key]
        if key in (cat.WON, cat.COSTLY):
            weight *= max(0.2, min(3.0, edge))
        elif key == cat.FAILED:
            weight *= max(0.2, min(3.0, 1.0 / max(0.25, edge)))
        elif key == cat.SEALED:
            weight *= 1.4 if threat.kind in (cat.RELIC, cat.SITE,
                                             cat.BLIGHT) else 0.5
        elif key == cat.BARGAIN:
            if threat.kind == cat.BLIGHT:
                weight = 0.0        # с порченой землёй не сторгуешься
            elif threat.kind in (cat.TYRANT, cat.HORDE, cat.LOSS):
                weight *= 1.6
            else:
                weight *= 0.6
        weights.append((key, weight))
    outcome = rng.weighted(weights)

    tale.stages.append({"вид": "испытание", "год": year,
                        "строка": texts.trial(rng)})
    # У цели платят дороже, чем в пути.
    tolls = {cat.WON: 1, cat.COSTLY: 3, cat.FAILED: 4, cat.SEALED: 2,
             cat.BARGAIN: 0, cat.CHANGED: 2, cat.HOLLOW: 0}
    for _ in range(tolls.get(outcome, 1)):
        if rng.chance(0.72):
            _lose_one(ctx, rng, tale, year, cat.FELL_TRIAL)
    if outcome == cat.CHANGED:
        _stay_behind(ctx, rng, tale, year)
    tale.stages.append({"вид": "исход", "год": year, "строка": texts.outcome(
        rng, outcome, _foe_nom(threat))})
    return outcome


def _stay_behind(ctx, rng, tale, year: int) -> None:
    """Кто-то остаётся там — и становится частью того, с чем шёл драться."""
    alive = [item for item in tale.company if item["судьба"] == cat.RETURNED]
    if len(alive) <= 1:
        return
    chosen = rng.weighted([(item, 0.4 if item["роль"] == "вождь похода"
                            else 1.0) for item in alive])
    chosen["судьба"] = cat.STAYED
    figure = ctx.world.figures.get(chosen["кто"])
    if figure is not None:
        figure.roles.append("не вернулся из похода" if figure.sex == "m"
                            else "не вернулась из похода")


# ---------------------------------------------------------------------------
# След
# ---------------------------------------------------------------------------

def _finish(ctx, rng, tale, threat, home, outcome: str, year: int) -> None:
    world = ctx.world
    ended_year = year      # сказание кончается тем годом, в котором мир
    # Число внутри года берётся случайно, и в год начала оно запросто
    # выпадало раньше самого начала: сказание кончалось до того, как
    # началось. Потому конец всегда отсчитывается от начала.
    tale.ended = ctx.date_in(rng, ended_year, after=tale.began)
    tale.outcome = outcome
    tale.dead = sum(1 for item in tale.company
                    if item["судьба"] in cat.DEAD_FATES)
    tale.fame = round(cat.OUTCOME_FAME.get(outcome, 1.0)
                      * (1.0 + 0.12 * tale.dead)
                      * (0.8 + threat.power * 0.12), 2)
    # Плачем зовут то, где кого-то хоронили. Напрасный путь без потерь —
    # не плач, а досада.
    mournful = outcome == cat.FAILED or tale.dead >= 3
    # На одну и ту же беду ходят и второй раз, и третий. Первое сказание
    # зовут по беде, следующие — по тому, кто вёл дружину: иначе к имени
    # прирастает «Новый», и получается «Новый Плач о чудовище».
    again = any(other is not tale and other.foe_name == threat.name
                for other in world.tales.values())
    leader = world.figures.get(tale.company[0]["кто"]) if tale.company else None
    if again and leader is not None:
        maker = lambda: texts.leader_title(          # noqa: E731
            rng, leader.plain_name, leader.sex, mournful)
    else:
        maker = lambda: texts.title(                 # noqa: E731
            rng, tale.kind, threat.name, mournful, about=threat.about)
    tale.name = ctx.forge.unique("tale", maker, rng)
    tale.stages.append({"вид": "след", "год": ended_year,
                        "строка": texts.trace(rng)})

    _touch_foe(ctx, rng, tale, threat, outcome, ended_year)

    era_index = world.era_index_at(ended_year)
    heroes = [item["кто"] for item in tale.company]
    subjects = [tale.id]
    if tale.foe_id:
        subjects.append(tale.foe_id)
    # В летопись идёт не всё сказание, а его суть: полный текст лежит в
    # своём разделе, и повторять его тут значило бы залить летопись.
    names = ", ".join(item["имя"] for item in tale.company[:3])
    if len(tale.company) > 3:
        names += " и ещё %d" % (len(tale.company) - 3)
    body = "%s %s Вышли: %s. Исход: %s; не вернулось %d из %d." % (
        tale.stages[0]["строка"],
        tale.stages[-2]["строка"] if len(tale.stages) > 1 else "",
        names, outcome, tale.dead, len(tale.company))
    # Если на эту же беду уже ходили и не совладали, новое сказание
    # растёт из прежнего: так «Нити причин» показывают, откуда оно взялось.
    causes = []
    for other in world.tales.values():
        if other is tale or other.foe_name != tale.foe_name:
            continue
        if other.outcome in (cat.FAILED, cat.SEALED, cat.HOLLOW) \
                and other.event_ids:
            causes.append(other.event_ids[0])
    event = world.add_event(
        date=tale.ended, era_index=era_index, kind="tale",
        title=tale.name, text=body,
        importance=4 if tale.fame >= FAME_FOR_LEGEND else 3,
        actors=heroes[:4], subjects=subjects,
        region_id=tale.region_id,
        race_id=world.figures[heroes[0]].race_id if heroes else "",
        causes=causes[-2:])
    tale.event_ids.append(event.id)
    for figure_id in heroes:
        figure = world.figures.get(figure_id)
        if figure is not None:
            figure.deeds.append(event.id)
    # Награда раздаётся последней: и след в ткани причин, и песня
    # ссылаются на запись летописи, а её до этой минуты не было.
    _reward(ctx, rng, tale, threat, home, outcome, ended_year)


def _touch_foe(ctx, rng, tale, threat, outcome: str, year: int) -> None:
    """Что сталось с самой бедой."""
    world = ctx.world
    ends = cat.OUTCOME_ENDS_FOE.get(outcome, False)
    date = tale.ended
    survivor = _first_alive(world, tale)

    if threat.kind == cat.MONSTER:
        monster = threat.obj
        if ends and monster.id in world.living_monsters:
            world.end_monster(monster, date, mon.SLAIN, slayer=survivor)
            site = world.sites.get(monster.site_id)
            if site is not None:
                site.status = sites_mod.CLEARED
                site.opened = date
                site.opened_by = survivor.id if survivor else ""
                site.story = "здесь кончилось сказание по имени %s" % tale.name
                tale.site_id = site.id
                _empty_out(world, site, survivor, year, tale)
            if monster.hoard:
                tale.notes.append("из логова вынесли золота на %d"
                                  % monster.hoard)
                monster.hoard = 0
        elif outcome == cat.FAILED:
            monster.power = round(min(8.0, monster.power * 1.12), 2)
            monster.kills += tale.dead
            monster.heroes_eaten.extend(
                item["кто"] for item in tale.company
                if item["судьба"] in cat.DEAD_FATES)

    elif threat.kind == cat.RELIC:
        relic = threat.obj
        prize = world.artifacts.get(tale.prize_id)
        if prize is not None and (ends or outcome == cat.BARGAIN):
            _hand_over(world, prize, survivor, year, tale)
            tale.notes.append(
                "вещь по имени %s вынесли оттуда, где её стерегли"
                % prize.name)
        if ends:
            relic.status = "исчерпан"
            if relic.id in world.sleeping_relics:
                world.sleeping_relics.remove(relic.id)
            relic.notes.append("кончено сказанием по имени %s" % tale.name)
        elif outcome == cat.SEALED:
            relic.potency = max(1, relic.potency - 1)
            relic.notes.append("запечатан заново в %d году" % year)
        elif outcome == cat.FAILED:
            relic.potency = min(9, relic.potency + 1)
            relic.notes.append("дружина не дошла, и он стал сильнее")

    elif threat.kind == cat.SITE:
        site = threat.obj
        tale.site_id = site.id
        if ends or outcome == cat.BARGAIN:
            site.status = sites_mod.ROBBED
            site.opened = date
            site.opened_by = survivor.id if survivor else ""
            site.notes.append("вскрыто сказанием по имени %s" % tale.name)
            _empty_out(world, site, survivor, year, tale)
        elif outcome == cat.SEALED:
            site.status = sites_mod.UNTOUCHED
            site.guards = "печать, положенная поверх прежней"
        elif outcome == cat.FAILED:
            site.guards = "кости тех, кто приходил до вас"

    elif threat.kind == cat.HORDE:
        camp = threat.obj
        if ends and camp.id in world.active_camps:
            world.end_camp(camp, date, "разбит в сказании", GONE)
        elif outcome == cat.BARGAIN:
            camp.population = int(camp.population * 0.8)
        elif outcome == cat.FAILED:
            camp.population = int(camp.population * 1.15) + 40

    elif threat.kind == cat.LOSS:
        artifact = world.artifacts.get(tale.prize_id)
        if artifact is not None and (ends or outcome == cat.BARGAIN):
            _hand_over(world, artifact, survivor, year, tale)
            tale.notes.append(
                "вещь по имени %s вернулась в руки: %s"
                % (artifact.name,
                   survivor.name if survivor is not None else "ничьи"))

    elif threat.kind == cat.BLIGHT:
        region = threat.obj
        if ends:
            region.savagery = max(0.0, region.savagery - 0.18)
            region.magic = round(region.magic + 0.12, 3)
        elif outcome == cat.FAILED:
            region.savagery = min(1.0, region.savagery + 0.08)

    elif threat.kind == cat.TYRANT:
        ruler = threat.obj
        if ends and ruler.alive_at(year):
            world.schedule_death(ruler, date, "убит в своём чертоге"
                                 if ruler.sex == "m"
                                 else "убита в своём чертоге")


def _empty_out(world, site, hero, year: int, tale) -> None:
    """Что лежало в месте — то и вынесли.

    Без этого сказание кончалось словами, а вещь так и оставалась в
    кургане: мир не замечал, что курган уже вскрыт.
    """
    for artifact_id in list(site.artifact_ids):
        artifact = world.artifacts.get(artifact_id)
        if artifact is None:
            continue
        _hand_over(world, artifact, hero, year, tale)
        tale.notes.append("из места по имени %s вынесли вещь по имени %s"
                          % (site.name, artifact.name))
        if not tale.prize_id:
            tale.prize_id = artifact.id
    site.artifact_ids = []
    if site.riches:
        tale.notes.append("добычи взяли на %d" % site.riches)
        site.riches = 0


def _hand_over(world, artifact, hero, year: int, tale) -> None:
    """Вещь возвращается в чьи-то руки — и это попадает в её родословную."""
    artifact.where = "у владельца" if hero is not None else "потерян"
    artifact.owner_id = hero.id if hero is not None else ""
    artifact.site_id = ""
    artifact.lost = None
    artifact.status = ACTIVE
    artifact.trail.append({
        "year": int(year),
        "who": hero.name if hero is not None else "никто",
        "how": "вынесен из сказания по имени %s" % tale.name,
    })


def _reward(ctx, rng, tale, threat, home, outcome: str, year: int) -> None:
    """Что остаётся живым, павшим и земле."""
    world = ctx.world
    survivors = [item for item in tale.company
                 if item["судьба"] == cat.RETURNED]

    for item in survivors:
        figure = world.figures.get(item["кто"])
        if figure is None:
            continue
        figure.notes.append("%s — %s" % (tale.name, outcome))
        if outcome in (cat.WON, cat.COSTLY) and "герой сказания" not in figure.roles:
            figure.roles.append("герой сказания")

    # Курган над теми, кто не вернулся: у сказания должно быть место.
    if tale.dead and outcome != cat.HOLLOW and rng.chance(0.55):
        fallen = [item for item in tale.company
                  if item["судьба"] in cat.DEAD_FATES]
        site = world.add_site(
            kind=sites_mod.TOMB,
            name=ctx.forge.unique(
                "site",
                lambda: rng.choice(cat.barrow_names(len(fallen))), rng),
            region_id=tale.region_id, created=tale.ended,
            figure_id=fallen[0]["кто"] if fallen else "",
            depth=1, riches=int(60 * len(fallen)),
            guards=sites_mod.NOBODY,
            story="здесь легли те, кто шёл на %s" % threat.name)
        if not tale.site_id:
            tale.site_id = site.id
        tale.notes.append("над павшими встал курган по имени %s" % site.name)

    # След в ткани причин: слава победителям, страх перед тем, что уцелело.
    polity_id = home.polity_id
    if polity_id and polity_id in world.polities:
        if outcome in (cat.WON, cat.COSTLY):
            history.leave(world, history.GLORY, year, polity_id,
                          weight=0.6 + 0.2 * tale.fame,
                          note="сказание по имени %s" % tale.name,
                          event_id=tale.event_ids[0] if tale.event_ids else "")
        elif outcome in (cat.FAILED, cat.HOLLOW):
            history.leave(world, history.DREAD, year, polity_id,
                          weight=0.5 + 0.15 * threat.power,
                          note="от того, с чем не совладали: %s" % threat.name)

    # Песня: складывают не обо всяком походе, а о том, который запомнили.
    if tale.fame >= FAME_FOR_LEGEND:
        hero = world.figures.get(tale.company[0]["кто"])
        song = ctx.forge.unique(
            "legend",
            lambda: "%s о %s по имени %s" % (
                rng.choice(("Песнь", "Сказ", "Быль", "Старина")),
                "воине" if hero is None or hero.sex == "m" else "воительнице",
                hero.plain_name if hero is not None else threat.name), rng)
        legend = world.add_legend(
            name=song, born=tale.ended,
            event_id=tale.event_ids[0] if tale.event_ids else "",
            about="герой", subject_id=tale.company[0]["кто"],
            race_id=world.figures[tale.company[0]["кто"]].race_id,
            region_id=tale.region_id,
            truth="%s — %s" % (tale.name, outcome))
        tale.legend_id = legend.id


def _first_alive(world, tale):
    for item in tale.company:
        if item["судьба"] != cat.RETURNED:
            continue
        figure = world.figures.get(item["кто"])
        if figure is not None:
            return figure
    return None


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _region_name(world, region_id: str) -> str:
    region = world.regions.get(region_id)
    return region.name if region is not None else "безымянной"


def _foe_phrase(threat) -> str:
    """«дракон по имени Скарагорн» — оборот для косвенных падежей.

    Имена в мире не склоняются, поэтому родовое слово берёт падеж на
    себя, а имя стоит следом и остаётся именительным.
    """
    if threat.kind == cat.BLIGHT:
        return "порча в земле по имени %s" % threat.name
    return "%s по имени %s" % (threat.word, threat.name)


def _foe_nom(threat) -> str:
    """То же в именительном падеже."""
    if threat.kind == cat.BLIGHT:
        return "порча в земле по имени %s" % threat.name
    return "%s по имени %s" % (threat.word, threat.name)


__all__ = ["upkeep"]
