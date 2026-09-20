# -*- coding: utf-8 -*-
"""Тексты о чудовищах: пробуждение, разор, охота, конец.

Правила прежние: сгенерированные имена стоят в именительном падеже,
косвенные падежи берутся готовыми оборотами, глаголы — в настоящем
времени третьего лица.
"""

from __future__ import annotations

from .narrative import cap
from .timeline import years_text


def beast(monster) -> str:
    """«дракон по имени Скарагорн» — для косвенных падежей."""
    return "%s по имени %s" % (monster.word.lower(), monster.name)


def beast_nom(monster) -> str:
    return "%s %s" % (monster.word, monster.name)


# ---------------------------------------------------------------------------
# Появление
# ---------------------------------------------------------------------------

WAKE_TEMPLATES = (
    "В земле по имени %(region)s заводится то, чего там прежде не было: "
    "%(who)s. %(note)s",
    "Пастухи приносят весть, которой сперва не верят, а потом верят "
    "слишком хорошо: земля по имени %(region)s теперь не своя — на ней "
    "%(who_short)s. %(note)s",
    "%(who)s приходит в эти земли и остаётся: место ему подходит. "
    "%(note)s",
    "Никто не помнит, когда это началось, но к этому году ясно: в земле "
    "по имени %(region)s живёт %(who_short)s. %(note)s",
    "Охотники находят логово и не находят дороги обратно. Так мир узнаёт, "
    "что %(who)s теперь здесь. %(note)s",
)

LAIR_LINES = (
    "Логово своё он устраивает там, куда не ходят.",
    "Место выбрано с умом: подойти можно только с одной стороны.",
    "Логово находят быстро — по тому, что вокруг него не живёт никто.",
)


def _note(text: str) -> str:
    """Приметы породы записаны обрывками — в летописи это целая фраза."""
    text = (text or "").strip()
    if not text:
        return ""
    return cap(text) if text.endswith((".", "!", "?")) else cap(text) + "."


def awoken(rng, monster, region, note: str) -> tuple:
    text = rng.choice(WAKE_TEMPLATES) % {
        "who": beast_nom(monster), "who_short": monster.name,
        "region": region.name if region is not None else "безымянной",
        "place": region.name if region is not None else "той земле",
        "note": _note(note),
    }
    text = "%s %s" % (text, rng.choice(LAIR_LINES))
    return ("Чудовище: %s" % monster.name), cap(text)


HIDE_TEMPLATES = (
    "В городе по имени %(city)s появляется новый человек, о котором никто "
    "ничего "
    "толком не знает. Через тридцать лет он выглядит так же, как в день "
    "приезда. %(note)s",
    "Никто не замечает главного: %(who_short)s живёт среди людей и живёт "
    "давно. %(note)s",
    "Пропажи в городе по имени %(city)s списывают на зверя, на "
    "разбойников и на дурную воду. %(note)s",
    "%(who)s селится в городе по имени %(city)s и заводит знакомства "
    "с теми, кого не хватятся. %(note)s",
)


def hidden(rng, monster, settlement, note: str) -> tuple:
    text = rng.choice(HIDE_TEMPLATES) % {
        "who": beast_nom(monster), "who_short": monster.name,
        "city": settlement.name if settlement is not None else "городе",
        "note": _note(note),
    }
    return ("Ночная тварь: %s" % monster.name), cap(text)


# ---------------------------------------------------------------------------
# Разор
# ---------------------------------------------------------------------------

RAID_TEMPLATES = (
    "%(who)s выходит из логова и разоряет округу. Убитых считают "
    "сотнями, скот не считают вовсе.",
    "Деревни в земле по имени %(region)s пустеют: кто мог — ушёл, кто не "
    "мог — остался там навсегда.",
    "Этот год в тех краях называют годом %(name)s и не поминают всуе.",
    "%(who)s берёт своё: сожжённые поля, угнанный скот и тишина по "
    "хуторам.",
    "Дорогу через те земли закрывают: купцы отказываются идти ни за "
    "какие деньги.",
)

TOLL_LINES = (
    "На счету у него теперь %(kills)s.",
    "Счёт убитых доходит до %(kills)s, и это только те, кого нашли.",
    "К концу года счёт идёт на %(kills)s.",
)


