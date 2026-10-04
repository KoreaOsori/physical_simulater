"""정상 부하 지도 기반 재조직(headroom)의 이점이 실제 뇌 위상에서만 나타나는가 -- 귀무 연결망 분포(docs/52, 검토 의견 13번).

docs/51 H16-5-2는 degree 보존 재배선 연결망 2개만 썼다(n=2 -> '강한 탐색적 근거'). 여기서는 귀무 연결망을 수백 개 만들어
ΔR = mean_병변[R(headroom) − R(비교 전략)] 의 귀무 분포를 얻고 P(ΔR_real > ΔR_null)를 보고한다.

귀무 두 종류:
  deg  -- degree 순서 보존 무작위 재배선(Maslov-Sneppen, 간선 수의 10배 교환). 공간 배치·배선 길이는 무너진다.
  geo  -- degree 보존 + 배선 길이 보존: 교환 후 두 간선 길이 합이 원래의 ±10% 안이고, 누적 총 배선 길이가 원래의 ±1% 안일
          때만 받아들인다(간선 수의 10배 수락).
          'deg에서 이점이 사라진 것이 위상 때문인가, 공간 배치(배선 길이) 때문인가'를 가른다.
비교 전략: distributed(현재 부하 최소), random(1시드), none(재조직 없음).
지표: 연쇄 생존(m=1.0, 1.2; 용량 = m × 그 연결망의 정상 부하), 부하 지도 충실도(재조직 후 매개 중심성과 정상 매개
중심성의 Spearman, 생존 영역), 과부하 영역 비율(부하 > 1.2 × 정상 부하), 전역 효율.

병변: 국소 증후군 25개(같은 영역 번호 집합을 모든 연결망에 적용).
재조직: scripts/fast_reorganize.py(원래 구현과 간선 집합이 같음을 검증).

실행: NULL_N_DEG=100 NULL_N_GEO=50 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.null_network_distribution > out.json
"""

from __future__ import annotations

import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import stats
from scipy.sparse.csgraph import shortest_path

from scripts.fast_reorganize import N, btw_array, reorganize_fast, to_adj
from scripts.reorganization_hypotheses import load

STRATS = ["none", "random", "distributed", "headroom"]
KEYS = ["cascade_m1.0", "cascade_m1.2", "loadmap_rho", "overload_frac", "global_eff"]


def global_eff(adj: np.ndarray, alive: np.ndarray) -> float:
    nodes = np.flatnonzero(alive)
    n = len(nodes)
    d = shortest_path(adj[np.ix_(nodes, nodes)].astype(float), unweighted=True, directed=False)
    off = ~np.eye(n, dtype=bool)
    return float((1.0 / d[off]).sum() / (n * (n - 1)))


def cascade(adj: np.ndarray, alive: np.ndarray, cap: np.ndarray) -> float:
    a = alive.copy()
    n0 = a.sum()
    for _ in range(50):
        b = btw_array(adj, a)
        over = a & (b > cap)
        if not over.any():
            break
        a &= ~over
    return float(a.sum() / n0)


def deg_null(g: nx.Graph, seed: int) -> nx.Graph:
    h = g.copy()
    nx.double_edge_swap(h, nswap=10 * h.number_of_edges(), max_tries=10**8, seed=seed)
    return h


def geo_null(g: nx.Graph, dist: np.ndarray, seed: int, tol: float = 0.10) -> nx.Graph:
    rng = np.random.default_rng(seed)
    edges = [tuple(e) for e in g.edges]
    eset = {frozenset(e) for e in edges}
    target, accepted, tries = 10 * len(edges), 0, 0
    total0 = total = float(sum(dist[a, b] for a, b in edges))
    while accepted < target and tries < 400 * len(edges):
        tries += 1
        i, j = rng.integers(len(edges), size=2)
        if i == j:
            continue
        a, b = edges[i]
        c, d = edges[j]
        if rng.random() < 0.5:
            c, d = d, c
        if len({a, b, c, d}) < 4 or frozenset((a, d)) in eset or frozenset((c, b)) in eset:
            continue
        old = dist[a, b] + dist[c, d]
        new = dist[a, d] + dist[c, b]
        if abs(new - old) > tol * old or abs(total + new - old - total0) > 0.01 * total0:
            continue
        total += new - old
        eset -= {frozenset((a, b)), frozenset((c, d))}
        eset |= {frozenset((a, d)), frozenset((c, b))}
        edges[i], edges[j] = (a, d), (c, b)
        accepted += 1
    h = nx.Graph()
    h.add_nodes_from(range(N))
    h.add_edges_from(edges)
    return h


