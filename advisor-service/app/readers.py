import io
import re
import csv
from typing import List, Optional, Tuple, Any
import pandas as pd
import pdfplumber
from fastapi import HTTPException, status


def read_csv_in_memory(file_bytes: bytes) -> List[List[str]]:
    """
    Reads a CSV file entirely in memory supporting irregular metadata header rows.
    Handles various encodings (utf-8, latin-1) and delimiter detection.
    """
    for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            content = file_bytes.decode(encoding)
            
            # First try standard CSV reader (handles rows of varying column counts without dropping rows)
            rows: List[List[str]] = []
            # Try common delimiters if comma doesn't produce multi-column tabular data
            sample = content[:4096]
            delimiter = ","
            if "\t" in sample and sample.count("\t") > sample.count(","):
                delimiter = "\t"
            elif ";" in sample and sample.count(";") > sample.count(","):
                delimiter = ";"

            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            for r in reader:
                if r and any(cell.strip() for cell in r):
                    rows.append([cell.strip() for cell in r])
            
            if rows:
                return rows
        except UnicodeDecodeError:
            continue
        except Exception as e:
            continue

    # Fallback to pandas with max columns detection if csv.reader encountered formatting quirks
    for encoding in ["utf-8", "latin-1"]:
        try:
            content = file_bytes.decode(encoding)
            df = pd.read_csv(
                io.StringIO(content),
                dtype=str,
                header=None,
                on_bad_lines="skip",
            ).fillna("")
            return df.values.tolist()
        except Exception:
            continue

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unable to decode and parse CSV statement with supported encodings.",
    )


def read_excel_in_memory(file_bytes: bytes) -> List[List[str]]:
    """
    Reads an Excel (XLSX / XLS) file entirely in memory with all columns as strings.
    """
    try:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            dtype=str,
            header=None,
        )
        df = df.fillna("")
        return df.values.tolist()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse Excel file: {str(e)}",
        )


def _split_text_line_to_cells(line: str) -> List[str]:
    """
    Intelligently splits a raw text or OCR line from a statement into tabular cells.
    Handles columns separated by wide whitespace, header keyword tokens, or trailing numbers.
    """
    line = line.strip()
    if not line:
        return []

    clean_line = re.sub(r"^[^0-9a-zA-Z]+", "", line).strip()

    # 0. If line is pipe-delimited (|) or bracket-delimited, split and expand merged header cells
    normalized_line = re.sub(r"\s*([|\]\[])\s*", " | ", clean_line)
    if normalized_line.count("|") >= 1:
        pipe_parts = [p.strip() for p in normalized_line.split("|") if p.strip()]
        if len(pipe_parts) >= 2:
            expanded = []
            header_kws = ["date", "narration", "particular", "chq", "ref", "value", "val", "withdrawal", "deposit", "depost", "balance", "closing", "amt", "amount"]
            for p in pipe_parts:
                sub = [s.strip(" \t‘\x27\"`") for s in re.split(r"[‘\x27\"`]|(?<=[a-zA-Z.])\s+(?=[A-Z])", p) if s.strip(" \t‘\x27\"`")]
                matched_kws = sum(1 for s in sub if any(k in s.lower() for k in header_kws))
                if len(sub) > 1 and matched_kws >= 2:
                    expanded.extend(sub)
                else:
                    expanded.append(p)

            # Re-merge compound header phrases (e.g. "Value" + "Dt", "Withdrawal" + "Amt.", "Closing" + "Balance")
            tokens = expanded
            merged = []
            skip = False
            for i in range(len(tokens)):
                if skip:
                    skip = False
                    continue
                tok = tokens[i].lower()
                if i + 1 < len(tokens):
                    nxt = tokens[i + 1].lower()
                    if (
                        tok in ["chq", "ref", "txn", "value", "closing", "running", "avail", "withdrawal", "deposit"]
                        and any(k in nxt for k in ["no", "ref", "date", "dt", "bal", "amt"])
                    ):
                        merged.append(f"{tokens[i]} {tokens[i + 1]}")
                        skip = True
                        continue
                merged.append(tokens[i])

            if len(merged) >= 2:
                return merged

    # 1. First check standard wide-whitespace / tab separation
    parts = [p.strip() for p in re.split(r"\s{2,}|\t+", clean_line) if p.strip()]
    if len(parts) >= 3:
        # Check if first element combines date and narration
        date_match = re.match(
            r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\s+(.+)$",
            parts[0],
        )
        if date_match and len(parts) < 6:
            return [date_match.group(1), date_match.group(2)] + parts[1:]
        return parts

    # 2. Check if this is a table header row (e.g. "Date Narration Withdrawal Deposit Balance")
    header_keywords = [
        "date", "narration", "particular", "description", "ref", "chq",
        "debit", "credit", "withdrawal", "deposit", "balance", "closing", "amount", "bal",
    ]
    line_lower = clean_line.lower()
    matched_kw_count = sum(1 for kw in header_keywords if kw in line_lower)
    if matched_kw_count >= 3:
        tokens = [t.strip() for t in clean_line.split() if t.strip()]
        merged = []
        skip = False
        for i in range(len(tokens)):
            if skip:
                skip = False
                continue
            tok = tokens[i].lower()
            if i + 1 < len(tokens):
                nxt = tokens[i + 1].lower()
                if (
                    tok in ["chq", "ref", "txn", "value", "closing", "running", "avail", "withdrawal", "deposit"]
                    and nxt in ["no", "refno", "ref", "date", "dt", "balance", "bal", "amt", "amount"]
                ):
                    merged.append(f"{tokens[i]} {tokens[i + 1]}")
                    skip = True
                    continue
            merged.append(tokens[i])
        if len(merged) >= 3:
            return merged

    # 3. Check if this is a transaction data line starting with a date and ending with numbers
    date_match = re.match(
        r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\s+(.+)$",
        clean_line,
    )
    if date_match:
        dt = date_match.group(1)
        rest = date_match.group(2).strip()
        tokens = rest.split()
        num_indices = []
        for i in range(len(tokens) - 1, -1, -1):
            tok = re.sub(r"[^\d.]", "", tokens[i])
            if tok and (tok.replace(".", "").isdigit()):
                num_indices.append(i)
                if len(num_indices) >= 3:
                    break
            else:
                break
        if len(num_indices) >= 1:
            split_point = min(num_indices)
            narration = " ".join(tokens[:split_point])
            nums = tokens[split_point:]
            return [dt, narration] + nums

    # 4. Smart fallback: split before decimal numbers or Dr/Cr indicators
    smart_parts = [
        p.strip()
        for p in re.split(r"\s{2,}|\t+|\s+(?=[0-9,]+\.[0-9]{2}\b)|\s+(?=\b(?:Dr|Cr)\b)", clean_line)
        if p.strip()
    ]
    if len(smart_parts) >= 3:
        dm = re.match(
            r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\s+(.+)$",
            smart_parts[0],
        )
        if dm:
            return [dm.group(1), dm.group(2)] + smart_parts[1:]
        return smart_parts

    return [clean_line]


