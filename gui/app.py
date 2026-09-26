# -*- coding: utf-8 -*-
"""Окно программы: настройки, генерация и просмотр мира."""

from __future__ import annotations

import json
import os
import sys
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from gui.atlas import Atlas
from gui.sidetabs import SideTabs
from gui import wizard as wizard_mod
from gui.wizard import Wizard
from worldgen import chronicle, storage
from worldgen.engine import GenerationCancelled, generate
from worldgen.models import ACTIVE
from worldgen.races import RACES, RACES_BY_ID, get_race
from worldgen.timeline import years_text

APP_TITLE = "Хронист — генератор фэнтезийных историй"


def _root_dir() -> str:
    """Где лежат значки и карты.

    Собранная программа распаковывает их во временную папку, и путь к ней
    лежит в sys._MEIPASS; при запуске из исходников это просто папка
    проекта.
    """
    packed = getattr(sys, "_MEIPASS", "")
    if packed:
        return packed
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT_DIR = _root_dir()
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

DENSITY_CHOICES = (
    ("Редкая — крупные события, мало мелочей", 0.6),
    ("Обычная", 1.0),
    ("Густая — больше народов и городов", 1.5),
    ("Очень густая — летопись на каждый год", 2.2),
)

IMPORTANCE_CHOICES = (
    ("Только эпохальное", 5),
    ("Главное: страны, расы, эпохи", 4),
    ("Важное: + города и падения", 3),
    ("Подробно: + лагеря и смерти", 2),
    ("Всё до последнего племени", 1),
)

BG = "#1d1b26"
PANEL = "#262433"
INK = "#e8e3d8"
ACCENT = "#c6a14a"


def pick_font(candidates, size, weight="normal"):
    families = set(tkfont.families())
    for name in candidates:
        if name in families:
            return tkfont.Font(family=name, size=size, weight=weight)
    return tkfont.Font(size=size, weight=weight)


# Настройки самой программы (не мира) живут в домашней папке человека:
# рядом с .exe писать нельзя — он может лежать где угодно, хоть на
# флешке, хоть в папке без прав на запись.
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".хронист.json")
MIN_SCALE, MAX_SCALE = -2, 10


