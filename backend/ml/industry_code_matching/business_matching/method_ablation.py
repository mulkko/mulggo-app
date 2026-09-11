"""
method_ablation.py — 개정 계획서 §10.5 (A~E 방법 비교).

원문(Q1+Q3+Q4) 기준으로 검색 방식을 단계적으로 쌓으며 Top-1 / Recall@3 측정.
  A. 키워드만            (토큰 매칭, LLM 0)
  B. 임베딩만            (bge-m3, LLM 0)
  C. 하이브리드          (A+B 순위 병합, LLM 0)
  D. + LLM 구조화        (--with-llm 시. 활동 추출 후 multi-query. 재판정 없음)  ~$0.3
  E. + LLM 재판정 (전체)  (eval_pipeline_<gold>.json 에서 가져옴)

사용:
    python business_matching/method_ablation.py --gold business_matching/gold_set_v3_sub90.csv
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import chromadb
import pandas as pd

SD = Path(__file__).resolve().parent
PROJECT_ROOT = SD.parent
sys.path.insert(0, str(SD))
import embedders  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_spec = importlib.util.spec_from_file_location("m23", SD / "match_business_code.py")
M = importlib.util.module_from_spec(_spec)
sys.modules["m23"] = M
_spec.loader.exec_module(M)

EMB = "bge-m3"
BASE = ["name", "hier", "ksic", "desc", "def"]
OUT_DIR = PROJECT_ROOT / "data" / "outputs"


def expected(row):
    o = [str(row["expected_primary"]).strip()]
    a = str(row.get("expected_alt", "") or "").strip()
    if a and a.lower() != "nan":
        o += [c.strip() for c in a.split(";") if c.strip()]
    return [c for c in o if c and c.lower() != "nan"]


def rank_in(codes, tgt):
    return next((i for i, c in enumerate(codes, 1) if c in tgt), None)


def kw_codes(ref_df, text, n=20):
    pseudo = {"canonical_activity": "", "product_service": text,
              "activity_name": "", "search_keywords": []}
    return [r["business_code"] for r in M.keyword_search(ref_df, pseudo, top_n=n)]


def emb_codes(col, text, n=20):
    e = embedders.embed([text], EMB)[0]
    res = col.query(query_embeddings=[e], n_results=n * 5,
                    where={"doc_type": {"$in": BASE}}, include=["metadatas"])
    out = []
    for md in res["metadatas"][0]:
        c = str(md.get("business_code", "")).strip()
        if c and c not in out:
            out.append(c)
        if len(out) >= n:
            break
    return out


def rrf(list_a, list_b, k=60, n=20):
    score = {}
    for lst in (list_a, list_b):
        for i, c in enumerate(lst):
            score[c] = score.get(c, 0) + 1 / (k + i + 1)
    return [c for c, _ in sorted(score.items(), key=lambda x: -x[1])][:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True)
    args = ap.parse_args()
    gold = pd.read_csv(args.gold, dtype=str, encoding="utf-8-sig").fillna("")
    real = gold[gold["expected_primary"].str.strip() != ""]

    ref_df = M.load_reference()
    db_path, coll = embedders.chroma_target(EMB)
    col = chromadb.PersistentClient(path=db_path).get_collection(coll)

    rec = {m: [] for m in ["A", "B", "C"]}
    for _, r in real.iterrows():
        tgt = expected(r)
        text = f"{r['seed']}\n{r['problem']}\n{r['solution']}"
        a = kw_codes(ref_df, text)
        b = emb_codes(col, text)
        c = rrf(a, b)
        rec["A"].append(rank_in(a, tgt))
        rec["B"].append(rank_in(b, tgt))
        rec["C"].append(rank_in(c, tgt))

    n = len(real)
    rows = []
    for m in ["A", "B", "C"]:
        rk = rec[m]
        rows.append({
            "방식": {"A": "A. 키워드만", "B": "B. 임베딩만(bge-m3)", "C": "C. 하이브리드"}[m],
            "Top-1": round(100 * sum(1 for x in rk if x == 1) / n, 1),
            "Recall@3": round(100 * sum(1 for x in rk if x and x <= 3) / n, 1),
            "Recall@20": round(100 * sum(1 for x in rk if x and x <= 20) / n, 1),
        })

    # E: 전체 파이프라인 (eval JSON)
    ej = OUT_DIR / f"eval_pipeline_{args.gold.stem}.json"
    if ej.exists():
        d = json.loads(ej.read_text(encoding="utf-8"))
        rl = [c for c in d["cases"] if "error" not in c and not c["none_case"]]
        rows.append({
            "방식": "E. + LLM 재판정 (전체)",
            "Top-1": round(100 * sum(1 for c in rl if c["top1"]) / len(rl), 1),
            "Recall@3": round(100 * sum(1 for c in rl if c["recall3"]) / len(rl), 1),
            "Recall@20": "-",
        })
    else:
        rows.append({"방식": "E. + LLM 재판정 (전체)", "Top-1": f"(먼저 `eval_pipeline.py` 실행: {ej.name})",
                     "Recall@3": "", "Recall@20": ""})

    tbl = pd.DataFrame(rows)
    (OUT_DIR / f"method_ablation_{args.gold.stem}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 64)
    print(f"방법 비교 (원문→검색, gold={args.gold.name}, real {n}건)")
    print("=" * 64)
    print(tbl.to_string(index=False))
    print("\nD (LLM 구조화 후 검색, 재판정 없음) 는 --with-llm 옵션 추가 시 (미구현, 예산상 생략).")


if __name__ == "__main__":
    main()