def read_pdf_in_memory(file_bytes: bytes, password: Optional[str] = None) -> List[List[str]]:
    """
    Extracts structured tables from PDF entirely in memory.
    Supports password-protected PDFs with clear error handling without logging credentials.
    Uses multi-pass extraction:
      1. Graphical line-based tables (pdfplumber)
      2. Text-aligned tables (pdfplumber text strategy)
      3. Layout text stream parsing with smart line-to-cell splitting
      4. pypdf text extraction fallback
    """
    stream = io.BytesIO(file_bytes)

    # 1. Pre-flight encryption verification with pypdf
    try:
        from pypdf import PdfReader
        pypdf_reader = PdfReader(io.BytesIO(file_bytes))
        if pypdf_reader.is_encrypted:
            if not password:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password required to decrypt this protected PDF statement.",
                )
            decrypt_res = pypdf_reader.decrypt(password)
            if decrypt_res == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid password provided for encrypted PDF statement.",
                )
    except HTTPException:
        raise
    except Exception:
        # If pypdf raises non-HTTP exception on malformed stream, proceed to pdfplumber
        pass

    try:
        pdf_kwargs: dict[str, Any] = {}
        if password:
            pdf_kwargs["password"] = password

        with pdfplumber.open(stream, **pdf_kwargs) as pdf:
            all_rows: List[List[str]] = []
            total_text_len = 0

            for page_idx, page in enumerate(pdf.pages):
                page_rows: List[List[str]] = []

                # Pass 1: Standard line-based table extraction
                try:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row and any(cell is not None and str(cell).strip() for cell in row):
                                    cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                                    if len([c for c in cleaned_row if c]) >= 2:
                                        page_rows.append(cleaned_row)
                except Exception:
                    pass

                # Pass 2: Text-alignment table extraction (for borderless statements)
                if len(page_rows) < 2:
                    try:
                        text_tables = page.extract_tables(table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 5,
                        })
                        if text_tables:
                            for table in text_tables:
                                for row in table:
                                    if row and any(cell is not None and str(cell).strip() for cell in row):
                                        cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                                        if len([c for c in cleaned_row if c]) >= 2:
                                            page_rows.append(cleaned_row)
                    except Exception:
                        pass

                # Pass 3: Layout text extraction with smart column splitting
                if len(page_rows) < 2:
                    text = page.extract_text(layout=True) or page.extract_text()
                    if not text:
                        try:
                            from pypdf import PdfReader
                            reader_fallback = PdfReader(io.BytesIO(file_bytes))
                            if password:
                                reader_fallback.decrypt(password)
                            if page_idx < len(reader_fallback.pages):
                                text = reader_fallback.pages[page_idx].extract_text()
                        except Exception:
                            pass

                    if text:
                        total_text_len += len(text)
                        for line in text.split("\n"):
                            cells = _split_text_line_to_cells(line)
                            if cells:
                                page_rows.append(cells)

                # Pass 4: OCR on scanned PDF page when no digital text exists
                if len(page_rows) < 2:
                    try:
                        import pytesseract
                        from PIL import Image, ImageOps, ImageFilter, ImageEnhance

                        pil_img = None
                        if page.images:
                            try:
                                raw_img_data = page.images[0]["stream"].get_rawdata()
                                pil_img = Image.open(io.BytesIO(raw_img_data))
                            except Exception:
                                pil_img = None

                        if pil_img is None:
                            pil_img = page.to_image(resolution=300).original

                        if pil_img is not None:
                            pil_img = ImageOps.exif_transpose(pil_img)
                            if pil_img.mode != "RGB":
                                pil_img = pil_img.convert("RGB")

                            # Preprocess with autocontrast and sharpening for maximum digit clarity
                            gray = ImageOps.grayscale(pil_img)
                            gray_auto = ImageOps.autocontrast(gray)
                            sharp_gray = gray_auto.filter(ImageFilter.SHARPEN)

                            ocr_text = pytesseract.image_to_string(sharp_gray, config=r"--oem 3 --psm 4")
                            if not ocr_text or len(ocr_text.strip()) < 10:
                                ocr_text = pytesseract.image_to_string(sharp_gray, config=r"--oem 3 --psm 6")
                            if not ocr_text or len(ocr_text.strip()) < 10:
                                ocr_text = pytesseract.image_to_string(pil_img, config=r"--oem 3 --psm 3")

                            if ocr_text:
                                total_text_len += len(ocr_text)
                                for line in ocr_text.split("\n"):
                                    cells = _split_text_line_to_cells(line)
                                    if cells:
                                        page_rows.append(cells)
                    except Exception:
                        pass

                all_rows.extend(page_rows)

            if not all_rows:
                if total_text_len == 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="No selectable text or readable table found in PDF. If this is a photo/scan, please ensure it is clear and upright, or upload a digital PDF/CSV/Excel statement.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No readable tabular transaction data found in PDF.",
                )

            return all_rows

    except HTTPException:
        # Re-raise explicit HTTP exceptions directly without masking
        raise
    except Exception as exc:
        err_repr = repr(exc).lower()
        err_msg = str(exc).lower()

        # Check for password/decryption error in exception type or representation
        is_pw_err = (
            "password" in err_repr
            or "password" in err_msg
            or "decrypt" in err_repr
            or "encrypt" in err_repr
            or "authenticate" in err_repr
        )

        if is_pw_err:
            if not password:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password required to decrypt this protected PDF statement.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid password provided for encrypted PDF statement.",
                )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error reading PDF file: {str(exc)}",
        )


