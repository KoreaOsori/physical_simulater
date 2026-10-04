"""혼합 손상 모델 Failure = αW1 + βW2 + γW3 (+δW4) -- 가상 환자 데이터로 하는 검증(docs/52, 검토 의견 7번).

실제 임상 데이터가 없으므로, 임상 데이터에 맞추기 '전에' 해야 하는 단계를 가상 데이터로 한다:
  (A) 모수 회복(parameter recovery): 정답 (α,β,γ)를 정해 가상 환자의 종단 데이터를 만들고, 같은 모델로 적합해 정답을
      되찾는가. 몇 명의 환자가 필요한가. 관측 잡음(놓친 위축·거짓 위축)에 버티는가.
  (B) 모형 오지정: 정답에 W3 밖의 기전(W4 구조적 단절)이 섞였는데 W1~W3로만 적합하면 어떻게 틀리나, W4를 넣으면 회복되나.
  (C) 관측 수준: 영역별 손상 시점(종단 위축 지도)이 아니라 전역 효율 곡선만 있으면 혼합 비율을 구별할 수 있나.
  (D) 전략 지도: 혼합 비율에 따라 어떤 재조직 전략이 최선인가("어떤 손상에는 어떤 재조직이 최적인가").

손상 기전(각 영역의 시기당 위험; 정상 뇌에서 평균 1이 되게 정규화 -- 어떤 혼합이든 정상 뇌는 시기당 약 2개 영역을 잃는다):
  W1 과부하형(상대)  f1 = ((L+1)/(1.2·L0+1))² / 정상 평균   -- 자기 정상 부하 대비 초과(문턱 없는 점진형)
  W2 활동의존형(절대) f2 = L / L̄0                            -- de Haan et al. 2012
  W3 무작위           f3 = 1
  W4 구조적 단절      f4 = 4 × (원래 이웃 중 잃은 비율)        -- 정상 뇌에서 0, 이웃의 25%를 잃으면 기준 위험과 같음
  p_i = 1 − exp(−s · Σ_k w_k f_k,i),  s = 2/400(정상 뇌 기준).
적합: θ_k = s·w_k ≥ 0 로 두면 로그우도가 θ에 대해 오목 -> 유일한 최대(L-BFGS-B). w = θ/Σθ. 신뢰구간은 환자 단위 bootstrap.
관측 잡음: 실제 손상의 80%만 관측(민감도), 시기당 영역당 0.1% 거짓 손상. 적합은 '관측된' 그래프 위에서 특징을 계산한다.

실행: MODE=recovery|strategy|noise_aware REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.mixed_failure_model > out.json
"""

from __future__ import annotations

import json
import os
import random
import zlib
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import optimize, stats

from scripts.fast_reorganize import N, btw_array, reorganize_fast, to_adj
from scripts.null_network_distribution import global_eff
from scripts.reorganization_hypotheses import load

T = 10
S0 = 2.0 / N
SENS, FP = 0.8, 0.001
N_BOOT = 200


class World:
    def __init__(self):
        g, dist, modules, lesions = load()
        self.g, self.dist, self.lesions = g, dist, lesions
        self.adj0, self.alive0 = to_adj(g)
        self.L0 = btw_array(self.adj0, self.alive0)
        self.Lbar = self.L0.mean()
        self.cap = 1.2 * self.L0
        self.f1h = float((((self.L0 + 1) / (self.cap + 1)) ** 2).mean())
        self.deg0 = self.adj0.sum(1)
        self.lmax = float(np.percentile([dist[a, b] for a, b in g.edges], 75))
        self.sizes = [len(l["nodes"]) for l in lesions]

    def features(self, adj, alive) -> np.ndarray:
        L = btw_array(adj, alive)
        dead_nb = (self.adj0 & ~alive[None, :]).sum(1)
        F = np.column_stack([
            ((L + 1) / (self.cap + 1)) ** 2 / self.f1h,
            L / self.Lbar,
            np.ones(N),
            4.0 * dead_nb / np.maximum(self.deg0, 1),
        ])
        return F

    def patient(self, rng: np.random.Generator) -> np.ndarray:
        """가상 환자 병변: 절반은 증후군 병변, 절반은 공간적으로 인접한 무작위 병변."""
        if rng.random() < 0.5:
            nodes = self.lesions[int(rng.integers(len(self.lesions)))]["nodes"]
        else:
            k = int(rng.choice(self.sizes))
            nodes = np.argsort(self.dist[int(rng.integers(N))])[:k].tolist()
        alive = self.alive0.copy()
        alive[list(nodes)] = False
        return alive


