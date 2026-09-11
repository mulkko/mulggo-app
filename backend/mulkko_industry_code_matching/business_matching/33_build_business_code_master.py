from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

try:  # Windows 콘솔(cp949)에서도 요약 출력이 깨지지 않도록
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# =============================================================================
# 33_build_business_code_master.py
#
# 목적 (개정 계획서 §10.1 "KSIC 기준 데이터")
# - 국세청 업종코드 1개 = 1행 인 통합 정보 테이블을 만든다.
# - 검색 색인(25·26)과 별개로, 사람이 읽고 골든셋 검수에 쓰는 "코드 사전".
#
# 출력 컬럼 (§10.1 대응)
#   business_code            국세청 6자리                           [키]
#   business_name            세세분류(활동)명
#   hierarchy_path           대 > 중 > 소 > 세 > 세세
#   biz_large/middle/small/sub_name   분류 경로 각 단계
#   linked_ksic_codes/names  연계 KSIC
#   definition               KSIC 11차 해설서 정의문                 (해설서 있을 때만)
#   include_activities       해설서 <예시> 활동 문구  ' | '          (포함 활동)
#   exclude_activities       해설서 <제외> 활동 문구  ' | '          (제외 활동)
#   detail_description       reference CSV 세부설명
#   representative_items     대표 품목·서비스   (규칙 추출: 예시에서 활동어 뗀 명사)
#   activity_terms           주요 활동어        (규칙 추출: 고정 어휘 매칭)
#   synonyms                 사용자 표현 동의어  (지금은 비움 — 필요한 코드만 LLM 보강 예정)
#   ksic_version             적용 KSIC 버전
#   has_haeseol              해설서(정의/포함/제외) 존재 여부
#
# 입력 : data/processed/business_code_chroma_reference_v1.csv   (21번 출력, 1,612행)
#        data/processed/ksic_haeseol_v1.json                    (27번 출력)
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REF_CSV = PROJECT_ROOT / "data" / "processed" / "business_code_chroma_reference_v1.csv"
HAESEOL_JSON = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_v1.json"
OUT_CSV = PROJECT_ROOT / "data" / "processed" / "business_code_master_v1.csv"
OUT_SUMMARY = PROJECT_ROOT / "data" / "processed" / "business_code_master_v1_summary.txt"

KSIC_VERSION = "KSIC 11차 (2024)"
SEP = "|"
CODE6_RE = re.compile(r"^\d{6}$")

# 주요 활동어 고정 어휘 (§10.1 "주요 활동어").
# 코드의 이름 + 정의 + 포함활동 문구에 등장하면 그 코드의 활동어로 본다.
ACTIVITY_VOCAB = [
    "재배", "사육", "양식", "어업", "벌목", "채취", "채굴", "양봉",
    "제조", "생산", "가공", "조립", "정제", "제련", "도축", "제분", "방적", "직조",
    "봉제", "성형", "주조", "단조", "인쇄", "제책",
    "건설", "시공", "축조", "설치", "해체", "포장공사",
    "도매", "소매", "판매", "유통", "중개", "알선", "경매", "위탁판매", "전자상거래",
    "운송", "운수", "배달", "택배", "보관", "창고", "하역",
    "출판", "방송", "제작", "배급", "상영", "녹음", "편집",
    "통신", "개발", "설계", "구축", "유지보수", "호스팅", "프로그래밍",
    "임대", "대여", "리스", "렌탈",
    "숙박", "음식", "조리", "주점", "출장음식", "제과",
    "금융", "대출", "보험", "투자", "중개매매",
    "부동산", "분양", "관리",
    "연구", "개발시험", "시험", "분석", "측정", "엔지니어링", "컨설팅", "자문", "회계", "법무", "번역", "디자인",
    "광고", "홍보", "시장조사",
    "고용알선", "인력공급", "경비", "청소", "방제", "조경관리", "콜센터",
    "교육", "강습", "훈련", "교습", "지도",
    "진료", "치료", "간병", "요양", "재활", "수의", "검사",
    "창작", "공연", "전시", "기획", "매니지먼트",
    "스포츠", "오락", "게임장", "노래연습장",
    "수리", "정비", "세탁", "미용", "이용", "피부관리", "장례", "예식",
]

# 예시 문구 끝에 붙는 활동어 → 떼어내면 "대표 품목" 이 남는다.
TRAIL_ACTIVITY_RE = re.compile(
    r"\s*(제조(업)?|생산|가공(업)?|판매(업)?|도매(업)?|소매(업)?|중개(업)?|"
    r"임대(업)?|대여|서비스(업)?|수리(업)?|공사(업)?|설치|운영|재배|사육|양식|어업|"
    r"운송|운수|배달|교육|강습|교습|진료|치료|시공|건설|제공|개발|제작|공급|알선|중개매매|영업)\s*$"
)

_NOISE_RE = re.compile(
    r"대분류|중분류|소분류|개요|포함한다|제외한다|다음과 같|산업활동을 말한다|"
    r"[（(]\s*\d+\s*[~∼]\s*\d+\s*[)）]|「|」|『|』"
)


