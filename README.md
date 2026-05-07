# HY-MT Translator (Local GGUF + llama.cpp)

一个运行在本地 Docker 环境中的轻量翻译服务，用于给物流系统提供批量翻译接口。  
当前主要目标场景是 **英文 -> 日文**，重点支持以下字段：

- 地址（address）
- 品名（item_name）
- 人名（person）
- 通用文本（generic）

底层模型采用本地 GGUF 文件，通过 `llama.cpp` 的 `llama-server` 提供 OpenAI 风格接口；上层通过 `translator-api` 暴露业务接口 `/translate-batch`。

当前版本已经支持：

- `/translate-batch` 批量翻译
- Python 侧受控并行
- `llama-server` continuous batching
- `X-API-Key` 简单认证
- PowerShell 批量压测
- Windows / Docker Desktop 资源检查

---

## 1. 目录结构

```text
hy-mt-translator/
  ├─ docker-compose.yml
  ├─ llama-server/
  │   └─ Dockerfile
  ├─ translator-api/
  │   ├─ Dockerfile
  │   ├─ requirements.txt
  │   └─ app/
  │       ├─ main.py
  │       ├─ auth.py
  │       ├─ models.py
  │       └─ translator_client.py
  ├─ scripts/
  │   └─ test-translate-batch.ps1
  └─ models/
      └─ HY-MT1.5-1.8B-Q4_K_M.gguf
```

---

## 2. 运行环境

建议环境：

- Windows 11
- Docker Desktop
- Intel Core Ultra 7 155H
- 32GB RAM
- 本地已下载 GGUF 模型文件：
  - `HY-MT1.5-1.8B-Q4_K_M.gguf`

---

## 3. 模型文件放置

请确保模型文件放在：

```text
hy-mt-translator/models/HY-MT1.5-1.8B-Q4_K_M.gguf
```

---

## 4. docker-compose.yml 推荐配置

```yaml
version: "3.9"

services:
  llama-server:
    build:
      context: ./llama-server
    container_name: hy-mt-llama-server
    command:
      - /opt/llama.cpp/build/bin/llama-server
      - --model
      - /models/HY-MT1.5-1.8B-Q4_K_M.gguf
      - -c
      - "1024"
      - -t
      - "8"
      - -np
      - "4"
      - --cont-batching
      - --host
      - 0.0.0.0
      - --port
      - "8080"
    environment:
      - LD_LIBRARY_PATH=/opt/llama.cpp/build/bin:/opt/llama.cpp/build/src:/opt/llama.cpp/build/ggml/src
    volumes:
      - ./models:/models:ro
    ports:
      - "8080:8080"
    restart: unless-stopped

  translator-api:
    build:
      context: ./translator-api
    container_name: hy-mt-translator-api
    depends_on:
      - llama-server
    environment:
      - LLAMA_BASE_URL=http://host.docker.internal:8080
      - LLAMA_MODEL=HY-MT1.5-1.8B-Q4_K_M.gguf
      - TRANSLATOR_API_KEY=replace-with-a-long-random-string
      - MAX_INPUT_CHARS=160
      - MAX_OUTPUT_TOKENS=48
      - REQUEST_TIMEOUT_SECONDS=60
      - MAX_RETRIES=3
      - RETRY_BASE_DELAY_SECONDS=0.8
      - MAX_BATCH_ITEMS=50
      - CONCURRENCY_LIMIT=3
    ports:
      - "8000:8000"
    restart: unless-stopped
```

---

## 5. 启动方式

在项目根目录执行：

```powershell
docker-compose down
docker-compose build --no-cache llama-server translator-api
docker-compose up -d
```

---

## 6. 查看服务日志

### 6.1 llama-server

```powershell
docker logs hy-mt-llama-server --tail 200
```

正常日志中应出现类似内容：

- `main: loading model`
- `srv load_model: loading model '/models/HY-MT1.5-1.8B-Q4_K_M.gguf'`
- `main: model loaded`
- `main: server is listening on http://0.0.0.0:8080`

### 6.2 translator-api

```powershell
docker logs hy-mt-translator-api --tail 200
```

如果这里出现 `SyntaxError`、`Traceback` 等错误，请先修复 Python 代码再继续测试。

---

## 7. 先测试底层 llama-server

