# HY-MT Translator GGUF Demo

基于 `HY-MT1.5-1.8B-Q4_K_M.gguf` + `llama.cpp` 的本地翻译服务 Demo，用于给物流系统提供本地批量翻译接口，当前主目标是 **EN -> JA**，重点覆盖地址、品名、人名等短字段。[1][2]

## 项目结构

```text
hy-mt-translator/
  ├─ docker-compose.yml
  ├─ llama-server/
  │   └─ Dockerfile
  ├─ translator-api/
  │   ├─ app/
  │   │   ├─ main.py
  │   │   ├─ models.py
  │   │   └─ translator_client.py
  ├─ docs/
  │   └─ api.md
  ├─ express-example/
  │   └─ src/
  │       ├─ utils/
  │       │   └─ translator.ts
  │       └─ routes/
  │           └─ shipment.ts
  └─ models/
      └─ HY-MT1.5-1.8B-Q4_K_M.gguf
```

## 当前方案说明

这套方案使用 `llama.cpp` 的 HTTP Server 加载本地 GGUF 模型文件，并通过 `translator-api` 对外提供更贴近业务的 `/translate-batch` 接口。[2][1]

`llama-server` 已验证能够成功加载 `HY-MT1.5-1.8B-Q4_K_M.gguf`，并通过 `/v1/chat/completions` 返回标准 OpenAI 风格 JSON 响应。[2][1]

## 环境要求

- Windows 11 + Docker Desktop。
- 建议至少 16GB 内存；你当前 32GB RAM 配置对 1.8B Q4_K_M 是足够的。[1]
- 已手动下载模型文件：`HY-MT1.5-1.8B-Q4_K_M.gguf`，来源仓库为 `tencent/HY-MT1.5-1.8B-GGUF`。[1]

## 模型文件准备

在项目根目录创建 `models` 目录，并放入模型文件：

```text
hy-mt-translator/
  └─ models/
      └─ HY-MT1.5-1.8B-Q4_K_M.gguf
```

推荐文件：

- 仓库：`tencent/HY-MT1.5-1.8B-GGUF`。[1]
- 文件：`HY-MT1.5-1.8B-Q4_K_M.gguf`。[1]

## 部署步骤

### 1. 构建并启动服务

在项目根目录执行：

```powershell
docker-compose down
docker-compose build --no-cache llama-server translator-api
docker-compose up -d
```

### 2. 检查 llama-server 日志

```powershell
docker logs hy-mt-llama-server --tail 200
```

正常情况下，日志中应出现以下关键信息：

- `main: loading model`
- `srv load_model: loading model '/models/HY-MT1.5-1.8B-Q4_K_M.gguf'`
- `main: model loaded`
- `main: server is listening on http://0.0.0.0:8080`

这表明模型已被正确加载，本地 HTTP 服务已经启动。[2]

### 3. 检查 translator-api

```powershell
docker logs hy-mt-translator-api --tail 200
```

如果没有 Python traceback，并且 `/health` 返回 200，则说明 API 容器正常启动。

## 测试流程

### 1. 测试 llama-server 首页

在 PowerShell 中：

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8080/" -Method GET
```

返回 200 即表示底层服务存活。[2]

### 2. 直接测试 chat/completions

```powershell
$llamaBody = @{
  model = "HY-MT1.5-1.8B-Q4_K_M.gguf"
  messages = @(
    @{
      role = "user"
      content = "Translate the following segment into Japanese, without additional explanation.`n`nApple iPhone 15 Pro Max 256GB"
    }
  )
  max_tokens = 64
  temperature = 0.2
  top_p = 0.9
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Uri "http://localhost:8080/v1/chat/completions" `
  -Method POST `
  -Body $llamaBody `
  -ContentType "application/json"
```

如果成功，你会拿到类似下面的 JSON：

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "アップル・iPhone 15 Pro Max 256GB"
      }
    }
  ]
}
```

这表示底层模型推理链路已经跑通。[2]

### 3. 测试业务接口 `/translate-batch`

```powershell
$body = @{
  source_lang = "en"
  target_lang = "ja"
  items = @(
    @{
      text = "2-8-1 Nishishinjuku, Shinjuku-ku, Tokyo 163-8001"
      field_type = "address"
    },
    @{
      text = "Apple iPhone 15 Pro Max 256GB Black Titanium"
      field_type = "item_name"
    },
    @{
      text = "John Smith"
      field_type = "person"
    }
  )
} | ConvertTo-Json -Depth 3

Invoke-RestMethod `
  -Uri "http://localhost:8000/translate-batch" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

PowerShell 下更推荐使用 `Invoke-RestMethod`，因为它会直接把 JSON 响应解析成对象，避免 `Invoke-WebRequest` 的安全提示与 `.Content` 读取问题。[3][4]

## translator_client.py 当前策略

当前版本针对物流字段做了定制化 prompt 与后处理：

- `address`：保留数字、邮编、楼栋号、房号，不补造缺失信息，偏 shipping label 风格。[5][6]
- `item_name`：偏向物流与清关可读的具体品名，不使用营销化表达；这与日本邮政对国际件品名“要具体”的建议一致。[7][8]
- `person`：不附加 `様` 等敬语，输出更适合数据库落库和运单字段。
- `generic`：采用简洁翻译 prompt，只输出译文，符合 HY-MT 官方 XX↔XX 模板思路。[9][10]

## 部署参数说明

| 参数 | 当前值 | 说明 |
|------|--------|------|
| 模型文件 | `HY-MT1.5-1.8B-Q4_K_M.gguf` | 适合本地 CPU 运行的 Q4_K_M 量化版本。[1] |
| `-c` | `1024` | 上下文限制，对短字段翻译足够，也有利于延迟控制。[2] |
| `-t` | `8` | 初始线程数，适合当前笔记本 CPU 配置；后续可做压测微调。 |
| `max_tokens` | `80` | 输出限制，防止模型输出冗长解释。 |
| 输入截断 | `160` 字符 | 防止异常长字段拖慢整体性能。 |

## 常见问题

### 1. PowerShell 出现 Script Execution Risk

这是 PowerShell 5.1 对 `Invoke-WebRequest` 的安全提示，不是服务故障；可以改用 `Invoke-RestMethod`，或者为 `Invoke-WebRequest` 增加 `-UseBasicParsing`。[3][11]

### 2. llama-server 已经起来，但 translator-api 仍报错

首先检查 `LLAMA_BASE_URL` 是否为：

```text
http://host.docker.internal:8080
```

在 Windows + Docker Desktop 下，这通常比直接使用容器服务名更稳。[12]

### 3. chat/completions 可以调用，但业务翻译结果风格不理想

这不是部署故障，而是 prompt 与后处理策略问题。当前版本已经针对地址、品名、人名做了初步优化，后续可以继续引入术语表、词典映射和缓存机制。[13][14]

## 生产化建议

### 1. 翻译缓存

建议按 `(source_lang, target_lang, field_type, text)` 做 Redis 或 PostgreSQL 缓存，减少重复请求，提高吞吐稳定性。

### 2. 术语表

可以为品牌名、规格、包装词、危险品类等维护一份术语表，在调用模型前做预替换或后校正；HY‑MT 技术报告也强调了术语干预对专业翻译场景的价值。[13][14]

### 3. 异步翻译

对不影响主流程的字段，可采用异步回填策略，降低峰值时的同步接口压力。

## 下一步

在现有状态下，这套系统已经可以进入与你物流系统的联调阶段。建议先从地址、品名、人名三个字段开始接入，再逐步引入缓存、术语表和审计日志。
