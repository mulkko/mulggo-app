from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import chromadb
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# =============================================================================
# 26_build_business_code_docs_chroma.py
#
# 목적
# - 25번이 만든 business_code_docs_v1.csv (업종코드 1개 = 문서 여러 개)를
#   OpenAI 임베딩해서 새 ChromaDB에 저장한다.
# - 문서 1개 = Chroma 항목 1개. metadata.business_code 로 코드에 다시 매핑한다.
#
# 중요
# - 기존 chroma_db/business_codes_2025 는 건드리지 않는다 (롤백용으로 보존).
# - 새 위치      : chroma_db/business_code_docs_2025
# - 새 collection : business_code_docs_2025
# - 23번은 이 새 collection을 바라보도록 이미 수정되어 있다.
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "business_code_docs_v1.csv"
DEFAULT_DB_DIR = PROJECT_ROOT / "chroma_db" / "business_code_docs_2025"
DEFAULT_COLLECTION = "business_code_docs_2025"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_BATCH_SIZE = 100


def load_environment() -> str:
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path if env_path.exists() else None)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY를 찾을 수 없습니다: {env_path}")
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()


def load_docs(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"25번 출력 파일이 없습니다: {path}\n"
            "먼저 25_prepare_business_code_docs.py를 실행하세요."
        )
    df = pd.read_csv(path, dtype={"business_code": str}, encoding="utf-8-sig")

    required = {"doc_id", "business_code", "doc_type", "doc_text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"docs CSV 필수 컬럼 누락: {sorted(missing)}")

    for col in ["doc_id", "business_code", "doc_type", "doc_text"]:
        df[col] = df[col].map(lambda v: "" if pd.isna(v) else str(v).strip())

    if df["doc_id"].duplicated().any():
        raise ValueError("doc_id 중복이 있습니다.")
    if (df["doc_text"] == "").any():
        raise ValueError("doc_text가 빈 행이 있습니다.")
    if not df["business_code"].str.fullmatch(r"\d{6}").all():
        raise ValueError("6자리 숫자가 아닌 business_code가 있습니다.")

    return df


def embed_batch(client: OpenAI, texts: list[str], model: str, max_retries: int = 5) -> list[list[float]]:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.embeddings.create(model=model, input=texts)
            ordered = sorted(resp.data, key=lambda item: item.index)
            return [item.embedding for item in ordered]
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt == max_retries:
                break
            wait = min(2 ** attempt, 20)
            print(f"[재시도 {attempt}/{max_retries}] {e} -> {wait}s 후 재시도")
            time.sleep(wait)
    raise RuntimeError("OpenAI Embedding 호출 최종 실패") from last_error


def reset_collection(client: chromadb.PersistentClient, name: str, model: str):
    try:
        client.delete_collection(name)
        print(f"[초기화] 기존 collection 삭제: {name}")
    except Exception:  # noqa: BLE001
        pass
    return client.create_collection(
        name=name,
        metadata={
            "description": "2025 6자리 업종코드 - 다중 검색문서(ONS 방식)",
            "embedding_model": model,
            "distance_metric": "cosine",
            "hnsw:space": "cosine",
        },
    )


def build(df: pd.DataFrame, db_dir: Path, collection_name: str, model: str, batch_size: int) -> None:
    db_dir.mkdir(parents=True, exist_ok=True)
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    chroma_client = chromadb.PersistentClient(path=str(db_dir))
    collection = reset_collection(chroma_client, collection_name, model)

    total = len(df)
    print("\n" + "=" * 72)
    print("26번 ChromaDB(다중문서) 구축 시작")
    print("=" * 72)
    print(f"문서 수        : {total:,}")
    print(f"고유 업종코드  : {df['business_code'].nunique():,}")
    print(f"Embedding 모델 : {model}")
    print(f"저장 경로      : {db_dir}")
    print("=" * 72)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = df.iloc[start:end]
        embeddings = embed_batch(openai_client, batch["doc_text"].tolist(), model)
        collection.upsert(
            ids=batch["doc_id"].tolist(),
            documents=batch["doc_text"].tolist(),
            metadatas=[
                {
                    "business_code": r["business_code"],
                    "doc_type": r["doc_type"],
                    "embedding_model": model,
                }
                for _, r in batch.iterrows()
            ],
            embeddings=embeddings,
        )
        print(f"[진행] {end:>5,} / {total:,} ({end / total * 100:5.1f}%)")

    stored = collection.count()
    if stored != total:
        raise RuntimeError(f"저장 건수 불일치: 예상 {total:,} / 실제 {stored:,}")

    print("\n" + "=" * 72)
    print("26번 구축 완료")
    print("=" * 72)
    print(f"저장 문서 수   : {stored:,}")
    print(f"Collection     : {collection_name}")
    print(f"저장 경로      : {db_dir}")

    # 간단 검색 점검
    probe = openai_client.embeddings.create(model=model, input="커피 원두 가공 및 제조").data[0].embedding
    res = collection.query(query_embeddings=[probe], n_results=5, include=["metadatas", "documents", "distances"])
    print("\n[점검 검색: '커피 원두 가공 및 제조']")
    for m, doc, d in zip(res["metadatas"][0], res["documents"][0], res["distances"][0]):
        print(f"  {m['business_code']} [{m['doc_type']}] cos={1 - d:.4f}  {doc[:40]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="다중 검색문서 기반 6자리 업종코드 ChromaDB 구축")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--collection", type=str, default=DEFAULT_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    model = load_environment()
    df = load_docs(args.input)
    build(df, args.db_dir, args.collection, model, args.batch_size)


if __name__ == "__main__":
    main()
