#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
门道接口复现性验证工具。

只做请求重放与结构诊断：
- 不破解 sign。
- 不绕过验证码。
- 不绕过登录。
- 不做加密逆向。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "token",
    "openid",
    "session",
    "sessionid",
    "sign",
    "nonce",
    "encryptdata",
}

DYNAMIC_KEYS = {
    "sign",
    "signature",
    "timestamp",
    "timeStamp",
    "nonce",
    "nonceStr",
    "encryptData",
    "encryptedData",
}

KEY_FIELDS = ("articleNo", "spuId", "skuDTOList", "minPrice", "saleCnt")
ARTICLE_RE = re.compile(r"X\d{9}", re.IGNORECASE)
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "transfer-encoding",
    "content-encoding",
}


def load_capture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        data = json.load(f)
    required = ["url", "method", "requestHeaders", "requestBody", "responseBody"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"captured JSON 缺少字段: {', '.join(missing)}")
    return data


def maybe_json(value: Any) -> tuple[bool, Any]:
    if isinstance(value, (dict, list)):
        return True, value
    if not isinstance(value, str):
        return False, None
    text = value.strip()
    if not text:
        return False, None
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, None


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if is_sensitive_name(key):
            pairs.append((key, "***"))
        else:
            pairs.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))


def redact_text(text: str) -> str:
    redacted = text
    for key in SENSITIVE_KEYS:
        redacted = re.sub(
            rf"({re.escape(key)}\s*[=:]\s*)([^&,\s\"']+)",
            rf"\1***",
            redacted,
            flags=re.I,
        )
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", redacted, flags=re.I)
    return redacted


def is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    return any(k in lowered for k in SENSITIVE_KEYS)


def headers_for_replay(headers: Any) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}
    result = {}
    for key, value in headers.items():
        lowered = str(key).lower()
        if lowered in HOP_BY_HOP_HEADERS:
            continue
        result[str(key)] = str(value)
    return result


