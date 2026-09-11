from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

# =============================================================================
# 27_parse_ksic_haeseol.py
#
# 목적
# - 통계청 "한국표준산업분류 제11차 개정 해설서" PDF를 파싱한다.
# - 각 세세분류(5자리 KSIC 코드)마다:
#     · 정의
#     · <예 시>  = 이 코드에 속하는 활동 목록      ← 정답 라벨 근거
#     · <제 외>  = 안 속하는 활동 + 올바른 코드     ← 애매 케이스 판정 규칙
#   을 추출한다.
# - KSIC 코드 -> 6자리 업종코드 매핑(ksic_clean.csv)을 붙인다.
#
# 출력: data/processed/ksic_haeseol_v1.json  (엔트리 리스트)
#       data/processed/ksic_haeseol_examples_v1.csv  (예시활동 1행 = 1건, 라벨 붙음)
#
# 이 파일들이 이후 정답셋(gold set) 자동 생성의 근거가 된다.
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_PDF = PROJECT_ROOT / "data" / "raw" / "KSIC_11차_해설서.pdf"
KSIC_CLEAN_CSV = PROJECT_ROOT / "data" / "processed" / "ksic_clean.csv"
OUT_JSON = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_v1.json"
OUT_CSV = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_examples_v1.csv"

BULLET = "․"  # ․ (해설서가 쓰는 가운뎃점)

# 페이지 머리말/꼬리말/세로 사이드바로 들어오는 잡음
NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*대분류\s+[A-Z]\s*$"),
    re.compile(r"^\s*(제\s*조\s*업|건\s*설\s*업|농\s*업|광\s*업|도\s*소\s*매\s*업|숙\s*박\s*및\s*음\s*식\s*점\s*업|운\s*수\s*업|정\s*보\s*통\s*신\s*업|금\s*융\s*및\s*보\s*험\s*업|부\s*동\s*산\s*업|사\s*업\s*시\s*설\s*관\s*리|교\s*육\s*서\s*비\s*스\s*업|보\s*건\s*업|예\s*술\s*스\s*포\s*츠|협\s*회\s*및\s*단\s*체)\s*$"),
    re.compile(r"^\s*\d{1,4}\s*$"),          # 페이지 번호
    re.compile(r"^\s*[A-Z]\s*$"),            # 사이드바 대분류 알파벳
    re.compile(r"^\s*[가-힣]\s*$"),          # 사이드바 세로글자 (제/조/업 등 한 글자)
]

# 세세분류 헤더:  "10301 김치류 제조업"  /  "01110  곡물 및 기타 식량작물 재배업"
DETAIL_HEADER = re.compile(r"^(\d{5})\s+([^\n]{2,40})$")
# 상위(2~4자리) 헤더 — 여기서 새 엔트리 종료 신호로만 씀
COARSE_HEADER = re.compile(r"^(\d{2,4})\s+([^\n]{2,40})$")
CODE_IN_PAREN = re.compile(r"\(([0-9]{2,5})\)")

# 분류항목표/개정표에서 온 가짜 헤더 걸러내기
BAD_NAME = re.compile(r"\d|코드변경|명칭변경|신설|세분|통합|이동|분할|흡수")
# 해설 정의 문장의 특징 (분류항목표에는 없음)
DEF_MARKER = re.compile(r"(말한다|포함한다|제외한다|산업활동)")


def is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    return any(p.match(s) for p in NOISE_LINE_PATTERNS)


def extract_pages(pdf_path: Path) -> list[str]:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for pg in pdf.pages:
            pages.append(pg.extract_text() or "")
    return pages


def clean_lines(pages: list[str]) -> list[str]:
    out: list[str] = []
    for txt in pages:
        for raw in txt.split("\n"):
            if is_noise(raw):
                continue
            out.append(raw.rstrip())
    return out


# 페이지 머리말로 자주 새어 들어오는 대분류명 조각
HEADER_BLEED = re.compile(
    r"^(농업[, ]*임업|광\s*업|제\s*조\s*업|건\s*설\s*업|도매 및 소매업|숙박 및 음식점업|"
    r"운수 및 창고업|정보통신업|금융 및 보험업|부동산업|전문[, ]*과학|사업시설|공공행정|"
    r"교육 서비스업|보건업|예술[, ]*스포츠|협회 및 단체|대분류)"
)


