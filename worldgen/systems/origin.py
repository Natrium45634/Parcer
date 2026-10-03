# -*- coding: utf-8 -*-
"""Ход начала мира: что было на самом деле — и что из этого узнали.

Система работает дважды и больше не вмешивается никогда.

**`prepare`** — один раз, в самом начале, после того как легли земли,
выбран уклад творения (`cosmogony`) и прошёл мифический век
(`divinity.prepare`). Тут решается то, **что было**: зачем мир вообще
сделан, в каком порядке положены его слои, каких слоёв в нём нет вовсе,
о чём спорили при каждом, какие законы из этого вышли, чем кончился
первый спор и что после него заперли, как завелась жизнь и кем были
первые, и какие шрамы творение оставило на настоящей земле.

**`close`** — в самом конце, когда народы уже прожили свою историю. Тут
решается то, **что об этом знают**: у каждого крупного народа своя
версия начала, и версия эта тем дальше от правды, чем меньше мир о себе
знает. Раньше конца это сделать нельзя: при творении народов ещё нет, а
миф принадлежит тем, кто жив.

Чего система нарочно не делает. Не заводит второй миф поверх
мифического века: первородные, их спор и останки — оттуда, и тут они
действующие лица, а не копия. Не разрешает противоречий между
источниками: нерешённое остаётся нерешённым, и до него потом докапывается
быль. И не кладёт слоёв больше, чем нужно: мир без сна, без души или без
магии — не обеднённый мир, а другой.
"""

from __future__ import annotations

from .. import origin as cat
from .. import narrative_origin as texts
from .. import sites as sites_mod
from ..models import ACTIVE
from ..timeline import Date

# Сколько шрамов творение оставляет на земле. Больше пяти — и мир
# превращается в поле аномалий, где странное перестаёт быть странным.
SCARS_MIN = 2
SCARS_MAX = 5

# С каким шансом о слое спорили. Спор — не правило: часть мира положили
# молча, и об этих частях рассказывать нечего.
DISPUTE_CHANCE = 0.45

# С каким шансом слой встал не на своё место — смерть прежде жизни,
# сознание прежде живого. Это самое заметное, что может случиться с
# порядком, и потому это редкость.
INVERT_CHANCE = 0.16

# Сколько народов получают свою версию начала.
VERSIONS_MAX = 6

# Сколько законов мир может назвать вслух. Правил у мира много, но
# свод из тринадцати строк читается как список, а не как устройство
# мира: назвать несколько — значит сказать о мире больше, чем назвать
# все. Остальные действуют молча, и это не умолчание, а честность.
MAX_NAMED_LAWS = 7

# Сколько противоречий между источниками заводится.
CLASH_MIN = 1
CLASH_MAX = 4


# ---------------------------------------------------------------------------
# Что было на самом деле
# ---------------------------------------------------------------------------

def prepare(ctx) -> None:
    world = ctx.world
    rng = ctx.rng("origin", "dawn")

    model = getattr(ctx, "cosmogony", "") or "безначальный мир"
    motif = _pick_motif(rng, model)
    sure = rng.weighted([(item, item.weight) for item in
                         sorted(cat.CERTAINTY.values(),
                                key=lambda row: row.key)])

    origin = world.set_origin(model=model, motif=motif.key,
                              certainty=sure.key, known=sure.known)
    _lay_layers(ctx, rng, origin)
    _collect_laws(ctx, rng, origin, motif)
    _first_quarrel(ctx, rng, origin)
    _first_life(ctx, rng, origin)
    _leave_scars(ctx, rng, origin)
    _make_clashes(ctx, rng, origin)

    # Законы мира нужны не только летописи: на них ссылаются обряды,
    # запреты и чудеса. Поэтому они кладутся туда, где их видно всем.
    ctx.cosmic_laws = {row["ключ"] for row in origin.laws}
    world.notes["начало мира"] = {
        "уклад": origin.model,
        "мотив": motif.name,
        "известно": sure.name,
        "слоёв положено": len(origin.layers),
        "слоёв нет": list(origin.missing),
        "законы": origin.law_texts,
    }
    _write_dawn(ctx, origin, motif, sure)


