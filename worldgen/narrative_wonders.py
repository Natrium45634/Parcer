# -*- coding: utf-8 -*-
"""Тексты о чудесах света: как их заметили, прославили и потеряли.

Правила прежние: имена собственные в именительном падеже и в текст
ставятся оборотами, прилагательные подставляются парами, глаголы — в
настоящем времени третьего лица.

Отдельная забота тут — не хвалить. Чудо не нуждается в том, чтобы
летопись объявляла его великим: она называет, за что его так зовут, и
этого довольно. Восторг — дело тех, кто туда дошёл.
"""

from __future__ import annotations

from . import wonders as cat
from .narrative import cap
from .timeline import plural


def _word_of(wonder) -> str:
    return (cat.SHAPES_BY_KEY.get(wonder.shape).word
            if wonder.shape in cat.SHAPES_BY_KEY else "место")


def _self_named(wonder) -> bool:
    """Несёт ли имя само слово облика: «Вечная Твердыня» у твердыни."""
    head = _word_of(wonder).split(",")[0].split()[0].lower()
    return head in [part.lower().strip(",") for part in wonder.name.split()]


def said_of(wonder) -> str:
    """«гора по имени X» — для косвенных падежей.

    Если имя уже содержит слово облика, оборот не нужен: «твердыня по
    имени Вечная Твердыня» — это не имя, а заикание.
    """
    if _self_named(wonder):
        return wonder.name
    word = _word_of(wonder)
    # «место, где всё не так по имени X» — оборот надо отделить запятой,
    # иначе он прилипает к придаточному внутри самого слова.
    glue = ", по имени %s" if "," in word else " по имени %s"
    return word + glue % wonder.name


_of = said_of


def pair(gender: str, male: str, female: str, neuter: str) -> str:
    if gender == "f":
        return female
    if gender == "n":
        return neuter
    return male


def _gender(wonder) -> str:
    shape = cat.SHAPES_BY_KEY.get(wonder.shape)
    return shape.gender if shape is not None else "n"


def _forms(wonder) -> dict:
    """Согласование с родом чуда: гора стояла, мост стоял, озеро стояло.

    Подлежащее во всех оборотах — слово облика («гора по имени X»), и
    род у фразы его, а не имени. Поэтому все глаголы и местоимения,
    какие встречаются в шаблонах, собраны тут одним набором.
    """
    gender = _gender(wonder)

    def take(male, female, neuter):
        return pair(gender, male, female, neuter)

    return {
        "it": take("его", "её", "его"),
        "it_of": take("его", "её", "его"),
        "in_it": take("в нём", "в ней", "в нём"),
        "about": take("о нём", "о ней", "о нём"),
        "at_it": take("при нём", "при ней", "при нём"),
        "it_in": take("ним", "ней", "ним"),
        "he": take("он", "она", "оно"),
        "he_cap": take("Он", "Она", "Оно"),
        "self": take("сам он", "сама она", "само оно"),
        "stood": take("стоял", "стояла", "стояло"),
        "held": take("устоял", "устояла", "устояло"),
        "done": take("достроен", "достроена", "достроено"),
        "whole": take("цел", "цела", "цело"),
        "whole_in": take("целым", "целой", "целым"),
        "such": take("таким", "такой", "таким"),
        "was": take("каким он был", "какой она была", "каким оно было"),
    }


# ---------------------------------------------------------------------------
# Как его заметили
# ---------------------------------------------------------------------------

FOUND_NATURAL = (
    "%(who)s %(stood)s тут прежде всех, кто %(about)s говорит, но чудом "
    "%(it)s назвали только теперь: %(why)s.",
    "Мир замечает то, что было при нём всегда: %(who)s. Зовут %(it)s "
    "чудом %(ground)s — %(why)s.",
    "О месте этом знали и раньше, а имя ему дали в этот год: %(who)s. "
    "%(why_cap)s.",
)

