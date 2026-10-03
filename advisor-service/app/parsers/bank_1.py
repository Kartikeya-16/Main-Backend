import re
from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import HTTPException, status

from app.parsers.base import BaseParser
from app.schemas import ParsedStatement, ParsedTxn
from app.normalize import (
    parse_decimal_amount,
    parse_date_with_formats,
    is_skip_row,
    sort_txns_oldest_first,
)
from app.reconcile import reconcile_transactions
from app.parsers.semantic import parse_semantically


class HDFCParser(BaseParser):
    """
    Parser for HDFC Bank statements (CSV, Excel, PDF).
    Common columns: Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt., Deposit Amt., Closing Balance
    Date formats: dd/mm/yy or dd/mm/yyyy
    """
    bank_name = "HDFC Bank"
    DATE_FORMATS = ["%d/%m/%y", "%d/%m/%Y"]

    def detect(self, raw_rows: List[List[str]], filename: str = "") -> bool:
        # Check document header branding (first 6 rows) or filename
        header_text = " ".join(" ".join(str(c) for c in row) for row in raw_rows[:6]).lower()
        fn_lower = filename.lower()

        if "hdfc bank" in header_text or "hdfc" in header_text or "hdfc" in fn_lower:
            return True

        # Check for signature HDFC headers in table header row
        for row in raw_rows[:25]:
            row_str = " ".join(str(c).lower() for c in row)
            if "narration" in row_str and "withdrawal" in row_str and "closing balance" in row_str:
                return True
        return False

    def parse(self, raw_rows: List[List[str]], filename: str = "") -> ParsedStatement:
        # 1. Locate header row
        header_idx = -1
        col_map = {}

        for idx, row in enumerate(raw_rows[:150]):
            row_lower = [str(c).lower().strip() for c in row]
            has_date = any("date" in c for c in row_lower)
            has_narration = any("narration" in c or "particular" in c for c in row_lower)
            has_withdrawal = any("withdrawal" in c or "debit" in c for c in row_lower)
            has_deposit = any("deposit" in c or "depost" in c or "credit" in c for c in row_lower)
            has_balance = any("balance" in c or "closing" in c for c in row_lower)

            if has_date and has_narration and (has_withdrawal or has_deposit or has_balance):
                header_idx = idx
                for col_i, col_name in enumerate(row_lower):
                    if "date" in col_name and "value" not in col_name and "date" not in col_map:
                        col_map["date"] = col_i
                    elif ("narration" in col_name or "particular" in col_name) and "narration" not in col_map:
                        col_map["narration"] = col_i
                    elif ("chq" in col_name or "ref" in col_name) and "ref_no" not in col_map:
                        col_map["ref_no"] = col_i
                    elif "value" in col_name and "val_date" not in col_map:
                        col_map["val_date"] = col_i
                    elif ("withdrawal" in col_name or "debit" in col_name) and "debit" not in col_map:
                        col_map["debit"] = col_i
                    elif ("deposit" in col_name or "depost" in col_name or "credit" in col_name) and "credit" not in col_map:
                        col_map["credit"] = col_i
                    elif ("closing" in col_name or "balance" in col_name) and "balance" not in col_map:
                        col_map["balance"] = col_i
                break

        if header_idx == -1 or "date" not in col_map or "narration" not in col_map:
            semantic_res = parse_semantically(raw_rows, self.bank_name, filename, self.DATE_FORMATS)
            if semantic_res and semantic_res.txns:
                return semantic_res

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to find HDFC transaction table headers.",
            )

        txns: List[ParsedTxn] = []
        data_rows = raw_rows[header_idx + 1 :]
        running_bal = Decimal("0.00")

        for row in data_rows:
            if not row or all(not str(c).strip() for c in row):
                continue

            # Check if this row is a repeated header or footer
            if is_skip_row(row):
                continue

            date_val = row[col_map["date"]] if col_map["date"] < len(row) else ""
            parsed_date = parse_date_with_formats(date_val, self.DATE_FORMATS)

            # Fallback to row[0], Value Date column, or last column if OCR missed date column delimiter
            if not parsed_date and len(row) > 0 and col_map["date"] != 0:
                parsed_date = parse_date_with_formats(row[0], self.DATE_FORMATS)
            if not parsed_date and "val_date" in col_map and col_map["val_date"] < len(row):
                parsed_date = parse_date_with_formats(row[col_map["val_date"]], self.DATE_FORMATS)
            if not parsed_date and len(row) > 1:
                parsed_date = parse_date_with_formats(row[-1], self.DATE_FORMATS)
            if not parsed_date:
                m = re.search(r"\b[0-3]?\d[/.-]?[0-1]?\d[/.-]?\d{2,4}\b", row[0] if len(row) > 0 else "")
                if m:
                    parsed_date = parse_date_with_formats(m.group(0), self.DATE_FORMATS)

            narration_val = row[col_map["narration"]] if col_map["narration"] < len(row) else row[0]
            narration_clean = re.sub(r"\s+", " ", str(narration_val).strip())

            # Multi-line narration handling
            if not parsed_date:
                if txns and narration_clean and not any(k in narration_clean.lower() for k in ["closing balance", "page no", "hdfc bank"]):
                    txns[-1].narration += " " + narration_clean
                continue

            # Parse amounts: handle full-width rows vs collapsed/shifted rows
            row_str = " ".join(str(c) for c in row)
            from app.parsers.semantic import extract_amounts_from_text, resolve_debit_credit_balance

            # If row has all expected columns matching the header layout
            if "debit" in col_map and "balance" in col_map and len(row) > max(col_map["debit"], col_map["balance"]):
                debit_val = row[col_map["debit"]] if col_map["debit"] < len(row) else "0.00"
                credit_val = row[col_map["credit"]] if ("credit" in col_map and col_map["credit"] < len(row)) else "0.00"
                balance_val = row[col_map["balance"]] if col_map["balance"] < len(row) else "0.00"

                debit = parse_decimal_amount(debit_val)
                credit = parse_decimal_amount(credit_val)
                balance = parse_decimal_amount(balance_val)

                # Verify against running balance: detect if empty withdrawal column collapsed and shifted deposit into debit
                if running_bal > Decimal("0.00") and balance > Decimal("0.00"):
                    if debit > Decimal("0.00") and credit == Decimal("0.00"):
                        if (running_bal + debit) == balance or balance > running_bal:
                            credit = debit
                            debit = Decimal("0.00")
                    elif credit > Decimal("0.00") and debit == Decimal("0.00"):
                        if (running_bal - credit) == balance or balance < running_bal:
                            debit = credit
                            credit = Decimal("0.00")

                running_bal = balance if balance > Decimal("0.00") else (running_bal + credit - debit)
            else:
                # Row has fewer columns than header (e.g. empty withdrawal cell collapsed in text/OCR)
                amounts = extract_amounts_from_text(row_str)
                context = row[col_map["narration"]] if (col_map.get("narration", 1) < len(row)) else row_str
                debit, credit, balance = resolve_debit_credit_balance(amounts, context, txns, running_bal)
                running_bal = balance

            # Contextual keyword check on narration to catch any remaining inversions
            n_low = narration_clean.lower()
            if any(k in n_low for k in ["salary", "credit interest", "cash dep", "refund", "cashback"]):
                if debit > Decimal("0.00") and credit == Decimal("0.00"):
                    credit = debit
                    debit = Decimal("0.00")
            elif any(k in n_low for k in ["billpay dr", "atm dr", "neft dr", "withdrawal"]):
                if credit > Decimal("0.00") and debit == Decimal("0.00"):
                    debit = credit
                    credit = Decimal("0.00")

            ref_no = None
            if "ref_no" in col_map and col_map["ref_no"] < len(row):
                ref_clean = str(row[col_map["ref_no"]]).strip()
                if ref_clean and ref_clean not in ["-", "--", "NA"]:
                    ref_no = ref_clean

            # Skip empty transaction lines
            if debit == Decimal("0.00") and credit == Decimal("0.00") and balance == Decimal("0.00"):
                continue

            txns.append(
                ParsedTxn(
                    txn_date=parsed_date,
                    narration=narration_clean,
                    ref_no=ref_no,
                    debit=debit,
                    credit=credit,
                    balance=balance,
                )
            )

        if not txns:
            semantic_res = parse_semantically(raw_rows, self.bank_name, filename, self.DATE_FORMATS)
            if semantic_res and semantic_res.txns:
                return semantic_res

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No valid transactions parsed from HDFC statement.",
            )

        # Sort chronologically oldest-first
        sorted_txns = sort_txns_oldest_first(txns)

        # Reconcile running balances
        reconciled, mismatch_rows, warnings = reconcile_transactions(sorted_txns)

        period_start = min(t.txn_date for t in sorted_txns)
        period_end = max(t.txn_date for t in sorted_txns)

        return ParsedStatement(
            bank=self.bank_name,
            period_start=period_start,
            period_end=period_end,
            txns=sorted_txns,
            reconciled=reconciled,
            mismatch_rows=mismatch_rows,
            warnings=warnings,
        )
