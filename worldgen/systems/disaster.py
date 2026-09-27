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
from .. import history
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


# ---------------------------------------------------------------------------
# Шрамы мира: география, которая помнит
# ---------------------------------------------------------------------------
# Великое бедствие меняет карту само (`systems/upheaval`). Обычное
# оставляет вот это: новое русло, пепельную пустошь, пустой город. Шрам
# не запись в справочнике: его сперва обходят, потом обживают, потом
# объявляют святым местом, а потом забывают, зачем он свят.

SCAR_CHANCE = 0.5           # у средней беды остаётся видимый след
SCAR_MAX = 2
SCAR_RIPEN = 80             # до этого срока шрам ещё свежий
SCAR_TURN = 0.2             # и потом раз в десятилетие может перемениться
SCAR_HOLY_WINDOW = (80, 420)  # освящают рано или никогда
SCAR_SETTLED_AGE = 220      # обжитое место забывают через поколения
SCAR_FORGET_AGE = 400       # а нестрашное — только совсем старым


def leave_scars(ctx, calamity, spec, rng, year: int, date) -> None:
    """Что беда оставила на земле — на века или навсегда."""
    kinds = dis.scars_for(spec)
    if not kinds or not calamity.region_ids:
        return
    world = ctx.world

    # Малая беда следа не оставляет: её заравнивают за одно поколение.
    want = 0
    if calamity.severity >= 4:
        want = 2 if rng.chance(0.5) else 1
    elif calamity.severity >= 2 and rng.chance(SCAR_CHANCE):
        want = 1
    elif calamity.settlements_lost and rng.chance(0.4):
        want = 1
    if want <= 0:
        return
    want = min(SCAR_MAX, want)

    # Свой вид беды весит больше общего: выгоревший бор остаётся от пожара,
    # а братская могила — от всякой войны.
    pairs = [(item, 2.0 if spec.key in item.keys else 0.6) for item in kinds]
    taken = {scar.name for scar in world.scars.values()}
    made = 0
    for _ in range(want * 3):
        if made >= want:
            break
        kind = rng.weighted(pairs)
        region_id = rng.choice(calamity.region_ids)
        region = world.regions.get(region_id)
        if region is None or region.drowned:
            continue
        if any(scar.kind == kind.key for scar in world.scars_in(region_id)):
            continue
        name = _scar_name(world, kind, region, year)
        if not name or name in taken:
            continue
        taken.add(name)
        scar = world.add_scar(kind=kind.key, name=name, region_id=region_id,
                              calamity_id=calamity.id, created=date,
                              danger=kind.danger, boon=kind.boon)
        calamity.scar_ids.append(scar.id)
        made += 1
        title, text = texts.scar_left(rng, scar, kind, calamity, region)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="scar",
            title=title, text=text,
            importance=3 if kind.danger >= 2 else 2,
            subjects=[scar.id, calamity.id], region_id=region_id)


def _scar_name(world, kind, region, year: int) -> str:
    """«Пепельная пустошь Оркхад»: имя шрама — вид да земля.

    Имена собственные остаются в именительном падеже, как и везде; вид
    шрама идёт перед именем, а не согласуется с ним.
    """
    tail = region.name
    if kind.key == "пустой город":
        # Пустой город зовётся именем того города, который опустел.
        dead = [item for item in world.settlements.values()
                if item.region_id == region.id and item.ended is not None
                and 0 <= year - item.ended.year <= 40]
        if not dead:
            return ""
        tail = sorted(dead, key=lambda item: item.id)[-1].name
    return "%s %s" % (kind.noun[0], tail)


def age_scars(ctx, year: int, period: int) -> None:
    """Шрам живёт своей жизнью, и живёт он дольше тех, кто его помнит."""
    world = ctx.world
    for scar in list(world.scars.values()):
        # Земля может уйти под воду и после того, как на ней остался шрам:
        # тогда шрам уходит вместе с ней, и помнить его больше некому.
        region = world.regions.get(scar.region_id)
        if region is None or region.drowned:
            if scar.state != dis.SCAR_FORGOTTEN:
                scar.state = dis.SCAR_FORGOTTEN
                scar.notes.append("%d: ушёл под воду вместе с землёй" % year)
            continue
        if scar.state == dis.SCAR_FORGOTTEN:
            continue
        age = year - scar.created.year
        if age < SCAR_RIPEN:
            continue
        rng = ctx.rng("disaster", "scar", scar.id, year)
        if not rng.chance(SCAR_TURN):
            continue
        state = _next_scar_state(world, scar, rng, age)
        if not state or state == scar.state:
            continue
        kind = dis.SCARS_BY_KEY.get(scar.kind)
        was, scar.state = scar.state, state
        if state == dis.SCAR_HOLY:
            scar.holy = True
        if state == dis.SCAR_SETTLED:
            # Обжитый шрам перестаёт быть опасным — по крайней мере на вид.
            scar.danger = min(scar.danger, 1)
        scar.notes.append("%d: %s" % (year, state))
        region = world.regions.get(scar.region_id)
        title, text = texts.scar_turn(rng, scar, kind, was, state, region, age)
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="scar_turn", title=title, text=text,
            importance=2 if state != dis.SCAR_FORGOTTEN else 1,
            subjects=[scar.id], region_id=scar.region_id)


