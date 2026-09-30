import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.api.ws_manager import manager
from app.core.config import get_settings
from app.domain.schemas import CommandRequest, CommandResponse, SimulationEvent
from app.simulation import engine
from app.simulation import hh_model

logger = logging.getLogger(__name__)

router = APIRouter(tags=["simulation"])


async def _compute_trace(request: CommandRequest) -> list[SimulationEvent]:
    settings = get_settings()
    if settings.simulation_engine == "hodgkin_huxley":
        try:
            # Brian2's simulation is synchronous/CPU-bound (~2-3s at 302
            # neurons); run it off the event loop so it doesn't block other
            # requests and WebSocket connections while it runs.
            silenced = frozenset(request.silenced_neuron_ids) if request.silenced_neuron_ids else None
            return await run_in_threadpool(hh_model.run_hh_trace, request.direction, 20, 8, silenced)
        except Exception:
            logger.exception("Hodgkin-Huxley simulation failed, falling back to rule-based engine")
    return engine.build_trace(request.direction)


@router.post("/api/simulation/command", response_model=CommandResponse)
async def send_command(request: CommandRequest) -> CommandResponse:
    events = await _compute_trace(request)
    # Read-only lookup (see hh_model.get_habituation_level) -- 0.0 whenever
    # the rule-based fallback ran instead (that path never records
    # stimulation, so the state for this direction stays empty).
    habituation_level = hh_model.get_habituation_level(request.direction)
    await manager.broadcast_events(request.direction.value, events, habituation_level=habituation_level)
    return CommandResponse(direction=request.direction, events=events, habituation_level=habituation_level)


@router.websocket("/ws/simulation")
async def simulation_socket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Frontend does not need to send anything; keep the connection open
            # and drain any client messages (e.g. pings) without acting on them.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
