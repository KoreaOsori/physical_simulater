"""Fenyves et al. 2020의 시냅스 극성 예측을 이 프로젝트용 JSON으로 변환한다(docs/47).

원자료: Fenyves, Szilágyi, Vassy, Sőti & Csermely 2020, "Synaptic polarity and sign-balance
prediction using gene expression data in the Caenorhabditis elegans chemical synapse neuronal
connectome network", PLOS Comput Biol 16(12):e1007974 -- S1 Data(시냅스 전 뉴런의 신경전달물질 +
시냅스 후 뉴런의 이온성 수용체 발현으로 예측, WormWiring 재구성 기준).
https://linkgroup.hu/docs/S1_Data.xlsx -> app/data/sources/fenyves2020_S1_Data.xlsx

엑셀 '5. Sign prediction' 시트의 'Predicted polarity' 열(캐시된 계산값)을 그대로 옮긴다:
  "+"        흥분성 수용체만 매칭(예: AWC->AIB)
  "-"        억제성 수용체만 매칭(예: AWC->AIY, GluCl -- Chalasani et al. 2007과 일치)
  "complex"  같은 신경전달물질에 흥분·억제 수용체가 둘 다 있어 예측 불가
  "no pred"  발현 정보 부족으로 예측 없음
이 변환은 값을 새로 추정하지 않는다 -- 원 논문의 예측을 그대로 옮기기만 한다.

실행(호스트 Python, openpyxl 필요 -- scripts/requirements-build.txt):
    python -m scripts.build_synapse_signs
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "data" / "sources" / "fenyves2020_S1_Data.xlsx"
OUT = ROOT / "app" / "data" / "celegans_synapse_signs.json"

_MAP = {"+": "+", "-": "-", "complex": "complex", "no pred": "no_pred"}


def main() -> None:
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    ws = wb["5. Sign prediction"]
    signs: dict[str, str] = {}
    for row in list(ws.iter_rows(values_only=True))[2:]:
        pre, post, edge_type, pred = row[0], row[3], row[5], row[16]
        if not pre or edge_type != "chemical" or pred not in _MAP:
            continue
        signs[f"{pre}>{post}"] = _MAP[pred]

    connectome = json.loads((ROOT / "app" / "data" / "celegans_connectome.json").read_text(encoding="utf-8"))
    neuron_ids = {n["id"] for n in connectome["neurons"]}
    ours = [s for s in connectome["synapses"] if s["type"] == "chemical" and s["post"] in neuron_ids]
    coverage = collections.Counter(signs.get(f'{s["pre"]}>{s["post"]}', "missing") for s in ours)

    OUT.write_text(
        json.dumps(
            {
                "source": "Fenyves et al. 2020, PLOS Comput Biol 16(12):e1007974, S1 Data (NT+R prediction)",
                "url": "https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007974",
                "note": "'+'/'-' are the paper's predicted polarities; 'complex'/'no_pred' are left unresolved on purpose.",
                "counts": dict(collections.Counter(signs.values())),
                "coverage_of_this_project_chemical_synapses": dict(coverage),
                "signs": signs,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print("connections:", len(signs), dict(collections.Counter(signs.values())))
    print("this project's neuron->neuron chemical synapses:", len(ours), dict(coverage))


if __name__ == "__main__":
    main()
