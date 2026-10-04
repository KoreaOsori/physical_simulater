"""'정상 용량'을 무엇으로 정의하느냐에 결론이 좌우되나(docs/51, H16-5 확장).

H16-5의 headroom은 용량 = 정상 뇌 betweenness × 1.2였고, 이를 평가한 연쇄 과부하 모델도 같은 용량을 썼다 -> 순환 가능성.
여기서는 용량 정의를 7가지로 바꿔 headroom 재조직을 반복하고, 용량 정의와 무관한 지표로 평가한다.

용량 후보(모두 정상 뇌에서 계산, 평균 1로 맞춘 뒤 정상 평균 부하 × 1.2를 곱해 betweenness 단위로 변환 --
headroom은 (현재 부하+1)/(용량+1)이 최소인 영역을 고르므로 영역 간 '상대 크기'만 의미가 있다):
  betweenness(기존), degree, strength(sc_avggm 가중), participation(Yeo-7), communicability(정규화 가중 행렬의 exp 행 합),
  controllability(평균 제어성, Gu et al. 2015), fc_strength(fc_cons 양의 연결 합).
  불가: metabolic cost(영역별 대사 자료 없음), 정상인 개인별 분포(개인별 연결망 없음 -- capacity envelope는 미실행).

평가(용량 정의와 무관): 2차 타격 효율 손실, 활동의존 마모(W2)·무작위 마모(W3) 후 효율 유지율, 정상 범위 이탈.
참고로만: betweenness 용량 기준 연쇄 생존율(betweenness 정의에 순환적으로 유리).

실행 전 예측: headroom의 이점(분산 대비 정상 이탈↓, 2차 타격은 비슷)이 betweenness 이외 정의 대부분에서도 유지된다면 진짜 효과,
betweenness에서만 나타나면 순환의 산물.

실행: REORG_PROCS=3 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.capacity_definition_sensitivity > out.json
"""

from __future__ import annotations

import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import linalg, stats

import scripts.short_long_term_reorganization as sl  # noqa: F401  (rh.betweenness를 빠른 구현으로 교체)
from scripts.reorganization_hypotheses import ALPHA, SRC, cascade, gini, load, reorganize
from scripts.short_long_term_reorganization import betweenness, calibrate, global_eff, wear_run

DEFS = ["betweenness", "degree", "strength", "participation", "communicability", "controllability", "fc_strength"]
TOP_FRAC = 0.05
WEAR_REPS = 4


def capacity_profiles(g: nx.Graph, modules: dict) -> dict:
    n = 400
    L0 = betweenness(g)
    w = np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy")
    w = np.where(np.eye(n, dtype=bool), 0.0, w)
    fc = np.load(SRC / "liu2023_fc_cons_400.npy")
    fc = np.where(np.eye(n, dtype=bool), 0.0, fc)
    s = w.sum(1)
    norm = w / np.sqrt(np.outer(np.maximum(s, 1e-12), np.maximum(s, 1e-12)))
    comm = linalg.expm(norm)
    a = w / (1 + np.linalg.eigvalsh(w).max())
    lam, v = np.linalg.eigh(a)
    ctrl = (v**2 / (1 - lam**2)).sum(1)
    part = {}
    for i in g.nodes:
        k = g.degree(i)
        cnt: dict = {}
        for j in g.neighbors(i):
            cnt[modules[j]] = cnt.get(modules[j], 0) + 1
        part[i] = 1 - sum((c / k) ** 2 for c in cnt.values()) if k else 0.0
    raw = {
        "betweenness": np.array([L0[i] for i in range(n)]),
        "degree": np.array([g.degree(i) for i in range(n)], dtype=float),
        "strength": s,
        "participation": np.array([part[i] for i in range(n)]),
        "communicability": comm.sum(1) - np.diag(comm),
        "controllability": ctrl,
        "fc_strength": np.clip(fc, 0, None).sum(1),
    }
    mean_L0 = float(np.mean(list(L0.values())))
    prof = {k: {i: (1 + ALPHA) * mean_L0 * float(x[i] / x.mean()) for i in range(n)} for k, x in raw.items()}
    corr = {k: float(stats.spearmanr(raw["betweenness"], x)[0]) for k, x in raw.items()}
    return {"prof": prof, "rho_with_betweenness": corr}


