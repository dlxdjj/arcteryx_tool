#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, time, requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_cfg = None

def load_config():
    global _cfg
    if _cfg is None:
        _cfg = load_json("config.json", {})
    return _cfg

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def calc_profit_eur(eur_price, dewu_price):
    cfg    = load_config()
    cost   = eur_price * cfg["eur_to_cny"] + cfg["weight_kg"] * cfg["freight_per_kg"]
    net    = dewu_price * (1 - cfg["dewu_pct"]) - cfg["dewu_fixed"] - cfg["domestic_freight"]
    profit = net - cost
    return round(profit), round(profit / cost * 100, 1) if cost else 0

def calc_profit_cny(buy_cny, dewu_price):
    cfg    = load_config()
    net    = dewu_price * (1 - cfg["dewu_pct"]) - cfg["dewu_fixed"] - cfg["domestic_freight"]
    profit = net - buy_cny
    return round(profit), round(profit / buy_cny * 100, 1) if buy_cny else 0

_API = "https://jh5e3sxgk0.execute-api.us-west-2.amazonaws.com/product-feed/products"
_CATS = [
    ("men",   "mensjacketscoats"),
    ("men",   "mensmidlayersfleece"),
    ("men",   "mensshirtstops"),
    ("men",   "mensbaselay"),
    ("men",   "menslegwear"),
    ("men",   "menssoftshells"),
    ("women", "womensjacketscoats"),
    ("women", "womensmidlayersfleece"),
    ("women", "womensshirtstops"),
]

def fetch_arcteryx():
    H = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
    items, seen = [], set()
    print("抓取始祖鸟奥特莱斯...")
    for gender, cat in _CATS:
        try:
            r = requests.get(_API, params={
                "market": "sale", "language": "en", "country": "it",
                "gender": gender, "category": cat, "subCategory": "", "env": "prod",
            }, headers=H, timeout=12, verify=False)
            for p in (r.json() if isinstance(r.json(), list) else []):
                sku = p.get("sku", "")
                if not sku or sku in seen:
                    continue
                sale = p.get("discountPrice") or p.get("minDiscountPrice", 0)
                if not sale:
                    continue
                seen.add(sku)
                items.append({
                    "sku":          sku,
                    "name":         p.get("name", ""),
                    "eur_price":    float(sale),
                    "discount_pct": p.get("savingsPercentage", 0),
                    "gender":       gender,
                    "category":     cat,
                    "url":          "https://outlet.arcteryx.com/" + p.get("url", ""),
                    "image":        (p.get("mainImage") or {}).get("url", ""),
                    "price_type":   "eur",
                })
            time.sleep(0.2)
        except Exception as e:
            print(f"  {cat}: {e}")
    print(f"找到 {len(items)} 件")
    return items

def parse_mendao_spu(j):
    try:
        if j.get('code') != 200:
            return None
        data    = j.get('data', {})
        title   = data.get('title', '')
        article = data.get('articleNo', '')
        spu_id  = str(data.get('spuId', ''))
        logo    = data.get('logo', '')
        if not spu_id and not article:
            return None
        prices = []
        for sku in data.get('skuDTOList', []):
            min_p    = sku.get('minPrice', 0)
            sale_cnt = sku.get('saleCnt', 0)
            color, size = '', ''
            for prop in sku.get('propertyDTOList', []):
                if prop.get('level') == 1:
                    color = prop.get('value', '')
                elif prop.get('level') == 2:
                    size = prop.get('value', '')
            prices.append({
                'skuId':   sku.get('skuId', ''),
                'color':   color,
                'size':    size,
                'price':   round(min_p / 100, 2) if min_p else 0,
                'inStock': min_p > 0,
                'saleCnt': sale_cnt,
            })
        in_stock   = [p for p in prices if p['inStock']]
        min_price  = round(min(p['price'] for p in in_stock), 2) if in_stock else 0
        total_sold = sum(p.get('saleCnt', 0) for p in prices)
        return {
            'spuId':      spu_id,
            'articleNo':  article,
            'title':      title,
            'image':      logo,
            'minPrice':   min_price,
            'total_sold': total_sold,
            'prices':     prices,
            'updatedAt':  time.strftime('%Y-%m-%d %H:%M:%S'),
        }
    except:
        return None

def read_fiddler(path="fiddler_latest.txt"):
    if not os.path.exists(path):
        return None
    try:
        if time.time() - os.path.getmtime(path) > 15:
            return None
        with open(path, encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except:
        return None
