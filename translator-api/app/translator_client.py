import os
from typing import List
import httpx

LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://llama-server:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "hy-mt1.5-1.8b-q4_k_m.gguf")

# 长度限制（字符数），可根据业务调整
MAX_INPUT_CHARS = 128   # 单条输入最大长度
MAX_OUTPUT_TOKENS = 64  # 最大输出 token 数，控制输出长度


def _build_prompt(field_type: str, source_lang: str, target_lang: str, text: str) -> str:
    """
    根据字段类型构造更贴近业务的 prompt。
    当前主要场景：EN -> JA。
    """
    # 这里简单写死成日文说明，你以后可以根据 source_lang / target_lang 再细分
    if field_type == "address":
        base = (
            "Translate the following address into Japanese, keeping the address structure "
            "and abbreviations natural for Japanese usage. Do not add explanations."
        )
    elif field_type == "item_name":
        base = (
            "Translate the following product name into Japanese suitable for logistics "
            "and customs documents. Do not add explanations."
        )
    elif field_type == "person":
        base = (
            "Translate the following person's name into Japanese. "
            "Use common Japanese conventions and do not add explanations."
        )
    else:
        base = (
            "Translate the following segment into Japanese, without additional explanation."
        )

    # 可以加上源语言和目标语言信息，但对 HY-MT1.5 这种翻译专模来说不是硬性要求
    return f"{base}\n\n{text}"


async def translate_batch_via_llama(
    source_lang: str,
    target_lang: str,
    texts: List[str],
    field_types: List[str],
) -> List[str]:
    """
    调用 llama-server 的 /v1/chat/completions 接口逐条翻译。
    如果未来要提高吞吐量，可改为并发请求或 continuous batching。
    """
    truncated_texts = [t[:MAX_INPUT_CHARS] for t in texts]

    translations: List[str] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for text, field_type in zip(truncated_texts, field_types):
            prompt = _build_prompt(field_type, source_lang, target_lang, text)
            payload = {
                "model": LLAMA_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "max_tokens": MAX_OUTPUT_TOKENS,
                "temperature": 0.7,
                "top_p": 0.6,
            }
            resp = await client.post(
                f"{LLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            translations.append(content.strip())

    return translations
