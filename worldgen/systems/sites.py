# -*- coding: utf-8 -*-
"""Места истории: курганы, руины, поля битв, клады и те, кто в них лезет.

Ничего из этого не придумано под игру — всё осталось от того, что уже
случилось. Полководца похоронили с его мечом; город сожгли, и от него
остались стены; казну зарыли, когда держава падала, и не вернулись за
ней. Место помнит год, имя и содержимое, а через век-другой кто-нибудь
находит вход — и тогда в мир возвращаются и вещи, и то, что их стерегло.
"""

from __future__ import annotations

from .. import narrative_sites as texts
from .. import races as races_mod
from .. import sites as sites_mod
from ..models import ACTIVE, RUINED

RUIN_CHANCE = 0.55          # какая доля погибших городов оставляет руины
FIELD_CHANCE = 0.30         # и какая доля больших сражений — поле с костями
SETTLE_RATE = 0.03          # шанс, что в пустое место кто-то вселится за такт
DELVE_RATE = 0.022          # и что в него кто-то полезет
MIN_FAME_FOR_TOMB = 1.0


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("sites", year)
    _mark_ruins(ctx, year, rng)
    _mark_fields(ctx, year, rng)
    _hide_hoards(ctx, year, rng)
    scale = period / 10.0
    for site in list(world.sites.values()):
        if site.status == sites_mod.COLLAPSED:
            continue
        # В поле с костями не селятся — селятся под крышей и под землёй.
        if site.status == sites_mod.UNTOUCHED \
                and site.kind != sites_mod.FIELD \
                and rng.chance(SETTLE_RATE * scale):
            _settle(ctx, site, year, rng)
            continue
        if site.status not in (sites_mod.UNTOUCHED, sites_mod.INHABITED):
            continue
        # Чем глубже и страшнее место, тем реже находится охотник в него
        # лезть: о таких местах рассказывают, а не ходят туда.
        urge = DELVE_RATE * scale * max(0.25, 1.35 - 0.22 * site.depth)
        if rng.chance(urge):
            _delve(ctx, site, year, rng)


# ---------------------------------------------------------------------------
# Место возникает
# ---------------------------------------------------------------------------

def bury(ctx, figure, year: int, date, artifacts=(), deeds: str = "",
         rich: float = 1.0):
    """Ставит курган над тем, кого стоит помнить, и кладёт в него вещи."""
    world = ctx.world
    region_id = figure.origin_region
    if not region_id:
        home = world.settlements.get(figure.home_id)
        region_id = home.region_id if home is not None else ""
    if not region_id or region_id not in world.regions:
        return None
    rng = ctx.rng("sites", "tomb", figure.id)
    race = races_mod.RACES_BY_ID.get(figure.race_id)
    kind = sites_mod.CRYPT if (race is not None and rng.chance(0.35)) \
        else sites_mod.TOMB
    words = sites_mod.CRYPT_WORDS if kind == sites_mod.CRYPT \
        else sites_mod.TOMB_WORDS
    name = _unique_name(ctx, rng, "%s %s" % (rng.choice(words), figure.given_name))
    site = world.add_site(
        kind=kind, name=name, region_id=region_id, created=date,
        figure_id=figure.id, polity_id=_polity_of(world, figure),
        guards=rng.choice(sites_mod.GUARDS[kind]),
        riches=sites_mod.riches_for(rng, kind, rich),
        hex_index=_hex_of(ctx, region_id, rng))
    site.depth = sites_mod.depth_for(kind, site.riches, bool(site.guards))
    for artifact in artifacts:
        world.put_artifact(artifact, "в кургане", date, site=site,
                           how="положена в могилу хозяина")
    site.story = texts.story_line(site, figure=figure, deeds=deeds)

    title, text = texts.tomb_raised(ctx.rng("sites", "text", site.id), site,
                                    figure, deeds)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="site_tomb",
        title=title, text=text, importance=2, actors=[figure.id],
        subjects=[site.id], region_id=region_id, race_id=figure.race_id)
    return site


def _blamed(world, settlement) -> str:
    """Какая беда сожгла этот город — по его же записи о конце.

    Место должно помнить, что его оставило: через тысячу лет по этой
    памяти государь и найдёт дорогу сюда (systems/legacy.py).
    """
    reason = settlement.end_reason or ""
    if "бедствия" not in reason and "беды" not in reason:
        return ""
    for calamity in world.calamities.values():
        if calamity.name and calamity.name in reason:
            return calamity.id
    return ""


