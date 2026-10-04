"""가중치 모델에서 H17이 왜 뒤집히나: 가소성 종류(발아 vs 강화)인가, 부하 불균일성(가중치 이질성)인가(docs/57).

H17-10: 기존 연결 강화(가중치) 모델에서는 균등 분산이 정상 부하 지도 기반보다 연쇄에 강했고 τ 무릎이 사라졌다.
원인 후보:
  (가) 가소성 종류 -- 새 연결 발아 vs 기존 연결 강화.
  (나) 부하 불균일성 -- 가중 부하는 소수의 강한 경로 골격에 몰려 있다(정상 부하 0인 영역 24개, 이진 부하보다 훨씬 치우침).
두 축을 교차한다:
  가중치 이질성 γ: 가중치 = (원래 평균 스트림라인 가중치)^γ, γ = 0.25 / 0.5 / 1(γ가 작을수록 균일, 0이면 이진과 같음 --
    γ=0은 최단 경로 동률이 많아 빠른 가중 betweenness(경로 유일 가정)를 쓸 수 없어 제외. 이진 결과는 기존 실험(docs/52-55)과 비교).
  가소성 p: 강화만(기존 생존 이웃의 연결에 더함) / 발아만(배선 제한 안의 새 연결을 만듦).
  재조직 양: 생존 영역 n이 잃은 연결 k_n개만큼, 한 번에 Δ = (잃은 강도)/k_n 씩(γ->0이면 이진 모델의 '잃은 수만큼 새 연결'과 같은 구조).
  전략: 균등 분산(가중 부하 최소), τ=0(정상 부하 지도 기반), τ=0.6(docs/56 허용치 불확실 하 최적), 허브 집중(연결 강도 최대); + 재조직 없음.
기전 진단(MH1): 연결이 간 영역의 정상 부하 백분위 평균, 재조직 직후 과부하 영역 중 골격(정상 부하 상위 10%) 비율.

실행 전 예측:
  MX1 뒤집힘은 (나) 때문: γ가 작으면 발아·강화 모두에서 τ=0 > 균등 분산, γ=1이면 둘 다에서 균등 분산 ≥ τ=0.
  MX2(대안) 뒤집힘은 (가) 때문: 발아형에서는 γ와 무관하게 τ=0 > 균등 분산.
  MH1 가중(γ=1)에서 τ=0은 정상 부하 백분위가 높은(골격) 영역으로 강도를 보내고, 과부하가 골격에서 생긴다.

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.plasticity_heterogeneity > out.json
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

from scripts.reorganization_hypotheses import SRC, gini, load
from scripts.weighted_reorganization import N, wbtw, wcascade, weff

INF = float("inf")
GAMMAS = [0.25, 0.5, 1.0]
PLAST = ["strengthen", "sprout"]
STRATS = [("distributed", None), ("tau", 0.0), ("tau", 0.6), ("concentrated", None)]
LESIONS = list(range(0, 24, 2))
RECOMPUTE = 20


def reorganize(W0, alive, lost_k, lost_s, dist, lmax, plast, rule, tau, cap, eps, L0pct, rng: random.Random):
    W = W0.copy()
    steps = [n for n, k in lost_k.items() for _ in range(k)]
    rng.shuffle(steps)
    load_ = wbtw(W, alive)
    near = dist <= lmax
    chosen_pct = []
    for i, n in enumerate(steps):
        if plast == "strengthen":
            mask = alive & (W[n] > 0)
        else:
            mask = alive & (W[n] == 0) & near[n]
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) == 0:
            continue
        r = np.array([rng.random() for _ in range(len(cands))])
        strength = W[cands].sum(1)
        if rule == "concentrated":
            t = int(cands[np.lexsort((-r, -strength))[0]])
        elif rule == "distributed":
            t = int(cands[np.lexsort((r, load_[cands]))[0]])
        else:
            ratio = (load_[cands] + eps) / cap[cands]
            ok = np.flatnonzero(ratio <= tau)
            if len(ok):
                t = int(cands[ok[np.lexsort((-r[ok], -strength[ok]))[0]]])
            else:
                t = int(cands[np.lexsort((r, ratio))[0]])
        dw = lost_s[n] / lost_k[n]
        W[n, t] += dw
        W[t, n] += dw
        chosen_pct.append(L0pct[t])
        if (i + 1) % RECOMPUTE == 0:
            load_ = wbtw(W, alive)
    return W, (float(np.mean(chosen_pct)) if chosen_pct else float("nan"))


def evaluate(W, alive, L0, cap12, eps, e_h, top10) -> dict:
    load_ = wbtw(W, alive)
    over = alive & (load_ > cap12)
    return {
        "casc_m1.2": wcascade(W, alive, cap12),
        "casc_m1.0": wcascade(W, alive, L0 + eps),
        "eff_rel": weff(W, alive) / e_h,
        "fidelity": float(stats.spearmanr(load_[alive], L0[alive])[0]),
        "overload": float(over[alive].mean()),
        "overload_backbone_share": float((over & top10).sum() / max(over.sum(), 1)),
        "overload_backbone_L0_share": float(L0[over & top10].sum() / max(L0[over].sum(), 1e-12)),
    }


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"plast57_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, _, lesions = load()
    C = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
    Wraw = np.where(C, np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy"), 0.0)
    np.fill_diagonal(Wraw, 0)
    iu = np.triu_indices(N, 1)
    lmax = float(np.percentile(dist[iu][C[iu]], 75))
    les = sorted(lesions[li]["nodes"])
    alive = np.ones(N, dtype=bool)
    alive[les] = False
    out = {"lesion": li, "res": {}}
    for gm in GAMMAS:
        W0 = np.where(C, Wraw ** gm, 0.0)
        L0 = wbtw(W0, np.ones(N, dtype=bool))
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
        out["res"][f"γ={gm}|none"] = evaluate(Wl, alive, L0, cap12, eps, e_h, top10) | {"target_L0_pct": float("nan"),
                                                                                         "L0_gini": gini(L0), "L0_zero": int((L0 == 0).sum())}
        for pl in PLAST:
            for rule, tau in STRATS:
                name = f"τ={tau}" if rule == "tau" else rule
                Wr, tp = reorganize(Wl, alive, lost_k, lost_s, dist, lmax, pl, rule, tau, cap12, eps, L0pct, random.Random(li * 1000))
                out["res"][f"γ={gm}|{pl}|{name}"] = evaluate(Wr, alive, L0, cap12, eps, e_h, top10) | {"target_L0_pct": tp}
        print(f"lesion {li} γ={gm}", file=sys.stderr, flush=True)
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    return out


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(job, LESIONS, chunksize=1)
    names = list(res[0]["res"])
    table = {}
    for n in names:
        keys = [k for k in res[0]["res"][n]]
        table[n] = {k: float(np.nanmean([r["res"][n][k] for r in res])) for k in keys}
    comp = {}
    for gm in GAMMAS:
        for pl in PLAST:
            for a, b in (("τ=0.0", "distributed"), ("τ=0.6", "τ=0.0"), ("τ=0.0", "concentrated")):
                for k in ("casc_m1.2", "casc_m1.0", "eff_rel"):
                    x = np.array([r["res"][f"γ={gm}|{pl}|{a}"][k] for r in res])
                    y = np.array([r["res"][f"γ={gm}|{pl}|{b}"][k] for r in res])
                    dd = x - y
                    comp[f"γ={gm}|{pl}|{a} − {b}|{k}"] = {"diff": float(dd.mean()), "a_higher": int((dd > 0).sum()), "n": len(dd),
                                                         "p": float(stats.wilcoxon(x, y).pvalue) if np.any(dd != 0) else 1.0}
    print(json.dumps({"table": table, "compare": comp}, ensure_ascii=False))


if __name__ == "__main__":
    main()
