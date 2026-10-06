# -*- coding: utf-8 -*-
"""Тексты о видах существ: откуда взялись, поумнели, одичали, развелись.

Правила прежние: сгенерированные имена стоят в именительном падеже,
косвенные падежи берутся готовыми оборотами («вид по имени X» тут не
нужен — у вида имя нарицательное), глаголы — в настоящем времени
третьего лица.

Тут важнее обычного не сорваться в справочник. «Гоблины неразумны» —
это графа. «Гоблины перестали говорить в 2140 году, после того как мор
выел им память, и к нынешнему дню помнят только, что когда-то у них
были слова» — это история.
"""

from __future__ import annotations

from . import creatures as cr
from .narrative import cap
from .timeline import plural


# ---------------------------------------------------------------------------
# Появление вида
# ---------------------------------------------------------------------------

BORN_TEMPLATES = (
    "%(who)s в этом мире %(origin)s: %(about)s.",
    "О том, откуда взялись %(who_low)s, говорят так: %(origin)s — "
    "%(about)s.",
    "%(who)s — не из тех, кто был тут всегда. Они %(origin)s. "
    "%(about_cap)s.",
    "Начало этого рода известно: %(who_low)s %(origin)s. %(about_cap)s.",
)

# Строка о том, кто за этим стоит, идёт следом за пояснением — и потому
# не повторяет его, а только называет имя.
MAKER_LINES = {
    "god_made": "Имя тому, кто их сделал, — %(maker)s.",
    "god_blood": "Кровь та была кровью того, кого звали %(maker)s.",
    "beast_made": "Вывел их %(maker)s.",
    "elder_kin": "Первородного того звали %(maker)s.",
    "fallen_god": "Звали его тогда %(maker)s.",
}


def species_born(rng, kin, maker_name: str = "") -> tuple:
    name, about = cr.ORIGINS_BY_KEY.get(kin.origin, ("неизвестно откуда", ""))
    # «Не из тех, кто был тут всегда» не говорят о тех, кто как раз был
    # тут всегда: оборот и пояснение спорили бы в одной фразе.
    shapes = BORN_TEMPLATES
    if kin.origin == "natural":
        shapes = tuple(row for row in BORN_TEMPLATES
                       if "кто был тут всегда" not in row)
    text = rng.choice(shapes) % {
        "who": kin.name, "who_low": kin.name.lower(),
        "origin": name, "about": about, "about_cap": cap(about),
    }
    line = MAKER_LINES.get(kin.origin, "")
    if line and maker_name:
        text += " " + line % {"maker": maker_name}
    return "Откуда взялись %s" % kin.name.lower(), text


# ---------------------------------------------------------------------------
# Разумность: обрели и потеряли
# ---------------------------------------------------------------------------

RISE_TEMPLATES = (
    "%(who)s перестают быть зверьём: %(why)s. С этого года у них есть то, "
    "чего не было, — %(gain)s.",
    "То, что случилось с этим родом, мир сперва не заметил: %(why)s. "
    "Заметил он позже, когда %(who_low)s заговорили.",
    "%(who)s были тем, на что охотятся. С этого года они — те, с кем "
    "договариваются: %(why)s.",
    "Про этот год потом скажут, что с него и началась их история: "
    "%(why)s. %(gain_cap)s — вот что они получили.",
)

FALL_TEMPLATES = (
    "%(who)s теряют то, что имели: %(why)s. Остаётся повадка, но не "
    "память о том, откуда она.",
    "Род этот был народом. С этого года он — не народ: %(why)s.",
    "%(who)s замолкают. Не разом — за три поколения, — но замолкают "
    "совсем: %(why)s.",
    "Города их стоят пустыми, а они сами никуда не делись: %(why)s. "
    "Теперь в этих городах живут они же, но строить такие больше не "
    "умеют.",
)

GAINS = {
    cr.PACK: "разум на всю стаю",
    cr.LIMITED: "вожди, стойбища и понимание чужой речи",
    cr.SENTIENT: "язык, вера и память о своих предках",
    cr.HIGH: "письмо и счёт поколений",
}


