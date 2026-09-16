# -*- coding: utf-8 -*-
"""Стандартный тест генератора.

Один прогон отвечает на два вопроса: интересно ли читать этот мир и нет
ли в нём поломок. Поэтому тест делает две вещи сразу.

**Срезы.** Берётся случайный сид (или заданный) и пять дат с разбросом по
всем эпохам. На каждую дату печатается состояние мира: эпоха, население
по народам, идущие бедствия и тёмные века, крупнейшая держава с её
правителем, народами и верой, походы, громкие события округи.

**Разбор.** После прогона мир проверяется на то, что ломалось раньше и
ломается обычно: падежи в сгенерированных текстах, согласование по полу,
титул против формы страны, повторяющиеся имена, связь урона бедствия с
его длительностью, монополия одного бога, а главное — **повторы текста**,
от которых мир перестаёт читаться как живой.

Запуск:

    python tools/worldtest.py                        случайный сид и даты
    python tools/worldtest.py --seed Ясень-7         свой сид
    python tools/worldtest.py --map maps/aurora-7.world
    python tools/worldtest.py --dates 500,2000,5000,7000,9500
    python tools/worldtest.py --years 4000 --out отчёт.txt
    python tools/worldtest.py --quiet                только разбор, без срезов

Выход не нулевой, если разбор нашёл хотя бы одну серьёзную аномалию —
так тест годится и для быстрой проверки после правок.
"""

from __future__ import annotations

import os
import re
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import aristocracy as arist                        # noqa: E402
from worldgen import nations as pol                              # noqa: E402
from worldgen import rulers                                      # noqa: E402
from worldgen.catastrophe import KIND_NAMES, SEVERITY_NAMES      # noqa: E402
from worldgen.engine import Settings, generate                   # noqa: E402
from worldgen.pantheon import (ALIGNMENT_NAMES, DOMAINS_BY_KEY,  # noqa: E402
                               FAITH_KIND_NAMES)
from worldgen.races import RACES_BY_ID, SUCCESSION_NAMES         # noqa: E402
from worldgen.rng import random_seed_text                        # noqa: E402
from worldgen.models import ACTIVE                                # noqa: E402
from worldgen.world import RURAL_FACTOR                          # noqa: E402

# Даты берутся по одной из каждой полосы истории: так срезы не сбиваются
# в кучу и охватывают и первобытный мир, и закат.
BANDS = ((0.01, 0.19), (0.19, 0.38), (0.38, 0.58), (0.58, 0.79), (0.79, 0.999))

MALE_MARKS = ("Младший", "Старший", "Второй", "Третий", "Иной")
RANK_FORMS = (("импер", ("импер",)), ("герцог", ("герцог",)),
              ("княж", ("княз", "княг")), ("ханств", ("хан",)))


# ---------------------------------------------------------------------------
# Срезы
# ---------------------------------------------------------------------------

def race_name(race_id: str) -> str:
    race = RACES_BY_ID.get(race_id)
    return race.name if race else race_id


def polity_population(world, polity):
    total = count = 0
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        if settlement.polity_id == polity.id:
            total += int(settlement.population * RURAL_FACTOR)
            count += 1
    return total, count


def reign_at(world, polity, year: int):
    best = None
    for reign_id in polity.reign_ids:
        reign = world.reigns.get(reign_id)
        if reign is None or reign.start.year > year:
            continue
        if reign.end is not None and reign.end.year < year:
            continue
        if best is None or reign.start.ordinal > best.start.ordinal:
            best = reign
    return best


def ruler_line(world, polity, year: int) -> str:
    reign = reign_at(world, polity, year)
    if reign is None:
        return "престол пуст (междуцарствие)"
    figure = world.figures.get(reign.ruler_id)
    if figure is None:
        return "правитель неизвестен"
    house = world.houses.get(reign.house_id)
    parts = ["%s %s" % (reign.title or "правитель", figure.name),
             "%s, возраст %d" % (race_name(figure.race_id),
                                 year - figure.birth.year),
             "на престоле с %d (%s)" % (reign.start.year, reign.legitimacy)]
    if house is not None:
        parts.append("род %s" % house.full_name)
    if reign.traits or reign.skills:
        parts.append("нрав: %s" % ", ".join(part for part in (
            rulers.alignment_label(reign.alignment, figure.sex),
            rulers.traits_text(reign.traits, figure.sex)) if part))
    if reign.skills:
        parts.append("умения: " + "/".join(
            "%s %d" % (key, reign.skills.get(key, 5)) for key in rulers.SKILLS))
    return "; ".join(parts)


