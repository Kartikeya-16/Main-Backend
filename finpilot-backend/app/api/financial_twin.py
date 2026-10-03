from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.connection import get_db
from app.models.user import User
from app.models.financial_twin import (
    FinancialTwin,
    Income,
    Expense,
    Asset,
    Liability,
    FinancialGoal,
)
from app.schemas.financial_twin import (
    FinancialTwinCreate,
    FinancialTwinUpdate,
    FinancialTwinResponse,
    IncomeCreate,
    IncomeUpdate,
    IncomeResponse,
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseResponse,
    AssetCreate,
    AssetUpdate,
    AssetResponse,
    LiabilityCreate,
    LiabilityUpdate,
    LiabilityResponse,
    FinancialGoalCreate,
    FinancialGoalUpdate,
    FinancialGoalResponse,
)
from app.core.dependencies import get_current_user

router = APIRouter(tags=["Financial Twin"])


# --- FINANCIAL TWIN ROUTER ---

@router.post("/financial-twin", response_model=FinancialTwinResponse, status_code=status.HTTP_201_CREATED)
def create_financial_twin(
    twin_in: FinancialTwinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new Financial Twin for the authenticated user.
    Returns HTTP 409 if a twin already exists.
    """
    existing_twin = db.query(FinancialTwin).filter(FinancialTwin.user_id == current_user.id).first()
    if existing_twin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Financial Twin already exists for this user."
        )

    db_twin = FinancialTwin(**twin_in.model_dump(), user_id=current_user.id)
    db.add(db_twin)
    db.commit()
    db.refresh(db_twin)
    return db_twin


@router.get("/financial-twin", response_model=FinancialTwinResponse)
def get_financial_twin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the Financial Twin of the authenticated user.
    """
    twin = db.query(FinancialTwin).filter(FinancialTwin.user_id == current_user.id).first()
    if not twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial Twin not found."
        )
    return twin


