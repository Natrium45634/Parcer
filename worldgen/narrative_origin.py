# -*- coding: utf-8 -*-
"""Слова о начале мира: первая глава, которую читают прежде всего.

Задача этих текстов одна: чтобы начало читалось мифом о рождении именно
этого мира, а не справкой. Поэтому тут нет перечислений через запятую
там, где можно сказать фразой, и порядок слоёв рассказывается как
порядок, а не как список.

Два правила письма, которых тут держимся особо.

Во-первых, **о неизвестном говорится вслух**. «Не записано», «согласия
нет», «спорят до сих пор» — такие же честные строки, как любая другая, и
в мире, где о начале известно мало, их должно быть много.

Во-вторых, **имена собственные тут редкость**. Первородных и творцов
зовут по именам, и эти имена выдуманы — значит стоят в именительном и
только после оборота («тот, кого звали X»). Всё прочее — обычные русские
слова, и они склоняются свободно.
"""

from __future__ import annotations

from . import origin as cat


def cap(line: str) -> str:
    return line[:1].upper() + line[1:] if line else line


# Слои зовутся обычными русскими словами, и потому их можно склонять. Но
# склонять их надо правильно, а правил на двенадцать слов не напишешь —
# проще выписать руками родительный падеж и род. Без этого в тексте
# встаёт «быть ли в мире смерть» и «материя легло прежде прочего».
LAYER_GEN = {
    cat.SPACE: "пространства", cat.TIME: "времени", cat.MATTER: "материи",
    cat.LIGHT: "света", cat.MAGIC: "магии", cat.LIFE: "жизни",
    cat.SOUL: "души", cat.DEATH: "смерти", cat.DREAM: "сна",
    cat.MEMORY: "памяти", cat.WORD: "слова", cat.MIND: "сознания",
}

LAYER_GENDER = {
    cat.SPACE: "с", cat.TIME: "с", cat.MATTER: "ж", cat.LIGHT: "м",
    cat.MAGIC: "ж", cat.LIFE: "ж", cat.SOUL: "ж", cat.DEATH: "ж",
    cat.DREAM: "м", cat.MEMORY: "ж", cat.WORD: "с", cat.MIND: "с",
}

# «лёг», «легла», «легло» — согласование по роду слоя.
LAID = {"м": "лёг", "ж": "легла", "с": "легло"}


# Предложный падеж: «спорят о времени», «о первом споре».
LAYER_PREP = {
    cat.SPACE: "пространстве", cat.TIME: "времени", cat.MATTER: "материи",
    cat.LIGHT: "свете", cat.MAGIC: "магии", cat.LIFE: "жизни",
    cat.SOUL: "душе", cat.DEATH: "смерти", cat.DREAM: "сне",
    cat.MEMORY: "памяти", cat.WORD: "слове", cat.MIND: "сознании",
}

# То же для прочего, о чём спорят, — это не слои, а имена предметов спора.
ABOUT_PREP = {
    "творец": "творце", "первая жизнь": "первой жизни",
    "первый спор": "первом споре",
}


def about_prep(key: str) -> str:
    """То, о чём спорят, в предложном: «о времени», «о первом споре»."""
    return LAYER_PREP.get(key) or ABOUT_PREP.get(key, key)


def layer_gen(key: str) -> str:
    """Слой в родительном: «быть ли в мире смерти»."""
    return LAYER_GEN.get(key, key)


def laid(key: str) -> str:
    """«легло» или «легла» — смотря какого рода слой."""
    return LAID.get(LAYER_GENDER.get(key, "с"), "легло")


# ---------------------------------------------------------------------------
# Как было прежде всего
# ---------------------------------------------------------------------------

BEFORE = {
    "единый творец": (
        "Прежде всего был один, и он был один по-настоящему: спросить "
        "было некого.",
        "Сперва не было ничего, кроме того, кто потом всё сделал.",
    ),
    "творцы": (
        "Прежде всего их было несколько, и они уже тогда не ладили.",
        "Сперва были те, кто взялся делать мир сообща, — и каждый тянул "
        "в свою сторону.",
    ),
    "мир из тела": (
        "Прежде всего было тело, и оно было живым.",
        "Сперва был один, и он не хотел становиться миром.",
    ),
    "спящий творец": (
        "Прежде всего был тот, кто работал, не просыпаясь.",
        "Сперва была работа, а делавший её и тогда уже спал.",
    ),
    "безначальный мир": (
        "Прежде всего был сам мир: его никто не начинал.",
        "Сперва было то же, что и теперь, — и с этим ничего не поделать.",
    ),
    "мир-случайность": (
        "Прежде всего был спор холода и огня, и спор этот был ни о чём.",
        "Сперва ничего не задумывалось. Это и пугает сильнее всего.",
    ),
}


