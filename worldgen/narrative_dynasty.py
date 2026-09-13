# -*- coding: utf-8 -*-
"""Тексты о династиях: восшествия, перевороты, роды и браки.

Правила те же, что и в narrative.py: имена всегда в именительном падеже,
глаголы — в настоящем времени третьего лица, никаких причастий, которые
пришлось бы согласовывать с придуманным словом.
"""

from __future__ import annotations

from .morph import accusative_noun, dative_noun, genitive_noun
from .narrative import cap
from .races import (ABSOLUTE_PRIMOGENITURE, COUNCIL, ELECTIVE, MALE_PRIMOGENITURE,
                    MATRILINEAL, SENIORITY, STRENGTH)
from .timeline import years_text


def by_sex(pair, sex: str) -> str:
    return pair[1] if (sex == "f" and len(pair) > 1) else pair[0]


def with_title(figure) -> str:
    """«король Ронвальд II Альдеринг»."""
    if figure.titles:
        return "%s %s" % (figure.titles[0].lower(), figure.name)
    return figure.name


def house_nom(house) -> str:
    return house.full_name


def house_gen(house) -> str:
    return "%s %s" % (genitive_noun(house.word).lower(), house.name)


def house_acc(house) -> str:
    return "%s %s" % (accusative_noun(house.word).lower(), house.name)


def house_dat(house) -> str:
    return "%s %s" % (dative_noun(house.word).lower(), house.name)


def polity_gen(polity) -> str:
    """«Королевства Броктон», «Вольного Союза Эйкмарк»."""
    return "%s %s" % (genitive_noun(polity.form).lower(), polity.name)


def ruler_word(sex: str, case: str = "nom") -> str:
    """«новый правитель» / «новая правительница» в нужном падеже."""
    forms = {
        "nom": ("новый правитель", "новая правительница"),
        "ins": ("новым правителем", "новой правительницей"),
    }[case]
    return by_sex(forms, sex)


# ---------------------------------------------------------------------------
# Рождение и угасание родов
# ---------------------------------------------------------------------------

HOUSE_FOUND_TEMPLATES = (
    "%(founder_given)s кладёт начало новому роду: %(house)s. "
    "Родовое гнездо — %(seat)s.",
    "С этого дня потомки основателя носят одно имя — %(surname)s. Так "
    "появляется %(house)s; родовое гнездо — %(seat)s.",
    "%(founder_given)s основывает %(house_acc)s. Род берёт себе %(seat_acc)s "
    "и герб по своему вкусу.",
    "Имя %(surname)s впервые записано как родовое: %(founder_given)s собирает "
    "вокруг себя родню и слуг. Гнездо рода — %(seat)s.",
    "Родовое имя %(surname)s входит в списки знати. Начало ему кладёт "
    "%(founder_given)s.",
)

ROYAL_HOUSE_TEMPLATES = (
    "%(house)s становится правящей династией: %(polity)s.",
    "Корона достаётся %(house_dat)s. С этого дня род — королевский.",
    "Отныне страна под рукой одного рода: %(house)s.",
)

CADET_TEMPLATES = (
    "%(founder)s отделяется от %(parent_gen)s и основывает младшую ветвь: "
    "%(house)s.",
    "Младший сын не желает жить в тени старшего: %(founder)s кладёт начало "
    "роду %(house_name)s, отделившись от %(parent_gen)s.",
    "От %(parent_gen)s откалывается младшая ветвь — %(house)s. Во главе "
    "встаёт %(founder)s.",
)

HOUSE_END_TEMPLATES = (
    "%(house)s пресекается: не остаётся ни одного наследника.",
    "С последним вздохом последнего из рода %(house)s уходит в предания.",
    "%(house_gen_cap)s больше нет. Родовое имя переходит в песни и судебные тяжбы.",
    "Род угасает: %(house)s остаётся только на старых печатях.",
)


