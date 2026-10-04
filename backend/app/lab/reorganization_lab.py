"""손상-재조직 실험실과 폐루프 재활 시뮬레이터 (docs/52).

docs/50-52의 가설 검증 스크립트(backend/scripts/*reorganization*, mixed_failure_model.py)를 연구소에서 직접 돌려 볼 수 있게
옮긴 것이다. 규칙은 스크립트와 같다(같은 병변·같은 시드면 같은 연결을 고른다 -- tests/test_lab_reorganization.py가 확인).

- 커넥톰: HCP 합의 구조 연결 400×400 이진(Liu et al. 2023; docs/49). 정상 부하 지도 L0 = 이 33명 합의(정상 집단 대표) 커넥톰의 매개 중심성 -- 특정 개인의 정상 뇌가 아니다(docs/53).
- 재조직 전략: none / local / concentrated / distributed / normative / random.
  normative = docs/50-51의 headroom. 검토 의견 17번에 따라 이름을 바꿨다: '용량'이 실제 생물학적 용량이 아니라
  정상 betweenness 지도를 뜻하므로 '정상 부하 지도 기반 재조직(normative-load-guided)'이 정확하다.
- 손상(마모) 혼합 모델: 위험 = α·W1(자기 정상 부하 대비 과부하²) + β·W2(절대 부하) + γ·W3(무작위) + δ·W4(구조적 단절).
  각 항은 정상 뇌에서 평균 1이 되게 정규화(W4는 이웃 25% 상실 = 1) -- 어떤 혼합이든 정상 뇌는 시기당 약 2개 영역을 잃는다.
- 폐루프 재활: 매 시기 '감지(현재 부하) -> 개입 -> 마모'. 개입은 연결 유도(가소성, 새 연결) 또는 활동 조절
  (TMS/BCI 유사, 과부하 영역의 부하 일부를 이웃의 여유분으로 넘김). 같은 예산의 개방 루프(처음에 한 번 계획)와 비교.

정직성: 모두 집단 평균 커넥톰 위의 계산 실험이다. 정상 범위는 개인별 μ_i, σ_i가 없어 '정상 부하 대비 비율'로 대신한다.
활동 조절은 경로 재계산이 아니라 이웃 비례 재분배 근사다.
"""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from app.lab.schemas import (
    ClosedLoopRequest,
    ClosedLoopResponse,
    ClosedLoopTraceOut,
    ReorgLabMetaOut,
    ReorgLabRequest,
    ReorgLabResponse,
    ReorgLesionOut,
    ReorgRegionStateOut,
    ReorgStrategyResultOut,
)

_DATA = Path(__file__).resolve().parents[1] / "data"
_SRC = _DATA / "sources" / "human"
N = 400
ALPHA = 0.2
S0 = 2.0 / N
STRATEGIES = ["none", "local", "concentrated", "distributed", "normative", "random", "tau"]
STRATEGY_LABEL = {
    "none": "재조직 없음",
    "local": "국소(가장 가까운 영역)",
    "concentrated": "허브 집중(degree 최대)",
    "distributed": "균등 분산(현재 부하 최소)",
    "normative": "정상 부하 지도 기반",
    "random": "무작위",
    "tau": "τ 제약(여유선)",
}
MECHANISMS = {
    "w1": "W1 과부하형 -- 자기 정상 부하 대비 초과²(점진형)",
    "w2": "W2 활동의존형 -- 절대 부하에 비례(de Haan 2012)",
    "w3": "W3 무작위 -- 부하와 무관한 노화",
    "w4": "W4 구조적 단절 -- 원래 이웃을 잃은 비율에 비례",
}
HONESTY = (
    "집단 평균 구조 커넥톰(400영역) 위의 계산 실험입니다. 환자 데이터가 아니며, '정상 범위'는 개인별 정상 분포(μ, σ)가 없어 "
    "정상 집단 대표(33명 합의) 커넥톰의 부하 대비 비율로 대신합니다. 손상 기전의 혼합 비율은 실제 임상 데이터로 정해진 값이 아닙니다."
)


# ---------- 그래프 계산(numpy; networkx와 값 일치 -- 테스트에서 확인) ----------

