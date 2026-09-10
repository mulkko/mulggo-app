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
- **[세션 후반 갱신]** 아래 6~12 작업 반영해서 구현율 재조정: 마이페이지
  55%→75%(찜하기·채우기이용내역 연동), 마이페이지-정보수정 70%→85%
  (BizCertUpload 개편 반영), 매칭결과·매칭결과-필터 90%→100%(4개 필터군
  전부 연동+지역/업종/정렬 URL 이동), 서류미리보기 80%→85%(저장 확인
  모달), 회원가입_완료(Onboarding) 신규 75%→85%. "백엔드 연동일"의 의미를
  "마지막 수정일"에서 "최초 연동일"로 재정의하고 전체 행 재검증(그 사이
  라벨만 바꾼 필드는 연동일 그대로, 진짜 처음 연동된 것만 갱신). "고객센터
  (챗봇)"(`/support`, 50%) 행 신규 추가, "[테스트] 사업자등록증 OCR" 링크가
  누락돼있던 것 발견해서 추가. "진단방식선택/구체화 진단1~4" 5행은 팀에서
  직접 추가함(작성일 09-03 소급, 수정일 09-10).

### 6. 매칭 필터 완전 연동 + 리스트 UX 개선
- `backend/api/matching.py`: `field`(지원분야, `category ILIKE ANY(...)`),
  `age`(연령, `target_age_groups && ...`) 파라미터 신규 추가 — 이걸로
  기업유형/지원분야/업력/연령 4개 필터 그룹 전부 백엔드 연동 완료(이전엔
  기업유형/업력 2개만 연동, 지원분야/연령은 카테고리 미확정으로 보류 상태였음).
  마감 정렬 동점 문제 해결용 `announcement_id` 보조 정렬 추가, 상세/리스트에
  `fillable`(채우기 가능 여부) 조인 추가.
- `FilterPage.tsx`: 연령 옵션을 실제 원본 10개 값으로 교체(가공 버킷 없음),
  필터 팝업 재진입 시 현재 적용된 값 복원(`parseInitialState`), 뒤로가기/
  적용 둘 다 기존 쿼리 유지한 채 이동. "예비창업자" 라벨은 "예비창업자
  포함"으로 바꿨다가 다시 "예비창업자"로 원복(2축 분리 UI 시안은 만들었다가
  최종적으로 기각 — LIKE 매칭이 이미 "예비창업자~N년미만" 같은 복합값을
  부분일치로 잘 잡아줘서 굳이 안 나눠도 됨).
- `MatchingList.tsx`: 지역/업종/정렬을 로컬 state에서 URL 쿼리로 이동(필터
  팝업 갔다 오면 초기화되던 버그 수정), 네이티브 `<select>` 3개를 칩 버튼+
  하단 시트 팝업으로 교체(좁은 화면에서 select 3개+필터버튼이 한 줄에 안
  들어가던 문제), "더보기" 로드 개수를 세션에 저장해서 상세 갔다와도 유지.
- `MatchingDetail.tsx`: 뒤로가기를 `navigate(-1)` 대신
  `location.state.fromSearch` 기반으로 변경(직접 링크 진입 시 history가
  없어서 뒤로가기 안 먹던 문제 수정) — 카드 클릭 시 `MatchingList.tsx`가
  현재 쿼리를 state로 같이 넘겨줌.

### 7. 찜하기(bookmarks) + 채우기 이용내역(fill-history) 연동
- `backend/api/mypage.py`: `GET /bookmarks`(로그인 세션 기준,
  `Depends(get_current_user_id)`), `GET /fill-history` 신규.
- `backend/api/matching.py`: 찜하기 토글 `POST`/`DELETE /attachments`
  아님 — `/api/matching/:id/bookmark` 신규(세션 기준).
- `MyPage.tsx`: "관심있는 지원사업"/"채우기 이용내역" 2개 섹션 실데이터로
  교체(기존엔 더미). 채우기 이용내역은 재다운로드도 됨(기존
  `downloadFilledDocument` 재사용).

