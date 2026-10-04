"""연구소(Lab) API 응답 모델 (docs/34+). `app/domain/schemas.py`와 의도적으로
분리 — 이 프로젝트의 "실제 출처만" 확정 데이터와, 이 서브패키지의 "실제
계산값이지만 해석은 가설" 탐구 데이터를 스키마 수준에서도 구분해 둔다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.schemas import Direction, SimulationEvent

SpeciesId = str  # "c_elegans" | "drosophila_<circuit>" | "human_macro" -- 자유 문자열, 고정 목록은 topology.py의 SPECIES_REGISTRY 참고


class CentralityEntryOut(BaseModel):
    node_id: str
    node_label: str = Field(description="사람이 읽을 수 있는 이름 (뉴런 이름 또는 해부학적 라벨).")
    degree_centrality: float
    betweenness_centrality: float
    pagerank: float
    combined_score: float = Field(description="세 지표를 0-1로 정규화해 평균한 값 -- 순위 매김용, 그 자체로 생물학적 의미를 갖는 표준 지표는 아님.")
    already_in_curated_literature: bool = Field(
        description="이 프로젝트가 이미 실제 문헌으로 큐레이션한 데이터(웜 고전 절제 연구, 인간 질환 연관)에 이 노드가 등장하는지 -- "
        "false라고 해서 문헌이 실제로 이 노드를 안 다뤘다는 뜻은 아니다. 이 프로젝트 안에 없을 뿐."
    )


class TopologyReportOut(BaseModel):
    species_id: str
    label_ko: str
    node_count: int
    edge_count: int
    is_directed: bool
    density: float
    average_clustering: float
    average_shortest_path_length: float | None
    small_world_sigma: float | None = Field(
        description="sigma > 1이면 '작은세상' 특성을 시사하는 것으로 문헌에서 관례적으로 해석하지만, "
        "이 값 하나로 판정을 내리지 않는다 -- 참고 수치."
    )
    small_world_skipped_reason: str | None = Field(description="그래프가 너무 커서 계산을 건너뛴 경우의 실제 이유.")
    betweenness_is_approximate: bool = Field(description="그래프가 커서 정확 계산 대신 표준 샘플링 근사를 썼는지.")
    is_fully_connected: bool
    modularity_q: float
    community_sizes: list[int] = Field(description="실제 탐지된 커뮤니티(모듈)들의 크기, 큰 순.")
    top_candidates: list[CentralityEntryOut]
    curated_literature_note: str = Field(description="'already_in_curated_literature'가 정확히 무엇과 비교한 것인지 설명하는 문구 (종마다 다름).")
    honesty_note: str = Field(description="이 보고서의 해석적 한계에 대한 고정 문구 -- 모든 종에서 동일.")


class VirtualExperimentRequest(BaseModel):
    direction: Direction
    silenced_neuron_ids: list[str] = Field(
        default_factory=list,
        description="자유롭게 고른 실제 뉴런 id 목록 -- AblationPanel의 7개 고전 절제 연구로 제한되지 않음. "
        "이 데이터셋에 실재하지 않는 id는 조용히 무시됨(지어내지 않음).",
    )


class VirtualExperimentResponse(BaseModel):
    direction: Direction
    silenced_neuron_ids: list[str] = Field(description="실제로 적용된 억제 목록 -- 존재하지 않는 id는 걸러진 뒤의 값.")
    experiment_events: list[SimulationEvent]
    baseline_events: list[SimulationEvent] = Field(description="같은 방향, 억제 없음 -- 비교 기준선(같은 습관화 상태에서 계산).")
    experiment_neurons_fired: list[str] = Field(description="실험 조건에서 실제로 발화한 뉴런 id들(첫 등장 순).")
    baseline_neurons_fired: list[str] = Field(description="기준선(억제 없음)에서 실제로 발화한 뉴런 id들.")
    silenced_but_would_have_fired: list[str] = Field(
        description="억제한 뉴런 중, 기준선에서는 실제로 발화했던 것들 -- 이 억제가 실제로 무언가를 바꿨다는 가장 직접적인 신호."
    )
    honesty_note: str


class ExploreChatRequest(BaseModel):
    message: str


class ExploreChatCitation(BaseModel):
    url: str
    title: str


class ExploreChatResponse(BaseModel):
    answer: str
    citations: list[ExploreChatCitation] = Field(
        description="실제 OpenAI web_search 도구가 반환한 URL 인용 -- 지어낸 출처가 아님. "
        "OpenAI 이용약관상 이 목록은 항상 클릭 가능하게 표시돼야 함."
    )
    used_web_search: bool = Field(description="이번 답변에서 모델이 실제로 웹 검색 도구를 호출했는지 -- 안 했으면 자체 지식만으로 답한 것.")
    honesty_note: str


class GeneCandidateOut(BaseModel):
    symbol: str
    chromosome: str
    map_location: str
    description: str | None
    distance_fraction: float = Field(
        description="같은 염색체 위에서 시드 유전자와의 실제 거리(0-1, 염색체 전체 길이 대비 cytoband 중점 간 거리) -- 작을수록 물리적으로 가까움."
    )
    go_tags: list[str]


class GenePathwayReportOut(BaseModel):
    seed_symbol: str = Field(description="이미 이 프로젝트가 실제 경로(BDNF 또는 Arc/Arg3.1)로 다루는 시드 유전자.")
    pathway_label: str
    seed_chromosome: str
    seed_map_location: str
    candidates: list[GeneCandidateOut] = Field(description="같은 염색체에서 시드 유전자와 물리적으로 가장 가까운 실제 유전자들 -- 위치 후보 유전자(positional candidate gene) 접근.")
    honesty_note: str


class VirtualOrganismPoseIn(BaseModel):
    """수동 조종(docs/45) -- 개체는 브라우저에서 실시간(실측 속도)으로 움직이고,
    뇌 회로는 이 요청이 보낸 "지금 위치"에서 감각을 받아 계산된다. 실제
    Brian2 틱 계산에 수 초가 걸리기 때문에, 이동을 틱 결과에 묶어 두면 조종이
    반응하지 않는다(docs/44의 실제 문제) -- 이동과 신경 계산을 분리한 이유."""

    x_um: float
    y_um: float
    z_um: float = Field(default=0.0, ge=0.0, description="바닥 위 높이(초파리 비행). 웜은 항상 0.")
    heading_deg: float = Field(ge=-720.0, le=720.0)
    elapsed_bio_ms: float = Field(
        default=100.0,
        gt=0.0,
        le=120000.0,
        description="직전 신경 계산 이후 흐른 생물학적 시간(ms, 배속 반영). 웜의 농도 변화율을 틱(100ms)당으로 환산하는 데 쓴다.",
    )
    path: list[list[float]] = Field(default_factory=list, max_length=800, description="직전 요청 이후 지나온 경로 [x_um, y_um] -- 궤적/이동거리 기록용.")
    run_id: int | None = Field(
        default=None,
        description="이 위치가 속한 기록(다시 시작마다 새 번호). 다르면 409 -- 다시 시작 직전에 보낸 옛 위치가 새 기록을 덮어쓰지 않게.",
    )


class VirtualOrganismSourceIn(BaseModel):
    x_um: float
    y_um: float


class VirtualOrganismReflexOut(BaseModel):
    """뇌가 반전/회피를 결정했을 때 몸이 할 반사 동작. 수동 조종에서 '반사
    반응 허용'이 켜져 있으면 프론트가 결과를 받은 시점의 실제 위치에 적용한다."""

    back_um: float
    new_heading_deg: float


