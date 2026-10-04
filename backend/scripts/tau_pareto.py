"""제약 강도 τ 파레토: 회복 – 기전별 강건성 – 장기 마모의 맞바꿈(docs/55, docs/54 다음 실험 ①).

H17 v2: 손상 후 불가피한 부하 재배치가 참조 부하 지도에서 '각 영역이 자기 정상 부하 대비 과도하게 벗어나지 않도록' 제약한다.
그 '과도하게'의 정도를 τ 하나로 두고 연속으로 훑는다.

τ 규칙(새 연결 하나마다):
  후보(배선 길이 제한 안, 아직 연결 안 된 생존 영역) 중 현재 부하 비율 r = (부하+1)/(1.2·정상 부하+1) ≤ τ 인 '허용' 후보가 있으면
  그중 현재 degree가 가장 큰 곳(허브 집중 = 빠른 회복, H16-2-1)에 붙이고, 없으면 r이 가장 작은 곳(정상 부하 지도 기반)에 붙인다.
  τ=0 -> 허용 후보가 없어 항상 정상 부하 지도 기반과 같다. τ=∞ -> 항상 허브 집중과 같다(난수 소비까지 같아 간선이 완전히 같다).

지표(국소 증후군 25개 평균, 재조직 없음·균등 분산·무작위도 기준점으로 함께):
  회복: 재조직 직후 전역 효율 / 문턱형 강건성: 연쇄 생존(m=1.2, 1.0) / 2차 타격 손실 /
  장기 마모: W1 점진형(자기 정상 대비 과부하²)·W2(절대 부하)만으로 10시기 뒤 효율(반복 3, 공통 난수) / 정상 부하 지도 충실도·과부하 비율.

실행 전 예측:
  P1 τ가 커질수록 효율은 오르고 연쇄 생존은 떨어진다(단조 맞바꿈).
  P2 '무릎'이 있다: 어떤 중간 τ(≈1.0~1.2)는 연쇄 생존을 정상 부하 지도 기반 수준(≥0.85)으로 지키면서 효율 차이의 절반 이상을 얻는다.
  P3 최적 τ가 기전마다 다르다: 문턱형 연쇄 -> τ=0, 점진형 W1 -> 큰 τ, W2 -> τ 계열 밖(균등 분산이 최선, H17-3).
  P4 중간 τ 중 양 끝점 어느 쪽에도 지배되지 않는(파레토 최적) 점이 있다.

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.tau_pareto > out.json
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

from scripts.fast_reorganize import N, btw_array, reorganize_fast, to_adj
from scripts.mixed_failure_model import World, simulate, strip
from scripts.null_network_distribution import cascade, global_eff
from scripts.reorganization_hypotheses import load

TAUS = [0.0, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0, 3.0, float("inf")]
REFS = ["none", "distributed", "random"]
WEAR = {"W1": np.array([1.0, 0, 0, 0]), "W2": np.array([0, 1.0, 0, 0])}
REPS = 3


def reorganize_tau(adj0, alive, lost, dist, lmax, tau, cap, rng: random.Random):
    adj = adj0.copy()
    queue = [n for n, k in lost.items() for _ in range(k)]
    rng.shuffle(queue)
    near = dist <= lmax
    btw = btw_array(adj, alive)
    added = 0
    for n in queue:
        mask = alive & ~adj[n] & near[n]
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) == 0:
            continue
        r = np.array([rng.random() for _ in range(len(cands))])
        ratio = (btw[cands] + 1.0) / (cap[cands] + 1.0)
        ok = ratio <= tau
        if ok.any():
            sub = np.flatnonzero(ok)
            deg = adj[cands[sub]].sum(1).astype(float)
            t = int(cands[sub[np.lexsort((-r[sub], -deg))[0]]])
        else:
            t = int(cands[np.lexsort((r, ratio))[0]])
        adj[n, t] = adj[t, n] = True
        added += 1
        if added % 10 == 0:
            btw = btw_array(adj, alive)
    return adj


def evaluate(world, ar, alive, L0, li) -> dict:
    b = btw_array(ar, alive)
    e0 = global_eff(ar, alive)
    k = max(1, int(round(0.05 * alive.sum())))
    top = np.argsort(-np.where(alive, b, -1))[:k]
    a2 = alive.copy()
    a2[top] = False
    out = {"global_eff": e0, "casc_m1.2": cascade(ar, alive, 1.2 * L0), "casc_m1.0": cascade(ar, alive, 1.0 * L0),
           "second_hit": (e0 - global_eff(ar, a2)) / e0, "loadmap_rho": float(stats.spearmanr(b[alive], L0[alive])[0]),
           "overload": float((b[alive] > 1.2 * L0[alive]).mean())}
    for name, w in WEAR.items():
        effs = [simulate(world, ar, alive, w, np.random.default_rng(li * 100 + rep), noisy=False)["eff"][-1] for rep in range(REPS)]
        out[f"{name}_effT"] = float(np.mean(effs))
    return out


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"tau55_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, _, lesions = load()
    world = World()
    adj_full, alive_full = to_adj(g)
    L0 = btw_array(adj_full, alive_full)
    cap = 1.2 * L0
    lmax = world.lmax
    les = set(lesions[li]["nodes"])
    alive = alive_full.copy()
    alive[list(les)] = False
    adj = strip(adj_full, alive)
    lost: dict = {}
    for a in les:
        for nb in np.flatnonzero(adj_full[a]):
            if int(nb) not in les:
                lost[int(nb)] = lost.get(int(nb), 0) + 1
    res = {}
    for tau in TAUS:
        ar = reorganize_tau(adj, alive, lost, dist, lmax, tau, cap, random.Random(li * 1000))
        res[f"tau={tau}"] = evaluate(world, ar, alive, L0, li)
    # 끝점 검증: τ=0 == headroom, τ=∞ == concentrated (간선 집합 동일)
    check = {}
    for tau, strat in ((0.0, "headroom"), (float("inf"), "concentrated")):
        ref = reorganize_fast(adj, alive, lost, dist, lmax, strat, random.Random(li * 1000), cap)
        mine = reorganize_tau(adj, alive, lost, dist, lmax, tau, cap, random.Random(li * 1000))
        check[strat] = bool((ref == mine).all())
    for s in REFS:
        ar = reorganize_fast(adj, alive, lost, dist, lmax, s, random.Random(li * 1000), cap)
        res[s] = evaluate(world, ar, alive, L0, li)
    out = {"lesion": li, "endpoint_identical": check, "res": res}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    print(f"done lesion {li}", file=sys.stderr, flush=True)
    return out


def pareto(points: dict, keys: list) -> list:
    """keys: (이름, 클수록 좋음 여부). 지배되지 않는 점들."""
    names = list(points)
    keep = []
    for a in names:
        dominated = False
        for b in names:
            if a == b:
                continue
            better_or_eq = all((points[b][k] >= points[a][k]) if up else (points[b][k] <= points[a][k]) for k, up in keys)
            strictly = any((points[b][k] > points[a][k]) if up else (points[b][k] < points[a][k]) for k, up in keys)
            if better_or_eq and strictly:
                dominated = True
                break
        if not dominated:
            keep.append(a)
    return keep


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(job, list(range(25)), chunksize=1)
    names = list(res[0]["res"])
    keys = list(res[0]["res"][names[0]])
    table = {n: {k: float(np.mean([r["res"][n][k] for r in res])) for k in keys} for n in names}
    objectives = {
        "회복(효율)": ("global_eff", True), "문턱형 연쇄(m1.2)": ("casc_m1.2", True), "문턱형 연쇄(m1.0)": ("casc_m1.0", True),
        "2차 타격": ("second_hit", False), "W1 점진형 10시기": ("W1_effT", True), "W2 활동 10시기": ("W2_effT", True),
    }
    best = {lab: (max if up else min)(names, key=lambda n: table[n][k]) for lab, (k, up) in objectives.items()}
    tau_names = [n for n in names if n.startswith("tau=")]
    best_tau = {lab: (max if up else min)(tau_names, key=lambda n: table[n][k]) for lab, (k, up) in objectives.items()}
    pf_all = pareto({n: table[n] for n in names}, [(k, up) for k, up in objectives.values()])
    pf_tau = pareto({n: table[n] for n in tau_names}, [(k, up) for k, up in objectives.values()])
    # 무릎: 연쇄 생존 ≥ 0.85를 지키는 가장 큰 τ와 그때 얻는 효율 몫
    e0, e1 = table["tau=0.0"]["global_eff"], table["tau=inf"]["global_eff"]
    knee = [n for n in tau_names if table[n]["casc_m1.2"] >= 0.85]
    knee_best = max(knee, key=lambda n: table[n]["global_eff"]) if knee else None
    # 병변 단위: 각 τ가 τ=0 대비 효율·연쇄에서 어떤지
    paired = {}
    for n in tau_names[1:]:
        for k in ("global_eff", "casc_m1.2", "W1_effT", "W2_effT"):
            x = np.array([r["res"][n][k] for r in res])
            y = np.array([r["res"]["tau=0.0"][k] for r in res])
            dd = x - y
            paired[f"{n}|{k}"] = {"diff_vs_tau0": float(dd.mean()), "higher": int((dd > 0).sum()),
                                  "p": float(stats.wilcoxon(x, y).pvalue) if np.any(dd != 0) else 1.0}
    print(json.dumps({
        "endpoint_identical": {k: all(r["endpoint_identical"][k] for r in res) for k in ("headroom", "concentrated")},
        "table": table, "best_overall": best, "best_tau": best_tau, "pareto_all": pf_all, "pareto_tau": pf_tau,
        "knee": {"tau": knee_best, "eff_share_of_gap": (table[knee_best]["global_eff"] - e0) / (e1 - e0) if knee_best else None},
        "paired_vs_tau0": paired,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