def eval_graph(g: nx.Graph, modules: dict, cap_btw: dict, cal: dict, rng: np.random.Generator) -> dict:
    btw = betweenness(g)
    b = np.array(list(btw.values()))
    comms: dict = {}
    for x in g.nodes:
        comms.setdefault(modules[x], set()).add(x)
    k = max(1, int(round(TOP_FRAC * g.number_of_nodes())))
    top = sorted(btw, key=btw.get, reverse=True)[:k]
    e0 = global_eff(g)
    h = g.copy()
    h.remove_nodes_from(top)
    out = {
        "global_eff": e0,
        "local_eff": nx.local_efficiency(g),
        "load_gini": gini(b),
        "modularity": nx.community.modularity(g, list(comms.values())),
        "second_hit_eff_drop": (e0 - global_eff(h)) / e0,
        "cascade_btw_capacity": cascade(g, cap_btw),
    }
    for wm in ("W2_activity", "W3_random"):
        tr = np.array([wear_run(g, wm, cap_btw, cal, rng) for _ in range(WEAR_REPS)]).mean(0)
        out[f"{wm}_retained"] = float(tr[-1] / tr[0])
    return out


def run_one(args) -> dict:
    lesion, seed = args
    g, dist, modules, _ = load()
    cp = capacity_profiles(g, modules)
    cap_btw = cp["prof"]["betweenness"]
    L0 = betweenness(g)
    cal = calibrate(g, cap_btw, L0)
    lmax = float(np.percentile([dist[a, b] for a, b in g.edges], 75))
    les = set(lesion["nodes"])
    lost: dict = {}
    for a in les:
        for b in g.neighbors(a):
            if b not in les:
                lost[b] = lost.get(b, 0) + 1
    gl = g.copy()
    gl.remove_nodes_from(les)
    out = {"lesion": lesion["name"], "size": len(les), "results": {}}
    runs = [("none", None), ("local", None), ("distributed", None)] + [("headroom", d) for d in DEFS]
    for strat, d in runs:
        gr = reorganize(gl, lost, dist, lmax, strat, random.Random(seed * 1000), cp["prof"][d] if d else cap_btw)
        rng = np.random.default_rng(seed * 104729)  # 같은 난수(공통 난수)로 전략 간 쌍대 비교
        out["results"][f"headroom:{d}" if d else strat] = eval_graph(gr, modules, cap_btw, cal, rng)
    print(f"done {lesion['name']}", file=sys.stderr, flush=True)
    return out


def _cached(fn, key: str, args):
    """작업 단위 결과를 REORG_CACHE 디렉터리에 저장 -- 메모리 부족 등으로 중단돼도 다시 실행하면 끝난 작업은 건너뛴다."""
    d = os.environ.get("REORG_CACHE")
    if not d:
        return fn(args)
    p = Path(d) / (key + ".json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    r = fn(args)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    return r


def cached_run(args) -> dict:
    return _cached(run_one, f"capdef_{args[1]}", args)


def main() -> None:
    g, _, modules, lesions = load()
    cp = capacity_profiles(g, modules)
    cap_btw = cp["prof"]["betweenness"]
    healthy = eval_graph(g, modules, cap_btw, calibrate(g, cap_btw, betweenness(g)), np.random.default_rng(1))
    with Pool(int(os.environ.get("REORG_PROCS", "3"))) as pool:
        res = pool.map(cached_run, [(les, i) for i, les in enumerate(lesions)], chunksize=1)
    dev_keys = ["global_eff", "local_eff", "load_gini", "modularity"]
    for r in res:
        for v in r["results"].values():
            v["deviation"] = sum(abs(v[k] - healthy[k]) / abs(healthy[k]) for k in dev_keys)
    keys = ["global_eff", "load_gini", "second_hit_eff_drop", "W2_activity_retained", "W3_random_retained", "deviation", "cascade_btw_capacity"]
    names = list(res[0]["results"])
    table = {nm: {k: float(np.mean([r["results"][nm][k] for r in res])) for k in keys} for nm in names}

    def paired(a: str, b: str, k: str) -> dict:
        x = np.array([r["results"][a][k] for r in res])
        y = np.array([r["results"][b][k] for r in res])
        return {"diff": float((x - y).mean()), "a_higher": int((x > y).sum()), "p": float(stats.wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0}

    vs = {f"headroom:{d}": {f"vs_{b}:{k}": paired(f"headroom:{d}", b, k) for b in ("distributed", "local", "none") for k in keys} for d in DEFS}
    print(json.dumps({"healthy": healthy, "rho_with_betweenness": cp["rho_with_betweenness"], "table": table, "paired": vs, "per_lesion": res}, ensure_ascii=False))


if __name__ == "__main__":
    main()
