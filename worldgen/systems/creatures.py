# -*- coding: utf-8 -*-
"""Жизнь видов: кто водится в этом мире, откуда взялся и что с ним стало.

Чудовищ ведёт ``systems/monsters.py`` — там логово, разор и охота. Тут
другое и выше этажом: не особь, а **вид**, и не повадка, а его история.

Четыре вещи, которые тут происходят по-настоящему, а не записываются в
справку.

**Кто вообще есть.** Видов в справочнике два с половиной десятка, а в
мире живёт дюжина: драконы есть не во всяком мире, а гидры — тем более.
Берётся вид не наугад: нужна земля, в которой он водится, а магическим
видам нужна магия — в мире без неё их нет вовсе.

**Разумны ли они тут.** Шесть видов могут оказаться либо народом, либо
зверьём: орки, гоблины, тролли, огры, кобольды, гноллы. Если вид вышел
зверьём, раса **не просыпается вовсе** — ни языка, ни племён, ни держав,
ни веры. Мир от этого выходит другой, а не беднее: вместо орочьих
каганатов в нём степь, по которой ходит то, с чем не договариваются.

**Разум приходит и уходит.** Зверьё может поумнеть — и тогда у него
начинается история, с года и с причины: бог коснулся, выучились у
соседей, выпили кровь павшего небывалого, дошли сами за тысячу лет.
Народ может одичать — но не просто так: только после того, как народом
быть перестал, и тогда беда, которая его доконала, и записывается
причиной.

**Ветви и ступени.** У вида заводятся разновидности — пещерные, огненные,
порченые, — и всякая отчего-то. А у именованной особи растёт ступень: не
броском, а годами, налётами и съеденными, — и потому великих в мире
единицы, а не каждый третий.
"""

from __future__ import annotations

from .. import creatures as cr
from .. import narrative_creatures as texts
from .. import races as races_mod
from ..origin import MAGIC

# Сколько видов мир заводит: доля от справочника. Если водится всё, то
# не водится ничего — встреча с драконом должна быть событием.
KIND_CHANCE = 0.46
# Шанс, что вид-народ в этом мире окажется зверьём, и сколько таких
# на мир. Двух довольно: три одичавших народа — это уже не особенность
# мира, а другой справочник рас.
FERAL_CHANCE = 0.22
FERAL_MAX = 2
# Поумнеть зверьё может раз за всю историю. При прежней частоте за три
# десятка тысяч лет это не случилось ни разу: рычаг был, а мира, где им
# что-то решалось, — ни одного. Теперь за полную историю обретает разум
# примерно каждый второй одичавший род, то есть видно это в трети миров.
RISE_RATE = 0.0008
# Одичать народ может только после того, как перестал быть народом.
FALL_CHANCE = 0.35
# Разновидности: сколько их бывает у вида и как часто заводятся. При
# большей частоте за десять тысяч лет всякий вид упирался в потолок, и
# «три ветви» выходило не редкостью, а правилом.
VARIANT_RATE = 0.0012
VARIANT_MAX = 3
# Вид может вывестись и вернуться. И то, и другое — редкость: при
# прежней частоте за десять тысяч лет уходили и возвращались по три вида
# на мир, и уход переставал что-либо значить.
GONE_RATE = 0.00012
BACK_RATE = 0.0025
GONE_QUIET = 600            # сколько лет его не видно, прежде чем вернётся

# --- ступени именованных особей -------------------------------------------
#
# Ступень набирается, а не бросается, и считается с убылью: тысячелетний
# дракон весомее столетнего, но не в десять раз. Пороги подобраны не на
# глаз, а по замеру: двести именованных тварей с двух десятитысячелетних
# миров, и считано вместе с потолками редкости. При первых порогах
# великих выходило по два десятка на мир, то есть «великий дракон» значил
# не больше, чем «дракон». При нынешних на десять тысяч лет приходится
# два великих и десяток древних — один раз в тысячу лет и один раз в
# девять веков; а это уже события, которые помнят.
TIER_STEPS = (2.4, 4.2, 6.6, 9.6, 13.5, 18.5, 25.0)
# И сверх порогов — потолок на весь мир: больше этого великих разом не
# бывает, сколько бы они ни наели.
GREAT_ALIVE = 2


