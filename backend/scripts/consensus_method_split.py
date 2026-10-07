"""외부 합의는 왜 나쁜가, 2~3명 꺼짐은 동점 규칙 때문인가 (docs/63, H17-17).

docs/62에서 남은 두 질문을 나눈다.
  1. MICA에서 외부 합의(Liu 2023 HCP)는 49명 다수결 합의 이득의 32%밖에 못 냈다. Liu는 '거리 보정 합의'
     (Betzel 2019: 반구 안/사이 × 거리 구간마다 개인 평균 연결 수만큼, 빈도 높은 연결을 고른다)다.
     MICA 49명을 같은 방식으로 합의(dd49)하면 다수결 49명과 비슷한가(→ 원인은 측정 방식) 아니면 외부 합의만큼 떨어지는가(→ 합의 방식).
  2. 참조 2~3명에서 꺼지는 현상: 다수결 동점을 '짧은 거리 우선'으로 깨는 규칙 때문인가.
     같은 표본으로 동점을 무작위로 깨는 길잡이(tie_n2/3/5)와 비교한다.

docs/62 캐시(curve62_*.json, 같은 표본·같은 재조직 난수)를 그대로 읽고 새 길잡이만 계산한다.
표본은 docs/62 run_unit의 난수 흐름을 그대로 다시 밟아 같은 사람·촬영을 고른다.

실행: MICA_DIR=../mica-mics-master/_extracted HCP_DIR=../zenodo-14017270/HCP/data_nobrainstem \
      CURVE62_CACHE=<docs/62 캐시> REORG_CACHE=<새 캐시> REORG_PROCS=1 \
      CURVE_SRC=mica|lausanne PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.consensus_method_split > out.json
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

from scripts.consensus_size_curve import DRAWS, M_LIST, N_LIST, _tool

TIE_N = (2, 3, 5)
DD_BINS = 40


def majority_random_tie(vecs: np.ndarray, n_edges: int, rng: np.random.Generator) -> np.ndarray:
    """다수결, 동점은 무작위로 깬다."""
    freq = vecs.mean(0)
    out = np.zeros(vecs.shape[1], dtype=bool)
    out[np.lexsort((rng.random(len(freq)), -freq))[:n_edges]] = True
    return out


def distance_dependent(vecs: np.ndarray, n_edges: int, dist_u: np.ndarray, inter: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Betzel 2019 거리 보정 합의(이진). 반구 안/사이 각각 거리 백분위 구간 DD_BINS개로 나누고,
    구간마다 개인 평균 연결 수(최대 나머지 반올림으로 합계 = n_edges)만큼 빈도 높은 연결을 고른다.
    원래 방법의 동점 규칙(평균 가중치)은 이진 자료라 쓸 수 없어 무작위로 깬다."""
    freq = vecs.mean(0)
    cells = []
    for cls in (False, True):
        idx = np.flatnonzero(inter == cls)
        edges = np.percentile(dist_u[idx], np.linspace(0, 100, DD_BINS + 1))
        b = np.clip(np.digitize(dist_u[idx], edges[1:-1]), 0, DD_BINS - 1)
        for k in range(DD_BINS):
            cells.append(idx[b == k])
    want = np.array([freq[c].sum() for c in cells])  # = 구간 안 개인 평균 연결 수
    quota = np.floor(want).astype(int)
    rest = n_edges - quota.sum()
    quota[np.argsort(-(want - quota), kind="stable")[:rest]] += 1
    out = np.zeros(vecs.shape[1], dtype=bool)
    for c, q in zip(cells, quota):
        if q:
            out[c[np.lexsort((rng.random(len(c)), -freq[c]))[:q]]] = True
    return out


def replay_samples(t, pi: int, d: int, pool: list) -> dict[str, list[int]]:
    """docs/62 run_unit과 같은 난수 흐름으로 n별 표본(촬영 번호)을 다시 뽑는다."""
    rng = np.random.default_rng(6200 + 100 * pi + d)
    src = "mica" if t.external is not None else "lausanne"
    out = {}
    for n in N_LIST[src]:
        for r in range(DRAWS if n < len(pool) else 1):
            people = rng.choice(len(pool), size=n, replace=False)
            out[f"n{n}_r{r}"] = [int(rng.choice(pool[i])) for i in people]
    return out


