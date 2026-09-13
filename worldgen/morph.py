# -*- coding: utf-8 -*-
"""Небольшой помощник по русской морфологии.

Нужен, чтобы составные названия («Серебряная Роща», «Железные Врата»)
и прозвища («Молчаливый» / «Молчаливая») звучали грамотно, и при этом
не приходилось выписывать каждое слово во всех формах.
"""

from __future__ import annotations

# Род существительного: m — мужской, f — женский, n — средний, p — множественное.
MASC, FEM, NEUT, PLUR = "m", "f", "n", "p"

# Прилагательные-исключения: полные формы (м., ж., ср., мн.).
ADJ_EXCEPTIONS = {
    "Охотничий": ("Охотничий", "Охотничья", "Охотничье", "Охотничьи"),
    "Паучий": ("Паучий", "Паучья", "Паучье", "Паучьи"),
    "Волчий": ("Волчий", "Волчья", "Волчье", "Волчьи"),
    "Птичий": ("Птичий", "Птичья", "Птичье", "Птичьи"),
    "Лисий": ("Лисий", "Лисья", "Лисье", "Лисьи"),
    "Медвежий": ("Медвежий", "Медвежья", "Медвежье", "Медвежьи"),
    "Кошачий": ("Кошачий", "Кошачья", "Кошачье", "Кошачьи"),
    "Божий": ("Божий", "Божья", "Божье", "Божьи"),
    "Орочий": ("Орочий", "Орочья", "Орочье", "Орочьи"),
    "Троллий": ("Троллий", "Троллья", "Тролльё", "Тролльи"),
    "Рыбий": ("Рыбий", "Рыбья", "Рыбье", "Рыбьи"),
    "Змеиный": ("Змеиный", "Змеиная", "Змеиное", "Змеиные"),
}

_HUSHING = "жшчщ"
_VELAR = "кгх"


def decline_adjective(adj: str) -> tuple:
    """Возвращает (муж., жен., ср., мн.) формы прилагательного.

    Работает для обычных качественных прилагательных на -ый/-ий/-ой.
    Нестандартные случаи перечислены в ADJ_EXCEPTIONS.
    """
    known = ADJ_EXCEPTIONS.get(adj)
    if known:
        return known

    if adj.endswith("ний"):
        stem = adj[:-3]
        return (adj, stem + "няя", stem + "нее", stem + "ние")

    if adj.endswith("ый") or adj.endswith("ой"):
        stem = adj[:-2]
        neuter = stem + ("ое" if adj.endswith("ый") or not stem[-1:] in _HUSHING else "ее")
        return (adj, stem + "ая", neuter, stem + "ые")

    if adj.endswith("ий"):
        stem = adj[:-2]
        last = stem[-1:].lower()
        if last in _HUSHING:
            return (adj, stem + "ая", stem + "ее", stem + "ие")
        if last in _VELAR:
            return (adj, stem + "ая", stem + "ое", stem + "ие")
        return (adj, stem + "яя", stem + "ее", stem + "ие")

    # Ничего не знаем об этом слове — оставляем как есть.
    return (adj, adj, adj, adj)


_GENDER_INDEX = {MASC: 0, FEM: 1, NEUT: 2, PLUR: 3}


def adjective_for(adj: str, gender: str) -> str:
    """Форма прилагательного, согласованная с родом существительного."""
    return decline_adjective(adj)[_GENDER_INDEX.get(gender, 0)]


def phrase(adj: str, noun: str, gender: str) -> str:
    """«Серебряный» + «Роща»(f) -> «Серебряная Роща»."""
    return "%s %s" % (adjective_for(adj, gender), noun)


ACCUSATIVE_EXCEPTIONS = {
    "Племя": "Племя",
    "Знамя": "Знамя",
}


def accusative_noun(word: str) -> str:
    """Винительный падеж для названий вида «Застава» -> «Заставу».

    Правило простое и покрывает все используемые слова: -а -> -у, -я -> -ю,
    остальные (мужской род неодушевлённый, средний род, «крепость», «пристань»)
    не меняются.
    """
    if not word:
        return word
    known = ACCUSATIVE_EXCEPTIONS.get(word)
    if known:
        return known
    last = word[-1]
    if last == "а":
        return word[:-1] + "у"
    if last == "я":
        return word[:-1] + "ю"
    return word


