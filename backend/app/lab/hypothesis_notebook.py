"""가설 노트 (docs/39-40). 연구소(Lab)의 4개 도구(위상 분석/가상 실험실/
탐구형 챗봇/유전자 후보)를 실제로 사용해 세운 가설 6개와 그 실제 검증
기록. "이 기능에 이 부분이 활용된다면 이렇게 되지 않을까"라는 구조로
가설을 세우고, 실제로 도구를 돌려서 나온 진짜 결과로 검증했다 —
가설이 지지됐든 기각됐든(H1, H6의 인간 부분처럼) 정직하게 기록한다.

H1(다중 질환 영역-위상 중심성 상관)만 매 요청마다 실시간 재계산되는
진짜 라이브 계산이다 -- 인간 거시 데이터(400개 노드)라 비용이
거의 없어서 캐시 없이 매번 다시 돌려도 무리 없다. H2~H6는 실제 Brian2
시뮬레이션·실제 OpenAI 웹 검색·실제 대형 그래프 계산(H5의 종간 σ 비교는
파리 항법 회로 하나만 173초 걸림)을 이 세션에서 실제로 1회 수행해 나온
결과를 그대로 기록했다 -- 페이지를 열 때마다 다시 돈 걸리는 계산/과금을
반복하지 않기 위해 정적으로 저장했고, 각 기록에 실행 시각과 실제 원본
질의/원자료를 남겨 재현 가능하게 했다.

H5·H6(docs/40)는 기존 위상 분석 도구(docs/34)가 계산하지 않던 두 가지를
새로 계산해서("추가 획득") 썼다 -- (1) 완전연결이 아닌 그래프에서도
최대연결요소(LCC) 기준으로 작은세상성(σ)을 실제로 계산하는 방법(기존
도구는 완전연결일 때만 계산하고 나머지는 건너뜀), (2)
참여계수(participation coefficient, Guimerà & Amaral 2005의 실제 공식)로
"연결자 허브"와 "지역 허브"를 구분하는 지표 -- 둘 다 이 파일에서
처음으로 구현했다."""

from __future__ import annotations

import networkx as nx

from app.data.human_data import get_macro_connectome
from app.lab.schemas import HypothesisEvidenceOut, HypothesisRecordOut

_EXECUTED_AT = "2026-09-24"


def _compute_h1_disease_hub_correlation() -> HypothesisRecordOut:
    """실시간 계산: 이 프로젝트가 큐레이션한 32개 질환 중 여러 질환에
    동시에 연루된("다중 질환") 영역이, 커넥톰 그래프 상에서도 위상적으로
    더 중심적인지 실제로 계산해본다."""
    macro = get_macro_connectome()
    graph = nx.Graph()
    graph.add_nodes_from(r.id for r in macro.regions)
    for e in macro.edges:
        if graph.has_edge(e.a, e.b):
            graph[e.a][e.b]["weight"] += e.weight
        else:
            graph.add_edge(e.a, e.b, weight=e.weight)

    degree = dict(graph.degree())
    max_degree = max(degree.values()) if degree else 0
    degree_c = {k: (v / max_degree if max_degree else 0.0) for k, v in degree.items()}
    betweenness = nx.betweenness_centrality(graph, weight=None)
    try:
        pagerank = nx.pagerank(graph, weight="weight")
    except nx.PowerIterationFailedConvergence:
        pagerank = dict.fromkeys(graph.nodes(), 0.0)

    def _normalize(d: dict[str, float]) -> dict[str, float]:
        vals = list(d.values())
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-12:
            return dict.fromkeys(d, 0.0)
        return {k: (v - lo) / (hi - lo) for k, v in d.items()}

    nd, nb, npr = _normalize(degree_c), _normalize(betweenness), _normalize(pagerank)
    combined = {k: (nd[k] + nb[k] + npr[k]) / 3 for k in graph.nodes()}

    disease_count: dict[str, int] = {}
    for disorder in macro.known_disorders:
        for rid in disorder.region_ids:
            disease_count[rid] = disease_count.get(rid, 0) + 1

    groups: dict[str, list[float]] = {"0개": [], "1개": [], "2개 이상": []}
    for rid, score in combined.items():
        count = disease_count.get(rid, 0)
        key = "0개" if count == 0 else ("1개" if count == 1 else "2개 이상")
        groups[key].append(score)

    averages = {k: (sum(v) / len(v) if v else 0.0) for k, v in groups.items()}

    xs = [disease_count.get(rid, 0) for rid in combined]
    ys = [combined[rid] for rid in combined]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / n
    std_x = (sum((x - mean_x) ** 2 for x in xs) / n) ** 0.5
    std_y = (sum((y - mean_y) ** 2 for y in ys) / n) ** 0.5
    pearson = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0.0

    verdict = "supported" if abs(pearson) >= 0.3 else ("inconclusive" if abs(pearson) >= 0.1 else "not_supported")

    return HypothesisRecordOut(
        id="h1-disease-hub-correlation",
        title="다중 질환 연루 영역은 위상적 허브일까?",
        statement=(
            "만약 여러 질환에 동시에 연루되는 뇌 영역이 실제로 '병목 지점'이라면, "
            "그 영역은 단일/무 질환 영역보다 커넥톰 그래프에서 위상적으로(중심성) 더 중심적일 것이다."
        ),
        method=(
            "네트워크 위상 분석(docs/34) 도구로 인간 거시 커넥톰 400개 영역의 중심성 종합점수를 실시간 계산하고, "
            "이 프로젝트가 실제로 큐레이션한 32개 질환(docs/33)의 region_ids를 영역별로 집계해 몇 개 질환에 "
            "연루되는지와 교차 비교한다."
        ),
        result_summary=(
            f"0개 질환 연루 영역 평균 중심성 {averages['0개']:.4f}(n={len(groups['0개'])}), "
            f"1개 {averages['1개']:.4f}(n={len(groups['1개'])}), "
            f"2개 이상 {averages['2개 이상']:.4f}(n={len(groups['2개 이상'])}) — "
            f"피어슨 상관계수 {pearson:.4f}"
            + ("로 사실상 무상관. " if abs(pearson) < 0.1 else ("로 약한 양의 상관. " if pearson > 0 else "로 약한 음의 상관. "))
            + "데이터 이력(docs/48-49): 처음 이 가설을 기록할 땐 거시 커넥톰에 네트워크 간 간선이 하나도 없어(원본 HCP 합의 행렬 "
            "5,059개 중 네트워크 내부 2,041개만 수록, 그래프 8조각) r=0.0501로 '기각'이었다. docs/49에서 원본 전체로 복구한 뒤 이 "
            "실시간 값이 올라갔지만, 해부학적 라벨 단위 순열 검정으로는 유의하지 않다(H1-1) -- 이 숫자 하나만으로 지지라고 볼 수 없다."
        ),
        verdict=verdict,
        evidence=[],
        raw_data_note=f"실시간 계산값 — 피어슨 r={pearson:.4f}, 그룹별 평균 {averages}",
        executed_at=None,
        is_live_computed=True,
    )


def _h2_dva_hub() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h2-dva-topological-hub",
        title="위상적으로 중심적인 '미큐레이션' 뉴런은 실제로 기능적으로 중요할까?",
        statement=(
            "만약 위상 중심성이 실제 기능적 중요성을 예측한다면, 이 프로젝트의 7개 고전 절제 연구(docs/26)에는 "
            "없지만 위상적으로 상위권인 웜 뉴런(DVA/RIPL/RIPR, docs/34에서 실제로 발견된 후보)을 억제했을 때도 "
            "실제 회로 반응에 측정 가능한 변화가 나타날 것이다."
        ),
        method=(
            "시뮬레이션 가상 실험실(docs/35)로 DVA/RIPL/RIPR 각각을 전진·후진·좌회전·우회전 4개 방향 모두에서 "
            "억제해 실제 HH 시뮬레이션을 돌렸다(기본 20개 이벤트 상한으로는 baseline=experiment로 나와 차이가 "
            "가려져서, docs/29에서 이미 겪은 것과 같은 문제 — 상한을 100으로 올려 재확인). 이어서 탐구형 "
            "챗봇(docs/36)으로 DVA의 실제 문헌상 기능을 조회했다."
        ),
        result_summary=(
            "DVA 억제 시 전진·후진·좌회전에서 RIMR·SMBDR 발화가 사라짐(우회전에서는 SMBDR만) — 실제 측정 가능한 "
            "효과 확인. 실제 문헌(PMC2865900, PMC3134788)에서 DVA는 TRP-4 기계감지 채널 기반 스트레치(자기수용감각) "
            "인터뉴런으로, 몸굽힘 진폭 조절과 NLP-12 신경펩타이드를 통한 운동 조절에 실제로 관여한다고 보고됨 — "
            "시뮬레이션에서 관찰된 운동 관련 뉴런(RIM/SMB) 영향과 실제 문헌상 역할이 서로 들어맞는다. 반면 "
            "RIPL/RIPR은 100개 이벤트 상한에서도 어떤 방향에서도 측정 가능한 차이를 만들지 않음 — 이 둘에 대해서는 "
            "가설이 지지되지 않음."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="A C. elegans stretch receptor neuron revealed by a mechanosensitive TRP channel homologue",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC2865900/",
            ),
            HypothesisEvidenceOut(
                title="A neuropeptide-mediated stretch response links muscle contraction to changes in neurotransmitter release",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3134788/",
            ),
        ],
        raw_data_note="가상 실험 원자료: DVA 억제 시 baseline=100/experiment=100(이벤트 상한 100 기준)이지만 실제 발화 뉴런 집합에서 RIMR/SMBDR 소실 확인. RIPL/RIPR은 동일 조건에서 차이 없음.",
        executed_at=_EXECUTED_AT,
        is_live_computed=False,
    )


def _h3_slc1a2_bdnf() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h3-slc1a2-bdnf-candidate",
        title="BDNF 옆의 '위치 후보 유전자' SLC1A2는 실제로 기능적 연관이 있을까?",
        statement=(
            "만약 위치 후보 유전자 접근(실제 유전학 방법론)이 유효하다면, BDNF 바로 옆 염색체 위치에 있는 "
            "SLC1A2(글루탐산 수송체, docs/37에서 실제로 발견된 최근접 후보)가 실제 문헌에서 BDNF의 시냅스 가소성 "
            "경로와 기능적으로 연관됐다고 보고된 적이 있을 것이다."
        ),
        method="유전자 경로 후보 가설 탐색기(docs/37)의 실제 결과를 탐구형 챗봇(docs/36)으로 실제 문헌 검증했다.",
        result_summary=(
            "실제 문헌 확인됨: BDNF가 성상교세포에서 SLC1A2(GLT-1/EAAT2) 발현을 유도한다는 실험 보고가 있고 "
            "(PubMed 12742080), EAAT2 활동이 시냅스 주변 글루탐산 농도·NMDA/mGluR 활성화를 조절해 LTP/LTD 같은 "
            "장기 가소성 유도 조건을 바꾼다는 다수의 연구가 있다(PMC6465798). 다만 'BDNF→EAAT2→가소성 변화'라는 "
            "인과 연쇄 전체를 한 논문이 직접 규정한 사례는 드물어(대부분 두 구간을 각각만 보여줌), 완전한 기전적 "
            "연결에는 추가 근거가 필요하다는 것도 실제 응답이 스스로 명시했다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Beta-amyloid and BDNF up-regulate the expression of glutamate transporter GLT-1/EAAT2 via NF-kappaB",
                url="https://pubmed.ncbi.nlm.nih.gov/12742080/",
            ),
            HypothesisEvidenceOut(
                title="Control of Long-Term Plasticity by Glutamate Transporters",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6465798/",
            ),
        ],
        raw_data_note="위치 후보 유전자 원자료: SLC1A2, 11p13, BDNF(11p14.1)과의 거리 0.03405(염색체 전체 길이 대비).",
        executed_at=_EXECUTED_AT,
        is_live_computed=False,
    )


