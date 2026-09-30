"""One-off build script: turns the vendored source files in
`app/data/sources/` into `app/data/celegans_connectome.json`, the dataset
`app.data.celegans_connectome` loads at runtime.

Run manually whenever the source files change:

    cd backend
    ./.venv/Scripts/python scripts/build_connectome_dataset.py

Not run automatically at server startup — the output JSON is committed so the
dataset is reproducible without needing to re-derive positions every time.
See app/data/sources/SOURCES.md for full provenance. Positions:

- **Neurons**: real EM-reconstructed soma coordinates from
  `celegans_neuron_soma_positions.json` (micrometres), scaled down into scene
  units. Verified axis meaning: y = anterior-posterior, x = left-right,
  z = dorsal-ventral (see SOURCES.md).
- **Effectors** (muscle/gut/epidermis): no per-cell coordinate source exists
  for these, so their anterior-posterior placement is anchored to the real
  position of the neurons that actually innervate them (e.g. vulval muscles
  anchored to HSNL/HSNR's real y), and their cross-sectional offset (which
  quadrant/ring position) is a fixed geometric placement, not measured.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

SOURCES_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sources"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "celegans_connectome.json"

EDGE_LIST_PATH = SOURCES_DIR / "herm_full_edgelist.csv"
OWMETA_PATH = SOURCES_DIR / "owmeta_neuron_muscle_info.json"
NEURON_POSITIONS_PATH = SOURCES_DIR / "celegans_neuron_soma_positions.json"
ONTOLOGY_PATH = SOURCES_DIR / "wbbt_anatomy_ontology.obo"

# Micrometres -> scene units. The real AP (y) span is ~-312..+410 um (~722 um
# total); this scale puts that at roughly -5.2..+6.8 scene units, matching
# the camera/OrbitControls distances already tuned in the frontend.
_UM_TO_SCENE = 1 / 60.0

TYPE_LABEL_MAP = {"interneuron": "inter", "sensory": "sensory", "motor": "motor"}
TYPE_PRIORITY = ["sensory", "motor", "inter"]

NT_LABEL_MAP = {
    "Acetylcholine": "acetylcholine",
    "GABA": "gaba",
    "Glutamate": "glutamate",
    "Dopamine": "dopamine",
    "Serotonin": "serotonin",
    "Octopamine": "octopamine",
    "Tyramine": "tyramine",
}


def normalize_numeric_suffix(name: str) -> str:
    """'VA1' and 'VA01' both occur across the two sources; zero-pad to 2 digits
    so they compare equal. Names without a trailing number pass through unchanged."""
    m = re.match(r"^([A-Za-z]+)(\d+)$", name)
    if not m:
        return name
    return f"{m.group(1)}{int(m.group(2)):02d}"


def classify_effector(name: str) -> str:
    if name.startswith(("dBWM", "vBWM")):
        return "muscle"
    if name.startswith("pm") or name == "sph" or name.startswith("mc"):
        return "muscle"
    if name.startswith(("um", "vm")):
        return "muscle"
    if name == "anal":
        return "muscle"
    if name in ("intestine", "intL", "intR"):
        return "gut"
    if name == "hyp":
        return "epidermis"
    return "other"


def load_neuron_positions() -> dict[str, dict]:
    with NEURON_POSITIONS_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return {
        name: {
            "x": p["x"] * _UM_TO_SCENE,
            "y": p["y"] * _UM_TO_SCENE,
            "z": p["z"] * _UM_TO_SCENE,
        }
        for name, p in raw.items()
    }


# Korean labels for the WormBase anatomy ontology's is_a functional/positional
# categories (see load_neuron_ontology below). Covers the ~59 category terms
# that actually apply to our 302 neurons; anything not listed here falls
# through to translate_category()'s generic "<CODE> 계열 뉴런" pattern or, for
# truly unmapped terms, is shown in English rather than guessed.
CATEGORY_LABEL_KO: dict[str, str] = {
    "interneuron": "중간뉴런",
    "motor neuron": "운동뉴런",
    "sensory neuron": "감각뉴런",
    "command interneuron": "명령 인터뉴런",
    "pharyngeal interneuron": "인두 중간뉴런",
    "pharyngeal motor neuron": "인두 운동뉴런",
    "pharyngeal neuron": "인두 뉴런",
    "head motor neuron": "머리 운동뉴런",
    "head neuron": "머리 뉴런",
    "nerve ring neuron": "신경환(nerve ring) 뉴런",
    "ventral cord neuron": "배쪽 신경삭 뉴런",
    "touch receptor neuron": "촉각수용 뉴런",
    "mechanosensory neuron": "기계감각 뉴런",
    "chemosensory neuron": "화학감각 뉴런",
    "odorsensory neuron": "후각(냄새감각) 뉴런",
    "osmosensory neuron": "삼투압감각 뉴런",
    "thermosensory neuron": "온도감각 뉴런",
    "nociceptor neuron": "통각(유해자극감각) 뉴런",
    "oxygen sensory neuron": "산소감각 뉴런",
    "carbon dioxide sensory neuron": "이산화탄소감각 뉴런",
    "amphid neuron": "암피드(amphid) 감각기 뉴런",
    "phasmid neuron": "파스미드(phasmid) 감각기 뉴런",
    "deirid neuron": "데이리드(deirid) 감각기 뉴런",
    "inner labial neuron": "내순(inner labial) 감각 뉴런",
    "outer labial neuron": "외순(outer labial) 감각 뉴런",
    "ciliated neuron": "섬모성 감각뉴런",
    "cholinergic neuron": "콜린성(아세틸콜린) 뉴런",
    "GABAergic neuron": "GABA성 뉴런",
    "glutamatergic neuron": "글루탐산성 뉴런",
    "serotonergic neuron": "세로토닌성 뉴런",
    "dopaminergic neuron": "도파민성 뉴런",
    "dorsal-rectal ganglion neuron": "배측직장신경절 뉴런",
    "lateral ganglion left neuron": "좌측 측면신경절 뉴런",
    "lateral ganglion right neuron": "우측 측면신경절 뉴런",
    "lumbar left ganglion neuron": "좌측 요추신경절 뉴런",
    "lumbar right ganglion neuron": "우측 요추신경절 뉴런",
    "posterior lateral left ganglion": "좌측 후측면신경절 뉴런",
    "posterior lateral right ganglion": "우측 후측면신경절 뉴런",
    "preanal ganglion neuron": "항문전신경절 뉴런",
    "retrovesicular ganglion neuron": "후방광신경절 뉴런",
}

# Redundant (equals the neuron's own class) or developmentally-focused terms
# that aren't useful to surface in a per-neuron tooltip.
CATEGORY_BLOCKLIST = {"embryonic cell", "post-embryonic cell", "hermaphrodite-specific anatomical entity", "neuron"}


def translate_category(label: str) -> str:
    if label in CATEGORY_LABEL_KO:
        return CATEGORY_LABEL_KO[label]
    m = re.match(r"^([A-Z][A-Za-z0-9]{0,4}) neuron$", label)
    if m:
        return f"{m.group(1)} 계열 뉴런"
    return label


def load_neuron_ontology() -> dict[str, dict]:
    """Parses the vendored WormBase anatomy ontology (WBbt) into
    {term_name: {"def": ..., "is_a": [...], "wormatlas_url": ...}}."""
    text = ONTOLOGY_PATH.read_text(encoding="utf-8")
    terms: dict[str, dict] = {}
    for block in text.split("\n[Term]\n"):
        m_name = re.search(r"^name:\s*(.+)$", block, re.M)
        if not m_name:
            continue
        m_def = re.search(r'^def:\s*"([^"]*)"', block, re.M)
        is_a = re.findall(r"^is_a:\s*\S+\s*!\s*(.+)$", block, re.M)
        m_comment = re.search(r"^comment:\s*(.+)$", block, re.M)
        wormatlas_url = None
        if m_comment:
            m_url = re.search(r"<(https?://[^>]+)>", m_comment.group(1))
            if m_url:
                wormatlas_url = m_url.group(1)
        terms[m_name.group(1).strip()] = {"def": m_def.group(1).strip() if m_def else None, "is_a": is_a, "wormatlas_url": wormatlas_url}
    return terms


def _ontology_lookup_keys(neuron_id: str) -> list[str]:
    no_digits = re.sub(r"\d+$", "", neuron_id)
    no_lr = re.sub(r"[LR]$", "", no_digits)
    # Single (unpaired) pharyngeal neurons like I3/M1/MI are named "I3 neuron"
    # etc. in the ontology rather than bare "I3" — see SOURCES.md.
    return [neuron_id, no_digits, no_lr, f"{neuron_id} neuron", f"{no_digits} neuron", f"{no_lr} neuron"]


def resolve_neuron_ontology(neuron_id: str, ontology_terms: dict[str, dict]) -> dict:
    # The most specific matching term (individual cell, e.g. "AVAL") often has
    # a richer historical definition than its class-level term ("AVA"), but
    # only the class-level term tends to carry is_a category tags — so take
    # the definition from the first match, but merge categories across every
    # matching key rather than stopping at the first one.
    description_en = None
    wormatlas_url = None
    raw_categories: list[str] = []
    seen_labels: set[str] = set()

    for key in _ontology_lookup_keys(neuron_id):
        entry = ontology_terms.get(key)
        if entry is None:
            continue
        if description_en is None:
            description_en = entry["def"]
        if wormatlas_url is None:
            wormatlas_url = entry["wormatlas_url"]
        for label in entry["is_a"]:
            if label in seen_labels:
                continue
            seen_labels.add(label)
            if label in CATEGORY_BLOCKLIST or (label.isupper() and " " not in label):
                continue
            raw_categories.append(translate_category(label))

    return {"description_en": description_en, "categories_ko": raw_categories, "wormatlas_url": wormatlas_url}


# Real anterior-posterior anchors (scene units), derived from the actual
# soma y-position of the neurons that innervate each structure — see
# SOURCES.md. Not fabricated: computed once from celegans_neuron_soma_positions.json
# and hardcoded here since they only need to be derived once.
_BWM_Y_RANGE = (-253.3 * _UM_TO_SCENE, 379.85 * _UM_TO_SCENE)  # DA/DB/DD/VA/VB/VD/AS motor neuron span
_PHARYNX_Y_RANGE = (-311.65 * _UM_TO_SCENE, -241.45 * _UM_TO_SCENE)  # I/M/MC/MI/NSM pharyngeal neuron span
_VULVA_Y = 61.05 * _UM_TO_SCENE  # HSNL/HSNR real y
_GUT_Y_RANGE = (-200.0 * _UM_TO_SCENE, 350.0 * _UM_TO_SCENE)

_BODY_RADIUS_X = 18.0 * _UM_TO_SCENE
_BODY_RADIUS_Z = 40.0 * _UM_TO_SCENE
_PHARYNX_RADIUS = 12.0 * _UM_TO_SCENE
_VULVA_RADIUS = 9.0 * _UM_TO_SCENE


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _remap_to_scene(p: dict[str, float]) -> dict[str, float]:
    """Real body axes are x=left-right, y=anterior-posterior, z=dorsal-ventral
    (see SOURCES.md). The 3D viewer expects x=anterior-posterior (the long,
    horizontal axis its camera/controls are tuned for), y=dorsal-ventral
    (up), z=left-right — matching the frontend's existing camera convention."""
    return {"x": p["y"], "y": p["z"], "z": p["x"]}


