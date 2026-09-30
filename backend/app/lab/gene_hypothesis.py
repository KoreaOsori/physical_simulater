"""유전자 경로 후보 가설 탐색기 (docs/37). 실제 염색체 위치(cytoband)
데이터로 "위치 후보 유전자(positional candidate gene)" 접근을 이
프로젝트의 2개 기존 경로(docs/28 BDNF, docs/29 Arc/Arg3.1)에 적용한다 --
알려진 유전자 근처의 유전자를 관련 후보로 보는 건 실제 유전학에서 쓰이는
방법론(포지셔널 클로닝/후보 유전자 접근)이다.

물리적 근접성 자체가 기능적 연관을 보장하지 않는다 -- 유전자 클러스터·
공동조절의 실제 사례(예: HOX 클러스터)가 있지만, 이웃한다고 반드시
관련 있는 건 아니다. 이 모듈은 "후보를 좁히는" 도구지 "발견을 주장하는"
도구가 아니다.

646개 GO 필터 유전자 목록에 왜 나머지 GO 태그 기반 유사도를 안 썼는지도
기록: 실제 데이터를 보면 go_tags는 3개짜리 광범위한 카테고리
(nervous_system_development/chemical_synaptic_transmission/
visual_perception)뿐이고 613/646개가 태그 1개만 갖고 있어, 쌍별 유사도를
계산해봐야 "같은 큰 범주"라는 거의 무의미한 신호만 나온다 -- 그래서
실제로 더 구체적인 신호인 염색체 위치를 썼다."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.data.human_data import get_genome
from app.domain.schemas import CytoBand
from app.lab.schemas import GeneCandidateOut, GenePathwayReportOut

TOP_N = 8

_HONESTY_NOTE = (
    "물리적으로 가깝다는 것이 기능적으로 연관됐다는 뜻은 아닙니다 — 유전자 클러스터·공동조절의 실제 사례가 "
    "있지만(예: HOX 클러스터), 이웃한다고 반드시 관련 있는 건 아닙니다. 이 목록은 후보를 좁혀보는 가설이지, "
    "이 프로젝트가 새로운 경로를 발견했다는 주장이 아닙니다."
)


@dataclass(frozen=True)
class _SeedGene:
    symbol: str
    chromosome: str
    map_location: str
    pathway_label: str


# 실제 human_genome_engine.py가 쓰는 두 경로의 시드 유전자 -- 646개 GO
# 필터 목록엔 없지만(다른 GO 카테고리 소속, 존재하지 않는 유전자가
# 아님, bdnf_pathway_genes.csv/arc_plasticity_genes.csv와 정확히 동일한
# 실제 NCBI map_location) 염색체 위치는 확실히 알려져 있다.
_SEED_GENES: list[_SeedGene] = [
    _SeedGene("BDNF", "11", "11p14.1", "BDNF 활동의존적 발현 경로"),
    _SeedGene("CREB1", "2", "2q33.3", "BDNF 활동의존적 발현 경로"),
    _SeedGene("NTRK2", "9", "9q21.33", "BDNF 활동의존적 발현 경로"),
    _SeedGene("GRIN2B", "12", "12p13.1", "Arc/Arg3.1 시냅스 가소성 경로"),
    _SeedGene("CAMK2A", "5", "5q32", "Arc/Arg3.1 시냅스 가소성 경로"),
    _SeedGene("ARC", "8", "8q24.3", "Arc/Arg3.1 시냅스 가소성 경로"),
]


def _position_fraction(chromosome: str, map_location: str, bands_by_chrom: dict[str, list[CytoBand]]) -> float | None:
    """backend/scripts/build_human_dataset.py의 `_gene_position_fraction`과
    정확히 같은 실제 cytoband 중점 계산 -- 빌드 타임이 아니라 이미 로드된
    실제 `genome.cytobands`로 런타임에 다시 계산한다(시드 유전자 6개는
    genome.genes 목록에 없어서 position_fraction이 미리 계산돼 있지 않음)."""
    bands = bands_by_chrom.get(chromosome)
    if not bands or not map_location:
        return None
    band_part = map_location[len(chromosome) :] if map_location.startswith(chromosome) else None
    if not band_part:
        return None
    band_part = band_part.split("|")[0].split(";")[0].strip()
    if not band_part:
        return None

    chrom_length = max(b.end for b in bands)
    match = next((b for b in bands if b.band == band_part), None)
    if match is None:
        match = next((b for b in bands if b.band.startswith(band_part)), None)
    if match is None:
        return None
    midpoint = (match.start + match.end) / 2
    return midpoint / chrom_length


@lru_cache
def build_gene_pathway_candidates() -> list[GenePathwayReportOut]:
    genome = get_genome()
    bands_by_chrom: dict[str, list[CytoBand]] = {}
    for band in genome.cytobands:
        bands_by_chrom.setdefault(band.chromosome, []).append(band)

    seed_symbols = {s.symbol for s in _SEED_GENES}
    reports: list[GenePathwayReportOut] = []
    for seed in _SEED_GENES:
        seed_pos = _position_fraction(seed.chromosome, seed.map_location, bands_by_chrom)
        candidates: list[GeneCandidateOut] = []
        if seed_pos is not None:
            same_chrom = [
                g
                for g in genome.genes
                if g.chromosome == seed.chromosome and g.symbol not in seed_symbols and g.position_fraction is not None
            ]
            same_chrom.sort(key=lambda g: abs(g.position_fraction - seed_pos))
            for g in same_chrom[:TOP_N]:
                candidates.append(
                    GeneCandidateOut(
                        symbol=g.symbol,
                        chromosome=g.chromosome,
                        map_location=g.map_location,
                        description=g.description,
                        distance_fraction=round(abs(g.position_fraction - seed_pos), 5),
                        go_tags=g.go_tags,
                    )
                )
        reports.append(
            GenePathwayReportOut(
                seed_symbol=seed.symbol,
                pathway_label=seed.pathway_label,
                seed_chromosome=seed.chromosome,
                seed_map_location=seed.map_location,
                candidates=candidates,
                honesty_note=_HONESTY_NOTE,
            )
        )
    return reports
