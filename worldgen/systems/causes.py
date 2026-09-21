# -*- coding: utf-8 -*-
"""Причины и последствия: как одно событие держит за руку другое.

Подсистема ничего не выдумывает сама. Она делает две вещи.

**Оставляет следы.** Проигранная война оставляет обиду, отнятый город —
притязание на него, торговый путь, которым держава кормится, —
зависимость от чужого хлеба. След слабеет с годами и однажды забывается,
но пока он жив, его читают поводы к войне, отношения держав и настроение
покорённых народов.

**Сеет зёрна.** Кроме следа событие может оставить отложенное
последствие с годом всхода: месть через полтораста лет, возврат земель
через восемь поколений, бунт в городе, который когда-то взяли силой.
Созрело зерно — подсистема пробует его прорастить; не вышло — зерно
ждёт дальше; вышло время — оно угасает, и это тоже записывается: мир, в
котором сбывается всё задуманное, выглядит ненастоящим.

Все зёрна прорастают через те же подсистемы, что и обычные события:
война объявляется войной, бунт поднимается бунтом. Новых способов
ломать мир здесь нет.
"""

from __future__ import annotations

from .. import goods as goods_mod
from .. import history
from .. import narrative_causes as texts
from ..models import ACTIVE

# Сколько зерно ждёт своего часа, если никто не задал иначе.
DEFAULT_WINDOW = 120

# Насколько слабым должен стать след, чтобы его сочли забытым.
FORGOTTEN = 0.03

# Какая доля несбывшегося попадает в летопись отдельной записью.
FAILED_SHARE = 0.22


# ---------------------------------------------------------------------------
# Годовой такт: всходы
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    world = ctx.world
    if not world.waiting_seeds:
        return
    # Список копируем: обработчики могут посеять новые зёрна.
    for seed in list(world.waiting_seeds):
        if seed.stale(year):
            _wither(ctx, seed, year)
            continue
        if not seed.ripe(year):
            continue
        rng = ctx.rng("causes", seed.id, year)
        # Зерно не обязано всходить в первый же год: у него есть окно.
        if not rng.chance(max(0.02, min(0.9, seed.chance))):
            continue
        result = history.sprout(ctx, seed, year)
        if result is None or result is False:
            continue
        if isinstance(result, str):
            world.settle_seed(seed, year, result)
            # Зерно отменили обстоятельства: мстить некому, город уже
            # чужой, народа в державе не осталось. Это тоже история.
            _remember_failure(ctx, seed, year)
            continue
        world.settle_seed(seed, year, "сбылось", getattr(result, "id", ""))


def _wither(ctx, seed, year: int) -> None:
    """Срок вышел, а зерно так и не взошло."""
    ctx.world.settle_seed(seed, year, "угасло")
    _remember_failure(ctx, seed, year)


def _remember_failure(ctx, seed, year: int) -> None:
    """Несбывшееся тоже оставляет след — слабый, но оставляет."""
    world = ctx.world
    fact = world.facts.get(seed.fact_id)
    rng = ctx.rng("causes", "fade", seed.id)
    if fact is not None:
        # Счёт остаётся неоплаченным, но с каждым несбывшимся сроком
        # он тускнеет: так обиды и забываются.
        fact.weight = max(0.05, fact.weight * 0.7)
    if seed.kind not in texts.FAILED_TITLES or not rng.chance(FAILED_SHARE):
        return
    holder = world.polities.get(seed.holder_id)
    if holder is None or holder.status != ACTIVE:
        return
    title, text = texts.unfulfilled(rng, seed.kind, max(1, year - seed.born),
                                    who=holder.name)
    event = world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="unfulfilled", title=title, text=text, importance=1,
        subjects=[holder.id],
        region_id=holder.region_ids[0] if holder.region_ids else "",
        race_id=holder.race_id,
        causes=[seed.event_id] if seed.event_id else [],
        facts=[seed.fact_id] if seed.fact_id else [],
        trace=history.trace_of(1))
    seed.result_id = event.id


# ---------------------------------------------------------------------------
# Медленный такт: что помнится, а что забылось
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    for fact in list(world.open_facts):
        if fact.power(year) <= FORGOTTEN:
            world.close_fact(fact, year, "забыто")
    _hunger_marks(ctx, year)
    _dependence_marks(ctx, year)


