"use client";

import { useMemo, useRef, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect } from "react";
import type { Mesh } from "three";

import { diveNeuralOpacity } from "@/features/connectome-viewer/lib/dive-reveal";
import { HumanHeadLayers } from "@/features/connectome-viewer/components/HumanHeadLayers";
import type { BrainRegion, MacroConnectome } from "@/types/human";

/** Same first-frame timing fix as FlyConnectomeCanvas's CanvasReadyKick. */
function CanvasReadyKick() {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const raf = requestAnimationFrame(() => invalidate());
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event("resize"));
      invalidate();
    }, 80);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [invalidate]);
  return null;
}

const REGION_COLOR = "#75cce9";
export const DISORDER_HIGHLIGHT_COLOR = "#ff3b3b";

/** What KIND a region's override color means -- not just a different color,
 * a different classification axis (see docs/30's "네트워크 vs 해부학"
 * section): "disorder" is a citation on top of the same network-based point
 * cloud (still a network's region, just flagged), while "lobe" is a
 * genuinely different partition of the brain (AAL's 4 classical lobes, not
 * Yeo-7 networks). Kept for the legend/callers, but marker SHAPE no longer
 * comes straight from this -- see `isLobeMember` below (docs/33: a region
 * can be BOTH the selected disorder's AND the active lobe's at once, and
 * both facts need to stay visible, not have one silently clobber the
 * other). */
export type RegionOverrideKind = "disorder" | "lobe";

export interface RegionOverride {
  color: string;
  kind: RegionOverrideKind;
  /** Whether this region is ALSO a member of the currently active lobe,
   * independent of which color won (disorder color always takes priority
   * over the passive lobe backdrop when both apply -- see
   * HumanMacroPage.tsx's additiveRegionColors) -- drives the octahedron
   * marker shape so a disorder-cited region that's also in the active lobe
   * shows red AND facet-cut, instead of losing the disorder highlight
   * entirely to the lobe's flat color (real bug: previously had to switch
   * to network mode to see a just-clicked disorder's highlight at all). */
  isLobeMember: boolean;
}

function RegionNode({ region, opacity, override }: { region: BrainRegion; opacity: number; override: RegionOverride | null }) {
  const meshRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  if (opacity <= 0.02) return null;

  const emphasized = override !== null;
  const color = override?.color ?? REGION_COLOR;
  const isLobe = override?.isLobeMember ?? false;

  return (
    <mesh
      ref={meshRef}
      position={[region.position.x, region.position.y, region.position.z]}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={(e) => {
        e.stopPropagation();
        setHovered(false);
      }}
      scale={hovered ? 1.8 : emphasized ? 1.4 : 1}
    >
      {isLobe ? <octahedronGeometry args={[0.1, 0]} /> : <sphereGeometry args={[0.08, 10, 10]} />}
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={hovered ? 1.4 : emphasized ? 1.1 : 0.5}
        transparent
        opacity={opacity}
        toneMapped={false}
      />
      {hovered && (
        <Html distanceFactor={9} zIndexRange={[60, 0]} style={{ pointerEvents: "none" }} center>
          <div className="neuron-tooltip">
            <strong>{region.name}</strong>
            <p className="neuron-tooltip-meta">Yeo-7 네트워크: {region.network}</p>
            <p className="neuron-tooltip-meta">
              실제 MNI 좌표(mm): ({region.mni_coordinate_mm.x.toFixed(0)}, {region.mni_coordinate_mm.y.toFixed(0)}, {region.mni_coordinate_mm.z.toFixed(0)})
            </p>
            {region.anatomical_label ? (
              <>
                <p className="neuron-tooltip-meta">
                  실제 위치(AAL 좌표 조회): {region.anatomical_label}
                </p>
                {region.anatomical_note && <p className="neuron-tooltip-curated">{region.anatomical_note}</p>}
              </>
            ) : (
              <p className="neuron-tooltip-degree">해부학적 라벨 미확인(주변에 조회 가능한 조직 없음)</p>
            )}
          </div>
        </Html>
      )}
    </mesh>
  );
}

