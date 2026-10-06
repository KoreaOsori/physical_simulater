"""합의 지도 길잡이는 참조 인원이 몇 명이면 충분한가 (docs/62, H17-16).

docs/61: 개인 촬영(손상 전 촬영 포함)은 길잡이에 아무것도 더하지 못했다. H17의 실용 형태는 집단 합의 지도 길잡이다.
남은 질문은 합의 쪽이다: 참조 n명 다수결 합의로 길잡이를 하면 n에 따라 연쇄 생존이 어떻게 오르고 어디서 포화되는가,
그리고 다른 코호트·다른 처리 방식의 외부 합의(Liu 2023)로도 되는가.

코호트 두 개
  mica      MICA-MICs 50명(Schaefer-400, docs/59 로더). 환자 = 짝수 번호 25명, 병변 = docs/50 국소 병변 8개(LESION_IDX).
            참조 = 환자를 뺀 49명에서 n명 무작위. 외부 합의 = Liu 2023 HCP 합의(liu2023_sc_cons_400_nosubc, 같은 밀도).
  lausanne  Zenodo 14017270 HCP 반복 촬영(Lausanne 462, docs/61). 단위 = 20쌍 × 양방향, 병변 = Desikan 재정의 8개.
            참조 = 이 사람을 뺀 23명(다른 짝 19명 + 짝 없는 4명)에서 n명, 짝이 있는 사람은 두 촬영 중 하나를 무작위로.
n < 최대이면 무작위 표본 DRAWS번(같은 환자·병변에 같은 표본). 평가는 docs/59·61과 같다
(추정 지도 × 1.2 허용선 재조직, 환자 자신의 부하 × m 문턱 연쇄; 오라클·균등 분산 함께).

실행: MICA_DIR=../mica-mics-master/_extracted HCP_DIR=../zenodo-14017270/HCP/data_nobrainstem REORG_CACHE=... REORG_PROCS=3 \
      CURVE_SRC=mica|lausanne PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.consensus_size_curve > out.json
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

DRAWS = 3
M_LIST = (1.2, 1.0)
N_LIST = {"mica": (1, 2, 3, 5, 10, 20, 35, 49), "lausanne": (1, 2, 3, 5, 10, 15, 23)}


# ---------- 코호트별 계산 도구 ----------

class Mica:
    def __init__(self) -> None:
        from scripts.fast_reorganize import N, btw_array
        from scripts.null_network_distribution import cascade
        from scripts.premorbid_map_estimation import load_real_cohort, majority
        from scripts.synthetic_individual_cohort import IU, LESION_IDX, Base, reorganize_key, to_adj
        base = Base()
        self.N, self.IU, self.btw, self.cascade, self.majority = N, IU, btw_array, cascade, majority
        self.reorganize_key, self.to_adj = reorganize_key, to_adj
        self.k = int(base.cons[IU].sum())
        _, vecs = load_real_cohort(os.environ["MICA_DIR"], self.k)
        self.vecs = np.array(vecs)
        self.dist, self.lmax = base.dist, base.lmax
        self.lesions = [sorted(base.lesions[i]["nodes"]) for i in LESION_IDX]
        self.external = btw_array(to_adj(base.cons[IU]), np.ones(N, dtype=bool))
        self.units = [(pi, 0) for pi in range(0, len(self.vecs), 2)]

    def truth_and_pool(self, pi: int, _d: int):
        """참 연결망과 참조 후보(사람 단위). 사람마다 촬영 후보 목록."""
        return self.vecs[pi], [[s] for s in range(len(self.vecs)) if s != pi]


class Lausanne:
    def __init__(self) -> None:
        from scripts import lausanne_retest_premorbid as lr
        from scripts.test_retest_noise import infer_pairs
        c = lr.load_cohort(os.environ["HCP_DIR"])
        self.N, self.IU, self.btw, self.cascade, self.majority = lr.N, lr.IU, lr.btw, lr.cascade, lr.majority
        self.reorganize_key, self.to_adj = lr.reorganize_key, lr.to_adj
        self.vecs, self.dist, self.k = c["vecs"], c["dist"], c["k"]
        self.lesions = [x["nodes"] for x in c["lesions"]]
        self.pairs = infer_pairs(os.environ["HCP_DIR"])
        paired = {x for p in self.pairs for x in p}
        self.people = [list(p) for p in self.pairs] + [[s] for s in range(len(self.vecs)) if s not in paired]
        full = self.majority(self.vecs, self.k, self.dist[self.IU])
        self.lmax = float(np.percentile(self.dist[self.IU][full], 75))
        self.external = None
        self.units = [(pi, d) for pi in range(len(self.pairs)) for d in (0, 1)]

    def truth_and_pool(self, pi: int, d: int):
        a, b = self.pairs[pi]
        t = a if d == 0 else b
        return self.vecs[t], [p for p in self.people if t not in p]


_T: dict = {}


def _tool(src: str):
    if src not in _T:
        _T[src] = Mica() if src == "mica" else Lausanne()
    return _T[src]


# ---------- 한 단위 ----------

def run_unit(args: tuple[str, int, int]) -> dict:
    src, pi, d = args
    cache = os.environ.get("REORG_CACHE")
    p = Path(cache) / f"curve62_{src}_p{pi}_d{d}.json" if cache else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    t = _tool(src)
    N, IU = t.N, t.IU
    dist_u = t.dist[IU]
    alive = np.ones(N, dtype=bool)
    T, pool = t.truth_and_pool(pi, d)
    pad = t.to_adj(T)
    L_true = t.btw(pad, alive)
    rng = np.random.default_rng(6200 + 100 * pi + d)
    maps: dict[str, np.ndarray] = {}
    for n in N_LIST[src]:
        for r in range(DRAWS if n < len(pool) else 1):
            people = rng.choice(len(pool), size=n, replace=False)
            scans = [int(rng.choice(pool[i])) for i in people]
            maps[f"n{n}_r{r}"] = t.btw(t.to_adj(t.majority(t.vecs[scans], t.k, dist_u)), alive)
    if t.external is not None:
        maps["external"] = t.external
    maps["oracle"] = L_true
    guides = list(maps) + ["distributed"]
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
        for g in guides:
            if g == "distributed":
                key = lambda bb, cc: bb[cc] + 1e-6 * cc
            else:
                est = maps[g]
                key = lambda bb, cc, est=est: (bb[cc] + 1) / (1.2 * est[cc] + 1)
            ar = t.reorganize_key(adj, surv, lost, t.dist, t.lmax, key, random.Random(pi * 1000 + d * 100 + li))
            row = {"unit": [pi, d], "lesion": li, "guide": g}
            for m in M_LIST:
                row[f"casc_m{m}"] = t.cascade(ar, surv, m * L_true)
            if g in maps:
                row["spearman"] = float(stats.spearmanr(maps[g][surv], L_true[surv])[0])
            rows.append(row)
    print(f"{src} unit {pi},{d} done", file=sys.stderr, flush=True)
    out = {"src": src, "unit": [pi, d], "rows": rows}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    return out


# ---------- 요약 ----------

def summarize(src: str, rows: list[dict]) -> dict:
    """n별(표본 평균) 연쇄·정확도, 최대 n 합의 대비 차이와 '최대 n 합의 이득 중 도달 비율'."""
    n_max = max(N_LIST[src])
    key = lambda r: (tuple(r["unit"]), r["lesion"])
    by: dict = {}
    for r in rows:
        g = r["guide"]
        name = g.split("_")[0] if g.startswith("n") else g
        by.setdefault(name, {}).setdefault(key(r), []).append(r)
    ref = {k: v[0] for k, v in by[f"n{n_max}"].items()}
    dist_ = {k: v[0] for k, v in by["distributed"].items()}
    units = sorted({k[0] for k in ref})
    out = {}
    for name, cells in by.items():
        o = {}
        for m in M_LIST:
            c = f"casc_m{m}"
            val = {k: np.mean([r[c] for r in v]) for k, v in cells.items()}
            diff = {k: val[k] - ref[k][c] for k in val}
            span = np.mean([ref[k][c] - dist_[k][c] for k in val])
            rng = np.random.default_rng(62)
            per = {u: [diff[k] for k in diff if k[0] == u] for u in units}
            boot = [np.mean(np.concatenate([per[units[i]] for i in rng.integers(0, len(units), len(units))])) for _ in range(2000)]
            o[c] = {"mean": float(np.mean(list(val.values()))), "minus_full": float(np.mean(list(diff.values()))),
                    "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                    # 균등 분산(0) -> 최대 n 합의(1) 사이 어디에 있는가
                    "frac_of_full_over_distributed": float((np.mean(list(val.values())) - np.mean([dist_[k][c] for k in val])) / span) if span else None}
        sp = [r["spearman"] for v in cells.values() for r in v if "spearman" in r]
        if sp:
            o["spearman"] = float(np.mean(sp))
        o["n_rows"] = sum(len(v) for v in cells.values())
        out[name] = o
    return out


def main() -> None:
    src = os.environ.get("CURVE_SRC", "mica")
    t = _tool(src)
    units = [(src, pi, d) for pi, d in t.units]
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(run_unit, units, chunksize=1)
    rows = [r for u in res for r in u["rows"]]
    print(json.dumps({"src": src, "n_list": N_LIST[src], "draws": DRAWS, "n_units": len(units), "summary": summarize(src, rows)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
