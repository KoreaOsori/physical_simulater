"""R1-R5: 병변 후 네트워크 재조직 방식과 이후 취약성 (docs/50).

사용자 가설: "뇌 손상 후 신경가소성 단계에서 허브 부담을 균등하게 분배하면 이후 질환 가능성을 낮출 수 있을까
(정상 범위 수준으로)". 외부 의견은 이를 'Network Reorganization–Vulnerability Hypothesis'로 정식화했다.

이 스크립트는 그 가설을 **건강한 성인 평균 구조 커넥톰 위의 계산 실험(in silico)**으로 검증한다 --
환자 데이터가 아니므로 '질환 예방'은 직접 검증할 수 없고, 대리 지표(두 번째 손상 내성, 과부하 연쇄, 정상 범위
근접도)로만 본다.

- 커넥톰: HCP 합의 구조 연결 400×400 이진(Liu et al. 2023, docs/49에서 복구한 전체 5,059개 간선).
- 병변: 이 프로젝트의 국소 증후군 25개의 병변-증상 영역 집합(교육용 큐레이션, docs/33) + 같은 크기 무작위 병변.
- 재조직: 병변과 연결돼 있던 생존 영역(탈구심 영역)이 잃은 연결 수만큼 새 연결을 만든다(모든 전략 같은 예산,
  같은 배선 길이 제한 = 기존 간선 길이 75백분위 이하). 전략은 새 짝을 고르는 규칙만 다르다:
    none(재조직 없음) / random / local(가장 가까운 영역) / concentrated(현재 degree 최대 = 허브 집중) /
    distributed(현재 매개 부하 최소 = 부담 분산).
- 지표: 전역 효율(기능 대리), 매개 중심성 Gini·최대 점유율(부하 집중), 국소 효율(중복성·내결함성),
  모듈성 Q(Yeo-7 고정 분할), 정상 뇌 대비 편차.
- 취약성: (a) 두 번째 손상 = 재조직 후 매개 부하 상위 5% 영역 제거 시 전역 효율 감소율,
  (b) Motter & Lai 2002 과부하 연쇄 = 각 영역 용량을 '정상 뇌 부하 × (1+α)'로 두고 부하가 용량을 넘는 영역이
  연쇄적으로 탈락할 때 살아남는 영역 비율.

실행: backend/.venv/Scripts/python.exe -m scripts.reorganization_hypotheses > out.json
"""

from __future__ import annotations

import json
import os
import random
from multiprocessing import Pool
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "data" / "sources" / "human"
STRATEGIES = ["none", "random", "local", "concentrated", "distributed"]
ALPHA = 0.2  # 과부하 연쇄의 용량 여유(Motter & Lai 2002의 tolerance parameter)
TOP_FRAC = 0.05
N_RANDOM_SEEDS = 5


def load():
    d = json.loads((ROOT / "app" / "data" / "human_macro_connectome.json").read_text(encoding="utf-8"))
    regions = sorted(d["regions"], key=lambda r: int(r["id"]))
    sc = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy")
    dist = np.load(SRC / "liu2023_dist_400.npy")
    g = nx.from_numpy_array(sc)
    modules = {i: regions[i]["network"] for i in range(400)}
    lesions = [
        {"name": x["name"], "nodes": sorted(int(r) - 1 for r in x["region_ids"])}
        for x in d["known_disorders"]
        if x["category"] == "focal"
    ]
    return g, dist, modules, lesions


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    if x.sum() == 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def betweenness(g: nx.Graph) -> dict:
    return nx.betweenness_centrality(g, normalized=False)


def metrics(g: nx.Graph, modules: dict) -> dict:
    btw = betweenness(g)
    b = np.array(list(btw.values()))
    comms = {}
    for n in g.nodes:
        comms.setdefault(modules[n], set()).add(n)
    return {
        "global_eff": nx.global_efficiency(g),
        "local_eff": nx.local_efficiency(g),
        "load_gini": gini(b),
        "load_max_share": float(b.max() / b.sum()) if b.sum() else 0.0,
        "modularity": nx.community.modularity(g, list(comms.values())),
        "_btw": btw,
    }