function RegionEdges({ connectome, opacity }: { connectome: MacroConnectome; opacity: number }) {
  const { vertices } = useMemo(() => {
    const byId = new Map(connectome.regions.map((r) => [r.id, r.position]));
    const verts: number[] = [];
    for (const e of connectome.edges) {
      const a = byId.get(e.a);
      const b = byId.get(e.b);
      if (!a || !b) continue;
      verts.push(a.x, a.y, a.z, b.x, b.y, b.z);
    }
    return { vertices: new Float32Array(verts) };
  }, [connectome]);

  if (opacity <= 0.02) return null;
  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[vertices, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color="#9fe27a" transparent opacity={0.25 * opacity} />
    </lineSegments>
  );
}

interface HumanMacroCanvasProps {
  connectome: MacroConnectome | null;
  activeNetwork: string;
  /** 0 (겉모습) → 1 (신경계), see dive-reveal.ts. */
  diveProgress: number;
  /** region id -> {color, kind}, for every region that should render in
   * something OTHER than the default blue sphere, regardless of
   * `activeNetwork` (a disorder's or a lobe's regions can span networks the
   * current toggle doesn't show — e.g. Fusiform appears in both Vis and
   * Limbic). Single source of truth: HumanMacroPage.tsx decides what goes in
   * here (disorder red, per-lobe colors, ...) — this component just renders
   * whatever it's given, it has no opinion about WHY a region is marked
   * differently. */
  additiveRegionColors: ReadonlyMap<string, RegionOverride>;
  /** Whether `activeNetwork`'s own un-highlighted regions should render as
   * the default blue "network baseline" at all — true in 보기 모드
   * ="network", false in 보기 모드="anatomy". Real user-reported bug this
   * fixes: activeNetwork defaults to "Vis" and never gets "deselected", so
   * without this the Vis baseline kept rendering underneath the lobe
   * overlay even in anatomy mode — the network layer effectively couldn't
   * be turned off. When false, only regions that ALSO have an additive
   * color (i.e. belong to the selected lobe) render from the active
   * network; everything else in it is hidden, symmetric with how leaving
   * anatomy mode already clears the lobe overlay (docs/33). */
  showNetworkBaseline: boolean;
}

export function HumanMacroCanvas({ connectome, activeNetwork, diveProgress, additiveRegionColors, showNetworkBaseline }: HumanMacroCanvasProps) {
  if (!connectome) {
    return <div className="viewport-loading">커넥톰 데이터를 불러오는 중입니다…</div>;
  }

  const regionOpacity = diveNeuralOpacity(diveProgress);
  const activeNetworkRegions = connectome.regions.filter((r) => r.network === activeNetwork);
  const activeIds = new Set(activeNetworkRegions.map((r) => r.id));
  // The "baseline" set actually rendered from the active network: all of it
  // when the network layer itself is on-screen, or only its additively
  // colored members (e.g. this network's regions that also belong to the
  // selected lobe) when it isn't — see the prop docstring above.
  const baselineRegions = showNetworkBaseline ? activeNetworkRegions : activeNetworkRegions.filter((r) => additiveRegionColors.has(r.id));
  // Colored regions outside the active network are shown too (additive,
  // not a network switch) — see the additiveRegionColors docstring above.
  // Always shown regardless of showNetworkBaseline since these were never
  // part of the network baseline to begin with.
  const extraColored = connectome.regions.filter((r) => additiveRegionColors.has(r.id) && !activeIds.has(r.id));
  const visibleConnectome: MacroConnectome = { ...connectome, regions: baselineRegions };

  return (
    <Canvas camera={{ position: [0, 2.2, 7], fov: 45 }}>
      <CanvasReadyKick />
      <color attach="background" args={["#050b09"]} />
      <ambientLight intensity={0.6} />
      <pointLight position={[4, 4, 4]} intensity={40} color="#c2ff70" />
      <pointLight position={[-4, -2, -3]} intensity={15} color="#75cce9" />

      <HumanHeadLayers anatomy={connectome.anatomy} progress={diveProgress} showH01Hint={activeNetwork === "Limbic"} />
      <RegionEdges connectome={visibleConnectome} opacity={regionOpacity} />
      {baselineRegions.map((region) => (
        <RegionNode key={region.id} region={region} opacity={regionOpacity} override={additiveRegionColors.get(region.id) ?? null} />
      ))}
      {extraColored.map((region) => (
        <RegionNode key={region.id} region={region} opacity={regionOpacity} override={additiveRegionColors.get(region.id)!} />
      ))}

      <OrbitControls enablePan minDistance={1} maxDistance={20} target={[0, 0, 0]} />
    </Canvas>
  );
}