def before_line(rng, model: str) -> str:
    rows = BEFORE.get(model) or BEFORE["безначальный мир"]
    return rng.choice(rows)


# ---------------------------------------------------------------------------
# Порядок слоёв
# ---------------------------------------------------------------------------

FIRST_WORDS = ("Первым легло", "Первым в мир пришло", "Прежде прочего встало")
# Связки нарочно без местоимений: «за ним» после «материи» или «смерти»
# читается как ошибка, а род предыдущего слоя тут всякий раз другой.
NEXT_WORDS = ("Следом —", "Потом —", "После того —", "Дальше —", "За тем —")
LAST_WORDS = ("И последним —", "В самом конце —", "Напоследок —")


def order_lines(rng, origin) -> list:
    """Порядок творения — рассказом, а не списком.

    Самое важное тут — слой, который встал прежде того, на чём держится:
    смерть прежде жизни, сознание прежде живого. Об этом говорится
    отдельной строкой, потому что это и есть главное, что надо знать о
    таком мире.
    """
    rows = origin.order
    if not rows:
        return ["О том, в каком порядке складывался этот мир, не известно "
                "ничего."]
    out = []
    names = []
    for number, row in enumerate(rows):
        layer = cat.LAYERS.get(row["слой"])
        if layer is None:
            continue
        if number == 0:
            lead = rng.choice(FIRST_WORDS)
        elif number == len(rows) - 1:
            lead = rng.choice(LAST_WORDS)
        else:
            lead = rng.choice(NEXT_WORDS)
        names.append("%s %s: %s." % (lead, layer.name,
                                     row.get("чем вышло") or layer.about))
    out.extend(names)

    # Перевёрнутый порядок: об этом надо сказать прямо.
    place = {row["слой"]: index for index, row in enumerate(rows)}
    if cat.DEATH in place and cat.LIFE in place \
            and place[cat.DEATH] < place[cat.LIFE]:
        out.append("Главное об этом мире: смерть тут старше жизни. Она не "
                   "пришла к живому — она его дождалась.")
    if cat.MIND in place and cat.LIFE in place \
            and place[cat.MIND] < place[cat.LIFE]:
        out.append("И ещё: сперва кто-то понял, а потом ожил. В этом мире "
                   "сознание старше тела.")
    if cat.MAGIC in place and cat.MATTER in place \
            and place[cat.MAGIC] < place[cat.MATTER]:
        out.append("Сила тут старше вещества, и потому вещи ей послушны "
                   "больше, чем следовало бы.")
    for key in origin.missing:
        layer = cat.LAYERS.get(key)
        if layer is not None and layer.without:
            out.append(cap(layer.without) + ".")
    return out


# ---------------------------------------------------------------------------
# Спор
# ---------------------------------------------------------------------------

QUARREL_LEADS = (
    "Спорили об этом так, что мир пошёл трещинами:",
    "Из всех споров тот был самый тяжёлый:",
    "Главный спор был не о красоте мира, а вот о чём:",
)


def quarrel_lines(rng, world, origin) -> list:
    if not origin.quarrel:
        return ["О том, спорили ли при творении, не сохранилось ничего."]
    row = origin.layer_of(origin.quarrel)
    out = [rng.choice(QUARREL_LEADS)]
    out.append("спорили о том, быть ли в мире %s. %s хотел иного: %s."
               % (layer_gen(origin.quarrel),
                  cap(_who(world, origin.loser_id, "кто-то из первых")),
                  row.get("чего хотел") or "чтобы вышло не так"))
    argued = cat.DISPUTES.get(row.get("спор"))
    if argued is not None:
        out.append("%s. Кончилось тем, что %s."
                   % (cap(argued.argued), origin.quarrel_how))
    if origin.quarrel_cost:
        out.append("Даром это не вышло: %s." % origin.quarrel_cost)
    if origin.winner_id:
        out.append("Настоял %s." % _who(world, origin.winner_id, "тот, кого "
                                        "уже не помнят"))
    if origin.sealed:
        out.append("Убить проигравшее не вышло, и его заперли: %s — %s."
                   % (origin.sealed, origin.sealed_how))
    return out


def _who(world, deity_id: str, instead: str) -> str:
    """Имя действующего лица — всегда в именительном и через оборот."""
    deity = world.deities.get(deity_id) if deity_id else None
    if deity is None:
        return instead
    return "тот, кого звали %s" % deity.given_name


# ---------------------------------------------------------------------------
# Законы
# ---------------------------------------------------------------------------

LAW_LEADS = (
    "Из всего этого вышли правила, по которым мир стоит до сих пор:",
    "Так у мира завелись законы — не писаные, а те, что не обойти:",
    "И вот чего в этом мире нельзя — не по запрету, а по устройству:",
)