def _next_scar_state(world, scar, rng, age: int) -> str:
    """Что стало со шрамом: это решают люди рядом, а не сам шрам.

    Пустая строка значит «пока ничего»: шрам остаётся при своём, и это
    самый частый ответ. Место, которого боятся, помнят дольше прочих —
    страх лучшая память, чем благодарность.
    """
    people = any(world.settlements[sid].region_id == scar.region_id
                 for sid in world.active_settlements)
    if not people:
        # Некому обходить и некому обживать: шрам зарастает безымянным.
        return dis.SCAR_FORGOTTEN if age > 300 else ""
    faith = any(temple.region_id == scar.region_id
                for temple in world.temples.values()) or bool(world.faiths)
    # Освящают рано или никогда: через полтысячи лет это просто место,
    # куда не ходят, и объяснять его уже нечем.
    holy_time = faith and SCAR_HOLY_WINDOW[0] <= age <= SCAR_HOLY_WINDOW[1]

    if scar.state == dis.SCAR_FRESH:
        # Место своё занимает один раз. Что с ним станет, решается в первые
        # поколения, пока помнят беду: дальше только забывают.
        if scar.danger >= 2:
            pairs = [("", 0.2), (dis.SCAR_SHUNNED, 0.8)]
            if holy_time:
                pairs.append((dis.SCAR_HOLY, 0.25))
            return rng.weighted(pairs)
        pairs = [("", 0.3), (dis.SCAR_SETTLED, 0.55), (dis.SCAR_SHUNNED, 0.25)]
        if holy_time:
            pairs.append((dis.SCAR_HOLY, 0.2))
        return rng.weighted(pairs)

    if scar.state == dis.SCAR_SHUNNED:
        # Опасное место так и остаётся местом, куда не ходят: его не
        # обживают и не забывают, пока рядом живут люди. Освятить его уже
        # не освятят — для этого нужно было объяснение, а объяснения нет.
        if scar.danger >= 2 or age <= SCAR_FORGET_AGE:
            return ""
        return rng.weighted([("", 1.0), (dis.SCAR_SETTLED, 0.45),
                             (dis.SCAR_FORGOTTEN, 0.35)])

    if scar.state == dis.SCAR_SETTLED:
        # Здесь пашут и не знают, отчего земля такая.
        if age <= SCAR_SETTLED_AGE:
            return ""
        return rng.weighted([("", 1.0), (dis.SCAR_FORGOTTEN, 0.6)])

    # Святое место остаётся святым. Забывают не его, а причину, по которой
    # он свят, — и об этом сказано в самой вехе.
    return ""


# ---------------------------------------------------------------------------
# Потерянное знание
# ---------------------------------------------------------------------------
# Самое сильное последствие большой беды — не убитые, а забытое. Умение
# исчезает не потому, что его нельзя повторить, а потому, что умерли все,
# кто умел. Через века остаются обрывки — и по ним однажды находят целое.

LORE_CHANCE = 0.3           # у большой беды знание гибнет вместе с людьми
LORE_MAX = 2
LORE_FRAGMENT_AFTER = 100   # раньше этого обрывки ещё не ищут
LORE_FRAGMENT_CHANCE = 0.14
# Трудность 4 — «вернуть некому»: последний, кто умел, умер, и никаких
# обрывков для того, чтобы собрать целое, не хватит. Такое знание уходит
# из мира навсегда, и без этого утрата ничего не стоит: за десять тысяч
# лет иначе возвращается всё.
LORE_NEVER = 4
LORE_NEVER_CHANCE = {3: 0.6, 2: 0.2}
# Насколько легко вернуть знание по трудности 1…3 — за десятилетие.
# Дорожные карты чертят заново за век-полтора; письмо народа, которого
# не стало, не возвращается почти никогда, и это главное в утрате.
LORE_FIND_CHANCE = (0.04, 0.008, 0.0015)
LORE_FINDERS = ("летописец", "мастер", "изобретатель", "искатель",
                "верховный жрец", "ересиарх")


