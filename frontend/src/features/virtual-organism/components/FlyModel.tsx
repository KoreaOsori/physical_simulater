"use client";

import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import type { OrganismKinematics } from "@/features/virtual-organism/components/OrganismDriver";
import { makeAbdomenTexture, makeCompoundEyeTexture, makeWingTexture } from "@/features/virtual-organism/lib/textures";

/** 3D 실험실 뷰의 성체 초파리(docs/44) -- 전부 코드로 만든 도식적 모델(스캔
 * 데이터 아님). 국소 좌표: +x = 앞, +y = 위, +z = 오른쪽, 단위 mm.
 *
 * 실측에 기댄 값: 체장 약 2.5mm(성체 암컷), 6다리 삼각보행(tripod gait --
 * 한쪽 앞·뒷다리와 반대쪽 가운뎃다리가 한 조로 동시에 움직이는, 빠른 보행
 * 초파리의 전형적 보행 패턴; Mendes et al. 2013, eLife 2:e00231 -- 이
 * 프로젝트가 보행 속도 28mm/s로 이미 인용한 논문).
 * 손으로 정한 값: 보폭(STRIDE_MM), 다리 분절 길이·각도, 색·재질. 걸음 위상은
 * 실제로 이동한 거리로만 진행한다(WormModel과 같은 원칙). */

export const FLY_LENGTH_MM = 2.5;
const STRIDE_MM = 1.9; // 한 걸음 주기당 전진 거리 -- 손튜닝(발이 바닥에서 미끄러져 보이지 않게)
const STANCE_HEIGHT = 0.36; // 흉부 다리 부착점의 바닥 위 높이
// 실제 날갯짓은 약 200Hz(Dickinson류 비행 역학 연구의 전형적 값)라 화면 주사율로는
// 표현할 수 없다 -- 날갯짓이 "보이도록" 느리게 그리는 표현상 값(측정값과 무관).
const WINGBEAT_DISPLAY_HZ = 14;
const WING_STROKE_RAD = 0.95; // 앞뒤 날갯짓 반진폭 -- 손튜닝(실제 스트로크 진폭 ~140°보다 작게 그림)

type Vec3 = [number, number, number];

/** 두 점을 잇는 원기둥 분절(다리·털). */
function Segment({ a, b, r, color, rEnd }: { a: Vec3; b: Vec3; r: number; color: string; rEnd?: number }) {
  const { position, quaternion, length } = useMemo(() => {
    const va = new THREE.Vector3(...a);
    const vb = new THREE.Vector3(...b);
    const dir = vb.clone().sub(va);
    const len = dir.length();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    return { position: va.add(vb).multiplyScalar(0.5), quaternion: q, length: len };
  }, [a, b]);
  return (
    <mesh position={position} quaternion={quaternion} castShadow>
      <cylinderGeometry args={[rEnd ?? r, r, length, 7]} />
      <meshStandardMaterial color={color} roughness={0.5} />
    </mesh>
  );
}

const LEG_COLOR = "#6b4a26";
const TARSUS_COLOR = "#4a3219";

// 다리 국소 좌표: +x = 몸 바깥쪽, +y = 위. 부착점(0,0)에서 바닥(y=-STANCE_HEIGHT)까지.
const FEMUR_A: Vec3 = [0.02, 0, 0];
const FEMUR_B: Vec3 = [0.5, 0.16, 0];
const TIBIA_B: Vec3 = [0.9, -STANCE_HEIGHT + 0.06, 0];
const TARSUS_B: Vec3 = [1.28, -STANCE_HEIGHT + 0.01, 0];

function Leg() {
  return (
    <group>
      <mesh position={[0.02, 0, 0]}>
        <sphereGeometry args={[0.055, 8, 6]} />
        <meshStandardMaterial color={LEG_COLOR} roughness={0.5} />
      </mesh>
      <Segment a={FEMUR_A} b={FEMUR_B} r={0.045} rEnd={0.038} color={LEG_COLOR} />
      <Segment a={FEMUR_B} b={TIBIA_B} r={0.034} rEnd={0.028} color={LEG_COLOR} />
      <Segment a={TIBIA_B} b={TARSUS_B} r={0.022} rEnd={0.014} color={TARSUS_COLOR} />
    </group>
  );
}