def _h4_frontal_sup_medial() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h4-frontal-sup-medial-gap",
        title="이 프로젝트가 안 다룬 위상적 허브가, 실제 문헌에서는 이미 중요하게 다뤄지고 있을까?",
        statement=(
            "만약 '이 프로젝트의 큐레이션 데이터에 없다'는 것이 '실제 문헌에도 없다'를 뜻하지 않는다면, 인간 거시 "
            "커넥톰에서 위상적으로 상위권이지만 이 프로젝트의 32개 큐레이션 질환 어디에도 없는 "
            "Frontal_Sup_Medial_L(docs/34에서 실제로 발견된 후보)이 실제 문헌에서는 이미 특정 질환·인지기능과 "
            "연관되어 보고됐을 것이다."
        ),
        method="네트워크 위상 분석(docs/34)의 실제 결과를 탐구형 챗봇(docs/36)으로 실제 문헌 검증했다.",
        result_summary=(
            "강하게 지지됨: 내측 위이마이랑은 디폴트모드 네트워크(DMN)의 일부로, 자기참조 사고·사회인지·에피소드 "
            "기억 회상·마음방황 등 내부지향적 인지기능과 실제로 연관된다(Nature Reviews Neuroscience 리뷰, "
            "PMC10524518). 임상적으로는 우울증·조현병·양극성장애·불안에서 이 부위의 활동·연결성 변화가 반복적으로 "
            "보고되고(PMC12207756), 알츠하이머병에서도 이 부위의 연결성·시냅스 밀도 변화가 인지저하와 연관된다는 "
            "증거가 있다(PubMed 36718002) — 이 프로젝트의 큐레이션 공백이었을 뿐, 실제 문헌 공백이 전혀 아니었다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="The default mode network in cognition: a topographical perspective",
                url="https://www.nature.com/articles/s41583-021-00474-4.pdf",
            ),
            HypothesisEvidenceOut(
                title="20 years of the default mode network: a review and synthesis",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10524518/",
            ),
            HypothesisEvidenceOut(
                title="Default mode network functional connectivity as a transdiagnostic biomarker of cognitive function",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12207756/",
            ),
        ],
        raw_data_note="위상 분석 원자료: Frontal_Sup_Medial_L 종합 중심성 점수 0.755(2위), 이 프로젝트의 32개 질환 중 어디에도 미등장.",
        executed_at=_EXECUTED_AT,
        is_live_computed=False,
    )


def _h5_small_world_cross_species() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h5-small-world-cross-species",
        title="작은세상성은 이 프로젝트의 3개 종 신경계 모두에서 보편적으로 나타날까?",
        statement=(
            "만약 작은세상(small-world) 구조가 신경계 조직의 보편적 원리라면, 이 프로젝트가 실제로 가진 웜 전체 "
            "신경계·인간 거시 구조연결·초파리 회로 그래프 전부에서 작은세상성 지표(σ)가 1을 넘을 것이다."
        ),
        method=(
            "위상 분석(docs/34)의 기존 σ 계산은 그래프가 완전연결일 때만 돌고, 이 프로젝트의 5개 그래프는 전부 "
            "완전연결이 아니라 늘 건너뛰어졌다 — 그래서 이번에 최대연결요소(LCC) 기준으로 σ를 계산하는 방법을 "
            "새로 추가해서(추가 획득) 웜·인간·초파리(항법 회로) 3개에 실제로 적용했다. 이어서 탐구형 챗봇(docs/36)으로 "
            "작은세상성이 실제 문헌에서 종을 넘어선 보편 원리로 보고되는지 검증했다."
        ),
        result_summary=(
            "웜 σ=1.78(전체 302개 중 LCC 300개), 인간 σ=2.2352(전체 400개 중 LCC 91개뿐 — 대표성에 한계 있음을 "
            "정직하게 명시), 초파리 항법 회로 σ=1.4005(완전연결, 896개 전체) — 3개 종 전부 σ>1로 작은세상성 시사. "
            "실제 문헌은 이를 강하게 뒷받침한다: Watts & Strogatz의 1998년 원논문 자체가 C. elegans 신경망을 "
            "작은세상 네트워크의 실제 예시로 들었고, 이후 초파리 전체 연결체·영장류·인간 피질 연구까지 반복 "
            "확인됐다고 보고된다. 다만 정확한 수치는 계산 방법·데이터 해상도에 따라 달라져 기계적 일반화는 "
            "주의해야 한다는 점도 응답이 스스로 명시했다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(title="Collective dynamics of 'small-world' networks", url="https://doi.org/10.1038/30918"),
            HypothesisEvidenceOut(
                title="Network Statistics of the Whole-Brain Connectome of Drosophila",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10402125/",
            ),
            HypothesisEvidenceOut(
                title="Complex brain networks: graph theoretical analysis of structural and functional systems",
                url="https://www.nature.com/articles/nrn2575",
            ),
        ],
        raw_data_note=(
            "σ(LCC 기준, niter=5/nrand=5): 웜 1.78(300/302 노드), 인간 2.2352(91/400 노드), 초파리 항법 1.4005(896/896 노드). "
            "정정(docs/49): 인간 값이 400개 중 91개뿐인 조각에서 나온 건 거시 커넥톰에 네트워크 간 간선이 빠져 그래프가 8조각이었기 "
            "때문이다(가장 큰 조각 = 기본모드 네트워크 하나). 원본 전체(간선 5,059개)로 복구한 뒤엔 그래프가 완전연결이고 연구소 위상 도구가 "
            "400개 전체로 σ=3.93을 계산한다 -- 결론(σ>1, 작은세상성)은 유지되며 오히려 더 뚜렷하다."
        ),
        executed_at=_EXECUTED_AT,
        is_live_computed=False,
    )


def _h6_connector_hub_cross_species() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h6-connector-hub-cross-species",
        title="'미큐레이션' 고중심성 후보는 여러 모듈에 걸친 '연결자 허브'일까 — 이 패턴은 종을 넘어설까?",
        statement=(
            "만약 H2에서 실제로 기능적 효과가 확인된 DVA가 '연결자 허브'(여러 커뮤니티에 걸쳐 연결되는 노드, "
            "실제 문헌 개념)이기 때문에 중요하다면, DVA의 참여계수는 이미 알려진 AVA/AVB급 명령 인터뉴런과 "
            "비슷하게 높을 것이다 — 그리고 이 '연결자 허브가 곧 기능적으로 중요하다'는 패턴이 인간 거시 "
            "커넥톰에서도 똑같이 나타날 것이다."
        ),
        method=(
            "위상 분석이 이미 계산하는 커뮤니티 검출 결과에, 참여계수(Guimerà & Amaral 2005의 실제 공식: "
            "P_i = 1 - Σ(k_is/k_i)²)를 새로 계산해 추가했다(추가 획득). 웜에서는 DVA/RIPL/RIPR을 이미 알려진 "
            "AVA/AVB와 비교했고, 인간에서는 Frontal_Sup_Medial_L의 9개 실제 파셀을 전체 평균·알츠하이머 연루 "
            "영역과 비교했다. 이어서 탐구형 챗봇으로 '연결자 허브' 개념의 실제 문헌 근거를 확인했다."
        ),
        result_summary=(
            "웜에서는 지지됨: DVA 참여계수 0.7943 — AVAL 0.7975·AVAR 0.778·AVBL 0.7749·AVBR 0.7871과 사실상 "
            "동급이며, 네트워크 평균(0.5177)보다 훨씬 높다 — DVA가 진짜 연결자 허브라는 실제 근거이자 H2의 실제 "
            "기능적 효과와 정합적이다. RIPL 0.6276·RIPR 0.6653은 평균보다는 높지만 DVA/AVA/AVB보다 뚜렷이 "
            "낮음 — H2에서 이 둘이 효과가 없었던 것과 다시 한번 정합적. 반면 **인간으로의 종간 일반화는 지지되지 "
            "않았다**: 인간 거시 그래프의 평균 참여계수는 사실상 0(0.0039)이고, Frontal_Sup_Medial_L의 실제 9개 "
            "파셀 중 8개가 정확히 0.0(1개만 0.375) — 알츠하이머 연루 91개 영역의 평균도 0.0085로 마찬가지로 "
            "거의 0이다. 즉 인간 거시 구조연결 그래프는 거의 완벽하게 모듈화돼 있어 '연결자 허브'라는 개념 자체가 "
            "이 데이터에서는 거의 성립하지 않는다. 실제 문헌(참여계수/허브 손상 연구)도 이런 판정이 분할 "
            "알고리즘·공간 해상도에 민감하다고 명시하는데, 웜은 시냅스 단위 EM 데이터이고 인간은 그보다 훨씬 "
            "성긴 확산MRI 파셀 단위 구조연결 데이터라 해상도 차이가 이 불일치의 유력한 원인으로 보인다. "
            "정정(docs/48): 인간 쪽 결론의 진짜 원인은 해상도가 아니라 데이터 결함이었다 -- 이 프로젝트의 거시 커넥톰은 "
            "원본 HCP 합의 행렬에서 네트워크 '내부' 간선만 수록해(네트워크 간 간선 3,018개 누락) 참여계수가 구조적으로 0일 "
            "수밖에 없었다. 원본 전체(간선 5,059개)로 다시 계산하면 인간 평균 참여계수는 0.630(웜 평균 0.518보다 오히려 높음), "
            "알츠하이머 영역 평균 0.679 -- '인간에선 연결자 허브 개념이 성립하지 않는다'는 위 결론은 철회되어야 한다(H1-1~H1-4)."
        ),
        verdict="inconclusive",
        evidence=[
            HypothesisEvidenceOut(title="Functional cartography of complex metabolic networks", url="https://pmc.ncbi.nlm.nih.gov/articles/PMC2175124/"),
            HypothesisEvidenceOut(
                title="The modular and integrative functional architecture of the human brain",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC4679040/",
            ),
            HypothesisEvidenceOut(title="Evidence for hubs in human functional brain networks", url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3838673/"),
        ],
        raw_data_note=(
            "참여계수 원자료 — 웜: DVA 0.7943, RIPL 0.6276, RIPR 0.6653, AVAL 0.7975, AVAR 0.778, AVBL 0.7749, "
            "AVBR 0.7871, 전체평균 0.5177. 인간: 전체평균 0.0039, Frontal_Sup_Medial_L 9개 파셀 중 8개=0.0(1개=0.375), "
            "알츠하이머 연루 91개 영역 평균 0.0085."
        ),
        executed_at=_EXECUTED_AT,
        is_live_computed=False,
    )


# ---------------------------------------------------------------------------
# docs/46 -- 가상 개체 폐루프(docs/41-45)로 세우고 검증한 가설 H7-H12. 실제 Brian2
# 네트워크를 폐루프 모듈 그대로 돌린 실험(backend/scripts/closed_loop_hypotheses.py,
# 백엔드 Docker 컨테이너·cython codegen)이며, 각 예측은 실험을 돌리기 전에 세웠다.
# ---------------------------------------------------------------------------

_LOOP_EXECUTED_AT = "2026-09-28"
_LOOP_SCRIPT = "backend/scripts/closed_loop_hypotheses.py"