def lose_lore(ctx, calamity, spec, rng, year: int, date) -> None:
    """Что ушло вместе с теми, кто умел."""
    pairs = dis.lore_for(spec)
    if not pairs or not calamity.region_ids:
        return
    world = ctx.world

    # Знание гибнет там, где гибнут города и книжники: от одного недорода
    # никто не забывает, как плавят железо.
    want = 0
    if calamity.severity >= 4 and rng.chance(0.65):
        want = 2 if rng.chance(0.35) else 1
    elif calamity.settlements_lost and rng.chance(LORE_CHANCE):
        want = 1
    elif calamity.severity >= 3 and calamity.depth >= 3 and rng.chance(0.25):
        want = 1
    if want <= 0:
        return
    want = min(LORE_MAX, want)

    had = {item.kind for item in world.lost_lore.values()
           if item.state != dis.LORE_FOUND}
    made = 0
    for _ in range(want * 3):
        if made >= want:
            break
        kind = rng.weighted(list(pairs))
        if kind.key in had:
            continue          # дважды одно и то же не забывают
        had.add(kind.key)
        region_id = rng.choice(calamity.region_ids)
        hardness = kind.hardness
        forever = LORE_NEVER_CHANCE.get(hardness, 0.0)
        if forever and rng.chance(forever):
            hardness = LORE_NEVER
        lore = world.add_lost_lore(
            kind=kind.key, about=kind.about, calamity_id=calamity.id,
            region_id=region_id, lost=date, hardness=hardness,
            fragment=kind.fragment, state=dis.LORE_LOST)
        if hardness == LORE_NEVER:
            lore.notes.append("вернуть это некому: последний, кто умел, умер")
        calamity.lore_ids.append(lore.id)
        made += 1
        # Забытое умение — это не только грусть: земля без него слабее.
        if kind.hurts:
            region = world.regions.get(region_id)
            if region is not None:
                was = vuln_of(world, region_id, kind.hurts)
                region.vulnerability[kind.hurts] = min(
                    1.0, was + dis.VULN_LEARN)
        title, text = texts.lore_lost(rng, lore, kind, calamity, world)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="lore_lost",
            title=title, text=text, importance=3,
            subjects=[lore.id, calamity.id], region_id=region_id)


def find_lore(ctx, year: int, period: int) -> None:
    """Обрывки находят, а по обрывкам однажды находят и целое."""
    world = ctx.world
    for lore in list(world.lost_lore.values()):
        if lore.state == dis.LORE_FOUND or lore.lost is None:
            continue
        age = year - lore.lost.year
        if age < LORE_FRAGMENT_AFTER:
            continue
        rng = ctx.rng("disaster", "lore", lore.id, year)
        if lore.state == dis.LORE_LOST:
            if not rng.chance(LORE_FRAGMENT_CHANCE):
                continue
            lore.state = dis.LORE_FRAGMENTS
            lore.notes.append("%d: %s" % (year, dis.LORE_FRAGMENTS))
            title, text = texts.lore_fragments(rng, lore, world)
            world.add_event(
                date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
                kind="lore_fragments", title=title, text=text, importance=2,
                subjects=[lore.id], region_id=lore.region_id)
            continue
        if lore.hardness >= LORE_NEVER:
            continue          # обрывки есть, а собрать их некому
        hard = max(1, min(3, lore.hardness))
        if not rng.chance(LORE_FIND_CHANCE[hard - 1]):
            continue
        finder, actor_id, sex = _lore_finder(world, lore, rng, year)
        if not finder:
            continue
        lore.state = dis.LORE_FOUND
        lore.found = ctx.date_in(rng, year)
        lore.found_by = finder
        lore.notes.append("%d: %s" % (year, dis.LORE_FOUND))
        kind = dis.LORE_BY_KEY.get(lore.kind)
        if kind is not None and kind.hurts:
            region = world.regions.get(lore.region_id)
            if region is not None:
                was = vuln_of(world, lore.region_id, kind.hurts)
                region.vulnerability[kind.hurts] = max(
                    0.0, was - dis.VULN_LEARN)
        title, text = texts.lore_found(rng, lore, finder, age, world, sex)
        world.add_event(
            date=lore.found, era_index=world.era_index_at(year),
            kind="lore_found", title=title, text=text, importance=3,
            actors=[actor_id] if actor_id else None,
            subjects=[lore.id], region_id=lore.region_id)


def _lore_finder(world, lore, rng, year: int) -> tuple:
    """Кто вернул знание: живой книжник, а если некому — сам город."""
    here = {sid for sid in world.active_settlements
            if world.settlements[sid].region_id == lore.region_id}
    people = []
    for figure in world.figures.values():
        if not figure.alive_at(year) or figure.home_id not in here:
            continue
        if any(role in LORE_FINDERS for role in figure.roles):
            people.append(figure)
    if people:
        figure = rng.choice(sorted(people, key=lambda item: item.id))
        return figure.plain_name, figure.id, figure.sex
    cities = [world.settlements[sid] for sid in here]
    if not cities:
        return "", "", ""
    # Знание вернул не человек, а город: так бывает, когда возвращали его
    # многие и ни одного не запомнили.
    city = max(cities, key=lambda item: (item.population, item.id))
    return "город по имени %s" % city.name, "", "m"


