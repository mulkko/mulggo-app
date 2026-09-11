# mulkko 배포 정리

## 확정된 배포 스택
- **백엔드**: Render
- **프론트엔드**: Vercel
- **DB**: Supabase (PostgreSQL, 프로젝트 ID: `jfcpdqpniutrdiruwlcx`)

## Supabase 보안 설정
- RLS(Row Level Security) 전체 테이블에 적용
- 새 프로젝트 기본 설정: "새 테이블 자동 노출 OFF + 자동 RLS ON"

## 배포 절차 (6단계)
1. **Supabase DB 준비**: 스키마 마이그레이션 후 Settings > API에서 프로젝트 URL, anon/service key 확보
2. **백엔드 Render 배포**: New Web Service → GitHub repo 연결 → Root Directory: `backend` → Build: `pip install -r requirements.txt` → Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. **환경변수 등록 (Render)**: `.env` 내용을 Render Environment 탭에 그대로 등록 (Supabase URL/키, Fernet 키 등). `.env` 파일 자체는 업로드 금지
4. **프론트엔드 Vercel 배포**: New Project → 같은 repo 연결 → Root Directory: `frontend` → Framework: Vite 자동 감지
5. **프론트-백엔드 연결**: Vercel 환경변수에 `VITE_API_URL` = Render 백엔드 주소 등록, 백엔드 CORS 설정(`main.py`)에 Vercel 도메인 추가
6. **배포 확인**: Vercel URL 접속해 회원가입/로그인 등 API 호출 기능 테스트

## 미해결/추후 확인 필요
- (배포 진행하면서 막히는 부분, 계정 이전 시 재설정해야 할 항목 등 여기에 계속 추가)

---

## 업종코드 매칭(`mulkko_industry_code_matching`) 배포 검토 — 2026-09-11

`backend/mulkko_industry_code_matching/`은 AI 담당자가 별도로 만든 "사업 아이디어 → 국세청 6자리 업종코드" 매칭 패키지. 아직 메인 백엔드(`backend/main.py`, `backend/api/*.py`) 어디에도 연결 안 된 상태(미착수). 배포 방식을 두고 논의한 내용 정리.

### 벡터DB(Chroma)란
- 파일 저장소 아님. 업종코드 14,627개 설명 글을 숫자 좌표(임베딩)로 바꿔서 저장해두고, "뜻이 비슷한 것"을 찾는 검색 색인.
- 실체는 폴더 하나: `chroma_db/business_code_docs_bge_m3/` 안에 `chroma.sqlite3`(메타데이터) + `.bin` 파일들(좌표값 원본, HNSW 색인).
- 로컬에서 실제로 만들어보고 확인한 구조.

### git에 올리지 않는 이유
- 완성된 벡터DB 폴더 약 74MB. 지금 `.git` 전체 크기가 90MB인데 여기에 한 번에 거의 두 배로 불어남.
- 재색인할 때마다(데이터 갱신 시) 바이너리가 통째로 바뀌어서 git이 델타 압축을 못 함 → 커밋할수록 계속 불어남.
- `.gitignore`에 이미 의도적으로 제외돼 있고(`backend/mulkko_industry_code_matching/chroma_db/`), 재생성 스크립트(`34_reindex_local.py`)로 언제든 재현 가능하다고 주석 남겨져 있음.
- **결론: git엔 안 올리고, 서버/로컬에서 직접 생성하는 현재 방식 유지.**

### Postgres(pgvector)로 이전 검토
- 우리 Supabase에 `pgvector` 확장 이미 설치 가능(버전 0.8.2, 미설치 상태) → **기술적으로는 가능.**
- 하지만: 확장 활성화 + 새 테이블/인덱스 설계 + **검색 코드(`23_match_business_code_v3.py`의 `collection.query()` 호출부 최소 3곳)를 SQL로 재작성**해야 함.
- 이미 골든셋 90건 기준 정확도(Top-1 70%)가 튜닝된 상태라, 재작성 후 재검증 필요 — 조용히 정확도 떨어질 위험 있음.
- git 부담은 해결되지만 **비용 문제(아래 참고)는 전혀 해결 안 됨.**
- **결론: 지금 단계에서는 비추천. Chroma 그대로 유지, 나중에 여러 서버로 확장하는 등 뚜렷한 이유 생기면 재검토.**

