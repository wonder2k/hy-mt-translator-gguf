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

# 2. 定义基础测试数据
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

# 3. 逐次测试 1条、10条、20条、50条
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