def _hunger_marks(ctx, year: int) -> None:
    """Голодный год помнится дольше самого голода."""
    world = ctx.world
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if polity.hunger < 0.2:
            continue
        history.leave(world, history.HUNGER, year, polity.id,
                      weight=min(1.0, polity.hunger),
                      note="в державе нечего есть")


def _dependence_marks(ctx, year: int) -> None:
    """Держава, которая живёт чужим подвозом, знает об этом."""
    world = ctx.world
    for route_id in list(world.active_routes):
        route = world.routes.get(route_id)
        if route is None or route.status != ACTIVE:
            continue
        buyer = world.polities.get(route.buyer_id)
        seller = world.polities.get(route.seller_id)
        if buyer is None or seller is None or buyer.status != ACTIVE:
            continue
        # Нехватка считается по своему хозяйству: привозной товар её не
        # закрывает, потому-то держава на подвоз и подсаживается.
        if not any(good == route.good for good, _ in (buyer.shortages or ())):
            continue
        age = year - (route.opened.year if route.opened else year)
        if age < 40:
            continue        # привычка к чужому товару складывается не сразу
        history.leave(world, history.DEPENDENCE, year, buyer.id, seller.id,
                      weight=min(1.0, 0.35 + age / 400.0),
                      place_id=route.id,
                      note="держава живёт чужим товаром: %s"
                           % goods_mod.GOOD_NOTES.get(route.good, route.good))


# ---------------------------------------------------------------------------
# Следы, которые оставляют подсистемы
# ---------------------------------------------------------------------------

def after_war(ctx, war, event, winner, loser, terms_map, year: int, rng) -> None:
    """Мир подписан — и с этого дня обе державы живут его последствиями."""
    world = ctx.world
    if event is not None:
        event.trace = history.trace_of(event.importance,
                                       extra=0.05 * min(3, war.scale))
    if winner is None or loser is None:
        return
    heavy = min(1.0, 0.3 + 0.12 * war.scale + 0.2 * bool(terms_map.get("cities")))

    grudge = history.leave(
        world, history.GRUDGE, year, loser.id, winner.id, weight=heavy,
        note="война по имени %s" % war.name,
        event_id=event.id if event is not None else "")
    history.leave(world, history.SHAME, year, loser.id, winner.id,
                  weight=0.5 * heavy, note="поражение в войне по имени %s"
                  % war.name, event_id=event.id if event is not None else "")
    history.leave(world, history.GLORY, year, winner.id, loser.id,
                  weight=heavy, note="победа в войне по имени %s" % war.name,
                  event_id=event.id if event is not None else "")

    # Месть не назначают на завтра: она ждёт нового поколения, а то и
    # нескольких. Чем тяжелее было поражение, тем вернее о нём вспомнят.
    if grudge is not None and loser.status == ACTIVE:
        delay = int(rng.bell(25, 260) * (1.3 - 0.4 * heavy))
        history.plant(world, "месть", year, year + max(12, delay),
                      window=DEFAULT_WINDOW + int(rng.uniform(0, 160)),
                      fact_id=grudge.id,
                      event_id=event.id if event is not None else "",
                      holder_id=loser.id, about_id=winner.id,
                      chance=min(0.8, 0.25 + 0.5 * heavy),
                      note="счёт за войну по имени %s" % war.name)

    if terms_map.get("tribute") or terms_map.get("vassal"):
        yoke = history.leave(world, history.YOKE, year, loser.id, winner.id,
                             weight=heavy,
                             note="дань после войны по имени %s" % war.name,
                             event_id=event.id if event is not None else "")
        history.plant(world, "иго", year, year + int(rng.bell(15, 90)),
                      window=140, fact_id=yoke.id if yoke else "",
                      event_id=event.id if event is not None else "",
                      holder_id=loser.id, about_id=winner.id, chance=0.4,
                      note="сбросить чужое старшинство")


