# -*- coding: utf-8 -*-
"""Жизнь города: биография, которая пишется сама.

Город тут не декорация с числом жителей, а историческая личность. У него
есть причина существовать, и эта причина тянется через всю его жизнь:
город у переправы и город у рудной жилы проживут разные тысячу лет.

Раз в десять лет система смотрит на каждое живое поселение и спрашивает:
что с ним случилось за эти годы? Выросло ли, село ли, сменило ли хозяина,
видело ли войну, пережило ли беду. Из ответов складываются **вехи**, из
вех — районы, слои под землёй, тяготы и нрав. Ничего не назначается
наперёд: воинственным город становится потому, что сто лет отбивался, а
не потому, что так выпало при основании.

Отдельно стоят две вещи, ради которых всё и затевалось.

**Занятие может кончиться.** Жила иссякает, брод заносит, граница уходит
на сто вёрст. Тогда город либо находит новое занятие — и это перелом в
его жизни, — либо начинает мельчать, пустеть и однажды остаётся стоять
без людей.

**Город помнит себя телом.** Каждый пожар, осада и перестройка оставляют
слой: ход из осаждённого города, могильник под кварталом, затопленный
ярус пристани. Через пятьсот лет под ногами лежит четыре чужих города —
и оттуда же берётся половина городских былей.
"""

from __future__ import annotations

from .. import goods
from .. import history
from .. import narrative_town as texts
from .. import races as races_mod
from .. import township as cat
from ..models import ACTIVE, RUINED

# Биографию заводят не всякому двору: у стана в полсотни душ её просто
# нет. Порог низкий — город должен успеть пожить, прежде чем о нём
# напишут.
MIN_SOULS = 260
GROWTH_MARK = 2.4          # во сколько раз надо вырасти для «первого роста»
CRISIS_DROP = 0.72         # и насколько просесть для «первого кризиса»
DISTRICT_RATE = 0.35       # шанс, что подросший город заведёт новый конец
TROUBLE_RATE = 0.11        # и что у него заведётся тягота
TROUBLE_LIFE = (30, 160)   # сколько лет тягота тянется, прежде чем решится
MAX_TROUBLES = 3
LOSS_RATE = 0.012          # шанс, что занятие города кончится за такт
SECRET_RATE = 0.35         # шанс, что слой обернётся городской тайной
MAX_SECRETS = 3
# Нрав складывается не из громких случаев, а из того, чем город жил
# изо дня в день. Поэтому занятие и тяготы подталкивают его понемногу
# каждый такт, а всё, чего давно не было, само сползает к середине:
# так сто лет войны дают воинственность, а триста лет мира её убирают.
# Равновесие тут посчитано, а не подобрано на глаз: постоянный крен
# силы t держит шкалу около 0,5 + t·(DAILY/FORGET). При этих числах
# сильное занятие (0,4) даёт около 0,85, слабое (0,2) — около 0,68, а
# всё, что перестало давить, за век-полтора сползает обратно к середине.
TEMPER_DRIFT = 0.35        # как сильно бьёт разовый случай
TEMPER_DAILY = 0.044       # и как давит то, чем город живёт постоянно
TEMPER_FORGET = 0.05       # насколько за такт всё сползает к середине
MAX_MARKS = 48             # длиннее биография не нужна никому


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("townships", year)
    besieged = _war_marks(world)
    struck = _calamity_regions(world)

    for settlement_id in list(world.active_settlements):
        settlement = world.settlements[settlement_id]
        if settlement.status != ACTIVE:
            continue
        town = world.town_of(settlement_id)
        if town is None:
            if settlement.population < MIN_SOULS:
                continue
            town = _born(ctx, rng, settlement, year)
        # Беда идёт десятилетиями, но городу она — одно событие, а не
        # запись в каждом такте: отмечаем только новую.
        woe = struck.get(settlement.region_id, "")
        _live(ctx, rng, town, settlement, year, period,
              besieged.get(settlement_id, ""),
              woe if woe and woe != town.last_woe else "")

    _close_dead(ctx, rng, year)


# ---------------------------------------------------------------------------
# Рождение биографии
# ---------------------------------------------------------------------------

