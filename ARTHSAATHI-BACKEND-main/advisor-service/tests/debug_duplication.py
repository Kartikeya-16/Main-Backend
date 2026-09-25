"""
Diagnostic script to trace the duplicate-row bug.
Run from advisor-service directory:
  source ../.venv/bin/activate && PYTHONPATH=. python tests/debug_duplication.py
"""
import io
import os
import sys

# Create an 11-transaction HDFC CSV fixture in memory
HDFC_11_TXN_CSV = """\
HDFC BANK LTD - STATEMENT OF ACCOUNT
Customer: Debug Test
Account No: 50100999999999

Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/05/24,SALARY CREDITED BY TECH CORP,REF001,01/05/24,,75000.00,75000.00
03/05/24,UPI-SWIGGY-BANGALORE,REF002,03/05/24,1250.00,,73750.00
05/05/24,ELECTRICITY BILL MSEB,REF003,05/05/24,3500.00,,70250.00
07/05/24,DIVIDEND TATA CONSULTANCY,REF004,07/05/24,,2500.00,72750.00
09/05/24,UPI-AMAZON-SHOPPING,REF005,09/05/24,1500.00,,71250.00
11/05/24,NEFT-RENT-PAYMENT,REF006,11/05/24,15000.00,,56250.00
13/05/24,FREELANCE INCOME CREDIT,REF007,13/05/24,,12000.00,68250.00
15/05/24,UPI-ZOMATO-DELIVERY,REF008,15/05/24,350.00,,67900.00
17/05/24,ATM CASH WITHDRAWAL,REF009,17/05/24,5000.00,,62900.00
19/05/24,MUTUAL FUND REDEMPTION,REF010,19/05/24,,8000.00,70900.00
21/05/24,INSURANCE PREMIUM HDFC,REF011,21/05/24,4200.00,,66700.00
"""

