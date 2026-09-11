"""
41_compare_embeddings.py — 개정 계획서 §6.4 "임베딩 모델은 평가 후 선택".

여러 한국어/다국어 임베딩 모델을 같은 조건(원문→검색, LLM 0)으로 비교.
각 모델: 14,627 docs 재색인(GPU, 없으면 스킵) → 골든셋 retrieval 지표.

사용:
    python business_matching/41_compare_embeddings.py \
        --models bge-m3,kure-v1,bge-m3-ko,ko-sroberta \
        --gold business_matching/gold_set_v3.csv

크레딧 0 (전부 로컬). 모델 다운로드 각 0.4~2.3GB.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import chromadb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedders  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_CSV = PROJECT_ROOT / "data" / "processed" / "business_code_docs_v1.csv"
OUT_DIR = PROJECT_ROOT / "data" / "outputs"
BASE_DOC_TYPES = ["name", "hier", "ksic", "desc", "def"]


def reindex(model: str, batch: int = 64) -> None:
    db_path, coll = embedders.chroma_target(model)
    client = chromadb.PersistentClient(path=db_path)
    try:
        if client.get_collection(coll).count() >= 14000:
            print(f"  [{model}] 인덱스 이미 있음 — 스킵")
            return
    except Exception:
        pass
    try:
        client.delete_collection(coll)
    except Exception:
        pass
    col = client.create_collection(coll, metadata={"embedding_model": model, "hnsw:space": "cosine"})
    df = pd.read_csv(DOCS_CSV, dtype={"business_code": str}, encoding="utf-8-sig").fillna("")
    t0 = time.time()
    for s in range(0, len(df), batch):
        b = df.iloc[s:s + batch]
        col.upsert(ids=b["doc_id"].tolist(), documents=b["doc_text"].tolist(),
                   embeddings=embedders.embed(b["doc_text"].tolist(), model),
                   metadatas=[{"business_code": r["business_code"], "doc_type": r["doc_type"]}
                              for _, r in b.iterrows()])
    print(f"  [{model}] 재색인 {len(df)}건 / {time.time()-t0:.0f}s")


def expected_codes(row):
    out = [str(row["expected_primary"]).strip()]
    alt = str(row.get("expected_alt", "") or "").strip()
    if alt and alt.lower() != "nan":
        out += [c.strip() for c in alt.split(";") if c.strip()]
    return [c for c in out if c and c.lower() != "nan"]


def eval_model(model: str, gold: pd.DataFrame, top: int = 20) -> dict:
    db_path, coll = embedders.chroma_target(model)
    col = chromadb.PersistentClient(path=db_path).get_collection(coll)
    ranks = []
    for _, r in gold.iterrows():
        tgt = expected_codes(r)
        if not tgt:
            continue
        emb = embedders.embed([f"{r['seed']}\n{r['problem']}\n{r['solution']}"], model)[0]
        res = col.query(query_embeddings=[emb], n_results=top * 5,
                        where={"doc_type": {"$in": BASE_DOC_TYPES}}, include=["metadatas"])
        seen = []
        for md in res["metadatas"][0]:
            c = str(md.get("business_code", "")).strip()
            if c and c not in seen:
                seen.append(c)
            if len(seen) >= top:
                break
        ranks.append(next((i for i, c in enumerate(seen, 1) if c in tgt), None))
    n = len(ranks)
    def p(cond): return round(100 * sum(1 for r in ranks if cond(r)) / n, 1)
    return {
        "model": model, "n": n,
        "top1": p(lambda r: r == 1),
        "recall@3": p(lambda r: r and r <= 3),
        "recall@10": p(lambda r: r and r <= 10),
        "recall@20": p(lambda r: r and r <= top),
        "mrr@20": round(sum(1 / r for r in ranks if r) / n, 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="bge-m3,kure-v1,bge-m3-ko,ko-sroberta")
    ap.add_argument("--gold", type=Path, default=Path(__file__).resolve().parent / "gold_set_v3.csv")
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    gold = pd.read_csv(args.gold, dtype=str, encoding="utf-8-sig").fillna("")

    rows = []
    for model in models:
        print(f"\n=== {model} ===")
        try:
            reindex(model)
            rows.append(eval_model(model, gold))
        except Exception as e:  # noqa: BLE001
            print(f"  [{model}] 실패: {repr(e)[:200]}")
            rows.append({"model": model, "error": repr(e)[:200]})

    tbl = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"embed_compare_{args.gold.stem}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"임베딩 모델 비교  (원문→검색, LLM 0, gold={args.gold.name})")
    print("=" * 70)
    print(tbl.to_string(index=False))
    ok = [r for r in rows if "error" not in r]
    if ok:
        best = max(ok, key=lambda r: r["recall@3"])
        print(f"\nRecall@3 최고: {best['model']} ({best['recall@3']}%)")


if __name__ == "__main__":
    main()
