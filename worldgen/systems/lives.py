# -*- coding: utf-8 -*-
"""Судьбы личностей.

Дата смерти известна в момент создания персонажа — так генерация остаётся
дешёвой и детерминированной. Здесь только отмечаются уходы тех, чьё имя
стоит записи в летописи.
"""

from __future__ import annotations

from . import houses as houses_mod
from .. import narrative
from .. import races as races_mod
from ..models import ACTIVE

NOTABLE_ROLES = ("основатель страны", "основатель поселения", "основатель племени")


def tick(ctx, year: int) -> None:
    world = ctx.world
    departed = world.due_deaths(year)
    if not departed:
        return
    rng = ctx.rng("deaths", year)

    for figure in departed:
        race = races_mod.get_race(figure.race_id)
        age = max(1, figure.death.year - figure.birth.year)
        houses_mod.note_death(ctx, figure, figure.death, year)
        _maybe_bury(ctx, figure, year, rng)

        # О смерти правящих монархов пишет система престолонаследия.
        if "правитель" in figure.roles:
            continue

        if "основатель страны" in figure.roles:
            importance = 3
            achievement = _polity_legacy(world, figure)
        elif "основатель поселения" in figure.roles and rng.chance(0.22):
            importance = 1
            achievement = _settlement_legacy(world, figure)
        elif "основатель племени" in figure.roles and rng.chance(0.06):
            importance = 1
            achievement = ""
        else:
            continue

        title, text = narrative.figure_death(rng, figure, race, age, achievement)
        world.add_event(
            date=figure.death, era_index=world.era_index_at(year), kind="figure_death",
            title=title, text=text, importance=importance, actors=[figure.id],
            region_id=figure.origin_region, race_id=figure.race_id,
        )


# Кого хоронят так, что об этом помнят: не всякого, кто носил титул, а
# того, кого летопись и так заметила.
TOMB_ROLES = ("правитель", "основатель страны", "полководец", "чародей",
              "верховный жрец", "мастер")
TOMB_CHANCE = {"правитель": 0.10, "основатель страны": 0.22,
               "полководец": 0.07, "чародей": 0.14, "верховный жрец": 0.10,
               "мастер": 0.08}


def _maybe_bury(ctx, figure, year: int, rng) -> None:
    """Над тем, чьё имя чего-то стоило, насыпают курган.

    Курган — не украшение: это место с годом, именем и содержимым, и
    через века туда кто-нибудь войдёт. Но курганы ставят не всем, иначе
    мир превращается в сплошное кладбище с картой входов.
    """
    from . import sites as sites_mod

    world = ctx.world
    if world.artifacts_of(figure):
        return          # с вещами хоронит система артефактов
    role = next((item for item in TOMB_ROLES if item in figure.roles), "")
    if not role:
        return
    # Посмертное прозвище — вернейший знак того, что человека запомнили:
    # его даёт не двор, а потомки. Таких и хоронят с камнем; прочих —
    # как придётся, иначе мир зарастает курганами.
    chance = TOMB_CHANCE.get(role, 0.08) * 0.5
    if figure.posthumous:
        chance = 0.40
    elif figure.deeds:
        chance += 0.06
    if figure.epithet:
        chance += 0.03
    if not rng.chance(min(0.5, chance)):
        return
    # Титул уже согласован по полу — на камне он и стоит.
    mark = figure.titles[0] if figure.titles else role
    sites_mod.bury(ctx, figure, year, figure.death,
                   deeds="при жизни — %s" % mark,
                   rich=1.0 + 0.4 * len(figure.titles))


def _polity_legacy(world, figure) -> str:
    by = "ею" if figure.sex == "f" else "им"
    for polity in world.polities.values():
        if polity.founder_id == figure.id:
            if polity.status == ACTIVE:
                return "Основанное %s государство — %s — стоит до сих пор." % (
                    by, polity.full_name)
            return "Основанное %s государство — %s — к тому времени уже пало." % (
                by, polity.full_name)
    return ""


def _settlement_legacy(world, figure) -> str:
    by = "ею" if figure.sex == "f" else "им"
    for settlement in world.settlements.values():
        if settlement.founder_id == figure.id:
            return "Основанное %s поселение — %s — живёт своей жизнью." % (
                by, settlement.full_name)
    return ""
