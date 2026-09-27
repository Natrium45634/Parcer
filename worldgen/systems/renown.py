# -*- coding: utf-8 -*-
"""Сколько человек весит в истории — и как это меняется после смерти.

Вес не назначается по должности. Он **считается по следам**, которые
человек оставил в самом мире: по событиям, где он действовал, по годам
правления, по основанным державам, городам и верам, по законам, вещам,
сказаниям, былям и потомкам. Поэтому король, тридцать лет правивший и
ничего не переменивший, оказывается ниже пахаря, который однажды успел
предупредить город.

Считается это после жизни, а не при рождении: пока человек жив, о нём
известно только то, насколько громко о нём говорят. Итог подводится
сотню лет спустя, когда видно, что из сделанного удержалось.

И главное — **вес продолжает меняться**. Раз в двести пятьдесят лет
потомки пересматривают имя. Память тает сама, пока её не держит
что-нибудь настоящее: держава, род, город, закон, вера, песня. Нашли
записи, довели до конца его начатое, всплыла его вещь — имя поднялось.
Держава рассыпалась, род пресёкся, песню петь перестали — осело. Слава
при жизни и нынешняя память с этого часа живут врозь.
"""

from __future__ import annotations

from .. import artifacts as artifacts_cat
from .. import lifepaths as life_cat
from .. import tales as tales_cat
from .. import narrative_renown as texts
from .. import renown as cat
from ..models import ACTIVE, RUINED

SWEEP_PERIOD = 100         # раз в сто лет мир подводит итог именам
MIN_SCORE = 9.0            # ниже этого имя не взвешивают вовсе
MAX_TRACKED = 6000         # и больше стольких мир не держит в памяти
FADE = 0.86                # во столько раз тает память за пересмотр
# Вес и память — разные вещи, и меняются они по-разному. Память тает
# сама; ступень стоит, пока не появится настоящая причина её двинуть:
# нашли записи, докончили начатое — вверх; выяснилось, что сделал это
# не он, — вниз. И ниже трёх ступеней от своего пика имя не падает:
# дела никуда не делись, просто их перестали помнить.
RAISE_RATE = 0.25
LOWER_RATE = 0.07
FLOOR_GAP = 3


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if year % SWEEP_PERIOD:
        return
    rng = ctx.rng("renown", year)
    index = _index(world)

    # 1. Имена тех, кто умер за этот век.
    fresh = 0
    for figure in world.figures.values():
        if figure.death is None or figure.death.year > year:
            continue
        if figure.death.year <= year - SWEEP_PERIOD:
            continue
        # Отсев прежде счёта: у большинства людей нет ни одного дела в
        # летописи, ни звания, ни прослеженной жизни. Их и взвешивать
        # незачем — это и правда о мире, и скорость.
        if not figure.deeds and not figure.titles and not figure.roles \
                and world.path_of(figure.id) is None:
            continue
        if world.renown_of(figure.id) is not None:
            continue
        if _weigh(ctx, rng, index, figure, year) is not None:
            fresh += 1
        if fresh > 400:
            break

    # 2. И пересмотр уже записанных: имена живут своей жизнью.
    for weight in sorted(world.renowns.values(), key=lambda item: item.id):
        last = weight.reviews[-1]["год"] if weight.reviews else weight.died_year
        if year - last < cat.REVIEW_STEP:
            continue
        _review(ctx, rng, index, weight, year)


# ---------------------------------------------------------------------------
# Указатель следов: один проход на весь век
# ---------------------------------------------------------------------------

