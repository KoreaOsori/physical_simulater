"use client";

import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { Mesh } from "three";

import { circuitClassDescriptionFor, curatedFlyDescriptionFor } from "@/features/connectome-viewer/lib/fly-neuron-info";
import { summarizeNeuron } from "@/features/connectome-viewer/lib/neuron-info";
import { useFlySimulationStore } from "@/store/fly-simulation-store";
import type { Neuron, NeuronType, Position3D } from "@/types/connectome";

const TYPE_COLOR: Record<NeuronType, string> = {
  sensory: "#75cce9",
  inter: "#baff71",
  motor: "#ff9c73",
  unknown: "#9aa79b",
};

interface FlyNeuronNodeProps {
  neuron: Neuron;
  position: Position3D;
  active: boolean;
  /** 0-1, defaults to 1 — used by the olfactory/visual "dive" slider
   * (FlyDiveSlider) to fade the neural network in as it reveals past the
   * external-anatomy stage. Pages without a dive stage (e.g. navigation)
   * just render at full opacity as before. */
  opacity?: number;
}

/** Same as connectome-viewer/components/NeuronNode.tsx, reading from the fly
 * store instead — see that file for why this is a separate component rather
 * than a shared one (the tooltip needs the *matching* connectome to look up
 * synapse degree/partners, and each page has its own store/dataset). */
export function FlyNeuronNode({ neuron, position, active, opacity = 1 }: FlyNeuronNodeProps) {
  const meshRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const connectome = useFlySimulationStore((s) => s.connectome);
  const color = TYPE_COLOR[neuron.type];

  useFrame((state) => {
    if (!meshRef.current) return;
    const pulse = active ? 1 + Math.sin(state.clock.elapsedTime * 8) * 0.25 : 1;
    meshRef.current.scale.setScalar(hovered ? pulse * 1.7 : pulse);
  });

  if (opacity <= 0.02) return null;

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
      <sphereGeometry args={[0.05, 6, 6]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={active || hovered ? 1.4 : 0.35}
        toneMapped={false}
        transparent
        opacity={opacity}
      />
      {hovered && connectome && (
        <Html distanceFactor={5} zIndexRange={[60, 0]} style={{ pointerEvents: "none" }} center>
          <FlyNeuronTooltip neuron={neuron} active={active} />
        </Html>
      )}
    </mesh>
  );
}

function FlyNeuronTooltip({ neuron, active }: { neuron: Neuron; active: boolean }) {
  const connectome = useFlySimulationStore((s) => s.connectome);
  if (!connectome) return null;
  const summary = summarizeNeuron(neuron, connectome);
  const curated = curatedFlyDescriptionFor(neuron.cell_type);
  const classDescription = circuitClassDescriptionFor(neuron);

  return (
    <div className="neuron-tooltip">
      <strong>
        {neuron.name}
        {active && <em> · 발화 중</em>}
      </strong>
      <p className="neuron-tooltip-meta">
        {summary.typeLabel} · {summary.ntLabel}
        {summary.categoriesKo.length > 0 && ` · ${summary.categoriesKo.join(" · ")}`}
      </p>
      {curated && <p className="neuron-tooltip-curated">{curated}</p>}
      {!curated && classDescription && <p className="neuron-tooltip-curated">{classDescription}</p>}
      <p className="neuron-tooltip-degree">
        출력 시냅스 {summary.outDegree}개 · 입력 시냅스 {summary.inDegree}개
      </p>
    </div>
  );
}