# ---------------------------------------------------------------------------
# Начало мира: кто тут водится
# ---------------------------------------------------------------------------

def prepare(ctx) -> None:
    """Решает, какие виды живут в этом мире и разумны ли они тут.

    Идёт после начала мира (нужны его законы: мир без магии не заводит
    магических тварей) и **до** расписания пробуждений: если орки в этом
    мире — зверьё, раса их не просыпается, и знать об этом надо раньше.
    """
    world = ctx.world
    rng = ctx.rng("creatures", "prepare")
    magic = _has_magic(world)
    terrains = {region.terrain for region in world.regions.values()}

    feral_left = FERAL_MAX
    for kind in cr.KINDS:
        if kind.terrains and terrains and not (set(kind.terrains) & terrains):
            continue        # негде водиться — и не водится
        folk = cr.can_be_folk(kind.key)
        # Вид-народ в мире есть всегда: его раса стоит в справочнике, и
        # не нам её отменять. Прочие заводятся не во всяком мире.
        if not folk and not rng.chance(min(0.95, KIND_CHANCE * kind.weight)):
            continue

        origin = _origin_for(rng, kind, magic)
        mind = kind.mind
        if folk and feral_left > 0 and rng.chance(FERAL_CHANCE):
            # Вот он, другой мир: эти — не народ, а зверьё.
            mind = kind.feral or cr.CUNNING
            feral_left -= 1

        kin = world.add_species(
            kind=kind.key, name=kind.plural, word=kind.word,
            gender=kind.gender, race_id=kind.race_id, origin=origin,
            origin_year=0, rarity=kind.rarity, social=kind.social,
            diet=kind.diet, breeding=kind.breeding,
            years=_years_for(rng, kind),
            base_mind=mind, mind=mind)
        if mind != kind.mind:
            kin.notes.append("в этом мире они не народ, а зверьё")


def settle(ctx) -> None:
    """Привязывает происхождение видов к тому, что в мире уже есть.

    Бог, который их сделал, первородный, чья кровь в них течёт, — всё
    это выбирается после того, как боги появились. И тогда же о каждом
    виде пишется первая запись: откуда он взялся.
    """
    world = ctx.world
    rng = ctx.rng("creatures", "settle")
    for kin in sorted(world.species.values(), key=lambda item: item.id):
        maker = _maker_for(world, kin, rng)
        if maker is not None:
            kin.maker_id = maker.id
            kin.origin_note = maker.given_name
        title, text = texts.species_born(rng, kin, kin.origin_note)
        world.add_event(
            date=ctx.date_in(rng, 1), era_index=0, kind="species_born",
            title=title, text=text,
            # Откуда взялся вид — это не новость года, а подкладка мира:
            # в ленту летописи такое лезть не должно.
            importance=1, race_id=kin.race_id)


def is_feral_race(world, race_id: str) -> bool:
    """Зверьё ли эта раса в этом мире — тогда она не просыпается народом."""
    kin = world.species_of_race(race_id)
    if kin is None:
        return False
    return cr.can_be_folk(kin.kind) and not kin.is_people


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.species:
        return
    rng = ctx.rng("creatures", year)
    scale = period / 10.0
    for kin in sorted(world.species.values(), key=lambda item: item.id):
        if kin.status == "сгинул":
            continue
        if kin.status == "не встречается":
            _maybe_back(ctx, kin, year, rng, scale)
            continue
        _maybe_rise(ctx, kin, year, rng, scale)
        _maybe_fall(ctx, kin, year, rng)
        _maybe_variant(ctx, kin, year, rng, scale)
        _maybe_gone(ctx, kin, year, rng, scale)


# ---------------------------------------------------------------------------
# Разум приходит
# ---------------------------------------------------------------------------

