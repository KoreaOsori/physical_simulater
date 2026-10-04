"""시간에 따라 바뀌는 가소성(초기 강화 → 후기 발아)에서 시기에 맞춘 전략 전환이 나은가(docs/58).

문헌(검색 요약 기준, 원문 직접 확인은 못 함 -- docs/58에 기록): 뇌졸중 직후 수 시간~수 일에는 흥분/억제 균형 변화로 기존의
잠재 연결이 드러나고(unmasking) 쓰이며, 수상돌기 가시 형성은 1~2주에 최대, 손상 주변 축삭 발아(새 연결)는 첫 2~4주에 늘어난다
(Murphy & Corbett 2009 Nat Rev Neurosci; Carmichael; Cirillo et al. 2020 JCBFM). 즉 '기존 연결 강화가 먼저, 새 연결 형성이 뒤따르며 겹친다'.

H17-11: 강화형 + 이질적 가중치에서는 균등 분산이, 발아형에서는 정상 부하 지도 기반이 문턱형 연쇄에 더 안전했다.
그렇다면 시기에 맞춰 전략을 바꾸면(강화 시기 = 균등 분산, 발아 시기 = 정상 부하 지도 기반) 둘 다보다 나을까.

모델: 원래 가중치(γ=1). 재조직 단계 = 생존 영역이 잃은 연결 수만큼, 한 번에 잃은 강도 평균만큼(docs/57과 같음).
일정:
  seq  -- 앞 50% 단계는 강화(기존 생존 이웃), 뒤 50%는 발아(배선 제한 안 새 연결).
  ramp -- 단계마다 발아 확률이 0 -> 1로 선형 증가(겹치는 전환).
정책: 고정(τ=0, 균등 분산, τ=0.6, 허브 집중), 맞춤(강화 단계=균등 분산, 발아 단계=τ=0), 엇갈림(강화=τ=0, 발아=균등 분산), 재조직 없음.
평가: 중간(50% 단계 후)과 끝의 연쇄 생존(m=1.2, 1.0)과 가중 효율(정상 대비). 국소 증후군 12개(0, 2, …, 22번).

실행 전 예측:
  T1 끝에서 맞춤이 모든 고정 전략보다 연쇄에 강하다(m1.2·m1.0).
  T2 중간(강화가 주인 초기)에는 균등 분산 계열(균등 분산·맞춤)이 τ=0 계열(τ=0·엇갈림)보다 안전하다.
  T3 엇갈림이 허브 집중을 빼고 가장 나쁘다.

실행: REORG_PROCS=1 REORG_CACHE=... PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.time_varying_plasticity > out.json
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

from scripts.reorganization_hypotheses import SRC, load
from scripts.weighted_reorganization import N, wbtw, wcascade, weff

LESIONS = list(range(0, 24, 2))
RECOMPUTE = 20
POLICIES = {
    "τ=0": ("tau0", "tau0"),
    "균등 분산": ("dist", "dist"),
    "τ=0.6": ("tau06", "tau06"),
    "허브 집중": ("conc", "conc"),
    "맞춤(강화=분산, 발아=τ0)": ("dist", "tau0"),
    "엇갈림(강화=τ0, 발아=분산)": ("tau0", "dist"),
}


def choose(rule, cands, load_, W, cap, eps, r):
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


def run(W0, alive, lost_k, lost_s, dist, lmax, schedule, policy, cap, eps, seed, snap):
    """snap(W) 를 50% 지점에서 호출. 반환 최종 W."""
    rng = random.Random(seed)
    W = W0.copy()
    steps = [n for n, k in lost_k.items() for _ in range(k)]
    rng.shuffle(steps)
    total = len(steps)
    load_ = wbtw(W, alive)
    near = dist <= lmax
    prng = random.Random(seed + 7)  # 발아/강화 추첨용(정책 간 같은 일정 = 공통 난수)
    half = total // 2
    for i, n in enumerate(steps):
        if schedule == "seq":
            sprout = i >= half
        else:
            sprout = prng.random() < i / max(total - 1, 1)
        if sprout:
            mask = alive & (W[n] == 0) & near[n]
        else:
            mask = alive & (W[n] > 0)
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands):
            r = np.array([rng.random() for _ in range(len(cands))])
            rule = policy[1] if sprout else policy[0]
            t = choose(rule, cands, load_, W, cap, eps, r)
            dw = lost_s[n] / lost_k[n]
            W[n, t] += dw
            W[t, n] += dw
        if (i + 1) % RECOMPUTE == 0:
            load_ = wbtw(W, alive)
        if i + 1 == half:
            snap(W)
    return W


def metrics(W, alive, L0, eps, e_h) -> dict:
    return {"casc_m1.2": wcascade(W, alive, 1.2 * (L0 + eps)), "casc_m1.0": wcascade(W, alive, L0 + eps), "eff_rel": weff(W, alive) / e_h}


def job(li: int) -> dict:
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"timeplast58_{li}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    g, dist, _, lesions = load()
    C = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy") > 0
    np.fill_diagonal(C, False)
    W0 = np.where(C, np.load(SRC / "liu2023_sc_avggm_400_nosubc.npy"), 0.0)
    iu = np.triu_indices(N, 1)
    lmax = float(np.percentile(dist[iu][C[iu]], 75))
    full = np.ones(N, dtype=bool)
    L0 = wbtw(W0, full)
    eps = 0.01 * L0.mean()
    cap = 1.2 * (L0 + eps)
    e_h = weff(W0, full)
    les = sorted(lesions[li]["nodes"])
    alive = full.copy()
    alive[les] = False
    Wl = W0.copy()
    Wl[les, :] = 0
    Wl[:, les] = 0
    lost_k = {int(n): int(C[n, les].sum()) for n in np.flatnonzero(alive) if C[n, les].sum() > 0}
    lost_s = {n: float(W0[n, les].sum()) for n in lost_k}
    out = {"lesion": li, "res": {"재조직 없음": {"mid": metrics(Wl, alive, L0, eps, e_h), "end": metrics(Wl, alive, L0, eps, e_h)}}}
    for sch in ("seq", "ramp"):
        for name, pol in POLICIES.items():
            mid = {}
            Wr = run(Wl, alive, lost_k, lost_s, dist, lmax, sch, pol, cap, eps, li * 1000,
                     lambda Wm: mid.update(metrics(Wm, alive, L0, eps, e_h)))
            out["res"][f"{sch}|{name}"] = {"mid": mid, "end": metrics(Wr, alive, L0, eps, e_h)}
        print(f"lesion {li} {sch}", file=sys.stderr, flush=True)
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    return out


def main() -> None:
    with Pool(int(os.environ.get("REORG_PROCS", "1"))) as pool:
        res = pool.map(job, LESIONS, chunksize=1)
    names = list(res[0]["res"])
    table = {n: {ph: {k: float(np.mean([r["res"][n][ph][k] for r in res])) for k in ("casc_m1.2", "casc_m1.0", "eff_rel")} for ph in ("mid", "end")} for n in names}
    comp = {}
    for sch in ("seq", "ramp"):
        for a, b in (("맞춤(강화=분산, 발아=τ0)", "τ=0"), ("맞춤(강화=분산, 발아=τ0)", "균등 분산"), ("엇갈림(강화=τ0, 발아=분산)", "τ=0"), ("τ=0.6", "τ=0")):
            for ph in ("mid", "end"):
                for k in ("casc_m1.2", "casc_m1.0"):
                    x = np.array([r["res"][f"{sch}|{a}"][ph][k] for r in res])
                    y = np.array([r["res"][f"{sch}|{b}"][ph][k] for r in res])
                    dd = x - y
                    comp[f"{sch}|{ph}|{a} − {b}|{k}"] = {"diff": float(dd.mean()), "a_higher": int((dd > 0).sum()), "n": len(dd),
                                                        "p": float(stats.wilcoxon(x, y).pvalue) if np.any(dd != 0) else 1.0}
    print(json.dumps({"table": table, "compare": comp}, ensure_ascii=False))


if __name__ == "__main__":
    main()