class VirtualOrganismStatsOut(BaseModel):
    bio_time_s: float = Field(description="이번 기록(다시 시작 또는 냄새원 이동 이후)에서 흐른 생물학적 시간.")
    distance_mm: float
    auto_ticks: int
    manual_ticks: int
    reorient_decisions: int = Field(description="뇌가 반전/회피를 결정한 횟수(수동 조종 중 적용 안 된 것 포함).")
    closest_approach_mm: float
    reached_at_s: float | None = Field(default=None, description="웜: 광원 근처에 처음 도달한 생물학적 시각. 초파리는 해당 없음.")


class VirtualWormNeuronActivityOut(BaseModel):
    neuron_id: str
    spike_count: int = Field(description="이번 틱 동안 이 뉴런이 실제로 발화한 횟수.")


class VirtualWormTickOut(BaseModel):
    tick: int
    x_um: float
    y_um: float
    heading_deg: float
    concentration: float = Field(description="이번 틱이 끝난 위치에서의 유인물질 농도(0-1, 가우시안 근사).")
    delta_concentration: float = Field(description="틱(100ms)당으로 환산한 농도 변화 -- 음수(감소)일 때만 AWC/ASE에 감각 자극이 들어간다.")
    event: Literal["run", "pirouette"] = Field(description="뇌가 이번 틱에 결정한 행동 -- 전진 유지(run) 또는 반전+재정향(pirouette).")
    forward_spikes: int = Field(description="이번 틱 동안 AVBL/AVBR(전진 명령 인터뉴런)이 실제로 발화한 횟수 합.")
    reverse_spikes: int = Field(description="이번 틱 동안 AVAL/AVAR(후진 명령 인터뉴런)이 실제로 발화한 횟수 합.")
    sensory_activity: list[VirtualWormNeuronActivityOut] = Field(description="이번 틱 동안 AWC*/ASE* 감각뉴런의 실제 발화 수.")
    reached_source: bool
    control: Literal["auto", "manual"] = Field(
        default="auto",
        description="auto면 event대로 실제 이동, manual이면 이동은 사용자 조종이고 event는 뇌의 결정(반사는 reflex로 제안).",
    )
    reflex: VirtualOrganismReflexOut | None = None
    bio_time_s: float = 0.0


