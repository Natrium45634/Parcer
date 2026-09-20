# -*- coding: utf-8 -*-
"""Наследие древних бед: беда, которая помнит прежнюю беду.

Мир, где бедствия случаются подряд и порознь, читается как погода.
Здесь у части бед есть родословная, и её видно в летописи.

Две нити лежат в других модулях: **след** — уцелевший военачальник,
кладка, печать, прореха, что спит веками и просыпается сам
(``systems/calamity``), и **глубина** — осколок великого нашествия,
поднявшийся из-под земли (``systems/upheaval``).

Третья нить здесь, и она человеческая: кто-то живой открывает дорогу
назад. Способов **двенадцать**, и мир берёт тот, для которого у него
нашлись действующие лица:

* государь идёт за силой на древнее поле;
* учёный дочитывает свод до страниц, которые прежние пропускали;
* гробокопатели сбивают печать ради золота;
* жрецы служат обряд, который не служили тысячу лет;
* проклятая вещь переходит по наследству к тому, кто её не отдаст;
* гильдия ведёт штольню глубже, чем вели деды;
* войско роет укрепления там, где рыть не следовало;
* голод гонит селиться туда, куда в сытые годы не ходили;
* легенду пересказывают так долго, что она становится указанием;
* в старом роду рождается тот, в ком прошлое проступает наружу;
* пленник, взятый в ту войну, оказывается не зверем;
* или не делает никто — просто настал срок.

Если бы путь был один, через три мира читатель знал бы наизусть, чем
кончится. Поэтому путь выбирается жребием среди тех, что миру доступны,
и цепь всё равно остаётся редкой: иначе она перестаёт быть цепью и
становится правилом.
"""

from __future__ import annotations

from . import calamity as calamity_system
from .. import catastrophe as cat
from .. import narrative_legacy as texts
from .. import sites as sites_mod
from ..models import ACTIVE

# Раз в сколько-то лет находится государь, готовый пойти за силой. Беда
# эта редкая: за десять тысяч лет её ждут три-четыре раза.
SEEK_RATE = 0.0016          # годовой шанс на весь мир
MIN_AGE = 400               # сколько лет месту, чтобы стать легендой
MIN_CITIES = 3              # мелкой державе не до древних курганов
FALL_DELAY = (2, 25)        # через сколько лет после находки приходит беда

# Куда ходят за силой: места, за которыми стоит чужая беда.
SEEK_KINDS = (sites_mod.TOMB, sites_mod.CRYPT, sites_mod.RUIN,
              sites_mod.FIELD, sites_mod.SEALED, sites_mod.SHRINE)

# Чем оборачивается находка. Ключ — род прежней беды.
HEIR_BY_KIND = {
    cat.INVASION: ("demon_invasion", "undead_tide", "void_incursion",
                   "hellish_swarm", "beast_tide"),
    cat.MAGIC: ("great_curse", "mage_war", "planar_rift", "wild_magic"),
    cat.RELIGIOUS: ("holy_war", "great_curse"),
    cat.POLITICAL: ("great_revolt", "succession_war"),
}
HEIR_DEFAULT = ("great_curse", "wild_magic", "undead_tide")


def tick(ctx, year: int) -> None:
    """Раз в год: не открыл ли кто-нибудь дорогу назад."""
    world = ctx.world
    _ripen(ctx, year)
    if not world.sites and not world.artifacts:
        return
    rng = ctx.rng("legacy", year)
    # У таких дел своя память: мир, где только что подняли старое зло,
    # не даёт второго такого же назавтра. Иначе редкость обращается в
    # обычай и перестаёт что-либо значить.
    last = int(world.notes.get(LAST_SEEK) or 0)
    memory = 1.0 if not last else min(1.0, ((year - last) / 800.0) ** 1.3)
    if not rng.chance(ctx.rate(SEEK_RATE) * memory):
        return

    # Путь выбирается жребием среди тех, что миру сейчас доступны: нет
    # гильдий — не будет штольни, нет сводов — не будет учёного.
    pairs = []
    for way in WAYS:
        if way.era and world.era_index_at(year) < way.era:
            continue
        pairs.append((way, way.weight))
    rng.shuffled(pairs)
    for _ in range(6):
        if not pairs:
            return
        way = rng.weighted(pairs)
        spark = way.find(ctx, rng, year)
        if spark is not None:
            _open_door(ctx, way, spark, year, rng)
            return
        pairs = [(item, weight) for item, weight in pairs if item is not way]


