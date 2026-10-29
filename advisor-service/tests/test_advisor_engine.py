import json
from datetime import date
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.advisor.data_loader import load_reference_data, freshness
from app.advisor.engine import (
    AdvisorInputError,
    build_plan,
    core_assessment,
    inr,
    validate_profile,
)
from app.advisor.products import fd_tenure_for, top_fds
from app.advisor.router import router as advisor_router

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PERSONAS_PATH = DATA_DIR / "fixtures" / "personas.json"


@pytest.fixture(scope="session")
def personas_data():
    with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["personas"]


@pytest.fixture(scope="session")
def client():
    app = FastAPI()
    app.include_router(advisor_router)
    return TestClient(app)


with open(PERSONAS_PATH, "r", encoding="utf-8") as _f:
    ALL_PERSONAS = json.load(_f)["personas"]


# ------------------------------------------------------------------
# Golden tests: core_assessment vs personas.json expected
# ------------------------------------------------------------------

@pytest.mark.parametrize("persona", ALL_PERSONAS, ids=[p["persona_id"] for p in ALL_PERSONAS])
def test_persona_golden(persona):
    pid = persona["persona_id"]
    exp = persona["expected"]
    profile = {k: v for k, v in persona.items() if k not in {"persona_id", "description", "tests", "expected"}}
    got = core_assessment(profile)
    assert got == exp, f"Mismatch for persona {pid}: expected {exp}, got {got}"


@pytest.mark.parametrize("persona", ALL_PERSONAS, ids=[p["persona_id"] for p in ALL_PERSONAS])
def test_persona_build_plan(persona):
    pid = persona["persona_id"]
    exp = persona["expected"]
    profile = {k: v for k, v in persona.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)

    # 1. Summary core matches expected
    for k in exp:
        assert plan["summary"][k] == exp[k], f"{pid} summary mismatch on {k}"

    # 2. First flags in actions match expected flags
    flag_action_codes = [a["code"] for a in plan["actions"] if a["code"] != "invest_for_goals"]
    assert flag_action_codes == exp["flags"], f"{pid} action flags mismatch"

    # 3. First action status is do_now
    if plan["actions"]:
        assert plan["actions"][0]["status"] == "do_now"
        for subsequent in plan["actions"][1:]:
            assert subsequent["status"] == "next"

    # 4. Every action has reasons
    for action in plan["actions"]:
        assert len(action["reasons"]) > 0, f"{pid} action {action['code']} has no reasons"

    # 5. Equity + debt split equals SIP for every goal
    for goal in plan["goals"]:
        sip = goal["required_monthly_sip_inr"]
        split = goal["split_monthly_inr"]
        assert split["equity"] + split["debt"] == sip, f"{pid} SIP split mismatch on {goal['goal_id']}"

        # 6. Every goal has instruments
        assert len(goal["instruments"]) > 0, f"{pid} goal {goal['goal_id']} has no instruments"

        # 7. Goals with 0% equity have no equity instruments
        if goal["equity_share_pct"] == 0:
            equity_instruments = [inst for inst in goal["instruments"] if inst["role"] in {"equity", "hybrid"}]
            assert len(equity_instruments) == 0, f"{pid} 0% equity goal {goal['goal_id']} contains equity/hybrid instruments: {equity_instruments}"


# ------------------------------------------------------------------
# Specific targeted tests
# ------------------------------------------------------------------

def test_p19_short_goal_gets_0_percent_equity(personas_data):
    p19 = next(p for p in personas_data if p["persona_id"].startswith("p19"))
    profile = {k: v for k, v in p19.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)
    assert plan["risk"]["profile"] == "aggressive"
    assert len(plan["goals"]) == 1
    assert plan["goals"][0]["bucket"] == "short"
    assert plan["goals"][0]["equity_share_pct"] == 0


def test_p01_capped_by_no_income(personas_data):
    p01 = next(p for p in personas_data if p["persona_id"].startswith("p01"))
    profile = {k: v for k, v in p01.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)
    assert plan["risk"]["score"] == 15  # Aggressive score
    assert plan["risk"]["questionnaire_profile"] == "aggressive"
    assert plan["risk"]["profile"] == "conservative"
    assert plan["risk"]["capped_by"] == "no_income"


def test_p07_capped_by_age_60_plus(personas_data):
    p07 = next(p for p in personas_data if p["persona_id"].startswith("p07"))
    profile = {k: v for k, v in p07.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)
    assert plan["risk"]["score"] >= 15
    assert plan["risk"]["questionnaire_profile"] == "aggressive"
    assert plan["risk"]["profile"] == "moderate"
    assert plan["risk"]["capped_by"] == "age_60_plus"


def test_p11_payoff_order_and_amount(personas_data):
    p11 = next(p for p in personas_data if p["persona_id"].startswith("p11"))
    profile = {k: v for k, v in p11.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)
    debt_action = next(a for a in plan["actions"] if a["code"] == "high_interest_debt")
    assert debt_action["amount_inr"] == 400000
    assert debt_action["payoff_order"] == ["credit_card", "personal_loan"]


