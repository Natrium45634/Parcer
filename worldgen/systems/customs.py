# -*- coding: utf-8 -*-
"""Жизнь обычая: отчего он заводится, как расходится и чем кончается.

Раз в десять лет система делает четыре вещи.

**Заводит обычай — из условий и из случившегося.** Не бросает жребий по
списку готовых традиций, а смотрит на народ: в какой земле он живёт,
какой у него век, есть ли письмо, ремесло, храм, держава, и что с ним
случилось за последние полвека. Из этого выходит задача, которую
обществу надо решить («сохранить умение», «унять распрю», «не дать
забыть»), а уже под задачу подбирается форма, которой в этих условиях
есть чем держаться. Поэтому обычай у народа с камнем под ногами и
обычай у народа на воде выходят разными, даже когда решают одно и то же.

**Ведёт те, что есть.** Обычай расходится к соседям — с торговлей,
через смешанные семьи, с переселенцами, с мечом; его забирает себе
держава или храм; его переделывают, запрещают, он уходит в тайну,
усыхает до одного движения, раскалывается на изводы, забывается и
возвращается. У каждого поворота названа причина, и причина берётся из
мира, а не из воздуха.

**Теряет причину.** Через века настоящая причина уходит раньше самого
обычая: те, кто помнил, умерли; запись сгорела; пришёл другой народ и
объяснил по-своему. Делать не перестали — объяснения разошлись. Это не
поломка памяти, а её работа, и именно отсюда берутся узлы для былей.

**Сводит обычай с человеком.** У значимых личностей заводится
культурный облик: где родился, где вырос, к кому себя причисляет и как
относится к обычаям своего народа — из пятнадцати видов отношения, а не
по одной шкале «традиционности». Кто-то соблюдает искренне, кто-то на
людях, кто-то хранит запрещённое, кто-то ломает при свидетелях — и
поступок меняет сам обычай.

Чего система нарочно **не** делает: не заводит обычай каждому народу на
каждый случай жизни (их у народа единицы, а не десятки), не объясняет
всякую традицию древней катастрофой, не превращает каждый обычай в
сюжетную зацепку и не трогает праздники — день в календаре живёт своей
системой (`systems/holidays.py`), а тут речь о том, как поступают в
случае.
"""

from __future__ import annotations

from .. import customs as cat
from .. import narrative_customs as texts
from .. import races as races_mod
from ..models import ACTIVE

# Сколько лет назад система смотрит, когда ищет повод для нового обычая.
LOOK_BACK = 60

# Обычай заводится примерно раз в два такта на весь мир: за десять тысяч
# лет это две-три сотни порядков, из которых до конца доживают десятки.
BIRTH_CHANCE = 0.42
# Сколько обычаев держится в мире разом. Больше — и раздел перестаёт
# читаться, а у народа становится по два десятка порядков на случай.
WORLD_CAP = 150
# Сколько своих обычаев бывает у одного народа: малолюдному хватает
# трёх, большому и старому — шести.
FOLK_SOFT = 3
FOLK_HARD = 6

# Все четыре числа ниже — на такт, и каждое делится на то, сколько с
# обычаем уже случалось: первый поворот вероятен, четвёртый — редкость.
# Без этого на длинной истории всякий обычай успевал разойтись ко всем
# соседям, обрасти изводами, трижды побывать под запретом и забыть
# причину — то есть все обычаи мира выходили одинаково бурными.
# Числа тут малы нарочно: обычай живёт сотни тактов, и даже сотая доля
# за такт означает «случится почти наверняка». При одной сотой к концу
# истории все обычаи мира оказывались разошедшимися по соседям и
# обросшими изводами — то есть одинаковыми.
SPREAD_CHANCE = 0.0016     # что за такт обычай шагнул к соседям
SPREAD_CAP = 3             # больше чем к трём народам обычай не уходит
TURN_CHANCE = 0.0035       # что с ним случился поворот судьбы
FORGET_FROM = 300          # с какого возраста причина может забыться
FORGET_CHANCE = 0.0045
VARIANT_CHANCE = 0.0013    # что где-то завёлся извод
CLASH_CHANCE = 0.070       # что два порядка столкнулись в одном городе

# Личности: облик заводится не всякому, иначе карточки распухают, а
# смысла в них не прибавляется.
PROFILE_CAP = 900
PROFILE_CHANCE = 0.55
DEED_CHANCE = 0.150        # что человек что-то с обычаем сделал
ATTITUDES_MAX = 3

SOULS_FLOOR = 3000         # народ мельче этого обычаев не заводит


# ---------------------------------------------------------------------------
# Земля под народом
# ---------------------------------------------------------------------------

TERRAIN_ROOTS = {
    races_mod.MOUNTAIN: ("stone",),
    races_mod.UNDERGROUND: ("under", "stone"),
    races_mod.HILLS: ("stone",),
    races_mod.COAST: ("sea",),
    races_mod.ISLANDS: ("sea", "few"),
    races_mod.FOREST: ("wood",),
    races_mod.JUNGLE: ("wood",),
    races_mod.SWAMP: ("wood",),
    races_mod.TUNDRA: ("cold", "few"),
    races_mod.DESERT: ("dry",),
    races_mod.STEPPE: ("open",),
    races_mod.PLAIN: ("open",),
}

# Что в событии летописи говорит о том, какой случай жизни оно задело.
# Ищется по куску ключа события: ключей в движке сотни, и перечислять их
# по одному значило бы заводить второй справочник событий.
EVENT_HINTS = (
    ("calamity", cat.DEATH, "woe"),
    ("disaster", cat.DEATH, "woe"),
    ("plague", cat.DEATH, "woe"),
    ("famine", cat.KIN, "woe"),
    ("dark", cat.DEATH, "woe"),
    ("scar", cat.HOME, "woe"),
    ("war_end", cat.TRUCE, "war"),
    ("war_start", cat.TRUCE, "war"),
    ("battle", cat.TRUCE, "war"),
    ("siege", cat.TRUCE, "war"),
    ("invasion", cat.TRUCE, "war"),
    ("raid", cat.TRUCE, "war"),
    ("feud", cat.HONOUR, ""),
    ("oath", cat.HONOUR, ""),
    ("migration", cat.ROAD, ""),
    ("assimilation", cat.ROAD, ""),
    ("exodus", cat.ROAD, "woe"),
    ("guild", cat.CRAFT, "craft"),
    ("craft", cat.CRAFT, "craft"),
    ("artifact", cat.CRAFT, "craft"),
    ("discovery", cat.CRAFT, "craft"),
    ("faith", cat.DEATH, "faith"),
    ("heresy", cat.HONOUR, "faith"),
    ("temple", cat.HOME, "faith"),
    ("deity", cat.BIRTH, "faith"),
    ("polity", cat.RULE, "state"),
    ("coup", cat.RULE, "state"),
    ("succession", cat.RULE, "state"),
    ("law", cat.RULE, "state"),
    ("city", cat.ROAD, ""),
    ("settlement", cat.ROAD, ""),
    ("tribe", cat.KIN, ""),
    ("monster", cat.HOME, "beast"),
    ("dominion", cat.HOME, "yoke"),
)

