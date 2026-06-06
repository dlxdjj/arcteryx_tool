# Fiddler 同时捕获 Request 和 Response

现有项目只把命中的 `spu-index` 响应体写入 `fiddler_latest.txt`。这足够让 `auto_click_mendao.py` 解析详情价格，但不足以判断接口能否脱离 UI 批量请求。要做接口复现性验证，需要保存完整请求、完整响应，并且每次命中都保存为独立 JSON 文件。

## 1. 修改 CustomRules.js

打开 Fiddler Classic：

1. 菜单选择 `Rules` -> `Customize Rules...`
2. 找到 `static function OnBeforeResponse(oSession: Session)`。
3. 在 `OnBeforeResponse` 前面加入 `JsonEscape` 和 `HeadersToJson` 两个辅助函数。
4. 在 `OnBeforeResponse` 函数内部加入捕获规则。
5. 把 `captureDir` 改成你本机项目路径下的 `fiddler_captures` 目录。

辅助函数：

```js
static function JsonEscape(s: String): String {
    if (s == null) return "";
    return s.Replace("\\", "\\\\")
            .Replace("\"", "\\\"")
            .Replace("\r", "\\r")
            .Replace("\n", "\\n")
            .Replace("\t", "\\t");
}

static function HeadersToJson(headers): String {
    var parts = new System.Text.StringBuilder();
    parts.Append("{");
    for (var i = 0; i < headers.Count(); i++) {
        var h = headers[i];
        if (i > 0) parts.Append(",");
        parts.Append("\"").Append(JsonEscape(h.Name)).Append("\":");
        parts.Append("\"").Append(JsonEscape(h.Value)).Append("\"");
    }
    parts.Append("}");
    return parts.ToString();
}
```

捕获规则：

```js
if (oSession.uriContains("spu-index") || oSession.uriContains("search") || oSession.uriContains("sku-summary")) {
    oSession.utilDecodeResponse();

    var captureDir = "C:\\Users\\linxx\\arcteryx_tool\\fiddler_captures";
    if (!System.IO.Directory.Exists(captureDir)) {
        System.IO.Directory.CreateDirectory(captureDir);
    }

    var now = System.DateTime.Now;
    var timestamp = now.ToString("yyyy-MM-ddTHH:mm:ss.fffzzz");
    var safeTime = now.ToString("yyyyMMdd_HHmmss_fff");
    var kind = "search";
    if (oSession.uriContains("spu-index")) {
        kind = "spu-index";
    } else if (oSession.uriContains("sku-summary")) {
        kind = "sku-summary";
    }
    var filePath = System.IO.Path.Combine(captureDir, safeTime + "_" + kind + ".json");

    var json = "{"
        + "\"timestamp\":\"" + JsonEscape(timestamp) + "\","
        + "\"url\":\"" + JsonEscape(oSession.fullUrl) + "\","
        + "\"method\":\"" + JsonEscape(oSession.RequestMethod) + "\","
        + "\"requestHeaders\":" + HeadersToJson(oSession.oRequest.headers) + ","
        + "\"requestBody\":\"" + JsonEscape(oSession.GetRequestBodyAsString()) + "\","
        + "\"responseHeaders\":" + HeadersToJson(oSession.oResponse.headers) + ","
        + "\"responseBody\":\"" + JsonEscape(oSession.GetResponseBodyAsString()) + "\","
        + "\"statusCode\":" + oSession.responseCode
        + "}";

    System.IO.File.WriteAllText(filePath, json, System.Text.Encoding.UTF8);

    if (oSession.uriContains("spu-index")) {
        System.IO.File.WriteAllText(
            "C:\\Users\\linxx\\arcteryx_tool\\fiddler_latest.txt",
            oSession.GetResponseBodyAsString(),
            System.Text.Encoding.UTF8
        );
    }
}
```

## 2. 捕获内容

每次命中搜索接口、`spu-index` 详情接口或 `sku-summary` SKU 成交摘要接口时，Fiddler 会在 `fiddler_captures` 下保存一个单独 JSON 文件，包含：

- `timestamp`
- `url`
- `method`
- `requestHeaders`
- `requestBody`
- `responseHeaders`
- `responseBody`
- `statusCode`

`fiddler_latest.txt` 仍然只保存最新 `spu-index` 的 response body，用于兼容现有 `auto_click_mendao.py` 流程。

## 3. 安全提醒

不要把 Cookie、Authorization、token 等内容打印到终端。上面的规则只保存到本地文件，不会主动输出到 Fiddler 日志或命令行。

分享捕获日志给别人之前，必须手动打码这些敏感字段：

- `Cookie`
- `Authorization`
- `token`
- `openid`
- `session`
- `sign`
- `nonce`
- `encryptData`
- 任何看起来像登录态、用户 ID、签名、密钥、手机号、地址的信息

如果不确定一个字段是否敏感，按敏感处理。
