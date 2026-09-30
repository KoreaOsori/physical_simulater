"""시뮬레이션 가상 실험실 (docs/35). 이미 있는 웜 HH 시뮬레이션 엔진
(hh_model.run_hh_trace_isolated)을 재사용해, 실제 302개 뉴런 중 어떤
조합이든 자유롭게 억제해보고 진짜 시뮬레이션 결과를 관찰할 수 있게
한다 -- 문헌으로 검증된 7개 고전 절제 연구로 제한된 AblationPanel과
달리, 아직 아무도 시도해본 적 없는 조합도 실험해볼 수 있다.

기존 `POST /api/simulation/command`와 의도적으로 분리됐다 -- 그
엔드포인트는 실제 웜 페이지가 열려 있으면 WS로 그 페이지의 3D
애니메이션까지 함께 트리거하는데, "가상 실험"이 실제 페이지의 상태에
영향을 주면 안 되기 때문(이 프로젝트의 "기존 기능은 그대로 둔다" 원칙).
습관화 상태도 `run_hh_trace_isolated`로 격리 -- 가상 실험은 실제
페이지의 습관화 수준에 흔적을 남기지 않는다."""

from __future__ import annotations

from app.data.celegans_connectome import get_connectome
from app.domain.schemas import Direction, SimulationEvent
from app.lab.schemas import VirtualExperimentResponse
from app.simulation import hh_model

_HONESTY_NOTE = (
    "이 결과는 실제 생물학적 관찰이 아니라 이 프로젝트의 시뮬레이션(Hodgkin-Huxley 모델) 결과입니다. "
    "억제한 뉴런 조합이 실제 문헌으로 검증된 적 없을 수 있습니다 -- 가설을 만들어보는 도구입니다."
)


def _fired_source_ids(events: list[SimulationEvent]) -> list[str]:
    seen: list[str] = []
    seen_set: set[str] = set()
    for e in events:
        if e.source and e.source not in seen_set:
            seen.append(e.source)
            seen_set.add(e.source)
    return seen


def run_virtual_experiment(direction: Direction, silenced_neuron_ids: list[str]) -> VirtualExperimentResponse:
    real_neuron_ids = {n.id for n in get_connectome().neurons}
    # 존재하지 않는 id는 조용히 무시 -- 지어내지 않는다.
    valid_silenced = frozenset(nid for nid in silenced_neuron_ids if nid in real_neuron_ids)

    baseline_events = hh_model.run_hh_trace_isolated(direction, silenced_neuron_ids=None)
    experiment_events = hh_model.run_hh_trace_isolated(direction, silenced_neuron_ids=valid_silenced or None)

    baseline_fired = _fired_source_ids(baseline_events)
    experiment_fired = _fired_source_ids(experiment_events)
    silenced_but_would_have_fired = [nid for nid in valid_silenced if nid in baseline_fired]

    return VirtualExperimentResponse(
        direction=direction,
        silenced_neuron_ids=sorted(valid_silenced),
        experiment_events=experiment_events,
        baseline_events=baseline_events,
        experiment_neurons_fired=experiment_fired,
        baseline_neurons_fired=baseline_fired,
        silenced_but_would_have_fired=silenced_but_would_have_fired,
        honesty_note=_HONESTY_NOTE,
    )
