/**
 * Real Drosophila brain-neuropil names for each circuit-class stage, keyed
 * by the exact Korean `categories_ko[0]` string
 * build_drosophila_dataset.py already tags every neuron with (e.g.
 * "촉각엽 투사뉴런(PN)"). Purely a frontend presentation layer — no new
 * backend field needed, since the grouping key already exists on every
 * neuron.
 *
 * Added because a plain point cloud of neurons/synapses is hard to read
 * without background knowledge: these labels place each real cluster in the
 * standard Drosophila brain atlas region it actually belongs to (Ito et al.
 * 2014's neuropil nomenclature), so a viewer can tell "this cluster of dots
 * is the antennal lobe" at a glance. The *positions* are still the existing
 * connectivity-based computed layout (see build_drosophila_dataset.py) —
 * this only draws a soft boundary + label around each real cluster's actual
 * rendered positions, it does not add or assert any new coordinate data.
 */
export interface AnatomyRegion {
  /** Exact match against neuron.categories_ko[0]. */
  categoryKo: string;
  /** Short label shown directly under the region. */
  label: string;
  /** Real neuropil name (English, standard Drosophila brain atlas term). */
  neuropil: string;
  color: string;
}

export const FLY_ANATOMY_REGIONS: AnatomyRegion[] = [
  { categoryKo: "후각수용뉴런(ORN)", label: "촉각엽", neuropil: "Antennal Lobe (AL)", color: "#75cce9" },
  { categoryKo: "촉각엽 투사뉴런(PN)", label: "촉각엽 → 버섯체/측각엽 투사로", neuropil: "AL→MB/LH projection tract", color: "#9fe27a" },
  { categoryKo: "버섯체 켄욘세포(KC)", label: "버섯체 (켈릭스/엽)", neuropil: "Mushroom Body (Calyx/Lobes)", color: "#baff71" },
  { categoryKo: "도파민성 뉴런(DAN)", label: "버섯체 도파민 입력부", neuropil: "PAM/PPL (MB-associated)", color: "#e2c85c" },
  { categoryKo: "버섯체 출력뉴런(MBON)", label: "버섯체 출력부", neuropil: "Mushroom Body Output Zone", color: "#ff9c73" },
  { categoryKo: "시각 투사뉴런(VPN)", label: "시엽 출력부 (로불라/로불라판)", neuropil: "Optic Lobe (Lobula/Lobula Plate) output", color: "#75cce9" },
  { categoryKo: "하행뉴런(DN)", label: "하행로 진입부", neuropil: "Descending Tract / SEZ entry", color: "#ff9c73" },
  { categoryKo: "고리뉴런(ER)", label: "타원체(EB) 랜드마크 입력부", neuropil: "Ellipsoid Body (EB) ring input", color: "#75cce9" },
  { categoryKo: "나침반 고리뉴런(EPG/PEN/PEG/Delta7)", label: "타원체-원판 나침반 링", neuropil: "Ellipsoid Body / Protocerebral Bridge (PB) compass ring", color: "#9fe27a" },
  { categoryKo: "헤딩-목표 통합뉴런(PFN)", label: "부채모양체 헤딩-목표 통합부", neuropil: "Fan-shaped Body (FB), PFN layer", color: "#baff71" },
  { categoryKo: "조향 출력뉴런(PFL)", label: "조향 출력부", neuropil: "PFL steering output", color: "#ff9c73" },
];

export function regionFor(categoryKo: string | undefined): AnatomyRegion | undefined {
  return FLY_ANATOMY_REGIONS.find((r) => r.categoryKo === categoryKo);
}
