/**
 * Resistive Force Theory (RFT) locomotion — turns the existing lateral
 * body-bending simulation (body-physics.ts's BodySpine) into an actual net
 * translation/rotation of the worm through the scene, instead of bending in
 * place. See docs/07-body-physics.md's "범위 밖으로 남겨둔 것" for why this
 * was previously out of scope, and docs/17-* for this addition.
 *
 * The physics: at C. elegans's scale, viscous drag from the surrounding
 * medium/substrate completely dominates inertia (low Reynolds number) — the
 * classic simplification used by every real model of this kind of locomotion
 * (Gray & Hancock 1955; Niebur & Erdos 1991, "Theory of the swimming of
 * C. elegans"; Fang-Yen et al. 2010, PNAS 107:20323; Shen, Sznitman,
 * Krajacic, Lamitina, Arratia 2012, Biophys J 102:2772, "Undulatory
 * locomotion of C. elegans on wet surfaces"). Instead of F=ma for the body's
 * rigid translation/rotation, the body moves at whatever instantaneous
 * velocity makes the NET drag force and torque zero — inertia is negligible,
 * so any non-zero net load would be resisted infinitely stiffly by the
 * medium. Each body segment's drag is anisotropic: it resists being dragged
 * sideways (normal to its own local tangent) much more than being dragged
 * lengthwise (tangential) — that asymmetry between a symmetric side-to-side
 * bending wave is exactly what converts bending into forward thrust.
 *
 * Real measured value used here: Shen et al. 2012 report C. elegans crawling
 * on wet agar has normal:tangential drag coefficients of approximately
 * 220:22 — a ratio of about 10 (their Cₙ/Cₜ ≈ 9.4-10; consistent with
 * Fang-Yen et al. 2010's independent estimate for the same crawling gait).
 * That RATIO is what determines propulsion direction/efficiency and is used
 * directly below. The absolute magnitude of the drag coefficients is NOT
 * portable as-is: this scene has no real physical unit scale (see
 * body-physics.ts's existing hand-tuned spring/damping constants), and the
 * force-balance solve below is scale-invariant in the drag coefficients'
 * common factor anyway (multiplying both by the same constant doesn't change
 * the solved velocity) — only their RATIO matters, which is why using the
 * literature ratio directly (rather than inventing one) is honest here even
 * without absolute-unit fidelity. One hand-tuned scalar (RFT_SPEED_SCALE)
 * controls overall visual pacing, same honesty caveat as the rest of this
 * project's physics constants.
 */

/** Cₙ/Cₜ for C. elegans crawling on wet agar (Shen et al. 2012, Biophys J
 * 102:2772; corroborated by Fang-Yen et al. 2010, PNAS 107:20323). Swimming
 * in liquid is a much lower ratio (~1.4-2, same sources) — not used here
 * since this project's worm is depicted crawling, not swimming. */
export const RFT_NORMAL_TANGENTIAL_RATIO = 10;

const C_TANGENTIAL = 1;
const C_NORMAL = RFT_NORMAL_TANGENTIAL_RATIO * C_TANGENTIAL;

/** Overall pacing constant: how much rigid-body velocity a given amount of
 * internal bending produces. Cancels out of which DIRECTION the worm moves
 * (only affects how fast) and, unlike the RFT ratio above, has no
 * literature value of its own — but it CAN be checked against one: this
 * scene's neuron/effector positions are placed via a real um->scene-unit
 * factor (`SCENE_UNITS_TO_UM` in scale.ts, matching
 * `_UM_TO_SCENE` in build_connectome_dataset.py), so a given
 * RFT_SPEED_SCALE implies a real um/s crawling speed that can be compared to
 * Fang-Yen et al. 2010's measurement (~200-400 um/s). See
 * `frontend/scripts/verify_rft_speed.mjs` and
 * docs/22-worm-locomotion-real-speed-grounding.md: the previous value (60,
 * picked from browser feel alone) implied a single "forward" press moves the
 * worm about 6.5 body-lengths in 2.2s (~2100 um/s) — ~5-10x too fast once
 * actually measured in real units. This value is derived (not felt) by
 * scaling so a single forward pulse's net displacement lands near the
 * middle of the literature range; re-derive with the same script if the
 * forcing pattern in movement-pose.ts ever changes. Not a linear knob (the
 * body's heading rotates WHILE translating, so higher values also curl the
 * path more, which is why this had to be found by sweeping rather than by
 * one proportion calculation — see the doc). */
const RFT_SPEED_SCALE = 2.5;

export interface RigidPose {
  x: number;
  z: number;
  /** Heading, radians, right-hand rule about +y (three.js up). */
  theta: number;
}

