# -*- coding: utf-8 -*-
"""Тексты о владениях чудовищ.

Правила прежние: имена собственные в именительном падеже и в косвенном
месте ставятся оборотом со склоняемым словом («у владения по имени X»),
прилагательные подставляются парами, глаголы — в настоящем времени.

Особая забота тут — **не пугать**. Владение чудовища и так страшно;
летопись, которая вдобавок ужасается вслух, читается как
приключенческая повесть, а не как история. Поэтому тон ровный: что
случилось, с кем, чем платят и как к этому относятся. Ужас — дело тех,
кто там живёт, и он виден по тому, что они делают.

И второе: **не всякое владение — зло**. У половины из них соседи
терпят хозяина по названной причине, и эта причина в тексте стоит
рядом с данью.
"""

from __future__ import annotations

from . import dominion as cat
from .narrative import cap

# Падежи слова-обёртки: имя собственное не склоняется, склоняется слово
# перед ним. Слово общее — «владение», а не слово вида: «царства мёртвых
# по имени X» потребовало бы склонять двенадцать видов, каждый со своим
# исключением.
_CASES = {"nom": "владение", "gen": "владения", "dat": "владению",
          "ins": "владением", "pre": "владении"}


def named(hold, case: str = "nom") -> str:
    """«владение по имени X» в нужном падеже."""
    return "%s по имени %s" % (_CASES.get(case, _CASES["nom"]), hold.name)


def said_of(hold) -> str:
    """«драконье владение по имени X» — именительный, для подлежащего.

    Если имя уже начинается словом вида («Гнездовье Тихих Холмов»),
    оборот не нужен: «гнездовье по имени Гнездовье» — это заикание.
    """
    word = cat.kind_word(hold.kind)
    head = word.split()[-1].lower()
    if head in [part.lower() for part in hold.name.split()]:
        return hold.name
    return "%s по имени %s" % (word, hold.name)


def pair(gender: str, male: str, female: str, neuter: str) -> str:
    if gender == "f":
        return female
    if gender == "n":
        return neuter
    return male


def _forms(hold) -> dict:
    """Согласование с родом слова вида и с полом хозяина сразу.

    Подлежащее в одних фразах — владение («царство»), в других хозяин
    («дракон»). Рода у них разные, поэтому наборов два, и путать их
    нельзя: «царство пришёл» и «дракон встало» — обе ошибки.
    """
    gender = cat.kind_gender(hold.kind)
    lord = hold.lord_gender or "m"

    def take(male, female, neuter):
        return pair(gender, male, female, neuter)

    def lord_take(male, female):
        return pair(lord, male, female, male)

    return {
        "it": take("его", "её", "его"),
        "in_it": take("в нём", "в ней", "в нём"),
        "about": take("о нём", "о ней", "о нём"),
        "he": take("он", "она", "оно"),
        "he_cap": take("Он", "Она", "Оно"),
        "stood": take("стоял", "стояла", "стояло"),
        "became": take("стал", "стала", "стало"),
        "held": take("держался", "держалась", "держалось"),
        "lord_came": lord_take("пришёл", "пришла"),
        "lord_took": lord_take("взял", "взяла"),
        "lord_he": lord_take("он", "она"),
        "lord_he_cap": lord_take("Он", "Она"),
        "lord_it": lord_take("его", "её"),
        "lord_at": lord_take("при нём", "при ней"),
        "lord_about": lord_take("о нём", "о ней"),
        "lord_left": lord_take("ушёл", "ушла"),
        "lord_slept": lord_take("уснул", "уснула"),
        "named": named(hold), "named_cap": cap(named(hold)),
        "named_of": named(hold, "gen"),
        "named_of_cap": cap(named(hold, "gen")),
        "named_to": named(hold, "dat"),
        "named_by": named(hold, "ins"),
        "named_at": named(hold, "pre"),
    }


