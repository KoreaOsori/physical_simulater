"""연구소(Lab) 라우트 (docs/34+) -- app/lab/의 탐구적 기능을 노출한다. 나머지
route 모듈(connectome/fly/human)과 물리적으로 나란히 두되, 응답 스키마는
`app/lab/schemas.py`로 분리해 "확정 데이터" API와 "가설 생성 도구" API를
계속 구분되게 유지한다."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.lab.explore_chat import answer_explore_chat
from app.lab.gene_hypothesis import build_gene_pathway_candidates
from app.lab.hypothesis_notebook import build_hypothesis_notebook
from app.lab.schemas import (
    ExploreChatRequest,
    ExploreChatResponse,
    GenePathwayReportOut,
    HypothesisRecordOut,
    TopologyReportOut,
    VirtualExperimentRequest,
    VirtualExperimentResponse,
    VirtualFlyStateOut,
    VirtualFlyStepRequest,
    VirtualFlyStepResponse,
    VirtualOrganismPoseIn,
    VirtualOrganismSourceIn,
    VirtualWormStateOut,
    VirtualWormStepRequest,
    VirtualWormStepResponse,
)
from app.lab.species_topology import list_species_ids
from app.lab.virtual_common import StaleRunError
from app.lab.species_topology import get_topology_report as _get_topology_report
from app.lab.virtual_experiment import run_virtual_experiment
from app.lab.virtual_fly import (
    get_virtual_fly_state,
    reset_virtual_fly,
    set_virtual_fly_pose,
    set_virtual_fly_source,
    step_virtual_fly,
)
from app.lab.virtual_worm import (
    get_virtual_worm_state,
    reset_virtual_worm,
    set_virtual_worm_pose,
    set_virtual_worm_source,
    step_virtual_worm,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lab", tags=["lab"])


@router.get("/topology/species", response_model=list[str])
def read_topology_species() -> list[str]:
    return list_species_ids()


@router.get("/topology/{species_id}", response_model=TopologyReportOut)
async def read_topology_report(species_id: str) -> TopologyReportOut:
    if species_id not in list_species_ids():
        raise HTTPException(status_code=404, detail=f"unknown species_id: {species_id}")
    # Off the event loop -- the first call per species can take real tens of
    # seconds (fly circuits especially); cached after that (see
    # species_topology.get_topology_report's @lru_cache).
    return await run_in_threadpool(_get_topology_report, species_id)


@router.post("/virtual-experiment/worm", response_model=VirtualExperimentResponse)
async def post_worm_virtual_experiment(request: VirtualExperimentRequest) -> VirtualExperimentResponse:
    # Off the event loop -- two real Brian2 runs (baseline + experiment),
    # ~2-3s each. Deliberately its own endpoint, not a variant of
    # /api/simulation/command -- see virtual_experiment.py's module
    # docstring for why (must not touch the real worm page's WS broadcast
    # or shared habituation state).
    #
    # 실제 버그(docs/38): /api/simulation/command과 달리 이 경로는
    # Brian2 실패 시 규칙 기반 엔진으로 폴백하지 않는다(의도적 -- 규칙
    # 엔진은 silenced_neuron_ids를 아예 모르므로, 조용히 폴백하면 사용자가
    # 고른 조합을 무시한 채 "실험 결과인 척"하는 답을 내는 셈이라 더
    # 부정직함). 그런데 예외 처리 자체가 아예 없어서 Brian2가 실패하면
    # 가공되지 않은 500 트레이스백이 그대로 나갔다 -- 명확한 503으로
    # 바꿈.
    try:
        return await run_in_threadpool(run_virtual_experiment, request.direction, request.silenced_neuron_ids)
    except Exception:
        logger.exception("Lab virtual experiment failed")
        raise HTTPException(status_code=503, detail="시뮬레이션을 실행하지 못했습니다 — 잠시 후 다시 시도해주세요.")


@router.post("/explore-chat", response_model=ExploreChatResponse)
async def post_explore_chat(request: ExploreChatRequest) -> ExploreChatResponse:
    # Off the event loop -- same reasoning as human_chat_engine.py's OpenAI
    # call, plus this one can also make a real web request via the
    # web_search tool.
    return await run_in_threadpool(answer_explore_chat, request.message)


@router.get("/gene-pathway-candidates", response_model=list[GenePathwayReportOut])
def read_gene_pathway_candidates() -> list[GenePathwayReportOut]:
    return build_gene_pathway_candidates()


@router.get("/hypotheses", response_model=list[HypothesisRecordOut])
async def read_hypothesis_notebook() -> list[HypothesisRecordOut]:
    # Off the event loop -- H1 recomputes a real networkx graph analysis
    # each call (cheap, ~1s, human macro is only 400 nodes) even though the
    # other 3 are static records.
    return await run_in_threadpool(build_hypothesis_notebook)


@router.post("/virtual-worm/reset", response_model=VirtualWormStateOut)
async def post_virtual_worm_reset() -> VirtualWormStateOut:
    # Off the event loop -- builds a brand-new independent Brian2 network
    # (app/lab/virtual_worm.py's own _NetworkAssets, not the shared
    # run_hh_trace singleton), ~same cost as the first command in a session.
    try:
        return await run_in_threadpool(reset_virtual_worm)
    except Exception:
        logger.exception("Virtual worm reset failed")
        raise HTTPException(status_code=503, detail="가상 웜 환경을 초기화하지 못했습니다 — 잠시 후 다시 시도해주세요.")


@router.get("/virtual-worm/state", response_model=VirtualWormStateOut)
async def read_virtual_worm_state() -> VirtualWormStateOut:
    # 아직 reset된 적 없으면 이 호출이 첫 상태를 만든다(자동 초기화) --
    # 프론트가 페이지를 열자마자 별도 reset 호출 없이도 볼 것이 있게.
    try:
        return await run_in_threadpool(get_virtual_worm_state)
    except Exception:
        logger.exception("Virtual worm state read failed")
        raise HTTPException(status_code=503, detail="가상 웜 환경 상태를 불러오지 못했습니다 — 잠시 후 다시 시도해주세요.")


@router.post("/virtual-worm/step", response_model=VirtualWormStepResponse)
async def post_virtual_worm_step(request: VirtualWormStepRequest) -> VirtualWormStepResponse:
    # Off the event loop -- n_ticks real Brian2 runs (~100ms 생물학적 시간씩)
    # on this feature's own independent network. 막전위는 매 틱
    # restore("initial")로 재초기화되고(연속 시뮬레이션이 영구 고착
    # 상태에 빠지는 실제 버그를 이렇게 고쳤다 -- docs/41), 위치/궤적 같은
    # 환경 상태만 파이썬 쪽에서 이어진다.
    try:
        return await run_in_threadpool(step_virtual_worm, request.n_ticks, request.manual)
    except StaleRunError:
        raise HTTPException(status_code=409, detail="다시 시작 이전 기록의 위치입니다 — 현재 기록에서 다시 조종하세요.")
    except Exception:
        logger.exception("Virtual worm step failed")
        raise HTTPException(status_code=503, detail="가상 웜 시뮬레이션을 진행하지 못했습니다 — 잠시 후 다시 시도해주세요.")


@router.post("/virtual-fly/reset", response_model=VirtualFlyStateOut)
async def post_virtual_fly_reset() -> VirtualFlyStateOut:
    # Off the event loop -- builds a brand-new independent Brian2 network
    # over the ~2,452-neuron olfactory circuit (app/lab/virtual_fly.py's own
    # _NetworkAssets, not the shared fly_hh_model run_hh_trace singleton).
    try:
        return await run_in_threadpool(reset_virtual_fly)
    except Exception:
        logger.exception("Virtual fly reset failed")
        raise HTTPException(status_code=503, detail="가상 초파리 환경을 초기화하지 못했습니다 — 잠시 후 다시 시도해주세요.")


@router.get("/virtual-fly/state", response_model=VirtualFlyStateOut)
async def read_virtual_fly_state() -> VirtualFlyStateOut:
    try:
        return await run_in_threadpool(get_virtual_fly_state)
    except Exception:
        logger.exception("Virtual fly state read failed")
        raise HTTPException(status_code=503, detail="가상 초파리 환경 상태를 불러오지 못했습니다 — 잠시 후 다시 시도해주세요.")


@router.post("/virtual-fly/step", response_model=VirtualFlyStepResponse)
async def post_virtual_fly_step(request: VirtualFlyStepRequest) -> VirtualFlyStepResponse:
    # Off the event loop -- n_ticks real Brian2 runs on a ~2,452-neuron
    # network (slower per-tick than the worm's 302-neuron one, hence this
    # schema's lower n_ticks cap -- see VirtualFlyStepRequest).
    try:
        return await run_in_threadpool(step_virtual_fly, request.n_ticks, request.manual)
    except StaleRunError:
        raise HTTPException(status_code=409, detail="다시 시작 이전 기록의 위치입니다 — 현재 기록에서 다시 조종하세요.")
    except Exception:
        logger.exception("Virtual fly step failed")
        raise HTTPException(status_code=503, detail="가상 초파리 시뮬레이션을 진행하지 못했습니다 — 잠시 후 다시 시도해주세요.")


# docs/45 -- 냄새원 옮기기 / 수동 조종 위치 확정(신경 계산 없음, 즉시 응답).
@router.post("/virtual-worm/source", response_model=VirtualWormStateOut)
async def post_virtual_worm_source(request: VirtualOrganismSourceIn) -> VirtualWormStateOut:
    return await run_in_threadpool(set_virtual_worm_source, request.x_um, request.y_um)


@router.post("/virtual-worm/pose", response_model=VirtualWormStateOut)
async def post_virtual_worm_pose(request: VirtualOrganismPoseIn) -> VirtualWormStateOut:
    try:
        return await run_in_threadpool(set_virtual_worm_pose, request)
    except StaleRunError:
        raise HTTPException(status_code=409, detail="다시 시작 이전 기록의 위치입니다.")


@router.post("/virtual-fly/source", response_model=VirtualFlyStateOut)
async def post_virtual_fly_source(request: VirtualOrganismSourceIn) -> VirtualFlyStateOut:
    return await run_in_threadpool(set_virtual_fly_source, request.x_um, request.y_um)


@router.post("/virtual-fly/pose", response_model=VirtualFlyStateOut)
async def post_virtual_fly_pose(request: VirtualOrganismPoseIn) -> VirtualFlyStateOut:
    try:
        return await run_in_threadpool(set_virtual_fly_pose, request)
    except StaleRunError:
        raise HTTPException(status_code=409, detail="다시 시작 이전 기록의 위치입니다.")
