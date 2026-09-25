import re
from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import HTTPException, status

from app.parsers.base import BaseParser
from app.schemas import ParsedStatement, ParsedTxn
from app.normalize import (
    parse_decimal_amount,
    parse_single_amount_with_drcr,
    parse_date_with_formats,
    is_skip_row,
    sort_txns_oldest_first,
)
from app.reconcile import reconcile_transactions
from app.parsers.semantic import parse_semantically


class BaseIndianBankParser(BaseParser):
    """
    Base parser for Indian public, private, and payments banks.
    Provides robust multi-column matching with graceful fallback to semantic parsing.
    """
    bank_name: str = "Bank Statement"
    bank_keywords: List[str] = []
    DATE_FORMATS: List[str] = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %b %y",
        "%d %B %Y",
        "%d %B %y",
        "%Y-%m-%d",
    ]

    def detect(self, raw_rows: List[List[str]], filename: str = "") -> bool:
        combined_text = " ".join(" ".join(str(c) for c in row) for row in raw_rows[:150]).lower()
        fn_lower = filename.lower()
        for kw in self.bank_keywords:
            if re.search(kw, combined_text) or re.search(kw, fn_lower):
                return True
        return False

    def _find_columns(self, raw_rows: List[List[str]]) -> tuple[int, dict]:
        col_map = {}
        header_idx = -1

        for idx, row in enumerate(raw_rows[:150]):
            row_lower = [str(c).lower().strip() for c in row]
            temp_map = {}
            for col_i, name in enumerate(row_lower):
                if not name:
                    continue
                if ("date" in name or "txn dt" in name or "tran date" in name) and "date" not in temp_map:
                    temp_map["date"] = col_i
                elif ("narration" in name or "description" in name or "particulars" in name or "details" in name or "remark" in name) and "narration" not in temp_map:
                    temp_map["narration"] = col_i
                elif ("ref" in name or "chq" in name or "utr" in name or "cheque" in name or "txn id" in name) and "ref_no" not in temp_map:
                    temp_map["ref_no"] = col_i
                elif ("withdrawal" in name or "debit" in name or name in ["dr", "dr."]) and "debit" not in temp_map:
                    temp_map["debit"] = col_i
                elif ("deposit" in name or "credit" in name or name in ["cr", "cr."]) and "credit" not in temp_map:
                    temp_map["credit"] = col_i
                elif ("amount" in name or "txn amount" in name) and "amount" not in temp_map and "debit" not in temp_map:
                    temp_map["amount"] = col_i
                elif (name in ["type", "dr/cr", "cr/dr", "txn type"]) and "drcr" not in temp_map:
                    temp_map["drcr"] = col_i
                elif ("balance" in name or "closing" in name or "bal" in name) and "balance" not in temp_map:
                    temp_map["balance"] = col_i

            has_amount = ("debit" in temp_map or "credit" in temp_map or "amount" in temp_map)
            if "date" in temp_map and "narration" in temp_map and has_amount:
                header_idx = idx
                col_map = temp_map
                break

        return header_idx, col_map

    def parse(self, raw_rows: List[List[str]], filename: str = "") -> ParsedStatement:
        header_idx, col_map = self._find_columns(raw_rows)
        if header_idx == -1:
            semantic_res = parse_semantically(raw_rows, self.bank_name, filename, self.DATE_FORMATS)
            if semantic_res and semantic_res.txns:
                return semantic_res
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unable to parse {self.bank_name} statement columns.",
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

            if not parsed_date:
                if txns and narration_clean:
                    txns[-1].narration += " " + narration_clean
                continue

            row_str = " ".join(str(c) for c in row)
            from app.parsers.semantic import extract_amounts_from_text, resolve_debit_credit_balance

            # If row is full-width matching standard columns
            if ("debit" in col_map or "credit" in col_map) and len(row) > max(col_map.get("debit", 0), col_map.get("credit", 0)):
                raw_debit = str(row[col_map["debit"]] if ("debit" in col_map and col_map["debit"] < len(row)) else "").strip()
                raw_credit = str(row[col_map["credit"]] if ("credit" in col_map and col_map["credit"] < len(row)) else "").strip()

                debit = parse_decimal_amount(raw_debit)
                credit = parse_decimal_amount(raw_credit)

                if "cr" in raw_debit.lower() and debit > Decimal("0.00"):
                    credit = debit
                    debit = Decimal("0.00")
                elif "dr" in raw_credit.lower() and credit > Decimal("0.00"):
                    debit = credit
                    credit = Decimal("0.00")

                if "balance" in col_map and col_map["balance"] < len(row):
                    raw_balance = str(row[col_map["balance"]]).strip()
                    balance = parse_decimal_amount(raw_balance)

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
                    running_bal = running_bal + credit - debit
                    balance = running_bal
            elif "amount" in col_map:
                amount_val = row[col_map["amount"]] if col_map["amount"] < len(row) else "0.00"
                drcr_val = row[col_map["drcr"]] if ("drcr" in col_map and col_map["drcr"] < len(row)) else ""
                debit, credit = parse_single_amount_with_drcr(amount_val, drcr_val)
                if "balance" in col_map and col_map["balance"] < len(row):
                    balance = parse_decimal_amount(row[col_map["balance"]])
                    running_bal = balance
                else:
                    running_bal = running_bal + credit - debit
                    balance = running_bal
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
                detail=f"No valid transactions found in {self.bank_name} statement.",
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


