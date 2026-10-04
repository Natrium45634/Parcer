# -*- coding: utf-8 -*-
"""Земля: одно место мира, расписанное прозой и по годам.

Беда, которую это лечит: дорога между летописью и картой шла только в
одну сторону. Из записи можно было перейти на карту и увидеть, где это
было, — но стоя на карте и щёлкнув по гексу, человек получал карточку
шириной в ладонь, где на строку приходится тридцать знаков. Летопись
иного гекса — полторы сотни строк; читать её в такое окошко нельзя.

Поэтому тут не карточка, а страница. Сверху — откуда она взялась и чем
её сменить: номер гекса, год, список заметных мест и кнопка обратно на
карту. Ниже — всё, что landlore знает об этом месте: каково в нём, чем
оно весомо, что на нём стоит, что на нём было по годам и что проходило
по всей земле вокруг.

Считается это на лету и только по запросу: ни один гекс не стоит того,
чтобы держать его страницу в памяти, а полтораста тысяч гексов — тем
более.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from worldgen import landlore

CARD_BG = "#211f2c"
CARD_INK = "#e8e2d0"
HEAD_INK = "#c6a14a"
DIM_INK = "#9a93a8"
YEAR_INK = "#8fb6c9"


class LandTab(ttk.Frame):
    """Полная страница одного гекса: условия, вес, летопись места."""

    def __init__(self, master, fonts=None, on_map=None):
        ttk.Frame.__init__(self, master)
        self.fonts = fonts or {}
        # Обратная дорога на карту: страницу открыли с гекса, и вернуться
        # человек хочет туда же.
        self.on_map = on_map
        self.world = None
        self.index = -1
        self.year = 0
        self._places = []

        self.hex_var = tk.StringVar(value="")
        self.year_var = tk.StringVar(value="")
        self.place_var = tk.StringVar(value="")
        self.note_var = tk.StringVar(value="")
        self._build()

    # ------------------------------------------------------------------
    # Устройство вкладки
    # ------------------------------------------------------------------

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 4))

        ttk.Label(bar, text="Гекс").pack(side="left", padx=(8, 3))
        box = ttk.Entry(bar, textvariable=self.hex_var, width=9)
        box.pack(side="left")
        box.bind("<Return>", lambda _e: self.ask_hex())
        ttk.Label(bar, text="год").pack(side="left", padx=(10, 3))
        years = ttk.Entry(bar, textvariable=self.year_var, width=8)
        years.pack(side="left")
        years.bind("<Return>", lambda _e: self.ask_hex())
        ttk.Button(bar, text="Показать",
                   command=self.ask_hex).pack(side="left", padx=(6, 0))

        ttk.Label(bar, text="или место").pack(side="left", padx=(16, 3))
        self.place_box = ttk.Combobox(bar, textvariable=self.place_var,
                                      state="readonly", width=46)
        self.place_box.pack(side="left")
        self.place_box.bind("<<ComboboxSelected>>", self._picked_place)

        self.to_map = ttk.Button(bar, text="Показать на карте",
                                 command=self.ask_map, state="disabled")
        self.to_map.pack(side="right", padx=(6, 8))

        ttk.Label(self, textvariable=self.note_var, anchor="w").pack(
            fill="x", padx=8, pady=(0, 3))

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        scroll = ttk.Scrollbar(holder, orient="vertical")
        scroll.pack(side="right", fill="y")
        self.text = tk.Text(holder, wrap="word", bg=CARD_BG, fg=CARD_INK,
                            font=self.fonts.get("mono"), relief="flat",
                            padx=14, pady=10, yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.text.yview)
        self.text.tag_configure("title", foreground=HEAD_INK,
                                font=self.fonts.get("head")
                                or self.fonts.get("ui"), spacing3=6)
        self.text.tag_configure("head", foreground=HEAD_INK,
                                font=self.fonts.get("ui"), spacing1=4)
        self.text.tag_configure("dim", foreground=DIM_INK)
        self.text.tag_configure("year", foreground=YEAR_INK)
        self._blank()

    def _blank(self) -> None:
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0",
                         "Выберите место: на карте щёлкните по гексу и "
                         "нажмите «Полные данные о месте», или возьмите "
                         "место из списка сверху, или наберите номер "
                         "гекса.\n\nЗдесь будет всё об одном месте: каково "
                         "в нём, чем оно весомо, что на нём стоит и что на "
                         "нём было — по годам.")
        self.text.config(state="disabled")

    # ------------------------------------------------------------------
    # Мир и показ
    # ------------------------------------------------------------------

    def set_world(self, world) -> None:
        """Новый мир: собрать список заметных мест и открыть самое весомое."""
        self.world = world
        self.index = -1
        self.year = int(getattr(world, "total_years", 0) or 0)
        self.year_var.set(str(self.year))
        self._places = landlore.notable(world)
        self.place_box.config(values=[said for _index, said in self._places])
        if not self._places:
            self.place_box.config(state="disabled")
        best = landlore.best_hex(world)
        if best >= 0:
            self.show_hex(best, self.year)
        else:
            self._blank()
            self.note_var.set("В этом мире нет карты — говорить о местах "
                              "нечего.")

    def show_hex(self, index: int, year: int = 0) -> None:
        """Показать это место на этот год."""
        if self.world is None or index < 0:
            return
        total = int(getattr(self.world, "total_years", 0) or 0)
        self.index = int(index)
        self.year = max(1, min(total, int(year or total))) if total else 0
        self.hex_var.set(str(self.index))
        self.year_var.set(str(self.year))
        self.note_var.set("")
        self.to_map.config(state="normal" if self.on_map is not None
                           else "disabled")
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        for tag, line in landlore.blocks(self.world, self.index, self.year):
            if tag == "dated":
                # Год — своим цветом: столбец годов тогда читается как
                # столбец, а не как часть фразы.
                self.text.insert("end", line[:10], "year")
                self.text.insert("end", line[10:] + "\n")
            elif tag == "line":
                self.text.insert("end", line + "\n")
            else:
                self.text.insert("end", line + "\n", tag)
        self.text.config(state="disabled")
        self.text.see("1.0")

    # ------------------------------------------------------------------
    # Ручки
    # ------------------------------------------------------------------

    def ask_hex(self) -> None:
        """Человек набрал номер гекса и год руками."""
        if self.world is None:
            return
        link = getattr(self.world, "map_link", None)
        wmap = getattr(link, "wmap", None) if link is not None else None
        if wmap is None:
            self.note_var.set("В этом мире нет карты.")
            return
        try:
            index = int(self.hex_var.get().strip())
        except ValueError:
            self.note_var.set("Номер гекса — число от 0 до %d."
                              % (wmap.width * wmap.height - 1))
            return
        if not 0 <= index < wmap.width * wmap.height:
            self.note_var.set("На этой карте гексов всего %d: от 0 до %d."
                              % (wmap.width * wmap.height,
                                 wmap.width * wmap.height - 1))
            return
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            year = self.year
        self.show_hex(index, year)

    def _picked_place(self, _event=None) -> None:
        said = self.place_var.get()
        for index, name in self._places:
            if name == said:
                self.show_hex(index, self.year)
                return

    def ask_map(self) -> None:
        """Обратно на карту — к тому же гексу и тому же году."""
        if self.on_map is None or self.index < 0:
            return
        self.on_map(self.index, self.year)

    def clear(self) -> None:
        self.world = None
        self.index = -1
        self._places = []
        self.place_box.config(values=[])
        self.place_var.set("")
        self.hex_var.set("")
        self.year_var.set("")
        self.note_var.set("")
        self.to_map.config(state="disabled")
        self._blank()
