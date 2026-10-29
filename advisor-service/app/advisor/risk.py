from __future__ import annotations

from typing import Any, Dict, List, Optional

RISK_ORDER = ["conservative", "moderate", "aggressive"]


def score_risk(
    answers: List[int],
    age: int,
    monthly_income: float,
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    rq = cfg["risk_questionnaire"]
    score = sum(answers)

    # Determine band from score
    questionnaire_profile = next(
        name for name, b in rq["bands"].items() if b["min"] <= score <= b["max"]
    )
    profile = questionnaire_profile
    capped_by: Optional[str] = None

    # Check caps in order
    if monthly_income == 0:
        profile = rq["caps"]["no_income"]
        capped_by = "no_income"
    elif age >= 60 and RISK_ORDER.index(profile) > RISK_ORDER.index(rq["caps"]["age_60_plus"]):
        profile = rq["caps"]["age_60_plus"]
        capped_by = "age_60_plus"

    return {
        "score": score,
        "questionnaire_profile": questionnaire_profile,
        "profile": profile,
        "capped_by": capped_by,
    }


def questionnaire(cfg: Dict[str, Any]) -> Dict[str, Any]:
    rq = cfg["risk_questionnaire"]
    return {
        "questions": rq["questions"],
        "bands": rq["bands"],
        "caps": rq["caps"],
    }
