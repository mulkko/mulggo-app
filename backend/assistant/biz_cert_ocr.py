"""
사업자등록증 → OCR → 필드매핑 → 신청서 HWPX 자동입력 → 완성 파일
담당: AI 신청서 어시스턴트 & 사후관리 (DA3)

[준비물 3개]
  1. 사업자등록증 이미지 또는 PDF
  2. 필드매핑 xlsx (C열=내부 key, F열=신청서에 나타나는 표현들 콤마 구분)
  3. 신청서 HWPX 파일 (HWP는 rhwp.kr 등으로 HWPX 변환 후)

[추가 설치]
  pip install pdf2image openpyxl qwen-vl-utils transformers torch accelerate
  # PDF 입력을 쓰려면 시스템에 poppler 설치 필요 (Windows: conda install -c conda-forge poppler
  #   또는 https://github.com/oschwartz10612/poppler-windows 릴리스 받아 PATH 등록)

[GPU]
  Qwen2.5-VL 때문에 OCR 단계는 GPU 필요. HWPX 채우기 단계는 가벼움(CPU).

[CLI 실행]
  python -m backend.assistant.biz_cert_ocr \
      --image 사업자등록증.png --mapping 필드매핑.xlsx \
      --form 신청서.hwpx --out 신청서_완성.hwpx
"""

import argparse
import json
import os
import re
import shutil
import tempfile
import zipfile

import openpyxl

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"

# 사업자등록증 OCR 결과(한글 key) → 내부 key
KEY_MAP = {
    "상호": "trade_name",
    "법인명": "corp_name",
    "대표자": "ceo_name",
    "등록번호": "biz_no",
    "법인등록번호": "corp_no",
    "생년월일": "birth_date",
    "개업연월일": "open_date",
    "사업장소재지": "address_basic",
}

# 필드매핑 xlsx로 못 잡는 신청서별 표현 보완 (필요시 추가)
EXTRA_ALIAS = {"설립일": "open_date"}

# 값을 넣지 않을 칸 (담당자 연락처·서명란 등)
EXCLUDE = [
    "e-mail", "email", "이메일", "휴대폰", "전화", "연락처",
    "직위", "사무실", "주생산품", "서명", "인)",
]


# ══════════════════════════════════════════════════════
# 1) OCR: 사업자등록증 읽기
# ══════════════════════════════════════════════════════
def load_vision_model():
    """Qwen2.5-VL 모델/프로세서 로딩. import 시점이 아니라 필요할 때 호출."""
    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.float16, device_map="auto"
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model.eval()
    return model, processor


def load_image(path):
    """이미지/PDF 경로 → PIL Image (PDF는 첫 페이지만)."""
    from PIL import Image

    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from pdf2image import convert_from_path

        return convert_from_path(path, dpi=200)[0]
    return Image.open(path)


