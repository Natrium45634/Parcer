# -*- coding: utf-8 -*-
"""Живая карта мира: графика картогенератора плюс вся история места.

Карта должна выглядеть так же, как страница картогенератора, с которой
начался этот проект: настоящие гексы, тот же цвет биома, реки нитками,
подписи морей и материков, вершины и вулканы значками. И при этом
отвечать на год: кто владел этой землёй, какой город тут стоял, что
здесь случилось.

**Как это нарисовано и почему так.** Гексов на большой карте полтораста
тысяч; рисовать их фигурами холста нельзя — окно встанет. Поэтому карта
собирается в картинку по точкам, в байтовый буфер, и уходит в Tk одним
куском как PPM: на окно в тысячу четыреста на девятьсот это четырнадцать
миллисекунд вместо секунды, которую съедала склейка миллиона строк
«#rrggbb».

Дальше главное: **вся карта рисуется один раз** на «своём» размере
гекса (`native`), а мельче получается уменьшением силами Tk — это
работа на языке C, десять миллисекунд. Поэтому прокрутка и приближение
на обзорных размерах ничего не считают заново: картинка уже есть.
Крупнее своего размера гексов в окне мало, и там карта рисуется прямо,
с запасом вокруг окна, — чтобы небольшая прокрутка снова была даром.

Значков поверх картинки сотни, а не тысячи: города, вершины, подписи,
выбранный гекс. Они живут фигурами холста, по ним можно щёлкать, и при
перетаскивании они едут вместе с картинкой одной командой.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from worldgen import worldmap as wm
from worldgen.mapregions import FEATURE_NOUNS, translit
from worldgen.worldforge import BIOME_COLORS, BIOME_NAMES

# Пропорции остроконечного гекса: высота к ширине и шаг между рядами.
HEX_TALL = 1.1547            # 2/√3
ROW_STEP = 0.8660            # √3/2

# Своим размером гекса зовётся тот, на котором рисуется вся карта разом.
# Двенадцать точек — гекс, в котором видно и форму, и реку; но на карте
# в полтораста тысяч гексов такая картинка занимает под сотню мегабайт,
# поэтому для больших карт свой размер меньше.
NATIVE_CHOICES = (24, 12, 6, 4)
NATIVE_BUDGET = 10_000_000    # точек в картинке всей карты
DIRECT_MARGIN = 220           # запас вокруг окна: чем больше, тем
                              # реже приходится резать заново

GRID_BG = "#0d1016"
WATER_DIM = "#16202c"
LAND_DIM = "#2e3330"
BORDER_INK = "#14110c"
RIVER_INK = "#3f8ecd"

MODES = (
    ("Биомы", "biome"),
    ("Рельеф", "relief"),
    ("Державы по годам", "realm"),
    ("Земли истории", "region"),
    ("Плодородие", "fert"),
    ("Дикость округи", "wild"),
    ("Магия", "magic"),
    ("Опасности", "risk"),
    ("Высоты", "elev"),
    ("Тепло", "temp"),
    ("Влага", "moist"),
    ("Литоплиты", "plates"),
)

# Подписи к шкалам: что значит цвет. Показываются под выбором слоя.
LEGENDS = {
    "fert": (("#3a3326", "камень"), ("#6b8f45", "средняя земля"),
             ("#8fd15a", "чернозём")),
    "wild": (("#2f3a34", "кроткое"), ("#7a4a30", "вольное"),
             ("#c0552f", "лютое")),
    "magic": (("#c8283c", "злая"), ("#1a1d16", "тихо"),
              ("#5ad2aa", "добрая")),
    "risk": (("#243042", "спокойно"), ("#7a5c3e", "случается"),
             ("#e08a3c", "беда за бедой")),
    "temp": (("#0a1e8c", "стужа"), ("#8a7a5a", "умеренно"),
             ("#d2321e", "жара")),
    "moist": (("#c4b278", "сушь"), ("#6d8f9a", "влажно"),
              ("#1e5a78", "мокро")),
    "elev": (("#081d30", "бездна"), ("#2f86a0", "мелководье"),
             ("#4e7a42", "низины"), ("#f1f5f7", "снега")),
}

EVENT_NAMES = (
    "Ураган", "Песчаная буря", "Снежный буран", "Извержение", "Паводок",
    "Лесной пожар", "Лавина", "Цунами", "Засуха", "Поветрие",
    "Землетрясение", "Урожайный год", "Рыбный ход", "Мягкий сезон",
    "Северное сияние", "Цветение",
)

AQUIFER_NAMES = ("нет", "лёгкий", "тяжёлый")
SAVAGERY_NAMES = ("кроткое", "вольное", "лютое")
SPIRIT_NAMES = ("злое", "нейтральное", "доброе")
RIVER_CLASSES = ("—", "ручей", "река", "большая река")

# Высотные ступени рельефа — те же, что в картогенераторе: по ним цвет
# земли и читается как карта, а не как градиент.
RELIEF_WATER = ((-6000, (8, 17, 42)), (-3000, (13, 34, 64)),
                (-1000, (22, 69, 110)), (-200, (40, 116, 162)),
                (99999, (91, 163, 191)))
RELIEF_LAND = ((50, (168, 200, 110)), (200, (138, 185, 88)),
               (500, (199, 184, 106)), (1000, (181, 155, 90)),
               (2000, (165, 115, 70)), (3500, (140, 88, 52)),
               (5000, (110, 68, 38)), (99999, (232, 226, 218)))


def _rgb(text: str) -> bytes:
    """«#rrggbb» в три байта — тем и заливается буфер картинки."""
    return bytes((int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)))


def _mix(low: str, high: str, part: float) -> bytes:
    """Цвет между двумя — для шкал плодородия, тепла и прочего."""
    part = 0.0 if part < 0 else (1.0 if part > 1 else part)
    out = []
    for index in (1, 3, 5):
        a = int(low[index:index + 2], 16)
        b = int(high[index:index + 2], 16)
        out.append(int(a + (b - a) * part))
    return bytes(out)


def _ramp(low: str, high: str, steps: int = 48) -> tuple:
    """Готовая лестница цветов: считать смесь на каждый гекс незачем."""
    return tuple(_mix(low, high, index / float(steps - 1))
                 for index in range(steps))


def _alive_at(began, ended, year: int) -> bool:
    """Было ли это уже на свете в таком-то году — и ещё не сгинуло."""
    if began is not None and int(getattr(began, "year", 0)) > year:
        return False
    if ended is not None and int(getattr(ended, "year", 0)) < year:
        return False
    return True


def _hsl(hue: float, sat: float, light: float) -> str:
    hue = (hue % 360) / 360.0

    def channel(p, q, t):
        t = t % 1.0
        if t < 1 / 6.0:
            return p + (q - p) * 6 * t
        if t < 0.5:
            return q
        if t < 2 / 3.0:
            return p + (q - p) * (2 / 3.0 - t) * 6
        return p

    if sat == 0:
        red = green = blue = light
    else:
        q = light * (1 + sat) if light < 0.5 else light + sat - light * sat
        p = 2 * light - q
        red = channel(p, q, hue + 1 / 3.0)
        green = channel(p, q, hue)
        blue = channel(p, q, hue - 1 / 3.0)
    return "#%02x%02x%02x" % (int(red * 255), int(green * 255),
                              int(blue * 255))


def _region_color(number: int) -> str:
    """Свой цвет каждой земле — лишь бы соседние не сливались.

    Тона идут золотым углом: каждый следующий отстоит от всех прежних
    настолько, насколько вообще можно.
    """
    hue = (number * 137.508) % 360.0
    light = 0.40 + (number % 3) * 0.055
    return _hsl(hue, 0.44, light)


def _decode_rle(flat) -> list:
    """Пары «значение, сколько раз» обратно в ряд значений."""
    out = []
    for index in range(0, len(flat) - 1, 2):
        out.extend([flat[index]] * int(flat[index + 1]))
    return out


