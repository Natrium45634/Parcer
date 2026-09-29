# -*- coding: utf-8 -*-
"""История мира: одна вкладка вместо блуждания по пятидесяти разделам.

Летопись большого мира — это сто тысяч записей. Читать их подряд нельзя,
а разложенные по пятидесяти разделам они отвечают на вопрос «что было с
верой», но не на вопрос «что было в 3400 году на земле по имени Эрирал и
почему».

Поэтому здесь не раздел, а отбор: слева века с числом записей, в
середине — что случилось, справа — подробность и то, из чего это
выросло. Сверху шесть ручек: годы, важность, о чём, земля, держава и
поиск по слову. Любая из них сужает список, и все они складываются.

Быстро это работает по двум причинам. Записи мира уже уложены по
времени, поэтому отрезок лет берётся срезом, а не перебором. А в список
кладётся не всё найденное, а первые две тысячи: показать больше нельзя
ни глазу, ни таблице, и об остатке честно написано числом.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# О чём событие. Разбор идёт по началу машинного имени, поэтому новые
# виды событий попадают в свою кучу сами, а неизвестные — в «прочее».
GROUPS = (
    ("всё", ()),
    ("державы и власть", (
        "polity_", "colony_", "capital_moved", "republic", "reform",
        "policy_", "titular_", "conquest", "city_taken", "city_lost",
        "coup", "revolt", "oppression", "dark_state", "world_rule")),
    ("правители и роды", (
        "ruler", "accession", "abdication", "heir_birth", "regency_",
        "interregnum", "house_", "noble_fronda", "marriage", "figure_death",
        "champion", "notable_deed", "name_weighed", "life_summed",
        "subject_", "unfulfilled")),
    ("войны", (
        "war_", "battle", "siege_", "sea_battle", "blockade_", "front_",
        "landing", "supply_break", "company_", "fortress_", "feud_",
        "strife_", "noble_war", "betrayal", "sea_exodus")),
    ("договоры и союзы", (
        "pact", "embassy", "union", "league_", "trade_pact", "trade_break",
        "plot", "cabal_")),
    ("вера", (
        "faith_", "temple_", "schism", "crusade", "persecution",
        "high_priest", "state_faith", "divine_", "omen", "mythic_age",
        "hall_sealed")),
    ("беды", (
        "calamity_", "famine", "dark_age", "crisis_era", "invasion_",
        "monster_", "relic_", "scar", "trace_", "land_drowned",
        "land_sundered", "refuge", "shortage", "dark_errand")),
    ("города, племена и народы", (
        "settlement_", "city", "camp", "tribe", "site", "migration",
        "folk_", "race_awakening", "race_gone", "assimilation",
        "colony_free", "founder", "festival")),
    ("хозяйство и открытия", (
        "guild", "discovery", "expedition_", "artifact_", "craft")),
    ("слово и память", (
        "codex_", "lore_", "legend_", "tale", "local_story", "script_found",
        "tongue_", "court_tongue")),
    ("эпохи мира", ("era_", "world_begin")),
)

IMPORTANCE = (
    ("всё подряд", 1),
    ("заметное и выше", 2),
    ("важное и выше", 3),
    ("главное и выше", 4),
    ("только эпохальное", 5),
)

# Значки важности. Нарочно взяты только те, что есть в любом шрифте:
# редкий знак на чужой машине превращается в пустой квадрат.
MARKS = {1: "·", 2: "•", 3: "◆", 4: "★", 5: "★★"}
SHOW_LIMIT = 2000


_GROUP_OF = {}


def group_of(kind: str) -> str:
    """К какой куче отнести запись — по началу её машинного имени.

    Ответ запоминается: видов записей около двух сотен, а самих записей
    сто тысяч, и перебирать приставки на каждую — значит ждать секунду
    на всяком отборе.
    """
    name = _GROUP_OF.get(kind)
    if name is not None:
        return name
    name = "прочее"
    for title, prefixes in GROUPS:
        if any(kind.startswith(prefix) for prefix in prefixes):
            name = title
            break
    _GROUP_OF[kind] = name
    return name


class HistoryTab(ttk.Frame):
    """Отбор по летописи: годы, важность, о чём, земля, держава, слово."""

    def __init__(self, master, fonts=None, on_map=None):
        ttk.Frame.__init__(self, master)
        self.fonts = fonts or {}
        self.on_map = on_map
        self.world = None
        self._rows = []             # что сейчас в таблице: (событие, ...)
        self._centuries = []        # (год начала, год конца, сколько)
        self._region_names = {}
        self._polity_names = {}
        self._build()

    # ------------------------------------------------------------------
    # Устройство вкладки
    # ------------------------------------------------------------------

    def _build(self) -> None:
        ui = self.fonts.get("ui")
        mono = self.fonts.get("mono")

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 3))
        ttk.Label(bar, text="Годы:").pack(side="left")
        self.from_var = tk.StringVar(value="")
        self.to_var = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self.from_var, width=7).pack(side="left",
                                                                padx=(4, 2))
        ttk.Label(bar, text="—").pack(side="left")
        ttk.Entry(bar, textvariable=self.to_var, width=7).pack(side="left",
                                                              padx=(2, 6))
        ttk.Button(bar, text="вся история",
                   command=self.all_years).pack(side="left")
        ttk.Label(bar, text="  на год:").pack(side="left")
        self.one_var = tk.StringVar(value="")
        one = ttk.Entry(bar, textvariable=self.one_var, width=7)
        one.pack(side="left", padx=4)
        one.bind("<Return>", lambda _e: self.one_year())
        ttk.Button(bar, text="показать",
                   command=self.one_year).pack(side="left")
        self.count_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.count_var).pack(side="right")

        picks = ttk.Frame(self)
        picks.pack(fill="x", pady=(0, 3))
        ttk.Label(picks, text="Важность:").pack(side="left")
        self.imp_var = tk.StringVar(value=IMPORTANCE[1][0])
        box = ttk.Combobox(picks, textvariable=self.imp_var, state="readonly",
                           width=18, values=[name for name, _ in IMPORTANCE])
        box.pack(side="left", padx=(4, 8))
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(picks, text="О чём:").pack(side="left")
        self.group_var = tk.StringVar(value=GROUPS[0][0])
        box = ttk.Combobox(picks, textvariable=self.group_var,
                           state="readonly", width=24,
                           values=[name for name, _ in GROUPS] + ["прочее"])
        box.pack(side="left", padx=(4, 8))
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(picks, text="Земля:").pack(side="left")
        self.region_var = tk.StringVar(value="весь мир")
        self.region_box = ttk.Combobox(picks, textvariable=self.region_var,
                                       state="readonly", width=22,
                                       values=["весь мир"])
        self.region_box.pack(side="left", padx=(4, 8))
        self.region_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(picks, text="Держава:").pack(side="left")
        self.polity_var = tk.StringVar(value="любая")
        self.polity_box = ttk.Combobox(picks, textvariable=self.polity_var,
                                       state="readonly", width=26,
                                       values=["любая"])
        self.polity_box.pack(side="left", padx=4)
        self.polity_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        seek = ttk.Frame(self)
        seek.pack(fill="x", pady=(0, 4))
        ttk.Label(seek, text="Искать слово:").pack(side="left")
        self.find_var = tk.StringVar(value="")
        entry = ttk.Entry(seek, textvariable=self.find_var, width=36)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(seek, text="найти", command=self.refresh).pack(side="left")
        ttk.Button(seek, text="сбросить всё",
                   command=self.reset).pack(side="left", padx=6)

        split = ttk.PanedWindow(self, orient="horizontal")
        split.pack(fill="both", expand=True)

        left = ttk.Frame(split)
        split.add(left, weight=1)
        ttk.Label(left, text="Века").pack(anchor="w")
        self.ages = tk.Listbox(left, width=22, bg="#211f2c", fg="#e8e2d0",
                               selectbackground="#4a4368", relief="flat",
                               activestyle="none", font=mono,
                               exportselection=False)
        self.ages.pack(fill="both", expand=True)
        self.ages.bind("<<ListboxSelect>>", self._age_picked)

        middle = ttk.Frame(split)
        split.add(middle, weight=3)
        holder = ttk.Frame(middle)
        holder.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(holder, orient="vertical")
        scroll.pack(side="right", fill="y")
        self.list = ttk.Treeview(holder, columns=("year", "mark", "what"),
                                 show="headings", selectmode="browse",
                                 yscrollcommand=scroll.set)
        self.list.heading("year", text="год")
        self.list.heading("mark", text="!")
        self.list.heading("what", text="что случилось")
        self.list.column("year", width=70, anchor="e", stretch=False)
        self.list.column("mark", width=44, anchor="center", stretch=False)
        self.list.column("what", width=460, anchor="w")
        self.list.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.list.yview)
        self.list.bind("<<TreeviewSelect>>", self._row_picked)
        self.list.tag_configure("big", foreground="#e8c877")
        self.list.tag_configure("huge", foreground="#f0a860")

        right = ttk.Frame(split)
        split.add(right, weight=2)
        tools = ttk.Frame(right)
        tools.pack(fill="x")
        ttk.Button(tools, text="Показать на карте",
                   command=self.to_map).pack(side="left")
        ttk.Button(tools, text="Отчего это вышло",
                   command=self.show_causes).pack(side="left", padx=4)
        card = ttk.Frame(right)
        card.pack(fill="both", expand=True)
        bar2 = ttk.Scrollbar(card, orient="vertical")
        bar2.pack(side="right", fill="y")
        self.card = tk.Text(card, wrap="word", bg="#211f2c", fg="#e8e2d0",
                            relief="flat", padx=8, pady=6, font=mono,
                            yscrollcommand=bar2.set)
        self.card.pack(side="left", fill="both", expand=True)
        bar2.config(command=self.card.yview)
        self.card.tag_configure("head", foreground="#c6a14a", font=ui)
        self._blank_card()

    # ------------------------------------------------------------------
    # Новый мир
    # ------------------------------------------------------------------

    def set_world(self, world) -> None:
        self.world = world
        self._region_names = {region.id: region.name
                              for region in world.regions.values()}
        self._polity_names = {}
        for polity in world.polities.values():
            self._polity_names.setdefault(polity.full_name, polity.id)
        self.region_box.config(
            values=["весь мир"] + sorted(self._region_names.values()))
        names = sorted(self._polity_names)
        # Держав за десять тысяч лет бывает две сотни; в один список они
        # влезают, но выбирать удобнее, когда крупные сверху не потеряны.
        self.polity_box.config(values=["любая"] + names)
        self.region_var.set("весь мир")
        self.polity_var.set("любая")
        self.find_var.set("")
        self.imp_var.set(IMPORTANCE[1][0])
        self.group_var.set(GROUPS[0][0])
        self._fill_ages()
        self.all_years()

    def _fill_ages(self) -> None:
        """Список веков с числом записей — по нему и ходят по истории."""
        self.ages.delete(0, "end")
        self._centuries = []
        if self.world is None:
            return
        total = max(1, int(self.world.total_years))
        step = 100 if total <= 2000 else (500 if total <= 20000 else 1000)
        counts = {}
        for event in self.world.events:
            counts[(event.date.year - 1) // step] = \
                counts.get((event.date.year - 1) // step, 0) + 1
        self.ages.insert("end", "вся история")
        self._centuries.append((1, total, len(self.world.events)))
        for number in sorted(counts):
            start = number * step + 1
            end = min(total, start + step - 1)
            self._centuries.append((start, end, counts[number]))
            self.ages.insert("end", "%5d–%-5d %5d" % (start, end,
                                                      counts[number]))

    def _age_picked(self, _event=None) -> None:
        picks = self.ages.curselection()
        if not picks:
            return
        start, end, _count = self._centuries[picks[0]]
        self.from_var.set(str(start))
        self.to_var.set(str(end))
        self.refresh()

    # ------------------------------------------------------------------
    # Отбор
    # ------------------------------------------------------------------

    def all_years(self) -> None:
        if self.world is None:
            return
        self.from_var.set("1")
        self.to_var.set(str(int(self.world.total_years)))
        self.refresh()

    def one_year(self) -> None:
        try:
            year = int(self.one_var.get())
        except (TypeError, ValueError):
            return
        self.from_var.set(str(year))
        self.to_var.set(str(year))
        self.refresh()

    def reset(self) -> None:
        self.imp_var.set(IMPORTANCE[1][0])
        self.group_var.set(GROUPS[0][0])
        self.region_var.set("весь мир")
        self.polity_var.set("любая")
        self.find_var.set("")
        self.all_years()

    def _span(self):
        total = int(self.world.total_years)
        try:
            start = int(self.from_var.get())
        except (TypeError, ValueError):
            start = 1
        try:
            end = int(self.to_var.get())
        except (TypeError, ValueError):
            end = total
        start = max(1, min(total, start))
        end = max(start, min(total, end))
        self.from_var.set(str(start))
        self.to_var.set(str(end))
        return start, end

    def _least(self) -> int:
        for name, level in IMPORTANCE:
            if name == self.imp_var.get():
                return level
        return 1

    def refresh(self) -> None:
        """Собрать список по всем шести ручкам сразу."""
        if self.world is None:
            return
        start, end = self._span()
        least = self._least()
        group = self.group_var.get()
        region_id = ""
        if self.region_var.get() != "весь мир":
            for key, name in self._region_names.items():
                if name == self.region_var.get():
                    region_id = key
                    break
        polity_id = self._polity_names.get(self.polity_var.get(), "")
        needle = self.find_var.get().strip().lower()

        rows = []
        found = 0
        for event in self.world.events:
            year = event.date.year
            if year < start:
                continue
            if year > end:
                break        # записи уже уложены по времени
            if event.importance < least:
                continue
            if group != "всё" and group_of(event.kind) != group:
                continue
            if region_id and event.region_id != region_id:
                continue
            if polity_id and polity_id not in (event.subjects or ()):
                continue
            if needle and needle not in event.title.lower() \
                    and needle not in event.text.lower():
                continue
            found += 1
            if len(rows) < SHOW_LIMIT:
                rows.append(event)

        self._rows = rows
        self.list.delete(*self.list.get_children())
        for number, event in enumerate(rows):
            tag = ("huge" if event.importance >= 5 else
                   "big" if event.importance == 4 else "")
            self.list.insert("", "end", iid=str(number),
                             values=(event.date.year,
                                     MARKS.get(event.importance, "·"),
                                     event.title),
                             tags=(tag,) if tag else ())
        if found > len(rows):
            self.count_var.set("найдено %d, показаны первые %d"
                               % (found, len(rows)))
        else:
            self.count_var.set("найдено %d" % found)
        if rows:
            self.list.selection_set("0")
            self.list.see("0")
            self._show(rows[0])
        else:
            self._blank_card()

    # ------------------------------------------------------------------
    # Подробность
    # ------------------------------------------------------------------

    def _blank_card(self) -> None:
        self.card.config(state="normal")
        self.card.delete("1.0", "end")
        self.card.insert("1.0", "Выберите запись слева — и здесь будет "
                                "она целиком: что случилось, с кем, где и "
                                "из чего выросло.")
        self.card.config(state="disabled")

    def _row_picked(self, _event=None) -> None:
        picks = self.list.selection()
        if not picks:
            return
        number = int(picks[0])
        if 0 <= number < len(self._rows):
            self._show(self._rows[number])

    def _chosen(self):
        picks = self.list.selection()
        if not picks:
            return None
        number = int(picks[0])
        if 0 <= number < len(self._rows):
            return self._rows[number]
        return None

    def _show(self, event) -> None:
        world = self.world
        lines = ["## %s" % event.title,
                 "%d год, %s" % (event.date.year, _era_name(world, event)),
                 ""]
        lines.append(event.text)
        lines.append("")
        lines.append("## ПОДРОБНОСТИ")
        lines.append("   важность ... %s (%d из 5)"
                     % (MARKS.get(event.importance, "·"), event.importance))
        lines.append("   о чём ...... %s" % group_of(event.kind))
        if event.region_id:
            lines.append("   земля ...... %s"
                         % self._region_names.get(event.region_id,
                                                  event.region_id))
        who = [world.entity_name(item) for item in (event.actors or ())]
        who = [name for name in who if name and name != "?"]
        if who:
            lines.append("   кто ........ %s" % ", ".join(who[:6]))
        about = [world.entity_name(item) for item in (event.subjects or ())]
        about = [name for name in about if name and name != "?"]
        if about:
            lines.append("   о ком ...... %s" % ", ".join(about[:6]))
        if event.motives:
            for key, value in event.motives.items():
                lines.append("   %-10s %s" % (key + " ..", value))
        self._put(lines)

    def show_causes(self) -> None:
        """Из чего это выросло и что из этого выросло — на три колена."""
        event = self._chosen()
        if event is None or self.world is None:
            return
        world = self.world
        seen = set()
        lines = ["## ОТЧЕГО ВЫШЛО: %s" % event.title, ""]

        def climb(item, depth):
            if depth > 3 or item.id in seen:
                return
            seen.add(item.id)
            for cause_id in (item.causes or ())[:4]:
                cause = _find_event(world, cause_id)
                if cause is None:
                    continue
                lines.append("%s%d: %s" % ("   " * depth, cause.date.year,
                                           cause.title))
                climb(cause, depth + 1)

        climb(event, 1)
        if len(lines) == 2:
            lines.append("   Причины не записаны: это событие само по себе "
                         "начало.")
        after = [item for item in world.events
                 if event.id in (item.causes or ())][:8]
        if after:
            lines.append("")
            lines.append("## ЧТО ИЗ ЭТОГО ВЫШЛО")
            for item in after:
                lines.append("   %d: %s" % (item.date.year, item.title))
        self._put(lines)

    def to_map(self) -> None:
        """Показать это место и этот год на карте мира."""
        event = self._chosen()
        if event is None or self.on_map is None:
            return
        self.on_map(event.date.year, event.region_id)

    def _put(self, lines) -> None:
        self.card.config(state="normal")
        self.card.delete("1.0", "end")
        for line in lines:
            if line.startswith("## "):
                self.card.insert("end", line[3:] + "\n", "head")
            else:
                self.card.insert("end", line + "\n")
        self.card.config(state="disabled")
        self.card.see("1.0")


def _era_name(world, event) -> str:
    era = world.era_at(event.date.year) if world is not None else None
    return era.name if era is not None else "эпоха не названа"


def _find_event(world, event_id: str):
    """Событие по номеру. Летопись хранится списком, поэтому ищем разом
    и запоминаем: причин у события немного, но спрашивают их часто."""
    index = getattr(world, "_event_index", None)
    if index is None or len(index) != len(world.events):
        index = {item.id: item for item in world.events}
        try:
            world._event_index = index
        except Exception:
            pass
    return index.get(event_id)
