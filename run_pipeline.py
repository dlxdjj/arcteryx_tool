#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-command pipeline for the Arc'teryx x Mendao comparison workflow."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import auto_click_mendao as mendao
import official_stock_enrich
import product_match_audit
from core import fetch_arcteryx


BASE_DIR = Path(__file__).resolve().parent


def configure_console() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def unique_uncached_items(items: list[dict]) -> list[dict]:
    sku_map = mendao.load_json(mendao.MAP_FILE, {})
    seen = set()
    todo = []
    for item in items:
        sku = item.get("sku")
        if not sku or sku in sku_map or sku in seen:
            continue
        seen.add(sku)
        todo.append(item)
    return todo


def countdown(seconds: int, message: str) -> None:
    if seconds <= 0:
        return
    print(message)
    for i in range(seconds, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    print(" " * 20, end="\r")


def run_mendao_ui(new_items: list[dict]) -> None:
    if not new_items:
        print("门道：没有新货号需要查询，使用已有缓存。")
        return

    positions = mendao.load_positions()
    if not positions:
        countdown(mendao.STARTUP_DELAY, "未找到坐标配置，请切到微信门道窗口，准备定位。")
        positions = mendao.locate_positions()

    countdown(
        mendao.STARTUP_DELAY,
        f"门道：即将查询 {len(new_items)} 个新货号，请保持微信门道小程序和 Fiddler 打开。",
    )
    mendao.pyautogui.PAUSE = 0.05
    mendao.pyautogui.FAILSAFE = True
    mendao.auto_browse(new_items, positions)


def open_dashboard_detached() -> None:
    subprocess.Popen(
        [sys.executable, str(BASE_DIR / "open_dashboard.py")],
        cwd=str(BASE_DIR),
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="自动抓取 Arc'teryx、补齐门道价格、补齐官网库存，并生成工作台结果。"
    )
    parser.add_argument(
        "--skip-mendao",
        action="store_true",
        help="不启动微信 UI 查询，只用已有 mendao_db/sku_spu_map 缓存生成结果。",
    )
    parser.add_argument(
        "--no-stock",
        action="store_true",
        help="跳过官网 SKU/库存补齐，只生成基础结果。",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="跳过匹配审计报告。",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="生成结果后不自动打开网页工作台。",
    )
    return parser.parse_args()


def main() -> int:
    configure_console()
    args = parse_args()

    print("=" * 60)
    print("Arc'teryx x 门道 一键生成流程")
    print("=" * 60)

    print("\n[1/5] 抓取 Arc'teryx Outlet + 官网商品...")
    items = fetch_arcteryx()
    if not items:
        print("未抓到商品，流程停止。")
        return 1

    new_items = unique_uncached_items(items)
    cached_count = len({i.get("sku") for i in items if i.get("sku")}) - len(new_items)
    print(f"商品行：{len(items)}，已缓存货号：{cached_count}，待查新货号：{len(new_items)}")

    print("\n[2/5] 补齐门道价格...")
    if args.skip_mendao:
        print("已选择 --skip-mendao，跳过微信 UI 查询。")
    else:
        run_mendao_ui(new_items)

    print("\n[3/5] 生成 results.json...")
    mendao.generate_results(items)

    if args.no_stock:
        print("\n[4/5] 已选择 --no-stock，跳过官网 SKU/库存补齐。")
    else:
        print("\n[4/5] 补齐官网 SKU/库存，并按官网有货 SKU 重算利润...")
        official_stock_enrich.main()

    if args.no_audit:
        print("\n[5/5] 已选择 --no-audit，跳过匹配审计。")
    else:
        print("\n[5/5] 生成匹配审计报告...")
        product_match_audit.main()

    if args.no_open:
        print("\n完成：结果已生成。运行 python open_dashboard.py 查看网页。")
    else:
        print("\n完成：正在打开网页工作台。")
        open_dashboard_detached()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
