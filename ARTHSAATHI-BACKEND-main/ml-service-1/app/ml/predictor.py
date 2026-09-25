import os
import joblib
import pandas as pd
from app.ml.trainer import FEATURES

MODEL_PATH = "models/health_score_model.pkl"

class Predictor:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.feature_importances = {}
        if os.path.exists(self.model_path):
            self.load_model()

    def load_model(self):
        print(f"Loading model from {self.model_path}...")
        self.model = joblib.load(self.model_path)
        
        # Store feature importances for response
        importances = self.model.feature_importances_
        self.feature_importances = {
            feature: float(importance)
            for feature, importance in zip(FEATURES, importances)
        }

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_category(self, score: float) -> str:
        if score <= 40:
            return "POOR"
        elif score <= 60:
            return "FAIR"
        elif score <= 80:
            return "GOOD"
        else:
            return "EXCELLENT"

    def generate_insights(self, features: dict) -> list[str]:
        insights = []

        emi = features.get("emi_to_income_ratio", 0.0)
        savings = features.get("savings_rate", 0.0)
        emergency = features.get("emergency_fund_months", 0.0)
        expense = features.get("expense_to_income_ratio", 0.0)
        asset_liab = features.get("asset_to_liability_ratio", 0.0)
        goal_prog = features.get("goal_progress_avg", 0.0)

        # 1. EMI ratio checks
        if emi > 0.60:
            insights.append("Dangerous debt levels: High EMI burden is severely reducing your score. Limit new borrowing.")
        elif emi > 0.40:
            insights.append("High EMI burden is reducing your score. Try to keep total EMIs below 40% of your income.")
        
        # 2. Savings rate checks
        if savings < 0.05:
            insights.append("Critical: Low savings rate is impacting your financial health. Save at least 10-20% of your income.")
        elif savings < 0.20:
            insights.append("Moderate savings rate. Try to increase savings towards the recommended 20% mark.")

        # 3. Emergency fund checks
        if emergency < 3.0:
            insights.append("Critical: Emergency fund is below 3 months of expenses. prioritize building a liquid buffer.")
        elif emergency < 6.0:
            insights.append("Emergency fund is moderate but below the recommended 6 months of expenses.")

        # 4. Expense ratio checks
        if expense > 0.80:
            insights.append("High expense-to-income ratio. Review your discretionary spending to free up cash flow.")

        # 5. Asset/Liability checks
        if asset_liab < 1.0:
            insights.append("Your liabilities exceed your assets. Focus on debt reduction and wealth creation.")

        # 6. Goal progress checks
        if goal_prog < 0.30:
            insights.append("Average progress towards your financial goals is slow. Consider automating your savings.")

        if not insights:
            insights.append("Excellent financial behavior! Keep maintaining low debt levels and a strong savings habit.")

        return insights

    def predict(self, features: dict) -> dict:
        if not self.is_loaded():
            raise RuntimeError("Model is not loaded. Please train the model first.")

        # Prepare features in the exact order model expects
        df_input = pd.DataFrame([features])[FEATURES]
        score = float(self.model.predict(df_input)[0])
        score = round(min(100.0, max(0.0, score)), 2)

        return {
            "health_score": score,
            "category": self.get_category(score),
            "feature_importance": self.feature_importances,
            "insights": self.generate_insights(features)
        }


# Global predictor instance
predictor = Predictor()
