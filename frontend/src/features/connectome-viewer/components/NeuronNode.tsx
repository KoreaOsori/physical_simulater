"use client";

import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { Mesh } from "three";

import { summarizeNeuron } from "@/features/connectome-viewer/lib/neuron-info";
import { useSimulationStore } from "@/store/simulation-store";
import type { Neuron, NeuronType, Position3D } from "@/types/connectome";

const TYPE_COLOR: Record<NeuronType, string> = {
  sensory: "#75cce9",
  inter: "#baff71",
  motor: "#ff9c73",
  unknown: "#9aa79b",
};

interface NeuronNodeProps {
  neuron: Neuron;
  position: Position3D;
  active: boolean;
  opacity: number;
  /** True while this neuron is part of the currently toggled-on classic
   * ablation (see AblationPanel.tsx / store's activeAblation) — rendered in
   * a distinct red, same "additive highlight regardless of other state"
   * convention HumanMacroCanvas uses for disorder-associated regions. */
  silenced?: boolean;
}

const SILENCED_COLOR = "#ff3b3b";

export function NeuronNode({ neuron, position, active, opacity, silenced = false }: NeuronNodeProps) {
  const meshRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const connectome = useSimulationStore((s) => s.connectome);
  const color = silenced ? SILENCED_COLOR : TYPE_COLOR[neuron.type];

  useFrame((state) => {
    if (!meshRef.current) return;
    const pulse = active ? 1 + Math.sin(state.clock.elapsedTime * 8) * 0.25 : 1;
    meshRef.current.scale.setScalar(hovered ? pulse * 1.7 : pulse);
  });

  if (opacity <= 0) return null;

  return (
    <mesh
      ref={meshRef}
      position={[position.x, position.y, position.z]}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={(e) => {
        e.stopPropagation();
        setHovered(false);
      }}
    >
      <sphereGeometry args={[0.09, 8, 8]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={active || hovered || silenced ? 1.4 : 0.35}
        transparent
        opacity={opacity}
        toneMapped={false}
      />
      {hovered && connectome && (
        <Html distanceFactor={5} zIndexRange={[60, 0]} style={{ pointerEvents: "none" }} center>
          <NeuronTooltip neuron={neuron} active={active} silenced={silenced} />
        </Html>
      )}
    </mesh>
  );
}

function NeuronTooltip({ neuron, active, silenced }: { neuron: Neuron; active: boolean; silenced: boolean }) {
  const connectome = useSimulationStore((s) => s.connectome);
  if (!connectome) return null;
  const summary = summarizeNeuron(neuron, connectome);

  return (
    <div className="neuron-tooltip">
      <strong>
        {summary.id}
        {active && <em> · 발화 중</em>}
        {silenced && <em> · 절제됨(출력 억제)</em>}
      </strong>
      <p className="neuron-tooltip-meta">
        {summary.typeLabel} · {summary.ntLabel}
        {summary.categoriesKo.length > 0 && ` · ${summary.categoriesKo.join(" · ")}`}
      </p>
      {summary.curated && <p className="neuron-tooltip-curated">{summary.curated}</p>}
      {summary.descriptionEn && (
        <p className="neuron-tooltip-definition">
          <span>WormBase 정의</span> {summary.descriptionEn}
        </p>
      )}
      <p className="neuron-tooltip-degree">
        출력 시냅스 {summary.outDegree}개 · 입력 시냅스 {summary.inDegree}개
      </p>
      {summary.topPartners.length > 0 && (
        <p className="neuron-tooltip-partners">주요 연결: {summary.topPartners.join(", ")}</p>
      )}
      {summary.wormatlasUrl && <p className="neuron-tooltip-link">WormAtlas 개별 뉴런 페이지 있음</p>}
    </div>
  );
}
