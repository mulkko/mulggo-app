# 전체 흐름 — 업종코드 매칭 v3 + Soft Hierarchy Reranking (2026-09-09)

이 문서 = "입력부터 출력까지 데이터가 어디로 흐르고, 계층 rerank 실험이 정확히 어느 지점에
끼는가". 함수·파일명은 실제 코드 기준.

- 파이프라인 본체: `business_matching/match_business_code.py`
- 진입점: `industry_matcher.py` → `match_business_code(seed, problem, solution, region="")`
- 실험 스크립트: `business_matching/30·31·32`
- 실험 상세: `EXPERIMENT_hierarchy_rerank.md`

---

## 0. 한눈에

```
사업설명 3개(PSST)                                              대표 업종 1개
  seed / problem / solution   ──►   [ v3 파이프라인 ]   ──►   + 부가 업종 0~2개
  (각 길이 제한)                                                + 신뢰도 high/mid/low
                                                                + 대안 후보 최대 5개
```

계층 rerank는 이 파이프라인의 **딱 한 지점**(③→④ 사이, 후보 순위 매기기)만 건드린다.
플래그 `USE_HIERARCHY_RERANK` 기본 `False` = 아래 흐름과 **완전히 동일**.

---

## 1. v3 파이프라인 — 단계별 데이터 흐름

