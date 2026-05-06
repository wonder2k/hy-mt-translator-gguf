# HY-MT Translator (Local GGUF + llama.cpp)

一个运行在本地 Docker 环境中的轻量翻译服务，用于给物流系统提供批量翻译接口。  
当前主要目标场景是 **英文 -> 日文**，重点支持以下字段：

- 地址（address）
- 品名（item_name）
- 人名（person）
- 通用文本（generic）

底层模型采用本地 GGUF 文件，通过 `llama.cpp` 的 `llama-server` 提供 OpenAI 风格接口；上层通过 `translator-api` 暴露业务接口 `/translate-batch`。

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
  │       ├─ models.py
  │       └─ translator_client.py
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

## 4. 启动方式

在项目根目录执行：

```powershell
docker-compose down
docker-compose build --no-cache llama-server translator-api
docker-compose up -d
```

---

## 5. 查看 llama-server 状态

```powershell
docker logs hy-mt-llama-server --tail 200
```

正常日志中应出现类似内容：

- `main: loading model`
- `srv load_model: loading model '/models/HY-MT1.5-1.8B-Q4_K_M.gguf'`
- `main: model loaded`
- `main: server is listening on http://0.0.0.0:8080`

---

## 6. 先测试底层 llama-server

### 6.1 测试首页

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8080/" -Method GET
```

如果返回 200，说明服务已启动。

### 6.2 测试 chat/completions

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

## 7. 测试业务接口 `/translate-batch`

### 7.1 PowerShell 推荐测试命令（UTF-8）

请优先使用下面这组命令，避免 Windows PowerShell 乱码问题：

```powershell
[Console]::OutputEncoding 
