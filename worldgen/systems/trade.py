# -*- coding: utf-8 -*-
"""Торговля, дороги и нужда.

Держава раз в десятилетие считает своё хозяйство: что земля даёт и чего
не хватает. Дальше всё просто и по-человечески:

* **нехватка** — повод искать, у кого купить. Сосед с избытком того же
  товара становится торговым партнёром, если до него можно дойти;
* **путь** прокладывается по гексам, а не по прямой: в обход пиков,
  долинами и вдоль рек. Через хребет дороги нет — есть перевал;
* **договор** кормит обе стороны: у покупателя гаснет нужда, у продавца
  растут города на пути;
* **голод** приходит, когда еды нет и купить её не у кого. Он убивает.

Морской путь возможен, если у обеих держав есть порт: тогда хребты вообще
не помеха, и торгуют через полмира.
"""

from __future__ import annotations

from .. import history
from . import causes as causes_sys
from .. import goods as goods_mod
from .. import narrative_trade as texts
from ..models import ACTIVE
from ..world import RURAL_FACTOR

PACT_RATE = 0.30            # насколько охотно ищут, у кого купить
MAX_ROUTE_COST = 260.0      # дальше этого караван не ходит
SEA_ROUTE_COST = 420.0      # морем возят дальше
FAMINE_RATE = 0.30          # как часто голод переходит в мор
FAMINE_COOLDOWN = 120       # голод не приходит каждое десятилетие подряд
ROUTE_DECAY = 0.02          # годовой шанс, что путь заглохнет сам


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    world.refresh_populations()
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None:
            continue
        _count(world, polity)
    _seek_partners(ctx, year)
    _suffer(ctx, year, period)
    _decay(ctx, year, period)


# ---------------------------------------------------------------------------
# Счёт хозяйства
# ---------------------------------------------------------------------------

def _count(world, polity) -> None:
    balance = goods_mod.polity_balance(world, polity)
    # Привозное считается своим: договор для того и нужен.
    for route_id in polity.routes:
        route = world.routes.get(route_id)
        if route is None or route.status != ACTIVE:
            continue
        if route.buyer_id != polity.id:
            continue
        have, need = balance.get(route.good, (0, 0))
        balance[route.good] = (int(have + need * 0.45), need)
    polity.goods = {good: list(pair) for good, pair in balance.items()}
    polity.shortages = goods_mod.shortages(balance)
    polity.surpluses = goods_mod.surpluses(balance)


# ---------------------------------------------------------------------------
# Поиск партнёра и прокладка пути
# ---------------------------------------------------------------------------

def _seek_partners(ctx, year: int) -> None:
    world = ctx.world
    if len(world.active_polities) < 2:
        return
    rng = ctx.rng("trade", year)
    if not rng.chance(ctx.rate(PACT_RATE)):
        return

    hungry = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if not polity.shortages or not polity.capital_id:
            continue
        hungry.append((polity, polity.shortages[0][1]))
    if not hungry:
        return
    buyer = rng.weighted(hungry)
    need = buyer.shortages[0][0]

    sellers = []
    for polity_id in world.active_polities:
        if polity_id == buyer.id:
            continue
        other = world.polities[polity_id]
        if not other.capital_id:
            continue
        for good, value in other.surpluses:
            if good == need:
                sellers.append((other, value))
                break
    if not sellers:
        return
    seller = rng.weighted(sellers)

    if any(world.routes[rid].good == need
           and world.routes[rid].seller_id == seller.id
           for rid in buyer.routes if rid in world.routes):
        return

    path, cost, by_sea = _lay_route(ctx, seller, buyer)
    if path is None:
        return

    # Чем платит покупатель: своим избытком, если он есть.
    back = ""
    for good, _ in buyer.surpluses:
        if good != need:
            back = good
            break

    date = ctx.date_in(rng, year)
    route = world.add_route(
        seller_id=seller.id, buyer_id=buyer.id, good=need, back=back,
        by_sea=by_sea, path=path, length=len(path), cost=round(cost, 1),
        opened=date)
    seller.routes.append(route.id)
    buyer.routes.append(route.id)

    title, text = texts.trade_pact(rng, buyer, seller, need, back, len(path))
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="trade_pact",
        title=title, text=text, importance=3,
        subjects=[route.id, seller.id, buyer.id],
        region_id=buyer.region_ids[0] if buyer.region_ids else "")


def _lay_route(ctx, seller, buyer):
    """Прокладывает путь между столицами: сперва посуху, потом морем."""
    world = ctx.world
    if ctx.map is None or ctx.travel is None:
        # Без карты путь условен: считаем, что соседи торгуют, дальние — нет.
        near = set(seller.region_ids) | {
            rid for region_id in seller.region_ids
            for rid in world.regions[region_id].neighbors
            if region_id in world.regions}
        if not (near & set(buyer.region_ids)):
            return None, 0.0, False
        return [], 1.0, False

    start = _port_of(world, seller)
    goal = _port_of(world, buyer)
    if start < 0 or goal < 0:
        return None, 0.0, False

    path, cost = ctx.travel.route(start, goal, by_sea=False,
                                  limit=MAX_ROUTE_COST)
    if path is not None:
        return path, cost, False

    # Посуху не вышло — попробуем морем, если у обоих есть выход к воде.
    sea_start = _sea_gate(ctx, world, seller)
    sea_goal = _sea_gate(ctx, world, buyer)
    if sea_start < 0 or sea_goal < 0:
        return None, 0.0, False
    path, cost = ctx.travel.route(sea_start, sea_goal, by_sea=True,
                                  limit=SEA_ROUTE_COST)
    if path is None:
        return None, 0.0, False
    return path, cost, True


