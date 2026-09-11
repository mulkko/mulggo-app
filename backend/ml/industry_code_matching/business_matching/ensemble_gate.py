"""
ensemble_gate.py — 앙상블 게이트 오프라인 분석. **LLM 안 씀. 크레딧 0.**

아이디어: 두 개의 독립 신호가 같은 코드를 가리킬 때만 "추천_가능(자동확정)".
  · 신호 A = 원문(Q1+Q3+Q4) 임베딩 검색(bge-m3)의 1위 코드
  · 신호 B = 파이프라인(⑦)의 재판정 최종 선택 코드  ← 이미 계산돼 있음(eval JSON)

입력:
  data/outputs/eval_pipeline_<gold>.json   (⑦ 결과, LLM 선택 코드 들어있음)
  + bge-m3 인덱스 (로컬)

사용:
  python business_matching/ensemble_gate.py --gold business_matching/gold_set_v3_auto.csv
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
OUT_DIR = PROJECT_ROOT / "data" / "outputs"
BASE_DOC_TYPES = ["name", "hier", "ksic", "desc", "def"]
EMB = "bge-m3"


def raw_top_codes(col, text: str, k: int = 3) -> list[str]:
    emb = embedders.embed([text], EMB)[0]
    res = col.query(query_embeddings=[emb], n_results=k * 6,
                    where={"doc_type": {"$in": BASE_DOC_TYPES}}, include=["metadatas"])
    out: list[str] = []
    for md in res["metadatas"][0]:
        c = str(md.get("business_code", "")).strip()
        if c and c not in out:
            out.append(c)
        if len(out) >= k:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True)
    args = ap.parse_args()

    eval_json = OUT_DIR / f"eval_pipeline_{args.gold.stem}.json"
    if not eval_json.exists():
        raise SystemExit(f"{eval_json} 없음. 먼저 eval_pipeline.py 를 이 gold 로 실행하세요.")
    ev = {c["id"]: c for c in json.loads(eval_json.read_text(encoding="utf-8"))["cases"]
          if "error" not in c}

    gold = pd.read_csv(args.gold, dtype=str, encoding="utf-8-sig").fillna("").set_index("id")
    db_path, coll = embedders.chroma_target(EMB)
    col = chromadb.PersistentClient(path=db_path).get_collection(coll)

    rows = []
    for cid, c in ev.items():
        if cid not in gold.index:
            continue
        r = gold.loc[cid]
        text = f"{r['seed']}\n{r['problem']}\n{r['solution']}"
        raw3 = raw_top_codes(col, text, 3)
        rows.append({
            "id": cid, "none_case": c["none_case"],
            "llm_pred": c["pred"], "llm_conf": c["confidence"], "llm_correct": c["top1"],
            "raw_top1": raw3[0] if raw3 else "", "raw_top3": raw3,
            "agree1": bool(raw3) and raw3[0] == c["pred"],
            "agree3": c["pred"] in raw3,
        })

    real = [x for x in rows if not x["none_case"]]
    none = [x for x in rows if x["none_case"]]
    n = len(real)

    def report(name, sel):
        g = [x for x in real if sel(x)]
        if not g:
            print(f"  {name:<34} 커버 0%")
            return
        cov = 100 * len(g) / n
        acc = 100 * sum(1 for x in g if x["llm_correct"]) / len(g)
        print(f"  {name:<34} 커버 {cov:5.1f}%   정확도 {acc:5.1f}%   (n={len(g)})")

    print(f"real 케이스 {n}건 · 전체 LLM Top-1 "
          f"{100*sum(1 for x in real if x['llm_correct'])/n:.1f}%\n")
    print("[게이트 후보별 커버리지 / 그 버킷 정확도]  — 목표: 커버 ~55% / 정확도 ≥90%")
    report("현재: LLM high (참고)", lambda x: x["llm_conf"] == "high")
    report("A. 검색1위 == LLM선택", lambda x: x["agree1"])
    report("B. A + LLM high  [파이프라인 채택]", lambda x: x["agree1"] and x["llm_conf"] == "high")
    report("C. LLM선택이 검색 top3 안", lambda x: x["agree3"])
    report("D. C + LLM high", lambda x: x["agree3"] and x["llm_conf"] == "high")
    report("E. A + (high 또는 mid)", lambda x: x["agree1"] and x["llm_conf"] in ("high", "mid"))

    # NONE 케이스: 불일치(disagree)가 NONE 신호가 되나?
    print(f"\n[NONE {len(none)}건 — 검색1위 vs LLM선택 불일치 비율]")
    if none:
        dis = sum(1 for x in none if not x["agree1"])
        dis_real = sum(1 for x in real if not x["agree1"])
        fp = 100 * dis_real / n
        print(f"  NONE 불일치: {dis}/{len(none)} ({100*dis/len(none):.0f}%)   "
              f"vs  real 불일치: {dis_real}/{n} ({fp:.0f}%)")
        print(f"  → '불일치 → 정보부족' 규칙 쓰면: NONE {100*dis/len(none):.0f}% 잡되 real {fp:.0f}% 오분류")
        # 불일치 AND 저신뢰 로 좁히면 오분류가 줄어드나
        dis_lo_none = sum(1 for x in none if not x["agree1"] and x["llm_conf"] != "high")
        dis_lo_real = sum(1 for x in real if not x["agree1"] and x["llm_conf"] != "high")
        print(f"  좁힘(불일치 AND not high): NONE {dis_lo_none}/{len(none)} vs real {dis_lo_real}/{n} "
              f"({100*dis_lo_real/n:.0f}% 오분류)")
    else:
        print("  (이 gold 에 NONE 케이스 없음)")

    (OUT_DIR / f"ensemble_{args.gold.stem}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[저장] {OUT_DIR / ('ensemble_' + args.gold.stem + '.json')}")


if __name__ == "__main__":
    main()
