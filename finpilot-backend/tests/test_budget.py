import pytest
from app.services.budget import calculate_budget_allocation


def test_budget_allocation_reconciliation_surplus():
    # Income ₹80,000, Needs ₹43,000, Wants ₹20,000 -> Savings ₹17,000
    res = calculate_budget_allocation(
        monthly_income=80000,
        raw_needs=43000,
        raw_wants=20000
    )
    assert res["monthly_income"] == 80000.0
    assert res["needs"] == 43000.0
    assert res["wants"] == 20000.0
    assert res["savings"] == 17000.0
    assert not res["is_deficit"]
    assert res["deficit_amount"] == 0.0

    # Assert percentages sum to exactly 100.0%
    total_pct = round(res["needs_pct"] + res["wants_pct"] + res["savings_pct"], 2)
    assert total_pct == 100.0


def test_budget_allocation_reconciliation_deficit():
    # Income ₹80,000, Needs ₹63,000, Wants ₹20,000 -> Savings -₹3,000 (Deficit)
    res = calculate_budget_allocation(
        monthly_income=80000,
        raw_needs=63000,
        raw_wants=20000
    )
    assert res["needs"] == 63000.0
    assert res["wants"] == 20000.0
    assert res["savings"] == -3000.0
    assert res["is_deficit"]
    assert res["deficit_amount"] == 3000.0

    # Percentages: Needs (78.75%), Wants (25.0%), Savings (-3.75%)
    total_pct = round(res["needs_pct"] + res["wants_pct"] + res["savings_pct"], 2)
    assert total_pct == 100.0


def test_budget_allocation_itemized_expenses():
    expenses = [
        {"category": "HOUSING", "amount": 18000},
        {"category": "FOOD", "amount": 9000},
        {"category": "TRANSPORT", "amount": 3500},
        {"category": "UTILITIES", "amount": 2800},
        {"category": "EDUCATION", "amount": 6000},
        {"category": "INSURANCE", "amount": 2200},
        {"category": "ENTERTAINMENT", "amount": 5000},
        {"category": "SHOPPING", "amount": 4000},
    ]
    liabilities = [
        {"emi_amount": 10000}
    ]
    # Needs = (18000+9000+3500+2800+6000+2200) + 10000 = 51,500
    # Wants = (5000+4000) = 9,000
    # Savings = 80,000 - 51,500 - 9,000 = 19,500
    res = calculate_budget_allocation(
        monthly_income=80000,
        expenses=expenses,
        liabilities=liabilities
    )
    assert res["needs"] == 51500.0
    assert res["wants"] == 9000.0
    assert res["savings"] == 19500.0
    assert not res["is_deficit"]

    total_pct = round(res["needs_pct"] + res["wants_pct"] + res["savings_pct"], 2)
    assert total_pct == 100.0
