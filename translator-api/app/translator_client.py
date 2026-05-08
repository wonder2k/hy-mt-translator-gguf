import os
import re
import asyncio
from typing import List
import httpx

# 配置保持不变
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://host.docker.internal:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "HY-MT1.5-1.8B-Q4_K_M.gguf")

MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "160"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "64")) # 稍微增加以防长地址截断
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_DELAY_SECONDS = float(os.getenv("RETRY_BASE_DELAY_SECONDS", "0.8"))
MAX_BATCH_ITEMS = int(os.getenv("MAX_BATCH_ITEMS", "50"))
CONCURRENCY_LIMIT = int(os.getenv("CONCURRENCY_LIMIT", "3"))

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

def _truncate_text(text: str) -> str:
    if not text:
        return ""
    return text.strip()[:MAX_INPUT_CHARS]

def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def _build_prompt(field_type: str, source_lang: str, target_lang: str, text: str) -> str:
    """
    针对 1.8B 模型优化的结构化 Prompt。
    增加 Few-shot 示例能显著提高地址转换的准确率。
    """
    lang_map = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}
    src = lang_map.get(source_lang, source_lang)
    tgt = lang_map.get(target_lang, target_lang)

    # 地址翻译：侧重专有名词对齐，禁止解释
    if field_type == "address":
        return f"""Task: Translate the following address from {src} to {tgt}.
Rules: Keep the format concise. No explanation. Use standard official names.
Text: {text}
Translation:"""

    # 物品品名：侧重电商术语，保持简短
    if field_type == "item_name":
        return f"""Task: Translate the product name from {src} to {tgt}.
Rules: Output only the translated name. No descriptions.
Text: {text}
Translation:"""

    # 姓名/通用
    if field_type == "person":
        return f"""Task: Translate the person name from {src} to {tgt}.
Rules: Output only the name.
Text: {text}
Translation:"""

    return f"""Translate from {src} to {tgt}: {text}\nTranslation:"""

def _postprocess_translation(field_type: str, text: str, target_lang: str) -> str:
    text = _normalize_whitespace(text)
    # 移除引号
    text = text.strip(' "\'「」')

    # 动态构建前缀过滤（支持多语种）
    prefixes = [
        "翻译：", "译文：", "结果：",
        "Translation:", "Translated text:", "Result:", "Output:",
        "日本語:", "Japanese:", "Target:",
    ]
    for prefix in prefixes:
        # 忽略大小写匹配前缀
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()

    # 过滤小模型常见的喋喋不休（幻觉）
    junk_patterns = [
        r"without additional explanation.*",
        r"translation only.*",
        r"rules:.*",
        r"説明なし.*",
        r"注釈なし.*"
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    # 针对字段类型做细化清洗
    if field_type == "address":
        # 统一地址中的标点，移除多余空格
        text = text.replace("，", " ").replace(",", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
        # 针对日文地址：防止出现中文汉字（如果是中翻日）
        if target_lang == "ja":
            # 这是一个简单的提示，复杂的汉字转换需要更强的模型或专门的库
            pass

    elif field_type == "item_name":
        # 移除末尾常见的标点
        text = text.rstrip("。.;；!！")

    elif field_type == "person":
        # 移除人名后面模型爱加的称谓
        text = text.replace("様", "").replace("さん", "").strip()

    return text.strip()

async def _post_with_retry(client: httpx.AsyncClient, payload: dict) -> dict:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.post(
                f"{LLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
            )
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise httpx.HTTPStatusError(
                    f"Retryable upstream status: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, 
                httpx.RemoteProtocolError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * attempt)
    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {last_error}")

def _extract_content(data: dict) -> str:
    if "choices" in data and data["choices"]:
        choice = data["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return choice["message"]["content"]
        if "text" in choice:
            return choice["text"]
    if "content" in data:
        return data["content"]
    raise RuntimeError(f"Unexpected response format: {data}")

async def _translate_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    source_lang: str,
    target_lang: str,
    text: str,
    field_type: str,
) -> str:
    async with semaphore:
        clean_text = _truncate_text(text)
        if not clean_text:
            return ""
            
        prompt = _build_prompt(field_type, source_lang, target_lang, clean_text)

        payload = {
            "model": LLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.1,  # 降低随机性，提高地址稳定性
            "top_p": 0.9,
            "stop": ["\n", "Text:", "Task:"] # 强制停止符号，防止小模型多嘴
        }

        try:
            data = await _post_with_retry(client, payload)
            content = _extract_content(data)
            return _postprocess_translation(field_type, content, target_lang)
        except Exception as e:
            print(f"Error translating item '{text[:20]}...': {e}")
            return text # 失败时返回原词，防止生产线中断

async def translate_batch_via_llama(
    source_lang: str,
    target_lang: str,
    texts: List[str],
    field_types: List[str],
) -> List[str]:
    if len(texts) != len(field_types):
        raise ValueError("texts and field_types must have the same length")
    if not texts:
        return []
    if len(texts) > MAX_BATCH_ITEMS:
        raise ValueError(f"batch size exceeds limit: {MAX_BATCH_ITEMS}")

    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            _translate_one(client, semaphore, source_lang, target_lang, t, f)
            for t, f in zip(texts, field_types)
        ]
        translations = await asyncio.gather(*tasks)
    return list(translations)
