#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键启动网页工作台
自动启动本地服务器并打开浏览器
"""
import http.server, threading, webbrowser, os, sys

PORT = 8080

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默运行，不打印日志

def start_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with http.server.HTTPServer(('', PORT), Handler) as httpd:
        httpd.serve_forever()

print(f"启动工作台服务器... 端口{PORT}")
t = threading.Thread(target=start_server, daemon=True)
t.start()

import time
time.sleep(0.5)

webbrowser.open(f'http://localhost:{PORT}/index.html')
print(f"已在浏览器打开工作台")
print(f"按 Ctrl+C 关闭服务器")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("服务器已关闭")
