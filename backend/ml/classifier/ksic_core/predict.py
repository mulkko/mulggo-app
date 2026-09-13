# -*- coding: utf-8 -*-
"""공고 원문 → 업종 판정 백엔드 API.

백엔드가 부르는 유일한 진입점.

    from ksic_core.predict import predict
    out = predict(공고원문)          # dict, JSON 직렬화 보장

CLI:
    echo "<원문>" | python -m ksic_core.predict
    python -m ksic_core.predict --file 공고.txt
    python -m ksic_core.predict --batch in.csv --out out.csv   # in.csv 컬럼: 공고ID, 원문

판정 로직 자체는 ksic_core.decide_industry (규칙 엔진). 이 모듈은 그 결과를
백엔드가 쓰기 좋은 평평한 JSON 스키마로 정리하고 서비스 이진범주를 붙인다.
"""
from __future__ import annotations

import json
import sys

from ksic_core.decide_industry import decide_industry, needs_human_review
from ksic_core import orchestrator, scope_policy

SCHEMA_VERSION = "2026-09-12e"

# 서비스 이진범주 매핑. scripts/22_build_notice_dataset.py 와 동일 기준.
# (KPI 재채점 재현_결과_개정기준.md 도 같은 정의)
_SPECIFIC_STAGES = {"대분류", "중분류", "소분류", "세분류", "세세분류", "복수산업"}


def _clean_excluded(items) -> list[dict]:
    out = []
    for x in items or []:
        if isinstance(x, dict):
            out.append(
                {
                    "code": (str(x.get("코드")).strip() or None) if x.get("코드") else None,
                    "name": (str(x.get("명칭") or x.get("업종명") or "").strip() or None),
                    "type": (str(x.get("유형") or "").strip() or None),
                }
            )
        else:
            s = str(x).strip()
            if s:
                out.append({"code": None, "name": s, "type": None})
    return out


