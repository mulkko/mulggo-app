"""
사업자등록증 이미지/PDF → OCR 추출 → CSV 저장 (확인·튜닝용 유틸).

biz_cert_ocr.py 의 extract_biz_cert / ask_image / parse_json / load_image 를 재사용한다.
단, 모델 로딩은 이 파일에서 자체적으로 한다 (아래 "왜 자체 로딩" 참고).
HWPX 신청서 입력 단계는 사용하지 않는다.

[왜 모델을 자체 로딩하나]
  biz_cert_ocr.load_vision_model 은 fp16으로 로딩하는데, 8GB GPU + 큰 이미지에서
  수치 오버플로로 CUDA device-side assert 가 난다. 여기서는 bf16 + greedy 로 로딩한다.
  (팀원 파일은 건드리지 않음)

[전처리]
  - 입력 이미지 EXIF 회전 보정 (폰 사진 대응)
  - 긴 변을 --max-side(기본 2000)px 로 축소
  - PDF 는 PyMuPDF 로 첫 페이지 렌더링 후 동일 전처리

[추출 항목]
  1) 기본정보  : extract_biz_cert() 그대로
  2) 업태·종목 : '사업의 종류' 표를 전용 프롬프트로 읽어 업태-종목 쌍 목록으로.
                 '업태'/'종목' 라벨 글자를 값으로 오인하지 않도록,
                 두 칸을 각각 세로 리스트로 뽑은 뒤 위치로 짝짓는다.

[CSV 형식]  업태-종목 쌍마다 한 행. 쌍이 없으면 기본정보만 한 행.
  파일, biz_type, 상호_법인명, 대표자, 등록번호, 법인등록번호, 생년월일,
  개업연월일, 사업장소재지, 순번, 업태, 종목

[추가 설치]  pip install pymupdf openpyxl  +  OCR용 GPU 패키지(requirements.txt 주석)

[실행]
  python -m backend.assistant.extract_biz_cert_to_csv --out 결과.csv 개인.jpg 법인.pdf
  python -m backend.assistant.extract_biz_cert_to_csv --out 결과.csv --debug "samples/*.jpg"
"""

import argparse
import csv
import glob
import os
import re
import tempfile
from itertools import zip_longest

from backend.assistant.biz_cert_ocr import ask_image, extract_biz_cert, parse_json
from backend.assistant.biz_cert_ocr import load_image as _load_image

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
DEFAULT_MAX_SIDE = 2400

BASIC_COLUMNS = [
    "파일", "biz_type", "상호_법인명", "대표자", "등록번호",
    "법인등록번호", "생년월일", "개업연월일", "사업장소재지",
]
COLUMNS = BASIC_COLUMNS + ["순번", "업태", "종목"]

# '사업의 종류' = 업태 칸 + 종목 칸.
# 업태 1개에 종목이 여러 개일 수 있으므로(1:1 아님), 세로 위치로 묶어서 읽게 한다.
_CATEGORY_PROMPT = (
    "이 사업자등록증의 '사업의 종류' 항목을 읽어라.\n"
    "왼쪽에 '업태' 칸, 오른쪽에 '종목' 칸이 있고 각 칸에 값이 세로로 나열된다.\n"
    "한 업태는 자기 줄 높이에서 시작하고, 다음 업태가 나오기 전까지 같은 높이대에 있는 "
    "모든 종목 줄이 그 업태에 속한다. (업태 1개에 종목이 여러 개일 수 있다.)\n"
    "규칙:\n"
    "1. '업태', '종목' 이라는 글자는 칸 제목이다. 값에 절대 넣지 마라.\n"
    "2. 업태 값이 두 줄 이상으로 접혀 있으면, 작은 글씨까지 빠짐없이 읽어 하나로 이어붙여라.\n"
    "3. 한 줄(한 행) 전체가 하나의 값이다. 한 줄 안에 쉼표(,)나 가운뎃점(·)으로 여러 개가 "
    "적혀 있어도 절대 나누지 말고, 그 줄 전체를 통째로 하나의 값으로 둬라.\n"
    "   예: 종목 줄이 '풍력발전·철구조물·산업플랜트' 이면 → 그대로 '풍력발전·철구조물·산업플랜트' 한 개.\n"
    "4. 세로 위치(높이)를 기준으로 어떤 종목 줄이 어떤 업태에 속하는지 판단하라. 개수를 억지로 맞추지 마라.\n"
    "5. 한글로만 적고 한자는 쓰지 마라.\n"
    "아래 JSON 형식으로만 답하라. 다른 설명은 하지 마라.\n"
    '{"항목": [{"업태": "", "종목": ["줄1 전체", "줄2 전체"]}, {"업태": "", "종목": ["줄1 전체"]}]}'
)

