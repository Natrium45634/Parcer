# -*- coding: utf-8 -*-
"""Жизнь артефактов: ковка, руки, утрата, находка.

Вещь с именем живёт дольше человека, и в этом вся её ценность для
летописи. Меч куют в такой-то год в такой-то кузне; его жалуют
полководцу; полководец гибнет, и меч уходит под курган вместе с ним;
через триста лет курган вскрывают — и меч возвращается в мир с новым
хозяином и старым проклятием.

Каждая такая перемена записывается в цепочку рук. По этой цепочке потом
и строится всё остальное: и рассказ летописца, и подземелье, в котором
вещь лежит.
"""

from __future__ import annotations

from .. import artifacts as art
from .. import narrative_artifacts as texts
from .. import races as races_mod
from ..models import ACTIVE

FORGE_RATE = 0.040          # шанс, что за такт где-то в мире выкуют вещь
GIFT_RATE = 0.012           # и что бог оставит дар на алтаре
GRANT_RATE = 0.35           # с какой охотой вещь из казны отдают в руки
FIND_RATE = 0.05            # и что забытую вещь снова находят
MIN_CITY = 1500             # в деревне такую работу не поднять
MIN_ERA = 1


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("artifacts", year)
    scale = period / 10.0

    if world.era_index_at(year) >= MIN_ERA:
        tries = 1 + len(world.active_polities) // 12
        for _ in range(tries):
            if rng.chance(FORGE_RATE * scale):
                _forge(ctx, year, rng)
        if rng.chance(GIFT_RATE * scale * (1 + len(world.living_faiths) // 8)):
            _bestow(ctx, year, rng)

    _tend(ctx, year, period, rng)


# ---------------------------------------------------------------------------
# Рождение вещи
# ---------------------------------------------------------------------------

def _forge(ctx, year: int, rng) -> None:
    """Мастер заканчивает работу, которой отдал не один год."""
    world = ctx.world
    cities = [world.settlements[sid] for sid in world.active_settlements
              if world.settlements[sid].population >= MIN_CITY]
    if not cities:
        return
    city = rng.weighted([(item, float(item.population) ** 0.7)
                         for item in cities])
    race = races_mod.RACES_BY_ID.get(city.race_id)
    if race is None:
        return
    maker = _master(ctx, city, race, year, rng)
    artifact = _make(ctx, rng, race, year, art.FORGED, maker=maker,
                     region_id=city.region_id, city=city)
    polity = world.polities.get(city.polity_id)
    date = artifact.made
    if polity is not None and polity.status == ACTIVE:
        world.put_artifact(artifact, art.IN_TREASURY, date, polity=polity,
                           how="принята в сокровищницу")
    else:
        world.put_artifact(artifact, art.WITH_FIGURE, date, figure=maker,
                           how="осталась у мастера")

    title, text = texts.forged(rng, artifact, maker, city)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="artifact_made",
        title=title, text=text, importance=3,
        actors=[maker.id] if maker is not None else [],
        subjects=[artifact.id, city.id], region_id=city.region_id,
        race_id=race.id)
    artifact.deeds.append(event.id)


def _master(ctx, city, race, year: int, rng):
    """Кузнец, которого запомнят по одной работе."""
    sex = "f" if rng.chance(0.35) else "m"
    return ctx.make_figure(
        rng, race, year, role="мастер", region_id=city.region_id,
        title="мастер" if sex == "m" else "мастерица", sex=sex,
        home_id=city.id, epithet_chance=0.7,
        folk=ctx.world.folks.get(city.folk_id))


def _bestow(ctx, year: int, rng) -> None:
    """Бог оставляет дар на алтаре своего храма."""
    world = ctx.world
    temples = [world.temples[tid] for tid in world.temples
               if world.temples[tid].status == "действует"]
    if not temples:
        return
    temple = rng.choice(sorted(temples, key=lambda t: t.id))
    faith = world.faiths.get(temple.faith_id)
    deity = world.deities.get(faith.chief_deity_id) if faith is not None else None
    settlement = world.settlements.get(temple.settlement_id)
    race = races_mod.RACES_BY_ID.get(
        settlement.race_id if settlement is not None else "")
    if race is None:
        return
    artifact = _make(ctx, rng, race, year, art.GIFTED,
                     region_id=settlement.region_id if settlement else "",
                     dark=-0.2 if faith is not None and faith.alignment > 0
                     else 0.3)
    world.put_artifact(artifact, art.IN_TEMPLE, artifact.made,
                       how="оставлена на алтаре")
    artifact.notes.append("храм: %s" % temple.name)

    title, text = texts.gifted(rng, artifact, deity, temple)
    event = world.add_event(
        date=artifact.made, era_index=world.era_index_at(year),
        kind="artifact_gift", title=title, text=text, importance=4,
        subjects=[artifact.id, temple.id],
        region_id=settlement.region_id if settlement is not None else "",
        race_id=race.id)
    artifact.deeds.append(event.id)


def _make(ctx, rng, race, year: int, origin: str, maker=None,
          region_id: str = "", city=None, sort: str = "", dark: float = 0.0):
    """Собирает вещь: род, материал, свойства, имя."""
    world = ctx.world
    shape = art.shape_for(rng, sort)
    material = art.material_for(rng)
    worth = material[2] * (1.2 if origin == art.GIFTED else 1.0)
    tongue = None
    if city is not None:
        folk = world.folks.get(city.folk_id)
        tongue = world.tongue_of(folk) if folk is not None else None
    name = ctx.forge.artifact(rng, race, shape, tongue)
    artifact = world.add_artifact(
        name=name, shape=shape.key, word=shape.word, gender=shape.gender,
        sort=shape.sort,
        material=material[0], material_gen=material[1],
        made=ctx.date_in(rng, year), origin=origin,
        maker_id=maker.id if maker is not None else "",
        race_id=race.id, region_id=region_id,
        powers=art.powers_for(rng, worth),
        curse=art.curse_for(rng, worth, dark + ctx.dark_tilt * 0.3))
    return artifact


# ---------------------------------------------------------------------------
# Жизнь вещи
# ---------------------------------------------------------------------------

def _tend(ctx, year: int, period: int, rng) -> None:
    world = ctx.world
    scale = period / 10.0
    for artifact in list(world.artifacts.values()):
        if artifact.status != ACTIVE:
            continue
        if artifact.where == art.WITH_FIGURE:
            _check_owner(ctx, artifact, year, rng)
        elif artifact.where == art.IN_TREASURY and rng.chance(GRANT_RATE * scale):
            _grant(ctx, artifact, year, rng)
        elif artifact.where in (art.LOST, art.IN_RUIN) \
                and rng.chance(FIND_RATE * scale):
            _rediscover(ctx, artifact, year, rng)


def _check_owner(ctx, artifact, year: int, rng) -> None:
    """Хозяин умер — вещь ищет новые руки, курган или чужую добычу."""
    world = ctx.world
    owner = world.figures.get(artifact.owner_id)
    if owner is None:
        _drop(ctx, artifact, year, rng)
        return
    if owner.alive_at(year):
        return

    date = owner.death or ctx.date_in(rng, year)
    heirs = [world.figures[fid] for fid in owner.children
             if fid in world.figures and world.figures[fid].alive_at(year)]
    roll = rng.random()
    if heirs and roll < 0.45:
        heir = heirs[0]
        world.put_artifact(artifact, art.WITH_FIGURE, date, figure=heir,
                           how="унаследована")
        title, text = texts.inherited(rng, artifact, heir)
        event = world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="artifact_passed", title=title, text=text, importance=2,
            actors=[heir.id], subjects=[artifact.id],
            region_id=artifact.region_id, race_id=artifact.race_id)
        artifact.deeds.append(event.id)
        return
    _drop(ctx, artifact, year, rng, owner=owner, date=date)


