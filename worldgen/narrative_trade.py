# -*- coding: utf-8 -*-
"""Тексты о торговле, дорогах и нужде.

Падежи — по общему правилу: имена стран и мест стоят в именительном,
косвенные формы берутся у помощников (``polity_gen``), названия товаров
лежат в словаре заранее в нужном падеже.
"""

from __future__ import annotations

from .narrative import cap
from .narrative_dynasty import polity_gen

# Товары в винительном и родительном — они не генерируются, а заданы.
GOOD_ACC = {
    "хлеб": "хлеб", "скот": "скот", "рыба": "рыбу", "лес": "лес",
    "камень": "камень", "металл": "металл", "соль": "соль",
    "шерсть": "шерсть", "меха": "меха", "вино": "вино",
    "пряности": "пряности", "самоцветы": "самоцветы",
    "чародейные снадобья": "чародейные снадобья",
}
GOOD_GEN = {
    "хлеб": "хлеба", "скот": "скота", "рыба": "рыбы", "лес": "леса",
    "камень": "камня", "металл": "металла", "соль": "соли",
    "шерсть": "шерсти", "меха": "мехов", "вино": "вина",
    "пряности": "пряностей", "самоцветы": "самоцветов",
    "чародейные снадобья": "чародейных снадобий",
}


def acc(good: str) -> str:
    return GOOD_ACC.get(good, good)


def gen(good: str) -> str:
    return GOOD_GEN.get(good, good)


# --- договор -----------------------------------------------------------

PACT_TEMPLATES = (
    "%(buyer)s не хватает %(need_gen)s, а у %(seller_gen)s его в избытке. "
    "Договор подписывают на десять лет.",
    "Купцы находят друг друга раньше послов: %(seller)s везёт %(need_acc)s "
    "в державу по имени %(buyer_name)s, обратно идёт %(back_acc)s.",
    "Голод учит считать: %(buyer)s покупает %(need_acc)s у %(seller_gen)s "
    "и платит тем, чего у самой девать некуда.",
    "Между %(seller_gen)s и %(buyer_gen)s ложится торговый путь. Возят "
    "%(need_acc)s, а обратно — %(back_acc)s.",
    "Послы торгуются полгода и сходятся на простом: %(need_acc)s в обмен "
    "на %(back_acc)s.",
)
PACT_ROAD = (
    "Дорогу к перевалу чинят обе стороны — впервые за много лет.",
    "Путь длиной %(length)s гексов размечают вехами и сторожевыми башнями.",
    "На бродах ставят паромы, на перевале — приют для обозов.",
    "Купеческие караваны идут в обход хребта: короче не выходит, но так "
    "доходят.",
    "Вдоль реки поднимаются торжища — по одному на день пути.",
)


def trade_pact(rng, buyer, seller, need, back, path_length: int):
    data = {
        "buyer": buyer.full_name, "buyer_gen": polity_gen(buyer),
        "buyer_name": buyer.name,
        "seller": seller.full_name, "seller_gen": polity_gen(seller),
        "need_acc": acc(need), "need_gen": gen(need),
        "back_acc": acc(back) if back else "серебро",
        "length": path_length,
    }
    lines = [rng.choice(PACT_TEMPLATES) % data, rng.choice(PACT_ROAD) % data]
    return ("Торговый путь: %s — %s" % (seller.name, buyer.name),
            cap(" ".join(lines)))


# --- разрыв ------------------------------------------------------------

BREAK_TEMPLATES = (
    "Путь между %(a_gen)s и %(b_gen)s закрывается: возить стало некому "
    "и незачем.",
    "Караваны перестают доходить. Торговый договор о %(good_prep)s "
    "расторгают без объяснений.",
    "Война съедает торговлю: путь между %(a_gen)s и %(b_gen)s пустеет.",
    "Последний обоз возвращается ни с чем, и торжища на пути закрываются.",
)