# ---------------------------------------------------------------------------
# Кто идёт и куда
# ---------------------------------------------------------------------------

def _seeker(ctx, rng, year: int):
    """Государь, которому своей силы мало.

    Жадный до власти, нечистый на руку или просто далеко зашедший в
    гордыне: на такое не решается ни праведник, ни слабая держава.
    """
    world = ctx.world
    pairs = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if len(polity.settlement_ids) < MIN_CITIES:
            continue
        if polity.notes and "пал во зло" in " ".join(polity.notes[-3:]):
            continue
        reign = world.current_reign(polity)
        if reign is None or reign.end is not None:
            continue
        ruler = world.figures.get(reign.ruler_id)
        if ruler is None or not ruler.alive_at(year):
            continue
        weight = 0.4
        if reign.alignment <= -1:
            weight += 0.5 * abs(reign.alignment)
        if reign.legitimacy == "узурпация":
            weight += 0.6
        for trait in reign.traits:
            if trait in DARK_TRAITS:
                weight += 0.5
        if reign.skills.get("вера", 5) <= 3:
            weight += 0.3
        if weight <= 0.4:
            continue          # праведный государь за таким не поедет
        pairs.append((polity, weight))
    return rng.weighted(pairs) if pairs else None


DARK_TRAITS = frozenset((
    "неразборчивый в средствах", "неразборчивая в средствах",
    "сребролюбивый", "сребролюбивая", "завистливый", "завистливая",
    "клятвопреступник", "клятвопреступница", "гонитель веры",
    "гонительница веры", "охотник до казней", "охотница до казней",
    "мстительный", "мстительная", "подозрительный", "подозрительная",
))


def _old_place(ctx, rng, polity, year: int):
    """Место, за которым стоит чужая беда, и до которого можно доехать."""
    world = ctx.world
    reach = set(polity.region_ids)
    for region_id in list(reach):
        region = world.regions.get(region_id)
        if region is not None:
            reach.update(region.neighbors)
    pairs = []
    for site in world.sites.values():
        if site.kind not in SEEK_KINDS:
            continue
        if site.status not in (sites_mod.UNTOUCHED, sites_mod.ROBBED):
            continue
        if year - site.created.year < MIN_AGE:
            continue
        if site.region_id not in reach:
            continue
        origin = world.calamities.get(site.calamity_id)
        cursed = [world.artifacts[aid] for aid in site.artifact_ids
                  if aid in world.artifacts and world.artifacts[aid].curse]
        if origin is None and not cursed:
            continue          # обычный курган силы не даёт
        # Чем древнее место и чем тяжелее была беда, тем громче слава.
        weight = 1.0 + (year - site.created.year) / 800.0
        if origin is not None:
            weight *= 1.0 + 0.4 * origin.severity
        if cursed:
            weight *= 1.8
        pairs.append((site, weight))
    return rng.weighted(pairs) if pairs else None


# ---------------------------------------------------------------------------
# Выезд
# ---------------------------------------------------------------------------

