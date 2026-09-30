"""Drosophila v2 (hemibrain multi-circuit) API routes — mirrors
app/api/routes/connectome.py + simulation.py's role for the C. elegans v1
routes, kept in a separate route namespace (/api/fly/...) rather than a
species query param so both species can be loaded/queried independently (see
app/core/config.py).

The dataset itself stays one merged file (so real cross-circuit synapses,
see SOURCES.md, aren't lost), but the frontend now renders one circuit per
page rather than a shared scene — `circuit` here filters the connectome
response to just that circuit's own neurons/synapses so each page's payload
and render cost stay flat as more circuit subsets get added later, instead
of growing with the merged total.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.api.ws_manager import fly_manager
from app.core.config import get_settings
from app.data.drosophila_connectome import get_connectome, get_connectome_for_circuit
from app.domain.schemas import CircuitName, Connectome, FlyCommandRequest, FlyCommandResponse, SimulationEvent
from app.simulation import fly_engine
from app.simulation import fly_hh_model

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fly"])


@router.get("/api/fly/connectome", response_model=Connectome)
def read_connectome(circuit: CircuitName | None = None) -> Connectome:
    if circuit is not None:
        return get_connectome_for_circuit(circuit)
    return get_connectome()


async def _compute_trace(request: FlyCommandRequest) -> list[SimulationEvent]:
    settings = get_settings()
    if settings.fly_simulation_engine == "hodgkin_huxley":
        try:
            # Network scale/cost documented in fly_hh_model.py — run off the
            # event loop like hh_model.py does.
            return await run_in_threadpool(fly_hh_model.run_hh_trace, request.stimulus)
        except Exception:
            logger.exception("Fly Hodgkin-Huxley simulation failed, falling back to rule-based engine")
    return fly_engine.build_trace(request.stimulus)


@router.post("/api/fly/simulation/command", response_model=FlyCommandResponse)
async def send_command(request: FlyCommandRequest) -> FlyCommandResponse:
    events = await _compute_trace(request)
    await fly_manager.broadcast_events(request.stimulus.value, events)
    return FlyCommandResponse(stimulus=request.stimulus, events=events)


@router.websocket("/ws/fly/simulation")
async def simulation_socket(websocket: WebSocket) -> None:
    await fly_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        fly_manager.disconnect(websocket)