### 8. 서류 미리보기 — 다운로드 전 저장 확인 모달
- 기존엔 "나의 정보로 채우기" 누르면 확인 없이 바로 브라우저 다운로드가
  됐음(사용자 확인: 의도한 흐름이 아니었음 — "서류가 준비됐어요" 모달에서
  "로컬저장"을 눌러야 저장되는 게 원래 의도).
- `frontend/src/utils/downloadFilledDoc.ts`: `fetchFilledDocument`(blob만
  받아옴)/`saveFilledBlob`(실제 저장)로 분리. `DocPreview.tsx`는 이 둘을
  나눠 써서 모달 확인 후에만 저장. `MyPage.tsx`(채우기 이용내역 재다운로드)는
  기존 `downloadFilledDocument`(즉시 저장) 그대로 유지 — 이미 한 번 저장했던
  걸 다시 받는 거라 확인 단계 불필요.
- `backend/api/matching.py`: hwpx 응답에 `media_type="application/
  haansofthwpx"` 명시 — 브라우저 "흔치 않은 파일" 다운로드 경고 완화 시도
  (매번 새로 생성되는 고유 파일이라 완전히는 안 없어질 수 있음, 근본 원인은
  파일 자체가 사용자마다 새로 만들어져서 크롬 세이프브라우징 평판이 없다는 것).

### 9. 관리자 인증 가드(`AdminRoute.tsx`) 활성화
- 위 "다른 세션과의 관계"에서 문의받았던 그 가드 — 다른 세션(mulkko-7d) 또는
  사용자가 직접 켠 것으로 확인(`if (!isAuthed) return <Navigate to="/admin/
  login" />` 주석 해제됨). 비로그인 상태로 `/admin/*` 접근 시 실제로
  `/admin/login`으로 리다이렉트되는 것까지 확인함.

### 10. 고객센터 챗봇 화면 신규 연결
- `backend/api/support.py`(`POST /api/support/chat`)는 이미 완성돼 있었는데
  (`backend/customer_chatbot/` 로직을 감싸기만 함) 붙는 프론트 화면이 없었음.
- `frontend/src/pages/support/CustomerSupport.tsx`(신규) + `customerSupport
  .module.css`: 디자인 시안 없이 채팅 버블+입력창만 있는 최소 형태로 구현.
  `App.tsx`에 `/support` 라우트 추가, `MyPage.tsx` 헤더 고객센터 아이콘에서
  진입하도록 연결(기존엔 TODO 스텁).
- `.env`에 `OPENAI_API_KEY` 있으면 실제 LLM 응답까지 확인됨(`needs_human_
  support`가 true면 안내 문구만 보여줌 — 문의 폼 자체는 아직 없음, TODO).

### 11. 사업자등록증 업로드 UX 전면 개편 (`BizCertUpload.tsx`)
- 원래 있던 필드별 "값 텍스트 + 수정 버튼" 패턴을 **값 영역 자체를 누르면
  바로 입력창으로 전환**되는 방식으로 통일(별도 버튼 제거, 사용자 확인 —
  "input 누르면 수정되게" 요청). 안 쓰게 된 `.viewRow`/`.editBtn` CSS 삭제.
- 법인/개인 필드: 네이티브 `<select>` → 값 버튼을 누르면 뜨는 작은 선택
  팝업(법인/개인 2개)으로 교체. 오른쪽 화살표 아이콘 여백 20px 확보.
- `notApplicable`(예: 개인일 때 법인등록번호) 필드는 기존엔 "-" 회색
  텍스트로 보여줬는데, **아예 렌더링 안 하도록 변경**(행 자체가 안 보임).
- 값 버튼들 기본 배경은 흰색, `:active`(누르는 순간)만 회색(`--color-
  stone-mist`)으로 바뀌게 해서 탭 피드백을 줌(법인/개인 버튼도 동일 적용).
- `backend/assistant/biz_cert_ocr.py`: OCR이 법인/개인 판별 후 반대쪽
  필드(법인이면 상호/생년월일, 개인이면 법인명/법인등록번호)를 서버에서
  지워버리던 로직 제거 — 프론트가 `notApplicable`로 화면에서만 숨기므로,
  나중에 사용자가 법인/개인을 바꿔도 원래 OCR 값이 남아있어서 복구 가능.