def _born(ctx, rng, settlement, year: int):
    """Почему этот город здесь и чем он начал жить."""
    world = ctx.world
    region = world.regions.get(settlement.region_id)
    origin = _pick_origin(ctx, rng, settlement, region)
    town = world.add_township(
        settlement_id=settlement.id, origin=origin.key,
        born=settlement.founded, life=cat.RISING,
        seen=settlement.population, held_by=settlement.polity_id,
        peak=settlement.population, peak_year=settlement.founded.year)

    # Нрав начинается с того, отчего город возник, и дальше живёт сам.
    town.temper = {name: 0.5 for name in cat.TEMPERS}
    _tilt(town, origin.tilt, 1.0)

    trade = cat.TRADES_BY_KEY.get(origin.trade)
    if trade is None or not _trade_fits(trade, region, settlement):
        trade = _pick_trade(ctx, rng, settlement, region, avoid=())
    if trade is not None:
        town.trades.append({"чем": trade.key, "с": settlement.founded.year,
                            "по": 0})
        _tilt(town, trade.tilt, 0.6)
        town.weak = trade.vuln

    _mark(ctx, town, settlement.founded.year, cat.FOUNDED,
          texts.mark_line(rng, cat.FOUNDED, origin.about))

    # Город на костях другого: если тут уже стояли, старое остаётся внизу.
    older, exact = _older_here(world, settlement)
    if older is not None and not exact and not rng.chance(0.4):
        older = None        # рядом, но не на том же месте
    if older is not None:
        town.layers.append({"слой": "древний фундамент под нынешним домом",
                            "год": settlement.founded.year,
                            "от чего": "город по имени %s" % older.name})
        _mark(ctx, town, settlement.founded.year, cat.RESETTLED,
              texts.mark_line(rng, cat.RESETTLED,
                              "тут стоял город по имени %s" % older.name))
        town.notes.append("стоит на месте города по имени %s" % older.name)
    elif origin.leaves:
        town.layers.append({"слой": _known_layer(origin.leaves),
                            "год": settlement.founded.year,
                            "от чего": origin.name})

    _refresh_mix(world, town, settlement)
    _refresh_estates(town, settlement)
    _refresh_forces(town, settlement)
    _refresh_trade_goods(world, town, settlement)
    return town


def _pick_origin(ctx, rng, settlement, region):
    """Причина основания — из того, что в этом месте вообще возможно."""
    world = ctx.world
    terrain = region.terrain if region is not None else races_mod.PLAIN
    rich = _region_goods(region)
    pairs = []
    for origin in cat.ORIGINS:
        if origin.terrains and terrain not in origin.terrains:
            continue
        if origin.wants_good and origin.wants_good not in rich:
            continue
        if origin.needs_polity and not settlement.polity_id:
            continue
        weight = origin.weight
        if origin.key == "older" and _older_here(world, settlement)[0] is None:
            weight *= 0.25
        if origin.key == "villages" and settlement.origin_tribe_id:
            weight *= 2.0
        pairs.append((origin, weight))
    if not pairs:
        return cat.ORIGINS_BY_KEY["villages"]
    pairs.sort(key=lambda pair: pair[0].key)
    return rng.weighted(pairs)


def _older_here(world, settlement):
    """Стоял ли тут город раньше — тот самый город-призрак.

    Новый город на костях старого — не редкость, а правило: место,
    удобное однажды, удобно и через триста лет. Зато и лежит под ним
    чужое: чужие погреба, чужие могилы и чужие байки.

    Возвращает пару (город, точно ли это то самое место). На карте
    «точно» значит тот же гекс; в мире без карты точнее земли не
    скажешь, и тогда совпадение — вероятное, а не верное.
    """
    exact = settlement.hex_index >= 0
    best, best_year = None, -1
    for other in world.settlements.values():
        if other.id == settlement.id or other.status == ACTIVE:
            continue
        if other.ended is None or other.ended.ordinal > settlement.founded.ordinal:
            continue
        if exact:
            if other.hex_index != settlement.hex_index:
                continue
            return other, True
        if other.region_id != settlement.region_id:
            continue
        # Слишком давнее запустение уже никто не помнит и не видит.
        if settlement.founded.year - other.ended.year > 250:
            continue
        if other.ended.year > best_year:
            best, best_year = other, other.ended.year
    return best, False


