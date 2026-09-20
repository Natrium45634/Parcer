# -*- coding: utf-8 -*-
"""Своды и легенды: как мир запоминает сам себя — и как ошибается.

Свод заводят в большом городе, при храме или при дворе, и ведут его
поколениями: один летописец сменяет другого, пока есть кому садиться за
стол. Всё это время в свод попадают события — но попадают не такими,
какими были: число павших растёт, заслугу приписывают тому, кто платит,
поражение пропускают, к победе прибавляют знамение.

Легенда живёт иначе. Она рождается из дела, которому уже полтора века,
и с каждым пересказом уходит от правды ещё на шаг: чудовище растёт,
герой оказывается королевской крови, а враг совершает злодейство,
которого не совершал.

В мире остаются оба слоя: то, что было, — в событиях; то, что об этом
рассказывают, — здесь.
"""

from __future__ import annotations

from .. import lore
from .. import narrative_lore as texts
from .. import races as races_mod
from ..models import ACTIVE

FOUND_RATE = 0.13           # шанс, что за такт где-то заведут новый свод
MAX_CODICES = 14
MIN_CITY = 2200
ENTRY_RATE = 0.55           # как часто свод вносит искажённую запись
HANDOVER_SPAN = (25, 70)    # сколько лет ведёт один летописец
BREAK_CHANCE = 0.18         # шанс, что преемника не найдётся
LOSS_RATE = 0.03
REFIND_RATE = 0.05

LEGEND_RATE = 0.11          # шанс, что за такт родится новая легенда
LEGEND_AGE = 150            # сколько лет делу должно быть
LEGEND_MEMORY = 1400        # и сколько лет его ещё помнят
DRIFT_RATE = 0.35           # и как часто её пересказывают по-новому
MAX_LEGENDS_PER_TICK = 1

# Из чего рождаются легенды: событие должно быть громким и с именем.
# Второе значение — как о нём говорят («о чудовище по имени …»), третье —
# насколько охотно об этом поют.
LEGEND_KINDS = {
    "monster_slain": ("чудовище", 3.0),
    "monster_exposed": ("нечисть", 1.6),
    "artifact_found": ("вещь", 1.6),
    "artifact_made": ("вещь", 1.2),
    "site_opened": ("место", 1.4),
    "war_end": ("война", 1.8),
    "calamity_end": ("беда", 1.6),
    "battle": ("битва", 1.5),
    "dynasty_change": ("престол", 1.0),
    "race_awakening": ("народ", 0.35),
}

# Как это зовётся в названии песни — уже в предложном падеже.
LEGEND_ABOUT = {
    "чудовище": "о чудовище по имени %s",
    "нечисть": "о нечисти по имени %s",
    "вещь": "о вещи по имени %s",
    "место": "о месте по имени %s",
    "война": "о войне, которую зовут «%s»",
    "беда": "о беде, которую звали «%s»",
    "битва": "о битве, которую зовут «%s»",
    "престол": "о смене крови на престоле державы %s",
    "народ": "о начале народа %s",
}


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("lore", year)
    scale = period / 10.0

    if len(world.active_codices) < MAX_CODICES \
            and rng.chance(FOUND_RATE * scale):
        _start_codex(ctx, year, rng)

    for codex_id in list(world.active_codices):
        _tend_codex(ctx, world.codices[codex_id], year, period, rng)
    for codex in list(world.codices.values()):
        if codex.status == lore.LOST and rng.chance(REFIND_RATE * scale):
            _refind(ctx, codex, year, rng)

    _legends(ctx, year, period, rng)


# ---------------------------------------------------------------------------
# Свод
# ---------------------------------------------------------------------------

def _start_codex(ctx, year: int, rng) -> None:
    world = ctx.world
    cities = [world.settlements[sid] for sid in world.active_settlements
              if world.settlements[sid].population >= MIN_CITY]
    if not cities:
        return
    city = rng.weighted([(item, float(item.population)) for item in cities])
    race = races_mod.RACES_BY_ID.get(city.race_id)
    if race is None:
        return
    polity = world.polities.get(city.polity_id)
    bias = rng.weighted(lore.BIAS_WEIGHT)
    keeper = _scribe(ctx, city, race, year, rng)
    date = ctx.date_in(rng, year)
    name = ctx.forge.unique(
        "codex", lambda: "%s %s" % (rng.choice(lore.CODEX_WORDS),
                                    rng.choice(lore.CODEX_OF)), rng)
    codex = world.add_codex(
        name=name, seat_id=city.id, region_id=city.region_id, started=date,
        polity_id=polity.id if polity is not None else "",
        faith_id=city.faith_id, bias=bias,
        accuracy=lore.accuracy_for(bias, 1), keeper_id=keeper.id,
        keepers=[{"figure": keeper.id, "from": year, "to": 0}])

    title, text = texts.codex_started(rng, codex, keeper, city)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="codex_started",
        title=title, text=text, importance=2, actors=[keeper.id],
        subjects=[codex.id, city.id], region_id=city.region_id,
        race_id=race.id)


