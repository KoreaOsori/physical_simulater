"""H17 결과가 '집단 대표 커넥톰을 어떻게 만들었느냐'에 좌우되나(docs/53, 검토 의견 8번).

지금까지의 '정상 부하 지도' L0는 33명 HCP 피험자의 거리 보정 합의(consensus) 이진 행렬 하나의 betweenness다
(Liu et al. 2023). 검토 의견: 이것은 '특정 정상 뇌'가 아니라 '정상 집단 대표 커넥톰'의 부하 지도다.
개인별 행렬이 없어도 확인할 수 있는 것:

  A. 대표 행렬의 밀도: 합의 간선 중 평균 가중치(sc_avggm) 상위 75%·50%만 남긴 더 엄격한 대표 행렬(둘 다 연결됨)에서
     L0를 다시 구하고 H17 핵심 비교(정상 부하 지도 기반 vs 균등 분산·무작위·허브 집중·없음)를 반복.
  B. 부하의 정의: 같은 합의 행렬에서 가중 betweenness(길이 = 1/평균 가중치; 신호가 강한 연결을 선호한다는 가정)를 구해
     이진 L0와 비교하고, 실패 문턱이 가중 부하 지도를 따를 때(정상 뇌가 20% 여유를 갖게 보정) 이점이 남는지 본다.
     -- H17-1의 λ 분석과 같은 틀이지만, 대안 프로필이 임의의 중심성이 아니라 '같은 연결망의 또 다른 그럴듯한 부하 정의'다.
  C. 대표 행렬 간 L0 일치도: Spearman, 상위 5% 허브 겹침.

실행 전 예측: L0는 밀도·정의를 바꿔도 순위가 대체로 유지되고(ρ > 0.8), H17의 연쇄 이점도 방향이 유지된다.
가중 부하 문턱에서는 이점이 줄어든다(H17-1처럼 문턱 모양이 이진 L0에서 벗어나므로).

실행: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.consensus_representation_sensitivity > out.json
"""

from __future__ import annotations

import json
import random
import sys

import networkx as nx
import numpy as np
from scipy import stats

from scripts.fast_reorganize import N, btw_array, reorganize_fast
from scripts.null_network_distribution import cascade, global_eff
from scripts.reorganization_hypotheses import SRC, load

STRATS = ["none", "random", "concentrated", "distributed", "headroom"]


def lesion_setup(adj_full, les):
    ls = set(les)
    lost: dict = {}
    for a in ls:
        for b in np.flatnonzero(adj_full[a]):
            if int(b) not in ls:
                lost[int(b)] = lost.get(int(b), 0) + 1
    alive = np.ones(N, dtype=bool)
    alive[list(ls)] = False
    adj = adj_full.copy()
    adj[list(ls), :] = False
    adj[:, list(ls)] = False
    return adj, alive, lost


def run_rep(adj_full, dist, lmax, lesions, eval_caps: dict) -> dict:
    """한 대표 행렬에서 전략 5개 × 병변 25개. eval_caps: 이름 -> 실패 문턱 배열."""
    L0 = btw_array(adj_full, np.ones(N, dtype=bool))
    rows = []
    for li, les in enumerate(lesions):
        adj, alive, lost = lesion_setup(adj_full, les["nodes"])
        for s in STRATS:
            ar = reorganize_fast(adj, alive, lost, dist, lmax, s, random.Random(li * 1000), 1.2 * L0)
            b = btw_array(ar, alive)
            r = {"lesion": li, "strategy": s, "global_eff": global_eff(ar, alive),
                 "loadmap_rho": float(stats.spearmanr(b[alive], L0[alive])[0])}
            for k, cap in eval_caps.items():
                r[f"casc:{k}"] = cascade(ar, alive, cap)
            rows.append(r)
        print(f"  lesion {li}", file=sys.stderr, flush=True)
    keys = [k for k in rows[0] if k not in ("lesion", "strategy")]
    table = {s: {k: float(np.mean([r[k] for r in rows if r["strategy"] == s])) for k in keys} for s in STRATS}
    paired = {}
    for o in ("distributed", "random", "concentrated", "none"):
        for k in [k for k in keys if k.startswith("casc:")]:
            x = np.array([r[k] for r in rows if r["strategy"] == "headroom"])
            y = np.array([r[k] for r in rows if r["strategy"] == o])
            d = x - y
            paired[f"headroom-{o}|{k}"] = {"diff": float(d.mean()), "higher": int((d > 0).sum()), "n": len(d),
                                           "p": float(stats.wilcoxon(x, y).pvalue) if np.any(d != 0) else 1.0}
    return {"table": table, "paired": paired}


def main() -> None:
    g, dist, _, lesions = load()
    cons = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
    np.fill_diagonal(cons, False)
    w = np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy")
    iu = np.triu_indices(N, 1)
    lmax = float(np.percentile(dist[iu][cons[iu]], 75))  # 배선 길이 제한은 원래 합의 행렬 기준(해부학적 제약)으로 고정
    all_alive = np.ones(N, dtype=bool)

    reps = {"cons100": cons}
    wv = w[iu][cons[iu]]
    for q in (0.75, 0.5):
        thr = np.quantile(wv, 1 - q)
        reps[f"cons{int(q * 100)}"] = (w >= thr) & cons
    L = {k: btw_array(a, all_alive) for k, a in reps.items()}

    # B. 가중 부하(길이 = 1/평균 가중치)
    gw = nx.Graph()
    gw.add_nodes_from(range(N))
    for a, b in zip(*np.nonzero(np.triu(cons, 1))):
        gw.add_edge(int(a), int(b), length=1.0 / w[a, b])
    bw = nx.betweenness_centrality(gw, normalized=False, weight="length")
    Lw = np.array([bw[i] for i in range(N)])
    print("weighted betweenness done", file=sys.stderr, flush=True)

    def agree(a, b):
        k = int(round(0.05 * N))
        ta, tb = set(np.argsort(-a)[:k]), set(np.argsort(-b)[:k])
        return {"spearman": float(stats.spearmanr(a, b)[0]), "top5pct_overlap": len(ta & tb) / k}

    out = {"edges": {k: int(a[iu].sum()) for k, a in reps.items()},
           "agreement": {f"{a}~{b}": agree(L[a], L[b]) for a, b in (("cons100", "cons75"), ("cons100", "cons50"), ("cons75", "cons50"))}}
    out["agreement"]["cons100~weighted"] = agree(L["cons100"], Lw)
    out["weighted_zero_frac"] = float((Lw == 0).mean())

    # 가중 부하 지도를 따르는 실패 문턱(이진 부하가 실제 부하일 때, 정상 뇌가 가장 빠듯한 영역에서도 20% 여유)
    L0 = L["cons100"]
    caps_main = {"m1.2": 1.2 * L0}
    for lam in (0.25, 0.5, 1.0):
        base = (1 - lam) * L0 + lam * Lw * (L0.mean() / Lw.mean())
        base = np.maximum(base, 1e-9)
        m = 1.2 * float(np.max(L0 / base))
        caps_main[f"weighted{lam}"] = m * base
        out.setdefault("weighted_caps_m", {})[f"weighted{lam}"] = m
    print("rep cons100", file=sys.stderr, flush=True)
    out["cons100"] = run_rep(cons, dist, lmax, lesions, caps_main)
    for k in ("cons75", "cons50"):
        print(f"rep {k}", file=sys.stderr, flush=True)
        out[k] = run_rep(reps[k], dist, lmax, lesions, {"m1.2": 1.2 * L[k]})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
