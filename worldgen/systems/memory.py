# -*- coding: utf-8 -*-
"""Память людей и связи между ними.

Подсистема отвечает на вопрос, которого летописи обычно не задают: что
этот человек пережил лично. Государь, у которого на чужой войне погиб
отец, и государь, у которого с той же державой связаны только выгодные
обозы, — это два разных государя, хотя держава у них одна.

Что здесь происходит:

1. **Запоминание.** Крупные события оставляют след не только на
   державах, но и на людях: гибель родича, плен, предательство союзника,
   победа, поражение, обойдённый престол.
2. **Связи.** Между людьми заводятся дружба, вражда, соперничество,
   долг, наставничество. Связь живёт: политика ссорит друзей, годы
   превращают вражду в холодное уважение.
3. **Забвение.** Память слабеет, но у разных людей по-разному:
   мстительный помнит обиду до могилы, не помнящий обид прощает за
   десять лет. Изредка память переиначивается — и человек помнит уже не
   то, что было.

Наружу подсистема отдаёт одно число — как этот человек относится к той
или иной стороне. Его читают поводы к войне, выбор жертвы, отношения
держав и, позже, заговоры.
"""

from __future__ import annotations

from .. import recall

# Сколько воспоминаний человек держит при себе: остальное стирается.
MEMORY_CAP = 14

# Кого помнят поимённо: у пастуха память тоже есть, но летопись её не ведёт.
NOTED_ROLES = ("правитель", "наследник", "полководец", "основатель страны",
               "глава дома", "чародей", "верховный жрец", "вождь восстания")

DRIFT_RATE = 0.12          # как часто связь меняется за десятилетие
TWIST_RATE = 0.05          # как часто воспоминание переиначивается за век


# ---------------------------------------------------------------------------
# Запоминание
# ---------------------------------------------------------------------------

def noted(figure) -> bool:
    """Стоит ли вести память этого человека."""
    if figure is None:
        return False
    if figure.noble or figure.house_id:
        return True
    return any(role in NOTED_ROLES for role in (figure.roles or ()))


def remember(ctx, figure, kind: str, year: int, about_id: str = "",
             weight: float = 1.0, event_id: str = "", place_id: str = "",
             note: str = "", told: bool = False):
    """Записать человеку воспоминание."""
    world = ctx.world
    if figure is None or not noted(figure):
        return None
    if figure.death is not None and figure.death.year < year:
        return None
    if figure.birth is not None and figure.birth.year > year:
        return None
    memory = world.add_memory(
        figure.id, kind, year, about_id=about_id,
        tone=recall.TONE.get(kind, "скорбь"),
        weight=max(0.1, min(1.0, float(weight))), event_id=event_id,
        place_id=place_id, note=note, told=told)
    _trim(world, figure, year)
    return memory


def _trim(world, figure, year: int) -> None:
    """Человек не помнит всего: слабое вытесняется сильным."""
    rows = world.memories_of(figure.id)
    if len(rows) <= MEMORY_CAP:
        return
    extra = sorted(rows, key=lambda item: (recall.power(item, year, figure),
                                           item.id))[:len(rows) - MEMORY_CAP]
    doomed = {item.id for item in extra}
    for memory_id in doomed:
        world.memories.pop(memory_id, None)
    kept = [item for item in world._memory_of.get(figure.id, ())
            if item not in doomed]
    world._memory_of[figure.id] = kept


def bind(ctx, first, second, kind: str, year: int, value: float = 0.0,
         note: str = ""):
    """Завязать связь между двумя людьми или укрепить прежнюю."""
    world = ctx.world
    if first is None or second is None or first.id == second.id:
        return None
    if not (noted(first) or noted(second)):
        return None
    bond = world.bond_between(first.id, second.id)
    if bond is not None:
        if bond.kind != kind:
            if not bond.turns:
                bond.turns.append([int(bond.since), bond.kind])
            bond.turns.append([int(year), kind])
            bond.kind = kind
        bond.value = max(-1.0, min(1.0, (bond.value + (value or
                                                       recall.BOND_SIGN.get(kind, 0.0))) / 2.0))
        bond.changed = int(year)
        if note:
            bond.note = note
        return bond
    return world.add_bond(first.id, second.id, kind, year,
                          value=value or recall.BOND_SIGN.get(kind, 0.0),
                          note=note)


# ---------------------------------------------------------------------------
# Кого это касается
# ---------------------------------------------------------------------------

def kin_of(world, figure, year: int) -> list:
    """Живая родня: отец, мать, супруг, дети, братья и сёстры."""
    out = []
    seen = set()

    def add(figure_id):
        if not figure_id or figure_id in seen:
            return
        seen.add(figure_id)
        other = world.figures.get(figure_id)
        if other is not None and other.id != figure.id and other.alive_at(year):
            out.append(other)

    add(figure.father_id)
    add(figure.mother_id)
    add(figure.spouse_id)
    for child_id in (figure.children or ()):
        add(child_id)
    father = world.figures.get(figure.father_id)
    if father is not None:
        for child_id in (father.children or ()):
            add(child_id)
    return out