class Atlas(ttk.Frame):
    """Карта мира со всеми слоями, значками и карточкой гекса."""

    def __init__(self, master, fonts=None):
        ttk.Frame.__init__(self, master)
        self.fonts = fonts or {}
        self.world = None
        self.wmap = None

        self.native = 6             # размер гекса, на котором нарисована карта
        self.cells = (2, 3, 6, 12)  # лестница приближения
        self.cell = 6
        self.off_x = 0.0            # какой угол карты сейчас в левом верхнем
        self.off_y = 0.0

        self._spans_cache = {}
        self._tint = None           # цвет каждого гекса: байты по три
        self._tint_key = None
        self._native_photo = None
        self._native_key = None
        self._direct = None         # прямая отрисовка: (фото, ox, oy, w, h)
        self._direct_key = None
        self._photo = None          # что сейчас лежит на холсте
        self._image_item = None

        self._frames = []
        self._frame_slots = None
        self._frame_year = 0
        self._colors = {}
        self._names = {}
        self._region_tones = {}
        self._roads = None
        self._towns = None
        self._features = None
        self._drag = None
        self._redraw_job = None
        self._picked = -1

        self.mode_var = tk.StringVar(value=MODES[0][0])
        self.year_var = tk.IntVar(value=0)
        self.show_rivers = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=True)
        self.show_peaks = tk.BooleanVar(value=True)
        self.show_cities = tk.BooleanVar(value=True)
        self.show_borders = tk.BooleanVar(value=True)
        self.show_routes = tk.BooleanVar(value=False)
        self.show_roads = tk.BooleanVar(value=False)
        self.show_lairs = tk.BooleanVar(value=False)
        self.show_tribes = tk.BooleanVar(value=False)
        self.note_var = tk.StringVar(value="")

        self._build()

    # ------------------------------------------------------------------
    # Устройство панели
    # ------------------------------------------------------------------

    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 2))
        ttk.Label(top, text="Слой:").pack(side="left", padx=(0, 6))
        box = ttk.Combobox(top, textvariable=self.mode_var, state="readonly",
                           width=20, values=[name for name, _ in MODES])
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda _e: self.relayer())
        self.zoom_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.zoom_var).pack(side="right", padx=6)
        ttk.Button(top, text="Вся карта", command=self.fit).pack(side="right")
        ttk.Button(top, text="+", width=3,
                   command=lambda: self.zoom(1)).pack(side="right", padx=2)
        ttk.Button(top, text="−", width=3,
                   command=lambda: self.zoom(-1)).pack(side="right")

        marks = ttk.Frame(self)
        marks.pack(fill="x", pady=(0, 2))
        ttk.Label(marks, text="Показывать:").pack(side="left", padx=(0, 6))
        for text, holder in (("реки", self.show_rivers),
                             ("подписи", self.show_labels),
                             ("вершины", self.show_peaks),
                             ("города", self.show_cities),
                             ("границы", self.show_borders),
                             ("пути", self.show_routes),
                             ("дороги", self.show_roads),
                             ("логова", self.show_lairs),
                             ("племена", self.show_tribes)):
            ttk.Checkbutton(marks, text=text, variable=holder,
                            command=self.relayer).pack(side="left", padx=3)

        self.year_bar = ttk.Frame(self)
        self.year_bar.pack(fill="x", pady=(0, 2))
        ttk.Label(self.year_bar, text="Год:").pack(side="left", padx=(0, 6))
        self.year_scale = ttk.Scale(self.year_bar, from_=0, to=1,
                                    orient="horizontal",
                                    command=self._year_moved)
        self.year_scale.pack(side="left", fill="x", expand=True)
        self.year_label = ttk.Label(self.year_bar, text="—", width=30,
                                    anchor="w")
        self.year_label.pack(side="left", padx=8)

        self.legend = tk.Canvas(self, height=20, bg=GRID_BG,
                                highlightthickness=0)
        self.legend.pack(fill="x", pady=(0, 3))

        # Перегородку между картой и карточкой человек двигает сам.
        split = ttk.PanedWindow(self, orient="horizontal")
        split.pack(fill="both", expand=True)
        self._split = split
        self._sash_set = False
        split.bind("<Configure>", self._place_sash)
        left = ttk.Frame(split)
        split.add(left, weight=4)
        self.canvas = tk.Canvas(left, bg=GRID_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._resized)
        self.canvas.bind("<Button-1>", self._pressed)
        self.canvas.bind("<B1-Motion>", self._dragged)
        self.canvas.bind("<ButtonRelease-1>", self._released)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", self._wheel)
        self.canvas.bind("<Button-5>", self._wheel)

        side = ttk.Frame(split, width=340)
        split.add(side, weight=1)
        side.pack_propagate(False)
        ttk.Label(side, textvariable=self.note_var, anchor="w",
                  wraplength=330).pack(fill="x", pady=(0, 4))
        holder = ttk.Frame(side)
        holder.pack(fill="both", expand=True)
        bar = ttk.Scrollbar(holder, orient="vertical")
        bar.pack(side="right", fill="y")
        self.card = tk.Text(holder, wrap="word", width=40,
                            font=self.fonts.get("mono"), bg="#211f2c",
                            fg="#e8e2d0", relief="flat", padx=8, pady=6,
                            yscrollcommand=bar.set)
        self.card.pack(side="left", fill="both", expand=True)
        bar.config(command=self.card.yview)
        self.card.tag_configure("head", foreground="#c6a14a",
                                font=self.fonts.get("ui"))
        self._blank_card()

    def _place_sash(self, _event=None) -> None:
        """Карточке — правый край шириной в ладонь; дальше перегородкой
        распоряжается человек, и трогать её мы больше не смеем."""
        if self._sash_set:
            return
        width = self._split.winfo_width()
        if width < 400:
            return
        self._sash_set = True
        try:
            self._split.sashpos(0, width - 340)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Новый мир
    # ------------------------------------------------------------------

    def show(self, world) -> None:
        """Взять мир и приготовить всё, что нужно для рисования."""
        self.world = world
        self.wmap = None
        link = getattr(world, "map_link", None)
        if link is not None:
            self.wmap = getattr(link, "wmap", None)
        self._forget_pictures()
        self._frames = []
        self._colors = {}
        self._names = {}
        self._region_tones = {region_id: _region_color(number)
                              for number, region_id
                              in enumerate(sorted(world.regions))}
        recorder = getattr(world, "map_recorder", None)
        if recorder is not None and recorder.frames:
            self._frames = recorder.frames
            from worldgen.chronicle_map import realm_color
            for polity_id, slot in recorder.slots.items():
                polity = world.polities.get(polity_id)
                if polity is None:
                    continue
                self._colors[slot] = realm_color(polity, slot)
                self._names[slot] = polity.full_name
        self._frame_slots = None
        self._roads = None
        self._towns = None
        self._features = None
        self._picked = -1
        self._blank_card()
        if self.wmap is None:
            if getattr(world, "map_source", ""):
                self.note_var.set(
                    "Гексовая карта вместе с миром не сохраняется — в записи "
                    "остался только её след: %s. Создайте мир заново тем же "
                    "сидом, и карта выйдет та же." % world.map_source)
            else:
                self.note_var.set("Этот мир построен без гексовой карты: "
                                  "земли движок придумал сам.")
            self.canvas.delete("all")
            self.legend.delete("all")
            return

        self._pick_native()
        count = len(self._frames)
        if count:
            self.year_scale.config(from_=0, to=max(0, count - 1))
            self.year_scale.set(count - 1)
            self.year_var.set(count - 1)
            self.year_scale.state(["!disabled"])
        else:
            self.year_scale.config(from_=0, to=0)
            self.year_var.set(0)
            self.year_scale.state(["disabled"])
        self.note_var.set("%d×%d гексов. Колесо приближает, перетаскивание "
                          "двигает, щелчок рассказывает о месте."
                          % (self.wmap.width, self.wmap.height))
        self.fit()

    def clear(self) -> None:
        self.world = None
        self.wmap = None
        self._frames = []
        self._roads = None
        self._picked = -1
        self._forget_pictures()
        self.canvas.delete("all")
        self.legend.delete("all")
        self.note_var.set("")
        self._blank_card()

    def _forget_pictures(self) -> None:
        self._tint = None
        self._tint_key = None
        self._native_photo = None
        self._native_key = None
        self._direct = None
        self._direct_key = None
        self._photo = None
        self._image_item = None

    def _pick_native(self) -> None:
        """Свой размер гекса и лестница приближения — по величине карты.

        Вся карта рисуется один раз на своём размере; больше её в памяти
        не удержать, а меньше — станет не видно ни формы гекса, ни реки.
        Мельче своего размера карта получается уменьшением, крупнее —
        рисуется прямо: гексов в окне тогда мало.
        """
        wmap = self.wmap
        native = NATIVE_CHOICES[-1]
        for choice in NATIVE_CHOICES:
            width = wmap.width * choice + choice
            height = int(wmap.height * choice * ROW_STEP) + choice * 2
            if width * height <= NATIVE_BUDGET:
                native = choice
                break
        self.native = native
        smaller = sorted({max(2, native // step) for step in (6, 4, 3, 2)
                          if native // step >= 2})
        bigger = [size for size in (native * 2, native * 3, native * 5)
                  if size <= 30]
        self.cells = tuple(sorted(set(smaller + [native] + bigger)))
        self.cell = native

    # ------------------------------------------------------------------
    # Геометрия гексов
    # ------------------------------------------------------------------

    def _hex_size(self, cell: int = 0):
        cell = cell or self.cell
        return cell, max(2, int(round(cell * HEX_TALL))), \
            max(1, int(round(cell * ROW_STEP)))

    def _spans(self, cell: int, odd: int = 0) -> tuple:
        """Ломти гекса по строкам: (сдвиг сверху, от, длина) в точках.

        Точка достаётся тому гексу, чей центр к ней ближе. Тогда соседние
        гексы сходятся без щелей — а щели на карте в полтораста тысяч
        клеток видно сразу, и карта выглядит грязной.
        """
        spans = self._spans_cache.get((cell, odd))
        if spans is not None:
            return spans
        _, height, step = self._hex_size(cell)
        if cell <= 2:
            # Мельче трёх точек гекс всё равно не разглядеть: кладём
            # прямоугольники, они смыкаются без единого зазора.
            spans = tuple((dy, 0, cell) for dy in range(step))
            self._spans_cache[(cell, odd)] = spans
            return spans

        def shift(row: int) -> int:
            return cell // 2 if row % 2 else 0

        half, mid = cell / 2.0, height / 2.0
        near = []
        for drow in (-2, -1, 0, 1, 2):
            for dcol in (-1, 0, 1):
                if dcol == 0 and drow == 0:
                    continue
                dx = dcol * cell + shift(odd + drow) - shift(odd)
                near.append((dx + half, drow * step + mid))

        rows = []
        for dy in range(-height, 2 * height):
            y = dy + 0.5
            left, right = None, None
            for dx in range(-cell, 2 * cell):
                x = dx + 0.5
                mine = (x - half) ** 2 + (y - mid) ** 2
                for cx, cy in near:
                    if (x - cx) ** 2 + (y - cy) ** 2 < mine:
                        break
                else:
                    if left is None:
                        left = dx
                    right = dx
            if left is not None:
                rows.append((dy, left, right + 1 - left))
        spans = tuple(rows)
        self._spans_cache[(cell, odd)] = spans
        return spans

    def _hex_origin(self, col: int, row: int, cell: int = 0):
        """Левый верхний угол гекса в точках всей карты."""
        cell, height, step = self._hex_size(cell)
        x = col * cell + (cell // 2 if row % 2 else 0)
        y = row * step - (height - step) / 2.0
        return x, y

    def _hex_center(self, index: int, cell: int = 0):
        cell, height, step = self._hex_size(cell)
        col, row = index % self.wmap.width, index // self.wmap.width
        ox, oy = self._hex_origin(col, row, cell)
        return ox + cell / 2.0, oy + height / 2.0

    def _hex_at(self, x: float, y: float) -> int:
        """Какому гексу принадлежит точка карты. Ищем ближайший центр."""
        if self.wmap is None:
            return -1
        cell, height, step = self._hex_size()
        row = int(y // step)
        best, best_far = -1, 1e18
        for dr in (-1, 0, 1):
            rr = row + dr
            if rr < 0 or rr >= self.wmap.height:
                continue
            for dc in (-1, 0, 1):
                cc = int((x - (cell // 2 if rr % 2 else 0)) // cell) + dc
                if self.wmap.wrap:
                    cc %= self.wmap.width
                elif cc < 0 or cc >= self.wmap.width:
                    continue
                ox, oy = self._hex_origin(cc, rr)
                dx = x - (ox + cell / 2.0)
                dy = y - (oy + height / 2.0)
                far = dx * dx + dy * dy
                if far < best_far:
                    best_far, best = far, rr * self.wmap.width + cc
        return best

    def _map_size(self, cell: int = 0):
        cell, height, step = self._hex_size(cell)
        return (self.wmap.width * cell + cell // 2,
                self.wmap.height * step + (height - step))

    # ------------------------------------------------------------------
    # Цвет каждого гекса
    # ------------------------------------------------------------------

    def _mode(self) -> str:
        wanted = self.mode_var.get()
        for name, key in MODES:
            if name == wanted:
                return key
        return "biome"

    def _frame_for_year(self):
        """Кто чем владел в выбранном году."""
        if not self._frames:
            return None
        index = max(0, min(len(self._frames) - 1, int(self.year_var.get())))
        frame = self._frames[index]
        if self._frame_slots is None or self._frame_year != frame["y"]:
            self._frame_slots = _decode_rle(frame["rle"])
            self._frame_year = frame["y"]
        return self._frame_slots

    def _year_now(self) -> int:
        """Год, на котором стоит ползунок. Без кадров — конец истории."""
        if not self._frames:
            return int(getattr(self.world, "total_years", 0) or 0)
        index = max(0, min(len(self._frames) - 1, int(self.year_var.get())))
        return int(self._frames[index]["y"])

    def _tint_colors(self) -> list:
        """Цвет каждого гекса — байтами, по три на гекс.

        Считается один раз на слой (а для держав — на год) и держится:
        именно из него собираются все картинки, сколько бы их ни
        понадобилось.
        """
        mode = self._mode()
        key = (mode, self._year_now() if mode == "realm" else 0)
        if self._tint_key == key and self._tint is not None:
            return self._tint
        wmap = self.wmap
        size = wmap.size
        flags = wmap.layer(wm.L_FLAGS)
        water_dim = _rgb(WATER_DIM)
        land_dim = _rgb(LAND_DIM)

        if mode == "biome":
            palette = [_rgb(colour) for colour in BIOME_COLORS]
            grey = _rgb("#777777")
            biome = wmap.layer(wm.L_BIOME)
            limit = len(palette)
            tint = [palette[value] if value < limit else grey
                    for value in biome] if biome is not None else [grey] * size

        elif mode == "relief":
            tint = self._relief_colors()

        elif mode == "realm":
            slots = self._frame_for_year()
            colors = {slot: _rgb(colour)
                      for slot, colour in self._colors.items()}
            other = _rgb("#8a8a8a")
            tint = []
            for index in range(size):
                if flags is not None and (flags[index] & 3):
                    tint.append(water_dim)
                    continue
                slot = slots[index] if slots is not None and \
                    index < len(slots) else -1
                tint.append(land_dim if slot < 0
                            else colors.get(slot, other))

        elif mode == "region":
            link = getattr(self.world, "map_link", None)
            owner = getattr(link, "region_of_hex", {}) if link else {}
            tones = {region_id: _rgb(colour)
                     for region_id, colour in self._region_tones.items()}
            tint = []
            for index in range(size):
                if flags is not None and (flags[index] & 3):
                    tint.append(water_dim)
                else:
                    tint.append(tones.get(owner.get(index)) or land_dim)

        elif mode == "plates":
            plate = wmap.layer(wm.L_PLATE)
            stress = wmap.layer(wm.L_STRESS)
            rift, crush = _rgb("#4f86c6"), _rgb("#d4553f")
            deep = _rgb("#13212d")
            tones = {}
            tint = []
            for index in range(size):
                if flags is not None and (flags[index] & 1):
                    tint.append(deep)
                    continue
                value = float(stress[index]) if stress is not None else 0.0
                if value > 0.25:
                    tint.append(crush)
                elif value < -0.25:
                    tint.append(rift)
                else:
                    number = int(plate[index]) if plate is not None else 0
                    tone = tones.get(number)
                    if tone is None:
                        tone = tones[number] = bytes((
                            (number * 53) % 150 + 50,
                            (number * 97) % 150 + 50,
                            (number * 29) % 150 + 50))
                    tint.append(tone)

        elif mode == "elev":
            deep = _ramp("#2f86a0", "#081d30")
            high = _ramp("#4e7a42", "#f1f5f7")
            tint = []
            for index in range(size):
                metres = wmap.elevation_m(index)
                if flags is not None and (flags[index] & 3):
                    part = min(1.0, max(0.0, -metres / 6000.0))
                    tint.append(deep[int(part * (len(deep) - 1))])
                else:
                    part = min(1.0, max(0.0, metres / 5000.0))
                    tint.append(high[int(part * (len(high) - 1))])

        elif mode == "temp":
            ramp = _ramp("#0a1e8c", "#d2321e", 64)
            data = wmap.layer(wm.L_TEMP)
            tint = []
            for index in range(size):
                value = float(data[index]) if data is not None else 0.0
                part = min(1.0, max(0.0, (value + 40.0) / 90.0))
                tint.append(ramp[int(part * (len(ramp) - 1))])

        elif mode == "moist":
            ramp = _ramp("#c4b278", "#1e5a78", 48)
            data = wmap.layer(wm.L_MOIST)
            tint = []
            for index in range(size):
                if flags is not None and (flags[index] & 1):
                    tint.append(_rgb("#16384f"))
                    continue
                value = float(data[index]) if data is not None else 0.0
                tint.append(ramp[int(min(1.0, max(0.0, value))
                                  * (len(ramp) - 1))])

        elif mode == "magic":
            good = _ramp("#1a1d16", "#5ad2aa", 40)
            evil = _ramp("#1a1d16", "#c8283c", 40)
            quiet = _rgb("#1a1d16")
            data = wmap.layer(wm.L_MAGIC)
            tint = []
            for index in range(size):
                value = float(data[index]) if data is not None else 0.0
                if abs(value) < 0.06:
                    tint.append(water_dim if flags is not None
                                and (flags[index] & 3) else quiet)
                elif value > 0:
                    tint.append(good[int(min(1.0, value) * (len(good) - 1))])
                else:
                    tint.append(evil[int(min(1.0, -value) * (len(evil) - 1))])

        else:
            layer, low, high, span = {
                "fert": (wm.L_FERTILITY, "#3a3326", "#8fd15a", 1.0),
                "wild": (wm.L_SAVAGERY, "#2f3a34", "#c0552f", 255.0),
                "risk": (wm.L_EVENTCHANCE, "#243042", "#e08a3c", 255.0),
            }.get(mode, (wm.L_FERTILITY, "#3a3326", "#8fd15a", 1.0))
            ramp = _ramp(low, high, 48)
            data = wmap.layer(layer)
            tint = []
            for index in range(size):
                if flags is not None and (flags[index] & 3):
                    tint.append(water_dim)
                    continue
                value = (float(data[index]) / span) if data is not None else 0.0
                tint.append(ramp[int(min(1.0, max(0.0, value))
                                    * (len(ramp) - 1))])

        self._tint = tint
        self._tint_key = key
        return tint

    def _relief_colors(self) -> list:
        """Рельеф с подсветкой склонов — как на странице картогенератора.

        Свет падает с северо-запада; чем круче склон к нему, тем светлее
        земля. Оттенки берутся по высотным ступеням, а не градиентом:
        так карта читается как карта.
        """
        wmap = self.wmap
        width, height = wmap.width, wmap.height
        elev = wmap.layer(wm.L_ELEV)
        flags = wmap.layer(wm.L_FLAGS)
        wrap = wmap.wrap
        # Лестница освещённости: считать на каждый гекс смесь дорого, а
        # тридцати двух ступеней глазу довольно.
        steps = 32
        bands = []
        for table in (RELIEF_WATER, RELIEF_LAND):
            for _, base in table:
                row = []
                for index in range(steps):
                    light = 0.25 + (1.15 - 0.25) * index / float(steps - 1)
                    row.append(bytes(tuple(min(255, int(channel * light))
                                           for channel in base)))
                bands.append(tuple(row))
        water_bands = bands[:len(RELIEF_WATER)]
        land_bands = bands[len(RELIEF_WATER):]
        water_edges = [edge for edge, _ in RELIEF_WATER]
        land_edges = [edge for edge, _ in RELIEF_LAND]

        tint = []
        for row in range(height):
            base = row * width
            up = max(0, row - 1) * width
            down = min(height - 1, row + 1) * width
            for col in range(width):
                index = base + col
                if wrap:
                    left = base + (col - 1) % width
                    right = base + (col + 1) % width
                else:
                    left = base + max(0, col - 1)
                    right = base + min(width - 1, col + 1)
                if elev is None:
                    tint.append(land_bands[0][steps // 2])
                    continue
                slope = (elev[left] - elev[right]) * 1.6 + \
                    (elev[up + col] - elev[down + col])
                light = 0.68 + slope * 5.5
                light = 0.25 if light < 0.25 else (1.15 if light > 1.15
                                                   else light)
                shade = int((light - 0.25) / 0.9 * (steps - 1))
                metres = wmap.elevation_m(index)
                wet = flags is not None and (flags[index] & 3)
                edges = water_edges if wet else land_edges
                table = water_bands if wet else land_bands
                for number, edge in enumerate(edges):
                    if metres < edge:
                        tint.append(table[number][shade])
                        break
                else:
                    tint.append(table[-1][shade])
        return tint

    # ------------------------------------------------------------------
    # Рисование картинок
    # ------------------------------------------------------------------

    def _paint(self, ox: int, oy: int, width: int, height: int, cell: int,
               borders: bool = False, rivers: bool = False):
        """Кусок карты в картинку Tk: заливка гексов ломтями по строкам."""
        wmap = self.wmap
        tint = self._tint_colors()
        _, hex_h, step = self._hex_size(cell)
        buf = bytearray(_rgb(GRID_BG) * (width * height))
        spans = (self._spans(cell, 0), self._spans(cell, 1))
        map_w, map_h = wmap.width, wmap.height
        first_row = max(0, int((oy - hex_h) // step) - 1)
        last_row = min(map_h - 1, int((oy + height) // step) + 1)
        first_col = max(0, int((ox - cell) // cell) - 1)
        last_col = min(map_w - 1, int((ox + width) // cell) + 1)
        runs = {}
        line3 = width * 3
        border_ink = _rgb(BORDER_INK)
        slots = self._frame_for_year() if borders else None

        for row in range(first_row, last_row + 1):
            base = row * map_w
            row_spans = spans[row % 2]
            py = int(row * step - (hex_h - step) / 2.0 - oy)
            shift = cell // 2 if row % 2 else 0
            below = base + map_w if row + 1 < map_h else -1
            for col in range(first_col, last_col + 1):
                index = base + col
                tone = tint[index]
                px = col * cell + shift - ox
                edge = False
                if slots is not None and index < len(slots):
                    mine = slots[index]
                    for other in (index + 1 if col + 1 < map_w else -1,
                                  below + col if below >= 0 else -1):
                        if other >= 0 and other < len(slots) \
                                and slots[other] != mine:
                            edge = True
                            break
                for dy, x0, span in row_spans:
                    y = py + dy
                    if y < 0 or y >= height:
                        continue
                    left = px + x0
                    right = left + span
                    if right <= 0 or left >= width:
                        continue
                    if left < 0:
                        left = 0
                    if right > width:
                        right = width
                    count = right - left
                    key = (tone, count)
                    chunk = runs.get(key)
                    if chunk is None:
                        chunk = runs[key] = tone * count
                    start = y * line3 + left * 3
                    buf[start:start + count * 3] = chunk
                    if edge:
                        buf[start:start + 3] = border_ink
                        end = start + (count - 1) * 3
                        buf[end:end + 3] = border_ink

        if rivers:
            self._paint_rivers(buf, ox, oy, width, height, cell)
        raw = b"P6\n%d %d\n255\n" % (width, height) + bytes(buf)
        return tk.PhotoImage(width=width, height=height, data=raw)

    def _paint_rivers(self, buf, ox, oy, width, height, cell) -> None:
        """Реки нитками: от гекса к тому, куда из него течёт вода.

        Толщина — по водосбору: ручей в одну точку, большая река в три.
        Рисуется прямо в буфере, потому что речных гексов тысячи, а
        фигур холста столько держать нельзя.
        """
        wmap = self.wmap
        flags = wmap.layer(wm.L_FLAGS)
        flow = wmap.layer(wm.L_FLOWTO)
        accum = wmap.layer(wm.L_ACCUM)
        if flags is None or flow is None:
            return
        _, hex_h, step = self._hex_size(cell)
        ink = _rgb(RIVER_INK)
        map_w = wmap.width
        first_row = max(0, int((oy - hex_h) // step) - 1)
        last_row = min(wmap.height - 1, int((oy + height) // step) + 1)
        first_col = max(0, int((ox - cell) // cell) - 1)
        last_col = min(map_w - 1, int((ox + width) // cell) + 1)
        thin = max(1, cell // 6)
        for row in range(first_row, last_row + 1):
            base = row * map_w
            for col in range(first_col, last_col + 1):
                index = base + col
                if not (flags[index] & 4):
                    continue
                target = int(flow[index])
                if target < 0 or target >= wmap.size:
                    continue
                water = float(accum[index]) if accum is not None else 0.0
                thick = thin if water < 20 else (thin + 1 if water < 120
                                                 else thin + 2)
                x0, y0 = self._hex_center(index, cell)
                x1, y1 = self._hex_center(target, cell)
                if abs(x1 - x0) > cell * 3:
                    continue      # шаг через край замкнутой карты
                _line(buf, width, height, x0 - ox, y0 - oy, x1 - ox, y1 - oy,
                      ink, thick)

    def _native_image(self):
        """Вся карта разом на своём размере гекса — основа всех картинок."""
        mode = self._mode()
        key = (mode, self._year_now() if mode == "realm" else 0,
               bool(self.show_borders.get()), bool(self.show_rivers.get()),
               self.native)
        if self._native_key == key and self._native_photo is not None:
            return self._native_photo
        width, height = self._map_size(self.native)
        note = self.note_var.get()
        if width * height > 1_500_000:
            self.note_var.set("Рисую карту целиком — это разом и надолго…")
            self.update_idletasks()
        photo = self._paint(0, 0, width, height, self.native,
                            borders=(mode == "realm"
                                     and self.show_borders.get()),
                            rivers=self.show_rivers.get())
        self._native_photo = photo
        self._native_key = key
        self.note_var.set(note)
        return photo

    def _surface(self, width: int, height: int):
        """Картинка под окно и то, где лежит её левый верхний угол.

        Класть на холст картинку всей карты нельзя: Tk перекладывает её
        целиком на всякую перерисовку, и на большой карте это полсотни
        миллисекунд ни за что. Поэтому из готовой карты вырезается окно
        с запасом — вырезает сам Tk, на языке C.
        """
        cell = self.cell
        native = self.native
        mode = self._mode()
        if cell <= native and native % cell == 0:
            factor = native // cell
            key = ("вырез", mode, self._year_now() if mode == "realm" else 0,
                   cell, bool(self.show_borders.get()),
                   bool(self.show_rivers.get()))
            held = self._direct
            if held is not None and self._direct_key == key:
                photo, ox, oy, has_w, has_h = held
                if ox <= self.off_x and oy <= self.off_y and \
                        ox + has_w >= self.off_x + width and \
                        oy + has_h >= self.off_y + height:
                    return photo, ox, oy
            native_photo = self._native_image()
            want_x = int(self.off_x) - DIRECT_MARGIN
            want_y = int(self.off_y) - DIRECT_MARGIN
            want_w = width + DIRECT_MARGIN * 2
            want_h = height + DIRECT_MARGIN * 2
            photo = tk.PhotoImage(width=want_w, height=want_h)
            src_x = max(0, want_x * factor)
            src_y = max(0, want_y * factor)
            src_x1 = min(native_photo.width(), (want_x + want_w) * factor)
            src_y1 = min(native_photo.height(), (want_y + want_h) * factor)
            if src_x1 > src_x and src_y1 > src_y:
                photo.tk.call(photo, "copy", native_photo,
                              "-from", src_x, src_y, src_x1, src_y1,
                              "-to", src_x // factor - want_x,
                              src_y // factor - want_y,
                              "-subsample", factor, factor)
            self._direct = (photo, want_x, want_y, want_w, want_h)
            self._direct_key = key
            return photo, float(want_x), float(want_y)
        # Крупный масштаб: гексов в окне мало, рисуем прямо — с запасом,
        # чтобы небольшая прокрутка обошлась без новой картинки.
        key = (mode, self._year_now() if mode == "realm" else 0, cell,
               bool(self.show_borders.get()), bool(self.show_rivers.get()))
        want_x = int(self.off_x - DIRECT_MARGIN)
        want_y = int(self.off_y - DIRECT_MARGIN)
        want_w = width + DIRECT_MARGIN * 2
        want_h = height + DIRECT_MARGIN * 2
        held = self._direct
        if held is not None and self._direct_key == key:
            photo, ox, oy, has_w, has_h = held
            if ox <= self.off_x and oy <= self.off_y and \
                    ox + has_w >= self.off_x + width and \
                    oy + has_h >= self.off_y + height:
                return photo, ox, oy
        photo = self._paint(want_x, want_y, want_w, want_h, cell,
                            borders=(mode == "realm"
                                     and self.show_borders.get()),
                            rivers=self.show_rivers.get())
        self._direct = (photo, want_x, want_y, want_w, want_h)
        self._direct_key = key
        return photo, float(want_x), float(want_y)

    # ------------------------------------------------------------------
    # Приближение и перерисовка
    # ------------------------------------------------------------------

    def fit(self) -> None:
        """Вся карта целиком в окно, и как можно крупнее.

        Размер берётся не из лестницы приближения, а какой войдёт: пустые
        поля по краям карту не украшают.
        """
        if self.wmap is None:
            return
        self.canvas.update_idletasks()
        width = max(200, self.canvas.winfo_width())
        height = max(200, self.canvas.winfo_height())
        by_width = width / (self.wmap.width + 0.5)
        by_height = height / (self.wmap.height * ROW_STEP + 0.5)
        self.cell = max(2, min(30, int(min(by_width, by_height))))
        self.off_x = 0.0
        self.off_y = 0.0
        self.redraw()

    def zoom(self, delta: int, focus=None) -> None:
        """Шаг по лестнице приближения — от того, где сейчас стоим."""
        if self.wmap is None:
            return
        order = list(self.cells)
        place = 0
        for number, cell in enumerate(order):
            if cell <= self.cell:
                place = number
        if delta > 0 and order[place] <= self.cell:
            place += 1
        elif delta < 0 and order[place] >= self.cell:
            place -= 1
        place = max(0, min(len(order) - 1, place))
        if order[place] == self.cell:
            return
        before = self.cell
        self.cell = order[place]
        ratio = float(self.cell) / before
        if focus is None:
            focus = (self.canvas.winfo_width() / 2.0,
                     self.canvas.winfo_height() / 2.0)
        self.off_x = (self.off_x + focus[0]) * ratio - focus[0]
        self.off_y = (self.off_y + focus[1]) * ratio - focus[1]
        self.redraw()

    def relayer(self) -> None:
        """Слой или набор значков переменились.

        Собирать что-то заново тут не надо: у каждой картинки есть ключ,
        в который входит и слой, и год, и границы с реками. Значки же
        живут фигурами холста и рисуются при всякой перерисовке.
        """
        self.redraw()

    def redraw(self) -> None:
        """Положить картинку на холст и расставить по ней значки."""
        if self.wmap is None or not self.winfo_exists():
            return
        self.canvas.update_idletasks()
        width = max(50, self.canvas.winfo_width())
        height = max(50, self.canvas.winfo_height())
        map_w, map_h = self._map_size()
        slack_x, slack_y = map_w - width, map_h - height
        self.off_x = (slack_x / 2.0 if slack_x < 0 else
                      max(-40.0, min(self.off_x, slack_x + 40)))
        self.off_y = (slack_y / 2.0 if slack_y < 0 else
                      max(-40.0, min(self.off_y, slack_y + 40)))

        photo, base_x, base_y = self._surface(width, height)
        self._photo = photo
        self.canvas.delete("all")
        self._image_item = self.canvas.create_image(
            base_x - self.off_x, base_y - self.off_y, image=photo, anchor="nw")
        self._draw_marks()
        self._update_year_label()
        self._draw_legend()
        self.zoom_var.set("гекс %d т." % self.cell)

    # ------------------------------------------------------------------
    # Значки поверх картинки
    # ------------------------------------------------------------------

    def _road_paths(self) -> list:
        """Дороги держав по гексам: считаются один раз за мир."""
        if self._roads is not None:
            return self._roads
        recorder = getattr(self.world, "map_recorder", None)
        if recorder is None or self.wmap is None:
            self._roads = []
            return self._roads
        note = self.note_var.get()
        self.note_var.set("Прокладываю дороги — это разом и надолго…")
        self.update_idletasks()
        width = self.wmap.width
        roads = []
        try:
            for road in recorder.roads():
                flat = road.get("path") or []
                path = [flat[i + 1] * width + flat[i]
                        for i in range(0, len(flat) - 1, 2)]
                if len(path) >= 2:
                    roads.append(path)
        except Exception:
            roads = []           # дороги — украшение, без них карта живёт
        self._roads = roads
        self.note_var.set(note)
        return self._roads

    def _draw_marks(self) -> None:
        """Города, вершины, подписи и прочее — на выбранный год.

        Город, основанный позже, ещё не заложен; погибший — уже брошен.
        Так ползунок листает не только границы держав, но и весь мир.
        """
        world = self.world
        if world is None:
            return
        cell, hex_h, step = self._hex_size()
        year = self._year_now()
        ui_font = self.fonts.get("ui")

        def point(index):
            x, y = self._hex_center(index)
            return x - self.off_x, y - self.off_y

        seam = self.wmap.width * cell / 2.0
        canvas = self.canvas
        width = max(50, canvas.winfo_width())
        height = max(50, canvas.winfo_height())

        def seen(x, y, slack=40):
            return -slack <= x <= width + slack and -slack <= y <= height + slack

        def thread(path, fill, thick=1, dash=None):
            piece = []
            last = None
            for index in path:
                x, y = point(index)
                if last is not None and abs(x - last) > seam:
                    if len(piece) >= 4:
                        canvas.create_line(*piece, fill=fill, width=thick,
                                           dash=dash)
                    piece = []
                piece.extend((x, y))
                last = x
            if len(piece) >= 4:
                canvas.create_line(*piece, fill=fill, width=thick, dash=dash)

        if self.show_roads.get():
            for path in self._road_paths():
                thread(path, "#8a7a5a")
        if self.show_routes.get():
            for route in world.routes.values():
                if _alive_at(route.opened, route.closed, year):
                    thread(route.path or (), "#c9a34a", dash=(3, 3))

        if self.show_peaks.get():
            size = max(3, min(9, int(cell * 0.7)))
            for peak in (self.wmap.peaks or ()):
                index = int(peak.get("i", -1))
                if index < 0:
                    continue
                x, y = point(index)
                if not seen(x, y, 10):
                    continue
                canvas.create_polygon(x, y - size, x + size * 0.8, y + size * 0.6,
                                      x - size * 0.8, y + size * 0.6,
                                      fill="#efe6d4", outline="#3a3428")
            for volcano in (self.wmap.volcanoes or ()):
                index = int(volcano.get("i", -1))
                if index < 0:
                    continue
                x, y = point(index)
                if not seen(x, y, 10):
                    continue
                hot = volcano.get("status") == "активный"
                canvas.create_polygon(x, y - size, x + size * 0.9, y + size * 0.7,
                                      x - size * 0.9, y + size * 0.7,
                                      fill="#b0453a" if hot else "#6d4a42",
                                      outline="#ffd9a0" if hot else "#2a2620")

        if self.show_lairs.get():
            for lair in (self.wmap.lairs or ()):
                index = int(lair.get("i", -1))
                if index < 0:
                    continue
                x, y = point(index)
                if not seen(x, y, 10):
                    continue
                size = max(3, cell // 2)
                canvas.create_polygon(x, y - size, x + size, y, x, y + size,
                                      x - size, y, fill="#b0353a",
                                      outline="#f0d0a0")

        if self.show_tribes.get():
            size = max(2, cell // 3)
            for item in world.tribes.values():
                if item.hex_index < 0 or not _alive_at(item.founded,
                                                       item.ended, year):
                    continue
                x, y = point(item.hex_index)
                if seen(x, y, 10):
                    canvas.create_oval(x - size, y - size, x + size, y + size,
                                       fill="#8a7448", outline="")
            for camp in world.camps.values():
                if camp.hex_index < 0 or not _alive_at(camp.founded,
                                                       camp.ended, year):
                    continue
                x, y = point(camp.hex_index)
                if seen(x, y, 10):
                    canvas.create_oval(x - size, y - size, x + size, y + size,
                                       fill="#6b3b2e", outline="")

        if self.show_cities.get():
            named = 0
            rows = self._towns_by_size()
            for item in rows:
                if item.hex_index < 0 or not _alive_at(item.founded,
                                                       item.ended, year):
                    continue
                x, y = point(item.hex_index)
                if not seen(x, y, 12):
                    continue
                size = 2 + min(6, int(math.sqrt(max(1, item.population)) / 34))
                if item.is_capital:
                    canvas.create_rectangle(x - size, y - size, x + size,
                                            y + size, fill="#f7e9b8",
                                            outline="#241f16", width=1)
                else:
                    canvas.create_oval(x - size, y - size, x + size, y + size,
                                       fill="#e8d8a8", outline="#241f16")
                # Подписи: сперва крупным городам, и только пока их немного —
                # иначе карта зарастает буквами.
                if cell >= 8 and named < 40:
                    named += 1
                    _halo(canvas, x, y - size - 6, item.name, ui_font,
                          "#f6eed6")

        if self.show_labels.get():
            self._draw_labels(point, seen, ui_font)

        if self._picked >= 0:
            x, y = point(self._picked)
            size = max(5, cell * 0.62)
            shape = []
            for number in range(6):
                angle = math.pi / 180.0 * (60 * number + 30)
                shape.extend((x + size * math.cos(angle),
                              y + size * math.sin(angle)))
            canvas.create_polygon(*shape, fill="", outline="#ffffff", width=2)
            canvas.create_polygon(*shape, fill="", outline="#d4553f", width=1)

    def _towns_by_size(self) -> list:
        """Города по убыванию людности — считается один раз на мир."""
        if self._towns is None:
            self._towns = sorted(self.world.settlements.values(),
                                 key=lambda item: -item.population)
        return self._towns

    def _big_features(self) -> list:
        """Что подписывать на карте: самое крупное, и не больше восьмидесяти.

        Островов на карте бывает под тысячу; подписать их все — значит
        закрыть буквами саму карту и просадить прокрутку.
        """
        if self._features is None:
            rows = [item for item in (self.wmap.features or ())
                    if not item.get("nolabel")]
            rows.sort(key=lambda item: -float(item.get("area", 0)))
            self._features = rows[:80]
        return self._features

    def _draw_labels(self, point, seen, ui_font) -> None:
        """Имена морей, материков и хребтов — как на карте картогенератора."""
        cell = self.cell
        sizes = {"ocean": 20, "sea": 14, "inlandsea": 13, "bay": 10,
                 "lake": 10, "continent": 17, "bigisland": 12, "island": 9,
                 "archipelago": 12, "range": 11}
        base = self.fonts.get("ui")
        family = base.cget("family") if base is not None else "Helvetica"
        _, hex_h, step = self._hex_size()
        for feature in self._big_features():
            kind = feature.get("type")
            weight = sizes.get(kind)
            if weight is None:
                continue
            size = int(max(8, min(30, weight * max(0.5, cell * 0.22))))
            if size < 9:
                continue
            col = float(feature.get("cx", 0))
            row = float(feature.get("cy", 0))
            x = (col + (0.5 if int(row) % 2 else 0)) * cell + cell / 2.0 \
                - self.off_x
            y = row * step + hex_h / 2.0 - self.off_y
            if not seen(x, y, 60):
                continue
            noun = FEATURE_NOUNS.get(kind, "")
            name = translit(feature.get("name", ""))
            text = ("%s %s" % (noun.capitalize(), name)).strip()
            water = kind in ("ocean", "sea", "bay", "inlandsea", "lake")
            _halo(self.canvas, x, y, text, (family, size, "bold"),
                  "#c8dae8" if water else "#f5eedc", halo="#0a1018")

    def _draw_legend(self) -> None:
        """Что значит цвет: для шкал — лестница, для держав — кто есть кто."""
        canvas = self.legend
        canvas.delete("all")
        mode = self._mode()
        x = 6
        font = self.fonts.get("ui")

        def chip(colour, text):
            """Пятно цвета и подпись к нему. Ширину меряем, а не гадаем:
            на кириллице «на глаз» подписи наезжают друг на друга."""
            nonlocal x
            if x > int(canvas.winfo_width()) - 60:
                return
            canvas.create_rectangle(x, 4, x + 14, 16, fill=colour, outline="")
            canvas.create_text(x + 19, 10, text=text, anchor="w",
                               fill="#cfc7b4", font=font)
            try:
                room = font.measure(text) if font is not None else len(text) * 7
            except Exception:
                room = len(text) * 7
            x += 19 + room + 16

        if mode == "realm":
            slots = self._frame_for_year()
            if not slots:
                canvas.create_text(6, 10, text="держав в этот год не видно",
                                   anchor="w", fill="#9a927f", font=font)
                return
            counts = {}
            for slot in slots:
                if slot >= 0:
                    counts[slot] = counts.get(slot, 0) + 1
            top = sorted(counts.items(), key=lambda item: -item[1])[:8]
            for slot, _size in top:
                chip(self._colors.get(slot, "#8a8a8a"),
                     self._names.get(slot, "чья-то держава"))
            return
        if mode == "biome":
            canvas.create_text(6, 10, anchor="w", fill="#9a927f", font=font,
                               text="цвета биомов — те же, что у карты; "
                                    "щелчок по гексу назовёт биом")
            return
        for colour, text in LEGENDS.get(mode, ()):
            chip(colour, text)

    # ------------------------------------------------------------------
    # Мышь и год
    # ------------------------------------------------------------------

    def _resized(self, _event=None) -> None:
        self._schedule()

    def _schedule(self, delay: int = 120) -> None:
        if self._redraw_job is not None:
            try:
                self.after_cancel(self._redraw_job)
            except Exception:
                pass
        self._redraw_job = self.after(delay, self._run_redraw)

    def _run_redraw(self) -> None:
        self._redraw_job = None
        self.redraw()

    def _pressed(self, event) -> None:
        self._drag = (event.x, event.y, self.off_x, self.off_y, False)

    def _dragged(self, event) -> None:
        if self._drag is None:
            return
        x0, y0, ox, oy, moved = self._drag
        dx, dy = event.x - x0, event.y - y0
        if not moved and abs(dx) + abs(dy) < 4:
            return
        self._drag = (x0, y0, ox, oy, True)
        # Картинка и значки едут вместе одной командой: перерисовывать
        # что-либо на каждое движение руки незачем.
        step_x = (ox - dx) - self.off_x
        step_y = (oy - dy) - self.off_y
        self.off_x = ox - dx
        self.off_y = oy - dy
        self.canvas.move("all", -step_x, -step_y)
        self._schedule(90)

    def _released(self, event) -> None:
        if self._drag is None:
            return
        moved = self._drag[4]
        self._drag = None
        if moved:
            self._schedule(10)
            return
        index = self._hex_at(event.x + self.off_x, event.y + self.off_y)
        if index >= 0:
            self._picked = index
            self.describe(index)
            self.redraw()

    def _wheel(self, event) -> None:
        delta = getattr(event, "delta", 0)
        step = 1 if (delta > 0 or getattr(event, "num", 0) == 4) else -1
        self.zoom(step, focus=(event.x, event.y))

    def _year_moved(self, _value=None) -> None:
        if not self._frames:
            return
        index = int(float(self.year_scale.get()))
        if index == self.year_var.get():
            return
        self.year_var.set(index)
        self._update_year_label()
        # Год меняет и окраску держав, и города, и племена. Пока ползунок
        # ползёт, перерисовывать нечего: ждём, пока рука остановится.
        if self._mode() == "realm":
            self._native_key = None
            self._direct_key = None
        self._schedule(160)

    def _update_year_label(self) -> None:
        if not self._frames:
            self.year_label.config(text="кадров нет")
            return
        index = max(0, min(len(self._frames) - 1, int(self.year_var.get())))
        year = self._frames[index]["y"]
        era = self.world.era_at(year) if self.world else None
        self.year_label.config(text="%d год — %s"
                               % (year, era.name if era else "—"))

    def look_at(self, year: int = 0, region_id: str = "",
                hex_index: int = -1) -> None:
        """Показать названное место в названный год.

        Этим пользуется «История мира»: человек нашёл запись и хочет
        увидеть, где это было и как тогда выглядел мир.
        """
        if self.wmap is None or self.world is None:
            return
        if year and self._frames:
            # Кадры границ сняты не каждый год: берём ближайший к
            # названному, но не позже него.
            best = 0
            for number, frame in enumerate(self._frames):
                if frame["y"] <= year:
                    best = number
            self.year_var.set(best)
            self.year_scale.set(best)
            self._update_year_label()
        if hex_index < 0 and region_id:
            hex_index = self._region_hex(region_id)
        if hex_index < 0:
            self.redraw()
            return
        self._picked = hex_index
        cell, hex_h, step = self._hex_size()
        x, y = self._hex_center(hex_index)
        self.off_x = x - max(50, self.canvas.winfo_width()) / 2.0
        self.off_y = y - max(50, self.canvas.winfo_height()) / 2.0
        self.describe(hex_index)
        self.redraw()

    def _region_hex(self, region_id: str) -> int:
        """Какой-нибудь гекс этой земли — лучше тот, где стоит город."""
        world = self.world
        for item in world.settlements.values():
            if item.region_id == region_id and item.hex_index >= 0:
                return item.hex_index
        link = getattr(world, "map_link", None)
        owner = getattr(link, "region_of_hex", {}) if link else {}
        for index, holder in owner.items():
            if holder == region_id:
                return index
        return -1

    # ------------------------------------------------------------------
    # Карточка гекса
    # ------------------------------------------------------------------

    def _blank_card(self) -> None:
        self.card.config(state="normal")
        self.card.delete("1.0", "end")
        self.card.insert("1.0", "Щёлкните по гексу — и здесь будет всё, что "
                                "о нём известно: земля, климат, недра, "
                                "и вся его история на выбранный год.")
        self.card.config(state="disabled")

    def describe(self, index: int) -> None:
        """Всё, что известно про этот гекс — человеческим языком."""
        wmap, world = self.wmap, self.world
        if wmap is None or world is None:
            return
        lines = []
        lines.extend(self._card_land(index))
        lines.extend(self._card_nature(index))
        lines.extend(self._card_here(index))
        lines.extend(self._card_history(index))
        self.card.config(state="normal")
        self.card.delete("1.0", "end")
        for line in lines:
            if line.startswith("## "):
                self.card.insert("end", line[3:] + "\n", "head")
            else:
                self.card.insert("end", line + "\n")
        self.card.config(state="disabled")
        self.card.see("1.0")

    def _card_land(self, index: int) -> list:
        """Первое, что нужно знать о месте: что это за земля."""
        wmap = self.wmap
        col, row = index % wmap.width, index // wmap.width
        biome = wmap.layer(wm.L_BIOME)
        value = int(biome[index]) if biome is not None else 0
        name = (BIOME_NAMES[value] if value < len(BIOME_NAMES)
                else "неведомая земля")
        lines = ["## %s" % name,
                 "гекс %d — столбец %d, строка %d" % (index, col, row),
                 "высота ......... %d м" % round(wmap.elevation_m(index))]
        temp = wmap.layer(wm.L_TEMP)
        if temp is not None:
            # Лето и зима считаются из средней и широты — так же, как их
            # считает карта: чем дальше от равнины экватора, тем больше
            # разброс.
            lat = abs(wmap.latitude(index))
            swing = 4.0 + 26.0 * lat
            lines.append("тепло .......... %+.1f °C в среднем, "
                         "лето %+.0f, зима %+.0f"
                         % (temp[index], temp[index] + swing / 2.0,
                            temp[index] - swing / 2.0))
        moist = wmap.layer(wm.L_MOIST)
        if moist is not None:
            lines.append("влага .......... %d %%" % round(moist[index] * 100))
        water = []
        if wmap.is_ocean(index):
            water.append("океан")
        if wmap.is_lake(index):
            water.append("озеро")
        if wmap.is_river(index):
            accum = wmap.layer(wm.L_ACCUM)
            flow = float(accum[index]) if accum is not None else 0.0
            level = 3 if flow >= 120 else (2 if flow >= 20 else 1)
            water.append(RIVER_CLASSES[level])
        if wmap.is_coast(index):
            water.append("берег")
        if water:
            lines.append("вода ........... %s" % ", ".join(water))
        plate = wmap.layer(wm.L_PLATE)
        stress = wmap.layer(wm.L_STRESS)
        if plate is not None:
            mood = ""
            if stress is not None:
                value = float(stress[index])
                mood = (" (сходятся)" if value > 0.25 else
                        " (расходятся)" if value < -0.25 else "")
            lines.append("литоплита ...... №%d%s" % (int(plate[index]), mood))
        return lines

    def _card_nature(self, index: int) -> list:
        """Чем земля живёт: плодородие, живность, промыслы, недра, округа."""
        wmap = self.wmap
        lines = [""]
        fert = wmap.layer(wm.L_FERTILITY)
        if fert is not None and wmap.is_land(index):
            lines.append("плодородие ..... %.2f" % fert[index])
        rich = wmap.layer(wm.L_RICHNESS)
        res = wmap.layer(wm.L_RESFLAGS)
        tail = wmap.tail.get("resources") or {}
        buckets = tail.get("densityBuckets") or ()
        if rich is not None and buckets:
            level = min(len(buckets) - 1, int(rich[index]) * len(buckets) // 256)
            lines.append("живность ....... %s" % buckets[level])
        if res is not None:
            bits = int(res[index])
            marks = []
            if bits & (1 << 2):
                marks.append("крупный зверь")
            if bits & (1 << 3):
                marks.append("редкая волшебная тварь")
            if bits & (1 << 4):
                marks.append("морской промысел")
            if marks:
                lines.append("промысел ....... %s" % ", ".join(marks))
        biome = wmap.layer(wm.L_BIOME)
        by_biome = (tail.get("biomes") or {}).get(
            str(int(biome[index])) if biome is not None else "")
        if by_biome:
            products = tail.get("products") or []
            names = [products[number] for number in
                     (by_biome.get("products") or ())
                     if 0 <= number < len(products)]
            if by_biome.get("common") and by_biome["common"] != "—":
                lines.append("водится ........ %s" % by_biome["common"])
            if by_biome.get("magical") and by_biome["magical"] != "—":
                lines.append("и ещё .......... %s" % by_biome["magical"])
            if names:
                lines.append("даёт ........... %s" % ", ".join(names[:6]))
        aqua = wmap.layer(wm.L_AQUIFER)
        if aqua is not None and wmap.is_land(index):
            lines.append("вода под землёй  %s"
                         % AQUIFER_NAMES[min(2, int(aqua[index]))])
        savage = wmap.layer(wm.L_SAVAGERY)
        magic = wmap.layer(wm.L_MAGIC)
        if savage is not None and wmap.is_land(index):
            level = 2 if savage[index] >= 168 else (1 if savage[index] >= 84
                                                    else 0)
            spirit = 1
            if magic is not None:
                spirit = 2 if magic[index] > 0.12 else (
                    0 if magic[index] < -0.12 else 1)
                names = (wmap.tail.get("surroundings") or {}).get("names") or ()
                place = level * 3 + spirit
                if 0 <= place < len(names):
                    lines.append("округа ......... %s (%s, %s)"
                                 % (names[place], SAVAGERY_NAMES[level],
                                    SPIRIT_NAMES[spirit]))
                else:
                    lines.append("округа ......... %s"
                                 % SAVAGERY_NAMES[level])
        if magic is not None and abs(magic[index]) > 0.05:
            lines.append("магия .......... %+.2f (%s)"
                         % (magic[index],
                            "светлая" if magic[index] > 0 else "тёмная"))
        mask = wmap.layer(wm.L_EVENTMASK)
        if mask is not None and mask[index]:
            bits = int(mask[index]) & 0xFFFF
            threats = [EVENT_NAMES[number] for number in range(len(EVENT_NAMES))
                       if bits & (1 << number)]
            if threats:
                lines.append("случается тут .. %s" % ", ".join(threats))
        ores = wmap.minerals.get(str(index))
        if ores:
            lines.append("")
            lines.append("## НЕДРА")
            for item in ores[:6]:
                lines.append("   %s — %s" % (item[0], item[1]))
        return lines

    def _card_here(self, index: int) -> list:
        """Что стоит на этом гексе по карте: земля истории, хребет, логово."""
        wmap, world = self.wmap, self.world
        story = []
        link = getattr(world, "map_link", None)
        region_id = (getattr(link, "region_of_hex", {}) or {}).get(index)
        region = world.regions.get(region_id) if region_id else None
        if region is not None:
            story.append("земля по имени %s" % region.name)
        for feature in (wmap.features or ()):
            layer_id = {"ocean": wm.L_WATERREG, "sea": wm.L_WATERREG,
                        "bay": wm.L_WATERREG, "lake": wm.L_WATERREG,
                        "inlandsea": wm.L_WATERREG,
                        "continent": wm.L_LANDREG, "island": wm.L_LANDREG,
                        "bigisland": wm.L_LANDREG,
                        "archipelago": wm.L_LANDREG,
                        "range": wm.L_RANGEREG,
                        "river": wm.L_RIVERREG}.get(feature.get("type"))
            if layer_id is None:
                continue
            data = wmap.layer(layer_id)
            if data is not None and data[index] == feature.get("id"):
                noun = FEATURE_NOUNS.get(feature.get("type"), "")
                name = translit(feature.get("name", ""))
                story.append(("%s по имени %s" % (noun, name)) if noun
                             else name)
        for peak in (wmap.peaks or ()):
            if peak.get("i") == index:
                name = str(peak.get("name", ""))
                name = name[3:] if name.startswith("г. ") else name
                story.append("вершина по имени %s, %d м"
                             % (translit(name), peak.get("m", 0)))
        for volcano in (wmap.volcanoes or ()):
            if volcano.get("i") == index:
                story.append("вулкан по имени %s (%s)"
                             % (translit(volcano.get("name", "")),
                                volcano.get("status")))
        for lair in (wmap.lairs or ()):
            if lair.get("i") == index:
                story.append("логово: %s по имени %s"
                             % (lair.get("kindName"),
                                translit(lair.get("name", ""))))
        if not story:
            return []
        return [""] + ["## ЗДЕСЬ"] + ["   %s" % row for row in story]

    def _card_history(self, index: int) -> list:
        """История места на выбранный год — главное, чего нет у карты.

        Держава, город, крепости, племена, беды, что тут случилось и что
        об этом рассказывают. Всё — по состоянию на год ползунка: карта
        должна отвечать на «а что было тогда», а не только на «что есть».
        """
        world = self.world
        year = self._year_now()
        lines = ["", "## В %d ГОДУ" % year]
        link = getattr(world, "map_link", None)
        region_id = (getattr(link, "region_of_hex", {}) or {}).get(index)

        slots = self._frame_for_year()
        owner = None
        if slots is not None and index < len(slots) and slots[index] >= 0:
            owner = self._names.get(slots[index])
        lines.append("   землёй владела: %s" % (owner or "ничья земля"))

        for item in world.settlements.values():
            if item.hex_index != index:
                continue
            if _alive_at(item.founded, item.ended, year):
                polity = world.polities.get(item.polity_id)
                lines.append("   %s — %d жителей%s"
                             % (item.full_name, item.population,
                                ", столица" if item.is_capital else ""))
                if polity is not None:
                    lines.append("   держава: %s" % polity.full_name)
            elif item.ended is not None and item.ended.year < year:
                lines.append("   %s — покинут в %d году (%s)"
                             % (item.full_name, item.ended.year,
                                item.end_reason or "причина не названа"))
        for fortress in world.fortresses.values():
            if getattr(fortress, "hex_index", -1) != index:
                continue
            if _alive_at(fortress.built, fortress.ended, year):
                holder = world.polities.get(fortress.polity_id)
                lines.append("   крепость по имени %s%s"
                             % (fortress.name,
                                " — держава %s" % holder.name if holder
                                else ""))
        for item in world.tribes.values():
            if item.hex_index == index and _alive_at(item.founded, item.ended,
                                                     year):
                lines.append("   племя по имени %s — %d душ"
                             % (item.name, item.population))
        for camp in world.camps.values():
            if camp.hex_index == index and _alive_at(camp.founded, camp.ended,
                                                     year):
                lines.append("   %s по имени %s"
                             % (camp.word.lower(), camp.name))

        # Беды: та, что шла по этой земле в этот год, важнее всех прочих.
        if region_id:
            going = []
            past = []
            for calamity in world.calamities.values():
                if region_id not in (calamity.region_ids or ()):
                    continue
                start = calamity.start.year if calamity.start else 0
                end = calamity.end.year if calamity.end else start
                if start <= year <= end:
                    going.append("   идёт: %s (с %d года)"
                                 % (calamity.name, start))
                elif end < year:
                    past.append((end, "   было: %s, %d–%d"
                                 % (calamity.name, start, end)))
            lines.extend(going)
            past.sort(reverse=True)
            lines.extend(row for _, row in past[:4])

            for scar in world.scars.values():
                if getattr(scar, "region_id", "") != region_id:
                    continue
                made = getattr(scar, "created", None)
                if made is not None and made.year <= year:
                    lines.append("   шрам на земле: %s" % scar.name)
            for trace in world.traces.values():
                if getattr(trace, "region_id", "") != region_id:
                    continue
                made = getattr(trace, "made", None)
                if made is not None and made.year <= year:
                    lines.append("   след беды: %s" % trace.full_name)

        places = [item.id for item in world.settlements.values()
                  if item.hex_index == index]
        places += [item.id for item in world.sites.values()
                   if item.hex_index == index]
        for place_id in places:
            place = world.entity(place_id)
            if place is None or place_id.startswith("C"):
                continue
            opened = getattr(place, "opened", None)
            lines.append("   место истории: %s%s"
                         % (getattr(place, "full_name", place.name),
                            " (вскрыто в %d)" % opened.year
                            if opened is not None and opened.year <= year
                            else ""))
        told = []
        for place_id in places:
            for story in world.stories_at(place_id):
                if story.began.year <= year:
                    told.append((story.began.ordinal, story))
        if told:
            told.sort()
            lines.append("")
            lines.append("## ЧТО ТУТ РАССКАЗЫВАЮТ")
            for _, story in told[:8]:
                lines.append("   %5d  %s" % (story.began.year, story.title))
        return lines


def _halo(canvas, x, y, text, font, fill, halo="#141018") -> None:
    """Надпись с тенью: без неё имена теряются на пёстрой карте.

    Тень — одна фигура, а не обводка из четырёх: подписей на карте
    сотни, и каждая лишняя фигура холста стоит времени на всякой
    прокрутке.
    """
    canvas.create_text(x + 1, y + 1, text=text, fill=halo, font=font)
    canvas.create_text(x, y, text=text, fill=fill, font=font)


def _line(buf, width, height, x0, y0, x1, y1, ink, thick=1) -> None:
    """Отрезок прямо в буфере картинки — для рек и прочих ниток."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    steps = max(abs(x1 - x0), abs(y1 - y0))
    if steps <= 0:
        steps = 1
    line3 = width * 3
    half = max(0, thick // 2)
    for step in range(steps + 1):
        x = x0 + (x1 - x0) * step // steps
        y = y0 + (y1 - y0) * step // steps
        for dy in range(-half, half + 1):
            row = y + dy
            if row < 0 or row >= height:
                continue
            left = max(0, x - half)
            right = min(width, x + half + 1)
            if right <= left:
                continue
            start = row * line3 + left * 3
            buf[start:start + (right - left) * 3] = ink * (right - left)