def _distances(sub: np.ndarray) -> np.ndarray:
    """비가중 최단거리(도달 불가 = -1). 모든 출발점 동시 BFS -- 층마다 행렬곱 한 번(scipy BFS보다 빠름)."""
    n = len(sub)
    A = sub.astype(np.float32)
    D = np.full((n, n), -1, dtype=np.int16)
    np.fill_diagonal(D, 0)
    reach = np.eye(n, dtype=bool)
    frontier = np.eye(n, dtype=np.float32)
    k = 0
    while True:
        k += 1
        new = ((frontier @ A) > 0) & ~reach
        if not new.any():
            return D
        D[new] = k
        reach |= new
        frontier = new.astype(np.float32)


def betweenness(adj: np.ndarray, alive: np.ndarray) -> np.ndarray:
    """비가중 무방향 그래프의 매개 중심성(비정규화, networkx와 같은 값). 모든 출발점을 한꺼번에 처리하는 층별 Brandes."""
    nodes = np.flatnonzero(alive)
    sub = adj[np.ix_(nodes, nodes)]
    n = len(nodes)
    if n < 3:
        return np.zeros(N)
    A = sub.astype(float)
    D = _distances(sub)
    dmax = int(D.max())
    levels = [D == k for k in range(dmax + 2)]
    sigma = np.eye(n)
    for k in range(1, dmax + 1):
        sigma += ((sigma * levels[k - 1]) @ A) * levels[k]
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = np.where(sigma > 0, 1.0 / sigma, 0.0)
    delta = np.zeros((n, n))
    for k in range(dmax - 1, 0, -1):
        delta += sigma * levels[k] * (((1 + delta) * inv * levels[k + 1]) @ A)
    out = np.zeros(N)
    out[nodes] = delta.sum(0) / 2
    return out


def abs_efficiency(adj: np.ndarray, alive: np.ndarray) -> float:
    """원래 400개 영역 기준 전역 효율(살아남은 쌍의 1/거리 합 / 400·399) -- 영역을 잃으면 반드시 낮아진다."""
    nodes = np.flatnonzero(alive)
    if len(nodes) < 2:
        return 0.0
    D = _distances(adj[np.ix_(nodes, nodes)]).astype(float)
    return float((1.0 / D[D > 0]).sum() / (N * (N - 1)))


def cascade(adj: np.ndarray, alive: np.ndarray, cap: np.ndarray) -> float:
    a = alive.copy()
    n0 = a.sum()
    for _ in range(50):
        over = a & (betweenness(adj, a) > cap)
        if not over.any():
            break
        a &= ~over
    return float(a.sum() / n0)


def strip(adj: np.ndarray, alive: np.ndarray) -> np.ndarray:
    a = adj.copy()
    a[~alive, :] = False
    a[:, ~alive] = False
    return a


# ---------- 데이터 ----------