def _index(world) -> dict:
    """Кто что после себя оставил — собранное разом.

    Спрашивать про каждого человека отдельно значило бы перебирать весь
    мир тысячу раз. Один проход по реестрам даёт то же самое.
    """
    out = {
        "держава": {}, "город": {}, "вера": {}, "род": {}, "вещь": {},
        "правление": {}, "храм": {}, "предание": {}, "ремесло": {},
        "сказание": {}, "быль": {}, "курган": {}, "товарищество": {},
    }
    for polity in world.polities.values():
        if polity.founder_id:
            out["держава"].setdefault(polity.founder_id, []).append(polity)
    for settlement in world.settlements.values():
        if settlement.founder_id:
            out["город"].setdefault(settlement.founder_id,
                                    []).append(settlement)
    for faith in world.faiths.values():
        if faith.founder_id:
            out["вера"].setdefault(faith.founder_id, []).append(faith)
    for house in world.houses.values():
        if house.founder_id:
            out["род"].setdefault(house.founder_id, []).append(house)
    for artifact in world.artifacts.values():
        if artifact.maker_id:
            out["вещь"].setdefault(artifact.maker_id, []).append(artifact)
    for reign in world.reigns.values():
        if reign.ruler_id:
            out["правление"].setdefault(reign.ruler_id, []).append(reign)
    for temple in world.temples.values():
        if temple.founder_id:
            out["храм"].setdefault(temple.founder_id, []).append(temple)
    for legend in world.legends.values():
        if legend.subject_id:
            out["предание"].setdefault(legend.subject_id, []).append(legend)
    for discovery in world.discoveries.values():
        if getattr(discovery, "figure_id", ""):
            out["ремесло"].setdefault(discovery.figure_id,
                                      []).append(discovery)
    for tale in world.tales.values():
        for item in tale.company:
            out["сказание"].setdefault(item.get("кто", ""), []).append(tale)
    for story in world.stories.values():
        for item in story.cast:
            out["быль"].setdefault(item.get("кто", ""), []).append(story)
    for site in world.sites.values():
        if site.figure_id:
            out["курган"].setdefault(site.figure_id, []).append(site)
    for guild in world.guilds.values():
        founder = getattr(guild, "founder_id", "")
        if founder:
            out["товарищество"].setdefault(founder, []).append(guild)
    out["закон"] = {}
    for law in world.laws.values():
        if law.ruler_id:
            out["закон"].setdefault(law.ruler_id, []).append(law)
    return out


# ---------------------------------------------------------------------------
# Счёт дел
# ---------------------------------------------------------------------------

