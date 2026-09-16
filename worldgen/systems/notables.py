# -*- coding: utf-8 -*-
"""Люди, оставшиеся в памяти не престолом.

Летопись, в которой есть только короли и полководцы, читается однообразно.
Здесь в мир приходят те, кто его менял иначе: звездочёты, летописцы,
лекари, зодчие, законники, рудознатцы, чародеи, сказители, картографы —
и полководцы, чьё имя осталось не из-за короны.

Каждый разыгранный предмет труда мир помнит: звёздный атлас составляют
один раз. Когда у ремесла кончаются несделанные работы, оно перестаёт
рождать имена — и в летописи не появится второй такой же человек.
"""

from __future__ import annotations

from .. import narrative_notables as texts
from .. import races as races_mod

NOTABLE_RATE = 0.055        # годовая вероятность, что появится такое имя
MIN_CITY_POPULATION = 900   # в деревне учёному взяться неоткуда
CRAFT_KEYS = tuple(sorted(texts.CRAFTS))


def tick(ctx, year: int) -> None:
    world = ctx.world
    if not world.active_settlements:
        return
    rng = ctx.rng("notables", year)
    era_index = world.era_index_at(year)
    # В первые эпохи грамотных мало: некому ни считать звёзды, ни писать своды.
    urge = 0.25 + 0.3 * era_index
    if not rng.chance(ctx.rate(NOTABLE_RATE) * urge):
        return

    home = _pick_home(ctx, rng)
    if home is None:
        return
    race = races_mod.RACES_BY_ID.get(home.race_id)
    if race is None:
        return

    craft = _pick_craft(ctx, rng, race, era_index)
    if craft is None:
        return
    subject = _take_subject(ctx, rng, craft)
    if subject is None:
        return

    sex = "f" if rng.chance(0.42) else "m"
    title = texts.craft_title(craft, sex)
    figure = ctx.make_figure(
        rng, race, year, role=craft, region_id=home.region_id,
        title=title, sex=sex, epithet_chance=0.35)
    figure.home_id = home.id
    figure.notes.append("труд: %s" % subject)

    region = world.regions.get(home.region_id)
    event_title, text = texts.deed(rng, figure, craft, subject, region)
    importance = 3 if craft in ("чародей", "полководец", "законник") else 2
    event = world.add_event(
        date=ctx.date_in(rng, year), era_index=era_index, kind="notable_deed",
        title=event_title, text=text, importance=importance,
        actors=[figure.id], subjects=[home.id], region_id=home.region_id,
        race_id=race.id)
    figure.deeds.append(event.id)


def _pick_home(ctx, rng):
    """Где рождаются такие люди: чем больше город, тем вероятнее."""
    world = ctx.world
    pairs = []
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.population < MIN_CITY_POPULATION:
            continue
        weight = float(settlement.population) ** 0.8
        if settlement.is_capital:
            weight *= 1.8
        pairs.append((settlement, weight))
    if not pairs:
        return None
    return rng.weighted(pairs)


def _pick_craft(ctx, rng, race, era_index: int):
    """Какое ремесло: народ тянется к своему, но не только к нему."""
    weights = {key: 1.0 for key in CRAFT_KEYS}
    for trait in race.traits:
        for craft in texts.TRAIT_CRAFTS.get(trait, ()):
            weights[craft] = weights.get(craft, 1.0) * 3.2
    # Чародеи и звездочёты появляются не в первый век, законники — позже всех.
    if era_index < 1:
        weights["законник"] *= 0.15
        weights["картограф"] *= 0.3
    if era_index < 2:
        weights["летописец"] *= 0.5

    # Ремесло, у которого кончились несделанные работы, больше не берут.
    done = ctx.notable_done
    pairs = []
    for craft, weight in weights.items():
        left = len(texts.subjects_of(craft)) - len(done.get(craft, ()))
        if left <= 0:
            continue
        pairs.append((craft, weight * (0.4 + left / 12.0)))
    if not pairs:
        return None
    return rng.weighted(pairs)


def _take_subject(ctx, rng, craft: str):
    """Берёт ещё не сделанную работу и помечает её сделанной."""
    used = ctx.notable_done.setdefault(craft, set())
    left = [subject for subject in texts.subjects_of(craft)
            if subject not in used]
    if not left:
        return None
    subject = rng.choice(sorted(left))
    used.add(subject)
    return subject
