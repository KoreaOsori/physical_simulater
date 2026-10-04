"""연구소 '손상-재조직 실험실'의 참고 패널 데이터 생성(docs/52).

입력(각 스크립트의 출력 JSON):
  --strategy  mixed_failure_model.py MODE=strategy 출력(손상 기전 혼합별 최선 전략 지도)
  --null      null_network_distribution.py 출력(귀무 연결망 분포) -- 귀무 Δ 값 히스토그램은 캐시에서 다시 읽는다(--null-cache)
출력: app/data/lab_reorganization_reference.json

실행: .venv/Scripts/python.exe -m scripts.build_reorg_reference --strategy s.json --null n.json --null-cache <cache52>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "lab_reorganization_reference.json"
STRAT_KEY = {"headroom": "normative"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy")
    ap.add_argument("--null")
    ap.add_argument("--null-cache")
    a = ap.parse_args()
    ref: dict = {"notes": []}
    if a.strategy:
        s = json.loads(Path(a.strategy).read_text(encoding="utf-8"))
        ref["strategy_map"] = [
            {"w": v["w"], "best_effT": STRAT_KEY.get(v["best_effT"], v["best_effT"]), "best_retained": STRAT_KEY.get(v["best_retained"], v["best_retained"]),
             "table": {STRAT_KEY.get(k, k): {q: round(x, 5) for q, x in t.items()} for k, t in v["table"].items()}}
            for v in s.values()
        ]
        ref["notes"].append("전략 지도: 국소 증후군 9개 × 반복 3, 10시기 마모 뒤 전역 효율(원래 400영역 기준)이 가장 높은 전략(scripts/mixed_failure_model.py MODE=strategy).")
    if a.null and a.null_cache:
        n = json.loads(Path(a.null).read_text(encoding="utf-8"))
        cache = Path(a.null_cache)
        ref["null_test"] = {}
        for kind, label in (("deg", "degree 보존 재배선"), ("geo", "degree + 배선 길이 보존")):
            vals = []
            for i in range(n["n_null"][kind]):
                d = json.loads((cache / f"null52_{kind}{i}.json").read_text(encoding="utf-8"))
                vals.append(d["delta"]["headroom-distributed"]["cascade_m1.2"])
            x = n[f"{kind}_vs_real"]["headroom-distributed"]["cascade_m1.2"]
            counts, edges = np.histogram(vals, bins=12)
            ref["null_test"][kind] = {"label": label, "real": x["real"], "null_mean": x["null_mean"], "null_p2_5": x["null_p2.5"],
                                      "null_p97_5": x["null_p97.5"], "p_real_gt_null": x["P_real_gt_null"], "n": len(vals),
                                      "hist": {"edges": [float(e) for e in edges], "counts": [int(c) for c in counts]}}
        ref["notes"].append("귀무 분포: 국소 증후군 25개 평균 연쇄 생존(m=1.2)의 차이(정상 부하 지도 기반 − 균등 분산)(scripts/null_network_distribution.py).")
    OUT.write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