def read_image_in_memory(file_bytes: bytes) -> List[List[str]]:
    """
    Extracts tabular text lines from an image (PNG, JPEG, WEBP, BMP) using OCR.
    Preprocesses the image (grayscale, contrast enhancement) and applies intelligent cell splitting.
    """
    try:
        from PIL import Image, ImageOps, ImageEnhance
        import pytesseract
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR dependencies (Pillow, pytesseract) are not available on this system.",
        )

    try:
        image = Image.open(io.BytesIO(file_bytes))
        # Handle phone camera EXIF rotation so photos are upright
        image = ImageOps.exif_transpose(image)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file: {str(exc)}",
        )

    # Pre-processing for optimal OCR readability
    try:
        if image.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            bg.paste(image, mask=image.split()[-1] if len(image.split()) == 4 else None)
            image = bg
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Dynamic dimension scaling for optimal OCR recognition (ensure 150-300 DPI clarity)
        from PIL import ImageFilter
        w, h = image.size
        if max(w, h) > 3200:
            scale = 3200 / max(w, h)
            image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        elif max(w, h) < 1800:
            image = image.resize((w * 2, h * 2), Image.Resampling.LANCZOS)

        # Multi-pass OCR with intelligent structure and content scoring
        # Multi-pass OCR with intelligent structure and content scoring
        def _score_ocr_text(t: str, is_psm_4: bool = False) -> int:
            if not t or not t.strip():
                return 0
            score = 0
            t_lower = t.lower()
            for kw in ["date", "narration", "particular", "chq", "ref", "withdrawal", "deposit", "depost", "balance", "closing", "debit", "credit"]:
                if kw in t_lower:
                    score += 20
            # Header bonus: if both date and narration and (withdrawal/deposit/balance) are present
            if "date" in t_lower and ("narration" in t_lower or "particular" in t_lower) and any(k in t_lower for k in ["withdrawal", "deposit", "depost", "balance", "closing", "debit", "credit"]):
                score += 150
            if is_psm_4:
                score += 60
            score += min(t.count("|") * 3, 100)
            score += min(len(re.findall(r"\d+\.\d{2}\b", t)) * 4, 80)
            score += min(len(re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", t)) * 6, 80)
            return score

        # Prepare sharpened grayscale version (eliminates JPEG/WebP compression blur)
        gray = ImageOps.grayscale(image)
        gray_auto = ImageOps.autocontrast(gray)
        sharp_gray = gray_auto.filter(ImageFilter.SHARPEN)

        # Prepare contrast-enhanced version
        enhancer = ImageEnhance.Contrast(gray_auto)
        processed_img = enhancer.enhance(1.3)

        candidates = []
        # Pass 1: Sharpened grayscale with PSM 4 (best for columnar tables & scan borders)
        try:
            t1 = pytesseract.image_to_string(sharp_gray, config=r"--oem 3 --psm 4")
            candidates.append((_score_ocr_text(t1, is_psm_4=True), len(t1), t1))
        except Exception:
            pass

        # Pass 2: Sharpened grayscale with PSM 6 (uniform text / notes)
        try:
            t2 = pytesseract.image_to_string(sharp_gray, config=r"--oem 3 --psm 6")
            candidates.append((_score_ocr_text(t2, is_psm_4=False), len(t2), t2))
        except Exception:
            pass

        # Pass 3: Processed contrast image with PSM 4
        try:
            t3 = pytesseract.image_to_string(processed_img, config=r"--oem 3 --psm 4")
            candidates.append((_score_ocr_text(t3, is_psm_4=True), len(t3), t3))
        except Exception:
            pass

        # Pass 4: Scaled RGB image with PSM 4
        try:
            t4 = pytesseract.image_to_string(image, config=r"--oem 3 --psm 4")
            candidates.append((_score_ocr_text(t4, is_psm_4=True), len(t4), t4))
        except Exception:
            pass

        # Pass 5: PSM 3 (auto page segmentation)
        try:
            t5 = pytesseract.image_to_string(image, config=r"--oem 3 --psm 3")
            candidates.append((_score_ocr_text(t5), len(t5), t5))
        except Exception:
            pass

        # Sort candidates by score descending, then length descending
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        ocr_text = candidates[0][2] if candidates else ""

    except Exception as exc:
        err_str = str(exc).lower()
        if "tesseract is not installed" in err_str or "no such file" in err_str:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tesseract OCR engine is not configured on the advisor service.",
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"OCR processing failed for this image: {str(exc)}",
        )

    if not ocr_text or not ocr_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No readable text detected in image. Please ensure the statement image is clear, sharp, and well-lit.",
        )

    all_rows: List[List[str]] = []
    for line in ocr_text.split("\n"):
        cells = _split_text_line_to_cells(line)
        if cells:
            all_rows.append(cells)

    if not all_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any transaction rows from image.",
        )

    return all_rows


def read_statement_raw(
    filename: str,
    file_bytes: bytes,
    password: Optional[str] = None,
) -> List[List[str]]:
    """
    Dispatch reader based on file extension / magic bytes.
    Supports CSV, XLSX, PDF (digital and scanned), and Images (PNG, JPEG, WEBP).
    """
    lower_name = filename.lower()
    if lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return read_image_in_memory(file_bytes)
    elif lower_name.endswith(".csv"):
        return read_csv_in_memory(file_bytes)
    elif lower_name.endswith((".xlsx", ".xls")):
        return read_excel_in_memory(file_bytes)
    elif lower_name.endswith(".pdf"):
        return read_pdf_in_memory(file_bytes, password=password)

    # Fallback inspection of magic bytes
    if file_bytes.startswith(b"%PDF-"):
        return read_pdf_in_memory(file_bytes, password=password)
    elif file_bytes.startswith(b"PK\x03\x04"):
        return read_excel_in_memory(file_bytes)
    elif (
        file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        or file_bytes.startswith(b"\xff\xd8\xff")
        or (file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16])
    ):
        return read_image_in_memory(file_bytes)
    else:
        return read_csv_in_memory(file_bytes)