# ---------------------------------------------------------------------------
# Что запоминают
# ---------------------------------------------------------------------------

def fallen(ctx, figure, foe_id: str, year: int, event_id: str = "",
           note: str = "") -> None:
    """Пал в бою — и с этого дня у его родни есть счёт к чужой державе."""
    if figure is None or not foe_id:
        return
    for relative in kin_of(ctx.world, figure, year):
        remember(ctx, relative, recall.KIN_DEATH, year, about_id=foe_id,
                 weight=0.95, event_id=event_id,
                 note=note or "гибель родича: %s" % figure.plain_name,
                 told=True)


def captured(ctx, figure, captor_id: str, year: int, event_id: str = "") -> None:
    if figure is None or not captor_id:
        return
    remember(ctx, figure, recall.CAPTIVITY, year, about_id=captor_id,
             weight=0.85, event_id=event_id, note="плен")


def war_result(ctx, war, winner, loser, year: int, event_id: str = "") -> None:
    """Государи и полководцы помнят свои войны поимённо."""
    world = ctx.world
    if winner is None or loser is None:
        return
    for polity, other, kind, weight in ((winner, loser, recall.VICTORY, 0.6),
                                        (loser, winner, recall.DEFEAT, 0.8)):
        ruler = world.figures.get(polity.ruler_id)
        remember(ctx, ruler, kind, year, about_id=other.id, weight=weight,
                 event_id=event_id, note="война по имени %s" % war.name,
                 told=True)
        side = (war.attacker_generals if polity.id == war.attacker_id
                else war.defender_generals)
        for figure_id in side[:3]:
            remember(ctx, world.figures.get(figure_id), kind, year,
                     about_id=other.id, weight=weight * 0.8,
                     event_id=event_id,
                     note="война по имени %s" % war.name)


def betrayed(ctx, wronged, breaker, year: int, event_id: str = "") -> None:
    """Не пришедшего на зов помнят дольше, чем врага."""
    world = ctx.world
    if wronged is None or breaker is None:
        return
    remember(ctx, world.figures.get(wronged.ruler_id), recall.BETRAYAL, year,
             about_id=breaker.id, weight=0.9, event_id=event_id,
             note="на зов о помощи не пришли", told=True)
    first = world.figures.get(wronged.ruler_id)
    second = world.figures.get(breaker.ruler_id)
    if first is not None and second is not None:
        bind(ctx, first, second, recall.B_TREASON, year, value=-0.8,
             note="нарушенное слово")


def passed_over(ctx, figure, chosen, year: int, event_id: str = "") -> None:
    """Обойдённый престолом помнит это до могилы."""
    if figure is None or chosen is None or figure.id == chosen.id:
        return
    remember(ctx, figure, recall.PASSED_OVER, year, about_id=chosen.id,
             weight=0.8, event_id=event_id, note="престол ушёл мимо")
    bind(ctx, figure, chosen, recall.B_RIVALRY, year, value=-0.45,
         note="спор о престоле")


# Когда престол «обходит» — то есть когда обойдённый считает себя
# обделённым, а не просто младшим родичем государя.
CONTESTED_LAWS = ("seniority", "council", "elective")
PASSED_CHANCE = 0.14


def rivals_passed(ctx, polity, heir, race, year: int, law: str = "") -> None:
    """Тот, мимо кого прошёл престол, — будущий заговорщик или мятежник.

    Обиженным себя считает не всякий родич: младший брат при законе
    первородства знает своё место. Другое дело — выборы, совет или
    старшинство: там престол мог достаться и тебе.
    """
    from .. import dynasty

    world = ctx.world
    if heir is None:
        return
    house = world.houses.get(polity.house_id)
    if house is None:
        return
    rng = ctx.rng("memory", "passed", polity.id, year)
    contested = (law or polity.succession or "") in CONTESTED_LAWS
    people = [figure for figure in dynasty.house_adults(world, house, race, year)
              if figure.id != heir.id]
    for other in people[:3]:
        older = (other.birth is not None and heir.birth is not None
                 and other.birth.year < heir.birth.year)
        if not contested and not older:
            continue
        if not rng.chance(PASSED_CHANCE + (0.16 if contested else 0.0)):
            continue
        passed_over(ctx, other, heir, year)
        return          # обойдённым себя чувствует один, а не всё семейство


def comrades(ctx, figures, year: int, warm: bool = True) -> None:
    """Пройденная вместе война связывает крепче любого договора."""
    world = ctx.world
    people = [world.figures.get(item) if isinstance(item, str) else item
              for item in figures]
    people = [item for item in people if item is not None
              and item.alive_at(year)]
    if len(people) < 2:
        return
    rng = ctx.rng("memory", "comrades", people[0].id, year)
    first, second = people[0], people[1]
    if not rng.chance(0.4):
        return
    if warm:
        bind(ctx, first, second, recall.B_FRIEND, year, value=0.55,
             note="война, пройденная вместе")
        remember(ctx, first, recall.FRIENDSHIP, year, about_id=second.id,
                 weight=0.6, note="боевой товарищ")
        remember(ctx, second, recall.FRIENDSHIP, year, about_id=first.id,
                 weight=0.6, note="боевой товарищ")
    else:
        bind(ctx, first, second, recall.B_RIVALRY, year, value=-0.3,
             note="спор о том, кто виноват в поражении")


