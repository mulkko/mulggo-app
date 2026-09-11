# 물꼬 업종코드 매칭 — 백엔드 통합 패키지 (2026-09-09판)

사용자의 사업 아이디어(PSST 자유 텍스트 3개)를 받아 **6자리 업종코드**를
자동으로 도출한다. 대표 업종 1개 + 부가 업종 0~2개를 신뢰도와 함께 반환한다.

> 이 패키지의 범위: **"사업 아이디어 → 업종코드"까지.**
> 업종코드 확정 이후의 지역 결합 / 지원사업 / 상권·시장분석은 별도 파트.

> **2026-09-09판 변경점**은 `CHANGELOG_20260909.md` 참고.
> 요약: 역할(role) 확정·필터, 검색 채널 분리(공식정보/해설서예시), 해설서 `<제외>` 규칙 반영.
> **성능: gold_set_v2(240건) 기준 최종 정확도 57.5% → 67.1%, 정답이 후보에 포함되는 비율 80% → 97.5%.**

---

## 1. 빠른 시작

```bash
# 1) 파이썬 3.10+ 환경
pip install -r requirements.txt

# 2) 환경변수
cp .env.example .env      # 그리고 OPENAI_API_KEY 채우기
#   (또는 서버 환경변수로 OPENAI_API_KEY / EMBEDDING_MODEL / LLM_MODEL 직접 주입)

# 3) 상태 점검
python -c "from industry_matcher import health; print(health())"
#   -> chroma_doc_count 14627, reference_rows 1612, exclusion_note_codes ~900 이면 정상

# 4) 한 건 테스트
python business_matching/match_business_code.py \
  --seed "직접 볶은 원두로 매장에서 커피 음료를 만들어 손님에게 판매하는 카페를 운영한다" \
  --problem "동네에 제대로 된 스페셜티 커피를 마실 곳이 없다는 불편이 크다" \
  --solution "좌석을 갖춘 매장에서 바리스타가 에스프레소 음료를 제조해 현장에서 판매한다"
```

벡터 DB(`chroma_db/business_code_docs_2025/`, 약 225MB, 문서 14,627개)는 **이미 구축되어 동봉**되어 있다.
`EMBEDDING_MODEL`을 그대로(`text-embedding-3-small`) 쓰면 재구축 불필요.

---

## 2. 입력 / 출력 (API 계약)

### 입력
| 인자 | 설명 | 길이 제한 |
|---|---|---|
| `seed` | 슬롯 0. 사업 아이디어 시드 | 20~120자 |
| `problem_to_solve` | 슬롯 2. 문제 / 기회 정의 | 20~250자 |
| `solution_approach` | 슬롯 5. 사업화 방식 | 20~300자 |
| `region` | 슬롯 14. 지역(선택) | 제한 없음. **업종 판정에 사용하지 않고** 통과만 |

길이 위반 시 `ValueError`. 프론트에서 먼저 검증 권장.

### 출력 (dict) — 백엔드가 최소로 쓸 필드

```jsonc
{
  "representative_business": {          // 대표 업종 (항상 1개)
    "business_code": "552303",          // ★ 6자리 업종코드
    "business_name": "커피 전문점",
    "confidence": "high",               // ★ high | mid | low  (UX 분기용)
    "ai_predicted_code": "552303",      //   business_code 별칭 (DB 저장용)
    "ai_predicted_score": 0.56,         //   검색 유사도(참고값, 정답 확률 아님). null 가능
    "candidate_rank": 1,                //   재판정이 후보 pool 몇 위를 골랐나
    "found_by_both_searches": true,
    "confidence_downgrade_reason": "",
    "alternatives": [                   // ★ "다른 업종 같아요" 후보 (최대 3)
      { "business_code": "552310", "business_name": "동물카페", "candidate_rank": 2, ... }
    ],
    "user_selected_code": null,         // ★ 사용자가 직접 고르면 백엔드가 채움
    "changed_by_user": false            // ★ 사용자가 대표 업종을 바꿨는지 백엔드가 채움
  },
  "additional_businesses": [ /* 부가 업종 0~2개, 구조 동일 */ ],
  "activities": [ /* LLM이 뽑은 수익활동 1~3개: activity_name, canonical_activity,
                     business_role, product_service, evidence, search_keywords, priority */ ],
  "activity_results": [ /* 활동별 후보 검색·재판정 상세. 디버깅/로깅용. */ ],
  "models": { "llm_model": "gpt-5-mini", "embedding_model": "text-embedding-3-small" },
  "input": { ... }
}
```