def _pick_motif(rng, model: str):
    """Зачем мир есть. Мотив должен быть к укладу, а не любой.

    Мир-тюрьму не строят там, где творца не было вовсе, а «незачем» не
    говорят о мире, который кто-то лепил своими руками.
    """
    rows = []
    for item in sorted(cat.MOTIFS.values(), key=lambda row: row.key):
        if item.needs and model not in item.needs:
            continue
        rows.append((item, item.weight))
    if not rows:
        return cat.MOTIFS["nobody_knows"]
    return rng.weighted(rows)


# ---------------------------------------------------------------------------
# Слои
# ---------------------------------------------------------------------------

def _lay_layers(ctx, rng, origin) -> None:
    """Из чего мир сложен и в каком порядке.

    Сперва решается, какие слои в этом мире есть вообще: пространство,
    время, материю, жизнь и сознание кладут всегда, прочие — по весу.
    Потом они выстраиваются в черёд, и тут самое важное: слой может
    встать **прежде** того, на чём держится, — смерть прежде жизни,
    сознание прежде живого. Это редкость, и это меняет мир сильнее,
    чем любая подробность.
    """
    present = list(cat.MUST)
    for key in cat.LAYER_ORDER:
        if key in present:
            continue
        layer = cat.LAYERS[key]
        if rng.chance(min(0.93, layer.weight / 3.0)):
            present.append(key)
        else:
            origin.missing.append(key)

    # Черёд: идём по обычному порядку чтения, но каждый слой может
    # обогнать то, что должно было лежать прежде него.
    order = [key for key in cat.LAYER_ORDER if key in present]
    for index, key in enumerate(list(order)):
        layer = cat.LAYERS[key]
        if not layer.needs or index == 0:
            continue
        if not rng.chance(INVERT_CHANCE):
            continue
        first_need = min((order.index(need) for need in layer.needs
                          if need in order), default=None)
        if first_need is None or first_need >= index:
            continue
        # Пространство обогнать нельзя: материи, которую положили прежде
        # места, негде лежать. Это не осторожность, а то же правило, из
        # которого потом выходит закон «расстояние нельзя отменить».
        if first_need == 0 and order[0] == cat.SPACE:
            continue
        order.remove(key)
        order.insert(first_need, key)

    actors = _actors(ctx)
    for number, key in enumerate(order, start=1):
        layer = cat.LAYERS[key]
        row = {"слой": key, "черёд": number,
               "кем": rng.choice(actors) if actors else "",
               "спор": "", "чего хотел": "", "чем кончилось": "",
               "цена": "", "кто спорил": ""}
        early = number <= 3
        late = number >= len(order) - 1
        row["чем вышло"] = layer.early if early else (
            layer.late if late else layer.about)
        if rng.chance(DISPUTE_CHANCE):
            dispute = rng.choice(sorted(cat.DISPUTES.values(),
                                        key=lambda item: item.key))
            row["спор"] = dispute.key
            row["чего хотел"] = dispute.want
            row["чем кончилось"] = dispute.how
            row["цена"] = dispute.cost
            if len(actors) > 1:
                row["кто спорил"] = rng.choice(
                    [name for name in actors if name != row["кем"]])
        origin.layers.append(row)


def _actors(ctx) -> list:
    """Кто вообще мог это делать: творцы и первородные — не выдуманные.

    Имена берутся из тех божеств, что уже есть в мире: творцы из
    `cosmogony` и первородные из мифического века. Если в мире не было
    ни тех, ни других, слои кладёт никто — и это тоже ответ.
    """
    world = ctx.world
    rows = []
    for deity in world.deities.values():
        if deity.maker or deity.primordial:
            rows.append(deity.id)
    rows.sort(key=lambda value: (len(value), value))
    return rows


# ---------------------------------------------------------------------------
# Законы
# ---------------------------------------------------------------------------