def _open_door(ctx, way, spark, year: int, rng) -> None:
    """Дверь открыли. Что именно за ней — выяснится через год-другой."""
    world = ctx.world
    site = spark.get("site")
    artifact = spark.get("artifact")
    origin = spark.get("origin")
    polity = spark.get("polity")
    date = ctx.date_in(rng, year)

    # Вещь переходит в руки, место считается вскрытым — мир запоминает
    # это и без всякой беды: кто-то ведь туда ходил.
    ruler = None
    if spark.get("actors"):
        ruler = world.figures.get(spark["actors"][0])
    if artifact is not None and ruler is not None and way.key == "ruler":
        world.put_artifact(artifact, "у владельца", date, figure=ruler,
                           polity=polity,
                           how="взята с древнего места по имени %s"
                               % (site.name if site else "без имени"))
    if site is not None and way.key in ("ruler", "delver", "guild", "war"):
        site.status = sites_mod.ROBBED
        site.opened = date
        if ruler is not None:
            site.opened_by = ruler.id

    ago = year - site.created.year if site is not None else 0
    line = texts.way_line(
        rng, way.key, who=spark.get("who", ""),
        where=site.name if site is not None else "",
        thing=artifact.name if artifact is not None else "")
    title, text = texts.door(rng, way.key, line, origin, ago,
                             site, spark.get("who", ""))
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="dark_errand",
        title=title, text=text, importance=4,
        actors=spark.get("actors", []),
        subjects=[item.id for item in (site, origin, artifact, polity)
                  if item is not None],
        region_id=spark.get("region_id", ""),
        race_id=polity.race_id if polity is not None else "")

    world.notes[LAST_SEEK] = year
    world.notes.setdefault(RIPENING, []).append({
        "year": year + rng.randint(*FALL_DELAY),
        "way": way.key,
        "polity": polity.id if polity is not None else "",
        "ruler": ruler.id if ruler is not None else "",
        "site": site.id if site is not None else "",
        "artifact": artifact.id if artifact is not None else "",
        "origin": origin.id if origin is not None else "",
        "kind": origin.kind if origin is not None else "",
        "region": spark.get("region_id", ""),
        "who": spark.get("who", ""),
    })


RIPENING = "что зреет во дворцах"
LAST_SEEK = "последний выезд за силой"


def _named(reign, ruler) -> str:
    title = (reign.title if reign is not None else "") or "государь"
    return "%s %s" % (title.lower(), ruler.name)


# ---------------------------------------------------------------------------
# Падение и новая беда
# ---------------------------------------------------------------------------

def _ripen(ctx, year: int) -> None:
    """Приходит срок тому, что зрело во дворце."""
    world = ctx.world
    pending = world.notes.get(RIPENING) or []
    if not pending:
        return
    ready = [item for item in pending if int(item.get("year", 0)) <= year]
    if not ready:
        return
    world.notes[RIPENING] = [item for item in pending
                             if int(item.get("year", 0)) > year]
    for item in ready:
        _fall(ctx, item, year)


def _fall(ctx, item, year: int) -> None:
    """Через год-другой дверь отзывается: старое зло входит обратно."""
    world = ctx.world
    way = item.get("way") or "quiet"
    polity = world.polities.get(item.get("polity"))
    if polity is not None and polity.status != ACTIVE:
        polity = None
    ruler = world.figures.get(item.get("ruler"))
    reign = world.current_reign(polity) if polity is not None else None

    rng = ctx.rng("legacy_fall", item.get("origin") or way, year)
    origin = world.calamities.get(item.get("origin"))
    artifact = world.artifacts.get(item.get("artifact"))
    site = world.sites.get(item.get("site"))
    date = ctx.date_in(rng, year)

    # Государь, открывший дверь сам, за это и платит — если дожил.
    fell = (way == "ruler" and reign is not None and ruler is not None
            and ruler.alive_at(year) and reign.ruler_id == ruler.id)
    if fell:
        date = ctx.date_in(rng, year, reign.start)
        reign.alignment = max(-3, min(reign.alignment, -2))
        if "павший во зло" not in reign.traits:
            reign.traits.append("павший во зло")
        polity.notes.append("%d: государь пал во зло" % year)
        title, text = texts.fall(rng, _named(reign, ruler), polity, artifact,
                                 origin)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="ruler_fallen", title=title, text=text, importance=5,
            actors=[ruler.id],
            subjects=[polity.id] + ([origin.id] if origin is not None else []),
            region_id=polity.region_ids[0] if polity.region_ids else "",
            race_id=polity.race_id)

    keys = HEIR_BY_KIND.get(item.get("kind"), HEIR_DEFAULT)
    spec = cat.CATALOG_BY_KEY.get(rng.choice(keys))
    if spec is None:
        return
    severity = max(3, min(5, (origin.severity if origin is not None else 3)))
    where = None
    if polity is not None and polity.region_ids:
        where = list(polity.region_ids[:3])
    elif site is not None and site.region_id:
        where = [site.region_id]
    elif item.get("region"):
        where = [item["region"]]
    child = calamity_system.start_named(
        ctx, year, spec.key, rng, severity=severity, region_ids=where)
    if child is None:
        return
    child.notes.append(WAY_NOTES.get(way, WAY_NOTES["quiet"])
                       % {"who": item.get("who") or "неизвестно кто",
                          "where": site.name if site is not None else "—"})
    if origin is not None:
        child.parent_id = origin.id
        child.notes.append("наследие беды «%s»" % origin.name)
    if artifact is not None:
        child.notes.append("через вещь по имени %s" % artifact.name)


