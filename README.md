# 套利工作台：Arc'teryx × 门道

这是一个用于对比 Arc'teryx 意大利 Outlet / 官网 与门道潮流小程序价格的本地工具。

当前推荐使用方式是“一键流程”：自动抓取 Arc'teryx 商品，补齐门道价格缓存，补齐官网颜色/尺码库存，按“官网有货 + 门道有价”的 SKU 重新计算利润，并打开本地工作台查看结果。

> 注意：门道接口是否能脱离 UI 批量请求，需要用本项目提供的复现工具自行验证。不要破解 sign，不要绕过登录、验证码或小程序安全机制。

## 主要能力

- 抓取 Arc'teryx 商品：支持 `Outlet` 和 `Official` 两个来源。
- 门道价格补齐：通过微信门道小程序触发搜索，Fiddler 捕获响应，Python 解析价格、尺码、颜色、销量。
- 官网库存补齐：读取官网商品页背后的 Next.js JSON 数据，提取颜色、尺码、库存状态。
- 精准利润展示：只把“官网对应颜色/尺码有货，并且门道对应 SKU 有价格”的项作为可买利润。
- SKU 级明细：前端详情页展示门道 SKU ID、颜色、尺码、官网库存、门道价、利润、门道销量。
- 缓存复用：已查过的门道货号会写入缓存，后续只补新货号。
- 接口复现验证：可用 Fiddler 捕获完整 request/response，再用脚本测试原样重放和替换货号重放。

## 快速开始

### 1. 安装依赖

```powershell
cd C:\Users\linxx\Desktop\arcteryx_tool
pip install pyautogui pyperclip requests openpyxl urllib3
```

如果项目在其他目录，请把路径换成你的实际目录。

### 2. 准备 Fiddler 和微信门道

运行完整一键流程前，请先确保：

- Fiddler Classic 已开启 HTTPS 抓包。
- 微信已打开门道小程序。
- Fiddler 规则能把门道接口响应写入项目目录。
- 首次使用时已经完成 PyAutoGUI 坐标定位。

Fiddler 详细配置见：

- `docs/fiddler_capture_request_response.md`

### 3. 一键运行

推荐直接运行：

```powershell
python run_pipeline.py
```

也可以双击：

```text
run_all.bat
```

完整流程会依次执行：

1. 抓取 Arc'teryx Outlet + Official 商品。
2. 检查哪些货号已有门道缓存。
3. 对新货号启动微信门道 UI 查询。
4. 生成 `results.json`。
5. 补齐官网颜色/尺码库存，生成或更新 `arcteryx_stock.json`。
6. 重新按官网有货 SKU 计算利润。
7. 生成匹配审计报告。
8. 自动打开网页工作台。

## 常用命令

只用已有门道缓存重新生成结果：

```powershell
python run_pipeline.py --skip-mendao
```

只生成数据，不自动打开网页：

```powershell
python run_pipeline.py --no-open
```

跳过官网库存补齐：

```powershell
python run_pipeline.py --no-stock
```

跳过匹配审计：

```powershell
python run_pipeline.py --no-audit
```

手动打开工作台：

```powershell
python open_dashboard.py
```

## 项目结构

```text
.
├── run_pipeline.py             # 一键总流程入口
├── run_all.bat                 # Windows 双击启动脚本
├── auto_click_mendao.py        # 微信门道 UI 查询 + Fiddler 响应解析
├── core.py                     # 配置、Arc'teryx 抓取、利润计算、门道解析
├── official_stock_enrich.py    # 官网颜色/尺码/库存补齐
├── product_match_audit.py      # 官网库存与门道 SKU 匹配审计
├── mendao_replay_tester.py     # 门道接口可复现性测试脚本
├── open_dashboard.py           # 启动本地网页工作台
├── index.html                  # 前端工作台
├── config.json                 # 成本、抓取来源、延迟等配置
├── sku_aliases.json            # 货号别名，例如 X000010110 -> X000010110-Black
├── mendao_db.json              # 门道商品详情缓存
├── sku_spu_map.json            # Arc'teryx 货号到门道 spuId 的映射
├── arcteryx_stock.json         # 官网 SKU 库存缓存
├── results.json                # 前端展示结果
└── docs/
    ├── fiddler_capture_request_response.md
    └── mendao_speedup_plan.md
```

## 数据与匹配逻辑

### 商品来源

`core.py` 当前会抓取：

- `sale`：`https://outlet.arcteryx.com/it/en`
- `outdoor`：`https://arcteryx.com/it/en`

同一个货号可能同时存在于 Outlet 和 Official，也可能对应不同颜色或商品页。因此项目不会只按货号粗暴去重，而是按来源、货号、商品 URL 保留商品行。

