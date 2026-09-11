# 실험: Soft Hierarchy Reranking (2026-09-09)

후보 pool 정렬에 **계층 적합성 soft 신호** 하나를 플래그로 얹는다.
v3 아키텍처·검색·프롬프트·반환 스키마 불변. `USE_HIERARCHY_RERANK = False` 가 기본이며
이때 정렬 결과는 v3와 **완전히 동일**(검증 완료).

논문 근거: 병목은 검색(pool recall 97.5%)이 아니라 최종 재판정. 미국 Census BEACON 이
NAICS 를 2자리→6자리로 계층적으로 좁힌다(선례). 우리는 hard filter 없이 순위 가감만.

---

## 파일

| 파일 | 역할 | 비용 |
|---|---|---|
| `business_matching/match_business_code_baseline_20260909.py` | v3 동결본. **수정 금지.** 롤백·대조용. | — |
| `business_matching/match_business_code.py` | 상수 블록 + `hierarchy_fit()` + `build_candidate_pool()` 5줄. 플래그 기본 off. | — |
| `business_matching/30_cache_experiment_inputs.py` | 구조화+임베딩 240건 캐시 → `data/outputs/exp_cache/` | **~$0.37 (1회)** |
| `business_matching/31_sweep_hierarchy.py` | 캐시 위에서 계층 신호가 pool 순위에 주는 효과를 상수별로 측정 | **$0** |
| `business_matching/32_ab_rerank.py` | 최적 config 로 A/B 재판정 → 최종 Top-1 비교 | **~$1.5/실행** |

변경된 v3 diff: 순수 추가 103줄, 수정 2줄 (`build_candidate_pool` 정렬 키).

---

## 실행 순서

### 0. 사전 (기존 패키지 셋업이 끝나 있으면 생략)

```
pip install -r requirements.txt        # numpy 추가됨
# .env 에 OPENAI_API_KEY (크레딧 $5 이상 권장)
python -c "from industry_matcher import health; print(health())"
```

### 1. 캐시 생성 — 유료 (~$0.37)

먼저 소액 점검:
```
python business_matching/30_cache_experiment_inputs.py --limit 5
```
정상이면 전체:
```
python business_matching/30_cache_experiment_inputs.py
```
- 중단돼도 재실행하면 남은 건만 처리 (10건마다 체크포인트).
- 산출: `data/outputs/exp_cache/{structuring.json, query_emb.npz, fulltext_emb.npz, hier_emb.npz}`

### 2. 무비용 스윕 — $0. **여기서 채택 여부의 1차 판단이 갈린다.**

```
python business_matching/31_sweep_hierarchy.py
```
출력에서 볼 것:
- **`회귀 검증: PASS`** — 플래그 off 가 v3 원본과 pool 순위 동일한지 (FAIL 이면 코드 문제, 진행 중단).
- **`recall@20`** 과 **`→win20`** (정답이 재판정 창 20 안으로 새로 들어온 건수).
  - baseline 대비 개선 없음 & `→win20 ≤ ←win20` → **계층 신호 효과 없음. 여기서 $0.37 쓰고 종료.**
  - 개선 있음 → 스크립트가 `=> 32번에 넘길 config:` 로 인자를 출력한다.

### 3. A/B 재판정 — 유료

배관 점검 (무비용):
```
python business_matching/32_ab_rerank.py --dry-run --limit 8
```
소액 실측 ($0.05):
```
python business_matching/32_ab_rerank.py --limit 8 --yes
```
본 실행 (31번이 알려준 config 로. 예: B1 / overlap 0.34 / bonus -4):
```
python business_matching/32_ab_rerank.py --variant B1 --overlap 0.34 --bonus -4 --repeats 2 --yes
```
- `--repeats 2` = A·B 각 2회 (재판정 LLM 비결정성 대비). 240×2×2 ≈ **$3.0**.
- 예산이 빠듯하면 `--repeats 1` (≈ $1.5) 먼저.
- 산출: `data/outputs/ab_rerank_*.json` + 콘솔에 비교표·개선/악화 케이스·최종 판정.

---

## 채택 / 폐기 기준 (32번이 자동 출력)

| 결과 | 판정 |
|---|---|
| Top-1 중앙값 하락(≤ −0.5%p) 또는 악화 ≥ 개선 | **폐기** — `USE_HIERARCHY_RERANK = False` 유지 (이미 기본값) |
| Top-1 +2%p 이상 또는 제조↔도소매 혼동 감소 | **채택 후보** — `--repeats` 늘려 재확인 후 True 로 |
| Top-1 ±1~2%p, 방향 불명확 | **애매** — gold_v2 순환성상 판별 불가. 비순환 평가셋 42→100건 확장 논의 |

**폐기해도 비용 0:** 플래그는 이미 off, 동결본 그대로.

---

## 롤백

```
# 코드 전체를 v3 원본으로:
cp business_matching/match_business_code_baseline_20260909.py \
   business_matching/match_business_code.py
```
또는 그냥 `USE_HIERARCHY_RERANK = False` (기본값) 두면 런타임 `match_business_code()` 는 v3와 동일하게 동작한다.

---

## 검증 완료 항목 (코드 작성 시점)

- `23_..._v3.py` 컴파일 OK
- 플래그 OFF → `build_candidate_pool` 정렬 결과가 동결본과 **바이트 동일** (합성 데이터)
- 플래그 ON → 순위 바뀜, 후보 개수 불변(제거 없음), `hierarchy_fit` 반환 정상
- `31_sweep_hierarchy.py` → 실제 Chroma DB 대상 end-to-end 실행 OK, 회귀검증 PASS 출력
- `32_ab_rerank.py --dry-run` → A/B 배관·비용추정·판정 로직 OK

미검증(크레딧 필요): 실제 gold_v2 240건 수치. → 위 1~3단계가 그것.