### 7.1 测试首页

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8080/" -Method GET
```

如果返回 200，说明服务已启动。

### 7.2 测试 chat/completions

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$llamaBody = @{
  model = "HY-MT1.5-1.8B-Q4_K_M.gguf"
  messages = @(
    @{
      role = "user"
      content = "Translate the following segment into Japanese, without additional explanation.`n`nApple iPhone 15 Pro Max 256GB"
    }
  )
  max_tokens = 48
  temperature = 0.2
  top_p = 0.9
} | ConvertTo-Json -Depth 4

$result = Invoke-RestMethod `
  -Uri "http://localhost:8080/v1/chat/completions" `
  -Method POST `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($llamaBody)) `
  -ContentType "application/json; charset=utf-8"

$result | ConvertTo-Json -Depth 6
```

如果返回内容中能看到正常日文，说明底层模型工作正常。

---

## 8. 认证机制

当前版本在 `/translate-batch` 上增加了简单的 API Key 认证，用于：

- 防止未授权调用
- 防止误调用导致 CPU 被无意义占用
- 便于后续 Express 后端安全接入

认证规则如下：

- `GET /health`：**不需要认证**
- `POST /translate-batch`：**必须带 `X-API-Key` 请求头**

### 8.1 API Key 配置

在 `docker-compose.yml` 中通过环境变量配置：

```yaml
- TRANSLATOR_API_KEY=replace-with-a-long-random-string
```

建议使用较长、随机、不可预测的字符串。

### 8.2 请求头格式

```http
X-API-Key: replace-with-a-long-random-string
```

如果请求头缺失或值不正确，接口会返回：

```json
{
  "detail": "Missing or invalid API key"
}
```

如果服务端未配置 API Key，会返回：

```json
{
  "detail": "Server API key is not configured"
}
```

---

## 9. 测试业务接口

### 9.1 测试 `/health`

```powershell
Invoke-RestMethod http://localhost:8000/health
```

正常应返回：

```json
{
  "status": "ok"
}
```

### 9.2 测试 `/translate-batch`

推荐在 PowerShell 里使用 `Invoke-RestMethod` 进行测试：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$headers = @{
  "X-API-Key" = "replace-with-a-long-random-string"
}

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

$result = Invoke-RestMethod `
  -Uri "http://localhost:8000/translate-batch" `
  -Method POST `
  -Headers $headers `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
  -ContentType "application/json; charset=utf-8"

$result | ConvertTo-Json -Depth 5
```

正常返回应类似：

```json
{
  "translations": [
    "東京都新宿区西新宿2-8-1 163-8001",
    "Apple iPhone 15 Pro Max 256GB ブラックチタニウム",
    "ジョン・スミス"
  ]
}
```

---

## 10. 接口说明

### `GET /health`

返回：

```json
{
  "status": "ok"
}
```

### `POST /translate-batch`

请求头：

```http
X-API-Key: your-api-key
```

请求体：

```json
{
  "source_lang": "en",
  "target_lang": "ja",
  "items": [
    {
      "text": "2-8-1 Nishishinjuku, Shinjuku-ku, Tokyo 163-8001",
      "field_type": "address"
    },
    {
      "text": "Apple iPhone 15 Pro Max 256GB Black Titanium",
      "field_type": "item_name"
    },
    {
      "text": "John Smith",
      "field_type": "person"
    }
  ]
}
```

响应体：

```json
{
  "translations": [
    "東京都新宿区西新宿2-8-1 163-8001",
    "Apple iPhone 15 Pro Max 256GB ブラックチタニウム",
    "ジョン・スミス"
  ]
}
```

---

## 11. field_type 说明

支持以下取值：

- `address`
- `item_name`
- `person`
- `generic`

当前策略：

### `address`
用于地址翻译，尽量保留：
- 数字
- 楼栋号
- 房号
- 邮编
- 关键地址结构

### `item_name`
用于物流品名、清关品名，尽量保留：
- 品牌
- 型号
- 容量
- 尺寸
- 颜色

### `person`
用于人名，尽量输出简洁稳定的名字，不追加 `様` 等敬语。

### `generic`
通用短文本翻译。

---

## 12. 当前 prompt 设计原则

当前版本**不使用长规则 prompt**。  
原因是：在当前 GGUF + llama.cpp 组合下，模型可能会把说明文字本身一起翻译出来。

所以当前策略是：

- 使用**短 prompt**
- 使用后处理清理杂质
- 通过字段类型控制 prompt 风格
- 控制 `max_tokens` 避免模型输出冗长解释

例如：

- address:
  - `Translate the following address into Japanese, without additional explanation.`
- item_name:
  - `Translate the following product name into Japanese, without additional explanation.`
- person:
  - `Translate the following name into Japanese, without additional explanation.`

---

## 13. 当前性能策略

当前版本属于：

- **业务层批量**
- **Python 受控并行**
- **底层 llama-server 多请求处理**

这意味着：

- API 支持一次传入多个 item
- Python 使用 `asyncio.gather + Semaphore` 做受控并行
- llama-server 使用 `-np 4 + --cont-batching`
- 当前方式更稳定，也更容易调试

建议起始参数：

- `CONCURRENCY_LIMIT=3`
- `MAX_BATCH_ITEMS=50`
- `MAX_OUTPUT_TOKENS=48`

---

## 14. 批量压测脚本

为了方便测试 `/translate-batch` 在不同批量下的性能，提供一份 PowerShell 压测脚本。

### 14.1 创建脚本文件

创建：

```text
hy-mt-translator/scripts/test-translate-batch.ps1
```

内容如下：

```powershell
# 强制使用 UTF-8 编码，避免中文乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. 先检查 /health 接口是否正常
Write-Host "1. Testing /health..." -ForegroundColor Green
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health"
    Write-Host "  - /health OK: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "  - /health FAIL: $($_.ErrorDetails.Message)" -ForegroundColor Red
    exit 1
}

