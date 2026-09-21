# -*- coding: utf-8 -*-
"""Политика между державами: что их сближает и что разводит.

Здесь только правила и числа; тексты живут в narrative_diplomacy.py,
годовой ход — в systems/diplomacy.py.

**Отношение** — одно число от −1 (кровная вражда) до +1 (братство). Оно
не выдумывается, а складывается из того, что в мире уже есть: кто какого
народа, кто во что верит, кто с кем торгует, у кого общий враг, чья
знать переженилась, кто кому платит дань и сколько раз они воевали.
Каждое слагаемое видно и может быть названо вслух — потому в летописи
и можно написать, *почему* два дома сошлись.

**Расовая склонность.** Дворф с человеком сговорится скорее, чем с
эльфом: между горой и лесом старые счёты. Высшие эльфы смотрят на
тёмных как на позор рода, зверолюды держатся своих, а со злыми расами
не договаривается никто. Это не запрет, а вес на чаше: союз дворфов с
эльфами возможен — просто он должен чем-то перевесить.

**Договоры** идут лесенкой: сначала ненападение, потом торговый, потом
брачный, и лишь потом союз. Через ступень не перепрыгивают, а разрывают
в обратном порядке.
"""

from __future__ import annotations

from . import history
from . import recall
from . import races as races_mod
from .models import ACTIVE

# --- виды договоров ------------------------------------------------------
TRUCE = "ненападение"
TRADE = "торговый"
MARRIAGE = "брачный"
ALLIANCE = "союз"

PACT_ORDER = (TRUCE, TRADE, MARRIAGE, ALLIANCE)
PACT_NAMES = {
    TRUCE: "договор о ненападении",
    TRADE: "торговый договор",
    MARRIAGE: "брачный союз домов",
    ALLIANCE: "союзный договор",
}
# Какое отношение нужно, чтобы дойти до такой ступени.
PACT_THRESHOLD = {TRUCE: 0.15, TRADE: 0.25, MARRIAGE: 0.36, ALLIANCE: 0.46}
# Ниже какого отношения договор рвут.
PACT_BREAK = {TRUCE: -0.15, TRADE: -0.05, MARRIAGE: 0.05, ALLIANCE: 0.15}

# --- виды союзов ---------------------------------------------------------
DEFENSIVE = "оборонительный"
OFFENSIVE = "наступательный"
HOLY = "священный"
TRADE_LEAGUE = "торговый"

LEAGUE_NAMES = {
    DEFENSIVE: "оборонительный союз", OFFENSIVE: "наступательный союз",
    HOLY: "священный союз", TRADE_LEAGUE: "торговый союз",
}


# ---------------------------------------------------------------------------
# Расовая склонность
# ---------------------------------------------------------------------------

# Между большими родами народов. Пары симметричны: порядок не важен.
GROUP_AFFINITY = {
    ("Люди", "Люди"): 0.12,
    ("Люди", "Дворфы"): 0.18,
    ("Люди", "Эльфы"): 0.02,
    ("Люди", "Полулюди"): 0.00,
    ("Люди", "Зверолюды"): -0.18,
    ("Люди", "Злые расы"): -0.75,
    ("Дворфы", "Дворфы"): 0.22,
    ("Дворфы", "Эльфы"): -0.42,
    ("Дворфы", "Полулюди"): -0.05,
    ("Дворфы", "Зверолюды"): -0.22,
    ("Дворфы", "Злые расы"): -0.85,
    ("Эльфы", "Эльфы"): 0.10,
    ("Эльфы", "Полулюди"): -0.08,
    ("Эльфы", "Зверолюды"): -0.10,
    ("Эльфы", "Злые расы"): -0.80,
    ("Полулюди", "Полулюди"): 0.14,
    ("Полулюди", "Зверолюды"): 0.02,
    ("Полулюди", "Злые расы"): -0.65,
    ("Зверолюды", "Зверолюды"): 0.10,
    ("Зверолюды", "Злые расы"): -0.45,
    ("Злые расы", "Злые расы"): -0.20,
}