def find_dynamic_fields(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in DYNAMIC_KEYS or key.lower() in {k.lower() for k in DYNAMIC_KEYS}:
                found.append(path)
            found.extend(find_dynamic_fields(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value[:5]):
            found.extend(find_dynamic_fields(child, f"{prefix}[]"))
    return sorted(set(found))


def detect_dynamic_fields(capture: dict[str, Any]) -> list[str]:
    found: list[str] = []
    url_parts = urlsplit(str(capture.get("url", "")))
    for key, _ in parse_qsl(url_parts.query, keep_blank_values=True):
        if key in DYNAMIC_KEYS or key.lower() in {k.lower() for k in DYNAMIC_KEYS}:
            found.append(f"url.query.{key}")

    headers = capture.get("requestHeaders", {})
    if isinstance(headers, dict):
        for key in headers:
            if key in DYNAMIC_KEYS or key.lower() in {k.lower() for k in DYNAMIC_KEYS}:
                found.append(f"requestHeaders.{key}")

    ok, body_json = maybe_json(capture.get("requestBody", ""))
    if ok:
        found.extend(f"requestBody.{p}" for p in find_dynamic_fields(body_json))
    else:
        body_text = str(capture.get("requestBody", ""))
        for key in DYNAMIC_KEYS:
            if re.search(rf"(^|[?&\"'\s]){re.escape(key)}($|[=:\"'\s])", body_text, re.I):
                found.append(f"requestBody.{key}")

    return sorted(set(found))


def extract_original_article(capture: dict[str, Any]) -> str | None:
    for source in (capture.get("requestBody", ""), capture.get("url", ""), capture.get("responseBody", "")):
        text = source if isinstance(source, str) else json.dumps(source, ensure_ascii=False)
        match = ARTICLE_RE.search(text)
        if match:
            return match.group(0)
    return None


def replace_article_in_obj(value: Any, old_article: str | None, new_article: str) -> Any:
    if isinstance(value, dict):
        return {k: replace_article_in_obj(v, old_article, new_article) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_article_in_obj(v, old_article, new_article) for v in value]
    if isinstance(value, str):
        if old_article and old_article in value:
            return value.replace(old_article, new_article)
        return ARTICLE_RE.sub(new_article, value)
    return value


def replace_article_in_url(url: str, old_article: str | None, new_article: str) -> str:
    parts = urlsplit(url)
    pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        pairs.append((key, replace_article_in_obj(value, old_article, new_article)))
    path = replace_article_in_obj(parts.path, old_article, new_article)
    query = urlencode(pairs, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def replace_article_in_body(body: Any, old_article: str | None, new_article: str) -> Any:
    ok, body_json = maybe_json(body)
    if ok:
        return json.dumps(replace_article_in_obj(body_json, old_article, new_article), ensure_ascii=False)
    if isinstance(body, str):
        if old_article and old_article in body:
            return body.replace(old_article, new_article)
        return ARTICLE_RE.sub(new_article, body)
    return body


def build_replay_request(
    capture: dict[str, Any],
    new_article: str | None,
    old_article: str | None,
) -> tuple[str, str, dict[str, str], Any, str | None]:
    method = str(capture.get("method", "GET")).upper()
    url = str(capture["url"])
    headers = headers_for_replay(capture.get("requestHeaders", {}))
    body = capture.get("requestBody", "")

    replaced_from = None
    if new_article:
        replaced_from = old_article or extract_original_article(capture)
        url = replace_article_in_url(url, replaced_from, new_article)
        body = replace_article_in_body(body, replaced_from, new_article)

    return method, url, headers, body, replaced_from


def json_key_paths(value: Any, prefix: str = "$") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            paths.add(child_prefix)
            paths.update(json_key_paths(child, child_prefix))
    elif isinstance(value, list):
        paths.add(f"{prefix}[]")
        for child in value[:3]:
            paths.update(json_key_paths(child, f"{prefix}[]"))
    return paths


def field_presence(value: Any) -> dict[str, bool]:
    paths = json_key_paths(value)
    return {field: any(path.endswith(f".{field}") for path in paths) for field in KEY_FIELDS}


def structure_similarity(original: Any, replayed: Any) -> tuple[float, int, int]:
    left = json_key_paths(original)
    right = json_key_paths(replayed)
    if not left and not right:
        return 1.0, 0, 0
    union = left | right
    inter = left & right
    return len(inter) / len(union), len(inter), len(union)


def explain_failure(status_code: int, is_json: bool, text: str, dynamic_fields: list[str]) -> list[str]:
    reasons = []
    lowered = text.lower()
    if status_code in (401, 403):
        reasons.append("登录态、Cookie、Authorization 或设备校验可能失效。")
    if status_code == 404:
        reasons.append("URL 路径或接口版本可能依赖运行时路由。")
    if status_code >= 500:
        reasons.append("服务端返回错误，可能是参数不完整或接口不接受直接重放。")
    if dynamic_fields:
        reasons.append("请求中存在动态字段，可能需要小程序运行时生成签名。")
    if "sign" in lowered or "signature" in lowered:
        reasons.append("响应文本提到了签名，可能存在动态签名校验。")
    if "captcha" in lowered or "verify" in lowered or "验证码" in text:
        reasons.append("响应可能涉及验证码或人机校验。")
    if not is_json:
        reasons.append("响应不是 JSON，可能被网关、风控页或错误页拦截。")
    if not reasons:
        reasons.append("响应结构或关键字段不符合原始接口，建议继续对照 Fiddler 捕获。")
    return reasons


def print_report(
    capture: dict[str, Any],
    method: str,
    url: str,
    new_article: str | None,
    replaced_from: str | None,
    response: requests.Response,
    dynamic_fields: list[str],
) -> None:
    original_ok, original_json = maybe_json(capture.get("responseBody", ""))
    replay_ok, replay_json = maybe_json(response.text)
    replay_value = replay_json if replay_ok else response.text

    print("门道接口复现性测试")
    print("=" * 40)
    print(f"请求方式: {method}")
    print(f"请求 URL: {redact_url(url)}")
    if new_article:
        print(f"货号替换: {replaced_from or '未识别原货号'} -> {new_article}")
    else:
        print("重放模式: 原样重放")

    if dynamic_fields:
        print("\n动态字段提示:")
        for field in dynamic_fields:
            print(f"- {field}")
        print("结论: 可能存在动态签名；本工具只提示，不尝试破解。")

    print("\n响应摘要:")
    print(f"- HTTP 状态码: {response.status_code}")
    print(f"- 响应长度: {len(response.content)} bytes")
    print(f"- 是否为 JSON: {'是' if replay_ok else '否'}")

    if replay_ok:
        presence = field_presence(replay_value)
        print("- 关键字段:")
        for field in KEY_FIELDS:
            print(f"  {field}: {'有' if presence[field] else '无'}")

    if original_ok and replay_ok:
        score, same, total = structure_similarity(original_json, replay_json)
        print(f"- 与原始 response 字段结构相似度: {score:.2%} ({same}/{total})")
    else:
        print("- 与原始 response 字段结构相似度: 无法比较")

    likely_success = response.ok and replay_ok
    if original_ok and replay_ok:
        score, _, _ = structure_similarity(original_json, replay_json)
        likely_success = likely_success and score >= 0.55

    print("\n判断建议:")
    if likely_success:
        if new_article:
            print("- 只替换货号后仍返回相似 JSON，可继续用更多货号验证 api_mode。")
        else:
            print("- 原样重放返回相似 JSON，可继续测试只替换货号。")
    else:
        for reason in explain_failure(response.status_code, replay_ok, response.text[:2000], dynamic_fields):
            print(f"- {reason}")
        print("- 建议 fallback 到 UI + Fiddler 混合模式，先不要改主流程。")


def replay(capture_path: Path, new_article: str | None, old_article: str | None, timeout: float, verify_tls: bool) -> int:
    capture = load_capture(capture_path)
    dynamic_fields = detect_dynamic_fields(capture)
    method, url, headers, body, replaced_from = build_replay_request(capture, new_article, old_article)

    kwargs: dict[str, Any] = {
        "method": method,
        "url": url,
        "headers": headers,
        "timeout": timeout,
        "verify": verify_tls,
    }
    if method not in {"GET", "HEAD"}:
        kwargs["data"] = body.encode("utf-8") if isinstance(body, str) else body

    try:
        response = requests.request(**kwargs)
    except requests.RequestException as exc:
        print("门道接口复现性测试")
        print("=" * 40)
        print(f"请求 URL: {redact_url(url)}")
        print(f"请求失败: {type(exc).__name__}: {redact_text(str(exc))}")
        if dynamic_fields:
            print("检测到动态字段，可能存在动态签名；建议 fallback 到 UI + Fiddler 混合模式。")
        return 2

    print_report(capture, method, url, new_article, replaced_from, response, dynamic_fields)
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 Fiddler 捕获的门道接口是否可重放")
    parser.add_argument("capture", type=Path, help="Fiddler 保存的 captured JSON 文件")
    parser.add_argument("--article-no", help="替换成新的货号后重放，例如 X000010126")
    parser.add_argument("--old-article-no", help="指定原始货号；不传则自动从请求/响应里识别")
    parser.add_argument("--timeout", type=float, default=15.0, help="请求超时时间，默认 15 秒")
    parser.add_argument("--insecure", action="store_true", help="关闭 TLS 证书验证")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return replay(
            capture_path=args.capture,
            new_article=args.article_no,
            old_article=args.old_article_no,
            timeout=args.timeout,
            verify_tls=not args.insecure,
        )
    except Exception as exc:
        print(f"测试失败: {exc}")
        print("建议检查 captured JSON 是否包含完整 request/response 字段。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
