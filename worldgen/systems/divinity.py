# -*- coding: utf-8 -*-
"""Боги живут тысячелетиями и ведут себя как действующие лица.

Пантеон в этом мире был справочником: имя, сферы, мировоззрение,
праздник. Здесь боги начинают **делать историю**, и делают её по своим
правилам, а не по броску кости.

Как это работает. У каждого бога есть принцип — одна мысль, ради которой
он есть, — и двенадцать мер, которыми он оценивает чужие дела. Народы
своими поступками двигают его покровительство: поставили храм, сберегли
рощу, не отреклись в гонение — он ближе; нарушили запрет, сожгли храм,
извели то, чем он ведает — дальше. Каждое движение записано с причиной и
годом, и потому через тысячу лет видно, **почему** богиня леса не любит
людей: не потому, что люди, а потому, что в 1204 году они свели рощу.

Второе, ради чего всё это: **бог и его культ — не одно и то же**. Жрецы
читают волю по-своему, толкование ужесточается или смягчается, забытый
запрет выпадает из свода, а к празднику прибавляется объяснение, которого
не было. Расхождение копится числом (`drift`), и когда оно велико, вера
начинает делать именем бога то, о чём он не просил. Отсюда растут ереси,
расколы и религиозные войны — и всё это уже есть в `systems/religion`.

Третье: **пророчества многозначны**. Они говорят не «в 1320 году придёт
король», а «когда луна станет красной, дитя без имени откроет ворота». У
каждого записана настоящая правда — и она всегда проще и мельче, чем
ждали, — и несколько чужих прочтений, из-за которых люди и ссорятся.
"""

from __future__ import annotations

from .. import divinity as cat
from .. import history
from .. import narrative_divine as texts
from .. import races as races_mod
from .. import sites as sites_mod
from ..models import Date

ACT_RATE = 0.16            # шанс, что бог за десятилетие что-то сделает
FAVOUR_RATE = 0.12         # и что покровительство кому-то сдвинется
DRIFT_RATE = 0.06          # и что культ уйдёт ещё на шаг от его воли
DRIFT_STEP = 0.18          # насколько далеко уводит один такой шаг
REFORM_RATE = 0.05         # и насколько часто находится тот, кто вернёт
PROPHECY_RATE = 0.05
SYMBOL_RATE = 0.02         # судьба знака решается редко и навсегда
FEAST_RATE = 0.02
CHOSEN_RATE = 0.06
MAX_BONDS = 5
MAX_MARKS = 40
LOUD_ENOUGH = 3            # с какой громкости дело попадает в летопись
SILENCE_DRIFT = 0.75       # при таком расхождении бог замолкает
WAKE_AFTER = 400           # и через сколько лет забытого могут разбудить


