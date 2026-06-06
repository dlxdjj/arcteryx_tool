#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch Arc'teryx product-page variant stock and annotate results.json.

The product feed only proves that a style exists in Outlet. Product pages expose
colour/size variants with stockStatus, which is what we need for SKU-level
comparison against Mendao colour/size rows.
"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
import urllib3

from core import load_config, load_json, save_json, calc_profit_eur, calc_profit_cny

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RESULTS_FILE = "results.json"
STOCK_FILE = "arcteryx_stock.json"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
IN_STOCK = {"InStock", "LowStock", "LimitedAvailability"}
NEXT_BUILD_ID = "iosQdR_ZeBJ6HtVyCDanv"


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


COLOR_CN = {
    "黑": "black",
    "黑色": "black",
    "白": "white",
    "白色": "white",
    "蓝": "blue",
    "蓝色": "blue",
    "深蓝": "blue",
    "紫": "purple",
    "紫色": "purple",
    "灰": "grey",
    "灰色": "grey",
    "绿": "green",
    "绿色": "green",
    "红": "red",
    "红色": "red",
    "粉": "pink",
    "粉色": "pink",
    "棕": "brown",
    "棕色": "brown",
    "米": "beige",
    "米色": "beige",
    "橙": "orange",
    "橙色": "orange",
    "黄": "yellow",
    "黄色": "yellow",
}
COLOR_ALIASES = {
    "blk": "black",
    "bk": "black",
    "gry": "grey",
    "gray": "grey",
    "dk": "dark",
    "lt": "light",
}


def translate_color_part(part):
    text = re.sub(r"\s+", "", str(part or ""))
    return COLOR_CN.get(text, "")


def color_tokens(value):
    tokens = set()
    for part in re.split(r"[/,|]+", str(value or "")):
        n = norm(part)
        if n:
            tokens.add(COLOR_ALIASES.get(n, n))
        t = translate_color_part(part)
        if t:
            tokens.add(t)
    return tokens


def color_parts(value):
    parts = []
    for part in re.split(r"[/,|]+", str(value or "")):
        n = norm(part) or translate_color_part(part)
        if n:
            parts.append(COLOR_ALIASES.get(n, n))
    return parts


def norm_size(value):
    raw = str(value or "").lower()
    raw = raw.replace("⅓", " third ").replace("⅔", " twothird ").replace("½", " half ")
    raw = re.sub(r"\b1\s*/\s*3\b", " third ", raw)
    raw = re.sub(r"\b2\s*/\s*3\b", " twothird ", raw)
    raw = re.sub(r"\b1\s*/\s*2\b", " half ", raw)
    raw = re.sub(r"[-\s_/]*(short|regular|reg|long)$", "", raw)
    raw = re.sub(r"[-\s_/]+[srl]$", "", raw)
    s = norm(raw)
    s = re.sub(r"(short|regular|reg|long)$", "", s)
    s = re.sub(r"(s|r|l)$", "", s) if re.match(r"^\d+(s|r|l)$", s) else s
    aliases = {
        "2xl": "xxl",
        "xxl": "xxl",
        "2x": "xxl",
        "3xl": "xxxl",
        "xxxl": "xxxl",
        "3x": "xxxl",
        "4xl": "xxxxl",
        "xxxxl": "xxxxl",
        "4x": "xxxxl",
    }
    return aliases.get(s, s)


def color_matches(mendao_color, official_color):
    m_full = norm(mendao_color)
    o_full = norm(official_color)
    m_parts = color_tokens(mendao_color)
    o_parts = color_tokens(official_color)
    m_order = color_parts(mendao_color)
    o_order = color_parts(official_color)
    if not o_full or not (m_full or m_parts):
        return False
    if m_full and (o_full == m_full or o_full in m_full or m_full in o_full):
        return True
    if o_full in m_parts or (m_full and m_full in o_parts):
        return True
    if m_order and o_order and m_order[0] == o_order[0]:
        return True
    # Black/Black, Blue/Blue etc. can match a single generic colour.
    if m_order and o_order and len(set(o_order)) == 1 and m_order[0] in set(o_order):
        return True
    if len(m_order) > 1 and o_order and o_order[0] in set(m_order):
        return True
    if len(o_order) == 1 and m_parts and o_order[0] in m_parts:
        return True
    return False


