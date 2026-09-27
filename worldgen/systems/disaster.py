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
# Ответ державы
# ---------------------------------------------------------------------------
# Беда сама по себе редко кончает державу. Её кончают решения: хлеб
# забрали в столицу, подать подняли в голодный год, виноватых нашли и
# казнили. И наоборот: открытые зернохранилища и выведенные из-под удара
# люди — это разница между «тяжёлым годом» и «годом, после которого
# держава не встала».

RESPONSE_MAX = 3            # сколько решений успевает принять одна держава
RESPONSE_CHANCE = 0.75      # и как часто власть вообще что-то делает


def _can(world, polity, need: str) -> bool:
    """Есть ли у державы то, без чего решение неисполнимо."""
    if not need:
        return True
    if need == "казна":
        return len(polity.settlement_ids) >= 2
    if need == "хлеб":
        return polity.hunger < 0.55 and bool(polity.surpluses)
    if need == "войско":
        return len(polity.settlement_ids) >= 1 and polity.weariness < 0.85
    if need == "жрецы":
        return bool(polity.faith_id)
    if need == "чародеи":
        return bool(polity.known)
    if need == "сосед":
        return any(value > 0.1 for value in (polity.relations or {}).values())
    return True


def _weigh_response(world, polity, ruler, item, spec) -> float:
    """Насколько это решение похоже на то, что примет этот государь."""
    weight = item.weight
    traits = set()
    reign = world.current_reign(polity)
    if reign is not None:
        traits |= set(reign.traits or ())
    if ruler is not None:
        traits |= set(ruler.traits or ())
    hits = len(traits & set(item.wants))
    weight *= 1.0 + 1.6 * hits
    skills = (reign.skills if reign is not None else None) or {}
    if item.works or item.key in ("насыпать амбары", "объявить карантин"):
        weight *= 0.6 + 0.12 * float(skills.get("правление", 5))
    if item.key == "послать войско":
        weight *= 0.6 + 0.12 * float(skills.get("война", 5))
    if item.needs == "жрецы":
        weight *= 0.6 + 0.12 * float(skills.get("вера", 5))
    if item.mistake:
        # Дурное решение принимают не потому, что оно дурное, а потому что
        # оно проще. Но умный государь так делает реже.
        weight *= 1.4 - 0.08 * float(skills.get("правление", 5))
    if polity.hunger > 0.4 and item.key in ("открыть зернохранилища",
                                            "изъять хлеб силой",
                                            "просить помощи"):
        weight *= 1.8
    return max(0.05, weight)


def _outcome(rng, world, polity, ruler, item) -> str:
    """Чем кончилось решение: помогло, поздно, не вышло, сделало хуже."""
    reign = world.current_reign(polity)
    skills = (reign.skills if reign is not None else None) or {}
    skill = float(skills.get("правление", 5))
    # Решение помогает не потому, что оно доброе, а потому, что его сумели
    # исполнить: у государя с умением правления пятёркой выходит едва
    # половина того, что он велел.
    good = 0.2 + 0.042 * skill
    if item.toll < 1.0:
        good += 0.07
    roll = rng.random()
    if roll < good:
        return dis.DONE_HELPED
    if roll < good + 0.26:
        return dis.DONE_LATE
    if roll < good + 0.52:
        return dis.DONE_FAILED
    return dis.DONE_WORSE


def _unrest(world, polity, item, outcome: str) -> None:
    """Недовольство от решения: голод в державе и злоба знати."""
    unrest = item.unrest
    if outcome == dis.DONE_WORSE:
        unrest += 0.15
    elif outcome == dis.DONE_HELPED:
        unrest -= 0.05
    if not unrest:
        return
    if item.key in ("изъять хлеб силой", "поднять подать"):
        polity.hunger = max(0.0, min(1.0, polity.hunger + unrest * 0.45))
    houses = [item_ for item_ in world.houses_of_polity(polity)
              if item_.status == ACTIVE and item_.id != polity.house_id]
    for house in houses[:2]:
        house.discontent = max(0.0, min(1.0, house.discontent + unrest * 0.5))


