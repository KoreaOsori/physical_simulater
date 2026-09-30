import { create } from "zustand";

import type { ConnectionStatus } from "@/shared/lib/ws-client";
import type { Connectome, FlyStimulus, SimulationEvent } from "@/types/connectome";

export interface LogEntry {
  id: string;
  time: string;
  tag: string;
  message: string;
}

const STAGE_TAG: Record<SimulationEvent["stage"], string> = {
  command: "자극",
  synapse: "시냅스",
  neurotransmitter: "신경전달물질",
  muscle: "출력(MBON/DN)",
  movement: "행동 반응",
};

function toLogEntry(event: SimulationEvent): LogEntry {
  return {
    id: `${event.stage}-${event.t_ms}-${Math.random().toString(36).slice(2, 8)}`,
    time: `+${event.t_ms.toFixed(1)} ms`,
    tag: STAGE_TAG[event.stage],
    message: event.message,
  };
}

/** Lean counterpart to store/simulation-store.ts for the Drosophila v2 (/fly)
 * page — no body/muscle/layer-reveal state, since this pass's olfactory
 * subset has no effectors (see backend/app/data/sources/drosophila/SOURCES.md). */
interface FlySimulationState {
  connectome: Connectome | null;
  connectionStatus: ConnectionStatus;
  activeCommand: FlyStimulus | null;
  signalActive: boolean;
  logs: LogEntry[];
  activeNeuronIds: Set<string>;
  activeSynapseKeys: Set<string>;
  playbackGeneration: number;

  setConnectome: (connectome: Connectome) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  beginCommandTrace: (stimulus: FlyStimulus) => number;
  applyEvent: (event: SimulationEvent, generation: number) => void;
  clearSignal: () => void;
}

export const useFlySimulationStore = create<FlySimulationState>((set, get) => ({
  connectome: null,
  connectionStatus: "connecting",
  activeCommand: null,
  signalActive: false,
  logs: [{ id: "seed-1", time: "00:00.000", tag: "준비", message: "커넥톰 데이터 로딩 대기 중입니다." }],
  activeNeuronIds: new Set(),
  activeSynapseKeys: new Set(),
  playbackGeneration: 0,

  setConnectome: (connectome) => set({ connectome }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),

  beginCommandTrace: (stimulus) => {
    const generation = get().playbackGeneration + 1;
    set({
      playbackGeneration: generation,
      activeCommand: stimulus,
      signalActive: true,
      activeNeuronIds: new Set(),
      activeSynapseKeys: new Set(),
    });
    return generation;
  },

  applyEvent: (event, generation) =>
    set((state) => {
      if (generation !== state.playbackGeneration) return state;

      const activeNeuronIds = new Set(state.activeNeuronIds);
      const activeSynapseKeys = new Set(state.activeSynapseKeys);
      if (event.source) activeNeuronIds.add(event.source);
      if (event.target) activeNeuronIds.add(event.target);

      if (event.stage === "synapse" && event.source && state.connectome) {
        const outgoing = state.connectome.synapses.filter((s) => s.pre === event.source).slice(0, 6);
        for (const s of outgoing) activeSynapseKeys.add(`${s.pre}->${s.post}`);
      }
      if (event.stage === "muscle" && event.source && event.target) {
        activeSynapseKeys.add(`${event.source}->${event.target}`);
      }

      return { logs: [...state.logs, toLogEntry(event)], activeNeuronIds, activeSynapseKeys };
    }),

  clearSignal: () => set({ signalActive: false }),
}));
