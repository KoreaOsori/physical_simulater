import { create } from "zustand";

import type { MovementPulse } from "@/features/connectome-viewer/lib/movement-pose";
import type { ConnectionStatus } from "@/shared/lib/ws-client";
import type { ClassicAblation, Connectome, Direction, Neurotransmitter, SimulationEvent } from "@/types/connectome";

export interface LogEntry {
  id: string;
  time: string;
  tag: string;
  message: string;
}

/** A brief neurotransmitter-release animation: a particle travels from
 * `sourceId` to each of `targetIds` (or, for muscle-stage events where the
 * firing neuron isn't tracked, just a release cloud at `targetIds` with no
 * source). See features/connectome-viewer/components/NeurotransmitterBursts.tsx. */
export interface Burst {
  id: string;
  sourceId: string | null;
  targetIds: string[];
  neurotransmitter: Neurotransmitter;
  startedAt: number; // performance.now()
}

/** A muscle/effector that just received a signal — drives the local body-mesh
 * deformation in WormBodyMesh, decaying out over MUSCLE_ACTIVATION_MS. */
export interface MuscleActivation {
  id: string;
  effectorId: string;
  startedAt: number;
}

export const MUSCLE_ACTIVATION_MS = 1400;

const STAGE_TAG: Record<SimulationEvent["stage"], string> = {
  command: "명령",
  synapse: "시냅스",
  neurotransmitter: "신경전달물질",
  muscle: "근육",
  movement: "운동",
};

function toLogEntry(event: SimulationEvent): LogEntry {
  return {
    id: `${event.stage}-${event.t_ms}-${Math.random().toString(36).slice(2, 8)}`,
    time: `+${event.t_ms.toFixed(1)} ms`,
    tag: STAGE_TAG[event.stage],
    message: event.message,
  };
}

const MAX_BURST_TARGETS = 6;
const MAX_TRACKED_BURSTS = 40;
const MAX_TRACKED_MUSCLE_ACTIVATIONS = 40;

interface SimulationState {
  connectome: Connectome | null;
  connectionStatus: ConnectionStatus;
  activeCommand: Direction | null;
  signalActive: boolean;
  selectedTissueId: string;
  logs: LogEntry[];
  activeNeuronIds: Set<string>;
  activeSynapseKeys: Set<string>;
  bursts: Burst[];
  muscleActivations: MuscleActivation[];
  movementPulse: MovementPulse | null;
  /** Bumped every time a new command trace starts; playback.ts's scheduled
   * callbacks check this so a stale timer from an interrupted trace can't
   * apply itself into a newer one. */
  playbackGeneration: number;
  /** 0-100: how far the "해부 레이어" slider has peeled the body open —
   * 0 = outer skin only, 100 = nervous system fully revealed. */
  layerReveal: number;
  /** The currently toggled-on classic ablation (AblationPanel.tsx), if any —
   * its neuron_ids get (1) highlighted in the 3D scene and (2) sent as
   * `silenced_neuron_ids` on the NEXT command a user issues via the normal
   * keyboard controls, so an existing "전진"/"후진" press becomes "what does
   * this command look like with these neurons ablated" without adding a
   * separate run button (see docs/26-worm-classic-ablation-behavior.md). */
  activeAblation: ClassicAblation | null;
  /** Last command's habituation level for its direction (0 = naive) -- see
   * docs/29-worm-habituation-plasticity.md. Not per-direction here since
   * only "the most recent command's" value is shown (SequenceStatusBar). */
  habituationLevel: number;

  setConnectome: (connectome: Connectome) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setSelectedTissueId: (id: string) => void;
  setLayerReveal: (value: number) => void;
  setActiveAblation: (ablation: ClassicAblation | null) => void;
  setHabituationLevel: (level: number) => void;
  /** Starts a new command trace: resets per-trace highlight state and
   * returns the generation id this trace's playback should check against. */
  beginCommandTrace: (direction: Direction) => number;
  /** Applies exactly one event — call this from a scheduled playback timer,
   * not with the whole event array at once, so the sequence animates. */
  applyEvent: (event: SimulationEvent, generation: number) => void;
  clearSignal: () => void;
  pruneExpiredBursts: (maxAgeMs: number) => void;
  pruneExpiredMuscleActivations: (maxAgeMs: number) => void;
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  connectome: null,
  connectionStatus: "connecting",
  activeCommand: null,
  signalActive: false,
  selectedTissueId: "neurons",
  logs: [
    { id: "seed-1", time: "00:00.000", tag: "준비", message: "커넥톰 데이터 로딩 대기 중입니다." },
  ],
  activeNeuronIds: new Set(),
  activeSynapseKeys: new Set(),
  bursts: [],
  muscleActivations: [],
  movementPulse: null,
  playbackGeneration: 0,
  layerReveal: 8,
  activeAblation: null,
  habituationLevel: 0,

