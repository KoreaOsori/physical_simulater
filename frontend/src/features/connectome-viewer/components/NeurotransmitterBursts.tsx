"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, MeshBasicMaterial, MeshStandardMaterial } from "three";

import { type Burst, useSimulationStore } from "@/store/simulation-store";
import type { Neurotransmitter, Position3D } from "@/types/connectome";

const NT_COLOR: Record<Neurotransmitter, string> = {
  acetylcholine: "#8fdff1",
  gaba: "#ff8f8f",
  glutamate: "#c2a6ff",
  dopamine: "#ffb86b",
  serotonin: "#ff9ecf",
  octopamine: "#ffe27a",
  tyramine: "#b7ff8f",
  electrical: "#e6ff9e",
  unknown: "#cfd8cf",
};

const TRAVEL_MS = 500;
const RELEASE_MS = 500;
const TOTAL_MS = TRAVEL_MS + RELEASE_MS;

interface Segment {
  key: string;
  from: Position3D | null;
  to: Position3D;
  color: string;
  startedAt: number;
}

/** One neurotransmitter release: a particle travels pre -> post over
 * TRAVEL_MS (skipped if there's no source, e.g. a muscle-stage event), then
 * an expanding, fading cloud represents diffusion into the synaptic cleft. */
function BurstParticle({ segment }: { segment: Segment }) {
  const particleRef = useRef<Mesh>(null);
  const cloudRef = useRef<Mesh>(null);

  useFrame(() => {
    const elapsed = performance.now() - segment.startedAt;
    const travelT = Math.min(1, elapsed / TRAVEL_MS);

    if (particleRef.current && segment.from) {
      particleRef.current.position.set(
        segment.from.x + (segment.to.x - segment.from.x) * travelT,
        segment.from.y + (segment.to.y - segment.from.y) * travelT,
        segment.from.z + (segment.to.z - segment.from.z) * travelT,
      );
      const mat = particleRef.current.material as MeshStandardMaterial;
      mat.opacity = travelT < 1 ? 1 : Math.max(0, 1 - (elapsed - TRAVEL_MS) / RELEASE_MS);
      particleRef.current.visible = mat.opacity > 0.02;
    }

    if (cloudRef.current) {
      const releaseT = Math.max(0, Math.min(1, (elapsed - TRAVEL_MS) / RELEASE_MS));
      cloudRef.current.scale.setScalar(0.4 + releaseT * 2.4);
      const mat = cloudRef.current.material as MeshBasicMaterial;
      mat.opacity = elapsed < TRAVEL_MS ? 0 : Math.max(0, 0.5 * (1 - releaseT));
      cloudRef.current.visible = mat.opacity > 0.01;
    }
  });

  return (
    <group>
      {segment.from && (
        <mesh ref={particleRef} position={[segment.from.x, segment.from.y, segment.from.z]}>
          <sphereGeometry args={[0.045, 6, 6]} />
          <meshStandardMaterial
            color={segment.color}
            emissive={segment.color}
            emissiveIntensity={1.6}
            transparent
            toneMapped={false}
          />
        </mesh>
      )}
      <mesh ref={cloudRef} position={[segment.to.x, segment.to.y, segment.to.z]} visible={false}>
        <sphereGeometry args={[0.1, 8, 8]} />
        <meshBasicMaterial color={segment.color} transparent opacity={0} toneMapped={false} />
      </mesh>
    </group>
  );
}

function burstsToSegments(bursts: Burst[], positions: Map<string, Position3D>): Segment[] {
  const out: Segment[] = [];
  for (const burst of bursts) {
    const from = burst.sourceId ? (positions.get(burst.sourceId) ?? null) : null;
    const color = NT_COLOR[burst.neurotransmitter];
    for (const targetId of burst.targetIds) {
      const to = positions.get(targetId);
      if (!to) continue;
      out.push({ key: `${burst.id}-${targetId}`, from, to, color, startedAt: burst.startedAt });
    }
  }
  return out;
}

/** Renders every in-flight neurotransmitter release as a small traveling
 * particle + arrival cloud. Part of the "nervous system" layer — gated by
 * the same opacity as neurons/synapses in the anatomy-layer toggle. */
export function NeurotransmitterBursts({
  positions,
  opacity,
}: {
  positions: Map<string, Position3D>;
  opacity: number;
}) {
  const bursts = useSimulationStore((s) => s.bursts);
  const pruneExpiredBursts = useSimulationStore((s) => s.pruneExpiredBursts);

  useFrame(() => {
    pruneExpiredBursts(TOTAL_MS + 200);
  });

  const segments = useMemo(() => burstsToSegments(bursts, positions), [bursts, positions]);

  if (opacity <= 0.02 || segments.length === 0) return null;

  return (
    <group>
      {segments.map((segment) => (
        <BurstParticle key={segment.key} segment={segment} />
      ))}
    </group>
  );
}
