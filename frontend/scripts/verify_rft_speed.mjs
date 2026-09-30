// Standalone reproducibility check (same spirit as docs/07 and docs/17's
// "Node.js 독립 실행으로 검증"): runs the ACTUAL production physics modules
// (not a reimplementation) outside the browser/React tree, converts the
// resulting displacement into real micrometres via scale.ts, and compares it
// against Fang-Yen et al. 2010's measured C. elegans crawling speed
// (~200-400 um/s). See docs/22-worm-locomotion-real-speed-grounding.md.
//
// Run with: node frontend/scripts/verify_rft_speed.mjs
// (Node >=22.6 needed for native .ts type-stripping; this repo runs Node 24.)

import { bendOffsetZ, bodyRadiusProfile } from "../src/features/connectome-viewer/lib/body-pose.ts";
import { BodySpine } from "../src/features/connectome-viewer/lib/body-physics.ts";
import { computeMovementForcing } from "../src/features/connectome-viewer/lib/movement-pose.ts";
import { stepLocomotion } from "../src/features/connectome-viewer/lib/rft-locomotion.ts";
import { SCENE_UNITS_TO_UM } from "../src/features/connectome-viewer/lib/scale.ts";

// Mirrors use-worm-locomotion.ts's createWormSpine()/constants exactly.
const SEGMENTS_ALONG = 48;
const MASS_COUNT = SEGMENTS_ALONG + 1;
const NEIGHBOR_STIFFNESS = 140;
const RESTORE_STIFFNESS = 60;
const DAMPING = 9;
const PHYSICS_SUBSTEPS = 4;
const MOVEMENT_ANIMATION_MS = 2200;

// Real body span is ~12 scene units (720 um / 60) per body-pose.ts's
// ApExtent, computed here directly rather than importing a live connectome.
const SPAN = 12;

function buildSpine() {
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

/**
 * Runs `totalS` seconds of physics. If `repeatPulse` is false (the default,
 * and the realistic case: a user presses "forward" once), only ONE
 * MOVEMENT_ANIMATION_MS pulse fires and the rest of `totalS` just lets the
 * spring chain settle back to rest — this is the scenario RFT_SPEED_SCALE is
 * actually derived from. If `repeatPulse` is true, a fresh pulse re-fires
 * the instant the previous one ends (simulating the button being held/spammed
 * continuously) — kept only to document a separate, NOT-yet-fixed issue (see
 * docs/22's "범위 밖" section): because `computeMovementForcing` replays the
 * identical spatial pattern from progress=0 every time, any small
 * per-pulse net-yaw bias compounds pulse after pulse into unrealistic net
 * spin. That compounding issue is out of scope for this pass (it's a
 * forcing-pattern bug, not a speed-constant calibration problem) and is
 * NOT used to derive RFT_SPEED_SCALE below.
 */
function runForward(totalS, { repeatPulse = false } = {}) {
  const spine = buildSpine();
  const localX = new Float64Array(MASS_COUNT);
  for (let i = 0; i < MASS_COUNT; i++) localX[i] = (i / SEGMENTS_ALONG) * SPAN - SPAN / 2;

  let pose = { x: 0, z: 0, theta: 0 };
  const landmarkT = { mouth: 0, vulva: 0.5, anus: 0.88 };
  const dt = 1 / 60;
  const scratchZ = new Float64Array(MASS_COUNT);
  const scratchVz = new Float64Array(MASS_COUNT);

  let now = 0;
  let pulseStart = 0;
  const steps = Math.round(totalS / dt);
  for (let step = 0; step < steps; step++) {
    const tMs = now * 1000;
    if (repeatPulse && tMs - pulseStart >= MOVEMENT_ANIMATION_MS) pulseStart = tMs;
    const pulse = { direction: "forward", startedAt: pulseStart };
    const movement = computeMovementForcing(pulse, tMs, landmarkT);
    for (const f of movement.lateralForces) spine.applyForce(f.t, f.magnitude, f.width);

    const subDt = dt / PHYSICS_SUBSTEPS;
    for (let s = 0; s < PHYSICS_SUBSTEPS; s++) spine.step(subDt);
    spine.clearForces();

    for (let i = 0; i < MASS_COUNT; i++) {
      scratchZ[i] = spine.offsetAt(i);
      scratchVz[i] = spine.velocityAt(i);
    }
    pose = stepLocomotion(pose, localX, scratchZ, scratchVz, dt);
    now += dt;
  }
  return pose;
}

const TARGET_LOW = 200;
const TARGET_HIGH = 400;
const PULSE_S = MOVEMENT_ANIMATION_MS / 1000;

function report(label, pose, elapsedS) {
  const dispSceneUnits = Math.hypot(pose.x, pose.z);
  const dispUm = dispSceneUnits * SCENE_UNITS_TO_UM;
  const speedUmPerS = dispUm / elapsedS;
  const bodyLengths = dispSceneUnits / SPAN;
  console.log(`--- ${label} ---`);
  console.log(`변위: ${dispSceneUnits.toFixed(3)} scene units (체장 ${bodyLengths.toFixed(2)}배) / ${elapsedS}s`);
  console.log(`회전: ${pose.theta.toFixed(3)} rad (${(pose.theta / (2 * Math.PI)).toFixed(2)} 바퀴)`);
  console.log(`환산 속도: ${speedUmPerS.toFixed(1)} um/s  (SCENE_UNITS_TO_UM=${SCENE_UNITS_TO_UM})`);
  return speedUmPerS;
}

console.log(`문헌 목표(Fang-Yen et al. 2010, C. elegans 크롤링): ${TARGET_LOW}-${TARGET_HIGH} um/s\n`);

// Primary measurement: single isolated "forward" press (realistic single
// button click), settled fully (3s of no-op afterward) — this is what
// RFT_SPEED_SCALE is derived from.
const singlePulsePose = runForward(PULSE_S + 3, { repeatPulse: false });
const singleSpeed = report(`단발 전진 1회 (${PULSE_S}s 펄스 + 3s 정착)`, singlePulsePose, PULSE_S);
const singleInRange = singleSpeed >= TARGET_LOW && singleSpeed <= TARGET_HIGH;
console.log(singleInRange ? "PASS: 목표 범위 안\n" : `범위 밖 (목표 중앙값 대비 ${(singleSpeed / ((TARGET_LOW + TARGET_HIGH) / 2)).toFixed(2)}x)\n`);

// Secondary, informational only: rapid repeated presses with zero gap.
// Demonstrates the separate net-yaw-accumulation issue documented in
// docs/22's "범위 밖으로 남겨둔 것" section — NOT used for calibration.
for (const totalS of [6, 10]) {
  const pose = runForward(totalS, { repeatPulse: true });
  report(`(참고, 보정에 미사용) ${totalS}s 연속 재입력`, pose, totalS);
}