def _h7_worm_blind_zone() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h7-worm-chemotaxis-blind-zone",
        title="가상 웜의 감각 문턱은 '냄새를 못 맡는 구역'을 만들까?",
        statement=(
            "만약 가상 웜의 감각이 하나의 전류 문턱으로 켜진다면, 틱당 농도 감소(ΔC)가 그 문턱을 넘는 곳에서만 "
            "반전이 가능하므로 광원에서 너무 가깝거나(기울기가 완만한 봉우리) 너무 먼(농도 자체가 거의 0) 곳에 "
            "기울기를 전혀 못 느끼는 사각지대가 생길 것이고, 그 경계는 문턱값에서 해석적으로 예측될 것이다."
        ),
        method=(
            f"① 감각 전류 비율 f를 0~1로 스윕해 반전(AVA>AVB) 문턱을 측정({_LOOP_SCRIPT} worm-sweep). ② 가우시안 "
            "농도장에서 실측 속도(29.6μm/틱)로 광원 반대쪽으로 움직일 때의 ΔC(r)가 문턱을 넘는 거리 구간을 계산해 "
            "사각지대 경계를 예측. ③ 실제 폐루프에서 거리 r마다 광원 반대쪽으로 두 틱 이동시켜 두 번째 틱의 "
            "실제 반응을 측정(worm-boundary, 0.25~0.5mm 간격 정밀 스캔 포함). ④ 기본 출발점(광원에서 70mm)에서 "
            "온전한 웜과 감각을 제거한 웜의 200틱 궤적을 같은 시드로 비교."
        ),
        result_summary=(
            "지지됨. 반전 문턱은 f=0.10~0.12(결정론적 -- 같은 입력 두 번에 같은 출력). 이로부터 예측한 감지 구간은 "
            "3.6~4.3mm ~ 57.0~59.4mm, 실제 폐루프로 잰 경계는 안쪽 4.0~4.25mm, 바깥쪽 57.5~58mm로 두 경계 모두 "
            "예측 구간 안에 들어왔다 -- 두 경계가 하나의 문턱(ΔC/틱≈1.9×10⁻⁴, f≈0.115)으로 동시에 설명된다. "
            "행동 수준의 결과: 아레나 면적의 28%가 사각지대이고, 기본 출발점(70mm)도 그 안이다. 거기서 출발한 "
            "온전한 웜과 감각 제거 웜 8쌍의 궤적은 소수점까지 동일했다(반전 0회) -- 기본 데모의 웜이 광원에 "
            "닿는 건 기울기를 감지해서가 아니라 처음부터 광원을 향해 출발하기 때문이다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Pierce-Shimomura, Morse & Lockery 1999 -- The fundamental role of pirouettes in C. elegans chemotaxis (J Neurosci 19:9557)",
                url="https://www.jneurosci.org/content/19/21/9557",
            ),
        ],
        raw_data_note=(
            "문턱 스윕: f≤0.10 감각·명령 발화 0, f=0.12 감각 5·AVB 11·AVA 16(반전). 정밀 경계: r=4.00mm ΔC=-1.88e-4 무반응, "
            "4.25mm ΔC=-1.99e-4 반전 / 57.5mm ΔC=-1.93e-4 반전, 58mm ΔC=-1.86e-4 무반응. 70mm 출발 8쌍 순이동: 온전=감각제거="
            "[4.82,-4.53,1.38,-5.90,-5.90,3.99,5.68,-5.34]mm."
        ),
        executed_at=_LOOP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h8_worm_ase_asymmetry() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h8-worm-ase-asymmetry-in-connectome",
        title="실제 ASEL(ON)/ASER(OFF) 기능 비대칭이 이 커넥톰 모델에서 재현될까?",
        statement=(
            "만약 이 302개 뉴런 모델이 실제 감각-명령 경로를 담고 있다면, Suzuki et al. 2008이 보고한 대로 ASER만 "
            "자극하면 반전(AVA>AVB), ASEL만 자극하면 전진(AVB≥AVA)이 나와야 한다. 또 AWC→AIY가 실제처럼 억제성이면 "
            "AWC 자극 시 AIY가 조용해져야 한다(Chalasani et al. 2007)."
        ),
        method=(
            f"감각뉴런 부분집합(AWC 쌍, ASE 쌍, 각 단일 뉴런)만 f=0.3/0.6/1.0으로 자극해 AVA/AVB/AIB/AIY 발화를 측정"
            f"({_LOOP_SCRIPT} worm-subsets). 후속으로 실제 행동이 알려진 입력(앞 촉각 ALM/AVM→후진, 뒤 촉각 PLM→전진, "
            "Chalfie et al. 1985; 유인 냄새 AWA, 유해 자극 ASH)을 같은 방식으로 자극하고, AWC→AIY 글루탐산 시냅스 3개만 "
            "억제성(-70mV)으로 바꿔 다시 측정(worm-signs). 모델 코드(hh_model.py)의 시냅스 부호 규칙도 확인."
        ),
        result_summary=(
            "지지되지 않음(비대칭 미재현). ASEL 단독 자극도 AVA>AVB(반전, f=1.0에서 AVA 26/AVB 17)로 ASER 단독과 같은 "
            "쪽이었다. 원인: 이 모델은 GABA 시냅스만 억제성이고 글루탐산 시냅스는 전부 흥분성으로 둔다(실제의 "
            "글루탐산 개폐 염소 채널 억제를 표현 못 함) -- 그래서 입력의 종류와 무관하게 명령층에 닿기만 하면 AVA>AVB가 "
            "된다: 앞 촉각(ALM/AVM)·유해 자극(ASH)은 실제처럼 후진이지만, 실제로는 전진을 촉진하는 유인 냄새 ON 세포 "
            "AWA도 후진 편향, 뒤 촉각 PLM은 명령 뉴런을 아예 활성화하지 못했다. AWC→AIY 3개 시냅스를 실제처럼 억제성으로 "
            "바꾸자 AIY 발화는 실제 문헌대로 0이 됐지만 AVA:AVB 비는 1.47로 전후 동일 -- 반전 편향은 AIY 부호가 아니라 "
            "더 아래 명령층에서 생긴다."
        ),
        verdict="not_supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Suzuki et al. 2008 -- Functional asymmetry in C. elegans taste neurons and its computational role in chemotaxis (Nature 454:114)",
                url="https://www.nature.com/articles/nature06927",
            ),
            HypothesisEvidenceOut(
                title="Chalasani et al. 2007 -- Dissecting a circuit for olfactory behaviour in C. elegans (Nature 450:63)",
                url="https://www.nature.com/articles/nature06292",
            ),
            HypothesisEvidenceOut(
                title="Chalfie et al. 1985 -- The neural circuit for touch sensitivity in C. elegans (J Neurosci 5:956)",
                url="https://www.jneurosci.org/content/5/4/956",
            ),
        ],
        raw_data_note=(
            "f=1.0 AVA/AVB: 4개 전부 32/23, AWC 쌍 28/19, ASE 쌍 30/19, AWCL 24/15, AWCR 24/17, ASEL 26/17, ASER 22/15. "
            "ALM 13/7, AVM 15/9, PLM 0/0, AWA 28/19, ASH 31/20. AWC→AIY 억제 전/후(f=1.0): AVA 28→22, AVB 19→15, AIY 7→0, AIB 16→9."
        ),
        executed_at=_LOOP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h9_worm_klinokinesis_efficiency() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h9-worm-klinokinesis-closed-loop",
        title="반전 빈도 조절(klinokinesis)만으로 실제 광원 접근이 일어날까?",
        statement=(
            "만약 Pierce-Shimomura 1999의 결론(화학주성은 반전이 동물을 기울기 쪽으로 재정향시키는 과정의 연속)이 "
            "이 가상 웜에서도 성립한다면, 정밀 조향(klinotaxis) 없이 반전 빈도 조절만 있는 이 폐루프로도 감지 구간 안에서 "
            "출발한 웜은 무작위 방향으로 출발해도 광원 쪽으로 순이동하고, 감각을 제거한 대조군은 그러지 못할 것이다."
        ),
        method=(
            f"광원에서 30mm(감지 구간 안) 지점에서 무작위 방향으로 출발하는 에피소드 8개씩, 200틱(생물학적 20초, 최대 이동 "
            f"5.92mm)을 온전한 웜 / 감각 제거 웜(같은 네트워크·같은 시드)으로 실제 폐루프 실행({_LOOP_SCRIPT} worm-episodes, "
            "7개 프로세스 병렬). 순이동 = 출발 거리 - 도착 거리."
        ),
        result_summary=(
            "지지됨. 온전한 웜 순이동 +3.44±1.76mm(8/8 모두 광원 쪽, 가능한 최대의 58%), 감각 제거 -0.83±5.13mm(4/8). 같은 "
            "시드끼리 짝지어 보면, 처음부터 광원 쪽을 향한 4개는 두 조건이 같았고 반대로 출발한 4개는 온전한 웜만 반전(평균 "
            "1.2회)으로 돌아와 모두 양수가 됐다 -- 실제 문헌이 말하는 '반전이 재정향을 만든다'는 메커니즘이 폐루프에서 그대로 "
            "나타났다. 광원 쪽으로 가던 중 일어난 '잘못된' 반전은 0회."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Pierce-Shimomura, Morse & Lockery 1999 -- The fundamental role of pirouettes in C. elegans chemotaxis",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC6782915/",
            ),
        ],
        raw_data_note=(
            "30mm 출발 순이동(mm) 온전: [4.69,4.56,1.05,1.04,2.26,3.79,5.65,4.46] / 감각 제거: [4.69,-4.65,1.05,-5.91,-5.90,3.79,5.65,-5.39]. "
            "실행 1,194초(에피소드 40개, H10 조건 포함)."
        ),
        executed_at=_LOOP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h10_worm_correct_polarity_breaks_chemotaxis() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h10-worm-correct-ase-polarity-breaks-loop",
        title="감각 극성을 생물학적으로 '올바르게' 고치면 가상 웜이 더 잘할까, 못할까?",
        statement=(
            "H8에서 이 모델은 어떤 감각 입력이든 반전 쪽으로 기운다는 걸 확인했다. 그렇다면 ASEL을 실제처럼 농도 '증가'에 "
            "반응하는 ON 세포로 고치면(Suzuki 2008), 광원 쪽으로 잘 가고 있을 때(농도 증가) ASEL이 켜져 오히려 반전을 "
            "일으키므로 화학주성이 나빠질 것이다 -- 즉 지금 모델의 '틀린' 극성(ASEL도 감소에 반응)이 반전 편향을 우연히 "
            "상쇄하고 있을 것이다."
        ),
        method=(
            "H9와 같은 시드·같은 출발점(광원에서 30mm)·200틱 에피소드 8개를, 감각 극성만 AWC·ASER=감소(OFF), ASEL=증가(ON)로 "
            f"바꾼 조건으로 실행({_LOOP_SCRIPT} worm-episodes의 asel_on 조건, 같은 감각 이득)."
        ),
        result_summary=(
            "지지됨(예측 적중). 극성을 생물학적으로 고친 웜은 순이동 -0.26±2.76mm(4/8)로 화학주성이 사라졌고, 반전이 평균 6.8회로 "
            "늘었으며 그중 3.0회는 광원 쪽으로 가던(농도가 오르던) 중에 일어난 '잘못된' 반전이었다(온전한 모델은 0회). 결론: 이 "
            "모델의 klinokinesis는 행동 수준에선 맞지만 기전 수준에선 '틀린 극성 × 부호 없는 글루탐산'이라는 두 근사가 서로를 "
            "상쇄해서 나온다. 실제 비대칭 계산을 재현하려면 글루탐산 시냅스의 억제성(GluCl) 부호 정보가 먼저 필요하다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Suzuki et al. 2008 -- ASEL is an ON-cell, ASER an OFF-cell (Nature 454:114)",
                url="https://www.nature.com/articles/nature06927",
            ),
        ],
        raw_data_note="30mm 출발 순이동(mm) ASEL-ON 조건: [-0.33,-1.18,1.05,-1.04,-5.90,3.79,0.82,0.73]; 반전 평균 6.8회(오르막 3.0회).",
        executed_at=_LOOP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h11_fly_avoidance_sphere() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h11-fly-avoidance-sphere",
        title="초파리의 회피는 문턱으로 예측되는 '구(球)' 모양 경계를 가질까?",
        statement=(
            "만약 가상 초파리의 회피가 PN 전류 문턱 하나로 켜지는 문턱형 반응이라면(docs/42), 바닥 광원 가우시안에서 "
            "C(r)=문턱이 되는 반경 r*=σ·√(2·ln(1/f문턱)) 안에서만 회피가 일어나고, 비행 중 농도를 3D 거리로 계산하므로 "
            "(docs/45) 광원 바로 위 높이 z에서도 같은 r*가 경계가 되는 구 모양일 것이다 -- 즉 r*보다 높이 날면 냄새원 "
            "바로 위를 지나가도 회로가 반응하지 않을 것이다."
        ),
        method=(
            f"① PN 전류 비율 f를 0~1로 스윕해 MBON01 발화 문턱 측정({_LOOP_SCRIPT} fly-sweep) → r* 예측. ② 결과를 보기 전에 "
            "예측을 적어 두고, 광원에서 바닥 수평 거리 r과 광원 바로 위 높이 z를 1mm 간격으로 바꿔 실제 회로가 회피를 "
            "결정하는지 측정(fly-boundary)."
        ),
        result_summary=(
            "지지됨(예측 정확히 적중). 문턱은 f=0.11~0.12(PN 0.066~0.072nA, 결정론적)이고 예측 경계는 r*=16.5~16.8mm. 실제 "
            "측정: 바닥에서 16mm까지 회피, 17mm부터 무반응 / 공중(광원 바로 위)에서도 16mm까지 회피, 17mm부터 무반응 -- "
            "경계가 정확히 예측 구간 안에 있고 바닥·공중이 같은 반경인 구다. 함의: 수동 조종에서 17mm 이상 높이로 날면 "
            "냄새원 바로 위를 지나도 이 회로는 냄새를 '못 맡는다'."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Aso et al. 2014 -- The neuronal architecture of the mushroom body provides a logic for associative learning (eLife 3:e04577)",
                url="https://elifesciences.org/articles/04577",
            ),
        ],
        raw_data_note=(
            "스윕: f=0.11 MBON01 0, f=0.12 MBON01 16, f=0.14 71, f=1.0 61(문턱 위에선 비례 안 함 -- docs/42 소견 재확인). "
            "경계: r(=z)=16mm C=0.1353 회피, 17mm C=0.1046 무반응(바닥·공중 동일)."
        ),
        executed_at=_LOOP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h12_fly_leaky_exclusion() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h12-fly-random-avoidance-leaky-zone",
        title="무작위 방향 회피만으로 초파리를 냄새 구역 밖에 붙잡아 둘 수 있을까?",
        statement=(
            "H11의 경계가 정확하다면, 자동 폐루프에서 초파리는 경계 안으로 기껏해야 한 틱 이동거리(2.8mm)와 후진 몇 번만큼만 "
            "들어올 수 있으므로 최근접 거리는 약 12mm(r*-4.2mm) 밑으로 내려가지 않을 것이고, 냄새 입력을 제거한 대조군은 "
            "광원에 자유롭게 다가갈 것이다."
        ),
        method=(
            f"광원에서 25mm 이상 떨어진 무작위 지점·방향에서 출발하는 자동 에피소드 7개씩, 100틱(생물학적 10초)을 온전한 초파리 / "
            f"냄새 입력 제거(같은 시드)로 실행({_LOOP_SCRIPT} fly-episodes, 7개 프로세스 병렬), 최근접 거리와 15mm 안 체류 비율 측정."
        ),
        result_summary=(
            "부분적으로만 맞아 기각으로 기록. 회피는 분명히 효과가 있었다: 최근접 거리 평균 12.4mm(대조군 3.9mm), 15mm 안 체류 "
            "11.6%(대조군 21.0%). 하지만 '12mm 밑으로 안 들어간다'는 예측은 깨졌다 -- 최소 6.97mm, 10.2mm, 10.6mm까지 들어갔고, "
            "한 에피소드는 100틱 중 67번 회피하며 41%를 구역 안에서 보냈다. 원인: 회피가 '1.4mm 후진 + 완전 무작위 재정향'이라 "
            "구역 안에서는 매 틱 회피하면서도 사실상 1.4mm 보폭의 무작위 걸음이 되어, 더 깊이 들어가거나 갇힐 수 있다. 경계 감지는 "
            "정확하지만(H11) 방향 정보가 없는 회피는 '새는' 배제 구역을 만든다 -- 실제 초파리처럼 농도 변화나 좌우 비교로 "
            "'바깥쪽'을 고르는 기전이 있어야 배제가 단단해질 것이라는 다음 가설로 이어진다."
        ),
        verdict="not_supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Aso et al. 2014 -- MBON activation drives avoidance (eLife 3:e04577)",
                url="https://elifesciences.org/articles/04577",
            ),
        ],
        raw_data_note=(
            "최근접(mm) 온전: [15.42,10.58,14.59,15.06,6.97,13.85,10.24] / 대조: [1.55,5.28,0.52,1.22,12.36,1.43,4.56]. "
            "15mm 안 체류 비율 온전: [0,0.22,0.02,0,0.41,0.02,0.14] / 대조: [0.32,0.29,0.22,0.16,0.06,0.17,0.25]. "
            "회피 횟수 온전: [4,35,6,8,67,15,24]. 실행 2,453초."
        ),
        executed_at=_LOOP_EXECUTED_AT,
        is_live_computed=False,
    )


