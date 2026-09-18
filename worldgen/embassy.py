# -*- coding: utf-8 -*-
"""Посольства: с каким наказом едут ко двору и с чем возвращаются.

Договор не появляется сам собой. Сперва едет посол — со свитой, с дарами
и с наказом, который ему дали дома. Ему кланяются или его высмеивают,
его слушают месяц или гонят через день, а изредка его убивают — и тогда
кровь посла становится поводом к войне лучше любой спорной межы.

Здесь лежит устройство переговоров: с чем едут (``PURPOSES``), что везут
в дар (``GIFTS``) и как двор решает, чем ответить (``verdict``). Сами
события пишет ``systems/embassy.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import diplomacy as dip
from . import goods as goods_mod
from . import races as races_mod
from . import rulers

# --- чем кончились переговоры -------------------------------------------
ACCEPT = "принято"
REFUSE = "отказано"
INSULT = "посла выставили"
BLOOD = "посла убили"


@dataclass(frozen=True)
class Purpose:
    """Наказ послу: чего просить, насколько это дерзко и что выйдет."""

    key: str
    what: str                # «просить союза»
    errand: str              # как наказ звучит в грамоте
    base: float              # с какой охотой на это соглашаются вообще
    weight: float            # как часто с этим вообще ездят
    pride: float             # насколько просьба задевает гордость хозяев


PURPOSES = (
    Purpose("почёт", "поклониться двору",
            "просто поклониться новому государю и поглядеть на его двор",
            0.80, 1.6, 0.0),
    Purpose("межа", "развести межу миром",
            "развести спорную межу без войны, по старым грамотам",
            0.55, 1.4, 0.15),
    Purpose("торг", "открыть торг",
            "открыть купцам дорогу в обе стороны и сбавить пошлины",
            0.60, 1.5, 0.05),
    Purpose("союз", "предложить союз",
            "предложить союз против общего недруга",
            0.40, 1.2, 0.10),
    Purpose("брак", "сватать наследника",
            "сватать наследника чужого дома за своего",
            0.42, 1.0, 0.20),
    Purpose("мир", "просить мира",
            "прекратить войну и развести войска по домам",
            0.45, 2.2, 0.10),
    Purpose("помощь", "звать на помощь",
            "звать союзника в уже идущую войну",
            0.45, 1.1, 0.10),
    Purpose("проход", "просить прохода",
            "пропустить войско через чужие земли без обиды для жителей",
            0.35, 0.9, 0.35),
    Purpose("вера", "вступиться за единоверцев",
            "не притеснять тех, кто молится тому же богу",
            0.45, 1.0, 0.30),
    Purpose("выдача", "требовать выдачи",
            "выдать головой беглеца, укрывшегося при чужом дворе",
            0.30, 0.9, 0.45),
    Purpose("выкуп", "выкупить пленных",
            "выкупить пленных за серебро и вернуть их домой",
            0.62, 1.0, 0.05),
    Purpose("дань", "требовать дани",
            "платить дань и впредь считаться младшим",
            0.14, 0.8, 0.85),
    Purpose("покорность", "требовать покорности",
            "признать чужое старшинство и склонить знамёна",
            0.10, 0.5, 1.00),
)

PURPOSES_BY_KEY = {item.key: item for item in PURPOSES}

# Наказы, с которыми едут только на войне, и наказы, только в мирное время.
WARTIME = ("мир", "выкуп", "помощь")
PEACETIME = ("торг", "союз", "брак", "межа", "почёт")


# ---------------------------------------------------------------------------
# Дары
# ---------------------------------------------------------------------------

GIFTS_BY_GOOD = {
    goods_mod.GRAIN: ("сорок возов отборного зерна",
                      "хлеб нового умолота в резных ларях"),
    goods_mod.MEAT: ("табун степных коней", "стадо белых быков"),
    goods_mod.FISH: ("бочки солёной рыбы и жемчужные раковины",
                     "жемчуг с дальней отмели"),
    goods_mod.TIMBER: ("корабельный лес в три обхвата",
                       "ладью, срубленную без единого гвоздя"),
    goods_mod.STONE: ("изваяние из цельного камня",
                      "плиты редкого камня на пол тронной палаты"),
    goods_mod.METAL: ("клинок небывалой ковки", "кольчугу двойного плетения",
                      "доспех, снятый с побеждённого врага"),
    goods_mod.SALT: ("соль в серебряных сосудах", "воз соли чистой, как снег"),
    goods_mod.WOOL: ("ковры, тканные три зимы", "полотно тоньше дыхания"),
    goods_mod.FURS: ("чёрные меха северных зверей", "шубу до самой земли"),
    goods_mod.WINE: ("вино столетней выдержки", "масло в расписных кувшинах"),
    goods_mod.SPICE: ("ларец пряностей с дальних берегов",
                      "благовония, каких при этом дворе не нюхали"),
    goods_mod.GEMS: ("венец с самоцветами", "горсть неогранённых камней"),
    goods_mod.REAGENTS: ("снадобья, что лечат раны за ночь",
                         "запечатанный сосуд с чародейным составом"),
}

PLAIN_GIFTS = (
    "ловчих птиц в золочёных клетках", "книгу, переписанную от руки",
    "карту неведомых земель", "тонкой работы часы с водой",
    "дюжину породистых псов", "зверя, невиданного в этих краях",
    "серебро в счёт будущей дружбы",
)


def gift_for(rng, world, sender) -> str:
    """Дар — из того, чем держава богата: своим хвалятся охотнее чужого."""
    options = []
    for good, _ in (sender.surpluses or ())[:4]:
        options.extend(GIFTS_BY_GOOD.get(good, ()))
    if not options:
        options = list(PLAIN_GIFTS)
    return rng.choice(sorted(set(options)))


# ---------------------------------------------------------------------------
# Что ответит двор
# ---------------------------------------------------------------------------

BLOOD_BASE = 0.010          # как часто посольство кончается кровью
INSULT_BASE = 0.10


def choose(rng, ctx, sender, host, at_war: bool) -> Purpose:
    """С каким наказом поедет посол к этому двору именно сейчас."""
    world = ctx.world
    relation = dip.relation(sender, host.id)
    options = []
    for purpose in PURPOSES:
        if at_war and purpose.key in PEACETIME:
            continue
        if not at_war and purpose.key in WARTIME:
            continue
        weight = purpose.weight
        if purpose.key == "дань" or purpose.key == "покорность":
            # Требовать дани едут только от силы.
            if sender.population < host.population * 1.8:
                continue
            weight *= 1.0 + 2.0 * max(0.0, -relation)
        if purpose.key == "союз":
            if relation < 0.2:
                continue
            weight *= 1.0 + 2.5 * relation
        if purpose.key == "брак" and not host.house_id:
            continue
        if purpose.key == "торг" and not (sender.shortages or sender.surpluses):
            continue
        if purpose.key == "вера":
            if not sender.faith_id or sender.faith_id == host.faith_id:
                continue
            weight *= 1.6
        if purpose.key == "проход":
            if not world.wars_of(sender):
                continue
        if purpose.key == "помощь" and not _allies(world, sender, host):
            weight *= 0.3
        if purpose.key == "выдача":
            weight *= 1.0 + 1.5 * max(0.0, -relation)
        if purpose.key == "межа" and relation > 0.5:
            weight *= 0.4
        options.append((purpose, max(0.05, weight)))
    if not options:
        return PURPOSES_BY_KEY["почёт"]
    return rng.weighted(options)


def _allies(world, sender, host) -> bool:
    pact = world.pact_between(sender.id, host.id)
    return pact is not None and pact.kind in (dip.ALLIANCE, dip.MARRIAGE)


def verdict(rng, world, sender, host, purpose, gift: bool, envoy_skill: float):
    """Чем двор ответит послу.

    Считается всё, что при настоящем дворе и считали бы: давняя приязнь,
    родство народов, нрав государя, дерзость просьбы, богатство даров и
    умение самого посла. Худший исход — кровь: он редок, но случается, и
    отмывать её потом приходится войной.
    """
    relation = dip.relation(host, sender.id)
    affinity = dip.racial_affinity(races_mod.get_race(host.race_id),
                                   races_mod.get_race(sender.race_id))
    chance = purpose.base
    chance += 0.40 * relation
    chance += 0.25 * affinity
    chance += 0.09 * (envoy_skill - 5.0) / 5.0
    if gift:
        chance += 0.10
    # Нрав государя: обходительный слушает, крутой — выставляет.
    chance += 0.16 * (1.0 - rulers.court_grip(world, host))
    chance -= purpose.pride * 0.35 * max(0.0, -relation + 0.2)
    if host.weariness > 0.4 and purpose.key in ("мир", "выкуп"):
        chance += 0.25 * host.weariness

    chance = max(0.02, min(0.94, chance))
    if rng.chance(chance):
        return ACCEPT

    # Отказали — но насколько грубо?
    anger = purpose.pride + max(0.0, -relation) + max(0.0, -affinity)
    harsh = rulers.harshness(world, host)
    if rng.chance(min(0.45, BLOOD_BASE * (1.0 + 3.0 * anger) * (1.0 + harsh))):
        return BLOOD
    if rng.chance(min(0.75, INSULT_BASE + 0.35 * anger + 0.20 * max(0.0, harsh))):
        return INSULT
    return REFUSE


# ---------------------------------------------------------------------------
# Что после этого делается с отношениями
# ---------------------------------------------------------------------------

RELATION_SHIFT = {
    ACCEPT: 0.16,
    REFUSE: -0.05,
    INSULT: -0.22,
    BLOOD: -0.75,
}
