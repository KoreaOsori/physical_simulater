"use client";

import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, Lightformer, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

import { FlyModel, FLY_LENGTH_MM } from "@/features/virtual-organism/components/FlyModel";
import {
  AttractantSpot,
  ConcentrationField,
  FlyChamber,
  type FloorClick,
  LabBench,
  OdorFilterPaper,
  PetriDish,
  Ruler,
  TrailRibbon,
} from "@/features/virtual-organism/components/LabEnvironment";
import { OrganismDriver, type CameraMode, type OrganismKinematics } from "@/features/virtual-organism/components/OrganismDriver";
import { WormModel, WORM_LENGTH_MM } from "@/features/virtual-organism/components/WormModel";
import { worldToSceneMm, type MotionPlan } from "@/features/virtual-organism/lib/motion";
import type { OrganismKeys } from "@/features/virtual-organism/lib/use-organism-keys";
import type { PilotState } from "@/features/virtual-organism/lib/use-pilot";

export type Species = "worm" | "fly";

export interface VirtualLabSceneProps {
  species: Species;
  arenaRadiusUm: number;
  sourceUm: [number, number];
  sigmaUm: number;
  trail: [number, number][];
  motion: MotionPlan;
  /** 수동 조종 중이면 실시간 조종 상태(없으면 자동 모션 계획을 재생). */
  pilotRef: MutableRefObject<PilotState> | null;
  keysRef: MutableRefObject<OrganismKeys>;
  showField: boolean;
  cameraMode: CameraMode;
  /** 초파리 비행 챔버 높이(mm). 웜은 0. */
  chamberHeightMm: number;
  /** 냄새원 옮기기 모드일 때 바닥 클릭 처리. */
  onFloorClick: FloorClick;
}

const SPECIES_CFG = {
  worm: {
    bodyMm: WORM_LENGTH_MM,
    followOffset: [0.9, 1.5, 2.1] as [number, number, number],
    minDist: 0.35,
    benchY: -5.5,
    fieldColor: "#9fe07a",
    trailColor: "#8a7a4c",
    trailWidth: 0.03,
    trailOpacity: 0.3,
    turnRadiusMm: 0.15,
    sourceLabel: "유인물질 점원",
  },
  fly: {
    bodyMm: FLY_LENGTH_MM,
    followOffset: [3.5, 5.5, 8] as [number, number, number],
    minDist: 1.2,
    benchY: -3,
    fieldColor: "#ff9a5c",
    trailColor: "#8c8a84",
    trailWidth: 0.1,
    trailOpacity: 0.2,
    turnRadiusMm: 0.6,
    sourceLabel: "cVA(DA1) 냄새원 · 혐오",
  },
} as const;

/** 카메라 모드를 바꿀 때(그리고 처음 한 번) 카메라를 그 모드의 기본 위치로 옮긴다.
 * 그 뒤로는 사용자가 드래그/휠로 자유롭게 돌리고 당길 수 있다. */
function CameraPlacer({ mode, species, kinematicsRef, radiusMm }: { mode: CameraMode; species: Species; kinematicsRef: MutableRefObject<OrganismKinematics>; radiusMm: number }) {
  const get = useThree((s) => s.get);
  const controlsReady = useThree((s) => s.controls !== null);
  useEffect(() => {
    const { camera, controls: rawControls } = get();
    const controls = rawControls as unknown as { target: THREE.Vector3; update: () => void } | null;
    if (!controlsReady || !controls) return;
    const k = kinematicsRef.current;
    if (mode === "follow") {
      const [ox, oy, oz] = SPECIES_CFG[species].followOffset;
      camera.position.set(k.x + ox, oy, k.z + oz);
      controls.target.set(k.x, 0, k.z);
    } else {
      camera.position.set(0, radiusMm * 2.7, radiusMm * 1.15);
      controls.target.set(0, 0, 0);
    }
    controls.update();
  }, [mode, species, get, controlsReady, kinematicsRef, radiusMm]);
  return null;
}

/** 3D 실험실 뷰(docs/44) -- "나침반" SVG 뷰와 같은 백엔드 폐루프 상태를
 * 실제 실험 기구 크기의 장면 속에서, 실제 비율의 개체 모델로 보여준다. */