# Отчего обычай заводится, когда громкого повода не было: просто так тут
# живут. Условие -> причина словами.
LIFE_WHYS = {
    "under": "под землёй всякая оплошность стоит жизни, и порядок тут дороже удобства",
    "stone": "камня кругом больше, чем дерева, и всё долговечное делают из него",
    "sea": "море забирает людей без счёта, и провожают тут основательнее, чем встречают",
    "wood": "лес кормит и лес же прячет, а заблудившегося ищут всем селом",
    "cold": "зима тут длиннее лета, и зимовать в одиночку нельзя",
    "dry": "вода дороже слова, и всякий разговор начинается с неё",
    "open": "кочуют тут чаще, чем сидят на месте, и дом носят с собой",
    "craft": "ремесло кормит целые города, и умение тут дороже имущества",
    "trade": "через эти земли идут чужие, и с чужими надо как-то уживаться",
    "letters": "тут рано научились писать, и записанному верят больше памяти",
    "faith": "храм в этой земле сильнее державы",
    "state": "держава тут давняя, и всякий порядок рано или поздно становится законом",
    "war": "войны здесь не редкость, и возвращаются не все",
    "woe": "на памяти этого народа было такое, чего он не хочет повторить",
    "long": "век тут долог, и застать можно и прадеда, и правнука",
    "short": "век короток, и всё важное успевают сделать рано",
    "many": "людей тут много, и без заведённого порядка они не разойдутся",
    "few": "людей мало, и каждый на счету",
    "yoke": "землёй правят чужие, и своё приходится держать негромко",
    "magic": "волшебство тут под рукой, и от него больше хлопот, чем пользы",
    "beast": "по соседству живёт то, с чем не воюют, а уживаются",
}


def _lands(world) -> dict:
    """Какие земли под каким народом — одним проходом на весь такт."""
    rows = {}
    for settlement_id in world.active_settlements:
        item = world.settlements[settlement_id]
        if item.folk_id:
            rows.setdefault(item.folk_id, set()).add(item.region_id)
    for tribe_id in world.active_tribes:
        item = world.tribes[tribe_id]
        if item.folk_id:
            rows.setdefault(item.folk_id, set()).add(item.region_id)
    return rows


def _folk_towns(world, folk_id: str) -> list:
    return [world.settlements[key] for key in world.active_settlements
            if world.settlements[key].folk_id == folk_id]


def _roots(world, folk, lands, year: int) -> tuple:
    """Условия, в которых живёт народ: из них и растут его порядки."""
    have = set()
    for region_id in sorted(lands.get(folk.id, ())):
        region = world.regions.get(region_id)
        if region is None:
            continue
        have.update(TERRAIN_ROOTS.get(region.terrain, ()))
        if abs(getattr(region, "magic", 0.0) or 0.0) > 0.35:
            have.add("magic")
    race = races_mod.RACES_BY_ID.get(folk.race_id)
    if race is not None:
        if race.lifespan[1] >= 400:
            have.add("long")
        elif race.lifespan[1] <= 80:
            have.add("short")
    if folk.population >= 900000:
        have.add("many")
    if folk.population <= 60000:
        have.add("few")
    tongue = world.tongues.get(folk.tongue_id)
    if tongue is not None and getattr(tongue, "script", ""):
        have.add("letters")

    towns = _folk_towns(world, folk.id)
    own_polities = set()
    for town in towns:
        polity = world.polities.get(town.polity_id)
        if polity is None:
            continue
        capital = world.settlements.get(polity.capital_id)
        if capital is not None and capital.folk_id == folk.id:
            own_polities.add(polity.id)
            have.add("state")
        else:
            have.add("yoke")
        if polity.known:
            have.add("craft")
        if polity.routes:
            have.add("trade")
        faith = world.faiths.get(polity.faith_id)
        if faith is not None and faith.followers > folk.population * 0.3:
            have.add("faith")
    for town in towns:
        polity = world.polities.get(town.polity_id)
        if polity is not None and world.guilds_of(polity):
            have.add("craft")
            break
    for polity_id in sorted(own_polities):
        polity = world.polities[polity_id]
        for war_id in polity.war_ids:
            war = world.wars.get(war_id)
            if war is not None and war.start.year >= year - 200:
                have.add("war")
                break
    mine = lands.get(folk.id, set())
    for calamity in world.calamities.values():
        if calamity.start.year < year - 400 or calamity.start.year > year:
            continue
        if mine.intersection(calamity.region_ids or ()):
            have.add("woe")
            break
    return tuple(sorted(have))


def _recent(world, folk, lands, year: int) -> list:
    """Что случилось с народом за последние полвека — по летописи."""
    mine = lands.get(folk.id, set())
    rows = []
    for event in reversed(world.events):
        if event.date.year < year - LOOK_BACK:
            break
        if event.date.year > year or event.importance < 3:
            continue
        if event.race_id and event.race_id != folk.race_id:
            continue
        if event.region_id and mine and event.region_id not in mine:
            continue
        if not event.race_id and not event.region_id:
            continue
        rows.append(event)
        if len(rows) >= 12:
            break
    return rows


def _hint(event) -> tuple:
    """Какой случай жизни задело событие и какое условие оно подтверждает."""
    kind = (event.kind or "").lower()
    for part, case, root in EVENT_HINTS:
        if part in kind:
            return case, root
    return "", ""


