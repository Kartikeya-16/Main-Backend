from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.advisor.data_loader import ReferenceData

BASE_SMALL_SAVINGS = [
    "posa",
    "potd_1y",
    "potd_2y",
    "potd_3y",
    "potd_5y",
    "rd_5y",
    "pomis",
    "nsc",
    "ppf",
    "kvp",
]


def fd_tenure_for(years: float) -> str:
    if years < 3:
        return "1y"
    elif years < 5:
        return "3y"
    else:
        return "5y"


def top_fds(
    ref: ReferenceData,
    tenure: str,
    senior: bool,
    profile: str,
    n: int = 3,
    product: str = "regular",
) -> List[Dict[str, Any]]:
    rate_key = "rate_senior_pct" if senior else "rate_general_pct"

    # Filter matching product and tenure
    matching = [
        r for r in ref.fd_rates
        if r["product"] == product and r["tenure_bucket"] == tenure
    ]

    # Conservative excludes SFB
    if profile == "conservative":
        matching = [r for r in matching if r["bank_type"] != "sfb"]

    # Sort descending by rate, tie-break by general rate
    sorted_fds = sorted(matching, key=lambda x: (x[rate_key], x["rate_general_pct"]), reverse=True)

    picks = sorted_fds[:n]

    # If all n picks are sfb (only possible if conservative wasn't applied), swap the last one for best large bank
    if len(picks) == n and all(p["bank_type"] == "sfb" for p in picks):
        large_banks = [r for r in sorted_fds if r["bank_type"] in {"psu", "private"}]
        if large_banks:
            picks[-1] = large_banks[0]

    # Add DICGC note for SFB items
    result = []
    for p in picks:
        item = dict(p)
        if item["bank_type"] == "sfb":
            item["note"] = "Small Finance Bank: keep deposit within Rs 5,00,000 DICGC insurance limit per depositor."
        result.append(item)

    return result


def goal_instruments(
    goal: Dict[str, Any],
    alloc: Dict[str, Any],
    profile: str,
    p: Dict[str, Any],
    ref: ReferenceData,
) -> List[Dict[str, Any]]:
    instruments = []
    eq_pct = alloc["equity_share_pct"]
    bucket = alloc["bucket"]
    years = float(goal["years"])
    tax_regime = p.get("tax_regime", "new")
    daughters_under_10 = p.get("daughters_under_10", 0)
    for_daughter = goal.get("for_daughter") or ("daughter" in goal.get("goal_id", "").lower()) or ("daughter" in goal.get("name", "").lower())

    # 1. Equity part (only if equity share > 0)
    if eq_pct > 0:
        if bucket == "medium":
            instruments.append("balanced_advantage_fund")
            if profile == "aggressive":
                instruments.append("index_fund_large_cap")
        elif bucket == "long":
            instruments.append("index_fund_large_cap")
            if profile == "aggressive":
                instruments.append("flexi_cap_fund")
            if tax_regime == "old":
                instruments.append("elss_fund")
            if profile != "conservative":
                instruments.append("gold_etf")

    # 2. Debt part
    if bucket == "short":
        if years < 1.0:
            instruments.append("liquid_fund")
            instruments.append("bank_fd")
            instruments.append("post_office_td")
        else:
            instruments.append("bank_fd")
            instruments.append("post_office_td")
            instruments.append("short_duration_debt_fund")
    elif bucket == "medium":
        instruments.append("bank_fd")
        instruments.append("post_office_td")
        instruments.append("short_duration_debt_fund")
        if tax_regime == "old" and years >= 5.0:
            instruments.append("nsc_certificate")
    elif bucket == "long":
        if for_daughter and daughters_under_10 > 0:
            instruments.append("ssy_account")
        if years >= 15.0:
            instruments.append("ppf_account")
        else:
            instruments.append("bank_fd")
            instruments.append("short_duration_debt_fund")

    # Map category_ids to structured items
    out = []
    seen = set()
    for cat_id in instruments:
        if cat_id in seen:
            continue
        seen.add(cat_id)
        cat_meta = ref.instruments.get(cat_id, {})
        item: Dict[str, Any] = {
            "category_id": cat_id,
            "name": cat_meta.get("category_name", cat_id),
            "role": cat_meta.get("asset_class", "debt"),
            "reason": cat_meta.get("use_for", ""),
        }
        if cat_meta.get("return_source") == "assumption":
            lo = cat_meta.get("assumed_return_low_pct")
            hi = cat_meta.get("assumed_return_high_pct")
            if lo is not None and hi is not None:
                item["assumed_return_pct"] = round((lo + hi) / 2.0, 2)
        out.append(item)

    return out


