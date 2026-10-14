# -*- coding: utf-8 -*-
"""Тексты об обычаях: как летопись рассказывает о заведённом порядке.

Правило тут одно и то же для всех строк: **обычай называется по делу, а
не по народу**. «У дворфов принято чтить камень» — это не запись о
мире, а отговорка; «в Долгом Броде после третьего обвала стали резать
имена погибших на плите у входа» — запись. Поэтому в каждом шаблоне
есть место для того, что делают, и место для того, отчего так делают.

Имена обычаев ставятся через оборот — «обычай «Камень имён»», — и в
косвенных падежах склоняется слово «обычай», а не имя.
"""

from __future__ import annotations

from . import customs as cat


def _cap(line: str) -> str:
    return line[:1].upper() + line[1:] if line else line


def quoted(name: str) -> str:
    return "«%s»" % name


def named(custom, case: str = "им") -> str:
    """«обычай «Камень имён»» в нужном падеже — склоняется только слово."""
    words = {"им": "обычай", "род": "обычая", "дат": "обычаю",
             "вин": "обычай", "твор": "обычаем", "пр": "обычае"}
    return "%s %s" % (words.get(case, "обычай"), quoted(custom.name))


# ---------------------------------------------------------------------------
# Обычай заводится
# ---------------------------------------------------------------------------

BORN_FROM_EVENT = (
    "После того как %(what)s, у народа по имени %(folk)s завёлся порядок: "
    "%(doing)s. Поначалу так делали те, кого это задело; через поколение "
    "так стали делать все.",
    "%(What)s — и в тот же век у народа по имени %(folk)s положили: "
    "%(doing)s. Говорят, первым так сделал тот, кому было хуже всех.",
    "Народ по имени %(folk)s вынес из этого одно правило: %(doing)s. "
    "Случилось это после того, как %(what)s, и спорить тогда не стали.",
)

BORN_FROM_LIFE = (
    "У народа по имени %(folk)s исстари ведётся: %(doing)s. Началось это "
    "не с указа, а оттого, что %(why)s.",
    "В землях народа по имени %(folk)s %(why)s — оттого и порядок: "
    "%(doing)s.",
    "Порядок этот у народа по имени %(folk)s никто не заводил: %(why)s, "
    "а дальше само. Делают так: %(doing)s.",
)

NEED_WORDS = {
    "know": "чтобы умение не ушло с человеком в землю",
    "heir": "чтобы после человека было кому отвечать",
    "calm": "чтобы обида не доросла до крови",
    "ours": "чтобы своего было видно сразу",
    "memory": "чтобы не забыли, чем это кончилось в прошлый раз",
    "adult": "чтобы знать, с кого уже спрашивать как со взрослого",
    "power": "чтобы власть была видна без лишних слов",
    "road": "чтобы путник дошёл живым",
    "goods": "чтобы добро делили без драки",
    "grief": "чтобы у горя был срок",
    "bond": "чтобы две семьи держались друг друга",
    "hands": "чтобы на тяжёлую работу собирались все",
    "fear": "чтобы откупиться от того, чего не понимают",
    "shame": "чтобы у оступившегося была дорога назад",
    "mix": "чтобы пришлого было куда деть",
}


def born(rng, custom, folk_name: str, event_title: str, why_line: str) -> tuple:
    """Как летопись объявляет новый обычай."""
    if event_title:
        shape = rng.choice(BORN_FROM_EVENT)
        what = event_title.rstrip(".").lower()
        text = shape % {"what": what, "What": _cap(what),
                        "folk": folk_name, "doing": custom.doing}
    else:
        shape = rng.choice(BORN_FROM_LIFE)
        text = shape % {"folk": folk_name, "doing": custom.doing,
                        "why": why_line}
    want = NEED_WORDS.get(custom.need, "")
    if want:
        text += " Держится это %s." % want
    return "Обычай: %s" % custom.name, text


# ---------------------------------------------------------------------------
# Обычай расходится
# ---------------------------------------------------------------------------

SPREAD_TEMPLATES = (
    "%(Custom)s перенял народ по имени %(folk)s: %(how)s. Делают его там "
    "на свой лад, и спорить об этом некому.",
    "То, что было порядком одного народа, стало порядком двух: "
    "%(custom)s пришёл к народу по имени %(folk)s — %(how)s.",
    "У народа по имени %(folk)s теперь делают то же: %(custom)s дошёл "
    "сюда — %(how)s.",
)


