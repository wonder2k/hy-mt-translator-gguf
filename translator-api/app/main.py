from fastapi import FastAPI, HTTPException
from .models import TranslateRequest, TranslateResponse
from .translator_client import translate_batch_via_llama

app = FastAPI(title="HY-MT1.5 GGUF Translator API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/translate-batch", response_model=TranslateResponse)
async def translate_batch(req: TranslateRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    texts = [i.text for i in req.items]
    field_types = [i.field_type or "generic" for i in req.items]

    translations = await translate_batch_via_llama(
        req.source_lang,
        req.target_lang,
        texts,
        field_types,
    )
    return TranslateResponse(translations=translations)
