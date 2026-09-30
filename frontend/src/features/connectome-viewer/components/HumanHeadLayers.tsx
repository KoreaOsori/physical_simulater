"use client";

import { useMemo, useRef } from "react";
import { Html } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import type { Mesh, MeshStandardMaterial } from "three";
import * as THREE from "three";

import {
  diveExternalOpacity,
  diveNeuralOpacity,
  diveOrganOpacity,
} from "@/features/connectome-viewer/lib/dive-reveal";
import type { AnatomyMeshLayer, HeadAnatomy } from "@/types/human";

function useLayerGeometry(layer: AnatomyMeshLayer) {
  return useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(layer.positions, 3));
    geometry.setIndex(layer.indices);
    geometry.computeVertexNormals();
    return geometry;
  }, [layer]);
}

/** This layer's own closest real surface point to the scene origin (world
 * origin == OrbitControls target == [0,0,0], see HumanMacroCanvas) — the
 * minimum, not the bounding-sphere radius, so it's a true "the camera is
 * guaranteed to be outside this mesh at every angle past this distance"
 * bound (docs/27's perf profile measured this: skin=1.581, brain=0.777,
 * gray_matter=0.079 scene units, computed the same way from the live API
 * response). Cheap (one pass over the vertex array), done once per layer
 * via useMemo, not per frame. */
function useLayerMinRadius(layer: AnatomyMeshLayer): number {
  return useMemo(() => {
    let min = Infinity;
    const p = layer.positions;
    for (let i = 0; i < p.length; i += 3) {
      const r = Math.hypot(p[i], p[i + 1], p[i + 2]);
      if (r < min) min = r;
    }
    return min;
  }, [layer]);
}

interface LayerMeshProps {
  layer: AnatomyMeshLayer;
  color: string;
  opacity: number;
  emissive?: string;
  emissiveIntensity?: number;
}

/** One real MNI-template isosurface layer — see HumanHeadLayers's docstring
 * for why these are genuine marching-cubes geometry, not primitives like
 * FlyExternalAnatomy's stand-ins. `depthWrite={false}` while translucent so
 * an outer layer never occludes the inner layers fading in underneath it
 * (same trick as FlyOrganShell's shell sphere).
 *
 * `side` is set imperatively every frame (not a fixed prop) based on the
 * camera's actual distance from the origin vs. this layer's own
 * `minRadius` (see useLayerMinRadius) — `THREE.FrontSide` whenever the
 * camera is provably still outside the mesh (cheaper: no backface
 * shading/blending), falling back to `THREE.DoubleSide` the moment the
 * camera could plausibly be inside it (e.g. OrbitControls' minDistance=1
 * lets the camera get closer to the origin than the skin mesh's own
 * minRadius=1.581 — see docs/27-rendering-performance-profile.md's "이번
 * 세션에서 고치지 않기로 한 이유", which this supersedes: the earlier pass
 * measured the cost and identified DoubleSide+transparent overdraw as the
 * cause but deferred a fix pending a way to verify it's safe when the
 * camera zooms in; this makes it safe by construction instead of needing
 * an eyeballed check). A small margin (0.97x) avoids switching exactly at
 * the boundary every frame from floating-point/orbit jitter. */
function LayerMesh({ layer, color, opacity, emissive, emissiveIntensity }: LayerMeshProps) {
  const geometry = useLayerGeometry(layer);
  const minRadius = useLayerMinRadius(layer);
  const materialRef = useRef<MeshStandardMaterial>(null);
  const meshRef = useRef<Mesh>(null);
  const camera = useThree((s) => s.camera);

  useFrame(() => {
    const material = materialRef.current;
    if (!material) return;
    const cameraDistance = camera.position.length(); // world origin == this mesh's local origin
    material.side = cameraDistance > minRadius * 0.97 ? THREE.FrontSide : THREE.DoubleSide;
  });

  if (opacity <= 0.02) return null;
  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        ref={materialRef}
        color={color}
        emissive={emissive}
        emissiveIntensity={emissiveIntensity ?? 0}
        transparent
        opacity={opacity}
        depthWrite={opacity >= 0.95 ? true : false}
        side={THREE.DoubleSide}
        roughness={0.55}
      />
    </mesh>
  );
}

interface HumanHeadLayersProps {
  anatomy: HeadAnatomy;
  progress: number;
  /** Whether to show the "H01 샘플 인접 부위" hint marker (only meaningful
   * once the viewer can see through to roughly where it'd sit). */
  showH01Hint: boolean;
  /** The micro page substitutes the real H01 point cloud for this final
   * stage instead (see HumanMicroCanvas) — rendering the gray-matter
   * isosurface there too would wrongly imply it's registered to that one
   * specific sample, which it isn't (H01 has no MNI registration). */
  showGrayMatter?: boolean;
}

/**
 * The human dive-in reveal's three stages, all real MNI152NLin2009cAsym
 * template isosurfaces (see backend/app/data/sources/human/SOURCES.md's
 * "두개골/뇌 표면 메시" section) sharing the exact same coordinate frame as
 * the macro connectome's region dots:
 *
 *   겉모습 (skin, T1w threshold) → 뇌 조직 (brain mask envelope) →
 *   신경계 (gray-matter isosurface — where cortical neuron cell bodies sit)
 *
 * Unlike FlyExternalAnatomy/FlyOrganShell (stylized primitives, no real
 * Drosophila scan available), every layer here is a genuine isosurface over
 * registered voxel data — the honest tradeoff is a population-average
 * template rather than one specific measured skull.
 */
export function HumanHeadLayers({ anatomy, progress, showH01Hint, showGrayMatter = true }: HumanHeadLayersProps) {
  const skinOpacity = diveExternalOpacity(progress);
  const brainOpacity = diveOrganOpacity(progress);
  const grayMatterOpacity = diveNeuralOpacity(progress);
  const hint = anatomy.h01_region_hint;

  return (
    <group>
      <LayerMesh layer={anatomy.skin} color="#e0b48c" opacity={skinOpacity * 0.9} />
      <LayerMesh layer={anatomy.brain} color="#d9a5b0" opacity={brainOpacity * 0.55} />
      {showGrayMatter && (
        <LayerMesh
          layer={anatomy.gray_matter}
          color="#ff6b81"
          emissive="#ff6b81"
          emissiveIntensity={0.4}
          opacity={Math.min(grayMatterOpacity, 0.7)}
        />
      )}
      {showH01Hint && grayMatterOpacity > 0.3 && (
        <group position={[hint.x, hint.y, hint.z]}>
          <mesh>
            <sphereGeometry args={[0.05, 12, 12]} />
            <meshStandardMaterial color="#ffe066" emissive="#ffe066" emissiveIntensity={1.2} toneMapped={false} />
          </mesh>
          <Html distanceFactor={9} zIndexRange={[50, 0]} style={{ pointerEvents: "none" }} center>
            <div className="anatomy-region-label" style={{ opacity: grayMatterOpacity }}>
              <strong>H01 미시 샘플 인접 부위</strong>
              <em>측두극(TempPole) 실제 MNI 위치 · H01 자체는 MNI 비정렬</em>
            </div>
          </Html>
        </group>
      )}
    </group>
  );
}
