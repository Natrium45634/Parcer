# -*- coding: utf-8 -*-
"""Жизнь вещей: материал, ковка, руки, утрата, находка, память.

Вещь с именем живёт дольше человека, и в этом вся её ценность для
летописи. Меч куют в такой-то год в такой-то кузне; его жалуют
полководцу; полководец гибнет, и меч уходит под курган вместе с ним;
через триста лет курган вскрывают — и меч возвращается в мир с новым
хозяином и старым проклятием.

Каждая такая перемена записывается в цепочку рук. По этой цепочке потом
и строится всё остальное: и рассказ летописца, и подземелье, в котором
вещь лежит.

Сверх того система ведёт четыре вещи, которых у предметов не было.

**Материал как сущность мира.** Прежде материал был строкой. Теперь у
него есть класс, происхождение, умельцы и судьба: жилу находят, её
осваивают, беда заваливает выработку, мастера умирают — и через тысячу
лет найденный клинок приписывают богам, потому что повторить его
больше некому.

**Ступень значимости.** Гвоздю биография не нужна. У вещи есть
ступень от обычной до первозданной, и глубина записи зависит от неё, а
не от цены, возраста или силы.

**Биография и утрата.** У значимой вещи своя хронология: применения с
названной ролью (свидетель, орудие, ключ), передачи, кражи, починки,
разделения на части, отрезки утраты с причиной и тем, кто знал, где
она. И не всякая утрата кончается находкой: «так и не нашлась» — такой
же честный ответ, как прочие.

**Правда и память врозь.** Генератор может знать, что венец тайно
передали изгнаннику, а летопись помнит только, что он пропал из
сокровищницы. Поэтому у события биографии есть графа «знают ли», а
рядом с вещью лежат чужие утверждения о ней — с источником, временем и
тем, подтверждены они или опровергнуты.
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

# Сколько материалов мир заводит себе на всю историю. Меньше десятка —
# и вещи выходят на одно лицо; больше двух десятков — и справочник
# перестаёт читаться, а редкое перестаёт быть редким.
STUFF_LOW = 9
STUFF_HIGH = 17

# Жизнь материала: иссякание и возвращение. Числа — на один материал за
# такт, а не на мир, и это главное. Пока бросок был общий, число
# иссякших материалов шло случайным блужданием с постоянными
# скоростями, а у такого блуждания нет равновесия: при перевесе
# иссякания оно съедало все материалы мира до одного, включая железо
# (мир, в котором ковать не из чего), а при перевесе возвращения почти
# всё время стояло на нуле (мир, в котором ничего не кончается). Обе
# крайности поймала одна и та же мера смотра. При счёте на каждый
# материал врозь доля иссякших держится сама собой около
# end / (end + back) и не зависит ни от числа материалов в мире, ни от
# длины его истории.
STUFF_END_CHANCE = 0.0045
STUFF_BACK_CHANCE = 0.0022
# Чем дольше материала нет, тем охотнее о нём вспоминают: старую
# выработку раскапывают, а по уцелевшим вещам разбирают, как это
# делали. За две тысячи лет забвения — втрое охотнее.
STUFF_BACK_AGE = 1000.0
STUFF_BACK_AGE_CAP = 2.0

# Биография ведётся не всякой вещи, а той, что ступенью не ниже
# исторической: у прочих и событий-то не бывает.
LIFE_CHANCE = 0.30          # что за такт с заметной вещью что-то случилось
CLAIM_CHANCE = 0.22         # что о ней стали говорить своё
WORTH_CHANCE = 0.25         # что её заново оценили
FAKE_CHANCE = 0.06          # что объявилась копия или подделка
SPLIT_CHANCE = 0.04         # что её разняли на части
LEGACY_AGE = 200            # с какого возраста у вещи считают наследие


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
    _woe_takes(ctx, year, rng, scale)
    _stuff_life(ctx, year, rng, scale)
    _lives(ctx, year, rng, scale)
    _claims(ctx, year, rng, scale)
    _worths(ctx, year, rng, scale)


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
    """Собирает вещь: род, материал, состав, ступень, свойства, имя.

    Материал берётся из материалов мира, а не из общего справочника:
    из того, что в этом мире есть и ещё не иссякло. Если мир почему-то
    остался без материалов вовсе, работает прежний путь — строкой из
    справочника; без этого старые сохранения и мир без подготовки
    перестали бы собираться.
    """
    world = ctx.world
    shape = art.shape_for(rng, sort)
    folk = None
    if city is not None:
        folk = world.folks.get(city.folk_id)
    rich = 1.0
    if origin == art.GIFTED:
        rich = 2.0
    elif city is not None and city.population >= 8000:
        rich = 1.4
    stuff = stuff_for(ctx, rng, year, folk=folk, rich=rich)
    if stuff is not None:
        material_name, material_gen, worth = stuff.name, stuff.gen, stuff.worth
    else:
        material = art.material_for(rng)
        material_name, material_gen, worth = material
    worth *= 1.2 if origin == art.GIFTED else 1.0
    tongue = world.tongue_of(folk) if folk is not None else None
    name = ctx.forge.artifact(rng, race, shape, tongue)
    artifact = world.add_artifact(
        name=name, shape=shape.key, word=shape.word, gender=shape.gender,
        sort=shape.sort,
        material=material_name, material_gen=material_gen,
        made=ctx.date_in(rng, year), origin=origin,
        maker_id=maker.id if maker is not None else "",
        race_id=race.id, region_id=region_id,
        powers=art.powers_for(rng, worth),
        curse=art.curse_for(rng, worth, dark + ctx.dark_tilt * 0.3),
        origin_kind=_origin_kind(origin, maker, rng),
        precision=art.P_EXACT, told_made=year, state=art.S_WHOLE,
        authentic=art.A_TRUE, tier=art.T_GOOD)
    artifact.parts = _parts_for(ctx, rng, artifact, stuff, year)
    artifact.tier = _tier_for(world, artifact, stuff, origin, rng)
    artifact.kinds = _kinds_for(artifact, origin, stuff)
    if artifact.powers and artifact.tier >= art.T_HIST:
        artifact.limits = [art.LIMIT_NAMES[key] for key in
                           _limits_for(rng, artifact)]
    note_deed(ctx, artifact, year, "made", rng,
              truth="%s: %s" % (art.said_of(artifact.gender,
                                            ("сделан", "сделана", "сделано")),
                                art.ORIGIN_KIND_NAMES.get(
                                    artifact.origin_kind, origin)),
              actors=[maker.id] if maker is not None else (),
              region_id=region_id)
    return artifact


def _origin_kind(origin: str, maker, rng) -> str:
    """Отчего вещь вообще появилась — ключом из справочника."""
    if origin == art.GIFTED:
        return "god"
    if origin == art.TAKEN:
        return "beast"
    if origin == art.FOUND:
        return "dark"
    if origin == art.OTHERWORLD:
        return "rift"
    if maker is not None:
        return rng.weighted([("master", 1.4), ("order", 1.2), ("craft", 1.6),
                             ("war", 0.8), ("remade", 0.5),
                             ("lostway", 0.3)])
    return "craft"


def _parts_for(ctx, rng, artifact, stuff, year: int) -> list:
    """Из чего вещь состоит: основа и, если работа богатая, вставки.

    Состав — не украшение записи: у каждой части своя доля и свой
    материал, а значит, своя судьба. Оковка из металла, которого
    больше не добывают, делает вещь свидетельством, даже если основа у
    неё обычная.
    """
    if stuff is None:
        return []
    parts = [{"материал": stuff.id, "доля": 1.0, "роль": "основа"}]
    extra = 0
    if artifact.sort in (art.REGALIA, art.BOOK) or rng.chance(0.35):
        extra = rng.weighted([(1, 2.0), (2, 0.8)])
    for _step in range(int(extra)):
        other = stuff_for(ctx, rng, year, rich=1.2)
        if other is None or other.id == stuff.id:
            continue
        if any(row["материал"] == other.id for row in parts):
            continue
        share = round(rng.uniform(0.05, 0.3), 2)
        parts[0]["доля"] = round(max(0.3, parts[0]["доля"] - share), 2)
        parts.append({"материал": other.id, "доля": share,
                      "роль": rng.choice(art.PART_ROLES[1:])})
    return parts


def _tier_for(world, artifact, stuff, origin: str, rng) -> int:
    """Насколько глубоко эту вещь записывать.

    Ступень не выводится ни из цены, ни из возраста: решает то, чем
    вещь станет в истории. Дар божества и работа из первозданного
    начинают высоко, обычная кузнечная работа — низко, и подняться ей
    ещё предстоит делами.
    """
    tier = art.T_GOOD
    if stuff is not None:
        if stuff.klass == art.M_FIRST:
            tier = art.T_FIRST
        elif stuff.klass in (art.M_WEIRD, art.M_BEAST):
            tier = art.T_RELIC
        elif stuff.klass == art.M_RARE:
            tier = art.T_HIST
    if origin == art.GIFTED:
        tier = max(tier, art.T_RELIC)
    if origin == art.OTHERWORLD:
        tier = max(tier, art.T_RELIC)
    if artifact.curse:
        tier = max(tier, art.T_HIST)
    if len(artifact.powers) >= 2:
        tier = max(tier, art.T_HIST)
    if tier >= art.T_RELIC and rng.chance(0.3):
        tier -= 1          # не всякая дорогая работа становится артефактом
    return tier


def _kinds_for(artifact, origin: str, stuff) -> list:
    kinds = []
    if origin == art.GIFTED:
        kinds.append(art.K_HOLY)
    if artifact.sort == art.REGALIA:
        kinds.append(art.K_CROWN)
    if artifact.powers:
        kinds.append(art.K_MAGIC)
    if stuff is not None and stuff.klass in (art.M_RARE, art.M_BEAST,
                                             art.M_WEIRD, art.M_FIRST):
        kinds.append(art.K_RARE_K)
    if stuff is not None and stuff.worth >= 1.5:
        kinds.append(art.K_TRADE)
    if origin == art.OTHERWORLD:
        kinds.append(art.K_ODD)
    return kinds


def _limits_for(rng, artifact) -> list:
    """Чем сила ограничена. Без ограничения сильная вещь ломает мир."""
    pool = [key for key, _said in art.LIMITS]
    count = 1 if len(artifact.powers) < 3 else 2
    out = []
    for _step in range(count):
        left = [key for key in pool if key not in out]
        if not left:
            break
        out.append(rng.choice(sorted(left)))
    return out


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
        note_deed(ctx, artifact, year, "heir", rng,
                  truth="%s к наследнику: %s"
                  % (art.said_of(artifact.gender,
                                 ("перешёл", "перешла", "перешло")),
                     heir.name),
                  actors=[heir.id])
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
        note_deed(ctx, artifact, year, "buried", rng,
                  truth="%s в погребение вместе с %s"
                  % (art.said_of(artifact.gender,
                                 ("положен", "положена", "положено")),
                     owner.name),
                  actors=[owner.id],
                  site_id=site.id if site is not None else "")
        _lose(ctx, artifact, year, "grave",
              where=site.name if site is not None else "могила хозяина",
              knew="те, кто хоронил")
        return
    world.put_artifact(artifact, art.LOST, date, how="потеряна")
    note_deed(ctx, artifact, year, "hidden", rng,
              truth="%s там, где %s видели в последний раз"
              % (art.said_of(artifact.gender,
                             ("потерян", "потеряна", "потеряно")),
                 texts.its(artifact)),
              known=True, region_id=artifact.region_id)
    _lose(ctx, artifact, year, _loss_why(ctx, artifact, year, rng),
          where=region.name if region is not None else "",
          knew="никто")
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
    note_deed(ctx, artifact, year, "given", rng,
              truth="%s государем: %s"
              % (art.said_of(artifact.gender,
                             ("пожалован", "пожалована", "пожаловано")),
                 hero.name),
              actors=[hero.id], polity_id=polity.id)
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
    _found(ctx, artifact, year, rng, finder, "chance")
    title, text = texts.found(rng, artifact, finder, place, years)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="artifact_found",
        title=title, text=text, importance=3, actors=[finder.id],
        subjects=[artifact.id], region_id=city.region_id, race_id=race.id)
    artifact.deeds.append(event.id)


# ---------------------------------------------------------------------------
# Утрата и находка как отрезки, а не как флажок
# ---------------------------------------------------------------------------


def _loss_why(ctx, artifact, year: int, rng) -> str:
    """Отчего вещь пропала — с оглядкой на то, что тогда было в мире."""
    world = ctx.world
    pool = [("forgot", 1.0), ("theft", 0.8), ("hidden", 0.8)]
    for calamity in world.calamities.values():
        if calamity.start is None or calamity.start.year > year:
            continue
        if calamity.start.year < year - 60:
            continue
        if artifact.region_id in (calamity.region_ids or ()):
            pool.append(("woe", 3.0))
            break
    for war in world.wars.values():
        if war.start is None or war.start.year > year:
            continue
        if war.start.year < year - 60:
            continue
        pool.append(("battle", 1.4))
        pool.append(("sack", 1.0))
        break
    region = world.regions.get(artifact.region_id)
    if region is not None and (region.coastal or region.island):
        pool.append(("sea", 1.0))
    return rng.weighted(pool)


def _lose(ctx, artifact, year: int, why: str, where: str = "",
          knew: str = "") -> None:
    """Открывает отрезок утраты: с какого года, отчего и кто знал.

    Отрезок, а не флажок: у утраты есть длина, и она бывает в
    тысячелетия. По нему же потом видно, сколько веков о вещи ничего
    не было слышно.
    """
    if artifact.losses and not artifact.losses[-1].get("по"):
        return                      # уже потеряна, второй раз не теряют
    artifact.losses.append({
        "с": year, "по": 0, "отчего": art.LOSS_WHY_NAMES.get(why, why),
        "где искали": where, "кто знал": knew or "никто",
        "чем кончилось": "",
    })


def _found(ctx, artifact, year: int, rng, finder=None, how: str = "chance",
           where: str = "") -> None:
    """Закрывает отрезок утраты находкой — и записывает, как нашли."""
    span = None
    for row in artifact.losses:
        if not row.get("по"):
            span = row
            break
    if span is not None:
        span["по"] = year
        years = year - int(span.get("с", year))
        span["чем кончилось"] = art.LOSS_END_NAMES.get(
            "soon" if years < 60 else ("ages" if years > 300 else how), how)
        if where:
            span["где нашли"] = art.FOUND_WHERE_NAMES.get(where, where)
    note_deed(ctx, artifact, year, "found", rng,
              truth="%s заново%s"
              % (art.said_of(artifact.gender,
                             ("найден", "найдена", "найдено")),
                 ": %s" % finder.name if finder is not None else ""),
              actors=[finder.id] if finder is not None else (),
              precision=art.P_YEAR)
    # Найденное не всегда опознают: вещь бывает лежит в сокровищнице
    # под чужим именем, пока книжник не разберёт надпись. Но о вещи,
    # про которую уже известно, что она копия или подделка, находка
    # этого знания не отменяет: иначе список со временем снова
    # становится «подлинником не установленной подлинности», а с него
    # потом делают список со списка.
    if artifact.tier >= art.T_HIST and not artifact.parent_id \
            and artifact.authentic == art.A_TRUE and rng.chance(0.35):
        artifact.authentic = art.A_UNSURE
        artifact.notes.append("%d: нашли, но чья она, сразу не поняли" % year)


def unearth(ctx, artifact, year: int, rng, finder=None, site=None) -> bool:
    """Вещь достали из земли — из раскопа, руин или вскрытой гробницы.

    Зовётся снаружи: из похода за знанием, из работы на месте истории.
    Возвращает False, если доставать было нечего: вещь не потеряна, её
    уже нашли или она вовсе уничтожена.
    """
    world = ctx.world
    if artifact is None or artifact.status != ACTIVE:
        return False
    if artifact.where not in (art.LOST, art.IN_RUIN, art.IN_TOMB,
                              art.IN_HOARD):
        return False
    date = ctx.date_in(rng, year)
    if finder is not None:
        world.put_artifact(artifact, art.WITH_FIGURE, date, figure=finder,
                           how="поднята из земли")
    else:
        world.put_artifact(artifact, art.IN_TREASURY, date,
                           how="поднята из земли")
    _found(ctx, artifact, year, rng, finder=finder, how="dig",
           where="ruin" if site is not None else "open")
    title, text = texts.unearthed(rng, artifact, finder, site, year)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year),
        kind="artifact_found", title=title, text=text,
        importance=2 + min(2, artifact.tier),
        actors=[finder.id] if finder is not None else [],
        subjects=[artifact.id] + ([site.id] if site is not None else []),
        region_id=artifact.region_id, race_id=artifact.race_id)
    artifact.deeds.append(event.id)
    return True


def sleeping_in(world, region_id: str, site_id: str = "") -> list:
    """Что лежит в этой земле или на этом месте и ждёт, когда найдут."""
    rows = []
    for artifact in world.artifacts.values():
        if artifact.status != ACTIVE:
            continue
        if artifact.where not in (art.LOST, art.IN_RUIN, art.IN_TOMB,
                                  art.IN_HOARD):
            continue
        if site_id and artifact.site_id == site_id:
            rows.append(artifact)
        elif region_id and artifact.region_id == region_id:
            rows.append(artifact)
    rows.sort(key=lambda item: (-item.tier, item.id))
    return rows


__all__ = ["upkeep", "prepare", "unearth", "sleeping_in", "note_deed"]


def _woe_takes(ctx, year: int, rng, scale: float) -> None:
    """Беда берёт своё: вещи уходят под завал вместе с городом.

    Это и есть главный способ, которым вещи попадают в землю надолго.
    Беду тут не выдумывают: берётся та, что в этом мире только что
    случилась, и вещи той земли, которые были на виду.
    """
    world = ctx.world
    fresh = []
    for calamity in world.calamities.values():
        if calamity.start is None or calamity.start.year > year:
            continue
        if calamity.start.year < year - 20:
            continue
        fresh.append(calamity)
    if not fresh or not rng.chance(0.5 * scale):
        return
    calamity = fresh[rng.randint(0, len(fresh) - 1)]
    lands = set(calamity.region_ids or ())
    if not lands:
        return
    pool = [item for item in world.artifacts.values()
            if item.status == ACTIVE and item.region_id in lands
            and item.where in (art.WITH_FIGURE, art.IN_TREASURY,
                               art.IN_TEMPLE)]
    if not pool:
        return
    artifact = pool[rng.randint(0, len(pool) - 1)]
    date = ctx.date_in(rng, year)
    world.put_artifact(artifact, art.IN_RUIN, date,
                       how="осталась под развалинами")
    note_deed(ctx, artifact, year, "hidden", rng,
              truth="%s под развалинами: %s"
              % (art.said_of(artifact.gender,
                             ("остался", "осталась", "осталось")),
                 calamity.name),
              region_id=artifact.region_id, precision=art.P_YEAR)
    _lose(ctx, artifact, year, "woe",
          where=world.regions[artifact.region_id].name
          if artifact.region_id in world.regions else "",
          knew="те, кто не пережил беду")
    if artifact.tier >= art.T_HIST:
        title, text = texts.lost(rng, artifact,
                                 world.regions.get(artifact.region_id))
        event = world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="artifact_lost", title=title, text=text, importance=2,
            subjects=[artifact.id, calamity.id],
            region_id=artifact.region_id, race_id=artifact.race_id)
        artifact.deeds.append(event.id)


# ---------------------------------------------------------------------------
# Материалы мира
# ---------------------------------------------------------------------------


def prepare(ctx) -> None:
    """Из чего в этом мире вообще делают вещи.

    Справочник родов материала один на все миры, а материалы у каждого
    мира свои: звёздное железо падало не везде, драконья кость бывает
    там, где есть драконы, а божье золото — там, где есть бог, который
    его дал. Поэтому тут не список, а отбор: берётся то, чему в этом
    мире есть откуда взяться.
    """
    world = ctx.world
    rng = ctx.rng("stuff", "prepare")
    beasts = [item for item in world.species.values()
              if not item.is_people]
    gods = sorted(world.deities.values(), key=lambda item: item.id)
    rich = sorted([region for region in world.regions.values()
                   if not region.drowned],
                  key=lambda region: (-float(region.richness or 0.0),
                                      region.id))
    want = rng.randint(STUFF_LOW, STUFF_HIGH)
    pool = []
    for stuff in art.STUFFS:
        weight = stuff.weight * art.stuff_class_weight(stuff.klass)
        if stuff.origin == art.O_BEAST and not beasts:
            continue
        if stuff.origin == art.O_GOD and not gods:
            continue
        if stuff.origin in (art.O_WORLD,) and not world.origins:
            weight *= 0.3
        if stuff.origin in (art.O_VEIN, art.O_QUARRY, art.O_DEPTH) \
                and not rich:
            continue
        pool.append((stuff, weight))
    taken = []
    while pool and len(taken) < want:
        stuff = rng.weighted(pool)
        pool = [(item, weight) for item, weight in pool if item.key != stuff.key]
        taken.append(stuff)

    for stuff in sorted(taken, key=lambda item: item.key):
        region_id = ""
        species_id = ""
        deity_id = ""
        if stuff.origin in (art.O_VEIN, art.O_QUARRY, art.O_DEPTH,
                            art.O_FOREST) and rich:
            region_id = rich[rng.randint(0, min(4, len(rich) - 1))].id
        if stuff.origin == art.O_BEAST and beasts:
            kin = beasts[rng.randint(0, len(beasts) - 1)]
            species_id = kin.id
        if stuff.origin == art.O_GOD and gods:
            deity_id = gods[rng.randint(0, len(gods) - 1)].id
        world.add_material(
            key=stuff.key, name=stuff.name, gen=stuff.gen, klass=stuff.klass,
            family=stuff.family, origin=stuff.origin, props=list(stuff.props),
            needs=stuff.needs, worth=stuff.worth,
            rarity=_rarity_of(stuff), region_id=region_id,
            species_id=species_id, deity_id=deity_id,
            origin_note=_origin_note(world, stuff, region_id, species_id,
                                     deity_id),
            found_year=0 if stuff.klass == art.M_FIRST else 0,
            state=art.D_OPEN)


def _rarity_of(stuff) -> str:
    return {
        art.M_PLAIN: "обычен", art.M_FINE: "не везде",
        art.M_RARE: "редок", art.M_BEAST: "добывается с боем",
        art.M_WEIRD: "почти не встречается",
        art.M_FIRST: "единственный в своём роде",
    }.get(stuff.klass, "редок")


def _origin_note(world, stuff, region_id: str, species_id: str,
                 deity_id: str) -> str:
    """Откуда он в этом мире — словами и с опорой на здешние имена."""
    region = world.regions.get(region_id)
    kin = world.species.get(species_id)
    deity = world.deities.get(deity_id)
    if deity is not None:
        return "дан божеством по имени %s" % deity.name
    if kin is not None:
        return "его берут у существ рода «%s»" % kin.name
    if region is not None:
        return "его берут в земле по имени %s — %s" \
            % (region.name, art.ORIGIN_ABOUT.get(stuff.origin, ""))
    return art.ORIGIN_ABOUT.get(stuff.origin, "откуда он взялся, не записано")


def stuff_for(ctx, rng, year: int, folk=None, rich: float = 1.0):
    """Материал, из которого в этом году и в этом месте могут сделать вещь.

    Выбор не свободный: то, что иссякло, в дело не идёт, а
    первозданное не берут на всякий нож. Чем богаче заказчик, тем
    вероятнее, что работа пойдёт из дорогого.
    """
    world = ctx.world
    pool = []
    for item in world.materials.values():
        if item.state in (art.D_SPENT, art.D_LOST, art.D_FORGOT):
            continue
        weight = art.stuff_class_weight(item.klass)
        if item.state == art.D_SCARCE:
            weight *= 0.4
        if item.klass in (art.M_WEIRD, art.M_FIRST):
            weight *= 0.35 * rich
        elif item.klass in (art.M_RARE, art.M_BEAST):
            weight *= 0.7 * rich
        if folk is not None and item.known_by and folk.id not in item.known_by:
            weight *= 0.5
        pool.append((item, max(0.02, weight)))
    if not pool:
        return None
    chosen = rng.weighted(pool)
    if folk is not None and folk.id not in chosen.known_by:
        chosen.known_by.append(folk.id)
        if not chosen.found_year:
            chosen.found_year = year
    elif not chosen.found_year:
        chosen.found_year = year
    return chosen


def _stuff_life(ctx, year: int, rng, scale: float) -> None:
    """Жила кончается, зверь переводится, умение забывается — и наоборот.

    Счёт идёт по каждому материалу врозь: у звёздного железа своя
    судьба, у драконьей кости своя, и то, что кончилось одно, ничего не
    говорит о другом. Общий бросок на мир этого не умел — он решал
    только, случится ли в этот век хоть что-нибудь, а с кем, выбирал
    потом.
    """
    world = ctx.world
    if not world.materials:
        return
    for item in sorted(world.materials.values(), key=lambda row: row.id):
        if item.alive:
            # Обычное железо, дерево и камень из мира не исчезают:
            # кончается жила, а не вещество. Такой материал бывает «на
            # исходе», но совсем взять его неоткуда не станет — иначе у
            # мира пропадает кузнечное дело как таковое.
            if item.klass == art.M_PLAIN:
                continue
            if rng.chance(STUFF_END_CHANCE * scale * _end_urge(item)):
                _stuff_ends(ctx, item, year, rng)
        else:
            gone = year - item.end_year if item.end_year else 0
            urge = 1.0 + min(STUFF_BACK_AGE_CAP, gone / STUFF_BACK_AGE)
            if rng.chance(STUFF_BACK_CHANCE * scale * urge):
                _stuff_back(ctx, item, year, rng)


def _end_urge(item) -> float:
    """Насколько этот материал на пути к концу.

    Жила иссякает оттого, что в неё копают, зверя переводят оттого, что
    на него охотятся, а умение забывают оттого, что мастеров было двое.
    Материал, которого никто не берёт, сам собой не кончается — его
    разве что завалит обвалом; и наоборот, тот, на котором держится
    ремесло трёх народов, кончается первым.

    Без этого выходила обратная неправда: кончались ровно те материалы,
    которых никто не касался, потому что бросок их не различал, а взять
    в дело кончившийся уже нельзя. Мир оставался с полным набором
    рабочих материалов и тремя мёртвыми строчками в описи, а вещи,
    повторить которую больше некому, в нём не было ни одной.
    """
    if not item.known_by and not item.found_year:
        return 0.3
    return min(2.0, 0.7 + 0.45 * len(item.known_by))


def _stuff_ends(ctx, item, year: int, rng) -> None:
    """Материал кончился — или только пошёл на убыль."""
    world = ctx.world
    key = _end_why(ctx, item, year, rng)
    if item.state == art.D_OPEN and key not in ("masters", "ban") \
            and rng.chance(0.45):
        item.state = art.D_SCARCE      # сперва на исходе
    else:
        item.state = art.D_FORGOT if key == "masters" else art.D_SPENT
        item.end_year = year
        item.end_why = art.STUFF_END_NAMES[key]
    item.marks.append({"год": year, "что": art.STUFF_END_NAMES[key]})
    if item.state != art.D_SCARCE:
        title, text = texts.stuff_lost(rng, item, year)
        world.add_event(
            date=ctx.date_in(rng, year),
            era_index=world.era_index_at(year), kind="stuff_lost",
            title=title, text=text, importance=2,
            subjects=[item.id], region_id=item.region_id)


def _stuff_back(ctx, item, year: int, rng) -> None:
    """Выработку раскопали, умение разобрали по вещам, зверь развёлся."""
    world = ctx.world
    key = rng.choice([row for row, _said in art.STUFF_BACKS])
    item.state = art.D_OPEN
    item.back_year = year
    item.marks.append({"год": year, "что": art.STUFF_BACK_NAMES[key]})
    # Конец его кончился: год и причина остаются в памяти материала, а
    # графа состояния говорит о нынешнем дне. Иначе выходит материал,
    # который кончился в трёхсотом и впервые взят в тысяча сто сороковом.
    item.end_year = 0
    item.end_why = ""
    title, text = texts.stuff_back(rng, item, year, key)
    world.add_event(
        date=ctx.date_in(rng, year),
        era_index=world.era_index_at(year), kind="stuff_back",
        title=title, text=text, importance=2, subjects=[item.id],
        region_id=item.region_id)


def _end_why(ctx, item, year: int, rng) -> str:
    """Отчего материал кончился — с опорой на то, что в мире случилось."""
    world = ctx.world
    pool = []
    if item.origin in (art.O_VEIN, art.O_QUARRY, art.O_DEPTH):
        pool.append(("mine", 1.6))
    if item.origin == art.O_BEAST:
        kin = world.species.get(item.species_id)
        if kin is not None and kin.status != "живёт":
            pool.append(("beastgone", 3.0))
        pool.append(("beastgone", 1.0))
    if item.origin == art.O_FOREST:
        pool.append(("holy", 0.8))
    for calamity in world.calamities.values():
        if calamity.start is None or calamity.start.year > year:
            continue
        if calamity.start.year < year - 300:
            continue
        if item.region_id and item.region_id in (calamity.region_ids or ()):
            pool.append(("woe", 2.5))
            pool.append(("masters", 1.5))
            break
    pool.extend([("masters", 1.0), ("road", 0.7), ("war", 0.7),
                 ("ban", 0.4)])
    return rng.weighted(pool)


# ---------------------------------------------------------------------------
# Биография вещи
# ---------------------------------------------------------------------------


def note_deed(ctx, artifact, year: int, kind: str, rng, truth: str = "",
              told: str = "", known: bool = True, role: str = "",
              tie: str = "", outcome: str = "", actors=(), region_id: str = "",
              site_id: str = "", polity_id: str = "", event_id: str = "",
              cause_id: str = "", precision: str = art.P_EXACT):
    """Записывает одно событие биографии вещи.

    Один вызов на всю систему нарочно: события вещи приходят и из
    ковки, и из войны, и из раскопа, и если каждый заводит запись
    по-своему, хронология перестаёт сходиться.
    """
    world = ctx.world
    # День внутри года бросается жребием, и он может выпасть раньше
    # дня, когда вещь сделали. Для хронологии это ложь на полгода,
    # поэтому дата не опускается ниже дня создания.
    date = ctx.date_in(rng, year)
    if artifact.made is not None and date.ordinal < artifact.made.ordinal:
        date = artifact.made
    deed = world.add_artifact_deed(
        artifact_id=artifact.id, kind=kind, date=date,
        precision=precision, region_id=region_id or artifact.region_id,
        site_id=site_id or artifact.site_id,
        actors=[key for key in actors if key], polity_id=polity_id,
        event_id=event_id, cause_id=cause_id, role=role, tie=tie,
        outcome=outcome, weight=art.DEED_WEIGHT.get(kind, 1),
        truth=truth or art.DEED_NAMES.get(kind, kind), told=told,
        known=bool(known))
    if known:
        artifact.last_seen = max(artifact.last_seen, year)
    return deed


def _notable(world) -> list:
    """Вещи, которым биографию ведут: исторические и выше."""
    return [item for item in world.artifacts.values()
            if item.tier >= art.T_HIST]


def _lives(ctx, year: int, rng, scale: float) -> None:
    """Что случилось с заметной вещью за эти десять лет."""
    world = ctx.world
    rows = _notable(world)
    if not rows:
        return
    if not rng.chance(LIFE_CHANCE * scale):
        return
    artifact = rows[rng.randint(0, len(rows) - 1)]
    if artifact.status != ACTIVE:
        return
    owner = world.figures.get(artifact.owner_id)
    pool = [("shown", 1.0), ("used", 1.2), ("holy", 0.5), ("hidden", 0.6),
            ("stolen", 0.7), ("mended", 0.5), ("broken", 0.5),
            ("misused", 0.4), ("banned", 0.3)]
    if artifact.where in (art.LOST, art.IN_RUIN, art.IN_TOMB):
        pool = [("forgotten", 0.0)]      # с потерянной вещью ничего не бывает
        return
    if owner is None:
        pool = [(key, weight) for key, weight in pool
                if key in ("shown", "holy", "hidden", "stolen", "banned")]
    kind = rng.weighted(pool)
    _play_deed(ctx, artifact, owner, kind, year, rng)


def _play_deed(ctx, artifact, owner, kind: str, year: int, rng) -> None:
    """Само событие: что произошло, чем кончилось и знают ли об этом."""
    world = ctx.world
    # Роль ставится не всякому событию: «вынесли на люди (свидетель)» —
    # это не роль, а шум. Роль есть там, где вещь что-то решала.
    role = ""
    outcome = ""
    known = True
    truth = art.DEED_NAMES.get(kind, kind)
    told = ""

    if kind == "used" and owner is not None:
        role = rng.weighted([(art.R_TOOL, 2.0), (art.R_WITNESS, 1.0),
                             (art.R_KEY, 0.5)])
        outcome = rng.weighted([("won", 1.4), ("half", 1.0), ("failed", 0.8),
                                ("cost", 0.6), ("hurt", 0.5)])
        truth = "%s пустил %s в дело" % (owner.name,
                                         texts.thing_acc(artifact))
        if outcome == "hurt":
            artifact.state = art.S_HURT
    elif kind == "shown":
        truth = "%s вынесли на люди" % texts.thing_acc(artifact)
    elif kind == "holy":
        if art.K_HOLY not in artifact.kinds:
            artifact.kinds.append(art.K_HOLY)
        truth = "%s объявили святыней" % texts.thing_acc(artifact)
    elif kind == "hidden":
        truth = "%s спрятали" % texts.thing_acc(artifact)
        known = rng.chance(0.4)
        told = "о ней перестали говорить" if not known else ""
    elif kind == "stolen":
        truth = "%s украли" % texts.thing_acc(artifact)
        known = rng.chance(0.7)
        told = "из сокровищницы она пропала" if not known else ""
    elif kind == "mended":
        if artifact.state == art.S_HURT:
            artifact.state = art.S_MENDED
        artifact.repairs.append({
            "год": year, "кто": owner.name if owner is not None else "неизвестно кто",
            "чем": _mend_stuff(world, artifact, rng),
            "что": rng.choice(("заменена рукоять", "перекована кромка",
                               "вставлен новый камень", "переплетена оправа",
                               "подновлена оковка"))})
        truth = "%s починили" % texts.thing_acc(artifact)
        outcome = ""
    elif kind == "broken":
        artifact.state = art.S_HURT
        truth = "%s повредили" % texts.thing_acc(artifact)
    elif kind == "misused":
        truth = "%s пустили в дело не по назначению" % texts.thing_acc(artifact)
        role = art.R_TOOL
    elif kind == "banned":
        truth = "%s велели убрать с глаз" % texts.thing_acc(artifact)

    deed = note_deed(ctx, artifact, year, kind, rng, truth=truth, told=told,
                     known=known, role=role, outcome=art.USE_END_NAMES.get(
                         outcome, ""),
                     actors=[owner.id] if owner is not None else ())
    if art.DEED_WEIGHT.get(kind, 1) >= 2 and known:
        title, text = texts.deed_line(rng, world, artifact, deed, owner)
        event = world.add_event(
            date=deed.date, era_index=world.era_index_at(year),
            kind="artifact_deed", title=title, text=text,
            importance=1 + art.DEED_WEIGHT.get(kind, 1),
            actors=[owner.id] if owner is not None else [],
            subjects=[artifact.id], region_id=artifact.region_id,
            race_id=artifact.race_id)
        deed.event_id = event.id
        artifact.deeds.append(event.id)


def _mend_stuff(world, artifact, rng) -> str:
    """Чем чинили: тем, что было под рукой в тот век."""
    pool = [item for item in world.materials.values() if item.alive]
    if not pool:
        return "тем, что нашлось"
    item = pool[rng.randint(0, len(pool) - 1)]
    return item.gen


# ---------------------------------------------------------------------------
# Что о вещи говорят
# ---------------------------------------------------------------------------


def _claims(ctx, year: int, rng, scale: float) -> None:
    """Предание, спор о подлинности, объявившаяся копия."""
    world = ctx.world
    rows = [item for item in world.artifacts.values()
            if item.tier >= art.T_HIST]
    if not rows or not rng.chance(CLAIM_CHANCE * scale):
        return
    artifact = rows[rng.randint(0, len(rows) - 1)]
    folks = [item for item in world.folks.values() if item.status == ACTIVE]
    if not folks:
        return
    folk = folks[rng.randint(0, len(folks) - 1)]
    said_key = rng.weighted([(key, 1.0) for key, _said in art.CLAIM_KINDS])
    before = world.claims_of_artifact(artifact.id)
    state = "неизвестно"
    against = ""
    for other in before:
        if other.kind != said_key and rng.chance(0.5):
            state = "спорно"
            against = other.id
            break
    claim = world.add_artifact_claim(
        artifact_id=artifact.id, kind=said_key,
        said=art.CLAIM_KIND_NAMES[said_key], who_kind="folk", who_id=folk.id,
        since=year, source=rng.choice(
            ("запись того года", "поздняя хроника", "предание стариков",
             "храмовая книга", "слово нашедшего")),
        trust=round(rng.uniform(0.2, 0.9), 2), state=state, against=against)
    if against:
        other = world.artifact_claims.get(against)
        if other is not None:
            other.state = "спорно"
            other.against = claim.id

    # Иногда спор о вещи кончается тем, что её объявляют не той.
    if rng.chance(FAKE_CHANCE):
        _doubt(ctx, artifact, year, rng, folk)


def _doubt(ctx, artifact, year: int, rng, folk) -> None:
    """Подлинность под сомнением — а то и объявилась вторая такая же."""
    world = ctx.world
    if artifact.authentic in (art.A_FAKE, art.A_COPY, art.A_RITE) \
            or artifact.parent_id:
        return                      # со списка списка не делают
    roll = rng.random()
    if roll < 0.35:
        artifact.authentic = art.A_ARGUED
        note_deed(ctx, artifact, year, "fake", rng,
                  truth="подлинность %s оспорили" % texts.thing_acc(artifact),
                  known=True, precision=art.P_YEAR)
        return
    # Объявилась вторая вещь: копия, обрядовая реплика или подделка.
    kind = rng.weighted([(art.A_COPY, 1.0), (art.A_RITE, 0.8),
                         (art.A_FAKE, 1.2)])
    twin = world.add_artifact(
        name=artifact.name, shape=artifact.shape, word=artifact.word,
        gender=artifact.gender, sort=artifact.sort,
        material=artifact.material, material_gen=artifact.material_gen,
        made=ctx.date_in(rng, year), origin=art.FORGED,
        race_id=artifact.race_id, region_id=artifact.region_id,
        tier=art.T_HIST if kind != art.A_FAKE else art.T_GOOD,
        kinds=list(artifact.kinds), authentic=kind, parent_id=artifact.id,
        origin_kind="remade" if kind == art.A_RITE else "craft",
        precision=art.P_YEAR, state=art.S_WHOLE)
    twin.notes.append("сделана по образцу вещи по имени %s" % artifact.name)
    artifact.pieces.append(twin.id)
    world.put_artifact(twin, art.IN_TEMPLE if kind == art.A_RITE
                       else art.WITH_FIGURE, twin.made,
                       how="объявилась как %s" % kind)
    note_deed(ctx, twin, year, "made", rng,
              truth="сделана по образцу вещи по имени %s" % artifact.name,
              known=kind != art.A_FAKE, precision=art.P_YEAR)
    title, text = texts.twin_found(rng, artifact, twin, kind, folk)
    world.add_event(
        date=twin.made, era_index=world.era_index_at(year),
        kind="artifact_twin", title=title, text=text, importance=2,
        subjects=[artifact.id, twin.id], region_id=artifact.region_id,
        race_id=artifact.race_id)


# ---------------------------------------------------------------------------
# Чего вещь стоит
# ---------------------------------------------------------------------------


def _worths(ctx, year: int, rng, scale: float) -> None:
    """Оценка вещи кем-то — и перемена этой оценки по названной причине."""
    world = ctx.world
    rows = [item for item in world.artifacts.values()
            if item.tier >= art.T_HIST]
    if not rows or not rng.chance(WORTH_CHANCE * scale):
        return
    artifact = rows[rng.randint(0, len(rows) - 1)]
    who = rng.choice([key for key, _said, _facets in art.APPRAISERS])
    facets = art.APPRAISER_FACETS[who]
    facet = facets[rng.randint(0, len(facets) - 1)]
    old = None
    for item in world.worths_of_artifact(artifact.id):
        if item.facet == facet and item.who_kind == who:
            old = item
            break
    level = _worth_level(world, artifact, facet, rng)
    if old is not None:
        if old.level == level:
            return
        turn = rng.choice([key for key, _said in art.WORTH_TURNS])
        old.until = year
        world.add_artifact_worth(
            artifact_id=artifact.id, facet=facet, who_kind=who,
            level=level, since=year, why=art.WORTH_TURN_NAMES[turn])
        return
    world.add_artifact_worth(
        artifact_id=artifact.id, facet=facet, who_kind=who, level=level,
        since=year, why=_worth_why(world, artifact, facet))


def _worth_level(world, artifact, facet: str, rng) -> int:
    """Насколько она дорога по этой мере — от нуля до пяти."""
    level = 1
    if facet == art.V_COIN:
        level = 1 + int(min(3, len(artifact.parts)))
        if artifact.state in ("повреждена", "разобрана"):
            level = max(0, level - 2)
    elif facet == art.V_HIST:
        level = min(5, 1 + len(world.deeds_of_artifact(artifact.id)) // 2)
    elif facet == art.V_RULE:
        level = 4 if art.K_CROWN in artifact.kinds else 1
    elif facet == art.V_FAITH:
        level = 4 if art.K_HOLY in artifact.kinds else 1
    elif facet == art.V_MAGIC:
        level = min(5, len(artifact.powers) + (1 if artifact.curse else 0))
    elif facet == art.V_LORE:
        material = world.material_by_key(_stuff_key(world, artifact))
        level = 4 if material is not None and not material.alive else 2
    elif facet == art.V_RARE_V:
        level = 4 if artifact.tier >= art.T_RELIC else 2
    else:
        level = rng.randint(1, 4)
    return max(0, min(5, level))


def _stuff_key(world, artifact) -> str:
    for part in artifact.parts:
        material = world.materials.get(part.get("материал", ""))
        if material is not None:
            return material.key
    return ""


def _worth_why(world, artifact, facet: str) -> str:
    if facet == art.V_LORE:
        key = _stuff_key(world, artifact)
        material = world.material_by_key(key) if key else None
        if material is not None and not material.alive:
            return "сделана из того, чего больше не добывают"
    if facet == art.V_RULE and art.K_CROWN in artifact.kinds:
        return "ею венчались, и без неё венчание неполно"
    if facet == art.V_FAITH and art.K_HOLY in artifact.kinds:
        return "над ней служат"
    if facet == art.V_HIST:
        return "по ней читается то, о чём иначе не узнать"
    # Пояснение, повторяющее саму меру, — пустая строка в летописи:
    # «для народа — чем она для народа». Лучше промолчать.
    return ""
