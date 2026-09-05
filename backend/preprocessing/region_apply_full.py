# region_apply_full.py
# region_apply_short.py의 1,589건 전체판.
# bizinfo.csv(1,589) + full_raw_texts_1589.csv(원문) -> 지역 매핑 전체 실행.

import csv
import os

csv.field_size_limit(10_000_000)  # 원문 컬럼이 길어서 기본 필드 제한 초과 방지

from backend.preprocessing.extract_region import extract_region

# [2026-09-05 주석처리] data/raw/bizinfo.csv, data/outputs/full_raw_texts_1589.csv
# 파일을 미리 준비해둬야 하는 CSV 배치 방식 대신, API에서 받은 데이터를 바로
# pipeline.process_notice()에 넘겨 매칭하는 방식(파일 의존성 없음)을 쓰기로
# 결정하여 이 배치 실행 경로(main() 이하)는 당분간 쓰지 않는다. STATUS_DESC는
# pipeline.py가 그대로 가져다 쓰므로 유지한다.
# BASE = os.path.dirname(os.path.abspath(__file__))
# RAW_CSV = os.path.join(BASE, "data", "raw", "bizinfo.csv")
# TEXT_CSV = os.path.join(BASE, "data", "outputs", "full_raw_texts_1589.csv")
# OUT_CSV = os.path.join(BASE, "data", "processed", "region_full.csv")

STATUS_DESC = {
    "parsed": "제목 지역태그",
    "parsed_multi": "제목 복수지역",
    "parsed_group": "제목 권역",
    "parsed_group_exclusion": "제목 제외권역",
    "parsed_from_fulltext": "원문 지역조건",
    "parsed_from_target_section": "대상/자격 섹션",
    "parsed_from_body": "사업요약문",
    "parsed_from_source_field": "원본 구조화 필드(K-Startup)",
    "explicit_nationwide": "전국 명시",
    "no_restriction": "지역 제한 없음",
    "inferred_no_restriction": "지역 제한 없음 추정",
    "inferred_from_jrsd": "소관기관 기반 추정",
    "unparsed": "판정 실패",
}


# [2026-09-05 주석처리] 아래는 data/raw/bizinfo.csv + data/outputs/full_raw_texts_1589.csv
# 두 CSV를 읽어 1,589건을 한 번에 재처리하던 배치 실행 로직이다. API에서 받은
# 데이터를 CSV로 미리 캐싱해둘 필요 없이 바로 process_notice()에 넘기는 방식으로
# 대체하기로 해서(사유: 매번 최신 공고를 API로 직접 받아 테스트하고 싶어서,
# 별도 CSV 준비 단계 없이 바로 확인 가능하게), 이 batch 진입점은 쓰지 않는다.
# 필요해지면 이 주석만 풀면 그대로 다시 동작한다(로직 자체는 안 건드림).
#
# def load_csv(path):
#     if not os.path.exists(path):
#         raise FileNotFoundError(f"파일 없음: {path}")
#     with open(path, encoding="utf-8-sig") as f:
#         return list(csv.DictReader(f))
#
#
# def main():
#     raw_rows = load_csv(RAW_CSV)
#     text_rows = load_csv(TEXT_CSV)
#     text_by_id = {r["공고ID"]: r.get("원문", "") for r in text_rows}
#
#     results = []
#     status_counts = {}
#
#     for i, row in enumerate(raw_rows, start=1):
#         notice_id = row.get("pblancId", "")
#         full_text = text_by_id.get(notice_id, "")
#
#         result = extract_region(
#             row.get("pblancNm", ""),
#             row.get("jrsdInsttNm", ""),
#             row.get("bsnsSumryCn", ""),
#             full_text=full_text,
#         )
#
#         status = result.get("status", "")
#         status_counts[status] = status_counts.get(status, 0) + 1
#
#         results.append({
#             "번호": i,
#             "공고ID": notice_id,
#             "공고명": row.get("pblancNm", ""),
#             "region_display": result.get("display", ""),
#             "region_list": "|".join(result.get("regions") or []),
#             "region_status": status,
#             "region_method": STATUS_DESC.get(status, ""),
#             "had_full_text": "Y" if full_text.strip() else "N",
#         })
#
#     os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
#
#     with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
#         writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
#         writer.writeheader()
#         writer.writerows(results)
#
#     print("=== 지역 매핑 완료 (1,589건 전체) ===")
#     print(f"공고 수 : {len(results)}건")
#     print(f"결과 파일 : {OUT_CSV}")
#     print("\n=== status 분포 ===")
#     for k, v in sorted(status_counts.items(), key=lambda x: -x[1]):
#         print(f"  {k:28s} {STATUS_DESC.get(k, ''):12s} {v:5d}건")
#
#
# if __name__ == "__main__":
#     main()