class ICICIParser(BaseIndianBankParser):
    bank_name = "ICICI Bank"
    bank_keywords = [r"\bicici bank\b", r"\bicici\b", r"\bicic0\b"]


class AxisParser(BaseIndianBankParser):
    bank_name = "Axis Bank"
    bank_keywords = [r"\baxis bank\b", r"\baxis\b", r"\butib\b"]


class KotakParser(BaseIndianBankParser):
    bank_name = "Kotak Mahindra Bank"
    bank_keywords = [r"\bkotak mahindra\b", r"\bkotak bank\b", r"\bkotak\b", r"\bkkbk\b"]


class PNBParser(BaseIndianBankParser):
    bank_name = "Punjab National Bank (PNB)"
    bank_keywords = [r"\bpunjab national bank\b", r"\bpnb\b", r"\bpunb\b"]


class BankOfBarodaParser(BaseIndianBankParser):
    bank_name = "Bank of Baroda"
    bank_keywords = [r"\bbank of baroda\b", r"\bbarb0\b", r"\bbob\b"]


class CanaraParser(BaseIndianBankParser):
    bank_name = "Canara Bank"
    bank_keywords = [r"\bcanara bank\b", r"\bcanara\b", r"\bcnrb\b"]


class UnionBankParser(BaseIndianBankParser):
    bank_name = "Union Bank of India"
    bank_keywords = [r"\bunion bank of india\b", r"\bunion bank\b", r"\bubin\b"]


class PaytmParser(BaseIndianBankParser):
    bank_name = "Paytm Payments Bank"
    bank_keywords = [r"\bpaytm payments bank\b", r"\bpaytm bank\b", r"\bpaytm\b", r"\bpytm\b"]


class UPIParser(BaseIndianBankParser):
    bank_name = "UPI / Digital Payments"
    bank_keywords = [r"\bphonepe\b", r"\bgoogle pay\b", r"\bgpay\b", r"\bcred\b", r"\bbhim\b", r"\bupi\b"]

    def parse(self, raw_rows: List[List[str]], filename: str = "") -> ParsedStatement:
        combined = " ".join(" ".join(str(c) for c in r) for r in raw_rows[:30]).lower()
        if "phonepe" in combined or "phonepe" in filename.lower():
            self.bank_name = "PhonePe"
        elif "google pay" in combined or "gpay" in combined or "gpay" in filename.lower():
            self.bank_name = "Google Pay"
        elif "cred" in combined or "cred" in filename.lower():
            self.bank_name = "CRED"
        return super().parse(raw_rows, filename)
