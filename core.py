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
_OFFICIAL_MARKETS = [
    {
        "market": "sale",
        "name": "Outlet",
        "base_url": "https://outlet.arcteryx.com/",
        "queries": [
            ("men",   "mensjacketscoats"),
            ("men",   "mensmidlayersfleece"),
            ("men",   "mensshirtstops"),
            ("men",   "mensbaselay"),
            ("men",   "menslegwear"),
            ("men",   "menssoftshells"),
            ("women", "womensjacketscoats"),
            ("women", "womensmidlayersfleece"),
            ("women", "womensshirtstops"),
        ],
    },
    {
        "market": "outdoor",
        "name": "Official",
        "base_url": "https://arcteryx.com/",
        "queries": [
            ("men", ""),
            ("women", ""),
        ],
    },
]
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

def _pick_eur_price(p):
    return p.get("discountPrice") or p.get("minDiscountPrice") or p.get("price") or p.get("minPrice") or 0

def _normalize_product(p, gender, cat, market_cfg):
    sku = p.get("sku", "")
    price = _pick_eur_price(p)
    if not sku or not price:
        return None
    rel_url = p.get("url", "")
    return {
        "sku":          sku,
        "name":         p.get("name", ""),
        "eur_price":    float(price),
        "discount_pct": p.get("savingsPercentage", 0) or 0,
        "gender":       p.get("gender") or gender,
        "category":     cat or p.get("category") or p.get("collection") or market_cfg["market"],
        "url":          market_cfg["base_url"] + rel_url.lstrip("/"),
        "image":        (p.get("mainImage") or {}).get("url", ""),
        "price_type":   "eur",
        "source":       market_cfg["name"],
        "source_market": market_cfg["market"],
    }

def _fetch_arcteryx_market(market_cfg, headers):
    rows = []
    for gender, cat in market_cfg["queries"]:
        try:
            r = requests.get(_API, params={
                "market": market_cfg["market"], "language": "en", "country": "it",
                "gender": gender, "category": cat, "subCategory": "", "env": "prod",
            }, headers=headers, timeout=20, verify=False)
            data = r.json()
            if not isinstance(data, list):
                raise ValueError(data)
            for p in data:
                item = _normalize_product(p, gender, cat, market_cfg)
                if item:
                    rows.append(item)
            time.sleep(0.2)
        except Exception as e:
            label = f"{market_cfg['market']} {gender} {cat}".strip()
            print(f"  {label}: {e}")
    return rows

def fetch_arcteryx():
    H = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"}
    items, by_item = [], {}
    enabled = set(load_config().get("arcteryx_markets", ["sale", "outdoor"]))
    print("抓取始祖鸟 Outlet + 官网...")
    for market_cfg in _OFFICIAL_MARKETS:
        if market_cfg["market"] not in enabled:
            continue
        rows = _fetch_arcteryx_market(market_cfg, H)
        added = 0
        for item in rows:
            key = (item.get("source_market"), item.get("sku"), item.get("url"))
            old = by_item.get(key)
            # 只合并完全相同来源/货号/商品页的重复 feed 行。
            if old and old.get("eur_price", 0) <= item.get("eur_price", 0):
                continue
            by_item[key] = item
            added += 1
        print(f"  {market_cfg['name']}: {len(rows)} 条，新增/更新 {added} 条")
    items = list(by_item.values())
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
