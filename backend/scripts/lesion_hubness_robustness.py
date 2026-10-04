"""H16-1 강건성 검증(docs/51). 사용자가 가져온 검토 의견의 5가지 + 추가 3가지.

H16-1: 국소 증후군 병변 25개에서 '재조직 없음' 전역 효율 손실은 병변 크기가 아니라 병변 허브성(평균 degree)과 관련된다.

검토 의견 요구: ① Pearson r ② Spearman ρ ③ bootstrap 95% CI ④ permutation test ⑤ 크기+허브성 동시 회귀.
추가:
  ⑥ 생성적 귀무 -- 같은 크기의 무작위 병변에서도 같은 관계가 나오나(증후군 특이적인가, 네트워크 일반 성질인가),
     그리고 실제 병변의 손실이 '같은 크기·같은 허브성' 무작위 병변보다 큰가.
  ⑦ leave-one-out -- 병변 하나(특히 69개 영역짜리)가 결과를 좌우하는가.
  ⑧ '잘린 간선 총수'(= 병변 영역 degree 합) 통제 -- 허브성이 단지 '잃은 연결 양'의 대리인가.
  ⑨ 병변 간 영역 중복 -- 독립 표본 가정 점검.

실행: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.lesion_hubness_robustness > out.json
"""

from __future__ import annotations

import json

import networkx as nx
import numpy as np
from scipy import stats

from scripts.reorganization_hypotheses import load
from scripts.short_long_term_reorganization import global_eff  # networkx와 값 일치, 약 6배 빠름

N_BOOT = 10_000
N_PERM = 20_000
N_RANDOM_PER_LESION = 200
SEED = 50


def eff_loss(g: nx.Graph, nodes, base: float) -> float:
    h = g.copy()
    h.remove_nodes_from(nodes)
    return base - global_eff(h)


def ols(y: np.ndarray, cols: dict) -> dict:
    """표준화 회귀(β는 표준편차 단위) + 일반 OLS t검정 + VIF."""
    names = list(cols)
    X = np.column_stack([stats.zscore(cols[k]) for k in names])
    yz = stats.zscore(y)
    Xd = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(Xd, yz, rcond=None)
    resid = yz - Xd @ beta
    dof = len(y) - Xd.shape[1]
    s2 = resid @ resid / dof
    se = np.sqrt(np.diag(s2 * np.linalg.inv(Xd.T @ Xd)))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), dof)
    r2 = 1 - resid @ resid / (yz @ yz)
    out = {"r2": float(r2), "n": len(y), "dof": dof, "coef": {}}
    for i, k in enumerate(names):
        others = [j for j in range(len(names)) if j != i]
        if others:
            bo, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(y)), X[:, others]]), X[:, i], rcond=None)
            ri = X[:, i] - np.column_stack([np.ones(len(y)), X[:, others]]) @ bo
            vif = float((X[:, i] @ X[:, i]) / (ri @ ri))
        else:
            vif = 1.0
        out["coef"][k] = {"beta_std": float(beta[i + 1]), "t": float(t[i + 1]), "p": float(p[i + 1]), "vif": vif}
    return out


def boot_ci(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> dict:
    n = len(x)
    pr, sr = [], []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        if np.ptp(x[idx]) == 0 or np.ptp(y[idx]) == 0:
            continue
        pr.append(stats.pearsonr(x[idx], y[idx])[0])
        sr.append(stats.spearmanr(x[idx], y[idx])[0])
    q = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]  # noqa: E731
    return {"pearson_ci95": q(pr), "spearman_ci95": q(sr), "n_valid": len(pr)}