# Чем цепь помечается в летописи — по одной строке на путь.
WAY_NOTES = {
    "ruler": "призвано государем: %(who)s",
    "scholar": "поднято по старым сводам: %(who)s",
    "delver": "выпущено гробокопателями из места по имени %(where)s",
    "priest": "призвано обрядом, который служил %(who)s",
    "heir": "пришло через проклятую вещь, что досталась %(who)s",
    "guild": "выкопано гильдией: %(who)s",
    "war": "разбужено войной у места по имени %(where)s",
    "famine": "впущено голодом: селились у места по имени %(where)s",
    "legend": "поднято по легенде, которую пересказал %(who)s",
    "blood": "проступило в крови рода: %(who)s",
    "captive": "выпущено из подземелья, где сидело со времён той войны",
    "quiet": "вернулось само: срок вышел",
}


__all__ = ["tick", "RIPENING", "WAYS"]


# ---------------------------------------------------------------------------
# Каталог путей: кто и как открывает дорогу назад
# ---------------------------------------------------------------------------


class Way:
    """Один способ вернуть старое зло в мир.

    ``find`` ищет в мире действующих лиц для этого пути и возвращает
    искру — словарь с тем, кто, где и через что, — либо None, если мир
    сейчас такого не предлагает.
    """

    __slots__ = ("key", "weight", "era", "find")

    def __init__(self, key, weight, era, find):
        self.key, self.weight, self.era, self.find = key, weight, era, find


def _spark(way, who="", where=None, origin=None, artifact=None,
           polity=None, region_id="", actors=()):
    return {"way": way, "who": who, "site": where, "origin": origin,
            "artifact": artifact, "polity": polity,
            "region_id": region_id or (where.region_id if where else ""),
            "actors": list(actors)}


def _origin_of(world, site, artifact=None):
    """Чья это беда: та, что оставила место, или та, что выковала вещь."""
    if site is not None:
        found = world.calamities.get(site.calamity_id)
        if found is not None:
            return found
    if artifact is not None:
        for note in artifact.notes:
            for calamity in world.calamities.values():
                if calamity.name and calamity.name in note:
                    return calamity
    return None


def _any_old_site(ctx, rng, year, kinds=None, need_origin=True):
    """Любое древнее место мира, за которым стоит чужая беда."""
    world = ctx.world
    pairs = []
    for site in world.sites.values():
        if kinds and site.kind not in kinds:
            continue
        if site.status not in (sites_mod.UNTOUCHED, sites_mod.ROBBED):
            continue
        if year - site.created.year < MIN_AGE:
            continue
        origin = world.calamities.get(site.calamity_id)
        if need_origin and origin is None:
            continue
        weight = 1.0 + (year - site.created.year) / 800.0
        if origin is not None:
            weight *= 1.0 + 0.35 * origin.severity
        pairs.append((site, weight))
    return rng.weighted(pairs) if pairs else None


