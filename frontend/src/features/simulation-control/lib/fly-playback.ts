import { useFlySimulationStore } from "@/store/fly-simulation-store";
import type { FlyStimulus, SimulationEvent } from "@/types/connectome";

/** Same idea as simulation-control/lib/playback.ts for the C. elegans page:
 * spreads one command's whole event trace across a ~4s real-time sequence
 * instead of applying it all at once, so the PN -> KC -> MBON cascade is
 * actually watchable. Shorter than the worm's 10s window since there's no
 * body animation tail to land on. */
const TOTAL_SEQUENCE_MS = 4000;
const LEAD_IN_MS = 300;
const WINDOW_END_MS = TOTAL_SEQUENCE_MS - 400;

export function scheduleFlyPlayback(stimulus: FlyStimulus, events: SimulationEvent[]): void {
  const generation = useFlySimulationStore.getState().beginCommandTrace(stimulus);
  if (events.length === 0) return;

  const sorted = [...events].sort((a, b) => a.t_ms - b.t_ms);

  const schedule = (event: SimulationEvent, delayMs: number) => {
    window.setTimeout(() => {
      useFlySimulationStore.getState().applyEvent(event, generation);
    }, delayMs);
  };

  if (sorted.length === 1) {
    schedule(sorted[0], 0);
    return;
  }

  const commandEvent = sorted[0];
  const lastEvent = sorted[sorted.length - 1];
  const middle = sorted.slice(1, -1);

  schedule(commandEvent, 0);
  middle.forEach((event, i) => {
    const t = middle.length === 1 ? (LEAD_IN_MS + WINDOW_END_MS) / 2 : LEAD_IN_MS + (i / (middle.length - 1)) * (WINDOW_END_MS - LEAD_IN_MS);
    schedule(event, t);
  });
  const lastDelay = middle.length === 0 ? Math.min(1200, WINDOW_END_MS) : WINDOW_END_MS + 150;
  schedule(lastEvent, lastDelay);

  window.setTimeout(() => {
    if (useFlySimulationStore.getState().playbackGeneration === generation) {
      useFlySimulationStore.getState().clearSignal();
    }
  }, lastDelay + 400);
}