def mind_rise(rng, kin, why_key: str) -> tuple:
    about, _short = cr.RISE_BY_KEY.get(why_key, ("это случилось", ""))
    gain = GAINS.get(kin.mind, "то, чего у них не было")
    text = rng.choice(RISE_TEMPLATES) % {
        "who": kin.name, "who_low": kin.name.lower(),
        "why": about, "gain": gain, "gain_cap": cap(gain),
    }
    return "%s обретают разум" % kin.name, text


def mind_fall(rng, kin, why_key: str) -> tuple:
    about, _short = cr.FALL_BY_KEY.get(why_key, ("это случилось", ""))
    text = rng.choice(FALL_TEMPLATES) % {
        "who": kin.name, "who_low": kin.name.lower(), "why": about,
    }
    return "%s теряют разум" % kin.name, text


# ---------------------------------------------------------------------------
# Разновидности
# ---------------------------------------------------------------------------

VARIANT_TEMPLATES = (
    "В земле по имени %(region)s у этого рода заводится своя ветвь: "
    "%(name)s. Причина названа — %(why)s.",
    "%(name)s — то же самое и уже не то же: %(why)s. Отличить их от "
    "прочих можно с одного взгляда, и те, кто живёт рядом, отличают.",
    "Мир узнаёт, что %(who_low)s бывают разные: в земле по имени "
    "%(region)s видели тех, кого зовут теперь %(name)s. Причиной тому "
    "называют %(why)s.",
    "То, что вышло в земле по имени %(region)s, сперва считали уродством "
    "одного выводка. Через два поколения стало ясно, что это ветвь — "
    "%(name)s, — и что причина ей %(why)s.",
)


def variant_born(rng, kin, name: str, why: str, region) -> tuple:
    text = rng.choice(VARIANT_TEMPLATES) % {
        "name": name, "who_low": kin.name.lower(), "why": why,
        "why_cap": cap(why),
        "region": region.name if region is not None else "безымянной",
    }
    return "Новая ветвь: %s" % name, text


# ---------------------------------------------------------------------------
# Ступень особи
# ---------------------------------------------------------------------------

TIER_TEMPLATES = (
    "То, что живёт в земле по имени %(region)s, перестало быть тем, чем "
    "было: теперь это %(rank)s. %(why_cap)s.",
    "Про %(name)s больше не говорят по-старому. Говорят — %(rank)s, и "
    "говорят с оглядкой. %(why_cap)s.",
    "%(name)s берёт свою новую меру: %(rank)s. %(why_cap)s.",
)

GREAT_TEMPLATES = (
    "%(name)s переходит ту черту, за которой чудовище становится силой "
    "мира: это %(rank)s. %(why_cap)s. Державы, у которых хватает ума, "
    "считают %(its)s теперь не бедой, а соседом.",
    "Мир получает ещё одну силу, с которой считаются, и сила эта — не "
    "человек: %(name)s, %(rank)s. %(why_cap)s. С этого года земля под "
    "%(by_it)s меняется, а не терпит.",
    "О том, что %(name)s %(became)s тем, чем %(became)s, узнают по тому, "
    "что перестают ходить дорогой мимо. %(rank_cap)s — такое в мире не "
    "каждый век. %(why_cap)s.",
)


def pair(gender: str, male: str, female: str) -> str:
    """Слово в роде существа: род у твари свой, и «стал» ей не всегда впору."""
    return female if gender == "f" else male


def tier_grew(rng, monster, kin, region, tier: int, why: str) -> tuple:
    rank = cr.tier_word(kin, tier)
    gender = getattr(monster, "gender", "m")
    pack = {"name": monster.name, "rank": rank, "rank_cap": cap(rank),
            "why_cap": cap(why), "why": why,
            "its": pair(gender, "его", "её"),
            "by_it": pair(gender, "ним", "ней"),
            "became": pair(gender, "стал", "стала"),
            "region": region.name if region is not None else "безымянной"}
    if tier >= cr.TIER_GREAT:
        return ("%s: %s" % (monster.name, rank),
                rng.choice(GREAT_TEMPLATES) % pack)
    return ("%s теперь %s" % (monster.name, rank),
            rng.choice(TIER_TEMPLATES) % pack)


