import io
import os
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import pypdf

FIXTURES_DIR = os.path.dirname(__file__)


def create_csv_fixtures():
    # 1. HDFC CSV
    hdfc_content = """HDFC BANK LTD - STATEMENT OF ACCOUNT
Customer: Test Customer
Account No: 50100987654321

Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/05/24,SALARY CREDITED BY TECH CORP,REF99201,01/05/24,,75000.00,75000.00
05/05/24,UPI-SWIGGY-BANGALORE,REF11029,05/05/24,1250.00,,73750.00
10/05/24,ELECTRICITY BILL MSEB,REF88291,10/05/24,3500.00,,70250.00
15/05/24,DIVIDEND TATA CONSULTANCY,REF44910,15/05/24,,2500.00,72750.00
"""
    with open(os.path.join(FIXTURES_DIR, "hdfc_sample.csv"), "w", encoding="utf-8") as f:
        f.write(hdfc_content)

    # 2. SBI CSV
    sbi_content = """STATE BANK OF INDIA - ACCOUNT STATEMENT
Branch: Nariman Point Mumbai

Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance
01-06-2024,01-06-2024,OPENING BALANCE TRANSFER,TXN001,,50000.00,50000.00
03-06-2024,03-06-2024,ATM CASH WITHDRAWAL,TXN002,10000.00,,40000.00
12-06-2024,12-06-2024,INTEREST CREDIT,TXN003,,620.00,40620.00
"""
    with open(os.path.join(FIXTURES_DIR, "sbi_sample.csv"), "w", encoding="utf-8") as f:
        f.write(sbi_content)

    # 3. Generic CSV
    generic_content = """Date,Description,Withdrawal,Deposit,Balance
2024-07-01,FREELANCE INVOICE 101,,45000.00,45000.00
2024-07-05,OFFICE RENT LEASE,15000.00,,30000.00
2024-07-10,GROCERY SUPERMARKET,4200.00,,25800.00
"""
    with open(os.path.join(FIXTURES_DIR, "generic_sample.csv"), "w", encoding="utf-8") as f:
        f.write(generic_content)

    # 4. Generic Excel (XLSX)
    df_generic = pd.read_csv(io.StringIO(generic_content))
    df_generic.to_excel(os.path.join(FIXTURES_DIR, "generic_sample.xlsx"), index=False)

    # 5. Multiline Narration CSV
    multiline_content = """Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/05/24,SALARY CREDIT FROM ACME CORP LTD,REF01,01/05/24,,80000.00,80000.00
,EMPLOYEE ID 449201 DEPARTMENT TECH,,,,
,BONUS COMPONENT INCLUDED,,,,
04/05/24,PURCHASE AMAZON INDIA,REF02,04/05/24,4500.00,,75500.00
"""
    with open(os.path.join(FIXTURES_DIR, "multiline_narration.csv"), "w", encoding="utf-8") as f:
        f.write(multiline_content)

    # 6. Tampered Balance CSV (mismatch at row 1)
    tampered_content = """Date,Narration,Withdrawal,Deposit,Balance
01/05/2024,INITIAL CREDIT,,10000.00,10000.00
05/05/2024,GROCERIES,2000.00,,9000.00
10/05/2024,INTEREST,,500.00,9500.00
"""
    with open(os.path.join(FIXTURES_DIR, "tampered_balance.csv"), "w", encoding="utf-8") as f:
        f.write(tampered_content)

    # 7. Newest-First CSV
    newest_first_content = """Date,Narration,Withdrawal,Deposit,Balance
15/05/2024,INTEREST,,500.00,8500.00
10/05/2024,EXPENSE,2000.00,,8000.00
01/05/2024,SALARY,,10000.00,10000.00
"""
    with open(os.path.join(FIXTURES_DIR, "newest_first.csv"), "w", encoding="utf-8") as f:
        f.write(newest_first_content)

    # 8. Unsupported Format
    unsupported_content = """SYSTEM LOG FILE
[2024-05-01 12:00:00] Server started on port 8080
[2024-05-01 12:01:00] Database connected
[2024-05-01 12:02:00] Job finished
"""
    with open(os.path.join(FIXTURES_DIR, "unsupported.txt"), "w", encoding="utf-8") as f:
        f.write(unsupported_content)


def create_pdf_fixtures():
    # Create plain PDF first using ReportLab
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>HDFC BANK LTD - ACCOUNT STATEMENT</b>", styles["Heading1"]),
        Paragraph("Account Number: 50100234567890", styles["Normal"]),
        Spacer(1, 10),
    ]

    data = [
        ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"],
        ["01/05/24", "SALARY CREDITED BY TECH CORP", "REF99201", "01/05/24", "", "75000.00", "75000.00"],
        ["05/05/24", "UPI-SWIGGY-BANGALORE", "REF11029", "05/05/24", "1250.00", "", "73750.00"],
        ["10/05/24", "ELECTRICITY BILL MSEB", "REF88291", "10/05/24", "3500.00", "", "70250.00"],
        ["15/05/24", "DIVIDEND TATA CONSULTANCY", "REF44910", "15/05/24", "", "2500.00", "72750.00"],
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(table)
    doc.build(story)

    unencrypted_pdf_bytes = pdf_buffer.getvalue()

    # Save standard unencrypted PDF
    with open(os.path.join(FIXTURES_DIR, "hdfc_sample.pdf"), "wb") as f:
        f.write(unencrypted_pdf_bytes)

    # Create password-protected PDF using pypdf
    reader = pypdf.PdfReader(io.BytesIO(unencrypted_pdf_bytes))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt("Secret123")
    enc_path = os.path.join(FIXTURES_DIR, "encrypted_sample.pdf")
    with open(enc_path, "wb") as f:
        writer.write(f)


if __name__ == "__main__":
    create_csv_fixtures()
    create_pdf_fixtures()
    print("Synthetic fixtures created successfully in:", FIXTURES_DIR)