def _weigh(ctx, rng, index, figure, year: int):
    """Собрать вес человека из того, что он на самом деле оставил."""
    world = ctx.world
    score = 0.0
    influence = {}
    foots = []
    roles = []

    def add(kind: str, value: float, what: str, entity_id: str = "",
            role: str = "") -> None:
        nonlocal score
        score += value
        where = cat.FOOT_INFLUENCE.get(kind)
        if where:
            influence[where] = influence.get(where, 0.0) + value
        foots.append({"вид": kind, "что": what, "id": entity_id, "жив": True})
        if role and role not in roles:
            roles.append(role)

    # --- события, где он действовал -----------------------------------
    loud = 0
    for event_id in figure.deeds[:120]:
        event = world.event(event_id)
        if event is None:
            continue
        weight = (event.importance ** 1.7) * 0.5
        score += weight
        influence[_event_influence(event.kind)] = \
            influence.get(_event_influence(event.kind), 0.0) + weight
        if event.importance >= 4:
            loud += 1

    # --- что после него осталось ---------------------------------------
    for polity in index["держава"].get(figure.id, ())[:4]:
        add(cat.FOOT_STATE, cat.FOOT_WEIGHT[cat.FOOT_STATE], polity.name,
            polity.id, "основатель")
    for settlement in index["город"].get(figure.id, ())[:6]:
        add(cat.FOOT_CITY, cat.FOOT_WEIGHT[cat.FOOT_CITY], settlement.name,
            settlement.id, "основатель")
    for faith in index["вера"].get(figure.id, ())[:3]:
        add(cat.FOOT_FAITH, cat.FOOT_WEIGHT[cat.FOOT_FAITH], faith.name,
            faith.id, "еретик" if faith.kind == "ересь" else "пророк")
    for house in index["род"].get(figure.id, ())[:3]:
        add(cat.FOOT_HOUSE, cat.FOOT_WEIGHT[cat.FOOT_HOUSE], house.name,
            house.id, "основатель")
    for artifact in index["вещь"].get(figure.id, ())[:5]:
        add(cat.FOOT_THING, cat.FOOT_WEIGHT[cat.FOOT_THING], artifact.name,
            artifact.id, "изобретатель")
    for discovery in index["ремесло"].get(figure.id, ())[:4]:
        add(cat.FOOT_CRAFT, cat.FOOT_WEIGHT[cat.FOOT_CRAFT], discovery.name,
            discovery.id, "изобретатель")
    for temple in index["храм"].get(figure.id, ())[:3]:
        add(cat.FOOT_FAITH, cat.FOOT_WEIGHT[cat.FOOT_FAITH] * 0.4,
            temple.name, temple.id)
    for legend in index["предание"].get(figure.id, ())[:4]:
        add(cat.FOOT_LEGEND, cat.FOOT_WEIGHT[cat.FOOT_LEGEND], legend.name,
            legend.id)
    for guild in index["товарищество"].get(figure.id, ())[:2]:
        add(cat.FOOT_GUILD, cat.FOOT_WEIGHT[cat.FOOT_GUILD], guild.name,
            guild.id, "основатель")
    for site in index["курган"].get(figure.id, ())[:2]:
        add(cat.FOOT_STONE, cat.FOOT_WEIGHT[cat.FOOT_STONE], site.name,
            site.id)

    # --- правления: долгий государь весит больше короткого -------------
    ruled = 0
    for reign in index["правление"].get(figure.id, ()):
        years = max(0, (reign.end.year if reign.end else year)
                    - reign.start.year)
        ruled += years
        polity = world.polities.get(reign.polity_id)
        value = 3.0 + years * 0.22
        if polity is not None:
            value += min(12.0, len(polity.settlement_ids) * 0.5)
        score += value
        influence[cat.POWER] = influence.get(cat.POWER, 0.0) + value
    if ruled >= 25:
        roles.append("самовластец" if figure.alignment <= -2 else "хранитель")

    # --- законы: их пишут не все ---------------------------------------
    for law in index["закон"].get(figure.id, ())[:5]:
        add(cat.FOOT_LAW, cat.FOOT_WEIGHT[cat.FOOT_LAW], law.name, law.id,
            "преобразователь")

    # --- сказания и были ------------------------------------------------
    for tale in index["сказание"].get(figure.id, ())[:6]:
        value = 6.0 + 4.0 * float(getattr(tale, "fame", 0.0))
        score += value
        influence[cat.CULTURE] = influence.get(cat.CULTURE, 0.0) + value
        if "спаситель" not in roles and tale.outcome in (tales_cat.WON,
                                                         tales_cat.COSTLY):
            roles.append("спаситель")
    for story in index["быль"].get(figure.id, ())[:8]:
        value = 1.0 + story.epicity * 1.2
        score += value
        influence[cat.ORDER] = influence.get(cat.ORDER, 0.0) + value

    # --- кровь и потомки -------------------------------------------------
    kin = len([child for child in figure.children
               if child in world.figures])
    if kin:
        value = min(10.0, kin * 1.6)
        add(cat.FOOT_KIN, value, "%d потомков в мире" % kin, "")

    # --- жизненный путь: чего хотел и что вышло --------------------------
    path = world.path_of(figure.id)
    if path is not None:
        score += _path_value(path)
        if path.state in life_cat.GOOD_ENDS:
            influence[cat.ORDER] = influence.get(cat.ORDER, 0.0) + 4.0
        for item in path.subgoals:
            if item.get("состояние") in (life_cat.FAILED,
                                         life_cat.GIVEN_UP):
                foots.append({"вид": cat.FOOT_UNDONE, "что": item.get("что", ""),
                              "id": "", "жив": True})
                score += 2.0
                break

    if score < MIN_SCORE:
        return None
    if len(world.renowns) >= MAX_TRACKED and not _make_room(world, year):
        return None

    level = cat.level_for(score)
    fame = _fame_of(score, loud, path)
    weight = world.add_renown(
        figure_id=figure.id,
        born_year=figure.birth.year if figure.birth else 0,
        died_year=figure.death.year if figure.death else year,
        level=level, peak_level=level,
        peak_year=figure.death.year if figure.death else year,
        score=round(score, 2), fame=fame, memory=fame,
        influence={name: int(min(100, value * 2.2))
                   for name, value in influence.items() if value >= 1.0},
        footprint=foots[:14], legacy_alive=bool(foots))
    weight.unique = _uniqueness(weight, ruled, loud)
    weight.roles = _roles(figure, weight, roles, path)[:4]
    # Вершина считается прежде судьбы: по ней и видно, был ли это
    # поздний расцвет или взлёт с падением.
    weight.climax = _climax(ctx, rng, figure, weight)
    weight.destiny = _destiny(ctx, figure, weight, path, year)
    weight.aura = rng.choice([key for key, _ in cat.AURAS])
    weight.voices = _voices(ctx, rng, figure, weight, path)
    return weight