# ---------------------------------------------------------------------------
# Десять лет городской жизни
# ---------------------------------------------------------------------------

def _live(ctx, rng, town, settlement, year: int, period: int,
          war: str, disaster: str) -> None:
    souls = settlement.population
    before = town.seen or souls

    # --- как город идёт: вверх, ровно или вниз ------------------------
    if souls > town.peak:
        town.peak, town.peak_year = souls, year
    if souls >= before * 1.08:
        town.life = cat.RISING
    elif souls <= before * 0.92:
        town.life = cat.FADING
        town.low_year = year
    else:
        town.life = cat.STILL
    town.seen = souls

    # Первый рост и первая беда отмечаются по одному разу за жизнь.
    if souls >= _first_souls(town) * GROWTH_MARK and not _has(town,
                                                              cat.FIRST_GROWTH):
        _mark(ctx, town, year, cat.FIRST_GROWTH,
              texts.mark_line(rng, cat.FIRST_GROWTH))
    if souls <= town.peak * CRISIS_DROP and town.peak > 0 \
            and not _has(town, cat.FIRST_CRISIS):
        _mark(ctx, town, year, cat.FIRST_CRISIS,
              texts.mark_line(rng, cat.FIRST_CRISIS, _why_shrunk(town, war,
                                                                 disaster)))

    # --- смена хозяина ------------------------------------------------
    if settlement.polity_id != town.held_by:
        town.held_by = settlement.polity_id
        _mark(ctx, town, year, cat.NEW_HAND, texts.mark_line(rng, cat.NEW_HAND))
        _tilt(town, {"устойчивость": -0.1, "закрытость": 0.05}, 0.5)
        _refresh_mix(ctx.world, town, settlement, shaken=True)

    # --- война и беда оставляют след, а не строчку ---------------------
    if war:
        _mark(ctx, town, year, cat.WAR_CAME, texts.mark_line(rng, cat.WAR_CAME))
        _tilt(town, {"воинственность": 0.2, "устойчивость": -0.05}, 0.8)
        _leave_layer(ctx, rng, town, year, "осада")
        # Осада перестраивает укрепления: город чинит не «стену вообще»,
        # а то самое место, где его проломили.
        if war == "осада" or rng.chance(0.4):
            work = texts.wall_work(rng)
            if work not in town.notes:
                town.notes.append(work)
                _mark(ctx, town, year, cat.REBUILT, texts.cap(work) + ".")
    if disaster:
        town.last_woe = disaster
        woe = ctx.world.calamities.get(disaster)
        _mark(ctx, town, year, cat.DISASTER,
              texts.mark_line(rng, cat.DISASTER,
                              "беда по имени %s дошла и сюда" % woe.name
                              if woe is not None
                              else "беда прошла по этой земле"))
        _leave_layer(ctx, rng, town, year, "бедствие")
        if rng.chance(0.4):
            _mark(ctx, town, year, cat.REBUILT,
                  texts.mark_line(rng, cat.REBUILT))
            _leave_layer(ctx, rng, town, year, "перестройка")

    # --- город растёт вширь -------------------------------------------
    if town.life == cat.RISING and rng.chance(DISTRICT_RATE * period / 10.0):
        _new_district(ctx, rng, town, settlement, year)

    # --- чем город кормится и надолго ли ------------------------------
    _trade_turn(ctx, rng, town, settlement, year, period)

    # --- тяготы -------------------------------------------------------
    _troubles_turn(ctx, rng, town, settlement, year, period)

    # --- тайны ---------------------------------------------------------
    if town.layers and len(town.secrets) < MAX_SECRETS \
            and rng.chance(SECRET_RATE * period / 20.0):
        _new_secret(ctx, rng, town, year)

    _daily_temper(town)

    # Уклад и сословия пересчитываются редко: они меняются веками.
    if rng.chance(0.2):
        _refresh_mix(ctx.world, town, settlement)
        _refresh_estates(town, settlement)
        _refresh_forces(town, settlement)
        _refresh_trade_goods(ctx.world, town, settlement)


