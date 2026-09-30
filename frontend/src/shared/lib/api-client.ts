import { API_URL } from "@/shared/lib/env";
import type { FlyCircuit } from "@/features/lab-shell/lib/fly-circuits";
import type { ClassicAblation, CommandResponse, Connectome, Direction, FlyCommandResponse, FlyStimulus } from "@/types/connectome";
import type { CompareSummary } from "@/types/compare";
import type {
  GenePathwayCommand,
  GenomeCommandResponse,
  HumanChatRequest,
  HumanChatResponse,
  HumanGenome,
  MacroConnectome,
  MicroConnectomeSample,
} from "@/types/human";
import type {
  ExploreChatResponse,
  GenePathwayReport,
  HypothesisRecord,
  TopologyReport,
  VirtualExperimentRequest,
  VirtualExperimentResponse,
  VirtualFlyState,
  VirtualFlyStepResponse,
  VirtualOrganismPose,
  VirtualWormState,
  VirtualWormStepResponse,
} from "@/types/lab";

export async function fetchConnectome(): Promise<Connectome> {
  const res = await fetch(`${API_URL}/api/connectome`);
  if (!res.ok) throw new Error(`Failed to load connectome: ${res.status}`);
  return res.json();
}

/** `silencedNeuronIds` approximates a classic laser-ablation experiment for
 * this one command (see AblationPanel.tsx / backend's hh_model.py) --
 * omitted (not sent as `[]`) when there's no active ablation, so the rule-
 * based fallback engine's request body stays exactly as before. */
export async function postCommand(direction: Direction, silencedNeuronIds?: string[]): Promise<CommandResponse> {
  const res = await fetch(`${API_URL}/api/simulation/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      silencedNeuronIds && silencedNeuronIds.length > 0
        ? { direction, silenced_neuron_ids: silencedNeuronIds }
        : { direction },
    ),
  });
  if (!res.ok) throw new Error(`Failed to send command: ${res.status}`);
  return res.json();
}

/** Real laser-ablation studies curated against this dataset's actual neuron
 * ids -- see backend/app/data/celegans_classic_ablations.py. */
export async function fetchClassicAblations(): Promise<ClassicAblation[]> {
  const res = await fetch(`${API_URL}/api/classic-ablations`);
  if (!res.ok) throw new Error(`Failed to load classic ablations: ${res.status}`);
  return res.json();
}

/** `circuit` filters the merged Drosophila dataset down to one circuit
 * subset's own neurons/synapses server-side (see backend/app/api/routes/fly.py)
 * — each per-circuit page passes its own circuit so its payload stays flat
 * as more circuit subsets get added, rather than fetching the whole merged
 * dataset just to discard most of it client-side. */
export async function fetchFlyConnectome(circuit: FlyCircuit): Promise<Connectome> {
  const res = await fetch(`${API_URL}/api/fly/connectome?circuit=${circuit}`);
  if (!res.ok) throw new Error(`Failed to load fly connectome: ${res.status}`);
  return res.json();
}

export async function postFlyCommand(stimulus: FlyStimulus): Promise<FlyCommandResponse> {
  const res = await fetch(`${API_URL}/api/fly/simulation/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stimulus }),
  });
  if (!res.ok) throw new Error(`Failed to send fly command: ${res.status}`);
  return res.json();
}

/** Real HCP-derived structural connectivity between Schaefer-atlas visual-
 * network parcels — see backend/app/data/sources/human/SOURCES.md. */
export async function fetchHumanMacroConnectome(): Promise<MacroConnectome> {
  const res = await fetch(`${API_URL}/api/human/connectome/macro`);
  if (!res.ok) throw new Error(`Failed to load human macro connectome: ${res.status}`);
  return res.json();
}

/** Real H01 (Harvard/Google) human temporal-cortex EM reconstruction sample
 * — 104 real proofread neurons, decimated (see SOURCES.md). */
