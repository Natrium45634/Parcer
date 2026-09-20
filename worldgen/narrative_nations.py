# -*- coding: utf-8 -*-
"""Тексты о народах внутри державы: завоевания, указы, восстания, врастание.

Правила письма те же, что и во всей летописи, и они не про красоту, а про
падежи:

* сгенерированные имена — людей, стран, земель — стоят только
  в именительном; склонять их некому;
* место называется через готовый оборот ``where()`` — «в землях под именем
  Синяя Чащоба», — потому что «в Синяя Чащоба» написать нельзя;
* названия рас склоняются: они не генерируются, а лежат в списке, и у
  каждой заранее есть форма родительного и винительного («эльфов»);
* глагол при названии народа стоит во множественном числе: не «эльфы
  берётся за оружие», а «берутся».
"""

from __future__ import annotations

from .narrative import cap, where
from .narrative_dynasty import polity_gen
from .nations import (EQUAL, PURGE, SLAVERY, SUBJECTS, UNEQUAL,
                      POLICY_DESCRIPTIONS)

__all__ = ["conquest", "decree", "oppression", "revolt", "assimilation",
           "titular_shift"]

_POLICIES = (EQUAL, SUBJECTS, UNEQUAL, SLAVERY, PURGE)


# --- завоевание --------------------------------------------------------

CONQUEST_TEMPLATES = (
    "%(winner)s забирает у %(loser_gen)s %(count)s. Войско ведёт %(general)s.",
    "Война кончается тем, чем кончаются войны: %(count)s переходят под руку "
    "%(winner_gen)s. Победу приносит %(general)s.",
    "%(general_cap)s приводит войско к воротам, и %(count)s меняют хозяина. "
    "Теперь это земли %(winner_gen)s.",
    "Границу двигают силой: %(winner)s прирастает за счёт %(loser_gen)s на "
    "%(count)s. Полководец — %(general)s.",
    "%(winner)s кончает спор железом и берёт %(count)s. Во главе войска "
    "стоит %(general)s.",
)

CONQUEST_AFTERMATH = {
    EQUAL: (
        "Победитель не трогает ни храмов, ни старейшин: новым подданным "
        "обещаны те же права, что и своим.",
        "Города берут почти без крови и оставляют им их собственный суд.",
    ),
    SUBJECTS: (
        "Новым подданным оставляют обычаи, но не власть.",
        "Знать покорённых приводят к присяге и отпускают по домам.",
    ),
    UNEQUAL: (
        "Покорённых облагают двойной податью и запрещают им носить оружие.",
        "Новым подданным отводят окраины города и свой, отдельный суд.",
    ),
    SLAVERY: (
        "Уцелевших уводят в цепях: это добыча, а не подданные.",
        "Пленных делят как скот — часть остаётся, часть уходит на торги.",
    ),
    PURGE: (
        "Города не берут, а вычищают. Имена их остаются только в летописи.",
        "Победители не считают пленных: их и не берут.",
    ),
}


CAPITAL_MOVE_TEMPLATES = (
    "Престольный город по имени %(lost)s лежит в пепле, и корону "
    "переносят: отныне государь сидит в городе по имени %(seat)s.",
    "Державе нужен престол, а прежнего больше нет: двор, казну и архив "
    "перевозят в город по имени %(seat)s.",
    "После гибели города по имени %(lost)s державу держит уже не он. "
    "Новым престолом становится город по имени %(seat)s.",
    "Корона переезжает. Город по имени %(lost)s остаётся в названиях "
    "улиц и в именах родов, престолом становится %(seat)s.",
)

CAPITAL_MOVE_LINES = (
    "Часть знати переезжать отказывается и остаётся при пепелище.",
    "Первые годы новый престол зовут временным, потом перестают.",
    "Казну везут под охраной и довозят не всю.",
    "Печати перерезают заново: старая была с именем павшего города.",
    "Те, кто помнит прежний двор, ещё поколение считают этот ненастоящим.",
)


def capital_moved(rng, polity, seat, lost_name: str) -> tuple:
    """Столицу переносят: престольный город пал."""
    text = rng.choice(CAPITAL_MOVE_TEMPLATES) % {
        "lost": lost_name, "seat": seat.name}
    text = "%s %s" % (text, rng.choice(CAPITAL_MOVE_LINES))
    return ("Перенос престола: %s" % polity.name), cap(text)


