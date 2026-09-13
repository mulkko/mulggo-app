# -*- coding: utf-8 -*-
"""ML Gate runtime — Whitelist를 통과 못한 Rule의 특정업종 후보가 실제
지원대상 업종으로 유효한지 이진 판정한다.

역할 경계(변경 금지):
- KSIC 코드를 새로 만들지 않는다. Rule이 이미 만든 ksic_codes/ksic_names를
  유지(KEEP_SPECIFIC)하거나 폐기(REJECT_SPECIFIC)할 뿐이다.
- 후보가 없는 공고에는 호출하지 않는다(orchestrator가 호출 전 가드).

scripts/48(모델비교)+49(선택·저장)가 만든 joblib 아티팩트를 로드한다.
아티팩트가 없거나 로드 실패해도 서비스는 죽지 않고 ``ml_status=UNAVAILABLE``.

[2026-09-13 Pipeline V2] Champion/Challenger 비교(scripts/70, 71) 후
``models/ml_gate_v2_champion.joblib``(embed_rule, human+tune만 학습, Phase A
Rule evidence-role 수정 반영)을 챔피언으로 채택했다. 기존 v1(embed-only)
아티팩트는 ``data/통합_2073/최종검증/5차/ml_gate_final.joblib``에 원본 그대로
보존돼 있고, ``models/ml_gate_v1_baseline.joblib``에도 동일 사본이 있다 —
롤백하려면 ARTIFACT_PATH만 그 경로로 되돌리면 된다(코드/threshold 변경 불필요).
"""
from __future__ import annotations

import os

import numpy as np

ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "ml_gate_v2_champion.joblib"
)
# V1 baseline(embed-only) — 항상 보존, 롤백용. 삭제/덮어쓰기 금지.
V1_BASELINE_ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "통합_2073", "최종검증", "5차", "ml_gate_final.joblib"
)

# 개발/튜닝 표본에서 결정한 값(scripts/49 리포트 참고). holdout/T1을 보고 고치지 않는다.
ML_KEEP_THRESHOLD = 0.80
ML_REJECT_THRESHOLD = 0.20

_artifact = None
_load_error: str | None = None
_embedder = None
_embedder_name = None


def _load_artifact():
    global _artifact, _load_error
    if _artifact is not None or _load_error is not None:
        return
    try:
        import joblib
        _artifact = joblib.load(ARTIFACT_PATH)
    except Exception as e:  # noqa: BLE001
        _load_error = f"{type(e).__name__}: {e}"


def _get_embedder(model_name: str):
    global _embedder, _embedder_name
    if _embedder is not None and _embedder_name == model_name:
        return _embedder
    try:
        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        from sentence_transformers import SentenceTransformer
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _embedder = SentenceTransformer(model_name, device=device)
        _embedder_name = model_name
    except Exception:  # noqa: BLE001
        _embedder = None
    return _embedder


def _rule_feature_row(text: str, rule_result: dict | None) -> dict:
    """live 원문/rule 결과로 notice_v2.csv와 최대한 같은 모양의 피처 1행을 만든다.

    표1유형/표2유형/추출상태는 오프라인 파일추출 단계(HWP/PDF 파싱) 메타데이터라
    predict() 시점의 순수 텍스트만으로는 재현 불가 — 중립 placeholder로 채운다
    (OneHotEncoder(handle_unknown='ignore')라 학습 시 못 본 값이어도 안전하게
    무시됨. scripts/45의 '근사치 주의' 메모와 같은 종류의 근사).
    """
    from ksic_core.span_extract import extract_industry_spans

    result = rule_result or {}
    codes = result.get("확정코드") or []
    spans = extract_industry_spans(text)
    label_counts = {lab: 0 for lab in ["지원대상", "지원제외", "제외예외", "제3자", "참고예시", "무관"]}
    for s in spans:
        lab = s.get("span_label")
        if lab in label_counts:
            label_counts[lab] += 1
    n_trig_code = sum(1 for s in spans if str(s.get("트리거유형", "")).endswith("code"))

    row = {
        "rule_stage": str(result.get("확정단계") or ""),
        "rule_conf": str(result.get("ksic_confidence") or ""),
        "rule_status": str(result.get("ksic_status") or result.get("확정단계") or ""),
        "표1유형": "unknown", "표2유형": "unknown", "추출상태": "unknown",
        "rule_n_codes": len(codes),
        "rule_has_excluded": int(bool(result.get("제외업종"))),
        "원문길이": len(text or ""),
        "n_spans": len(spans),
        "n_trig_code": n_trig_code,
        "has_support_span": int(label_counts["지원대상"] > 0),
    }
    for lab, cnt in label_counts.items():
        row[f"n_{lab}"] = cnt
    return row


def run_ml_gate(text: str, rule_result: dict | None, evidence_window_text: str | None = None) -> dict:
    _load_artifact()
    if _load_error is not None:
        return {
            "ml_model_name": None, "ml_status": "UNAVAILABLE",
            "ml_valid_probability": None, "ml_decision": None,
            "ml_unavailable_reason": _load_error,
        }

    art = _artifact
    model_name = art.get("model_name", "unknown")
    try:
        feature_mode = art["feature_mode"]
        parts = []

        if feature_mode in ("rule", "embed_rule"):
            import pandas as pd
            from scipy.sparse import hstack, csr_matrix
            from ksic_core.notice_gate import CAT_COLS, NUM_COLS
            row = _rule_feature_row(text, rule_result)
            d = pd.DataFrame([row])
            Xcat = art["ohe"].transform(d[CAT_COLS].astype(str).values)
            Xnum = csr_matrix(((d[NUM_COLS] - art["num_mean"]) / art["num_std"]).values)
            parts.append(hstack([Xcat, Xnum]).toarray())

        if feature_mode in ("embed", "embed_rule"):
            embedder = _get_embedder(art["embed_model_name"])
            if embedder is None:
                return {
                    "ml_model_name": model_name, "ml_status": "UNAVAILABLE",
                    "ml_valid_probability": None, "ml_decision": None,
                    "ml_unavailable_reason": "임베딩 모델 로드 실패(오프라인/패키지 없음)",
                }
            window = evidence_window_text
            if window is None:
                from ksic_core import scope_policy
                window = scope_policy.evidence_window(text, rule_result)
            parts.append(embedder.encode([window], show_progress_bar=False))

        if not parts:
            return {
                "ml_model_name": model_name, "ml_status": "ERROR",
                "ml_valid_probability": None, "ml_decision": None,
                "ml_unavailable_reason": f"알 수 없는 feature_mode: {feature_mode}",
            }

        X = np.hstack(parts) if len(parts) > 1 else parts[0]
        clf = art["clf"]
        proba = clf.predict_proba(X)[0]
        p_specific = float(proba[list(clf.classes_).index(1)])

        if p_specific >= ML_KEEP_THRESHOLD:
            decision = "KEEP_SPECIFIC"
        elif p_specific <= ML_REJECT_THRESHOLD:
            decision = "REJECT_SPECIFIC"
        else:
            decision = "UNCERTAIN"

        return {
            "ml_model_name": model_name, "ml_status": "RUN",
            "ml_valid_probability": p_specific, "ml_decision": decision,
            "ml_unavailable_reason": "",
        }
    except Exception as e:  # noqa: BLE001 — 서비스가 ML 오류로 죽으면 안 됨
        return {
            "ml_model_name": model_name, "ml_status": "ERROR",
            "ml_valid_probability": None, "ml_decision": None,
            "ml_unavailable_reason": f"{type(e).__name__}: {e}",
        }
