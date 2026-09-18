# -*- coding: utf-8 -*-
"""Законы наследования: кто займёт освободившийся престол.

Порядок наследования — это культура, а не техническая деталь. У людей
трон переходит старшему сыну, у дворфов — старшему в клане (брат раньше
сына), у тёмных эльфов правят женщины, у волколюдов власть берут с боем,
а лисолюды и вольные союзы выбирают правителя из глав знатных домов.
"""

from __future__ import annotations

from . import races as races_mod


class HeirChoice:
    """Результат поиска наследника."""

    __slots__ = ("figure", "relation", "needs_regent", "other_house", "law", "note")

    def __init__(self, figure, relation: str, needs_regent: bool = False,
                 other_house: bool = False, law: str = "", note: str = ""):
        self.figure = figure
        self.relation = relation
        self.needs_regent = needs_regent
        self.other_house = other_house
        self.law = law
        self.note = note


# ---------------------------------------------------------------------------
# Родство
# ---------------------------------------------------------------------------

def is_adult(figure, race, year: int) -> bool:
    return figure.age_at(year) >= race.adulthood


def living(world, ids, year: int) -> list:
    people = []
    for figure_id in ids:
        figure = world.figures.get(figure_id)
        if figure is not None and figure.alive_at(year):
            people.append(figure)
    return people


def children_of(world, figure, year: int) -> list:
    """Живые дети по старшинству."""
    if figure is None:
        return []
    people = living(world, figure.children, year)
    people.sort(key=lambda f: (f.birth_order, f.birth.ordinal, f.id))
    return people


def siblings_of(world, figure, year: int) -> list:
    """Живые братья и сёстры по старшинству."""
    if figure is None:
        return []
    parent = world.figures.get(figure.father_id) or world.figures.get(figure.mother_id)
    if parent is None:
        return []
    people = [f for f in children_of(world, parent, year) if f.id != figure.id]
    return people


def house_adults(world, house, race, year: int, sex: str = "") -> list:
    """Взрослые живые члены рода, старшие первыми."""
    if house is None:
        return []
    people = [f for f in world.house_members(house, alive_in_year=year)
              if is_adult(f, race, year)]
    if sex:
        people = [f for f in people if f.sex == sex]
    people.sort(key=lambda f: (f.birth.ordinal, f.id))
    return people


def relation_word(world, ruler, heir) -> str:
    """Кем приходится наследник прежнему правителю."""
    if ruler is None or heir is None:
        return "преемник" if (heir is None or heir.sex != "f") else "преемница"
    female = heir.sex == "f"
    if heir.father_id == ruler.id or heir.mother_id == ruler.id:
        return "дочь" if female else "сын"
    if ruler.father_id and heir.father_id == ruler.father_id:
        return "сестра" if female else "брат"
    if ruler.mother_id and heir.mother_id == ruler.mother_id:
        return "сестра" if female else "брат"

    parent = world.figures.get(heir.father_id) or world.figures.get(heir.mother_id)
    if parent is not None:
        if parent.father_id == ruler.id or parent.mother_id == ruler.id:
            return "внучка" if female else "внук"
        if ruler.father_id and parent.father_id == ruler.father_id:
            return "племянница" if female else "племянник"
    if heir.house_id and heir.house_id == ruler.house_id:
        return "родственница" if female else "родич"
    return "чужачка" if female else "чужак"


# ---------------------------------------------------------------------------
# Поиск наследника
# ---------------------------------------------------------------------------

def _first_adult_or_minor(world, people, race, year: int):
    """Первый подходящий: взрослый — сразу, малолетний — с регентом."""
    for figure in people:
        if is_adult(figure, race, year):
            return figure, False
    if people:
        return people[0], True
    return None, False


def _by_primogeniture(world, ruler, house, race, year: int, males_first: bool):
    order = []
    kids = children_of(world, ruler, year)
    if males_first:
        kids = ([f for f in kids if f.sex == "m"] + [f for f in kids if f.sex != "m"])
    order.extend(kids)

    # Внуки по линии умерших детей.
    for child_id in (ruler.children if ruler is not None else ()):
        child = world.figures.get(child_id)
        if child is not None and not child.alive_at(year):
            order.extend(children_of(world, child, year))

    brothers = siblings_of(world, ruler, year)
    if males_first:
        brothers = ([f for f in brothers if f.sex == "m"]
                    + [f for f in brothers if f.sex != "m"])
    order.extend(brothers)
    for brother in brothers:
        order.extend(children_of(world, brother, year))

    order.extend(house_adults(world, house, race, year))

    seen = set()
    unique = []
    for figure in order:
        if figure.id in seen or (ruler is not None and figure.id == ruler.id):
            continue
        seen.add(figure.id)
        unique.append(figure)
    return unique


def _by_matriline(world, ruler, house, race, year: int):
    order = [f for f in children_of(world, ruler, year) if f.sex == "f"]
    order += [f for f in siblings_of(world, ruler, year) if f.sex == "f"]
    for sister in list(order):
        order += [f for f in children_of(world, sister, year) if f.sex == "f"]
    order += house_adults(world, house, race, year, sex="f")
    order += house_adults(world, house, race, year, sex="m")   # только если женщин нет

    seen = set()
    unique = []
    for figure in order:
        if figure.id in seen or (ruler is not None and figure.id == ruler.id):
            continue
        seen.add(figure.id)
        unique.append(figure)
    return unique


