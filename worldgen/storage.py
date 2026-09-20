# -*- coding: utf-8 -*-
"""Сохранение и загрузка мира.

Мир целиком укладывается в один JSON-файл: его можно передать, сравнить
или открыть заново и продолжить разглядывать без повторной генерации.
"""

from __future__ import annotations

import dataclasses
import io
import json

from .models import (ACTIVE, ONGOING, Artifact, Battle, Calamity, Camp,
                     Company, Deity,
                     Embassy, EraSpan, Event, Expedition, Faith, Feud, Figure,
                     Folk, Fortress, Guild, House, League, Pact, Plot, Polity,
                     Region, Reign, Relic, Settlement, Site, Temple, Tongue,
                     TradeRoute, Tribe, Union, War)
from .timeline import Date
from .world import World

FORMAT_NAME = "fantasy-chronicle-world"
FORMAT_VERSION = 1

_DATE_FIELDS = {"birth", "death", "founded", "ended", "date", "start", "end",
                "created", "awakened", "revealed", "born", "opened",
                "sent", "returned", "started", "made", "lost", "opened",
                "closed", "married", "signed", "built"}


def _defaults(cls) -> dict:
    """Значения по умолчанию для полей класса."""
    values = {}
    for field in dataclasses.fields(cls):
        if field.default is not dataclasses.MISSING:
            values[field.name] = field.default
        elif field.default_factory is not dataclasses.MISSING:   # type: ignore
            values[field.name] = field.default_factory()          # type: ignore
    return values


def _compact(cls, data: dict) -> dict:
    """Выбрасывает поля со значениями по умолчанию.

    Мир на десять тысяч лет — это десятки тысяч личностей, у большинства
    из которых половина полей пуста. Без такой чистки файл раздувается
    вдвое без всякой пользы.
    """
    defaults = _defaults(cls)
    known = {f.name for f in dataclasses.fields(cls)}
    result = {}
    for key, value in data.items():
        if key not in known:
            continue        # производные поля («name», «full_name») не храним
        if key in defaults and value == defaults[key]:
            continue
        result[key] = value
    return result


def _clean(cls, data: dict) -> dict:
    """Оставляет только те ключи, которые есть в классе."""
    known = {field.name for field in dataclasses.fields(cls)}
    result = {}
    for key, value in data.items():
        if key not in known:
            continue
        if key in _DATE_FIELDS:
            value = Date.from_dict(value)
        result[key] = value
    return result


def world_to_dict(world: World) -> dict:
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "seed_text": world.seed_text,
        "seed_value": world.seed_value,
        "total_years": world.total_years,
        "settings": world.settings,
        "map_source": world.map_source,
        "geography": world.geography,
        "eras": [era.to_dict() for era in world.eras],
        "regions": [_compact(Region, item.to_dict()) for item in world.regions.values()],
        "figures": [_compact(Figure, item.to_dict()) for item in world.figures.values()],
        "tribes": [_compact(Tribe, item.to_dict()) for item in world.tribes.values()],
        "settlements": [_compact(Settlement, item.to_dict())
                        for item in world.settlements.values()],
        "polities": [_compact(Polity, item.to_dict()) for item in world.polities.values()],
        "camps": [_compact(Camp, item.to_dict()) for item in world.camps.values()],
        "houses": [_compact(House, item.to_dict()) for item in world.houses.values()],
        "reigns": [_compact(Reign, item.to_dict()) for item in world.reigns.values()],
        "calamities": [_compact(Calamity, item.to_dict())
                       for item in world.calamities.values()],
        "relics": [_compact(Relic, item.to_dict()) for item in world.relics.values()],
        "expeditions": [_compact(Expedition, item.to_dict())
                        for item in world.expeditions.values()],
        "folks": [_compact(Folk, item.to_dict()) for item in world.folks.values()],
        "routes": [_compact(TradeRoute, item.to_dict())
                   for item in world.routes.values()],
        "battles": [_compact(Battle, item.to_dict())
                    for item in world.battles.values()],
        "wars": [_compact(War, item.to_dict()) for item in world.wars.values()],
        "feuds": [_compact(Feud, item.to_dict()) for item in world.feuds.values()],
        "pacts": [_compact(Pact, item.to_dict()) for item in world.pacts.values()],
        "tongues": [_compact(Tongue, item.to_dict())
                    for item in world.tongues.values()],
        "embassies": [_compact(Embassy, item.to_dict())
                      for item in world.embassies.values()],
        "unions": [_compact(Union, item.to_dict())
                   for item in world.unions.values()],
        "plots": [_compact(Plot, item.to_dict())
                  for item in world.plots.values()],
        "guilds": [_compact(Guild, item.to_dict())
                   for item in world.guilds.values()],
        "artifacts": [_compact(Artifact, item.to_dict())
                      for item in world.artifacts.values()],
        "sites": [_compact(Site, item.to_dict())
                  for item in world.sites.values()],
        "fortresses": [_compact(Fortress, item.to_dict())
                       for item in world.fortresses.values()],
        "companies": [_compact(Company, item.to_dict())
                      for item in world.companies.values()],
        "leagues": [_compact(League, item.to_dict())
                    for item in world.leagues.values()],
        "dark_ages": world.dark_ages,
        "deities": [_compact(Deity, item.to_dict()) for item in world.deities.values()],
        "faiths": [_compact(Faith, item.to_dict()) for item in world.faiths.values()],
        "temples": [_compact(Temple, item.to_dict())
                    for item in world.temples.values()],
        "events": [_compact(Event, item.to_dict()) for item in world.events],
        "race_awakening": world.race_awakening,
        "counters": world._counters,
        "notes": world.notes,
    }


