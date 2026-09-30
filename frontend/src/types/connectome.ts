// Mirrors backend/app/domain/schemas.py — keep both sides in sync when a field changes.

export type NeuronType = "sensory" | "inter" | "motor" | "unknown";

export type SynapseType = "chemical" | "electrical";

export type Neurotransmitter =
  | "acetylcholine"
  | "gaba"
  | "glutamate"
  | "dopamine"
  | "serotonin"
  | "octopamine"
  | "tyramine"
  | "electrical"
  | "unknown";

export type EffectorType = "muscle" | "gut" | "epidermis" | "other";

export interface Position3D {
  x: number;
  y: number;
  z: number;
}

export interface Neuron {
  id: string;
  name: string;
  type: NeuronType;
  position: Position3D;
  neurotransmitter: Neurotransmitter;
  /** WormBase anatomy ontology (WBbt) definition, English, verbatim. */
  description_en: string | null;
  /** Korean labels for this neuron's WBbt functional/positional categories. */
  categories_ko: string[];
  wormatlas_url: string | null;
  /** Raw source cell-type name (hemibrain's `type` column, e.g. "LC4"/
   * "MBON01"/"KCab") for precise per-type lookups. Null for C. elegans,
   * where `id` already encodes the class. */
  cell_type: string | null;
  /** Which circuit subset this neuron belongs to (e.g. "olfactory"/"visual"/
   * "navigation" — see backend/app/domain/schemas.py's CircuitName). Null
   * for single-subset datasets (e.g. C. elegans). */
  circuit: string | null;
}

export interface Effector {
  id: string;
  name: string;
  kind: EffectorType;
  position: Position3D;
}

export interface Synapse {
  id: string;
  pre: string;
  post: string;
  type: SynapseType;
  neurotransmitter: Neurotransmitter;
  weight: number;
}

export interface Connectome {
  organism: string;
  neuron_count_total: number;
  effector_count_total: number;
  is_placeholder: boolean;
  neurons: Neuron[];
  effectors: Effector[];
  synapses: Synapse[];
}

export type SimulationStage =
  | "command"
  | "synapse"
  | "neurotransmitter"
  | "muscle"
  | "movement";

export interface SimulationEvent {
  t_ms: number;
  stage: SimulationStage;
  source?: string | null;
  target?: string | null;
  neurotransmitter?: Neurotransmitter | null;
  message: string;
}

export type Direction =
  | "forward"
  | "reverse"
  | "left"
  | "right"
  | "stop"
  | "feed"
  | "defecate"
  | "reproduce";

export interface CommandResponse {
  direction: Direction;
  events: SimulationEvent[];
  /** 0 (naive) to hh_model's _MAX_HABITUATION -- see
   * docs/29-worm-habituation-plasticity.md. Always 0 for directions with no
   * HH pathway or when the rule-based fallback engine runs instead. */
  habituation_level: number;
}

/** One real laser-ablation study, resolved against this dataset's actual
 * neuron ids -- see backend/app/data/celegans_classic_ablations.py and
 * docs/26-worm-classic-ablation-behavior.md. */
export interface ClassicAblation {
  name: string;
  category: string;
  description: string;
  neuron_ids: string[];
}

export interface SimulationSocketMessage {
  direction: Direction;
  events: SimulationEvent[];
  /** Only present on the worm's /ws/simulation broadcasts (see
   * ws_manager.py's ConnectionManager.broadcast_events) -- undefined for
   * message shapes where the backend never passed it. */
  habituation_level?: number;
}

/** Drosophila v2 olfactory-circuit subset — named after the real antennal-lobe
 * glomerulus it stimulates (see backend/app/domain/schemas.py's OdorCommand
 * and backend/app/data/sources/drosophila/SOURCES.md). */
export type OdorCommand = "DA1" | "DL2d" | "VM5d" | "DA2";

/** Drosophila v2 phase 2 visual-circuit subset — named after the real
 * hemibrain lobula/lobula-plate visual projection neuron (VPN) type it
 * stimulates (see backend/app/domain/schemas.py's VisualCommand and
 * backend/app/data/sources/drosophila/SOURCES.md). */
export type VisualCommand = "LC4" | "LC6" | "LPLC2" | "LC9";

/** Drosophila v2 phase 4 navigation (central-complex) circuit subset — named
 * after the real hemibrain protocerebral-bridge wedge (EPG compass neuron)
 * it stimulates (see backend/app/domain/schemas.py's HeadingCommand and
 * backend/app/data/sources/drosophila/SOURCES.md). */
export type HeadingCommand = "EPG_L4" | "EPG_R4" | "EPG_R6" | "EPG_L2";

export type FlyStimulus = OdorCommand | VisualCommand | HeadingCommand;

export interface FlyCommandResponse {
  stimulus: FlyStimulus;
  events: SimulationEvent[];
}

export interface FlySimulationSocketMessage {
  direction: FlyStimulus; // backend's ConnectionManager.broadcast_events always uses this JSON key
  events: SimulationEvent[];
}
