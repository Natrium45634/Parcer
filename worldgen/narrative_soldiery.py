# -*- coding: utf-8 -*-
"""Тексты о крепостях и вольных ротах."""

from __future__ import annotations

from .morph import genitive_noun
from .narrative import cap

FORT_KINDS = ("крепость", "застава", "твердыня", "бастион", "форт",
              "сторожевая башня")
FORT_KINDS_MOUNTAIN = ("твердыня", "крепость", "горный форт", "застава")
FORT_KINDS_COAST = ("морская крепость", "береговой форт", "сторожевая башня",
                    "застава")


def fort_kind(rng, race, region) -> str:
    if region.terrain in ("горы", "холмы", "подземелье"):
        return rng.choice(FORT_KINDS_MOUNTAIN)
    if region.terrain in ("побережье", "острова"):
        return rng.choice(FORT_KINDS_COAST)
    return rng.choice(FORT_KINDS)


def polity_gen(polity) -> str:
    return "%s %s" % (genitive_noun(polity.form).lower(), polity.name)


BUILT_TEMPLATES = (
    "%(polity)s закладывает %(fort)s в земле по имени %(region)s: место "
    "узкое, и кто его держит, держит дорогу.",
    "На меже поднимают %(fort)s. Камень возят три года.",
    "%(fort_cap)s встаёт там, где прежде стояли только дозоры.",
    "У брода в земле по имени %(region)s ставят %(fort)s — и берут за "
    "переправу пошлину в тот же год.",
    "Стены кладут из здешнего камня, и оттого их видно издалека: "
    "%(fort_cap)s готова.",
    "Перевал запирают: там, где проходило войско, теперь стоит %(fort)s.",
)

BUILT_NOTES = (
    "Гарнизон набирают из соседних деревень.",
    "Строили дольше, чем обещали, и дороже, чем считали.",
    "Колодец бьют внутри стен — на случай долгой осады.",
    "Первый комендант получает землю вокруг в кормление.",
    "Соседи присылают посольство с вопросом, против кого это.",
    "Над воротами высекают год и имя государя.",
)


def fort_built(rng, fortress, polity, region, ruler):
    data = {
        "polity": polity.full_name, "fort": fortress.full_name,
        "fort_cap": cap(fortress.full_name), "region": region.name,
    }
    return ("Новая крепость: %s" % fortress.name,
            "%s %s" % (cap(rng.choice(BUILT_TEMPLATES) % data),
                       rng.choice(BUILT_NOTES)))


TAKEN_TEMPLATES = (
    "%(fort_cap)s переходит к %(who_dat)s.",
    "Над %(fort_ins)s поднимают чужое знамя.",
    "%(fort_cap)s взята. Гарнизон выпускают без оружия.",
    "Ворота открывают на третий день: %(fort)s меняет хозяина.",
)

TAKEN_AGAIN = (
    "Эта крепость меняет знамя не впервые: за её стенами уже не помнят, "
    "чьи они.",
    "Старики в округе считают хозяев крепости по пальцам и сбиваются.",
    "Кладку латали столько раз, что первоначального камня почти не видно.",
)

QUIET_TEMPLATES = (
    "Пустующую %(fort)s занимает %(who)s: гарнизон входит без боя.",
    "Брошенные стены обживают заново — %(fort)s снова при знамени.",
    "%(fort_cap)s стоит на земле %(who_gen)s, и туда наконец ставят гарнизон.",
)


def fort_taken(rng, fortress, polity, previous, retaken: bool):
    data = {
        "fort": fortress.full_name, "fort_cap": cap(fortress.full_name),
        "fort_ins": "%s %s" % (fortress.kind.lower(), fortress.name),
        "who": polity.full_name, "who_gen": polity_gen(polity),
        "who_dat": "%s %s" % (polity.form.lower(), polity.name),
    }
    if not retaken:
        return ("Крепость при знамени: %s" % fortress.name,
                cap(rng.choice(QUIET_TEMPLATES) % data))
    body = cap(rng.choice(TAKEN_TEMPLATES) % data)
    if fortress.times_taken >= 2 and rng.chance(0.7):
        body = "%s %s" % (body, rng.choice(TAKEN_AGAIN))
    return ("Взятие крепости: %s" % fortress.name, body)