def _maybe_rise(ctx, kin, year: int, rng, scale: float) -> None:
    """Зверьё, которое поумнело: с этого года у него начинается история."""
    world = ctx.world
    if kin.is_people or not cr.can_be_folk(kin.kind):
        return
    if kin.mind_marks:
        return          # дважды такого с одним родом не бывает
    if not rng.chance(RISE_RATE * scale):
        return
    why = _rise_why(ctx, rng)
    was = kin.mind
    kin.mind = cr.SENTIENT
    kin.mind_marks.append({"год": year, "было": was, "стало": kin.mind,
                           "отчего": cr.RISE_BY_KEY[why][0],
                           "ключ": why})
    title, text = texts.mind_rise(rng, kin, why)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="species_mind_rise", title=title, text=text, importance=5,
        race_id=kin.race_id)
    # И это не запись в справке: раса просыпается прямо сейчас.
    _wake_race(ctx, kin, year)


def _rise_why(ctx, rng) -> str:
    """Причина берётся не из воздуха, а из того, что в мире есть."""
    world = ctx.world
    gods = any(deity for deity in world.deities.values())
    fallen = any(item.status != "жив" for item in world.monsters.values())
    pairs = []
    for key, _about, _short in cr.RISE_WHYS:
        if key in ("god_touch", "god_pity") and not gods:
            continue
        if key == "blood" and not fallen:
            continue
        if key == "magic_tide" and not _has_magic(world):
            continue
        weight = 1.0
        if key == "slow":
            weight = 1.6        # сами дошли — самый частый случай
        pairs.append((key, weight))
    if not pairs:
        return "slow"
    return rng.weighted(pairs)


def _wake_race(ctx, kin, year: int) -> None:
    """Разбудить расу тем же порядком, каким она просыпается по расписанию."""
    from . import peoples
    if not kin.race_id:
        return
    race = races_mod.RACES_BY_ID.get(kin.race_id)
    if race is None or kin.race_id in ctx.world.race_awakening:
        return
    peoples.awaken_now(ctx, race, year)


# ---------------------------------------------------------------------------
# Разум уходит
# ---------------------------------------------------------------------------

def _maybe_fall(ctx, kin, year: int, rng) -> None:
    """Народ, которого не стало, может остаться видом — одичавшим.

    Сам по себе народ не глупеет: это была бы отмена его истории задним
    числом. Одичать он может только после того, как народом быть
    перестал, — и тогда причиной записывается та беда, что его доконала.
    """
    world = ctx.world
    if not kin.is_people or not kin.race_id:
        return
    from . import upheaval
    if not upheaval.is_gone(world, kin.race_id):
        return
    if kin.mind_marks and kin.mind_marks[-1].get("ключ") in cr.FALL_BY_KEY:
        return
    if not rng.chance(FALL_CHANCE):
        kin.status = "сгинул"
        kin.gone_year = year
        kin.gone_why = "их не стало вместе с их народом"
        return
    why = _fall_why(world, kin)
    was = kin.mind
    kin.mind = cr.KINDS_BY_KEY[kin.kind].feral or cr.CUNNING
    kin.mind_marks.append({"год": year, "было": was, "стало": kin.mind,
                           "отчего": cr.FALL_BY_KEY[why][0], "ключ": why})
    title, text = texts.mind_fall(rng, kin, why)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="species_mind_fall", title=title, text=text, importance=4,
        race_id=kin.race_id)


def _fall_why(world, kin) -> str:
    """Отчего одичали: по той беде, которая взяла их больше всех."""
    best, best_toll = None, 0
    for calamity in world.calamities.values():
        toll = calamity.deaths_by_race.get(kin.race_id, 0)
        if toll > best_toll:
            best, best_toll = calamity, toll
    if best is None:
        return "left"
    kind = getattr(best, "kind", "")
    if kind in ("мор", "поветрие", "магия"):
        return "plague"
    if kind in ("нашествие", "война"):
        return "demon"
    return "ruin"


# ---------------------------------------------------------------------------
# Ветви
# ---------------------------------------------------------------------------

