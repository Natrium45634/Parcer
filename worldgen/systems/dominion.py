# -*- coding: utf-8 -*-
"""Жизнь владений чудовищ: как земля достаётся нечеловеку и что потом.

Владение тут не ставится на карту, а **вырастает из того, что в мире уже
случилось**. Поэтому в начале стоит не бросок кости, а отбор: есть ли в
мире тот, кому это по силам (именное чудовище с делами за спиной, вождь
кончившегося нашествия, вернувшийся древний), есть ли место, которое он
способен удержать, и есть ли причина, которую можно показать пальцем в
летописи — павшая держава, кончившееся нашествие, беда, пустая земля.
Нет причины — нет и владения: чудовище остаётся чудовищем с логовом.

Второе: **размер считается, а не назначается**. Сила хозяина, способ
власти и предел вида дают число земель, и дракон, желающий тишины,
получает две долины, а не полмира. Способ власти при этом не украшение:
от него зависит и то, сколько земель держится, и то, как быстро всё
разваливается, когда хозяин перестал показываться.

Третье: **под властью живут**. Для каждой земли считаются те, кто в ней
остался: чем они стали хозяину, что отдают, как к этому относятся и что
делают, когда терпеть перестают. Из этого потом и растут восстания,
герои и то, что остаётся после.

И четвёртое: **владение не обязано быть вечным врагом**. Соседи терпят
его по названной причине — платят, не могут дойти, держат им межу, —
и триста лет такого соседства не недосмотр, а история.
"""

from __future__ import annotations

from .. import dominion as cat
from .. import invasion as inv_cat
from .. import monsters as mon
from .. import narrative_dominion as texts
from .. import subject as sub
from ..models import ACTIVE

# Как часто в мире вообще заводится владение и сколько их стоит разом.
# Числа малы нарочно: если владений в мире десяток, «владение чудовища»
# перестаёт быть событием и становится фоном.
RISE_RATE = 0.05            # шанс за десятилетний такт
WORLD_CAP = 4               # больше разом не стоит
DEEDS = 3                   # зверю — столько набегов и убитых, чтобы завести своё
FOLK_GROUPS = 4             # больше народов в списке подданных не держим
FOLK_LEAST = 0.06           # и не держим вовсе тех, кого против главного нет

# Сколько земель даёт сила. Чудовище силы 5 (дракон) при способе власти
# с размахом 1 берёт три земли; способ множит, вид обрезает сверху.
LAND_PER_POWER = 0.62
LAND_LEAST = 1

# Крепость власти: с чего начинается и куда ползёт.
FIRM_DRIFT = 0.04           # к своему пределу за такт
FIRM_ABSENT = 0.05          # сколько теряет владение без хозяина
FIRM_LEAST = 0.08           # ниже этого оно уже не владение

# Как часто что случается за десятилетие
SPREAD_RATE = 0.10          # прибавить землю
SHRINK_RATE = 0.06          # потерять землю
RISING_RATE = 0.09          # подняться против хозяина
WAR_RATE = 0.07             # война с соседней державой
CRISIS_RATE = 0.05          # кончилось то, чем оно живёт
MARK_RATE = 0.22            # земля меняется под хозяином
EDICT_RATE = 0.12           # появляется новое правило
VOICE_RATE = 0.18           # о нём начинают говорить ещё на один голос
LIE_CHANCE = 0.45           # и доля владений, о которых знают неверно

# Конец
END_BASE = 0.012            # сам по себе
END_STRAIN = 0.10           # добавка, когда владение трещит
RETURN_AFTER = 200          # через сколько лет запертый может вернуться
RETURN_RATE = 0.03
RETURN_CAP = 1              # дважды возвращаются только в сказках

# Возраст, после которого владение считается древним: столько живёт
# держава, и то не всякая.
ELDER_AGE = 800

# Роды нашествий, из которых вырастает владение, и во что именно.
KIND_BY_INVASION = {
    inv_cat.DEMONS: "demon",
    inv_cat.UNDEAD: "undead",
    inv_cat.DRAGONS: "dragon",
    inv_cat.GIANTS: "horde",
    inv_cat.BEASTS: "occupation",
    inv_cat.SWARM: "brood",
    inv_cat.DEEP: "occupation",
    inv_cat.ANCIENT: "elder",
    inv_cat.VOID: "warded",
    inv_cat.FAE: "warded",
    inv_cat.ELEMENTALS: "warded",
}

# Исходы нашествия, после которых пришедшие остаются хозяевами. Прочие
# («разбиты», «истреблены») владения не дают: это и есть разница между
# нашествием и властью.
STAY_OUTCOMES = (inv_cat.OUT_VASSAL, inv_cat.OUT_SETTLED, inv_cat.OUT_HELD,
                 inv_cat.OUT_DEAL, inv_cat.OUT_JOINED)

# Роды субъектов, которые вообще способны владеть землёй.
LORD_KINDS = (sub.DEMON, sub.UNDEAD, sub.VAMPIRE, sub.ANCIENT, sub.DRAGON,
              sub.SPIRIT, sub.MAGICAL, sub.MADE)


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("dominion", year)
    scale = period / 10.0

    standing = [item for item in world.dominions.values() if item.alive]
    if len(standing) < WORLD_CAP and rng.chance(RISE_RATE * scale):
        _rise(ctx, year, rng)

    for hold in sorted(world.dominions.values(), key=lambda item: item.id):
        # Заведённое в этот самый такт не проживает десятилетие сразу:
        # иначе владение успевает родиться, разойтись вширь, схватить
        # восстание и кончиться в одном году, и в летописи остаётся
        # владение сроком в ноль лет.
        if hold.began.year >= year:
            continue
        if hold.alive:
            _live(ctx, hold, year, period, rng)
        elif hold.end in cat.RETURNABLE:
            _maybe_return(ctx, hold, year, rng)


# ---------------------------------------------------------------------------
# Как оно заводится
# ---------------------------------------------------------------------------