def trade_break(rng, first, second, good):
    data = {
        "a_gen": polity_gen(first), "b_gen": polity_gen(second),
        "good_prep": gen(good),
    }
    return ("Конец торгового пути: %s — %s" % (first.name, second.name),
            cap(rng.choice(BREAK_TEMPLATES) % data))


# --- нужда -------------------------------------------------------------

SHORTAGE_TEMPLATES = {
    "хлеб": (
        "В %(polity)s кончается хлеб. Цену на зерно называют шёпотом.",
        "Житницы %(polity_gen)s пусты второй год подряд.",
        "Хлеба нет, и подати собирают скотом, железом, чем придётся.",
    ),
    "металл": (
        "Кузни %(polity_gen)s стоят: руды нет, а привозная дорога.",
        "Войско %(polity_gen)s перековывает старое оружие — нового железа "
        "взять негде.",
        "Металл в державе по имени %(name)s дороже серебра, и это не "
        "оборот речи.",
    ),
    "лес": (
        "Строевого леса в державе по имени %(name)s не осталось: "
        "последние рощи вырубили "
        "на верфи.",
        "Дома в державе по имени %(name)s ставят из камня не от хорошей "
        "жизни.",
    ),
    "соль": (
        "Без соли рыбу не сохранить, и %(polity)s платит за неё вдвое.",
    ),
}
SHORTAGE_GENERAL = (
    "%(polity)s остро не хватает %(good_gen)s, и это чувствует каждый двор.",
    "Нужда в %(good_prep)s становится в державе по имени %(name)s делом "
    "государственным.",
    "Чего в державе по имени %(name)s нет совсем — так это %(good_gen)s.",
)


def shortage(rng, polity, good):
    data = {
        "polity": polity.full_name, "polity_gen": polity_gen(polity),
        "name": polity.name,
        "good_gen": gen(good), "good_prep": gen(good), "good_acc": acc(good),
    }
    pool = SHORTAGE_TEMPLATES.get(good)
    line = rng.choice(pool) % data if pool else \
        rng.choice(SHORTAGE_GENERAL) % data
    return ("Нужда: %s" % polity.name, cap(line))


# --- голод -------------------------------------------------------------

FAMINE_TEMPLATES = (
    "В %(polity)s наступает голод. Считают не урожай, а умерших: %(dead)s.",
    "Два неурожая подряд, и %(polity)s начинает есть посевное зерно. "
    "Умерших — %(dead)s.",
    "Голод в державе по имени %(name)s выкашивает окраины первыми. "
    "Всего погибает "
    "%(dead)s.",
    "Хлеба нет ни купить, ни отнять. %(polity)s теряет %(dead)s.",
)


def famine(rng, polity, dead: int):
    data = {"polity": polity.full_name, "name": polity.name,
            "dead": _souls(dead)}
    return ("Голод: %s" % polity.name, cap(rng.choice(FAMINE_TEMPLATES) % data))


def _souls(count: int) -> str:
    if count >= 1000000:
        return "%.1f млн душ" % (count / 1000000.0)
    if count >= 1000:
        return "%d тысяч душ" % (count // 1000)
    return "%d душ" % count


# --- дороги ------------------------------------------------------------

ROAD_TEMPLATES = (
    "%(polity)s мостит дорогу между городами: %(length)s гексов пути, "
    "броды и мосты за казённый счёт.",
    "Тракт через %(polity_gen)s достраивают при третьем правителе подряд. "
    "Длина — %(length)s гексов.",
    "Дорогу ведут в обход хребта и всё равно называют прямой.",
    "От столицы расходятся мощёные пути: первый готов через %(years)s.",
)


def road(rng, polity, length: int, years: int):
    data = {
        "polity": polity.full_name, "polity_gen": polity_gen(polity),
        "length": length, "years": "%d лет" % years,
    }
    return ("Дорога: %s" % polity.name, cap(rng.choice(ROAD_TEMPLATES) % data))
