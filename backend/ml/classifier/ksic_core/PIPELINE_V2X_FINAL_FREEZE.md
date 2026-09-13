# PIPELINE V2.X — FINAL FREEZE

## Final Version

    Pipeline V2.x
    Freeze date: 2026-09-13

## Development Benchmark

T1 (50 notices, development benchmark — no longer called "unseen final holdout"):

    35/50 = 70.0%

(Frozen V2 baseline was 34/50 = 68.0%, canonical/bug-free scoring.)

## Independent110

    83/110 = 75.5% (unchanged from Frozen V2 — zero regression)

## Components

| Component | State |
|---|---|
| Rule | Phase A evidence-role fixes (unchanged from Frozen V2) **+ one new colloquial-term entry** ("원전기업" → 35111/원자력 발전업) in `data/processed/ksic_index_terms.csv` |
| Whitelist | confidence-calibration gating (unchanged) |
| ML Gate | Champion (embed_rule, human+tune only) — `models/ml_gate_v2_champion.joblib` (unchanged) |
| Verifier | Candidate-verification design + evidence-role gate from the V2.1 attempt (kept; unchanged this round) |
| Resolver | Phase 2 (evidence-gated scope-first) (unchanged this round — a broader ambiguity-guard loosening was simulated and explicitly rejected, see `v2x_fix_candidate_analysis.md`) |
| Normalizer | `scope_policy.normalize_final_result()` (unchanged) |
| Evaluator | `scripts/29_score_professor_criteria.py::score_row()` + `ksic_core.hierarchy.is_same_industry()` (unchanged, reused as-is) |

## What changed from Frozen V2

Exactly one data-level addition: `data/processed/ksic_index_terms.csv` gained
one row mapping the colloquial term "원전기업" (nuclear-power company) to
KSIC 35111 (원자력 발전업). This is the same dictionary already used for
other informal industry terms (e.g. "화장품" → 20423) — no new mechanism,
no code-path change, no notice ID or Gold-code hardcoding. It affects
Rule's candidate generation only for texts that literally contain the
string "원전기업" — verified to be exactly 2 of the 160 development/
diagnostic texts (`PBLN_125902` in T1, `PBLN_125724` in Independent110).

A second candidate (loosening the Resolver's broad-sector/open-ended
ambiguity guard to guess a multi-industry answer instead of abstaining)
was simulated against stored data *before* touching any code and was
**rejected**: on Independent110, the Resolver's current abstentions are
already correct 19 times out of 20 — loosening the guard risked a much
larger regression there for a small T1 gain. This is documented in
`v2x_fix_candidate_analysis.md` as a deliberately-not-taken fix.

## Known limitations (unchanged from Frozen V2, carried forward honestly)

- `RESOLVER_FAILED_TO_RECOVER` (5 of T1's original 16 errors) and
  `RULE_CANDIDATE_MISS` (3 remaining) require Rule/Resolver recall
  improvements out of this round's safe, deterministic scope.
- `RESOLVER_FALSE_POSITIVE` (4 cases) and `ML_FALSE_KEEP` (1 case) hinge on
  LLM judgment reliability that a prompt-level evidence-role field cannot
  fully force — demonstrated repeatedly across this project's Resolver and
  Verifier evidence-gate work.
- `VERIFIER_FALSE_CONFIRM` (1 case, `PBLN_126301`) already has a code-level
  gate (from the V2.1 attempt) that is logically correct but did not
  change this specific case's real-LLM outcome in practice.
- LLM call-to-call non-determinism remains a known, previously-documented
  source of ±1-2 case noise on any given real run; this round's one
  structural change was, by design, isolated from that noise (only 2 of
  160 texts were re-called, both deterministically identified in advance).
- T1 (50 notices) is now formally the project's **development benchmark**,
  not an untouched final holdout — it has been analyzed and used to guide
  fixes across multiple rounds (V2.1 and this V2.x round). Any future
  claim of generalization should use a genuinely fresh sample.

## Status

```
MODEL DEVELOPMENT COMPLETE
READY FOR BACKEND INTEGRATION
```

## Entry point

```
ksic_core.predict.predict(text)
```

Single entry point, unchanged. Output schema unchanged (same keys as
Frozen V2 / `PIPELINE_V2_FREEZE.md`).

## Preserved artifacts

- `PIPELINE_V2_FREEZE.md`, `PIPELINE_CHAMPION_FREEZE.md`,
  `PIPELINE_V21_REJECTED.md`: preserved unchanged, not deleted.
- `models/ml_gate_v1_baseline.joblib`, `models/ml_gate_v2_challenger_B.joblib`,
  `models/ml_gate_v2_champion.joblib`: preserved unchanged.
- `data/통합_2073/최종검증/5차/ml_gate_final.joblib` (v1 original): preserved
  unchanged at its original path.

## Backend champion

```
PIPELINE_V2.x
```
