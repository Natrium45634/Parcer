# -*- coding: utf-8 -*-
"""Тексты о местах: курганы, руины, клады и те, кто в них входит.

Правила прежние: сгенерированные имена стоят в именительном падеже,
косвенные падежи берутся готовыми оборотами, глаголы — в настоящем
времени третьего лица.
"""

from __future__ import annotations

from . import sites as sites_mod
from .narrative import cap
from .timeline import years_text


# ---------------------------------------------------------------------------
# Место возникает
# ---------------------------------------------------------------------------

TOMB_TEMPLATES = (
    "%(who)s погребают с почестями и с тем, что было при нём. Над могилой "
    "насыпают курган, и место это зовут %(place)s.",
    "Похороны выходят пышнее, чем жизнь: %(who)s уходит в землю вместе с "
    "оружием, утварью и теми, кто не захотел остаться. Курган называют "
    "%(place)s.",
    "Могилу роют глубоко и закладывают камнем: %(place)s. Лежит в ней "
    "%(who)s.",
    "%(place)s насыпают три лета. Столько же спорят, что положить внутрь "
    "вместе с %(who)s.",
)

TOMB_NOTES = (
    "Место считают недобрым и обходят стороной — но обходят не все.",
    "Первые полвека к кургану носят дары, потом перестают.",
    "Входа не оставляют вовсе: вход прорубят потом, и не те, кто строил.",
    "Строители берут клятву молчать о том, где именно вход.",
    "Через поколение место помнят уже неточно, а через три — по-разному.",
)


def tomb_raised(rng, site, figure, deeds: str = "") -> tuple:
    text = rng.choice(TOMB_TEMPLATES) % {
        "who": figure.name if figure is not None else "покойного",
        "place": site.name}
    if deeds:
        text = "%s %s" % (text, deeds)
    text = "%s %s" % (text, rng.choice(TOMB_NOTES))
    return ("Курган: %s" % site.name), cap(text)


RUIN_TEMPLATES = (
    "От города остаются стены без крыш и улицы без людей. Место зовут "
    "%(place)s.",
    "%(place)s — всё, что осталось от города, который стоял здесь "
    "%(years)s.",
    "Через десять лет здесь не живёт никто, кроме тех, кому всё равно. "
    "Место так и зовут: %(place)s.",
    "Дома стоят целыми ещё долго — это и приводит сюда первых охотников "
    "за чужим добром. %(place)s.",
)


def ruin_left(rng, site, settlement, years: int) -> tuple:
    text = rng.choice(RUIN_TEMPLATES) % {
        "place": site.name, "years": years_text(max(1, years))}
    return ("Руины: %s" % site.name), cap(text)


FIELD_TEMPLATES = (
    "Поле, где сошлись войска, так и остаётся полем: пахать его не берутся "
    "ещё сто лет. Место зовут %(place)s.",
    "Кости не убирают — их слишком много. %(place)s.",
    "Над полем ставят камень с именами, и камень этот переживёт обе "
    "державы. %(place)s.",
)


# Имя поля битвы строится не из имени сражения, а из самого места:
# «Битва за чертог X» даёт «Поле за чертог X», а это уже не по-русски.
FIELD_AT_CITY = (
    "Поле у стен города %s",
    "Поле под городом %s",
    "Поле у города по имени %s",
    "Поле, что зовут по городу %s",
)

FIELD_AT_REGION = (
    "Поле в земле по имени %s",
    "Поле на рубежах земли по имени %s",
    "Поле в краю по имени %s",
    "Поле, что зовут по земле %s",
)


def field_name(rng, world, battle) -> str:
    """Как назовут это поле через сто лет."""
    settlement = world.settlements.get(battle.settlement_id)
    if settlement is not None:
        return rng.choice(FIELD_AT_CITY) % settlement.name
    region = world.regions.get(battle.region_id)
    if region is not None:
        return rng.choice(FIELD_AT_REGION) % region.name
    return "Поле битвы"


def field_left(rng, site, battle) -> tuple:
    text = rng.choice(FIELD_TEMPLATES) % {"place": site.name}
    return ("Поле битвы: %s" % site.name), cap(text)


