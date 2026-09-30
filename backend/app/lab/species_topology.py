"""종별 위상 분석 리포트 조립 (docs/34). `topology.py`의 순수 그래프 알고리즘을
각 종의 실제 데이터셋(worm 전체 신경계, fly 3개 회로, human 거시 구조연결)에
연결한다. 계산 비용이 실제로 큰 그래프(특히 fly 회로, 최대 3천 개 노드·14만
개 시냅스)가 있어 프로세스 생애주기당 한 번만 계산하도록 `@lru_cache`를
쓴다 -- 데이터 자체가 서버 실행 중 바뀌지 않으므로 안전하다."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, get_args

from app.data.celegans_connectome import get_classic_ablations, get_connectome as get_worm_connectome
from app.data.drosophila_connectome import get_connectome_for_circuit
from app.data.human_data import get_macro_connectome
from app.domain.schemas import CircuitName
from app.lab.schemas import CentralityEntryOut, TopologyReportOut
from app.lab.topology import TopologyEdge, analyze_topology

SpeciesId = Literal["c_elegans", "drosophila_olfactory", "drosophila_visual", "drosophila_navigation", "human_macro"]

_HONESTY_NOTE = (
    "이 보고서의 모든 숫자는 이 프로젝트가 실제로 가진 데이터로부터 계산한 진짜 값이다. 하지만 "
    "\"위상적으로 중심적이다\"는 \"생물학적으로 중요하다\"는 뜻이 아니고, \"이 프로젝트의 큐레이션 데이터에 "
    "없다\"는 것도 \"실제 문헌에 없다\"는 뜻이 아니다 -- 이건 가설을 만들어보는 도구지, 발견을 주장하는 도구가 "
    "아니다. 개인 로컬 탐구용, 배포 대상 아님."
)


def _worm_report() -> TopologyReportOut:
    connectome = get_worm_connectome()
    neuron_ids = {n.id for n in connectome.neurons}
    labels = {n.id: n.name for n in connectome.neurons}
    edges = [TopologyEdge(s.pre, s.post, s.weight) for s in connectome.synapses if s.pre in neuron_ids and s.post in neuron_ids]
    curated_ids: set[str] = set()
    for ablation in get_classic_ablations():
        curated_ids.update(ablation.neuron_ids)

    result = analyze_topology(list(neuron_ids), labels, edges, directed=True, curated_ids=curated_ids, top_n=15)
    return _to_out(
        result,
        species_id="c_elegans",
        label_ko="예쁜꼬마선충 — 전체 신경계",
        curated_literature_note=f"이 프로젝트가 큐레이션한 고전 레이저 절제 연구({len(curated_ids)}개 실제 뉴런)에 등장하는지.",
    )


def _fly_report(circuit: CircuitName) -> TopologyReportOut:
    connectome = get_connectome_for_circuit(circuit)
    neuron_ids = {n.id for n in connectome.neurons}
    labels = {n.id: n.name for n in connectome.neurons}
    edges = [TopologyEdge(s.pre, s.post, s.weight) for s in connectome.synapses if s.pre in neuron_ids and s.post in neuron_ids]

    circuit_label = {"olfactory": "후각", "visual": "시각", "navigation": "항법"}[circuit]
    result = analyze_topology(list(neuron_ids), labels, edges, directed=True, curated_ids=set(), top_n=15)
    return _to_out(
        result,
        species_id=f"drosophila_{circuit}",
        label_ko=f"초파리 — {circuit_label} 회로",
        curated_literature_note="이 프로젝트는 초파리 회로에 대한 고전 문헌 큐레이션 데이터셋을 아직 갖고 있지 않음 -- 전부 false로 표시됨(실제로 없어서가 아니라, 이 프로젝트가 아직 안 만들어서).",
    )


def _human_report() -> TopologyReportOut:
    macro = get_macro_connectome()
    node_ids = [r.id for r in macro.regions]
    labels = {r.id: (r.anatomical_label or r.name) for r in macro.regions}
    edges = [TopologyEdge(e.a, e.b, e.weight) for e in macro.edges]
    curated_ids: set[str] = set()
    for disorder in macro.known_disorders:
        curated_ids.update(disorder.region_ids)

    result = analyze_topology(node_ids, labels, edges, directed=False, curated_ids=curated_ids, top_n=15)
    return _to_out(
        result,
        species_id="human_macro",
        label_ko="인간 — 거시 구조연결(Schaefer-400)",
        curated_literature_note=f"이 프로젝트가 큐레이션한 실제 질환-영역 연관({len(curated_ids)}개 실제 영역)에 등장하는지.",
    )


def _to_out(result, *, species_id: str, label_ko: str, curated_literature_note: str) -> TopologyReportOut:
    return TopologyReportOut(
        species_id=species_id,
        label_ko=label_ko,
        node_count=result.node_count,
        edge_count=result.edge_count,
        is_directed=result.is_directed,
        density=result.density,
        average_clustering=result.average_clustering,
        average_shortest_path_length=result.average_shortest_path_length,
        small_world_sigma=result.small_world_sigma,
        small_world_skipped_reason=result.small_world_skipped_reason,
        betweenness_is_approximate=result.betweenness_is_approximate,
        is_fully_connected=result.is_fully_connected,
        modularity_q=result.modularity_q,
        community_sizes=result.community_sizes,
        top_candidates=[
            CentralityEntryOut(
                node_id=c.node_id,
                node_label=c.node_label,
                degree_centrality=c.degree_centrality,
                betweenness_centrality=c.betweenness_centrality,
                pagerank=c.pagerank,
                combined_score=c.combined_score,
                already_in_curated_literature=c.already_in_curated_literature,
            )
            for c in result.top_candidates
        ],
        curated_literature_note=curated_literature_note,
        honesty_note=_HONESTY_NOTE,
    )


_BUILDERS = {
    "c_elegans": _worm_report,
    "drosophila_olfactory": lambda: _fly_report("olfactory"),
    "drosophila_visual": lambda: _fly_report("visual"),
    "drosophila_navigation": lambda: _fly_report("navigation"),
    "human_macro": _human_report,
}


@lru_cache
def get_topology_report(species_id: SpeciesId) -> TopologyReportOut:
    """Cached per species_id -- some of these (esp. fly circuits, up to
    ~3,000 neurons/140,000 synapses) take real tens-of-seconds to compute,
    so this must only ever run once per server process, not per request."""
    return _BUILDERS[species_id]()


def list_species_ids() -> list[str]:
    return list(get_args(SpeciesId))