FOUND_BUILT = (
    "В земле по имени %(land)s кончают то, что начинали не для славы: "
    "%(who)s. %(why_cap)s.",
    "%(who_cap)s %(done)s. %(motive_cap)s — так это объясняли тогда, и "
    "так записали. %(why_cap)s.",
    "То, что строили %(years)s, наконец стоит: %(who)s. %(why_cap)s.",
)

FOUND_MAGIC = (
    "%(who_cap)s — и объяснить его нечем: %(why)s.",
    "В этот год мир получает то, чего в нём не было и чего он не просил: "
    "%(who)s. %(why_cap)s.",
)


def found(rng, wonder, region, years: int = 0) -> tuple:
    shape = cat.SHAPES_BY_KEY.get(wonder.shape)
    kind = shape.kind if shape is not None else cat.NATURAL
    said = _of(wonder)
    motive = cat.MOTIVES_BY_KEY.get(wonder.motive, ("", ""))[0]
    pack = dict(_forms(wonder))
    pack.update({
        "who": said, "who_cap": cap(said),
        "ground": cat.ground_name(wonder.ground),
        "why": wonder.measure or cat.ground_about(wonder.ground),
        "why_cap": cap(wonder.measure or cat.ground_about(wonder.ground)),
        "land": region.name if region is not None else "безымянной",
        "motive_cap": cap(motive) if motive else "Так было надо",
        "years": "%d лет" % years if years else "дольше, чем помнят",
    })
    if kind in (cat.BUILT, cat.MIXED):
        text = rng.choice(FOUND_BUILT) % pack
    elif kind in (cat.MAGICAL, cat.DIVINE):
        text = rng.choice(FOUND_MAGIC) % pack
    else:
        text = rng.choice(FOUND_NATURAL) % pack
    return ("Чудо света: %s" % wonder.name, text)


# ---------------------------------------------------------------------------
# Слава
# ---------------------------------------------------------------------------

FAME_UP = (
    "О месте, что зовут %(name)s, узнают дальше прежнего: теперь "
    "%(about)s %(now)s.",
    "Слава %(name)s растёт — не делами, а рассказами тех, кто дошёл: "
    "теперь %(about)s %(now)s.",
    "Про %(name)s начинают спрашивать там, где прежде %(about)s не "
    "слыхали. Теперь %(about)s %(now)s.",
)

FAME_DOWN = (
    "О месте, что звалось %(name)s, говорят всё реже: теперь %(about)s "
    "%(now)s.",
    "Дорога к %(name)s заросла, и вместе с дорогой ушли рассказы: теперь "
    "%(about)s %(now)s.",
    "%(name)s уходит из людской памяти не разом, а так, как уходит "
    "всё: теперь %(about)s %(now)s.",
)


def fame_moved(rng, wonder, up: bool) -> tuple:
    forms = _forms(wonder)
    pack = dict(forms)
    pack.update({"name": wonder.name, "now": cat.fame_word(wonder.fame)})
    text = rng.choice(FAME_UP if up else FAME_DOWN) % pack
    head = "%s говорят" % forms["about"] if up \
        else "%s забывают" % forms["about"]
    return ("%s: %s" % (wonder.name, head), text)


# ---------------------------------------------------------------------------
# Что с ним стало
# ---------------------------------------------------------------------------

