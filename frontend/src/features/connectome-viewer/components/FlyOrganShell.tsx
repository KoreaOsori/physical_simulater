"use client";

import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { Points } from "three";
import * as THREE from "three";

interface FlyOrganShellProps {
  organNeuropilLabel: string;
  flowLabel: string;
  opacity: number;
}

const PARTICLE_COUNT = 60;
const FLOW_LENGTH = 7; // matches roughly the ORN/VPN stage-x span (-3.4 to ~0)
const FLOW_START_X = -4.2;

/** The "감각기관 내부" transitional stage between the external organ and the
 * neural network: a soft translucent shell (not a real measured organ
 * boundary — just a visual container for the transition) plus particles
 * drifting inward along the flow axis, standing in for air (olfactory) or
 * light (visual) entering. Purely illustrative, same honesty note as
 * FlyExternalAnatomy. */
export function FlyOrganShell({ organNeuropilLabel, flowLabel, opacity }: FlyOrganShellProps) {
  const pointsRef = useRef<Points>(null);

  // useState's initializer (unlike useMemo's factory) is guaranteed by React
  // to run exactly once per mount, so it's the correct place for a one-time
  // impure (Math.random) computation -- see react-hooks/purity.
  const [positions] = useState(() => {
    const arr = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      arr[i * 3] = FLOW_START_X + Math.random() * FLOW_LENGTH;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 1.4;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 1.4;
    }
    return arr;
  });

  useFrame((_state, delta) => {
    if (!pointsRef.current || opacity <= 0.02) return;
    const attr = pointsRef.current.geometry.getAttribute("position") as THREE.BufferAttribute;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      let x = attr.getX(i) + delta * 1.6;
      if (x > FLOW_START_X + FLOW_LENGTH) x = FLOW_START_X;
      attr.setX(i, x);
    }
    attr.needsUpdate = true;
  });

  if (opacity <= 0.02) return null;

  return (
    <group>
      <mesh position={[-1.5, 0, 0]} scale={[3.2, 1.3, 1.3]}>
        <sphereGeometry args={[1, 20, 16]} />
        <meshBasicMaterial color="#baff71" transparent opacity={0.06 * opacity} depthWrite={false} />
      </mesh>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial color="#e8ffcf" size={0.045} transparent opacity={opacity * 0.8} depthWrite={false} />
      </points>
      {opacity > 0.5 && (
        <Html position={[-1.5, 1.6, 0]} distanceFactor={9} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }} center>
          <div className="anatomy-region-label" style={{ opacity }}>
            <strong>{organNeuropilLabel} 진입부</strong>
            <em>{flowLabel}이(가) 신경계로 들어가는 경로 · 도식적 표현</em>
          </div>
        </Html>
      )}
    </group>
  );
}
