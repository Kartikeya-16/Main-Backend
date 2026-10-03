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


class SBIParser(BaseParser):
    """
    Parser for State Bank of India (SBI) statements.
    Common columns: Txn Date, Value Date, Description, Ref No./Cheque No., Debit, Credit, Balance
    Date formats: dd-mm-yyyy, dd/mm/yyyy, or dd MMM yyyy
    """
    bank_name = "State Bank of India (SBI)"
    DATE_FORMATS = [
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d %b %Y",
        "%d %b %y",
        "%d %B %Y",
    ]

    def detect(self, raw_rows: List[List[str]], filename: str = "") -> bool:
        header_text = " ".join(" ".join(str(c) for c in row) for row in raw_rows[:6]).lower()
        fn_lower = filename.lower()

        # Do not steal statements with clear other bank branding
        if "hdfc" in header_text or "hdfc" in fn_lower:
            return False

        if "state bank of india" in header_text or bool(re.search(r"\bsbi\b|\bsbin\b", header_text)) or "sbi" in fn_lower:
            return True

        # Check for signature SBI table header row
        for row in raw_rows[:25]:
            row_str = " ".join(str(c).lower() for c in row)
            if "txn date" in row_str and "description" in row_str and ("ref" in row_str or "cheque" in row_str):
                return True
        return False

    def parse(self, raw_rows: List[List[str]], filename: str = "") -> ParsedStatement:
        header_idx = -1
        col_map = {}

        for idx, row in enumerate(raw_rows):
            row_lower = [str(c).lower().strip() for c in row]
            has_date = any("date" in c for c in row_lower)
            has_desc = any("desc" in c or "particular" in c or "narration" in c for c in row_lower)
            has_dr = any(
                "debit" in c or "withdrawal" in c or c in ["dr", "dr."] or bool(re.search(r"\bdr\b|\bdr\.", c))
                for c in row_lower
            )
            has_cr = any(
                "credit" in c or "deposit" in c or c in ["cr", "cr."] or bool(re.search(r"\bcr\b|\bcr\.", c))
                for c in row_lower
            )
            has_bal = any("balance" in c for c in row_lower)

            if has_date and has_desc and (has_dr or has_cr) and has_bal:
                temp_map = {}
                for col_i, col_name in enumerate(row_lower):
                    if ("desc" in col_name or "particular" in col_name or "narration" in col_name) and "narration" not in temp_map:
                        temp_map["narration"] = col_i
                    elif "date" in col_name and "value" not in col_name and "date" not in temp_map:
                        temp_map["date"] = col_i
                    elif ("ref" in col_name or "chq" in col_name or "cheque" in col_name) and "ref_no" not in temp_map:
                        temp_map["ref_no"] = col_i
                    elif (
                        "debit" in col_name
                        or "withdrawal" in col_name
                        or col_name in ["dr", "dr."]
                        or bool(re.search(r"\bdr\b", col_name))
                    ) and "debit" not in temp_map:
                        temp_map["debit"] = col_i
                    elif (
                        "credit" in col_name
                        or "deposit" in col_name
                        or col_name in ["cr", "cr."]
                        or bool(re.search(r"\bcr\b", col_name))
                    ) and "credit" not in temp_map:
                        temp_map["credit"] = col_i
                    elif "balance" in col_name and "balance" not in temp_map:
                        temp_map["balance"] = col_i

                if "date" in temp_map and "narration" in temp_map and "balance" in temp_map and ("debit" in temp_map or "credit" in temp_map):
                    header_idx = idx
                    col_map = temp_map
                    break

        if header_idx == -1 or "date" not in col_map or "narration" not in col_map or "balance" not in col_map:
            # Fallback to semantic line parsing (especially for scanned/OCR statements)
            semantic_res = parse_semantically(raw_rows, self.bank_name, filename, self.DATE_FORMATS)
            if semantic_res and semantic_res.txns:
                return semantic_res

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to find SBI transaction table headers.",
            )

        txns: List[ParsedTxn] = []
        data_rows = raw_rows[header_idx + 1 :]
        running_bal = Decimal("0.00")

        for row in data_rows:
            if not row or all(not str(c).strip() for c in row):
                continue

            if is_skip_row(row):
                continue

            date_val = row[col_map["date"]] if col_map["date"] < len(row) else ""
            parsed_date = parse_date_with_formats(date_val, self.DATE_FORMATS)

            narration_val = row[col_map["narration"]] if col_map["narration"] < len(row) else ""
            narration_clean = re.sub(r"\s+", " ", str(narration_val).strip())

            # Multi-line narration handling
            if not parsed_date:
                if txns and narration_clean:
                    txns[-1].narration += " " + narration_clean
                continue

            row_str = " ".join(str(c) for c in row)
            from app.parsers.semantic import extract_amounts_from_text, resolve_debit_credit_balance

            if "debit" in col_map and "balance" in col_map and len(row) > max(col_map["debit"], col_map["balance"]):
                raw_debit = str(row[col_map["debit"]] if col_map["debit"] < len(row) else "").strip()
                raw_credit = str(row[col_map["credit"]] if ("credit" in col_map and col_map["credit"] < len(row)) else "").strip()
                raw_balance = str(row[col_map["balance"]] if col_map["balance"] < len(row) else "").strip()

                debit = parse_decimal_amount(raw_debit)
                credit = parse_decimal_amount(raw_credit)
                balance = parse_decimal_amount(raw_balance)

                # Honor explicit CR / DR markers inside amount cells
                if "cr" in raw_debit.lower() and debit > Decimal("0.00"):
                    credit = debit
                    debit = Decimal("0.00")
                elif "dr" in raw_credit.lower() and credit > Decimal("0.00"):
                    debit = credit
                    credit = Decimal("0.00")

                # Verify against running balance delta
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
                amounts = extract_amounts_from_text(row_str)
                context = row[col_map["narration"]] if (col_map.get("narration", 1) < len(row)) else row_str
                debit, credit, balance = resolve_debit_credit_balance(amounts, context, txns, running_bal)
                running_bal = balance

            ref_no = None
            if "ref_no" in col_map and col_map["ref_no"] < len(row):
                ref_clean = str(row[col_map["ref_no"]]).strip()
                if ref_clean and ref_clean not in ["-", "--", "NA"]:
                    ref_no = ref_clean

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
                detail="No valid transactions parsed from SBI statement.",
            )

        sorted_txns = sort_txns_oldest_first(txns)
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
