import uuid
import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, Numeric, ForeignKey, Enum as SQLEnum, func, Uuid
from sqlalchemy.orm import relationship
from app.database.connection import Base


# Python enums for DB-level enforcement via SQLEnum
class OccupationType(str, enum.Enum):
    SALARIED = "SALARIED"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    BUSINESS = "BUSINESS"
    FREELANCER = "FREELANCER"
    STUDENT = "STUDENT"
    RETIRED = "RETIRED"
    OTHER = "OTHER"


class EducationLevel(str, enum.Enum):
    HIGH_SCHOOL = "HIGH_SCHOOL"
    GRADUATE = "GRADUATE"
    POST_GRADUATE = "POST_GRADUATE"
    OTHER = "OTHER"


class MaritalStatus(str, enum.Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"


class RiskAppetite(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FrequencyType(str, enum.Enum):
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    ANNUAL = "ANNUAL"
    ONE_TIME = "ONE_TIME"


class ExpenseCategory(str, enum.Enum):
    HOUSING = "HOUSING"
    FOOD = "FOOD"
    TRANSPORT = "TRANSPORT"
    UTILITIES = "UTILITIES"
    HEALTHCARE = "HEALTHCARE"
    EDUCATION = "EDUCATION"
    ENTERTAINMENT = "ENTERTAINMENT"
    CLOTHING = "CLOTHING"
    PERSONAL_CARE = "PERSONAL_CARE"
    INSURANCE = "INSURANCE"
    OTHER = "OTHER"


class AssetType(str, enum.Enum):
    REAL_ESTATE = "REAL_ESTATE"
    VEHICLE = "VEHICLE"
    SAVINGS = "SAVINGS"
    STOCKS = "STOCKS"
    MUTUAL_FUNDS = "MUTUAL_FUNDS"
    GOLD = "GOLD"
    FIXED_DEPOSIT = "FIXED_DEPOSIT"
    CRYPTO = "CRYPTO"
    OTHER = "OTHER"


class LiabilityType(str, enum.Enum):
    HOME_LOAN = "HOME_LOAN"
    CAR_LOAN = "CAR_LOAN"
    PERSONAL_LOAN = "PERSONAL_LOAN"
    EDUCATION_LOAN = "EDUCATION_LOAN"
    CREDIT_CARD = "CREDIT_CARD"
    OTHER = "OTHER"


class GoalType(str, enum.Enum):
    EMERGENCY_FUND = "EMERGENCY_FUND"
    HOME_PURCHASE = "HOME_PURCHASE"
    VEHICLE_PURCHASE = "VEHICLE_PURCHASE"
    EDUCATION = "EDUCATION"
    RETIREMENT = "RETIREMENT"
    TRAVEL = "TRAVEL"
    WEDDING = "WEDDING"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"


class GoalPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GoalStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACHIEVED = "ACHIEVED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class FinancialTwin(Base):
    __tablename__ = "financial_twins"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    
    occupation = Column(String, nullable=False)
    occupation_type = Column(SQLEnum(OccupationType), nullable=False)
    monthly_income = Column(Numeric(12, 2), nullable=False)
    state = Column(String, nullable=False)
    city = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    education_level = Column(SQLEnum(EducationLevel), nullable=False)
    marital_status = Column(SQLEnum(MaritalStatus), nullable=False)
    dependents_count = Column(Integer, default=0, nullable=False)
    has_elderly_parents = Column(Boolean, default=False, nullable=False)
    risk_appetite = Column(SQLEnum(RiskAppetite), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="financial_twin")


class Income(Base):
    __tablename__ = "income"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    source = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    frequency = Column(SQLEnum(FrequencyType), nullable=False)
    description = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    user = relationship("User", back_populates="income")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    category = Column(SQLEnum(ExpenseCategory), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    frequency = Column(SQLEnum(FrequencyType), nullable=False)
    description = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    user = relationship("User", back_populates="expenses")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    asset_type = Column(SQLEnum(AssetType), nullable=False)
    name = Column(String, nullable=False)
    current_value = Column(Numeric(12, 2), nullable=False)
    description = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    user = relationship("User", back_populates="assets")


class Liability(Base):
    __tablename__ = "liabilities"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    liability_type = Column(SQLEnum(LiabilityType), nullable=False)
    name = Column(String, nullable=False)
    principal_amount = Column(Numeric(12, 2), nullable=False)
    outstanding_amount = Column(Numeric(12, 2), nullable=False)
    emi_amount = Column(Numeric(12, 2), nullable=True)
    interest_rate = Column(Numeric(12, 2), nullable=True)
    description = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    user = relationship("User", back_populates="liabilities")


class FinancialGoal(Base):
    __tablename__ = "financial_goals"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    title = Column(String, nullable=False)
    goal_type = Column(SQLEnum(GoalType), nullable=False)
    target_amount = Column(Numeric(12, 2), nullable=False)
    current_savings = Column(Numeric(12, 2), default=0.0, nullable=False)
    target_date = Column(Date, nullable=True)
    priority = Column(SQLEnum(GoalPriority), nullable=False)
    status = Column(SQLEnum(GoalStatus), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    user = relationship("User", back_populates="financial_goals")
