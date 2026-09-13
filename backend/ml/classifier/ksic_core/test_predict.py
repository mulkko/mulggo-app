# -*- coding: utf-8 -*-
"""predict.py 백엔드 API 스모크 테스트.

실행:  python -m ksic_core.test_predict

Gold 164건에서 사람 검수로 라벨이 안정적인 케이스만 골라, predict() 가
백엔드 계약(서비스범주 / 코드 유무 / needs_review / JSON 직렬화)을
지키는지 확인한다. 규칙 엔진 회귀는 ksic_core.smoke_test_rule_detectors 담당.
"""
from __future__ import annotations

import os

# 방어적 조치(2026-09-12f): predict()의 use_llm_fallback 기본값이 True로
# 바뀌면서, 이 스모크 테스트도 아무 인자 없이 predict()를 부른다 — 키를
# 먼저 무력화해 두지 않으면 CASES 중 코드없음/특정불가 케이스가 매번 실제
# LLM Resolver를 호출해 과금이 발생한다. 이 파일은 순수 회귀 스모크
# 테스트이므로 실제 API 호출 없이 도는 게 맞다.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import json
from pathlib import Path

import pandas as pd

from ksic_core.predict import predict, predict_batch

ROOT = Path(__file__).resolve().parent.parent


def _raw_texts() -> dict[str, str]:
    matches = [p for p in ROOT.rglob("full_raw_texts_1589.csv") if "__pycache__" not in p.parts]
    assert matches, "full_raw_texts_1589.csv 를 찾지 못했습니다."
    df = pd.read_csv(sorted(matches, key=lambda p: len(p.parts))[0], dtype=str, encoding="utf-8-sig").fillna("")
    return dict(zip(df["공고ID"], df["원문"]))


# (공고ID, 기대 service_category, 코드가_있어야_하나)
CASES = [
    # 2026-09-12c: PBLN_125844(직접 KSIC 표, 후보 34개)는 candidate_count>=20
    # 구조이상(table_reference_anomaly) 하드게이트로 UNRESOLVED_REVIEW/전업종노출로
    # 바뀌는 게 맞는 동작이다(90개 코드 오탐 버그와 같은 유형, scope_policy.py 참고).
    ("PBLN_000000000125844", "전업종노출", False),
    ("PBLN_000000000125475", "특정업종대상", True),   # 대분류 C (제조업)
    ("PBLN_000000000118207", "특정업종대상", True),   # 복수산업 011|012|03 (농업)
    ("PBLN_000000000120282", "전업종노출", False),    # 업종무관
    ("PBLN_000000000121366", "전업종노출", False),    # 업종무관
    ("PBLN_000000000125673", "전업종노출", False),    # 특정불가
    ("PBLN_000000000125300", "전업종노출", False),    # 근거 없음 (None 결과)
]


def run() -> None:
    texts = _raw_texts()

    for gid, want_cat, want_codes in CASES:
        assert gid in texts, f"{gid} 원문 없음"
        out = predict(texts[gid])
        assert out["service_category"] == want_cat, (
            f"{gid}: service_category {out['service_category']} != {want_cat}"
        )
        assert bool(out["ksic_codes"]) == want_codes, (
            f"{gid}: 코드유무 {bool(out['ksic_codes'])} != {want_codes} ({out['ksic_codes']})"
        )
        assert len(out["ksic_codes"]) == len(out["ksic_names"]), f"{gid}: 코드/업종명 길이 불일치"
        # 계약: JSON 직렬화 가능
        json.dumps(out)
        # 계약: 필수 키
        for k in ("service_category", "ksic_codes", "ksic_names", "stage",
                  "confidence", "needs_review", "excluded", "evidence", "schema_version"):
            assert k in out, f"{gid}: 키 누락 {k}"

    # 특정업종대상이면 needs_review 여부와 무관하게 코드가 있어야 한다
    specific = predict(texts["PBLN_000000000118207"])
    assert specific["service_category"] == "특정업종대상" and specific["ksic_codes"]

    # 구조이상(후보 20개+)은 needs_review와 무관하게 코드가 비어야 한다(불변조건 §3)
    anomaly = predict(texts["PBLN_000000000125844"])
    assert anomaly["scope_decision"] == "UNRESOLVED_REVIEW" and not anomaly["ksic_codes"]
    assert len(anomaly["candidate_ksic_codes"]) >= 20  # 원본 후보는 감사용으로 보존

    # 빈 입력 / 공백 입력 → 전업종노출 + 검토 필요, 크래시 없음
    for empty in ("", "   \n  ", None):
        out = predict(empty)  # type: ignore[arg-type]
        assert out["service_category"] == "전업종노출"
        assert out["ksic_codes"] == []
        assert out["needs_review"] is True

    # batch = 개별 호출과 동일
    ids = [c[0] for c in CASES]
    batch = predict_batch([texts[i] for i in ids])
    assert [b["service_category"] for b in batch] == [predict(texts[i])["service_category"] for i in ids]

    print(f"OK - predict 스모크 테스트 통과 ({len(CASES)} Gold 케이스 + 빈입력 + batch)")


if __name__ == "__main__":
    run()
