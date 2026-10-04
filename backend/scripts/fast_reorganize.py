"""reorganization_hypotheses.reorganize()의 빠른 동치 구현(docs/52).

원래 구현은 후보 목록과 정렬 키를 순수 Python으로 매번 만든다(병변 하나·전략 하나에 4~8초). 귀무 연결망 수백 개 실험에는
너무 느려서 numpy 인접 행렬로 다시 썼다. **같은 시드면 같은 연결을 고른다**: 후보 순서(영역 번호 오름차순), 동점 처리용
rng.random() 호출 순서·횟수, random 전략의 rng.choice까지 원래와 같게 맞췄고 `verify()`로 간선 집합이 완전히 같음을 확인한다.
매개 중심성은 rustworkx 다중 스레드(프로세스를 늘리지 않아 메모리가 적게 든다).

실행(검증): PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.fast_reorganize
"""

from __future__ import annotations

import random

import networkx as nx
import numpy as np
import rustworkx as rx

N = 400


def btw_array(adj: np.ndarray, alive: np.ndarray) -> np.ndarray:
    """살아 있는 영역만의 매개 중심성(비정규화). 죽은 영역은 0."""
    nodes = np.flatnonzero(alive)
    idx = -np.ones(N, dtype=int)
    idx[nodes] = np.arange(len(nodes))
    sub = adj[np.ix_(nodes, nodes)]
    a, b = np.nonzero(np.triu(sub, 1))
    r = rx.PyGraph()
    r.add_nodes_from(range(len(nodes)))
    r.add_edges_from_no_data(list(zip(a.tolist(), b.tolist())))
    bc = rx.graph_betweenness_centrality(r, normalized=False)
    out = np.zeros(N)
    for i, v in bc.items():
        out[nodes[i]] = v
    return out


def to_adj(g: nx.Graph) -> tuple[np.ndarray, np.ndarray]:
    adj = np.zeros((N, N), dtype=bool)
    for a, b in g.edges:
        adj[a, b] = adj[b, a] = True
    alive = np.zeros(N, dtype=bool)
    alive[list(g.nodes)] = True
    return adj, alive


def to_graph(adj: np.ndarray, alive: np.ndarray) -> nx.Graph:
    g = nx.Graph()
    g.add_nodes_from(np.flatnonzero(alive).tolist())
    a, b = np.nonzero(np.triu(adj, 1))
    g.add_edges_from(zip(a.tolist(), b.tolist()))
    return g


def reorganize_fast(adj0: np.ndarray, alive: np.ndarray, lost: dict, dist: np.ndarray, lmax: float, strategy: str,
                    rng: random.Random, capacity: np.ndarray | None = None) -> np.ndarray:
    """원래 reorganize()와 같은 규칙. 반환: 재조직 후 인접 행렬(죽은 영역 행·열은 False)."""
    adj = adj0.copy()
    if strategy == "none":
        return adj
    queue = [n for n, k in lost.items() for _ in range(k)]
    rng.shuffle(queue)
    near = dist <= lmax
    btw = btw_array(adj, alive) if strategy in ("distributed", "headroom") else None
    added = 0
    for n in queue:
        mask = alive & ~adj[n] & near[n]
        mask[n] = False
        cands = np.flatnonzero(mask)
        if len(cands) == 0:
            continue
        if strategy == "random":
            t = rng.choice(cands.tolist())
        else:
            r = np.array([rng.random() for _ in range(len(cands))])
            if strategy == "local":
                keys = (dist[n, cands],)
            elif strategy == "concentrated":
                keys = (-adj[cands].sum(1).astype(float),)
            elif strategy == "headroom":
                keys = ((btw[cands] + 1.0) / (capacity[cands] + 1.0),)
            else:  # distributed
                keys = (btw[cands], adj[cands].sum(1).astype(float))
            # 원래의 min/max(key=(..., rng.random())) 와 같은 사전식 선택. concentrated는 max -> 부호 반전 + r도 최대.
            if strategy == "concentrated":
                order = np.lexsort((-r, *keys[::-1]))
            else:
                order = np.lexsort((r, *keys[::-1]))
            t = int(cands[order[0]])
        adj[n, t] = adj[t, n] = True
        added += 1
        if strategy in ("distributed", "headroom") and added % 10 == 0:
            btw = btw_array(adj, alive)
    return adj


def verify() -> None:
    import scripts.short_long_term_reorganization as sl  # noqa: F401  (rh.betweenness를 rustworkx로 교체 -- 값 동일)
    from scripts.reorganization_hypotheses import load, reorganize

    g, dist, _, lesions = load()
    lmax = float(np.percentile([dist[a, b] for a, b in g.edges], 75))
    adj_full, _ = to_adj(g)
    L0 = btw_array(adj_full, np.ones(N, dtype=bool))
    cap = 1.2 * L0
    cap_d = {i: float(cap[i]) for i in range(N)}
    bad = 0
    for li in (0, 7, 13, 24):
        les = set(lesions[li]["nodes"])
        lost: dict = {}
        for a in les:
            for b in g.neighbors(a):
                if b not in les:
                    lost[b] = lost.get(b, 0) + 1
        gl = g.copy()
        gl.remove_nodes_from(les)
        adj, alive = to_adj(gl)
        for s in ["random", "local", "concentrated", "distributed", "headroom"]:
            ref = reorganize(gl, lost, dist, lmax, s, random.Random(li * 1000), cap_d)
            fast = to_graph(reorganize_fast(adj, alive, lost, dist, lmax, s, random.Random(li * 1000), cap), alive)
            same = {tuple(sorted(e)) for e in ref.edges} == {tuple(sorted(e)) for e in fast.edges}
            bad += not same
            print(f"lesion {li} {s:13s} same_edges={same}")
    print("ALL IDENTICAL" if bad == 0 else f"MISMATCH {bad}")


if __name__ == "__main__":
    verify()
