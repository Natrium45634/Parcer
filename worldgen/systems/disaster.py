# -*- coding: utf-8 -*-
"""Живая катастрофа: причина, предвестники, фазы, уязвимость земель.

Надстройка над `systems/calamity`. Тот ведёт беду как объект: тяжесть,
охват, срок, урон. Этот отвечает за то, из чего получается история:

* **склад мира** — не два бича, а девять мер: недра, небо, чары, боги,
  древнее, власть, зараза, звери, лёд. Из них берутся веса причин;
* **уязвимость земли** — одна и та же беда в двух землях идёт по-разному.
  Земля, поставившая дамбы, теряет вдвое меньше; земля, забывшая, зачем
  их чинить, — вдвое больше. Отсюда историческая петля: беда → дело →
  забвение → та же беда, но хуже;
* **причина и триггер** — причина тянется веками (шахты ослабляли гору
  триста лет), триггер длится один день (гильдия повела новую штольню);
* **предвестники** — беда зреет на глазах, и её читают: верно, неверно
  или не читают вовсе. Прочитанная вовремя беда может быть предотвращена
  или ослаблена, и это отдельная запись летописи;
* **фазы и живая сила** — беда не бьёт ровно весь срок: первый удар,
  самое худшее, привыкание, отступление. Переломы сдвигают силу.
"""

from __future__ import annotations

from .. import catastrophe as cat
from .. import disaster as dis
from .. import narrative_disaster as texts
from ..models import ACTIVE

# Сколько бед приходит с предвестниками, а не внезапно. Внезапные тоже
# нужны: землетрясение не предупреждает, а мор идёт с торгом неделями.
OMEN_SHARE = 0.55
OMEN_LEAD = (2, 6)          # за сколько лет до беды видны знаки
OMEN_COUNT = (1, 3)

# Как читают знаки. Верное чтение — не подарок: нужен тот, кто умеет.
READ_RIGHT_BASE = 0.3
READ_NONE_BASE = 0.35

# Предотвращение. Полностью беду отводят редко — и это должно быть
# редко, иначе мир перестаёт быть опасным.
STOP_FULL_CHANCE = 0.16
STOP_PART_CHANCE = 0.45
STOP_TOLL = 0.55            # во сколько раз меньше берёт ослабленная беда

# Переломы: сколько их бывает и насколько они двигают силу беды.
TURN_CHANCE = 0.45
TURN_MAX = 3


# ---------------------------------------------------------------------------
# Склад мира: из чего берутся причины
# ---------------------------------------------------------------------------

PROFILE_KEYS = ("недра", "небо", "чары", "боги", "древнее", "власть",
                "зараза", "звери", "лёд")


def prepare(ctx) -> None:
    """Склад этого мира: чем он опасен и почему.

    Нрав мира (`systems/calamity.prepare`) говорит, какие беды случаются
    чаще. Склад говорит другое — какие **причины** в этом мире вообще
    работают: в мире с живой магией беды чаще магические по своей
    природе, в мире с древними логовами — чаще из-под земли. Карта, если
    она есть, знает об этом больше, чем жребий.
    """
    rng = ctx.rng("disaster", "profile")
    profile = {key: rng.uniform(0.4, 1.6) for key in PROFILE_KEYS}

    world = ctx.world
    if ctx.map is not None:
        # Карта уже решила, где дрожит земля, где сильна магия и сколько
        # в мире спящих логовищ. Незачем бросать это второй раз.
        quake = 0.0
        magic = 0.0
        for region in world.regions.values():
            quake += float(region.risk or 0.0)
            magic += abs(float(region.magic or 0.0))
        count = max(1, len(world.regions))
        profile["недра"] *= 0.6 + 1.6 * min(1.5, quake / count)
        profile["чары"] *= 0.6 + 1.6 * min(1.5, magic / count)
        lairs = len(getattr(ctx, "lair_of_relic", ()) or ())
        profile["древнее"] *= 0.7 + 0.25 * min(6, lairs)

    ctx.disaster_profile = profile
    ctx.disaster_pending = []
    world.notes["склад мира"] = sorted(profile, key=lambda key: -profile[key])[:4]