def _first_souls(town) -> int:
    """Сколько душ было в начале: по этому мерится «вырос втрое»."""
    for mark in town.marks:
        if mark.get("вид") == cat.FOUNDED:
            return max(120, int(mark.get("души", 0) or 200))
    return 200


def _why_shrunk(town, war: str, disaster: bool) -> str:
    if war:
        return "город брали"
    if disaster:
        return "беда прошла по этой земле"
    if town.troubles:
        return cat.TROUBLES_BY_KEY[town.troubles[-1]["тягота"]].about
    return "людей стало меньше, и никто не мог сказать почему"


# ---------------------------------------------------------------------------
# Концы города
# ---------------------------------------------------------------------------

def _new_district(ctx, rng, town, settlement, year: int) -> None:
    """Новый конец города появляется от жизни, а не из списка."""
    souls = settlement.population
    have = {item["конец"] for item in town.districts}
    # Концов у города столько, сколько он может прокормить: у пятитысячного
    # их четыре, у сорокатысячного — с десяток, и это уже большой город.
    if len(town.districts) >= 3 + souls // 4000:
        return
    trade = town.trade
    pairs = []
    for district in cat.DISTRICTS:
        if district.weight <= 0 or souls < district.min_souls:
            continue
        if district.once and district.key in have:
            continue
        weight = district.weight
        if district.wants_trade:
            if trade in district.wants_trade:
                weight *= 2.2
            elif any(key in district.wants_trade
                     for key in _live_trades(town)):
                weight *= 0.8      # город кормится не одним делом
            else:
                weight *= 0.12     # такому концу тут взяться неоткуда
        if district.key == "старый город" and len(town.districts) < 3:
            continue        # старым город становится не сразу
        pairs.append((district, weight))
    if not pairs:
        return
    pairs.sort(key=lambda pair: pair[0].key)
    district = rng.weighted(pairs)
    town.districts.append({"конец": district.key, "год": year,
                           "чем живёт": district.culture})
    _tilt(town, district.tilt, 0.7)
    _mark(ctx, town, year, cat.NEW_PART,
          texts.district_born(rng, district))
    if district.key == "старый город":
        _leave_layer(ctx, rng, town, year, "перестройка")


# ---------------------------------------------------------------------------
# Занятия: как город теряет кормильца и ищет нового
# ---------------------------------------------------------------------------

def _trade_turn(ctx, rng, town, settlement, year: int, period: int) -> None:
    world = ctx.world
    region = world.regions.get(settlement.region_id)
    trade = cat.TRADES_BY_KEY.get(town.trade)
    if trade is None:
        new = _pick_trade(ctx, rng, settlement, region, avoid=())
        if new is not None:
            _take_trade(ctx, rng, town, new, year)
        return

    # Занятие кончается либо оттого, что кончилось само (жила, рыба,
    # граница), либо оттого, что город вырос и перерос его.
    risk = LOSS_RATE * period / 10.0
    if town.life == cat.FADING:
        risk *= 2.0
    if not _trade_fits(trade, region, settlement):
        risk *= 3.0
    if not rng.chance(min(0.5, risk)):
        # Большой город кормится не одним: второе занятие берётся редко.
        if settlement.population > 4000 and len(_live_trades(town)) < 3 \
                and rng.chance(0.06 * period / 10.0):
            new = _pick_trade(ctx, rng, settlement, region,
                              avoid=_live_trades(town))
            if new is not None:
                _take_trade(ctx, rng, town, new, year, keep=True)
        return

    for item in town.trades:
        if item.get("чем") == trade.key and not item.get("по"):
            item["по"] = year
    _mark(ctx, town, year, cat.LOST_TRADE,
          texts.mark_line(rng, cat.LOST_TRADE, trade.vuln))
    _event(ctx, town, settlement, year, cat.LOST_TRADE,
           "%s — %s." % (texts.cap(trade.vuln), trade.about))
    _tilt(town, {"устойчивость": -0.15, "богатство": -0.1}, 0.8)

    new = _pick_trade(ctx, rng, settlement, region,
                      avoid=_live_trades(town) + (trade.key,))
    if new is None or rng.chance(0.3):
        # Нового кормильца не нашлось — и город начинает мельчать.
        town.life = cat.FADING
        _add_trouble(ctx, rng, town, settlement, year, "отток людей")
        return
    _take_trade(ctx, rng, town, new, year)