STATE_LINES = {
    cat.STANDS: ("%(who_cap)s снова %(whole)s: %(why)s.",
                 "О %(name)s говорят, что %(he)s оправилось: %(why)s."),
    cat.HURT: ("%(who_cap)s стоит, но уже не %(whole_in)s: %(why)s.",
               "С %(name)s случилось то, что рано или поздно случается со "
               "всем: %(why)s. %(he_cap)s стоит, но половина %(it_of)s "
               "теперь — рассказ."),
    cat.RUINS: ("От %(name)s остались стены: %(why)s.",
                "%(who_cap)s не %(held)s: %(why)s. Теперь туда ходят за "
                "камнем."),
    cat.GONE: ("%(who_cap)s кончается совсем: %(why)s. Место это "
               "остаётся, а чуда на нём больше нет.",
               "%(name)s больше нет: %(why)s."),
    cat.SUNK: ("%(who_cap)s уходит под воду: %(why)s.",
               "Воды поднимаются и берут %(name)s — целиком и сразу: "
               "%(why)s."),
    cat.BURIED: ("%(who_cap)s заносит так, что через век %(it)s ищут и не "
                 "находят: %(why)s.",
                 "%(name)s скрывается под землёй: %(why)s."),
    cat.LEFT: ("%(who_cap)s %(whole)s, а людей %(at_it)s больше нет: "
               "%(why)s.",
               "От %(name)s уходят: %(why)s. %(self)s стоит."),
    cat.SEALED: ("%(who_cap)s запирают, и ключа после этого не находят: "
                 "%(why)s.",
                 "%(name)s закрывают — и закрывают так, что открывать "
                 "больше нечем: %(why)s."),
    cat.FORGOT: ("О %(name)s перестают помнить, хотя %(he)s стоит: "
                 "%(why)s.",
                 "%(who_cap)s остаётся, а память %(about)s — нет: %(why)s."),
    cat.FOUND: ("%(who_cap)s находят снова — через столько лет, что "
                "сперва не верят: %(why)s.",
                "То, что считалось потерянным, стоит на месте: %(name)s. "
                "%(why_cap)s."),
    cat.FIXED: ("%(who_cap)s поднимают заново: %(why)s.",
                "%(name)s восстанавливают — не %(such)s, %(was)s, но "
                "и это немало: %(why)s."),
}


def state_moved(rng, wonder, why: str) -> tuple:
    lines = STATE_LINES.get(wonder.state) or STATE_LINES[cat.HURT]
    said = _of(wonder)
    pack = dict(_forms(wonder))
    pack.update({"who": said, "who_cap": cap(said), "name": wonder.name,
                 "why": why, "why_cap": cap(why)})
    text = rng.choice(lines) % pack
    return ("%s: %s" % (wonder.name, wonder.state), text)


# ---------------------------------------------------------------------------
# Ложное чудо
# ---------------------------------------------------------------------------

FALSE_LINES = (
    "С %(name)s выходит неловкость: те, кто дошёл и посмотрел, говорят, "
    "что чуда там нет и не было. Спорить с ними, впрочем, некому — до "
    "тех пор, пока не дойдёт кто-нибудь ещё.",
    "О %(name)s начинают говорить иначе: будто бы всё это придумали "
    "сами, и придумали с умыслом. Тех, кто говорит так, в тех краях не "
    "любят.",
    "%(name_cap)s оказывается не тем, чем %(it)s звали: %(truth)s. Имя "
    "за %(it_in)s, однако, остаётся — имена держатся дольше оснований.",
)


def false_wonder(rng, wonder) -> tuple:
    forms = _forms(wonder)
    pack = dict(forms)
    pack.update({
        "name": wonder.name, "name_cap": cap(wonder.name),
        "truth": wonder.truth
        or "за %s не стоит ничего" % forms["it_in"]})
    text = rng.choice(FALSE_LINES) % pack
    return ("%s: чудо ли это" % wonder.name, text)


# ---------------------------------------------------------------------------
# Списки чудес
# ---------------------------------------------------------------------------

# Оборот о составителе приходит готовым («в державе по имени X», «у
# народа по имени X»): державы и народы считают чудеса по-разному, и
# подставлять тут слово «держава» нельзя.
LIST_LINES = (
    "%(where_cap)s составляют список того, чем эта земля стоит перед "
    "прочими: %(name)s. Вошло в него %(count_said)s, и выбирали %(why)s.",
    "%(name_cap)s — так называют то, что %(where)s сочли достойным "
    "счёта. В списке %(count_said)s; про всё прочее сказано, что оно не "
    "хуже, но считать надо было где-то остановиться.",
    "Появляется счёт чудесам: %(name)s. Считали %(why)s, насчитали "
    "%(count_said)s, и спор об этом списке переживёт всех, кто его "
    "составлял.",
)

