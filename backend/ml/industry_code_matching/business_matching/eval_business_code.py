from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from openai import OpenAI

# =============================================================================
# eval_business_code.py
#
# 목적
# - gold_set_v1.csv(정답셋)로 3가지 방식의 성능을 비교한다.
#   A. 원문 그대로 임베딩 -> Chroma TOP1        (LLM 없음)
#   B. LLM 활동 구조화 -> multi-query 임베딩 -> 후보 pool TOP1  (재판정 없음)
#   C. B + GPT 재판정                          (v3 최종 방식)
# - 핵심 지표: "정답이 후보 pool 안에 들어오는가"(retrieval recall)와
#   A/B Top1·Top3·Top5, C Top1.
#
# 사용
#   python eval_business_code.py
#   python eval_business_code.py --gold gold_set_v1.csv --limit 5
#
# cosine similarity 절댓값은 지표로 쓰지 않는다. 순위/포함여부만 본다.
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

V3_PATH = SCRIPT_DIR / "match_business_code.py"
DEFAULT_GOLD = SCRIPT_DIR / "gold_set_v1.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "outputs"

POOL_RECALL_K = None  # None이면 `match_business_code.py`의 RERANK_TOP_N(재판정 후보 수)을 그대로 쓴다


def load_v3_module():
    spec = importlib.util.spec_from_file_location("match_v3", V3_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["match_v3"] = module
    spec.loader.exec_module(module)
    return module


def expected_codes(row: pd.Series) -> list[str]:
    codes = [str(row["expected_primary"]).strip()]
    alt = str(row.get("expected_alt", "") or "").strip()
    if alt and alt.lower() != "nan":
        codes += [c.strip() for c in alt.split(";") if c.strip()]
    return [c for c in codes if c]


def expected_secondary_codes(row: pd.Series) -> list[str]:
    raw = str(row.get("expected_secondary", "") or "").strip()
    if not raw or raw.lower() == "nan":
        return []
    return [c.strip() for c in raw.split(";") if c.strip()]


def hit(code: str, targets: list[str]) -> bool:
    return code in targets


def rank_in(codes: list[str], targets: list[str]) -> int | None:
    for i, c in enumerate(codes, start=1):
        if c in targets:
            return i
    return None


def model_a_codes(
    client: OpenAI,
    collection,
    embedding_model: str,
    text: str,
    top_n: int = 10,
) -> list[str]:
    """원문을 그대로 임베딩해서 검색 (LLM 미사용). 임베딩 백엔드는 embedders 가 분기."""
    import embedders
    emb = embedders.embed([text], embedding_model)[0]
    result = collection.query(
        query_embeddings=[emb],
        n_results=top_n,
        include=["metadatas"],
    )
    return [m.get("business_code", "") for m in result["metadatas"][0]]


def evaluate(
    gold_path: Path,
    limit: int | None,
    out_dir: Path,
    only_ids: list[str] | None = None,
) -> dict[str, Any]:
    m = load_v3_module()

    global POOL_RECALL_K
    if POOL_RECALL_K is None:
        POOL_RECALL_K = m.RERANK_TOP_N

    llm_model, embedding_model = m.load_env()
    client = OpenAI(api_key=m.os.environ["OPENAI_API_KEY"])

    ref_df = m.load_reference()
    lookup = m.reference_lookup(ref_df)
    collection = m.open_chroma(embedding_model)
    name_of = {c: v["business_name"] for c, v in lookup.items()}

    gold = pd.read_csv(gold_path, dtype=str, encoding="utf-8-sig").fillna("")
    if only_ids:
        gold = gold[gold["id"].isin(only_ids)]
    if limit:
        gold = gold.head(limit)

    per_case: list[dict[str, Any]] = []
    multi_case: list[dict[str, Any]] = []

    for _, row in gold.iterrows():
        cid = row["id"]
        targets = expected_codes(row)
        sec_targets = expected_secondary_codes(row)
        seed, problem, solution = row["seed"], row["problem"], row["solution"]

        print(f"[{cid}] 처리 중... (정답 {targets}" + (f" / 부가 {sec_targets}" if sec_targets else "") + ")")

        # ---- 복수 활동(대표 + 부가) 케이스: 전체 파이프라인을 그대로 실행해 대표·부가 확인 ----
        if sec_targets:
            full = m.match_business_code(seed, problem, solution)
            rep_code = full["representative_business"]["business_code"]
            add_codes = [a["business_code"] for a in full["additional_businesses"]]
            multi_case.append({
                "id": cid,
                "primary_targets": targets,
                "secondary_targets": sec_targets,
                "n_activities": len(full["activities"]),
                "rep_code": rep_code,
                "rep_name": name_of.get(rep_code, "?"),
                "additional_codes": add_codes,
                "additional_names": [name_of.get(c, "?") for c in add_codes],
                "primary_ok": rep_code in targets,
                "secondary_ok": any(c in sec_targets for c in add_codes),
                "both_ok": rep_code in targets and any(c in sec_targets for c in add_codes),
            })
            continue

        # ---- Model A : 원문 임베딩 ----
        a_codes = model_a_codes(
            client, collection, embedding_model,
            f"{seed}\n{problem}\n{solution}", top_n=10,
        )
        a_rank = rank_in(a_codes, targets)

        # ---- Model B/C : LLM 활동 구조화 ----
        activities = m.extract_activities(client, llm_model, seed, problem, solution)
        primary = next(a for a in activities if a["priority"] == "primary")

        queries = m.build_queries(primary)
        vec = m.vector_search_multi(client, collection, embedding_model, queries)
        kw = m.keyword_search(ref_df, primary)
        pool = m.build_candidate_pool(vec, kw, lookup, primary)
        pool_codes = [c["business_code"] for c in pool]

        b_rank = rank_in(pool_codes, targets)
        pool_recall_k = b_rank is not None and b_rank <= POOL_RECALL_K
        pool_recall_all = b_rank is not None

        # ---- Model C : GPT 재판정 ----
        rr = m.rerank(client, llm_model, primary, pool)
        c_code = rr["selected_candidate"]["business_code"]
        conf = m.compute_confidence(rr["confidence"], rr["selected_candidate"], vec)

        per_case.append({
            "id": cid,
            "targets": targets,
            "target_names": [name_of.get(t, "?") for t in targets],
            "primary_activity": primary["activity_name"],
            "canonical_activity": primary["canonical_activity"],
            "business_role": primary["business_role"],
            "A_top1": hit(a_codes[0], targets) if a_codes else False,
            "A_top3": a_rank is not None and a_rank <= 3,
            "A_top5": a_rank is not None and a_rank <= 5,
            "A_rank": a_rank,
            "A_top1_code": a_codes[0] if a_codes else "",
            "A_top1_name": name_of.get(a_codes[0], "?") if a_codes else "",
            "B_top1": hit(pool_codes[0], targets) if pool_codes else False,
            "B_top3": b_rank is not None and b_rank <= 3,
            "B_top5": b_rank is not None and b_rank <= 5,
            "B_rank": b_rank,
            "B_top1_code": pool_codes[0] if pool_codes else "",
            "B_top1_name": name_of.get(pool_codes[0], "?") if pool_codes else "",
            "pool_recall_k": pool_recall_k,
            "pool_recall_all": pool_recall_all,
            "C_top1": hit(c_code, targets),
            "C_code": c_code,
            "C_name": name_of.get(c_code, "?"),
            "C_confidence": conf["confidence"],
            "C_llm_confidence": conf["llm_confidence"],
            "C_retrieval_margin": conf["retrieval_margin"],
            "C_selected_pool_rank": conf["selected_pool_rank"],
            "C_found_by_both": conf["found_by_both_searches"],
            "C_downgrade": conf["confidence_downgrade_reason"],
            "C_reason": rr["reason"],
        })

    n = len(per_case)

    def pct(key: str) -> float:
        return round(100.0 * sum(1 for c in per_case if c[key]) / n, 1) if n else 0.0

    # 신뢰도 버킷별 실측 정확도 (최종 confidence 기준, LLM 원본 기준 둘 다)
    def bucket_table(conf_key: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for level in ["high", "mid", "low"]:
            grp = [c for c in per_case if c[conf_key] == level]
            if not grp:
                continue
            correct = sum(1 for c in grp if c["C_top1"])
            out[level] = {
                "count": len(grp),
                "share_pct": round(100.0 * len(grp) / n, 1),
                "accuracy_pct": round(100.0 * correct / len(grp), 1),
            }
        return out

    nm = len(multi_case)
    multi_summary = None
    if nm:
        multi_summary = {
            "n": nm,
            "primary_ok_pct": round(100.0 * sum(1 for c in multi_case if c["primary_ok"]) / nm, 1),
            "secondary_ok_pct": round(100.0 * sum(1 for c in multi_case if c["secondary_ok"]) / nm, 1),
            "both_ok_pct": round(100.0 * sum(1 for c in multi_case if c["both_ok"]) / nm, 1),
        }

    summary = {
        "gold_set": str(gold_path),
        "n_cases": n,
        "llm_model": llm_model,
        "embedding_model": embedding_model,
        "pool_recall_k": POOL_RECALL_K,
        "metrics": {
            "A_top1": pct("A_top1"), "A_top3": pct("A_top3"), "A_top5": pct("A_top5"),
            "B_top1": pct("B_top1"), "B_top3": pct("B_top3"), "B_top5": pct("B_top5"),
            "pool_recall_at_k": pct("pool_recall_k"),
            "pool_recall_all": pct("pool_recall_all"),
            "C_top1": pct("C_top1"),
        },
        "confidence_reliability_final": bucket_table("C_confidence"),
        "confidence_reliability_llm_only": bucket_table("C_llm_confidence"),
        "multi_industry": multi_summary,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    # gold 파일마다 다른 출력 파일 (v1 결과를 덮어쓰지 않도록)
    gold_stem = Path(gold_path).stem  # gold_set_v1 / gold_set_v2 ...
    stem = f"eval_{gold_stem}"
    if only_ids:
        stem += "_partial"
    (out_dir / f"{stem}.json").write_text(
        json.dumps(
            {"summary": summary, "cases": per_case, "multi_cases": multi_case},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    if per_case:
        try:
            pd.DataFrame(per_case).to_csv(
                out_dir / f"{stem}.csv", index=False, encoding="utf-8-sig",
            )
        except PermissionError:
            print(f"[경고] {stem}.csv가 열려 있어 저장을 건너뜀 (JSON은 저장됨).")

    print_summary(summary, per_case, multi_case)
    return {"summary": summary, "cases": per_case, "multi_cases": multi_case}


def print_summary(
    summary: dict[str, Any],
    per_case: list[dict[str, Any]],
    multi_case: list[dict[str, Any]] | None = None,
) -> None:
    mt = summary["metrics"]
    if per_case:
        print("\n" + "=" * 92)
        print(f"업종코드 매칭 성능 비교  (n={summary['n_cases']}, LLM={summary['llm_model']})")
        print("=" * 92)
        print(f"{'방식':<34} {'Top1':>8} {'Top3':>8} {'Top5':>8}")
        print("-" * 92)
        print(f"{'A. 원문 임베딩 (LLM 없음)':<32} {mt['A_top1']:>7}% {mt['A_top3']:>7}% {mt['A_top5']:>7}%")
        print(f"{'B. LLM 구조화 + 임베딩 (후보 pool)':<30} {mt['B_top1']:>7}% {mt['B_top3']:>7}% {mt['B_top5']:>7}%")
        print(f"{'C. B + GPT 재판정':<33} {mt['C_top1']:>7}% {'-':>8} {'-':>8}")
        print("-" * 92)
        print(f"정답이 후보 pool TOP{summary['pool_recall_k']} 안에 포함된 비율 : {mt['pool_recall_at_k']}%")
        print(f"정답이 후보 pool 전체에 포함된 비율        : {mt['pool_recall_all']}%")
        print("=" * 92)

    ms = summary.get("multi_industry")
    if ms:
        print(f"\n[복수 업종(대표+부가) — {ms['n']}건]")
        print(f"  대표 적중        : {ms['primary_ok_pct']}%")
        print(f"  부가 적중        : {ms['secondary_ok_pct']}%")
        print(f"  대표+부가 모두 적중: {ms['both_ok_pct']}%")
        for c in (multi_case or []):
            mark = "O" if c["both_ok"] else ("△" if c["primary_ok"] or c["secondary_ok"] else "X")
            print(
                f"  [{mark}] {c['id']} 활동{c['n_activities']}개 | "
                f"대표 {c['rep_code']}({c['rep_name'][:14]}) 부가 {c['additional_codes']} | "
                f"정답 대표{c['primary_targets']} 부가{c['secondary_targets']}"
            )

    for title, key in [("최종 신뢰도(LLM+가드)", "confidence_reliability_final"),
                       ("LLM 자기판단만", "confidence_reliability_llm_only")]:
        print(f"\n[신뢰도 버킷별 실측 정확도 — {title}]")
        tbl = summary.get(key, {})
        for level in ["high", "mid", "low"]:
            if level in tbl:
                b = tbl[level]
                print(f"  {level:4s}: {b['count']:2d}건 (전체의 {b['share_pct']:>4}%)  정확도 {b['accuracy_pct']:>5}%")

    print("\n[케이스별]")
    print(f"{'id':<5} {'정답':<8} {'A rank':>7} {'B rank':>7} {'poolK':>6} {'C 적중':>6}  {'C 선택':<22} conf")
    print("-" * 92)
    for c in per_case:
        print(
            f"{c['id']:<5} {c['targets'][0]:<8} "
            f"{str(c['A_rank'] or '-'):>7} {str(c['B_rank'] or '-'):>7} "
            f"{('O' if c['pool_recall_k'] else 'X'):>6} {('O' if c['C_top1'] else 'X'):>6}  "
            f"{c['C_name'][:20]:<22} {c['C_confidence']}"
        )

    misses = [c for c in per_case if not c["C_top1"]]
    if misses:
        print("\n[C 오답 케이스]")
        for c in misses:
            in_pool = "pool 안에 정답 있음" if c["pool_recall_all"] else "pool에 정답 자체가 없음(retrieval 실패)"
            print(f"- {c['id']} 정답 {c['targets']} {c['target_names']}")
            print(f"    C 선택: {c['C_code']} {c['C_name']}  ({in_pool}, B rank={c['B_rank']})")
            print(f"    이유: {c['C_reason'][:160]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--ids", type=str, default=None,
                        help="쉼표로 구분한 케이스 id만 평가 (예: M01,M02,M03)")
    args = parser.parse_args()

    only_ids = [s.strip() for s in args.ids.split(",")] if args.ids else None
    evaluate(args.gold, args.limit, args.out_dir, only_ids)


if __name__ == "__main__":
    main()