def _take_trade(ctx, rng, town, trade, year: int, keep: bool = False) -> None:
    town.trades.append({"чем": trade.key, "с": year, "по": 0})
    town.weak = trade.vuln
    _tilt(town, trade.tilt, 0.6)
    if not keep:
        _mark(ctx, town, year, cat.NEW_TRADE,
              texts.mark_line(rng, cat.NEW_TRADE, trade.about))
        settlement = ctx.world.settlements.get(town.settlement_id)
        if settlement is not None:
            _event(ctx, town, settlement, year, cat.NEW_TRADE,
                   "Теперь город %s." % trade.about)


def _live_trades(town) -> tuple:
    return tuple(item["чем"] for item in town.trades if not item.get("по"))


def _pick_trade(ctx, rng, settlement, region, avoid=()):
    """Чем город может жить здесь и сейчас."""
    terrain = region.terrain if region is not None else races_mod.PLAIN
    rich = _region_goods(region)
    pairs = []
    for trade, weight in cat.fitting_trades(terrain, settlement.population,
                                            rich):
        if trade.key in avoid:
            continue
        if trade.key == cat.RULE and not settlement.is_capital:
            continue
        if trade.key == cat.MARCH and not settlement.polity_id:
            continue
        pairs.append((trade, weight))
    if not pairs:
        return None
    pairs.sort(key=lambda pair: pair[0].key)
    return rng.weighted(pairs)


def _trade_fits(trade, region, settlement) -> bool:
    terrain = region.terrain if region is not None else races_mod.PLAIN
    if trade.terrains and terrain not in trade.terrains:
        return False
    if trade.wants_good and trade.wants_good not in _region_goods(region):
        return False
    if trade.key == cat.RULE and not settlement.is_capital:
        return False
    return settlement.population >= trade.min_souls


def _region_goods(region) -> tuple:
    """Что эта земля вообще даёт — на глаз, по одному порогу."""
    if region is None:
        return ()
    yields = goods.region_yield(region)
    return tuple(good for good, value in yields.items() if value >= 0.35)


# ---------------------------------------------------------------------------
# Тяготы
# ---------------------------------------------------------------------------

def _troubles_turn(ctx, rng, town, settlement, year: int, period: int) -> None:
    # Старые тяготы решаются или перерастают в новые.
    for item in list(town.troubles):
        if item.get("по"):
            continue
        age = year - int(item.get("с", year))
        if age < TROUBLE_LIFE[0]:
            continue
        if age < TROUBLE_LIFE[1] and not rng.chance(0.3 * period / 10.0):
            continue
        _end_trouble(ctx, rng, town, settlement, item, year)

    live = [item for item in town.troubles if not item.get("по")]
    if len(live) >= MAX_TROUBLES:
        return
    if not rng.chance(TROUBLE_RATE * period / 10.0):
        return
    _add_trouble(ctx, rng, town, settlement, year)


def _add_trouble(ctx, rng, town, settlement, year: int, key: str = "") -> None:
    if key:
        trouble = cat.TROUBLES_BY_KEY.get(key)
    else:
        souls = settlement.population
        trades = _live_trades(town)
        pairs = []
        for item in cat.TROUBLES:
            if item.weight <= 0 or souls < item.min_souls:
                continue
            if item.wants_trade and not any(name in trades
                                            for name in item.wants_trade):
                continue
            if any(row["тягота"] == item.key and not row.get("по")
                   for row in town.troubles):
                continue
            pairs.append((item, item.weight))
        if not pairs:
            return
        pairs.sort(key=lambda pair: pair[0].key)
        trouble = rng.weighted(pairs)
    if trouble is None:
        return
    if any(row["тягота"] == trouble.key and not row.get("по")
           for row in town.troubles):
        return
    town.troubles.append({"тягота": trouble.key, "с": year, "по": 0,
                          "чем": ""})
    _tilt(town, trouble.tilt, 0.5)
    # В биографию идут не всякие тяготы: мелкое город и сам не помнит.
    if trouble.heavy or rng.chance(0.45):
        _mark(ctx, town, year, cat.TROUBLE_MARK,
              texts.trouble_start(rng, trouble))


