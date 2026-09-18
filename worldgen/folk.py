# -*- coding: utf-8 -*-
"""Народы внутри расы.

Раса — это не народ. Люди, проснувшиеся на болотах у большой реки, и
люди, проснувшиеся в предгорьях за тысячу вёрст оттуда, — разные народы:
разные имена, разные обычаи, разные враги. Родство у них есть, но общего
государства может не быть никогда.

Имена народов нарочно **не** собираются той же кузницей, что имена людей
и городов. Иначе они сливаются в похожие наборы слогов — мир начинает
звучать одинаково. Здесь три уклада, и все три опираются на настоящие
слова или на имена, которые карта уже дала земле:

1. **от земли** — «валдестадцы», «кораосцы»: имя места плюс русский
   суффикс;
2. **по приметe** — «Люди Длинных Вёсел», «Дети Солёного Ветра»: обычные
   слова, ни одного выдуманного слога;
3. **у ориентира** — «люди реки Кораос», «дети хребта Валдестад»: родовое
   слово и имя карты следом, в именительном, поэтому оборот годится
   в любом падеже.
"""

from __future__ import annotations

from . import races as races_mod

# --- 1. Суффиксы для имени от земли ------------------------------------
# Подбираются по окончанию имени, чтобы «Кораос» не стал «кораосцыцы».
# (окончание, сколько букв отбросить, что дописать).
ETHNIC_SUFFIXES = (
    ("ия", 2, "йцы"), ("ея", 2, "йцы"), ("ая", 2, "йцы"),
    ("а", 1, "цы"), ("я", 1, "цы"), ("о", 1, "вцы"), ("е", 1, "вцы"),
    ("у", 1, "вцы"), ("ы", 1, "цы"), ("и", 1, "йцы"),
    ("ь", 1, "ьцы"), ("й", 1, "йцы"),
    ("л", 0, "ьцы"), ("нь", 1, "ьцы"),
    ("к", 0, "овцы"), ("г", 0, "овцы"), ("х", 0, "овцы"),
    ("ц", 0, "евцы"), ("ч", 0, "евцы"), ("ш", 0, "евцы"), ("ж", 0, "евцы"),
)
ALT_SUFFIXES = ("ичи", "ане", "иты")

# --- 2. Приметы: слова, а не слоги -------------------------------------
MARK_HEADS = ("Люди", "Дети", "Народ", "Сыны", "Племена")
MARK_BY_TERRAIN = {
    races_mod.FOREST: ("Долгой Тени", "Хвойного Пояса", "Тихих Троп",
                       "Смолы и Коры", "Зелёного Молчания"),
    races_mod.MOUNTAIN: ("Высокого Камня", "Снежного Гребня", "Орлиных Скал",
                         "Холодных Вершин", "Каменного Слова"),
    races_mod.HILLS: ("Круглых Холмов", "Овечьих Склонов", "Медных Гряд",
                      "Ветреных Увалов"),
    races_mod.PLAIN: ("Открытого Поля", "Хлебного Простора", "Долгих Дорог",
                      "Пыльного Тракта"),
    races_mod.STEPPE: ("Высокой Травы", "Конского Топота", "Сухого Ветра",
                       "Бескрайней Гривы"),
    races_mod.COAST: ("Длинных Вёсел", "Солёного Ветра", "Отлива",
                      "Белого Прибоя", "Крикливых Чаек"),
    races_mod.ISLANDS: ("Разбитых Берегов", "Тысячи Камней", "Дальней Воды",
                        "Чаячьего Гнездовья"),
    races_mod.SWAMP: ("Мокрой Земли", "Ольхи и Тины", "Тумана над Водой",
                      "Гнилого Брода"),
    races_mod.JUNGLE: ("Тяжёлого Листа", "Вечного Пара", "Лианной Кровли",
                       "Душного Полога"),
    races_mod.TUNDRA: ("Долгой Ночи", "Белого Мха", "Стылого Дыхания",
                       "Северного Огня"),
    races_mod.DESERT: ("Горячего Песка", "Сухого Колодца", "Поющих Дюн",
                       "Солёной Корки"),
    races_mod.UNDERGROUND: ("Глубокого Хода", "Слепого Камня", "Рудной Жилы",
                            "Подземного Эха"),
}
MARK_GENERAL = ("Первого Костра", "Старого Договора", "Разделённой Реки",
                "Двух Знамён", "Последнего Перехода", "Чёрного Знака",
                "Серого Рассвета", "Позднего Снега")

