import os
import re
import asyncio
from typing import List
import httpx

LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://host.docker.internal:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "HY-MT1.5-1.8B-Q4_K_M.gguf")

MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "160"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "48"))
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
    if field_type == "address":
        return f"""Translate the following address into Japanese, without additional explanation.

{text}"""

    if field_type == "item_name":
        return f"""Translate the following product name into Japanese, without additional explanation.

{text}"""

    if field_type == "person":
        return f"""Translate the following name into Japanese, without additional explanation.

{text}"""

    return f"""Translate the following segment into Japanese, without additional explanation.

{text}"""


def _extract_content(data: dict) -> str:
    if "choices" in data and data["choices"]:
        choice = data["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return choice["message"]["content"]
        if "text" in choice:
            return choice["text"]
    if "content" in data:
        return data["content"]
    raise RuntimeError(f"Unexpected llama response format: {data}")


def _postprocess_translation(field_type: str, text: str) -> str:
    text = _normalize_whitespace(text)
    text = text.strip(' "\'')

    prefixes = [
        "翻译：",
        "译文：",
        "Translation:",
        "Translated text:",
        "Japanese:",
        "日本語:",
    ]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    junk_markers = [
        "ルール：",
        "説明なしで",
        "翻訳された住所のみ",
        "項目名を翻訳しただけ",
        "マーケティング用の表現ではなく",
        "without additional explanation",
        "do not add explanation",
    ]
    if any(marker in text for marker in junk_markers):
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            text = lines[-1]

    if field_type == "address":
        text = text.replace("，", " ").replace(",", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()

    elif field_type == "item_name":
        text = text.rstrip("。.;；")

    elif field_type == 
