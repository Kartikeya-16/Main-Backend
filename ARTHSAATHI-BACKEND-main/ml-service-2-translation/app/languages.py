from typing import Tuple

# FLORES-200 code map for English + 22 scheduled Indian languages
LANGUAGES = {
    "eng_Latn": "English",
    "asm_Beng": "Assamese",
    "ben_Beng": "Bengali",
    "brx_Deva": "Bodo",
    "doi_Deva": "Dogri",
    "guj_Gujr": "Gujarati",
    "hin_Deva": "Hindi",
    "kan_Knda": "Kannada",
    "kas_Arab": "Kashmiri",
    "kok_Deva": "Konkani",
    "mai_Deva": "Maithili",
    "mal_Mlym": "Malayalam",
    "mni_Beng": "Manipuri",
    "mar_Deva": "Marathi",
    "npi_Deva": "Nepali",
    "ory_Orya": "Odia",
    "pan_Guru": "Punjabi",
    "san_Deva": "Sanskrit",
    "sat_Olck": "Santali",
    "snd_Arab": "Sindhi",
    "tam_Taml": "Tamil",
    "tel_Telu": "Telugu",
    "urd_Arab": "Urdu",
}

EN_INDIC_MODEL = "prajdabre/rotary-indictrans2-en-indic-dist-200M"
INDIC_EN_MODEL = "prajdabre/rotary-indictrans2-indic-en-dist-200M"
INDIC_INDIC_MODEL = "ai4bharat/indictrans2-indic-indic-dist-320M"

# Open mirrors mapping
MIRROR_MODELS = {
    "ai4bharat/indictrans2-en-indic-dist-200M": "prajdabre/rotary-indictrans2-en-indic-dist-200M",
    "ai4bharat/indictrans2-indic-en-dist-200M": "prajdabre/rotary-indictrans2-indic-en-dist-200M",
}



def route_translation_model(src_lang: str, tgt_lang: str) -> str:
    """
    Determines which model to use based on source and target languages.
    If src_lang is English -> use en-indic model.
    If tgt_lang is English -> use indic-en model.
    If both are Indic -> use indic-indic model.
    
    Raises ValueError if languages are unsupported or identical.
    """
    if src_lang not in LANGUAGES:
        raise ValueError(f"Unsupported source language: {src_lang}")
    if tgt_lang not in LANGUAGES:
        raise ValueError(f"Unsupported target language: {tgt_lang}")
    if src_lang == tgt_lang:
        raise ValueError("Source and target languages must be different.")

    if src_lang == "eng_Latn":
        return EN_INDIC_MODEL
    elif tgt_lang == "eng_Latn":
        return INDIC_EN_MODEL
    else:
        return INDIC_INDIC_MODEL