def test_p09_home_loan_not_flagged(personas_data):
    p09 = next(p for p in personas_data if p["persona_id"].startswith("p09"))
    profile = {k: v for k, v in p09.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)
    assert "high_interest_debt" not in [a["code"] for a in plan["actions"]]
    assert plan["summary"]["first_action"] == "invest_for_goals"


def test_tax_saving_presence(personas_data):
    p13 = next(p for p in personas_data if p["persona_id"].startswith("p13"))
    profile_p13 = {k: v for k, v in p13.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan_p13 = build_plan(profile_p13)
    assert plan_p13["tax_saving"] is not None
    assert plan_p13["summary"]["tax_saving_relevant"] is True

    p03 = next(p for p in personas_data if p["persona_id"].startswith("p03"))
    profile_p03 = {k: v for k, v in p03.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan_p03 = build_plan(profile_p03)
    assert plan_p03["tax_saving"] is None
    assert plan_p03["summary"]["tax_saving_relevant"] is False


def test_p13_daughter_goal_instruments_and_tax(personas_data):
    p13 = next(p for p in personas_data if p["persona_id"].startswith("p13"))
    profile = {k: v for k, v in p13.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)

    # First tax option must be SSY
    assert plan["tax_saving"]["options"][0]["instrument"] == "ssy_account"

    # Goal with for_daughter=True has SSY as first debt instrument
    for g in plan["goals"]:
        debt_instruments = [inst["category_id"] for inst in g["instruments"] if inst["role"] == "debt"]
        assert debt_instruments[0] == "ssy_account"


def test_conservative_top_fds_never_return_sfb():
    ref = load_reference_data()
    fds = top_fds(ref=ref, tenure="1y", senior=False, profile="conservative", n=5)
    for fd in fds:
        assert fd["bank_type"] != "sfb"


def test_fd_options_sorted_by_rate():
    ref = load_reference_data()
    fds = top_fds(ref=ref, tenure="3y", senior=False, profile="moderate", n=5)
    rates = [f["rate_general_pct"] for f in fds]
    assert rates == sorted(rates, reverse=True)


def test_senior_rate_greater_or_equal_general():
    ref = load_reference_data()
    for row in ref.fd_rates:
        assert row["rate_senior_pct"] >= row["rate_general_pct"]


def test_large_bank_always_included_for_aggressive():
    ref = load_reference_data()
    # In 1y tenure, top banks by rate are all SFBs
    fds = top_fds(ref=ref, tenure="1y", senior=False, profile="aggressive", n=3)
    assert len(fds) == 3
    # Check that at least one large bank (psu or private) is included
    assert any(f["bank_type"] in {"psu", "private"} for f in fds)


def test_fd_tenure_for():
    assert fd_tenure_for(2) == "1y"
    assert fd_tenure_for(4) == "3y"
    assert fd_tenure_for(5) == "5y"
    assert fd_tenure_for(10) == "5y"


def test_p12_gets_dicgc_note(personas_data):
    p12 = next(p for p in personas_data if p["persona_id"].startswith("p12"))
    profile = {k: v for k, v in p12.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(profile)
    goal = plan["goals"][0]
    assert goal["fd_options"]["dicgc_note"] is not None
    assert "exceeds the Rs 5,00,000 DICGC insurance cover" in goal["fd_options"]["dicgc_note"]


def test_inr_formatting():
    assert inr(1234567) == "Rs 12,34,567"
    assert inr(500) == "Rs 500"
    assert inr(100000) == "Rs 1,00,000"
    assert inr(0) == "Rs 0"
    assert inr(-50000) == "-Rs 50,000"


def test_data_freshness():
    fresh_on_recent = freshness(today=date(2026, 10, 20))
    assert fresh_on_recent["stale"] is False

    stale_on_future = freshness(today=date(2027, 1, 5))
    assert stale_on_future["stale"] is True


def test_bad_inputs_raise_advisor_input_error(personas_data):
    p01 = personas_data[0]
    valid_profile = {k: v for k, v in p01.items() if k not in {"persona_id", "description", "tests", "expected"}}

    # 1. Invalid age
    with pytest.raises(AdvisorInputError):
        bad = dict(valid_profile)
        bad["age"] = 120
        validate_profile(bad)

    # 2. Invalid risk answers
    with pytest.raises(AdvisorInputError):
        bad = dict(valid_profile)
        bad["risk_answers"] = [1, 2, 3]
        validate_profile(bad)

    with pytest.raises(AdvisorInputError):
        bad = dict(valid_profile)
        bad["risk_answers"] = [1, 2, 3, 4, 9]
        validate_profile(bad)

    # 3. Negative money
    with pytest.raises(AdvisorInputError):
        bad = dict(valid_profile)
        bad["monthly_expenses_inr"] = -500
        validate_profile(bad)

    # 4. Duplicate goal IDs
    with pytest.raises(AdvisorInputError):
        bad = dict(valid_profile)
        bad["goals"] = [
            {"goal_id": "g1", "name": "G1", "target_inr": 1000, "years": 2},
            {"goal_id": "g1", "name": "G2", "target_inr": 2000, "years": 3},
        ]
        validate_profile(bad)

    # 5. Invalid goal years
    with pytest.raises(AdvisorInputError):
        bad = dict(valid_profile)
        bad["goals"] = [{"goal_id": "g1", "name": "G1", "target_inr": 1000, "years": 0}]
        validate_profile(bad)


# ------------------------------------------------------------------
# FastAPI API Endpoint Tests
# ------------------------------------------------------------------

def test_api_questionnaire(client):
    res = client.get("/advisor/questionnaire")
    assert res.status_code == 200
    data = res.json()
    assert len(data["questions"]) == 5
    assert "bands" in data
    assert "caps" in data


def test_api_meta(client):
    res = client.get("/advisor/meta")
    assert res.status_code == 200
    data = res.json()
    assert "data_freshness" in data
    assert "fd_rates_as_of" in data["data_freshness"]
    assert "disclaimer" in data
    assert "assumptions" in data


def test_api_post_plan_p04(client, personas_data):
    p04 = next(p for p in personas_data if p["persona_id"].startswith("p04"))
    profile = {k: v for k, v in p04.items() if k not in {"persona_id", "description", "tests", "expected"}}
    res = client.post("/advisor/plan", json=profile)
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["first_action"] == "term_insurance_gap"
    assert body["actions"][0]["code"] == "term_insurance_gap"
    assert body["actions"][0]["status"] == "do_now"


def test_api_post_plan_invalid_answers_422(client, personas_data):
    p04 = next(p for p in personas_data if p["persona_id"].startswith("p04"))
    profile = dict(p04)
    profile["risk_answers"] = [9, 9, 9, 9, 9]
    res = client.post("/advisor/plan", json=profile)
    assert res.status_code == 422


def test_fd_recommendations_exists_for_every_persona(personas_data):
    for p_raw in personas_data:
        p = {k: v for k, v in p_raw.items() if k not in {"persona_id", "description", "tests", "expected"}}
        plan = build_plan(p)
        assert "fd_recommendations" in plan
        rec = plan["fd_recommendations"]
        assert "rate_type" in rec
        assert "profile" in rec
        assert "sfb_hidden" in rec
        assert "by_tenure" in rec
        assert "1y" in rec["by_tenure"]
        assert "3y" in rec["by_tenure"]
        assert "5y" in rec["by_tenure"]
        assert "tax_saver" in rec
        assert "post_office_td" in rec
        assert "dicgc_cover_inr" in rec
        assert "safety_note" in rec
        assert "as_of" in rec


def test_fd_recommendations_by_tenure_sorted_up_to_5(personas_data):
    p04 = next(p for p in personas_data if p["persona_id"].startswith("p04"))
    p = {k: v for k, v in p04.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(p)
    rec = plan["fd_recommendations"]
    for tenure in ["1y", "3y", "5y"]:
        items = rec["by_tenure"][tenure]
        assert 0 < len(items) <= 5
        rates = [item["rate_general_pct"] for item in items]
        assert rates == sorted(rates, reverse=True)


def test_fd_recommendations_conservative_hides_sfb(personas_data):
    # p18 is conservative profile
    p18 = next(p for p in personas_data if p["persona_id"].startswith("p18"))
    p = {k: v for k, v in p18.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(p)
    rec = plan["fd_recommendations"]
    assert rec["profile"] == "conservative"
    assert rec["sfb_hidden"] is True
    for tenure in ["1y", "3y", "5y"]:
        for item in rec["by_tenure"][tenure]:
            assert item["bank_type"] != "sfb"


def test_fd_recommendations_senior_rate_type(personas_data):
    # p07 is age 60+ retiree
    p07 = next(p for p in personas_data if p["persona_id"].startswith("p07"))
    p = {k: v for k, v in p07.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(p)
    rec = plan["fd_recommendations"]
    assert rec["rate_type"] == "senior"


def test_fd_recommendations_tax_saver_regime(personas_data):
    # p13 is old tax regime
    p13 = next(p for p in personas_data if p["persona_id"].startswith("p13"))
    p_old = {k: v for k, v in p13.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan_old = build_plan(p_old)
    assert len(plan_old["fd_recommendations"]["tax_saver"]) > 0

    # p03 is new tax regime
    p03 = next(p for p in personas_data if p["persona_id"].startswith("p03"))
    p_new = {k: v for k, v in p03.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan_new = build_plan(p_new)
    assert plan_new["fd_recommendations"]["tax_saver"] == []


def test_fd_recommendations_post_office_td_has_4_rows(personas_data):
    p01 = next(p for p in personas_data if p["persona_id"].startswith("p01"))
    p = {k: v for k, v in p01.items() if k not in {"persona_id", "description", "tests", "expected"}}
    plan = build_plan(p)
    assert len(plan["fd_recommendations"]["post_office_td"]) == 4