def _clean_item(p: str) -> str:
    p = re.sub(r"\s+", " ", p).strip(" ·.;，,")
    # 세로 사이드바에서 붙은 한 글자(업/조/제/임/어 등) 꼬리 제거
    p = re.sub(r"\s+[가-힣]$", "", p).strip()
    return p


def split_items(block_lines: list[str]) -> list[str]:
    """<예 시> / <제 외> 블록의 줄들을 활동 항목 리스트로."""
    text = " ".join(block_lines)
    parts = re.split(rf"[{BULLET}·]|\s{{3,}}", text)
    items = []
    for p in parts:
        p = _clean_item(p)
        if len(p) < 2 or HEADER_BLEED.match(p):
            continue
        items.append(p)
    return items


def parse_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    i = 0
    n = len(lines)

    while i < n:
        m = DETAIL_HEADER.match(lines[i].strip())
        if not m:
            i += 1
            continue

        code = m.group(1)
        name = re.sub(r"\s+", " ", m.group(2)).strip()
        i += 1

        body: list[str] = []
        while i < n:
            s = lines[i].strip()
            if DETAIL_HEADER.match(s) or COARSE_HEADER.match(s):
                break
            body.append(lines[i])
            i += 1

        # body 안에서 <예 시> / <제 외> 분리
        definition: list[str] = []
        examples_block: list[str] = []
        excludes_block: list[str] = []
        section = "def"
        for ln in body:
            s = ln.strip()
            if re.match(r"^<\s*예\s*시\s*>", s):
                section = "ex"
                continue
            if re.match(r"^<\s*제\s*외\s*>", s):
                section = "exc"
                continue
            if section == "def":
                definition.append(s)
            elif section == "ex":
                examples_block.append(s)
            else:
                excludes_block.append(s)

        examples = split_items(examples_block)
        excludes_raw = split_items(excludes_block)
        excludes = []
        for ex in excludes_raw:
            codes = CODE_IN_PAREN.findall(ex)
            activity = CODE_IN_PAREN.sub("", ex).strip(" ·.,()")
            excludes.append({"activity": activity, "codes": codes})

        definition_text = re.sub(r"\s+", " ", " ".join(definition)).strip()

        # 가짜 헤더(분류항목표/개정표) 배제:
        # - 이름에 숫자/개정어가 있거나
        # - 정의도 예시도 없으면(분류항목표는 이름만 있음)
        if BAD_NAME.search(name):
            continue
        if not examples and not DEF_MARKER.search(definition_text):
            continue

        entries.append({
            "ksic_code": code,
            "ksic_name": name.split("  ")[0].strip(),
            "definition": definition_text,
            "examples": examples,
            "excludes": excludes,
        })

    # 같은 KSIC 코드가 여러 번 잡히면 내용이 가장 풍부한 것만 남긴다
    best: dict[str, dict] = {}
    for e in entries:
        score = len(e["definition"]) + 20 * len(e["examples"]) + 20 * len(e["excludes"])
        cur = best.get(e["ksic_code"])
        if cur is None or score > cur["_score"]:
            e["_score"] = score
            best[e["ksic_code"]] = e
    out = sorted(best.values(), key=lambda x: x["ksic_code"])
    for e in out:
        e.pop("_score", None)
    return out