# ---------------------------------------------------------------------------
# Такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.folks:
        return
    rng = ctx.rng("customs", year)
    scale = period / 10.0
    lands = _lands(world)

    if rng.chance(BIRTH_CHANCE * scale):
        _born(ctx, rng, year, lands)
    for custom in sorted(world.customs.values(), key=lambda item: item.id):
        if custom.ended is not None:
            continue
        _live(ctx, rng, custom, year, scale, lands)
    _people(ctx, rng, year, scale, lands)
    if rng.chance(CLASH_CHANCE * scale):
        _clash(ctx, rng, year, lands)


# ---------------------------------------------------------------------------
# Обычай заводится
# ---------------------------------------------------------------------------

def _folk_cap(folk) -> int:
    """Сколько своих порядков бывает у этого народа."""
    cap = FOLK_SOFT
    if folk.population >= 300000:
        cap += 1
    if folk.population >= 1500000:
        cap += 1
    if folk.settlements >= 4:
        cap += 1
    return min(FOLK_HARD, cap)


def _pick_folk(world, rng, lands):
    """Кому заводить обычай: тому, у кого есть люди и мало порядков."""
    pairs = []
    for folk in sorted(world.folks.values(), key=lambda item: item.id):
        if folk.status != ACTIVE or folk.population < SOULS_FLOOR:
            continue
        if not lands.get(folk.id):
            continue
        mine = [item for item in world.customs.values()
                if item.folk_id == folk.id and item.ended is None]
        room = _folk_cap(folk) - len(mine)
        if room <= 0:
            continue
        # Вес: простор под новый порядок плюс немного за людность. Народ
        # в три души своих обычаев не заводит — ему не для кого.
        weight = room + min(2.0, folk.population / 800000.0)
        pairs.append((folk.id, weight))
    if not pairs:
        return None
    return world.folks[rng.weighted(pairs)]


# Какие случаи жизни встают острее при таких условиях. Вес — не приговор:
# обычай про гостя заводится и у народа без торговых путей, просто реже.
CASE_WEIGHTS = {
    "war": ((cat.TRUCE, 2.4), (cat.HONOUR, 1.6), (cat.DEATH, 1.4)),
    "craft": ((cat.CRAFT, 2.6), (cat.GROWN, 1.4)),
    "long": ((cat.GROWN, 1.8), (cat.RULE, 1.6), (cat.KIN, 1.3)),
    "short": ((cat.BIRTH, 1.8), (cat.DEATH, 1.5)),
    "woe": ((cat.DEATH, 2.0), (cat.HOME, 1.5), (cat.ROAD, 1.2)),
    "trade": ((cat.GUEST, 2.2), (cat.ROAD, 1.6), (cat.HONOUR, 1.2)),
    "few": ((cat.GUEST, 1.6), (cat.KIN, 1.6), (cat.HOME, 1.2)),
    "many": ((cat.RULE, 1.6), (cat.HONOUR, 1.5), (cat.KIN, 1.2)),
    "state": ((cat.RULE, 2.0), (cat.HONOUR, 1.3)),
    "faith": ((cat.DEATH, 1.8), (cat.BIRTH, 1.6)),
    "yoke": ((cat.ROAD, 1.8), (cat.HONOUR, 1.5)),
    "sea": ((cat.DEATH, 1.4), (cat.ROAD, 1.4)),
    "under": ((cat.CRAFT, 1.5), (cat.DEATH, 1.3)),
    "cold": ((cat.GUEST, 1.5), (cat.HOME, 1.2)),
    "open": ((cat.ROAD, 1.8), (cat.GUEST, 1.3)),
    "letters": ((cat.HONOUR, 1.3), (cat.RULE, 1.2)),
    "magic": ((cat.BIRTH, 1.3), (cat.HOME, 1.3)),
    "beast": ((cat.HOME, 1.4), (cat.ROAD, 1.3), (cat.TRUCE, 1.2)),
}


def _case_for(rng, roots) -> str:
    """Какой случай жизни требует порядка у народа с такими условиями."""
    weights = {}
    for case in cat.CASES:
        # «Быт» годится всегда и потому забивает прочее: ему вес поменьше.
        weights[case.key] = 0.6 if case.key == cat.HOME else 1.0
    for root in roots:
        for case_key, add in CASE_WEIGHTS.get(root, ()):
            weights[case_key] = weights.get(case_key, 1.0) + add
    return rng.weighted(sorted(weights.items()))


def _name_for(world, rng, folk, form, need: str = "") -> str:
    """Имя обычая: головное слово формы и хвост, какого ещё не было."""
    head, tails = cat.name_parts(form, need)
    taken = {item.name for item in world.customs.values()}
    rows = [tail for tail in tails if "%s %s" % (head, tail) not in taken]
    if not rows:
        rows = list(tails)
    return "%s %s" % (head, rng.choice(rows))