def _make_room(world, year: int) -> bool:
    """Освободить место в памяти мира под новые имена.

    Память не бесконечна: когда мест не остаётся, из неё выпадают те,
    кого давно не помнят и от кого ничего не осталось. Это и есть
    забвение — оно и в мире так работает.
    """
    doomed = []
    for weight in world.renowns.values():
        if weight.level >= 4 or weight.legacy_alive:
            continue
        if year - weight.died_year < 500:
            continue
        doomed.append(weight)
    if not doomed:
        return False
    doomed.sort(key=lambda item: (item.level, item.memory, item.score,
                                  item.id))
    for weight in doomed[:200]:
        world.renowns.pop(weight.id, None)
        world._renown_of.pop(weight.figure_id, None)
    return True


def _event_influence(kind: str) -> str:
    """К какому влиянию отнести событие такого рода."""
    for needle, where in EVENT_INFLUENCE:
        if needle in kind:
            return where
    return cat.POWER


EVENT_INFLUENCE = (
    ("war", cat.WAR), ("battle", cat.WAR), ("siege", cat.WAR),
    ("raid", cat.WAR), ("monster", cat.WAR),
    ("faith", cat.FAITH), ("temple", cat.FAITH), ("schism", cat.FAITH),
    ("deity", cat.FAITH), ("divine", cat.COSMOS), ("mythic", cat.COSMOS),
    ("craft", cat.CRAFT), ("discovery", cat.CRAFT), ("artifact", cat.CRAFT),
    ("trade", cat.WEALTH), ("guild", cat.WEALTH), ("route", cat.WEALTH),
    ("settlement", cat.PEOPLE), ("colony", cat.PEOPLE),
    ("migration", cat.PEOPLE), ("famine", cat.PEOPLE),
    ("law", cat.ORDER), ("reform", cat.ORDER), ("strife", cat.ORDER),
    ("expedition", cat.LAND), ("region", cat.LAND),
    ("dynasty", cat.BLOOD), ("marriage", cat.BLOOD), ("birth", cat.BLOOD),
    ("tale", cat.CULTURE), ("legend", cat.CULTURE), ("lore", cat.CULTURE),
    ("story", cat.CULTURE), ("magic", cat.MAGIC),
)


