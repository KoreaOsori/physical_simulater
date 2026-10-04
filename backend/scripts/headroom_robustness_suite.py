"""'정상 용량 기준(headroom) 재조직이 우수하다'가 알고리즘의 산물은 아닌지 검증(docs/51, 사용자 검토 의견 16번).

① 연결 예산 동일화: 병변마다 모든 전략이 같은 수의 새 연결만 추가(전략별 실제 추가 수의 최솟값으로 자름; 이진 연결망이라
   연결 수 = 연결 강도).
② degree 보존 귀무:
   (a) 전략 귀무 'degree_matched': headroom이 추가한 연결(출발 영역 n -> 목표 t)마다 목표를 t와 같은 정상 degree 십분위의
       무작위 후보로 바꿈 -- headroom의 이점이 '어떤 degree 등급을 골랐나'만으로 설명되는지.
   (b) 네트워크 귀무: degree 순서를 보존한 무작위 재배선(Maslov-Sneppen) 연결망 2개에서 같은 실험 -- 이점이 실제 뇌 위상의
       성질인지, degree 분포만으로 생기는지.
③ 무작위 재배선: 무작위 전략 6시드(국소), 3시드(나머지).
④ 다른 용량 정의: scripts/capacity_definition_sensitivity.py(별도 실행).
⑤ 다른 병변 집합: 복합 질환 7개 + 공간적으로 인접한 무작위 병변 20개(크기는 국소 증후군 크기 분포에서 추출).
⑥ leave-one-lesion-out: 국소 25개에서 하나씩 빼고 쌍대 비교 방향·유의성 유지 여부.
⑦ 용량 허용치 스윕: 연쇄 과부하 용량 = m × 정상 부하, m = 0.8~1.5. (headroom의 선택 기준 (부하+1)/(m·정상 부하+1)은 m에
   거의 무관하므로, 스윕은 주로 '같은 재조직 결과가 허용치에 따라 얼마나 버티나'를 본다. 정상 뇌 곡선도 함께.)

평가 지표: 전역 효율, 정상 범위 이탈, 2차 타격 손실, 활동의존 마모(W2) 유지율 -- 모두 용량 정의와 무관 -- 와 연쇄 생존율
곡선(betweenness 용량 기준; headroom에 순환적으로 유리할 수 있어 따로 해석).

실행: REORG_PROCS=3 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.headroom_robustness_suite > out.json
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
from scipy import stats

import scripts.short_long_term_reorganization as sl
from scripts.reorganization_hypotheses import cascade, gini, load, reorganize
from scripts.short_long_term_reorganization import betweenness, calibrate, global_eff, wear_run

M_SWEEP = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5]
MAIN = ["none", "local", "concentrated", "distributed", "headroom"]
N_RANDOM = 6
N_DEGMATCH = 3
N_NULL_NETS = 2
N_CONTIG = 20
WEAR_REPS = 3
KEYS = ["global_eff", "deviation", "second_hit_eff_drop", "W2_retained", "cascade_m1.2"]


class Ctx:
    """연결망 하나(실제 뇌 또는 귀무 연결망)에 대한 정상 기준값."""

    def __init__(self, g: nx.Graph, dist: np.ndarray, modules: dict):
        self.g, self.dist, self.modules = g, dist, modules
        self.L0 = betweenness(g)
        self.cap12 = {n: 1.2 * L for n, L in self.L0.items()}
        self.cal = calibrate(g, self.cap12, self.L0)
        self.lmax = float(np.percentile([dist[a, b] for a, b in g.edges], 75))
        deg = np.array([g.degree(i) for i in range(400)])
        edges = np.percentile(deg, np.arange(10, 100, 10))
        self.deg_bin = {i: int(np.searchsorted(edges, deg[i], side="right")) for i in range(400)}
        self.healthy = None
        self.healthy = self.evaluate(g, np.random.default_rng(0))

    def evaluate(self, g: nx.Graph, rng: np.random.Generator) -> dict:
        btw = betweenness(g)
        comms: dict = {}
        for x in g.nodes:
            comms.setdefault(self.modules[x], set()).add(x)
        k = max(1, int(round(0.05 * g.number_of_nodes())))
        top = sorted(btw, key=btw.get, reverse=True)[:k]
        e0 = global_eff(g)
        h = g.copy()
        h.remove_nodes_from(top)
        out = {
            "global_eff": e0,
            "local_eff": nx.local_efficiency(g),
            "load_gini": gini(np.array(list(btw.values()))),
            "modularity": nx.community.modularity(g, list(comms.values())),
            "second_hit_eff_drop": (e0 - global_eff(h)) / e0,
        }
        for m in M_SWEEP:
            out[f"cascade_m{m}"] = cascade(g, {n: m * L for n, L in self.L0.items()})
        tr = np.array([wear_run(g, "W2_activity", self.cap12, self.cal, rng) for _ in range(WEAR_REPS)]).mean(0)
        out["W2_retained"] = float(tr[-1] / tr[0])
        if self.healthy is not None:
            out["deviation"] = sum(abs(out[q] - self.healthy[q]) / abs(self.healthy[q]) for q in ("global_eff", "local_eff", "load_gini", "modularity"))
        else:
            out["deviation"] = 0.0
        return out


def lost_edges(g: nx.Graph, les: set) -> dict:
    lost: dict = {}
    for a in les:
        for b in g.neighbors(a):
            if b not in les:
                lost[b] = lost.get(b, 0) + 1
    return lost


def degree_matched(ctx: Ctx, gl: nx.Graph, added: list, rng: random.Random) -> nx.Graph:
    g = gl.copy()
    for n, t in added:
        cands = [c for c in g.nodes if c != n and not g.has_edge(n, c) and ctx.dist[n, c] <= ctx.lmax and ctx.deg_bin[c] == ctx.deg_bin[t]]
        if not cands:
            cands = [c for c in g.nodes if c != n and not g.has_edge(n, c) and ctx.dist[n, c] <= ctx.lmax]
        if cands:
            g.add_edge(n, rng.choice(cands))
    return g


def run_lesion(ctx: Ctx, nodes, seed: int, n_random: int, with_degmatch: bool) -> dict:
    les = set(nodes)
    lost = lost_edges(ctx.g, les)
    gl = ctx.g.copy()
    gl.remove_nodes_from(les)
    plan = [(s, 0) for s in MAIN] + [("random", i) for i in range(n_random)]

    def build(strat, sd, budget=None, log=None):
        cb = (lambda a, gg, n, t: log.append((n, t))) if log is not None else None
        return reorganize(gl, lost, ctx.dist, ctx.lmax, strat, random.Random(seed * 1000 + sd), ctx.cap12, cb, budget)

    counts = {}
    for s, sd in plan:
        if s == "none":
            continue
        gr = build(s, sd)
        counts[(s, sd)] = gr.number_of_edges() - gl.number_of_edges()
    budget = min(counts.values()) if counts else 0
    out = {"size": len(les), "edges_lost": sum(lost.values()), "budget": budget, "unconstrained_counts": {f"{s}:{sd}": c for (s, sd), c in counts.items()}, "results": {}}
    rng = lambda: np.random.default_rng(seed * 104729)  # noqa: E731  공통 난수로 전략 간 쌍대 비교
    head_log: list = []
    for s, sd in plan:
        log = head_log if s == "headroom" else None
        gr = gl.copy() if s == "none" else build(s, sd, budget, log)
        out["results"][s if s != "random" else f"random:{sd}"] = ctx.evaluate(gr, rng())
    if with_degmatch:
        for i in range(N_DEGMATCH):
            gr = degree_matched(ctx, gl, head_log, random.Random(seed * 7 + i))
            out["results"][f"degmatch:{i}"] = ctx.evaluate(gr, rng())
    # 여러 시드 전략은 평균으로 요약
    for pref in ("random", "degmatch"):
        rs = [v for k, v in out["results"].items() if k.startswith(pref + ":")]
        if rs:
            out["results"][pref] = {k: float(np.mean([r[k] for r in rs])) for k in rs[0]}
    return out


def job(args) -> dict:
    kind, name, nodes, seed, net = args
    g, dist, modules, _ = load()
    if net is not None:
        g = nx.Graph()
        g.add_nodes_from(range(400))
        g.add_edges_from(net)
    ctx = Ctx(g, dist, modules)
    full = kind == "focal"
    r = run_lesion(ctx, nodes, seed, N_RANDOM if full else 3, full)
    r.update({"kind": kind, "lesion": name, "healthy": ctx.healthy})
    print(f"done {kind} {name}", file=sys.stderr, flush=True)
    return r


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


def cached_job(args) -> dict:
    kind, name, _, seed, _ = args
    return _cached(job, f"suite_{kind}_{seed}", args)


def null_networks(g: nx.Graph) -> list:
    nets = []
    for i in range(N_NULL_NETS):
        h = g.copy()
        nx.double_edge_swap(h, nswap=10 * h.number_of_edges(), max_tries=10**8, seed=100 + i)
        if not nx.is_connected(h):  # 드물게 조각나면 가장 큰 조각의 결과만 해석되므로 기록
            print(f"null {i} not connected", file=sys.stderr)
        nets.append(sorted(h.edges))
    return nets


def contiguous_lesions(g: nx.Graph, dist: np.ndarray, sizes: list, rng: np.random.Generator) -> list:
    out = []
    for i in range(N_CONTIG):
        k = int(rng.choice(sizes))
        seed_node = int(rng.integers(400))
        nodes = sorted(np.argsort(dist[seed_node])[:k].tolist())
        out.append((f"contig{i}(k={k})", nodes))
    return out


def paired(res: list, a: str, b: str, key: str) -> dict:
    x = np.array([r["results"][a][key] for r in res])
    y = np.array([r["results"][b][key] for r in res])
    d = x - y
    return {"mean_diff": float(d.mean()), "a_higher": int((d > 0).sum()), "n": len(d), "p": float(stats.wilcoxon(x, y).pvalue) if np.any(d != 0) else 1.0}


def summarize(res: list, names: list) -> dict:
    keys = KEYS + [f"cascade_m{m}" for m in M_SWEEP]
    return {nm: {k: float(np.mean([r["results"][nm][k] for r in res])) for k in dict.fromkeys(keys)} for nm in names}


def compare(res: list, others: list) -> dict:
    return {f"headroom_vs_{o}": {k: paired(res, "headroom", o, k) for k in KEYS} for o in others}


def main() -> None:
    g, dist, _, lesions = load()
    d = json.loads((sl.rh.ROOT / "app" / "data" / "human_macro_connectome.json").read_text(encoding="utf-8"))
    complex_ = [(x["name"], sorted(int(r) - 1 for r in x["region_ids"])) for x in d["known_disorders"] if x["category"] != "focal"]
    contig = contiguous_lesions(g, dist, [len(l["nodes"]) for l in lesions], np.random.default_rng(51))
    nets = null_networks(g)
    jobs = [("focal", l["name"], l["nodes"], i, None) for i, l in enumerate(lesions)]
    jobs += [("complex", n, nodes, 100 + i, None) for i, (n, nodes) in enumerate(complex_)]
    jobs += [("contig", n, nodes, 200 + i, None) for i, (n, nodes) in enumerate(contig)]
    jobs += [(f"null{j}", l["name"], l["nodes"], i, nets[j]) for j in range(N_NULL_NETS) for i, l in enumerate(lesions)]
    with Pool(int(os.environ.get("REORG_PROCS", "3"))) as pool:
        res = pool.map(cached_job, jobs, chunksize=1)
    by = lambda k: [r for r in res if r["kind"] == k]  # noqa: E731
    focal = by("focal")
    out: dict = {"n_jobs": len(res)}

    # ①③②a 국소 25개
    out["focal_budget"] = {"budgets": [r["budget"] for r in focal], "unconstrained_min_max": [[min(r["unconstrained_counts"].values()), max(r["unconstrained_counts"].values())] for r in focal]}
    out["focal_table"] = summarize(focal, MAIN + ["random", "degmatch"])
    out["focal_healthy"] = focal[0]["healthy"]
    out["focal_compare"] = compare(focal, ["distributed", "random", "degmatch", "local", "none", "concentrated"])
    # random 시드별로 headroom을 이긴 비율(단일 무작위 시드 중 headroom보다 나은 것이 있는가)
    out["focal_random_seed_beats"] = {
        k: float(np.mean([np.mean([r["results"][f"random:{i}"][k] > r["results"]["headroom"][k] for i in range(N_RANDOM)]) for r in focal]))
        for k in KEYS
    }
    # ⑥ leave-one-out
    loo = {}
    for o in ["distributed", "random", "degmatch", "none"]:
        for k in KEYS:
            full = paired(focal, "headroom", o, k)
            sign = np.sign(full["mean_diff"])
            keep = sig = 0
            for i in range(len(focal)):
                sub = [r for j, r in enumerate(focal) if j != i]
                p = paired(sub, "headroom", o, k)
                keep += np.sign(p["mean_diff"]) == sign
                sig += p["p"] < 0.05
            loo[f"vs_{o}:{k}"] = {"full_p": full["p"], "same_direction": int(keep), "still_p<0.05": int(sig), "of": len(focal)}
    out["focal_loo"] = loo
    # ⑤ 다른 병변 집합
    for kind in ("complex", "contig"):
        rs = by(kind)
        out[f"{kind}_table"] = summarize(rs, MAIN + ["random"])
        out[f"{kind}_compare"] = compare(rs, ["distributed", "random", "local", "none"])
    # ②b 귀무 연결망
    for j in range(N_NULL_NETS):
        rs = by(f"null{j}")
        out[f"null{j}_healthy"] = rs[0]["healthy"]
        out[f"null{j}_table"] = summarize(rs, MAIN + ["random"])
        out[f"null{j}_compare"] = compare(rs, ["distributed", "random", "local", "none"])
    # ⑦ 스윕: 정상 뇌 + 전략별 곡선(국소 25개 평균)
    out["sweep"] = {
        "m": M_SWEEP,
        "healthy": [focal[0]["healthy"][f"cascade_m{m}"] for m in M_SWEEP],
        **{nm: [out["focal_table"][nm][f"cascade_m{m}"] for m in M_SWEEP] for nm in MAIN + ["random", "degmatch"]},
        "headroom_vs_distributed": [paired(focal, "headroom", "distributed", f"cascade_m{m}") for m in M_SWEEP],
        "headroom_vs_random": [paired(focal, "headroom", "random", f"cascade_m{m}") for m in M_SWEEP],
        "headroom_vs_none": [paired(focal, "headroom", "none", f"cascade_m{m}") for m in M_SWEEP],
    }
    out["per_job"] = [{k: v for k, v in r.items() if k != "results"} | {"results": {n: v for n, v in r["results"].items() if ":" not in n}} for r in res]
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
