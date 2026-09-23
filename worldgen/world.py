# -*- coding: utf-8 -*-
"""Мир и его база данных.

World — единственное хранилище состояния. Все подсистемы генератора читают
и пишут только сюда, поэтому мир целиком сохраняется в файл и целиком
восстанавливается из него.
"""

from __future__ import annotations

import heapq

from . import artifacts as artifacts_mod
from . import history
from . import races as races_mod
from .models import (ACTIVE, ENDED, EXTINCT, FALLEN, GONE, ONGOING, RUINED,
                     Artifact, Battle, Bond, Cabal, Calamity, Camp, Codex,
                     Company,
                     Deity,
                     Discovery, Embassy, Event, Expedition, Fact, Faith, Feud,
                     Figure,
                     Folk, Fortress,
                     Guild, House, Law, League, Legend, Memory, Migration,
                     Monster, Pact,
                     Plot,
                     Polity,
                     Region,
                     Reign,
                     Relic, Seed, Settlement, Site, Strife, Tale, Temple,
                     Tongue,
                     TradeRoute,
                     Tribe,
                     Union, War)

# Поселение в летописи — это город и кормящая его округа. Чтобы потери от
# бедствий считались в людях, а не в условных единицах, население страны
# считается с этим множителем.
RURAL_FACTOR = 5.5

# Насколько тяжела именная обида и как она называется в летописи.
GRUDGE_WEIGHT = {"poison": 0.85, "envoy": 0.8, "spy": 0.45, "claim": 0.5,
                 "oath": 0.7, "murder": 0.9, "insult": 0.4}
GRUDGE_NOTE = {"poison": "яд, поднесённый при дворе",
               "envoy": "кровь посла", "spy": "пойманный соглядатай",
               "claim": "подложная грамота на престол",
               "oath": "нарушенная клятва", "murder": "кровь без ответа",
               "insult": "оскорбление"}
from .timeline import Date


