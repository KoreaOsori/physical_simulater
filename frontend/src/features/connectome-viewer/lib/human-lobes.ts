/**
 * Frontend mirror of backend/app/data/human_lobes.py (real AAL -> classical
 * 4-lobe mapping, see that file's docstring for the full citation/honesty
 * notes -- Tzourio-Mazoyer et al. 2002's own AAL lobe categorization,
 * limited to the 38 AAL base labels actually matched in this dataset).
 * Kept here (not sent by the backend) because assigning a color per lobe is
 * a presentation concern and the frontend already has every region's real
 * `anatomical_label` loaded -- see docs/30-human-macro-chat-panel.md's
 * "네트워크 vs 해부학" section for why lobe requests get their own
 * multi-color treatment instead of the disorder panel's flat highlight.
 */

export type Lobe = "frontal" | "parietal" | "temporal" | "occipital";

export const LOBE_LABEL_KO: Record<Lobe, string> = {
  frontal: "전두엽",
  parietal: "두정엽",
  temporal: "측두엽",
  occipital: "후두엽",
};

/** Validated (dataviz skill's CVD/lightness/contrast checks, dark surface
 * #050b09 -- HumanMacroCanvas's actual background) against every other
 * color already in this scene (region blue #75cce9, disorder red #ff3b3b,
 * skin/brain/gray-matter warm tones, lime accents). */
export const LOBE_COLOR: Record<Lobe, string> = {
  frontal: "#a8850f",
  parietal: "#0d9ea8",
  temporal: "#9c3fba",
  occipital: "#b85c1a",
};

const _AAL_BASE_TO_LOBE: Record<string, Lobe> = {
  Frontal_Inf_Oper: "frontal",
  Frontal_Inf_Orb: "frontal",
  Frontal_Inf_Tri: "frontal",
  Frontal_Med_Orb: "frontal",
  Frontal_Mid: "frontal",
  Frontal_Mid_Orb: "frontal",
  Frontal_Sup: "frontal",
  Frontal_Sup_Medial: "frontal",
  Frontal_Sup_Orb: "frontal",
  Precentral: "frontal",
  Rectus: "frontal",
  Rolandic_Oper: "frontal",
  Supp_Motor_Area: "frontal",
  Paracentral_Lobule: "frontal",
  Parietal_Inf: "parietal",
  Parietal_Sup: "parietal",
  Postcentral: "parietal",
  Angular: "parietal",
  SupraMarginal: "parietal",
  Precuneus: "parietal",
  Temporal_Inf: "temporal",
  Temporal_Mid: "temporal",
  Temporal_Pole_Mid: "temporal",
  Temporal_Pole_Sup: "temporal",
  Temporal_Sup: "temporal",
  Fusiform: "temporal",
  Heschl: "temporal",
  Calcarine: "occipital",
  Cuneus: "occipital",
  Lingual: "occipital",
  Occipital_Inf: "occipital",
  Occipital_Mid: "occipital",
  Occipital_Sup: "occipital",
  // Insula/Cingulum_*/ParaHippocampal (AAL's own Limbic/Insula categories)
  // intentionally absent -- not part of the classical 4 lobes, same as the
  // backend mapping.
};

function baseName(aalLabel: string): string {
  return aalLabel.endsWith("_L") || aalLabel.endsWith("_R") ? aalLabel.slice(0, -2) : aalLabel;
}

export function lobeForAnatomicalLabel(anatomicalLabel: string | null): Lobe | null {
  if (!anatomicalLabel) return null;
  return _AAL_BASE_TO_LOBE[baseName(anatomicalLabel)] ?? null;
}