def strip(adj, alive):
    a = adj.copy()
    a[~alive, :] = False
    a[:, ~alive] = False
    return a


def simulate(world: World, adj, alive, w: np.ndarray, rng: np.random.Generator, noisy: bool = True) -> dict:
    """정답 혼합 w로 T시기 마모. 반환: 관측 시기별 (특징, 관측 손상) -- 적합기가 보는 것은 '관측된' 그래프."""
    true_alive = alive.copy()
    obs_alive = alive.copy()
    X, Y, eff = [], [], [global_eff(strip(adj, true_alive), true_alive) * true_alive.sum() * (true_alive.sum() - 1) / (N * (N - 1))]
    for _ in range(T):
        Ft = world.features(strip(adj, true_alive), true_alive)
        p = 1 - np.exp(-S0 * Ft @ w)
        die = true_alive & (rng.random(N) < p)
        Fo = world.features(strip(adj, obs_alive), obs_alive) if noisy else Ft  # 잡음 없으면 관측 그래프 = 실제 그래프
        if noisy:
            seen = die & obs_alive & (rng.random(N) < SENS)
            false = obs_alive & ~die & (rng.random(N) < FP)
            y = seen | false
        else:
            y = die & obs_alive
        X.append(Fo[obs_alive])
        Y.append(y[obs_alive])
        true_alive &= ~die
        obs_alive &= ~y
        n = true_alive.sum()
        eff.append(global_eff(strip(adj, true_alive), true_alive) * n * (n - 1) / (N * (N - 1)) if n > 1 else 0.0)
    return {"X": np.vstack(X), "Y": np.concatenate(Y), "eff": eff}


def fit(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    K = X.shape[1]

    def nll(th):
        h = np.maximum(X @ th, 1e-12)
        return -(np.log1p(-np.exp(-h[Y])).sum() - h[~Y].sum())

    def grad(th):
        h = np.maximum(X @ th, 1e-12)
        e = np.exp(-h[Y])
        return -((X[Y] * (e / (1 - e))[:, None]).sum(0) - X[~Y].sum(0))

    r = optimize.minimize(nll, np.full(K, S0 / K), jac=grad, method="L-BFGS-B", bounds=[(0, None)] * K)
    return r.x


def recover(datasets: list, K: int, rng: np.random.Generator) -> dict:
    X = np.vstack([d["X"][:, :K] for d in datasets])
    Y = np.concatenate([d["Y"] for d in datasets])
    th = fit(X, Y)
    boots = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(datasets), len(datasets))
        Xb = np.vstack([datasets[i]["X"][:, :K] for i in idx])
        Yb = np.concatenate([datasets[i]["Y"] for i in idx])
        tb = fit(Xb, Yb)
        boots.append(tb / tb.sum())
    boots = np.array(boots)
    return {"w": (th / th.sum()).tolist(), "s": float(th.sum()), "ci95": np.percentile(boots, [2.5, 97.5], axis=0).T.tolist()}


def recovery_job(args) -> dict:
    tag, w_true, n_pat, rep, K_fit, noisy = args
    world = World()
    rng = np.random.default_rng(zlib.crc32(f"{tag}|{n_pat}|{rep}|{noisy}".encode()))
    w = np.array(w_true + [0.0] * (4 - len(w_true)))
    ds = [simulate(world, strip(world.adj0, a), a, w, rng, noisy) for a in (world.patient(rng) for _ in range(n_pat))]
    out = {"tag": tag, "w_true": w.tolist(), "n_patients": n_pat, "rep": rep, "noisy": noisy,
           "eff_retained": float(np.mean([d["eff"][-1] / d["eff"][0] for d in ds]))}
    for K in K_fit:
        r = recover(ds, K, rng)
        wt = w[:K] / w[:K].sum() if K < 4 else w
        r["abs_err"] = float(np.abs(np.array(r["w"]) - wt).max())
        r["covered"] = [bool(lo - 1e-9 <= t <= hi + 1e-9) for t, (lo, hi) in zip(wt, r["ci95"])]
        out[f"fit_K{K}"] = r
    print(f"done {tag} n={n_pat} rep={rep}", file=sys.stderr, flush=True)
    return out