def _rise(ctx, year: int, rng) -> None:
    """Выбрать из того, что мир уже вырастил, и завести владение."""
    world = ctx.world
    taken = {hold.lord_id for hold in world.dominions.values()
             if hold.alive and hold.lord_id}
    rows = []
    rows.extend(_from_monsters(world, year, taken))
    rows.extend(_from_invasions(world, year, taken))
    rows.extend(_from_scars(world, year, taken))
    rows.extend(_from_empty(world, year))
    if not rows:
        return
    rows.sort(key=lambda row: row["ключ"])
    pick = rng.weighted([(row, row["вес"]) for row in rows])
    _found(ctx, pick, year, rng)


def _from_monsters(world, year: int, taken: set) -> list:
    """Именное чудовище, за которым уже есть дела, и земля под ним."""
    rows = []
    for monster_id in sorted(world.living_monsters):
        monster = world.monsters.get(monster_id)
        if monster is None or monster.id in taken:
            continue
        # Ночная тварь живёт среди людей и землёй не владеет: её власть —
        # это чужое имя и чужой дом, а не межа.
        if monster.family != mon.BEAST or not monster.region_id:
            continue
        if monster.raids + len(monster.heroes_eaten) < DEEDS:
            continue
        region = world.regions.get(monster.region_id)
        if region is None or getattr(region, "drowned", False):
            continue
        near = _souls_near(world, region)
        for kind in cat.KINDS:
            if monster.breed not in kind.lords:
                continue
            rows.append({
                "ключ": "%s:%s" % (monster.id, kind.key),
                # Владение, под которым никто не живёт, — это опасное
                # место, а не власть. Поэтому там, где есть кем править,
                # оно заводится охотнее, и вид выбирается по тому же:
                # тролль на пустом перевале — владение одиночки, а
                # тролль над тремя деревнями берёт с них дань и
                # становится другим владением вовсе.
                #
                # Без этой поправки мир на карте вырождался: земель в
                # нём много, людей мало, и двадцать два владения из
                # двадцати восьми выходили логовами в глуши.
                "вид": kind.key,
                "вес": kind.weight * monster.power
                       * (0.4 + 1.6 * near) * _fits(kind, near),
                "хозяин": monster.id, "род хозяина": "чудовище",
                "имя": monster.name, "слово": _monster_word(monster),
                "пол": monster.gender, "земля": region.id,
                "сила": monster.power, "логово": monster.site_id,
                "гекс": -1, "нашествие": "", "беда": "", "держава": "",
                "спал": monster.status == mon.SLEEPING
                        or year - monster.born.year > 600,
            })
    return rows


def _fits(kind, near: float) -> float:
    """Идёт ли такой вид владения к такому месту.

    Виду, которому подданные нужны, нечего делать в пустой земле;
    виду, который их не знает, нечего делать посреди деревень.
    """
    if kind.folk == cat.NEED_FOLK:
        return 0.15 + 2.0 * near
    if kind.folk == cat.SOME_FOLK:
        return 0.6 + 1.0 * near
    return 1.0 - 0.6 * near


def _souls_near(world, region) -> float:
    """Насколько тут есть кем владеть: 0 — пусто, 1 — людно.

    Считается не только своя земля, но и соседние — вполовину. Логово
    стоит в глуши почти всегда, а владение складывается из глуши и той
    долины, что рядом: по одной своей земле выходило, что людей нет
    нигде, и мир на карте набивался логовами в пустоте.
    """
    lands = {region.id: 1.0}
    for other in (region.neighbors or ()):
        lands.setdefault(other, 0.5)
    souls = 0.0
    for item in world.settlements.values():
        if item.status == ACTIVE and item.region_id in lands:
            souls += item.population * lands[item.region_id]
    for item in world.tribes.values():
        if item.status == ACTIVE and item.region_id in lands:
            souls += item.population * lands[item.region_id]
    return min(1.0, souls / 20000.0)


def _monster_word(monster) -> str:
    """Как его называть в тексте: словом породы, а не ключом."""
    breed = mon.BREEDS_BY_KEY.get(monster.breed)
    word = (breed.word if breed is not None else monster.word) or "чудовище"
    return word.lower()


def _from_invasions(world, year: int, taken: set) -> list:
    """Нашествие, которое не отбили: пришедшие остались хозяевами."""
    rows = []
    for inv in sorted(world.invasions.values(), key=lambda item: item.id):
        if inv.outcome not in STAY_OUTCOMES:
            continue
        if inv.ended is None or inv.ended.year > year:
            continue
        # Пока нашествие свежо, это ещё нашествие. Владением оно
        # становится тогда, когда стало ясно, что они не уйдут.
        if year - inv.ended.year > 300:
            continue
        kind_key = KIND_BY_INVASION.get(inv.kind)
        if kind_key is None:
            continue
        calamity = world.calamities.get(inv.calamity_id)
        lands = [land for land in (calamity.region_ids if calamity else ())
                 if land in world.regions]
        if not lands:
            continue
        # Хозяин нужен и тут. Сперва ищется субъект истории, выросший
        # из этого нашествия, потом — его вождь, если у нашествия есть
        # имя вождя. Нет ни того, ни другого — владения не будет:
        # «пришли и остались» без того, кто остался, — это не власть,
        # а запись в летописи бед. Прежде такое проходило, и в мире
        # заводилось царство набега без хозяина вовсе.
        lord = _subject_of_invasion(world, inv)
        lord_kind = "субъект"
        if lord is None:
            lord = world.figures.get(inv.leader_id)
            lord_kind = "личность"
        if lord is None:
            continue
        lord_id = lord.id
        if lord_id in taken:
            continue
        if any(hold.invasion_id == inv.id for hold in world.dominions.values()):
            continue
        rows.append({
            "ключ": "%s:%s" % (inv.id, kind_key),
            "вид": kind_key, "вес": 1.6,
            "хозяин": lord_id, "род хозяина": lord_kind,
            "имя": lord.name,
            "слово": _invasion_word(inv, lord),
            "пол": getattr(lord, "sex", "m"),
            "земля": lands[0], "сила": 3.5 + 0.5 * len(lands),
            "логово": "", "гекс": -1,
            "нашествие": inv.id, "беда": inv.calamity_id,
            "держава": "", "спал": False, "земли": lands,
        })
    return rows


