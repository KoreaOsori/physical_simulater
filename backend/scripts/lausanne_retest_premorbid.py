"""반복 촬영 짝으로 병전 지도 추정을 가정 없이 다시 하기 -- Lausanne 462 (docs/61, H17-15).

docs/59-60: 손상 후 촬영으로 병전 지도를 채워 넣는 방법은 촬영 잡음 ε에 막힌다. docs/60은 실제 반복 촬영으로
ε ≈ 9~17%(MICA 척도)를 쟀지만, 그 값은 파이프라인 비(반복/사람 사이)를 옮긴 것이고 perturb() 잡음 모델도 가정이다.
여기서는 ε를 쓰지 않는다. 같은 사람의 두 촬영(Zenodo 14017270 HCP, Lausanne layer 1, 462영역)을 그대로 쓴다.

한 단위 = (짝 p, 방향 d)
  참(병전) 연결망 T = 짝의 한 촬영(재조직과 연쇄도 이 연결망 위에서 한다)
  손상 후 관측     = 다른 촬영 O에서 병변에 닿는 연결을 지운 것(실제 반복 촬영 차이가 곧 촬영 잡음)
  참조 코호트      = 이 사람의 두 촬영을 뺀 나머지 42건(짝 없는 4건 포함, 다른 짝의 두 촬영이 모두 들어감)

추정기
  consensus    참조 다수결 합의(같은 밀도, 동점은 짧은 거리 우선)
  mu           참조 개인 부하 평균
  post_lesion  손상 후 관측에서 바로 잰 부하
  impute_all   손상 후 관측 + 병변에 닿는 연결만 참조 빈도로 채움(docs/59 핵심 추정기)
  pre_scan     O를 손상 없이 그대로 쓴 부하 = '다른 날 찍어 둔 병전 촬영'이 있을 때의 최선
  oracle       T의 부하(상한)
  distributed  균등 분산(지도 없음)

핵심 질문
  Q1 실제 잡음에서 impute_all은 합의보다 나은가(docs/60 환산 예측: 아니다).
  Q2 pre_scan이 오라클 이득(oracle − consensus)의 몇 %를 되찾는가.
     = 개인화 이득 중 두 촬영에 공통인(안정된) 개인 차의 몫. 작으면 '촬영 1회 = 참'으로 잰 오라클 이득은 대부분 잡음 맞추기다.

병변: Liu 2023 Schaefer-400 병변(docs/50)과 같은 8개 증후군을 Desikan 해부 이름으로 다시 정의했다(LESIONS). 크기는 대략만 맞는다.
거리: 영역 무게중심 좌표(44건 평균)의 유클리드 거리. 촬영 공간 좌표라 mm 단위는 근사다.
이진화: 각 촬영 섬유 밀도 상위 k개, 밀도 = Liu 합의와 같은 6.34%.

실행: HCP_DIR=../zenodo-14017270/HCP/data_nobrainstem REORG_CACHE=... REORG_PROCS=4 PYTHONIOENCODING=utf-8 \
      .venv/Scripts/python.exe -m scripts.lausanne_retest_premorbid > out.json
"""

from __future__ import annotations

import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import rustworkx as rx
from scipy import stats
from scipy.sparse.csgraph import shortest_path

from scripts.test_retest_noise import infer_pairs

LAYER, N = 1, 462
IU = np.triu_indices(N, 1)
DENSITY = 5059 / (400 * 399 / 2)  # Liu 합의 밀도
M_LIST = (1.2, 1.0)
GUIDES = ("consensus", "mu", "post_lesion", "impute_all", "pre_scan", "oracle", "distributed")

# docs/50의 국소 병변 8개(LESION_IDX)와 같은 증후군, Desikan 이름으로(괄호는 Schaefer-400 병변 크기)
LESIONS = {
    "대뇌색맹(24)": ["lh_fusiform", "rh_fusiform", "lh_lingual", "rh_lingual"],
    "운동맹(18)": ["lh_lateraloccipital", "rh_lateraloccipital"],
    "베르니케 실어증(14)": ["lh_superiortemporal", "lh_bankssts"],
    "집행기능장애(38)": ["lh_rostralmiddlefrontal", "rh_rostralmiddlefrontal", "lh_caudalmiddlefrontal", "rh_caudalmiddlefrontal"],
    "전행성 기억상실증(5)": ["Left_Hippocampus", "Right_Hippocampus", "lh_entorhinal", "rh_entorhinal", "lh_parahippocampal", "rh_parahippocampal"],
    "발린트 증후군(34)": ["lh_superiorparietal", "rh_superiorparietal"],
    "복측 동시실인증(16)": ["lh_fusiform", "lh_inferiortemporal"],
    "안톤 증후군(9)": ["lh_pericalcarine", "rh_pericalcarine", "lh_cuneus", "rh_cuneus"],
}


# ---------- 그래프 계산(N=462 일반화; fast_reorganize·null_network_distribution과 같은 규칙) ----------