def attach_business_codes(entries: list[dict]) -> list[dict]:
    if not KSIC_CLEAN_CSV.exists():
        print(f"[경고] {KSIC_CLEAN_CSV} 없음 — 업종코드 매핑 생략")
        return entries

    ref = pd.read_csv(KSIC_CLEAN_CSV, dtype=str).fillna("")
    ksic_to_biz: dict[str, list[str]] = {}
    biz_name: dict[str, str] = {}
    ksic_name: dict[str, str] = {}
    biz_to_ksic: dict[str, set] = {}
    for _, r in ref.iterrows():
        k = r["KSIC_코드"].strip()
        b = r["국세청_업종코드"].strip()
        if k and b:
            ksic_to_biz.setdefault(k, [])
            if b not in ksic_to_biz[k]:
                ksic_to_biz[k].append(b)
            biz_name[b] = r["국세청_세세분류명"].strip()
            ksic_name[k] = r["KSIC_세세분류명"].strip()
            biz_to_ksic.setdefault(b, set()).add(k)

    for e in entries:
        k = e["ksic_code"]
        codes = ksic_to_biz.get(k, [])
        e["business_codes"] = codes
        e["business_names"] = [biz_name.get(c, "") for c in codes]
        # 연계표의 공식 세세분류명으로 교체(파싱 노이즈 제거)
        if ksic_name.get(k):
            e["ksic_name"] = ksic_name[k]
        # 이 업종코드가 오직 이 KSIC 하나에만 연결되면 라벨이 가장 깨끗함
        e["business_codes_clean"] = [
            c for c in codes if biz_to_ksic.get(c) == {k}
        ]
    return entries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--out-csv", type=Path, default=OUT_CSV)
    args = ap.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(
            f"해설서 PDF를 찾을 수 없습니다: {args.pdf}\n"
            "통계청 통계분류포털에서 '한국표준산업분류 제11차 개정 해설서' PDF를 받아\n"
            f"위 경로에 두세요."
        )

    print(f"PDF 읽는 중: {args.pdf}")
    pages = extract_pages(args.pdf)
    print(f"  페이지 수: {len(pages)}")

    lines = clean_lines(pages)
    entries = parse_entries(lines)
    entries = attach_business_codes(entries)

    with_ex = [e for e in entries if e["examples"]]
    with_biz = [e for e in entries if e.get("business_codes")]
    biz_covered = set()
    biz_covered_clean = set()
    for e in entries:
        biz_covered.update(e.get("business_codes", []))
        biz_covered_clean.update(e.get("business_codes_clean", []))

    print(f"\n파싱된 세세분류 엔트리: {len(entries)}  (11차 KSIC 세세분류 ≈ 1,196)")
    print(f"  <예 시> 있는 엔트리 : {len(with_ex)}")
    print(f"  <제 외> 있는 엔트리 : {sum(1 for e in entries if e['excludes'])}")
    print(f"  업종코드 매핑된 엔트리: {len(with_biz)}")
    print(f"  커버된 업종코드      : {len(biz_covered)} / 1,612")
    print(f"  1:1 깨끗한 업종코드  : {len(biz_covered_clean)} / 1,612  (라벨로 바로 쓸 수 있음)")

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON 저장: {args.out_json}")

    # 예시활동 1행 = 1건 (라벨 후보)
    rows = []
    for e in entries:
        for ex in e["examples"]:
            rows.append({
                "ksic_code": e["ksic_code"],
                "ksic_name": e["ksic_name"],
                "example_activity": ex,
                "business_codes": ";".join(e.get("business_codes", [])),
                "business_names": " | ".join(n for n in e.get("business_names", []) if n),
            })
    pd.DataFrame(rows).to_csv(args.out_csv, index=False, encoding="utf-8-sig")
    print(f"CSV 저장 : {args.out_csv}  ({len(rows)}건)")

    print("\n[샘플 5개]")
    for e in entries[:5]:
        print(f"\n  {e['ksic_code']} {e['ksic_name']}  -> 업종코드 {e.get('business_codes')}")
        print(f"    정의: {e['definition'][:80]}")
        print(f"    예시: {e['examples'][:4]}")
        if e["excludes"]:
            print(f"    제외: {[(x['activity'][:24], x['codes']) for x in e['excludes'][:3]]}")

    print("\n[커피 관련 확인]")
    for e in entries:
        if "커피" in e["ksic_name"]:
            print(f"  {e['ksic_code']} {e['ksic_name']} 업종코드={e.get('business_codes')}")
            print(f"    예시: {e['examples']}")
            print(f"    제외: {[(x['activity'], x['codes']) for x in e['excludes']]}")


if __name__ == "__main__":
    main()
