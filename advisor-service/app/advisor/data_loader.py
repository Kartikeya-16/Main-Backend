from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass(frozen=True)
class ReferenceData:
    config: Dict[str, Any]
    fd_rates: List[Dict[str, Any]]
    small_savings: Dict[str, Dict[str, Any]]
    instruments: Dict[str, Dict[str, Any]]
    fd_as_of: date
    small_savings_quarter: str
    small_savings_valid_to: date


def _get_data_dir() -> Path:
    env_dir = os.environ.get("ADVISOR_DATA_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    # default to <advisor-service>/data
    return Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def load_reference_data() -> ReferenceData:
    data_dir = _get_data_dir()
    ref_dir = data_dir / "reference"

    # 1. Config
    with open(ref_dir / "rules_config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 2. FD Rates
    fd_rates: List[Dict[str, Any]] = []
    latest_fd_as_of: date = date.min
    with open(ref_dir / "fd_rates.csv", "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed_row: Dict[str, Any] = dict(row)
            # Parse numbers
            if row.get("tenure_years"):
                parsed_row["tenure_years"] = float(row["tenure_years"])
            else:
                parsed_row["tenure_years"] = None

            parsed_row["rate_general_pct"] = float(row["rate_general_pct"])
            parsed_row["rate_senior_pct"] = float(row["rate_senior_pct"])
            parsed_row["lock_in_years"] = float(row["lock_in_years"]) if row.get("lock_in_years") else 0.0
            parsed_row["tax_deduction_eligible"] = row.get("tax_deduction_eligible", "").lower() == "true"
            parsed_row["dicgc_cover_inr"] = int(row["dicgc_cover_inr"]) if row.get("dicgc_cover_inr") else 500000

            as_of = date.fromisoformat(row["as_of_date"])
            parsed_row["as_of_date"] = as_of
            if as_of > latest_fd_as_of:
                latest_fd_as_of = as_of

            fd_rates.append(parsed_row)

    # 3. Small Savings
    small_savings: Dict[str, Dict[str, Any]] = {}
    quarter = ""
    valid_to: date = date.min
    with open(ref_dir / "small_savings.csv", "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed_row = dict(row)
            parsed_row["rate_pct"] = float(row["rate_pct"])
            parsed_row["tenure_years"] = float(row["tenure_years"]) if row.get("tenure_years") else None
            parsed_row["lock_in_years"] = float(row["lock_in_years"]) if row.get("lock_in_years") else 0.0
            parsed_row["min_amount_inr"] = float(row["min_amount_inr"]) if row.get("min_amount_inr") else None
            parsed_row["max_amount_inr"] = float(row["max_amount_inr"]) if row.get("max_amount_inr") else None
            parsed_row["tax_deduction_eligible"] = row.get("tax_deduction_eligible", "").lower() == "true"
            parsed_row["interest_taxable"] = row.get("interest_taxable", "").lower() == "true"
            parsed_row["sovereign_backed"] = row.get("sovereign_backed", "").lower() == "true"

            v_to = date.fromisoformat(row["valid_to"])
            parsed_row["valid_to"] = v_to
            if v_to > valid_to:
                valid_to = v_to
            quarter = row.get("quarter", quarter)

            small_savings[row["scheme_id"]] = parsed_row

    # 4. Instrument Categories
    instruments: Dict[str, Dict[str, Any]] = {}
    with open(ref_dir / "instrument_categories.csv", "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed_row = dict(row)
            parsed_row["min_horizon_years"] = float(row["min_horizon_years"]) if row.get("min_horizon_years") else 0.0
            parsed_row["risk_level"] = int(row["risk_level"]) if row.get("risk_level") else 1
            parsed_row["assumed_return_low_pct"] = float(row["assumed_return_low_pct"]) if row.get("assumed_return_low_pct") else None
            parsed_row["assumed_return_high_pct"] = float(row["assumed_return_high_pct"]) if row.get("assumed_return_high_pct") else None
            parsed_row["lock_in_years"] = float(row["lock_in_years"]) if row.get("lock_in_years") else 0.0
            parsed_row["tax_deduction_eligible"] = row.get("tax_deduction_eligible", "").lower() == "true"

            instruments[row["category_id"]] = parsed_row

    return ReferenceData(
        config=cfg,
        fd_rates=fd_rates,
        small_savings=small_savings,
        instruments=instruments,
        fd_as_of=latest_fd_as_of,
        small_savings_quarter=quarter,
        small_savings_valid_to=valid_to,
    )


def freshness(today: date | None = None) -> Dict[str, Any]:
    if today is None:
        today = date.today()
    ref = load_reference_data()

    fd_age_days = (today - ref.fd_as_of).days
    stale = (fd_age_days > 45) or (today > ref.small_savings_valid_to)

    return {
        "fd_rates_as_of": ref.fd_as_of.isoformat(),
        "small_savings_quarter": ref.small_savings_quarter,
        "small_savings_valid_to": ref.small_savings_valid_to.isoformat(),
        "stale": stale,
    }
