"use client";

import { useEffect, useMemo } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";

import { diveNeuralOpacity } from "@/features/connectome-viewer/lib/dive-reveal";
import { HumanHeadLayers } from "@/features/connectome-viewer/components/HumanHeadLayers";
import type { HeadAnatomy, MicroConnectomeSample } from "@/types/human";

const SYNAPSE_AXON_COLOR: [number, number, number] = [1, 0.55, 0.2]; // sending/output side
const SYNAPSE_DENDRITE_COLOR: [number, number, number] = [0.35, 0.65, 1]; // receiving/input side

/** Real H01 synapse contact points (see SOURCES.md's "실제 시냅스 접촉점"
 * section) — each has at least one real proofread-neuron side, the other
 * almost always an unproofread segment (`partner_is_proofread`, honestly not
 * drawn as a resolved neuron since we don't have its shape). Colored by
 * `role`: this project's only verified per-synapse signal (AXON = the real
 * neuron is sending here, DENDRITE = receiving) — see SOURCES.md for why no
 * excitatory/inhibitory color is used. One draw call, same reasoning as
 * HumanMicroPoints. */
function HumanMicroSynapses({ sample, opacity }: { sample: MicroConnectomeSample; opacity: number }) {
  const { positions, colors } = useMemo(() => {
    const positions = new Float32Array(sample.synapses.length * 3);
    const colors = new Float32Array(sample.synapses.length * 3);
    sample.synapses.forEach((s, i) => {
      positions[i * 3] = s.position.x;
      positions[i * 3 + 1] = s.position.y;
      positions[i * 3 + 2] = s.position.z;
      const [r, g, b] = s.role === "AXON" ? SYNAPSE_AXON_COLOR : SYNAPSE_DENDRITE_COLOR;
      colors[i * 3] = r;
      colors[i * 3 + 1] = g;
      colors[i * 3 + 2] = b;
    });
    return { positions, colors };
  }, [sample]);

  if (opacity <= 0.02 || sample.synapses.length === 0) return null;
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.012} vertexColors transparent opacity={0.7 * opacity} sizeAttenuation toneMapped={false} />
    </points>
  );
}

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

/** Deterministic per-neuron hue so the 104 real H01 neurons are visually
 * distinguishable from each other in one merged point cloud (see
 * HumanMicroPoints below for why it's one draw call, not 104). */
function colorForNeuron(neuronId: string): [number, number, number] {
  let hash = 0;
  for (let i = 0; i < neuronId.length; i++) hash = (hash * 31 + neuronId.charCodeAt(i)) >>> 0;
  const hue = (hash % 360) / 360;
  // small manual HSL->RGB (avoids pulling in a color library for one conversion)
  const s = 0.65;
  const l = 0.6;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((hue * 6) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  const seg = Math.floor(hue * 6);
  if (seg === 0) [r, g, b] = [c, x, 0];
  else if (seg === 1) [r, g, b] = [x, c, 0];
  else if (seg === 2) [r, g, b] = [0, c, x];
  else if (seg === 3) [r, g, b] = [0, x, c];
  else if (seg === 4) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [r + m, g + m, b + m];
}

function HumanMicroPoints({ sample, opacity }: { sample: MicroConnectomeSample; opacity: number }) {
  const { positions, colors } = useMemo(() => {
    const positions = new Float32Array(sample.points.length * 3);
    const colors = new Float32Array(sample.points.length * 3);
    sample.points.forEach((p, i) => {
      positions[i * 3] = p.position.x;
      positions[i * 3 + 1] = p.position.y;
      positions[i * 3 + 2] = p.position.z;
      const [r, g, b] = colorForNeuron(p.neuron_id);
      colors[i * 3] = r;
      colors[i * 3 + 1] = g;
      colors[i * 3 + 2] = b;
    });
    return { positions, colors };
  }, [sample]);

  if (opacity <= 0.02) return null;
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.02} vertexColors transparent opacity={0.85 * opacity} sizeAttenuation toneMapped={false} />
    </points>
  );
}

interface HumanMicroCanvasProps {
  sample: MicroConnectomeSample | null;
  anatomy: HeadAnatomy | null;
  /** 0 (겉모습) → 1 (신경계 = 실제 H01 뉴런), see dive-reveal.ts. */
  diveProgress: number;
  showSynapses: boolean;
}

/** Real H01 (Harvard/Google) human temporal-cortex EM reconstruction —
 * 104 real proofread neurons, ~41k decimated skeleton points (see
 * backend/app/data/sources/human/SOURCES.md) rendered as one colored point
 * cloud (one draw call, same reasoning as SynapseLines.tsx) rather than 104
 * separate mesh objects. No per-point hover — at this density individual
 * points aren't meaningfully selectable, unlike the sparser neuron nodes on
 * the fly/worm pages.
 *
 * The dive-in reveal's outer two stages (겉모습/뇌 조직) reuse the same real
 * MNI152 skin/brain isosurfaces as the macro page as generic anatomical
 * context — NOT registered to this specific sample (H01 has no MNI
 * registration) — fading into the real H01 point cloud for the 신경계 stage
 * instead of a gray-matter isosurface, which would falsely imply exact
 * correspondence. */
export function HumanMicroCanvas({ sample, anatomy, diveProgress, showSynapses }: HumanMicroCanvasProps) {
  if (!sample) {
    return <div className="viewport-loading">샘플 데이터를 불러오는 중입니다…</div>;
  }

  const pointOpacity = diveNeuralOpacity(diveProgress);

  return (
    <Canvas camera={{ position: [0, 1.5, 6], fov: 45 }}>
      <CanvasReadyKick />
      <color attach="background" args={["#050b09"]} />
      <ambientLight intensity={0.8} />
      <pointLight position={[3, 3, 3]} intensity={20} color="#e0b48c" />

      {anatomy && (
        <HumanHeadLayers anatomy={anatomy} progress={diveProgress} showH01Hint={false} showGrayMatter={false} />
      )}
      {anatomy && diveProgress > DIVE_CONTEXT_LABEL_THRESHOLD && diveProgress < 0.95 && (
        <Html position={[0, -2.2, 0]} distanceFactor={9} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }} center>
          <div className="anatomy-region-label" style={{ opacity: 1 - pointOpacity }}>
            <em>일반 MNI 평균 두상/뇌 — 이 샘플에 좌표 정합된 것 아님</em>
          </div>
        </Html>
      )}
      <HumanMicroPoints sample={sample} opacity={pointOpacity} />
      {showSynapses && <HumanMicroSynapses sample={sample} opacity={pointOpacity} />}

      <OrbitControls enablePan minDistance={0.5} maxDistance={20} target={[0, 0, 0]} />
    </Canvas>
  );
}

const DIVE_CONTEXT_LABEL_THRESHOLD = 0.05;
