// Mirrors backend/app/domain/schemas.py's human-domain models — keep both
// sides in sync when a field changes. See backend/app/data/sources/human/
// SOURCES.md for why these are three separate real datasets rather than one
// unified "human connectome" (no whole-brain neuron-level human connectome
// exists, unlike C. elegans/Drosophila).
import type { SimulationEvent } from "@/types/connectome";

export interface Position3D {
  x: number;
  y: number;
  z: number;
}

export interface BrainRegion {
  id: string;
  name: string;
  network: string;
  /** Real MNI centroid, recentered+uniformly scaled for 3D scene framing —
   * preserves real relative geometry but is NOT directly comparable to a
   * published MNI coordinate. Use `mni_coordinate_mm` for that. */
  position: Position3D;
  /** The literal, unscaled real MNI152 centroid in millimeters (x=R, y=A,
   * z=S, the conventional MNI coordinate order) — what to check against an
   * atlas or paper (docs/32). */
  mni_coordinate_mm: Position3D;
  /** Real AAL atlas region name this parcel's centroid falls in/nearest to
   * (e.g. "Calcarine_L") — a coordinate lookup, not a claim the Schaefer
   * parcel and AAL region are the same shape. Null if unresolved. */
  anatomical_label: string | null;
  /** Short general-neuroanatomy functional note for `anatomical_label`. */
  anatomical_note: string | null;
}

export interface RegionEdge {
  a: string;
  b: string;
  weight: number;
}

export interface AnatomyMeshLayer {
  /** Flat [x0,y0,z0,x1,y1,z1,...] — already in this scene's coordinate frame. */
  positions: number[];
  /** Flat triangle index array. */
  indices: number[];
  vertex_count: number;
  triangle_count: number;
}

export interface HeadAnatomy {
  skin: AnatomyMeshLayer;
  brain: AnatomyMeshLayer;
  gray_matter: AnatomyMeshLayer;
  source: string;
  /** Real MNI centroid of the Limbic/TempPole parcels (temporal pole) — the
   * closest macro-atlas neighborhood to where H01's micro sample was taken.
   * NOT a registered coordinate for the H01 sample itself. */
  h01_region_hint: Position3D;
}

export type DisorderCategory = "focal" | "complex";

export interface DisorderAssociation {
  name: string;
  /** "focal" = classic single/few-region lesion syndrome. "complex" = real
   * condition with well-documented multi-network involvement and a
   * genuinely multifactorial cause — kept visually separate from focal
   * syndromes so a long region list is never mistaken for "the cause". */
  category: DisorderCategory;
  /** For "focal" entries: the real network most of its region_ids belong to
   * (majority vote). Always null for "complex" entries. */
  primary_network: string | null;
  /** Same majority-vote logic one level down: the real classical 4-lobe
   * (frontal/parietal/temporal/occipital) most of its region_ids belong to.
   * Null for "complex" entries AND for any "focal" entry whose regions all
   * fall outside the 4 classical lobes (e.g. insula-only entries) — never
   * forced into a lobe it doesn't really belong to (docs/33). */
  primary_lobe: string | null;
  description: string;
  anatomical_labels: string[];
  region_ids: string[];
}

export interface MacroConnectome {
  networks: string[];
  region_count_total: number;
  regions: BrainRegion[];
  edges: RegionEdge[];
  anatomy: HeadAnatomy;
  known_disorders: DisorderAssociation[];
}

export interface MicroNeuronPoint {
  neuron_id: string;
  position: Position3D;
  radius: number;
}

export type SynapseRole = "AXON" | "DENDRITE";

export interface MicroSynapseContact {
  neuron_id: string;
  /** AXON = this neuron is the sending/presynaptic side; DENDRITE = receiving/postsynaptic. */
  role: SynapseRole;
  partner_neuron_id: string;
  /** Real data shows this is essentially always false — see SOURCES.md. */
  partner_is_proofread: boolean;
  position: Position3D;
  confidence: number | null;
}

export interface MicroConnectomeSample {
  source_region: string;
  neuron_count_total: number;
  point_count_total: number;
  points: MicroNeuronPoint[];
  synapse_count_total: number;
  synapses: MicroSynapseContact[];
}

export type GeneConfidence = "annotated" | "hypothetical";

export interface Gene {
  id: string;
  symbol: string;
  chromosome: string;
  map_location: string;
  description: string | null;
  type_of_gene: string;
  go_tags: string[];
  confidence: GeneConfidence;
  /** 0-1 position along the chromosome, from a real cytoband match — null
   * if no matching band was found (see backend build_human_dataset.py). */
  position_fraction: number | null;
}

export interface CytoBand {
  chromosome: string;
  start: number;
  end: number;
  band: string;
  stain: string;
}

export interface HumanGenome {
  gene_count_total: number;
  genes: Gene[];
  cytobands: CytoBand[];
}

export type GenePathwayCommand = "BDNF_ACTIVATION" | "ARC_PLASTICITY_ACTIVATION";

export interface GenomeCommandResponse {
  stimulus: GenePathwayCommand;
  events: SimulationEvent[];
}

export interface GenomeSocketMessage {
  direction: GenePathwayCommand;
  events: SimulationEvent[];
}

/** DB-grounded chat panel on the human macro page — see
 * docs/30-human-macro-chat-panel.md. `active_network`/`visible_region_ids`/
 * `selected_disorder_name` describe what's actually on screen; the backend's
 * retrieval starts from this, not a free search over the whole dataset. */
export interface HumanChatRequest {
  message: string;
  active_network: string | null;
  visible_region_ids: string[];
  selected_disorder_name: string | null;
}

export interface HumanChatResponse {
  answer: string;
  /** Which real DB entries (region/disorder/gene ids) the answer actually
   * drew on — shown so the answer stays checkable against the data. */
  used_source_ids: string[];
  /** Regions to highlight in ONE color (disorder/region citations) — see
   * requested_lobes for the separate multi-color lobe-view mechanism. */
  highlighted_region_ids: string[];
  /** Real lobe keys ("frontal"/"parietal"/"temporal"/"occipital") detected
   * in the message — resolve via human-lobes.ts's lobeForAnatomicalLabel,
   * each lobe gets its own color (LOBE_COLOR), not the flat disorder red. */
  requested_lobes: string[];
}
