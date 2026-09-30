"""Stimulus command -> neural event trace generation for the Drosophila v2
subsets (mirrors app/simulation/engine.py's role for v1).

STATUS: rule-based placeholder, exactly like engine.py — every neuron id /
synapse below is real and verified against the imported hemibrain subsets
(`app/data/drosophila_connectome.json` — see
`app/data/sources/drosophila/SOURCES.md`). Three stimulus modalities share
this module:

- **Odor** (`OdorCommand`, phase 1): a verified two-hop PN->KC->MBON path —
  for each glomerulus, the single highest-weight real PN->KC edge, then the
  single highest-weight real KC->MBON edge out of that specific KC.
- **Visual** (`VisualCommand`, phase 2): a verified *one*-hop VPN->DN path —
  the single highest-weight real synapse from that VPN type onto any
  descending neuron (DN)/Giant Fiber.
- **Heading** (`HeadingCommand`, phase 4): a verified *one*-hop EPG->PFL path
  — the single highest-weight real synapse from that compass wedge's EPG
  neuron onto a PFL steering-output neuron.

Both one-hop cases are real hemibrain connectivity, not a literature claim —
see the analysis behind `_VISUAL_PATHWAYS`/`_NAV_PATHWAYS` below (both share
the generic `OneHopPathway` shape).

What's illustrative in all three cases is the *staging* (one hand-picked path
narrated with fixed timings) rather than a simulated cascade across the whole
network — that's what `fly_hh_model.py` does instead.

This subset has no muscle/effector layer (see SOURCES.md), so the
MUSCLE/MOVEMENT `SimulationStage` values are reused but reinterpreted:
MUSCLE narrates the circuit's output-layer response (MBON for odor, DN for
visual, PFL for heading), MOVEMENT narrates the resulting behavioral-valence/
escape/steering signal rather than a body movement.
"""

from __future__ import annotations

from app.domain.schemas import (
    FlyStimulus,
    HeadingCommand,
    Neurotransmitter,
    OdorCommand,
    SimulationEvent,
    SimulationStage,
    VisualCommand,
)

_ODOR_LABELS: dict[OdorCommand, str] = {
    OdorCommand.DA1: "DA1 (페로몬 cVA) 사구체 자극",
    OdorCommand.DL2D: "DL2d 사구체 자극",
    OdorCommand.VM5D: "VM5d 사구체 자극",
    OdorCommand.DA2: "DA2 사구체 자극",
}

_VISUAL_LABELS: dict[VisualCommand, str] = {
    VisualCommand.LC4: "LC4 (루밍/도피) 시각채널 자극",
    VisualCommand.LC6: "LC6 (루밍/도피) 시각채널 자극",
    VisualCommand.LPLC2: "LPLC2 (양안 루밍) 시각채널 자극",
    VisualCommand.LC9: "LC9 (소형 이동물체) 시각채널 자극",
}

_NAV_LABELS: dict[HeadingCommand, str] = {
    HeadingCommand.EPG_L4: "EPG L4 웨지 헤딩 자극",
    HeadingCommand.EPG_R4: "EPG R4 웨지 헤딩 자극",
    HeadingCommand.EPG_R6: "EPG R6 웨지 헤딩 자극",
    HeadingCommand.EPG_L2: "EPG L2 웨지 헤딩 자극",
}


class Pathway:
    """A verified two-hop pre(PN) -> mid(KC) -> post(MBON) path used to
    narrate one odor command."""

    __slots__ = ("pn", "kc", "mbon", "pn_kc_weight", "kc_mbon_weight")

    def __init__(self, pn: str, kc: str, mbon: str, pn_kc_weight: int, kc_mbon_weight: int) -> None:
        self.pn = pn
        self.kc = kc
        self.mbon = mbon
        self.pn_kc_weight = pn_kc_weight
        self.kc_mbon_weight = kc_mbon_weight


class OneHopPathway:
    """A verified one-hop pre -> post path used to narrate one visual or
    heading command (pre=VPN/post=DN for visual, pre=EPG/post=PFL for
    heading — generic since both are "one real direct synapse" pathways)."""

    __slots__ = ("pre", "post", "weight")

    def __init__(self, pre: str, post: str, weight: int) -> None:
        self.pre = pre
        self.post = post
        self.weight = weight


# Verified against drosophila_connectome.json (see build_drosophila_dataset.py) —
# for each glomerulus, the single highest-weight real PN->KC edge, then the
# single highest-weight real KC->MBON edge out of that specific KC.
_PATHWAYS: dict[OdorCommand, Pathway] = {
    OdorCommand.DA1: Pathway("754538881", "5813053885", "612371421", 32, 58),
    OdorCommand.DL2D: Pathway("5813024710", "632397750", "799586652", 53, 41),
    OdorCommand.VM5D: Pathway("1006258344", "5901198074", "799586652", 41, 35),
    OdorCommand.DA2: Pathway("1796817841", "5812982273", "799586652", 28, 35),
}