class VirtualWormStateOut(BaseModel):
    tick: int
    x_um: float
    y_um: float
    heading_deg: float
    concentration: float
    arena_radius_um: float
    source_x_um: float
    source_y_um: float
    gradient_sigma_um: float
    trail: list[list[float]] = Field(description="최근 이동 경로 [x_um, y_um] 목록(메모리 상한으로 최근 구간만 유지).")
    reached_source: bool
    stats: VirtualOrganismStatsOut
    run_id: int
    honesty_note: str


class VirtualWormStepRequest(BaseModel):
    n_ticks: int = Field(default=1, ge=1, le=20, description="한 번의 호출로 진행할 틱 수 -- 실시간이 아니라 시뮬레이션 시간을 가속하기 위한 배치 처리.")
    manual: VirtualOrganismPoseIn | None = Field(default=None, description="주면 수동 조종 틱(그 위치에서 감각 1회 계산, n_ticks는 1이어야 함).")

    @model_validator(mode="after")
    def _manual_is_single_tick(self):
        if self.manual is not None and self.n_ticks != 1:
            raise ValueError("manual 틱은 n_ticks=1만 허용됩니다.")
        return self


class VirtualWormStepResponse(BaseModel):
    ticks: list[VirtualWormTickOut]
    state: VirtualWormStateOut


class VirtualFlyTickOut(BaseModel):
    tick: int
    x_um: float
    y_um: float
    z_um: float = 0.0
    heading_deg: float
    concentration: float = Field(description="이번 틱 위치에서의 냄새(DA1/cVA) 농도(0-1, 가우시안 근사 -- 비행 중엔 바닥 광원으로부터의 3D 거리).")
    event: Literal["cruise", "avoidance"] = Field(description="뇌가 이번 틱에 결정한 행동 -- 순항(cruise) 또는 회피(avoidance, 반전+재정향).")
    pn_current_na: float = Field(description="이번 틱에 실제 PN(DA1 사구체)에 주입한 전류(nA) -- 현재 위치 농도에 비례.")
    mbon01_spikes: int = Field(description="이번 틱 동안 MBON01(y5B'2a)이 실제로 발화한 횟수 -- Aso et al. 2014에서 회피 행동을 유도한다고 보고된 그 구획.")
    control: Literal["auto", "manual"] = Field(
        default="auto",
        description="auto면 event대로 실제 이동, manual이면 이동은 사용자 조종이고 event는 뇌의 결정(반사는 reflex로 제안).",
    )
    reflex: VirtualOrganismReflexOut | None = None
    bio_time_s: float = 0.0