# ---------------------------------------------------------------------------
# docs/47 -- H7-H12의 결론을 실제 모델 수정으로 옮기고 다시 검증한 가설 H13-H15.
# ---------------------------------------------------------------------------

_FIX_EXECUTED_AT = "2026-09-29"


def _h13_worm_receptor_signs() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h13-worm-receptor-signs-rescue-polarity",
        title="시냅스 흥분/억제를 수용체 발현대로 바꾸면 생물학적으로 올바른 감각 극성이 작동할까?",
        statement=(
            "H10에서 ASEL을 실제처럼 ON 세포로 고치면 화학주성이 망가졌고, 원인은 모든 글루탐산 시냅스를 흥분성으로 둔 "
            "부호 규칙(H8)이었다. 그렇다면 시냅스마다 시냅스 후 수용체 발현으로 예측한 부호(Fenyves et al. 2020 -- 억제성 "
            "GluCl/ACC 채널 포함)를 쓰면 (1) AWC→AIY 억제 같은 실제 소견이 재현되고, (2) 올바른 극성으로도 화학주성이 "
            "회복되며, (3) 그래도 ASEL 단독→전진 같은 비대칭은 신호 부호만으론 재현되지 않을 것이다."
        ),
        method=(
            "원 논문 S1 Data의 연결별 예측 극성('+'/'-'; 'complex'·예측 없음은 추측하지 않고 기존 규칙 유지)을 이 프로젝트의 "
            "3,638개 화학 시냅스에 대응(+ 854, - 412 적용). 부호 규칙(A 기존 / B 수용체 기반 / C 수용체 기반+실제 극성)별로 알려진 "
            f"입력의 전진/후진 방향과 문턱을 비교하고({_LOOP_SCRIPT} worm-signmodel), H9와 같은 시드·출발점으로 폐루프 에피소드 "
            "8개씩 실행(worm-episodes plan=B@30,C@30). AVA·AVB가 커넥톰에서 받는 입력 총량도 계산."
        ),
        result_summary=(
            "(1) 지지: 수용체 기반 부호에서 AIY는 AWC·ASE 어느 입력에서도 0으로 조용해졌다(실제 소견과 일치), 전체 활동도 1/2~1/3로 "
            "줄었다(기존 규칙이 과흥분이었음을 시사). (2) 지지: 올바른 극성(C)의 화학주성이 순이동 +3.31±2.63mm(7/8)로 회복 -- "
            "기존 부호에선 -0.26mm(4/8)였다. 오르막 반전은 1.2회로 남았다. (3) 지지: ASEL 단독·AWA 자극은 여전히 AVA≥AVB, PLM은 "
            "여전히 명령층에 닿지 못한다. 원인은 구조적이다 -- 커넥톰에서 AVA 쌍이 받는 화학 시냅스 입력은 1,338(87개 뉴런), AVB 쌍은 "
            "673(63개), 전기 시냅스도 459 대 269로 약 2배 -- 넓게 퍼지는 흥분은 항상 AVA 쪽으로 기운다. 실제 선충은 상호 억제·등급 "
            "전위·신경조절로 이를 해소한다고 여겨지며, 스파이크 HH 모델에는 그 기전이 없다. 이 결과로 가상 웜의 기본 설정을 C(수용체 "
            "기반 부호 + 실제 극성)로 바꿨다(다른 기존 기능은 기존 규칙 유지)."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Fenyves et al. 2020 -- Synaptic polarity and sign-balance prediction using gene expression data in the C. elegans chemical synapse neuronal connectome network (PLOS Comput Biol 16:e1007974)",
                url="https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007974",
            ),
            HypothesisEvidenceOut(
                title="Chalasani et al. 2007 -- AWC inhibits AIY via glutamate-gated chloride channels (Nature 450:63)",
                url="https://www.nature.com/articles/nature06292",
            ),
            HypothesisEvidenceOut(
                title="Suzuki et al. 2008 -- ASEL ON / ASER OFF (Nature 454:114)",
                url="https://www.nature.com/articles/nature06927",
            ),
        ],
        raw_data_note=(
            "f=1.0 AVA/AVB/AIY -- A: ASEL 26/17/6, AWC 28/19/7, AWA 28/19/6 · B: ASEL 10/8/0, AWC 10/8/0, AWA 17/12/0. 반전 문턱: A f=0.10~0.12, "
            "C f=0.12~0.14. 30mm 출발 순이동(mm) B: [4.69,4.56,1.05,1.04,2.26,3.79,5.65,4.46](A와 동일), C: [4.69,4.39,1.05,-1.01,5.22,5.73,5.65,0.73]."
        ),
        executed_at=_FIX_EXECUTED_AT,
        is_live_computed=False,
    )


def _h14_worm_new_start() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h14-worm-default-start-in-band",
        title="출발점을 감지 구간 안으로 옮기고 광원 반대쪽을 보게 하면, 기본 데모가 진짜 화학주성을 보여줄까?",
        statement=(
            "H7에서 원래 출발점(70mm)은 사각지대라 감각을 끈 웜과 궤적이 같았다. 새 설정(C)의 감지 구간(재측정 약 5~55mm) 안쪽 "
            "40mm에서 광원 '반대쪽'을 보고 출발시키면, 온전한 웜은 곧바로 농도 감소를 느껴 돌아서 광원 쪽으로 가고, 감각을 끈 웜은 "
            "그대로 멀어질 것이다."
        ),
        method=(
            f"기본 설정 C에서 반전 문턱을 다시 재 감지 구간을 계산(worm-sweep: f=0.12~0.14 → 5.05~54.85mm). 실제 페이지의 '다시 시작'과 "
            f"같은 조건(모듈 기본값)으로 400틱(최대 11.84mm) 에피소드 7개씩, 온전/감각 제거({_LOOP_SCRIPT} worm-default-start)."
        ),
        result_summary=(
            "지지됨. 온전한 웜 7개 모두 두 번째 틱(비교할 첫 이동 직후)에 농도 감소를 감지해 반전했고, 순이동 +5.96±6.76mm(5/7 광원 쪽, "
            "4개는 가능한 최대에 근접). 감각을 끈 웜은 7개 모두 -11.84mm로 그대로 멀어졌다 -- 원래 출발점에서 두 조건이 소수점까지 같았던 "
            "것(H7)과 정반대로, 이제 기본 데모의 움직임은 실제 감각 회로의 결과다. 두 에피소드가 약간 멀어진 채 끝난 건(-2.8mm) 무작위 재정향 "
            "운이며, 정밀 조향(klinotaxis)이 없는 이 기전의 예상된 한계다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Pierce-Shimomura, Morse & Lockery 1999 -- The fundamental role of pirouettes in C. elegans chemotaxis",
                url="https://www.jneurosci.org/content/19/21/9557",
            ),
        ],
        raw_data_note=(
            "순이동(mm) 온전: [11.12,-2.76,2.10,-2.52,10.62,11.70,11.44], 반전 횟수 [7,10,2,7,8,2,8], 첫 반전 틱 전부 2. "
            "감각 제거: 7개 모두 -11.84, 반전 0."
        ),
        executed_at=_FIX_EXECUTED_AT,
        is_live_computed=False,
    )