GENITIVE_EXCEPTIONS = {
    "Выводок": "Выводка",
    "Огонёк": "Огонька",
    "Костёр": "Костра",
    "Котёл": "Котла",
    "Шатёр": "Шатра",
    "Венец": "Венца",
    "Корень": "Корня",
    "Камень": "Камня",
    "Ветер": "Ветра",
    # Мужские существительные на мягкий знак — их не отличить по правилу.
    "Лагерь": "Лагеря",
    "Панцирь": "Панциря",
    "Уголь": "Угля",
    # Разносклоняемые на -мя.
    "Племя": "Племени",
    "Знамя": "Знамени",
    "Имя": "Имени",
    # Двусловные названия родов и форм правления.
    "Высокий Дом": "Высокого Дома",
    "Вольный Союз": "Вольного Союза",
    "Подгорное Королевство": "Подгорного Королевства",
    "Клановый Союз": "Кланового Союза",
    "Лесное Владение": "Лесного Владения",
    "Вечный Лес": "Вечного Леса",
    "Светлое Королевство": "Светлого Королевства",
    "Тёмный Дом": "Тёмного Дома",
    "Подземное Царство": "Подземного Царства",
    "Песчаный Союз": "Песчаного Союза",
    "Союз Стай": "Союза Стай",
    "Горный Союз": "Горного Союза",
    "Поднебесное Вождество": "Поднебесного Вождества",
    "Союз Гнёзд": "Союза Гнёзд",
    "Город-кузня": "Города-кузни",
    "Медвежий двор": "Медвежьего двора",
    "Подземный город": "Подземного города",
    "Утёсный город": "Утёсного города",
}


def genitive_noun(word: str) -> str:
    """Родительный падеж: «Род» -> «Рода», «Стая» -> «Стаи», «Гнездо» -> «Гнезда».

    Нужен для оборотов вроде «откалывается от рода „Дом Костра“». Правил
    хватает на весь словарь генератора; особые случаи — в словаре выше.
    """
    if not word:
        return word
    known = GENITIVE_EXCEPTIONS.get(word)
    if known:
        return known
    if word.endswith("ье"):
        return word[:-1] + "я"
    last = word[-1]
    stem = word[:-1]
    if last == "а":
        return stem + ("и" if stem[-1:].lower() in "гкхжшчщ" else "ы")
    if last in "яь":
        return stem + "и"
    if last == "о":
        return stem + "а"
    if last == "е":
        return stem + ("а" if stem[-1:].lower() in "жшчщ" else "я")
    if last == "й":
        return stem + "я"
    return word + "а"


ROMAN_STEPS = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
               (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
               (5, "V"), (4, "IV"), (1, "I"))


def roman(number: int) -> str:
    """Римская цифра для порядкового номера правителя: 4 -> «IV»."""
    number = int(number)
    if number <= 0:
        return ""
    out = []
    for value, sign in ROMAN_STEPS:
        while number >= value:
            out.append(sign)
            number -= value
    return "".join(out)


DATIVE_EXCEPTIONS = {
    "Высокий Дом": "Высокому Дому",
    "Племя": "Племени",
}


def dative_noun(word: str) -> str:
    """Дательный падеж: «Дом» -> «Дому», «Стая» -> «Стае», «Сень» -> «Сени»."""
    if not word:
        return word
    known = DATIVE_EXCEPTIONS.get(word)
    if known:
        return known
    last = word[-1]
    stem = word[:-1]
    if last in "ая":
        return stem + "е"
    if last == "ь":
        return stem + "и"
    if last == "о":
        return stem + "у"
    if last == "е":
        return stem + "ю"
    if last == "й":
        return stem + "ю"
    return word + "у"


def gendered(word_pair, sex: str) -> str:
    """Выбирает форму из пары (мужская, женская) по полу персонажа."""
    if isinstance(word_pair, (tuple, list)):
        return word_pair[1] if sex == "f" and len(word_pair) > 1 else word_pair[0]
    # Одиночное прилагательное склоняем автоматически.
    forms = decline_adjective(word_pair)
    return forms[1] if sex == "f" else forms[0]
