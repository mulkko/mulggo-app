# 기업마당 원본 → 통합 공고 테이블 파이프라인 (2026-09-07)

`docs/announcement_csv_columns.md`(CSV 테스트용, 2026-09-05)의 다음 단계 —
CSV가 아니라 실제 PostgreSQL `announcements_raw_bizinfo` → `announcements`로
가는 "중간다리" 코드입니다. TA 작업 시 이 문서 + 아래 코드 파일만 보면
됩니다.

## 코드 위치

**`backend/preprocessing/sync_bizinfo_announcements.py`** (신규 파일 1개).
기존 파일(`extract_region.py`, `decide_industry.py`, `db/connection.py` 등)은
전혀 안 건드렸습니다 — 이 파일이 그것들을 그대로 호출만 합니다.

## 전체 흐름

```
announcements_raw_bizinfo (PostgreSQL SELECT)
        ↓
① 기본 전처리     clean_bizinfo()
   결측치는 원본 의미 보존(임의로 "없음"/0 안 채움), 텍스트 정규화
   (_x000D_/NBSP/zero-width space/BOM/CRLF 정리), bsns_sumry_cn HTML 제거,
   pblanc_id 중복은 updt_pnttm 최신 우선으로 대표 행 선택
        ↓
   공통 필드 변환   transform_bizinfo_to_common()
                  + parse_target_conditions() + normalize_support_fields()
   title/host_org_name/category 등 통합 스키마 컬럼명으로 매핑
        ↓
② 지역 매핑       map_regions()
   backend/preprocessing/extract_region.py::extract_region() 그대로 호출
   (새 판단 로직 없음)
        ↓
③ 업종코드 매핑    map_ksic()
   backend/ml/classifier/decide_industry.py::decide_industry() 그대로 호출
   (새 판단 로직 없음). 첨부파일 원문 추출(get_notice_full_text)도 이 단계에서.
        ↓
   최종 검증        validate_announcements()
   (통과분, 검토대상) 두 개로 분리 - 검증 실패해도 조용히 안 버림
        ↓
announcements (PostgreSQL UPSERT, raw_bizinfo_id 기준)
```

PostgreSQL엔 **맨 처음(RAW 조회)과 맨 마지막(UPSERT) 딱 두 번만** 접근합니다.
중간 단계는 전부 pandas DataFrame으로 전달(요청된 staging 방식).

## 실행 방법

```bash
cd C:/workspace/mulkko
python -m backend.preprocessing.sync_bizinfo_announcements
```

`run(only_unprocessed=True)`가 기본값 — `announcements`에 아직 없는
(raw_bizinfo_id 기준) 공고만 새로 처리합니다. 전체 재처리가 필요하면
`run(only_unprocessed=False)`로 호출.

## 필드 매핑 기준

`docs/announcement_csv_columns.md`(2026-09-05, 팀 확정본)를 그대로 따랐습니다:

| 컬럼 | 값 출처 |
|---|---|
| `host_org_name` | `exc_instt_nm` (수행기관) |
| `supervising_org` | `jrsd_instt_nm` (소관기관) |
| `category` | `pldir_sport_realm_lclas_code_nm` + `pldir_sport_realm_mlsfc_code_nm`을 `" > "`로 연결 |
| `target_age_groups`, `business_age_condition` | bizinfo 원본에 없음 → 항상 NULL (임의 추론 안 함) |
| `management_no` | 중복공고 판별 로직 자체가 없음 → 항상 NULL |

## TA가 알아야 할 미해결 사항 (이번 범위에서 의도적으로 안 고침)

1. **`backend/db/schema.sql`에 `announcements_raw_bizinfo`/`announcements` 테이블
   정의가 없습니다.** 더 단순한 `announcements_raw`/`announcements_parsed`만
   있음. 근데 `backend/crawler/bizinfo_api.py::save_to_db()`는 이미
   `announcements_raw_bizinfo`에 INSERT하는 코드가 있어서, 실제 Supabase엔
   schema.sql 밖에서 이미 테이블이 만들어져 있을 가능성이 높다고 가정하고
   짰습니다. **실행 전에 실제 DB에 두 테이블이 있는지 먼저 확인하세요.**
   없으면 DDL부터 필요합니다(이번엔 스키마를 임의로 만들지 않기로
   결정해서 안 만들었습니다).
2. **[2026-09-07 수정 완료] `refrnc_nm`(문의처) 크롤러 누락 - 고쳤습니다.**
   실제 raw CSV(`data/raw/bizinfo.csv`, 1589건)를 확인해보니 `refrncNm`
   컬럼에 1588건 담당기관/연락처 값이 이미 들어있었는데, `bizinfo_api.py`의
   INSERT 컬럼 목록에서 빠져 있어서 DB엔 저장이 안 되고 있었습니다.
   `bizinfo_api.py`(INSERT 컬럼 추가) + `sync_bizinfo_announcements.py`
   (`RAW_COLUMNS`/`TEXT_FIELDS`에 반영)를 고쳐서 `contact`가 실제로
   채워지도록 했습니다.
   **실행 전 필수**: 실제 Supabase `announcements_raw_bizinfo` 테이블에
   `refrnc_nm` 컬럼이 없으면 크롤러 INSERT가 바로 에러 납니다 —
   `ALTER TABLE announcements_raw_bizinfo ADD COLUMN refrnc_nm TEXT;`를
   먼저 실행하세요. 그리고 이 수정 이전에 이미 수집돼 있던 행들은
   `refrnc_nm` 값 자체가 없으므로, 크롤러를 다시 돌리기 전까지는 그
   행들의 `contact`가 계속 NULL입니다.
3. **`decide_industry()`가 최신 버전이 아닙니다.** 자매 프로젝트
   (`final_project/ksic_core`)에서 최근 2일간 여러 버그를 고쳤는데
   (업종무관 오판정, 제외/제한 키워드 인식, 직접코드 우선순위 등)
   `backend/ml/classifier/`엔 아직 반영 안 된 이전 버전입니다. 이번 작업
   범위에서 동기화는 의도적으로 제외했습니다(사용자 확인) — 필요 시
   별도 작업으로 진행.
4. **`company_type`/`support_field_large`/`support_field_medium`** 같은
   컬럼은 넣지 않았습니다 — 아직 팀이 검토/확정하지 않은 컬럼이라
   `announcement_csv_columns.md` 기준(27개 컬럼)만 따랐습니다. 나중에
   기업유형/지원분야 필터 기능에 필요해지면 그때 추가하면 됩니다
   (원본에 `trget_nm`/`pldirSportRealmLclasCodeNm`/`MlsfcCodeNm`으로
   이미 값은 존재함).
5. **첨부파일 원문 추출을 매번 새로 합니다.** `map_ksic()` 안에서
   `get_notice_full_text()`를 캐시 없이 매번 호출 - 같은 공고를 재처리할
   때마다 다시 다운로드/OCR합니다. 처리 건수가 많아지면 `announcements`에
   이미 저장된 `content`를 캐시로 재사용하는 로직을 추가하는 게 좋습니다.

K-Startup용은 별도 문서 `docs/kstartup_announcements_pipeline.md` 참고
(코드도 `sync_kstartup_announcements.py`로 완전히 분리돼 있습니다).