### 门道数据

门道数据来自小程序接口响应，主要写入：

- `mendao_db.json`：spu 详情、SKU 价格、颜色、尺码、销量。
- `sku_spu_map.json`：货号到门道 spuId 的映射。
- `missing_skus.json`：门道查询不到或无法确认匹配的货号。

### 官网库存数据

`official_stock_enrich.py` 会为每个商品页提取官网 SKU 级信息：

- 颜色
- 尺码
- 是否有库存
- 官网价格 / 折扣价

前端只把“官网有货”的颜色/尺码作为真正可买项。

### 利润展示规则

首页利润优先使用：

- 官网对应颜色/尺码有货
- 门道对应颜色/尺码有价格
- 二者匹配成功后的最低门道价

详情弹窗默认只显示官网有货 SKU。如果要排查颜色/尺码为什么没匹配，可以点“显示全部”查看门道无价、官网无货、未匹配的行。

## Fiddler 捕获

旧流程只需要把 `spu-index` 的 response body 写入：

```text
fiddler_latest.txt
```

如果要验证接口能不能脱离 UI 重放，请按文档保存完整 request/response：

```text
docs/fiddler_capture_request_response.md
```

分享捕获日志前必须手动打码：

- Cookie
- Authorization
- token
- openid
- session
- sign
- nonce
- timestamp
- 其他任何登录态或设备标识

## 接口复现测试

读取 Fiddler 保存出的 captured JSON：

```powershell
python mendao_replay_tester.py .\fiddler_captures\xxxx_search.json --insecure
```

测试替换货号：

```powershell
python mendao_replay_tester.py .\fiddler_captures\xxxx_search.json --article-no X000010126 --insecure
```

判断标准：

- 原样重放 200 且 JSON 结构相似：说明当前请求在短时间内可复现。
- 替换货号也 200 且返回目标货号：说明搜索接口可能可批量化。
- 返回 401、签名错误、结构变化大：多半存在动态签名或登录态校验。
- 存在 sign / timestamp / nonce / encryptData：只提示风险，不做破解。
- 替换货号失败：继续使用 UI + Fiddler 混合模式。

## 配置说明

`config.json` 示例：

```json
{
  "eur_to_cny": 8.0,
  "weight_kg": 0.5,
  "freight_per_kg": 100,
  "dewu_fixed": 48,
  "dewu_pct": 0.06,
  "arcteryx_markets": ["sale", "outdoor"],
  "official_stock_markets": ["sale", "outdoor"],
  "official_stock_delay": 0.2
}
```

常用字段：

| 字段 | 说明 |
| --- | --- |
| `eur_to_cny` | 欧元兑人民币汇率 |
| `weight_kg` | 单件预估重量 |
| `freight_per_kg` | 国际运费 |
| `dewu_fixed` | 平台固定费用 |
| `dewu_pct` | 平台手续费比例 |
| `arcteryx_markets` | 抓取 `sale` / `outdoor` |
| `official_stock_markets` | 补齐哪些来源的官网库存 |
| `official_stock_delay` | 官网库存请求间隔 |

## 货号别名

有些门道商品不是用纯货号查询，例如：

```json
{
  "X000010110": ["X000010110-Black"]
}
```

这类映射放在：

```text
sku_aliases.json
```

系统会优先查原货号，查不到时再尝试别名。别名只用于门道搜索，不会改变官网商品本身。

## 排查建议

如果首页没有结果：

1. 确认已经生成 `results.json`。
2. 运行 `python run_pipeline.py --skip-mendao --no-open` 看是否报错。
3. 运行 `python open_dashboard.py`，用新打开的地址访问页面。
4. 浏览器强制刷新，避免 Service Worker 旧缓存。

如果详情里显示“未匹配”：

- 官网有货颜色/尺码与门道颜色/尺码没有匹配上。
- 例如 `2XL` 和 `XXL` 已做归一化；但颜色不会激进猜测，避免错误匹配。
- 可以看 `match_audit_report.json` 排查是颜色不匹配、尺码不匹配，还是门道无价格。

如果出现 429：

- 官网请求被限流。
- 降低速度，提高 `official_stock_delay`。
- 等一段时间后用 `python run_pipeline.py --skip-mendao` 继续补齐。

## 注意事项

- 自动点击时不要移动鼠标；移动到屏幕左上角可触发 PyAutoGUI 紧急停止。
- 门道 UI 查询依赖微信窗口位置，首次运行需要定位坐标。
- 不建议把 Fiddler 完整捕获日志提交到 Git。
- 不要尝试破解签名、验证码、加密字段或登录保护。