class _Base:
    def __init__(self) -> None:
        d = json.loads((_DATA / "human_macro_connectome.json").read_text(encoding="utf-8"))
        self.regions = sorted(d["regions"], key=lambda r: int(r["id"]))
        self.adj0 = np.load(_SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
        np.fill_diagonal(self.adj0, False)
        self.dist = np.load(_SRC / "liu2023_dist_400.npy")
        self.alive0 = np.ones(N, dtype=bool)
        self.L0 = betweenness(self.adj0, self.alive0)
        self.cap = (1 + ALPHA) * self.L0
        self.f1h = float((((self.L0 + 1) / (self.cap + 1)) ** 2).mean())
        self.Lbar = float(self.L0.mean())
        self.deg0 = self.adj0.sum(1)
        iu = np.triu_indices(N, 1)
        self.lmax = float(np.percentile(self.dist[iu][self.adj0[iu]], 75))
        self.eff0 = abs_efficiency(self.adj0, self.alive0)
        self.lesions = []
        for i, x in enumerate(d["known_disorders"]):
            self.lesions.append({"id": f"d{i}", "name": x["name"], "category": x["category"],
                                 "nodes": sorted(int(r) - 1 for r in x["region_ids"])})

    def lesion(self, lesion_id: str) -> dict:
        for x in self.lesions:
            if x["id"] == lesion_id:
                return x
        raise KeyError(lesion_id)

    def features(self, load: np.ndarray, alive: np.ndarray) -> np.ndarray:
        dead_nb = (self.adj0 & ~alive[None, :]).sum(1)
        return np.column_stack([
            ((load + 1) / (self.cap + 1)) ** 2 / self.f1h,
            load / self.Lbar,
            np.ones(N),
            4.0 * dead_nb / np.maximum(self.deg0, 1),
        ])


@lru_cache(maxsize=1)
def _base() -> _Base:
    return _Base()


def _lesioned(b: _Base, lesion_id: str):
    les = set(b.lesion(lesion_id)["nodes"])
    alive = b.alive0.copy()
    alive[list(les)] = False
    lost: dict = {}
    for a in les:
        for nb in np.flatnonzero(b.adj0[a]):
            if int(nb) not in les:
                lost[int(nb)] = lost.get(int(nb), 0) + 1
    return strip(b.adj0, alive), alive, lost


def _seed(lesion_id: str) -> int:
    """스크립트와 같은 시드: 국소 증후군 i번째 병변 = i*1000 (scripts는 국소 병변만 0부터 번호를 매긴다)."""
    b = _base()
    focal = [x["id"] for x in b.lesions if x["category"] == "focal"]
    idx = focal.index(lesion_id) if lesion_id in focal else 100 + [x["id"] for x in b.lesions].index(lesion_id)
    return idx * 1000


def reorganize(adj0: np.ndarray, alive: np.ndarray, lost: dict, strategy: str, rng: random.Random,
               max_edges: int | None = None, log: list | None = None, tau: float = 0.6) -> np.ndarray:
    """scripts/reorganization_hypotheses.reorganize()와 같은 규칙·같은 난수 소비(scripts/fast_reorganize.py와 동치).

    tau(docs/55-56): 현재 부하 / 자기 정상 용량 비율이 τ 이하인 후보 중 degree 최대(빠른 회복), 없으면 비율 최소.
    τ=0이면 normative, τ가 아주 크면 concentrated와 간선까지 같다(scripts/tau_pareto.py와 동치)."""
    b = _base()
    adj = adj0.copy()
    if strategy == "none":
        return adj
    rule = "headroom" if strategy == "normative" else strategy
    queue = [n for n, k in lost.items() for _ in range(k)]
    rng.shuffle(queue)
    near = b.dist <= b.lmax
    btw = betweenness(adj, alive) if rule in ("distributed", "headroom", "tau") else None
    added = 0
    for n in queue:
        if max_edges is not None and added >= max_edges:
            break
        if not alive[n]:
            continue
        mask = alive & ~adj[n] & near[n]
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) == 0:
            continue
        if rule == "random":
            t = rng.choice(cands.tolist())
        else:
            r = np.array([rng.random() for _ in range(len(cands))])
            if rule == "local":
                order = np.lexsort((r, b.dist[n, cands]))
            elif rule == "concentrated":
                order = np.lexsort((-r, -adj[cands].sum(1).astype(float)))
            elif rule == "headroom":
                order = np.lexsort((r, (btw[cands] + 1.0) / (b.cap[cands] + 1.0)))
            elif rule == "tau":
                ratio = (btw[cands] + 1.0) / (b.cap[cands] + 1.0)
                ok = np.flatnonzero(ratio <= tau)
                if len(ok):
                    order = ok[np.lexsort((-r[ok], -adj[cands[ok]].sum(1).astype(float)))]
                else:
                    order = np.lexsort((r, ratio))
            else:
                order = np.lexsort((r, adj[cands].sum(1).astype(float), btw[cands]))
            t = int(cands[order[0]])
        adj[n, t] = adj[t, n] = True
        added += 1
        if log is not None:
            log.append((n, t))
        if rule in ("distributed", "headroom", "tau") and added % 10 == 0:
            btw = betweenness(adj, alive)
    return adj


def _mixture(req) -> np.ndarray:
    w = np.array([req.w1, req.w2, req.w3, req.w4], dtype=float)
    if w.sum() <= 0:
        w = np.array([0, 0, 1.0, 0])
    return w / w.sum()


def _wear(adj: np.ndarray, alive: np.ndarray, w: np.ndarray, U: np.ndarray) -> list[float]:
    """혼합 위험으로 T시기 마모. U: (T, N) 균등 난수(전략 간 공통 난수)."""
    b = _base()
    a = alive.copy()
    traj = [abs_efficiency(strip(adj, a), a)]
    for t in range(len(U)):
        load = betweenness(strip(adj, a), a)
        p = 1 - np.exp(-S0 * b.features(load, a) @ w)
        a &= ~(U[t] < p)
        traj.append(abs_efficiency(strip(adj, a), a))
    return traj


# ---------- API 진입점 ----------