def law_lines(rng, origin) -> list:
    named = [row for row in origin.laws if row.get("известен")]
    if not named:
        return ["Законов этого мира никто не назвал: о его устройстве "
                "спорят, а не знают."]
    out = [rng.choice(LAW_LEADS)]
    for row in named:
        out.append("— %s. Так вышло потому, что %s."
                   % (cap(row["закон"]), row["отчего"]))
    quiet = len(origin.laws) - len(named)
    if quiet:
        out.append("Ещё несколько правил в этом мире действуют, но назвать "
                   "их никто не берётся.")
    return out


# ---------------------------------------------------------------------------
# Жизнь и первые
# ---------------------------------------------------------------------------

def life_lines(rng, origin) -> list:
    way = cat.LIFE_WAYS.get(origin.life_way)
    kind = cat.FIRST_KINDS.get(origin.first_kind)
    out = []
    if way is not None:
        out.append("%s: %s." % (cap(way.name), way.about))
    if kind is not None:
        out.append("Первыми в этом мире были %s — %s." % (kind.name,
                                                          kind.about))
        if kind.fate:
            out.append(cap(kind.fate) + ".")
        if kind.heirs:
            out.append(cap(kind.heirs) + ".")
    if origin.one_root:
        out.append("Нынешние народы — ветви одного корня, и сами они об "
                   "этом не помнят.")
        if origin.split_how:
            out.append("Разошлись они вот отчего: %s." % origin.split_how)
    else:
        out.append("Нынешние народы друг другу не родня: у живого тут "
                   "несколько корней.")
    return out


# ---------------------------------------------------------------------------
# Шрамы
# ---------------------------------------------------------------------------

SCAR_LEADS = (
    "Творение оставило на земле следы, и до них можно дойти ногами:",
    "Кое-что от начала мира лежит в нём до сих пор:",
    "А это осталось от самой работы — и никуда не денется:",
)


def scar_lines(rng, world, origin) -> list:
    if not origin.scars:
        return []
    out = [rng.choice(SCAR_LEADS)]
    for row in origin.scars:
        region = world.regions.get(row.get("земля", ""))
        where = ("в земле по имени %s" % region.name) if region is not None \
            else "неизвестно где"
        out.append("— %s, %s: %s. %s."
                   % (cap(row.get("имя", "")), where, row.get("что было", ""),
                      cap(row.get("что теперь", ""))))
    return out


# ---------------------------------------------------------------------------
# Что об этом знают
# ---------------------------------------------------------------------------

FOLK_FRAMES = (
    "у них это рассказывают так: %s",
    "они говорят, что %s",
    "по их счёту %s",
    "их старшие учат, что %s",
)

# Чем версия расходится с правдой. Чем меньше мир знает о себе, тем
# дальше уходит рассказ — но уходит он не куда попало, а по людски: себя
# ставят в начало, чужое объявляют поздним, непонятное — злым.
DRIFTS = (
    "мир сделан для них и держится на них",
    "их предки были при творении и помогали",
    "прочие народы появились много позже и не из того же корня",
    "то, чего они не понимают в мире, сделано не творцом, а чужим",
    "у творения был один хозяин, и имя его знают только они",
    "начало мира было недавно, и счёт годам ведут от их первого города",
    "смерти в замысле не было, и она чужая работа",
    "мир кончится так же, как начался, и они это переживут",
)


def folk_version(rng, origin, name: str) -> str:
    """Как рассказывает о начале один народ."""
    true_part = _true_bit(rng, origin)
    if rng.chance(max(0.1, origin.known)):
        return rng.choice(FOLK_FRAMES) % true_part
    return rng.choice(FOLK_FRAMES) % rng.choice(DRIFTS)


FAITH_FRAMES = (
    "храм учит, что %s",
    "в своде этой веры написано, что %s",
    "жрецы читают это так: %s",
)

FAITH_DRIFTS = (
    "мир сделан по воле того, кому они служат, и больше ничьей",
    "спор при творении был не спором, а испытанием",
    "запертое в основании мира держит их молитва, и только она",
    "законы мира даны им, а не выведены людьми",
    "о начале сказано всё, и кто спрашивает дальше — ищет не истины",
)


def faith_version(rng, origin, name: str) -> str:
    if rng.chance(max(0.08, origin.known - 0.15)):
        return rng.choice(FAITH_FRAMES) % _true_bit(rng, origin)
    return rng.choice(FAITH_FRAMES) % rng.choice(FAITH_DRIFTS)