def _path_value(path) -> float:
    """Чего стоит прожитая жизнь сама по себе.

    Сюда входит не только удача: провал большой цели тоже весит, потому
    что после него остаётся след — брошенное дело, ученики, обида.
    """
    value = 2.0 + 1.2 * float(path.steps_done)
    if path.state in life_cat.GOOD_ENDS:
        value += 6.0
    if path.fame in (life_cat.GREAT, life_cat.HISTORIC):
        value += 10.0
    if path.irony:
        value += 3.0
    return value


def _fame_of(score: float, loud: int, path) -> int:
    """Насколько громко о нём знали при жизни.

    Слава — не то же самое, что вес: о ком-то гремели при жизни, а он
    ничего не оставил, и наоборот.
    """
    fame = min(100.0, score * 0.9 + loud * 6.0)
    if path is not None and path.fame in (life_cat.GREAT, life_cat.HISTORIC):
        fame = min(100.0, fame + 18.0)
    return int(max(1.0, fame))


def _uniqueness(weight, ruled: int, loud: int) -> float:
    """Насколько трудно заменить этого человека другим.

    Долгое правление заменимо: на престоле был бы кто-то другой. А вот
    редкое дело — основанная вера, выкованная вещь, открытое ремесло —
    без него могло не случиться вовсе.
    """
    rare = sum(1 for item in weight.footprint
               if item["вид"] in (cat.FOOT_FAITH, cat.FOOT_CRAFT,
                                  cat.FOOT_SPELL, cat.FOOT_THING,
                                  cat.FOOT_SCHOOL, cat.FOOT_LEGEND))
    value = 0.15 + 0.14 * rare + 0.05 * loud
    if ruled >= 30:
        value -= 0.12
    # Чем выше человек поднялся, тем труднее представить на его месте
    # кого-то ещё: такие дела в одну жизнь укладываются не у всякого.
    value += 0.09 * max(0, weight.level - 5)
    return round(max(0.0, min(1.0, value)), 2)


def _roles(figure, weight, roles: list, path) -> list:
    """Чем человек оказался для истории — по делам, а не по званию."""
    out = list(roles)
    if weight.level >= 7 and "спаситель" not in out:
        out.append("спаситель" if figure.alignment >= 1
                   else "приносящий беду")
    if figure.death_cause and "убит" in figure.death_cause \
            and figure.alignment >= 1 and "мученик" not in out:
        out.append("мученик")
    if path is not None:
        if path.state in (life_cat.FAILED, life_cat.GIVEN_UP):
            out.append("последний защитник" if figure.alignment >= 1
                       else "смутьян")
        if "дорог" in path.wish or "земл" in path.wish:
            out.append("первопроходец")
    if any(item["вид"] == cat.FOOT_STATE for item in weight.footprint) \
            and "объединитель" not in out:
        out.append("объединитель")
    return out


def _destiny(ctx, figure, weight, path, year: int) -> str:
    """Какой формы вышла жизнь.

    Форма берётся из того, что о человеке и так известно: сколько он
    прожил, когда была его вершина, чем кончилась его цель, кем он
    приходился знаменитой родне и что после него осталось.
    """
    world = ctx.world
    lived = (figure.death.year - figure.birth.year) if figure.death \
        and figure.birth else 0
    climax = int(weight.climax.get("год", 0)) if weight.climax else 0
    age_at_peak = climax - figure.birth.year if figure.birth and climax else 0

    if weight.level >= 4 and lived and lived < 35:
        return "ранняя смерть"
    if path is not None and path.state in (life_cat.FAILED,
                                           life_cat.GIVEN_UP) \
            and weight.level >= 4:
        return "несостоявшееся величие"
    if path is not None and path.irony:
        return "нашёл и потерял"
    if any(item["вид"] == cat.FOOT_UNDONE for item in weight.footprint) \
            and weight.level >= 3:
        return "посмертный успех"
    if age_at_peak and lived and age_at_peak > lived * 0.75 and lived > 45:
        return "поздний расцвет"
    if age_at_peak and lived and age_at_peak < lived * 0.35 and lived > 40:
        return "взлёт и падение"
    # Родня: жизнь рядом со знаменитым отцом или братом — своя форма.
    for kin_id in (figure.father_id, figure.mother_id):
        kin = world.renown_of(kin_id) if kin_id else None
        if kin is not None and kin.level >= weight.level + 2:
            return "в чужой тени"
    if figure.death_cause and ("убит" in figure.death_cause
                               or "казн" in figure.death_cause):
        return "жизнь ради мести" if "месть" in (path.wish if path else "") \
            else ("ложный герой" if weight.unique < 0.2 and weight.level >= 4
                  else "взлёт и падение")
    if weight.unique >= 0.5 and weight.level <= 3:
        return "забытый гений"
    if path is not None and path.state in life_cat.GOOD_ENDS \
            and weight.level >= 5:
        return "продолжатель" if path.steps_done <= 2 else "ровная жизнь"
    if not figure.children and figure.house_id and weight.level >= 3:
        return "последний в роду"
    return "ровная жизнь"


