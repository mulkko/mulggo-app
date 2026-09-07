# K-Startup 원본 → 통합 공고 테이블 파이프라인 (2026-09-07)

기업마당용(`docs/bizinfo_announcements_pipeline.md`)과 완전히 같은 9단계
구조를 K-Startup에 맞게 별도로 만든 것입니다. 코드도 문서도 기업마당과
독립된 파일입니다 — 서로 안 섞여 있습니다.

## 코드 위치

- **`backend/preprocessing/sync_kstartup_announcements.py`** — 전처리~UPSERT
  본 파이프라인
- **`backend/crawler/kstartup_seed_loader.py`** — raw 원본 1회 적재용
  (아래 "원본 데이터 준비" 참고)

기존 파일(`extract_region.py`, `pipeline.py`, `db/connection.py` 등)은
전혀 안 건드렸습니다.

## 기업마당과 다른 점 (딱 2가지)

1. **지역**: `extract_region()` 대신 이미 있던 `normalize_kstartup_region()`
   (`backend/preprocessing/extract_region.py`)을 씁니다. `supt_regin`
   구조화 필드를 직접 정규화하는 방식이라 텍스트 추론보다 신뢰도가 높습니다
   (253건 실측, 불일치 0건 - 기존 검증 결과).
2. **업종코드**: `decide_industry()`를 아예 호출하지 않습니다. 2026-09-04
   팀 결정(253건 재검증 결과 대부분 기관명 우연 충돌이라 신뢰 불가)에 따라
   전부 `"업종무관(기본값)"`으로 고정합니다 - 이미
   `backend/preprocessing/pipeline.py::process_kstartup_notice()`가 이렇게
   하고 있던 것과 동일 정책입니다.

## 전체 흐름

```
announcements_raw_kstartup (PostgreSQL SELECT)
        ↓
① 기본 전처리     clean_kstartup()
   모집중(rcrt_prgs_yn='Y')이고 마감일 안 지난 것만 유지, 텍스트 정규화,
   신청대상(aply_trgt+aply_trgt_ctnt) 병합, 업력/연령 조건 단일화
        ↓
   공통 필드 변환   transform_kstartup_to_common()
                  + parse_target_conditions() + normalize_support_fields()
        ↓
② 지역 매핑       map_regions()  ← normalize_kstartup_region() 그대로 호출
        ↓
③ 업종코드 매핑    map_ksic()    ← 호출 안 함, "업종무관(기본값)" 고정
        ↓
   최종 검증        validate_announcements()
        ↓
announcements (PostgreSQL UPSERT, raw_kstartup_id 기준)
```

## 원본 데이터 준비 - 먼저 해야 할 것

**K-Startup은 아직 라이브 크롤러가 없습니다.** 대신 2026-09-07에 확보한
K-Startup 전체 이력 원본(29,991건, K-Startup Open API 항목ID 그대로인
CSV)을 1회 적재하는 시더를 만들어뒀습니다:

```bash
cd C:/workspace/mulkko
python -m backend.crawler.kstartup_seed_loader --csv "<원본 CSV 경로>"
```

`pbanc_sn` 기준으로 이미 있는 건 건너뛰므로 재실행해도 중복이 안 쌓입니다.
**나중에 실제 K-Startup API 크롤러가 생기면 이 시더는 그 크롤러의
`save_to_db()`로 대체하면 됩니다.**

## 정제 로직 출처

"모집중만 유지 / 신청대상 텍스트 병합 / 업력·연령 단일화" 로직은 사용자가
별도로 검증해온 `15_clean_kstartup_raw_v2.py`를 그대로 포팅했습니다(다시
설계 안 함) - 마감된 공고(`rcrt_prgs_yn != 'Y'` 또는 마감일 경과)는
`clean_kstartup()` 단계에서 아예 걸러내고 `announcements`에 안 올라갑니다.

## 필드 매핑 기준

ERD(0904_DB업로드) + `final_project/transform_kstartup.py`의 기존 결정을
그대로 따랐습니다:

| 컬럼 | 값 출처 |
|---|---|
| `host_org_name` | `pbanc_ntrp_nm` (공고 게시기관명) |
| `supervising_org` | `sprv_inst` (주관기관) |
| `contact` | `biz_prch_dprt_nm` (담당부서명) |
| `category` | `supt_biz_clsfc` 원본값 그대로 |
| `target_summary` | `aply_trgt`/`aply_trgt_ctnt` 병합 결과 |
| `target_age_groups` | `biz_trgt_age` 단일화 문자열을 1개짜리 배열로 감쌈 |
| `business_age_condition` | `biz_enyy` + 신청대상 텍스트에서 추출한 값 단일화 |
| `apply_method` | 신청방법 6개 필드(이메일/팩스/방문/온라인/우편/기타)를 줄바꿈으로 결합 |

## 실행 방법

```bash
cd C:/workspace/mulkko
python -m backend.preprocessing.sync_kstartup_announcements
```

## TA가 알아야 할 미해결 사항

1. **`announcements_raw_kstartup` raw 데이터가 지금 DB에 없습니다** - 위
   시더부터 먼저 돌려야 합니다.
2. **`target_age_groups`는 ERD가 `TEXT[]` 배열인데, 정제 로직은 "전연령"
   같은 단일 문자열을 만듭니다** - 1개짜리 배열(`["전연령"]`)로 감싸서
   저장하도록 했습니다(사용자 확인, 2026-09-07). 여러 연령대를 동시에
   허용해야 하는 공고가 나오면 이 부분을 다시 봐야 합니다.
3. **`backend/db/schema.sql`에 `announcements_raw_kstartup`/`announcements`
   정의가 없는 건 기업마당과 같은 문제입니다** - 실행 전에 실제 DB에
   테이블이 있는지 먼저 확인하세요.
4. 크롤러가 없는 상태라 seed CSV의 실제 컬럼명이 DB 스키마와 정확히
   일치하는지 확인이 안 된 상태입니다(`kstartup_seed_loader.py`의
   `COLUMNS` 목록이 K-Startup Open API 항목ID와 같다고 가정하고 짰습니다) -
   실제 테이블 생성 시 컬럼명을 대조하세요.