export async function fetchHumanMicroSample(): Promise<MicroConnectomeSample> {
  const res = await fetch(`${API_URL}/api/human/connectome/micro`);
  if (!res.ok) throw new Error(`Failed to load human micro sample: ${res.status}`);
  return res.json();
}

/** Real nervous-system-related human genes (GO-filtered) + real hg38
 * chromosome ideogram bands. */
export async function fetchHumanGenome(): Promise<HumanGenome> {
  const res = await fetch(`${API_URL}/api/human/genome`);
  if (!res.ok) throw new Error(`Failed to load human genome: ${res.status}`);
  return res.json();
}

/** The one endpoint spanning all three species' otherwise separate route
 * namespaces -- see backend/app/api/routes/compare.py. */
export async function fetchCompareSummary(): Promise<CompareSummary> {
  const res = await fetch(`${API_URL}/api/compare/summary`);
  if (!res.ok) throw new Error(`Failed to load compare summary: ${res.status}`);
  return res.json();
}

export async function postGenomeCommand(stimulus: GenePathwayCommand): Promise<GenomeCommandResponse> {
  const res = await fetch(`${API_URL}/api/human/genome/pathway/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stimulus }),
  });
  if (!res.ok) throw new Error(`Failed to send genome pathway command: ${res.status}`);
  return res.json();
}

/** DB-grounded only -- see docs/30-human-macro-chat-panel.md. */
export async function postHumanChatMessage(request: HumanChatRequest): Promise<HumanChatResponse> {
  const res = await fetch(`${API_URL}/api/human/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`Failed to send human chat message: ${res.status}`);
  return res.json();
}

export async function fetchLabTopologySpecies(): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/lab/topology/species`);
  if (!res.ok) throw new Error(`Failed to load lab topology species list: ${res.status}`);
  return res.json();
}

/** The first request for a given species can take real tens of seconds
 * server-side (fly circuits especially, see species_topology.py's
 * @lru_cache comment) -- no special client-side timeout handling added, the
 * default fetch behavior (wait) is the right one here. */
export async function fetchLabTopologyReport(speciesId: string): Promise<TopologyReport> {
  const res = await fetch(`${API_URL}/api/lab/topology/${speciesId}`);
  if (!res.ok) throw new Error(`Failed to load lab topology report: ${res.status}`);
  return res.json();
}

/** Two real Brian2 runs server-side (baseline + experiment), ~2-3s each --
 * see docs/35. Deliberately a separate endpoint from postCommand, does NOT
 * touch the real worm page's WS state or habituation level. */
export async function postLabVirtualExperiment(request: VirtualExperimentRequest): Promise<VirtualExperimentResponse> {
  const res = await fetch(`${API_URL}/api/lab/virtual-experiment/worm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`Failed to run lab virtual experiment: ${res.status}`);
  return res.json();
}

/** DB 밖으로 나가는 게 핵심인 챗봇 모드(docs/36) -- postHumanChatMessage와
 * 정반대로 실제 웹 검색을 허용한다. */
export async function postLabExploreChat(message: string): Promise<ExploreChatResponse> {
  const res = await fetch(`${API_URL}/api/lab/explore-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Failed to send lab explore chat message: ${res.status}`);
  return res.json();
}

export async function fetchLabGenePathwayCandidates(): Promise<GenePathwayReport[]> {
  const res = await fetch(`${API_URL}/api/lab/gene-pathway-candidates`);
  if (!res.ok) throw new Error(`Failed to load lab gene pathway candidates: ${res.status}`);
  return res.json();
}

export async function fetchLabHypotheses(): Promise<HypothesisRecord[]> {
  const res = await fetch(`${API_URL}/api/lab/hypotheses`);
  if (!res.ok) throw new Error(`Failed to load lab hypothesis notebook: ${res.status}`);
  return res.json();
}