def _climax(ctx, rng, figure, weight) -> dict:
    """Вершина жизни — не обязательно смерть и не обязательно победа."""
    world = ctx.world
    best, best_value = None, 0
    for event_id in figure.deeds[:120]:
        event = world.event(event_id)
        if event is not None and event.importance > best_value:
            best, best_value = event, event.importance
    if best is not None:
        return {"год": best.date.year, "что": best.title,
                "вид": rng.choice(cat.CLIMAXES)}
    return {"год": weight.died_year, "что": rng.choice(cat.CLIMAXES),
            "вид": "итог"}


def _voices(ctx, rng, figure, weight, path) -> dict:
    """Шесть голосов об одном человеке.

    Первый — как было; остальные пять расходятся с ним по-своему, и
    расходятся не случайно: держава льстит, враги чернят, песня
    переделывает, потомки пересматривают.
    """
    was = path.did if path is not None and path.did \
        else rng.choice(texts.DEEDS_AS_WAS)
    out = {cat.AS_WAS: was}
    for voice in cat.VOICES[1:]:
        out[voice] = texts.voice_line(rng, voice, was)
    return out


# ---------------------------------------------------------------------------
# Пересмотр: имя живёт дольше человека
# ---------------------------------------------------------------------------

def _review(ctx, rng, index, weight, year: int) -> None:
    """Что потомки думают об этом имени теперь."""
    world = ctx.world
    figure = world.figures.get(weight.figure_id)
    if figure is None:
        return
    alive = _footprint_alive(world, weight)
    before = weight.level

    # Память тает сама; её держит только то, что ещё стоит.
    keep = 1.0 + 0.09 * alive
    weight.memory = int(max(0, min(100, weight.memory * FADE * keep)))

    shift, why = 0, ""
    if alive >= 2 and rng.chance(RAISE_RATE):
        shift, why = 1, rng.choice(cat.RAISED)
    elif alive == 0 and rng.chance(LOWER_RATE):
        shift, why = -1, rng.choice(cat.LOWERED)

    floor = max(0, weight.peak_level - FLOOR_GAP)
    # Потолок: пересмотр поднимает имя, но не делает из старосты
    # переменившего мироздание. Выше двух ступеней над тем, что человек
    # взял при жизни, поднимает только настоящая находка — быль.
    # Девятая и десятая ступени не даются пересмотром: их зарабатывают
    # при жизни, и потому их единицы на весь мир.
    ceiling = min(8, _born_level(weight) + 2)
    if shift:
        weight.level = max(floor, min(ceiling, weight.level + shift))
        if weight.level == before:
            shift, why = 0, ""
    if shift:
        if weight.level > weight.peak_level:
            weight.peak_level, weight.peak_year = weight.level, year
        weight.reviews.append({"год": int(year), "было": before,
                               "стало": weight.level, "почему": why})
        if shift > 0:
            weight.memory = int(min(100, weight.memory + 12))
            # Поднявшееся имя мир замечает — но не всякое: в летопись
            # идёт только то, что поднялось высоко.
            if weight.level >= 7 and rng.chance(0.4):
                _tell(ctx, weight, figure, year, before, why)
    weight.legacy_alive = alive > 0
    if not weight.reviews or weight.reviews[-1]["год"] != year:
        weight.reviews.append({"год": int(year), "было": before,
                               "стало": weight.level,
                               "почему": "имя осталось при своём"})