**최소 사용 필드:** `representative_business.{business_code, business_name, confidence, alternatives}`
+ `additional_businesses[].{business_code, business_name, confidence}`.

---

## 3. 백엔드에서 호출하기

```python
from industry_matcher import match_business_code, warm_up

warm_up()   # (선택) 서버 기동 시 1회 — 모델·DB·해설서 노트 예열

def resolve_industry_code(seed, problem, solution, region=""):
    result = match_business_code(seed, problem, solution, region)
    rep = result["representative_business"]
    return {
        "predicted_code": rep["ai_predicted_code"],
        "predicted_name": rep["business_name"],
        "confidence": rep["confidence"],
        "score": rep["ai_predicted_score"],
        "alternatives": [{"code": a["business_code"], "name": a["business_name"]}
                         for a in rep["alternatives"]],
        "additional": [{"code": b["business_code"], "name": b["business_name"],
                        "confidence": b["confidence"]}
                       for b in result["additional_businesses"]],
        "raw": result,   # 로깅용 전체
    }
```

- **동기 함수.** 내부에서 OpenAI를 **활동 1개당 3회**(구조화는 1회 공통, 활동별 임베딩 1회 + 재판정 1회) 호출.
  재판정 프롬프트가 후보 20개를 담아 입력 토큰이 크다. 응답 시간 보통 **8~20초.**
  워커/큐에서 처리하거나 타임아웃 30초+.
- 예외: 길이 위반 `ValueError`, DB/모델 불일치 `RuntimeError`, OpenAI 오류는 그대로 전파.
- 비용(참고): 요청당 gpt-5-mini 입력 ~1만 토큰 내외 + 임베딩. 대략 요청당 수 원~수십 원 수준(모델 단가에 따름).

---

## 4. 신뢰도(confidence)

`representative_business.confidence` = `high` / `mid` / `low`.

**계산:** ① 재판정 LLM이 `llm_confidence`(high/mid/low) 자기판단 → ② 검색 신호 가드로 **낮추기만** 한다.
코드: `match_business_code.py`의 `compute_confidence()`.

### 가드 (2026-09-09 데이터 기반 재설정, gold_v2 240건 실측)

| 조건 | 응답 필드 | 효과 |
|---|---|---|
| 재판정이 고른 후보가 pool **4위 이하** | `candidate_rank >= 4` | high → mid |
| 벡터·키워드 중 **한쪽에서만** 잡힘 | `found_by_both_searches == false` | high → mid |
| 1·2위 유사도차 < 0.06 이고 1위 아님 | `retrieval_margin < 0.06` | high → mid |
| 후보 6위 이하 **AND** 한쪽 검색만 | (둘 다) | → **low 확정** |

### 실측 정확도 (gold_v2 240건)

| 버킷 | 비중 | 실측 정확도 |
|---|---|---|
| `high` | 48% | **83.5%** |
| `mid` | 33% | 64.6% |
| `low` | 19% | 30.4% |

**이것이 아니다:** 학습된 분류 확률 ❌ / 통계적으로 calibrated된 임계값 ❌ / 코사인 절댓값 ❌.
본질적으로 **LLM 자기판단 + 규칙 가드**다. `high`여도 100%가 아니다 — 아래 사용자 확인이 전제.

### 사용자 확인 플로우 (필수)

```
confidence == high  →  "회원님 업종은 [커피 전문점]으로 확인됐어요"  [맞아요] [다른 업종 같아요]
confidence == mid   →  대표 + alternatives 나란히, "아래 후보도 확인해 주세요"
confidence == low   →  alternatives 크게 + 직접 검색·선택 UI 우선
```

`high`여도 **자동 확정 금지.** 최소 "[맞아요 / 다른 업종 같아요]" 1회 확인 단계를 둘 것.
(미국 Census BEACON, 영국 ONS ClassifAI도 "제시 후 사용자 확인" 방식.)

### 사용자 선택 로그 (정답 데이터 축적)

