"""
Pydantic models for the Scheme Generator microservice.

These mirror the multi-step wizard fields (gender, age, state,
residence, caste, disability, minority, student, BPL, income) plus the
derived/enriched fields added to the dataset (eligibility_minority,
eligibility_student, eligibility_caste_extended).
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Input payload built from the multi-step onboarding form."""

    gender: Literal["male", "female", "transgender"]
    age: int = Field(..., ge=0, le=120)

    state: Optional[str] = None  # None/omitted -> only "Central" + no-state-restriction schemes
    residence: Literal["urban", "rural"]

    # NOTE: dataset only has SC/ST/OBC/General as *original* structured values.
    # PVTG and DNT are supported via the enriched eligibility_caste_extended column.
    caste: Literal["General", "OBC", "SC", "ST", "PVTG", "DNT"]

    disability: bool = False
    minority: bool = False

    is_student: bool = False

    bpl: bool = False
    annual_income: Optional[float] = Field(
        None, ge=0, description="Combined household income used against eligibility_income_max"
    )
    applying_for_family: bool = Field(
        False, description="True if the user is applying on behalf of their household/family, not just themselves"
    )
    occupation: Optional[str] = Field(
        None, description="User's occupation title (e.g. Software Engineer, Farmer, Teacher)"
    )
    occupation_type: Optional[str] = Field(
        None, description="Type of occupation (SALARIED, BUSINESS, SELF_EMPLOYED, STUDENT, RETIRED, OTHER)"
    )


class MatchedScheme(BaseModel):
    slug: str
    name: str
    category: str
    state: str
    description: str
    benefits: str
    apply_url: Optional[str] = None
    official_url: Optional[str] = None

    match_score: float = Field(..., description="0-100 relevance score")
    match_confidence: Literal["high", "medium", "low"] = Field(
        ...,
        description=(
            "high = has_structured_eligibility True and all hard filters explicitly matched. "
            "medium = structured eligibility missing/partial, matched via soft/text signals. "
            "low = fell back almost entirely on category/keyword overlap."
        ),
    )
    matched_criteria: List[str] = Field(default_factory=list)
    documents_required: Optional[str] = None
    application_process: Optional[str] = None
    eligibility_text: Optional[str] = None
    ministry: Optional[str] = None
    department: Optional[str] = None
    beneficiary_type: Optional[str] = None
    tags: Optional[str] = None


class MatchResponse(BaseModel):
    total_matches: int
    results: List[MatchedScheme]


class HealthResponse(BaseModel):
    status: str
    schemes_loaded: int
