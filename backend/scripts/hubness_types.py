"""어떤 종류의 허브성이 병변 영향을 가장 잘 예측하는가(docs/52, 검토 의견 3번; H16-1 확장).

H16-1/H16-1-1은 허브성 = 병변 영역의 평균 degree 하나로 봤다. 선행 연구는 허브를 한 개념으로 묶지 않는다:
  - Yuan et al. 2017 (Sci Rep, doi:10.1038/s41598-017-17886-x): '병변 허브'는 degree 하나와 일치하지 않고 연결자(높은 participation coefficient)와
    지역 허브(높은 within-module degree)가 모두 포함된다. 기능 연결망 위상 변화를 병변 패턴으로 예측.
  - Warren et al. 2014 (PNAS 111:14247): 연결자형 허브(높은 PC·system density) 손상 -> 광범위한 인지 결손,
    높은 degree '대조 허브' 손상 -> 국한된 결손.
  - Gratton et al. 2012 (J Cogn Neurosci 24:1275): 연결자 손상은 (기능) 모듈성을 낮추고, 지역 허브 손상은 그렇지 않다.
  - Alstott et al. 2009 (PLoS Comput Biol 5:e1000408): 중심성이 높은 영역 손상이 전역 효과가 크다.

허브성 7종(정상 뇌 400영역, 구조 연결): degree, strength(가중), betweenness, 노드 전역 효율(harmonic closeness),
eigenvector, participation coefficient(PC, Yeo-7), within-module degree z(WMD, Yeo-7). 병변 허브성 = 병변 영역 평균.
병변 영향(재조직 없음): ΔE 전역 효율 손실, ΔQ 모듈성 변화(Yeo-7 고정 분할), ΔC 평균 군집 계수 변화.
표본: 국소 증후군 25개 + 공간적으로 인접한 무작위 병변 2,000개(크기는 증후군 크기 분포에서 추출).
비교: Spearman ρ, 크기 통제 부분 ρ, 크기+허브성 회귀의 추가 설명력(ΔR²), 지표 간 ρ 차이의 쌍대 bootstrap 95% CI.

실행 전 예측(선행 연구 기반):
  P1 ΔE: 경로 기반 허브성(betweenness·노드 효율)이 degree보다 잘 예측한다(Alstott).
  P2 ΔQ: PC가 가장 잘 예측한다(Gratton/Warren). 방향은 정적 구조 제거 모델에서 Gratton과 반대(연결자 제거 -> 모듈 간
     간선이 빠져 Q가 오른다)일 수 있다 -- Gratton의 효과는 기능 연결망의 동적 변화(diaschisis)라 이 모델이 재현하지 못할 수 있다.
  P3 WMD(지역 허브)는 ΔQ와 약하거나 반대 관계.

실행: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.hubness_types > out.json
"""

from __future__ import annotations

import json

import networkx as nx
import numpy as np
from scipy import stats

from scripts.reorganization_hypotheses import SRC, load
from scripts.short_long_term_reorganization import betweenness, global_eff

N_RAND = 2000
N_BOOT = 5000
SEED = 52
METRICS = ["degree", "strength", "betweenness", "nodal_eff", "eigenvector", "participation", "within_module_z"]


def node_metrics(g: nx.Graph, modules: dict) -> dict:
    n = 400
    w = np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy")
    deg = np.array([g.degree(i) for i in range(n)], float)
    strength = np.array([w[i][[j for j in g.neighbors(i)]].sum() for i in range(n)])
    btw = betweenness(g)
    from scipy.sparse.csgraph import shortest_path
    d = shortest_path(nx.to_scipy_sparse_array(g, nodelist=range(n)), unweighted=True, directed=False)
    with np.errstate(divide="ignore"):
        inv = np.where(d > 0, 1.0 / d, 0.0)
    nodal_eff = inv.sum(1) / (n - 1)
    eig = nx.eigenvector_centrality_numpy(g)
    pc, wmd_raw = np.zeros(n), np.zeros(n)
    for i in range(n):
        cnt: dict = {}
        for j in g.neighbors(i):
            cnt[modules[j]] = cnt.get(modules[j], 0) + 1
        k = deg[i]
        pc[i] = 1 - sum((c / k) ** 2 for c in cnt.values()) if k else 0.0
        wmd_raw[i] = cnt.get(modules[i], 0)
    wmd = np.zeros(n)
    for m in set(modules.values()):
        idx = [i for i in range(n) if modules[i] == m]
        v = wmd_raw[idx]
        wmd[idx] = (v - v.mean()) / (v.std() or 1.0)
    return {"degree": deg, "strength": strength, "betweenness": np.array([btw[i] for i in range(n)]), "nodal_eff": nodal_eff,
            "eigenvector": np.array([eig[i] for i in range(n)]), "participation": pc, "within_module_z": wmd}


