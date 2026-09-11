from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

# =============================================================================
# 25_prepare_business_code_docs.py
#
# 목적 (벤치마킹: 영국 ONS ClassifAI)
# - "업종코드 1개 = 거대한 문서 1개" 구조를 버린다.
# - 업종코드 1개를 여러 개의 짧고 깨끗한 검색 문서로 쪼갠다.
#     · name    : 세세분류(활동명) 그 자체              ← 가장 순수한 신호
#     · hier    : 대>중>소>세분류 계층 경로             ← 맥락
#     · ksic    : 연계 KSIC 분류명                     ← 다른 표현의 같은 개념
#     · desc    : 세부설명 (reference CSV, 있을 때만)
#     · def     : KSIC 11차 해설서 '정의문'            ← 공식 설명 (27번)
#     · example : KSIC 11차 해설서 <예시> 활동 문구      ← 구체 활동, 반직관 케이스 포함 (27번)
#
# 왜 def / example 을 넣나 (2026-09-09)
# - 검색 실패 47건 분석 결과, 정답 코드명이 활동 설명과 한 단어도 안 겹치는
#   "반직관" 케이스가 많았다 (밀가루 제조 -> 곡물 제분업, 깃털 장식 -> 전시용 모형 제조업).
# - 이런 연결고리는 통계청 해설서 <예시>에 그대로 들어 있는데, 그동안 검색 인덱스에는
#   안 담겨 있었다 (27번은 정답셋 생성용으로만 썼음).
# - example 문구를 색인하면 "이 활동 = 이 코드" 매핑이 검색으로 직접 잡힌다.
#
# 중요
# - 문서 텍스트에 코드 숫자("154901", "10891")와 라벨("업종코드:")을 넣지 않는다.
#   → 이것들이 모든 임베딩 벡터를 희석시켜 검색이 헛발질하는 원인이었다.
# - 원본/21번 reference CSV는 건드리지 않는다. 여기서는 그걸 읽어 docs CSV만 새로 만든다.
#
# 입력 : data/processed/business_code_chroma_reference_v1.csv   (21번 출력)
#        data/processed/ksic_haeseol_examples_v1.csv            (27번 출력)
#        data/processed/ksic_haeseol_v1.json                    (27번 출력, 정의문)
# 출력 : data/processed/business_code_docs_v1.csv
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "business_code_chroma_reference_v1.csv"
DEFAULT_EXAMPLES = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_examples_v1.csv"
DEFAULT_HAESEOL_JSON = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_v1.json"
DEFAULT_KSIC_CLEAN = PROJECT_ROOT / "data" / "processed" / "ksic_clean.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "business_code_docs_v1.csv"

# example 문서를 붙일 업종코드 화이트리스트 (한 줄에 6자리 코드 하나).
# 존재하면 이 코드들에만 example 문서를 붙인다 (선별 색인).
# 2026-09-09: 전 코드 일괄 색인은 제조업 예시가 소매/도매 후보 pool을 오염시켜
#   gold_v1 C Top1을 95%->83%로 떨어뜨림. 실제 검색 실패한 코드에만 붙이는 방식(ⓑ)으로 전환.
DEFAULT_EXAMPLE_WHITELIST = PROJECT_ROOT / "data" / "processed" / "example_index_whitelist.txt"

SEP = " | "  # 21번이 다중 값을 이 구분자로 합쳐 놓았다

# 해설서 예시 문구 하나가 지나치게 길면(여러 활동을 나열한 경우) 임베딩이 흐려진다.
EXAMPLE_MAX_LEN = 60
CODE_RE = re.compile(r"\d{6}")

# 파싱 노이즈(해설서 절 머리말·개요 문장 등)를 예시/경계 문서에서 걸러낸다.
_NOISE_RE = re.compile(r"대분류|중분류|소분류|개요|포함한다|제외한다|다음과 같|산업활동을 말한다|\(\d+\s*~\s*\d+\)|「|』")


def is_clean_phrase(phrase: str) -> bool:
    if not phrase or len(phrase) < 2 or len(phrase) > EXAMPLE_MAX_LEN:
        return False
    if _NOISE_RE.search(phrase):
        return False
    if phrase.count(" ") > 7 or phrase.endswith("다."):
        return False
    return True


def clean(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split()).strip()


def split_values(value: str) -> list[str]:
    """'A | B | C' -> ['A', 'B', 'C'] (빈 값/중복 제거, 순서 유지)."""
    out: list[str] = []
    for part in clean(value).split("|"):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def joined(value: str) -> str:
    """'A | B | C' -> 'A, B, C'  (사람이 읽는 한 줄)."""
    return ", ".join(split_values(value))


def split_codes(raw: str) -> list[str]:
    """'011007;011009' -> ['011007', '011009'] (6자리만)."""
    return [c for c in CODE_RE.findall(raw or "")]


