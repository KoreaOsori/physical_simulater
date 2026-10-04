"""개인별 정상 부하 범위(μ_i, σ_i)·Z 점수를 개인 데이터 없이 미리 검증하기 -- 합성 개인 코호트(docs/53, 검토 의견 8·9번).

전제(정직성): 이 프로젝트에는 개인별 연결망이 없다(33명 합의 행렬 하나). 실제 σ_i의 크기는 이 스크립트로 알 수 없고,
여기서 만든 σ는 '내가 정한 생성 가정'의 산물이다. 그래서 σ의 크기를 주장하지 않고, σ 크기와 무관하게 답할 수 있는
'방법론 질문'만 묻는다. 변동 크기 v는 모르므로 0.1/0.2/0.3으로 훑는다.

합성 개인(생성 가정 G1): 합의 행렬에서 출발해
  - 합의 간선을 '평균 가중치가 약할수록 잘 빠지게' 지움(제거 확률 ∝ 1 − 가중치 순위, 평균 제거율 v),
  - 지운 수만큼 합의에 없는 간선을 '합의 간선의 길이 분포를 따르게' 추가(Betzel 2019 거리 보정 합의가 맞추는 성질).
  밀도·길이 분포는 개인마다 합의와 비슷하고, 약한 연결일수록 개인 차가 크다.
관측 잡음(생성 가정 G2): 같은 사람을 두 번 촬영하면 간선의 ε=5%가 같은 방식으로 다시 섞인다.

질문
  Q1 합의 지도 ≠ 개인 평균? 합성 33명의 다수결 합의(밀도 맞춤)에서 구한 L0_cons와 개인 부하 평균 μ를 비교 -- 특히 허브.
  Q2 분포 모양: 영역별 개인 간 부하 분포의 왜도, log 변환 후 왜도.
  Q3 개인화의 가치: 따로 뽑은 합성 '환자' 8명(병전 연결망을 오라클로 앎) × 병변 8개에서, 재조직 길잡이를
      ① 합의 지도 1.2·L0_cons ② 개인 평균 1.2·μ ③ Z 기준((부하−μ)/σ 최소인 영역에 연결) ④ 오라클(환자 자신의 병전 지도)
      ⑤ 균등 분산(기준)으로 바꿔, '환자 자신의 정상 부하 × 1.2'를 문턱으로 하는 연쇄 생존을 비교(H17-1의 가정을 개인 수준에 적용).
  Q4 관측 잡음: 두 번 촬영으로 잡음 분산을 추정해 σ를 보정할 수 있나(σ_관측 vs σ_진짜 vs σ_보정).

실행 전 예측: Q1 합의는 약한(개인적) 연결을 버려 허브 부하를 과대 추정한다. Q2 오른쪽 꼬리(log가 낫다).
Q3 합의·평균 길잡이는 오라클보다 조금 못하지만 균등 분산보다는 훨씬 낫다(개인화의 이득 < 정상 부하 지도 사용의 이득).
Q4 잡음이 σ를 부풀리고, 두 번 촬영 차이로 대부분 보정된다.

실행: REORG_CACHE=... REORG_PROCS=2 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.synthetic_individual_cohort > out.json
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

from scripts.fast_reorganize import N, btw_array
from scripts.null_network_distribution import cascade, global_eff
from scripts.reorganization_hypotheses import SRC, load

N_SUB = 33
N_PAT = 8
LESION_IDX = list(range(0, 25, 3))[:8]
EPS = 0.05
IU = np.triu_indices(N, 1)


class Base:
    def __init__(self):
        g, dist, _, lesions = load()
        self.dist, self.lesions = dist, lesions
        self.cons = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
        np.fill_diagonal(self.cons, False)
        w = np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy")
        e = self.cons[IU]
        self.ei = np.flatnonzero(e)  # 합의 간선의 상삼각 인덱스
        self.ni = np.flatnonzero(~e)
        wr = stats.rankdata(w[IU][self.ei]) / len(self.ei)  # 0..1, 강할수록 1
        self.weak = 1 - wr + 1e-3
        d = dist[IU]
        bins = np.linspace(0, d.max() + 1e-9, 31)
        h_e, _ = np.histogram(d[self.ei], bins)
        h_n, _ = np.histogram(d[self.ni], bins)
        ratio = np.where(h_n > 0, h_e / np.maximum(h_n, 1), 0)
        self.add_p = ratio[np.clip(np.digitize(d[self.ni], bins) - 1, 0, 29)]
        self.add_p = self.add_p / self.add_p.sum()
        self.lmax = float(np.percentile(d[self.ei], 75))


def to_adj(vec: np.ndarray) -> np.ndarray:
    a = np.zeros((N, N), dtype=bool)
    a[IU] = vec
    return a | a.T


def perturb(base: Base, vec: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    """간선 frac만큼을 약한 것 위주로 지우고, 같은 수를 길이 분포에 맞춰 더한다(현재 간선 집합 기준)."""
    v = vec.copy()
    on = np.flatnonzero(v)
    # 합의 간선이면 약함 가중, 아니면(이미 개인 간선) 평균 약함
    wk = np.full(len(on), base.weak.mean())
    pos = np.searchsorted(base.ei, on)
    isc = (pos < len(base.ei)) & (base.ei[np.minimum(pos, len(base.ei) - 1)] == on)
    wk[isc] = base.weak[pos[isc]]
    k = int(round(frac * len(on)))
    drop = rng.choice(on, size=k, replace=False, p=wk / wk.sum())
    v[drop] = False
    off = np.flatnonzero(~v)
    pmap = np.zeros(len(IU[0]))
    pmap[base.ni] = base.add_p
    pmap[base.ei] = base.add_p.mean()  # 합의 간선이 빠졌다가 다시 생기는 것도 허용
    p = pmap[off]
    add = rng.choice(off, size=k, replace=False, p=p / p.sum())
    v[add] = True
    return v


def individual(base: Base, v: float, rng) -> np.ndarray:
    return perturb(base, base.cons[IU].copy(), v, rng)


def reorganize_key(adj0, alive, lost, dist, lmax, key, rng: random.Random):
    """fast_reorganize의 headroom과 같은 구조, 정렬 키만 바꾼다. key(btw, cands) -> 낮을수록 우선."""
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
        t = int(cands[np.lexsort((r, key(btw, cands)))[0]])
        adj[n, t] = adj[t, n] = True
        added += 1
        if added % 10 == 0:
            btw = btw_array(adj, alive)
    return adj


def run_v(v: float) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"cohort53_v{v}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    base = Base()
    rng = np.random.default_rng(int(v * 1000) + 53)
    alive = np.ones(N, dtype=bool)
    subs = [individual(base, v, rng) for _ in range(N_SUB)]
    Ls = np.array([btw_array(to_adj(s), alive) for s in subs])
    mu, sd = Ls.mean(0), Ls.std(0, ddof=1)
    # Q1 다수결 합의(밀도 = 개인 평균)
    freq = np.mean(subs, axis=0)
    E = int(round(np.mean([s.sum() for s in subs])))
    cons_vec = np.zeros(len(IU[0]), dtype=bool)
    cons_vec[np.argsort(-freq + 1e-9 * base.dist[IU])[:E]] = True
    L0c = btw_array(to_adj(cons_vec), alive)
    hub = np.argsort(-mu)[: int(0.05 * N)]
    L0_true = btw_array(base.cons, alive)
    q1 = {
        "spearman_cons_vs_mu": float(stats.spearmanr(L0c, mu)[0]),
        "hub_ratio_cons_over_mu": float(np.mean(L0c[hub] / mu[hub])),
        "all_ratio_cons_over_mu_median": float(np.median(L0c / np.maximum(mu, 1e-9))),
        "spearman_mu_vs_generating_consensus": float(stats.spearmanr(mu, L0_true)[0]),
        "mean_individual_spearman_vs_mu": float(np.mean([stats.spearmanr(L, mu)[0] for L in Ls])),
        "cons_gini_minus_mu_gini": float(_gini(L0c) - _gini(mu)),
        "edges_cons": int(cons_vec.sum()), "edges_individual_mean": E,
    }
    # Q2 분포 모양
    sk = stats.skew(Ls, axis=0)
    skl = stats.skew(np.log1p(Ls), axis=0)
    q2 = {"median_skew_raw": float(np.median(sk)), "median_skew_log": float(np.median(skl)),
          "frac_nodes_log_less_skewed": float((np.abs(skl) < np.abs(sk)).mean()),
          "median_cv": float(np.median(sd / np.maximum(mu, 1e-9))), "hub_cv": float(np.median(sd[hub] / mu[hub]))}
    # Q4 관측 잡음
    obs1 = np.array([btw_array(to_adj(perturb(base, s, EPS, rng)), alive) for s in subs])
    obs2 = np.array([btw_array(to_adj(perturb(base, s, EPS, rng)), alive) for s in subs])
    sd_obs = obs1.std(0, ddof=1)
    noise_var = np.var(obs1 - obs2, axis=0, ddof=1) / 2
    sd_corr = np.sqrt(np.maximum(sd_obs**2 - noise_var, 0))
    q4 = {"median_sd_obs_over_true": float(np.median(sd_obs / np.maximum(sd, 1e-9))),
          "median_sd_corrected_over_true": float(np.median(sd_corr / np.maximum(sd, 1e-9))),
          "spearman_sd_obs_true": float(stats.spearmanr(sd_obs, sd)[0]),
          "spearman_sd_corr_true": float(stats.spearmanr(sd_corr, sd)[0])}
    # Q3 개인화의 가치
    guides = {
        "consensus": lambda b, c, Lp: (b[c] + 1) / (1.2 * L0c[c] + 1),
        "mu": lambda b, c, Lp: (b[c] + 1) / (1.2 * mu[c] + 1),
        "z": lambda b, c, Lp: (b[c] - mu[c]) / np.maximum(sd[c], 1e-6),
        "oracle": lambda b, c, Lp: (b[c] + 1) / (1.2 * Lp[c] + 1),
        "distributed": lambda b, c, Lp: b[c] + 1e-6 * c,
    }
    rows = []
    for pi in range(N_PAT):
        pv = individual(base, v, rng)
        pad = to_adj(pv)
        Lp = btw_array(pad, alive)
        for li in LESION_IDX:
            les = set(base.lesions[li]["nodes"])
            al = alive.copy()
            al[list(les)] = False
            adj = pad.copy()
            adj[list(les), :] = False
            adj[:, list(les)] = False
            lost: dict = {}
            for a in les:
                for b in np.flatnonzero(pad[a]):
                    if int(b) not in les:
                        lost[int(b)] = lost.get(int(b), 0) + 1
            for gname, fn in guides.items():
                ar = reorganize_key(adj, al, lost, base.dist, base.lmax, lambda b, c, fn=fn, Lp=Lp: fn(b, c, Lp), random.Random(pi * 100 + li))
                rows.append({"patient": pi, "lesion": li, "guide": gname,
                             "casc_own": cascade(ar, al, 1.2 * Lp), "global_eff": global_eff(ar, al)})
        print(f"v={v} patient {pi}", file=sys.stderr, flush=True)
    q3 = {gname: {k: float(np.mean([r[k] for r in rows if r["guide"] == gname])) for k in ("casc_own", "global_eff")} for gname in guides}
    for gname in ("consensus", "mu", "z", "distributed"):
        x = np.array([r["casc_own"] for r in rows if r["guide"] == "oracle"])
        y = np.array([r["casc_own"] for r in rows if r["guide"] == gname])
        q3[f"oracle-{gname}"] = {"diff": float((x - y).mean()), "oracle_higher": int((x > y).sum()), "n": len(x),
                                "p": float(stats.wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0}
    for a, b in (("z", "mu"), ("mu", "consensus")):
        x = np.array([r["casc_own"] for r in rows if r["guide"] == a])
        y = np.array([r["casc_own"] for r in rows if r["guide"] == b])
        q3[f"{a}-{b}"] = {"diff": float((x - y).mean()), "a_higher": int((x > y).sum()), "n": len(x),
                         "p": float(stats.wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0}
    out = {"v": v, "Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    return out


def _gini(x):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(run_v, [0.1, 0.2, 0.3], chunksize=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
