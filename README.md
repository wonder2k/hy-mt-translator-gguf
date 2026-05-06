# HY-MT Translator GGUF Demo

基于 HY-MT1.5-1.8B GGUF + llama.cpp 的本地翻译服务 Demo，用于给现有物流系统提供本地批量翻译接口（主要 EN -> JA）。

## 目录结构

```text
hy-mt-translator-gguf/
  ├─ llama-server/          # llama.cpp HTTP Server（加载 GGUF 模型）
  ├─ translator-api/        # 对外 REST API（/translate-batch）
  ├─ docs/                  # 接口文档
  ├─ docker-compose.yml     # 一键启动
  └─ README.md
```

## 依赖

- Docker
- Docker Compose

## 启动

```bash
docker-compose up -d --build
```

第一次启动会从 Hugging Face 下载 GGUF 模型，时间取决于网络，完成后会缓存。

## 测试

健康检查：

```bash
curl http://localhost:8000/health
```

批量翻译（EN -> JA）：

```bash
curl -X POST http://localhost:8000/translate-batch \
  -H "Content-Type: application/json" \
  -d '{
    "source_lang": "en",
    "target_lang": "ja",
    "items": [
      { "text": "Tokyo, Chiyoda City, 1-1 Chiyoda", "field_type": "address" },
      { "text": "Apple iPhone 15 Pro Max 256GB", "field_type": "item_name" },
      { "text": "John Smith", "field_type": "person" }
    ]
  }'
```

返回示例：

```json
{
  "translations": [
    "...",
    "...",
    "..."
  ]
}
```

## 与物流系统对接

详见 `docs/api.md`。