# Уточнения там, где внутри одного рода народов всё не так гладко.
RACE_AFFINITY = {
    ("elf", "high_elf"): 0.30,
    ("elf", "dark_elf"): -0.55,
    ("high_elf", "dark_elf"): -0.80,
    ("dwarf", "dark_elf"): -0.30,       # и без того вражда, но эти хуже всех
    ("human", "high_elf"): -0.08,       # высокомерие замечают
    ("catfolk", "foxkin"): 0.18,
    ("wolfkin", "foxkin"): -0.22,
    ("wolfkin", "bearkin"): 0.16,
    ("wolfkin", "catfolk"): -0.12,
    ("birdkin", "catfolk"): -0.15,      # у одних гнёзда, у других когти
    ("birdkin", "bearkin"): 0.08,
    ("dwarf", "birdkin"): -0.10,        # гора и высота не делят неба
    ("lizardfolk", "serpentfolk"): 0.20,
    ("toadfolk", "serpentfolk"): -0.15,
    ("turtlefolk", "crabfolk"): 0.18,
}


def _pair(first: str, second: str) -> tuple:
    return (first, second) if first <= second else (second, first)


def racial_affinity(first_race, second_race) -> float:
    """Насколько два народа расположены друг к другу сами по себе."""
    if first_race.id == second_race.id:
        return 0.35                      # свои со своими сходятся легче всего
    exact = RACE_AFFINITY.get(_pair(first_race.id, second_race.id))
    group = GROUP_AFFINITY.get(_pair(first_race.group, second_race.group), -0.05)
    if exact is None:
        return group
    # Уточнение не отменяет общее правило, а поправляет его.
    return max(-1.0, min(1.0, group * 0.4 + exact))


def can_deal(first_race, second_race) -> bool:
    """Со злыми расами договоров не заключают вовсе."""
    if first_race.is_evil or second_race.is_evil:
        return False
    return first_race.builds_states and second_race.builds_states


# ---------------------------------------------------------------------------
# Из чего складывается отношение
# ---------------------------------------------------------------------------

class Index:
    """Подённые заготовки для политики: считать их для каждой пары дорого.

    Мир в полтораста держав — это тысячи пар за такт, и каждая пара
    спрашивает одно и то же: кто с кем торгует, кто с кем воюет, чьи
    дома переженились. Всё это считается один раз за такт.
    """

    __slots__ = ("routes", "foes", "kin", "allies")

    def __init__(self, world):
        self.routes = {}
        for route_id in world.active_routes:
            route = world.routes[route_id]
            key = _pair(route.seller_id, route.buyer_id)
            self.routes[key] = self.routes.get(key, 0) + 1

        self.foes = {}
        for war_id in world.active_wars:
            war = world.wars[war_id]
            self.foes.setdefault(war.attacker_id, set()).add(war.defender_id)
            self.foes.setdefault(war.defender_id, set()).add(war.attacker_id)

        self.allies = {}
        for pact_id in world.active_pacts:
            pact = world.pacts[pact_id]
            if pact.kind != ALLIANCE:
                continue
            self.allies.setdefault(pact.first_id, set()).add(pact.second_id)
            self.allies.setdefault(pact.second_id, set()).add(pact.first_id)

        # Браки правящих домов: кто на ком женат, по державам.
        self.kin = {}
        spouses = {}
        for polity_id in world.active_polities:
            polity = world.polities[polity_id]
            house = world.houses.get(polity.house_id)
            if house is None:
                continue
            for figure_id in house.members[-90:]:
                figure = world.figures.get(figure_id)
                if figure is not None and figure.spouse_id:
                    spouses[figure_id] = (polity_id, figure.spouse_id)
        for figure_id, (polity_id, spouse_id) in spouses.items():
            other = spouses.get(spouse_id)
            if other is None or other[0] == polity_id:
                continue
            key = _pair(polity_id, other[0])
            self.kin[key] = self.kin.get(key, 0) + 1


def _live_routes(world, first, second, index=None) -> int:
    if index is not None:
        return index.routes.get(_pair(first.id, second.id), 0)
    count = 0
    for route_id in world.active_routes:
        route = world.routes[route_id]
        if {route.seller_id, route.buyer_id} == {first.id, second.id}:
            count += 1
    return count


def _kin_houses(world, first, second, index=None) -> int:
    """Сколько браков связывает правящие дома двух держав."""
    if index is not None:
        return index.kin.get(_pair(first.id, second.id), 0)
    house_first = world.houses.get(first.house_id)
    house_second = world.houses.get(second.house_id)
    if house_first is None or house_second is None:
        return 0
    members = set(house_first.members)
    count = 0
    for figure_id in house_second.members[-90:]:
        figure = world.figures.get(figure_id)
        if figure is not None and figure.spouse_id in members:
            count += 1
    return count


