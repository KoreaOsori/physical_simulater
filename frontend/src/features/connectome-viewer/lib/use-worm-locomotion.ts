"use client";

import { useEffect, useMemo, useRef, type ElementRef, type RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Group } from "three";

import { BodySpine } from "@/features/connectome-viewer/lib/body-physics";
import { bendOffsetZ, bodyRadiusProfile, type ApExtent, type BodyLandmarks } from "@/features/connectome-viewer/lib/body-pose";
import { computeMovementForcing } from "@/features/connectome-viewer/lib/movement-pose";
import { stepLocomotion, type RigidPose } from "@/features/connectome-viewer/lib/rft-locomotion";
import { MUSCLE_ACTIVATION_MS, useSimulationStore } from "@/store/simulation-store";

export const SEGMENTS_ALONG = 48;
export const MASS_COUNT = SEGMENTS_ALONG + 1;

// Spine physics constants — hand-tuned for a stable, plausible-looking
// response, not measured (see body-physics.ts's module docstring). Moved
// here from WormBodyMesh.tsx now that this hook owns the physics step.
const NEIGHBOR_STIFFNESS = 140;
const RESTORE_STIFFNESS = 60;
const DAMPING = 9;
const PHYSICS_SUBSTEPS = 4;
const MAX_FRAME_DT = 1 / 30; // clamp so a lag spike can't destabilize the integrator

const MUSCLE_FORCE_MAGNITUDE = 66;
const MUSCLE_WIDTH = 0.08;

type OrbitControlsInstance = ElementRef<typeof OrbitControls>;

/** Creates the BodySpine instance both use-worm-locomotion (physics) and
 * WormBodyMesh (rendering) read from — created ONCE at the ConnectomeCanvas
 * level (a plain useMemo, no R3F context needed) and passed to both, since a
 * hook that itself calls useFrame can only run inside <Canvas>, but the
 * spine object needs to be shared with a sibling component. */
export function createWormSpine(): BodySpine {
  const restZ = new Float64Array(MASS_COUNT);
  for (let i = 0; i < MASS_COUNT; i++) restZ[i] = bendOffsetZ(i / SEGMENTS_ALONG);
  return new BodySpine(restZ, {
    segments: SEGMENTS_ALONG,
    neighborStiffness: NEIGHBOR_STIFFNESS,
    restoreStiffness: RESTORE_STIFFNESS,
    damping: DAMPING,
    massAt: (t) => bodyRadiusProfile(t) ** 2,
  });
}

interface UseWormLocomotionArgs {
  spine: BodySpine;
  extent: ApExtent;
  landmarks: BodyLandmarks;
  lateralIndex: Map<string, { t: number; side: number }>;
  groupRef: RefObject<Group | null>;
  controlsRef: RefObject<OrbitControlsInstance | null>;
}

/**
 * Owns the worm's full body dynamics: the existing lateral bend simulation
 * (BodySpine, created by the caller via createWormSpine so WormBodyMesh can
 * share the same instance) PLUS the new RFT rigid-body locomotion solve
 * (rft-locomotion.ts) that turns that bending into actual net
 * translation/rotation. Runs once per frame, ahead of WormBodyMesh's own
 * geometry-rebuild useFrame (parent components register useFrame before
 * their children in R3F's per-frame call order), then imperatively pushes
 * the resulting rigid pose onto `groupRef` (the <group> wrapping the whole
 * worm scene — see ConnectomeCanvas.tsx) and follows it with the camera via
 * `controlsRef`. Must be called from a component rendered inside <Canvas>
 * (it calls useFrame) — see ConnectomeCanvas.tsx's WormPhysicsDriver.
 */