# --- 3. Ориентиры ------------------------------------------------------
LANDMARK_HEADS = ("люди", "дети", "народ")

# --- черты народа: чем он отличается от собратьев по расе ---------------
FOLK_TRAITS_BY_TERRAIN = {
    races_mod.COAST: ("мореходы", "рыбаки", "солевары", "китобои"),
    races_mod.ISLANDS: ("мореходы", "ныряльщики", "птицеловы"),
    races_mod.MOUNTAIN: ("горняки", "камнетёсы", "козопасы"),
    races_mod.UNDERGROUND: ("горняки", "рудознатцы", "грибоводы"),
    races_mod.FOREST: ("охотники", "смолокуры", "древоделы"),
    races_mod.JUNGLE: ("травники", "звероловы", "древолазы"),
    races_mod.STEPPE: ("коневоды", "лучники", "кочевники"),
    races_mod.PLAIN: ("хлебопашцы", "гончары", "мельники"),
    races_mod.HILLS: ("овцеводы", "виноградари", "медовары"),
    races_mod.SWAMP: ("болотники", "лодочники", "знахари"),
    races_mod.TUNDRA: ("оленеводы", "следопыты", "костерезы"),
    races_mod.DESERT: ("караванщики", "водознатцы", "погонщики"),
}
FOLK_TRAITS_GENERAL = ("упрямцы", "молчуны", "гостеприимные", "злопамятные",
                       "скорые на клятву", "суеверные", "насмешники",
                       "домоседы", "странники", "хлебосолы", "бражники",
                       "книжники", "спорщики")


def ethnonym(name: str) -> str:
    """«Валдестад» -> «валдестадцы», «Келара» -> «келарцы»."""
    if not name:
        return ""
    base = name.split()[-1].lower().replace("'", "")
    if len(base) < 3:
        return base + "цы"
    for ending, cut, suffix in ETHNIC_SUFFIXES:
        if base.endswith(ending):
            stem = base[:len(base) - cut] if cut else base
            return stem + suffix
    return base + "цы"


def folk_name(rng, race, region, used) -> tuple:
    """Имя народа и то, как оно построено.

    Возвращает (имя, уклад). Уклад пригодится текстам: «валдестадцы»
    склоняются как обычное слово, а «люди реки Кораос» — нет.
    """
    ways = []

    landmark = _landmark(region)
    if landmark:
        ways.append(("landmark", "%s %s" % (rng.choice(LANDMARK_HEADS), landmark)))

    # Имя земли идёт впереди имени материка: иначе половина народов мира
    # окажется «виренцами» просто потому, что материк один на всех.
    source = region.range_name or (region.rivers[0] if region.rivers else "") \
        or region.name or region.landmass
    if source:
        stem = ethnonym(source)
        if stem:
            ways.append(("ethnic", stem))
            if rng.chance(0.3):
                ways.append(("ethnic", source.split()[-1].lower()
                             + rng.choice(ALT_SUFFIXES)))

    marks = MARK_BY_TERRAIN.get(region.terrain, ()) + MARK_GENERAL
    ways.append(("mark", "%s %s" % (rng.choice(MARK_HEADS), rng.choice(marks))))

    # Занятым считается не только имя целиком, но и его сердцевина: иначе
    # рядом оказываются «Дети Позднего Снега», «Сыны Позднего Снега» и
    # «Народ Позднего Снега» — разные слова, одна и та же примета.
    cores = {_core(name) for name in used}
    for _ in range(16):
        kind, name = rng.choice(ways)
        if kind == "mark":
            marks_pool = MARK_BY_TERRAIN.get(region.terrain, ()) + MARK_GENERAL
            name = "%s %s" % (rng.choice(MARK_HEADS), rng.choice(marks_pool))
        if name and name not in used and _core(name) not in cores:
            return name, kind
    # Всё занято — добавляем сторону света, а не выдуманный слог.
    for side in ("Северные", "Южные", "Западные", "Восточные", "Горние",
                 "Дольние", "Дальние", "Ближние"):
        candidate = "%s %s" % (side, ways[0][1])
        if candidate not in used:
            return candidate, ways[0][0]
    return ways[0][1], ways[0][0]


