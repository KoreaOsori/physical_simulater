"""Curated real laser-ablation studies for C. elegans, paired with this
dataset's actual neuron ids -- mirrors human_anatomical_labels.py's
`DISORDERS`/`resolve_disorders()` pattern (see
docs/21-human-macro-disorder-associations.md) one level down: instead of
"which brain region is classically implicated in this human syndrome," this
is "which of the 302 real neurons, when a classic experiment silenced them,
produced a documented behavioral deficit."

Every entry cites a real published laser-ablation (or genetic-ablation-
equivalent) study. `resolve_ablations()` only keeps entries whose neuron ids
actually exist in this dataset (all of them do, as of 2026-09-19 -- checked
directly against celegans_connectome.json) and silently drops any that
don't, same honesty convention as human_anatomical_labels.py's disorder
resolution.
"""

from __future__ import annotations

ABLATIONS: list[dict[str, object]] = [
    {
        "name": "후진 지휘 인터뉴런 (AVA/AVD/AVE)",
        "category": "locomotion",
        "description": (
            "AVA, AVD, AVE 인터뉴런은 A형 운동뉴런을 지휘해 후진(reversal)을 일으킨다 — "
            "Chalfie et al. 1985 (J Neurosci 5(4):956-964)의 레이저 절제 실험이 이 세 쌍을 "
            "제거하면 후진 반응이 사라지는 것을 보였다. 이 프로젝트에서는 세포를 실제로 "
            "제거하지 않고 이 뉴런들의 출력 시냅스를 이번 명령 한 번에 한해 무효화하는 "
            "방식으로 근사한다."
        ),
        "neuron_ids": ["AVAL", "AVAR", "AVDL", "AVDR", "AVEL", "AVER"],
    },
    {
        "name": "전진 지휘 인터뉴런 (AVB/PVC)",
        "category": "locomotion",
        "description": (
            "AVB, PVC 인터뉴런은 B형 운동뉴런을 지휘해 전진(forward locomotion)을 일으킨다 — "
            "Chalfie et al. 1985가 같은 논문에서 이 쌍을 제거하면 전진이 약화되는 것을 보였다 "
            "(PVC의 기여는 AVB보다 작다고 보고됨)."
        ),
        "neuron_ids": ["AVBL", "AVBR", "PVCL", "PVCR"],
    },
    {
        "name": "전방 촉각 수용 뉴런 (ALM/AVM)",
        "category": "sensory",
        "description": (
            "머리 쪽을 가볍게 건드렸을 때의 회피 반응은 ALML/R과 AVM이 담당한다 — "
            "Chalfie & Sulston 1981 (Dev Biol 82(2):358-370)이 확립한 예쁜꼬마선충 촉각 "
            "수용 회로. PVM은 형태·유전자 발현은 비슷하지만 단독으로는 정상 촉각 반응을 "
            "매개하지 못한다고 보고되어 이 목록에서 의도적으로 제외했다."
        ),
        "neuron_ids": ["ALML", "ALMR", "AVM"],
    },
    {
        "name": "후방 촉각 수용 뉴런 (PLM)",
        "category": "sensory",
        "description": (
            "꼬리 쪽을 가볍게 건드렸을 때의 전진 회피 반응은 PLML/R이 담당한다 — "
            "같은 Chalfie & Sulston 1981 촉각 회로의 후방 절반."
        ),
        "neuron_ids": ["PLML", "PLMR"],
    },
    {
        "name": "산란 지휘 뉴런 (HSN)",
        "category": "reproductive",
        "description": (
            "HSNL/R은 세로토닌을 분비해 산란(egg-laying)을 촉진하는 지휘 뉴런이다 — "
            "Trent, Tsung & Horvitz 1983이 HSN을 절제하면 산란율이 크게 떨어지는 것을 "
            "보였고, 외인성 세로토닌 투여로 그 결손이 회복되는 것도 확인했다."
        ),
        "neuron_ids": ["HSNL", "HSNR"],
    },
    {
        "name": "휘발성 냄새 화학주성 뉴런 (AWA/AWC)",
        "category": "sensory",
        "description": (
            "AWA·AWC는 휘발성 유인 물질(디아세틸 등)에 대한 화학주성을 매개한다 — "
            "Bargmann, Hartwieg & Horvitz 1993 (Cell 74(3):515-527)의 절제 실험. 두 뉴런의 "
            "기여도는 냄새 물질마다 다르다(디아세틸은 AWA 주도, 아이소아밀알코올은 AWC "
            "주도) — 이 항목은 단순화해 둘을 함께 절제하는 것으로 근사한다."
        ),
        "neuron_ids": ["AWAL", "AWAR", "AWCL", "AWCR"],
    },
    {
        "name": "코끝 접촉·고삼투압 회피 뉴런 (ASH)",
        "category": "sensory",
        "description": (
            "ASHL/R은 코끝 접촉, 고삼투압, 휘발성 기피 물질 모두에 반응해 후진 회피를 "
            "일으키는 다중감각 뉴런이다 — Kaplan & Horvitz 1993의 절제 실험이 이 반응들을 "
            "매개함을 보였다."
        ),
        "neuron_ids": ["ASHL", "ASHR"],
    },
]


def resolve_ablations(existing_neuron_ids: set[str]) -> list[dict[str, object]]:
    """Filters ABLATIONS down to entries whose neuron_ids are all present in
    this dataset -- mirrors human_anatomical_labels.py's resolve_disorders()
    "drop, don't fabricate" convention. Returns dicts shaped to match
    ClassicAblation (see app/domain/schemas.py)."""
    resolved: list[dict[str, object]] = []
    for entry in ABLATIONS:
        neuron_ids = [nid for nid in entry["neuron_ids"] if nid in existing_neuron_ids]  # type: ignore[index]
        if not neuron_ids:
            continue
        resolved.append(
            {
                "name": entry["name"],
                "category": entry["category"],
                "description": entry["description"],
                "neuron_ids": neuron_ids,
            }
        )
    return resolved
