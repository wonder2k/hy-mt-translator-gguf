from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from app.models import TranslateRequest, TranslateResponse
from app.translator_client import translate_batch_via_llama

app = FastAPI(
    title="HY-MT Translator API",
    version="1.0.0",
    description="Local translation API powered by llama.cpp + HY-MT1.5 GGUF",
)


def utf8_json_response(content: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=content,
        status_code=status_code,
        media_type="application/json; charset=utf-8",
    )


@app.get("/health")
async def health():
    return utf8_json_response({"status": "ok"})


@app.post("/translate-batch", response_model=TranslateResponse)
async def translate_batch(req: TranslateRequest,
                         _: str = Depends(verify_api_key):
    try:
        texts = [item.text for item in req.items]
        field_types = [item.field_type or "generic" for item in req.items]

        translations = await translate_batch_via_llama(
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            texts=texts,
            field_types=field_types,
        )

        return utf8_json_response(
            {"translations": translations},
            status_code=200,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"translation failed: {str(exc)}")