def run_unit(args: tuple[str, int, int]) -> dict:
    src, pi, d = args
    cache = os.environ.get("REORG_CACHE")
    p = Path(cache) / f"split63_{src}_p{pi}_d{d}.json" if cache else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    t = _tool(src)
    N, IU = t.N, t.IU
    dist_u = t.dist[IU]
    alive = np.ones(N, dtype=bool)
    T, pool = t.truth_and_pool(pi, d)
    pad = t.to_adj(T)
    L_true = t.btw(pad, alive)
    samples = replay_samples(t, pi, d, pool)
    # 재현 확인: 다시 뽑은 n최대 표본으로 만든 지도의 정확도가 docs/62 캐시 값과 같아야 한다
    rng = np.random.default_rng(6300 + 100 * pi + d)
    maps: dict[str, np.ndarray] = {}
    bins: dict[str, np.ndarray] = {}
    for n in TIE_N:
        for r in range(DRAWS):
            bins[f"tie_n{n}_r{r}"] = majority_random_tie(t.vecs[samples[f"n{n}_r{r}"]], t.k, rng)
    if src == "mica":
        h = np.arange(N) >= N // 2
        inter = (h[:, None] != h[None, :])[IU]
        bins["dd49"] = distance_dependent(t.vecs[samples[f"n{max(N_LIST[src])}_r0"]], t.k, dist_u, inter, rng)
    bins["maj_check"] = t.majority(t.vecs[samples[f"n{max(N_LIST[src])}_r0"]], t.k, dist_u)
    for g, b in bins.items():
        maps[g] = t.btw(t.to_adj(b), alive)
    shape = {g: {"mean_len": float(dist_u[b].mean())} for g, b in bins.items()}
    rows = []
    for li, les in enumerate(t.lesions):
        les_mask = np.zeros(N, dtype=bool)
        les_mask[les] = True
        surv = ~les_mask
        adj = pad.copy()
        adj[les, :] = False
        adj[:, les] = False
        lost: dict = {}
        for x in les:
            for y in np.flatnonzero(pad[x]):
                if not les_mask[y]:
                    lost[int(y)] = lost.get(int(y), 0) + 1
        for g, est in maps.items():
            sp = float(stats.spearmanr(est[surv], L_true[surv])[0])
            row = {"unit": [pi, d], "lesion": li, "guide": g, "spearman": sp}
            if g != "maj_check":
                key = lambda bb, cc, est=est: (bb[cc] + 1) / (1.2 * est[cc] + 1)
                ar = t.reorganize_key(adj, surv, lost, t.dist, t.lmax, key, random.Random(pi * 1000 + d * 100 + li))
                for m in M_LIST:
                    row[f"casc_m{m}"] = t.cascade(ar, surv, m * L_true)
            rows.append(row)
    print(f"{src} unit {pi},{d} done", file=sys.stderr, flush=True)
    out = {"src": src, "unit": [pi, d], "rows": rows, "shape": shape}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    return out


def summarize(src: str, rows: list[dict], shapes: list[dict]) -> dict:
    """길잡이(표본 평균)별 연쇄, 최대 n 다수결 대비 차이 [단위 부트스트랩], 균등 분산 0 → 최대 n 100% 위치.
    tie_nX는 같은 표본의 다수결 nX와 짝 비교도 한다."""
    n_max = max(N_LIST[src])
    key = lambda r: (tuple(r["unit"]), r["lesion"])
    name_of = lambda g: g.rsplit("_r", 1)[0] if "_r" in g else g
    by: dict = {}
    for r in rows:
        by.setdefault(name_of(r["guide"]), {}).setdefault(key(r), []).append(r)
    units = sorted({k[0] for k in by["distributed"]})
    out = {}
    for name, cells in by.items():
        o: dict = {}
        paired = [f"n{name[5:]}"] if name.startswith("tie_n") else []
        for m in M_LIST:
            c = f"casc_m{m}"
            if c not in next(iter(cells.values()))[0]:
                continue
            val = {k: np.mean([r[c] for r in v]) for k, v in cells.items()}
            o[c] = {"mean": float(np.mean(list(val.values())))}
            for ref_name in [f"n{n_max}"] + paired:
                ref = {k: np.mean([r[c] for r in v]) for k, v in by[ref_name].items()}
                diff = {k: val[k] - ref[k] for k in val}
                rng = np.random.default_rng(63)
                per = {u: [diff[k] for k in diff if k[0] == u] for u in units}
                boot = [np.mean(np.concatenate([per[units[i]] for i in rng.integers(0, len(units), len(units))])) for _ in range(2000)]
                o[c][f"minus_{ref_name}"] = float(np.mean(list(diff.values())))
                o[c][f"ci95_{ref_name}"] = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
            full = np.mean([np.mean([r[c] for r in v]) for v in by[f"n{n_max}"].values()])
            dist0 = np.mean([v[0][c] for v in by["distributed"].values()])
            o[c]["frac_of_full_over_distributed"] = float((o[c]["mean"] - dist0) / (full - dist0))
        sp = [r["spearman"] for v in cells.values() for r in v if "spearman" in r]
        if sp:
            o["spearman"] = float(np.mean(sp))
        lens = [s[g]["mean_len"] for s in shapes for g in s if name_of(g) == name]
        if lens:
            o["mean_len"] = float(np.mean(lens))
        out[name] = o
    return out


def main() -> None:
    src = os.environ.get("CURVE_SRC", "mica")
    t = _tool(src)
    units = [(src, pi, d) for pi, d in t.units]
    with Pool(int(os.environ.get("REORG_PROCS", "1"))) as pool:
        res = pool.map(run_unit, units, chunksize=1)
    old_dir = Path(os.environ["CURVE62_CACHE"])
    rows, shapes, check = [], [], []
    for u in res:
        pi, d = u["unit"]
        old = json.loads((old_dir / f"curve62_{src}_p{pi}_d{d}.json").read_text(encoding="utf-8"))["rows"]
        rows += old + [r for r in u["rows"] if r["guide"] != "maj_check"]
        shapes.append(u["shape"])
        # 재현 확인: maj_check 정확도 = docs/62 n최대 정확도
        o = {r["lesion"]: r["spearman"] for r in old if r["guide"] == f"n{max(N_LIST[src])}_r0"}
        check += [abs(r["spearman"] - o[r["lesion"]]) for r in u["rows"] if r["guide"] == "maj_check"]
    print(json.dumps({"src": src, "n_units": len(units), "replay_max_abs_spearman_diff": float(max(check)),
                      "maj_full_mean_len": float(np.mean([s["maj_check"]["mean_len"] for s in shapes])),
                      "summary": summarize(src, rows, shapes)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
