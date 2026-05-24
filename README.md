# 套利工作台 — Arc'teryx × 门道

始祖鸟奥特莱斯 → 得物/门道 跨境跨平台套利比价工具。从始祖鸟意大利奥特莱斯抓取打折商品，在得物平台查价，计算利润空间，并有记账功能追踪每一笔买卖。

## 功能

- **自动抓取** - 从 Arc'teryx Outlet API 抓取全品类打折商品（男/女冲锋衣、抓绒、上装、裤装等）
- **自动查价** - PyAutoGUI 控制微信门道小程序逐个搜索货号，配合 Fiddler 拦截 API 响应，自动解析颜色×尺码价格
- **利润对比** - 综合成本（欧元×汇率+运费+手续费）vs 得物到手价，按利润排序，支持多维度筛选排序
- **网页工作台** - PWA 看板，深色主题，移动端/桌面端自适应，支持商品详情弹窗实时调参重算
- **记账追踪** - 记录每件商品的采购成本、实售价、平台、状态（持有中/已售出），自动计算 ROI
- **实时汇率** - Frankfurter API 获取 EUR→CNY 汇率，支持缓存和手动刷新

## 项目结构

```
arcteryx_tool/
├── index.html              # PWA 工作台（比价 + 记账）
├── sw.js                   # Service Worker 离线缓存
├── manifest.json           # PWA 清单
├── icon.svg                # 应用图标
├── core.py                 # 核心共用库（配置、API 抓取、利润计算）
├── auto_click_mendao.py    # 主自动化脚本（PyAutoGUI 控制微信门道小程序）
├── rebuild_results.py      # 用缓存数据重建利润对比结果
├── manual_add.py           # 手动补录门道未收录货号
├── socks5_server.py        # SOCKS5 代理服务器
├── open_dashboard.py       # 启动本地服务器 + 打开浏览器
├── launcher.bat            # Windows 菜单式启动器
└── config.json             # 利润计算参数（汇率、运费、手续费等）
```

## 快速开始

### 方式一：启动器（推荐）
双击 `launcher.bat`，按菜单选择操作。

### 方式二：命令行
```bash
# 1. 自动查价（需要微信 + 门道小程序 + Fiddler）
python auto_click_mendao.py

# 2. 仅用缓存数据生成利润结果
python rebuild_results.py

# 3. 打开网页看板
python open_dashboard.py

# 4. 手动补录门道未收录的货号
python manual_add.py
```

## 前置条件

- Python 3.x（依赖：`pyautogui`, `pyperclip`, `requests`, `openpyxl`, `urllib3`）
- [Fiddler Classic](https://www.telerik.com/fiddler/fiddler-classic) — 拦截门道小程序 API 响应
- 微信 + 门道小程序 — 搜索货号查价
- 浏览器 — 查看网页工作台

## Fiddler 配置

在 Fiddler CustomRules.js 的 `OnBeforeResponse` 中添加：
```js
if (oSession.uriContains("spu-index")) {
    oSession.utilDecodeResponse();
    System.IO.File.WriteAllText(
        "C:\\Users\\linxx\\Desktop\\arcteryx_tool\\fiddler_latest.txt",
        oSession.GetResponseBodyAsString()
    );
}
```

## 注意事项

- 仅支持 Windows（PyAutoGUI 坐标定位依赖）
- 查价过程中请勿操作鼠标（PyAutoGUI 在自动点击）
- 鼠标移到屏幕左上角可紧急停止自动化