def _maybe_variant(ctx, kin, year: int, rng, scale: float) -> None:
    world = ctx.world
    if len(kin.variants) >= VARIANT_MAX:
        return
    if not rng.chance(VARIANT_RATE * scale):
        return
    kind = cr.KINDS_BY_KEY[kin.kind]
    pairs = []
    for key, _name, _about in cr.VARIANT_KINDS:
        if key == cr.MAGICAL and not _has_magic(world):
            continue
        if key == cr.RISEN and kin.origin not in ("elder_kin", "god_made",
                                                  "god_blood", "fallen_god"):
            continue
        pairs.append((key, 1.0))
    if not pairs:
        return
    variant_kind = rng.weighted(pairs)
    word = cr.variant_word(rng, kind, variant_kind)
    name = "%s %s" % (word, kind.word.lower())
    if any(row.get("имя") == name for row in kin.variants):
        return
    region = _some_region(world, kind, rng)
    why = rng.choice(cr.VARIANT_WHYS[variant_kind])
    kin.variants.append({"имя": name, "слово": word, "род": variant_kind,
                         "год": year, "отчего": why,
                         "земля": region.name if region is not None else ""})
    if region is not None and region.id not in kin.regions:
        kin.regions.append(region.id)
    title, text = texts.variant_born(rng, kin, name, why, region)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="species_variant", title=title, text=text, importance=2,
        region_id=region.id if region is not None else "",
        race_id=kin.race_id)


# ---------------------------------------------------------------------------
# Вид выводится и возвращается
# ---------------------------------------------------------------------------

def _maybe_gone(ctx, kin, year: int, rng, scale: float) -> None:
    """Вывестись может только тот, кого и так было мало."""
    world = ctx.world
    if kin.is_people or cr.rarity_named(kin.rarity) > 4:
        return
    if any(world.monsters[mid].status == "жив"
           for mid in kin.named if mid in world.monsters):
        return
    if not rng.chance(GONE_RATE * scale):
        return
    kin.status = "не встречается"
    kin.gone_year = year
    kin.gone_why = "их перебили быстрее, чем они успевали плодиться"
    region = _some_region(world, cr.KINDS_BY_KEY[kin.kind], rng)
    title, text = texts.species_gone(rng, kin, kin.gone_why, region)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="species_gone", title=title, text=text, importance=3,
        region_id=region.id if region is not None else "",
        race_id=kin.race_id)


def _maybe_back(ctx, kin, year: int, rng, scale: float) -> None:
    world = ctx.world
    if year - int(kin.gone_year or 0) < GONE_QUIET:
        return
    if not rng.chance(BACK_RATE * scale):
        return
    kin.status = "живёт"
    kin.back_year = year
    region = _some_region(world, cr.KINDS_BY_KEY[kin.kind], rng)
    if region is not None and region.id not in kin.regions:
        kin.regions.append(region.id)
    title, text = texts.species_back(rng, kin, region)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="species_back", title=title, text=text, importance=3,
        region_id=region.id if region is not None else "",
        race_id=kin.race_id)


# ---------------------------------------------------------------------------
# Именованная особь: кто она такая и как растёт
# ---------------------------------------------------------------------------

def attach(ctx, monster, breed, region, year: int, rng) -> None:
    """Приписать чудовищу вид, ветвь и источник силы.

    Вид у породы может и не водиться в этом мире — тогда запись о нём
    заводится прямо тут: раз эта тварь есть, значит, род её в мире всё же
    есть, просто мир о нём до сих пор не знал.
    """
    world = ctx.world
    kind = cr.KINDS_BY_BREED.get(breed.key)
    if kind is None:
        return
    kin = world.species_of(kind.key)
    if kin is None:
        kin = world.add_species(
            kind=kind.key, name=kind.plural, word=kind.word,
            gender=kind.gender, race_id=kind.race_id,
            origin=_origin_for(rng, kind, _has_magic(world)),
            origin_year=year, rarity=kind.rarity, social=kind.social,
            diet=kind.diet, breeding=kind.breeding,
            years=_years_for(rng, kind),
            base_mind=kind.mind, mind=kind.mind)
    monster.species = kind.key
    monster.source = _power_for(rng, kin)
    monster.tier = 0
    if kin.variants and rng.chance(0.45):
        row = rng.choice(kin.variants)
        monster.variant = row.get("слово", "")
        monster.variant_kind = row.get("род", "")
    if monster.id not in kin.named:
        kin.named.append(monster.id)
    if region is not None and region.id not in kin.regions:
        kin.regions.append(region.id)
    if kin.status != "живёт":
        kin.status = "живёт"


