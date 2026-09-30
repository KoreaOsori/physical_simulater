"use client";

import { useEffect, useMemo, useState } from "react";
import { Html } from "@react-three/drei";
import type { ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";

import { worldToSceneMm } from "@/features/virtual-organism/lib/motion";
import { makeFilterPaperTexture, makeRulerTexture, makeSpeckleTexture } from "@/features/virtual-organism/lib/textures";

/** 3D 실험실 장면의 환경 소품(docs/44). 크기는 전부 백엔드 폐루프가 실제로 쓰는
 * 값(아레나 반경, 광원 위치, 가우시안 시그마)에서 그대로 가져온다 -- 장면의
 * 1 단위 = 1mm. 모양·재질은 실제 실험 기구를 참고한 도식적 재현이다. */

/** 한 번 만들고 언마운트 때 해제하는 텍스처. 인자 없는 팩토리만 받는다(재생성 없음). */
function useDisposable<T extends { dispose: () => void }>(make: () => T): T {
  const [value] = useState(make);
  useEffect(() => () => value.dispose(), [value]);
  return value;
}

export function LabBench({ y }: { y: number }) {
  const tex = useDisposable(() => makeSpeckleTexture("#3a3f44", "#101214", 5000, 7, 6));
  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <circleGeometry args={[400, 64]} />
      <meshStandardMaterial map={tex} roughness={0.82} metalness={0.05} />
    </mesh>
  );
}

/** 벽 두께가 있는 투명 원통 용기(페트리 접시 / 아크릴 아레나 벽). */
function ClearWall({ innerR, thickness, bottomY, height, color, ior }: { innerR: number; thickness: number; bottomY: number; height: number; color: string; ior: number }) {
  const geo = useMemo(() => {
    const outer = innerR + thickness;
    const pts = [
      new THREE.Vector2(innerR, bottomY),
      new THREE.Vector2(outer, bottomY),
      new THREE.Vector2(outer, bottomY + height - thickness * 0.5),
      new THREE.Vector2(outer - thickness * 0.5, bottomY + height),
      new THREE.Vector2(innerR, bottomY + height - thickness * 0.2),
      new THREE.Vector2(innerR, bottomY),
    ];
    return new THREE.LatheGeometry(pts, 128);
  }, [innerR, thickness, bottomY, height]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <mesh geometry={geo}>
      {/* transmission(굴절) 대신 알파 블렌딩 -- 굴절 패스는 장면 전체를 한 번 더 그려 느려진다 */}
      <meshPhysicalMaterial color={color} roughness={0.05} ior={ior} clearcoat={1} transparent opacity={0.22} depthWrite={false} side={THREE.DoubleSide} />
    </mesh>
  );
}

/** 바닥 클릭(냄새원 옮기기, docs/45). 드래그(카메라 회전) 끝의 클릭은 무시한다. */
export type FloorClick = ((x_um: number, y_um: number) => void) | null;

function floorClickHandler(onFloorClick: FloorClick) {
  if (!onFloorClick) return undefined;
  return (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 4) return;
    e.stopPropagation();
    onFloorClick(e.point.x * 1000, -e.point.z * 1000);
  };
}

/** 9cm NGM 한천 플레이트(WormBook 표준 화학주성 배지 규모 -- virtual_worm.py와 동일한 축척). */
export function PetriDish({ radiusMm, onFloorClick }: { radiusMm: number; onFloorClick: FloorClick }) {
  const agarTex = useDisposable(() => makeSpeckleTexture("#e2d4a4", "#9c8a55", 2600, 3, 3));
  const agarDepth = 4;
  return (
    <group>
      {/* 접시 바닥판 */}
      <mesh position={[0, -agarDepth - 0.5, 0]}>
        <cylinderGeometry args={[radiusMm + 1.2, radiusMm + 1.2, 1, 128]} />
        <meshStandardMaterial color="#e8f0f2" roughness={0.08} transparent opacity={0.3} depthWrite={false} />
      </mesh>
      {/* 한천(NGM agar) -- 반투명하고 표면이 젖어 광택이 있다 */}
      <mesh position={[0, -agarDepth / 2, 0]} receiveShadow onClick={floorClickHandler(onFloorClick)}>
        <cylinderGeometry args={[radiusMm + 0.15, radiusMm + 0.15, agarDepth, 128]} />
        {/* 화면 전체를 덮는 면이라 physical(clearcoat) 대신 standard -- 통합 GPU에서 프레임이 크게 떨어졌다(docs/44 측정) */}
        <meshStandardMaterial map={agarTex} color="#f2e6bd" roughness={0.38} envMapIntensity={0.45} />
      </mesh>
      <ClearWall innerR={radiusMm + 0.15} thickness={1} bottomY={-agarDepth - 1} height={14} color="#eef6f8" ior={1.55} />
      <Html position={[-radiusMm * 0.72, 0.5, radiusMm * 0.78]} center distanceFactor={60} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div className="vo-scene-label">
          <strong>NGM 한천 플레이트 · 지름 {Math.round(radiusMm * 2)}mm</strong>
          <em>WormBook 표준 화학주성 배지 규모</em>
        </div>
      </Html>
    </group>
  );
}

