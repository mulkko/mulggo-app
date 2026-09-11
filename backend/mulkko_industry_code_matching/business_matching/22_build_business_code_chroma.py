from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

try:
    import chromadb
except ImportError as e:
    raise ImportError(
        "chromadb가 설치되어 있지 않습니다.\n"
        "터미널에서 다음을 실행하세요:\n"
        "pip install chromadb"
    ) from e

try:
    from dotenv import load_dotenv
except ImportError as e:
    raise ImportError(
        "python-dotenv가 설치되어 있지 않습니다.\n"
        "터미널에서 다음을 실행하세요:\n"
        "pip install python-dotenv"
    ) from e

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError(
        "openai 패키지가 설치되어 있지 않습니다.\n"
        "터미널에서 다음을 실행하세요:\n"
        "pip install openai"
    ) from e


# =============================================================================
# 22_build_business_code_chroma.py
#
# 목적
# - 21번에서 만든 업종코드 reference CSV를 읽는다.
# - embedding_text를 OpenAI text-embedding-3-small로 임베딩한다.
# - 6자리 업종코드 1개 = Chroma 문서 1개 구조로 저장한다.
# - 저장 위치: chroma_db/business_codes_2025/
#
# 중요
# - 23번 검색에서도 반드시 같은 Embedding 모델을 사용해야 한다.
# - Embedding 모델을 바꾸면 ChromaDB를 다시 구축해야 한다.
# =============================================================================


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "business_code_chroma_reference_v1.csv"
)

DEFAULT_DB_DIR = (
    PROJECT_ROOT
    / "chroma_db"
    / "business_codes_2025"
)

DEFAULT_COLLECTION_NAME = "business_codes_2025"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# OpenAI Embeddings API는 여러 문장을 한 번에 처리할 수 있다.
# 너무 크게 잡지 않고 안정적으로 100개씩 처리한다.
DEFAULT_BATCH_SIZE = 100


METADATA_COLUMNS = [
    "business_code",
    "biz_large_names",
    "biz_middle_names",
    "biz_small_names",
    "biz_sub_names",
    "biz_detail_names",
    "linked_ksic_codes",
    "linked_ksic_names",
    "main_ksic_codes",
    "main_ksic_names",
    "detail_descriptions",
    "source_row_count",
]