def _pack(hold, region=None, **extra) -> dict:
    said = said_of(hold)
    pack = dict(_forms(hold))
    pack.update({
        "who": said, "who_cap": cap(said), "name": hold.name,
        "lord": hold.lord_name or "никто",
        "lord_word": hold.lord_word or "хозяин",
        "kind": cat.kind_word(hold.kind),
        "kind_about": cat.kind_about(hold.kind),
        "land": region.name if region is not None else "безымянной",
        "why": hold.origin_why or cat.kind_about(hold.kind),
        "why_cap": cap(hold.origin_why or cat.kind_about(hold.kind)),
        "control": cat.control_word(hold.control),
        "control_about": cat.control_about(hold.control),
        "motive": cat.motive_word(hold.motive),
        "motive_about": cat.motive_about(hold.motive),
    })
    pack.update(extra)
    return pack


# ---------------------------------------------------------------------------
# Как оно завелось
# ---------------------------------------------------------------------------

ROSE_LORD = (
    "В земле по имени %(land)s заводится то, чему в летописи державы нет "
    "названия: %(who)s. %(why_cap)s. Держится это %(control)s: "
    "%(control_about)s.",
    "%(who_cap)s. Хозяин тут %(lord_word)s по имени %(lord)s, и нужно "
    "%(lord_it)s одно: %(motive)s — %(motive_about)s.",
    "Земля по имени %(land)s перестаёт быть чьей бы то ни было: теперь "
    "это %(who)s. %(why_cap)s.",
)

ROSE_EMPTY = (
    "Землю по имени %(land)s перестают считать землёй: это теперь "
    "%(who)s. %(why_cap)s. Ходить туда перестают не по запрету, а по "
    "тому, что оттуда не возвращаются.",
    "О земле по имени %(land)s говорят коротко: %(who)s. %(why_cap)s.",
)


def rose(rng, hold, region) -> tuple:
    lines = ROSE_EMPTY if hold.kind in cat.LORDLESS else ROSE_LORD
    text = rng.choice(lines) % _pack(hold, region)
    return ("%s: начало" % hold.name, text)


# ---------------------------------------------------------------------------
# Что оно делает с землёй
# ---------------------------------------------------------------------------

LAND_LINES = (
    "Земля по имени %(land)s меняется под хозяином: %(mark)s. Через "
    "поколение это перестают замечать, через три — перестают "
    "объяснять.",
    "В земле по имени %(land)s появляется то, чего там не было: "
    "%(mark)s.",
    "%(mark_cap)s — вот что остаётся в земле по имени %(land)s от того, "
    "что ею владеют.",
)


def land_changed(rng, hold, region, mark: str) -> tuple:
    pack = _pack(hold, region, mark=mark, mark_cap=cap(mark))
    return ("%s: %s" % (hold.name, mark), rng.choice(LAND_LINES) % pack)


TOOK_LINES = (
    "%(named_cap)s прибавляет землю по имени %(land)s: держать её было "
    "некому.",
    "Земля по имени %(land)s отходит под %(named)s. Спросить об этом "
    "было не у кого.",
    "%(who_cap)s расходится вширь: теперь под ним и земля по имени "
    "%(land)s.",
)


def took_land(rng, hold, region) -> tuple:
    pack = _pack(hold, region)
    return ("%s: ещё одна земля" % hold.name, rng.choice(TOOK_LINES) % pack)


# ---------------------------------------------------------------------------
# Те, кто под ним
# ---------------------------------------------------------------------------

RISING_LINES = (
    "Под %(named_by)s поднимаются: %(folk)s %(way)s. Кончается это "
    "так — %(end)s: %(end_about)s.",
    "%(folk_cap)s, живущие под %(named_by)s, %(way)s. %(end_cap)s: "
    "%(end_about)s.",
    "Терпеть перестают: %(folk)s %(way)s. %(end_cap)s.",
)


def rising(rng, hold, who: dict, way: str, end: str) -> tuple:
    from . import races as races_mod
    race = races_mod.get_race(who.get("раса", ""))
    name = race.name if race is not None else "жители"
    way_word, _about = cat.RESIST_BY_KEY.get(way, ("поднимаются", ""))
    end_word, end_about = cat.RESIST_ENDS_BY_KEY.get(end, ("кончается", ""))
    pack = _pack(hold, None, folk=name, folk_cap=cap(name),
                 way=way_word, end=end_word, end_cap=cap(end_word),
                 end_about=end_about)
    return ("%s: поднялись" % hold.name, rng.choice(RISING_LINES) % pack)


# ---------------------------------------------------------------------------
# Соседи
# ---------------------------------------------------------------------------

