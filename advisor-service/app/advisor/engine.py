from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from app.advisor.data_loader import load_reference_data, freshness, ReferenceData
from app.advisor.risk import score_risk, questionnaire
from app.advisor.foundations import cash_flow, find_gaps, high_interest_debts
from app.advisor.goals import horizon_bucket, allocate
from app.advisor.products import (
    BASE_SMALL_SAVINGS,
    goal_instruments,
    fd_options_for_goal,
    emergency_products,
    eligible_schemes,
    tax_saving_options,
    build_fd_recommendations,
)


class AdvisorInputError(ValueError):
    """Raised when profile data fails validation."""
    pass


def inr(amount: float | int) -> str:
    """
    Format number in Indian numbering system: e.g. Rs 12,34,567
    """
    amt = int(round(amount))
    sign = "-" if amt < 0 else ""
    s = str(abs(amt))
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted = ",".join(groups) + "," + last3
    return f"{sign}Rs {formatted}"


def validate_profile(p: Dict[str, Any]) -> None:
    required = [
        "age",
        "monthly_income_inr",
        "monthly_expenses_inr",
        "emergency_fund_inr",
        "liabilities",
        "insurance",
        "dependents",
        "risk_answers",
    ]
    for r in required:
        if r not in p:
            raise AdvisorInputError(f"Missing required field: {r}")

    # Age 16-100
    age = p.get("age")
    if not isinstance(age, (int, float)) or not (16 <= age <= 100):
        raise AdvisorInputError("Age must be between 16 and 100")

    # Risk answers = five ints 1-4
    answers = p.get("risk_answers")
    if not isinstance(answers, list) or len(answers) != 5 or not all(isinstance(x, int) and 1 <= x <= 4 for x in answers):
        raise AdvisorInputError("risk_answers must be exactly five integers between 1 and 4")

    # Tax regime old/new
    tax_regime = p.get("tax_regime", "new")
    if tax_regime not in {"old", "new"}:
        raise AdvisorInputError("tax_regime must be 'old' or 'new'")

    # No negative money
    money_fields = ["monthly_income_inr", "other_monthly_inflow_inr", "monthly_expenses_inr", "emergency_fund_inr"]
    for mf in money_fields:
        if mf in p and p[mf] is not None and p[mf] < 0:
            raise AdvisorInputError(f"{mf} cannot be negative")

    insurance = p.get("insurance", {})
    if insurance.get("term_cover_inr", 0) < 0 or insurance.get("health_cover_inr", 0) < 0:
        raise AdvisorInputError("Insurance cover amounts cannot be negative")

    # Liabilities
    for l in p.get("liabilities", []):
        if l.get("outstanding_inr", 0) < 0 or l.get("emi_inr", 0) < 0:
            raise AdvisorInputError("Liability amounts cannot be negative")
        rate = l.get("interest_rate_pct", 0)
        if not (0 <= rate <= 60):
            raise AdvisorInputError("Interest rate must be between 0 and 60%")

    # Unique goal_ids & years > 0 and <= 50
    goals = p.get("goals", [])
    if len(goals) > 10:
        raise AdvisorInputError("A maximum of 10 goals is supported")

    goal_ids = set()
    for g in goals:
        gid = g.get("goal_id")
        if not gid or gid in goal_ids:
            raise AdvisorInputError(f"Goal ID '{gid}' is duplicated or empty")
        goal_ids.add(gid)

        years = g.get("years")
        if years is None or not (0 < years <= 50):
            raise AdvisorInputError("Goal years must be greater than 0 and up to 50")
        if g.get("target_inr", 0) < 0 or g.get("current_savings_inr", 0) < 0:
            raise AdvisorInputError("Goal amounts cannot be negative")


