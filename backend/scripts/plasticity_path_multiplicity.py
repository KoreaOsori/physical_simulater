"""경로 다중성(동률 최단 경로) 가설 검증(docs/57 추가).

plasticity_heterogeneity.py 점검에서: 가중치 이질성을 줄여도(γ=0.25) 가중 부하 집중도(Gini 0.66, 0인 영역 27개)가
이진 부하(0.555)보다 오히려 컸다. 차이의 원인이 '가중치가 얼마나 다른가'가 아니라 '최단 경로가 하나뿐인가'일 수 있다:
이진 그래프에서는 길이가 같은 최단 경로가 많아 부하가 여러 경로로 나뉘고(경로 다중성), 가중 그래프에서는 경로가 하나라
한 경로의 부하가 통째로 한 영역에 몰린다.

검증: 이진 합의 그래프에 1%의 무작위 길이 흔들림(길이 = 1 + 0.01·U(0,1))만 주어 최단 경로를 유일하게 만든다(가중치 차이는
사실상 없음). 같은 실험(발아/강화 × 전략 4개 + 없음)을 반복.

실행 전 예측:
  J1 경로 다중성이 핵심이라면, 흔들림만 준 이진 그래프에서도 발아형의 정상 부하 지도 기반 이점(이진 모델 docs/52: 균등 분산 대비 +0.185)이
     크게 줄어든다.
  J2 반대로 이점이 그대로라면, 뒤집힘의 원인은 가중치 크기 차이 자체다.

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.plasticity_path_multiplicity > out.json
"""

from __future__ import annotations

import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import stats

from scripts.fast_reorganize import btw_array
from scripts.plasticity_heterogeneity import LESIONS, PLAST, STRATS, evaluate, reorganize
from scripts.reorganization_hypotheses import SRC, gini, load
from scripts.weighted_reorganization import N, wbtw, weff

JITTER = 0.01


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"plastjit57_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, _, lesions = load()
    C = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
    np.fill_diagonal(C, False)
    rng0 = np.random.default_rng(57)
    U = rng0.random((N, N))
    U = np.triu(U, 1)
    U = U + U.T
    W0 = np.where(C, 1.0 / (1.0 + JITTER * U), 0.0)  # 길이 = 1 + 0.01·U
    iu = np.triu_indices(N, 1)
    lmax = float(np.percentile(dist[iu][C[iu]], 75))
    les = sorted(lesions[li]["nodes"])
    alive = np.ones(N, dtype=bool)
    alive[les] = False
    L0 = wbtw(W0, np.ones(N, dtype=bool))
    L0_bin = btw_array(C, np.ones(N, dtype=bool))
    eps = 0.01 * L0.mean()
    cap12 = 1.2 * (L0 + eps)
    L0pct = stats.rankdata(L0) / N
    top10 = L0pct > 0.9
    e_h = weff(W0, np.ones(N, dtype=bool))
    Wl = W0.copy()
    Wl[les, :] = 0
    Wl[:, les] = 0
    lost_k = {int(n): int(C[n, les].sum()) for n in np.flatnonzero(alive) if C[n, les].sum() > 0}
    lost_s = {n: float(W0[n, les].sum()) for n in lost_k}
    out = {"lesion": li, "L0_gini": gini(L0), "L0_bin_gini": gini(L0_bin), "L0_zero": int((L0 == 0).sum()),
           "rho_jitter_vs_binary_L0": float(stats.spearmanr(L0, L0_bin)[0]), "res": {}}
    out["res"]["none"] = evaluate(Wl, alive, L0, cap12, eps, e_h, top10)
    for pl in PLAST:
        for rule, tau in STRATS:
            name = f"τ={tau}" if rule == "tau" else rule
            Wr, tp = reorganize(Wl, alive, lost_k, lost_s, dist, lmax, pl, rule, tau, cap12, eps, L0pct, random.Random(li * 1000))
            out["res"][f"{pl}|{name}"] = evaluate(Wr, alive, L0, cap12, eps, e_h, top10) | {"target_L0_pct": tp}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    print(f"done lesion {li}", file=sys.stderr, flush=True)
    return out


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(job, LESIONS, chunksize=1)
    names = list(res[0]["res"])
    table = {n: {k: float(np.nanmean([r["res"][n][k] for r in res])) for k in res[0]["res"][n]} for n in names}
    comp = {}
    for pl in PLAST:
        for a, b in (("τ=0.0", "distributed"), ("τ=0.6", "τ=0.0"), ("τ=0.0", "concentrated")):
            for k in ("casc_m1.2", "casc_m1.0"):
                x = np.array([r["res"][f"{pl}|{a}"][k] for r in res])
                y = np.array([r["res"][f"{pl}|{b}"][k] for r in res])
                dd = x - y
                comp[f"{pl}|{a} − {b}|{k}"] = {"diff": float(dd.mean()), "a_higher": int((dd > 0).sum()), "n": len(dd),
                                              "p": float(stats.wilcoxon(x, y).pvalue) if np.any(dd != 0) else 1.0}
    meta = {k: float(np.mean([r[k] for r in res])) for k in ("L0_gini", "L0_bin_gini", "L0_zero", "rho_jitter_vs_binary_L0")}
    print(json.dumps({"meta": meta, "table": table, "compare": comp}, ensure_ascii=False))


if __name__ == "__main__":
    main()
