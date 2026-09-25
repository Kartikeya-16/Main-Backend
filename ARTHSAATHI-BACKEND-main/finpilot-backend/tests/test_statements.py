import uuid
import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import get_db
from app.models.statement import Statement, Transaction

client = TestClient(app)


def get_authenticated_user_headers(prefix: str = "statement_user"):
    unique_email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    full_name = "Statement Test User"

    reg_res = client.post(
        "/auth/register",
        json={"email": unique_email, "password": password, "full_name": full_name},
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_statement_upload_requires_jwt():
    res = client.post("/statements/upload")
    assert res.status_code == 401


def test_statement_upload_invalid_file_type():
    headers = get_authenticated_user_headers("invalid_type")
    # Send unsupported file type
    fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
    res = client.post(
        "/statements/upload",
        files={"file": ("malware.exe", fake_exe, "application/x-msdownload")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Invalid file type" in res.json()["detail"]


def test_statement_upload_oversized_file():
    headers = get_authenticated_user_headers("oversized")
    # 10.5 MB payload
    large_bytes = b"0" * (11 * 1024 * 1024)
    res = client.post(
        "/statements/upload",
        files={"file": ("statement.csv", io.BytesIO(large_bytes), "text/csv")},
        headers=headers,
    )
    assert res.status_code == 413
    assert "exceeds" in res.json()["detail"].lower()


@patch("app.api.routes.statements.forward_statement_parse")
def test_statement_upload_and_deduplication_lifecycle(mock_parse):
    headers = get_authenticated_user_headers("lifecycle")

    mock_parse.return_value = {
        "bank": "HDFC Bank",
        "period_start": "2024-05-01",
        "period_end": "2024-05-15",
        "reconciled": True,
        "warnings": [],
        "txns": [
            {
                "txn_date": "2024-05-01",
                "narration": "SALARY CREDITED BY TECH CORP",
                "ref_no": "REF001",
                "debit": "0.00",
                "credit": "80000.00",
                "balance": "80000.00",
            },
            {
                "txn_date": "2024-05-05",
                "narration": "BILL PAYMENT TO ACCOUNT 50100987654321 ELEC",
                "ref_no": "REF002",
                "debit": "2500.00",
                "credit": "0.00",
                "balance": "77500.00",
            },
            {
                "txn_date": "2024-05-10",
                "narration": "MUTUAL FUND SIP DEBIT",
                "ref_no": "REF003",
                "debit": "5000.00",
                "credit": "0.00",
                "balance": "72500.00",
            },
        ],
    }

    # 1. First upload: all 3 should be inserted
    csv_bytes = b"Date,Narration,Withdrawal,Deposit,Balance\n01/05/2024,SALARY,,80000,80000\n"
    res1 = client.post(
        "/statements/upload",
        files={"file": ("statement.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers,
    )
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["bank"] == "HDFC Bank"
    assert data1["txn_count"] == 3
    assert data1["skipped_duplicates"] == 0
    assert data1["reconciled"] is True
    assert data1["totals"]["credit"] == "80000.00"
    assert data1["totals"]["debit"] == "7500.00"

    # Verify PII account masking
    masked_txn = next(t for t in data1["preview"] if "BILL PAYMENT" in t["narration"])
    assert "50100987654321" not in masked_txn["narration"]
    assert "XXXXXXXXXX4321" in masked_txn["narration"]

    statement_id = data1["statement_id"]

    # 2. Second upload with the same transactions: must skip all 3 duplicates!
    res2 = client.post(
        "/statements/upload",
        files={"file": ("statement.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers,
    )
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["txn_count"] == 0
    assert data2["skipped_duplicates"] == 3

    # 3. List statements
    list_res = client.get("/statements", headers=headers)
    assert list_res.status_code == 200
    stmts = list_res.json()
    assert len(stmts) >= 2
    assert any(s["id"] == statement_id for s in stmts)

    # 4. Paginated transactions
    txns_res = client.get(
        f"/statements/{statement_id}/transactions?page=1&size=2",
        headers=headers,
    )
    assert txns_res.status_code == 200
    txns_page = txns_res.json()
    assert txns_page["total"] == 3
    assert txns_page["page"] == 1
    assert txns_page["size"] == 2
    assert len(txns_page["items"]) == 2

    # 5. Delete statement (cascading transactions)
    del_res = client.delete(f"/statements/{statement_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verification: statement transactions now return 404
    txns_after = client.get(f"/statements/{statement_id}/transactions", headers=headers)
    assert txns_after.status_code == 404


@patch("app.api.routes.statements.forward_statement_parse")
def test_multitenant_isolation(mock_parse):
    user_a_headers = get_authenticated_user_headers("user_a")
    user_b_headers = get_authenticated_user_headers("user_b")

    mock_parse.return_value = {
        "bank": "SBI",
        "period_start": "2024-06-01",
        "period_end": "2024-06-15",
        "reconciled": True,
        "warnings": [],
        "txns": [
            {
                "txn_date": "2024-06-01",
                "narration": "OPENING TRANSFER",
                "ref_no": "TX01",
                "debit": "0.00",
                "credit": "50000.00",
                "balance": "50000.00",
            }
        ],
    }

    # Upload as User A
    upload_res = client.post(
        "/statements/upload",
        files={"file": ("user_a_statement.csv", io.BytesIO(b"Date,Narration,Deposit,Balance\n01/06/2024,OPENING,50000,50000\n"), "text/csv")},
        headers=user_a_headers,
    )
    assert upload_res.status_code == 201
    statement_id = upload_res.json()["statement_id"]

    # User B cannot read User A's statement transactions
    get_res = client.get(f"/statements/{statement_id}/transactions", headers=user_b_headers)
    assert get_res.status_code == 404

    # User B cannot delete User A's statement
    del_res = client.delete(f"/statements/{statement_id}", headers=user_b_headers)
    assert del_res.status_code == 404

    # User B's statement list does not contain User A's statement
    list_b = client.get("/statements", headers=user_b_headers).json()
    assert not any(s["id"] == statement_id for s in list_b)