# Verified against drosophila_connectome.json — for each VPN type, the
# single highest-weight real direct synapse onto a DN/Giant Fiber neuron
# (found by scanning hemibrain v1.2's traced-total-connections.csv; see
# app/data/sources/drosophila/SOURCES.md's "시각 회로 서브셋" section).
_VISUAL_PATHWAYS: dict[VisualCommand, OneHopPathway] = {
    VisualCommand.LC4: OneHopPathway("1938544937", "1405231475", 98),  # LC4 -> DNp04
    VisualCommand.LC6: OneHopPathway("1198477582", "5813023322", 10),  # LC6 -> DNp06
    VisualCommand.LPLC2: OneHopPathway("1815826155", "2307027729", 36),  # LPLC2 -> Giant Fiber
    VisualCommand.LC9: OneHopPathway("1262990404", "1281324958", 18),  # LC9 -> DNp11
}

# Verified against drosophila_connectome.json — for each EPG compass wedge,
# the single highest-weight real direct synapse onto a PFL steering neuron
# (see app/data/sources/drosophila/SOURCES.md's "항법(나침반) 회로 서브셋"
# section).
_NAV_PATHWAYS: dict[HeadingCommand, OneHopPathway] = {
    HeadingCommand.EPG_L4: OneHopPathway("634962055", "850194651", 78),  # EPG(PB08)_L4 -> PFL2
    HeadingCommand.EPG_R4: OneHopPathway("416642425", "1167282562", 50),  # EPG(PB08)_R4 -> PFL2
    HeadingCommand.EPG_R6: OneHopPathway("942491983", "941132430", 48),  # EPG(PB08)_R6 -> PFL3
    HeadingCommand.EPG_L2: OneHopPathway("697001770", "481121605", 40),  # EPG(PB08)_L2 -> PFL1
}


def _build_odor_trace(odor: OdorCommand) -> list[SimulationEvent]:
    label = _ODOR_LABELS[odor]
    pathway = _PATHWAYS[odor]

    return [
        SimulationEvent(t_ms=0, stage=SimulationStage.COMMAND, message=f"'{label}' 냄새 자극이 촉각엽(antennal lobe)에 입력되었습니다."),
        SimulationEvent(
            t_ms=12.4,
            stage=SimulationStage.SYNAPSE,
            source=pathway.pn,
            target=pathway.kc,
            neurotransmitter=Neurotransmitter.UNKNOWN,
            message=f"{pathway.pn} -> {pathway.kc}: PN->KC 경로가 활성화되었습니다 (시냅스 가중치 {pathway.pn_kc_weight}).",
        ),
        SimulationEvent(
            t_ms=28.1,
            stage=SimulationStage.MUSCLE,
            source=pathway.kc,
            target=pathway.mbon,
            message=f"{pathway.kc} -> {pathway.mbon}: KC->MBON 경로로 버섯체 출력이 전달되었습니다 (시냅스 가중치 {pathway.kc_mbon_weight}).",
        ),
        SimulationEvent(
            t_ms=45.0,
            stage=SimulationStage.MOVEMENT,
            message=f"{label}에 대한 행동 유의성(valence) 신호가 발현되었습니다.",
        ),
    ]


def _build_visual_trace(visual: VisualCommand) -> list[SimulationEvent]:
    label = _VISUAL_LABELS[visual]
    pathway = _VISUAL_PATHWAYS[visual]

    return [
        SimulationEvent(t_ms=0, stage=SimulationStage.COMMAND, message=f"'{label}' 시각 자극이 시엽(optic lobe) 출력 채널에 입력되었습니다."),
        SimulationEvent(
            t_ms=14.0,
            stage=SimulationStage.MUSCLE,
            source=pathway.pre,
            target=pathway.post,
            message=f"{pathway.pre} -> {pathway.post}: VPN->DN 경로로 하행뉴런 출력이 전달되었습니다 (시냅스 가중치 {pathway.weight}).",
        ),
        SimulationEvent(
            t_ms=32.0,
            stage=SimulationStage.MOVEMENT,
            message=f"{label}에 대한 도피/추적 행동 신호가 발현되었습니다.",
        ),
    ]


def _build_nav_trace(heading: HeadingCommand) -> list[SimulationEvent]:
    label = _NAV_LABELS[heading]
    pathway = _NAV_PATHWAYS[heading]

    return [
        SimulationEvent(t_ms=0, stage=SimulationStage.COMMAND, message=f"'{label}' 나침반 웨지에 헤딩 자극이 입력되었습니다."),
        SimulationEvent(
            t_ms=11.0,
            stage=SimulationStage.MUSCLE,
            source=pathway.pre,
            target=pathway.post,
            message=f"{pathway.pre} -> {pathway.post}: EPG->PFL 경로로 조향 출력이 전달되었습니다 (시냅스 가중치 {pathway.weight}).",
        ),
        SimulationEvent(
            t_ms=26.0,
            stage=SimulationStage.MOVEMENT,
            message=f"{label}에 대한 조향(steering) 신호가 발현되었습니다.",
        ),
    ]


def build_trace(stimulus: FlyStimulus) -> list[SimulationEvent]:
    if isinstance(stimulus, VisualCommand):
        return _build_visual_trace(stimulus)
    if isinstance(stimulus, HeadingCommand):
        return _build_nav_trace(stimulus)
    return _build_odor_trace(stimulus)