| 필드 | 채우는 주체 |
|---|---|
| `ai_predicted_code` / `ai_predicted_score` / `confidence` | 시스템 (이미 채워짐) |
| `user_selected_code` | **백엔드** — 사용자가 최종 고른 코드 |
| `changed_by_user` | **백엔드** — 대표 업종을 바꿨으면 true |
| 입력 텍스트 3개 | 백엔드 |

이 로그가 쌓이면 → 비순환 정답셋으로 신뢰도 임계값 재설정 / 검색 약한 업종 보강.

---

## 5. 성능

### gold_set_v2 — 240건 (통계청 KSIC 11차 해설서 <예시>/<제외> 기반, gpt-5-mini)

| 방식 | Top1 |
|---|---|
| 원문만 임베딩 (LLM 없음) | 61.7% |
| LLM 활동 구조화 + 임베딩 (후보 pool) | 36.7% (Top3 58%, Top5 66%) |
| **+ GPT 재판정 (현재 방식)** | **67.1%** |

- 정답이 후보 pool에 포함: **97.5%** (이전 80.4%)
- 정답이 후보 20위 안: 82.1%
- 남은 오답 79건 = 검색 실패 6 + 재판정 실패 73 (그중 42건은 정답이 pool 15위+ 로 깊음)

### gold_set_v1 — 42건 (손으로 만든 셋, 해설서와 무관)

| 방식 | Top1 |
|---|---|
| **+ GPT 재판정** | **92.9%** (이전 95.2% — LLM 비결정성 범위 내 동급) |

> gold_v2가 훨씬 넓고 어려운 셋이라 실제 실력에 가깝다. gold_v1 95%는 쉬운 손선별셋 과대평가였음.

상세: `docs/business_code_matching_status.html`, `docs/business_code_matching_onboarding.html`

---

## 6. 벡터 DB — 이미 포함됨 / 재구축 방법

`chroma_db/business_code_docs_2025/` 에 구축된 DB 동봉 (문서 **14,627개**).
문서 유형: `name`(업종명) / `hier`(계층) / `ksic`(연계 KSIC) / `desc`(설명) /
`example`(해설서 <예시> 활동) / `xref`(해설서 <제외> 경계 활동).

전체 재생성이 필요할 때만:
```bash
python business_matching/prepare_business_code_chroma_reference.py   # 원본 CSV -> reference CSV
python business_matching/prepare_business_code_docs.py --example-whitelist none
        #   reference + ksic_haeseol_v1.json -> 검색문서 CSV (example/xref 포함)
python business_matching/build_business_code_docs_chroma.py          # 임베딩 -> 벡터 DB (OpenAI, 약 $0.05, 4~5분)
```
`prepare_business_code_docs.py`는 `data/processed/ksic_haeseol_v1.json` 과 `ksic_clean.csv` 를 읽는다(신규 의존성).
`--example-whitelist <파일>` 로 특정 코드에만 예시를 붙일 수도 있다(빈 파일이면 예시 없음).

---

## 7. 알려진 제약 / 개선 포인트 (백엔드 담당자용)

1. **호출마다 재로드.** `match_business_code()`는 매번 reference CSV 로드 + Chroma 오픈 +
   OpenAI 클라이언트 생성을 한다. 트래픽 있으면 `match_business_code.py`의
   `load_reference()` / `reference_lookup()` / `open_chroma()` / OpenAI 클라이언트를
   모듈 전역에 1회 캐시하도록 리팩터링 권장. (`load_exclusion_notes()`는 이미 모듈 전역 캐시됨.)
2. **경로.** `PROJECT_ROOT = 파일의 상위상위` 기준으로 DB·CSV·JSON을 찾는다. 패키지 폴더 구조
   (`business_matching/`, `data/processed/`, `chroma_db/`)를 유지하면 그대로 동작.
   경로 변경은 `match_business_code.py` 상단 상수(`DB_DIR`, `REF_CSV`, `COLLECTION`,
   `HAESEOL_JSON`, `KSIC_CLEAN_CSV`) 수정.
3. **구조화 변동성.** gpt-5-mini가 같은 입력에도 표현이 달라진다. 대표 업종은 안정적,
   부가 업종은 흔들릴 수 있음. 캐싱하려면 입력 텍스트 3개를 키로.