def _drop(ctx, artifact, year: int, rng, owner=None, date=None) -> None:
    """Вещь без хозяина: теряется или уходит в землю вместе с ним."""
    world = ctx.world
    date = date or ctx.date_in(rng, year)
    region = world.regions.get(artifact.region_id)
    if owner is not None and rng.chance(0.55):
        # Вещь уходит в землю вместе с хозяином, и над ними обоими встаёт
        # курган — место, у которого есть и год, и имя, и содержимое.
        from . import sites as sites_mod

        deeds = _deeds_line(world, owner)
        site = sites_mod.bury(ctx, owner, year, date, artifacts=[artifact],
                              deeds=deeds, rich=artifact.fame)
        if site is None:
            world.put_artifact(artifact, art.IN_TOMB, date,
                               how="положена в могилу хозяина")
        artifact.notes.append("похоронена с %s в %d году"
                              % (owner.name, date.year))
        return
    world.put_artifact(artifact, art.LOST, date, how="потеряна")
    title, text = texts.lost(rng, artifact, region)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="artifact_lost",
        title=title, text=text, importance=2, subjects=[artifact.id],
        region_id=artifact.region_id, race_id=artifact.race_id)
    artifact.deeds.append(event.id)


def _deeds_line(world, figure) -> str:
    """Чем этот человек был памятен — одной строкой для надписи на камне.

    Титул уже согласован по полу, поэтому его и берут: «при жизни —
    королева», а не «при жизни она была правитель».
    """
    if figure.titles:
        return "при жизни — %s" % figure.titles[0]
    roles = [role for role in figure.roles
             if role not in ("искатель", "новая кровь", "дитя знатного рода")]
    return "при жизни — %s" % roles[0] if roles else ""


