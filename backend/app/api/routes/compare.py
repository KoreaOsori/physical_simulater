"""Cross-species scale comparison — the one endpoint that spans all three
species' otherwise fully separate route namespaces (connectome.py/fly.py/
human.py). Reuses each species' existing data accessors rather than adding a
new dataset; the only new thing here is packaging their counts side by side,
plus citable real-world reference numbers kept in clearly separate fields so
"what this project's data contains" is never visually confused with "the
real organism's actual scale" (see docs/23-cross-species-scale-comparison.md
and this project's is_placeholder-style honesty convention elsewhere)."""

from fastapi import APIRouter

from app.data.celegans_connectome import get_connectome as get_worm_connectome
from app.data.drosophila_connectome import get_connectome as get_fly_connectome
from app.data.human_data import get_macro_connectome, get_micro_sample
from app.domain.schemas import CompareSummary, SpeciesDatasetScale

router = APIRouter(tags=["compare"])


def _build_summary() -> CompareSummary:
    worm = get_worm_connectome()
    fly = get_fly_connectome()
    human_macro = get_macro_connectome()
    human_micro = get_micro_sample()

    species = [
        SpeciesDatasetScale(
            species_id="c_elegans",
            common_name_ko="예쁜꼬마선충",
            scientific_name="Caenorhabditis elegans",
            is_dataset_complete=True,
            dataset_neuron_count=worm.neuron_count_total,
            dataset_synapse_count=len(worm.synapses),
            dataset_region_count=None,
            dataset_note="White et al./OpenWorm EM 재구성 302개 뉴런 전체 — 이 종의 실제 체세포 신경계와 사실상 동일한 규모(추가/누락 없음).",
            real_world_neuron_count=worm.neuron_count_total,
            real_world_neuron_count_note="이 데이터셋 자체가 실제 전체 성체 자웅동체 신경계(302개, 발생학적으로 고정된 수)와 같다 — 별도 추정치가 필요 없는 유일한 종.",
        ),
        SpeciesDatasetScale(
            species_id="drosophila",
            common_name_ko="초파리",
            scientific_name="Drosophila melanogaster",
            is_dataset_complete=False,
            dataset_neuron_count=fly.neuron_count_total,
            dataset_synapse_count=len(fly.synapses),
            dataset_region_count=None,
            dataset_note="헤미브레인(hemibrain) 커넥톰에서 가져온 3개 회로(후각/시각/항법) 부분집합 — 전체 헤미브레인(중심뇌 약 25,000개 뉴런)의 일부, 전체 성체 뇌는 더 크다.",
            real_world_neuron_count=25_000,
            real_world_neuron_count_note="Scheffer et al. 2020 (eLife), hemibrain 커넥톰 논문의 중심뇌(central brain) 재구성 규모 약 25,000개 — 이 프로젝트 데이터셋과 같은 소스로 직접 비교 가능한 수치. 전체 성체 뇌(시엽 포함)는 문헌마다 추정치 편차가 커(약 10-15만 개 범위) 여기서는 인용하지 않음.",
        ),
        SpeciesDatasetScale(
            species_id="human",
            common_name_ko="인간",
            scientific_name="Homo sapiens",
            is_dataset_complete=False,
            dataset_neuron_count=human_micro.neuron_count_total,
            dataset_synapse_count=human_micro.synapse_count_total,
            dataset_region_count=human_macro.region_count_total,
            dataset_note=(
                f"두 개의 서로 다른 실제 데이터가 있다 — (1) 거시: Schaefer-{human_macro.region_count_total} "
                "파셀레이션, 전체 피질을 빠짐없이 덮지만 각 파셀은 뉴런 하나가 아니라 수백만 개를 뭉친 영역이라 "
                f"'뉴런 수'가 아님. (2) 미세: H01 EM 데이터셋에서 가져온 실제 뉴런 {human_micro.neuron_count_total}개"
                f"(측두피질의 아주 작은 샘플, 시냅스 접촉점 {human_micro.synapse_count_total}개) — 전체 뇌의 "
                "극히 일부. 두 숫자를 더하거나 섞지 않는다."
            ),
            real_world_neuron_count=86_000_000_000,
            real_world_neuron_count_note="Herculano-Houzel 2009 (Front Hum Neurosci), 등방성분획법(isotropic fractionator) 실측 기반 추정 약 860억 개 — 이 데이터셋(미세 샘플 104개, 거시 파셀 400개) 어느 쪽과도 비교 불가능할 만큼 큰 차이이며, 그 차이 자체가 메시지다.",
        ),
    ]
    return CompareSummary(species=species)


@router.get("/api/compare/summary", response_model=CompareSummary)
def read_compare_summary() -> CompareSummary:
    return _build_summary()