RAZED_TEMPLATES = (
    "%(fort_cap)s срыта до основания: победитель не желает, чтобы она "
    "досталась кому-то ещё.",
    "Стены валят и камень растаскивают на дома — от %(fort_gen)s остаётся "
    "поле.",
    "%(fort_cap)s взрывают подкопом. Больше её не отстроят.",
)

LOST_TEMPLATES = (
    "%(fort_cap)s рассыпается от времени: гарнизона в ней не было уже век.",
    "Пустые стены %(fort_gen)s обваливаются одна за другой.",
    "О %(fort_gen)s вспоминают только пастухи, что гоняют скот через "
    "провалившиеся ворота.",
)


def _fort_gen(fortress) -> str:
    return "%s %s" % (genitive_noun(fortress.kind).lower(), fortress.name)


def fort_razed(rng, fortress):
    data = {"fort_cap": cap(fortress.full_name), "fort_gen": _fort_gen(fortress)}
    return ("Крепость срыта: %s" % fortress.name,
            cap(rng.choice(RAZED_TEMPLATES) % data))


def fort_lost(rng, fortress):
    data = {"fort_cap": cap(fortress.full_name), "fort_gen": _fort_gen(fortress)}
    return ("Заброшенная крепость: %s" % fortress.name,
            cap(rng.choice(LOST_TEMPLATES) % data))


SIEGE_FORT_START = (
    "%(fort_cap)s обложена со всех сторон. Под её стенами садятся надолго: "
    "обойти её нельзя, а оставить в тылу — тем более.",
    "Войско встаёт лагерем под стенами %(fort_gen)s. Дорога дальше идёт "
    "только через неё.",
    "%(fort_cap)s заперта. Осадные машины собирают на месте — везти их было "
    "бы дольше.",
    "Ров вокруг %(fort_gen)s засыпают три недели, и всё это время со стен "
    "стреляют.",
    "Осада %(fort_gen)s начинается с того, что вырубают всё живое на "
    "полдня пути вокруг.",
    "Гарнизону %(fort_gen)s предлагают сдаться. Ответ был коротким.",
    "%(fort_cap)s стоит на пути войска, и войско останавливается.",
    "Под стенами %(fort_gen)s ставят два кольца: одно против гарнизона, "
    "другое против тех, кто придёт на выручку.",
)

SIEGE_FORT_HOLD = (
    "Приступы отбиты, подкопы залиты водой, а в лагере осаждающих "
    "начинается своя беда.",
    "Со стен считают костры в лагере и находят, что их стало меньше.",
    "Колодец внутри стен не иссякает — на это и был расчёт строителей.",
    "Перемирие на день, чтобы убрать тела, и снова всё то же.",
    "Тарана хватает на трое ворот и ни на одни больше.",
    "Гарнизон делает вылазку и возвращается не весь, но с провиантом.",
)

SIEGE_FORT_FALL = (
    "Ворота открывают изнутри — так кончается большинство осад.",
    "Стена рушится после третьего подкопа.",
    "Гарнизон сдаётся, когда кончается вода.",
    "Приступ удаётся ночью и стоит дороже полевого сражения.",
    "Последних защитников находят в башне, и они уже не могут держать оружие.",
)

SIEGE_FORT_LIFTED = (
    "стоять под стенами дольше нечем",
    "подошло войско на выручку",
    "в осадном лагере начался мор",
    "зима разогнала осаждающих вернее вылазки",
    "вести из дому оказались хуже, чем дела под стенами",
)


