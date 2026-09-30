"""Human data access — three separate real datasets (see
app/data/sources/human/SOURCES.md for why they're not unified into one
"connectome" the way C. elegans/Drosophila are): a macro-scale brain-region
network, a micro-scale real EM neuron sample, and a nervous-system gene map.

To rebuild after changing the source files or the build script:

    cd backend
    ./.venv/Scripts/python scripts/build_human_dataset.py
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.schemas import HumanGenome, MacroConnectome, MicroConnectomeSample

DATA_DIR = Path(__file__).resolve().parent
MACRO_PATH = DATA_DIR / "human_macro_connectome.json"
MICRO_PATH = DATA_DIR / "human_micro_sample.json"
GENOME_PATH = DATA_DIR / "human_genome.json"


@lru_cache
def get_macro_connectome() -> MacroConnectome:
    with MACRO_PATH.open(encoding="utf-8") as f:
        return MacroConnectome.model_validate(json.load(f))


@lru_cache
def get_micro_sample() -> MicroConnectomeSample:
    with MICRO_PATH.open(encoding="utf-8") as f:
        return MicroConnectomeSample.model_validate(json.load(f))


@lru_cache
def get_genome() -> HumanGenome:
    with GENOME_PATH.open(encoding="utf-8") as f:
        return HumanGenome.model_validate(json.load(f))