LIST_WHYS = (
    "по тому, чем гордятся",
    "по тому, что показывают чужим послам",
    "по тому, о чём чаще поют",
    "по тому, что дальше всего видно",
    "по тому, что пережило больше всех",
)


def wonder_list(rng, name: str, where: str, count: int, why: str) -> tuple:
    """Текст о списке чудес. `where` — готовый оборот о составителе."""
    said = "%d %s" % (count, plural(count, "чудо", "чуда", "чудес"))
    text = rng.choice(LIST_LINES) % {
        "name": name, "name_cap": cap(name), "where": where,
        "where_cap": cap(where), "count_said": said, "why": why}
    return (name, text)


# ---------------------------------------------------------------------------
# Строки для карточек и разделов
# ---------------------------------------------------------------------------


def head_line(wonder) -> str:
    """Заголовок: имя, что это и за что его зовут чудом.

    У имени, которое уже называет себя («Старый Водопад»), слово облика
    не повторяется: иначе выходит «Старый Водопад — водопад».
    """
    if _self_named(wonder):
        return "%s — чудо %s" % (wonder.name,
                                 cat.ground_name(wonder.ground))
    return "%s — %s, %s" % (wonder.name, _word_of(wonder),
                            cat.ground_name(wonder.ground))


def fame_line(wonder) -> str:
    said = "%s %s" % (_forms(wonder)["about"], cat.fame_word(wonder.fame))
    if wonder.peak_fame > wonder.fame:
        said += "; прежде знали дальше — %s" \
            % cat.fame_word(wonder.peak_fame)
    return said


def state_since(wonder) -> int:
    """С какого года оно в нынешнем состоянии.

    Последняя отметка не годится: отметки есть и о дороге, и о споре, а
    спрашивают именно про состояние.
    """
    for mark in reversed(wonder.marks):
        if mark.get("что") in cat.STATES_BY_KEY:
            return int(mark.get("год", wonder.born.year))
    return wonder.born.year


def access_line(wonder) -> str:
    """Дойти ли туда — и если нет, то отчего именно."""
    name, about = cat.ACCESS_BY_KEY.get(wonder.access,
                                        ("дойти можно", ""))
    said = "%s — %s" % (name, about) if about else name
    if wonder.access_why:
        said += "; %s" % wonder.access_why
    return said


def made_line(world, wonder) -> str:
    """Кто и зачем — одной строкой, если это рукотворное."""
    polity = world.polities.get(wonder.polity_id)
    figure = world.figures.get(wonder.figure_id)
    motive = cat.MOTIVES_BY_KEY.get(wonder.motive, ("", ""))[0]
    said = []
    if polity is not None:
        said.append("построила держава по имени %s" % polity.full_name)
    if figure is not None:
        said.append("по воле того, кого звали %s" % figure.name)
    if motive:
        said.append(motive)
    cost = cat.COSTS_BY_KEY.get(wonder.cost)
    if cost:
        said.append("а стоило это %s: %s" % (cost[0], cost[1]))
    return "; ".join(said)


def mark_line(mark: dict) -> str:
    return "%d год — %s: %s" % (int(mark.get("год", 0)),
                                mark.get("что", ""),
                                mark.get("отчего", ""))


def voice_line(row: dict) -> str:
    name, _about = cat.VOICES_BY_KEY.get(row.get("чей", ""), ("", ""))
    return "%s: %s" % (name or "где-то", row.get("что", ""))


__all__ = ["said_of", "found", "fame_moved", "state_moved", "false_wonder",
           "wonder_list", "head_line", "fame_line", "access_line",
           "state_since",
           "made_line", "mark_line", "voice_line", "pair"]