class VirtualFlyStateOut(BaseModel):
    tick: int
    x_um: float
    y_um: float
    z_um: float
    heading_deg: float
    concentration: float
    arena_radius_um: float
    chamber_height_um: float
    source_x_um: float
    source_y_um: float
    gradient_sigma_um: float
    trail: list[list[float]]
    stats: VirtualOrganismStatsOut
    run_id: int
    honesty_note: str


class VirtualFlyStepRequest(BaseModel):
    n_ticks: int = Field(default=1, ge=1, le=10, description="한 번의 호출로 진행할 틱 수 -- 이 회로(~2,452개 뉴런)는 웜보다 틱당 연산 비용이 커서 상한을 더 낮게 잡음.")
    manual: VirtualOrganismPoseIn | None = Field(default=None, description="주면 수동 조종 틱(그 위치에서 감각 1회 계산, n_ticks는 1이어야 함).")

    @model_validator(mode="after")
    def _manual_is_single_tick(self):
        if self.manual is not None and self.n_ticks != 1:
            raise ValueError("manual 틱은 n_ticks=1만 허용됩니다.")
        return self


class VirtualFlyStepResponse(BaseModel):
    ticks: list[VirtualFlyTickOut]
    state: VirtualFlyStateOut


class HypothesisEvidenceOut(BaseModel):
    title: str
    url: str


class HypothesisRecordOut(BaseModel):
    id: str
    title: str
    statement: str = Field(description="'만약 X라면 Y일 것이다' 구조의 실제 가설 문장.")
    method: str = Field(description="어떤 연구소 도구를 어떻게 조합해 검증했는지.")
    result_summary: str = Field(description="실제로 도구를 돌려서 나온 진짜 결과 요약 -- 지지든 기각이든 정직하게.")
    verdict: Literal["supported", "not_supported", "inconclusive"]
    evidence: list[HypothesisEvidenceOut] = Field(description="실제 검색으로 찾은 실제 문헌 인용 -- 없으면 빈 목록(예: 순수 계산 기반 가설).")
    raw_data_note: str | None = Field(default=None, description="검증에 쓴 실제 원자료 숫자.")
    executed_at: str | None = Field(default=None, description="실제로 실행한 날짜 -- 라이브 계산이면 null(매번 다시 계산되므로 날짜 의미 없음).")
    is_live_computed: bool = Field(description="매 요청마다 실시간 재계산되는지, 아니면 이 세션에서 실제로 1회 수행하고 기록만 남긴 것인지.")


# ---------- 손상-재조직 실험실 · 폐루프 재활 (docs/52) ----------

class ReorgLesionOut(BaseModel):
    id: str
    name: str
    category: str
    size: int


class ReorgLabMetaOut(BaseModel):
    lesions: list[ReorgLesionOut]
    strategies: list[str]
    strategy_labels: dict[str, str]
    mechanisms: dict[str, str]
    healthy_efficiency: float
    reference: dict | None = Field(default=None, description="스크립트로 미리 계산한 참고 결과(docs/52) -- 없으면 null.")
    honesty_note: str


class _Mixture(BaseModel):
    w1: float = Field(default=0.25, ge=0, le=1)
    w2: float = Field(default=0.25, ge=0, le=1)
    w3: float = Field(default=0.25, ge=0, le=1)
    w4: float = Field(default=0.25, ge=0, le=1)


