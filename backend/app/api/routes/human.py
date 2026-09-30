"""Human (v3) API routes — three separate real datasets (see
app/data/sources/human/SOURCES.md): a macro-scale brain-region network, a
real micro-scale EM neuron sample, and a nervous-system gene map. Kept in
their own route namespace (/api/human/...) same as Drosophila's /api/fly/...,
so no species/dataset ever needs to guess which shape of data it's getting.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.api.ws_manager import human_manager
from app.data.human_data import get_genome, get_macro_connectome, get_micro_sample
from app.domain.schemas import (
    GenomeCommandRequest,
    GenomeCommandResponse,
    HumanChatRequest,
    HumanChatResponse,
    HumanGenome,
    MacroConnectome,
    MicroConnectomeSample,
)
from app.simulation import human_chat_engine, human_genome_engine

router = APIRouter(tags=["human"])


@router.get("/api/human/connectome/macro", response_model=MacroConnectome)
def read_macro_connectome() -> MacroConnectome:
    return get_macro_connectome()


@router.get("/api/human/connectome/micro", response_model=MicroConnectomeSample)
def read_micro_sample() -> MicroConnectomeSample:
    return get_micro_sample()


@router.get("/api/human/genome", response_model=HumanGenome)
def read_genome() -> HumanGenome:
    return get_genome()


@router.post("/api/human/genome/pathway/command", response_model=GenomeCommandResponse)
async def send_genome_command(request: GenomeCommandRequest) -> GenomeCommandResponse:
    events = human_genome_engine.build_trace(request.stimulus)
    await human_manager.broadcast_events(request.stimulus.value, events)
    return GenomeCommandResponse(stimulus=request.stimulus, events=events)


@router.websocket("/ws/human/genome/pathway")
async def genome_pathway_socket(websocket: WebSocket) -> None:
    await human_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        human_manager.disconnect(websocket)


@router.post("/api/human/chat", response_model=HumanChatResponse)
async def send_human_chat_message(request: HumanChatRequest) -> HumanChatResponse:
    # Synchronous OpenAI SDK call -- off the event loop, same reasoning as
    # hh_model's Brian2 runs (see app/api/routes/simulation.py).
    return await run_in_threadpool(human_chat_engine.answer_human_chat, request)
