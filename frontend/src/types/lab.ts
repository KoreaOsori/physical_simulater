// Mirrors backend/app/lab/schemas.py -- keep both sides in sync. 연구소(Lab)
// 응답 타입은 나머지 확정 데이터 타입(human.ts/connectome.ts)과 의도적으로
// 분리 -- "실제 계산값이지만 해석은 가설"이라는 다른 성격을 타입 레벨에서도
// 구분해 둔다.

import type { Direction, SimulationEvent } from "@/types/connectome";

export interface CentralityEntry {
  node_id: string;
  node_label: string;
  degree_centrality: number;
  betweenness_centrality: number;
  pagerank: number;
  combined_score: number;
  /** 이 프로젝트가 이미 큐레이션한 실제 문헌(웜 고전 절제 연구, 인간 질환
   * 연관)에 등장하는지 -- false는 "실제로 연구된 적 없다"가 아니라
   * "이 프로젝트 안에는 없다"는 뜻. */
  already_in_curated_literature: boolean;
}

export interface TopologyReport {
  species_id: string;
  label_ko: string;
  node_count: number;
  edge_count: number;
  is_directed: boolean;
  density: number;
  average_clustering: number;
  average_shortest_path_length: number | null;
  small_world_sigma: number | null;
  small_world_skipped_reason: string | null;
  betweenness_is_approximate: boolean;
  is_fully_connected: boolean;
  modularity_q: number;
  community_sizes: number[];
  top_candidates: CentralityEntry[];
  curated_literature_note: string;
  honesty_note: string;
}

export interface VirtualExperimentRequest {
  direction: Direction;
  silenced_neuron_ids: string[];
}

export interface VirtualExperimentResponse {
  direction: Direction;
  silenced_neuron_ids: string[];
  experiment_events: SimulationEvent[];
  baseline_events: SimulationEvent[];
  experiment_neurons_fired: string[];
  baseline_neurons_fired: string[];
  silenced_but_would_have_fired: string[];
  honesty_note: string;
}

export interface ExploreChatCitation {
  url: string;
  title: string;
}

export interface ExploreChatResponse {
  answer: string;
  /** 실제 OpenAI web_search 도구가 반환한 URL 인용 -- OpenAI 이용약관상
   * 항상 클릭 가능하게 표시해야 함(링크 렌더링 생략 금지). */
  citations: ExploreChatCitation[];
  used_web_search: boolean;
  honesty_note: string;
}

export interface GeneCandidate {
  symbol: string;
  chromosome: string;
  map_location: string;
  description: string | null;
  distance_fraction: number;
  go_tags: string[];
}

export interface GenePathwayReport {
  seed_symbol: string;
  pathway_label: string;
  seed_chromosome: string;
  seed_map_location: string;
  candidates: GeneCandidate[];
  honesty_note: string;
}

export type HypothesisVerdict = "supported" | "not_supported" | "inconclusive";

export interface HypothesisEvidence {
  title: string;
  url: string;
}

export interface HypothesisRecord {
  id: string;
  title: string;
  statement: string;
  method: string;
  result_summary: string;
  verdict: HypothesisVerdict;
  evidence: HypothesisEvidence[];
  raw_data_note: string | null;
  executed_at: string | null;
  is_live_computed: boolean;
}

export interface VirtualWormNeuronActivity {
  neuron_id: string;
  spike_count: number;
}

/** docs/44/45 -- auto면 event대로 실제 이동, manual이면 이동은 사용자 조종이고
 * event는 뇌의 결정(반사 동작은 reflex로 제안만). */
export type VirtualOrganismControl = "auto" | "manual";

/** docs/45 -- 수동 조종 틱: 브라우저에서 실시간으로 움직인 "지금 위치"를 보내면
 * 서버가 그 자리에서 감각을 1회 계산한다. */
export interface VirtualOrganismPose {
  x_um: number;
  y_um: number;
  z_um?: number;
  heading_deg: number;
  elapsed_bio_ms: number;
  path: [number, number][];
  /** 다시 시작마다 바뀌는 기록 번호 -- 옛 기록의 위치는 서버가 409로 거절한다. */
  run_id?: number;
}

export interface VirtualOrganismReflex {
  back_um: number;
  new_heading_deg: number;
}

export interface VirtualOrganismStats {
  bio_time_s: number;
  distance_mm: number;
  auto_ticks: number;
  manual_ticks: number;
  reorient_decisions: number;
  closest_approach_mm: number;
  reached_at_s: number | null;
}

export type VirtualWormEvent = "run" | "pirouette";

export interface VirtualWormTick {
  tick: number;
  x_um: number;
  y_um: number;
  heading_deg: number;
  concentration: number;
  delta_concentration: number;
  event: VirtualWormEvent;
  forward_spikes: number;
  reverse_spikes: number;
  sensory_activity: VirtualWormNeuronActivity[];
  reached_source: boolean;
  control: VirtualOrganismControl;
  reflex: VirtualOrganismReflex | null;
  bio_time_s: number;
}

export interface VirtualWormState {
  tick: number;
  x_um: number;
  y_um: number;
  heading_deg: number;
  concentration: number;
  arena_radius_um: number;
  source_x_um: number;
  source_y_um: number;
  gradient_sigma_um: number;
  trail: [number, number][];
  reached_source: boolean;
  stats: VirtualOrganismStats;
  run_id: number;
  honesty_note: string;
}

