/**
 * Maps a single 0-100 "해부 레이어" slider onto per-layer opacities, so
 * dragging it peels the body open from the outside in — cuticle/skin first,
 * then muscle/gut/epidermis, then the nervous system — mirroring the
 * classic OpenWorm "peel away" visualization.
 */
export interface LayerOpacities {
  skin: number;
  effector: number;
  neuron: number;
}

function lerpClamped(a: number, b: number, t: number): number {
  const c = Math.min(1, Math.max(0, t));
  return a + (b - a) * c;
}

export function computeLayerOpacities(reveal: number): LayerOpacities {
  return {
    // Never fully disappears — a faint outline stays so the real outer body
    // shape can still be compared against whatever internal layer is shown.
    skin: lerpClamped(1, 0.12, (reveal - 15) / 25),
    effector: lerpClamped(0, 1, (reveal - 20) / 30),
    neuron: lerpClamped(0, 1, (reveal - 45) / 35),
  };
}

export function activeLayerLabel(reveal: number): string {
  if (reveal < 25) return "겉모습 (큐티클)";
  if (reveal < 55) return "근육 / 조직";
  return "신경계";
}
