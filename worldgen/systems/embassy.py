# -*- coding: utf-8 -*-
"""Посольства: переговоры между дворами и их последствия.

Договоры до сих пор заключались сами собой — отношение доросло, и бумагу
подписали. Здесь между отношением и бумагой встаёт человек: посол с
именем, со свитой и с наказом. Его принимают или выставляют, ему верят
или смеются в лицо, и изредка его убивают — а кровь посла помнят дольше
любой спорной межи и припоминают при объявлении войны.

Посольство даёт истории то, чего не даёт голая дипломатия: имена,
поступки и обиды, у которых есть виновник.
"""

from __future__ import annotations

from . import diplomacy as dip_system
from . import war as war_system
from .. import diplomacy as dip
from .. import embassy as emb
from .. import narrative
from .. import narrative_embassy as texts
from .. import races as races_mod
from ..models import ACTIVE

EMBASSY_RATE = 0.30         # шанс, что держава за такт снарядит посольство
WAR_TALK_RATE = 0.45        # и шанс, что воюющая пошлёт его к врагу
MAX_PER_TICK = 16           # чтобы мир из сотни держав не утонул в посольствах
GIFT_CHANCE = 0.72
TRIBUTE_YEARS = 60


# ---------------------------------------------------------------------------
# Десятилетний такт
# ---------------------------------------------------------------------------

def upkeep(ctx, year: int, period: int) -> None:
    world = ctx.world
    rng = ctx.rng("embassy", year)
    owners = {}
    for polity_id in world.active_polities:
        for region_id in world.polities[polity_id].region_ids:
            owners.setdefault(region_id, []).append(polity_id)

    senders = []
    for polity_id in world.active_polities:
        polity = world.polities[polity_id]
        if polity.status != ACTIVE or polity.interregnum:
            continue
        race = races_mod.get_race(polity.race_id)
        if not race.builds_states or race.is_evil:
            continue
        if not polity.ruler_id:
            continue
        senders.append(polity)
    if not senders:
        return

    # Порядок перемешиваем: иначе посольства всегда снаряжали бы одни и
    # те же державы — те, что записаны в базу первыми.
    for polity in rng.shuffled(senders)[:MAX_PER_TICK * 3]:
        # Воюющий двор прежде всего шлёт послов к врагу: пока идёт война,
        # посольство — единственный способ её прекратить.
        foe = _enemy(world, polity, rng)
        if foe is not None and rng.chance(WAR_TALK_RATE * (period / 10.0)):
            _send(ctx, polity, foe, year, rng)
            continue
        if not rng.chance(EMBASSY_RATE * (period / 10.0)):
            continue
        host = _target(ctx, polity, year, rng, owners)
        if host is None:
            continue
        _send(ctx, polity, host, year, rng)


def _enemy(world, polity, rng):
    """Тот, с кем эта держава воюет прямо сейчас."""
    options = []
    for fight in world.wars_of(polity, only_active=True):
        if polity.id in fight.attacker_allies or fight.defender_id == polity.id:
            foe_id = fight.attacker_id
        else:
            foe_id = fight.defender_id
        foe = world.polities.get(foe_id)
        if foe is None or foe.status != ACTIVE or foe.id == polity.id:
            continue
        if not foe.ruler_id:
            continue
        options.append(foe)
    if not options:
        return None
    return rng.choice(sorted(options, key=lambda p: p.id))


def _target(ctx, sender, year: int, rng, owners):
    """К какому двору поедет посольство.

    К врагу едут чаще, чем к другу: на войне посольство — единственный
    способ её прекратить. К соседу — чаще, чем к дальней державе, о
    которой при дворе и не слышали.
    """
    world = ctx.world
    options = []
    for other in dip_system.circle(ctx, world, sender, year, owners):
        if other.status != ACTIVE or not other.ruler_id:
            continue
        relation = dip.relation(sender, other.id)
        weight = 1.0
        if world.war_between(sender.id, other.id) is not None:
            weight = 12.0      # на войне посольство — дело первое
        elif world.pact_between(sender.id, other.id) is not None:
            weight = 1.6
        weight *= 1.0 + 0.6 * abs(relation)
        options.append((other, weight))
    if not options:
        return None
    return rng.weighted(options)


# ---------------------------------------------------------------------------
# Посольство
# ---------------------------------------------------------------------------

def _send(ctx, sender, host, year: int, rng) -> None:
    world = ctx.world
    fight = world.war_between(sender.id, host.id)
    purpose = emb.choose(rng, ctx, sender, host, fight is not None)
    envoy = _envoy(ctx, sender, year, rng)
    if envoy is None:
        return
    gift = emb.gift_for(rng, world, sender) if rng.chance(GIFT_CHANCE) else ""

    date = ctx.date_in(rng, year)
    record = world.add_embassy(
        sender_id=sender.id, host_id=host.id, envoy_id=envoy.id, sent=date,
        purpose=purpose.key, gift=gift)
    title, text = texts.embassy_sent(rng, sender, host, envoy, purpose, gift)
    world.add_event(
        date=date, era_index=world.era_index_at(year), kind="embassy",
        title=title, text=text, importance=1,
        actors=[envoy.id], subjects=[record.id, sender.id, host.id],
        region_id=sender.region_ids[0] if sender.region_ids else "",
        race_id=sender.race_id)

    answer = emb.verdict(rng, world, sender, host, purpose, bool(gift),
                         _envoy_skill(envoy))
    record.answer = answer
    back = ctx.date_in(rng, year, date)
    record.returned = back

    note = _settle(ctx, record, sender, host, envoy, purpose, answer, year,
                   back, rng, fight)
    title, text = texts.embassy_answer(rng, sender, host, envoy, purpose, answer)
    if note:
        text = "%s %s" % (text, note)
    world.add_event(
        date=back, era_index=world.era_index_at(year), kind="embassy_answer",
        title=title, text=text,
        importance={emb.ACCEPT: 2, emb.REFUSE: 1, emb.INSULT: 2,
                    emb.BLOOD: 4}[answer],
        actors=[envoy.id], subjects=[record.id, sender.id, host.id],
        region_id=host.region_ids[0] if host.region_ids else "",
        race_id=sender.race_id)