# ---------------------------------------------------------------------------
# Фронт: нашествие идёт по землям
# ---------------------------------------------------------------------------
# «Вторжение в пяти землях» — сводка, а не событие. События — это то, что
# первой пала земля у пролома, что перевал держали одиннадцать лет, что
# столица досталась им последней и что две земли так и остались за ними.

FRONT_FROM = 2              # с какой тяжести у беды есть направление
FRONT_STEP = 0.3            # с какой охотой фронт двигается за год
FRONT_HOLD_CHANCE = 0.4     # и как часто земля его задерживает
FRONT_HOLD_MAX = 2          # дважды на одной земле — и хватит


def wants_front(calamity, spec) -> bool:
    """Есть ли у этой беды направление.

    Мор и голод идут по всем землям сразу, а нашествие — откуда-то куда-то,
    и это разные истории. Направление есть у того, у чего есть войско или
    чужая воля: нашествия, завоевания, священной войны.
    """
    if calamity.severity < FRONT_FROM or len(calamity.region_ids) < 2:
        return False
    return spec.kind in (cat.INVASION, cat.POLITICAL, cat.RELIGIOUS)


def open_front(ctx, calamity, spec, rng, year: int) -> None:
    """Где пролом и куда они пойдут дальше."""
    if not wants_front(calamity, spec):
        return
    world = ctx.world
    first = calamity.region_ids[0]
    calamity.front.append({
        "земля": first, "год": int(year), "состояние": dis.LAND_HELD,
        "чем": "с этого начали", "город": "", "роль": "",
    })
    city = _front_city(world, first)
    if city is not None:
        calamity.front[-1]["город"] = city.name
        calamity.front[-1]["роль"] = dis.ROLE_GATE if rng.chance(0.55) \
            else dis.ROLE_FIRST


def move_front(ctx, calamity, spec, rng, year: int) -> None:
    """Фронт за год: шаг вперёд, или задержка, и у задержки есть причина."""
    if not calamity.front:
        return
    world = ctx.world
    # Пока задержка не вышла, они стоят — и стоят по названной причине.
    stop = _front_stop(calamity)
    if stop > year:
        return

    ahead = _front_ahead(calamity)
    if not ahead:
        return
    if not rng.chance(FRONT_STEP * max(0.3, min(2.0, calamity.force))):
        return

    region_id = ahead[0]
    region = world.regions.get(region_id)
    has_fort = any(world.fortresses[fid].region_id == region_id
                   for fid in world.active_fortresses)
    held_here = sum(1 for row in calamity.front
                    if row["земля"] == region_id
                    and row.get("состояние") == dis.LAND_THREAT)
    pairs = dis.holds_for(region, has_fort)
    if pairs and held_here < FRONT_HOLD_MAX and rng.chance(FRONT_HOLD_CHANCE):
        hold = rng.weighted(list(pairs))
        years = rng.randint(*hold.years)
        row = {"земля": region_id, "год": int(year),
               "состояние": dis.LAND_THREAT, "чем": hold.about,
               "город": "", "роль": "", "до": int(year + years)}
        # Пока держат, город за спиной у линии наполняется теми, кто ушёл;
        # а если держат выкупом, то платит его тот самый город.
        city = _front_city(world, region_id)
        if city is not None:
            if hold.key == "выкуп":
                row["город"], row["роль"] = city.name, dis.ROLE_BOUGHT
            elif rng.chance(0.35):
                row["город"], row["роль"] = city.name, dis.ROLE_SHELTER
        calamity.front.append(row)
        if calamity.severity >= 3:
            title, text = texts.front_hold(rng, calamity, hold, region, years,
                                           row["роль"], row["город"])
            world.add_event(
                date=ctx.date_in(rng, year),
                era_index=world.era_index_at(year), kind="front_hold",
                title=title, text=text, importance=3,
                subjects=[calamity.id], region_id=region_id)
        return

    # Земля взята. Разорена или занята — это разные вещи: разорённую
    # бросают, занятую держат.
    state = dis.LAND_RUINED if rng.chance(0.45) else dis.LAND_HELD
    row = {"земля": region_id, "год": int(year), "состояние": state,
           "чем": "", "город": "", "роль": ""}
    city = _front_city(world, region_id)
    if city is not None:
        role = _city_role(calamity, city, rng, state)
        if role:
            row["город"], row["роль"] = city.name, role
    calamity.front.append(row)
    if calamity.severity >= 3:
        title, text = texts.front_step(rng, calamity, region, state,
                                       row["роль"], row["город"])
        world.add_event(
            date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
            kind="front_step", title=title, text=text, importance=3,
            subjects=[calamity.id], region_id=region_id)