def spread(rng, custom, folk_name: str, how: str) -> tuple:
    shape = rng.choice(SPREAD_TEMPLATES)
    text = shape % {"custom": named(custom), "Custom": _cap(named(custom)),
                    "folk": folk_name, "how": how}
    return "Обычай разошёлся: %s" % custom.name, text


# ---------------------------------------------------------------------------
# Повороты судьбы
# ---------------------------------------------------------------------------

TURN_TEMPLATES = {
    "hold": (
        "%(Holder)s взял %(custom_vin)s себе: отныне это не обычай, а "
        "требование, и за небрежение спрашивают.",
        "То, что делали по памяти, стало делом обязательным: "
        "%(holder)s закрепил %(custom_vin)s и назначил, кто смотрит за "
        "исполнением.",
    ),
    "reform": (
        "%(Custom_vin)s переделали: суть оставили, порядок сменили — "
        "%(what)s. Старшие ворчат, младшие не помнят, как было.",
        "%(Holder)s поправил %(custom_vin)s: %(what)s. Говорят, так "
        "удобнее; говорят также, что удобнее не тем, кому он служил.",
    ),
    "forbid": (
        "%(Holder)s запретил %(custom_vin)s: %(why)s. Запрет объявили "
        "при людях, и первые годы его держали строго.",
        "%(Custom)s попал под запрет — %(why)s. Делать его стало опасно, "
        "и опасность эту сочли не всякий.",
    ),
    "hide": (
        "Запрет запретом, а %(custom_vin)s делают за закрытой дверью: "
        "коротко, без свидетелей и не называя вслух.",
        "%(Custom)s ушёл в дома: его держат втайне, и знающие узнают друг "
        "друга по мелочи, которую со стороны не разглядеть.",
    ),
    "thin": (
        "От всего порядка осталось одно движение: %(husk)s. Так короче, и "
        "никто уже не помнит, что было прежде.",
        "%(Custom)s усох: %(husk)s. На это ушло меньше века.",
    ),
    "quarrel": (
        "О том, нужен ли %(custom)s, в народе спорят: одни держат его как "
        "держали отцы, другие зовут это пустой тратой дней.",
        "%(Custom)s раскололся не на изводы, а на мнения: половина "
        "соблюдает, половина посмеивается, и обе половины уверены в своём.",
    ),
    "fade": (
        "%(Custom)s перестали делать. Не запрещали и не отменяли — просто "
        "последние, кто помнил порядок, умерли, а спросить стало некого.",
        "О %(custom_pr)s ещё помнят старики, но уже никто не делает: "
        "случай, для которого он был заведён, давно не повторялся.",
    ),
    "revive": (
        "%(Custom)s подняли заново: %(why)s. Вышло похоже на прежнее, но "
        "те, кто помнил прежнее, сказали бы иначе.",
        "Забытое вернули: %(custom)s снова делают — %(why)s.",
    ),
}


def turn(rng, custom, key: str, holder: str = "", why: str = "",
         what: str = "") -> tuple:
    shapes = TURN_TEMPLATES.get(key)
    if not shapes:
        return "Обычай: %s" % custom.name, custom.doing
    shape = rng.choice(shapes)
    text = shape % {
        "custom": named(custom), "Custom": _cap(named(custom)),
        "custom_vin": named(custom, "вин"),
        "Custom_vin": _cap(named(custom, "вин")),
        "custom_pr": named(custom, "пр"),
        "holder": holder or "власть", "Holder": _cap(holder or "власть"),
        "why": why, "what": what,
        "husk": custom.husk or "делают то же, но короче",
    }
    heads = {
        "hold": "Обычай закреплён: %s", "reform": "Обычай переделан: %s",
        "forbid": "Обычай запрещён: %s", "hide": "Обычай ушёл в тайну: %s",
        "thin": "Обычай усох: %s", "quarrel": "Спор об обычае: %s",
        "fade": "Обычай забыт: %s", "revive": "Обычай вернулся: %s",
    }
    return heads.get(key, "Обычай: %s") % custom.name, text


# ---------------------------------------------------------------------------
# Забытая причина
# ---------------------------------------------------------------------------

FORGOT_TEMPLATES = (
    "Отчего делают так, в народе уже не скажут: %(how)s. Порядок остался, "
    "объяснения разошлись — говорят кто во что: %(folk_why)s",
    "Причина потерялась — %(how)s. Делать не перестали: %(doing)s. А "
    "спросишь зачем — ответят так: %(folk_why)s",
    "%(How)s, и смысл ушёл раньше самого обычая. Теперь о нём говорят "
    "так: %(folk_why)s",
)