def _profile(ctx, key: str) -> float:
    profile = getattr(ctx, "disaster_profile", None) or {}
    return float(profile.get(key, 1.0))


# ---------------------------------------------------------------------------
# Уязвимость земли
# ---------------------------------------------------------------------------

def vuln_of(world, region_id: str, kind: str) -> float:
    """Насколько эта земля не готова к беде такого рода, 0…1."""
    region = world.regions.get(region_id)
    if region is None:
        return dis.VULN_START
    if kind not in region.vulnerability:
        region.vulnerability[kind] = dis.VULN_START
    return max(0.0, min(1.0, float(region.vulnerability[kind])))


def vuln_kind(spec) -> str:
    """Какая уязвимость важна для этой беды."""
    return dis.VULNERABLE_BY_KEY.get(spec.key, dis.V_ORDER)


def vuln_factor(world, calamity, spec) -> float:
    """Во сколько раз земли усиливают или ослабляют беду.

    Считается по всем затронутым землям сразу: беда идёт по тем, что
    есть, и готовность у них разная.
    """
    kind = vuln_kind(spec)
    values = [vuln_of(world, region_id, kind)
              for region_id in calamity.region_ids]
    if not values:
        return 1.0
    share = sum(values) / float(len(values))
    return dis.VULN_LOW + (dis.VULN_HIGH - dis.VULN_LOW) * share


def hurt_lands(world, calamity, spec, share: float = 1.0) -> None:
    """Беда оставляет землю слабее, чем нашла: следующая ляжет тяжелее."""
    kind = vuln_kind(spec)
    step = dis.VULN_SCAR * share * (0.5 + 0.25 * calamity.severity)
    for region_id in calamity.region_ids:
        region = world.regions.get(region_id)
        if region is None:
            continue
        was = vuln_of(world, region_id, kind)
        region.vulnerability[kind] = min(1.0, was + step)


def build_works(ctx, region, work: str, year: int, calamity=None) -> None:
    """Дело людей: дамба, амбар, стена, карантинный двор.

    Это и есть память земли: она держится веками и сбивает уязвимость,
    пока её чинят. Забвение поднимет её обратно (см. `forget`).
    """
    kind = dis.WORKS.get(work)
    if kind is None or region is None:
        return
    was = vuln_of(ctx.world, region.id, kind)
    region.vulnerability[kind] = max(0.0, was - dis.VULN_LEARN)
    region.works.append({"что": work, "год": int(year),
                         "беда": calamity.name if calamity is not None else ""})


def forget(ctx, year: int, period: int) -> None:
    """Время тянет землю к середине — и это работает в обе стороны.

    Дамбы не чинят, амбары стоят пустыми, устав о деревянных крышах никто
    не читал двести лет: выученное забывается, и следующая такая же беда
    выходит страшнее. Но и разорённая земля не остаётся разорённой навек:
    её отстраивают, и через век-полтора она такая же, как все.
    """
    world = ctx.world
    drift = dis.VULN_FORGET * max(1, period)
    middle = dis.VULN_START
    for region in world.regions.values():
        if not region.vulnerability:
            continue
        for kind, value in list(region.vulnerability.items()):
            if abs(value - middle) <= drift:
                region.vulnerability[kind] = middle
            elif value < middle:
                region.vulnerability[kind] = value + drift
            else:
                region.vulnerability[kind] = value - drift


# ---------------------------------------------------------------------------
# Причина и триггер
# ---------------------------------------------------------------------------