def respond(ctx, calamity, spec, plan, rng, year: int) -> None:
    """Что решили в столицах тех держав, по которым идёт беда."""
    world = ctx.world
    if len(calamity.responses) >= RESPONSE_MAX:
        return
    options = dis.responses_for(spec.kind)
    if not options:
        return

    for polity_id in calamity.polity_ids[:3]:
        polity = world.polities.get(polity_id)
        if polity is None or polity.status != ACTIVE:
            continue
        if len(calamity.responses) >= RESPONSE_MAX:
            return
        if not rng.chance(RESPONSE_CHANCE):
            continue
        taken = {row["решение"] for row in calamity.responses
                 if row.get("держава") == polity.id}
        ruler = world.figures.get(polity.ruler_id)
        pairs = [(item, _weigh_response(world, polity, ruler, item, spec))
                 for item in options
                 if item.key not in taken and _can(world, polity, item.needs)]
        if not pairs:
            continue
        item = rng.weighted(pairs)
        outcome = _outcome(rng, world, polity, ruler, item)

        # Решение двигает живую силу беды: спасает, не помогает или губит.
        shift = item.toll
        if outcome == dis.DONE_LATE:
            shift = 1.0 + (item.toll - 1.0) * 0.4
        elif outcome == dis.DONE_FAILED:
            shift = 1.0
        elif outcome == dis.DONE_WORSE:
            shift = max(1.0, 2.0 - item.toll) * 1.1
        saved = 0.0
        if shift < 1.0:
            saved = 1.0 - shift
        calamity.force = max(0.5, min(1.6, calamity.force * shift))
        _unrest(world, polity, item, outcome)

        if item.works and outcome in (dis.DONE_HELPED, dis.DONE_LATE):
            for region_id in calamity.region_ids:
                region = world.regions.get(region_id)
                if region is None or region_id not in polity.region_ids:
                    continue
                build_works(ctx, region, item.works, year, calamity)

        row = {"год": int(year), "держава": polity.id, "решение": item.key,
               "итог": outcome, "кто": ruler.id if ruler is not None else ""}
        calamity.responses.append(row)
        if outcome == dis.DONE_WORSE and item.mistake:
            calamity.mistakes.append({"год": int(year), "держава": polity.id,
                                      "что": item.key})
        if saved:
            calamity.would_take = int(calamity.would_take + saved * 100)

        # Не всякое решение — событие летописи: их и так много. Но
        # ошибка управления и спасение людей — события.
        loud = (outcome == dis.DONE_WORSE and item.mistake) or \
            (outcome == dis.DONE_HELPED and item.toll <= 0.78)
        if loud or calamity.severity >= 4:
            title, text = texts.response(rng, calamity, polity, ruler, item,
                                         outcome)
            world.add_event(
                date=ctx.date_in(rng, year),
                era_index=world.era_index_at(year), kind="calamity_answer",
                title=title, text=text,
                importance=3 if loud else 2,
                actors=[ruler.id] if ruler is not None else [],
                subjects=[calamity.id, polity.id],
                region_id=calamity.region_ids[0] if calamity.region_ids else "")


# ---------------------------------------------------------------------------
# Кто нажился и кто в этом был кем
# ---------------------------------------------------------------------------

def count_gains(ctx, calamity, rng) -> None:
    """У всякой беды есть те, кому она оказалась выгодна.

    Это не злодеи: довезти хлеб в голодный край — это риск, и цена у
    риска своя. Но история должна помнить и их, иначе выходит, что беда
    только отнимает.
    """
    if calamity.severity < 2:
        return
    count = 1 if calamity.severity < 4 else rng.randint(1, 3)
    seen = set()
    for _ in range(count):
        gain = rng.choice(dis.GAINS)
        if gain in seen:
            continue
        seen.add(gain)
        calamity.gains.append(gain)