def load_whitelist(path: Path) -> set[str] | None:
    """example 문서를 붙일 코드 집합. 파일 없으면 None(=전 코드 허용)."""
    if not path.exists():
        return None
    codes = {c for line in path.read_text(encoding="utf-8").splitlines()
             for c in CODE_RE.findall(line)}
    return codes


def load_haeseol_examples(path: Path, whitelist: set[str] | None) -> dict[str, list[str]]:
    """
    27번의 examples CSV -> {업종코드: [예시활동 문구, ...]}.
    한 예시 행이 여러 업종코드에 매핑되면 각 코드에 모두 붙인다.
    whitelist가 주어지면 그 코드에만 예시를 모은다 (선별 색인).
    """
    if not path.exists():
        print(f"[건너뜀] 해설서 예시 CSV 없음: {path}")
        return {}

    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    by_code: dict[str, list[str]] = {}
    for _, r in df.iterrows():
        phrase = clean(r.get("example_activity"))
        if not is_clean_phrase(phrase):
            continue
        for code in split_codes(r.get("business_codes", "")):
            if whitelist is not None and code not in whitelist:
                continue
            bucket = by_code.setdefault(code, [])
            if phrase not in bucket:
                bucket.append(phrase)
    return by_code


def load_ksic_to_business(path: Path) -> dict[str, set[str]]:
    """ksic_clean.csv -> {KSIC 5자리 코드: {업종코드, ...}}."""
    out: dict[str, set[str]] = {}
    if not path.exists():
        return out
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    kcol = "KSIC_코드" if "KSIC_코드" in df.columns else df.columns[10]
    bcol = "국세청_업종코드" if "국세청_업종코드" in df.columns else df.columns[0]
    for _, r in df.iterrows():
        k, b = clean(r[kcol]), clean(r[bcol])
        if CODE_RE.fullmatch(b):
            out.setdefault(k, set()).add(b)
    return out


def load_haeseol_excludes(path: Path, k2b: dict[str, set[str]]) -> dict[str, list[str]]:
    """
    27번 JSON의 <제외> 규칙 -> {업종코드: [그 코드로 '가야 하는' 활동 문구, ...]}.
    '이 활동은 A가 아니라 B로 간다'에서 B 코드에 그 활동을 양성 신호로 붙인다.
    검색 example 채널에서 경계 케이스를 잡게 한다.
    """
    if not path.exists() or not k2b:
        return {}
    entries = json.loads(path.read_text(encoding="utf-8"))
    by_code: dict[str, list[str]] = {}
    for e in entries:
        for x in e.get("excludes", []):
            phrase = clean(x.get("activity"))
            if not is_clean_phrase(phrase):
                continue
            dests: set[str] = set()
            for kc in x.get("codes", []):
                kc = clean(kc)
                if kc in k2b:
                    dests |= k2b[kc]
                else:  # 4자리 등 부분 코드 -> 접두 매칭
                    for kk, bb in k2b.items():
                        if kk.startswith(kc):
                            dests |= bb
            for code in dests:
                bucket = by_code.setdefault(code, [])
                if phrase not in bucket:
                    bucket.append(phrase)
    return by_code


def load_haeseol_definitions(path: Path) -> dict[str, str]:
    """
    27번의 haeseol JSON -> {업종코드: 정의문}.
    한 업종코드에 여러 KSIC 정의문이 걸리면 ' / '로 합친다.
    """
    if not path.exists():
        print(f"[건너뜀] 해설서 JSON 없음: {path}")
        return {}

    entries = json.loads(path.read_text(encoding="utf-8"))
    by_code: dict[str, list[str]] = {}
    for e in entries:
        definition = clean(e.get("definition"))
        if not definition:
            continue
        codes = e.get("business_codes_clean") or e.get("business_codes") or []
        for code in codes:
            code = clean(code)
            if not CODE_RE.fullmatch(code):
                continue
            bucket = by_code.setdefault(code, [])
            if definition not in bucket:
                bucket.append(definition)
    return {c: " / ".join(v) for c, v in by_code.items()}