WAR_LINES = (
    "Держава по имени %(foe)s идёт на %(named_acc)s. %(out_cap)s.",
    "С %(named_by)s воюет держава по имени %(foe)s. %(out_cap)s.",
    "Соседи решают, что терпеть больше нельзя: держава по имени %(foe)s "
    "собирает войско. %(out_cap)s.",
)


def war_came(rng, hold, foe, out: str) -> tuple:
    pack = _pack(hold, None, foe=foe.full_name, out=out, out_cap=cap(out),
                 named_acc=named(hold))
    return ("%s: война" % hold.name, rng.choice(WAR_LINES) % pack)


CRISIS_LINES = (
    "У %(named_of)s перебои с тем, чем оно живо: %(need)s. %(risk_cap)s.",
    "То, на чём всё держалось, кончается: %(need)s. %(risk_cap)s.",
)


def crisis(rng, hold, need_row) -> tuple:
    word, about, risk = need_row
    pack = _pack(hold, None, need=word, need_about=about,
                 risk=risk, risk_cap=cap(risk))
    return ("%s: нехватка" % hold.name, rng.choice(CRISIS_LINES) % pack)


# ---------------------------------------------------------------------------
# Конец и возвращение
# ---------------------------------------------------------------------------

END_LINES = (
    "%(named_of_cap)s больше нет: %(end)s — %(how)s.",
    "Тому, что звалось %(name)s, приходит конец: %(end)s. %(how_cap)s.",
    "%(end_cap)s, и на этом %(named)s кончается. %(how_cap)s.",
)


def ended(rng, hold) -> tuple:
    word, about = cat.ENDS_BY_KEY.get(hold.end, ("кончилось", ""))
    how = hold.end_how or about
    pack = _pack(hold, None, end=word, end_cap=cap(word),
                 how=how, how_cap=cap(how))
    return ("%s: конец" % hold.name, rng.choice(END_LINES) % pack)


RETURN_LINES = (
    "%(named_cap)s возвращается — то же самое, а не похожее: %(how)s.",
    "То, что считали кончившимся, оказывается на месте: %(name)s. "
    "%(how_cap)s.",
)


def returned(rng, hold) -> tuple:
    how = "печать держала не вечно"
    pack = _pack(hold, None, how=how, how_cap=cap(how))
    return ("%s: вернулось" % hold.name, rng.choice(RETURN_LINES) % pack)


# ---------------------------------------------------------------------------
# Пять голосов
# ---------------------------------------------------------------------------

VOICE_LINES = {
    cat.VOICE_LORD: (
        "эта земля его по праву, и спорить тут не о чем",
        "он не брал ничего, что не было бы ему должно",
    ),
    cat.VOICE_FOLK: (
        "жить можно, если не перечить",
        "при дедах было хуже, а при прадедах лучше",
        "платим и живём, а за межой тоже не сахар",
    ),
    cat.VOICE_NEIGHBOUR: (
        "туда не ходят, и правильно делают",
        "пока платят — не трогает, а это уже порядок",
        "рано или поздно придётся собираться и идти",
    ),
    cat.VOICE_FLED: (
        "рассказывают такое, что верят через раз",
        "говорят, половина сказанного — правда, и этого довольно",
    ),
    cat.VOICE_FAITH: (
        "это кара, и послана она не ему, а нам",
        "служить ему грех, а платить ему — необходимость",
    ),
    cat.VOICE_LATER: (
        "в своды это вошло короче, чем было",
        "поздние списки путают его с тем, что было до него",
    ),
}


def voice_said(rng, hold, voice: str) -> str:
    lines = VOICE_LINES.get(voice) or VOICE_LINES[cat.VOICE_NEIGHBOUR]
    return rng.choice(list(lines))


# ---------------------------------------------------------------------------
# Строки для разделов и карточек
# ---------------------------------------------------------------------------


def head_line(hold) -> str:
    """Заголовок: имя, что это и кто хозяин."""
    word = cat.kind_word(hold.kind)
    if hold.lord_name and hold.kind not in cat.LORDLESS:
        return "%s — %s, хозяин %s по имени %s" \
            % (hold.name, word, hold.lord_word or "хозяин", hold.lord_name)
    return "%s — %s" % (hold.name, word)


