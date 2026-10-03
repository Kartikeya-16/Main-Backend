import os
from app.ml.data_generator import generate_synthetic_data
from app.ml.trainer import train_model

DATA_PATH = "data/synthetic_financial_data.csv"
MODEL_PATH = "models/health_score_model.pkl"


def main():
    print("Starting retraining pipeline...")
    
    # 1. Generate fresh synthetic training data
    print("Generating new synthetic dataset...")
    generate_synthetic_data(num_profiles=10000, output_path=DATA_PATH)

    # 2. Train Random Forest model and print metrics
    print("Training Random Forest model...")
    mae, r2, importances = train_model(data_path=DATA_PATH, model_path=MODEL_PATH)

    print("-" * 50)
    print(f"Model retrained successfully. MAE: {mae:.4f}, R²: {r2:.4f}")
    print("-" * 50)


if __name__ == "__main__":
    main()
