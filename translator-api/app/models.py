from pydantic import BaseModel, Field
from typing import List, Optional


class TranslateItem(BaseModel):
    text: str = Field(..., description="待翻译文本")
    field_type: Optional[str] = Field(
        default="generic",
        description="字段类型：address/item_name/person/generic",
    )


class TranslateRequest(BaseModel):
    source_lang: str
    target_lang: str
    items: List[TranslateItem]


class TranslateResponse(BaseModel):
    translations: List[str]