/** Solves the 3x3 low-Reynolds force-balance system (see module docstring
 * for the derivation) for the rigid body's instantaneous velocity, expressed
 * in the BODY's own local frame at this instant — i.e. `vx`/`vz` are "how
 * fast is the reference point moving along/across the body's current local
 * x/z axes", not world axes yet (the caller rotates by the current heading
 * before integrating world position — see `stepLocomotion`). `omega` (yaw
 * rate) needs no such rotation, being a scalar about the shared vertical axis.
 *
 * `localX`/`localZ` are the body-frame positions of each mass (localX is
 * static per body-physics.ts's model; localZ is the live bend from
 * BodySpine.offsetAt). `localVz` is BodySpine.velocityAt (the bending
 * velocity contributed by the SHAPE changing, before any rigid motion is
 * added on top).
 */
export function solveRigidVelocity(
  localX: Float64Array,
  localZ: Float64Array,
  localVz: Float64Array,
): { vx: number; vz: number; omega: number } {
  const n = localX.length;
  let cx = 0;
  let cz = 0;
  for (let i = 0; i < n; i++) {
    cx += localX[i];
    cz += localZ[i];
  }
  cx /= n;
  cz /= n;

  let k11 = 0;
  let k12 = 0;
  let k13 = 0;
  let k22 = 0;
  let k23 = 0;
  let k33 = 0;
  let b1 = 0;
  let b2 = 0;
  let b3 = 0;

  for (let i = 0; i < n; i++) {
    const xPrev = i > 0 ? localX[i - 1] : localX[i];
    const zPrev = i > 0 ? localZ[i - 1] : localZ[i];
    const xNext = i < n - 1 ? localX[i + 1] : localX[i];
    const zNext = i < n - 1 ? localZ[i + 1] : localZ[i];
    let tx = xNext - xPrev;
    let tz = zNext - zPrev;
    const tLen = Math.hypot(tx, tz) || 1;
    tx /= tLen;
    tz /= tLen;
    const nx = -tz;
    const nz = tx;

    // Friction tensor T = C_t*(t⊗t) + C_n*(n⊗n), a symmetric 2x2 matrix
    // mapping local velocity to drag force (before the leading minus sign).
    const txx = C_TANGENTIAL * tx * tx + C_NORMAL * nx * nx;
    const txz = C_TANGENTIAL * tx * tz + C_NORMAL * nx * nz;
    const tzz = C_TANGENTIAL * tz * tz + C_NORMAL * nz * nz;

    const rx = localX[i] - cx;
    const rz = localZ[i] - cz;
    const vzShape = localVz[i];

    k11 += txx;
    k12 += txz;
    k13 += -txx * rz + txz * rx;
    k22 += tzz;
    k23 += -txz * rz + tzz * rx;
    k33 += rx * rx * tzz + rz * rz * txx - 2 * rx * rz * txz;

    b1 += txz * vzShape;
    b2 += tzz * vzShape;
    b3 += (rx * tzz - rz * txz) * vzShape;
  }

  // Solve symmetric 3x3 system [[k11,k12,k13],[k12,k22,k23],[k13,k23,k33]] · u = [-b1,-b2,-b3]
  // via Cramer's rule (cheap and numerically fine at this size).
  const det =
    k11 * (k22 * k33 - k23 * k23) - k12 * (k12 * k33 - k23 * k13) + k13 * (k12 * k23 - k22 * k13);
  if (Math.abs(det) < 1e-9) return { vx: 0, vz: 0, omega: 0 };

  const rhs1 = -b1;
  const rhs2 = -b2;
  const rhs3 = -b3;

  const detVx =
    rhs1 * (k22 * k33 - k23 * k23) - k12 * (rhs2 * k33 - k23 * rhs3) + k13 * (rhs2 * k23 - k22 * rhs3);
  const detVz =
    k11 * (rhs2 * k33 - k23 * rhs3) - rhs1 * (k12 * k33 - k23 * k13) + k13 * (k12 * rhs3 - rhs2 * k13);
  const detOmega =
    k11 * (k22 * rhs3 - rhs2 * k23) - k12 * (k12 * rhs3 - rhs2 * k13) + rhs1 * (k12 * k23 - k22 * k13);

  return { vx: detVx / det, vz: detVz / det, omega: detOmega / det };
}

/** Advances a rigid pose by `dt` given the current body shape (local frame)
 * — solves for the body-frame velocity, rotates the translational part into
 * world space using the CURRENT heading (standard body-frame-to-world
 * integration for a 2D unicycle-like system; the yaw rate itself needs no
 * rotation), then integrates. */
export function stepLocomotion(
  pose: RigidPose,
  localX: Float64Array,
  localZ: Float64Array,
  localVz: Float64Array,
  dt: number,
): RigidPose {
  const { vx, vz, omega } = solveRigidVelocity(localX, localZ, localVz);
  const cosT = Math.cos(pose.theta);
  const sinT = Math.sin(pose.theta);
  const worldVx = (cosT * vx - sinT * vz) * RFT_SPEED_SCALE;
  const worldVz = (sinT * vx + cosT * vz) * RFT_SPEED_SCALE;
  return {
    x: pose.x + worldVx * dt,
    z: pose.z + worldVz * dt,
    theta: pose.theta + omega * RFT_SPEED_SCALE * dt,
  };
}
