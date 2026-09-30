"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh } from "three";

import type { Effector, EffectorType, Position3D } from "@/types/connectome";

const KIND_COLOR: Record<EffectorType, string> = {
  muscle: "#e0715c",
  gut: "#e8c86d",
  epidermis: "#8fa8ff",
  other: "#888888",
};

interface EffectorNodeProps {
  effector: Effector;
  position: Position3D;
  active: boolean;
  opacity: number;
}

/** Muscle/gut/epidermis synapse targets — same idea as NeuronNode but a
 * smaller box shape so the two node kinds stay visually distinct at a glance. */
export function EffectorNode({ effector, position, active, opacity }: EffectorNodeProps) {
  const meshRef = useRef<Mesh>(null);
  const color = KIND_COLOR[effector.kind];

  useFrame((state) => {
    if (!meshRef.current) return;
    const pulse = active ? 1 + Math.sin(state.clock.elapsedTime * 8) * 0.25 : 1;
    meshRef.current.scale.setScalar(pulse);
  });

  if (opacity <= 0) return null;

  return (
    <mesh ref={meshRef} position={[position.x, position.y, position.z]}>
      <boxGeometry args={[0.09, 0.09, 0.09]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={active ? 1.4 : 0.25}
        transparent
        opacity={opacity}
        toneMapped={false}
      />
    </mesh>
  );
}
