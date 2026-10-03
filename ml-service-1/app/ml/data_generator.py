import os
import random
import pandas as pd
import numpy as np


def calculate_health_score(row):
    score = 0.0

    # EMI ratio (max 25 points) — lower is better
    # if emi_to_income_ratio is 0.0, score is 25. If 0.40, score is 0.
    emi_score = max(0.0, 25.0 * (1.0 - (row['emi_to_income_ratio'] / 0.40)))
    score += min(25.0, emi_score)

    # Savings rate (max 25 points) — higher is better
    # if savings_rate is >= 0.20, score is 25. If 0.0, score is 0.
    savings_score = min(25.0, 25.0 * (row['savings_rate'] / 0.20))
    score += savings_score

    # Emergency fund (max 20 points) — target 6 months
    # if emergency_fund_months >= 6.0, score is 20.
    emergency_score = min(20.0, 20.0 * (row['emergency_fund_months'] / 6.0))
    score += emergency_score

    # Expense ratio (max 15 points) — lower is better
    # if expense_to_income_ratio is 0.0, score is 15. If >= 0.70, score is 0.
    expense_score = max(0.0, 15.0 * (1.0 - (row['expense_to_income_ratio'] / 0.70)))
    score += min(15.0, expense_score)

    # Asset to liability ratio (max 10 points)
    # if asset_to_liability_ratio >= 3.0, score is 10.
    asset_score = min(10.0, 10.0 * (row['asset_to_liability_ratio'] / 3.0))
    score += asset_score

    # Goal progress (max 5 points)
    goal_score = 5.0 * row['goal_progress_avg']
    score += goal_score

    return round(min(100.0, max(0.0, score)), 2)


def get_category(score):
    if score <= 40:
        return "POOR"
    elif score <= 60:
        return "FAIR"
    elif score <= 80:
        return "GOOD"
    else:
        return "EXCELLENT"


def generate_synthetic_data(num_profiles=10000, output_path="data/synthetic_financial_data.csv"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Set seed for reproducibility
    np.random.seed(42)
    random.seed(42)

    income_ranges = [
        (15000, 30000),   # Entry level / blue collar
        (30000, 60000),   # Mid level
        (60000, 120000),  # Senior level
        (120000, 300000), # High income
    ]

    data = []
    for _ in range(num_profiles):
        # Pick an income range and get a monthly income
        inc_range = random.choice(income_ranges)
        monthly_income = float(random.randint(inc_range[0], inc_range[1]))

        emi_to_income_ratio = float(np.random.uniform(0.0, 0.80))
        savings_rate = float(np.random.uniform(0.0, 0.50))
        emergency_fund_months = float(np.random.uniform(0.0, 12.0))
        expense_to_income_ratio = float(np.random.uniform(0.30, 1.10))
        asset_to_liability_ratio = float(np.random.uniform(0.0, 10.0))
        goal_progress_avg = float(np.random.uniform(0.0, 1.0))

        row = {
            "monthly_income": monthly_income,
            "emi_to_income_ratio": emi_to_income_ratio,
            "savings_rate": savings_rate,
            "emergency_fund_months": emergency_fund_months,
            "expense_to_income_ratio": expense_to_income_ratio,
            "asset_to_liability_ratio": asset_to_liability_ratio,
            "goal_progress_avg": goal_progress_avg
        }

        score = calculate_health_score(row)
        row["health_score"] = score
        row["category"] = get_category(score)

        data.append(row)

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"Generated {num_profiles} profiles and saved to {output_path}")
    return df


if __name__ == "__main__":
    generate_synthetic_data()
