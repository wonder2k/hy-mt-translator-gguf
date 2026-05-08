import os
import re
import asyncio
from typing import List
import httpx

# ================= 配置区 =================
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

# ================= 辅助函数 =================

def _truncate_text(text: str) -> str:
    return text.strip()[:MAX_INPUT_CHARS] if text else ""

def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def _build_prompt(field_type: str, source_lang: str, target_lang: str, text: str) -> str:
    """
    采用更强硬的 Instruction-Following 格式。
    Source/Target 标签能有效防止 1.8B 小模型直接复读原文。
    """
    lang_map = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}
    src = lang_map.get(source_lang, source_lang)
    tgt = lang_map.get(target_lang, target_lang)

    if field_type == "address":
        return f"""Instruction: Translate the {src} address into {tgt} Kanji. 
Rules: Use {tgt} address format (Big-to-Small). No English.

Example:
Source: 1-1-1 Chiyoda, Chiyoda-ku, Tokyo
Target: 〒100-0001 東京都千代田区千代田1-1-1

Source: {text}
Target:"""

    if field_type == "item_name":
        return f"""Instruction: Translate the product name from {src} to {tgt}.
Rules: Output ONLY the translated name.

Source: {text}
Target:"""

    return f"""Instruction: Translate from {src} to {tgt}.
Source: {text}
Target:"""

def _postprocess_translation(field_type: str, text: str) -> str:
    """
    清洗模型可能输出的残留标签或解释。
    """
    text = _normalize_whitespace(text)
    # 移除引号和可能残留的引导词
    text = text.strip(' "\'「」')
    
    # 清理模型可能因为 stop 没触发而输出的多余行
    if "\n" in text:
        text = text.split("\n")[0]

    # 针对地址的最终格式化
    if field_type == "address":
        text = text.replace(",", " ").replace("，", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
    
    elif field_type == "item_name":
        text = text.rstrip("。.;；!！")

    return text.strip()

# ================= 核心逻辑 =================

async def _post_with_retry(client: httpx.AsyncClient, payload: dict) -> dict:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.post(
                f"{LLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
            )
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise httpx.HTTPStatusError(f"Status: {response.status_code}", request=response.request, response=response)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * attempt)
    raise RuntimeError(f"Llama request failed: {last_error}")

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
        if not clean_text: return ""
            
        prompt = _build_prompt(field_type, source_lang, target_lang, clean_text)

        payload = {
            "model": LLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.0, # 必须
