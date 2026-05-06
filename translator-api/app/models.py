from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


FieldType = Literal["address", "item_name", "person", "generic"]


class TranslateItem(BaseModel):
    text: str = Field(..., description="Original text to translate")
    field_type: Optional[FieldType] = Field(
        default="generic",
        description="Field type for translation strategy",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if value is None:
            raise ValueError("text is required")
        value = value.strip()
        if not value:
            raise ValueError("text must not be empty")
        return value


class TranslateRequest(BaseModel):
    source_lang: str = Field(..., description="Source language code, e.g. en")
    target_lang: str = Field(..., description="Target language code, e.g. ja")
    items: List[TranslateItem] = Field(..., description="Items to translate")

    @field_validator("source_lang", "target_lang")
    @classmethod
    def validate_lang(cls, value: str) -> str:
        if value is None:
            raise ValueError("language code is required")
        value = value.strip()
        if not value:
            raise ValueError("language code must not be empty")
        return value

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: List[TranslateItem]) -> List[TranslateItem]:
        if not value:
            raise ValueError("items must not be empty")
        return value


class TranslateResponse(BaseModel):
    translations: List[str] = Field(..., description="Translated texts in the same order")
