"use client";

import { useEffect, useRef, type MutableRefObject, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { samplePlan, worldToSceneMm, type MotionPlan } from "@/features/virtual-organism/lib/motion";
import type { OrganismKeys } from "@/features/virtual-organism/lib/use-organism-keys";
import type { PilotState } from "@/features/virtual-organism/lib/use-pilot";

/** 모델(웜/초파리)이 매 프레임 읽는 운동 상태. travelledMm는 진행 방향 기준
 * 부호 있는 누적 이동거리라 후진하면 줄어든다 -- 걸음/굽이 위상이 실제 이동과
 * 같은 방향으로 돌게 하는 값. */
export interface OrganismKinematics {
  x: number;
  z: number;
  headingRad: number;
  travelledMm: number;
  turning: number;
  turnSign: number;
  /** 바닥 위 높이(mm) -- 초파리 비행. */
  altitudeMm: number;
  airborne: boolean;
}

export type CameraMode = "follow" | "overview";

type OrbitLike = { target: THREE.Vector3; update: () => void };

interface OrganismDriverProps {
  motion: MotionPlan;
  kinematicsRef: MutableRefObject<OrganismKinematics>;
  /** 수동 조종 중이면 위치·방향·고도를 실시간 조종 상태에서 읽는다. */
  pilotRef: MutableRefObject<PilotState> | null;
  keysRef: MutableRefObject<OrganismKeys>;
  cameraMode: CameraMode;
  /** 제자리 회전 때도 다리/몸이 움직이게 -- 회전 반경(mm) × 각변화를 이동거리로 환산. */
  turnRadiusMm: number;
  children: ReactNode;
}

const CAM_YAW_RATE = 1.6; // rad/s -- 방향키 ←→
const CAM_PITCH_RATE = 1.1; // rad/s -- 방향키 ↑↓
const MIN_POLAR = 0.12;
const MAX_POLAR = Math.PI * 0.47;

const _offset = new THREE.Vector3();
const _sph = new THREE.Spherical();

/** 모션 계획(자동) 또는 조종 상태(수동)를 매 프레임 읽어 개체 그룹을 옮기고,
 * 추적 카메라면 카메라도 같은 변위만큼 끌고 간다. 방향키는 카메라 시선을 돌리고,
 * 수동 조종에선 그 시선 방향이 W 전진 방향이 된다(3인칭 조종). */
export function OrganismDriver({ motion, kinematicsRef, pilotRef, keysRef, cameraMode, turnRadiusMm, children }: OrganismDriverProps) {
  const group = useRef<THREE.Group>(null);
  const lastRef = useRef<{ x: number; z: number; h: number } | null>(null);
  // 3D 장면이 사라지면(나침반 보기) 시선 방향은 다시 방향키로 직접 돌린다
  useEffect(
    () => () => {
      if (pilotRef) pilotRef.current.cameraDriven = false;
    },
    [pilotRef],
  );

  useFrame((three, delta) => {
    const controls = three.controls as unknown as OrbitLike | null;
    const k = kinematicsRef.current;
    let x: number;
    let z: number;
    let heading: number;
    let targetAlt = 0;
    let turning: number;
    let turnSign: number;
    const pilot = pilotRef?.current ?? null;
    if (pilot) {
      [x, z] = worldToSceneMm(pilot.x_um, pilot.y_um);
      heading = pilot.headingRad;
      targetAlt = pilot.z_um / 1000;
      turning = pilot.turning;
      turnSign = pilot.turnSign;
      k.airborne = pilot.airborne;
    } else {
      const p = samplePlan(motion, performance.now());
      [x, z] = worldToSceneMm(p.x_um, p.y_um);
      heading = p.headingRad;
      turning = p.turning;
      turnSign = p.turnSign;
      k.airborne = false;
    }
    // 고도는 부드럽게(자동 전환 시 착지 등이 순간이동으로 보이지 않게). 조종 중엔 거의 즉시.
    const altLerp = pilot ? 1 - Math.exp(-delta * 30) : 1 - Math.exp(-delta * 3);
    k.altitudeMm += (targetAlt - k.altitudeMm) * altLerp;

    const prev = lastRef.current;
    if (prev) {
      const dx = x - prev.x;
      const dz = z - prev.z;
      const forward = dx * Math.cos(prev.h) - dz * Math.sin(prev.h);
      let dh = heading - prev.h;
      if (dh > Math.PI) dh -= Math.PI * 2;
      if (dh < -Math.PI) dh += Math.PI * 2;
      k.travelledMm += forward + Math.abs(dh) * turnRadiusMm;
      if (cameraMode === "follow" && controls) {
        three.camera.position.x += dx;
        three.camera.position.z += dz;
      }
    }
    lastRef.current = { x, z, h: heading };
    k.x = x;
    k.z = z;
    k.headingRad = heading;
    k.turning = turning;
    k.turnSign = turnSign;

    if (group.current) {
      group.current.position.set(x, 0, z);
      group.current.rotation.y = heading;
    }

    if (controls) {
      if (cameraMode === "follow") {
        const ty = k.altitudeMm;
        three.camera.position.y += ty - controls.target.y;
        controls.target.set(x, ty, z);
      }
      // 방향키 = 카메라 시선. 목표점 둘레로 카메라를 돌린다(마우스 드래그와 같은 궤도).
      const keys = keysRef.current;
      const yaw = ((keys.left ? 1 : 0) - (keys.right ? 1 : 0)) * CAM_YAW_RATE * delta;
      // ↑ = 시선을 위로(카메라가 낮아짐), ← = 시선을 왼쪽으로(위에서 봐서 반시계)
      const pitch = ((keys.up ? 1 : 0) - (keys.down ? 1 : 0)) * CAM_PITCH_RATE * delta;
      if (yaw !== 0 || pitch !== 0) {
        _offset.copy(three.camera.position).sub(controls.target);
        _sph.setFromVector3(_offset);
        _sph.theta += yaw;
        _sph.phi = Math.min(MAX_POLAR, Math.max(MIN_POLAR, _sph.phi + pitch));
        _offset.setFromSpherical(_sph);
        three.camera.position.copy(controls.target).add(_offset);
      }
      controls.update();
      if (pilotRef) {
        // 카메라가 목표를 바라보는 수평 방향 -> 세계 heading(수학 좌표계: 장면 -z가 세계 +y)
        const dirX = controls.target.x - three.camera.position.x;
        const dirZ = controls.target.z - three.camera.position.z;
        if (Math.hypot(dirX, dirZ) > 1e-6) pilotRef.current.viewYawRad = Math.atan2(-dirZ, dirX);
        pilotRef.current.cameraDriven = true;
      }
    }
  });

  return <group ref={group}>{children}</group>;
}
