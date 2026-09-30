"use client";

import { Html } from "@react-three/drei";

import type { FlyDiveOrganKind } from "@/features/connectome-viewer/lib/fly-dive-stages";

interface FlyExternalAnatomyProps {
  organKind: FlyDiveOrganKind;
  organLabel: string;
  opacity: number;
}

/** Stylized external-anatomy meshes for the "dive-in" reveal's first stage
 * (겉모습) — see fly-dive-stages.ts's module docstring: this project has no
 * real 3D scan of Drosophila external anatomy, so these are illustrative
 * primitive-geometry approximations (proportions/segment counts from general
 * Drosophila external morphology, not measured), not hemibrain data. */
export function FlyExternalAnatomy({ organKind, organLabel, opacity }: FlyExternalAnatomyProps) {
  if (opacity <= 0.02) return null;

  return (
    <group>
      {organKind === "antenna" ? (
        <>
          <Antenna mirror={1} opacity={opacity} />
          <Antenna mirror={-1} opacity={opacity} />
        </>
      ) : (
        <>
          <CompoundEye mirror={1} opacity={opacity} />
          <CompoundEye mirror={-1} opacity={opacity} />
        </>
      )}
      {opacity > 0.5 && (
        <Html position={[-3.4, -1.1, 0]} distanceFactor={9} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }} center>
          <div className="anatomy-region-label" style={{ opacity }}>
            <strong>{organLabel}</strong>
            <em>실제 형태 아님 · 도식적 표현</em>
          </div>
        </Html>
      )}
    </group>
  );
}

const CUTICLE_COLOR = "#c9a35a";
// Individual segment coordinates below were authored at "life size" (real
// antenna proportions are only ~0.1 units); scaled up here so the whole
// antenna reads as a clear shape at the same camera framing the neuron
// cluster uses, rather than a barely-visible speck.
const ANTENNA_SCALE = 7;

/** Three tapering segments (scape/pedicel/funiculus) curving up and
 * forward, plus a thin backward-sweeping arista — the recognizable silhouette
 * of a Drosophila antenna, built from primitive geometry. Each mesh gets its
 * own <meshStandardMaterial> (not a single shared JSX element reused across
 * meshes) since sharing one material descriptor across many mesh parents is
 * fragile in R3F's reconciler. */
function Antenna({ mirror, opacity }: { mirror: 1 | -1; opacity: number }) {
  const baseX = -3.4;
  const baseZ = mirror * 0.5;

  return (
    <group position={[baseX, -0.3, baseZ]} rotation={[0, 0, mirror * -0.3]} scale={[ANTENNA_SCALE, ANTENNA_SCALE, ANTENNA_SCALE]}>
      {/* scape */}
      <mesh position={[0, 0, 0]}>
        <capsuleGeometry args={[0.09, 0.12, 4, 8]} />
        <meshStandardMaterial color={CUTICLE_COLOR} transparent opacity={opacity} roughness={0.6} />
      </mesh>
      {/* pedicel */}
      <mesh position={[0.05, 0.22, 0]} rotation={[0, 0, mirror * -0.25]}>
        <capsuleGeometry args={[0.08, 0.1, 4, 8]} />
        <meshStandardMaterial color={CUTICLE_COLOR} transparent opacity={opacity} roughness={0.6} />
      </mesh>
      {/* funiculus (bulb) */}
      <mesh position={[0.13, 0.4, 0]}>
        <sphereGeometry args={[0.13, 10, 8]} />
        <meshStandardMaterial color={CUTICLE_COLOR} transparent opacity={opacity} roughness={0.6} />
      </mesh>
      {/* arista, a gentle backward arc made of 5 tapering segments */}
      {[0, 1, 2, 3, 4].map((i) => {
        const t = i / 4;
        const angle = -0.4 - t * 1.5;
        const r = 0.35;
        const x = 0.13 + Math.sin(angle) * r * 0.4;
        const y = 0.4 + (1 - Math.cos(angle)) * r;
        return (
          <mesh key={i} position={[x, y, 0]} rotation={[0, 0, mirror * angle]}>
            <cylinderGeometry args={[0.02 * (1 - t * 0.6), 0.025 * (1 - t * 0.5), 0.18, 6]} />
            <meshStandardMaterial color={CUTICLE_COLOR} transparent opacity={opacity} roughness={0.6} />
          </mesh>
        );
      })}
    </group>
  );
}

const EYE_COLOR = "#7a2233";

/** A flat-shaded faceted sphere (icosahedron subdivision) — each triangle
 * face catching light distinctly, a lightweight stand-in for compound-eye
 * ommatidia texture without a real per-facet model. */
function CompoundEye({ mirror, opacity }: { mirror: 1 | -1; opacity: number }) {
  return (
    <group position={[-2.2, 0.2, mirror * 2.6]}>
      <mesh scale={[1, 1, 0.85]}>
        <icosahedronGeometry args={[1.3, 3]} />
        <meshStandardMaterial
          color={EYE_COLOR}
          flatShading
          transparent
          opacity={opacity}
          roughness={0.35}
          metalness={0.1}
        />
      </mesh>
    </group>
  );
}