def prepare(ctx) -> None:
    """Мифический век: те, кто был прежде мира, и что от них осталось.

    Первородные — не боги в человеческом смысле: они были до мира и не
    творили его, мир вышел из их спора. Кончается спор Расколом, и они
    исчезают — но остаются в мире телами: кости одного лежат хребтом,
    кровь другого налилась морем, мысли третьего смертные зовут магией.

    Это не вступление к летописи, а первый слой её причин. Останки
    отмечены настоящими землями и настоящими местами, и через десять
    тысяч лет кто-то в них полезет — и это будет уже обычная быль.
    """
    world = ctx.world
    rng = ctx.rng("myth", "dawn")
    if not rng.chance(0.72):
        world.notes["первородные"] = {
            "были": False,
            "как было": "прежде мира не было ничего, и спорить было некому"}
        return

    race = rng.choice(sorted(races_mod.RACES, key=lambda item: item.id))
    firsts = list(rng.shuffled(list(cat.FIRSTS)))[:rng.randint(3, 5)]
    born = Date(1, 1, 1)
    made = []
    for first in firsts:
        sex = rng.weighted((("m", 3.0), ("f", 3.0), ("n", 2.0)))
        deity = world.add_deity(
            given_name=ctx.forge.deity(rng, race, sex),
            title=rng.choice(FIRST_TITLES[sex]), sex=sex, race_id="",
            domains=[first.domain], alignment=0,
            symbol="знак, которого больше не чертят",
            festival_name="", festival_month=1, festival_day=1,
            revealed=born, status="забыт", epithet=first.name,
            primordial=True, patron_kind="мироздание",
            patron_name="того, что было прежде мира")
        deity.notes.append("первородный: %s" % first.about)
        made.append((first, deity))

    strife = list(rng.shuffled(list(cat.FROM_STRIFE)))[:rng.randint(3, 5)]
    sundering, how = rng.choice(cat.SUNDERINGS)

    # Останки: настоящая земля, настоящее место, а не строчка в мифе.
    traces = []
    for first, deity in made:
        region = _trace_region(ctx, rng, first)
        row = {"кто": deity.id, "чем был": first.name,
               "что осталось": first.remains,
               "земля": region.id if region is not None else "",
               "место": ""}
        if region is not None and rng.chance(0.7):
            site = _trace_site(ctx, rng, first, deity, region, born)
            row["место"] = site.id
        traces.append(row)

    world.myths.append({
        "ключ": "первородные", "имя": sundering, "год": 1,
        cat.AS_IT_WAS: "прежде мира были %s; %s; из их спора вышли %s; "
                       "кончилось это тем, что %s"
                       % (", ".join(first.name for first, _ in made),
                          "; ".join(first.about for first, _ in made[:2]),
                          ", ".join(strife), how),
        cat.AS_TAUGHT: rng.choice(cat.MYTH_TEACH),
        cat.AS_TOLD: rng.choice(cat.MYTH_TELL),
        cat.AS_SUNG: rng.choice(cat.MYTH_SING),
        "следы": traces,
        "кто": [deity.id for _, deity in made],
    })
    world.notes["первородные"] = {
        "были": True, "раскол": sundering,
        "кто": [deity.full_name for _, deity in made],
    }

    date = born
    world.add_event(
        date=date, era_index=0, kind="mythic_age",
        title="Прежде мира: %s" % sundering,
        text="Прежде мира были те, кто спорил о том, каким ему быть: %s. "
             "Из их спора вышли %s. %s. Останки их лежат в самом мире."
             % (", ".join(first.name for first, _ in made),
                ", ".join(strife), texts.cap(how)),
        importance=5, subjects=[deity.id for _, deity in made])


FIRST_TITLES = {
    "m": ("Первый", "Тот, кто был прежде", "Старший"),
    "f": ("Первая", "Та, что была прежде", "Старшая"),
    "n": ("Первое", "То, что было прежде", "Старшее"),
}

# Какая земля годится под чьи останки: кости — в горы, кровь — к морю.
TRACE_TERRAIN = {
    "горы": ("горы", "холмы"),
    "побережье": ("побережье", "острова"),
    "равнина": ("равнина", "степь"),
}


def _trace_region(ctx, rng, first):
    """Земля, в которой лежит то, что осталось от первородного."""
    world = ctx.world
    rows = [region for region in world.regions.values()
            if not getattr(region, "drowned", False)]
    if not rows:
        return None
    wanted = TRACE_TERRAIN.get(first.terrain, ())
    fitting = [region for region in rows if region.terrain in wanted]
    pool = fitting or rows
    pool.sort(key=lambda item: item.id)
    return rng.choice(pool)


