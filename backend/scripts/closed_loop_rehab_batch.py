"""폐루프 재활 체계 비교(docs/52) -- 연구소 '폐루프 재활' 탭과 같은 서버 코드(app/lab/reorganization_lab.run_closed_loop)를
여러 병변·손상 기전에 돌린다.

조건: 국소 증후군 9개(0, 3, ..., 24번) × 개입 2종(연결 유도, 활동 조절[자연 재조직 = 균등 분산 위]) × 손상 기전 5종
(W1, W2, W3, W4, 고른 혼합) × 제어기 3종(없음/개방 루프/폐루프). 12시기, 반복 2, 시기당 예산 20.
지표: 마지막 시기 전역 효율(원래 400영역 기준), 생존 영역 수. 병변 단위 쌍대 Wilcoxon.

실행 전 예측:
  M1 활동 조절은 W1(자기 정상 부하 대비 과부하, 비선형)에서만 도움이 된다. W2(절대 부하, 선형)는 부하를 옮겨도 위험 총합이
     같아 효과가 거의 없고, W3·W4는 부하와 무관해 효과가 없다.
  M2 활동 조절에서 폐루프 > 개방 루프(W1): 처음 고른 영역이 죽거나 부하가 바뀌면 개방 루프는 헛자극한다.
  C1 연결 유도에서 폐루프 ≥ 개방 루프: 특히 W4(구조적 단절)에서 -- 폐루프는 새로 잃은 영역의 이웃까지 재조직 대상으로 삼는다.
  C2 연결 유도는 어떤 기전에서든 개입 없음보다 효율이 높다(새 연결 자체가 경로를 늘림).

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.closed_loop_rehab_batch > out.json
"""

from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import stats

from app.lab import reorganization_lab as rl
from app.lab.schemas import ClosedLoopRequest

MIXES = {"W1": (1, 0, 0, 0), "W2": (0, 1, 0, 0), "W3": (0, 0, 1, 0), "W4": (0, 0, 0, 1), "mixed": (0.25, 0.25, 0.25, 0.25)}
MODES = ["connect", "modulate"]
LESION_IDX = list(range(0, 25, 3))


def job(args) -> dict:
    mode, mix, li = args
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"rehab52_{mode}_{mix}_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    b = rl._base()
    lesion_id = [x["id"] for x in b.lesions if x["category"] == "focal"][li]
    w = MIXES[mix]
    r = rl.run_closed_loop(ClosedLoopRequest(lesion_id=lesion_id, mode=mode, budget=20, epochs=12, reps=2, base_strategy="distributed",
                                             w1=w[0], w2=w[1], w3=w[2], w4=w[3], seed=52))
    out = {"mode": mode, "mix": mix, "lesion": li,
           "final": {t.controller: {"eff": t.efficiency[-1], "alive": t.alive[-1], "dev": t.deviation[-1], "acts": float(sum(t.interventions))} for t in r.traces}}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    print(f"done {mode} {mix} {li}", file=sys.stderr, flush=True)
    return out


def main() -> None:
    jobs = [(m, x, li) for m in MODES for x in MIXES for li in LESION_IDX]
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(job, jobs, chunksize=1)
    summary = {}
    for m in MODES:
        for x in MIXES:
            rs = [r for r in res if r["mode"] == m and r["mix"] == x]
            row = {c: {k: float(np.mean([r["final"][c][k] for r in rs])) for k in ("eff", "alive", "dev", "acts")} for c in ("none", "open", "closed")}
            for a, b in (("closed", "open"), ("closed", "none"), ("open", "none")):
                for k in ("eff", "alive"):
                    xa = np.array([r["final"][a][k] for r in rs])
                    xb = np.array([r["final"][b][k] for r in rs])
                    dd = xa - xb
                    row[f"{a}_vs_{b}:{k}"] = {"diff": float(dd.mean()), "a_higher": int((dd > 0).sum()), "ties": int((dd == 0).sum()), "n": len(dd),
                                              "p": float(stats.wilcoxon(xa, xb).pvalue) if np.any(dd != 0) else 1.0}
            summary[f"{m}|{x}"] = row
    print(json.dumps({"summary": summary, "per_job": res}, ensure_ascii=False))


if __name__ == "__main__":
    main()