def _shared_enemy(world, first, second, year: int, index=None) -> int:
    """Общий враг — самый быстрый способ подружиться."""
    if index is not None:
        ours = index.foes.get(first.id, set())
        theirs = index.foes.get(second.id, set())
    else:
        def foes(polity):
            out = set()
            for war in world.wars_of(polity, only_active=True):
                out.add(war.defender_id if war.attacker_id == polity.id
                        else war.attacker_id)
            return out
        ours, theirs = foes(first), foes(second)
    return len((ours & theirs) - {first.id, second.id})


def _mutual_allies(world, first, second, index=None) -> int:
    if index is not None:
        return len(index.allies.get(first.id, set())
                   & index.allies.get(second.id, set()))

    def allies(polity):
        out = set()
        for pact in world.pacts_of(polity):
            if pact.kind == ALLIANCE:
                out.add(pact.other(polity.id))
        return out
    return len(allies(first) & allies(second))


def _past_wars(world, first, second, year: int) -> tuple:
    """Сколько войн было между ними и как давно была последняя."""
    count, last = 0, 0
    for war in world.wars_of(first):
        if second.id not in (war.attacker_id, war.defender_id):
            continue
        count += 1
        if war.end is not None:
            last = max(last, war.end.year)
    return count, last


def _neighbours(world, first, second) -> bool:
    reach = set(first.region_ids)
    for region_id in first.region_ids:
        region = world.regions.get(region_id)
        if region is not None:
            reach.update(region.neighbors)
    return bool(reach & set(second.region_ids))


def reasons(world, first, second, year: int, index=None) -> list:
    """Все слагаемые отношения — списком (название, вес).

    Возвращается именно список, а не число: летописи нужно знать, почему
    державы сошлись или разошлись, а не только насколько.
    """
    out = []
    race_first = races_mod.get_race(first.race_id)
    race_second = races_mod.get_race(second.race_id)

    value = racial_affinity(race_first, race_second)
    if abs(value) >= 0.05:
        out.append(("родство народов" if value > 0 else "рознь народов", value))

    faith_first = world.faiths.get(first.faith_id)
    faith_second = world.faiths.get(second.faith_id)
    if faith_first is not None and faith_second is not None:
        if faith_first.id == faith_second.id:
            out.append(("общая вера", 0.32))
        else:
            gap = abs(faith_first.alignment - faith_second.alignment)
            if faith_first.parent_id == faith_second.id \
                    or faith_second.parent_id == faith_first.id:
                out.append(("ересь и материнская вера", -0.30))
            elif gap >= 3:
                out.append(("несовместимые веры", -0.28))
            elif gap >= 1:
                out.append(("разная вера", -0.10))
        if faith_first.forbidden or faith_second.forbidden:
            out.append(("вера под запретом у соседа", -0.25))

    routes = _live_routes(world, first, second, index)
    if routes:
        out.append(("давняя торговля", min(0.30, 0.12 * routes)))

    kin = _kin_houses(world, first, second, index)
    if kin:
        out.append(("родство правящих домов", min(0.35, 0.14 * kin)))

    enemies = _shared_enemy(world, first, second, year, index)
    if enemies:
        out.append(("общий враг", min(0.40, 0.22 * enemies)))

    # Союзник моего союзника — почти свой: на этом и держатся большие союзы.
    mutual = _mutual_allies(world, first, second, index)
    if mutual:
        out.append(("общие союзники", min(0.24, 0.12 * mutual)))
    if first.league_id and first.league_id == second.league_id:
        out.append(("общий союз", 0.20))

    wars, last = _past_wars(world, first, second, year)
    if wars:
        fresh = max(0.0, 1.0 - (year - last) / 300.0) if last else 1.0
        out.append(("пролитая кровь", -min(0.55, 0.16 * wars) * (0.35 + fresh)))

    if first.tribute_to == second.id or first.overlord_id == second.id:
        out.append(("дань чужой короне", -0.35))
    elif second.tribute_to == first.id or second.overlord_id == first.id:
        out.append(("своё старшинство", 0.18))

    if _neighbours(world, first, second):
        out.append(("общая межа", -0.10))

    # Историческая инерция: подписанный мир не превращает вражду в
    # дружбу. Следы прошлого — отнятые города, нарушенные клятвы,
    # спасённые обозы — тянут отношения к себе, пока не выветрятся.
    cold, warm = history.feelings(world, first.id, second.id, year)
    if cold > 0.05:
        out.append(("старые счёты", -min(0.50, 0.30 * cold)))
    if warm > 0.05:
        out.append(("старое добро", min(0.35, 0.26 * warm)))

    ruler_first = world.figures.get(first.ruler_id)
    ruler_second = world.figures.get(second.ruler_id)
    if ruler_first is not None and ruler_second is not None:
        gap = abs(int(getattr(ruler_first, "alignment", 0) or 0)
                  - int(getattr(ruler_second, "alignment", 0) or 0))
        if gap >= 4:
            out.append(("несхожий нрав государей", -0.18))
        elif gap <= 1:
            out.append(("схожий нрав государей", 0.10))
        # Личное: что эти двое помнят друг о друге и о чужой державе.
        personal = (recall.attitude(world, ruler_first, second.id, year)
                    + recall.attitude(world, ruler_second, first.id, year)) / 2.0
        personal += 0.5 * recall.bond_worth(
            world.bond_between(ruler_first.id, ruler_second.id))
        if personal <= -0.18:
            out.append(("личные счёты государей", max(-0.45, personal * 0.6)))
        elif personal >= 0.18:
            out.append(("личная приязнь государей", min(0.35, personal * 0.5)))

    from . import nations as pol
    if pol.is_harsh(second.policy) and faith_first is not None \
            and faith_first.alignment >= 1:
        out.append(("чужие законы о народах", -0.22))

    return out


