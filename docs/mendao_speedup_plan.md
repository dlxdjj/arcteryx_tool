# 门道查询加速方案

这个项目当前的瓶颈在 UI 自动化：`auto_click_mendao.py` 需要控制微信小程序搜索货号、点击第一个结果、等待详情页，再由 Fiddler 保存 `spu-index` 响应。接口是否能脱离 UI 批量请求，需要先用 `mendao_replay_tester.py` 验证。

## 1. api_mode

适用条件：

- 搜索接口可以原样重放。
- 搜索接口只替换货号后仍能返回新货号的候选商品。
- `spu-index` 详情接口可以原样重放。
- 如果详情接口需要 `spuId`，搜索接口能稳定返回对应 `spuId`。
- 没有必须由小程序运行时生成且无法复用的动态签名。

实现方向：

- Python 直接批量请求搜索接口。
- 从搜索结果提取 `articleNo` / `spuId` 映射。
- 再批量请求 `spu-index` 详情接口。
- 继续沿用 `core.parse_mendao_spu()`、`mendao_db.json`、`sku_spu_map.json`、`results.json` 的数据结构。

优点是最快，缺点是依赖接口长期稳定和登录态有效。

## 2. hybrid_mode

适用条件：

- `spu-index` 详情接口可复现。
- 搜索接口不可复现，或者搜索接口替换货号后不稳定。
- `sku_spu_map.json` 已缓存一部分货号到 `spuId` / `articleNo` 的映射。

实现方向：

- 已缓存映射的货号直接调用详情接口刷新价格、尺码、销量。
- 未缓存的新货号仍然走 UI 查询一次。
- UI 查询成功后，把新映射写入 `sku_spu_map.json`，把详情写入 `mendao_db.json`。
- 下一轮运行时，新货号就可以进入接口刷新路径。

这是比较稳妥的中间态：减少重复 UI 操作，同时保留现有可用链路。

## 3. ui_fiddler_mode

适用条件：

- 搜索接口和 `spu-index` 接口都不可复现。
- 存在动态签名、一次性 nonce、强登录校验、验证码、设备绑定等限制。
- 直接请求返回 401、403、签名错误、空数据或结构明显不一致。
- 如果还需要近 7 日/30 日成交均价、销量和趋势，需要由 UI 点击具体颜色尺码 SKU，触发 `sku-summary` 之类的 SKU 摘要接口，再由 Fiddler 捕获。

优化方向：

- 继续用 UI 触发小程序真实请求。
- 不要固定依赖 `delay_search`、`delay_detail` 这样的长 sleep。
- 搜索后监听 Fiddler 捕获文件目录或 `fiddler_latest.txt` 的更新时间。
- 一旦捕获到新的响应并且 `core.parse_mendao_spu()` 解析成功，就立即进入下一条货号。
- 如果要采集 SKU 摘要，点击每个目标 SKU 后监听新的 `sku-summary` 捕获文件，并校验请求 URL 中的 `skuId` 与当前 SKU 匹配。
- 给监听设置超时，超时后再判断为无结果或需要人工处理。

这种模式不能突破小程序接口限制，但可以减少空等时间，通常比固定 sleep 更快、更稳定。

## 推荐落地顺序

1. 用 Fiddler 保存一条搜索接口 JSON 和一条 `spu-index` 详情接口 JSON。
2. 用 `mendao_replay_tester.py` 分别测试原样重放。
3. 对搜索接口测试只替换货号。
4. 对详情接口测试已缓存 `spuId` 或 `articleNo` 的直接刷新。
5. 根据测试结果选择 `api_mode`、`hybrid_mode` 或 `ui_fiddler_mode`。

在确认接口可复现之前，不建议改动 `auto_click_mendao.py` 主流程。
