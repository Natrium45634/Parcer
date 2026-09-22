# -*- coding: utf-8 -*-
"""Быстрая самопроверка движка.

Запуск:  python tools/selfcheck.py

Проверяет три вещи, которые легко сломать при добавлении новых блоков:

1. детерминированность — один сид даёт побайтово одну и ту же летопись;
2. сохранение и загрузка мира не теряют ни одной записи;
3. правила рас соблюдаются: зверолюды живут племенами, злые расы не
   строят государств и городов;
4. устройство знати: фамилии только у знатных, роды только у тех рас,
   у которых знать бывает, правления идут по порядку;
5. бедствия: у каждого есть исход, следы и битвы ссылаются на своё
   бедствие, потери не превышают населения, тёмные века не вечны;
6. вера: у каждого бога есть вера и праздник, имена вер не повторяются,
   верующие ссылаются на существующие веры;
7. карта: мир, построенный по файлу .world, детерминирован так же, земли
   покрывают всю сушу без пересечений, поселения стоят в своих землях,
   а политическая карта для картогенератора собирается без изъянов;
8. народы и походы: доли народов в державе сходятся с её населением,
   титульный народ живёт в стране, заморские земли открыты до того, как
   в них поселились, а труды учёных не повторяются.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldgen import chronicle, espionage, storage, warfare   # noqa: E402
from worldgen.engine import Settings, generate                # noqa: E402
from worldgen.models import ACTIVE, ONGOING as ONGOING_STATE                             # noqa: E402
from worldgen.races import BEASTFOLK, EVIL, RACES, get_race   # noqa: E402

RACE_IDS = {race.id for race in RACES}

SEEDS = ("Ясень-7", "Первый мир", "проверка", "1234")
FORGE_SEEDS = ("Своя земля",)
MAP_SEEDS = ("карта-1", "карта-2")
SAMPLE_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "maps", "aurora-7.world")


def check_capitals(world, seed: str) -> list:
    """Престол державы: он должен быть живым городом этой самой державы."""
    problems = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if not polity.capital_id:
            if polity.settlement_ids:
                problems.append("сид «%s»: у державы %s есть города, но нет "
                                "престола" % (seed, polity.name))
                break
            continue
        capital = world.settlements.get(polity.capital_id)
        if capital is None:
            problems.append("сид «%s»: престол державы %s — несуществующий "
                            "город" % (seed, polity.name))
            break
        if capital.status != ACTIVE:
            problems.append("сид «%s»: престол державы %s стоит в руинах (%s)"
                            % (seed, polity.name, capital.name))
            break
        if capital.id not in polity.settlement_ids:
            problems.append("сид «%s»: престол державы %s ей не принадлежит "
                            "(%s)" % (seed, polity.name, capital.name))
            break
        if not capital.is_capital:
            problems.append("сид «%s»: город %s держит престол, но не знает "
                            "об этом" % (seed, capital.name))
            break
    return problems


def check_nations(world, seed: str) -> list:
    """Проверяет народы держав и походы в неизведанное."""
    problems = []

    for polity in world.polities.values():
        if polity.status != ACTIVE or not polity.peoples:
            continue
        total = sum(polity.peoples.values())
        if abs(total - polity.population) > max(50, polity.population * 0.02):
            problems.append("сид «%s»: у страны %s народов на %d душ, а "
                            "населения %d" % (seed, polity.name, total,
                                              polity.population))
            break
        if polity.race_id not in polity.peoples:
            problems.append("сид «%s»: титульный народ страны %s в ней не живёт"
                            % (seed, polity.name))
            break
        for value in polity.grievance.values():
            if not (0.0 <= value <= 1.0):
                problems.append("сид «%s»: обида в стране %s вышла за пределы"
                                % (seed, polity.name))
                break

    for expedition in world.expeditions.values():
        if expedition.end is not None and expedition.end.ordinal < expedition.start.ordinal:
            problems.append("сид «%s»: поход «%s» вернулся раньше, чем вышел"
                            % (seed, expedition.name))
            break
        if expedition.deaths > expedition.crew:
            problems.append("сид «%s»: в походе «%s» погибло больше, чем ушло"
                            % (seed, expedition.name))
            break
        for region_id in expedition.discovered:
            region = world.regions.get(region_id)
            if region is None or not region.known:
                problems.append("сид «%s»: поход «%s» открыл землю, которая "
                                "так и не стала ведомой" % (seed, expedition.name))
                break

    # Города не ставят в землях, о которых никто не знает.
    for settlement in world.settlements.values():
        region = world.regions.get(settlement.region_id)
        if region is not None and not region.known:
            problems.append("сид «%s»: город %s стоит в неведомой земле %s"
                            % (seed, settlement.name, region.name))
            break

    # Народы: имя своё, колыбель настоящая, раса совпадает с носителями.
    names = [folk.name for folk in world.folks.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена народов повторяются" % seed)
    for folk in world.folks.values():
        if folk.cradle_region and folk.cradle_region not in world.regions:
            problems.append("сид «%s»: у народа %s колыбель в несуществующей земле"
                            % (seed, folk.name))
            break
    for settlement in world.settlements.values():
        folk = world.folks.get(settlement.folk_id)
        if folk is not None and folk.race_id != settlement.race_id:
            problems.append("сид «%s»: город %s приписан народу чужой расы"
                            % (seed, settlement.name))
            break

    # Торговые пути: настоящие, связные и не через пики.
    link = getattr(world, "map_link", None)
    if link is not None:
        wmap = link.wmap
        for route in world.routes.values():
            if not route.path:
                continue
            broken = False
            for first, second in zip(route.path, route.path[1:]):
                if second not in wmap.neighbors(first):
                    broken = True
                    break
            if broken:
                problems.append("сид «%s»: торговый путь %s рвётся"
                                % (seed, route.id))
                break
            wrong = any(wmap.is_ocean(index) for index in route.path) \
                if not route.by_sea else \
                any(wmap.is_land(index) for index in route.path[1:-1])
            if wrong:
                problems.append("сид «%s»: путь %s идёт не своей стихией"
                                % (seed, route.id))
                break

    # Один труд — один раз за всю историю мира.
    works = [note for figure in world.figures.values() for note in figure.notes
             if note.startswith("труд: ")]
    if len(works) != len(set(works)):
        problems.append("сид «%s»: труды учёных повторяются" % seed)
    return problems


def check_map_world(world, wmap, seed: str) -> list:
    """Проверяет мир, построенный по карте.

    Карту надо передать ту самую, на которой мир и строился: своя карта
    Worldforge и карта из файла — это разные земли, и сверять мир с
    чужой картой значит искать города в чужом море.
    """
    from worldgen import worldmap as wm

    problems = []
    if wmap is None:
        wmap = wm.load(SAMPLE_MAP)

    seen = {}
    for region in world.regions.values():
        if not region.hexes:
            problems.append("сид «%s»: земля %s без гексов" % (seed, region.name))
            continue
        for index in region.hexes:
            if index in seen:
                problems.append("сид «%s»: гекс %d поделили %s и %s"
                                % (seed, index, seen[index], region.name))
                break
            seen[index] = region.name
    land = sum(1 for i in range(wmap.size) if wmap.is_land(i))
    if len(seen) != land:
        problems.append("сид «%s»: земли покрывают %d гексов суши из %d"
                        % (seed, len(seen), land))

    for settlement in world.settlements.values():
        index = settlement.hex_index
        if index < 0:
            continue
        if not wmap.is_land(index):
            problems.append("сид «%s»: город %s стоит в воде"
                            % (seed, settlement.name))
            break
        region = world.regions.get(settlement.region_id)
        if region is not None and region.hexes and index not in region.hexes:
            problems.append("сид «%s»: город %s стоит вне своей земли %s"
                            % (seed, settlement.name, region.name))
            break

    for camp in world.camps.values():
        if camp.hex_index >= 0 and not wmap.is_land(camp.hex_index):
            problems.append("сид «%s»: лагерь %s стоит в воде" % (seed, camp.name))
            break

    recorder = world.map_recorder
    if recorder is None:
        problems.append("сид «%s»: политическая карта не записана" % seed)
        return problems

    section = recorder.build()
    if section["w"] != wmap.width or section["h"] != wmap.height:
        problems.append("сид «%s»: размер политической карты не совпал с картой" % seed)
    if not section["frames"]:
        problems.append("сид «%s»: в политической карте нет ни одного кадра" % seed)
    for frame in section["frames"]:
        total = sum(frame["rle"][i] for i in range(1, len(frame["rle"]), 2))
        if total != wmap.size:
            problems.append("сид «%s»: кадр %d развернулся в %d гексов вместо %d"
                            % (seed, frame["y"], total, wmap.size))
            break
    years = [frame["y"] for frame in section["frames"]]
    if years != sorted(years):
        problems.append("сид «%s»: кадры политической карты идут не по годам" % seed)
    slots = len(section["realmColors"])
    for frame in section["frames"]:
        worst = max((frame["rle"][i] for i in range(0, len(frame["rle"]), 2)),
                    default=-1)
        if worst >= slots:
            problems.append("сид «%s»: в кадре %d держава %d без цвета"
                            % (seed, frame["y"], worst))
            break
    return problems


def digest(world) -> str:
    return hashlib.sha256(chronicle.full_text(world).encode("utf-8")).hexdigest()


def check_nobility(world, seed: str) -> list:
    """Проверяет устройство знати и престолонаследия."""
    problems = []

    for figure in world.figures.values():
        if figure.surname and not figure.house_id:
            problems.append("сид «%s»: у %s есть фамилия без рода"
                            % (seed, figure.name))
            break
    for figure in world.figures.values():
        if figure.house_id and not figure.surname:
            problems.append("сид «%s»: %s состоит в роду, но без фамилии"
                            % (seed, figure.given_name))
            break
    for figure in world.figures.values():
        if figure.surname and not figure.noble:
            problems.append("сид «%s»: %s с фамилией, но не знатен"
                            % (seed, figure.name))
            break

    for house in world.houses.values():
        race = get_race(house.race_id)
        if not race.has_nobility:
            problems.append("сид «%s»: у расы «%s» завёлся род %s"
                            % (seed, race.name, house.name))
            break

    for polity in world.polities.values():
        previous = None
        for index, reign_id in enumerate(polity.reign_ids, start=1):
            reign = world.reigns.get(reign_id)
            if reign is None:
                problems.append("сид «%s»: у страны %s потеряно правление"
                                % (seed, polity.name))
                break
            if reign.ruler_id not in world.figures:
                problems.append("сид «%s»: правление без правителя в %s"
                                % (seed, polity.name))
                break
            if reign.number != index:
                problems.append("сид «%s»: сбит счёт правлений в %s"
                                % (seed, polity.name))
                break
            if previous is not None and reign.start.ordinal < previous.start.ordinal:
                problems.append("сид «%s»: правления идут не по порядку в %s"
                                % (seed, polity.name))
                break
            previous = reign
        if problems:
            break

    return problems


def check_wars(world, seed: str) -> list:
    """Проверяет связность войн: стороны, сражения, мир, добыча."""
    problems = []

    for war in world.wars.values():
        if war.attacker_id == war.defender_id:
            problems.append("сид «%s»: война «%s» ведётся сама с собой"
                            % (seed, war.name))
            break
        if war.attacker_id not in world.polities \
                or war.defender_id not in world.polities:
            problems.append("сид «%s»: у войны «%s» потеряна сторона"
                            % (seed, war.name))
            break
        if war.end is not None and war.end.ordinal < war.start.ordinal:
            problems.append("сид «%s»: война «%s» кончилась раньше, чем началась"
                            % (seed, war.name))
            break
        if war.deaths < 0 or war.attacker_losses < 0 or war.defender_losses < 0:
            problems.append("сид «%s»: у войны «%s» отрицательные потери"
                            % (seed, war.name))
            break
        for battle_id in war.battle_ids:
            if battle_id not in world.battles:
                problems.append("сид «%s»: у войны «%s» потеряно сражение"
                                % (seed, war.name))
                break
        if problems:
            break
        if war.status == "длится" and war.id not in world.active_wars:
            problems.append("сид «%s»: идущая война «%s» не в списке идущих"
                            % (seed, war.name))
            break
        if war.status != "длится" and war.id in world.active_wars:
            problems.append("сид «%s»: законченная война «%s» числится идущей"
                            % (seed, war.name))
            break

    # Взятые города должны принадлежать победителю или быть разорены.
    for war in world.wars.values():
        if war.outcome != "победа нападавших":
            continue
        for settlement_id in war.taken_ids:
            settlement = world.settlements.get(settlement_id)
            if settlement is None:
                problems.append("сид «%s»: война «%s» взяла несуществующий город"
                                % (seed, war.name))
                break
        if problems:
            break

    for feud in world.feuds.values():
        if len(feud.polity_ids) != 2:
            problems.append("сид «%s»: у распри «%s» не две стороны"
                            % (seed, feud.name))
            break
        if feud.end is not None and feud.start is not None \
                and feud.end.ordinal < feud.start.ordinal:
            problems.append("сид «%s»: распря «%s» кончилась раньше начала"
                            % (seed, feud.name))
            break
        for war_id in feud.war_ids:
            if war_id not in world.wars:
                problems.append("сид «%s»: у распри «%s» потеряна война"
                                % (seed, feud.name))
                break
        if problems:
            break

    # Дань и покорность должны указывать на живые державы.
    for polity in world.polities.values():
        for key in ("tribute_to", "overlord_id"):
            other_id = getattr(polity, key)
            if other_id and other_id not in world.polities:
                problems.append("сид «%s»: страна %s платит несуществующей державе"
                                % (seed, polity.name))
                break
        if problems:
            break

    return problems


def check_politics(world, seed: str) -> list:
    """Проверяет связность политики: договоры, союзы, крепости, роты."""
    problems = []

    for pact in world.pacts.values():
        if pact.first_id == pact.second_id:
            problems.append("сид «%s»: договор заключён сам с собой" % seed)
            break
        if pact.first_id not in world.polities \
                or pact.second_id not in world.polities:
            problems.append("сид «%s»: у договора потеряна сторона" % seed)
            break
        if pact.ended is not None and pact.ended.ordinal < pact.signed.ordinal:
            problems.append("сид «%s»: договор расторгнут раньше, чем заключён"
                            % seed)
            break
        if pact.status == "активно" and pact.id not in world.active_pacts:
            problems.append("сид «%s»: действующий договор не в списке" % seed)
            break

    # Между одной парой держав не может быть двух действующих договоров.
    seen = set()
    for pact_id in world.active_pacts:
        pact = world.pacts[pact_id]
        key = tuple(sorted((pact.first_id, pact.second_id)))
        if key in seen:
            problems.append("сид «%s»: у пары держав два договора разом" % seed)
            break
        seen.add(key)

    for league in world.leagues.values():
        if league.ended is not None and league.founded is not None \
                and league.ended.ordinal < league.founded.ordinal:
            problems.append("сид «%s»: союз «%s» распался раньше, чем сложился"
                            % (seed, league.name))
            break
        if league.status == "активно":
            if len(league.member_ids) < 2:
                problems.append("сид «%s»: в союзе «%s» некому состоять"
                                % (seed, league.name))
                break
            if league.leader_id and league.leader_id not in league.member_ids:
                problems.append("сид «%s»: во главе союза «%s» тот, кто в нём "
                                "не состоит" % (seed, league.name))
                break

    for fortress in world.fortresses.values():
        if fortress.region_id not in world.regions:
            problems.append("сид «%s»: крепость %s стоит в несуществующей земле"
                            % (seed, fortress.name))
            break
        if fortress.polity_id and fortress.polity_id not in world.polities:
            problems.append("сид «%s»: крепость %s держит несуществующая держава"
                            % (seed, fortress.name))
            break
        if fortress.ended is not None \
                and fortress.ended.ordinal < fortress.built.ordinal:
            problems.append("сид «%s»: крепость %s разрушена раньше постройки"
                            % (seed, fortress.name))
            break

    for company in world.companies.values():
        if company.men <= 0:
            problems.append("сид «%s»: в роте «%s» нет людей"
                            % (seed, company.name))
            break
        if company.employer_id and company.employer_id not in world.polities:
            problems.append("сид «%s»: роту «%s» нанял никто"
                            % (seed, company.name))
            break

    # Союзники войны должны быть настоящими державами и не воевать сами с собой.
    for war in world.wars.values():
        both = set(war.attacker_allies) & set(war.defender_allies)
        if both:
            problems.append("сид «%s»: в войне «%s» союзник на обеих сторонах"
                            % (seed, war.name))
            break
        for ally_id in war.attacker_allies + war.defender_allies:
            if ally_id not in world.polities:
                problems.append("сид «%s»: в войне «%s» союзник-призрак"
                                % (seed, war.name))
                break
        if war.attacker_id in war.defender_allies \
                or war.defender_id in war.attacker_allies:
            problems.append("сид «%s»: в войне «%s» сторона союзничает сама с "
                            "собой" % (seed, war.name))
            break

    return problems


def check_tongues(world, seed: str) -> list:
    """Проверяет связность языков: родство, носителей, письменность."""
    from worldgen import tongues as tng

    problems = []
    for tongue in world.tongues.values():
        if tongue.parent_id and tongue.parent_id not in world.tongues:
            problems.append("сид «%s»: у языка «%s» потерян родитель"
                            % (seed, tongue.name))
            break
        if tongue.parent_id == tongue.id:
            problems.append("сид «%s»: язык «%s» происходит сам от себя"
                            % (seed, tongue.name))
            break
        if tongue.ended is not None and tongue.ended.ordinal < tongue.born.ordinal:
            problems.append("сид «%s»: язык «%s» умолк раньше, чем родился"
                            % (seed, tongue.name))
            break
        if tongue.status == tng.LIVING and tongue.id not in world.living_tongues:
            problems.append("сид «%s»: живой язык «%s» не в списке живых"
                            % (seed, tongue.name))
            break
        if tongue.status != tng.LIVING and tongue.id in world.living_tongues:
            problems.append("сид «%s»: умолкший язык «%s» числится живым"
                            % (seed, tongue.name))
            break
        if tongue.script_from and tongue.script_from not in world.tongues:
            problems.append("сид «%s»: письмо языка «%s» взято ниоткуда"
                            % (seed, tongue.name))
            break
        if tongue.script_from and not tongue.script:
            problems.append("сид «%s»: у языка «%s» есть источник письма, но "
                            "нет письма" % (seed, tongue.name))
            break

    # Круг в родословной языков невозможен.
    for tongue in world.tongues.values():
        seen, walk = set(), tongue
        while walk is not None and walk.parent_id:
            if walk.id in seen:
                problems.append("сид «%s»: языки «%s» ходят по кругу"
                                % (seed, tongue.name))
                break
            seen.add(walk.id)
            walk = world.tongues.get(walk.parent_id)
        else:
            continue
        break

    # Народ и его язык должны знать друг о друге.
    for folk in world.folks.values():
        if not folk.tongue_id:
            continue
        tongue = world.tongues.get(folk.tongue_id)
        if tongue is None:
            problems.append("сид «%s»: народ %s говорит на несуществующем языке"
                            % (seed, folk.name))
            break
        if folk.id not in tongue.folk_ids:
            problems.append("сид «%s»: народ %s не числится среди говорящих на "
                            "«%s»" % (seed, folk.name, tongue.name))
            break

    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if polity.tongue_id and polity.tongue_id not in world.tongues:
            problems.append("сид «%s»: у державы %s язык двора неизвестен"
                            % (seed, polity.name))
            break

    # Живой язык без единого говорящего — это мёртвый язык.
    for tongue_id in world.living_tongues:
        tongue = world.tongues[tongue_id]
        alive = [fid for fid in tongue.folk_ids
                 if fid in world.folks and world.folks[fid].population > 0]
        if not alive and world.total_years - tongue.born.year > 400:
            problems.append("сид «%s»: на живом языке «%s» никто не говорит"
                            % (seed, tongue.name))
            break

    return problems


def check_embassies(world, seed: str) -> list:
    """Проверяет связность посольств, уний и записанных обид."""
    problems = []
    for record in world.embassies.values():
        if record.sender_id == record.host_id:
            problems.append("сид «%s»: посольство отправлено самим себе" % seed)
            break
        for key in (record.sender_id, record.host_id):
            if key not in world.polities:
                problems.append("сид «%s»: у посольства потеряна сторона" % seed)
                break
        if record.envoy_id and record.envoy_id not in world.figures:
            problems.append("сид «%s»: посольство без посла" % seed)
            break
        if record.returned is not None \
                and record.returned.ordinal < record.sent.ordinal:
            problems.append("сид «%s»: посольство вернулось раньше, чем выехало"
                            % seed)
            break
        if record.pact_id and record.pact_id not in world.pacts:
            problems.append("сид «%s»: договор посольства не найден" % seed)
            break

    for guild in world.guilds.values():
        if guild.seat_id and guild.seat_id not in world.settlements:
            problems.append("сид «%s»: гильдия %s сидит в несуществующем городе"
                            % (seed, guild.name))
            break
        if guild.polity_id and guild.polity_id not in world.polities:
            problems.append("сид «%s»: гильдия %s в несуществующей державе"
                            % (seed, guild.name))
            break
        if guild.ended is not None \
                and guild.ended.ordinal < guild.founded.ordinal:
            problems.append("сид «%s»: гильдия %s кончилась раньше, чем "
                            "завелась" % (seed, guild.name))
            break
        if guild.status == ACTIVE and guild.id not in world.active_guilds:
            problems.append("сид «%s»: живая гильдия %s не в списке живых"
                            % (seed, guild.name))
            break
        if guild.republic_id and guild.republic_id not in world.polities:
            problems.append("сид «%s»: вольный город гильдии %s не найден"
                            % (seed, guild.name))
            break
        for polity_id in guild.charters:
            if polity_id not in world.polities:
                problems.append("сид «%s»: вольности гильдии %s при "
                                "несуществующем дворе" % (seed, guild.name))
                break

    for plot in world.plots.values():
        if plot.sender_id == plot.target_id:
            problems.append("сид «%s»: тайное дело затеяно против себя" % seed)
            break
        if plot.agent_id and plot.agent_id not in world.figures:
            problems.append("сид «%s»: тайное дело без исполнителя" % seed)
            break
        if plot.victim_id and plot.victim_id not in world.figures:
            problems.append("сид «%s»: у тайного дела жертва-призрак" % seed)
            break
        if plot.kind not in espionage.DEEDS_BY_KEY:
            problems.append("сид «%s»: тайное дело неизвестного рода (%s)"
                            % (seed, plot.kind))
            break
        if plot.war_id and plot.war_id not in world.wars:
            problems.append("сид «%s»: тайное дело в несуществующей войне" % seed)
            break

    for union in world.unions.values():
        if union.first_id == union.second_id:
            problems.append("сид «%s»: держава в унии сама с собой" % seed)
            break
        for key in (union.first_id, union.second_id):
            if key not in world.polities:
                problems.append("сид «%s»: у унии потеряна держава" % seed)
                break
        if union.ended is not None \
                and union.ended.ordinal < union.started.ordinal:
            problems.append("сид «%s»: уния распалась раньше, чем сложилась"
                            % seed)
            break
        if union.status == ACTIVE:
            first = world.polities.get(union.first_id)
            second = world.polities.get(union.second_id)
            if first is None or second is None:
                continue
            if first.ruler_id != second.ruler_id:
                problems.append("сид «%s»: в действующей унии два государя"
                                % seed)
                break
            if first.union_id != union.id or second.union_id != union.id:
                problems.append("сид «%s»: держава не помнит своей унии" % seed)
                break

    for polity in world.polities.values():
        for other_id, items in (polity.grudges or {}).items():
            if other_id == polity.id:
                problems.append("сид «%s»: держава %s держит обиду на себя"
                                % (seed, polity.name))
                break
            for key, when in items.items():
                if key not in warfare.CAUSES_BY_KEY:
                    problems.append("сид «%s»: обида без повода (%s)"
                                    % (seed, key))
                    break
                if when < 1 or when > world.total_years:
                    problems.append("сид «%s»: обида записана вне истории"
                                    % seed)
                    break
    return problems


def check_calamities(world, seed: str) -> list:
    """Проверяет связность бедствий, их следов и сражений."""
    problems = []

    for calamity in world.calamities.values():
        if calamity.end is None and calamity.status != "длится":
            problems.append("сид «%s»: бедствие «%s» без даты конца"
                            % (seed, calamity.name))
            break
        if calamity.end is not None and calamity.end.ordinal < calamity.start.ordinal:
            problems.append("сид «%s»: бедствие «%s» кончилось раньше начала"
                            % (seed, calamity.name))
            break
        for region_id in calamity.region_ids:
            if region_id not in world.regions:
                problems.append("сид «%s»: бедствие «%s» ссылается на пустую землю"
                                % (seed, calamity.name))
                break
        if calamity.parent_id and calamity.parent_id not in world.calamities:
            problems.append("сид «%s»: у бедствия «%s» потерян родитель"
                            % (seed, calamity.name))
            break

    faith_relics = ("храм забытой веры", "идол забытого бога")
    for relic in world.relics.values():
        if relic.kind in faith_relics:
            continue          # следы забытых вер остаются не от бедствий
        if any("логово с карты" in note for note in relic.notes):
            continue          # логова лежали в мире ещё до первых бедствий
        if relic.calamity_id not in world.calamities:
            problems.append("сид «%s»: след «%s» без своего бедствия"
                            % (seed, relic.name))
            break

    for battle in world.battles.values():
        if battle.war_id:
            continue          # сражения держав принадлежат войне, а не беде
        if battle.calamity_id not in world.calamities:
            problems.append("сид «%s»: сражение «%s» без своего бедствия"
                            % (seed, battle.name))
            break

    for settlement in world.settlements.values():
        if settlement.population < 0:
            problems.append("сид «%s»: у поселения %s отрицательное население"
                            % (seed, settlement.name))
            break

    for record in world.dark_ages:
        if record["end"] <= record["start"]:
            problems.append("сид «%s»: тёмные века нулевой длины" % seed)
            break

    monsters = {race.id for race in __import__(
        "worldgen.races", fromlist=["MONSTERS"]).MONSTERS}
    for settlement in world.settlements.values():
        if settlement.race_id in monsters:
            problems.append("сид «%s»: чудовища построили город %s"
                            % (seed, settlement.name))
            break
    for house in world.houses.values():
        if house.race_id in monsters:
            problems.append("сид «%s»: у чудовищ завёлся знатный род" % seed)
            break

    return problems


def check_causes(world, seed: str) -> list:
    """Причинность: следы, зёрна и цепи событий.

    Проверяем то, что ломается незаметно: след, ссылающийся на событие,
    которого нет; зерно, взошедшее раньше, чем посеяно; причина, которая
    случилась позже следствия; цепь причин, замкнутая в кольцо.
    """
    from worldgen import history

    problems = []
    events = {event.id: event for event in world.events}

    for fact in world.facts.values():
        if fact.event_id and fact.event_id not in events:
            problems.append("сид «%s»: след «%s» ссылается на несуществующее "
                            "событие" % (seed, fact.kind))
            break
        if fact.closed and fact.closed < fact.year:
            problems.append("сид «%s»: след «%s» закрыт раньше, чем появился"
                            % (seed, fact.kind))
            break
        if fact.holder_id and not (fact.holder_id in world.polities
                                   or fact.holder_id in world.regions
                                   or fact.holder_id in world.settlements
                                   or fact.holder_id in world.figures
                                   or fact.holder_id in RACE_IDS):
            problems.append("сид «%s»: след «%s» принадлежит неизвестно кому"
                            % (seed, fact.kind))
            break

    for item in world.seeds.values():
        if item.due < item.born:
            problems.append("сид «%s»: зерно «%s» созревает раньше, чем "
                            "посеяно" % (seed, item.kind))
            break
        if item.state == "сбылось" and item.result_id \
                and item.result_id not in events:
            problems.append("сид «%s»: зерно «%s» взошло в несуществующее "
                            "событие" % (seed, item.kind))
            break
        if item.settled and item.settled < item.born:
            problems.append("сид «%s»: зерно «%s» разрешилось раньше, чем "
                            "посеяно" % (seed, item.kind))
            break
        if item.state != "ждёт" and not history.known_seed(item.kind):
            problems.append("сид «%s»: у зерна «%s» нет обработчика"
                            % (seed, item.kind))
            break

    deep = 0
    for event in world.events:
        for parent_id in event.causes:
            parent = events.get(parent_id)
            if parent is None:
                problems.append("сид «%s»: событие «%s» ссылается на "
                                "несуществующую причину" % (seed, event.title))
                break
            if parent.date.ordinal > event.date.ordinal:
                problems.append("сид «%s»: причина события «%s» случилась "
                                "позже него" % (seed, event.title))
                break
        else:
            deep = max(deep, history.depth_of(world, event, 30))
            continue
        break
    if deep >= 29:
        problems.append("сид «%s»: цепь причин не кончается — похоже на "
                        "кольцо" % seed)
    return problems


def check_people_memory(world, seed: str) -> list:
    """Память людей и связи: не помнит ли кто того, чего не было."""
    problems = []
    events = {event.id: event for event in world.events}

    for memory in world.memories.values():
        figure = world.figures.get(memory.figure_id)
        if figure is None:
            problems.append("сид «%s»: воспоминание принадлежит "
                            "несуществующему человеку" % seed)
            break
        if figure.birth is not None and memory.year < figure.birth.year:
            problems.append("сид «%s»: %s помнит то, что было до его "
                            "рождения" % (seed, figure.plain_name))
            break
        if figure.death is not None and memory.year > figure.death.year:
            problems.append("сид «%s»: %s помнит то, что случилось после "
                            "его смерти" % (seed, figure.plain_name))
            break
        if memory.event_id and memory.event_id not in events:
            problems.append("сид «%s»: воспоминание ссылается на событие, "
                            "которого не было" % seed)
            break
        if memory.about_id and not (memory.about_id in world.figures
                                    or memory.about_id in world.polities
                                    or memory.about_id in RACE_IDS):
            problems.append("сид «%s»: воспоминание о том, кого нет" % seed)
            break

    for bond in world.bonds.values():
        if bond.a_id not in world.figures or bond.b_id not in world.figures:
            problems.append("сид «%s»: связь с несуществующим человеком" % seed)
            break
        if bond.a_id == bond.b_id:
            problems.append("сид «%s»: человек связан сам с собой" % seed)
            break
        if bond.ended and bond.ended < bond.since:
            problems.append("сид «%s»: связь оборвалась раньше, чем "
                            "завязалась" % seed)
            break
    return problems


def check_migrations(world, seed: str) -> list:
    """Переселения: не ушли ли люди в никуда и не пришли ли ниоткуда."""
    problems = []
    events = {event.id: event for event in world.events}
    for item in world.migrations.values():
        if item.from_region and item.from_region not in world.regions:
            problems.append("сид «%s»: переселение из несуществующей земли"
                            % seed)
            break
        if item.to_region and item.to_region not in world.regions:
            problems.append("сид «%s»: переселение в несуществующую землю"
                            % seed)
            break
        target = world.regions.get(item.to_region)
        # Земля могла утонуть и после того, как в неё пришли: беда
        # переселению не помеха, если она случилась позже.
        if target is not None and target.drowned \
                and target.drowned_year and item.year > target.drowned_year:
            problems.append("сид «%s»: переселение в землю, ушедшую под воду"
                            % seed)
            break
        if item.souls <= 0:
            problems.append("сид «%s»: переселение без единой души" % seed)
            break
        if item.year < 1 or item.year > world.total_years:
            problems.append("сид «%s»: переселение вне времени мира" % seed)
            break
        if item.event_id and item.event_id not in events:
            problems.append("сид «%s»: переселение без записи в летописи"
                            % seed)
            break
        if item.to_polity and item.to_polity not in world.polities:
            problems.append("сид «%s»: переселение в несуществующую державу"
                            % seed)
            break
        if item.race_id not in RACE_IDS:
            problems.append("сид «%s»: переселение народа, которого нет"
                            % seed)
            break
    return problems


def check_strifes(world, seed: str) -> list:
    """Смуты и заговоры: не воюет ли держава с тем, кого нет."""
    problems = []
    for item in world.strifes.values():
        if item.polity_id not in world.polities:
            problems.append("сид «%s»: смута в несуществующей державе" % seed)
            break
        if item.end is not None and item.end.ordinal < item.start.ordinal:
            problems.append("сид «%s»: смута «%s» кончилась раньше, чем "
                            "началась" % (seed, item.name))
            break
        if item.status != ONGOING_STATE and not item.outcome:
            problems.append("сид «%s»: у смуты «%s» нет исхода"
                            % (seed, item.name))
            break
        both = set(item.crown_cities) & set(item.rebel_cities)
        if both:
            problems.append("сид «%s»: город смуты «%s» держат обе стороны "
                            "разом" % (seed, item.name))
            break
        if item.rebel_id and item.rebel_id not in world.figures:
            problems.append("сид «%s»: смуту «%s» поднял тот, кого нет"
                            % (seed, item.name))
            break
        if item.heir_polity_id and item.heir_polity_id not in world.polities:
            problems.append("сид «%s»: из смуты «%s» вышла несуществующая "
                            "держава" % (seed, item.name))
            break

    for item in world.cabals.values():
        if item.polity_id not in world.polities:
            problems.append("сид «%s»: заговор в несуществующей державе" % seed)
            break
        if item.leader_id not in world.figures:
            problems.append("сид «%s»: заговор ведёт тот, кого нет" % seed)
            break
        if item.target_id and item.target_id not in world.figures:
            problems.append("сид «%s»: заговор против того, кого нет" % seed)
            break
        if item.ended and item.ended < item.born:
            problems.append("сид «%s»: заговор кончился раньше, чем начался"
                            % seed)
            break
        if item.ended and not item.outcome:
            problems.append("сид «%s»: у кончившегося заговора нет исхода"
                            % seed)
            break
        if any(member not in world.figures for member in item.members):
            problems.append("сид «%s»: в заговоре числится тот, кого нет"
                            % seed)
            break
    return problems


def check_things(world, seed: str) -> list:
    """Вещи, места и чудовища: всё ли на месте и ни у кого ли нет лишнего.

    Главное правило блока: подземелье берёт факты из истории, а не наоборот.
    Значит, у каждой вещи должна быть цепочка рук, у каждого места — то,
    от чего оно осталось, а у каждого чудовища — год, когда его убили,
    если оно мертво.
    """
    problems = []

    names = [item.name for item in world.artifacts.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена вещей повторяются" % seed)

    for artifact in world.artifacts.values():
        if artifact.made is None:
            problems.append("сид «%s»: вещь «%s» никогда не делали"
                            % (seed, artifact.name))
            break
        if artifact.gender not in ("m", "f", "n", "p"):
            problems.append("сид «%s»: у вещи «%s» нет рода"
                            % (seed, artifact.name))
            break
        if artifact.owner_id and artifact.owner_id not in world.figures:
            problems.append("сид «%s»: вещь «%s» у несуществующего владельца"
                            % (seed, artifact.name))
            break
        if artifact.site_id and artifact.site_id not in world.sites:
            problems.append("сид «%s»: вещь «%s» лежит в несуществующем месте"
                            % (seed, artifact.name))
            break
        if not artifact.trail:
            problems.append("сид «%s»: у вещи «%s» пустая цепочка рук"
                            % (seed, artifact.name))
            break
        years = [int(step.get("year", 0)) for step in artifact.trail]
        if any(years[i] > years[i + 1] for i in range(len(years) - 1)):
            problems.append("сид «%s»: цепочка рук вещи «%s» идёт вспять"
                            % (seed, artifact.name))
            break
        if years and years[0] < artifact.made.year:
            problems.append("сид «%s»: вещь «%s» сменила владельца до ковки"
                            % (seed, artifact.name))
            break

    names = [site.name for site in world.sites.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена мест повторяются" % seed)

    for site in world.sites.values():
        if site.region_id and site.region_id not in world.regions:
            problems.append("сид «%s»: место «%s» лежит вне земель"
                            % (seed, site.name))
            break
        if not (1 <= site.depth <= 5):
            problems.append("сид «%s»: у места «%s» немыслимая глубина"
                            % (seed, site.name))
            break
        if site.riches < 0:
            problems.append("сид «%s»: у места «%s» отрицательное добро"
                            % (seed, site.name))
            break
        if site.opened is not None and site.opened.ordinal < site.created.ordinal:
            problems.append("сид «%s»: место «%s» вскрыли до того, как оно "
                            "появилось" % (seed, site.name))
            break
        if site.figure_id and site.figure_id not in world.figures:
            problems.append("сид «%s»: в месте «%s» лежит неизвестно кто"
                            % (seed, site.name))
            break
        for artifact_id in site.artifact_ids:
            if artifact_id not in world.artifacts:
                problems.append("сид «%s»: в месте «%s» лежит несуществующая вещь"
                                % (seed, site.name))
                break
        if not (site.figure_id or site.settlement_id or site.battle_id
                or site.calamity_id or site.monster_id or site.polity_id
                or site.artifact_ids or site.story):
            problems.append("сид «%s»: место «%s» появилось ниоткуда"
                            % (seed, site.name))
            break

    names = [monster.name for monster in world.monsters.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена чудовищ повторяются" % seed)

    for monster in world.monsters.values():
        if monster.status != "жив" and monster.ended is None:
            problems.append("сид «%s»: чудовище «%s» мертво без года смерти"
                            % (seed, monster.name))
            break
        if monster.ended is not None and monster.ended.ordinal < monster.born.ordinal:
            problems.append("сид «%s»: чудовище «%s» умерло до рождения"
                            % (seed, monster.name))
            break
        if monster.slayer_id and monster.slayer_id not in world.figures:
            problems.append("сид «%s»: чудовище «%s» убил никто"
                            % (seed, monster.name))
            break
        if monster.hoard < 0 or monster.kills < 0:
            problems.append("сид «%s»: у чудовища «%s» отрицательный счёт"
                            % (seed, monster.name))
            break
        if monster.site_id and monster.site_id not in world.sites:
            problems.append("сид «%s»: у чудовища «%s» логово в пустоте"
                            % (seed, monster.name))
            break

    return problems


def check_lore(world, seed: str) -> list:
    """Ремёсла, своды, легенды и законы: связность и здравый смысл."""
    problems = []

    for discovery in world.discoveries.values():
        if discovery.polity_id and discovery.polity_id not in world.polities:
            problems.append("сид «%s»: открытие «%s» сделала несуществующая страна"
                            % (seed, discovery.name))
            break
        for polity_id in discovery.known_by:
            if polity_id not in world.polities:
                problems.append("сид «%s»: открытие «%s» перенял никто"
                                % (seed, discovery.name))
                break
        if len(discovery.known_by) != len(set(discovery.known_by)):
            problems.append("сид «%s»: открытие «%s» переняли дважды"
                            % (seed, discovery.name))
            break
        if discovery.polity_id and discovery.polity_id not in discovery.known_by:
            problems.append("сид «%s»: страна забыла своё же открытие «%s»"
                            % (seed, discovery.name))
            break

    for polity in world.polities.values():
        if len(polity.known) != len(set(polity.known)):
            problems.append("сид «%s»: страна %s знает одно ремесло дважды"
                            % (seed, polity.name))
            break
        if len(polity.reforms) != len(set(polity.reforms)):
            problems.append("сид «%s»: страна %s провела одну реформу дважды"
                            % (seed, polity.name))
            break

    for codex in world.codices.values():
        if codex.seat_id and codex.seat_id not in world.settlements:
            problems.append("сид «%s»: свод «%s» пишут в несуществующем городе"
                            % (seed, codex.name))
            break
        if not (0.0 <= codex.accuracy <= 1.0):
            problems.append("сид «%s»: у свода «%s» немыслимая точность"
                            % (seed, codex.name))
            break
        if codex.ended is not None and codex.ended.ordinal < codex.started.ordinal:
            problems.append("сид «%s»: свод «%s» закрыли до того, как начали"
                            % (seed, codex.name))
            break
        if codex.status != "ведётся" and codex.ended is None:
            problems.append("сид «%s»: свод «%s» оборван без года"
                            % (seed, codex.name))
            break
        years = [int(entry.get("year", 0)) for entry in codex.entries]
        if any(years[i] > years[i + 1] for i in range(len(years) - 1)):
            problems.append("сид «%s»: записи свода «%s» идут вспять"
                            % (seed, codex.name))
            break
        if years and years[0] < codex.started.year:
            problems.append("сид «%s»: в своде «%s» есть запись до его начала"
                            % (seed, codex.name))
            break
        seen = set()
        for keeper in codex.keepers:
            figure_id = keeper.get("figure")
            if figure_id and figure_id not in world.figures:
                problems.append("сид «%s»: свод «%s» ведёт неизвестно кто"
                                % (seed, codex.name))
                break
            if figure_id in seen:
                problems.append("сид «%s»: летописец свода «%s» садится за него "
                                "дважды" % (seed, codex.name))
                break
            seen.add(figure_id)

    names = [legend.name for legend in world.legends.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена легенд повторяются" % seed)

    for legend in world.legends.values():
        if legend.tellings < 1:
            problems.append("сид «%s»: легенду «%s» никто не рассказывал"
                            % (seed, legend.name))
            break
        if not legend.truth:
            problems.append("сид «%s»: у легенды «%s» нет правды под ней"
                            % (seed, legend.name))
            break
        shift_years = [int(shift.get("year", 0)) for shift in legend.shifts]
        if any(year < legend.born.year for year in shift_years):
            problems.append("сид «%s»: легенда «%s» изменилась до рождения"
                            % (seed, legend.name))
            break

    for law in world.laws.values():
        if law.polity_id and law.polity_id not in world.polities:
            problems.append("сид «%s»: закон «%s» завела несуществующая страна"
                            % (seed, law.name))
            break
        if law.polity_id and law.polity_id not in law.copied_by:
            problems.append("сид «%s»: страна забыла свой же закон «%s»"
                            % (seed, law.name))
            break
        if len(law.copied_by) != len(set(law.copied_by)):
            problems.append("сид «%s»: закон «%s» переняли дважды"
                            % (seed, law.name))
            break
        if law.ruler_id and law.ruler_id not in world.figures:
            problems.append("сид «%s»: закон «%s» завёл никто"
                            % (seed, law.name))
            break

    return problems


def check_upheavals(world, seed: str) -> list:
    """Великие бедствия: что они сделали с картой — и осталось ли согласовано."""
    from worldgen.systems import upheaval as upheaval_mod

    problems = []

    for region in world.regions.values():
        if not region.drowned:
            continue
        if region.capacity or region.habitat:
            problems.append("сид «%s»: затопленная земля %s всё ещё кормит"
                            % (seed, region.name))
            break
        for settlement_id in world.active_settlements:
            if world.settlements[settlement_id].region_id == region.id:
                problems.append("сид «%s»: город стоит в затопленной земле %s"
                                % (seed, region.name))
                break
        for tribe_id in world.active_tribes:
            if world.tribes[tribe_id].region_id == region.id:
                problems.append("сид «%s»: племя живёт в затопленной земле %s"
                                % (seed, region.name))
                break

    for region in world.regions.values():
        for other_id in region.neighbors:
            other = world.regions.get(other_id)
            if other is None:
                problems.append("сид «%s»: земля %s соседит с пустотой"
                                % (seed, region.name))
                break
            if region.id not in other.neighbors:
                problems.append("сид «%s»: соседство %s и %s держится в одну "
                                "сторону" % (seed, region.name, other.name))
                break
        for other_id in region.sea_links:
            other = world.regions.get(other_id)
            if other is None:
                problems.append("сид «%s»: у земли %s морской путь в пустоту"
                                % (seed, region.name))
                break
            if other_id in region.neighbors:
                problems.append("сид «%s»: %s и %s соседят и по суше, и по морю "
                                "разом" % (seed, region.name, other.name))
                break

    gone = world.notes.get(upheaval_mod.GONE_NOTE) or {}
    alive = world.population_by_race()
    for race_id in gone:
        if alive.get(race_id):
            problems.append("сид «%s»: вымерший народ «%s» всё ещё жив"
                            % (seed, race_id))
            break

    great = [item for item in world.calamities.values()
             if item.key in upheaval_mod.GREAT]
    if len(great) > 8:
        problems.append("сид «%s»: великих бедствий %d — это уже погода, "
                        "а не конец света" % (seed, len(great)))
    for calamity in great:
        if calamity.key == "deep_waking" and not calamity.parent_id:
            problems.append("сид «%s»: «%s» поднялось ниоткуда, а должно было "
                            "быть осколком прошлого" % (seed, calamity.name))
            break

    peak = int(world.notes.get(upheaval_mod.PEAK_NOTE) or 0)
    if peak and world.world_population() * 200 < peak:
        problems.append("сид «%s»: мир опустел — от лучшего века осталась "
                        "двухсотая доля" % seed)

    return problems


def check_faiths(world, seed: str) -> list:
    """Проверяет устройство веры."""
    problems = []

    names = [faith.name for faith in world.faiths.values()]
    if len(names) != len(set(names)):
        problems.append("сид «%s»: имена вер повторяются" % seed)

    for deity in world.deities.values():
        if deity.faith_id and deity.faith_id not in world.faiths:
            problems.append("сид «%s»: бог %s принадлежит несуществующей вере"
                            % (seed, deity.given_name))
            break
        if not (1 <= deity.festival_month <= 12 and 1 <= deity.festival_day <= 30):
            problems.append("сид «%s»: у бога %s праздник вне календаря"
                            % (seed, deity.given_name))
            break
        if not (-3 <= deity.alignment <= 3):
            problems.append("сид «%s»: у бога %s немыслимое мировоззрение"
                            % (seed, deity.given_name))
            break

    for faith in world.faiths.values():
        for deity_id in faith.deity_ids:
            if deity_id not in world.deities:
                problems.append("сид «%s»: у веры «%s» потерян бог"
                                % (seed, faith.name))
                break
        if faith.parent_id and faith.parent_id not in world.faiths:
            problems.append("сид «%s»: у ереси «%s» нет родительской веры"
                            % (seed, faith.name))
            break

    for settlement in world.settlements.values():
        if settlement.faith_id and settlement.faith_id not in world.faiths:
            problems.append("сид «%s»: город %s верит в несуществующее"
                            % (seed, settlement.name))
            break

    for temple in world.temples.values():
        if temple.faith_id not in world.faiths:
            problems.append("сид «%s»: храм «%s» без веры" % (seed, temple.name))
            break

    return problems


def main() -> int:
    failures = []

    for seed in SEEDS:
        started = time.time()
        first = generate(Settings(seed=seed, years=10000))
        second = generate(Settings(seed=seed, years=10000))
        spent = time.time() - started

        if digest(first) != digest(second):
            failures.append("сид «%s»: две генерации разошлись" % seed)

        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        try:
            storage.save_world(first, path)
            restored = storage.load_world(path)
        finally:
            os.remove(path)
        if digest(restored) != digest(first):
            failures.append("сид «%s»: мир изменился после сохранения" % seed)

        for settlement in first.settlements.values():
            race = get_race(settlement.race_id)
            if race.category in (BEASTFOLK, EVIL):
                failures.append("сид «%s»: %s построили город %s"
                                % (seed, race.name, settlement.name))
                break
        for polity in first.polities.values():
            race = get_race(polity.race_id)
            if race.category in (BEASTFOLK, EVIL):
                failures.append("сид «%s»: %s основали страну %s"
                                % (seed, race.name, polity.name))
                break
        for camp in first.camps.values():
            if not get_race(camp.race_id).is_evil:
                failures.append("сид «%s»: лагерь %s принадлежит не злой расе"
                                % (seed, camp.name))
                break

        events = first.events
        if any(events[i].date.ordinal > events[i + 1].date.ordinal
               for i in range(len(events) - 1)):
            failures.append("сид «%s»: события идут не по порядку" % seed)

        failures.extend(check_nobility(first, seed))
        failures.extend(check_wars(first, seed))
        failures.extend(check_politics(first, seed))
        failures.extend(check_calamities(first, seed))
        failures.extend(check_faiths(first, seed))
        failures.extend(check_nations(first, seed))
        failures.extend(check_tongues(first, seed))
        failures.extend(check_embassies(first, seed))
        failures.extend(check_things(first, seed))
        failures.extend(check_causes(first, seed))
        failures.extend(check_people_memory(first, seed))
        failures.extend(check_migrations(first, seed))
        failures.extend(check_strifes(first, seed))
        failures.extend(check_lore(first, seed))
        failures.extend(check_upheavals(first, seed))
        failures.extend(check_capitals(first, seed))

        print("  сид «%-12s» событий %5d | города %4d | страны %3d | роды %4d | "
              "бедствия %3d | боги %3d | веры %3d | население %8d (%.1f c)"
              % (seed, len(events), len(first.settlements), len(first.polities),
                 len(first.houses), len(first.calamities), len(first.deities),
                 len(first.faiths), first.world_population(), spent))

    if not os.path.exists(SAMPLE_MAP):
        print("\n  карта для примера не найдена — проверка по карте пропущена")
    else:
        from worldgen import worldmap as wm_mod
        sample = wm_mod.load(SAMPLE_MAP)
        print()
        for seed in MAP_SEEDS:
            started = time.time()
            settings = Settings(seed=seed, years=10000, map_path=SAMPLE_MAP)
            first = generate(settings)
            second = generate(settings)
            spent = time.time() - started

            if digest(first) != digest(second):
                failures.append("карта, сид «%s»: две генерации разошлись" % seed)

            handle, path = tempfile.mkstemp(suffix=".json")
            os.close(handle)
            try:
                storage.save_world(first, path)
                restored = storage.load_world(path)
            finally:
                os.remove(path)
            if digest(restored) != digest(first):
                failures.append("карта, сид «%s»: мир изменился после сохранения" % seed)

            failures.extend(check_nobility(first, "карта/" + seed))
            failures.extend(check_wars(first, "карта/" + seed))
            failures.extend(check_politics(first, "карта/" + seed))
            failures.extend(check_calamities(first, "карта/" + seed))
            failures.extend(check_faiths(first, "карта/" + seed))
            failures.extend(check_nations(first, "карта/" + seed))
            failures.extend(check_tongues(first, "карта/" + seed))
            failures.extend(check_embassies(first, "карта/" + seed))
            failures.extend(check_things(first, "карта/" + seed))
            failures.extend(check_causes(first, "карта/" + seed))
            failures.extend(check_people_memory(first, "карта/" + seed))
            failures.extend(check_migrations(first, "карта/" + seed))
            failures.extend(check_strifes(first, "карта/" + seed))
            failures.extend(check_lore(first, "карта/" + seed))
            failures.extend(check_upheavals(first, "карта/" + seed))
            failures.extend(check_capitals(first, "карта/" + seed))
            failures.extend(check_map_world(first, sample, "карта/" + seed))

            print("  карта, сид «%-8s» земель %3d | города %4d | страны %3d | "
                  "кадров %3d | население %8d (%.1f c)"
                  % (seed, len(first.regions), len(first.settlements),
                     len(first.polities),
                     len(first.map_recorder.frames) if first.map_recorder else 0,
                     first.world_population(), spent))

    # Мир на карте, которую программа делает сама: Worldforge должен
    # держать те же проверки, что и карта из файла.
    print()
    for seed in FORGE_SEEDS:
        started = time.time()
        settings = Settings(seed=seed, years=4000,
                            map_make={"seed": seed, "size": "small"})
        first = generate(settings)
        second = generate(settings)
        spent = time.time() - started

        if digest(first) != digest(second):
            failures.append("своя карта, сид «%s»: две генерации разошлись"
                            % seed)
        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        try:
            storage.save_world(first, path)
            restored = storage.load_world(path)
        finally:
            os.remove(path)
        if digest(restored) != digest(first):
            failures.append("своя карта, сид «%s»: мир изменился после "
                            "сохранения" % seed)
        for check in (check_nobility, check_wars, check_politics,
                      check_calamities, check_faiths, check_nations,
                      check_tongues, check_embassies, check_things,
                      check_causes, check_people_memory, check_migrations,
                      check_strifes, check_lore, check_upheavals,
                      check_capitals):
            failures.extend(check(first, "своя/" + seed))
        from worldgen import worldforge
        failures.extend(check_map_world(
            first, worldforge.forge(seed, size="small"), "своя/" + seed))
        print("  своя карта, сид «%-8s» земель %3d | города %4d | страны %3d "
              "| население %8d (%.1f c)"
              % (seed, len(first.regions), len(first.settlements),
                 len(first.polities), first.world_population(), spent))

    if failures:
        print("\nОШИБКИ:")
        for line in failures:
            print("  -", line)
        return 1
    print("\nВсё в порядке.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
