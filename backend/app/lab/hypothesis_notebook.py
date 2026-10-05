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


def _h16_1_1_hubness_robustness() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-1-1-hubness-effect-robustness",
        title="H16-1-1 · '허브성이 크기보다 중요하다'는 상관(ρ=0.69)은 통계적으로 얼마나 튼튼할까?",
        statement=(
            "(외부 검토 의견) 25개 병변의 상관 하나로는 부족하다. Pearson·Spearman, bootstrap 95% 신뢰구간, 순열검정, 크기+허브성 동시 회귀를 모두 "
            "통과해야 '크기가 커서가 아니라 위상적으로 중요한 위치가 손상돼서 네트워크 영향이 크다'고 말할 수 있다. 예측: 모두 통과하지만, 가장 큰 "
            "병변(69개 영역)에 좌우되는지와 '잘린 연결 수'와의 관계는 따로 봐야 한다."
        ),
        method=(
            "H16-1과 같은 국소 병변 25개의 재조직 없음 전역 효율 손실. ① Pearson ② Spearman ③ bootstrap 10,000회 ④ 병변-허브성 짝 뒤섞기 순열 20,000회 "
            "⑤ 표준화 회귀(허브성+크기, 허브성+log 크기, 순위 회귀). 추가: ⑥ 같은 크기 무작위 병변 5,000개 생성적 귀무 ⑦ 병변 하나씩 빼기 ⑧ 잘린 간선 수 통제 "
            "⑨ 병변 간 영역 중복(backend/scripts/lesion_hubness_robustness.py)."
        ),
        result_summary=(
            "대체로 지지, 두 가지 단서. 통과: Pearson r=0.545(p=0.005), Spearman ρ=0.691(p=1.3×10⁻⁴), bootstrap 95% CI Pearson [0.23, 0.81]·Spearman "
            "[0.32, 0.87](0을 포함하지 않음, 다만 넓음), 순열 p=0.004/0.0001. 회귀에서 크기를 넣어도 허브성 β=0.62(p=0.0008)로 유지, 하나씩 빼도 최소 "
            "ρ=0.65·β=0.52. 단서 1 -- '크기는 무관'은 과장이었다: 선형 회귀에선 크기도 독립적으로 기여(β=0.40, p=0.02; 허브성과 크기가 약한 음의 상관이라 "
            "단순 상관에선 가려짐). log 크기나 순위 회귀에선 크기가 유의하지 않아, 크기 효과는 가장 큰 병변 쪽에 치우친 비선형 효과다. 단서 2 -- 허브성·크기·"
            "잘린 간선 수를 함께 넣으면 다중공선성(VIF 26)으로 분리되지 않는다: 잘린 간선 ≈ 크기 × 허브성이기 때문. 즉 '위치 대 양'이 아니라 '잃은 연결의 "
            "양은 대부분 위치(허브성)가 정한다'가 정확하다. 추가 발견: 같은 크기 무작위 병변에서도 허브성-손실 관계가 같다(같은 크기 안 ρ 중앙값 0.87) -- "
            "이건 국소 증후군만의 성질이 아니라 이 연결망의 일반 법칙이고, 실제 증후군 병변은 같은 허브성의 무작위 병변보다 오히려 손실이 작았다(잔차 z 평균 "
            "-1.06; 공간적으로 뭉친 병변이라 서로 간의 중복 경로를 함께 잃기 때문으로 보인다). 25쌍 중 15쌍이 영역을 공유(부분집합 관계)해 표본이 완전히 "
            "독립은 아니다. 정정: H16-1의 'r=0.69'는 Pearson이 아니라 Spearman 값이다."
        ),
        verdict="supported",
        evidence=[_EV_ALSTOTT, _EV_SCHLEMM],
        raw_data_note=(
            "허브성: Pearson 0.545(p=0.0049), Spearman 0.691(p=0.00013); 크기: 0.281(0.17)/0.009(0.97); 잘린 간선: 0.554(0.0041)/0.251(0.23). "
            "회귀 β(p): 허브성+크기 0.621(0.0008)+0.400(0.021), R² 0.45; 허브성+log크기 0.541(0.005)+0.163(0.36); 순위 0.733(0.0001)+0.180(0.25); "
            "허브성+크기+잘린간선 -0.246(0.18)/-2.55(0.0001)/2.97(<0.001), VIF 3.2/26.4/25.7. LOO 최소: Spearman 0.655, Pearson 0.472, β 0.519(편측무시 제외 시). "
            "무작위 병변 5,000개: 허브성 ρ 0.657, 크기 ρ 0.604; 실제 병변 손실 백분위 평균 0.48. 미각상실증은 같은 허브성 대비 잔차 z=+7.0로 예외적."
        ),
        executed_at="2026-09-30",
        is_live_computed=False,
    )


_EV_YUAN_2017 = HypothesisEvidenceOut(
    title="Yuan et al. 2017 -- Brain hubs in lesion models: Predicting functional network topology with lesion patterns in patients (Scientific Reports)",
    url="https://www.nature.com/articles/s41598-017-17886-x",
)
_EV_WARREN_2014 = HypothesisEvidenceOut(
    title="Warren, Power, Bruss et al. 2014 -- Network measures predict neuropsychological outcome after brain injury (PNAS 111:14247)",
    url="https://www.pnas.org/doi/10.1073/pnas.1322173111",
)
_EV_GRATTON_2012 = HypothesisEvidenceOut(
    title="Gratton, Nomura, Pérez & D'Esposito 2012 -- Focal brain lesions to critical locations cause widespread disruption of the modular organization of the brain (J Cogn Neurosci 24:1275)",
    url="https://pubmed.ncbi.nlm.nih.gov/22401285/",
)


def _h16_1_2_which_hubness() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-1-2-which-hubness-predicts-impact",
        title="H16-1-2 · '허브성'을 하나로 묶지 않으면, 어떤 종류의 허브성이 병변 영향을 가장 잘 예측할까?",
        statement=(
            "(외부 검토 의견 3번) 허브성 ≠ degree. 선행 연구는 병변 허브를 연결자(participation coefficient, PC)와 지역 허브(within-module degree, WMD)로 "
            "나누고(Yuan 2017, Warren 2014, Gratton 2012), 중심성이 높은 영역 손상이 전역 효과가 크다고 본다(Alstott 2009). 예측: P1 전역 효율 손실은 경로 "
            "기반 허브성(betweenness·노드 효율)이 degree보다 잘 예측한다. P2 모듈성 변화는 PC가 가장 잘 예측한다 -- 단 방향은 Gratton(기능 연결망에서 연결자 "
            "손상 -> 모듈성 감소)과 반대일 수 있다(정적 구조 제거 모델에서는 모듈 사이 간선이 빠져 모듈성이 오른다). P3 WMD는 모듈성 변화와 약하거나 반대 관계."
        ),
        method=(
            "정상 뇌 400영역에서 허브성 7종(degree, strength, betweenness, 노드 전역 효율, eigenvector, PC, WMD; Yeo-7 모듈). 병변 허브성 = 병변 영역 평균. "
            "재조직 없음 영향 3종(전역 효율 손실 ΔE, 모듈성 변화 ΔQ, 평균 군집 계수 변화 ΔC). 표본: 국소 증후군 25개 + 공간적으로 인접한 무작위 병변 2,000개. "
            "Spearman ρ, 크기 통제 부분 ρ, 크기 대비 추가 설명력 ΔR², 최선 지표와의 |부분 ρ| 차이 bootstrap 95% CI(backend/scripts/hubness_types.py)."
        ),
        result_summary=(
            "지지 -- 결과마다 최선의 허브성이 다르고, degree는 어디서도 최선이 아니다. P1 지지: ΔE는 노드 전역 효율이 최선(증후군 ρ=0.87, 무작위 2,000개 "
            "ρ=0.87), betweenness가 거의 같고(증후군 0.87, 차이 CI가 0을 포함), degree는 유의하게 낮았다(0.69 / 0.80, 차이 CI가 0을 넘음). P2 지지(방향 포함): "
            "ΔQ는 PC가 최선(0.83 / 0.77, 나머지와의 차이 CI 모두 0 초과)이고, 예측대로 PC가 높은 병변일수록 모듈성이 '오른다' -- Gratton의 기능 연결망 "
            "결과와 반대 방향. 이 모델은 정적 구조 제거라 손상 후 기능적 재편(diaschisis)을 재현하지 못한다는 뜻이다. P3 지지: WMD는 ΔQ와 약한 음의 관계"
            "(−0.14 / −0.18). ΔC는 일관된 최선 지표가 없었다(증후군 strength, 무작위 betweenness). 해석: H16-1의 '허브성(평균 degree)'은 경로 기반 허브성의 "
            "근사였을 뿐이다. 그리고 정상 부하 지도(betweenness)가 재조직을 설명하고 degree는 설명하지 못한 H16-5-1 결과와 같은 방향 -- 이 연결망에서 영향을 "
            "정하는 것은 연결 수가 아니라 경로 구조다."
        ),
        verdict="supported",
        evidence=[_EV_YUAN_2017, _EV_WARREN_2014, _EV_GRATTON_2012, _EV_ALSTOTT],
        raw_data_note=(
            "증후군 25개 Spearman ρ(ΔE/ΔQ): degree 0.691/0.139, strength 0.464/−0.169, betweenness 0.866/0.759, 노드 효율 0.867/0.454, eigenvector 0.526/−0.017, "
            "PC 0.527/0.834, WMD 0.281/−0.137. 무작위 2,000개: degree 0.798/0.436, betweenness 0.790/0.471, 노드 효율 0.870/0.453, PC 0.442/0.766, WMD 0.422/−0.179. "
            "크기 대비 ΔR²(무작위, ΔE): 노드 효율 0.510, degree 0.448, betweenness 0.274. 허브성 간 순위 상관: degree-노드 효율 0.93, degree-betweenness 0.82, degree-PC 0.26. "
            "주의: 선행 연구 셋은 실제 환자의 기능 연결망·인지 결과, 이 결과는 구조 연결망의 정적 제거 -- 'Nature'로 인용된 Yuan 연구는 Scientific Reports(Nature 계열)."
        ),
        executed_at="2026-10-02",
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


def _h16_2_1_short_vs_long_term() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-2-1-short-vs-long-term-optima",
        title="H16-2-1 · 단기 효율 회복과 장기 강건성은 서로 다른 최적 전략을 가질까?",
        statement=(
            "(외부 검토 의견) H16-2의 실패는 '단기 효율'과 '장기 강건성'의 최적해가 다를 수 있다는 경계조건이다. H16-2는 재조직이 끝난 뒤만 봤으므로 "
            "시간을 나눠 본다. 예측: S1 허브 집중이 초기(예산 25%) 회복이 가장 빠르다. L1 장기 마모에서 허브 집중이 가장 빨리 무너지고 headroom/분산이 "
            "오래 버틴다(무작위 마모에선 차이 작음). X 병변마다 단기 순위와 장기 순위가 반대 방향이다."
        ),
        method=(
            "단기: 잃은 연결을 하나씩 다시 붙이며 예산 10/25/50/100% 시점 전역 효율, 회복 곡선 넓이. 장기: 재조직된 연결망을 20개 시기 동안 마모 -- "
            "W1 과부하형(자기 정상 용량 대비 부하²에 비례, 부드러운 확률적 실패), W2 활동의존형(절대 부하에 비례; de Haan et al. 2012), W3 무작위(대조). "
            "정상 뇌가 시기당 약 2개 영역을 잃도록 보정, 8회 반복, 원래 400개 기준 효율 유지율. 국소 병변 25개 쌍대 Wilcoxon"
            "(backend/scripts/short_long_term_reorganization.py; 매개 중심성·최단경로는 rustworkx·scipy로 계산, networkx와 값 일치 확인)."
        ),
        result_summary=(
            "전략 수준에선 지지 -- 단 '장기'의 답은 손상 기전에 따라 뒤집힌다. S1 부분 기각: 허브 집중은 headroom·국소보다 빨랐지만(25/25) 분산과는 "
            "초기부터 차이가 없었다(예산 25% p=0.51) -- '허브에 몰면 빨리 회복'은 단기로 봐도 성립하지 않는다. L1 혼재: 절대 부하가 닳는 W2에선 예측대로 "
            "집중이 최악(유지율 0.781, 정상 0.791보다 낮음), 분산이 최선(0.817). 그러나 자기 용량 대비 초과가 서서히 손상을 부르는 W1에선 정반대로 집중이 "
            "최선(0.836), 분산이 최악(0.672) -- 허브는 용량이 커서 초과 비율이 작고, 분산은 용량 작은 영역에 부하를 보낸다. 같은 과부하라도 '문턱을 넘으면 "
            "즉시 실패'(H16-4의 연쇄 모델)에선 집중이 최악이었다. W3 무작위에선 유지율 차이 없음(대조군 통과). X 기각: 병변별 단기-장기 순위 상관 중앙값 "
            "-0.2(p=0.50). 핵심: 어느 한 전략도 모든 시간·기전에서 최적이 아니었다. headroom만이 어떤 기준에서도 최하위가 아니었다(단기 3위, W1 3위, W2 2위, "
            "연쇄 1위) -- 최선이 아니라 '최악을 피하는' 절충안. 어떤 전략도 장기 절대 효율에서 정상 뇌(W2 0.341)에 도달하지 못했다."
        ),
        verdict="supported",
        evidence=[
            _EV_MOTTER_LAI,
            HypothesisEvidenceOut(
                title="de Haan, Mott, van Straaten, Scheltens & Stam 2012 -- Activity dependent degeneration explains hub vulnerability in Alzheimer's disease (PLOS Comput Biol 8:e1002582)",
                url="https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1002582",
            ),
        ],
        raw_data_note=(
            "단기 효율(예산 25%/100%, 곡선 넓이): 집중 0.4369/0.4507/0.0118, 분산 0.4362/0.4488/0.0107, headroom 0.4343/0.4435/0.0077, 국소 0.4320/0.4385/0.0045, "
            "없음 0.4297. 장기 유지율 W1/W2/W3: 정상 0.827/0.791/0.816, 없음 0.824/0.789/0.809, 국소 0.806/0.799/0.809, 집중 0.836/0.781/0.809, 분산 0.672/0.817/0.809, "
            "headroom 0.813/0.804/0.809. 순위 역전 ρ 중앙값 W1 -0.2(p=0.50), W2 -0.2(p=0.86), W3 0.0(p=0.49)."
        ),
        executed_at="2026-09-30",
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