HOARD_TEMPLATES = (
    "Казну прячут наспех и не там, где следовало: %(place)s остаётся в "
    "земле дольше, чем те, кто его закапывал.",
    "Добро зарывают в расчёте вернуться через год. Не возвращается никто. "
    "%(place)s.",
    "%(place)s — то, что успели спрятать, когда стало ясно, чем всё "
    "кончится.",
)


def hoard_left(rng, site) -> tuple:
    text = rng.choice(HOARD_TEMPLATES) % {"place": site.name}
    return ("Клад: %s" % site.name), cap(text)


# ---------------------------------------------------------------------------
# В место входят
# ---------------------------------------------------------------------------

ENTER_TEMPLATES = (
    "%(who)s входит в %(place)s — первым за %(years)s.",
    "О том, что там лежит, знали давно; решается на это %(who)s.",
    "%(who)s находит вход там, где его не искали, и спускается.",
    "Сговариваются впятером, возвращается %(who)s.",
    "%(who)s идёт туда за славой, а не за золотом — впрочем, золото тоже "
    "берёт.",
)

SUCCESS_LINES = (
    "Выносят немало: %(riches)s.",
    "Добычи хватает, чтобы купить себе имя: %(riches)s.",
    "Всё, что можно унести, уносят. Считают потом: %(riches)s.",
)

TROUBLE_LINES = (
    "Назад выходят не все.",
    "Стерегущее место берёт свою долю: из пришедших возвращается половина.",
    "Что случилось внизу, рассказывают по-разному и все — неправду.",
    "Того, кто шёл первым, оставляют там же.",
)

FAIL_TEMPLATES = (
    "%(who)s входит в %(place)s и не выходит. Искать не идут.",
    "Из тех, кто спустился в %(place)s, наверх не поднимается никто.",
    "%(place)s принимает ещё одного: %(who)s остаётся там навсегда.",
    "Вход обваливается за спиной у вошедших. %(who)s среди них.",
)


def site_entered(rng, site, figure, years: int, riches: str,
                 trouble: bool) -> tuple:
    text = rng.choice(ENTER_TEMPLATES) % {
        "who": figure.name if figure is not None else "неизвестный",
        "place": site.name, "years": years_text(max(1, years))}
    if riches:
        text = "%s %s" % (text, rng.choice(SUCCESS_LINES) % {"riches": riches})
    if trouble:
        text = "%s %s" % (text, rng.choice(TROUBLE_LINES))
    return ("Вскрыто: %s" % site.name), cap(text)


def site_failed(rng, site, figure) -> tuple:
    text = rng.choice(FAIL_TEMPLATES) % {
        "who": figure.name if figure is not None else "пришедший",
        "place": site.name}
    return ("Не вернулись: %s" % site.name), cap(text)


# ---------------------------------------------------------------------------
# Место обживают
# ---------------------------------------------------------------------------

SETTLED_TEMPLATES = (
    "В %(place)s поселяется то, чего там прежде не было. Окрестные деревни "
    "узнают об этом первыми.",
    "Пустое место недолго остаётся пустым: в %(place)s кто-то живёт.",
    "Охотники приносят весть: в %(place)s горит огонь, а жечь его некому.",
)


def site_settled(rng, site, guard: str) -> tuple:
    text = rng.choice(SETTLED_TEMPLATES) % {"place": site.name}
    if guard and guard != sites_mod.NOBODY:
        text = "%s Стережёт место %s." % (text, guard)
    return ("Обитаемо: %s" % site.name), cap(text)


# ---------------------------------------------------------------------------
# Строка о том, чем место памятно
# ---------------------------------------------------------------------------

def story_line(site, figure=None, settlement=None, battle=None,
               deeds: str = "") -> str:
    """Одна строка, которая объясняет место целиком."""
    if site.kind in (sites_mod.TOMB, sites_mod.CRYPT) and figure is not None:
        base = "здесь лежит %s" % figure.name
        return "%s, %s" % (base, deeds) if deeds else base
    if site.kind == sites_mod.RUIN and settlement is not None:
        return "здесь стоял город %s" % settlement.name
    if site.kind == sites_mod.FIELD and battle is not None:
        return "здесь сошлись войска: %s" % battle.name
    if site.kind == sites_mod.HOARD:
        return "здесь спрятали то, за чем не вернулись"
    return "место, о котором помнят не всё"
