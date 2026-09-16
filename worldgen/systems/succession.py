# -*- coding: utf-8 -*-
"""Престолонаследие: правления, наследники, регентства и перевороты.

Каждая страна ведёт список правлений. Когда правитель умирает, наследник
определяется по закону его народа (см. dynasty.py). Если наследника нет —
род пресекается и престол переходит другому дому или вовсе пустует.

Отдельно живёт своей жизнью придворная интрига: дворцовые перевороты,
узурпации, поединки за власть, низложения советом и раскрытые заговоры.
"""

from __future__ import annotations

from . import houses as houses_mod
from .. import dynasty
from .. import narrative_dynasty as texts
from .. import races as races_mod
from ..models import ACTIVE, GREAT, ROYAL
from ..timeline import Date

# Вероятность придворной смуты считается не «раз в столько-то лет вообще»,
# а по сумме неустойчивости всех престолов мира. Иначе в юном мире, где
# стоят две тихие эльфийские державы, все заговоры сыпались бы на них.
COUP_PER_INSTABILITY = 0.008
COUP_MAX_RATE = 0.5
ABDICATION_SHARE = 0.08       # доля попыток, оборачивающихся отречением
CHILD_MORTALITY = 0.18        # доля детей, не доживающих до совершеннолетия
DYNASTIC_MARRIAGE = 0.45      # доля браков между знатными родами


# ---------------------------------------------------------------------------
# Годовой такт
# ---------------------------------------------------------------------------

def tick(ctx, year: int) -> None:
    world = ctx.world
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        _check_throne(ctx, polity, year)
    _tick_regency(ctx, year)
    _maybe_intrigue(ctx, year)


def _check_throne(ctx, polity, year: int) -> None:
    world = ctx.world
    reign = world.current_reign(polity)
    ruler = world.figures.get(polity.ruler_id)

    if ruler is not None and ruler.alive_at(year) and reign is not None and reign.end is None:
        return

    rng = ctx.rng("throne", polity.id, year)
    if reign is not None and reign.end is None and ruler is not None:
        death_date = ruler.death or ctx.date_in(rng, year)
        _close_reign(world, reign, death_date, "смерть")
        years_ruled = max(0, death_date.year - reign.start.year)
        if years_ruled >= 1 or rng.chance(0.5):
            title, text = texts.ruler_death(rng, polity, ruler, years_ruled,
                                            ruler.death_cause)
            world.add_event(
                date=death_date, era_index=world.era_index_at(year),
                kind="ruler_death", title=title, text=text, importance=2,
                actors=[ruler.id], subjects=[polity.id], race_id=polity.race_id,
            )

    after = ruler.death if (ruler is not None and ruler.death is not None) else None
    _succeed(ctx, polity, year, after, rng)


def _close_reign(world, reign, date: Date, reason: str) -> None:
    if reign is None or reign.end is not None:
        return
    reign.end = date
    reign.end_reason = reason


# ---------------------------------------------------------------------------
# Наследование
# ---------------------------------------------------------------------------

def _succeed(ctx, polity, year: int, after: Date, rng) -> None:
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    law = polity.succession or race.succession_for(polity.form)
    ruler = world.figures.get(polity.ruler_id)

    date = ctx.date_in(rng, year, after)
    choice = dynasty.choose_heir(world, rng, polity, ruler, race, law, year)

    if choice is None:
        choice = _new_dynasty(ctx, polity, race, year, date, rng)
    if choice is None:
        if not polity.interregnum:
            polity.interregnum = True
            title, text = texts.interregnum(rng, polity)
            world.add_event(
                date=date, era_index=world.era_index_at(year), kind="interregnum",
                title=title, text=text, importance=3, subjects=[polity.id],
                race_id=polity.race_id,
            )
        return

    old_house = world.houses.get(polity.house_id)
    enthrone(ctx, polity, choice.figure, date, year, choice,
             legitimacy="избрание" if choice.law == races_mod.ELECTIVE else "законное",
             old_house=old_house, rng=rng)


