# TA1_rh 작업 현황 / 이어서 할 것 (2026-09-09 기준, 백엔드 중심)

> 이 문서는 **2026-09-09 세션 기준**으로 코드를 직접 대조해서 정리한 백엔드
> 작업 현황입니다. `docs/DA2_작업현황.md`(2026-09-08)와 겹치는 항목은 그 사이
> 무엇이 실제로 끝났는지 다시 확인해서 반영했습니다. 정리되면 삭제해도 됩니다.

## ✅ 완료된 것

- **bizinfo/kstartup 통합 반영 NUL(0x00) 크래시 버그 수정** — 저장 직전
  `_strip_nul()`로 제거. 배치 전체 commit → 행별 commit으로 바꿔서 1건 실패가
  나머지를 롤백시키지 않음 (`sync_bizinfo_announcements.py` / `sync_kstartup_announcements.py`)
- **K-Startup 통합 반영 빈 배치 버그 수정** — raw가 전부 마감 공고라 필터 후
  0건이면 `KeyError`로 죽던 문제, `clean_df.empty` 조기 종료로 수정
- **관리자 "통합 반영" 실행에 건수 제한(`limit`) 옵션 추가** — 1,500여 건 전체를
  매번 처리하던 것을, 관리자 화면에서 건수 입력 시 그만큼만(테스트/분할 실행용)
  처리하도록 함. `only_unprocessed=True`라 이미 반영된 건 자동 스킵 → 같은
  값으로 반복 실행하면 다음 구간이 이어서 처리됨
- **상권분석용 대용량 데이터 전용 DB 분리** — `commercial_districts`(270만 건,
  ~741MB)가 메인 DB 무료 플랜 용량(500MB)을 초과시키던 문제. 별도 Supabase
  프로젝트로 분리(`connection.py::get_analysis_connection()`, `.env.example`의
  `ANALYSIS_DB_*`)
- **`start_all.bat` 경로 버그 수정** — 따옴표 이스케이프 문제로 백엔드 창이
  조용히 안 뜨던 것, `start`의 `/D` 옵션으로 수정
- **`requirements.txt` 머지 충돌 마커 정리** (main) — 한때 `<<<<<<< HEAD` 등
  충돌 마커가 그대로 커밋돼 `pip install` 자체가 깨졌던 것, 이후 정리 확인됨

## ⚠️ 부분적으로만 해결된 것

- **첨부파일 원문 추출 캐싱 — 실제 캐시는 아직 없음.** `map_ksic()`은 여전히
  매번 `get_notice_full_text()`로 재다운로드+재OCR한다(코드 주석에도 "이번
  범위에선 매번 호출하는 가장 단순한 형태로 둔다"고 그대로 남아있음). 다만
  위 NUL버그 수정(행별 commit + `only_unprocessed` 필터) 덕분에, **이미 성공한
  행은 스크립트를 통째로 재실행해도 자동으로 건너뛰어져서** "재실행마다
  1,559건 처음부터 다시" 하던 증상은 실질적으로 많이 완화됐다. 단, 실패해서
  재시도되는 행은 여전히 재추출된다. 최근 추가된 `[i/total] ... 본문 추출
  성공/실패` 로그는 진행상황 확인용일 뿐, 캐싱 로직이 아니다.

## ❌ 아직 안 된 것 (우선순위 순)

1. **매칭 본체 (사실상 시작 전)** — `backend/ml/ranker/`가 `__init__.py`만
   있는 빈 폴더. 유저 KSIC ∩ 공고 `ksic_codes_matched` + 지역 필터 + 우대조건
   정렬 로직 자체가 없음. 유저 쪽도 업태/종목을 텍스트로만 저장하고
   `decide_industry`로 KSIC 코드화해서 저장하는 단계가 안 됨
   (`profile_business_types.ksic_code` 등). 프론트도 더미 데이터로 되어있음
2. **사업 구체화 챗봇** (`backend/chatbot/chain.py`) — TODO 주석 한 줄뿐,
   고객·문제해결·수익모델·차별점·지역규모 5가지 질문 흐름 미구현
3. **AI 신청서 PSST 초안 생성** (`backend/assistant/psst_generator.py`) —
   TODO 주석뿐. (참고: 같은 폴더의 사업자등록증 OCR → HWPX 자동입력 파이프라인
   `biz_cert_ocr.py`/`hwpx_fill.py` 등은 별개로 상당히 진행돼 있음 — PSST
   "본문 작성" 파트만 미착수)
4. **RAG/벡터DB(Chroma) 연동** (`backend/rag/`) — `__init__.py`만 있고 내용 없음
5. **분류기 최신화** (구버전 → `final_project/ksic_core`) — 국세청 코드 직접
   명시 탐지용 `rule_detectors.py`가 없음. `nts_to_ksic` 크로스워크 데이터도 미도입
6. **"통합 반영 (임시)" 메뉴 정식화** — 관리자 화면 이름에 아직 "(임시)" 남음
7. **스케줄러 (자동 매일 크롤링)** — `POST /admin/crawl` + `/admin/sync`를 cron/
   작업 스케줄러에 물리는 부분. 코드는 `only_unprocessed=True` 전제로 이미
   짜여 있어서 준비는 돼 있지만 실제로 스케줄 등록된 곳은 없음

## 🔍 확인 필요 (DB 직접 조회가 있어야 확인 가능, 코드만으론 판단 불가)

- bizinfo 통합 반영이 실제로 `announcements` 테이블에 얼마나 들어갔는지
  (행 수) — `GET /admin/bizinfo-count` 등으로 확인 가능
- `explicit_match.py` / `llm_match.py`가 `data/ksic_clean_v2.csv` 직접 읽기에서
  `ksic_codes` DB 테이블 읽기로 전환됐는지

## 관련 파일

| | |
|---|---|
| 통합 반영 파이프라인 | `backend/preprocessing/sync_{bizinfo,kstartup}_announcements.py` |
| 관리자 API | `backend/api/admin.py` (`/admin/sync?source=...&limit=...`) |
| 관리자 화면 | `frontend/src/pages/admin/AnnouncementsSync.tsx` |
| 매칭(미착수) | `backend/ml/ranker/` |
| 챗봇(미착수) | `backend/chatbot/chain.py` |
| 신청서 어시스턴트 | `backend/assistant/{psst_generator.py(미착수), biz_cert_ocr.py, hwpx_fill.py, category_ocr.py}` |
| RAG(미착수) | `backend/rag/` |
