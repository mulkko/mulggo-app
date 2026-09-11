"""
38_eval_pipeline.py — 개정 계획서 §10.5 E안 + §10.6 지표, 문헌 기준(docs/평가근거_문헌표.md §2) 대조.

전체 파이프라인(match_business_code)을 골든셋에 돌려 측정:
  Top-1 / Recall@3 / MRR@pool / result_state 분포 / 상태별 실측 정확도
  · expected_primary 가 빈 행(정보부족) = "정보_추가_필요" 로 나오면 정답
문헌 대조:
  추천_가능 비중 ~55% (Census) / 추천_가능 버킷 정확도 ≥90% / 전체 Top-1 65~80% 밴드

사용:
    python business_matching/38_eval_pipeline.py --gold business_matching/gold_set_v3.csv
    python business_matching/38_eval_pipeline.py --gold business_matching/gold_set_v1.csv --limit 10
전제: .env 에 OPENAI_API_KEY + EMBEDDING_MODEL(bge-m3 권장), 해당 인덱스 존재.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SD = Path(__file__).resolve().parent
PROJECT_ROOT = SD.parent
OUT_DIR = PROJECT_ROOT / "data" / "outputs"

_spec = importlib.util.spec_from_file_location("m23", SD / "23_match_business_code_v3.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["m23"] = m
_spec.loader.exec_module(m)

AUTO_STATE = "추천_가능"


def parse_offline(v: str):
    v = str(v).strip().lower()
    if v in ("true", "1", "예", "y", "o"):
        return True
    if v in ("false", "0", "아니오", "n", "x"):
        return False
    return None


def targets(row) -> list[str]:
    out = [str(row.get("expected_primary", "") or "").strip()]
    alt = str(row.get("expected_alt", "") or "").strip()
    if alt and alt.lower() != "nan":
        out += [c.strip() for c in alt.split(";") if c.strip()]
    return [c for c in out if c and c.lower() != "nan"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=SD / "gold_set_v1.csv")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    gold = pd.read_csv(args.gold, dtype=str, encoding="utf-8-sig").fillna("")
    if args.limit:
        gold = gold.head(args.limit)

    per: list[dict] = []
    for _, r in gold.iterrows():
        tgt = targets(r)
        none_case = len(tgt) == 0
        try:
            res = m.match_business_code(
                r["seed"], r["problem"], r["solution"],
                is_offline_store=parse_offline(r.get("is_offline_store", "")),
            )
        except Exception as e:  # noqa: BLE001
            per.append({"id": r["id"], "error": str(e)[:120]})
            print(f"[{r['id']}] 오류: {e}")
            continue

        rep = res["representative_business"]
        pool_codes = [c["business_code"] for c in res["activity_results"][0]["candidate_pool"]]
        pred = rep["business_code"]
        alts = [a["business_code"] for a in rep["alternatives"]]
        rank = next((i for i, c in enumerate(pool_codes, 1) if c in tgt), None)

        row = {
            "id": r["id"], "category": r.get("category", ""),
            "targets": tgt, "none_case": none_case,
            "pred": pred, "pred_name": rep["business_name"],
            "state": rep["result_state"], "confidence": rep["confidence"],
            "top1": (not none_case) and pred in tgt,
            "recall3": (not none_case) and (pred in tgt or any(a in tgt for a in alts[:2])),
            "pool_rank": rank,
            "none_ok": none_case and rep["result_state"] == "정보_추가_필요",
        }
        per.append(row)
        mark = "O" if (row["top1"] or row["none_ok"]) else "X"
        print(f"[{mark}] {r['id']:<7} {rep['result_state']:<12} pred={pred}({rep['business_name'][:12]}) 정답={tgt or 'NONE'}")

    ok = [p for p in per if "error" not in p]
    real = [p for p in ok if not p["none_case"]]
    none = [p for p in ok if p["none_case"]]
    n = len(real)

    def pct(pred):
        return round(100 * sum(1 for p in real if p[pred]) / n, 1) if n else 0.0

    mrr = round(sum(1.0 / p["pool_rank"] for p in real if p["pool_rank"]) / n, 4) if n else 0.0
    auto = [p for p in real if p["state"] == AUTO_STATE]
    auto_acc = round(100 * sum(1 for p in auto if p["top1"]) / len(auto), 1) if auto else None
    state_dist = {s: sum(1 for p in ok if p.get("state") == s) for s in m.RESULT_STATES}

    summary = {
        "gold": str(args.gold), "n_total": len(ok), "n_real": n, "n_none": len(none),
        "embedding_model": res["models"]["embedding_model"] if ok and "error" not in per[-1] else "?",
        "top1": pct("top1"), "recall@3": pct("recall3"), "mrr@pool": mrr,
        "state_distribution": state_dist,
        "auto(추천_가능)_share_pct": round(100 * len(auto) / n, 1) if n else 0.0,
        "auto(추천_가능)_accuracy_pct": auto_acc,
        "none_detection_pct": round(100 * sum(1 for p in none if p["none_ok"]) / len(none), 1) if none else None,
    }

    lit = {
        "추천_가능 비중 목표": "~55% (Census ACS 산업코딩)",
        "추천_가능 정확도 목표": "≥90%",
        "전체 Top-1 밴드": "65~80% (Schierholz 2021 + 사람 일치 상한)",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"eval_pipeline_{args.gold.stem}"
    (OUT_DIR / f"{stem}.json").write_text(
        json.dumps({"summary": summary, "literature_targets": lit, "cases": per},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 66)
    for k, v in summary.items():
        print(f"  {k:>26s} : {v}")
    print("-" * 66 + "\n  문헌 기준(docs/평가근거_문헌표.md §2):")
    for k, v in lit.items():
        print(f"  {k:>26s} : {v}")
    print("=" * 66)
    print(f"[저장] {OUT_DIR / (stem + '.json')}")


if __name__ == "__main__":
    main()