def conquest(rng, winner, loser, general, taken, policy):
    data = {
        "winner": winner.full_name,
        "winner_gen": polity_gen(winner),
        "loser_gen": polity_gen(loser),
        "count": _cities(len(taken)),
        "general": general.name,
        "general_cap": cap(general.name),
    }
    lines = [rng.choice(CONQUEST_TEMPLATES) % data]
    tail = CONQUEST_AFTERMATH.get(policy)
    if tail:
        lines.append(rng.choice(tail))
    return ("Завоевание: %s" % winner.name, cap(" ".join(lines)))


def _cities(count: int) -> str:
    if count == 1:
        return "один город"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "%d города" % count
    return "%d городов" % count


# --- указ о положении народов ------------------------------------------

DECREE_TEMPLATES = (
    "%(ruler_cap)s меняет закон о чужих народах. Отныне %(what)s.",
    "Новый указ ложится на страну: %(what)s. Печать ставит %(ruler)s.",
    "Совет спорит недолго. Решают так: %(what)s.",
    "%(ruler_cap)s подписывает закон, о котором будут помнить дольше, чем "
    "о самом правителе: %(what)s.",
)

DECREE_REASON_HARSH = (
    "Поводом называют мятеж, но настоящая причина — страх.",
    "Говорят, так надёжнее. Надёжнее не становится.",
    "Ропот в окраинных городах решают унять раз и навсегда.",
)
DECREE_REASON_SOFT = (
    "Говорят, держава устала бояться собственных подданных.",
    "Казна считает, что покорный подданный платит больше, чем испуганный.",
    "После долгих лет крови кто-то решается на обратное.",
)


def decree(rng, polity, ruler, old_policy, new_policy, harsher_now: bool):
    name = ruler.name if ruler is not None else "совет знати"
    data = {
        "ruler": name,
        "ruler_cap": cap(name),
        "what": POLICY_DESCRIPTIONS.get(new_policy, new_policy),
    }
    lines = [rng.choice(DECREE_TEMPLATES) % data,
             rng.choice(DECREE_REASON_HARSH if harsher_now
                        else DECREE_REASON_SOFT)]
    return ("Указ о народах: %s" % polity.name, cap(" ".join(lines)))


# --- притеснение -------------------------------------------------------
# «вырезают эльфов» — винительный падеж, у одушевлённых он совпадает
# с родительным, который у каждой расы хранится заранее.

MASSACRE_TEMPLATES = (
    "%(where_cap)s вырезают %(folk_acc)s. Счёт идёт на %(dead)s.",
    "То, что потом назовут резнёй, начинается с обыска и кончается пожаром: "
    "%(where)s не остаётся %(folk_gen)s. Погибших — %(dead)s.",
    "Целый край пустеет за одну зиму: %(where)s больше нет %(folk_gen)s. "
    "Погибших — %(dead)s.",
)
ENSLAVE_TEMPLATES = (
    "%(folk_acc_cap)s уводят на торги: %(dead)s уходят в чужие руки.",
    "Облава %(where)s даёт %(dead)s невольников. Их не вернут.",
    "Долговые списки переписывают так, что %(folk_nom)s разом оказываются "
    "в неволе: %(dead)s.",
)


def oppression(rng, polity, race, region, dead, policy):
    spot = where(rng, region)
    data = {
        "where": spot,
        "where_cap": cap(spot),
        "folk_nom": race.name.lower(),
        "folk_gen": race.gen_plural,
        "folk_acc": race.gen_plural,
        "folk_acc_cap": cap(race.gen_plural),
        "dead": _souls(dead),
    }
    if policy == PURGE:
        return ("Резня: %s" % polity.name,
                cap(rng.choice(MASSACRE_TEMPLATES) % data))
    return ("Обращение в рабство: %s" % polity.name,
            cap(rng.choice(ENSLAVE_TEMPLATES) % data))


