import os
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.readers import read_statement_raw
from app.parsers.registry import get_parser_for_statement
from app.parsers.bank_1 import HDFCParser
from app.parsers.bank_2 import SBIParser
from app.parsers.generic import GenericParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES_DIR, name), "rb") as f:
        return f.read()


def test_hdfc_csv_parsing():
    content = load_fixture("hdfc_sample.csv")
    raw_rows = read_statement_raw("hdfc_sample.csv", content)
    parser = get_parser_for_statement(raw_rows, filename="hdfc_sample.csv")
    
    assert isinstance(parser, HDFCParser)
    statement = parser.parse(raw_rows, filename="hdfc_sample.csv")
    
    assert statement.bank == "HDFC Bank"
    assert len(statement.txns) == 4
    assert statement.reconciled is True
    assert statement.mismatch_rows == []
    
    # Assert Decimal types - strictly no floats
    for t in statement.txns:
        assert isinstance(t.debit, Decimal)
        assert isinstance(t.credit, Decimal)
        assert isinstance(t.balance, Decimal)
        assert not isinstance(t.debit, float)
        assert not isinstance(t.credit, float)
        assert not isinstance(t.balance, float)

    # Check amounts and dates
    assert statement.txns[0].credit == Decimal("75000.00")
    assert statement.txns[0].balance == Decimal("75000.00")
    assert statement.txns[1].debit == Decimal("1250.00")
    assert statement.txns[1].balance == Decimal("73750.00")


def test_sbi_csv_parsing():
    content = load_fixture("sbi_sample.csv")
    raw_rows = read_statement_raw("sbi_sample.csv", content)
    parser = get_parser_for_statement(raw_rows, filename="sbi_sample.csv")
    
    assert isinstance(parser, SBIParser)
    statement = parser.parse(raw_rows, filename="sbi_sample.csv")
    
    assert statement.bank == "State Bank of India (SBI)"
    assert len(statement.txns) == 3
    assert statement.reconciled is True
    assert statement.txns[0].balance == Decimal("50000.00")
    assert statement.txns[1].debit == Decimal("10000.00")
    assert statement.txns[1].balance == Decimal("40000.00")
    assert statement.txns[2].credit == Decimal("620.00")
    assert statement.txns[2].balance == Decimal("40620.00")


def test_generic_csv_parsing():
    content = load_fixture("generic_sample.csv")
    raw_rows = read_statement_raw("generic_sample.csv", content)
    parser = get_parser_for_statement(raw_rows, filename="generic_sample.csv")
    
    assert isinstance(parser, GenericParser)
    statement = parser.parse(raw_rows, filename="generic_sample.csv")
    
    assert len(statement.txns) == 3
    assert statement.reconciled is True
    assert statement.txns[0].credit == Decimal("45000.00")
    assert statement.txns[1].debit == Decimal("15000.00")
    assert statement.txns[2].debit == Decimal("4200.00")


def test_generic_xlsx_parsing():
    content = load_fixture("generic_sample.xlsx")
    raw_rows = read_statement_raw("generic_sample.xlsx", content)
    parser = get_parser_for_statement(raw_rows, filename="generic_sample.xlsx")
    
    assert isinstance(parser, GenericParser)
    statement = parser.parse(raw_rows, filename="generic_sample.xlsx")
    
    assert len(statement.txns) == 3
    assert statement.reconciled is True


def test_pdf_parsing_unencrypted():
    content = load_fixture("hdfc_sample.pdf")
    raw_rows = read_statement_raw("hdfc_sample.pdf", content)
    parser = get_parser_for_statement(raw_rows, filename="hdfc_sample.pdf")
    
    statement = parser.parse(raw_rows, filename="hdfc_sample.pdf")
    assert len(statement.txns) >= 4
    assert statement.reconciled is True


def test_password_protected_pdf():
    content = load_fixture("encrypted_sample.pdf")

    # 1. Without password: must raise HTTP 401
    with pytest.raises(HTTPException) as exc_info:
        read_statement_raw("encrypted_sample.pdf", content, password=None)
    assert exc_info.value.status_code == 401

    # 2. With wrong password: must raise HTTP 422
    with pytest.raises(HTTPException) as exc_info_wrong:
        read_statement_raw("encrypted_sample.pdf", content, password="WrongPassword123")
    assert exc_info_wrong.value.status_code == 422

    # 3. With correct password: must succeed and parse correctly
    raw_rows = read_statement_raw("encrypted_sample.pdf", content, password="Secret123")
    parser = get_parser_for_statement(raw_rows, filename="encrypted_sample.pdf")
    statement = parser.parse(raw_rows, filename="encrypted_sample.pdf")
    assert len(statement.txns) >= 4
    assert statement.reconciled is True