def _port_of(world, polity) -> int:
    settlement = world.settlements.get(polity.capital_id)
    if settlement is not None and settlement.hex_index >= 0:
        return settlement.hex_index
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is not None and settlement.hex_index >= 0:
            return settlement.hex_index
    return -1


def _sea_gate(ctx, world, polity) -> int:
    """Ближайшая к городам держава вода — откуда отходят корабли."""
    wmap = ctx.map.wmap
    for settlement_id in [polity.capital_id] + list(polity.settlement_ids):
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.hex_index < 0:
            continue
        for neighbor in wmap.neighbors(settlement.hex_index):
            if wmap.is_ocean(neighbor):
                return neighbor
    return -1


# ---------------------------------------------------------------------------
# Последствия нужды
# ---------------------------------------------------------------------------

def _suffer(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("trade", "need", year)
    for polity_id in list(world.active_polities):
        polity = world.polities.get(polity_id)
        if polity is None or not polity.goods:
            continue
        balance = {good: tuple(pair) for good, pair in polity.goods.items()}
        hunger = goods_mod.famine_pressure(balance)
        before = polity.hunger
        polity.hunger = round(hunger, 3)

        # Держава, которой вечно нечего есть, не голодает каждое
        # десятилетие — она просто не вырастает большой. Голод приходит,
        # когда становится хуже, чем было: закрылся путь, кончился урожай,
        # выросло население.
        worsened = hunger - before
        ready = year - polity.last_famine >= FAMINE_COOLDOWN
        striking = hunger > 0.45 and worsened > 0.05
        if ready and (striking or worsened > 0.15) \
                and rng.chance(min(0.7, hunger * FAMINE_RATE)):
            polity.last_famine = year
            _famine(ctx, polity, hunger, rng, year)
        elif polity.shortages and rng.chance(0.05):
            good = polity.shortages[0][0]
            title, text = texts.shortage(rng, polity, good)
            world.add_event(
                date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
                kind="shortage", title=title, text=text, importance=2,
                subjects=[polity.id],
                region_id=polity.region_ids[0] if polity.region_ids else "")


def _famine(ctx, polity, hunger: float, rng, year: int) -> None:
    """Голод: держава теряет людей там, где их нечем кормить."""
    world = ctx.world
    dead = 0
    for settlement_id in list(polity.settlement_ids):
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        share = hunger * rng.uniform(0.02, 0.09)
        loss = int(settlement.population * share)
        if loss <= 0:
            continue
        settlement.population = max(30, settlement.population - loss)
        dead += int(loss * RURAL_FACTOR)
    if dead < 100:
        return
    title, text = texts.famine(rng, polity, dead)
    # Голод редко приходит ниоткуда: оборванный подвоз, разорённая войной
    # округа, засушливые годы — всё это уже записано следами.
    roots, marks = [], []
    for kind in (history.HUNGER, history.DEPENDENCE, history.SCAR):
        for fact in world.facts_of(polity.id, year, kind)[:1]:
            marks.append(fact.id)
            if fact.event_id:
                roots.append(fact.event_id)
    event = world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="famine", title=title, text=text, importance=4,
        subjects=[polity.id],
        region_id=polity.region_ids[0] if polity.region_ids else "",
        race_id=polity.race_id, causes=roots, facts=marks,
        trace=history.trace_of(4))
    history.leave(world, history.HUNGER, year, polity.id, weight=0.9,
                  note="голод, унёсший %d душ" % dead, event_id=event.id)


def _decay(ctx, year: int, period: int) -> None:
    """Пути глохнут: война, разорение, или просто возить стало нечего."""
    world = ctx.world
    rng = ctx.rng("trade", "decay", year)
    for route_id in list(world.active_routes):
        route = world.routes.get(route_id)
        if route is None:
            continue
        seller = world.polities.get(route.seller_id)
        buyer = world.polities.get(route.buyer_id)
        gone = (seller is None or seller.status != ACTIVE
                or buyer is None or buyer.status != ACTIVE)
        if not gone and not rng.chance(ROUTE_DECAY * period / 10.0):
            continue
        date = ctx.date_in(rng, year)
        world.close_route(route, date, "торговля заглохла")
        # Для того, кто на этот подвоз привык рассчитывать, это не конец
        # пути, а начало нужды: последствие придёт через год-другой.
        causes_sys.after_route_end(ctx, route, year)
        if seller is not None and buyer is not None:
            title, text = texts.trade_break(rng, seller, buyer, route.good)
            world.add_event(
                date=date, era_index=world.era_index_at(year),
                kind="trade_break", title=title, text=text, importance=2,
                subjects=[route.id])
