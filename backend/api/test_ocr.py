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

from backend.assistant.biz_cert_ocr import extract_biz_cert, load_vision_model

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
    }

    try:
        model, processor = load_vision_model()
        entity_type, biz_cert = extract_biz_cert(save_path, model, processor)
    except Exception as e:
        result["error"] = f"OCR 실패: {e}"
        return result

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
