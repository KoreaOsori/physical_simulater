"use client";

import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import type { OrganismKinematics } from "@/features/virtual-organism/components/OrganismDriver";

/** 3D 실험실 뷰의 예쁜꼬마선충(docs/44) -- 한천 위에 옆으로 누워 등배 방향으로
 * 굽이치며 기어가는 성체 자웅동체. 전부 코드로 만든 도식적 모델이며 EM
 * 재구성 메시가 아니다.
 *
 * 실측에 기댄 값:
 * - 체장 약 1mm, 체폭 약 80μm (WormBook, 성체 자웅동체).
 * - 한천 위 기어가기(crawling) 파장 ≈ 0.65 체장 -- Fang-Yen et al. 2010
 *   (PNAS 107:20323; 이 프로젝트가 이동 속도 296μm/s로 이미 인용한 논문).
 * - 굽이 파동의 위상은 "실제로 이동한 거리 / 파장"으로만 진행한다 -- 한천 위
 *   기어가기는 미끄러짐이 적어 몸 파동이 거의 제자리에 남는 궤적을 따라가기
 *   때문(no-slip 근사). 즉 멈춰 있으면 파동도 멈추고, 후진하면 파동도 거꾸로
 *   간다 -- 애니메이션이 폐루프의 실제 이동과 어긋나지 않게.
 * 손으로 정한 값: 굽이 진폭, 인두 구근/장/알 위치(대략적 해부 비율), 색·재질. */

export const WORM_LENGTH_MM = 1.0;
const MAX_RADIUS_MM = 0.04;
const WAVELENGTH_MM = 0.65 * WORM_LENGTH_MM;
const BEND_AMPLITUDE_RAD = 0.62; // 접선각 진폭 -- 손튜닝(실제 기어가기 자세와 비슷해 보이는 값)
const RINGS = 72;
const RADIAL = 14;
const EGG_COUNT = 9;

function bodyRadius(s: number): number {
  // s: 0 = 머리 끝, 1 = 꼬리 끝. 머리는 뭉툭하게 둥글고, 꼬리는 길게 뾰족해진다.
  const head = Math.sqrt(Math.min(1, s / 0.05));
  const tail = s < 0.78 ? 1 : Math.pow(Math.max(0, (1 - s) / 0.22), 1.25);
  return MAX_RADIUS_MM * Math.max(0.035, head * tail * (0.9 + 0.1 * Math.sin(Math.PI * s)));
}

function gutRadius(s: number): number {
  // 인두(pharynx): 가는 관 + 중부 구근(metacorpus) + 말단 구근(terminal bulb),
  // 이어서 인두-장 판막에서 잘록해졌다가 장(intestine)이 꼬리 근처까지.
  if (s < 0.012) return 0.001;
  if (s < 0.145) {
    const g = (c: number, w: number) => Math.exp(-(((s - c) / w) ** 2));
    return MAX_RADIUS_MM * (0.18 + 0.28 * g(0.068, 0.018) + 0.36 * g(0.128, 0.014));
  }
  if (s < 0.17) return MAX_RADIUS_MM * 0.12;
  if (s < 0.88) return MAX_RADIUS_MM * (0.44 + 0.04 * Math.sin(s * 40));
  return MAX_RADIUS_MM * 0.44 * Math.max(0.05, (0.93 - s) / 0.05);
}

function tubeGeometry(): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(RINGS * RADIAL * 3), 3));
  const idx: number[] = [];
  for (let i = 0; i < RINGS - 1; i++) {
    for (let j = 0; j < RADIAL; j++) {
      const a = i * RADIAL + j;
      const b = i * RADIAL + ((j + 1) % RADIAL);
      const c = (i + 1) * RADIAL + j;
      const d = (i + 1) * RADIAL + ((j + 1) % RADIAL);
      idx.push(a, b, c, b, d, c);
    }
  }
  geo.setIndex(idx);
  return geo;
}

interface Centerline {
  px: Float32Array;
  pz: Float32Array;
  tx: Float32Array;
  tz: Float32Array;
}

/** 접선각을 적분해 길이가 보존되는 중심선을 만든다(국소 좌표, +x = 앞). */
function computeCenterline(out: Centerline, phase: number, turning: number, turnSign: number) {
  const ds = 1 / (RINGS - 1);
  const angles = new Float32Array(RINGS);
  let mean = 0;
  for (let i = 0; i < RINGS; i++) {
    const s = i * ds;
    const envelope = 0.55 + 0.45 * Math.sin(Math.PI * Math.min(1, s * 1.15));
    const wave = BEND_AMPLITUDE_RAD * (1 - 0.6 * turning) * envelope * Math.cos((2 * Math.PI * s * WORM_LENGTH_MM) / WAVELENGTH_MM - phase);
    // 재정향(pirouette) 중엔 몸 전체를 한쪽으로 크게 말아 오메가 굽힘에 가깝게
    const omega = turnSign * turning * 1.35 * Math.PI * (s - 0.5);
    angles[i] = wave + omega;
    mean += angles[i];
  }
  mean /= RINGS;
  let x = 0;
  let z = 0;
  let cx = 0;
  let cz = 0;
  for (let i = 0; i < RINGS; i++) {
    const a = angles[i] - mean;
    const dirX = Math.cos(a);
    const dirZ = -Math.sin(a);
    out.px[i] = x;
    out.pz[i] = z;
    out.tx[i] = dirX;
    out.tz[i] = dirZ;
    cx += x;
    cz += z;
    x -= dirX * ds * WORM_LENGTH_MM;
    z -= dirZ * ds * WORM_LENGTH_MM;
  }
  cx /= RINGS;
  cz /= RINGS;
  for (let i = 0; i < RINGS; i++) {
    out.px[i] -= cx;
    out.pz[i] -= cz;
  }
}

