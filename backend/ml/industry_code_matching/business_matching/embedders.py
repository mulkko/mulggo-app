"""
임베딩 백엔드 추상화 — 개정 계획서 §6.4 "임베딩 모델은 평가 후 선택".

지원:
  - OpenAI  : text-embedding-3-small / -large   (API, 유료 소액)
  - 로컬    : bge-m3 (BAAI/bge-m3, 1024차원)     (GPU, 무료)

사용:
    from embedders import embed, embedding_dim, chroma_target
    vecs = embed(["카페 운영", "커피 로스팅"], "bge-m3")

DB 분리 — 모델마다 별도 Chroma 컬렉션(차원·의미공간이 다르므로 섞으면 안 됨):
    chroma_target("text-embedding-3-small") -> (path, collection)  # 기존 index
    chroma_target("bge-m3")                 -> (path, collection)  # `reindex_local.py`가 새로 만듦
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Windows + conda + torch/mkl 의 libiomp5md.dll 중복 로드 회피 (추론 한정 안전).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

_PKG_ROOT = Path(__file__).resolve().parent.parent

_OPENAI_MODELS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
_LOCAL_ALIASES = {
    "bge-m3": "BAAI/bge-m3",
    "bge-m3-ko": "dragonkue/bge-m3-ko",
    "kure-v1": "nlpai-lab/KURE-v1",               # 한국어 retrieval 특화 (bge-m3 기반)
    "e5-large": "intfloat/multilingual-e5-large",  # 다국어 강 baseline
    "ko-sroberta": "jhgan/ko-sroberta-multitask",  # 한국어 문장임베딩 클래식
    "kosimcse": "BM-K/KoSimCSE-roberta",
}
_LOCAL_DIM = {
    "BAAI/bge-m3": 1024, "dragonkue/bge-m3-ko": 1024, "nlpai-lab/KURE-v1": 1024,
    "intfloat/multilingual-e5-large": 1024, "jhgan/ko-sroberta-multitask": 768,
    "BM-K/KoSimCSE-roberta": 768,
}
# e5 계열은 쿼리/문서에 접두어("query: " / "passage: ")를 요구한다.
_E5_PREFIX = {"intfloat/multilingual-e5-large"}

# 모델 -> (chroma path, collection 이름). 기존 OpenAI index 는 건드리지 않는다.
_CHROMA = {
    "text-embedding-3-small": ("chroma_db/business_code_docs_2025", "business_code_docs_2025"),
    "bge-m3": ("chroma_db/business_code_docs_bge_m3", "business_code_docs_bge_m3"),  # 기존 위치 유지
}
for _k in _LOCAL_ALIASES:
    _CHROMA.setdefault(_k, (f"chroma_db/bcd_{_k.replace('-', '_')}", f"bcd_{_k.replace('-', '_')}"))


def is_openai(model: str) -> bool:
    return model in _OPENAI_MODELS


def embedding_dim(model: str) -> int:
    if model in _OPENAI_MODELS:
        return _OPENAI_MODELS[model]
    return _LOCAL_DIM.get(_LOCAL_ALIASES.get(model, model), 1024)


def chroma_target(model: str) -> tuple[str, str]:
    if model not in _CHROMA:
        raise KeyError(f"chroma_target: 등록되지 않은 임베딩 모델 '{model}'")
    rel, coll = _CHROMA[model]
    return str(_PKG_ROOT / rel), coll


# ----------------------------------------------------------------- OpenAI
def _openai_embed(texts: list[str], model: str) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.embeddings.create(model=model, input=texts)
    return [e.embedding for e in sorted(resp.data, key=lambda x: x.index)]


# ----------------------------------------------------------------- 로컬 임베딩
@lru_cache(maxsize=1)
def _load_local(name: str):
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"
    from sentence_transformers import SentenceTransformer
    kw = {"device": device}
    if "gte" in name.lower() or "KURE" in name:
        kw["trust_remote_code"] = True
    return SentenceTransformer(name, **kw)


def _local_embed(texts: list[str], model: str) -> list[list[float]]:
    name = _LOCAL_ALIASES.get(model, model)
    if name in _E5_PREFIX:   # e5 계열: query/passage 구분 없이 통일 접두어 (근사)
        texts = [f"query: {t}" for t in texts]
    m = _load_local(name)
    return m.encode(texts, normalize_embeddings=True, batch_size=64,
                    show_progress_bar=False).tolist()


# ----------------------------------------------------------------- 공개 API
def embed(texts: list[str], model: str) -> list[list[float]]:
    texts = [t if (t and t.strip()) else " " for t in texts]
    if model in _OPENAI_MODELS:
        return _openai_embed(texts, model)
    return _local_embed(texts, model)


if __name__ == "__main__":  # 간단 셀프체크 (모델 로드 확인)
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    m = sys.argv[1] if len(sys.argv) > 1 else "bge-m3"
    v = embed(["직접 볶은 원두로 커피를 만들어 파는 카페", "반려동물 예방접종 알림 앱"], m)
    print(f"{m}: {len(v)}개 벡터, 차원 {len(v[0])} (예상 {embedding_dim(m)})")
    assert len(v[0]) == embedding_dim(m), "차원 불일치"
    print("OK")
