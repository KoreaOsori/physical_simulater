import { create } from "zustand";

import type { ConnectionStatus } from "@/shared/lib/ws-client";
import type { SimulationEvent } from "@/types/connectome";
import type { GenePathwayCommand, HumanGenome } from "@/types/human";

export interface LogEntry {
  id: string;
  time: string;
  tag: string;
  message: string;
}

const STAGE_TAG: Record<SimulationEvent["stage"], string> = {
  command: "자극",
  synapse: "전사인자 활성화",
  neurotransmitter: "신경전달물질",
  muscle: "유전자 발현/수용체 결합",
  movement: "결과",
};

function toLogEntry(event: SimulationEvent): LogEntry {
  return {
    id: `${event.stage}-${event.t_ms}-${Math.random().toString(36).slice(2, 8)}`,
    time: `+${event.t_ms.toFixed(1)} ms`,
    tag: STAGE_TAG[event.stage],
    message: event.message,
  };
}

/** Same shape/role as fly-simulation-store.ts, adapted for the human genome
 * pathway demo — "activeGeneIds" plays the role activeNeuronIds played
 * there (both are just "which real id lit up during this event trace"). */
interface HumanGenomeState {
  genome: HumanGenome | null;
  connectionStatus: ConnectionStatus;
  activeCommand: GenePathwayCommand | null;
  signalActive: boolean;
  logs: LogEntry[];
  activeGeneIds: Set<string>;
  playbackGeneration: number;

  setGenome: (genome: HumanGenome) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  beginCommandTrace: (stimulus: GenePathwayCommand) => number;
  applyEvent: (event: SimulationEvent, generation: number) => void;
  clearSignal: () => void;
}

export const useHumanGenomeStore = create<HumanGenomeState>((set, get) => ({
  genome: null,
  connectionStatus: "connecting",
  activeCommand: null,
  signalActive: false,
  logs: [{ id: "seed-1", time: "00:00.000", tag: "준비", message: "게놈 데이터 로딩 대기 중입니다." }],
  activeGeneIds: new Set(),
  playbackGeneration: 0,

  setGenome: (genome) => set({ genome }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),

  beginCommandTrace: (stimulus) => {
    const generation = get().playbackGeneration + 1;
    set({
      playbackGeneration: generation,
      activeCommand: stimulus,
      signalActive: true,
      activeGeneIds: new Set(),
    });
    return generation;
  },

  applyEvent: (event, generation) =>
    set((state) => {
      if (generation !== state.playbackGeneration) return state;

      const activeGeneIds = new Set(state.activeGeneIds);
      if (event.source) activeGeneIds.add(event.source);
      if (event.target) activeGeneIds.add(event.target);

      return { logs: [...state.logs, toLogEntry(event)], activeGeneIds };
    }),

  clearSignal: () => set({ signalActive: false }),
}));
