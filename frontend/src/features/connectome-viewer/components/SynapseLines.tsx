"use client";

import { useMemo } from "react";

import type { Position3D, Synapse } from "@/types/connectome";

const CHEMICAL_COLOR: [number, number, number] = [0.9, 0.84, 0.48];
const ELECTRICAL_COLOR: [number, number, number] = [0.56, 0.87, 0.95];
const ACTIVE_COLOR: [number, number, number] = [1, 0.94, 0.55];

function buildLineBuffers(
  synapses: Synapse[],
  positions: Map<string, Position3D>,
): { vertices: Float32Array; colors: Float32Array } {
  const vertices = new Float32Array(synapses.length * 2 * 3);
  const colors = new Float32Array(synapses.length * 2 * 3);
  let vertexCount = 0;

  for (const synapse of synapses) {
    const pre = positions.get(synapse.pre);
    const post = positions.get(synapse.post);
    if (!pre || !post) continue;
    const [r, g, b] = synapse.type === "electrical" ? ELECTRICAL_COLOR : CHEMICAL_COLOR;

    vertices[vertexCount * 3] = pre.x;
    vertices[vertexCount * 3 + 1] = pre.y;
    vertices[vertexCount * 3 + 2] = pre.z;
    colors[vertexCount * 3] = r;
    colors[vertexCount * 3 + 1] = g;
    colors[vertexCount * 3 + 2] = b;
    vertexCount++;

    vertices[vertexCount * 3] = post.x;
    vertices[vertexCount * 3 + 1] = post.y;
    vertices[vertexCount * 3 + 2] = post.z;
    colors[vertexCount * 3] = r;
    colors[vertexCount * 3 + 1] = g;
    colors[vertexCount * 3 + 2] = b;
    vertexCount++;
  }

  return { vertices: vertices.subarray(0, vertexCount * 3), colors: colors.subarray(0, vertexCount * 3) };
}

/**
 * All ~6,900 synapses in a single draw call (one merged buffer geometry).
 * Rendering each synapse as its own <Line> component would mean thousands of
 * separate draw calls / React fiber nodes.
 */
export function SynapseLines({
  synapses,
  positions,
  opacity,
}: {
  synapses: Synapse[];
  positions: Map<string, Position3D>;
  opacity: number;
}) {
  const { vertices, colors } = useMemo(() => buildLineBuffers(synapses, positions), [synapses, positions]);

  if (opacity <= 0 || vertices.length === 0) return null;

  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[vertices, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <lineBasicMaterial vertexColors transparent opacity={opacity * 0.16} />
    </lineSegments>
  );
}

/** The (usually one) synapse actually referenced by the current command's
 * event trace, drawn brighter on top of the base graph. Recomputed only when
 * the active set changes, so it stays cheap even though the base graph above
 * is large. */
export function ActiveSynapseLines({
  synapses,
  positions,
  activeSynapseKeys,
  opacity,
}: {
  synapses: Synapse[];
  positions: Map<string, Position3D>;
  activeSynapseKeys: Set<string>;
  opacity: number;
}) {
  const { vertices, colors } = useMemo(() => {
    if (activeSynapseKeys.size === 0) return { vertices: new Float32Array(0), colors: new Float32Array(0) };
    const active = synapses.filter((s) => activeSynapseKeys.has(`${s.pre}->${s.post}`));
    const buffers = buildLineBuffers(active, positions);
    const colors = new Float32Array(buffers.vertices.length);
    for (let i = 0; i < colors.length; i += 3) {
      colors[i] = ACTIVE_COLOR[0];
      colors[i + 1] = ACTIVE_COLOR[1];
      colors[i + 2] = ACTIVE_COLOR[2];
    }
    return { vertices: buffers.vertices, colors };
  }, [synapses, positions, activeSynapseKeys]);

  if (opacity <= 0 || vertices.length === 0) return null;

  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[vertices, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <lineBasicMaterial vertexColors transparent opacity={opacity * 0.95} linewidth={2} />
    </lineSegments>
  );
}
