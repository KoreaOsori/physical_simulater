"""쌍 흐름 분해: 손상 영역이 하던 '역할'별로 대체 경로가 다른가(docs/57, docs/54 다음 실험 ③).

사용자 정리(docs/54 2번): B의 부하 35는 한 종류가 아니다 -- 모듈 안 중계, 모듈 사이 전달 등 역할마다 대체 경로가 다를 수 있다.
부하(betweenness)를 '어떤 영역 쌍의 최단 경로를 중계하나'로 쪼갠다:
  L_class(v) = Σ_{(s,t) ∈ class} σ_sv·σ_vt / σ_st · 1[d(s,v)+d(v,t)=d(s,t)]
  class = 모듈 안 쌍(같은 Yeo-7) / 모듈 사이 쌍.  두 클래스의 합 = 전체 betweenness(검증).
'영향받은 쌍' = 정상 뇌에서 최단 경로 중 하나라도 병변 영역을 지나던 쌍.

질문과 실행 전 예측:
  F1 병변 뒤(재조직 없음) 영향받은 쌍의 효율 손실은 모듈 사이 쌍이 모듈 안 쌍보다 크다.
  F2 대체 경로가 역할마다 다르다: 생존 영역의 모듈 안 부하 증가와 모듈 사이 부하 증가의 순위 상관 < 0.5.
  F3 모듈 사이 우회 부하는 연결자(participation coefficient가 높은 영역)가 떠맡는다(ρ > 0.3).
  F4 정상 부하 지도 기반(τ=0)은 허브 집중(τ=∞)보다 모듈 사이 쌍의 효율 회복이 작지만, 클래스별 부하 지도 충실도는 더 높다.

전략: 재조직 없음, τ=0(정상 부하 지도 기반), τ=0.75, τ=∞(허브 집중), 균등 분산. 국소 증후군 25개.

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.pair_flow_decomposition > out.json
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

from scripts.fast_reorganize import N, btw_array, reorganize_fast, to_adj
from scripts.mixed_failure_model import strip
from scripts.reorganization_hypotheses import load
from scripts.tau_pareto import reorganize_tau

INF = float("inf")


def distances(sub: np.ndarray) -> np.ndarray:
    n = len(sub)
    A = sub.astype(np.float32)
    D = np.full((n, n), -1, dtype=np.int16)
    np.fill_diagonal(D, 0)
    reach = np.eye(n, dtype=bool)
    frontier = np.eye(n, dtype=np.float32)
    k = 0
    while True:
        k += 1
        new = ((frontier @ A) > 0) & ~reach
        if not new.any():
            return D
        D[new] = k
        reach |= new
        frontier = new.astype(np.float32)


def sigma_and_d(adj: np.ndarray, alive: np.ndarray):
    nodes = np.flatnonzero(alive)
    sub = adj[np.ix_(nodes, nodes)]
    D = distances(sub)
    A = sub.astype(float)
    sig = np.eye(len(nodes))
    for k in range(1, int(D.max()) + 1):
        sig += ((sig * (D == k - 1)) @ A) * (D == k)
    return nodes, D, sig


def class_loads(adj: np.ndarray, alive: np.ndarray, masks: dict, extra_pair_mask: np.ndarray | None = None):
    """클래스별 부하(전체 N 길이, 죽은 영역 0). masks: 이름 -> N×N 쌍 마스크(대칭). extra_pair_mask: 추가로 곱할 쌍 마스크."""
    nodes, D, sig = sigma_and_d(adj, alive)
    n = len(nodes)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = np.where(sig > 0, 1.0 / sig, 0.0)
    sub_masks = {}
    for name, M in masks.items():
        m = M[np.ix_(nodes, nodes)].copy()
        if extra_pair_mask is not None:
            m &= extra_pair_mask[np.ix_(nodes, nodes)]
        np.fill_diagonal(m, False)
        sub_masks[name] = m
    out = {name: np.zeros(N) for name in masks}
    Dp = D.astype(np.int32)
    valid = Dp >= 0
    for vi in range(n):
        dv = Dp[:, vi]
        on = (dv[:, None] + dv[None, :] == Dp) & valid & (dv[:, None] > 0) & (dv[None, :] > 0)
        frac = np.outer(sig[:, vi], sig[vi, :]) * inv * on
        for name, m in sub_masks.items():
            out[name][nodes[vi]] = (frac * m).sum() / 2
    return out


def pair_eff(adj: np.ndarray, alive: np.ndarray, pairmask: np.ndarray) -> float:
    """주어진 쌍들의 평균 1/거리(원래 쌍 수 기준; 죽거나 끊긴 쌍은 0)."""
    nodes = np.flatnonzero(alive)
    D = distances(adj[np.ix_(nodes, nodes)]).astype(float)
    full = np.zeros((N, N))
    with np.errstate(divide="ignore"):
        inv = np.where(D > 0, 1.0 / D, 0.0)
    full[np.ix_(nodes, nodes)] = inv
    iu = np.triu(pairmask, 1)
    return float(full[iu].sum() / max(iu.sum(), 1))


def participation(adj: np.ndarray, modules: np.ndarray) -> np.ndarray:
    deg = adj.sum(1).astype(float)
    pc = np.ones(N)
    for m in np.unique(modules):
        k_m = adj[:, modules == m].sum(1)
        pc -= np.where(deg > 0, (k_m / np.maximum(deg, 1)) ** 2, 0)
    return pc


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"pairflow57_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, modules_d, lesions = load()
    modules = np.array([modules_d[i] for i in range(N)])
    same = modules[:, None] == modules[None, :]
    masks = {"within": same, "between": ~same}
    adj_full, alive_full = to_adj(g)
    L0 = btw_array(adj_full, alive_full)
    cap = 1.2 * L0
    iu = np.triu_indices(N, 1)
    lmax = float(np.percentile(dist[iu][adj_full[iu]], 75))
    pc = participation(adj_full, modules)
    les = sorted(lesions[li]["nodes"])
    alive = alive_full.copy()
    alive[les] = False
    # 영향받은 쌍: 정상 뇌에서 병변 영역을 지나는 최단 경로가 하나라도 있던 생존 영역 쌍
    nodes, D, sig = sigma_and_d(adj_full, alive_full)
    Dp = D.astype(np.int32)
    affected = np.zeros((N, N), dtype=bool)
    for v in les:
        dv = Dp[:, v]
        affected |= (dv[:, None] + dv[None, :] == Dp) & (dv[:, None] > 0) & (dv[None, :] > 0)
    affected &= alive[:, None] & alive[None, :]
    np.fill_diagonal(affected, False)
    healthy_cls = class_loads(adj_full, alive_full, masks)
    lesion_role = {k: float(v[les].sum()) for k, v in healthy_cls.items()}
    adj = strip(adj_full, alive)
    lost: dict = {}
    for a in les:
        for nb in np.flatnonzero(adj_full[a]):
            if int(nb) not in set(les):
                lost[int(nb)] = lost.get(int(nb), 0) + 1
    out = {"lesion": li, "n_affected_pairs": {k: int(np.triu(affected & m, 1).sum()) for k, m in masks.items()},
           "lesion_between_share": lesion_role["between"] / max(lesion_role["within"] + lesion_role["between"], 1e-9),
           "lesion_mean_pc": float(pc[les].mean()), "res": {}}
    healthy_eff = {k: pair_eff(adj_full, alive_full, affected & m) for k, m in masks.items()}
    strategies = {
        "none": lambda: adj.copy(),
        "τ=0": lambda: reorganize_tau(adj, alive, lost, dist, lmax, 0.0, cap, random.Random(li * 1000)),
        "τ=0.75": lambda: reorganize_tau(adj, alive, lost, dist, lmax, 0.75, cap, random.Random(li * 1000)),
        "τ=∞": lambda: reorganize_tau(adj, alive, lost, dist, lmax, INF, cap, random.Random(li * 1000)),
        "distributed": lambda: reorganize_fast(adj, alive, lost, dist, lmax, "distributed", random.Random(li * 1000), cap),
    }
    surv = alive.copy()
    for name, fn in strategies.items():
        ar = fn()
        cl = class_loads(ar, alive, masks)
        total = btw_array(ar, alive)
        r = {"class_sum_check": float(np.abs(cl["within"] + cl["between"] - total)[surv].max())}
        for k, m in masks.items():
            r[f"eff_rel_{k}"] = pair_eff(ar, alive, affected & m) / max(healthy_eff[k], 1e-12)
            r[f"fidelity_{k}"] = float(stats.spearmanr(cl[k][surv], healthy_cls[k][surv])[0])
        dW = cl["within"][surv] - healthy_cls["within"][surv]
        dB = cl["between"][surv] - healthy_cls["between"][surv]
        r["rho_dWithin_dBetween"] = float(stats.spearmanr(dW, dB)[0])
        r["rho_dBetween_pc"] = float(stats.spearmanr(dB, pc[surv])[0])
        r["rho_dWithin_pc"] = float(stats.spearmanr(dW, pc[surv])[0])
        # 모듈 사이 우회 부하 증가분을 어느 네트워크가 떠맡나(증가분 양수 합의 비율)
        pos = np.maximum(dB, 0)
        mods = modules[surv]
        r["between_absorb_share"] = {str(mm): float(pos[mods == mm].sum() / max(pos.sum(), 1e-9)) for mm in np.unique(modules)}
        out["res"][name] = r
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
    scal = [k for k in res[0]["res"]["none"] if k != "between_absorb_share"]
    table = {n: {k: float(np.nanmean([r["res"][n][k] for r in res])) for k in scal} for n in names}
    absorb = {n: {m: float(np.mean([r["res"][n]["between_absorb_share"][m] for r in res])) for m in res[0]["res"][n]["between_absorb_share"]} for n in names}
    x = np.array([r["res"]["none"]["eff_rel_between"] for r in res])
    y = np.array([r["res"]["none"]["eff_rel_within"] for r in res])
    f1 = {"between_minus_within_loss": float(((1 - x) - (1 - y)).mean()), "between_loses_more": int(((1 - x) > (1 - y)).sum()), "n": len(x),
          "p": float(stats.wilcoxon(x, y).pvalue)}
    role = {"lesion_between_share_mean": float(np.mean([r["lesion_between_share"] for r in res])),
            "rho_share_vs_pc": float(stats.spearmanr([r["lesion_between_share"] for r in res], [r["lesion_mean_pc"] for r in res])[0])}
    comp = {}
    for a, b in (("τ=0", "τ=∞"), ("τ=0.75", "τ=0"), ("τ=0", "distributed")):
        for k in ("eff_rel_between", "eff_rel_within", "fidelity_between", "fidelity_within"):
            xa = np.array([r["res"][a][k] for r in res])
            xb = np.array([r["res"][b][k] for r in res])
            dd = xa - xb
            comp[f"{a} − {b}|{k}"] = {"diff": float(dd.mean()), "a_higher": int((dd > 0).sum()), "p": float(stats.wilcoxon(xa, xb).pvalue) if np.any(dd != 0) else 1.0}
    print(json.dumps({"table": table, "absorb_between_by_network": absorb, "F1": f1, "lesion_role": role, "compare": comp}, ensure_ascii=False))


if __name__ == "__main__":
    main()
