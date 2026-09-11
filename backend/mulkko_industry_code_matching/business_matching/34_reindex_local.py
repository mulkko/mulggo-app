"""
34_reindex_local.py — business_code_docs_v1.csv 를 로컬 임베딩 모델로 재색인.

26번(OpenAI)과 동일 구조, OpenAI 호출 없음. GPU 사용.
기존 OpenAI 컬렉션(business_code_docs_2025)은 건드리지 않는다 — A/B 비교용으로 둘 다 유지.

사용:
    python business_matching/34_reindex_local.py --model bge-m3
    python business_matching/34_reindex_local.py --model bge-m3 --limit 200   # 스모크

출력: embedders.chroma_target(model) 이 가리키는 새 컬렉션.
"""
from __future__ import annotations

import argparse
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
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "business_code_docs_v1.csv"


def load_docs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"business_code": str}, encoding="utf-8-sig")
    for col in ["doc_id", "business_code", "doc_type", "doc_text"]:
        df[col] = df[col].map(lambda v: "" if pd.isna(v) else str(v).strip())
    if df["doc_id"].duplicated().any():
        raise ValueError("doc_id 중복")
    if (df["doc_text"] == "").any():
        raise ValueError("빈 doc_text 존재")
    if not df["business_code"].str.fullmatch(r"\d{6}").all():
        raise ValueError("6자리 아닌 business_code 존재")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="bge-m3", help="embedders 에 등록된 로컬 모델명")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--limit", type=int, default=None, help="스모크용: 앞 N개만")
    args = ap.parse_args()

    if embedders.is_openai(args.model):
        raise SystemExit(f"'{args.model}' 은 OpenAI 모델입니다. 26번을 쓰세요.")

    df = load_docs(args.input)
    if args.limit:
        df = df.head(args.limit)
    total = len(df)

    db_path, collection_name = embedders.chroma_target(args.model)
    Path(db_path).mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=db_path)
    try:
        chroma.delete_collection(collection_name)
        print(f"[초기화] 기존 컬렉션 삭제: {collection_name}")
    except Exception:
        pass
    col = chroma.create_collection(
        name=collection_name,
        metadata={
            "description": "국세청 6자리 업종코드 다중 검색문서 (로컬 임베딩)",
            "embedding_model": args.model,
            "distance_metric": "cosine",
            "hnsw:space": "cosine",
        },
    )

    print("=" * 72)
    print(f"34번 로컬 재색인  |  모델={args.model}  차원={embedders.embedding_dim(args.model)}")
    print(f"문서 {total:,}개  고유코드 {df['business_code'].nunique():,}개  ->  {db_path}")
    print("=" * 72)

    t0 = time.time()
    for start in range(0, total, args.batch_size):
        end = min(start + args.batch_size, total)
        batch = df.iloc[start:end]
        vecs = embedders.embed(batch["doc_text"].tolist(), args.model)
        col.upsert(
            ids=batch["doc_id"].tolist(),
            documents=batch["doc_text"].tolist(),
            metadatas=[
                {"business_code": r["business_code"], "doc_type": r["doc_type"],
                 "embedding_model": args.model}
                for _, r in batch.iterrows()
            ],
            embeddings=vecs,
        )
        if end % (args.batch_size * 10) == 0 or end == total:
            rate = end / max(time.time() - t0, 1e-6)
            print(f"[진행] {end:>6,}/{total:,}  ({end/total*100:5.1f}%)  {rate:5.0f} docs/s")

    stored = col.count()
    if stored != total:
        raise RuntimeError(f"저장 불일치: 예상 {total:,} / 실제 {stored:,}")

    probe = embedders.embed(["커피 원두 가공 및 제조"], args.model)[0]
    res = col.query(query_embeddings=[probe], n_results=5, include=["metadatas", "documents", "distances"])
    print(f"\n완료 {stored:,}건 · {time.time()-t0:.0f}s")
    print("[점검: '커피 원두 가공 및 제조']")
    for m, doc, d in zip(res["metadatas"][0], res["documents"][0], res["distances"][0]):
        print(f"  {m['business_code']} [{m['doc_type']}] cos={1-d:.4f}  {doc[:40]}")


if __name__ == "__main__":
    main()