def _end_trouble(ctx, rng, town, settlement, item, year: int) -> None:
    trouble = cat.TROUBLES_BY_KEY.get(item["тягота"])
    if trouble is None:
        item["по"] = year
        return
    chain = cat.TROUBLE_CHAIN.get(trouble.key, "")
    weights = [("уладилось", 1.4), ("привыкли и живут так", 1.0)]
    if chain:
        weights.append(("переросло в большее", 1.2))
    how = rng.weighted(weights)
    item["по"] = year
    item["чем"] = how
    if trouble.heavy or how == "переросло в большее":
        _mark(ctx, town, year, cat.TROUBLE_MARK, texts.trouble_end(rng, how))
    if how == "переросло в большее" and chain:
        _add_trouble(ctx, rng, town, settlement, year, chain)
    elif how == "уладилось":
        _tilt(town, {"устойчивость": 0.1}, 0.4)
    if trouble.heavy and how != "уладилось":
        # Тяжёлая тягота не просто портит настроение: от неё уезжают.
        settlement.population = max(40, int(settlement.population * 0.96))


# ---------------------------------------------------------------------------
# Слои и тайны
# ---------------------------------------------------------------------------

def _leave_layer(ctx, rng, town, year: int, why: str) -> None:
    rows = cat.LAYER_FROM.get(why) or cat.LAYERS
    layer = rng.choice(rows)
    if any(item["слой"] == layer for item in town.layers):
        return
    town.layers.append({"слой": layer, "год": year, "от чего": why})


def _known_layer(line: str) -> str:
    """Причина основания оставляет свой след; если он не из списка — свой."""
    return line


def _new_secret(ctx, rng, town, year: int) -> None:
    """Тайна города: одно и то же дело на пяти уровнях сразу."""
    have = {item["тайна"] for item in town.secrets}
    layers = {item["слой"] for item in town.layers}
    pairs = []
    for secret in cat.SECRETS:
        if secret.key in have:
            continue
        weight = secret.weight
        if secret.wants_layer:
            if secret.wants_layer not in layers:
                continue
            weight *= 2.5
        pairs.append((secret, weight))
    if not pairs:
        return
    pairs.sort(key=lambda pair: pair[0].key)
    secret = rng.weighted(pairs)
    town.secrets.append({
        "тайна": secret.key, "уровень": cat.RUMOUR,
        cat.PUBLIC: secret.public, cat.KNOWN: secret.known,
        cat.RUMOUR: secret.rumour, cat.HIDDEN: secret.hidden,
        cat.TRUTH: secret.truth, "год": year, "раскрыта": 0,
    })


# ---------------------------------------------------------------------------
# Уклад, сословия, силы
# ---------------------------------------------------------------------------

def _refresh_mix(world, town, settlement, shaken: bool = False) -> None:
    """Кто в городе живёт, на чём говорит и во что верит.

    Доли не выдумываются: главная — та, чья держава и чей народ город
    держит, остальное добирается из соседей по земле. Завоевание и
    переселение подмешивают чужое, и через четыреста лет город может
    стать другим, стоя на том же месте.
    """
    races = dict(town.mix.get("расы") or {})
    main = settlement.race_id
    if not races:
        races[main] = 1.0
    share = 0.12 if shaken else 0.04
    # Держава, которой город принадлежит, понемногу перетягивает уклад.
    polity = world.polities.get(settlement.polity_id)
    if polity is not None and polity.race_id and polity.race_id != main:
        races[polity.race_id] = races.get(polity.race_id, 0.0) + share
    races[main] = races.get(main, 0.0) + (0.02 if not shaken else 0.0)
    town.mix["расы"] = _normalized(races)

    folks = dict(town.mix.get("народы") or {})
    if settlement.folk_id:
        folks[settlement.folk_id] = folks.get(settlement.folk_id, 0.0) + 0.06
    town.mix["народы"] = _normalized(folks)

    faiths = dict(town.mix.get("веры") or {})
    if settlement.faith_id:
        faiths[settlement.faith_id] = faiths.get(settlement.faith_id,
                                                 0.0) + 0.08
    town.mix["веры"] = _normalized(faiths)


