"""
build_gold_draft.py — 개정 계획서 §10.2~10.4.

인간 검증 골든셋의 *초안*을 만든다. LLM이 사례 + 예상 정답코드를 생성하고,
bge-m3 검색으로 자동 교차검증(예상코드가 상위 K에 있나)해서 사람 검수 부담을 줄인다.
최종 정답은 사람이 승인 → 이 스크립트는 사람_확정코드 칸을 비워 둔다.

카테고리(§10.3):  명확단일 80 / 유사경계 60 / 정보부족 25 / 복합 20 / 구어체 15  (기본 200)
MVP 업종군:        카페·음식점 / 소매 / 생활서비스 / 제조 / 농업·스마트팜 / 앱·플랫폼 / 교육·콘텐츠

사용:
    python business_matching/build_gold_draft.py                 # 200건
    python business_matching/build_gold_draft.py --n 20 --dry     # 스모크(20건)

출력: business_matching/gold_draft_v1.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import chromadb
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

SD = Path(__file__).resolve().parent
sys.path.insert(0, str(SD))
import embedders  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = SD.parent
MASTER = PROJECT_ROOT / "data" / "processed" / "business_code_master_v1.csv"
OUT = SD / "gold_draft_v1.csv"
EMB = "bge-m3"

MVP_GROUPS = [
    "카페·음식점", "소매(오프라인·온라인)", "생활서비스(미용·수리·세탁 등)",
    "제조·가공", "농업·스마트팜", "앱·플랫폼·소프트웨어", "교육·콘텐츠",
]
# 카테고리: (이름, 목표 건수, 프롬프트 지시)
CATEGORIES = [
    ("명확단일", 80,
     "업종이 명확히 하나로 떨어지는 사례. 직접 만드는지/파는지/중개인지가 분명하다."),
    ("유사경계", 60,
     "제조 vs 도소매 vs 중개 vs 소프트웨어 경계가 헷갈리는 사례. 정답은 하나지만 오답 후보가 그럴듯하다."),
    ("정보부족", 25,
     "설명이 막연해서 무슨 일로 돈 버는지 특정하기 어려운 사례. 예상코드는 비워도 되고, "
     "expected_note에 '정보 부족' 이라고 쓴다."),
    ("복합", 20,
     "독립된 수익활동이 2개 이상 섞인 사례 (예: 카페 + 원두 도매, 앱 + 오프라인 강의). "
     "expected_primary + expected_secondary 둘 다 채운다."),
    ("구어체", 15,
     "실제 사용자가 급하게 쓴 듯한 짧은 문장, 반말/오탈자/줄임말 포함. 내용은 분류 가능해야 한다."),
]

GEN_SYSTEM = """너는 한국 예비창업자의 사업 설명 사례와 그에 맞는 국세청 6자리 업종코드를 만든다.
반드시 아래에 주어진 '후보 코드 목록' 안에서만 예상 정답코드를 고른다. 목록에 없으면 만들지 않는다.
사례는 실제 창업 상담에서 나올 법하게, 구체적인 품목·활동·수익방식을 담아 쓴다.
PSST 폼 구조에 맞춘다: Q1 사업 아이템(한 줄), Q3 문제/기회, Q4 해결 방식(무엇을 만들고 무엇을 파는지),
Q5 오프라인 매장 여부(true/false)."""

GEN_SCHEMA = {
    "name": "gold_cases",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "cases": {
                "type": "array", "minItems": 1, "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "seed": {"type": "string"},
                        "problem_or_opportunity": {"type": "string"},
                        "solution_approach": {"type": "string"},
                        "is_offline_store": {"type": "boolean"},
                        "expected_primary": {"type": "string"},
                        "expected_secondary": {"type": "string"},
                        "expected_note": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["seed", "problem_or_opportunity", "solution_approach",
                                "is_offline_store", "expected_primary", "expected_secondary",
                                "expected_note", "why"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["cases"], "additionalProperties": False,
    },
}


def load_env() -> str:
    env = PROJECT_ROOT / ".env"
    load_dotenv(env if env.exists() else None)
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(f"OPENAI_API_KEY 없음: {env}")
    return os.getenv("LLM_MODEL", "gpt-5-mini").strip()


def code_menu(master: pd.DataFrame, group: str, k: int = 60) -> str:
    """그룹 키워드로 마스터에서 후보 코드 메뉴를 뽑는다 (LLM이 이 안에서만 고름)."""
    kw = {
        "카페·음식점": ["음식점", "커피", "제과", "주점", "음료"],
        "소매(오프라인·온라인)": ["소매", "전자상거래", "판매업"],
        "생활서비스(미용·수리·세탁 등)": ["미용", "수리", "세탁", "이용", "관리 서비스"],
        "제조·가공": ["제조업", "가공업", "생산"],
        "농업·스마트팜": ["재배업", "작물", "축산", "양식", "농업"],
        "앱·플랫폼·소프트웨어": ["소프트웨어", "정보 서비스", "포털", "중개"],
        "교육·콘텐츠": ["교육", "학원", "콘텐츠", "출판", "제작"],
    }[group]
    hit = master[master["business_name"].str.contains("|".join(kw), na=False)]
    if len(hit) > k:
        hit = hit.sample(k, random_state=len(group))
    lines = []
    for _, r in hit.iterrows():
        d = (r["definition"] or r["representative_items"] or "")[:70]
        lines.append(f"{r['business_code']}  {r['business_name']}  — {d}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--dry", action="store_true", help="20건만")
    args = ap.parse_args()
    if args.dry:
        args.n = 20

    llm = load_env()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    master = pd.read_csv(MASTER, dtype=str).fillna("")
    valid_codes = set(master["business_code"])
    name_of = dict(zip(master["business_code"], master["business_name"]))

    db_path, coll = embedders.chroma_target(EMB)
    col = chromadb.PersistentClient(path=db_path).get_collection(coll)

    scale = args.n / sum(c[1] for c in CATEGORIES)
    rows: list[dict] = []
    cid = 0
    for cat, target, instr in CATEGORIES:
        want = max(1, round(target * scale))
        per_group = max(1, want // len(MVP_GROUPS))
        for group in MVP_GROUPS:
            menu = code_menu(master, group)
            prompt = (f"[업종군] {group}\n[카테고리] {cat} — {instr}\n\n"
                      f"[후보 코드 목록]\n{menu}\n\n"
                      f"위 목록 안에서 골라, {cat} 성격의 사례를 {per_group}개 만들어라.")
            try:
                resp = client.chat.completions.create(
                    model=llm,
                    messages=[{"role": "system", "content": GEN_SYSTEM},
                              {"role": "user", "content": prompt}],
                    response_format={"type": "json_schema", "json_schema": GEN_SCHEMA},
                )
                cases = json.loads(resp.choices[0].message.content)["cases"]
            except Exception as e:  # noqa: BLE001
                print(f"[건너뜀] {cat}/{group}: {e}")
                continue

            for c in cases:
                cid += 1
                prim = c["expected_primary"].strip()
                # 자동 교차검증: 예상코드가 bge-m3 검색 상위 20에 있나
                text = f"{c['seed']}\n{c['problem_or_opportunity']}\n{c['solution_approach']}"
                emb = embedders.embed([text], EMB)[0]
                res = col.query(query_embeddings=[emb], n_results=80,
                                where={"doc_type": {"$in": ["name", "hier", "ksic", "desc", "def"]}},
                                include=["metadatas"])
                seen: list[str] = []
                for md in res["metadatas"][0]:
                    x = str(md.get("business_code", "")).strip()
                    if x and x not in seen:
                        seen.append(x)
                rank = (seen.index(prim) + 1) if prim in seen else None
                flag = []
                if prim and prim not in valid_codes:
                    flag.append("코드없음")
                if cat != "정보부족" and rank is None:
                    flag.append("검색밖")
                if cat != "정보부족" and rank and rank > 20:
                    flag.append(f"검색{rank}위")

                rows.append({
                    "id": f"D{cid:04d}", "category": cat, "mvp_group": group,
                    "seed": c["seed"], "problem_or_opportunity": c["problem_or_opportunity"],
                    "solution_approach": c["solution_approach"],
                    "is_offline_store": c["is_offline_store"],
                    "llm_expected_primary": prim,
                    "llm_expected_primary_name": name_of.get(prim, ""),
                    "llm_expected_secondary": c["expected_secondary"].strip(),
                    "llm_expected_note": c["expected_note"].strip(),
                    "llm_why": c["why"].strip(),
                    "auto_check": "OK" if not flag else " / ".join(flag),
                    "search_rank_of_expected": rank if rank else "",
                    "사람_확정_primary": "", "사람_확정_secondary": "",
                    "사람_확정_note": "", "사람_검수완료": "",
                })
            print(f"  {cat:>5} / {group:<16}  누적 {len(rows)}건")
            time.sleep(0.3)
            if len(rows) >= args.n:
                break
        if len(rows) >= args.n:
            break

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    ok = (df["auto_check"] == "OK").sum()
    print(f"\n[저장] {OUT}  —  {len(df)}건 (자동검증 OK {ok} / 플래그 {len(df)-ok})")
    print("다음: 사람_확정_* 칸 채우고 사람_검수완료=Y → finalize_gold.py")


if __name__ == "__main__":
    main()