def _subject_of_invasion(world, inv):
    """Вождь нашествия, если он дорос до субъекта истории."""
    for item in sorted(world.subjects.values(), key=lambda row: row.id):
        if item.invasion_id == inv.id and item.kind in LORD_KINDS:
            return item
    return None


def _invasion_word(inv, lord) -> str:
    """Как звать хозяина: родом субъекта, а у человека — родом пришедших."""
    kind = getattr(lord, "kind", "")
    if kind and kind in sub.KINDS:
        return kind
    return inv.kind


def _from_scars(world, year: int, taken: set) -> list:
    """Проклятая земля: шрам беды, за которым кто-то стоит.

    У проклятия непременно есть источник, иначе это просто дурное
    место. Источником тут может быть только тот, кто в мире уже есть:
    древний, дух, чародейная сущность, нежить или божество. Нет
    такого — нет и проклятой земли, и это правильный ответ: в мире без
    подобных сущностей проклятие некому держать.
    """
    rows = []
    kind = cat.KINDS_BY_KEY["curse"]
    lords = [item for item in sorted(world.subjects.values(),
                                     key=lambda row: row.id)
             if item.kind in kind.lords and item.id not in taken
             and item.entered.year <= year
             and (item.ended is None or item.ended.year >= year)]
    if not lords:
        return rows
    for scar in sorted(world.scars.values(), key=lambda item: item.id):
        if scar.created.year > year or year - scar.created.year > 400:
            continue
        if scar.danger < 3 or scar.region_id not in world.regions:
            continue
        lord = lords[0]
        rows.append({
            "ключ": "%s:curse" % scar.id,
            "вид": "curse", "вес": 0.6,
            "хозяин": lord.id, "род хозяина": "субъект",
            "имя": lord.name, "слово": lord.kind, "пол": lord.sex,
            "земля": scar.region_id, "сила": 2.0 + scar.danger,
            "логово": scar.site_id, "гекс": -1,
            "нашествие": "", "беда": scar.calamity_id, "держава": "",
            "спал": True,
        })
    return rows


def _from_empty(world, year: int) -> list:
    """Ничья земля: там, где держава кончилась, а живых не осталось.

    Это единственное владение без хозяина. Оно держится не волей, а
    тем, что всякий, кто туда пошёл, не вернулся, — и потому земля
    выпадает из мира, пока кто-нибудь не решится.
    """
    rows = []
    held = set()
    for hold in world.dominions.values():
        if hold.alive:
            held.update(hold.region_ids)
    for region in sorted(world.regions.values(), key=lambda item: item.id):
        if region.id in held or getattr(region, "drowned", False):
            continue
        if not region.known:
            continue
        alive = [item for item in world.settlements.values()
                 if item.region_id == region.id and item.status == ACTIVE]
        if alive:
            continue
        ruins = [item for item in world.settlements.values()
                 if item.region_id == region.id and item.status != ACTIVE
                 and item.ended is not None and year - item.ended.year < 400]
        if not ruins:
            continue
        rows.append({
            "ключ": "%s:noman" % region.id,
            "вид": "noman", "вес": 0.5,
            "хозяин": "", "род хозяина": "", "имя": region.name,
            "слово": "", "пол": "m", "земля": region.id, "сила": 1.5,
            "логово": "", "гекс": -1, "нашествие": "", "беда": "",
            "держава": ruins[0].polity_id, "спал": False,
        })
    return rows


def _found(ctx, pick: dict, year: int, rng) -> None:
    """Собрать владение: причина, земли, способ власти, подданные, правила."""
    world = ctx.world
    kind = cat.KINDS_BY_KEY[pick["вид"]]
    home = world.regions.get(pick["земля"])
    if home is None:
        return
    origin, why = _origin_for(world, kind, pick, home, year, rng)
    if origin is None:
        return                  # причины не нашлось — владения не будет

    control = _control_for(world, kind, pick, home, rng)
    lands = _lands_for(world, kind, control, pick, home, rng)
    date = ctx.date_in(rng, year)
    hold = world.add_dominion(
        name=_name_for(world, rng, kind, home, pick),
        kind=kind.key, began=date,
        lord_id=pick["хозяин"], lord_kind=pick["род хозяина"],
        lord_name=pick["имя"], lord_word=pick["слово"],
        lord_gender=pick["пол"],
        origin=origin.key, origin_why=why,
        invasion_id=pick["нашествие"], calamity_id=pick["беда"],
        polity_id=pick["держава"],
        motive=rng.choice(list(cat.motives_for(kind.key))),
        control=control.key,
        strength=min(0.9, rng.jitter(control.firm, 0.2)),
        region_ids=list(lands),
        seat_kind=rng.choice(list(kind.seats)),
        seat_region=home.id, site_id=pick["логово"],
        hex_index=pick["гекс"],
        phase="rising",
    )
    hold.claimed_ids = _claims_for(world, hold, lands, rng)
    for land in lands:
        hold.held.append({"земля": land, "с": year, "по": 0})
    _needs_for(hold, kind, rng)
    hold.tolerated = rng.choice([key for key, _about in cat.TOLERATED])
    _folk_of(ctx, hold, year, rng)
    _edict_for(ctx, hold, year, rng)
    _tribute_for(hold, rng)
    _voices_of(ctx, hold, year, rng)
    hold.marks.append({"год": year, "что": "завелось",
                       "отчего": why})
    title, text = texts.rose(rng, hold, home)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year),
        kind="dominion_rise", title=title, text=text,
        importance=4 if hold.souls else 3,
        region_id=home.id, subjects=[hold.id],
        causes=[pick.get("повод", "")] if pick.get("повод") else None)
    hold.event_id = event.id


