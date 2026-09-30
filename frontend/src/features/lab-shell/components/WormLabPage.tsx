"use client";

import { useEffect } from "react";

import { ConnectomeViewport } from "@/features/connectome-viewer/components/ConnectomeViewport";
import { EventLog } from "@/features/event-log/components/EventLog";
import { TopBar } from "@/features/lab-shell/components/TopBar";
import { schedulePlayback } from "@/features/simulation-control/lib/playback";
import { SequenceStatusBar } from "@/features/simulation-control/components/SequenceStatusBar";
import { TissuePanel } from "@/features/tissue-panel/components/TissuePanel";
import { fetchConnectome } from "@/shared/lib/api-client";
import { openSimulationSocket } from "@/shared/lib/ws-client";
import { useSimulationStore } from "@/store/simulation-store";

export function WormLabPage() {
  const setConnectome = useSimulationStore((s) => s.setConnectome);
  const setConnectionStatus = useSimulationStore((s) => s.setConnectionStatus);
  const setHabituationLevel = useSimulationStore((s) => s.setHabituationLevel);

  useEffect(() => {
    fetchConnectome()
      .then(setConnectome)
      .catch((error: unknown) => console.error("Failed to load connectome", error));

    // schedulePlayback reads the store itself (useSimulationStore.getState()),
    // so it doesn't need to be an effect dependency — each command's ~10s
    // playback is scheduled independently of this socket's lifecycle.
    const close = openSimulationSocket({
      onMessage: (message) => {
        schedulePlayback(message.direction, message.events);
        // Known immediately (unlike the staggered event trace), so set it
        // right away rather than threading it through schedulePlayback.
        setHabituationLevel(message.habituation_level ?? 0);
      },
      onStatusChange: setConnectionStatus,
    });
    return close;
  }, [setConnectome, setConnectionStatus, setHabituationLevel]);

  return (
    <main className="lab-shell">
      <TopBar />
      <section className="workspace">
        <TissuePanel />
        <ConnectomeViewport />
        <EventLog />
      </section>
      <SequenceStatusBar />
    </main>
  );
}