- 이 컴포넌트는 `Onboarding.tsx`(step3 "바로 매칭받기")와
  `ProfileEdit.tsx`(사업자등록증 미등록 상태) 둘 다에서 쓰여서, 개선 효과가
  두 화면에 동시에 적용됨.

### 12. 사업구체화 진단(슬롯필링) 정식 화면 5개 신규
- `frontend/src/pages/diagnosis/`: `DiagnosisSelect`, `DiagnosisStep1~4`.
  `frontend/dev/idea-flow-test.html`에서 이미 검증된 질문 흐름을 정식
  화면으로 옮김. 제출은 `backend/api/idea_card_test.py`의 `POST /api/test/
  slot-filling`(DB 저장 없는 테스트 전용 엔드포인트) 그대로 재사용 — 정식
  API로 교체는 아직 안 함.
- `Home.tsx` "아이디어 구체화하기", `Onboarding.tsx` "아이디어 카드로
  시작하기" 카드 둘 다 `/diagnosis/select`로 연결(기존엔 둘 다 빈 TODO 스텁).
- **업종코드(KSIC) 매칭 결과는 화면에 안 띄움** — 위 "1. 슬롯필링 재설계"에서
  발견한 `decide_industry()` 게이트 문제(공고문 전용 분류기라 사용자
  아이디어 텍스트로는 항상 매칭 실패)가 아직 안 풀려서, 팀이 별도로
  재작업하기로 하고 지금은 아이디어 카드 결과만 보여줌.
- `backend/api/analysis.py`: `GET /analysis/regions` 신규 — `DiagnosisStep4.tsx`의
  지역 3단(시/도→시/군/구→행정동) 캐스케이딩 셀렉트박스용으로 `administrative_dong`
  테이블(3,924행) 전체를 한 번에 내려줌. 이 테이블은 실 DB엔 이미 있었는데
  `schema.sql`에 문서화가 안 돼있던 걸 발견해서 같이 정리함(상권분석
  `GET /analysis/market`도 내부적으로 이미 같은 테이블을 쓰고 있었음).

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
가드(당시 TODO로 꺼져있었음)를 켜는 작업을 하려고 교차 세션 메시지로
문의해옴. 그 시점엔 `AdminRoute.tsx` 자체는 안 건드렸다고 답했고, 인접
파일(`LoginForm.tsx`, `backend/api/auth.py`, `schema.sql`)을 그날 건드렸다고
알려줌.

**[해결됨]** 이후 확인해보니 그 가드가 실제로 켜져 있었음(`if (!isAuthed)
return <Navigate to="/admin/login" />` 주석 해제됨) — mulkko-7d 또는
사용자가 직접 켠 것으로 추정, 누가 했는지는 명확히 확인 안 됨. 비로그인
상태로 `/admin/*` 접근 시 `/admin/login`으로 리다이렉트되는 것까지 직접
확인 완료. 이 세션 중에도 `ProfileEdit.tsx`가 `SelectSheet` 컴포넌트를
참조하다가(빌드 에러) 이후 스스로 원복되는 등, 같은 파일을 여러 세션/본인이
번갈아 건드리는 상황이 계속 있었음 — **이어받을 땐 항상 `git status`/`git
diff`로 로컬 미커밋 변경사항부터 먼저 확인할 것** (이 문서에 안 적힌 변경이
디스크에 더 있을 수 있음).

## ❌ 다음 세션 우선순위 제안

1. **KSIC 분류기가 사용자 아이디어 텍스트를 못 읽는 문제 (여전히 최우선)** —
   위 "1. 슬롯필링 재설계" / "12. 사업구체화 진단" 참고. 슬롯 구성은 다
   고쳤고 정식 화면(진단 1~4)까지 나왔는데, `decide_industry()`가 공고문
   전용 게이트라 실제 매칭이 계속 안 돼서 **결과 화면에서 KSIC 자체를 숨긴
   상태로 우회 중**. 게이트 프롬프트 우회 또는 전용 분류 경로 신설 필요 —
   미루면 미룰수록 "업종코드 없는 진단 결과"가 정식 기능인 것처럼 굳어질
   위험 있음.