```
match_business_code(seed, problem, solution, region)          [23_..._v3.py:1043]
│
├─ validate_inputs()            길이 규칙 위반 시 ValueError
├─ load_env()                   llm_model="gpt-5-mini", embedding_model="text-embedding-3-small"
├─ load_reference()             business_code_chroma_reference_v1.csv → ref_df
│  reference_lookup(ref_df)     → lookup = { "552303": {업종명, 대/중/소/세분류명, KSIC, 설명}, ... }
├─ open_chroma()                chroma_db/business_code_docs_2025/  (문서 14,627개)
│
▼ ① 구조화  extract_activities(client, llm_model, seed, problem, solution)   [:489]
│     LLM 1회 호출.  ACTIVITY_SYSTEM 프롬프트 + json_schema(strict)
│     출력: activities = [
│       { activity_name, canonical_activity,        ← "커피 가공업" 같은 분류표 어투
│         business_role,                            ← 18종 enum 중 하나 (제조·가공 / 도매 / 소매 ...)
│         priority(primary 1개), product_service,
│         evidence, search_keywords[2~6] }, ...(최대 3개)
│     ]
│     ※ 업종코드는 여기서 절대 생성 안 함.
│
▼ 활동마다 반복 (for activity in activities):
│
│   ② 검색  ──────────────────────────────────────────────────────────
│   │
│   ├─ build_queries(activity)            [:532]   → 쿼리 최대 3개
│   │     q1 = canonical 단독
│   │     q2 = canonical + role + product + keywords
│   │     q3 = product + keywords
│   │
│   ├─ vector_search_multi(client, collection, emb_model, queries)   [:675]
│   │     · 쿼리 3개 임베딩  (OpenAI embeddings, 유료)
│   │     · vector_search_from_embeddings(collection, embs)          [:694]  ← 30/31이 여기로 진입
│   │         _search_channel(embs, BASE_DOC_TYPES)     name/hier/ksic/desc/def
│   │         _search_channel(embs, EXAMPLE_DOC_TYPES)  example/xref (해설서 예시·제외)
│   │         BASE 상위 25개 유지  +  EXAMPLE-only 상위 12개를 뒤에 '추가만'
│   │         → v = [ {business_code, vector_rank, cosine_similarity, from_base, from_example}, ... ]
│   │
│   └─ keyword_search(ref_df, activity)   [:767]   → k = 상위 15개
│         tokenize(canonical+product+activity_name+keywords) → expand_synonyms(동의어)
│         세세분류명 일치 2배 가중, linked_ksic는 제외
│         → k = [ {business_code, keyword_score}, ... ]
│
│   ③④ 후보 pool 만들기  build_candidate_pool(v, k, lookup, activity)   [:784]
│   │
│   │   각 후보 code 에 대해:
│   │     in_both_searches = (벡터에도 있고 키워드에도 있나)
│   │     role_fit  = role_fit(role, 후보.biz_large_names, 후보.업종명)     → 0 부합 / 1 중립 / 2 상충
│   │     role_d    = {0:-6, 1:0, 2:+12}[role_fit]                        ← 역할 순위 가감
│   │
│   │  ┌───────────────────────────────────────────────────────────────┐
│   │  │ ★ 계층 rerank 삽입 지점 (USE_HIERARCHY_RERANK=True 일 때만)      │
│   │  │   hf     = hierarchy_fit(activity, 후보)   → 0 적합 / 1 중립 / 2 상충 │
│   │  │            · 활동어(canonical/product/keywords) ↔ 후보 중·소·세분류명   │
│   │  │              + 세세분류명 + main KSIC  토큰 겹침비율              │
│   │  │            · business_role 은 입력으로 안 씀 (틀린 role 되돌리기용)  │
│   │  │   hier_d = {0:HIER_BONUS(-4), 1:0, 2:HIER_PENALTY(+6, B2만)}[hf]  │
│   │  └───────────────────────────────────────────────────────────────┘
│   │
│   │     role_adjusted_rank  = vector_rank + role_d               (기존 필드, 값 보존)
│   │     final_adjusted_rank = vector_rank + role_d + hier_d      (플래그 off면 hier_d=0)
│   │
│   │   정렬 키:  ( in_both 아니면 뒤로,  final_adjusted_rank,  -keyword_score )
│   │            └ 플래그 off면 final == role_adjusted → v3와 정렬 결과 동일
│   │   → pool = [ {..., candidate_rank}, ... ]   (제거 없음. 순위만 조정)
│   │
│   ⑤ 재판정  rerank(client, llm_model, activity, pool, top_n=20)   [:958]   ← 유료 (LLM 1회)
│   │   shortlist = pool[:20]
│   │   load_exclusion_notes()  → 후보별 해설서 <제외> 노트
│   │   후보 20개를 블록으로: 코드·세세~대분류·역할적합성(부합/중립/상충)·KSIC·세부설명·제외노트
│   │   RERANK_SYSTEM: 1)역할 2)제품일치 3)포함예시 4)제외위반 5)KSIC 6)계층
│   │   출력: selected_business_code, role_alignment, reason, confidence(high/mid/low)
│   │   후보 밖 코드면 → pool[0]로 대체 + confidence=low
│   │   pick_alternatives(shortlist, 선택코드, n=5)
│   │
│   ⑥ 신뢰도  compute_confidence(rr.confidence, selected, v)   [:898]
│       LLM 자기판단에서 시작, 아래면 한 단계 '하향만':
│         · candidate_rank ≥ 4          · 벡터·키워드 한쪽만
│         · 1·2위 cosine 차 < 0.06 & 1위 아님
│         · rank ≥ 6 AND 한쪽만  → low 확정
│
▼ 조립
    representative_business = primary 활동 결과  { business_code, business_name, confidence,
                              ai_predicted_code, ai_predicted_score, candidate_rank,
                              alternatives[], user_selected_code=None, changed_by_user=False }
    additional_businesses   = secondary 활동 결과 0~2개 (중복 코드 제외)
    return { models, input, activities, activity_results, representative_business, additional_businesses }
```

**계층 rerank가 바꾸는 것 = 위 ③④ 박스 하나.** ①②⑤⑥, 프롬프트, 검색, 반환 스키마 전부 그대로.

---

## 2. 왜 이 지점인가

| 사실 | 함의 |
|---|---|
| 정답이 후보 pool에 포함 = 97.5% | 검색(②)은 병목 아님 |
| 남은 오답 79건 중 73건이 재판정(⑤) 실패 | 병목은 최종 선택 |
| 그중 42건은 정답이 pool 15~31위 | ⑤는 pool[:20]만 본다 → 정답이 창 밖이면 못 고름 |
| 최대 실패원인 = ①의 business_role 오판 | role_d(+12)가 정답을 밀어냄 + ⑤ 프롬프트가 "역할 상충 탈락" 지시 |