def _h16_5_1_capacity_definition_sensitivity() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-5-1-capacity-definition-sensitivity",
        title="H16-5-1 · '정상 용량'을 betweenness가 아닌 다른 척도로 정의해도 headroom 재조직이 여전히 나을까?",
        statement=(
            "(외부 검토 의견) H16-5는 용량 = 정상 뇌 betweenness × 1.2로 고정했고, 평가한 연쇄 과부하 모델도 같은 용량을 썼다 -- 순환 가능성. 용량을 하나의 "
            "중심성으로 고정하지 말고 여러 정의로 바꿔 본다. 예측: headroom의 이점(분산 대비 정상 이탈이 작고 연쇄 생존이 높음)이 betweenness 이외 정의 "
            "대부분에서도 유지되면 진짜 효과, betweenness에서만 나타나면 순환의 산물."
        ),
        method=(
            "용량 정의 7가지(모두 정상 뇌에서 계산): betweenness(기존), degree, strength(가중 연결 합), participation(Yeo-7), communicability, 평균 제어성"
            "(controllability, Gu et al. 2015), 기능 연결 강도(fc_strength). 각 정의로 headroom 재조직을 반복하고 분산·국소·재조직 없음과 국소 병변 25개 쌍대 "
            "Wilcoxon. 정의와 무관한 지표(전역 효율, 부하 Gini, 2차 타격, W2·W3 마모 유지율, 정상 이탈)와 참고용 betweenness 용량 연쇄 생존율"
            "(backend/scripts/capacity_definition_sensitivity.py). 대사 비용·개인별 정상 분포는 자료가 없어 제외."
        ),
        result_summary=(
            "기각 -- 이점은 betweenness 정의에서만 뚜렷하다. 분산 대비 연쇄 생존: betweenness +0.185(25/25), 평균 제어성 +0.082(23/25), 나머지 5가지는 "
            "-0.017~+0.012로 사실상 분산과 같다. 정의와 무관한 지표인 정상 이탈도 같은 양상: betweenness 0.133, 제어성 0.213, 나머지 0.31~0.34(분산 0.345). "
            "betweenness와 순위 상관이 0.82로 높은 degree조차 이점이 전혀 없었다(연쇄 0.694, 분산보다 오히려 낮음). 즉 headroom의 효과는 '각 영역의 용량을 "
            "존중한다'는 일반 원리가 아니라, '정상 뇌의 부하 분포(betweenness) 자체를 되살리는' 데서 나온다. 정상 이탈은 순환과 무관한 지표라 이 결과가 "
            "평가의 순환만으로 생긴 것은 아니다 -- 다만 정의의 순환(용량 = 정상 부하)은 그대로 남는다. 따라서 사용자 가설의 '정상 범위로 되돌린다'는 목표는 "
            "'정상 부하 지도'를 기준으로 삼을 때만 효과가 있고, 구조적 대리 지표로는 대체되지 않는다. 재조직 없음과 비교하면 모든 정의에서 연쇄 생존이 "
            "낮거나 같았다(betweenness -0.011, p=0.07; 나머지 -0.11~-0.21)."
        ),
        verdict="not_supported",
        evidence=[
            _EV_MOTTER_LAI,
            HypothesisEvidenceOut(
                title="Gu, Pasqualetti, Cieslak et al. 2015 -- Controllability of structural brain networks (Nature Communications 6:8414)",
                url="https://www.nature.com/articles/ncomms9414",
            ),
        ],
        raw_data_note=(
            "betweenness와의 순위 상관: degree 0.82, communicability 0.52, participation 0.38, strength 0.37, 제어성 0.13, fc_strength -0.14. "
            "국소 25개 평균(효율/정상 이탈/2차 타격/W2/연쇄): betweenness 0.4435/0.133/0.0466/0.806/0.895, degree 0.4490/0.343/0.0410/0.814/0.694, "
            "strength 0.4477/0.314/0.0415/0.818/0.722, participation 0.4482/0.329/0.0414/0.815/0.714, communicability 0.4487/0.341/0.0409/0.815/0.711, "
            "제어성 0.4453/0.213/0.0449/0.807/0.792, fc_strength 0.4485/0.332/0.0408/0.817/0.716; 분산 0.4488/0.345/0.0409/0.815/0.710, 없음 0.4297/0.057/0.0524/0.785/0.906. "
            "W3 무작위 마모 유지율은 모든 전략 0.812±0.001(대조군 통과)."
        ),
        executed_at="2026-09-30",
        is_live_computed=False,
    )


def _h16_5_2_headroom_not_algorithm_artifact() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-5-2-headroom-not-algorithm-artifact",
        title="H16-5-2 · headroom 재조직의 우수함은 알고리즘이 만든 산물이 아닐까?",
        statement=(
            "(외부 검토 의견) headroom이 연쇄 과부하에 강한 이유가 연결을 덜 붙였거나, 특정 degree 등급만 골랐거나, 우연한 시드, 특정 병변 집합, "
            "특정 용량 허용치 때문일 수 있다. 예측: 연결 예산을 같게 하고, degree를 맞춘 귀무 전략·무작위 전략·다른 병변 집합·하나씩 빼기에서도 "
            "headroom의 연쇄 생존 이점이 유지된다. degree 보존 무작위 재배선 연결망에서는 이점이 줄어든다면, 이점은 알고리즘이 아니라 실제 뇌 위상의 성질이다."
        ),
        method=(
            "① 병변마다 전략 간 새 연결 수를 최솟값으로 동일화 ②(a) headroom이 고른 목표를 같은 정상 degree 십분위의 무작위 후보로 바꾼 귀무 전략 3시드 "
            "(b) degree 순서 보존 재배선(Maslov-Sneppen) 연결망 2개에서 같은 실험 ③ 무작위 전략 6시드 ⑤ 복합 질환 7개 + 공간적으로 인접한 무작위 병변 20개 "
            "⑥ 병변 하나씩 빼기 ⑦ 연쇄 허용치 m=0.8~1.5 스윕. 지표: 전역 효율, 정상 이탈, 2차 타격 손실, 활동의존 마모(W2) 유지율, 연쇄 생존율. 총 102개 작업"
            "(backend/scripts/headroom_robustness_suite.py). ④ 용량 정의 민감도는 H16-5-1."
        ),
        result_summary=(
            "지지 -- 연쇄 생존 이점은 알고리즘 산물이 아니라 실제 뇌 위상에서 나온다. 단 허용치 조건이 붙는다. ① 모든 전략이 병변마다 정확히 같은 수의 "
            "연결을 붙이고 있었다(예산 동일화가 결과를 바꾸지 않음). ②(a) degree 등급만 맞춘 귀무보다 연쇄 생존 +0.11(25/25, p=6×10⁻⁸), 정상 이탈도 25/25 "
            "작았다 -- '어떤 degree를 골랐나'로는 설명되지 않는다. ③ 무작위 6시드 중 연쇄 생존에서 headroom을 이긴 경우는 0%. ⑤ 복합 질환(0.819 vs 분산 "
            "0.600, 7/7)과 인접 무작위 병변(0.914 vs 0.728, 20/20)에서도 재조직 전략 중 최고. ⑥ 하나씩 빼도 방향은 25/25 유지. ②(b) 가장 중요한 근거(단 귀무 연결망 2개뿐이라 강한 탐색적 근거 -- H16-5-3에서 확장): degree 보존 "
            "재배선 연결망에서는 분산 대비 이점이 +0.185 → +0.05로 줄고, 무작위 전략보다 오히려 낮았다(-0.025, 2/25), 정상 이탈 이점도 사라졌다. 즉 이점은 "
            "degree 분포가 아니라 실제 뇌의 부하 구조에 달려 있다. ⑦ 단서: 허용치 m≥1.0에서만 성립한다. m=0.8~0.9(정상 뇌 자체도 연쇄 붕괴하는 영역)에선 "
            "분산·무작위보다 낮았다. 재조직 없음과 비교하면 m=0.9~1.0에선 headroom이 낫고 m≥1.3에선 오히려 낮다. 대가는 그대로다: 효율·2차 타격·W2 "
            "유지율은 분산·무작위보다 조금 나쁘다. 단 H16-5-1: 이 이점은 용량을 betweenness(정상 부하)로 정의했을 때만 뚜렷하다."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "국소 25개 평균(효율/정상 이탈/2차 타격 손실/W2 유지율/연쇄 m1.2): headroom 0.4435/0.133/0.0466/0.804/0.895, 분산 0.4488/0.345/0.0409/0.815/0.710, "
            "무작위 0.4497/0.268/0.0411/0.811/0.745, degree 맞춤 귀무 0.4488/0.222/0.0427/0.808/0.782, 없음 0.4297/0.057/0.0524/0.785/0.906. "
            "재배선 연결망(null0/null1) 연쇄: headroom 0.913/0.914, 분산 0.862/0.859, 무작위 0.938/0.938, 없음 0.989/0.987. "
            "스윕 m=0.8/0.9/1.0/1.1/1.2/1.3/1.5 연쇄: 정상 0/0/1/1/1/1/1, headroom 0.129/0.351/0.751/0.855/0.895/0.915/0.939, 분산 0.308/0.503/0.642/0.689/0.710/0.728/0.757, "
            "없음 0.079/0.145/0.505/0.840/0.906/0.937/0.983. 재배선 연결망의 '국소' 정상 이탈(5.3/9.0)은 정상 모듈성이 0에 가까워 상대 오차가 커진 것."
        ),
        executed_at="2026-09-30",
        is_live_computed=False,
    )