def _cursed_thing(ctx, rng, year):
    """Проклятая вещь, у которой сейчас есть живой владелец."""
    world = ctx.world
    pairs = []
    for artifact in world.artifacts.values():
        if not artifact.curse or not artifact.owner_id:
            continue
        owner = world.figures.get(artifact.owner_id)
        if owner is None or not owner.alive_at(year):
            continue
        if year - artifact.made.year < MIN_AGE:
            continue
        pairs.append(((artifact, owner), 1.0 + len(artifact.trail) * 0.3))
    return rng.weighted(pairs) if pairs else None


def _living(world, year, roles=(), limit=400):
    """Живые личности с нужной ролью."""
    out = []
    for figure in world.figures.values():
        if not figure.alive_at(year) or not figure.roles:
            continue
        if roles and not any(role in figure.roles for role in roles):
            continue
        out.append(figure)
        if len(out) >= limit:
            break
    return out


# --- сами пути ----------------------------------------------------------

def _way_ruler(ctx, rng, year):
    polity = _seeker(ctx, rng, year)
    if polity is None:
        return None
    site = _old_place(ctx, rng, polity, year)
    if site is None:
        return None
    reign = ctx.world.current_reign(polity)
    ruler = ctx.world.figures.get(reign.ruler_id) if reign else None
    if ruler is None:
        return None
    cursed = [ctx.world.artifacts[aid] for aid in site.artifact_ids
              if aid in ctx.world.artifacts and ctx.world.artifacts[aid].curse]
    return _spark("ruler", who=_named(reign, ruler), where=site,
                  origin=_origin_of(ctx.world, site),
                  artifact=cursed[0] if cursed else None,
                  polity=polity, actors=[ruler.id])


def _way_scholar(ctx, rng, year):
    world = ctx.world
    codices = [world.codices[cid] for cid in world.codices
               if world.codices[cid].span >= 200]
    if not codices:
        return None
    codex = rng.choice(codices)
    keeper = world.figures.get(codex.keeper_id)
    if keeper is None or not keeper.alive_at(year):
        scholars = _living(world, year, ("летописец", "летописица", "учёный"))
        keeper = rng.choice(scholars) if scholars else None
    if keeper is None:
        return None
    site = _any_old_site(ctx, rng, year)
    return _spark("scholar", who=keeper.name, where=site,
                  origin=_origin_of(world, site),
                  polity=world.polities.get(codex.polity_id),
                  region_id=codex.region_id, actors=[keeper.id])


def _way_delver(ctx, rng, year):
    site = _any_old_site(ctx, rng, year,
                         kinds=(sites_mod.SEALED, sites_mod.CRYPT,
                                sites_mod.TOMB, sites_mod.SUNKEN))
    if site is None:
        return None
    folk = _living(ctx.world, year)
    who = rng.choice(folk).name if folk else "ватага без имени"
    return _spark("delver", who=who, where=site,
                  origin=_origin_of(ctx.world, site))


def _way_priest(ctx, rng, year):
    world = ctx.world
    if not world.living_faiths:
        return None
    faith = world.faiths.get(rng.choice(list(world.living_faiths)))
    if faith is None:
        return None
    site = _any_old_site(ctx, rng, year,
                         kinds=(sites_mod.SHRINE, sites_mod.CRYPT,
                                sites_mod.RUIN, sites_mod.TOMB))
    if site is None:
        return None
    priests = _living(world, year, ("жрец", "жрица", "пророк", "пророчица"))
    who = rng.choice(priests).name if priests else faith.name
    return _spark("priest", who=who, where=site,
                  origin=_origin_of(world, site),
                  polity=None, actors=[])


def _way_heir(ctx, rng, year):
    row = _cursed_thing(ctx, rng, year)
    if row is None:
        return None
    artifact, owner = row
    return _spark("heir", who=owner.name, artifact=artifact,
                  origin=_origin_of(ctx.world, None, artifact),
                  region_id=artifact.region_id, actors=[owner.id])


