from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.financial_twin import router as financial_twin_router
from app.api.routes.ml import router as ml_proxy_router
from app.api.routes.statements import router as statements_router
from app.api.routes.scam import router as scam_router
from app.database.connection import get_db, Base, engine
import app.models.user  # noqa: F401
import app.models.financial_twin  # noqa: F401
import app.models.statement  # noqa: F401

# Automatically create tables if reachable
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

app = FastAPI(
    title="FinPilot API",
    description="AI-powered financial companion capstone project backend",
    version="1.0.0"
)

# CORS middleware configuration using dynamically parsed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(financial_twin_router)
app.include_router(ml_proxy_router)
app.include_router(statements_router)
app.include_router(scam_router)



@app.get("/health", tags=["Health Check"])
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint to verify backend and database service status.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": f"disconnected: {str(e)}"}