def _core(name: str) -> str:
    """Сердцевина имени: то, что остаётся без родового слова впереди."""
    words = name.split()
    if words and words[0] in MARK_HEADS + tuple(
            head.capitalize() for head in LANDMARK_HEADS) + LANDMARK_HEADS:
        return " ".join(words[1:]).lower()
    return name.lower()


def _landmark(region) -> str:
    """Ориентир, по которому народ может себя назвать."""
    if region.rivers:
        return "реки %s" % region.rivers[0]
    if region.range_name:
        return "хребта %s" % region.range_name
    if region.sea and region.coastal:
        kinds = {"океан": "океана", "море": "моря", "залив": "залива"}
        return "%s %s" % (kinds.get(region.sea_kind, "моря"), region.sea)
    if region.landmass and region.landmass_kind in ("остров", "большой остров",
                                                    "архипелаг"):
        return "острова %s" % region.landmass
    return ""


# Этноним — обычное русское слово и склоняется как слово. Имена по примете
# («Люди Двух Знамён») не склоняются, поэтому в косвенных падежах их
# оборачивают: «история народа „Люди Двух Знамён“».
_PLURAL_CASES = (
    ("цы", "цев", "цам"), ("ичи", "ичей", "ичам"),
    ("ане", "ан", "анам"), ("иты", "итов", "итам"),
)


def folk_gen(folk) -> str:
    """Родительный падеж: «виренцев», «народа „Люди Двух Знамён“»."""
    return _case(folk, 1)


def folk_dat(folk) -> str:
    """Дательный падеж: «виренцам», «народу „Люди Двух Знамён“»."""
    return _case(folk, 2)


# Определение при этнониме склоняется вместе с ним: не «Северные
# дубравцев», а «Северных дубравцев».
_ADJ_CASES = (
    ("ые", "ых", "ым"), ("ие", "их", "им"), ("ьи", "ьих", "ьим"),
)


def _case(folk, slot: int) -> str:
    name = folk.name
    if folk.name_kind == "ethnic":
        words = name.split(" ")
        bent = _bend(words[-1], _PLURAL_CASES, slot)
        if bent is not None:
            head = []
            for word in words[:-1]:
                shifted = _bend(word, _ADJ_CASES, slot)
                if shifted is None:
                    head = None
                    break
                head.append(shifted)
            if head is not None:
                return " ".join(head + [bent])
    return "%s «%s»" % ("народа" if slot == 1 else "народу", name)


def _bend(word: str, table, slot: int):
    """Меняет окончание по таблице; None — если слово нам не по зубам."""
    for ending, gen, dat in table:
        if word.endswith(ending):
            return word[:-len(ending)] + (gen if slot == 1 else dat)
    return None


def folk_traits(rng, region) -> list:
    """Одна-две черты, которыми народ отличается от собратьев по расе."""
    pool = FOLK_TRAITS_BY_TERRAIN.get(region.terrain, ())
    traits = []
    if pool:
        traits.append(rng.choice(pool))
    if FOLK_TRAITS_GENERAL and rng.chance(0.6):
        traits.append(rng.choice(FOLK_TRAITS_GENERAL))
    return traits
