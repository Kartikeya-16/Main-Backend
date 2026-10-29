from __future__ import annotations

from typing import Any, Dict, List, Optional


def cash_flow(p: Dict[str, Any]) -> Dict[str, Any]:
    emis = sum(l.get("emi_inr", 0) for l in p.get("liabilities", []))
    inflow = p.get("monthly_income_inr", 0) + p.get("other_monthly_inflow_inr", 0)
    outflow = p.get("monthly_expenses_inr", 0) + emis
    surplus = inflow - outflow

    emergency_fund = p.get("emergency_fund_inr", 0)
    emergency_fund_months = round(emergency_fund / outflow, 1) if outflow > 0 else None

    return {
        "emis": emis,
        "inflow": inflow,
        "outflow": outflow,
        "surplus": surplus,
        "emergency_fund_months": emergency_fund_months,
    }


def find_gaps(p: Dict[str, Any], flow: Dict[str, Any], cfg: Dict[str, Any]) -> List[str]:
    surplus = flow["surplus"]
    ef_months = flow["emergency_fund_months"]
    liabilities = p.get("liabilities", [])
    insurance = p.get("insurance", {})

    found = set()
    if surplus < 0:
        found.add("budget_deficit")

    crit_months = cfg["emergency_fund"]["critical_months"]
    target_months = cfg["emergency_fund"]["target_months"]
    if ef_months is not None and ef_months < crit_months:
        found.add("emergency_fund_critical")
    elif ef_months is not None and ef_months < target_months:
        found.add("emergency_fund_gap")

    high_int_thresh = cfg["debt"]["high_interest_threshold_pct"]
    if any(l.get("interest_rate_pct", 0) >= high_int_thresh for l in liabilities):
        found.add("high_interest_debt")

    min_health = cfg["insurance"]["min_health_cover_inr"]
    if insurance.get("health_cover_inr", 0) < min_health:
        found.add("health_insurance_gap")

    term_multiple = cfg["insurance"]["term_cover_multiple_of_annual_income"]
    annual_income = p.get("monthly_income_inr", 0) * 12
    need_term = insurance.get("term_cover_inr", 0) < (term_multiple * annual_income)
    if p.get("dependents", 0) > 0 and need_term:
        found.add("term_insurance_gap")

    # Return in cfg action_priority order
    return [f for f in cfg["action_priority"] if f in found]


def high_interest_debts(p: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    thresh = cfg["debt"]["high_interest_threshold_pct"]
    debts = [l for l in p.get("liabilities", []) if l.get("interest_rate_pct", 0) >= thresh]
    # Avalanche order: highest interest rate first
    return sorted(debts, key=lambda d: d.get("interest_rate_pct", 0), reverse=True)
