# CLAUDE.md

이 저장소에서 작업할 때는 아래 내용을 기본 전제로 삼는다.

## 1. 프로젝트 개요

**mulkko** — 정부지원사업 매칭 AI 서비스 (부트캠프 최종 프로젝트, 팀 6인, 약 3주).
막연한 사업 아이디어를 AI 질문으로 구체화하고, 자격 맞는 정부지원사업을 우대조건 충족순으로 골라주며, 성장 로드맵과 AI 신청서 초안 생성까지 돕는다.

## 2. 기술 스택

- **백엔드**: FastAPI
- **프론트엔드**: React (Vite + TypeScript)
- **DB**: Supabase (PostgreSQL)
- **벡터DB**: Chroma (서버 모드)
- **ORM**: SQLAlchemy

## 3. 인증 방식

- 비밀번호: **bcrypt** 해싱
- 민감 필드: **Fernet** 암호화
- 로컬 개발 환경: **SQLite** 사용 (Supabase 대신 로컬 DB로 개발)

## 4. 폴더 구조

```
mulkko/
├── backend/
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── api/                    # 엔드포인트 (auth.py: 로그인/회원가입, admin.py: 관리자용)
│   ├── auth/                   # 로그인/회원가입 검증 로직
│   ├── crawler/                # 원본 수집 (API 호출/크롤링) → DB raw 테이블 저장
│   │   └── bizinfo_api.py      # 기업마당 API 수집 스크립트
│   ├── preprocessing/          # raw → 구조화 가공, DB processed 테이블 저장
│   ├── db/                     # DB 연결/스키마 (connection.py, schema.sql)
│   ├── rag/                    # RAG 인덱싱/벡터DB(Chroma) 연동
│   ├── chatbot/                # LangChain 사업구체화 챗봇 로직
│   ├── ml/                     # 업종 자동매핑 분류기 + 매칭 재정렬 모델
│   └── assistant/              # AI 신청서 어시스턴트 (PSST 초안 생성)
│
├── frontend/                   # 사용자·관리자 화면 전부 여기 (React + Vite + TS)
│   ├── dev/                    # dev_links.html(로컬 서버 링크 모음) + 단독 기능 검증용 테스트 페이지 (예: ocr-test.html)
│   │                            #   - page-prompt-checklist.html: 새 사용자 화면 요청할 때 채우는 체크리스트
│   │                            #   - api-endpoints.html: 백엔드 엔드포인트 목록 (수동 관리, 자동 동기화 안 됨)
│   │                            #   - 파일명에 `_test`가 들어가면 개인 테스트용으로 간주해 git에서 제외됨(.gitignore, `frontend/dev/*_test.*`).
│   │                            #     팀 공용 테스트 페이지는 `ocr-test.html`처럼 하이픈(-test)으로 구분.
│   └── src/
│       ├── pages/              # 화면별 컴포넌트, 기능 폴더로 구성 (auth/, admin/ 등)
│       ├── components/         # 여러 화면이 공유하는 컴포넌트 (AdminStyleGuide, WebStyleGuide 등)
│       ├── styles/             # 전역 CSS + 페이지별 *.module.css, 디자인 토큰(adminTokens.css: 관리자, webTokens.css: 사용자)
│       └── assets/             # 이미지 등 정적 리소스 (기능별 하위 폴더, 예: assets/admin/)
│
├── frontend-admin/              # (레거시) Streamlit 관리자 화면 — 더 이상 사용 안 함, 관리자 화면은 frontend/src/pages/admin으로 이전됨
│
├── data/                        # 소규모 정적 참고자료 + ML 라벨 데이터 + 로컬 테스트 샘플만 (대용량은 DB에)
├── docs/                        # 기획 문서, 발표자료
├── requirements.txt
└── README.md
```

## 5. 코딩 컨벤션

파일명에 담당자 이름이나 역할을 넣지 않는다 (예: `kim_login.py`, `ta1_utils.py` 금지). 언어별로 이미 통일되어 있는 방식을 따른다.

- **백엔드(Python)**: 소문자 + 언더스코어(snake_case). 파일명(`bizinfo_api.py`, `connection.py`)과 함수/변수명(`fetch_page`, `save_to_db`) 모두 동일 (PEP8 표준).
- **프론트엔드(React/TS)**: 컴포넌트 파일은 PascalCase(`Login.tsx`, `AdminHome.tsx`, React 표준), 짝꿍 CSS 모듈은 컴포넌트명을 소문자로 시작한 camelCase(`login.module.css`, `adminHome.module.css`), 변수/함수는 camelCase(`handleSubmit`).

## 6. Git 브랜치 규칙

`{역할}_{작업내용}` 형식 (예: `TA1_rh`, `DA3_ha`). 역할 코드는 README의 팀 구성 기준(DA1/DA2/DA3/TA1/TA2)을 따른다.

- 작업 브랜치를 오래 방치하지 말고, 틈틈이 `main`을 merge해서 따라잡는다. 오래 묵혀두면(수십 커밋 이상 벌어지면) 나중에 합칠 때 충돌이 크게 나서 되돌리기 번거로워진다.
- **작업 브랜치에서 커밋하는 건 끝이 아니라 과정이다.** 각자 브랜치(`TA1_rh` 등)에 커밋 + 푸시까지 했어도, 그 자체로 끝내지 않고 **PR을 열어서 `main`에 머지하는 것까지가 한 작업 단위**다. 브랜치에만 쌓아두고 PR을 안 열면 다른 팀원 작업과 계속 갈라진 채로 남아서, 나중에 합칠 때 충돌이 커지고 팀원들이 서로의 최신 변경사항을 못 보게 된다. 커밋/푸시를 마쳤으면 사용자에게 PR 생성 여부를 먼저 물어보고, 원하면 PR 링크/제목/설명까지 만들어준다 (`gh` CLI가 없으면 제목·본문이 채워진 `https://github.com/<owner>/<repo>/compare/main...<branch>?quick_pull=1&title=...&body=...` 형태의 링크로 대신한다).

## 7. 데이터 원칙

- **raw 데이터는 가공 없이 원본 그대로 저장** (`crawler/`가 담당, 예: `announcements_raw_bizinfo` 테이블)
- **가공은 별도 단계로 분리** — `preprocessing/`이 raw를 읽어서 구조화된 결과를 별도 테이블에 저장
- 원본/가공본을 분리하는 이유: 전처리 로직 버그 발생 시 크롤링을 처음부터 다시 하지 않고 저장된 원본으로 재처리만 하면 됨
- `data/` 폴더에는 대용량 원본/가공 데이터를 두지 않는다 (DB가 저장소 원칙)

## 8. API 응답 포맷

- 성공 응답:
  ```json
  { "success": true, "data": ... }
  ```
- 실패 응답:
  ```json
  { "success": false, "error": { "message": ..., "code": ... } }
  ```
- 상태 코드 규칙:
  - `200` / `201` 성공
  - `400` 잘못된 요청 (유효성 검사 실패)
  - `401` 인증 안 됨
  - `403` 인증은 됐지만 권한 없음 (예: 관리자 아닌 계정으로 관리자 로그인 시도)
  - `409` 중복 (이메일 중복 등)
  - `422` 요청 형식 오류 (Pydantic 검증 실패)
  - `500` 서버 에러

## 9. 환경변수 관리

- DB 접속정보, API 키, Fernet 암호화 키 등 민감정보는 전부 `.env` 파일에서 관리한다.
- 코드나 `CLAUDE.md`, 커밋에 절대 하드코딩하지 않는다.
- `.env`는 `.gitignore`에 포함되어야 한다.
- 필요한 환경변수 목록은 `.env.example` 파일로 별도 관리한다 (실제 값 없이 키 이름만).

## 10. 프론트엔드 디자인 토큰

- 색상·타이포그래피·radius 값은 코드에 하드코딩하지 않고 `frontend/src/styles/adminTokens.css`(관리자 화면, 파란색 계열) / `webTokens.css`(사용자 화면, 틸그린·네이비 계열)의 CSS 변수(`:root`)로만 관리한다.
- 값의 출처는 Figma `mulkko-style-guide` 파일(fileKey: `PpV1b4s9zsB1UHLGEtBQWP`)이다. 새 색상/컴포넌트가 필요하면 이 프레임에서 실측값(Dev Mode로 노드를 열어 실제 hex/padding/radius 확인)을 가져와 반영하고, 텍스트 스펙만으로 추측하지 않는다.
- 변수 네이밍은 기존 규칙을 따른다: `--color-{이름}`(배경/베이스), `--color-{이름}-text`(그 색 위에 얹는 텍스트/보더), `--color-bg-*`(페이지·비활성 배경), `--radius-{용도}`(sm/md/lg/btn/pill).
- 새 값을 추가했으면 반드시 해당 스타일가이드 컴포넌트(`components/AdminStyleGuide` 또는 `components/WebStyleGuide`)에도 같이 반영하고, `/style-guide`(관리자) 또는 `/dev/web-style-guide`(사용자) 라우트에서 눈으로 확인한다. 코드와 스타일가이드 문서가 항상 일치해야 한다.
- `adminTokens.css`와 `webTokens.css`는 둘 다 `main.tsx`에서 전역으로 로드되므로, **같은 변수 이름을 두 파일에 각각 다른 값으로 정의하면 안 된다** (나중에 로드되는 파일 값이 조용히 덮어씀). 새 변수를 추가하기 전에 다른 쪽 토큰 파일에 같은 이름이 이미 있는지 먼저 확인한다. 같은 색상/값이 이미 다른 이름으로 있으면 새로 만들지 말고 기존 변수를 재사용한다.
- 사용자(web) 화면은 모바일 우선 레이아웃을 기본으로 하고, 데스크톱에서는 `frontend/src/styles/common.css`의 `.pageContainer` 클래스로 최대 640px 가운데 정렬한다. 별도의 데스크톱 전용 레이아웃(사이드바, 그리드 등)은 만들지 않는다.
