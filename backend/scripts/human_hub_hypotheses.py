"""H1 후속 가설(H1-1, H1-2, H1-3) 재분석 (docs/48).

외부 검토 의견(사용자 제공)이 제안한 방향 -- 연속 질환 수, 여러 중심성 지표 분리, 순열 검정, 질환별
분석, 다중검정 보정, 분자 취약성과의 결합 모델 -- 을 실제 데이터로 수행한다.

데이터:
- 구조 연결: Liu, Shafiei, Baillet & Mišić 2023(NeuroImage) 부속 HCP 합의 구조 연결 400×400(이진, 원본 전체).
  이 프로젝트의 거시 커넥톰(app/data/human_macro_connectome.json)은 네트워크 내부 간선 2,041개만 담고 있었다
  -- 원본의 네트워크 간 간선 3,018개가 빠져 그래프가 8조각이었다(docs/48에서 발견). 여기서는 원본 전체를 쓴다.
- 수용체: Hansen et al. 2022(Nat Neurosci 25:1569) 19종 신경전달물질 수용체/수송체 PET 밀도, Schaefer-400.
- 질환 매핑: 이 프로젝트의 32개 질환 → 해부학적 라벨(AAL) → 영역(docs/33). 교육용 큐레이션이지 환자 데이터가 아니다.

순열 귀무모형: 질환 매핑이 해부학적 라벨 단위로 만들어졌으므로(이웃 영역이 같은 라벨을 공유) 영역 단위로
섞으면 p값이 지나치게 작아진다. 각 질환의 라벨을 같은 개수의 무작위 라벨로 바꾸는 '라벨 단위 순열'을 쓴다.

실행: backend/.venv/Scripts/python.exe -m scripts.human_hub_hypotheses > out.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "data" / "sources" / "human"
N_PERM = 5000
RNG = np.random.default_rng(20260929)

RECEPTORS = ["5HT1a", "5HT1b", "5HT2a", "5HT4", "5HT6", "5HTT", "A4B2", "CB1", "D1", "D2", "DAT", "GABAa", "H3", "M1", "mGluR5", "MOR", "NET", "NMDA", "VAChT"]


def load():
    d = json.loads((ROOT / "app" / "data" / "human_macro_connectome.json").read_text(encoding="utf-8"))
    regions = sorted(d["regions"], key=lambda r: int(r["id"]))
    assert [int(r["id"]) for r in regions] == list(range(1, 401))
    sc = np.load(SRC / "liu2023_sc_cons_400_nosubc.npy")
    rec = np.loadtxt(SRC / "hansen2022_receptor_data_scale400.csv", delimiter=",")
    return d, regions, sc, rec


def graph_metrics(adj: np.ndarray, modules: list[str]) -> dict[str, np.ndarray]:
    g = nx.from_numpy_array(adj)
    n = adj.shape[0]
    deg = adj.sum(1)
    btw = nx.betweenness_centrality(g)
    clo = nx.closeness_centrality(g)
    try:
        eig = nx.eigenvector_centrality_numpy(g)
    except Exception:  # 조각난 그래프에선 정의가 불안정
        eig = dict.fromkeys(range(n), float("nan"))
    mod = np.array(modules)
    pc = np.zeros(n)
    for i in range(n):
        if deg[i] == 0:
            continue
        s = 0.0
        for m in set(modules):
            s += (adj[i, mod == m].sum() / deg[i]) ** 2
        pc[i] = 1 - s  # 참여계수(Guimerà & Amaral 2005), 모듈 = Yeo-7 네트워크
    thr = np.percentile(deg, 85)
    rich = (deg >= thr).astype(float)
    return {
        "degree": deg.astype(float),
        "betweenness": np.array([btw[i] for i in range(n)]),
        "closeness": np.array([clo[i] for i in range(n)]),
        "eigenvector": np.array([eig[i] for i in range(n)]),
        "participation": pc,
        "rich_club": rich,
    }


def disease_sets(d, regions):
    # 질환 매핑은 좌우를 합친 기본 이름(예: "Fusiform" = Fusiform_L + Fusiform_R) 단위다
    # (scripts/human_anatomical_labels.resolve_disorders) -- 순열 단위도 똑같이 맞춘다.
    def base(label: str) -> str:
        return label[:-2] if label.endswith(("_L", "_R")) else label

    label_of = [base(r["anatomical_label"]) for r in regions]
    labels = sorted(set(label_of))
    label_regions = {lab: np.array([i for i, x in enumerate(label_of) if x == lab]) for lab in labels}
    sets = []
    for dis in d["known_disorders"]:
        idx = np.array(sorted(int(x) - 1 for x in dis["region_ids"]))
        sets.append({"name": dis["name"], "category": dis["category"], "labels": list(dis["anatomical_labels"]), "idx": idx})
    return labels, label_regions, sets


def count_vector(idx_sets, n=400) -> np.ndarray:
    c = np.zeros(n)
    for idx in idx_sets:
        c[idx] += 1
    return c


def perm_sets(sets, labels, label_regions, rng):
    """라벨 단위 순열: 각 질환의 라벨 수만큼 무작위 라벨을 뽑아 그 라벨의 모든 영역을 할당."""
    out = []
    for s in sets:
        k = max(1, len(s["labels"]))
        chosen = rng.choice(len(labels), size=k, replace=False)
        out.append(np.unique(np.concatenate([label_regions[labels[c]] for c in chosen])))
    return out


def bh(pvals: list[float]) -> list[float]:
    p = np.array(pvals)
    order = np.argsort(p)
    q = np.empty_like(p)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[i] * len(p) / rank)
        q[i] = prev
    return q.tolist()


def partial_spearman(x, y, z):
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    res = lambda a: a - np.polyval(np.polyfit(rz, a, 1), rz)  # noqa: E731
    return float(np.corrcoef(res(rx), res(ry))[0, 1])


def main() -> None:
    d, regions, sc, rec = load()
    modules = [r["network"] for r in regions]
    labels, label_regions, sets = disease_sets(d, regions)
    count = count_vector([s["idx"] for s in sets])

    # 매핑 검증: 질환의 영역 = 그 라벨의 모든 영역인가(라벨 단위 순열이 원 매핑과 같은 생성 규칙인지)
    exact = sum(1 for s in sets if set(s["idx"].tolist()) == set(np.concatenate([label_regions[l] for l in s["labels"] if l in label_regions]).tolist()))

    old_adj = np.zeros((400, 400))
    for e in d["edges"]:
        a, b = int(e["a"]) - 1, int(e["b"]) - 1
        old_adj[a, b] = old_adj[b, a] = 1
    full_adj = sc.astype(float)

    out = {"mapping_label_exact_disorders": exact, "n_disorders": len(sets)}

    # --- 원래 H1 재현(조각난 그래프, 원래 복합 점수) ---
    g_old = nx.from_numpy_array(old_adj)
    deg_old = old_adj.sum(1)
    btw_old = np.array(list(nx.betweenness_centrality(g_old).values()))
    pr = nx.pagerank(g_old)
    pr_old = np.array([pr[i] for i in range(400)])
    norm = lambda v: (v - v.min()) / (v.max() - v.min()) if v.max() > v.min() else v * 0  # noqa: E731
    combined_old = (norm(deg_old / deg_old.max()) + norm(btw_old) + norm(pr_old)) / 3
    out["h1_reproduction_pearson_old_graph"] = float(np.corrcoef(count, combined_old)[0, 1])

    # --- H1-1: 전체 그래프, 지표별 ---
    m_full = graph_metrics(full_adj, modules)
    m_old = graph_metrics(old_adj, modules)
    perm_counts = [count_vector(perm_sets(sets, labels, label_regions, RNG)) for _ in range(N_PERM)]
    rows = []
    for key, vals in m_full.items():
        rs = stats.spearmanr(count, vals).statistic
        rp = float(np.corrcoef(count, vals)[0, 1])
        null_s = np.array([stats.spearmanr(pc_, vals).statistic for pc_ in perm_counts])
        p_perm = float((np.sum(np.abs(null_s) >= abs(rs)) + 1) / (N_PERM + 1))
        rows.append({
            "metric": key,
            "spearman": float(rs),
            "pearson": rp,
            "spearman_old_graph": float(stats.spearmanr(count, m_old[key]).statistic) if not np.isnan(m_old[key]).any() else None,
            "partial_spearman_controlling_degree": None if key == "degree" else partial_spearman(vals, count, m_full["degree"]),
            "null_mean": float(null_s.mean()),
            "null_sd": float(null_s.std()),
            "p_label_perm": p_perm,
        })
    q = bh([r["p_label_perm"] for r in rows])
    for r, qq in zip(rows, q):
        r["q_fdr"] = qq
    out["h1_1"] = {"edges_full": int(np.triu(full_adj, 1).sum()), "edges_old": int(np.triu(old_adj, 1).sum()), "rows": rows}

    # --- H1-2: 질환별 (영역 평균 z 점수 vs 라벨 단위 순열) ---
    z = {k: (v - v.mean()) / v.std() for k, v in m_full.items() if k in ("degree", "betweenness", "participation")}
    per = []
    for si, s in enumerate(sets):
        rec_row = {"name": s["name"], "category": s["category"], "n_regions": int(len(s["idx"]))}
        for key, zv in z.items():
            obs = float(zv[s["idx"]].mean())
            k = max(1, len(s["labels"]))
            null = []
            for _ in range(2000):
                chosen = RNG.choice(len(labels), size=k, replace=False)
                ridx = np.unique(np.concatenate([label_regions[labels[c]] for c in chosen]))
                null.append(zv[ridx].mean())
            null = np.array(null)
            rec_row[key] = {"mean_z": obs, "effect_sd": float((obs - null.mean()) / null.std()), "p": float((np.sum(np.abs(null - null.mean()) >= abs(obs - null.mean())) + 1) / 2001)}
        per.append(rec_row)
    all_p = [(i, key, per[i][key]["p"]) for i in range(len(per)) for key in z]
    qs = bh([p for _, _, p in all_p])
    for (i, key, _), qq in zip(all_p, qs):
        per[i][key]["q"] = qq
    out["h1_2"] = per

    # --- H1-3: 모델 비교 (질환 수 ~ 연결 + 수용체) ---
    rz = (rec - rec.mean(0)) / rec.std(0)
    u, s_, vt = np.linalg.svd(rz, full_matrices=False)
    pcs = u[:, :3] * s_[:3]
    var_expl = (s_**2 / (s_**2).sum())[:3].tolist()
    loadings = {RECEPTORS[j]: float(vt[0, j]) for j in range(19)}

    def zs(v):
        return (v - v.mean()) / v.std()

    blocks = {
        "M1: 중심성(degree+betweenness)": [zs(m_full["degree"]), zs(m_full["betweenness"])],
        "M2: M1+참여계수": [zs(m_full["degree"]), zs(m_full["betweenness"]), zs(m_full["participation"])],
        "M3: M1+수용체 PC1-3": [zs(m_full["degree"]), zs(m_full["betweenness"]), *[zs(pcs[:, k]) for k in range(3)]],
        "M4: M2+수용체 PC1-3": [zs(m_full["degree"]), zs(m_full["betweenness"]), zs(m_full["participation"]), *[zs(pcs[:, k]) for k in range(3)]],
        "M5: 수용체 PC1-3만": [zs(pcs[:, k]) for k in range(3)],
    }

    def r2(y, cols):
        X = np.column_stack([np.ones(len(y)), *cols])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        r2_ = 1 - resid.var() / y.var()
        p = X.shape[1] - 1
        adj = 1 - (1 - r2_) * (len(y) - 1) / (len(y) - p - 1)
        return r2_, adj, beta

    models = []
    for name, cols in blocks.items():
        r2_, adj, beta = r2(count, cols)
        null = np.array([r2(pc_, cols)[0] for pc_ in perm_counts[:2000]])
        models.append({"model": name, "r2": float(r2_), "adj_r2": float(adj), "betas": [float(b) for b in beta[1:]], "p_label_perm": float((np.sum(null >= r2_) + 1) / 2001), "null_r2_mean": float(null.mean())})
    # 증분: M1 -> M3 (수용체 추가)의 ΔR²를 같은 귀무모형으로
    d_obs = r2(count, blocks["M3: M1+수용체 PC1-3"])[0] - r2(count, blocks["M1: 중심성(degree+betweenness)"])[0]
    d_null = np.array([r2(pc_, blocks["M3: M1+수용체 PC1-3"])[0] - r2(pc_, blocks["M1: 중심성(degree+betweenness)"])[0] for pc_ in perm_counts[:2000]])
    out["h1_3"] = {
        "receptor_pc_variance_explained": var_expl,
        "receptor_pc1_loadings": loadings,
        "models": models,
        "delta_r2_receptors_over_centrality": float(d_obs),
        "delta_r2_p_label_perm": float((np.sum(d_null >= d_obs) + 1) / 2001),
    }
    print(json.dumps(out, ensure_ascii=False))


def extra() -> None:
    """H1-4(복합 vs 국소 질환, 질환을 단위로) + H1-5(알츠하이머 영역의 기능 연결 허브성, Buckner et al. 2009)."""
    d, regions, sc, _rec = load()
    modules = [r["network"] for r in regions]
    labels, label_regions, sets = disease_sets(d, regions)
    fc = np.load(SRC / "liu2023_fc_cons_400.npy")
    np.fill_diagonal(fc, 0)
    fc_strength = np.where(fc > 0, fc, 0).sum(1)  # 양의 기능 연결 강도(기능 허브성)
    m = graph_metrics(sc.astype(float), modules)
    feats = {"sc_degree": m["degree"], "sc_betweenness": m["betweenness"], "sc_participation": m["participation"], "fc_strength": fc_strength}
    zf = {k: (v - v.mean()) / v.std() for k, v in feats.items()}

    per = []
    for s in sets:
        k = max(1, len(s["labels"]))
        nulls = {key: [] for key in zf}
        for _ in range(4000):
            chosen = RNG.choice(len(labels), size=k, replace=False)
            ridx = np.unique(np.concatenate([label_regions[labels[c]] for c in chosen]))
            for key, zv in zf.items():
                nulls[key].append(zv[ridx].mean())
        row = {"name": s["name"], "category": s["category"]}
        for key, zv in zf.items():
            obs = zv[s["idx"]].mean()
            nu = np.array(nulls[key])
            row[key] = {"effect_sd": float((obs - nu.mean()) / nu.std()), "p": float((np.sum(np.abs(nu - nu.mean()) >= abs(obs - nu.mean())) + 1) / 4001)}
        per.append(row)

    # H1-4: 질환을 단위로 복합 vs 국소 -- 순위합 검정 + 범주 라벨 순열
    h14 = {}
    cats = np.array([r["category"] for r in per])
    for key in zf:
        eff = np.array([r[key]["effect_sd"] for r in per])
        cx, fo = eff[cats == "complex"], eff[cats == "focal"]
        mw = stats.mannwhitneyu(cx, fo, alternative="two-sided")
        obs = cx.mean() - fo.mean()
        null = []
        for _ in range(20000):
            perm = RNG.permutation(cats)
            null.append(eff[perm == "complex"].mean() - eff[perm == "focal"].mean())
        null = np.array(null)
        h14[key] = {"complex_mean": float(cx.mean()), "focal_mean": float(fo.mean()), "mannwhitney_p": float(mw.pvalue), "perm_p": float((np.sum(np.abs(null) >= abs(obs)) + 1) / 20001)}
    ad = next(r for r in per if "Alzheimer" in r["name"])
    corr_sc_fc = stats.spearmanr([r["sc_degree"]["effect_sd"] for r in per], [r["fc_strength"]["effect_sd"] for r in per])
    print(json.dumps({"h1_4": h14, "h1_5_alzheimer": ad, "per_disorder": per, "disorder_level_spearman_scdeg_vs_fc": {"rho": float(corr_sc_fc.statistic), "p": float(corr_sc_fc.pvalue)}}, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    extra() if "--extra" in sys.argv else main()
