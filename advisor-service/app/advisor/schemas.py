from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class LiabilityInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    outstanding_inr: float = Field(ge=0)
    interest_rate_pct: float = Field(ge=0, le=60)
    emi_inr: float = Field(ge=0)


class InsuranceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    term_cover_inr: float = Field(ge=0, default=0.0)
    health_cover_inr: float = Field(ge=0, default=0.0)


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal_id: str
    name: str
    target_inr: float = Field(ge=0)
    years: float = Field(gt=0, le=50)
    current_savings_inr: float = Field(ge=0, default=0.0)
    for_daughter: bool = False


class AdvisorProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    age: int = Field(ge=16, le=100)
    monthly_income_inr: float = Field(ge=0)
    other_monthly_inflow_inr: float = Field(ge=0, default=0.0)
    monthly_expenses_inr: float = Field(ge=0)
    emergency_fund_inr: float = Field(ge=0)
    liabilities: List[LiabilityInput] = Field(default_factory=list)
    insurance: InsuranceInput = Field(default_factory=InsuranceInput)
    dependents: int = Field(ge=0, default=0)
    daughters_under_10: int = Field(ge=0, default=0)
    tax_regime: Literal["old", "new"] = "new"
    goals: List[GoalInput] = Field(default_factory=list, max_length=10)
    risk_answers: List[int] = Field(min_length=5, max_length=5)
