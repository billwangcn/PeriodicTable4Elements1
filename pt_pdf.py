# -*- coding: utf-8 -*-
"""周期表 PDF 导出（reportlab）。

导出内容与界面使用同一套配色方案与显示规则：
  1. 首页：着色周期表（18 列 × 7 行 + 镧系/锕系两行）+ 标题 + 图例 + 页脚
  2. 可选：当前选中元素的详情页
  3. 可选：全部 118 个元素的详情页（每页一个）

中文字体自动嵌入（微软雅黑优先，其次黑体/宋体）；扩展区生僻字自动回退为“钅+声旁”写法。
"""
from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from color_schemes import Scheme, get as scheme_get
from elements_data import (
    ACTINIDES,
    BY_NUMBER,
    LANTHANIDES,
    Element,
    zh_display,
)

# ---------------------------------------------------------------- 字体
_REG_NAME = "PT-CJK"
_BOLD_NAME = "PT-CJK-Bold"
_NAME_REG = "Helvetica"       # 注册成功后实际可用的字体名
_NAME_BOLD = "Helvetica"
_FONT_READY = False
_GLYPH_OK = None


def _register_fonts() -> None:
    global _FONT_READY, _GLYPH_OK, _NAME_REG, _NAME_BOLD
    if _FONT_READY:
        return
    candidates = [
        (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"),
        (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simhei.ttf"),
        (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simsun.ttc"),
        ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    ]
    for reg_path, bold_path in candidates:
        try:
            if not os.path.exists(reg_path):
                continue
            pdfmetrics.registerFont(TTFont(_REG_NAME, reg_path, subfontIndex=0))
            bpath = bold_path if os.path.exists(bold_path) else reg_path
            pdfmetrics.registerFont(TTFont(_BOLD_NAME, bpath, subfontIndex=0))
            pdfmetrics.registerFontFamily(_REG_NAME, normal=_REG_NAME, bold=_BOLD_NAME)
            _NAME_REG, _NAME_BOLD = _REG_NAME, _BOLD_NAME
            _FONT_READY = True
            _GLYPH_OK = _make_glyph_checker(_REG_NAME)
            return
        except Exception:  # noqa: BLE001
            continue

    # 兜底：reportlab 内置的 Adobe CID 字体（无需外部字体文件）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _NAME_REG = _NAME_BOLD = "STSong-Light"
    except Exception:  # noqa: BLE001
        _NAME_REG = _NAME_BOLD = "Helvetica"
    _FONT_READY = True
    if _GLYPH_OK is None:
        _GLYPH_OK = lambda ch: ord(ch) <= 0x9FA5  # noqa: E731


def _make_glyph_checker(font_name: str):
    try:
        face = pdfmetrics.getFont(font_name).face
        cmap = face.charToGlyph
    except Exception:  # noqa: BLE001
        return lambda ch: ord(ch) <= 0x9FA5

    def ok(ch: str) -> bool:
        code = ord(ch)
        if code <= 0x9FA5:
            return True
        return code in cmap and cmap[code] != 0

    return ok


def _ensure() -> None:
    _register_fonts()


def font_regular() -> str:
    _ensure()
    return _NAME_REG


def font_bold() -> str:
    _ensure()
    return _NAME_BOLD


def glyph_ok(ch: str) -> bool:
    _ensure()
    if _GLYPH_OK is None:
        return ord(ch) <= 0x9FA5
    return _GLYPH_OK(ch)


def zh(e: Element) -> str:
    return zh_display(e, glyph_ok)


# ---------------------------------------------------------------- 排版常量
PAPERS = {
    "A4 横向": lambda: landscape(A4),
    "A3 横向": lambda: landscape(A3),
    "A4 纵向": lambda: portrait(A4),
}

MARGIN = 10 * mm
TITLE_H = 15 * mm
FOOTER_H = 9 * mm
GAP = 0.55 * mm
LABEL_W = 8 * mm
HEADER_H = 4.6 * mm
SPACER_H = 2.6 * mm

INK = colors.HexColor("#1f2933")
INK_SEC = colors.HexColor("#5c6b7a")
GRID = colors.HexColor("#b9c2cd")
HEADER_BG = colors.HexColor("#e9eef5")
PLACE_BG = colors.HexColor("#eef2f7")
ACCENT = colors.HexColor("#1660d0")


def _hex2color(value: str) -> colors.Color:
    try:
        return colors.HexColor(value)
    except Exception:  # noqa: BLE001
        return colors.white


# ------------------------------------------------- 文本工具（支持上/下标）
#: 微软雅黑等常见字体不含 Unicode 上下标字符，这里统一降级为“小字号位移绘制”，
#: 既保证化学式（Fe₂O₃）与同位素（²³⁸U）正确显示，也更符合印刷排版。
_SUB_MAP = {chr(0x2080 + i): str(i) for i in range(10)}
_SUB_MAP["\u208a"] = "+"
_SUB_MAP["\u208b"] = "-"
_SUB_MAP["\u208c"] = "="
_SUB_MAP["\u208d"] = "("
_SUB_MAP["\u208e"] = ")"
_SUP_MAP = {chr(0x2070 + i): str(i) for i in range(1, 10)}
_SUP_MAP[chr(0x2070)] = "0"
_SUP_MAP.update({"\u00b9": "1", "\u00b2": "2", "\u00b3": "3"})
_SUP_MAP["\u207a"] = "+"
_SUP_MAP["\u207b"] = "-"

SUB_SCALE = 0.66


def _runs(text: str):
    """把文本切成 (类型, 内容) 序列，类型为 n / sub / sup。"""
    out = []
    buf, kind = "", "n"
    for ch in text:
        k = "sub" if ch in _SUB_MAP else ("sup" if ch in _SUP_MAP else "n")
        v = _SUB_MAP.get(ch, _SUP_MAP.get(ch, ch))
        if k != kind:
            if buf:
                out.append((kind, buf))
            buf, kind = v, k
        else:
            buf += v
    if buf:
        out.append((kind, buf))
    return out


def text_width(text: str, size: float, bold: bool = False) -> float:
    fname = font_bold() if bold else font_regular()
    w = 0.0
    for k, seg in _runs(text):
        s = size * SUB_SCALE if k != "n" else size
        w += pdfmetrics.stringWidth(seg, fname, s)
    return w


def draw_text(c, x: float, y: float, text: str, size: float,
              bold: bool = False, fill=INK) -> float:
    """在 (x, y) 左对齐绘制一行富文本，返回占用宽度。"""
    fname = font_bold() if bold else font_regular()
    c.setFillColor(fill)
    cx = x
    for k, seg in _runs(text):
        if k == "n":
            s = size
            dy = 0.0
        else:
            s = size * SUB_SCALE
            dy = -size * 0.16 if k == "sub" else size * 0.40
        c.setFont(fname, s)
        c.drawString(cx, y + dy, seg)
        cx += pdfmetrics.stringWidth(seg, fname, s)
    return cx - x


def wrap(text: str, size: float, max_w: float, bold: bool = False) -> List[str]:
    """按字符宽度折行（中英文混排均可用）。"""
    lines: List[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if text_width(trial, size, bold) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _centered(c, x, y, text, size, bold=False, fill=INK):
    w = text_width(text, size, bold)
    draw_text(c, x - w / 2.0, y, text, size, bold, fill)


def _left(c, x, y, text, size, bold=False, fill=INK):
    draw_text(c, x, y, text, size, bold, fill)


def clip(c, x, y, w, h, text, size, bold=False, fill=INK):
    """在给定矩形内居中绘制一行文本，过长则按比例缩字号。"""
    s = size
    while s > 2.2 and text_width(text, s, bold) > w - 0.8 * mm:
        s -= 0.15
    tw = text_width(text, s, bold)
    draw_text(c, x + (w - tw) / 2.0, y, text, s, bold, fill)


# ---------------------------------------------------------------- 周期表首页
def _cell_fonts(cell_h: float) -> Tuple[float, float, float, float]:
    """依据单元格高度（mm）推导四级字号（pt）。"""
    num = cell_h * 0.115 / 0.3528
    sym = cell_h * 0.300 / 0.3528
    zhn = cell_h * 0.186 / 0.3528
    mass = cell_h * 0.112 / 0.3528
    return num, sym, zhn, mass


def draw_table_page(c, scheme: Scheme, W: float, H: float, with_legend: bool) -> None:
    reg, bold = font_regular(), font_bold()

    legend_h = (16 * mm) if with_legend else 0.0
    avail_w = W - 2 * MARGIN
    cell_w = (avail_w - LABEL_W) / 18.0

    y_top = H - MARGIN - TITLE_H
    legend_top = MARGIN + FOOTER_H + legend_h
    grid_bottom = legend_top + 3 * mm
    cell_h = (y_top - grid_bottom - HEADER_H - SPACER_H) / 9.0
    cell_h = min(cell_h, cell_w * 1.22)
    cell_h = max(cell_h, 8 * mm)

    # 内容比可用高度矮时（如 A4 纵向）整体垂直居中
    used = HEADER_H + 9 * cell_h + SPACER_H
    if used < y_top - grid_bottom:
        grid_bottom += (y_top - grid_bottom - used) / 2.0

    x0 = MARGIN + LABEL_W

    # ---------------- 标题 ----------------
    _left(c, MARGIN, y_top + TITLE_H * 0.50, "元素周期表", 16, bold=True, fill=ACCENT)
    tw = pdfmetrics.stringWidth("元素周期表", bold, 16)
    _left(c, MARGIN + tw + 4 * mm, y_top + TITLE_H * 0.50,
          "Periodic Table · 118 种元素", 9, fill=INK_SEC)
    _left(c, MARGIN, y_top + TITLE_H * 0.14,
          f"配色方案：{scheme.name}（{scheme.hint}）　生成日期：{date.today().isoformat()}",
          6.5, fill=INK_SEC)

    # 主表从 grid_bottom 往上排列：镧系/锕系 → 第7周期 … 第1周期 → 族号表头
    base = grid_bottom + SPACER_H + 2 * cell_h      # 镧系、锕系两行的顶
    hy = base + 7 * cell_h                          # 第 1 周期行的顶
    num_pt, sym_pt, zh_pt, mass_pt = _cell_fonts(cell_h / mm)

    # ---------------- 族号表头 ----------------
    for g in range(1, 19):
        x = x0 + (g - 1) * cell_w
        c.setFillColor(HEADER_BG)
        c.rect(x + GAP / 2, hy + GAP / 2, cell_w - GAP, HEADER_H - GAP, stroke=0, fill=1)
        clip(c, x, hy + HEADER_H * 0.30, cell_w, HEADER_H, str(g), 5.2, bold=True,
             fill=INK_SEC)

    # ---------------- 主表 ----------------
    def element_at(period: int, group: int) -> Optional[Element]:
        for e in BY_NUMBER.values():
            if e.period == period and e.group == group \
                    and e.category not in ("lanthanide", "actinide"):
                return e
        return None

    for p in range(1, 8):
        row_y = hy - p * cell_h
        x = MARGIN
        c.setFillColor(HEADER_BG)
        c.rect(x + GAP / 2, row_y + GAP / 2, LABEL_W - GAP, cell_h - GAP, stroke=0, fill=1)
        clip(c, x, row_y + cell_h * 0.34, LABEL_W, cell_h, str(p), 6, bold=True, fill=INK_SEC)

        for g in range(1, 19):
            x = x0 + (g - 1) * cell_w
            e = element_at(p, g)
            if e is None and p in (6, 7) and g == 3:
                _draw_placeholder(c, x, row_y, cell_w, cell_h,
                                  "57-71" if p == 6 else "89-103",
                                  "镧系" if p == 6 else "锕系")
            elif e is None:
                continue
            else:
                _draw_cell(c, e, x, row_y, cell_w, cell_h, scheme,
                           (num_pt, sym_pt, zh_pt, mass_pt))

    # ---------------- 镧系 / 锕系 ----------------
    for idx, (seq, title) in enumerate(((LANTHANIDES, "镧系"), (ACTINIDES, "锕系"))):
        row_y = base - (idx + 1) * cell_h
        c.setFillColor(HEADER_BG)
        c.rect(MARGIN + GAP / 2, row_y + GAP / 2, LABEL_W - GAP, cell_h - GAP,
               stroke=0, fill=1)
        clip(c, MARGIN, row_y + cell_h * 0.34, LABEL_W, cell_h, title, 5, bold=True,
             fill=INK_SEC)
        for i, e in enumerate(seq):
            col = 3 + i
            if col > 18:
                break
            x = x0 + (col - 1) * cell_w
            _draw_cell(c, e, x, row_y, cell_w, cell_h, scheme,
                       (num_pt, sym_pt, zh_pt, mass_pt))

    # ---------------- 图例 ----------------
    if with_legend:
        _draw_legend(c, scheme, MARGIN, legend_top, W - 2 * MARGIN)

    # ---------------- 页脚 ----------------
    _left(c, MARGIN, MARGIN * 0.55,
          "说明：单元格第一行为原子序数，第二行为元素符号，第三行为中文名，第四行为相对原子质量；"
          "人工合成元素的质量数加方括号表示最长寿命同位素。",
          6, fill=INK_SEC)
    c.setFont(reg, 6)
    c.setFillColor(INK_SEC)
    c.drawRightString(W - MARGIN, MARGIN * 0.55, "第 1 页")


def _draw_cell(c, e: Element, x: float, y: float, w: float, h: float,
               scheme: Scheme, fonts) -> None:
    bg = _hex2color(scheme.color(e))
    fg = _hex2color(scheme.text_color(e))
    num_pt, sym_pt, zh_pt, mass_pt = fonts

    c.setFillColor(bg)
    c.setStrokeColor(GRID)
    c.setLineWidth(0.35)
    c.rect(x + GAP / 2, y + GAP / 2, w - GAP, h - GAP, stroke=1, fill=1)

    name = zh(e)
    # 四行文字在单元格内自下而上排布
    mass_y = y + h * 0.10
    zh_y = y + h * 0.30
    sym_y = y + h * 0.48
    num_y = y + h * 0.76

    clip(c, x, mass_y, w, h, e.mass, mass_pt, fill=fg)
    clip(c, x, zh_y, w, h, name, zh_pt, fill=fg)
    clip(c, x, sym_y, w, h, e.symbol, sym_pt, bold=True, fill=fg)
    clip(c, x, num_y, w, h, str(e.number), num_pt, fill=fg)


def _draw_placeholder(c, x: float, y: float, w: float, h: float,
                      span: str, title: str) -> None:
    c.setFillColor(PLACE_BG)
    c.setStrokeColor(GRID)
    c.setLineWidth(0.35)
    c.rect(x + GAP / 2, y + GAP / 2, w - GAP, h - GAP, stroke=1, fill=1)
    clip(c, x, y + h * 0.52, w, h, span, 5.5, bold=True, fill=INK_SEC)
    clip(c, x, y + h * 0.20, w, h, title, 5.5, fill=INK_SEC)


def _draw_legend(c, scheme: Scheme, x: float, y_top: float, width: float) -> None:
    """y_top 为图例区顶部，内容自上而下排布。"""
    reg = font_regular()
    chips = scheme.legend
    sw = 3.6 * mm
    sh = 2.9 * mm
    pad = 1.2 * mm
    per_row = 10

    c.setFont(reg, 6.2)
    c.setFillColor(INK_SEC)
    c.drawString(x, y_top - 4 * mm, "图例")

    row0 = y_top - 4 * mm - 2.4 * mm - sh
    pitch = sh + 3.2 * mm
    for i, (label, color) in enumerate(chips):
        row, col = divmod(i, per_row)
        cx = x + col * (width / per_row)
        cy = row0 - row * pitch
        c.setFillColor(_hex2color(color))
        c.setStrokeColor(GRID)
        c.setLineWidth(0.3)
        c.rect(cx, cy, sw, sh, stroke=1, fill=1)
        c.setFillColor(INK_SEC)
        c.setFont(reg, 5.6)
        c.drawString(cx + sw + pad, cy + 0.9 * mm, label)


# ---------------------------------------------------------------- 元素详情页
def draw_detail_page(c, e: Element, scheme: Scheme, W: float, H: float,
                     page_no: int) -> None:
    reg, bold = font_regular(), font_bold()
    x = MARGIN
    width = W - 2 * MARGIN
    y = H - MARGIN

    bg = _hex2color(scheme.color(e))
    fg = _hex2color(scheme.text_color(e))

    # 顶部色条 + 元素名
    bar_h = 16 * mm
    c.setFillColor(bg)
    c.setStrokeColor(GRID)
    c.setLineWidth(0.4)
    c.rect(x, y - bar_h, width, bar_h, stroke=1, fill=1)
    c.setFillColor(fg)
    c.setFont(bold, 22)
    c.drawString(x + 4 * mm, y - bar_h * 0.62, e.symbol)
    c.setFont(bold, 13)
    c.drawString(x + 20 * mm, y - bar_h * 0.56,
                 f"{e.number} · {zh(e)}（{e.en}）")
    sub = [e.category_name]
    if e.group is not None:
        sub.append(e.group_label)
    sub += [f"第 {e.period} 周期", f"{e.block} 区"]
    draw_text(c, x + 20 * mm, y - bar_h * 0.86, " · ".join(sub), 7.5, False, fg)

    y = y - bar_h - 7 * mm

    def section(title: str) -> float:
        nonlocal y
        c.setFillColor(colors.HexColor("#eef3f9"))
        c.rect(x, y - 5.4 * mm, width, 5.0 * mm, stroke=0, fill=1)
        draw_text(c, x + 2 * mm, y - 3.9 * mm, title, 9, True, ACCENT)
        y -= 7.6 * mm
        return y

    def para(text: str, size: float = 8.2) -> None:
        nonlocal y
        for line in wrap(text, size, width - 4 * mm):
            if y < MARGIN + 10 * mm:
                break
            draw_text(c, x + 2 * mm, y, line, size, False, INK)
            y -= size * 1.45
        y -= 2.2 * mm

    def kv(k: str, v: str, size: float = 8.2) -> None:
        nonlocal y
        draw_text(c, x + 2 * mm, y, k + "：", size, True, INK_SEC)
        kw = text_width(k + "：", size, True)
        for i, line in enumerate(wrap(v, size, width - 4 * mm - kw)):
            draw_text(c, x + 2 * mm + (kw if i == 0 else 0), y, line, size, False, INK)
            y -= size * 1.45
        y -= 0.6 * mm

    section("基本参数")
    kv("相对原子质量", e.mass)
    kv("电子排布", e.config)
    kv("电负性（鲍林）", e.electroneg_text)
    kv("常温状态", e.phase)

    section("发现过程")
    kv("发现年代", e.era)
    kv("发现者 / 提出者", e.discoverer)
    para(e.story)

    section("丰度")
    kv("地壳丰度", e.crust_text)
    kv("宇宙丰度", e.cosmic_text)

    section("在自然界的主要存在形式")
    para(e.occurrence)

    section("主要化合物")
    para(e.compounds)

    section("在生产中的用途")
    para(e.uses)

    c.setFont(reg, 6)
    c.setFillColor(INK_SEC)
    c.drawString(MARGIN, MARGIN * 0.55, "元素周期表 · 元素详情")
    c.drawRightString(W - MARGIN, MARGIN * 0.55, f"第 {page_no} 页")


# ---------------------------------------------------------------- 对外接口
def build_default_path(scheme_name: str = "") -> str:
    _ensure()
    out_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(out_dir, exist_ok=True)
    tag = scheme_name.split("（")[0].strip() or "分类"
    return os.path.join(out_dir, f"元素周期表_{tag}.pdf")


def export_periodic_table_pdf(path: str,
                              scheme: Scheme,
                              paper: str = "A4 横向",
                              with_legend: bool = True,
                              detail_element: Optional[Element] = None,
                              all_details: bool = False) -> str:
    """导出着色周期表 PDF，返回实际文件路径。"""
    _ensure()
    if isinstance(scheme, str):          # 允许直接传配色方案的键名
        scheme = scheme_get(scheme)
    pagesize = PAPERS.get(paper, PAPERS["A4 横向"])()
    W, H = pagesize

    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)

    c = rl_canvas.Canvas(path, pagesize=pagesize)
    c.setTitle(f"元素周期表（{scheme.name}）")
    c.setAuthor("元素周期表程序")

    draw_table_page(c, scheme, W, H, with_legend)
    c.showPage()

    page_no = 2
    elements: List[Element] = []
    if all_details:
        elements = list(BY_NUMBER.values())
    elif detail_element is not None:
        elements = [detail_element]

    for e in elements:
        draw_detail_page(c, e, scheme, W, H, page_no)
        c.showPage()
        page_no += 1

    c.save()
    return path


if __name__ == "__main__":
    from color_schemes import SCHEMES
    _ensure()
    print("字体：", font_regular(), "/", font_bold())
    for s in SCHEMES[:3]:
        p = os.path.join(os.getcwd(), "output", f"_test_{s.key}.pdf")
        export_periodic_table_pdf(p, s, "A4 横向")
        print("导出：", p, os.path.getsize(p), "字节")
