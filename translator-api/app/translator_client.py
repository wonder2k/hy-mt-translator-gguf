import os
import re
import asyncio
from typing import List
import httpx

# 配置
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://host.docker.internal:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "HY-MT1.5-1.8B-Q4_K_M.gguf")

MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "160"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "64"))
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
    lang_map = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}
    src = lang_map.get(source_lang, source_lang)
    tgt = lang_map.get(target_lang, target_lang)

    # 地址翻译：增加 Few-shot 强制纠正语序和汉字使用
    if field_type == "address":
        return f"""Task: Translate {src} address to {tgt}.
Rules: Use {tgt} formal format. No Romaji/Pinyin. Output only the result.

Example (English to Japanese):
Input: 2-8-1 Nishishinjuku, Shinjuku-ku, Tokyo 163-8001
Output: 〒163-8001 東京都新宿区西新宿2-8-1

Input: {text}
Output:"""

    # 物品品名：侧重简洁
    if field_type == "item_name":
        return f"""Task: Translate product name from {src} to {tgt}.
Example: 
Input: Apple iPhone Case
Output: Apple iPhoneケース

Input: {text}
Output:"""

    # 姓名/通用
    if field_type == "person":
        return f"""Translate the person's name from {src} to {tgt}: {text}\nOutput:"""

    return f"""Translate from {src} to {tgt}: {text}\nOutput:"""

def _postprocess_translation(field_type: str, text: str, target_lang: str) -> str:
    text = _normalize_whitespace(text)
    text = text.strip(' "\'「」')

    # 清除常见的引导词
    prefixes = ["翻译：", "译文：", "结果：", "Translation:", "Output:", "日本語:", "〒"]
    for prefix in prefixes:
        if text.lower().startswith(prefix.lower()):
            if prefix == "〒": # 邮编符号保留
                break
            text = text[len(prefix):].lstrip(":： ").strip()

    # 清洗地址中的逗号
    if field_type == "address":
        text = text.replace(",", " ").replace("，", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
        
    elif field_type == "item_name":
        text = text.rstrip("。.;；!！")

    return text

async def _post_with_retry(client: httpx.AsyncClient, payload: dict) -> dict:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.post(f"{LLAMA_BASE_URL}/v1/chat/completions", json=payload)
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise httpx.HTTPStatusError(f"Retryable status: {response.status_code}", request=response.request, response=response)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.HTTPStatusError) as exc:
            last_error = exc
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * attempt)
    raise RuntimeError(f"Request failed: {last_error}")

async def _translate_one(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, source_lang: str, target_lang: str, text: str, field_type: str) -> str:
    async with semaphore:
        clean_text = _truncate_text(text)
        if not clean_text: return ""
            
        prompt = _build_prompt(field_type, source_lang, target_lang, clean_text)

        payload = {
            "model": LLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.0,  # 强制最高确定性，解决音译乱跑问题
            "top_p": 1.0,
            "stop": ["\n", "Input:", "Task:"] # 遇到这些字符立即停止，防止模型多嘴
        }

        try:
            data = await _post_with_retry(client, payload)
            content = data["choices"][0]["message"]["content"]
            return _postprocess_translation(field_type, content, target_lang)
        except Exception as e:
            return text # 降级处理：返回原文

async def translate_batch_via_llama(source_lang: str, target_lang: str, texts: List[str], field_types: List[str]) -> List[str]:
    if len(texts) != len(field_types): raise ValueError("Mismatch length")
    if not texts: return []
    
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [_translate_one(client, semaphore, source_lang, target_lang, t, f) for t, f in zip(texts, field_types)]
        return list(await asyncio.gather(*tasks))