def choose_heir(world, rng, polity, ruler, race, law: str, year: int):
    """Возвращает HeirChoice или None, если род пресёкся."""
    house = world.houses.get(polity.house_id)

    if law == races_mod.SENIORITY:
        people = house_adults(world, house, race, year)
        people = [f for f in people if ruler is None or f.id != ruler.id]
        if not people:
            return None
        heir = people[0]            # самый старший в роду
        return HeirChoice(heir, relation_word(world, ruler, heir), law=law)

    if law == races_mod.MATRILINEAL:
        # Прямая дочь наследует, даже если она ещё дитя: тогда правит регент.
        daughters = [f for f in children_of(world, ruler, year) if f.sex == "f"]
        if daughters:
            heir = daughters[0]
            return HeirChoice(heir, relation_word(world, ruler, heir),
                              needs_regent=not is_adult(heir, race, year), law=law)
        order = _by_matriline(world, ruler, house, race, year)
        heir, minor = _first_adult_or_minor(world, order, race, year)
        if heir is None:
            return None
        note = "" if heir.sex == "f" else "мужчина на престоле — дело неслыханное"
        return HeirChoice(heir, relation_word(world, ruler, heir),
                          needs_regent=minor, law=law, note=note)

    if law == races_mod.COUNCIL:
        people = house_adults(world, house, race, year)
        people = [f for f in people if ruler is None or f.id != ruler.id]
        if not people:
            return None
        pairs = []
        for figure in people:
            age = figure.age_at(year)
            prime = 1.0 + min(age / float(max(1, race.lifespan[0])), 1.0)
            pairs.append((figure, prime * rng.uniform(0.6, 1.6)))
        heir = rng.weighted(pairs)
        return HeirChoice(heir, relation_word(world, ruler, heir), law=law)

    if law == races_mod.ELECTIVE:
        pairs = []
        for other in world.houses_of_polity(polity):
            head = world.figures.get(other.head_id)
            if head is None or not head.alive_at(year) or not is_adult(head, race, year):
                continue
            if ruler is not None and head.id == ruler.id:
                continue
            weight = max(0.2, other.prestige) * (1.6 if other.id == polity.house_id else 1.0)
            # Выбирают своего: дом, чьего народа в державе не осталось
            # вовсе, голосов почти не собирает.
            if not polity.peoples.get(other.race_id, 0):
                weight *= 0.2
            pairs.append(((head, other), weight * rng.uniform(0.7, 1.4)))
        for figure in house_adults(world, house, race, year):
            if ruler is not None and figure.id == ruler.id:
                continue
            pairs.append(((figure, house), 1.2 * rng.uniform(0.7, 1.4)))
        if not pairs:
            return None
        heir, chosen_house = rng.weighted(pairs)
        return HeirChoice(heir, relation_word(world, ruler, heir),
                          other_house=(chosen_house.id != polity.house_id), law=law)

    if law == races_mod.STRENGTH:
        pairs = []
        for figure in house_adults(world, house, race, year):
            if ruler is not None and figure.id == ruler.id:
                continue
            pairs.append(((figure, house), 1.4 * _prowess(rng, figure, race, year)))
        for other in world.houses_of_polity(polity):
            if other.id == polity.house_id:
                continue
            head = world.figures.get(other.head_id)
            if head is None or not head.alive_at(year) or not is_adult(head, race, year):
                continue
            pairs.append(((head, other), max(0.3, other.prestige)
                          * _prowess(rng, head, race, year)))
        if not pairs:
            return None
        heir, chosen_house = rng.weighted(pairs)
        return HeirChoice(heir, relation_word(world, ruler, heir),
                          other_house=(chosen_house.id != polity.house_id), law=law)

    # Первородство — мужское или равное.
    males_first = law == races_mod.MALE_PRIMOGENITURE
    kids = children_of(world, ruler, year)
    if males_first:
        kids = [f for f in kids if f.sex == "m"] + [f for f in kids if f.sex != "m"]
    if kids:
        # Прямой наследник вступает в права даже ребёнком — при регенте.
        heir = kids[0]
        return HeirChoice(heir, relation_word(world, ruler, heir),
                          needs_regent=not is_adult(heir, race, year), law=law)

    order = _by_primogeniture(world, ruler, house, race, year, males_first)
    heir, minor = _first_adult_or_minor(world, order, race, year)
    if heir is None:
        return None
    return HeirChoice(heir, relation_word(world, ruler, heir),
                      needs_regent=minor, law=law)


def _prowess(rng, figure, race, year: int) -> float:
    """Боевая сила: молодость и зрелость вместе, дряхлость — против."""
    age = figure.age_at(year)
    peak = race.adulthood * 2.5
    if age <= peak:
        factor = 0.6 + 0.4 * (age / float(max(1, peak)))
    else:
        span = max(1.0, race.lifespan[1] - peak)
        factor = max(0.25, 1.0 - 0.7 * ((age - peak) / span))
    return factor * rng.uniform(0.5, 1.5)


def pick_regent(world, rng, polity, heir, race, year: int):
    """Регент при малолетнем правителе: мать, дядя или глава рода."""
    house = world.houses.get(polity.house_id)
    options = []
    mother = world.figures.get(heir.mother_id)
    father = world.figures.get(heir.father_id)
    for relative, weight in ((mother, 3.0), (father, 2.0)):
        if relative is not None and relative.alive_at(year) and is_adult(relative, race, year):
            options.append((relative, weight))
    for uncle in siblings_of(world, world.figures.get(heir.father_id), year):
        if is_adult(uncle, race, year):
            options.append((uncle, 1.5))
    head = world.figures.get(house.head_id) if house else None
    if head is not None and head.alive_at(year) and head.id != heir.id:
        options.append((head, 1.2))
    for figure in house_adults(world, house, race, year):
        if figure.id != heir.id:
            options.append((figure, 0.6))
    if not options:
        return None
    return rng.weighted(options)
