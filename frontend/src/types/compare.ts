// Mirrors backend/app/domain/schemas.py's SpeciesDatasetScale/CompareSummary
// (GET /api/compare/summary) — keep both sides in sync when a field changes.

export interface SpeciesDatasetScale {
  species_id: "c_elegans" | "drosophila" | "human";
  common_name_ko: string;
  scientific_name: string;
  /** True only for C. elegans -- its 302-neuron dataset IS the real total,
   * not a subset. Never true for drosophila/human -- see dataset_note. */
  is_dataset_complete: boolean;
  dataset_neuron_count: number | null;
  dataset_synapse_count: number | null;
  /** Only set for human macro (400 Schaefer parcels) -- a region-level
   * count, not a neuron count; deliberately a separate field so the two are
   * never added together. */
  dataset_region_count: number | null;
  dataset_note: string;
  real_world_neuron_count: number | null;
  real_world_neuron_count_note: string;
}

export interface CompareSummary {
  species: SpeciesDatasetScale[];
}