def target_relation(world, first, second, year: int) -> float:
    """К чему отношение стремится сейчас."""
    return max(-1.0, min(1.0, sum(weight for _, weight in
                                  reasons(world, first, second, year))))


def relation(polity, other_id: str) -> float:
    return float((polity.relations or {}).get(other_id, 0.0))


def set_relation(first, second, value: float) -> None:
    """Отношение держав всегда взаимно: обиду помнят обе стороны."""
    value = max(-1.0, min(1.0, value))
    first.relations[second.id] = round(value, 3)
    second.relations[first.id] = round(value, 3)


def relation_word(value: float) -> str:
    for threshold, word in ((0.6, "братство"), (0.35, "дружба"),
                            (0.15, "доброе соседство"), (-0.15, "ровное"),
                            (-0.35, "холод"), (-0.6, "вражда")):
        if value >= threshold:
            return word
    return "кровная вражда"


# ---------------------------------------------------------------------------
# Договоры
# ---------------------------------------------------------------------------

def pact_kind_for(value: float, current: str = "") -> str:
    """Какая ступень договора по плечу при таком отношении.

    Через ступень не перепрыгивают: сперва перестают воевать, потом
    начинают торговать, потом роднятся и только потом клянутся в союзе.
    """
    reachable = [kind for kind in PACT_ORDER if value >= PACT_THRESHOLD[kind]]
    if not reachable:
        return ""
    highest = reachable[-1]
    if not current:
        return PACT_ORDER[0] if PACT_ORDER[0] in reachable else ""
    index = PACT_ORDER.index(current)
    if PACT_ORDER.index(highest) <= index:
        return ""                       # выше не поднимаются
    return PACT_ORDER[index + 1]


def league_kind(world, members) -> str:
    """Чем держится союз: верой, торговлей, страхом или расчётом."""
    faiths = {polity.faith_id for polity in members if polity.faith_id}
    if len(faiths) == 1 and list(faiths)[0]:
        return HOLY
    routes = 0
    for index, first in enumerate(members):
        for second in members[index + 1:]:
            routes += _live_routes(world, first, second)
    if routes >= len(members):
        return TRADE_LEAGUE
    threats = sum(len(world.wars_of(polity, only_active=True))
                  for polity in members)
    return DEFENSIVE if threats else OFFENSIVE


def strongest(world, members):
    """Кто в союзе первый среди равных."""
    best, best_weight = None, -1.0
    for polity in sorted(members, key=lambda p: p.id):
        weight = float(polity.population) ** 0.6 * (1.0 + 0.1 * polity.wars_won)
        if weight > best_weight:
            best, best_weight = polity, weight
    return best


def alive(world, polity) -> bool:
    return polity is not None and polity.status == ACTIVE
