import type { FlyStimulus, HeadingCommand, OdorCommand, VisualCommand } from "@/types/connectome";

/**
 * Static per-circuit metadata for the Drosophila v2 pages. Each hemibrain
 * circuit subset (see backend/app/domain/schemas.py's `CircuitName` and
 * backend/app/data/sources/drosophila/SOURCES.md) now gets its own route
 * (`/fly/olfactory`, `/fly/visual`) instead of sharing one page — a merged
 * page was fine at 2 subsets/5,459 neurons, but every future subset would
 * have kept adding to one shared render + WebSocket + command-bar surface,
 * so splitting now avoids that compounding cost while the merged *dataset*
 * (real cross-circuit synapses included, see SOURCES.md) stays intact behind
 * `GET /api/fly/connectome?circuit=...`.
 */
export type FlyCircuit = "olfactory" | "visual" | "navigation";

export interface StimulusButtonConfig<T extends FlyStimulus> {
  stimulus: T;
  label: string;
}

export interface FlyCircuitConfig {
  circuit: FlyCircuit;
  /** Route path for this circuit's page. */
  path: string;
  /** Short nav label, e.g. for switching between circuits. */
  navLabel: string;
  specimenTitle: string;
  specimenSubtitle: string;
  /** Legend entries shown under the 3D viewport, in render order. */
  legend: { color: string; label: string }[];
  pipelineDescription: string;
  stageLabel: string;
  buttons: StimulusButtonConfig<OdorCommand | VisualCommand | HeadingCommand>[];
}

export const FLY_CIRCUITS: Record<FlyCircuit, FlyCircuitConfig> = {
  olfactory: {
    circuit: "olfactory",
    path: "/fly/olfactory",
    navLabel: "후각 회로 서브셋",
    specimenTitle: "노랑초파리 / 후각 회로 서브셋",
    specimenSubtitle: "hemibrain v1.2 · ORN-PN-KC-MBON-DAN",
    legend: [
      { color: "#75cce9", label: "ORN (감각)" },
      { color: "#baff71", label: "PN / KC / DAN (중간)" },
      { color: "#ff9c73", label: "MBON (출력)" },
    ],
    pipelineDescription: "사구체 자극 → PN→KC 시냅스 → 버섯체(KC) → MBON 출력 → 행동 유의성",
    stageLabel: "02 / 냄새 자극",
    buttons: [
      { stimulus: "DA1", label: "DA1 (페로몬 cVA)" },
      { stimulus: "DL2d", label: "DL2d" },
      { stimulus: "VM5d", label: "VM5d" },
      { stimulus: "DA2", label: "DA2" },
    ],
  },
  visual: {
    circuit: "visual",
    path: "/fly/visual",
    navLabel: "시각 회로 서브셋",
    specimenTitle: "노랑초파리 / 시각 회로 서브셋",
    specimenSubtitle: "hemibrain v1.2 · VPN-DN",
    legend: [
      { color: "#75cce9", label: "VPN (감각)" },
      { color: "#ff9c73", label: "DN (출력)" },
    ],
    pipelineDescription: "시각투사뉴런(VPN) 자극 → VPN→DN 시냅스 → 하행뉴런(DN) 출력 → 도피/추적 행동",
    stageLabel: "02 / 시각 자극",
    buttons: [
      { stimulus: "LC4", label: "LC4 (루밍/도피)" },
      { stimulus: "LC6", label: "LC6 (루밍/도피)" },
      { stimulus: "LPLC2", label: "LPLC2 (양안 루밍)" },
      { stimulus: "LC9", label: "LC9 (소형 이동물체)" },
    ],
  },
  navigation: {
    circuit: "navigation",
    path: "/fly/navigation",
    navLabel: "항법(나침반) 회로 서브셋",
    specimenTitle: "노랑초파리 / 항법(나침반) 회로 서브셋",
    specimenSubtitle: "hemibrain v1.2 · ER-EPG/PEN/PEG/Delta7-PFN-PFL",
    legend: [
      { color: "#75cce9", label: "ER (감각)" },
      { color: "#baff71", label: "EPG/PEN/PEG/Delta7 / PFN (중간)" },
      { color: "#ff9c73", label: "PFL (출력)" },
    ],
    pipelineDescription: "EPG 웨지 헤딩 자극 → EPG→PFL 시냅스 → 조향 출력뉴런(PFL) → 조향(steering) 신호",
    stageLabel: "02 / 헤딩 자극",
    buttons: [
      { stimulus: "EPG_L4", label: "EPG L4" },
      { stimulus: "EPG_R4", label: "EPG R4" },
      { stimulus: "EPG_R6", label: "EPG R6" },
      { stimulus: "EPG_L2", label: "EPG L2" },
    ],
  },
};