def _h15_fly_directed_avoidance() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h15-fly-directed-avoidance-seals-zone",
        title="냄새의 시간 변화로 회피 방향을 고르면 '새는' 배제 구역이 막힐까?",
        statement=(
            "H12에서 완전 무작위 회피는 구역 안에서 무작위 걸음이 되어 새는 구역을 만들었다. 광원 위치를 쓰지 않고 뇌가 받는 입력의 "
            "시간 비교만으로 -- 직전 틱보다 냄새가 짙어졌으면 반대로(±30도), 옅어지는 중이면 그대로(±30도) 물러나면 -- 최근접 거리가 "
            "경계(16.6mm)에서 한 틱 이동 남짓 안쪽(약 13mm 이상)에 머물고 갇히는 에피소드가 사라질 것이다."
        ),
        method=(
            f"H12와 같은 시드·출발점·100틱으로, 원래 무작위 회피(random -- H12 재현 확인용)와 방향 선택 회피(directed)를 7개씩 실행"
            f"({_LOOP_SCRIPT} fly-episodes conditions=random,directed). 방향 규칙의 근거: 실제 보행 초파리도 냄새만으로 냄새 시작/소실에 "
            "따라 회전·속도를 바꾸지만, 바람 방향 같은 절대 방향 선택엔 더듬이 기계감각이 필요하다(Álvarez-Salvado et al. 2018) -- "
            "'반대로 돈다'는 규칙 자체는 이 모델의 단순화."
        ),
        result_summary=(
            "지지됨. 무작위 조건은 H12 수치를 소수점까지 그대로 재현했다(리팩터링이 기존 동작을 바꾸지 않았다는 확인). 방향 선택 회피는 "
            "최근접 거리 최소 13.98mm·평균 14.93mm(무작위 6.97/12.39mm)로 예측한 13mm 이상을 모든 에피소드에서 지켰고, 15mm 안 체류는 "
            "11.6%→0.4%, 회피 횟수는 에피소드당 2~9회(무작위는 최대 67회 -- 갇힘)로 갇힘이 사라졌다. 이 결과로 가상 초파리의 기본 회피를 "
            "방향 선택 방식으로 바꿨다(수동 조종의 반사도 같은 규칙)."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Álvarez-Salvado et al. 2018 -- Elementary sensory-motor transformations underlying olfactory navigation in walking fruit-flies (eLife 7:e37815)",
                url="https://elifesciences.org/articles/37815",
            ),
            HypothesisEvidenceOut(
                title="Aso et al. 2014 -- MBON activation drives avoidance (eLife 3:e04577)",
                url="https://elifesciences.org/articles/04577",
            ),
        ],
        raw_data_note=(
            "최근접(mm) directed: [13.98,15.21,15.13,15.29,14.86,15.53,14.49] / random: [15.42,10.58,14.59,15.06,6.97,13.85,10.24](H12와 동일). "
            "15mm 안 체류 directed: [0.01,0,0,0,0.01,0,0.01]. 회피 횟수 directed: [5,2,5,7,9,7,3]. 실행 2,234초."
        ),
        executed_at=_FIX_EXECUTED_AT,
        is_live_computed=False,
    )


# ---------------------------------------------------------------------------
# docs/48 -- H1·H2·H3에 대한 외부 검토 의견(사용자 제공)을 받아 세운 후속 가설 H1-1~H1-5, H2-1~H2-3, H3-1.
# 각 예측은 실험 전에 세웠다. 인간 분석은 backend/scripts/human_hub_hypotheses.py, 웜은
# closed_loop_hypotheses.py(+analyze_silence_all.py), 유전자는 gene_positional_hypothesis.py.
# ---------------------------------------------------------------------------

_FOLLOWUP_EXECUTED_AT = "2026-09-29"
_HUMAN_SCRIPT = "backend/scripts/human_hub_hypotheses.py"

_EV_CROSSLEY = HypothesisEvidenceOut(
    title="Crossley et al. 2014 -- The hubs of the human connectome are generally implicated in the anatomy of brain disorders (Brain 137:2382)",
    url="https://academic.oup.com/brain/article/137/8/2382/2847927",
)
_EV_HANSEN_NC = HypothesisEvidenceOut(
    title="Hansen et al. 2022 -- Local molecular and global connectomic contributions to cross-disorder cortical abnormalities (Nat Commun 13:4682)",
    url="https://www.nature.com/articles/s41467-022-32420-y",
)
_EV_LIU = HypothesisEvidenceOut(
    title="Liu, Shafiei, Baillet & Mišić 2023 -- HCP consensus structural connectome (Schaefer-400) data, netneurolab/liu_meg-scfc",
    url="https://github.com/netneurolab/liu_meg-scfc",
)


