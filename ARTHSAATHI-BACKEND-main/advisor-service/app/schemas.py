from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_serializer, ConfigDict


class ParsedTxn(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    txn_date: date
    narration: str
    ref_no: Optional[str] = None
    debit: Decimal = Field(default=Decimal("0.00"))
    credit: Decimal = Field(default=Decimal("0.00"))
    balance: Decimal

    @field_serializer("debit", "credit", "balance", when_used="json")
    def serialize_decimal(self, value: Decimal) -> str:
        return f"{value:.2f}"


class ParsedStatement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    bank: str
    period_start: date
    period_end: date
    txns: List[ParsedTxn]
    reconciled: bool
    mismatch_rows: List[int] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