_LABEL_WORDS = {"업태", "종목", ""}
_CATEGORY_MIN_SIDE = 2600  # 업태·종목 칸의 작은/접힌 글씨 대응: 이 호출만 더 큰 이미지 사용


def _strip_label_prefix(s: str) -> str:
    """'업태 소매업' 처럼 값 앞에 라벨이 붙은 경우 제거."""
    for lbl in ("업태", "종목"):
        if s.startswith(lbl) and s != lbl:
            s = s[len(lbl):].lstrip(" :·-\t")
    return s.strip()


def load_model(dtype: str = "bf16"):
    """Qwen2.5-VL 로딩. fp16 대신 bf16 기본 + greedy 디코딩."""
    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    torch_dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[dtype]
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch_dtype, device_map="auto"
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model.eval()
    model.generation_config.do_sample = False  # greedy (multinomial assert 회피)
    return model, processor


def prep_image(src: str, max_side: int = DEFAULT_MAX_SIDE) -> tuple[str, tuple[int, int]]:
    """EXIF 회전 보정 + RGB 변환 + 과대 이미지 축소 → 임시 PNG 경로, 크기."""
    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(Image.open(src))
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    fd, out_path = tempfile.mkstemp(suffix=".png", prefix="bizcert_prep_")
    os.close(fd)
    im.save(out_path)
    return out_path, im.size


def _upscale(im, min_side: int):
    """긴 변이 min_side 보다 작으면 확대 (작은/접힌 글씨 인식용). PIL Image in/out."""
    from PIL import Image

    w, h = im.size
    if max(w, h) >= min_side:
        return im
    scale = min_side / max(w, h)
    return im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def pdf_first_page_to_png(pdf_path: str, dpi: int = 200) -> str:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    try:
        pix = doc.load_page(0).get_pixmap(dpi=dpi)
        fd, out_path = tempfile.mkstemp(suffix=".png", prefix="bizcert_pdf_")
        os.close(fd)
        pix.save(out_path)
        return out_path
    finally:
        doc.close()


def _clean_list(v) -> list[str]:
    if not isinstance(v, list):
        v = [v] if v else []
    out = []
    for x in v:
        s = _strip_label_prefix(str(x).strip())
        if s and s not in _LABEL_WORDS:
            out.append(s)
    return out


def _split_items(v) -> list[str]:
    """종목 값 정규화. 한 줄(문자열) = 한 값. 쉼표·가운뎃점으로 쪼개지 않는다.

    - 문자열: 한 값으로 취급 (줄바꿈이 있으면 그것만 분리)
    - 리스트: 각 원소가 한 값
    라벨 글자('업태'/'종목')와 빈값만 제거.
    """
    if isinstance(v, str):
        parts = v.split("\n")
    elif isinstance(v, list):
        parts = [x for x in v]
    else:
        parts = []
    out = []
    for p in parts:
        s = _strip_label_prefix(str(p).strip())
        if s and s not in _LABEL_WORDS:
            out.append(s)
    return out