def predict(text: str, *, use_llm_fallback: bool = True) -> dict:
    """공고 원문 1건 → 업종 판정.

    Returns (모든 값 JSON 직렬화 가능):
      service_category : "특정업종대상" | "전업종노출"
          특정업종대상 = 신뢰할 KSIC 코드를 확정  → 해당 업종 + 계층에만 노출
          전업종노출  = 특정 업종 확정 불가        → 모든 업종에 노출 (누락 방지)
      ksic_codes    : list[str]  확정 KSIC (대분류 알파벳 ~ 세세분류 5자리 혼재 가능)
      ksic_names    : list[str]  각 코드 업종명 (ksic_codes 와 같은 길이)
      stage         : "세세분류"|"복수산업"|"업종무관"|"특정불가"|"확인필요(국세청1:N)"|""
      confidence    : "HIGH"|"MED"|"LOW"|""   (=match_strength) 매칭 강도. 실제 정답
                      확률이 아니므로 자동확정 판단에는 쓰지 말 것 — needs_review 참고.
      match_strength: confidence와 동일 값(별칭). 의미를 명확히 하려고 추가.
      scope_decision: "SPECIFIC"|"ALL_INDUSTRIES"|"UNRESOLVED_REVIEW"  최종(orchestration
        이후) 판정. ksic_codes/service_category와 절대 모순되지 않는다(아래 불변조건).
      scope_verified: bool  Rule+Whitelist 단계에서 근거가 충분히 검증됐는가(진단용)
      final_confidence: "HIGH"|"MED"|"LOW"|""  재보정된 신뢰도(자동확정 판단 기준)
      needs_review  : bool  자동확정 불가 → 사람 확인 권장 (= not auto_accept_eligible)
      auto_accept_eligible: bool  사람 검토 없이 자동확정해도 되는가(최종값)
      candidate_ksic_codes/candidate_ksic_names: Rule이 원래 제안했던 후보(감사용).
        ML/LLM이 기각했으면 ksic_codes와 달라질 수 있다 — 최종 확정값과 혼동 금지.
      candidate_source: 최종 ksic_codes의 출처 provenance — "RULE"(Rule이 처음
        만듦 또는 코드 없음) | "RULE_VERIFIED_BY_ML"(ML이 Rule 후보를 KEEP) |
        "RULE_VERIFIED_BY_LLM"(Candidate Verifier가 Rule 후보를 SUPPORTED로
        확인) | "LLM_RESOLVER"(Resolver가 새로 찾음).
      excluded      : list[{code,name,type}]  공고가 명시한 제외 업종
      evidence      : 판정 근거 (dict 또는 str)
      schema_version: str

      document_sufficient/attachment_missing/structural_anomaly: 문서 완전성 신호
      ml_model_name/ml_status/ml_valid_probability/ml_decision: ML Gate 결과
        (ml_status: NOT_RUN|RUN|UNAVAILABLE|ERROR, ml_decision: KEEP_SPECIFIC|
        REJECT_SPECIFIC|UNCERTAIN|null)
      llm_status/llm_decision/llm_verified_codes/llm_verified_names/
      llm_evidence_quote/llm_reason/llm_candidate_consistent/llm_raw_confidence/
      llm_verdicts_detail/llm_suggested_refinement:
        LLM **Candidate Verifier** 결과 (llm_status: NOT_RUN|RUN|UNAVAILABLE|ERROR).
        Rule 후보만 검증한다 — llm_verified_codes는 항상 Rule 후보의 부분집합.
      resolver_status/resolver_decision/resolver_ksic_codes/resolver_ksic_names/
      resolver_evidence/resolver_reason:
        LLM **Fallback Resolver** 결과 (resolver_status: NOT_RUN|RUN|UNAVAILABLE|
        ERROR, resolver_decision: SINGLE_INDUSTRY|MULTI_INDUSTRY|
        UNRESOLVED_REVIEW|null). Rule/ML/Verifier가 실패했을 때만 호출되며,
        KSIC 마스터 전체를 대상으로 새 코드를 찾을 수 있다.
      final_reason: orchestration이 이 결론에 도달한 사유 태그

      최종 상태 불변조건(scope_policy.normalize_final_result):
        scope_decision==ALL_INDUSTRIES     -> ksic_codes==[] and ksic_names==[]
        scope_decision==SPECIFIC           -> len(ksic_codes)>=1
        scope_decision==UNRESOLVED_REVIEW  -> ksic_codes==[] (원 후보는 candidate_ksic_codes)
        auto_accept_eligible==True         -> needs_review==False, scope_decision!=UNRESOLVED_REVIEW

      scope_decision/service_category/ksic_codes/ksic_names/needs_review/
      auto_accept_eligible은 규칙+화이트리스트만이 아니라
      ksic_core.orchestrator의 ML Gate/LLM Verifier/Resolver 결과까지 반영한
      최종값이다(ksic_core/orchestrator.py, scope_policy.normalize_final_result
      참고). Whitelist를 통과하지 못하면 ML/LLM이 뭐라 하든 needs_review는
      계속 True — ML/LLM은 새 자동확정 통로가 아니라 검토 큐로 보낼 최종
      코드셋을 다듬거나(Verifier), 최후 수단으로 새로 찾을(Resolver) 뿐이다.
      rule-only 결과가 필요하면 decide_industry()를 직접 호출한다(평가용).

      2026-09-12: confidence==HIGH 자동확정 정책을 폐기했다. 독립홀드아웃
      실측에서 confidence==HIGH인 특정업종 확정의 정확도가 53.1%로, MED(96.0%)
      /LOW(100.0%)보다 오히려 낮았다(scope_policy.py 참고). 지금은
      auto_accept_eligible(=scope_policy가 계산한 final_confidence 기반
      화이트리스트)이 자동확정 여부를 결정한다. confidence/stage 필드 자체는
      하위호환을 위해 그대로 남겨뒀다.

      2026-09-12e: "Rule/ML/Verifier가 후보를 못 찾거나 기각했다"는 더 이상
      그 자체로 ALL_INDUSTRIES 확정 근거가 아니다(이전엔 그랬음 — 실제
      "특정 후보 기각"과 "업종무관 확정"을 혼동한 버그였다). 이제 그런 경우엔
      LLM Fallback Resolver에게 최후 기회를 주고, 그마저 못 찾으면
      UNRESOLVED_REVIEW로 보낸다. 순수 Rule 판정으로 명시적 "전 업종"/
      "업종무관" 근거를 찾은 경우만 ALL_INDUSTRIES가 유지된다.

    use_llm_fallback: 기본 False. **2026-09-12e부터 의미가 바뀌었다** — 더 이상
        decide_industry() 내부의 legacy LLM fallback을 켜는 인자가 아니라(그
        경로는 predict()에서 항상 비활성이다, 아래 참고), orchestrator의
        Candidate Verifier/Fallback Resolver가 **실제 API를 호출해도 되는지**를
        게이팅한다. False면 OPENAI_API_KEY가 설정돼 있어도 실제 호출이 전혀
        나가지 않는다(llm_status/resolver_status가 NOT_RUN으로 남음).

        **기본값은 2026-09-12f부터 True다** — 사용자 요청으로 predict() 단건
        호출은 기본적으로 실제 LLM(Verifier/Resolver)을 쓴다. 이는 명시적
        요청에 따른 변경이며, `OPENAI_API_KEY`/`GOOGLE_API_KEY`가 설정돼
        있으면 ML이 UNCERTAIN/REJECT를 내거나 Rule이 후보를 못 찾는 공고마다
        실제 과금 호출이 나갈 수 있다는 뜻이다. 키가 없으면 여전히 예외 없이
        `UNAVAILABLE`로 안전하게 처리된다.

        **`predict_batch()`는 의도적으로 기본값을 `False`로 남겨뒀다** — 배치는
        한 번에 수백~수천 건이 돌 수 있어 기본값을 켜두면 대량 과금 위험이
        지나치게 크다(비대칭 설계, 실수 방지). 배치에서도 실제 LLM을 쓰려면
        `predict_batch(texts, use_llm_fallback=True)`처럼 명시적으로 켜야 한다.
        CLI(`--llm`)도 `args.llm`을 항상 명시적으로 넘기므로 이 기본값 변경과
        무관하게 그대로 동작한다(플래그 없으면 여전히 실제 호출 없음).
    """
    # decide_industry()에는 항상 use_llm_fallback=False를 전달한다 — 그 내부의
    # legacy LLM fallback(match_ksic_by_llm 직접 호출)은 predict() 경로에서
    # 완전히 봉인됐다. LLM 개입은 이제 아래 orchestrator.orchestrate() 안의
    # Candidate Verifier/Fallback Resolver 두 갈래로만 일어난다 — 그래야
    # "legacy LLM → ML → LLM Verifier"처럼 한 요청 안에서 LLM이 중복 호출되는
    # 경로가 생기지 않는다(2026-09-12e 리팩터링). decide_industry(text,
    # use_llm_fallback=True)를 직접 호출하는 기존 스크립트(scripts/06,07,08 등)는
    # 이 변경의 영향을 받지 않는다 — predict()를 거치지 않기 때문이다.
    result = decide_industry(
        text or "", use_llm_fallback=False, return_scope_result=True
    )

    if not result:
        scope = scope_policy.build_scope_fields(None)
        out = {
            "service_category": "전업종노출",
            "ksic_codes": [],
            "ksic_names": [],
            "stage": "",
            "confidence": "",
            "match_strength": scope["match_strength"],
            "scope_decision": scope["scope_decision"],
            "scope_verified": scope["scope_verified"],
            "final_confidence": scope["final_confidence"],
            "needs_review": True,
            "auto_accept_eligible": scope["auto_accept_eligible"],
            "excluded": [],
            "evidence": None,
            "schema_version": SCHEMA_VERSION,
        }
    else:
        codes = [str(c).strip() for c in (result.get("확정코드") or []) if str(c).strip()]
        names = [str(n).strip() for n in (result.get("확정업종명") or []) if str(n).strip()]
        stage = str(result.get("확정단계") or "")
        specific = bool(codes) and stage in _SPECIFIC_STAGES
        out = {
            "service_category": "특정업종대상" if specific else "전업종노출",
            "ksic_codes": codes,
            "ksic_names": names,
            "stage": stage,
            "confidence": str(result.get("ksic_confidence") or ""),
            "match_strength": str(result.get("match_strength") or result.get("ksic_confidence") or ""),
            "scope_decision": result.get("scope_decision") or scope_policy.SCOPE_ALL_INDUSTRIES,
            "scope_verified": bool(result.get("scope_verified")),
            "final_confidence": str(result.get("final_confidence") or ""),
            "needs_review": bool(needs_human_review(result)),
            "auto_accept_eligible": bool(result.get("auto_accept_eligible")),
            "excluded": _clean_excluded(result.get("제외업종")),
            "evidence": result.get("근거"),
            "schema_version": SCHEMA_VERSION,
        }

    # --- orchestration: Whitelist 미통과 특정업종 후보는 ML Gate/LLM Verifier로 ---
    # (2026-09-12c) scope_decision/service_category/ksic_codes/ksic_names/
    # needs_review/auto_accept_eligible은 이제 규칙+화이트리스트만이 아니라 이
    # orchestration 결과를 반영한 "최종" 값이다 — 전부 orchestrator.orchestrate()
    # 안의 scope_policy.normalize_final_result() 한 곳에서만 조립되므로
    # "SPECIFIC인데 ksic_codes==[]" 같은 모순이 나올 수 없다. rule-only 결과가
    # 필요하면 ksic_core.decide_industry()를 직접 호출할 것(평가 스크립트용).
    # Rule이 원래 제안했던 후보는 candidate_ksic_codes/candidate_ksic_names에
    # 감사용으로 그대로 남는다(최종 ksic_codes와 다를 수 있음).
    orch = orchestrator.orchestrate(text or "", result, use_llm_fallback=use_llm_fallback)
    out["service_category"] = orch["service_category"]
    out["scope_decision"] = orch["scope_decision"]
    out["ksic_codes"] = orch["ksic_codes"]
    out["ksic_names"] = orch["ksic_names"]
    out["candidate_ksic_codes"] = orch["candidate_ksic_codes"]
    out["candidate_ksic_names"] = orch["candidate_ksic_names"]
    out["candidate_source"] = orch["candidate_source"]
    out["auto_accept_eligible"] = orch["auto_accept_eligible"]
    out["needs_review"] = bool(orch["needs_human_review"])
    out["final_reason"] = orch["final_reason"]
    out["document_sufficient"] = orch["document_sufficient"]
    out["attachment_missing"] = orch["attachment_missing"]
    out["structural_anomaly"] = orch["structural_anomaly"]
    out["ml_model_name"] = orch["ml_model_name"]
    out["ml_status"] = orch["ml_status"]
    out["ml_valid_probability"] = orch["ml_valid_probability"]
    out["ml_decision"] = orch["ml_decision"]
    out["llm_status"] = orch["llm_status"]
    out["llm_decision"] = orch["llm_decision"]
    out["llm_verified_codes"] = orch["llm_verified_codes"]
    out["llm_verified_names"] = orch["llm_verified_names"]
    out["llm_evidence_quote"] = orch["llm_evidence_quote"]
    out["llm_reason"] = orch["llm_reason"]
    out["llm_candidate_consistent"] = orch["llm_candidate_consistent"]
    out["llm_raw_confidence"] = orch["llm_raw_confidence"]
    # (2026-09-12d) LLM은 candidate verifier로만 동작한다 — 후보별 SUPPORTED/
    # UNSUPPORTED/UNCERTAIN 판정 상세와, 후보 밖에서 LLM이 참고로 제안한(자동
    # 채택 안 됨) 세분화/신규 코드는 아래 두 필드로만 노출된다. llm_suggested_
    # refinement의 코드는 ksic_codes/candidate_ksic_codes 어디에도 섞이지 않는다.
    out["llm_verdicts_detail"] = orch["llm_verdicts_detail"]
    out["llm_suggested_refinement"] = orch["llm_suggested_refinement"]
    # (2026-09-12e) LLM Fallback Resolver 결과 — Rule/ML/Verifier가 전부
    # 실패했을 때만 호출된다. resolver_ksic_codes가 최종 ksic_codes로 채택된
    # 경우 candidate_source=="LLM_RESOLVER"로 표시된다(위 참고).
    out["resolver_status"] = orch["resolver_status"]
    out["resolver_decision"] = orch["resolver_decision"]
    out["resolver_ksic_codes"] = orch["resolver_ksic_codes"]
    out["resolver_ksic_names"] = orch["resolver_ksic_names"]
    out["resolver_evidence"] = orch["resolver_evidence"]
    out["resolver_reason"] = orch["resolver_reason"]

    # JSON 직렬화 보장 (근거 dict 안에 비직렬화 값이 섞여도 안전)
    return json.loads(json.dumps(out, ensure_ascii=False, default=str))