2. **`SelectSheet` 컴포넌트 — 만들어놓고 아직 아무 데서도 안 씀**
   (`frontend/src/components/SelectSheet/`). `ProfileEdit.tsx`의 지역/
   연령대/기업유형 select 3개를 매칭 리스트처럼 팝업으로 바꾸려던 작업으로
   보이는데, 중간에 보류됨(사용자 확인) — 이어서 연결할지, 그대로 둘지 결정 필요.
3. **사업구체화 진단 제출을 정식 API로 교체** — 지금은
   `/api/test/slot-filling`(테스트용, DB 미저장) 재사용 중. 정식 저장
   경로 필요.
4. **햄버거 메뉴 드로어 사용 여부 결정** — 결정만 나면 주석 4곳 풀기만
   하면 됨(위 "4. 홈 화면" 참고).
5. **`물꼬_사업구체화_지표결합_설계안.docx`의 미결 항목 5개** — 팀 확인 필요
   (문항 구조, 우수사례 매칭 시점/데이터 자체, KSIC 정확도, PSST 분할, RAG 정의).
6. **로그인 UX 마무리** — 비밀번호 찾기(`href="#"` 죽은 링크), 회원가입 직후
   자동 로그인 여부, 관리자 배지 정합성 등.
7. **마이페이지 남은 2개 섹션(분석리포트/지원내역) 실데이터 연동** —
   찜하기/채우기이용내역은 오늘 연동 완료(구현율 75%로 반영). 남은 2개는
   대응 DB 테이블(`idea_refinement_sessions`, `applications` 등)이 실제로
   0건이라 연동해도 항상 빈 목록 — 데이터가 쌓이기 시작하면 그때 연동.
8. **ProfileEdit 프로필사진 변경 / 사업자등록증 재업로드** — 여전히 TODO
   (재업로드는 시나리오 분석까지만 해둠, 코드 미착수 — `ProfileEdit.tsx`
   `handleBizCertClick` 주석 참고).

## 관련 파일 (2026-09-10 작업분)

| | |
|---|---|
| 슬롯필링/업종매칭 | `backend/api/idea_card_test.py`, `frontend/dev/idea-flow-test.html`, `backend/ml/classifier/{decide_industry,llm_match}.py` |
| 사업구체화 진단 정식 화면 | `frontend/src/pages/diagnosis/{DiagnosisSelect,DiagnosisStep1~4}.tsx`, `backend/api/analysis.py`(`/regions` 신규), `backend/db/schema.sql`(`administrative_dong` 문서화) |
| 로그인 세션 | `backend/auth/session.py`, `backend/api/auth.py`, `backend/db/schema.sql`(auth_sessions), `frontend/src/auth/session.ts`, `frontend/src/components/LoginForm.tsx`, `frontend/src/App.tsx` |
| 관리자 인증 가드 | `frontend/src/pages/admin/AdminRoute.tsx` |
| 마이페이지 사업자등록증/찜하기/이용내역 | `backend/api/mypage.py`, `frontend/src/pages/mypage/{MyPage,ProfileEdit}.tsx`, `frontend/src/components/BizCertUpload/{BizCertUpload.tsx,bizCertUpload.module.css}`, `backend/assistant/biz_cert_ocr.py` |
| 매칭 필터/리스트/상세/서류 | `backend/api/matching.py`, `frontend/src/pages/matching/{MatchingList,FilterPage,MatchingDetail,DocPreview}.tsx`, `frontend/src/utils/downloadFilledDoc.ts` |
| 고객센터 챗봇 | `backend/api/support.py`(기존), `frontend/src/pages/support/CustomerSupport.tsx`(신규) |
| 홈/온보딩 | `frontend/src/pages/home/Home.tsx`, `frontend/src/pages/onboarding/Onboarding.tsx`, 각 `.module.css` |
| 미사용/보류 컴포넌트 | `frontend/src/components/SelectSheet/`(만들어짐, 아직 어디서도 안 씀) |
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
