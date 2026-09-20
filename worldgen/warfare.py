# -*- coding: utf-8 -*-
"""Война: за что берутся за оружие, чем воюют и чем это кончается.

Здесь нет ни одного текста для летописи — только правила. Тексты живут
в narrative_war.py, годовой ход войны — в systems/war.py.

**Повод.** Война не начинается оттого, что сосед слаб. У неё есть
причина, и причина эта видна из состояния мира: держава без железа
смотрит на чужие рудники, держава без хлеба — на чужие житницы,
светлая вера — на соседей-работорговцев, а род, потерявший престол, —
на чужую корону. Есть и причины, которых в нашем мире не бывает:
пророчество, воля бога, реликвия в чужих руках, жила магии под чужой
землёй, древняя вражда со времён бедствия.

**Сила.** Войско считается от числа душ. Держава выставляет около
сотой части населения, и это сильно зависит от народа, эпохи и от
того, кто на престоле: полководец приводит вдвое больше, чем книжник.
Качество войска решает не меньше числа.

**Случай.** Вдвое сильнейший проигрывает примерно каждое пятое
сражение. Так и должно быть: без этого история становится таблицей
умножения, а не историей.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import goods as goods_mod
from . import nations as pol
from .models import ACTIVE

# --- чего хотят от войны ------------------------------------------------
LAND = "земли"           # забрать города
FREE = "единокровцы"     # отбить города своего народа
TRIBUTE = "дань"         # обложить данью
VASSAL = "подчинение"    # заставить признать старшинство
FAITH = "вера"           # заставить сменить веру
PLUNDER = "добыча"       # пограбить и уйти
RELIC = "святыня"        # забрать реликвию или святыню
RUIN = "искоренение"     # стереть

AIM_NAMES = {
    LAND: "отобрать земли", FREE: "вернуть единокровцев",
    TRIBUTE: "обложить данью", VASSAL: "принудить к покорности",
    FAITH: "переменить веру", PLUNDER: "взять добычу",
    RELIC: "забрать святыню", RUIN: "истребить",
}


@dataclass(frozen=True)
class Casus:
    """Повод к войне: как он зовётся, чего от него хотят и как жестоко."""

    key: str
    kind: str                # земля / хозяйство / вера / народы / престол / чудеса
    aim: str
    zeal: float              # 0.7 — повоюют и разойдутся, 1.6 — до конца
    titles: tuple            # как назовут войну (шаблоны с безопасными местами)
    pretexts: tuple          # чем объяснили её начало


# Места в шаблонах названий: %(city)s, %(region)s, %(good)s, %(faith)s,
# %(house)s, %(folk)s, %(foe)s — все подставляются в именительном падеже
# после слова в нужном падеже, поэтому склонять ничего не приходится.
CAUSES = (
    # --- земля -----------------------------------------------------------
    Casus("border", "земля", LAND, 0.9,
          ("Война за межу", "Пограничная война",
           "Война за землю по имени %(region)s"),
          ("Межу не могут развести третье поколение подряд.",
           "Спорную землю обе стороны считают своей по праву давности.",
           "Пограничные камни переставляли столько раз, что верить им перестали.",
           "Повод — луга, на которых пасли скот и те и другие.")),
    Casus("reclaim", "земля", LAND, 1.25,
          ("Война за возвращение", "Война за город %(city)s",
           "Война за утраченное"),
          ("Отнятое дедами намерены вернуть внуки.",
           "Города, потерянные в прошлой войне, объявлены исконными.",
           "Старая грамота о владении найдена вовремя и очень кстати.",
           "Обиду прежнего поражения припомнили при первой же слабости соседа.")),
    Casus("gate", "земля", LAND, 1.0,
          ("Война за перевал", "Война за проход",
           "Война за город %(city)s"),
          ("Кто держит проход, тот держит и торговлю, и войско соседа.",
           "Крепость в теснине стоит целой области, и обе стороны это знают.",
           "Единственная дорога через горы оказалась в чужих руках.")),
    # --- хозяйство -------------------------------------------------------
    Casus("port", "хозяйство", LAND, 1.05,
          ("Война за гавань", "Война за город %(city)s", "Морская война"),
          ("Держава без своего порта платит за море втридорога.",
           "Чужая гавань закрыта для купцов — и это сочли объявлением войны.",
           "Пошлины в чужом порту подняли трижды за десять лет.")),
    Casus("mines", "хозяйство", LAND, 1.1,
          ("Рудная война", "Война за рудники", "Война за землю по имени %(region)s"),
          ("Своего железа нет, а чужое лежит за рекой.",
           "Рудники соседа кормят его кузни и его войско.",
           "Оружейники требуют руды, и проще взять, чем купить.")),
    Casus("bread", "хозяйство", TRIBUTE, 1.0,
          ("Хлебная война", "Война за житницы", "Голодная война"),
          ("Своего хлеба не хватает третий год, а у соседа полны амбары.",
           "Житницы соседа решено взять прежде, чем начнётся мор.",
           "Голод гонит войско вернее любого указа.")),
    Casus("salt", "хозяйство", LAND, 0.95,
          ("Соляная война", "Война за варницы"),
          ("Соль дороже серебра, а варницы — у соседа.",
           "Соляной откуп у чужих рук, и это давно раздражает.")),
    Casus("tolls", "хозяйство", TRIBUTE, 0.85,
          ("Война за пошлины", "Купеческая война",
           "Война за дорогу"),
          ("Пошлины на чужих переправах съедают всю выгоду.",
           "Купцов ограбили на чужой дороге, и никто не ответил.",
           "Торговый путь перекрыт, а без него держава беднеет на глазах.")),
    Casus("gems", "хозяйство", PLUNDER, 0.8,
          ("Война за самоцветы", "Богатая война"),
          ("Богатство соседа стало заметнее его войска.",
           "Сокровищницу чужой столицы уже подсчитали заранее.")),
    # --- вера ------------------------------------------------------------
    Casus("crusade", "вера", FAITH, 1.45,
          ("Война за веру", "Священная война", "Война против нечестивых"),
          ("Соседская вера объявлена мерзостью, и терпеть её больше не намерены.",
           "Жрецы обещают всякому павшему место подле бога.",
           "Войну объявляют не государь, а храм — государь лишь соглашается.")),
    Casus("heresy", "вера", FAITH, 1.4,
          ("Война с ересью", "Война за чистую веру"),
          ("Ересь, отколовшаяся от здешней веры, окрепла и обзавелась державой.",
           "Отступников решено привести к прежней вере силой.",
           "Раскол, начатый спором о словах, кончается войском.")),
    Casus("shrine", "вера", RELIC, 1.35,
          ("Война за святыню", "Война за город %(city)s",
           "Война за храм"),
          ("Святыня здешней веры оказалась в чужих руках.",
           "Паломников к святому месту перестали пускать вовсе.",
           "Храм, куда ходили триста лет, объявлен чужим.")),
    Casus("godword", "чудеса", RUIN, 1.6,
          ("Война по воле богов", "Война-знамение"),
          ("Бог говорил с государем во сне, и сон был недвусмысленный.",
           "Оракул назвал год, землю и имя врага.",
           "Волю бога огласили с крыльца храма, и спорить никто не стал.")),
    # --- народы ----------------------------------------------------------
    Casus("kin", "народы", FREE, 1.3,
          ("Война за единокровцев", "Освободительная война",
           "Война за народ по имени %(folk)s"),
          ("За рубежом живут свои, и живут они плохо.",
           "Единокровцев за межой притесняют, и терпеть это перестали.",
           "Просьбу о защите привезли беглецы, и её не оставили без ответа.")),
    Casus("oppression", "народы", VASSAL, 1.2,
          ("Война против притеснителей", "Война за правду"),
          ("О том, что творится у соседа, рассказали беглые.",
           "Чужие законы о народах сочли достаточным поводом.",
           "Соседская жестокость стала известна слишком многим.")),
    Casus("slavers", "народы", RUIN, 1.5,
          ("Война против работорговцев", "Война за волю"),
          ("Соседи торгуют людьми, и торгуют в том числе здешними.",
           "Невольничьи рынки соседа решено закрыть железом.",
           "Караван с невольниками перехватили — и не остановились на этом.")),
    # --- престол ---------------------------------------------------------
    Casus("claim", "престол", VASSAL, 1.3,
          ("Война за наследство", "Война за корону",
           "Война за престол"),
          ("Притязание на чужой венец основано на родстве и подкреплено войском.",
           "Родословную перечитали заново и нашли в ней достаточно оснований.",
           "Наследство делили без нас — значит, поделим сами.")),
    Casus("succession", "престол", VASSAL, 1.25,
          ("Война за пустой престол", "Война о наследстве"),
          ("У соседа некому сесть на престол, и охотников нашлось много.",
           "Междуцарствие у соседа сочли приглашением.",
           "Наследников не осталось, и на корону нашлось трое чужих.")),
    Casus("insult", "престол", TRIBUTE, 0.85,
          ("Война за обиду", "Война чести"),
          ("Обиду нанесли при всём дворе, и её нельзя было проглотить.",
           "Посольство выгнали, не выслушав, — этого хватило.",
           "Сватовство отвергли в таких словах, что оскорбление сочли общим.")),
    Casus("murder", "престол", RUIN, 1.45,
          ("Война за кровь", "Война мести"),
          ("Посла убили на чужой земле, и виновных не выдали.",
           "Родича государя нашли мёртвым в чужом городе.",
           "За смерть заложника решено взыскать войском.")),
    # --- чудеса ----------------------------------------------------------
    Casus("prophecy", "чудеса", LAND, 1.4,
          ("Война по пророчеству", "Предсказанная война"),
          ("Пророчество назвало год и место, и его решили не обманывать.",
           "Звездочёты сошлись на том, что срок пришёл.",
           "В старом свитке нашли строку, которую истолковали как приказ.")),
    Casus("relic", "чудеса", RELIC, 1.35,
          ("Война за реликвию", "Война за землю по имени %(region)s"),
          ("Реликвия, оставшаяся от древнего бедствия, лежит на чужой земле.",
           "След старой беды на соседской земле решено взять под свою руку.",
           "То, что спит за рубежом, не должно достаться чужим рукам.")),
    Casus("leyline", "чудеса", LAND, 1.3,
          ("Война за источник силы", "Чародейная война",
           "Война за землю по имени %(region)s"),
          ("Земля соседа полна силы, и чародеи требуют её себе.",
           "Жилу магии нашли по ту сторону межи.",
           "Чародейный круг настоял на походе, и его послушали.")),
    Casus("curse", "чудеса", RUIN, 1.5,
          ("Война с проклятым", "Война против порчи"),
          ("Соседа объявили проклятым, и порчу решено выжечь.",
           "Мор, пришедший с той стороны, сочли не случайностью, а умыслом.",
           "Чужих чародеев обвинили в засухе, и обвинение приняли на веру.")),
    Casus("undeath", "чудеса", RUIN, 1.55,
          ("Война против мёртвых", "Война за покой мёртвых"),
          ("У соседа поднимают мёртвых, и терпеть это никто не станет.",
           "Могилы за рубежом пусты, и это видели многие.",
           "Некромантия соседа перестала быть слухом.")),
    Casus("dragon", "чудеса", PLUNDER, 1.15,
          ("Война за клад", "Драконья война"),
          ("Клад, о котором рассказывают сказители, лежит за чужой межой.",
           "Логово на спорной земле обещает больше, чем десять лет податей.")),
    Casus("ancient", "чудеса", RUIN, 1.35,
          ("Война древней вражды", "Война старой памяти"),
          ("Вражда тянется со времён общего бедствия, и причину уже забыли.",
           "Обиду помнят с той поры, когда обе державы были племенами.",
           "Старые счёты припомнили полностью и с процентами.")),
    # --- море --------------------------------------------------------------
    Casus("sealanes", "хозяйство", TRIBUTE, 1.15,
          ("Война за морские пути", "Война за проливы", "Морская война"),
          ("Морскую дорогу перекрыли чужие корабли, и купцы взвыли.",
           "Пролив, которым ходят все, объявлен чужим владением.",
           "Пошлину за проход через пролив подняли вчетверо.",
           "Кто держит пролив, тот держит и хлеб, и соль, и войско.")),
    Casus("piracy", "хозяйство", PLUNDER, 1.2,
          ("Война против морского разбоя", "Война за чистое море",
           "Война с пиратами"),
          ("Корабли пропадают третий год, и все знают, в чьи гавани уходит добыча.",
           "Разбой на море перестали скрывать даже приличия ради.",
           "Купеческий караван вырезали целиком, и виновных не выдали.")),
    Casus("isles", "земля", LAND, 1.05,
          ("Война за острова", "Заморская война",
           "Война за город %(city)s"),
          ("Острова за проливом лежат ничьи только на словах.",
           "Заморские земли решено взять, пока их не взяли другие.",
           "Флот построили раньше, чем придумали, куда его вести.")),
    # --- реванш ------------------------------------------------------------
    Casus("revenge", "престол", LAND, 1.4,
          ("Война за реванш", "Война отместки", "Вторая война за %(region)s"),
          ("Прошлую войну проиграли, и проигравшие успели вырасти.",
           "Условия прошлого мира назвали позорными, едва высохли подписи.",
           "Договор, которым кончилась прошлая война, объявлен недействительным.",
           "Поколение, выросшее после поражения, помнит его лучше отцов.")),
    # --- иго ---------------------------------------------------------------
    Casus("yoke", "престол", TRIBUTE, 1.5,
          ("Война против ига", "Война за свободу от дани",
           "Война против старшинства"),
          ("Дань платили три поколения; четвёртое платить отказалось.",
           "Посольство за данью выгоняют, не приняв, — и это объявление войны.",
           "Старшинство признавали, пока признавать было выгодно.",
           "Обоз с данью разворачивают у самой границы.")),
    # --- обиды, у которых есть виновник -----------------------------------
    Casus("envoy", "обида", RUIN, 1.5,
          ("Война за кровь посла", "Война посольской крови",
           "Война за поруганное слово"),
          ("Посольство не вернулось домой, и убийц называют поимённо.",
           "Кровь посла не смывается ни выкупом, ни извинением.",
           "Убийство посла сочли объявлением войны — и не ошиблись.",
           "Тело посла привозят домой, и войско собирают прежде похорон.")),
    Casus("spy", "обида", PLUNDER, 1.1,
          ("Война соглядатаев", "Война за тайные дела",
           "Война, начатая при дворе"),
          ("Соглядатая взяли с поличным, и признание он дал полное.",
           "Тайные дела чужого двора вскрылись слишком поздно, но вскрылись.",
           "Пойманный лазутчик назвал того, кто его послал.",
           "Подкуп военачальника вскрылся после проигранного сражения.")),
    Casus("poison", "обида", RUIN, 1.6,
          ("Война за отравленного государя", "Война яда и кубка",
           "Война за смерть при дворе"),
          ("Государя отравили, и лекари назвали яд чужеземным.",
           "Смерть при дворе списали бы на болезнь, если бы не найденный сосуд.",
           "Убийцу взяли живым, и он говорил охотно.",
           "Яд подали за столом, и виновных искали недолго.")),
    Casus("oath", "обида", LAND, 1.3,
          ("Война клятвопреступников", "Война за нарушенное слово",
           "Война за попранный договор"),
          ("Клятву нарушили первыми не мы — так пишут обе стороны.",
           "Договор порвали, не дождавшись, пока высохнут подписи.",
           "На зов союзника не пришли, и союз кончился войной.",
           "Слово, данное при свидетелях, взяли назад.")),
    # --- без затей -------------------------------------------------------
    Casus("greed", "земля", PLUNDER, 0.75,
          ("Война за добычу", "Набеговая война", "Короткая война"),
          ("Повода не искали: сосед оказался слаб, и этого хватило.",
           "Войско собрали раньше, чем придумали объяснение.",
           "Летописец честно пишет: пошли за добычей.")),
)

CAUSES_BY_KEY = {item.key: item for item in CAUSES}

# Как повод называется в справочниках — коротко и по-русски.
CAUSE_LABELS = {
    "border": "спор о меже", "reclaim": "возврат утраченного",
    "gate": "горный проход", "port": "чужая гавань", "mines": "рудники",
    "bread": "житницы", "salt": "соляные варницы", "tolls": "пошлины и дороги",
    "gems": "чужое богатство", "crusade": "иная вера", "heresy": "ересь",
    "shrine": "святыня в чужих руках", "godword": "воля бога",
    "kin": "единокровцы под чужой рукой", "oppression": "притеснение народов",
    "slavers": "работорговля", "claim": "притязание на престол",
    "succession": "пустой престол", "insult": "обида", "murder": "пролитая кровь",
    "prophecy": "пророчество", "relic": "реликвия", "leyline": "жила магии",
    "curse": "проклятие", "undeath": "поднятые мёртвые", "dragon": "драконий клад",
    "ancient": "древняя вражда", "greed": "жажда добычи",
    "yoke": "дань и чужое старшинство", "revenge": "память о поражении",
    "sealanes": "морские пути", "piracy": "морской разбой",
    "isles": "заморские земли", "envoy": "кровь посла",
    "spy": "тайные дела и соглядатаи", "poison": "яд при дворе",
    "oath": "нарушенная клятва",
}

# Обиды, у которых есть виновник и год. Живут долго, но не вечно: через
# GRUDGE_YEARS о них помнят только летописцы.
GRUDGE_YEARS = 260
GRUDGE_WEIGHT = {"envoy": 5.0, "poison": 4.6, "oath": 2.6, "spy": 2.2,
                 "insult": 1.4}


def cause_label(key: str) -> str:
    return CAUSE_LABELS.get(key, key)


# ---------------------------------------------------------------------------
# Из чего вырастает повод
# ---------------------------------------------------------------------------

def _faith_of(world, polity):
    return world.faiths.get(polity.faith_id)


def _has_port(world, polity) -> bool:
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        region = world.regions.get(settlement.region_id)
        if region is not None and region.coastal:
            return True
    return False


def _good_share(polity, good: str) -> float:
    """Во сколько раз своего товара больше нужды (или меньше)."""
    pair = (polity.goods or {}).get(good)
    if not pair:
        return 1.0
    have, need = pair
    return float(have) / max(0.001, float(need))


def _region_magic(world, polity) -> float:
    best = 0.0
    for region_id in polity.region_ids:
        region = world.regions.get(region_id)
        if region is not None:
            best = max(best, abs(region.magic))
    return best


def _relics_in(world, polity) -> int:
    count = 0
    for relic in world.relics.values():
        if relic.status == "исчерпан":
            continue
        if relic.region_id in polity.region_ids:
            count += 1
    return count


def reasons(ctx, attacker, defender, year: int) -> list:
    """Все поводы, какие у этой державы есть против этой — с весами.

    Вес — не вероятность, а то, насколько повод на виду. Слабый повод
    тоже годится: за добычей ходили во все времена.
    """
    world = ctx.world
    out = [(CAUSES_BY_KEY["greed"], 1.0), (CAUSES_BY_KEY["border"], 1.6)]

    def add(key, weight):
        if weight > 0:
            out.append((CAUSES_BY_KEY[key], weight))

    # --- земля ---
    lost = sum(1 for sid in defender.settlement_ids
               if sid in world.settlements
               and world.settlements[sid].race_id == attacker.race_id)
    if lost:
        add("reclaim", 1.0 + 0.7 * min(4, lost))
    if any(world.regions.get(rid) is not None
           and world.regions[rid].terrain == "горы"
           for rid in defender.region_ids):
        add("gate", 1.1)

    # --- хозяйство ---
    if not _has_port(world, attacker) and _has_port(world, defender):
        add("port", 2.4)
    if _good_share(attacker, goods_mod.METAL) < 0.8 \
            and _good_share(defender, goods_mod.METAL) > 1.2:
        add("mines", 2.2)
    if attacker.hunger > 0.15 and _good_share(defender, goods_mod.GRAIN) > 1.1:
        add("bread", 1.8 + 3.0 * attacker.hunger)
    if _good_share(attacker, goods_mod.SALT) < 0.8 \
            and _good_share(defender, goods_mod.SALT) > 1.2:
        add("salt", 1.5)
    if attacker.routes or defender.routes:
        add("tolls", 1.2)

    # --- море ---
    our_ports, their_ports = ports(world, attacker), ports(world, defender)
    if our_ports and their_ports:
        sea_routes = sum(1 for route_id in attacker.routes
                         if route_id in world.routes
                         and world.routes[route_id].by_sea)
        add("sealanes", 1.4 + 0.5 * sea_routes)
        add("piracy", 0.9 + 0.4 * sea_routes)
    if their_ports and any(getattr(world.regions.get(rid), "island", False)
                           or getattr(world.regions.get(rid), "terrain", "")
                           == "острова"
                           for rid in defender.region_ids):
        add("isles", 1.6 if our_ports else 0.3)
    if defender.population > attacker.population * 0.8 \
            and _good_share(defender, goods_mod.GEMS) > 1.3:
        add("gems", 1.1)

    # --- вера ---
    ours, theirs = _faith_of(world, attacker), _faith_of(world, defender)
    if ours is not None and theirs is not None and ours.id != theirs.id:
        gap = abs(ours.alignment - theirs.alignment)
        add("crusade", 0.6 + 0.8 * gap + (1.2 if theirs.forbidden else 0.0))
        if theirs.parent_id == ours.id or ours.parent_id == theirs.id:
            add("heresy", 2.6)
        for temple_id in ours.temple_ids:
            temple = world.temples.get(temple_id)
            if temple is None:
                continue
            settlement = world.settlements.get(temple.settlement_id)
            if settlement is not None and settlement.polity_id == defender.id:
                add("shrine", 2.2)
                break
    if ours is not None and abs(ours.alignment) >= 2:
        add("godword", 0.5 + 0.4 * abs(ours.alignment))

    # --- народы ---
    kin = defender.peoples.get(attacker.race_id, 0)
    if kin and defender.share_of(attacker.race_id) >= 0.08:
        anger = defender.grievance.get(attacker.race_id, 0.0)
        add("kin", 1.4 + 3.0 * anger + 2.0 * defender.share_of(attacker.race_id))
    if pol.is_harsh(defender.policy):
        add("oppression", 1.6)
        if defender.policy in (pol.SLAVERY, pol.PURGE):
            good = ours is not None and ours.alignment >= 1
            add("slavers", 2.0 + (1.5 if good else 0.0))

    # --- престол ---
    # Проигранная война — самый верный повод к следующей.
    for war in world.wars_of(attacker):
        if war.end is None or defender.id not in (war.attacker_id,
                                                  war.defender_id):
            continue
        if year - war.end.year > 400:
            continue
        lost = ((war.attacker_id == attacker.id
                 and war.outcome == DEFENDER_WON)
                or (war.defender_id == attacker.id
                    and war.outcome == ATTACKER_WON))
        if lost:
            add("revenge", 3.2)
            break
    if attacker.tribute_to == defender.id or attacker.overlord_id == defender.id:
        add("yoke", 4.0)
    if defender.interregnum:
        add("succession", 2.8)
    house = world.houses.get(attacker.house_id)
    if house is not None and house.thrones > 1:
        add("claim", 1.3)
    add("insult", 0.9)
    if attacker.conquests or defender.conquests:
        add("murder", 0.7)

    # --- чудеса ---
    add("prophecy", 0.6)
    relics = _relics_in(world, defender)
    if relics:
        add("relic", 0.8 + 0.6 * min(4, relics))
        add("dragon", 0.5 + 0.4 * min(3, relics))
    magic = _region_magic(world, defender)
    if magic > 0.35:
        add("leyline", 0.8 + 2.0 * magic)
    if theirs is not None and theirs.alignment <= -2:
        add("undeath", 1.2)
        add("curse", 1.0)
    if ctx.world_darkness > 0.25:
        add("curse", 1.2)          # в тёмные века виноват всегда сосед
    if attacker.founded.year < year - 1500 and defender.founded.year < year - 1500:
        add("ancient", 1.0)

    # --- обиды поимённо ---
    # Кровь посла, яд в кубке, пойманный соглядатай, нарушенная клятва:
    # поводы, у которых есть виновник, год и имя. Свежая обида весит
    # больше любой спорной межи и со временем стирается.
    for key, when in sorted((attacker.grudges.get(defender.id) or {}).items()):
        if key not in CAUSES_BY_KEY:
            continue
        age = year - int(when)
        if age < 0 or age > GRUDGE_YEARS:
            continue
        fade = 1.0 - age / float(GRUDGE_YEARS)
        add(key, GRUDGE_WEIGHT.get(key, 1.5) * (0.3 + 0.7 * fade))

    return out


# ---------------------------------------------------------------------------
# Войско
# ---------------------------------------------------------------------------

LEVY_SHARE = 0.011          # какая доля душ уходит в поход
LEVY_MIN = 60

# Народы, у которых война — ремесло, и те, у кого она в тягость.
MARTIAL_TRAITS = {
    "воители": 0.35, "берсерки": 0.40, "налётчики": 0.30, "лучники": 0.20,
    "танцоры клинка": 0.30, "почитатели войны": 0.40, "костоломы": 0.25,
    "дубиноносцы": 0.20, "следопыты": 0.15, "загонщики": 0.15,
    "небесные дозорные": 0.15, "сторожа драконьих троп": 0.20,
    "ловушечники": 0.15, "отравители": 0.15, "тенемаги": 0.20,
    "чародеи": 0.25, "заклинатели": 0.20, "шаманы тины": 0.10,
    "камнерезы": -0.10, "хлебопашцы": -0.15, "торговцы": -0.10,
    "звездочёты": -0.15, "певцы леса": -0.10, "менестрели": -0.15,
    "травники": -0.10, "сказители": -0.10, "медлительные мудрецы": -0.20,
    "бортники": -0.15, "рыболовы": -0.05, "хранители очага": -0.10,
}


def martial(race) -> float:
    """Насколько народ воинствен: 1.0 — обычно."""
    value = 1.0
    for trait in race.traits:
        value += MARTIAL_TRAITS.get(trait, 0.0)
    return max(0.55, min(1.8, value))


def levy(world, polity, race, era_index: int = 2) -> int:
    """Сколько душ держава может поставить под знамёна.

    Считается от населения, но не только: воинственный народ выводит
    вдвое против землепашцев, полководец на престоле собирает больше
    книжника, а голодная держава — меньше всех.
    """
    from . import rulers as rulers_mod

    souls = max(0, int(polity.population))
    share = LEVY_SHARE * martial(race)
    share *= 0.85 + 0.06 * max(0, era_index)          # позже воюют большими силами
    share *= rulers_mod.war_edge(world, polity)
    if polity.hunger:
        share *= max(0.45, 1.0 - polity.hunger)
    if polity.policy in (pol.SLAVERY, pol.PURGE):
        share *= 1.12                                  # гонят и подневольных
    elif polity.policy == pol.EQUAL:
        share *= 1.06                                  # идут охотнее
    return max(LEVY_MIN, int(souls * share))


def quality(world, polity, race, general=None) -> float:
    """Выучка войска: от ополчения до дружины, что ходила двадцать лет."""
    from . import rulers as rulers_mod

    from . import crafts as crafts_mod
    from . import laws as laws_mod

    value = 0.75 + 0.35 * martial(race)
    value *= rulers_mod.war_edge(world, polity)
    # Стремя, сталь и самострел стоят выучки: держава, отставшая на век,
    # выходит в поле хуже вооружённой — и это видно по исходу.
    value *= crafts_mod.bonus(polity.known, "war")
    # Постоянное войско и правильный набор стоят не меньше стали.
    value *= laws_mod.bonus(polity.reforms, "war")
    if general is not None:
        value *= 0.85 + 0.06 * _general_skill(general)
    # Обиженные народы воюют хуже: их держат в тылу и не доверяют оружия.
    anger = max(list(polity.grievance.values()) + [0.0])
    value *= max(0.7, 1.0 - 0.3 * anger)
    return max(0.4, min(2.2, value))


def _general_skill(figure) -> int:
    """Полководческое умение: у правителя оно записано, у прочих — жребий."""
    if figure is None:
        return 5
    skills = getattr(figure, "skills", None)
    if skills:
        return int(skills.get("война", 5))
    return int(getattr(figure, "war_skill", 5) or 5)


def host_power(men: int, quality_value: float) -> float:
    """Сила войска. Число решает, но не линейно: толпа не вдвое сильнее."""
    return (max(1, men) ** 0.92) * quality_value


# ---------------------------------------------------------------------------
# Сражение
# ---------------------------------------------------------------------------

# Насколько случай способен перевернуть перевес. При 2.2 вдвое
# сильнейший проигрывает примерно каждое пятое сражение — это и есть
# то, ради чего всё затевалось.
LUCK_SPREAD = 2.2


def battle_odds(rng, attack_power: float, defend_power: float,
                home_ground: bool = False, fortified: bool = False,
                attack_general=None, defend_general=None) -> tuple:
    """Кто победит и насколько решительно. Возвращает (победа_нападающих, вес).

    Случай входит в расчёт не поправкой, а множителем: туман, брод,
    ночной переход и предательство проводника весят столько же, сколько
    лишняя тысяча копий.
    """
    ratio = max(0.05, attack_power) / max(0.05, defend_power)
    if home_ground:
        ratio /= 1.32            # дома и стены помогают
    if fortified:
        ratio /= 1.35
    ratio *= (1.0 + 0.045 * (_general_skill(attack_general) - 5))
    ratio /= (1.0 + 0.045 * (_general_skill(defend_general) - 5))

    luck = rng.uniform(1.0 / LUCK_SPREAD, LUCK_SPREAD)
    edge = ratio * luck
    attacker_wins = edge >= 1.0
    # Насколько решительно: 0 — еле устояли, 1 — разгром.
    margin = abs(edge - 1.0) / (abs(edge - 1.0) + 1.0)
    return attacker_wins, margin


def battle_losses(rng, winner_men: int, loser_men: int, margin: float) -> tuple:
    """Потери сторон. Разгром выкашивает войско, ничья — стачивает оба."""
    loser_share = 0.06 + 0.30 * margin
    winner_share = 0.05 * (1.0 - margin) + 0.015
    loser_dead = int(loser_men * loser_share * rng.uniform(0.7, 1.35))
    winner_dead = int(winner_men * winner_share * rng.uniform(0.6, 1.5))
    return max(1, winner_dead), max(1, loser_dead)


# ---------------------------------------------------------------------------
# Осада
# ---------------------------------------------------------------------------

# Во сколько раз быстрее падает гавань, запертая и с суши, и с моря.
SEALED_SPEED = 2.0


def siege_odds(rng, besiegers: float, garrison: float, years: int,
               starving: bool = False, sealed: bool = False) -> str:
    """Чем кончится осадный год: «пал», «держится», «снята».

    Город берут не силой, а временем: чем дольше стоят под стенами, тем
    вернее откроются ворота — или тем вернее осаждающие уйдут сами,
    потому что в лагере начался мор.

    Портовый город — особая статья. Пока гавань открыта, осада почти
    бессмысленна: подвоз идёт морем, и город переживёт осаждающих. Но
    если та же сторона заперла гавань флотом, город остаётся без
    подвоза вовсе — и падает вдвое быстрее.
    """
    # Числом город не берут: за стенами перевес значит куда меньше, чем
    # в поле, и потому осада — это прежде всего время.
    strength = min(3.0, besiegers / max(0.05, garrison))
    chance_fall = min(0.55, 0.03 + 0.07 * strength + 0.06 * years)
    if starving:
        chance_fall += 0.14
    lift = min(0.4, 0.05 + 0.05 * years) / max(0.6, strength)
    if sealed:
        chance_fall = min(0.8, chance_fall * SEALED_SPEED)
        lift *= 0.5          # осаждающих кормит их же флот
    if rng.chance(chance_fall):
        return "пал"
    # Осада разваливается сама: болезни, зима, бескормица.
    if rng.chance(lift):
        return "снята"
    return "держится"


# ---------------------------------------------------------------------------
# Сколько война длится и чем кончается
# ---------------------------------------------------------------------------

def war_scale(attacker_men: int, defender_men: int) -> int:
    """Масштаб войны: 1 — стычка двух княжеств, 5 — война империй.

    Пороги считаны по живым мирам генератора, а не по нашей истории:
    держава в четверть миллиона душ выводит около трёх тысяч копий, и
    война двух таких — уже большая война, а не пограничная стычка.
    """
    total = attacker_men + defender_men
    for level, threshold in ((5, 20000), (4, 8000), (3, 3000), (2, 900)):
        if total >= threshold:
            return level
    return 1


def expected_length(rng, scale: int, zeal: float, parity: float) -> int:
    """Сколько лет война продлится, если ничто её не оборвёт.

    Долго воюют равные и упрямые. Империя, налетевшая на княжество,
    кончает дело за год-другой — если княжество не окажется упрямым.
    """
    base = {1: 4, 2: 8, 3: 14, 4: 22, 5: 34}.get(scale, 8)
    # Равные силы — главная причина долгих войн: ни у кого нет сил
    # кончить дело, и ни у кого нет причин уступить.
    value = base * zeal * (0.40 + 1.6 * parity)
    return max(1, int(rng.uniform(0.55, 1.8) * value))


# --- чем всё кончилось ---------------------------------------------------
ATTACKER_WON = "победа нападавших"
DEFENDER_WON = "победа оборонявшихся"
WHITE = "без перемен"
EXHAUSTION = "обоюдное истощение"
INTERRUPTED = "война прервана"
ANNIHILATION = "держава уничтожена"

OUTCOME_ORDER = (ATTACKER_WON, DEFENDER_WON, WHITE, EXHAUSTION, INTERRUPTED,
                 ANNIHILATION)


def terms(aim: str, margin: float) -> dict:
    """Что победитель берёт по миру — по своей цели и по тому, как крупно взял.

    `margin` — насколько уверенной вышла победа, от 0 до 1.
    """
    strong = margin >= 0.55
    out = {"cities": 0, "tribute": 0, "faith": False, "vassal": False,
           "plunder": False, "relic": False, "raze": False}
    if aim in (LAND, FREE):
        out["cities"] = 3 if strong else (2 if margin >= 0.3 else 1)
        if strong:
            out["tribute"] = 30
    elif aim == TRIBUTE:
        out["tribute"] = 80 if strong else 40
        out["cities"] = 1 if strong else 0
    elif aim == VASSAL:
        out["vassal"] = True
        out["tribute"] = 100 if strong else 50
        out["cities"] = 1 if strong else 0
    elif aim == FAITH:
        out["faith"] = True
        out["tribute"] = 40 if strong else 0
        out["cities"] = 1 if strong else 0
    elif aim == PLUNDER:
        out["plunder"] = True
        out["tribute"] = 25 if strong else 10
    elif aim == RELIC:
        out["relic"] = True
        out["cities"] = 1 if strong else 0
    elif aim == RUIN:
        out["cities"] = 5 if strong else 2
        out["raze"] = strong
    return out


# ---------------------------------------------------------------------------
# Море
# ---------------------------------------------------------------------------

# Народы, для которых море — дорога, и те, для кого оно край света.
SEA_TRAITS = {
    "мореходы": 0.55, "рыболовы": 0.25, "собиратели прибоя": 0.30,
    "хранители отмелей": 0.30, "ломатели раковин": 0.20,
    "собиратели ветров": 0.25, "небесные дозорные": 0.10,
    "торговцы": 0.15, "караванщики": -0.10, "камнерезы": -0.25,
    "рудознатцы": -0.30, "рудокопы-воришки": -0.30, "камнееды": -0.35,
    "хлебопашцы": -0.15, "певцы леса": -0.20, "хранители рун": -0.20,
}

SHIP_PER_SOULS = 3500.0     # сколько душ кормит один боевой корабль
CREW_PER_SHIP = 45          # и сколько человек он несёт


def seafaring(race) -> float:
    """Насколько народ силён на воде: 1.0 — обычно, 0.3 — сухопутный."""
    value = 1.0
    for trait in race.traits:
        value += SEA_TRAITS.get(trait, 0.0)
    return max(0.25, min(2.2, value))


# Земли, что выходят к воде, даже когда карта об этом не говорит прямо.
SEA_TERRAINS = ("побережье", "острова")


def is_shore(region) -> bool:
    if region is None:
        return False
    return bool(region.coastal or region.island
                or region.terrain in SEA_TERRAINS or region.sea)


def ports(world, polity) -> list:
    """Города на берегу — из них и растёт флот."""
    out = []
    for settlement_id in polity.settlement_ids:
        settlement = world.settlements.get(settlement_id)
        if settlement is None or settlement.status != ACTIVE:
            continue
        if is_shore(world.regions.get(settlement.region_id)):
            out.append(settlement)
    return out


def fleet(world, polity, race, era_index: int = 2) -> int:
    """Сколько боевых кораблей держава может вывести в море.

    Флот растёт не из населения вообще, а из портов: держава в глубине
    материка не построит и лодки, сколько бы душ в ней ни жило.
    """
    harbours = ports(world, polity)
    if not harbours:
        return 0
    souls = sum(settlement.population for settlement in harbours)
    from . import crafts as crafts_mod

    ships = souls / SHIP_PER_SOULS * seafaring(race)
    ships *= 0.75 + 0.12 * max(0, era_index)
    # Киль, компас и океанский корабль: держава, знающая их, выводит
    # в море больше и дальше.
    ships *= crafts_mod.bonus(polity.known, "sea")
    if polity.hunger:
        ships *= max(0.4, 1.0 - polity.hunger)
    return max(1, int(ships))


def sea_power(ships: int, race, admiral=None) -> float:
    """Сила флота: корабли, выучка команд и умение того, кто их ведёт."""
    value = seafaring(race) * (0.85 + 0.06 * _general_skill(admiral))
    return (max(1, ships) ** 0.95) * value


def sea_battle(rng, attack_power: float, defend_power: float,
               home_waters: bool = False, storm: bool = False) -> tuple:
    """Морской бой. На воде случай весит ещё больше, чем на суше.

    Ветер, течение и внезапный шквал переворачивают морские сражения
    чаще, чем туман — сухопутные.
    """
    ratio = max(0.05, attack_power) / max(0.05, defend_power)
    if home_waters:
        ratio /= 1.20            # свои отмели, свои лоцманы
    if storm:
        # Буря не разбирает, кто сильнее: она просто мешает обоим, но
        # больше — тому, у кого кораблей больше.
        ratio = 1.0 + (ratio - 1.0) * 0.35
    luck = rng.uniform(1.0 / SEA_LUCK, SEA_LUCK)
    edge = ratio * luck
    margin = abs(edge - 1.0) / (abs(edge - 1.0) + 1.0)
    return edge >= 1.0, margin


SEA_LUCK = 2.7               # разброс морской удачи: шире сухопутного


def sea_losses(rng, winner_ships: int, loser_ships: int, margin: float,
               storm: bool = False) -> tuple:
    """Потери кораблей. На море разгром означает дно, а не отступление."""
    loser_share = 0.12 + 0.45 * margin
    winner_share = 0.06 * (1.0 - margin) + 0.02
    if storm:
        loser_share += 0.10
        winner_share += 0.08
    return (max(0, int(winner_ships * winner_share * rng.uniform(0.5, 1.5))),
            max(1, int(loser_ships * loser_share * rng.uniform(0.7, 1.3))))


def can_reach_by_sea(world, first, second) -> bool:
    """Есть ли у обеих держав порты и общая вода между ними."""
    first_ports = ports(world, first)
    second_ports = ports(world, second)
    if not first_ports or not second_ports:
        return False
    waters = set()
    for settlement in first_ports:
        region = world.regions.get(settlement.region_id)
        if region is not None:
            if region.sea:
                waters.add(region.sea)
            waters.update(region.sea_links)
    for settlement in second_ports:
        region = world.regions.get(settlement.region_id)
        if region is None:
            continue
        if region.id in waters:
            return True
        if region.sea and region.sea in waters:
            return True
    # На процедурной карте морей по именам нет — считаем, что берег общий:
    # два приморских народа рано или поздно встретятся на воде.
    return not waters