export function VirtualLabScene({
  species,
  arenaRadiusUm,
  sourceUm,
  sigmaUm,
  trail,
  motion,
  pilotRef,
  keysRef,
  showField,
  cameraMode,
  chamberHeightMm,
  onFloorClick,
}: VirtualLabSceneProps) {
  const cfg = SPECIES_CFG[species];
  const radiusMm = arenaRadiusUm / 1000;
  const first = motion.segments[0].from;
  const [ix, iz] = worldToSceneMm(first.x_um, first.y_um);
  const kinematics = useRef<OrganismKinematics>({
    x: ix,
    z: iz,
    headingRad: (first.heading_deg * Math.PI) / 180,
    travelledMm: 0,
    turning: 0,
    turnSign: 1,
    altitudeMm: 0,
    airborne: false,
  });

  return (
    <Canvas
      dpr={[1, 2]}
      gl={{ antialias: true, logarithmicDepthBuffer: true }}
      camera={{ fov: 38, near: 0.01, far: 3000, position: [ix + cfg.followOffset[0], cfg.followOffset[1], iz + cfg.followOffset[2]] }}
      style={{ cursor: onFloorClick ? "crosshair" : undefined }}
    >
      <color attach="background" args={["#171b1f"]} />
      <fog attach="fog" args={["#171b1f", radiusMm * 4, radiusMm * 12]} />

      <hemisphereLight args={["#e6eeff", "#2b2622", 0.7]} />
      <directionalLight position={[radiusMm, radiusMm * 2.2, radiusMm * 0.6]} intensity={1.8} color="#fff6e8" />
      <directionalLight position={[-radiusMm * 1.4, radiusMm, -radiusMm]} intensity={0.55} color="#cfe2ff" />
      {/* 반사용 조명판(외부 HDR 없이 로컬에서 만든 환경맵) -- 유리·젖은 한천·겹눈의 하이라이트 */}
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={1.4} position={[0, 30, 0]} rotation-x={Math.PI / 2} scale={[40, 40, 1]} />
        <Lightformer form="rect" intensity={1.2} position={[-30, 8, -10]} rotation-y={Math.PI / 2} scale={[30, 10, 1]} color="#dbe8ff" />
        <Lightformer form="rect" intensity={0.8} position={[30, 6, 10]} rotation-y={-Math.PI / 2} scale={[30, 8, 1]} color="#ffe9cf" />
      </Environment>

      <LabBench y={cfg.benchY} />
      {species === "worm" ? (
        <>
          <PetriDish radiusMm={radiusMm} onFloorClick={onFloorClick} />
          <AttractantSpot x_um={sourceUm[0]} y_um={sourceUm[1]} label={cfg.sourceLabel} />
          <Ruler lengthMm={60} position={[0, cfg.benchY + 0.3, radiusMm + 14]} />
        </>
      ) : (
        <>
          <FlyChamber radiusMm={radiusMm} heightMm={chamberHeightMm} onFloorClick={onFloorClick} />
          <OdorFilterPaper x_um={sourceUm[0]} y_um={sourceUm[1]} label={cfg.sourceLabel} />
          <Ruler lengthMm={50} position={[0, cfg.benchY + 0.3, radiusMm + 12]} />
        </>
      )}
      {showField && <ConcentrationField radiusMm={radiusMm} sourceUm={sourceUm} sigmaUm={sigmaUm} color={cfg.fieldColor} opacity={0.5} />}
      <TrailRibbon trail={trail} widthMm={cfg.trailWidth} color={cfg.trailColor} opacity={cfg.trailOpacity} />

      <OrganismDriver
        motion={motion}
        kinematicsRef={kinematics}
        pilotRef={pilotRef}
        keysRef={keysRef}
        cameraMode={cameraMode}
        turnRadiusMm={cfg.turnRadiusMm}
      >
        {species === "worm" ? <WormModel kinematicsRef={kinematics} /> : <FlyModel kinematicsRef={kinematics} />}
        {species === "fly" && <BlobShadow lengthMm={cfg.bodyMm * 1.25} widthMm={cfg.bodyMm * 0.75} kinematicsRef={kinematics} />}
        <LocatorRing bodyMm={cfg.bodyMm} color={pilotRef ? "#7fdcff" : "#9dff7a"} kinematicsRef={kinematics} />
      </OrganismDriver>

      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={cfg.minDist}
        maxDistance={radiusMm * 5}
        maxPolarAngle={Math.PI * 0.47}
      />
      <CameraPlacer mode={cameraMode} species={species} kinematicsRef={kinematics} radiusMm={radiusMm} />
    </Canvas>
  );
}

/** 부드러운 타원 그림자(초파리 몸 아래 바닥). 날아오르면 커지고 옅어진다. */
function BlobShadow({ lengthMm, widthMm, kinematicsRef }: { lengthMm: number; widthMm: number; kinematicsRef: MutableRefObject<OrganismKinematics> }) {
  const ref = useRef<THREE.Mesh>(null);
  const tex = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const ctx = c.getContext("2d")!;
    const g = ctx.createRadialGradient(64, 64, 4, 64, 64, 64);
    g.addColorStop(0, "rgba(0,0,0,0.75)");
    g.addColorStop(0.55, "rgba(0,0,0,0.35)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }, []);
  useEffect(() => () => tex.dispose(), [tex]);
  useFrame(() => {
    const m = ref.current;
    if (!m) return;
    const alt = kinematicsRef.current.altitudeMm;
    const spread = 1 + alt / 6;
    m.scale.set(lengthMm * spread, widthMm * spread, 1);
    (m.material as THREE.MeshBasicMaterial).opacity = 0.55 / (spread * spread);
  });
  return (
    <mesh ref={ref} position={[-0.15, 0.003, 0]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={1}>
      <planeGeometry args={[1, 1]} />
      <meshBasicMaterial map={tex} transparent opacity={0.55} depthWrite={false} />
    </mesh>
  );
}

/** 실제 비율이라 멀리서 보면 1mm 웜 / 2.5mm 초파리가 안 보인다 -- 카메라가 멀어지면
 * 화면상 크기가 일정한 위치 표시 고리를 띄운다(가까이 가면 사라짐). 고도만큼 따라 올라간다. */
function LocatorRing({ bodyMm, color, kinematicsRef }: { bodyMm: number; color: string; kinematicsRef: MutableRefObject<OrganismKinematics> }) {
  const ref = useRef<THREE.Mesh>(null);
  const worldPos = useMemo(() => new THREE.Vector3(), []);
  useFrame((three) => {
    const m = ref.current;
    if (!m) return;
    m.position.y = 0.01 + kinematicsRef.current.altitudeMm;
    m.getWorldPosition(worldPos);
    const d = three.camera.position.distanceTo(worldPos);
    const show = d > bodyMm * 14;
    m.visible = show;
    if (show) {
      const pulse = 1 + 0.12 * Math.sin(performance.now() / 260);
      m.scale.setScalar(d * 0.028 * pulse);
    }
  });
  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} renderOrder={5}>
      <ringGeometry args={[0.72, 1, 48]} />
      <meshBasicMaterial color={color} transparent opacity={0.85} depthTest={false} depthWrite={false} />
    </mesh>
  );
}