def _collect_laws(ctx, rng, origin, motif) -> None:
    """Законы мира: из мотива, из слоёв и из их порядка.

    Закон попадает в свод не всякий: мир знает о себе ровно столько,
    сколько даёт его достоверность. Остальные законы действуют, но
    названы быть не могут — и это честнее, чем полный свод в мире, где о
    начале спорят.
    """
    keys = [motif.law]
    for row in origin.order:
        layer = cat.LAYERS.get(row["слой"])
        if layer is not None and layer.law:
            keys.append(layer.law)
    for mark, (law_key, why) in sorted(cat.ORDER_LAWS.items()):
        if _holds(origin, mark):
            keys.append(law_key)

    seen = set()
    for key in keys:
        law = cat.LAWS.get(key)
        if law is None or key in seen:
            continue
        seen.add(key)
        # Чем меньше мир знает о себе, тем меньше законов он может
        # назвать вслух. Названные — не выдумка: они те же самые.
        origin.laws.append({"ключ": key, "закон": law.text,
                            "отчего": law.because, "касается": law.touches,
                            "нарушить": law.breaks, "известен": False})

    # Какие законы мир называет вслух: первым — тот, что из мотива (это
    # и есть главное о мире), дальше по жребию, и не больше, чем мир
    # вообще способен о себе знать.
    room = max(1, min(MAX_NAMED_LAWS,
                      int(round(1 + MAX_NAMED_LAWS * origin.known))))
    rows = list(origin.laws)
    named = [rows[0]] if rows else []
    rest = rows[1:]
    while rest and len(named) < room:
        pick = rng.choice(rest)
        rest.remove(pick)
        named.append(pick)
    for row in named:
        row["известен"] = True


def _holds(origin, mark: str) -> bool:
    """Сошлось ли условие, из которого выходит закон порядка."""
    order = [row["слой"] for row in origin.order]
    place = {key: index for index, key in enumerate(order)}
    if mark == "смерть позже жизни":
        return (cat.DEATH in place and cat.LIFE in place
                and place[cat.DEATH] > place[cat.LIFE])
    if mark == "смерть прежде жизни":
        return (cat.DEATH in place and cat.LIFE in place
                and place[cat.DEATH] < place[cat.LIFE])
    if mark == "души нет вовсе":
        return cat.SOUL in origin.missing
    if mark == "магия сразу за памятью":
        return (cat.MAGIC in place and cat.MEMORY in place
                and place[cat.MAGIC] - place[cat.MEMORY] == 1)
    if mark == "жизнь прежде сознания":
        return (cat.LIFE in place and cat.MIND in place
                and place[cat.LIFE] < place[cat.MIND])
    if mark == "спор кончился запретом":
        return any(row.get("спор") == "undone" for row in origin.layers)
    return False


# ---------------------------------------------------------------------------
# Первый спор
# ---------------------------------------------------------------------------

def _first_quarrel(ctx, rng, origin) -> None:
    """Самый крупный из споров — и то, что после него заперли.

    Крупным считается спор о слое, который для мира тяжелее прочих:
    смерть, магия, душа. Запечатанное — не конец, а отложенный конец:
    печать надо обновлять, и через десять тысяч лет это будет уже
    обычная беда.
    """
    rows = [row for row in origin.layers if row.get("спор")]
    if not rows:
        return
    def heft(row):
        layer = cat.LAYERS.get(row["слой"])
        return layer.weight if layer is not None else 1.0
    rows.sort(key=lambda row: (-heft(row), row["черёд"]))
    row = rows[0]
    origin.quarrel = row["слой"]
    origin.quarrel_how = row["чем кончилось"]
    origin.quarrel_cost = row["цена"]
    origin.winner_id = row.get("кем", "")
    origin.loser_id = row.get("кто спорил", "")
    if rng.chance(0.55):
        what, how = rng.choice(cat.SEALED)
        origin.sealed = what
        origin.sealed_how = how


# ---------------------------------------------------------------------------
# Жизнь и первые
# ---------------------------------------------------------------------------

def _first_life(ctx, rng, origin) -> None:
    """Как завелось живое и кем были первые.

    Путь жизни сверяется с тем, что в мире есть: жизнь из силы не
    заводится там, где магии не положили. А если все нынешние народы из
    одного корня, у них есть общее происхождение, о котором они не
    помнят, — и расхождение, у которого названа причина.
    """
    rows = []
    for way in sorted(cat.LIFE_WAYS.values(), key=lambda item: item.key):
        if any(need in origin.missing for need in way.needs):
            continue
        rows.append((way, way.weight))
    way = rng.weighted(rows) if rows else cat.LIFE_WAYS["self"]
    origin.life_way = way.key
    if way.law and way.law in cat.LAWS \
            and not any(row["ключ"] == way.law for row in origin.laws):
        law = cat.LAWS[way.law]
        origin.laws.append({"ключ": law.key, "закон": law.text,
                            "отчего": law.because, "касается": law.touches,
                            "нарушить": law.breaks,
                            "известен": rng.chance(0.5 + 0.4 * origin.known)})

    kind = rng.weighted([(item, item.weight) for item in
                         sorted(cat.FIRST_KINDS.values(),
                                key=lambda row: row.key)])
    origin.first_kind = kind.key
    origin.one_root = way.key in ("one_root", "made") or rng.chance(0.3)
    if origin.one_root:
        split, how = rng.choice(cat.SPLITS)
        origin.split = split
        origin.split_how = how