def _origin_for(world, kind, pick: dict, home, year: int, rng):
    """Причина, которую можно показать пальцем в летописи.

    Отбираются только те причины, под которые в мире есть основание:
    павшая держава, кончившееся нашествие, беда, пустая земля, спавший
    хозяин. Если не подошла ни одна — владение не заводится вовсе, и
    это правильно: беспричинных царств чудовищ быть не должно.
    """
    fallen = _fallen_here(world, home, year)
    woe = _woe_here(world, home, year)
    kin = _kin_here(world, home, year)
    empty = not [item for item in world.settlements.values()
                 if item.region_id == home.id and item.status == ACTIVE]
    rows = []
    for origin in cat.origins_for(kind.key):
        if origin.needs == cat.NEED_FALL and fallen is None:
            continue
        if origin.needs == cat.NEED_INVASION and not pick["нашествие"]:
            continue
        if origin.needs == cat.NEED_WOE and woe is None:
            continue
        if origin.needs == cat.NEED_SLEEPER and not pick["спал"]:
            continue
        if origin.needs == cat.NEED_EMPTY and not empty:
            continue
        if origin.needs == cat.NEED_KIN and kin is None:
            continue
        # Причина, которую можно показать пальцем в летописи, лучше
        # причины вообще: «после беды по имени X» — история, а «они
        # ушли сюда от того, кто страшнее их» — присказка. Поэтому
        # опирающиеся на событие тянут вдвое.
        rows.append((origin, 2.2 if origin.needs else 1.0))
    if not rows:
        return None, ""
    origin = rng.weighted(rows)
    why = origin.about
    if origin.needs == cat.NEED_FALL and fallen is not None:
        why = "держава по имени %s кончилась, а земля осталась" \
            % fallen.full_name
    elif origin.needs == cat.NEED_WOE and woe is not None:
        why = "%s — после беды по имени %s" % (origin.about, woe.name)
    elif origin.needs == cat.NEED_KIN and kin is not None:
        why = "%s; прежде тут стояло %s" % (origin.about, kin.name)
    elif origin.needs == cat.NEED_INVASION and pick["нашествие"]:
        inv = world.invasions.get(pick["нашествие"])
        if inv is not None:
            why = "%s — так кончилось то, что звали «%s»" \
                % (origin.about, inv.full_name)
    return origin, why


def _fallen_here(world, region, year: int):
    """Держава, которая держала эту землю и кончилась не слишком давно."""
    best = None
    for polity in sorted(world.polities.values(), key=lambda item: item.id):
        if polity.status == ACTIVE or polity.ended is None:
            continue
        if region.id not in polity.region_ids:
            continue
        if not 0 <= year - polity.ended.year <= 500:
            continue
        if best is None or polity.ended.year > best.ended.year:
            best = polity
    return best


def _kin_here(world, region, year: int):
    """Владение, стоявшее тут прежде: из него можно расколоться или восстать.

    Без него причины «раскол», «восстание подчинённых» и «возвращение»
    были бы словами: расколоться не от чего, восставать не против кого.
    """
    best = None
    for hold in sorted(world.dominions.values(), key=lambda item: item.id):
        if region.id not in hold.region_ids and region.id not in [
                row.get("земля") for row in hold.held]:
            continue
        if hold.began.year > year:
            continue
        if hold.ended is not None and year - hold.ended.year > 400:
            continue
        if best is None or hold.began.year > best.began.year:
            best = hold
    return best


def _woe_here(world, region, year: int):
    """Беда, прошедшая по этой земле на памяти живущих."""
    best = None
    for woe in sorted(world.calamities.values(), key=lambda item: item.id):
        if region.id not in woe.region_ids:
            continue
        if woe.start is None or woe.start.year > year:
            continue
        if year - woe.start.year > 300:
            continue
        if best is None or woe.start.year > best.start.year:
            best = woe
    return best


def _control_for(world, kind, pick: dict, home, rng):
    """Чем он будет держать землю: по виду владения и по тому, есть ли люди.

    Способ, которому нужны подданные, в пустой земле не выпадает: не на
    ком. Отсюда и выходит разница между царством и логовом.
    """
    folk = bool([item for item in world.settlements.values()
                 if item.region_id == home.id and item.status == ACTIVE])
    rows = []
    for key in kind.controls:
        model = cat.CONTROLS_BY_KEY.get(key)
        if model is None or (model.folk and not folk):
            continue
        rows.append((model, 1.0))
    if not rows:
        return cat.CONTROLS_BY_KEY["fear"]
    return rng.weighted(rows)


def _lands_for(world, kind, control, pick: dict, home, rng) -> list:
    """Сколько земель он удержит — считается, а не назначается."""
    power = float(pick.get("сила", 2.0))
    room = int(LAND_LEAST + power * LAND_PER_POWER * control.reach)
    room = max(LAND_LEAST, min(kind.wide, room))
    lands = [home.id]
    known = list(pick.get("земли") or ())
    for land in known:
        if land not in lands and len(lands) < room:
            lands.append(land)
    for land in sorted(home.neighbors or ()):
        if len(lands) >= room:
            break
        region = world.regions.get(land)
        if region is None or getattr(region, "drowned", False):
            continue
        if _held_by_other(world, land):
            continue
        lands.append(land)
    return lands


def _held_by_other(world, region_id: str) -> bool:
    for hold in world.dominions.values():
        if hold.alive and region_id in hold.region_ids:
            return True
    return False


def _claims_for(world, hold, lands, rng) -> list:
    """На что он притязает сверх того, что держит.

    Притязание — не власть: за межой о нём могут и не знать. Но из
    него растут споры, войны и «он считает эту землю своей до сих пор».
    """
    claims = list(lands)
    for land in lands:
        region = world.regions.get(land)
        for near in sorted((region.neighbors or ()) if region else ()):
            if near in claims or near not in world.regions:
                continue
            if rng.chance(0.3):
                claims.append(near)
    return claims


def _needs_for(hold, kind, rng) -> None:
    """Чем оно живёт и что будет, если этого не станет."""
    keys = cat.NEEDS_BY_KIND.get(kind.key) or ("none",)
    hold.need = rng.choice(list(keys))
    row = cat.NEEDS_BY_KEY.get(hold.need)
    hold.need_risk = row[2] if row else ""


