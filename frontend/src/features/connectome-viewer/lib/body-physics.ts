/**
 * A real (if deliberately simplified) numerical dynamics simulation of the
 * worm body's lateral bend — replaces the earlier purely scripted animation
 * (a phase-shifted sine wave + hand-placed Gaussian bumps written directly
 * into geometry) with an actual damped mass-spring-damper chain that muscle
 * activation and locomotion forcing *push on*, and whose resulting shape is
 * an emergent consequence of those forces propagating through the chain —
 * not a pre-authored curve.
 *
 * Model: N point masses laid out along the anterior-posterior axis, each
 * free to move only in the lateral (z) direction. Each mass is coupled to
 * its neighbors (a discrete Laplacian — the standard finite-difference model
 * of a tensioned elastic rod) and pulled back toward the body's resting
 * S-curve pose by a spring, with velocity damping standing in for drag from
 * the surrounding medium. External forces (muscle contraction, locomotion
 * pattern) are injected as local, Gaussian-distributed forces and let the
 * chain's own dynamics decide how far the disturbance propagates and how it
 * decays — this is what makes the response look organic instead of scripted.
 *
 * Explicitly NOT modeled (see docs/07-*.md): substrate friction/thrust (so
 * there is no net translation across the ground — only bending), 3D
 * (dorsal-ventral) bending, and any measured value for stiffness/damping —
 * every constant below is hand-tuned for a stable, plausible-looking
 * response, not derived from cuticle/muscle biomechanics literature.
 */

export interface BodyPhysicsConfig {
  segments: number; // number of masses = segments + 1
  neighborStiffness: number;
  restoreStiffness: number;
  damping: number;
  massAt: (t: number) => number; // t in [0,1]; must be > 0
}

export class BodySpine {
  readonly n: number;
  private readonly z: Float64Array;
  private readonly v: Float64Array;
  private readonly restZ: Float64Array;
  private readonly mass: Float64Array;
  private readonly force: Float64Array;
  private readonly cfg: BodyPhysicsConfig;

  constructor(restZ: Float64Array, cfg: BodyPhysicsConfig) {
    this.n = restZ.length;
    this.restZ = restZ;
    this.z = Float64Array.from(restZ);
    this.v = new Float64Array(this.n);
    this.force = new Float64Array(this.n);
    this.mass = new Float64Array(this.n);
    for (let i = 0; i < this.n; i++) {
      this.mass[i] = Math.max(0.05, cfg.massAt(i / (this.n - 1)));
    }
    this.cfg = cfg;
  }

  /** Re-centers the chain on a new resting pose without discarding its
   * current velocity/displacement (used when the body's S-curve extent
   * changes, which in practice it doesn't after load — kept for safety). */
  setRestPose(restZ: Float64Array): void {
    this.restZ.set(restZ);
  }

  /** Injects a Gaussian-distributed force around AP fraction `t` (0-1). */
  applyForce(t: number, magnitude: number, width: number): void {
    const center = t * (this.n - 1);
    const radius = Math.max(1, width * (this.n - 1) * 3);
    const lo = Math.max(0, Math.floor(center - radius));
    const hi = Math.min(this.n - 1, Math.ceil(center + radius));
    for (let i = lo; i <= hi; i++) {
      const d = (i - center) / ((this.n - 1) * width);
      this.force[i] += magnitude * Math.exp(-d * d);
    }
  }

  /** Advances the simulation by `dt` seconds (semi-implicit Euler). Forces
   * accumulated via `applyForce` persist across calls — call `clearForces()`
   * once per rendered frame after however many substeps you run, not after
   * each one, so a force applied this frame acts throughout all its substeps. */
  step(dt: number): void {
    const { neighborStiffness: k, restoreStiffness: kr, damping: c } = this.cfg;
    for (let i = 0; i < this.n; i++) {
      const left = i > 0 ? this.z[i - 1] : this.z[i];
      const right = i < this.n - 1 ? this.z[i + 1] : this.z[i];
      const laplacian = left + right - 2 * this.z[i];
      const restoring = -(this.z[i] - this.restZ[i]) * kr;
      const springForce = laplacian * k + restoring;
      const total = springForce + this.force[i] - this.v[i] * c;
      const accel = total / this.mass[i];
      this.v[i] += accel * dt;
    }
    for (let i = 0; i < this.n; i++) {
      this.z[i] += this.v[i] * dt;
    }
  }

  clearForces(): void {
    this.force.fill(0);
  }

  offsetAt(index: number): number {
    return this.z[index];
  }

  /** Lateral velocity dz/dt at this mass — the "shape-change" velocity a
   * locomotion model (rft-locomotion.ts) needs on top of whatever rigid
   * translation/rotation the body as a whole is undergoing. */
  velocityAt(index: number): number {
    return this.v[index];
  }
}