def nobility_line(world, polity, year: int) -> str:
    """Лестница знати державы и самые весомые дома на ней."""
    race = RACES_BY_ID.get(polity.race_id)
    if race is None or not race.has_nobility:
        return "знати нет"
    houses = [world.houses[hid] for hid in polity.house_ids
              if hid in world.houses and world.houses[hid].status == ACTIVE
              and world.houses[hid].id != polity.house_id]
    if not houses:
        return "знатных родов нет"
    steps = {}
    for house in houses:
        if house.rung >= 0:
            steps[house.rung] = steps.get(house.rung, 0) + 1
    ladder = "; ".join("%s — %d" % (arist.style_text(race, rung, "m"), count)
                       for rung, count in sorted(steps.items(), reverse=True))
    houses.sort(key=lambda h: (-h.prestige, h.id))
    top = ", ".join("%s (%s, %s%s)" % (
        house.full_name, house.style or "без титула",
        arist.alignment_word(house.alignment),
        ", недовольство %.2f" % house.discontent if house.discontent > 0.3 else "")
        for house in houses[:3])
    return "%s | верхушка: %s" % (ladder or "ступени не разведены", top)


def faith_line(world, faith_id: str) -> str:
    if not faith_id or faith_id not in world.faiths:
        return "государственной веры нет"
    faith = world.faiths[faith_id]
    deity = world.deities.get(faith.chief_deity_id)
    bits = ["«%s» (%s, %s%s)" % (faith.name,
                                 FAITH_KIND_NAMES.get(faith.kind, faith.kind),
                                 faith.status,
                                 ", ЗАПРЕЩЕНА" if faith.forbidden else "")]
    if deity is not None:
        domains = ", ".join(DOMAINS_BY_KEY[key].name for key in deity.domains
                            if key in DOMAINS_BY_KEY)
        bits.append("глава — %s %s (%s); сферы: %s"
                    % (deity.title, deity.full_name,
                       ALIGNMENT_NAMES.get(deity.alignment), domains))
    bits.append("верующих: %d" % faith.followers)
    return "; ".join(bits)


