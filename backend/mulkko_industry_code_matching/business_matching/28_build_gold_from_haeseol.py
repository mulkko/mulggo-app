from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# =============================================================================
# 28_build_gold_from_haeseol.py
#
# 통계청 11차 해설서 파싱 결과(27번 출력)로부터 정답셋을 자동 생성한다.
#
#   각 케이스:
#     - 라벨(expected_primary) = 해설서 <예시> 활동이 속한 업종코드   ← 근거: 통계청
#     - seed/problem/solution  = 그 활동을 하는 소규모 사업의 현실적 PSST 설명
#                                (LLM이 작성, 라벨은 LLM이 만들지 않음)
#
#   disambiguation 케이스:
#     - 해설서 <제외> "활동 X (코드 Y)" → 활동 X를 설명하고 라벨 = Y
#       (예: "매장 조리 김밥 소매(561)" → 도시락 제조가 아니라 음식점)
#
# 생성 모델(설명 작성용)과 매칭 모델(23번)은 별개다. 여기선 빠른 모델을 쓴다.
#
# 출력: business_matching/gold_set_v2.csv
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

HAESEOL_JSON = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_v1.json"
REF_CSV = PROJECT_ROOT / "data" / "processed" / "business_code_chroma_reference_v1.csv"
OUT_CSV = SCRIPT_DIR / "gold_set_v2.csv"

DEFAULT_GEN_MODEL = "gpt-4o-mini"

LEN = {"seed": (20, 120), "problem": (20, 250), "solution": (20, 300)}

GEN_SCHEMA = {
    "name": "psst_case",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "seed": {"type": "string"},
            "problem": {"type": "string"},
            "solution": {"type": "string"},
        },
        "required": ["seed", "problem", "solution"],
        "additionalProperties": False,
    },
}

GEN_SYSTEM = """
너는 대한민국 소상공인·창업자의 사업 아이디어를 PSST 형식으로 쓰는 사람이다.

주어진 '실제 산업활동'을 하는 소규모 사업을 상상해서 아래 3개를 쓴다.
- seed: 무엇을 해서 돈을 버는지 (사업 아이디어 시드)
- problem: 이 사업이 노리는 문제 또는 시장 기회
- solution: 구체적으로 어떻게 그 제품/서비스를 만들고 파는지

규칙:
- 반드시 '주어진 산업활동' 그대로의 사업이어야 한다. 다른 업종 활동(관광·투어·운영·교육 등)을
  덧붙이지 마라. 사업은 그 활동 하나로만 돈을 번다.
- '제외해야 할 활동'이 주어지면 그 활동은 절대 묘사하지 마라.
- 분류표 용어를 그대로 베끼지 말고, 실제 창업자가 쓸 법한 자연스러운 말로.
- 판매 채널(온라인/앱/배달)은 필요할 때만 짧게. '온라인 플랫폼을 통해' 같은 상투어를 남발하지 마라.
  케이스마다 표현을 다르게.
- 업종코드/KSIC 코드는 쓰지 마라.
- 각 필드 길이: seed 25~110자, problem 30~230자, solution 30~280자.
""".strip()

# 사업 설명 시드로 쓰기 좋은 예시활동 (동사성/명사구, 너무 짧지 않은 것)
GOOD_EX = re.compile(r"(제조|생산|가공|재배|사육|판매|소매|도매|운영|시공|공사|설치|"
                     r"수리|서비스|중개|교육|개발|제작|공급|납품|양성|양식|취급|알선)")


def load_haeseol() -> list[dict]:
    return json.loads(HAESEOL_JSON.read_text(encoding="utf-8"))


def load_ref_names() -> dict[str, str]:
    import pandas as pd
    df = pd.read_csv(REF_CSV, dtype={"business_code": str}, encoding="utf-8-sig").fillna("")
    return dict(zip(df["business_code"], df["biz_detail_names"]))


def usable_examples(entry: dict) -> list[str]:
    out = []
    for ex in entry.get("examples", []):
        ex = ex.strip(" ·.,;")
        if len(ex) < 4:
            continue
        if not GOOD_EX.search(ex) and len(ex) < 8:
            continue
        # 명백한 파싱 잡음
        if re.fullmatch(r"[가-힣]{1,3}", ex) or "타회" in ex or "기협" in ex:
            continue
        out.append(ex)
    return out