def run_net(g: nx.Graph, dist: np.ndarray, lesions: list) -> dict:
    adj_full, alive_full = to_adj(g)
    L0 = btw_array(adj_full, alive_full)
    lengths = [dist[a, b] for a, b in g.edges]
    lmax = float(np.percentile(lengths, 75))
    out = {"connected": nx.is_connected(g), "mean_len": float(np.mean(lengths)), "clustering": nx.average_clustering(g),
           "per_lesion": []}
    for li, les in enumerate(lesions):
        les_set = set(les["nodes"])
        lost: dict = {}
        for a in les_set:
            for b in g.neighbors(a):
                if b not in les_set:
                    lost[b] = lost.get(b, 0) + 1
        alive = alive_full.copy()
        alive[list(les_set)] = False
        adj = adj_full.copy()
        adj[list(les_set), :] = False
        adj[:, list(les_set)] = False
        row = {}
        for s in STRATS:
            ar = reorganize_fast(adj, alive, lost, dist, lmax, s, random.Random(li * 1000), 1.2 * L0)
            b = btw_array(ar, alive)
            row[s] = {
                "cascade_m1.0": cascade(ar, alive, 1.0 * L0),
                "cascade_m1.2": cascade(ar, alive, 1.2 * L0),
                "loadmap_rho": float(stats.spearmanr(b[alive], L0[alive])[0]),
                "overload_frac": float((b[alive] > 1.2 * L0[alive]).mean()),
                "global_eff": global_eff(ar, alive),
            }
        out["per_lesion"].append(row)
    out["mean"] = {s: {k: float(np.mean([r[s][k] for r in out["per_lesion"]])) for k in KEYS} for s in STRATS}
    out["delta"] = {f"headroom-{o}": {k: float(np.mean([r["headroom"][k] - r[o][k] for r in out["per_lesion"]])) for k in KEYS}
                    for o in ("distributed", "random", "none")}
    return out


def cached(key: str, fn):
    d = os.environ.get("REORG_CACHE")
    if not d:
        return fn()
    p = Path(d) / f"null52_{key}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    r = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(r), encoding="utf-8")
    tmp.replace(p)
    return r


def null_job(args) -> dict:
    kind, i = args

    def f():
        g, dist, _, lesions = load()
        h = deg_null(g, 1000 + i) if kind == "deg" else geo_null(g, dist, 2000 + i)
        return run_net(h, dist, lesions)

    r = cached(f"{kind}{i}", f)
    print(f"done {kind}{i}", file=sys.stderr, flush=True)
    return r


def main() -> None:
    n_null = {"deg": int(os.environ.get("NULL_N_DEG", "100")), "geo": int(os.environ.get("NULL_N_GEO", "50"))}
    g, dist, _, lesions = load()
    res = {"real": cached("real", lambda: run_net(g, dist, lesions))}
    print("done real", file=sys.stderr, flush=True)
    jobs = [(kind, i) for i in range(max(n_null.values())) for kind in ("deg", "geo") if i < n_null[kind]]
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        for (kind, i), r in zip(jobs, pool.imap(null_job, jobs)):
            res[f"{kind}{i}"] = r

    real = res["real"]
    summary: dict = {"n_null": n_null, "real_mean": real["mean"], "real_delta": real["delta"],
                     "real_meta": {k: real[k] for k in ("connected", "mean_len", "clustering")}}
    for kind in ("deg", "geo"):
        nets = [res[f"{kind}{i}"] for i in range(n_null[kind])]
        summary[f"{kind}_meta"] = {k: [float(np.mean([x[k] for x in nets])), float(np.std([x[k] for x in nets]))]
                                   for k in ("mean_len", "clustering")} | {"n_connected": int(sum(x["connected"] for x in nets))}
        summary[f"{kind}_mean"] = {s: {k: float(np.mean([x["mean"][s][k] for x in nets])) for k in KEYS} for s in STRATS}
        comp = {}
        for pair in real["delta"]:
            comp[pair] = {}
            for k in KEYS:
                nd = np.array([x["delta"][pair][k] for x in nets])
                r = real["delta"][pair][k]
                comp[pair][k] = {
                    "real": r, "null_mean": float(nd.mean()), "null_sd": float(nd.std(ddof=1)),
                    "null_p2.5": float(np.percentile(nd, 2.5)), "null_p97.5": float(np.percentile(nd, 97.5)),
                    "P_real_gt_null": float((nd < r).mean()), "z": float((r - nd.mean()) / nd.std(ddof=1)) if nd.std() > 0 else None,
                    # 귀무 연결망에서도 headroom이 이기는 비율(이점이 '어디서나' 생기는지)
                    "null_frac_positive": float((nd > 0).mean()),
                }
        summary[f"{kind}_vs_real"] = comp
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