def to_adj(vec: np.ndarray) -> np.ndarray:
    a = np.zeros((N, N), dtype=bool)
    a[IU] = vec
    return a | a.T


def btw(adj: np.ndarray, alive: np.ndarray) -> np.ndarray:
    nodes = np.flatnonzero(alive)
    sub = adj[np.ix_(nodes, nodes)]
    a, b = np.nonzero(np.triu(sub, 1))
    r = rx.PyGraph()
    r.add_nodes_from(range(len(nodes)))
    r.add_edges_from_no_data(list(zip(a.tolist(), b.tolist())))
    out = np.zeros(N)
    for i, v in rx.graph_betweenness_centrality(r, normalized=False).items():
        out[nodes[i]] = v
    return out


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
        over = a & (btw(adj, a) > cap)
        if not over.any():
            break
        a &= ~over
    return float(a.sum() / n0)


def reorganize_key(adj0, alive, lost, dist, lmax, key, rng: random.Random):
    """synthetic_individual_cohort.reorganize_key와 같은 규칙(N만 다름)."""
    adj = adj0.copy()
    queue = [n for n, k in lost.items() for _ in range(k)]
    rng.shuffle(queue)
    near = dist <= lmax
    b = btw(adj, alive)
    added = 0
    for n in queue:
        mask = alive & ~adj[n] & near[n]
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) == 0:
            continue
        r = np.array([rng.random() for _ in range(len(cands))])
        t = int(cands[np.lexsort((r, key(b, cands)))[0]])
        adj[n, t] = adj[t, n] = True
        added += 1
        if added % 10 == 0:
            b = btw(adj, alive)
    return adj


# ---------- 데이터 ----------

def load_cohort(root: str) -> dict:
    root = Path(root)
    k = int(round(DENSITY * len(IU[0])))
    vecs, coords, names = [], [], None
    for s in range(44):
        nodes = np.genfromtxt(root / f"HCP_nobrainstem_{s}_layer_{LAYER}_nodes.txt", skip_header=1, dtype=None, encoding="utf-8")
        nm = [str(r[4]) for r in nodes]
        if names is None:
            names = nm
        elif nm != names:
            raise SystemExit(f"scan {s}: 영역 순서가 다르다")
        coords.append(np.array([[r[1], r[2], r[3]] for r in nodes], dtype=float))
        e = np.loadtxt(root / f"HCP_nobrainstem_{s}_layer_{LAYER}_weight_edgelist.txt", skiprows=1)
        w = np.zeros((N, N))
        i, j = e[:, 0].astype(int), e[:, 1].astype(int)
        w[i, j] = w[j, i] = e[:, 3]
        wu = w[IU]
        v = np.zeros(len(wu), dtype=bool)
        v[np.argsort(-wu, kind="stable")[:k]] = True
        v &= wu > 0
        vecs.append(v)
    c = np.mean(coords, axis=0)
    dist = np.sqrt(((c[:, None, :] - c[None, :, :]) ** 2).sum(-1))
    base = {r.rsplit("_", 1)[0] if r.startswith(("lh_", "rh_")) else r for r in names}
    lesions = []
    for lname, parts in LESIONS.items():
        missing = [p for p in parts if p not in base]
        if missing:
            raise SystemExit(f"{lname}: 영역 이름 없음 {missing}")
        nodes_ = [i for i, r in enumerate(names) if (r.rsplit("_", 1)[0] if r.startswith(("lh_", "rh_")) else r) in parts]
        lesions.append({"name": lname, "nodes": nodes_})
    return {"vecs": np.array(vecs), "dist": dist, "names": names, "lesions": lesions, "k": k}


def majority(vecs: np.ndarray, n_edges: int, dist_u: np.ndarray) -> np.ndarray:
    freq = vecs.mean(0)
    out = np.zeros(vecs.shape[1], dtype=bool)
    out[np.argsort(-freq + 1e-9 * dist_u, kind="stable")[:n_edges]] = True
    return out


def impute(obs: np.ndarray, touch: np.ndarray, freq: np.ndarray, dist_u: np.ndarray) -> np.ndarray:
    out = obs.copy()
    out[touch] = False
    idx = np.flatnonzero(touch)
    k = int(round(freq[idx].sum()))
    if k:
        order = np.lexsort((dist_u[idx], -freq[idx]))
        out[idx[order[:k]]] = True
    return out


def accuracy(est: np.ndarray, true: np.ndarray, surv: np.ndarray) -> dict:
    e, t = est[surv], true[surv]
    k = max(1, int(round(0.05 * len(t))))
    return {"spearman": float(stats.spearmanr(e, t)[0]),
            "hub_overlap": len(set(np.argsort(-e)[:k]) & set(np.argsort(-t)[:k])) / k}


# ---------- 한 단위 ----------

_C: dict = {}