function writeTube(geo: THREE.BufferGeometry, cl: Centerline, radiusAt: (s: number) => number, lift: number, ySquash = 0.92) {
  const pos = geo.getAttribute("position") as THREE.BufferAttribute;
  for (let i = 0; i < RINGS; i++) {
    const s = i / (RINGS - 1);
    const r = radiusAt(s);
    // 옆 방향(side) = 접선을 수평면에서 90도 돌린 것, 위 = +y
    const sideX = -cl.tz[i];
    const sideZ = cl.tx[i];
    for (let j = 0; j < RADIAL; j++) {
      const th = (j / RADIAL) * Math.PI * 2;
      const c = Math.cos(th);
      const sn = Math.sin(th);
      pos.setXYZ(i * RADIAL + j, cl.px[i] + sideX * c * r, lift + sn * r * ySquash, cl.pz[i] + sideZ * c * r);
    }
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  geo.computeBoundingSphere();
}

export function WormModel({ kinematicsRef }: { kinematicsRef: MutableRefObject<OrganismKinematics> }) {
  const bodyGeo = useMemo(() => tubeGeometry(), []);
  const gutGeo = useMemo(() => tubeGeometry(), []);
  const shadowGeo = useMemo(() => tubeGeometry(), []);
  useEffect(
    () => () => {
      bodyGeo.dispose();
      gutGeo.dispose();
      shadowGeo.dispose();
    },
    [bodyGeo, gutGeo, shadowGeo],
  );
  const eggRefs = useRef<(THREE.Mesh | null)[]>([]);
  const cl = useMemo<Centerline>(
    () => ({ px: new Float32Array(RINGS), pz: new Float32Array(RINGS), tx: new Float32Array(RINGS), tz: new Float32Array(RINGS) }),
    [],
  );

  useFrame(() => {
    const k = kinematicsRef.current;
    const phase = (2 * Math.PI * k.travelledMm) / WAVELENGTH_MM;
    computeCenterline(cl, phase, k.turning, k.turnSign);
    const lift = MAX_RADIUS_MM * 0.92;
    writeTube(bodyGeo, cl, bodyRadius, lift);
    writeTube(gutGeo, cl, gutRadius, lift);
    // 몸 모양 그대로 한천 위에 눌린 부드러운 그림자(접촉면 음영)
    writeTube(shadowGeo, cl, (s) => bodyRadius(s) * 1.45, 0.0015, 0.02);

    // 자궁 속 알(성체 자웅동체 몸 가운데 부근) -- 중심선을 따라 몸통 안쪽에 배치
    for (let e = 0; e < EGG_COUNT; e++) {
      const mesh = eggRefs.current[e];
      if (!mesh) continue;
      const s = 0.36 + (e / (EGG_COUNT - 1)) * 0.28;
      const i = Math.round(s * (RINGS - 1));
      const side = (e % 2 === 0 ? 1 : -1) * MAX_RADIUS_MM * 0.38;
      mesh.position.set(cl.px[i] - cl.tz[i] * side, lift + MAX_RADIUS_MM * 0.12, cl.pz[i] + cl.tx[i] * side);
      mesh.rotation.y = Math.atan2(-cl.tz[i], cl.tx[i]);
    }
  });

  return (
    <group>
      <mesh geometry={shadowGeo} renderOrder={1}>
        <meshBasicMaterial color="#2a2210" transparent opacity={0.22} depthWrite={false} />
      </mesh>
      {/* 반투명 큐티클 -- 안쪽의 인두·장·알이 비쳐 보이게(실제 C. elegans는 투명해 현미경으로 내부가 보인다) */}
      <mesh geometry={bodyGeo} renderOrder={2}>
        <meshPhysicalMaterial
          color="#f1ecdc"
          roughness={0.3}
          clearcoat={0.8}
          clearcoatRoughness={0.25}
          transparent
          opacity={0.58}
        />
      </mesh>
      <mesh geometry={gutGeo}>
        <meshStandardMaterial color="#8d7650" roughness={0.75} />
      </mesh>
      {Array.from({ length: EGG_COUNT }, (_, e) => (
        <mesh
          key={e}
          ref={(m) => {
            eggRefs.current[e] = m;
          }}
          scale={[0.028, 0.014, 0.017]}
        >
          <sphereGeometry args={[1, 12, 8]} />
          <meshStandardMaterial color="#cdbf94" roughness={0.6} />
        </mesh>
      ))}
    </group>
  );
}