def _new_dynasty(ctx, polity, race, year: int, date, rng):
    """Правящий род пресёкся — ищем, кому отдать корону."""
    world = ctx.world
    pairs = []
    for house in world.houses_of_polity(polity):
        if house.id == polity.house_id:
            continue
        head = world.figures.get(house.head_id)
        if head is None or not head.alive_at(year):
            continue
        if head.age_at(year) < race.adulthood:
            continue
        pairs.append((head, max(0.2, house.prestige)))
    if pairs:
        heir = rng.weighted(pairs)
        return dynasty.HeirChoice(heir, "чужачка" if heir.sex == "f" else "чужак",
                                  other_house=True, law=polity.succession)

    # Знати не осталось вовсе — власть берёт кто-то из горожан.
    seats = [world.settlements[sid] for sid in polity.settlement_ids
             if sid in world.settlements and world.settlements[sid].status == ACTIVE]
    if not seats:
        return None
    seat = rng.choice(sorted(seats, key=lambda s: s.id))
    sex = "f" if rng.chance(0.4) else "m"
    upstart = ctx.make_figure(
        rng, race, year, role="новая кровь", region_id=seat.region_id,
        title=ctx.ruler_title(polity, race, sex), sex=sex, home_id=seat.id,
        epithet_chance=0.8)
    houses_mod.found_house(ctx, upstart, year, date, seat=seat, rank=GREAT,
                           polity=polity, importance=2)
    return dynasty.HeirChoice(upstart, "чужачка" if sex == "f" else "чужак",
                              other_house=True, law=polity.succession,
                              note="корона досталась человеку без рода и имени")


