"""손상 전(병전) 부하 지도를 '환자 자신의 손상 후 연결망 + 참조 코호트'로 추정하기 -- 사전 검증(docs/59, H17-13).

배경(docs/53 H17-6): 재조직 길잡이로 환자 자신의 병전 지도(오라클)를 쓰면 집단 합의 지도보다 연쇄 생존이 +0.04~0.06 높았다.
개인 평균 μ나 Z는 오히려 합의보다 못했다. 그러나 실제 환자의 병전 지도는 볼 수 없다. 볼 수 있는 것은
  (1) 손상 후 촬영한 환자 자신의 연결망(병변에 닿는 연결은 사라짐, 촬영 잡음 포함)과
  (2) 건강인 참조 코호트뿐이다.
질문: 이 두 가지로 병전 지도를 추정하면 오라클 이득의 몇 %를 되찾는가.

추정기(모두 병변 밖 영역의 병전 부하를 추정한다)
  consensus      참조 코호트의 다수결 합의 지도(지금 방식)
  mu             참조 코호트 개인 부하의 평균(docs/53에서 합의보다 못했음, 비교용)
  post_lesion    환자의 손상 후 연결망에서 바로 잰 부하(이미 우회 부하가 섞인 '현재' 지도, 함정 비교용)
  impute_all     환자의 손상 후 연결망 + 병변에 닿는 연결만 참조 코호트 빈도로 채워 넣은 뒤 잰 부하
  impute_knn     위와 같되, 병변 밖 연결이 환자와 가장 비슷한 참조 k명의 빈도로 채움
  knn_mean       병변 밖 연결이 가장 비슷한 참조 k명 부하의 평균
  impute_clean   impute_all과 같되 촬영 잡음이 없는 손상 후 연결망을 쓴 것(잡음의 몫을 가르는 진단용)
  impute_eps2    촬영 잡음을 5% 대신 2%로(잡음 크기 민감도)
  impute_2scan   독립 촬영 2번(각 5% 잡음)으로 각각 impute_all을 만든 뒤 부하 평균
  impute_shrink  impute_all과 consensus의 log(부하+1) 평균(집단 지도 쪽으로 당기기)
  (허용 배수를 바꾸는 비교군은 뺐다: 길잡이는 비율 최소 후보를 고르는 정렬 키라 배수를 일괄로 곱해도 순서가 거의 그대로다)
  oracle         환자의 실제 병전 지도(상한)
  distributed    균등 분산(기준선, 지도를 쓰지 않음)

평가
  정확도  병변 밖 영역에서 추정 vs 실제 병전 부하: Spearman, 상위 5% 허브 일치율, |log 비율| 중앙값
  쓸모    추정 지도 × 1.2를 허용선으로 한 재조직(docs/53과 같은 reorganize_key) 후,
          '환자 자신의 병전 부하 × m'을 문턱으로 한 연쇄 생존(m=1.2, 1.0)과 전역 효율

코호트
  합성(기본): docs/53의 생성 가정 G1(약한 연결 위주 변동, 길이 분포 보존)으로 v=0.1/0.2/0.3.
             환자 = 앞의 N_PAT명, 참조 = 나머지 전원(한 명씩 빼기). 환자 촬영에는 잡음 ε=5%(G2)를 넣는다.
  실제:      환경변수 MICA_DIR에 개인별 Schaefer-400 구조 연결 행렬 파일이 있으면 그것으로 같은 계산을 한다
             (load_real_cohort 참조). 병변·거리 행렬은 Liu 2023 Schaefer-400(7 네트워크 순서)의 것을 쓰므로,
             실제 데이터의 영역 순서가 같은지 받은 뒤 반드시 확인한다.

정직성: 합성 개인은 하나의 합의에서 독립적으로 흔든 것이라 '비슷한 사람끼리 묶이는 구조'가 없다.
그래서 합성에서 kNN 계열이 이점이 없다고 실제에서도 없다는 뜻은 아니다. 또 실제 손상 후에는 병변에 닿지 않는
연결도 2차 변성(왈러 변성, 원격 기능 저하)으로 바뀔 수 있는데 여기서는 촬영 잡음 5%만 넣었다.

실행 전 예측
  P1 impute_all은 병변 밖 연결이 대부분 보이므로 정확도가 consensus·mu보다 훨씬 높다(Spearman 0.9 이상).
  P2 post_lesion은 순위는 잘 맞지만 우회 부하 때문에 병변 주변을 과대 추정해, 길잡이로는 오라클보다 확실히 못하다.
  P3 impute_all은 오라클 이득(oracle − consensus)의 70% 이상을 되찾는다.
  P4 합성 코호트에서는 impute_knn ≈ impute_all, knn_mean ≈ mu(구조가 없으므로).

실행: REORG_CACHE=... REORG_PROCS=3 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.premorbid_map_estimation > out.json
실제: MICA_DIR=... (위와 같음)
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
from scripts.synthetic_individual_cohort import EPS, IU, LESION_IDX, Base, individual, perturb, reorganize_key, to_adj

N_PAT = 8
N_REF = 33
K_NN = 5
V_LIST = [0.1, 0.2, 0.3]
M_LIST = (1.2, 1.0)
ESTIMATORS = ("consensus", "mu", "post_lesion", "impute_all", "impute_knn", "knn_mean",
              "impute_clean", "impute_eps2", "impute_2scan", "impute_shrink", "oracle")
EPS_LOW = 0.02
GUIDES = ESTIMATORS + ("distributed",)


# ---------- 실제 코호트 읽기 ----------

def _read_matrix(path: Path) -> np.ndarray:
    s = path.name.lower()
    if s.endswith(".npy"):
        return np.load(path)
    if s.endswith(".gii"):
        import nibabel as nib

        return np.asarray(nib.load(str(path)).darrays[0].data, dtype=float)
    txt = path.read_text(encoding="utf-8", errors="replace")
    delim = "," if txt.count(",") > txt.count("\n") else None
    return np.loadtxt(path, delimiter=delim)


def load_real_cohort(root: str, n_edges: int) -> tuple[list[str], list[np.ndarray]]:
    """MICA_DIR 아래의 개인별 Schaefer-400 구조 연결 행렬을 읽어, 각자 가중치 상위 n_edges개로 이진화한다.

    파일 이름에 'schaefer'와 '400'이 들어 있고 'length'·'fc'가 없는 행렬을 피험자 폴더(sub-*)별로 1개씩 고른다
    (같은 사람에 세션이 여럿이면 이름순 첫 번째). 행렬이 400보다 크면(피질하·소뇌 포함) MICA_OFFSET으로
    피질 400 블록의 시작 위치를 지정해야 한다 -- 데이터를 받은 뒤 확인해서 정한다.
    상삼각만 채워진 행렬은 대칭으로 만든다.
    """
    files = sorted(
        p for p in Path(root).rglob("*")
        if p.is_file() and "schaefer" in p.name.lower() and "400" in p.name
        and not any(k in p.name.lower() for k in ("length", "_fc", "func"))
        and p.suffix.lower() in (".txt", ".csv", ".npy", ".gii")
    )
    by_sub: dict[str, Path] = {}
    for p in files:
        sub = next((part for part in p.parts if part.startswith("sub-")), p.stem)
        by_sub.setdefault(sub, p)
    if not by_sub:
        raise SystemExit(f"MICA_DIR={root}: Schaefer-400 연결 행렬 파일을 찾지 못했다")
    off = os.environ.get("MICA_OFFSET")
    names, vecs = [], []
    for sub, p in sorted(by_sub.items()):
        m = _read_matrix(p)
        if m.shape[0] != m.shape[1]:
            raise SystemExit(f"{p}: 정사각 행렬이 아니다 {m.shape}")
        if m.shape[0] != N:
            if off is None:
                raise SystemExit(f"{p}: 크기 {m.shape} -- 피질 400 블록 시작 위치를 MICA_OFFSET으로 지정해야 한다")
            o = int(off)
            m = m[o:o + N, o:o + N]
        m = np.nan_to_num(np.asarray(m, float))
        if np.allclose(np.tril(m, -1), 0) or np.allclose(np.triu(m, 1), 0):
            m = m + m.T
        np.fill_diagonal(m, 0)
        w = m[IU]
        vec = np.zeros(len(w), dtype=bool)
        vec[np.argsort(-w, kind="stable")[:n_edges]] = True
        vec &= w > 0
        names.append(sub)
        vecs.append(vec)
    return names, vecs


# ---------- 추정기 ----------

def majority(vecs: np.ndarray, n_edges: int, dist_u: np.ndarray) -> np.ndarray:
    freq = vecs.mean(0)
    out = np.zeros(vecs.shape[1], dtype=bool)
    out[np.argsort(-freq + 1e-9 * dist_u, kind="stable")[:n_edges]] = True
    return out


def impute(obs: np.ndarray, touch: np.ndarray, freq: np.ndarray, dist_u: np.ndarray) -> np.ndarray:
    """병변에 닿는 쌍만 참조 빈도로 채운다. 채울 개수 = 그 쌍들의 기대 연결 수(빈도 합)."""
    out = obs.copy()
    out[touch] = False
    idx = np.flatnonzero(touch)
    k = int(round(freq[idx].sum()))
    if k:
        order = np.lexsort((dist_u[idx], -freq[idx]))
        out[idx[order[:k]]] = True
    return out


def estimate_maps(obs: np.ndarray, clean: np.ndarray, obs_low: np.ndarray, obs2: np.ndarray, les_mask: np.ndarray, ref: np.ndarray, ref_L: np.ndarray, n_edges: int,
                  dist_u: np.ndarray, L_true: np.ndarray) -> dict[str, np.ndarray]:
    alive_all = np.ones(N, dtype=bool)
    touch = les_mask[IU[0]] | les_mask[IU[1]]
    keep = ~touch
    # 병변 밖 연결로 본 유사도(Jaccard)
    a = obs[keep]
    inter = (ref[:, keep] & a).sum(1)
    union = (ref[:, keep] | a).sum(1)
    nn = np.argsort(-(inter / np.maximum(union, 1)), kind="stable")[:K_NN]
    post = obs.copy()
    post[touch] = False
    fr = ref.mean(0)
    imp = btw_array(to_adj(impute(obs, touch, fr, dist_u)), alive_all)
    cons = btw_array(to_adj(majority(ref, n_edges, dist_u)), alive_all)
    return {
        "consensus": cons,
        "mu": ref_L.mean(0),
        "post_lesion": btw_array(to_adj(post), ~les_mask),
        "impute_all": imp,
        "impute_knn": btw_array(to_adj(impute(obs, touch, ref[nn].mean(0), dist_u)), alive_all),
        "knn_mean": ref_L[nn].mean(0),
        "impute_clean": btw_array(to_adj(impute(clean, touch, fr, dist_u)), alive_all),
        "impute_eps2": btw_array(to_adj(impute(obs_low, touch, fr, dist_u)), alive_all),
        "impute_2scan": (imp + btw_array(to_adj(impute(obs2, touch, fr, dist_u)), alive_all)) / 2,
        "impute_shrink": np.expm1((np.log1p(imp) + np.log1p(cons)) / 2),
        "oracle": L_true,
    }


def accuracy(est: np.ndarray, true: np.ndarray, surv: np.ndarray) -> dict:
    e, t = est[surv], true[surv]
    k = max(1, int(round(0.05 * len(t))))
    top_e, top_t = set(np.argsort(-e)[:k]), set(np.argsort(-t)[:k])
    return {"spearman": float(stats.spearmanr(e, t)[0]), "hub_overlap": len(top_e & top_t) / k,
            "median_abs_log_ratio": float(np.median(np.abs(np.log((e + 1) / (t + 1)))))}


# ---------- 한 단위(코호트 v 또는 실제, 환자 1명) ----------

def _cohort(src: str, base: Base) -> tuple[np.ndarray, int]:
    n_edges = int(base.cons[IU].sum())
    if src == "real":
        _, vecs = load_real_cohort(os.environ["MICA_DIR"], n_edges)
        return np.array(vecs), n_edges
    v = float(src)
    rng = np.random.default_rng(int(v * 1000) + 59)
    return np.array([individual(base, v, rng) for _ in range(N_PAT + N_REF)]), n_edges


def run_unit(args: tuple[str, int]) -> dict:
    src, pi = args
    d = os.environ.get("REORG_CACHE")
    p = Path(d) / f"premorbid59b_{src}_p{pi}.json" if d else None
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    base = Base()
    subs, n_edges = _cohort(src, base)
    dist_u = base.dist[IU]
    alive = np.ones(N, dtype=bool)
    ref_idx = [i for i in range(len(subs)) if i != pi]
    ref = subs[ref_idx]
    ref_L = np.array([btw_array(to_adj(s), alive) for s in ref])
    pv = subs[pi]
    pad = to_adj(pv)
    L_true = btw_array(pad, alive)
    obs_rng = np.random.default_rng(1000 + pi)
    rows = []
    for li in LESION_IDX:
        les = sorted(base.lesions[li]["nodes"])
        les_mask = np.zeros(N, dtype=bool)
        les_mask[les] = True
        surv = ~les_mask
        obs = perturb(base, pv, EPS, obs_rng)  # 손상 후 촬영 = 병전 연결 + 촬영 잡음, 병변 연결은 추정기에서 지운다
        obs_low = perturb(base, pv, EPS_LOW, obs_rng)
        obs2 = perturb(base, pv, EPS, obs_rng)
        maps = estimate_maps(obs, pv, obs_low, obs2, les_mask, ref, ref_L, n_edges, dist_u, L_true)
        adj = pad.copy()
        adj[les, :] = False
        adj[:, les] = False
        lost: dict = {}
        for a in les:
            for b in np.flatnonzero(pad[a]):
                if not les_mask[b]:
                    lost[int(b)] = lost.get(int(b), 0) + 1
        for g in GUIDES:
            if g == "distributed":
                key = lambda b, c: b[c] + 1e-6 * c
            else:
                est = maps[g]
                key = lambda b, c, est=est: (b[c] + 1) / (1.2 * est[c] + 1)
            ar = reorganize_key(adj, surv, lost, base.dist, base.lmax, key, random.Random(pi * 100 + li))
            row = {"patient": pi, "lesion": li, "guide": g, "global_eff": global_eff(ar, surv)}
            for m in M_LIST:
                row[f"casc_m{m}"] = cascade(ar, surv, m * L_true)
            if g in maps:
                row.update(accuracy(maps[g], L_true, surv))
            rows.append(row)
    print(f"{src} patient {pi} done", file=sys.stderr, flush=True)
    out = {"src": src, "patient": pi, "rows": rows}
    if p:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(p)
    return out


def summarize(rows: list[dict]) -> dict:
    out: dict = {"by_guide": {}, "paired": {}}
    for g in GUIDES:
        rs = [r for r in rows if r["guide"] == g]
        keys = [k for k in rs[0] if k not in ("patient", "lesion", "guide")]
        out["by_guide"][g] = {k: float(np.mean([r[k] for r in rs])) for k in keys}
    for m in M_LIST:
        k = f"casc_m{m}"
        get = lambda g: np.array([r[k] for r in rows if r["guide"] == g])
        oracle, cons = get("oracle"), get("consensus")
        gap = float((oracle - cons).mean())
        for g in GUIDES:
            x = get(g)
            out["paired"].setdefault(g, {})[k] = {
                "minus_consensus": float((x - cons).mean()),
                "minus_oracle": float((x - oracle).mean()),
                "gain_recovered": float((x - cons).mean() / gap) if abs(gap) > 1e-9 else None,
                "p_vs_consensus": float(stats.wilcoxon(x, cons).pvalue) if np.any(x != cons) else 1.0,
                "n": len(x),
            }
    return out


def main() -> None:
    srcs = ["real"] if os.environ.get("MICA_DIR") else [str(v) for v in V_LIST]
    if srcs == ["real"]:
        n_sub = len(load_real_cohort(os.environ["MICA_DIR"], int(Base().cons[IU].sum()))[0])
        units = [("real", i) for i in range(n_sub)]
    else:
        units = [(s, i) for s in srcs for i in range(N_PAT)]
    with Pool(int(os.environ.get("REORG_PROCS", "2"))) as pool:
        res = pool.map(run_unit, units, chunksize=1)
    out = {}
    for s in srcs:
        out[s] = summarize([r for u in res if u["src"] == s for r in u["rows"]])
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