def snapshot(world, year: int, out) -> None:
    era = world.era_at(year)
    out("=" * 78)
    out("ГОД %d — %s (%d–%d)" % (year, era.name if era else "?",
                                 era.start_year if era else 0,
                                 era.end_year if era else 0))
    out("=" * 78)

    total = 0
    by_race = {}
    for settlement_id in world.active_settlements:
        settlement = world.settlements[settlement_id]
        souls = int(settlement.population * RURAL_FACTOR)
        total += souls
        by_race[settlement.race_id] = by_race.get(settlement.race_id, 0) + souls
    for tribe_id in world.active_tribes:
        tribe = world.tribes[tribe_id]
        total += tribe.population
        by_race[tribe.race_id] = by_race.get(tribe.race_id, 0) + tribe.population
    for camp_id in world.active_camps:
        camp = world.camps[camp_id]
        total += camp.population
        by_race[camp.race_id] = by_race.get(camp.race_id, 0) + camp.population

    out("Население мира: %d" % total)
    out("  по народам: " + ", ".join(
        "%s %d" % (race_name(key), value)
        for key, value in sorted(by_race.items(), key=lambda kv: -kv[1])[:10]))
    out("Живых: стран %d, городов %d, племён %d, лагерей %d, родов %d" % (
        len(world.active_polities), len(world.active_settlements),
        len(world.active_tribes), len(world.active_camps),
        len(world.active_houses)))

    dark = world.darkness_snapshot(year)
    if dark:
        out("Тёмные века: %d земель во мраке%s, тяжесть до %.2f" % (
            len([key for key in dark if key]),
            ", по всему миру" if dark.get("") else "", max(dark.values())))
    else:
        out("Тёмных веков нет.")

    live = [item for item in world.calamities.values()
            if item.start.year <= year and (item.end is None
                                            or item.end.year >= year)]
    if live:
        out("ИДУЩИЕ БЕДСТВИЯ (%d):" % len(live))
        for item in sorted(live, key=lambda c: -c.severity)[:5]:
            leader = world.figures.get(item.leader_id)
            out("   • %s [%s, %s] с %d г.%s" % (
                item.name, KIND_NAMES.get(item.kind, item.kind),
                SEVERITY_NAMES.get(item.severity), item.start.year,
                "; вождь %s" % leader.name if leader is not None else ""))
    else:
        out("Идущих бедствий нет.")

    running = [world.expeditions[x] for x in world.active_expeditions]
    if running:
        out("В пути: %s" % "; ".join("%s (%s)" % (x.name, x.target_name)
                                     for x in running[:3]))

    active = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        population, cities = polity_population(world, polity)
        active.append((population, cities, polity))
    active.sort(key=lambda row: -row[0])

    if not active:
        out("Стран ещё нет — мир племенной.")
        tribes = sorted((world.tribes[t] for t in world.active_tribes),
                        key=lambda t: -t.population)[:5]
        for tribe in tribes:
            region = world.regions.get(tribe.region_id)
            chief = world.figures.get(tribe.chief_id)
            out("   • %s (%s), %d душ, земля %s, вождь %s" % (
                tribe.full_name, race_name(tribe.race_id), tribe.population,
                region.name if region else "?",
                chief.name if chief else "—"))
    else:
        population, cities, polity = active[0]
        capital = world.settlements.get(polity.capital_id)
        out("КРУПНЕЙШАЯ СТРАНА: %s — %s" % (polity.full_name,
                                            race_name(polity.race_id)))
        out("   основана %s" % polity.founded.long())
        out("   население %d в %d городах; столица: %s" % (
            population, cities, capital.full_name if capital else "—"))
        out("   земли: %s" % ", ".join(
            "%s (%s)" % (world.regions[r].name, world.regions[r].terrain)
            for r in polity.region_ids if r in world.regions))
        out("   правитель: %s" % ruler_line(world, polity, year))
        out("   знать: %s" % nobility_line(world, polity, year))
        out("   наследование: %s" % SUCCESSION_NAMES.get(polity.succession,
                                                         polity.succession))
        if polity.peoples:
            out("   народы: %s" % pol.describe(polity, world))
        if polity.policy:
            out("   закон о народах: %s" % pol.POLICY_NAMES.get(polity.policy,
                                                                polity.policy))
        out("   вера: %s" % faith_line(world, polity.faith_id))
        out("ОСТАЛЬНЫЕ ДЕРЖАВЫ (всего %d):" % len(active))
        for population, cities, polity in active[1:7]:
            faith = world.faiths.get(polity.faith_id)
            out("   • %s (%s) — %d душ, %d городов; %s; вера: %s" % (
                polity.full_name, race_name(polity.race_id), population, cities,
                ruler_line(world, polity, year).split(";")[0],
                "«%s»" % faith.name if faith else "нет"))

    events = [e for e in world.events
              if year - 70 <= e.date.year <= year and e.importance >= 4]
    if events:
        out("ГРОМКИЕ СОБЫТИЯ ПОСЛЕДНИХ 70 ЛЕТ:")
        for event in sorted(events, key=lambda e: e.date.ordinal)[-8:]:
            out("   [%d] %s" % (event.date.year, event.title))
    out("")


# ---------------------------------------------------------------------------
# Разбор: что обычно ломается
# ---------------------------------------------------------------------------