def house_found(rng, house, founder, seat, race, royal: bool = False):
    data = {
        "founder": with_title(founder),
        "founder_given": ("%s %s" % (founder.titles[0].lower(), founder.given_name)
                          if founder.titles else founder.given_name),
        "founder_bare": founder.name,
        "house": house_nom(house),
        "house_name": house.name,
        "house_acc": house_acc(house),
        "surname": house.name,
        "seat": seat.full_name if seat is not None else "родовые земли",
        "seat_name": (seat.name if seat is not None else "своих земель"),
        "seat_acc": (("%s %s" % (accusative_noun(seat.kind).lower(), seat.name))
                     if seat is not None else "свои земли"),
    }
    title = "Новый род: %s" % house.name
    return title, cap(rng.choice(HOUSE_FOUND_TEMPLATES) % data)


def house_royal(rng, house, polity):
    data = {
        "house": house_nom(house),
        "house_name": house.name,
        "house_gen": house_gen(house),
        "house_dat": house_dat(house),
        "polity": polity.full_name,
    }
    return ("Династия: %s" % house.name,
            cap(rng.choice(ROYAL_HOUSE_TEMPLATES) % data))


def cadet_branch(rng, house, parent_house, founder):
    data = {
        "founder": with_title(founder),
        "house": house_nom(house),
        "house_name": house.name,
        "parent_gen": house_gen(parent_house),
    }
    return ("Младшая ветвь: %s" % house.name,
            cap(rng.choice(CADET_TEMPLATES) % data))


