"""Validate the Financial Advisor reference data and golden personas.

Run from the advisor-service folder:

    python tools/validate_datasets.py            # check everything
    python tools/validate_datasets.py --regen    # rewrite personas.json "expected" blocks

The `evaluate()` function below is the reference implementation of the rules in
rules_config.yaml. The real advisor engine must produce the same outputs for every
persona; pytest can import `evaluate` and `load_all` from this file to check that.
Only use --regen on purpose (for example after changing a threshold), then review
the diff by hand.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
FIX = ROOT / "data" / "fixtures"

RISK_ORDER = ["conservative", "moderate", "aggressive"]
BASE_SMALL_SAVINGS = ["posa", "potd_1y", "potd_2y", "potd_3y", "potd_5y", "rd_5y", "pomis", "nsc", "ppf", "kvp"]


# ------------------------------------------------------------------ loading
def read_csv(name: str) -> list[dict]:
    with open(REF / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_all() -> dict:
    with open(REF / "rules_config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(FIX / "personas.json", encoding="utf-8") as f:
        personas = json.load(f)
    return {
        "config": cfg,
        "fd_rates": read_csv("fd_rates.csv"),
        "small_savings": read_csv("small_savings.csv"),
        "instruments": read_csv("instrument_categories.csv"),
        "personas": personas,
    }


# ------------------------------------------------------------------ reference rules
def risk_profile(p: dict, cfg: dict) -> tuple[int, str]:
    rq = cfg["risk_questionnaire"]
    answers = p["risk_answers"]
    score = sum(answers)
    profile = next(name for name, b in rq["bands"].items() if b["min"] <= score <= b["max"])
    if p["monthly_income_inr"] == 0:
        profile = rq["caps"]["no_income"]
    if p["age"] >= 60 and RISK_ORDER.index(profile) > RISK_ORDER.index(rq["caps"]["age_60_plus"]):
        profile = rq["caps"]["age_60_plus"]
    return score, profile


def horizon_bucket(years: float) -> str:
    if years < 3:
        return "short"
    if years <= 5:
        return "medium"
    return "long"


def required_monthly_sip(goal: dict, equity_pct: int, cfg: dict) -> int:
    a = cfg["planning_assumptions"]
    years = goal["years"]
    future_target = goal["target_inr"] * (1 + a["inflation_pct"] / 100) ** years
    r = (equity_pct * a["equity_return_pct"] + (100 - equity_pct) * a["debt_return_pct"]) / 10000
    grown_savings = goal.get("current_savings_inr", 0) * (1 + r) ** years
    gap = max(0.0, future_target - grown_savings)
    if gap == 0:
        return 0
    i, m = r / 12, round(years * 12)
    sip = gap * i / ((1 + i) ** m - 1)
    return max(math.ceil(sip), a["min_monthly_sip_inr"])


def evaluate(p: dict, cfg: dict) -> dict:
    emis = sum(l["emi_inr"] for l in p["liabilities"])
    inflow = p["monthly_income_inr"] + p.get("other_monthly_inflow_inr", 0)
    surplus = inflow - p["monthly_expenses_inr"] - emis
    outflow = p["monthly_expenses_inr"] + emis
    ef_months = round(p["emergency_fund_inr"] / outflow, 1) if outflow > 0 else None

    found = set()
    if surplus < 0:
        found.add("budget_deficit")
    if ef_months is not None and ef_months < cfg["emergency_fund"]["critical_months"]:
        found.add("emergency_fund_critical")
    elif ef_months is not None and ef_months < cfg["emergency_fund"]["target_months"]:
        found.add("emergency_fund_gap")
    if any(l["interest_rate_pct"] >= cfg["debt"]["high_interest_threshold_pct"] for l in p["liabilities"]):
        found.add("high_interest_debt")
    if p["insurance"]["health_cover_inr"] < cfg["insurance"]["min_health_cover_inr"]:
        found.add("health_insurance_gap")
    need_term = p["insurance"]["term_cover_inr"] < cfg["insurance"]["term_cover_multiple_of_annual_income"] * p["monthly_income_inr"] * 12
    if p["dependents"] > 0 and need_term:
        found.add("term_insurance_gap")
    flags = [f for f in cfg["action_priority"] if f in found]

    score, profile = risk_profile(p, cfg)
    goals_out, total_sip = [], 0
    for g in p["goals"]:
        bucket = horizon_bucket(g["years"])
        eq = cfg["equity_share_pct"][bucket][profile]
        sip = required_monthly_sip(g, eq, cfg)
        total_sip += sip
        goals_out.append({"goal_id": g["goal_id"], "bucket": bucket, "equity_share_pct": eq, "required_monthly_sip_inr": sip})

    eligible = list(BASE_SMALL_SAVINGS)
    if p["age"] >= cfg["eligibility"]["scss_min_age"]:
        eligible.append("scss")
    if p.get("daughters_under_10", 0) > 0:
        eligible.append("ssy")

    return {
        "monthly_surplus_inr": surplus,
        "emergency_fund_months": ef_months,
        "flags": flags,
        "first_action": flags[0] if flags else "invest_for_goals",
        "risk_score": score,
        "risk_profile": profile,
        "goals": goals_out,
        "total_required_monthly_sip_inr": total_sip,
        "goals_affordable": total_sip <= max(surplus, 0),
        "eligible_small_savings": eligible,
        "tax_saving_relevant": p["tax_regime"] == "old",
    }


# ------------------------------------------------------------------ schema checks
def check_reference(data: dict) -> list[str]:
    errs = []
    today = date.today()
    fd_cols = {"bank_id", "bank_name", "bank_type", "product", "tenure_bucket", "tenure_years", "rate_general_pct",
               "rate_senior_pct", "lock_in_years", "tax_deduction_eligible", "dicgc_cover_inr", "source_url", "as_of_date"}
    if not fd_cols <= set(data["fd_rates"][0]):
        errs.append(f"fd_rates.csv missing columns: {fd_cols - set(data['fd_rates'][0])}")
    seen = set()
    for i, r in enumerate(data["fd_rates"], start=2):
        key = (r["bank_id"], r["product"], r["tenure_bucket"])
        if key in seen:
            errs.append(f"fd_rates.csv line {i}: duplicate {key}")
        seen.add(key)
        if r["bank_type"] not in {"psu", "private", "sfb"}:
            errs.append(f"fd_rates.csv line {i}: bad bank_type {r['bank_type']}")
        g, s = float(r["rate_general_pct"]), float(r["rate_senior_pct"])
        if not (2.0 <= g <= 10.0 and 2.0 <= s <= 10.0):
            errs.append(f"fd_rates.csv line {i}: rate out of range")
        if s < g:
            errs.append(f"fd_rates.csv line {i}: senior rate below general rate")
        if r["product"] == "tax_saver" and (r["lock_in_years"] != "5" or r["tax_deduction_eligible"] != "true"):
            errs.append(f"fd_rates.csv line {i}: tax saver must be 5-year lock-in and deduction eligible")
        if (today - date.fromisoformat(r["as_of_date"])).days > 45:
            errs.append(f"fd_rates.csv line {i}: rates older than 45 days - refresh")
    for bank in {r["bank_id"] for r in data["fd_rates"]}:
        rows = {r["tenure_bucket"]: float(r["rate_general_pct"]) for r in data["fd_rates"] if r["bank_id"] == bank and r["product"] == "regular"}
        if rows["best_slab"] < max(rows["1y"], rows["3y"], rows["5y"]):
            errs.append(f"fd_rates.csv: {bank} best_slab lower than a listed tenure")

    for i, r in enumerate(data["small_savings"], start=2):
        if not (3.0 <= float(r["rate_pct"]) <= 10.0):
            errs.append(f"small_savings.csv line {i}: rate out of range")
        if date.fromisoformat(r["valid_to"]) < today:
            errs.append(f"small_savings.csv line {i}: quarter expired on {r['valid_to']} - refresh")
    ids = {r["scheme_id"] for r in data["small_savings"]}
    missing = set(BASE_SMALL_SAVINGS + ["scss", "ssy"]) - ids
    if missing:
        errs.append(f"small_savings.csv missing schemes: {missing}")

    for i, r in enumerate(data["instruments"], start=2):
        src = r["return_source"]
        if src == "assumption":
            lo, hi = float(r["assumed_return_low_pct"]), float(r["assumed_return_high_pct"])
            if lo > hi:
                errs.append(f"instrument_categories.csv line {i}: low > high")
        elif src not in {"fd_rates.csv", "small_savings.csv"}:
            errs.append(f"instrument_categories.csv line {i}: unknown return_source {src}")

    cfg = data["config"]
    bands = cfg["risk_questionnaire"]["bands"]
    covered = sorted(n for b in bands.values() for n in range(b["min"], b["max"] + 1))
    if covered != list(range(5, 21)):
        errs.append("rules_config.yaml: risk bands must cover scores 5-20 exactly once")
    if cfg["emergency_fund"]["critical_months"] >= cfg["emergency_fund"]["target_months"]:
        errs.append("rules_config.yaml: critical_months must be below target_months")
    return errs


def check_personas(data: dict) -> list[str]:
    errs = []
    cfg = data["config"]
    ids = set()
    for p in data["personas"]["personas"]:
        pid = p["persona_id"]
        if pid in ids:
            errs.append(f"duplicate persona_id {pid}")
        ids.add(pid)
        a = p["risk_answers"]
        if len(a) != 5 or not all(1 <= x <= 4 for x in a):
            errs.append(f"{pid}: risk_answers must be five values from 1 to 4")
        got = evaluate(p, cfg)
        exp = p.get("expected")
        if exp is None:
            errs.append(f"{pid}: missing expected block")
        elif got != exp:
            diff = {k: (exp.get(k), got[k]) for k in got if exp.get(k) != got[k]}
            errs.append(f"{pid}: expected != computed {diff}")
    return errs


def main() -> int:
    data = load_all()
    if "--regen" in sys.argv:
        for p in data["personas"]["personas"]:
            p["expected"] = evaluate(p, data["config"])
        with open(FIX / "personas.json", "w", encoding="utf-8") as f:
            json.dump(data["personas"], f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("personas.json expected blocks regenerated - review the diff before committing")
    errs = check_reference(data) + check_personas(data)
    for e in errs:
        print("FAIL", e)
    n = len(data["personas"]["personas"])
    print(f"{len(data['fd_rates'])} FD rows, {len(data['small_savings'])} schemes, "
          f"{len(data['instruments'])} instrument categories, {n} personas")
    print("OK" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
