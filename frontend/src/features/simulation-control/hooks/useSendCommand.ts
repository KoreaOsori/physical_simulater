"use client";

import { useCallback } from "react";

import { postCommand } from "@/shared/lib/api-client";
import { useSimulationStore } from "@/store/simulation-store";
import type { Direction } from "@/types/connectome";

/**
 * Fire-and-forget command dispatch: the resulting event trace comes back over
 * the simulation WebSocket (see app/page.tsx), not this call's HTTP response,
 * so every connected view — not just the sender — stays in sync.
 *
 * If a classic ablation is currently toggled on (AblationPanel.tsx), its
 * neuron_ids ride along as `silenced_neuron_ids` on every command sent this
 * way — including the normal ArrowUp/Down/etc. keyboard controls, not just a
 * dedicated button — so comparing "normal" vs "ablated" is just toggling the
 * ablation on/off and pressing the same key.
 */
export function useSendCommand() {
  return useCallback((direction: Direction) => {
    const activeAblation = useSimulationStore.getState().activeAblation;
    postCommand(direction, activeAblation?.neuron_ids).catch((error: unknown) => {
      console.error("Failed to send simulation command", error);
    });
  }, []);
}