def stratified_sample(entries: list[dict], n_total: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    # 업종코드 대분류(첫 글자 A/C/G/I...) 기준 층화
    buckets: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        codes = e.get("business_codes_clean") or e.get("business_codes") or []
        if not codes:
            continue
        if not usable_examples(e):
            continue
        # 업종코드 첫 2자리로 대략적 대분류 근사
        buckets[codes[0][:2]].append(e)

    # 창업 아이디어로 잘 안 나오는 영역(금융·보험, 공공행정, 국제기구, 가구내고용)은
    # 표본에서 축소한다. 업종코드 앞 2자리 대략 기준.
    DEMOTE_PREFIX = {"66", "64", "65", "84", "99", "97"}
    for k in list(buckets.keys()):
        if k in DEMOTE_PREFIX and len(buckets[k]) > 2:
            buckets[k] = rnd.sample(buckets[k], 2)

    picked: list[dict] = []
    keys = list(buckets.keys())
    rnd.shuffle(keys)
    # 각 버킷에서 비례 추출 (최소 1)
    total_pool = sum(len(v) for v in buckets.values())
    for k in keys:
        share = max(1, round(n_total * len(buckets[k]) / total_pool))
        picked.extend(rnd.sample(buckets[k], min(share, len(buckets[k]))))
    rnd.shuffle(picked)
    return picked[:n_total]


def gen_case(client: OpenAI, model: str, activity: str, ksic_name: str,
             definition: str, exclude_hint: str) -> dict | None:
    user = f"""
[산업활동] {activity}
[분류명] {ksic_name}
[정의] {definition[:300]}
{f'[제외해야 할 활동] {exclude_hint}' if exclude_hint else ''}

이 활동을 하는 소규모 사업의 seed/problem/solution 을 써라.
""".strip()
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": GEN_SYSTEM},
                          {"role": "user", "content": user}],
                response_format={"type": "json_schema", "json_schema": GEN_SCHEMA},
                temperature=0.7,
            )
            d = json.loads(r.choices[0].message.content)
            ok = True
            for f, (lo, hi) in LEN.items():
                key = {"seed": "seed", "problem": "problem", "solution": "solution"}[f]
                v = d.get(key, "").strip()
                if not (lo <= len(v) <= hi):
                    ok = False
            if ok:
                return {k: v.strip() for k, v in d.items()}
        except Exception as e:  # noqa: BLE001
            print(f"    [재시도 {attempt+1}] {str(e)[:80]}")
            time.sleep(2)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="예시활동 기반 케이스 수")
    ap.add_argument("--n-disambig", type=int, default=40, help="제외활동 기반 구분 케이스 수")
    ap.add_argument("--model", type=str, default=DEFAULT_GEN_MODEL)
    ap.add_argument("--seed", type=int, default=20260908)
    ap.add_argument("--out", type=Path, default=OUT_CSV)
    ap.add_argument("--append", action="store_true", help="기존 out에 이어붙임")
    args = ap.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    entries = load_haeseol()
    ref_names = load_ref_names()
    by_ksic = {e["ksic_code"]: e for e in entries}

    rows: list[dict] = []
    done_ids = set()
    start_idx = 1
    if args.append and args.out.exists():
        import pandas as pd
        prev = pd.read_csv(args.out, dtype=str, encoding="utf-8-sig").fillna("")
        rows = prev.to_dict("records")
        done_ids = set(prev["id"])
        start_idx = len(rows) + 1

    # ---- 1) 예시활동 기반 ----
    picked = stratified_sample(entries, args.n, args.seed)
    print(f"층화 표본 {len(picked)}개 엔트리 → 케이스 생성 (모델={args.model})")
    rnd = random.Random(args.seed)
    for i, e in enumerate(picked):
        exs = usable_examples(e)
        activity = rnd.choice(exs)
        codes = e.get("business_codes_clean") or e["business_codes"]
        cid = f"H{start_idx + i:04d}"
        if cid in done_ids:
            continue
        excl = ""
        if e.get("excludes"):
            x = e["excludes"][0]
            excl = x["activity"]
        case = gen_case(client, args.model, activity, e["ksic_name"], e["definition"], excl)
        if not case:
            print(f"  [{cid}] 생성 실패, 스킵")
            continue
        rows.append({
            "id": cid,
            "seed": case["seed"], "problem": case["problem"], "solution": case["solution"],
            "expected_primary": codes[0],
            "expected_alt": ";".join(codes[1:]),
            "expected_secondary": "",
            "note": f"haeseol예시:{activity[:30]} | {e['ksic_code']} {e['ksic_name']}",
            "source": "haeseol_example",
            "ksic_code": e["ksic_code"],
        })
        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(picked)}")

    # ---- 2) 제외활동 기반 구분 케이스 ----
    disambig_pool = []
    for e in entries:
        for x in e.get("excludes", []):
            for c in x["codes"]:
                tgt = by_ksic.get(c if len(c) == 5 else None)
                if not tgt:
                    continue
                tcodes = tgt.get("business_codes_clean") or tgt.get("business_codes")
                if not tcodes or len(x["activity"]) < 6:
                    continue
                disambig_pool.append({
                    "activity": x["activity"],
                    "from_name": e["ksic_name"],
                    "to_entry": tgt,
                    "to_codes": tcodes,
                })
    rnd.shuffle(disambig_pool)
    dis = disambig_pool[:args.n_disambig]
    print(f"\n구분 케이스 {len(dis)}개 생성")
    for j, d in enumerate(dis):
        cid = f"D{start_idx + args.n + j:04d}"
        case = gen_case(client, args.model, d["activity"], d["to_entry"]["ksic_name"],
                        d["to_entry"]["definition"], f"'{d['from_name']}'로 오해되지 않게")
        if not case:
            continue
        rows.append({
            "id": cid,
            "seed": case["seed"], "problem": case["problem"], "solution": case["solution"],
            "expected_primary": d["to_codes"][0],
            "expected_alt": ";".join(d["to_codes"][1:]),
            "expected_secondary": "",
            "note": f"haeseol제외:{d['activity'][:30]} (→{d['to_entry']['ksic_name']}, X={d['from_name']})",
            "source": "haeseol_exclude",
            "ksic_code": d["to_entry"]["ksic_code"],
        })

    # ---- 저장 ----
    cols = ["id", "seed", "problem", "solution", "expected_primary", "expected_alt",
            "expected_secondary", "note", "source", "ksic_code"]
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    print(f"\n저장: {args.out}  ({len(rows)}건)")
    # 라벨 존재 검증
    import pandas as pd
    ref = set(pd.read_csv(REF_CSV, dtype={"business_code": str}, encoding="utf-8-sig")["business_code"])
    bad = [r["id"] for r in rows if r["expected_primary"] not in ref]
    print(f"  reference에 없는 라벨: {bad if bad else '없음'}")
    print("\n[샘플 5]")
    for r in rows[-5:]:
        print(f"  {r['id']} [{r['expected_primary']}] {ref_names.get(r['expected_primary'],'?')}")
        print(f"     seed: {r['seed']}")
        print(f"     note: {r['note']}")


if __name__ == "__main__":
    main()
