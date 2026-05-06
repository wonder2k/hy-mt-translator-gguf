# HY-MT Translator API 文档

## 基本信息

- Base URL（本地开发）：
  - `http://localhost:8000`
- Docker 内部访问：
  - `http://hy-mt-translator-api:8000`（按 docker-compose 服务名）

## 健康检查

### `GET /health`

**Response**

```json
{
  "status": "ok"
}
```

---

## 批量翻译接口

### `POST /translate-batch`

用于批量翻译短文本字段（地址、品名、人名等），当前主要支持 `en -> ja`。

#### Request Body

```json
{
  "source_lang": "en",
  "target_lang": "ja",
  "items": [
    {
      "text": "Tokyo, Chiyoda City, 1-1 Chiyoda",
      "field_type": "address"
    },
    {
      "text": "Apple iPhone 15 Pro Max 256GB",
      "field_type": "item_name"
    },
    {
      "text": "John Smith",
      "field_type": "person"
    }
  ]
}
```

字段说明：

- `source_lang`：源语言代码，当前推荐 `"en"`。
- `target_lang`：目标语言代码，当前推荐 `"ja"`。
- `items`：待翻译数组。
  - `text`：待翻译内容（单条最长约 128 字符，超出部分会被截断）。
  - `field_type`：字段类型，可选：
    - `"address"`：收件地址
    - `"item_name"`：品名
    - `"person"`：人名
    - `"generic"` / 省略：通用文本

#### Response Body

```json
{
  "translations": [
    "（对应第 1 条的日文地址）",
    "（对应第 2 条的日文品名）",
    "（对应第 3 条的人名日文形式）"
  ]
}
```

数组顺序与请求 `items` 一一对应。

#### 错误响应

- `400 Bad Request`：请求参数不合法，例如 `items` 为空。
- `500 Internal Server Error`：底层翻译服务异常（可查看 translator-api 和 llama-server 日志）。

---

## 与物流系统对接说明

在物流系统后端（Express.js）中：

- 使用环境变量 `TRANSLATOR_BASE_URL` 指向本服务：
  - Docker 内：`http://hy-mt-translator-api:8000`
  - 本地开发：`http://localhost:8000`
- 根据业务场景组装 `items` 数组，例如：
  - 地址字段使用 `field_type: "address"`
  - 品名字段使用 `field_type: "item_name"`
  - 收件人姓名使用 `field_type: "person"`
