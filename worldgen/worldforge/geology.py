# -*- coding: utf-8 -*-
"""Недра Worldforge: руды, самоцветы и сказочные металлы.

Залежи не рассыпаны по карте ровным слоем. У каждого семейства руд своё
низкочастотное поле — металлогенический пояс: один край мира богат
золотом, другой пуст, как оно и бывает на самом деле. Внутри пояса
залежь бросается по гексу: есть ли она вообще, насколько велика, какова
руда и легко ли к ней подступиться.

Магматические провинции (свёрнутое напряжение плит плюс близость
вулканов) добавляют к этому порфировую медь, молибден и жильное золото.
"""

from __future__ import annotations


from array import array

from .rng import make_noise, rng_from

SIZE_NAMES = ('ничтожные следы', 'следы', 'скудные залежи',
              'умеренные залежи', 'значительные залежи', 'богатые залежи',
              'огромные запасы')
GRADE_NAMES = ('бедная руда', 'рядовая руда', 'богатая руда')

# Поля металлогенических поясов считаются по сиду мира, и хранить их
# стоит только для того мира, который сейчас на руках: иначе за сеанс с
# десятком карт в памяти копятся десятки полей шума.
_PROV_CACHE = {"seed": None, "fields": {}}


def ore_province(world, family: str, c: int, r: int) -> float:
    """Насколько богат этим семейством руд здешний край."""
    seed = world.cfg.seed
    if _PROV_CACHE["seed"] != seed:
        _PROV_CACHE["seed"] = seed
        _PROV_CACHE["fields"] = {}
    field = _PROV_CACHE["fields"].get(family)
    if field is None:
        field = make_noise(rng_from("%s:prov:%s" % (seed, family)))
        _PROV_CACHE["fields"][family] = field
    v = (field(c * 0.016, r * 0.016, 3.7) * 0.72
         + field(c * 0.055, r * 0.055, 8.1) * 0.28)
    return (max(0.0, v + 0.65) ** 3) * 1.4