def fd_options_for_goal(
    goal: Dict[str, Any],
    alloc: Dict[str, Any],
    profile: str,
    p: Dict[str, Any],
    ref: ReferenceData,
) -> Dict[str, Any]:
    years = float(goal["years"])
    tenure = fd_tenure_for(years)
    senior = p.get("age", 0) >= 60

    picks = top_fds(ref=ref, tenure=tenure, senior=senior, profile=profile, n=3, product="regular")

    # Check DICGC cover note: inflated_target * debt share > DICGC cover
    dicgc_cover = ref.config["deposit_safety"]["dicgc_cover_inr"]
    debt_share_pct = 100 - alloc["equity_share_pct"]
    debt_target = alloc["inflated_target_inr"] * debt_share_pct / 100.0

    dicgc_note = None
    if debt_target > dicgc_cover:
        dicgc_note = (
            f"Debt target of Rs {int(debt_target):,} exceeds the Rs 5,00,000 DICGC insurance cover. "
            f"Spread across multiple banks to keep each deposit within Rs 5,00,000."
        )

    return {
        "tenure": tenure,
        "top_fds": picks,
        "dicgc_note": dicgc_note,
    }


def emergency_products(ref: ReferenceData) -> List[Dict[str, Any]]:
    cats = ["savings_account", "liquid_fund", "bank_fd"]
    out = []
    for c in cats:
        meta = ref.instruments.get(c, {})
        out.append({
            "category_id": c,
            "name": meta.get("category_name", c),
            "role": meta.get("asset_class", "cash"),
            "reason": meta.get("use_for", ""),
        })
    return out


def eligible_schemes(p: Dict[str, Any], ref: ReferenceData) -> List[Dict[str, Any]]:
    eligible_ids = list(BASE_SMALL_SAVINGS)
    if p.get("age", 0) >= ref.config["eligibility"]["scss_min_age"]:
        eligible_ids.append("scss")
    if p.get("daughters_under_10", 0) > 0:
        eligible_ids.append("ssy")

    out = []
    for sid in eligible_ids:
        s = ref.small_savings.get(sid, {})
        out.append({
            "scheme_id": sid,
            "name": s.get("scheme_name", sid),
            "rate_pct": s.get("rate_pct"),
            "lock_in_years": s.get("lock_in_years"),
            "tax_deduction_eligible": s.get("tax_deduction_eligible"),
            "interest_taxable": s.get("interest_taxable"),
            "sovereign_backed": s.get("sovereign_backed"),
        })
    return out


