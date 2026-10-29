import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Date,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
    Uuid,
)
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Statement(Base):
    __tablename__ = "statements"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    bank = Column(String, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    txn_count = Column(Integer, default=0, nullable=False)
    reconciled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="statements")
    transactions = relationship(
        "Transaction",
        back_populates="statement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("statements.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    txn_date = Column(Date, nullable=False)
    narration = Column(String, nullable=False)
    ref_no = Column(String, nullable=True)
    debit = Column(Numeric(12, 2), default=0.00, nullable=False)
    credit = Column(Numeric(12, 2), default=0.00, nullable=False)
    balance = Column(Numeric(12, 2), nullable=False)
    category = Column(String, default="uncategorized", nullable=False)
    dedupe_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    statement = relationship("Statement", back_populates="transactions")
    user = relationship("User", backref="transactions")

    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_hash", name="uq_user_dedupe_hash"),
        Index("ix_transactions_dedupe_hash", "dedupe_hash"),
    )
