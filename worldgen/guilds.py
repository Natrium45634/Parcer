# -*- coding: utf-8 -*-
"""Гильдии и торговые республики: третья сила между престолом и знатью.

Купец не воюет и не наследует корону, но он даёт в долг тому, кто воюет,
и покупает вольности у того, кто наследует. Гильдия — это касса, склады,
корабли и своё право, записанное грамотой; там, где она богатеет
быстрее, чем крепнет престол, город однажды объявляет себя вольным и
правит собой сам.

Здесь лежит устройство гильдий: из чего они растут, во что вкладывают
деньги и когда разоряются. События пишет ``systems/guilds.py``.
"""

from __future__ import annotations

from . import goods as goods_mod

# --- ремёсла -------------------------------------------------------------
# Каждое — уже в родительном падеже множественного числа: «гильдия
# солеваров». Склонять на ходу ничего не приходится.
CRAFTS = {
    goods_mod.GRAIN: "хлеботорговцев",
    goods_mod.MEAT: "скотопромышленников",
    goods_mod.FISH: "рыбников",
    goods_mod.TIMBER: "лесопромышленников",
    goods_mod.STONE: "камнерезов",
    goods_mod.METAL: "оружейников",
    goods_mod.SALT: "солеваров",
    goods_mod.WOOL: "суконщиков",
    goods_mod.FURS: "меховщиков",
    goods_mod.WINE: "виноторговцев",
    goods_mod.SPICE: "пряничников",
    goods_mod.GEMS: "самоцветчиков",
    goods_mod.REAGENTS: "травников",
}

GUILD_WORDS = ("Гильдия", "Братство", "Товарищество", "Складническое братство",
               "Торговый дом", "Компания", "Ряд")

SEA_WORDS = ("Гильдия мореходов", "Братство корабельщиков",
             "Товарищество дальнего пути")
BANK_WORDS = ("Гильдия менял", "Братство весов", "Товарищество заимодавцев")

# --- чем гильдия живёт ---------------------------------------------------
TRADE = "купеческая"
SEA = "мореходная"
CRAFT = "ремесленная"
BANK = "банкирская"
KINDS = (TRADE, SEA, CRAFT, BANK)

KIND_NOTES = {
    TRADE: "возит товар по дорогам и держит склады в трёх городах",
    SEA: "держит корабли и знает путь туда, куда прочие не ходят",
    CRAFT: "владеет мастерскими и правом клеймить чужую работу",
    BANK: "не возит ничего, но даёт в долг под залог податей",
}

# --- деньги --------------------------------------------------------------
FOUND_WEALTH = (40, 120)     # с чего начинают
ROUTE_INCOME = 9.0           # доход с действующего торгового пути за такт
CITY_INCOME = 0.0018         # и с души городского населения
WAR_LOSS = 0.22              # какую долю казны съедает война за такт
CHARTER_COST = 45.0          # во что обходится вольность при чужом дворе
COMPANY_COST = 90.0          # и наёмная рота
PEACE_COST = 160.0           # и выкупленный мир
REPUBLIC_WEALTH = 900.0      # с каких денег город заговаривает о вольности

# --- почему гильдия кончается -------------------------------------------
RUIN = "разорилась"
SEIZED = "казна отобрана престолом"
GONE = "город, где она сидела, опустел"


def guild_name(rng, kind: str, good: str, city) -> str:
    """Имя гильдии — по ремеслу или по городу, но всегда узнаваемое."""
    if kind == SEA:
        base = rng.choice(SEA_WORDS)
    elif kind == BANK:
        base = rng.choice(BANK_WORDS)
    else:
        craft = CRAFTS.get(good)
        if craft and rng.chance(0.6):
            return "%s %s" % (rng.choice(GUILD_WORDS), craft)
        base = rng.choice(GUILD_WORDS)
    return "%s города %s" % (base, city.name)


SHORE = ("побережье", "острова")


def kind_for(rng, world, polity, settlement) -> str:
    """Какого рода гильдия сложится в этом городе.

    Мореходная заводится только там, где есть куда выйти: в городе на
    берегу или в державе, которая уже возит товар морем.
    """
    options = [(TRADE, 2.0), (CRAFT, 1.4), (BANK, 0.8)]
    sea_routes = sum(1 for route_id in polity.routes
                     if route_id in world.routes and world.routes[route_id].by_sea)
    region = world.regions.get(settlement.region_id)
    shore = region is not None and (region.terrain in SHORE
                                    or getattr(region, "coastal", False))
    if sea_routes or shore:
        options.append((SEA, 1.4 + 0.5 * sea_routes + (1.0 if shore else 0.0)))
    return rng.weighted(options)


def main_good(polity) -> str:
    """Товар, на котором гильдия и поднялась."""
    if polity.surpluses:
        return polity.surpluses[0][0]
    if polity.goods:
        return sorted(polity.goods.items(), key=lambda kv: -kv[1][0])[0][0]
    return goods_mod.GRAIN


def income(world, guild, polity, period: int) -> float:
    """Сколько гильдия наживает за такт."""
    if polity is None:
        return 0.0
    routes = sum(1 for route_id in polity.routes
                 if route_id in world.active_routes)
    value = ROUTE_INCOME * routes + CITY_INCOME * max(0, polity.population)
    value *= 1.0 + 0.25 * len(guild.charters)      # вольности при чужих дворах
    if guild.kind == BANK:
        value *= 1.15
    return value * (period / 10.0)


def upkeep_cost(world, guild, polity, period: int) -> float:
    """И сколько теряет: война, голод, содержание складов."""
    if polity is None:
        return 0.0
    # Склады, писцы и охрана стоят денег и тогда, когда торга нет:
    # гильдия без путей проедает кассу и разоряется.
    loss = 0.06 * guild.wealth + 14.0
    if world.wars_of(polity, only_active=True):
        loss += WAR_LOSS * guild.wealth
    loss += 0.5 * polity.hunger * guild.wealth
    return loss * (period / 10.0)