def _grant(ctx, artifact, year: int, rng) -> None:
    """Вещь из казны жалуют тому, кому предстоит ею воспользоваться."""
    from . import nations as nations_mod

    world = ctx.world
    polity = world.polities.get(artifact.polity_id)
    if polity is None or polity.status != ACTIVE:
        world.put_artifact(artifact, art.LOST, ctx.date_in(rng, year),
                           how="пропала с гибелью державы")
        return
    race = races_mod.get_race(polity.race_id)
    hero = nations_mod.pick_general(ctx, rng, polity, race, year)
    if hero is None:
        return
    date = ctx.date_in(rng, year)
    world.put_artifact(artifact, art.WITH_FIGURE, date, figure=hero,
                       polity=polity, how="пожалована государем")
    artifact.polity_id = polity.id
    title, text = texts.granted(rng, artifact, hero, polity)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="artifact_granted",
        title=title, text=text, importance=2, actors=[hero.id],
        subjects=[artifact.id, polity.id],
        region_id=polity.region_ids[0] if polity.region_ids else "",
        race_id=polity.race_id)
    artifact.deeds.append(event.id)


def _rediscover(ctx, artifact, year: int, rng) -> None:
    """Забытую вещь находят — случайно или потому, что искали."""
    world = ctx.world
    region = world.regions.get(artifact.region_id)
    cities = [world.settlements[sid] for sid in world.active_settlements
              if region is None
              or world.settlements[sid].region_id == region.id]
    if not cities:
        cities = [world.settlements[sid] for sid in world.active_settlements]
    if not cities:
        return
    city = rng.choice(sorted(cities, key=lambda s: s.id))
    race = races_mod.RACES_BY_ID.get(city.race_id)
    if race is None:
        return
    sex = "f" if rng.chance(0.4) else "m"
    finder = ctx.make_figure(
        rng, race, year, role="искатель", region_id=city.region_id,
        title="", sex=sex, home_id=city.id, epithet_chance=0.6,
        folk=world.folks.get(city.folk_id))
    date = ctx.date_in(rng, year)
    place = "руин" if artifact.where == art.IN_RUIN else "земли, где её потеряли"
    years = max(1, year - (artifact.lost.year if artifact.lost else
                           artifact.made.year))
    world.put_artifact(artifact, art.WITH_FIGURE, date, figure=finder,
                       how="найдена")
    title, text = texts.found(rng, artifact, finder, place, years)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="artifact_found",
        title=title, text=text, importance=3, actors=[finder.id],
        subjects=[artifact.id], region_id=city.region_id, race_id=race.id)
    artifact.deeds.append(event.id)


__all__ = ["upkeep"]
