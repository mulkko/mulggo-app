"""
37_finalize_gold.py — 사람이 검수한 gold_draft_v1.csv -> 평가용 gold_set_v3.csv.

검수 규칙:
  · 사람_검수완료 == 'Y' 인 행만 채택.
  · 사람_확정_primary 가 있으면 그걸, 없으면 llm_expected_primary 를 정답으로.
  · 사람_확정_note 에 '제외' 또는 '버림' 이 있으면 그 행 폐기.
  · category == '정보부족' 이고 정답 코드가 비면 expected_primary='' (NONE, 판정 보류 케이스로 평가).

출력 컬럼(24/38 평가 스크립트 호환): id, seed, problem, solution, is_offline_store,
  expected_primary, expected_alt, expected_secondary, category, note
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SD = Path(__file__).resolve().parent
OUT = SD / "gold_set_v3.csv"
# 검수 파일 우선순위: 사람이 채운 xlsx > csv > 원본 draft
_CANDS = [SD / "골든셋_검수.xlsx", SD / "골든셋_검수.csv", SD / "gold_draft_v1.csv"]
DRAFT = next((p for p in _CANDS if p.exists()), _CANDS[-1])


def _read_draft(p: Path) -> pd.DataFrame:
    if p.suffix == ".xlsx":
        return pd.read_excel(p, dtype=str).fillna("")
    return pd.read_csv(p, dtype=str, encoding="utf-8-sig").fillna("")


def pick(row, human_col, llm_col):
    h = str(row.get(human_col, "") or "").strip()
    return h if h else str(row.get(llm_col, "") or "").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true",
                    help="사람 검수 전, auto_check==OK 행을 LLM 정답 그대로 잠정 채택 (⑦ 1차용). "
                         "출력: gold_set_v3_auto.csv")
    args = ap.parse_args()

    if not DRAFT.exists():
        raise SystemExit(f"{DRAFT} 없음. 먼저 36_build_gold_draft.py 실행하세요.")
    print(f"[읽음] {DRAFT.name}")
    df = _read_draft(DRAFT)

    global OUT
    if args.auto:
        done = df[df["auto_check"].str.strip() == "OK"].copy()
        done["사람_확정_primary"] = ""      # LLM 정답을 그대로 쓰게
        done["사람_확정_secondary"] = ""
        done["사람_확정_note"] = ""
        OUT = SD / "gold_set_v3_auto.csv"
        if done.empty:
            raise SystemExit("auto_check==OK 행이 없습니다.")
    else:
        done = df[df["사람_검수완료"].str.upper().str.strip() == "Y"].copy()
        if done.empty:
            raise SystemExit("사람_검수완료=Y 인 행이 없습니다. (1차 평가는 --auto)")

    out_rows = []
    dropped = 0
    for _, r in done.iterrows():
        note = str(r.get("사람_확정_note", "") or "")
        if any(w in note for w in ["제외", "버림", "폐기"]):
            dropped += 1
            continue
        primary = pick(r, "사람_확정_primary", "llm_expected_primary")
        if r["category"] == "정보부족" and not str(r.get("사람_확정_primary", "")).strip():
            primary = ""   # NONE — 판정 보류가 정답
        out_rows.append({
            "id": r["id"],
            "seed": r["seed"],
            "problem": r["problem_or_opportunity"],
            "solution": r["solution_approach"],
            "is_offline_store": r["is_offline_store"],
            "expected_primary": primary,
            "expected_alt": "",
            "expected_secondary": pick(r, "사람_확정_secondary", "llm_expected_secondary"),
            "category": r["category"],
            "note": note or r.get("llm_expected_note", ""),
        })

    res = pd.DataFrame(out_rows)

    # "정보부족" 초안은 잘못됐음(분류 가능한 사례). 손작성 gold_none_v1.csv 로 교체.
    none_csv = SD / "gold_none_v1.csv"
    if none_csv.exists():
        res = res[res["category"] != "정보부족"]
        nd = pd.read_csv(none_csv, dtype=str, encoding="utf-8-sig").fillna("")
        nd = nd.rename(columns={"problem_or_opportunity": "problem", "solution_approach": "solution"})
        for c in res.columns:
            if c not in nd.columns:
                nd[c] = ""
        res = pd.concat([res, nd[res.columns]], ignore_index=True)
        print(f"[교체] 초안 정보부족 제거 + gold_none_v1.csv {len(nd)}건 병합")

    res.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"[저장] {OUT}  —  채택 {len(res)}건 / 폐기 {dropped}건 / 미검수 {len(df)-len(done)}건")
    print(res["category"].value_counts().to_string())
    none_n = (res["expected_primary"] == "").sum()
    print(f"판정보류(NONE) 정답: {none_n}건")


if __name__ == "__main__":
    main()
