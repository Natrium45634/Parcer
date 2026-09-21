# -*- coding: utf-8 -*-
"""Мастер создания мира: три шага до первой строки летописи.

Программа больше не начинается с таблиц. Она начинается с вопроса, какой
мир нужен:

1. **Мир.** Сид и длительность истории — этого хватит, чтобы нажать
   «Создать». А если хочется своего, рядом лежат шестьдесят восемь шкал:
   от скорости размножения народов до частоты бедствий, смут и
   заговоров. Каждую можно зафиксировать, и тогда бросок костей её не
   тронет.
2. **Карта.** Случайная гексовая карта, которую программа делает сама,
   готовый файл .world или вовсе без карты — тогда земли придумает
   движок. Случайную карту видно сразу и можно бросать заново, пока не
   понравится.
3. **Создание.** Короткая сводка того, что выбрано, и одна кнопка.

Окно мастера — обычный кадр, который живёт до первого готового мира;
потом на его место встают вкладки летописи, а вернуться сюда можно
кнопкой «Новый мир».
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from worldgen import mapforge, tuning
from worldgen.engine import Settings
from worldgen.rng import Rng, random_seed_text, seed_to_int

DENSITY_CHOICES = (
    ("пореже — только заметное", 0.6),
    ("как задумано", 1.0),
    ("погуще — мир кипит", 1.6),
)

MAP_RANDOM = "случайная"
MAP_FILE = "файл"
MAP_NONE = "без карты"

PREVIEW_MAX = 520          # во сколько точек шириной показывать карту


class Wizard(ttk.Frame):
    """Три шага: мир, карта, создание."""

    def __init__(self, master, on_start, fonts=None):
        ttk.Frame.__init__(self, master)
        self.on_start = on_start
        self.ui_font = (fonts or {}).get("ui")
        self.mono = (fonts or {}).get("mono")

        self.seed_var = tk.StringVar(value=random_seed_text())
        self.years_var = tk.StringVar(value="10000")
        self.regions_var = tk.StringVar(value="18")
        self.density_var = tk.StringVar(value=DENSITY_CHOICES[1][0])

        self.knob_vars = {}        # ключ -> IntVar
        self.knob_locks = {}       # ключ -> BooleanVar
        self.knob_labels = {}

        self.map_mode = tk.StringVar(value=MAP_RANDOM)
        self.map_seed_var = tk.StringVar(value=random_seed_text())
        self.map_size_var = tk.StringVar(value=mapforge.DEFAULT_SIZE)
        self.map_land = tk.IntVar(value=34)
        self.map_rough = tk.IntVar(value=50)
        self.map_warm = tk.IntVar(value=50)
        self.map_wet = tk.IntVar(value=50)
        self.map_magic = tk.IntVar(value=50)
        self.map_path = ""
        self.map_preview = None    # сделанная карта (WorldMap)
        self._photo = None

        self.steps = ttk.Notebook(self)
        self.steps.pack(fill="both", expand=True, padx=6, pady=6)
        self._build_world_step()
        self._build_map_step()
        self._build_start_step()

    # ------------------------------------------------------------------
    # Шаг 1: мир
    # ------------------------------------------------------------------

    def _build_world_step(self) -> None:
        page = ttk.Frame(self.steps, padding=12)
        self.steps.add(page, text="  1. Мир  ")

        head = ttk.Frame(page)
        head.pack(fill="x")
        ttk.Label(head, text="Сид:").grid(row=0, column=0, sticky="e",
                                          padx=(0, 6))
        ttk.Entry(head, textvariable=self.seed_var, width=24).grid(
            row=0, column=1, sticky="w")
        ttk.Button(head, text="Случайный", command=self.roll_seed).grid(
            row=0, column=2, padx=6)
        ttk.Label(head, text="Лет истории:").grid(row=0, column=3, sticky="e",
                                                  padx=(18, 6))
        ttk.Spinbox(head, from_=50, to=100000, increment=500, width=10,
                    textvariable=self.years_var).grid(row=0, column=4,
                                                      sticky="w")
        ttk.Label(head, text="Плотность событий:").grid(
            row=1, column=0, sticky="e", padx=(0, 6), pady=(8, 0))
        ttk.Combobox(head, textvariable=self.density_var, state="readonly",
                     width=30,
                     values=[name for name, _ in DENSITY_CHOICES]).grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(head, text="Земель (без карты):").grid(
            row=1, column=3, sticky="e", padx=(18, 6), pady=(8, 0))
        ttk.Spinbox(head, from_=6, to=60, increment=1, width=6,
                    textvariable=self.regions_var).grid(row=1, column=4,
                                                        sticky="w",
                                                        pady=(8, 0))

        ttk.Label(page, text=(
            "Этого хватит: нажмите «3. Создание» — и мир будет готов.\n"
            "Ниже — тонкая настройка: каждое число движка своей шкалой."),
            justify="left").pack(anchor="w", pady=(12, 6))

        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Бросить кости",
                   command=self.roll_knobs).pack(side="left")
        ttk.Button(bar, text="Всё как задумано",
                   command=self.reset_knobs).pack(side="left", padx=6)
        ttk.Button(bar, text="Снять все замки",
                   command=self.unlock_all).pack(side="left")
        self.knob_note = tk.StringVar(value="Все шкалы стоят посередине.")
        ttk.Label(bar, textvariable=self.knob_note).pack(side="left", padx=12)

        self._build_knobs(page)

    def _build_knobs(self, page) -> None:
        """Шкалы всех настроек — списком с прокруткой."""
        holder = ttk.Frame(page)
        holder.pack(fill="both", expand=True)
        canvas = tk.Canvas(holder, highlightthickness=0, bg="#231f30")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda event: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def wheel(event):
            step = -1 if getattr(event, "delta", 0) > 0 or event.num == 4 else 1
            canvas.yview_scroll(step, "units")

        for widget in (canvas, inner):
            widget.bind("<MouseWheel>", wheel)
            widget.bind("<Button-4>", wheel)
            widget.bind("<Button-5>", wheel)

        row = 0
        for group, knobs in tuning.groups():
            ttk.Label(inner, text=group.upper()).grid(
                row=row, column=0, columnspan=4, sticky="w", pady=(10, 2))
            row += 1
            for knob in knobs:
                lock = tk.BooleanVar(value=False)
                position = tk.IntVar(value=tuning.MIDDLE)
                self.knob_locks[knob.key] = lock
                self.knob_vars[knob.key] = position
                ttk.Checkbutton(inner, variable=lock).grid(row=row, column=0,
                                                           sticky="w")
                ttk.Label(inner, text=knob.name, width=38, anchor="w").grid(
                    row=row, column=1, sticky="w")
                scale = ttk.Scale(inner, from_=0, to=100, length=220,
                                  orient="horizontal")
                scale.set(tuning.MIDDLE)
                scale.grid(row=row, column=2, sticky="w", padx=6)
                label = ttk.Label(inner, text=self._knob_text(knob,
                                                              tuning.MIDDLE),
                                  width=22, anchor="w")
                label.grid(row=row, column=3, sticky="w")
                self.knob_labels[knob.key] = label

                def moved(value, key=knob.key, holder=position, tag=knob,
                          widget=scale):
                    holder.set(int(float(value)))
                    self.knob_labels[key].config(
                        text=self._knob_text(tag, holder.get()))
                    self._refresh_note()

                scale.config(command=moved)
                position.trace_add("write", lambda *_, s=scale, v=position:
                                   s.set(v.get()))
                row += 1

    def _knob_text(self, knob, position: int) -> str:
        if position == tuning.MIDDLE:
            return "как задумано"
        share = tuning.value_of(knob, position) / max(
            1e-9, tuning.base_value(knob.targets[0]))
        word = "чаще" if position > tuning.MIDDLE else "реже"
        if knob.invert:
            word = "чаще" if position > tuning.MIDDLE else "реже"
        return "%d — в %.1f раза %s" % (position,
                                        share if share >= 1 else 1.0 / share,
                                        word)

    def _refresh_note(self) -> None:
        moved = sum(1 for key, var in self.knob_vars.items()
                    if var.get() != tuning.MIDDLE)
        locked = sum(1 for var in self.knob_locks.values() if var.get())
        if not moved:
            self.knob_note.set("Все шкалы стоят посередине.")
        else:
            self.knob_note.set("Сдвинуто шкал: %d; закреплено: %d"
                               % (moved, locked))

    # --- действия шага 1 ---

    def roll_seed(self) -> None:
        self.seed_var.set(random_seed_text())

    def roll_knobs(self) -> None:
        rng = Rng(seed_to_int("knobs:%s" % random_seed_text()))
        locked = [key for key, var in self.knob_locks.items() if var.get()]
        current = {key: var.get() for key, var in self.knob_vars.items()}
        rolled = tuning.random_positions(rng, locked=locked, current=current)
        for key, value in rolled.items():
            if key in self.knob_vars:
                self.knob_vars[key].set(int(value))
                knob = tuning.KNOBS_BY_KEY.get(key)
                if knob is not None:
                    self.knob_labels[key].config(
                        text=self._knob_text(knob, int(value)))
        self._refresh_note()

    def reset_knobs(self) -> None:
        for key, var in self.knob_vars.items():
            if self.knob_locks[key].get():
                continue
            var.set(tuning.MIDDLE)
            knob = tuning.KNOBS_BY_KEY.get(key)
            if knob is not None:
                self.knob_labels[key].config(
                    text=self._knob_text(knob, tuning.MIDDLE))
        self._refresh_note()

    def unlock_all(self) -> None:
        for var in self.knob_locks.values():
            var.set(False)
        self._refresh_note()

    # ------------------------------------------------------------------
    # Шаг 2: карта
    # ------------------------------------------------------------------

    def _build_map_step(self) -> None:
        page = ttk.Frame(self.steps, padding=12)
        self.steps.add(page, text="  2. Карта  ")

        picker = ttk.Frame(page)
        picker.pack(fill="x")
        ttk.Radiobutton(picker, text="Случайная гексовая карта",
                        variable=self.map_mode, value=MAP_RANDOM,
                        command=self._map_mode_changed).grid(row=0, column=0,
                                                             sticky="w")
        ttk.Radiobutton(picker, text="Своя карта .world",
                        variable=self.map_mode, value=MAP_FILE,
                        command=self._map_mode_changed).grid(row=0, column=1,
                                                             sticky="w",
                                                             padx=18)
        ttk.Radiobutton(picker, text="Без карты — земли придумает движок",
                        variable=self.map_mode, value=MAP_NONE,
                        command=self._map_mode_changed).grid(row=0, column=2,
                                                             sticky="w")

        self.map_box = ttk.Frame(page)
        self.map_box.pack(fill="x", pady=(10, 0))
        ttk.Label(self.map_box, text="Сид карты:").grid(row=0, column=0,
                                                        sticky="e",
                                                        padx=(0, 6))
        ttk.Entry(self.map_box, textvariable=self.map_seed_var, width=20).grid(
            row=0, column=1, sticky="w")
        ttk.Button(self.map_box, text="Случайный",
                   command=lambda: self.map_seed_var.set(
                       random_seed_text())).grid(row=0, column=2, padx=6)
        ttk.Label(self.map_box, text="Размер:").grid(row=0, column=3,
                                                     sticky="e", padx=(18, 6))
        ttk.Combobox(self.map_box, textvariable=self.map_size_var,
                     state="readonly", width=12,
                     values=list(mapforge.SIZES)).grid(row=0, column=4,
                                                       sticky="w")

        sliders = (("Сколько суши", self.map_land),
                   ("Насколько изрезан рельеф", self.map_rough),
                   ("Тепло", self.map_warm),
                   ("Влага", self.map_wet),
                   ("Магия", self.map_magic))
        for number, (name, var) in enumerate(sliders, start=1):
            ttk.Label(self.map_box, text=name, width=26, anchor="w").grid(
                row=number, column=0, columnspan=2, sticky="w", pady=(6, 0))
            scale = ttk.Scale(self.map_box, from_=0, to=100, length=240,
                              orient="horizontal")
            scale.set(var.get())
            scale.grid(row=number, column=2, columnspan=3, sticky="w",
                       pady=(6, 0))
            scale.config(command=lambda value, holder=var:
                         holder.set(int(float(value))))

        buttons = ttk.Frame(page)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Сделать карту",
                   command=self.make_map).pack(side="left")
        ttk.Button(buttons, text="Ещё раз, по-другому",
                   command=self.reroll_map).pack(side="left", padx=6)
        ttk.Button(buttons, text="Сохранить .world…",
                   command=self.save_map).pack(side="left")
        ttk.Button(buttons, text="Выбрать файл .world…",
                   command=self.choose_map).pack(side="left", padx=6)

        self.map_note = tk.StringVar(
            value="Карта ещё не сделана. Нажмите «Сделать карту».")
        ttk.Label(page, textvariable=self.map_note, anchor="w").pack(
            fill="x", pady=(10, 4))
        self.map_canvas = tk.Canvas(page, height=300, bg="#1b1826",
                                    highlightthickness=0)
        self.map_canvas.pack(fill="both", expand=True)

    def _map_mode_changed(self) -> None:
        mode = self.map_mode.get()
        state = "normal" if mode == MAP_RANDOM else "disabled"
        for child in self.map_box.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass
        if mode == MAP_NONE:
            self.map_note.set("Мир без карты: земли движок придумает сам.")
        elif mode == MAP_FILE:
            self.map_note.set("Выбран файл: %s"
                              % (os.path.basename(self.map_path)
                                 or "пока никакой"))

    def make_map(self) -> None:
        self.map_mode.set(MAP_RANDOM)
        self._map_mode_changed()
        try:
            wmap = mapforge.forge(
                self.map_seed_var.get() or random_seed_text(),
                size=self.map_size_var.get(),
                land_share=self.map_land.get() / 100.0,
                roughness=self.map_rough.get() / 100.0,
                warmth=self.map_warm.get() / 100.0,
                wetness=self.map_wet.get() / 100.0,
                magic=self.map_magic.get() / 100.0)
        except Exception as error:               # показать, а не молчать
            messagebox.showerror("Карта не вышла", repr(error))
            return
        self.map_preview = wmap
        facts = wmap.describe()
        self.map_note.set("%s, суша %s, логов %s, вершин %s, климат-событий %s"
                          % (facts["Размер"], facts["Суша"], facts["Логовов"],
                             facts["Вершин"], facts["Климат-событий"]))
        self._draw_map(wmap)

    def reroll_map(self) -> None:
        self.map_seed_var.set(random_seed_text())
        self.make_map()

    def _draw_map(self, wmap) -> None:
        grid = mapforge.color_grid(wmap)
        image = tk.PhotoImage(width=wmap.width, height=wmap.height)
        for y, row in enumerate(grid):
            image.put("{%s}" % " ".join(row), to=(0, y))
        zoom = max(1, min(6, PREVIEW_MAX // max(1, wmap.width)))
        image = image.zoom(zoom, zoom)
        self._photo = image                    # иначе картинку соберёт сборщик
        self.map_canvas.delete("all")
        self.map_canvas.config(height=min(360, wmap.height * zoom))
        self.map_canvas.create_image(6, 6, image=image, anchor="nw")

    def save_map(self) -> None:
        if self.map_preview is None:
            messagebox.showinfo("Нечего сохранять", "Сначала сделайте карту.")
            return
        path = filedialog.asksaveasfilename(
            title="Сохранить карту", defaultextension=".world",
            initialfile="%s.world" % (self.map_seed_var.get() or "карта"),
            filetypes=[("Карта мира", "*.world"), ("Все файлы", "*.*")])
        if not path:
            return
        mapforge.save(self.map_preview, path)
        messagebox.showinfo("Готово", "Карта записана:\n%s" % path)

    def choose_map(self) -> None:
        path = filedialog.askopenfilename(
            title="Карта мира .world",
            filetypes=[("Карта мира", "*.world"), ("Все файлы", "*.*")])
        if not path:
            return
        self.map_path = path
        self.map_mode.set(MAP_FILE)
        self._map_mode_changed()
        try:
            from worldgen import worldmap as wmod
            wmap = wmod.load(path)
        except Exception as error:
            messagebox.showerror("Карта не читается", repr(error))
            return
        self.map_preview = wmap
        facts = wmap.describe()
        self.map_note.set("%s — %s, суша %s"
                          % (os.path.basename(path), facts["Размер"],
                             facts["Суша"]))
        self._draw_map(wmap)

    # ------------------------------------------------------------------
    # Шаг 3: создание
    # ------------------------------------------------------------------

    def _build_start_step(self) -> None:
        page = ttk.Frame(self.steps, padding=16)
        self.steps.add(page, text="  3. Создание  ")

        self.summary = tk.Text(page, height=16, wrap="word", relief="flat",
                               bg="#231f30", fg="#efe7d8", padx=12, pady=10)
        if self.mono:
            self.summary.configure(font=self.mono)
        self.summary.pack(fill="both", expand=True)
        self.summary.config(state="disabled")

        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Button(bar, text="Обновить сводку",
                   command=self.refresh_summary).pack(side="left")
        self.go_button = ttk.Button(bar, text="Создать мир",
                                    style="Go.TButton", command=self._start)
        self.go_button.pack(side="right")
        self.progress = ttk.Progressbar(page, mode="determinate", maximum=1000)
        self.progress.pack(fill="x", pady=(10, 0))
        self.steps.bind("<<NotebookTabChanged>>", self._tab_changed)

    def _tab_changed(self, event=None) -> None:
        try:
            if self.steps.index(self.steps.select()) == 2:
                self.refresh_summary()
        except tk.TclError:
            pass

    def refresh_summary(self) -> None:
        lines = ["ЧТО БУДЕТ СОЗДАНО", ""]
        lines.append("  Сид мира ............ %s" % (self.seed_var.get()
                                                     or "—"))
        lines.append("  Лет истории ......... %s" % self.years_var.get())
        lines.append("  Плотность событий ... %s" % self.density_var.get())

        mode = self.map_mode.get()
        if mode == MAP_RANDOM:
            if self.map_preview is not None:
                facts = self.map_preview.describe()
                lines.append("  Карта ............... своя, %s, суша %s"
                             % (facts["Размер"], facts["Суша"]))
            else:
                lines.append("  Карта ............... своя, будет сделана "
                             "при создании мира")
            lines.append("  Сид карты ........... %s" % self.map_seed_var.get())
        elif mode == MAP_FILE:
            lines.append("  Карта ............... файл %s"
                         % (os.path.basename(self.map_path) or "не выбран"))
        else:
            lines.append("  Карта ............... нет, земли придумает движок")
            lines.append("  Земель .............. %s" % self.regions_var.get())

        moved = tuning.describe(self.knob_positions())
        locked = [tuning.KNOBS_BY_KEY[key].name
                  for key, var in self.knob_locks.items() if var.get()]
        lines.append("")
        if moved:
            lines.append("  СДВИНУТЫЕ ШКАЛЫ (%d)" % len(moved))
            for row in moved:
                lines.append("    %s" % row)
        else:
            lines.append("  Все шкалы стоят посередине — движок работает "
                         "так, как задуман.")
        if locked:
            lines.append("")
            lines.append("  ЗАКРЕПЛЕНО: %s" % ", ".join(locked))
        lines.append("")
        lines.append("  Десять тысяч лет истории считаются одну-две минуты.")

        self.summary.config(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.config(state="disabled")

    # ------------------------------------------------------------------
    # Наружу
    # ------------------------------------------------------------------

    def knob_positions(self) -> dict:
        return {key: int(var.get()) for key, var in self.knob_vars.items()
                if int(var.get()) != tuning.MIDDLE}

    def settings(self) -> Settings:
        """Всё, что выбрано в мастере, — одним набором настроек."""
        density = dict(DENSITY_CHOICES).get(self.density_var.get(), 1.0)
        try:
            years = int(float(self.years_var.get()))
        except ValueError:
            years = 10000
        try:
            regions = int(float(self.regions_var.get()))
        except ValueError:
            regions = 18

        make, path = {}, ""
        mode = self.map_mode.get()
        if mode == MAP_RANDOM:
            make = {
                "seed": self.map_seed_var.get() or self.seed_var.get(),
                "size": self.map_size_var.get(),
                "land_share": self.map_land.get() / 100.0,
                "roughness": self.map_rough.get() / 100.0,
                "warmth": self.map_warm.get() / 100.0,
                "wetness": self.map_wet.get() / 100.0,
                "magic": self.map_magic.get() / 100.0,
            }
        elif mode == MAP_FILE:
            path = self.map_path
        return Settings(seed=self.seed_var.get() or random_seed_text(),
                        years=years, regions=regions, density=density,
                        map_path=path, map_make=make,
                        tuning=self.knob_positions())

    def _start(self) -> None:
        if self.map_mode.get() == MAP_FILE and not self.map_path:
            messagebox.showinfo("Карта не выбрана",
                                "Выберите файл .world или другой способ "
                                "на шаге «Карта».")
            return
        self.refresh_summary()
        self.on_start(self.settings())

    # --- обратная связь от генерации ---

    def set_busy(self, busy: bool) -> None:
        self.go_button.config(state="disabled" if busy else "normal")

    def set_progress(self, part: float) -> None:
        self.progress["value"] = max(0.0, min(1.0, part)) * 1000