def _normalized(rows: dict) -> dict:
    total = sum(rows.values())
    if total <= 0:
        return {}
    # Мелочь ниже сотой доли не хранится: она только засоряет файл.
    out = {key: round(value / total, 3) for key, value in rows.items()
           if value / total >= 0.01}
    left = sum(out.values())
    if left <= 0:
        return {}
    return {key: round(value / left, 3) for key, value in out.items()}


def _refresh_estates(town, settlement) -> None:
    """Кто в этом городе есть и чего хочет."""
    trades = _live_trades(town)
    rows = ["пашенные"] if settlement.population < 1500 else []
    for trade_key in trades:
        trade = cat.TRADES_BY_KEY.get(trade_key)
        if trade is None:
            continue
        rows.extend(_ESTATES_BY_TRADE.get(trade_key, ()))
    if settlement.is_capital:
        rows.extend(("знать", "приказные"))
    if settlement.population >= 2600:
        rows.append("лихие")
    seen, out = set(), []
    for name in rows:
        if name in seen or name not in cat.ESTATE_WANTS:
            continue
        seen.add(name)
        out.append({"сословие": name, "хочет": cat.ESTATE_WANTS[name]})
    town.estates = out[:8]


_ESTATES_BY_TRADE = {
    cat.TILL: ("пашенные",),
    cat.TRADE_ROW: ("купцы", "пришлые"),
    cat.HARBOUR: ("купцы", "лихие", "пришлые"),
    cat.WARLIKE: ("воинские", "наёмные"),
    cat.MINE: ("работные", "купцы"),
    cat.CRAFT: ("ремесленники",),
    cat.HOLY: ("храмовые",),
    cat.RULE: ("знать", "приказные"),
    cat.MAGIC: ("чародеи",),
    cat.BOOK: ("книжные",),
    cat.MARCH: ("воинские", "пришлые"),
    cat.HUNT: ("пашенные",),
    cat.WOOD: ("работные",),
    cat.FISH_TOWN: ("пашенные",),
    cat.CARAVAN: ("купцы", "пришлые"),
    cat.PILGRIM: ("храмовые", "пришлые"),
    cat.COLONY: ("пришлые", "пашенные"),
    cat.GAOL: ("подневольные", "воинские"),
    cat.QUARRY: ("работные",),
    cat.FOUNDRY: ("работные", "ремесленники"),
}


def _refresh_trade_goods(world, town, settlement) -> None:
    """Чем город кормится, что вывозит и чего ему всегда не хватает.

    Доходы — это не «богатство числом», а перечень: серебро, рыба,
    оружие. Из него и растёт уязвимость: город на одной жиле падает
    вместе с ней, город на четырёх товарах переживёт потерю любого.
    """
    region = world.regions.get(settlement.region_id)
    rich = set(_region_goods(region))
    gives, takes = [], []
    for key in _live_trades(town):
        trade = cat.TRADES_BY_KEY.get(key)
        if trade is None:
            continue
        gives.extend(good for good in trade.gives if good in rich
                     or good == goods.METAL)
        takes.extend(trade.takes)
    # Земля даёт своё и без всякого занятия.
    gives.extend(good for good in rich if good in goods.STAPLES)
    town.incomes = sorted(set(gives))
    town.takes = sorted(set(takes) - set(gives))


def _refresh_forces(town, settlement) -> None:
    """Кто в городе может настоять на своём."""
    trades = _live_trades(town)
    souls = settlement.population
    out = []
    for force in cat.FORCES:
        if souls < force.min_souls:
            continue
        if force.wants_trade and not any(name in trades
                                         for name in force.wants_trade):
            continue
        out.append({"сила": force.key, "хочет": force.wants})
    town.forces = out[:6]


# ---------------------------------------------------------------------------
# Конец города
# ---------------------------------------------------------------------------