def close_front(ctx, calamity, rng, year: int, date, won: bool) -> None:
    """Чем кончился фронт: что вернули, а что осталось за ними."""
    if not calamity.front:
        return
    world = ctx.world
    taken = []
    for row in calamity.front:
        if row.get("состояние") in (dis.LAND_HELD, dis.LAND_RUINED):
            taken.append(row["земля"])
    if not taken:
        return
    # Даже победой возвращают не всё: за дальние земли уже не идут. Но
    # «осталась за врагом» — не слово в летописи, а положение дел: земля,
    # в которой живут прежние города прежней державы, за чужими не
    # остаётся, чем бы её ни называли.
    kept = []
    for region_id in taken:
        back = won and rng.chance(0.8)
        if not back and _still_theirs(world, region_id):
            back = True
        calamity.front.append({
            "земля": region_id, "год": int(year),
            "состояние": dis.LAND_FREED if back else dis.LAND_LOST,
            "чем": "", "город": "", "роль": "",
        })
        if not back:
            kept.append(region_id)
    if not kept:
        return
    title, text = texts.front_end(rng, calamity, kept, world, won)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="front_end",
        title=title, text=text, importance=4, subjects=[calamity.id],
        region_id=kept[0])


def _still_theirs(world, region_id: str) -> bool:
    """Живут ли в земле прежние города прежней державы.

    Если живут — землю отбили, как бы ни шёл фронт: державы не теряют
    земель, в которых стоят их же города с их же людьми.
    """
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id != region_id:
            continue
        polity = world.polities.get(settlement.polity_id)
        if polity is not None and polity.ended is None:
            return True
    return False


def front_states(calamity) -> dict:
    """Что с каждой землёй на нынешний час: последняя запись и есть ответ."""
    out = {}
    for row in calamity.front:
        out[row["земля"]] = row.get("состояние", dis.LAND_CLEAR)
    return out


def _front_ahead(calamity) -> list:
    """Земли, до которых фронт ещё не дошёл, — в порядке хода."""
    states = front_states(calamity)
    return [region_id for region_id in calamity.region_ids
            if states.get(region_id, dis.LAND_CLEAR)
            in (dis.LAND_CLEAR, dis.LAND_THREAT)]


def _front_stop(calamity) -> int:
    """До какого года они стоят, если стоят."""
    stop = 0
    for row in calamity.front:
        if row.get("состояние") == dis.LAND_THREAT:
            stop = max(stop, int(row.get("до", 0)))
    return stop


def _front_city(world, region_id: str):
    """Главный город земли: о нём и пойдёт речь."""
    cities = [world.settlements[sid] for sid in world.active_settlements
              if world.settlements[sid].region_id == region_id]
    if not cities:
        return None
    return max(cities, key=lambda item: (item.population, item.id))


def _city_role(calamity, city, rng, state: str) -> str:
    """Чем этот город был в этом нашествии.

    Роль не бросается костью вслепую, и она не спорит с тем, что стало с
    землёй. Последним оплотом бывает тот, за кем и правда никого не
    осталось. «Взят первым» бывает один на всё нашествие. А «выстоял» —
    только там, где округу выжгли, а город не взяли.
    """
    if len(_front_ahead(calamity)) <= 1:
        return dis.ROLE_KEEP
    if city.is_capital and rng.chance(0.5):
        return dis.ROLE_KEEP
    pairs = []
    # Первым берут один город, и это тот, что сразу за проломом.
    taken = sum(1 for row in calamity.front[1:]
                if row.get("состояние") in (dis.LAND_HELD, dis.LAND_RUINED))
    if taken <= 1:
        pairs.append((dis.ROLE_FIRST, 1.6))
    if state == dis.LAND_RUINED:
        pairs.append((dis.ROLE_STOOD, 1.2))
    if not pairs:
        return ""
    pairs.append(("", 1.4))
    return rng.weighted(pairs)


# ---------------------------------------------------------------------------
# Шесть версий одного события
# ---------------------------------------------------------------------------
# «Как было на деле» знает только летопись. Держава записала своё, вера
# объяснила своё, уцелевшие помнят один день, враги — малый поход, а
# поздние своды нашли причину поскучнее. Все шесть версий держатся рядом,
# и ни одна не отменяет остальных.

VERSION_FROM = 2            # с какой тяжести у беды заводятся версии
VERSION_SHARE = 0.6         # и как часто заводятся вообще