export interface VirtualWormStepResponse {
  ticks: VirtualWormTick[];
  state: VirtualWormState;
}

export type VirtualFlyEvent = "cruise" | "avoidance";

export interface VirtualFlyTick {
  tick: number;
  x_um: number;
  y_um: number;
  z_um: number;
  heading_deg: number;
  concentration: number;
  event: VirtualFlyEvent;
  pn_current_na: number;
  mbon01_spikes: number;
  control: VirtualOrganismControl;
  reflex: VirtualOrganismReflex | null;
  bio_time_s: number;
}

export interface VirtualFlyState {
  tick: number;
  x_um: number;
  y_um: number;
  z_um: number;
  heading_deg: number;
  concentration: number;
  arena_radius_um: number;
  chamber_height_um: number;
  source_x_um: number;
  source_y_um: number;
  gradient_sigma_um: number;
  trail: [number, number][];
  stats: VirtualOrganismStats;
  run_id: number;
  honesty_note: string;
}

export interface VirtualFlyStepResponse {
  ticks: VirtualFlyTick[];
  state: VirtualFlyState;
}

// ---------- 손상-재조직 실험실 · 폐루프 재활 (docs/52) ----------

export type ReorgStrategy = "none" | "local" | "concentrated" | "distributed" | "normative" | "random" | "tau";

export interface ReorgLesion {
  id: string;
  name: string;
  category: string;
  size: number;
}

export interface ReorgMixture {
  w1: number;
  w2: number;
  w3: number;
  w4: number;
}

export interface ReorgReference {
  strategy_map?: { w: number[]; best_effT: string; best_retained: string; table: Record<string, { effT: number; retained: number; eff0: number }> }[];
  null_test?: Record<string, { label: string; real: number; null_mean: number; null_p2_5: number; null_p97_5: number; p_real_gt_null: number; n: number; hist: { edges: number[]; counts: number[] } }>;
  notes?: string[];
}

export interface ReorgLabMeta {
  lesions: ReorgLesion[];
  strategies: ReorgStrategy[];
  strategy_labels: Record<ReorgStrategy, string>;
  mechanisms: Record<string, string>;
  healthy_efficiency: number;
  reference: ReorgReference | null;
  honesty_note: string;
}

export interface ReorgLabRequest extends ReorgMixture {
  lesion_id: string;
  strategies: ReorgStrategy[];
  epochs: number;
  reps: number;
  cascade_m: number;
  seed: number;
  tau: number;
}

export interface ReorgStrategyResult {
  strategy: ReorgStrategy;
  label: string;
  edges_added: number;
  efficiency: number;
  loadmap_rho: number;
  overload_frac: number;
  cascade_survival: number;
  wear_mean: number[];
  wear_sd: number[];
}

export interface ReorgLabResponse {
  lesion_id: string;
  lesion_name: string;
  lesion_size: number;
  edges_lost: number;
  mixture: number[];
  healthy_efficiency: number;
  healthy_wear: number[];
  results: ReorgStrategyResult[];
  honesty_note: string;
}

export type ClosedLoopMode = "connect" | "modulate";
export type ClosedLoopController = "none" | "open" | "closed";

export interface ClosedLoopRequest extends ReorgMixture {
  lesion_id: string;
  mode: ClosedLoopMode;
  budget: number;
  base_strategy: ReorgStrategy;
  epochs: number;
  reps: number;
  seed: number;
}

export interface ClosedLoopTrace {
  controller: ClosedLoopController;
  efficiency: number[];
  alive: number[];
  overload: number[];
  deviation: number[];
  interventions: number[];
}

export interface ReorgRegionState {
  id: number;
  network: string;
  x: number;
  y: number;
  lesioned: boolean;
  ratio_none: number;
  ratio_closed: number;
  alive_none: boolean;
  alive_closed: boolean;
}

export interface ClosedLoopResponse {
  lesion_id: string;
  lesion_name: string;
  mode: ClosedLoopMode;
  budget: number;
  base_strategy: ReorgStrategy | null;
  mixture: number[];
  edges_lost: number;
  traces: ClosedLoopTrace[];
  regions: ReorgRegionState[];
  honesty_note: string;
}

// ---------- 시기 맞춤 재조직(가중치 모델, docs/58) ----------

export type PlasticityPolicy = "tau0" | "dist" | "tau06" | "conc" | "matched" | "mismatched";

export interface PlasticityScheduleRequest {
  lesion_id: string;
  schedule: "seq" | "ramp";
  policies: PlasticityPolicy[];
}

export interface PlasticityPolicyResult {
  policy: PlasticityPolicy | "none";
  label: string;
  mid: { casc_m12: number; casc_m10: number; eff_rel: number };
  end: { casc_m12: number; casc_m10: number; eff_rel: number };
}

export interface PlasticityScheduleResponse {
  lesion_id: string;
  lesion_name: string;
  schedule: "seq" | "ramp";
  steps: number;
  sprout_fraction_by_decile: number[];
  results: PlasticityPolicyResult[];
  honesty_note: string;
}
