from typing import Optional
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, status
from app.schemas import ParsedStatement
from app.readers import read_statement_raw
from app.parsers.registry import get_parser_for_statement
from app.parsers.llm_parser import parse_statement_with_llm
from app.advisor.router import router as advisor_router

app = FastAPI(
    title="Arthsaathi Advisor Service",
    description="Bank statement upload, normalization, parsing, and balance reconciliation service",
    version="1.0.0",
)

app.include_router(advisor_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for advisor-service container and Docker orchestration.
    """
    return {"status": "ok", "service": "advisor-service"}


@app.post("/parse", response_model=ParsedStatement, tags=["Statement Parsing"])
async def parse_statement(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    ai_key: Optional[str] = Form(None),
):
    """
    Stateless bank statement parser endpoint.
    Accepts CSV, XLSX, or text-based PDF (optionally encrypted with password).
    Returns normalized transactions, chronological bounds, and reconciliation status.
    Files and passwords are never persisted to disk or logged.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded or filename is missing.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 1. Extract raw tabular rows using memory-only reader
    raw_rows = read_statement_raw(
        filename=file.filename,
        file_bytes=file_bytes,
        password=password,
    )

    if not raw_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any tabular rows from the statement.",
        )

    # 2. Select appropriate parser (HDFC, SBI, or Generic)
    print(f"[PARSE ATTEMPT] filename={file.filename}, rows={len(raw_rows)}, ai_key_present={bool(ai_key)}")
    for i, r in enumerate(raw_rows[:15]):
        print(f"  row[{i}] = {r}")

    import os
    effective_ai_key = (ai_key or "").strip() or os.environ.get("OPENROUTER_API_KEY", "").strip()
    is_image = file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")) or (bool(file.content_type) and file.content_type.startswith("image/"))

    parsed_statement = None
    local_exc = None

    try:
        parser = get_parser_for_statement(raw_rows, filename=file.filename)
        parsed_statement = parser.parse(raw_rows, filename=file.filename)
    except Exception as exc:
        local_exc = exc

    # If AI key is present and (statement is an image, unreconciled, empty, or parsing failed)
    if effective_ai_key and (parsed_statement is None or not parsed_statement.reconciled or len(parsed_statement.txns) == 0 or is_image):
        try:
            llm_res = await parse_statement_with_llm(
                raw_rows=raw_rows,
                file_bytes=file_bytes,
                content_type=file.content_type,
                ai_key=effective_ai_key,
                filename=file.filename,
            )
            if llm_res and llm_res.txns:
                # Prefer LLM if local failed or LLM has better reconciliation / more complete entries
                if parsed_statement is None or (llm_res.reconciled and not parsed_statement.reconciled) or len(llm_res.txns) > len(parsed_statement.txns):
                    return llm_res
        except Exception as ai_exc:
            print(f"[AI PARSE ERROR] {ai_exc}")

    if parsed_statement is not None and parsed_statement.txns:
        return parsed_statement

    if local_exc is not None:
        if isinstance(local_exc, HTTPException):
            raise local_exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Statement parsing error: {str(local_exc)}",
        )

    if parsed_statement is not None:
        return parsed_statement

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unable to parse any financial transactions from this statement.",
    )
