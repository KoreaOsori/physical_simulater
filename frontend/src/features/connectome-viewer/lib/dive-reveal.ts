/**
 * Shared 0-1 slider math for the "겉모습→조직→신경계" dive-in reveal, used by
 * both the Drosophila circuit pages (fly-dive-stages.ts) and the human
 * connectome pages (human-dive-stages.ts). Kept as pure functions of a single
 * `progress` value so every page's outer/mid/inner layers agree on exactly
 * where one stage fades out and the next fades in.
 */

export const DIVE_EXTERNAL_END = 0.4;
export const DIVE_ORGAN_PEAK = 0.5;
export const DIVE_ORGAN_START = 0.3;
export const DIVE_ORGAN_END = 0.7;
export const DIVE_NEURAL_START = 0.6;

export function diveExternalOpacity(progress: number): number {
  if (progress >= DIVE_EXTERNAL_END) return 0;
  return 1 - progress / DIVE_EXTERNAL_END;
}

export function diveOrganOpacity(progress: number): number {
  if (progress <= DIVE_ORGAN_START || progress >= DIVE_ORGAN_END) return 0;
  if (progress <= DIVE_ORGAN_PEAK) return (progress - DIVE_ORGAN_START) / (DIVE_ORGAN_PEAK - DIVE_ORGAN_START);
  return 1 - (progress - DIVE_ORGAN_PEAK) / (DIVE_ORGAN_END - DIVE_ORGAN_PEAK);
}

export function diveNeuralOpacity(progress: number): number {
  if (progress <= DIVE_NEURAL_START) return 0;
  return (progress - DIVE_NEURAL_START) / (1 - DIVE_NEURAL_START);
}
