"""시기 맞춤 재조직(가중치 모델) -- 연구소 폐루프 탭의 세 번째 모드(docs/58, H17-12).

회복 기전이 시간에 따라 바뀐다고 본다: 앞쪽은 기존 연결 강화(드러남), 뒤쪽은 새 연결 발아(문헌: 강화가 먼저, 발아가 뒤따르며 겹침).
'기전 인지' 정책(맞춤)은 매 단계 지금 일어나는 회복 기전을 감지해 전략을 고른다: 강화 단계 = 균등 분산, 발아 단계 = 정상 부하 지도 기반.
이를 고정 전략·엇갈린 정책과 비교한다. 규칙·난수 소비는 backend/scripts/time_varying_plasticity.py와 같다(테스트에서 간선까지 같음을 확인).

가중치 = 합의 간선의 평균 스트림라인 가중치(Liu et al. 2023), 길이 = 1/가중치, 부하 = 가중 betweenness(연속 가중치라 최단 경로가 사실상
유일 -- 최단 경로 나무를 따라 쌓는 빠른 구현, networkx와 오차 0). 실패 문턱 = m·(정상 가중 부하 + ε), ε = 평균의 1%.
"""

from __future__ import annotations

import random
from functools import lru_cache

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from app.lab.reorganization_lab import N, _SRC, _base, _seed
from app.lab.schemas import PlasticityScheduleRequest, PlasticityScheduleResponse, PlasticityPolicyResultOut

RECOMPUTE = 20
POLICIES = {
    "tau0": ("정상 부하 지도 기반(τ=0)", ("tau0", "tau0")),
    "dist": ("균등 분산", ("dist", "dist")),
    "tau06": ("τ=0.6", ("tau06", "tau06")),
    "conc": ("허브 집중", ("conc", "conc")),
    "matched": ("기전 인지 맞춤(강화=분산, 발아=τ0)", ("dist", "tau0")),
    "mismatched": ("엇갈림(강화=τ0, 발아=분산)", ("tau0", "dist")),
}


def wbtw(W: np.ndarray, alive: np.ndarray) -> np.ndarray:
    nodes = np.flatnonzero(alive)
    sub = W[np.ix_(nodes, nodes)]
    L = np.where(sub > 0, 1.0 / np.where(sub > 0, sub, 1), 0)
    D, P = dijkstra(csr_matrix(L), directed=False, return_predecessors=True)
    n = len(nodes)
    rows = np.repeat(np.arange(n)[:, None], n, 1)
    depth = np.full((n, n), -1, np.int32)
    np.fill_diagonal(depth, 0)
    reach = ~np.isinf(D)
    Pc = np.where(P < 0, 0, P)
    for _ in range(n):
        par = depth[rows, Pc]
        upd = (depth < 0) & reach & (par >= 0) & (P >= 0)
        if not upd.any():
            break
        depth[upd] = par[upd] + 1
    delta = np.zeros((n, n))
    for d in range(int(depth.max()), 1, -1):
        s, v = np.nonzero(depth == d)
        np.add.at(delta, (s, P[s, v]), 1 + delta[s, v])
    out = np.zeros(N)
    out[nodes] = delta.sum(0) / 2
    return out


def weff(W: np.ndarray, alive: np.ndarray) -> float:
    nodes = np.flatnonzero(alive)
    sub = W[np.ix_(nodes, nodes)]
    L = np.where(sub > 0, 1.0 / np.where(sub > 0, sub, 1), 0)
    D = dijkstra(csr_matrix(L), directed=False)
    off = ~np.eye(len(nodes), dtype=bool) & ~np.isinf(D)
    return float((1.0 / D[off]).sum() / (N * (N - 1)))


def wcascade(W: np.ndarray, alive: np.ndarray, cap: np.ndarray) -> float:
    a = alive.copy()
    n0 = a.sum()
    for _ in range(50):
        Wa = W.copy()
        Wa[~a, :] = 0
        Wa[:, ~a] = 0
        over = a & (wbtw(Wa, a) > cap)
        if not over.any():
            break
        a &= ~over
    return float(a.sum() / n0)


class _WBase:
    def __init__(self) -> None:
        b = _base()
        self.C = b.adj0
        W = np.load(_SRC / "liu2023_sc_avggm_400_nosubc.npy")
        self.W0 = np.where(self.C, W, 0.0)
        full = np.ones(N, dtype=bool)
        self.L0 = wbtw(self.W0, full)
        self.eps = 0.01 * float(self.L0.mean())
        self.cap = 1.2 * (self.L0 + self.eps)
        self.e_h = weff(self.W0, full)


@lru_cache(maxsize=1)
def _wbase() -> _WBase:
    return _WBase()