4. **남은 오답 유형:**
   - `525101` 전자상거래 소매업 검색 미탐 (해설서 예시 1개뿐) — 소수
   - 정답이 후보 15~31위로 깊어 재판정 창(20) 밖 → `RERANK_TOP_N` 20→28 상향 검토
     (`match_business_code.py:57`, 2026-09-09 미검증 — OpenAI 크레딧 소진)
   - 제조·가공 반직관 케이스 (침구→임산물 채취 등 통계청 특유 분류)
5. **정답셋 순환 주의.** gold_v2는 해설서에서 파생 → 해설서를 검색에 넣은 현 구조에서는
   점수가 다소 낙관적. 실사용 로그(4절) 또는 해설서 밖 별도 셋으로 재검증 필요.

---

## 8. 파일 구성

```
industry_matcher.py                        백엔드 import 진입점 (여기서 시작)
                                            # 의존성/환경변수는 프로젝트 루트 requirements.txt / .env(.example)로 통합 관리
CHANGELOG_20260909.md                      2026-09-09판 변경 내역
business_matching/
  match_business_code.py   ← 파이프라인 본체 (match_business_code)
  eval_business_code.py       ← 성능 평가
  prepare_business_code_docs.py   ← 업종코드 -> 검색문서 (example/xref 포함)
  build_business_code_docs_chroma.py  ← 임베딩 -> 벡터 DB
  prepare_business_code_chroma_reference.py  ← (전체 재생성용)
  parse_ksic_haeseol.py       ← 해설서 PDF 파싱 -> ksic_haeseol_v1.json
  build_gold_from_haeseol.py  ← 해설서 근거 정답셋 생성 -> gold_set_v2.csv
  calibrate_confidence.py     ← 신뢰도 임계값 실측 분석 (무비용)
  gold_set_v1.csv (42건) / gold_set_v2.csv (240건)
data/
  raw/업종코드-표준산업분류 연계표.csv        원본 기준 데이터 (수정 금지)
  processed/business_code_chroma_reference_v1.csv   업종코드 1개 = 1행 (런타임 lookup)
  processed/business_code_docs_v1.csv               업종코드 1개 = 검색문서 여러 개 (빌드 산출물)
  processed/ksic_haeseol_v1.json    ★ 런타임 의존 — 해설서 정의/예시/제외
  processed/ksic_clean.csv          ★ 런타임 의존 — KSIC ↔ 업종코드 매핑
  processed/example_index_whitelist.txt   빌드타임(prepare_business_code_docs.py)용 — 예시 선별 색인
  outputs/                          평가 결과 저장 위치
chroma_db/business_code_docs_bge_m3/  구축된 벡터 DB (문서 14,627개, 로컬 bge-m3 임베딩)
docs/
  business_code_matching_status.html      개발 경위·성능·벤치마킹
  business_code_matching_onboarding.html  신규 팀원용 온보딩
```

---

## 9. 파이프라인 요약 (심사/발표용)

```
PSST 슬롯 0+2+5
 → ① GPT-5-mini: 실제 수익활동 1~3개 구조화 (canonical_activity, business_role)  ※ 코드 생성 안 함
      · business_role 을 18종 중 하나로 확정 (직접 만들면 제조 / 떼다 팔면 도소매 /
        연결 수수료면 중개 / 매장 조리면 음식점)
 → ② text-embedding-3-small: 여러 표현으로 임베딩 검색을 2개 채널로 분리
      · BASE 채널   : 공식정보(업종명/계층/KSIC/정의) — 상위 25개 반드시 유지
      · EXAMPLE 채널: 해설서 <예시>/<제외> 활동 — 상위 12개를 '추가만' (BASE를 밀어내지 않음)
 → ③ 키워드 검색 보완 → 통합 후보 Pool
      · 역할 상충 후보(소매인데 제조업 등)는 검색 순위 뒤로, 역할 부합은 앞으로
 → ④ GPT-5-mini 재판정 (후보 20개):
      · 1순위 = 역할 적합성 → 제품/서비스 일치 → 포함 예시 → <제외> 규칙 위반 여부
      · 후보 목록 밖 코드 생성 금지
 → ⑤ 대표 업종 1개 + 부가 업종 0~2개 + 신뢰도
```

해외 사례(미국 Census BEACON = 검색/검증 분리, 영국 ONS ClassifAI = 분류 1개당 다중 검색문서)를
국내 6자리 업종코드에 맞게 재설계. 근거는 `docs/` 문서 참고.
