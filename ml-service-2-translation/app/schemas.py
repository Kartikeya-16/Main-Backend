from pydantic import BaseModel, Field
from typing import List

class TranslateRequest(BaseModel):
    text: str = Field(..., description="The text to translate")
    src_lang: str = Field("eng_Latn", description="Source language code (FLORES-200)", example="eng_Latn")
    tgt_lang: str = Field("hin_Deva", description="Target language code (FLORES-200)", example="hin_Deva")

class TranslateResponse(BaseModel):
    translated_text: str
    src_lang: str
    tgt_lang: str

class BatchTranslateRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to translate")
    src_lang: str = Field("eng_Latn", description="Source language code (FLORES-200)", example="eng_Latn")
    tgt_lang: str = Field("hin_Deva", description="Target language code (FLORES-200)", example="hin_Deva")

class BatchTranslateResponse(BaseModel):
    translated_texts: List[str]
    src_lang: str
    tgt_lang: str
