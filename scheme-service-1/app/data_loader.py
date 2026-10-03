"""
Loads finpilot_schemes_enriched.csv into memory once at startup and
pre-parses the JSON-string columns (eligibility_caste, eligibility_caste_extended,
eligibility_state) so the matcher never has to touch pandas/json parsing
on the request path.

In-memory by design (no DB table, no per-request disk I/O). Acceptable at
~4.9k rows / ~18MB; if the dataset grows an order of magnitude, revisit and
move to CockroachDB.
"""
import json
import os
from functools import lru_cache
from typing import Any, List

import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "finpilot_schemes_enriched.csv")

BOOL_COLS = ["eligibility_disability", "eligibility_bpl", "eligibility_minority", "eligibility_student"]
JSON_ARRAY_COLS = ["eligibility_caste", "eligibility_caste_extended", "eligibility_state"]


def _safe_json_list(value: Any) -> List[str]:
    if pd.isna(value):
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _safe_bool(value: Any) -> Any:
    """Cast True/False/'True'/'False'/NaN to a real bool, or None if unknown."""
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


@lru_cache(maxsize=1)
def load_schemes() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, engine="python", on_bad_lines="warn")

    for col in JSON_ARRAY_COLS:
        if col in df.columns:
            df[col] = df[col].apply(_safe_json_list)

    for col in BOOL_COLS:
        if col in df.columns:
            df[col] = df[col].apply(_safe_bool)

    df["eligibility_gender"] = df["eligibility_gender"].fillna("all").str.strip().str.lower()
    df["eligibility_residence"] = df["eligibility_residence"].fillna("both").str.strip().str.lower()
    df["state"] = df["state"].fillna("Central").str.strip()
    df["category"] = df["category"].fillna("").str.strip()
    df["beneficiary_type"] = df["beneficiary_type"].fillna("").str.strip()

    if "apply_url_clean" not in df.columns:
        df["apply_url_clean"] = df["apply_url"]

    return df


def reload_schemes() -> pd.DataFrame:
    """Clears the cache and reloads from disk. Useful after a data refresh."""
    load_schemes.cache_clear()
    return load_schemes()