def _souls(count: int) -> str:
    if count >= 1000000:
        return "%.1f млн душ" % (count / 1000000.0)
    if count >= 1000:
        return "%d тысяч душ" % (count // 1000)
    return "%d душ" % count


# --- восстание ---------------------------------------------------------

REVOLT_OPENINGS = (
    "%(folk_nom_cap)s поднимаются. Во главе встаёт %(leader)s.",
    "Терпение кончается: %(where)s %(folk_nom)s берутся за оружие. Ведёт их "
    "%(leader)s.",
    "Восстание начинается с одного убитого сборщика податей и за месяц "
    "охватывает целый край. Имя вождя — %(leader)s.",
    "%(leader_cap)s поднимает %(folk_acc)s против державы, в которой они "
    "давно чужие.",
)

REVOLT_CRUSHED = (
    "Мятеж давят. %(leader_cap)s не доживает до суда.",
    "Восстание кончается ничем: войско державы приходит раньше, чем "
    "мятежники успевают собраться.",
    "Мятеж тонет в крови, и после него становится только хуже.",
)
REVOLT_FREEDOM = (
    "На этот раз держава не справляется, и на карте появляется %(new)s.",
    "Мятежники берут города и не отдают их. Так рождается %(new)s.",
    "Восстание перерастает в войну, война — в границу: отныне эти земли "
    "зовутся %(new)s.",
)
REVOLT_TAKEOVER = (
    "Мятежники не уходят из страны — они забирают её себе. На престол "
    "садится %(leader)s, и держава становится их державой.",
    "Восстание кончается тем, чего никто не ждал: %(leader_cap)s садится "
    "на престол, и титульным народом становятся %(folk_nom)s.",
    "Старая знать бежит, новая садится на её место: отныне страной правят "
    "%(folk_nom)s, а на престоле — %(leader)s.",
)


def revolt(rng, polity, race, leader, region, outcome, new_polity=None):
    data = {
        "folk_nom": race.name.lower(),
        "folk_nom_cap": race.name,
        "folk_acc": race.gen_plural,
        "where": where(rng, region),
        "leader": leader.name,
        "leader_cap": cap(leader.name),
        "new": new_polity.full_name if new_polity is not None else "новая держава",
    }
    lines = [rng.choice(REVOLT_OPENINGS) % data]
    if outcome == "crushed":
        lines.append(rng.choice(REVOLT_CRUSHED) % data)
        title = "Подавленное восстание: %s" % polity.name
    elif outcome == "freedom":
        lines.append(rng.choice(REVOLT_FREEDOM) % data)
        title = "Восстание: %s" % (new_polity.name if new_polity else polity.name)
    else:
        lines.append(rng.choice(REVOLT_TAKEOVER) % data)
        title = "Смена титульного народа: %s" % polity.name
    return (title, cap(" ".join(lines)))


# --- мирная смена титульного народа ------------------------------------

SHIFT_TEMPLATES = (
    "%(polity)s давно считает больше %(new_gen)s, чем %(old_gen)s, и "
    "однажды это признают вслух: на престол садится %(heir)s. Ни мятежа, "
    "ни крови — только долгий счёт поколений.",
    "Перепись показывает то, что и так все знали: %(new_gen)s в стране "
    "вдвое больше. Совет выбирает своим главой %(heir)s, и титульным "
    "народом становятся %(new_nom)s.",
    "Последний правитель прежнего рода не оставляет наследника, и корона "
    "%(polity_gen)s достаётся большинству. Её принимает %(heir)s.",
)


def titular_shift(rng, polity, old_race, new_race, heir):
    data = {
        "polity": polity.full_name,
        "polity_gen": polity_gen(polity),
        "old_gen": old_race.gen_plural,
        "new_gen": new_race.gen_plural,
        "new_nom": new_race.name.lower(),
        "heir": heir.name,
    }
    return ("Престол переходит к большинству: %s" % polity.name,
            cap(rng.choice(SHIFT_TEMPLATES) % data))


# --- мирное врастание --------------------------------------------------

ASSIMILATION_TEMPLATES = (
    "%(where_cap)s перестают считать, кто чьих кровей: %(folk_gen)s тут "
    "уже не отличить от прочих подданных %(polity_gen)s.",
    "Третье поколение, выросшее %(where)s, говорит на языке державы и носит "
    "её имена. Отдельным народом %(folk_gen)s больше не числят.",
    "Край тихо меняет облик: смешанные браки делают то, чего не сделали "
    "ни указы, ни войско. О %(folk_prep)s тут вспоминают только старики.",
)


def assimilation(rng, polity, race, region):
    spot = where(rng, region)
    data = {
        "where": spot,
        "where_cap": cap(spot),
        "folk_gen": race.gen_plural,
        "folk_prep": race.gen_plural,
        "polity_gen": polity_gen(polity),
    }
    return ("Врастание: %s" % polity.name,
            cap(rng.choice(ASSIMILATION_TEMPLATES) % data))
