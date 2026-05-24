#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
门道小程序 全自动查价 v2.0
功能：PyAutoGUI自动操作门道小程序搜索货号
      Fiddler自动保存spu-index响应，自动解析价格

Fiddler CustomRules.js 需要设置：
static function OnBeforeResponse(oSession: Session) {
    if (oSession.uriContains("spu-index")) {
        oSession.utilDecodeResponse();
        System.IO.File.WriteAllText(
            "C:\\Users\\linxx\\Desktop\\arcteryx_tool\\fiddler_latest.txt",
            oSession.GetResponseBodyAsString()
        );
    }
}
"""

import pyautogui, pyperclip
import time, os, sys, glob
from core import (load_config, load_json, save_json,
                  fetch_arcteryx, calc_profit_eur, calc_profit_cny,
                  parse_mendao_spu, read_fiddler)

FIDDLER_FILE   = "fiddler_latest.txt"
DB_FILE        = "mendao_db.json"
MAP_FILE       = "sku_spu_map.json"
PRICES_FILE    = "dewu_prices.json"
RESULTS_FILE   = "results.json"
POSITIONS_FILE = "dewu_positions.json"
MISSING_FILE   = "missing_skus.json"
STARTUP_DELAY  = 5

# ── 读取Excel ─────────────────────────────────────────────────
def read_excel(filepath):
    try:
        import openpyxl
    except ImportError:
        print("请安装: pip install openpyxl")
        return []
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header_idx = 0
    for i, row in enumerate(rows):
        if len([c for c in row if c is not None and str(c).strip()]) >= 2:
            header_idx = i
            break
    headers = [str(h or '').strip().lower() for h in rows[header_idx]]
    def fc(keys):
        for i, h in enumerate(headers):
            for k in keys:
                if k in h:
                    return i
        return -1
    sku_col   = fc(['货号', 'sku', '型号', '编号'])
    price_col = fc(['折后价', '成本', '进价', '购买价', '价格', '售价'])
    brand_col = fc(['品牌'])
    name_col  = fc(['货品名称', '商品名', '名称', '品名'])
    if sku_col < 0:
        print("❌ 找不到货号列")
        return []
    items = []
    for row in rows[header_idx + 1:]:
        if not any(c for c in row if c is not None):
            continue
        sku = str(row[sku_col] or '').strip() if sku_col < len(row) else ''
        if not sku or sku == 'None':
            continue
        price = 0
        if price_col >= 0 and price_col < len(row):
            try:
                price = float(row[price_col] or 0)
            except:
                pass
        brand = str(row[brand_col] or '').strip() if brand_col >= 0 and brand_col < len(row) else ''
        name  = str(row[name_col]  or '').strip() if name_col  >= 0 and name_col  < len(row) else ''
        items.append({"sku": sku, "brand": brand, "name": name, "price": price, "price_type": "cny"})
    print(f"读取 {len(items)} 件商品")
    return items

# ── 坐标管理 ──────────────────────────────────────────────────
def load_positions():
    return load_json(POSITIONS_FILE, None)

def locate_positions():
    positions = {}
    print("\n坐标定位（只需做一次）")
    elements = [
        ("search_box",   "门道小程序搜索框（点击可输入文字的地方）"),
        ("first_result", "搜索结果第一个商品（搜索框正下方）"),
        ("back_button",  "返回按钮（左上角<箭头）"),
    ]
    for key, desc in elements:
        print(f"\n  👉 把鼠标移到：{desc}")
        input(f"     移好后按回车...")
        x, y = pyautogui.position()
        positions[key] = (x, y)
        print(f"     ✅ ({x}, {y})")
    save_json(POSITIONS_FILE, positions)
    print("\n✅ 坐标已保存")
    return positions

def check_captcha():
    try:
        sc = pyautogui.screenshot()
        w, h = sc.size
        region = sc.crop((w // 4, h // 4, w * 3 // 4, h * 3 // 4))
        pixels = list(region.getdata())
        white = sum(1 for r, g, b in pixels if r > 230 and g > 230 and b > 230)
        if white / len(pixels) > 0.65:
            print(f"\n⚠️  检测到人机验证，请手动完成后按回车继续...")
            input()
            time.sleep(1)
    except:
        pass

# ── 核心自动化 ────────────────────────────────────────────────
def auto_browse(items, positions):
    cfg = load_config()
    sp  = tuple(positions["search_box"])
    rp  = tuple(positions["first_result"])
    bp  = tuple(positions["back_button"])

    db      = load_json(DB_FILE, {})
    sku_map = load_json(MAP_FILE, {})

    print(f"\n开始自动浏览 {len(items)} 个货号")
    print("鼠标移到屏幕左上角可紧急停止\n")

    if os.path.exists(FIDDLER_FILE):
        os.remove(FIDDLER_FILE)

    success = mapped = 0
    missing_skus = []

    for i, item in enumerate(items, 1):
        sku = item['sku']
        try:
            print(f"[{i}/{len(items)}] {sku}", end=' ', flush=True)

            pyautogui.click(sp[0], sp[1])
            time.sleep(0.5)
            pyperclip.copy(sku)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.3)
            pyautogui.press('enter')
            print("→搜索", end=' ', flush=True)
            time.sleep(cfg["delay_search"])
            check_captcha()

            pyautogui.click(rp[0], rp[1])
            print("→详情", end=' ', flush=True)
            time.sleep(cfg["delay_detail"])
            check_captcha()

            j = read_fiddler(FIDDLER_FILE)
            got_result = False
            if j:
                product = parse_mendao_spu(j)
                if product:
                    article          = product.get('articleNo') or sku
                    sku_map[sku]     = article
                    sku_map[article] = article
                    db[article]      = product
                    save_json(DB_FILE, db)
                    save_json(MAP_FILE, sku_map)
                    save_json(PRICES_FILE, list(db.values()))
                    mapped += 1
                    got_result = True
                    in_stock_cnt = len([p for p in product['prices'] if p['inStock']])
                    print(f"→✅ {article} ¥{product['minPrice']:.0f} ({in_stock_cnt}个尺码有货)")
                else:
                    print("→⚠️ 解析失败")
            else:
                missing_skus.append(sku)
                print("→❌ 门道无此货号（跳过）")

            if got_result:
                pyautogui.click(bp[0], bp[1])
                time.sleep(cfg["delay_back"])

            success += 1
            time.sleep(cfg["delay_between"])

        except pyautogui.FailSafeException:
            print(f"\n⚠️  紧急停止！")
            break
        except Exception as e:
            print(f"❌({e})")
            time.sleep(1)

    print(f"\n{'='*50}")
    print(f"完成！浏览:{success} 成功映射:{mapped} 门道无录入:{len(missing_skus)}")

    if missing_skus:
        existing = load_json(MISSING_FILE, [])
        save_json(MISSING_FILE, list(set(existing + missing_skus)))
        print(f"门道无录入货号已保存到 missing_skus.json ({len(missing_skus)} 个)")
        print("可运行 python manual_add.py 手动补录")

    return db, sku_map

# ── 生成对比结果 ──────────────────────────────────────────────
def generate_results(items):
    db      = load_json(DB_FILE, {})
    sku_map = load_json(MAP_FILE, {})

    results, matched = [], 0

    for item in items:
        sku    = item['sku']
        spu_id = str(sku_map.get(sku, ''))
        prod   = db.get(spu_id) if spu_id else None

        if prod:
            matched += 1
            dw = prod['minPrice']
            if item.get('price_type') == 'eur' and item.get('eur_price', 0) > 0:
                profit, rate = calc_profit_eur(item['eur_price'], dw)
                buy_display  = f"€{item['eur_price']:.0f}"
            elif item.get('price', 0) > 0:
                profit, rate = calc_profit_cny(item['price'], dw)
                buy_display  = f"¥{item['price']:.0f}"
            else:
                profit, rate, buy_display = 0, 0, '—'

            results.append({
                **item,
                "spuId":          spu_id,
                "dewu_title":     prod['title'],
                "dewu_price":     dw,
                "dewu_min_price": dw,
                "image":          prod.get('image', '') or item.get('image', ''),
                "prices":         prod['prices'],
                "profit":         profit,
                "rate":           rate,
                "buy_display":    buy_display,
                "has_dewu":       True,
            })
        else:
            results.append({**item, "has_dewu": False, "profit": None})

    matched_r = sorted(
        [r for r in results if r.get('profit') is not None],
        key=lambda x: x['profit'], reverse=True
    )
    no_match = [r for r in results if r.get('profit') is None]

    print(f"\n{'='*70}")
    print(f"  利润排行（{len(results)}件，匹配{matched}件）")
    print(f"{'='*70}")
    print(f"{'货号':<20} {'进价':>8} {'门道价':>8} {'利润':>9} {'利润率':>7}  商品名")
    print('-' * 72)
    for r in matched_r[:30]:
        tag = "✅" if r['profit'] > 0 else "❌"
        print(f"{tag}{r['sku']:<19} {r.get('buy_display', '—'):>8} "
              f"¥{r['dewu_price']:<7.0f} ¥{r['profit']:>+8.0f} "
              f"{r['rate']:>6.1f}%  {r.get('name', r.get('dewu_title', ''))[:22]}")

    import time as _t
    output = {
        "timestamp": _t.strftime('%Y-%m-%d %H:%M:%S'),
        "total":     len(results),
        "matched":   matched,
        "results":   matched_r + no_match,
    }
    save_json(RESULTS_FILE, output)
    print(f"\n💾 结果已保存 → results.json")
    print(f"🌐 运行 python open_dashboard.py 打开网页查看")

# ── 主程序 ────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  门道小程序 全自动查价工具 v2.0")
    print("=" * 55)
    print()

    xlsx_files = [f for f in glob.glob("*.xlsx") if not f.startswith('~$')]

    print("选择数据源：")
    print("  [1] 始祖鸟奥特莱斯（自动抓取）")
    for i, f in enumerate(xlsx_files, 2):
        print(f"  [{i}] Excel: {f}")
    print("  [0] 退出")
    print()
    choice = input("请选择: ").strip()

    if choice == '0':
        return
    elif choice == '1':
        items = fetch_arcteryx()
    elif choice.isdigit() and 2 <= int(choice) <= len(xlsx_files) + 1:
        items = read_excel(xlsx_files[int(choice) - 2])
    else:
        print("无效选择")
        return

    if not items:
        return

    sku_map   = load_json(MAP_FILE, {})
    new_items = [i for i in items if i['sku'] not in sku_map]
    cached    = [i for i in items if i['sku'] in sku_map]
    print(f"\n已缓存: {len(cached)} 件  需查询: {len(new_items)} 件")

    print()
    print("选择操作：")
    print("  [1] 自动浏览查价（需要微信+门道+Fiddler）")
    print("  [2] 仅用缓存数据生成结果")
    print("  [3] 重新定位坐标")
    print("  [4] 退出")
    op = input("\n请选择: ").strip()

    if op == '1':
        positions = load_positions()
        if not positions:
            print(f"\n{STARTUP_DELAY}秒后定位坐标，请切换到微信窗口...")
            for i in range(STARTUP_DELAY, 0, -1):
                print(f"  {i}...", end='\r')
                time.sleep(1)
            positions = locate_positions()

        if new_items:
            print(f"\n{STARTUP_DELAY}秒后开始，请切换到微信/门道小程序！")
            for i in range(STARTUP_DELAY, 0, -1):
                print(f"  {i}...", end='\r')
                time.sleep(1)
            print()
            pyautogui.PAUSE    = 0.05
            pyautogui.FAILSAFE = True
            auto_browse(new_items, positions)

    elif op == '3':
        print(f"\n{STARTUP_DELAY}秒后定位坐标...")
        for i in range(STARTUP_DELAY, 0, -1):
            print(f"  {i}...", end='\r')
            time.sleep(1)
        locate_positions()
        return
    elif op == '4':
        return

    generate_results(items)

if __name__ == "__main__":
    main()