def dict_to_world(data: dict) -> World:
    if data.get("format") != FORMAT_NAME:
        raise ValueError("Это не файл мира, созданный этим генератором.")

    world = World(
        seed_text=data.get("seed_text", ""),
        seed_value=int(data.get("seed_value", 0)),
        total_years=int(data.get("total_years", 0)),
        settings=data.get("settings"),
    )
    world.eras = [EraSpan(**_clean(EraSpan, item)) for item in data.get("eras", ())]

    for item in data.get("regions", ()):
        region = Region(**_clean(Region, item))
        world.regions[region.id] = region
    for item in data.get("figures", ()):
        figure = Figure(**_clean(Figure, item))
        world.figures[figure.id] = figure
    for item in data.get("tribes", ()):
        tribe = Tribe(**_clean(Tribe, item))
        world.tribes[tribe.id] = tribe
        if tribe.status == ACTIVE:
            world.active_tribes.append(tribe.id)
    for item in data.get("settlements", ()):
        settlement = Settlement(**_clean(Settlement, item))
        world.settlements[settlement.id] = settlement
        if settlement.status == ACTIVE:
            world.active_settlements.append(settlement.id)
    for item in data.get("polities", ()):
        polity = Polity(**_clean(Polity, item))
        world.polities[polity.id] = polity
        if polity.status == ACTIVE:
            world.active_polities.append(polity.id)
    for item in data.get("camps", ()):
        camp = Camp(**_clean(Camp, item))
        world.camps[camp.id] = camp
        if camp.status == ACTIVE:
            world.active_camps.append(camp.id)
    for item in data.get("houses", ()):
        house = House(**_clean(House, item))
        world.houses[house.id] = house
        if house.status == ACTIVE:
            world.active_houses.append(house.id)
    for item in data.get("reigns", ()):
        reign = Reign(**_clean(Reign, item))
        world.reigns[reign.id] = reign
    for item in data.get("calamities", ()):
        calamity = Calamity(**_clean(Calamity, item))
        world.calamities[calamity.id] = calamity
        if calamity.status == ONGOING:
            world.active_calamities.append(calamity.id)
    for item in data.get("relics", ()):
        relic = Relic(**_clean(Relic, item))
        world.relics[relic.id] = relic
        if relic.status == "спит":
            world.sleeping_relics.append(relic.id)
    for item in data.get("battles", ()):
        battle = Battle(**_clean(Battle, item))
        world.battles[battle.id] = battle
    for item in data.get("wars", ()):
        war = War(**_clean(War, item))
        world.wars[war.id] = war
        if war.status == ONGOING:
            world.active_wars.append(war.id)
    for item in data.get("feuds", ()):
        feud = Feud(**_clean(Feud, item))
        world.feuds[feud.id] = feud
    for item in data.get("tongues", ()):
        tongue = Tongue(**_clean(Tongue, item))
        world.tongues[tongue.id] = tongue
        if tongue.status != "мёртвый":
            world.living_tongues.append(tongue.id)
    for item in data.get("fortresses", ()):
        fortress = Fortress(**_clean(Fortress, item))
        world.fortresses[fortress.id] = fortress
        if fortress.status == ACTIVE:
            world.active_fortresses.append(fortress.id)
    for item in data.get("companies", ()):
        company = Company(**_clean(Company, item))
        world.companies[company.id] = company
        if company.status == ACTIVE:
            world.active_companies.append(company.id)
    for item in data.get("artifacts", ()):
        artifact = Artifact(**_clean(Artifact, item))
        world.artifacts[artifact.id] = artifact
    for item in data.get("sites", ()):
        site = Site(**_clean(Site, item))
        world.sites[site.id] = site
    for item in data.get("guilds", ()):
        guild = Guild(**_clean(Guild, item))
        world.guilds[guild.id] = guild
        if guild.status == ACTIVE:
            world.active_guilds.append(guild.id)
    for item in data.get("plots", ()):
        plot = Plot(**_clean(Plot, item))
        world.plots[plot.id] = plot
    for item in data.get("unions", ()):
        union = Union(**_clean(Union, item))
        world.unions[union.id] = union
        if union.status == ACTIVE:
            world.active_unions.append(union.id)
    for item in data.get("embassies", ()):
        embassy = Embassy(**_clean(Embassy, item))
        world.embassies[embassy.id] = embassy
    for item in data.get("pacts", ()):
        pact = Pact(**_clean(Pact, item))
        world.pacts[pact.id] = pact
        if pact.status == ACTIVE:
            world.active_pacts.append(pact.id)
    for item in data.get("leagues", ()):
        league = League(**_clean(League, item))
        world.leagues[league.id] = league
        if league.status == ACTIVE:
            world.active_leagues.append(league.id)
    world.dark_ages = list(data.get("dark_ages") or ())
    for item in data.get("deities", ()):
        deity = Deity(**_clean(Deity, item))
        world.deities[deity.id] = deity
    for item in data.get("faiths", ()):
        faith = Faith(**_clean(Faith, item))
        world.faiths[faith.id] = faith
        if faith.status not in ("забыта",):
            world.living_faiths.append(faith.id)
    for item in data.get("temples", ()):
        temple = Temple(**_clean(Temple, item))
        world.temples[temple.id] = temple
    for item in data.get("routes", ()):
        route = TradeRoute(**_clean(TradeRoute, item))
        world.routes[route.id] = route
        if route.status == ACTIVE:
            world.active_routes.append(route.id)
    for item in data.get("folks", ()):
        folk = Folk(**_clean(Folk, item))
        world.folks[folk.id] = folk
    for item in data.get("expeditions", ()):
        expedition = Expedition(**_clean(Expedition, item))
        world.expeditions[expedition.id] = expedition
        if expedition.end is None:
            world.active_expeditions.append(expedition.id)
    for item in data.get("events", ()):
        world.events.append(Event(**_clean(Event, item)))

    world.race_awakening = dict(data.get("race_awakening") or {})
    world._counters = dict(data.get("counters") or {})
    world.notes = dict(data.get("notes") or {})
    world.map_source = data.get("map_source", "") or ""
    world.geography = dict(data.get("geography") or {})
    return world


def save_world(world: World, path: str) -> None:
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(world_to_dict(world), handle, ensure_ascii=False,
                  separators=(",", ":"))


def load_world(path: str) -> World:
    with io.open(path, "r", encoding="utf-8") as handle:
        return dict_to_world(json.load(handle))


def save_text(text: str, path: str) -> None:
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
