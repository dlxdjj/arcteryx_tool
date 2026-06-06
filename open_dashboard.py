#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动本地网页工作台。

如果 8080 已被旧服务占用，会自动尝试 8081、8082 等端口，避免打开旧页面。
"""
from __future__ import annotations

import functools
import http.server
import socket
import socketserver
import threading
import time
import webbrowser
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
START_PORT = 8080


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def pick_port(start: int = START_PORT, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"没有可用端口：{start}-{start + attempts - 1}")


def start_server(port: int) -> None:
    handler = functools.partial(Handler, directory=str(BASE_DIR))
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()


def main() -> None:
    port = pick_port()
    url = f"http://localhost:{port}/index.html"
    print(f"启动工作台: {url}")
    if port != START_PORT:
        print(f"提示: 端口 {START_PORT} 已被占用，已切换到 {port}")

    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    time.sleep(0.5)

    webbrowser.open(url)
    print("按 Ctrl+C 关闭工作台服务")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("工作台已关闭")


if __name__ == "__main__":
    main()