def after_seizure(ctx, war, winner, loser, settlement, year: int, rng) -> None:
    """Город перешёл из рук в руки — и помнит об этом дольше людей."""
    world = ctx.world
    # Если победитель сам когда-то потерял этот город, притязание закрыто.
    history.settle(world, history.CLAIM, year, winner.id,
                   reason="город возвращён", place_id=settlement.id)
    history.settle(world, history.LOSS, year, winner.id,
                   reason="город возвращён", place_id=settlement.id)

    root = war.origin_id if war is not None else ""
    claim = history.leave(
        world, history.CLAIM, year, loser.id, winner.id, weight=0.85,
        place_id=settlement.id, event_id=root,
        note="город по имени %s взят силой" % settlement.name)
    history.leave(world, history.LOSS, year, loser.id, winner.id, weight=0.8,
                  place_id=settlement.id, event_id=root,
                  note="потерян город по имени %s" % settlement.name)
    if claim is not None and loser.status == ACTIVE:
        history.plant(world, "возврат", year,
                      year + int(rng.bell(30, 300)), window=200,
                      fact_id=claim.id, event_id=root, holder_id=loser.id,
                      about_id=winner.id, place_id=settlement.id,
                      chance=0.35, note="вернуть город по имени %s"
                      % settlement.name)
    # У самого города появляется своя память: чей он был раньше.
    if settlement.race_id and settlement.race_id != winner.race_id:
        history.plant(world, "восстание", year,
                      year + int(rng.bell(20, 220)), window=260,
                      fact_id=claim.id if claim is not None else "",
                      event_id=root,
                      holder_id=winner.id, about_id=settlement.race_id,
                      place_id=settlement.id, chance=0.3,
                      note="город по имени %s помнит прежнюю власть"
                           % settlement.name)


def after_calamity(ctx, calamity, event, year: int) -> None:
    """Земля помнит беду дольше, чем её помнят люди."""
    world = ctx.world
    weight = min(1.0, 0.25 + 0.16 * calamity.severity)
    for region_id in calamity.region_ids[:6]:
        history.leave(world, history.SCAR, year, region_id,
                      weight=weight, place_id=region_id,
                      note="беда по имени %s" % calamity.name,
                      event_id=event.id if event is not None else "")
    for polity_id in calamity.polity_ids[:8]:
        polity = world.polities.get(polity_id)
        if polity is None:
            continue
        history.leave(world, history.DREAD, year, polity.id,
                      weight=0.6 * weight,
                      note="беда по имени %s" % calamity.name,
                      event_id=event.id if event is not None else "")


def after_pact(ctx, pact, first, second, year: int) -> None:
    """Слово, данное при свидетелях."""
    world = ctx.world
    for holder, about in ((first, second), (second, first)):
        if holder is None or about is None:
            continue
        history.leave(world, history.OATH, year, holder.id, about.id,
                      weight=0.6, note="договор с державой по имени %s"
                      % about.name)


def after_pact_end(ctx, first, second, year: int) -> None:
    """Договор разошёлся сам собой: клятвы больше нет, обиды ещё нет."""
    world = ctx.world
    if first is None or second is None:
        return
    history.settle(world, history.OATH, year, first.id, second.id,
                   reason="договор расторгнут")
    history.settle(world, history.OATH, year, second.id, first.id,
                   reason="договор расторгнут")


def after_broken_pact(ctx, breaker, wronged, year: int, note: str = "") -> None:
    """И слово, которое не сдержали."""
    world = ctx.world
    if breaker is None or wronged is None:
        return
    history.settle(world, history.OATH, year, wronged.id, breaker.id,
                   reason="слово нарушено")
    history.settle(world, history.OATH, year, breaker.id, wronged.id,
                   reason="слово нарушено")
    history.leave(world, history.GRUDGE, year, wronged.id, breaker.id,
                  weight=0.75, note=note or "нарушенное слово")


def after_route_end(ctx, route, year: int, reason: str = "") -> None:
    """Путь оборвался. Для того, кто им кормился, это начало беды."""
    world = ctx.world
    buyer = world.polities.get(route.buyer_id)
    seller = world.polities.get(route.seller_id)
    if buyer is None or buyer.status != ACTIVE:
        return
    facts = [fact for fact in world.facts_of(buyer.id, year,
                                             history.DEPENDENCE,
                                             route.seller_id)
             if not fact.place_id or fact.place_id == route.id]
    if not facts:
        return
    fact = facts[0]
    rng = ctx.rng("causes", "break", route.id)
    history.plant(world, "разрыв", year, year + rng.randint(1, 4), window=12,
                  fact_id=fact.id, holder_id=buyer.id,
                  about_id=seller.id if seller is not None else "",
                  place_id=route.good, chance=0.7,
                  note="без подвоза: %s"
                       % goods_mod.GOOD_NOTES.get(route.good, route.good))


# ---------------------------------------------------------------------------
# Всходы: что делает каждое зерно
# ---------------------------------------------------------------------------