def fort_siege(rng, fortress, stage: str, years_word: str = ""):
    data = {"fort_cap": cap(fortress.full_name),
            "fort_gen": _fort_gen(fortress)}
    if stage == "начало":
        return ("Осада крепости: %s" % fortress.name,
                cap(rng.choice(SIEGE_FORT_START) % data))
    if stage == "держится":
        return ("Крепость держится: %s" % fortress.name,
                "%s стоит %s. %s" % (cap(fortress.full_name), years_word,
                                     rng.choice(SIEGE_FORT_HOLD)))
    if stage == "снята":
        return ("Осада крепости снята: %s" % fortress.name,
                "Осаду %s снимают: %s." % (fortress.full_name,
                                           rng.choice(SIEGE_FORT_LIFTED)))
    return ("Взятие крепости: %s" % fortress.name,
            "%s взята. %s" % (cap(fortress.full_name),
                              rng.choice(SIEGE_FORT_FALL)))


# ---------------------------------------------------------------------------
# Вольные роты
# ---------------------------------------------------------------------------

COMPANY_BORN = (
    "После войны остаются те, кто ничего другого не умеет: так возникает "
    "%(company)s под началом %(captain)s.",
    "Распущенное войско расходиться не хочет. Вместо этого оно нанимается "
    "целиком: %(company)s, капитан — %(captain)s.",
    "Ветераны сбиваются в отряд и дают ему имя: %(company)s. Ведёт их "
    "%(captain)s.",
    "%(company_cap)s собирается из тех, кому некуда возвращаться. Во главе "
    "— %(captain)s.",
)

COMPANY_BORN_NOTES = (
    "Плату требуют вперёд и серебром.",
    "Знамя шьют из чужого плаща.",
    "Половина роты — не своего народа, и никого это не смущает.",
    "Договор пишут на двух листах: один для нанимателя, другой для себя.",
    "Клянутся не грабить тех, кто платит. Про остальных не уточняют.",
)


def company_born(rng, company, captain, polity, reason: str = ""):
    data = {"company": company.full_name, "company_cap": cap(company.full_name),
            "captain": captain.name}
    return ("Вольная рота: %s" % company.name,
            "%s %s" % (cap(rng.choice(COMPANY_BORN) % data),
                       rng.choice(COMPANY_BORN_NOTES)))


COMPANY_HIRED = (
    "%(polity)s нанимает %(company_acc)s: платить чужой кровью дешевле, "
    "чем своей.",
    "Договор о найме подписан: %(company)s идёт под чужое знамя за "
    "серебро.",
    "%(company_cap)s нанимается к %(polity_dat)s. Условия знают обе стороны "
    "и обе им не верят.",
)


def company_hired(rng, company, polity):
    data = {
        "polity": polity.full_name,
        "polity_dat": "%s %s" % (polity.form.lower(), polity.name),
        "company": company.full_name, "company_cap": cap(company.full_name),
        "company_acc": company.full_name,
    }
    return ("Наём: %s" % company.name,
            cap(rng.choice(COMPANY_HIRED) % data))


COMPANY_RAID = (
    "%(company_cap)s, оставшись без найма, кормится сама: город по имени "
    "%(city)s теряет %(loss)d душ.",
    "Без нанимателя рота становится бедой: %(city_cap)s разграблен.",
    "%(company_cap)s берёт с города по имени %(city)s «плату за постой». "
    "Плата выходит в %(loss)d жизней.",
    "Наёмники не расходятся, а переходят на подножный корм. Городу по "
    "имени %(city)s это стоит %(loss)d душ.",
)


def company_raid(rng, company, settlement, loss: int):
    data = {"company_cap": cap(company.full_name), "city": settlement.name,
            "city_cap": cap("%s %s" % (settlement.kind.lower(),
                                       settlement.name)),
            "loss": max(1, loss)}
    return ("Разбой наёмников: %s" % settlement.name,
            cap(rng.choice(COMPANY_RAID) % data))


COMPANY_GONE = (
    "%(company_cap)s расходится: серебра нет, войны тоже.",
    "Роту распускают. Кто-то садится на землю, кто-то уходит к соседям.",
    "Знамя %(company_gen)s сворачивают и оставляют в кабаке в залог.",
)


def company_gone(rng, company):
    data = {"company_cap": cap(company.full_name),
            "company_gen": "вольной роты «%s»" % company.name}
    return ("Конец вольной роты: %s" % company.name,
            cap(rng.choice(COMPANY_GONE) % data))
