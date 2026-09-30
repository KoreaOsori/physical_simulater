import type { Direction } from "@/types/connectome";

/** How long the body-level "movement" animation plays after the MOVEMENT
 * stage event fires — the last leg of the 10s command sequence (see
 * features/simulation-control/lib/playback.ts). */
export const MOVEMENT_ANIMATION_MS = 2200;

export interface MovementPulse {
  direction: Direction;
  startedAt: number; // performance.now()
}

/** A lateral force to inject into the body's spring-mass spine this frame
 * (see body-physics.ts) — NOT a direct geometry offset. What the body
 * actually does with it (how far it bends, how it settles back) is the
 * physics simulation's job, not this function's. */
export interface LateralForcing {
  t: number; // AP fraction 0-1, where to push
  magnitude: number;
  width: number;
}

/** A local radius squeeze (pharyngeal pumping, rectal/vulval contraction,
 * whole-body tensing) — orthogonal to lateral bending, so these stay direct
 * geometry modulation rather than going through the spine physics. */
export interface RadiusBump {
  t: number;
  amount: number;
  width: number;
}

const NEUTRAL = { lateralForces: [] as LateralForcing[], radiusBumps: [] as RadiusBump[] };

/** Called every frame while a movement pulse is active; returns this frame's
 * forcing (recomputed each call since forward/reverse sweep the injection
 * point over time — see WormBodyMesh). */
export function computeMovementForcing(
  pulse: MovementPulse | null,
  now: number,
  landmarkT: { mouth: number; vulva: number; anus: number },
): { lateralForces: LateralForcing[]; radiusBumps: RadiusBump[] } {
  if (!pulse) return NEUTRAL;
  const age = now - pulse.startedAt;
  if (age < 0 || age > MOVEMENT_ANIMATION_MS) return NEUTRAL;
  const progress = age / MOVEMENT_ANIMATION_MS;
  const envelope = Math.sin(Math.PI * progress); // 0 -> 1 -> 0

  switch (pulse.direction) {
    case "forward":
    case "reverse": {
      // A real traveling bending wave along the WHOLE body at once — not one
      // point sweeping head<->tail. This matters for rft-locomotion.ts: RFT
      // propulsion comes from a bend pattern that's actually wave-shaped at
      // every instant (spatial phase varying smoothly along the body), so
      // the anisotropic drag sees a consistent "this side pushes back" signal
      // to convert into net thrust. A single moving point (the previous
      // version here) bends only a local patch at any instant — correct-
      // looking on screen, but numerically almost reciprocal/incoherent, so
      // the RFT solver saw ~0.004 units of net displacement over 10s real
      // play (measured) — no meaningfully more than a rounding error. See
      // docs/17-worm-rft-locomotion.md.
      const dir = pulse.direction === "forward" ? 1 : -1;
      const cycles = 1.5; // matches the body's own resting S-curve wavelength (body-pose.ts's BEND_CYCLES)
      const temporalCycles = 3; // how many full oscillations sweep through during one MOVEMENT_ANIMATION_MS pulse
      const phase = dir * progress * Math.PI * 2 * temporalCycles;
      const POINT_COUNT = 9;
      const lateralForces: LateralForcing[] = [];
      for (let i = 0; i < POINT_COUNT; i++) {
        const t = i / (POINT_COUNT - 1);
        const magnitude = Math.sin(t * Math.PI * 2 * cycles - phase) * 42 * envelope;
        lateralForces.push({ t, magnitude, width: 0.09 });
      }
      return { lateralForces, radiusBumps: [] };
    }
    case "left":
      return { lateralForces: [{ t: 0.5, magnitude: 30 * envelope, width: 0.6 }], radiusBumps: [] };
    case "right":
      return { lateralForces: [{ t: 0.5, magnitude: -30 * envelope, width: 0.6 }], radiusBumps: [] };
    case "feed": {
      const pulseCount = Math.sin(progress * Math.PI * 5);
      return {
        lateralForces: [],
        radiusBumps: [{ t: landmarkT.mouth, amount: -0.3 * envelope * Math.abs(pulseCount), width: 0.05 }],
      };
    }
    case "defecate":
      return { lateralForces: [], radiusBumps: [{ t: landmarkT.anus, amount: -0.4 * envelope, width: 0.06 }] };
    case "reproduce":
      return { lateralForces: [], radiusBumps: [{ t: landmarkT.vulva, amount: -0.35 * envelope, width: 0.07 }] };
    case "stop":
      return { lateralForces: [], radiusBumps: [{ t: 0.5, amount: 0.12 * envelope, width: 0.9 }] };
    default:
      return NEUTRAL;
  }
}