export function useWormLocomotion({ spine, extent, landmarks, lateralIndex, groupRef, controlsRef }: UseWormLocomotionArgs) {
  // Body-center-relative AP positions (see body-pose.ts's bodyCenterX) —
  // static, matches WormBodyMesh's own vertex x so the RFT solve's shape
  // matches what's actually rendered.
  const localX = useMemo(() => {
    const span = extent.max - extent.min || 1;
    const arr = new Float64Array(MASS_COUNT);
    for (let i = 0; i < MASS_COUNT; i++) arr[i] = (i / SEGMENTS_ALONG) * span - span / 2;
    return arr;
  }, [extent]);

  // Reusable scratch buffers for the per-frame RFT solve — avoids
  // reallocating two 49-element arrays every frame (GC churn at 60fps).
  // Refs, not useMemo: these are intentionally mutated every frame outside
  // React's render cycle, which useMemo values must not be.
  const scratchZRef = useRef<Float64Array>(null);
  const scratchVzRef = useRef<Float64Array>(null);
  if (scratchZRef.current === null) scratchZRef.current = new Float64Array(MASS_COUNT);
  if (scratchVzRef.current === null) scratchVzRef.current = new Float64Array(MASS_COUNT);

  const landmarkT = useMemo(() => {
    const span = extent.max - extent.min || 1;
    return {
      mouth: 0,
      vulva: (landmarks.vulvaX - extent.min) / span,
      anus: (landmarks.anusX - extent.min) / span,
    };
  }, [landmarks, extent]);

  // Pose starts at the body's real-world center (bodyCenterX) so frame 0
  // renders in exactly the same place as before this feature existed — the
  // group's local origin now coincides with the body's own center (every
  // rendered position was re-centered around it, see body-pose.ts), so
  // starting the pose there means zero visible jump when locomotion begins.
  const bodyCenterXValue = (extent.min + extent.max) / 2;
  const poseRef = useRef<RigidPose>({ x: bodyCenterXValue, z: 0, theta: 0 });
  const prevPoseRef = useRef<{ x: number; z: number }>({ x: bodyCenterXValue, z: 0 });
  useEffect(() => {
    poseRef.current = { x: bodyCenterXValue, z: 0, theta: 0 };
    prevPoseRef.current = { x: bodyCenterXValue, z: 0 };
  }, [bodyCenterXValue]);

  useFrame((_state, delta) => {
    const now = performance.now();
    const { muscleActivations, movementPulse } = useSimulationStore.getState();

    for (const activation of muscleActivations) {
      const age = now - activation.startedAt;
      if (age < 0 || age > MUSCLE_ACTIVATION_MS) continue;
      const info = lateralIndex.get(activation.effectorId);
      if (!info || info.side === 0) continue;
      const strength = 1 - age / MUSCLE_ACTIVATION_MS;
      spine.applyForce(info.t, info.side * strength * MUSCLE_FORCE_MAGNITUDE, MUSCLE_WIDTH);
    }

    const movement = computeMovementForcing(movementPulse, now, landmarkT);
    for (const f of movement.lateralForces) spine.applyForce(f.t, f.magnitude, f.width);

    const dt = Math.min(delta, MAX_FRAME_DT);
    const subDt = dt / PHYSICS_SUBSTEPS;
    for (let s = 0; s < PHYSICS_SUBSTEPS; s++) spine.step(subDt);
    spine.clearForces();

    const scratchZ = scratchZRef.current!;
    const scratchVz = scratchVzRef.current!;
    for (let i = 0; i < MASS_COUNT; i++) {
      scratchZ[i] = spine.offsetAt(i);
      scratchVz[i] = spine.velocityAt(i);
    }
    poseRef.current = stepLocomotion(poseRef.current, localX, scratchZ, scratchVz, dt);

    const group = groupRef.current;
    if (group) {
      group.position.set(poseRef.current.x, 0, poseRef.current.z);
      group.rotation.y = -poseRef.current.theta;
    }
    // Minimal debug readout for e2e/e2e-regression-tests.md's
    // worm-locomotion.spec.ts (no other way to assert "did the worm actually
    // move/stay on screen" without either parsing pixels or reaching into
    // R3F internals from outside the component tree). Harmless: three
    // numbers, no state, overwritten every frame.
    if (typeof window !== "undefined") {
      (window as unknown as { __wormPose?: RigidPose }).__wormPose = poseRef.current;
    }
    // Camera follow: translate the camera by the SAME delta the target
    // moved, so the view slides along with the worm instead of just
    // re-aiming at it from a fixed spot (which would look like the camera
    // spinning in place rather than tracking).
    const controls = controlsRef.current;
    if (controls) {
      const dx = poseRef.current.x - prevPoseRef.current.x;
      const dz = poseRef.current.z - prevPoseRef.current.z;
      controls.object.position.x += dx;
      controls.object.position.z += dz;
      controls.target.set(poseRef.current.x, 0, poseRef.current.z);
      controls.update();
    }
    prevPoseRef.current = { x: poseRef.current.x, z: poseRef.current.z };
  });
}
