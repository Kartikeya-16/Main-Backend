from datetime import datetime, date
from uuid import UUID
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.financial_twin import (
    OccupationType,
    EducationLevel,
    MaritalStatus,
    RiskAppetite,
    FrequencyType,
    ExpenseCategory,
    AssetType,
    LiabilityType,
    GoalType,
    GoalPriority,
    GoalStatus,
)


# --- INCOME SCHEMAS ---
class IncomeBase(BaseModel):
    source: str
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    frequency: FrequencyType
    description: Optional[str] = None


class IncomeCreate(IncomeBase):
    pass


class IncomeUpdate(BaseModel):
    source: Optional[str] = None
    amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    frequency: Optional[FrequencyType] = None
    description: Optional[str] = None


class IncomeResponse(IncomeBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- EXPENSE SCHEMAS ---
class ExpenseBase(BaseModel):
    category: ExpenseCategory
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    frequency: FrequencyType
    description: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    category: Optional[ExpenseCategory] = None
    amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    frequency: Optional[FrequencyType] = None
    description: Optional[str] = None


class ExpenseResponse(ExpenseBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- ASSET SCHEMAS ---
class AssetBase(BaseModel):
    asset_type: AssetType
    name: str
    current_value: Decimal = Field(..., max_digits=12, decimal_places=2)
    description: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_type: Optional[AssetType] = None
    name: Optional[str] = None
    current_value: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    description: Optional[str] = None


class AssetResponse(AssetBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- LIABILITY SCHEMAS ---
class LiabilityBase(BaseModel):
    liability_type: LiabilityType
    name: str
    principal_amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    outstanding_amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    emi_amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    interest_rate: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    description: Optional[str] = None

    @field_validator("emi_amount", "interest_rate", mode="before")
    @classmethod
    def sanitize_empty_decimal(cls, v):
        if v == "" or v is None:
            return None
        return v


class LiabilityCreate(LiabilityBase):
    pass


class LiabilityUpdate(BaseModel):
    liability_type: Optional[LiabilityType] = None
    name: Optional[str] = None
    principal_amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    outstanding_amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    emi_amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    interest_rate: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    description: Optional[str] = None


class LiabilityResponse(LiabilityBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- FINANCIAL GOAL SCHEMAS ---
class FinancialGoalBase(BaseModel):
    title: str
    goal_type: GoalType
    target_amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    current_savings: Decimal = Field(Decimal("0.0"), max_digits=12, decimal_places=2)
    target_date: Optional[date] = None
    priority: GoalPriority
    status: GoalStatus

    @field_validator("target_date", mode="before")
    @classmethod
    def sanitize_empty_date(cls, v):
        if v == "" or v is None:
            return None
        return v


class FinancialGoalCreate(FinancialGoalBase):
    pass


class FinancialGoalUpdate(BaseModel):
    title: Optional[str] = None
    goal_type: Optional[GoalType] = None
    target_amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    current_savings: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    target_date: Optional[date] = None
    priority: Optional[GoalPriority] = None
    status: Optional[GoalStatus] = None

    @field_validator("target_date", mode="before")
    @classmethod
    def sanitize_empty_update_date(cls, v):
        if v == "" or v is None:
            return None
        return v


class FinancialGoalResponse(FinancialGoalBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- FINANCIAL TWIN SCHEMAS ---
class FinancialTwinBase(BaseModel):
    occupation: str
    occupation_type: OccupationType
    monthly_income: Decimal = Field(..., max_digits=12, decimal_places=2)
    state: str
    city: str
    age: int = Field(..., ge=0)
    education_level: EducationLevel
    marital_status: MaritalStatus
    dependents_count: int = Field(0, ge=0)
    has_elderly_parents: bool = False
    risk_appetite: RiskAppetite


class FinancialTwinCreate(FinancialTwinBase):
    pass


class FinancialTwinUpdate(BaseModel):
    occupation: Optional[str] = None
    occupation_type: Optional[OccupationType] = None
    monthly_income: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    state: Optional[str] = None
    city: Optional[str] = None
    age: Optional[int] = Field(None, ge=0)
    education_level: Optional[EducationLevel] = None
    marital_status: Optional[MaritalStatus] = None
    dependents_count: Optional[int] = Field(None, ge=0)
    has_elderly_parents: Optional[bool] = None
    risk_appetite: Optional[RiskAppetite] = None


class FinancialTwinResponse(FinancialTwinBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
