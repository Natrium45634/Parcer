# -*- coding: utf-8 -*-
"""Живая карта мира: гексы, границы по годам и карточка места.

Картогенератор показывает мир гексами и рассказывает про каждый гекс,
если по нему щёлкнуть. Здесь то же самое, только поверх готовой истории:
к земле и климату добавляются державы в выбранном году, города, дороги,
торговые пути, логова древних тварей и стоянки племён.

Как это нарисовано. Рисовать каждый гекс отдельной фигурой нельзя: на
большой карте их сто пятьдесят тысяч, и окно встанет. Поэтому видимый
кусок карты собирается в картинку по строкам пикселей — гекс за гексом,
ломтями, — и кладётся на холст одним куском. Поверх картинки ложатся
только редкие значки: города, пути, логова. Их сотни, а не тысячи, и они
рисуются обычными фигурами, чтобы по ним можно было щёлкать.

Оттого и прокрутка устроена окном: при перетаскивании картинка едет
целиком, а перерисовывается уже после того, как рука остановилась.
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
MIN_CELL, MAX_CELL = 1, 28

WATER_DIM = "#16202c"
LAND_DIM = "#2e3330"
GRID_BG = "#0d1016"

MODES = (
    ("Биомы", "biome"),
    ("Державы по годам", "realm"),
    ("Земли истории", "region"),
    ("Плодородие", "fert"),
    ("Дикость округи", "wild"),
    ("Магия", "magic"),
    ("Опасности", "risk"),
    ("Высоты", "elev"),
)

EVENT_NAMES = (
    "Ураган", "Песчаная буря", "Снежный буран", "Извержение", "Паводок",
    "Лесной пожар", "Лавина", "Цунами", "Засуха", "Поветрие",
    "Землетрясение", "Урожайный год", "Рыбный ход", "Мягкий сезон",
    "Северное сияние", "Цветение",
)

AQUIFER_NAMES = ("нет", "лёгкий", "тяжёлый")
SAVAGERY_NAMES = ("кроткое", "вольное", "лютое")


def _mix(low, high, part: float) -> str:
    """Цвет между двумя — для шкал плодородия, дикости и прочего."""
    part = max(0.0, min(1.0, part))
    out = []
    for index in (1, 3, 5):
        a = int(low[index:index + 2], 16)
        b = int(high[index:index + 2], 16)
        out.append(int(a + (b - a) * part))
    return "#%02x%02x%02x" % tuple(out)


def _alive_at(began, ended, year: int) -> bool:
    """Было ли это уже на свете в таком-то году — и ещё не сгинуло."""
    if began is not None and int(getattr(began, "year", 0)) > year:
        return False
    if ended is not None and int(getattr(ended, "year", 0)) < year:
        return False
    return True


def _region_color(number: int) -> str:
    """Свой цвет каждой земле — лишь бы соседние не сливались.

    Тона идут золотым углом: каждый следующий отстоит от всех прежних
    настолько, насколько вообще можно. Тридцать земель так не сливаются,
    а хэш имени давал по три пурпурных подряд.
    """
    hue = (number * 137.508) % 360.0
    light = 0.40 + (number % 3) * 0.055
    return _hsl(hue, 0.44, light)


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


def _decode_rle(flat) -> list:
    """Пары «значение, сколько раз» обратно в ряд значений."""
    out = []
    for index in range(0, len(flat) - 1, 2):
        out.extend([flat[index]] * int(flat[index + 1]))
    return out


class Atlas(ttk.Frame):
    """Карта мира со всеми слоями и карточкой гекса."""

    def __init__(self, master, fonts=None):
        ttk.Frame.__init__(self, master)
        self.fonts = fonts or {}
        self.world = None
        self.wmap = None
        self.cell = 6
        self.off_x = 0.0            # какой угол карты сейчас в левом верхнем
        self.off_y = 0.0
        self._photo = None
        self._spans = {}            # (ширина, чётность ряда) -> ломти
        self._frames = []
        self._frame_slots = None
        self._frame_year = 0
        self._colors = {}
        self._names = {}
        self._region_tones = {}
        self._drag = None
        self._redraw_job = None
        self._marks = {}            # что нарисовано поверх картинки
        self._roads = None          # дороги держав: считаются раз и надолго
        self._picked = -1

        self.mode_var = tk.StringVar(value=MODES[0][0])
        self.year_var = tk.IntVar(value=0)
        self.show_cities = tk.BooleanVar(value=True)
        self.show_routes = tk.BooleanVar(value=True)
        self.show_roads = tk.BooleanVar(value=False)
        self.show_lairs = tk.BooleanVar(value=True)
        self.show_tribes = tk.BooleanVar(value=False)
        self.note_var = tk.StringVar(value="")

        self._build()

    # ------------------------------------------------------------------
    # Устройство панели
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Две строки вместо одной: при крупном шрифте всё в один ряд не
        # помещается, и кнопки приближения уезжают под галочки.
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 2))
        ttk.Label(top, text="Показывать:").pack(side="left", padx=(0, 6))
        box = ttk.Combobox(top, textvariable=self.mode_var, state="readonly",
                           width=18, values=[name for name, _ in MODES])
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda _e: self.redraw())
        ttk.Button(top, text="Вся карта",
                   command=self.fit).pack(side="right")
        ttk.Button(top, text="+", width=3,
                   command=lambda: self.zoom(1)).pack(side="right", padx=2)
        ttk.Button(top, text="−", width=3,
                   command=lambda: self.zoom(-1)).pack(side="right")

        marks = ttk.Frame(self)
        marks.pack(fill="x", pady=(0, 2))
        ttk.Label(marks, text="Отмечать:").pack(side="left", padx=(0, 6))
        for text, holder in (("города", self.show_cities),
                             ("торговые пути", self.show_routes),
                             ("дороги", self.show_roads),
                             ("логова", self.show_lairs),
                             ("племена и лагеря", self.show_tribes)):
            ttk.Checkbutton(marks, text=text, variable=holder,
                            command=self.redraw).pack(side="left", padx=4)

        self.year_bar = ttk.Frame(self)
        self.year_bar.pack(fill="x", pady=(0, 4))
        ttk.Label(self.year_bar, text="Год:").pack(side="left", padx=(0, 6))
        self.year_scale = ttk.Scale(self.year_bar, from_=0, to=1,
                                    orient="horizontal",
                                    command=self._year_moved)
        self.year_scale.pack(side="left", fill="x", expand=True)
        self.year_label = ttk.Label(self.year_bar, text="—", width=26,
                                    anchor="w")
        self.year_label.pack(side="left", padx=8)

        # Перегородку между картой и карточкой человек двигает сам: кому
        # нужна карта во всю ширину, тот уберёт карточку к краю.
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

        side = ttk.Frame(split, width=330)
        split.add(side, weight=1)
        side.pack_propagate(False)
        ttk.Label(side, textvariable=self.note_var, anchor="w",
                  wraplength=320).pack(fill="x", pady=(0, 4))
        self.card = tk.Text(side, wrap="word", width=40,
                            font=self.fonts.get("mono"), bg="#211f2c",
                            fg="#e8e2d0", relief="flat", padx=8, pady=6)
        self.card.pack(fill="both", expand=True)
        self.card.insert("1.0", "Щёлкните по гексу — и здесь будет всё, "
                                "что о нём известно.")
        self.card.config(state="disabled")

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
            self._split.sashpos(0, width - 330)
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
        self._frames = []
        self._colors = {}
        self._names = {}
        # Земли получают цвета в одном и том же порядке — чтобы карта
        # одного мира выглядела всегда одинаково.
        self._region_tones = {region_id: _region_color(number)
                              for number, region_id
                              in enumerate(sorted(world.regions))}
        recorder = getattr(world, "map_recorder", None)
        if recorder is not None and recorder.frames:
            self._frames = recorder.frames
            for polity_id, slot in recorder.slots.items():
                polity = world.polities.get(polity_id)
                if polity is None:
                    continue
                from worldgen.chronicle_map import realm_color
                self._colors[slot] = realm_color(polity, slot)
                self._names[slot] = polity.full_name
        self._frame_slots = None
        self._roads = None
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
            return
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
                          "двигает, щелчок рассказывает." %
                          (self.wmap.width, self.wmap.height))
        self.fit()

    def clear(self) -> None:
        self.world = None
        self.wmap = None
        self._frames = []
        self._roads = None
        self._picked = -1
        self.canvas.delete("all")
        self.note_var.set("")
        self._blank_card()

    def _blank_card(self) -> None:
        self.card.config(state="normal")
        self.card.delete("1.0", "end")
        self.card.insert("1.0", "Щёлкните по гексу — и здесь будет всё, "
                                "что о нём известно.")
        self.card.config(state="disabled")

    # ------------------------------------------------------------------
    # Геометрия гексов
    # ------------------------------------------------------------------

    def _hex_size(self):
        cell = self.cell
        return cell, max(2, int(round(cell * HEX_TALL))), \
            max(1, int(round(cell * ROW_STEP)))

    def _hex_spans(self, cell: int, odd: int = 0) -> list:
        """Ломти гекса по строкам: (сдвиг сверху, от, до) в точках.

        Считаются не «на глазок», а по-честному: точка достаётся тому
        гексу, чей центр к ней ближе. Тогда соседние гексы сходятся без
        щелей — а щели на карте в полтораста тысяч клеток видно сразу,
        и карта выглядит грязной.

        У чётных и нечётных рядов разбиение своё: нечётный ряд сдвинут
        вбок на полклетки, а полклетки при нечётной ширине — не поровну.
        """
        spans = self._spans.get((cell, odd))
        if spans is not None:
            return spans
        _, height, step = self._hex_size()
        if cell <= 2:
            # Мельче трёх точек гекс всё равно не разглядеть: кладём
            # прямоугольники, они смыкаются без единого зазора.
            spans = [(dy, 0, cell) for dy in range(step)]
            self._spans[(cell, odd)] = spans
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

        spans = []
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
                spans.append((dy, left, right + 1))
        self._spans[(cell, odd)] = spans
        return spans

    def _hex_origin(self, col: int, row: int):
        """Левый верхний угол гекса в точках всей карты."""
        cell, height, step = self._hex_size()
        x = col * cell + (cell // 2 if row % 2 else 0)
        y = row * step - (height - step) / 2.0
        return x, y

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

    # ------------------------------------------------------------------
    # Цвета
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

    def _road_paths(self) -> list:
        """Дороги держав по гексам.

        Каждая дорога — поиск пути от столицы к городу, и таких путей
        сотни. Поэтому считаются они один раз за мир и только тогда,
        когда их попросили показать.
        """
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

    def _colorizer(self):
        """Готовая раскраска: по гексу — цвет. Считается раз на перерисовку."""
        wmap = self.wmap
        mode = self._mode()
        flags = wmap.layer(wm.L_FLAGS)
        biome = wmap.layer(wm.L_BIOME)

        def water(index):
            return flags is not None and (flags[index] & 3)

        if mode == "biome":
            def colour(index):
                value = biome[index] if biome is not None else 0
                return (BIOME_COLORS[value] if value < len(BIOME_COLORS)
                        else "#777777")
            return colour

        if mode == "realm":
            slots = self._frame_for_year()

            def colour(index):
                if water(index):
                    return WATER_DIM
                if slots is None or index >= len(slots):
                    return LAND_DIM
                slot = slots[index]
                if slot < 0:
                    return LAND_DIM
                return self._colors.get(slot, "#8a8a8a")
            return colour

        if mode == "region":
            link = getattr(self.world, "map_link", None)
            owner = getattr(link, "region_of_hex", {}) if link else {}
            tones = self._region_tones

            def colour(index):
                if water(index):
                    return WATER_DIM
                return tones.get(owner.get(index)) or LAND_DIM
            return colour

        if mode == "elev":
            def colour(index):
                if water(index):
                    depth = min(1.0, max(0.0, -wmap.elevation_m(index) / 6000.0))
                    return _mix("#2f86a0", "#081d30", depth)
                part = min(1.0, max(0.0, wmap.elevation_m(index) / 5000.0))
                return _mix("#4e7a42", "#f1f5f7", part)
            return colour

        layer, low, high, span = {
            "fert": (wm.L_FERTILITY, "#3a3326", "#8fd15a", 1.0),
            "wild": (wm.L_SAVAGERY, "#2f3a34", "#c0552f", 255.0),
            "risk": (wm.L_EVENTCHANCE, "#243042", "#e08a3c", 255.0),
        }.get(mode, (wm.L_MAGIC, "", "", 0.0))

        if mode == "magic":
            magic = wmap.layer(wm.L_MAGIC)

            def colour(index):
                value = float(magic[index]) if magic is not None else 0.0
                if abs(value) < 0.08:
                    return WATER_DIM if water(index) else "#2b2b33"
                if value > 0:
                    return _mix("#2b2b33", "#f0e39a", min(1.0, value))
                return _mix("#2b2b33", "#a03f8f", min(1.0, -value))
            return colour

        data = wmap.layer(layer)

        def colour(index):
            if water(index):
                return WATER_DIM
            value = float(data[index]) / span if data is not None else 0.0
            return _mix(low, high, value)
        return colour

    # ------------------------------------------------------------------
    # Рисование
    # ------------------------------------------------------------------

    def fit(self) -> None:
        """Вся карта целиком в окно."""
        if self.wmap is None:
            return
        self.canvas.update_idletasks()
        width = max(200, self.canvas.winfo_width())
        height = max(200, self.canvas.winfo_height())
        by_width = width / float(self.wmap.width + 1)
        by_height = height / float(self.wmap.height * ROW_STEP + 1)
        self.cell = max(MIN_CELL, min(MAX_CELL, int(min(by_width, by_height))))
        # Куда встанет карта, решит сама перерисовка: что не заполнило
        # окно, она поставит посередине.
        self.off_x = 0.0
        self.off_y = 0.0
        self.redraw()

    def zoom(self, delta: int, focus=None) -> None:
        if self.wmap is None:
            return
        before = self.cell
        step = 1 if before < 10 else 2
        self.cell = max(MIN_CELL, min(MAX_CELL, before + delta * step))
        if self.cell == before:
            return
        ratio = float(self.cell) / before
        if focus is None:
            focus = (self.canvas.winfo_width() / 2.0,
                     self.canvas.winfo_height() / 2.0)
        self.off_x = (self.off_x + focus[0]) * ratio - focus[0]
        self.off_y = (self.off_y + focus[1]) * ratio - focus[1]
        self.redraw()

    def redraw(self) -> None:
        """Перерисовать видимый кусок карты и всё, что на нём стоит."""
        if self.wmap is None or not self.winfo_exists():
            return
        self.canvas.update_idletasks()
        width = max(50, self.canvas.winfo_width())
        height = max(50, self.canvas.winfo_height())
        cell, hex_h, step = self._hex_size()
        full_w = self.wmap.width * cell + cell // 2
        full_h = self.wmap.height * step + (hex_h - step)
        # Что меньше окна — ставим посередине; что больше — не даём
        # утащить за край дальше, чем на сорок точек.
        slack_x, slack_y = full_w - width, full_h - height
        self.off_x = (slack_x / 2.0 if slack_x < 0 else
                      max(-40.0, min(self.off_x, slack_x + 40)))
        self.off_y = (slack_y / 2.0 if slack_y < 0 else
                      max(-40.0, min(self.off_y, slack_y + 40)))

        colour = self._colorizer()
        by_parity = (self._hex_spans(cell, 0), self._hex_spans(cell, 1))
        rows = [[GRID_BG] * width for _ in range(height)]

        first_row = max(0, int((self.off_y - 2 * hex_h) // step))
        last_row = min(self.wmap.height - 1,
                       int((self.off_y + height) // step) + 2)
        first_col = max(0, int((self.off_x - 2 * cell) // cell))
        last_col = min(self.wmap.width - 1,
                       int((self.off_x + width) // cell) + 2)
        for row in range(first_row, last_row + 1):
            base = row * self.wmap.width
            spans = by_parity[row % 2]
            for col in range(first_col, last_col + 1):
                index = base + col
                ox, oy = self._hex_origin(col, row)
                px = int(ox - self.off_x)
                py = int(oy - self.off_y)
                tone = colour(index)
                for dy, x0, x1 in spans:
                    line = py + dy
                    if line < 0 or line >= height:
                        continue
                    left = px + x0
                    right = px + x1
                    if right <= 0 or left >= width:
                        continue
                    rows[line][max(0, left):min(width, right)] = \
                        [tone] * (min(width, right) - max(0, left))

        image = tk.PhotoImage(width=width, height=height)
        image.put(" ".join("{%s}" % " ".join(line) for line in rows))
        self._photo = image
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=image, anchor="nw")
        self._draw_marks()
        self._update_year_label()

    def _draw_marks(self) -> None:
        """Города, пути, логова и прочее — поверх картинки.

        Всё, что стоит на земле, показано на выбранный год: город,
        основанный позже, ещё не заложен, а погибший — уже брошен. Так
        ползунок листает не только границы держав, но и весь мир.
        """
        world = self.world
        if world is None:
            return
        cell, hex_h, step = self._hex_size()
        year = self._year_now()

        def point(index):
            col, row = index % self.wmap.width, index // self.wmap.width
            ox, oy = self._hex_origin(col, row)
            return ox - self.off_x + cell / 2.0, oy - self.off_y + hex_h / 2.0

        seam = self.wmap.width * cell / 2.0

        def thread(path, fill, width=1, dash=None):
            """Ломаная по гексам. На замкнутой карте путь может уйти за
            правый край и вернуться слева — такой шаг рвём, иначе через
            весь мир протянется нитка, которой нет."""
            piece = []
            last = None
            for index in path:
                x, y = point(index)
                if last is not None and abs(x - last) > seam:
                    if len(piece) >= 4:
                        self.canvas.create_line(*piece, fill=fill,
                                                width=width, dash=dash)
                    piece = []
                piece.extend((x, y))
                last = x
            if len(piece) >= 4:
                self.canvas.create_line(*piece, fill=fill, width=width,
                                        dash=dash)

        if self.show_roads.get():
            for path in self._road_paths():
                thread(path, "#8a7a5a")
        if self.show_routes.get():
            for route in world.routes.values():
                if not _alive_at(route.opened, route.closed, year):
                    continue
                thread(route.path or (), "#c9a34a", dash=(3, 3))

        if self.show_lairs.get():
            for lair in (self.wmap.lairs or ()):
                index = int(lair.get("i", -1))
                if index < 0:
                    continue
                x, y = point(index)
                size = max(3, cell // 2)
                self.canvas.create_polygon(x, y - size, x + size, y,
                                           x, y + size, x - size, y,
                                           fill="#b0353a", outline="#f0d0a0")
        if self.show_tribes.get():
            for item in world.tribes.values():
                if item.hex_index < 0:
                    continue
                if not _alive_at(item.founded, item.ended, year):
                    continue
                x, y = point(item.hex_index)
                size = max(2, cell // 3)
                self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                        fill="#8a7448", outline="")
            for camp in world.camps.values():
                if camp.hex_index < 0:
                    continue
                if not _alive_at(camp.founded, camp.ended, year):
                    continue
                x, y = point(camp.hex_index)
                size = max(2, cell // 3)
                self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                        fill="#6b3b2e", outline="")

        if self.show_cities.get():
            for item in world.settlements.values():
                if item.hex_index < 0:
                    continue
                if not _alive_at(item.founded, item.ended, year):
                    continue
                x, y = point(item.hex_index)
                size = 2 + min(5, int(math.sqrt(max(1, item.population)) / 40))
                if item.is_capital:
                    self.canvas.create_rectangle(
                        x - size, y - size, x + size, y + size,
                        fill="#f0e0b0", outline="#2a2620")
                else:
                    self.canvas.create_oval(x - size, y - size, x + size,
                                            y + size, fill="#e8d8a8",
                                            outline="#2a2620")
                if cell >= 12:
                    self.canvas.create_text(x, y - size - 7, text=item.name,
                                            fill="#f0e6cc",
                                            font=self.fonts.get("ui"))
        if self._picked >= 0:
            x, y = point(self._picked)
            size = max(4, cell // 2 + 2)
            self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                    outline="#ffd970", width=2)

    # ------------------------------------------------------------------
    # Мышь и год
    # ------------------------------------------------------------------

    def _resized(self, _event=None) -> None:
        self._schedule()

    def _schedule(self, delay: int = 140) -> None:
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
        self.off_x = ox - dx
        self.off_y = oy - dy
        self.canvas.delete("all")
        if self._photo is not None:
            self.canvas.create_image(-(self.off_x - ox), -(self.off_y - oy),
                                     image=self._photo, anchor="nw")
        self._schedule(80)

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
        # Год меняет не только окраску держав, но и города, пути и племена,
        # поэтому перерисовывать надо в любом случае.
        self._schedule(60)

    def _update_year_label(self) -> None:
        if not self._frames:
            self.year_label.config(text="кадров нет")
            return
        index = max(0, min(len(self._frames) - 1, int(self.year_var.get())))
        year = self._frames[index]["y"]
        era = self.world.era_at(year) if self.world else None
        self.year_label.config(text="%d год — %s"
                               % (year, era.name if era else "—"))

    # ------------------------------------------------------------------
    # Карточка гекса
    # ------------------------------------------------------------------

    def describe(self, index: int) -> None:
        """Всё, что известно про этот гекс — человеческим языком."""
        wmap, world = self.wmap, self.world
        if wmap is None or world is None:
            return
        col, row = index % wmap.width, index // wmap.width
        lines = ["ГЕКС %d — столбец %d, строка %d" % (index, col, row), ""]

        biome = wmap.layer(wm.L_BIOME)
        value = biome[index] if biome is not None else 0
        name = (BIOME_NAMES[value] if value < len(BIOME_NAMES)
                else "неведомая земля")
        lines.append("  %s" % name)
        lines.append("  высота ......... %d м" % round(wmap.elevation_m(index)))
        temp = wmap.layer(wm.L_TEMP)
        moist = wmap.layer(wm.L_MOIST)
        if temp is not None:
            lines.append("  температура .... %+.1f °C" % temp[index])
        if moist is not None:
            lines.append("  влажность ...... %.2f" % moist[index])
        fert = wmap.layer(wm.L_FERTILITY)
        if fert is not None:
            lines.append("  плодородие ..... %.2f" % fert[index])
        rich = wmap.layer(wm.L_RICHNESS)
        if rich is not None:
            lines.append("  живность ....... %d из 255" % rich[index])
        aqua = wmap.layer(wm.L_AQUIFER)
        if aqua is not None:
            level = min(2, int(aqua[index]))
            lines.append("  вода под землёй  %s" % AQUIFER_NAMES[level])
        savage = wmap.layer(wm.L_SAVAGERY)
        if savage is not None:
            level = 2 if savage[index] >= 168 else 1 if savage[index] >= 84 else 0
            lines.append("  округа ......... %s" % SAVAGERY_NAMES[level])
        magic = wmap.layer(wm.L_MAGIC)
        if magic is not None and abs(magic[index]) > 0.05:
            lines.append("  магия .......... %+.2f (%s)"
                         % (magic[index],
                            "светлая" if magic[index] > 0 else "тёмная"))

        water = []
        if wmap.is_ocean(index):
            water.append("океан")
        if wmap.is_lake(index):
            water.append("озеро")
        if wmap.is_river(index):
            water.append("река")
        if wmap.is_coast(index):
            water.append("берег")
        if water:
            lines.append("  вода ........... %s" % ", ".join(water))

        mask = wmap.layer(wm.L_EVENTMASK)
        if mask is not None and mask[index]:
            bits = int(mask[index]) & 0xFFFF
            threats = [EVENT_NAMES[i] for i in range(len(EVENT_NAMES))
                       if bits & (1 << i)]
            if threats:
                lines.append("")
                lines.append("  СЛУЧАЕТСЯ ТУТ")
                lines.append("    " + ", ".join(threats))

        ores = wmap.minerals.get(str(index))
        if ores:
            lines.append("")
            lines.append("  НЕДРА")
            for item in ores[:6]:
                lines.append("    %s — %s" % (item[0], item[1]))

        # --- что тут в истории ---
        link = getattr(world, "map_link", None)
        region_id = (getattr(link, "region_of_hex", {}) or {}).get(index)
        region = world.regions.get(region_id) if region_id else None
        story = []
        if region is not None:
            story.append("земля по имени %s" % region.name)
        # Карта зовёт свои материки и хребты на своём языке; в летописи
        # они уже переложены на кириллицу, и тут должно быть так же.
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
                # У вершин карта уже приписала «г.» — своё имя дальше.
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
        if story:
            lines.append("")
            lines.append("  ЗДЕСЬ")
            for row_text in story:
                lines.append("    %s" % row_text)

        year = self._year_now()
        here = []
        for item in world.settlements.values():
            if item.hex_index != index:
                continue
            if not _alive_at(item.founded, item.ended, year):
                continue
            polity = world.polities.get(item.polity_id)
            here.append("%s — %d жителей%s"
                        % (item.full_name, item.population,
                           ", столица" if item.is_capital else ""))
            if polity is not None:
                here.append("держава: %s" % polity.full_name)
        for item in world.tribes.values():
            if item.hex_index == index and _alive_at(item.founded, item.ended,
                                                     year):
                here.append("племя по имени %s — %d душ"
                            % (item.name, item.population))
        for item in world.camps.values():
            if item.hex_index == index and _alive_at(item.founded, item.ended,
                                                     year):
                here.append("%s по имени %s" % (item.word.lower(), item.name))
        if here:
            lines.append("")
            lines.append("  ЛЮДИ В %d ГОДУ" % year)
            for row_text in here:
                lines.append("    %s" % row_text)

        # Быль привязана к месту, а не к гексу: собираем места этого гекса
        # и спрашиваем у мира, что тут рассказывают. Показываем только
        # то, что к выбранному году уже случилось, — ползунок года
        # управляет и этим.
        places = [item.id for item in world.settlements.values()
                  if item.hex_index == index]
        places += [item.id for item in world.sites.values()
                   if item.hex_index == index]
        told = []
        for place_id in places:
            for story in world.stories_at(place_id):
                if story.began.year <= year and story.id not in \
                        [item[0] for item in told]:
                    told.append((story.id, story))
        if told:
            told.sort(key=lambda item: item[1].began.ordinal)
            lines.append("")
            lines.append("  ЧТО ТУТ РАССКАЗЫВАЮТ")
            for _, story in told[:8]:
                # Карточка узкая: год и имя, а подробности — в разделе.
                lines.append("    %5d  %s" % (story.began.year, story.title))

        slots = self._frame_for_year()
        if slots is not None and index < len(slots):
            slot = slots[index]
            if slot >= 0:
                lines.append("")
                lines.append("  В %d ГОДУ ЗЕМЛЁЙ ВЛАДЕЛА" % self._frame_year)
                lines.append("    %s" % self._names.get(slot, "чья-то держава"))

        self.card.config(state="normal")
        self.card.delete("1.0", "end")
        self.card.insert("1.0", "\n".join(lines))
        self.card.config(state="disabled")