def reorganize(g_lesioned: nx.Graph, lost: dict, dist: np.ndarray, lmax: float, strategy: str, rng: random.Random, capacity: dict | None = None) -> nx.Graph:
    """lost: 생존 영역 -> 병변 때문에 잃은 연결 수. 각 영역이 잃은 만큼 새 연결을 만든다(라운드로빈).

    headroom(R6, docs/50): '균등하게'가 아니라 '각 영역이 자기 정상 용량 대비 얼마나 여유 있는가' 기준 --
    현재 부하 / 정상 뇌 부하 기반 용량이 가장 낮은 영역에 붙인다(정상 범위 안에서의 분배)."""
    g = g_lesioned.copy()
    if strategy == "none":
        return g
    queue = [n for n, k in lost.items() for _ in range(k)]
    rng.shuffle(queue)
    btw = betweenness(g) if strategy in ("distributed", "headroom") else None
    added = 0
    for n in queue:
        cands = [t for t in g.nodes if t != n and not g.has_edge(n, t) and dist[n, t] <= lmax]
        if not cands:
            continue
        if strategy == "random":
            t = rng.choice(cands)
        elif strategy == "local":
            t = min(cands, key=lambda c: (dist[n, c], rng.random()))
        elif strategy == "concentrated":
            t = max(cands, key=lambda c: (g.degree(c), rng.random()))
        elif strategy == "headroom":
            t = min(cands, key=lambda c: ((btw[c] + 1.0) / (capacity[c] + 1.0), rng.random()))
        else:  # distributed
            t = min(cands, key=lambda c: (btw[c], g.degree(c), rng.random()))
        g.add_edge(n, t)
        added += 1
        if strategy in ("distributed", "headroom") and added % 10 == 0:
            btw = betweenness(g)  # 부하 지도를 주기적으로 갱신(매번 갱신은 계산 비용이 커서 10개마다)
    return g


def second_hit(g: nx.Graph, btw: dict) -> float:
    k = max(1, int(round(TOP_FRAC * g.number_of_nodes())))
    top = sorted(btw, key=btw.get, reverse=True)[:k]
    e0 = nx.global_efficiency(g)
    h = g.copy()
    h.remove_nodes_from(top)
    return float((e0 - nx.global_efficiency(h)) / e0)


def cascade(g: nx.Graph, capacity: dict) -> float:
    """Motter-Lai: 부하(매개 중심성)가 용량을 넘는 영역을 반복 제거. 살아남은 영역 비율(원래 400개 기준 아님, 시작 그래프 기준)."""
    h = g.copy()
    n0 = h.number_of_nodes()
    for _ in range(50):
        btw = betweenness(h)
        over = [n for n, L in btw.items() if L > capacity[n]]
        if not over:
            break
        h.remove_nodes_from(over)
    return h.number_of_nodes() / n0


def run_lesion(args) -> dict:
    lesion, seed, *rest = args
    strategies = rest[0] if rest else STRATEGIES
    g, dist, modules, _ = load()
    healthy = metrics(g, modules)
    capacity = {n: (1 + ALPHA) * L for n, L in healthy["_btw"].items()}
    lengths = [dist[a, b] for a, b in g.edges]
    lmax = float(np.percentile(lengths, 75))
    lesion_nodes = set(lesion["nodes"])
    lost = {}
    for a in lesion_nodes:
        for b in g.neighbors(a):
            if b not in lesion_nodes:
                lost[b] = lost.get(b, 0) + 1
    gl = g.copy()
    gl.remove_nodes_from(lesion_nodes)
    out = {
        "lesion": lesion["name"],
        "size": len(lesion_nodes),
        "edges_lost_by_survivors": sum(lost.values()),
        "lesion_mean_degree": float(np.mean([g.degree(n) for n in lesion_nodes])),
        "lesion_mean_btw": float(np.mean([healthy["_btw"][n] for n in lesion_nodes])),
        "strategies": {},
    }
    for strat in strategies:
        runs = []
        for s in range(N_RANDOM_SEEDS if strat in ("random",) else 1):
            rng = random.Random(seed * 1000 + s)
            gr = reorganize(gl, lost, dist, lmax, strat, rng, capacity)
            m = metrics(gr, modules)
            runs.append({
                "global_eff": m["global_eff"],
                "local_eff": m["local_eff"],
                "load_gini": m["load_gini"],
                "load_max_share": m["load_max_share"],
                "modularity": m["modularity"],
                "second_hit_eff_drop": second_hit(gr, m["_btw"]),
                "cascade_survival": cascade(gr, capacity),
                "edges_added": gr.number_of_edges() - gl.number_of_edges(),
            })
        out["strategies"][strat] = {k: float(np.mean([r[k] for r in runs])) for k in runs[0]}
    return out


