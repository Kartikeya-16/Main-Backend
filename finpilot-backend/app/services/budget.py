from typing import List, Dict, Any, Optional

# Expense categories that represent essential "Needs"
NEED_EXPENSE_CATEGORIES = {
    "HOUSING",
    "FOOD",
    "UTILITIES",
    "TRANSPORT",
    "EDUCATION",
    "INSURANCE",
    "HEALTH",
}

# Expense categories that represent discretionary "Wants"
WANT_EXPENSE_CATEGORIES = {
    "ENTERTAINMENT",
    "SHOPPING",
    "TRAVEL",
    "VACATION",
    "OTHER",
}


def calculate_budget_allocation(
    monthly_income: float,
    expenses: Optional[List[Dict[str, Any]]] = None,
    liabilities: Optional[List[Dict[str, Any]]] = None,
    raw_needs: Optional[float] = None,
    raw_wants: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculates the 50/30/20 budget breakdown (Needs, Wants, Savings).
    Guarantees:
    - needs + wants + savings == monthly_income
    - needs_pct + wants_pct + savings_pct == 100.0%
    - If needs + wants > monthly_income, savings is negative (deficit) with is_deficit=True.
    """
    income = float(monthly_income) if monthly_income > 0 else 1.0

    if expenses is not None or liabilities is not None:
        expenses = expenses or []
        liabilities = liabilities or []

        needs_total = 0.0
        wants_total = 0.0

        for exp in expenses:
            amt = float(exp.get("amount", 0.0))
            cat = str(exp.get("category", "")).upper()
            if cat in WANT_EXPENSE_CATEGORIES:
                wants_total += amt
            else:
                # Default essential or unclassified to Needs
                needs_total += amt

        for lia in liabilities:
            emi = float(lia.get("emi_amount", 0.0) or 0.0)
            needs_total += emi

        needs = needs_total
        wants = wants_total
    else:
        needs = float(raw_needs) if raw_needs is not None else income * 0.50
        wants = float(raw_wants) if raw_wants is not None else income * 0.30

    savings = income - needs - wants
    is_deficit = savings < 0

    needs_pct = round((needs / income) * 100.0, 2)
    wants_pct = round((wants / income) * 100.0, 2)
    # Ensure total percentages sum exactly to 100.0%
    savings_pct = round(100.0 - (needs_pct + wants_pct), 2)

    needs_target = round(income * 0.50, 2)
    wants_target = round(income * 0.30, 2)
    savings_target = round(income * 0.20, 2)

    return {
        "monthly_income": income,
        "needs": round(needs, 2),
        "wants": round(wants, 2),
        "savings": round(savings, 2),
        "needs_pct": needs_pct,
        "wants_pct": wants_pct,
        "savings_pct": savings_pct,
        "needs_target": needs_target,
        "wants_target": wants_target,
        "savings_target": savings_target,
        "is_deficit": is_deficit,
        "deficit_amount": round(abs(savings), 2) if is_deficit else 0.0,
    }