def _close_dead(ctx, rng, year: int) -> None:
    """Город оставили — биография закрывается последней вехой."""
    world = ctx.world
    for town in world.townships.values():
        if town.life in (cat.EMPTY,):
            continue
        settlement = world.settlements.get(town.settlement_id)
        if settlement is None or settlement.status == ACTIVE:
            continue
        when = settlement.ended.year if settlement.ended else year
        town.life = cat.EMPTY
        town.low_year = when
        for item in town.trades:
            if not item.get("по"):
                item["по"] = when
        for item in town.troubles:
            if not item.get("по"):
                item["по"] = when
                item["чем"] = "кончилось вместе с городом"
        _mark(ctx, town, when, cat.ABANDONED, texts.mark_line(rng,
                                                              cat.ABANDONED))
        if settlement.status == RUINED:
            _leave_layer(ctx, rng, town, when, "запустение")


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _war_marks(world) -> dict:
    """Какие города прямо сейчас видят войну своими стенами."""
    hit = {}
    for war_id in world.active_wars:
        war = world.wars.get(war_id)
        if war is None:
            continue
        for settlement_id in war.sieges:
            hit[settlement_id] = "осада"
        for settlement_id in war.taken_ids:
            hit.setdefault(settlement_id, "взят")
    return hit


def _calamity_regions(world) -> dict:
    """Какая беда сейчас идёт по какой земле."""
    out = {}
    for calamity_id in world.active_calamities:
        calamity = world.calamities.get(calamity_id)
        if calamity is None:
            continue
        for region_id in calamity.region_ids:
            out.setdefault(region_id, calamity.id)
    return out


def _mark(ctx, town, year: int, kind: str, line: str) -> None:
    if not line:
        return
    town.marks.append({"год": int(year), "вид": kind, "строка": line,
                       "души": _souls_now(ctx, town)})
    if len(town.marks) > MAX_MARKS:
        # Держим начало и конец: середину города и сами не помнят.
        town.marks = town.marks[:MAX_MARKS // 2] + town.marks[-MAX_MARKS // 2:]


def _souls_now(ctx, town) -> int:
    settlement = ctx.world.settlements.get(town.settlement_id)
    return settlement.population if settlement is not None else 0


def _has(town, kind: str) -> bool:
    return any(item.get("вид") == kind for item in town.marks)


def _daily_temper(town) -> None:
    """Нрав города за обычное десятилетие.

    Громкие случаи бьют по нраву сильно и редко, а по-настоящему его
    делает то, чем город живёт постоянно: чем кормится и что у него
    болит. И ещё одно — забывание: то, чего давно не было, само сползает
    к середине, и через триста лет мира воинственный город становится
    обычным.
    """
    for key in _live_trades(town):
        trade = cat.TRADES_BY_KEY.get(key)
        if trade is not None:
            _tilt(town, trade.tilt, TEMPER_DAILY / TEMPER_DRIFT)
    for item in town.troubles:
        if item.get("по"):
            continue
        trouble = cat.TROUBLES_BY_KEY.get(item["тягота"])
        if trouble is not None:
            _tilt(town, trouble.tilt, TEMPER_DAILY / TEMPER_DRIFT)
    for name in cat.TEMPERS:
        value = town.temper.get(name, 0.5)
        town.temper[name] = round(value + (0.5 - value) * TEMPER_FORGET, 3)


def _tilt(town, tilt: dict, force: float) -> None:
    """Нрав подстраивается под прожитое — медленно и без рывков."""
    if not tilt:
        return
    for name, shift in tilt.items():
        value = town.temper.get(name, 0.5)
        value += shift * TEMPER_DRIFT * force
        town.temper[name] = round(max(0.0, min(1.0, value)), 3)


def _event(ctx, town, settlement, year: int, kind: str, text: str) -> None:
    """Перелом в жизни города — в летопись; мелочь — только в биографию."""
    world = ctx.world
    date = ctx.date_in(ctx.rng("town-events", year), year)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="town_turn",
        title=texts.event_title(kind, settlement.name), text=text,
        importance=2, subjects=[settlement.id],
        region_id=settlement.region_id, race_id=settlement.race_id)
    town.event_ids.append(event.id)
    # Перелом в жизни города — след и для державы: он потом объяснит,
    # почему эта земля богатела или беднела.
    if settlement.polity_id:
        history.leave(world,
                      history.SCAR if kind == cat.LOST_TRADE
                      else history.FAVOUR,
                      year, settlement.polity_id, weight=0.2,
                      note="город по имени %s" % settlement.name,
                      event_id=event.id)


__all__ = ["upkeep"]