def main() -> None:
    g, dist, modules, lesions = load()
    healthy = metrics(g, modules)
    capacity = {n: (1 + ALPHA) * L for n, L in healthy["_btw"].items()}
    healthy_out = {k: v for k, v in healthy.items() if not k.startswith("_")}
    healthy_out["second_hit_eff_drop"] = second_hit(g, healthy["_btw"])
    healthy_out["cascade_survival"] = cascade(g, capacity)

    rng = random.Random(7)
    jobs = [(les, i) for i, les in enumerate(lesions)]
    # 같은 크기 무작위 병변(R1 대조)
    rand_lesions = [{"name": f"random_{i}", "nodes": sorted(rng.sample(range(400), len(les["nodes"])))} for i, les in enumerate(lesions)]
    jobs += [(les, 100 + i) for i, les in enumerate(rand_lesions)]
    with Pool(7) as pool:
        results = pool.map(run_lesion, jobs)
    focal = results[: len(lesions)]
    rand = results[len(lesions):]

    # R1: 병변 크기 vs 병변의 허브성 -- 전역 효율 손실(재조직 없음)과의 편상관
    loss = np.array([healthy_out["global_eff"] - r["strategies"]["none"]["global_eff"] for r in focal])
    size = np.array([r["size"] for r in focal])
    hubness = np.array([r["lesion_mean_degree"] for r in focal])

    def partial(x, y, z):
        rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
        res = lambda a: a - np.polyval(np.polyfit(rz, a, 1), rz)  # noqa: E731
        return float(stats.pearsonr(res(rx), res(ry)).statistic)

    r1 = {
        "spearman_loss_vs_size": float(stats.spearmanr(size, loss).statistic),
        "spearman_loss_vs_hubness": float(stats.spearmanr(hubness, loss).statistic),
        "partial_loss_vs_hubness_given_size": partial(hubness, loss, size),
        "focal_vs_random_same_size": {
            "focal_mean_loss": float(loss.mean()),
            "random_mean_loss": float(np.mean([healthy_out["global_eff"] - r["strategies"]["none"]["global_eff"] for r in rand])),
            "focal_mean_gini": float(np.mean([r["strategies"]["none"]["load_gini"] for r in focal])),
            "random_mean_gini": float(np.mean([r["strategies"]["none"]["load_gini"] for r in rand])),
        },
    }

    # R2-R5: 전략 비교(국소 병변 25개를 표본으로, 쌍체 Wilcoxon)
    keys = ["global_eff", "load_gini", "load_max_share", "local_eff", "modularity", "second_hit_eff_drop", "cascade_survival"]
    table = {s: {k: float(np.mean([r["strategies"][s][k] for r in focal])) for k in keys} for s in STRATEGIES}

    def paired(a: str, b: str, k: str) -> dict:
        x = np.array([r["strategies"][a][k] for r in focal])
        y = np.array([r["strategies"][b][k] for r in focal])
        w = stats.wilcoxon(x, y) if np.any(x != y) else None
        return {"mean_diff": float((x - y).mean()), "a_better_count": int(np.sum(x > y)), "p": float(w.pvalue) if w else 1.0}

    comparisons = {k: paired("distributed", "concentrated", k) for k in keys}
    # R5: 정상 뇌 대비 편차(지표별 |Δ|/정상값의 합, 전역효율·국소효율·부하 Gini·모듈성)
    dev_keys = ["global_eff", "local_eff", "load_gini", "modularity"]
    deviation = {
        s: float(np.mean([sum(abs(r["strategies"][s][k] - healthy_out[k]) / abs(healthy_out[k]) for k in dev_keys) for r in focal]))
        for s in STRATEGIES
    }
    dev_pair = {}
    for a, b in (("distributed", "concentrated"), ("distributed", "local"), ("distributed", "none")):
        xa = [sum(abs(r["strategies"][a][k] - healthy_out[k]) / abs(healthy_out[k]) for k in dev_keys) for r in focal]
        xb = [sum(abs(r["strategies"][b][k] - healthy_out[k]) / abs(healthy_out[k]) for k in dev_keys) for r in focal]
        dev_pair[f"{a}_vs_{b}"] = {"a_closer_count": int(np.sum(np.array(xa) < np.array(xb))), "p": float(stats.wilcoxon(xa, xb).pvalue)}

    print(json.dumps({
        "healthy": healthy_out,
        "wiring_lmax_note": "new edges <= 75th percentile of existing edge lengths",
        "alpha": ALPHA,
        "r1": r1,
        "strategy_means": table,
        "distributed_vs_concentrated": comparisons,
        "deviation_from_healthy": deviation,
        "deviation_pairs": dev_pair,
        "per_lesion": focal,
    }, ensure_ascii=False))


