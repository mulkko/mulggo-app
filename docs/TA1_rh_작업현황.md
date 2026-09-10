# TA1_rh 작업 현황 / 이어서 할 것 (2026-09-10 기준)

> 이 문서는 **2026-09-10 세션** 작업을 중심으로 새로 정리했습니다. 이전 버전
> (2026-09-09 기준, 크롤링/공고 파이프라인 중심)의 내용은 이번 세션에서
> 직접 재검증하지 않았으므로 하단 "2026-09-09 이전 항목(재검증 안 함)"
> 섹션에 그대로 옮겨뒀습니다. 다른 계정/세션에서 이어받을 때는 이 문서 +
> `docs/물꼬_사업구체화_지표결합_설계안.docx`(팀 제공, 위치: `E:\3차프로젝트\`)
> 를 같이 참고하세요. 정리되면 삭제해도 됩니다.

## ✅ 오늘(2026-09-10) 완료한 것

### 1. 슬롯필링(사업구체화) 재설계 — 업종코드 매칭 입력값 버그 수정
- 근거 문서 확인: `E:\3차프로젝트\슬롯필링_기능_설계_260905.pdf`,
  `슬롯필링_260909.xlsx`, `물꼬_사업구체화_지표결합_설계안.docx`(팀 결정,
  최신). PDF 5장 기준 KSIC 매칭엔 **seed(슬롯0)+problem_to_solve(슬롯2)+
  solution_approach(슬롯5)** 세 원문이 필요한데, 기존 코드는 전혀 다른
  슬롯(target/differentiator/revenue_model/core_skill, 브레인스토밍용
  6~9번)을 넣고 있었음 — 이번에 수정.
- `backend/api/idea_card_test.py`: 옛 "업종만 매칭"(1문항) `/industry-match`
  삭제, `/api/test/slot-filling` 신규. seed_interest+problem_to_solve+
  solution_approach로 KSIC 매칭, has_store로 `report_type`(market/
  tech_startup) 분기, target~core_skill(선택)은 기존 `idea_card_generator.py`
  그대로 재사용.
- `frontend/dev/idea-flow-test.html`: 슬롯 0~9(출발점 분기 포함, 매장운영여부
  Y/N, 지역 3단 입력, 6~9번은 건너뛰기 가능) 단일 흐름으로 재작성.
- **⚠️ 발견한 미해결 구조적 문제**: `backend/ml/classifier/decide_industry()`
  (→ `llm_match.py`)는 **"공고문의 지원자격 조항에서 업종 판별"**용으로
  설계·튜닝된 분류기다. 게이트 프롬프트가 "이 공고가 지원대상 업종을
  판단할 근거가 있는지"를 묻는데, 사용자가 1인칭으로 쓴 사업 아이디어
  설명엔 애초에 그런 조항이 없어서 `_check_has_basis()`가 항상 `False`를
  반환 → 슬롯필링 텍스트로는 KSIC이 절대 안 잡힘(직접 실행해서 확인함).
  슬롯 구성을 바로잡아도 이 게이트 때문에 여전히 매칭 실패. **분류기를
  사용자 아이디어 텍스트용으로 새로 만들거나 게이트를 우회하는 별도
  경로가 필요함 — 다음 세션 최우선 후보.**
- `물꼬_사업구체화_지표결합_설계안.docx` 검토: "6문항 필수 → KSIC매칭/분기 →
  리포트+우수사례 → Q7~10 앵커링(직전 리포트 데이터로 질문 문구 동적 조립,
  LLM 불필요) → PSST/카드" 재배치안. 팀 방향은 확정됐으나 문서 자체에 미결
  항목 5개(문항 구조 "필수4+선택4" vs "구조화5문항" 확정, 우수사례 매칭
  시점, KSIC 매칭 정확도, PSST 2단계 분할, RAG 정의 갈등)가 담당자 지정
  상태로 남아있음 — **"우수사례" 기능 자체가 코드베이스에 아직 전혀 없음**
  (grep 0건). 아직 미착수.

### 2. 로그인 세션 배관 (토큰 발급) + 개발용 자동로그인
- 이전엔 로그인 성공해도 토큰/세션이 전혀 발급 안 됐음(`login()`이 dict만
  반환, 프론트도 저장 안 함 — `MyPage.tsx`/`ProfileEdit.tsx`가 `TEMP_USER_ID=27`
  하드코딩으로 때우던 상태). JWT 대신 opaque random token + DB 조회 방식으로
  새로 구현(새 의존성 없음, stdlib `secrets`만 사용):
  - `backend/db/schema.sql`: `auth_sessions` 테이블 추가(실제 DB에도 생성 완료)
  - `backend/auth/session.py`(신규): `create_session`, `get_user_id_by_token`,
    `get_current_user_id`(FastAPI `Depends`용, 아직 실제로 쓰는 엔드포인트는 없음 — 준비만 됨)
  - `backend/api/auth.py`: `/login`, `/admin-login` 응답에 `token` 추가.
    `_dev_auto_login()` 공통 헬퍼로 `/dev-auto-login`(일반),
    `/dev-auto-login-admin`(관리자, `is_admin` 서버검증 포함) 신규 —
    `.env`의 `DEV_AUTO_LOGIN_EMAIL/PASSWORD`,
    `DEV_ADMIN_AUTO_LOGIN_EMAIL/PASSWORD`가 없으면(대부분의 환경) 그냥 404로
    비활성 상태. 비밀번호는 서버 `.env`에만 있고 프론트/브라우저엔 절대 노출 안 됨.
  - 테스트 계정 실제 생성(`signup()` 정식 경로): `dev-auto@mulkko.test` /
    `DevAuto!2026`(user_id=28, 일반), `dev-admin@mulkko.test` /
    `DevAdmin!2026`(user_id=29, `is_admin=true`로 직접 UPDATE)
  - `frontend/src/auth/session.ts`(신규): `getAuthToken/getUserId/getUserEmail/
    setSession/clearSession/authHeaders/ensureDevAutoLogin`
  - `App.tsx`: 앱 시작 시 `ensureDevAutoLogin()` 1회 호출. 우하단에 작은
    점(초록=로그인됨/빨강=안됨) `DevAuthBadge` 추가 — 클릭하면 user_id/이메일
    펼쳐보임. **[임시/디버그] 확인 끝나면 지울 것으로 표시해둠.**
  - `LoginForm.tsx`: 로그인 성공 시 `setSession()` 호출, user variant는
    `/home`으로, admin variant는 `/admin`으로 이동(기존엔 이동 안 하고 문구만
    표시했음 — 같이 개선됨, 다른 세션이 건드렸을 수도 있어 확인 필요).
    폼 하단에 "[DEV] 테스트 계정으로 바로 로그인" 임시 버튼 추가(user/admin
    화면 각각).
  - `MyPage.tsx`/`ProfileEdit.tsx`: `TEMP_USER_ID` → `FALLBACK_USER_ID`로
    이름 변경, `getUserId() ?? FALLBACK_USER_ID`로 실제 세션 우선 사용.
  - `MyPage.tsx`: 하단에 "로그아웃" 텍스트 링크 추가, `clearSession()` +
    `/login` 이동으로 실제 동작.
  - `.env.example`에 위 4개 DEV_* 변수 추가.
  - **⚠️ 진짜 로그인 세션 UX(비밀번호 찾기, 회원가입 후 리다이렉트 등)는
    미완성** — 지금은 "토큰 배관"만 놓은 상태.

### 3. 마이페이지 — 사업자등록증 미등록 시 업로드 컴포넌트
- `backend/api/mypage.py`: `GET /profile`에 `has_biz_cert`(EXISTS 서브쿼리)
  추가. `POST /biz-cert` 신규(파일+OCR확인값 저장, `signup.py::
  save_biz_cert_data()` 그대로 재사용 — 재OCR 안 함).
- `ProfileEdit.tsx`: `has_biz_cert===false`면 기존 정적 버튼 대신 회원가입
  때 쓰던 `BizCertUpload` 컴포넌트 렌더링, 확인 완료 시 저장 후 정적
  표시로 전환. user_id=28(미등록)/27(등록됨) 둘 다 실서버로 검증 완료,
  테스트로 만든 더미 데이터는 정리해서 원복함.

### 4. 홈 화면(`Home.tsx`)
- 로그인 상태면 "회원가입하기"/로그인 유도 문구 숨김, 대신 "아이디어
  구체화하기"(TODO — 정식 화면 없어서 아직 미연결)/"매칭공고 보기"(→
  `/matching`, 실제 이동) 임시 버튼 노출.
- 로그인 상태에서만 하단 `BottomNav`(홈 탭 활성) 표시.
- 햄버거 메뉴 드로어(홈/아이디어/매칭/마이페이지/로그아웃) 내용은 다 만들어서
  검토까지 마쳤으나, **쓸지 말지 결정 안 돼서 주석 처리해둠** — 파일 내
  `[START: 보류] 햄버거 메뉴 드로어` / `[END: 보류] ...` 마커 3곳(import,
  state/핸들러, JSX)을 검색하면 한 번에 찾을 수 있음. 켜려면: (1) 세 블록
  주석 해제 (2) 헤더 메뉴 버튼에 `onClick={() => setMenuOpen(true)}` 연결.
  `home.module.css`에 `.menuOverlay/.menuDrawer/.menuCloseBtn/.menuItem`
  스타일은 이미(주석 아님) 넣어놨음.

### 5. `dev_links.html` / `dev_links_share.html` (항상 같이 수정)
- `idea-flow-test.html` 링크 설명/날짜 갱신.
- "구현율" 칸(수동 입력, 자동계산 아님) 채움: 홈 90%, 로그인 90%, 회원가입
  85%, 마이페이지 55%(6섹션 중 프로필요약+사업자등록증만 실데이터, 나머지
  4개 더미), 마이페이지-정보수정 70%, 매칭결과 85%, 매칭결과-필터 90%,
  매칭결과-상세보기 85%, 서류미리보기 80%. 근거: TODO/더미데이터 grep +
  실제 fetch 호출 여부 직접 확인.
- 관리자 로그인 행에 이미 90%가 채워져 있었음 — 아래 "다른 세션과의 관계"
  참고, 다른 세션이 넣은 것으로 추정.

## ⚠️ 환경/문서 불일치 발견 (수정 안 하고 사용자 확인만 받음)

- `CLAUDE.md`엔 "로컬 개발 환경: SQLite 사용"이라고 되어있지만, 실제
  `backend/db/connection.py`는 SQLite 분기가 아예 없고 psycopg2로 곧바로
  Postgres에 붙는 코드만 있음. `.env`를 열어보면 현재 `DB_HOST`는
  Supabase(`aws-0-ap-northeast-2.pooler.supabase.com`)이고, Neon 설정은
  주석처리돼 있음(`connection.py` 상단 주석엔 "Supabase에서 Neon으로
  이관"이라고 적혀 있어 실제 상태와 다름). CLAUDE.md는 사용자 확인 전까지
  임의로 안 고쳤음.
- 작업 중 `.env`의 `DEV_AUTO_LOGIN_PASSWORD` 값 뒤에 다음 줄 키가 개행 없이
  붙어버린 걸 발견해서 정리함(제 실수로 추정, printf에 개행 빠뜨림). `.env`는
  커밋 안 되는 파일이라 다른 팀원 영향 없음.

## 🤝 다른 세션과의 관계 (2026-09-10)

같은 PC에서 "mulkko-7d"라는 다른 Claude 세션이 `AdminRoute.tsx`의 인증
가드(현재 TODO로 꺼져있음)를 켜는 작업을 하려고 교차 세션 메시지로 문의해옴.
`AdminRoute.tsx` 자체는 안 건드렸다고 답했고, 대신 인접 파일(`LoginForm.tsx`,
`backend/api/auth.py`, `schema.sql`)을 오늘 건드렸다고 알려줬음 — 이어받을
때 `LoginForm.tsx`가 이 문서 작성 시점 이후 또 바뀌어 있을 가능성 있음
(실제로 세션 중 로그인 후 `/home`/`/admin` 이동 로직이 제가 모르는 새
추가돼있는 걸 발견한 적 있음 — 확인 후 진행할 것).

## ❌ 다음 세션 우선순위 제안

1. **KSIC 분류기가 사용자 아이디어 텍스트를 못 읽는 문제 (최우선)** — 위
   "1. 슬롯필링 재설계" 참고. 슬롯 구성은 다 고쳤는데 `decide_industry()`
   자체가 공고문 전용이라 실제 매칭이 안 됨. 게이트 프롬프트 우회 또는
   전용 분류 경로 신설 필요.
2. **햄버거 메뉴 드로어 사용 여부 결정** — 결정만 나면 주석 4곳 풀기만
   하면 됨(위 "4. 홈 화면" 참고).
3. **`물꼬_사업구체화_지표결합_설계안.docx`의 미결 항목 5개** — 팀 확인 필요
   (문항 구조, 우수사례 매칭 시점/데이터 자체, KSIC 정확도, PSST 분할, RAG 정의).
4. **로그인 UX 마무리** — 비밀번호 찾기(`href="#"` 죽은 링크), 회원가입 직후
   자동 로그인 여부, 관리자 배지 정합성 등.
5. **마이페이지 4개 섹션(리포트/관심공고/이용내역/지원내역) 실데이터 연동**
   — 현재 프로필요약+사업자등록증만 실데이터(구현율 55%로 반영함).

## 관련 파일 (2026-09-10 작업분)

| | |
|---|---|
| 슬롯필링/업종매칭 | `backend/api/idea_card_test.py`, `frontend/dev/idea-flow-test.html`, `backend/ml/classifier/{decide_industry,llm_match}.py` |
| 로그인 세션 | `backend/auth/session.py`, `backend/api/auth.py`, `backend/db/schema.sql`(auth_sessions), `frontend/src/auth/session.ts`, `frontend/src/components/LoginForm.tsx`, `frontend/src/App.tsx` |
| 마이페이지 사업자등록증 | `backend/api/mypage.py`, `frontend/src/pages/mypage/ProfileEdit.tsx`, `frontend/src/components/BizCertUpload/BizCertUpload.tsx` |
| 홈 화면 | `frontend/src/pages/home/Home.tsx`, `frontend/src/styles/home.module.css` |
| 진행 현황 문서 | `frontend/dev/dev_links.html`, `dev_links_share.html` |
| 설계 근거 문서 (팀 제공, 리포지토리 밖) | `E:\3차프로젝트\슬롯필링_기능_설계_260905.pdf`, `슬롯필링_260909.xlsx`, `물꼬_사업구체화_지표결합_설계안.docx` |

---

## 2026-09-09 이전 항목 (재검증 안 함 — 이전 버전 그대로 보존)

### ✅ 완료된 것
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
- **[2026-09-09 후반] 사업 구체화 → 업종코드 매핑 파이프라인 (테스트 레벨)** —
  기획 방향이 "빠른진단(4문항)+정밀진단(14문항) 2트랙"에서 "업종매칭+아이디어
  구체화"로 바뀌었음(정밀진단 트랙은 없어짐, 사용자 확인). `backend/chatbot/
  idea_card_generator.py`(슬롯 4개→아이디어 카드) + `decide_industry()` 재사용
  (카드 내용→KSIC 코드) + `/analysis/tech-startup` 연결까지 테스트 페이지
  (`frontend/dev/idea-card-test.html`, `idea-chat-test.html`)로 동작 확인 완료.
  낡은 계획의 흔적이던 `backend/chatbot/chain.py`(TODO 스텁)는 삭제함.

### ⚠️ 부분적으로만 해결된 것
- **첨부파일 원문 추출 캐싱 — 실제 캐시는 아직 없음.** `map_ksic()`은 여전히
  매번 `get_notice_full_text()`로 재다운로드+재OCR한다. NUL버그 수정(행별
  commit + `only_unprocessed` 필터) 덕분에 이미 성공한 행은 재실행해도
  자동으로 건너뛰어져서 증상은 많이 완화됨. 실패해서 재시도되는 행은 여전히
  재추출됨.

### ❌ 아직 안 된 것 (우선순위 순, 09-09 시점)
1. **매칭 본체** — `backend/ml/ranker/`가 `__init__.py`만 있는 빈 폴더였음.
   (오늘 프론트 쪽 `/matching` 관련 화면들이 실제 fetch로 연동된 건 확인했으나,
   랭킹 로직 자체가 완성됐는지는 이번 세션에서 재확인 안 함 — 위 "관련 파일"
   업데이트 필요할 수 있음)
2. **사업 구체화 정식 화면 + API** — 오늘 슬롯필링 쪽 백엔드/테스트 페이지는
   진전 있었으나 정식 화면·API는 여전히 미착수 (위 "오늘 완료한 것" 참고)
3. **AI 신청서 PSST 초안 생성** (`backend/assistant/psst_generator.py`) — TODO뿐
4. **RAG/벡터DB(Chroma) 연동** (`backend/rag/`) — 내용 없음
5. **분류기 최신화** (구버전 → `final_project/ksic_core`) — `rule_detectors.py` 없음
6. **"통합 반영 (임시)" 메뉴 정식화** — 이름에 "(임시)" 남음
7. **스케줄러 (자동 매일 크롤링)** — 미등록

### 🔍 확인 필요 (09-09 시점)
- bizinfo 통합 반영이 실제로 `announcements` 테이블에 얼마나 들어갔는지
- `explicit_match.py`/`llm_match.py`가 `ksic_codes` DB 테이블 읽기로 전환됐는지

### 관련 파일 (09-09 시점)
| | |
|---|---|
| 통합 반영 파이프라인 | `backend/preprocessing/sync_{bizinfo,kstartup}_announcements.py` |
| 관리자 API | `backend/api/admin.py` (`/admin/sync?source=...&limit=...`) |
| 관리자 화면 | `frontend/src/pages/admin/AnnouncementsSync.tsx` |
| 매칭(미착수 당시) | `backend/ml/ranker/` |
| 신청서 어시스턴트 | `backend/assistant/{psst_generator.py(미착수), biz_cert_ocr.py, hwpx_fill.py, category_ocr.py}` |
| RAG(미착수) | `backend/rag/` |