def _born_level(weight) -> int:
    """Какую ступень он взял при жизни, до всяких пересмотров."""
    if weight.reviews:
        return int(weight.reviews[0].get("было", weight.level))
    return weight.level


def _footprint_alive(world, weight) -> int:
    """Сколько следов этого человека ещё стоит в мире."""
    alive = 0
    for item in weight.footprint:
        kind, entity_id = item.get("вид"), item.get("id", "")
        standing = True
        if kind == cat.FOOT_STATE:
            polity = world.polities.get(entity_id)
            standing = polity is not None and polity.status == ACTIVE
        elif kind == cat.FOOT_CITY:
            settlement = world.settlements.get(entity_id)
            standing = settlement is not None and settlement.status != RUINED
        elif kind == cat.FOOT_FAITH:
            faith = world.faiths.get(entity_id)
            standing = faith is not None and faith.status != "забыта"
        elif kind == cat.FOOT_HOUSE:
            house = world.houses.get(entity_id)
            standing = house is not None and house.status == "активно"
        elif kind == cat.FOOT_THING:
            artifact = world.artifacts.get(entity_id)
            standing = artifact is not None \
                and artifact.status != artifacts_cat.DESTROYED
        elif kind == cat.FOOT_LAW:
            law = world.laws.get(entity_id)
            polity = world.polities.get(law.polity_id) if law else None
            # Закон живёт, пока жива держава, которая его завела, — или
            # пока его переняли соседи.
            standing = law is not None and (
                bool(law.copied_by)
                or (polity is not None and polity.status == ACTIVE))
        elif kind == cat.FOOT_LEGEND:
            standing = entity_id in world.legends
        elif kind == cat.FOOT_GUILD:
            guild = world.guilds.get(entity_id)
            standing = guild is not None \
                and getattr(guild, "status", ACTIVE) == ACTIVE
        elif kind == cat.FOOT_KIN:
            # Потомки — след недолгий: род пресёкся, и вспоминать некому.
            figure = world.figures.get(weight.figure_id)
            standing = bool(figure is not None
                            and _kin_alive(world, figure, weight))
        item["жив"] = bool(standing)
        if standing:
            alive += 1
    return alive


def _kin_alive(world, figure, weight) -> bool:
    """Остался ли кто-то из его крови — хотя бы внук."""
    seen, wave = set(), list(figure.children)
    for _ in range(3):          # дальше правнуков не считаем: дорого
        nxt = []
        for child_id in wave:
            if child_id in seen:
                continue
            seen.add(child_id)
            child = world.figures.get(child_id)
            if child is None:
                continue
            if child.death is None:
                return True
            nxt.extend(child.children)
        wave = nxt
        if not wave:
            break
    return False


def _tell(ctx, weight, figure, year: int, before: int, why: str) -> None:
    """Имя, поднявшееся из небытия, — это событие."""
    world = ctx.world
    rng = ctx.rng("renown-events", year)
    date = ctx.date_in(rng, year)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="name_weighed",
        title="Имя из прошлого: %s" % figure.plain_name,
        text="%s Теперь его ставят на %d ступень, прежде стояло %d."
             % (texts.cap(texts.review_line(rng, before, weight.level, why)),
                weight.level, before),
        importance=3, subjects=[figure.id], race_id=figure.race_id)
    weight.event_ids.append(event.id)


__all__ = ["upkeep"]