def _true_bit(rng, origin) -> str:
    """Та часть правды, которую этот рассказ удержал верно.

    Берётся не одно и то же: если у двух народов верная память об одном
    и том же, рассказ выходит скучнее, чем мир.
    """
    rows = []
    motif = cat.MOTIFS.get(origin.motif)
    if motif is not None:
        rows.append(motif.about)
    for row in origin.order[:3]:
        key = row["слой"]
        layer = cat.LAYERS.get(key)
        if layer is not None:
            rows.append("%s %s прежде прочего" % (layer.name, laid(key)))
    way = cat.LIFE_WAYS.get(origin.life_way)
    if way is not None:
        rows.append(way.about)
    kind = cat.FIRST_KINDS.get(origin.first_kind)
    if kind is not None:
        rows.append("первыми тут были %s" % kind.name)
    if origin.sealed:
        rows.append("под миром заперто то, ради чего он и сделан")
    if origin.quarrel:
        rows.append("спор при творении шёл о том, быть ли в мире %s"
                    % layer_gen(origin.quarrel))
    if origin.one_root:
        rows.append("все нынешние народы вышли из одного корня")
    for row in origin.laws[:4]:
        if row.get("известен"):
            rows.append(row["закон"])
    if origin.missing:
        key = origin.missing[0]
        layer = cat.LAYERS.get(key)
        if layer is not None and layer.without:
            rows.append(layer.without)
    return rng.choice(rows) if rows else "мир был сделан"


CLASH_LEADS = (
    "А кое в чём источники друг другу прямо противоречат:",
    "И тут согласия нет вовсе:",
    "Об этом спорят, и спор не решён:",
)


def clash_lines(rng, origin) -> list:
    rows = origin.clashes
    if not rows:
        return []
    out = [rng.choice(CLASH_LEADS)]
    for row in rows:
        tail = " Спор решили." if row.get("решено") else \
            " Так и не решено, кто прав."
        out.append("— о %s: %s (%s против %s).%s"
                   % (about_prep(row.get("о чём", "")), row.get("как", ""),
                      row.get("кто", ""), row.get("против", ""), tail))
    return out


# ---------------------------------------------------------------------------
# Записи летописи
# ---------------------------------------------------------------------------

def dawn_event(origin, motif, sure) -> tuple:
    """Первая запись летописи — та, с которой всё начинается."""
    title = "Начало: %s" % motif.name
    rows = ["%s." % cap(motif.about)]
    rows.append("Уклад этого мира — %s." % origin.model)
    rows.append("Слоёв в нём положено %d%s."
                % (len(origin.layers),
                   ", и %d не положено вовсе" % len(origin.missing)
                   if origin.missing else ""))
    if motif.leaves:
        rows.append("%s." % cap(motif.leaves))
    rows.append("О начале известно вот сколько: %s." % sure.about)
    return title, " ".join(rows)


def laws_event(origin, named) -> tuple:
    title = "Законы мира"
    rows = ["То, чего в этом мире нельзя не по запрету, а по устройству:"]
    rows.append("; ".join(row["закон"] for row in named) + ".")
    return title, " ".join(rows)


# ---------------------------------------------------------------------------
# Первая глава
# ---------------------------------------------------------------------------

def chapter(rng, world, origin) -> list:
    """Вся первая глава по порядку: как было, что из этого вышло, что знают."""
    motif = cat.MOTIFS.get(origin.motif)
    sure = cat.CERTAINTY.get(origin.certainty)
    rows = []
    rows.append(before_line(rng, origin.model))
    if motif is not None:
        rows.append("%s." % cap(motif.about))
        if motif.leaves:
            rows.append("%s." % cap(motif.leaves))
    rows.append("")
    rows.extend(order_lines(rng, origin))
    rows.append("")
    rows.extend(quarrel_lines(rng, world, origin))
    rows.append("")
    rows.extend(law_lines(rng, origin))
    rows.append("")
    rows.extend(life_lines(rng, origin))
    scars = scar_lines(rng, world, origin)
    if scars:
        rows.append("")
        rows.extend(scars)
    rows.append("")
    if sure is not None:
        rows.append("%s." % cap(sure.about))
    for row in origin.versions:
        rows.append("— %s: %s." % (row.get("кто", ""), row.get("как", "")))
    clashes = clash_lines(rng, origin)
    if clashes:
        rows.append("")
        rows.extend(clashes)
    if origin.unknown:
        rows.append("")
        rows.append("И вот что осталось без ответа:")
        for line in origin.unknown:
            rows.append("— %s." % line)
    return rows


__all__ = ["cap", "about_prep", "layer_gen", "laid",
           "before_line", "order_lines", "quarrel_lines", "law_lines",
           "life_lines", "scar_lines", "folk_version", "faith_version",
           "clash_lines", "dawn_event", "laws_event", "chapter"]