def _scribe(ctx, city, race, year: int, rng):
    sex = "f" if rng.chance(0.35) else "m"
    return ctx.make_figure(
        rng, race, year, role="летописец", region_id=city.region_id,
        title="летописец" if sex == "m" else "летописица", sex=sex,
        home_id=city.id, epithet_chance=0.35,
        folk=ctx.world.folks.get(city.folk_id))


def _tend_codex(ctx, codex, year: int, period: int, rng) -> None:
    world = ctx.world
    city = world.settlements.get(codex.seat_id)
    if city is None or city.status != ACTIVE:
        _lose(ctx, codex, year, rng)
        return
    codex.span = max(codex.span, year - codex.started.year)

    keeper = world.figures.get(codex.keeper_id)
    if keeper is None or not keeper.alive_at(year):
        _handover(ctx, codex, city, year, rng)
        if codex.status != lore.KEPT:
            return
    if rng.chance(LOSS_RATE * (period / 10.0)):
        _lose(ctx, codex, year, rng)
        return
    if rng.chance(ENTRY_RATE * (period / 10.0)):
        _write(ctx, codex, year, rng)


def _handover(ctx, codex, city, year: int, rng) -> None:
    """Перо переходит к новому летописцу — или не переходит вовсе."""
    world = ctx.world
    if codex.keepers:
        codex.keepers[-1]["to"] = year
    if rng.chance(BREAK_CHANCE):
        date = ctx.date_in(rng, year)
        world.close_codex(codex, date, lore.BROKEN)
        title, text = texts.codex_broken(rng, codex, codex.span)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="codex_broken", title=title, text=text, importance=1,
            subjects=[codex.id], region_id=codex.region_id)
        return
    race = races_mod.RACES_BY_ID.get(city.race_id)
    if race is None:
        return
    keeper = _scribe(ctx, city, race, year, rng)
    codex.keeper_id = keeper.id
    codex.keepers.append({"figure": keeper.id, "from": year, "to": 0})
    # Чем больше рук вело свод, тем дальше он от того, что было.
    codex.accuracy = lore.accuracy_for(codex.bias, len(codex.keepers))
    if rng.chance(0.5):
        date = ctx.date_in(rng, year)
        span = rng.randint(*HANDOVER_SPAN)
        title, text = texts.codex_handover(rng, codex, keeper, span)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="codex_keeper", title=title, text=text, importance=1,
            actors=[keeper.id], subjects=[codex.id],
            region_id=codex.region_id)


def _write(ctx, codex, year: int, rng) -> None:
    """Свод вносит запись — и вносит её не совсем такой, какой было."""
    world = ctx.world
    event = _pick_event(world, codex, year, rng)
    if event is None:
        return
    if rng.chance(codex.accuracy):
        # Записал честно: такие записи в летопись о летописи не попадают.
        codex.entries.append({"year": year, "event": event.id, "kind": "верно"})
        return
    kind = lore.distortion_for(rng, codex.bias)
    codex.entries.append({"year": year, "event": event.id, "kind": kind})
    date = ctx.date_in(rng, year)
    title, text = texts.entry(rng, codex, event, kind)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="codex_entry",
        title=title, text=text, importance=1,
        subjects=[codex.id, event.id], region_id=codex.region_id)


def _pick_event(world, codex, year: int, rng):
    """О чём пишут: о громком и о недавнем, да и то не обо всём."""
    window = []
    for event in reversed(world.events):
        if event.date.year > year:
            continue
        if year - event.date.year > 60:
            break
        if event.importance < 3:
            continue
        if event.kind.startswith("codex"):
            continue
        window.append(event)
        if len(window) >= 40:
            break
    if not window:
        return None
    # Своё ближе: о делах своей земли пишут охотнее, чем о чужих.
    pairs = []
    for event in window:
        weight = 1.0 + 0.4 * (event.importance - 3)
        if event.region_id == codex.region_id:
            weight *= 2.5
        pairs.append((event, weight))
    return rng.weighted(pairs)


