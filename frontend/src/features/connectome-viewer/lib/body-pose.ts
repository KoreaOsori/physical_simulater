import type { Connectome, Position3D } from "@/types/connectome";

/**
 * Real neuron/effector positions (see backend/app/data/sources/SOURCES.md)
 * come from an EM-reconstructed specimen mounted straight for imaging, not a
 * live crawling worm. This applies a purely cosmetic sinusoidal bend along
 * the anterior-posterior (x) axis so the body reads as a recognizable
 * S-shaped worm — the bend itself is not measured data.
 */
const BEND_AMPLITUDE_Z = 0.85; // scene units, left-right sway
const BEND_CYCLES = 1.3; // number of S-wave periods along the body

/** Maximum cross-sectional radius of the body envelope (WormBodyMesh) — also
 * used by BodyLandmarks to place mouth/vulva/anus markers on the surface. */
export const MAX_BODY_RADIUS = 0.85;

export interface ApExtent {
  min: number;
  max: number;
}

export function computeApExtent(connectome: Connectome): ApExtent {
  let min = Infinity;
  let max = -Infinity;
  for (const node of [...connectome.neurons, ...connectome.effectors]) {
    if (node.position.x < min) min = node.position.x;
    if (node.position.x > max) max = node.position.x;
  }
  if (!Number.isFinite(min)) return { min: -1, max: 1 };
  return { min, max };
}

/** 0 (tip) -> 1 (tip), thin at the head/tail and thickest a little ahead of
 * mid-body — a rough approximation of the real worm's taper profile. */
export function bodyRadiusProfile(t: number): number {
  const clamped = Math.min(1, Math.max(0, t));
  return Math.pow(Math.sin(Math.PI * clamped), 0.55);
}

export function apFraction(x: number, extent: ApExtent): number {
  const span = extent.max - extent.min || 1;
  return (x - extent.min) / span;
}

/** World-space midpoint of the real AP extent — used to re-center every
 * rendered position on the body's own middle (rft-locomotion.ts's rigid
 * transform rotates/translates a <group> around ITS local origin, so that
 * origin has to coincide with the body's own center, not some unrelated
 * point, or turning would look like swinging around a distant pivot). */
export function bodyCenterX(extent: ApExtent): number {
  return (extent.min + extent.max) / 2;
}

/** Lateral (z) offset for the S-curve bend at a given AP fraction. `phaseShift`
 * (radians) lets a traveling locomotion wave animate this same curve — see
 * movement-pose.ts — without changing the resting pose's shape. */
export function bendOffsetZ(t: number, phaseShift = 0): number {
  return Math.sin(t * Math.PI * BEND_CYCLES + phaseShift) * BEND_AMPLITUDE_Z * bodyRadiusProfile(t);
}

/** Real neuron/effector position, bent, and re-centered on the body's own
 * midpoint (see bodyCenterX) so it composes correctly with a rigid
 * translate+rotate <group> applied on top for locomotion (rft-locomotion.ts) —
 * `extent` (absolute world x) is still used for `t`/centering math, but the
 * returned x is relative to the body center, not absolute world x. */
export function bendPosition(pos: Position3D, extent: ApExtent): Position3D {
  const t = apFraction(pos.x, extent);
  return { x: pos.x - bodyCenterX(extent), y: pos.y, z: pos.z + bendOffsetZ(t) };
}

/** +1 for a left-side effector id (…L / …L#), -1 for right-side, 0 if the
 * name doesn't encode a side (e.g. "intestine", "hyp"). Used to bias the
 * body-mesh deformation toward whichever side's muscle just fired. */
export function parseLateralSign(effectorOrNeuronId: string): number {
  if (/L\d*$/.test(effectorOrNeuronId)) return 1;
  if (/R\d*$/.test(effectorOrNeuronId)) return -1;
  return 0;
}

export interface BodyLandmarks {
  /** Terminal opening at the very anterior tip — feeding. */
  mouthX: number;
  /** Real HSNL/HSNR (the neurons that innervate the vulval muscles) position —
   * the actual anatomical vulva location, not guessed. */
  vulvaX: number;
  /** Real DVB (the neuron that drives the defecation motor program) position —
   * anatomically right at the rectum/anus. */
  anusX: number;
}

/** Derives the three body-opening positions from real neuron landmarks
 * already in the dataset, rather than hardcoding fractions. */
export function computeBodyLandmarks(connectome: Connectome, extent: ApExtent): BodyLandmarks {
  const byId = new Map(connectome.neurons.map((n) => [n.id, n.position.x]));
  return {
    mouthX: extent.min,
    vulvaX: byId.get("HSNL") ?? byId.get("HSNR") ?? (extent.min + extent.max) / 2,
    anusX: byId.get("DVB") ?? extent.min + (extent.max - extent.min) * 0.88,
  };
}

/** One bent position per neuron/effector id, computed once per connectome so
 * every consumer (nodes, synapse lines, the body mesh, NT bursts) agrees. */
export function buildBentPositionLookup(connectome: Connectome): {
  positions: Map<string, Position3D>;
  extent: ApExtent;
} {
  const extent = computeApExtent(connectome);
  const positions = new Map<string, Position3D>();
  for (const neuron of connectome.neurons) positions.set(neuron.id, bendPosition(neuron.position, extent));
  for (const effector of connectome.effectors) positions.set(effector.id, bendPosition(effector.position, extent));
  return { positions, extent };
}
