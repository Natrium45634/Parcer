# -*- coding: utf-8 -*-
"""Контекст генерации: всё, что нужно подсистемам для работы.

Через него подсистемы получают мир, потоки случайных чисел, кузницу имён
и общие вспомогательные операции (создать личность, выбрать землю).
"""

from __future__ import annotations

from . import races as races_mod
from .eras import spec_for
from .names import NameForge
from .rng import RngHub
from .timeline import Date


# Эталонная длительность: под неё подобраны все скорости движка.
REFERENCE_YEARS = 10000.0


class GenContext:
    def __init__(self, world, settings):
        self.world = world
        self.settings = settings
        # Короткую историю надо проживать быстрее, иначе за 500 лет племена
        # не успеют вырасти до городов и мир останется первобытным.
        # Длинную историю не замедляем — пусть копится.
        tempo = max(1.0, REFERENCE_YEARS / max(1, int(settings.years)))
        self.tempo = tempo
        self.growth_scale = min(tempo, 20.0)
        self.rate_scale = min(tempo ** 0.5, 6.0)
        self.hub = RngHub(world.seed_value)
        self.forge = NameForge()
        self.map = None              # связь с картой .world, если она задана
        # Движок настроен на восемнадцать земель. На большой карте их
        # втрое больше, и без поправки мир заселялся бы втрое медленнее.
        self.world_scale = 1.0
        self.region_weights = {}     # race_id -> список (region_id, вес)
        self.awakened = []           # расы в порядке пробуждения
        self.awakened_ids = set()
        self.schedule = {}           # год -> список race_id
        self.darkness = {}           # земля -> тяжесть тёмных веков (0…1)
        self.world_darkness = 0.0    # общемировая тяжесть
        self.calamity_bias = {}      # нрав мира: к каким бедам он склонен
        self.calamity_last = {}
        self.calamity_plans = {}
        self.climate_plan = []       # перемены климата, вписанные в карту
        self.expedition_due = {}     # поход -> год возвращения
        self.expedition_attempts = {}  # цель -> сколько раз к ней ходили
        self.notable_done = {}       # ремесло -> уже сделанные работы
        self.lair_of_relic = {}      # след -> логово карты, из которого он взялся
        self.piety = 1.0             # набожность мира
        self.dark_tilt = 0.0         # склонность богов к тьме
        self.faith_style = "многобожие"
        self.faith_dawn = 10 ** 9    # год, когда родится первая вера

    # ------------------------------------------------------------------
    # Случайность
    # ------------------------------------------------------------------

    def rng(self, *parts):
        return self.hub.stream(*parts)

    # ------------------------------------------------------------------
    # Эпохи
    # ------------------------------------------------------------------

    def era_spec(self, year: int):
        return spec_for(self.world.era_index_at(year))

    def density(self) -> float:
        return getattr(self.settings, "density", 1.0)

    def rate(self, base: float) -> float:
        """Годовая вероятность события с учётом плотности, темпа и тьмы."""
        return base * self.density() * self.rate_scale * \
            max(0.25, 1.0 - 0.5 * self.world_darkness)

    def spread_rate(self, base: float) -> float:
        """То же, но для расселения: чем мир шире, тем больше в нём места."""
        return min(0.95, self.rate(base) * self.world_scale)

    def set_world_scale(self, region_count: int) -> None:
        reference = 18.0
        self.world_scale = max(1.0, min(4.0, (region_count / reference) ** 0.65))

    def growth(self, base: float, region_id: str = "") -> float:
        """Годовой прирост населения. В тёмные века он уходит в минус."""
        gloom = self.gloom(region_id)
        return base * self.growth_scale * max(-0.35, 1.0 - 1.15 * gloom)

    def gloom(self, region_id: str = "") -> float:
        """Насколько тяжело живётся в этой земле прямо сейчас."""
        value = self.world_darkness
        if region_id:
            value = max(value, self.darkness.get(region_id, 0.0))
        return min(1.0, value)

    def refresh_darkness(self, year: int) -> None:
        self.darkness = self.world.darkness_snapshot(year)
        self.world_darkness = self.darkness.get("", 0.0)

    # ------------------------------------------------------------------
    # Земли
    # ------------------------------------------------------------------

    def build_region_weights(self) -> None:
        """Для каждой расы — насколько ей подходит каждая земля."""
        world = self.world
        for race in races_mod.RACES:
            pairs = []
            for region in world.regions.values():
                if region.terrain in race.terrains:
                    rank = race.terrains.index(region.terrain)
                    weight = 10.0 / (1.0 + rank)
                else:
                    weight = 0.35
                if region.from_map:
                    # Карта знает, каково там на самом деле: голые скалы
                    # и ледник — тоже «горы», но жить в них почти нельзя.
                    weight *= 0.35 + 1.3 * region.habitat
                    if race.category == races_mod.EVIL:
                        # Злым народам глушь и дурная слава только на руку.
                        weight *= 0.75 + 0.9 * region.savagery
                        if region.magic < 0:
                            weight *= 1.25
                pairs.append((region.id, weight))
            self.region_weights[race.id] = pairs

    def spread_knowledge(self) -> None:
        """Молва расходится по суше: сосед ведомой земли тоже становится ведом.

        За море молва не идёт — туда нужен корабль и тот, кто рискнёт.
        """
        world = self.world
        changed = True
        while changed:
            changed = False
            for region in world.regions.values():
                if not region.known:
                    continue
                for neighbor_id in region.neighbors:
                    neighbor = world.regions.get(neighbor_id)
                    if neighbor is not None and not neighbor.known:
                        neighbor.known = True
                        changed = True

    def pick_region(self, rng, race, near: str = "", spread: float = 0.0,
                    known_only: bool = True):
        """Выбирает землю для расы. near — желательная близость к этой земле.

        Селиться можно только там, куда уже дошли: заморская земля остаётся
        пустой, пока её не откроют мореплаватели. Исключение — пробуждение
        расы: народ появляется там, где появляется, и сам делает свою землю
        ведомой.
        """
        world = self.world
        pairs = self.region_weights.get(race.id) or []
        if known_only:
            pairs = [(region_id, weight) for region_id, weight in pairs
                     if world.regions[region_id].known]
        if not pairs:
            return None
        if near and rng.chance(1.0 - spread):
            home = world.regions.get(near)
            if home is not None:
                allowed = set(home.neighbors) | {home.id}
                near_pairs = [(rid, w) for rid, w in pairs if rid in allowed]
                if near_pairs:
                    pairs = near_pairs
        region_id = rng.weighted(pairs)
        return world.regions.get(region_id)

    # ------------------------------------------------------------------
    # Личности
    # ------------------------------------------------------------------

    def make_figure(self, rng, race, year: int, role: str, region_id: str = "",
                    title: str = "", sex: str = "", epithet_chance: float = 0.62,
                    home_id: str = "", house=None, given_name: str = "",
                    birth_year: int = 0, father=None, mother=None,
                    birth_order: int = 0, death_year: int = 0):
        """Создаёт историческую личность и заносит её в базу мира.

        Если передан знатный род, личность получает родовое имя (фамилию);
        у простолюдинов фамилии нет — так и задумано.
        """
        world = self.world
        if not sex:
            sex = "f" if rng.chance(0.45) else "m"

        low, high = race.lifespan
        lifespan = rng.randint(low, high)
        if not birth_year:
            # Возраст в момент деяния: зрелость, но ещё не закат.
            age = int(lifespan * rng.uniform(0.22, 0.48))
            birth_year = max(1, year - age)
        if not death_year:
            death_year = birth_year + lifespan
            if death_year <= year:
                death_year = year + rng.randint(1, max(2, lifespan // 8))
        death_year = max(death_year, birth_year + 1)

        given = given_name or self.forge.person(rng, race, sex)
        epithet = self.forge.epithet(rng, race, sex) if rng.chance(epithet_chance) else ""

        titles = [title] if title else []
        figure = world.add_figure(
            given_name=given, epithet=epithet, race_id=race.id, sex=sex,
            birth=Date.random_in_year(rng, birth_year),
            death=Date.random_in_year(rng, death_year),
            origin_region=region_id, titles=titles, roles=[role],
            home_id=home_id,
            surname=house.name if house is not None else "",
            house_id=house.id if house is not None else "",
            noble=house is not None,
            father_id=father.id if father is not None else "",
            mother_id=mother.id if mother is not None else "",
            birth_order=birth_order,
        )
        if father is not None:
            father.children.append(figure.id)
        if mother is not None:
            mother.children.append(figure.id)
        return figure

    def title_for(self, race, kind: str, sex: str) -> str:
        """Титул по роли: вождь племени, основатель города, правитель страны."""
        pairs = {
            "chief": race.chief_titles,
            "founder": race.founder_titles or race.chief_titles,
            "ruler": race.ruler_titles or race.founder_titles or race.chief_titles,
        }.get(kind, race.chief_titles)
        if not pairs:
            return "вождь" if sex == "m" else "вождица"
        return pairs[1] if (sex == "f" and len(pairs) > 1) else pairs[0]

    def ruler_title(self, polity, race, sex: str) -> str:
        """Титул правителя страны.

        Империей правит император, герцогством — герцог, а вот подгорным
        королевством — король-под-горой: тут слово за расой. Если страна
        сменила форму (королевство стало империей), титул меняется вместе
        с ней.
        """
        form = getattr(polity, "form", "") if polity is not None else ""
        return races_mod.title_for_form(form, sex, race.ruler_titles or
                                        race.founder_titles or race.chief_titles)

    # ------------------------------------------------------------------
    # Прочее
    # ------------------------------------------------------------------

    def date_in(self, rng, year: int, after: Date = None) -> Date:
        """Дата внутри года; при указании after — не раньше неё."""
        if after is None or after.year != year:
            return Date.random_in_year(rng, year)
        month = rng.randint(after.month, 12)
        day = rng.randint(after.day, 30) if month == after.month else rng.randint(1, 30)
        return Date(year, month, day)

    def note(self, key: str, value) -> None:
        self.world.notes[key] = value