# 2. API Key
$headers = @{
    "X-API-Key" = "replace-with-a-long-random-string"
}

# 3. 定义基础测试数据
$BaseText = "Apple iPhone 15 Pro Max 256GB Black Titanium"
$BaseField = "item_name"

function BuildBatchBody {
    param(
        [int]$ItemCount
    )

    $Items = @()
    for ($i = 0; $i -lt $ItemCount; $i++) {
        $Items += @{
            text = "$BaseText #$($i + 1)"
            field_type = $BaseField
        }
    }

    @{
        source_lang = "en"
        target_lang = "ja"
        items = $Items
    }
}

# 4. 逐次测试 1条、10条、20条、50条
$TestCases = @(1, 10, 20, 50)

foreach ($ItemCount in $TestCases) {
    Write-Host "2. Testing $ItemCount-item batch..." -ForegroundColor Yellow

    $BodyObj = BuildBatchBody -ItemCount $ItemCount
    $BodyJson = $BodyObj | ConvertTo-Json -Depth 3
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($BodyJson)

    $StopWatch = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        $Result = Invoke-RestMethod `
            -Uri "http://localhost:8000/translate-batch" `
            -Method POST `
            -Headers $headers `
            -Body $Bytes `
            -ContentType "application/json; charset=utf-8"

        $StopWatch.Stop()

        if ($Result.translations.Count -eq $ItemCount) {
            Write-Host "  - Success: $ItemCount items, time: $($StopWatch.ElapsedMilliseconds) ms" -ForegroundColor Green
        } else {
            Write-Host "  - ERROR: expected $ItemCount items, got $($Result.translations.Count)" -ForegroundColor Red
        }
    } catch {
        $StopWatch.Stop()
        Write-Host "  - ERROR: $($StopWatch.ElapsedMilliseconds) ms, error: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host "All tests done." -ForegroundColor Cyan
```

### 14.2 运行脚本

如果系统默认不允许直接运行 `.ps1`，推荐使用下面这个一次性命令：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\test-translate-batch.ps1"
```

如果你已经允许当前用户执行本地脚本，也可以直接运行：

```powershell
.\scripts\test-translate-batch.ps1
```

### 14.3 示例压测结果

示例输出：

```text
1. Testing /health...
  - /health OK: ok
2. Testing 1-item batch...
  - Success: 1 items, time: 1102 ms
2. Testing 10-item batch...
  - Success: 10 items, time: 5824 ms
2. Testing 20-item batch...
  - Success: 20 items, time: 17755 ms
2. Testing 50-item batch...
  - Success: 50 items, time: 40351 ms
All tests done.
```

### 14.4 压测结果解读

从上述样例可以看出：

- 1 条请求约 1.1 秒
- 10 条请求总耗时约 5.8 秒，平均每条约 0.58 秒
- 20 条请求总耗时约 17.8 秒，平均每条约 0.89 秒
- 50 条请求总耗时约 40.4 秒，平均每条约 0.81 秒

说明：

- 小批量（例如 5 到 10 条）通常性价比最好
- 批量越大，吞吐不一定线性提升
- 在本地 CPU 场景下，不建议默认单次 batch 做得过大

当前建议：

- 默认业务分块大小：8 到 12 条
- `CONCURRENCY_LIMIT=3` 先保持不变
- 后续优先引入缓存，再继续压榨吞吐

---

## 15. CPU / 内存 / 系统资源检查

为了判断当前配置下本地机器是否接近瓶颈，建议同时检查：

- Docker 容器资源
- Docker 可用资源总量
- Windows 主机 CPU / 内存
- 主要高占用进程

### 15.1 查看容器 CPU / 内存

```powershell
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}"
```

只查看本项目容器：

```powershell
docker stats --no-stream hy-mt-llama-server hy-mt-translator-api
```

### 15.2 查看 Docker 可用 CPU / 内存

```powershell
docker info --format "CPUs: {{.NCPU}}, Memory: {{.MemTotal}}"
```

### 15.3 查看 Windows 总 CPU 占用

```powershell
Get-Counter '\Processor(_Total)\% Processor Time'
```

### 15.4 查看可用内存

```powershell
Get-Counter '\Memory\Available MBytes'
```

### 15.5 查看最占资源的进程

```powershell
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, WS, PM
```

### 15.6 图形界面检查

- 任务管理器（Task Manager）
- 资源监视器（运行 `resmon`）
- Docker Desktop 容器资源界面

### 15.7 如何判断是否已接近瓶颈

一般可以这样判断：

- `hy-mt-llama-server` 在压测时 CPU 明显升高，说明推理在正常工作
- `translator-api` CPU 通常较低，这是正常现象
- 如果 Windows 主机整体 CPU 长时间接近 90% 以上，并出现明显卡顿，说明当前并发或 batch 偏高
- 如果 `llama-server` 内存稳定且不持续上涨，通常说明资源状态正常
- 如果大批量耗时增长明显变陡，说明已接近 CPU 推理吞吐瓶颈

---

## 16. Windows PowerShell 执行策略说明

如果运行脚本时报错：

```text
cannot be loaded because running scripts is disabled on this system
```

说明 PowerShell 执行策略阻止了 `.ps1` 文件直接运行。

推荐做法是一次性绕过，不修改系统全局策略：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\test-translate-batch.ps1"
```

