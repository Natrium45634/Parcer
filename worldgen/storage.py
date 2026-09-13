# -*- coding: utf-8 -*-
"""Сохранение и загрузка мира.

Мир целиком укладывается в один JSON-файл: его можно передать, сравнить
или открыть заново и продолжить разглядывать без повторной генерации.
"""

from __future__ import annotations

import dataclasses
import io
import json

from .models import (Camp, EraSpan, Event, Figure, Polity, Region, Settlement,
                     Tribe)
from .timeline import Date
from .world import World

FORMAT_NAME = "fantasy-chronicle-world"
FORMAT_VERSION = 1

_DATE_FIELDS = {"birth", "death", "founded", "ended", "date"}


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
        "eras": [era.to_dict() for era in world.eras],
        "regions": [item.to_dict() for item in world.regions.values()],
        "figures": [item.to_dict() for item in world.figures.values()],
        "tribes": [item.to_dict() for item in world.tribes.values()],
        "settlements": [item.to_dict() for item in world.settlements.values()],
        "polities": [item.to_dict() for item in world.polities.values()],
        "camps": [item.to_dict() for item in world.camps.values()],
        "events": [item.to_dict() for item in world.events],
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
        if tribe.status == "активно":
            world.active_tribes.append(tribe.id)
    for item in data.get("settlements", ()):
        settlement = Settlement(**_clean(Settlement, item))
        world.settlements[settlement.id] = settlement
        if settlement.status == "активно":
            world.active_settlements.append(settlement.id)
    for item in data.get("polities", ()):
        polity = Polity(**_clean(Polity, item))
        world.polities[polity.id] = polity
        if polity.status == "активно":
            world.active_polities.append(polity.id)
    for item in data.get("camps", ()):
        camp = Camp(**_clean(Camp, item))
        world.camps[camp.id] = camp
        if camp.status == "активно":
            world.active_camps.append(camp.id)
    for item in data.get("events", ()):
        world.events.append(Event(**_clean(Event, item)))

    world.race_awakening = dict(data.get("race_awakening") or {})
    world._counters = dict(data.get("counters") or {})
    world.notes = dict(data.get("notes") or {})
    return world


def save_world(world: World, path: str) -> None:
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(world_to_dict(world), handle, ensure_ascii=False, indent=1)


def load_world(path: str) -> World:
    with io.open(path, "r", encoding="utf-8") as handle:
        return dict_to_world(json.load(handle))


def save_text(text: str, path: str) -> None:
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