def tell_versions(ctx, calamity, spec, rng, year: int = 0, date=None) -> dict:
    """Кто что про эту беду рассказал.

    Версий не бывает у мелочи: про недород в одной волости никто не спорит.
    Версии заводятся там, где было что делить, — и чем беда глубже, тем
    больше голосов её пересказывают.
    """
    if calamity.severity < VERSION_FROM:
        return {}
    if calamity.severity < 4 and not rng.chance(VERSION_SHARE):
        return {}
    world = ctx.world

    # Правда всегда одна и всегда первая: настоящая причина, даже если
    # мир её не узнал.
    truth = calamity.cause_hidden or calamity.cause or "причину не назвали"
    told = {dis.V_TRUE: truth}

    voices = [dis.V_STATE, dis.V_SURVIVOR, dis.V_FOLK]
    if calamity.kind in (cat.INVASION, cat.POLITICAL, cat.RELIGIOUS):
        voices.append(dis.V_ENEMY)
    if world.faiths:
        voices.append(dis.V_FAITH)
    # Поздние своды появляются только если после беды было кому писать.
    if calamity.severity >= 3:
        voices.append(dis.V_LATER)

    for voice in voices:
        rows = dis.VERSION_TWIST.get(voice, ())
        if not rows:
            continue
        told[voice] = rng.choice(rows)
    calamity.versions = told

    # Спор о том, что это было, — отдельная запись: без неё шесть версий
    # лежат в данных и в летопись не попадают.
    if date is not None and len(told) >= 4:
        title, text = texts.versions(rng, calamity, told)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="calamity_versions", title=title, text=text,
            importance=3 if calamity.severity < 4 else 4,
            subjects=[calamity.id],
            region_id=calamity.region_ids[0] if calamity.region_ids else "")
    return told


# ---------------------------------------------------------------------------
# Катастрофическая эпоха
# ---------------------------------------------------------------------------
# Шесть бед, идущих одна из другой, — это не шесть событий, а одно время,
# и у времени есть имя. Имя берётся из того, что в эпохе было, и у каждого
# народа оно своё: держава помнит войну, деревня — голодные годы.

ERA_FROM = 3                # с какой тяжести беда тянет за собой эпоху
ERA_NEED = 3                # сколько бед подряд делают из них одно время
ERA_GAP = 60                # и какой разрыв ещё считается «подряд»
ERA_DEPTH = 2               # глубина, ниже которой беда в эпоху не входит
# Эпоха — сгущение, а не полтысячи лет с бедой раз в век. Набралось на три
# века — время закрывается, и следующая беда открывает уже новое.
ERA_MAX = 280


def era_watch(ctx, calamity, year: int, date) -> None:
    """Беда открывает эпоху, входит в открытую или закрывает её.

    Эпоха не объявляется заранее: она набирается. Пока беды идут одна за
    другой без передышки, они складываются в одно время; как только мир
    получает сто лет покоя, время кончается и получает имя.
    """
    world = ctx.world
    if calamity.severity < ERA_FROM or calamity.depth < ERA_DEPTH:
        return
    rng = ctx.rng("disaster", "era", calamity.id)
    era = world.crisis_eras.get(world.era_open)
    last = getattr(ctx, "era_last", 0)
    if era is not None and era.end is None:
        # В открытое время беда входит, только если пришла ему вслед: через
        # три поколения покоя это уже не то же время, а другое.
        if (last and year - last > ERA_GAP) or \
                year - era.start.year > ERA_MAX:
            close_era(ctx, year, date, force=True)
            era = None
    if era is None or era.end is not None:
        era = world.add_crisis_era(name="", start=date)
        world.era_open = era.id
        era.notes.append("открыта бедой «%s»" % calamity.name)
    era.calamity_ids.append(calamity.id)
    era.deaths += calamity.deaths
    era.depth = max(era.depth, calamity.depth)
    for region_id in calamity.region_ids:
        if region_id not in era.regions:
            era.regions.append(region_id)
    calamity.era_id = era.id
    ctx.era_last = year
    _ = rng


def close_era(ctx, year: int, date, force: bool = False) -> None:
    """Покой длиннее века — и набранное время становится эпохой с именем.

    Эпоха из двух бед — это не эпоха, а две беды: такую закрываем молча
    и не даём ей имени. `force` — последний зов на исходе истории: время,
    которое так и не кончилось, всё равно получает имя.
    """
    world = ctx.world
    era = world.crisis_eras.get(world.era_open)
    if era is None or era.end is not None:
        return
    last = getattr(ctx, "era_last", 0)
    if not force and (not last or year - last < ERA_GAP):
        return
    world.era_open = ""
    era.end = date
    if len(era.calamity_ids) < ERA_NEED:
        era.notes.append("в одно время не сложилось: бед было мало")
        world.crisis_eras.pop(era.id, None)
        for calamity_id in era.calamity_ids:
            calamity = world.calamities.get(calamity_id)
            if calamity is not None:
                calamity.era_id = ""
        return

    rng = ctx.rng("disaster", "era-name", era.id)
    era.name = _era_name(world, era, rng)
    era.voices = _era_voices(world, era, rng)
    title, text = texts.era_closed(rng, era, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="crisis_era",
        title=title, text=text, importance=5,
        subjects=[era.id] + era.calamity_ids[:6],
        region_id=era.regions[0] if era.regions else "")


