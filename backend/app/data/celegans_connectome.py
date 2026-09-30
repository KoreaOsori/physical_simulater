"""C. elegans connectome data access.

Loads the real 302-neuron / ~6,900-edge dataset built by
`backend/scripts/build_connectome_dataset.py` from the vendored sources in
`app/data/sources/` (see `SOURCES.md` there for provenance and known
limitations — most notably: 3D positions are a computed graph layout, not
real anatomical coordinates).

To rebuild after changing the source files or the build script:

    cd backend
    ./.venv/Scripts/python scripts/build_connectome_dataset.py
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.data.celegans_classic_ablations import resolve_ablations
from app.domain.schemas import ClassicAblation, Connectome

DATASET_PATH = Path(__file__).resolve().parent / "celegans_connectome.json"


@lru_cache
def get_connectome() -> Connectome:
    with DATASET_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return Connectome.model_validate(raw)


@lru_cache
def get_classic_ablations() -> list[ClassicAblation]:
    """Resolved against the real neuron ids in this dataset -- see
    app/data/celegans_classic_ablations.py."""
    neuron_ids = {n.id for n in get_connectome().neurons}
    return [ClassicAblation.model_validate(entry) for entry in resolve_ablations(neuron_ids)]
