import os
import re
from typing import List
import httpx

LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://host.docker.internal:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "HY-MT1.5-1.8B-Q4_K_M.gguf")

MAX_INPUT_CHARS = 160
MAX_OUTPUT_TOKENS = 80


def _truncate_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:MAX_INPUT_CHARS]


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _postprocess_translation(field_type: str, text: str) -> str:
    text = _normalize_whitespace(text)

    # 去掉模型偶尔附带的引号
    text = text.strip(' "\'')

    # 去掉常见多余前缀
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
        # 地址尽量单行、减少多余标点
        text = text.replace("，", " ").replace(",", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()

    elif field_type == "item_name":
        # 品名不希望带句号或解释尾巴
        text = text.rstrip("。.;；")

    elif field_type == "person":
        # 人名通常不希望带额外称呼
        text = text.replace("様", "").replace("さん", "").strip()

    return text


def _build_prompt(field_type: str, source_lang: str, target_lang: str, text: str) -> str:
    """
    针对物流字段做 prompt 优化。
    当前主要目标：英文 -> 日文。
    """

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


async def translate_batch_via_llama(
    source_lang: str,
    target_lang: str,
    texts: List[str],
    field_types: List[str],
) -> List[str]:
    translations: List[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
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

            resp = await client.post(
                f"{LLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()

            data = resp.json()

            # 兼容 llama.cpp OpenAI 风格返回
            content = ""
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                elif "text" in choice:
                    content = choice["text"]

            translations.append(_postprocess_translation(field_type, content))

    return translations