def _era_name(world, era, rng) -> str:
    """Имя эпохи — из того, что в ней было тяжелее всего."""
    weighted = []
    for calamity_id in era.calamity_ids:
        calamity = world.calamities.get(calamity_id)
        if calamity is None:
            continue
        for word in dis.ERA_WORDS.get(calamity.key, ()):
            weighted.append((word, float(calamity.severity)))
    taken = {item.name for item in world.crisis_eras.values() if item.name}
    for _ in range(12):
        name = rng.weighted(weighted) if weighted \
            else rng.choice(dis.ERA_GENERIC)
        if name not in taken:
            return name
    # Тёзки бывают и у эпох: тогда зовут по числу бед, а не по счёту.
    for name in dis.ERA_GENERIC:
        if name not in taken:
            return name
    return "%s (%d–%d)" % (dis.ERA_GENERIC[0], era.start.year,
                           era.end.year if era.end else era.start.year)


def _era_voices(world, era, rng) -> list:
    """У каждого своё имя для одного и того же времени."""
    pool = []
    for calamity_id in era.calamity_ids:
        calamity = world.calamities.get(calamity_id)
        if calamity is None:
            continue
        pool.extend(dis.ERA_WORDS.get(calamity.key, ()))
    # Имена не повторяем: три голоса, зовущие время одним словом, — это
    # один голос, а не три.
    pool = sorted({name for name in pool if name != era.name})
    out = []
    for who, frame in dis.ERA_VOICES:
        if not pool:
            break
        if not rng.chance(0.7):
            continue
        name = rng.choice(pool)
        pool.remove(name)
        out.append({"кто": who, "имя": name, "оборот": frame % name})
    return out


# ---------------------------------------------------------------------------
# Онтологическая беда: та, после которой в мире переменилось правило
# ---------------------------------------------------------------------------
# Пять ступеней глубины кончаются пятой: поверхностная, поколенческая,
# историческая, цивилизационная — и онтологическая. Последняя меняет не
# державу и не уклад, а само правило мира. Это не новая физика: это
# запись в памяти мира, на которую дальше ссылаются вера, обычай и
# летопись.

def change_rule(ctx, calamity, rng, year: int, date) -> str:
    """Беда пятой глубины переменяет правило мира."""
    if calamity.depth < 5:
        return ""
    world = ctx.world
    changed = world.notes.setdefault("правила мира", [])
    taken = {row.get("что") for row in changed}
    free = [rule for rule in dis.WORLD_RULES if rule not in taken]
    if not free:
        return ""          # все правила этого мира уже переменились
    rule = rng.choice(free)
    changed.append({"год": int(year), "что": rule, "беда": calamity.name})
    calamity.notes.append("переменилось правило мира: %s" % rule)
    title, text = texts.rule_changed(rng, calamity, rule, world)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="world_rule",
        title=title, text=text, importance=5, subjects=[calamity.id],
        region_id=calamity.region_ids[0] if calamity.region_ids else "")
    return rule


# ---------------------------------------------------------------------------
# Старый враг: беда меняет отношения держав
# ---------------------------------------------------------------------------
# «Нашествие отбито» — и на этом обычно всё. А между державами после
# такого остаётся то, что переживёт и победителей: обида на того, кто не
# пришёл на помощь, и память о том, кто пришёл.

ENEMY_FROM = 3              # с какой тяжести беда оставляет след в политике