def clean(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return " ".join(str(v).split()).strip()


def first_value(v: object) -> str:
    """'A | B | C' -> 'A' (21번이 다중 값을 파이프로 합쳐 놓음)."""
    for part in clean(v).split("|"):
        part = part.strip()
        if part:
            return part
    return ""


def is_clean_phrase(p: str) -> bool:
    if not p or len(p) < 2 or len(p) > 40:
        return False
    if _NOISE_RE.search(p):
        return False
    if p.count(" ") > 6 or p.endswith("다."):
        return False
    return True


def load_haeseol(path: Path) -> dict[str, dict[str, list[str]]]:
    """
    ksic_haeseol_v1.json -> {업종코드: {definition:[...], include:[...], exclude:[...]}}
    한 업종코드에 여러 KSIC 항목이 걸리면 합친다.
    """
    entries = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, list[str]]] = {}
    for e in entries:
        codes = [clean(c) for c in (e.get("business_codes_clean") or e.get("business_codes") or [])]
        codes = [c for c in codes if CODE6_RE.match(c)]
        if not codes:
            continue
        definition = clean(e.get("definition"))
        includes = [clean(x) for x in (e.get("examples") or [])]
        includes = [x for x in includes if is_clean_phrase(x)]
        excludes = [clean(x.get("activity")) for x in (e.get("excludes") or []) if isinstance(x, dict)]
        excludes = [x for x in excludes if is_clean_phrase(x)]
        for code in codes:
            slot = out.setdefault(code, {"definition": [], "include": [], "exclude": []})
            if definition and definition not in slot["definition"]:
                slot["definition"].append(definition)
            for x in includes:
                if x not in slot["include"]:
                    slot["include"].append(x)
            for x in excludes:
                if x not in slot["exclude"]:
                    slot["exclude"].append(x)
    return out


def extract_items(includes: list[str], fallback: str) -> list[str]:
    """포함활동 문구에서 끝의 활동어를 떼어 대표 품목만 남긴다."""
    items: list[str] = []
    for phrase in includes:
        head = TRAIL_ACTIVITY_RE.sub("", phrase).strip(" ·,")
        if head and 1 < len(head) <= 30 and head not in items:
            items.append(head)
    if not items and fallback:
        items.append(TRAIL_ACTIVITY_RE.sub("", fallback).strip() or fallback)
    return items[:15]


def extract_activity_terms(text: str) -> list[str]:
    hits = [t for t in ACTIVITY_VOCAB if t in text]
    # 짧은 어휘가 긴 어휘에 포함되면(예: '제조' vs '재제조') 중복 방지는 생략 — 단순 유지
    seen: list[str] = []
    for t in hits:
        if t not in seen:
            seen.append(t)
    return seen


def main() -> None:
    ref = pd.read_csv(REF_CSV, dtype=str).fillna("")
    haeseol = load_haeseol(HAESEOL_JSON)

    rows: list[dict[str, object]] = []
    for _, r in ref.iterrows():
        code = clean(r["business_code"])
        if not CODE6_RE.match(code):
            continue

        large = first_value(r.get("biz_large_names"))
        middle = first_value(r.get("biz_middle_names"))
        small = first_value(r.get("biz_small_names"))
        sub = first_value(r.get("biz_sub_names"))
        name = first_value(r.get("biz_detail_names")) or first_value(r.get("biz_sub_names"))
        path_parts = [p for p in [large, middle, small, sub, name] if p]
        hierarchy_path = " > ".join(dict.fromkeys(path_parts))

        h = haeseol.get(code, {})
        definition = " / ".join(h.get("definition", []))
        includes = h.get("include", [])
        excludes = h.get("exclude", [])
        detail_desc = clean(r.get("detail_descriptions"))

        term_src = " ".join([name, definition, " ".join(includes)])
        rows.append({
            "business_code": code,
            "business_name": name,
            "hierarchy_path": hierarchy_path,
            "biz_large_name": large,
            "biz_middle_name": middle,
            "biz_small_name": small,
            "biz_sub_name": sub,
            "linked_ksic_codes": clean(r.get("linked_ksic_codes")),
            "linked_ksic_names": clean(r.get("linked_ksic_names")),
            "definition": definition,
            "include_activities": SEP.join(includes),
            "exclude_activities": SEP.join(excludes),
            "detail_description": detail_desc,
            "representative_items": SEP.join(extract_items(includes, name)),
            "activity_terms": SEP.join(extract_activity_terms(term_src)),
            "synonyms": "",
            "ksic_version": KSIC_VERSION,
            "has_haeseol": bool(h.get("definition") or includes or excludes),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    n = len(df)
    with_def = int((df["definition"] != "").sum())
    with_inc = int((df["include_activities"] != "").sum())
    with_exc = int((df["exclude_activities"] != "").sum())
    with_hae = int(df["has_haeseol"].sum())
    with_items = int((df["representative_items"] != "").sum())
    with_terms = int((df["activity_terms"] != "").sum())
    no_term = df.loc[df["activity_terms"] == "", "business_code"].tolist()

    summary = "\n".join([
        f"business_code_master_v1.csv  —  {n}행 (국세청 업종코드 1개 = 1행)",
        f"  정의문 있음          : {with_def}  ({with_def*100//n}%)",
        f"  포함활동 있음        : {with_inc}  ({with_inc*100//n}%)",
        f"  제외활동 있음        : {with_exc}  ({with_exc*100//n}%)",
        f"  해설서 연결(정의/포함/제외 중 1+) : {with_hae}  ({with_hae*100//n}%)",
        f"  대표품목 추출됨      : {with_items}  ({with_items*100//n}%)",
        f"  활동어 추출됨        : {with_terms}  ({with_terms*100//n}%)",
        f"  동의어              : 0 (다음 단계에서 검색 실패 코드만 LLM 보강)",
        "",
        f"활동어 못 뽑은 코드 {len(no_term)}개 (규칙 어휘 미매칭 → LLM 보강 후보):",
        "  " + ", ".join(no_term[:40]) + (" ..." if len(no_term) > 40 else ""),
    ])
    OUT_SUMMARY.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\n[저장] {OUT_CSV}")


if __name__ == "__main__":
    main()
