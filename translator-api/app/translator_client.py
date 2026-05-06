import os
import re
import asyncio
from typing import List
import httpx

LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://host.docker.internal:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "HY-MT1.5-1.8B-Q4_K_M.gguf")

MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "160"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "80"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_DELAY_SECONDS = float(os.getenv("RETRY_BASE_DELAY_SECONDS", "0.8"))
MAX_BATCH_ITEMS = int(os.getenv("MAX_BATCH_ITEMS", "50"))

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

    if field_type == "address":
        text = text.replace("，", " ").replace(",", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
    elif field_type == "item_name":
        text = text.rstrip("。.;；")
    elif field_type == "person":
        text = text.replace("様", "").replace("さん", "").strip()

    return text


def _build_prompt(field_type: str, source_lang: str, target_lang: str, text: str) -> str:
    if field_type == "address":
        return f"""Translate the following delivery address into Japanese for logistics use.
Rules:
- Output only the translated address, with no explanation.
- Preserve numbers, postal codes, room numbers, block numbers, and building identifiers accurately.
- Keep the address concise and suitable for shipping labels.
- Do not invent missing prefecture, city, or postal code information.
- If a part is better kept in Latin letters or numbers, keep it.

{text}"""

    if field_type == "item_name":
        return f"""Translate the following product/item name into Japanese for logistics and customs use.
Rules:
- Output only the translated item name, with no explanation.
- Use a specific and practical product description, not marketing wording.
- Preserve brand, model, capacity, size, color, and quantity expressions when present.
- Keep it concise and label-friendly.

{text}"""

    if field_type == "person":
        return f"""Translate the following person's name into Japanese for shipping documents.
Rules:
- Output only the translated name, with no explanation.
- Do not add honorifics such as 様.
- Keep the result stable and concise.
- If the original form is better preserved in Latin letters, keep it.

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

        except (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * attempt)

    raise RuntimeError(
        f"llama-server request failed after {MAX_RETRIES} attempts: {last_error}"
    )


async def translate_batch_via_llama(
    source_lang: str,
    target_lang: str,
    texts: List[str],
    field_types: List[str],
) -> List[str]:
    if len(texts) != len(field_types):
        raise ValueError("texts and field_types must have the same length")

    if len(texts) > MAX_BATCH_ITEMS:
        raise ValueError(f"batch size exceeds limit: {MAX_BATCH_ITEMS}")

    translations: List[str] = []

    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for text, field_type in zip(texts, field_types):
            clean_text = _truncate_text(text)
            prompt = _build_prompt(field_type, source_lang, target_lang, clean_text)

            payload = {
                "model": LLAMA_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "max_tokens": MAX_OUTPUT_TOKENS,
                "temperature": 0.2,
                "top_p": 0.9,
            }

            data = await _post_with_retry(client, payload)
            content = _extract_content(data)
            translations.append(_postprocess_translation(field_type, content))

    return translations