def raised(ctx, figure, patron, year: int, note: str = "") -> None:
    """Возвышенный помнит, чьей рукой он поднят."""
    if figure is None or patron is None:
        return
    remember(ctx, figure, recall.GRATITUDE, year, about_id=patron.id,
             weight=0.75, note=note or "возвышение")
    bind(ctx, figure, patron, recall.B_DEBT, year, value=0.6,
         note=note or "возвышение")


def wedded(ctx, first, second, year: int, love: bool = False) -> None:
    """Брак: где по любви, где по расчёту, но связь остаётся."""
    if first is None or second is None:
        return
    kind = recall.B_LOVE if love else recall.B_RESPECT
    bind(ctx, first, second, kind, year, value=0.75 if love else 0.4,
         note="брак")
    # Отдельным воспоминанием брак ложится только у тех, чью жизнь
    # летопись и так ведёт: у прочих остаётся сама связь.
    crowned = any(role in ("правитель", "наследник")
                  for figure in (first, second)
                  for role in (figure.roles or ()))
    if love and crowned:
        for one, other in ((first, second), (second, first)):
            remember(ctx, one, recall.LOVE, year, about_id=other.id,
                     weight=0.8, note="брак")


def owed(ctx, figure, saviour, year: int, note: str = "") -> None:
    """Спасённый остаётся должен."""
    if figure is None or saviour is None:
        return
    remember(ctx, figure, recall.DEBT, year, about_id=saviour.id, weight=0.8,
             note=note or "спасение")
    bind(ctx, figure, saviour, recall.B_DEBT, year, value=0.6, note=note)


def taught(ctx, pupil, master, year: int, note: str = "") -> None:
    if pupil is None or master is None:
        return
    bind(ctx, pupil, master, recall.B_MENTOR, year, value=0.55,
         note=note or "учёба")


def dread(ctx, figure, about_id: str, year: int, note: str = "") -> None:
    if figure is None:
        return
    remember(ctx, figure, recall.FEAR, year, about_id=about_id, weight=0.7,
             note=note)


# ---------------------------------------------------------------------------
# Медленный такт: связи живут, память тускнеет и путается
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    if not world.bonds and not world.memories:
        return
    rng = ctx.rng("memory", "drift", year)
    _drift(ctx, world, rng, year, period)
    _twist(ctx, world, rng, year, period)


def _drift(ctx, world, rng, year: int, period: int) -> None:
    """Связи портятся и остывают — чаще всего из-за политики."""
    from .. import diplomacy as dip

    chance = min(0.5, DRIFT_RATE * period / 10.0)
    for bond in list(world.bonds.values()):
        if bond.ended:
            continue
        first = world.figures.get(bond.a_id)
        second = world.figures.get(bond.b_id)
        if first is None or second is None:
            continue
        if not first.alive_at(year) or not second.alive_at(year):
            bond.ended = year
            bond.end_reason = "смерть"
            continue
        if not rng.chance(chance):
            continue
        # Если их державы разошлись, разойдутся и они.
        pull = 0.0
        home_first = _home_polity(world, first)
        home_second = _home_polity(world, second)
        if home_first is not None and home_second is not None \
                and home_first.id != home_second.id:
            pull = dip.relation(home_first, home_second.id)
        shift = rng.uniform(-0.12, 0.12) + 0.25 * pull
        bond.value = max(-1.0, min(1.0, bond.value + shift))
        turned = ""
        if bond.value <= -0.35 and bond.kind in recall.SOURS:
            turned = recall.SOURS[bond.kind]
        elif bond.value >= 0.4 and bond.kind in recall.MELLOWS:
            turned = recall.MELLOWS[bond.kind]
        if turned and turned != bond.kind:
            if not bond.turns:
                bond.turns.append([int(bond.since), bond.kind])
            bond.turns.append([int(year), turned])
            bond.kind = turned
            bond.changed = int(year)


def _home_polity(world, figure):
    settlement = world.settlements.get(figure.home_id)
    if settlement is not None:
        return world.polities.get(settlement.polity_id)
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if polity.ruler_id == figure.id:
            return polity
    return None


def _twist(ctx, world, rng, year: int, period: int = 10) -> None:
    """Память переиначивается: со временем обида растёт, а вина тускнеет."""
    for memory in list(world.memories.values()):
        if memory.twisted or year - memory.year < 30:
            continue
        # Считаем на век, а не на десятилетие: иначе у долгоживущих
        # народов к старости переиначивается вся память до единого
        # воспоминания.
        if not rng.chance(TWIST_RATE * period / 100.0):
            continue
        figure = world.figures.get(memory.figure_id)
        if figure is None or not figure.alive_at(year):
            continue
        memory.twisted = True
        memory.weight = min(1.0, memory.weight * 1.2)
