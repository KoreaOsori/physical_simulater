"""H2-1 분석 (docs/48): worm-silence-all 결과(JSON 경로 인자)와 연구소 위상 도구의 중심성을 비교한다.

중심성은 app/lab/topology.analyze_topology와 같은 방식(방향 그래프, degree/betweenness/PageRank 정규화 평균)
-- H2에서 DVA/RIPL/RIPR을 고른 바로 그 기준.
기능 영향 = 두 자극(내리막: AWC·ASER OFF / 오르막: ASEL ON)에서 AVA·AVB 발화 변화량 합 + 결정(반전/직진) 뒤집힘.
"""

from __future__ import annotations

import json
import sys

import networkx as nx
import numpy as np
from scipy import stats

from app.data.celegans_connectome import get_connectome


def main(path: str) -> None:
    data = json.loads(open(path, encoding="utf-8").read())
    conn = get_connectome()
    ids = {n.id for n in conn.neurons}
    g = nx.DiGraph()
    g.add_nodes_from(ids)
    for s in conn.synapses:
        if s.pre in ids and s.post in ids:
            if g.has_edge(s.pre, s.post):
                g[s.pre][s.post]["weight"] += s.weight
            else:
                g.add_edge(s.pre, s.post, weight=s.weight)
    deg = dict(g.degree())
    mx = max(deg.values())
    btw = nx.betweenness_centrality(g, weight=None)
    pr = nx.pagerank(g, weight="weight")

    def norm(d):
        lo, hi = min(d.values()), max(d.values())
        return {k: (v - lo) / (hi - lo) for k, v in d.items()}

    nd, nb, np_ = norm({k: v / mx for k, v in deg.items()}), norm(btw), norm(pr)
    combined = {k: (nd[k] + nb[k] + np_[k]) / 3 for k in ids}
    rank = {k: i + 1 for i, k in enumerate(sorted(ids, key=lambda k: -combined[k]))}

    base = data["baseline"]
    decide = lambda ava, avb: "P" if ava > avb and ava > 0 else "R"  # noqa: E731
    rows = []
    for r in data["rows"]:
        (da, db, dn), (ua, ub, un) = r["down"], r["up"]
        impact = abs(da - base["down"][0]) + abs(db - base["down"][1]) + abs(ua - base["up"][0]) + abs(ub - base["up"][1])
        flips = int(decide(da, db) != decide(*base["down"][:2])) + int(decide(ua, ub) != decide(*base["up"][:2]))
        rows.append({"neuron": r["neuron"], "impact": impact, "flips": flips, "down": r["down"], "up": r["up"], "combined": combined[r["neuron"]], "rank": rank[r["neuron"]], "degree": deg[r["neuron"]], "betweenness": btw[r["neuron"]]})

    imp = np.array([r["impact"] for r in rows])
    out = {"baseline": base, "n": len(rows), "n_with_any_impact": int((imp > 0).sum()), "n_with_decision_flip": int(sum(r["flips"] > 0 for r in rows))}
    for key in ("combined", "degree", "betweenness"):
        v = np.array([r[key] for r in rows])
        s = stats.spearmanr(v, imp)
        out[f"spearman_{key}"] = {"rho": float(s.statistic), "p": float(s.pvalue)}
    top = sorted(rows, key=lambda r: r["rank"])
    out["top15_central"] = [{k: r[k] for k in ("neuron", "rank", "impact", "flips")} for r in top[:15]]
    out["top_impact"] = [{k: r[k] for k in ("neuron", "rank", "impact", "flips", "down", "up")} for r in sorted(rows, key=lambda r: -r["impact"])[:15]]
    out["h2_neurons"] = [{k: r[k] for k in ("neuron", "rank", "impact", "flips")} for r in rows if r["neuron"] in ("DVA", "RIPL", "RIPR")]
    top30 = top[:30]
    out["top30_central_with_impact"] = sum(r["impact"] > 0 for r in top30)
    rest = [r for r in rows if r["rank"] > 30]
    out["rest_with_impact_frac"] = sum(r["impact"] > 0 for r in rest) / len(rest)
    # 조건부 비율의 정확 검정(상위 30 중심 뉴런 vs 나머지)
    a, b = out["top30_central_with_impact"], 30 - out["top30_central_with_impact"]
    c = sum(r["impact"] > 0 for r in rest)
    d = len(rest) - c
    out["fisher_top30_vs_rest"] = {"odds_ratio": float(stats.fisher_exact([[a, b], [c, d]])[0]), "p": float(stats.fisher_exact([[a, b], [c, d]])[1])}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
