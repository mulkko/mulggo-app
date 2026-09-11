from __future__ import annotations

import argparse
import json
from pathlib import Path

# =============================================================================
# 29_calibrate_confidence.py
#
# 24번 평가 결과 JSON을 읽어, 신뢰도를 "데이터로" 분석한다. (API 비용 없음)
#
#   1) 버킷별 실측 정확도 (reliability)  — high/mid/low 가 실제로 뭘 뜻하나
#   2) 관찰 신호별 정확도 분포           — retrieval_margin / 선택 후보순위 /
#      벡터·키워드 동시여부. 어느 지점에서 정확도가 갈리는지.
#   3) 위 분석으로 유도되는 데이터 기반 규칙 후보를 제시.
#
# 정답셋은 통계청 해설서 <예시>/<제외> 기반(28번). 라벨 근거가 있으므로
# 여기서 나온 임계값은 "실측"이다.
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_JSON = PROJECT_ROOT / "data" / "outputs" / "eval_business_code_v1.json"


def acc(rows: list[dict]) -> tuple[int, int, float]:
    n = len(rows)
    ok = sum(1 for r in rows if r["C_top1"])
    return ok, n, (100.0 * ok / n if n else 0.0)


def bucketize(cases: list[dict], key: str, edges: list[float]) -> list[tuple[str, list[dict]]]:
    """edges = [a,b,c] -> 구간 (-inf,a] (a,b] (b,c] (c,inf)"""
    out: list[tuple[str, list[dict]]] = []
    prev = None
    for e in edges:
        lbl = f"≤{e}" if prev is None else f"({prev},{e}]"
        grp = [c for c in cases if c.get(key) is not None and (prev is None or c[key] > prev) and c[key] <= e]
        out.append((lbl, grp))
        prev = e
    out.append((f">{prev}", [c for c in cases if c.get(key) is not None and c[key] > prev]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = ap.parse_args()

    d = json.loads(args.json.read_text(encoding="utf-8"))
    cases = d["cases"]
    n = len(cases)
    print(f"정답셋: {d['summary'].get('gold_set')}")
    print(f"케이스: {n}  |  전체 C Top1: {acc(cases)[2]:.1f}%")

    # 1) 버킷별 실측 정확도
    for key, title in [("C_confidence", "최종 신뢰도(LLM+가드)"), ("C_llm_confidence", "LLM 자기판단만")]:
        print(f"\n[1] 버킷별 실측 정확도 — {title}")
        for lvl in ["high", "mid", "low"]:
            grp = [c for c in cases if c.get(key) == lvl]
            if grp:
                ok, m, p = acc(grp)
                print(f"    {lvl:4s}: n={m:3d} ({100*m/n:4.0f}%)   정확도 {p:5.1f}%  ({ok}/{m})")

    # 2) 신호별 정확도
    print("\n[2] retrieval_margin (벡터 1위-2위 cosine 차) 구간별 정확도")
    for lbl, grp in bucketize(cases, "C_retrieval_margin", [0.03, 0.06, 0.1, 0.15]):
        if grp:
            ok, m, p = acc(grp)
            print(f"    {lbl:>10s}: n={m:3d}   정확도 {p:5.1f}%")

    print("\n[3] 재판정이 고른 후보 순위(C_selected_pool_rank)별 정확도")
    for lbl, grp in [("1위", [c for c in cases if c.get("C_selected_pool_rank") == 1]),
                     ("2-3위", [c for c in cases if c.get("C_selected_pool_rank") in (2, 3)]),
                     ("4-5위", [c for c in cases if c.get("C_selected_pool_rank") in (4, 5)]),
                     ("6위+", [c for c in cases if (c.get("C_selected_pool_rank") or 0) >= 6])]:
        if grp:
            ok, m, p = acc(grp)
            print(f"    {lbl:>6s}: n={m:3d}   정확도 {p:5.1f}%")

    print("\n[4] 벡터·키워드 동시 검출 여부별 정확도")
    for lbl, val in [("동시 O", True), ("동시 X", False)]:
        grp = [c for c in cases if c.get("C_found_by_both") == val]
        if grp:
            ok, m, p = acc(grp)
            print(f"    {lbl}: n={m:3d}   정확도 {p:5.1f}%")

    # 5) 조합 규칙 후보 탐색: margin >= t AND rank == 1 AND both
    print("\n[5] 데이터 기반 'high' 규칙 후보 (조건 만족 시 정확도 / 커버리지)")
    for t in [0.05, 0.08, 0.10, 0.12, 0.15]:
        grp = [c for c in cases
               if (c.get("C_retrieval_margin") or -1) >= t
               and c.get("C_selected_pool_rank") == 1
               and c.get("C_found_by_both")]
        if grp:
            ok, m, p = acc(grp)
            print(f"    margin≥{t} & 1위 & 동시:  정확도 {p:5.1f}%  커버 {m}/{n} ({100*m/n:.0f}%)")

    # 6) 오답 목록
    miss = [c for c in cases if not c["C_top1"]]
    print(f"\n[6] C 오답 {len(miss)}건")
    for c in miss[:40]:
        pool = "pool내" if c["pool_recall_all"] else "pool밖"
        print(f"    {c['id']} 정답{c['targets']} → {c['C_code']}({c['C_name'][:14]}) "
              f"conf={c['C_confidence']} margin={c['C_retrieval_margin']} rank={c['C_selected_pool_rank']} {pool}")


if __name__ == "__main__":
    main()
