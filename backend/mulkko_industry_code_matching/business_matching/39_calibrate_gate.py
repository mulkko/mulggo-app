"""
39_calibrate_gate.py — ⑦ 결과 JSON 으로 "추천_가능" 게이트 컷을 데이터로 찾는다. (API 비용 0)

문헌 운영점 (docs/평가근거_문헌표.md §2):
  · 추천_가능 비중 ~55%   · 그 버킷 정확도 ≥90%   · 전체 Top-1 65~80%

컷 후보: confidence 등급 × 선택된 pool 순위(<=K).
"추천_가능 커버리지" 대 "그 버킷 실측 정확도" 트레이드오프 표를 출력.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT = PROJECT_ROOT / "data" / "outputs" / "eval_pipeline_gold_set_v3_auto.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=DEFAULT)
    args = ap.parse_args()

    d = json.loads(args.json.read_text(encoding="utf-8"))
    real = [c for c in d["cases"] if "error" not in c and not c["none_case"]]
    n = len(real)
    base_top1 = round(100 * sum(1 for c in real if c["top1"]) / n, 1)
    print(f"real 케이스 {n}건 · 전체 Top-1 {base_top1}%\n")

    conf_rank = {"high": 3, "mid": 2, "low": 1}
    print(f"{'컷 (confidence≥ & pool순위≤)':<32}{'커버':>8}{'그 버킷 정확도':>14}{'문헌부합':>10}")
    print("-" * 66)
    best = None
    for cmin, cname in [(3, "high"), (2, "mid+")]:
        for kmax in [1, 2, 3, 5, 20]:
            grp = [c for c in real
                   if conf_rank.get(c["confidence"], 0) >= cmin
                   and (c["pool_rank"] or 99) <= kmax]
            if not grp:
                continue
            cov = round(100 * len(grp) / n, 1)
            acc = round(100 * sum(1 for c in grp if c["top1"]) / len(grp), 1)
            fit = "○" if (45 <= cov <= 65 and acc >= 85) else ("△" if acc >= 90 or (50 <= cov <= 60) else "")
            label = f"{cname} & 순위≤{kmax}" if kmax < 20 else f"{cname} (순위 무관)"
            print(f"{label:<32}{cov:>7}%{acc:>13}%{fit:>10}")
            score = (acc >= 90, -abs(cov - 55))
            if best is None or score > best[0]:
                best = (score, label, cov, acc)

    print("-" * 66)
    print(f"\n권장 컷: {best[1]}  →  커버 {best[2]}% / 정확도 {best[3]}%")
    print("(90% 도달 불가 시: 가장 높은 정확도를 주는 컷 + 나머지는 사용자_확인_필요로)")

    # NONE 케이스: 현재 상태 분포
    none = [c for c in d["cases"] if "error" not in c and c["none_case"]]
    from collections import Counter
    print(f"\nNONE {len(none)}건 현재 상태: {dict(Counter(c['state'] for c in none))}")
    print("→ 규칙만으론 안 잡힘. 구조화에 classifiable(y/n) 신호 추가 필요.")


if __name__ == "__main__":
    main()
