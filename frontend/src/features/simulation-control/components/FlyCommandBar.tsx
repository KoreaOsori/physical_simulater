"use client";

import { useCallback } from "react";

import { FLY_CIRCUITS, type FlyCircuit } from "@/features/lab-shell/lib/fly-circuits";
import { postFlyCommand } from "@/shared/lib/api-client";
import { useFlySimulationStore } from "@/store/fly-simulation-store";
import type { FlyStimulus } from "@/types/connectome";

interface FlyCommandBarProps {
  circuit: FlyCircuit;
}

/** Neither odor nor visual commands have a natural keyboard mapping the way
 * the worm's forward/reverse/left/right arrow keys do (see
 * simulation-control/components/SequenceStatusBar.tsx's note on why that page
 * has no on-screen direction pad), so buttons are the primary control here —
 * not a redundant duplicate of some other input. Button list/labels come
 * from fly-circuits.ts, one circuit's worth at a time now that each circuit
 * has its own page. */
export function FlyCommandBar({ circuit }: FlyCommandBarProps) {
  const activeCommand = useFlySimulationStore((s) => s.activeCommand);
  const signalActive = useFlySimulationStore((s) => s.signalActive);
  const config = FLY_CIRCUITS[circuit];

  const send = useCallback((stimulus: FlyStimulus) => {
    postFlyCommand(stimulus).catch((error: unknown) => console.error("Failed to send fly command", error));
  }, []);

  return (
    <footer className="control-deck">
      <div className="sequence">
        <small>{config.stageLabel}</small>
        <strong>{activeCommand === null ? "대기 중" : `${activeCommand} 자극 시퀀스 실행`}</strong>
        <p>{config.pipelineDescription}</p>
      </div>
      <div className="odor-buttons">
        {config.buttons.map(({ stimulus, label }) => (
          <button
            key={stimulus}
            type="button"
            disabled={signalActive}
            onClick={() => send(stimulus)}
            className={activeCommand === stimulus && signalActive ? "lit" : undefined}
          >
            {label}
          </button>
        ))}
      </div>
    </footer>
  );
}
