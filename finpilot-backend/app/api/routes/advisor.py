from __future__ import annotations

from datetime import date
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.models.financial_twin import (
    FinancialTwin,
    Income,
    Expense,
    Asset,
    Liability,
    FinancialGoal,
    AssetType,
    FrequencyType,
)
from app.services.microservice_client import (
    advisor_questionnaire,
    advisor_meta,
    advisor_plan,
)

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get("/questionnaire")
async def get_advisor_questionnaire(
    current_user: User = Depends(get_current_user),
):
    """
    Proxies request to advisor-service GET /advisor/questionnaire.
    Requires authenticated user.
    """
    return await advisor_questionnaire()


@router.get("/meta")
async def get_advisor_meta(
    current_user: User = Depends(get_current_user),
):
    """
    Proxies request to advisor-service GET /advisor/meta.
    Requires authenticated user.
    """
    return await advisor_meta()


@router.post("/plan")
async def post_advisor_plan(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    Proxies request to advisor-service POST /advisor/plan.
    Requires authenticated user.
    """
    return await advisor_plan(payload)


def _convert_frequency_to_monthly(amount: float, frequency: FrequencyType | str) -> float:
    freq_str = frequency.value if isinstance(frequency, FrequencyType) else str(frequency).upper()
    if freq_str == "MONTHLY":
        return amount
    elif freq_str == "WEEKLY":
        return amount * 52.0 / 12.0
    elif freq_str == "ANNUAL":
        return amount / 12.0
    elif freq_str == "ONE_TIME":
        return 0.0
    return amount


@router.get("/profile-draft")
async def get_advisor_profile_draft(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Builds an advisor profile draft from the current user's Financial Twin.
    Pre-fills income, expenses, liquid emergency funds, liabilities, and goals.
    """
    twin = db.query(FinancialTwin).filter(FinancialTwin.user_id == current_user.id).first()
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create your Financial Twin first",
        )

    incomes = db.query(Income).filter(Income.user_id == current_user.id).all()
    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    assets = db.query(Asset).filter(Asset.user_id == current_user.id).all()
    liabilities = db.query(Liability).filter(Liability.user_id == current_user.id).all()
    goals = db.query(FinancialGoal).filter(FinancialGoal.user_id == current_user.id).all()

    # 1. Income conversion to monthly
    monthly_income = 0.0
    for inc in incomes:
        amt = float(inc.amount or 0.0)
        monthly_income += _convert_frequency_to_monthly(amt, inc.frequency)

    # If twin has monthly_income and no itemized incomes, fallback to twin.monthly_income
    if monthly_income == 0.0 and twin.monthly_income:
        monthly_income = float(twin.monthly_income)

    # 2. Expenses conversion to monthly
    monthly_expenses = 0.0
    for exp in expenses:
        amt = float(exp.amount or 0.0)
        monthly_expenses += _convert_frequency_to_monthly(amt, exp.frequency)

    # 3. Emergency fund = sum of liquid assets only (SAVINGS, FIXED_DEPOSIT)
    # AssetType: SAVINGS, FIXED_DEPOSIT, STOCKS, MUTUAL_FUNDS, REAL_ESTATE, VEHICLE, GOLD, CRYPTO, OTHER
    liquid_types = {AssetType.SAVINGS, AssetType.FIXED_DEPOSIT}
    emergency_fund = 0.0
    for ast in assets:
        ast_type = ast.asset_type
        if ast_type in liquid_types or str(ast_type).upper() in {"SAVINGS", "FIXED_DEPOSIT"}:
            emergency_fund += float(ast.current_value or 0.0)

    # 4. Liabilities mapping
    liabilities_list = []
    for lia in liabilities:
        lia_type_val = lia.liability_type.value if hasattr(lia.liability_type, "value") else str(lia.liability_type).lower()
        liabilities_list.append({
            "type": lia_type_val,
            "outstanding_amount": float(lia.outstanding_amount or 0.0),
            "interest_rate": float(lia.interest_rate or 0.0),
            "emi_amount": float(lia.emi_amount or 0.0),
            # Also keep advisor service schema keys for compatibility if needed
            "outstanding_inr": float(lia.outstanding_amount or 0.0),
            "interest_rate_pct": float(lia.interest_rate or 0.0),
            "emi_inr": float(lia.emi_amount or 0.0),
        })

    # 5. Goals mapping
    today = date.today()
    goals_list = []
    skipped_goals = []

    for g in goals:
        g_name = g.title or "Goal"
        t_date = g.target_date

        if t_date is None:
            skipped_goals.append({
                "goal_id": str(g.id),
                "name": g_name,
                "reason": "Missing target date",
            })
            continue

        if t_date <= today:
            skipped_goals.append({
                "goal_id": str(g.id),
                "name": g_name,
                "reason": "Target date is in the past",
            })
            continue

        # Compute years until target date
        days = (t_date - today).days
        years = round(days / 365.25, 2)
        if years <= 0:
            skipped_goals.append({
                "goal_id": str(g.id),
                "name": g_name,
                "reason": "Target date evaluates to 0 years",
            })
            continue

        for_daughter = "daughter" in g_name.lower() or "daughter" in str(g.goal_type).lower()

        goals_list.append({
            "goal_id": str(g.id),
            "name": g_name,
            "target_amount": float(g.target_amount or 0.0),
            "target_inr": float(g.target_amount or 0.0),
            "years": years,
            "current_savings": float(g.current_savings or 0.0),
            "current_savings_inr": float(g.current_savings or 0.0),
            "for_daughter": for_daughter,
        })

    # Twin demographics that might map directly
    age_val = twin.age if twin.age else None
    dependents_val = twin.dependents_count if twin.dependents_count is not None else 0

    # Source map tracks which fields originated from the Financial Twin
    source_map: Dict[str, str] = {}
    if age_val is not None:
        source_map["age"] = "twin"
    if dependents_val is not None:
        source_map["dependents"] = "twin"
    if monthly_income > 0.0 or (twin.monthly_income and float(twin.monthly_income) > 0.0):
        source_map["monthly_income_inr"] = "twin"
    if monthly_expenses > 0.0:
        source_map["monthly_expenses_inr"] = "twin"
    if emergency_fund > 0.0:
        source_map["emergency_fund_inr"] = "twin"
    if len(liabilities_list) > 0:
        source_map["liabilities"] = "twin"
    if len(goals_list) > 0:
        source_map["goals"] = "twin"

    # Twin gaps: helpful warnings when the Twin lacks essential planning data
    twin_gaps = []
    if monthly_income <= 0.0 and (not twin.monthly_income or float(twin.monthly_income) <= 0.0):
        twin_gaps.append({
            "field": "monthly_income_inr",
            "message": "No income streams recorded in your Financial Twin.",
            "link": "/twin",
        })
    if monthly_expenses <= 0.0:
        twin_gaps.append({
            "field": "monthly_expenses_inr",
            "message": "No monthly living expenses recorded in your Financial Twin.",
            "link": "/twin",
        })
    if emergency_fund <= 0.0:
        twin_gaps.append({
            "field": "emergency_fund_inr",
            "message": "No liquid cash or savings accounts found in your Financial Twin assets.",
            "link": "/twin",
        })
    if len(goals_list) == 0:
        twin_gaps.append({
            "field": "goals",
            "message": "No active future financial goals defined in your Financial Twin.",
            "link": "/twin",
        })

    profile_draft = {
        "age": age_val,
        "monthly_income_inr": round(monthly_income, 2),
        "other_monthly_inflow_inr": 0.0,
        "monthly_expenses_inr": round(monthly_expenses, 2),
        "emergency_fund_inr": round(emergency_fund, 2),
        "liabilities": liabilities_list,
        "insurance": {
            "term_cover_inr": 0.0,
            "health_cover_inr": 0.0,
        },
        "dependents": dependents_val,
        "daughters_under_10": 0,
        "tax_regime": "new",
        "goals": goals_list,
        "risk_answers": [],
    }

    missing_fields = [
        "age" if age_val is None else None,
        "daughters_under_10",
        "insurance",
        "tax_regime",
        "risk_answers",
    ]
    missing_fields = [m for m in missing_fields if m is not None]

    twin_updated_at = twin.updated_at.isoformat() if twin.updated_at else None

    return {
        "profile": profile_draft,
        "missing_fields": missing_fields,
        "skipped_goals": skipped_goals,
        "source": source_map,
        "twin_gaps": twin_gaps,
        "twin_updated_at": twin_updated_at,
    }
