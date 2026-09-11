# DA2 작업 현황 / 이어서 할 것 (2026-09-11 갱신)

> 이 문서는 원래 **2026-09-08 세션 기준**으로 작성됐고, **2026-09-11에 TA1_rh
> 세션에서 DB/코드 상태를 직접 대조해 갱신**했습니다(완료 항목 반영, 행 수
> 최신화). 정리되면 이 파일은 삭제해도 됩니다 (`git rm docs/DA2_작업현황.md`).

## 지금 DB 상태 (Supabase, 2026-09-11 확인)

| 테이블 | 행 수 | 비고 |
|---|---|---|
| `announcements_raw_bizinfo` | 1,704 | 크롤 완료 |
| `announcements_raw_kstartup` | 311 | 크롤 완료 |
| `announcements` (통합) | **1,994** (bizinfo 1,704 + kstartup 290) | 1번 버그 해결 후 재실행 완료 |
| `ksic_codes` | 1,202 | `load_ksic_codes.py`로 적재. `data/ksic_clean_v2.csv` 기준 |
| `nts_industry_codes` / `nts_ksic_mapping` | 1,611 / 1,772 | `load_nts_ksic_mapping.py`로 적재 완료 |

## 결정된 것

- **유저 쪽 업종 매칭 = path (a)**: 사업자등록증 업태/종목 **텍스트**를
  `decide_industry` → KSIC 코드로 뽑아서, 공고의 KSIC와 비교. 사업자등록증엔
  숫자 업종코드가 안 찍혀 나오므로 유저 쪽은 국세청 코드 불필요. 홈택스 연동
  안 함(사용자 확인).
- **K-Startup 공고는 업종 분류 안 함** — `ksic_status='업종무관(기본값)'` 고정
  (2026-09-04 팀 결정, 분류기가 K-Startup 텍스트에 헛다리 많음).

## ⚠️ 정정 (2026-09-08, 세션 후반) — ✅ 2026-09-11 해소됨

이전에 "path (a)면 `nts_*` 테이블 전부 불필요"라고 정리했는데 **틀렸음.**
그건 **유저 쪽만** 맞고, **공고 쪽**은 다름:

- **공고문에 국세청 업종코드를 직접 명시하는 경우가 있음** (예: 크리에이터미디어
  콤플렉스 입주공고 "국세청 업종코드 940306(1인 미디어 콘텐츠 창작자) 또는 921505").
- `final_project/ksic_core`의 **최신 분류기**는 이걸 `match_ksic_by_nts_code()` +
  `nts_to_ksic.csv`(국세청코드↔KSIC 크로스워크)로 처리함.
- → 이 필요 데이터는 이미 적재 완료: `nts_industry_codes` 1,611건 +
  `nts_ksic_mapping` 1,772건 (`load_nts_ksic_mapping.py`). 아래 8번도 참고.

## 이어서 할 것 (우선순위 순)

### ~~1. [버그] bizinfo 통합 반영 NUL(0x00) 크래시~~ ✅ 완료 (2026-09-11 확인)
- `sync_bizinfo_announcements.py` / `sync_kstartup_announcements.py` 둘 다
  `_strip_nul` 헬퍼로 저장 직전 NUL 제거 처리됨.

### ~~2. [성능] 첨부 추출 텍스트 캐싱~~ ✅ 완료 (2026-09-11 확인)
- `bizinfo_attachment_text_cache` 테이블에 캐시 있으면 재사용, 없으면 추출 후
  캐시에 저장하는 방식으로 구현됨 (`sync_bizinfo_announcements.py` 345번 줄대).

### ~~3. bizinfo 통합 반영 재실행~~ ✅ 완료 (2026-09-11 확인)
- `announcements` 테이블에 bizinfo 1,704건 + kstartup 290건, 총 1,994건 반영됨.

### ~~4. [정리] 분류기 → DB 전환~~ ✅ 완료 (2026-09-08 세션 내 완료로 확인)
- `explicit_match.py` / `llm_match.py` 둘 다 `ksic_codes` 테이블에서 읽도록
  바뀜(1202건 전수 대조로 CSV와 동일함 확인 후 전환). `data/ksic_clean_v2.csv`
  git 제외 여부는 미확인 — 남아있으면 마저 정리.

### 5. [기능] 매칭 본체 — 부분 진행 중
- 프론트: `MatchingList.tsx` / `MatchingDetail.tsx` **실제 API 연동 완료**
  (더미데이터 하드코딩 아님, 2026-09-10~11 TA1_rh 세션에서 처리).
- 매칭 API: 유저 KSIC ∩ `announcements.ksic_codes_matched` + 지역 필터까지는
  동작(`backend/api/matching.py`). **우대조건 정렬은 아직** —
  `backend/ml/ranker/`는 여전히 빈 폴더.
- 유저 쪽: `signup.py`가 업태/종목을 `profile_business_types`에 **여전히
  텍스트로만** 저장 — `decide_industry`에 태워서 `ksic_code` 채우는 작업은
  아직 미착수 (5자리 세세분류 정규화 필요한 것도 그대로 유효).

### 6. [장기] 스케줄러
- crawl (`POST /admin/crawl`) + sync (`POST /admin/sync`)를 Windows 작업 스케줄러
  또는 cron에 물려서 매일 자동. 코드가 이미 이걸 전제로 짜여 있음
  (`run(only_unprocessed=True)`, `kst_api.py` 경로 고정 주석)

### 7. [정리] "통합 반영 (임시)" 메뉴 정식화
- 지금은 별도 페이지 + 임시 사이드바 메뉴 (`AdminLayout.tsx`의 MENU_ITEMS 3번째,
  아이콘 없음). 나중에 "공고 수집 현황" 페이지에 "수집 → 가공" 두 단계로 통합

### ~~8. [큰 작업] 분류기 최신화~~ ✅ 국세청코드 매칭 도입 완료 (2026-09-11 확인)
`decide_industry()`가 이제 0단계로 `nts_code_match.py::match_ksic_by_nts_code()`를
먼저 시도(국세청 업종코드를 숫자로 직접 명시한 공고문 처리), 실패하면 기존
1단계(이름 매칭)·2단계(LLM)로 이어짐. `final_project/ksic_core`의
`rule_detectors.py`(721줄, 제외·제한 키워드/별표 인용 처리 등)를 그대로 이식한 건
아니고 `nts_code_match.py`라는 더 작은 파일로 국세청코드 매칭 부분만 구현한
차이는 있음 — 나머지(제외 키워드 등 세부 규칙)까지 필요하면 `ksic_core` 쪽과
다시 비교해볼 것.

## 관련 파일

| | |
|---|---|
| bizinfo 파이프라인 | `backend/preprocessing/sync_bizinfo_announcements.py` + `docs/bizinfo_announcements_pipeline.md` |
| kstartup 파이프라인 | `backend/preprocessing/sync_kstartup_announcements.py` + `docs/kstartup_announcements_pipeline.md` |
| KSIC 시드 로더 | `backend/preprocessing/load_ksic_codes.py` |
| 분류기 | `backend/ml/classifier/{decide_industry,explicit_match,llm_match,nts_code_match}.py` |
| nts_ksic_mapping 시드 로더 | `backend/db/load_nts_ksic_mapping.py` |
| 관리자 API | `backend/api/admin.py` (`/admin/crawl`, `/admin/sync`, `/admin/sync-status`, `/admin/export`, `*-count`) |
| 관리자 화면 | `frontend/src/pages/admin/{AdminHome,AnnouncementsSync}.tsx` |
