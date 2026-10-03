def extract_features(
    monthly_income: float,
    total_monthly_emis: float,
    total_monthly_expenses: float,
    liquid_savings: float,
    total_assets: float,
    total_liabilities: float,
    goal_list: list,
) -> dict:
    """
    Converts raw Financial Twin values into the 6 normalized features
    the ML model expects. This is the bridge between the API input
    and the model input.
    """
    income = float(monthly_income)
    emis = float(total_monthly_emis)
    expenses = float(total_monthly_expenses)
    savings = float(liquid_savings)
    assets = float(total_assets)
    liabilities = float(total_liabilities)

    # 1. emi_to_income_ratio (safe < 0.40, dangerous > 0.60)
    if income > 0:
        emi_to_income_ratio = emis / income
    else:
        emi_to_income_ratio = 1.0 if emis > 0 else 0.0

    # 2. savings_rate (poor < 0.05, good > 0.20)
    # savings = income - expenses - emis
    calc_savings = max(0.0, income - expenses - emis)
    if income > 0:
        savings_rate = calc_savings / income
    else:
        savings_rate = 0.0

    # 3. emergency_fund_months (critical < 3, safe > 6)
    if expenses > 0:
        emergency_fund_months = savings / expenses
    else:
        emergency_fund_months = 12.0 if savings > 0 else 0.0

    # 4. expense_to_income_ratio (lean < 0.50, stretched > 0.80)
    if income > 0:
        expense_to_income_ratio = expenses / income
    else:
        expense_to_income_ratio = 1.0 if expenses > 0 else 0.0

    # 5. asset_to_liability_ratio (poor < 1.0, good > 3.0)
    if liabilities > 0:
        asset_to_liability_ratio = assets / liabilities
    else:
        asset_to_liability_ratio = 10.0 if assets > 0 else 0.0

    # 6. goal_progress_avg (0 = not started, 1.0 = achieved)
    if goal_list:
        progresses = []
        for goal in goal_list:
            target = float(goal.get("target_amount", 0.0))
            current = float(goal.get("current_savings", 0.0))
            if target > 0:
                prog = min(1.0, max(0.0, current / target))
            else:
                prog = 1.0 if current > 0 else 0.0
            progresses.append(prog)
        goal_progress_avg = sum(progresses) / len(progresses)
    else:
        # Default to 0.0 if no goals exist
        goal_progress_avg = 0.0

    return {
        "emi_to_income_ratio": emi_to_income_ratio,
        "savings_rate": savings_rate,
        "emergency_fund_months": emergency_fund_months,
        "expense_to_income_ratio": expense_to_income_ratio,
        "asset_to_liability_ratio": asset_to_liability_ratio,
        "goal_progress_avg": goal_progress_avg,
    }