def _h1_1_full_graph_reanalysis() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h1-1-full-graph-reanalysis",
        title="H1-1 · 끊어진 그래프를 고치고 지표를 나눠 보면, 질환 연루 수와 허브성의 상관이 드러날까?",
        statement=(
            "H1(r=0.0501)을 다시 보다가 이 프로젝트의 인간 거시 커넥톰에 네트워크 간 간선이 하나도 없다는 걸 발견했다(원본 HCP 합의 "
            "행렬 5,059개 중 네트워크 내부 2,041개만 수록 -- 그래프가 8조각). 만약 H1의 무상관이 이 결함 때문이라면, 원본 전체 그래프에서 "
            "여러 중심성 지표(degree·betweenness·closeness·eigenvector·참여계수·rich-club)를 따로 계산하면 질환 연루 수와 양의 상관이 "
            "드러나고, 특히 참여계수·betweenness에서 순열 검정을 통과할 것이다."
        ),
        method=(
            f"원본 400×400 이진 합의 행렬(Liu et al. 2023)을 그대로 사용({_HUMAN_SCRIPT}). 먼저 옛 그래프로 H1의 r=0.0501이 정확히 재현되는지 확인. "
            "질환 연루 수(0~6)를 연속변수로 두고 지표별 Spearman/Pearson, degree를 통제한 편상관, 그리고 '해부학적 라벨 단위 순열'(질환 매핑이 "
            "좌우를 합친 AAL 라벨 단위로 만들어져 이웃 영역이 같은 라벨을 공유 -- 영역 단위로 섞으면 p가 과소평가됨; 각 질환의 라벨을 같은 "
            "개수의 무작위 라벨로 교체, 5,000회) + Benjamini-Hochberg FDR."
        ),
        result_summary=(
            "부분 지지(방향은 맞으나 유의하지 않음). 옛 그래프 재현 r=0.0501 정확히 일치. 원본 전체 그래프에선 6개 지표가 모두 양의 상관으로 "
            "돌아섰다(Spearman +0.11~+0.18; 옛 그래프에선 closeness -0.15 등 부호가 섞임). 하지만 라벨 단위 순열+FDR을 통과한 지표는 없었다"
            "(최소 p=0.030 rich-club, q=0.18). 이유는 표본의 실제 독립 단위가 400개 영역이 아니라 약 75개 해부학적 라벨이라 귀무분포 폭이 "
            "넓기 때문(귀무 SD 0.07~0.16) -- 즉 이 교육용 매핑으론 검정력이 부족하다. 문헌(Crossley et al. 2014: 26개 질환 메타분석에서 병변이 "
            "허브에 집중)과 방향은 일치한다."
        ),
        verdict="inconclusive",
        evidence=[_EV_CROSSLEY, _EV_LIU],
        raw_data_note=(
            "Spearman(옛 그래프): degree +0.159(-0.029), betweenness +0.109(+0.070), closeness +0.177(-0.151), eigenvector +0.181(정의 불가), "
            "participation +0.115(전부 0), rich-club +0.165(-0.008). 라벨 순열 p: 0.176/0.144/0.106/0.258/0.354/0.030, FDR q 최소 0.18. "
            "degree 통제 편상관: betweenness -0.04, closeness +0.08, eigenvector +0.09, participation +0.08."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h1_2_per_disorder() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h1-2-per-disorder-hubness",
        title="H1-2 · '여러 질환 공통 영역'이 아니라 '질환마다' 보면 허브 편향이 보일까?",
        statement=(
            "검토 의견의 모델 B: 중심성은 질환 '개수'보다 특정 종류의 질환 취약성과 관련될 수 있다. 그렇다면 32개 질환을 하나씩 보면 "
            "복합(네트워크형) 질환의 영역은 허브 쪽, 일차 감각·운동 피질 중심의 국소 증후군은 비허브 쪽으로 치우칠 것이다."
        ),
        method=(
            "질환마다 해당 영역의 degree·betweenness·참여계수 평균(z)을 H1-1과 같은 라벨 단위 순열(질환별 2,000회) 분포와 비교해 효과크기"
            f"(귀무 SD 단위)와 p를 구하고, 32×3개 검정 전체에 FDR 적용({_HUMAN_SCRIPT})."
        ),
        result_summary=(
            "개별 질환 단위로는 FDR을 통과한 질환이 없지만, 패턴은 뚜렷했다: degree 효과 상위 8개 중 6개가 복합 질환(강박 +2.14, 주요우울 "
            "+2.02, PTSD +1.45, 자폐 +1.43, 조현병 +1.37, 이인증 +1.12), 일차 감각·운동 증후군(반신마비 -0.90, 반신감각소실 -1.04, 청각실인증 "
            "-1.48)은 음수. 예외는 알츠하이머(degree -1.53, 참여계수 +1.24) -- Crossley 2014에선 알츠하이머가 허브 집중이 유의한 9개 질환 중 "
            "하나였다는 점과 어긋나며, 이 프로젝트의 알츠하이머 매핑(교육용 라벨 큐레이션)이 실제 병변 지도와 다를 가능성을 시사한다. 패턴 "
            "자체의 검정은 H1-4."
        ),
        verdict="inconclusive",
        evidence=[_EV_CROSSLEY],
        raw_data_note=(
            "degree 효과(귀무 SD): OCD +2.14, MDD +2.02, 안와전두 증후군 +1.69, PTSD +1.45, ASD +1.43, 집행기능장애 +1.43, SCZ +1.37, 이인증 +1.12 ... "
            "반신마비 -0.90, 반신감각소실 -1.04, 청각실인증 -1.48, AD -1.53, 발린트 -1.91, 편측무시 -2.13. betweenness 최대: 이인증 +2.64, PTSD +2.53, "
            "미각상실 +2.44, MDD +2.29. 96개 검정 중 q<0.05 0개."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h1_3_receptor_model() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h1-3-receptor-plus-centrality-model",
        title="H1-3 · 중심성에 분자(수용체) 취약성을 더하면 질환 연루를 더 잘 설명할까?",
        statement=(
            "검토 의견의 모델 C와 Hansen et al. 2022(Nat Commun -- 13개 질환에서 신경전달물질 수용체 프로파일이 가장 좋은 예측변수)를 따라, "
            "중심성만 쓴 모델보다 실제 수용체 밀도 지도를 더한 모델이 질환 연루 수를 유의하게 더 설명할 것이다."
        ),
        method=(
            "Hansen et al. 2022(Nat Neurosci) 19종 수용체/수송체 PET 밀도(Schaefer-400, netneurolab/hansen_receptors)를 표준화해 PCA(PC1~3이 "
            "분산 41.8/15.9/14.4%). 모델 M1 중심성(degree+betweenness), M2 +참여계수, M3 M1+수용체 PC1~3, M4 전부, M5 수용체만 -- 각각의 R²와 "
            f"M1→M3 증분 ΔR²를 H1-1과 같은 라벨 단위 순열로 검정({_HUMAN_SCRIPT})."
        ),
        result_summary=(
            "방향은 지지, 통계적으론 미확인. 수용체를 더하면 R²가 0.036→0.111(ΔR²=0.075)로 3배, 수용체만으로도 0.099로 중심성(0.036)보다 높았다 "
            "-- Hansen 2022의 '국소 분자 특성이 더 강한 예측변수'와 같은 방향. 하지만 라벨 단위 순열에서 ΔR²의 p=0.27로 유의하지 않았다(귀무 "
            "ΔR² 평균도 약 0.06으로 커서 -- 같은 검정력 문제). PC1은 mGluR5·5-HT6·D1·D2·MOR·CB1 등이 함께 실린 '전반적 수용체 밀도' 축."
        ),
        verdict="inconclusive",
        evidence=[
            _EV_HANSEN_NC,
            HypothesisEvidenceOut(
                title="Hansen et al. 2022 -- Mapping neurotransmitter systems to the structural and functional organization of the human neocortex (Nat Neurosci 25:1569), data: netneurolab/hansen_receptors",
                url="https://github.com/netneurolab/hansen_receptors",
            ),
        ],
        raw_data_note="R²(순열 p): M1 0.036(0.21), M2 0.050(0.26), M3 0.111(0.23), M4 0.114(0.27), M5 0.099(0.15). ΔR²(M1→M3)=0.075, p=0.27.",
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h1_4_complex_vs_focal() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h1-4-complex-vs-focal-disorders",
        title="H1-4 · 질환을 단위로 보면, 복합 질환은 국소 증후군보다 실제로 더 허브에 있을까?",
        statement=(
            "H1-2에서 보인 패턴이 우연이 아니라면, 질환 하나를 표본 하나로 두고(복합 7 vs 국소 25) 비교했을 때 복합 질환의 허브 효과크기가 "
            "유의하게 클 것이다 -- 즉 '질환 수'가 아니라 '질환 종류'가 허브성과 관련된다."
        ),
        method=(
            f"H1-2의 질환별 효과크기(구조 degree·betweenness·참여계수, 기능 연결 강도)를 두 범주로 나눠 Mann-Whitney 검정 + 범주 라벨 순열(20,000회)({_HUMAN_SCRIPT} --extra)."
        ),
        result_summary=(
            "지지됨. 복합 질환의 구조적 허브 효과가 국소 증후군보다 유의하게 컸다: degree +1.16 vs +0.05(순열 p=0.020, Mann-Whitney p=0.006), "
            "betweenness +1.31 vs -0.03(p=0.001), 참여계수 +0.94 vs -0.06(p=0.021). H1의 원래 가설('많은 질환에 걸린 영역 = 허브')은 약했지만, "
            "'네트워크형 복합 질환이 허브를 표적으로 한다'는 형태로 바꾸면 이 데이터에서도 지지된다(Crossley et al. 2014와 같은 방향). 단, 질환 "
            "범주 자체가 이 프로젝트의 큐레이션(국소=고전적 병변-증상, 복합=정신·신경퇴행 질환)이라는 한계가 있다."
        ),
        verdict="supported",
        evidence=[_EV_CROSSLEY],
        raw_data_note="복합/국소 평균 효과(순열 p): degree 1.159/0.047(0.020), betweenness 1.313/-0.030(0.0012), participation 0.937/-0.063(0.021), 기능연결 강도 -1.423/0.072(0.021).",
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h1_5_alzheimer_functional_hubs() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h1-5-alzheimer-functional-hubs",
        title="H1-5 · 알츠하이머 영역은 구조 허브는 아니어도 '기능' 허브일까?",
        statement=(
            "H1-2에서 알츠하이머 영역만 구조 degree가 낮았다(-1.53). Buckner et al. 2009는 알츠하이머 아밀로이드 침착이 '기능 연결' 허브(후대상·"
            "외측 두정·외측 측두·전전두)와 겹친다고 보고했다. 그렇다면 같은 400개 영역의 기능 연결 행렬로 보면 알츠하이머 영역은 기능 허브 쪽으로 "
            "유의하게 치우칠 것이다."
        ),
        method=(
            "같은 저장소의 HCP 합의 기능 연결 행렬(fc_cons_400)에서 양의 기능 연결 강도를 영역별 기능 허브 지표로 삼아 H1-2와 같은 라벨 단위 순열"
            f"(4,000회)로 검정({_HUMAN_SCRIPT} --extra). 사후(탐색적)로 Buckner의 '서로 다른 시스템을 잇는 허브' 정의에 가깝게 네트워크 '간' 기능 연결 강도도 계산."
        ),
        result_summary=(
            "기각. 알츠하이머 영역의 기능 연결 강도 효과는 +0.15(p=0.88). 오히려 이 지표는 일차 시각·감각운동 영역에서 가장 높았고(네트워크 내부의 "
            "강한 상관을 반영), 복합 질환 전체는 음수(-1.42), 질환 단위로 구조 degree와 기능 강도는 역상관(ρ=-0.64)이었다. 사후 탐색(네트워크 간 "
            "기능 연결)에서도 알츠하이머 +0.55(p=0.56)이고, 이 데이터의 상위 20개 네트워크 간 기능 허브는 시각 8·배측주의 6·현저성 4·기본모드 1개로 "
            "Buckner의 기본모드 중심 허브 지도와 크게 달랐다. 교훈: '어떤 허브 지도(구조/기능, 지표 정의, 전처리)'를 쓰느냐가 결론을 뒤집는다 -- "
            "알츠하이머-허브 관계를 이 데이터로 판단하려면 Buckner와 같은 방식의 허브 정의가 먼저 필요하다."
        ),
        verdict="not_supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Buckner et al. 2009 -- Cortical hubs revealed by intrinsic functional connectivity: relation to Alzheimer's disease (J Neurosci 29:1860)",
                url="https://www.jneurosci.org/content/29/6/1860",
            ),
            HypothesisEvidenceOut(
                title="Zhou, Gennatas, Kramer, Miller & Seeley 2012 -- Predicting regional neurodegeneration from the healthy brain functional connectome (Neuron 73:1216)",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC3361461/",
            ),
        ],
        raw_data_note="AD 효과(p): 구조 degree -1.52(0.13), betweenness -0.24(0.82), 참여계수 +1.25(0.21), 기능 강도 +0.15(0.88), 네트워크 간 기능 강도 +0.55(0.56, 사후).",
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h2_1_all_neuron_silencing() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h2-1-all-neuron-silencing-vs-centrality",
        title="H2-1 · 3개가 아니라 302개 뉴런 전부를 절제하면, 중심성은 기능적 중요성을 얼마나 예측할까?",
        statement=(
            "H2는 손으로 고른 3개(DVA/RIPL/RIPR) 중 1개만 효과가 있었다. 검토 의견대로 '중심성은 후보 탐색용 사전정보이지 충분조건은 아니다'가 "
            "맞다면, 302개 뉴런을 하나씩 절제했을 때 중심성과 기능 영향 사이에 약~중간 정도의 양의 상관이 있고, 상위 중심 뉴런 다수는 영향이 없을 것이다."
        ),
        method=(
            f"가상 웜 폐루프의 현재 네트워크(수용체 기반 부호+실제 극성)에서 뉴런마다 출력 시냅스를 막고(가상 실험실과 같은 절제 방식) 폐루프가 실제로 "
            f"쓰는 두 자극(내리막 OFF: AWC·ASER / 오르막 ON: ASEL, f=0.3)에서 AVA·AVB 반응 변화를 측정({_LOOP_SCRIPT} worm-silence-all, 7개 프로세스). "
            "중심성은 H2가 후보를 고른 연구소 위상 도구와 같은 방식(degree·betweenness·PageRank 정규화 평균). 측정 대상(AVA/AVB)과 직접 자극받는 "
            "감각뉴런(AWC/ASE) 8개는 순환 논리라 제외하고 재분석."
        ),
        result_summary=(
            "지지됨. 294개 중 16개만 결정 회로에 영향이 있었고, 중심성과 영향은 약한 양의 상관(Spearman ρ=0.26, p=4×10⁻⁶; degree 0.29). 중심성 상위 "
            "30개에서 영향 있는 뉴런 비율은 27%로 나머지(3%)의 약 12배(Fisher p=3×10⁻⁵) -- 사전정보로는 강력하다. 하지만 상위 30개 중 22개는 영향 0이고, "
            "DVA(6위)·RIPR(8위)·RIPL(9위)도 이 과제에선 영향 0. 가장 큰 영향은 중간 순위의 AIBL(32위)·AIBR(22위)·RIMR(39위)·RIML(41위) -- 실제 문헌이 "
            "반전·방향전환 회로로 지목한 뉴런이다(Gray, Hill & Bargmann 2005: AIB가 반전·오메가 회전을 유발). DVA가 H2의 이동 명령 과제에선 효과가 있었고 여기선 "
            "없다는 건, 기능적 중요성이 '과제 의존적'임을 보여준다(실제 DVA는 몸 신장을 감지하는 고유수용 뉴런)."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Gray, Hill & Bargmann 2005 -- A circuit for navigation in Caenorhabditis elegans (PNAS 102:3184)",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC546636/",
            ),
            HypothesisEvidenceOut(
                title="Li et al. 2006 -- A C. elegans stretch receptor neuron revealed by a mechanosensitive TRP channel homologue (Nature 440:684)",
                url="https://pmc.ncbi.nlm.nih.gov/articles/PMC2865900/",
            ),
        ],
        raw_data_note=(
            "기준 반응: 내리막 AVA10/AVB8, 오르막 AVA6/AVB6. 영향(|ΔAVA|+|ΔAVB| 합) 상위: AIBL 22(32위), AIBR 12(22위), RIML 10(41위), RIMR 8(39위), "
            "PVCL 6(10위), PVCR 5(5위), SAADR·SAAVR 4, AVDL·AVDR·SAAVL 3, RIBR 2, RIBL·ADAR·AIAR·VB1 1. 제외 전 전체 302개: 영향 24개, 결정 뒤집힘 13개, ρ=0.28."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h2_2_closed_loop_silencing() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h2-2-closed-loop-silencing",
        title="H2-2 · 폐루프에서 '영향 큰 중간 허브'와 '영향 없는 최상위 허브'를 끄면 행동은 어떻게 달라질까?",
        statement=(
            "H2-1이 옳다면, 실제로 움직이는 폐루프에서 AIB를 끄면 반전이 사라져 화학주성이 무너지고(Gray 2005의 AIB 역할), 중심성 최상위지만 영향이 "
            "없던 DVA+RIPL+RIPR을 끄면 행동이 전혀 달라지지 않을 것이다."
        ),
        method=(
            f"광원에서 30mm, 무작위 방향, 200틱 폐루프 에피소드 7개씩을 같은 시드로: 온전 / AIBL+AIBR 절제 / RIML+RIMR 절제 / DVA+RIPL+RIPR 절제"
            f"({_LOOP_SCRIPT} worm-episodes plan=cur@30,silence:...)."
        ),
        result_summary=(
            "지지됨(예측 정확히 적중). AIB 절제: 반전 0회, 순이동 -0.18mm(4/7) -- 궤적이 docs/46에서 감각을 통째로 끈 대조군과 소수점까지 동일해, AIB 두 "
            "개만 꺼도 '냄새를 못 맡는' 것과 행동상 같아졌다. RIM 절제: 반전이 3.3→1.1회로 줄고 순이동 +2.88mm로 약화(오르막 오반전은 0). "
            "DVA+RIPL+RIPR 절제: 7개 모두 온전한 웜과 궤적이 비트 단위로 동일 -- 위상적 최상위 허브여도 이 행동에는 아무 역할이 없다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Gray, Hill & Bargmann 2005 -- AIB interneurons trigger reversals and omega turns (PNAS 102:3184)",
                url="https://www.pnas.org/doi/10.1073/pnas.0409009101",
            ),
        ],
        raw_data_note=(
            "순이동(mm): 온전 [4.69,4.39,1.05,-1.01,5.22,5.73,5.65] / AIB [4.69,-4.65,1.05,-5.91,-5.90,3.79,5.65] / RIM [4.69,4.56,1.05,1.04,-0.60,3.79,5.65] / "
            "DVA+RIP = 온전과 동일. 반전 평균 3.3 / 0.0 / 1.1 / 3.3."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h2_3_avb_balance_counterfactual() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h2-3-avb-input-balance-counterfactual",
        title="H2-3 · 반전 편향의 원인이 '입력 불균형'이라면, 그걸 맞추면 실제처럼 자극마다 다른 방향이 나올까?",
        statement=(
            "docs/47은 AVA가 AVB보다 약 2배의 입력을 받아 어떤 자극이든 반전 쪽으로 기운다고 봤다. 이게 원인이라면 AVB로 들어오는 시냅스만 약 2배로 "
            "키웠을 때 (1) 실제로 전진을 촉진하는 AWA·ASEL 자극이 전진 쪽으로 돌아서고, (2) 폐루프에 필요한 '농도 감소(OFF) → 반전'은 유지될 것이다."
        ),
        method=(
            f"현재 폐루프 네트워크에서 AVB로 들어오는 화학·전기 시냅스 가중치만 k=1~3배로 조정(반사실적 조작, 실제 생물 수치 아님)하고, 알려진 입력"
            f"(ASEL, AWA, ASH, PLM, ALM)과 폐루프의 내리막/오르막 자극에서 AVA/AVB 결정을 측정({_LOOP_SCRIPT} worm-avb-balance)."
        ),
        result_summary=(
            "절반만 지지. (1)은 맞았다: k=2에서 ASEL·AWA가 전진 쪽(AVB>AVA)으로 돌아서 -- 구조적 입력 불균형이 반전 편향의 원인임이 확인됐다. 하지만 "
            "(2)는 깨졌다: 같은 k=2에서 실제로는 후진을 일으키는 유해 자극(ASH)도 전진이 되고, 내리막(OFF) 자극도 반전을 못 일으켜 화학주성에 필요한 "
            "신호가 사라졌다. 어떤 k에서도 'AWA는 전진, ASH는 후진'이 동시에 나오지 않았다 -- 이 모델의 전진/후진 결정은 자극 종류를 가리지 않는 '전체 흥분 "
            "균형 판독기'이고, 자극별 선택성은 모델에 없는 기전(명령층 상호 억제, 등급 전위, 신경조절)이 필요하다는 뜻이다."
        ),
        verdict="inconclusive",
        evidence=[
            HypothesisEvidenceOut(
                title="Chalfie et al. 1985 -- The neural circuit for touch sensitivity in C. elegans (J Neurosci 5:956)",
                url="https://www.jneurosci.org/content/5/4/956",
            ),
        ],
        raw_data_note=(
            "f=1.0 AVA/AVB -- k=1: ASEL 10/8, AWA 17/12, ASH 16/12, 내리막 13/10(반전) · k=1.5: ASEL 11/11, AWA 18/17, 내리막 15/15(직진) · "
            "k=2: ASEL 13/15, AWA 19/21, ASH 20/21, 내리막 17/20(직진) · k=3: 전부 전진. PLM은 모든 k에서 0/0."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h3_1_positional_candidates_specificity() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h3-1-positional-candidate-specificity",
        title="H3-1 · 염색체상 '가까운 유전자'는 무작위 유전자보다 실제로 기능적으로 더 연관돼 있을까?",
        statement=(
            "검토 의견: 게놈상 근접성 ≠ 기능적 관계. 이를 H3의 방법 자체에 대한 검증으로 바꾸면 -- 연구소 유전자 도구가 내놓는 위치 후보(6개 시드 × 8개)는 "
            "독립적인 기능 연관 데이터베이스(STRING)에서 같은 신경계 유전자 목록의 무작위 유전자보다 시드와 더 자주 연관되지 '않을' 것이다. 그리고 H3에서 찾은 "
            "BDNF-SLC1A2 관계는 위치가 아니라 문헌에서 온 것일 것이다."
        ),
        method=(
            "시드 6개(BDNF, CREB1, NTRK2, GRIN2B, CAMK2A, ARC) × 위치 후보 8개 = 48쌍의 STRING v12 연관 점수를 공개 API로 조회. 연관 기준은 중간 신뢰도 0.4 "
            "이상, 전체 점수와 '텍스트마이닝 제외(실험+데이터베이스+공발현)' 점수를 따로 봄. 귀무: 같은 646개 신경계 유전자에서 무작위 8개(20,000회)"
            "(backend/scripts/gene_positional_hypothesis.py)."
        ),
        result_summary=(
            "예측대로(위치 → 기능 추론은 지지되지 않음). 48쌍 중 연관 4쌍, 무작위 기대 4.9쌍(p=0.74) -- 위치 후보가 무작위보다 나을 게 없다. 텍스트마이닝을 "
            "빼면 0/48(기대 0.8). BDNF-SLC1A2 점수 0.619는 100% 텍스트마이닝(문헌 공출현)에서 나왔고 실험·데이터베이스·공발현 근거는 0 -- 즉 H3의 'SLC1A2는 "
            "BDNF와 관련된다'는 발견은 위치 방법 덕이 아니라 문헌(Rodriguez-Kern et al. 2003: BDNF가 NF-κB 경로로 아교세포 GLT-1/EAAT2 발현을 높임)이 뒷받침한 "
            "우연한 적중이다. 또 BDNF는 워낙 유명한 유전자라 무작위 유전자의 16%와도 텍스트 연관이 있어 '문헌 연관'의 기준선 자체가 높다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Rodriguez-Kern et al. 2003 -- Beta-amyloid and BDNF up-regulate GLT-1/EAAT2 via different pathways utilizing NF-kappaB (Neurochem Int 43:363)",
                url="https://pubmed.ncbi.nlm.nih.gov/12742080/",
            ),
            HypothesisEvidenceOut(
                title="STRING database (functional protein association networks) -- API",
                url="https://string-db.org/",
            ),
        ],
        raw_data_note=(
            "시드별 연관 비율(전체 점수≥0.4, 기준선): BDNF 2/8(16.1%, p=0.38; PAX6 0.616, SLC1A2 0.619), CREB1 1/8(8.3%; FN1 0.624), NTRK2 1/8(12.1%; GABBR2 0.512), "
            "GRIN2B 0/8, CAMK2A 0/8, ARC 0/8. 합산 4/48 vs 기대 4.89(p=0.74); 텍스트마이닝 제외 0/48 vs 0.79."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


# ---------------------------------------------------------------------------
# docs/50 -- 손상 후 네트워크 재조직-취약성 가설(사용자 가설). 복구된 인간 거시 커넥톰(docs/49, 5,059개 간선) 위에서
# 25개 국소 증후군 병변 → 생존 영역이 잃은 연결을 배선 길이 제한 안에서 다시 잇는 재조직 전략 비교.
# 실제 뇌에서 '질환 가능성'을 직접 잴 수는 없으므로 대리 지표(부하 집중, 2차 타격 손실, 연쇄 과부하 생존, 정상 범위 이탈)로 검증.
# backend/scripts/reorganization_hypotheses.py (기본 실행: R1~R5, --r6: 정상 용량 기준 분배).
# ---------------------------------------------------------------------------

_REORG_SCRIPT = "backend/scripts/reorganization_hypotheses.py"

_EV_ALSTOTT = HypothesisEvidenceOut(
    title="Alstott, Breakspear, Hagmann, Cammoun & Sporns 2009 -- Modeling the impact of lesions in the human brain (PLOS Comput Biol 5:e1000408)",
    url="https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1000408",
)
_EV_SCHLEMM = HypothesisEvidenceOut(
    title="Schlemm et al. 2020 -- Structural brain networks and functional motor outcome after stroke: a prospective cohort study (Brain Commun 2:fcaa001)",
    url="https://academic.oup.com/braincomms/article/2/1/fcaa001/5699899",
)
_EV_MOTTER_LAI = HypothesisEvidenceOut(
    title="Motter & Lai 2002 -- Cascade-based attacks on complex networks (Phys Rev E 66:065102)",
    url="https://link.aps.org/doi/10.1103/PhysRevE.66.065102",
)
_EV_GRIFFIS = HypothesisEvidenceOut(
    title="Griffis, Metcalf, Corbetta & Shulman 2019 -- Structural disconnections explain brain network dysfunction after stroke (Cell Rep 28:2527)",
    url="https://doi.org/10.1016/j.celrep.2019.07.100",
)
_EV_REHAB_REVIEW = HypothesisEvidenceOut(
    title="Reconnecting brain networks after stroke: a scoping review of conventional, neuromodulatory, and feedback-driven rehabilitation approaches",
    url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12651463/",
)

_REORG_METHOD_COMMON = (
    "복구된 인간 거시 구조 커넥톰(Schaefer-400, 5,059개 간선)에서 질환 매핑의 국소 증후군 25개 영역 집합을 병변으로 제거. 생존 영역은 병변 때문에 잃은 "
    "연결 수만큼 새 연결을 만들되, 정상 간선 길이의 75백분위(67.3mm) 이내 영역에만 연결(배선 비용 제한). 전략: 없음 / 무작위 / 국소(가장 가까운 영역) / "
    "집중(가장 degree 높은 허브) / 분산(현재 부하=betweenness가 가장 낮은 영역). 지표: 전역·국소 효율, 부하 Gini·최대 점유율, 모듈성(Yeo-7), "
    "2차 타격(부하 상위 5% 영역 제거) 효율 손실, Motter-Lai 연쇄 과부하 생존율(용량 = 정상 뇌 부하 × 1.2). 병변 25개에 대한 쌍대 Wilcoxon."
)


def _h16_equal_hub_distribution_after_lesion() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-equal-hub-distribution-after-lesion",
        title="H16 · 손상 후 가소성 단계에서 허브를 균등하게 분배하면, 향후 질환 위험을 정상 뇌 수준까지 낮출 수 있을까?",
        statement=(
            "(사용자 가설) 뇌 병변 후 재조직 때 네트워크 허브(부하)를 균등하게 분배하면, 부담이 한 곳에 쏠리지 않아 추후 질환 가능성을 정상 뇌 범위 "
            "수준까지 충분히 낮출 수 있다. 외부 글의 '네트워크 재조직-취약성 가설'(병변 → 분산/집중 재조직 → 부담 분배·회복탄력성 → 기능 예후 → 장기 위험)과 같은 틀."
        ),
        method=(
            f"{_REORG_METHOD_COMMON} '질환 가능성'은 직접 잴 수 없어 2차 타격 손실·연쇄 과부하 생존율·정상 범위 이탈을 대리 지표로 썼다. 가설을 두 형태로 "
            f"검증: (a) 문자 그대로의 '균등' = 부하가 가장 낮은 곳에 연결(분산), (b) '정상 뇌 범위 수준으로' = 각 영역의 정상 용량 대비 여유가 가장 큰 곳에 "
            f"연결(headroom, H16-5)({_REORG_SCRIPT}, --r6)."
        ),
        result_summary=(
            "혼재 -- 형태에 따라 결론이 갈린다. (a) 문자 그대로 '균등하게'는 기각: 부하 쏠림·2차 타격 취약성은 허브 집중보다 확실히 낮췄지만(H16-3·H16-4), "
            "네트워크를 모든 전략 중 정상에서 가장 멀리 밀어냈고(정상 이탈 0.345, 재조직 없음 0.057) 연쇄 과부하 생존율도 재조직 없음보다 나빴다(0.71 vs 0.91). "
            "평평하게 만드는 것 자체가 정상이 아니다 -- 정상 뇌도 부하 Gini 0.555로 꽤 불균등하다. (b) '각 영역을 자기 정상 용량 안에서' 분배하면 지지에 가깝다: "
            "연쇄 생존 0.895로 재조직 전략 중 최고이자 재조직 없음(0.906)과 통계적으로 구별되지 않으면서(p=0.07), 효율은 회복하고(0.4435 > 정상 0.431) 2차 타격 "
            "손실은 정상보다 작았다(0.047 vs 0.051). 다만 어떤 전략도 정상 뇌의 연쇄 생존(1.0)에 도달하진 못했다. 결론: '균등'이 아니라 '정상 용량을 넘지 "
            "않게' 분배하는 것이 이 모델에서 취약성을 낮춘다. 실제 환자의 질환 발생으로 이어지는지는 종단 코호트 자료가 있어야 검증할 수 있다."
        ),
        verdict="inconclusive",
        evidence=[_EV_SCHLEMM, _EV_MOTTER_LAI, _EV_ALSTOTT, _EV_GRIFFIS, _EV_REHAB_REVIEW],
        raw_data_note=(
            "정상 뇌: 전역 효율 0.431, 부하 Gini 0.555, 2차 타격 손실 0.051, 연쇄 생존 1.0. 전략별 연쇄 생존 / 정상 이탈: 없음 0.906/0.057, 국소 0.854/0.081, "
            "집중 0.492/0.224, 무작위 0.744/0.268, 분산 0.710/0.345, headroom 0.895/0.133. 문헌 확인: Griffis 2019는 Nature가 아니라 Cell Reports."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h16_1_lesion_hubness_not_size() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-1-lesion-hubness-not-size",
        title="H16-1 · 병변의 영향은 크기보다 '어디가' 손상됐는지(허브성)가 더 크게 좌우할까?",
        statement=(
            "재조직을 하기 전, 병변 직후 네트워크 효율 손실은 병변 크기(영역 수)보다 병변 영역의 허브성(평균 degree)과 더 강하게 관련될 것이다 "
            "(Alstott 2009의 '위치 민감성', Schlemm 2020의 '병변 부피와 독립적인 네트워크 변화')."
        ),
        method=f"{_REORG_METHOD_COMMON} 이 기록은 재조직 없음 상태의 전역 효율 손실만 사용({_REORG_SCRIPT}).",
        result_summary=(
            "지지됨. 효율 손실과 병변 크기의 상관은 사실상 0(Spearman ρ=0.01, p=0.97, 1~69개 영역), 병변 허브성과는 강한 양의 상관(ρ=0.69, p=1.3×10⁻⁴; "
            "크기를 통제한 편상관 0.71). 가장 큰 손실은 가장 큰 병변(편측마비 무인지, 69개)이었지만, 2위 미각상실(18개)·3위 실행기능 장애(38개)가 "
            "더 큰 병변들을 앞섰다 -- 모두 평균 degree 25~33의 허브성 병변. 같은 크기 무작위 병변과 비교하면 국소 증후군 병변의 평균 손실은 오히려 약간 "
            "작았다(0.00128 vs 0.00153): 이 질환 매핑의 국소 증후군이 특별히 허브를 겨냥하진 않는다(H1-4의 '국소 증후군은 비허브'와 일치)."
        ),
        verdict="supported",
        evidence=[_EV_ALSTOTT, _EV_SCHLEMM],
        raw_data_note=(
            "정상 전역 효율 0.4310. 손실 상위: 편측마비 무인지(69개, degree 25.3) 0.0112, 미각상실(18, 30.3) 0.0094, 실행기능 장애(38, 32.8) 0.0076, "
            "안와전두 증후군(23, 30.7) 0.0029. 무작위 동일 크기 병변 평균 손실 0.00153, 부하 Gini 0.5534(국소 0.5539)."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h16_2_concentrated_recovers_efficiency() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-2-concentrated-recovers-efficiency",
        title="H16-2 · 잃은 연결을 기존 허브에 몰아주면(집중 재조직) 단기 효율 회복이 더 빠를까?",
        statement=(
            "집중 재조직(가장 연결 많은 허브에 새 연결을 붙임)은 경로를 허브로 모아 전역 효율을 분산 재조직보다 더 많이 회복시킬 것이다 -- "
            "'단기 기능 회복에는 유리하지만 부담이 쏠린다'는 사용자 가설의 전반부."
        ),
        method=f"{_REORG_METHOD_COMMON} 집중 vs 분산의 전역 효율 비교({_REORG_SCRIPT}).",
        result_summary=(
            "기각. 두 전략 모두 전역 효율을 정상 이상으로 회복시켰지만(집중 0.4507, 분산 0.4488, 정상 0.4310, 재조직 없음 0.4297), 차이는 유의하지 "
            "않았다(평균 차 0.0019, 분산이 13/25 병변에서 더 높음, p=0.33). 배선 길이 제한 안에서는 '허브로 모으기'가 효율에서 얻는 이점이 거의 없다. "
            "즉 이 모델에선 집중 재조직이 '효율을 사고 취약성을 파는' 거래조차 성립하지 않고, 취약성만 늘린다(H16-3·H16-4)."
        ),
        verdict="not_supported",
        evidence=[_EV_GRIFFIS],
        raw_data_note="전역 효율 평균: 없음 0.4297, 무작위 0.4497, 국소 0.4385, 집중 0.4507, 분산 0.4488. 분산-집중 쌍대 차 -0.0019(p=0.33).",
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h16_3_distributed_evens_load() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-3-distributed-evens-load",
        title="H16-3 · 분산 재조직은 네트워크 부하(부담)를 더 고르게 나눌까?",
        statement="분산 재조직은 집중 재조직보다 영역 간 부하(betweenness) 불균등(Gini)과 한 영역의 최대 부하 점유율을 낮출 것이다.",
        method=f"{_REORG_METHOD_COMMON} 부하 Gini·최대 점유율 비교({_REORG_SCRIPT}).",
        result_summary=(
            "지지됨(25/25 병변). 부하 Gini: 분산 0.460 vs 집중 0.616(p=6×10⁻⁸), 최대 점유율 0.030 vs 0.057(p=1×10⁻⁷). 집중 재조직은 정상 뇌(Gini 0.555, "
            "최대 0.037)보다도 부하를 더 쏠리게 만들었고, 분산 재조직은 정상보다 더 평평하게 만들었다. 다만 '고르게'가 공짜는 아니었다 -- 분산은 국소 효율을 "
            "0.707→0.652로 떨어뜨렸다(25/25, p=6×10⁻⁸; 정상 0.700): 이웃끼리 서로 연결된 국소 중복 경로가 줄어든 것."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note="부하 Gini(최대 점유율): 정상 0.555(0.037), 없음 0.554(0.036), 무작위 0.495(0.030), 국소 0.543(0.035), 집중 0.616(0.057), 분산 0.460(0.030). 국소 효율: 집중 0.7066, 분산 0.6519.",
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h16_4_distributed_resists_second_hit() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-4-distributed-resists-second-hit",
        title="H16-4 · 부하를 고르게 나눈 네트워크는 두 번째 손상과 연쇄 과부하에 더 강할까?",
        statement=(
            "'향후 질환 가능성'을 직접 잴 수 없으므로 대리 지표로 -- 분산 재조직 네트워크는 집중 재조직보다 (1) 부하 상위 영역이 추가로 손상될 때 효율 "
            "손실이 작고, (2) 정상 용량을 넘는 과부하가 번지는 연쇄 붕괴(Motter & Lai 2002)에서 더 많은 영역이 살아남을 것이다."
        ),
        method=f"{_REORG_METHOD_COMMON} 2차 타격 손실·연쇄 생존율 비교({_REORG_SCRIPT}).",
        result_summary=(
            "집중 재조직과 비교하면 지지됨. 2차 타격 효율 손실: 분산 0.041 vs 집중 0.081(25/25, p=6×10⁻⁸), 연쇄 생존율 0.710 vs 0.492(23/25, "
            "p=4×10⁻⁷). 그러나 중요한 단서: 연쇄 생존율이 가장 높은 건 어떤 재조직 전략도 아닌 '재조직 없음'(0.906)이었고 다음이 국소 재조직(0.854)이었다. "
            "새 연결은 부하 경로를 바꿔 원래 적게 쓰이던(=용량이 작은) 영역에 정상 용량을 넘는 부하를 보낸다 -- 분산 전략은 '현재 부하가 낮은 곳'을 "
            "고르므로 바로 그 용량이 작은 영역에 연결을 몰아준다. 이 설명은 H16-5에서 확인됐다(용량 대비로 고르면 연쇄 생존이 0.71→0.895)."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI, _EV_ALSTOTT],
        raw_data_note="2차 타격 효율 손실: 정상 0.0509, 없음 0.0524, 무작위 0.0411, 국소 0.0496, 집중 0.0805, 분산 0.0409. 연쇄 생존율(정상 1.0): 없음 0.906, 무작위 0.744, 국소 0.854, 집중 0.492, 분산 0.710.",
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def _h16_5_capacity_aware_distribution() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-5-capacity-aware-distribution",
        title="H16-5 · '균등하게'가 아니라 '각 영역의 정상 용량 안에서' 나누면 연쇄 과부하를 피할 수 있을까?",
        statement=(
            "H16-4의 설명이 맞다면, 새 연결을 '현재 부하 / 정상 용량'이 가장 낮은 영역(여유가 가장 큰 곳)에 붙이는 headroom 전략은 재조직 전략 중 연쇄 "
            "과부하 생존율이 가장 높고, 효율 회복은 다른 재조직 전략과 비슷할 것이다 -- 사용자 가설의 '정상 뇌 범위 수준으로'를 그대로 옮긴 형태."
        ),
        method=(
            f"{_REORG_METHOD_COMMON} headroom: (현재 betweenness+1)/(정상 용량+1)이 최소인 후보에 연결, 10개마다 부하 재계산. 나머지 전략은 기본 실행 결과를 "
            f"재사용(같은 시드라 결정적)({_REORG_SCRIPT} --r6)."
        ),
        result_summary=(
            "대체로 지지(연쇄 예측 적중, 효율 예측은 부분). 연쇄 생존 0.895로 재조직 전략 중 최고 -- 분산 0.710(25/25, p=6×10⁻⁸), 국소 0.854(22/25, p=4×10⁻⁵), "
            "집중 0.492(25/25)보다 높고, 재조직 없음 0.906과는 유의차 없음(p=0.07). 정상 이탈도 분산(0.345)·집중(0.224)보다 25/25 병변에서 작았다(0.133). "
            "그러나 효율 회복은 '비슷하다'까진 아니었다: 0.4435로 분산(0.4488)·집중(0.4507)보다 25/25 낮고 국소(0.4385)보다는 25/25 높다 -- 분산이 얻은 효율 "
            "개선의 약 72%. 즉 효율 일부를 양보하고 취약성을 크게 줄이는 절충점이다. 재조직 없음·국소보다는 여전히 정상에서 멀다(국소 효율 0.687 vs 정상 0.700)."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "headroom: 전역 효율 0.4435, 부하 Gini 0.531, 국소 효율 0.6866, 2차 타격 손실 0.0466, 연쇄 생존 0.895, 정상 이탈 0.133. 쌍대 비교(headroom이 높은 병변 수/25, p): "
            "연쇄 vs 분산 25(6×10⁻⁸), vs 국소 22(4×10⁻⁵), vs 없음 4(0.065); 전역 효율 vs 분산 0(6×10⁻⁸), vs 국소 25(6×10⁻⁸)."
        ),
        executed_at=_FOLLOWUP_EXECUTED_AT,
        is_live_computed=False,
    )


def build_hypothesis_notebook() -> list[HypothesisRecordOut]:
    # 후속 가설(docs/48)은 부모 가설 바로 아래에 둔다(H1 → H1-1~H1-5, H2 → H2-1~H2-3, H3 → H3-1).
    return [
        _compute_h1_disease_hub_correlation(),
        _h1_1_full_graph_reanalysis(),
        _h1_2_per_disorder(),
        _h1_3_receptor_model(),
        _h1_4_complex_vs_focal(),
        _h1_5_alzheimer_functional_hubs(),
        _h2_dva_hub(),
        _h2_1_all_neuron_silencing(),
        _h2_2_closed_loop_silencing(),
        _h2_3_avb_balance_counterfactual(),
        _h3_slc1a2_bdnf(),
        _h3_1_positional_candidates_specificity(),
        _h4_frontal_sup_medial(),
        _h5_small_world_cross_species(),
        _h6_connector_hub_cross_species(),
        _h7_worm_blind_zone(),
        _h8_worm_ase_asymmetry(),
        _h9_worm_klinokinesis_efficiency(),
        _h10_worm_correct_polarity_breaks_chemotaxis(),
        _h11_fly_avoidance_sphere(),
        _h12_fly_leaky_exclusion(),
        _h13_worm_receptor_signs(),
        _h14_worm_new_start(),
        _h15_fly_directed_avoidance(),
        # docs/50: 손상 후 재조직-취약성(사용자 가설)과 후속 H16-1~H16-5
        _h16_equal_hub_distribution_after_lesion(),
        _h16_1_lesion_hubness_not_size(),
        _h16_2_concentrated_recovers_efficiency(),
        _h16_3_distributed_evens_load(),
        _h16_4_distributed_resists_second_hit(),
        _h16_5_capacity_aware_distribution(),
    ]
