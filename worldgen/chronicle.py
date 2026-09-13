# -*- coding: utf-8 -*-
"""Летописец: превращает события мира в читаемый текст."""

from __future__ import annotations

import textwrap

from .timeline import years_text

IMPORTANCE_MARKS = {5: "***", 4: " **", 3: "  *", 2: "   ", 1: "   "}

KIND_LABELS = {
    "world_begin": "Сотворение",
    "era_begin": "Начало эпохи",
    "era_end": "Конец эпохи",
    "race_awakening": "Пробуждение расы",
    "tribe_found": "Племя",
    "tribe_end": "Гибель племени",
    "settlement_found": "Основание поселения",
    "colony_found": "Новое поселение",
    "settlement_ruined": "Запустение",
    "polity_found": "Рождение страны",
    "polity_fall": "Падение страны",
    "camp_found": "Лагерь",
    "camp_end": "Разорение лагеря",
    "figure_death": "Смерть",
}


DATE_WIDTH = 22


def event_date_text(event) -> str:
    date = event.date
    return "%6d г. %2d %-10s" % (date.year, date.day, date.month_name)


def format_event(event, width: int = 100, indent: str = "   ") -> str:
    mark = IMPORTANCE_MARKS.get(event.importance, "   ")
    head = "%s%s %s  %s" % (indent, mark, event_date_text(event), event.title)
    body_indent = " " * (len(indent) + len(mark) + 1 + DATE_WIDTH + 2)
    body = textwrap.fill(event.text, width=max(50, width),
                         initial_indent=body_indent, subsequent_indent=body_indent)
    return "%s\n%s" % (head, body)


def render_header(world) -> str:
    line = "=" * 78
    settings = world.settings or {}
    return "\n".join((
        line,
        "  ЛЕТОПИСЬ МИРА",
        "  Сид: %s" % world.seed_text,
        "  Охват: %s, земель: %d, плотность: %.2f" % (
            years_text(world.total_years), len(world.regions),
            settings.get("density", 1.0)),
        "  Год делится на 12 месяцев по 30 дней.",
        line,
    ))


def render_chronicle(world, min_importance: int = 1, kinds=None,
                     race_id: str = "", search: str = "", width: int = 100) -> str:
    """Основной текст летописи, разбитый по эпохам."""
    search_low = search.strip().lower()
    parts = [render_header(world), ""]

    by_era = {}
    for event in world.events:
        by_era.setdefault(event.era_index, []).append(event)

    for era in world.eras:
        events = by_era.get(era.index, [])
        shown = []
        for event in events:
            if event.importance < min_importance:
                continue
            if kinds and event.kind not in kinds:
                continue
            if race_id and event.race_id != race_id:
                continue
            if search_low and search_low not in (event.title + " " + event.text).lower():
                continue
            shown.append(event)

        parts.append("-" * 78)
        parts.append("  %s   (%d — %d, %s)" % (
            era.name.upper(), era.start_year, era.end_year, years_text(era.length)))
        if era.end_title:
            parts.append("  Конец эпохи: %s" % era.end_title)
        parts.append("-" * 78)
        parts.append(textwrap.fill(era.description, width=width,
                                   initial_indent="  ", subsequent_indent="  "))
        parts.append("")
        if not shown:
            parts.append("   (в этот отрезок не попало ни одного события по выбранным условиям)")
            parts.append("")
            continue
        for event in shown:
            parts.append(format_event(event, width=width))
        parts.append("")

    parts.append("=" * 78)
    parts.append("  Событий показано: %d из %d" % (
        sum(1 for era in world.eras for event in by_era.get(era.index, [])
            if event.importance >= min_importance
            and (not kinds or event.kind in kinds)
            and (not race_id or event.race_id == race_id)
            and (not search_low or search_low in (event.title + " " + event.text).lower())),
        len(world.events)))
    return "\n".join(parts)


def render_eras(world) -> str:
    rows = ["ЭПОХИ МИРА", ""]
    for era in world.eras:
        rows.append("%s  (%d — %d), %s" % (era.name, era.start_year,
                                           era.end_year, years_text(era.length)))
        rows.append(textwrap.fill(era.description, width=96,
                                  initial_indent="    ", subsequent_indent="    "))
        if era.end_title:
            rows.append("    Завершение: %s" % era.end_title)
        rows.append("")
    return "\n".join(rows)


def render_stats(world) -> str:
    rows = ["ИТОГИ", ""]
    for key, value in world.stats().items():
        rows.append("  %-26s %s" % (key + ":", value))
    rows.append("")
    rows.append("РАСЫ")
    rows.append("")
    rows.append("  В колонках: основано всего / уцелело к концу истории.")
    rows.append("")
    header = "  %-20s %-16s %10s %10s %9s %10s %10s" % (
        "Раса", "Пробуждение", "племён", "городов", "стран", "лагерей", "лиц")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for row in world.race_summary():
        race = row["race"]
        awakening = ("%d год" % row["awakening"]) if row["awakening"] else "не пробудилась"

        def pair(key):
            total, alive = row[key]
            return "—" if not total else "%d/%d" % (total, alive)

        rows.append("  %-20s %-16s %10s %10s %9s %10s %10s" % (
            race.name, awakening, pair("tribes"), pair("settlements"),
            pair("polities"), pair("camps"), pair("figures")))
    return "\n".join(rows)


def render_regions(world) -> str:
    rows = ["ЗЕМЛИ МИРА", ""]
    rows.append("  %-28s %-14s %s" % ("Название", "Местность", "Соседи"))
    rows.append("  " + "-" * 72)
    for region in world.regions.values():
        neighbors = ", ".join(world.regions[n].name for n in region.neighbors)
        rows.append("  %-28s %-14s %s" % (region.name, region.terrain, neighbors))
    return "\n".join(rows)


def full_text(world) -> str:
    """Полный экспорт: летопись + справочники."""
    return "\n\n".join((
        render_chronicle(world),
        render_eras(world),
        render_regions(world),
        render_stats(world),
    ))
