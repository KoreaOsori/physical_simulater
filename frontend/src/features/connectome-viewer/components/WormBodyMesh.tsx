"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import type { BodySpine } from "@/features/connectome-viewer/lib/body-physics";
import { MAX_BODY_RADIUS, bodyRadiusProfile, type ApExtent, type BodyLandmarks } from "@/features/connectome-viewer/lib/body-pose";
import { computeMovementForcing } from "@/features/connectome-viewer/lib/movement-pose";
import { SEGMENTS_ALONG, MASS_COUNT } from "@/features/connectome-viewer/lib/use-worm-locomotion";
import { useSimulationStore } from "@/store/simulation-store";

const RADIAL_SEGMENTS = 14;

function buildIndices(): number[] {
  const indices: number[] = [];
  for (let i = 0; i < SEGMENTS_ALONG; i++) {
    for (let j = 0; j < RADIAL_SEGMENTS; j++) {
      const a = i * RADIAL_SEGMENTS + j;
      const b = i * RADIAL_SEGMENTS + ((j + 1) % RADIAL_SEGMENTS);
      const c = (i + 1) * RADIAL_SEGMENTS + j;
      const d = (i + 1) * RADIAL_SEGMENTS + ((j + 1) % RADIAL_SEGMENTS);
      indices.push(a, c, b, b, c, d);
    }
  }
  return indices;
}

interface WormBodyMeshProps {
  extent: ApExtent;
  opacity: number;
  landmarks: BodyLandmarks;
  /** Owned by use-worm-locomotion.ts (a parent's useFrame steps it, and also
   * runs the RFT locomotion solve from the same state) — this component only
   * reads the resulting shape, it doesn't step the physics itself anymore. */
  spine: BodySpine;
}

/**
 * The worm's outer cuticle/hypodermis surface: a tapered tube following the
 * body's anterior-posterior extent, whose lateral bend is driven by a real
 * damped mass-spring simulation (body-physics.ts) rather than a scripted
 * curve — muscle activation and locomotion commands push on the spine as
 * forces, and how far/how the body actually bends is that simulation's
 * output. Radius (girth) bumps for feed/defecate/reproduce/stop are still
 * direct geometry modulation (a different, un-simulated degree of freedom).
 * Purely a rendered envelope, not a real segmented mesh — see SOURCES.md.
 */
export function WormBodyMesh({ extent, opacity, landmarks, spine }: WormBodyMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const vertexCount = MASS_COUNT * RADIAL_SEGMENTS;
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(vertexCount * 3), 3));
    geo.setIndex(buildIndices());
    return geo;
  }, []);

  const landmarkT = useMemo(
    () => ({
      mouth: 0,
      vulva: (landmarks.vulvaX - extent.min) / (extent.max - extent.min || 1),
      anus: (landmarks.anusX - extent.min) / (extent.max - extent.min || 1),
    }),
    [landmarks, extent],
  );

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh || opacity <= 0.01) return;
    const now = performance.now();
    const { movementPulse } = useSimulationStore.getState();

    // Only radiusBumps are read here — lateralForces were already applied to
    // this same `spine` instance and stepped by use-worm-locomotion.ts's
    // useFrame (which runs first, see that module's docstring). Calling
    // computeMovementForcing again is cheap/pure; not worth threading the
    // result through a ref just to avoid one extra call.
    const movement = computeMovementForcing(movementPulse, now, landmarkT);

    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const span = extent.max - extent.min || 1;

    for (let i = 0; i < MASS_COUNT; i++) {
      const t = i / SEGMENTS_ALONG;
      // Body-center-relative (see body-pose.ts's bodyCenterX) — matches
      // use-worm-locomotion.ts's localX so the RFT solve sees the same shape
      // that's actually rendered, and composes correctly with the rigid
      // <group> transform applied around this same center in ConnectomeCanvas.
      const x = t * span - span / 2;

      let radius = MAX_BODY_RADIUS * bodyRadiusProfile(t);
      for (const bump of movement.radiusBumps) {
        const d = (t - bump.t) / bump.width;
        radius += bump.amount * MAX_BODY_RADIUS * Math.exp(-d * d);
      }
      radius = Math.max(radius, 0.01);

      const zCenter = spine.offsetAt(i);

      for (let j = 0; j < RADIAL_SEGMENTS; j++) {
        const theta = (j / RADIAL_SEGMENTS) * Math.PI * 2;
        const y = Math.sin(theta) * radius;
        const z = zCenter + Math.cos(theta) * radius;
        posAttr.setXYZ(i * RADIAL_SEGMENTS + j, x, y, z);
      }
    }

    posAttr.needsUpdate = true;
    geometry.computeVertexNormals();
  });

  if (opacity <= 0.01) return null;

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        color="#dff2c8"
        transparent
        opacity={opacity}
        side={THREE.DoubleSide}
        roughness={0.55}
        metalness={0}
        depthWrite={opacity > 0.5}
      />
    </mesh>
  );
}