def _h16_5_3_null_distribution() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h16-5-3-null-network-distribution",
        title="H16-5-3 · 귀무 연결망을 2개가 아니라 145개 만들어도 '실제 뇌 위상에서만 이점이 크다'가 유지될까?",
        statement=(
            "(외부 검토 의견 13번) H16-5-2의 degree 보존 재배선 연결망은 2개뿐이라 '결정적 근거'가 아니라 '강한 탐색적 근거'다. 귀무 연결망을 크게 늘려 "
            "ΔR = 평균[R(정상 부하 지도 기반) − R(비교 전략)]의 귀무 분포를 만들고 P(ΔR_실제 > ΔR_귀무)를 본다. 추가로 degree 보존 재배선은 공간 배치(배선 "
            "길이)까지 무너뜨리므로, 배선 길이를 보존한 귀무로 '위상 때문인가, 공간 배치 때문인가'를 가른다. 예측: 실제 뇌의 ΔR이 두 귀무 분포 모두의 위쪽 "
            "끝 밖에 있다."
        ),
        method=(
            "귀무 ① degree 보존 재배선(Maslov-Sneppen, 간선 수의 10배 교환) 95개 ② degree + 총 배선 길이 보존 재배선(두 간선 길이 합 ±10%, 누적 총 길이 ±1%) "
            "50개. 각 연결망에서 국소 증후군 25개 병변(같은 영역 번호) × 전략 4개(재조직 없음, 무작위, 균등 분산, 정상 부하 지도 기반). 지표: 연쇄 생존(m=1.0, "
            "1.2), 부하 지도 충실도, 과부하 비율, 전역 효율. 재조직은 원래 구현과 간선 집합이 같음을 검증한 빠른 구현(scripts/fast_reorganize.py) "
            "(backend/scripts/null_network_distribution.py). degree 보존 100개 중 95개만 완료 -- 백그라운드 실행 시간 상한(2시간)에 걸려 나머지 5개는 계산하지 않았다."
        ),
        result_summary=(
            "지지 -- 실제 뇌의 이점은 145개 귀무 연결망 전부보다 크다. 균등 분산 대비 연쇄 생존(m=1.2) ΔR: 실제 +0.185, degree 보존 귀무 +0.052±0.003"
            "(95개 중 실제보다 큰 것 0개, z=47), 배선 길이 보존 귀무 +0.100±0.004(50개 중 0개, z=24). 경험적 p ≤ 1/96 ≈ 0.010(degree), ≤ 1/51 ≈ 0.020(길이). "
            "정정: docs/51의 '이점이 거의 사라진다'는 과장이었다 -- 귀무에서도 이점은 남는다(degree 귀무 95/95, 길이 귀무 50/50에서 양수). 실제 이점을 셋으로 "
            "나누면 대략 28%는 degree 분포만으로(알고리즘 자체), 26%는 공간 배치(배선 길이)로, 나머지 46%는 그 둘로 설명되지 않는 실제 뇌 위상(군집 계수 "
            "0.43 vs 길이 귀무 0.15 vs degree 귀무 0.08 등)에서 온다. 무작위 전략과 비교하면 갈린다: degree 귀무에서는 정상 부하 지도 기반이 무작위보다 "
            "낮고(−0.024, 0/95 양수), 길이 귀무에서는 조금 높다(+0.020, 50/50). 단서: 재조직 없음보다 나은가는 허용치에 달렸다 -- m=1.0에선 실제 이점(+0.247)이 "
            "degree 귀무와 비슷하고(P=0.05) 길이 귀무보다 작다."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "실제 / degree 귀무 평균 / 길이 귀무 평균 -- 연쇄 m1.2: 정상 부하 지도 기반 0.895/0.914/0.959, 균등 분산 0.710/0.863/0.859, 무작위 0.745/0.939/0.939, "
            "없음 0.906/0.988/0.993. 부하 지도 충실도: 0.983/0.977/0.993 vs 균등 분산 0.879/0.942/0.970. ΔR(정상 부하 지도 기반 − 균등 분산) 충실도: 실제 +0.104, "
            "degree 귀무 +0.035±0.002, 길이 귀무 +0.023±0.001. 연결망 성질: 평균 배선 길이 실제 46.1, degree 귀무 79.9, 길이 귀무 46.5; 군집 계수 0.435/0.080/0.151. "
            "귀무 연결망 145개 모두 연결됨."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


_H17_SCRIPTS = "backend/scripts/normative_load_map.py, null_network_distribution.py, mixed_failure_model.py, closed_loop_rehab_batch.py"


def _h17_normative_load_map_reorganization() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-normative-load-map-reorganization",
        title="H17 · 정상 부하 지도 기반 재조직 가설 -- '균등하게'가 아니라 '정상 집단 대표 커넥톰의 영역별 부하 분포를 되살리며' 재조직하면 더 강해질까?",
        statement=(
            "(H16을 외부 검토 의견 16·17번에 따라 다시 씀) 뇌손상 후 네트워크 재조직의 강건성은 기능적 부담을 균등하게 분산하는 것 자체보다, 정상 집단 대표 "
            "커넥톰(33명 합의)에서 관찰되는 영역별 부하 분포(정상 부하 지도)를 보존·복원하면서 과도한 병목 집중을 제한하는 방향에서 증가할 것이다. 단, 그 효과는 부하가 임계치를 "
            "넘으면 급격히 무너지는 연쇄형(cascade) 실패에서 가장 뚜렷할 것이다. 'headroom'은 실제 생물학적 용량이 아니라 정상 betweenness 지도를 쓰므로 "
            "'정상 부하 지도 기반 재조직(normative-load-guided)'으로 부른다. [docs/54 v2: '복원'이 아니라 '참조 지도 대비 "
            "각 영역이 자기 정상 부하보다 과도하게 늘지 않도록 제약'(순서 유지만으로는 부족 -- 허브 집중도 순서는 유지했지만 연쇄에 가장 약했다), "
            "점진형 W1에서는 허브 집중이 더 낫다는 반대 조건을 명시.]"
        ),
        method=(
            "docs/50-52의 결과를 이 문장 기준으로 다시 읽고, 빠진 검증을 추가했다: H17-1 정상 부하 지도 복원 정도와 그 대가·순환 분리, H16-5-3 귀무 연결망 "
            f"145개, H17-2 혼합 손상 모델의 가상 환자 모수 회복, H17-3 손상 기전 혼합별 최선 전략, H17-4 폐루프 재활({_H17_SCRIPTS}). 연구소 '손상-재조직 "
            "실험실'(/lab/reorganization)에서 같은 계산을 직접 돌려볼 수 있다."
        ),
        result_summary=(
            "조건부 지지 -- 단 조건이 하나 더 필요하다. 지지되는 것: ① 균등화는 답이 아니다(균등 분산은 정상에서 가장 멀고, 점진형 과부하 W1에서 붕괴). "
            "② 정상 부하 지도 기반은 재조직 전략 중 정상 부하 지도를 가장 잘 되살리고(ρ 0.983, 과부하 10%), 연쇄형 실패에서 최선이다(생존 0.895). "
            "③ 그 이점은 실제 뇌 위상에서 커진다(귀무 연결망 145개 모두보다 큼). 조건으로 드러난 것: ④ 연쇄형이 아닌 점진형 마모(W1~W4 혼합 18가지)에서는 "
            "어디에서도 최선이 아니었다 -- W1이 섞이면 허브 집중이 일관되게 최선(평균 순위 1.28)이고, 정상 부하 지도 기반은 2~4위(평균 2.78)로 '붕괴하지 "
            "않는' 쪽이다. ⑤ 연쇄형에서도 이점은 '각 영역의 실패 문턱이 자기 정상 부하에 비례한다'는 가정에서만 크다: 문턱 모양이 정상 부하 지도에서 25%만 "
            "벗어나도 이점이 +0.185 -> +0.117, 50%면 +0.024로 줄어든다. ⑥ 부하 지도를 충실히 되살릴수록 정상 위상에 가깝고 연쇄에 강하지만, 전역 효율·2차 "
            "타격 내성·활동의존 마모 내성은 나빠진다(병변 안 순위 상관 −0.61, +0.74, −0.52). 정확한 결론: '정상 부하 지도 복원'은 일반적 최적해가 아니라, "
            "실패가 문턱형이고 그 문턱이 정상 부하에 맞춰져 있을 때의 최적해다. 다음 검증: 개인별 정상 부하 범위(μ, σ) -- 이것이 집단 평균의 산물인지 가린다. [docs/56 단서: 가소성을 '기존 연결 강화'(가중치)로 "
            "모델링하면 균등 분산이 정상 부하 지도 기반보다 연쇄에 강해지고 τ 무릎도 사라진다(H17-10) -- 위 결론은 이진·발아형 재조직 모델에 한정된다. docs/58 H17 v3: 회복 기전(발아/강화)·시간 순서·실패 기전별 조건부 전략으로 정리.]"
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI, _EV_ALSTOTT],
        raw_data_note=(
            "국소 25개 평균(정상 부하 지도 충실도 ρ / 과부하 / 효율 / 2차 타격 / W2 / 연쇄 m1.2): 정상 부하 지도 기반 0.983/0.102/0.4435/0.0466/0.806/0.895, 균등 분산 "
            "0.879/0.290/0.4488/0.0409/0.815/0.710, 허브 집중 0.972/0.058/0.4507/0.0805/0.782/0.492, 무작위 0.931/0.253/0.4496/0.0407/0.810/0.745, 없음 0.991/0.032/0.4297/0.0524/0.785/0.906. "
            "점진형 혼합 18점의 최대 후회(최선과의 효율 차): 허브 집중 0.0057, 정상 부하 지도 기반 0.0116, 균등 분산 0.0709."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_1_restoring_the_load_map() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-1-restoring-the-load-map-and-circularity",
        title="H17-1 · headroom의 이점은 정말 '정상 부하 지도를 되살린' 데서 오고, 그것은 순환 논리가 아닐까?",
        statement=(
            "(외부 검토 의견 9번 -- 중요 지점) headroom의 목표는 사실상 Target_i ≈ 정상 betweenness_i이므로 결과는 '정상 betweenness 분포를 복원했더니 강건성이 "
            "높아졌다'로 써야 하며 '뇌는 각 영역의 정상 용량을 유지하려 한다'로 일반화하면 안 된다. 그런데 연쇄 모델의 실패 문턱도 정상 betweenness × 1.2라, "
            "이 이점 자체가 정의상 생긴 것(순환)일 수 있다. 확인: (a) 실제로 정상 부하 지도를 되살리나 (b) 되살릴수록 순환과 무관한 지표도 좋아지나 (c) 실패 "
            "문턱을 정상 부하 지도가 아닌 모양으로 바꿔도 이점이 남나. 예측(일치 원리): 문턱 모양이 정상 부하에서 멀어질수록 이점이 줄고, 그 모양으로 재조직한 "
            "headroom이 이긴다."
        ),
        method=(
            "국소 25개 × 조건 12개(재조직 없음, 국소, 허브 집중, 균등 분산, 무작위, headroom × 용량 정의 7) = 300개 그래프(docs/51 캐시와 300/300 동일 확인). "
            "부하 지도 충실도 = 재조직 후 betweenness와 정상 betweenness의 Spearman ρ. 병변 안 순위 상관(조건 12개)의 평균. 평가용 실패 문턱 c(λ) = m_λ·[(1−λ)·정상 부하 "
            "+ λ·평균 부하·대안 프로필(degree 또는 평균 제어성)], m_λ는 정상 뇌가 가장 빠듯한 영역에서도 20% 여유를 갖게 보정(backend/scripts/normative_load_map.py)."
        ),
        result_summary=(
            "검토 의견의 재서술이 맞다 -- 그리고 조건이 하나 더 붙는다. (a) 그렇다: headroom(betweenness)은 재조직 전략 중 정상 부하 지도를 가장 잘 되살렸다"
            "(ρ 0.983, 과부하 10%; 다른 용량 정의로 한 headroom은 0.886~0.909로 균등 분산 0.879와 비슷). (b) 반만 그렇다: 충실도가 높을수록 정상 위상에 가깝고"
            "(이탈과 ρ −0.86, 25/25) 정상 부하 문턱 연쇄에 강하지만(+0.48, 23/25), 전역 효율(−0.61, 0/25 양수)·2차 타격 내성(손실과 +0.74, 25/25)·W2 마모 "
            "내성(−0.52)은 나빠진다 -- 복원은 '전반적 강건성'이 아니라 맞바꿈이다. (c) 순환이 일부 맞다: 문턱 모양이 정상 부하에서 25% 벗어나면 이점 +0.185 -> "
            "+0.117, 50%면 +0.024. degree나 제어성 모양 그대로(λ=1)면 정상 뇌를 안정시키려고 문턱 여유가 ×6.4~×536이 필요하고, 그러면 연쇄가 아예 일어나지 "
            "않는다(모든 전략 생존 1.0). 일치 원리 예측은 기각: 대안 프로필로 재조직한 headroom은 어떤 λ에서도 headroom(betweenness)을 이기지 못했다. 정확한 "
            "결론: '정상 betweenness 분포를 복원하면, 실패 문턱이 정상 부하에 비례하는 연쇄형 실패에서 강해진다(효율·2차 타격·활동의존 마모를 대가로).' "
            "'뇌가 정상 용량을 유지하려 한다'는 이 결과로 말할 수 없다 -- 그것은 '실제 실패 문턱이 정상 부하에 맞춰져 있는가'라는 별도의 생물학적 질문이다."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "병변 안 ρ(충실도 vs 지표; 양수 병변 수/25): 전역 효율 −0.615(0), 2차 타격 손실 +0.739(25), W2 −0.523(1), 정상 이탈 −0.863(0), 정상 부하 문턱 연쇄 +0.476(23). "
            "headroom(betweenness) − 균등 분산 연쇄 생존: λ=0(m 1.20) +0.185(25/25), degree λ=0.25(m 1.51) +0.117(25/25), λ=0.5(m 2.02) +0.024(24/25), λ=1(m 6.43) 0; "
            "제어성 λ=0.5(m 2.39) +0.155, λ=1(m 535.8) 0. 재조직 없음 대비: λ=0 −0.011(p=0.07), λ=0.25 +0.022(p=0.007)."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_3_strategy_map() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-3-best-strategy-by-failure-mixture",
        title="H17-3 · 손상 기전의 혼합 비율에 따라 최선의 재조직 전략이 바뀔까?",
        statement=(
            "(외부 검토 의견 7·21번) '어떤 전략이 최고인가'가 아니라 '어떤 손상에는 어떤 재조직이 최적인가'를 묻는다. 예측: 연쇄형(문턱)에서 최선인 정상 부하 "
            "지도 기반이 점진형 마모 혼합에서도 대체로 상위권이고, W2(절대 부하)가 우세하면 균등 분산, W1(상대 과부하)이 우세하면 허브 집중이 유리하다"
            "(docs/51 H16-2-1의 W1·W2 결과)."
        ),
        method=(
            "W1·W2·W3 단체(simplex) 0.25 간격 15점 + W4 포함 3점. 국소 증후군 9개(0, 3, …, 24번) × 전략 6개 × 반복 3(전략 간 공통 난수), 10시기 마모 뒤 전역 효율"
            "(원래 400영역 기준). 혼합마다 최선 전략, 병변별 1위 횟수, 최선과의 차이(후회)(backend/scripts/mixed_failure_model.py MODE=strategy)."
        ),
        result_summary=(
            "지지 -- 최선 전략은 손상 기전에 따라 바뀐다. 다만 정상 부하 지도 기반은 점진형 마모 어디에서도 1위가 아니었다. W1이 25% 이상 섞인 10점과 "
            "W4+W1에서는 허브 집중이 1위(병변 7~9/9), 균등 분산은 최하위(0.29~0.32, 정상 부하 지도 기반 0.350). 순수 W2에서는 균등 분산(6/9), W2+W3·W2+W4에서는 "
            "무작위·균등 분산·허브 집중이 비슷하다. 18점 전체: 허브 집중 평균 순위 1.28·최대 후회 0.0057, 정상 부하 지도 기반 2.78·0.0116, 균등 분산 4.67·0.0709. "
            "즉 점진형 마모만 보면 허브 집중이 가장 안전하다. 그러나 문턱형 연쇄에서는 허브 집중이 붕괴한다(생존 0.49 vs 정상 부하 지도 기반 0.895). 실패가 "
            "문턱형인지 점진형인지에 따라 최적이 뒤집히고, 둘 다에서 무너지지 않는 것은 정상 부하 지도 기반뿐이다. 주의: 효율은 재조직 직후 이득(허브 집중이 "
            "가장 큼)을 포함한다 -- '유지율'만 보면 재조직 없음이 자주 1위(시작이 가장 낮아 잃을 것이 적음)."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "10시기 뒤 효율(없음/국소/허브 집중/균등 분산/정상 부하 지도 기반/무작위): W3 0.3387/0.3475/0.3590/0.3565/0.3523/0.3574, W2 0.3360/0.3465/0.3553/0.3610/0.3527/0.3605, "
            "W1 0.3410/0.3415/0.3614/0.2905/0.3498/0.3320, W1·W2·W3 25/25/50 0.3379/0.3437/0.3590/0.3136/0.3510/0.3436, W4 0.3695/0.3786/0.3908/0.3881/0.3837/0.3893, "
            "W4+W1 0.3548/0.3569/0.3748/0.3122/0.3659/0.3501."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_4_closed_loop_rehab() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-4-closed-loop-rehab",
        title="H17-4 · '정상 부하 지도와의 차이를 매 시기 재고 개입하는' 폐루프 재활이 처음 한 번 계획하는 개방 루프보다 나을까?",
        statement=(
            "검토 의견 21번의 '환자 connectome -> 정상 operating envelope -> 목표 재조직 상태 -> 폐루프 개입' 틀을 연구소에서 시험한다(개인별 envelope 대신 "
            "집단 정상 부하 지도). 예측: M1 활동 조절(TMS/BCI 유사, 과부하 영역의 부하를 이웃의 여유분으로 넘김)은 W1(자기 정상 부하 대비 과부하, 비선형)에서만 "
            "돕는다 -- W2(절대 부하, 선형)는 부하를 옮겨도 위험 총합이 같고 W3·W4는 부하와 무관. M2 활동 조절에서 폐루프 > 개방 루프. C1 연결 유도(가소성)에서 "
            "폐루프 ≥ 개방 루프, 특히 W4(단절)에서. C2 연결 유도는 어떤 기전에서든 개입 없음보다 효율이 높다."
        ),
        method=(
            "연구소 '폐루프 재활' 탭과 같은 서버 코드(app/lab/reorganization_lab.run_closed_loop). 국소 증후군 9개 × 개입 2종(연결 유도 / 균등 분산 자연 재조직 "
            "위의 활동 조절) × 기전 5종(W1, W2, W3, W4, 고른 혼합) × 제어기 3종(없음/개방/폐루프), 12시기, 반복 2, 시기당 예산 20, 공통 난수. 마지막 시기 전역 "
            "효율·생존 영역 수, 병변 단위 쌍대 Wilcoxon(backend/scripts/closed_loop_rehab_batch.py)."
        ),
        result_summary=(
            "혼재 -- 폐루프의 이점은 개입 종류에 달렸다. M1 지지: 활동 조절은 W1에서 생존 영역 +6.3(9/9, p=0.004), 고른 혼합에서 +5.4(9/9), W2에서는 +0.3"
            "(유의하지 않음), W3·W4에서는 정확히 0(9/9 동률) -- 분석적 예측(선형 위험은 부하를 옮겨도 총합이 같다)과 일치. M2 지지: W1에서 폐루프가 개방 루프보다 "
            "생존 +5.0(9/9, p=0.004), 효율 +0.009(9/9); 개방 루프는 처음 고른 영역이 죽거나 부하가 바뀌어도 같은 곳을 계속 자극해 개입 없음과 거의 같았다"
            "(+1.3, p=0.06). C1 기각: 연결 유도에서는 폐루프와 개방 루프가 거의 같았다(W4 −0.0002, 2/9; W3 +0.0009, 8/9; 생존 차이 0~−0.8). 새로 잃은 영역의 "
            "이웃을 대상에 넣는 피드백은 이득이 없었다. C2 부분 지지: 연결 유도는 모든 기전에서 효율을 올렸지만(8~9/9), W1·고른 혼합에서는 생존 영역을 줄였다"
            "(고른 혼합 −2.0, 0/9) -- 새 연결이 과부하를 만들기 때문(H17-1의 맞바꿈과 같은 방향). 정리: 피드백이 값어치를 하는 것은 '부하를 직접 조절하는' 개입이고, "
            "그 개입은 실패가 자기 정상 부하 대비 과부하(W1)에 좌우될 때만 효과가 있다. 활동 조절은 경로 재계산이 아닌 이웃 비례 재분배 근사다."
        ),
        verdict="inconclusive",
        evidence=[_EV_REHAB_REVIEW],
        raw_data_note=(
            "마지막 시기 효율(없음/개방/폐루프) · 생존 영역: 연결 유도 W1 0.3333/0.3397/0.3388 · 352.5/351.2/350.4, W2 0.3351/0.3467/0.3486, W3 0.3300/0.3382/0.3391, "
            "W4 0.3680/0.3767/0.3765, 혼합 0.3410/0.3475/0.3465 · 357.3/356.1/355.3. 활동 조절 W1 0.2884/0.2907/0.2996 · 318.4/319.7/324.7, W2 0.3565/0.3570/0.3570, "
            "W3·W4 세 제어기 동일, 혼합 0.3133/0.3189/0.3232 · 332.8/335.9/338.2. 개입 횟수(12시기 합): 활동 조절 W1 개방 84(처음 고른 영역이 죽으면 줄어듦) vs 폐루프 240."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_5_representative_connectome() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-5-representative-connectome-sensitivity",
        title="H17-5 · '정상 부하 지도'는 정상 뇌의 고유한 지도일까, 아니면 집단 대표 커넥톰을 만든 방식의 산물일까?",
        statement=(
            "(외부 검토 의견 8번) 지금의 정상 부하 지도는 33명 HCP 합의(consensus) 이진 행렬 하나의 betweenness다 -- '특정 정상 뇌'가 아니라 '정상 집단 대표 "
            "커넥톰'의 지도다. 개인별 행렬은 없지만, 대표 행렬을 다르게 만들어 볼 수는 있다. 예측: 부하 지도는 밀도·정의를 바꿔도 순위가 대체로 유지되고"
            "(ρ > 0.8), H17의 연쇄 이점도 방향이 유지된다."
        ),
        method=(
            "대표 행렬 3개: 합의 간선 전체(5,059개), 평균 가중치 상위 75%(3,794개)·50%(2,530개)(모두 연결됨). 부하 정의 2개: 이진 betweenness, 가중 betweenness"
            "(길이 = 1/평균 가중치). 대표 행렬마다 자기 부하 지도로 국소 25개 병변 × 전략 5개 연쇄 비교. 합의 행렬에서 실패 문턱이 가중 부하 지도 쪽으로 "
            "λ만큼 섞일 때(정상 뇌 20% 여유 보정)의 이점(backend/scripts/consensus_representation_sensitivity.py)."
        ),
        result_summary=(
            "혼재(예측의 절반 기각) -- '원리'는 버티지만 '지도'는 버티지 않는다. 지도: 합의 75%·50%와의 순위 상관 0.88·0.75지만 상위 5% 허브는 45%·40%만 겹치고, 같은 "
            "행렬의 가중 부하와는 ρ=0.36, 허브 겹침 25%다 -- '어느 영역이 정상 뇌의 부하 허브인가'는 대표 행렬과 부하 정의에 따라 크게 바뀐다. 원리: 각 대표 "
            "행렬이 자기 부하 지도로 재조직·평가하면 정상 부하 지도 기반이 균등 분산보다 어디서나 강하다(+0.185, +0.144, +0.103, 모두 25/25; 무작위 대비도 "
            "25/25). 실패 문턱이 가중 부하 지도 쪽으로 25%·50% 섞여도 이점이 남는다(+0.137, +0.094) -- 임의 중심성(degree·제어성, H17-1: 50%에서 +0.024)보다 "
            "덜 깨진다. 정확한 문장: '실패 문턱이 따르는 부하 지도를 되살리면 연쇄에 강해진다'는 대표 행렬과 무관하게 성립하지만, '그 지도가 이것이다'는 "
            "분석 선택(합의 밀도·가중치 사용)에 따라 달라진다. 따라서 임상에서 쓰려면 지도를 집단 대표 하나로 고정할 수 없고, 개인·측정 방식별 지도와 그 "
            "불확실성(μ, σ)이 필요하다 -- 검토 의견 8·9번이 옳다."
        ),
        verdict="inconclusive",
        evidence=[
            HypothesisEvidenceOut(
                title="Liu, Shafiei, Baillet & Mišić 2023 -- HCP consensus structural connectome (Schaefer-400) data, netneurolab/liu_meg-scfc",
                url="https://github.com/netneurolab/liu_meg-scfc",
            ),
        ],
        raw_data_note=(
            "부하 지도 일치(Spearman / 상위 5% 겹침): 합의~75% 0.877/0.45, 합의~50% 0.750/0.40, 75%~50% 0.825/0.55, 이진~가중 0.364/0.25(가중 부하 0인 영역 6%). "
            "연쇄 생존 m1.2(정상 부하 지도 기반/균등 분산/무작위/허브 집중/없음): 합의 0.895/0.710/0.745/0.492/0.906, 75% 0.876/0.731/0.752/0.455/0.892, 50% 0.867/0.764/0.747/0.577/0.858. "
            "가중 문턱 λ=0.25(m 1.6): 0.958 vs 균등 분산 0.821, λ=0.5(m 2.4): 0.973 vs 0.879, λ=1: 모든 전략 ≈1.0(가중 부하 0인 영역 때문에 보정 배율이 발산)."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_6_synthetic_individual_cohort() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-6-synthetic-individual-envelope",
        title="H17-6 · 개인별 정상 범위(μ, σ)와 Z 점수는 정말 집단 대표 지도보다 나은 길잡이일까? (합성 개인 코호트 사전 검증)",
        statement=(
            "(외부 검토 의견 8·9번) 개인별 연결망이 없으므로(의학적 위험·공개 제공처 없음·개인 연구 단계), 실제 σ의 크기는 주장하지 않고 σ 크기와 무관한 "
            "방법론 질문만 합성 코호트로 묻는다. 예측: Q1 합의 지도는 약한(개인적) 연결을 버려 허브 부하를 과대 추정한다. Q2 영역별 부하 분포는 오른쪽 꼬리다. "
            "Q3 합의·개인 평균 길잡이는 환자 자신의 병전 지도(오라클)보다 조금 못하지만 균등 분산보다 훨씬 낫다. Q4 관측 잡음이 σ를 부풀리고 두 번 촬영으로 보정된다."
        ),
        method=(
            "합성 개인 = 합의 행렬에서 약한 간선 위주로 v만큼 지우고 같은 수를 합의 길이 분포에 맞춰 추가(밀도·길이 분포 유지, v = 0.1/0.2/0.3을 훑음 -- 실제 v는 "
            "모름). 33명으로 μ_i, σ_i와 다수결 합의 지도를 만들고, 따로 뽑은 합성 환자 8명 × 병변 8개에서 재조직 길잡이 5종(합의 지도, μ, Z, 오라클, 균등 분산)을 "
            "'환자 자신의 정상 부하 × 1.2' 문턱 연쇄로 비교. 관측 잡음 = 간선 5% 재배치, 두 번 촬영(backend/scripts/synthetic_individual_cohort.py)."
        ),
        result_summary=(
            "혼재 -- 예상과 다른 결과가 핵심이다. Q1 지지: 합의 지도는 개인 평균과 순위는 비슷하지만(ρ 0.87~0.97) 허브 부하를 1.45~2.17배 과대 추정하고"
            "(개인 차가 클수록 심함), 부하 Gini가 0.17~0.31 높다. Q2 지지: 오른쪽 꼬리(왜도 중앙값 0.58~0.79), log 변환이 63~84% 영역에서 왜도를 줄이지만 "
            "과보정한다 -- Z보다 백분위가 안전. Q3 부분 기각(가장 중요): 개인 평균 μ로 길잡이를 하면 균등 분산과 다를 바 없었고(0.795~0.854 vs 0.801~0.851), "
            "합의 지도보다 오히려 0.04~0.09 낮았다(61~64/64). 평균을 내면 사람마다 다른 위치의 날카로운 허브가 뭉개져, 실제 한 사람의 부하 지도 모양에서 "
            "멀어지기 때문이다. Z 길잡이는 μ보다 낫지만(+0.01~0.05) 합의 지도에는 못 미쳤다. 오라클은 합의 지도보다 +0.04~0.06(63~64/64) -- 개인 차가 0.2 "
            "이상이면 이 '개인화의 이득'이 '부하 지도를 쓰는 이득'(합의 − 균등 분산 0.04)보다 크다. Q4 기각(이 가정 하에서): 5% 잡음은 σ를 거의 부풀리지 "
            "않았고(×0.99~1.02), 두 번 촬영 차이로 빼는 보정은 오히려 σ를 과소 추정했다(×0.79~0.88, 순위 상관 하락). 함의: 개인화에서 필요한 것은 '정상인들의 "
            "평균 부하'가 아니라 '그 사람의 지도 모양'이다. μ·σ로 Z를 만드는 것만으로는 부족하고, 병전 지도를 추정하는 방법(예: 손상 반대편·비손상 영역으로 "
            "개인 지도 복원)이 다음 질문이다. 모든 수치는 합성 생성 가정의 산물이며 실제 σ의 크기를 말하지 않는다."
        ),
        verdict="inconclusive",
        evidence=[],
        raw_data_note=(
            "v=0.1/0.2/0.3 -- 합의 허브 부하 ÷ μ: 1.45/1.79/2.17, 합의~μ ρ 0.965/0.924/0.871, 개인~μ ρ 평균 0.859/0.787/0.721. 연쇄 생존(환자 자신 문턱; 합의/μ/Z/오라클/균등 분산): "
            "0.883/0.795/0.849/0.922/0.801, 0.879/0.834/0.854/0.943/0.839, 0.892/0.854/0.864/0.955/0.851. 변동계수 중앙값 0.41/0.38/0.38(허브 0.19/0.21/0.26). "
            "σ_관측/σ_진짜 1.02/0.99/0.99, σ_보정/σ_진짜 0.79/0.85/0.88."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_7_tau_pareto() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-7-tau-constraint-pareto",
        title="H17-7 · '정상 부하 대비 이탈 제약'의 강도 τ를 연속으로 바꾸면, 회복–강건성–마모 사이에 더 나은 지점이 있을까?",
        statement=(
            "(docs/54 다음 실험 ①) H17 v2의 '과도하게 벗어나지 않도록'을 τ 하나로 둔다: 새 연결을 붙일 때 현재 부하가 자기 정상 용량(정상 부하 × 1.2) 대비 "
            "τ 이하인 영역 중 degree가 가장 큰 곳(빠른 회복)에 붙이고, 없으면 비율이 가장 낮은 곳에 붙인다. τ=0은 정상 부하 지도 기반, τ=∞는 허브 집중과 "
            "간선까지 같다. 예측: P1 τ가 커질수록 효율은 오르고 연쇄 생존은 떨어진다(단조). P2 연쇄 생존 ≥ 0.85를 지키며 효율 차이의 절반 이상을 얻는 중간 τ가 "
            "있다. P3 최적 τ가 기전마다 다르다(연쇄 -> 0, 점진형 W1 -> 큰 τ, W2 -> τ 계열 밖). P4 양 끝점에 지배되지 않는 중간 τ가 있다."
        ),
        method=(
            "τ 11개(0, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2, 3, ∞) + 기준 전략 3개 × 국소 증후군 25개. 지표: 재조직 직후 효율, 연쇄 생존(m=1.2, 1.0), 2차 타격 손실, "
            "W1 점진형·W2만으로 10시기 마모 뒤 효율(반복 3, 공통 난수), 충실도·과부하. 끝점이 기존 전략과 25/25 병변에서 간선까지 같음을 확인"
            "(backend/scripts/tau_pareto.py)."
        ),
        result_summary=(
            "대체로 지지 -- 단 예측과 다른 모양이 핵심이다. P1 부분 기각: 효율은 단조 증가하지만 연쇄 생존(m1.2)은 단조가 아니다 -- τ=0 0.895 -> τ=0.75 0.921"
            "(가장 높음, 재조직 없음 0.906보다도) -> τ=0.9 0.724 -> τ=1.0 0.480으로 τ=0.75~1.0 사이에 절벽이 있다. P2 부분 지지: τ=0.75가 무릎이다 -- 연쇄 "
            "0.921을 지키며 효율 차이의 36%를 얻는다(절반에는 못 미침). 그리고 τ=0.75는 τ=0(정상 부하 지도 기반)을 효율(+0.0026, 21/25)·연쇄 m1.2(+0.026, "
            "21/25)·점진형 W1(+0.009, 24/25)·W2(+0.002, 19/25)에서 모두 이겼다. 대가는 2차 타격 손실(+0.006, 24/25)과, 실패 문턱이 더 낮을 때(m1.0)의 연쇄"
            "(0.570 vs 0.752, 3/25)다. P3 지지: 최적 τ는 m1.2 연쇄 0.75, m1.0 연쇄 0.5, 점진형 W1 1.25(∞가 아니라 중간), W2는 τ 계열 밖(균등 분산 0.3687). "
            "P4 지지: (효율, 연쇄 m1.2) 2축 파레토 = {τ=0.75, τ=2, τ=∞, 무작위}, τ=0과 재조직 없음은 τ=0.75에 지배된다. 해석: 최적의 제약은 '정상 대비 "
            "비율을 최소화'가 아니라 '실패 문턱보다 한 단계 아래 여유선(같은 비율 단위로 문턱 1.0 -> 0.75, 문턱 0.83 -> 0.5)까지는 허브를 써서 빨리 회복'이다. "
            "그런데 문턱을 과대평가하면(실제 문턱이 더 낮으면) 바로 절벽으로 떨어진다 -- 위험이 비대칭이다. 그래서 환자의 허용치를 모를 때는 보수적인 τ(≈0~0.5)가 "
            "안전하고, 허용치를 추정할 수 있을수록 더 공격적인 τ가 이득이다. H17 v2 정교화: '이탈 최소화'가 아니라 '추정한 실패 문턱 아래 여유선까지의 제약'."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "τ: 효율 / 연쇄 m1.2 / m1.0 / 2차 타격 / W1 / W2 -- 0: 0.4435/0.895/0.752/0.0466/0.3594/0.3613, 0.5: 0.4435/0.897/0.754/0.0467/0.3594/0.3612, "
            "0.75: 0.4461/0.921/0.570/0.0529/0.3689/0.3634, 0.9: 0.4480/0.724/0.271/0.0616/0.3729/0.3638, 1.0: 0.4483/0.480/0.267/0.0656/0.3737/0.3633, "
            "1.25: 0.4489/0.491/0.296/0.0716/0.3743/0.3634, 2: 0.4497/0.506/0.296/0.0772/0.3742/0.3637, ∞: 0.4507/0.492/0.314/0.0805/0.3721/0.3632. "
            "기준: 없음 0.4297/0.906/0.505/0.0524/0.3541/0.3477, 균등 분산 0.4488/0.710/0.642/0.0409/0.3039/0.3687, 무작위 0.4496/0.745/0.627/0.0407/0.3435/0.3678."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_8_staged_adaptive() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-8-staged-adaptive-under-threshold-uncertainty",
        title="H17-8 · 허용치(실패 문턱)를 모를 때, 시기별로 전략을 바꾸거나 τ를 천천히 올리면 더 안전할까?",
        statement=(
            "(docs/54 다음 실험 ②) H17-7: τ=0.75가 최적이지만 문턱을 과대평가하면 절벽처럼 무너진다. 실제 문턱 m ∈ {0.9, 1.0, 1.1, 1.2, 1.3, 1.5}을 모른다고 보고, "
            "고정 τ 8개, 단계형 3개(허브→정상 25%·50%, 정상→허브 50%), τ 상승형(0 -> 0.75)을 비교한다. 예측: S1 허브 우선 단계형은 초기 회복이 빠르고 최종 연쇄는 "
            "τ=0에 가깝다. S2 허용치를 모를 때 최적 고정 τ는 0.5 근처다. S3 τ 상승형은 고정 τ=0.75보다 문턱 불확실성에 강하다."
        ),
        method=(
            "국소 증후군 25개 × 정책 12개 + 기준 3개. 회복 곡선(예산 10/25/50/100% 시점 효율), 연쇄 생존 6개 m, 2차 타격, W1·W2 10시기 효율(반복 3). m 균등 사전분포에서 "
            "기대 생존·최악 생존·최대 후회(backend/scripts/staged_adaptive_reorganization.py)."
        ),
        result_summary=(
            "대체로 지지. S2 지지: 기대 연쇄 생존 최적 고정 τ = 0.6(0.795; τ=0 0.784, τ=0.75 0.740). τ=0.6은 6개 m 모두에서 τ=0 이상이고 효율도 약간 높다 -- '허용치를 "
            "모를 때의 안전한 무릎'. τ=0.75는 낮은 문턱(m≤1.0)에서 무너져 최대 후회 0.294. S3 지지: τ 상승형은 고정 τ=0.75보다 기대 0.792 vs 0.740, 최대 후회 0.151 vs "
            "0.294로 훨씬 안전하고, τ=0보다 연쇄 m1.2 +0.011(18/25)·효율 +0.0005(19/25). S1 부분 지지: 허브 우선 단계형(처음 25%)은 초기 회복이 가장 빠르다(예산 25% "
            "시점 +0.0026, 25/25)·점진형 W1도 좋다(+0.005, 25/25). 그러나 최종 연쇄는 τ=0보다 낮다(m1.2 −0.023, m1.0 −0.084). 대신 문턱이 아주 낮을 때(m=0.9) 덜 "
            "무너져(0.434 vs 0.351) 최대 후회가 전체 최소(0.102)다. 허브 단계를 50%로 늘리면 연쇄가 크게 나빠진다(m1.2 −0.082). 최악의 경우만 보면 균등 분산이 최선"
            "(0.503) -- 아주 낮은 문턱에서는 모든 전략이 무너지고 균등 분산이 가장 완만하게 무너진다. 정리: 허용치를 모르면 '고정 τ≈0.6' 또는 '0에서 천천히 올리는 τ'가 "
            "기대값 기준으로 가장 낫고, 최악을 피하려면 '짧은 허브 단계(25%) 후 정상 부하 지도 기반'이 낫다 -- 무엇을 최적화하느냐(기대 vs 최악)에 따라 답이 갈린다."
        ),
        verdict="supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "연쇄 생존 m=0.9/1.0/1.1/1.2/1.3/1.5: τ=0 0.351/0.752/0.855/0.895/0.915/0.939, τ=0.6 0.367/0.769/0.863/0.902/0.923/0.949, τ=0.75 0.210/0.570/0.819/0.921/0.951/0.972, "
            "τ 상승 0.352/0.755/0.870/0.906/0.924/0.946, 허브→정상 25% 0.434/0.668/0.804/0.872/0.914/0.947, 균등 분산 0.503/0.643/0.689/0.710/0.728/0.757, 없음 0.145/0.505/0.840/0.906/0.937/0.983. "
            "예산 25% 시점 효율: τ=0 0.4343, 허브→정상 0.4369, τ=∞ 0.4369."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_9_pair_flow() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-9-pair-flow-decomposition",
        title="H17-9 · 손상 영역이 하던 '역할'(모듈 안 중계 / 모듈 사이 전달)마다 대체 경로가 다를까?",
        statement=(
            "(docs/54 다음 실험 ③, 사용자 정리 2번) 부하를 '어떤 영역 쌍을 중계하나'로 쪼갠다(모듈 안 쌍 / 모듈 사이 쌍, Yeo-7). 예측: F1 병변 뒤 영향받은 쌍의 "
            "효율 손실은 모듈 사이 쌍이 더 크다. F2 대체 경로가 역할마다 다르다(생존 영역의 모듈 안·모듈 사이 부하 증가의 순위 상관 < 0.5). F3 모듈 사이 우회 "
            "부하는 연결자(높은 participation coefficient)가 떠맡는다. F4 정상 부하 지도 기반은 허브 집중보다 모듈 사이 효율 회복이 작지만 역할별 부하 지도 "
            "충실도는 높다."
        ),
        method=(
            "역할별 부하 L_class(v) = Σ_{(s,t)∈class} σ_sv·σ_vt/σ_st(최단 경로 위) -- 두 클래스 합이 전체 betweenness와 오차 10⁻¹²로 같고, 모듈 안 부하가 networkx "
            "부분집합 betweenness와 오차 10⁻¹³로 같음을 확인. 영향받은 쌍 = 정상 뇌에서 최단 경로 중 하나라도 병변을 지나던 쌍. 국소 증후군 25개 × 전략 5개(없음, "
            "τ=0, τ=0.75, τ=∞, 균등 분산)(backend/scripts/pair_flow_decomposition.py)."
        ),
        result_summary=(
            "혼재 -- 역할 구분은 실재하지만 예상한 방식은 아니었다. 병변 영역이 하던 일의 평균 87%는 모듈 사이 중계였고, 그 비율은 병변의 PC와 상관(ρ=0.62). "
            "F1 기각: 영향받은 쌍의 효율 손실은 모듈 사이·모듈 안이 같았다(둘 다 약 2%, 10/25, p=0.98) -- 우회 경로가 많아 손실 자체가 작다. F2 경계선: 자연 "
            "우회(재조직 없음)에서 두 역할의 대체 경로 겹침은 ρ=0.48로 '부분적으로 다른 길'. 그런데 재조직하면 겹침이 커진다(정상 부하 지도 기반 0.61, τ=0.75 "
            "0.54, 허브 집중 0.72, 균등 분산 0.74) -- 재조직이 두 역할을 같은 영역들로 몰아넣는다. F3 기각(예상 밖): 모듈 사이 우회 부하를 떠맡는 것은 연결자가 "
            "아니었다(ρ −0.06, 재조직 후 −0.28~−0.37) -- 새 연결이 PC가 낮은 영역을 통해 모듈 사이 지름길을 만든다. F4 지지: 정상 부하 지도 기반은 허브 집중보다 "
            "모듈 사이 효율 회복이 작고(−0.059, 24/25) 역할별 충실도는 높다(19/25). τ=0.75는 τ=0보다 모듈 사이 회복이 크면서(+0.023, 23/25) 충실도 손실은 없었다 "
            "-- H17-7의 τ 무릎이 '모듈 사이 역할 회복'에서 온다는 단서. 균등 분산은 회복은 τ=0과 같고 역할별 충실도가 크게 낮다(25/25). 허브 집중은 모듈 사이 "
            "부하를 제어(27%)·시각(26%) 네트워크로 몰았다."
        ),
        verdict="inconclusive",
        evidence=[_EV_GRATTON_2012, _EV_WARREN_2014],
        raw_data_note=(
            "영향받은 쌍 효율(정상 대비, 모듈 안/사이): 없음 0.980/0.979, τ=0 1.158/1.121, τ=0.75 1.154/1.144, τ=∞ 1.155/1.180, 균등 분산 1.100/1.118. "
            "역할별 충실도(안/사이): τ=0 0.975/0.982, τ=0.75 0.975/0.977, τ=∞ 0.969/0.970, 균등 분산 0.898/0.864. "
            "ρ(Δ모듈 안, Δ모듈 사이): 없음 0.48, τ=0 0.61, τ=0.75 0.54, τ=∞ 0.72, 균등 분산 0.74. ρ(Δ모듈 사이, PC): 없음 −0.06, τ=0 −0.28, τ=∞ −0.37."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_10_weighted_reorganization() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-10-weighted-strengthening-model",
        title="H17-10 · 가소성을 '새 연결 추가'가 아니라 '기존 약한 연결의 강화'(가중치)로 바꿔도 H17이 유지될까?",
        statement=(
            "(docs/54 다음 실험 ④, 사용자 정리 3번) 지금까지는 이진 연결망 + 새 연결 추가(축삭 발아에 가까움)였다. 실제 가소성은 W_normal -> W_lesion -> "
            "W_reorganized처럼 연결 강도 변화이고, H17-5에서 같은 연결망의 가중 부하와 이진 부하는 순위 상관 0.36뿐이었다 -- docs/54가 꼽은 가장 큰 위험 요인. "
            "예측: G1 τ=0(정상 부하 지도 기반)이 균등 분산·허브 집중보다 가중 연쇄에 강하다. G2 τ 무릎(≈0.75)이 나타난다. G3 충실도-효율 맞바꿈이 유지된다."
        ),
        method=(
            "가중치 = 합의 간선 평균 스트림라인 가중치, 길이 = 1/가중치, 부하 = 가중 betweenness(빠른 구현이 networkx와 오차 0). 생존 영역이 잃은 연결 강도를 3번에 나눠 "
            "변형 A(기존 생존 이웃 강화만) 또는 B(강화 + 배선 제한 안 새 연결)로 더한다. 전략 9개(없음, 무작위, 허브 집중=강도 최대, 균등 분산=가중 부하 최소, τ 5개). "
            "실패 문턱 = m·(정상 가중 부하 + ε), ε = 평균의 1%·10%(정상 부하 0인 영역 24개). 국소 증후군 25개(backend/scripts/weighted_reorganization.py)."
        ),
        result_summary=(
            "핵심 예측 기각 -- 위험 요인이 실제로 드러났다. G1 절반 기각: 정상 부하 지도 기반은 허브 집중보다는 여전히 연쇄에 강하지만(+0.22, 22/25), 균등 분산이 "
            "정상 부하 지도 기반보다 강했다(m1.0 −0.094, 21/25 균등 분산 우세; ε=10%에서는 m1.2도 −0.156, p=0.008). G2 기각: τ 무릎이 없다 -- 연쇄 생존이 τ와 함께 "
            "단조 감소(τ=0 0.685, 0.5 0.669, 0.75 0.544, 1.0 0.452). G3 지지: 충실도와 효율의 맞바꿈은 유지(병변 안 ρ −0.53). 변형 B(강화+발아)에서도 정상 부하 지도 "
            "기반 ≈ 균등 분산(0.716 vs 0.725). 재조직 없음도 연쇄 0.675로 낮다 -- 가중 부하가 소수의 강한 경로(backbone)에 몰려 있어 연결망 전체가 더 취약하다. "
            "결론: '균등화보다 정상 부하 지도'라는 H17의 핵심 구분과 τ 무릎은 가소성 모델(새 연결 발아 vs 기존 연결 강화)에 따라 뒤집힌다. 두 모델에서 공통으로 "
            "살아남는 것은 '허브로 몰지 말 것'(허브 집중이 연쇄에 가장 약함)과 '복원 충실도-효율 맞바꿈'뿐이다. 따라서 H17 v2는 '이진·발아형 재조직 모델에서'라는 "
            "조건을 붙여야 하고, 실제 뇌의 가소성이 어느 쪽에 가까운지(새 경로 형성 vs 기존 경로 강화)가 H17의 성립 여부를 정하는 미해결 질문이다. 왜 뒤집히는지"
            "(강한 경로 골격 위에서 정상 부하 지도 비례 문턱이 어떻게 작동하는지)의 기전은 아직 확인하지 않았다."
        ),
        verdict="not_supported",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "변형 A, ε=1% -- 효율(정상 대비)/연쇄 m1.2/m1.0/충실도: 없음 0.898/0.675/0.339/0.963, 무작위 1.014/0.640/0.443/0.879, 허브 집중 1.056/0.464/0.345/0.884, "
            "균등 분산 0.988/0.728/0.528/0.814, τ=0 0.981/0.685/0.434/0.941, τ=0.5 0.994/0.669/0.449/0.930, τ=0.75 1.032/0.544/0.357/0.906, τ=1.0 1.046/0.452/0.315/0.889. "
            "변형 B: 균등 분산 1.018/0.725/0.570/0.696, τ=0 0.981/0.716/0.435/0.950, τ=0.75 1.052/0.599/0.375/0.896, τ=∞ 1.077/0.511/0.370/0.880. "
            "ε=10%: 균등 분산 0.762/0.529, τ=0 0.606/0.368, 허브 집중 0.422/0.303(연쇄 m1.2/m1.0)."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_11_why_weighted_flips() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-11-why-weighted-model-flips",
        title="H17-11 · 가중치 모델에서 H17이 뒤집힌 원인은 가소성 종류(발아 vs 강화)일까, 가중치 이질성일까, 경로 다중성일까?",
        statement=(
            "(H17-10 후속) 원인 후보: (가) 가소성 종류 -- 새 연결 발아 vs 기존 연결 강화, (나) 가중치 이질성 -- 강한 경로 골격, (다) 경로 다중성 -- 이진 그래프는 "
            "길이가 같은 최단 경로가 많아 부하가 나뉘지만 가중 그래프는 경로가 하나라 부하가 통째로 몰린다. 예측: MX1 (나)가 원인(γ가 작으면 발아·강화 모두 "
            "τ=0 > 균등 분산). MX2 (가)가 원인(발아형은 γ와 무관하게 τ=0 > 균등 분산). J1 (다)가 원인(1% 길이 흔들림으로 경로만 유일하게 만들어도 발아형 이점이 "
            "크게 준다). MH1 기전: 가중 모델에서 정상 부하 지도 기반의 과부하가 골격(정상 부하 상위 10%)에 생긴다."
        ),
        method=(
            "가중치 = 원래 가중치^γ(γ = 0.25, 0.5, 1) × 가소성(강화만 / 발아만) × 전략 4개(균등 분산, τ=0, τ=0.6, 허브 집중) + 재조직 없음, 국소 증후군 12개"
            "(실행 중 PC 메모리 부족으로 10개에서 중단됐다가, 사용자 요청으로 캐시에서 이어서 12개 완료). 경로 다중성: 이진 그래프에 길이 1 + 0.01·U(0,1) 흔들림만 주어 같은 실험(12개). "
            "재조직 양은 잃은 연결 수만큼, 한 번에 잃은 강도의 평균(backend/scripts/plasticity_heterogeneity.py, plasticity_path_multiplicity.py)."
        ),
        result_summary=(
            "혼재 -- 원인은 하나가 아니라 둘의 합이다. 정상 부하 지도 기반 − 균등 분산(연쇄 m1.2): 발아형은 γ=0.25 +0.162(12/12), γ=0.5 +0.132(12/12), γ=1 +0.071"
            "(10/12) -- 이질성이 커질수록 줄지만 뒤집히지는 않는다. 강화형은 γ=0.25 +0.044(11/12), γ=0.5 +0.050(12/12), γ=1 −0.031(4/12; m1.0에서는 −0.088, p=0.03) "
            "-- 처음부터 작고 γ=1에서 뒤집힌다. 즉 가소성 종류(강화)가 이점을 약 0.1 깎고, 가중치 이질성이 또 약 0.1 깎아, 둘이 겹칠 때만 뒤집힌다(MX1·MX2 모두 절반만 맞음). 문턱이 더 "
            "낮으면(m1.0) 강화형에서는 모든 γ에서 균등 분산이 앞선다. J1 기각: 경로만 유일하게 만든 이진 그래프에서도 발아형 이점은 그대로였다(+0.157, 12/12; 이진 "
            "모델 +0.185) -- 경로 다중성은 원인이 아니다. 같은 그래프에서 강화형은 +0.052(m1.2, 12/12)지만 m1.0에서는 −0.048(2/12)이고 τ 무릎이 사라진다(τ=0.6 "
            "−0.075) -- 가중치가 거의 같아도 '강화'만으로 이점이 크게 준다. MH1 부분 지지: 정상 부하 지도 기반은 어느 조건에서나 중간 부하 영역(백분위 ≈0.6)으로 "
            "연결을 보내지만, 강화형에서는 과부하의 부하량 중 골격 영역 몫이 0.20~0.27로 균등 분산(0.11~0.12)·발아형(0.04~0.08)보다 크다 -- 기존 연결을 강화하면 "
            "그 길이 '고속도로'가 되어 주변 고부하 영역으로 교통을 끌어온다. 함의: H17은 '새 경로를 만드는 가소성'일수록, 그리고 연결 강도가 고를수록 성립한다. 기존 "
            "경로 강화가 주된 회복 기전이면 균등 분산이 더 안전하다."
        ),
        verdict="inconclusive",
        evidence=[_EV_MOTTER_LAI],
        raw_data_note=(
            "연쇄 m1.2/m1.0(균등 분산 · τ=0 · τ=0.6 · 허브 집중): γ=0.25 강화 0.639/0.575 · 0.683/0.537 · 0.630/0.452 · 0.425/0.280, 발아 0.686/0.649 · 0.845/0.695 · 0.841/0.688 · 0.657/0.392; "
            "γ=0.5 강화 0.728/0.654 · 0.774/0.634 · 0.715/0.561 · 0.454/0.314, 발아 0.744/0.692 · 0.872/0.705 · 0.861/0.675 · 0.771/0.529; "
            "γ=1 강화 0.741/0.546 · 0.696/0.458 · 0.698/0.377 · 0.494/0.351, 발아 0.748/0.606 · 0.808/0.610 · 0.763/0.525 · 0.656/0.463. "
            "흔들림 이진: 강화 0.642/0.565 · 0.694/0.517 · 0.620/0.350 · 0.404/0.260, 발아 0.733/0.674 · 0.890/0.755 · 0.896/0.738 · 0.527/0.295. "
            "가중 부하 Gini: γ=0.25 0.660, 0.5 0.635, 1 0.620(이진 0.555, 흔들림 0.577)."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_12_time_varying_plasticity() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-12-time-matched-strategy",
        title="H17-12 · 회복 초기엔 기존 연결 강화, 후기엔 새 연결 발아가 주라면, 시기에 맞춰 전략을 바꾸는 것이 나을까?",
        statement=(
            "(H17-11 후속) 문헌(검색 요약 기준): 뇌졸중 직후 수 시간~수 일에는 흥분/억제 균형 변화로 기존 잠재 연결이 드러나 쓰이고(unmasking), 수상돌기 가시 "
            "형성은 1~2주에 최대, 손상 주변 축삭 발아는 첫 2~4주에 늘어난다(Murphy & Corbett 2009; Cirillo et al. 2020). H17-11: 강화형에서는 균등 분산이, "
            "발아형에서는 정상 부하 지도 기반이 안전했다. 예측: T1 '강화 시기 = 균등 분산, 발아 시기 = 정상 부하 지도 기반'으로 맞춘 정책이 끝에서 모든 고정 "
            "전략보다 연쇄에 강하다. T2 초기(강화 위주)에는 균등 분산 계열이 안전하다. T3 반대로 엇갈린 정책이 허브 집중을 빼고 가장 나쁘다."
        ),
        method=(
            "원래 가중치(γ=1). 일정 2개: 순차(앞 50% 강화, 뒤 50% 발아) / 점진(발아 확률 0 -> 1 선형 증가). 정책 6개(τ=0, 균등 분산, τ=0.6, 허브 집중, 맞춤, 엇갈림) + "
            "재조직 없음. 중간(50% 지점)과 끝의 연쇄 생존(m=1.2, 1.0)·가중 효율. 국소 증후군 12개, 정책 간 같은 일정·난수"
            "(backend/scripts/time_varying_plasticity.py)."
        ),
        result_summary=(
            "혼재(긍정 쪽) -- 맞춤 정책은 '어느 문턱에서도 뒤처지지 않는 유일한 정책'이지만 모든 지표에서 1위는 아니다. T1 부분 지지: 순차 일정 끝에서 맞춤은 "
            "m1.2에서 τ=0과 같고(0.807 vs 0.811) 균등 분산보다 크게 높으며(+0.086, 12/12), m1.0에서는 τ=0보다 높고(+0.080, 10/12) 균등 분산과 같다(0.612 vs 0.597). "
            "두 문턱 평균은 맞춤이 최선(0.710; τ=0 0.672, 균등 분산 0.659, 엇갈림 0.693). 점진 일정도 같은 양상(평균 0.699 최선; m1.2 τ=0과 같음, 균등 분산보다 "
            "+0.062 11/12; m1.0 τ=0보다 +0.067 10/12). T2 약한 지지: 초기(강화 위주)에는 균등 분산 계열이 m1.0에서 더 안전(+0.077, 8/12, p=0.07). T3 기각: 엇갈린 "
            "정책은 m1.2에서는 τ=0보다 약하지만(−0.045, 11/12) m1.0에서는 오히려 강해 최악이 아니었다. 효율은 맞춤 0.971로 τ=0(0.961)과 균등 분산(0.998) 사이. "
            "허브 집중은 모든 일정·시점에서 연쇄 최하위(효율은 최고). τ=0.6은 가중 모델에서 τ=0보다 낮았다(H17-10과 일치). 정리: 회복 기전이 시간에 따라 바뀐다면, "
            "그에 맞춰 '초기 분산 → 후기 정상 부하 지도 참조'로 바꾸는 것이 문턱 불확실성까지 고려할 때 가장 균형 잡힌 선택이다. 단 이점의 크기는 작고 일부만 유의하다."
        ),
        verdict="inconclusive",
        evidence=[
            HypothesisEvidenceOut(
                title="Murphy & Corbett 2009 -- Plasticity during stroke recovery: from synapse to behaviour (Nature Reviews Neuroscience 10:861)",
                url="https://www.nature.com/articles/nrn2735",
            ),
            HypothesisEvidenceOut(
                title="Cirillo et al. 2020 -- Post-stroke remodeling processes in animal models and humans (J Cereb Blood Flow Metab)",
                url="https://doi.org/10.1177/0271678X19882788",
            ),
        ],
        raw_data_note=(
            "끝 연쇄 m1.2/m1.0(순차 · 점진): τ=0 0.811/0.532 · 0.790/0.545, 균등 분산 0.721/0.597 · 0.722/0.637, 맞춤 0.807/0.612 · 0.784/0.613, 엇갈림 0.767/0.619 · 0.764/0.592, "
            "τ=0.6 0.778/0.541 · 0.754/0.530, 허브 집중 0.619/0.415 · 0.589/0.442, 재조직 없음 0.689/0.359. 중간(순차): τ=0 0.769/0.447, 균등 분산·맞춤 0.773/0.524. "
            "문헌 시간 경과는 검색 결과 요약으로만 확인(두 원문 사이트가 자동 접근을 막음)."
        ),
        executed_at="2026-10-03",
        is_live_computed=False,
    )


def _h17_13_premorbid_map_estimation() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-13-premorbid-map-from-own-scan",
        title="H17-13 · 환자 자신의 손상 후 연결망으로 손상 전 부하 지도를 추정하면, 개인화의 이득을 되찾을 수 있을까? (합성 코호트 사전 검증)",
        statement=(
            "(H17-6 후속) H17-6: 환자 자신의 병전 지도(오라클)로 길잡이를 하면 집단 합의 지도보다 연쇄 생존이 +0.04~0.06 높지만, 실제 병전 지도는 볼 수 없다. "
            "볼 수 있는 것은 손상 후 촬영한 환자 자신의 연결망(병변에 닿는 연결은 사라짐, 촬영 잡음 포함)과 건강인 참조 코호트다. 병변 밖 연결은 환자 것을 그대로 "
            "쓰고, 병변에 닿는 연결만 참조 코호트 빈도로 채워 병전 지도를 추정한다. 예측: P1 정확도(Spearman)가 0.9 이상으로 합의·평균 지도보다 훨씬 높다. "
            "P2 손상 후 지도를 그대로 쓰면 길잡이로는 오라클보다 확실히 못하다. P3 채워 넣은 추정은 오라클 이득의 70% 이상을 되찾는다. P4 합성 코호트에는 비슷한 "
            "사람끼리 묶이는 구조가 없으므로 k-최근접 방식은 이점이 없다."
        ),
        method=(
            "docs/53의 합성 개인(생성 가정 G1), 개인 차 v=0.1/0.2/0.3, 환자 8명 × 병변 8개, 참조 = 나머지 33명(한 명씩 빼기). 손상 후 촬영 = 병전 연결 + 간선 5% "
            "잡음(G2). 추정기: 합의, 평균 μ, 손상 후 지도, 채워 넣기(전체 참조 / 가장 비슷한 5명), 5명 부하 평균, 진단용(잡음 0%, 2%, 두 번 촬영 평균, 합의 쪽 "
            "당기기), 오라클, 균등 분산. 평가: 병변 밖 영역의 Spearman·상위 5% 허브 일치·|log 비율| 중앙값, 그리고 추정 지도 × 1.2 길잡이로 재조직한 뒤 환자 "
            "자신의 병전 부하 × m(1.2, 1.0) 문턱 연쇄 생존(backend/scripts/premorbid_map_estimation.py). 같은 스크립트가 MICA_DIR로 실제 개인 행렬도 읽는다."
        ),
        result_summary=(
            "혼재 -- 방법은 맞지만 촬영 잡음에 매우 민감하다. P1 지지: 채워 넣은 추정의 Spearman 0.92(합의 0.63~0.84), 허브 일치 0.74~0.78(합의 0.44~0.69). "
            "P3 기각(5% 잡음): m=1.2에서 되찾은 이득은 v=0.1 −139%, 0.2 −21%, 0.3 +14%로 합의 지도보다 못하거나 비슷했다. 그러나 잡음을 줄이면 급격히 좋아진다 "
            "(v=0.2: 5% −21% -> 2% +26% -> 0% +109%, 잡음 0%는 오라클과 같은 수준). 즉 개인화가 이득이 되려면 지도 정확도가 Spearman 약 0.98 이상이어야 하고, "
            "0.92~0.96으로는 부족하다. 두 번 촬영 평균은 조금만 나아졌다(v=0.3 +14% -> +23%). 합의 쪽으로 당기기는 m=1.2에서 합의보다 조금 낫지만(+22~29%, "
            "v≥0.2) m=1.0에서는 합의의 약점을 물려받는다. 반대로 문턱이 낮으면(m=1.0) 합의 지도가 크게 무너지고(0.52~0.62; 허브 부하 과대 추정 탓으로 보임) "
            "채워 넣은 추정은 오라클 이득의 61~90%를 되찾지만, 균등 분산도 같은 수준(0.72~0.76)이다. P2 지지(손상 후 지도는 채워 넣은 추정보다 조금 못함). "
            "P4 지지(k-최근접 ≈ 전체 참조). 정리: '그 사람의 지도 모양'은 손상 후 촬영으로 거의 복원되지만, 실제로 쓸모가 있는지는 반복 촬영 잡음의 크기가 "
            "결정한다. 실제 트랙토그래피의 반복 촬영 신뢰도를 재는 것이 다음 순서다. "
            "[실제 데이터 MICA-MICs 50명, 2026-10-04] 한 명씩 빼기(참조 49명) × 병변 8개: 실제 개인 차는 합성 가정보다 훨씬 커서 "
            "개인화의 이득(오라클 − 합의)이 m=1.2 +0.135(0.859 vs 0.724), m=1.0 +0.089로 합성(+0.04~0.06)의 2~3배였다. 같은 병목이 "
            "재현됐다: 채워 넣은 지도는 허브 일치 0.57 -> 0.83으로 정확하지만 5% 잡음에서는 되찾은 이득 −17%(m1.0 −10%), 2%에서 +12%, "
            "0%에서 +92%. μ는 합의보다 못했고(−29%) k-최근접은 이점이 없었다. 합성에서 본 '합의 지도의 m=1.0 붕괴'는 실제에서는 "
            "나타나지 않았다. 예상 밖으로 두 번 촬영 평균·합의 쪽 당기기가 한 번 촬영보다 나빴다(원인 미확인)."
        ),
        verdict="inconclusive",
        evidence=[
            HypothesisEvidenceOut(
                title="Royer et al. 2022 -- MICA-MICs: An open MRI dataset for multiscale neuroscience (Scientific Data 9:569)",
                url="https://www.nature.com/articles/s41597-022-01682-y",
            ),
        ],
        raw_data_note=(
            "연쇄 m1.2/m1.0 (v=0.1 · 0.2 · 0.3): 합의 0.879/0.617 · 0.885/0.580 · 0.890/0.521, 채워 넣기 0.824/0.719 · 0.873/0.746 · 0.899/0.746, "
            "손상 후 지도 0.818/0.708 · 0.863/0.727 · 0.889/0.731, μ 0.789/0.690 · 0.832/0.722 · 0.854/0.743, 잡음 2% 0.856/0.735 · 0.900/0.746 · 0.918/0.734, "
            "두 번 촬영 0.819/0.709 · 0.879/0.748 · 0.905/0.759, 합의 당기기 0.869/0.714 · 0.902/0.677 · 0.904/0.611, 잡음 0% 0.926/0.780 · 0.948/0.737 · 0.952/0.716, "
            "오라클 0.918/0.784 · 0.943/0.780 · 0.955/0.772, 균등 분산 0.798/0.719 · 0.834/0.746 · 0.855/0.760. Spearman: 채워 넣기 0.92, 잡음 2% 0.96, 두 번 촬영 "
            "0.95, 잡음 0% 0.98~0.99. 잡음 5%는 생성 가정이며 실제 반복 촬영 잡음 크기는 모른다. 잡음이 '비율 최소 후보 선택'에서 과대 추정된 노드를 고르게 "
            "만든다는 설명은 추정이며 직접 확인하지 않았다. 허용 배수를 일괄로 낮추는 비교군은 정렬 키 구조상 순서가 거의 바뀌지 않아 결과에서 뺐다. "
            "MICA-MICs(m1.2/m1.0): 합의 0.724/0.644, μ 0.684/0.617, 손상 후 0.696/0.629, 채워 넣기 0.701/0.635, 잡음 2% 0.739/0.659, "
            "두 번 촬영 0.676/0.615, 당기기 0.677/0.609, 잡음 0% 0.848/0.719, 오라클 0.859/0.733, 균등 분산 0.660/0.611. 데이터: OSF j532r "
            "micapipe_MICs_v1.1.zip에서 Schaefer-400 sc·edgeLength 100개만 범위 요청으로 받아 git-annex MD5 100/100 일치 확인, 416 배치에서 "
            "피질 400개(내측벽 14·215 제외), 영역 순서는 Liu 거리와 ρ=0.82(무작위 −0.01)로 확인, 개인별 가중치 상위 5,059개로 이진화. "
            "400건은 50명 × 병변 8개로 독립이 아니다."
        ),
        executed_at="2026-10-03",
        is_live_computed=False,
    )


def _h17_2_mixed_failure_recovery() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-2-mixed-failure-parameter-recovery",
        title="H17-2 · 손상 기전 혼합 비율(α·W1 + β·W2 + γ·W3 + δ·W4)을 환자 종단 데이터로 되찾을 수 있을까? (가상 환자 검증)",
        statement=(
            "(외부 검토 의견 7번) 실제 뇌 손상은 W1·W2 하나로 단순화할 수 없으므로 혼합 모델로 두고 비율을 임상 데이터에 맞춘다. 실제 임상 데이터가 없으므로 그 "
            "'전 단계'를 가상 데이터로 검증한다: 정답 비율로 가상 환자를 만들고 같은 모델로 적합해 정답을 되찾는가(모수 회복). 예측: 영역별 종단 손상 자료가 "
            "있으면 40명 정도로 회복된다. 관측 잡음이나 빠진 기전이 있으면 체계적으로 틀린다. 전역 효율 곡선만으로는 구별이 어렵다."
        ),
        method=(
            "위험 = 정규화된 W1(자기 정상 부하 대비 과부하²) + W2(절대 부하) + W3(무작위) + W4(구조적 단절: 원래 이웃 상실 비율), 각 항은 정상 뇌에서 평균 1. "
            "가상 환자: 증후군 병변 또는 인접 무작위 병변, 10시기. 관측: 영역별 손상 시점(종단 위축 지도에 해당), 잡음 = 민감도 80%·시기당 거짓 손상 0.1%. "
            "적합: θ=s·w(≥0)로 오목한 로그우도 최대화, 환자 단위 bootstrap 200회 95% CI. 진실 9개 × 환자 10/40명 × 3회, 잡음 없는 기준선, W4 오지정 실험, "
            "잡음 모델을 넣은 적합 비교(backend/scripts/mixed_failure_model.py)."
        ),
        result_summary=(
            "대체로 지지 -- 단 임상 적용 전 반드시 풀어야 할 조건 두 개가 드러났다. ① 관측이 정확하면 회복된다: 40명·잡음 없음에서 최대 오차 0.02~0.12, CI "
            "포함률 100%(예: 진실 W1 0.5·W3 0.5 -> 0.56·0.44). ② 현실적 관측 잡음이 있으면 W3(무작위) 쪽으로 0.2~0.3 치우치고(순수 W2 -> 0.77·W3 0.23), "
            "환자를 10명에서 40명으로 늘려도 줄지 않는다(분산이 아니라 편향). 무작위 거짓 위축은 '무작위 노화'와 구별되지 않기 때문. 그러나 잡음 모델(민감도·"
            "거짓 양성률)을 우도에 넣으면 대부분 사라진다(순수 W2 0.80 -> 0.98, 고른 혼합 W3 0.46 -> 0.32(진실 0.33), 순수 W1 0.75 -> 0.91). ③ 기전이 빠지면 "
            "엉뚱한 곳으로 간다: W4(단절)가 30% 섞였는데 W1~W3로만 적합하면 W3가 0.68로 부풀고(포함률 11%), W4를 넣어도 잡음 하에서는 과소추정(0.14, 포함률 "
            "67%). ④ 전역 효율 곡선만으로는 W1과 W3를 구별할 수 없다(10시기 효율 유지율 0.904 vs 0.901, 반복 간 SD 0.002). 결론: 임상 데이터에 맞추려면 "
            "(a) 영역별 종단 자료, (b) 건강인 반복 촬영으로 잰 관측 잡음, (c) 단절·대사 등 빠진 기전의 후보 항이 필요하다."
        ),
        verdict="supported",
        evidence=[
            HypothesisEvidenceOut(
                title="de Haan, Mott, van Straaten, Scheltens & Stam 2012 -- Activity dependent degeneration explains hub vulnerability in Alzheimer's disease (PLOS Comput Biol 8:e1002582)",
                url="https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1002582",
            ),
        ],
        raw_data_note=(
            "40명·잡음 평균 추정(W1, W2, W3): 진실 W1 -> 0.77/0.01/0.22, W2 -> 0.00/0.77/0.23, W3 -> 0.03/0.01/0.97, 고른 혼합 -> 0.32/0.27/0.41, mixA(0.6/0.3/0.1) -> "
            "0.51/0.24/0.25. 10명·잡음: W1 -> 0.62/0.10/0.28. 잡음 없음 40명: W1 -> 0.97/0.00/0.03, mixA -> 0.67/0.33/0.00. W4 오지정(진실 0.3/0.2/0.2/0.3): K3 "
            "0.12/0.20/0.68, K4 0.16/0.17/0.53/0.14; (진실 0.1/0.2/0.1/0.6): K3 0.12/0.29/0.59, K4 0.15/0.21/0.27/0.37. 잡음 인지 적합(2회 평균): W1 0.91/0.01/0.08, "
            "mixA 0.51/0.25/0.24."
        ),
        executed_at="2026-10-02",
        is_live_computed=False,
    )


def _h17_14_real_test_retest_noise() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-14-real-test-retest-scan-noise",
        title="H17-14 · 실제 반복 촬영 잡음은 얼마나 크고, 손상 후 촬영으로 병전 지도를 개인화할 수 있는 수준인가?",
        statement=(
            "(H17-13 후속) H17-13에서 손상 후 촬영으로 병전 지도를 채워 넣는 방법은 촬영 잡음 ε에 막혔다(MICA 50명: ε 5% −17%, 2% +12%, 0% +92%). "
            "그 ε=5%는 가정이었다. 실제 반복 촬영으로 ε를 재면, 개인화가 이득이 되는 쪽(ε ≤ 2%)인지 아닌지 정해진다. "
            "예측: 반복 촬영의 차이는 사람 사이 차이보다 훨씬 작다(교체율 비 ≤ 0.3)."
        ),
        method=(
            "Zenodo 14017270(Barjuan 2024, HCP 반복 촬영 표본 44건, Lausanne 분할). 세션 표시가 없어 집단 평균을 뺀 연결 패턴의 상호 최근접으로 반복 촬영 "
            "20쌍을 추론(layer 1·2에서 같은 짝, z ≥ 3.4). Liu 합의와 같은 밀도 6.34%로 이진화해 짝 사이·사람 사이의 간선 교체율, 부하(매개 중심성) Spearman, "
            "상위 5% 허브 일치를 잼. MICA 50명에 docs/59 잡음 perturb(ε)를 독립적으로 두 번 넣은 곡선과 비(반복/사람 사이)로 맞춰 MICA 척도의 ε를 구함 "
            "(backend/scripts/test_retest_noise.py). 이어 ε=10%로 docs/59 실제 분석을 다시 돌림(PREMORBID_EPS=0.10). 가중 매개 중심성·강도의 재현성도 비교."
        ),
        result_summary=(
            "기각 -- 같은 사람을 다시 찍은 차이가 다른 사람끼리의 차이와 거의 같다. 교체율 반복 0.334 vs 사람 사이 0.368(비 0.91, layer 2 0.88, 밀도 6~15%에서 "
            "0.91~0.92), 부하 Spearman 반복 0.60 vs 사람 사이 0.53. MICA 척도로 옮긴 촬영 1회 잡음은 ε ≈ 9~17%(교체율 비 17%, 부하 불신뢰도 비 9%)로 "
            "가정 5%의 2~3배다. ε=10%로 다시 돌리면 채워 넣기의 되찾은 이득이 m=1.2 −35%, m=1.0 −27%(5%에서 −17%/−10%)로, 환자 자신의 촬영을 쓰는 모든 "
            "추정기가 합의 지도보다 나쁘고 균등 분산(−47%/−37%)에 가까워진다. 가중 매개 중심성(불신뢰도 비 0.85)과 강도(0.79)도 개인 신호 비율이 거의 같다. "
            "함의: (1) 촬영 1회로는 병전 지도 개인화가 안 된다. (2) H17-13의 '실제 개인화 이득 +0.135'는 각자의 촬영 1회를 참 연결망으로 놓은 값이라, 촬영에서 "
            "보이는 개인 차의 대부분이 측정 잡음이면 과대 추정일 수 있다(파이프라인이 달라 비가 그대로 옮겨진다는 것은 가정). (3) 지금은 집단 합의 지도가 "
            "가장 나은 길잡이다."
        ),
        verdict="not_supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Barjuan, Soriano & Serrano 2024 -- Optimal navigability of weighted human brain connectomes in physical space (NeuroImage 297:120703); 데이터 Zenodo 14017270",
                url="https://zenodo.org/records/14017270",
            ),
        ],
        raw_data_note=(
            "HCP 20쌍(짝 없는 5·8·16·35번 제외). layer 1(462): 교체율 0.334±0.011 / 0.368±0.012, 부하 ρ 0.603 / 0.529, 허브 0.56 / 0.53. "
            "layer 2(233): 0.244 / 0.277, ρ 0.632 / 0.561, 허브 0.73 / 0.71. MICA 모의(두 사본): ε 2% 교체율 0.039 ρ 0.853, 5% 0.094 / 0.765, "
            "10% 0.178 / 0.699, 20% 0.324 / 0.640, 사람 사이 0.318 / 0.650. ε=10% 재실행 연쇄 m1.2/m1.0: 합의 0.724/0.644, 채워 넣기 0.677/0.620, "
            "손상 후 0.673/0.615, 두 번 촬영 0.662/0.608, 당기기 0.662/0.601, μ 0.684/0.617, 5명 평균 0.698/0.627, 균등 분산 0.660/0.611, 오라클 0.859/0.733. "
            "가중(layer 2): 가중 매개 ρ 0.604 / 0.532, 강도 0.777 / 0.716. 짝은 추론이며 원 자료에 짝 정보는 없다. 400건은 50명 × 병변 8개로 독립이 아니다."
        ),
        executed_at="2026-10-06",
        is_live_computed=False,
    )


def _h17_15_lausanne_retest_premorbid() -> HypothesisRecordOut:
    return HypothesisRecordOut(
        id="h17-15-retest-pairs-premorbid-without-noise-assumption",
        title="H17-15 · 같은 사람의 다른 날 촬영(손상 전 촬영)이 있으면 개인화의 이득을 되찾을 수 있을까? (반복 촬영 짝, 잡음 가정 없음)",
        statement=(
            "(H17-14 후속) H17-13·14는 잡음 모델 perturb(ε)와 파이프라인 비율 환산에 기댔다. 같은 사람의 두 실제 촬영을 그대로 '참(병전)'과 '관측'으로 쓰면 "
            "잡음 가정이 필요 없다. 오라클은 '참 = 촬영 1회'로 정의되므로, 다른 날 찍은 손상 전 촬영이 되찾는 오라클 이득의 몫은 개인화 이득 중 두 촬영에 "
            "공통인(안정된) 개인 차의 몫이다. 예측: 손상 전 촬영은 오라클 이득의 절반 이상을 되찾는다."
        ),
        method=(
            "Zenodo 14017270 HCP, Lausanne layer 1(462영역), H17-14에서 추론한 반복 촬영 20쌍 × 양방향 = 40건, 병변 8개씩 320건. 참 = 한 촬영(재조직·연쇄도 이 "
            "연결망 위), 손상 후 관측 = 다른 촬영에서 병변 연결을 지운 것, 참조 = 나머지 42건. 병변은 docs/50 국소 병변 8개와 같은 증후군을 Desikan 해부 이름으로 "
            "다시 정의. 추정기: 합의, μ, 손상 후 지도, 채워 넣기, 손상 전 촬영(다른 촬영 그대로), 오라클, 균등 분산. 평가는 H17-13과 같음(추정 지도 × 1.2 길잡이, "
            "참 부하 × m 문턱 연쇄). 95% 구간은 짝 단위 부트스트랩(backend/scripts/lausanne_retest_premorbid.py)."
        ),
        result_summary=(
            "기각 -- 손상 전 촬영이 있어도 개인화 이득은 0이다. 오라클 이득은 m=1.2 +0.078 [+0.075, +0.081], m=1.0 +0.036으로 뚜렷하지만, 같은 사람의 "
            "다른 날 촬영은 m=1.2 −0.006 [−0.008, −0.003], m=1.0 +0.001 [−0.004, +0.007]로 그 이득의 −8% / +3%만 되찾는다. 8개 병변 모두 같다. 즉 오라클 "
            "이득은 두 촬영에 공통인 개인 차가 아니라 그 촬영 1회에만 있는 특징(잡음)에서 나온다(연쇄 문턱이 그 촬영의 부하로 정해지므로). H17-13의 MICA "
            "'실제 개인화 이득 +0.135'도 같은 이유일 가능성이 크다. 채워 넣기(−7% / +5%)와 손상 후 지도(−10% / +1%)도 합의와 거의 같다. 지도 정확도에서도 "
            "합의(ρ 0.66)가 같은 사람의 다른 촬영(ρ 0.60)보다 낫다. H17-14의 환산(ε=10%에서 −0.047)보다 해는 훨씬 작아(−0.006), perturb 모델이 해를 과장했다. "
            "결론: 현재 트랙토그래피로는 개인 정상 부하 지도를 잴 수 없고, H17의 실용 형태는 집단 합의 지도 기반 길잡이다."
        ),
        verdict="not_supported",
        evidence=[
            HypothesisEvidenceOut(
                title="Barjuan, Soriano & Serrano 2024 -- Optimal navigability of weighted human brain connectomes in physical space (NeuroImage 297:120703); 데이터 Zenodo 14017270",
                url="https://zenodo.org/records/14017270",
            ),
        ],
        raw_data_note=(
            "연쇄 m1.2/m1.0: 합의 0.840/0.715, μ 0.811/0.706, 손상 후 0.832/0.715, 채워 넣기 0.834/0.716, 손상 전 촬영 0.834/0.716, 오라클 0.917/0.750, "
            "균등 분산 0.809/0.711. Spearman: 합의 0.66, μ 0.70, 손상 후 0.60, 채워 넣기 0.61, 손상 전 촬영 0.60. 병변 크기(Lausanne): 대뇌색맹 31, 운동맹 21, "
            "베르니케 14, 집행기능 36, 전행성 기억상실 10, 발린트 27, 복측 동시실인 16, 안톤 14. 이진화 상위 6,751개(밀도 6.34%), 거리 = 촬영 공간 무게중심 "
            "좌표(근사). 짝은 추론이고, 참조 42건에 다른 사람의 두 촬영이 모두 들어 있다. 짝 20개라 ±0.01 수준의 작은 이득은 가르지 못한다."
        ),
        executed_at="2026-10-06",
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
        _h16_1_1_hubness_robustness(),
        _h16_1_2_which_hubness(),
        _h16_2_concentrated_recovers_efficiency(),
        _h16_2_1_short_vs_long_term(),
        _h16_3_distributed_evens_load(),
        _h16_4_distributed_resists_second_hit(),
        _h16_5_capacity_aware_distribution(),
        _h16_5_1_capacity_definition_sensitivity(),
        _h16_5_2_headroom_not_algorithm_artifact(),
        _h16_5_3_null_distribution(),
        # docs/52: 외부 검토 의견에 따라 H16을 다시 쓴 중심 가설 H17과 후속 검증
        _h17_normative_load_map_reorganization(),
        _h17_1_restoring_the_load_map(),
        _h17_2_mixed_failure_recovery(),
        _h17_3_strategy_map(),
        _h17_4_closed_loop_rehab(),
        # docs/53: 집단 대표 커넥톰의 한계와 개인별 정상 범위 사전 검증
        _h17_5_representative_connectome(),
        _h17_6_synthetic_individual_cohort(),
        # docs/55: 제약 강도 τ 파레토
        _h17_7_tau_pareto(),
        # docs/56: 다음 실험 ②③④
        _h17_8_staged_adaptive(),
        _h17_9_pair_flow(),
        _h17_10_weighted_reorganization(),
        # docs/57: 뒤집힘의 원인
        _h17_11_why_weighted_flips(),
        # docs/58: 시간 가변 가소성
        _h17_12_time_varying_plasticity(),
        # docs/59
        _h17_13_premorbid_map_estimation(),
        # docs/60
        _h17_14_real_test_retest_noise(),
        # docs/61
        _h17_15_lausanne_retest_premorbid(),
    ]
