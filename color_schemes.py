# -*- coding: utf-8 -*-
"""周期表配色方案。

提供两套类型：
  - 离散型（discrete）：按类别/族/周期/区块/状态取色，图例为一组色块
  - 渐变型（gradient）：按地壳丰度 / 电负性 / 发现年代着色，图例为色带分段

每个方案统一暴露：
  color(element)      -> 背景色（十六进制）
  text_color(element) -> 叠在该背景上的可读文字色
  legend              -> [(标签, 颜色)] 用于界面与 PDF 图例
"""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from elements_data import (
    CAT_ACTINIDE,
    CAT_ALKALI,
    CAT_ALKALINE,
    CAT_HALOGEN,
    CAT_LANTHANIDE,
    CAT_METALLOID,
    CAT_NONMETAL,
    CAT_NOBLE,
    CAT_POST,
    CAT_TRANSITION,
    CAT_UNKNOWN,
    CATEGORY_NAMES,
    Element,
)

# ---------------------------------------------------------------- 常量
TEXT_DARK = "#1e2a35"
TEXT_LIGHT = "#ffffff"
NO_DATA_BG = "#eef1f5"          # 无数据（如人工元素的地壳丰度）
NO_DATA_TEXT = "#7b8794"


def hsl_hex(h: float, s: float, l: float) -> str:
    """h(0~360) s(0~1) l(0~1) -> #rrggbb"""
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _hex2rgb(hex_color: str) -> Tuple[int, int, int]:
    c = hex_color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def luminance(hex_color: str) -> float:
    """感知亮度（0~1），用于决定叠加深色字还是浅色字。"""
    r, g, b = _hex2rgb(hex_color)

    def ch(v: int) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def readable_text(bg: str) -> str:
    return TEXT_LIGHT if luminance(bg) < 0.42 else TEXT_DARK