def perm_p(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> dict:
    obs_p = stats.pearsonr(x, y)[0]
    obs_s = stats.spearmanr(x, y)[0]
    cp = cs = 0
    for _ in range(N_PERM):
        yp = rng.permutation(y)
        cp += abs(stats.pearsonr(x, yp)[0]) >= abs(obs_p)
        cs += abs(stats.spearmanr(x, yp)[0]) >= abs(obs_s)
    return {"pearson_p": (cp + 1) / (N_PERM + 1), "spearman_p": (cs + 1) / (N_PERM + 1)}


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    return str(o)


def _sig(r) -> dict:
    return {"statistic": float(r.statistic), "pvalue": float(r.pvalue)}


def main() -> None:
    rng = np.random.default_rng(SEED)
    g, _, _, lesions = load()
    base = global_eff(g)
    deg = dict(g.degree())
    all_nodes = np.array(sorted(g.nodes))

    size = np.array([len(l["nodes"]) for l in lesions], dtype=float)
    hub = np.array([np.mean([deg[n] for n in l["nodes"]]) for l in lesions])
    cut = np.array([len({(min(a, b), max(a, b)) for a in l["nodes"] for b in g.neighbors(a)}) for l in lesions], dtype=float)
    loss = np.array([eff_loss(g, l["nodes"], base) for l in lesions])

    res: dict = {"n_lesions": len(lesions), "healthy_global_eff": base}
    res["1_2_correlations"] = {
        "hub": {"pearson": _sig(stats.pearsonr(hub, loss)), "spearman": _sig(stats.spearmanr(hub, loss))},
        "size": {"pearson": _sig(stats.pearsonr(size, loss)), "spearman": _sig(stats.spearmanr(size, loss))},
        "cut_edges": {"pearson": _sig(stats.pearsonr(cut, loss)), "spearman": _sig(stats.spearmanr(cut, loss))},
        "hub_vs_size": _sig(stats.spearmanr(hub, size)),
    }
    res["3_bootstrap"] = boot_ci(hub, loss, rng)
    res["4_permutation"] = perm_p(hub, loss, rng)
    res["5_regression"] = {
        "hub+size": ols(loss, {"hub": hub, "size": size}),
        "hub+log_size": ols(loss, {"hub": hub, "log_size": np.log(size)}),
        "rank_hub+rank_size": ols(stats.rankdata(loss), {"hub": stats.rankdata(hub), "size": stats.rankdata(size)}),
    }
    res["8_cut_edges_control"] = {
        "hub+cut": ols(loss, {"hub": hub, "cut_edges": cut}),
        "hub+size+cut": ols(loss, {"hub": hub, "size": size, "cut_edges": cut}),
    }

    # ⑦ leave-one-out
    loo = []
    for i in range(len(lesions)):
        m = np.arange(len(lesions)) != i
        loo.append({
            "dropped": lesions[i]["name"],
            "spearman": float(stats.spearmanr(hub[m], loss[m])[0]),
            "pearson": float(stats.pearsonr(hub[m], loss[m])[0]),
            "beta_hub_given_size": ols(loss[m], {"hub": hub[m], "size": size[m]})["coef"]["hub"]["beta_std"],
        })
    res["7_leave_one_out"] = {
        "spearman_min": min(x["spearman"] for x in loo),
        "pearson_min": min(x["pearson"] for x in loo),
        "pearson_min_dropped": min(loo, key=lambda x: x["pearson"])["dropped"],
        "beta_hub_min": min(x["beta_hub_given_size"] for x in loo),
        "beta_hub_min_dropped": min(loo, key=lambda x: x["beta_hub_given_size"])["dropped"],
        "rows": loo,
    }

    # ⑥ 생성적 귀무: 병변마다 같은 크기 무작위 영역 집합 N개
    rs_s, rs_h, rs_l = [], [], []
    z_vs_random = []
    for li, l in enumerate(lesions):
        k = len(l["nodes"])
        hl, ll = [], []
        for _ in range(N_RANDOM_PER_LESION):
            nodes = rng.choice(all_nodes, k, replace=False)
            hl.append(np.mean([deg[n] for n in nodes]))
            ll.append(eff_loss(g, nodes, base))
        hl, ll = np.array(hl), np.array(ll)
        rs_s += [k] * len(hl)
        rs_h += list(hl)
        rs_l += list(ll)
        # 같은 크기 무작위 병변들 안에서 허브성으로 손실을 예측한 뒤 실제 병변의 잔차
        slope, icpt = np.polyfit(hl, ll, 1)
        resid_sd = np.std(ll - (slope * hl + icpt))
        z_vs_random.append({
            "lesion": l["name"],
            "size": k,
            "loss_percentile_among_same_size": float((ll < loss[li]).mean()),
            "hub_percentile_among_same_size": float((hl < hub[li]).mean()),
            "resid_z_given_hub": float((loss[li] - (slope * hub[li] + icpt)) / resid_sd) if resid_sd > 0 else 0.0,
        })
        print(f"random null {li + 1}/{len(lesions)}", flush=True, file=__import__("sys").stderr)
    rs_s, rs_h, rs_l = map(np.array, (rs_s, rs_h, rs_l))
    res["6_random_lesion_null"] = {
        "n": int(len(rs_l)),
        "spearman_hub_loss": float(stats.spearmanr(rs_h, rs_l)[0]),
        "spearman_size_loss": float(stats.spearmanr(rs_s, rs_l)[0]),
        "regression": ols(rs_l, {"hub": rs_h, "size": rs_s.astype(float)}),
        "within_size_spearman_hub_loss_median": float(np.median([
            stats.spearmanr(rs_h[rs_s == k], rs_l[rs_s == k])[0] for k in np.unique(rs_s) if k > 1
        ])),
        "real_lesions": z_vs_random,
        "mean_loss_percentile": float(np.mean([z["loss_percentile_among_same_size"] for z in z_vs_random])),
        "mean_resid_z_given_hub": float(np.mean([z["resid_z_given_hub"] for z in z_vs_random])),
    }

    # ⑨ 병변 간 영역 중복
    sets = [set(l["nodes"]) for l in lesions]
    overlaps = [(lesions[i]["name"], lesions[j]["name"], len(sets[i] & sets[j]) / min(len(sets[i]), len(sets[j])))
                for i in range(len(sets)) for j in range(i + 1, len(sets)) if sets[i] & sets[j]]
    res["9_overlap"] = {
        "pairs_sharing_regions": len(overlaps),
        "total_pairs": len(sets) * (len(sets) - 1) // 2,
        "pairs_overlap_ge_50pct": sum(o[2] >= 0.5 for o in overlaps),
        "top": sorted(overlaps, key=lambda o: -o[2])[:6],
    }
    res["per_lesion"] = [
        {"lesion": l["name"], "size": int(size[i]), "hub": float(hub[i]), "cut_edges": int(cut[i]), "loss": float(loss[i])}
        for i, l in enumerate(lesions)
    ]
    print(json.dumps(res, ensure_ascii=False, default=_jsonable))


if __name__ == "__main__":
    main()