### 서버에 배포할 때 git 외 추가로 필요한 것 (체크리스트)
1. `chroma_db/` 폴더 — 서버에서 재색인 실행하거나 별도로 이전
2. `.env` (`OPENAI_API_KEY` 등) — git엔 `.env.example`만 있음, 실제 키 새로 등록
3. 이 서브패키지 전용 `requirements.txt` (`chromadb`, `sentence-transformers`, `torch` 등) — 메인 프로젝트 `requirements.txt`엔 없음, 별도 설치 필요
4. (bge-m3 계속 쓸 경우) 모델 가중치 — 최초 실행 시 자동 다운로드(HuggingFace, 약 2GB), 서버에 인터넷 필요
5. **API 라우터 연결 코드 자체가 아직 없음** — 파일 다 올려도 실제 서비스에서 안 씀, FastAPI 라우터 추가 작업 별도 필요

### 비용/인프라 문제 — 두 가지 다른 축
| | 벡터DB(Chroma) 저장 위치 | 임베딩 모델 선택 (bge-m3 vs OpenAI) | LLM 재판정(GPT-5-mini) |
|---|---|---|---|
| 성격 | 어디에 저장하냐 | 무엇으로 텍스트→숫자 변환하냐 | 후보 중 최종 판단 |
| 비용 | 저장 자체는 무료 | bge-m3=로컬 무료(단 서버 자원 필요) / OpenAI=API 요금(저렴) | 요청당 실비용 발생, **저장 위치와 무관하게 항상 발생** |
| 무료 서버 영향 | 큰 문제 없음(74MB 파일) | **bge-m3는 모델 자체가 2GB+라 무료 서버 RAM에 못 들어갈 가능성 높음** | 무관 |

- **실제 요청당 비용(GPT-5-mini + 임베딩)은 벡터DB를 어디 두든 항상 발생** — pgvector로 옮겨도 안 없어짐.
- OpenAI는 이미 $5 크레딧 확보/유지 중(부트캠프 기간 유지 예정) → 요청당 약 $0.01~0.03 기준 150~250건 정도 감당 가능한 수준. 단, 골든셋 재생성(`36_build_gold_draft.py` ~$0.3)·전체 평가(`38_eval_pipeline.py` ~$1.5) 재실행 시 한 번에 크게 소모되니 주의.