class World:
    """Состояние мира и вся накопленная летопись."""

    def __init__(self, seed_text: str, seed_value: int, total_years: int, settings=None):
        self.seed_text = seed_text
        self.seed_value = seed_value
        self.total_years = total_years
        self.settings = settings

        self.eras = []                 # список EraSpan
        self.regions = {}              # id -> Region
        self.figures = {}              # id -> Figure
        self.tribes = {}               # id -> Tribe
        self.settlements = {}          # id -> Settlement
        self.polities = {}             # id -> Polity
        self.camps = {}                # id -> Camp
        self.houses = {}               # id -> House  (знатные роды)
        self.reigns = {}               # id -> Reign  (правления)
        self.calamities = {}           # id -> Calamity (бедствия)
        self.relics = {}               # id -> Relic (следы бедствий)
        self.battles = {}              # id -> Battle (сражения)
        self.dark_ages = []            # тёмные века: последствия бедствий
        self.deities = {}              # id -> Deity (боги)
        self.faiths = {}               # id -> Faith (веры)
        self.temples = {}              # id -> Temple (храмы и святилища)
        self.events = []               # список Event в хронологическом порядке

        # Быстрые списки активных сущностей (поддерживаются в актуальном виде).
        self.active_tribes = []
        self.active_settlements = []
        self.active_polities = []
        self.active_camps = []
        self.active_houses = []
        self.active_calamities = []
        self.sleeping_relics = []
        self.living_faiths = []

        # Служебное
        self._counters = {}
        self._death_queue = []         # куча (год смерти, порядок, id личности)
        self._death_order = 0
        self.race_awakening = {}       # race_id -> год пробуждения
        self.expeditions = {}
        self.active_expeditions = []
        self.tales = {}                # сказания: местные героические истории
        self.folks = {}
        self.routes = {}
        self.active_routes = []
        self.wars = {}
        self.active_wars = []
        self.feuds = {}
        self.pacts = {}
        self.active_pacts = []
        self.tongues = {}
        self.living_tongues = []
        self.embassies = {}
        self.unions = {}
        self.plots = {}
        self.guilds = {}
        self.active_guilds = []
        self.artifacts = {}
        self.sites = {}
        self.monsters = {}
        self.living_monsters = []
        self.discoveries = {}
        self.codices = {}
        self.laws = {}
        self.active_codices = []
        self.legends = {}
        self.active_unions = []
        self.fortresses = {}
        self.active_fortresses = []
        self.companies = {}
        self.active_companies = []
        self.leagues = {}
        self.active_leagues = []
        # --- причинность (блок 15) ---
        # След каждого крупного события и зёрна будущих событий. По ним
        # летопись умеет отвечать на вопрос «почему так вышло».
        self.facts = {}                # id -> Fact
        self.seeds = {}                # id -> Seed
        self.open_facts = []           # живые следы
        self.waiting_seeds = []        # зёрна, ждущие своего года
        self._facts_by_holder = {}     # кто помнит -> [id следов]
        # --- память людей и связи между ними (блок 16) ---
        self.memories = {}             # id -> Memory
        self.bonds = {}                # id -> Bond
        self._memory_of = {}           # личность -> [id воспоминаний]
        self._bonds_of = {}            # личность -> [id связей]
        self.migrations = {}           # id -> Migration (переселения народов)
        # --- смуты и заговоры (блоки 20 и 21) ---
        self.strifes = {}              # id -> Strife
        self.active_strifes = []       # смуты, которые идут прямо сейчас
        self.cabals = {}               # id -> Cabal
        self.live_cabals = []          # заговоры, ещё не кончившиеся
        self._events_by_id = {}        # id -> Event (для дерева причин)
        self.notes = {}                # свободные заметки для будущих блоков
        # Перепись мира раз в несколько лет: по ней видно, как мир рос,
        # когда он проваливался и какой век стоил ему дороже всего.
        self.census = []               # [{year, souls, tribes, towns, ...}]
        self.map_source = ""           # файл карты, если мир построен по ней
        self.geography = {}            # имена океанов, материков, хребтов
        self.map_link = None           # связь с картой: чтобы освобождать гексы
        self.map_recorder = None       # политическая карта по годам (не сохраняется)

    # ------------------------------------------------------------------
    # Идентификаторы
    # ------------------------------------------------------------------

    def next_id(self, prefix: str) -> str:
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return "%s%d" % (prefix, value)

    # ------------------------------------------------------------------
    # Добавление сущностей
    # ------------------------------------------------------------------

    def add_region(self, **kwargs) -> Region:
        region = Region(id=self.next_id("R"), **kwargs)
        self.regions[region.id] = region
        return region

    def add_figure(self, **kwargs) -> Figure:
        figure = Figure(id=self.next_id("F"), **kwargs)
        self.figures[figure.id] = figure
        self._queue_death(figure)
        if figure.house_id:
            house = self.houses.get(figure.house_id)
            if house is not None:
                house.members.append(figure.id)
                house.living.append(figure.id)
                house.alive_count = len(house.living)
        return figure

    def _queue_death(self, figure) -> None:
        if figure.death is None:
            return
        self._death_order += 1
        heapq.heappush(self._death_queue,
                       (figure.death.ordinal, self._death_order, figure.id))

    def schedule_death(self, figure, date: Date, cause: str = "") -> None:
        """Переносит дату смерти (убийство, казнь, гибель) и обновляет очередь."""
        figure.death = date
        if cause:
            figure.death_cause = cause
        self._queue_death(figure)

    def add_house(self, **kwargs) -> House:
        house = House(id=self.next_id("H"), **kwargs)
        self.houses[house.id] = house
        self.active_houses.append(house.id)
        return house

    def add_deity(self, **kwargs) -> Deity:
        deity = Deity(id=self.next_id("Y"), **kwargs)
        self.deities[deity.id] = deity
        return deity

    def add_faith(self, **kwargs) -> Faith:
        faith = Faith(id=self.next_id("W"), **kwargs)
        self.faiths[faith.id] = faith
        self.living_faiths.append(faith.id)
        return faith

    def add_temple(self, **kwargs) -> Temple:
        temple = Temple(id=self.next_id("M"), **kwargs)
        self.temples[temple.id] = temple
        faith = self.faiths.get(temple.faith_id)
        if faith is not None:
            faith.temple_ids.append(temple.id)
        return temple

    def end_faith(self, faith, date: Date, reason: str, status: str) -> None:
        if faith.id not in self.living_faiths:
            return
        faith.status = status
        faith.ended = date
        faith.end_reason = reason
        self.living_faiths.remove(faith.id)
        for deity_id in faith.deity_ids:
            deity = self.deities.get(deity_id)
            if deity is not None:
                deity.status = "забыт"

    def end_temple(self, temple, date: Date, reason: str,
                   status: str = "в руинах") -> None:
        if temple.status != "действует":
            return
        temple.status = status
        temple.ended = date
        temple.end_reason = reason

    def add_calamity(self, **kwargs) -> Calamity:
        calamity = Calamity(id=self.next_id("D"), **kwargs)
        self.calamities[calamity.id] = calamity
        self.active_calamities.append(calamity.id)
        return calamity

    def add_route(self, **kwargs) -> TradeRoute:
        route = TradeRoute(id=self.next_id("T"), **kwargs)
        self.routes[route.id] = route
        self.active_routes.append(route.id)
        return route

    def close_route(self, route, date: Date, reason: str) -> None:
        if route.status != ACTIVE:
            return
        route.status = ENDED
        route.closed = date
        route.end_reason = reason
        if route.id in self.active_routes:
            self.active_routes.remove(route.id)
        for polity_id in (route.seller_id, route.buyer_id):
            polity = self.polities.get(polity_id)
            if polity is not None and route.id in polity.routes:
                polity.routes.remove(route.id)

    def add_folk(self, **kwargs) -> Folk:
        folk = Folk(id=self.next_id("N"), **kwargs)
        self.folks[folk.id] = folk
        return folk

    def refresh_folks(self) -> None:
        """Пересчитывает, сколько за каким народом душ, городов и стран."""
        for folk in self.folks.values():
            folk.population = folk.settlements = folk.tribes = folk.polities = 0
        for settlement_id in self.active_settlements:
            settlement = self.settlements[settlement_id]
            folk = self.folks.get(settlement.folk_id)
            if folk is None:
                continue
            folk.population += self.settlement_realm(settlement)
            folk.settlements += 1
        for tribe_id in self.active_tribes:
            tribe = self.tribes[tribe_id]
            folk = self.folks.get(tribe.folk_id)
            if folk is None:
                continue
            folk.population += tribe.population
            folk.tribes += 1
        for polity_id in self.active_polities:
            polity = self.polities[polity_id]
            capital = self.settlements.get(polity.capital_id)
            folk = self.folks.get(capital.folk_id) if capital is not None else None
            if folk is not None:
                folk.polities += 1

    def end_folk(self, folk, date: Date, reason: str, status: str = GONE) -> None:
        """Народ кончился: последних его людей не стало.

        Назад народы не возвращаются — новые рождаются только при
        пробуждении расы, а раса просыпается один раз.
        """
        if folk.status != ACTIVE:
            return
        folk.status = status
        folk.ended = date
        folk.notes.append(reason)
        folk.population = folk.settlements = folk.tribes = folk.polities = 0

    def folks_of_race(self, race_id: str) -> list:
        return [folk for folk in self.folks.values() if folk.race_id == race_id]

    def add_expedition(self, **kwargs) -> "Expedition":
        expedition = Expedition(id=self.next_id("X"), **kwargs)
        self.expeditions[expedition.id] = expedition
        self.active_expeditions.append(expedition.id)
        return expedition

    def end_expedition(self, expedition, date: Date, outcome: str) -> None:
        expedition.end = date
        expedition.outcome = outcome
        if expedition.id in self.active_expeditions:
            self.active_expeditions.remove(expedition.id)

    def discover_region(self, region, year: int, figure_id: str = "",
                        race_id: str = "") -> bool:
        """Отмечает землю ведомой. Возвращает True, если она была неведома."""
        if region is None or region.known:
            return False
        region.known = True
        region.discovered_year = int(year)
        if figure_id:
            region.discovered_by_id = figure_id
        if race_id and not region.discovered_by:
            region.discovered_by = race_id
        return True

    def known_regions(self) -> list:
        return [region for region in self.regions.values() if region.known]

    def add_relic(self, **kwargs) -> Relic:
        relic = Relic(id=self.next_id("L"), **kwargs)
        self.relics[relic.id] = relic
        if relic.status == "спит":
            self.sleeping_relics.append(relic.id)
        return relic

    def add_battle(self, **kwargs) -> Battle:
        battle = Battle(id=self.next_id("B"), **kwargs)
        self.battles[battle.id] = battle
        calamity = self.calamities.get(battle.calamity_id)
        if calamity is not None:
            calamity.battle_ids.append(battle.id)
        war = self.wars.get(battle.war_id)
        if war is not None:
            war.battle_ids.append(battle.id)
        return battle

    # --- войны ---------------------------------------------------------

    def add_war(self, **kwargs) -> War:
        war = War(id=self.next_id("W"), **kwargs)
        self.wars[war.id] = war
        self.active_wars.append(war.id)
        for polity_id in (war.attacker_id, war.defender_id):
            polity = self.polities.get(polity_id)
            if polity is not None and war.id not in polity.war_ids:
                polity.war_ids.append(war.id)
        return war

    def end_war(self, war, date: Date, outcome: str, peace_name: str = "") -> None:
        if war.status != ONGOING:
            return
        war.status = ENDED
        war.end = date
        war.outcome = outcome
        war.peace_name = peace_name
        if war.id in self.active_wars:
            self.active_wars.remove(war.id)
        feud = self.feuds.get(war.feud_id)
        if feud is not None:
            feud.end = date
            feud.deaths += war.deaths

    # --- языки ----------------------------------------------------------

    def add_tongue(self, **kwargs) -> Tongue:
        tongue = Tongue(id=self.next_id("Y"), **kwargs)
        self.tongues[tongue.id] = tongue
        if tongue.status != "мёртвый":
            self.living_tongues.append(tongue.id)
        return tongue

    def end_tongue(self, tongue, date: Date, reason: str,
                   status: str = "мёртвый") -> None:
        # Священный язык тоже перестаёт быть живым: дома на нём уже
        # не говорят, он остаётся только в храме.
        if tongue.status != "живой":
            return
        tongue.status = status
        tongue.end_reason = reason
        tongue.ended = date
        if tongue.id in self.living_tongues:
            self.living_tongues.remove(tongue.id)

    def tongue_of(self, folk):
        if folk is None:
            return None
        return self.tongues.get(folk.tongue_id)

    # --- посольства и обиды ---------------------------------------------

    def add_embassy(self, **kwargs):
        embassy = Embassy(id=self.next_id("E"), **kwargs)
        self.embassies[embassy.id] = embassy
        return embassy

    def embassies_of(self, polity) -> list:
        return [item for item in self.embassies.values()
                if polity.id in (item.sender_id, item.host_id)]

    def add_grudge(self, polity, other_id: str, key: str, year: int) -> None:
        """Держава запоминает обиду: кровь посла, яд, пойманного соглядатая.

        Обида живёт не вечно, но живёт дольше того, кто её нанёс: списком
        обид пользуется ``warfare.reasons``, когда ищет повод к войне.
        """
        if not other_id or polity is None:
            return
        polity.grudges.setdefault(other_id, {})[key] = int(year)
        # Та же обида ложится и в общий счёт держав: оттуда её читают
        # отношения, выбор жертвы и отложенные последствия.
        history.leave(self, history.GRUDGE, year, polity.id, other_id,
                      weight=GRUDGE_WEIGHT.get(key, 0.5),
                      note=GRUDGE_NOTE.get(key, key))

    # --- вещи и места ----------------------------------------------------

    def add_artifact(self, **kwargs) -> Artifact:
        artifact = Artifact(id=self.next_id("A"), **kwargs)
        self.artifacts[artifact.id] = artifact
        return artifact

    def add_site(self, **kwargs) -> Site:
        site = Site(id=self.next_id("Z"), **kwargs)
        self.sites[site.id] = site
        return site

    def add_law(self, **kwargs) -> Law:
        law = Law(id=self.next_id("X"), **kwargs)
        self.laws[law.id] = law
        return law

    def law_of(self, key: str):
        for item in self.laws.values():
            if item.key == key:
                return item
        return None

    def add_codex(self, **kwargs) -> Codex:
        codex = Codex(id=self.next_id("L"), **kwargs)
        self.codices[codex.id] = codex
        self.active_codices.append(codex.id)
        return codex

    def close_codex(self, codex, date: Date, status: str) -> None:
        if codex.id in self.active_codices:
            self.active_codices.remove(codex.id)
        codex.status = status
        codex.ended = date

    def add_legend(self, **kwargs) -> Legend:
        legend = Legend(id=self.next_id("J"), **kwargs)
        self.legends[legend.id] = legend
        return legend

    def add_discovery(self, **kwargs) -> Discovery:
        discovery = Discovery(id=self.next_id("O"), **kwargs)
        self.discoveries[discovery.id] = discovery
        return discovery

    def discovery_of(self, key: str):
        for item in self.discoveries.values():
            if item.key == key:
                return item
        return None

    def add_monster(self, **kwargs) -> Monster:
        monster = Monster(id=self.next_id("B"), **kwargs)
        self.monsters[monster.id] = monster
        self.living_monsters.append(monster.id)
        return monster

    def end_monster(self, monster, date: Date, status: str,
                    slayer=None) -> None:
        if monster.id not in self.living_monsters:
            return
        monster.status = status
        monster.ended = date
        monster.slayer_id = slayer.id if slayer is not None else ""
        self.living_monsters.remove(monster.id)

    def artifacts_of(self, figure) -> list:
        return [item for item in self.artifacts.values()
                if item.owner_id == figure.id and item.where == "у владельца"]

    def put_artifact(self, artifact, where: str, date: Date = None,
                     figure=None, polity=None, site=None, how: str = "") -> None:
        """Перекладывает вещь в новые руки или в новое место — и помнит это.

        Всякая перемена записывается в цепочку: год, чьи руки (или чьё
        место) и как вещь туда попала. Из этой цепочки потом и строится
        рассказ о ней — и подземелье, в котором она лежит.
        """
        artifact.where = where
        artifact.owner_id = figure.id if figure is not None else ""
        artifact.polity_id = polity.id if polity is not None else (
            artifact.polity_id if where in ("в сокровищнице державы",) else "")
        artifact.site_id = site.id if site is not None else ""
        if site is not None:
            artifact.region_id = site.region_id
            if artifact.id not in site.artifact_ids:
                site.artifact_ids.append(artifact.id)
        elif figure is not None and figure.origin_region:
            artifact.region_id = figure.origin_region
        if where == "потерян":
            artifact.lost = date
        who = ""
        if figure is not None:
            who = figure.name
        elif site is not None:
            who = site.name
        elif polity is not None:
            who = polity.full_name
        else:
            # Ни рук, ни места: пусть в цепочке останется хотя бы земля,
            # где вещь видели в последний раз.
            region = self.regions.get(artifact.region_id)
            who = "земля по имени %s" % region.name if region is not None else "—"
        artifact.trail.append({
            "year": date.year if date is not None else 0,
            "who": who, "where": where, "how": how,
        })
        artifact.fame = artifacts_mod.fame_of(artifact)

    # --- гильдии ---------------------------------------------------------

    def add_guild(self, **kwargs) -> Guild:
        guild = Guild(id=self.next_id("G"), **kwargs)
        self.guilds[guild.id] = guild
        self.active_guilds.append(guild.id)
        return guild

    def end_guild(self, guild, date: Date, reason: str) -> None:
        if guild.status != ACTIVE:
            return
        guild.status = ENDED
        guild.ended = date
        guild.end_reason = reason
        if guild.id in self.active_guilds:
            self.active_guilds.remove(guild.id)

    def guilds_of(self, polity) -> list:
        return [self.guilds[gid] for gid in self.active_guilds
                if self.guilds[gid].polity_id == polity.id]

    # --- тайные дела -----------------------------------------------------

    def add_plot(self, **kwargs) -> Plot:
        plot = Plot(id=self.next_id("Q"), **kwargs)
        self.plots[plot.id] = plot
        return plot

    def plots_of(self, polity) -> list:
        return [item for item in self.plots.values()
                if polity.id in (item.sender_id, item.target_id)]

    # --- династические унии ---------------------------------------------

    def add_union(self, **kwargs) -> Union:
        union = Union(id=self.next_id("N"), **kwargs)
        self.unions[union.id] = union
        self.active_unions.append(union.id)
        for polity_id in (union.first_id, union.second_id):
            polity = self.polities.get(polity_id)
            if polity is not None:
                polity.union_id = union.id
        return union

    def end_union(self, union, date: Date, reason: str,
                  merged: bool = False) -> None:
        if union.status != ACTIVE:
            return
        union.status = ENDED
        union.ended = date
        union.end_reason = reason
        union.merged = merged
        if union.id in self.active_unions:
            self.active_unions.remove(union.id)
        for polity_id in (union.first_id, union.second_id):
            polity = self.polities.get(polity_id)
            if polity is not None and polity.union_id == union.id:
                polity.union_id = ""

    def union_between(self, first_id: str, second_id: str):
        for union_id in self.active_unions:
            union = self.unions[union_id]
            if {union.first_id, union.second_id} == {first_id, second_id}:
                return union
        return None

    # --- крепости и вольные роты ----------------------------------------

    def add_fortress(self, **kwargs) -> Fortress:
        fortress = Fortress(id=self.next_id("K"), **kwargs)
        self.fortresses[fortress.id] = fortress
        self.active_fortresses.append(fortress.id)
        if fortress.polity_id:
            fortress.holders.append([fortress.built.year, fortress.polity_id])
        return fortress

    def end_fortress(self, fortress, date: Date, reason: str,
                     status: str = "разрушено") -> None:
        if fortress.status != ACTIVE:
            return
        fortress.status = status
        fortress.ended = date
        fortress.end_reason = reason
        if fortress.id in self.active_fortresses:
            self.active_fortresses.remove(fortress.id)

    def fortresses_of(self, polity) -> list:
        return [self.fortresses[fid] for fid in self.active_fortresses
                if self.fortresses[fid].polity_id == polity.id]

    def add_company(self, **kwargs) -> Company:
        company = Company(id=self.next_id("C"), **kwargs)
        self.companies[company.id] = company
        self.active_companies.append(company.id)
        return company

    def end_company(self, company, date: Date, reason: str) -> None:
        if company.status != ACTIVE:
            return
        company.status = ENDED
        company.ended = date
        company.end_reason = reason
        if company.id in self.active_companies:
            self.active_companies.remove(company.id)

    # --- политика -------------------------------------------------------

    def add_pact(self, **kwargs) -> Pact:
        pact = Pact(id=self.next_id("P"), **kwargs)
        self.pacts[pact.id] = pact
        self.active_pacts.append(pact.id)
        for polity_id in (pact.first_id, pact.second_id):
            polity = self.polities.get(polity_id)
            if polity is not None and pact.id not in polity.pact_ids:
                polity.pact_ids.append(pact.id)
        return pact

    def end_pact(self, pact, date: Date, reason: str) -> None:
        if pact.status != ACTIVE:
            return
        pact.status = ENDED
        pact.ended = date
        pact.end_reason = reason
        if pact.id in self.active_pacts:
            self.active_pacts.remove(pact.id)

    def pacts_of(self, polity, only_active: bool = True) -> list:
        rows = []
        for pact_id in polity.pact_ids:
            pact = self.pacts.get(pact_id)
            if pact is None or (only_active and pact.status != ACTIVE):
                continue
            rows.append(pact)
        return rows

    def pact_between(self, first_id: str, second_id: str):
        pair = {first_id, second_id}
        for pact_id in self.active_pacts:
            pact = self.pacts[pact_id]
            if {pact.first_id, pact.second_id} == pair:
                return pact
        return None

    def add_league(self, **kwargs) -> League:
        league = League(id=self.next_id("U"), **kwargs)
        self.leagues[league.id] = league
        self.active_leagues.append(league.id)
        for polity_id in league.member_ids:
            polity = self.polities.get(polity_id)
            if polity is not None:
                polity.league_id = league.id
        return league

    def end_league(self, league, date: Date, reason: str) -> None:
        if league.status != ACTIVE:
            return
        league.status = ENDED
        league.ended = date
        league.end_reason = reason
        if league.id in self.active_leagues:
            self.active_leagues.remove(league.id)
        for polity_id in league.member_ids:
            polity = self.polities.get(polity_id)
            if polity is not None and polity.league_id == league.id:
                polity.league_id = ""

    def add_feud(self, **kwargs) -> Feud:
        feud = Feud(id=self.next_id("F"), **kwargs)
        self.feuds[feud.id] = feud
        return feud

    def wars_of(self, polity, only_active: bool = False) -> list:
        rows = []
        for war_id in polity.war_ids:
            war = self.wars.get(war_id)
            if war is None:
                continue
            if only_active and war.status != ONGOING:
                continue
            rows.append(war)
        return rows

    def war_between(self, first_id: str, second_id: str):
        """Идущая война между этой парой, если она есть."""
        pair = {first_id, second_id}
        for war_id in self.active_wars:
            war = self.wars[war_id]
            if {war.attacker_id, war.defender_id} == pair:
                return war
        return None

    def end_calamity(self, calamity, date: Date, resolution: str) -> None:
        if calamity.status != ONGOING:
            return
        calamity.status = ENDED
        calamity.end = date
        calamity.resolution = resolution
        if calamity.id in self.active_calamities:
            self.active_calamities.remove(calamity.id)

    def wake_relic(self, relic, date: Date) -> None:
        relic.status = "потревожен"
        relic.awakened = date
        if relic.id in self.sleeping_relics:
            self.sleeping_relics.remove(relic.id)

    def add_reign(self, **kwargs) -> Reign:
        reign = Reign(id=self.next_id("G"), **kwargs)
        self.reigns[reign.id] = reign
        polity = self.polities.get(reign.polity_id)
        if polity is not None:
            polity.reign_ids.append(reign.id)
        return reign

    def add_tribe(self, **kwargs) -> Tribe:
        tribe = Tribe(id=self.next_id("T"), **kwargs)
        self.tribes[tribe.id] = tribe
        self.active_tribes.append(tribe.id)
        return tribe

    def add_settlement(self, **kwargs) -> Settlement:
        settlement = Settlement(id=self.next_id("C"), **kwargs)
        self.settlements[settlement.id] = settlement
        self.active_settlements.append(settlement.id)
        return settlement

    def add_polity(self, **kwargs) -> Polity:
        polity = Polity(id=self.next_id("P"), **kwargs)
        self.polities[polity.id] = polity
        self.active_polities.append(polity.id)
        return polity

    def add_camp(self, **kwargs) -> Camp:
        camp = Camp(id=self.next_id("K"), **kwargs)
        self.camps[camp.id] = camp
        self.active_camps.append(camp.id)
        return camp

    def add_event(self, date: Date, era_index: int, kind: str, title: str,
                  text: str, importance: int = 2, actors=None, subjects=None,
                  region_id: str = "", race_id: str = "",
                  causes=None, facts=None, motives=None,
                  trace: float = 0.0) -> Event:
        # Причина не может случиться позже следствия. Внутри одного года
        # дни выпадают случайно, и ссылка на «причину», датированную
        # позднее, — не связь, а ошибка; такие отбрасываем молча.
        roots = []
        for event_id in (causes or ()):
            if not event_id:
                continue
            earlier = self._events_by_id.get(event_id)
            if earlier is not None and earlier.date.ordinal > date.ordinal:
                continue
            roots.append(event_id)
        event = Event(
            id=self.next_id("V"), date=date, era_index=era_index, kind=kind,
            title=title, text=text, importance=importance,
            actors=list(actors or ()), subjects=list(subjects or ()),
            region_id=region_id, race_id=race_id,
            causes=roots,
            facts=[item for item in (facts or ()) if item],
            motives=dict(motives or {}),
            trace=float(trace),
        )
        self.events.append(event)
        self._events_by_id[event.id] = event
        for actor_id in event.actors:
            figure = self.figures.get(actor_id)
            if figure is not None:
                figure.deeds.append(event.id)
        # Раз повод пригодился — отмечаем, что след сработал: по этим
        # отметкам видно, какие следы двигали историю, а какие пролежали зря.
        for fact_id in event.facts:
            fact = self.facts.get(fact_id)
            if fact is not None:
                fact.uses += 1
                fact.last_use = date.year
        return event

    def event(self, event_id: str):
        """Событие по номеру — без перебора всей летописи."""
        found = self._events_by_id.get(event_id)
        if found is not None:
            return found
        for item in self.events:          # мир, поднятый из файла
            self._events_by_id[item.id] = item
        return self._events_by_id.get(event_id)

    # ------------------------------------------------------------------
    # Следы событий и отложенные последствия (блок 15)
    # ------------------------------------------------------------------

    def add_fact(self, kind: str, year: int, **kwargs) -> Fact:
        fact = Fact(id=self.next_id("FA"), kind=kind, year=int(year), **kwargs)
        self.facts[fact.id] = fact
        self.open_facts.append(fact)
        self._facts_by_holder.setdefault(fact.holder_id, []).append(fact.id)
        event = self._events_by_id.get(fact.event_id)
        if event is not None and fact.id not in event.marks:
            event.marks.append(fact.id)
        return fact

    def close_fact(self, fact, year: int, reason: str = "") -> None:
        if fact is None or fact.closed:
            return
        fact.closed = int(year)
        fact.close_reason = reason
        if fact in self.open_facts:
            self.open_facts.remove(fact)

    def live_facts(self, holder_id: str):
        """Живые следы держателя без сортировки — для частых подсчётов."""
        for fact_id in self._facts_by_holder.get(holder_id, ()):
            fact = self.facts.get(fact_id)
            if fact is not None and not fact.closed:
                yield fact

    def facts_of(self, holder_id: str, year: int = 0, kind: str = "",
                 about_id: str = "", least: float = 0.0) -> list:
        """Живые следы этого держателя, от сильного к слабому."""
        rows = []
        for fact_id in self._facts_by_holder.get(holder_id, ()):
            fact = self.facts.get(fact_id)
            if fact is None or fact.closed:
                continue
            if kind and fact.kind != kind:
                continue
            if about_id and fact.about_id != about_id:
                continue
            power = fact.power(year) if year else fact.weight
            if power <= least:
                continue
            rows.append((power, fact))
        rows.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [fact for _, fact in rows]

    def fact_power(self, holder_id: str, kind: str, year: int,
                   about_id: str = "") -> float:
        """Сколько всего силы в следах одного разбора."""
        total = 0.0
        for fact in self.facts_of(holder_id, year, kind, about_id):
            total += fact.power(year)
        return total

    def rebuild_fact_index(self) -> None:
        """После загрузки из файла — восстановить быстрые списки."""
        self.open_facts = []
        self._facts_by_holder = {}
        for fact in self.facts.values():
            self._facts_by_holder.setdefault(fact.holder_id, []).append(fact.id)
            if not fact.closed:
                self.open_facts.append(fact)
        self.waiting_seeds = [seed for seed in self.seeds.values()
                              if seed.state == "ждёт"]
        self._events_by_id = {item.id: item for item in self.events}

    # ------------------------------------------------------------------
    # Память людей и связи между ними (блок 16)
    # ------------------------------------------------------------------

    def add_tale(self, **kwargs) -> Tale:
        tale = Tale(id=self.next_id("SG"), **kwargs)
        self.tales[tale.id] = tale
        return tale

    def add_memory(self, figure_id: str, kind: str, year: int, **kwargs) -> Memory:
        item = Memory(id=self.next_id("ME"), figure_id=figure_id, kind=kind,
                      year=int(year), **kwargs)
        self.memories[item.id] = item
        self._memory_of.setdefault(figure_id, []).append(item.id)
        return item

    def memories_of(self, figure_id: str, kind: str = "",
                    about_id: str = "") -> list:
        rows = []
        for memory_id in self._memory_of.get(figure_id, ()):
            memory = self.memories.get(memory_id)
            if memory is None:
                continue
            if kind and memory.kind != kind:
                continue
            if about_id and memory.about_id != about_id:
                continue
            rows.append(memory)
        rows.sort(key=lambda item: (-item.weight, item.id))
        return rows

    def add_bond(self, a_id: str, b_id: str, kind: str, year: int,
                 **kwargs) -> Bond:
        bond = Bond(id=self.next_id("BN"), a_id=a_id, b_id=b_id, kind=kind,
                    since=int(year), changed=int(year), **kwargs)
        self.bonds[bond.id] = bond
        self._bonds_of.setdefault(a_id, []).append(bond.id)
        self._bonds_of.setdefault(b_id, []).append(bond.id)
        return bond

    def bonds_of(self, figure_id: str, kind: str = "", alive: bool = True) -> list:
        rows = []
        for bond_id in self._bonds_of.get(figure_id, ()):
            bond = self.bonds.get(bond_id)
            if bond is None:
                continue
            if alive and bond.ended:
                continue
            if kind and bond.kind != kind:
                continue
            rows.append(bond)
        rows.sort(key=lambda item: (-abs(item.value), item.id))
        return rows

    def bond_between(self, first_id: str, second_id: str, alive: bool = True):
        for bond in self.bonds_of(first_id, alive=alive):
            if bond.other(first_id) == second_id:
                return bond
        return None

    # ------------------------------------------------------------------
    # Смуты и заговоры
    # ------------------------------------------------------------------

    def add_strife(self, **kwargs) -> Strife:
        strife = Strife(id=self.next_id("SF"), **kwargs)
        self.strifes[strife.id] = strife
        self.active_strifes.append(strife.id)
        return strife

    def end_strife(self, strife, date: Date, outcome: str) -> None:
        if strife.status != ONGOING:
            return
        strife.status = ENDED
        strife.end = date
        strife.outcome = outcome
        if strife.id in self.active_strifes:
            self.active_strifes.remove(strife.id)

    def strife_of(self, polity):
        """Идущая смута этой державы, если она есть."""
        for strife_id in self.active_strifes:
            strife = self.strifes.get(strife_id)
            if strife is not None and strife.polity_id == polity.id:
                return strife
        return None

    def add_cabal(self, **kwargs) -> Cabal:
        cabal = Cabal(id=self.next_id("CB"), **kwargs)
        self.cabals[cabal.id] = cabal
        self.live_cabals.append(cabal.id)
        return cabal

    def end_cabal(self, cabal, year: int, outcome: str) -> None:
        if cabal.outcome:
            return
        cabal.outcome = outcome
        cabal.ended = int(year)
        if cabal.id in self.live_cabals:
            self.live_cabals.remove(cabal.id)

    def cabal_of(self, polity):
        """Заговор, зреющий в этой державе."""
        for cabal_id in self.live_cabals:
            cabal = self.cabals.get(cabal_id)
            if cabal is not None and cabal.polity_id == polity.id:
                return cabal
        return None

    def add_migration(self, year: int, race_id: str, **kwargs) -> Migration:
        item = Migration(id=self.next_id("MG"), year=int(year),
                         race_id=race_id, **kwargs)
        self.migrations[item.id] = item
        return item

    def rebuild_people_index(self) -> None:
        """После загрузки из файла — восстановить память и связи."""
        self._memory_of = {}
        self._bonds_of = {}
        for memory in self.memories.values():
            self._memory_of.setdefault(memory.figure_id, []).append(memory.id)
        for bond in self.bonds.values():
            self._bonds_of.setdefault(bond.a_id, []).append(bond.id)
            self._bonds_of.setdefault(bond.b_id, []).append(bond.id)

    def add_seed(self, kind: str, due: int, born: int, **kwargs) -> Seed:
        seed = Seed(id=self.next_id("SD"), kind=kind, due=int(due),
                    born=int(born), **kwargs)
        self.seeds[seed.id] = seed
        self.waiting_seeds.append(seed)
        event = self._events_by_id.get(seed.event_id)
        if event is not None and seed.id not in event.seeds:
            event.seeds.append(seed.id)
        return seed

    def settle_seed(self, seed, year: int, state: str, result_id: str = "") -> None:
        if seed is None or seed.state != "ждёт":
            return
        seed.state = state
        seed.settled = int(year)
        seed.result_id = result_id
        if seed in self.waiting_seeds:
            self.waiting_seeds.remove(seed)

    # ------------------------------------------------------------------
    # Смерти по расписанию
    # ------------------------------------------------------------------

    def due_deaths(self, year: int) -> list:
        """Личности, чей срок вышел к концу указанного года.

        Запись могла устареть: если персонажа убили раньше срока, в очереди
        осталась его прежняя дата. Такие записи отбрасываются.
        """
        limit = year * 360
        result = []
        while self._death_queue and self._death_queue[0][0] < limit:
            ordinal, _, figure_id = heapq.heappop(self._death_queue)
            figure = self.figures[figure_id]
            if figure.death is not None and figure.death.ordinal == ordinal:
                result.append(figure)
        return result

    # ------------------------------------------------------------------
    # Изменение состояния
    # ------------------------------------------------------------------

    def end_tribe(self, tribe, date: Date, reason: str, status: str = GONE) -> None:
        if tribe.status not in (ACTIVE,):
            return
        tribe.status = status
        tribe.ended = date
        tribe.end_reason = reason
        if tribe.id in self.active_tribes:
            self.active_tribes.remove(tribe.id)
        if self.map_link is not None:
            self.map_link.release(tribe.id)

    def end_settlement(self, settlement, date: Date, reason: str,
                       status: str = RUINED) -> None:
        if settlement.status != ACTIVE:
            return
        settlement.status = status
        settlement.ended = date
        settlement.end_reason = reason
        if settlement.id in self.active_settlements:
            self.active_settlements.remove(settlement.id)
        if self.map_link is not None:
            self.map_link.release(settlement.id)
        polity = self.polities.get(settlement.polity_id)
        if polity is not None and settlement.id in polity.settlement_ids:
            polity.settlement_ids.remove(settlement.id)
        if polity is not None and polity.capital_id == settlement.id:
            self.ensure_capital(polity, date)

    def ensure_capital(self, polity, date: Date) -> bool:
        """Престол должен быть живым городом этой самой державы.

        Город пал, откололся в вольную республику, отошёл победителю или
        ушёл с мятежным домом — во всех этих случаях корона оставалась
        при нём, и держава числилась со столицей, которой у неё нет.
        Теперь корону переносят в крупнейший из уцелевших своих городов.
        """
        seat = self.settlements.get(polity.capital_id)
        if seat is not None and seat.status == ACTIVE \
                and seat.id in polity.settlement_ids:
            seat.is_capital = True
            return False
        lost = seat.name if seat is not None else ""
        if seat is not None:
            seat.is_capital = False

        best, best_souls = None, -1
        for settlement_id in polity.settlement_ids:
            settlement = self.settlements.get(settlement_id)
            if settlement is None or settlement.status != ACTIVE:
                continue
            if settlement.population > best_souls:
                best, best_souls = settlement, settlement.population
        if best is None:
            polity.capital_id = ""
            return False
        best.is_capital = True
        polity.capital_id = best.id
        if lost:
            polity.capital_moved = date.year
            polity.capital_lost = lost
        return True

    def end_polity(self, polity, date: Date, reason: str, status: str = FALLEN) -> None:
        if polity.status != ACTIVE:
            return
        reign = self.current_reign(polity)
        if reign is not None and reign.end is None:
            reign.end = date
            reign.end_reason = "гибель страны"
            # Правление, при котором держава кончилась, историей не
            # оправдывается — чем бы ни была вызвана гибель.
            reign.closing = {"population": 0, "cities": 0, "regions": 0,
                             "fallen": True}
            reign.verdict = "гибельное"
            reign.score = 0.0
        house = self.houses.get(polity.house_id)
        if house is not None and house.rank == "правящий":
            house.rank = "великий"
            house.rung = -1
            house.style = ""
        polity.status = status
        polity.ended = date
        polity.end_reason = reason
        if polity.id in self.active_polities:
            self.active_polities.remove(polity.id)
        for settlement_id in list(polity.settlement_ids):
            settlement = self.settlements.get(settlement_id)
            if settlement is not None and settlement.status == ACTIVE:
                settlement.polity_id = ""
                settlement.is_capital = False

    def end_camp(self, camp, date: Date, reason: str, status: str = GONE) -> None:
        if camp.status != ACTIVE:
            return
        camp.status = status
        camp.ended = date
        camp.end_reason = reason
        if camp.id in self.active_camps:
            self.active_camps.remove(camp.id)
        if self.map_link is not None:
            self.map_link.release(camp.id)

    def end_house(self, house, date: Date, reason: str,
                  status: str = EXTINCT) -> None:
        if house.status != ACTIVE:
            return
        house.status = status
        house.ended = date
        house.end_reason = reason
        if house.id in self.active_houses:
            self.active_houses.remove(house.id)
        polity = self.polities.get(house.polity_id)
        if polity is not None and house.id in polity.house_ids:
            polity.house_ids.remove(house.id)

    # ------------------------------------------------------------------
    # Выборки
    # ------------------------------------------------------------------

    def house_members(self, house, alive_in_year: int = 0) -> list:
        """Члены рода; при указании года — только живые в этом году.

        Для живых перебирается короткий список house.living, а не вся
        история рода: за десять тысяч лет она вырастает до сотен имён.
        """
        source = house.living if alive_in_year else house.members
        people = [self.figures[fid] for fid in source if fid in self.figures]
        if alive_in_year:
            people = [p for p in people if p.alive_at(alive_in_year)]
        return people

    def current_reign(self, polity):
        if not polity.reign_ids:
            return None
        return self.reigns.get(polity.reign_ids[-1])

    def houses_of_polity(self, polity) -> list:
        return [self.houses[hid] for hid in polity.house_ids
                if hid in self.houses and self.houses[hid].status == ACTIVE]

    def houses_of_race(self, race_id: str) -> list:
        return [self.houses[hid] for hid in self.active_houses
                if self.houses[hid].race_id == race_id]

    def era_at(self, year: int):
        for span in self.eras:
            if span.contains(year):
                return span
        return self.eras[-1] if self.eras else None

    def era_index_at(self, year: int) -> int:
        span = self.era_at(year)
        return span.index if span else 0

    def tribes_of_race(self, race_id: str) -> list:
        return [self.tribes[tid] for tid in self.active_tribes
                if self.tribes[tid].race_id == race_id]

    def settlements_of_race(self, race_id: str) -> list:
        return [self.settlements[sid] for sid in self.active_settlements
                if self.settlements[sid].race_id == race_id]

    def free_settlements_of_race(self, race_id: str) -> list:
        """Города расы, ещё не входящие ни в одну страну."""
        return [s for s in self.settlements_of_race(race_id) if not s.polity_id]

    def polities_of_race(self, race_id: str) -> list:
        return [self.polities[pid] for pid in self.active_polities
                if self.polities[pid].race_id == race_id]

    def region(self, region_id: str):
        return self.regions.get(region_id)

    def entity(self, entity_id: str):
        """Универсальный доступ по идентификатору."""
        if not entity_id:
            return None
        prefix = entity_id[0]
        table = {
            "R": self.regions, "F": self.figures, "T": self.tribes,
            "C": self.settlements, "P": self.polities, "K": self.camps,
            "H": self.houses, "G": self.reigns, "D": self.calamities,
            "L": self.relics, "B": self.battles, "Y": self.deities,
            "W": self.faiths, "M": self.temples,
        }.get(prefix)
        return table.get(entity_id) if table else None

    def entity_name(self, entity_id: str) -> str:
        item = self.entity(entity_id)
        if item is None:
            return "?"
        return getattr(item, "full_name", None) or item.name

    # ------------------------------------------------------------------
    # Население
    # ------------------------------------------------------------------

    def settlement_realm(self, settlement) -> int:
        """Город вместе с кормящей его округой."""
        return int(settlement.population * RURAL_FACTOR)

    def refresh_populations(self) -> None:
        """Пересчитывает население стран по их поселениям — и по народам."""
        totals = {}
        peoples = {}
        for settlement_id in self.active_settlements:
            settlement = self.settlements[settlement_id]
            if not settlement.polity_id:
                continue
            souls = self.settlement_realm(settlement)
            totals[settlement.polity_id] = totals.get(settlement.polity_id, 0) + souls
            by_race = peoples.setdefault(settlement.polity_id, {})
            by_race[settlement.race_id] = by_race.get(settlement.race_id, 0) + souls
        for polity_id in self.active_polities:
            polity = self.polities[polity_id]
            polity.population = totals.get(polity_id, 0)
            polity.peak_population = max(polity.peak_population, polity.population)
            polity.peoples = peoples.get(polity_id, {})

    def world_population(self) -> int:
        total = 0
        for settlement_id in self.active_settlements:
            total += self.settlement_realm(self.settlements[settlement_id])
        for tribe_id in self.active_tribes:
            total += self.tribes[tribe_id].population
        for camp_id in self.active_camps:
            total += self.camps[camp_id].population
        return total

    def population_by_race(self) -> dict:
        totals = {}
        for settlement_id in self.active_settlements:
            settlement = self.settlements[settlement_id]
            totals[settlement.race_id] = totals.get(settlement.race_id, 0) + \
                self.settlement_realm(settlement)
        for tribe_id in self.active_tribes:
            tribe = self.tribes[tribe_id]
            totals[tribe.race_id] = totals.get(tribe.race_id, 0) + tribe.population
        for camp_id in self.active_camps:
            camp = self.camps[camp_id]
            totals[camp.race_id] = totals.get(camp.race_id, 0) + camp.population
        return totals

    # ------------------------------------------------------------------
    # Вера
    # ------------------------------------------------------------------

    def refresh_faiths(self) -> None:
        """Пересчитывает верующих и народы-носители каждой веры."""
        totals = {}
        races = {}
        for settlement_id in self.active_settlements:
            settlement = self.settlements[settlement_id]
            if not settlement.faith_id:
                continue
            totals[settlement.faith_id] = totals.get(settlement.faith_id, 0) + \
                self.settlement_realm(settlement)
            races.setdefault(settlement.faith_id, set()).add(settlement.race_id)
        for tribe_id in self.active_tribes:
            tribe = self.tribes[tribe_id]
            if tribe.faith_id:
                totals[tribe.faith_id] = totals.get(tribe.faith_id, 0) + tribe.population
                races.setdefault(tribe.faith_id, set()).add(tribe.race_id)
        for camp_id in self.active_camps:
            camp = self.camps[camp_id]
            if camp.faith_id:
                totals[camp.faith_id] = totals.get(camp.faith_id, 0) + camp.population
                races.setdefault(camp.faith_id, set()).add(camp.race_id)
        for faith in self.faiths.values():
            faith.followers = totals.get(faith.id, 0)
            faith.peak_followers = max(faith.peak_followers, faith.followers)
            # Государственной вера считается только в живых странах.
            faith.polity_ids = [pid for pid in faith.polity_ids
                                if pid in self.polities
                                and self.polities[pid].status == ACTIVE
                                and self.polities[pid].faith_id == faith.id]
            present = races.get(faith.id)
            if present:
                # Народы-носители — те, кто верит сейчас, плюс родина веры.
                home = faith.race_ids[0] if faith.race_ids else ""
                ordered = sorted(present)
                if home and home in ordered:
                    ordered.remove(home)
                    ordered.insert(0, home)
                faith.race_ids = ordered

    def faiths_of_race(self, race_id: str) -> list:
        return [self.faiths[fid] for fid in self.living_faiths
                if race_id in self.faiths[fid].race_ids]

    def deity_of(self, faith) -> "Deity":
        return self.deities.get(faith.chief_deity_id)

    # ------------------------------------------------------------------
    # Тёмные века
    # ------------------------------------------------------------------

    def add_dark_age(self, calamity_id: str, start: int, end: int,
                     region_ids, intensity: float, worldwide: bool = False) -> dict:
        record = {
            "calamity_id": calamity_id, "start": int(start), "end": int(end),
            "regions": list(region_ids), "intensity": float(intensity),
            "worldwide": bool(worldwide),
        }
        self.dark_ages.append(record)
        return record

    def darkness_snapshot(self, year: int) -> dict:
        """Карта тьмы на год: земля -> насколько тяжело в ней живётся (0…1).

        Ключ "" хранит общемировую тяжесть.
        """
        snapshot = {}
        for record in self.dark_ages:
            if not (record["start"] <= year <= record["end"]):
                continue
            value = record["intensity"]
            # К концу тёмных веков становится легче.
            span = max(1, record["end"] - record["start"])
            value *= max(0.25, 1.0 - (year - record["start"]) / float(span) * 0.75)
            if record["worldwide"]:
                snapshot[""] = max(snapshot.get("", 0.0), value)
            for region_id in record["regions"]:
                snapshot[region_id] = max(snapshot.get(region_id, 0.0), value)
        return snapshot

    # ------------------------------------------------------------------
    # Итоги
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        final_year = self.total_years
        alive_figures = sum(1 for f in self.figures.values()
                            if f.alive_at(final_year))
        return {
            "Сид": self.seed_text,
            "Длительность": "%d лет" % self.total_years,
            "Эпох": len(self.eras),
            "Земель": len(self.regions),
            "Событий": len(self.events),
            "Личностей": len(self.figures),
            "Живых на конец истории": alive_figures,
            "Племён (всего)": len(self.tribes),
            "Племён (живых)": len(self.active_tribes),
            "Поселений (всего)": len(self.settlements),
            "Поселений (живых)": len(self.active_settlements),
            "Стран (всего)": len(self.polities),
            "Стран (живых)": len(self.active_polities),
            "Лагерей (всего)": len(self.camps),
            "Лагерей (живых)": len(self.active_camps),
            "Знатных родов (всего)": len(self.houses),
            "Знатных родов (живых)": len(self.active_houses),
            "Правлений": len(self.reigns),
            "Бедствий": len(self.calamities),
            "Сражений": len(self.battles),
            "Следов бедствий": len(self.relics),
            "Народов": len(self.folks),
            "Торговых путей": len(self.routes),
            "Путей действует": len(self.active_routes),
            "Походов в неизведанное": len(self.expeditions),
            "Сказаний": len(self.tales),
            "Открытых земель": sum(1 for r in self.regions.values()
                                   if r.discovered_year),
            "Тёмных веков": len(self.dark_ages),
            "Богов": len(self.deities),
            "Вер (всего)": len(self.faiths),
            "Вер (живых)": len(self.living_faiths),
            "Храмов": len(self.temples),
            "Население мира": "%d" % self.world_population(),
            "Погибло от бедствий": "%d" % sum(
                c.deaths for c in self.calamities.values()),
        }

    def race_summary(self) -> list:
        """Сводка по расам: когда пробудились, что основали и что уцелело."""
        blank = {"tribes": [0, 0], "settlements": [0, 0], "polities": [0, 0],
                 "camps": [0, 0], "figures": [0, 0]}
        counts = {race.id: {key: list(value) for key, value in blank.items()}
                  for race in races_mod.RACES}

        def tally(items, key):
            for item in items:
                row = counts.get(item.race_id)
                if row is None:
                    continue
                row[key][0] += 1
                if getattr(item, "status", ACTIVE) == ACTIVE:
                    row[key][1] += 1

        tally(self.tribes.values(), "tribes")
        tally(self.settlements.values(), "settlements")
        tally(self.polities.values(), "polities")
        tally(self.camps.values(), "camps")
        final_year = self.total_years
        for figure in self.figures.values():
            row = counts.get(figure.race_id)
            if row is None:
                continue
            row["figures"][0] += 1
            if figure.alive_at(final_year):
                row["figures"][1] += 1

        rows = []
        for race in races_mod.RACES:
            row = dict(counts[race.id])
            row["race"] = race
            row["awakening"] = self.race_awakening.get(race.id)
            rows.append(row)
        return rows
