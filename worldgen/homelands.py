# -*- coding: utf-8 -*-
"""Какие гексы держава хочет, а какие берёт нехотя.

Без этого границы на карте ложились лентами: волна расселения шла по
самой дешёвой дороге — вдоль рек и по равнинам — и держава дворфов
вытягивалась через степь на пол-материка, потому что по степи идти
легче, чем по своим же горам.

Здесь считается **желание**: насколько эта земля своя для этого народа.
Дворф лезет в горы и в ближние долины и не идёт в болото; эльф держится
леса; человек берёт всё, где родится хлеб. Цена шага на карте делится на
желание — и чужая земля обходится державе втрое-впятеро дороже. Поэтому
нежеланные гексы остаются серыми, пока держава не вырастет настолько,
чтобы дотянуться и до них.

Числа подбирались по виду карты: при меньшем разбросе ленты остаются,
при большем державы съёживаются в пятна размером с город.
"""

from __future__ import annotations

from . import races as races_mod

# Насколько дороже чужая земля. Ниже — мягче границы, выше — резче.
ALIEN = 0.28              # желание для местности, которой нет в списке расы
RANK_STEP = 0.14          # насколько слабее желание с каждым местом в списке
FERTILE_PULL = 0.55       # сколько добавляет плодородие тем, кто пашет
RIVER_PULL = 0.18         # река тянет всех
HARSH = 0.55              # лёд, голые скалы и пески не хочет почти никто

# Кто живёт с земли, а кто с камня. Пахарям плодородие важнее местности,
# горнякам — наоборот: голая скала с рудой лучше сытого луга.
TILLERS = frozenset((races_mod.PLAIN, races_mod.STEPPE, races_mod.HILLS,
                     races_mod.COAST, races_mod.FOREST, races_mod.JUNGLE))
DIGGERS = frozenset((races_mod.MOUNTAIN, races_mod.UNDERGROUND))

# Местности, в которые почти никто не лезет по доброй воле.
BLEAK = frozenset((races_mod.TUNDRA, races_mod.DESERT))


def desire(race, terrain: str, fertility: float = 0.0,
           river: bool = False) -> float:
    """Насколько народ хочет этот гекс, 0…1.

    Ноль не возвращается никогда: любую землю можно занять, вопрос цены.
    """
    if race is None:
        return 0.5
    order = race.terrains or ()
    if terrain in order:
        rank = order.index(terrain)
        value = max(0.30, 1.0 - RANK_STEP * rank)
    else:
        value = ALIEN

    # Плодородие тянет тех, кто кормится с земли; горнякам оно безразлично.
    if terrain in TILLERS and order and order[0] in TILLERS:
        value += FERTILE_PULL * max(0.0, min(1.0, fertility))
    if river:
        value += RIVER_PULL

    # Лёд и пески отталкивают всех, кроме тех, кто ими и живёт.
    if terrain in BLEAK and (not order or order[0] not in BLEAK):
        value *= HARSH

    return max(0.08, min(1.6, value))


def cost_scale(race, terrain: str, fertility: float = 0.0,
               river: bool = False) -> float:
    """Во сколько раз дороже обходится державе шаг в эту землю."""
    return 1.0 / desire(race, terrain, fertility, river)


__all__ = ["desire", "cost_scale", "ALIEN"]
