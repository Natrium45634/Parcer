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
    "house_found": "Новый род",
    "house_cadet": "Младшая ветвь",
    "house_royal": "Династия",
    "house_extinct": "Пресечение рода",
    "accession": "Восшествие на престол",
    "dynasty_change": "Смена династии",
    "coup": "Переворот",
    "plot_failed": "Раскрытый заговор",
    "abdication": "Отречение",
    "regency_start": "Регентство",
    "regency_end": "Конец регентства",
    "marriage": "Брак",
    "heir_birth": "Рождение наследника",
    "ruler_death": "Смерть правителя",
    "interregnum": "Междуцарствие",
    "calamity_begins": "Начало бедствия",
    "calamity_ongoing": "Бедствие продолжается",
    "calamity_ends": "Конец бедствия",
    "calamity_compound": "Беда на беду",
    "battle": "Сражение",
    "city_lost": "Гибель города",
    "dark_age": "Тёмные века",
    "dark_age_end": "Конец тёмных веков",
    "relic_left": "След бедствия",
    "relic_awakens": "Пробуждение следа",
    "relic_echo": "Отголосок бедствия",
    "polity_split": "Осколок державы",
    "polity_fracture": "Раздробленность",
    "conquest": "Завоевание",
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
    populations = world.population_by_race()
    header = "  %-20s %-16s %9s %9s %8s %9s %9s %12s" % (
        "Раса", "Пробуждение", "племён", "городов", "стран", "лагерей", "лиц",
        "население")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for row in world.race_summary():
        race = row["race"]
        awakening = ("%d год" % row["awakening"]) if row["awakening"] else "не пробудилась"

        def pair(key):
            total, alive = row[key]
            return "—" if not total else "%d/%d" % (total, alive)

        living = populations.get(race.id, 0)
        rows.append("  %-20s %-16s %9s %9s %8s %9s %9s %12s" % (
            race.name, awakening, pair("tribes"), pair("settlements"),
            pair("polities"), pair("camps"), pair("figures"),
            "%d" % living if living else "—"))
    return "\n".join(rows)


def render_regions(world) -> str:
    rows = ["ЗЕМЛИ МИРА", ""]
    rows.append("  %-28s %-14s %s" % ("Название", "Местность", "Соседи"))
    rows.append("  " + "-" * 72)
    for region in world.regions.values():
        neighbors = ", ".join(world.regions[n].name for n in region.neighbors)
        rows.append("  %-28s %-14s %s" % (region.name, region.terrain, neighbors))
    return "\n".join(rows)


def render_calamities(world) -> str:
    """Справочник бедствий: что, когда, какой ценой и чем кончилось."""
    from . import catastrophe as cat
    from .narrative_calamity import number

    rows = ["БЕДСТВИЯ МИРА", ""]
    nature = world.notes.get("нрав мира")
    if nature:
        titles = []
        for key in nature:
            spec = cat.CATALOG_BY_KEY.get(key)
            if spec is not None:
                titles.append(spec.title.lower())
        if titles:
            rows.append("  Этот мир особенно склонен к таким бедам: %s."
                        % ", ".join(titles))
            rows.append("")

    calamities = sorted(world.calamities.values(), key=lambda c: c.start.ordinal)
    for calamity in calamities:
        spec = cat.CATALOG_BY_KEY.get(calamity.key)
        years = "%d—%s" % (calamity.start.year,
                           calamity.end.year if calamity.end else "…")
        rows.append("%s   [%s, %s]" % (
            calamity.name, cat.KIND_NAMES.get(calamity.kind, calamity.kind),
            cat.SEVERITY_NAMES.get(calamity.severity, "")))
        rows.append("    годы: %-16s вид: %s" % (
            years, spec.title if spec is not None else calamity.key))
        if calamity.host_size:
            rows.append("    врагов: %s" % number(calamity.host_size))
        leader = world.figures.get(calamity.leader_id)
        if leader is not None:
            rows.append("    во главе: %s" % leader.name)
        if calamity.general_ids:
            names = ", ".join(world.figures[fid].name for fid in calamity.general_ids
                              if fid in world.figures)
            rows.append("    военачальники: %s" % names)
        rows.append("    земли: %s" % ", ".join(
            world.regions[rid].name for rid in calamity.region_ids
            if rid in world.regions))
        if calamity.deaths:
            rows.append("    погибло: %s" % number(calamity.deaths))
        if calamity.settlements_lost or calamity.polities_lost:
            rows.append("    потеряно: поселений %d, стран %d" % (
                calamity.settlements_lost, calamity.polities_lost))
        if calamity.hero_ids:
            names = ", ".join(world.figures[fid].name for fid in calamity.hero_ids
                              if fid in world.figures)
            rows.append("    одолели: %s" % names)
        if calamity.commander_ids:
            names = ", ".join(world.figures[fid].name
                              for fid in calamity.commander_ids
                              if fid in world.figures)
            rows.append("    полководцы: %s" % names)
        if calamity.resolution:
            rows.append("    исход: %s" % calamity.resolution)
        if calamity.compounded_with:
            names = ", ".join(world.calamities[cid].name
                              for cid in calamity.compounded_with
                              if cid in world.calamities)
            rows.append("    совпало с: %s" % names)
        if calamity.parent_id and calamity.parent_id in world.calamities:
            rows.append("    выросло из: %s (%d год)" % (
                world.calamities[calamity.parent_id].name,
                world.calamities[calamity.parent_id].start.year))
        if calamity.dark_age_until:
            rows.append("    тёмные века до %d года" % calamity.dark_age_until)
        for relic_id in calamity.relic_ids:
            relic = world.relics.get(relic_id)
            if relic is None:
                continue
            region = world.regions.get(relic.region_id)
            rows.append("    след: %s (%s, %s) — %s" % (
                relic.name, relic.kind, region.name if region else "—",
                relic.status))
        for battle_id in calamity.battle_ids:
            battle = world.battles.get(battle_id)
            if battle is None:
                continue
            rows.append("    %s, %d год: победа — %s, полегло %s" % (
                battle.name, battle.date.year, battle.winner,
                number(battle.deaths)))
        rows.append("")
    if not calamities:
        rows.append("  Миру повезло: больших бед не случилось.")
    return "\n".join(rows)