def grow(ctx, monster, year: int, rng) -> None:
    """Пересчитать ступень по прожитому и сделанному — и записать рост.

    Ступень не бросается: её набирают. Поэтому великим чудовище
    становится не при появлении, а через века налётов, и в летописи это
    отдельное событие — чаще всего последнее, что о нём успевают
    записать спокойно.
    """
    world = ctx.world
    if not monster.species:
        return
    kin = world.species_of(monster.species)
    if kin is None:
        return
    lived = max(0, year - int(monster.born.year))
    want = tier_for(lived, monster.raids, monster.kills, monster.hoard,
                    cr.lift_of(monster.source), cr.rarity_cap(kin.rarity))
    if want >= cr.TIER_GREAT and _greats_alive(world) >= GREAT_ALIVE:
        want = cr.TIER_GREAT - 1
    if want <= monster.tier:
        return
    monster.tier = want
    why = _why_grew(monster, lived)
    monster.tier_marks.append({"год": year, "ступень": want, "отчего": why})
    kin.top_tier = max(kin.top_tier, want)
    if want < cr.TIER_KNOWN:
        return          # до четвёртой ступени мир о таком не пишет
    region = world.regions.get(monster.region_id)
    title, text = texts.tier_grew(rng, monster, cr.KINDS_BY_KEY[kin.kind],
                                  region, want, why)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="creature_tier", title=title, text=text,
        importance=5 if want >= cr.TIER_GREAT else 3,
        subjects=[monster.id],
        region_id=monster.region_id)


def tier_for(years: int, raids: int, kills: int, hoard: int,
             lift: float, cap: int) -> int:
    """Ступень по прожитому и сделанному, с убылью.

    С убылью — потому что тысячелетний дракон весомее столетнего, но не
    в десять раз, и три сотни съеденных не делают тварь втрое страшнее
    сотни. Без этого ступень считалась бы по счёту убитых, а счёт убитых
    растёт сам собой у всякого, кто просто долго живёт.
    """
    # Веса подобраны так, чтобы ни одно слагаемое не забивало прочие. При
    # прежних налёты решали всё: у твари, прожившей девять тысяч лет, их
    # набиралось триста пятьдесят, и один этот счёт тянул её в легенды
    # помимо всего, что она сделала.
    score = (1.6 * (max(0, years) / 300.0) ** 0.5
             + 0.8 * max(0, raids) ** 0.5
             + 1.0 * (max(0, kills) / 500.0) ** 0.5
             + 0.6 * (max(0, hoard) / 50000.0) ** 0.5)
    score *= max(0.5, lift)
    tier = 0
    for step in TIER_STEPS:
        if score >= step:
            tier += 1
    return max(0, min(cap, cr.TOP_TIER, tier))


def _why_grew(monster, lived: int) -> str:
    """Отчего поднялся — по тому, чего у него больше.

    Род у твари свой, поэтому слова берутся парами: «пережил» годится
    дракону, но не гидре.
    """
    name, _about, _lift = cr.POWERS_BY_KEY.get(monster.source,
                                               cr.POWERS_BY_KEY["age"])
    gender = getattr(monster, "gender", "m")
    its = texts.pair(gender, "ним", "ней")
    whose = texts.pair(gender, "его", "её")
    if monster.kills >= 1500:
        return ("за %s столько съеденных, что счёт им ведут только в песнях"
                % its)
    if monster.raids >= 8:
        return "округа платит %s уже которое поколение" % texts.pair(
            gender, "ему", "ей")
    if lived >= 600:
        return "%s пережила всех, кто помнил её молодой" % monster.name \
            if gender == "f" else \
            "%s пережил всех, кто помнил его молодым" % monster.name
    if monster.hoard >= 120000:
        return "клад %s стоит больше иной казны, и это тоже сила" % whose
    return "сила %s %s" % (whose, name)