def compute_effector_position(effector_id: str, row_counts: dict[str, int]) -> dict[str, float]:
    """Anatomically-anchored (not measured) effector placement — see the
    module docstring and SOURCES.md."""
    m = re.match(r"^([dv])BWM([LR])(\d+)$", effector_id)
    if m:
        dorsoventral, side, idx = m.group(1), m.group(2), int(m.group(3))
        row_key = f"{dorsoventral}BWM{side}"
        t = (idx - 1) / max(row_counts[row_key] - 1, 1)
        y = _lerp(*_BWM_Y_RANGE, t)
        x = _BODY_RADIUS_X if side == "L" else -_BODY_RADIUS_X
        z = _BODY_RADIUS_Z if dorsoventral == "d" else -_BODY_RADIUS_Z
        return {"x": x, "y": y, "z": z}

    m = re.match(r"^pm(\d)(d|vl|vr)$", effector_id)
    if m:
        idx, sub = int(m.group(1)), m.group(2)
        t = (idx - 1) / 7  # pm1..pm8
        y = _lerp(*_PHARYNX_Y_RANGE, t)
        if sub == "d":
            return {"x": 0.0, "y": y, "z": _PHARYNX_RADIUS}
        x = _PHARYNX_RADIUS * 0.7 if sub == "vl" else -_PHARYNX_RADIUS * 0.7
        return {"x": x, "y": y, "z": -_PHARYNX_RADIUS * 0.6}

    m = re.match(r"^mc(\d)(dl|dr|v)$", effector_id)
    if m:
        idx, sub = int(m.group(1)), m.group(2)
        t = (idx - 1) / 2  # mc1..mc3
        y = _lerp(*_PHARYNX_Y_RANGE, t)
        if sub == "v":
            return {"x": 0.0, "y": y, "z": -_PHARYNX_RADIUS}
        x = _PHARYNX_RADIUS * 0.6 if sub == "dl" else -_PHARYNX_RADIUS * 0.6
        return {"x": x, "y": y, "z": _PHARYNX_RADIUS * 0.5}

    m = re.match(r"^vm(\d)([ap])([LR])$", effector_id)
    if m:
        _idx, ap, side = m.group(1), m.group(2), m.group(3)
        y = _VULVA_Y + (-14.0 * _UM_TO_SCENE if ap == "a" else 14.0 * _UM_TO_SCENE)
        x = _VULVA_RADIUS if side == "L" else -_VULVA_RADIUS
        return {"x": x, "y": y, "z": -_VULVA_RADIUS * 0.5}

    if effector_id == "hyp":
        return {"x": 0.0, "y": _lerp(*_GUT_Y_RANGE, 0.5), "z": _BODY_RADIUS_Z * 1.05}
    if effector_id == "intestine":
        return {"x": 0.0, "y": _lerp(*_GUT_Y_RANGE, 0.5), "z": 0.0}
    if effector_id == "intL":
        return {"x": _BODY_RADIUS_X * 0.4, "y": _lerp(*_GUT_Y_RANGE, 0.6), "z": 0.0}

    # Fallback for any future/unexpected effector name: mid-body, on-axis.
    return {"x": 0.0, "y": _lerp(*_GUT_Y_RANGE, 0.5), "z": 0.0}