  setConnectome: (connectome) => set({ connectome }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setSelectedTissueId: (selectedTissueId) => set({ selectedTissueId }),
  setLayerReveal: (layerReveal) => set({ layerReveal: Math.min(100, Math.max(0, layerReveal)) }),
  setActiveAblation: (activeAblation) => set({ activeAblation }),
  setHabituationLevel: (habituationLevel) => set({ habituationLevel }),

  beginCommandTrace: (direction) => {
    const generation = get().playbackGeneration + 1;
    set({
      playbackGeneration: generation,
      activeCommand: direction,
      signalActive: true,
      activeNeuronIds: new Set(),
      activeSynapseKeys: new Set(),
      movementPulse: null,
    });
    return generation;
  },

  applyEvent: (event, generation) =>
    set((state) => {
      if (generation !== state.playbackGeneration) return state; // superseded by a newer command

      const activeNeuronIds = new Set(state.activeNeuronIds);
      const activeSynapseKeys = new Set(state.activeSynapseKeys);
      const newBursts: Burst[] = [];
      const newMuscleActivations: MuscleActivation[] = [];
      const now = performance.now();

      if (event.source) activeNeuronIds.add(event.source);
      if (event.target) activeNeuronIds.add(event.target);

      if (event.stage === "synapse" && event.source && state.connectome) {
        // The HH engine reports "this neuron fired", not a specific
        // pre->post pair, so derive which real synapses to light up /
        // animate from the connectome's actual outgoing edges.
        const outgoing = state.connectome.synapses
          .filter((s) => s.pre === event.source)
          .slice(0, MAX_BURST_TARGETS);
        for (const s of outgoing) activeSynapseKeys.add(`${s.pre}->${s.post}`);
        if (outgoing.length > 0) {
          newBursts.push({
            id: `${event.source}-${event.t_ms}-${Math.random().toString(36).slice(2, 7)}`,
            sourceId: event.source,
            targetIds: outgoing.map((s) => s.post),
            neurotransmitter: event.neurotransmitter ?? "unknown",
            startedAt: now,
          });
        }
      }

      if (event.stage === "muscle" && event.target) {
        newBursts.push({
          id: `muscle-${event.target}-${event.t_ms}-${Math.random().toString(36).slice(2, 7)}`,
          sourceId: null,
          targetIds: [event.target],
          neurotransmitter: "unknown",
          startedAt: now,
        });
        newMuscleActivations.push({
          id: `${event.target}-${event.t_ms}-${Math.random().toString(36).slice(2, 7)}`,
          effectorId: event.target,
          startedAt: now,
        });
      }

      const movementPulse: MovementPulse | null =
        event.stage === "movement" && state.activeCommand ? { direction: state.activeCommand, startedAt: now } : state.movementPulse;

      return {
        logs: [...state.logs, toLogEntry(event)],
        activeNeuronIds,
        activeSynapseKeys,
        bursts: [...state.bursts, ...newBursts].slice(-MAX_TRACKED_BURSTS),
        muscleActivations: [...state.muscleActivations, ...newMuscleActivations].slice(-MAX_TRACKED_MUSCLE_ACTIVATIONS),
        movementPulse,
      };
    }),

  clearSignal: () => set({ signalActive: false }),

  pruneExpiredBursts: (maxAgeMs) =>
    set((state) => {
      const now = performance.now();
      const kept = state.bursts.filter((b) => now - b.startedAt < maxAgeMs);
      return kept.length === state.bursts.length ? state : { bursts: kept };
    }),

  pruneExpiredMuscleActivations: (maxAgeMs) =>
    set((state) => {
      const now = performance.now();
      const kept = state.muscleActivations.filter((m) => now - m.startedAt < maxAgeMs);
      return kept.length === state.muscleActivations.length ? state : { muscleActivations: kept };
    }),
}));