def groups_from_parsed(parsed) -> list[dict]:
    """모델 응답(JSON) → [{"업태": str, "종목": [str, ...]}] 목록.

    기대 형식: {"항목": [{"업태": "...", "종목": ["...", "..."]}]}
    구형/변형 형식(업태목록·종목목록 병렬리스트, 목록[{업태,종목}])도 허용.
    """
    if not isinstance(parsed, dict):
        return []

    items = parsed.get("항목") or parsed.get("items")
    if isinstance(items, list):
        out = []
        for d in items:
            if not isinstance(d, dict):
                continue
            up = _strip_label_prefix(str(d.get("업태", "") or "").strip())
            if up in _LABEL_WORDS:
                up = ""
            jong = _split_items(d.get("종목") or d.get("종목들") or d.get("종목목록"))
            if up or jong:
                out.append({"업태": up, "종목": jong})
        if out:
            return out

    # 병렬 리스트 형식 {"업태목록":[...], "종목목록":[...]} → 위치로 1:1
    up_list = _clean_list(parsed.get("업태목록") or parsed.get("업태"))
    jong_list = _clean_list(parsed.get("종목목록") or parsed.get("종목"))
    if up_list or jong_list:
        return [
            {"업태": a, "종목": [b] if b else []}
            for a, b in zip_longest(up_list, jong_list, fillvalue="")
            if a or b
        ]

    # {"목록":[{"업태":..,"종목":..}]}
    lst = parsed.get("목록") or parsed.get("list")
    if isinstance(lst, list):
        out = []
        for d in lst:
            if isinstance(d, dict):
                up = str(d.get("업태", "") or "").strip()
                up = "" if up in _LABEL_WORDS else _strip_label_prefix(up)
                jong = _split_items(d.get("종목"))
                if up or jong:
                    out.append({"업태": up, "종목": jong})
        return out
    return []


def extract_categories(image, model, processor, debug: bool = False) -> list[dict]:
    raw = ask_image(model, processor, image, _CATEGORY_PROMPT)
    if debug:
        print(f"  [debug] 업태·종목 raw 응답: {raw!r}")
    return groups_from_parsed(parse_json(raw))


# 내부 영어 key (schema.sql / 필드매핑과 맞춤)
_BIZ_KEYS = [
    "trade_name", "corp_name", "ceo_name", "biz_no", "corp_no",
    "birth_date", "open_date", "address_basic",
]


def extract_record(path, model, processor, with_category, max_side, debug=False) -> dict:
    """이미지/PDF 한 개 → 구조화된 레코드(dict)."""
    tmp_files = []
    try:
        if path.lower().endswith(".pdf"):
            raw_png = pdf_first_page_to_png(path)
            tmp_files.append(raw_png)
            image_path, size = prep_image(raw_png, max_side)
        else:
            image_path, size = prep_image(path, max_side)
        tmp_files.append(image_path)
        if debug:
            print(f"  [debug] 전처리 후 크기: {size}")

        biz_type, biz_cert = extract_biz_cert(image_path, model, processor)

        groups = []
        if with_category:
            cat_img = _load_image(image_path)
            cat_img = _upscale(cat_img, _CATEGORY_MIN_SIDE)  # 접힌/작은 글씨 대응
            groups = extract_categories(cat_img, model, processor, debug)

        record = {"source_file": os.path.basename(path), "biz_type": biz_type}
        record.update({k: biz_cert.get(k, "") for k in _BIZ_KEYS})
        record["business_category"] = groups  # [{"업태": str, "종목": [str, ...]}]
        return record
    finally:
        for f in tmp_files:
            if os.path.exists(f):
                os.remove(f)


