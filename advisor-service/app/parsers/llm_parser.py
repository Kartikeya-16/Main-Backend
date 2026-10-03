import os
import re
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

import httpx
from app.schemas import ParsedTxn, ParsedStatement
from app.normalize import sort_txns_oldest_first
from app.reconcile import reconcile_transactions

logger = logging.getLogger("llm_parser")


async def parse_statement_with_llm(
    raw_rows: List[List[str]],
    file_bytes: Optional[bytes] = None,
    content_type: Optional[str] = None,
    ai_key: Optional[str] = None,
    filename: str = "",
    model: str = "meta-llama/llama-3.3-70b-instruct",
) -> Optional[ParsedStatement]:
    """
    Universal AI statement parser using OpenRouter LLM and Multimodal Vision reasoning.
    Reads and accurately extracts transactions from any document, photo, screenshot,
    or irregular PDF layout with ChatGPT-level comprehension.
    """
    effective_key = ai_key or os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not effective_key:
        return None

    # Flatten raw rows into text representation
    lines = []
    for r in raw_rows:
        if not r:
            continue
        line_str = " | ".join(str(c) for c in r if str(c).strip()).strip()
        if line_str:
            lines.append(line_str)

    raw_text = "\n".join(lines)
    truncated_text = raw_text[:28000]

    system_prompt = (
        "You are an expert financial auditor and automated banking data parser. "
        "Your task is to accurately extract all financial transactions from bank statements, "
        "passbooks, mobile banking screenshots, receipts, or handwritten notes into structured JSON. "
        "You extract every single transaction row without missing any. Read all dates, narrations, debits, credits, and balances precisely."
    )

    user_prompt = f"""Extract all banking transactions from this statement into structured JSON.
File name: {filename}

RAW STATEMENT TEXT / OCR STREAM:
\"\"\"
{truncated_text}
\"\"\"

Return ONLY a JSON object with this exact schema:
{{
  "bank": "Name of the Bank or Financial Institution",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "txns": [
    {{
      "txn_date": "YYYY-MM-DD",
      "narration": "Full narration description of the transaction",
      "ref_no": "Reference / Cheque / UTR / Transaction ID or null",
      "debit": "0.00",
      "credit": "0.00",
      "balance": "0.00"
    }}
  ]
}}

STRICT RULES:
1. "debit", "credit", and "balance" must ALWAYS be formatted as two-decimal numeric strings (e.g. "500.00", "0.00"). Never use null or floating point numbers.
2. If the transaction is a debit/withdrawal/expense, "debit" must be the positive amount and "credit" must be "0.00".
3. If the transaction is a credit/deposit/income, "credit" must be the positive amount and "debit" must be "0.00".
4. If running balance is reported, provide it in "balance". If not reported, compute it progressively.
5. Parse EVERY transaction found in the document chronologically.
6. Output raw JSON ONLY. Do not enclose in markdown ticks, and do not include any explanatory commentary.
"""

    headers = {
        "Authorization": f"Bearer {effective_key}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Arthsaathi AI Parser",
        "Content-Type": "application/json",
    }

    is_image = filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")) or (bool(content_type) and content_type.startswith("image/"))

    # If file is an image and bytes are provided, use Multimodal Vision
    if is_image and file_bytes:
        import base64
        mime = content_type or "image/jpeg"
        if filename.lower().endswith(".webp"):
            mime = "image/webp"
        elif filename.lower().endswith(".png"):
            mime = "image/png"
        elif filename.lower().endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"

        b64 = base64.b64encode(file_bytes).decode("utf-8")
        vision_user_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]

        vision_models = [
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.2-11b-vision-instruct:free",
            "qwen/qwen-2.5-vl-72b-instruct:free",
            "openai/gpt-4o-mini",
        ]

        for v_model in vision_models:
            v_payload = {
                "model": v_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": vision_user_content},
                ],
                "temperature": 0.05,
            }
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=v_payload)
                    if not resp.is_error:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0]["message"]["content"].strip()
                            if content.startswith("```"):
                                content = re.sub(r"^```(?:json)?\s*", "", content)
                                content = re.sub(r"\s*```$", "", content)
                            try:
                                parsed_data = json.loads(content)
                                if parsed_data.get("txns"):
                                    return _build_parsed_statement_from_json(parsed_data)
                            except Exception:
                                pass
            except Exception as e:
                logger.warning(f"Vision model {v_model} attempt error: {e}")

    # Text-based fallback via high-performance LLM
    text_models = [model, "meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-chat"]
    for t_model in text_models:
        payload = {
            "model": t_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.05,
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if not resp.is_error:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0]["message"]["content"].strip()
                        if content.startswith("```"):
                            content = re.sub(r"^```(?:json)?\s*", "", content)
                            content = re.sub(r"\s*```$", "", content)
                        try:
                            parsed_data = json.loads(content)
                            if parsed_data.get("txns"):
                                return _build_parsed_statement_from_json(parsed_data)
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Text model {t_model} attempt error: {e}")

    return None


def _build_parsed_statement_from_json(parsed_data: dict) -> Optional[ParsedStatement]:
    try:
        raw_txns = parsed_data.get("txns", [])
        if not raw_txns:
            return None

        validated_txns: List[ParsedTxn] = []
        for t in raw_txns:
            raw_dt = str(t.get("txn_date", "")).strip()
            try:
                parsed_dt = datetime.strptime(raw_dt[:10], "%Y-%m-%d").date()
            except Exception:
                continue

            narration = str(t.get("narration", "")).strip() or "Transaction"
            ref_no = t.get("ref_no")
            if ref_no:
                ref_no = str(ref_no).strip() or None

            def _to_dec(v) -> Decimal:
                s = re.sub(r"[^\d.]", "", str(v or "0.00"))
                try:
                    return Decimal(s).quantize(Decimal("0.01"))
                except Exception:
                    return Decimal("0.00")

            debit = _to_dec(t.get("debit"))
            credit = _to_dec(t.get("credit"))
            balance = _to_dec(t.get("balance"))

            validated_txns.append(
                ParsedTxn(
                    txn_date=parsed_dt,
                    narration=narration,
                    ref_no=ref_no,
                    debit=debit,
                    credit=credit,
                    balance=balance,
                )
            )

        if not validated_txns:
            return None

        validated_txns = sort_txns_oldest_first(validated_txns)
        reconciled, mismatch_rows, warnings = reconcile_transactions(validated_txns)

        dates = [t.txn_date for t in validated_txns]
        p_start = min(dates)
        p_end = max(dates)
        bank_label = str(parsed_data.get("bank", "")).strip() or "Bank Statement"

        return ParsedStatement(
            bank=bank_label,
            period_start=p_start,
            period_end=p_end,
            txns=validated_txns,
            reconciled=reconciled,
            mismatch_rows=mismatch_rows,
            warnings=warnings,
        )
    except Exception as exc:
        logger.warning(f"Error during LLM statement extraction: {exc}")
        return None
