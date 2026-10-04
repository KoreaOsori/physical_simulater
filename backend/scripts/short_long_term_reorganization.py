"""단기 효율 vs 장기 강건성 시뮬레이터(docs/51, H16-2 확장).

H16-2는 재조직이 '끝난 뒤' 효율만 비교했다(허브 집중 0.4507 vs 분산 0.4488, p=0.33). '빨리 회복'은 재지 않았다.
여기서는 시간을 두 축으로 나눈다.

단기(회복 속도): 잃은 연결을 하나씩 다시 붙이는 동안 전역 효율을 예산 10/25/50/100% 시점에 기록 -> 회복 곡선 넓이(AUC).
장기(마모): 재조직이 끝난 네트워크를 T개 시기 동안 굴린다. 매 시기 각 영역이 확률적으로 기능을 잃고(제거), 부하가 재분배된다.
  마모 모델 3개(결론이 모델 선택에 좌우되는지 보려고):
    W1 과부하형   p = P1 * ((부하+1)/(정상 용량+1))^2   -- 자기 정상 용량 대비 초과 부하가 손상을 부름(Motter-Lai 계열).
                  주의: headroom 전략이 최적화하는 양과 같아 headroom에 유리한 '순환성'이 있다.
    W2 활동의존형 p = P2 * (부하 / 정상 뇌 평균 부하)  -- 절대 부하가 큰(많이 쓰이는) 영역이 닳음
                  (de Haan et al. 2012, 활동 의존적 퇴행이 허브 취약성을 설명).
    W3 무작위     p = P3                              -- 부하와 무관한 노화(대조군).
  세 모델 모두 '정상 뇌'가 시기당 평균 약 2개 영역을 잃도록 보정. 지표: 원래 400개 기준 효율(생존 쌍만 기여) -- 시기 T의 값, 곡선 넓이.

실행 전 예측(docs/51):
  S1 단기: 허브 집중이 초기(예산 25%) 효율 회복이 가장 빠르다.
  L1 장기: W1·W2에서 허브 집중이 가장 빨리 무너지고, headroom/분산이 가장 오래 버틴다. W3에선 차이가 작다.
  X  역전: 단기 순위와 장기 순위가 반대 방향이다.

실행: REORG_PROCS=3 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.short_long_term_reorganization > out.json
"""

from __future__ import annotations

import json
import os
import random
import sys
from multiprocessing import Pool

import networkx as nx
import numpy as np
import rustworkx as rx
from scipy import stats
from scipy.sparse.csgraph import shortest_path

import scripts.reorganization_hypotheses as rh
from scripts.reorganization_hypotheses import ALPHA, load, reorganize