→ 계층 신호를 **role과 독립적으로** ③④에 넣어, 정답을 pool 위로(→ 창 20 안으로) 끌어올리고
role 오판 페널티를 상쇄한다. 완전 배제는 안 함(hard filter 금지) — ⑤가 여전히 되돌릴 수 있게.

---

## 3. 실험 3단계가 v3의 어느 부분을 재현/변형하나

```
                 ①구조화   ②임베딩   ②검색·③④pool   ⑤재판정
                 (LLM)     (OpenAI)  (로컬,무료)      (LLM)
─────────────────────────────────────────────────────────────────
30_cache_...      ✔ 실행    ✔ 실행    –               –          → 결과를 exp_cache/ 에 저장  (유료 ~$0.37, 1회)
31_sweep_...      캐시 사용  캐시 사용  ✔ 상수 바꿔가며   ✘ 안 함    → pool 순위만 측정          (무료, 무한 반복)
32_ab_rerank     캐시 사용  캐시 사용  ✔ config A vs B  ✔ A/B 각각  → 최종 Top-1 비교           (유료 ~$1.5/회)
```

- **30** = ①②를 240건 한 번만 지불. `structuring.json`(활동) + `query_emb.npz`(쿼리 임베딩)
  + `fulltext_emb.npz`(원문 임베딩, Model A용) + `hier_emb.npz`(계층경로 임베딩, B2용).
  → ① 구조화 비결정성(±7%p)이 이 시점에 **고정**되어, A/B에서 노이즈가 하나 사라진다.
- **31** = `vector_search_from_embeddings`(캐시 임베딩) + `keyword_search` + `build_candidate_pool`을
  9개 config로 반복. 측정: `pool_recall@20`, `→win20`(정답이 창 안으로 새로 들어온 수), 역할별.
  플래그 OFF config가 동결본과 순위 동일한지도 검증(`회귀검증 PASS`).
  **여기서 효과 없으면 → 32 안 돌리고 $0.37에서 종료.**
- **32** = config A(플래그 off) / B(31이 고른 최적)로 `rerank`까지 실행. 최종 Top-1·역할별·
  개선/악화 케이스·제조↔도소매 혼동 수를 비교하고 §채택기준으로 자동 판정.

---

## 4. 파일 관계도

```
industry_matcher.py                         (백엔드 진입점, 변경 없음)
  └─ import match_business_code.py     ← 여기에 상수+hierarchy_fit()+5줄 추가
        │
        ├─ (동결) match_business_code_baseline_20260909.py   ← 롤백·대조 기준
        │
        ├─ 30_cache_experiment_inputs.py  ─┐
        ├─ 31_sweep_hierarchy.py          ─┤ 셋 다 23_..._v3.py의 함수를 import해서 재사용
        └─ 32_ab_rerank.py               ─┘ (구조화·검색·pool·재판정 로직은 한 벌만 존재)

데이터:
  data/processed/business_code_chroma_reference_v1.csv   후보 상세 (계층명 포함) — 그대로
  chroma_db/business_code_docs_2025/                     벡터 DB — 그대로
  data/outputs/exp_cache/                                30이 생성, 31·32가 소비 (신규)
  data/outputs/ab_rerank_*.json, sweep_hierarchy.json    31·32 결과 (신규)

정답셋:
  business_matching/gold_set_v2.csv   240건. 30이 입력으로 사용.
```

---

## 5. 롤백

플래그가 이미 `False`라 런타임은 v3와 동일하다. 코드까지 되돌리려면:

```
cp business_matching/match_business_code_baseline_20260909.py \
   business_matching/match_business_code.py
```

30/31/32와 `exp_cache/`는 남겨둬도 파이프라인에 영향 없음(호출되지 않음).