def _envoy(ctx, sender, year: int, rng):
    """Кого посылают: своего знатного человека или доверенного простолюдина.

    Сперва смотрят на знать — посольство и есть то дело, ради которого
    младших сыновей держат при дворе. Нового человека заводят, только
    если посылать некого: чужаков в чужой род не вписывают.
    """
    world = ctx.world
    race = races_mod.get_race(sender.race_id)
    ready = []
    for house in world.houses_of_polity(sender):
        if house.status != ACTIVE:
            continue
        for figure in world.house_members(house, alive_in_year=year):
            if figure.id == sender.ruler_id:
                continue
            if figure.age_at(year) < race.adulthood:
                continue
            if "правитель" in figure.roles or "посол" in figure.roles:
                continue
            ready.append(figure)
    if ready:
        envoy = rng.choice(sorted(ready, key=lambda f: f.id))
        envoy.roles.append("посол")
        return envoy

    sex = "f" if rng.chance(0.38) else "m"
    return ctx.make_figure(
        rng, race, year, role="посол",
        region_id=sender.region_ids[0] if sender.region_ids else "",
        title="посол" if sex == "m" else "посланница", sex=sex,
        home_id=sender.id, epithet_chance=0.5,
        folk=world.folks.get(_folk_of(world, sender)))


def _folk_of(world, polity) -> str:
    settlement = world.settlements.get(polity.capital_id)
    return settlement.folk_id if settlement is not None else ""


def _envoy_skill(envoy) -> float:
    """Умение посла: у знатного и примеченного речь складнее."""
    value = 5.0 + (1.2 if envoy.noble else 0.0)
    if envoy.epithet:
        value += 0.6
    return value


# ---------------------------------------------------------------------------
# Что выходит из ответа
# ---------------------------------------------------------------------------

def _settle(ctx, record, sender, host, envoy, purpose, answer: str, year: int,
            date, rng, fight) -> str:
    world = ctx.world
    shift = emb.RELATION_SHIFT[answer]
    dip.set_relation(sender, host, dip.relation(sender, host.id) + shift)

    if answer == emb.BLOOD:
        world.schedule_death(envoy, date,
                             narrative.fate(("убит при чужом дворе",
                                             "убита при чужом дворе"),
                                            envoy.sex))
        world.add_grudge(sender, host.id, "envoy", year)
        return ""
    if answer == emb.INSULT:
        world.add_grudge(sender, host.id, "insult", year)
        return ""
    if answer == emb.REFUSE:
        return ""

    envoy.roles.append("посол, добившийся своего")
    return _reward(ctx, record, sender, host, purpose, year, date, rng, fight)


def _reward(ctx, record, sender, host, purpose, year: int, date, rng,
            fight) -> str:
    """Согласие двора переводится на язык мира: договор, дань, мир, помощь."""
    world = ctx.world
    key = purpose.key

    if key == "мир" and fight is not None:
        war_system.sue_for_peace(ctx, fight, year,
                                 "Мир выговорило посольство, а не войско.")
    elif key in ("союз", "торг", "брак", "межа"):
        kind = {"союз": dip.ALLIANCE, "торг": dip.TRADE,
                "брак": dip.MARRIAGE, "межа": dip.TRUCE}[key]
        if world.pact_between(sender.id, host.id) is None \
                and world.war_between(sender.id, host.id) is None:
            reasons = [("слово посла", 0.5)]
            pact = dip_system.make_pact(ctx, kind, sender, host, reasons,
                                        year, rng)
            if pact is not None:
                record.pact_id = pact.id
    elif key == "дань":
        host.tribute_to = sender.id
        host.tribute_until = year + TRIBUTE_YEARS
    elif key == "покорность":
        host.overlord_id = sender.id
        host.tribute_to = sender.id
        host.tribute_until = year + TRIBUTE_YEARS
    elif key == "помощь":
        _join_war(ctx, sender, host, year)
    elif key == "вера" and host.faith_id and sender.faith_id:
        # Гонения прекращают — обида притесняемых спадает.
        race = sender.race_id
        if race in host.grievance:
            host.grievance[race] = max(0.0, host.grievance[race] - 0.3)

    return texts.gain_note(rng, key)


def _join_war(ctx, sender, host, year: int) -> None:
    """Союзник, которого выпросило посольство, входит в чужую войну."""
    world = ctx.world
    for fight in world.wars_of(sender):
        if fight.end is not None:
            continue
        side = (fight.attacker_allies if fight.attacker_id == sender.id
                else fight.defender_allies)
        foe_id = (fight.defender_id if fight.attacker_id == sender.id
                  else fight.attacker_id)
        if host.id == foe_id or host.id in side:
            continue
        other = (fight.defender_allies if fight.attacker_id == sender.id
                 else fight.attacker_allies)
        if host.id in other:
            continue
        side.append(host.id)
        if fight.id not in host.war_ids:
            host.war_ids.append(fight.id)
        return


# ---------------------------------------------------------------------------
# Повод к войне из обиды
# ---------------------------------------------------------------------------

def forget_dead(world) -> None:
    """Обиды на исчезнувшие державы держать незачем."""
    for polity in world.polities.values():
        for other_id in list(polity.grudges):
            if other_id not in world.polities:
                del polity.grudges[other_id]


__all__ = ["upkeep", "forget_dead"]
