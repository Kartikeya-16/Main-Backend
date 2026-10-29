from __future__ import annotations

import math
from typing import Any, Dict


def horizon_bucket(years: float) -> str:
    if years < 3:
        return "short"
    if years <= 5:
        return "medium"
    return "long"


def allocate(goal: Dict[str, Any], profile: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    a = cfg["planning_assumptions"]
    years = float(goal["years"])
    bucket = horizon_bucket(years)
    eq_pct = cfg["equity_share_pct"][bucket][profile]

    inflation = a["inflation_pct"] / 100.0
    future_target = goal["target_inr"] * ((1.0 + inflation) ** years)

    eq_ret = a["equity_return_pct"]
    debt_ret = a["debt_return_pct"]
    r = (eq_pct * eq_ret + (100 - eq_pct) * debt_ret) / 10000.0

    current_savings = goal.get("current_savings_inr", 0)
    grown_savings = current_savings * ((1.0 + r) ** years)

    gap = max(0.0, future_target - grown_savings)
    if gap == 0.0:
        sip = 0
    else:
        i = r / 12.0
        m = round(years * 12.0)
        sip_val = gap * i / (((1.0 + i) ** m) - 1.0)
        sip = max(math.ceil(sip_val), a["min_monthly_sip_inr"])

    # Split monthly sip into equity and debt
    if sip == 0:
        equity_split = 0
        debt_split = 0
    else:
        equity_split = round(sip * eq_pct / 100.0)
        debt_split = sip - equity_split

    return {
        "goal_id": goal["goal_id"],
        "bucket": bucket,
        "equity_share_pct": eq_pct,
        "required_monthly_sip_inr": sip,
        "inflated_target_inr": round(future_target),
        "expected_return_pct": round(r * 100.0, 2),
        "split_monthly_inr": {
            "equity": equity_split,
            "debt": debt_split,
        },
    }