def forgot(rng, custom, how: str) -> tuple:
    shape = rng.choice(FORGOT_TEMPLATES)
    text = shape % {"how": how, "How": _cap(how), "doing": custom.doing,
                    "folk_why": custom.folk_why or "«так положено»"}
    return "Забытая причина: %s" % custom.name, text


# ---------------------------------------------------------------------------
# Изводы
# ---------------------------------------------------------------------------

VARIANT_TEMPLATES = (
    "%(Where)s %(custom)s держат иначе: %(mark)s. Соседи считают это "
    "порчей, сами — единственно верным порядком.",
    "У %(custom_rod)s завёлся извод: %(where)s %(mark)s.",
    "%(Where)s то же самое делают по-другому: %(mark)s. Спорят об этом "
    "редко — разъезжаются нечасто.",
)


def variant(rng, custom, where: str, mark: str) -> tuple:
    shape = rng.choice(VARIANT_TEMPLATES)
    text = shape % {"custom": named(custom), "custom_rod": named(custom, "род"),
                    "where": where, "Where": _cap(where), "mark": mark}
    return "Извод обычая: %s" % custom.name, text


# ---------------------------------------------------------------------------
# Человек и обычай
# ---------------------------------------------------------------------------

BROKE_TEMPLATES = (
    "%(Who)s нарушил %(custom_vin)s — и не тайком, а при свидетелях. "
    "%(Why)s",
    "%(Who)s сделал то, чего по обычаю не делают: %(custom)s был нарушен "
    "у всех на глазах. %(Why)s",
    "О том, что %(who)s пренебрёг %(custom_twor)s, говорили дольше, чем о "
    "самом деле. %(Why)s",
)

BROKE_WHYS = {
    "refuse": "Он и не скрывал, что считает этот порядок лишним.",
    "blind": "Он попросту не знал, что так нельзя: вырос он не здесь.",
    "wrong": "Он был уверен, что делает всё верно, — и ошибался не со зла.",
    "secret": "Он держал запрещённое, и держал не первый год.",
    "reform": "Он говорил, что хочет сохранить суть, сменив порядок.",
    "new": "Взамен он завёл своё, и у него нашлись подражатели.",
}

BROKE_ENDS = (
    "Простили: дело было давнее, а человек нужный.",
    "Не простили: имя его в этом городе с тех пор поминают с оговоркой.",
    "Разошлись миром, когда он возместил ущерб.",
    "Родня отступилась от него, и это оказалось хуже любого суда.",
    "Молодые взяли с него пример, и через поколение так стали делать многие.",
    "Власть сочла это вызовом себе, хотя он о власти и не думал.",
)


def broke(rng, who: str, custom, kind: str) -> tuple:
    shape = rng.choice(BROKE_TEMPLATES)
    text = shape % {"who": who, "Who": _cap(who), "custom": named(custom),
                    "custom_vin": named(custom, "вин"),
                    "custom_twor": named(custom, "твор"),
                    "Why": BROKE_WHYS.get(kind, "Объяснений он не давал.")}
    return "Против обычая: %s" % custom.name, text + " " + rng.choice(BROKE_ENDS)


MADE_TEMPLATES = (
    "%(Who)s завёл порядок, которого прежде не было: %(doing)s. Сперва "
    "над этим посмеивались.",
    "С %(who_rod)s пошёл новый обычай: %(doing)s. Он никому его не "
    "навязывал — просто делал так всегда.",
    "%(Who)s переделал старое на свой лад: %(doing)s. Прижилось не сразу "
    "и не везде.",
)


def made(rng, who: str, who_rod: str, doing: str) -> tuple:
    shape = rng.choice(MADE_TEMPLATES)
    text = shape % {"who": who, "Who": _cap(who), "who_rod": who_rod,
                    "doing": doing}
    return "Новый обычай", text


# ---------------------------------------------------------------------------
# Столкновение обычаев
# ---------------------------------------------------------------------------

CLASH_TEMPLATES = (
    "В городе по имени %(town)s сошлись два порядка: %(what)s. Дело "
    "дошло до старейшин.",
    "Народы, живущие в городе по имени %(town)s, разошлись в простом: "
    "%(what)s.",
    "Спор в городе по имени %(town)s вышел не из-за добра и не из-за "
    "веры: %(what)s.",
)

