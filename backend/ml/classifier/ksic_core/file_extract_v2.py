# ============================================================
# ksic_core/file_extract.py (v2)
#
# 개선 목표
# - PDF: 본문 + 표(Markdown) + 페이지별 OCR fallback
# - 스캔 PDF: PyMuPDF 렌더링 + PaddleOCR
# - HWP: hwp5txt 유지
# - HWPX: XML 문단/표(row/cell) 구조 추출
# - 실패 시 예외 전파 대신 None + 상태값 반환
# ============================================================

import io
import os
import re
import html
import subprocess
import tempfile
import zipfile
from typing import Optional, Tuple, List

import requests
import pdfplumber

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}

PDF_TEXT_MIN_CHARS = 50
OCR_DPI = 180
OCR_MAX_LONG_SIDE = 4000
REQUEST_TIMEOUT = 20

_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        from paddleocr import PaddleOCR
        _ocr_reader = PaddleOCR(lang="korean", enable_mkldnn=False)
    return _ocr_reader


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_cell(value) -> str:
    if value is None:
        return ""
    value = html.unescape(str(value))
    value = value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value.replace("|", r"\|")


def _table_to_markdown(table) -> str:
    if not table:
        return ""

    rows: List[List[str]] = []
    for row in table:
        if row is None:
            continue
        cleaned = [_clean_cell(cell) for cell in row]
        if any(cleaned):
            rows.append(cleaned)

    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (max_cols - len(row)))

    header = rows[0]
    if not any(header):
        header = [f"col_{i+1}" for i in range(max_cols)]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * max_cols) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def detect_file_type(content: bytes) -> str:
    if content[:4] == b"%PDF":
        return "pdf"
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "hwp"
    if content[:2] == b"PK":
        return "hwpx_or_zip"
    return "unknown"


# ============================================================
# PDF
# ============================================================

def _extract_pdf_tables(page) -> List:
    line_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "intersection_tolerance": 5,
        "text_tolerance": 3,
    }
    try:
        tables = page.extract_tables(line_settings) or []
    except Exception:
        tables = []

    if tables:
        return tables

    text_settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "min_words_vertical": 2,
        "min_words_horizontal": 1,
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "intersection_tolerance": 5,
        "text_tolerance": 3,
    }
    try:
        return page.extract_tables(text_settings) or []
    except Exception:
        return []


def _render_pdf_page_with_pymupdf(content: bytes, page_index: int):
    """Poppler 대신 PyMuPDF로 특정 페이지만 이미지 배열로 렌더링."""
    import fitz
    import numpy as np
    from PIL import Image

    doc = fitz.open(stream=content, filetype="pdf")
    try:
        page = doc.load_page(page_index)
        scale = OCR_DPI / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        width, height = image.size
        long_side = max(width, height)
        if long_side > OCR_MAX_LONG_SIDE:
            ratio = OCR_MAX_LONG_SIDE / long_side
            image = image.resize((max(1, int(width * ratio)), max(1, int(height * ratio))))

        return np.array(image)
    finally:
        doc.close()


def _ocr_image_array(img_array) -> str:
    """PaddleOCR 버전별 결과 차이를 일부 흡수해 텍스트만 반환."""
    reader = _get_ocr_reader()

    if hasattr(reader, "predict"):
        results = reader.predict(img_array)
        texts = []
        for res in results:
            try:
                rec_texts = res["rec_texts"]
            except Exception:
                rec_texts = res.get("rec_texts", []) if isinstance(res, dict) else []
            texts.extend(str(x) for x in rec_texts if str(x).strip())
        return _normalize_text("\n".join(texts))

    if hasattr(reader, "ocr"):
        result = reader.ocr(img_array, cls=True)
        texts = []
        for page_result in result or []:
            for item in page_result or []:
                try:
                    text = item[1][0]
                    if str(text).strip():
                        texts.append(str(text))
                except Exception:
                    continue
        return _normalize_text("\n".join(texts))

    return ""


def extract_text_from_pdf(content: bytes) -> Optional[str]:
    """
    PDF 페이지별 Hybrid 추출.

    - 텍스트 충분: pdfplumber 본문 + 표(Markdown)
    - 텍스트 부족: 해당 페이지만 PyMuPDF 렌더링 + PaddleOCR
    """
    try:
        page_results = []

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            total_pages = len(pdf.pages)

            for page_index, page in enumerate(pdf.pages):
                page_num = page_index + 1
                parts = [f"==================== PAGE {page_num}/{total_pages} ===================="]

                try:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=3, layout=True)
                except TypeError:
                    page_text = page.extract_text(x_tolerance=2, y_tolerance=3)
                except Exception:
                    page_text = None

                text = _normalize_text(page_text)
                tables = _extract_pdf_tables(page)

                if len(text) >= PDF_TEXT_MIN_CHARS:
                    parts.append(text)
                else:
                    if text:
                        parts.append(text)
                    try:
                        img_array = _render_pdf_page_with_pymupdf(content, page_index)
                        ocr_text = _ocr_image_array(img_array)
                    except Exception as e:
                        print(f"[PDF OCR 오류] page={page_num}: {e}")
                        ocr_text = ""

                    if ocr_text:
                        parts.append(f"[PAGE {page_num} - OCR FALLBACK]\n{ocr_text}")

                for table_num, table in enumerate(tables, start=1):
                    md = _table_to_markdown(table)
                    if md:
                        parts.append(f"[PAGE {page_num} - TABLE {table_num}]\n{md}")

                block = "\n\n".join(p for p in parts if p and p.strip()).strip()
                if block:
                    page_results.append(block)

        result = "\n\n".join(page_results)
        return result if result.strip() else None

    except Exception as e:
        print(f"[PDF 추출 오류] {e}")
        return None