def name_actors(ctx, calamity, spec, rng, year: int) -> None:
    """Люди беды: не только герои.

    У беды есть лекарь, который лечил, пока было чем; книжник, который
    первым понял и которому не поверили; предатель, открывший то, что
    надо было держать закрытым; и случайный спаситель, сделавший
    очевидное. Часть этих людей уже есть в мире, часть появляется здесь —
    и дальше живёт своей жизнью.
    """
    world = ctx.world
    if calamity.severity < 2:
        return
    count = min(4, 1 + calamity.severity // 2)
    roles = [key for key, _ in dis.ACTORS]
    used = set()
    races = []
    for polity_id in calamity.polity_ids:
        polity = world.polities.get(polity_id)
        if polity is not None:
            races.append(polity.race_id)
    if not races:
        for settlement_id in world.active_settlements:
            settlement = world.settlements[settlement_id]
            if settlement.region_id in calamity.region_ids:
                races.append(settlement.race_id)
                break
    if not races:
        return

    from .. import races as races_mod
    for _ in range(count):
        role = rng.choice(roles)
        if role in used:
            continue
        used.add(role)
        figure = None
        if role == "государь" and calamity.polity_ids:
            polity = world.polities.get(calamity.polity_ids[0])
            figure = world.figures.get(polity.ruler_id) if polity else None
        elif role == "воевода" and calamity.commander_ids:
            figure = world.figures.get(calamity.commander_ids[0])
        if figure is None:
            race = races_mod.get_race(rng.choice(sorted(set(races))))
            sex = "f" if rng.chance(0.42) else "m"
            figure = ctx.make_figure(
                rng, race, year, role=role,
                region_id=rng.choice(calamity.region_ids)
                if calamity.region_ids else "",
                title=role, sex=sex, epithet_chance=0.35)
        if role not in figure.roles:
            figure.roles.append(role)
        calamity.actors.append({"роль": role, "кто": figure.id,
                                "что": dis.ACTORS_BY_KEY.get(role, "")})


# ---------------------------------------------------------------------------
# Цепи: беда, выросшая из беды
# ---------------------------------------------------------------------------
# Не «засуха вызвала чуму, потому что так вышло», а: колодцы пересохли,
# люди сбились у последней воды, болезнь пошла по рукам. Через что одно
# стало другим — записано у каждой связи.

CHAIN_MAX = 2               # сколько бед может вырасти из одной
CHAIN_BUSY = 5              # и не плодим их, когда в мире и так тесно


def plan_chain(ctx, calamity, spec, rng, year: int) -> None:
    """Что вырастет из этой беды и через что именно."""
    links = dis.CHAINS_BY_PARENT.get(spec.key, ())
    if not links or calamity.severity < 2:
        return
    world = ctx.world
    if len(world.active_calamities) >= CHAIN_BUSY:
        return
    queue = getattr(ctx, "disaster_chains", None)
    if queue is None:
        queue = ctx.disaster_chains = []

    born = 0
    for link in links:
        if born >= CHAIN_MAX:
            break
        child_spec = cat.CATALOG_BY_KEY.get(link.child)
        if child_spec is None:
            continue
        weight = link.chance * (0.35 + 0.15 * calamity.severity)
        if not rng.chance(min(0.85, weight)):
            continue
        # Дитя слабее родителя: цепь затухает, иначе одна засуха кончает мир.
        want = max(1, calamity.severity - 1)
        levels = [level for level, _ in child_spec.severities]
        severity = min(levels, key=lambda level: (abs(level - want), level))
        regions = list(calamity.region_ids[:2]) or list(calamity.region_ids)
        queue.append({
            "год": year + rng.randint(*link.delay),
            "ключ": link.child, "родитель": calamity.id,
            "через": link.factor, "земли": regions, "тяжесть": severity,
        })
        born += 1


def tick_chains(ctx, year: int) -> None:
    """Беды, которым пришёл срок вырасти из прежних."""
    queue = getattr(ctx, "disaster_chains", None)
    if not queue:
        return
    world = ctx.world
    from . import calamity as calamity_system

    for item in list(queue):
        if item["год"] > year:
            continue
        queue.remove(item)
        spec = cat.CATALOG_BY_KEY.get(item["ключ"])
        parent = world.calamities.get(item["родитель"])
        if spec is None or parent is None:
            continue
        if len(world.active_calamities) >= CHAIN_BUSY:
            continue
        rng = ctx.rng("disaster", "chain", year, item["ключ"])
        child = calamity_system.start_chained(
            ctx, year, spec, rng, severity=item["тяжесть"],
            region_ids=item["земли"], parent=parent, factor=item["через"])
        if child is not None:
            child.notes.append("выросло из беды «%s»: %s"
                               % (parent.name, item["через"]))


# ---------------------------------------------------------------------------
# Счёт ущерба и четыре исхода
# ---------------------------------------------------------------------------

def count_damage(ctx, calamity, spec) -> dict:
    """Ущерб по видам, каждый 0…1.

    «Погибло десять сотых» — только одна мера, и не главная. Беда,
    унёсшая два процента людей и всю письменность, для истории страшнее.
    """
    world = ctx.world
    souls = 0
    for region_id in calamity.region_ids:
        souls += _souls_in(world, region_id)
    souls = max(1, souls + calamity.deaths)
    damage = {}
    damage[dis.D_SOULS] = min(1.0, calamity.deaths / float(souls))
    towns = max(1, sum(1 for sid in world.active_settlements
                       if world.settlements[sid].region_id
                       in calamity.region_ids) + calamity.settlements_lost)
    damage[dis.D_WEALTH] = min(1.0, calamity.settlements_lost / float(towns)
                               + 0.1 * len(calamity.mistakes))
    damage[dis.D_LAND] = min(1.0, 0.2 * len(calamity.scar_ids)
                             + (0.5 if spec.key in ("drowning", "sundering")
                                else 0.0))
    power = 0.25 * calamity.polities_lost + 0.15 * len(calamity.mistakes)
    if calamity.kind == cat.POLITICAL:
        power += 0.25
    damage[dis.D_POWER] = min(1.0, power)
    damage[dis.D_LORE] = min(1.0, 0.3 * len(calamity.lore_ids))
    damage[dis.D_HOST] = min(1.0, 0.12 * len(calamity.battle_ids))
    faith = 0.0
    if calamity.kind == cat.RELIGIOUS:
        faith = 0.5
    elif calamity.cause in ("гнев божества", "спор богов", "сорванный обряд"):
        faith = 0.3
    damage[dis.D_FAITH] = faith
    damage[dis.D_CUSTOM] = min(1.0, 0.1 * len(calamity.responses)
                               + 0.2 * len(calamity.gains) / 3.0)
    calamity.damage = {key: round(value, 3) for key, value in damage.items()
                       if value > 0.01}
    return calamity.damage


def _souls_in(world, region_id: str) -> int:
    total = 0
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id == region_id:
            total += world.settlement_realm(settlement)
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        if tribe.region_id == region_id:
            total += tribe.population
    return total


PHYS_BY_RESOLUTION = {
    "sealed": dis.PHYS_SEALED,
    "faded": dis.PHYS_LEFT,
    "driven_back": dis.PHYS_LEFT,
    "burned_out": dis.PHYS_LEFT,
    "tribute": dis.PHYS_STAYS,
    "adapted": dis.PHYS_STAYS,
    "absorbed": dis.PHYS_STAYS,
    "endured": dis.PHYS_GONE,
    "rains": dis.PHYS_GONE,
    "hero": dis.PHYS_GONE,
    "heroes": dis.PHYS_GONE,
    "coalition": dis.PHYS_GONE,
    "dispersed": dis.PHYS_GONE,
    "suppressed": dis.PHYS_GONE,
    "reunited": dis.PHYS_GONE,
    "shattered": dis.PHYS_STAYS,
}


def four_outcomes(ctx, calamity, spec, plan, rng) -> dict:
    """Четыре исхода вместо одного.

    «Демоны изгнаны» — это только телесный исход. Держава при этом могла
    рассыпаться, народ уйти, а летопись запомнить всё победой. Один
    исход больше не описывает беду целиком.
    """
    damage = calamity.damage or {}
    resolution = plan.get("resolution", "endured")

    phys = PHYS_BY_RESOLUTION.get(resolution, dis.PHYS_GONE)
    if spec.kind == cat.CLIMATE and phys == dis.PHYS_GONE:
        phys = dis.PHYS_LEFT

    if calamity.polities_lost:
        pol = dis.POL_SPLIT
    elif damage.get(dis.D_POWER, 0.0) >= 0.4 or calamity.mistakes:
        pol = dis.POL_WEAK
    elif calamity.gains and rng.chance(0.4):
        pol = dis.POL_GAINED
    elif resolution in ("shattered", "absorbed"):
        pol = dis.POL_NEW
    else:
        pol = dis.POL_HELD

    souls = damage.get(dis.D_SOULS, 0.0)
    if souls >= 0.3:
        man = dis.MAN_BLED
    elif resolution == "adapted" or spec.kind == cat.CLIMATE:
        man = dis.MAN_CHANGED
    elif calamity.settlements_lost >= 2:
        man = dis.MAN_MOVED
    elif any(row.get("итог") == dis.DONE_HELPED
             for row in calamity.responses):
        man = dis.MAN_SAVED
    else:
        man = dis.MAN_CHANGED

    if calamity.depth >= 4 or pol == dis.POL_SPLIT:
        hist = dis.HIST_DOOM
    elif phys == dis.PHYS_GONE and pol in (dis.POL_WEAK, dis.POL_NEW):
        hist = dis.HIST_PYRRHIC
    elif phys == dis.PHYS_SEALED and not calamity.cause_known:
        hist = dis.HIST_FALSE
    elif not calamity.cause_known and rng.chance(0.5):
        hist = dis.HIST_DISPUTED
    elif calamity.severity <= 2 and not calamity.scar_ids:
        hist = dis.HIST_FORGOTTEN
    else:
        hist = dis.HIST_VICTORY

    calamity.outcome = {"телесный": phys, "державный": pol,
                        "людской": man, "исторический": hist}
    return calamity.outcome


def dark_pressure_of(calamity) -> float:
    """Давление на тёмные века: не тяжесть, а то, что именно сломалось.

    Землетрясение, унёсшее пятую часть людей при целой державе, тёмных
    веков не даёт. Малый бунт, убивший род государя и растащивший
    державу по частям, — даёт.
    """
    damage = calamity.damage or {}
    pressure = (1.1 * damage.get(dis.D_SOULS, 0.0)
                + 0.9 * damage.get(dis.D_POWER, 0.0)
                + 0.7 * damage.get(dis.D_WEALTH, 0.0)
                + 0.8 * damage.get(dis.D_LORE, 0.0)
                + 0.4 * damage.get(dis.D_LAND, 0.0)
                + 0.3 * damage.get(dis.D_CUSTOM, 0.0))
    pressure += 0.08 * calamity.severity
    if calamity.polities_lost:
        pressure += 0.15 * min(3, calamity.polities_lost)
    return max(0.0, min(2.0, pressure))


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
           "force_now", "respond", "count_gains", "name_actors",
           "plan_chain", "tick_chains", "count_damage", "four_outcomes",
           "dark_pressure_of", "PROFILE_KEYS"]