def _cohort() -> dict:
    if not _C:
        root = os.environ["HCP_DIR"]
        _C.update(load_cohort(root))
        _C["pairs"] = infer_pairs(root)
    return _C


def run_unit(args: tuple[int, int]) -> dict:
    pi, direction = args
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"lausanne61_p{pi}_d{direction}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    c = _cohort()
    vecs, dist = c["vecs"], c["dist"]
    dist_u = dist[IU]
    a, b = c["pairs"][pi]
    ti, oi = (a, b) if direction == 0 else (b, a)
    ref_idx = [s for s in range(len(vecs)) if s not in (a, b)]
    ref = vecs[ref_idx]
    alive = np.ones(N, dtype=bool)
    ref_L = np.array([btw(to_adj(s), alive) for s in ref])
    T, O = vecs[ti], vecs[oi]
    pad = to_adj(T)
    L_true = btw(pad, alive)
    lmax = float(np.percentile(dist_u[majority(ref, c["k"], dist_u)], 75))
    cons = btw(to_adj(majority(ref, c["k"], dist_u)), alive)
    pre = btw(to_adj(O), alive)
    fr = ref.mean(0)
    rows = []
    for li, les_d in enumerate(c["lesions"]):
        les = les_d["nodes"]
        les_mask = np.zeros(N, dtype=bool)
        les_mask[les] = True
        surv = ~les_mask
        touch = les_mask[IU[0]] | les_mask[IU[1]]
        post = O.copy()
        post[touch] = False
        maps = {
            "consensus": cons,
            "mu": ref_L.mean(0),
            "post_lesion": btw(to_adj(post), surv),
            "impute_all": btw(to_adj(impute(O, touch, fr, dist_u)), alive),
            "pre_scan": pre,
            "oracle": L_true,
        }
        adj = pad.copy()
        adj[les, :] = False
        adj[:, les] = False
        lost: dict = {}
        for x in les:
            for y in np.flatnonzero(pad[x]):
                if not les_mask[y]:
                    lost[int(y)] = lost.get(int(y), 0) + 1
        for g in GUIDES:
            if g == "distributed":
                key = lambda bb, cc: bb[cc] + 1e-6 * cc
            else:
                est = maps[g]
                key = lambda bb, cc, est=est: (bb[cc] + 1) / (1.2 * est[cc] + 1)
            ar = reorganize_key(adj, surv, lost, dist, lmax, key, random.Random(pi * 1000 + direction * 100 + li))
            row = {"pair": pi, "direction": direction, "lesion": li, "guide": g, "global_eff": global_eff(ar, surv)}
            for m in M_LIST:
                row[f"casc_m{m}"] = cascade(ar, surv, m * L_true)
            if g in maps:
                row.update(accuracy(maps[g], L_true, surv))
            rows.append(row)
    print(f"pair {pi} dir {direction} done", file=sys.stderr, flush=True)
    out = {"pair": pi, "direction": direction, "rows": rows}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    return out


def summarize(rows: list[dict]) -> dict:
    out: dict = {"by_guide": {}, "paired": {}}
    keys = ("global_eff", "casc_m1.2", "casc_m1.0", "spearman", "hub_overlap")
    by = {g: [r for r in rows if r["guide"] == g] for g in GUIDES}
    for g, rs in by.items():
        out["by_guide"][g] = {k: float(np.mean([r[k] for r in rs])) for k in keys if k in rs[0]}
    idx = lambda r: (r["pair"], r["direction"], r["lesion"])
    cons = {idx(r): r for r in by["consensus"]}
    orc = {idx(r): r for r in by["oracle"]}
    for g, rs in by.items():
        out["paired"][g] = {}
        for m in M_LIST:
            k = f"casc_m{m}"
            dc = np.array([r[k] - cons[idx(r)][k] for r in rs])
            gap = np.mean([orc[idx(r)][k] - cons[idx(r)][k] for r in rs])
            # 짝 단위로 묶은 부트스트랩 95% 구간(병변·방향은 독립이 아니다)
            pairs = sorted({r["pair"] for r in rs})
            per = {pp: [] for pp in pairs}
            for r, v in zip(rs, dc):
                per[r["pair"]].append(v)
            rng = np.random.default_rng(61)
            boot = [np.mean(np.concatenate([per[pp] for pp in rng.choice(pairs, len(pairs))])) for _ in range(2000)]
            out["paired"][g][k] = {"minus_consensus": float(dc.mean()), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                                   "gain_recovered": float(dc.mean() / gap) if gap else None, "oracle_gap": float(gap), "n": len(rs)}
    return out


def main() -> None:
    c = _cohort()
    units = [(pi, d) for pi in range(len(c["pairs"])) for d in (0, 1)]
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(run_unit, units)
    rows = [r for u in res for r in u["rows"]]
    print(json.dumps({"n_pairs": len(c["pairs"]), "lesions": [{"name": x["name"], "size": len(x["nodes"])} for x in c["lesions"]],
                      "k_edges": c["k"], "summary": summarize(rows)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