def _world_has(world, need: str) -> bool:
    """Есть ли в мире то, без чего причина невозможна."""
    if not need:
        return True
    if need == "гильдия":
        return any(item.status == ACTIVE for item in world.guilds.values())
    if need == "чародеи":
        return any(item.status == ACTIVE for item in world.guilds.values()) \
            or bool(world.discoveries)
    if need == "храм":
        return bool(world.temples) or bool(world.faiths)
    if need == "след":
        return bool(world.relics)
    if need == "война":
        return bool(world.wars)
    if need == "беда":
        return any(item.end is not None for item in world.calamities.values())
    if need == "торг":
        return bool(world.routes)
    if need == "держава":
        return bool(world.active_polities)
    return True


def choose_cause(ctx, spec, rng, year: int, parent=None) -> dict:
    """Почему это случилось — и что спустило беду именно в этот год.

    У беды, выросшей из другой беды, причина известна заранее: её
    ослабила прежняя. У всех прочих причина берётся по складу мира и по
    тому, что в мире вообще есть: без гильдий никто не углубит шахту,
    без храмов никто не отслужит забытый обряд.
    """
    world = ctx.world
    pairs = []
    for cause in dis.CAUSES:
        if spec.kind not in cause.families:
            continue
        if not _world_has(world, cause.needs):
            continue
        weight = cause.weight
        if cause.profile:
            weight *= _profile(ctx, cause.profile)
        if parent is not None and cause.key == "ослабленная земля":
            weight *= 6.0
        pairs.append((cause, weight))
    if not pairs:
        cause = dis.CAUSES_BY_KEY[dis.UNKNOWN_CAUSE]
    else:
        cause = rng.weighted(pairs)

    # Причина может тянуться веками: шахты ослабляли гору задолго до того,
    # как она рухнула.
    span = {"чрезмерная добыча": (80, 400), "сведённый лес": (40, 200),
            "ослабленная земля": (20, 300), "распечатанное древнее": (200, 2000),
            "долгая вражда": (30, 200), "недра": (0, 0),
            "небесный ход": (0, 0)}.get(cause.key, (0, 60))
    cause_year = year
    if span[1] > 0:
        cause_year = max(1, year - rng.randint(span[0], span[1]))

    # Скрытая правда: известная причина не всегда настоящая. Людскую вину
    # скрывают чаще прочего — её есть кому скрывать.
    hidden = ""
    known = True
    if cause.human and rng.chance(0.35):
        known = False
    elif rng.chance(0.12):
        known = False
    if not known:
        options = [item for item in dis.CAUSES
                   if item.hidden and item.key != cause.key
                   and spec.kind in item.families
                   and _world_has(world, item.needs)]
        if options:
            hidden = rng.choice(sorted(options, key=lambda item: item.key)).key
        else:
            known = True

    triggers = [item for item in dis.TRIGGERS
                if cause.key in item.causes and _world_has(world, item.needs)]
    trigger = ""
    if triggers:
        trigger = rng.weighted([(item, item.weight) for item in triggers]).key

    return {"причина": cause.key, "скрытая": hidden, "известна": known,
            "год причины": cause_year, "спуск": trigger}


# ---------------------------------------------------------------------------
# Предвестники и предотвращение
# ---------------------------------------------------------------------------

def want_omens(ctx, spec, rng) -> bool:
    """Придёт ли беда с предвестниками или разом.

    Внезапность — свойство беды: землетрясение не предупреждает, а
    ледник виден за десятки лет.
    """
    if spec.kind == cat.CLIMATE:
        return True
    if spec.key in ("earthquake", "eruption", "wildfire", "sundering"):
        return rng.chance(0.3)
    return rng.chance(OMEN_SHARE)