# 속도: networkx 순수 Python 대신 rustworkx(매개 중심성)·scipy(최단경로). 같은 그래프에서 networkx와 값이 일치함을
# 확인(betweenness 최대 차 5e-13, 효율 차 3e-13) -- 약 20배 빠름. 분석 스크립트 전용 의존성(서버 requirements에는 없음).
def betweenness(g: nx.Graph) -> dict:
    nodes = list(g.nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    r = rx.PyGraph()
    r.add_nodes_from(nodes)
    r.add_edges_from_no_data([(idx[a], idx[b]) for a, b in g.edges])
    b = rx.graph_betweenness_centrality(r, normalized=False, parallel_threshold=10**9)
    return {nodes[i]: float(v) for i, v in b.items()}


def global_eff(g: nx.Graph) -> float:
    n = g.number_of_nodes()
    if n < 2:
        return 0.0
    d = shortest_path(nx.to_scipy_sparse_array(g), unweighted=True, directed=False)
    off = ~np.eye(n, dtype=bool)
    return float((1.0 / d[off]).sum() / (n * (n - 1)))


rh.betweenness = betweenness  # reorganize()의 분산/headroom 부하 재계산에도 같은 빠른 구현 사용

STRATS = ["none", "local", "concentrated", "distributed", "headroom"]
CHECKPOINTS = [0.1, 0.25, 0.5, 1.0]
T_EPOCHS = 20
N_REPS = 8
WEAR = ["W1_overload", "W2_activity", "W3_random"]
N0 = 400


def abs_eff(h: nx.Graph) -> float:
    """원래 400개 영역 기준 효율: 살아남은 쌍의 1/거리 합 / (400*399). 영역을 잃으면 반드시 낮아진다."""
    n = h.number_of_nodes()
    if n < 2:
        return 0.0
    return global_eff(h) * n * (n - 1) / (N0 * (N0 - 1))


def calibrate(g: nx.Graph, cap: dict, L0: dict) -> dict:
    mean_L0 = float(np.mean(list(L0.values())))
    s1 = np.mean([((L0[n] + 1) / (cap[n] + 1)) ** 2 for n in g])
    return {"P1": 2.0 / (N0 * s1), "P2": 2.0 / N0, "P3": 2.0 / N0, "mean_L0": mean_L0}


def wear_run(g0: nx.Graph, model: str, cap: dict, cal: dict, rng: np.random.Generator) -> list[float]:
    h = g0.copy()
    traj = [abs_eff(h)]
    for _ in range(T_EPOCHS):
        if h.number_of_nodes() < 2:
            traj.append(0.0)
            continue
        nodes = list(h.nodes)
        if model == "W3_random":
            p = np.full(len(nodes), cal["P3"])
        else:
            btw = betweenness(h)
            if model == "W1_overload":
                p = np.array([cal["P1"] * ((btw[n] + 1) / (cap[n] + 1)) ** 2 for n in nodes])
            else:
                p = np.array([cal["P2"] * btw[n] / cal["mean_L0"] for n in nodes])
        dead = [n for n, pi in zip(nodes, np.minimum(p, 1.0)) if rng.random() < pi]
        h.remove_nodes_from(dead)
        traj.append(abs_eff(h))
    return traj


def run_one(args) -> dict:
    lesion, seed = args
    g, dist, _, _ = load()
    L0 = betweenness(g)
    cap = {n: (1 + ALPHA) * L for n, L in L0.items()}
    cal = calibrate(g, cap, L0)
    lmax = float(np.percentile([dist[a, b] for a, b in g.edges], 75))
    les = set(lesion["nodes"])
    lost: dict = {}
    for a in les:
        for b in g.neighbors(a):
            if b not in les:
                lost[b] = lost.get(b, 0) + 1
    total = sum(lost.values())
    gl = g.copy()
    gl.remove_nodes_from(les)
    e_les = global_eff(gl)
    out = {"lesion": lesion["name"], "size": len(les), "edges_to_regrow": total, "strategies": {}}
    for strat in STRATS:
        marks = {max(1, int(round(c * total))): c for c in CHECKPOINTS}
        curve = {0.0: e_les}

        def on_edge(added, gg, *_, marks=marks, curve=curve):
            if added in marks:
                curve[marks[added]] = global_eff(gg)

        gr = reorganize(gl, lost, dist, lmax, strat, random.Random(seed * 1000), cap, on_edge if strat != "none" else None)
        e_final = global_eff(gr)
        for c in CHECKPOINTS:
            curve.setdefault(c, e_final if strat != "none" else e_les)
        xs = [0.0, *CHECKPOINTS]
        ys = [curve[x] for x in xs]
        short = {f"eff_at_{int(c * 100)}pct": curve[c] for c in CHECKPOINTS}
        short["recovery_auc"] = float(np.trapezoid(np.array(ys) - e_les, xs))
        long = {}
        for w in WEAR:
            rng = np.random.default_rng(seed * 7919 + WEAR.index(w))
            trajs = np.array([wear_run(gr, w, cap, cal, rng) for _ in range(N_REPS)])
            m = trajs.mean(axis=0)
            long[w] = {"eff_T": float(m[-1]), "retained_frac": float(m[-1] / m[0]), "auc": float(np.trapezoid(m) / T_EPOCHS), "start": float(m[0])}
        out["strategies"][strat] = {"short": short, "long": long}
    print(f"done {lesion['name']}", file=sys.stderr, flush=True)
    return out


def healthy_reference() -> dict:
    g, _, _, _ = load()
    L0 = betweenness(g)
    cap = {n: (1 + ALPHA) * L for n, L in L0.items()}
    cal = calibrate(g, cap, L0)
    ref = {"global_eff": global_eff(g)}
    for w in WEAR:
        rng = np.random.default_rng(99 + WEAR.index(w))
        trajs = np.array([wear_run(g, w, cap, cal, rng) for _ in range(N_REPS * 2)])
        m = trajs.mean(axis=0)
        ref[w] = {"eff_T": float(m[-1]), "retained_frac": float(m[-1] / m[0]), "auc": float(np.trapezoid(m) / T_EPOCHS), "start": float(m[0])}
    return ref


def paired(res: list, get, a: str, b: str) -> dict:
    x = np.array([get(r["strategies"][a]) for r in res])
    y = np.array([get(r["strategies"][b]) for r in res])
    return {"mean_diff": float((x - y).mean()), "a_higher": int((x > y).sum()), "p": float(stats.wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0}


def main() -> None:
    _, _, _, lesions = load()
    with Pool(int(os.environ.get("REORG_PROCS", "3"))) as pool:
        async_ref = pool.apply_async(healthy_reference)
        res = pool.map(run_one, [(les, i) for i, les in enumerate(lesions)])
        ref = async_ref.get()
    short_keys = [f"eff_at_{int(c * 100)}pct" for c in CHECKPOINTS] + ["recovery_auc"]
    summary = {
        s: {
            "short": {k: float(np.mean([r["strategies"][s]["short"][k] for r in res])) for k in short_keys},
            "long": {w: {k: float(np.mean([r["strategies"][s]["long"][w][k] for r in res])) for k in ("start", "eff_T", "retained_frac", "auc")} for w in WEAR},
        }
        for s in STRATS
    }
    tests = {}
    for a, b in [("concentrated", "distributed"), ("concentrated", "headroom"), ("concentrated", "local"), ("headroom", "distributed"), ("headroom", "none")]:
        tests[f"{a}_vs_{b}"] = {
            "short_eff25": paired(res, lambda v: v["short"]["eff_at_25pct"], a, b),
            "short_auc": paired(res, lambda v: v["short"]["recovery_auc"], a, b),
            **{f"long_{w}_retained": paired(res, lambda v, w=w: v["long"][w]["retained_frac"], a, b) for w in WEAR},
            **{f"long_{w}_effT": paired(res, lambda v, w=w: v["long"][w]["eff_T"], a, b) for w in WEAR},
        }
    # X: 병변마다 전략 5개의 단기 순위와 장기 순위의 상관(음수면 역전)
    inversion = {}
    for w in WEAR:
        rhos = []
        for r in res:
            s_short = [r["strategies"][s]["short"]["recovery_auc"] for s in STRATS if s != "none"]
            s_long = [r["strategies"][s]["long"][w]["retained_frac"] for s in STRATS if s != "none"]
            rhos.append(stats.spearmanr(s_short, s_long)[0])
        rhos = np.array(rhos, dtype=float)
        inversion[w] = {"median_rho": float(np.nanmedian(rhos)), "n_negative": int((rhos < 0).sum()), "wilcoxon_p_vs0": float(stats.wilcoxon(rhos[~np.isnan(rhos)]).pvalue)}
    print(json.dumps({"healthy": ref, "summary": summary, "tests": tests, "inversion": inversion, "per_lesion": res}, ensure_ascii=False))


if __name__ == "__main__":
    main()