def record_to_rows(record: dict) -> list[dict]:
    """레코드 → CSV 행 리스트 (업태-종목 쌍마다 1행)."""
    base = {
        "파일": record["source_file"],
        "biz_type": record["biz_type"],
        "상호_법인명": record.get("corp_name") or record.get("trade_name", ""),
        "대표자": record.get("ceo_name", ""),
        "등록번호": record.get("biz_no", ""),
        "법인등록번호": record.get("corp_no", ""),
        "생년월일": record.get("birth_date", ""),
        "개업연월일": record.get("open_date", ""),
        "사업장소재지": record.get("address_basic", ""),
    }
    cats = record.get("business_category") or []
    rows = []
    for gi, c in enumerate(cats, start=1):
        up = c.get("업태", "")
        jongs = c.get("종목") or [""]
        if isinstance(jongs, str):
            jongs = [jongs]
        for j in jongs:
            rows.append({**base, "순번": gi, "업태": up, "종목": j})
    return rows or [{**base, "순번": "", "업태": "", "종목": ""}]


def resolve_inputs(patterns: list[str]) -> list[str]:
    paths = []
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        paths.extend(hits if hits else [pat])
    return paths


def _write_json(path: str, obj) -> None:
    import json

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="사업자등록증 이미지/PDF → OCR → CSV/JSON")
    parser.add_argument("inputs", nargs="+", help="이미지/PDF 경로 (glob 가능)")
    parser.add_argument("--out", help="출력 CSV 경로")
    parser.add_argument("--json-dir", help="파일별 JSON을 저장할 폴더")
    parser.add_argument("--json", help="전체 결과를 한 JSON 배열 파일로 저장")
    parser.add_argument("--max-side", type=int, default=DEFAULT_MAX_SIDE, help=f"이미지 긴 변 상한 px (기본 {DEFAULT_MAX_SIDE})")
    parser.add_argument("--dtype", choices=["bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--no-category", action="store_true", help="업태·종목 추출 건너뜀")
    parser.add_argument("--debug", action="store_true", help="모델 raw 응답 등 출력")
    args = parser.parse_args()

    if not (args.out or args.json_dir or args.json):
        parser.error("--out / --json-dir / --json 중 하나는 지정하세요.")

    paths = resolve_inputs(args.inputs)
    with_category = not args.no_category

    print(f"모델 로딩({args.dtype}) 중...")
    model, processor = load_model(args.dtype)
    print("로딩 완료\n")

    records, rows = [], []
    for path in paths:
        name = os.path.basename(path)
        print(f"[{name}] 추출 중...")
        if not os.path.exists(path):
            print("  실패: 파일 없음\n")
            rec = {"source_file": name, "biz_type": "ERROR: 파일 없음", "business_category": []}
        else:
            try:
                rec = extract_record(path, model, processor, with_category, args.max_side, args.debug)
                print(f"  판별: {rec['biz_type']}")
                for k in _BIZ_KEYS:
                    if rec.get(k):
                        print(f"  {k}: {rec[k]}")
                cats = rec.get("business_category") or []
                if cats:
                    print(f"  업태·종목 {len(cats)}개 그룹:")
                    for i, c in enumerate(cats, 1):
                        print(f"    {i}. {c['업태']} → {', '.join(c.get('종목') or [])}")
                elif with_category:
                    print("  업태·종목: (추출 안 됨)")
            except Exception as e:
                print(f"  실패: {type(e).__name__}: {str(e)[:200]}")
                rec = {"source_file": name, "biz_type": f"ERROR: {type(e).__name__}", "business_category": []}
        records.append(rec)
        rows.extend(record_to_rows(rec))
        if args.json_dir:
            _write_json(os.path.join(args.json_dir, os.path.splitext(name)[0] + ".json"), rec)
        print()

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV 저장 -> {args.out} ({len(rows)}행)")
    if args.json:
        _write_json(args.json, records)
        print(f"JSON 저장 -> {args.json} ({len(records)}건)")
    if args.json_dir:
        print(f"파일별 JSON 저장 -> {args.json_dir}/ ({len(records)}개)")


if __name__ == "__main__":
    main()
