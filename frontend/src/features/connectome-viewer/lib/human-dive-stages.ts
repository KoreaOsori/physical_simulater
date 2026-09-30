/**
 * Configures the "dive-in" reveal (겉모습→뇌 조직→신경계) for the human
 * macro/micro connectome pages — same UX as v1's LayerControlPanel and v2's
 * fly dive-in reveal (see dive-reveal.ts for the shared opacity math), but
 * here all three stages are real MNI152 template isosurfaces
 * (HumanHeadLayers.tsx), not schematic/illustrative geometry — see
 * backend/app/data/sources/human/SOURCES.md's "두개골/뇌 표면 메시" section.
 */
import { DIVE_NEURAL_START, DIVE_ORGAN_START } from "@/features/connectome-viewer/lib/dive-reveal";

export function humanDiveStageLabel(progress: number): string {
  if (progress < DIVE_ORGAN_START) return "겉모습 (두피)";
  if (progress < DIVE_NEURAL_START) return "뇌 조직";
  return "신경계 (회백질)";
}