def mix(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex2rgb(c1)
    r2, g2, b2 = _hex2rgb(c2)
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % (round(r1 + (r2 - r1) * t),
                              round(g1 + (g2 - g1) * t),
                              round(b1 + (b2 - b1) * t))


def ramp(stops: List[str], t: float) -> str:
    """在多段色标上按 t(0~1) 插值。"""
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    pos = t * n
    i = min(int(pos), n - 1)
    return mix(stops[i], stops[i + 1], pos - i)


# ---------------------------------------------------------------- 调色板
CATEGORY_PALETTE = {
    CAT_ALKALI: "#f9b49c",
    CAT_ALKALINE: "#f8d497",
    CAT_TRANSITION: "#a9c7ea",
    CAT_POST: "#9ad6bb",
    CAT_METALLOID: "#c6dd97",
    CAT_NONMETAL: "#8ae2d2",
    CAT_HALOGEN: "#f0a8d6",
    CAT_NOBLE: "#c2aef2",
    CAT_LANTHANIDE: "#f3b0c6",
    CAT_ACTINIDE: "#e89c9c",
    CAT_UNKNOWN: "#cbd2da",
}

BLOCK_PALETTE = {
    "s": "#fbb5a4",
    "p": "#add8f7",
    "d": "#b3e3c3",
    "f": "#e6c6f3",
}

PHASE_PALETTE = {
    "固": "#bcd6ea",
    "液": "#7fc9dc",
    "气": "#f5c98c",
    "未知": "#d5dae1",
}

PERIOD_PALETTE = ["#d5e6f8", "#bfd8f2", "#a8c9eb", "#90bae3",
                  "#79aadb", "#6199d3", "#4a88cb"]

# 族（18 列）配色：色相均匀铺满色轮，明度高以保证深色字可读
GROUP_PALETTE = [hsl_hex((g - 1) * 20.0, 0.52, 0.78) for g in range(1, 19)]

ABUNDANCE_RAMP = ["#fff6e0", "#ffe08a", "#fcb45c", "#f2803f", "#d64a2e", "#8f2318"]
ELECTRONEG_RAMP = ["#e7f1fb", "#a9d3ef", "#74c7c2", "#f2d06b", "#ea9a3e", "#c0392b"]
YEAR_RAMP = ["#5c3f75", "#8d6bab", "#b79ed0", "#e3c38f", "#8ec9a3", "#57a3c9"]


# ---------------------------------------------------------------- 方案定义
@dataclass
class Scheme:
    key: str
    name: str
    hint: str
    kind: str                                   # discrete | gradient
    legend: List[Tuple[str, str]] = field(default_factory=list)
    _fn: Optional[Callable[[Element], Optional[str]]] = None

    def color(self, e: Element) -> str:
        if self._fn is None:
            return NO_DATA_BG
        c = self._fn(e)
        return NO_DATA_BG if c is None else c

    def text_color(self, e: Element) -> str:
        c = self.color(e)
        if c == NO_DATA_BG:
            return NO_DATA_TEXT
        return readable_text(c)


def _category_color(e: Element) -> str:
    return CATEGORY_PALETTE.get(e.category, NO_DATA_BG)


def _group_color(e: Element) -> Optional[str]:
    if e.group is None:
        return CATEGORY_PALETTE.get(e.category, NO_DATA_BG)
    return GROUP_PALETTE[e.group - 1]


def _period_color(e: Element) -> str:
    return PERIOD_PALETTE[e.period - 1]


def _block_color(e: Element) -> str:
    return BLOCK_PALETTE.get(e.block, NO_DATA_BG)


def _phase_color(e: Element) -> str:
    return PHASE_PALETTE.get(e.phase, NO_DATA_BG)


def _abundance_color(e: Element) -> Optional[str]:
    if e.crust is None or e.crust <= 0:
        return None
    lo, hi = -5.5, 5.7          # log10(ppm)
    v = max(lo, min(hi, math.log10(e.crust)))
    return ramp(ABUNDANCE_RAMP, (v - lo) / (hi - lo))


def _electroneg_color(e: Element) -> Optional[str]:
    if e.electroneg is None:
        return None
    lo, hi = 0.7, 4.0
    v = max(lo, min(hi, e.electroneg))
    return ramp(ELECTRONEG_RAMP, (v - lo) / (hi - lo))


def _year_color(e: Element) -> Optional[str]:
    if e.year is None:
        return ramp(YEAR_RAMP, 0.0)          # 史前已知
    lo, hi = 1250.0, 2010.0
    v = max(lo, min(hi, float(e.year)))
    return ramp(YEAR_RAMP, (v - lo) / (hi - lo))


def _abundance_legend() -> List[Tuple[str, str]]:
    labels = ["< 0.001 ppm", "0.001~0.1", "0.1~10", "10~1000", "1千~10万", "> 10万 ppm"]
    return [(labels[i], ramp(ABUNDANCE_RAMP, i / (len(labels) - 1)))
            for i in range(len(labels))]


def _electroneg_legend() -> List[Tuple[str, str]]:
    labels = ["< 1.0", "1.0~1.6", "1.6~2.0", "2.0~2.5", "2.5~3.0", "> 3.0"]
    return [(labels[i], ramp(ELECTRONEG_RAMP, i / (len(labels) - 1)))
            for i in range(len(labels))]


def _year_legend() -> List[Tuple[str, str]]:
    labels = ["史前/古代", "~1700", "~1800", "~1900", "~1950", "1950 年后"]
    return [(labels[i], ramp(YEAR_RAMP, i / (len(labels) - 1)))
            for i in range(len(labels))]


def _category_legend() -> List[Tuple[str, str]]:
    order = [CAT_ALKALI, CAT_ALKALINE, CAT_TRANSITION, CAT_POST, CAT_METALLOID,
             CAT_NONMETAL, CAT_HALOGEN, CAT_NOBLE, CAT_LANTHANIDE, CAT_ACTINIDE,
             CAT_UNKNOWN]
    return [(CATEGORY_NAMES[k], CATEGORY_PALETTE[k]) for k in order]


def _group_legend() -> List[Tuple[str, str]]:
    items = [(f"第 {g} 族", GROUP_PALETTE[g - 1]) for g in range(1, 19)]
    # 镧系/锕系不属于 1~18 族中的任何一列，单独说明
    items.append(("镧系（无族号）", CATEGORY_PALETTE[CAT_LANTHANIDE]))
    items.append(("锕系（无族号）", CATEGORY_PALETTE[CAT_ACTINIDE]))
    return items


def _period_legend() -> List[Tuple[str, str]]:
    return [(f"第 {p} 周期", PERIOD_PALETTE[p - 1]) for p in range(1, 8)]


def _block_legend() -> List[Tuple[str, str]]:
    names = {"s": "s 区（碱金属/碱土）", "p": "p 区（主族）",
             "d": "d 区（过渡金属）", "f": "f 区（镧系/锕系）"}
    return [(names[k], BLOCK_PALETTE[k]) for k in ("s", "p", "d", "f")]


def _phase_legend() -> List[Tuple[str, str]]:
    return [(k, PHASE_PALETTE[k]) for k in ("固", "液", "气", "未知")]


def build_schemes() -> List[Scheme]:
    return [
        Scheme("category", "元素族别（分类）", "按碱金属、卤素、稀有气体等族别着色",
               "discrete", _category_legend(), _category_color),
        Scheme("group", "按族（18 列）", "周期表每一纵列一种颜色",
               "discrete", _group_legend(), _group_color),
        Scheme("period", "按周期（7 行）", "周期表每一横行一种颜色",
               "discrete", _period_legend(), _period_color),
        Scheme("block", "电子区块 s/p/d/f", "按价电子所在轨道区块着色",
               "discrete", _block_legend(), _block_color),
        Scheme("phase", "常温状态", "按常温常压下的固/液/气态着色",
               "discrete", _phase_legend(), _phase_color),
        Scheme("abundance", "地壳丰度（对数）", "含量越高颜色越深，人工元素为无数据",
               "gradient", _abundance_legend(), _abundance_color),
        Scheme("electroneg", "电负性", "鲍林标度，越大越强（吸电子能力）",
               "gradient", _electroneg_legend(), _electroneg_color),
        Scheme("year", "发现年代", "越晚被发现颜色越冷（人工合成元素最冷）",
               "gradient", _year_legend(), _year_color),
    ]


SCHEMES: List[Scheme] = build_schemes()
DEFAULT_SCHEME = SCHEMES[0]
BY_KEY = {s.key: s for s in SCHEMES}


def get(key: str) -> Scheme:
    return BY_KEY.get(key, DEFAULT_SCHEME)


if __name__ == "__main__":
    from elements_data import BY_SYMBOL
    for s in SCHEMES:
        print(f"{s.key:<10} {s.name:<14} {s.kind:<9} 图例 {len(s.legend)} 项")
    for sym in ("H", "Fe", "Au", "U", "Og"):
        e = BY_SYMBOL[sym]
        c = DEFAULT_SCHEME.color(e)
        print(f"  {sym:<3} {c} 字色 {DEFAULT_SCHEME.text_color(e)}")