def _born(ctx, rng, year: int, lands) -> None:
    world = ctx.world
    alive = len([item for item in world.customs.values()
                 if item.ended is None])
    if alive >= WORLD_CAP:
        return
    folk = _pick_folk(world, rng, lands)
    if folk is None:
        return
    roots = _roots(world, folk, lands, year)

    # Повод. Если за полвека с народом случилось что-то громкое, обычай
    # вырастает из этого; если нет — из того, как он живёт всегда.
    event = None
    case = ""
    for row in _recent(world, folk, lands, year):
        hint_case, hint_root = _hint(row)
        if not hint_case:
            continue
        if rng.chance(0.55):
            event, case = row, hint_case
            if hint_root:
                roots = tuple(sorted(set(roots) | {hint_root}))
            break
    if not case:
        case = _case_for(rng, roots)
    # Трёх порядков на один случай жизни у народа не бывает: это уже не
    # обычаи, а перечень обрядов.
    same = len([item for item in world.customs.values()
                if item.folk_id == folk.id and item.case == case
                and item.ended is None])
    if same >= 2:
        return

    need = rng.choice(cat.NEEDS_BY_CASE.get(case, ("ours",)))
    pairs = []
    for form in cat.forms_for(case, need):
        weight = cat.form_fit(form, roots)
        if weight > 0:
            pairs.append((form.key, weight))
    if not pairs:
        for form in cat.forms_for(case):
            weight = cat.form_fit(form, roots)
            if weight > 0:
                pairs.append((form.key, weight))
    if not pairs:
        return
    form = cat.FORMS_BY_KEY[rng.weighted(pairs)]

    # Та же форма у того же народа дважды — это не два обычая.
    for item in world.customs.values():
        if item.folk_id == folk.id and item.form == form.key \
                and item.ended is None:
            return

    date = ctx.date_in(rng, year)
    # Причина берётся из того, что к обычаю относится: сперва из условия,
    # которого эта форма и требует, а если такого у народа нет — из самой
    # задачи. Брать первое попавшееся условие нельзя: «Камень имён» с
    # пояснением «вода дороже слова» читается как сбой.
    why_root = ""
    for key in form.wants:
        if key in roots and key in LIFE_WHYS:
            why_root = LIFE_WHYS[key]
            break
    if not why_root:
        why_root = cat.NEED_WHYS.get(need, "так сложилось")
    why = ("так вышло после того, что в летописи записано как «%s»"
           % event.title.rstrip(".")) if event else why_root

    custom = world.add_custom(
        name=_name_for(world, rng, folk, form, need), case=case, need=need,
        form=form.key, folk_id=folk.id, race_id=folk.race_id, born=date,
        doing=form.doing, gear=form.gear,
        bind=rng.weighted([(cat.USUAL, 3.0), (cat.EXPECTED, 2.0),
                           (cat.FREE, 1.5), (cat.MUST, 0.7)]),
        reach=rng.weighted([(cat.REACH_TOWN, 2.0), (cat.REACH_LAND, 3.0),
                            (cat.REACH_FOLK, 1.2)]),
        state=cat.LIVE, why=why, why_event=event.id if event else "",
        said=rng.choice(cat.SAID_WHYS), folk_why=rng.choice(cat.FOLK_WHYS),
        husk=form.husk, roots=list(roots),
        region_ids=sorted(lands.get(folk.id, ()))[:4])
    if form.key == "ban" or need == "fear":
        custom.taboo = dict(cat.TABOO_ROOTS)[
            rng.weighted([(key, 2.0 if key in ("woe", "use", "faith") else 1.0)
                          for key, _about in cat.TABOO_ROOTS])]

    title, text = texts.born(rng, custom, folk.name,
                             event.title if event else "", why_root)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="custom_born",
        title=title, text=text, importance=2,
        subjects=[custom.id, folk.id], race_id=folk.race_id,
        region_id=custom.region_ids[0] if custom.region_ids else "",
        causes=[event.id] if event is not None else None)


# ---------------------------------------------------------------------------
# Обычай живёт
# ---------------------------------------------------------------------------

def _live(ctx, rng, custom, year: int, scale: float, lands) -> None:
    world = ctx.world
    folk = world.folks.get(custom.folk_id)

    # Народа не стало — порядок уходит с ним, если его не перенял никто.
    # А если перенял, то наследник становится хозяином обычая целиком: и
    # народом, и расой, и из списка перенявших его надо убрать, иначе
    # выходит, что он перенял порядок сам у себя.
    if folk is not None and folk.status != ACTIVE and custom.state != cat.LOST:
        heir = None
        for key in custom.folk_ids:
            other = world.folks.get(key)
            if other is None or other.status != ACTIVE:
                continue
            # Если такой порядок у наследника уже есть, второго не
            # заводим: он сливается с тем, что они делали и так.
            if any(item.folk_id == other.id and item.form == custom.form
                   and item.ended is None and item.id != custom.id
                   for item in world.customs.values()):
                continue
            heir = other
            break
        if heir is not None:
            custom.folk_id = heir.id
            custom.race_id = heir.race_id
            custom.folk_ids = [key for key in custom.folk_ids
                               if key != heir.id]
            custom.notes.append(
                "%d: народа, у которого он завёлся, не стало — порядок "
                "остался у народа по имени %s" % (year, heir.name))
        elif custom.folk_ids:
            _end(ctx, rng, custom, year,
                 "народа, у которого он завёлся, не стало, а у перенявших "
                 "он слился с их собственным порядком")
            return
        else:
            _end(ctx, rng, custom, year, "народа, у которого он был, не стало")
            return

    if custom.state in (cat.LOST,):
        # Забытое иногда возвращают, но чаще оно так и лежит.
        if rng.chance(0.004 * scale):
            _turn(ctx, rng, custom, "revive", year)
        elif year - custom.born.year > 600 and rng.chance(0.02 * scale):
            _end(ctx, rng, custom, year, "о нём не помнит никто")
        return

    # Чем больше с обычаем уже случалось, тем реже с ним случается
    # дальше: бурная судьба — это особенность, а не общее правило.
    if len(custom.folk_ids) < SPREAD_CAP and rng.chance(
            SPREAD_CHANCE * scale / (1.0 + len(custom.spread))):
        _spread(ctx, rng, custom, year, lands)
    if rng.chance(TURN_CHANCE * scale / (1.0 + len(custom.marks))):
        _maybe_turn(ctx, rng, custom, year)
    if rng.chance(VARIANT_CHANCE * scale / (1.0 + len(custom.variants))):
        _variant(ctx, rng, custom, year, lands)
    age = year - custom.born.year
    if age >= FORGET_FROM and cat.is_known(custom.why) \
            and rng.chance(FORGET_CHANCE * scale * _forget_help(custom)):
        _forget(ctx, rng, custom, year)


def _forget_help(custom) -> float:
    """Насколько легко этому обычаю потерять свою причину.

    Записанное держится дольше изустного, а у того, за кем смотрит храм
    или держава, причину переписывают, а не теряют. Зато у обычая,
    ушедшего в тайну или к чужим народам, помнить её скоро станет некому.
    """
    help_it = 1.0
    if "letters" in (custom.roots or ()):
        help_it *= 0.5
    if custom.holder:
        help_it *= 0.7
    if custom.state in (cat.SECRET, cat.BANNED):
        help_it *= 1.8
    if len(custom.folk_ids) > 1:
        help_it *= 1.4
    return help_it