def old_enemy(ctx, calamity, spec, rng, year: int) -> None:
    """Кто после беды стал старым врагом, а кто — тем, кого помнят добром."""
    if calamity.severity < ENEMY_FROM:
        return
    world = ctx.world
    hurt = sorted(calamity.deaths_by_polity.items(),
                  key=lambda pair: (-pair[1], pair[0]))
    if not hurt:
        return
    victim = world.polities.get(hurt[0][0])
    if victim is None or victim.ended is not None:
        return

    # Тот, кто на этой беде поднялся, — сосед, занявший опустевшие земли,
    # или тот, кто не пришёл, когда звали. Обида ложится на него.
    others = [world.polities[pid] for pid in world.active_polities
              if pid != victim.id]
    if not others:
        return
    near = [item for item in others
            if set(item.region_ids) & set(calamity.region_ids)]
    pool = near or others
    blamed = rng.choice(sorted(pool, key=lambda item: item.id))
    history.leave(world, history.GRUDGE, year, victim.id, blamed.id,
                  weight=0.3 + 0.1 * calamity.severity,
                  note="не пришли, когда шла беда по имени «%s»"
                       % calamity.name)
    line = "старый враг с беды «%s»: %s" % (calamity.name, blamed.name)
    if line not in victim.notes:
        victim.notes.append(line)

    # А кто пришёл — того помнят добром, и это тоже след, а не строчка.
    if len(pool) > 1 and rng.chance(0.45):
        friend = rng.choice(sorted([item for item in pool
                                    if item.id != blamed.id],
                                   key=lambda item: item.id))
        history.leave(world, history.FAVOUR, year, victim.id, friend.id,
                      weight=0.25 + 0.08 * calamity.severity,
                      note="пришли на помощь в беду по имени «%s»"
                           % calamity.name)
        line = "помнят добром с беды «%s»: %s" % (calamity.name, friend.name)
        if line not in victim.notes:
            victim.notes.append(line)


# ---------------------------------------------------------------------------
# Беженцы: беда не только убивает, но и гонит
# ---------------------------------------------------------------------------
# Разорённая земля пустеет не только мёртвыми. Люди уходят — и город,
# куда они пришли, становится вдвое больше себя, с чужим наречием на
# улицах и с теми, кому тут нечем заняться.

REFUGEE_SHARE = (0.1, 0.3)  # какая доля уцелевших уходит из разорённой земли
REFUGEE_MIN = 300           # ниже этого числа исход не считают исходом


def refugees(ctx, calamity, rng, year: int, date) -> None:
    """Куда ушли те, кто ушёл, и что стало с городом, который их принял."""
    world = ctx.world
    ruined = [row["земля"] for row in calamity.front
              if row.get("состояние") in (dis.LAND_RUINED, dis.LAND_LOST)]
    if not ruined:
        ruined = list(calamity.region_ids[:1]) if calamity.settlements_lost \
            else []
    if not ruined:
        return

    for region_id in dict.fromkeys(ruined):
        leaving = 0
        from_cities = []
        for settlement_id in list(world.active_settlements):
            settlement = world.settlements[settlement_id]
            if settlement.region_id != region_id or settlement.population <= 0:
                continue
            share = rng.uniform(*REFUGEE_SHARE)
            gone = int(settlement.population * share)
            if gone <= 0:
                continue
            settlement.population -= gone
            leaving += gone
            from_cities.append(settlement)
        if leaving < REFUGEE_MIN:
            # Слишком мало, чтобы это было исходом: вернём людей на место.
            for settlement in from_cities:
                settlement.population += int(leaving / max(1,
                                                           len(from_cities)))
            continue

        host = _refuge_city(world, region_id, calamity, rng)
        if host is None:
            continue
        host.population += leaving
        calamity.notes.append(
            "исход из земли: ушло %d, приняли в городе по имени %s"
            % (leaving, host.name))
        town = world.town_of(host.id) if hasattr(world, "town_of") else None
        if town is not None:
            town.notes.append("принял беженцев беды «%s»" % calamity.name)
        region = world.regions.get(region_id)
        title, text = texts.refuge(rng, calamity, region, host, leaving, world)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="refuge",
            title=title, text=text, importance=3,
            subjects=[calamity.id, host.id], region_id=host.region_id,
            race_id=host.race_id)


def _refuge_city(world, region_id: str, calamity, rng):
    """Куда бегут: в ближний город из целой земли, а не куда попало."""
    region = world.regions.get(region_id)
    near = set(region.neighbors) if region is not None else set()
    hurt = set(calamity.region_ids)
    pairs = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.region_id == region_id or settlement.population < 400:
            continue
        # Из-под беды не бегут в беду: земли, по которым она шла, не в счёт.
        if settlement.region_id in hurt:
            continue
        weight = float(settlement.population)
        if settlement.region_id in near:
            weight *= 4.0      # ближний город принимает первым
        pairs.append((settlement, weight))
    if not pairs:
        return None
    return rng.weighted(pairs)


__all__ = ["prepare", "vuln_of", "vuln_kind", "vuln_factor", "hurt_lands",
           "build_works", "forget", "choose_cause", "want_omens", "schedule",
           "tick_pending", "phase_at", "note_phase", "maybe_turn",
           "force_now", "respond", "count_gains", "name_actors",
           "plan_chain", "tick_chains", "count_damage", "four_outcomes",
           "dark_pressure_of", "leave_scars", "age_scars",
           "lose_lore", "find_lore", "wants_front", "open_front",
           "move_front", "close_front", "front_states",
           "tell_versions", "era_watch", "close_era",
           "change_rule", "old_enemy", "refugees",
           "PROFILE_KEYS"]