def build_docs_for_row(
    row: pd.Series,
    examples_by_code: dict[str, list[str]],
    xref_by_code: dict[str, list[str]],
    definition_by_code: dict[str, str],
    with_def: bool,
) -> list[dict[str, str]]:
    code = clean(row["business_code"])
    docs: list[dict[str, str]] = []
    seen_text: set[str] = set()

    def add(doc_type: str, text: str) -> None:
        text = clean(text)
        if not text or text in seen_text:
            return
        seen_text.add(text)
        docs.append({
            "doc_id": f"{code}__{doc_type}{sum(1 for d in docs if d['doc_type'] == doc_type)}",
            "business_code": code,
            "doc_type": doc_type,
            "doc_text": text,
        })

    # 1) name : 세세분류(활동명). 여러 개면 각각 별도 문서.
    detail_names = split_values(row["biz_detail_names"]) or split_values(row["biz_sub_names"])
    for name in detail_names:
        add("name", name)

    # 2) hier : 계층 경로 (대 > 중 > 소 > 세분류)
    path_parts = [
        joined(row["biz_large_names"]),
        joined(row["biz_middle_names"]),
        joined(row["biz_small_names"]),
        joined(row["biz_sub_names"]),
    ]
    path = " > ".join(p for p in path_parts if p)
    if path:
        add("hier", path)

    # 3) ksic : 연계 KSIC 분류명 (main 우선, 없으면 linked 전체)
    ksic = joined(row["main_ksic_names"]) or joined(row["linked_ksic_names"])
    if ksic:
        add("ksic", ksic)

    # 4) desc : 세부설명 (있고, 2글자 이상일 때만)
    desc = joined(row["detail_descriptions"])
    if len(desc) >= 2:
        add("desc", desc)

    # 5) def : 해설서 정의문 (--with-def 일 때만)
    if with_def:
        add("def", definition_by_code.get(code, ""))

    # 6) example : 해설서 <예시> 활동 문구 (각각 별도 문서)
    for phrase in examples_by_code.get(code, []):
        add("example", phrase)

    # 7) xref : 해설서 <제외>에서 "이 코드로 와야 한다"고 지목된 경계 활동
    for phrase in xref_by_code.get(code, []):
        add("xref", phrase)

    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="업종코드 1개 -> 검색 문서 여러 개로 확장")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--haeseol-json", type=Path, default=DEFAULT_HAESEOL_JSON)
    parser.add_argument("--ksic-clean", type=Path, default=DEFAULT_KSIC_CLEAN)
    parser.add_argument("--example-whitelist", type=Path, default=DEFAULT_EXAMPLE_WHITELIST,
                        help="이 파일의 코드에만 example 문서를 붙인다. 'none'이면 전 코드.")
    parser.add_argument("--with-def", action="store_true",
                        help="KSIC 해설서 정의문(def) 문서도 넣는다. 기본은 넣지 않음.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"21번 reference CSV가 없습니다: {args.input}")

    ref = pd.read_csv(args.input, dtype={"business_code": str}, encoding="utf-8-sig")
    for col in ref.columns:
        if col != "source_row_count":
            ref[col] = ref[col].map(clean)

    whitelist = None if str(args.example_whitelist).lower() == "none" else load_whitelist(args.example_whitelist)
    if whitelist is not None:
        print(f"[선별 색인] example 문서를 붙일 코드: {len(whitelist)}개 ({args.example_whitelist.name})")
    else:
        print("[전체 색인] 모든 코드에 example 문서를 붙임")

    examples_by_code = load_haeseol_examples(args.examples, whitelist)
    k2b = load_ksic_to_business(args.ksic_clean)
    xref_by_code = load_haeseol_excludes(args.haeseol_json, k2b)
    definition_by_code = load_haeseol_definitions(args.haeseol_json) if args.with_def else {}

    all_docs: list[dict[str, str]] = []
    for _, row in ref.iterrows():
        all_docs.extend(build_docs_for_row(
            row, examples_by_code, xref_by_code, definition_by_code, args.with_def))

    out = pd.DataFrame(all_docs, columns=["doc_id", "business_code", "doc_type", "doc_text"])

    if out["doc_id"].duplicated().any():
        dups = out.loc[out["doc_id"].duplicated(), "doc_id"].head(5).tolist()
        raise RuntimeError(f"doc_id 중복: {dups}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")

    n_codes = ref["business_code"].nunique()
    n_docs = len(out)
    ref_codes = set(ref["business_code"])
    ex_codes = ref_codes & set(examples_by_code)
    def_codes = ref_codes & set(definition_by_code)
    print("\n" + "=" * 70)
    print("25번 문서 확장 완료")
    print("=" * 70)
    print(f"업종코드 수      : {n_codes:,}")
    print(f"생성 문서 수     : {n_docs:,}  (코드당 평균 {n_docs / n_codes:.1f}개)")
    print(f"해설서 예시 커버 : {len(ex_codes):,} 코드 / 정의문 커버 {len(def_codes):,} 코드")
    print(f"예시·정의 둘 다 없는 코드 : {n_codes - len(ex_codes | def_codes):,}")
    print(f"문서 유형별 분포 :")
    for dt, cnt in out["doc_type"].value_counts().items():
        print(f"  {dt:8s} {cnt:>6,}")
    codes_covered = out["business_code"].nunique()
    if codes_covered != n_codes:
        print(f"\n[경고] 문서가 없는 업종코드 {n_codes - codes_covered}개")
    print(f"\n출력 파일        : {args.output}")

    for probe in ["154901", "143107"]:
        rows = out[out["business_code"] == probe]
        print(f"\n[예시: {probe}]  문서 {len(rows)}개")
        for _, d in rows.iterrows():
            print(f"  [{d['doc_type']:8s}] {d['doc_text'][:70]}")


if __name__ == "__main__":
    main()