def raided(rng, monster, region, dead: int) -> tuple:
    text = rng.choice(RAID_TEMPLATES) % {
        "who": beast_nom(monster), "name": monster.name,
        "region": region.name if region is not None else "тех краях",
    }
    if dead > 0:
        text = "%s %s" % (text, rng.choice(TOLL_LINES)
                          % {"kills": "%d душ" % monster.kills})
    return ("Разор: %s" % monster.name), cap(text)


FEED_TEMPLATES = (
    "В городе по имени %(city)s снова пропадают люди. Считают, что "
    "виноват зверь.",
    "Пропажи в городе по имени %(city)s идут по одной в год, и это "
    "тянется дольше, чем живут те, кто мог бы заметить.",
    "Город хоронит очередного пропавшего без тела и без объяснений.",
)


def fed(rng, monster, settlement) -> tuple:
    text = rng.choice(FEED_TEMPLATES) % {
        "city": settlement.name if settlement is not None else "городе"}
    return ("Пропажи: %s" % (settlement.name if settlement is not None
                             else monster.name)), cap(text)


# ---------------------------------------------------------------------------
# Охота
# ---------------------------------------------------------------------------

HUNT_FAIL = (
    "%(hero)s уходит за головой %(name)s и не возвращается. Из отряда не "
    "возвращается никто.",
    "Охота кончается, не начавшись: %(hero)s гибнет в первый же день.",
    "%(hero)s находит логово — и это последнее, что о нём известно.",
    "Отряд %(hero)s отбивают от логова, и половину отряда не досчитываются.",
)

HUNT_WIN = (
    "%(hero)s убивает %(name)s после %(span)s охоты. Голову привозят в "
    "город и выставляют на площади.",
    "Бой длится с рассвета до темноты, и к темноте %(who_short)s мёртв. "
    "Победителя зовут %(hero)s.",
    "%(hero)s делает то, чего не сделали до него шестеро: %(who_short)s "
    "убит.",
    "Всё решает не сила, а то, что %(hero)s знает о нём больше прочих. "
    "%(who_short)s не встаёт.",
)

HOARD_LINES = (
    "Логово оказывается полно золота: %(riches)d.",
    "Клад из логова делят на месте, и делёж выходит не без крови. Всего "
    "там %(riches)d.",
    "Добра в логове больше, чем в казне иной державы: %(riches)d.",
)


def hunt_failed(rng, monster, hero) -> tuple:
    text = rng.choice(HUNT_FAIL) % {
        "hero": hero.name, "name": monster.name}
    return ("Охота не удалась: %s" % monster.name), cap(text)


def hunt_won(rng, monster, hero, years: int, riches: int) -> tuple:
    text = rng.choice(HUNT_WIN) % {
        "hero": hero.name, "name": monster.name,
        "who_short": monster.name, "span": years_text(max(1, years)),
    }
    if riches > 0:
        text = "%s %s" % (text, rng.choice(HOARD_LINES) % {"riches": riches})
    return ("Чудовище убито: %s" % monster.name), cap(text)


EXPOSE_TEMPLATES = (
    "%(hero)s замечает то, что не замечали сто лет: %(who_short)s не "
    "человек. Разоблачение стоит городу большой крови.",
    "Истина выходит наружу случайно — и город хватается за факелы. "
    "%(who_short)s раскрыт, и правил он дольше, чем кто-либо думал.",
    "Счёт пропавших наконец сводят с чьим-то именем. Имя это — "
    "%(who_short)s.",
)


def exposed(rng, monster, hero, years: int) -> tuple:
    text = rng.choice(EXPOSE_TEMPLATES) % {
        "hero": hero.name if hero is not None else "новый жрец",
        "who_short": monster.name,
    }
    text = "%s Прожил он среди людей %s." % (text, years_text(max(1, years)))
    return ("Разоблачён: %s" % monster.name), cap(text)


# ---------------------------------------------------------------------------
# След
# ---------------------------------------------------------------------------

LEGACY_LINES = (
    "Из костей его делают то, что потом носят короли.",
    "Череп вешают над воротами, и город ещё долго зовут по нему.",
    "Место, где он лежал, обходят стороной и через сто лет.",
    "Об этой охоте складывают песню, и в песне всё было иначе.",
)


def legacy(rng) -> str:
    return rng.choice(LEGACY_LINES)
