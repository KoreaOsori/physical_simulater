"""실제 반복 촬영 잡음을 docs/59의 촬영 잡음 ε 곡선 위에 놓기 (docs/60, H17-13 후속).

docs/59 결론: 손상 후 촬영으로 병전 지도를 채워 넣는 방법은 촬영 잡음에 막힌다(실제 MICA 50명에서
ε=5% −17%, 2% +12%, 0% +92%). 그런데 ε=5%는 가정이었다. 여기서 실제 반복 촬영으로 ε를 잰다.

데이터: Zenodo 14017270 (Barjuan et al. 2024, CC-BY 4.0) HCP 반복 촬영 표본 44건, Lausanne 분할.
  - 세션 표시가 없다. 집단 평균을 뺀 연결 패턴의 상호 최근접으로 반복 촬영 짝을 추론한다
    (두 해상도에서 같은 짝, 짝 상관 z ≥ 3.4). 짝 없는 4건은 뺀다.
  - 분할이 Schaefer-400이 아니므로 병변·재조직 계산에 직접 쓰지 않고, 잡음 크기만 잰다.

비교 방법(같은 것끼리 비교)
  실제: 두 번 촬영(각각 잡음 포함)을 같은 밀도(Liu 합의와 같은 6.34%)로 이진화해
        (a) 간선 교체율 = |A \\ B| / k, (b) 영역별 부하(매개 중심성) Spearman, (c) 상위 5% 허브 일치율.
        사람 사이(짝이 아닌 쌍) 값도 같이 잰다.
  모의: MICA 50명 각자에 docs/59의 perturb(ε)를 독립적으로 두 번 넣어 같은 세 지표를 잰다.
  보정 1(교체율 비): 실제의 (반복/사람 사이) 교체율 비 × MICA 사람 사이 교체율 → MICA 척도의 반복 교체율
                    → 모의에서 그 교체율을 내는 ε. 파이프라인 차이(분할·추적 방법)를 비로 상쇄한다.
  보정 2(부하 재현성): 모의 두 사본의 부하 Spearman이 실제 반복 촬영의 부하 Spearman과 같아지는 ε.

실행: MICA_DIR=../mica-mics-master/_extracted HCP_DIR=../zenodo-14017270/HCP/data_nobrainstem \
      PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.test_retest_noise > out.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import rustworkx as rx
from scipy import stats

from scripts.premorbid_map_estimation import load_real_cohort
from scripts.synthetic_individual_cohort import IU, Base, perturb

DENSITY = None  # Base()의 합의 밀도로 정한다
LAYERS = {1: 462, 2: 233}  # Lausanne 해상도(뇌간 제외 영역 수 +1 = 파일의 노드 수)
EPS_GRID = (0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20)
N_SIM_REP = 2


def betweenness(vec: np.ndarray, n: int) -> np.ndarray:
    iu = np.triu_indices(n, 1)
    r = rx.PyGraph()
    r.add_nodes_from(range(n))
    on = np.flatnonzero(vec)
    r.add_edges_from_no_data(list(zip(iu[0][on].tolist(), iu[1][on].tolist())))
    bc = rx.graph_betweenness_centrality(r, normalized=False)
    out = np.zeros(n)
    for i, v in bc.items():
        out[i] = v
    return out


def pair_stats(a: np.ndarray, b: np.ndarray, la: np.ndarray, lb: np.ndarray) -> dict:
    k = max(int(a.sum()), 1)
    h = max(1, int(round(0.05 * len(la))))
    return {"swap": float((a & ~b).sum() / k), "load_spearman": float(stats.spearmanr(la, lb)[0]),
            "hub_overlap": len(set(np.argsort(-la)[:h]) & set(np.argsort(-lb)[:h])) / h}


def summarize(rows: list[dict]) -> dict:
    return {key: {"mean": float(np.mean([r[key] for r in rows])), "sd": float(np.std([r[key] for r in rows], ddof=1)),
                  "n": len(rows)} for key in ("swap", "load_spearman", "hub_overlap")}


# ---------- 실제 반복 촬영(HCP, Lausanne) ----------

def load_hcp(root: str, layer: int, n: int, density: float) -> np.ndarray:
    iu = np.triu_indices(n, 1)
    k = int(round(density * len(iu[0])))
    vecs = []
    for s in range(44):
        e = np.loadtxt(Path(root) / f"HCP_nobrainstem_{s}_layer_{layer}_weight_edgelist.txt", skiprows=1)
        w = np.zeros((n, n))
        i, j = e[:, 0].astype(int), e[:, 1].astype(int)
        w[i, j] = w[j, i] = e[:, 3]
        wu = w[iu]
        v = np.zeros(len(wu), dtype=bool)
        v[np.argsort(-wu, kind="stable")[:k]] = True
        v &= wu > 0
        vecs.append(v)
    return np.array(vecs)


def infer_pairs(root: str) -> list[tuple[int, int]]:
    """집단 평균을 뺀 log 가중치 패턴의 상호 최근접 짝(layer 2와 1에서 같아야 채택)."""
    found = []
    for layer, n in LAYERS.items():
        iu = np.triu_indices(n, 1)
        rows = []
        for s in range(44):
            e = np.loadtxt(Path(root) / f"HCP_nobrainstem_{s}_layer_{layer}_weight_edgelist.txt", skiprows=1)
            w = np.zeros((n, n))
            i, j = e[:, 0].astype(int), e[:, 1].astype(int)
            w[i, j] = w[j, i] = e[:, 3]
            rows.append(w[iu])
        v = np.log1p(np.array(rows) * 1e4)
        c = np.corrcoef(v - v.mean(0))
        np.fill_diagonal(c, -np.inf)
        nn = c.argmax(1)
        found.append({(a, int(nn[a])) for a in range(44) if nn[nn[a]] == a and a < nn[a]})
    return sorted(found[0] & found[1])


def real_retest(root: str, density: float) -> dict:
    pairs = infer_pairs(root)
    paired = {x for p in pairs for x in p}
    out = {"pairs": pairs, "n_pairs": len(pairs), "unpaired": sorted(set(range(44)) - paired), "layers": {}}
    for layer, n in LAYERS.items():
        vecs = load_hcp(root, layer, n, density)
        L = [betweenness(v, n) for v in vecs]
        rr = [pair_stats(vecs[a], vecs[b], L[a], L[b]) for a, b in pairs]
        idx = sorted(paired)
        pset = set(pairs)
        bs = [pair_stats(vecs[a], vecs[b], L[a], L[b]) for ii, a in enumerate(idx) for b in idx[ii + 1:]
              if (a, b) not in pset]
        out["layers"][layer] = {"n": n, "retest": summarize(rr), "between": summarize(bs)}
        print(f"HCP layer {layer} done", file=sys.stderr, flush=True)
    return out


# ---------- 모의 잡음(MICA, Schaefer-400) ----------

def simulated(root: str, base: Base, n_edges: int) -> dict:
    _, vecs = load_real_cohort(root, n_edges)
    vecs = np.array(vecs)
    n = 400
    L = [betweenness(v, n) for v in vecs]
    bs = [pair_stats(vecs[a], vecs[b], L[a], L[b]) for a in range(len(vecs)) for b in range(a + 1, len(vecs))]
    out = {"n_subjects": len(vecs), "between": summarize(bs), "eps": {}}
    rng = np.random.default_rng(60)
    for eps in EPS_GRID:
        rows = []
        for s, v in enumerate(vecs):
            for _ in range(N_SIM_REP):
                a = perturb(base, v, eps, rng) if eps else v.copy()
                b = perturb(base, v, eps, rng) if eps else v.copy()
                rows.append(pair_stats(a, b, betweenness(a, n), betweenness(b, n)))
        out["eps"][str(eps)] = summarize(rows)
        print(f"MICA eps {eps} done", file=sys.stderr, flush=True)
    return out


def invert(grid: dict, key: str, target: float) -> float | None:
    """모의 곡선(ε → 지표 평균)에서 target을 내는 ε를 선형 보간으로 찾는다."""
    xs = [float(e) for e in grid]
    ys = [grid[e][key]["mean"] for e in grid]
    for x0, x1, y0, y1 in zip(xs, xs[1:], ys, ys[1:]):
        if (y0 - target) * (y1 - target) <= 0 and y0 != y1:
            return x0 + (target - y0) * (x1 - x0) / (y1 - y0)
    return None


def main() -> None:
    base = Base()
    n_edges = int(base.cons[IU].sum())
    density = n_edges / len(IU[0])
    real = real_retest(os.environ["HCP_DIR"], density)
    sim = simulated(os.environ["MICA_DIR"], base, n_edges)
    cal = {}
    for layer, r in real["layers"].items():
        ratio = r["retest"]["swap"]["mean"] / r["between"]["swap"]["mean"]
        swap_mica = ratio * sim["between"]["swap"]["mean"]
        cal[layer] = {
            "swap_ratio_retest_over_between": ratio,
            "mica_scale_retest_swap": swap_mica,
            "eps_by_swap_ratio": invert(sim["eps"], "swap", swap_mica),
            "eps_by_load_spearman": invert(sim["eps"], "load_spearman", r["retest"]["load_spearman"]["mean"]),
            "eps_by_hub_overlap": invert(sim["eps"], "hub_overlap", r["retest"]["hub_overlap"]["mean"]),
            # 사람 사이 대비 상대 위치도 같이: 실제 (1-반복ρ)/(1-사람사이ρ)
            "load_unreliability_ratio": (1 - r["retest"]["load_spearman"]["mean"]) / (1 - r["between"]["load_spearman"]["mean"]),
        }
        rel = cal[layer]["load_unreliability_ratio"]
        target = 1 - rel * (1 - sim["between"]["load_spearman"]["mean"])
        cal[layer]["eps_by_load_unreliability_ratio"] = invert(sim["eps"], "load_spearman", target)
    print(json.dumps({"density": density, "n_edges_400": n_edges, "real": real, "sim": sim, "calibration": cal},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