def size_matches(mendao_size, official_size):
    return norm_size(mendao_size) == norm_size(official_size)


def extract_next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m:
        return None
    return json.loads(m.group(1))


def next_data_url(url):
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    host = f"{parts.scheme}://{parts.netloc}"
    return f"{host}/catalog-pages/_next/data/{NEXT_BUILD_ID}{path}.json"


def load_product_payload(url):
    data_url = next_data_url(url)
    r = requests.get(data_url, headers={**UA, "Accept": "application/json"}, timeout=30, verify=False)
    if r.status_code == 200:
        data = r.json()
        product = data.get("pageProps", {}).get("product")
        if product:
            return json.loads(product)

    r = requests.get(url, headers=UA, timeout=30, verify=False)
    if r.status_code == 429:
        time.sleep(float(load_config().get("official_stock_429_delay", 20.0)))
        r = requests.get(url, headers=UA, timeout=30, verify=False)
    r.raise_for_status()
    data = extract_next_data(r.text)
    if not data:
        raise ValueError("missing __NEXT_DATA__")
    return json.loads(data["props"]["pageProps"]["product"])


def stock_cache_key(item):
    return "|".join([
        str(item.get("sku") or ""),
        str(item.get("source_market") or item.get("source") or ""),
        str(item.get("url") or ""),
    ])


def fetch_official_stock(item):
    url = item.get("url")
    sku = item.get("sku")
    if not url:
        return None

    product = load_product_payload(url)

    colour_map = {
        str(c.get("id")): c.get("label") or c.get("heroImage", {}).get("image", {}).get("alt") or ""
        for c in product.get("colourOptions", [])
    }
    size_map = {
        str(s.get("value")): s.get("label") or ""
        for s in product.get("sizeOptions", {}).get("options", [])
    }

    variants = []
    for v in product.get("variants", []):
        colour = colour_map.get(str(v.get("colourId")), "")
        size = size_map.get(str(v.get("sizeId")), "")
        status = v.get("stockStatus") or ""
        variants.append({
            "variantId": v.get("id"),
            "colour": colour,
            "size": size,
            "stockStatus": status,
            "officialInStock": status in IN_STOCK,
            "price": v.get("price"),
            "discountPrice": v.get("discountPrice"),
        })

    return {
        "sku": sku,
        "url": url,
        "name": product.get("name") or item.get("name"),
        "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "variants": variants,
    }


def annotate_price(price_row, stock):
    variants = (stock or {}).get("variants", [])
    candidates = [
        v for v in variants
        if size_matches(price_row.get("size"), v.get("size"))
        and color_matches(price_row.get("color"), v.get("colour"))
    ]
    in_stock = [v for v in candidates if v.get("officialInStock")]
    match = in_stock[0] if in_stock else (candidates[0] if candidates else None)
    row = dict(price_row)
    row["officialMatched"] = bool(match)
    row["officialInStock"] = bool(match and match.get("officialInStock"))
    row["officialColor"] = match.get("colour") if match else ""
    row["officialSize"] = match.get("size") if match else ""
    row["officialStockStatus"] = match.get("stockStatus") if match else ""
    row["officialVariantId"] = match.get("variantId") if match else ""
    return row