/** 초파리 아레나(docs/45에서 비행 챔버로 확장) -- 흰 무광 바닥 + 높은 투명 아크릴
 * 원통 벽 + 맨 위 덮개 유리. 원래 보행 아레나(벽 4mm + 낮은 덮개)는 날 수 없어서, 같은
 * 바닥 지름을 유지한 채 벽만 높였다. 챔버 높이는 데모 규모 선택(측정값 아님). */
export function FlyChamber({ radiusMm, heightMm, onFloorClick }: { radiusMm: number; heightMm: number; onFloorClick: FloorClick }) {
  const floorTex = useDisposable(() => makeSpeckleTexture("#f1f0ec", "#b9b6ad", 1400, 5, 2));
  const floorDepth = 3;
  return (
    <group>
      <mesh position={[0, -floorDepth / 2, 0]} receiveShadow onClick={floorClickHandler(onFloorClick)}>
        <cylinderGeometry args={[radiusMm + 2.5, radiusMm + 2.5, floorDepth, 128]} />
        <meshStandardMaterial map={floorTex} roughness={0.78} />
      </mesh>
      <ClearWall innerR={radiusMm} thickness={1.2} bottomY={0} height={heightMm} color="#f4fbff" ior={1.49} />
      {/* 덮개 유리 -- 시야를 가리지 않도록 아주 옅게 */}
      <mesh position={[0, heightMm + 0.15, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[radiusMm + 1.2, 96]} />
        <meshStandardMaterial color="#ffffff" roughness={0.05} transparent opacity={0.05} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <Html position={[-radiusMm * 0.72, 0.5, radiusMm * 0.8]} center distanceFactor={40} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div className="vo-scene-label">
          <strong>비행 챔버 · 지름 {Math.round(radiusMm * 2)}mm · 높이 {Math.round(heightMm)}mm</strong>
          <em>데모 규모 -- 특정 논문의 치수 재현 아님</em>
        </div>
      </Html>
    </group>
  );
}

/** 유인물질 한 방울(웜) -- 한천에 스며든 젖은 자국 + 작은 액적. */
export function AttractantSpot({ x_um, y_um, label }: { x_um: number; y_um: number; label: string }) {
  const [x, z] = worldToSceneMm(x_um, y_um);
  return (
    <group position={[x, 0, z]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.004, 0]}>
        <circleGeometry args={[1.6, 48]} />
        <meshPhysicalMaterial color="#d8c78e" roughness={0.03} clearcoat={1} transparent opacity={0.45} depthWrite={false} />
      </mesh>
      <mesh scale={[0.9, 0.22, 0.9]}>
        <sphereGeometry args={[1, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshPhysicalMaterial color="#f4f8fa" roughness={0.02} clearcoat={1} transparent opacity={0.45} />
      </mesh>
      <Html position={[0, 1.2, 0]} center distanceFactor={70} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div className="vo-scene-label source">{label}</div>
      </Html>
    </group>
  );
}

/** 냄새원(초파리) -- 냄새 용액을 적신 여과지 원판. */
export function OdorFilterPaper({ x_um, y_um, label }: { x_um: number; y_um: number; label: string }) {
  const tex = useDisposable(makeFilterPaperTexture);
  const [x, z] = worldToSceneMm(x_um, y_um);
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.06, 0]} receiveShadow>
        <cylinderGeometry args={[2.2, 2.2, 0.12, 48]} />
        <meshStandardMaterial map={tex} roughness={0.95} />
      </mesh>
      <Html position={[0, 2.2, 0]} center distanceFactor={40} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div className="vo-scene-label source">{label}</div>
      </Html>
    </group>
  );
}

/** 금속자 -- 실제 크기 감각용 소품(1 단위 = 1mm). */
export function Ruler({ lengthMm, position }: { lengthMm: number; position: [number, number, number] }) {
  const tex = useDisposable(() => makeRulerTexture(lengthMm));
  const width = 9;
  const total = lengthMm + 2;
  return (
    <mesh position={position} receiveShadow>
      <boxGeometry args={[total, 0.6, width]} />
      {/* 윗면(+y, 인덱스 2)에만 눈금 텍스처 */}
      <meshStandardMaterial attach="material-0" color="#aeb3b8" metalness={0.8} roughness={0.35} />
      <meshStandardMaterial attach="material-1" color="#aeb3b8" metalness={0.8} roughness={0.35} />
      <meshStandardMaterial attach="material-2" map={tex} metalness={0.55} roughness={0.38} />
      <meshStandardMaterial attach="material-3" color="#aeb3b8" metalness={0.8} roughness={0.35} />
      <meshStandardMaterial attach="material-4" color="#aeb3b8" metalness={0.8} roughness={0.35} />
      <meshStandardMaterial attach="material-5" color="#aeb3b8" metalness={0.8} roughness={0.35} />
    </mesh>
  );
}