def main():
    from app.readers import read_statement_raw, read_csv_in_memory
    from app.parsers.registry import get_parser_for_statement
    from app.reconcile import reconcile_transactions

    print("=" * 80)
    print("DIAGNOSTIC: Tracing 11-transaction HDFC CSV through the pipeline")
    print("=" * 80)

    file_bytes = HDFC_11_TXN_CSV.encode("utf-8")

    # Stage 1: Reader
    raw_rows = read_statement_raw("hdfc_debug.csv", file_bytes)
    print(f"\n[STAGE 1] Reader output: {len(raw_rows)} raw rows")
    for i, r in enumerate(raw_rows):
        print(f"  row[{i}] = {r}")

    # Stage 2: Parser detection
    parser = get_parser_for_statement(raw_rows, filename="hdfc_debug.csv")
    print(f"\n[STAGE 2] Detected parser: {type(parser).__name__} (bank_name={parser.bank_name})")

    # Stage 3: Parser output
    statement = parser.parse(raw_rows, filename="hdfc_debug.csv")
    print(f"\n[STAGE 3] Parser output: {len(statement.txns)} transactions")
    for i, t in enumerate(statement.txns):
        print(f"  txn[{i}] date={t.txn_date} narr={t.narration[:50]:<50} dr={t.debit:>10.2f} cr={t.credit:>10.2f} bal={t.balance:>10.2f}")

    print(f"\n[STAGE 3] Reconciled: {statement.reconciled}")
    print(f"[STAGE 3] Mismatch rows: {statement.mismatch_rows}")
    print(f"[STAGE 3] Warnings: {statement.warnings}")

    # Final check
    expected = 11
    actual = len(statement.txns)
    if actual == expected:
        print(f"\n=== PASS: Got exactly {expected} transactions. No duplication for CSV.")
    elif actual == expected * 2:
        print(f"\n=== FAIL: Got {actual} transactions (2x duplication detected!)")
    else:
        print(f"\n=== UNEXPECTED: Got {actual} transactions (expected {expected})")

    # Now test PDF path
    print("\n" + "=" * 80)
    print("DIAGNOSTIC: Testing with multi-page PDF fixture")
    print("=" * 80)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buf, pagesize=letter)
        styles = getSampleStyleSheet()

        header_row = ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
        data_rows = [
            ["01/05/24", "SALARY CREDITED BY TECH CORP", "REF001", "01/05/24", "", "75000.00", "75000.00"],
            ["03/05/24", "UPI-SWIGGY-BANGALORE", "REF002", "03/05/24", "1250.00", "", "73750.00"],
            ["05/05/24", "ELECTRICITY BILL MSEB", "REF003", "05/05/24", "3500.00", "", "70250.00"],
            ["07/05/24", "DIVIDEND TATA CONSULTANCY", "REF004", "07/05/24", "", "2500.00", "72750.00"],
            ["09/05/24", "UPI-AMAZON-SHOPPING", "REF005", "09/05/24", "1500.00", "", "71250.00"],
            ["11/05/24", "NEFT-RENT-PAYMENT", "REF006", "11/05/24", "15000.00", "", "56250.00"],
            ["13/05/24", "FREELANCE INCOME CREDIT", "REF007", "13/05/24", "", "12000.00", "68250.00"],
            ["15/05/24", "UPI-ZOMATO-DELIVERY", "REF008", "15/05/24", "350.00", "", "67900.00"],
            ["17/05/24", "ATM CASH WITHDRAWAL", "REF009", "17/05/24", "5000.00", "", "62900.00"],
            ["19/05/24", "MUTUAL FUND REDEMPTION", "REF010", "19/05/24", "", "8000.00", "70900.00"],
            ["21/05/24", "INSURANCE PREMIUM HDFC", "REF011", "21/05/24", "4200.00", "", "66700.00"],
        ]

        story = [
            Paragraph("<b>HDFC BANK LTD - ACCOUNT STATEMENT</b>", styles["Heading1"]),
            Paragraph("Account Number: 50100999999999", styles["Normal"]),
            Spacer(1, 10),
        ]

        # Put first 6 txns on page 1
        page1_data = [header_row] + data_rows[:6]
        t1 = Table(page1_data)
        t1.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t1)
        story.append(PageBreak())

        # Remaining 5 txns on page 2 WITH repeated header
        page2_data = [header_row] + data_rows[6:]
        t2 = Table(page2_data)
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t2)
        doc.build(story)

        pdf_bytes = pdf_buf.getvalue()

        raw_rows_pdf = read_statement_raw("hdfc_debug.pdf", pdf_bytes)
        print(f"\n[STAGE 1 - PDF] Reader output: {len(raw_rows_pdf)} raw rows")
        for i, r in enumerate(raw_rows_pdf):
            print(f"  row[{i}] = {r}")

        parser_pdf = get_parser_for_statement(raw_rows_pdf, filename="hdfc_debug.pdf")
        print(f"\n[STAGE 2 - PDF] Detected parser: {type(parser_pdf).__name__}")

        statement_pdf = parser_pdf.parse(raw_rows_pdf, filename="hdfc_debug.pdf")
        print(f"\n[STAGE 3 - PDF] Parser output: {len(statement_pdf.txns)} transactions")
        for i, t in enumerate(statement_pdf.txns):
            print(f"  txn[{i}] date={t.txn_date} narr={t.narration[:50]:<50} dr={t.debit:>10.2f} cr={t.credit:>10.2f} bal={t.balance:>10.2f}")

        print(f"\n[STAGE 3 - PDF] Reconciled: {statement_pdf.reconciled}")
        print(f"[STAGE 3 - PDF] Mismatch rows: {statement_pdf.mismatch_rows}")

        if len(statement_pdf.txns) == 11:
            print(f"\n=== PASS: Got exactly 11 transactions from multi-page PDF.")
        elif len(statement_pdf.txns) == 22:
            print(f"\n=== FAIL: Got 22 transactions from multi-page PDF (2x duplication!)")
        else:
            print(f"\n=== Got {len(statement_pdf.txns)} transactions from multi-page PDF (expected 11)")

    except ImportError:
        print("reportlab not available, skipping PDF test")

    # Check env
    print("\n" + "=" * 80)
    has_ai_key = bool((os.environ.get("OPENROUTER_API_KEY", "")).strip())
    print(f"OPENROUTER_API_KEY present: {has_ai_key}")
    if has_ai_key:
        print("WARNING: AI key is set - main.py will attempt LLM fallback if rule-based is unreconciled!")


if __name__ == "__main__":
    main()