@router.put("/financial-twin", response_model=FinancialTwinResponse)
def update_financial_twin(
    twin_in: FinancialTwinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates the Financial Twin of the authenticated user.
    """
    db_twin = db.query(FinancialTwin).filter(FinancialTwin.user_id == current_user.id).first()
    if not db_twin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial Twin not found."
        )

    update_data = twin_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_twin, key, value)

    db.add(db_twin)
    db.commit()
    db.refresh(db_twin)
    return db_twin


# --- INCOME ROUTER ---

@router.post("/income", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
def add_income(
    income_in: IncomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adds a new income stream.
    """
    db_income = Income(**income_in.model_dump(), user_id=current_user.id)
    db.add(db_income)
    db.commit()
    db.refresh(db_income)
    return db_income


@router.get("/income", response_model=List[IncomeResponse])
def get_income_streams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves all income streams of the authenticated user.
    """
    return db.query(Income).filter(Income.user_id == current_user.id).all()


@router.put("/income/{income_id}", response_model=IncomeResponse)
def update_income(
    income_id: UUID,
    income_in: IncomeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates an existing income stream.
    """
    db_income = db.query(Income).filter(Income.id == income_id, Income.user_id == current_user.id).first()
    if not db_income:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income stream not found.")
    for key, value in income_in.model_dump(exclude_unset=True).items():
        setattr(db_income, key, value)
    db.commit()
    db.refresh(db_income)
    return db_income


@router.delete("/income/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes an existing income stream.
    """
    db_income = db.query(Income).filter(Income.id == income_id, Income.user_id == current_user.id).first()
    if not db_income:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income stream not found.")
    db.delete(db_income)
    db.commit()
    return None


# --- EXPENSES ROUTER ---

@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def add_expense(
    expense_in: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adds a new expense.
    """
    db_expense = Expense(**expense_in.model_dump(), user_id=current_user.id)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


@router.get("/expenses", response_model=List[ExpenseResponse])
def get_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves all expenses of the authenticated user.
    """
    return db.query(Expense).filter(Expense.user_id == current_user.id).all()


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: UUID,
    expense_in: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates an existing expense.
    """
    db_expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not db_expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
    for key, value in expense_in.model_dump(exclude_unset=True).items():
        setattr(db_expense, key, value)
    db.commit()
    db.refresh(db_expense)
    return db_expense


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes an existing expense.
    """
    db_expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not db_expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
    db.delete(db_expense)
    db.commit()
    return None


# --- ASSETS ROUTER ---

@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def add_asset(
    asset_in: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adds a new asset.
    """
    db_asset = Asset(**asset_in.model_dump(), user_id=current_user.id)
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset


@router.get("/assets", response_model=List[AssetResponse])
def get_assets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves all assets of the authenticated user.
    """
    return db.query(Asset).filter(Asset.user_id == current_user.id).all()


@router.put("/assets/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: UUID,
    asset_in: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates an existing asset.
    """
    db_asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not db_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    for key, value in asset_in.model_dump(exclude_unset=True).items():
        setattr(db_asset, key, value)
    db.commit()
    db.refresh(db_asset)
    return db_asset


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes an existing asset.
    """
    db_asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not db_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    db.delete(db_asset)
    db.commit()
    return None


# --- LIABILITIES ROUTER ---

@router.post("/liabilities", response_model=LiabilityResponse, status_code=status.HTTP_201_CREATED)
def add_liability(
    liability_in: LiabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adds a new liability.
    """
    db_liability = Liability(**liability_in.model_dump(), user_id=current_user.id)
    db.add(db_liability)
    db.commit()
    db.refresh(db_liability)
    return db_liability


@router.get("/liabilities", response_model=List[LiabilityResponse])
def get_liabilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves all liabilities of the authenticated user.
    """
    return db.query(Liability).filter(Liability.user_id == current_user.id).all()


@router.put("/liabilities/{liability_id}", response_model=LiabilityResponse)
def update_liability(
    liability_id: UUID,
    liability_in: LiabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates an existing liability.
    """
    db_liability = db.query(Liability).filter(Liability.id == liability_id, Liability.user_id == current_user.id).first()
    if not db_liability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liability not found.")
    for key, value in liability_in.model_dump(exclude_unset=True).items():
        setattr(db_liability, key, value)
    db.commit()
    db.refresh(db_liability)
    return db_liability


@router.delete("/liabilities/{liability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_liability(
    liability_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes an existing liability.
    """
    db_liability = db.query(Liability).filter(Liability.id == liability_id, Liability.user_id == current_user.id).first()
    if not db_liability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liability not found.")
    db.delete(db_liability)
    db.commit()
    return None


# --- FINANCIAL GOALS ROUTER ---

@router.post("/goals", response_model=FinancialGoalResponse, status_code=status.HTTP_201_CREATED)
def add_goal(
    goal_in: FinancialGoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adds a new financial goal.
    """
    db_goal = FinancialGoal(**goal_in.model_dump(), user_id=current_user.id)
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


@router.get("/goals", response_model=List[FinancialGoalResponse])
def get_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves all financial goals of the authenticated user.
    """
    return db.query(FinancialGoal).filter(FinancialGoal.user_id == current_user.id).all()


@router.put("/goals/{goal_id}", response_model=FinancialGoalResponse)
def update_goal(
    goal_id: UUID,
    goal_in: FinancialGoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates an existing financial goal.
    """
    db_goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id, FinancialGoal.user_id == current_user.id).first()
    if not db_goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Financial Goal not found.")
    for key, value in goal_in.model_dump(exclude_unset=True).items():
        setattr(db_goal, key, value)
    db.commit()
    db.refresh(db_goal)
    return db_goal


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes an existing financial goal.
    """
    db_goal = db.query(FinancialGoal).filter(FinancialGoal.id == goal_id, FinancialGoal.user_id == current_user.id).first()
    if not db_goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Financial Goal not found.")
    db.delete(db_goal)
    db.commit()
    return None