def get_meta() -> ReorgLabMetaOut:
    b = _base()
    ref_path = _DATA / "lab_reorganization_reference.json"
    reference = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.exists() else None
    return ReorgLabMetaOut(
        lesions=[ReorgLesionOut(id=x["id"], name=x["name"], category=x["category"], size=len(x["nodes"])) for x in b.lesions],
        strategies=STRATEGIES,
        strategy_labels=STRATEGY_LABEL,
        mechanisms=MECHANISMS,
        healthy_efficiency=b.eff0,
        reference=reference,
        honesty_note=HONESTY,
    )


def run_reorganization_lab(req: ReorgLabRequest) -> ReorgLabResponse:
    b = _base()
    adj_l, alive, lost = _lesioned(b, req.lesion_id)
    w = _mixture(req)
    rng = np.random.default_rng(req.seed)
    U = rng.random((req.reps, req.epochs, N))
    seed = _seed(req.lesion_id)
    healthy = np.mean([_wear(b.adj0, b.alive0, w, U[r]) for r in range(req.reps)], axis=0)
    results = []
    for s in [x for x in STRATEGIES if x in req.strategies]:
        ar = reorganize(adj_l, alive, lost, s, random.Random(seed), tau=req.tau)
        load = betweenness(ar, alive)
        trajs = np.array([_wear(ar, alive, w, U[r]) for r in range(req.reps)])
        results.append(ReorgStrategyResultOut(
            strategy=s,
            label=f"{STRATEGY_LABEL[s]} τ={req.tau:g}" if s == "tau" else STRATEGY_LABEL[s],
            edges_added=int((ar.sum() - adj_l.sum()) // 2),
            efficiency=abs_efficiency(ar, alive),
            loadmap_rho=float(spearmanr(load[alive], b.L0[alive])[0]),
            overload_frac=float((load[alive] > b.cap[alive]).mean()),
            cascade_survival=cascade(ar, alive, req.cascade_m * b.L0),
            wear_mean=trajs.mean(0).tolist(),
            wear_sd=trajs.std(0).tolist(),
        ))
    les = b.lesion(req.lesion_id)
    return ReorgLabResponse(
        lesion_id=req.lesion_id, lesion_name=les["name"], lesion_size=len(les["nodes"]), edges_lost=int(sum(lost.values())),
        mixture=w.tolist(), healthy_efficiency=b.eff0, healthy_wear=healthy.tolist(), results=results, honesty_note=HONESTY,
    )


def _shed(load: np.ndarray, adj: np.ndarray, alive: np.ndarray, targets: dict) -> np.ndarray:
    """활동 조절 근사: 대상 영역 i의 부하를 s_i만큼 덜어 살아 있는 이웃에게 '여유분(용량 − 부하)'에 비례해 넘긴다(총량 보존)."""
    b = _base()
    a = load.copy()
    for i, s in targets.items():
        if not alive[i] or s <= 0:
            continue
        moved = s * load[i]
        nb = np.flatnonzero(adj[i] & alive)
        if len(nb) == 0:
            continue
        room = np.maximum(b.cap[nb] - a[nb], 0)
        share = room / room.sum() if room.sum() > 0 else np.full(len(nb), 1 / len(nb))
        a[i] -= moved
        a[nb] += moved * share
    return a


def _suppression(load: np.ndarray, alive: np.ndarray, budget: int) -> dict:
    """과부하(부하 > 용량) 상위 budget개 영역을, 부하를 정확히 용량까지 낮추는 만큼(최대 50%) 억제."""
    b = _base()
    ratio = np.where(alive, load / np.maximum(b.cap, 1e-9), 0)
    top = [int(i) for i in np.argsort(-ratio)[:budget] if ratio[i] > 1]
    return {i: float(min(0.5, 1 - b.cap[i] / load[i])) for i in top}


def _closed_loop_run(adj_l, alive0, lost, mode, controller, budget, w, U, seed) -> dict:
    b = _base()
    adj, alive = adj_l.copy(), alive0.copy()
    plan: list = []
    if mode == "connect":
        # 개방 루프 계획 = 처음 한 번 계산한 정상 부하 지도 기반 재조직. 폐루프도 같은 총 예산(계획된 연결 수)을 넘지 않는다.
        reorganize(adj_l, alive0, lost, "normative", random.Random(seed), log=plan)
    total_budget = len(plan)
    stubs = [n for n, k in lost.items() for _ in range(k)]
    random.Random(seed).shuffle(stubs)
    fixed_targets = None
    used = 0
    tr = {"efficiency": [abs_efficiency(adj, alive)], "alive": [int(alive.sum())], "overload": [], "deviation": [], "interventions": []}
    for t in range(len(U)):
        load = betweenness(adj, alive)
        n_act = 0
        if mode == "connect" and controller != "none":
            if controller == "open":
                while plan and n_act < budget:
                    n, m = plan.pop(0)
                    if alive[n] and alive[m] and not adj[n, m]:
                        adj[n, m] = adj[m, n] = True
                        n_act += 1
            else:
                take, stubs = stubs[: budget], stubs[budget:]
                take = [n for n in take if alive[n]][: max(0, total_budget - used)]
                if take:
                    before = int(adj.sum())
                    adj = reorganize(adj, alive, _count(take), "normative", random.Random(seed + t))
                    n_act = (int(adj.sum()) - before) // 2
            used += n_act
            load = betweenness(adj, alive)
            eff_load = load
        elif mode == "modulate" and controller != "none":
            if controller == "open":
                if fixed_targets is None:
                    fixed_targets = _suppression(load, alive, budget)
                targets = fixed_targets
            else:
                targets = _suppression(load, alive, budget)
            eff_load = _shed(load, adj, alive, targets)
            n_act = sum(1 for i in targets if alive[i])
        else:
            eff_load = load
        tr["overload"].append(float((eff_load[alive] > b.cap[alive]).mean()))
        tr["deviation"].append(float(np.abs(np.log((eff_load[alive] + 1) / (b.L0[alive] + 1))).mean()))
        tr["interventions"].append(int(n_act))
        p = 1 - np.exp(-S0 * b.features(eff_load, alive) @ w)
        died = alive & (U[t] < p)
        alive &= ~died
        adj = strip(adj, alive)
        if mode == "connect" and controller == "closed":
            # 피드백: 새로 잃은 영역의 이웃도 잃은 연결만큼 재조직 대상이 된다
            for d in np.flatnonzero(died):
                stubs += [int(x) for x in np.flatnonzero(adj_l[d] & alive)]
        tr["efficiency"].append(abs_efficiency(adj, alive))
        tr["alive"].append(int(alive.sum()))
    final_load = betweenness(adj, alive)
    tr["final_ratio"] = np.where(alive, (final_load + 1) / (b.L0 + 1), 0).tolist()
    tr["final_alive"] = alive.tolist()
    return tr


def _count(nodes: list) -> dict:
    out: dict = {}
    for n in nodes:
        out[n] = out.get(n, 0) + 1
    return out


def run_closed_loop(req: ClosedLoopRequest) -> ClosedLoopResponse:
    b = _base()
    adj_l, alive, lost = _lesioned(b, req.lesion_id)
    w = _mixture(req)
    U = np.random.default_rng(req.seed).random((req.reps, req.epochs, N))
    seed = _seed(req.lesion_id)
    base = None
    if req.mode == "modulate":
        # 활동 조절은 구조를 바꾸지 않는다 -- 환자가 이미 겪은 자연 재조직(기본: 균등 분산, 과부하를 만든다) 위에서 개입한다.
        base = req.base_strategy
        adj_l = reorganize(adj_l, alive, lost, base, random.Random(seed))
    traces = []
    rep0 = {}
    for c in ("none", "open", "closed"):
        runs = [_closed_loop_run(adj_l, alive, lost, req.mode, c, req.budget, w, U[r], seed) for r in range(req.reps)]
        rep0[c] = runs[0]
        keys = ("efficiency", "alive", "overload", "deviation", "interventions")
        traces.append(ClosedLoopTraceOut(controller=c, **{k: np.mean([r[k] for r in runs], axis=0).tolist() for k in keys}))
    regions = [
        ReorgRegionStateOut(id=i, network=b.regions[i]["network"], x=b.regions[i]["mni_coordinate_mm"]["x"], y=b.regions[i]["mni_coordinate_mm"]["y"],
                            lesioned=not alive[i], ratio_none=rep0["none"]["final_ratio"][i], ratio_closed=rep0["closed"]["final_ratio"][i],
                            alive_none=rep0["none"]["final_alive"][i], alive_closed=rep0["closed"]["final_alive"][i])
        for i in range(N)
    ]
    les = b.lesion(req.lesion_id)
    return ClosedLoopResponse(lesion_id=req.lesion_id, lesion_name=les["name"], mode=req.mode, budget=req.budget, base_strategy=base, mixture=w.tolist(),
                              edges_lost=int(sum(lost.values())), traces=traces, regions=regions, honesty_note=HONESTY)
