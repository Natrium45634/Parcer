# -*- coding: utf-8 -*-
"""Пять эпох мира и их границы.

Эпохи задают «правила игры» для каждого отрезка истории: в Эпоху Сотворения
существуют только племена, страны появляются лишь в Эпоху Мифов, а к Эпохе
Железа мир заселён плотно. Конец каждой эпохи отмечен большим событием —
катастрофой, войной или уходом древних сил.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import EraSpan


@dataclass(frozen=True)
class EraSpec:
    key: str
    name: str
    share: float              # доля от всей истории
    description: str
    allow_settlements: bool
    allow_polities: bool
    tribe_rate: float         # шанс появления нового племени за год
    settle_rate: float        # шанс, что племя осядет и построит поселение
    colony_rate: float        # шанс основания нового города страной
    polity_rate: float        # шанс рождения новой страны
    camp_rate: float          # шанс появления лагеря злой расы
    turmoil: float            # общий фон бедствий
    end_titles: tuple         # чем может закончиться эпоха
    tone: str = ""


ERA_SPECS = (
    EraSpec(
        key="creation",
        name="Эпоха Сотворения",
        share=0.08,
        description=(
            "Мир юн, земли безымянны. Первые народы пробуждаются и бродят по "
            "нетронутым землям, не зная ни городов, ни границ."
        ),
        allow_settlements=False,
        allow_polities=False,
        tribe_rate=0.120,
        settle_rate=0.0,
        colony_rate=0.0,
        polity_rate=0.0,
        camp_rate=0.004,
        turmoil=0.25,
        tone="первозданная",
        end_titles=(
            "Уход Творцов",
            "Угасание Первого Пламени",
            "Раскол Первозданной Тверди",
            "Последний Вздох Творения",
            "Затворение Небесных Врат",
        ),
    ),
    EraSpec(
        key="gods",
        name="Эпоха Богов",
        share=0.14,
        description=(
            "Боги ходят по земле и говорят со смертными. Племена учатся "
            "строить, и первые каменные стены поднимаются над стоянками."
        ),
        allow_settlements=True,
        allow_polities=False,
        tribe_rate=0.100,
        settle_rate=0.014,
        colony_rate=0.004,
        polity_rate=0.0,
        camp_rate=0.012,
        turmoil=0.35,
        tone="божественная",
        end_titles=(
            "Война Богов",
            "Низвержение Пантеона",
            "Молчание Небес",
            "Падение Небесного Столпа",
            "Раздел Божественного Наследия",
        ),
    ),
    EraSpec(
        key="myths",
        name="Эпоха Мифов",
        share=0.20,
        description=(
            "Век чудовищ, драконов и великих чудес. Из союзов городов "
            "рождаются первые страны, а границы впервые наносят на карты."
        ),
        allow_settlements=True,
        allow_polities=True,
        tribe_rate=0.070,
        settle_rate=0.024,
        colony_rate=0.010,
        polity_rate=0.0060,
        camp_rate=0.020,
        turmoil=0.45,
        tone="мифическая",
        end_titles=(
            "Гибель Последнего Дракона",
            "Падение Великого Древа",
            "Погребение Титанов",
            "Исход Чудовищ",
            "Ночь Павших Звёзд",
        ),
    ),
    EraSpec(
        key="heroes",
        name="Эпоха Героев",
        share=0.26,
        description=(
            "Время имён и подвигов. Короли собирают дружины, герои идут "
            "в проклятые земли, а летописцы едва успевают записывать."
        ),
        allow_settlements=True,
        allow_polities=True,
        tribe_rate=0.045,
        settle_rate=0.030,
        colony_rate=0.026,
        polity_rate=0.0120,
        camp_rate=0.025,
        turmoil=0.55,
        tone="героическая",
        end_titles=(
            "Битва Тысячи Знамён",
            "Смерть Последнего Героя",
            "Разлом Клятв",
            "Ночь Погасших Клинков",
            "Великое Предательство",
        ),
    ),
    EraSpec(
        key="iron",
        name="Эпоха Железа",
        share=0.32,
        description=(
            "Чудеса отступают, остаются железо, договоры и расчёт. Мир плотно "
            "заселён, и каждая пядь земли кому-то принадлежит."
        ),
        allow_settlements=True,
        allow_polities=True,
        tribe_rate=0.035,
        settle_rate=0.028,
        colony_rate=0.034,
        polity_rate=0.0125,
        camp_rate=0.025,
        turmoil=0.60,
        tone="железная",
        end_titles=(
            "Летопись обрывается на полуслове",
            "Последняя запись хрониста",
        ),
    ),
)

ERA_COUNT = len(ERA_SPECS)


def build_eras(rng, total_years: int) -> list:
    """Делит историю на пять эпох с небольшим случайным разбросом границ."""
    total_years = max(ERA_COUNT * 5, int(total_years))

    weights = []
    for spec in ERA_SPECS:
        weights.append(max(0.02, rng.jitter(spec.share, 0.18)))
    scale = sum(weights)

    lengths = []
    for weight in weights:
        lengths.append(max(5, int(round(total_years * weight / scale))))

    # Подгоняем сумму ровно под заданное число лет.
    drift = total_years - sum(lengths)
    index = 0
    while drift != 0:
        step = 1 if drift > 0 else -1
        position = index % ERA_COUNT
        if lengths[position] + step >= 5:
            lengths[position] += step
            drift -= step
        index += 1

    spans = []
    start = 1
    for i, spec in enumerate(ERA_SPECS):
        end = start + lengths[i] - 1
        spans.append(EraSpan(
            index=i,
            key=spec.key,
            name=spec.name,
            start_year=start,
            end_year=end,
            description=spec.description,
        ))
        start = end + 1
    return spans


def spec_for(index: int) -> EraSpec:
    return ERA_SPECS[max(0, min(ERA_COUNT - 1, index))]
