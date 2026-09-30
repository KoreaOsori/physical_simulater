"""Command -> neural event trace generation.

STATUS: rule-based placeholder, but every neuron id / synapse / neurotransmitter
referenced below is real and verified against the imported connectome
(`app/data/celegans_connectome.json` — see `app/data/sources/SOURCES.md`), not
invented. What's still illustrative is the *staging* (command -> synapse ->
muscle -> movement, each with a fixed offset) and the fact that a whole
command triggers a single hand-picked synapse rather than a simulated wave of
activity across the network. That's the seam `hh_model.py` plugs into: once
it can simulate real membrane potentials, `build_trace` should derive its
timings/messages from simulated spike times instead of this fixed table.

Where a synapse's neurotransmitter shows as `unknown`, that's not a bug —
several major command interneurons (AVA, AVB, ASI) don't have a curated
neurotransmitter in the source data (`owmeta`), so we report that honestly
rather than guessing.
"""

from __future__ import annotations

from app.domain.schemas import Direction, Neurotransmitter, SimulationEvent, SimulationStage

_DIRECTION_LABELS: dict[Direction, str] = {
    Direction.FORWARD: "전진",
    Direction.LEFT: "좌회전",
    Direction.STOP: "정지",
    Direction.RIGHT: "우회전",
    Direction.REVERSE: "후진",
    Direction.FEED: "섭식",
    Direction.DEFECATE: "배설",
    Direction.REPRODUCE: "번식 행동",
}


class Pathway:
    """A single verified pre -> post synapse used to narrate one command,
    plus the human-readable muscle-stage description that follows it."""

    __slots__ = ("pre", "post", "neurotransmitter", "muscle_message")

    def __init__(self, pre: str, post: str, neurotransmitter: Neurotransmitter, muscle_message: str) -> None:
        self.pre = pre
        self.post = post
        self.neurotransmitter = neurotransmitter
        self.muscle_message = muscle_message


# Verified against celegans_connectome.json (see build_connectome_dataset.py).
_PATHWAYS: dict[Direction, Pathway] = {
    Direction.FORWARD: Pathway("AVBL", "VB2", Neurotransmitter.UNKNOWN, "체벽 근육의 전진 파형이 적용되었습니다."),
    Direction.REVERSE: Pathway("AVAL", "VA1", Neurotransmitter.UNKNOWN, "체벽 근육의 후진 파형이 적용되었습니다."),
    Direction.LEFT: Pathway("AVBL", "VB1", Neurotransmitter.ELECTRICAL, "좌측 체벽 근육 수축이 강화되었습니다."),
    Direction.RIGHT: Pathway("AVBR", "VB2", Neurotransmitter.ELECTRICAL, "우측 체벽 근육 수축이 강화되었습니다."),
    Direction.FEED: Pathway("ASIL", "AIBL", Neurotransmitter.UNKNOWN, "인두 근육(pm)의 펌핑 패턴이 시작되었습니다."),
    Direction.DEFECATE: Pathway("AVL", "DVB", Neurotransmitter.GABA, "장-항문 근육의 리듬성 수축이 시작되었습니다."),
    Direction.REPRODUCE: Pathway("HSNL", "vm2aL", Neurotransmitter.SEROTONIN, "외음부 근육(vm2)의 수축이 시작되었습니다."),
}

_NT_LABELS: dict[Neurotransmitter, str] = {
    Neurotransmitter.ACETYLCHOLINE: "아세틸콜린",
    Neurotransmitter.GABA: "GABA",
    Neurotransmitter.GLUTAMATE: "글루탐산",
    Neurotransmitter.DOPAMINE: "도파민",
    Neurotransmitter.SEROTONIN: "세로토닌",
    Neurotransmitter.OCTOPAMINE: "옥토파민",
    Neurotransmitter.TYRAMINE: "티라민",
    Neurotransmitter.ELECTRICAL: "전기 시냅스(gap junction)",
    Neurotransmitter.UNKNOWN: "미확인 신경전달물질",
}


def build_trace(direction: Direction) -> list[SimulationEvent]:
    label = _DIRECTION_LABELS[direction]
    events = [
        SimulationEvent(
            t_ms=0,
            stage=SimulationStage.COMMAND,
            message=f"'{label}' 명령이 감각-운동 회로에 입력되었습니다.",
        )
    ]

    pathway = _PATHWAYS.get(direction)
    if pathway is not None:
        nt_label = _NT_LABELS[pathway.neurotransmitter]
        events.append(
            SimulationEvent(
                t_ms=12.4,
                stage=SimulationStage.SYNAPSE,
                source=pathway.pre,
                target=pathway.post,
                neurotransmitter=pathway.neurotransmitter,
                message=f"{pathway.pre} -> {pathway.post}: {nt_label} 경로가 활성화되었습니다.",
            )
        )
        events.append(
            SimulationEvent(t_ms=28.1, stage=SimulationStage.MUSCLE, message=pathway.muscle_message)
        )
    else:
        # STOP: cessation of the forward/backward command circuit, not a new
        # synapse firing, so there is no synapse/muscle stage to report.
        pass

    events.append(
        SimulationEvent(
            t_ms=45.0,
            stage=SimulationStage.MOVEMENT,
            message=f"{label} 운동이 발현되었습니다.",
        )
    )
    return events
