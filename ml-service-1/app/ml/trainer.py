import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from app.ml.data_generator import generate_synthetic_data

FEATURES = [
    "emi_to_income_ratio",
    "savings_rate",
    "emergency_fund_months",
    "expense_to_income_ratio",
    "asset_to_liability_ratio",
    "goal_progress_avg",
]
TARGET = "health_score"


def train_model(data_path="data/synthetic_financial_data.csv", model_path="models/health_score_model.pkl"):
    # Ensure data directory exists
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    # If data does not exist, generate it
    if not os.path.exists(data_path):
        print(f"Data file not found at {data_path}. Generating synthetic data first...")
        df = generate_synthetic_data(num_profiles=10000, output_path=data_path)
    else:
        df = pd.read_csv(data_path)

    X = df[FEATURES]
    y = df[TARGET]

    # Split into 80/20 train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Initialize Random Forest Regressor
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Predict and evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"--- Training Metrics ---")
    print(f"Mean Absolute Error (MAE): {mae:.4f}")
    print(f"R² Score: {r2:.4f}")

    # Feature Importance
    importances = model.feature_importances_
    print("--- Feature Importances ---")
    for feature, importance in zip(FEATURES, importances):
        print(f"{feature}: {importance:.4f}")

    # Save model
    joblib.dump(model, model_path)
    print(f"Model saved successfully to {model_path}")

    return mae, r2, importances


if __name__ == "__main__":
    train_model()
