"""Stimulus command -> narrated event trace for the human-genome
activity-dependent gene expression cascade demo (mirrors
app/simulation/fly_engine.py's role, adapted for genes instead of neurons).

STATUS: rule-based narration only, same honesty framing as fly_engine.py —
this replays one real, well-documented pathway's real gene order with fixed
timings; it is not a simulation of transcription/translation kinetics (no
ODE model of gene expression exists in this project). Real gene identities
and chromosome locations come from
app/data/sources/human/bdnf_pathway_genes.csv (see SOURCES.md's "BDNF
활동의존적 발현 경로" section for citations: Tao et al. 1998; Greenberg et
al. 2009) and app/data/sources/human/arc_plasticity_genes.csv (see
SOURCES.md's "Arc/Arg3.1 시냅스 가소성 경로" section: Bramham, Worley,
Moore & Guzowski 2008, J Neurosci 28(46):11760-11767).
"""

from __future__ import annotations

from app.domain.schemas import GenePathwayCommand, SimulationEvent, SimulationStage

# Real NCBI GeneIDs (not invented) — see app/data/sources/human/bdnf_pathway_genes.csv.
_BDNF_GENE_ID = "627"  # chr11, 11p14.1
_CREB1_GENE_ID = "1385"  # chr2, 2q33.3
_NTRK2_GENE_ID = "4915"  # chr9, 9q21.33 (TrkB)

# Real NCBI GeneIDs — see app/data/sources/human/arc_plasticity_genes.csv.
# GRIN2B is also in the main 646-gene pool (app/data/human_genome.json);
# CAMK2A/ARC aren't (same as CREB1/NTRK2 above for the BDNF pathway —
# pathway-trace genes don't need to be in that pool, see human_genome_engine
# usage in schemas.py).
_GRIN2B_GENE_ID = "2904"  # chr12, 12p13.1 (NMDA receptor subunit GluN2B)
_CAMK2A_GENE_ID = "815"  # chr5, 5q32
_ARC_GENE_ID = "23237"  # chr8, 8q24.3 (Arc/Arg3.1)

_LABELS: dict[GenePathwayCommand, str] = {
    GenePathwayCommand.BDNF_ACTIVATION: "신경 활동 자극 → BDNF 활동의존적 발현",
    GenePathwayCommand.ARC_PLASTICITY_ACTIVATION: "NMDA 수용체 활성화 → Arc/Arg3.1 발현",
}


def _build_bdnf_trace() -> list[SimulationEvent]:
    return [
        SimulationEvent(
            t_ms=0,
            stage=SimulationStage.COMMAND,
            message="신경 활동(칼슘 유입)이 자극으로 입력되었습니다 — Tao et al. 1998.",
        ),
        SimulationEvent(
            t_ms=15.0,
            stage=SimulationStage.SYNAPSE,
            source=_CREB1_GENE_ID,
            target=_CREB1_GENE_ID,
            message="CREB1(2q33.3) 단백질이 인산화되어 전사인자로 활성화되었습니다.",
        ),
        SimulationEvent(
            t_ms=32.0,
            stage=SimulationStage.MUSCLE,
            source=_CREB1_GENE_ID,
            target=_BDNF_GENE_ID,
            message="CREB1 -> BDNF(11p14.1): 활성화된 CREB1이 BDNF 유전자 발현을 유도했습니다.",
        ),
        SimulationEvent(
            t_ms=48.0,
            stage=SimulationStage.MUSCLE,
            source=_BDNF_GENE_ID,
            target=_NTRK2_GENE_ID,
            message="BDNF -> NTRK2/TrkB(9q21.33): 분비된 BDNF 단백질이 TrkB 수용체에 결합했습니다 — Greenberg et al. 2009.",
        ),
        SimulationEvent(
            t_ms=64.0,
            stage=SimulationStage.MOVEMENT,
            message="TrkB 신호전달을 통해 시냅스 가소성(강화)이 유도되었습니다.",
        ),
    ]


def _build_arc_trace() -> list[SimulationEvent]:
    """NMDA receptor activation -> CaMKII phosphorylation -> Arc/Arg3.1
    transcription -> synaptic plasticity (LTP/LTD) — see Bramham et al.
    2008's review for the pathway order and mechanism; the timings below
    are narration pacing, same as _build_bdnf_trace(), not measured
    transcription kinetics."""
    return [
        SimulationEvent(
            t_ms=0,
            stage=SimulationStage.COMMAND,
            message="강한 패턴화된 시냅스 활동이 자극으로 입력되었습니다 — Bramham et al. 2008.",
        ),
        SimulationEvent(
            t_ms=12.0,
            stage=SimulationStage.SYNAPSE,
            source=_GRIN2B_GENE_ID,
            target=_GRIN2B_GENE_ID,
            message="GRIN2B(12p13.1, NMDA 수용체 GluN2B 소단위)가 활성화되어 칼슘이 유입되었습니다.",
        ),
        SimulationEvent(
            t_ms=27.0,
            stage=SimulationStage.SYNAPSE,
            source=_GRIN2B_GENE_ID,
            target=_CAMK2A_GENE_ID,
            message="GRIN2B -> CAMK2A(5q32): 유입된 칼슘이 CaMKII를 인산화·활성화했습니다.",
        ),
        SimulationEvent(
            t_ms=45.0,
            stage=SimulationStage.MUSCLE,
            source=_CAMK2A_GENE_ID,
            target=_ARC_GENE_ID,
            message="CAMK2A -> ARC(8q24.3): 활성화된 CaMKII 신호가 Arc/Arg3.1 즉시초기유전자 발현을 유도했습니다.",
        ),
        SimulationEvent(
            t_ms=64.0,
            stage=SimulationStage.MOVEMENT,
            message="Arc/Arg3.1 단백질이 시냅스 후막에 축적되어 시냅스 가소성(LTP/LTD)을 조절했습니다.",
        ),
    ]


def build_trace(stimulus: GenePathwayCommand) -> list[SimulationEvent]:
    if stimulus == GenePathwayCommand.BDNF_ACTIVATION:
        return _build_bdnf_trace()
    if stimulus == GenePathwayCommand.ARC_PLASTICITY_ACTIVATION:
        return _build_arc_trace()
    raise ValueError(f"Unknown gene pathway command: {stimulus}")
