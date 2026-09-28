# -*- coding: utf-8 -*-
"""Тексты нашествия: как пришли, чего хотели, как назвали.

Тексты беды как беды лежат в `narrative_calamity`, а живой катастрофы —
в `narrative_disaster`. Здесь то, что есть только у нашествия: имя по
месту, по вождю и по-державному; открывшийся вождь; перемена цели;
разные ответы держав; исход с его способом; остатки и имена, которые
дали, когда всё кончилось.
"""

from __future__ import annotations

from . import invasion as inv
from .narrative_calamity import cap, region_list, souls
from .timeline import years_text


# ---------------------------------------------------------------------------
# Имена
# ---------------------------------------------------------------------------

# Имена собственные остаются в именительном падеже, как везде в летописи,
# поэтому и в названии события они стоят через оборот: «Беда на земле по
# имени Оркхад», а не «Беда Оркхада».
PLACE_FRAMES = (
    "Беда на земле по имени %s",
    "Стояние у земли по имени %s",
    "Война за землю по имени %s",
    "Год земли по имени %s",
    "Падение рубежа у земли по имени %s",
)

LEADER_FRAMES = (
    "Поход вождя по имени %s",
    "Война вождя по имени %s",
    "Возвращение того, кого звали %s",
    "Годы вождя по имени %s",
)


def place_name(rng, where: str) -> str:
    """Имя по месту: «Беда на земле по имени Оркхад»."""
    if not where:
        return rng.choice(inv.NAME_BY_SIGN)
    return rng.choice(PLACE_FRAMES) % where


def leader_name(rng, figure) -> str:
    """Имя по вождю: «Поход вождя по имени Архаан»."""
    if figure is None:
        return rng.choice(inv.NAME_BY_SIGN)
    return rng.choice(LEADER_FRAMES) % figure.plain_name


def state_name(rng, where: str, year: int) -> str:
    """Державное имя: сухо, по году и по краю."""
    frame = rng.choice(inv.NAME_STATE_FRAMES)
    return frame % {"where": where or "Дальний", "year": int(year)}


FOLK_TAILS = (
    "Ночь, Когда Они Пришли", "Лето, Которое Помнят",
    "Годы, Когда Мы Бежали", "Время, Когда Не Звонили",
    "Зима, После Которой Считали Живых",
)


def folk_name(rng, invasion, calamity, world) -> str:
    """Народное имя: по тому дню, который запомнили, а не по итогу."""
    if invasion.first_sign and rng.chance(0.4):
        return rng.choice(inv.NAME_BY_MARK)
    if rng.chance(0.5):
        return rng.choice(FOLK_TAILS)
    return rng.choice(inv.NAME_BY_TOKEN)


# ---------------------------------------------------------------------------
# Начало
# ---------------------------------------------------------------------------

BEGIN_FRAMES = (
    "Началось не с войска: %(sign)s.",
    "Первым знаком было вот что: %(sign)s.",
    "Поняли не сразу — %(sign)s.",
)

THEIRS_FRAMES = (
    "С их стороны это выглядело иначе: %(theirs)s.",
    "Сами они рассказывали так: %(theirs)s.",
    "Того, что они шли не воевать, никто не слушал: %(theirs)s.",
)


def invasion_begins(rng, invasion, calamity, world) -> tuple:
    """Как это началось — и чем это было для них самих."""
    where = region_list(world, calamity.region_ids, limit=2)
    lines = [cap(rng.choice(BEGIN_FRAMES) % {"sign": invasion.first_sign})]
    lines.append("Пришли %s — %s." % (
        invasion.kind, inv.INVADERS_BY_KEY[invasion.kind].about))
    lines.append("Отчего: %s." % inv.CAUSES_BY_KEY[invasion.cause].about)
    lines.append("Чего хотели: %s." % inv.GOALS_BY_KEY[invasion.goal].about)
    if invasion.cause_theirs:
        lines.append(rng.choice(THEIRS_FRAMES)
                     % {"theirs": invasion.cause_theirs})
    lines.append("Земли, куда это пришло: %s." % where)
    return ("Начало: %s" % (invasion.title or calamity.name),
            " ".join(lines))


# ---------------------------------------------------------------------------
# Открывшийся вождь
# ---------------------------------------------------------------------------

SHOWN_FRAMES = (
    "Годы это шло как набеги без разбора, а потом стало ясно: ими правят.",
    "Сперва думали, что это просто их природа. Потом нашли того, кто им "
    "велит.",
    "Того, что у них есть старший, не знали до этого года.",
)

SHOWN_TAILS = (
    "И война стала другой войной: с державой, а не со стаей.",
    "После этого стали искать не логово, а ставку.",
    "Прежние победы пришлось пересчитать заново.",
)


def leader_shown(rng, invasion, calamity, figure, world) -> tuple:
    """Скрытый вождь открылся."""
    who = ("вождь по имени %s" % figure.plain_name) if figure is not None \
        else "тот, кого так и не увидели"
    text = "%s Это %s. %s" % (rng.choice(SHOWN_FRAMES), who,
                              rng.choice(SHOWN_TAILS))
    return ("Ими правят: %s" % (calamity.name or "нашествие"), text)


# ---------------------------------------------------------------------------
# Перемена цели
# ---------------------------------------------------------------------------

TURN_FRAMES = (
    "Вышло так, что %(why)s, — и они переменили, чего хотят.",
    "%(why_cap)s. С этого года они хотели другого.",
    "Их держало одно, стало другое: %(why)s.",
)