def test_multiline_narration_merged():
    content = load_fixture("multiline_narration.csv")
    raw_rows = read_statement_raw("multiline_narration.csv", content)
    parser = get_parser_for_statement(raw_rows, filename="multiline_narration.csv")
    statement = parser.parse(raw_rows, filename="multiline_narration.csv")

    assert len(statement.txns) == 2
    # Check that line 2 & 3 text was appended to txn 0 narration
    first_narration = statement.txns[0].narration
    assert "SALARY CREDIT" in first_narration
    assert "EMPLOYEE ID 449201" in first_narration
    assert "BONUS COMPONENT INCLUDED" in first_narration


def test_tampered_balance_detected():
    content = load_fixture("tampered_balance.csv")
    raw_rows = read_statement_raw("tampered_balance.csv", content)
    parser = get_parser_for_statement(raw_rows, filename="tampered_balance.csv")
    statement = parser.parse(raw_rows, filename="tampered_balance.csv")

    # Row 1 has tampered balance: prev 10000 - dr 2000 = 8000, but statement reports 9000
    assert statement.reconciled is False
    assert 1 in statement.mismatch_rows
    assert len(statement.warnings) > 0


def test_newest_first_sorted_oldest_first():
    content = load_fixture("newest_first.csv")
    raw_rows = read_statement_raw("newest_first.csv", content)
    parser = get_parser_for_statement(raw_rows, filename="newest_first.csv")
    statement = parser.parse(raw_rows, filename="newest_first.csv")

    # Verify chronological order
    dates = [t.txn_date for t in statement.txns]
    assert dates == sorted(dates)
    assert dates[0] < dates[-1]


def test_unsupported_format_raises_422():
    content = load_fixture("unsupported.txt")
    raw_rows = read_statement_raw("unsupported.txt", content)
    parser = get_parser_for_statement(raw_rows, filename="unsupported.txt")
    with pytest.raises(HTTPException) as exc_info:
        parser.parse(raw_rows, filename="unsupported.txt")
    assert exc_info.value.status_code == 422