def impact(g: nx.Graph, nodes, base: dict, comms: list) -> dict:
    h = g.copy()
    h.remove_nodes_from(nodes)
    cs = [c - set(nodes) for c in comms]
    cs = [c for c in cs if c]
    return {
        "dE": base["E"] - global_eff(h),
        "dQ": nx.community.modularity(h, cs) - base["Q"],
        "dC": nx.average_clustering(h) - base["C"],
    }


def partial_spearman(x, y, z) -> float:
    rx_, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
    ex = rx_ - np.polyval(np.polyfit(rz, rx_, 1), rz)
    ey = ry - np.polyval(np.polyfit(rz, ry, 1), rz)
    return float(stats.pearsonr(ex, ey)[0])


def delta_r2(y, size, x) -> float:
    def r2(cols):
        X = np.column_stack([np.ones(len(y))] + [stats.zscore(c) for c in cols])
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        res = y - X @ b
        return 1 - res @ res / ((y - y.mean()) @ (y - y.mean()))
    return float(r2([size, x]) - r2([size]))


def analyse(H: dict, Y: dict, size: np.ndarray, rng) -> dict:
    out = {}
    for yk, y in Y.items():
        row = {}
        for m in METRICS:
            x = H[m]
            row[m] = {"rho": float(stats.spearmanr(x, y)[0]), "partial_rho_size": partial_spearman(x, y, size),
                      "dR2_over_size": delta_r2(y, size, x)}
        best = max(METRICS, key=lambda m: abs(row[m]["partial_rho_size"]))
        # 최선 지표와 나머지의 |부분 ρ| 차이 bootstrap
        n = len(y)
        diffs = {m: [] for m in METRICS if m != best}
        for _ in range(N_BOOT if n < 100 else 1000):
            idx = rng.integers(0, n, n)
            pb = abs(partial_spearman(H[best][idx], y[idx], size[idx]))
            for m in diffs:
                diffs[m].append(pb - abs(partial_spearman(H[m][idx], y[idx], size[idx])))
        row["_best"] = best
        row["_best_minus_other_ci95"] = {m: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for m, v in diffs.items()}
        out[yk] = row
    return out


def main() -> None:
    g, dist, modules, lesions = load()
    rng = np.random.default_rng(SEED)
    M = node_metrics(g, modules)
    comms_d: dict = {}
    for i in range(400):
        comms_d.setdefault(modules[i], set()).add(i)
    comms = list(comms_d.values())
    base = {"E": global_eff(g), "Q": nx.community.modularity(g, comms), "C": nx.average_clustering(g)}
    sizes = [len(l["nodes"]) for l in lesions]
    sets = {"syndromes": [l["nodes"] for l in lesions]}
    rand = []
    for _ in range(N_RAND):
        k = int(rng.choice(sizes))
        s = int(rng.integers(400))
        rand.append(sorted(np.argsort(dist[s])[:k].tolist()))
    sets["contiguous_random"] = rand
    corr = {a: {b: float(stats.spearmanr(M[a], M[b])[0]) for b in METRICS} for a in METRICS}
    out = {"base": base, "metric_rank_corr": corr, "results": {}}
    for name, ls in sets.items():
        H = {m: np.array([M[m][l].mean() for l in ls]) for m in METRICS}
        imp = [impact(g, l, base, comms) for l in ls]
        Y = {k: np.array([r[k] for r in imp]) for k in ("dE", "dQ", "dC")}
        size = np.array([len(l) for l in ls], float)
        out["results"][name] = {"n": len(ls), "size_rho": {k: float(stats.spearmanr(size, v)[0]) for k, v in Y.items()},
                                "by_outcome": analyse(H, Y, size, rng),
                                "outcome_means": {k: float(v.mean()) for k, v in Y.items()}}
        if name == "syndromes":
            out["results"][name]["per_lesion"] = [{"name": l["name"], **{m: float(H[m][i]) for m in METRICS}, **imp[i]} for i, l in enumerate(lesions)]
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