interface LegSpec {
  attach: Vec3;
  side: 1 | -1;
  /** 앞쪽으로 기운 기본 각(rad) -- 앞다리 +, 뒷다리 -. */
  baseFwd: number;
  /** 삼각보행 조: 0 = (좌1, 우2, 좌3), 1 = (우1, 좌2, 우3). */
  tripod: 0 | 1;
}

const LEGS: LegSpec[] = [
  { attach: [0.42, STANCE_HEIGHT, -0.13], side: -1, baseFwd: 0.75, tripod: 0 },
  { attach: [0.42, STANCE_HEIGHT, 0.13], side: 1, baseFwd: 0.75, tripod: 1 },
  { attach: [0.2, STANCE_HEIGHT, -0.16], side: -1, baseFwd: 0.05, tripod: 1 },
  { attach: [0.2, STANCE_HEIGHT, 0.16], side: 1, baseFwd: 0.05, tripod: 0 },
  { attach: [-0.02, STANCE_HEIGHT, -0.14], side: -1, baseFwd: -0.7, tripod: 0 },
  { attach: [-0.02, STANCE_HEIGHT, 0.14], side: 1, baseFwd: -0.7, tripod: 1 },
];
const SWING_AMP = 0.32;
const LIFT_AMP = 0.42;

/** 흉부 등쪽의 굵은 강모(macrochaetae) 대략 배치. */
const BRISTLES: { a: Vec3; b: Vec3 }[] = [
  [0.45, 0.2],
  [0.3, 0.24],
  [0.12, 0.25],
  [-0.05, 0.22],
  [0.4, 0.07],
  [0.2, 0.08],
  [-0.12, 0.08],
].flatMap(([x, zOff]) =>
  ([1, -1] as const).map((s) => {
    const z = s * zOff;
    const y = 0.55 + 0.34 * Math.sqrt(Math.max(0, 1 - ((x - 0.2) / 0.5) ** 2 - (z / 0.38) ** 2));
    return { a: [x, y, z] as Vec3, b: [x - 0.2, y + 0.1, z * 1.25] as Vec3 };
  }),
);

function wingGeometry(): THREE.BufferGeometry {
  // 뿌리(0,0) -> 끝(2.05, 0). 앞가장자리는 거의 곧고 뒷가장자리는 둥글다.
  const shape = new THREE.Shape();
  shape.moveTo(0, 0.02);
  shape.bezierCurveTo(0.5, 0.2, 1.4, 0.36, 1.95, 0.22);
  shape.bezierCurveTo(2.12, 0.14, 2.12, -0.14, 1.9, -0.26);
  shape.bezierCurveTo(1.4, -0.46, 0.55, -0.4, 0.15, -0.12);
  shape.lineTo(0, 0.02);
  const geo = new THREE.ShapeGeometry(shape, 24);
  // 텍스처 좌표: u = 뿌리->끝, v = 앞가장자리(0) -> 뒷가장자리(1). makeWingTexture와 맞춤.
  const pos = geo.getAttribute("position");
  const uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {
    uv[i * 2] = pos.getX(i) / 2.1;
    uv[i * 2 + 1] = 1 - (pos.getY(i) + 0.46) / 0.84;
  }
  geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  return geo;
}

