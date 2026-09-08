# DA2 작업 현황 / 이어서 할 것 (2026-09-08 기준)

> 이 문서는 **2026-09-08 세션 기준**의 열린 작업 목록입니다. 다른 자리에서
> 진행한 분류기(`explicit_match` 등) 작업은 여기 반영 안 돼 있을 수 있음.
> 정리되면 이 파일은 삭제해도 됩니다 (`git rm docs/DA2_작업현황.md`).

## 지금 DB 상태 (Supabase)

| 테이블 | 행 수 | 비고 |
|---|---|---|
| `announcements_raw_bizinfo` | 1,559 | 크롤 완료 |
| `announcements_raw_kstartup` | 242 | 크롤 완료 |
| `announcements` (통합) | **221 (kstartup만)** | bizinfo는 아래 1번 버그로 0행 |
| `ksic_codes` | 1,202 | `load_ksic_codes.py`로 적재. `data/ksic_clean_v2.csv` 기준 |
| `nts_industry_codes` / `nts_ksic_mapping` | 0 | **적재 안 함** (아래 "결정된 것" 참고) |

## 결정된 것

- **업종 매칭 = path (a)**: 유저(사업자등록증 업태/종목 텍스트)도 공고도 둘 다
  `decide_industry` → KSIC 코드로 뽑아서 KSIC끼리 비교. **국세청(NTS) 업종코드는
  안 씀** (홈택스 연동 안 함 — 사용자 확인). 그래서 `nts_industry_codes` /
  `nts_ksic_mapping` 테이블은 적재 안 함. 국세청↔KSIC 연계표
  (`final_project/data/raw/업종코드-표준산업분류_연계표.csv`) 정규화 작업은 보류.
- **K-Startup 공고는 업종 분류 안 함** — `ksic_status='업종무관(기본값)'` 고정
  (2026-09-04 팀 결정, 분류기가 K-Startup 텍스트에 헛다리 많음).

## 이어서 할 것 (우선순위 순)

### 1. [버그] bizinfo 통합 반영 NUL(0x00) 크래시  ⬅ 이것부터
- 파일: `backend/preprocessing/sync_bizinfo_announcements.py::upsert_announcements`
  (같은 파일 9번 섹션에 상세 주석 + 수정 코드 예시 있음)
- 증상: 1,559건 전부 처리(검증 통과) 후 마지막 UPSERT에서
  `ValueError: A string literal cannot contain NUL (0x00) characters.` → 전량 롤백
- 수정: 저장 직전 `str` / `list[str]` 값에서 `"\x00"` 제거 (`_strip_nul` 헬퍼)
- `sync_kstartup_announcements.py`도 같은 패턴 → 같이 고칠 것

### 2. [성능] 첨부 추출 텍스트 캐싱
- `map_ksic()`이 `get_notice_full_text()`를 캐시 없이 매번 호출 → 재실행 시
  1,559건 첨부 재다운로드 + 재OCR (수 시간)
- 1번 버그로 재실행이 불가피해서 이게 크게 문제 됨
- 방향: 이미 뽑은 원문을 어딘가(파일 / 별도 테이블 / `announcements.content`)에
  저장해두고 재사용. 1번 고치기 전/후 어느 쪽이든 이거 먼저 넣는 게 나을 수도.

### 3. bizinfo 통합 반영 재실행
- 1번(+2번) 끝난 뒤 `POST /admin/sync?source=bizinfo` (관리자 "통합 반영(임시)" 메뉴)
  또는 `python -m backend.preprocessing.sync_bizinfo_announcements`
- 로그: `logs/sync_bizinfo.log` (gitignore). 관리자 화면에서 폴링해서 볼 수 있음

### 4. [정리] 분류기 → DB 전환 + `data/ksic_clean_v2.csv` git 제외
- `explicit_match.py` / `llm_match.py`가 `data/ksic_clean_v2.csv` 파일을 하드코딩
  경로로 읽음 → `ksic_codes` 테이블 읽도록 변경
- 컬럼 매핑: `KSIC_코드→code`, `KSIC_세세분류명→name`, 대/중/소/세 코드+명 →
  `large/medium/small/detail_code|name`. `embedding_text`는 두 분류기 다 미사용
- 그 후: `.gitignore`에서 `!data/ksic_clean_v2.csv` 삭제, `.gitattributes` 정리,
  `git rm --cached data/ksic_clean_v2.csv`. `load_ksic_codes.py`는 시드 전용으로 유지
- ※ `llm_match.py`는 PR #29(`623ebcf`)에서 수정됐으니 그 위에서

### 5. [기능] 매칭 본체 (아직 시작 전)
- 유저 쪽: `signup.py`가 업태/종목을 `profile_business_types`에 **텍스트로만** 저장.
  → `decide_industry`에 태워서 KSIC 코드도 저장 (`profile_business_types.ksic_code`,
  FK라 5자리 세세분류로 정규화 필요 — 분류기는 상위레벨 코드도 뱉음)
- 매칭 API: 유저 KSIC ∩ `announcements.ksic_codes_matched` + 지역 필터 + 우대조건 정렬
  (`backend/ml/ranker/`는 빈 폴더)
- 프론트: `MatchingList.tsx` / `MatchingDetail.tsx`가 `DUMMY_ANNOUNCEMENTS` /
  `matchingDetailData.ts` 하드코딩 → 실제 API 연동

### 6. [장기] 스케줄러
- crawl (`POST /admin/crawl`) + sync (`POST /admin/sync`)를 Windows 작업 스케줄러
  또는 cron에 물려서 매일 자동. 코드가 이미 이걸 전제로 짜여 있음
  (`run(only_unprocessed=True)`, `kst_api.py` 경로 고정 주석)

### 7. [정리] "통합 반영 (임시)" 메뉴 정식화
- 지금은 별도 페이지 + 임시 사이드바 메뉴 (`AdminLayout.tsx`의 MENU_ITEMS 3번째,
  아이콘 없음). 나중에 "공고 수집 현황" 페이지에 "수집 → 가공" 두 단계로 통합

## 관련 파일

| | |
|---|---|
| bizinfo 파이프라인 | `backend/preprocessing/sync_bizinfo_announcements.py` + `docs/bizinfo_announcements_pipeline.md` |
| kstartup 파이프라인 | `backend/preprocessing/sync_kstartup_announcements.py` + `docs/kstartup_announcements_pipeline.md` |
| KSIC 시드 로더 | `backend/preprocessing/load_ksic_codes.py` |
| 분류기 | `backend/ml/classifier/{decide_industry,explicit_match,llm_match}.py` |
| 관리자 API | `backend/api/admin.py` (`/admin/crawl`, `/admin/sync`, `/admin/sync-status`, `/admin/export`, `*-count`) |
| 관리자 화면 | `frontend/src/pages/admin/{AdminHome,AnnouncementsSync}.tsx` |
