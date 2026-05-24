#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动添加门道未录入货号的价格信息
对于门道没有的商品，手动输入得物/门道价格，参与利润计算

用法：python manual_add.py
"""

import json, os, time

DB_FILE      = "mendao_db.json"
MAP_FILE     = "sku_spu_map.json"
PRICES_FILE  = "dewu_prices.json"
MISSING_FILE = "missing_skus.json"

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, encoding='utf-8') as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def input_float(prompt, default=0):
    try:
        v = input(prompt).strip()
        return float(v) if v else default
    except: return default

def main():
    print("="*55)
    print("  手动添加货号价格工具")
    print("="*55)
    print()

    db      = load_json(DB_FILE, {})
    sku_map = load_json(MAP_FILE, {})
    missing = load_json(MISSING_FILE, [])

    print("选择操作：")
    print("  [1] 逐个处理门道未录入的货号")
    print("  [2] 手动添加单个货号")
    print("  [3] 查看已手动添加的货号")
    print("  [4] 退出")
    choice = input("\n请选择: ").strip()

    if choice == '1':
        if not missing:
            print("没有未录入的货号记录")
            print("运行 auto_click_mendao.py 后会自动生成 missing_skus.json")
            return

        print(f"\n共 {len(missing)} 个货号在门道未找到")
        print("对每个货号，你可以：")
        print("  - 输入得物/门道价格（手动查询后填入）")
        print("  - 直接回车跳过")
        print("  - 输入 q 退出")
        print()

        done = []
        for i, sku in enumerate(missing, 1):
            print(f"\n[{i}/{len(missing)}] 货号: {sku}")
            print(f"  已在数据库: {'是' if sku in db else '否'}")

            ans = input("  是否手动添加价格？(y/回车跳过/q退出): ").strip().lower()
            if ans == 'q': break
            if ans != 'y': continue

            title = input(f"  商品名称（可简写）: ").strip()
            price = input_float("  门道/得物最低价（元，如 299）: ")

            if price <= 0:
                print("  价格无效，跳过")
                continue

            # 手动输入尺码价格
            print("  输入各尺码价格（回车跳过该尺码，输入空行结束）：")
            prices = []
            while True:
                size_input = input("    尺码（如 S/M/L，空行结束）: ").strip()
                if not size_input: break
                size_price = input_float(f"    {size_input} 的价格（元）: ", price)
                prices.append({
                    'skuId':   0,
                    'color':   '',
                    'size':    size_input,
                    'price':   size_price,
                    'inStock': size_price > 0,
                    'saleCnt': 0,
                    'manual':  True,
                })

            if not prices:
                # 没有输入尺码，只记录最低价
                prices = [{
                    'skuId':   0, 'color': '', 'size': '均码',
                    'price':   price, 'inStock': True,
                    'saleCnt': 0, 'manual': True,
                }]

            product = {
                'spuId':     '',
                'articleNo': sku,
                'title':     title or f'手动添加-{sku}',
                'image':     '',
                'minPrice':  price,
                'prices':    prices,
                'manual':    True,
                'updatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
            }

            db[sku]      = product
            sku_map[sku] = sku
            save_json(DB_FILE, db)
            save_json(MAP_FILE, sku_map)
            save_json(PRICES_FILE, list(db.values()))
            done.append(sku)
            print(f"  ✅ 已保存 {sku} → ¥{price:.0f}")

        # 从missing列表移除已处理的
        remaining = [s for s in missing if s not in done]
        save_json(MISSING_FILE, remaining)
        print(f"\n完成！手动添加 {len(done)} 个，剩余 {len(remaining)} 个未处理")

    elif choice == '2':
        sku = input("\n输入货号: ").strip().upper()
        if not sku: return

        title  = input("商品名称: ").strip()
        price  = input_float("最低价（元）: ")
        if price <= 0: print("价格无效"); return

        print("输入各尺码价格（空行结束）：")
        prices = []
        while True:
            size_input = input("  尺码（空行结束）: ").strip()
            if not size_input: break
            sp = input_float(f"  {size_input} 价格: ", price)
            prices.append({'skuId':0,'color':'','size':size_input,'price':sp,'inStock':sp>0,'saleCnt':0,'manual':True})

        if not prices:
            prices = [{'skuId':0,'color':'','size':'均码','price':price,'inStock':True,'saleCnt':0,'manual':True}]

        product = {
            'spuId':'','articleNo':sku,'title':title or f'手动添加-{sku}',
            'image':'','minPrice':price,'prices':prices,
            'manual':True,'updatedAt':time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        db[sku] = product
        sku_map[sku] = sku
        save_json(DB_FILE, db)
        save_json(MAP_FILE, sku_map)
        save_json(PRICES_FILE, list(db.values()))
        print(f"✅ 已保存 {sku}")

    elif choice == '3':
        manual = {k:v for k,v in db.items() if v.get('manual')}
        print(f"\n手动添加的货号共 {len(manual)} 个：")
        for sku, prod in manual.items():
            print(f"  {sku:<20} ¥{prod['minPrice']:.0f}  {prod['title'][:30]}")

if __name__ == "__main__":
    main()