def _mark_ruins(ctx, year: int, rng) -> None:
    """Погибший город оставляет по себе руины — и не пустые."""
    world = ctx.world
    known = {site.settlement_id for site in world.sites.values()
             if site.settlement_id}
    for settlement in world.settlements.values():
        if settlement.status != RUINED or settlement.id in known:
            continue
        if settlement.ended is None or year - settlement.ended.year > 60:
            continue
        if not rng.chance(RUIN_CHANCE):
            known.add(settlement.id)
            continue
        date = settlement.ended
        name = _unique_name(ctx, rng, "%s %s" % (rng.choice(sites_mod.RUIN_WORDS),
                                                 settlement.name))
        site = world.add_site(
            kind=sites_mod.RUIN, name=name, region_id=settlement.region_id,
            created=date, settlement_id=settlement.id,
            polity_id=settlement.polity_id,
            calamity_id=_blamed(world, settlement),
            guards=rng.choice(sites_mod.GUARDS[sites_mod.RUIN]),
            riches=sites_mod.riches_for(rng, sites_mod.RUIN,
                                        0.6 + settlement.population / 9000.0),
            hex_index=settlement.hex_index)
        site.depth = sites_mod.depth_for(sites_mod.RUIN, site.riches, True)
        site.story = texts.story_line(site, settlement=settlement)
        known.add(settlement.id)
        years = max(1, date.year - settlement.founded.year)
        title, text = texts.ruin_left(rng, site, settlement, years)
        world.add_event(
            date=date, era_index=world.era_index_at(date.year), kind="site_ruin",
            title=title, text=text, importance=2, subjects=[site.id],
            region_id=site.region_id, race_id=settlement.race_id)


def _mark_fields(ctx, year: int, rng) -> None:
    """Большое сражение оставляет по себе поле, которое не пашут."""
    world = ctx.world
    known = {site.battle_id for site in world.sites.values() if site.battle_id}
    for battle in world.battles.values():
        if battle.id in known or not battle.decisive:
            continue
        if year - battle.date.year > 60 or not battle.region_id:
            continue
        known.add(battle.id)
        if battle.deaths < 900 or not rng.chance(FIELD_CHANCE):
            continue
        name = _unique_name(ctx, rng,
                            lambda: texts.field_name(rng, world, battle))
        site = world.add_site(
            kind=sites_mod.FIELD, name=name, region_id=battle.region_id,
            created=battle.date, battle_id=battle.id,
            calamity_id=battle.calamity_id,
            guards=rng.choice(sites_mod.GUARDS[sites_mod.FIELD]),
            riches=sites_mod.riches_for(rng, sites_mod.FIELD,
                                        0.5 + battle.deaths / 9000.0))
        site.depth = sites_mod.depth_for(sites_mod.FIELD, site.riches, False)
        site.story = texts.story_line(site, battle=battle)
        title, text = texts.field_left(rng, site, battle)
        world.add_event(
            date=battle.date, era_index=world.era_index_at(battle.date.year),
            kind="site_field", title=title, text=text, importance=1,
            subjects=[site.id, battle.id], region_id=site.region_id)


def _hide_hoards(ctx, year: int, rng) -> None:
    """Павшая держава оставляет по себе зарытую казну."""
    world = ctx.world
    known = {site.polity_id for site in world.sites.values()
             if site.kind == sites_mod.HOARD and site.polity_id}
    for polity in world.polities.values():
        if polity.status == ACTIVE or polity.id in known:
            continue
        if polity.ended is None or year - polity.ended.year > 60:
            continue
        known.add(polity.id)
        if len(polity.settlement_ids) < 2 or not rng.chance(0.45):
            continue
        hide_hoard(ctx, polity, year, polity.ended, rng)


def hide_hoard(ctx, polity, year: int, date, rng):
    """Падающая держава прячет казну — и не возвращается за ней."""
    world = ctx.world
    region_id = polity.region_ids[0] if polity.region_ids else ""
    if not region_id or region_id not in world.regions:
        return None
    name = _unique_name(ctx, rng, "%s %s" % (rng.choice(sites_mod.HOARD_WORDS),
                                             polity.name))
    site = world.add_site(
        kind=sites_mod.HOARD, name=name, region_id=region_id, created=date,
        polity_id=polity.id,
        guards=rng.choice(sites_mod.GUARDS[sites_mod.HOARD]),
        riches=sites_mod.riches_for(rng, sites_mod.HOARD,
                                    0.7 + len(polity.settlement_ids) / 8.0),
        hex_index=_hex_of(ctx, region_id, rng))
    site.depth = sites_mod.depth_for(sites_mod.HOARD, site.riches, False)
    site.story = texts.story_line(site)
    title, text = texts.hoard_left(rng, site)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="site_hoard",
        title=title, text=text, importance=1, subjects=[site.id, polity.id],
        region_id=region_id, race_id=polity.race_id)
    return site


