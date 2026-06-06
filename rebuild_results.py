#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建利润结果
用法: python rebuild_results.py
"""

import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from core import load_json, save_json, fetch_arcteryx, calc_profit_eur

DB_FILE      = "mendao_db.json"
RESULTS_FILE = "results.json"

def main():
    db = load_json(DB_FILE, {})

    # 用articleNo建立查找映射
    article_map = {}
    for key, prod in db.items():
        article_map[key] = key
        article = prod.get('articleNo', '')
        if article and article != key:
            article_map[article] = key
    print(f'门道数据库: {len(db)} 件  映射: {len(article_map)} 条')

    items = fetch_arcteryx()

    matched, results = 0, []
    for item in items:
        sku    = item['sku']
        db_key = article_map.get(sku)
        prod   = db.get(db_key) if db_key else None

        if prod:
            matched += 1
            dw           = prod['minPrice']
            profit, rate = calc_profit_eur(item['eur_price'], dw)
            results.append({
                **item,
                'dewu_title':     prod['title'],
                'dewu_price':     dw,
                'dewu_min_price': dw,
                'image':          prod.get('image', '') or item.get('image', ''),
                'prices':         prod['prices'],
                'total_sold':     prod.get('total_sold', 0),
                'sourceSku':      prod.get('sourceSku', sku),
                'querySku':       prod.get('querySku', sku),
                'profit':         profit,
                'rate':           rate,
                'buy_display':    f"€{item['eur_price']:.0f}",
                'dp':             dw,
                'ep':             item['eur_price'],
                'has_dewu':       True,
            })
        else:
            results.append({
                **item,
                'dewu_price':     0,
                'dewu_min_price': 0,
                'dp':             0,
                'ep':             item['eur_price'],
                'has_dewu':       False,
                'profit':         None,
            })

    matched_r = sorted(
        [r for r in results if r.get('profit') is not None],
        key=lambda x: x['profit'], reverse=True
    )
    no_match = [r for r in results if r.get('profit') is None]

    print(f"\n{'='*65}")
    print(f"  利润排行（{len(results)}件 匹配{matched}件）")
    print(f"{'='*65}")
    if matched_r:
        print(f"{'货号':<20} {'欧元价':>7} {'门道价':>8} {'利润':>9} {'利润率':>7}  商品名")
        print('-' * 70)
        for r in matched_r[:20]:
            tag = '[+]' if r['profit'] > 0 else '[-]'
            print(f"{tag}{r['sku']:<19} €{r['eur_price']:<6.0f} "
                  f"¥{r['dewu_price']:<7.0f} ¥{r['profit']:>+8.0f} "
                  f"{r['rate']:>6.1f}%  {r['name'][:22]}")
    else:
        print('没有匹配的商品')
        print('需要继续用门道小程序抓取更多商品数据')

    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total':     len(results),
        'matched':   matched,
        'results':   matched_r + no_match,
    }
    save_json(RESULTS_FILE, output)
    print(f"\n💾 results.json 已更新")
    print(f"🌐 刷新浏览器查看")

    if no_match:
        print(f"\n还需抓取 {len(no_match)} 件商品的门道价格:")
        for r in no_match[:10]:
            print(f"  {r['sku']:<20} €{r['eur_price']:.0f}  {r['name'][:35]}")
        if len(no_match) > 10:
            print(f"  ... 还有 {len(no_match)-10} 件")

if __name__ == "__main__":
    main()
