"""Tracks active simulation WebSocket connections and broadcasts events to them."""

from __future__ import annotations

from fastapi import WebSocket

from app.domain.schemas import SimulationEvent


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast_events(
        self, direction: str, events: list[SimulationEvent], habituation_level: float | None = None
    ) -> None:
        payload: dict[str, object] = {
            "direction": direction,
            "events": [event.model_dump(mode="json") for event in events],
        }
        if habituation_level is not None:
            # Optional: only the worm's /ws/simulation clients send this
            # (see docs/29-worm-habituation-plasticity.md) -- fly/human
            # callers never pass it, so their payload shape is unchanged.
            payload["habituation_level"] = habituation_level
        stale: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()
# Separate connection pool for the Drosophila v2 page (/fly), so its
# broadcasts never reach C. elegans (/) clients and vice versa.
fly_manager = ConnectionManager()
# Separate pool for the human genome pathway demo (/human/genome), same
# isolation reasoning as fly_manager.
human_manager = ConnectionManager()