CLASH_END_TEXT = {
    "apart": "Кончилось тем, что разошлись по разным концам города и "
             "делают каждый своё.",
    "mixed": "Кончилось третьим порядком, которого прежде не было ни у "
             "одних, ни у других.",
    "yield": "Кончилось тем, что младшие уступили старшим; обида осталась.",
    "law": "Кончилось законом, и обе стороны сочли себя обделёнными.",
    "feud": "Кончилось кровью, и помнят об этом дольше, чем о самом споре.",
    "quiet": "Кончилось ничем: через поколение об этом перестали спорить.",
}


def clash(rng, town_name: str, what: str, end_key: str) -> tuple:
    shape = rng.choice(CLASH_TEMPLATES)
    text = shape % {"town": town_name, "what": what}
    return ("Спор об обычаях: %s" % town_name,
            text + " " + CLASH_END_TEXT.get(end_key, ""))


# ---------------------------------------------------------------------------
# Описание для карточек
# ---------------------------------------------------------------------------

def about(world, custom) -> list:
    """Обычай прозой: что делают, отчего и что с ним стало."""
    rows = ["%s — %s." % (_cap(custom.name), custom.doing)]
    case = cat.CASES_BY_KEY.get(custom.case)
    need = cat.NEEDS_BY_KEY.get(custom.need)
    if case is not None and need is not None:
        rows.append("Случай: %s. Служит тому, чтобы %s."
                    % (case.when, need.name.lower()))
    if custom.gear:
        rows.append("Нужно для этого: %s." % custom.gear)
    if cat.is_known(custom.why):
        rows.append("Отчего завёлся: %s." % custom.why)
    else:
        rows.append("Отчего завёлся — не помнят%s."
                    % (" (забыли к %d году)" % custom.forgot_year
                       if custom.forgot_year else ""))
    if custom.said:
        rows.append("Сверху говорят: %s." % custom.said)
    if custom.folk_why:
        rows.append("Между собой говорят: %s." % custom.folk_why)
    rows.append("Насколько обязателен: %s — %s."
                % (custom.bind, cat.BIND_ABOUT.get(custom.bind, "")))
    rows.append("Докуда дошёл: %s. Состояние: %s." % (custom.reach,
                                                      custom.state))
    if custom.holder:
        rows.append("Держит его %s." % custom.holder)
    if custom.taboo:
        rows.append("Это запрет, и стоит он вот на чём: %s." % custom.taboo)
    return rows


def profile_lines(world, profile, figure) -> list:
    """Культурный облик личности для карточки."""
    rows = []
    born = world.folks.get(profile.born_folk)
    raised = world.folks.get(profile.raised_folk)
    now = world.folks.get(profile.now_folk)
    if born is not None:
        line = "Родился в народе по имени %s" % born.name
        if raised is not None and raised.id != born.id:
            line += ", а вырос среди народа по имени %s" % raised.name
        if now is not None and now.id != (raised or born).id:
            line += "; теперь причисляет себя к народу по имени %s" % now.name
        rows.append(line + ".")
    for mark in profile.influences:
        rows.append("Чужое влияние: %s — %s."
                    % (mark.get("что", "?"), mark.get("отчего", "?")))
    for row in profile.attitudes:
        custom = world.customs.get(row.get("обычай", ""))
        kind = cat.ATTITUDES_BY_KEY.get(row.get("вид", ""))
        if custom is None or kind is None:
            continue
        rows.append("К обычаю «%s» — %s: %s."
                    % (custom.name, kind.name,
                       row.get("отчего") or kind.about))
    for row in profile.habits:
        rows.append("Привычка: %s." % row.get("что", "?"))
    for row in profile.rites:
        rows.append("Свой обряд: %s%s." % (row.get("что", "?"),
                                           " — " + row.get("отчего")
                                           if row.get("отчего") else ""))
    for row in profile.broke:
        custom = world.customs.get(row.get("обычай", ""))
        if custom is not None:
            rows.append("Нарушил обычай «%s» в %d году."
                        % (custom.name, int(row.get("год", 0))))
    for row in profile.made:
        custom = world.customs.get(row.get("обычай", ""))
        if custom is not None:
            rows.append("%s обычай «%s» (%d год)."
                        % (row.get("что", "Переменил"), custom.name,
                           int(row.get("год", 0))))
    return rows