def _tribute_for(hold, rng) -> None:
    """Чем платят. Пустому владению платить некому — и это ответ."""
    if not hold.folk:
        return
    model = cat.CONTROLS_BY_KEY.get(hold.control)
    if model is not None and model.key in ("ecological", "nesting",
                                           "contested", "claimed"):
        return
    hold.tribute = rng.choice(list(cat.tributes_for(hold.kind)))
    hold.tribute_why = cat.tribute_about(hold.tribute)
    ways = [key for key, _w, _a in cat.RULE_WAYS]
    hold.ways = [rng.choice(ways)]
    if rng.chance(0.4):
        second = rng.choice(ways)
        if second not in hold.ways:
            hold.ways.append(second)


# ---------------------------------------------------------------------------
# Кто под ним живёт
# ---------------------------------------------------------------------------

def _folk_of(ctx, hold, year: int, rng) -> None:
    """Собрать подчинённых: кто остался в его землях и чем он им стал."""
    world = ctx.world
    kind = cat.KINDS_BY_KEY[hold.kind]
    if kind.folk == cat.NO_FOLK:
        return
    groups = {}
    for item in sorted(world.settlements.values(), key=lambda row: row.id):
        if item.region_id not in hold.region_ids or item.status != ACTIVE:
            continue
        row = groups.setdefault(item.race_id, {"душ": 0, "где": []})
        row["душ"] += item.population
        row["где"].append(item.id)
    for item in sorted(world.tribes.values(), key=lambda row: row.id):
        if item.region_id not in hold.region_ids or item.status != ACTIVE:
            continue
        row = groups.setdefault(item.race_id, {"душ": 0, "где": []})
        row["душ"] += item.population
        row["где"].append(item.id)
    if not groups:
        return
    # Под владением живёт не весь справочник рас. Берутся те, кого тут
    # заметно, — иначе список подданных читается как перепись, а
    # «четырнадцать народов под драконом» не говорит ни о чём.
    rows = sorted(groups.items(), key=lambda pair: (-pair[1]["душ"], pair[0]))
    biggest = float(rows[0][1]["душ"]) or 1.0
    keep = [pair for pair in rows[:FOLK_GROUPS]
            if pair[1]["душ"] >= biggest * FOLK_LEAST or pair is rows[0]]
    for race_id, row in keep:
        standing = _standing_for(hold, race_id, rng)
        hold.folk.append({
            "раса": race_id, "душ": int(row["душ"]),
            "где": row["где"][:4],
            "как": standing,
            "чувство": _feeling_for(standing, rng),
            "год": year,
        })


def _standing_for(hold, race_id: str, rng) -> str:
    """Чем именно народ стал хозяину: по способу власти, а не наугад."""
    model = hold.control
    pools = {
        "direct": ("subject", "labour", "occupied", "ruling"),
        "military": ("occupied", "soldiers", "labour", "subject"),
        "tribute": ("tribute", "vassal", "free"),
        "cult": ("cult", "subject", "kept"),
        "fear": ("tribute", "occupied", "free", "hidden"),
        "vassal": ("vassal", "ruling", "tribute"),
        "magical": ("subject", "cattle", "kept", "unknown"),
        "ecological": ("hidden", "fled", "free"),
        "nesting": ("hidden", "fled", "cattle"),
        "route": ("tribute", "free"),
        "indirect": ("free", "tribute", "unknown"),
        "claimed": ("free",),
        "contested": ("free", "hidden"),
    }
    keys = [key for key in pools.get(model, ("subject",))
            if key in cat.STANDINGS_BY_KEY]
    return rng.choice(keys) if keys else "subject"


def _feeling_for(standing: str, rng) -> str:
    """Как они к этому относятся. Не одно «ненавидят»."""
    row = cat.STANDINGS_BY_KEY.get(standing)
    pairs = []
    for key, _word, _about in cat.FEELINGS:
        weight = 1.0
        if row is not None:
            if key in ("hate", "fear") and row.risk >= 0.5:
                weight = 2.0
            if key in ("deal", "bear", "lesser") and row.free >= 0.4:
                weight = 1.8
            if key == "revere" and row.free <= 0.4:
                weight = 0.8
            if key == "serve" and standing in ("ruling", "soldiers", "cult"):
                weight = 2.2
        pairs.append((key, weight))
    return rng.weighted(pairs)


def _edict_for(ctx, hold, year: int, rng) -> None:
    """Правило, которое тут действует, — с карой и причиной."""
    rows = cat.edicts_for(hold.kind)
    if not rows:
        return
    have = {row.get("ключ") for row in hold.edicts}
    rows = [item for item in rows if item.key not in have]
    if not rows:
        return
    edict = rng.choice(list(rows))
    hold.edicts.append({"ключ": edict.key, "что": edict.said,
                        "отчего": edict.why, "кара": edict.pain,
                        "год": year})


# ---------------------------------------------------------------------------
# Правда и то, что о ней говорят
# ---------------------------------------------------------------------------

def _voices_of(ctx, hold, year: int, rng) -> None:
    """Пять голосов об одном владении — и ни один не обязан быть правым."""
    if not hold.told:
        hold.told[cat.VOICE_NEIGHBOUR] = texts.voice_said(
            rng, hold, cat.VOICE_NEIGHBOUR)
    if rng.chance(LIE_CHANCE) and not hold.lie:
        key = rng.choice([row[0] for row in cat.LIES])
        hold.lie = key
        hold.truth = cat.LIES_BY_KEY[key][1]


def _add_voice(ctx, hold, year: int, rng) -> None:
    left = [voice for voice in cat.VOICES if voice not in hold.told]
    if not left:
        return
    voice = rng.choice(left)
    hold.told[voice] = texts.voice_said(rng, hold, voice)


# ---------------------------------------------------------------------------
# Жизнь владения
# ---------------------------------------------------------------------------