def _choose(rule, cands, load_, W, cap, eps, r) -> int:
    strength = W[cands].sum(1)
    if rule == "conc":
        return int(cands[np.lexsort((-r, -strength))[0]])
    if rule == "dist":
        return int(cands[np.lexsort((r, load_[cands]))[0]])
    tau = 0.0 if rule == "tau0" else 0.6
    ratio = (load_[cands] + eps) / cap[cands]
    ok = np.flatnonzero(ratio <= tau)
    if len(ok):
        return int(cands[ok[np.lexsort((-r[ok], -strength[ok]))[0]]])
    return int(cands[np.lexsort((r, ratio))[0]])


def run_schedule(W0, alive, lost_k, lost_s, schedule, policy, cap, eps, seed, snap=None, sprout_log=None):
    """scripts/time_varying_plasticity.run()과 같은 규칙. snap(W)은 50% 지점에서 호출."""
    b = _base()
    rng = random.Random(seed)
    W = W0.copy()
    steps = [n for n, k in lost_k.items() for _ in range(k)]
    rng.shuffle(steps)
    total = len(steps)
    load_ = wbtw(W, alive)
    near = b.dist <= b.lmax
    prng = random.Random(seed + 7)
    half = total // 2
    for i, n in enumerate(steps):
        sprout = i >= half if schedule == "seq" else prng.random() < i / max(total - 1, 1)
        if sprout_log is not None:
            sprout_log.append(bool(sprout))
        mask = (alive & (W[n] == 0) & near[n]) if sprout else (alive & (W[n] > 0))
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands):
            r = np.array([rng.random() for _ in range(len(cands))])
            t = _choose(policy[1] if sprout else policy[0], cands, load_, W, cap, eps, r)
            dw = lost_s[n] / lost_k[n]
            W[n, t] += dw
            W[t, n] += dw
        if (i + 1) % RECOMPUTE == 0:
            load_ = wbtw(W, alive)
        if snap is not None and i + 1 == half:
            snap(W)
    return W


def _metrics(W, alive, wb: _WBase) -> dict:
    return {"casc_m12": wcascade(W, alive, wb.cap), "casc_m10": wcascade(W, alive, wb.L0 + wb.eps), "eff_rel": weff(W, alive) / wb.e_h}


def lesion_setup(lesion_id: str):
    b, wb = _base(), _wbase()
    les = sorted(b.lesion(lesion_id)["nodes"])
    alive = np.ones(N, dtype=bool)
    alive[les] = False
    Wl = wb.W0.copy()
    Wl[les, :] = 0
    Wl[:, les] = 0
    lost_k = {int(n): int(wb.C[n, les].sum()) for n in np.flatnonzero(alive) if wb.C[n, les].sum() > 0}
    lost_s = {n: float(wb.W0[n, les].sum()) for n in lost_k}
    return Wl, alive, lost_k, lost_s


def run_plasticity_schedule(req: PlasticityScheduleRequest) -> PlasticityScheduleResponse:
    b, wb = _base(), _wbase()
    Wl, alive, lost_k, lost_s = lesion_setup(req.lesion_id)
    seed = _seed(req.lesion_id)
    none = _metrics(Wl, alive, wb)
    results = [PlasticityPolicyResultOut(policy="none", label="재조직 없음", mid=none, end=none)]
    sprout_bins: list[float] = []
    for key in [k for k in POLICIES if k in req.policies]:
        label, pol = POLICIES[key]
        mid: dict = {}
        log: list = []
        Wr = run_schedule(Wl, alive, lost_k, lost_s, req.schedule, pol, wb.cap, wb.eps, seed, lambda Wm: mid.update(_metrics(Wm, alive, wb)), log)
        if not sprout_bins and log:
            chunks = np.array_split(np.array(log, dtype=float), 10)
            sprout_bins = [float(c.mean()) if len(c) else 0.0 for c in chunks]
        results.append(PlasticityPolicyResultOut(policy=key, label=label, mid=mid, end=_metrics(Wr, alive, wb)))
    les = b.lesion(req.lesion_id)
    return PlasticityScheduleResponse(
        lesion_id=req.lesion_id, lesion_name=les["name"], schedule=req.schedule, steps=sum(lost_k.values()),
        sprout_fraction_by_decile=sprout_bins, results=results,
        honesty_note=(
            "가중치(기존 연결 강화 + 새 연결 발아) 모델의 계산 실험입니다. '강화가 먼저, 발아가 뒤따름'이라는 시간 순서는 주로 설치류 연구의 검색 요약에 "
            "근거하며(docs/58), 사람의 회복 시간 척도와 비율은 확인되지 않았습니다."
        ),
    )
