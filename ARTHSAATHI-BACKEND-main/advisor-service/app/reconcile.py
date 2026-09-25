from decimal import Decimal
from typing import List, Tuple
from app.schemas import ParsedTxn


def reconcile_transactions(
    txns: List[ParsedTxn],
    explicit_opening_balance: Decimal = None,
) -> Tuple[bool, List[int], List[str]]:
    """
    Validates arithmetic running balance integrity across chronological transactions:
      prev_balance + credit - debit == balance

    Auto-calibrates transactions where column shifting or OCR flipped debit and credit,
    provided the running balance difference mathematically proves the exact transaction amount.

    Uses Decimal exclusively. Returns:
      (reconciled: bool, mismatch_rows: list[int], warnings: list[str])
    """
    if not txns:
        return True, [], []

    mismatch_rows: List[int] = []
    warnings: List[str] = []

    # Calibrate row 0 if narration or indicators obviously conflict with column placement
    if len(txns) > 0:
        t0 = txns[0]
        narr_lower = t0.narration.lower()
        if t0.debit > Decimal("0.00") and t0.credit == Decimal("0.00"):
            if any(k in narr_lower for k in ["salary", "credit interest", "refund", "cashback", "deposited"]):
                t0.credit = t0.debit
                t0.debit = Decimal("0.00")
        elif t0.credit > Decimal("0.00") and t0.debit == Decimal("0.00"):
            if any(k in narr_lower for k in ["billpay dr", "withdrawn", "atm dr", "chq dr", "debit"]):
                t0.debit = t0.credit
                t0.credit = Decimal("0.00")

    # Derive opening balance if none provided explicitly:
    # opening_balance + txns[0].credit - txns[0].debit == txns[0].balance
    # => opening_balance = txns[0].balance - txns[0].credit + txns[0].debit
    if explicit_opening_balance is not None:
        running_balance = explicit_opening_balance.quantize(Decimal("0.01"))
    else:
        running_balance = (txns[0].balance - txns[0].credit + txns[0].debit).quantize(Decimal("0.01"))

    for idx, txn in enumerate(txns):
        actual_balance = txn.balance.quantize(Decimal("0.01"))
        expected_balance = (running_balance + txn.credit - txn.debit).quantize(Decimal("0.01"))

        # If mismatch occurs, check for mathematically provable auto-calibration
        if expected_balance != actual_balance and actual_balance != Decimal("0.00"):
            delta = (actual_balance - running_balance).quantize(Decimal("0.01"))

            # Case 1: Deposit was parsed into Debit (credit == 0)
            # prev_balance + debit == actual_balance
            if txn.debit > Decimal("0.00") and txn.credit == Decimal("0.00"):
                if (running_balance + txn.debit).quantize(Decimal("0.01")) == actual_balance:
                    txn.credit = txn.debit
                    txn.debit = Decimal("0.00")
                    expected_balance = actual_balance
                elif delta > Decimal("0.00") and abs(delta) == txn.debit:
                    txn.credit = txn.debit
                    txn.debit = Decimal("0.00")
                    expected_balance = actual_balance

            # Case 2: Withdrawal was parsed into Credit (debit == 0)
            # prev_balance - credit == actual_balance
            elif txn.credit > Decimal("0.00") and txn.debit == Decimal("0.00"):
                if (running_balance - txn.credit).quantize(Decimal("0.01")) == actual_balance:
                    txn.debit = txn.credit
                    txn.credit = Decimal("0.00")
                    expected_balance = actual_balance
                elif delta < Decimal("0.00") and abs(delta) == txn.credit:
                    txn.debit = txn.credit
                    txn.credit = Decimal("0.00")
                    expected_balance = actual_balance

            # Case 3: Both debit and credit populated (e.g. ghost number from Ref/Chq)
            elif txn.debit > Decimal("0.00") and txn.credit > Decimal("0.00"):
                if (running_balance - txn.debit).quantize(Decimal("0.01")) == actual_balance:
                    txn.credit = Decimal("0.00")
                    expected_balance = actual_balance
                elif (running_balance + txn.credit).quantize(Decimal("0.01")) == actual_balance:
                    txn.debit = Decimal("0.00")
                    expected_balance = actual_balance

            # Case 4: Net balance delta exactly matches one of the amounts or Narration proves direction
            elif delta != Decimal("0.00"):
                if delta > Decimal("0.00") and txn.debit == delta:
                    txn.credit = delta
                    txn.debit = Decimal("0.00")
                    expected_balance = actual_balance
                elif delta < Decimal("0.00") and txn.credit == abs(delta):
                    txn.debit = abs(delta)
                    txn.credit = Decimal("0.00")
                    expected_balance = actual_balance

        # If after calibration balance still mismatches, record diagnostic warning
        if expected_balance != actual_balance and actual_balance != Decimal("0.00"):
            mismatch_rows.append(idx)
            warnings.append(
                f"Row {idx} ({txn.txn_date.isoformat()}): balance mismatch. "
                f"Computed {expected_balance:.2f} (prev {running_balance:.2f} + cr {txn.credit:.2f} - dr {txn.debit:.2f}), "
                f"but statement reports {actual_balance:.2f}."
            )
            # Re-anchor running balance to the statement's reported balance so errors don't cascade indefinitely
            running_balance = actual_balance
        elif actual_balance == Decimal("0.00") and (txn.debit > Decimal("0.00") or txn.credit > Decimal("0.00")):
            # If statement had no balance column on this row, compute it progressively
            txn.balance = expected_balance
            running_balance = expected_balance
        else:
            running_balance = actual_balance

    reconciled = len(mismatch_rows) == 0
    return reconciled, mismatch_rows, warnings