def test_sbi_with_dr_cr_amounts_and_dd_mm_yy_dates():
    raw_rows = [
        ["STATE BANK OF INDIA", "STATEMENT OF ACCOUNT"],
        ["Customer Name : BEENA JOSHI", "Address : JOSHI NIWAS NOIDA"],
        ["Available Balance : 115515.630 CR", "Account Description : REGULAR SAVINGS BANK ACCOUNT"],
        ["Txn Date", "Value Date", "Description", "Ref/Cheque No.", "Debit", "Credit", "Balance"],
        ["01-08-23", "01-08-23", "NEFT*ICIC0000393*CMS3461768763*PHYSICSWALLAH", "000000", "-", "164211.00 CR", "171191.04 CR"],
        ["01-08-23", "01-08-23", "COMM - OTHER MISC. SERVICES", "000000", "118.00 DR", "-", "171073.04 CR"],
        ["01-08-23", "01-08-23", "CASH Withdrawn at GCC", "000000", "100.00 DR", "-", "170973.04 CR"],
        ["01-08-23", "01-08-23", "CASH Deposited at GCC", "000000", "-", "100.00 CR", "171073.04 CR"],
        ["01-08-23", "01-08-23", "UPI/DR/321360002810/GIPPark/PYTM/paytm-6453/Oid20", "000000", "25.00 DR", "-", "171048.04 CR"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="sbi_statement.pdf")
    assert isinstance(parser, SBIParser)
    statement = parser.parse(raw_rows, filename="sbi_statement.pdf")
    assert statement.bank == "State Bank of India (SBI)"
    assert len(statement.txns) == 5
    assert statement.reconciled is True
    assert statement.txns[0].credit == Decimal("164211.00")
    assert statement.txns[0].balance == Decimal("171191.04")
    assert statement.txns[1].debit == Decimal("118.00")
    assert statement.txns[1].balance == Decimal("171073.04")
    assert statement.txns[4].debit == Decimal("25.00")
    assert statement.txns[4].balance == Decimal("171048.04")


def test_semantic_fallback_for_scanned_statement():
    # Simulated OCR output without standard tabular header columns
    ocr_rows = [
        ["SBI STATE BANK OF INDIA"],
        ["STATEMENT OF ACCOUNT Date : 04-01-24"],
        ["Customer Name BEENA JOSHI"],
        ["Account Number 37528203798"],
        ["Available Balance 118515630 CR"],
        ["01-08-23 | 01-08-23 SERVICES 000000 | 118.00 DR : 171073.04 CR"],
        ["COMM - OTHER MISC."],
        ["01-08-23 | 01-08-23 CASH Withdrawn at GCC 000000 | 100.00 DR s 170973.04 CR"],
        ["01-08-23 | 01-08-23 CASH Deposited at GCC 000000 - 100.00CR | 171073.04 CR"],
        ["UPUDR/321360002810/GIP"],
        ["01-08-23 | 01-08-23 | petipyTpayimeassoueo | 000000 | 25.00DR : 171048.04 CR"],
        ["0208-23 | 02-08-23 SHeAVeICRWALTAGS 00000 : 15189,00 CR | 183718.04 CR"],
        ["03-08-23 | 03-08-23 | UPYDR'958129562032/AKASH | 99909 | 1000.00 DR : 182718.04 CR"],
    ]
    parser = get_parser_for_statement(ocr_rows, filename="statement_scan.pdf")
    statement = parser.parse(ocr_rows, filename="statement_scan.pdf")
    assert statement.bank == "State Bank of India (SBI)"
    assert len(statement.txns) == 6
    assert statement.txns[0].debit == Decimal("118.00")
    assert statement.txns[0].balance == Decimal("171073.04")
    assert any(t.credit == Decimal("100.00") for t in statement.txns)


def test_space_separated_and_alphanumeric_dates():
    raw_rows = [
        ["ICICI Bank Statement of Account"],
        ["Account: 001101567890"],
        ["01 Aug 2023 Swiggy Food Delivery Bangalore 350.00 DR 12000.00 CR"],
        ["15 September 2023 Netflix Subscription 649.00 DR 25000.00 CR"],
        ["August 25, 2023 Salary Credit from Tech Corp 85000.00 CR 110000.00 CR"],
        ["2024-01-15 Amazon India Shopping 1499.00 DR 50000.00 CR"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="icici_statement.pdf")
    statement = parser.parse(raw_rows, filename="icici_statement.pdf")
    assert statement.bank == "ICICI Bank"
    assert len(statement.txns) == 4
    assert statement.txns[0].txn_date == date(2023, 8, 1)
    assert statement.txns[0].debit == Decimal("350.00")
    assert statement.txns[1].txn_date == date(2023, 8, 25)
    assert statement.txns[1].credit == Decimal("85000.00")


def test_integer_amounts_and_currency_symbols():
    raw_rows = [
        ["PhonePe Statement"],
        ["01-08-2023 Transfer to Mother ₹10000 DR ₹45000 CR"],
        ["02-08-2023 Cash Received ₹500 CR ₹45500 CR"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="phonepe.pdf")
    statement = parser.parse(raw_rows, filename="phonepe.pdf")
    assert statement.bank == "PhonePe"
    assert len(statement.txns) == 2
    assert statement.txns[0].debit == Decimal("10000.00")
    assert statement.txns[0].balance == Decimal("45000.00")
    assert statement.txns[1].credit == Decimal("500.00")


def test_multiline_date_and_amount_pairing():
    raw_rows = [
        ["Mobile Banking Export"],
        ["01 Aug 2023 Swiggy Order 89745 Bangalore"],
        ["350.00 DR 14,750.00 CR"],
        ["02 Aug 2023 Uber Ride CP to Airport"],
        ["850.00 DR 13,900.00 CR"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="mobile_app.pdf")
    statement = parser.parse(raw_rows, filename="mobile_app.pdf")
    assert len(statement.txns) == 2
    assert statement.txns[0].txn_date == date(2023, 8, 1)
    assert statement.txns[0].debit == Decimal("350.00")
    assert statement.txns[0].balance == Decimal("14750.00")
    assert "Swiggy" in statement.txns[0].narration
    assert statement.txns[1].txn_date == date(2023, 8, 2)
    assert statement.txns[1].debit == Decimal("850.00")


def test_generic_table_without_balance_column():
    raw_rows = [
        ["Date", "Narration", "Debit", "Credit"],
        ["01/08/2023", "Coffee Shop", "150.00", "0.00"],
        ["02/08/2023", "Freelance Payment", "0.00", "15000.00"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="credit_card.csv")
    statement = parser.parse(raw_rows, filename="credit_card.csv")
    assert len(statement.txns) == 2
    assert statement.txns[0].debit == Decimal("150.00")
    assert statement.txns[1].credit == Decimal("15000.00")
    assert statement.reconciled is True


def test_multi_bank_detection_and_parsing():
    test_banks = [
        ("ICICI Bank", [["ICICI Bank Statement"], ["01/08/2023", "Swiggy", "350.00", "0.00", "12000.00"]], "icici.csv"),
        ("Axis Bank", [["AXIS BANK Statement of Account"], ["01-08-2023", "Zomato", "450.00", "0.00", "25000.00"]], "axis.csv"),
        ("Kotak Mahindra Bank", [["Kotak Mahindra Bank"], ["01/08/2023", "Uber", "250.00", "0.00", "15000.00"]], "kotak.csv"),
        ("Punjab National Bank (PNB)", [["Punjab National Bank Statement"], ["01-08-2023", "Coffee", "150.00", "0.00", "5000.00"]], "pnb.csv"),
        ("Bank of Baroda", [["Bank of Baroda Statement"], ["01/08/2023", "Tea", "50.00", "0.00", "8000.00"]], "bob.csv"),
        ("Canara Bank", [["Canara Bank Statement"], ["01/08/2023", "Books", "500.00", "0.00", "12000.00"]], "canara.csv"),
        ("Union Bank of India", [["Union Bank of India"], ["01/08/2023", "Rent", "15000.00", "0.00", "40000.00"]], "union.csv"),
        ("Paytm Payments Bank", [["Paytm Payments Bank Statement"], ["01/08/2023", "Recharge", "299.00", "0.00", "1500.00"]], "paytm.csv"),
        ("PhonePe", [["PhonePe Transaction Statement"], ["01/08/2023", "Grocery", "450.00", "0.00", "8500.00"]], "phonepe.csv"),
        ("IndusInd Bank", [["IndusInd Bank Statement"], ["01/08/2023", "Dinner", "1200.00", "0.00", "22000.00"]], "indusind.csv"),
        ("Citibank", [["Citibank Account Statement"], ["01/08/2023", "Flight", "8500.00", "0.00", "65000.00"]], "citi.csv"),
    ]

    for expected_bank, rows, fn in test_banks:
        parser = get_parser_for_statement(rows, filename=fn)
        st = parser.parse(rows, filename=fn)
        assert st.bank == expected_bank
        assert len(st.txns) == 1


def test_handwritten_blank_paper_statement():
    raw_rows = [
        ["Hostel Monthly Expenses for August 2023"],
        ["1/8/2023 Milk 60"],
        ["2/8/2023 Grocery 450 paid"],
        ["3/8/2023 Rent 10000"],
        ["4/8/2023 Petrol 200"],
        ["5/8/2023 Received 5000 from Rohit"],
        ["Evening Snacks 80"],
        ["Coffee 150"],
        ["Got 2000 from Mom"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="blank_paper_notes.jpg")
    statement = parser.parse(raw_rows, filename="blank_paper_notes.jpg")
    assert "Hostel Monthly Expenses" in statement.bank
    assert len(statement.txns) == 8
    assert statement.txns[0].debit == Decimal("60.00")
    assert statement.txns[1].debit == Decimal("450.00")
    assert statement.txns[2].debit == Decimal("10000.00")
    assert any(t.credit == Decimal("5000.00") for t in statement.txns)
    assert any(t.credit == Decimal("2000.00") for t in statement.txns)


def test_dateless_cash_expense_list_on_paper():
    raw_rows = [
        ["Milk 60"],
        ["Vegetables 150"],
        ["Snacks 80"],
        ["Petrol 500"],
        ["Salary from tutoring 4000"],
        ["Medicine 250"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="paper_diary.png")
    statement = parser.parse(raw_rows, filename="paper_diary.png")
    assert len(statement.txns) == 6
    assert statement.txns[0].debit == Decimal("60.00")
    assert statement.txns[1].debit == Decimal("150.00")
    assert any(t.credit == Decimal("4000.00") for t in statement.txns)


def test_casual_dates_without_year_on_paper():
    raw_rows = [
        ["Daily Ledger"],
        ["1 Aug Milk 60"],
        ["2 Aug Bread 40"],
        ["15th August Dinner with friends 850"],
        ["20 Aug Freelance payment 12000 received"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="notes.txt")
    statement = parser.parse(raw_rows, filename="notes.txt")
    assert len(statement.txns) == 4
    assert statement.txns[0].txn_date.month == 8
    assert statement.txns[0].txn_date.day == 1
    assert statement.txns[0].debit == Decimal("60.00")
    assert statement.txns[3].credit == Decimal("12000.00")


def test_blank_paper_image_ocr_end_to_end():
    import io
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    text = """
Monthly Expenses Diary
10/08 Milk 60
11/08 Grocery 450 paid
12/08 Electricity Bill 1200
13/08 Salary 45000 received
14/08 Coffee 150
"""
    draw.text((50, 50), text, fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    raw_rows = read_statement_raw("blank_paper.png", img_bytes)
    assert len(raw_rows) >= 5

    parser = get_parser_for_statement(raw_rows, filename="blank_paper.png")
    statement = parser.parse(raw_rows, filename="blank_paper.png")

    assert "Expenses Diary" in statement.bank
    assert len(statement.txns) == 5
    assert statement.txns[0].debit == Decimal("60.00")
    assert statement.txns[1].debit == Decimal("450.00")
    assert statement.txns[2].debit == Decimal("1200.00")
    assert statement.txns[3].credit == Decimal("45000.00")
    assert statement.txns[4].debit == Decimal("150.00")


def test_cash_receipt_and_inflows():
    raw_rows = [
        ["Hostel Expense Chit"],
        ["Milk 60"],
        ["Eggs 70"],
        ["Bread 40"],
        ["Tea 20"],
        ["Cash from Dad 2000"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="chit.png")
    statement = parser.parse(raw_rows, filename="chit.png")
    assert len(statement.txns) == 5
    assert statement.txns[0].debit == Decimal("60.00")
    assert statement.txns[4].credit == Decimal("2000.00")


def test_hdfc_collapsed_deposit_columns_reconcile():
    """
    Test HDFC statement where Deposit rows have empty Withdrawal column collapsed into 6 cells,
    verifying deposits become Credits and running balance reconciles with 100% accuracy.
    """
    raw_rows = [
        ["HDFC BANK LIMITED", "STATEMENT OF ACCOUNT"],
        ["Date", "Narration", "Chq/Ref No", "Value Dt", "Withdrawal Amt", "Deposit Amt", "Closing Balance"],
        ["02/06/18", "GMITSA/MY0326/19", "000000", "02/06/18", "14955.00", "", "29064.95"],
        ["03/06/18", "IB BILLPAY DR-HDFCPE-5459643563", "000000", "03/06/18", "1285.98", "", "27778.97"],
        ["04/06/18", "NEFT DR-UBIN0539686-RAJU DUBEY-NETBANK", "000000", "04/06/18", "5000.00", "", "22778.97"],
        ["04/06/18", "UPI-9044-6700@UPI-81551", "000000", "04/06/18", "7000.00", "29778.97"],  # Collapsed: 6 items
        ["05/06/18", "EMI 4923306 CHQ 000051", "000000", "05/06/18", "2268.00", "", "27510.97"],
        ["05/06/18", "UPI-9044-6700@UPI-81561", "000000", "05/06/18", "1500.00", "29010.97"],  # Collapsed: 6 items
        ["07/06/18", "EMI 50037630 CHQ 000091", "000000", "07/06/18", "5333.00", "", "23677.97"],
        ["09/06/18", "NHDF6376325463/SBI CARDS", "000000", "09/06/18", "2820.00", "", "20857.97"],
        ["12/06/18", "NHDF6385796167/BILLDKVODAFONEINDIAL", "000000", "12/06/18", "119.18", "", "20738.79"],
        ["18/06/18", "ACH D- TP ACH HOME-9750", "000000", "18/06/18", "2284.98", "", "18453.81"],
        ["18/06/18", "NEFT DR-VIB0005051-PANKAJ KUMAR", "000000", "18/06/18", "4000.00", "", "14453.81"],
        ["19/06/18", "UPI-9044-6700@UPI-81701", "000000", "19/06/18", "2300.00", "16753.81"],  # Collapsed: 6 items
        ["19/06/18", "NHDF6406143679/BILLDKKOTAKCARDS", "000000", "19/06/18", "11445.00", "", "5308.81"],
        ["22/06/18", "ACH D- HOMECRIND FINPVT LTD", "000000", "22/06/18", "1315.00", "", "3993.81"],
        ["26/06/18", "POS 4160218060 DCSIRELIANCE POS DE", "000000", "26/06/18", "1760.00", "", "2233.81"],
        ["27/06/18", "NEFT DR-UBIN0539686-RAJU DUBEY", "000000", "27/06/18", "1000.00", "", "1233.81"],
        ["01/07/18", "CREDIT INTEREST CAPITALISED", "000000", "01/07/18", "", "156.00", "1389.81"],
        ["02/07/18", "MICRO ATM CASH DEP - HDFC", "000000", "02/07/18", "", "10000.00", "11389.81"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="hdfc_statement.pdf")
    statement = parser.parse(raw_rows, filename="hdfc_statement.pdf")

    assert statement.bank == "HDFC Bank"
    # Row 3 (UPI): must be Credit 7000.00, NOT Debit
    assert statement.txns[3].credit == Decimal("7000.00")
    assert statement.txns[3].debit == Decimal("0.00")
    assert statement.txns[3].balance == Decimal("29778.97")

    # Row 5 (UPI): must be Credit 1500.00, NOT Debit
    assert statement.txns[5].credit == Decimal("1500.00")
    assert statement.txns[5].debit == Decimal("0.00")
    assert statement.txns[5].balance == Decimal("29010.97")

    # Row 11 (UPI): must be Credit 2300.00, NOT Debit
    assert statement.txns[11].credit == Decimal("2300.00")
    assert statement.txns[11].debit == Decimal("0.00")
    assert statement.txns[11].balance == Decimal("16753.81")

    # Reconciled status
    assert statement.reconciled is True
    assert statement.mismatch_rows == []


def test_reconcile_auto_calibration():
    """
    Test that reconcile_transactions automatically calibrates flipped debit/credit fields.
    """
    from app.schemas import ParsedTxn
    from app.reconcile import reconcile_transactions

    # Simulated transactions where row 1 was parsed as debit but balance increased by 5000
    txns = [
        ParsedTxn(
            txn_date=date(2024, 1, 1),
            narration="Opening Balance",
            ref_no=None,
            debit=Decimal("0.00"),
            credit=Decimal("10000.00"),
            balance=Decimal("10000.00"),
        ),
        ParsedTxn(
            txn_date=date(2024, 1, 2),
            narration="Client Payment Inward",
            ref_no=None,
            debit=Decimal("5000.00"),  # Mistakenly set as debit
            credit=Decimal("0.00"),
            balance=Decimal("15000.00"),  # Balance went from 10000 to 15000
        ),
        ParsedTxn(
            txn_date=date(2024, 1, 3),
            narration="Server Hosting Payment",
            ref_no=None,
            debit=Decimal("2000.00"),
            credit=Decimal("0.00"),
            balance=Decimal("13000.00"),
        ),
    ]

    reconciled, mismatches, warnings = reconcile_transactions(txns)
    assert reconciled is True
    assert mismatches == []
    # Row 1 must have been auto-calibrated to credit 5000
    assert txns[1].credit == Decimal("5000.00")
    assert txns[1].debit == Decimal("0.00")


def test_reference_number_not_treated_as_financial_amount():
    """
    Test that reference numbers (like REF 11029) are not treated as debit amount in semantic parsing.
    """
    raw_rows = [
        ["Bank Statement"],
        ["01/05/2024 SALARY CREDIT REF 99201 0.00 75000.00 75000.00"],
        ["05/05/2024 UPI SWIGGY REF 11029 1250.00 73750.00"],
    ]
    parser = get_parser_for_statement(raw_rows, filename="statement.txt")
    statement = parser.parse(raw_rows, filename="statement.txt")

    assert len(statement.txns) == 2
    assert statement.txns[0].credit == Decimal("75000.00")
    assert statement.txns[1].debit == Decimal("1250.00")
    assert statement.txns[1].credit == Decimal("0.00")
    assert statement.txns[1].balance == Decimal("73750.00")
    assert statement.reconciled is True




