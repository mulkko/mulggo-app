"""
35_compare_retrieval.py — 개정 계획서 §6.4 / §10.5(A·B).

"사업설명 원문 -> 임베딩 -> 검색"만으로 정답 업종코드가 상위 K에 들어오는지 측정.
LLM 안 씀. 로컬 임베딩(bge-m3)이면 크레딧 0.

임베딩 모델별로 따로 돌려서 비교:
    python business_matching/35_compare_retrieval.py --model bge-m3
    python business_matching/35_compare_retrieval.py --model text-embedding-3-small

지표: Top-1 / Recall@3 / Recall@10 / Recall@20 / MRR@20  (계획서 §10.6)
"""
from __future__ import annotations

import argparse
import json
import sys
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
DEFAULT_GOLD = Path(__file__).resolve().parent / "gold_set_v1.csv"
OUT_DIR = PROJECT_ROOT / "data" / "outputs"
BASE_DOC_TYPES = ["name", "hier", "ksic", "desc", "def"]   # 23번과 동일 (공식 정보 채널)


def expected_codes(row: pd.Series) -> list[str]:
    codes = [str(row["expected_primary"]).strip()]
    alt = str(row.get("expected_alt", "") or "").strip()
    if alt and alt.lower() != "nan":
        codes += [c.strip() for c in alt.split(";") if c.strip()]
    return [c for c in codes if c and c.lower() != "nan"]


def rank_of(codes: list[str], targets: list[str]) -> int | None:
    for i, c in enumerate(codes, start=1):
        if c in targets:
            return i
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="bge-m3")
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if embedders.is_openai(args.model):   # OpenAI 임베딩이면 .env 로드
        from dotenv import load_dotenv
        env = PROJECT_ROOT / ".env"
        load_dotenv(env if env.exists() else None)

    db_path, coll_name = embedders.chroma_target(args.model)
    col = chromadb.PersistentClient(path=db_path).get_collection(coll_name)

    gold = pd.read_csv(args.gold, dtype=str, encoding="utf-8-sig").fillna("")
    if args.limit:
        gold = gold.head(args.limit)

    per: list[dict] = []
    for _, r in gold.iterrows():
        targets = expected_codes(r)
        text = f"{r['seed']}\n{r['problem']}\n{r['solution']}"
        emb = embedders.embed([text], args.model)[0]
        res = col.query(query_embeddings=[emb], n_results=args.top * 4,
                        where={"doc_type": {"$in": BASE_DOC_TYPES}},
                        include=["metadatas"])
        seen: list[str] = []
        for md in res["metadatas"][0]:
            c = str(md.get("business_code", "")).strip()
            if c and c not in seen:
                seen.append(c)
            if len(seen) >= args.top:
                break
        rk = rank_of(seen, targets)
        per.append({"id": r["id"], "targets": targets, "rank": rk,
                    "top1": rk == 1, "r3": rk is not None and rk <= 3,
                    "r10": rk is not None and rk <= 10,
                    "r20": rk is not None and rk <= args.top})

    n = len(per)
    def pct(k): return round(100 * sum(1 for x in per if x[k]) / n, 1)
    mrr = round(sum((1.0 / x["rank"]) for x in per if x["rank"]) / n, 4)

    summary = {
        "model": args.model, "gold": str(args.gold), "n": n,
        "top1": pct("top1"), "recall@3": pct("r3"),
        "recall@10": pct("r10"), f"recall@{args.top}": pct("r20"),
        f"mrr@{args.top}": mrr,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"retrieval_{args.model.replace('/', '_')}_{args.gold.stem}"
    (OUT_DIR / f"{stem}.json").write_text(
        json.dumps({"summary": summary, "cases": per}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:>16s} : {v}")
    print("=" * 60)
    miss = [x for x in per if not x["r20"]]
    if miss:
        print(f"상위 {args.top}에도 정답 없음: {len(miss)}건  {[x['id'] for x in miss]}")
    print(f"[저장] {OUT_DIR / (stem + '.json')}")


if __name__ == "__main__":
    main()
