# -*- coding: utf-8 -*-
"""Наследие древних бед: беда, которая помнит прежнюю беду.

Мир, где бедствия случаются подряд и порознь, читается как погода.
Здесь у части бед есть родословная, и её видно в летописи.

Три нити ведут от старой беды к новой:

* **След** — уцелевший военачальник, кладка, печать, прореха. Он спит
  веками и однажды просыпается сам; этим занимается ``systems/calamity``.
* **Глубина** — осколок великого нашествия, поднявшийся из-под земли;
  этим занимается ``systems/upheaval``.
* **Государь** — и это здесь. Держава богата и спокойна, а государь едет
  к месту, где полторы тысячи лет назад добили чужое войско, и выносит
  оттуда то, что там лежало. Через год-другой двор замечает, что правит
  уже не совсем он.

Нарочно не всякая беда такова: цепь должна быть редкой, иначе она
перестаёт быть цепью и становится правилом.
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
    """Раз в год: не нашёлся ли государь, которому мало своей силы."""
    world = ctx.world
    _ripen(ctx, year)
    if not world.active_polities or not world.sites:
        return
    rng = ctx.rng("legacy", year)
    # У таких выездов своя память: мир, где государь только что пал во
    # зло, не даёт второго такого же назавтра. Иначе редкость обращается
    # в обычай и перестаёт что-либо значить.
    last = int(world.notes.get(LAST_SEEK) or 0)
    memory = 1.0 if not last else min(1.0, ((year - last) / 800.0) ** 1.3)
    if not rng.chance(ctx.rate(SEEK_RATE) * memory):
        return

    polity = _seeker(ctx, rng, year)
    if polity is None:
        return
    site = _old_place(ctx, rng, polity, year)
    if site is None:
        return
    _seek(ctx, polity, site, year, rng)


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

def _seek(ctx, polity, site, year: int, rng) -> None:
    world = ctx.world
    reign = world.current_reign(polity)
    ruler = world.figures.get(reign.ruler_id) if reign is not None else None
    if ruler is None:
        return
    origin = world.calamities.get(site.calamity_id)
    cursed = [world.artifacts[aid] for aid in site.artifact_ids
              if aid in world.artifacts and world.artifacts[aid].curse]
    artifact = cursed[0] if cursed else None
    date = ctx.date_in(rng, year)

    if artifact is not None:
        world.put_artifact(artifact, "у владельца", date, figure=ruler,
                           polity=polity,
                           how="взята с древнего места по имени %s" % site.name)
    site.status = sites_mod.ROBBED
    site.opened = date
    site.opened_by = ruler.id
    ruler.notes.append("ходил за силой к месту по имени %s в %d году"
                       % (site.name, year))

    ago = year - site.created.year
    title, text = texts.seek(rng, _named(reign, ruler), site, origin, ago,
                             artifact, ruler.sex)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="dark_errand",
        title=title, text=text, importance=4, actors=[ruler.id],
        subjects=[polity.id, site.id]
        + ([artifact.id] if artifact is not None else [])
        + ([origin.id] if origin is not None else []),
        region_id=site.region_id, race_id=polity.race_id)

    world.notes[LAST_SEEK] = year
    # Беда приходит не в тот же день: сперва двор замечает перемену.
    world.notes.setdefault(RIPENING, []).append({
        "year": year + rng.randint(*FALL_DELAY),
        "polity": polity.id,
        "ruler": ruler.id,
        "site": site.id,
        "artifact": artifact.id if artifact is not None else "",
        "origin": origin.id if origin is not None else "",
        "kind": origin.kind if origin is not None else "",
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
    world = ctx.world
    polity = world.polities.get(item.get("polity"))
    if polity is None or polity.status != ACTIVE:
        return
    ruler = world.figures.get(item.get("ruler"))
    reign = world.current_reign(polity)
    if reign is None or ruler is None or reign.ruler_id != ruler.id:
        return          # государь не дожил — зло осталось лежать
    if not ruler.alive_at(year):
        return

    rng = ctx.rng("legacy_fall", polity.id, year)
    origin = world.calamities.get(item.get("origin"))
    artifact = world.artifacts.get(item.get("artifact"))
    date = ctx.date_in(rng, year, reign.start)

    reign.alignment = max(-3, min(reign.alignment, -2))
    if "павший во зло" not in reign.traits:
        reign.traits.append("павший во зло")
    polity.notes.append("%d: государь пал во зло" % year)

    title, text = texts.fall(rng, _named(reign, ruler), polity, artifact,
                             origin)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="ruler_fallen",
        title=title, text=text, importance=5, actors=[ruler.id],
        subjects=[polity.id] + ([origin.id] if origin is not None else []),
        region_id=polity.region_ids[0] if polity.region_ids else "",
        race_id=polity.race_id)

    keys = HEIR_BY_KIND.get(item.get("kind"), HEIR_DEFAULT)
    spec = cat.CATALOG_BY_KEY.get(rng.choice(keys))
    if spec is None:
        return
    severity = max(3, min(5, (origin.severity if origin is not None else 3)))
    child = calamity_system.start_named(
        ctx, year, spec.key, rng, severity=severity,
        region_ids=list(polity.region_ids[:3]) or None)
    if child is None:
        return
    child.notes.append("призвано государем державы по имени %s" % polity.name)
    if origin is not None:
        child.parent_id = origin.id
        child.notes.append("наследие беды «%s»" % origin.name)
    if artifact is not None:
        child.notes.append("через вещь по имени %s" % artifact.name)


__all__ = ["tick", "RIPENING"]
