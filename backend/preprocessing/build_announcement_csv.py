# build_announcement_csv.py
#
# [2026-09-05 추가] bizinfo API에서 공고를 받아와 pipeline.process_notice()로
# 지역/업종 매칭까지 거친 뒤, DB 컬럼 설계(컬럼명.xlsx 기준 27개 컬럼)에 맞춰
# 테스트용 CSV를 만든다. 컬럼별 값 출처와 임시 처리(placeholder) 판단 근거는
# docs/announcement_csv_columns.md에 정리해뒀다 — 두 파일을 같이 업데이트할 것.
#
# 아직 규칙이 없어서 비워두는 컬럼(announcement_id는 임시 순번, target_age_groups/
# business_age_condition/management_no는 null)도 전부 이 문서에서 사유를 설명함.

import argparse
import csv
import json
import os
from datetime import datetime

from backend.crawler.bizinfo_api import fetch_page
from backend.preprocessing.pipeline import process_notice

COLUMNS = [
    "announcement_id", "source", "raw_bizinfo_id", "raw_kstartup_id",
    "title", "content", "host_org_name", "supervising_org", "contact",
    "category", "target_summary", "target_age_groups", "business_age_condition",
    "apply_start_date", "apply_end_date", "apply_method", "detail_page_url",
    "regions", "region_status", "region_needs_review",
    "ksic_codes_matched", "ksic_names_matched", "ksic_codes_excluded", "ksic_status",
    "management_no", "collected_at", "updated_at",
]

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "data", "announcements_test_50.csv")


def _json_array(pipe_delimited: str) -> str:
    """pipeline 결과의 '|' 구분 문자열을 JSON 배열 문자열로 변환. 빈 값이면 빈 배열."""
    items = [x for x in (pipe_delimited or "").split("|") if x]
    return json.dumps(items, ensure_ascii=False)


def _needs_region_review(region_status: str) -> bool:
    """[2026-09-05 신규] 업종엔 이미 '업종_확인필요' 판정이 있는데 지역엔 없었음.
    추정성 상태값(inferred_*)이거나 끝까지 못 찾은 경우(unparsed)만 확인필요로 본다."""
    return region_status.startswith("inferred_") or region_status == "unparsed"


def build_row(seq_no: int, raw_row: dict, now: str) -> dict:
    result = process_notice(raw_row, source="bizinfo", use_llm_fallback=False)

    lclas = raw_row.get("pldirSportRealmLclasCodeNm", "") or ""
    mlsfc = raw_row.get("pldirSportRealmMlsfcCodeNm", "") or ""
    category = " > ".join(p for p in [lclas, mlsfc] if p)

    period = raw_row.get("reqstBeginEndDe", "") or ""
    if "~" in period:
        start_date, end_date = (p.strip() for p in period.split("~", 1))
    else:
        start_date, end_date = "", ""

    return {
        # [placeholder] 통합ID 규칙 미정 — 확정되기 전까지 임시 순번만 사용
        "announcement_id": seq_no,
        "source": "bizinfo",
        "raw_bizinfo_id": raw_row.get("pblancId", ""),
        "raw_kstartup_id": "",  # 이번 소스(bizinfo)엔 해당 없음
        "title": raw_row.get("pblancNm", ""),
        "content": result.get("원문", ""),
        "host_org_name": raw_row.get("excInsttNm", ""),
        "supervising_org": raw_row.get("jrsdInsttNm", ""),
        "contact": raw_row.get("refrncNm", ""),
        "category": category,
        "target_summary": raw_row.get("trgetNm", ""),
        # [placeholder] bizinfo API에 없는 정보 — 다른 API 연동 전까지 null
        "target_age_groups": "",
        "business_age_condition": "",
        "apply_start_date": start_date,
        "apply_end_date": end_date,
        "apply_method": raw_row.get("reqstMthPapersCn", ""),
        "detail_page_url": raw_row.get("pblancUrl", ""),
        "regions": _json_array(result.get("region_list", "")),
        "region_status": result.get("region_status", ""),
        "region_needs_review": _needs_region_review(result.get("region_status", "")),
        "ksic_codes_matched": _json_array(result.get("확정코드", "")),
        "ksic_names_matched": _json_array(result.get("확정업종명", "")),
        "ksic_codes_excluded": _json_array(result.get("제외코드", "")),
        "ksic_status": result.get("확정단계", ""),
        # [placeholder] 중복공고 판별 로직 없음 — 로직 생기기 전까지 null
        "management_no": "",
        "collected_at": now,
        "updated_at": now,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50, help="받아올 공고 건수 (기본 50)")
    parser.add_argument("--output", default=None, help="출력 CSV 경로 (기본: data/announcements_test_50.csv)")
    args = parser.parse_args()

    output_path = args.output or DEFAULT_OUTPUT

    data = fetch_page(1, args.count)
    items = data.get("jsonArray", [])
    if isinstance(items, dict):
        items = [items]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for i, raw_row in enumerate(items, start=1):
        print(f"[{i}/{len(items)}] {raw_row.get('pblancId', '')} 처리 중...")
        rows.append(build_row(i, raw_row, now))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n완료: {len(rows)}건 -> {output_path}")


if __name__ == "__main__":
    main()