def schedule(ctx, year: int, spec, rng, severity: int, region_ids) -> None:
    """Кладёт беду в зреющие: со знаками и годом, когда она придёт."""
    omens = dis.omens_for(spec)
    if not omens:
        return
    lead = rng.randint(*OMEN_LEAD)
    count = min(len(omens), rng.randint(*OMEN_COUNT))
    chosen = []
    seen = set()
    for _ in range(count):
        omen = rng.weighted([(item, item.weight) for item in omens])
        if omen.key in seen:
            continue
        seen.add(omen.key)
        chosen.append({"знак": omen.key,
                       "год": max(1, year + rng.randint(0, max(1, lead - 1))),
                       "прочтение": ""})
    if not chosen:
        return
    ctx.disaster_pending.append({
        "ключ": spec.key, "тяжесть": severity, "земли": list(region_ids),
        "год": year + lead, "знаки": chosen, "читали": "",
        "отведено": "",
    })


def _readers(ctx, region_ids) -> tuple:
    """Кто в этих землях может прочесть знак: книжники и жрецы.

    Возвращает (сколько умеющих, есть ли кому распоряжаться).
    """
    world = ctx.world
    lettered = 0
    power = False
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        touched = False
        for settlement_id in polity.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is not None and settlement.region_id in region_ids:
                touched = True
                break
        if not touched:
            continue
        power = True
        lettered += 1 + len(polity.known or ()) // 6
        if polity.faith_id:
            lettered += 1
    lettered += min(4, len(world.codices) // 8)
    return lettered, power


def _read(ctx, rng, region_ids) -> str:
    """Как прочли знак: верно, неверно или не поняли вовсе."""
    lettered, power = _readers(ctx, region_ids)
    right = READ_RIGHT_BASE + 0.06 * min(6, lettered)
    none = max(0.05, READ_NONE_BASE - 0.05 * min(5, lettered))
    if not power:
        right *= 0.5
        none += 0.2
    roll = rng.random()
    if roll < right:
        return dis.READ_RIGHT
    if roll < right + none:
        return dis.READ_NONE
    return dis.READ_WRONG


def tick_pending(ctx, year: int) -> None:
    """Зреющие беды: знаки, чтение знаков и то, что из этого вышло."""
    pending = getattr(ctx, "disaster_pending", None)
    if not pending:
        return
    world = ctx.world
    from . import calamity as calamity_system

    for item in list(pending):
        spec = cat.CATALOG_BY_KEY.get(item["ключ"])
        if spec is None:
            pending.remove(item)
            continue
        rng = ctx.rng("disaster", item["ключ"], year)

        # 1. Знаки этого года: их видят и толкуют.
        for sign in item["знаки"]:
            if sign["прочтение"] or sign["год"] != year:
                continue
            omen = dis.OMENS_BY_KEY.get(sign["знак"])
            if omen is None:
                sign["прочтение"] = dis.READ_NONE
                continue
            reading = _read(ctx, rng, item["земли"])
            sign["прочтение"] = reading
            title, text = texts.omen(rng, omen, reading, world, item["земли"])
            world.add_event(
                date=ctx.date_in(rng, year),
                era_index=world.era_index_at(year), kind="omen",
                title=title, text=text,
                importance=3 if reading == dis.READ_RIGHT else 2,
                region_id=item["земли"][0] if item["земли"] else "")

        if year < item["год"]:
            continue

        # 2. Срок пришёл. Если знак прочли верно, у мира был год-другой на
        #    приготовления — и беда может не случиться вовсе.
        pending.remove(item)
        right = any(sign["прочтение"] == dis.READ_RIGHT
                    for sign in item["знаки"])
        stopped = dis.STOP_NONE
        if right:
            lettered, power = _readers(ctx, item["земли"])
            luck = 0.05 * min(6, lettered) + (0.1 if power else 0.0)
            if rng.chance(STOP_FULL_CHANCE + luck):
                stopped = dis.STOP_FULL
            elif rng.chance(STOP_PART_CHANCE + luck):
                stopped = dis.STOP_PART

        if stopped == dis.STOP_FULL:
            way, about = rng.choice(dis.STOP_WAYS)
            title, text = texts.prevented(rng, spec, way, about, world,
                                          item["земли"])
            world.add_event(
                date=ctx.date_in(rng, year),
                era_index=world.era_index_at(year), kind="calamity_stopped",
                title=title, text=text, importance=4,
                region_id=item["земли"][0] if item["земли"] else "")
            continue

        calamity = calamity_system.start_scheduled(
            ctx, year, spec, rng, severity=item["тяжесть"],
            region_ids=item["земли"], omens=item["знаки"], prevented=stopped)
        if calamity is None:
            continue
        if stopped == dis.STOP_PART:
            way, about = rng.choice(dis.STOP_WAYS)
            calamity.notes.append("ослаблена заранее: %s" % about)


# ---------------------------------------------------------------------------
# Фазы и живая сила
# ---------------------------------------------------------------------------

def phase_at(spec, plan, calamity, year: int) -> tuple:
    """Какая фаза беды идёт в этом году и во сколько раз она сильнее.

    Фазы делят срок беды в своих долях, и у каждой своя сила. Поэтому
    двадцатилетняя беда не размазана ровно: сперва удар, потом худшее,
    потом годы, когда живут как-нибудь.
    """
    phases = dis.phases_for(spec.kind)
    duration = max(1, int(plan.get("duration", 1)))
    passed = max(0, year - calamity.start.year)
    share = min(0.999, passed / float(duration))
    edge = 0.0
    for phase in phases:
        edge += phase.share
        if share < edge:
            return phase, phase.force
    last = phases[-1]
    return last, last.force


def note_phase(world, calamity, phase, year: int, force: float) -> bool:
    """Отмечает смену фазы. Возвращает True, если фаза сменилась."""
    if calamity.phase == phase.key:
        return False
    if calamity.phase_log:
        calamity.phase_log[-1]["по"] = int(year)
    calamity.phase = phase.key
    calamity.phase_log.append({"фаза": phase.key, "с": int(year),
                               "по": 0, "сила": round(force, 2)})
    return True


def maybe_turn(ctx, calamity, spec, plan, rng, year: int) -> None:
    """Перелом: событие, после которого беда идёт иначе.

    Перелом не украшение: он двигает живую силу беды. Пала крепость —
    стало хуже; пришла помощь соседей — стало легче; нашли, чем с этим
    бороться, — легче надолго.
    """
    if len(calamity.turns) >= TURN_MAX:
        return
    if not rng.chance(TURN_CHANCE):
        return
    what, shift = rng.choice(dis.TURNS)
    if any(item.get("что") == what for item in calamity.turns):
        return
    calamity.force = max(0.5, min(1.6, calamity.force * (1.0 + shift)))
    calamity.force_peak = max(calamity.force_peak, calamity.force)
    calamity.turns.append({"год": int(year), "что": what,
                           "сдвиг": round(shift, 2)})
    world = ctx.world
    title, text = texts.turn_point(rng, calamity, what, shift, world)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="calamity_turn", title=title, text=text,
        importance=3 if abs(shift) >= 0.25 else 2,
        subjects=[calamity.id],
        region_id=calamity.region_ids[0] if calamity.region_ids else "")


def force_now(world, calamity, spec, plan, year: int) -> float:
    """Во сколько раз беда сильна прямо сейчас.

    Три множителя: фаза (перераспределяет урон по годам, а не добавляет
    его), живая сила беды (её двигают переломы и решения людей) и
    готовность земель. Фаза делится на среднюю силу своего семейства —
    иначе долгая беда с тяжёлой серединой брала бы больше положенного.
    """
    phase, base = phase_at(spec, plan, calamity, year)
    mean = dis.PHASE_MEAN.get(spec.kind, 1.0) or 1.0
    return (base / mean) * calamity.force * vuln_factor(world, calamity, spec)


__all__ = ["prepare", "vuln_of", "vuln_kind", "vuln_factor", "hurt_lands",
           "build_works", "forget", "choose_cause", "want_omens", "schedule",
           "tick_pending", "phase_at", "note_phase", "maybe_turn",
           "force_now", "PROFILE_KEYS"]
