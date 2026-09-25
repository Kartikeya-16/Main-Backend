import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.health_score import router as health_score_router
from app.ml.trainer import train_model
from app.ml.predictor import predictor, MODEL_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: Check if model file exists
    if not os.path.exists(MODEL_PATH):
        print("Model file not found. Initializing auto-train pipeline...")
        train_model()
    
    # Load model into predictor
    predictor.load_model()
    yield


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Arthsaathi ML Service 1 — Financial Health Score",
    description="Microservice to predict user Financial Health Score",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(health_score_router)


@app.get("/health", tags=["Health Check"])
def health_check():
    """
    Verifies service status, model loading status, and version.
    """
    model_loaded = predictor.is_loaded()
    return {
        "status": "ok",
        "model": "loaded" if model_loaded else "not_loaded",
        "model_version": "1.0.0"
    }
