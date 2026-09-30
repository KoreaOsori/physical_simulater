import { WS_URL } from "@/shared/lib/env";
import type { FlySimulationSocketMessage, SimulationSocketMessage } from "@/types/connectome";
import type { GenomeSocketMessage } from "@/types/human";

export type ConnectionStatus = "connecting" | "open" | "closed";

interface SimulationSocketHandlers<TMessage> {
  onMessage: (message: TMessage) => void;
  onStatusChange: (status: ConnectionStatus) => void;
}

function openSocket<TMessage>(path: string, { onMessage, onStatusChange }: SimulationSocketHandlers<TMessage>): () => void {
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  const connect = () => {
    if (stopped) return;
    onStatusChange("connecting");
    socket = new WebSocket(`${WS_URL}${path}`);

    socket.onopen = () => onStatusChange("open");

    socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data) as TMessage);
      } catch {
        // Ignore malformed frames rather than crashing the socket handler.
      }
    };

    socket.onclose = () => {
      onStatusChange("closed");
      if (!stopped) reconnectTimer = setTimeout(connect, 2000);
    };

    socket.onerror = () => socket?.close();
  };

  connect();

  return () => {
    stopped = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    socket?.close();
  };
}

/** Opens the C. elegans simulation WebSocket and auto-reconnects with a fixed backoff while mounted. */
export function openSimulationSocket(handlers: SimulationSocketHandlers<SimulationSocketMessage>): () => void {
  return openSocket("/ws/simulation", handlers);
}

/** Same as openSimulationSocket, for the Drosophila v2 (/fly) page. */
export function openFlySimulationSocket(handlers: SimulationSocketHandlers<FlySimulationSocketMessage>): () => void {
  return openSocket("/ws/fly/simulation", handlers);
}

/** Same as openSimulationSocket, for the human genome pathway demo. */
export function openGenomePathwaySocket(handlers: SimulationSocketHandlers<GenomeSocketMessage>): () => void {
  return openSocket("/ws/human/genome/pathway", handlers);
}
