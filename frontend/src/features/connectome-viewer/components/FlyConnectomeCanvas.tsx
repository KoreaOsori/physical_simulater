"use client";

import { useEffect, useMemo } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

import { FlyAnatomyRegions } from "@/features/connectome-viewer/components/FlyAnatomyRegions";
import { FlyExternalAnatomy } from "@/features/connectome-viewer/components/FlyExternalAnatomy";
import { FlyNeuronNode } from "@/features/connectome-viewer/components/FlyNeuronNode";
import { FlyOrganShell } from "@/features/connectome-viewer/components/FlyOrganShell";
import { ActiveSynapseLines, SynapseLines } from "@/features/connectome-viewer/components/SynapseLines";
import {
  diveExternalOpacity,
  diveNeuralOpacity,
  diveOrganOpacity,
  type FlyDiveConfig,
} from "@/features/connectome-viewer/lib/fly-dive-stages";
import { useFlySimulationStore } from "@/store/fly-simulation-store";

/** Kicks the WebGL canvas to repaint shortly after mount. Without this, the
 * very first frame on a fresh page load can be captured before the parent
 * `.viewport` layout (now taller with FlyDiveSlider above it) has fully
 * settled, leaving the canvas blank until the user's first interaction
 * (drag/resize) forces a repaint — this makes the initial 겉모습 stage
 * actually visible without requiring that first interaction. */
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

interface FlyConnectomeCanvasProps {
  showAnatomy: boolean;
  /** 0-1 "dive" position — ignored (network always shown at full opacity)
   * when diveConfig is null (e.g. the navigation page, which has no
   * external-organ stage — see fly-dive-stages.ts). */
  diveProgress: number;
  diveConfig: FlyDiveConfig | null;
}

/** Counterpart to ConnectomeCanvas.tsx for the Drosophila v2 (/fly) page —
 * no body-bending or skin mesh (this circuit subset has no effectors/movement
 * to animate, see SOURCES.md), so it plots `connectome.neurons[].position`
 * (a computed layered layout, not real anatomical coordinates — see
 * build_drosophila_dataset.py) directly, with an optional real-neuropil-name
 * region overlay (`FlyAnatomyRegions`) for orientation and an optional
 * external-anatomy "dive-in" reveal (`FlyExternalAnatomy`/`FlyOrganShell`,
 * see fly-dive-stages.ts) before the network fades in. */
export function FlyConnectomeCanvas({ showAnatomy, diveProgress, diveConfig }: FlyConnectomeCanvasProps) {
  const connectome = useFlySimulationStore((s) => s.connectome);
  const signalActive = useFlySimulationStore((s) => s.signalActive);
  const activeNeuronIds = useFlySimulationStore((s) => s.activeNeuronIds);
  const activeSynapseKeys = useFlySimulationStore((s) => s.activeSynapseKeys);

  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number; z: number }>();
    if (!connectome) return map;
    for (const n of connectome.neurons) map.set(n.id, n.position);
    return map;
  }, [connectome]);

  if (!connectome) {
    return <div className="viewport-loading">커넥톰 데이터를 불러오는 중입니다…</div>;
  }

  const neuralOpacity = diveConfig ? diveNeuralOpacity(diveProgress) : 1;

  return (
    <Canvas camera={{ position: [0, 2.2, 7], fov: 45 }}>
      <CanvasReadyKick />
      <color attach="background" args={["#050b09"]} />
      <ambientLight intensity={0.6} />
      <pointLight position={[4, 4, 4]} intensity={40} color="#c2ff70" />
      <pointLight position={[-4, -2, -3]} intensity={15} color="#75cce9" />

      {diveConfig && (
        <>
          <FlyExternalAnatomy
            organKind={diveConfig.organKind}
            organLabel={diveConfig.organLabel}
            opacity={diveExternalOpacity(diveProgress)}
          />
          <FlyOrganShell
            organNeuropilLabel={diveConfig.organNeuropilLabel}
            flowLabel={diveConfig.flowLabel}
            opacity={diveOrganOpacity(diveProgress)}
          />
        </>
      )}

      <FlyAnatomyRegions neurons={connectome.neurons} positions={positions} visible={showAnatomy} opacity={neuralOpacity} />

      <SynapseLines synapses={connectome.synapses} positions={positions} opacity={0.4 * neuralOpacity} />
      {signalActive && (
        <ActiveSynapseLines
          synapses={connectome.synapses}
          positions={positions}
          activeSynapseKeys={activeSynapseKeys}
          opacity={neuralOpacity}
        />
      )}

      {connectome.neurons.map((neuron) => (
        <FlyNeuronNode
          key={neuron.id}
          neuron={neuron}
          position={positions.get(neuron.id)!}
          active={signalActive && activeNeuronIds.has(neuron.id)}
          opacity={neuralOpacity}
        />
      ))}

      <OrbitControls enablePan minDistance={1} maxDistance={20} target={[0, 0, 0]} />
    </Canvas>
  );
}
