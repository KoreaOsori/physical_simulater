"""가중치 재조직: '약했던 연결의 강화'로 바꿔도 H17 결론이 유지되나(docs/58, docs/54 다음 실험 ④).

지금까지의 모델은 이진 연결망 + '새 연결 추가'(축삭 발아에 가까움)였다. 사용자 정리(docs/54 3번)의 가소성은
W_normal -> W_lesion -> W_reorganized, 즉 기존 연결의 가중치 변화다. H17-5에서 같은 연결망의 가중 부하와 이진 부하의
순위 상관이 0.36뿐이었으므로, 가중치 모델에서는 결론이 바뀔 수 있다 -- docs/54가 꼽은 가장 큰 위험 요인.

모델
  가중치 W = 합의 간선의 평균 스트림라인 가중치(sc_avggm). 길이 = 1/W. 부하 = 가중 betweenness(연속 가중치라 최단 경로가 사실상
  유일 -- 빠른 구현이 networkx와 오차 0으로 일치함을 확인).
  손상: 병변 영역 제거. 생존 영역 n이 잃은 연결 강도 s_n = Σ_{병변 a} W[n,a].
  재조직: 각 n이 s_n을 3번에 나눠(Δ = s_n/3) 다른 영역과의 연결에 더한다.
    변형 A '강화만': 후보 = n의 기존 생존 이웃(약했던 경로 강화).
    변형 B '강화+발아': 후보 = 기존 이웃 + 배선 길이 제한 안의 새 영역(새 연결은 0에서 시작).
  전략(후보 고르는 규칙): 없음 / 무작위 / 허브 집중(현재 연결 강도 최대) / 균등 분산(현재 가중 부하 최소) /
    τ 규칙(비율 r = (부하+ε)/(1.2·(정상 부하+ε)) ≤ τ 인 후보 중 강도 최대, 없으면 r 최소; τ = 0, 0.5, 0.75, 1.0, ∞).
    ε = 정상 가중 부하 평균의 1%(정상 부하가 0인 영역 24개가 있어 문턱이 0이 되는 것을 막음 -- 민감도로 10%도 봄).
  평가: 가중 전역 효율(정상 대비), 가중 연쇄 생존(문턱 = m·(정상 부하+ε), m = 1.2, 1.0), 가중 부하 지도 충실도, 과부하 비율.

실행 전 예측:
  G1 H17 핵심이 유지된다: τ=0(정상 부하 지도 기반)이 균등 분산·허브 집중보다 가중 연쇄에 강하다.
  G2 τ 무릎(τ≈0.75)이 가중치 모델에서도 나타난다.
  G3 충실도와 효율의 맞바꿈이 유지된다.
  (불확실) 가중 부하가 소수의 강한 경로에 몰려 있어(0인 영역 24개) 결과가 이진 모델과 다를 수 있다.

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.weighted_reorganization > out.json
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
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from scripts.reorganization_hypotheses import SRC, load

N = 400
INF = float("inf")
K_STEPS = 3
RECOMPUTE = 20


def wpaths(W: np.ndarray, alive: np.ndarray):
    nodes = np.flatnonzero(alive)
    sub = W[np.ix_(nodes, nodes)]
    L = np.where(sub > 0, 1.0 / np.where(sub > 0, sub, 1), 0)
    D, P = dijkstra(csr_matrix(L), directed=False, return_predecessors=True)
    return nodes, D, P


def wbtw(W: np.ndarray, alive: np.ndarray) -> np.ndarray:
    nodes, D, P = wpaths(W, alive)
    n = len(nodes)
    rows = np.repeat(np.arange(n)[:, None], n, 1)
    depth = np.full((n, n), -1, np.int32)
    np.fill_diagonal(depth, 0)
    reach = ~np.isinf(D)
    Pc = np.where(P < 0, 0, P)
    for _ in range(n):
        par = depth[rows, Pc]
        upd = (depth < 0) & reach & (par >= 0) & (P >= 0)
        if not upd.any():
            break
        depth[upd] = par[upd] + 1
    delta = np.zeros((n, n))
    for d in range(int(depth.max()), 1, -1):
        s, v = np.nonzero(depth == d)
        np.add.at(delta, (s, P[s, v]), 1 + delta[s, v])
    out = np.zeros(N)
    out[nodes] = delta.sum(0) / 2
    return out


def weff(W: np.ndarray, alive: np.ndarray) -> float:
    """원래 400영역 기준 가중 전역 효율(Σ 1/가중 거리 / 400·399)."""
    nodes, D, _ = wpaths(W, alive)
    off = ~np.eye(len(nodes), dtype=bool) & ~np.isinf(D)
    return float((1.0 / D[off]).sum() / (N * (N - 1)))


def wcascade(W: np.ndarray, alive: np.ndarray, cap: np.ndarray) -> float:
    a = alive.copy()
    n0 = a.sum()
    for _ in range(50):
        Wa = W.copy()
        Wa[~a, :] = 0
        Wa[:, ~a] = 0
        over = a & (wbtw(Wa, a) > cap)
        if not over.any():
            break
        a &= ~over
    return float(a.sum() / n0)


def reorganize_w(W0, alive, lost_s, dist, lmax, rule, tau, cap, eps, variant, rng: random.Random):
    W = W0.copy()
    if rule == "none":
        return W
    steps = [n for n, s in lost_s.items() for _ in range(K_STEPS)]
    rng.shuffle(steps)
    load = wbtw(W, alive)
    near = dist <= lmax
    for i, n in enumerate(steps):
        if variant == "A":
            mask = alive & (W[n] > 0)
        else:
            mask = alive & ((W[n] > 0) | near[n])
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) == 0:
            continue
        r = np.array([rng.random() for _ in range(len(cands))])
        strength = W[cands].sum(1)
        if rule == "random":
            t = int(cands[rng.randrange(len(cands))])
        elif rule == "concentrated":
            t = int(cands[np.lexsort((-r, -strength))[0]])
        elif rule == "distributed":
            t = int(cands[np.lexsort((r, load[cands]))[0]])
        else:  # tau
            ratio = (load[cands] + eps) / (cap[cands])
            ok = ratio <= tau
            if ok.any():
                sub = np.flatnonzero(ok)
                t = int(cands[sub[np.lexsort((-r[sub], -strength[sub]))[0]]])
            else:
                t = int(cands[np.lexsort((r, ratio))[0]])
        dw = lost_s[n] / K_STEPS
        W[n, t] += dw
        W[t, n] += dw
        if (i + 1) % RECOMPUTE == 0:
            load = wbtw(W, alive)
    return W


STRATS = [("none", None), ("random", None), ("concentrated", None), ("distributed", None)] + [("tau", t) for t in (0.0, 0.5, 0.75, 1.0, INF)]
VARIANT_B = [("distributed", None), ("tau", 0.0), ("tau", 0.75), ("tau", INF)]


def label(rule, tau):
    return f"τ={tau}" if rule == "tau" else rule


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"weighted58_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, _, lesions = load()
    C = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
    W0 = np.where(C, np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy"), 0.0)
    np.fill_diagonal(W0, 0)
    iu = np.triu_indices(N, 1)
    lmax = float(np.percentile(dist[iu][C[iu]], 75))
    alive_full = np.ones(N, dtype=bool)
    L0 = wbtw(W0, alive_full)
    e_h = weff(W0, alive_full)
    les = sorted(lesions[li]["nodes"])
    alive = alive_full.copy()
    alive[les] = False
    Wl = W0.copy()
    Wl[les, :] = 0
    Wl[:, les] = 0
    lost_s = {int(n): float(W0[n, les].sum()) for n in np.flatnonzero(alive) if W0[n, les].sum() > 0}
    out = {"lesion": li, "res": {}}
    for eps_frac in (0.01, 0.1):
        eps = eps_frac * L0.mean()
        cap12 = 1.2 * (L0 + eps)
        cap10 = 1.0 * (L0 + eps)
        plans = [("A", s) for s in STRATS] + ([("B", s) for s in VARIANT_B] if eps_frac == 0.01 else [])
        for variant, (rule, tau) in plans:
            Wr = reorganize_w(Wl, alive, lost_s, dist, lmax, rule, tau, cap12, eps, variant, random.Random(li * 1000))
            load_r = wbtw(Wr, alive)
            key = f"{variant}|{label(rule, tau)}|eps{eps_frac}"
            out["res"][key] = {
                "eff_rel": weff(Wr, alive) / e_h,
                "casc_m1.2": wcascade(Wr, alive, cap12),
                "casc_m1.0": wcascade(Wr, alive, cap10),
                "fidelity": float(stats.spearmanr(load_r[alive], L0[alive])[0]),
                "overload": float((load_r[alive] > cap12[alive]).mean()),
            }
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    print(f"done lesion {li}", file=sys.stderr, flush=True)
    return out


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(job, list(range(25)), chunksize=1)
    names = list(res[0]["res"])
    keys = list(res[0]["res"][names[0]])
    table = {n: {k: float(np.mean([r["res"][n][k] for r in res])) for k in keys} for n in names}
    comp = {}
    for eps in ("0.01", "0.1"):
        for a, b in (("τ=0.0", "distributed"), ("τ=0.0", "concentrated"), ("τ=0.75", "τ=0.0"), ("τ=0.0", "none")):
            for k in ("casc_m1.2", "casc_m1.0", "eff_rel", "fidelity"):
                ka, kb = f"A|{a}|eps{eps}", f"A|{b}|eps{eps}"
                x = np.array([r["res"][ka][k] for r in res])
                y = np.array([r["res"][kb][k] for r in res])
                dd = x - y
                comp[f"A eps{eps}: {a} − {b}|{k}"] = {"diff": float(dd.mean()), "a_higher": int((dd > 0).sum()), "ties": int((dd == 0).sum()),
                                                     "p": float(stats.wilcoxon(x, y).pvalue) if np.any(dd != 0) else 1.0}
    # 충실도-효율 맞바꿈(병변 안 순위 상관, 변형 A eps0.01 전략 9개)
    rho = []
    for r in res:
        ks = [k for k in r["res"] if k.startswith("A|") and k.endswith("eps0.01")]
        rho.append(stats.spearmanr([r["res"][k]["fidelity"] for k in ks], [r["res"][k]["eff_rel"] for k in ks])[0])
    print(json.dumps({"table": table, "compare": comp, "within_lesion_rho_fidelity_eff": float(np.nanmean(rho))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
