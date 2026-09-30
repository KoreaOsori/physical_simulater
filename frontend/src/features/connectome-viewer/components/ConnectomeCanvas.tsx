"use client";

import { useMemo, useRef, type ElementRef } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Group } from "three";

import { BodyLandmarks } from "@/features/connectome-viewer/components/BodyLandmarks";
import { EffectorNode } from "@/features/connectome-viewer/components/EffectorNode";
import { NeuronNode } from "@/features/connectome-viewer/components/NeuronNode";
import { NeurotransmitterBursts } from "@/features/connectome-viewer/components/NeurotransmitterBursts";
import { ActiveSynapseLines, SynapseLines } from "@/features/connectome-viewer/components/SynapseLines";
import { WormBodyMesh } from "@/features/connectome-viewer/components/WormBodyMesh";
import { apFraction, bodyCenterX, buildBentPositionLookup, computeBodyLandmarks, parseLateralSign } from "@/features/connectome-viewer/lib/body-pose";
import { computeLayerOpacities } from "@/features/connectome-viewer/lib/layer-reveal";
import { createWormSpine, useWormLocomotion } from "@/features/connectome-viewer/lib/use-worm-locomotion";
import { useSimulationStore } from "@/store/simulation-store";

/** Runs the worm's physics (bending + RFT locomotion, see
 * use-worm-locomotion.ts) and applies the resulting rigid pose to
 * `groupRef`/`controlsRef` — a real child component (not just a plain
 * function call) because `useFrame`/hooks need to run inside the R3F
 * reconciler tree, which only exists inside <Canvas>. Renders nothing
 * itself; WormBodyMesh (child of the group it's driving) reads the same
 * `spine` instance for its geometry. */
function WormPhysicsDriver(props: Parameters<typeof useWormLocomotion>[0]) {
  useWormLocomotion(props);
  return null;
}

export function ConnectomeCanvas() {
  const connectome = useSimulationStore((s) => s.connectome);
  const signalActive = useSimulationStore((s) => s.signalActive);
  const activeNeuronIds = useSimulationStore((s) => s.activeNeuronIds);
  const activeSynapseKeys = useSimulationStore((s) => s.activeSynapseKeys);
  const layerReveal = useSimulationStore((s) => s.layerReveal);
  const activeAblation = useSimulationStore((s) => s.activeAblation);
  const silencedNeuronIds = useMemo(() => new Set(activeAblation?.neuron_ids ?? []), [activeAblation]);

  const bent = useMemo(() => (connectome ? buildBentPositionLookup(connectome) : null), [connectome]);
  const layers = useMemo(() => computeLayerOpacities(layerReveal), [layerReveal]);

  const landmarks = useMemo(() => (connectome && bent ? computeBodyLandmarks(connectome, bent.extent) : null), [connectome, bent]);

  const lateralIndex = useMemo(() => {
    const map = new Map<string, { t: number; side: number }>();
    if (!connectome || !bent) return map;
    for (const node of [...connectome.neurons, ...connectome.effectors]) {
      map.set(node.id, { t: apFraction(node.position.x, bent.extent), side: parseLateralSign(node.id) });
    }
    return map;
  }, [connectome, bent]);

  // Real damped-spring bending (body-physics.ts) plus RFT locomotion
  // (rft-locomotion.ts) — see docs/17-*. Created here (not inside
  // WormPhysicsDriver) so WormBodyMesh can read the same instance.
  const spine = useMemo(() => createWormSpine(), []);
  const wormGroupRef = useRef<Group>(null);
  const controlsRef = useRef<ElementRef<typeof OrbitControls>>(null);

  if (!connectome || !bent || !landmarks) {
    return <div className="viewport-loading">커넥톰 데이터를 불러오는 중입니다…</div>;
  }

  const center = bodyCenterX(bent.extent);
  const landmarkOpacity = Math.max(layers.skin, layers.effector);

  return (
    <Canvas camera={{ position: [center, 2.6, 9], fov: 45 }}>
      <color attach="background" args={["#050b09"]} />
      <ambientLight intensity={0.6} />

      <WormPhysicsDriver
        spine={spine}
        extent={bent.extent}
        landmarks={landmarks}
        lateralIndex={lateralIndex}
        groupRef={wormGroupRef}
        controlsRef={controlsRef}
      />

      {/* Everything below is body-center-relative (see body-pose.ts) so this
          group's own local origin IS the worm's center — the RFT locomotion
          pose (translate + rotate) applied to it turns/moves the whole worm
          as a rigid body around its own middle, not some unrelated pivot. */}
      <group ref={wormGroupRef} position={[center, 0, 0]}>
        <pointLight position={[4, 4, 4]} intensity={40} color="#c2ff70" />
        <pointLight position={[-4, -2, -3]} intensity={15} color="#75cce9" />

        <WormBodyMesh extent={bent.extent} opacity={layers.skin} landmarks={landmarks} spine={spine} />
        <BodyLandmarks extent={bent.extent} landmarks={landmarks} opacity={landmarkOpacity} />

        <SynapseLines synapses={connectome.synapses} positions={bent.positions} opacity={layers.neuron} />
        {signalActive && (
          <ActiveSynapseLines
            synapses={connectome.synapses}
            positions={bent.positions}
            activeSynapseKeys={activeSynapseKeys}
            opacity={layers.neuron}
          />
        )}
        <NeurotransmitterBursts positions={bent.positions} opacity={layers.neuron} />

        {connectome.neurons.map((neuron) => (
          <NeuronNode
            key={neuron.id}
            neuron={neuron}
            position={bent.positions.get(neuron.id)!}
            active={signalActive && activeNeuronIds.has(neuron.id)}
            opacity={layers.neuron}
            silenced={silencedNeuronIds.has(neuron.id)}
          />
        ))}
        {connectome.effectors.map((effector) => (
          <EffectorNode
            key={effector.id}
            effector={effector}
            position={bent.positions.get(effector.id)!}
            active={signalActive && activeNeuronIds.has(effector.id)}
            opacity={layers.effector}
          />
        ))}
      </group>

      {/* No `target` prop here on purpose: use-worm-locomotion.ts's useFrame
          sets controls.target imperatively every frame (starting from the
          same [center,0,0] the pose starts at) — a reactive `target` prop
          would fight that on every re-render this component gets from
          unrelated store changes (e.g. each synapse/muscle event during a
          10s command playback), snapping the camera back to the ORIGINAL
          fixed point while the worm has already moved on. `enableDamping`
          is off for the same reason: damped orbit easing can't keep up with
          a target that moves every physics frame, so the camera
          progressively lags behind and the worm walks off-screen. */}
      <OrbitControls
        ref={controlsRef}
        enableDamping={false}
        enablePan={false}
        minDistance={1.5}
        maxDistance={20}
      />
    </Canvas>
  );
}
