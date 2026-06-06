#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit official stock vs Mendao colour/size matching."""

from __future__ import annotations

import json
from collections import Counter

from official_stock_enrich import STOCK_FILE, color_matches, load_json, size_matches, stock_cache_key


RESULTS_FILE = "results.json"
REPORT_FILE = "match_audit_report.json"


def compact_pairs(rows, color_key="color", size_key="size", limit=12):
    seen = []
    for row in rows:
        pair = f"{row.get(color_key) or ''} / {row.get(size_key) or ''}".strip()
        if pair and pair not in seen:
            seen.append(pair)
        if len(seen) >= limit:
            break
    return seen


def classify(row):
    variants = [
        v for v in ((row.get("officialStockRaw") or {}).get("variants") or [])
        if v.get("officialInStock")
    ]
    prices = row.get("prices") or []
    priced = [p for p in prices if p.get("inStock") and p.get("price", 0) > 0]

    if not variants:
        return "official_no_stock"
    if not prices:
        return "mendao_no_sku_rows"
    if not priced:
        return "mendao_no_price"

    exact = [
        p for p in priced
        if any(color_matches(p.get("color"), v.get("colour")) and size_matches(p.get("size"), v.get("size")) for v in variants)
    ]
    if exact:
        return "matched"

    color_any = any(color_matches(p.get("color"), v.get("colour")) for p in priced for v in variants)
    size_any = any(size_matches(p.get("size"), v.get("size")) for p in priced for v in variants)

    if not color_any and not size_any:
        return "color_and_size_no_match"
    if not color_any:
        return "color_no_match"
    if not size_any:
        return "size_no_match"
    return "color_size_combination_no_match"


def main():
    data = load_json(RESULTS_FILE, {})
    rows = data.get("results", [])
    stock_cache = load_json(STOCK_FILE, {})

    for row in rows:
        row["officialStockRaw"] = stock_cache.get(stock_cache_key(row), {})

    bad = []
    counts = Counter()
    for row in rows:
        if not row.get("has_dewu"):
            continue
        if (row.get("official_buyable_count") or 0) > 0:
            counts["matched"] += 1
            continue
        st = row.get("officialStock") or {}
        if st.get("inStockCount", 0) <= 0:
            counts["official_no_stock"] += 1
            continue

        reason = classify(row)
        counts[reason] += 1
        bad.append({
            "sku": row.get("sku"),
            "name": row.get("name"),
            "source": row.get("source"),
            "source_market": row.get("source_market"),
            "url": row.get("url"),
            "reason": reason,
            "official_in_stock_count": st.get("inStockCount", 0),
            "mendao_rows": len(row.get("prices") or []),
            "mendao_priced_sample": compact_pairs([p for p in row.get("prices") or [] if p.get("inStock")]),
            "annotated_official_sample": compact_pairs(
                [p for p in row.get("prices") or [] if p.get("officialMatched")],
                "officialColor",
                "officialSize",
            ),
        })

    report = {
        "total_results": len(rows),
        "summary": dict(counts),
        "unmatched_with_official_stock": bad,
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("match audit summary:")
    for key, value in counts.most_common():
        print(f"  {key}: {value}")
    print(f"report saved: {REPORT_FILE}")


if __name__ == "__main__":
    main()