def clean_text(value: object) -> str:
    """NaN/None을 Chroma metadata에 넣지 않도록 빈 문자열로 변환."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def load_environment() -> None:
    """
    프로젝트 루트의 .env를 로드한다.

    기대 형식:
    OPENAI_API_KEY=sk-...
    """
    env_path = PROJECT_ROOT / ".env"

    if env_path.exists():
        load_dotenv(env_path)
    else:
        # 시스템 환경변수에 직접 등록되어 있을 수도 있으므로
        # .env가 없다고 바로 실패시키지는 않는다.
        load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY를 찾을 수 없습니다.\n\n"
            f"프로젝트 루트의 .env 파일을 확인하세요:\n{env_path}\n\n"
            "예시:\n"
            "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx"
        )


def load_reference(path: Path) -> pd.DataFrame:
    """21번 출력 파일을 읽고 구조를 검증한다."""
    if not path.exists():
        raise FileNotFoundError(
            "21번 출력 파일을 찾을 수 없습니다.\n"
            f"확인 경로: {path}\n\n"
            "먼저 21_prepare_business_code_chroma_reference.py를 실행하세요."
        )

    df = pd.read_csv(
        path,
        dtype={"business_code": str},
        encoding="utf-8-sig",
    )

    required_columns = {
        "business_code",
        "embedding_text",
        *METADATA_COLUMNS,
    }

    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise ValueError(
            "reference CSV에 필요한 컬럼이 없습니다.\n"
            f"누락 컬럼: {missing}"
        )

    # 문자열 컬럼 정리
    for col in df.columns:
        if col != "source_row_count":
            df[col] = df[col].map(clean_text)

    if df["business_code"].duplicated().any():
        duplicated = (
            df.loc[df["business_code"].duplicated(), "business_code"]
            .head(10)
            .tolist()
        )
        raise ValueError(
            "업종코드 중복이 발견되었습니다.\n"
            "21번 결과는 '업종코드 1개 = 1행'이어야 합니다.\n"
            f"예시: {duplicated}"
        )

    invalid_codes = df.loc[
        ~df["business_code"].str.fullmatch(r"\d{6}", na=False),
        "business_code",
    ]
    if not invalid_codes.empty:
        raise ValueError(
            "6자리 숫자 형식이 아닌 업종코드가 있습니다.\n"
            f"예시: {invalid_codes.head(10).tolist()}"
        )

    empty_docs = df["embedding_text"].eq("")
    if empty_docs.any():
        raise ValueError(
            f"embedding_text가 비어 있는 행이 {int(empty_docs.sum())}개 있습니다."
        )

    return df


def build_metadata(row: pd.Series) -> dict:
    """
    Chroma metadata 생성.

    Chroma metadata는 str/int/float/bool 같은 단순 타입만 허용하므로
    list/dict 대신 문자열로 저장한다.
    """
    metadata: dict = {}

    for col in METADATA_COLUMNS:
        value = row[col]

        if col == "source_row_count":
            try:
                metadata[col] = int(float(value))
            except (TypeError, ValueError):
                metadata[col] = 0
        else:
            metadata[col] = clean_text(value)

    # 어떤 임베딩 모델로 DB를 만들었는지 각 문서에도 남긴다.
    metadata["embedding_model"] = DEFAULT_EMBEDDING_MODEL

    return metadata


def embed_batch(
    client: OpenAI,
    texts: list[str],
    model: str,
    max_retries: int = 5,
) -> list[list[float]]:
    """
    OpenAI Embeddings API 호출.

    일시적인 오류가 나면 짧게 기다렸다가 재시도한다.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.embeddings.create(
                model=model,
                input=texts,
            )

            # API가 반환한 index 순서대로 정렬하여
            # 입력 text와 embedding의 순서를 확실히 맞춘다.
            ordered = sorted(response.data, key=lambda item: item.index)
            return [item.embedding for item in ordered]

        except Exception as e:
            last_error = e

            if attempt == max_retries:
                break

            wait_seconds = min(2 ** attempt, 20)
            print(
                f"\n[재시도] OpenAI Embedding 호출 실패 "
                f"({attempt}/{max_retries})"
            )
            print(f"원인: {e}")
            print(f"{wait_seconds}초 후 다시 시도합니다...")
            time.sleep(wait_seconds)

    raise RuntimeError(
        "OpenAI Embedding 호출에 최종 실패했습니다."
    ) from last_error


def reset_collection(
    chroma_client: chromadb.PersistentClient,
    collection_name: str,
):
    """
    같은 이름의 기존 Collection이 있으면 삭제 후 새로 만든다.

    22번을 다시 실행했을 때 과거 DB와 섞이는 것을 방지한다.
    """
    try:
        chroma_client.delete_collection(collection_name)
        print(f"[초기화] 기존 Collection 삭제: {collection_name}")
    except Exception:
        # 기존 collection이 없으면 정상적인 상황
        pass

    return chroma_client.create_collection(
        name=collection_name,
        metadata={
            "description": "2025 6자리 업종코드 매칭 기준 DB",
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "distance_metric": "cosine",
            "hnsw:space": "cosine",
        },
    )