# ---------------------------------------------------------------------------
# Вид ушёл и вернулся
# ---------------------------------------------------------------------------

GONE_TEMPLATES = (
    "%(who)s в этом мире больше не встречаются: %(why)s. Последних "
    "видели в земле по имени %(region)s.",
    "Их не стало тихо: %(why)s. Мир заметил это не сразу и записал "
    "задним числом — %(who_low)s вывелись.",
    "%(who)s кончились. %(why_cap)s, и охотиться стало не на кого.",
)

BACK_TEMPLATES = (
    "%(who)s объявляются снова — там, где их не искали, в земле по имени "
    "%(region)s. Кто-то пережил всё это в глуши, и теперь их опять "
    "столько, что видно.",
    "То, что считалось выведенным, выходит обратно: %(who_low)s. "
    "Выходит оттуда, куда никто не ходил, — и за то время, пока их не "
    "было, они переменились.",
    "Мир привык, что %(who_low)s — дело прошлое. Привычку приходится "
    "менять.",
)


def species_gone(rng, kin, why: str, region) -> tuple:
    text = rng.choice(GONE_TEMPLATES) % {
        "who": kin.name, "who_low": kin.name.lower(), "why": why,
        "why_cap": cap(why),
        "region": region.name if region is not None else "безымянной"}
    return "%s выводятся" % kin.name, text


def species_back(rng, kin, region) -> tuple:
    text = rng.choice(BACK_TEMPLATES) % {
        "who": kin.name, "who_low": kin.name.lower(),
        "region": region.name if region is not None else "безымянной"}
    return "%s возвращаются" % kin.name, text


# ---------------------------------------------------------------------------
# Строки для летописи и карточек
# ---------------------------------------------------------------------------


def mind_line(kin) -> str:
    """Одна строка о разумности: где стоит и откуда пришёл."""
    mind = cr.mind_of(kin.mind)
    line = "%s — %s" % (cap(mind.name), mind.about)
    if kin.mind != kin.base_mind:
        was = cr.mind_of(kin.base_mind)
        line += " (а были %s)" % was.name
    return line


def nature_lines(kin) -> list:
    """Природа вида: чем кормится, как плодится, как держится, сколько живёт."""
    social_name, social_about = cr.SOCIALS_BY_KEY.get(
        kin.social, ("сами по себе", ""))
    rows = ["кормится: %s" % kin.diet,
            "плодится: %s" % kin.breeding,
            "держится %s — %s" % (social_name, social_about)]
    if kin.years:
        # «Около 41 лет» — не по-русски, а веков у видов бывает всякий:
        # и 41 год, и 2 года, и 3240 лет.
        rows.append("живёт около %s" % plural(kin.years,
                                              "%d года" % kin.years,
                                              "%d лет" % kin.years,
                                              "%d лет" % kin.years))
    rarity, about, _named, _cap = cr.RARITIES_BY_KEY.get(
        kin.rarity, cr.RARITIES_BY_KEY["common"])
    rows.append("редкость: %s — %s" % (rarity, about))
    return rows


def mark_line(mark: dict) -> str:
    """Переход разумности строкой: год, куда и отчего."""
    year = int(mark.get("год", 0))
    where = cr.mind_of(mark.get("стало", cr.BEASTLY)).name
    why = mark.get("отчего", "")
    return "%d год — стали %s: %s" % (year, where, why)


def variant_line(row: dict) -> str:
    kind_name, _about = cr.VARIANT_KINDS_BY_KEY.get(
        row.get("род", ""), ("", ""))
    where = row.get("земля", "")
    line = "%s (%s, с %d года)" % (row.get("имя", ""), kind_name,
                                   int(row.get("год", 0)))
    if where:
        line += " — %s" % where
    return line


def power_line(source: str, gender: str = "m") -> str:
    name, about, _lift = cr.POWERS_BY_KEY.get(source, ("", "", 1.0))
    if not name:
        return ""
    return "сила %s %s: %s" % (pair(gender, "его", "её"), name, about)


__all__ = ["species_born", "mind_rise", "mind_fall", "variant_born",
           "tier_grew", "species_gone", "species_back", "mind_line",
           "nature_lines", "mark_line", "variant_line", "power_line",
           "pair"]
