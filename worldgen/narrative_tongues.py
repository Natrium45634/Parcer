# -*- coding: utf-8 -*-
"""Тексты о языках: рождение наречий, письменность, заимствования, смерть."""

from __future__ import annotations

from . import tongues as tng
from .narrative import cap
from .timeline import years_text

SPLIT_TEMPLATES = (
    "Речь %(folk_gen)s расходится с речью предков настолько, что толмач "
    "нужен уже и своим: рождается %(name)s.",
    "Купцы с той стороны перестают понимать здешних без переспроса. Так "
    "летописец впервые записывает %(name)s как отдельный язык.",
    "Триста лет врозь делают своё дело: %(name)s больше не наречие, а язык.",
    "Старики ещё помнят, как говорили деды, молодые — уже нет. %(name_cap)s "
    "отделяется окончательно.",
    "Одно и то же слово по обе стороны рубежа звучит по-разному, и обе "
    "стороны считают правым себя. Так появляется %(name)s.",
    "Песни, привезённые с родины, здесь поют с чужим выговором. Имя этому "
    "выговору — %(name)s.",
)

SPLIT_NOTES = (
    "Пример перемены слышен в одном слове: «%(old)s» здесь говорят как "
    "«%(new)s».",
    "Прежнее «%(old)s» стало «%(new)s» — и так со всяким словом.",
    "Там, где предки говорили «%(old)s», теперь говорят «%(new)s».",
    "Писцы двух держав пишут одно имя двояко: «%(old)s» и «%(new)s».",
)


def tongue_split(rng, tongue, parent, folk):
    from . import folk as folk_mod
    data = {
        "name": tongue.name, "name_cap": cap(tongue.name),
        "folk_gen": folk_mod.folk_gen(folk),
        "old": tng.sample(rng, parent.laws if parent is not None else ()),
        "new": tng.sample(rng, tongue.laws),
    }
    body = cap(rng.choice(SPLIT_TEMPLATES) % data)
    if data["old"] != data["new"]:
        body = "%s %s" % (body, rng.choice(SPLIT_NOTES) % data)
    return ("Новый язык: %s" % tongue.name, body)


PROTO_TEMPLATES = (
    "У %(race_gen)s появляется своё слово: %(name)s. На нём поют первые "
    "песни и заключают первые договоры.",
    "Речь %(race_gen)s складывается в язык — %(name)s. Всё, что будет после,"
    " будет сказано на нём или на его потомках.",
    "%(name_cap)s — первый язык этого народа. Имена, которые он даёт, "
    "переживут его самого.",
)


def proto_born(rng, tongue, race):
    data = {"name": tongue.name, "name_cap": cap(tongue.name),
            "race_gen": race.gen_plural}
    return ("Первый язык: %s" % race.name,
            cap(rng.choice(PROTO_TEMPLATES) % data))


SCRIPT_TEMPLATES = (
    "%(folk_cap)s обзаводятся письменностью: %(script)s — %(note)s.",
    "Кто-то догадывается закрепить слово на веществе, и появляется "
    "%(script)s: %(note)s.",
    "Счётные знаки купцов превращаются в письмо. Это %(script)s: %(note)s.",
    "Жрецы заводят %(script)s, чтобы записать то, что нельзя забыть: "
    "%(note)s.",
)

SCRIPT_BORROW = (
    "%(folk_cap)s перенимают письмо у соседей: %(script)s. Вместе с буквами "
    "приходят и чужие слова.",
    "Своего письма так и не изобрели — взяли готовое: %(script)s.",
    "Купцы привозят не только товар: %(script)s приходит с обозами.",
    "Писцы учатся по чужим грамотам, и %(script)s остаётся здесь навсегда.",
)


def script_found(rng, tongue, folk, borrowed_from=None):
    from . import folk as folk_mod
    data = {
        "folk_cap": cap(folk.name), "script": tongue.script,
        "note": tng.SCRIPT_NOTES.get(tongue.script, "писать этим непросто"),
        "folk_gen": folk_mod.folk_gen(folk),
    }
    pool = SCRIPT_BORROW if borrowed_from is not None else SCRIPT_TEMPLATES
    return ("Письменность: %s" % folk.name,
            cap(rng.choice(pool) % data))


BORROW_TEMPLATES = (
    "Торговля приносит в %(name)s чужие слова: счёт, меры и брань — всё "
    "теперь наполовину заёмное.",
    "В %(name)s входят слова соседей, и через век уже никто не помнит, что "
    "они чужие.",
    "Купеческий говор смешивает два языка так, что на рубеже понимают оба.",
    "Слова о море, соли и деньгах в %(name)s все до одного чужие.",
)


def borrowing(rng, tongue, source):
    return ("Заимствования: %s" % tongue.name,
            cap(rng.choice(BORROW_TEMPLATES) % {"name": tongue.name}))


DEAD_TEMPLATES = (
    "На %(name)s больше некому говорить: последние, кто его помнил, умерли.",
    "%(name_cap)s умолкает вместе со своим народом.",
    "Язык уходит раньше, чем земля: на %(name)s не говорят уже нигде.",
    "Завоеватели запрещают чужую речь, и через три поколения запрещать "
    "становится нечего.",
)

SACRED_TEMPLATES = (
    "Говорить на %(name)s перестают, но служить на нём продолжают: язык "
    "остаётся в храме.",
    "%(name_cap)s уходит из дома в храм: на нём теперь только молятся.",
    "Народа не стало, а язык остался — на нём читают свитки, которых никто "
    "уже не понимает до конца.",
    "Жрецы сохраняют мёртвую речь, потому что обряд на другой не годится.",
)


def tongue_dead(rng, tongue, sacred: bool, years: int):
    data = {"name": tongue.name, "name_cap": cap(tongue.name)}
    pool = SACRED_TEMPLATES if sacred else DEAD_TEMPLATES
    return (("Священный язык: %s" if sacred else "Мёртвый язык: %s") % tongue.name,
            "%s Он прожил %s." % (cap(rng.choice(pool) % data),
                                  years_text(max(1, years))))