// 장면이 logarithmicDepthBuffer를 쓰므로(0.01mm 개체 ~ 수백 mm 실험대를 한 장면에)
// 커스텀 셰이더도 logdepth 청크를 넣어야 깊이 비교가 맞는다.
const FIELD_VERT = /* glsl */ `
  #include <common>
  #include <logdepthbuf_pars_vertex>
  varying vec2 vWorld;
  void main() {
    vec4 w = modelMatrix * vec4(position, 1.0);
    vWorld = w.xz;
    gl_Position = projectionMatrix * viewMatrix * w;
    #include <logdepthbuf_vertex>
  }
`;
const FIELD_FRAG = /* glsl */ `
  #include <logdepthbuf_pars_fragment>
  uniform vec2 uSource;
  uniform float uSigma;
  uniform vec3 uColor;
  uniform float uOpacity;
  varying vec2 vWorld;
  void main() {
    #include <logdepthbuf_fragment>
    vec2 d = vWorld - uSource;
    float c = exp(-dot(d, d) / (2.0 * uSigma * uSigma));
    // 등농도선(0.1 간격)을 옅게 -- 지도처럼 기울기를 읽을 수 있게
    // bands: 등농도선(c = 0.1, 0.2, ...) 위에서 0.5, 그 사이에선 0 쪽
    float bands = abs(fract(c * 10.0) - 0.5);
    float line = smoothstep(0.44, 0.49, bands) * smoothstep(0.02, 0.05, c);
    float a = uOpacity * (c * 0.75 + line * 0.35);
    gl_FragColor = vec4(uColor, a);
  }
`;

/** 농도장 시각화(실제로는 보이지 않는 화학 기울기) -- 백엔드와 같은 가우시안
 * 식(exp(-r²/2σ²))을 셰이더로 그대로 계산해 아레나 바닥 위에 얹는다. */
export function ConcentrationField({ radiusMm, sourceUm, sigmaUm, color, opacity }: { radiusMm: number; sourceUm: [number, number]; sigmaUm: number; color: string; opacity: number }) {
  const [sx, sz] = worldToSceneMm(sourceUm[0], sourceUm[1]);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: FIELD_VERT,
        fragmentShader: FIELD_FRAG,
        transparent: true,
        depthWrite: false,
        uniforms: {
          uSource: { value: new THREE.Vector2(sx, sz) },
          uSigma: { value: sigmaUm / 1000 },
          uColor: { value: new THREE.Color(color) },
          uOpacity: { value: opacity },
        },
      }),
    [sx, sz, sigmaUm, color, opacity],
  );
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.006, 0]} material={material} renderOrder={1}>
      <circleGeometry args={[radiusMm, 128]} />
    </mesh>
  );
}

/** 지나온 자취 -- 바닥 위 얇은 띠(웜은 한천에 파인 홈처럼, 초파리는 옅은 선). */
export function TrailRibbon({ trail, widthMm, color, opacity }: { trail: [number, number][]; widthMm: number; color: string; opacity: number }) {
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    if (trail.length < 2) return g;
    const pos: number[] = [];
    const idx: number[] = [];
    const pts = trail.map(([x, y]) => worldToSceneMm(x, y));
    for (let i = 0; i < pts.length; i++) {
      const a = pts[Math.max(0, i - 1)];
      const b = pts[Math.min(pts.length - 1, i + 1)];
      let dx = b[0] - a[0];
      let dz = b[1] - a[1];
      const len = Math.hypot(dx, dz) || 1;
      dx /= len;
      dz /= len;
      const hw = widthMm / 2;
      pos.push(pts[i][0] - dz * hw, 0.003, pts[i][1] + dx * hw, pts[i][0] + dz * hw, 0.003, pts[i][1] - dx * hw);
      if (i > 0) {
        const k = (i - 1) * 2;
        idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3);
      }
    }
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setIndex(idx);
    return g;
  }, [trail, widthMm]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <mesh geometry={geo} renderOrder={1}>
      <meshBasicMaterial color={color} transparent opacity={opacity} depthWrite={false} side={THREE.DoubleSide} />
    </mesh>
  );
}
