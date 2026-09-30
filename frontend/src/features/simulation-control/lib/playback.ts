import { MOVEMENT_ANIMATION_MS } from "@/features/connectome-viewer/lib/movement-pose";
import { useSimulationStore } from "@/store/simulation-store";
import type { Direction, SimulationEvent } from "@/types/connectome";

/**
 * The backend computes an entire command's event trace (command -> synapse
 * spikes -> muscle activation -> movement) in one HH simulation run and sends
 * it back as a single WebSocket message. Applying all of it at once made the
 * whole cascade flash by instantly, which defeats the point — the user wants
 * to actually watch which neuron fires, where the signal goes, and where it
 * turns into movement. So instead of applying the array immediately, this
 * spreads it across one ~10s real-time sequence: a lead-in so the command
 * registers, the in-between synapse/muscle events spaced evenly across the
 * middle, then the movement event (and its body-animation tail) landing
 * right at the 10s mark.
 */
const TOTAL_SEQUENCE_MS = 10000;
const LEAD_IN_MS = 500;
const TAIL_MS = MOVEMENT_ANIMATION_MS + 300;
const WINDOW_END_MS = TOTAL_SEQUENCE_MS - TAIL_MS;

export function schedulePlayback(direction: Direction, events: SimulationEvent[]): void {
  const generation = useSimulationStore.getState().beginCommandTrace(direction);
  if (events.length === 0) return;

  const sorted = [...events].sort((a, b) => a.t_ms - b.t_ms);

  const schedule = (event: SimulationEvent, delayMs: number) => {
    window.setTimeout(() => {
      useSimulationStore.getState().applyEvent(event, generation);
    }, delayMs);
  };

  if (sorted.length === 1) {
    schedule(sorted[0], 0);
    return;
  }

  const commandEvent = sorted[0];
  const movementEvent = sorted[sorted.length - 1];
  const middle = sorted.slice(1, -1);

  schedule(commandEvent, 0);

  middle.forEach((event, i) => {
    const t =
      middle.length === 1
        ? (LEAD_IN_MS + WINDOW_END_MS) / 2
        : LEAD_IN_MS + (i / (middle.length - 1)) * (WINDOW_END_MS - LEAD_IN_MS);
    schedule(event, t);
  });

  // A trivial trace (e.g. STOP: just command -> movement) doesn't need to
  // stretch out to fill the full 10s — only rich cascades do.
  const movementDelay = middle.length === 0 ? Math.min(1800, WINDOW_END_MS) : WINDOW_END_MS + 150;
  schedule(movementEvent, movementDelay);

  window.setTimeout(
    () => {
      if (useSimulationStore.getState().playbackGeneration === generation) {
        useSimulationStore.getState().clearSignal();
      }
    },
    movementDelay + MOVEMENT_ANIMATION_MS + 200,
  );
}