def enthrone(ctx, polity, heir, date: Date, year: int, choice,
             legitimacy: str = "законное", old_house=None, rng=None,
             announce: bool = True, kind: str = "accession") -> None:
    """Сажает наследника на престол и открывает новое правление."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    rng = rng or ctx.rng("enthrone", polity.id, year)
    capital = world.settlements.get(polity.capital_id)

    house = world.houses.get(heir.house_id)
    if house is None:
        house = houses_mod.found_house(ctx, heir, year, date, seat=capital,
                                       rank=ROYAL, polity=polity, importance=2)
    changed_dynasty = bool(old_house is not None and house is not None
                           and house.id != old_house.id)

    if house is not None and polity.house_id != house.id:
        houses_mod.make_royal(ctx, house, polity, year, date, announce=False)
    elif house is not None:
        houses_mod.attach(world, house, polity)

    heir.regnal_number = _regnal_number(world, polity, heir)
    ruler_title = ctx.ruler_title(polity, race, heir.sex)
    if ruler_title in heir.titles:
        heir.titles.remove(ruler_title)
    heir.titles.insert(0, ruler_title)
    if "правитель" not in heir.roles:
        heir.roles.append("правитель")
    heir.home_id = polity.capital_id or heir.home_id

    polity.ruler_id = heir.id
    polity.interregnum = False

    needs_regent = getattr(choice, "needs_regent", False)
    regent = None
    regency_until = 0
    if needs_regent:
        regent = dynasty.pick_regent(world, rng, polity, heir, race, year)
        regency_until = heir.birth.year + race.adulthood

    reign = world.add_reign(
        polity_id=polity.id, ruler_id=heir.id,
        house_id=house.id if house is not None else "",
        start=date, number=len(polity.reign_ids) + 1,
        regent_id=regent.id if regent is not None else "",
        regency_until=regency_until, legitimacy=legitimacy, title=ruler_title,
    )

    ensure_family(ctx, heir, year, polity=polity)

    if announce:
        if changed_dynasty and house is not None:
            title, text = texts.dynasty_change(rng, polity, house, heir, old_house)
            importance = 4
            kind = "dynasty_change"
        else:
            title, text = texts.accession(rng, polity, heir, choice, capital, race,
                                          first=(reign.number == 1))
            importance = 2
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind=kind,
            title=title, text=text, importance=importance, actors=[heir.id],
            subjects=[polity.id] + ([house.id] if house is not None else []),
            region_id=polity.capital_id and capital.region_id or "",
            race_id=polity.race_id,
        )

    if regent is not None:
        title, text = texts.regency_start(rng, polity, heir, regent, regency_until)
        if "регент" not in regent.roles:
            regent.roles.append("регент")
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="regency_start",
            title=title, text=text, importance=3,
            actors=[regent.id, heir.id], subjects=[polity.id],
            race_id=polity.race_id,
        )


def _regnal_number(world, polity, heir) -> int:
    """Какой по счёту правитель с таким именем в этой стране.

    Возвращение на престол прежнего правителя номера не меняет: он всё тот же.
    """
    seen = set()
    for reign_id in polity.reign_ids:
        reign = world.reigns.get(reign_id)
        if reign is None or reign.ruler_id == heir.id:
            continue
        previous = world.figures.get(reign.ruler_id)
        if previous is not None and previous.given_name == heir.given_name:
            seen.add(previous.id)
    if heir.regnal_number and heir.id in {r for r in seen}:
        return heir.regnal_number
    return len(seen) + 1


def install_founder(ctx, polity, founder, capital, date: Date, year: int) -> None:
    """Первое правление: основатель страны становится её правителем."""
    world = ctx.world
    race = races_mod.get_race(polity.race_id)
    polity.succession = race.succession_for(polity.form)

    house = world.houses.get(founder.house_id)
    if house is None:
        house = houses_mod.found_house(ctx, founder, year, date, seat=capital,
                                       rank=ROYAL, polity=polity, announce=True,
                                       importance=2)
    if house is not None:
        houses_mod.make_royal(ctx, house, polity, year, date, announce=False)

    choice = dynasty.HeirChoice(founder, "основатель", law=polity.succession)
    enthrone(ctx, polity, founder, date, year, choice, legitimacy="основание",
             old_house=None, announce=False)


# ---------------------------------------------------------------------------
# Семья
# ---------------------------------------------------------------------------

def ensure_family(ctx, figure, year: int, polity=None, announce: bool = True) -> None:
    """Заводит супруга и детей — если их ещё нет."""
    world = ctx.world
    race = races_mod.get_race(figure.race_id)
    if figure.spouse_id or figure.children:
        return
    if figure.death is None or figure.birth is None:
        return
    if figure.age_at(year) < race.adulthood:
        return

    rng = ctx.rng("family", figure.id)
    earliest = figure.birth.year + race.adulthood
    latest = min(year, figure.death.year - 1)
    if latest < earliest:
        marriage_year = max(earliest, figure.death.year - 1)
    else:
        marriage_year = rng.randint(earliest, latest)
    marriage_year = max(1, marriage_year)

    spouse = _make_spouse(ctx, figure, race, marriage_year, rng)
    if spouse is None:
        return
    figure.spouse_id = spouse.id
    spouse.spouse_id = figure.id

    if announce and polity is not None:
        date = ctx.date_in(rng, max(marriage_year, 1))
        spouse_house = world.houses.get(spouse.house_id)
        title, text = texts.marriage(rng, polity, figure, spouse, spouse_house)
        world.add_event(
            date=date, era_index=world.era_index_at(date.year), kind="marriage",
            title=title, text=text, importance=1,
            actors=[figure.id, spouse.id], subjects=[polity.id],
            race_id=race.id,
        )

    _make_children(ctx, figure, spouse, race, marriage_year, year, rng, polity)


def _make_spouse(ctx, figure, race, marriage_year: int, rng):
    world = ctx.world
    sex = "m" if figure.sex == "f" else "f"
    lifespan_mid = (race.lifespan[0] + race.lifespan[1]) // 2
    age_at_marriage = race.adulthood + rng.randint(0, max(1, int(race.adulthood * 0.9)))
    birth_year = max(1, marriage_year - age_at_marriage)

    house = None
    if race.has_nobility and rng.chance(DYNASTIC_MARRIAGE):
        options = [h for h in world.houses_of_race(race.id)
                   if h.id != figure.house_id]
        if options:
            house = rng.weighted([(h, max(0.2, h.prestige)) for h in options])

    spouse = ctx.make_figure(
        rng, race, marriage_year, role="супруг" if sex == "m" else "супруга",
        region_id=figure.origin_region, sex=sex, house=house,
        birth_year=birth_year, epithet_chance=0.25, home_id=figure.home_id)
    if spouse.death.year <= marriage_year:
        world.schedule_death(spouse, Date.random_in_year(
            rng, marriage_year + rng.randint(1, max(2, lifespan_mid // 3))))
    return spouse


def _make_children(ctx, figure, spouse, race, marriage_year: int, year: int,
                   rng, polity=None) -> None:
    world = ctx.world
    father, mother = (figure, spouse) if figure.sex == "m" else (spouse, figure)
    if race.succession == races_mod.MATRILINEAL:
        house_owner = mother
    elif "правитель" in figure.roles:
        # Дети правящей особы остаются в её роду: династия не прерывается
        # оттого, что корону надела женщина.
        house_owner = figure
    else:
        house_owner = father
    house = world.houses.get(house_owner.house_id)

    last_year = min(figure.death.year, spouse.death.year) - 1
    fertile_span = max(race.adulthood, int((race.lifespan[0] + race.lifespan[1]) * 0.15))
    window_end = min(last_year, marriage_year + fertile_span)
    if window_end <= marriage_year:
        return

    count = rng.randint(race.fertility[0], race.fertility[1])
    born = []
    for index in range(count):
        birth_year = rng.randint(marriage_year + 1, window_end)
        born.append(birth_year)
    born.sort()

    for order, birth_year in enumerate(born, start=1):
        sex = "f" if rng.chance(0.48) else "m"
        given = _ancestral_name(world, house, rng, sex)
        child = ctx.make_figure(
            rng, race, birth_year, role="дитя знатного рода",
            region_id=figure.origin_region, sex=sex,
            house=house, given_name=given, birth_year=birth_year,
            father=father, mother=mother, birth_order=order,
            epithet_chance=0.18, home_id=figure.home_id)
        if rng.chance(CHILD_MORTALITY):
            world.schedule_death(child, Date.random_in_year(
                rng, birth_year + rng.randint(0, max(1, race.adulthood - 1))),
                cause="не дожил до совершеннолетия")

        if order == 1 and polity is not None and rng.chance(0.22):
            date = child.birth
            title, text = texts.heir_birth(rng, polity, child, house)
            world.add_event(
                date=date, era_index=world.era_index_at(date.year),
                kind="heir_birth", title=title, text=text, importance=1,
                actors=[child.id], subjects=[polity.id], race_id=race.id,
            )


def _ancestral_name(world, house, rng, sex: str):
    """Знать любит называть детей в честь предков — отсюда и «Ронвальд III».

    Имя берётся только у предка того же пола: «король Фара II» после
    «королевы Фары» выглядел бы нелепо.
    """
    if house is None or not rng.chance(0.45):
        return ""
    pool = []
    for member_id in house.members[:60]:
        member = world.figures.get(member_id)
        if member is not None and member.given_name and member.sex == sex:
            pool.append(member.given_name)
    if not pool:
        return ""
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# Продолжение знатных линий
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    """Не даёт важным родам угаснуть на ровном месте.

    Малые роды вымирают сами собой — так и должно быть. А вот правящие
    династии и великие дома женят наследников и продолжают линию.
    """
    world = ctx.world
    rng = ctx.rng("lineage", year)

    for house_id in list(world.active_houses):
        house = world.houses[house_id]
        important = house.rank in (ROYAL, GREAT) or house.thrones > 0
        if not important:
            seat = world.settlements.get(house.seat_id)
            if seat is None or seat.status != ACTIVE:
                continue
            if not rng.chance(0.25 * (period / 10.0)):
                continue

        race = races_mod.get_race(house.race_id)
        alive = world.house_members(house, alive_in_year=year)
        with_children = sum(1 for f in alive if f.children)
        # Двух семей в поколении хватает, чтобы род не пресёкся и не разросся.
        if with_children >= 2 and len(alive) > 4:
            continue

        ready = []
        for figure in alive:
            if figure.spouse_id or figure.children:
                continue
            age = figure.age_at(year)
            if race.adulthood <= age <= race.lifespan[0] * 0.6:
                ready.append(figure)
        if not ready:
            continue
        ready.sort(key=lambda f: (-f.birth.ordinal, f.id))      # младшие первыми
        ensure_family(ctx, ready[0], year, polity=None, announce=False)


# ---------------------------------------------------------------------------
# Регентство
# ---------------------------------------------------------------------------

def _tick_regency(ctx, year: int) -> None:
    world = ctx.world
    for polity_id in list(world.active_polities):
        polity = world.polities[polity_id]
        reign = world.current_reign(polity)
        if reign is None or not reign.regent_id or reign.end is not None:
            continue
        if year < reign.regency_until:
            continue
        ruler = world.figures.get(reign.ruler_id)
        regent = world.figures.get(reign.regent_id)
        rng = ctx.rng("regency_end", polity.id, year)
        reign.regent_id = ""
        if ruler is None or not ruler.alive_at(year):
            continue
        date = ctx.date_in(rng, year)
        title, text = texts.regency_end(rng, polity, ruler, regent)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="regency_end",
            title=title, text=text, importance=2, actors=[ruler.id],
            subjects=[polity.id], race_id=polity.race_id,
        )


# ---------------------------------------------------------------------------
# Придворная интрига
# ---------------------------------------------------------------------------

def _instability(ctx, world, polity, year: int) -> float:
    """Насколько шатко сидит правитель.

    Главное здесь — время. Узурпатор опасен первые годы, а тот, кто правит
    дольше срока взросления, успевает обрасти сторонниками, и его уже
    не трогают. Без этого одна несчастливая страна собирала бы на себя
    все перевороты мира подряд.
    """
    race = races_mod.get_race(polity.race_id)
    value = race.coup_propensity
    reign = world.current_reign(polity)
    if reign is not None:
        reign_age = max(0, year - reign.start.year)
        settled = reign_age > race.adulthood
        if reign.regent_id:
            value += 0.9
        if reign.legitimacy == "узурпация" and not settled:
            value += 0.7
        if reign_age < race.adulthood * 0.5:
            value *= 0.45            # только сел на престол — двор ещё присматривается
        ruler = world.figures.get(reign.ruler_id)
        if ruler is not None:
            if ruler.age_at(year) > race.lifespan[0] * 0.85:
                value += 0.35
    value += 0.08 * max(0, len(polity.house_ids) - 1)
    # Долгоживущие народы правят веками: если считать угрозу по годам,
    # на одно эльфийское правление пришлось бы больше заговоров, чем на
    # десять человеческих. Приводим опасность к длине поколения.
    value *= 70.0 / max(20.0, float(race.lifespan[0]))
    value *= 0.7 + ctx.era_spec(year).turmoil
    return max(0.01, value)


def _maybe_intrigue(ctx, year: int) -> None:
    world = ctx.world
    if not world.active_polities:
        return
    rng = ctx.rng("intrigue", year)

    pairs = []
    total = 0.0
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        ruler = world.figures.get(polity.ruler_id)
        if ruler is None or not ruler.alive_at(year):
            continue
        value = _instability(ctx, world, polity, year)
        total += value
        pairs.append((polity, value))
    if not pairs:
        return

    chance = min(COUP_MAX_RATE, ctx.rate(COUP_PER_INSTABILITY) * total)
    if not rng.chance(chance):
        return

    polity = rng.weighted(pairs)
    ruler = world.figures.get(polity.ruler_id)
    race = races_mod.get_race(polity.race_id)

    # Правителя, севшего на престол в этом же году, ещё не трогают:
    # иначе два правления начались бы в одном году задом наперёд.
    reign = world.current_reign(polity)
    if reign is not None and reign.start.year >= year:
        return

    if rng.chance(ABDICATION_SHARE) and ruler.age_at(year) > race.lifespan[0] * 0.7:
        _abdicate(ctx, polity, ruler, year, rng)
        return
    _resolve_coup(ctx, polity, ruler, race, year, rng)


def _abdicate(ctx, polity, ruler, year: int, rng) -> None:
    world = ctx.world
    reign = world.current_reign(polity)
    date = ctx.date_in(rng, year, reign.start if reign is not None else None)
    _close_reign(world, reign, date, "отречение")
    title, text = texts.abdication(rng, polity, ruler)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="abdication",
        title=title, text=text, importance=3, actors=[ruler.id],
        subjects=[polity.id], race_id=polity.race_id,
    )
    race = races_mod.get_race(polity.race_id)
    law = polity.succession or race.succession_for(polity.form)
    choice = dynasty.choose_heir(world, rng, polity, ruler, race, law, year)
    if choice is None:
        choice = _new_dynasty(ctx, polity, race, year, date, rng)
    if choice is None:
        polity.interregnum = True
        return
    old_house = world.houses.get(polity.house_id)
    polity.ruler_id = ""
    enthrone(ctx, polity, choice.figure, date, year, choice,
             legitimacy="законное", old_house=old_house, rng=rng)


def _coup_kind(law: str, rng) -> str:
    if law == races_mod.STRENGTH:
        return "challenge"
    if law == races_mod.ELECTIVE:
        return "deposition" if rng.chance(0.6) else "usurpation"
    return "palace" if rng.chance(0.5) else "usurpation"


def _pick_challenger(ctx, world, polity, ruler, race, year: int, kind: str, rng):
    ruling = world.houses.get(polity.house_id)
    pairs = []

    if kind in ("palace", "challenge"):
        for figure in dynasty.house_adults(world, ruling, race, year):
            if figure.id == ruler.id:
                continue
            weight = 1.0
            if figure.father_id and figure.father_id == ruler.father_id:
                weight = 2.0                      # братья опаснее всех
            pairs.append(((figure, ruling), weight * rng.uniform(0.6, 1.5)))

    if kind in ("usurpation", "deposition", "challenge"):
        for house in world.houses_of_polity(polity):
            if house.id == polity.house_id:
                continue
            head = world.figures.get(house.head_id)
            if head is None or not head.alive_at(year):
                continue
            if head.age_at(year) < race.adulthood:
                continue
            pairs.append(((head, house), max(0.25, house.prestige)
                          * rng.uniform(0.6, 1.5)))

    if not pairs:
        return None, None
    return rng.weighted(pairs)


def _resolve_coup(ctx, polity, ruler, race, year: int, rng) -> None:
    world = ctx.world
    law = polity.succession or race.succession_for(polity.form)
    kind = _coup_kind(law, rng)
    challenger, house = _pick_challenger(ctx, world, polity, ruler, race, year,
                                         kind, rng)
    if challenger is None:
        return

    reign = world.current_reign(polity)
    date = ctx.date_in(rng, year, reign.start if reign is not None else None)
    capital = world.settlements.get(polity.capital_id)

    success = 0.52 + 0.10 * (race.coup_propensity - 1.0)
    if reign is not None and reign.regent_id:
        success += 0.15
    if reign is not None and reign.legitimacy == "узурпация":
        success += 0.08
    if kind == "challenge":
        success += 0.05

    if not rng.chance(max(0.15, min(0.9, success))):
        world.schedule_death(challenger, date, "казнён за мятеж")
        if house is not None:
            house.prestige = max(0.15, house.prestige - 1.5)
        title, text = texts.plot_failed(rng, polity, challenger, ruler, house)
        world.add_event(
            date=date, era_index=world.era_index_at(year), kind="plot_failed",
            title=title, text=text, importance=3,
            actors=[challenger.id, ruler.id], subjects=[polity.id],
            race_id=polity.race_id,
        )
        return

    violent = rng.chance(0.62)
    reason = {"palace": "дворцовый переворот", "usurpation": "узурпация",
              "challenge": "поединок за власть", "deposition": "низложение"}[kind]
    _close_reign(world, reign, date, reason)
    if violent:
        world.schedule_death(ruler, date, "погиб(ла) при перевороте")
    else:
        ruler.notes.append("свергнут(а) в %d году" % year)

    title, text = texts.coup_success(rng, kind, polity, challenger, ruler, house,
                                     capital, violent)
    old_house = world.houses.get(polity.house_id)
    polity.ruler_id = ""
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="coup",
        title=title, text=text, importance=4,
        actors=[challenger.id, ruler.id],
        subjects=[polity.id] + ([house.id] if house is not None else []),
        race_id=polity.race_id,
    )

    choice = dynasty.HeirChoice(challenger, "узурпатор", other_house=(
        house is not None and house.id != (old_house.id if old_house else "")),
        law=law)
    enthrone(ctx, polity, challenger, date, year, choice, legitimacy="узурпация",
             old_house=old_house, rng=rng, announce=False)
