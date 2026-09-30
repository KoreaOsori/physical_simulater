"use client";

import { useState } from "react";
import { Html } from "@react-three/drei";

import {
  MAX_BODY_RADIUS,
  apFraction,
  bendOffsetZ,
  bodyCenterX,
  bodyRadiusProfile,
  type ApExtent,
  type BodyLandmarks as BodyLandmarksData,
} from "@/features/connectome-viewer/lib/body-pose";

interface LandmarkDef {
  key: string;
  label: string;
  description: string;
  x: number;
  ventral: boolean;
}

/**
 * The worm's three body openings — mouth, vulva, anus — placed at their real
 * anatomical anterior-posterior position (derived from real neuron landmarks,
 * see body-pose.ts's computeBodyLandmarks) and rendered as small dark
 * markers on the body surface, each with a hover tooltip explaining what it
 * does.
 */
export function BodyLandmarks({
  extent,
  landmarks,
  opacity,
}: {
  extent: ApExtent;
  landmarks: BodyLandmarksData;
  opacity: number;
}) {
  if (opacity <= 0.05) return null;

  const defs: LandmarkDef[] = [
    {
      key: "mouth",
      label: "입",
      description: "먹이를 먹는 것을 담당합니다. 입 → 인두 → 장으로 이어지는 소화관의 시작점입니다.",
      x: landmarks.mouthX,
      ventral: false,
    },
    {
      key: "vulva",
      label: "배 (생식공)",
      description:
        "자웅동체 개체에서 정자와 난자가 수정되어 알을 낳는 것을 담당합니다. HSN 뉴런이 이 부위 근육의 수축을 유도합니다.",
      x: landmarks.vulvaX,
      ventral: true,
    },
    {
      key: "anus",
      label: "항문",
      description: "배설을 담당합니다. AVL · DVB 뉴런이 이 부위 근육의 수축 리듬을 조절합니다.",
      x: landmarks.anusX,
      ventral: true,
    },
  ];

  return (
    <group>
      {defs.map((def) => (
        <LandmarkMarker key={def.key} def={def} extent={extent} opacity={opacity} />
      ))}
    </group>
  );
}

function LandmarkMarker({ def, extent, opacity }: { def: LandmarkDef; extent: ApExtent; opacity: number }) {
  const [hovered, setHovered] = useState(false);
  const t = apFraction(def.x, extent);
  const radius = MAX_BODY_RADIUS * bodyRadiusProfile(t);
  const zCenter = bendOffsetZ(t);
  const y = def.ventral ? -radius * 0.95 : 0;
  const z = def.ventral ? zCenter : zCenter;
  const x = def.x - bodyCenterX(extent); // body-center-relative — see body-pose.ts's bendPosition

  return (
    <mesh
      position={[x, y, z]}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={(e) => {
        e.stopPropagation();
        setHovered(false);
      }}
    >
      <sphereGeometry args={[0.055, 10, 10]} />
      <meshStandardMaterial
        color="#3a2a22"
        emissive={hovered ? "#c77a4a" : "#7a4a35"}
        emissiveIntensity={hovered ? 1.3 : 0.5}
        transparent
        opacity={opacity}
      />
      {hovered && (
        <Html distanceFactor={5} zIndexRange={[60, 0]} style={{ pointerEvents: "none" }} center>
          <div className="neuron-tooltip">
            <strong>{def.label}</strong>
            <p>{def.description}</p>
          </div>
        </Html>
      )}
    </mesh>
  );
}