def house_extinct(rng, house, last_member):
    data = {"house": house_nom(house),
            "house_gen_cap": cap(house_gen(house)),
            "last": last_member.name if last_member is not None else "последний из рода"}
    return ("Пресечение рода: %s" % house.name,
            cap(rng.choice(HOUSE_END_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Восшествие на престол
# ---------------------------------------------------------------------------

LAW_NOTES = {
    MALE_PRIMOGENITURE: "Закон прост: престол идёт по мужской линии, от отца к старшему сыну.",
    ABSOLUTE_PRIMOGENITURE: "По закону наследует старший из детей, сын или дочь — всё равно.",
    SENIORITY: "По обычаю престол берёт старший в роду, а не старший сын.",
    MATRILINEAL: "Власть держится на женской линии, и так было всегда.",
    COUNCIL: "Совет дома выбирает достойнейшего и объявляет своё решение вслух.",
    ELECTIVE: "Главы знатных домов сходятся и выбирают правителя из своего числа.",
    STRENGTH: "Право на власть здесь доказывают силой.",
}

ACCESSION_TEMPLATES = (
    "%(heir)s всходит на престол %(polity_gen)s. %(relation)s",
    "Престол %(polity_gen)s принимает %(heir)s. %(relation)s",
    "Венец возлагают в городе по имени %(capital)s: правит теперь %(heir)s. "
    "%(relation)s",
    "%(polity)s получает нового правителя — это %(heir)s. %(relation)s",
    "Год траура кончается венчанием: власть принимает %(heir)s. %(relation)s",
    "Имя нового правителя объявляют с крыльца: %(heir)s. %(relation)s",
)

RELATION_NOTES = {
    "сын": "Наследует старший сын.",
    "дочь": "Наследует дочь.",
    "брат": "Наследует брат — так велит обычай.",
    "сестра": "Наследует сестра.",
    "внук": "Корона миновала целое поколение и легла на внука.",
    "внучка": "Корона миновала целое поколение и легла на внучку.",
    "племянник": "Прямых наследников не осталось — правит племянник.",
    "племянница": "Прямых наследниц не осталось — правит племянница.",
    "родич": "Наследник — дальний родич из того же дома.",
    "родственница": "Наследница — дальняя родственница из того же дома.",
    "чужак": "Родная кровь пресеклась, власть взяли со стороны.",
    "чужачка": "Родная кровь пресеклась, власть взяли со стороны.",
    "основатель": "Это первое правление в новой стране.",
    "узурпатор": "Право на власть доказано силой, а не родством.",
}


def accession(rng, polity, heir, choice, capital, race, first: bool = False):
    note = RELATION_NOTES.get(choice.relation, "")
    if first:
        note = "Это первое правление в новой стране."
    elif rng.chance(0.3):
        note = LAW_NOTES.get(choice.law, note)
    if choice.note:
        note = "%s %s." % (note, cap(choice.note))
    data = {
        "heir": with_title(heir),
        "polity": polity.full_name,
        "polity_gen": polity_gen(polity),
        "capital": capital.name if capital is not None else "столица",
        "relation": note,
    }
    return ("Восшествие: %s" % heir.plain_name,
            cap(rng.choice(ACCESSION_TEMPLATES) % data))


DYNASTY_CHANGE_TEMPLATES = (
    "Престол %(polity_gen)s переходит к новому роду: %(house)s. "
    "Правит теперь %(heir)s.",
    "Старая династия пресеклась. Знать выбирает нового правителя, и корона "
    "переходит %(house_dat)s. На престоле — %(heir)s.",
    "%(polity)s меняет династию: вместо угасшего рода правит %(house)s. "
    "Первый правитель новой крови — %(heir)s.",
    "Венец переходит из рук в руки: с этого дня страна под рукой рода "
    "%(house_name)s. На престоле — %(heir)s.",
    "Прежний род кончился, новый начинается: %(house)s. %(ruler_word_cap)s — "
    "%(heir)s.",
)


def dynasty_change(rng, polity, house, heir, old_house):
    data = {
        "polity": polity.full_name,
        "polity_gen": polity_gen(polity),
        "house": house_nom(house),
        "house_name": house.name,
        "house_gen": house_gen(house),
        "house_dat": house_dat(house),
        "heir": with_title(heir),
        "ruler_word_cap": cap(ruler_word(heir.sex)),
        "old": house_nom(old_house) if old_house is not None else "прежний род",
    }
    return ("Смена династии: %s" % house.name,
            cap(rng.choice(DYNASTY_CHANGE_TEMPLATES) % data))


INTERREGNUM_TEMPLATES = (
    "Престол %(polity_gen)s пуст: наследников нет, а знать не может договориться.",
    "Наступает междуцарствие: %(polity)s живёт без правителя, каждый город "
    "сам по себе.",
    "Корона %(polity_gen)s лежит без головы — желающих много, права нет ни у кого.",
)


def interregnum(rng, polity):
    return ("Междуцарствие: %s" % polity.name,
            cap(rng.choice(INTERREGNUM_TEMPLATES) % {
                "polity": polity.full_name, "polity_gen": polity_gen(polity)}))


# ---------------------------------------------------------------------------
# Регентство
# ---------------------------------------------------------------------------

REGENCY_START_TEMPLATES = (
    "Правитель ещё дитя, и страной правит %(regent)s.",
    "При малолетнем правителе учреждено регентство: дела ведёт %(regent)s.",
    "Венец надет на ребёнка. Печать держит %(regent)s — до совершеннолетия.",
)

REGENCY_END_TEMPLATES = (
    "%(ruler)s достигает совершеннолетия и берёт власть в свои руки.",
    "Регентство кончается: %(ruler)s правит сам.",
    "Печать возвращается законному владельцу: страной правит %(ruler)s.",
)


def regency_start(rng, polity, heir, regent, until_year: int):
    data = {
        "regent": with_title(regent) if regent is not None else "совет знати",
        "heir": heir.plain_name,
        "polity": polity.full_name,
        "until": until_year,
    }
    return ("Регентство при %s" % heir.plain_name,
            cap(rng.choice(REGENCY_START_TEMPLATES) % data
                + " Совершеннолетие ждут к %d году." % until_year))


def regency_end(rng, polity, ruler, regent):
    data = {"ruler": with_title(ruler), "polity": polity.full_name,
            "regent": regent.name if regent is not None else "регент"}
    return ("Конец регентства: %s" % ruler.plain_name,
            cap(rng.choice(REGENCY_END_TEMPLATES) % data))


# ---------------------------------------------------------------------------
# Перевороты и узурпации
# ---------------------------------------------------------------------------

FATES = (
    ("убит в своих покоях", "убита в своих покоях"),
    ("зарезан на собственном пиру", "зарезана на собственном пиру"),
    ("задушен ночью", "задушена ночью"),
    ("брошен в яму и забыт", "брошена в яму и забыта"),
    ("отравлен на глазах у двора", "отравлена на глазах у двора"),
)

EXILE_FATES = (
    ("изгнан за пределы страны", "изгнана за пределы страны"),
    ("заточён в дальней башне", "заточена в дальней башне"),
    ("лишён престола и имени", "лишена престола и имени"),
    ("отправлен доживать век в глуши", "отправлена доживать век в глуши"),
)

PALACE_COUP_TEMPLATES = (
    "Дворцовый переворот: власть берёт %(usurper)s. %(victim_cap)s %(fate)s.",
    "Ночью в столице меняется всё: на престол садится %(usurper)s, "
    "а %(victim)s %(fate)s.",
    "Свергает своя же родня: правителем объявляет себя %(usurper)s. "
    "%(victim_cap)s %(fate)s.",
    "Заговор удался. Страной правит %(usurper)s, а %(victim)s %(fate)s.",
    "Стража открывает ворота изнутри. Наутро правит %(usurper)s, "
    "а %(victim)s %(fate)s.",
)

USURPATION_TEMPLATES = (
    "Узурпация: престол %(polity_gen)s занимает %(usurper)s. "
    "%(victim_cap)s %(fate)s.",
    "%(house_cap)s поднимает мятеж и побеждает: венец берёт %(usurper)s. "
    "%(victim_cap)s %(fate)s.",
    "Право крови уступает праву силы: власть берёт %(usurper)s. "
    "%(victim_cap)s %(fate)s.",
    "Мятеж знати кончается сменой имени на печати: теперь правит %(usurper)s. "
    "%(victim_cap)s %(fate)s.",
)

CHALLENGE_TEMPLATES = (
    "Вызов принят при всех: в поединке побеждает %(usurper)s и берёт власть. "
    "%(victim_cap)s %(fate)s.",
    "По древнему праву сильнейшего вызов правителю бросает %(usurper)s — "
    "и выигрывает. %(victim_cap)s %(fate)s.",
    "Круг вытоптан, дело решено: правит %(usurper)s. %(victim_cap)s %(fate)s.",
)

DEPOSITION_TEMPLATES = (
    "Совет знати низлагает правителя. Власть принимает %(usurper)s; "
    "%(victim_cap)s %(fate)s.",
    "Главы домов сходятся и объявляют правление оконченным: теперь правит "
    "%(usurper)s, а %(victim)s %(fate)s.",
)

COUP_KIND_TITLES = {
    "palace": "Дворцовый переворот",
    "usurpation": "Узурпация престола",
    "challenge": "Поединок за власть",
    "deposition": "Низложение",
}


def coup_success(rng, kind, polity, usurper, victim, house, capital, violent: bool):
    fate_pool = FATES if violent else EXILE_FATES
    fate = by_sex(rng.choice(fate_pool), victim.sex if victim is not None else "m")
    templates = {
        "palace": PALACE_COUP_TEMPLATES,
        "usurpation": USURPATION_TEMPLATES,
        "challenge": CHALLENGE_TEMPLATES,
        "deposition": DEPOSITION_TEMPLATES,
    }[kind]
    data = {
        "usurper": with_title(usurper),
        "usurper_cap": cap(with_title(usurper)),
        "polity_gen": polity_gen(polity),
        "victim": with_title(victim) if victim is not None else "прежний правитель",
        "victim_cap": cap(with_title(victim)) if victim is not None else "Прежний правитель",
        "polity": polity.full_name,
        "capital": capital.name if capital is not None else "столице",
        "house_gen": house_gen(house) if house is not None else "чужого рода",
        "house_cap": cap(house_nom(house)) if house is not None else "Чужой род",
        "fate": fate,
    }
    return ("%s: %s" % (COUP_KIND_TITLES[kind], polity.name),
            cap(rng.choice(templates) % data))


PLOT_FAILED_TEMPLATES = (
    "Заговор раскрыт. %(plotter_cap)s казнён на площади, и на этом всё "
    "кончается.",
    "Мятеж захлебнулся: %(plotter)s не дожил до утра, а %(ruler)s правит дальше.",
    "Покушение не удалось. %(plotter_cap)s поплатился головой, %(house_cap)s — "
    "землями и честью.",
)


def plot_failed(rng, polity, plotter, ruler, house):
    female = plotter.sex == "f"
    data = {
        "plotter": with_title(plotter),
        "plotter_cap": cap(with_title(plotter)),
        "ruler": with_title(ruler) if ruler is not None else "правитель",
        "polity": polity.full_name,
        "house_cap": cap(house_nom(house)) if house is not None else "Род заговорщика",
    }
    text = rng.choice(PLOT_FAILED_TEMPLATES) % data
    if female:
        text = text.replace("казнён", "казнена").replace("не дожил", "не дожила")
        text = text.replace("поплатился", "поплатилась")
    return ("Раскрытый заговор: %s" % polity.name, cap(text))


ABDICATION_TEMPLATES = (
    "%(ruler)s отрекается от престола и уходит от дел.",
    "Устав от власти, %(ruler)s складывает венец добровольно.",
    "%(ruler)s передаёт власть при жизни — случай редкий и памятный.",
)


def abdication(rng, polity, ruler):
    return ("Отречение: %s" % ruler.plain_name,
            cap(rng.choice(ABDICATION_TEMPLATES) % {"ruler": with_title(ruler),
                                                    "polity": polity.full_name}))


# ---------------------------------------------------------------------------
# Браки, наследники, смерть правителя
# ---------------------------------------------------------------------------

MARRIAGE_TEMPLATES = (
    "%(ruler)s берёт в супруги %(spouse)s. %(note)s",
    "Свадьба при дворе: %(ruler)s и %(spouse)s теперь одна семья. %(note)s",
    "Брачный договор скреплён: %(ruler)s и %(spouse)s. %(note)s",
)

MARRIAGE_NOTES_HOUSE = (
    "Два рода связаны кровью, и это дороже золота.",
    "Союз домов подписан на пергаменте и запит вином.",
    "Приданое считают три дня.",
)

MARRIAGE_NOTES_COMMON = (
    "Родня ворчит: вторая половина не из знатного рода.",
    "Двор перешёптывается — крови в этом браке больше простой, чем знатной.",
    "Брак по любви, говорят одни; по расчёту, говорят другие.",
)


def marriage(rng, polity, ruler, spouse, spouse_house):
    note = rng.choice(MARRIAGE_NOTES_HOUSE if spouse_house is not None
                      else MARRIAGE_NOTES_COMMON)
    if spouse_house is not None:
        note = "%s Вторая половина — из %s." % (note, house_gen(spouse_house))
    data = {
        "ruler": with_title(ruler),
        "spouse": spouse.name,
        "polity": polity.full_name if polity is not None else "столице",
        "note": note,
    }
    return ("Брак: %s" % ruler.plain_name, cap(rng.choice(MARRIAGE_TEMPLATES) % data))


HEIR_BIRTH_TEMPLATES = (
    "У правителя рождается наследник — %(child)s.",
    "При дворе празднуют: на свет появляется %(child)s, первенец правителя.",
    "Родовое древо %(house_gen)s даёт новую ветвь: %(child)s.",
    "Повитуха выносит младенца к окну: имя ему — %(child)s.",
)


def heir_birth(rng, polity, child, house):
    data = {
        "child": child.plain_name,
        "polity": polity.full_name if polity is not None else "столице",
        "house_gen": house_gen(house) if house is not None else "правящего рода",
    }
    return ("Рождение наследника: %s" % child.plain_name,
            cap(rng.choice(HEIR_BIRTH_TEMPLATES) % data))


RULER_DEATH_TEMPLATES = (
    "%(ruler)s умирает, проведя на престоле %(reign)s. %(legacy)s",
    "Правление кончается смертью: %(ruler)s уходит, процарствовав %(reign)s. "
    "%(legacy)s",
    "%(ruler)s не встаёт с ложа. Правление длилось %(reign)s. %(legacy)s",
)

RULER_LEGACY = (
    "Погребение длится девять дней.",
    "Наследство делят прежде, чем остынет тело.",
    "Летописец выводит последнюю строку и меняет перо.",
    "В столице закрывают ворота до объявления наследника.",
    "Имя заносят в список правителей и высекают на камне.",
)


def ruler_death(rng, polity, ruler, reign_years: int, cause: str = ""):
    legacy = rng.choice(RULER_LEGACY)
    if cause:
        legacy = "%s %s" % (cap(cause), legacy)
    data = {
        "ruler": with_title(ruler),
        "polity": polity.full_name,
        "reign": years_text(max(1, reign_years)),
        "legacy": legacy,
    }
    return ("Смерть правителя: %s" % ruler.plain_name,
            cap(rng.choice(RULER_DEATH_TEMPLATES) % data))
