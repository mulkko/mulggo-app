# [테스트 전용] 사업자등록증 OCR + 저장 검증용 엔드포인트.
# 정식 회원가입 플로우(auth.py)와 무관하다 — OCR 파싱이 잘 되는지만 확인하는 용도.
# DB(biz_registration_docs)에는 저장하지 않고, 결과를 CSV 한 줄로 남긴다.
# 잘 되는 거 확인되면 회원가입 플로우 통합 시 실제 DB 저장으로 교체할 예정.
#
# 주의: OCR은 backend/assistant/biz_cert_ocr.py의 Qwen2.5-VL(GPU 권장) 모델을 그대로 씀.
# 이 서버가 도는 환경에 torch/transformers/qwen-vl-utils가 설치돼 있어야 실제 호출이 성공한다.

import csv
import json
import os
import shutil

from fastapi import APIRouter, File, UploadFile
from PIL import UnidentifiedImageError

from backend.assistant.biz_cert_ocr import extract_biz_cert, get_cached_vision_model

try:
    from pdf2image.exceptions import (
        PDFInfoNotInstalledError,
        PDFPageCountError,
        PDFSyntaxError,
    )
    _PDF_ERRORS = (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError)
except ImportError:
    _PDF_ERRORS = ()

router = APIRouter(prefix="/api/test", tags=["test"])

UPLOAD_DIR = os.path.join("data", "test_uploads", "biz_registration")
CSV_PATH = os.path.join("data", "test_uploads", "biz_registration_ocr_test.csv")

# biz_registration_docs 정식 컬럼(DB컬럼/사업자등록증OCR_컬럼.xlsx 기준) + 디버깅용 2개(entity_type, ocr_raw_text)
CSV_FIELDS = [
    "file_name",
    "biz_no",
    "corp_no",
    "company_name",
    "ceo_name",
    "open_date",
    "birth_date",
    "business_address",
    "head_address",
    "business_category",
    "entity_type",
    "ocr_raw_text",
]


@router.post("/ocr-upload")
async def test_ocr_upload(file: UploadFile = File(...)) -> dict:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    result: dict = {
        "file_name": file.filename,
        "ocr_success": False,
        "csv_saved": False,
        "extracted": None,
        "error": None,
        "error_type": None,   # 프론트에서 종류별로 다른 안내를 보여주기 위한 코드값
        "error_label": None,  # 사용자에게 그대로 보여줄 한글 안내 문구
    }

    def _fail(error_type, label, exc):
        result["error_type"] = error_type
        result["error_label"] = label
        result["error"] = f"OCR 실패: {exc}"
        return result

    try:
        model, processor = get_cached_vision_model()
        entity_type, biz_cert = extract_biz_cert(save_path, model, processor)
    except (UnidentifiedImageError, FileNotFoundError, OSError) as e:
        # 파일 자체를 못 열었을 때 (손상된 파일, 이미지가 아닌 파일 등)
        return _fail("file_error", "파일을 열 수 없습니다. 이미지가 손상되었거나 지원하지 않는 형식일 수 있어요.", e)
    except _PDF_ERRORS as e:
        # PDF -> 이미지 변환 실패 (주로 서버에 poppler 미설치)
        return _fail("pdf_error", "PDF 변환에 실패했습니다. 서버 설정 문제일 수 있어요.", e)
    except ValueError as e:
        # 모델이 사진은 읽었지만 정해진 JSON 형식으로 답을 못 준 경우 (biz_cert_ocr.py의 parse_json 실패).
        # 어둡거나 흐릿한 사진에서 자주 발생.
        return _fail("recognition_error", "사업자등록증을 인식하지 못했습니다. 밝고 선명한 사진으로 다시 시도해주세요.", e)
    except RuntimeError as e:
        if "CUDA" in str(e):
            # GPU 연산 중 크래시 (device-side assert 등). 서버/모델 쪽 문제라 사용자가 고칠 수 없음.
            return _fail("gpu_error", "서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", e)
        return _fail("unknown_error", "알 수 없는 오류가 발생했습니다.", e)
    except Exception as e:
        # 위에서 분류하지 못한 나머지 전부
        return _fail("unknown_error", "알 수 없는 오류가 발생했습니다.", e)

    result["ocr_success"] = True

    row = {
        "file_name": file.filename,
        "biz_no": biz_cert.get("biz_no", ""),
        "corp_no": biz_cert.get("corp_no", ""),
        "company_name": biz_cert.get("corp_name") or biz_cert.get("trade_name", ""),
        "ceo_name": biz_cert.get("ceo_name", ""),
        "open_date": biz_cert.get("open_date", ""),
        "birth_date": biz_cert.get("birth_date", ""),
        "business_address": biz_cert.get("address_basic", ""),
        "head_address": "",
        "business_category": "",
        "entity_type": entity_type,
        "ocr_raw_text": json.dumps(biz_cert, ensure_ascii=False),
    }
    result["extracted"] = row

    try:
        file_exists = os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        result["csv_saved"] = True
    except Exception as e:
        result["error"] = f"CSV 저장 실패: {e}"

    return result