def _neighbours(world, folk_id: str, lands) -> list:
    """Народы, с которыми этот живёт бок о бок."""
    mine = lands.get(folk_id, set())
    rows = []
    for other_id in sorted(lands):
        if other_id == folk_id:
            continue
        other = world.folks.get(other_id)
        if other is None or other.status != ACTIVE:
            continue
        theirs = lands[other_id]
        if mine.intersection(theirs):
            rows.append((other_id, 3.0))
            continue
        for region_id in sorted(mine):
            region = world.regions.get(region_id)
            if region is not None and set(region.neighbors or ()) & theirs:
                rows.append((other_id, 1.0))
                break
    return rows


def _spread(ctx, rng, custom, year: int, lands) -> None:
    world = ctx.world
    pairs = [(key, weight) for key, weight in _neighbours(world,
                                                          custom.folk_id, lands)
             if key not in custom.folk_ids]
    if not pairs:
        return
    other = world.folks.get(rng.weighted(pairs))
    if other is None:
        return
    way = rng.weighted([("trade", 2.0), ("marry", 2.0), ("move", 1.5),
                        ("craft", 1.2), ("faith", 1.0), ("court", 0.8),
                        ("sword", 0.8), ("name", 0.5)])
    custom.folk_ids.append(other.id)
    custom.spread.append({"год": year, "народ": other.id,
                          "как": cat.SPREAD_NAMES[way]})
    if cat.reach_index(custom.reach) < cat.reach_index(cat.REACH_WIDE):
        custom.reach = cat.REACH_WIDE if len(custom.folk_ids) > 1 \
            else cat.REACH_FOLK
    title, text = texts.spread(rng, custom, other.name, cat.SPREAD_NAMES[way])
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="custom_spread", title=title, text=text, importance=2,
        subjects=[custom.id, other.id], race_id=other.race_id)
    # Перенятое редко переносят слово в слово.
    if rng.chance(0.3):
        _variant(ctx, rng, custom, year, lands, why_key="alien",
                 where="у народа по имени %s" % other.name)


def _holder_for(world, custom, rng):
    """Кто может закрепить, запретить или вернуть этот обычай."""
    rows = []
    towns = _folk_towns(world, custom.folk_id)
    for town in towns:
        polity = world.polities.get(town.polity_id)
        if polity is not None:
            rows.append((cat.HOLDER_STATE, polity.id, polity.full_name))
            break
    for town in towns:
        faith = world.faiths.get(town.faith_id)
        if faith is not None:
            rows.append((cat.HOLDER_TEMPLE, faith.id,
                         "храм веры «%s»" % faith.name))
            break
    for town in towns:
        polity = world.polities.get(town.polity_id)
        guilds = world.guilds_of(polity) if polity is not None else []
        if guilds:
            rows.append((cat.HOLDER_GUILD, guilds[0].id, guilds[0].name))
            break
    if towns:
        rows.append((cat.HOLDER_TOWN, towns[0].id, towns[0].full_name))
    folk = world.folks.get(custom.folk_id)
    if folk is not None:
        rows.append((cat.HOLDER_FOLK, folk.id, "сам народ"))
    if not rows:
        return None
    return rows[rng.randint(0, len(rows) - 1)]


def _maybe_turn(ctx, rng, custom, year: int) -> None:
    pairs = []
    for turn in cat.TURNS:
        if custom.state not in turn.from_states:
            continue
        if turn.key == "hold" and custom.state == cat.OFFICIAL:
            continue
        weight = 1.0
        if turn.key == "thin" and year - custom.born.year < 200:
            weight = 0.3
        if turn.key == "fade" and custom.bind in (cat.MUST, cat.EXPECTED):
            weight = 0.4
        if turn.key == "forbid":
            # Запрещают редко: у власти обычно нет ни повода, ни нужды.
            weight = 0.35 if custom.state != cat.OFFICIAL else 0.15
        if turn.key == "revive":
            # Возвращают забытое редко, а запрещённое — чаще: пока жив
            # хоть кто-то, кто его помнит, запрет сам по себе довод.
            weight = 1.2 if custom.state == cat.BANNED else 0.5
        pairs.append((turn.key, weight))
    if not pairs:
        return
    _turn(ctx, rng, custom, rng.weighted(pairs), year)


def _turn(ctx, rng, custom, key: str, year: int) -> None:
    world = ctx.world
    turn = cat.TURNS_BY_KEY.get(key)
    if turn is None or custom.state not in turn.from_states:
        return
    holder_name = ""
    if turn.needs_holder:
        holder = _holder_for(world, custom, rng)
        if holder is None:
            return
        kind, holder_id, holder_name = holder
        if key in ("hold", "forbid"):
            custom.holder = kind
            custom.holder_id = holder_id
    why = what = ""
    if key == "forbid":
        why = rng.choice(cat.BAN_WHYS)
        custom.bind = cat.FADING
    elif key == "revive":
        why = rng.choice(cat.BACK_WHYS)
        custom.bind = cat.BACK
    elif key == "reform":
        what = rng.choice(cat.VARIANT_MARKS)
    elif key == "hold":
        custom.bind = cat.MUST
    elif key == "thin":
        custom.bind = cat.USUAL if custom.bind == cat.MUST else custom.bind
    elif key == "quarrel":
        custom.bind = cat.ARGUED
    elif key == "fade":
        custom.bind = cat.FADING

    custom.state = turn.into or custom.state
    custom.marks.append({"год": year, "что": turn.name,
                         "отчего": why or what or turn.about,
                         "кто": holder_name})
    title, text = texts.turn(rng, custom, key, holder_name, why, what)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="custom_%s" % key, title=title, text=text,
        importance=3 if key in ("forbid", "revive", "hold") else 2,
        subjects=[custom.id, custom.folk_id], race_id=custom.race_id)
    if key == "fade" and rng.chance(0.3):
        _end(ctx, rng, custom, year, "последние, кто его делал, перестали")


def _forget(ctx, rng, custom, year: int) -> None:
    world = ctx.world
    how = rng.choice(cat.FORGET_WHYS)
    custom.why = cat.UNKNOWN_WHY
    custom.forgot_year = year
    custom.notes.append("%d: причина забыта — %s" % (year, how))
    if custom.husk:
        custom.doing = custom.husk
    title, text = texts.forgot(rng, custom, how)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="custom_forgot", title=title, text=text, importance=2,
        subjects=[custom.id, custom.folk_id], race_id=custom.race_id)