def render_houses(world) -> str:
    """Справочник знатных родов."""
    from . import races as races_mod

    rows = ["ЗНАТНЫЕ РОДА", ""]
    header = "  %-24s %-16s %8s %-12s %-22s %6s %s" % (
        "Род", "Раса", "Основан", "Ранг", "Родовое гнездо", "Живых", "Состояние")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    houses = sorted(world.houses.values(), key=lambda h: h.founded.ordinal)
    for house in houses:
        seat = world.settlements.get(house.seat_id)
        state = house.status
        if house.ended is not None:
            state = "%s (%d)" % (house.status, house.ended.year)
        rows.append("  %-24s %-16s %8d %-12s %-22s %6d %s" % (
            house.full_name, races_mod.get_race(house.race_id).name,
            house.founded.year, house.rank, seat.name if seat else "—",
            house.alive_count, state))
    rows.append("")
    rows.append("  Всего родов: %d, из них живы: %d" % (
        len(world.houses), len(world.active_houses)))
    return "\n".join(rows)


def render_dynasties(world) -> str:
    """Списки правителей по странам — родословная власти."""
    from . import races as races_mod

    rows = ["ДИНАСТИИ И ПРАВИТЕЛИ", ""]
    polities = sorted(world.polities.values(), key=lambda p: p.founded.ordinal)
    for polity in polities:
        if not polity.reign_ids:
            continue
        house = world.houses.get(polity.house_id)
        race = races_mod.get_race(polity.race_id)
        life = "основана %d" % polity.founded.year
        if polity.ended is not None:
            life += ", пала %d" % polity.ended.year
        rows.append("%s   (%s, %s)" % (polity.full_name, race.name, life))
        rows.append("    закон наследования: %s" % races_mod.SUCCESSION_NAMES.get(
            polity.succession, "не определён"))
        if house is not None:
            rows.append("    правящий род на конец истории: %s" % house.full_name)
        rows.append("    %-4s %-14s %-40s %-24s %s" % (
            "№", "годы", "правитель", "род", "чем кончилось"))
        for reign_id in polity.reign_ids:
            reign = world.reigns.get(reign_id)
            if reign is None:
                continue
            ruler = world.figures.get(reign.ruler_id)
            reign_house = world.houses.get(reign.house_id)
            years = "%d—%s" % (reign.start.year,
                               reign.end.year if reign.end else "…")
            name = ruler.plain_name if ruler is not None else "?"
            if reign.title:
                name = "%s %s" % (reign.title, name)
            mark = ""
            if reign.legitimacy == "узурпация":
                mark = " *"
            elif reign.regent_id:
                mark = " (регент)"
            rows.append("    %-4d %-14s %-40s %-24s %s" % (
                reign.number, years, (name + mark)[:40],
                (reign_house.full_name if reign_house else "—")[:24],
                reign.end_reason or "правит"))
        rows.append("")
    rows.append("  * — власть получена не по закону.")
    return "\n".join(rows)


def full_text(world) -> str:
    """Полный экспорт: летопись + справочники."""
    return "\n\n".join((
        render_chronicle(world),
        render_eras(world),
        render_regions(world),
        render_dynasties(world),
        render_houses(world),
        render_calamities(world),
        render_stats(world),
    ))
