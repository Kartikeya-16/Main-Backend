from pydantic import BaseModel, Field
from typing import List


class GoalInput(BaseModel):
    target_amount: float = Field(..., ge=0.0)
    current_savings: float = Field(..., ge=0.0)


class HealthScoreRequest(BaseModel):
    monthly_income: float = Field(..., ge=0.0)
    total_monthly_emis: float = Field(..., ge=0.0)
    total_monthly_expenses: float = Field(..., ge=0.0)
    liquid_savings: float = Field(..., ge=0.0)
    total_assets: float = Field(..., ge=0.0)
    total_liabilities: float = Field(..., ge=0.0)
    goals: List[GoalInput]


class FeatureImportance(BaseModel):
    emi_to_income_ratio: float
    savings_rate: float
    emergency_fund_months: float
    expense_to_income_ratio: float
    asset_to_liability_ratio: float
    goal_progress_avg: float


class HealthScoreResponse(BaseModel):
    health_score: float
    category: str
    feature_importance: FeatureImportance
    insights: List[str]
    model_version: str = "1.0.0"

    model_config = {
        "protected_namespaces": ()
    }