def _greats_alive(world) -> int:
    return sum(1 for mid in world.living_monsters
               if world.monsters[mid].tier >= cr.TIER_GREAT)


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _years_for(rng, kind) -> int:
    """Сколько живёт обычная особь этого вида.

    У вида, за которым стоит раса, век берётся у расы: иначе книга о
    видах говорила бы одно, а весь остальной генератор — другое.
    """
    race = races_mod.RACES_BY_ID.get(kind.race_id) if kind.race_id else None
    span = getattr(race, "lifespan", None) if race is not None else None
    low, high = span if span else kind.years
    return int(rng.uniform(low, high))


def _has_magic(world) -> bool:
    """Есть ли в этом мире магия вообще."""
    origin = world.origin
    if origin is None:
        return True
    return MAGIC not in (origin.missing or ())


def _origin_for(rng, kind, magic: bool) -> str:
    pairs = []
    for key, _name, _about in cr.ORIGINS:
        if key in cr.MAGIC_ORIGINS and not magic:
            continue
        if key == "fallen_folk" and not cr.can_be_folk(kind.key):
            continue
        weight = 1.0
        if key == "natural":
            weight = 2.4        # большинство завелось само
        elif key in ("unknown", "otherworld"):
            weight = 0.7
        elif key == "fallen_god":
            weight = 0.4
        pairs.append((key, weight))
    return rng.weighted(pairs)


def _power_for(rng, kin) -> str:
    """Откуда у этой особи сила — не ради красоты, а чтобы было чем расти.

    Источник выбирается по виду и по его происхождению: у потомка
    первородного сила идёт от крови, у вида без магии магической силы
    взяться неоткуда.
    """
    pairs = []
    for key, _name, _about, _lift in cr.POWERS:
        weight = 1.0
        if key == "elder_blood":
            weight = 2.2 if kin.origin in ("elder_kin", "god_blood") else 0.3
        elif key == "blessing":
            weight = 1.8 if kin.origin == "god_made" else 0.4
        elif key == "taint":
            weight = 1.8 if kin.origin in ("beast_made", "cursed") else 0.5
        elif key == "age":
            weight = 1.8        # чаще всего сила — это просто прожитые годы
        elif key == "learned" and not cr.mind_of(kin.mind).tools:
            continue            # зверя никто не учил
        pairs.append((key, weight))
    return rng.weighted(pairs)


def _maker_for(world, kin, rng):
    """Тот, кто за этим стоит: бог, первородный или никто."""
    if kin.origin not in ("god_made", "god_blood", "beast_made", "elder_kin",
                          "fallen_god"):
        return None
    want_first = kin.origin in ("god_blood", "elder_kin", "fallen_god")
    pool = [deity for deity in world.deities.values()
            if bool(getattr(deity, "primordial", False)) == want_first]
    if not pool:
        pool = list(world.deities.values())
    if not pool:
        return None
    pool.sort(key=lambda item: item.id)
    return rng.choice(pool)


def _some_region(world, kind, rng):
    """Земля, в которой этот вид мог бы водиться."""
    good = [region for region in world.regions.values()
            if not getattr(region, "drowned", False)
            and (not kind.terrains or region.terrain in kind.terrains)]
    if not good:
        good = [region for region in world.regions.values()
                if not getattr(region, "drowned", False)]
    if not good:
        return None
    good.sort(key=lambda item: item.id)
    return rng.choice(good)


__all__ = ["prepare", "settle", "upkeep", "attach", "grow", "tier_for",
           "is_feral_race"]