def build_chroma(
    df: pd.DataFrame,
    db_dir: Path,
    collection_name: str,
    embedding_model: str,
    batch_size: int,
) -> None:
    """OpenAI 임베딩을 생성하고 ChromaDB에 저장한다."""
    db_dir.mkdir(parents=True, exist_ok=True)

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    chroma_client = chromadb.PersistentClient(path=str(db_dir))

    collection = reset_collection(
        chroma_client=chroma_client,
        collection_name=collection_name,
    )

    total = len(df)
    print("\n" + "=" * 72)
    print("22번 ChromaDB 구축 시작")
    print("=" * 72)
    print(f"입력 문서 수       : {total:,}")
    print(f"Embedding 모델     : {embedding_model}")
    print(f"Batch size         : {batch_size}")
    print(f"Collection         : {collection_name}")
    print(f"DB 저장 경로       : {db_dir}")
    print("=" * 72)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = df.iloc[start:end]

        ids = [
            f"business_code_{code}"
            for code in batch["business_code"].tolist()
        ]

        documents = batch["embedding_text"].tolist()

        metadatas = [
            build_metadata(row)
            for _, row in batch.iterrows()
        ]

        embeddings = embed_batch(
            client=openai_client,
            texts=documents,
            model=embedding_model,
        )

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        print(
            f"[진행] {end:>4,} / {total:,} "
            f"({end / total * 100:5.1f}%)"
        )

    stored_count = collection.count()

    if stored_count != total:
        raise RuntimeError(
            "ChromaDB 저장 건수가 예상과 다릅니다.\n"
            f"예상: {total:,}\n"
            f"실제: {stored_count:,}"
        )

    print("\n" + "=" * 72)
    print("22번 ChromaDB 구축 완료")
    print("=" * 72)
    print(f"저장 문서 수       : {stored_count:,}")
    print(f"Embedding 모델     : {embedding_model}")
    print(f"Collection         : {collection_name}")
    print(f"DB 저장 경로       : {db_dir}")
    print("=" * 72)


def verify_sample(
    db_dir: Path,
    collection_name: str,
) -> None:
    """DB 구축 후 문서 하나를 읽어 기본 저장 상태를 확인한다."""
    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_collection(collection_name)

    result = collection.get(
        limit=1,
        include=["documents", "metadatas"],
    )

    if not result["ids"]:
        raise RuntimeError("ChromaDB에서 저장 문서를 읽지 못했습니다.")

    print("\n[저장 샘플 확인]")
    print(f"ID           : {result['ids'][0]}")
    print(
        f"업종코드     : "
        f"{result['metadatas'][0].get('business_code', '')}"
    )
    print(
        f"세세분류     : "
        f"{result['metadatas'][0].get('biz_detail_names', '')}"
    )
    print(
        f"연계 KSIC    : "
        f"{result['metadatas'][0].get('linked_ksic_codes', '')}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenAI Embedding 기반 6자리 업종코드 ChromaDB 구축"
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"21번 reference CSV (기본값: {DEFAULT_INPUT})",
    )

    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help=f"Chroma 저장 폴더 (기본값: {DEFAULT_DB_DIR})",
    )

    parser.add_argument(
        "--collection",
        type=str,
        default=DEFAULT_COLLECTION_NAME,
        help=f"Collection 이름 (기본값: {DEFAULT_COLLECTION_NAME})",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"OpenAI Embedding 모델 (기본값: {DEFAULT_EMBEDDING_MODEL})",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"API Batch 크기 (기본값: {DEFAULT_BATCH_SIZE})",
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size는 1 이상이어야 합니다.")

    if args.model != DEFAULT_EMBEDDING_MODEL:
        print(
            "\n[주의] 현재 설계 기준 모델은 "
            f"{DEFAULT_EMBEDDING_MODEL} 입니다."
        )
        print(
            "22번과 23번의 Embedding 모델은 반드시 같아야 합니다.\n"
        )

    return args


def main() -> None:
    args = parse_args()

    load_environment()

    reference_df = load_reference(args.input)

    print("[사전 확인]")
    print(f"Reference CSV : {args.input}")
    print(f"문서 수       : {len(reference_df):,}")
    print(f"첫 업종코드   : {reference_df.iloc[0]['business_code']}")
    print(f"마지막 업종코드: {reference_df.iloc[-1]['business_code']}")

    build_chroma(
        df=reference_df,
        db_dir=args.db_dir,
        collection_name=args.collection,
        embedding_model=args.model,
        batch_size=args.batch_size,
    )

    verify_sample(
        db_dir=args.db_dir,
        collection_name=args.collection,
    )


if __name__ == "__main__":
    main()