如果你希望当前用户以后都能方便运行本地脚本，可以以管理员身份运行 PowerShell，然后执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

之后按 `Y` 确认。

---

## 17. 常见问题

### 17.1 PowerShell 显示乱码

如果返回日文时出现乱码，通常不是服务错误，而是控制台编码问题。  
请确保使用：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

并使用：

```powershell
-Body ([System.Text.Encoding]::UTF8.GetBytes($body))
-ContentType "application/json; charset=utf-8"
```

### 17.2 模型把提示词规则也翻译出来

说明 prompt 太长、太像说明书。  
请改用当前 README 中的**短 prompt 版本**，不要恢复旧版长规则模板。

### 17.3 translator-api 改了但没生效

修改 Python 代码后要重新 build：

```powershell
docker-compose build translator-api
docker-compose up -d translator-api
```

### 17.4 忘记带 X-API-Key

接口会返回 401：

```json
{
  "detail": "Missing or invalid API key"
}
```

### 17.5 服务端没配置 TRANSLATOR_API_KEY

接口会返回 500：

```json
{
  "detail": "Server API key is not configured"
}
```

### 17.6 批量太大导致响应明显变慢

这是本地 CPU 推理的正常现象。  
建议优先做业务分块和缓存，而不是继续无限增大单次 batch。

---

## 18. 后续优化路线

建议按这个顺序做：

1. 当前稳定版跑通
2. Python 侧受控并行
3. llama-server 并发参数微调
4. Express 端批量分块
5. Redis / PostgreSQL 缓存
6. 术语表
7. 更深层 batch 优化

---

## 19. 不建议现在做的事

当前阶段不建议：

- 把所有 item 拼成一个超长 prompt
- 盲目提高并发到 8 或更高
- 频繁改 llama-server 底层实现
- 在系统还没稳定前就引入过多复杂缓存逻辑

---

## 20. 当前结论

对本地笔记本、物流字段短文本、英文到日文翻译这个场景来说，当前方案已经可以进入业务联调。  
下一阶段重点应放在：

- Express 后端接入
- 批量请求拆分
- 翻译缓存
- 术语一致性
- API Key 安全接入
- 资源占用监控