def _lose(ctx, codex, year: int, rng) -> None:
    world = ctx.world
    date = ctx.date_in(rng, year)
    if codex.keepers:
        codex.keepers[-1]["to"] = year
    world.close_codex(codex, date, lore.LOST)
    title, text = texts.codex_lost(rng, codex)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="codex_lost",
        title=title, text=text, importance=2, subjects=[codex.id],
        region_id=codex.region_id)


def _refind(ctx, codex, year: int, rng) -> None:
    """Утраченный свод находят — и век приходится переписывать."""
    world = ctx.world
    date = ctx.date_in(rng, year)
    span = max(1, year - (codex.ended.year if codex.ended else year))
    codex.status = lore.FOUND
    codex.notes.append("найден в %d году" % year)
    title, text = texts.codex_found(rng, codex, span)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="codex_found",
        title=title, text=text, importance=3, subjects=[codex.id],
        region_id=codex.region_id)


# ---------------------------------------------------------------------------
# Легенды
# ---------------------------------------------------------------------------

def _legends(ctx, year: int, period: int, rng) -> None:
    world = ctx.world
    scale = period / 10.0
    if rng.chance(LEGEND_RATE * scale):
        for _ in range(rng.randint(1, MAX_LEGENDS_PER_TICK)):
            _born(ctx, year, rng)
    for legend in list(world.legends.values()):
        if rng.chance(DRIFT_RATE * scale):
            _drift(ctx, legend, year, rng)


def _born(ctx, year: int, rng) -> None:
    """Дело, которому полтора века, становится песней."""
    world = ctx.world
    told = {legend.event_id for legend in world.legends.values()}
    pairs = []
    for event in world.events:
        if event.date.year > year - LEGEND_AGE:
            break
        age = year - event.date.year
        # Поют о том, что ещё помнят: о делах тысячелетней давности
        # складывают редко, о позавчерашних — не складывают вовсе.
        if age > LEGEND_MEMORY:
            continue
        if event.id in told or event.kind not in LEGEND_KINDS:
            continue
        about, weight = LEGEND_KINDS[event.kind]
        pairs.append(((event, about), weight * (1.0 + min(1.0, age / 900.0))))
    if not pairs:
        return
    event, about = rng.weighted(pairs)
    date = ctx.date_in(rng, year)
    subject = _about_line(world, event, about)
    name = ctx.forge.unique(
        "legend", lambda: "%s %s" % (rng.choice(lore.LEGEND_WORDS), subject),
        rng)
    subject_id = event.subjects[0] if event.subjects else (
        event.actors[0] if event.actors else "")
    legend = world.add_legend(
        name=name, born=date, event_id=event.id, about=about,
        subject_id=subject_id, race_id=event.race_id,
        region_id=event.region_id, truth=event.title)
    title, text = texts.legend_born(rng, legend, year - event.date.year)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="legend_born",
        title=title, text=text, importance=2,
        subjects=[legend.id, event.id], region_id=event.region_id,
        race_id=event.race_id)


def _about_line(world, event, about: str) -> str:
    """О чём песня — одной строкой в предложном падеже, без склонений.

    Имена в мире не склоняются, поэтому они всегда стоят после оборота:
    «о чудовище по имени Скарагорн», «о войне, которую зовут „Война за
    межу“». Так название песни читается и не ломает падежей.
    """
    pattern = LEGEND_ABOUT.get(about, "о деле по имени %s")
    if about == "народ":
        race = races_mod.RACES_BY_ID.get(event.race_id)
        return pattern % (race.gen_plural if race is not None else "древних")
    for entity_id in list(event.subjects) + list(event.actors):
        name = world.entity_name(entity_id)
        if name and name != entity_id:
            return pattern % name
    # Имени не нашлось — берём заголовок события, он всегда есть.
    return pattern % event.title


def _drift(ctx, legend, year: int, rng) -> None:
    """Каждый пересказ уводит легенду ещё на шаг от того, что было."""
    world = ctx.world
    used = {item.get("shift") for item in legend.shifts}
    left = [item for item in lore.shifts_for(legend.about) if item not in used]
    if not left:
        return
    shift = rng.choice(sorted(left))
    legend.shifts.append({"year": year, "shift": shift})
    legend.tellings += 1
    if not rng.chance(0.45):
        return
    date = ctx.date_in(rng, year)
    title, text = texts.legend_drift(rng, legend, shift)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="legend_drift",
        title=title, text=text, importance=1, subjects=[legend.id],
        region_id=legend.region_id, race_id=legend.race_id)


__all__ = ["upkeep"]