# ---------------------------------------------------------------------------
# Место живёт
# ---------------------------------------------------------------------------

def _settle(ctx, site, year: int, rng) -> None:
    """Пустое место недолго остаётся пустым."""
    world = ctx.world
    site.status = sites_mod.INHABITED
    if not site.guards or site.guards == sites_mod.NOBODY:
        site.guards = rng.choice(sites_mod.GUARDS.get(site.kind, ("тьма",)))
    site.depth = min(5, site.depth + 1)
    date = ctx.date_in(rng, year, site.created
                       if site.created.year == year else None)
    title, text = texts.site_settled(rng, site, site.guards)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="site_settled",
        title=title, text=text, importance=1, subjects=[site.id],
        region_id=site.region_id)


def _delve(ctx, site, year: int, rng) -> None:
    """Кто-то находит вход и спускается. Наружу выходят не всегда."""
    world = ctx.world
    seeker = _seeker(ctx, site, year, rng)
    if seeker is None:
        return
    date = ctx.date_in(rng, year, site.created
                       if site.created.year == year else None)
    years = max(1, year - site.created.year)

    # Чем глубже место, тем вернее оно оставит вошедшего при себе.
    doom = 0.10 + 0.13 * site.depth
    if site.status == sites_mod.INHABITED:
        doom += 0.12
    if rng.chance(min(0.8, doom)):
        world.schedule_death(seeker, date, "не вернулся из подземелья"
                             if seeker.sex == "m" else "не вернулась из подземелья")
        site.notes.append("%d: не вернулся %s" % (year, seeker.name))
        title, text = texts.site_failed(rng, site, seeker)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="site_failed",
            title=title, text=text, importance=2, actors=[seeker.id],
            subjects=[site.id], region_id=site.region_id)
        return

    taken = []
    for artifact_id in list(site.artifact_ids):
        artifact = world.artifacts.get(artifact_id)
        if artifact is None or artifact.status != ACTIVE:
            continue
        world.put_artifact(artifact, "у владельца", date, figure=seeker,
                           how="вынесена из места по имени %s" % site.name)
        site.artifact_ids.remove(artifact_id)
        taken.append(artifact)
    # Всё не выносят никогда: что-то не нашли, что-то не смогли поднять.
    riches = int(site.riches * rng.uniform(0.35, 0.85))
    site.riches = max(0, site.riches - riches)
    site.status = sites_mod.ROBBED
    site.opened = date
    site.opened_by = seeker.id

    haul = ""
    if riches > 0:
        haul = "добра на %d" % riches
    if taken:
        haul = ("%s и вещь по имени %s" % (haul, taken[0].name)) if haul \
            else "вещь по имени %s" % taken[0].name
    title, text = texts.site_entered(rng, site, seeker, years, haul,
                                     trouble=rng.chance(0.45))
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="site_opened",
        title=title, text=text, importance=3 if taken else 2,
        actors=[seeker.id], subjects=[site.id] + [a.id for a in taken],
        region_id=site.region_id)
    for artifact in taken:
        artifact.deeds.append(event.id)


def _seeker(ctx, site, year: int, rng):
    """Тот, кто полезет: местный житель, которому нечего терять."""
    world = ctx.world
    cities = [world.settlements[sid] for sid in world.active_settlements
              if world.settlements[sid].region_id == site.region_id]
    if not cities:
        cities = [world.settlements[sid] for sid in world.active_settlements]
    if not cities:
        return None
    city = rng.choice(sorted(cities, key=lambda s: s.id))
    race = races_mod.RACES_BY_ID.get(city.race_id)
    if race is None:
        return None
    sex = "f" if rng.chance(0.38) else "m"
    return ctx.make_figure(
        rng, race, year, role="искатель", region_id=city.region_id,
        title="", sex=sex, home_id=city.id, epithet_chance=0.65,
        folk=world.folks.get(city.folk_id))


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _polity_of(world, figure) -> str:
    home = world.settlements.get(figure.home_id)
    return home.polity_id if home is not None else ""


def _hex_of(ctx, region_id: str, rng) -> int:
    if ctx.map is None:
        return -1
    return ctx.map.place(region_id, rng, kind="site")


def _unique_name(ctx, rng, name) -> str:
    """name — либо готовая строка, либо способ придумать ещё одну."""
    maker = name if callable(name) else (lambda: name)
    return ctx.forge.unique("site", maker, rng)


__all__ = ["upkeep", "bury", "hide_hoard"]