def minerals_at(world, i: int) -> list:
    """Список залежей этого гекса — от следов до огромных запасов."""
    if world.is_ocean[i]:
        return []
    W = world.W
    c, r = i % W, i // W
    rng = rng_from("%s:min:%d" % (world.cfg.seed, i))
    meters = max(0.0, world.elev_to_m(world.elev[i]))
    conv = world.stress[i]
    b = world.biome[i]
    hills, mtn, deep = meters > 500, meters > 1500, meters > 3500
    orog = conv > 0.3
    volc = world.dist_v[i] < 6
    arid = world.moist[i] < 0.24
    wet = world.moist[i] > 0.6
    craton = (world.continental[i] > 0.7 and abs(conv) < 0.18 and not mtn)
    sl = 0.0
    for j in world.neighbors(i):
        sl += abs(world.elev[j] - world.elev[i])
    sl /= 6
    flat_low = meters < 400 and sl < 0.02
    sed_forest = (17 <= b <= 21) or b in (10, 36, 38)
    placer = False
    for j in world.neighbors(i):
        if world.is_river[j] and meters < 900:
            placer = True
            break
    dry_lake = False
    for j in world.neighbors(i):
        if world.is_lake[j] and arid:
            dry_lake = True
            break
    salt_flat = b == 30
    out = []

    def dig(name, p, family=None, bias=0.0, gem=False, mat=False,
            access=None, placerable=False, imps=(), gbias=0.0):
        if len(out) >= 8:
            return
        pm = ore_province(world, family, c, r) if family else 1.0
        if rng() >= min(0.97, p * (0.30 + pm * 0.9)):
            return
        q = rng() * 0.5 + pm * 0.38 + bias
        size = (6 if q > 1.32 else 5 if q > 1.02 else 4 if q > 0.76
                else 3 if q > 0.54 else 2 if q > 0.34 else 1 if q > 0.18 else 0)
        if gem:
            g = rng() + pm * 0.14
            grade = ('высокая чистота' if g > 1.1
                     else 'обычное качество' if g > 0.6 else 'низкое качество')
        elif mat:
            g = rng() + pm * 0.10
            grade = ('высокого качества' if g > 1.05
                     else 'обычного качества' if g > 0.5
                     else 'низкого качества')
        else:
            g = rng() + pm * 0.14 + gbias
            grade = GRADE_NAMES[2 if g > 1.05 else 1 if g > 0.55 else 0]
        acc = access
        if not acc:
            if placer and placerable and rng() < 0.6:
                acc = 'россыпь, добыча легка'
            elif flat_low:
                acc = 'у поверхности'
            elif mtn:
                acc = 'глубокие жилы'
            elif hills:
                acc = 'штольни'
            else:
                acc = 'неглубоко'
        found = []
        for im_name, im_p in imps:
            if rng() < im_p * (0.6 + pm * 0.5):
                found.append(im_name)
        sub = (grade + ' · ' if size > 0 else '') + acc
        if found:
            sub += ' · примеси: ' + ', '.join(found)
        out.append({"n": name, "lv": SIZE_NAMES[size], "sub": sub})

    dig('Железная руда', (0.5 if mtn else 0.32 if hills else 0.08)
        + (0.18 if orog else 0), family='iron', bias=0.08,
        imps=(('марганец', 0.20), ('никель', 0.10)))
    dig('Медная руда', (0.34 if mtn else 0.18 if hills else 0.04)
        + (0.12 if orog else 0) + (0.2 if volc else 0), family='copper',
        imps=(('серебро', 0.28), ('золото', 0.12), ('мышьяк', 0.16)))
    dig('Оловянная руда', (0.17 if mtn else 0.03) + (0.08 if orog else 0),
        family='tin', imps=(('вольфрам', 0.18),))
    dig('Свинцово-цинковая руда', (0.15 if mtn else 0.07 if hills else 0.02),
        family='leadzinc', imps=(('серебро', 0.45), ('кадмий', 0.10)))
    dig('Серебро', (0.10 if mtn else 0.015) + (0.13 if volc else 0),
        family='silver')
    dig('Золото', (0.08 if mtn else 0.012) + (0.11 if volc else 0)
        + (0.13 if placer else 0) + (0.05 if craton else 0), family='gold',
        placerable=True, imps=(('платина', 0.10), ('серебро', 0.22)))
    if craton and placer:
        dig('Платина', 0.05, family='gold', placerable=True, bias=-0.1)
    dig('Алмазы', 0.07 if craton else 0.004, family='gems', gem=True,
        access='кимберлитовые трубки' if craton else 'аллювий', bias=-0.18)
    dig('Изумруды', 0.06 if (mtn and orog) else 0.004, family='gems',
        gem=True, bias=-0.12)
    dig('Рубины и сапфиры', (0.07 if (mtn and orog) else 0.004)
        + (0.04 if deep else 0), family='gems', gem=True, bias=-0.12)
    dig('Аметисты и агаты', 0.16 if volc else 0.02, family='gems', gem=True)
    dig('Опалы', 0.06 if (arid and hills) else 0.005, family='gems', gem=True)
    dig('Гранаты', 0.10 if mtn else 0.015, family='gems', gem=True)
    dig('Топазы и бериллы', 0.06 if (mtn and orog) else 0.006, family='gems',
        gem=True)
    if volc:
        dig('Сера', 0.5, bias=0.15, mat=True, access='фумарольные поля')
        dig('Обсидиан', 0.42, mat=True, access='у поверхности')
    dig('Каменный уголь', (0.45 if (flat_low and sed_forest)
                           else 0.10 if flat_low else 0.02), family='coal',
        bias=0.1, mat=True,
        access='пласты у поверхности' if flat_low else 'глубокие пласты')
    if b == 38:
        dig('Бурый уголь и торф', 0.5, bias=0.1, mat=True,
            access='открытая добыча')
    dig('Каменная соль', (0.85 if salt_flat else 0) + (0.25 if arid else 0)
        + (0.30 if dry_lake else 0.01), family='salt',
        bias=0.3 if salt_flat else 0.05, mat=True, access='соляные пласты')
    dig('Гипс', 0.22 if (arid and flat_low) else 0.02, mat=True)
    dig('Мрамор', 0.13 if (mtn and orog) else 0.01, mat=True)
    dig('Строительный камень', 0.55 if (mtn or hills) else 0.22, bias=0.1,
        mat=True, access='каменоломни')
    dig('Глина', (0.42 if (flat_low or wet) else 0.08)
        + (0.25 if b in (10, 38) else 0), mat=True, access='открытая добыча')
    dig('Селитра', 0.12 if (arid and hills) else 0.02, mat=True)
    dig('Мифрил', (0.02 if (deep and orog) else 0)
        + (0.012 if (volc and mtn) else 0), family='myth', bias=0.3,
        access='очень глубокие жилы')
    dig('Адамантин', 0.009 if (deep and orog) else 0, family='myth',
        bias=0.4, access='бездонные копи')
    dig('Звёздный металл', 0.006 if volc else 0.0015, bias=0.4,
        access='метеоритные поля')
    if not out:
        out.append({"n": 'Обычные породы и грунт', "lv": '', "sub": ''})
    return out