def tax_saving_options(p: Dict[str, Any], ref: ReferenceData) -> Optional[Dict[str, Any]]:
    if p.get("tax_regime") != "old":
        return None

    cfg_tax = ref.config["tax"]
    section_name = cfg_tax["deduction_section"]
    limit_inr = cfg_tax["deduction_limit_inr"]

    senior = p.get("age", 0) >= 60
    options: List[Dict[str, Any]] = []

    # 1. SSY first if eligible
    if p.get("daughters_under_10", 0) > 0:
        ssy = ref.small_savings.get("ssy", {})
        options.append({
            "instrument": "ssy_account",
            "name": ssy.get("scheme_name", "Sukanya Samriddhi Yojana"),
            "rate_pct": ssy.get("rate_pct", 8.2),
            "lock_in_years": ssy.get("lock_in_years", 21.0),
            "why": "Highest sovereign rate, dedicated for daughter, interest and maturity completely tax-free.",
        })

    # 2. PPF
    ppf = ref.small_savings.get("ppf", {})
    options.append({
        "instrument": "ppf_account",
        "name": ppf.get("scheme_name", "Public Provident Fund"),
        "rate_pct": ppf.get("rate_pct", 7.1),
        "lock_in_years": ppf.get("lock_in_years", 15.0),
        "why": "Exempt-Exempt-Exempt (EEE) sovereign tax status, ideal debt anchor for long retirement.",
    })

    # 3. ELSS
    elss = ref.instruments.get("elss_fund", {})
    options.append({
        "instrument": "elss_fund",
        "name": elss.get("category_name", "ELSS Tax Saving Mutual Fund"),
        "rate_pct": 11.0,  # assumed average
        "lock_in_years": 3.0,
        "why": "Shortest lock-in (3 years) among Section 123 options with high equity growth potential.",
    })

    # 4. NSC
    nsc = ref.small_savings.get("nsc", {})
    options.append({
        "instrument": "nsc_certificate",
        "name": nsc.get("scheme_name", "National Savings Certificate"),
        "rate_pct": nsc.get("rate_pct", 7.7),
        "lock_in_years": 5.0,
        "why": "Guaranteed 5-year sovereign compounding with Section 123 deduction.",
    })

    # 5. Best Tax-Saver FD (sorted by senior or general rate)
    best_tax_fds = top_fds(ref=ref, tenure="5y", senior=senior, profile="moderate", n=1, product="tax_saver")
    if best_tax_fds:
        best_fd = best_tax_fds[0]
        fd_rate = best_fd["rate_senior_pct"] if senior else best_fd["rate_general_pct"]
        options.append({
            "instrument": "tax_saver_fd",
            "name": f"5-Year Tax Saver Bank FD ({best_fd['bank_name']})",
            "rate_pct": fd_rate,
            "lock_in_years": 5.0,
            "why": "Safe bank fixed deposit with Section 123 deduction up to Rs 1.5 lakh.",
        })

    # 6. SCSS if 60+
    if senior:
        scss = ref.small_savings.get("scss", {})
        options.append({
            "instrument": "scss_account",
            "name": scss.get("scheme_name", "Senior Citizens Savings Scheme"),
            "rate_pct": scss.get("rate_pct", 8.2),
            "lock_in_years": 5.0,
            "why": "Government-backed quarterly payout for senior citizens with Section 123 deduction.",
        })

    return {
        "section": section_name,
        "limit_inr": limit_inr,
        "note": "Applicable only under the Old Tax Regime. The New Default Tax Regime does not allow this deduction.",
        "options": options,
    }


def build_fd_recommendations(
    p: Dict[str, Any],
    profile: str,
    ref: ReferenceData,
) -> Dict[str, Any]:
    age = p.get("age", 0)
    senior = age >= 60
    rate_type = "senior" if senior else "general"
    sfb_hidden = profile == "conservative"

    # by_tenure: 1y, 3y, 5y (top 5 each)
    by_tenure = {
        "1y": top_fds(ref=ref, tenure="1y", senior=senior, profile=profile, n=5, product="regular"),
        "3y": top_fds(ref=ref, tenure="3y", senior=senior, profile=profile, n=5, product="regular"),
        "5y": top_fds(ref=ref, tenure="5y", senior=senior, profile=profile, n=5, product="regular"),
    }

    # tax_saver: top 3 tax_saver FDs only if tax_regime == "old", else []
    tax_saver = []
    if p.get("tax_regime") == "old":
        tax_saver = top_fds(ref=ref, tenure="5y", senior=senior, profile=profile, n=3, product="tax_saver")

    # post_office_td: the 1/2/3/5-year post office TD rates from small_savings
    potd_keys = ["potd_1y", "potd_2y", "potd_3y", "potd_5y"]
    post_office_td = []
    for k in potd_keys:
        s = ref.small_savings.get(k)
        if s:
            post_office_td.append({
                "scheme_id": k,
                "name": s.get("scheme_name", k),
                "tenure_years": s.get("tenure_years"),
                "rate_pct": s.get("rate_pct"),
                "tax_deduction_eligible": s.get("tax_deduction_eligible", False),
                "sovereign_backed": True,
            })

    dicgc_cover = ref.config["deposit_safety"]["dicgc_cover_inr"]
    safety_note = (
        f"Deposits are insured up to Rs {dicgc_cover:,} per depositor per bank by DICGC. "
        "Keep no more than this at any one small finance bank."
    )
    as_of = ref.fd_as_of.isoformat() if hasattr(ref.fd_as_of, "isoformat") else str(ref.fd_as_of)

    return {
        "rate_type": rate_type,
        "profile": profile,
        "sfb_hidden": sfb_hidden,
        "by_tenure": by_tenure,
        "tax_saver": tax_saver,
        "post_office_td": post_office_td,
        "dicgc_cover_inr": dicgc_cover,
        "safety_note": safety_note,
        "as_of": as_of,
    }

