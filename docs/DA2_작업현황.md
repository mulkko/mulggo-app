# DA2 작업 현황 / 이어서 할 것 (2026-09-11 갱신)

> 이 문서는 원래 **2026-09-08 세션 기준**으로 작성됐고, **2026-09-11에 TA1_rh
> 세션에서 DB/코드 상태를 직접 대조해 갱신**했습니다(완료 항목 반영, 행 수
> 최신화). 정리되면 이 파일은 삭제해도 됩니다 (`git rm docs/DA2_작업현황.md`).
>
> **[2026-09-11 추가 갱신]** 사용자 요청으로 이 문서는 **사업자등록증 OCR
> 관련 내용만** 남기기로 함. 원래 있던 KSIC 업종코드 매칭 관련 내용은 OCR과
> 무관해서 삭제 대신 문서 하단에 주석(HTML 주석) 처리해뒀음 — 필요하면
> 주석만 풀면 원상복구 가능.

## 사업자등록증 OCR 현황 (2026-09-11 코드 대조)

### 사용 모델

- **기본정보** (상호/법인명/대표자/등록번호/법인등록번호/생년월일/개업연월일/
  사업장소재지): **Qwen2.5-VL-3B-Instruct** (`Qwen/Qwen2.5-VL-3B-Instruct`,
  VLM, GPU 권장) — `backend/assistant/biz_cert_ocr.py`
- **사업의 종류** (업태/종목 표): **EasyOCR**(`ko`,`en`) + 좌표 기반 규칙 —
  `backend/assistant/category_ocr.py`. Qwen VLM이 이 표에서 행을 빠뜨리거나
  라벨/값을 헷갈려서 별도 파이프라인으로 분리한 것 (파일 상단 주석 참고).
- **업로드 직후 품질 게이트**: EasyOCR로 빠르게 훑어 인식 가능한 사진인지만
  먼저 판정(문서 종류/사업자번호 패턴/신뢰도) — `backend/assistant/biz_cert_quality.py`.
  실패하면 무거운 Qwen 파이프라인을 돌리기 전에 재업로드 안내.

### 튜닝 이력 (biz_cert_ocr.py 코드 주석 기준)

- `torch_dtype`: float16 → **bfloat16**로 변경 (2026-09-06). VRAM 부족(8GB)으로
  일부 레이어가 CPU 오프로딩될 때 float16 혼합연산이 불안정해서 확률이 깨지는
  문제(`"!!!"` 반복 출력 등) 확인, bfloat16은 표현범위가 fp32와 같아 덜 취약.
- `do_sample=False`(greedy)로 고정 — VRAM 부족 상황에서 확률이 전부 0이 되며
  샘플링 단계 CUDA assert 발생 확인(2026-09-06). OCR은 정답이 정해진 작업이라
  샘플링 불필요, greedy가 크래시 회피 + 결과 일관성 둘 다 유리.
- `MAX_OCR_PIXELS = 1600*1600`: 이미지 리사이즈 실험. 직접 PIL로 리사이즈하면
  qwen_vl_utils의 patch/병합 단위와 안 맞아 CUDA assert 발생 → `max_pixels`만
  넘겨서 qwen_vl_utils가 자체 규칙으로 리사이즈하게 함. 1280×1280에서는 작은
  글씨(대표자 이름 등)가 뭉개지는 사례 있어 해상도를 올린 상태 — VRAM(8GB)
  한계로 더 크게는 못 올림.
- `load_image()`에 `autocontrast` 추가(2026-09-06) — 어두운 사진 OCR 실패 이슈 대응.
- 법인/개인 판별용 VLM 호출을 없애고 기본정보 전체를 1회 호출로 통합 —
  이미지 prefill 비용 때문에 지연시간이 컸던 걸 절반 가까이 줄임. 법인/개인은
  같은 응답의 등록번호(가운데 2자리 81~88)로 사후 계산.

### 연동 지점

- `POST /api/auth/biz-cert-ocr` (`backend/api/auth.py`) — **회원가입용**.
  업로드 → OCR → 사용자 확인/수정 화면에 결과만 반환, 이 시점엔 DB/디스크
  저장 안 함. `/signup` 제출 시 확정값+파일을 같이 보내야 그때 1회 저장
  (`save_biz_cert_data`, 재OCR 없음).
- `POST /api/mypage/biz-cert` (`backend/api/mypage.py`, 2026-09-10 추가) —
  **등록된 사업자등록증이 없는 기존 사용자**가 마이페이지에서 처음 첨부할 때.
  회원가입용과 동일 패턴(이미 OCR/확인된 값만 저장, 재OCR 없음).
- `POST /api/test/*` (`backend/api/test_ocr.py`) — **테스트 전용**. 정식
  회원가입 플로우와 무관, DB엔 저장 안 하고 결과를 CSV 한 줄로 남김. OCR
  파싱 자체가 잘 되는지 확인하는 용도.
- 프론트: `frontend/src/components/BizCertUpload/BizCertUpload.tsx` (회원가입에서 사용 중).

### 미착수 / TODO

- **온보딩(Onboarding.tsx) step3에 OCR 추가 예정** — 아직 미착수. 회원가입 때
  쓰는 `BizCertUpload.tsx` 재사용 우선 검토, 저장은 `mypage.py::POST /biz-cert`
  패턴 참고 예정 (자세한 배경은 memory `onboarding-bizcert-ocr-plan` 참고).
  정확히 step3을 교체할지 / step3 안에 추가할지 / 카드 선택 후 이어지는
  스텝으로 넣을지는 미정 — 작업 시작할 때 다시 확인 필요.
- 업태/종목(EasyOCR) 실패 시 기본정보(Qwen)는 그대로 보여주는 것까지는 처리됨
  (`auth.py::biz_cert_ocr_endpoint`, try/except로 분리) — 실패율 자체를
  낮추는 개선은 별도로 남아있음.

### 관련 파일

| | |
|---|---|
| 기본정보 OCR + HWPX 채우기 | `backend/assistant/biz_cert_ocr.py` |
| 업태/종목 OCR (EasyOCR) | `backend/assistant/category_ocr.py` |
| 업로드 품질 게이트 (EasyOCR) | `backend/assistant/biz_cert_quality.py` |
| 회원가입 OCR 엔드포인트 | `backend/api/auth.py` (`POST /api/auth/biz-cert-ocr`), `backend/auth/signup.py` |
| 마이페이지 사후 등록 엔드포인트 | `backend/api/mypage.py` (`POST /api/mypage/biz-cert`) |
| 테스트 전용 엔드포인트 | `backend/api/test_ocr.py` |
| 프론트 업로드 컴포넌트 | `frontend/src/components/BizCertUpload/BizCertUpload.tsx` |

<!--
[2026-09-11 주석 처리] 아래는 OCR/사업자등록증과 무관한 내용(KSIC 업종코드
매칭 작업 현황)이라 사용자 요청으로 주석 처리함 — 삭제는 아님, 필요하면
이 블록을 감싼 HTML 주석 기호만 지우면 그대로 복구됨.

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
-->