def _live(ctx, hold, year: int, period: int, rng) -> None:
    world = ctx.world
    scale = period / 10.0
    lord = _lord_state(world, hold)
    lord_here = lord == LORD_HERE

    # Хозяина не стало, а владение осталось: дань собирают по привычке,
    # и годами никто не проверяет, кому она идёт. Но держится такое
    # недолго.
    if not lord_here and hold.kind not in cat.LORDLESS:
        hold.strength -= FIRM_ABSENT * scale
        if not any(row.get("что") == "хозяина не стало" for row in hold.marks):
            hold.marks.append({
                "год": year, "что": "хозяина не стало",
                "отчего": "его прикончили, а правила его остались"
                if lord == LORD_GONE
                else "его не видели, а правила его остались"})
    else:
        model = cat.CONTROLS_BY_KEY.get(hold.control)
        aim = model.firm if model is not None else 0.5
        if hold.strength < aim:
            hold.strength = min(aim, hold.strength + FIRM_DRIFT * scale)

    _phase_step(hold, year)

    if rng.chance(MARK_RATE * scale):
        _land_mark(ctx, hold, year, rng)
    if hold.folk and rng.chance(EDICT_RATE * scale):
        _edict_for(ctx, hold, year, rng)
    if rng.chance(VOICE_RATE * scale):
        _add_voice(ctx, hold, year, rng)
    if rng.chance(SPREAD_RATE * scale * max(0.2, hold.strength)):
        _spread(ctx, hold, year, rng)
    if rng.chance(SHRINK_RATE * scale):
        _shrink(ctx, hold, year, rng)
    if hold.folk and rng.chance(RISING_RATE * scale * _anger(hold)):
        _rising(ctx, hold, year, rng)
    if rng.chance(WAR_RATE * scale):
        _war(ctx, hold, year, rng)
    if rng.chance(CRISIS_RATE * scale):
        _crisis(ctx, hold, year, rng)

    _refresh_folk(ctx, hold, year)
    _check_end(ctx, hold, year, rng, scale, lord)


LORD_HERE = "тут"
LORD_GONE = "сгинул"
LORD_QUIET = "молчит"


def _lord_state(world, hold) -> str:
    """Что с хозяином: он тут, его не стало или его просто не видно.

    Разница важна для конца владения. Убитый хозяин — это «его
    прикончили» и дележ наследства; хозяин, которого не видели, — это
    «оно уснуло», и такое возвращается. Прежде оба случая давали одно
    слово, и в летопись попадало «он уснул» про того, кого зарубили.
    """
    if hold.kind in cat.LORDLESS:
        return LORD_HERE
    lord = world.entity(hold.lord_id) if hold.lord_id else None
    if lord is None:
        return LORD_QUIET
    if getattr(lord, "status", "") in (mon.SLAIN, mon.DRIVEN):
        return LORD_GONE
    if getattr(lord, "ended", None) is not None:
        return LORD_GONE
    return LORD_HERE


def _phase_step(hold, year: int) -> None:
    """Ступень жизни владения — из его собственного состояния, не по кости."""
    age = year - hold.began.year
    was = hold.phase
    if hold.strength < 0.2:
        phase = "breaking"
    elif hold.strength < 0.35:
        phase = "straining"
    elif age >= ELDER_AGE:
        phase = "settled"
    elif len(hold.region_ids) > 1 and age < 150:
        phase = "spreading"
    elif age < 40:
        phase = "taking"
    else:
        phase = "holding"
    if phase != was:
        hold.phase = phase
        hold.marks.append({"год": year, "что": cat.PHASES_BY_KEY[phase],
                           "отчего": _phase_why(hold)})


def _phase_why(hold) -> str:
    if hold.strength < 0.2:
        return "держать стало нечем"
    if hold.strength < 0.35:
        return "его слушаются всё хуже"
    return "так вышло само собой"


def _anger(hold) -> float:
    """Насколько тут готовы подняться: из положения подданных, а не из кости."""
    worst = 0.0
    for row in hold.folk:
        standing = cat.STANDINGS_BY_KEY.get(row.get("как"))
        if standing is None:
            continue
        heat = standing.cost + standing.risk - standing.free
        if row.get("чувство") in ("hate",):
            heat += 0.6
        if row.get("чувство") in ("deal", "serve", "revere", "forgot"):
            heat -= 0.5
        worst = max(worst, heat)
    return max(0.1, min(2.0, worst))


def _land_mark(ctx, hold, year: int, rng) -> None:
    """Земля меняется под хозяином — и след этот остаётся дольше него."""
    keys = cat.marks_for(hold.kind)
    if not keys:
        return
    have = {row.get("что") for row in hold.land_marks}
    keys = [key for key in keys if cat.LAND_MARKS_BY_KEY[key][0] not in have]
    if not keys:
        return
    key = rng.choice(keys)
    land = rng.choice(list(hold.region_ids))
    region = ctx.world.regions.get(land)
    hold.land_marks.append({"год": year, "земля": land,
                            "что": cat.LAND_MARKS_BY_KEY[key][0]})
    if region is not None and rng.chance(0.4):
        title, text = texts.land_changed(rng, hold, region,
                                         cat.LAND_MARKS_BY_KEY[key][0])
        ctx.world.add_event(
            date=ctx.date_in(rng, year),
            era_index=ctx.world.era_index_at(year),
            kind="dominion_land", title=title, text=text, importance=2,
            region_id=land, subjects=[hold.id])


def _spread(ctx, hold, year: int, rng) -> None:
    """Прибавить землю — если есть куда и если на неё хватает силы."""
    world = ctx.world
    kind = cat.KINDS_BY_KEY[hold.kind]
    if len(hold.region_ids) >= kind.wide:
        return
    near = []
    for land in hold.region_ids:
        region = world.regions.get(land)
        for other in sorted((region.neighbors or ()) if region else ()):
            if other in hold.region_ids or other not in world.regions:
                continue
            if _held_by_other(world, other):
                continue
            if getattr(world.regions[other], "drowned", False):
                continue
            near.append(other)
    if not near:
        return
    land = rng.choice(sorted(set(near)))
    hold.region_ids.append(land)
    hold.held.append({"земля": land, "с": year, "по": 0})
    if land not in hold.claimed_ids:
        hold.claimed_ids.append(land)
    hold.marks.append({"год": year, "что": "взял ещё землю",
                       "отчего": "ему стало тесно"})
    region = world.regions.get(land)
    title, text = texts.took_land(rng, hold, region)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="dominion_spread", title=title, text=text, importance=3,
        region_id=land, subjects=[hold.id])


