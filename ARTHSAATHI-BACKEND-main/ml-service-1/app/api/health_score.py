import time
from collections import defaultdict
from fastapi import APIRouter, HTTPException, status, Request
from app.schemas.health_score import HealthScoreRequest, HealthScoreResponse
from app.ml.features import extract_features
from app.ml.predictor import predictor

router = APIRouter(prefix="/ml")

# Simple in-memory sliding window rate limiter
# Max 10 requests per second per IP
VISIT_RECORDS = defaultdict(list)
RATE_LIMIT_WINDOW = 1.0  # 1 second
RATE_LIMIT_MAX = 10


def rate_limiter(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Filter out timestamps older than the window
    VISIT_RECORDS[client_ip] = [t for t in VISIT_RECORDS[client_ip] if now - t < RATE_LIMIT_WINDOW]
    
    if len(VISIT_RECORDS[client_ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 10 requests per second."
        )
    
    VISIT_RECORDS[client_ip].append(now)


@router.post("/health-score", response_model=HealthScoreResponse)
def calculate_financial_health_score(
    payload: HealthScoreRequest,
    request: Request
):
    """
    Accepts raw financial profile data, engineers the features,
    and runs Random Forest inference to return health score, category,
    feature importance, and personalized insights.
    """
    # Apply rate limiting
    rate_limiter(request)

    # Extract goal list
    goal_list = [{"target_amount": g.target_amount, "current_savings": g.current_savings} for g in payload.goals]

    # Convert to engineered features
    engineered_features = extract_features(
        monthly_income=payload.monthly_income,
        total_monthly_emis=payload.total_monthly_emis,
        total_monthly_expenses=payload.total_monthly_expenses,
        liquid_savings=payload.liquid_savings,
        total_assets=payload.total_assets,
        total_liabilities=payload.total_liabilities,
        goal_list=goal_list,
    )

    # Perform prediction
    result = predictor.predict(engineered_features)

    return HealthScoreResponse(
        health_score=result["health_score"],
        category=result["category"],
        feature_importance=result["feature_importance"],
        insights=result["insights"],
        model_version="1.0.0"
    )