def hold_line(hold) -> str:
    """Чем держит и насколько крепко — или держал, если его уже нет."""
    said = cat.control_word(hold.control)
    firm = hold.strength
    if firm >= 0.7:
        how = ("держится крепко", "держалось крепко")
    elif firm >= 0.45:
        how = ("держится", "держалось")
    elif firm >= 0.25:
        how = ("держится через раз", "держалось через раз")
    else:
        how = ("держится едва", "держалось едва")
    return "%s; %s" % (said, how[0] if hold.alive else how[1])


def folk_line(world, row: dict) -> str:
    """Одна строка о подчинённой группе: кто, сколько, чем стал и как к этому."""
    from . import races as races_mod
    from .narrative_calamity import number
    race = races_mod.get_race(row.get("раса", ""))
    name = race.name if race is not None else "жители"
    said = cat.standing_word(row.get("как", ""))
    feel = cat.FEELINGS_BY_KEY.get(row.get("чувство", ""), ("", ""))[0]
    souls = int(row.get("душ", 0))
    line = "%s — %s" % (cap(name), said)
    if souls:
        line += ", душ %s" % number(souls)
    if feel:
        line += "; %s" % feel
    return line


def edict_line(row: dict) -> str:
    return "%s — %s (%s)" % (row.get("что", ""), row.get("отчего", ""),
                             row.get("кара", ""))


def tribute_line(hold) -> str:
    if not hold.tribute:
        return ""
    said = cat.tribute_word(hold.tribute)
    about = hold.tribute_why or cat.tribute_about(hold.tribute)
    ways = [cat.RULE_WAYS_BY_KEY[key][0] for key in hold.ways
            if key in cat.RULE_WAYS_BY_KEY]
    line = "платят %s" % said
    if about:
        line += ", %s" % about
    if ways:
        line += "; держат это: %s" % ", ".join(ways)
    return line


def need_line(hold) -> str:
    row = cat.NEEDS_BY_KEY.get(hold.need)
    if row is None:
        return ""
    word, about, risk = row
    return "%s — %s; %s" % (word, about, risk)


def tolerated_line(hold) -> str:
    said = cat.TOLERATED_BY_KEY.get(hold.tolerated, "")
    return said


def truth_line(hold) -> str:
    """Чего о нём не знают — и как на самом деле."""
    if not hold.lie:
        return ""
    word, truth = cat.LIES_BY_KEY.get(hold.lie, ("", ""))
    return "%s, а %s" % (word, truth)


def mark_line(row: dict) -> str:
    return "%d год — %s: %s" % (int(row.get("год", 0)), row.get("что", ""),
                                row.get("отчего", ""))


def rising_line(world, row: dict) -> str:
    """«1720 год — высшие эльфы убивают надсмотрщиков, и их раздавили».

    Одного глагола мало: «убивают» без того, кого именно, читается как
    обрывок. Поэтому к способу идёт его же пояснение, а к исходу —
    союз, иначе строка распадается на два слова через двоеточие.
    """
    from . import races as races_mod
    race = races_mod.get_race(row.get("кто", ""))
    name = race.name if race is not None else "жители"
    way, way_about = cat.RESIST_BY_KEY.get(row.get("как", ""), ("", ""))
    end, _about = cat.RESIST_ENDS_BY_KEY.get(row.get("чем", ""), ("", ""))
    said = "%s — %s" % (way, way_about) if way_about else way
    return "%d год — %s %s, и это %s" \
        % (int(row.get("год", 0)), name.lower(), said, end)


def war_line(world, row: dict) -> str:
    polity = world.polities.get(row.get("с кем", ""))
    name = polity.full_name if polity is not None else "кто-то из соседей"
    return "%d год — держава по имени %s: %s" \
        % (int(row.get("год", 0)), name, row.get("чем", ""))


def voice_line(voice: str, said: str) -> str:
    return "%s: %s" % (voice, said)


__all__ = ["named", "said_of", "pair", "rose", "land_changed", "took_land",
           "rising", "war_came", "crisis", "ended", "returned", "voice_said",
           "head_line", "hold_line", "folk_line", "edict_line",
           "tribute_line", "need_line", "tolerated_line", "truth_line",
           "mark_line", "rising_line", "war_line", "voice_line"]