def _read_scale() -> int:
    """Во сколько ступеней крупнее обычного человек просил набирать текст."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as handle:
            saved = json.load(handle)
        return max(MIN_SCALE, min(MAX_SCALE, int(saved.get("scale", 0))))
    except Exception:
        return 0


def _write_scale(step: int) -> None:
    try:
        saved = {}
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, encoding="utf-8") as handle:
                saved = json.load(handle)
        saved["scale"] = int(step)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump(saved, handle, ensure_ascii=False)
    except Exception:
        pass          # не записалось — не беда, в этот раз обойдёмся


def _fit(text: str, limit: int = 44) -> str:
    """Подрезает подпись, чтобы она не растягивала панель настроек."""
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


class ChronicleApp(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title(APP_TITLE)
        self.geometry("1240x820")
        self.minsize(980, 640)
        self.configure(bg=BG)

        self.world = None
        self.worker = None
        self.atlas = None              # живая карта: появляется вместе с миром
        self.progress_queue = queue.Queue()
        self.stop_flag = False

        self.mono = pick_font(("Consolas", "DejaVu Sans Mono", "Menlo",
                               "Courier New", "TkFixedFont"), 10)
        self.ui_font = pick_font(("Segoe UI", "DejaVu Sans", "Helvetica"), 10)
        self.head_font = pick_font(("Segoe UI", "DejaVu Sans"), 11, "bold")
        self.go_font = pick_font(("Segoe UI", "DejaVu Sans"), 10, "bold")
        # Масштаб окна: насколько крупнее обычного набраны буквы. Выбор
        # человека переживает закрытие программы — переставлять его при
        # каждом запуске никто не станет.
        self.scale_step = _read_scale()

        self._set_icon()
        self._setup_style()
        self._build_menu()
        self._build_topbar()
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)
        self._build_wizard()
        self._build_tabs()
        self._build_status()
        self._show_welcome()
        self.show_wizard()
        self.apply_scale()
        for combo in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind_all(combo, lambda _event: self.change_scale(1))
        for combo in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind_all(combo, lambda _event: self.change_scale(-1))
        self.bind_all("<Control-0>", lambda _event: self.reset_scale())

    # ------------------------------------------------------------------
    # Оформление
    # ------------------------------------------------------------------

    def _set_icon(self) -> None:
        png = os.path.join(ASSETS_DIR, "icon.png")
        ico = os.path.join(ASSETS_DIR, "icon.ico")
        try:
            if os.path.exists(ico) and os.name == "nt":
                self.iconbitmap(ico)
            elif os.path.exists(png):
                self._icon_image = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon_image)
        except tk.TclError:
            pass

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=INK, font=self.ui_font)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Panel.TLabel", background=PANEL, foreground=INK)
        style.configure("Head.TLabel", background=PANEL, foreground=ACCENT,
                        font=self.head_font)
        style.configure("TButton", background="#3a3550", foreground=INK, padding=5)
        style.map("TButton", background=[("active", "#4a4368")])
        style.configure("Go.TButton", background=ACCENT, foreground="#221d14",
                        font=self.go_font)
        style.map("Go.TButton", background=[("active", "#e0bc63")])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=INK,
                        padding=(8, 5))
        style.map("TNotebook.Tab", background=[("selected", "#3a3550")],
                  foreground=[("selected", ACCENT)])
        style.configure("Treeview", background="#211f2c", fieldbackground="#211f2c",
                        foreground=INK, rowheight=22, borderwidth=0)
        style.configure("Treeview.Heading", background="#3a3550", foreground=ACCENT)
        style.map("Treeview", background=[("selected", "#4a4368")])
        style.configure("TEntry", fieldbackground="#2f2c3e", foreground=INK)
        style.configure("TSpinbox", fieldbackground="#2f2c3e", foreground=INK,
                        arrowcolor=INK)
        style.configure("TCombobox", fieldbackground="#2f2c3e", foreground=INK,
                        arrowcolor=INK, selectbackground="#2f2c3e",
                        selectforeground=INK)
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#2f2c3e")],
                  foreground=[("readonly", INK)],
                  selectbackground=[("readonly", "#2f2c3e")],
                  selectforeground=[("readonly", INK)])
        # Выпадающий список рисуется не через ttk, ему нужны свои настройки.
        self.option_add("*TCombobox*Listbox.background", "#2f2c3e")
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#221d14")
        style.configure("TProgressbar", background=ACCENT, troughcolor=PANEL)

    # ------------------------------------------------------------------
    # Меню
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = tk.Menu(self, font=self.ui_font)
        self._menus = [menu]
        file_menu = tk.Menu(menu, tearoff=0, font=self.ui_font)
        self._menus.append(file_menu)
        file_menu.add_command(label="Сохранить мир…", command=self.save_world)
        file_menu.add_command(label="Открыть мир…", command=self.open_world)
        file_menu.add_separator()
        file_menu.add_command(label="Сохранить летопись в текст…",
                              command=self.export_text)
        file_menu.add_command(label="Сохранить политическую карту (chronicle.json)…",
                              command=self.export_chronicle_map)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        menu.add_cascade(label="Файл", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=0, font=self.ui_font)

        self._menus.append(help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        menu.add_cascade(label="Справка", menu=help_menu)
        self.config(menu=menu)

    # ------------------------------------------------------------------
    # Панель настроек
    # ------------------------------------------------------------------

    def _build_topbar(self) -> None:
        """Верхняя строка: куда идти и как вернуться."""
        bar = ttk.Frame(self, style="Panel.TFrame", padding=8)
        bar.pack(fill="x", side="top")
        ttk.Label(bar, text="ХРОНИСТ", style="Head.TLabel").pack(side="left")
        self.where_var = tk.StringVar(value="создание мира")
        ttk.Label(bar, textvariable=self.where_var,
                  style="Panel.TLabel").pack(side="left", padx=12)
        ttk.Button(bar, text="Новый мир",
                   command=self.show_wizard).pack(side="right")
        # Масштаб: крупнее или мельче весь текст окна разом.
        zoom = ttk.Frame(bar, style="Panel.TFrame")
        zoom.pack(side="right", padx=(0, 14))
        ttk.Button(zoom, text="А−", width=3,
                   command=lambda: self.change_scale(-1)).pack(side="left")
        self.scale_var = tk.StringVar(value="100%")
        ttk.Label(zoom, textvariable=self.scale_var, style="Panel.TLabel",
                  width=5, anchor="center").pack(side="left", padx=2)
        ttk.Button(zoom, text="А+", width=3,
                   command=lambda: self.change_scale(1)).pack(side="left")
        self.to_chronicle = ttk.Button(bar, text="К летописи",
                                       command=self.show_viewer)
        self.to_chronicle.pack(side="right", padx=6)
        self.to_chronicle.config(state="disabled")

    # ------------------------------------------------------------------
    # Масштаб окна
    # ------------------------------------------------------------------

    def change_scale(self, delta: int) -> None:
        step = max(MIN_SCALE, min(MAX_SCALE, self.scale_step + int(delta)))
        if step == self.scale_step:
            return
        self.scale_step = step
        self.apply_scale()
        _write_scale(step)

    def reset_scale(self) -> None:
        self.scale_step = 0
        self.apply_scale()
        _write_scale(0)

    def apply_scale(self) -> None:
        """Крупнее весь текст разом: шрифты общие, потому хватает их одних."""
        step = self.scale_step
        self.ui_font.configure(size=max(7, 10 + step))
        self.mono.configure(size=max(7, 10 + step))
        self.head_font.configure(size=max(8, 11 + step))
        self.go_font.configure(size=max(7, 10 + step))
        # Строки таблиц не растут за шрифтом сами — им надо сказать.
        ttk.Style(self).configure("Treeview",
                                  rowheight=max(18, 22 + step * 2))
        for item in getattr(self, "_menus", ()):
            try:
                item.configure(font=self.ui_font)
            except tk.TclError:
                pass
        if hasattr(self, "scale_var"):
            self.scale_var.set("%d%%" % round((10 + step) * 100.0 / 10))
        if getattr(self, "atlas", None) is not None:
            self.atlas.redraw()

    def _build_wizard(self) -> None:
        self.wizard = Wizard(self.body, on_start=self.start_generation,
                             fonts={"ui": self.ui_font, "mono": self.mono})

    # ------------------------------------------------------------------
    # Два вида окна: мастер и летопись
    # ------------------------------------------------------------------

    def show_wizard(self) -> None:
        self.tabs.pack_forget()
        self.wizard.pack(fill="both", expand=True)
        self.where_var.set("создание мира")

    def show_viewer(self) -> None:
        if self.world is None:
            return
        self.wizard.pack_forget()
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self.where_var.set("летопись мира «%s»" % self.world.seed_text)
        self.to_chronicle.config(state="normal")

    # ------------------------------------------------------------------
    # Вкладки
    # ------------------------------------------------------------------

    def _build_tabs(self) -> None:
        self.tabs = SideTabs(self.body)
        # Таблицы заполняются лениво: на десять тысяч лет истории их строки
        # считаются десятками тысяч, и заполнять всё сразу — значит заставить
        # человека ждать впустую.
        self._fillers = {}
        self._filled = set()

        self._build_chronicle_tab()
        self._build_map_tab()
        self.eras_text = self._add_text_tab("Эпохи")
        self.polity_tree = self._add_tree_tab(
            "Страны",
            ("Название", "Форма", "Раса", "Основана", "Основатель", "Столица",
             "Городов", "Население", "Вера", "Состояние"),
            (185, 150, 110, 80, 180, 150, 70, 90, 150, 100), self._on_polity_open,
            filler=lambda: self._fill_polities())
        self.city_tree = self._add_tree_tab(
            "Города",
            ("Название", "Тип", "Раса", "Основан", "Основатель", "Страна",
             "Население", "Состояние"),
            (200, 110, 120, 90, 210, 190, 90, 110), self._on_city_open,
            filler=lambda: self._fill_cities())
        self.group_tree = self._add_tree_tab(
            "Племена и лагеря",
            ("Название", "Тип", "Раса", "Основано", "Основатель", "Земля",
             "Население", "Состояние"),
            (200, 110, 120, 90, 200, 160, 90, 120), self._on_group_open,
            filler=lambda: self._fill_groups())
        self.house_tree = self._add_tree_tab(
            "Знатные рода",
            ("Род", "Раса", "Основан", "Основатель", "Ранг", "Страна",
             "Гнездо", "Живых", "Престолов", "Состояние"),
            (200, 120, 80, 190, 90, 180, 150, 60, 80, 120), self._on_house_open,
            filler=lambda: self._fill_houses())
        self.faith_tree = self._add_tree_tab(
            "Веры",
            ("Вера", "Вид", "Основана", "Состояние", "Мировоззрение",
             "Верующих", "Богов", "Храмов", "Народы"),
            (200, 120, 80, 110, 130, 100, 60, 60, 230), self._on_faith_open,
            filler=lambda: self._fill_faiths())
        self.pantheon_text = self._add_text_tab(
            "Пантеон",
            filler=lambda: self._set_text(self.pantheon_text,
                                          chronicle.render_pantheon(self.world)))
        self.calamity_tree = self._add_tree_tab(
            "Бедствия",
            ("Название", "Вид", "Уровень", "Годы", "Земель", "Врагов",
             "Погибло", "Исход", "Следов"),
            (230, 150, 130, 110, 70, 100, 100, 190, 70), self._on_calamity_open,
            filler=lambda: self._fill_calamities())
        self.politics_text = self._add_text_tab(
            "Политика",
            filler=lambda: self._set_text(self.politics_text,
                                          chronicle.render_politics(self.world)))
        self.embassy_text = self._add_text_tab(
            "Посольства и тайны", lambda: self._set_text(
                self.embassy_text, chronicle.render_embassies(self.world)))
        self.wars_text = self._add_text_tab(
            "Войны",
            filler=lambda: self._set_text(self.wars_text,
                                          chronicle.render_wars(self.world)))
        self.soldiery_text = self._add_text_tab(
            "Крепости и роты",
            filler=lambda: self._set_text(self.soldiery_text,
                                          chronicle.render_soldiery(self.world)))
        self.dynasty_text = self._add_text_tab(
            "Правители",
            filler=lambda: self._set_text(self.dynasty_text,
                                          chronicle.render_dynasties(self.world)))
        self.houses_text = self._add_text_tab(
            "Знать",
            filler=lambda: self._set_text(self.houses_text,
                                          chronicle.render_houses(self.world)))
        self.figure_tree = self._add_tree_tab(
            "Личности",
            ("Имя", "Раса", "Пол", "Годы жизни", "Род", "Титул", "Роли", "Событий"),
            (230, 120, 60, 110, 150, 150, 200, 70), self._on_figure_open,
            toolbar=self._figures_toolbar, filler=lambda: self._fill_figures())
        self.folks_text = self._add_text_tab("Народы")
        self.tongues_text = self._add_text_tab("Языки")
        self.peoples_text = self._add_text_tab("Державы и народы")
        self.trade_text = self._add_text_tab("Хозяйство")
        self.guilds_text = self._add_text_tab(
            "Гильдии", lambda: self._set_text(
                self.guilds_text, chronicle.render_guilds(self.world)))
        self.laws_text = self._add_text_tab(
            "Законы", lambda: self._set_text(
                self.laws_text, chronicle.render_laws(self.world)))
        self.lore_text = self._add_text_tab(
            "Своды и легенды", lambda: self._set_text(
                self.lore_text, chronicle.render_lore(self.world)))
        self.tales_text = self._add_text_tab(
            "Сказания", lambda: self._set_text(
                self.tales_text, chronicle.render_tales(self.world)))
        self.lives_text = self._add_text_tab(
            "Судьбы людей", lambda: self._set_text(
                self.lives_text, chronicle.render_lifepaths(self.world)))
        self.stories_text = self._add_text_tab(
            "Были", lambda: self._set_text(
                self.stories_text, chronicle.render_stories(self.world)))
        self.crafts_text = self._add_text_tab(
            "Ремёсла", lambda: self._set_text(
                self.crafts_text, chronicle.render_crafts(self.world)))
        self.monsters_text = self._add_text_tab(
            "Чудовища", lambda: self._set_text(
                self.monsters_text, chronicle.render_monsters(self.world)))
        self.artifacts_text = self._add_text_tab(
            "Вещи", lambda: self._set_text(
                self.artifacts_text, chronicle.render_artifacts(self.world)))
        self.sites_text = self._add_text_tab(
            "Места", lambda: self._set_text(
                self.sites_text, chronicle.render_sites(self.world)))
        self.sagas_text = self._add_text_tab(
            "Цепи бедствий", lambda: self._set_text(
                self.sagas_text, chronicle.render_sagas(self.world)))
        self.upheaval_text = self._add_text_tab(
            "Как менялся мир", lambda: self._set_text(
                self.upheaval_text, chronicle.render_upheavals(self.world)))
        self.causes_text = self._add_text_tab(
            "Нити причин", lambda: self._set_text(
                self.causes_text, chronicle.render_causes(self.world)))
        self.memory_text = self._add_text_tab(
            "Память и связи", lambda: self._set_text(
                self.memory_text, chronicle.render_memory(self.world)))
        self.migration_text = self._add_text_tab(
            "Переселения", lambda: self._set_text(
                self.migration_text, chronicle.render_migrations(self.world)))
        self.culture_text = self._add_text_tab(
            "Растворение народов", lambda: self._set_text(
                self.culture_text, chronicle.render_culture(self.world)))
        self.strife_text = self._add_text_tab(
            "Смуты", lambda: self._set_text(
                self.strife_text, chronicle.render_strifes(self.world)))
        self.cabal_text = self._add_text_tab(
            "Заговоры", lambda: self._set_text(
                self.cabal_text, chronicle.render_cabals(self.world)))
        self.expeditions_text = self._add_text_tab("Походы")
        self.regions_text = self._add_text_tab("Земли")
        self.stats_text = self._add_text_tab("Итоги")
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_map_tab(self) -> None:
        """Живая карта мира — тот же гексовый вид, что у картогенератора.

        Раздел тяжёлый: карту надо нарисовать целиком. Поэтому он тоже
        заполняется лениво — только когда его открыли.
        """
        self.atlas = Atlas(self.tabs, fonts={"ui": self.ui_font,
                                             "mono": self.mono})
        self.tabs.add(self.atlas, text="Карта мира")
        self._fillers[str(self.atlas)] = self._fill_atlas

    def _fill_atlas(self) -> None:
        if self.world is not None:
            self.atlas.show(self.world)

    def _build_chronicle_tab(self) -> None:
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text="Летопись")

        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(6, 4))

        ttk.Label(bar, text="Подробность:").pack(side="left", padx=(4, 6))
        self.importance_var = tk.StringVar(value=IMPORTANCE_CHOICES[2][0])
        ttk.Combobox(bar, textvariable=self.importance_var, state="readonly",
                     width=32,
                     values=[name for name, _ in IMPORTANCE_CHOICES]).pack(side="left")

        ttk.Label(bar, text="Раса:").pack(side="left", padx=(14, 6))
        self.race_var = tk.StringVar(value="Все расы")
        ttk.Combobox(bar, textvariable=self.race_var, state="readonly", width=26,
                     values=["Все расы"] + [race.name for race in RACES]).pack(side="left")

        ttk.Label(bar, text="Поиск:").pack(side="left", padx=(14, 6))
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=24)
        entry.pack(side="left")
        entry.bind("<Return>", lambda event: self.refresh_chronicle())

        ttk.Button(bar, text="Показать", command=self.refresh_chronicle).pack(
            side="left", padx=10)

        self.chronicle_text = self._make_text(frame)

    def _make_text(self, parent) -> tk.Text:
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(holder, orient="vertical")
        scroll.pack(side="right", fill="y")
        widget = tk.Text(holder, wrap="none", font=self.mono, bg="#211f2c",
                         fg=INK, insertbackground=INK, relief="flat",
                         yscrollcommand=scroll.set, padx=10, pady=8)
        widget.pack(side="left", fill="both", expand=True)
        scroll.config(command=widget.yview)
        bottom = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview)
        bottom.pack(fill="x")
        widget.config(xscrollcommand=bottom.set)
        widget.config(state="disabled")
        return widget

    def _add_text_tab(self, title: str, filler=None) -> tk.Text:
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text=title)
        if filler is not None:
            self._fillers[str(frame)] = filler
        return self._make_text(frame)

    def _figures_toolbar(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(6, 2))
        self.only_noble = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Только те, кто попал в летопись",
                        variable=self.only_noble,
                        command=self._refill_figures).pack(side="left", padx=6)
        self.figures_note = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.figures_note).pack(side="left", padx=10)

    def _add_tree_tab(self, title, columns, widths, on_open,
                      toolbar=None, filler=None) -> ttk.Treeview:
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text=title)
        if toolbar is not None:
            toolbar(frame)
        scroll = ttk.Scrollbar(frame, orient="vertical")
        scroll.pack(side="right", fill="y")
        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            yscrollcommand=scroll.set)
        for name, width in zip(columns, widths):
            tree.heading(name, text=name,
                         command=lambda t=tree, c=name: self._sort_tree(t, c, False))
            tree.column(name, width=width, anchor="w")
        tree.pack(side="left", fill="both", expand=True)
        scroll.config(command=tree.yview)
        tree.bind("<Double-1>", on_open)
        if filler is not None:
            self._fillers[str(frame)] = filler
        return tree

    def _build_status(self) -> None:
        self.status_var = tk.StringVar(value="Готов к работе.")
        bar = ttk.Frame(self, style="Panel.TFrame", padding=(10, 4))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status_var, style="Panel.TLabel").pack(
            side="left")

    # ------------------------------------------------------------------
    # Генерация
    # ------------------------------------------------------------------

    def randomize_seed(self) -> None:
        self.wizard.roll_seed()

    def choose_map(self) -> None:
        """Выбор файла .world — теперь это шаг мастера."""
        self.show_wizard()
        self.wizard.choose_map()

    def clear_map(self) -> None:
        self.show_wizard()
        self.wizard.set_map_mode(wizard_mod.MAP_NONE)

    def export_chronicle_map(self) -> None:
        """Пишет chronicle.json — политическую карту по годам."""
        if self.world is None:
            messagebox.showinfo("Нечего сохранять", "Сначала создайте мир.")
            return
        if self.world.map_recorder is None:
            messagebox.showinfo(
                "Мир создан без карты",
                "Политическая карта пишется только для мира, построенного "
                "по файлу .world. Выберите карту в настройках и создайте мир "
                "заново.")
            return
        path = filedialog.asksaveasfilename(
            title="Политическая карта для картогенератора",
            defaultextension=".json", initialfile="chronicle.json",
            filetypes=[("chronicle.json", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        from worldgen import chronicle_map
        payload = chronicle_map.export(self.world, self.world.map_recorder, path)
        section = payload["map"]
        messagebox.showinfo(
            "Готово",
            "Записано %s\n\nКадров границ: %d\nДержав: %d\nГородов: %d\n\n"
            "Откройте файл во вкладке «Страны» картогенератора — и история "
            "проиграется по годам прямо на карте."
            % (os.path.basename(path), len(section["frames"]),
               len(section["realmColors"]), len(section["cities"])))

    def start_generation(self, settings=None) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        settings = (settings or self.wizard.settings()).normalized()
        self.wizard.seed_var.set(settings.seed)
        self.wizard.set_busy(True)
        self.status_var.set("Творение мира…")
        self.wizard.set_progress(0.0)
        self.stop_flag = False

        def work():
            try:
                world = generate(
                    settings,
                    progress=lambda part, note: self.progress_queue.put(("step", part, note)),
                    should_stop=lambda: self.stop_flag)
                self.progress_queue.put(("done", world, ""))
            except GenerationCancelled:
                self.progress_queue.put(("cancelled", None, ""))
            except Exception as error:                      # показать, а не молчать
                self.progress_queue.put(("error", None, repr(error)))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.after(60, self._poll_progress)

    def _poll_progress(self) -> None:
        try:
            while True:
                kind, payload, note = self.progress_queue.get_nowait()
                if kind == "step":
                    self.wizard.set_progress(payload)
                    self.status_var.set("Творение мира: %s" % note)
                elif kind == "done":
                    self.wizard.set_progress(1.0)
                    self.wizard.set_busy(False)
                    self.world = payload
                    self._fill_all()
                    self.show_viewer()
                    return
                elif kind == "cancelled":
                    self.wizard.set_busy(False)
                    self.status_var.set("Генерация прервана.")
                    return
                else:
                    self.wizard.set_busy(False)
                    self.status_var.set("Ошибка генерации.")
                    messagebox.showerror("Ошибка", note)
                    return
        except queue.Empty:
            pass
        self.after(60, self._poll_progress)

    # ------------------------------------------------------------------
    # Заполнение вкладок
    # ------------------------------------------------------------------

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _show_welcome(self) -> None:
        self._set_text(self.chronicle_text, (
            "\n  Здесь появится летопись мира.\n\n"
            "  1. Нажмите «Случайный» — получите код вида «KR7M-93XD» —\n"
            "     или впишите свой: хоть код, хоть любое слово.\n"
            "  2. Укажите, сколько лет истории нужно сгенерировать.\n"
            "  3. Нажмите «Сгенерировать мир».\n\n"
            "  Один и тот же сид всегда даёт одну и ту же историю.\n"
        ))

    def _on_tab_changed(self, event=None) -> None:
        """Заполняет открываемую вкладку, если руки до неё ещё не дошли."""
        if self.world is None:
            return
        try:
            current = self.tabs.select()
        except tk.TclError:
            return
        if not current or current in self._filled:
            return
        self._filled.add(current)
        filler = self._fillers.get(current)
        if filler is None:
            return
        self.status_var.set("Собираю таблицу…")
        self.update_idletasks()
        filler()
        self._say_ready()

    def _fill_all(self) -> None:
        world = self.world
        self._filled = set()
        if self.atlas is not None:
            self.atlas.clear()     # чтобы не осталась карта прошлого мира
        self.refresh_chronicle()
        self._set_text(self.eras_text, chronicle.render_eras(world))
        self._set_text(self.folks_text, chronicle.render_folks(world))
        self._set_text(self.tongues_text, chronicle.render_tongues(world))
        self._set_text(self.peoples_text, chronicle.render_peoples(world))
        self._set_text(self.trade_text, chronicle.render_trade(world))
        self._set_text(self.expeditions_text,
                       chronicle.render_expeditions(world))
        self._set_text(self.regions_text, chronicle.render_regions(world))
        self._set_text(self.stats_text, chronicle.render_stats(world))
        self._on_tab_changed()
        self._say_ready()

    def _say_ready(self) -> None:
        world = self.world
        self.status_var.set(
            "Мир «%s» готов: %s, событий %d, стран %d, поселений %d, родов %d, "
            "личностей %d."
            % (world.seed_text, years_text(world.total_years), len(world.events),
               len(world.polities), len(world.settlements), len(world.houses),
               len(world.figures)))

    def refresh_chronicle(self) -> None:
        if self.world is None:
            return
        level = dict(IMPORTANCE_CHOICES).get(self.importance_var.get(), 3)
        race_id = ""
        chosen = self.race_var.get()
        for race in RACES:
            if race.name == chosen:
                race_id = race.id
                break
        self.status_var.set("Собираю летопись…")
        self.update_idletasks()
        text = chronicle.render_chronicle(
            self.world, min_importance=level, race_id=race_id,
            search=self.search_var.get())
        self._set_text(self.chronicle_text, text)
        self.status_var.set("Летопись обновлена.")

    def _fill_tree(self, tree, rows) -> None:
        tree.delete(*tree.get_children())
        for key, values in rows:
            tree.insert("", "end", iid=key, values=values)

    def _fill_polities(self) -> None:
        world = self.world
        rows = []
        for polity in world.polities.values():
            founder = world.figures.get(polity.founder_id)
            capital = world.settlements.get(polity.capital_id)
            rows.append((polity.id, (
                polity.name, polity.form, get_race(polity.race_id).name,
                polity.founded.year, founder.name if founder else "—",
                capital.name if capital else "—",
                len(polity.settlement_ids), polity.population,
                (world.faiths[polity.faith_id].name
                 if polity.faith_id in world.faiths else "—"),
                polity.status if polity.status == ACTIVE
                else "%s (%d)" % (polity.status, polity.ended.year))))
        self._fill_tree(self.polity_tree, rows)

    def _fill_cities(self) -> None:
        world = self.world
        rows = []
        for settlement in world.settlements.values():
            founder = world.figures.get(settlement.founder_id)
            polity = world.polities.get(settlement.polity_id)
            rows.append((settlement.id, (
                settlement.name, settlement.kind, get_race(settlement.race_id).name,
                settlement.founded.year, founder.name if founder else "—",
                polity.full_name if polity else "—",
                settlement.population,
                settlement.status if settlement.status == ACTIVE
                else "%s (%d)" % (settlement.status, settlement.ended.year))))
        self._fill_tree(self.city_tree, rows)

    def _fill_groups(self) -> None:
        world = self.world
        rows = []
        for tribe in world.tribes.values():
            founder = world.figures.get(tribe.founder_id)
            region = world.regions.get(tribe.region_id)
            rows.append((tribe.id, (
                tribe.name, tribe.word, get_race(tribe.race_id).name,
                tribe.founded.year, founder.name if founder else "—",
                region.name if region else "—", tribe.population,
                tribe.status if tribe.status == ACTIVE
                else "%s (%d)" % (tribe.status, tribe.ended.year))))
        for camp in world.camps.values():
            founder = world.figures.get(camp.founder_id)
            region = world.regions.get(camp.region_id)
            rows.append((camp.id, (
                camp.name, camp.word, get_race(camp.race_id).name,
                camp.founded.year, founder.name if founder else "—",
                region.name if region else "—", camp.population,
                camp.status if camp.status == ACTIVE
                else "%s (%d)" % (camp.status, camp.ended.year))))
        rows.sort(key=lambda row: row[1][3])
        self._fill_tree(self.group_tree, rows)

    def _refill_figures(self) -> None:
        if self.world is None:
            return
        self.status_var.set("Собираю таблицу…")
        self.update_idletasks()
        self._fill_figures()
        self._say_ready()

    def _fill_houses(self) -> None:
        world = self.world
        rows = []
        for house in world.houses.values():
            founder = world.figures.get(house.founder_id)
            polity = world.polities.get(house.polity_id)
            seat = world.settlements.get(house.seat_id)
            state = house.status
            if house.ended is not None:
                state = "%s (%d)" % (house.status, house.ended.year)
            rows.append((house.id, (
                house.full_name, get_race(house.race_id).name,
                house.founded.year, founder.name if founder else "—",
                house.rank, polity.full_name if polity else "—",
                seat.name if seat else "—", house.alive_count,
                house.thrones, state)))
        self._fill_tree(self.house_tree, rows)

    def _fill_faiths(self) -> None:
        from worldgen import pantheon as pan
        world = self.world
        rows = []
        for faith in sorted(world.faiths.values(), key=lambda f: f.founded.ordinal):
            races = ", ".join(RACES_BY_ID[rid].name for rid in faith.race_ids
                              if rid in RACES_BY_ID)
            rows.append((faith.id, (
                faith.name, pan.FAITH_KIND_NAMES.get(faith.kind, faith.kind),
                faith.founded.year, faith.status,
                pan.ALIGNMENT_NAMES.get(faith.alignment, ""),
                faith.followers, len(faith.deity_ids), len(faith.temple_ids),
                races)))
        self._fill_tree(self.faith_tree, rows)

    def _fill_calamities(self) -> None:
        from worldgen import catastrophe as cat
        world = self.world
        rows = []
        for calamity in sorted(world.calamities.values(),
                               key=lambda c: c.start.ordinal):
            years = "%d—%s" % (calamity.start.year,
                               calamity.end.year if calamity.end else "…")
            rows.append((calamity.id, (
                calamity.name, cat.KIND_NAMES.get(calamity.kind, calamity.kind),
                cat.SEVERITY_NAMES.get(calamity.severity, ""), years,
                len(calamity.region_ids),
                calamity.host_size or "—", calamity.deaths,
                calamity.resolution or "длится", len(calamity.relic_ids))))
        self._fill_tree(self.calamity_tree, rows)

    def _fill_figures(self) -> None:
        world = self.world
        only_noble = getattr(self, "only_noble", None)
        filtered = only_noble.get() if only_noble is not None else True
        rows = []
        for figure in world.figures.values():
            if filtered and not figure.deeds:
                continue
            house = world.houses.get(figure.house_id)
            rows.append((figure.id, (
                figure.name, get_race(figure.race_id).name,
                "жен." if figure.sex == "f" else "муж.",
                figure.lifespan_text(),
                house.full_name if house else "—",
                figure.titles[0] if figure.titles else "—",
                ", ".join(figure.roles) if figure.roles else "—",
                len(figure.deeds))))
        self._fill_tree(self.figure_tree, rows)
        if hasattr(self, "figures_note"):
            self.figures_note.set("показано %d из %d" % (len(rows), len(world.figures)))

    def _sort_tree(self, tree, column, descending) -> None:
        data = [(tree.set(item, column), item) for item in tree.get_children("")]

        def key(pair):
            try:
                return (0, float(pair[0]), "")
            except ValueError:
                return (1, 0.0, pair[0])

        data.sort(key=key, reverse=descending)
        for position, (_, item) in enumerate(data):
            tree.move(item, "", position)
        tree.heading(column, command=lambda: self._sort_tree(tree, column, not descending))

    # ------------------------------------------------------------------
    # Карточки сущностей
    # ------------------------------------------------------------------

    def _selected(self, tree):
        items = tree.selection()
        return items[0] if items else None

    def _on_polity_open(self, event) -> None:
        self._open_card(self._selected(self.polity_tree))

    def _on_city_open(self, event) -> None:
        self._open_card(self._selected(self.city_tree))

    def _on_group_open(self, event) -> None:
        self._open_card(self._selected(self.group_tree))

    def _on_figure_open(self, event) -> None:
        self._open_card(self._selected(self.figure_tree))

    def _on_house_open(self, event) -> None:
        self._open_card(self._selected(self.house_tree))

    def _on_calamity_open(self, event) -> None:
        self._open_card(self._selected(self.calamity_tree))

    def _on_faith_open(self, event) -> None:
        self._open_card(self._selected(self.faith_tree))

    def _open_card(self, entity_id) -> None:
        if not entity_id or self.world is None:
            return
        world = self.world
        entity = world.entity(entity_id)
        if entity is None:
            return

        lines = [world.entity_name(entity_id), "=" * 60, ""]
        for name, value in self._card_fields(entity):
            lines.append("  %-22s %s" % (name + ":", value))
        lines.extend(self._card_extra(entity))

        related = [event for event in world.events
                   if entity_id in event.subjects or entity_id in event.actors]
        if related:
            lines.extend(["", "СОБЫТИЯ", "-" * 60])
            for event in related:
                lines.append(chronicle.format_event(event, width=86))

        window = tk.Toplevel(self)
        window.title(world.entity_name(entity_id))
        window.geometry("900x560")
        window.configure(bg=BG)
        text = self._make_text(window)
        self._set_text(text, "\n".join(lines))

    def _card_fields(self, entity) -> list:
        world = self.world
        fields = []

        def name_of(entity_id):
            return world.entity_name(entity_id) if entity_id else "—"

        kind = type(entity).__name__
        if kind == "Figure":
            children = ", ".join(name_of(child) for child in entity.children) or "—"
            fields = [
                ("Раса", get_race(entity.race_id).name),
                ("Пол", "женский" if entity.sex == "f" else "мужской"),
                ("Знатность", "знатный род" if entity.noble else "простолюдин"),
                ("Родовое имя", entity.surname or "—"),
                ("Род", name_of(entity.house_id)),
                ("Годы жизни", entity.lifespan_text()),
                ("Рождение", entity.birth.long() if entity.birth else "—"),
                ("Смерть", entity.death.long() if entity.death else "—"),
                ("Причина смерти", entity.death_cause or "—"),
                ("Титулы", ", ".join(entity.titles) or "—"),
                ("Роли", ", ".join(entity.roles) or "—"),
                ("Отец", name_of(entity.father_id)),
                ("Мать", name_of(entity.mother_id)),
                ("Супруг(а)", name_of(entity.spouse_id)),
                ("Дети", children),
                ("Родина", name_of(entity.origin_region)),
                ("Связан с", name_of(entity.home_id)),
            ]
        elif kind == "Polity":
            from worldgen.races import SUCCESSION_NAMES
            fields = [
                ("Форма правления", entity.form),
                ("Раса", get_race(entity.race_id).name),
                ("Основана", entity.founded.long()),
                ("Основатель", name_of(entity.founder_id)),
                ("Столица", name_of(entity.capital_id)),
                ("Правящий род", name_of(entity.house_id)),
                ("Наследование", SUCCESSION_NAMES.get(entity.succession, "—")),
                ("Нынешний правитель", name_of(entity.ruler_id)),
                ("Правлений", len(entity.reign_ids)),
                ("Знатных родов", len(entity.house_ids)),
                ("Поселений", len(entity.settlement_ids)),
                ("Земли", ", ".join(name_of(rid) for rid in entity.region_ids) or "—"),
                ("Состояние", entity.status),
                ("Конец", entity.ended.long() if entity.ended else "—"),
                ("Причина", entity.end_reason or "—"),
            ]
        elif kind == "Settlement":
            fields = [
                ("Тип", entity.kind),
                ("Раса", get_race(entity.race_id).name),
                ("Основан", entity.founded.long()),
                ("Основатель", name_of(entity.founder_id)),
                ("Земля", name_of(entity.region_id)),
                ("Страна", name_of(entity.polity_id)),
                ("Столица", "да" if entity.is_capital else "нет"),
                ("Население", entity.population),
                ("Приметы города", ", ".join(entity.landmarks) or "—"),
                ("Из племени", name_of(entity.origin_tribe_id)),
                ("Состояние", entity.status),
                ("Конец", entity.ended.long() if entity.ended else "—"),
            ]
        elif kind == "Tribe":
            fields = [
                ("Тип", entity.word),
                ("Раса", get_race(entity.race_id).name),
                ("Основано", entity.founded.long()),
                ("Основатель", name_of(entity.founder_id)),
                ("Земля", name_of(entity.region_id)),
                ("Население", entity.population),
                ("Отделилось от", name_of(entity.parent_id)),
                ("Осело в", name_of(entity.settlement_id)),
                ("Состояние", entity.status),
                ("Конец", entity.ended.long() if entity.ended else "—"),
            ]
        elif kind == "House":
            fields = [
                ("Тип", entity.word),
                ("Раса", get_race(entity.race_id).name),
                ("Основан", entity.founded.long()),
                ("Основатель", name_of(entity.founder_id)),
                ("Ранг", entity.rank),
                ("Глава рода", name_of(entity.head_id)),
                ("Родовое гнездо", name_of(entity.seat_id)),
                ("Страна", name_of(entity.polity_id)),
                ("Всходил на престол", entity.thrones),
                ("Влияние", "%.1f" % entity.prestige),
                ("Членов рода", len(entity.members)),
                ("Живых", entity.alive_count),
                ("Отделился от", name_of(entity.parent_id)),
                ("Состояние", entity.status),
                ("Конец", entity.ended.long() if entity.ended else "—"),
            ]
        elif kind == "Faith":
            from worldgen import pantheon as pan
            fields = [
                ("Вид", pan.FAITH_KIND_NAMES.get(entity.kind, entity.kind)),
                ("Основана", entity.founded.long()),
                ("Основатель", name_of(entity.founder_id)),
                ("Мировоззрение", "%d — %s" % (
                    entity.alignment,
                    pan.ALIGNMENT_NAMES.get(entity.alignment, ""))),
                ("Под запретом", "да" if entity.forbidden else "нет"),
                ("Состояние", entity.status),
                ("Верующих", entity.followers),
                ("Наибольшее число", entity.peak_followers),
                ("Народы", ", ".join(RACES_BY_ID[rid].name
                                     for rid in entity.race_ids
                                     if rid in RACES_BY_ID) or "—"),
                ("Государственная в", ", ".join(name_of(pid)
                                                for pid in entity.polity_ids) or "—"),
                ("Глава веры", name_of(entity.high_priest_id)),
                ("Богов", len(entity.deity_ids)),
                ("Храмов", len(entity.temple_ids)),
                ("Отделилась от", name_of(entity.parent_id)),
                ("Конец", entity.ended.long() if entity.ended else "—"),
            ]
        elif kind == "Deity":
            from worldgen import pantheon as pan
            from worldgen.narrative_faith import domains_list, festival_line
            fields = [
                ("Титул", entity.title),
                ("Пол", {"m": "мужской", "f": "женский"}.get(entity.sex, "без пола")),
                ("Сферы", domains_list(entity.domains)),
                ("Мировоззрение", "%d — %s" % (
                    entity.alignment,
                    pan.ALIGNMENT_NAMES.get(entity.alignment, ""))),
                ("Знак", entity.symbol),
                ("Праздник", festival_line(entity)),
                ("Явился", entity.revealed.long() if entity.revealed else "—"),
                ("Народ", RACES_BY_ID[entity.race_id].name
                 if entity.race_id in RACES_BY_ID else "—"),
                ("Вера", name_of(entity.faith_id)),
                ("Состояние", entity.status),
            ]
        elif kind == "Temple":
            fields = [
                ("Вера", name_of(entity.faith_id)),
                ("Божество", name_of(entity.deity_id)),
                ("Город", name_of(entity.settlement_id)),
                ("Земля", name_of(entity.region_id)),
                ("Основан", entity.founded.long() if entity.founded else "—"),
                ("Строитель", name_of(entity.founder_id)),
                ("Величина", {1: "святилище", 2: "храм", 3: "великий храм"}.get(
                    entity.grandeur, "храм")),
                ("Состояние", entity.status),
                ("Конец", entity.ended.long() if entity.ended else "—"),
            ]
        elif kind == "Calamity":
            from worldgen import catastrophe as cat
            spec = cat.CATALOG_BY_KEY.get(entity.key)
            fields = [
                ("Вид", cat.KIND_NAMES.get(entity.kind, entity.kind)),
                ("Разновидность", spec.title if spec is not None else entity.key),
                ("Тяжесть", "%d — %s" % (entity.severity,
                                         cat.SEVERITY_NAMES.get(entity.severity, ""))),
                ("Начало", entity.start.long()),
                ("Конец", entity.end.long() if entity.end else "длится"),
                ("Длилось", "%d лет" % entity.years),
                ("Земли", ", ".join(name_of(rid) for rid in entity.region_ids)),
                ("Страны", ", ".join(name_of(pid) for pid in entity.polity_ids) or "—"),
                ("Врагов", entity.host_size or "—"),
                ("Во главе", name_of(entity.leader_id)),
                ("Военачальники", ", ".join(name_of(fid)
                                            for fid in entity.general_ids) or "—"),
                ("Погибло", entity.deaths),
                ("Потеряно поселений", entity.settlements_lost),
                ("Потеряно стран", entity.polities_lost),
                ("Исход", entity.resolution or "—"),
                ("Победители", ", ".join(name_of(fid)
                                         for fid in entity.hero_ids) or "—"),
                ("Полководцы", ", ".join(name_of(fid)
                                         for fid in entity.commander_ids) or "—"),
                ("Совпало с", ", ".join(name_of(cid)
                                        for cid in entity.compounded_with) or "—"),
                ("Выросло из", name_of(entity.parent_id)),
                ("Тёмные века до", entity.dark_age_until or "—"),
            ]
        elif kind == "Relic":
            fields = [
                ("Вид следа", entity.kind),
                ("Оставлен бедствием", name_of(entity.calamity_id)),
                ("Земля", name_of(entity.region_id)),
                ("Появился", entity.created.long()),
                ("Опасность", entity.potency),
                ("Состояние", entity.status),
                ("Потревожен", entity.awakened.long() if entity.awakened else "—"),
                ("Связан с", name_of(entity.figure_id)),
            ]
        elif kind == "Battle":
            fields = [
                ("Дата", entity.date.long()),
                ("Бедствие", name_of(entity.calamity_id)),
                ("Земля", name_of(entity.region_id)),
                ("Нападающих ведёт", name_of(entity.attacker_id)),
                ("Защитников ведут", ", ".join(name_of(fid)
                                               for fid in entity.defender_ids) or "—"),
                ("Победа", entity.winner),
                ("Полегло", entity.deaths),
                ("Пали", ", ".join(name_of(fid) for fid in entity.fallen_ids) or "—"),
                ("Решающая", "да" if entity.decisive else "нет"),
            ]
        elif kind == "Camp":
            fields = [
                ("Тип", entity.word),
                ("Раса", get_race(entity.race_id).name),
                ("Основан", entity.founded.long()),
                ("Вожак", name_of(entity.founder_id)),
                ("Земля", name_of(entity.region_id)),
                ("Население", entity.population),
                ("Состояние", entity.status),
                ("Конец", entity.ended.long() if entity.ended else "—"),
            ]
        return fields

    def _card_extra(self, entity) -> list:
        """Дополнительные разделы карточки: правления и члены рода."""
        world = self.world
        kind = type(entity).__name__
        lines = []

        def reign_rows(reigns):
            out = []
            for reign in reigns:
                ruler = world.figures.get(reign.ruler_id)
                house = world.houses.get(reign.house_id)
                polity = world.polities.get(reign.polity_id)
                out.append("  %-4d %5d—%-7s %-32s %-22s %s" % (
                    reign.number, reign.start.year,
                    reign.end.year if reign.end else "…",
                    (ruler.plain_name if ruler else "?")[:32],
                    (polity.full_name if polity else (house.full_name if house else "—"))[:22],
                    reign.end_reason or "правит"))
            return out

        if kind == "Polity":
            # «Почему эта держава такая»: живые следы её прошлого —
            # обиды, притязания, зависимости, долги.
            why = chronicle.polity_why(world, entity)
            if why:
                lines.extend(["", "ЧТО ЗА НЕЙ ЧИСЛИТСЯ", "-" * 60])
                lines.extend("  %s" % row for row in why)
            reigns = [world.reigns[r] for r in entity.reign_ids if r in world.reigns]
            if reigns:
                lines.extend(["", "ПРАВИТЕЛИ", "-" * 60])
                lines.extend(reign_rows(reigns))
            houses = [world.houses[h] for h in entity.house_ids if h in world.houses]
            if houses:
                lines.extend(["", "ЗНАТНЫЕ РОДА СТРАНЫ", "-" * 60])
                for house in houses:
                    lines.append("  %-26s %-12s влияние %.1f" % (
                        house.full_name, house.rank, house.prestige))

        elif kind == "House":
            reigns = [r for r in world.reigns.values() if r.house_id == entity.id]
            reigns.sort(key=lambda r: r.start.ordinal)
            if reigns:
                lines.extend(["", "ПРАВЛЕНИЯ РОДА", "-" * 60])
                lines.extend(reign_rows(reigns))
            members = [world.figures[m] for m in entity.members if m in world.figures]
            if members:
                lines.extend(["", "ЧЛЕНЫ РОДА", "-" * 60])
                for member in members:
                    mark = " (глава)" if member.id == entity.head_id else ""
                    lines.append("  %-34s %-14s %s%s" % (
                        member.plain_name[:34], member.lifespan_text(),
                        ", ".join(member.roles[:2]) or "—", mark))

        elif kind == "Figure":
            # Чего человек хотел и что из этого вышло. Это первое, что
            # стоит знать о нём: послужной список — уже следствие.
            path = world.path_of(entity.id)
            if path is not None:
                lines.extend(["", "ЧЕГО ХОТЕЛ" if entity.sex == "m"
                              else "ЧЕГО ХОТЕЛА", "-" * 60])
                lines.append("  %s%s" % (path.wish,
                                         " — %s" % path.about
                                         if path.about else ""))
                if path.hidden:
                    lines.append("  а на деле: %s" % path.hidden)
                if path.limits:
                    lines.append("  мешало: %s" % ", ".join(path.limits))
                lines.append("  чем кончилось: %s" % path.state)
                if path.steps:
                    lines.extend(["", "КАК ЭТО ШЛО", "-" * 60])
                    for item in path.steps:
                        lines.append("  %5d  %s" % (item["год"],
                                                    item["строка"]))
                lines.extend(["", "ЧТО ИЗ ЭТОГО ВЫШЛО", "-" * 60])
                lines.append("  на деле ...... %s" % (path.did or "—"))
                lines.append("  сам считал ... %s" % (path.thought or "—"))
                lines.append("  в летописи ... %s" % (path.written or "—"))
                if path.sung:
                    lines.append("  поют ......... %s" % path.sung)
                if path.irony:
                    lines.append("  и вот что вышло: %s" % path.irony)
                for item in path.legacy:
                    lines.append("  после (%d): %s" % (item["год"],
                                                       item["что"]))

            # Что человек помнит и с кем связан: по этому видно, почему
            # он поступал так, а не иначе.
            memories = world.memories_of(entity.id)
            if memories:
                lines.extend(["", "ЧТО ПОМНИТ", "-" * 60])
                for memory in memories[:10]:
                    about = world.entity_name(memory.about_id) \
                        if memory.about_id else ""
                    lines.append("  %-5d %-22s %s%s" % (
                        memory.year, memory.kind,
                        (about + ": ") if about else "",
                        memory.note or memory.tone))
            bonds = world.bonds_of(entity.id, alive=False)
            if bonds:
                lines.extend(["", "С КЕМ СВЯЗАН", "-" * 60])
                for bond in bonds[:10]:
                    other = world.figures.get(bond.other(entity.id))
                    path = " → ".join(item[1] for item in bond.turns) \
                        or bond.kind
                    lines.append("  %-32s %-28s с %d года%s" % (
                        (other.plain_name if other else "?")[:32], path,
                        bond.since,
                        ", оборвалась в %d" % bond.ended if bond.ended else ""))
            stories = [story for story in world.stories.values()
                       if any(item.get("кто") == entity.id
                              for item in story.cast)]
            if stories:
                stories.sort(key=lambda item: item.began.ordinal)
                lines.extend(["", "В КАКИХ ДЕЛАХ ЗАМЕШАН" if entity.sex == "m"
                              else "В КАКИХ ДЕЛАХ ЗАМЕШАНА", "-" * 60])
                for story in stories[:12]:
                    role = next((item.get("роль", "") for item in story.cast
                                 if item.get("кто") == entity.id), "")
                    lines.append("  %-5d %-38s %-22s %s"
                                 % (story.began.year, story.title[:38],
                                    role[:22], story.outcome))
            reigns = [r for r in world.reigns.values() if r.ruler_id == entity.id]
            reigns.sort(key=lambda r: r.start.ordinal)
            if reigns:
                lines.extend(["", "ПРАВЛЕНИЯ", "-" * 60])
                lines.extend(reign_rows(reigns))

        elif kind in ("Settlement", "Site", "Region"):
            # У места своя память: что тут рассказывают. Летопись помнит
            # основание и разорение, а быль — то, из-за чего это место
            # обходят стороной или ходят к нему за советом.
            told = world.stories_at(entity.id)
            if told:
                lines.extend(["", "ЧТО ТУТ РАССКАЗЫВАЮТ", "-" * 60])
                for story in told[:15]:
                    lines.append("  %-5d %-40s %-16s %s"
                                 % (story.began.year, story.title[:40],
                                    story.tone, story.outcome))

        elif kind == "Calamity":
            if entity.battle_ids:
                lines.extend(["", "СРАЖЕНИЯ", "-" * 60])
                for battle_id in entity.battle_ids:
                    battle = world.battles.get(battle_id)
                    if battle is None:
                        continue
                    lines.append("  %5d  %-44s победа: %-11s полегло %d" % (
                        battle.date.year, battle.name[:44], battle.winner,
                        battle.deaths))
            if entity.relic_ids:
                lines.extend(["", "СЛЕДЫ", "-" * 60])
                for relic_id in entity.relic_ids:
                    relic = world.relics.get(relic_id)
                    if relic is None:
                        continue
                    region = world.regions.get(relic.region_id)
                    lines.append("  %-34s %-22s %-14s %s" % (
                        relic.name[:34], relic.kind[:22],
                        region.name if region else "—", relic.status))
            if entity.deaths_by_polity:
                lines.extend(["", "ПОТЕРИ ПО СТРАНАМ", "-" * 60])
                for polity_id, dead in sorted(entity.deaths_by_polity.items(),
                                              key=lambda pair: -pair[1])[:12]:
                    polity = world.polities.get(polity_id)
                    lines.append("  %-40s %d" % (
                        polity.full_name if polity else polity_id, dead))
            if entity.deaths_by_race:
                lines.extend(["", "ПОТЕРИ ПО НАРОДАМ", "-" * 60])
                for race_id, dead in sorted(entity.deaths_by_race.items(),
                                            key=lambda pair: -pair[1])[:12]:
                    race = RACES_BY_ID.get(race_id)
                    lines.append("  %-40s %d" % (
                        race.name if race is not None else race_id, dead))

        elif kind == "Faith":
            if entity.deity_ids:
                from worldgen.narrative_faith import domains_list, festival_line
                lines.extend(["", "БОГИ ЭТОЙ ВЕРЫ", "-" * 60])
                for deity_id in entity.deity_ids:
                    deity = world.deities.get(deity_id)
                    if deity is None:
                        continue
                    lines.append("  %-40s %s" % (
                        deity.full_name[:40], domains_list(deity.domains)))
                    lines.append("      %s  праздник: %s" % (
                        deity.symbol, festival_line(deity)))
            temples = [world.temples[tid] for tid in entity.temple_ids
                       if tid in world.temples]
            if temples:
                lines.extend(["", "ХРАМЫ", "-" * 60])
                for temple in temples[:40]:
                    settlement = world.settlements.get(temple.settlement_id)
                    lines.append("  %-34s %-22s %s" % (
                        temple.name[:34],
                        settlement.name if settlement else "—", temple.status))

        elif kind == "Relic":
            children = [c for c in world.calamities.values()
                        if c.parent_id == entity.calamity_id
                        and entity.name in " ".join(c.notes)]
            if children:
                lines.extend(["", "ЧТО ИЗ ЭТОГО ВЫРОСЛО", "-" * 60])
                for child in children:
                    lines.append("  %5d  %s" % (child.start.year, child.name))
        return lines

    # ------------------------------------------------------------------
    # Файлы
    # ------------------------------------------------------------------

    def save_world(self) -> None:
        if self.world is None:
            messagebox.showinfo("Нечего сохранять", "Сначала сгенерируйте мир.")
            return
        path = filedialog.asksaveasfilename(
            title="Сохранить мир", defaultextension=".json",
            initialfile="мир-%s.json" % self.world.seed_text,
            filetypes=[("Мир генератора", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        storage.save_world(self.world, path)
        self.status_var.set("Мир сохранён: %s" % path)

    def open_world(self) -> None:
        path = filedialog.askopenfilename(
            title="Открыть мир",
            filetypes=[("Мир генератора", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            self.world = storage.load_world(path)
        except Exception as error:
            messagebox.showerror("Не удалось открыть", str(error))
            return
        settings = self.world.settings or {}
        self.wizard.seed_var.set(self.world.seed_text)
        self.wizard.years_var.set(str(self.world.total_years))
        self.wizard.regions_var.set(
            str(settings.get("regions", len(self.world.regions))))
        # Карта мира сохраняется ссылкой на файл: он мог и переехать.
        source = self.world.map_source or ""
        if source and os.path.exists(source):
            self.wizard.map_path = source
            self.wizard.set_map_mode(wizard_mod.MAP_FILE)
        self._fill_all()
        self.show_viewer()

    def export_text(self) -> None:
        if self.world is None:
            messagebox.showinfo("Нечего сохранять", "Сначала сгенерируйте мир.")
            return
        path = filedialog.asksaveasfilename(
            title="Сохранить летопись", defaultextension=".txt",
            initialfile="летопись-%s.txt" % self.world.seed_text,
            filetypes=[("Текст", "*.txt"), ("Все файлы", "*.*")])
        if not path:
            return
        storage.save_text(chronicle.full_text(self.world), path)
        self.status_var.set("Летопись сохранена: %s" % path)

    def show_about(self) -> None:
        messagebox.showinfo(
            "О программе",
            "Хронист — генератор фэнтезийных историй.\n\n"
            "Детерминированная генерация: один сид — один и тот же мир.\n"
            "Год: 12 месяцев по 30 дней. История делится на пять эпох.\n\n"
            "Блок 1: основа движка, расы, племена, города и страны.")


def run() -> None:
    ChronicleApp().mainloop()
