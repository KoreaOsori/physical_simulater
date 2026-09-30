import type { FlyCircuit } from "@/features/lab-shell/lib/fly-circuits";
import {
  DIVE_EXTERNAL_END,
  DIVE_NEURAL_START,
  DIVE_ORGAN_END,
  DIVE_ORGAN_PEAK,
  DIVE_ORGAN_START,
  diveExternalOpacity,
  diveNeuralOpacity,
  diveOrganOpacity,
} from "@/features/connectome-viewer/lib/dive-reveal";

export {
  DIVE_EXTERNAL_END,
  DIVE_NEURAL_START,
  DIVE_ORGAN_END,
  DIVE_ORGAN_PEAK,
  DIVE_ORGAN_START,
  diveExternalOpacity,
  diveNeuralOpacity,
  diveOrganOpacity,
};

/**
 * Configures the "dive-in" reveal (겉모습→감각기관→신경계) for the circuit
 * pages where a real external sense organ exists — olfactory (antennae) and
 * visual (compound eyes). Deliberately NOT offered for the navigation
 * (central-complex) page: that circuit has no external sense organ of its
 * own (it integrates signals from other senses), so there's no honest
 * external-anatomy stage to build for it — it keeps showing the neural
 * network directly, as before.
 *
 * The external organ meshes (FlyExternalAnatomy.tsx) are stylized/illustrative
 * — this project has no real 3D scan data of Drosophila external anatomy —
 * not literal measured geometry the way neuron positions are hemibrain data.
 */
export type FlyDiveOrganKind = "antenna" | "eye";

export interface FlyDiveConfig {
  organKind: FlyDiveOrganKind;
  /** Short Korean name for the external organ, e.g. "더듬이". */
  organLabel: string;
  /** The real neuropil this organ's signal enters — matches the label
   * already used in fly-anatomy-regions.ts for continuity across the dive. */
  organNeuropilLabel: string;
  /** What the flowing-particle transition represents (air for smell, light
   * for vision) — cosmetic wording only. */
  flowLabel: string;
}

export const FLY_DIVE_CONFIG: Partial<Record<FlyCircuit, FlyDiveConfig>> = {
  olfactory: {
    organKind: "antenna",
    organLabel: "더듬이",
    organNeuropilLabel: "촉각엽 (Antennal Lobe)",
    flowLabel: "냄새 분자",
  },
  visual: {
    organKind: "eye",
    organLabel: "겹눈",
    organNeuropilLabel: "시엽 (Optic Lobe)",
    flowLabel: "빛",
  },
};

export function diveStageLabel(progress: number): string {
  if (progress < DIVE_ORGAN_START) return "겉모습";
  if (progress < DIVE_NEURAL_START) return "감각기관 내부";
  return "신경계";
}