def recalc_result(result, eligible_prices):
    if not eligible_prices:
        result["official_has_buyable_sku"] = False
        result["official_buyable_count"] = 0
        result["official_mendao_min_price"] = 0
        result["best_official_mendao_sku"] = None
        result["profit"] = None
        result["rate"] = None
        return result

    best = min(eligible_prices, key=lambda p: p.get("price") or 10**12)
    dw = best["price"]
    result["official_has_buyable_sku"] = True
    result["official_buyable_count"] = len(eligible_prices)
    result["official_mendao_min_price"] = dw
    result["dewu_price"] = dw
    result["dewu_min_price"] = dw
    result["best_official_mendao_sku"] = {
        "skuId": best.get("skuId"),
        "color": best.get("color"),
        "size": best.get("size"),
        "price": best.get("price"),
        "saleCnt": best.get("saleCnt", 0),
        "officialColor": best.get("officialColor"),
        "officialSize": best.get("officialSize"),
    }

    if result.get("price_type") == "eur" and result.get("eur_price", 0) > 0:
        profit, rate = calc_profit_eur(result["eur_price"], dw)
        result["profit"] = profit
        result["rate"] = rate
    elif result.get("price", 0) > 0:
        profit, rate = calc_profit_cny(result["price"], dw)
        result["profit"] = profit
        result["rate"] = rate
    return result


def main():
    data = load_json(RESULTS_FILE, {})
    results = data.get("results", [])
    cache = load_json(STOCK_FILE, {})
    cfg = load_config()
    delay = float(cfg.get("official_stock_delay", 2.0))
    enabled_markets = set(cfg.get("official_stock_markets", ["sale"]))
    consecutive_429 = 0
    print(f"official stock enrich: {len(results)} product pages, delay {delay}s")
    print(f"official stock markets: {', '.join(sorted(enabled_markets))}")

    for i, item in enumerate(results, 1):
        sku = item.get("sku")
        if not sku or not item.get("url"):
            continue
        key = stock_cache_key(item)
        market = item.get("source_market") or ""
        cached = cache.get(key)
        if not cached:
            legacy = cache.get(sku)
            if legacy and legacy.get("url") == item.get("url"):
                cached = legacy
        if not cached and market not in enabled_markets:
            cached = {
                "sku": sku,
                "url": item.get("url"),
                "error": f"skipped_by_config: source_market={market}",
                "variants": [],
            }
            cache[key] = cached
            save_json(STOCK_FILE, cache)
            print(f"[{i}/{len(results)}] skip official stock {sku} {item.get('source', '')}")
        if not cached:
            print(f"[{i}/{len(results)}] fetch official stock {sku} {item.get('source', '')}")
            try:
                cached = fetch_official_stock(item)
                cache[key] = cached
                save_json(STOCK_FILE, cache)
                consecutive_429 = 0
                time.sleep(delay)
            except Exception as e:
                print(f"  failed: {e}")
                cache[key] = {"sku": sku, "url": item.get("url"), "error": str(e), "variants": []}
                cached = cache[key]
                if "429" in str(e):
                    consecutive_429 += 1
                    if consecutive_429 >= 3:
                        print("  too many 429 responses; stop now and retry later")
                        break
                else:
                    consecutive_429 = 0

        prices = [annotate_price(p, cached) for p in item.get("prices", [])]
        item["prices"] = prices
        item["officialStock"] = {
            "updatedAt": cached.get("updatedAt", ""),
            "variantCount": len(cached.get("variants", [])),
            "inStockCount": len([v for v in cached.get("variants", []) if v.get("officialInStock")]),
            "error": cached.get("error", ""),
        }
        eligible = [p for p in prices if p.get("inStock") and p.get("officialInStock")]
        recalc_result(item, eligible)

    matched = len([r for r in results if r.get("profit") is not None])
    matched_r = sorted(
        [r for r in results if r.get("profit") is not None],
        key=lambda x: x["profit"],
        reverse=True,
    )
    no_match = [r for r in results if r.get("profit") is None]
    data["matched"] = matched
    data["results"] = matched_r + no_match
    data["official_stock_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json(RESULTS_FILE, data)
    print(f"official stock enriched: {matched} buyable results / {len(results)} total")


if __name__ == "__main__":
    main()