def _variant(ctx, rng, custom, year: int, lands, why_key: str = "",
             where: str = "") -> None:
    world = ctx.world
    if len(custom.variants) >= 4:
        return
    if not why_key:
        pairs = [("land", 2.0), ("town", 1.5), ("rank", 1.2), ("house", 1.2),
                 ("guild", 1.0), ("temple", 1.0)]
        if custom.state in (cat.BANNED, cat.SECRET):
            pairs.append(("ban", 2.5))
        why_key = rng.weighted(pairs)
    if not where:
        where = _variant_where(world, rng, custom, why_key, lands)
    if not where:
        return
    mark = rng.choice(cat.VARIANT_MARKS)
    if any(row.get("где") == where for row in custom.variants):
        return
    custom.variants.append({"отчего": cat.VARIANT_BY_KEY[why_key].name,
                            "где": where, "в чём": mark, "год": year})
    title, text = texts.variant(rng, custom, where, mark)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="custom_variant", title=title, text=text, importance=1,
        subjects=[custom.id], race_id=custom.race_id)


def _variant_where(world, rng, custom, why_key: str, lands) -> str:
    towns = _folk_towns(world, custom.folk_id)
    if why_key == "town" and towns:
        town = towns[rng.randint(0, len(towns) - 1)]
        return "в городе по имени %s" % town.name
    if why_key == "land":
        rows = sorted(lands.get(custom.folk_id, ()))
        if rows:
            region = world.regions.get(rows[rng.randint(0, len(rows) - 1)])
            if region is not None:
                return "в земле по имени %s" % region.name
    if why_key == "temple":
        for town in towns:
            faith = world.faiths.get(town.faith_id)
            if faith is not None:
                return "у держащих веру «%s»" % faith.name
    if why_key == "guild":
        for town in towns:
            polity = world.polities.get(town.polity_id)
            guilds = world.guilds_of(polity) if polity is not None else []
            if guilds:
                return "в цеху по имени %s" % guilds[0].name
    if why_key == "house":
        for town in towns:
            polity = world.polities.get(town.polity_id)
            if polity is None:
                continue
            for house_id in polity.house_ids:
                house = world.houses.get(house_id)
                if house is not None:
                    return "в роду по имени %s" % house.name
    if why_key == "rank":
        return "у знати"
    if why_key == "ban":
        return "там, где его запретили"
    return ""


def _end(ctx, rng, custom, year: int, reason: str) -> None:
    custom.ended = ctx.date_in(rng, year)
    custom.end_reason = reason
    custom.state = cat.LOST
    custom.bind = cat.FADING


# ---------------------------------------------------------------------------
# Человек и обычай
# ---------------------------------------------------------------------------

def _worth_profile(world, figure, year: int) -> bool:
    """Кому заводить культурный облик.

    Не всякому: у рядового жителя довольно народа и места рождения.
    Облик нужен тем, чьи решения видны в летописи, — иначе карточки
    распухают, а читать в них нечего.

    И заводится он при жизни. Прежде облик доставался и давно умершим;
    потолок выбирался на первых веках, и к середине истории живых людей
    с обликом не оставалось вовсе — а значит, некому было ни нарушить
    обычай, ни переделать его.
    """
    if figure.death is not None and figure.death.year < year:
        return False
    if not figure.folk_id:
        return False
    if figure.titles or figure.noble:
        return True
    if len(figure.deeds) >= 3 or len(figure.roles) >= 2:
        return True
    return False