def extract_text_from_scanned_pdf(content: bytes) -> Optional[str]:
    """완전 스캔 PDF용 전 페이지 OCR. 동일 함수 중복 정의 금지."""
    try:
        import fitz

        doc = fitz.open(stream=content, filetype="pdf")
        total_pages = len(doc)
        doc.close()

        blocks = []
        for page_index in range(total_pages):
            page_num = page_index + 1
            try:
                img_array = _render_pdf_page_with_pymupdf(content, page_index)
                page_text = _ocr_image_array(img_array)
            except Exception as e:
                print(f"[OCR 오류] page={page_num}: {e}")
                page_text = ""

            if page_text:
                blocks.append(
                    f"==================== OCR PAGE {page_num}/{total_pages} ====================\n"
                    f"{page_text}"
                )

        result = "\n\n".join(blocks)
        return result if result.strip() else None

    except Exception as e:
        print(f"[스캔 PDF OCR 오류] {e}")
        return None


# ============================================================
# HWP
# ============================================================

def extract_text_from_hwp(content: bytes) -> Optional[str]:
    """구버전 HWP(OLE): hwp5txt 유지."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        result = subprocess.run(
            ["hwp5txt", tmp_path],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        text = result.stdout.decode("utf-8", errors="ignore")
        text = _normalize_text(text)
        return text if text else None

    except Exception as e:
        print(f"[HWP 추출 오류] {e}")
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ============================================================
# HWPX
# ============================================================

def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def _element_text(elem) -> str:
    texts = []
    for child in elem.iter():
        if _local_name(child.tag).lower() == "t" and child.text and child.text.strip():
            texts.append(child.text.strip())
    return _normalize_text(" ".join(texts))


def _extract_hwpx_paragraphs_from_root(root) -> List[str]:
    paragraphs = []
    for elem in root.iter():
        if _local_name(elem.tag).lower() == "p":
            text = _element_text(elem)
            if text:
                paragraphs.append(text)
    return paragraphs


def _extract_hwpx_tables_from_root(root) -> List[List[List[str]]]:
    tables = []

    for table_elem in root.iter():
        if _local_name(table_elem.tag).lower() not in {"tbl", "table"}:
            continue

        table_rows = []
        for row_elem in table_elem.iter():
            if _local_name(row_elem.tag).lower() != "tr":
                continue

            row = []
            for cell_elem in row_elem:
                if _local_name(cell_elem.tag).lower() == "tc":
                    row.append(_element_text(cell_elem))

            if not row:
                for cell_elem in row_elem.iter():
                    if _local_name(cell_elem.tag).lower() == "tc":
                        row.append(_element_text(cell_elem))

            if any(cell.strip() for cell in row):
                table_rows.append(row)

        if table_rows:
            tables.append(table_rows)

    return tables


def extract_text_from_hwpx(content: bytes) -> Optional[str]:
    """HWPX(zip+xml): 문단 + 표(row/cell) 구조 추출."""
    try:
        import xml.etree.ElementTree as ET

        blocks = []
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            section_files = sorted(
                name for name in z.namelist()
                if "section" in name.lower() and name.lower().endswith(".xml")
            )

            if not section_files:
                return None

            for section_idx, section_file in enumerate(section_files, start=1):
                try:
                    root = ET.fromstring(z.read(section_file))
                except Exception:
                    continue

                parts = [f"==================== HWPX SECTION {section_idx} ===================="]

                paragraphs = _extract_hwpx_paragraphs_from_root(root)
                if paragraphs:
                    parts.append("\n".join(paragraphs))

                tables = _extract_hwpx_tables_from_root(root)
                for table_num, table in enumerate(tables, start=1):
                    md = _table_to_markdown(table)
                    if md:
                        parts.append(
                            f"[HWPX SECTION {section_idx} - TABLE {table_num}]\n{md}"
                        )

                blocks.append("\n\n".join(parts))

        result = "\n\n".join(blocks)
        return result if result.strip() else None

    except Exception as e:
        print(f"[HWPX 추출 오류] {e}")
        return None


# ============================================================
# URL -> 다운로드 -> 형식별 추출
# ============================================================

def get_notice_full_text(print_flpth_url: str) -> Tuple[Optional[str], str]:
    """
    반환 status:
      success_pdf / success_hwp / success_hwpx / success_ocr
      extract_failed / download_failed / unknown_format / no_url
    """
    if not print_flpth_url or not print_flpth_url.strip():
        return None, "no_url"

    try:
        response = requests.get(
            print_flpth_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200 or not response.content:
            return None, "download_failed"
        content = response.content
    except Exception:
        return None, "download_failed"

    file_type = detect_file_type(content)

    if file_type == "pdf":
        text = extract_text_from_pdf(content)
        if text:
            return text, "success_ocr" if "OCR FALLBACK" in text else "success_pdf"

        text = extract_text_from_scanned_pdf(content)
        return (text, "success_ocr") if text else (None, "extract_failed")

    if file_type == "hwp":
        text = extract_text_from_hwp(content)
        return (text, "success_hwp") if text else (None, "extract_failed")

    if file_type == "hwpx_or_zip":
        text = extract_text_from_hwpx(content)
        return (text, "success_hwpx") if text else (None, "extract_failed")

    return None, "unknown_format"