<<<<<<< HEAD
def ask_image(model, processor, image, question):
    """PIL Image + 질문 → 모델 응답 텍스트."""
    import torch
    from qwen_vl_utils import process_vision_info

    messages = [{
        "role": "user",
        "content": [{"type": "image", "image": image}, {"type": "text", "text": question}],
=======
# ══════════════════════════════════════════════════════
# [테스트] OCR 속도 개선 실험 — 이미지 리사이즈 (2026-09-05)
# ══════════════════════════════════════════════════════
# 배경: 사업자등록증 사진이 클수록(휴대폰 사진 등 3000~4000px) Qwen2.5-VL의
#   이미지 prefill 비용이 커져서 OCR이 느려짐. 이미지를 줄여서 넣으면 빨라질 것으로 예상.
#
# 1차 시도(실패): load_image()에서 PIL로 직접 img.resize()해서 넘김.
#   → CUDA error: device-side assert triggered 발생.
#   → 원인 추정: qwen_vl_utils가 모델에 넣기 직전 이미지를 patch(28px 배수) /
#     2x2 병합 단위에 맞춰 내부적으로 다시 리사이즈하는데, 우리가 미리 임의 크기로
#     잘라놓으면 그 단위와 안 맞아서 vision 토큰을 텍스트에 합치는 단계에서 인덱스가
#     어긋나는 것으로 보임. (서버 재시작 후에도 동일 이미지로 재현됨 → 일회성 GPU
#     컨텍스트 오류 아니라 리사이즈 방식 자체의 문제로 판단)
#
# 2차 시도(현재 적용 중): 직접 리사이즈하지 않고, ask_image()에 max_pixels만 넘겨서
#   qwen_vl_utils가 자기 규칙(patch/병합 단위)에 맞춰 알아서 축소하게 함.
#   → 아래 MAX_OCR_PIXELS 값을 ask_image(..., max_pixels=MAX_OCR_PIXELS)로 전달
#     (호출부: extract_biz_cert() 안의 ask_image 호출, 이 파일에서 검색 시 하나뿐).
#
# 되돌리는 법 (이 실험을 완전히 없던 일로 하고 싶을 때):
#   1) 아래 MAX_OCR_PIXELS = None 으로 바꾸거나,
#   2) extract_biz_cert() 안의 `ask_image(model, processor, img, q, max_pixels=MAX_OCR_PIXELS)`에서
#      `max_pixels=MAX_OCR_PIXELS` 부분을 지우면 원래 상태(리사이즈 전혀 없음, 처음부터 잘 되던 버전)로 복귀.
#   둘 다 안전하게 원복 가능 — load_image()나 다른 함수는 이 실험과 무관하게 그대로임.
MAX_OCR_PIXELS = 1280 * 1280


def ask_image(model, processor, image, question, max_new_tokens=512, max_pixels=None):
    """PIL Image + 질문 → 모델 응답 텍스트.
    max_pixels: [테스트] qwen_vl_utils가 자체 규칙에 맞춰 리사이즈할 때 쓰는 픽셀 상한.
    None이면 기존 방식(리사이즈 없음)과 동일."""
    import torch
    from qwen_vl_utils import process_vision_info

    image_content = {"type": "image", "image": image}
    if max_pixels is not None:
        image_content["max_pixels"] = max_pixels

    messages = [{
        "role": "user",
        "content": [image_content, {"type": "text", "text": question}],
>>>>>>> DA3_
    }]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, _ = process_vision_info(messages)
    inputs = processor(
        text=[text], images=image_inputs, padding=True, return_tensors="pt"
    ).to(model.device)
    with torch.no_grad():
<<<<<<< HEAD
        out = model.generate(**inputs, max_new_tokens=512)
=======
        out = model.generate(**inputs, max_new_tokens=max_new_tokens)
>>>>>>> DA3_
    out = [o[len(i):] for i, o in zip(inputs.input_ids, out)]
    result = processor.batch_decode(out, skip_special_tokens=True)[0]
    del inputs, out
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result


def parse_json(raw):
    """응답 텍스트에서 첫 번째 JSON 객체를 추출. 실패 시 None."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _normalize_dates(biz_cert):
    for key in ("open_date", "birth_date"):
        val = biz_cert.get(key)
        if not val:
            continue
        m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", val)
        if m:
            biz_cert[key] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return biz_cert


def extract_biz_cert(image_path, model, processor):
    """
    사업자등록증 이미지/PDF → (biz_type, biz_cert dict).

    biz_type: "법인" 또는 "개인"
    biz_cert: 내부 key(trade_name, ceo_name, biz_no, ...)로 정규화된 값
    """
    img = load_image(image_path)

<<<<<<< HEAD
    # ── 개인/법인 판별 (사업자등록번호 가운데 2자리 81~88 = 법인) ──
    reg_raw = ask_image(
        model, processor, img,
        "이 사업자등록증의 등록번호(사업자등록번호)만 숫자로 답해줘. "
        "예: 123-45-67890. 다른 말은 하지 마.",
    )
    digits = "".join(c for c in reg_raw if c.isdigit())
    biz_type = "법인" if (len(digits) >= 5 and 81 <= int(digits[3:5]) <= 88) else "개인"

    # ── 판별에 맞는 항목 추출 ──
    if biz_type == "법인":
        q = (
            "이 사업자등록증을 읽고 아래 JSON 형식으로만 답해줘. 설명하지 말고 JSON만. "
            "반드시 한글로만 적고 한자는 쓰지 마.\n"
            '{"법인명":"","대표자":"","등록번호":"","법인등록번호":"","개업연월일":"","사업장소재지":""}'
        )
    else:
        q = (
            "이 사업자등록증을 읽고 아래 JSON 형식으로만 답해줘. 설명하지 말고 JSON만. "
            "반드시 한글로만 적고 한자는 쓰지 마.\n"
            '{"상호":"","대표자":"","등록번호":"","생년월일":"","개업연월일":"","사업장소재지":""}'
        )

    raw = ask_image(model, processor, img, q)
=======
    # 법인/개인 판별용 호출을 없애고 전체 항목을 한 번의 VLM 호출로 추출
    # (이미지 prefill 비용이 커서 호출 2회 -> 1회로 줄이면 지연시간이 절반 가까이 줄어듦).
    # 법인/개인 판별은 이 응답에 포함된 등록번호로 사후 계산.
    q = (
        "이 사업자등록증을 읽고 아래 JSON 형식으로만 답해줘. 설명하지 말고 JSON만. "
        "해당 없는 항목은 빈 문자열로 둬. 반드시 한글로만 적고 한자는 쓰지 마.\n"
        '{"법인명":"","상호":"","대표자":"","등록번호":"","법인등록번호":"",'
        '"생년월일":"","개업연월일":"","사업장소재지":""}'
    )
    raw = ask_image(model, processor, img, q, max_pixels=MAX_OCR_PIXELS)  # [테스트] 롤백: max_pixels 인자 제거
>>>>>>> DA3_
    parsed = parse_json(raw)
    if parsed is None:
        raise ValueError(f"OCR 결과에서 JSON을 파싱하지 못했습니다: {raw!r}")

<<<<<<< HEAD
=======
    # ── 개인/법인 판별 (사업자등록번호 가운데 2자리 81~88 = 법인) ──
    digits = "".join(c for c in parsed.get("등록번호", "") if c.isdigit())
    biz_type = "법인" if (len(digits) >= 5 and 81 <= int(digits[3:5]) <= 88) else "개인"

    if biz_type == "법인":
        parsed.pop("상호", None)
        parsed.pop("생년월일", None)
    else:
        parsed.pop("법인명", None)
        parsed.pop("법인등록번호", None)

>>>>>>> DA3_
    biz_cert = {KEY_MAP.get(k, k): v for k, v in parsed.items()}
    _normalize_dates(biz_cert)
    return biz_type, biz_cert


# ══════════════════════════════════════════════════════
# 2) 필드매핑 로드 + 신청서 표현 → 내부 key 해석
# ══════════════════════════════════════════════════════
def load_mapping(path):
    """필드매핑 xlsx → [{key, keywords[]}] 규칙 목록 (C열=key, F열=키워드)."""
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rules = []
    for r in range(2, ws.max_row + 1):
        key = ws.cell(r, 3).value
        kw = ws.cell(r, 6).value
        if key and kw:
            rules.append({
                "key": str(key).strip(),
                "keywords": [k.strip() for k in str(kw).split(",") if k.strip()],
            })
    return rules


def _norm(s):
    return re.sub(r"\s+", "", s)


def resolve_key(field, rules, biz_type):
    """신청서에 나타난 표현(field) → 내부 key. 못 찾으면 None."""
    nf = _norm(field)
    for alias, key in EXTRA_ALIAS.items():
        if _norm(alias) == nf:
            return key
    for rule in rules:
        for kw in rule["keywords"]:
            if _norm(kw) == nf:
                key = rule["key"]
                if key == "trade_name" and biz_type == "법인":
                    key = "corp_name"
                if key == "corp_name" and biz_type == "개인":
                    key = "trade_name"
                return key
    return None


# ══════════════════════════════════════════════════════
# 3) HWPX 자동 입력 (대표자 정보만, 서명란·담당자 제외)
# ══════════════════════════════════════════════════════
def fill_hwpx(form_path, out_path, rules, biz_cert, biz_type):
    """신청서 HWPX의 빈 칸에 사업자등록증 정보를 채워 out_path로 저장. 채운 필드 로그 반환."""
    work = tempfile.mkdtemp(prefix="hwpx_")
    try:
        with zipfile.ZipFile(form_path) as z:
            z.extractall(work)

        sec = os.path.join(work, "Contents", "section0.xml")
        with open(sec, encoding="utf-8") as f:
            xml = f.read()

        parts = re.split(r"(<hp:t>.*?</hp:t>)", xml, flags=re.DOTALL)
        pending = None
        used = set()
        log = []
        in_damdang = False

        for i, part in enumerate(parts):
            m = re.match(r"<hp:t>(.*?)</hp:t>", part, re.DOTALL)
            if not m:
                continue
            st = m.group(1).strip()

            if "담" in st and "당" in st and "자" in st:  # 담당자 영역 진입
                in_damdang = True

            if pending is not None and st == "":
                parts[i] = f"<hp:t>{pending[1]}</hp:t>"
                log.append(pending)
                pending = None
                continue

            if not st:
                continue
            if any(ex in st.lower() for ex in EXCLUDE):
                continue

            # 성명: 표 안 대표자만 (담당자 영역 제외)
            if _norm(st) == "성명":
                if in_damdang:
                    continue
                val = biz_cert.get("ceo_name")
                if val and "ceo" not in used:
                    pending = (st, val)
                    used.add("ceo")
                continue
            # "대표자"/"대표" 단어(서명란)엔 안 넣음
            if _norm(st) in ("대표자", "대표"):
                continue

            key = resolve_key(st, rules, biz_type)
            if key:
                val = biz_cert.get(key)
                if val and key not in used:
                    pending = (st, val)
                    used.add(key)

        with open(sec, "w", encoding="utf-8") as f:
            f.write("".join(parts))

        if os.path.exists(out_path):
            os.remove(out_path)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            # mimetype은 무압축으로 가장 먼저 저장 (OpenDocument/HWPX 규약)
            z.write(
                os.path.join(work, "mimetype"), "mimetype",
                compress_type=zipfile.ZIP_STORED,
            )
            for root, _dirs, files in os.walk(work):
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, work)
                    if rel == "mimetype":
                        continue
                    z.write(full, rel)
        return log
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ══════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="사업자등록증 OCR → 신청서 HWPX 자동입력"
    )
    parser.add_argument("--image", required=True, help="사업자등록증 이미지 또는 PDF")
    parser.add_argument("--mapping", required=True, help="필드매핑 xlsx")
    parser.add_argument("--form", required=True, help="신청서 HWPX (입력)")
    parser.add_argument("--out", required=True, help="완성 HWPX (출력)")
    args = parser.parse_args()

    model, processor = load_vision_model()
    biz_type, biz_cert = extract_biz_cert(args.image, model, processor)
    print(f"판별: {biz_type}")
    print(f"추출: {biz_cert}")

    rules = load_mapping(args.mapping)
    log = fill_hwpx(args.form, args.out, rules, biz_cert, biz_type)

    print(f"\n=== 신청서 자동 입력 완료 ({biz_type}) ===")
    for field, val in log:
        print(f"  [{field}] <- {val}")
    print(f"\n완성 파일: {args.out}")


if __name__ == "__main__":
    main()
