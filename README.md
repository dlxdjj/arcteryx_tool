# 套利工作台 — Arc'teryx × 门道

始祖鸟奥特莱斯 → 得物/门道 跨境跨平台套利比价工具。自动抓取始祖鸟打折商品，在微信门道小程序查价，计算跨平台利润空间，并追踪每一笔买卖的盈亏。

## 功能

- **自动抓取商品** — 从 Arc'teryx Outlet API 抓取意大利区打折商品（9 个品类：男/女冲锋衣、抓绒、上装、底层、裤装、软壳等）
- **自动查价** — PyAutoGUI 控制微信门道小程序逐个搜索货号，配合 Fiddler 拦截 `spu-index` API 响应，自动解析颜色×尺码价格和销量
- **利润对比** — 综合成本（欧元×汇率 + 重量×运费 + 手续费）vs 得物到手价，按利润排序，支持筛选（男/女/冲锋衣/抓绒/盈利）
- **网页工作台** — PWA 单页应用，深色主题，移动端/桌面端自适应，详情弹窗可实时调参数重算利润
- **记账追踪** — 记录采购成本、实售价、平台、状态，自动计算总投入/已实现利润/ROI
- **实时汇率** — Frankfurter API 获取 EUR→CNY，支持缓存（1 小时 TTL）和手动刷新

## 技术栈

- **前端**：原生 HTML/CSS/JS，PWA（Service Worker + Web App Manifest）
- **后端脚本**：Python 3（PyAutoGUI、requests、openpyxl、pyperclip）
- **数据抓取**：Arc'teryx Outlet API + Fiddler 抓包门道小程序
- **利润模型**：可配置的欧元汇率、重量、运费、得物手续费等参数（config.json）

## 项目结构

```
├── index.html              # PWA 工作台（比价 Tab + 记账 Tab）
├── sw.js                   # Service Worker（离线缓存 + 策略路由）
├── manifest.json           # PWA 清单
├── core.py                 # 共用库（配置读写、API 抓取、利润计算、门道数据解析）
├── auto_click_mendao.py    # 自动化查价主脚本（PyAutoGUI + Fiddler）
├── rebuild_results.py      # 从缓存重建 results.json
├── manual_add.py           # 手动补录门道未收录货号
├── socks5_server.py        # SOCKS5 代理服务器
├── open_dashboard.py       # 一键启动本地 HTTP 服务并打开浏览器
├── launcher.bat            # Windows 菜单式启动器
├── config.json             # 利润计算参数
├── results.json            # 利润对比结果
└── mendao_db.json          # 门道价格缓存
```

## 本地运行

### 前置条件

- Windows（PyAutoGUI 坐标定位依赖 Windows 屏幕坐标系）
- Python 3.x，安装依赖：
  ```bash
  pip install pyautogui pyperclip requests openpyxl urllib3
  ```
- [Fiddler Classic](https://www.telerik.com/fiddler/fiddler-classic) — 用于拦截微信门道小程序 API
- 微信 + 门道小程序 — 查价目标平台

### Fiddler 配置

在 CustomRules.js 的 `OnBeforeResponse` 中添加：

```js
if (oSession.uriContains("spu-index")) {
    oSession.utilDecodeResponse();
    System.IO.File.WriteAllText(
        "C:\\path\\to\\arcteryx_tool\\fiddler_latest.txt",
        oSession.GetResponseBodyAsString()
    );
}
```

### 运行

```bash
# 方式一：菜单启动器
launcher.bat

# 方式二：命令行
python auto_click_mendao.py   # 自动查价（需 Fiddler + 微信）
python rebuild_results.py     # 用缓存生成利润结果
python manual_add.py          # 手动补录价格
python open_dashboard.py      # 打开网页工作台（localhost:8080）
```

## 配置说明

`config.json` 中的利润计算参数均可在网页工作台的详情弹窗中实时调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| eur_to_cny | 8.0 | 欧元兑人民币汇率 |
| weight_kg | 0.5 | 单件预估重量 |
| freight_per_kg | 100 | 每公斤国际运费（元） |
| dewu_pct | 0.06 | 得物平台手续费率 |
| dewu_fixed | 48 | 得物固定服务费（元） |
| domestic_freight | 7 | 国内运费（元） |

## 注意事项

- 查价过程中请勿操作鼠标（PyAutoGUI 在自动控制光标），鼠标移到屏幕左上角可紧急停止
- 门道小程序的搜索框、第一个结果、返回按钮的屏幕坐标需首次运行时定位（保存在 dewu_positions.json）