def _shrink(ctx, hold, year: int, rng) -> None:
    """Потерять землю: власть ушла оттуда раньше, чем хозяин."""
    if len(hold.region_ids) <= 1:
        return
    land = rng.choice(sorted(hold.region_ids[1:]))
    hold.region_ids.remove(land)
    _close_span(hold, land, year)
    if land not in hold.contested_ids:
        hold.contested_ids.append(land)
    hold.marks.append({"год": year, "что": "земля вышла из-под него",
                       "отчего": "дотуда у него перестали доходить руки"})


def _close_span(hold, land: str, year: int) -> None:
    for row in reversed(hold.held):
        if row.get("земля") == land and not row.get("по"):
            row["по"] = year
            return


def _rising(ctx, hold, year: int, rng) -> None:
    """Подняться против хозяина. Победа не обещана никому."""
    world = ctx.world
    rows = [row for row in hold.folk
            if row.get("как") not in cat.OUTSIDE]
    if not rows:
        return
    who = max(rows, key=lambda row: (row.get("душ", 0), row.get("раса", "")))
    way = rng.choice([key for key, _w, _a in cat.RESIST_WAYS])
    odds = 0.18 + 0.3 * (1.0 - hold.strength)
    if way == "rise":
        odds += 0.1
    if rng.chance(odds):
        end = rng.weighted([("fell", 1.0), ("freed", 1.4), ("bled", 1.6),
                            ("deal", 1.2)])
    else:
        end = rng.weighted([("crushed", 2.0), ("betrayed", 0.8),
                            ("quiet", 1.2), ("bled", 0.8)])
    hold.risings.append({"год": year, "кто": who.get("раса", ""),
                         "как": way, "чем": end})
    if end == "freed":
        _shrink(ctx, hold, year, rng)
        hold.strength = max(0.05, hold.strength - 0.12)
    elif end == "bled":
        hold.strength = max(0.05, hold.strength - 0.08)
    elif end == "deal":
        hold.strength = max(0.05, hold.strength - 0.04)
        who["как"] = "tribute" if who.get("как") != "tribute" else "free"
    elif end == "crushed":
        hold.strength = min(0.95, hold.strength + 0.05)
        who["душ"] = int(who.get("душ", 0) * 0.8)
    title, text = texts.rising(rng, hold, who, way, end)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="dominion_rising", title=title, text=text,
        importance=4 if end in ("fell", "freed") else 3,
        region_id=hold.seat_region, subjects=[hold.id],
        race_id=who.get("раса", ""))
    if end == "fell":
        _end(ctx, hold, year, rng, "revolt",
             "подданные поднялись, и на этот раз у них вышло")


def _war(ctx, hold, year: int, rng) -> None:
    """Соседняя держава пробует его на зуб — или он её."""
    world = ctx.world
    neighbours = []
    for polity in sorted(world.polities.values(), key=lambda item: item.id):
        if polity.status != ACTIVE:
            continue
        if set(polity.region_ids) & set(hold.claimed_ids):
            neighbours.append(polity)
    if not neighbours:
        return
    foe = rng.choice(neighbours)
    theirs = 0.35 + 0.25 * min(1.0, len(foe.settlement_ids) / 8.0)
    if rng.chance(theirs):
        out = "отбили" if rng.chance(0.55) else "выбили из части земель"
        if out.startswith("выбили"):
            _shrink(ctx, hold, year, rng)
            hold.strength = max(0.05, hold.strength - 0.1)
    else:
        out = "ушли ни с чем" if rng.chance(0.6) else "потеряли войско"
        hold.strength = min(0.95, hold.strength + 0.06)
    hold.wars.append({"год": year, "с кем": foe.id, "чем": out})
    title, text = texts.war_came(rng, hold, foe, out)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="dominion_war", title=title, text=text, importance=3,
        region_id=hold.seat_region, subjects=[hold.id], actors=[foe.id])


def _crisis(ctx, hold, year: int, rng) -> None:
    """Кончилось то, чем оно живёт."""
    if hold.need in ("", "none"):
        return
    row = cat.NEEDS_BY_KEY.get(hold.need)
    if row is None:
        return
    hold.strength = max(0.03, hold.strength - 0.15)
    hold.marks.append({"год": year, "что": "перебои с тем, чем он жив",
                       "отчего": row[2]})
    title, text = texts.crisis(rng, hold, row)
    ctx.world.add_event(
        date=ctx.date_in(rng, year),
        era_index=ctx.world.era_index_at(year),
        kind="dominion_crisis", title=title, text=text, importance=3,
        region_id=hold.seat_region, subjects=[hold.id])


def _refresh_folk(ctx, hold, year: int) -> None:
    """Пересчитать, сколько душ под ним осталось."""
    world = ctx.world
    counts = {}
    for item in world.settlements.values():
        if item.region_id in hold.region_ids and item.status == ACTIVE:
            counts[item.race_id] = counts.get(item.race_id, 0) + item.population
    for item in world.tribes.values():
        if item.region_id in hold.region_ids and item.status == ACTIVE:
            counts[item.race_id] = counts.get(item.race_id, 0) + item.population
    for row in hold.folk:
        left = int(counts.get(row.get("раса"), 0))
        # Народ, которого в этих землях не осталось, перестаёт быть
        # данником: он не платит, он ушёл. Иначе в летописи стоят
        # подданные, которых нет, и у владения выходит ноль душ при
        # четырёх народах под ним.
        if not left and row.get("как") not in cat.OUTSIDE:
            row["как"] = "fled"
            row["чувство"] = "hate" if row.get("чувство") != "hate" \
                else row["чувство"]
        row["душ"] = left