### 무료 서버 + bge-m3 조합이 안 되는 이유 (실측)
- bge-m3 모델 자체 ≈ 2.2GB + OS/런타임 오버헤드 ≈ 1GB → **최소 3GB대 RAM 필요.**
- **AWS Lightsail 실제 요금 확인(2026-09 기준)**:
  - 무료체험(3개월)은 $5/$7/**$12(2GB RAM)**까지만 적용됨 — **2GB로는 bge-m3 못 돌림.**
  - bge-m3가 안정적으로 돌아가는 사양(4GB RAM)은 **$24/월 플랜인데 무료체험 대상에서 제외.**
  - Lightsail은 시간당 과금(월 상한 있음) → 며칠만 써도 비례 청구되지만, **정지(stop)만으로는 과금이 안 멈추고 삭제(delete)해야 멈춤.**
- **결론**: 무료 서버 그대로 쓰려면 bge-m3 포기하고 OpenAI 임베딩(`text-embedding-3-small`)으로 전환. bge-m3 그대로 쓰려면 유료 서버(월 약 3만원대, 4GB RAM) 필요.

### 클라우드 PC(VM) vs 유료 배포 서버(PaaS) 차이
- **클라우드 PC(VM, 예: AWS Lightsail/EC2)**: 컴퓨터 자체를 통째로 빌림, 원하는 사양·설치물 직접 통제. bge-m3처럼 무거운 걸 확실히 돌리려면 이쪽이 안전.
- **유료 배포 서버(PaaS, 예: Render — 우리 확정 배포처)**: 코드만 올리면 나머지 관리는 플랫폼이 대신함. 단, 무거운 패키지(torch 등)가 플랜별 빌드/용량 제한에 걸릴 수 있어 **Render 쪽 정확한 스펙은 별도 확인 필요** (이번 조사에서 확인한 요금은 Lightsail 기준이고 Render 자체 수치는 아직 미확인).
- 세팅 방식: VS Code의 "Remote - SSH" 확장으로 클라우드 PC에 붙으면 로컬과 거의 동일한 화면으로 작업 가능(단, 최초엔 파이썬/git clone/pip install/.env 세팅을 새로 해줘야 함).

### 대안: OCR과 같은 하이브리드 방식 (팀원 PC를 모델 서버로)
- 지금 사업자등록증 OCR(`Qwen2.5-VL-3B-Instruct`, bge-m3보다 더 무거움)이 이미 이 방식 사용 중: GPU 있는 고정 PC(`192.168.0.160`)에 모델만 올리고, 나머지는 요청만 보내는 구조.
- bge-m3도 같은 방식 적용 가능. **부트캠프 기간(로컬 네트워크 시연) 동안은 문제없이 가능** — 단, 프로젝트 종료 후 개인 PC를 계속 켜둘 수 없으므로 그 시점엔 유료 서버나 OpenAI 임베딩 전환 등 다른 방법 필요.
- 실제 외부 배포 서버(Render 등)에서 이 PC로 요청을 보내려면 **포트포워딩 또는 Cloudflare Tunnel 같은 터널링 서비스** 필요(포트포워딩보다 터널링이 설정 간단하고 보안상 안전 — 나가는 연결만 사용, 공유기 설정 불필요).
- 이 PC 자체에서 터널링 서비스가 될지 실측 확인함: 아웃바운드 443 포트 정상(0.03초 연결), 프록시 차단 없음, Windows 64비트로 `cloudflared` 공식 지원 환경 — **기술적으로 문제없음.**
- 망 부담: 나가는 연결만 쓰므로 학원/공유 네트워크에 기술적 부담·보안 구멍 거의 없음. 단, 기관 보안 정책상 터널링 프로그램 자체를 금지하는 경우가 있을 수 있어 **학원 네트워크 정책 확인은 별도로 필요.**
- 참고: 같은 GPU PC라도 유선 랜은 되는데 와이파이로는 접속 안 되는 증상은, 윈도우가 와이파이/유선을 다른 "네트워크 프로필"(공용/개인)로 잡아서 방화벽이 공용 프로필의 inbound를 막기 때문일 가능성이 높음(포트포워딩과는 별개 문제).

### 남은 결정 사항
1. bge-m3 유지(유료서버 또는 팀원PC+터널링) vs OpenAI 임베딩 전환 — 아직 미결정
2. Render의 실제 RAM/빌드 제약 확인 (Lightsail 수치로 대체 판단하면 안 됨)
3. 학원 네트워크가 터널링 프로그램(cloudflared 등) 허용하는지 확인
4. 위 방향 정해지면 → API 라우터 연결 코드 작성 (현재 미착수)

### 추가 확인 (2026-09-11)
- **`.env`에 실제로 채워야 할 키는 `OPENAI_API_KEY` 하나뿐.** `LLM_MODEL`/`EMBEDDING_MODEL`은 비밀값이 아니라 그냥 설정 문자열이라 예시 파일 기본값 그대로 두면 됨.
- **벡터DB 종류(Chroma)는 어디서 돌리든(클라우드 PC든 이 PC든) 고정.** "어디서 돌리냐(호스팅 위치)"와 "어떤 DB 기술을 쓰냐"는 서로 다른 축이라, 지금 코드(`23_match_business_code_v3.py`)가 Chroma 전용으로 짜여 있는 이상 호스팅 위치와 무관하게 항상 Chroma를 씀 (pgvector로 바꾸려면 위에서 다룬 코드 재작성이 필요하고, 이건 비추천 상태).

### 개발 기간 진행 순서 (이 PC 기준)
1. `.env` 만들고 `OPENAI_API_KEY` 채우기
2. **벡터DB 재색인** — `python business_matching/34_reindex_local.py --model bge-m3` → **완료 (2026-09-11)**, 이 PC GPU(RTX 4060)로 실행
3. 상태 점검 — **완료.** `health()` 결과: `chroma_doc_count 14627`, `reference_rows 1612`, `exclusion_note_codes 904` — README 정상값과 일치 확인
4. 한 건 테스트 (스모크) — 아직
5. 메인 백엔드에 API 라우터 연결 (미착수)
6. 프론트엔드 3상태 분기 UI 연동 (미착수)

### 프로젝트 컨벤션에 맞게 구조 정리 (2026-09-11)
"확인만" 요청이 아니라 실제 반영 요청받아 진행. 완료한 것:
- **폴더 이동**: `backend/mulkko_industry_code_matching/` → `backend/ml/industry_code_matching/` (CLAUDE.md 폴더구조상 `ml/`이 맞는 자리). `.gitignore` 경로도 갱신.
- **env 변수명 충돌 회피 + 통합**: `LLM_MODEL`/`EMBEDDING_MODEL`이 기존 `backend/ml/classifier/llm_match.py`(다른 기본값 `gpt-4o-mini`)와 이름이 겹쳐서, 이 패키지 것만 `INDUSTRY_MATCH_LLM_MODEL`/`INDUSTRY_MATCH_EMBEDDING_MODEL`로 개명(코드 수정: `23_match_business_code_v3.py::load_env()`). 서브패키지 전용 `.env`/`.env.example` 삭제하고 루트 `.env`/`.env.example`에 통합.
- **`requirements.txt` 병합**: `chromadb` 정식 추가, `torch`/`sentence-transformers`는 기존 OCR과 같은 패턴(무거운 GPU 패키지는 주석으로 별도 설치 안내)으로 정리. 서브패키지 자체 `requirements.txt` 삭제.
- **API 응답 포맷 통일**: `service.py::predict()`를 CLAUDE.md 8번 규칙(`{"success", "data"|"error"}`)에 맞게 변경 (기존 `{"ok", ...}` 형식에서 전환).
- 각 단계마다 `health()`로 재검증, 벡터DB(`chroma_doc_count 14627`) 정상 유지 확인.

**파일명 정리(번호 접두사 제거) — 완료 (2026-09-11)**: 처음엔 참조 범위가 너무 커서(파이썬 6개 + 문서 30여 군데) 보류했으나, "나중에 헷갈리는 것보다 지금 하는 게 낫다"는 판단으로 진행함.
- `business_matching/` 안 번호 접두사 파일 20개 전부 `git mv`로 개명 (예: `23_match_business_code_v3.py` → `match_business_code.py`, `34_reindex_local.py` → `reindex_local.py`)
- 이 파일명들을 참조하던 **62개 파일**(코드 내 `importlib` 경로, 마크다운/HTML 문서의 파일명·"25번"류 번호 언급 전부) 자동 치환 스크립트로 일괄 정리, 이후 `print()`/`raise()` 런타임 문자열에 마크다운 백틱이 잘못 섞여 들어간 곳들과 `.py`(모음 끝소리) 뒤에 어색하게 붙은 조사("과"→"와")까지 손으로 재검토해 수정
- 예외: `EXPERIMENT_hierarchy_rerank.md`/`docs/pipeline_flow_2026-09-09.md`에 남은 "31번"/"32번" 언급은 그대로 둠 — 현재 폴더에 없는(archive로 이미 빠진) 실험 스크립트를 가리키는 정확한 역사적 기록이라 손댈 대상이 아님
- 매 단계 `health()` + 무료 오프라인 테스트(`test_pipeline_v4_offline.py`, 28건)로 재검증, 전부 통과·`chroma_doc_count 14627` 유지 확인

### 재색인 중 발견한 것: `.env` 우선순위 문제
- 재색인/상태점검 시 서브패키지(`mulkko_industry_code_matching/`) 안에 `.env`가 없어도 에러 없이 넘어갔는데, 이유는 **상위 폴더 `E:/mulkko/.env`(메인 프로젝트 전체 설정)에 이미 `OPENAI_API_KEY`가 있어서 그걸 자동으로 찾아 쓴 것**(`python-dotenv`가 현재 위치에서 상위로 올라가며 `.env`를 탐색함).
- 문제는 **`EMBEDDING_MODEL`은 이 방식으로 안 채워짐** — 코드 기본값이 `bge-m3`가 아니라 `text-embedding-3-small`이라서, 명시적으로 지정 안 하면 방금 만든 bge-m3 색인이 아니라 존재하지도 않는 OpenAI용 색인을 찾다가 에러남 (`Collection [business_code_docs_2025] does not exist`).
- **결론**: `OPENAI_API_KEY`는 메인 `.env` 상속으로 지금 당장은 동작하지만, **`EMBEDDING_MODEL=bge-m3`를 명시하는 서브패키지 전용 `.env`는 따로 필요.** 비밀값(진짜 키)이 들어가는 게 아니라 설정 한 줄(+ 필요시 `LLM_MODEL=gpt-5-mini`)이라 언제든 만들면 됨 — 다음 대화에서 만들지 여부 결정.

---
*작성일: 2026-09-10 / 계정 이전 시 참고용*
*업종매칭 배포 검토 추가: 2026-09-11*