def _way_guild(ctx, rng, year):
    world = ctx.world
    guilds = [world.guilds[gid] for gid in world.guilds]
    if not guilds:
        return None
    guild = rng.weighted([(item, 1.0 + item.wealth / 2000.0)
                          for item in guilds])
    site = _any_old_site(ctx, rng, year)
    if site is None:
        return None
    head = world.figures.get(guild.head_id)
    return _spark("guild", who=head.name if head else guild.name, where=site,
                  origin=_origin_of(world, site),
                  polity=world.polities.get(guild.polity_id))


def _way_war(ctx, rng, year):
    world = ctx.world
    if not world.active_wars:
        return None
    site = _any_old_site(ctx, rng, year,
                         kinds=(sites_mod.FIELD, sites_mod.SEALED,
                                sites_mod.TOMB, sites_mod.RUIN))
    if site is None:
        return None
    war = world.wars.get(rng.choice(list(world.active_wars)))
    return _spark("war", who=war.name if war else "войско", where=site,
                  origin=_origin_of(world, site))


def _way_famine(ctx, rng, year):
    world = ctx.world
    hungry = [world.polities[pid] for pid in world.active_polities
              if world.polities[pid].hunger >= 0.3]
    if not hungry:
        return None
    polity = rng.choice(hungry)
    site = _any_old_site(ctx, rng, year)
    if site is None:
        return None
    return _spark("famine", who=polity.full_name, where=site,
                  origin=_origin_of(world, site), polity=polity)


def _way_legend(ctx, rng, year):
    world = ctx.world
    old = [item for item in world.legends.values()
           if item.shifts and year - item.born.year >= 200]
    if not old:
        return None
    legend = rng.choice(old)
    site = _any_old_site(ctx, rng, year)
    folk = _living(world, year, ("сказитель", "сказительница", "летописец"))
    who = rng.choice(folk).name if folk else legend.name
    return _spark("legend", who=who, where=site,
                  origin=_origin_of(world, site),
                  region_id=legend.region_id)


def _way_blood(ctx, rng, year):
    world = ctx.world
    houses = [world.houses[hid] for hid in world.active_houses
              if year - world.houses[hid].founded.year >= 300]
    if not houses:
        return None
    house = rng.choice(houses)
    kin = [world.figures[fid] for fid in world.figures
           if world.figures[fid].house_id == house.id
           and world.figures[fid].alive_at(year)]
    if not kin:
        return None
    heir = rng.choice(kin)
    site = _any_old_site(ctx, rng, year)
    return _spark("blood", who=heir.name, where=site,
                  origin=_origin_of(world, site),
                  polity=world.polities.get(house.polity_id),
                  actors=[heir.id])


def _way_captive(ctx, rng, year):
    world = ctx.world
    old = []
    for calamity in world.calamities.values():
        if calamity.kind != cat.INVASION or calamity.end is None:
            continue
        if year - calamity.end.year < MIN_AGE:
            continue
        if calamity.captive_taken:
            continue
        old.append(calamity)
    if not old:
        return None
    origin = rng.choice(old)
    origin.captive_taken = True
    site = _any_old_site(ctx, rng, year, need_origin=False)
    return _spark("captive", who="", where=site, origin=origin)


def _way_quiet(ctx, rng, year):
    site = _any_old_site(ctx, rng, year)
    if site is None:
        return None
    return _spark("quiet", where=site, origin=_origin_of(ctx.world, site))


WAYS = (
    Way("ruler", 1.6, 2, _way_ruler),
    Way("scholar", 1.3, 2, _way_scholar),
    Way("delver", 1.5, 1, _way_delver),
    Way("priest", 1.2, 1, _way_priest),
    Way("heir", 1.3, 1, _way_heir),
    Way("guild", 1.0, 3, _way_guild),
    Way("war", 1.1, 2, _way_war),
    Way("famine", 0.9, 1, _way_famine),
    Way("legend", 1.0, 2, _way_legend),
    Way("blood", 1.1, 2, _way_blood),
    Way("captive", 0.8, 2, _way_captive),
    Way("quiet", 0.7, 0, _way_quiet),
)