def _profile_cap(world) -> int:
    """Сколько культурных обликов держать в мире.

    Потолок считается от длины истории: на тысяче лет значимых имён
    немного, а на десяти тысячах их тысячи — и если брать первых
    попавшихся, облик достанется случайным людям первого века, а
    государям последних тысячелетий не достанется вовсе.
    """
    return min(PROFILE_CAP, 60 + int(world.total_years) // 12)


# Какие отношения к обычаю ведут к поступку: прочие живут тихо.
DOER_KINDS = ("refuse", "blind", "wrong", "secret", "reform", "new")


def _people(ctx, rng, year: int, scale: float, lands) -> None:
    world = ctx.world
    if len(world.culture_profiles) >= _profile_cap(world):
        rows = []
    else:
        rows = [figure for figure in world.figures.values()
                if world.profile_of(figure.id) is None
                and figure.birth is not None and figure.birth.year <= year
                and _worth_profile(world, figure, year)]
        rows.sort(key=lambda item: item.id)
    for figure in rows[:6]:
        if not rng.chance(PROFILE_CHANCE):
            continue
        _profile(ctx, rng, figure, year, lands)
    # Поступок. Делает его не всякий: нужен живой человек, у которого к
    # обычаю отношение из тех, что ведут к делу, — отказ, непонимание,
    # тайное хранение, переделка. Искренне соблюдающие историю не
    # двигают, и это правильно.
    doers = []
    for key in sorted(world.culture_profiles):
        profile = world.culture_profiles[key]
        figure = world.figures.get(profile.figure_id)
        if figure is None or figure.birth is None or figure.birth.year > year:
            continue
        if figure.death is not None and figure.death.year < year:
            continue
        if not any(row.get("вид") in DOER_KINDS for row in profile.attitudes):
            continue
        doers.append(profile)
    if not doers or not rng.chance(DEED_CHANCE * scale):
        return
    profile = doers[rng.randint(0, len(doers) - 1)]
    figure = world.figures.get(profile.figure_id)
    _deed(ctx, rng, profile, figure, year)


def _profile(ctx, rng, figure, year: int, lands) -> None:
    world = ctx.world
    born_folk = figure.folk_id
    raised = born_folk
    now = born_folk
    influences = []

    # Вырос не там, где родился: дом в чужой земле, чужая держава, плен.
    home = world.settlements.get(figure.home_id) or \
        world.tribes.get(figure.home_id)
    if home is not None and getattr(home, "folk_id", "") \
            and home.folk_id != born_folk:
        raised = now = home.folk_id
        other = world.folks.get(home.folk_id)
        if other is not None:
            influences.append({"что": "вырос среди народа по имени %s"
                                      % other.name,
                               "отчего": "там стоял дом его семьи",
                               "год": figure.birth.year})
    if figure.spouse_id:
        spouse = world.figures.get(figure.spouse_id)
        if spouse is not None and spouse.folk_id and spouse.folk_id != now:
            other = world.folks.get(spouse.folk_id)
            if other is not None:
                influences.append({"что": "держит и порядки народа по имени %s"
                                          % other.name,
                                   "отчего": "так заведено в доме супруга",
                                   "год": year})

    profile = world.add_culture_profile(
        figure_id=figure.id, born_folk=born_folk, raised_folk=raised,
        now_folk=now, influences=influences)

    rows = world.customs_of(now) or world.customs_of(born_folk)
    rows = [item for item in rows if item.state in cat.KEPT]
    if not rows:
        return
    count = min(ATTITUDES_MAX, 1 + (1 if rng.chance(0.45) else 0)
                + (1 if rng.chance(0.2) else 0))
    picked = []
    for _step in range(count):
        choices = [item for item in rows if item.id not in picked]
        if not choices:
            break
        custom = choices[rng.randint(0, len(choices) - 1)]
        picked.append(custom.id)
        kind = _attitude_for(rng, figure, custom, profile)
        profile.attitudes.append({"обычай": custom.id, "вид": kind,
                                  "отчего": _attitude_why(rng, figure, custom,
                                                          kind, profile)})
    _habits(rng, figure, profile)


def _attitude_for(rng, figure, custom, profile) -> str:
    """Как этот человек относится к этому обычаю.

    Вид берётся не из расы и не из сословия: смотрят на состояние самого
    обычая, на то, свой он человеку или чужой, и на нрав. Два человека
    одного города к одному обряду относятся по-разному — в этом вся суть.
    """
    fits = cat.ATTITUDE_FITS.get(custom.state)
    pairs = []
    for row in cat.ATTITUDES:
        if fits and row.key not in fits:
            continue
        weight = 1.0
        if row.key == "true":
            weight = 2.2
        if row.key == "habit":
            weight = 2.4
        if row.key in ("refuse", "new", "reform"):
            weight = 0.5 + (0.8 if figure.alignment < 0 else 0.0)
        if row.key == "blind":
            # По незнанию нарушает тот, кто вырос не здесь.
            weight = 1.4 if profile.born_folk != profile.now_folk else 0.15
        if row.key == "other":
            weight = 1.2 if custom.variants else 0.3
        if row.key == "secret":
            weight = 2.0 if custom.state in (cat.BANNED, cat.SECRET) else 0.0
        if row.key == "forced" and custom.bind != cat.MUST:
            weight = 0.3
        if row.key == "mask":
            weight = 1.3 if custom.bind in (cat.MUST, cat.EXPECTED) else 0.6
        if weight > 0:
            pairs.append((row.key, weight))
    if not pairs:
        return "habit"
    return rng.weighted(pairs)


ATTITUDE_WHYS = {
    "true": ("в этом он не сомневался никогда",
             "он видел, как это однажды спасло дело"),
    "habit": ("так делали в его доме, и он не задумывался",
              "он сам не сказал бы, зачем это нужно"),
    "kin": ("смысла в этом он не видит, но мать видела",
            "ради родни, которая этого ждёт"),
    "fear": ("не божества боится, а соседей",
             "однажды он видел, чем кончается небрежение"),
    "mask": ("при людях делает, дома — нет",
             "держит вид, а дома об этом не вспоминают"),
    "part": ("берёт из обычая то, что ему годится",
             "половину порядка он считает лишней"),
    "rethink": ("порядок держит, а смысл вкладывает свой",
                "делает то же, что отцы, и объясняет иначе"),
    "refuse": ("говорит вслух, что это пустая трата дней",
               "однажды отказался при свидетелях и не отступил"),
    "blind": ("вырос не здесь и узнал об этом поздно",
              "не знал, что так нельзя"),
    "wrong": ("уверен, что делает верно, и делает не то",
              "перепутал порядок и не дал себя поправить"),
    "other": ("держит тот извод, что в его краю",
              "у них дома это делают иначе"),
    "forced": ("делает, потому что иначе не дадут жить",
               "его заставляют, и он этого не скрывает"),
    "secret": ("делает тайком то, что велено забыть",
               "хранит запрещённое и учит этому сына"),
    "new": ("завёл рядом своё и приучил к нему других",
            "поставил своё взамен и не спрашивал старших"),
    "reform": ("хочет сохранить суть, сменив порядок",
               "говорит, что обычай надо спасать от самого себя"),
}


def _attitude_why(rng, figure, custom, kind: str, profile) -> str:
    rows = ATTITUDE_WHYS.get(kind)
    return rng.choice(rows) if rows else ""


def _habits(rng, figure, profile) -> None:
    """Одна-две привычки, выросшие из биографии, а не из воздуха."""
    marks = set()
    roles = " ".join(figure.roles or ()) + " " + " ".join(figure.titles or ())
    if "воин" in roles or "полковод" in roles or "вожд" in roles:
        marks.add("war")
    if "мастер" in roles or "ремесл" in roles or "основат" in roles:
        marks.add("craft")
    if "жре" in roles or "проро" in roles:
        marks.add("faith")
    if figure.titles or figure.noble:
        marks.update(("power", "duty"))
    if figure.death is not None:
        marks.add("duty")
    if profile.born_folk != profile.now_folk:
        marks.add("exile")
    if figure.alignment < 0:
        marks.add("pride")
    if figure.alignment > 1:
        marks.add("kin")
    marks.update(("fear", "loss"))

    pairs = [(seed.key, 2.0 if marks.intersection(seed.from_what) else 0.25)
             for seed in cat.HABIT_SEEDS]
    chosen = rng.weighted(pairs)
    seed = next(item for item in cat.HABIT_SEEDS if item.key == chosen)
    profile.habits.append({"что": seed.doing, "из чего": seed.from_what[0],
                           "говорят": seed.telling})
    if rng.chance(0.3):
        why_key, why_name = cat.RITE_WHYS[rng.randint(0,
                                                      len(cat.RITE_WHYS) - 1)]
        profile.rites.append({"что": rng.choice(cat.PERSONAL_RITES),
                              "отчего": why_name, "ключ": why_key})


def _deed(ctx, rng, profile, figure, year: int) -> None:
    """Человек делает с обычаем что-то, что заметят."""
    world = ctx.world
    doers = [row for row in profile.attitudes
             if row.get("вид") in ("refuse", "blind", "wrong", "secret",
                                   "reform", "new")]
    if not doers:
        return
    row = doers[rng.randint(0, len(doers) - 1)]
    custom = world.customs.get(row.get("обычай", ""))
    if custom is None or custom.ended is not None:
        return
    kind = row.get("вид")
    date = ctx.date_in(rng, year)
    if kind in ("refuse", "blind", "wrong", "secret"):
        if any(mark.get("обычай") == custom.id for mark in profile.broke):
            return
        profile.broke.append({"обычай": custom.id, "год": year, "как": kind})
        title, text = texts.broke(rng, figure.name, custom, kind)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="custom_broken", title=title, text=text, importance=3,
            actors=[figure.id], subjects=[custom.id, figure.id],
            race_id=figure.race_id)
        # Нарушение на виду расшатывает обычай, но не всякое.
        if custom.state == cat.LIVE and rng.chance(0.35):
            custom.state = cat.SHAKEN
            custom.marks.append({"год": year, "что": "спор",
                                 "отчего": "его нарушил %s" % figure.name,
                                 "кто": figure.name})
    else:
        if any(mark.get("обычай") == custom.id for mark in profile.made):
            return
        what = "Переделал" if kind == "reform" else "Завёл заново"
        profile.made.append({"обычай": custom.id, "год": year, "что": what})
        mark = rng.choice(cat.VARIANT_MARKS)
        custom.marks.append({"год": year, "что": "переделка",
                             "отчего": mark, "кто": figure.name})
        if kind == "reform":
            custom.doing = custom.doing
            custom.notes.append("%d: %s переделал порядок — %s"
                                % (year, figure.name, mark))
        title, text = texts.made(rng, figure.name, figure.plain_name, mark)
        world.add_event(
            date=date, era_index=world.era_index_at(year),
            kind="custom_made", title=title, text=text, importance=3,
            actors=[figure.id], subjects=[custom.id, figure.id],
            race_id=figure.race_id)