def main_r6() -> None:
    """R6: 정상 용량 기준 분배(headroom)를 local·distributed와 같은 국소 병변 25개에서 비교."""
    g, dist, modules, lesions = load()
    healthy = metrics(g, modules)
    dev_keys = ["global_eff", "local_eff", "load_gini", "modularity"]
    strats = ["none", "local", "concentrated", "distributed", "headroom"]
    # 나머지 전략은 결정적(같은 시드)이라 기본 실행 결과(REORG_PREV json)를 재사용하고 headroom만 새로 계산 -- 메모리·시간 절약
    prev = {r["lesion"]: r for r in json.loads(Path(os.environ["REORG_PREV"]).read_text(encoding="utf-8"))["per_lesion"]}
    with Pool(int(os.environ.get("REORG_PROCS", "7"))) as pool:
        res = pool.map(run_lesion, [(les, i, ["headroom"]) for i, les in enumerate(lesions)])
    for r in res:
        r["strategies"].update({s: v for s, v in prev[r["lesion"]]["strategies"].items() if s != "headroom"})
    keys = ["global_eff", "load_gini", "local_eff", "second_hit_eff_drop", "cascade_survival"]
    table = {s: {k: float(np.mean([r["strategies"][s][k] for r in res])) for k in keys} for s in strats}
    dev = {s: [sum(abs(r["strategies"][s][k] - healthy[k]) / abs(healthy[k]) for k in dev_keys) for r in res] for s in strats}
    pairs = {}
    for other in ("local", "concentrated", "distributed", "none"):
        for k in keys:
            x = np.array([r["strategies"]["headroom"][k] for r in res])
            y = np.array([r["strategies"][other][k] for r in res])
            pairs[f"headroom_vs_{other}:{k}"] = {"mean_diff": float((x - y).mean()), "headroom_higher": int((x > y).sum()), "p": float(stats.wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0}
        pairs[f"headroom_vs_{other}:deviation"] = {"headroom_closer": int((np.array(dev["headroom"]) < np.array(dev[other])).sum()), "p": float(stats.wilcoxon(dev["headroom"], dev[other]).pvalue)}
    print(json.dumps({"table": table, "deviation_mean": {s: float(np.mean(v)) for s, v in dev.items()}, "pairs": pairs}, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    main_r6() if "--r6" in sys.argv else main()
