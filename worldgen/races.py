# -*- coding: utf-8 -*-
"""Расы мира и их культурные особенности.

Три категории:

* ``CIVILIZED``  — цивилизованные народы: строят племена, города и страны.
* ``BEASTFOLK``  — зверолюды: разумны, но живут только племенами.
* ``EVIL``       — злые расы: не создают стран и городов, только лагеря,
                   логова и орды.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- типы местности ----------------------------------------------------

FOREST = "лес"
MOUNTAIN = "горы"
HILLS = "холмы"
STEPPE = "степь"
PLAIN = "равнина"
SWAMP = "болото"
COAST = "побережье"
TUNDRA = "тундра"
DESERT = "пустыня"
JUNGLE = "джунгли"
UNDERGROUND = "подземья"
ISLANDS = "острова"

TERRAINS = (
    FOREST, MOUNTAIN, HILLS, STEPPE, PLAIN, SWAMP,
    COAST, TUNDRA, DESERT, JUNGLE, UNDERGROUND, ISLANDS,
)

# Насколько земля богата: влияет на предельный размер населения.
TERRAIN_CAPACITY = {
    FOREST: 1.0, MOUNTAIN: 0.7, HILLS: 0.9, STEPPE: 0.8, PLAIN: 1.3,
    SWAMP: 0.5, COAST: 1.2, TUNDRA: 0.4, DESERT: 0.4, JUNGLE: 0.9,
    UNDERGROUND: 0.6, ISLANDS: 0.7,
}

# --- категории ---------------------------------------------------------

CIVILIZED = "civilized"
BEASTFOLK = "beastfolk"
EVIL = "evil"
MONSTER = "monster"          # не народы мира, а его бедствия

CATEGORY_NAMES = {
    CIVILIZED: "Цивилизованные народы",
    BEASTFOLK: "Зверолюды",
    EVIL: "Злые расы",
    MONSTER: "Бедствия мира",
}

# Расы, которые просыпаются в мире и живут в нём своей жизнью.
MORTAL_CATEGORIES = (CIVILIZED, BEASTFOLK, EVIL)

# --- законы наследования -----------------------------------------------
#
# Порядок престолонаследия — главное культурное различие между народами.
# Человеческий трон переходит старшему сыну, дворфийский — старшему в клане,
# у тёмных эльфов правят женщины, у волколюдов власть берут с боем.

MALE_PRIMOGENITURE = "male_primogeniture"      # старший сын, потом дочери
ABSOLUTE_PRIMOGENITURE = "absolute_primogeniture"  # старший ребёнок любого пола
SENIORITY = "seniority"                        # старший в роду (брат раньше сына)
MATRILINEAL = "matrilineal"                    # старшая дочь, женская линия
COUNCIL = "council"                            # совет выбирает достойнейшего в доме
ELECTIVE = "elective"                          # знать выбирает из всех домов
STRENGTH = "strength"                          # власть берёт сильнейший

SUCCESSION_NAMES = {
    MALE_PRIMOGENITURE: "престол наследует старший сын",
    ABSOLUTE_PRIMOGENITURE: "престол наследует старший из детей",
    SENIORITY: "престол наследует старший в роду",
    MATRILINEAL: "престол наследует старшая дочь",
    COUNCIL: "правителя выбирает совет дома",
    ELECTIVE: "правителя выбирает знать из всех домов",
    STRENGTH: "власть берёт сильнейший",
}

# Формы правления, при которых наследование всегда выборное.
ELECTIVE_FORMS = (
    "Вольный Союз", "Клановый Союз", "Союз Стай", "Союз Гнёзд",
    "Песчаный Союз", "Горный Союз", "Ковенант",
)


@dataclass(frozen=True)
class Race:
    """Описание расы."""

    id: str
    name: str                 # «Эльфы»
    gen_plural: str           # «эльфов» — для оборота «страна эльфов»
    adj: str                  # «Эльфийский» — склоняется автоматически
    noun_m: str               # «эльф»
    noun_f: str               # «эльфийка»
    category: str
    group: str                # объединение родственных рас для интерфейса
    style: str                # ключ стиля имён в names.py
    terrains: tuple           # предпочитаемые земли (по убыванию желания)
    first_era: int            # индекс эпохи пробуждения
    lifespan: tuple           # (минимум, максимум) лет жизни
    growth: float             # базовый прирост населения в год
    expansion: float          # склонность основывать новые поселения
    traits: tuple             # ключевые слова для текстов летописи
    tribe_words: tuple        # «Племя», «Клан», ...
    settlement_words: tuple = ()   # «Город», «Крепость», ...
    polity_words: tuple = ()       # «Королевство», «Держава», ...
    camp_words: tuple = ()         # «Лагерь», «Логово», ...
    chief_titles: tuple = ()       # титул вождя племени (муж., жен.)
    founder_titles: tuple = ()     # титул основателя города
    ruler_titles: tuple = ()       # титул правителя страны
    settles: bool = True           # может ли строить постоянные поселения
    builds_states: bool = True     # может ли основывать страны

    # --- знать и наследование (блок 2) ---
    succession: str = MALE_PRIMOGENITURE
    adulthood: int = 16            # возраст совершеннолетия
    fertility: tuple = (1, 5)      # сколько детей бывает в семье
    coup_propensity: float = 1.0   # склонность к переворотам и мятежам
    has_nobility: bool = True      # есть ли знатные роды
    house_words: tuple = ("Дом",)  # «Дом», «Клан», «Род», «Стая», «Гнездо»
    noble_titles: tuple = ()       # титулы знати от старшего к младшему
    heir_titles: tuple = ()        # титул наследника
    regent_titles: tuple = ()      # титул регента

    @property
    def is_evil(self) -> bool:
        return self.category == EVIL

    def noun(self, sex: str) -> str:
        return self.noun_f if sex == "f" else self.noun_m

    def noble_title(self, rank: int, sex: str) -> str:
        """Титул знатного лица: 0 — глава великого дома, дальше — помельче."""
        if not self.noble_titles:
            return "лорд" if sex != "f" else "леди"
        pair = self.noble_titles[min(rank, len(self.noble_titles) - 1)]
        return pair[1] if (sex == "f" and len(pair) > 1) else pair[0]

    def succession_for(self, form: str) -> str:
        """Закон наследования с поправкой на форму правления."""
        if form in ELECTIVE_FORMS:
            return ELECTIVE
        return self.succession


def _t(*names) -> tuple:
    return tuple(names)


RACES = (
    # ------------------------------------------------------------------
    # Цивилизованные народы
    # ------------------------------------------------------------------
    Race(
        id="human", name="Люди", gen_plural="людей", adj="Людской",
        noun_m="человек", noun_f="женщина",
        category=CIVILIZED, group="Люди", style="human",
        terrains=_t(PLAIN, COAST, HILLS, STEPPE, FOREST, MOUNTAIN, TUNDRA, DESERT),
        first_era=1, lifespan=(55, 85), growth=0.0062, expansion=1.35,
        traits=("хлебопашцы", "мореходы", "строители дорог", "торговцы"),
        tribe_words=_t("Племя", "Род", "Ватага"),
        settlement_words=_t("Город", "Крепость", "Порт", "Застава", "Торжище"),
        polity_words=_t("Королевство", "Княжество", "Герцогство", "Вольный Союз", "Империя"),
        chief_titles=_t("вождь", "вождица"),
        founder_titles=_t("основатель", "основательница"),
        ruler_titles=_t("король", "королева"),
        succession=MALE_PRIMOGENITURE, adulthood=16, fertility=(1, 6),
        coup_propensity=1.0, house_words=_t("Дом", "Род"),
        noble_titles=(("герцог", "герцогиня"), ("граф", "графиня"),
                      ("барон", "баронесса"), ("лорд", "леди")),
        heir_titles=("наследный принц", "наследная принцесса"),
        regent_titles=("регент", "регентша"),
    ),
    Race(
        id="dwarf", name="Дворфы", gen_plural="дворфов", adj="Дворфийский",
        noun_m="дворф", noun_f="дворфийка",
        category=CIVILIZED, group="Дворфы", style="dwarf",
        terrains=_t(MOUNTAIN, UNDERGROUND, HILLS, TUNDRA, PLAIN),
        first_era=0, lifespan=(180, 320), growth=0.0040, expansion=0.8,
        traits=("камнерезы", "рудознатцы", "кузнецы", "хранители рун"),
        tribe_words=_t("Клан", "Род", "Артель"),
        settlement_words=_t("Чертог", "Твердыня", "Рудник", "Город-кузня", "Застава"),
        polity_words=_t("Подгорное Королевство", "Держава", "Клановый Союз", "Твердыня"),
        chief_titles=_t("старейшина", "старейшина"),
        founder_titles=_t("тан", "тана"),
        ruler_titles=_t("король-под-горой", "королева-под-горой"),
        succession=SENIORITY, adulthood=40, fertility=(1, 4),
        coup_propensity=0.45, house_words=_t("Клан"),
        noble_titles=(("тан", "тана"), ("старейшина клана", "старейшина клана"),
                      ("мастер", "мастерица")),
        heir_titles=("наследник клана", "наследница клана"),
        regent_titles=("наместник", "наместница"),
    ),
    Race(
        id="elf", name="Эльфы", gen_plural="эльфов", adj="Эльфийский",
        noun_m="эльф", noun_f="эльфийка",
        category=CIVILIZED, group="Эльфы", style="elf",
        terrains=_t(FOREST, JUNGLE, HILLS, COAST, PLAIN),
        first_era=0, lifespan=(600, 1100), growth=0.0032, expansion=0.7,
        traits=("следопыты", "лучники", "певцы леса", "звездочёты"),
        tribe_words=_t("Ветвь", "Круг", "Сень"),
        settlement_words=_t("Город", "Чертог", "Приют", "Святилище", "Пристань"),
        polity_words=_t("Лесное Владение", "Королевство", "Вечный Лес", "Дом"),
        chief_titles=_t("хранитель", "хранительница"),
        founder_titles=_t("зодчий", "зодчая"),
        ruler_titles=_t("владыка", "владычица"),
        succession=COUNCIL, adulthood=90, fertility=(1, 4),
        coup_propensity=0.35, house_words=_t("Дом", "Сень"),
        noble_titles=(("лорд", "леди"), ("хранитель", "хранительница")),
        heir_titles=("преемник", "преемница"),
        regent_titles=("наместник", "наместница"),
    ),
    Race(
        id="high_elf", name="Высшие эльфы", gen_plural="высших эльфов",
        adj="Высокоэльфийский", noun_m="высший эльф", noun_f="высшая эльфийка",
        category=CIVILIZED, group="Эльфы", style="high_elf",
        terrains=_t(COAST, ISLANDS, HILLS, PLAIN, MOUNTAIN),
        first_era=0, lifespan=(900, 1600), growth=0.0028, expansion=0.6,
        traits=("чародеи", "звездочёты", "хранители памяти", "зодчие света"),
        tribe_words=_t("Дом", "Круг", "Сень"),
        settlement_words=_t("Город", "Башня", "Чертог", "Святилище", "Гавань"),
        polity_words=_t("Светлое Королевство", "Высокий Дом", "Владение", "Престол"),
        chief_titles=_t("старший", "старшая"),
        founder_titles=_t("архитектор", "архитекторша"),
        ruler_titles=_t("архонт", "архонтесса"),
        succession=ABSOLUTE_PRIMOGENITURE, adulthood=110, fertility=(1, 3),
        coup_propensity=0.28, house_words=_t("Высокий Дом", "Дом"),
        noble_titles=(("высокий лорд", "высокая леди"), ("лорд", "леди")),
        heir_titles=("первородный", "первородная"),
        regent_titles=("наместник", "наместница"),
    ),
    Race(
        id="dark_elf", name="Тёмные эльфы", gen_plural="тёмных эльфов",
        adj="Тёмноэльфийский", noun_m="тёмный эльф", noun_f="тёмная эльфийка",
        category=CIVILIZED, group="Эльфы", style="dark_elf",
        terrains=_t(UNDERGROUND, SWAMP, FOREST, MOUNTAIN, DESERT),
        first_era=1, lifespan=(500, 950), growth=0.0034, expansion=0.9,
        traits=("отравители", "работорговцы", "тенемаги", "паучьи жрецы"),
        tribe_words=_t("Дом", "Гнездо", "Ковен"),
        settlement_words=_t("Город", "Крепость", "Святилище", "Яма", "Подземный город"),
        polity_words=_t("Владычество", "Тёмный Дом", "Подземное Царство", "Ковенант"),
        chief_titles=_t("матрон", "матрона"),
        founder_titles=_t("зодчий тьмы", "зодчая тьмы"),
        ruler_titles=_t("владыка", "владычица"),
        succession=MATRILINEAL, adulthood=80, fertility=(1, 4),
        coup_propensity=1.75, house_words=_t("Дом"),
        noble_titles=(("матрон", "матрона"), ("наставник", "наставница")),
        heir_titles=("наследник дома", "наследница дома"),
        regent_titles=("наместник", "наместница"),
    ),
    Race(
        id="catfolk", name="Кошколюды", gen_plural="кошколюдов", adj="Кошачий",
        noun_m="кошколюд", noun_f="кошколюдка",
        category=CIVILIZED, group="Полулюди", style="catfolk",
        terrains=_t(DESERT, STEPPE, PLAIN, JUNGLE, COAST),
        first_era=2, lifespan=(50, 75), growth=0.0068, expansion=1.2,
        traits=("караванщики", "воры", "танцоры клинка", "звёздные гадатели"),
        tribe_words=_t("Прайд", "Племя", "Караван"),
        settlement_words=_t("Город", "Оазис", "Торжище", "Застава"),
        polity_words=_t("Ханство", "Вождество", "Песчаный Союз", "Княжество"),
        chief_titles=_t("вожак", "вожачиха"),
        founder_titles=_t("основатель", "основательница"),
        ruler_titles=_t("хан", "ханша"),
        succession=ELECTIVE, adulthood=15, fertility=(2, 6),
        coup_propensity=1.15, house_words=_t("Род", "Прайд"),
        noble_titles=(("бек", "бека"), ("старший каравана", "старшая каравана")),
        heir_titles=("наследник", "наследница"),
        regent_titles=("опекун", "опекунша"),
    ),
    Race(
        id="wolfkin", name="Волколюды", gen_plural="волколюдов", adj="Волчий",
        noun_m="волколюд", noun_f="волколюдка",
        category=CIVILIZED, group="Полулюди", style="wolfkin",
        terrains=_t(TUNDRA, FOREST, HILLS, MOUNTAIN, STEPPE),
        first_era=2, lifespan=(45, 70), growth=0.0072, expansion=1.3,
        traits=("загонщики", "следопыты", "лунные певцы", "воители"),
        tribe_words=_t("Стая", "Племя", "Свора"),
        settlement_words=_t("Городище", "Крепость", "Застава", "Стойбище"),
        polity_words=_t("Союз Стай", "Вождество", "Княжество", "Королевство"),
        chief_titles=_t("вожак стаи", "вожачиха стаи"),
        founder_titles=_t("основатель", "основательница"),
        ruler_titles=_t("вождь-король", "вождь-королева"),
        succession=STRENGTH, adulthood=15, fertility=(2, 6),
        coup_propensity=1.45, house_words=_t("Стая", "Род"),
        noble_titles=(("ярл", "ярла"), ("вожак", "вожачиха")),
        heir_titles=("наследник", "наследница"),
        regent_titles=("опекун", "опекунша"),
    ),
    Race(
        id="bearkin", name="Медведолюды", gen_plural="медведолюдов", adj="Медвежий",
        noun_m="медведолюд", noun_f="медведолюдка",
        category=CIVILIZED, group="Полулюди", style="bearkin",
        terrains=_t(MOUNTAIN, FOREST, TUNDRA, HILLS),
        first_era=2, lifespan=(60, 95), growth=0.0044, expansion=0.85,
        traits=("бортники", "знахари", "берсерки", "хранители очага"),
        tribe_words=_t("Род", "Племя", "Берлога"),
        settlement_words=_t("Городище", "Твердыня", "Застава", "Медвежий двор"),
        polity_words=_t("Вождество", "Княжество", "Горный Союз"),
        chief_titles=_t("старший", "старшая"),
        founder_titles=_t("основатель", "основательница"),
        ruler_titles=_t("князь", "княгиня"),
        succession=SENIORITY, adulthood=18, fertility=(1, 4),
        coup_propensity=0.7, house_words=_t("Род"),
        noble_titles=(("князь", "княгиня"), ("старший рода", "старшая рода")),
        heir_titles=("наследник", "наследница"),
        regent_titles=("опекун", "опекунша"),
    ),
    Race(
        id="foxkin", name="Лисолюды", gen_plural="лисолюдов", adj="Лисий",
        noun_m="лисолюд", noun_f="лисолюдка",
        category=CIVILIZED, group="Полулюди", style="foxkin",
        terrains=_t(FOREST, HILLS, PLAIN, COAST),
        first_era=2, lifespan=(55, 80), growth=0.0060, expansion=1.15,
        traits=("сказители", "менестрели", "лисьи хитрецы", "травники"),
        tribe_words=_t("Выводок", "Племя", "Круг"),
        settlement_words=_t("Город", "Торжище", "Приют", "Застава"),
        polity_words=_t("Княжество", "Вольный Союз", "Вождество"),
        chief_titles=_t("старший", "старшая"),
        founder_titles=_t("основатель", "основательница"),
        ruler_titles=_t("князь", "княгиня"),
        succession=ELECTIVE, adulthood=15, fertility=(2, 6),
        coup_propensity=1.05, house_words=_t("Дом"),
        noble_titles=(("господин", "госпожа"), ("старший дома", "старшая дома")),
        heir_titles=("наследник", "наследница"),
        regent_titles=("опекун", "опекунша"),
    ),
    Race(
        id="birdkin", name="Птицелюды", gen_plural="птицелюдов", adj="Птичий",
        noun_m="птицелюд", noun_f="птицелюдка",
        category=CIVILIZED, group="Полулюди", style="birdkin",
        terrains=_t(MOUNTAIN, ISLANDS, COAST, HILLS, TUNDRA),
        first_era=2, lifespan=(50, 78), growth=0.0050, expansion=1.0,
        traits=("вестники", "небесные дозорные", "собиратели ветров", "гнездовщики"),
        tribe_words=_t("Стая", "Гнездовье", "Клин"),
        settlement_words=_t("Гнездовье", "Башня", "Утёсный город", "Дозор"),
        polity_words=_t("Поднебесное Вождество", "Союз Гнёзд", "Княжество"),
        chief_titles=_t("старший", "старшая"),
        founder_titles=_t("основатель", "основательница"),
        ruler_titles=_t("владыка небес", "владычица небес"),
        succession=ABSOLUTE_PRIMOGENITURE, adulthood=15, fertility=(1, 4),
        coup_propensity=0.8, house_words=_t("Гнездо", "Клин"),
        noble_titles=(("старший гнезда", "старшая гнезда"), ("дозорный", "дозорная")),
        heir_titles=("первенец", "первенец"),
        regent_titles=("опекун", "опекунша"),
    ),

    # ------------------------------------------------------------------
    # Зверолюды — только племена
    # ------------------------------------------------------------------
    Race(
        id="lizardfolk", name="Ящеролюды", gen_plural="ящеролюдов", adj="Ящеролюдский",
        noun_m="ящеролюд", noun_f="ящеролюдка",
        category=BEASTFOLK, group="Зверолюды", style="lizardfolk",
        terrains=_t(SWAMP, JUNGLE, COAST, ISLANDS),
        first_era=0, lifespan=(70, 120), growth=0.0034, expansion=0.9,
        traits=("болотные охотники", "хранители яиц", "шаманы тины"),
        tribe_words=_t("Выводок", "Племя", "Кладка"),
        chief_titles=_t("вождь", "вождица"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=14, fertility=(2, 7),
        coup_propensity=1.2, has_nobility=False,
    ),
    Race(
        id="serpentfolk", name="Змеелюды", gen_plural="змеелюдов", adj="Змеиный",
        noun_m="змеелюд", noun_f="змеелюдка",
        category=BEASTFOLK, group="Зверолюды", style="serpentfolk",
        terrains=_t(JUNGLE, DESERT, UNDERGROUND, SWAMP),
        first_era=0, lifespan=(120, 240), growth=0.0022, expansion=0.8,
        traits=("заклинатели", "хранители древних знаний", "ядотворцы"),
        tribe_words=_t("Гнездо", "Племя", "Кольцо"),
        chief_titles=_t("старший", "старшая"),
        settles=False, builds_states=False,
        succession=COUNCIL, adulthood=30, fertility=(1, 4),
        coup_propensity=0.9, has_nobility=False,
    ),
    Race(
        id="toadfolk", name="Жаболюды", gen_plural="жаболюдов", adj="Жаболюдский",
        noun_m="жаболюд", noun_f="жаболюдка",
        category=BEASTFOLK, group="Зверолюды", style="toadfolk",
        terrains=_t(SWAMP, COAST, JUNGLE),
        first_era=1, lifespan=(40, 70), growth=0.0058, expansion=1.0,
        traits=("собиратели тины", "громкоголосые", "ловцы пиявок"),
        tribe_words=_t("Племя", "Трясина", "Хор"),
        chief_titles=_t("вождь", "вождица"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=10, fertility=(3, 8),
        coup_propensity=1.1, has_nobility=False,
    ),
    Race(
        id="turtlefolk", name="Черепахолюды", gen_plural="черепахолюдов",
        adj="Черепаший", noun_m="черепахолюд", noun_f="черепахолюдка",
        category=BEASTFOLK, group="Зверолюды", style="turtlefolk",
        terrains=_t(COAST, ISLANDS, SWAMP),
        first_era=1, lifespan=(200, 400), growth=0.0014, expansion=0.5,
        traits=("медлительные мудрецы", "рыболовы", "хранители отмелей"),
        tribe_words=_t("Племя", "Отмель", "Круг"),
        chief_titles=_t("старейший", "старейшая"),
        settles=False, builds_states=False,
        succession=SENIORITY, adulthood=40, fertility=(1, 3),
        coup_propensity=0.4, has_nobility=False,
    ),
    Race(
        id="crabfolk", name="Панцирный народ", gen_plural="панцирников",
        adj="Панцирный", noun_m="панцирник", noun_f="панцирница",
        category=BEASTFOLK, group="Зверолюды", style="crabfolk",
        terrains=_t(COAST, ISLANDS, SWAMP),
        first_era=2, lifespan=(35, 60), growth=0.0062, expansion=0.9,
        traits=("собиратели прибоя", "ломатели раковин", "солевары"),
        tribe_words=_t("Стая", "Племя", "Клешня"),
        chief_titles=_t("вождь", "вождица"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=10, fertility=(2, 7),
        coup_propensity=1.0, has_nobility=False,
    ),

    # ------------------------------------------------------------------
    # Злые расы — только лагеря и логова
    # ------------------------------------------------------------------
    Race(
        id="orc", name="Орки", gen_plural="орков", adj="Орочий",
        noun_m="орк", noun_f="орчиха",
        category=EVIL, group="Злые расы", style="orc",
        terrains=_t(STEPPE, HILLS, MOUNTAIN, PLAIN, DESERT),
        first_era=1, lifespan=(35, 60), growth=0.0090, expansion=1.6,
        traits=("налётчики", "костоломы", "почитатели войны"),
        tribe_words=_t("Орда", "Клан", "Свора"),
        camp_words=_t("Лагерь", "Стан", "Костровище", "Орда"),
        chief_titles=_t("вожак", "вожачиха"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=13, fertility=(2, 7),
        coup_propensity=1.9, has_nobility=False,
    ),
    Race(
        id="goblin", name="Гоблины", gen_plural="гоблинов", adj="Гоблинский",
        noun_m="гоблин", noun_f="гоблинша",
        category=EVIL, group="Злые расы", style="goblin",
        terrains=_t(UNDERGROUND, HILLS, FOREST, SWAMP),
        first_era=1, lifespan=(25, 45), growth=0.0120, expansion=1.8,
        traits=("падальщики", "ловушечники", "крикуны"),
        tribe_words=_t("Свора", "Выводок", "Шайка"),
        camp_words=_t("Логово", "Нора", "Яма", "Гнездовище"),
        chief_titles=_t("главарь", "главариха"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=10, fertility=(3, 9),
        coup_propensity=2.1, has_nobility=False,
    ),
    Race(
        id="troll", name="Тролли", gen_plural="троллей", adj="Троллий",
        noun_m="тролль", noun_f="троллиха",
        category=EVIL, group="Злые расы", style="troll",
        terrains=_t(MOUNTAIN, SWAMP, TUNDRA, UNDERGROUND),
        first_era=0, lifespan=(150, 300), growth=0.0020, expansion=0.6,
        traits=("камнееды", "одиночки", "пожиратели"),
        tribe_words=_t("Род", "Свора"),
        camp_words=_t("Логово", "Пещера", "Мостовище"),
        chief_titles=_t("старший", "старшая"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=30, fertility=(1, 3),
        coup_propensity=1.3, has_nobility=False,
    ),
    Race(
        id="ogre", name="Огры", gen_plural="огров", adj="Огрский",
        noun_m="огр", noun_f="огрица",
        category=EVIL, group="Злые расы", style="ogre",
        terrains=_t(HILLS, MOUNTAIN, PLAIN, TUNDRA),
        first_era=2, lifespan=(50, 90), growth=0.0048, expansion=0.9,
        traits=("дубиноносцы", "обжоры", "костоломы"),
        tribe_words=_t("Свора", "Род"),
        camp_words=_t("Стан", "Логово", "Костровище"),
        chief_titles=_t("вожак", "вожачиха"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=16, fertility=(1, 4),
        coup_propensity=1.6, has_nobility=False,
    ),
    Race(
        id="kobold", name="Кобольды", gen_plural="кобольдов", adj="Кобольдский",
        noun_m="кобольд", noun_f="кобольдиха",
        category=EVIL, group="Злые расы", style="kobold",
        terrains=_t(UNDERGROUND, MOUNTAIN, HILLS, DESERT),
        first_era=2, lifespan=(20, 40), growth=0.0130, expansion=1.7,
        traits=("рудокопы-воришки", "ловушечники", "сторожа драконьих троп"),
        tribe_words=_t("Выводок", "Свора"),
        camp_words=_t("Нора", "Штольня", "Логово", "Яма"),
        chief_titles=_t("главарь", "главариха"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=8, fertility=(3, 9),
        coup_propensity=2.0, has_nobility=False,
    ),
    Race(
        id="gnoll", name="Гноллы", gen_plural="гноллов", adj="Гнолльский",
        noun_m="гнолл", noun_f="гноллиха",
        category=EVIL, group="Злые расы", style="gnoll",
        terrains=_t(STEPPE, DESERT, PLAIN, HILLS),
        first_era=2, lifespan=(30, 50), growth=0.0100, expansion=1.5,
        traits=("людоеды", "хохочущие охотники", "работорговцы"),
        tribe_words=_t("Стая", "Свора"),
        camp_words=_t("Стан", "Логово", "Костровище", "Свалка"),
        chief_titles=_t("вожак", "вожачиха"),
        settles=False, builds_states=False,
        succession=STRENGTH, adulthood=12, fertility=(2, 7),
        coup_propensity=1.8, has_nobility=False,
    ),
)

# ---------------------------------------------------------------------------
# Бедствия мира: демоны, драконы, нежить и прочие незваные гости.
#
# Это не народы: они не просыпаются вместе со всеми, не заводят племён,
# городов и стран. Они приходят извне, оставляют по себе выжженные земли
# и уходят — а их вожди попадают в летопись наравне с королями.
# ---------------------------------------------------------------------------

MONSTERS = (
    Race(
        id="demon", name="Демоны", gen_plural="демонов", adj="Демонический",
        noun_m="демон", noun_f="демоница",
        category=MONSTER, group="Бедствия мира", style="demon",
        terrains=_t(MOUNTAIN, DESERT, UNDERGROUND, STEPPE),
        first_era=9, lifespan=(900, 4000), growth=0.0, expansion=0.0,
        traits=("пожиратели душ", "владыки пламени", "искусители"),
        tribe_words=_t("Легион", "Орда"),
        chief_titles=_t("владыка демонов", "владычица демонов"),
        settles=False, builds_states=False, has_nobility=False,
        succession=STRENGTH, adulthood=100,
    ),
    Race(
        id="dragon", name="Драконы", gen_plural="драконов", adj="Драконий",
        noun_m="дракон", noun_f="драконица",
        category=MONSTER, group="Бедствия мира", style="dragon",
        terrains=_t(MOUNTAIN, HILLS, ISLANDS, DESERT),
        first_era=9, lifespan=(1500, 7000), growth=0.0, expansion=0.0,
        traits=("крылатые бедствия", "хранители золота", "древние ящеры"),
        tribe_words=_t("Стая", "Выводок"),
        chief_titles=_t("великий дракон", "великая драконица"),
        settles=False, builds_states=False, has_nobility=False,
        succession=STRENGTH, adulthood=200,
    ),
    Race(
        id="undead", name="Нежить", gen_plural="нежити", adj="Мёртвый",
        noun_m="мертвец", noun_f="мертвячка",
        category=MONSTER, group="Бедствия мира", style="undead",
        terrains=_t(SWAMP, UNDERGROUND, TUNDRA, PLAIN),
        first_era=9, lifespan=(500, 9000), growth=0.0, expansion=0.0,
        traits=("ходячие кости", "слуги праха", "не знающие усталости"),
        tribe_words=_t("Легион", "Воинство"),
        chief_titles=_t("великий лич", "великая личесса"),
        settles=False, builds_states=False, has_nobility=False,
        succession=STRENGTH, adulthood=50,
    ),
    Race(
        id="deep_one", name="Глубоководные", gen_plural="глубоководных",
        adj="Глубинный", noun_m="глубоководный", noun_f="глубоководная",
        category=MONSTER, group="Бедствия мира", style="deep_one",
        terrains=_t(COAST, ISLANDS, SWAMP),
        first_era=9, lifespan=(800, 5000), growth=0.0, expansion=0.0,
        traits=("дети бездны", "поющие в воде", "безглазые"),
        tribe_words=_t("Косяк", "Воинство"),
        chief_titles=_t("владыка глубин", "владычица глубин"),
        settles=False, builds_states=False, has_nobility=False,
        succession=STRENGTH, adulthood=60,
    ),
    Race(
        id="swarm", name="Роевые твари", gen_plural="роевых тварей",
        adj="Роевой", noun_m="трутень", noun_f="матка",
        category=MONSTER, group="Бедствия мира", style="swarm",
        terrains=_t(JUNGLE, DESERT, STEPPE, PLAIN),
        first_era=9, lifespan=(20, 300), growth=0.0, expansion=0.0,
        traits=("пожиратели полей", "бесчисленные", "жвалы и хитин"),
        tribe_words=_t("Рой", "Гнездо"),
        chief_titles=_t("роевой владыка", "роевая матка"),
        settles=False, builds_states=False, has_nobility=False,
        succession=STRENGTH, adulthood=5,
    ),
    Race(
        id="void", name="Порождения Пустоты", gen_plural="порождений пустоты",
        adj="Пустотный", noun_m="пустотник", noun_f="пустотница",
        category=MONSTER, group="Бедствия мира", style="void",
        terrains=_t(TUNDRA, UNDERGROUND, DESERT, MOUNTAIN),
        first_era=9, lifespan=(100, 9000), growth=0.0, expansion=0.0,
        traits=("то, чему нет имени", "пришедшие из ниоткуда", "неправильные"),
        tribe_words=_t("Стая", "Скопище"),
        chief_titles=_t("владыка пустоты", "владычица пустоты"),
        settles=False, builds_states=False, has_nobility=False,
        succession=STRENGTH, adulthood=10,
    ),
)

ALL_RACES = RACES + MONSTERS
RACES_BY_ID = {race.id: race for race in ALL_RACES}


def get_race(race_id: str) -> Race:
    return RACES_BY_ID[race_id]


def races_of(category: str) -> tuple:
    return tuple(race for race in ALL_RACES if race.category == category)


def mortal_races() -> tuple:
    """Народы, которые просыпаются в мире и живут в нём."""
    return tuple(race for race in RACES if race.category in MORTAL_CATEGORIES)


def monster(monster_id: str) -> Race:
    return RACES_BY_ID[monster_id]


def playable_groups() -> tuple:
    """Уникальные группы рас в порядке появления (для интерфейса)."""
    groups = []
    for race in RACES:
        if race.group not in groups:
            groups.append(race.group)
    return tuple(groups)