def core_assessment(p: Dict[str, Any]) -> Dict[str, Any]:
    validate_profile(p)
    ref = load_reference_data()
    cfg = ref.config

    flow = cash_flow(p)
    surplus = flow["surplus"]
    ef_months = flow["emergency_fund_months"]

    flags = find_gaps(p, flow, cfg)
    first_action = flags[0] if flags else "invest_for_goals"

    risk_info = score_risk(p["risk_answers"], p["age"], p["monthly_income_inr"], cfg)
    score = risk_info["score"]
    profile = risk_info["profile"]

    goals_out = []
    total_sip = 0
    for g in p.get("goals", []):
        alloc = allocate(g, profile, cfg)
        sip = alloc["required_monthly_sip_inr"]
        total_sip += sip
        goals_out.append({
            "goal_id": alloc["goal_id"],
            "bucket": alloc["bucket"],
            "equity_share_pct": alloc["equity_share_pct"],
            "required_monthly_sip_inr": sip,
        })

    eligible = list(BASE_SMALL_SAVINGS)
    if p["age"] >= cfg["eligibility"]["scss_min_age"]:
        eligible.append("scss")
    if p.get("daughters_under_10", 0) > 0:
        eligible.append("ssy")

    return {
        "monthly_surplus_inr": surplus,
        "emergency_fund_months": ef_months,
        "flags": flags,
        "first_action": first_action,
        "risk_score": score,
        "risk_profile": profile,
        "goals": goals_out,
        "total_required_monthly_sip_inr": total_sip,
        "goals_affordable": total_sip <= max(surplus, 0),
        "eligible_small_savings": eligible,
        "tax_saving_relevant": p.get("tax_regime") == "old",
    }