/** 서버가 응답한 오류(상태 코드 보존) -- 네트워크 단절("Failed to fetch", TypeError)과
 * 구분해야 재시도 여부를 정할 수 있다(docs/45: 409 = 다시 시작 이전 기록의 위치). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** docs/41 -- 실제 302개 뉴런 커넥톰이 매 틱 환경(농도 기울기)을 감지하고
 * 실제로 이동하는 폐루프 시뮬레이션. reset은 완전히 새로운 독립 Brian2
 * 네트워크를 만든다(기존 명령 경로의 공유 싱글턴과 무관). */
export async function postVirtualWormReset(): Promise<VirtualWormState> {
  const res = await fetch(`${API_URL}/api/lab/virtual-worm/reset`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to reset virtual worm: ${res.status}`);
  return res.json();
}

export async function fetchVirtualWormState(): Promise<VirtualWormState> {
  const res = await fetch(`${API_URL}/api/lab/virtual-worm/state`);
  if (!res.ok) throw new Error(`Failed to load virtual worm state: ${res.status}`);
  return res.json();
}

/** 틱당 실제 Brian2 계산 비용이 있어 실시간이 아니라 배치 스텝 호출로
 * 시뮬레이션 시간을 가속한다(n_ticks, 서버 측 1-20 제한). */
export async function postVirtualWormStep(
  nTicks: number,
  manual: VirtualOrganismPose | null = null,
): Promise<VirtualWormStepResponse> {
  const res = await fetch(`${API_URL}/api/lab/virtual-worm/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ n_ticks: nTicks, manual }),
  });
  if (!res.ok) throw new ApiError(`Failed to step virtual worm: ${res.status}`, res.status);
  return res.json();
}

/** docs/42 -- 실제 초파리 hemibrain 후각 회로(~2,452개 뉴런)가 매 틱
 * DA1(cVA) 냄새 농도를 감지하고 MBON01(y5B'2a) 발화 여부로 회피를
 * 판정하는 폐루프. 틱당 연산 비용이 웜보다 커서 n_ticks 상한이 더
 * 낮다(서버 측 1-10 제한). */
export async function postVirtualFlyReset(): Promise<VirtualFlyState> {
  const res = await fetch(`${API_URL}/api/lab/virtual-fly/reset`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to reset virtual fly: ${res.status}`);
  return res.json();
}

export async function fetchVirtualFlyState(): Promise<VirtualFlyState> {
  const res = await fetch(`${API_URL}/api/lab/virtual-fly/state`);
  if (!res.ok) throw new Error(`Failed to load virtual fly state: ${res.status}`);
  return res.json();
}

/** manual을 주면 수동 조종 틱(docs/45) -- 그 위치에서 실제 회로가 감각을 1회 계산한다. */
export async function postVirtualFlyStep(
  nTicks: number,
  manual: VirtualOrganismPose | null = null,
): Promise<VirtualFlyStepResponse> {
  const res = await fetch(`${API_URL}/api/lab/virtual-fly/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ n_ticks: nTicks, manual }),
  });
  if (!res.ok) throw new ApiError(`Failed to step virtual fly: ${res.status}`, res.status);
  return res.json();
}

/** docs/45 -- 냄새원/유인물질 광원 옮기기(기록 구간이 새로 시작된다). */
export async function postVirtualOrganismSource(species: "worm" | "fly", x_um: number, y_um: number): Promise<VirtualWormState | VirtualFlyState> {
  const res = await fetch(`${API_URL}/api/lab/virtual-${species}/source`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ x_um, y_um }),
  });
  if (!res.ok) throw new Error(`Failed to move virtual ${species} source: ${res.status}`);
  return res.json();
}

/** docs/45 -- 신경 계산 없이 위치만 확정(수동 -> 자동 전환 시). */
export async function postVirtualOrganismPose(species: "worm" | "fly", pose: VirtualOrganismPose): Promise<VirtualWormState | VirtualFlyState> {
  const res = await fetch(`${API_URL}/api/lab/virtual-${species}/pose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pose),
  });
  if (!res.ok) throw new ApiError(`Failed to set virtual ${species} pose: ${res.status}`, res.status);
  return res.json();
}