def _trace_site(ctx, rng, first, deity, region, date):
    """Место, где до этих останков можно дойти ногами."""
    world = ctx.world
    word = rng.choice(("Кости", "След", "Ложе", "Яма", "Провал", "Камни"))
    name = ctx.forge.unique(
        "site", lambda: "%s %s" % (word, deity.given_name), rng)
    site = world.add_site(
        kind=sites_mod.SEALED, name=name, region_id=region.id, created=date,
        guards=rng.choice(sites_mod.GUARDS[sites_mod.SEALED]),
        riches=sites_mod.riches_for(rng, sites_mod.SEALED, 1.4),
        hex_index=_hex_of(ctx, region.id, rng))
    site.depth = sites_mod.depth_for(sites_mod.SEALED, site.riches, True)
    site.story = "Тут лежит то, что осталось от первородного: %s." \
        % first.remains
    site.notes.append("останки первородного по имени %s" % deity.given_name)
    return site


def _hex_of(ctx, region_id: str, rng) -> int:
    """Гекс под место — если мир построен по карте."""
    region = ctx.world.regions.get(region_id)
    if region is None or not region.hexes:
        return -1
    return rng.choice(sorted(region.hexes))


def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.deities:
        return
    rng = ctx.rng("gods", year)

    # Новым богам — биографию. Бог без неё — это просто имя со сферами.
    for deity in sorted(world.deities.values(), key=lambda item: item.id):
        if world.godhead_of(deity.id) is not None:
            continue
        if deity.revealed is not None and deity.revealed.year > year:
            continue
        _born(ctx, rng, deity, year)

    temples = _temple_news(world, year, period)
    for head in sorted(world.godheads.values(), key=lambda item: item.id):
        deity = world.deities.get(head.deity_id)
        if deity is None:
            continue
        _live(ctx, rng, head, deity, year, period,
              temples.get(head.deity_id, 0))


# ---------------------------------------------------------------------------
# Явление бога
# ---------------------------------------------------------------------------

def _born(ctx, rng, deity, year: int):
    """Откуда он взялся, ради чего он есть и чем меряет чужие дела."""
    world = ctx.world
    origin = _pick_origin(ctx, rng, deity, year)
    head = world.add_godhead(
        deity_id=deity.id, origin=origin.key,
        born=deity.revealed or ctx.date_in(rng, year),
        principle=cat.principle_of(deity.domains, deity.alignment),
        values=cat.values_of(deity.domains, deity.alignment),
        symbols=cat.symbols_for(rng, deity.domains))

    # Запреты и дары — из сфер: бог леса не прощает того же, чего не
    # прощает бог моря.
    taboos = cat.taboos_of(deity.domains)
    head.taboos = list(rng.shuffled(taboos))[:3] if taboos else []
    gifts = cat.gifts_of(deity.domains)
    for gift in list(rng.shuffled(gifts))[:3]:
        head.gifts.append({"дар": gift, "кому": rng.choice(GIFT_TERMS)})

    # Покровительство: свой народ ближе всех, дальше — по нраву.
    _first_favour(ctx, rng, head, deity, year)
    _first_bonds(ctx, rng, head, deity, year)

    _mark(head, year, cat.BORN, texts.born_line(rng, origin, deity))
    if origin.leaves:
        head.notes.append(origin.leaves)
    return head


