"""
Trains Text Scam Classifier:
- Combines Word N-Grams (1-2) + Character N-Grams (2-5) using FeatureUnion to absorb Hinglish variations.
- Calibrated Classifier (Logistic Regression / LinearSVC) predicting 'scam', 'promo', 'legit' probabilities.
- Saves model to artifacts/text_scam_model.joblib.
"""
import os
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

from dataset_builder import generate_text_dataset

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE_DIR, "app", "data", "financial_sms_3class.csv")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
MODEL_OUT = os.path.join(ARTIFACTS_DIR, "text_scam_model.joblib")


def train_text_classifier():
    if not os.path.exists(DATA_PATH):
        generate_text_dataset()

    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} samples from {DATA_PATH}. Class distribution:")
    print(df["label"].value_counts())

    X = df["text"].astype(str)
    y = df["label"].astype(str)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # FeatureUnion: Word (1-2) n-grams + Character (2-5) n-grams
    vectorizer = FeatureUnion([
        ("word_tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            lowercase=True,
            max_features=5000,
            token_pattern=r"(?u)\b\w+\b"
        )),
        ("char_tfidf", TfidfVectorizer(
            ngram_range=(2, 5),
            analyzer="char_wb",
            lowercase=True,
            max_features=10000
        ))
    ])

    base_clf = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        C=2.0,
        random_state=42
    )

    # Calibrated classifier for reliable probability estimates
    model = Pipeline([
        ("union", vectorizer),
        ("clf", CalibratedClassifierCV(estimator=base_clf, cv=3))
    ])

    print("\nTraining Text Scam Classifier pipeline...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n=== CLASSIFICATION REPORT (Text Scam Model) ===")
    print(classification_report(y_test, y_pred, digits=4))
    print("=== CONFUSION MATRIX ===")
    print(confusion_matrix(y_test, y_pred))

    joblib.dump(model, MODEL_OUT)
    print(f"\nModel successfully saved to: {MODEL_OUT}")
    return model


if __name__ == "__main__":
    train_text_classifier()
