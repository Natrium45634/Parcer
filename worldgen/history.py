# -*- coding: utf-8 -*-
"""Причинность: следы событий, отложенные последствия и дерево истории.

История здесь не набор случаев, а ткань. Крупное событие оставляет след —
факт, с которым живут державы, роды и народы: обиду, притязание, долг,
зависимость от чужого хлеба. След слабеет с годами, но пока он жив,
подсистемы читают его как готовый повод.

Кроме следа событие может оставить зерно — отложенное последствие с
годом всхода. Созрело зерно — обработчик решает, сбылось оно или
сорвалось; не дождалось — тихо угасает и остаётся в мире как
несбывшееся.

Модуль ничего не генерирует сам: он даёт подсистемам общий язык причин.
"""

from __future__ import annotations

# --- разборы следов ---------------------------------------------------

GRUDGE = "обида"                 # кровь, вероломство, оскорбление
CLAIM = "притязание"             # на землю, город или престол
LOSS = "утрата"                  # отнятый город, потерянная земля
DEBT = "долг"                    # услуга, выкуп, спасение
DEPENDENCE = "зависимость"       # чужой хлеб, чужое железо
GLORY = "слава"                  # победа, о которой помнят
SHAME = "позор"                  # поражение, о котором помнят
DREAD = "страх"                  # перед соседом, чудовищем, колдовством
OATH = "клятва"                  # слово, данное при свидетелях
KINSHIP = "родство"              # общая кровь двух домов
YOKE = "иго"                     # дань и чужое старшинство
SACRILEGE = "поругание"          # чужие руки на святыне
SCAR = "рубец"                   # память земли о бедствии
HUNGER = "голодная память"       # год, когда нечего было есть
FAVOUR = "приязнь"               # добро, которое помнят

KINDS = (GRUDGE, CLAIM, LOSS, DEBT, DEPENDENCE, GLORY, SHAME, DREAD, OATH,
         KINSHIP, YOKE, SACRILEGE, SCAR, HUNGER, FAVOUR)

# Сколько силы след теряет за сто лет. Притязание на землю переживает
# десяток поколений, голодная память стирается за век с небольшим.
FADE = {
    GRUDGE: 0.34, CLAIM: 0.11, LOSS: 0.14, DEBT: 0.46, DEPENDENCE: 0.55,
    GLORY: 0.22, SHAME: 0.28, DREAD: 0.42, OATH: 0.38, KINSHIP: 0.18,
    YOKE: 0.50, SACRILEGE: 0.13, SCAR: 0.09, HUNGER: 0.52, FAVOUR: 0.40,
}

# Какие следы толкают к войне, а какие удерживают от неё.
HOSTILE = (GRUDGE, CLAIM, LOSS, SHAME, YOKE, SACRILEGE)
FRIENDLY = (DEBT, KINSHIP, FAVOUR, OATH)


def fade_of(kind: str) -> float:
    return FADE.get(kind, 0.3)


# --- как след появляется ---------------------------------------------

def leave(world, kind: str, year: int, holder_id: str, about_id: str = "",
          weight: float = 1.0, note: str = "", event_id: str = "",
          place_id: str = "", parent_id: str = "", fade: float = 0.0):
    """Оставить след. Если такой уже есть — он освежается, а не двоится."""
    if not holder_id:
        return None
    weight = max(0.05, min(1.0, float(weight)))
    for old in world.facts_of(holder_id, year, kind, about_id):
        if old.place_id and place_id and old.place_id != place_id:
            continue
        # Новая обида поверх старой: след молодеет и тяжелеет, но не
        # бесконечно — память у держав не резиновая.
        old.weight = min(1.0, max(old.power(year), weight) + 0.25 * weight)
        old.year = int(year)
        if note:
            old.note = note
        if event_id:
            old.event_id = event_id
        return old
    return world.add_fact(kind=kind, year=year, holder_id=holder_id,
                          about_id=about_id, weight=weight, note=note,
                          event_id=event_id, place_id=place_id,
                          parent_id=parent_id,
                          fade=fade or fade_of(kind))


def settle(world, kind: str, year: int, holder_id: str, about_id: str = "",
           reason: str = "", place_id: str = "") -> int:
    """Закрыть следы: землю вернули, кровь простили, нужду закрыли."""
    count = 0
    for fact in world.facts_of(holder_id, year, kind, about_id):
        if place_id and fact.place_id and fact.place_id != place_id:
            continue
        world.close_fact(fact, year, reason)
        count += 1
    return count


def power(world, holder_id: str, kind: str, year: int, about_id: str = "") -> float:
    return world.fact_power(holder_id, kind, year, about_id)


def feelings(world, holder_id: str, about_id: str, year: int) -> tuple:
    """Одним проходом: сколько старого зла и сколько старого добра.

    Считается часто — раз в десятилетие для каждой пары соседей, — и
    потому идёт по следам напрямую, без сортировок и промежуточных
    списков.
    """
    cold = warm = 0.0
    for fact in world.live_facts(holder_id):
        if about_id and fact.about_id != about_id:
            continue
        if fact.kind in HOSTILE:
            cold += fact.power(year)
        elif fact.kind in FRIENDLY:
            warm += fact.power(year)
    return cold, warm


