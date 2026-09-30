"""Drosophila (hemibrain olfactory-circuit subset) connectome data access.

Loads the dataset built by `backend/scripts/build_drosophila_dataset.py` from
the vendored hemibrain v1.2 source files in `app/data/sources/drosophila/`
(see `SOURCES.md` there for provenance and known limitations — most notably:
this is a ~2,452-neuron olfactory pathway subset of the full ~25k-neuron
hemibrain, and 3D positions are a connectivity-informed computed layout, not
real anatomical coordinates).

To rebuild after changing the source files or the build script:

    cd backend
    ./.venv/Scripts/python scripts/build_drosophila_dataset.py
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.schemas import CircuitName, Connectome

DATASET_PATH = Path(__file__).resolve().parent / "drosophila_connectome.json"


@lru_cache
def get_connectome() -> Connectome:
    with DATASET_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return Connectome.model_validate(raw)


@lru_cache
def get_connectome_for_circuit(circuit: CircuitName) -> Connectome:
    """The full merged dataset filtered to one circuit subset's own neurons
    and the synapses between them — used both by the per-circuit frontend
    pages (`GET /api/fly/connectome?circuit=...`, see app/api/routes/fly.py)
    and by fly_hh_model.py to simulate a much smaller network than the full
    merged one. Real cross-circuit bridge synapses (see SOURCES.md) are
    dropped here since one endpoint always belongs to the other circuit —
    they only make sense in the unfiltered full dataset."""
    full = get_connectome()
    neuron_ids = {n.id for n in full.neurons if n.circuit == circuit}
    neurons = [n for n in full.neurons if n.id in neuron_ids]
    synapses = [s for s in full.synapses if s.pre in neuron_ids and s.post in neuron_ids]
    return Connectome(
        organism=full.organism,
        neuron_count_total=len(neurons),
        effector_count_total=full.effector_count_total,
        is_placeholder=full.is_placeholder,
        neurons=neurons,
        effectors=full.effectors,
        synapses=synapses,
    )