STRATS = ["none", "local", "concentrated", "distributed", "headroom", "random"]


def strategy_job(args) -> dict:
    tag, w_true, li = args
    world = World()
    les = set(world.lesions[li]["nodes"])
    alive = world.alive0.copy()
    alive[list(les)] = False
    lost: dict = {}
    for a in les:
        for b in world.g.neighbors(a):
            if b not in les:
                lost[b] = lost.get(b, 0) + 1
    adj_l = strip(world.adj0, alive)
    w = np.array(w_true)
    out = {"tag": tag, "w": w_true, "lesion": li, "res": {}}
    for s in STRATS:
        ar = reorganize_fast(adj_l, alive, lost, world.dist, world.lmax, s, random.Random(li * 1000), world.cap)
        effs = []
        for rep in range(3):  # 공통 난수: 전략 간 같은 시드
            d = simulate(world, ar, alive, w, np.random.default_rng(li * 100 + rep), noisy=False)
            effs.append(d["eff"])
        e = np.array(effs).mean(0)
        out["res"][s] = {"eff0": float(e[0]), "effT": float(e[-1]), "retained": float(e[-1] / e[0])}
    print(f"done {tag} lesion {li}", file=sys.stderr, flush=True)
    return out


def cached(fn, key: str, args):
    d = os.environ.get("REORG_CACHE")
    if not d:
        return fn(args)
    p = Path(d) / f"mix52_{key}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    r = fn(args)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(r), encoding="utf-8")
    tmp.replace(p)
    return r


def _rec(args):
    tag, w, n, rep, K, noisy = args
    return cached(recovery_job, f"rec_{tag}_{n}_{rep}_{int(noisy)}", args)


def _str(args):
    return cached(strategy_job, f"str_{args[0]}_{args[2]}", args)


TRUTHS = {
    "W1": [1, 0, 0], "W2": [0, 1, 0], "W3": [0, 0, 1],
    "W1W2": [0.5, 0.5, 0], "W1W3": [0.5, 0, 0.5], "W2W3": [0, 0.5, 0.5],
    "center": [1 / 3, 1 / 3, 1 / 3], "mixA": [0.6, 0.3, 0.1], "mixB": [0.2, 0.2, 0.6],
}
MISSPEC = {"W4mix": [0.3, 0.2, 0.2, 0.3], "W4heavy": [0.1, 0.2, 0.1, 0.6]}