@history.handler("месть")
def _grow_revenge(ctx, seed, year: int):
    world = ctx.world
    avenger = world.polities.get(seed.holder_id)
    foe = world.polities.get(seed.about_id)
    if avenger is None or foe is None or avenger.status != ACTIVE \
            or foe.status != ACTIVE:
        return "угасло"
    fact = world.facts.get(seed.fact_id)
    if fact is None or fact.power(year) < 0.12:
        return "угасло"
    from . import war as war_sys
    return war_sys.settle_score(ctx, avenger, foe, year, "revenge",
                                seed=seed, fact=fact)


@history.handler("возврат")
def _grow_reclaim(ctx, seed, year: int):
    world = ctx.world
    claimant = world.polities.get(seed.holder_id)
    holder = world.polities.get(seed.about_id)
    settlement = world.settlements.get(seed.place_id)
    if claimant is None or holder is None or claimant.status != ACTIVE \
            or holder.status != ACTIVE:
        return "угасло"
    if settlement is None or settlement.status != ACTIVE:
        return "угасло"
    if settlement.polity_id != holder.id:
        return "угасло"          # город уже сменил хозяина без них
    fact = world.facts.get(seed.fact_id)
    if fact is None or fact.power(year) < 0.1:
        return "угасло"
    from . import war as war_sys
    return war_sys.settle_score(ctx, claimant, holder, year, "reclaim",
                                seed=seed, fact=fact)


@history.handler("иго")
def _grow_yoke(ctx, seed, year: int):
    world = ctx.world
    vassal = world.polities.get(seed.holder_id)
    overlord = world.polities.get(seed.about_id)
    if vassal is None or overlord is None or vassal.status != ACTIVE \
            or overlord.status != ACTIVE:
        return "угасло"
    if vassal.tribute_to != overlord.id and vassal.overlord_id != overlord.id:
        return "угасло"          # иго кончилось само
    if vassal.population < overlord.population * 0.5:
        return None              # пока не с чем подниматься
    from . import war as war_sys
    fact = world.facts.get(seed.fact_id)
    return war_sys.settle_score(ctx, vassal, overlord, year, "yoke",
                                seed=seed, fact=fact)


@history.handler("восстание")
def _grow_revolt(ctx, seed, year: int):
    world = ctx.world
    polity = world.polities.get(seed.holder_id)
    if polity is None or polity.status != ACTIVE:
        return "угасло"
    race_id = seed.about_id
    if polity.peoples.get(race_id, 0) <= 0:
        return "угасло"          # некому вспоминать
    settlement = world.settlements.get(seed.place_id)
    if settlement is not None and settlement.status != ACTIVE:
        return "угасло"
    from . import nations as nations_sys
    return nations_sys.stir_revolt(ctx, polity, race_id, year,
                                   note=seed.note, seed=seed)


@history.handler("разрыв")
def _grow_break(ctx, seed, year: int):
    world = ctx.world
    buyer = world.polities.get(seed.holder_id)
    if buyer is None or buyer.status != ACTIVE:
        return "угасло"
    fact = world.facts.get(seed.fact_id)
    if fact is None or fact.closed:
        return "угасло"
    good = seed.place_id or goods_mod.GRAIN
    # Путь мог открыться заново — тогда беды не будет.
    for route_id in buyer.routes:
        route = world.routes.get(route_id)
        if route is not None and route.status == ACTIVE and route.good == good:
            return "угасло"
    rng = ctx.rng("causes", "supply", seed.id)
    seller = world.polities.get(seed.about_id)
    buyer.hunger = min(1.0, buyer.hunger + (0.25 if good in goods_mod.STAPLES
                                            else 0.08))
    title, text = texts.supply_break(
        rng, buyer, goods_mod.gen(good),
        blamed=seller.name if seller is not None else "")
    if seller is not None:
        history.leave(world, history.GRUDGE, year, buyer.id, seller.id,
                      weight=0.45, note="обоз, который не пришёл")
        from .. import diplomacy as dip
        dip.set_relation(buyer, seller,
                         dip.relation(buyer, seller.id) - 0.18)
    event = world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="supply_break", title=title, text=text, importance=3,
        subjects=[buyer.id] + ([seller.id] if seller is not None else []),
        region_id=buyer.region_ids[0] if buyer.region_ids else "",
        race_id=buyer.race_id,
        causes=[seed.event_id] if seed.event_id else [],
        facts=[fact.id], trace=history.trace_of(3))
    history.leave(world, history.HUNGER, year, buyer.id,
                  weight=0.7, note="год без подвоза", event_id=event.id)
    return event