export function FlyModel({ kinematicsRef }: { kinematicsRef: MutableRefObject<OrganismKinematics> }) {
  const textures = useMemo(
    () => ({ abdomen: makeAbdomenTexture(), eye: makeCompoundEyeTexture(), wing: makeWingTexture() }),
    [],
  );
  useEffect(
    () => () => {
      textures.abdomen.dispose();
      textures.eye.dispose();
      textures.wing.dispose();
    },
    [textures],
  );
  const wingGeo = useMemo(() => wingGeometry(), []);
  const legRefs = useRef<(THREE.Group | null)[]>([]);
  const wingRefs = useRef<(THREE.Group | null)[]>([]);
  const bodyRef = useRef<THREE.Group>(null);
  const flightRef = useRef({ blend: 0, flap: 0 });

  useFrame((_, delta) => {
    const k = kinematicsRef.current;
    const f = flightRef.current;
    // 이륙/착지 자세 전환은 0.25초 정도에 걸쳐 부드럽게
    f.blend += ((k.airborne ? 1 : 0) - f.blend) * (1 - Math.exp(-delta * 10));
    f.flap += delta * 2 * Math.PI * WINGBEAT_DISPLAY_HZ;
    const fl = f.blend;
    const phase = (2 * Math.PI * k.travelledMm) / STRIDE_MM;
    LEGS.forEach((leg, i) => {
      const g = legRefs.current[i];
      if (!g) return;
      const ph = phase + (leg.tripod === 1 ? Math.PI : 0);
      // (0, π): 입각기(발이 바닥에서 뒤로), (π, 2π): 유각기(발을 들고 앞으로)
      const walkFwd = leg.baseFwd + SWING_AMP * Math.cos(ph);
      const walkLift = Math.max(0, -Math.sin(ph)) * LIFT_AMP;
      // 비행 중엔 다리를 뒤로 모아 아래로 늘어뜨린다
      const fwd = walkFwd * (1 - fl) + (leg.baseFwd * 0.35 - 0.55) * fl;
      const lift = walkLift * (1 - fl) - 0.55 * fl;
      g.rotation.set(0, 0, 0);
      g.rotation.y = -leg.side * (Math.PI / 2 - fwd);
      g.rotateZ(lift);
    });
    ([1, -1] as const).forEach((s, i) => {
      const w = wingRefs.current[i];
      if (!w) return;
      // 힌지 yaw: 접힘(π+0.2s, 복부 위로 뒤를 향함) <-> 펼침(π+s·π/2, 옆으로) + 앞뒤 날갯짓
      const stroke = Math.sin(f.flap) * WING_STROKE_RAD;
      const folded = Math.PI + 0.2 * s;
      const spread = Math.PI + s * (Math.PI / 2 + stroke);
      w.rotation.set(fl * s * 0.25 * Math.cos(f.flap), folded + (spread - folded) * fl, 0, "YXZ");
    });
    if (bodyRef.current) {
      // 걸을 땐 삼각보행 조가 바뀔 때마다 살짝 오르내림, 날 땐 고도만큼 떠 있다
      bodyRef.current.position.y = k.altitudeMm + 0.012 * Math.abs(Math.sin(phase)) * (1 - fl);
    }
  });

  return (
    <group ref={bodyRef}>
      {/* 흉부 */}
      <mesh position={[0.2, 0.55, 0]} scale={[0.5, 0.36, 0.37]} castShadow>
        <sphereGeometry args={[1, 32, 24]} />
        <meshPhysicalMaterial color="#9c6d37" roughness={0.45} clearcoat={0.4} clearcoatRoughness={0.4} />
      </mesh>
      {/* 소순판(scutellum) */}
      <mesh position={[-0.22, 0.8, 0]} scale={[0.16, 0.08, 0.15]}>
        <sphereGeometry args={[1, 16, 12]} />
        <meshPhysicalMaterial color="#a0733c" roughness={0.45} clearcoat={0.4} />
      </mesh>
      {BRISTLES.map((br, i) => (
        <Segment key={i} a={br.a} b={br.b} r={0.009} rEnd={0.003} color="#1b120a" />
      ))}

      {/* 머리 + 겹눈 + 더듬이 + 주둥이 */}
      <group position={[0.8, 0.6, 0]}>
        <mesh scale={[0.2, 0.25, 0.29]} castShadow>
          <sphereGeometry args={[1, 24, 18]} />
          <meshStandardMaterial color="#b3854a" roughness={0.55} />
        </mesh>
        {([1, -1] as const).map((s) => (
          <mesh key={s} position={[0.03, 0.02, s * 0.2]} scale={[0.17, 0.22, 0.13]} rotation={[0, s * -0.35, 0]}>
            <sphereGeometry args={[1, 32, 24]} />
            <meshPhysicalMaterial map={textures.eye} roughness={0.35} clearcoat={1} clearcoatRoughness={0.15} />
          </mesh>
        ))}
        {([1, -1] as const).map((s) => (
          <group key={`ant${s}`} position={[0.19, 0.08, s * 0.06]}>
            <mesh scale={[0.05, 0.07, 0.045]}>
              <sphereGeometry args={[1, 10, 8]} />
              <meshStandardMaterial color="#8a6334" roughness={0.6} />
            </mesh>
            <Segment a={[0.02, 0.03, 0]} b={[0.1, 0.17, s * 0.05]} r={0.006} rEnd={0.002} color="#3a2814" />
          </group>
        ))}
        <Segment a={[0.1, -0.16, 0]} b={[0.2, -0.3, 0]} r={0.035} rEnd={0.045} color="#8a6a42" />
        {/* 단안(ocelli) 삼각형 */}
        {[[0.02, 0.24, 0], [-0.03, 0.23, 0.04], [-0.03, 0.23, -0.04]].map((p, i) => (
          <mesh key={`oc${i}`} position={p as Vec3}>
            <sphereGeometry args={[0.018, 8, 6]} />
            <meshPhysicalMaterial color="#2a1a10" clearcoat={1} roughness={0.2} />
          </mesh>
        ))}
      </group>

      {/* 복부 -- 구의 극축을 몸 축(x)으로 눕혀 텍스처 v가 앞->뒤를 따르게 */}
      <mesh position={[-0.62, 0.5, 0]} rotation={[0, 0, -Math.PI / 2 + 0.12]} scale={[0.4, 0.78, 0.4]} castShadow>
        <sphereGeometry args={[1, 32, 32]} />
        <meshPhysicalMaterial map={textures.abdomen} roughness={0.42} clearcoat={0.5} clearcoatRoughness={0.35} />
      </mesh>

      {/* 평균곤(halteres) */}
      {([1, -1] as const).map((s) => (
        <group key={`hal${s}`}>
          <Segment a={[-0.12, 0.62, s * 0.3]} b={[-0.2, 0.62, s * 0.4]} r={0.01} color="#a58a5a" />
          <mesh position={[-0.21, 0.62, s * 0.42]}>
            <sphereGeometry args={[0.035, 10, 8]} />
            <meshStandardMaterial color="#d8c69a" roughness={0.5} />
          </mesh>
        </group>
      ))}

      {/* 날개 -- 걷는 동안은 복부 위에 겹쳐 접혀 있고, 날 때는 힌지에서 펼쳐 앞뒤로 친다 */}
      {([1, -1] as const).map((s, i) => (
        <group
          key={`wing${s}`}
          position={[0.02, 0.93, s * 0.1]}
          ref={(g) => {
            wingRefs.current[i] = g;
          }}
        >
          <mesh geometry={wingGeo} rotation={[-Math.PI / 2, 0, 0]} scale={[0.86, s * 0.9, 1]} renderOrder={3}>
            <meshPhysicalMaterial
              map={textures.wing}
              transparent
              depthWrite={false}
              side={THREE.DoubleSide}
              roughness={0.15}
              iridescence={0.9}
              iridescenceIOR={1.4}
              iridescenceThicknessRange={[250, 600]}
              opacity={0.95}
            />
          </mesh>
        </group>
      ))}

      {/* 다리 6개 */}
      {LEGS.map((leg, i) => (
        <group
          key={`leg${i}`}
          position={leg.attach}
          ref={(g) => {
            legRefs.current[i] = g;
          }}
        >
          <Leg />
        </group>
      ))}
    </group>
  );
}