def load_neuron_metadata() -> dict[str, dict]:
    with OWMETA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    neuron_info = data["neuron_info"]

    metadata: dict[str, dict] = {}
    for canonical_name, record in neuron_info.items():
        types: list[str] = record[1]
        neurotransmitters: list[str] = record[3]

        primary_type = "unknown"
        for candidate in TYPE_PRIORITY:
            if candidate in [TYPE_LABEL_MAP.get(t, t) for t in types]:
                primary_type = candidate
                break

        primary_nt = "unknown"
        for nt in neurotransmitters:
            if nt in NT_LABEL_MAP:
                primary_nt = NT_LABEL_MAP[nt]
                break

        metadata[normalize_numeric_suffix(canonical_name)] = {
            "canonical_name": canonical_name,
            "type": primary_type,
            "neurotransmitter": primary_nt,
        }
    return metadata


def load_edges() -> list[dict]:
    edges = []
    with EDGE_LIST_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row["Source"].strip()
            target = row["Target"].strip()
            weight = row["Weight"].strip()
            edge_type = row["Type"].strip()
            if not source or not weight.isdigit():
                continue
            edges.append({"source": source, "target": target, "weight": int(weight), "type": edge_type})
    return edges


def build() -> None:
    neuron_meta = load_neuron_metadata()  # keyed by zero-padded join key
    edges_raw = load_edges()

    padded_neuron_keys = set(neuron_meta.keys())
    effector_kinds: dict[str, str] = {}  # raw (unpadded) edge-list name -> kind

    resolved_edges = []
    for e in edges_raw:
        src_key = normalize_numeric_suffix(e["source"])
        tgt_key = normalize_numeric_suffix(e["target"])
        if src_key not in padded_neuron_keys:
            # Source should always be a neuron in this dataset; skip anything
            # unexpected (in practice: effector-to-effector edges, see
            # SOURCES.md) rather than silently mis-typing it.
            continue
        source_id = neuron_meta[src_key]["canonical_name"]
        if tgt_key in padded_neuron_keys:
            target_id = neuron_meta[tgt_key]["canonical_name"]
        else:
            target_id = e["target"].strip()
            effector_kinds.setdefault(target_id, classify_effector(target_id))
        resolved_edges.append({**e, "source": source_id, "target": target_id})

    ontology_terms = load_neuron_ontology()
    unmatched_ontology: list[str] = []

    neurons = []
    for meta in sorted(neuron_meta.values(), key=lambda m: m["canonical_name"]):
        neuron_id = meta["canonical_name"]
        ontology = resolve_neuron_ontology(neuron_id, ontology_terms)
        if ontology["description_en"] is None:
            unmatched_ontology.append(neuron_id)
        neurons.append(
            {
                "id": neuron_id,
                "name": neuron_id,
                "type": meta["type"],
                "neurotransmitter": meta["neurotransmitter"],
                "description_en": ontology["description_en"],
                "categories_ko": ontology["categories_ko"],
                "wormatlas_url": ontology["wormatlas_url"],
            }
        )
    if unmatched_ontology:
        print(f"WARNING: no WBbt ontology definition found for {len(unmatched_ontology)} neurons: {unmatched_ontology}")

    effectors = [
        {"id": eid, "name": eid, "kind": kind}
        for eid, kind in sorted(effector_kinds.items())
    ]

    neuron_positions = load_neuron_positions()
    for neuron in neurons:
        pos = _remap_to_scene(neuron_positions[neuron["id"]])
        neuron["position"] = {k: round(v, 4) for k, v in pos.items()}

    bwm_row_counts: dict[str, int] = {}
    for eid in effector_kinds:
        m = re.match(r"^([dv]BWM[LR])(\d+)$", eid)
        if m:
            row, idx = m.group(1), int(m.group(2))
            bwm_row_counts[row] = max(bwm_row_counts.get(row, 0), idx)
    for effector in effectors:
        pos = _remap_to_scene(compute_effector_position(effector["id"], bwm_row_counts))
        effector["position"] = {k: round(v, 4) for k, v in pos.items()}

    neurotransmitter_by_canonical = {n["id"]: n["neurotransmitter"] for n in neurons}

    synapses = []
    for i, e in enumerate(resolved_edges):
        nt = "electrical"
        if e["type"] == "chemical":
            nt = neurotransmitter_by_canonical[e["source"]]
        synapses.append(
            {
                "id": f"s{i}",
                "pre": e["source"],
                "post": e["target"],
                "type": e["type"],
                "neurotransmitter": nt,
                "weight": e["weight"],
            }
        )

    dataset = {
        "organism": "c_elegans",
        "neuron_count_total": len(neurons),
        "effector_count_total": len(effectors),
        "is_placeholder": False,
        "neurons": neurons,
        "effectors": effectors,
        "synapses": synapses,
    }

    OUTPUT_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH} - {len(neurons)} neurons, {len(effectors)} effectors, "
        f"{len(synapses)} synapses."
    )


if __name__ == "__main__":
    build()