def _pick_origin(ctx, rng, deity, year: int):
    """Происхождение: творцу — своё, позднему богу — своё."""
    late = year > max(400, ctx.world.total_years // 12)
    pairs = []
    for origin in cat.ORIGINS:
        if origin.needs == cat.MAKER and not deity.maker:
            continue
        if origin.needs == cat.PRIMORDIAL and not deity.primordial:
            continue
        if origin.needs == cat.LATE and not late:
            continue
        weight = origin.weight
        if deity.maker and origin.key == "creator":
            weight *= 12.0
        if deity.primordial and origin.key == "firstborn":
            weight *= 10.0
        if origin.key in ("ascended", "of_faith") and deity.alignment >= 2:
            weight *= 1.4
        pairs.append((origin, weight))
    if not pairs:
        return cat.ORIGINS_BY_KEY["unknown"]
    pairs.sort(key=lambda pair: pair[0].key)
    return rng.weighted(pairs)


GIFT_TERMS = (
    "тому, кто соблюдает его запреты",
    "тому, кто принёс жертву в его праздник",
    "тому, кто просит не для себя",
    "тому, кто пришёл в его святое место",
    "тому, кто ни разу не отрёкся",
    "тому, кто отдал больше, чем мог",
)


def _first_favour(ctx, rng, head, deity, year: int) -> None:
    """Кому он благоволит на первых порах — и почему именно им."""
    world = ctx.world
    if deity.race_id:
        head.favour[deity.race_id] = {
            "сила": 0.65, "почему": "им он явился первым", "год": year}
    for race_id in _races_here(world):
        if race_id in head.favour:
            continue
        race = races_mod.RACES_BY_ID.get(race_id)
        if race is None:
            continue
        # Нрав народа против нрава бога: добрый бог сторонится злого
        # народа не из прихоти, а потому что они делают то, чего он не
        # терпит.
        gap = abs(deity.alignment - _race_light(race))
        if gap >= 4:
            head.favour[race_id] = {
                "сила": -0.35, "почему": "они живут не по его правде",
                "год": year}


def _race_light(race) -> int:
    """Насколько народ в среднем светел — по его же складу."""
    value = getattr(race, "alignment", None)
    if isinstance(value, (int, float)):
        return int(value)
    dark = getattr(race, "dark", False)
    return -2 if dark else 1


def _races_here(world) -> list:
    """Народы, у которых в мире есть живые поселения."""
    out = []
    for settlement_id in world.active_settlements:
        race_id = world.settlements[settlement_id].race_id
        if race_id and race_id not in out:
            out.append(race_id)
    return out


def _first_bonds(ctx, rng, head, deity, year: int) -> None:
    """С кем он сошёлся и с кем разошёлся среди других богов."""
    world = ctx.world
    others = [other for other in world.deities.values()
              if other.id != deity.id and other.status != "низвергнут"]
    others.sort(key=lambda item: item.id)
    if not others:
        return
    for other in list(rng.shuffled(others))[:3]:
        kind = cat.bond_between(deity.domains, other.domains,
                                deity.alignment, other.alignment)
        why = rng.choice(cat.BOND_REASONS[kind])
        head.bonds.append({"кто": other.id, "связь": kind, "почему": why,
                           "год": year})
        _mark(head, year, cat.BOND_MARK,
              texts.bond_line(rng, kind, texts.god_ref(other, "род"), why))


# ---------------------------------------------------------------------------
# Десять лет божественной жизни
# ---------------------------------------------------------------------------

def _live(ctx, rng, head, deity, year: int, period: int,
          temple_news: int) -> None:
    world = ctx.world
    faiths = [world.faiths[fid] for fid in _faiths_of(world, deity.id)]
    alive = any(faith.status not in ("забыта",) for faith in faiths)
    followers = sum(faith.followers for faith in faiths)

    # Храм построили или сожгли — это и есть поступок народа, за который
    # бог приближает или отдаляет.
    if temple_news:
        _favour_move(ctx, rng, head, deity, year, up=temple_news > 0,
                     forced="поставили ему храм" if temple_news > 0
                     else "сожгли его храм")

    scale = period / 10.0
    weight = 1.0 if followers > 500 else 0.45
    if not alive:
        weight = 0.12          # забытый бог почти не подаёт голоса

    if rng.chance(FAVOUR_RATE * scale * weight):
        _favour_move(ctx, rng, head, deity, year, up=rng.chance(0.45))

    if rng.chance(ACT_RATE * scale * weight) and head.awake:
        _do_deed(ctx, rng, head, deity, year, followers)

    if alive and rng.chance(DRIFT_RATE * scale):
        _cult_drift(ctx, rng, head, deity, year)
    elif alive and head.drift >= 0.45 and rng.chance(REFORM_RATE * scale):
        _reform(ctx, rng, head, deity, year)

    if alive and followers > 300 and rng.chance(PROPHECY_RATE * scale):
        _prophesy(ctx, rng, head, deity, year)

    if alive and followers > 200 and rng.chance(CHOSEN_RATE * scale):
        _choose_one(ctx, rng, head, deity, year)

    # Старые избранники доводят дело до конца или не доводят.
    _close_chosen(ctx, rng, head, deity, year)

    if head.symbols and rng.chance(SYMBOL_RATE * scale):
        _symbol_fate(ctx, rng, head, deity, year)
    if rng.chance(FEAST_RATE * scale):
        _feast_turn(ctx, rng, head, deity, year)

    # Молчание и уход: бог замолкает, когда его именем делают чужое.
    if head.awake and not head.silent_since and head.drift >= SILENCE_DRIFT \
            and rng.chance(0.25 * scale):
        head.silent_since = year
        _mark(head, year, cat.SILENCE,
              "Он перестал отвечать: его именем делают не его дело.")
        _tell(ctx, head, deity, year, "молчание", "молитвы остались без "
              "ответа, и жрецы объясняют это испытанием", loud=3)

    # Забытого бога может разбудить чьё-то слово.
    if not alive and head.awake and head.silent_since \
            and year - head.silent_since > WAKE_AFTER \
            and rng.chance(0.05 * scale):
        head.silent_since = 0
        _mark(head, year, cat.RETURN,
              "Кто-то назвал его имя вслух, и он отозвался.")
        _tell(ctx, head, deity, year, "пробуждение",
              "имя, которого не произносили веками, было сказано", loud=4)


def _faiths_of(world, deity_id: str) -> list:
    return [faith.id for faith in world.faiths.values()
            if deity_id in faith.deity_ids]


# ---------------------------------------------------------------------------
# Покровительство двигается с причиной
# ---------------------------------------------------------------------------

def _favour_move(ctx, rng, head, deity, year: int, up: bool,
                 forced: str = "") -> None:
    world = ctx.world
    races = _races_here(world)
    if not races:
        return
    # Двигается покровительство к тем, кто рядом: чаще к своим, но и
    # чужие могут сделать то, чего он не ждал.
    pairs = []
    for race_id in races:
        weight = 3.0 if race_id == deity.race_id else 1.0
        if race_id in head.favour:
            weight *= 1.6
        pairs.append((race_id, weight))
    pairs.sort(key=lambda pair: pair[0])
    race_id = rng.weighted(pairs)
    race = races_mod.RACES_BY_ID.get(race_id)
    if race is None:
        return

    if forced:
        reason, shift = forced, (0.12 if up else -0.25)
    else:
        reason, shift = rng.choice(cat.FAVOUR_UP if up else cat.FAVOUR_DOWN)
    row = head.favour.get(race_id) or {"сила": 0.0, "почему": "", "год": year}
    before = float(row.get("сила", 0.0))
    after = max(-1.0, min(1.0, before + shift))
    head.favour[race_id] = {"сила": round(after, 3), "почему": reason,
                            "куда": "вверх" if after > before else "вниз",
                            "год": int(year)}

    # Заметным считается не всякое движение, а переход через черту:
    # избранный народ, отвернулся, проклял.
    if cat.favour_name(before) == cat.favour_name(after):
        return
    line = "%s %s: %s." % (texts.cap(race.name),
                           "теперь" if after > before else "теперь",
                           cat.favour_name(after))
    _mark(head, year, cat.FAVOUR_MARK,
          "%s %s" % (texts.favour_line(rng, reason, after > before), line))
    if after >= 0.6:
        head.notes.append("держит своим народ по имени %s" % race.name)
        _tell(ctx, head, deity, year, "завет",
              "народ по имени %s стал его народом: %s" % (race.name, reason),
              loud=3, race_id=race_id)
    elif after <= -0.6:
        _tell(ctx, head, deity, year, "отречение",
              "он отвернулся от народа по имени %s: %s" % (race.name, reason),
              loud=3, race_id=race_id)


# ---------------------------------------------------------------------------
# Дела богов
# ---------------------------------------------------------------------------

def _do_deed(ctx, rng, head, deity, year: int, followers: int) -> None:
    has_foe = any(item["связь"] in (cat.FOE, cat.RIVAL) for item in head.bonds)
    pairs = []
    for deed in cat.DEEDS:
        if deed.needs == "верующие" and followers < 200:
            continue
        if deed.needs == "запрет" and not head.taboos:
            continue
        if deed.needs == "враг" and not has_foe:
            continue
        if deed.key in ("уход", "возвращение") and not _may_leave(head, year):
            continue
        # Уходят не от скуки: бог оставляет мир, когда его именем давно
        # делают не его дело, а вернуться может и без причины.
        if deed.key == "уход" and head.drift < 0.4:
            continue
        pairs.append((deed, deed.weight))
    if not pairs:
        return
    pairs.sort(key=lambda pair: pair[0].key)
    deed = rng.weighted(pairs)
    about = _deed_about(ctx, rng, head, deity, deed, year)
    _mark(head, year, cat.DEED_MARK, texts.deed_line(rng, deed.key, about))
    head.deeds.append({"год": int(year), "вид": deed.key, "строка": about})
    if deed.key == "уход":
        head.gone_year = year
        head.back_year = 0
    elif deed.key == "возвращение":
        head.back_year = year
    if deed.loud >= LOUD_ENOUGH:
        _tell(ctx, head, deity, year, deed.key, about, loud=deed.loud)


def _may_leave(head, year: int) -> bool:
    """Уходят и возвращаются редко и не дважды подряд."""
    if head.gone_year and not head.back_year:
        return year - head.gone_year > 300
    return year - max(head.gone_year, head.back_year) > 500


def _deed_about(ctx, rng, head, deity, deed, year: int) -> str:
    """Чем именно обернулось дело — по сферам и по тому, что уже было."""
    world = ctx.world
    if deed.key == "кара" and head.taboos:
        return "покарал тех, кто взялся %s" % rng.choice(head.taboos)
    if deed.key == "дар" and head.gifts:
        gift = rng.choice(head.gifts)
        return "дал %s — %s" % (gift["дар"], gift["кому"])
    if deed.key in ("спор", "война богов") and head.bonds:
        foes = [item for item in head.bonds
                if item["связь"] in (cat.FOE, cat.RIVAL)]
        if foes:
            item = rng.choice(foes)
            other = world.deities.get(item["кто"])
            if other is not None:
                return "сошёлся с %s — %s" % (texts.god_ref(other, "род"),
                                              item["почему"])
    if deed.key == "реликвия":
        return "оставил вещь, и её после искали не раз"
    if deed.key == "подмена":
        return "чудеса пошли от кого-то, кто говорит его голосом"
    if deed.key == "молчание":
        return "перестал отвечать, и никто не знает почему"
    if deed.key == "явление":
        return "показался людям сам, и свидетели спорят, что видели"
    return deed.about


# ---------------------------------------------------------------------------
# Культ уходит от воли бога
# ---------------------------------------------------------------------------

def _cult_drift(ctx, rng, head, deity, year: int) -> None:
    """Жрецы прочли его волю по-своему — и это осталось надолго."""
    key, about, weight = rng.choice(cat.DRIFTS)
    head.drift = round(min(1.0, head.drift + weight * DRIFT_STEP), 3)
    head.drifts.append({"год": int(year), "как": key, "что": about})
    _mark(head, year, cat.DRIFT_MARK, texts.drift_line(rng, about))
    if head.drift >= 0.5 and rng.chance(0.4):
        # Бог, если бы его спросили, ответил бы так.
        head.notes.append("%s — %s" % (rng.choice(cat.GOD_SAYS), about))
    if head.drift >= SILENCE_DRIFT:
        _tell(ctx, head, deity, year, "расхождение",
              "вера делает его именем то, о чём он не просил: %s" % about,
              loud=3)


REFORMS = (
    "нашли старый список и сверили с ним нынешний устав",
    "в руины пришёл человек и прочёл то, что было вырезано на камне",
    "чудо случилось там, где по нынешнему уставу его быть не должно",
    "вернулась реликвия, и с ней вернулась забытая половина завета",
    "явился проповедник и заставил вспомнить, с чего всё начиналось",
)


def _reform(ctx, rng, head, deity, year: int) -> None:
    """Возврат к тому, с чего вера начиналась.

    Без этого расхождение шло бы только в одну сторону, и всякая вера к
    середине истории делалась бы противоположностью себе. На деле раз в
    несколько веков находится тот, кто сверяет нынешний устав с древним
    списком, — и часть наносного отваливается.
    """
    how = rng.choice(REFORMS)
    head.drift = round(max(0.0, head.drift - 0.3), 3)
    head.drifts.append({"год": int(year), "как": "возврат", "что": how})
    _mark(head, year, cat.DRIFT_MARK,
          "Веру вернули к прежнему: %s." % how)
    _tell(ctx, head, deity, year, "возврат к древнему уставу", how, loud=3)


# ---------------------------------------------------------------------------
# Пророчества
# ---------------------------------------------------------------------------

def _prophesy(ctx, rng, head, deity, year: int) -> None:
    words = texts.prophecy_text(rng.choice(cat.OMENS), rng.choice(cat.DOERS),
                                rng.choice(cat.FORETOLD))
    truth = rng.choice(cat.TRUE_MEANINGS)
    readings = list(rng.shuffled(list(cat.READINGS)))[:2]
    head.prophecies.append({"слова": words, "правда": truth,
                            "читают": readings, "год": int(year),
                            "сбылось": 0})
    _mark(head, year, cat.PROPHECY_MARK, texts.prophecy_line(rng, words))
    _tell(ctx, head, deity, year, "пророчество",
          "сказано было: «%s». %s" % (words, texts.cap(readings[0])), loud=3)


# ---------------------------------------------------------------------------
# Избранники
# ---------------------------------------------------------------------------

def _choose_one(ctx, rng, head, deity, year: int) -> None:
    """Бог выбирает человека — и человек не обязан справиться."""
    world = ctx.world
    race_id = _favoured_race(head, deity)
    pool = []
    for figure in world.figures.values():
        if not figure.alive_at(year) or figure.race_id != race_id:
            continue
        if figure.age_at(year) < 16:
            continue
        pool.append(figure)
        if len(pool) >= 40:
            break
    if not pool:
        return
    pool.sort(key=lambda item: item.id)
    figure = rng.choice(pool)
    task = rng.choice(cat.CHOSEN_TASKS)
    head.chosen.append({"кто": figure.id, "имя": figure.plain_name,
                        "дело": task, "год": int(year), "чем": "", "конец": 0})
    _mark(head, year, cat.CHOSEN_MARK, texts.chosen_line(rng, task))
    figure.notes.append("избран %s: %s" % (texts.god_ref(deity, "дат"), task))


def _close_chosen(ctx, rng, head, deity, year: int) -> None:
    world = ctx.world
    for item in head.chosen:
        if item.get("чем"):
            continue
        figure = world.figures.get(item["кто"])
        if figure is None:
            item["чем"], item["конец"] = "пропал", year
            continue
        dead = figure.death is not None and figure.death.year <= year
        if not dead and year - int(item.get("год", year)) < 30:
            continue
        name, about, _ = rng.weighted([(row, row[2]) for row in cat.CHOSEN_ENDS])
        if dead and name == "исполнил" and rng.chance(0.5):
            name, about = "погиб", "не дошёл"
        item["чем"] = name
        item["конец"] = int(min(year, figure.death.year) if dead else year)
        _mark(head, item["конец"], cat.CHOSEN_MARK,
              texts.chosen_end(rng, "%s — %s" % (item["имя"], about)))
        if name in ("исполнил", "предал"):
            _tell(ctx, head, deity, item["конец"], "избрание",
                  "избранник по имени %s %s" % (item["имя"], about), loud=3)


def _favoured_race(head, deity) -> str:
    best, best_value = deity.race_id, -9.0
    for race_id, row in head.favour.items():
        value = float(row.get("сила", 0.0))
        if value > best_value:
            best, best_value = race_id, value
    return best or deity.race_id


# ---------------------------------------------------------------------------
# Символы и праздники переживают смысл
# ---------------------------------------------------------------------------

def _symbol_fate(ctx, rng, head, deity, year: int) -> None:
    left = [name for name in head.symbols
            if not any(item["знак"] == name for item in head.symbol_fates)]
    if not left:
        return
    what = rng.choice(sorted(left))
    fate = rng.choice(cat.SYMBOL_FATES)
    head.symbol_fates.append({"знак": what, "что стало": fate,
                              "год": int(year)})
    _mark(head, year, cat.SYMBOL_MARK,
          texts.symbol_line(rng, "%s (%s)" % (what, head.symbols[what]), fate))


def _feast_turn(ctx, rng, head, deity, year: int) -> None:
    if len(head.feast_turns) >= 3:
        return
    turn = rng.choice(cat.FEAST_TURNS)
    head.feast_turns.append({"год": int(year), "что": turn})
    _mark(head, year, cat.FEAST_MARK,
          texts.feast_line(rng, deity.festival_name, turn))


# ---------------------------------------------------------------------------
# Мелочи
# ---------------------------------------------------------------------------

def _temple_news(world, year: int, period: int) -> dict:
    """Кому за это десятилетие поставили храм, а у кого сожгли.

    Один проход по храмам на весь такт: спрашивать про каждого бога
    отдельно было бы вдесятеро дороже.
    """
    out = {}
    for temple in world.temples.values():
        if not temple.deity_id:
            continue
        if temple.founded is not None \
                and year - period < temple.founded.year <= year:
            out[temple.deity_id] = out.get(temple.deity_id, 0) + 1
        if temple.ended is not None \
                and year - period < temple.ended.year <= year:
            out[temple.deity_id] = out.get(temple.deity_id, 0) - 1
    return out


def _mark(head, year: int, kind: str, line: str) -> None:
    if not line:
        return
    head.marks.append({"год": int(year), "вид": kind, "строка": line})
    if len(head.marks) > MAX_MARKS:
        head.marks = head.marks[:MAX_MARKS // 2] + head.marks[-MAX_MARKS // 2:]


def _tell(ctx, head, deity, year: int, kind: str, about: str, loud: int = 3,
          race_id: str = "") -> None:
    """Громкое дело идёт в летопись; тихое живёт в биографии бога."""
    world = ctx.world
    rng = ctx.rng("god-events", year)
    # Громкое дело мир запоминает всегда, обычное — через раз: иначе
    # летопись превращается в перечень знамений.
    if loud < 4 and not rng.chance(0.35):
        return
    date = ctx.date_in(rng, year)
    title = "%s: %s" % (texts.cap(kind), deity.given_name)
    event = world.add_event(
        date=date, era_index=world.era_index_at(year), kind="divine_deed",
        title=title, text="%s %s." % (texts.cap(texts.god_ref(deity)),
                                      about),
        importance=min(5, 1 + loud), subjects=[deity.id],
        race_id=race_id or deity.race_id)
    head.event_ids.append(event.id)
    # След в ткани причин: богам держава помнит и милость, и кару.
    for faith_id in _faiths_of(world, deity.id):
        faith = world.faiths.get(faith_id)
        if faith is None:
            continue
        for polity_id in faith.polity_ids[:2]:
            history.leave(world,
                          history.SACRILEGE if kind in ("отречение",
                                                        "молчание")
                          else history.FAVOUR,
                          year, polity_id, weight=0.3,
                          note="дело %s" % texts.god_ref(deity, "род"),
                          event_id=event.id)


__all__ = ["prepare", "upkeep"]