def build_plan(p: Dict[str, Any]) -> Dict[str, Any]:
    validate_profile(p)
    ref = load_reference_data()
    cfg = ref.config

    core = core_assessment(p)
    flow = cash_flow(p)

    target_months = cfg["emergency_fund"]["target_months"]
    ef_target = flow["outflow"] * target_months

    summary = {
        **core,
        "inflow_inr": flow["inflow"],
        "outflow_inr": flow["outflow"],
        "emergency_fund_target_inr": ef_target,
    }

    risk_info = score_risk(p["risk_answers"], p["age"], p["monthly_income_inr"], cfg)
    risk = {
        "score": risk_info["score"],
        "profile": risk_info["profile"],
        "questionnaire_profile": risk_info["questionnaire_profile"],
        "capped_by": risk_info["capped_by"],
    }

    # Goals detailed
    profile = risk_info["profile"]
    goals_detail = []
    for g in p.get("goals", []):
        alloc = allocate(g, profile, cfg)
        instruments = goal_instruments(g, alloc, profile, p, ref)
        fd_options = fd_options_for_goal(g, alloc, profile, p, ref)
        goals_detail.append({
            **alloc,
            "name": g.get("name", g["goal_id"]),
            "years": g["years"],
            "target_today_inr": g["target_inr"],
            "instruments": instruments,
            "fd_options": fd_options,
        })

    # Build action cards
    actions = []
    priority = 1
    flags = core["flags"]

    for flag in flags:
        status = "do_now" if priority == 1 else "next"
        if flag == "budget_deficit":
            deficit = abs(flow["surplus"])
            actions.append({
                "priority": priority,
                "code": "budget_deficit",
                "status": status,
                "title": f"Resolve Monthly Budget Deficit ({inr(deficit)}/month)",
                "amount_inr": deficit,
                "reasons": [
                    f"Your total monthly expenses ({inr(p['monthly_expenses_inr'])}) and loan EMIs ({inr(flow['emis'])}) exceed your monthly inflow ({inr(flow['inflow'])}).",
                    f"You have a recurring deficit of {inr(deficit)} every month, which will erode your savings or force costly debt.",
                    "Review discretionary spending and renegotiate loan terms immediately.",
                ],
                "products": [],
            })
        elif flag == "emergency_fund_critical":
            shortfall = max(0, (flow["outflow"] * cfg["emergency_fund"]["critical_months"]) - p["emergency_fund_inr"])
            actions.append({
                "priority": priority,
                "code": "emergency_fund_critical",
                "status": status,
                "title": f"Build Critical Emergency Fund (Have {flow['emergency_fund_months']} months, Need at least {cfg['emergency_fund']['critical_months']})",
                "amount_inr": shortfall,
                "reasons": [
                    f"You currently have {inr(p['emergency_fund_inr'])}, which covers only {flow['emergency_fund_months']} months of living expenses and EMIs.",
                    f"A critical cushion of at least {cfg['emergency_fund']['critical_months']} months ({inr(flow['outflow'] * cfg['emergency_fund']['critical_months'])}) is vital before investing or aggressive debt repayment.",
                    f"Direct savings towards a liquid buffer to close the {inr(shortfall)} gap.",
                ],
                "products": emergency_products(ref),
            })
        elif flag == "emergency_fund_gap":
            shortfall = max(0, ef_target - p["emergency_fund_inr"])
            actions.append({
                "priority": priority,
                "code": "emergency_fund_gap",
                "status": status,
                "title": f"Reach Target Emergency Fund ({target_months} Months Cushion)",
                "amount_inr": shortfall,
                "reasons": [
                    f"You have {flow['emergency_fund_months']} months of expenses ({inr(p['emergency_fund_inr'])}) in emergency savings.",
                    f"The full safety target is {target_months} months of outflows ({inr(ef_target)}).",
                    f"Add {inr(shortfall)} in liquid instruments to achieve full peace of mind.",
                ],
                "products": emergency_products(ref),
            })
        elif flag == "high_interest_debt":
            debts = high_interest_debts(p, cfg)
            total_debt_amount = sum(d.get("outstanding_inr", 0) for d in debts)
            payoff_order = [d.get("type", "loan") for d in debts]
            actions.append({
                "priority": priority,
                "code": "high_interest_debt",
                "status": status,
                "title": f"Eliminate High-Interest Debt ({inr(total_debt_amount)} Outstanding)",
                "amount_inr": total_debt_amount,
                "reasons": [
                    f"You are carrying debt at or above {cfg['debt']['high_interest_threshold_pct']}% interest rate.",
                    f"Aggressively pay off using the Avalanche method: {', '.join(payoff_order)}.",
                    "Prepaying expensive loans provides a guaranteed post-tax return equal to the loan interest rate.",
                ],
                "payoff_order": payoff_order,
                "products": [],
            })
        elif flag == "health_insurance_gap":
            min_health = cfg["insurance"]["min_health_cover_inr"]
            curr_health = p.get("insurance", {}).get("health_cover_inr", 0)
            shortfall = max(0, min_health - curr_health)
            actions.append({
                "priority": priority,
                "code": "health_insurance_gap",
                "status": status,
                "title": f"Secure Adequate Health Insurance Cover (Target {inr(min_health)})",
                "amount_inr": shortfall,
                "reasons": [
                    f"Your existing health insurance cover is {inr(curr_health)}.",
                    f"Medical inflation in India requires a baseline family cover of at least {inr(min_health)}.",
                    "A single hospitalization without adequate cover can wipe out months of investment gains.",
                ],
                "products": [],
            })
        elif flag == "term_insurance_gap":
            mult = cfg["insurance"]["term_cover_multiple_of_annual_income"]
            ann_inc = p.get("monthly_income_inr", 0) * 12
            target_term = mult * ann_inc
            curr_term = p.get("insurance", {}).get("term_cover_inr", 0)
            shortfall = max(0, target_term - curr_term)
            actions.append({
                "priority": priority,
                "code": "term_insurance_gap",
                "status": status,
                "title": f"Protect Dependents with Pure Term Life Cover ({mult}x Annual Income: {inr(target_term)})",
                "amount_inr": shortfall,
                "reasons": [
                    f"You have {p.get('dependents')} financial dependent(s) and {inr(curr_term)} in existing term cover.",
                    f"With an annual income of {inr(ann_inc)}, your income replacement requirement is {inr(target_term)} ({mult}x income).",
                    f"Purchase a pure term insurance policy for the shortfall of {inr(shortfall)} to ensure your family's future is secure.",
                ],
                "products": [],
            })

        priority += 1

    # Invest for goals action if goals exist
    if p.get("goals"):
        status = "do_now" if priority == 1 else "next"
        total_sip = core["total_required_monthly_sip_inr"]
        affordable = core["goals_affordable"]

        reasons = [
            f"Your goals require a combined monthly investment (SIP) of {inr(total_sip)}.",
            f"Your current monthly surplus is {inr(flow['surplus'])}.",
        ]
        if not affordable:
            reasons.append(
                f"Your required SIP ({inr(total_sip)}) exceeds your monthly surplus ({inr(flow['surplus'])}). "
                "Consider extending your timeline, reducing the target amount, or funding your highest-priority goal first."
            )
        else:
            reasons.append(
                f"Your monthly surplus fully covers the required SIP with {inr(flow['surplus'] - total_sip)} remaining as cushion."
            )

        actions.append({
            "priority": priority,
            "code": "invest_for_goals",
            "status": status,
            "title": f"Automate Monthly Investments for Goals ({inr(total_sip)}/month)",
            "amount_inr": total_sip,
            "reasons": reasons,
            "products": [],
        })

    return {
        "summary": summary,
        "risk": risk,
        "actions": actions,
        "goals": goals_detail,
        "fd_recommendations": build_fd_recommendations(p, profile, ref),
        "eligible_small_savings": eligible_schemes(p, ref),
        "tax_saving": tax_saving_options(p, ref),
        "assumptions": cfg["planning_assumptions"],
        "data_freshness": freshness(),
        "disclaimer": cfg["disclaimer"],
    }