def hostility(world, holder_id: str, about_id: str, year: int) -> float:
    """Сколько старого зла накопилось у одной державы на другую."""
    return feelings(world, holder_id, about_id, year)[0]


def warmth(world, holder_id: str, about_id: str, year: int) -> float:
    """И сколько накопилось доброго."""
    return feelings(world, holder_id, about_id, year)[1]


def reasons_for(world, holder_id: str, about_id: str, year: int,
                limit: int = 3) -> list:
    """Живые следы одного против другого — от тяжёлого к лёгкому."""
    rows = []
    for fact in world.facts_of(holder_id, year, about_id=about_id):
        rows.append((fact.power(year), fact))
    rows.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [fact for _, fact in rows[:limit]]


# --- отложенные последствия -------------------------------------------

_HANDLERS = {}


def handler(kind: str):
    """Пометить обработчик зерна: @history.handler(«месть»)."""
    def wrap(func):
        _HANDLERS[kind] = func
        return func
    return wrap


def known_seed(kind: str) -> bool:
    return kind in _HANDLERS


def plant(world, kind: str, year: int, due: int, **kwargs):
    """Посеять отложенное последствие."""
    return world.add_seed(kind=kind, due=max(year + 1, int(due)), born=year,
                          **kwargs)


def sprout(ctx, seed, year: int):
    """Отдать зерно его обработчику.

    Обработчик отвечает одним из трёх: событие — зерно взошло; None —
    год не тот, подождём ещё; строка «угасло» — всходить уже нечему.
    """
    func = _HANDLERS.get(seed.kind)
    if func is None:
        return "угасло"
    return func(ctx, seed, year)


# --- сила следа --------------------------------------------------------

def trace_of(importance: int, extra: float = 0.0) -> float:
    """Насколько глубоко событие врезалось в мир, 0…1."""
    base = {1: 0.08, 2: 0.18, 3: 0.35, 4: 0.6, 5: 0.9}.get(int(importance), 0.2)
    return max(0.05, min(1.0, base + extra))


# --- дерево истории ----------------------------------------------------

def causes_of(world, event) -> list:
    """События-причины: прямые ссылки плюс те, что стоят за следами."""
    seen, out = set(), []
    for event_id in event.causes:
        if event_id in seen:
            continue
        seen.add(event_id)
        found = world.event(event_id)
        if found is not None:
            out.append(found)
    for fact_id in event.facts:
        fact = world.facts.get(fact_id)
        if fact is None or not fact.event_id or fact.event_id in seen:
            continue
        seen.add(fact.event_id)
        found = world.event(fact.event_id)
        if found is not None:
            out.append(found)
    return out


def effects_of(world, event) -> list:
    """Чем событие обернулось: зёрна, которые взошли."""
    out = []
    for seed_id in event.seeds:
        seed = world.seeds.get(seed_id)
        if seed is None:
            continue
        result = world.event(seed.result_id) if seed.result_id else None
        out.append((seed, result))
    return out


def roots(world, event, depth: int = 4) -> list:
    """Цепочка причин вверх: от события к его началу."""
    chain, current, seen = [], event, {event.id}
    for _ in range(max(1, depth)):
        parents = causes_of(world, current)
        if not parents:
            break
        parents.sort(key=lambda item: (-item.importance, item.date.ordinal))
        current = parents[0]
        if current.id in seen:
            break
        seen.add(current.id)
        chain.append(current)
    return chain


def depth_of(world, event, limit: int = 12) -> int:
    """Длина цепи причин — по ней видно, насколько история связна."""
    return len(roots(world, event, limit))


def tree_text(world, event, width: int = 2, depth: int = 3) -> list:
    """Текстовое дерево: причина — событие — последствия."""
    lines = []
    chain = roots(world, event, depth)
    for step, parent in enumerate(reversed(chain)):
        lines.append("%s%d: %s" % ("  " * step, parent.date.year, parent.title))
        lines.append("%s|" % ("  " * step))
    shift = "  " * len(chain)
    lines.append("%s%d: %s" % (shift, event.date.year, event.title))
    for fact_id in event.marks[:width + 1]:
        fact = world.facts.get(fact_id)
        if fact is None:
            continue
        lines.append("%s+-- след: %s%s" % (shift, fact.kind,
                                           (" — " + fact.note) if fact.note else ""))
    for seed, result in effects_of(world, event)[:width + 1]:
        if result is not None:
            lines.append("%s+-- через %d лет: %s"
                         % (shift, max(0, result.date.year - event.date.year),
                            result.title))
        elif seed.state == "ждёт":
            lines.append("%s+-- ждёт своего часа: %s (с %d года)"
                         % (shift, seed.kind, seed.due))
        else:
            lines.append("%s+-- %s: %s" % (shift, seed.state, seed.kind))
    return lines
