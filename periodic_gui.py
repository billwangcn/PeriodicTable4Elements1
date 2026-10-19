# -*- coding: utf-8 -*-
"""元素周期表 · Tkinter 桌面程序。

功能：
  1. 完整 18 列 × 7 行周期表（含镧系、锕系两行），点击任一元素查看详细信息
  2. 8 套配色方案：元素族别 / 按族（18 列）/ 按周期 / 电子区块 / 常温状态 /
     地壳丰度 / 电负性 / 发现年代
  3. 详情面板：主要化合物、主要存在形式、生产用途、地壳与宇宙丰度、较详细发现过程
  4. 导出与界面完全同色的 PDF 周期表（可选附带 118 个元素详情）
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import List, Optional

import pt_pdf
from color_schemes import DEFAULT_SCHEME, SCHEMES, Scheme
from elements_data import (
    ACTINIDES,
    BY_NUMBER,
    BY_SYMBOL,
    LANTHANIDES,
    Element,
    search,
    zh_display,
)

# ---------------------------------------------------------------- 界面配色
BG = "#f4f6f9"
PANEL = "#ffffff"
BORDER = "#d3dae3"
HEADER_BG = "#e9eef5"
HEADER_FG = "#5a6673"
TEXT = "#1f2933"
TEXT_SEC = "#5c6b7a"
ACCENT = "#1660d0"
SELECT_BORDER = "#e8890c"

GROUPS = 18
PERIODS = 7


# ---------------------------------------------------------------- 字体
_FONT_FAMILY: Optional[str] = None


def font_family() -> str:
    """惰性探测中文字体（必须在 Tk 根窗口创建之后调用）。"""
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        try:
            fams = set(tkfont.families())
        except Exception:  # noqa: BLE001
            fams = set()
        for n in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                  "Noto Sans CJK SC", "Microsoft JhengHei", "SimHei", "SimSun"):
            if n in fams:
                _FONT_FAMILY = n
                break
        else:
            _FONT_FAMILY = "TkDefaultFont"
    return _FONT_FAMILY


def f(size: int, weight: str = "normal") -> tuple:
    return (font_family(), size, weight)


def line_px(spec: tuple) -> int:
    return tkfont.Font(font=spec).metrics("linespace")


# ---------------------------------------------------------------- 可滚动容器
class Scrolled(tk.Frame):
    """带横纵向滚动条的容器。"""

    def __init__(self, master, bg: str = BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner.bind("<Configure>", self._sync)
        self.canvas.bind("<Configure>", self._on_canvas)
        self._bind_wheel(self.canvas)

    def _sync(self, _e=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e) -> None:
        self.canvas.itemconfig(self.win, width=max(e.width, self.inner.winfo_reqwidth()))

    def _bind_wheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>",
                    lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        widget.bind("<Shift-MouseWheel>",
                    lambda e: self.canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))

    def bind_inner_wheel(self) -> None:
        for w in (self.inner,) + tuple(self.inner.winfo_children()):
            self._bind_wheel(w)


# ---------------------------------------------------------------- 主程序
class PeriodicTableApp(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.scheme: Scheme = DEFAULT_SCHEME
        self.selected: Element = BY_NUMBER[26]
        self._cells = {}
        self._detail_cache = None

        self.title("元素周期表 · 118 种元素")
        self.configure(bg=BG)

        self._metrics()
        width = min(self.winfo_screenwidth() - 30, self.table_w + 400 + 46)
        height = min(self.winfo_screenheight() - 70, self.table_h + 250)
        self.geometry(f"{max(1080, width)}x{max(720, height)}+20+10")
        self.minsize(940, 620)

        self._build_top()
        self._build_body()
        self._build_status()
        self.render_table()
        self.render_legend()
        self.show_detail(self.selected)

    # ---------------- 尺寸度量 ----------------
    def _metrics(self) -> None:
        num_ls = line_px(f(7))
        sym_ls = line_px(f(11, "bold"))
        zh_ls = line_px(f(8))
        mass_ls = line_px(f(6))
        self.cell_h = num_ls + sym_ls + zh_ls + mass_ls + 10
        self.cell_w = max(52, int(zh_ls * 2.9))
        self.label_w = max(30, int(line_px(f(8)) * 2.4))
        self.head_h = line_px(f(7, "bold")) + 6
        self.table_w = self.label_w + GROUPS * (self.cell_w + 2)
        self.table_h = (self.head_h + PERIODS * (self.cell_h + 2)
                        + 14 + 2 * (self.cell_h + 2))

    # ---------------- 顶栏 ----------------
    def _build_top(self) -> None:
        top = tk.Frame(self, bg=PANEL, height=52)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        inner = tk.Frame(top, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=12, pady=8)

        tk.Label(inner, text="元素周期表", bg=PANEL, fg=TEXT,
                 font=f(14, "bold")).pack(side="left")
        tk.Label(inner, text="118 种元素 · 公历农历无关 · 支持 PDF 导出",
                 bg=PANEL, fg=TEXT_SEC, font=f(9)).pack(side="left", padx=(10, 0))

        right = tk.Frame(inner, bg=PANEL)
        right.pack(side="right")

        ttk.Button(right, text="导出 PDF…", command=self.export_pdf).pack(side="right", padx=(8, 0))

        self.scheme_var = tk.StringVar(value=self.scheme.name)
        cb = ttk.Combobox(right, values=[s.name for s in SCHEMES],
                          textvariable=self.scheme_var, state="readonly", width=18)
        cb.pack(side="right", padx=(8, 0))
        cb.bind("<<ComboboxSelected>>", self._on_scheme)
        tk.Label(right, text="配色方案：", bg=PANEL, fg=TEXT, font=f(9)).pack(side="right")

        box = tk.Frame(inner, bg=PANEL)
        box.pack(side="right", padx=(0, 16))
        self.search_var = tk.StringVar()
        ent = tk.Entry(box, textvariable=self.search_var, width=12, font=f(9),
                       relief="solid", bd=1)
        ent.pack(side="left", ipady=2)
        ent.bind("<Return>", lambda e: self._do_search())
        ttk.Button(box, text="搜索", width=6, command=self._do_search).pack(side="left", padx=(4, 0))
        tk.Label(box, text="序数/符号/中英文：", bg=PANEL, fg=TEXT_SEC,
                 font=f(9)).pack(side="left", padx=(0, 6))

    # ---------------- 主体 ----------------
    def _build_body(self) -> None:
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        self.scroll = Scrolled(left, bg=BG)
        self.scroll.pack(fill="both", expand=True)
        self.table_host = self.scroll.inner

        legend_box = tk.LabelFrame(left, text=" 图例 ", bg=PANEL, fg=TEXT_SEC,
                                   font=f(9), bd=1, relief="solid", labelanchor="nw")
        legend_box.pack(fill="x", pady=(8, 0))
        self.legend_host = tk.Frame(legend_box, bg=PANEL)
        self.legend_host.pack(fill="x", padx=8, pady=6)

        right = tk.Frame(body, bg=PANEL, width=400)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)
        self._build_detail(right)

    def _build_detail(self, parent: tk.Frame) -> None:
        head = tk.Frame(parent, bg=PANEL)
        head.pack(fill="x", padx=10, pady=(10, 4))

        self.dtl_symbol = tk.Label(head, text="Fe", bg=PANEL, fg=ACCENT, font=f(26, "bold"))
        self.dtl_symbol.pack(side="left")
        box = tk.Frame(head, bg=PANEL)
        box.pack(side="left", padx=(10, 0), fill="x")
        self.dtl_name = tk.Label(box, text="铁", bg=PANEL, fg=TEXT, font=f(13, "bold"),
                                 anchor="w")
        self.dtl_name.pack(fill="x")
        self.dtl_sub = tk.Label(box, text="Iron · 第 8 族", bg=PANEL, fg=TEXT_SEC,
                                font=f(9), anchor="w")
        self.dtl_sub.pack(fill="x")

        nav = tk.Frame(parent, bg=PANEL)
        nav.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Button(nav, text="◀ 上一个", command=lambda: self._step(-1)).pack(side="left")
        ttk.Button(nav, text="下一个 ▶", command=lambda: self._step(1)).pack(side="left", padx=(6, 0))
        ttk.Button(nav, text="复制详情", command=self._copy_detail).pack(side="right")

        wrap = tk.Frame(parent, bg=BORDER)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        # wrap="char" 让中文按字折行，避免中英混排时右侧出现大片空白
        self.text = tk.Text(wrap, wrap="char", relief="flat", bd=0, bg=PANEL,
                            fg=TEXT, font=f(10), padx=12, pady=10, spacing1=1,
                            spacing2=1, spacing3=2, cursor="arrow")
        sb = ttk.Scrollbar(wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_configure("h2", font=f(10, "bold"), foreground=ACCENT,
                                spacing1=10, spacing3=3)
        self.text.tag_configure("key", font=f(9, "bold"), foreground=TEXT_SEC)
        self.text.tag_configure("body", font=f(10), foreground=TEXT, lmargin1=4, lmargin2=4)
        self.text.tag_configure("lead", font=f(10, "bold"), foreground=TEXT)
        self.text.tag_configure("sep", font=f(1))
        self.text.configure(state="disabled")

    def _build_status(self) -> None:
        bar = tk.Frame(self, bg=PANEL, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status = tk.StringVar(value="点击元素查看详细信息")
        tk.Label(bar, textvariable=self.status, bg=PANEL, fg=TEXT_SEC, font=f(9),
                 anchor="w").pack(fill="x", padx=12)

    # ---------------- 周期表 ----------------
    def render_table(self) -> None:
        for w in self.table_host.winfo_children():
            w.destroy()
        self._cells.clear()

        cw, ch = self.cell_w, self.cell_h
        host = self.table_host
        host.configure(bg=BG)

        host.columnconfigure(0, minsize=self.label_w)
        for g in range(1, GROUPS + 1):
            host.columnconfigure(g, minsize=cw)

        host.rowconfigure(0, minsize=self.head_h)
        tk.Label(host, text="族", bg=HEADER_BG, fg=TEXT_SEC, font=f(7, "bold")).grid(
            row=0, column=0, sticky="nsew", padx=1, pady=1)
        for g in range(1, GROUPS + 1):
            tk.Label(host, text=str(g), bg=HEADER_BG, fg=HEADER_FG,
                     font=f(7, "bold")).grid(row=0, column=g, sticky="nsew", padx=1, pady=1)

        for p in range(1, PERIODS + 1):
            host.rowconfigure(p, minsize=ch)
            tk.Label(host, text=str(p), bg=HEADER_BG, fg=TEXT_SEC, font=f(8, "bold")).grid(
                row=p, column=0, sticky="nsew", padx=1, pady=1)
            for g in range(1, GROUPS + 1):
                e = self._at(p, g)
                if e is None and p in (6, 7) and g == 3:
                    self._placeholder(host, p, g, "57-71" if p == 6 else "89-103",
                                      "镧系" if p == 6 else "锕系")
                elif e is None:
                    tk.Frame(host, bg=BG).grid(row=p, column=g, sticky="nsew")
                else:
                    c = self._make_cell(host, e)
                    c.grid(row=p, column=g, sticky="nsew", padx=1, pady=1)

        host.rowconfigure(8, minsize=14)
        tk.Frame(host, bg=BG).grid(row=8, column=0, columnspan=GROUPS + 1)

        for row_off, seq, title in ((9, LANTHANIDES, "镧系"), (10, ACTINIDES, "锕系")):
            host.rowconfigure(row_off, minsize=ch)
            tk.Label(host, text=title, bg=HEADER_BG, fg=TEXT_SEC, font=f(7, "bold")).grid(
                row=row_off, column=0, sticky="nsew", padx=1, pady=1)
            for i, e in enumerate(seq):
                col = 3 + i
                if col > GROUPS:
                    break
                c = self._make_cell(host, e)
                c.grid(row=row_off, column=col, sticky="nsew", padx=1, pady=1)

        self.scroll.bind_inner_wheel()
        self._highlight_selected()

    @staticmethod
    def _at(period: int, group: int) -> Optional[Element]:
        for e in BY_NUMBER.values():
            if e.period == period and e.group == group and e.group is not None \
                    and e.category not in ("lanthanide", "actinide"):
                return e
        return None

    def _placeholder(self, host, row, col, span: str, title: str) -> None:
        cell = tk.Frame(host, bg="#eef2f7", highlightthickness=1,
                        highlightbackground=BORDER)
        tk.Label(cell, text=span, bg="#eef2f7", fg=TEXT_SEC, font=f(7)).pack(pady=(6, 0))
        tk.Label(cell, text=title, bg="#eef2f7", fg=TEXT_SEC, font=f(8, "bold")).pack()
        cell.bind("<Button-1>", lambda e, s=span: self._jump_span(s))
        for w in cell.winfo_children():
            w.bind("<Button-1>", lambda e, s=span: self._jump_span(s))
        cell.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)

    def _jump_span(self, span: str) -> None:
        n = int(span.split("-")[0])
        self.select(BY_NUMBER[n])

    def _make_cell(self, host, e: Element) -> tk.Frame:
        bg = self.scheme.color(e)
        fg = self.scheme.text_color(e)
        zh = zh_display(e)

        cell = tk.Frame(host, bg=bg, highlightthickness=1, highlightbackground=BORDER,
                        cursor="hand2")
        cell.grid_propagate(False)

        tk.Label(cell, text=str(e.number), bg=bg, fg=fg, font=f(6)).pack(anchor="w", padx=3)
        tk.Label(cell, text=e.symbol, bg=bg, fg=fg, font=f(11, "bold")).pack(pady=(1, 0))
        tk.Label(cell, text=zh, bg=bg, fg=fg, font=f(8)).pack()
        tk.Label(cell, text=e.mass, bg=bg, fg=fg, font=f(6)).pack()

        widgets = [cell] + list(cell.winfo_children())
        for w in widgets:
            w.bind("<Button-1>", lambda ev, el=e: self.select(el))
            w.bind("<Enter>", lambda ev, el=e: self._hover(el))
        self._cells[e.number] = cell
        return cell

    def _hover(self, e: Element) -> None:
        self.status.set(f"{e.number} {e.symbol} {zh_display(e)} {e.en}"
                        f" · {e.category_name} · {e.group_label} · 第 {e.period} 周期")

    def _highlight_selected(self) -> None:
        for num, cell in self._cells.items():
            if num == self.selected.number:
                cell.configure(highlightthickness=3, highlightbackground=SELECT_BORDER)
            else:
                cell.configure(highlightthickness=1, highlightbackground=BORDER)

    def select(self, e) -> None:
        """选中元素。可接受 Element 对象，也可接受原子序数或元素符号。"""
        if not isinstance(e, Element):
            key = str(e).strip()
            e = BY_NUMBER.get(int(key)) if key.isdigit() else BY_SYMBOL.get(key)
            if e is None:
                return
        self.selected = e
        self._highlight_selected()
        self.show_detail(e)
        self.status.set(f"已选中：{e.number} {e.symbol} {zh_display(e)} {e.en}")

    def _step(self, delta: int) -> None:
        n = self.selected.number + delta
        if 1 <= n <= 118:
            self.select(BY_NUMBER[n])

    # ---------------- 图例 ----------------
    def render_legend(self) -> None:
        for w in self.legend_host.winfo_children():
            w.destroy()
        chips = self.scheme.legend
        cols = 9
        for i, (label, color) in enumerate(chips):
            chip = tk.Frame(self.legend_host, bg=PANEL)
            chip.grid(row=i // cols, column=i % cols, sticky="w", padx=(0, 12), pady=2)
            swatch = tk.Label(chip, text="  ", bg=color, relief="solid", bd=1,
                              highlightthickness=0)
            swatch.pack(side="left")
            tk.Label(chip, text=label, bg=PANEL, fg=TEXT_SEC, font=f(8)).pack(
                side="left", padx=(4, 0))
        tk.Label(self.legend_host, text=f"（{self.scheme.hint}）", bg=PANEL,
                 fg=TEXT_SEC, font=f(8)).grid(row=(len(chips) // cols) + 1, column=0,
                                              columnspan=cols, sticky="w", pady=(2, 0))

    def _on_scheme(self, _e=None) -> None:
        name = self.scheme_var.get()
        for s in SCHEMES:
            if s.name == name:
                self.scheme = s
                break
        self.render_table()
        self.render_legend()
        self.show_detail(self.selected)

    # ---------------- 搜索 ----------------
    def _do_search(self) -> None:
        kw = self.search_var.get().strip()
        if not kw:
            return
        hits = search(kw)
        if not hits:
            messagebox.showinfo("搜索", f"没有匹配“{kw}”的元素。\n"
                                        f"可输入：原子序数（26）、符号（Fe）、中文名（铁）或英文名（iron）。")
            return
        self.select(hits[0])
        if len(hits) > 1:
            names = "、".join(f"{h.number}{h.symbol}{zh_display(h)}" for h in hits[:8])
            self.status.set(f"匹配 {len(hits)} 个，已选中第一个：{names}")

    # ---------------- 详情 ----------------
    def show_detail(self, e: Element) -> None:
        zh = zh_display(e)
        self.dtl_symbol.configure(text=e.symbol)
        self.dtl_name.configure(text=f"{e.number} · {zh}")
        sub = [e.en, e.category_name]
        if e.group is not None:
            sub.append(e.group_label)
        sub.append(f"第 {e.period} 周期")
        self.dtl_sub.configure(text=" · ".join(sub))

        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")

        def h2(title: str) -> None:
            t.insert("end", "\n" + title + "\n", "h2")

        def kv(k: str, v: str) -> None:
            t.insert("end", f"  {k}：", "key")
            t.insert("end", v + "\n", "body")

        def para(text: str) -> None:
            t.insert("end", "  " + text + "\n", "body")

        bg = self.scheme.color(e)
        t.insert("end", f"{e.number} {e.symbol}  {zh}（{e.en}）\n", "lead")
        parts = [e.category_name]
        if e.group is not None:
            parts.append(e.group_label)
        parts += [f"第 {e.period} 周期", f"{e.block} 区"]
        t.insert("end", "所属：" + "　".join(parts) + "\n", "body")
        t.insert("end",
                 f"当前配色：{self.scheme.name}　格底色 {bg}（{self.scheme.hint}）\n", "body")

        h2("【基本参数】")
        kv("相对原子质量", e.mass)
        kv("电子排布", e.config)
        kv("电负性（鲍林）", e.electroneg_text)
        kv("常温状态", e.phase)
        kv("元素族别", e.category_name + (f"（{e.group_label}）" if e.group is not None
                                          else "（不属于 1~18 族的独立序列）"))
        kv("电子区块", f"{e.block} 区")

        h2("【发现过程】")
        kv("发现年代", e.era)
        kv("发现者 / 提出者", e.discoverer)
        para(e.story)

        h2("【丰度】")
        kv("地壳丰度", e.crust_text)
        kv("宇宙丰度", e.cosmic_text)

        h2("【在自然界的主要存在形式】")
        para(e.occurrence)

        h2("【主要化合物】")
        para(e.compounds)

        h2("【在生产中的用途】")
        para(e.uses)

        t.insert("end", "\n")
        t.configure(state="disabled")
        t.yview_moveto(0)
        self._detail_cache = t.get("1.0", "end")

    def _copy_detail(self) -> None:
        txt = self.text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.status.set(f"已复制 {self.selected.symbol} 的详细信息到剪贴板")

    # ---------------- 导出 ----------------
    def export_pdf(self) -> None:
        ExportDialog(self)


# ---------------------------------------------------------------- 导出对话框
class ExportDialog(tk.Toplevel):
    def __init__(self, app: PeriodicTableApp):
        super().__init__(app)
        self.app = app
        self.title("导出 PDF 周期表")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        pad = {"padx": 12, "pady": 6}
        row = 0

        tk.Label(self, text="配色方案：", bg=PANEL, font=f(10)).grid(
            row=row, column=0, sticky="w", **pad)
        self.scheme_var = tk.StringVar(value=app.scheme.name)
        ttk.Combobox(self, values=[s.name for s in SCHEMES], textvariable=self.scheme_var,
                     state="readonly", width=20).grid(row=row, column=1, columnspan=2,
                                                      sticky="w", **pad)
        row += 1

        tk.Label(self, text="纸张版式：", bg=PANEL, font=f(10)).grid(
            row=row, column=0, sticky="w", **pad)
        self.paper_var = tk.StringVar(value="A4 横向")
        box = tk.Frame(self, bg=PANEL)
        box.grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        for p in ("A4 横向", "A3 横向", "A4 纵向"):
            ttk.Radiobutton(box, text=p, value=p, variable=self.paper_var).pack(side="left")
        row += 1

        self.legend_var = tk.BooleanVar(value=True)
        self.detail_var = tk.BooleanVar(value=False)
        self.sel_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="包含配色图例", variable=self.legend_var, bg=PANEL,
                       font=f(10), anchor="w").grid(row=row, column=1, columnspan=2,
                                                    sticky="w", **pad)
        row += 1
        tk.Checkbutton(self, text=f"附带当前元素（{app.selected.symbol}）详情页",
                       variable=self.sel_var, bg=PANEL, font=f(10), anchor="w").grid(
            row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1
        tk.Checkbutton(self, text="附带全部 118 个元素详情（页数较多）",
                       variable=self.detail_var, bg=PANEL, font=f(10), anchor="w").grid(
            row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1

        tk.Label(self, text="保存路径：", bg=PANEL, font=f(10)).grid(
            row=row, column=0, sticky="w", **pad)
        self.path_var = tk.StringVar(value=pt_pdf.build_default_path(app.scheme.name))
        tk.Entry(self, textvariable=self.path_var, width=42, font=f(9), relief="solid",
                 bd=1).grid(row=row, column=1, sticky="w", **pad)
        ttk.Button(self, text="浏览…", width=8, command=self._browse).grid(
            row=row, column=2, sticky="w", **pad)
        row += 1

        btns = tk.Frame(self, bg=PANEL)
        btns.grid(row=row, column=0, columnspan=3, pady=(10, 12))
        ttk.Button(btns, text="开始导出", command=self._run).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right")

        self.geometry("+%d+%d" % (app.winfo_rootx() + 220, app.winfo_rooty() + 140))
        self.wait_visibility()
        self.focus_force()

    def _browse(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".pdf", filetypes=[("PDF 文件", "*.pdf")],
            initialfile=os.path.basename(self.path_var.get()),
            title="保存周期表 PDF")
        if path:
            self.path_var.set(path)

    def _run(self) -> None:
        name = self.scheme_var.get()
        scheme = next((s for s in SCHEMES if s.name == name), self.app.scheme)
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("导出", "请选择保存路径。", parent=self)
            return
        try:
            out = pt_pdf.export_periodic_table_pdf(
                path=path, scheme=scheme, paper=self.paper_var.get(),
                with_legend=self.legend_var.get(),
                detail_element=self.app.selected if self.sel_var.get() else None,
                all_details=self.detail_var.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导出失败", f"{exc}", parent=self)
            return
        self.destroy()
        self.app.status.set(f"已导出：{out}")
        if messagebox.askyesno("导出完成", f"PDF 已生成：\n{out}\n\n是否立即打开？",
                               parent=self.app):
            try:
                if sys.platform.startswith("win"):
                    os.startfile(out)  # noqa: S606
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", out])
                else:
                    subprocess.Popen(["xdg-open", out])
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    app = PeriodicTableApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
