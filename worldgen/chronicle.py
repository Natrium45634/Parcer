# -*- coding: utf-8 -*-
"""Летописец: превращает события мира в читаемый текст."""

from __future__ import annotations

import textwrap

from . import races as races_mod
from .timeline import years_text

IMPORTANCE_MARKS = {5: "***", 4: " **", 3: "  *", 2: "   ", 1: "   "}

KIND_LABELS = {
    "world_begin": "Сотворение",
    "conquest": "Завоевание",
    "revolt": "Восстание",
    "oppression": "Притеснение народа",
    "assimilation": "Врастание народа",
    "policy_decree": "Указ о народах",
    "titular_shift": "Смена титульного народа",
    "expedition_start": "Поход в неизведанное",
    "expedition_end": "Исход похода",
    "colony_overseas": "Колония за морем",
    "colony_free": "Отделение колонии",
    "notable_deed": "Труд, оставшийся в памяти",
    "folk_awakening": "Новый народ",
    "trade_pact": "Торговый путь",
    "trade_break": "Конец торгового пути",
    "shortage": "Нужда",
    "famine": "Голод",
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
    "faith_born": "Рождение веры",
    "faith_spread": "Обращение в веру",
    "state_faith": "Государственная вера",
    "dark_state": "Тёмная вера у власти",
    "temple_built": "Построен храм",
    "temple_ruined": "Заброшенный храм",
    "schism": "Раскол веры",
    "persecution": "Гонения на веру",
    "crusade": "Священный поход",
    "blessing": "Благословение",
    "curse": "Проклятие",
    "faith_fading": "Угасание веры",
    "faith_forgotten": "Забытая вера",
    "faith_revived": "Возвращение веры",
    "divine_blame": "Гнев богов",
    "festival": "Праздник",
    "high_priest": "Глава веры",
    "champion": "Избранник богов",
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


# Родительный падеж родовых слов: имя следом остаётся в именительном,
# поэтому «у океана Коранен» верно в любом обороте.
_WATER_GEN = {"океан": "океана", "море": "моря", "залив": "залива",
              "внутреннее море": "внутреннего моря", "озеро": "озера"}


def _water_gen(kind: str, name: str) -> str:
    return "%s %s" % (_WATER_GEN.get(kind, kind or "моря"), name)


def render_regions(world) -> str:
    rows = ["ЗЕМЛИ МИРА", ""]

    if world.geography:
        rows.append("  ОБЛИК МИРА")
        order = ("океан", "море", "залив", "внутреннее море", "материк",
                 "большой остров", "остров", "архипелаг", "озеро", "хребет",
                 "река")
        for noun in order:
            items = world.geography.get(noun)
            if not items:
                continue
            rows.append("    %s: %s" % (noun.capitalize(),
                                        ", ".join(row["name"] for row in items)))
        rows.append("")

    card = world.notes.get("карта")
    if card:
        rows.append("  Мир построен по карте «%s» (сид карты «%s», %s, земель %s)."
                    % (card.get("файл"), card.get("сид карты"),
                       card.get("размер"), card.get("земель")))
        homeless = world.notes.get("не пробудились")
        if homeless:
            rows.append("  Подходящей земли не нашлось, и в мир так и не пришли: %s."
                        % ", ".join(homeless))
        rows.append("")

    from_map = any(region.from_map for region in world.regions.values())
    if not from_map:
        rows.append("  %-28s %-14s %s" % ("Название", "Местность", "Соседи"))
        rows.append("  " + "-" * 72)
        for region in world.regions.values():
            neighbors = ", ".join(world.regions[n].name for n in region.neighbors)
            rows.append("  %-28s %-14s %s" % (region.name, region.terrain, neighbors))
        return "\n".join(rows)

    for region in world.regions.values():
        marks = []
        if region.coastal:
            marks.append("побережье")
        if region.river:
            marks.append("реки")
        if region.island:
            marks.append("остров")
        rows.append("  %s — %s%s" % (region.name, region.terrain,
                                     (", " + ", ".join(marks)) if marks else ""))
        rows.append("      гексов: %-6d высота: %d м   температура: %+.1f °C"
                    "   влажность: %.2f"
                    % (len(region.hexes), region.elev_m, region.temp,
                       region.moist))
        place = []
        if region.landmass:
            place.append("%s %s" % (region.landmass_kind or "земля",
                                    region.landmass))
        if region.sea:
            place.append("у %s" % _water_gen(region.sea_kind, region.sea))
        if region.range_name:
            place.append("хребет %s" % region.range_name)
        if region.rivers:
            place.append("реки: %s" % ", ".join(region.rivers))
        if place:
            rows.append("      %s" % "; ".join(place))
        rows.append("      пригодность для жизни: %.2f   плодородие: %.2f   "
                    "руды: %.2f   дикость: %.2f"
                    % (region.habitat, region.fertility, region.richness,
                       region.savagery))
        if abs(region.magic) >= 0.005:
            rows.append("      магия: %+.3f — земля %s" % (
                region.magic, "с дурной славой" if region.magic < 0
                else "светлая"))
        if region.risk_kinds:
            rows.append("      грозит: %s" % ", ".join(region.risk_kinds))
        if region.boons:
            rows.append("      дарит: %s" % ", ".join(region.boons))
        neighbors = ", ".join(world.regions[n].name for n in region.neighbors
                              if n in world.regions)
        if neighbors:
            rows.append("      граничит с: %s" % neighbors)
        rows.append("")
    return "\n".join(rows)


def render_expeditions(world) -> str:
    """Походы в неизведанное и что из них вышло."""
    rows = ["ПОХОДЫ В НЕИЗВЕДАННОЕ", ""]
    if not world.expeditions:
        rows.append("  За море в этом мире так и не вышел никто.")
        return "\n".join(rows)

    names = {"discovered": "земля найдена", "sighted": "берег видели",
             "lost": "не вернулся никто", "empty": "впустую", "": "в пути"}
    kinds = {"sea": "за море", "ice": "к краю света", "deep": "в открытую воду",
             "land": "за горы"}
    found = sum(1 for x in world.expeditions.values() if x.discovered)
    rows.append("  Всего походов: %d. Открытых земель: %d." % (
        len(world.expeditions), found))
    edge = world.notes.get("край света") or []
    if edge:
        rows.append("  Края света достигали: %s." % "; ".join(edge))
    rows.append("")

    for expedition in sorted(world.expeditions.values(),
                             key=lambda x: x.start.ordinal):
        leader = world.figures.get(expedition.leader_id)
        polity = world.polities.get(expedition.polity_id)
        rows.append("  %d — %s (%s)" % (expedition.start.year, expedition.name,
                                        kinds.get(expedition.kind, expedition.kind)))
        rows.append("      ведёт: %s%s" % (
            leader.name if leader else "—",
            "; снаряжает %s" % polity.full_name if polity is not None else
            "; поход вольный"))
        rows.append("      цель: %s; попытка %d; людей: %d" % (
            expedition.target_name or "—", expedition.attempt, expedition.crew))
        rows.append("      исход: %s%s" % (
            names.get(expedition.outcome, expedition.outcome),
            "; погибло %d" % expedition.deaths if expedition.deaths else ""))
        for region_id in expedition.discovered:
            region = world.regions.get(region_id)
            if region is not None:
                rows.append("      открыто: %s (%s)" % (region.name, region.terrain))
        rows.append("")
    return "\n".join(rows)


def render_peoples(world) -> str:
    """Народы внутри держав: титульные, покорённые, пришлые."""
    from . import nations as pol

    rows = ["НАРОДЫ ДЕРЖАВ", ""]
    living = [world.polities[pid] for pid in world.active_polities]
    multi = [p for p in living if p.multiethnic]
    rows.append("  Живых держав: %d, из них многонародных: %d."
                % (len(living), len(multi)))
    shifts = world.notes.get("смены титульного народа") or []
    if shifts:
        rows.append("  Титульный народ менялся: %d раз." % len(shifts))
        for line in shifts[:8]:
            rows.append("      %s" % line)
    rows.append("")

    from . import races as races_mod
    from . import troops as troops_mod
    from . import warfare

    for polity in sorted(living, key=lambda p: -p.population):
        race = races_mod.get_race(polity.race_id)
        rows.append("  %s" % polity.full_name)
        rows.append("      %s" % (pol.describe(polity, world) or "нет сведений"))
        harbours = warfare.ports(world, polity)
        arms = "      войско: %s" % troops_mod.describe(race)
        if harbours:
            arms += "; портов %d, флот до %d кораблей" % (
                len(harbours), warfare.fleet(world, polity, race, 4))
        rows.append(arms)
        if polity.policy:
            rows.append("      закон о народах: %s"
                        % pol.POLICY_DESCRIPTIONS.get(polity.policy, polity.policy))
        anger = {race_id: value for race_id, value in polity.grievance.items()
                 if value >= 0.15}
        if anger:
            from . import races as races_mod
            rows.append("      копят обиду: %s" % ", ".join(
                "%s (%.0f%%)" % (races_mod.RACES_BY_ID[race_id].name, value * 100)
                for race_id, value in sorted(anger.items(), key=lambda kv: -kv[1])
                if race_id in races_mod.RACES_BY_ID))
        if polity.conquests:
            rows.append("      завоеваний на счету: %d" % len(polity.conquests))
        rows.append("")
    return "\n".join(rows)


def render_folks(world) -> str:
    """Народы внутри рас: где проснулись, чем славятся, что от них осталось."""
    from . import races as races_mod

    world.refresh_folks()
    rows = ["НАРОДЫ МИРА", ""]
    if not world.folks:
        rows.append("  Народы в этом мире не разделились.")
        return "\n".join(rows)

    alive = [folk for folk in world.folks.values() if folk.population > 0]
    rows.append("  Всего народов: %d, из них живых: %d." % (len(world.folks),
                                                            len(alive)))
    rows.append("")

    by_race = {}
    for folk in world.folks.values():
        by_race.setdefault(folk.race_id, []).append(folk)

    for race in races_mod.RACES:
        folks = by_race.get(race.id)
        if not folks:
            continue
        rows.append("  %s — очагов %d" % (race.name, len(folks)))
        for folk in sorted(folks, key=lambda f: -f.population):
            cradle = world.regions.get(folk.cradle_region)
            rows.append("      %s%s" % (folk.name,
                                        " — угас" if folk.population <= 0 else ""))
            rows.append("          колыбель: %s; пробуждение: %d год"
                        % (cradle.name if cradle else "—", folk.born.year))
            if folk.traits:
                rows.append("          слывут: %s" % ", ".join(folk.traits))
            if folk.population > 0:
                rows.append("          душ: %d; городов: %d; племён: %d; "
                            "держав: %d" % (folk.population, folk.settlements,
                                            folk.tribes, folk.polities))
        rows.append("")
    return "\n".join(rows)


def render_tongues(world) -> str:
    """Языки: семьи, звуковые законы, письменность и те, кто на них говорит."""
    from . import narrative_tongues
    from . import races as races_mod
    from . import tongues as tng

    rows = ["ЯЗЫКИ НАРОДОВ", ""]
    if not world.tongues:
        rows.append("  В этом мире языки не разошлись.")
        return "\n".join(rows)

    world.refresh_folks()
    living = [t for t in world.tongues.values() if t.status == tng.LIVING]
    sacred = [t for t in world.tongues.values() if t.status == tng.SACRED]
    dead = [t for t in world.tongues.values() if t.status == tng.DEAD]
    scripts = sorted({t.script for t in world.tongues.values() if t.script})
    rows.append("  Всего языков: %d — живых %d, храмовых %d, умолкших %d."
                % (len(world.tongues), len(living), len(sacred), len(dead)))
    if scripts:
        rows.append("  Письменностей изобретено: %d (%s)."
                    % (len(scripts), ", ".join(scripts)))
    rows.append("  Одни и те же слова показаны ниже через законы каждого языка.")
    rows.append("")

    families = {}
    for tongue in world.tongues.values():
        families.setdefault(tng.family_of(world, tongue) or tongue.id,
                            []).append(tongue)

    def family_key(item):
        root = world.tongues.get(item[0])
        return (root.born.year if root else 0, item[0])

    for root_id, kin in sorted(families.items(), key=family_key):
        root = world.tongues.get(root_id)
        race = races_mod.RACES_BY_ID.get(root.race_id if root else "")
        rows.append("  СЕМЬЯ: %s%s — наречий %d"
                    % (root.name if root else "?",
                       " (%s)" % race.name if race else "", len(kin)))
        for tongue in sorted(kin, key=lambda t: (t.born.year, t.id)):
            depth = 0
            walk, seen = tongue, set()
            while walk is not None and walk.parent_id and walk.id not in seen:
                seen.add(walk.id)
                walk = world.tongues.get(walk.parent_id)
                depth += 1
            pad = "      " + "    " * min(depth, 3)
            state = {tng.LIVING: "", tng.SACRED: " — остался в храме",
                     tng.DEAD: " — умолк"}.get(tongue.status, "")
            span = "%d" % tongue.born.year
            if tongue.ended is not None:
                span += "—%d" % tongue.ended.year
            rows.append("%s%s (%s)%s" % (pad, tongue.name, span, state))
            rows.append("%s    звучит: %s → %s"
                        % (pad, tng.SAMPLE_NAME, tng.sample(None, tongue.laws)))
            rows.append("%s    словник: %s" % (pad, ", ".join(
                "%s — %s" % pair for pair in tng.wordlist(tongue.laws))))
            if tongue.laws:
                rows.append("%s    законы: %s" % (pad, ", ".join(
                    "%s — %s" % (key, tng.LAWS[key][0])
                    for key in tongue.laws if key in tng.LAWS)))
            if tongue.script:
                source = world.tongues.get(tongue.script_from)
                origin = ""
                if source is not None and source.id != tongue.id:
                    origin = (", взято у народа, что говорит на %s"
                              % narrative_tongues.quoted(source.name))
                rows.append("%s    письмо: %s%s%s"
                            % (pad, tongue.script,
                               " с %d года" % tongue.script_year
                               if tongue.script_year else "", origin))
                note = tng.SCRIPT_NOTES.get(tongue.script)
                if note:
                    rows.append("%s        %s" % (pad, note))
            folks = [world.folks[fid] for fid in tongue.folk_ids
                     if fid in world.folks]
            speaking = [folk for folk in folks if folk.population > 0]
            if speaking:
                rows.append("%s    говорят: %s; душ %d"
                            % (pad, ", ".join(folk.name for folk in speaking),
                               tongue.speakers))
            elif folks:
                rows.append("%s    говорили: %s"
                            % (pad, ", ".join(folk.name for folk in folks)))
            if tongue.borrowed:
                names = [world.tongues[item].name for item in tongue.borrowed
                         if item in world.tongues]
                if names:
                    rows.append("%s    переняли слова: %s"
                                % (pad, ", ".join(names[:4])))
            states = [world.polities[pid].full_name
                      for pid in world.active_polities
                      if world.polities[pid].tongue_id == tongue.id]
            if states:
                rows.append("%s    язык двора в державах: %s"
                            % (pad, ", ".join(sorted(states))))
        rows.append("")
    return "\n".join(rows)


def render_trade(world) -> str:
    """Чем державы богаты, чего им не хватает и кто с кем торгует."""

    from . import goods as goods_mod

    rows = ["ХОЗЯЙСТВО И ТОРГОВЛЯ", ""]
    living = [world.polities[pid] for pid in world.active_polities]
    middle = goods_mod.middle_wealth(world)
    open_routes = [world.routes[rid] for rid in world.active_routes]
    rows.append("  Держав: %d. Торговых путей за историю: %d, действует: %d."
                % (len(living), len(world.routes), len(open_routes)))
    by_sea = sum(1 for route in world.routes.values() if route.by_sea)
    if world.routes:
        rows.append("  Из них морем: %d." % by_sea)
    rows.append("")

    if open_routes:
        rows.append("  ДЕЙСТВУЮЩИЕ ПУТИ")
        for route in sorted(open_routes, key=lambda r: r.opened.year):
            seller = world.polities.get(route.seller_id)
            buyer = world.polities.get(route.buyer_id)
            rows.append("    %d — %s → %s: %s%s"
                        % (route.opened.year,
                           seller.full_name if seller else "?",
                           buyer.full_name if buyer else "?",
                           route.good,
                           ", морем" if route.by_sea else ""))
            if route.back:
                rows.append("        обратный груз: %s" % route.back)
            if route.length:
                rows.append("        путь: %d гексов" % route.length)
        rows.append("")

    for polity in sorted(living, key=lambda p: -p.population):
        if not polity.goods:
            continue
        rows.append("  %s" % polity.full_name)
        souls = goods_mod.polity_souls(world, polity)
        balance = goods_mod.polity_balance(world, polity)
        rows.append("      %s" % goods_mod.living_line(balance, souls, middle))
        output = ", ".join("%s %d" % (good, values[0])
                           for good, values in sorted(
                               polity.goods.items(),
                               key=lambda kv: -kv[1][0])[:6])
        rows.append("      даёт: %s" % (output or "—"))
        if polity.shortages:
            rows.append("      не хватает: %s" % ", ".join(
                "%s (%.0f%%)" % (good, value * 100)
                for good, value in polity.shortages[:4]))
        if polity.surpluses:
            rows.append("      в избытке: %s" % ", ".join(
                good for good, _ in polity.surpluses[:4]))
        if polity.hunger >= 0.2:
            rows.append("      сытость: %s"
                        % ("впроголодь" if polity.hunger < 0.45 else "голодает"))
        rows.append("")
    return "\n".join(rows)


def render_guilds(world) -> str:
    """Гильдии и вольные города: деньги как третья сила."""
    rows = ["ГИЛЬДИИ И ВОЛЬНЫЕ ГОРОДА", ""]
    if not world.guilds:
        rows.append("  Купцы этого мира в силу не вошли.")
        return "\n".join(rows)

    guilds = sorted(world.guilds.values(),
                    key=lambda item: item.founded.ordinal)
    republics = [item for item in guilds if item.republic_id]
    rows.append("  Всего гильдий: %d, из них держится доныне %d. "
                "Вольных городов вышло %d."
                % (len(guilds), len(world.active_guilds), len(republics)))
    rows.append("  Вольностей куплено при чужих дворах: %d; вмешательств в "
                "дела держав: %d."
                % (sum(len(item.charters) for item in guilds),
                   sum(item.deeds for item in guilds)))
    rows.append("")

    header = "  %-8s %-46s %-14s %-9s %s" % ("Год", "Гильдия", "Род", "Казна",
                                             "Судьба")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for guild in guilds:
        seat = world.settlements.get(guild.seat_id)
        polity = world.polities.get(guild.polity_id)
        rows.append("  %-8d %-46s %-14s %-9d %s" % (
            guild.founded.year, guild.name[:46], guild.kind,
            int(guild.wealth), guild.end_reason or "действует"))
        line = "        город: %s; держава: %s; товар: %s" % (
            seat.name if seat else "—",
            polity.full_name if polity else "—", guild.good)
        rows.append(line)
        head = world.figures.get(guild.head_id)
        if head is not None:
            rows.append("        старшина: %s" % head.name)
        if guild.charters:
            names = [world.polities[pid].full_name for pid in guild.charters
                     if pid in world.polities]
            if names:
                rows.append("        вольности при дворах: %s"
                            % ", ".join(names[:4]))
        if guild.republic_id:
            republic = world.polities.get(guild.republic_id)
            rows.append("        добилась вольности города: %s"
                        % (republic.full_name if republic else "—"))
    rows.append("")

    free = [world.polities[pid] for pid in world.polities
            if world.polities[pid].form in ("Торговая Республика",
                                            "Вольный Город")]
    if free:
        rows.append("  ВОЛЬНЫЕ ГОРОДА И РЕСПУБЛИКИ")
        for polity in sorted(free, key=lambda p: p.founded.ordinal):
            ruler = world.figures.get(polity.ruler_id)
            rows.append("    %d — %s%s"
                        % (polity.founded.year, polity.full_name,
                           "" if polity.id in world.active_polities
                           else " (%s)" % (polity.end_reason or "пала")))
            if ruler is not None:
                rows.append("        во главе: %s" % ruler.name)
        rows.append("")
    return "\n".join(rows)


def render_artifacts(world) -> str:
    """Вещи с именами: кто сделал, через чьи руки прошли, где лежат."""
    from . import artifacts as art

    rows = ["ВЕЩИ, У КОТОРЫХ ЕСТЬ ИМЯ", ""]
    if not world.artifacts:
        rows.append("  Таких вещей этот мир не сделал.")
        return "\n".join(rows)

    items = sorted(world.artifacts.values(),
                   key=lambda item: item.made.ordinal)
    where = {}
    for item in items:
        where[item.where] = where.get(item.where, 0) + 1
    rows.append("  Всего вещей: %d. Из них с проклятием: %d."
                % (len(items), sum(1 for item in items if item.curse)))
    rows.append("  Где они сейчас: %s." % ", ".join(
        "%s %d" % (key, count) for key, count in
        sorted(where.items(), key=lambda pair: (-pair[1], pair[0]))))
    rows.append("")

    for item in items:
        maker = world.figures.get(item.maker_id)
        rows.append("  %s — %s, %s" % (item.name, item.word.lower(),
                                       item.material_gen))
        line = "      сделана в %d году" % item.made.year
        if maker is not None:
            line += "; мастер: %s" % maker.name
        line += "; %s" % art.ORIGIN_NAMES.get(item.origin, item.origin)
        rows.append(line)
        if item.powers:
            rows.append("      за ней числится: %s" % "; ".join(item.powers))
        if item.curse:
            rows.append("      проклятие: %s" % item.curse)
        site = world.sites.get(item.site_id)
        owner = world.figures.get(item.owner_id)
        place = item.where
        if site is not None:
            place = "%s (%s)" % (item.where, site.name)
        elif owner is not None:
            place = "%s — %s" % (item.where, owner.name)
        rows.append("      ныне: %s; слава: %.1f" % (place, item.fame))
        if item.trail:
            hands = ["%d — %s" % (step.get("year", 0), step.get("who") or "—")
                     for step in item.trail]
            rows.append("      руки: %s" % " → ".join(hands[:8]))
        rows.append("")
    return "\n".join(rows)


def render_sites(world) -> str:
    """Места, в которых лежит история: курганы, руины, клады, логова.

    Это и есть тот справочник, по которому будущая игра строит
    подземелья: у каждого места есть год, имя, содержимое и тот, кто его
    стережёт.
    """
    from . import sites as sites_mod

    rows = ["МЕСТА, ГДЕ ЛЕЖИТ ИСТОРИЯ", ""]
    if not world.sites:
        rows.append("  Таких мест этот мир не оставил.")
        return "\n".join(rows)

    items = sorted(world.sites.values(), key=lambda item: item.created.ordinal)
    kinds, states = {}, {}
    for item in items:
        kinds[item.kind] = kinds.get(item.kind, 0) + 1
        states[item.status] = states.get(item.status, 0) + 1
    rows.append("  Всего мест: %d — %s." % (len(items), ", ".join(
        "%s %d" % (key, count) for key, count in
        sorted(kinds.items(), key=lambda pair: (-pair[1], pair[0])))))
    rows.append("  Состояние: %s." % ", ".join(
        "%s %d" % (key, count) for key, count in
        sorted(states.items(), key=lambda pair: (-pair[1], pair[0]))))
    rows.append("")

    # Сперва те, куда ещё никто не входил: они и интересны.
    order = {sites_mod.UNTOUCHED: 0, sites_mod.INHABITED: 1,
             sites_mod.ROBBED: 2, sites_mod.COLLAPSED: 3}
    items.sort(key=lambda item: (order.get(item.status, 4), -item.riches))
    for item in items:
        region = world.regions.get(item.region_id)
        rows.append("  %s — %s, %s" % (item.name, item.kind,
                                       item.status))
        rows.append("      земля: %s; год: %d; глубина: %d; добра: %d"
                    % (region.name if region is not None else "—",
                       item.created.year, item.depth, item.riches))
        if item.story:
            rows.append("      память: %s" % item.story)
        if item.guards:
            rows.append("      стережёт: %s" % item.guards)
        if item.artifact_ids:
            names = [world.artifacts[aid].name for aid in item.artifact_ids
                     if aid in world.artifacts]
            if names:
                rows.append("      внутри: %s" % ", ".join(names))
        if item.opened is not None:
            opener = world.figures.get(item.opened_by)
            rows.append("      вскрыто в %d году%s"
                        % (item.opened.year,
                           "; вошёл %s" % opener.name if opener else ""))
        rows.append("")
    return "\n".join(rows)


def render_laws(world) -> str:
    """Законы и реформы: кто что завёл и кто это перенял."""
    from . import laws as laws_mod

    rows = ["ЗАКОНЫ И РЕФОРМЫ", ""]
    if not world.laws:
        rows.append("  Порядков в этом мире не заводили.")
        return "\n".join(rows)

    items = sorted(world.laws.values(), key=lambda item: item.made.ordinal)
    common = [item for item in items if item.famous]
    rows.append("  Заведено порядков: %d из %d возможных; общими стали %d."
                % (len(items), len(laws_mod.REFORMS), len(common)))
    rows.append("")

    header = "  %-8s %-26s %-14s %-32s %s" % (
        "Год", "Порядок", "Дело", "Кто первым", "Держав")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for item in items:
        polity = world.polities.get(item.polity_id)
        ruler = world.figures.get(item.ruler_id)
        rows.append("  %-8d %-26s %-14s %-32s %d%s"
                    % (item.made.year, item.name[:26],
                       laws_mod.FAMILY_NAMES.get(item.family,
                                                 item.family)[:14],
                       (polity.full_name if polity is not None else "—")[:32],
                       len(item.copied_by),
                       "  (общий порядок)" if item.famous else ""))
        if ruler is not None:
            rows.append("        завёл: %s" % ruler.name)
    rows.append("")

    living = [world.polities[pid] for pid in world.active_polities]
    if living:
        living.sort(key=lambda item: (-len(item.reforms), item.name))
        rows.append("  ЧЕМ ЖИВУТ ДЕРЖАВЫ НА КОНЕЦ ИСТОРИИ")
        for polity in living[:8]:
            names = [laws_mod.REFORMS_BY_KEY[key].name
                     for key in polity.reforms
                     if key in laws_mod.REFORMS_BY_KEY]
            rows.append("    %-34s порядков %2d: %s"
                        % (polity.full_name[:34], len(names),
                           ", ".join(names[:5])
                           + ("…" if len(names) > 5 else "")))
        rows.append("")
    return "\n".join(rows)


def render_lore(world) -> str:
    """Своды и легенды: что мир записал о себе и что об этом поёт."""
    from . import lore as lore_mod

    rows = ["СВОДЫ И ЛЕГЕНДЫ", ""]
    if not world.codices and not world.legends:
        rows.append("  Этот мир о себе ничего не записал.")
        return "\n".join(rows)

    if world.codices:
        # Заголовки событий нужны по их id: без указателя каждый свод
        # перебирал бы всю летопись заново.
        titles = {event.id: event.title for event in world.events}
        codices = sorted(world.codices.values(),
                         key=lambda item: item.started.ordinal)
        rows.append("  Сводов заведено: %d, ведётся доныне: %d."
                    % (len(codices), len(world.active_codices)))
        rows.append("")
        for codex in codices:
            city = world.settlements.get(codex.seat_id)
            span = codex.span or (
                (codex.ended.year if codex.ended else world.total_years)
                - codex.started.year)
            rows.append("  «%s» — %s, %s"
                        % (codex.name,
                           lore_mod.BIAS_NAMES.get(codex.bias, codex.bias),
                           codex.status))
            rows.append("      где: %s; начат в %d году; охватывает %d лет; "
                        "летописцев: %d"
                        % (city.name if city is not None else "—",
                           codex.started.year, max(0, span),
                           len(codex.keepers)))
            names = []
            for item in codex.keepers:
                figure = world.figures.get(item.get("figure", ""))
                if figure is None:
                    continue
                names.append("%s (%d—%s)" % (figure.name, item.get("from", 0),
                                             item.get("to") or "…"))
            if names:
                rows.append("      вели: %s" % "; ".join(names[:5]))
            wrong = [item for item in codex.entries
                     if item.get("kind") not in ("верно", None)]
            rows.append("      записей: %d, из них неверных: %d (точность "
                        "%.0f%%)" % (len(codex.entries), len(wrong),
                                     codex.accuracy * 100))
            for item in wrong[:3]:
                rows.append("          %d — %s: «%s»"
                            % (item.get("year", 0), item.get("kind", ""),
                               titles.get(item.get("event"), "—")))
            rows.append("")

    if world.legends:
        legends = sorted(world.legends.values(),
                         key=lambda item: item.born.ordinal)
        rows.append("  ЛЕГЕНДЫ")
        rows.append("  Сложено песен: %d." % len(legends))
        rows.append("")
        for legend in legends:
            rows.append("  «%s»" % legend.name)
            rows.append("      сложена в %d году; пересказов: %d"
                        % (legend.born.year, legend.tellings))
            if legend.truth:
                rows.append("      как было: %s" % legend.truth)
            for item in legend.shifts[:4]:
                rows.append("      %d — %s" % (item.get("year", 0),
                                               item.get("shift", "")))
            rows.append("")
    return "\n".join(rows)


def render_crafts(world) -> str:
    """Открытия: что, когда, кем сделано и кто успел это перенять."""
    from . import crafts as crafts_mod

    rows = ["РЕМЁСЛА И ОТКРЫТИЯ", ""]
    if not world.discoveries:
        rows.append("  Этот мир так ничего и не придумал.")
        return "\n".join(rows)

    items = sorted(world.discoveries.values(),
                   key=lambda item: item.made.ordinal)
    rows.append("  Сделано открытий: %d из %d возможных."
                % (len(items), len(crafts_mod.CRAFTS)))
    rows.append("")

    header = "  %-8s %-26s %-18s %-28s %s" % (
        "Год", "Открытие", "Дело", "Где", "Переняли")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for item in items:
        city = world.settlements.get(item.settlement_id)
        polity = world.polities.get(item.polity_id)
        maker = world.figures.get(item.figure_id)
        rows.append("  %-8d %-26s %-18s %-28s %d"
                    % (item.made.year, item.name[:26],
                       crafts_mod.FAMILY_NAMES.get(item.family,
                                                   item.family)[:18],
                       (city.name if city is not None else
                        (polity.name if polity is not None else "—"))[:28],
                       len(item.known_by)))
        if maker is not None:
            rows.append("        придумал: %s%s"
                        % (maker.name,
                           "; держава: %s" % polity.full_name
                           if polity is not None else ""))
    rows.append("")

    living = [world.polities[pid] for pid in world.active_polities]
    if living:
        living.sort(key=lambda item: (-len(item.known), item.name))
        rows.append("  КТО ЧТО УМЕЕТ НА КОНЕЦ ИСТОРИИ")
        for polity in living[:8]:
            names = [crafts_mod.CRAFTS_BY_KEY[key].name for key in polity.known
                     if key in crafts_mod.CRAFTS_BY_KEY]
            rows.append("    %-34s открытий %2d: %s"
                        % (polity.full_name[:34], len(names),
                           ", ".join(names[:6]) + ("…" if len(names) > 6 else "")))
        if len(living) > 8:
            backward = living[-1]
            rows.append("    …отстают: %s — открытий %d"
                        % (backward.full_name, len(backward.known)))
        rows.append("")
    return "\n".join(rows)


def render_monsters(world) -> str:
    """Чудовища с именами: логова, счёт убитых и те, кто их прикончил."""
    rows = ["ЧУДОВИЩА, У КОТОРЫХ ЕСТЬ ИМЯ", ""]
    if not world.monsters:
        rows.append("  Таких этот мир не знал.")
        return "\n".join(rows)

    items = sorted(world.monsters.values(), key=lambda item: item.born.ordinal)
    alive = [item for item in items if item.id in world.living_monsters]
    rows.append("  Всего чудовищ: %d, живы доныне: %d. Убито людей ими: %d."
                % (len(items), len(alive),
                   sum(item.kills for item in items)))
    rows.append("")

    header = "  %-8s %-26s %-18s %8s %7s %s" % (
        "Год", "Имя", "Порода", "Убито", "Клад", "Судьба")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for item in items:
        region = world.regions.get(item.region_id)
        slayer = world.figures.get(item.slayer_id)
        fate = item.status
        if slayer is not None:
            fate = "%s — %s" % (item.status, slayer.name)
        rows.append("  %-8d %-26s %-18s %8d %7d %s"
                    % (item.born.year, item.name[:26], item.word[:18],
                       item.kills, item.hoard, fate))
        line = "        земля: %s" % (region.name if region is not None else "—")
        site = world.sites.get(item.site_id)
        if site is not None:
            line += "; логово: %s" % site.name
        home = world.settlements.get(item.settlement_id)
        if home is not None:
            line += "; прячется в городе %s" % home.name
        rows.append(line)
        if item.heroes_eaten:
            names = [world.figures[fid].name for fid in item.heroes_eaten
                     if fid in world.figures]
            if names:
                rows.append("        погибли на охоте: %s"
                            % ", ".join(names[:5]))
    rows.append("")
    return "\n".join(rows)


def render_soldiery(world) -> str:
    """Крепости и вольные роты: то, что остаётся от войны между войнами."""
    from .models import ACTIVE as ACTIVE_STATE

    rows = ["КРЕПОСТИ И ВОЛЬНЫЕ РОТЫ", ""]

    forts = sorted(world.fortresses.values(), key=lambda f: f.built.ordinal)
    if forts:
        header = "  %-30s %-20s %8s %-24s %6s %s" % (
            "Крепость", "Земля", "Заложена", "Чьё знамя", "Взятий", "Состояние")
        rows.append(header)
        rows.append("  " + "-" * (len(header) - 2))
        for fortress in forts:
            region = world.regions.get(fortress.region_id)
            holder = world.polities.get(fortress.polity_id)
            state = fortress.status
            if fortress.ended is not None:
                state = "%s (%d)" % (fortress.status, fortress.ended.year)
            rows.append("  %-30s %-20s %8d %-24s %6d %s" % (
                fortress.full_name[:30],
                (region.name if region else "—")[:20], fortress.built.year,
                (holder.full_name if holder else "без знамени")[:24],
                fortress.times_taken, state))
            if len(fortress.holders) > 1:
                names = []
                for moment in fortress.holders[:8]:
                    owner = world.polities.get(moment[1]) if moment[1] else None
                    names.append("%d: %s" % (moment[0],
                                             owner.name if owner else "никто"))
                rows.append("        знамёна — %s" % "; ".join(names))
        rows.append("")
        standing = [item for item in forts if item.status == ACTIVE_STATE]
        if standing:
            oldest = min(standing, key=lambda f: f.built.ordinal)
            rows.append("  Стоит крепостей: %d; старейшая — %s, заложена в %d году."
                        % (len(standing), oldest.full_name, oldest.built.year))
        rows.append("")

    companies = sorted(world.companies.values(),
                       key=lambda c: c.founded.ordinal)
    if not companies:
        rows.append("  Вольных рот в этом мире не заводилось.")
        return "\n".join(rows)

    rows.append("  ВОЛЬНЫЕ РОТЫ")
    header = "  %-26s %8s %7s %8s %7s %s" % (
        "Рота", "Собрана", "Копий", "Нанимали", "Грабежей", "Судьба")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for company in companies:
        captain = world.figures.get(company.captain_id)
        fate = company.end_reason or (
            "служит державе" if company.employer_id else "ищет нанимателя")
        rows.append("  %-26s %8d %7d %8d %7d %s" % (
            company.name[:26], company.founded.year, company.men,
            company.wars, company.raids, fate))
        if captain is not None:
            rows.append("        капитан: %s" % captain.name)
    rows.append("")
    rows.append("  Всего рот: %d, разбоев за ними: %d"
                % (len(companies), sum(c.raids for c in companies)))
    return "\n".join(rows)


def render_politics(world) -> str:
    """Справочник политики: союзы держав, договоры и отношения."""
    from . import diplomacy as dip
    from .models import ACTIVE

    rows = ["ПОЛИТИКА: СОЮЗЫ, ДОГОВОРЫ И ОТНОШЕНИЯ", ""]

    leagues = sorted(world.leagues.values(),
                     key=lambda item: item.founded.ordinal)
    if leagues:
        rows.append("  СОЮЗЫ ДЕРЖАВ")
        for league in leagues:
            leader = world.polities.get(league.leader_id)
            span = "%d—%s" % (league.founded.year,
                              league.ended.year if league.ended else "…")
            rows.append("    %-38s %-16s %-12s держав %d, войн %d"
                        % (league.name[:38], league.kind, span,
                           len(league.member_ids), len(league.war_ids)))
            names = []
            for polity_id in league.member_ids:
                polity = world.polities.get(polity_id)
                names.append(polity.full_name if polity else "?")
            rows.append("        во главе: %s; в союзе: %s"
                        % (leader.full_name if leader else "—",
                           ", ".join(names)))
            if league.end_reason:
                rows.append("        распался: %s" % league.end_reason)
        rows.append("")

    unions = sorted(world.unions.values(),
                    key=lambda item: item.started.ordinal)
    if unions:
        rows.append("  ДИНАСТИЧЕСКИЕ УНИИ")
        for union in unions:
            first = world.polities.get(union.first_id)
            second = world.polities.get(union.second_id)
            span = "%d—%s" % (union.started.year,
                              union.ended.year if union.ended else "…")
            rows.append("    %s — %s и %s (государей %d)"
                        % (span, first.full_name if first else "?",
                           second.full_name if second else "?",
                           len(union.monarchs)))
            names = []
            for figure_id in union.monarchs:
                figure = world.figures.get(figure_id)
                if figure is not None:
                    names.append(figure.name)
            if names:
                rows.append("        обе короны носили: %s" % ", ".join(names))
            rows.append("        %s" % (union.end_reason or "длится доныне"))
        rows.append("")

    pacts = sorted(world.pacts.values(), key=lambda item: item.signed.ordinal)
    if not pacts:
        rows.append("  Держав, способных договариваться, в этом мире не нашлось.")
        return "\n".join(rows)

    header = "  %-8s %-24s %-44s %-8s %s" % (
        "Год", "Договор", "Стороны", "Лет", "Чем кончился")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for pact in pacts:
        first = world.polities.get(pact.first_id)
        second = world.polities.get(pact.second_id)
        years = (pact.ended.year - pact.signed.year) if pact.ended else \
            (world.total_years - pact.signed.year)
        rows.append("  %-8d %-24s %-44s %-8d %s" % (
            pact.signed.year, dip.PACT_NAMES.get(pact.kind, pact.kind)[:24],
            ("%s — %s" % (first.full_name if first else "?",
                          second.full_name if second else "?"))[:44],
            max(0, years), pact.end_reason or "действует"))
        extra = []
        if pact.reasons:
            extra.append("свело: %s" % ", ".join(pact.reasons))
        if pact.wars_together:
            extra.append("воевали вместе %d раз" % pact.wars_together)
        if pact.betrayals:
            extra.append("клятву нарушали %d раз" % pact.betrayals)
        if extra:
            rows.append("        %s" % "; ".join(extra))
    rows.append("")

    # Кто кого на конец истории любит и ненавидит.
    pairs = []
    seen = set()
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        for other_id, value in (polity.relations or {}).items():
            other = world.polities.get(other_id)
            if other is None or other.status != ACTIVE:
                continue
            key = tuple(sorted((polity_id, other_id)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((value, polity, other))
    if pairs:
        pairs.sort(key=lambda row: -row[0])
        rows.append("  ОТНОШЕНИЯ НА КОНЕЦ ИСТОРИИ")
        for value, first, second in pairs[:6]:
            rows.append("    %+.2f  %-14s %s — %s"
                        % (value, dip.relation_word(value), first.full_name,
                           second.full_name))
        if len(pairs) > 6:
            rows.append("    …")
            for value, first, second in pairs[-6:]:
                rows.append("    %+.2f  %-14s %s — %s"
                            % (value, dip.relation_word(value),
                               first.full_name, second.full_name))
    rows.append("")
    rows.append("  Всего договоров: %d, из них действует: %d; союзов: %d"
                % (len(pacts), len(world.active_pacts), len(world.leagues)))
    return "\n".join(rows)


def render_embassies(world) -> str:
    """Посольства и тайные дела: кто к кому ездил, с чем и чем это кончилось."""
    from . import embassy as emb

    rows = ["ПОСОЛЬСТВА, ПЕРЕГОВОРЫ И ТАЙНЫЕ ДЕЛА", ""]
    if not world.embassies:
        rows.append("  Дворы этого мира друг к другу не ездили.")
        return "\n".join(rows)

    embassies = sorted(world.embassies.values(),
                       key=lambda item: item.sent.ordinal)
    counts = {}
    for record in embassies:
        counts[record.answer] = counts.get(record.answer, 0) + 1
    rows.append("  Всего посольств: %d. Принято %d, отказано %d, выставлено "
                "%d, убито послов %d."
                % (len(embassies), counts.get(emb.ACCEPT, 0),
                   counts.get(emb.REFUSE, 0), counts.get(emb.INSULT, 0),
                   counts.get(emb.BLOOD, 0)))
    errands = {}
    for record in embassies:
        errands[record.purpose] = errands.get(record.purpose, 0) + 1
    rows.append("  С чем ездили: %s." % ", ".join(
        "%s %d" % (key, count) for key, count in
        sorted(errands.items(), key=lambda pair: (-pair[1], pair[0]))))
    rows.append("")

    # Целиком список был бы в тысячу строк; в летописи он и так есть.
    # Здесь — то, что переменило ход дел: кровь, дань и подписанные договоры.
    notable = [record for record in embassies
               if record.answer == emb.BLOOD or record.pact_id
               or record.purpose in ("мир", "дань", "покорность")]
    if notable:
        rows.append("  ПОСОЛЬСТВА, ПЕРЕМЕНИВШИЕ ДЕЛА")
        for record in notable:
            sender = world.polities.get(record.sender_id)
            host = world.polities.get(record.host_id)
            envoy = world.figures.get(record.envoy_id)
            rows.append("    %d — %s → %s"
                        % (record.sent.year,
                           sender.full_name if sender else "?",
                           host.full_name if host else "?"))
            rows.append("        наказ: %s; ответ: %s"
                        % (record.purpose, record.answer))
            if envoy is not None:
                rows.append("        посол: %s%s"
                            % (envoy.name,
                               "; в дар — %s" % record.gift if record.gift
                               else ""))
        rows.append("")

    if world.plots:
        rows.append("  ТАЙНЫЕ ДЕЛА")
        kinds, results = {}, {}
        for plot in world.plots.values():
            kinds[plot.kind] = kinds.get(plot.kind, 0) + 1
            results[plot.outcome] = results.get(plot.outcome, 0) + 1
        rows.append("  Всего дел: %d — %s." % (len(world.plots), ", ".join(
            "%s %d" % (key, count) for key, count in
            sorted(kinds.items(), key=lambda pair: (-pair[1], pair[0])))))
        rows.append("  Из них удалось %d, сорвалось %d, раскрыто %d."
                    % (results.get("удалось", 0), results.get("сорвалось", 0),
                       results.get("раскрыто", 0)))
        # Показываем то, что видно в истории: яд, подкуп и подложные права.
        loud = [plot for plot in world.plots.values()
                if plot.outcome == "удалось"
                and plot.kind in ("яд", "подкуп", "подлог")]
        loud.sort(key=lambda item: item.date.ordinal)
        for plot in loud[:14]:
            sender = world.polities.get(plot.sender_id)
            target = world.polities.get(plot.target_id)
            agent = world.figures.get(plot.agent_id)
            victim = world.figures.get(plot.victim_id)
            rows.append("    %d — %s против %s: %s"
                        % (plot.date.year,
                           sender.full_name if sender else "?",
                           target.full_name if target else "?", plot.kind))
            line = "        исполнитель: %s" % (agent.name if agent else "—")
            if victim is not None:
                line += "; жертва: %s" % victim.name
            rows.append(line)
        if len(loud) > 14:
            rows.append("    …всего громких дел: %d" % len(loud))
        rows.append("")

    # Обиды, у которых есть виновник: их припоминают при объявлении войны.
    grudges = []
    kinds = {}
    for polity in world.polities.values():
        for other_id, items in (polity.grudges or {}).items():
            other = world.polities.get(other_id)
            for key, when in items.items():
                grudges.append((when, polity, other, key))
                kinds[key] = kinds.get(key, 0) + 1
    if grudges:
        rows.append("  ОБИДЫ, КОТОРЫЕ ПОМНЯТ")
        rows.append("  Всего записано: %d — %s."
                    % (len(grudges), ", ".join(
                        "%s %d" % (warfare_label(key), count)
                        for key, count in sorted(kinds.items(),
                                                 key=lambda pair: (-pair[1],
                                                                   pair[0])))))
        # Кровь посла и яд помнят дольше прочего — их и показываем первыми.
        weight = {"envoy": 0, "poison": 1, "oath": 2, "spy": 3, "insult": 4}
        grudges.sort(key=lambda row: (weight.get(row[3], 5), -row[0],
                                      row[1].id))
        for when, polity, other, key in grudges[:14]:
            rows.append("    %d — %s и держава по имени %s: %s"
                        % (when, polity.full_name,
                           other.full_name if other else "—",
                           warfare_label(key)))
        rows.append("")
    return "\n".join(rows)


def warfare_label(key: str) -> str:
    from . import warfare
    return warfare.CAUSE_LABELS.get(key, key)


def render_wars(world) -> str:
    """Справочник войн: за что, кто с кем, сколько лет и чем кончилось."""
    from . import warfare

    rows = ["ВОЙНЫ И РАСПРИ", ""]

    feuds = sorted(world.feuds.values(),
                   key=lambda f: (f.start.ordinal if f.start else 0))
    if feuds:
        rows.append("  ВЕКОВЫЕ РАСПРИ")
        for feud in feuds:
            sides = []
            for polity_id in feud.polity_ids:
                polity = world.polities.get(polity_id)
                sides.append(polity.full_name if polity else "?")
            span = "%s—%s" % (feud.start.year if feud.start else "?",
                              feud.end.year if feud.end else "…")
            rows.append("    %-26s %-12s войн %2d, погибло %8d   %s"
                        % (feud.name, span, len(feud.war_ids), feud.deaths,
                           " против ".join(sides)))
        rows.append("")

    wars = sorted(world.wars.values(), key=lambda w: w.start.ordinal)
    if not wars:
        rows.append("  Войн в этой истории не было.")
        return "\n".join(rows)

    header = "  %-8s %-34s %-9s %5s %9s  %s" % (
        "Год", "Война", "Масштаб", "Лет", "Погибло", "Чем кончилась")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for war in wars:
        attacker = world.polities.get(war.attacker_id)
        defender = world.polities.get(war.defender_id)
        rows.append("  %-8d %-34s %-9s %5s %9d  %s" % (
            war.start.year, war.name[:34],
            "%d из 5" % war.scale,
            war.years if war.end else "идёт",
            war.deaths, war.outcome or "идёт"))
        rows.append("        %s → %s" % (
            attacker.full_name if attacker else "?",
            defender.full_name if defender else "?"))
        line = "        повод: %s; цель: %s" % (
            warfare.cause_label(war.cause),
            warfare.AIM_NAMES.get(war.aim, war.aim))
        battles = sum(1 for bid in war.battle_ids
                      if bid in world.battles
                      and world.battles[bid].kind == "битва")
        storms = len(war.battle_ids) - battles
        if battles or storms:
            line += "; сражений %d, взятых городов %d" % (battles, storms)
        if war.taken_ids:
            line += "; земель отошло %d" % len(war.taken_ids)
        if war.razed:
            line += "; срыто городов %d" % war.razed
        rows.append(line)
        if war.peace_name:
            rows.append("        мир: %s" % war.peace_name)
        elif war.end is not None:
            rows.append("        мира не заключали")
    rows.append("")
    finished = [w for w in wars if w.end is not None]
    rows.append("  Всего войн: %d, погибших в них: %d" % (
        len(wars), sum(w.deaths for w in wars)))
    if finished:
        longest = max(finished, key=lambda w: w.years)
        bloodiest = max(finished, key=lambda w: w.deaths)
        rows.append("  Самая долгая: %s (%d лет)" % (longest.name, longest.years))
        rows.append("  Самая кровавая: %s (%d погибших)"
                    % (bloodiest.name, bloodiest.deaths))
    return "\n".join(rows)


def render_pantheon(world) -> str:
    """Боги мира: имена, сферы, мировоззрение, праздники."""
    from . import pantheon as pan
    from .narrative_faith import domains_list, festival_line

    rows = ["БОГИ МИРА", ""]
    nature = world.notes.get("вера мира")
    if nature:
        rows.append("  Устройство веры: %s. Набожность: %s. Первая вера явилась "
                    "в %s году." % (nature.get("устройство"),
                                    nature.get("набожность"),
                                    nature.get("первая вера")))
        rows.append("")
    if not world.deities:
        rows.append("  Богов в этом мире так и не назвали по именам.")
        return "\n".join(rows)

    by_faith = {}
    for deity in world.deities.values():
        by_faith.setdefault(deity.faith_id, []).append(deity)

    for faith_id, deities in sorted(by_faith.items()):
        faith = world.faiths.get(faith_id)
        head = faith.name if faith is not None else "Без веры"
        state = faith.status if faith is not None else ""
        rows.append("%s   [%s]" % (head, state))
        for deity in sorted(deities, key=lambda d: d.id):
            rows.append("    %-42s %-32s %s" % (
                deity.full_name[:42],
                domains_list(deity.domains)[:32],
                pan.ALIGNMENT_SHORT.get(deity.alignment, "")))
            rows.append("        знак: %-26s праздник: %s%s" % (
                deity.symbol[:26], festival_line(deity),
                "" if deity.status == "почитается" else "  (%s)" % deity.status))
        rows.append("")
    return "\n".join(rows)


def render_faiths(world) -> str:
    """Веры мира: кто, когда, сколько верующих и чем кончилось."""
    from . import pantheon as pan
    from .narrative_calamity import number

    rows = ["ВЕРЫ МИРА", ""]
    header = "  %-26s %-15s %8s %-13s %10s %s" % (
        "Вера", "Вид", "Основана", "Состояние", "Верующих", "Народы")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    for faith in sorted(world.faiths.values(), key=lambda f: f.founded.ordinal):
        races = ", ".join(races_mod.RACES_BY_ID[rid].name
                          for rid in faith.race_ids
                          if rid in races_mod.RACES_BY_ID)
        rows.append("  %-26s %-15s %8d %-13s %10s %s" % (
            faith.name[:26], pan.FAITH_KIND_NAMES.get(faith.kind, faith.kind)[:15],
            faith.founded.year, faith.status[:13],
            number(faith.followers), races[:40]))
    rows.append("")
    rows.append("  Храмов построено: %d, из них стоит: %d" % (
        len(world.temples),
        sum(1 for t in world.temples.values() if t.status == "действует")))
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
    """Справочник знатных родов: кто, чей, какого достоинства и нрава."""
    from . import narrative_aristocracy as texts
    from . import races as races_mod
    from .models import ACTIVE, MINOR

    rows = ["ЗНАТНЫЕ РОДА", ""]
    header = "  %-24s %-16s %8s %-12s %-18s %-22s %6s %s" % (
        "Род", "Раса", "Основан", "Ранг", "Титул", "Родовое гнездо",
        "Живых", "Состояние")
    rows.append(header)
    rows.append("  " + "-" * (len(header) - 2))
    houses = sorted(world.houses.values(), key=lambda h: h.founded.ordinal)
    for house in houses:
        seat = world.settlements.get(house.seat_id)
        state = house.status
        if house.ended is not None:
            state = "%s (%d)" % (house.status, house.ended.year)
        rows.append("  %-24s %-16s %8d %-12s %-18s %-22s %6d %s" % (
            house.full_name, races_mod.get_race(house.race_id).name,
            house.founded.year, house.rank, (house.style or "—")[:18],
            (seat.name if seat else "—")[:22], house.alive_count, state))
        # Подробность — только о тех, кто что-то значил: за десять тысяч
        # лет угасших малых родов набираются тысячи, и строка нрава на
        # каждого превращает справочник в стену текста.
        notable = (house.status == ACTIVE or house.rank != MINOR
                   or house.thrones or house.charters)
        if not notable:
            continue
        note = texts.house_character(house)
        if house.motto:
            note += " · девиз %s" % house.motto
        if house.charters:
            note += " · вольностей у короны: %d" % house.charters
        if house.thrones:
            note += " · венец брал %d раз" % house.thrones
        rows.append("      %s" % note)
    rows.append("")
    rows.append("  Всего родов: %d, из них живы: %d" % (
        len(world.houses), len(world.active_houses)))
    return "\n".join(rows)


def _ruler_life(world, reign, ruler) -> str:
    """Строка жизни: когда родился, на ком женился, когда взошёл и умер.

    Ради неё всё и затевалось: король в летописи должен быть человеком
    с датами, роднёй и концом, а не строкой в таблице.
    """
    if ruler is None:
        return ""
    parts = []
    if ruler.birth is not None:
        parts.append("род. %d" % ruler.birth.year)
    crown = "венец %d" % reign.start.year
    if reign.relation:
        crown += " (%s)" % reign.relation
    parts.append(crown)
    spouse = world.figures.get(ruler.spouse_id)
    if spouse is not None:
        who = spouse.plain_name
        spouse_house = world.houses.get(spouse.house_id)
        if spouse_house is not None and spouse_house.id != ruler.house_id:
            who += " (%s)" % spouse_house.full_name
        if ruler.married is not None:
            parts.append("брак %d: %s" % (ruler.married.year, who))
        else:
            parts.append("супруг(а): %s" % who)
    kids = len([cid for cid in ruler.children if cid in world.figures])
    if kids:
        parts.append("детей %d" % kids)
    if ruler.death is not None:
        age = max(0, ruler.death.year - (ruler.birth.year if ruler.birth else 0))
        end = "ум. %d (%d)" % (ruler.death.year, age)
        if ruler.death_cause:
            end += ", %s" % ruler.death_cause
        parts.append(end)
    return " · ".join(parts)


def _ruler_nature(reign, ruler) -> str:
    """Нрав, умения и приговор истории — одной строкой."""
    from . import rulers as rulers_mod

    sex = ruler.sex if ruler is not None else "m"
    parts = []
    if reign.traits or reign.skills:
        nature = rulers_mod.alignment_label(reign.alignment, sex)
        traits = rulers_mod.traits_text(reign.traits, sex)
        parts.append(", ".join(part for part in (nature, traits) if part))
        if reign.skills:
            parts.append(", ".join(
                "%s %d" % (key, reign.skills.get(key, 5))
                for key in rulers_mod.SKILLS))
    if reign.verdict:
        if reign.closing.get("fallen"):
            parts.append("итог: гибельное — держава не пережила правления")
        else:
            parts.append("итог: %s (×%s)" % (
                reign.verdict, ("%.2f" % reign.score).replace(".", ",")))
    return " · ".join(parts)


def _noble_ladder(world, polity, race) -> str:
    """Какие ступени знатности держава успела развести — и кто на них.

    Показывает не справочную лестницу народа, а ту, что страна в самом
    деле использует: в трёхгородном княжестве она короткая.
    """
    from . import aristocracy as arist

    counts = {}
    for house_id in polity.house_ids:
        house = world.houses.get(house_id)
        if house is None or house.id == polity.house_id or house.rung < 0:
            continue
        counts[house.rung] = counts.get(house.rung, 0) + 1
    if not counts:
        return ""
    parts = []
    for rung in range(max(counts), -1, -1):
        if not counts.get(rung):
            continue
        parts.append("%s — %d" % (arist.style_text(race, rung, "m"),
                                  counts[rung]))
    return "; ".join(parts)


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
        ladder = _noble_ladder(world, polity, race)
        if ladder:
            rows.append("    лестница знати: %s" % ladder)
        rows.append("    %-4s %-14s %-52s %-24s %s" % (
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
            if ruler is not None and ruler.posthumous:
                name = "%s «%s»" % (name, ruler.posthumous)
            if reign.title:
                name = "%s %s" % (reign.title, name)
            mark = ""
            if reign.legitimacy == "узурпация":
                mark = " *"
            elif reign.regent_id:
                mark = " (регент)"
            rows.append("    %-4d %-14s %-52s %-24s %s" % (
                reign.number, years, (name + mark)[:52],
                (reign_house.full_name if reign_house else "—")[:24],
                reign.end_reason or "правит"))
            for line in (_ruler_life(world, reign, ruler),
                         _ruler_nature(reign, ruler)):
                if line:
                    rows.append("         %s" % line)
        rows.append("")
    rows.append("  * — власть получена не по закону.")
    return "\n".join(rows)


def render_upheavals(world) -> str:
    """Что великие беды сделали с самой картой — и кого мир потерял."""
    from . import catastrophe as cat
    from . import sites as sites_mod
    from .narrative_calamity import number
    from .systems import upheaval as upheaval_mod

    rows = ["КАК МЕНЯЛСЯ МИР", ""]

    great = [calamity for calamity in world.calamities.values()
             if calamity.key in upheaval_mod.GREAT]
    great.sort(key=lambda c: c.start.ordinal)
    if great:
        rows.append("  Великие беды")
        for calamity in great:
            spec = cat.CATALOG_BY_KEY.get(calamity.key)
            rows.append("    %s — %s, %d год" % (
                calamity.name, spec.title.lower() if spec else calamity.key,
                calamity.start.year))
            if calamity.deaths:
                rows.append("        погибло: %s" % number(calamity.deaths))
            for note in calamity.notes:
                if note.startswith(("под воду", "порвано", "оставлен",
                                    "исход", "осколок")):
                    rows.append("        %s" % note)
        rows.append("")

    drowned = [region for region in world.regions.values() if region.drowned]
    if drowned:
        rows.append("  Земли, которых больше нет под ногами")
        for region in sorted(drowned, key=lambda r: r.name):
            rows.append("    %s — под водой" % region.name)
        rows.append("")

    sundered = [region for region in world.regions.values() if region.sundered]
    if sundered:
        rows.append("  Земли, разрезанные разломом")
        for region in sorted(sundered, key=lambda r: r.name):
            links = ", ".join(world.regions[rid].name
                              for rid in region.sea_links
                              if rid in world.regions)
            rows.append("    %s — теперь только морем: %s"
                        % (region.name, links or "никуда"))
        rows.append("")

    sunken = [site for site in world.sites.values()
              if site.kind in (sites_mod.SUNKEN, sites_mod.SEALED)]
    if sunken:
        rows.append("  Места, куда не ходят")
        ordered = sorted(sunken, key=lambda s: s.created.ordinal)
        for site in ordered[:12]:
            region = world.regions.get(site.region_id)
            rows.append("    %s (%s, %s), %d год" % (
                site.name, site.kind, region.name if region else "—",
                site.created.year))
            if site.story:
                rows.append("        %s" % site.story)
        if len(ordered) > 12:
            rows.append("    …и ещё %d таких же" % (len(ordered) - 12))
        rows.append("")

    gone = world.notes.get(upheaval_mod.GONE_NOTE) or {}
    peaks = world.notes.get(upheaval_mod.PEAK_BY_RACE) or {}
    notable = [(race_id, year) for race_id, year in gone.items()
               if int(peaks.get(race_id, 0)) >= upheaval_mod.NOTABLE_PEAK]
    if notable:
        rows.append("  Народы, которых больше нет")
        for race_id, year in sorted(notable, key=lambda item: item[1]):
            race = races_mod.RACES_BY_ID.get(race_id)
            rows.append("    %s — %d год (в лучший век: %s)" % (
                race.name if race else race_id, year,
                number(peaks.get(race_id, 0))))
        rows.append("")

    faded = [race_id for race_id in gone
             if int(peaks.get(race_id, 0)) < upheaval_mod.NOTABLE_PEAK]
    if faded:
        names = []
        for race_id in sorted(faded):
            race = races_mod.RACES_BY_ID.get(race_id)
            names.append(race.name.lower() if race else race_id)
        rows.append("  Так и не поднялись: %s." % ", ".join(names))
        rows.append("")

    census = [row for row in (getattr(world, "census", None) or [])
              if row["souls"] > 0]
    if len(census) > 11:
        span = 10
        age, age_loss = None, 0
        for index in range(len(census) - span):
            before, after = census[index], census[index + span]
            if before["souls"] - after["souls"] > age_loss:
                age, age_loss = (before, after), before["souls"] - after["souls"]
        best = max(census, key=lambda row: row["souls"])
        rows.append("  Как жил мир")
        rows.append("    в лучший свой век: %s, %d год"
                    % (number(best["souls"]), best["year"]))
        if age is not None and age_loss > 0:
            before, after = age
            blame = ", ".join(after["calamities"][:3]) \
                or ", ".join(before["calamities"][:3]) or "долгий упадок"
            rows.append("    худший век: %d—%d, потеряно %s (%.0f%% живших)"
                        % (before["year"], after["year"], number(age_loss),
                           age_loss * 100.0 / max(1, before["souls"])))
            rows.append("        виной: %s" % blame)
        rows.append("")

    peak = world.notes.get(upheaval_mod.PEAK_NOTE)
    if peak:
        rows.append("  Людей в лучший свой век: %s." % number(peak))
        rows.append("  Сейчас: %s." % number(world.world_population()))

    if len(rows) <= 2:
        rows.append("  Карта мира осталась такой, какой её начертили.")
    return "\n".join(rows)


def render_sagas(world) -> str:
    """Цепи бедствий: какая беда из какой выросла и через сколько веков.

    Мир, где бедствия случаются порознь, читается как погода. Здесь
    видно родословную: уцелевший позвал собратьев, осколок поднялся из
    глубины, государь пришёл за силой на старое поле.
    """
    from . import catastrophe as cat
    from .narrative_calamity import number

    rows = ["ЦЕПИ БЕДСТВИЙ", ""]

    kids = {}
    for calamity in world.calamities.values():
        if calamity.parent_id and calamity.parent_id in world.calamities:
            kids.setdefault(calamity.parent_id, []).append(calamity)
    if not kids:
        rows.append("  Ни одна беда этого мира не выросла из прежней: "
                    "все они пришли сами по себе.")
        return "\n".join(rows)

    roots = []
    for calamity_id in kids:
        calamity = world.calamities[calamity_id]
        if not calamity.parent_id or calamity.parent_id not in world.calamities:
            roots.append(calamity)
    roots.sort(key=lambda item: item.start.ordinal)

    def walk(calamity, depth: int) -> None:
        pad = "    " + "    " * depth
        spec = cat.CATALOG_BY_KEY.get(calamity.key)
        rows.append("%s%s — %s, %d год%s" % (
            pad, calamity.name,
            spec.title.lower() if spec is not None else calamity.key,
            calamity.start.year,
            ", погибло %s" % number(calamity.deaths) if calamity.deaths else ""))
        for note in calamity.notes:
            if note.startswith(("выросло из следа", "поднялось из логова",
                                "осколок нашествия", "наследие беды",
                                "призвано государем", "через вещь")):
                rows.append("%s    %s" % (pad, note))
        for child in sorted(kids.get(calamity.id, ()),
                            key=lambda item: item.start.ordinal):
            gap = child.start.year - calamity.start.year
            rows.append("%s      └─ через %d %s:" % (
                pad, gap, plural_years(gap)))
            walk(child, depth + 1)

    longest, deepest = 0, 0
    for root in roots:
        rows.append("  Цепь от %d года" % root.start.year)
        walk(root, 0)
        rows.append("")
        longest = max(longest, _chain_span(world, kids, root))
        deepest = max(deepest, _chain_depth(kids, root))

    linked = sum(len(items) for items in kids.values())
    knees = deepest + 1
    rows.append("  Связанных бед: %d из %d (%.0f%%); самая длинная цепь "
                "тянется %d %s и насчитывает %d %s."
                % (linked, len(world.calamities),
                   linked * 100.0 / max(1, len(world.calamities)),
                   longest, plural_years(longest), knees,
                   _plural(knees, "колено", "колена", "колен")))
    return "\n".join(rows)


def _plural(value: int, one: str, few: str, many: str) -> str:
    value = abs(int(value)) % 100
    if 11 <= value <= 14:
        return many
    tail = value % 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


def plural_years(value: int) -> str:
    value = abs(int(value)) % 100
    if 11 <= value <= 14:
        return "лет"
    tail = value % 10
    if tail == 1:
        return "год"
    if 2 <= tail <= 4:
        return "года"
    return "лет"


def _chain_span(world, kids, root) -> int:
    last = root.start.year
    stack = [root]
    while stack:
        item = stack.pop()
        last = max(last, item.start.year)
        stack.extend(kids.get(item.id, ()))
    return last - root.start.year


def _chain_depth(kids, root) -> int:
    children = kids.get(root.id, ())
    if not children:
        return 0
    return 1 + max(_chain_depth(kids, child) for child in children)


def full_text(world) -> str:
    """Полный экспорт: летопись + справочники."""
    return "\n\n".join((
        render_chronicle(world),
        render_eras(world),
        render_regions(world),
        render_folks(world),
        render_tongues(world),
        render_trade(world),
        render_crafts(world),
        render_laws(world),
        render_lore(world),
        render_guilds(world),
        render_expeditions(world),
        render_politics(world),
        render_embassies(world),
        render_wars(world),
        render_soldiery(world),
        render_dynasties(world),
        render_peoples(world),
        render_houses(world),
        render_pantheon(world),
        render_faiths(world),
        render_calamities(world),
        render_sagas(world),
        render_upheavals(world),
        render_monsters(world),
        render_artifacts(world),
        render_sites(world),
        render_stats(world),
    ))
