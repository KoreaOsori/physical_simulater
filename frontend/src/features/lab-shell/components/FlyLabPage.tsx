"use client";

import { useEffect } from "react";

import { FlyConnectomeViewport } from "@/features/connectome-viewer/components/FlyConnectomeViewport";
import { FlyEventLog } from "@/features/event-log/components/FlyEventLog";
import { FlyTopBar } from "@/features/lab-shell/components/FlyTopBar";
import type { FlyCircuit } from "@/features/lab-shell/lib/fly-circuits";
import { scheduleFlyPlayback } from "@/features/simulation-control/lib/fly-playback";
import { FlyCommandBar } from "@/features/simulation-control/components/FlyCommandBar";
import { fetchFlyConnectome } from "@/shared/lib/api-client";
import { openFlySimulationSocket } from "@/shared/lib/ws-client";
import { useFlySimulationStore } from "@/store/fly-simulation-store";

interface FlyLabPageProps {
  circuit: FlyCircuit;
}

/** Renders one circuit's page (`/fly/olfactory` or `/fly/visual`) — see
 * fly-circuits.ts for why these are separate routes rather than one shared
 * page. The WebSocket connection is still the single shared `/ws/fly/simulation`
 * channel (mirrors the shared HTTP connectome endpoint's `circuit` filter
 * design less strictly): a command sent from the *other* circuit's page will
 * still arrive here and get logged, since this is a local single-user tool
 * where that cross-talk is harmless, not a multi-tenant one. */
export function FlyLabPage({ circuit }: FlyLabPageProps) {
  const setConnectome = useFlySimulationStore((s) => s.setConnectome);
  const setConnectionStatus = useFlySimulationStore((s) => s.setConnectionStatus);

  useEffect(() => {
    fetchFlyConnectome(circuit)
      .then(setConnectome)
      .catch((error: unknown) => console.error("Failed to load fly connectome", error));

    const close = openFlySimulationSocket({
      onMessage: (message) => scheduleFlyPlayback(message.direction, message.events),
      onStatusChange: setConnectionStatus,
    });
    return close;
  }, [circuit, setConnectome, setConnectionStatus]);

  return (
    <main className="lab-shell">
      <FlyTopBar circuit={circuit} />
      <section className="workspace-fly">
        <FlyConnectomeViewport circuit={circuit} />
        <FlyEventLog />
      </section>
      <FlyCommandBar circuit={circuit} />
    </main>
  );
}