# ---------------------------------------------------------------------------
# Шрамы творения
# ---------------------------------------------------------------------------

def _leave_scars(ctx, rng, origin) -> None:
    """Чем начало мира отзывается через десять тысяч лет.

    Шрам ложится в настоящую землю и, если до него можно дойти ногами, —
    в настоящее место. Через тысячи лет туда придут, не зная, что это, и
    это будет уже обычная быль, а не миф.
    """
    world = ctx.world
    regions = [region for region in world.regions.values()
               if not getattr(region, "drowned", False)]
    if not regions:
        return
    count = rng.randint(SCARS_MIN, SCARS_MAX)
    pool = sorted(cat.SCARS.values(), key=lambda item: item.key)
    taken = set()
    for _ in range(count):
        rows = [(item, item.weight) for item in pool if item.key not in taken]
        if not rows:
            break
        scar = rng.weighted(rows)
        taken.add(scar.key)
        region = _scar_region(rng, regions, scar)
        row = {"вид": scar.key, "имя": scar.name, "что было": scar.about,
               "что теперь": scar.now,
               "земля": region.id if region is not None else "",
               "место": ""}
        # Шрам, увязанный со слоем, которого в мире нет, — бессмыслица.
        if scar.key == "sleepless" and cat.DREAM in origin.missing:
            row["что было"] = cat.LAYERS[cat.DREAM].without
        if scar.key == "dense_magic" and cat.MAGIC in origin.missing:
            continue
        if region is not None and rng.chance(0.6):
            site = _scar_site(ctx, rng, scar, region)
            row["место"] = site.id
        origin.scars.append(row)


def _scar_region(rng, regions, scar):
    """Земля под шрам: кости — в горы, древнее море — к берегу."""
    fitting = [region for region in regions
               if not scar.terrain or region.terrain in scar.terrain]
    pool = fitting or regions
    return rng.choice(sorted(pool, key=lambda item: item.id))


def _scar_site(ctx, rng, scar, region):
    """Место, до которого можно дойти ногами."""
    world = ctx.world
    word = rng.choice(("Рубец", "Шов", "Провал", "Отметина", "Запечье",
                       "Старина"))
    name = ctx.forge.unique(
        "site", lambda: "%s %s" % (word, region.name), rng)
    site = world.add_site(
        kind=sites_mod.SEALED, name=name, region_id=region.id,
        created=Date(1, 1, 1),
        guards=rng.choice(sites_mod.GUARDS[sites_mod.SEALED]),
        riches=sites_mod.riches_for(rng, sites_mod.SEALED, 1.2),
        hex_index=_hex_of(ctx, region.id, rng))
    site.depth = sites_mod.depth_for(sites_mod.SEALED, site.riches, True)
    site.story = "Это осталось от самого творения: %s. %s." \
        % (scar.about, texts.cap(scar.now))
    site.notes.append("шрам творения: %s" % scar.name)
    return site


def _hex_of(ctx, region_id: str, rng) -> int:
    region = ctx.world.regions.get(region_id)
    if region is None or not region.hexes:
        return -1
    return rng.choice(sorted(region.hexes))


# ---------------------------------------------------------------------------
# Противоречия
# ---------------------------------------------------------------------------

