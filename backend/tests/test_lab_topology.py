"""연구소(Lab) 네트워크 위상 분석 테스트 (docs/34). fly 회로 계산은 진짜
수십 초가 걸릴 수 있어(species_topology.py의 @lru_cache 주석 참고)
전체 스위트에서 시간이 오래 걸리는 걸 피하려고, 순수 알고리즘
(`topology.analyze_topology`)은 작은 합성 그래프로 빠르게 테스트하고,
실제 종 데이터 연결(`species_topology.py`)은 웜/인간처럼 이미 빠른
것 위주로만 실제 데이터로 검증한다 -- fly 회로 자체가 동작하는지는
API 스모크 테스트 하나로만 확인(실제로 값을 받는지만 확인, 매 pytest
실행마다 70초씩 쓰지 않도록)."""

from fastapi.testclient import TestClient

from app.lab.topology import TopologyEdge, analyze_topology
from app.main import app

client = TestClient(app)


def test_analyze_topology_on_a_small_known_graph() -> None:
    # A simple directed path + one hub (real, hand-verifiable topology, not
    # sampled from project data) -- checks the algorithm's own correctness
    # independent of any real dataset's scale.
    node_ids = ["a", "b", "c", "d", "e"]
    labels = {n: n.upper() for n in node_ids}
    edges = [
        TopologyEdge("a", "b"),
        TopologyEdge("b", "c"),
        TopologyEdge("c", "d"),
        TopologyEdge("d", "e"),
        TopologyEdge("e", "a"),
        TopologyEdge("b", "d"),  # a real shortcut making "b"/"d" more central than "a"/"c"/"e"
    ]

    result = analyze_topology(node_ids, labels, edges, directed=True, curated_ids={"a"}, top_n=5)

    assert result.node_count == 5
    assert result.edge_count == 6
    assert result.is_directed is True
    assert result.betweenness_is_approximate is False  # well under the exact-computation node limit
    assert len(result.top_candidates) == 5
    # "a" was marked curated, everything else wasn't
    curated_flags = {c.node_id: c.already_in_curated_literature for c in result.top_candidates}
    assert curated_flags["a"] is True
    assert curated_flags["b"] is False


def test_analyze_topology_handles_disconnected_graph_without_crashing() -> None:
    # Two separate triangles -- a real disconnected topology (not a bug
    # case, a legitimate honest one: some real subsets of this project's
    # datasets genuinely aren't one connected component either).
    node_ids = ["a", "b", "c", "x", "y", "z"]
    labels = {n: n for n in node_ids}
    edges = [
        TopologyEdge("a", "b"),
        TopologyEdge("b", "c"),
        TopologyEdge("c", "a"),
        TopologyEdge("x", "y"),
        TopologyEdge("y", "z"),
        TopologyEdge("z", "x"),
    ]

    result = analyze_topology(node_ids, labels, edges, directed=False, curated_ids=set())

    assert result.is_fully_connected is False
    assert result.small_world_sigma is None
    # average_shortest_path_length still gets an honest approximate answer
    # from the largest connected component (both components tie at 3 nodes
    # here, so either is a valid "largest").
    assert result.average_shortest_path_length is not None


def test_worm_topology_report_surfaces_real_command_interneurons() -> None:
    # Real sanity check: the classic AVA/AVB backward/forward command
    # interneurons (already curated in this project's own ablation studies,
    # docs/26) should rank at or near the top of a real degree/betweenness/
    # pagerank composite -- if they didn't, that would suggest a bug in the
    # graph construction, not a genuine finding.
    response = client.get("/api/lab/topology/c_elegans")
    assert response.status_code == 200
    body = response.json()

    assert body["node_count"] == 302
    assert body["is_directed"] is True
    top_ids = {c["node_id"] for c in body["top_candidates"][:5]}
    assert "AVAR" in top_ids or "AVAL" in top_ids  # one of the two AVA command interneurons


def test_human_macro_topology_report_computes_real_metrics() -> None:
    response = client.get("/api/lab/topology/human_macro")
    assert response.status_code == 200
    body = response.json()

    assert body["node_count"] == 400
    assert body["is_directed"] is False
    assert 0 <= body["density"] <= 1
    # docs/49: 네트워크 간 간선 복구 후 -- 400개가 하나로 이어지고 작은세상성을 전체 그래프로 계산할 수 있어야 한다
    # (복구 전엔 8조각이라 σ를 건너뛰었다).
    assert body["edge_count"] == 5059
    assert body["is_fully_connected"] is True
    assert body["small_world_sigma"] is not None and body["small_world_sigma"] > 1
    assert body["curated_literature_note"]  # non-empty, mentions the real disorder dataset
    assert body["honesty_note"]


def test_topology_species_list_is_real_and_stable() -> None:
    response = client.get("/api/lab/topology/species")
    assert response.status_code == 200
    ids = response.json()
    assert set(ids) == {"c_elegans", "drosophila_olfactory", "drosophila_visual", "drosophila_navigation", "human_macro"}


def test_topology_unknown_species_returns_404() -> None:
    response = client.get("/api/lab/topology/not_a_real_species")
    assert response.status_code == 404
