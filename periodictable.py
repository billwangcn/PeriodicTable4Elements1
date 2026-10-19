# -*- coding: utf-8 -*-
"""元素周期表 · 程序入口。

用法：
  python periodictable.py                                   # 打开图形界面
  python periodictable.py --list-schemes                     # 查看所有配色方案
  python periodictable.py --export out.pdf --scheme group    # 直接导出 PDF（不打开界面）
  python periodictable.py --export out.pdf --details         # 导出并附 118 个元素详情页

模块分工：
  elements_data.py   118 个元素的全部数据（化合物/存在形式/用途/丰度/发现过程）
  color_schemes.py   8 套配色方案
  periodic_gui.py    Tkinter 界面
  pt_pdf.py          PDF 绘制
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="元素周期表 · 118 种元素 · 多配色方案 · PDF 导出",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", metavar="PATH",
                        help="不打开界面，直接把 PDF 周期表导出到该路径")
    parser.add_argument("--scheme", default="category",
                        help="配色方案键，默认 category（可用 --list-schemes 查看）")
    parser.add_argument("--paper", default="A4 横向",
                        choices=("A4 横向", "A3 横向", "A4 纵向"),
                        help="纸张版式，默认 A4 横向")
    parser.add_argument("--details", action="store_true",
                        help="附带全部 118 个元素的详情页")
    parser.add_argument("--element", metavar="符号或序数",
                        help="附带指定元素的详情页，例如 --element Fe 或 --element 26")
    parser.add_argument("--no-legend", action="store_true", help="不输出配色图例")
    parser.add_argument("--list-schemes", action="store_true", help="列出全部配色方案后退出")
    args = parser.parse_args()

    from color_schemes import BY_KEY, SCHEMES

    if args.list_schemes:
        print("可用的配色方案：")
        for s in SCHEMES:
            print(f"  {s.key:<11} {s.name:<16} {s.hint}")
        return 0

    if args.export:
        import pt_pdf
        scheme = BY_KEY.get(args.scheme)
        if scheme is None:
            print(f"未知的配色方案键：{args.scheme}", file=sys.stderr)
            print("可用键：" + "、".join(BY_KEY), file=sys.stderr)
            return 2

        element = None
        if args.element:
            from elements_data import BY_NUMBER, BY_SYMBOL
            key = args.element.strip()
            element = BY_SYMBOL.get(key.capitalize()) or (
                BY_NUMBER.get(int(key)) if key.isdigit() else None)
            if element is None:
                print(f"找不到元素：{args.element}", file=sys.stderr)
                return 2

        path = args.export
        if os.path.isdir(path):
            path = os.path.join(path, os.path.basename(pt_pdf.build_default_path(scheme.name)))

        out = pt_pdf.export_periodic_table_pdf(
            path=path, scheme=scheme, paper=args.paper,
            with_legend=not args.no_legend,
            detail_element=element, all_details=args.details)
        print(f"已导出：{out}")
        return 0

    try:
        from periodic_gui import main as gui_main
    except Exception as exc:  # noqa: BLE001
        print("无法启动图形界面：", exc, file=sys.stderr)
        print("提示：界面需要 tkinter，请使用 python.org 官方安装包（勾选 Tcl/Tk）。",
              file=sys.stderr)
        print("也可以直接用命令行导出 PDF：python periodictable.py --export out.pdf",
              file=sys.stderr)
        return 1
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