# ---------------------------------------------------------------------------
# Магматические провинции
# ---------------------------------------------------------------------------

def magma_field(world):
    """Свёрнутое напряжение плит плюс близость вулканов.

    Поле считается один раз и живёт на самом мире: привязывать кэш к
    адресу объекта нельзя — освобождённый мир отдаёт свой адрес
    следующему, и тот получил бы чужие провинции.
    """
    field = getattr(world, "_magma_field", None)
    if field is not None:
        return field
    n = world.W * world.H
    conv = array('f', [0.0]) * n
    for i in range(n):
        conv[i] = max(0.0, world.stress[i])
    for _ in range(3):
        tmp = conv[:]
        for i in range(n):
            s = tmp[i] * 2
            count = 2
            for j in world.neighbors(i):
                s += tmp[j]
                count += 1
            conv[i] = s / count
    field = array('f', [0.0]) * n
    for i in range(n):
        mp = conv[i] * 1.4
        dv = world.dist_v[i]
        if dv < 12:
            mp += (12 - dv) / 12 * 0.9
        field[i] = max(0.0, min(1.6, mp))
    world._magma_field = field
    return field


def minerals_with_magma(world, i: int, field) -> list:
    """Те же недра плюс порфировые пояса магматических провинций."""
    out = minerals_at(world, i)
    if world.is_ocean[i]:
        return out
    magma = field[i]
    if magma > 0.55:
        rng = rng_from("%s:magma:%d" % (world.cfg.seed, i))
        m = world.elev_to_m(world.elev[i])
        mtn, hills = m > 1400, m > 400
        if (hills or mtn) and rng() < 0.30 + (0.18 if mtn else 0):
            has_copper = any(('Мед' in item["n"]) or ('мед' in item["n"])
                             for item in out)
            if not has_copper:
                out.append({"n": 'Медная руда (порфировая)',
                            "lv": ('богатые залежи' if magma > 1.0
                                   else 'жилы'),
                            "sub": 'магматический пояс · спутники: золото, '
                                   'молибден'})
            if rng() < 0.45:
                out.append({"n": 'Молибденовая руда', "lv": 'штокверки',
                            "sub": 'порфировая система'})
            if rng() < 0.40:
                out.append({"n": 'Золото (жильное)',
                            "lv": 'гидротермальные жилы',
                            "sub": 'эпитермальное, магматическое'})
        if rng() < 0.18:
            out.append({"n": 'Серебро', "lv": 'жилы',
                        "sub": 'гидротермальное'})
        if magma > 1.0 and rng() < 0.14:
            out.append({"n": 'Самоцветы (аметист, топаз)', "lv": 'миаролы',
                        "sub": 'магматические пустоты'})
    return out


def minerals_json(world) -> dict:
    """Секция недр для .world: только настоящие залежи, без пустой породы."""
    field = magma_field(world)
    out = {}
    for i in range(world.W * world.H):
        if world.is_ocean[i]:
            continue
        found = [[item["n"], item["lv"]]
                 for item in minerals_with_magma(world, i, field)
                 if item["n"] != 'Обычные породы и грунт' and item["lv"]]
        if found:
            out[str(i)] = found
    return out