def main() -> None:
    mode = os.environ.get("MODE", "recovery")
    procs = int(os.environ.get("REORG_PROCS", "2"))
    if mode == "recovery":
        jobs = [(t, w, n, r, [3], True) for t, w in TRUTHS.items() for n in (10, 40) for r in range(3)]
        jobs += [(t, w, 40, 0, [3], False) for t, w in TRUTHS.items()]  # 잡음 없는 기준선
        jobs += [(t, w, 40, r, [3, 4], True) for t, w in MISSPEC.items() for r in range(3)]
        with Pool(procs) as pool:
            res = pool.map(_rec, jobs, chunksize=1)
        summ = {}
        for (t, w, n, r, K, noisy), x in zip(jobs, res):
            key = f"{t}|n{n}|{'noisy' if noisy else 'clean'}"
            s = summ.setdefault(key, {"w_true": x["w_true"], "fits": {}})
            for k in K:
                s["fits"].setdefault(f"K{k}", []).append({"w": x[f"fit_K{k}"]["w"], "abs_err": x[f"fit_K{k}"]["abs_err"], "covered": x[f"fit_K{k}"]["covered"]})
            s.setdefault("eff_retained", []).append(x["eff_retained"])
        for s in summ.values():
            for k, fl in s["fits"].items():
                s[f"{k}_mean_w"] = np.mean([f["w"] for f in fl], 0).tolist()
                s[f"{k}_max_abs_err_mean"] = float(np.mean([f["abs_err"] for f in fl]))
                s[f"{k}_coverage"] = float(np.mean([c for f in fl for c in f["covered"]]))
        # (C) 전역 효율 곡선만으로 구별되나: 40명·잡음 데이터의 환자별 효율 유지율 분포(진실 간 효과크기)
        effs = {t: [] for t in TRUTHS}
        for (t, w, n, r, K, noisy), x in zip(jobs, res):
            if t in TRUTHS and n == 40 and noisy:
                effs[t].append(x["eff_retained"])
        print(json.dumps({"summary": summ, "eff_retained_by_truth": {t: [float(np.mean(v)), float(np.std(v))] for t, v in effs.items()}}, ensure_ascii=False))
    else:
        grid = {}
        for a in range(5):
            for b in range(5 - a):
                grid[f"s{a}{b}"] = [a / 4, b / 4, (4 - a - b) / 4, 0.0]
        grid["W4"] = [0, 0, 0, 1.0]
        grid["W4W1"] = [0.5, 0, 0, 0.5]
        grid["W4W2"] = [0, 0.5, 0, 0.5]
        lesions = list(range(0, 25, 3))  # 9개
        jobs = [(t, w, li) for t, w in grid.items() for li in lesions]
        with Pool(procs) as pool:
            res = pool.map(_str, jobs, chunksize=1)
        out = {}
        for t, w in grid.items():
            rs = [x for x in res if x["tag"] == t]
            tab = {s: {k: float(np.mean([x["res"][s][k] for x in rs])) for k in ("eff0", "effT", "retained")} for s in STRATS}
            wins = {s: int(sum(max(STRATS, key=lambda q: x["res"][q]["effT"]) == s for x in rs)) for s in STRATS}
            out[t] = {"w": w, "table": tab, "best_effT": max(STRATS, key=lambda s: tab[s]["effT"]),
                      "best_retained": max(STRATS, key=lambda s: tab[s]["retained"]), "wins_effT": wins}
        print(json.dumps(out, ensure_ascii=False))



def fit_noise_aware(X: np.ndarray, Y: np.ndarray, sens: float = SENS, fp: float = FP) -> np.ndarray:
    """관측 잡음 모델을 우도에 넣은 적합: P(관측 손상) = sens·p + fp·(1−p), p = 1 − exp(−θ·f).
    sens·fp는 '알려져 있다'고 가정(실제로는 건강인 반복 촬영(test-retest)으로 보정해야 하는 값)."""
    K = X.shape[1]

    def nll(th):
        p = 1 - np.exp(-np.maximum(X @ th, 1e-12))
        q = np.clip(sens * p + fp * (1 - p), 1e-12, 1 - 1e-12)
        return -(np.log(q[Y]).sum() + np.log1p(-q[~Y]).sum())

    best = None
    for x0 in (np.full(K, S0 / K), np.eye(K)[0] * S0, np.eye(K)[1] * S0):
        r = optimize.minimize(nll, x0, method="L-BFGS-B", bounds=[(0, None)] * K)
        if best is None or r.fun < best.fun:
            best = r
    return best.x


def noise_aware_check() -> dict:
    """같은 잡음 데이터에 순진한 적합과 잡음 인지 적합을 나란히(40명, 진실 4개, 각 2회)."""
    world = World()
    out = {}
    for tag in ("W1", "W2", "center", "mixA"):
        w = np.array(TRUTHS[tag] + [0.0])
        rows = []
        for rep in range(2):
            rng = np.random.default_rng(zlib.crc32(f"na|{tag}|{rep}".encode()))
            ds = [simulate(world, strip(world.adj0, a), a, w, rng, True) for a in (world.patient(rng) for _ in range(40))]
            X = np.vstack([d["X"][:, :3] for d in ds])
            Y = np.concatenate([d["Y"] for d in ds])
            naive, aware = fit(X, Y), fit_noise_aware(X, Y)
            rows.append({"naive": (naive / naive.sum()).tolist(), "aware": (aware / aware.sum()).tolist()})
            print(f"done noise-aware {tag} {rep}", file=sys.stderr, flush=True)
        out[tag] = {"w_true": w[:3].tolist(), "naive_mean": np.mean([r["naive"] for r in rows], 0).tolist(),
                    "aware_mean": np.mean([r["aware"] for r in rows], 0).tolist(), "runs": rows}
    return out


if __name__ == "__main__":
    if os.environ.get("MODE") == "noise_aware":
        print(json.dumps(noise_aware_check()))
    else:
        main()
