"""단계형·적응형 재조직과 허용치(실패 문턱) 불확실성(docs/56, docs/54 다음 실험 ②).

docs/55: 최적의 제약은 '실패 문턱 아래 여유선까지 허용'(τ≈0.75)이지만, 문턱을 과대평가하면 절벽처럼 무너진다(비대칭 위험).
여기서 묻는 것:
  A. 시기별 전략 전환(단계형): 처음 x%의 연결은 허브 집중(빠른 회복), 나머지는 정상 부하 지도 기반 -- 또는 그 반대.
  B. τ 상승형: 처음엔 보수적(τ=0)으로 시작해 예산이 쓰일수록 τ를 0.75까지 선형으로 올린다('천천히 허용을 넓힌다').
  C. 허용치를 모를 때의 선택: 실제 문턱 m ∈ {0.9, 1.0, 1.1, 1.2, 1.3, 1.5}(같은 확률)에서 각 정책의 연쇄 생존 -> 기대값·최악·최대 후회.

정책: 고정 τ 8개(0, 0.25, 0.5, 0.6, 0.75, 0.9, 1.0, ∞), 단계형 3개(허브→정상 25%·50%, 정상→허브 50%), τ 상승형 1개, 기준 3개(없음·균등 분산·무작위).
지표: 회복 곡선(예산 10/25/50/100% 시점 효율, 곡선 넓이), 연쇄 생존 6개 m, 2차 타격 손실, W1·W2 10시기 효율(반복 3).

실행 전 예측:
  S1 허브 우선 단계형(허브→정상)은 초기(25%) 회복이 τ=0보다 빠르고, 최종 연쇄 생존(m1.2)은 τ=0에 가깝다.
  S2 허용치를 모를 때 기대 연쇄 생존·최대 후회 기준 최적 고정 τ는 0.5 근처(0.75는 낮은 m에서 무너져 손해).
  S3 τ 상승형은 고정 τ=0.75보다 문턱 불확실성에 강하다(최대 후회가 작다).

실행: REORG_PROCS=2 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.staged_adaptive_reorganization > out.json
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

INF = float("inf")
MS = [0.9, 1.0, 1.1, 1.2, 1.3, 1.5]
CHECK = [0.1, 0.25, 0.5, 1.0]
WEAR = {"W1": np.array([1.0, 0, 0, 0]), "W2": np.array([0, 1.0, 0, 0])}
REPS = 3


def policies() -> dict:
    p = {f"τ={t}": (lambda frac, t=t: t) for t in (0.0, 0.25, 0.5, 0.6, 0.75, 0.9, 1.0, INF)}
    p["단계 허브→정상 25%"] = lambda frac: INF if frac < 0.25 else 0.0
    p["단계 허브→정상 50%"] = lambda frac: INF if frac < 0.5 else 0.0
    p["단계 정상→허브 50%"] = lambda frac: 0.0 if frac < 0.5 else INF
    p["τ 상승 0→0.75"] = lambda frac: 0.75 * frac
    return p


def reorganize_policy(adj0, alive, lost, dist, lmax, tau_of, cap, rng: random.Random, curve: list | None = None):
    """tau_of(예산 진행률) -> 그 시점의 τ. 회복 곡선은 CHECK 시점 효율을 curve에 기록."""
    adj = adj0.copy()
    queue = [n for n, k in lost.items() for _ in range(k)]
    rng.shuffle(queue)
    total = len(queue)
    near = dist <= lmax
    btw = btw_array(adj, alive)
    added = 0
    marks = {max(1, int(round(c * total))): c for c in CHECK}
    for i, n in enumerate(queue):
        mask = alive & ~adj[n] & near[n]
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) > 0:
            tau = tau_of(i / max(total, 1))
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
        if curve is not None and (i + 1) in marks:
            curve.append((marks[i + 1], global_eff(adj, alive)))
    return adj


def evaluate(world, ar, alive, L0, li, curve) -> dict:
    b = btw_array(ar, alive)
    e0 = global_eff(ar, alive)
    k = max(1, int(round(0.05 * alive.sum())))
    top = np.argsort(-np.where(alive, b, -1))[:k]
    a2 = alive.copy()
    a2[top] = False
    out = {"global_eff": e0, "second_hit": (e0 - global_eff(ar, a2)) / e0}
    for c, e in curve:
        out[f"eff@{c}"] = e
    for m in MS:
        out[f"casc_m{m}"] = cascade(ar, alive, m * L0)
    for name, w in WEAR.items():
        out[f"{name}_effT"] = float(np.mean([simulate(world, ar, alive, w, np.random.default_rng(li * 100 + rep), noisy=False)["eff"][-1] for rep in range(REPS)]))
    return out


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"staged56_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, _, lesions = load()
    world = World()
    adj_full, alive_full = to_adj(g)
    L0 = btw_array(adj_full, alive_full)
    cap = 1.2 * L0
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
    for name, tau_of in policies().items():
        curve: list = []
        ar = reorganize_policy(adj, alive, lost, dist, world.lmax, tau_of, cap, random.Random(li * 1000), curve)
        res[name] = evaluate(world, ar, alive, L0, li, curve)
    e_l = global_eff(adj, alive)
    for s in ("none", "distributed", "random"):
        ar = reorganize_fast(adj, alive, lost, dist, world.lmax, s, random.Random(li * 1000), cap)
        curve = [(c, e_l if s == "none" else np.nan) for c in CHECK]
        res[s] = evaluate(world, ar, alive, L0, li, curve)
    out = {"lesion": li, "eff_lesioned": e_l, "res": res}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    print(f"done lesion {li}", file=sys.stderr, flush=True)
    return out


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(job, list(range(25)), chunksize=1)
    names = list(res[0]["res"])
    keys = list(res[0]["res"][names[0]])
    table = {n: {k: float(np.nanmean([r["res"][n][k] for r in res])) for k in keys} for n in names}
    # 회복 곡선 넓이(재조직 전 효율 대비 이득의 평균, 정책만)
    for n in names:
        if np.isnan(table[n].get("eff@0.1", np.nan)):
            continue
        gains = [np.mean([r["res"][n][f"eff@{c}"] - r["eff_lesioned"] for c in CHECK]) for r in res]
        table[n]["recovery_auc"] = float(np.mean(gains))
    # C. 허용치 불확실성: m 균등 사전분포에서 기대·최악·최대 후회(정책 + 기준)
    casc = {n: np.array([table[n][f"casc_m{m}"] for m in MS]) for n in names}
    best_per_m = np.max(np.array(list(casc.values())), axis=0)
    robust = {n: {"expected": float(v.mean()), "worst": float(v.min()), "max_regret": float((best_per_m - v).max())} for n, v in casc.items()}
    # 병변 단위 쌍대: 각 정책 vs τ=0
    paired = {}
    for n in names:
        if n == "τ=0.0":
            continue
        for k in ("eff@0.25", "global_eff", "casc_m1.0", "casc_m1.2", "W1_effT", "W2_effT"):
            x = np.array([r["res"][n][k] for r in res], float)
            y = np.array([r["res"]["τ=0.0"][k] for r in res], float)
            if np.isnan(x).any():
                continue
            dd = x - y
            paired[f"{n}|{k}"] = {"diff": float(dd.mean()), "higher": int((dd > 0).sum()), "p": float(stats.wilcoxon(x, y).pvalue) if np.any(dd != 0) else 1.0}
    print(json.dumps({"table": table, "robust_over_m": robust, "best_expected": max(robust, key=lambda n: robust[n]["expected"]),
                      "best_worst": max(robust, key=lambda n: robust[n]["worst"]), "best_regret": min(robust, key=lambda n: robust[n]["max_regret"]),
                      "paired_vs_tau0": paired}, ensure_ascii=False))


if __name__ == "__main__":
    main()
