# KSIC 매칭 코드 재배치 (2026-09-05)

## 무엇을 왜 옮겼나

DA2가 만든 업종(KSIC) 매칭 + 지역 하드필터 코드가 `backend/matching/`이라는
새 폴더에 통째로 들어와 있었습니다. 기능은 이미 실제 bizinfo API 데이터로
검증 완료(원문추출→지역매핑→업종매칭까지 정상 동작)했지만, `backend/matching/`은
`README.md`가 정의한 폴더 구조에 없는 폴더였고, 안의 코드는 역할별로 보면
이미 만들어져 있던 두 폴더에 정확히 대응됐습니다.

- `backend/ml/classifier/__init__.py`에 이미 이렇게 적혀 있었음:
  > "업종 자동매핑 분류기 (자유텍스트 업종 -> 국세청 업종코드/KSIC 정규화) / 담당: 매칭 & 업종 분류기 (DA2)"
- `backend/preprocessing/__init__.py`에 이미 이렇게 적혀 있었음:
  > "원본 -> 구조화된 데이터로 가공... 예정 파일: qualification_parser.py(자격요건 구조화), attachment_parser.py(첨부자료 파싱)"

그래서 새 폴더를 만드는 대신, 원래 계획된 자리로 파일을 옮겼습니다.

## 이동 내역

| 이전 위치 (`backend/matching/...`) | 새 위치 | 역할 |
|---|---|---|
| `ksic_core/explicit_match.py` | `backend/ml/classifier/explicit_match.py` | 업종매칭 1단계: KSIC 공식 명칭 문자열 매칭 |
| `ksic_core/decide_industry.py` | `backend/ml/classifier/decide_industry.py` | 업종매칭 최종 진입점 (1단계→2단계 오케스트레이션) |
| `ksic_core/llm_match.py` | `backend/ml/classifier/llm_match.py` | 업종매칭 2단계: LLM(OpenAI) 폴백 |
| `ksic_core/extract_region.py` | `backend/preprocessing/extract_region.py` | 지역 하드필터 추출 (자격요건 구조화) |
| `scripts2/extract_all_texts.py` | `backend/preprocessing/extract_all_texts.py` | 첨부파일(PDF/HWP/이미지) 다운로드 + OCR 원문 추출 |
| `scripts/region_apply_full.py` | `backend/preprocessing/region_apply_full.py` | 지역매핑 배치 실행 스크립트 |
| `ksic_core/pipeline.py` | `backend/preprocessing/pipeline.py` | 공고 1건을 위 세 단계로 이어붙이는 오케스트레이터 (최종 진입점: `process_notice()`) |
| `data/processed/ksic_clean_v2.csv` | `data/ksic_clean_v2.csv` | KSIC 코드 마스터 참고표 — 루트 `data/README.md`가 예시로 든 "국세청 업종 코드표"가 바로 이것 |
| `requirements.txt` | `backend/preprocessing/requirements.txt` | 이 기능 전용 의존성 (pdfplumber, pymupdf, paddleocr, openai 등) |

`backend/matching/` 폴더는 이제 완전히 삭제됐습니다.

## 코드에서 바뀐 것

- import 경로를 프로젝트 관례(`backend.xxx` 절대경로 — `backend/api/auth.py`가
  `from backend.auth.login import login`로 쓰는 방식과 동일)에 맞춰 전부 수정.
  예: `from ksic_core.explicit_match import ...` → `from backend.ml.classifier.explicit_match import ...`
- `pipeline.py`에 있던 `sys.path.insert(...)` 우회 코드 제거 — 이제 정식 패키지
  경로로 import되므로 더 이상 필요 없음.
- KSIC 마스터 CSV 경로(`KSIC_CLEAN_CSV_PATH`)를 새 위치(`data/ksic_clean_v2.csv`)
  기준으로 재계산하도록 수정 (`explicit_match.py`, `llm_match.py`).
- `region_apply_full.py`/`extract_all_texts.py`가 쓰는 대용량 배치 입출력 CSV
  (`bizinfo.csv`, `full_raw_texts_1589.csv` 등)는 `backend/preprocessing/data/`
  아래 로컬 작업 폴더로 유지(`raw/`, `outputs/`, `processed/`) — 실제 데이터는
  DB에 저장한다는 원칙(README)에 따라 이 폴더는 `.gitignore` 처리해 커밋되지 않음.

## 검증

이동 전/후로 실제 bizinfo API에서 받은 공고 데이터를 `process_notice()`에
그대로 넣어 돌려봤고, 원문추출(PDF/HWP 다운로드) → 지역매핑 → 업종매칭까지
**이동 전과 동일한 결과**가 나오는 것을 확인했습니다.

## 아직 남은 것 (이번 작업 범위 밖)

- `backend/db/schema.sql`의 `announcements_parsed` 테이블은 아직 이 파이프라인이
  뱉는 복수 업종 리스트/신뢰도(`ksic_confidence`)/지역 상태값 등을 담을 컬럼이
  없음 — DB 스키마 확장 필요.
- `backend/crawler/bizinfo_api.py`는 아직 CSV로만 저장하고 DB `announcements_raw`
  테이블에는 안 씀.
- `backend/api/`에 이 파이프라인을 호출하는 라우터가 아직 없음(지금은 `auth`만 있음).