def audit(world) -> list:
    """Ищет в готовом мире следы известных поломок.

    Возвращает список (важность, строка). Важность «!» — серьёзно,
    «·» — стоит посмотреть.
    """
    found = []

    def bad(line):
        found.append(("!", line))

    def note(line):
        found.append(("·", line))

    # 1. Мужской признак у женского имени и наоборот.
    wrong_sex = [f for f in world.figures.values() if f.sex == "f"
                 and any(mark in f.given_name for mark in MALE_MARKS)]
    if wrong_sex:
        bad("мужской признак у женских имён: %d (%s)"
            % (len(wrong_sex), wrong_sex[0].name))

    # 2. Титул против формы страны.
    mismatch = []
    for polity in world.polities.values():
        reign = world.current_reign(polity)
        if reign is None or not reign.title:
            continue
        form = polity.form.lower()
        title = reign.title.lower()
        for key, wanted in RANK_FORMS:
            if key in form and not any(w in title for w in wanted):
                mismatch.append("%s -> %s" % (polity.full_name, reign.title))
                break
    if mismatch:
        bad("титул не отвечает форме страны: %d (%s)"
            % (len(mismatch), mismatch[0]))

    # 3. Повторяющиеся имена там, где они должны быть своими.
    for label, values in (
            ("бедствий", [c.name for c in world.calamities.values()]),
            ("вер", [f.name for f in world.faiths.values()]),
            ("стран", [p.name for p in world.polities.values()]),
            ("городов", [s.name for s in world.settlements.values()]),
            ("походов", [x.name for x in world.expeditions.values()])):
        repeats = [name for name, count in Counter(values).items() if count > 1]
        if repeats:
            bad("повторяются имена %s: %d (%s)"
                % (label, len(repeats), repeats[0]))

    # 4. Один бог во главе слишком многих вер.
    chiefs = Counter(f.chief_deity_id for f in world.faiths.values()
                     if f.chief_deity_id)
    if chiefs:
        deity_id, count = chiefs.most_common(1)[0]
        share = count * 100.0 / max(1, len(world.faiths))
        if share > 20:
            deity = world.deities.get(deity_id)
            bad("один бог возглавляет %.0f%% вер мира (%s, %d из %d)"
                % (share, deity.given_name if deity else deity_id, count,
                   len(world.faiths)))

    # 5. Связь урона с длительностью: долгая беда не должна быть безобиднее
    #    короткой той же тяжести.
    by_severity = {}
    for item in world.calamities.values():
        if item.end is None or item.severity < 3:
            continue
        by_severity.setdefault(item.severity, []).append(item)
    for severity, items in sorted(by_severity.items()):
        if len(items) < 3:
            continue
        longest = max(items, key=lambda c: c.end.year - c.start.year)
        typical = sorted(c.deaths for c in items)[len(items) // 2]
        span = longest.end.year - longest.start.year
        if span > 200 and typical > 0 and longest.deaths < typical * 0.2:
            note("самое долгое бедствие тяжести %d (%s, %d лет) унесло %d — "
                 "меньше пятой части обычного (%d)"
                 % (severity, longest.name, span, longest.deaths, typical))

    # 6. Тяжёлое бедствие без единой жертвы.
    empty = [c for c in world.calamities.values()
             if c.severity >= 4 and c.deaths == 0 and c.end is not None]
    if empty:
        note("бедствий тяжести 4–5 без единой жертвы: %d (%s)"
             % (len(empty), empty[0].name))

    # 7. Падежные ловушки в текстах событий.
    #    «в Синяя Чащоба» — предлог и следом название в именительном.
    prepositional = re.compile(r"\b(?:в|на|из|от|к|у|о)\s+[А-ЯЁ][а-яё]+\s+"
                               r"[А-ЯЁ][а-яё]+\b")
    suspicious = []
    for event in world.events:
        for match in prepositional.finditer(event.text):
            phrase = match.group(0)
            # «в землях под именем X» и прочие обороты — законные.
            if any(word in phrase for word in ("имени", "именем", "краю")):
                continue
            suspicious.append((event.date.year, phrase))
            break
    if len(suspicious) > len(world.events) * 0.02:
        note("возможные падежные ошибки после предлога: %d случаев (%s)"
             % (len(suspicious), suspicious[0][1]))

    # 8. Правители как личности: у каждого правления должны быть нрав,
    #    умения и приговор истории, иначе короли снова станут переменными.
    reigns = [r for r in world.reigns.values() if r.end is not None]
    if reigns:
        faceless = [r for r in reigns if not r.skills]
        if faceless:
            bad("правлений без нрава и умений: %d из %d"
                % (len(faceless), len(reigns)))
        judged = [r for r in reigns
                  if (r.end.year - r.start.year) >= 8 and not r.verdict]
        if judged:
            bad("долгих правлений без приговора истории: %d" % len(judged))
        grades = Counter(r.verdict for r in reigns if r.verdict)
        if grades:
            top, count = grades.most_common(1)[0]
            if count > len(reigns) * 0.85:
                note("приговор «%s» стоит у %.0f%% правлений — оценка не "
                     "различает правителей" % (top, count * 100.0 / len(reigns)))
        # Черта нрава без женской формы выдала бы «королева, мстительный».
        unknown = set()
        for reign in reigns:
            for trait in reign.traits:
                if trait not in rulers.TRAIT_FEMALE:
                    unknown.add(trait)
        if unknown:
            bad("черты нрава без женской формы: %s" % ", ".join(sorted(unknown)))

    # 9. Знать как сила: в крупной старой державе лестница должна быть
    #    разведена, а дома — иметь нрав и достаток.
    grown = [p for p in world.polities.values()
             if len(p.house_ids) >= 4 and p.reign_ids]
    if grown:
        flat = [p for p in grown
                if not any(world.houses[h].rung >= 0 for h in p.house_ids
                           if h in world.houses)]
        if len(flat) > len(grown) * 0.5:
            note("держав со знатью, но без разведённой лестницы: %d из %d"
                 % (len(flat), len(grown)))
    faceless_houses = [h for h in world.houses.values() if not h.motto]
    if faceless_houses:
        bad("знатных родов без нрава и девиза: %d из %d"
            % (len(faceless_houses), len(world.houses)))

    # 10. Повторы текста — главное, из-за чего мир перестаёт читаться живым.
    sentences = Counter()
    for event in world.events:
        for piece in re.split(r"(?<=[.!?])\s+", event.text):
            piece = piece.strip()
            if len(piece) > 40:
                sentences[piece] += 1
    if sentences:
        total = sum(sentences.values())
        unique = len(sentences)
        top_text, top_count = sentences.most_common(1)[0]
        variety = unique * 100.0 / max(1, total)
        line = ("разнообразие фраз: %d различных на %d, самая частая "
                "повторена %d раз" % (unique, total, top_count))
        if variety < 25 or top_count > total * 0.02:
            note(line + " — «%s…»" % top_text[:60])
        else:
            found.append(("=", line))

    # 9. Мир, в котором ничего не выросло.
    if world.active_polities:
        biggest = max((world.polities[p].population
                       for p in world.active_polities), default=0)
        if biggest < 5000:
            note("крупнейшая держава к концу истории — %d душ" % biggest)
    elif world.total_years >= 3000:
        note("за всю историю не уцелело ни одной страны")

    return found


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

def pick_dates(total_years: int, count: int = 5) -> list:
    """Пять случайных дат, по одной из каждой полосы истории."""
    raw = os.urandom(8 * count)
    values = [struct.unpack(">Q", raw[i * 8:(i + 1) * 8])[0] for i in range(count)]
    dates = []
    for value, (low, high) in zip(values, BANDS[:count]):
        start = max(1, int(total_years * low))
        end = max(start + 1, int(total_years * high))
        dates.append(start + value % (end - start))
    return sorted(dates)


def main(argv) -> int:
    options = {"--seed": "", "--years": "10000", "--map": "", "--dates": "",
               "--out": "", "--regions": "18"}
    flags = set()
    index = 0
    while index < len(argv):
        key = argv[index]
        if key in options and index + 1 < len(argv):
            options[key] = argv[index + 1]
            index += 2
        else:
            flags.add(key)
            index += 1

    seed = options["--seed"] or random_seed_text()
    years = int(float(options["--years"]))
    dates = [int(x) for x in options["--dates"].split(",")] \
        if options["--dates"] else pick_dates(years)
    dates = [d for d in dates if 1 <= d <= years] or [years]

    lines = []

    def out(line=""):
        lines.append(line)

    settings = Settings(seed=seed, years=years, map_path=options["--map"],
                        regions=int(float(options["--regions"])))

    out("#" * 78)
    out("СТАНДАРТНЫЙ ТЕСТ ГЕНЕРАТОРА")
    out("  сид: %s" % seed)
    out("  длительность: %d лет" % years)
    out("  карта: %s" % (os.path.basename(options["--map"])
                         if options["--map"] else "процедурная"))
    out("  даты срезов: %s" % ", ".join(str(d) for d in dates))
    out("#" * 78)
    out("")

    targets = set(dates)
    from worldgen.systems import lives
    original = lives.tick

    def patched(ctx, year):
        original(ctx, year)
        if year in targets and "--quiet" not in flags:
            snapshot(ctx.world, year, out)

    lives.tick = patched
    try:
        world = generate(settings)
    finally:
        lives.tick = original

    out("#" * 78)
    out("ИТОГ")
    out("#" * 78)
    for key, value in world.stats().items():
        out("  %-28s %s" % (key, value))
    out("")

    out("#" * 78)
    out("РАЗБОР")
    out("#" * 78)
    findings = audit(world)
    serious = [row for row in findings if row[0] == "!"]
    for mark, line in findings:
        out("  %s %s" % (mark, line))
    if not findings:
        out("  всё чисто")
    out("")
    out("  серьёзных аномалий: %d" % len(serious))

    text = "\n".join(lines)
    if options["--out"]:
        with open(options["--out"], "w", encoding="utf-8") as handle:
            handle.write(text)
        print("Записано в %s (серьёзных аномалий: %d)"
              % (options["--out"], len(serious)))
    else:
        print(text)
    return 1 if serious else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
