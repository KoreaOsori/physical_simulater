"""'정상 부하 지도 복원' 재검토(docs/52, 검토 의견 9번 -- 중요 지점).

검토 의견: headroom의 목표는 사실상 Target_i ≈ 정상 betweenness_i 이므로, 결과는 "정상 betweenness 분포를 복원했더니
강건성이 높아졌다"로 써야 하고 "뇌는 각 영역의 정상 용량을 유지하려 한다"로 일반화하면 안 된다.

여기서 세 가지를 직접 확인한다.
 (a) 복원 정도: 전략 12개(none, local, concentrated, distributed, random, headroom × 용량 정의 7)가 재조직 후
     정상 부하 지도를 얼마나 되살리나 -- 부하 지도 충실도 ρ(재조직 후 매개 중심성 vs 정상 매개 중심성, 생존 영역 Spearman),
     과부하 비율(부하 > 1.2 × 정상 부하).
 (b) 충실도가 무엇을 설명하나: 조건(전략 × 병변 300개) 전체에서 충실도와 각 강건성 지표의 관계(병변 고정효과 = 병변 안
     순위 상관의 평균). 연쇄 생존(용량 = 정상 부하 × 1.2)은 정의상 충실도와 얽혀 있으므로(순환) 따로 표시하고,
     순환과 무관한 지표 -- 전역 효율, 2차 타격 손실, W2 활동의존 마모 유지율, 정상 위상 이탈 -- 를 본다.
 (c) 순환 분리 검사(핵심): 실패 문턱이 '정상 부하 지도'가 아닐 때도 headroom(betweenness)이 이기는가.
     평가용 용량 c_i(λ) = m_λ · [(1−λ)·L0_i + λ·L̄0·p_i],  p = 대안 용량 프로필(평균 1; degree, 평균 제어성).
     m_λ는 '정상 뇌가 가장 빠듯한 영역에서도 20% 여유를 갖도록' 보정: m_λ = 1.2 · max_i L0_i / base_i(λ). (λ=0이면 기존과 같다.)
     예측(일치 원리): 이점이 '정상 부하 지도를 복원'하는 데서 온다면 λ가 커질수록 headroom(betweenness)의 이점이 줄고,
     λ=1에서는 그 프로필로 재조직한 headroom(p)이 가장 낫다.

W2 유지율은 기존 실행 결과를 재사용(같은 시드라 같은 그래프): capdef 캐시(none, local, distributed, headroom×7),
suite 캐시(concentrated, random:0).

실행: REUSE_CACHE=<docs/51 캐시> PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.normative_load_map > out.json
"""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import stats

from scripts.capacity_definition_sensitivity import DEFS, capacity_profiles
from scripts.fast_reorganize import N, btw_array, reorganize_fast, to_adj, to_graph
from scripts.null_network_distribution import cascade, global_eff
from scripts.reorganization_hypotheses import gini, load

FAMILIES = [("degree", 0.0), ("degree", 0.25), ("degree", 0.5), ("degree", 1.0), ("controllability", 0.5), ("controllability", 1.0)]
ALT = ["degree", "controllability"]


def topo(adj, alive, modules, with_local: bool = False) -> dict:
    """local_efficiency(networkx, 느림)는 기본으로 계산하지 않는다 -- 같은 그래프의 값이 docs/51 캐시에 있다(같은 그래프임을 확인)."""
    g = to_graph(adj, alive)
    b = btw_array(adj, alive)
    comms: dict = {}
    for x in g.nodes:
        comms.setdefault(modules[x], set()).add(x)
    e0 = global_eff(adj, alive)
    k = max(1, int(round(0.05 * alive.sum())))
    top = np.argsort(-np.where(alive, b, -1))[:k]
    a2 = alive.copy()
    a2[top] = False
    return {"global_eff": e0, "local_eff": nx.local_efficiency(g) if with_local else None, "load_gini": gini(b[alive]),
            "modularity": nx.community.modularity(g, list(comms.values())), "second_hit_eff_drop": (e0 - global_eff(adj, a2)) / e0}


