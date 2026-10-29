from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from app.advisor.data_loader import load_reference_data, freshness
from app.advisor.risk import questionnaire
from app.advisor.engine import build_plan, AdvisorInputError
from app.advisor.schemas import AdvisorProfile

router = APIRouter(prefix="/advisor", tags=["Financial Advisor"])


@router.get("/questionnaire")
def get_questionnaire():
    """
    Returns the 5-question risk questionnaire, score bands, and capping rules.
    """
    ref = load_reference_data()
    return questionnaire(ref.config)


@router.get("/meta")
def get_metadata():
    """
    Returns data freshness info, planning assumptions, and disclaimer.
    """
    ref = load_reference_data()
    return {
        "data_freshness": freshness(),
        "assumptions": ref.config["planning_assumptions"],
        "disclaimer": ref.config["disclaimer"],
    }


@router.post("/plan")
def generate_plan(profile: AdvisorProfile):
    """
    Generates a personalized financial foundation and investment allocation plan.
    """
    try:
        # Convert Pydantic model to dictionary
        p_dict = profile.model_dump()
        return build_plan(p_dict)
    except AdvisorInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
