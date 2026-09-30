"use client";

import { useMemo } from "react";
import { Html } from "@react-three/drei";

import { regionFor } from "@/features/connectome-viewer/lib/fly-anatomy-regions";
import type { Neuron, Position3D } from "@/types/connectome";

interface FlyAnatomyRegionsProps {
  neurons: Neuron[];
  positions: Map<string, Position3D>;
  visible: boolean;
  /** 0-1, defaults to 1 — multiplies region opacity, driven by the
   * olfactory/visual dive slider (FlyDiveSlider) so these fade in together
   * with the neural network rather than popping in abruptly. */
  opacity?: number;
}

interface RegionBounds {
  categoryKo: string;
  center: Position3D;
  radius: number;
}

/** Groups neurons by their real `categories_ko[0]` circuit-class tag and
 * draws a soft translucent sphere + label around each group's actual
 * rendered positions — see fly-anatomy-regions.ts for why this is presented
 * as a real-neuropil-name overlay rather than fabricated geometry. */
export function FlyAnatomyRegions({ neurons, positions, visible, opacity = 1 }: FlyAnatomyRegionsProps) {
  const bounds = useMemo<RegionBounds[]>(() => {
    const groups = new Map<string, Position3D[]>();
    for (const n of neurons) {
      const key = n.categories_ko[0];
      const pos = positions.get(n.id);
      if (!key || !pos) continue;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(pos);
    }

    const out: RegionBounds[] = [];
    for (const [categoryKo, pts] of groups) {
      if (pts.length < 2) continue;
      const center = {
        x: pts.reduce((s, p) => s + p.x, 0) / pts.length,
        y: pts.reduce((s, p) => s + p.y, 0) / pts.length,
        z: pts.reduce((s, p) => s + p.z, 0) / pts.length,
      };
      const radius = Math.max(
        ...pts.map((p) => Math.hypot(p.x - center.x, p.y - center.y, p.z - center.z)),
      );
      out.push({ categoryKo, center, radius: radius + 0.25 });
    }
    return out;
  }, [neurons, positions]);

  if (!visible || opacity <= 0.02) return null;

  return (
    <group>
      {bounds.map(({ categoryKo, center, radius }) => {
        const region = regionFor(categoryKo);
        if (!region) return null;
        return (
          <group key={categoryKo} position={[center.x, center.y, center.z]}>
            <mesh>
              <sphereGeometry args={[radius, 20, 20]} />
              <meshBasicMaterial color={region.color} transparent opacity={0.05 * opacity} depthWrite={false} />
            </mesh>
            <mesh>
              <sphereGeometry args={[radius, 20, 20]} />
              <meshBasicMaterial color={region.color} wireframe transparent opacity={0.18 * opacity} depthWrite={false} />
            </mesh>
            {opacity > 0.5 && (
              <Html distanceFactor={9} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }} center>
                <div className="anatomy-region-label" style={{ opacity }}>
                  <strong>{region.label}</strong>
                  <em>{region.neuropil}</em>
                </div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}
