# -*- coding: utf-8 -*-
"""Список разделов слева вместо ленты вкладок.

Разделов летописи тридцать восемь. В одну строку они не помещаются:
ttk сжимает подписи до «Ль» и «Пр», и найти нужное нельзя — только
тыкать наугад. Здесь разделы собраны в дерево по смыслу: слева девять
групп, внутри — полные названия, справа — сам раздел.

Снаружи этот виджет ведёт себя как ttk.Notebook: те же add, select,
tabs, tab, index и то же событие <<NotebookTabChanged>>, — чтобы окно
летописи не знало, чем ему показывают разделы. Чего нет, того нет:
разделы не прячутся и не удаляются (forget, hide, insert), потому что
летопись этого никогда не просит.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# Порядок групп и что в какой лежит. Раздел, которого здесь нет,
# попадёт в «Прочее» — лучше так, чем потерять его совсем.
GROUPS = (
    ("Мир", ("Летопись", "Эпохи", "Земли", "Как менялся мир", "Итоги")),
    ("Державы", ("Страны", "Города", "Племена и лагеря", "Державы и народы",
                 "Политика", "Законы")),
    ("Война", ("Войны", "Походы", "Крепости и роты", "Смуты", "Заговоры",
               "Посольства и тайны")),
    ("Люди", ("Правители", "Знать", "Знатные рода", "Личности",
              "Память и связи")),
    ("Народы", ("Народы", "Языки", "Переселения", "Растворение народов")),
    ("Вера", ("Веры", "Пантеон")),
    ("Хозяйство", ("Хозяйство", "Гильдии", "Ремёсла")),
    ("Чудеса", ("Чудовища", "Вещи", "Места", "Своды и легенды")),
    ("Беды", ("Бедствия", "Цепи бедствий", "Нити причин")),
)

OTHER = "Прочее"

_GROUP_OF = {}
for _name, _titles in GROUPS:
    for _title in _titles:
        _GROUP_OF[_title] = _name


class SideTabs(ttk.Frame):
    """Тот же Notebook, только вкладки стоят списком слева."""

    def __init__(self, master, width: int = 210, **kwargs):
        ttk.Frame.__init__(self, master, **kwargs)
        self._frames = []          # окна разделов по порядку добавления
        self._titles = []
        self._nodes = []           # узел дерева для каждого раздела
        self._groups = {}          # имя группы -> узел дерева
        self._current = -1

        left = ttk.Frame(self)
        left.pack(side="left", fill="y")
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse",
                                 height=24)
        self.tree.column("#0", width=width, stretch=False)
        bar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.config(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="y", expand=True)
        bar.pack(side="left", fill="y")

        self.holder = ttk.Frame(self)
        self.holder.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.tree.bind("<<TreeviewSelect>>", self._chosen)

    # ------------------------------------------------------------------
    # То, что снаружи выглядит как Notebook
    # ------------------------------------------------------------------

    def add(self, child, text: str = "", **kwargs) -> None:
        group = _GROUP_OF.get(text, OTHER)
        parent = self._groups.get(group)
        if parent is None:
            parent = self.tree.insert("", self._place_for(group), text=group,
                                      open=True)
            self._groups[group] = parent
        node = self.tree.insert(parent, "end", text="  " + text)
        self._frames.append(child)
        self._titles.append(text)
        self._nodes.append(node)
        if len(self._frames) == 1:
            self._show(0)

    def _place_for(self, group: str) -> int:
        """Куда вставить группу, чтобы порядок был задуманный, а не
        случайный — какой раздел раньше добавили."""
        order = [name for name, _ in GROUPS] + [OTHER]
        place = order.index(group) if group in order else len(order)
        number = 0
        for node in self.tree.get_children(""):
            name = self.tree.item(node, "text")
            other = order.index(name) if name in order else len(order)
            if other > place:
                break
            number += 1
        return number

    def tabs(self) -> list:
        return [str(frame) for frame in self._frames]

    def tab(self, item, option=None, **kwargs):
        """Прочитать или переименовать раздел — как у ttk.Notebook."""
        index = self._index_of(item)
        if "text" in kwargs:
            self._titles[index] = kwargs["text"]
            self.tree.item(self._nodes[index], text="  " + kwargs["text"])
        if option in ("text", "-text"):
            return self._titles[index]
        return {"text": self._titles[index]}

    def index(self, item) -> int:
        if item == "current":
            return max(0, self._current)
        if item == "end":
            return len(self._frames)     # у Notebook «end» — это счёт разделов
        return self._index_of(item)

    def select(self, item=None):
        if item is None:
            if not self._frames or self._current < 0:
                return ""
            return str(self._frames[self._current])
        self._show(self._index_of(item))
        return None

    # ------------------------------------------------------------------
    # Внутреннее
    # ------------------------------------------------------------------

    def _index_of(self, item) -> int:
        if isinstance(item, int):
            return item
        name = str(item)
        for number, frame in enumerate(self._frames):
            if str(frame) == name:
                return number
        for number, title in enumerate(self._titles):
            if title == name:
                return number
        raise tk.TclError("нет такого раздела: %s" % name)

    def _chosen(self, event=None) -> None:
        picked = self.tree.selection()
        if not picked:
            return
        node = picked[0]
        if node in self._nodes:
            self._show(self._nodes.index(node))
            return
        # Ткнули в имя группы: показываем первый раздел из неё.
        children = self.tree.get_children(node)
        if children:
            self.tree.selection_set(children[0])

    def _show(self, index: int) -> None:
        if index < 0 or index >= len(self._frames):
            return
        if index != self._current:
            for frame in self._frames:
                frame.pack_forget()
            self._frames[index].pack(in_=self.holder, fill="both", expand=True)
            self._current = index
        node = self._nodes[index]
        if self.tree.selection() != (node,):
            self.tree.selection_set(node)
        if index == 0:
            self.tree.yview_moveto(0.0)    # у первого раздела видно и заголовок
        else:
            self.tree.see(node)
        self.event_generate("<<NotebookTabChanged>>")
