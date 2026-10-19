from app.database.connection import Base
from app.models.user import User
from app.models.financial_twin import (
    FinancialTwin,
    Income,
    Expense,
    Asset,
    Liability,
    FinancialGoal,
)

from app.models.statement import Statement, Transaction

# This allows Alembic or other parts of the app to import all models easily
__all__ = [
    "Base",
    "User",
    "FinancialTwin",
    "Income",
    "Expense",
    "Asset",
    "Liability",
    "FinancialGoal",
    "Statement",
    "Transaction",
]