def _check_end(ctx, hold, year: int, rng, scale: float, lord: str) -> None:
    """Не пора ли этому кончиться — и если да, то отчего именно.

    Конец выбирается не из общего мешка: что случилось с хозяином, то и
    решает. Пока он тут, владение кончают люди — убивают, выбивают,
    запирают. Когда его прикончили, остаётся дележ и забвение. Когда
    его просто не видно, владение засыпает — и такое возвращается.
    """
    if hold.strength <= FIRM_LEAST:
        key = {"тут": "faded", "сгинул": "faded", "молчит": "sleep"}[lord]
        _end(ctx, hold, year, rng, key,
             "держать стало нечем, и власть эта сошла на нет")
        return
    chance = END_BASE * scale
    if hold.phase in ("straining", "breaking"):
        chance += END_STRAIN * scale
    if lord != LORD_HERE:
        chance += 0.06 * scale
    if not rng.chance(chance):
        return
    if lord == LORD_HERE:
        pairs = [("slain", 1.4), ("driven", 1.0), ("war", 1.0), ("gone", 0.8),
                 ("starved", 0.7), ("split", 0.6), ("taken", 0.6),
                 ("sealed", 0.7), ("melted", 0.5), ("faded", 0.6)]
    elif lord == LORD_GONE:
        pairs = [("split", 1.4), ("taken", 1.2), ("faded", 1.4),
                 ("melted", 1.0), ("starved", 0.8)]
    else:
        pairs = [("sleep", 1.6), ("faded", 1.2), ("melted", 0.8),
                 ("split", 0.8), ("taken", 0.8)]
    if not hold.folk:
        # «Стало державой» бывает только там, где было кому ею стать.
        pairs = [(key, weight) for key, weight in pairs if key != "melted"]
    key = rng.weighted(pairs)
    _end(ctx, hold, year, rng, key, cat.ENDS_BY_KEY[key][1])


def _end(ctx, hold, year: int, rng, key: str, how: str) -> None:
    world = ctx.world
    hold.ended = ctx.date_in(rng, year)
    hold.end = key
    hold.end_how = how
    hold.status = "кончилось"
    hold.phase = "over"
    for land in list(hold.region_ids):
        _close_span(hold, land, year)
    # Кончившееся владение не держит ничего: «держит на деле» — это
    # настоящее время. Что оно держало, остаётся в записи земель, и
    # оттуда же потом берётся его размах.
    hold.region_ids = []
    hold.marks.append({"год": year, "что": cat.ENDS_BY_KEY[key][0],
                       "отчего": how})
    title, text = texts.ended(rng, hold)
    world.add_event(
        date=hold.ended, era_index=world.era_index_at(year),
        kind="dominion_end", title=title, text=text,
        importance=4 if hold.souls or len(hold.region_ids) > 1 else 3,
        region_id=hold.seat_region, subjects=[hold.id],
        causes=[hold.event_id] if hold.event_id else None)


def _maybe_return(ctx, hold, year: int, rng) -> None:
    """Запертое и уснувшее возвращается — но не всякое и не дважды."""
    if hold.ended is None or year - hold.ended.year < RETURN_AFTER:
        return
    if len([row for row in hold.marks if row.get("что") == "вернулось"]) \
            >= RETURN_CAP:
        return
    if not rng.chance(RETURN_RATE):
        return
    world = ctx.world
    # Возвращается он на то, что держал напоследок, а не на всё, что
    # прошло через его руки за триста лет.
    last = hold.ended.year
    back = sorted({row.get("земля") for row in hold.held
                   if int(row.get("по", 0)) == last and row.get("земля")})
    hold.ended = None
    hold.status = "вернулось"
    hold.end = ""
    hold.end_how = ""
    hold.phase = "rising"
    hold.strength = 0.3
    hold.region_ids = list(back)
    for land in back:
        hold.held.append({"земля": land, "с": year, "по": 0})
    hold.marks.append({"год": year, "что": "вернулось",
                       "отчего": "печать не держала вечно"})
    title, text = texts.returned(rng, hold)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="dominion_return", title=title, text=text, importance=4,
        region_id=hold.seat_region, subjects=[hold.id])


# ---------------------------------------------------------------------------
# Имя
# ---------------------------------------------------------------------------

def _name_for(world, rng, kind, region, pick: dict) -> str:
    """Имя владению дают люди снаружи, и оно описательное.

    Своих земель чудовища обычно никак не зовут: имя нужно тем, кто
    живёт за межой и должен как-то называть то место, куда не ходят.
    Поэтому имя тут — либо примета («Пепельное Царство»), либо место
    («Удел Семи Холмов»), а не имя хозяина: его за межой чаще всего не
    знают.

    Имя целиком стоит в именительном падеже; склонение внутри самого
    имени («Семи Холмов») — часть имени, а не падеж в тексте.
    """
    taken = {item.name for item in world.dominions.values()}
    words = list(cat.NAME_WORDS.get(kind.key, (("Владение", "n"),)))
    for _try in range(12):
        word, gender = rng.choice(words)
        if rng.chance(0.4):
            name = "%s %s" % (word, rng.choice(list(cat.NAME_TAILS)))
        else:
            forms, _why = rng.choice(list(cat.NAME_ADJ))
            name = "%s %s" % (cat.adjective(forms, gender), word)
        if name not in taken:
            return name
    return name


# ---------------------------------------------------------------------------
# Спросить у мира
# ---------------------------------------------------------------------------

def at_region(world, region_id: str, year: int = 0):
    """Кто на деле держал эту землю в таком-то году.

    Спрашивается со страницы места и с карты. Отвечается по записи
    владений, а не по нынешнему списку земель: владение расходится и
    усыхает, и «он держал это место» верно не на всю его жизнь.
    """
    for hold in sorted(world.dominions.values(), key=lambda item: item.id):
        for row in hold.held:
            if row.get("земля") != region_id:
                continue
            began = int(row.get("с", 0))
            over = int(row.get("по", 0))
            if year and began > year:
                continue
            if year and over and over < year:
                continue
            if not year and over:
                continue
            return hold
    return None