def _make_clashes(ctx, rng, origin) -> None:
    """Где источники спорят друг с другом.

    Генератор не обязан разрешать противоречие. Вера говорит одно,
    древняя надпись другое, сама вещь третье — и это остаётся так.
    Чем меньше мир знает о себе, тем больше таких мест.
    """
    count = rng.randint(CLASH_MIN, CLASH_MAX)
    if origin.known > 0.8:
        count = min(count, 2)
    about = [row["слой"] for row in origin.order] + ["творец", "первая жизнь",
                                                     "первый спор"]
    sources = sorted(cat.SOURCES.values(), key=lambda item: item.key)
    used = set()
    for _ in range(count):
        subject = rng.choice(sorted(set(about)))
        if subject in used:
            continue
        used.add(subject)
        first, second = rng.choice(sources), rng.choice(sources)
        if first.key == second.key:
            continue
        kind, how = rng.choice(cat.CLASHES)
        origin.clashes.append({
            "о чём": subject, "расхождение": kind, "как": how,
            "кто": first.name, "против": second.of,
            # Разрешить противоречие может только тот, у кого есть
            # третий источник, а третьего обычно нет.
            "решено": rng.chance(0.18 * origin.known)})


# ---------------------------------------------------------------------------
# Первая запись летописи
# ---------------------------------------------------------------------------

def _write_dawn(ctx, origin, motif, sure) -> None:
    world = ctx.world
    date = Date(1, 1, 1)
    title, text = texts.dawn_event(origin, motif, sure)
    event = world.add_event(
        date=date, era_index=0, kind="world_origin", title=title, text=text,
        importance=5, subjects=[origin.id])
    if event is not None:
        origin.event_ids.append(event.id)
    named = [row for row in origin.laws if row.get("известен")]
    if named:
        title, text = texts.laws_event(origin, named)
        event = world.add_event(
            date=date, era_index=0, kind="world_laws", title=title,
            text=text, importance=4, subjects=[origin.id])
        if event is not None:
            origin.event_ids.append(event.id)


# ---------------------------------------------------------------------------
# Что об этом узнали
# ---------------------------------------------------------------------------

def close(ctx, total: int) -> None:
    """Версии начала у тех, кто дожил, — и то, что осталось без ответа.

    Делается в самом конце: при творении народов ещё нет, а миф
    принадлежит живым. Версия тем дальше от правды, чем меньше мир знает
    о себе и чем дальше народ от того места, где всё случилось.
    """
    world = ctx.world
    origin = world.origin
    if origin is None:
        return
    rng = ctx.rng("origin", "close")

    folks = [folk for folk in world.folks.values()
             if folk.status == ACTIVE and folk.population > 0]
    folks.sort(key=lambda item: (-item.population, item.id))
    for folk in folks[:VERSIONS_MAX]:
        origin.versions.append({
            "кто": folk.name, "чей": folk.id,
            "как": texts.folk_version(rng, origin, folk.name),
        })
    for faith in sorted(world.faiths.values(),
                        key=lambda item: (-item.followers, item.id))[:2]:
        if faith.status != ACTIVE:
            continue
        origin.versions.append({
            "кто": "вера по имени %s" % faith.name, "чей": faith.id,
            "как": texts.faith_version(rng, origin, faith.name),
        })

    # Что осталось без ответа. Это не дыра в генераторе, а свойство
    # мира: о начале знают ровно столько, сколько знают.
    hidden = [row["слой"] for row in origin.layers
              if not rng.chance(origin.known)]
    for key in hidden[:4]:
        layer = cat.LAYERS.get(key)
        if layer is not None:
            origin.unknown.append(
                "о том, когда в мир пришло %s, согласия нет" % layer.name)
    if not origin.winner_id:
        origin.unknown.append("кто настоял в первом споре, не записано")
    # Противоречия тут не перечисляются: они уже названы выше своими
    # словами, и повторять их списком — значит сказать дважды одно.
    kind = cat.FIRST_KINDS.get(origin.first_kind)
    if kind is not None and not rng.chance(origin.known):
        origin.unknown.append("куда девались первые, не знает никто")
    if origin.sealed and not rng.chance(origin.known):
        origin.unknown.append("держится ли ещё печать в основании мира, "
                              "проверить некому")
    if origin.scars and not rng.chance(origin.known):
        row = origin.scars[0]
        origin.unknown.append("отчего взялось то, что зовут «%s», никто "
                              "объяснить не может" % row.get("имя", ""))
    world.notes["о начале неизвестно"] = list(origin.unknown)


__all__ = ["prepare", "close"]