class ReorgLabRequest(_Mixture):
    lesion_id: str
    strategies: list[Literal["none", "local", "concentrated", "distributed", "normative", "random", "tau"]] = Field(min_length=1)
    tau: float = Field(default=0.6, ge=0, le=5, description="τ 제약 전략의 여유선(자기 정상 용량 대비 비율). docs/55-56: 허용치를 모를 때 기대값 최적 ≈ 0.6.")
    epochs: int = Field(default=10, ge=1, le=20)
    reps: int = Field(default=2, ge=1, le=4)
    cascade_m: float = Field(default=1.2, ge=0.8, le=1.5)
    seed: int = Field(default=52, ge=0, le=10**6)


class ReorgStrategyResultOut(BaseModel):
    strategy: str
    label: str
    edges_added: int
    efficiency: float = Field(description="재조직 직후 전역 효율(원래 400영역 기준).")
    loadmap_rho: float = Field(description="재조직 후 부하와 정상 부하 지도의 Spearman 상관(생존 영역).")
    overload_frac: float = Field(description="정상 부하 × 1.2를 넘는 생존 영역 비율.")
    cascade_survival: float
    wear_mean: list[float]
    wear_sd: list[float]


class ReorgLabResponse(BaseModel):
    lesion_id: str
    lesion_name: str
    lesion_size: int
    edges_lost: int
    mixture: list[float]
    healthy_efficiency: float
    healthy_wear: list[float]
    results: list[ReorgStrategyResultOut]
    honesty_note: str


class ClosedLoopRequest(_Mixture):
    lesion_id: str
    mode: Literal["connect", "modulate"] = "connect"
    budget: int = Field(default=20, ge=1, le=100, description="시기당 개입 수(연결 유도: 새 연결 수, 활동 조절: 자극 영역 수).")
    base_strategy: Literal["none", "local", "concentrated", "distributed", "normative", "random"] = Field(
        default="distributed", description="활동 조절 모드에서 환자가 이미 겪은 자연 재조직(연결 유도 모드에서는 무시 -- 개입 자체가 재조직).")
    epochs: int = Field(default=12, ge=1, le=20)
    reps: int = Field(default=2, ge=1, le=4)
    seed: int = Field(default=52, ge=0, le=10**6)


class ClosedLoopTraceOut(BaseModel):
    controller: Literal["none", "open", "closed"]
    efficiency: list[float]
    alive: list[float]
    overload: list[float]
    deviation: list[float] = Field(description="정상 부하 지도 이탈: 생존 영역 |log((부하+1)/(정상 부하+1))| 평균.")
    interventions: list[float]


class ReorgRegionStateOut(BaseModel):
    id: int
    network: str
    x: float
    y: float
    lesioned: bool
    ratio_none: float
    ratio_closed: float
    alive_none: bool
    alive_closed: bool


class ClosedLoopResponse(BaseModel):
    lesion_id: str
    lesion_name: str
    mode: str
    budget: int
    base_strategy: str | None
    mixture: list[float]
    edges_lost: int
    traces: list[ClosedLoopTraceOut]
    regions: list[ReorgRegionStateOut]
    honesty_note: str


# ---------- 시기 맞춤 재조직(가중치 모델, docs/58) ----------

class PlasticityScheduleRequest(BaseModel):
    lesion_id: str
    schedule: Literal["seq", "ramp"] = Field(default="seq", description="seq: 앞 50% 강화 -> 뒤 50% 발아, ramp: 발아 확률 0 -> 1 선형 증가.")
    policies: list[Literal["tau0", "dist", "tau06", "conc", "matched", "mismatched"]] = Field(min_length=1)


class PlasticityPolicyResultOut(BaseModel):
    policy: str
    label: str
    mid: dict[str, float] = Field(description="50% 지점: casc_m12, casc_m10, eff_rel(정상 대비 가중 효율).")
    end: dict[str, float]


class PlasticityScheduleResponse(BaseModel):
    lesion_id: str
    lesion_name: str
    schedule: str
    steps: int
    sprout_fraction_by_decile: list[float] = Field(description="재조직 단계를 10등분했을 때 각 구간에서 발아(새 연결)가 차지한 비율.")
    results: list[PlasticityPolicyResultOut]
    honesty_note: str