def main() -> None:
    g, dist, modules, lesions = load()
    cache = Path(os.environ.get("REUSE_CACHE") or os.environ["REORG_CACHE"])  # docs/51 capdef·suite 캐시
    cp = capacity_profiles(g, modules)
    adj_full, alive_full = to_adj(g)
    L0 = btw_array(adj_full, alive_full)
    Lbar = L0.mean()
    lmax = float(np.percentile([dist[a, b] for a, b in g.edges], 75))
    caps = {d: np.array([cp["prof"][d][i] for i in range(N)]) for d in DEFS}
    prof = {d: caps[d] / caps[d].mean() for d in ALT}  # 평균 1

    def eval_caps():
        fams = {}
        for d, lam in FAMILIES:
            base = (1 - lam) * L0 + lam * Lbar * prof[d]
            m = 1.2 * float(np.max(L0 / base))
            fams[f"{d}:{lam}"] = (m * base, m)
        return fams

    fams = eval_caps()
    healthy = topo(adj_full, alive_full, modules, with_local=True)
    healthy_casc = {k: cascade(adj_full, alive_full, c) for k, (c, _) in fams.items()}
    conds = ["none", "local", "concentrated", "distributed", "random"] + [f"headroom:{d}" for d in DEFS]
    rows = []
    for li, les in enumerate(lesions):
        ls = set(les["nodes"])
        lost: dict = {}
        for a in ls:
            for b in g.neighbors(a):
                if b not in ls:
                    lost[b] = lost.get(b, 0) + 1
        alive = alive_full.copy()
        alive[list(ls)] = False
        adj = adj_full.copy()
        adj[list(ls), :] = False
        adj[:, list(ls)] = False
        capdef = json.loads((cache / f"capdef_{li}.json").read_text(encoding="utf-8"))["results"]
        suite = json.loads((cache / f"suite_focal_{li}.json").read_text(encoding="utf-8"))["results"]
        for c in conds:
            strat, d = (c.split(":") + [None])[:2]
            ar = reorganize_fast(adj, alive, lost, dist, lmax, strat, random.Random(li * 1000), caps[d] if d else caps["betweenness"])
            b = btw_array(ar, alive)
            r = {"lesion": li, "cond": c, **topo(ar, alive, modules)}
            r["loadmap_rho"] = float(stats.spearmanr(b[alive], L0[alive])[0])
            r["loadmap_l1"] = float(np.abs(b[alive] - L0[alive]).sum() / L0[alive].sum())
            r["overload_frac"] = float((b[alive] > 1.2 * L0[alive]).mean())
            for k, (cap, _) in fams.items():
                r[f"casc:{k}"] = cascade(ar, alive, cap)
            # 재사용 검증: 같은 시드로 다시 만든 그래프가 캐시의 그래프와 같은지(전역 효율 일치)
            ref = capdef.get(c) or {"concentrated": suite["concentrated"], "random": suite["random:0"]}[c]
            r["same_graph_as_cache"] = abs(ref["global_eff"] - r["global_eff"]) < 1e-9
            r["local_eff"] = ref["local_eff"]
            r["deviation"] = sum(abs(r[q] - healthy[q]) / abs(healthy[q]) for q in ("global_eff", "local_eff", "load_gini", "modularity"))
            if c in capdef:
                r["W2"] = capdef[c]["W2_activity_retained"]
            else:
                r["W2"] = suite["random:0" if c == "random" else c]["W2_retained"]
            rows.append(r)
        print(f"done {li}", file=sys.stderr, flush=True)

    keys = ["loadmap_rho", "loadmap_l1", "overload_frac", "global_eff", "second_hit_eff_drop", "W2", "deviation"] + [f"casc:{k}" for k in fams]
    table = {c: {k: float(np.mean([r[k] for r in rows if r["cond"] == c])) for k in keys} for c in conds}

    # (b) 병변 안 순위 상관(전략 12개)의 평균 = 병변 고정효과
    def within(xk: str, yk: str) -> dict:
        rs = []
        for li in range(len(lesions)):
            sub = [r for r in rows if r["lesion"] == li]
            rs.append(stats.spearmanr([r[xk] for r in sub], [r[yk] for r in sub])[0])
        rs = np.array(rs)
        return {"mean_rho": float(np.nanmean(rs)), "n_positive": int((rs > 0).sum()), "p_wilcoxon": float(stats.wilcoxon(rs).pvalue)}

    fidelity = {yk: within("loadmap_rho", yk) for yk in ["global_eff", "second_hit_eff_drop", "W2", "deviation", "casc:degree:0.0", "casc:degree:1.0", "casc:controllability:1.0"]}

    # (c) 순환 분리: 각 평가 용량에서 headroom(btw)과 다른 조건의 쌍대 차
    def paired(a: str, b: str, k: str) -> dict:
        x = np.array([r[k] for r in rows if r["cond"] == a])
        y = np.array([r[k] for r in rows if r["cond"] == b])
        d = x - y
        return {"diff": float(d.mean()), "a_higher": int((d > 0).sum()), "p": float(stats.wilcoxon(x, y).pvalue) if np.any(d != 0) else 1.0}

    sep = {}
    for k in fams:
        ranking = sorted(conds, key=lambda c: -table[c][f"casc:{k}"])
        sep[k] = {"m": fams[k][1], "healthy_survival": healthy_casc[k], "ranking": ranking[:5],
                  "headroom_btw_vs_distributed": paired("headroom:betweenness", "distributed", f"casc:{k}"),
                  "headroom_btw_vs_none": paired("headroom:betweenness", "none", f"casc:{k}"),
                  f"headroom_{k.split(':')[0]}_vs_headroom_btw": paired(f"headroom:{k.split(':')[0]}", "headroom:betweenness", f"casc:{k}")}
    print(json.dumps({"n_same_graph_as_cache": int(sum(r["same_graph_as_cache"] for r in rows)), "n_rows": len(rows), "healthy": healthy, "table": table, "fidelity_within_lesion": fidelity, "circularity_separation": sep, "rows": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
