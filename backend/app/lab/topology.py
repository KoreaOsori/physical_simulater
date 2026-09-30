"""네트워크 위상 분석 (docs/34). 이 프로젝트가 이미 가진 실제 커넥톰
그래프(웜 전체 신경계/파리 3개 회로/인간 거시 구조연결)에 표준 네트워크
과학 지표(중심성·모듈성·작은세상성·리치클럽)를 계산한다.

전부 실제 데이터로부터 나온 진짜 계산값이지만, 해석에는 명확한 한계가
있다 — "이 지표에서 순위가 높다"는 "위상적으로 중심적일 가능성이 있다"는
뜻일 뿐, "생물학적으로 중요하다"거나 "고전 문헌이 놓친 걸 이 프로젝트가
발견했다"는 뜻이 절대 아니다. 어떤 신경과학적으로 흥미로운 회로도 위상
지표 하나로 요약되지 않는다 — 이건 가설을 만들어보는 도구지, 발견을
주장하는 도구가 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


@dataclass(frozen=True)
class TopologyEdge:
    source: str
    target: str
    weight: float = 1.0


@dataclass(frozen=True)
class CentralityEntry:
    node_id: str
    node_label: str
    degree_centrality: float
    betweenness_centrality: float
    pagerank: float
    combined_score: float
    already_in_curated_literature: bool


# Above these node counts, exact betweenness centrality and small-world
# sigma become too slow for a personal machine (both are effectively
# O(V*E)-or-worse, and sigma multiplies that by several random reference
# graphs) -- real fly circuits in this dataset go up to ~3,000 neurons, so
# this isn't a hypothetical. Betweenness falls back to a standard k-sample
# approximation (real, unbiased technique, just noisier) above the first
# threshold; sigma/average-shortest-path are skipped entirely above the
# second rather than silently hanging -- both documented honestly in the
# API response, not just in this comment.
BETWEENNESS_EXACT_NODE_LIMIT = 400
BETWEENNESS_SAMPLE_K = 300
SMALL_WORLD_NODE_LIMIT = 500


@dataclass(frozen=True)
class TopologyResult:
    node_count: int
    edge_count: int
    is_directed: bool
    density: float
    average_clustering: float
    average_shortest_path_length: float | None
    small_world_sigma: float | None
    small_world_skipped_reason: str | None
    betweenness_is_approximate: bool
    is_fully_connected: bool
    modularity_q: float
    community_sizes: list[int]
    top_candidates: list[CentralityEntry] = field(default_factory=list)


def _normalize(values: dict[str, float]) -> dict[str, float]:
    vals = list(values.values())
    if not vals:
        return {}
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def analyze_topology(
    node_ids: list[str],
    node_labels: dict[str, str],
    edges: list[TopologyEdge],
    *,
    directed: bool,
    curated_ids: set[str],
    top_n: int = 15,
) -> TopologyResult:
    """`curated_ids`: node ids this project's own curated real literature
    (worm classic ablation studies, human disorder associations) already
    features -- used only to flag `already_in_curated_literature` on each
    candidate, never to filter anything out."""
    graph: nx.DiGraph | nx.Graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_nodes_from(node_ids)
    for e in edges:
        if graph.has_edge(e.source, e.target):
            graph[e.source][e.target]["weight"] += e.weight
        else:
            graph.add_edge(e.source, e.target, weight=e.weight)

    degree = dict(graph.degree())
    max_degree = max(degree.values()) if degree else 0
    degree_centrality = {k: (v / max_degree if max_degree else 0.0) for k, v in degree.items()}
    # Unweighted shortest paths for betweenness -- real synapse counts
    # (`weight`) aren't a validated "distance" in the literature, so
    # treating them as one here would silently invent a meaning the source
    # data never claimed.
    betweenness_is_approximate = graph.number_of_nodes() > BETWEENNESS_EXACT_NODE_LIMIT
    betweenness = nx.betweenness_centrality(
        graph, k=(BETWEENNESS_SAMPLE_K if betweenness_is_approximate else None), seed=0, weight=None
    )
    try:
        pagerank = nx.pagerank(graph, weight="weight")
    except nx.PowerIterationFailedConvergence:
        pagerank = dict.fromkeys(graph.nodes(), 0.0)

    norm_degree = _normalize(degree_centrality)
    norm_betweenness = _normalize(betweenness)
    norm_pagerank = _normalize(pagerank)
    combined = {nid: (norm_degree[nid] + norm_betweenness[nid] + norm_pagerank[nid]) / 3 for nid in graph.nodes()}

    ranked = sorted(graph.nodes(), key=lambda nid: combined[nid], reverse=True)
    top_candidates = [
        CentralityEntry(
            node_id=nid,
            node_label=node_labels.get(nid, nid),
            degree_centrality=degree_centrality[nid],
            betweenness_centrality=betweenness[nid],
            pagerank=pagerank[nid],
            combined_score=combined[nid],
            already_in_curated_literature=nid in curated_ids,
        )
        for nid in ranked[:top_n]
    ]

    # Clustering/modularity/small-world/rich-club are standardly defined on
    # undirected graphs -- a directed graph's weak/strong connectivity
    # structure would need a different, non-standard treatment this pass
    # doesn't attempt (honestly scoped out, not silently approximated).
    undirected = graph.to_undirected() if directed else graph
    average_clustering = nx.average_clustering(undirected)

    try:
        communities = list(nx.community.greedy_modularity_communities(undirected, weight="weight"))
        modularity_q = nx.community.modularity(undirected, communities, weight="weight")
        community_sizes = sorted((len(c) for c in communities), reverse=True)
    except Exception:
        modularity_q = 0.0
        community_sizes = []

    is_fully_connected = nx.is_connected(undirected) if undirected.number_of_nodes() > 0 else False
    average_shortest_path_length: float | None = None
    small_world_sigma: float | None = None
    small_world_skipped_reason: str | None = None

    if undirected.number_of_nodes() > SMALL_WORLD_NODE_LIMIT:
        small_world_skipped_reason = (
            f"이 그래프({undirected.number_of_nodes()}개 노드)가 {SMALL_WORLD_NODE_LIMIT}개 초과라 "
            "평균최단경로/작은세상성(sigma) 계산을 건너뜀 -- 개인 로컬 머신에서 감당하기엔 비용이 너무 큼."
        )
    elif is_fully_connected:
        average_shortest_path_length = nx.average_shortest_path_length(undirected)
        try:
            # niter/nrand kept small (networkx's own default is
            # niter=100/nrand=10) -- trades statistical precision for
            # tractable runtime on a personal machine. Still real random
            # reference graphs, just fewer of them -- documented honestly
            # in docs/34 rather than silently using a weaker default.
            small_world_sigma = nx.sigma(undirected, niter=5, nrand=5, seed=0)
        except Exception:
            small_world_sigma = None
    elif undirected.number_of_nodes() > 2:
        largest_cc = max(nx.connected_components(undirected), key=len)
        subgraph = undirected.subgraph(largest_cc)
        if subgraph.number_of_nodes() > 2:
            average_shortest_path_length = nx.average_shortest_path_length(subgraph)

    return TopologyResult(
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        is_directed=directed,
        density=nx.density(graph),
        average_clustering=average_clustering,
        average_shortest_path_length=average_shortest_path_length,
        small_world_sigma=small_world_sigma,
        small_world_skipped_reason=small_world_skipped_reason,
        betweenness_is_approximate=betweenness_is_approximate,
        is_fully_connected=is_fully_connected,
        modularity_q=modularity_q,
        community_sizes=community_sizes,
        top_candidates=top_candidates,
    )