def goal_turned(rng, invasion, calamity, why: str, was: str,
                now: str) -> tuple:
    """Цель нашествия сменилась по ходу."""
    data = {"why": why, "why_cap": cap(why)}
    was_about = inv.GOALS_BY_KEY[was].about if was in inv.GOALS_BY_KEY else was
    now_about = inv.GOALS_BY_KEY[now].about if now in inv.GOALS_BY_KEY else now
    text = "%s Шли, чтобы %s; стали — чтобы %s." % (
        cap(rng.choice(TURN_FRAMES) % data), was_about, now_about)
    return ("Они передумали: %s" % calamity.name, text)


# ---------------------------------------------------------------------------
# Ответы держав
# ---------------------------------------------------------------------------

ANSWER_FRAMES = (
    "Отвечали по-разному, и это потом не забылось.",
    "Каждая держава решала за себя, и решили они врозь.",
    "Одного ответа на это не нашлось.",
)

ANSWER_TAILS = (
    "Тот, кто вышел в поле, не простил тому, кто заплатил.",
    "Через сто лет об этом всё ещё считались.",
    "Кто как повёл себя в тот год, помнили дольше самой беды.",
    "Спорить о том, кто был прав, перестали только с теми, кто помнил.",
)


def answers_told(rng, invasion, calamity, world) -> tuple:
    """Как разные державы ответили на одно нашествие."""
    lines = [rng.choice(ANSWER_FRAMES)]
    for row in invasion.answers[:5]:
        polity = world.polities.get(row.get("держава", ""))
        answer = inv.ANSWERS_BY_KEY.get(row.get("ответ", ""))
        if polity is None or answer is None:
            continue
        lines.append("%s — %s." % (polity.full_name, answer.about))
    lines.append(rng.choice(ANSWER_TAILS))
    return ("Как отвечали: %s" % calamity.name, " ".join(lines))


# ---------------------------------------------------------------------------
# Исход
# ---------------------------------------------------------------------------

DECISIVE = (
    "решило дело одно утро под стенами",
    "решил один человек, которого потом не нашли",
    "решило то, что у них кончилась вода",
    "решил переход, которого от них не ждали",
    "решило письмо, перехваченное случайно",
    "решило то, что их вождь не поверил своим",
    "решила зима, пришедшая на месяц раньше",
    "решил тот, кто перешёл на другую сторону",
    "решило, что помощь пришла не оттуда, откуда ждали",
    "решило дело то, что они рассорились между собой",
    "решило то, что людям стало нечего терять",
    "не решило ничего: просто однажды их не стало видно",
)

END_FRAMES = {
    inv.OUT_DESTROYED: "Их не стало вовсе.",
    inv.OUT_DEFEATED: "Их разбили.",
    inv.OUT_REPULSED: "Их отбили, и дальше они не пошли.",
    inv.OUT_SEALED: "Их заперли там, откуда они вышли.",
    inv.OUT_EXILED: "Их выгнали за край известных земель.",
    inv.OUT_DEAL: "С ними сговорились, и уговор держался.",
    inv.OUT_HELD: "Их заперли в тех землях, которые они взяли.",
    inv.OUT_JOINED: "Они остались и стали ещё одним соседом.",
    inv.OUT_BECAME: "Они остались, и через несколько поколений их перестали "
                    "считать чужими.",
    inv.OUT_VASSAL: "Они взяли людей под себя.",
    inv.OUT_SETTLED: "Они осели на этой земле и не ушли.",
    inv.OUT_LEFT: "Они ушли сами, и никто не понял отчего.",
    inv.OUT_BROKE: "Они перебили друг друга, и людям осталось держать стены.",
    inv.OUT_HALF: "Их разбили наполовину, и половина осталась.",
    inv.OUT_GOING: "Это не кончилось.",
    inv.OUT_UNKNOWN: "Чем это кончилось, летопись не говорит.",
}

END_TAILS = (
    "Своды обеих сторон считают этот год по-разному.",
    "Тех, кто помнил начало, к концу уже не было.",
    "Победой это назвали позже и не сразу.",
    "Счёт ушедшим свели через двадцать лет и не сошлись.",
)


def invasion_ends(rng, invasion, calamity, world) -> tuple:
    """Чем кончилось нашествие — и что от него осталось."""
    lines = [END_FRAMES.get(invasion.outcome, "Это как-то кончилось.")]
    if invasion.way:
        about = inv.WAYS_BY_KEY.get(invasion.way, ("", ()))[0]
        if about:
            lines.append("Как: %s." % about)
    if invasion.decisive:
        lines.append("А %s." % invasion.decisive)
    if invasion.goal_turns:
        last = invasion.goal_turns[-1]
        lines.append("К концу они хотели уже не того, с чем пришли: %s."
                     % inv.GOALS_BY_KEY.get(last.get("стало", ""),
                                            inv.GOALS[0]).about)
    if invasion.surrender:
        lines.append("Людям это стоило вот чего: %s." % invasion.surrender)
    if calamity.deaths:
        lines.append("Не досчитались %s." % souls(calamity.deaths))
    if invasion.years:
        lines.append("Шло это %s." % years_text(invasion.years))
    for row in invasion.remnants:
        region = world.regions.get(row.get("земля", ""))
        lines.append("Осталось: %s%s." % (
            row.get("о чём", row.get("вид", "")),
            (" — в земле по имени %s" % region.name) if region else ""))
    if invasion.names:
        said = "; ".join("%s — «%s»" % (voice, name)
                         for voice, name in invasion.names.items())
        lines.append("Имён у этого несколько: %s." % said)
    lines.append(rng.choice(END_TAILS))
    return ("Чем кончилось: %s" % calamity.name, " ".join(lines))


__all__ = ["place_name", "leader_name", "state_name", "folk_name",
           "invasion_begins", "leader_shown", "goal_turned", "answers_told",
           "invasion_ends", "DECISIVE"]