def predict_batch(texts, *, use_llm_fallback: bool = False) -> list[dict]:
    return [predict(t, use_llm_fallback=use_llm_fallback) for t in texts]


def _cli(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="공고 원문 → 업종 판정")
    ap.add_argument("--file", help="원문 텍스트 파일 1건")
    ap.add_argument("--batch", help="입력 CSV (컬럼: 공고ID, 원문)")
    ap.add_argument("--out", help="--batch 결과 CSV 저장 경로")
    ap.add_argument("--llm", action="store_true", help="규칙 실패 시 LLM fallback 사용")
    args = ap.parse_args(argv)

    if args.batch:
        import pandas as pd

        df = pd.read_csv(args.batch, dtype=str, encoding="utf-8-sig").fillna("")
        if "원문" not in df.columns:
            print("입력 CSV에 '원문' 컬럼이 필요합니다.", file=sys.stderr)
            return 2
        preds = predict_batch(df["원문"].tolist(), use_llm_fallback=args.llm)
        df["service_category"] = [p["service_category"] for p in preds]
        df["ksic_codes"] = ["|".join(p["ksic_codes"]) for p in preds]
        df["ksic_names"] = ["|".join(p["ksic_names"]) for p in preds]
        df["stage"] = [p["stage"] for p in preds]
        df["confidence"] = [p["confidence"] for p in preds]
        df["needs_review"] = [p["needs_review"] for p in preds]
        out_path = args.out or "predict_batch_out.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        n_spec = sum(p["service_category"] == "특정업종대상" for p in preds)
        print(f"{len(df)}건 처리 → {out_path}  (특정업종대상 {n_spec} / 전업종노출 {len(df) - n_spec})")
        return 0

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    print(json.dumps(predict(text, use_llm_fallback=args.llm), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