# ---------------------------------------------------------------------------
# Узлы для былей
# ---------------------------------------------------------------------------

# Сколько лет должно пройти, чтобы о порядке стало что рассказывать.
STORY_AGE = 80


def story_nodes(world, year: int) -> list:
    """Обычаи, из которых прямо сейчас может вырасти быль.

    Не всякий обычай годится в узел — и это условие, а не недоработка:
    большинство порядков просто держит мир правдоподобным. Годятся три
    случая: о порядке спорят, его держат втайне от власти и его делают,
    не помня зачем. В первых двух быль растёт из людей, в третьем — из
    дыры в памяти.
    """
    rows = []
    for custom in sorted(world.customs.values(), key=lambda item: item.id):
        if custom.ended is not None or custom.state == cat.LOST:
            continue
        folk = world.folks.get(custom.folk_id)
        where = custom.region_ids[0] if custom.region_ids else ""
        since = custom.forgot_year or custom.born.year
        if year - since < STORY_AGE:
            continue
        folk_name = folk.name if folk is not None else "этот народ"
        if custom.state == cat.SHAKEN or custom.bind == cat.ARGUED:
            rows.append(("спор о порядке",
                         "о том, нужен ли обычай «%s», спорят у народа по "
                         "имени %s" % (custom.name, folk_name),
                         custom, where, 1.2))
        elif custom.state in (cat.BANNED, cat.SECRET):
            rows.append(("спор о порядке",
                         "обычай «%s» запрещён, и его держат втайне"
                         % custom.name, custom, where, 1.1))
        elif not cat.is_known(custom.why):
            rows.append(("обряд без причины",
                         "обычай «%s» делают, не помня зачем: %s"
                         % (custom.name, custom.doing),
                         custom, where, 1.0))
    return rows


# ---------------------------------------------------------------------------
# Столкновение обычаев
# ---------------------------------------------------------------------------

def _clash(ctx, rng, year: int, lands) -> None:
    """Два народа в одном городе разошлись в простом."""
    world = ctx.world
    towns = []
    for settlement_id in world.active_settlements:
        town = world.settlements[settlement_id]
        polity = world.polities.get(town.polity_id)
        if polity is None or len(polity.peoples) < 2:
            continue
        towns.append(town)
    if not towns:
        return
    town = towns[rng.randint(0, len(towns) - 1)]
    polity = world.polities[town.polity_id]
    races = [race for race, souls in sorted(polity.peoples.items())
             if souls > 0]
    if len(races) < 2:
        return
    first = [item for item in world.customs.values()
             if item.race_id == races[0] and item.state in cat.KEPT]
    second = [item for item in world.customs.values()
              if item.race_id == races[1] and item.state in cat.KEPT]
    if not first or not second:
        return
    one = first[rng.randint(0, len(first) - 1)]
    two = second[rng.randint(0, len(second) - 1)]
    what = rng.choice(cat.CLASHES)
    end_key = rng.weighted([("quiet", 2.5), ("apart", 2.0), ("mixed", 1.5),
                            ("yield", 1.5), ("law", 1.2), ("feud", 0.8)])
    title, text = texts.clash(rng, town.name, what, end_key)
    world.add_event(
        date=ctx.date_in(rng, year), era_index=world.era_index_at(year),
        kind="custom_clash", title=title, text=text, importance=3,
        subjects=[one.id, two.id, town.id], region_id=town.region_id)
    note = "%d: в городе по имени %s — %s" % (year, town.name,
                                              cat.CLASH_END_NAMES[end_key])
    one.notes.append(note)
    two.notes.append(note)
    if end_key == "mixed":
        # Из спора вышел третий порядок: он живёт у обоих народов.
        for custom, other_race in ((one, races[1]), (two, races[0])):
            folk = next((item for item in world.folks.values()
                         if item.race_id == other_race
                         and item.status == ACTIVE), None)
            if folk is not None and folk.id not in custom.folk_ids:
                custom.folk_ids.append(folk.id)
                custom.spread.append({"год": year, "народ": folk.id,
                                      "как": "из спора вышел общий порядок"})
