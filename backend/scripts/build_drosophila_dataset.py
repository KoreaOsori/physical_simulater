"""One-off build script: turns the vendored hemibrain circuit subsets in
`app/data/sources/drosophila/` into `app/data/drosophila_connectome.json`, the
dataset `app.data.drosophila_connectome` loads at runtime.

Run manually whenever the source files change:

    cd backend
    ./.venv/Scripts/python scripts/build_drosophila_dataset.py

See app/data/sources/drosophila/SOURCES.md for full provenance and honestly
documented limitations. Summary of what's real vs. computed:

- **Neurons/connections**: real hemibrain v1.2 EM-reconstructed data (Janelia
  FlyEM, CC-BY). Three circuit subsets are merged into one connectome:
  - olfactory: ORN/PN/KC/MBON/DAN (v2 phase 1)
  - visual: VPN (lobula/lobula-plate output types: LC/LT/LPLC/LLPC/LPC) and DN
    (descending neurons: DNp*/Giant Fiber) (v2 phase 2)
  - navigation: ER (ellipsoid-body ring neurons), RING (EPG/PEN/PEG/Delta7
    compass ring), PFN (heading x goal integration), PFL (steering output) —
    the central-complex circuit (v2 phase 4)
  Plus small sets of *real* direct synapses that happen to cross between
  subsets (`cross_circuit_bridge_connections*.csv`) — these aren't
  fabricated links, they're genuine hemibrain edges (e.g. an MBON synapsing
  onto a DN) that a naive per-subset filter would otherwise silently drop.
  All connections use the same >=3-synapse noise threshold (see SOURCES.md).
- **Positions**: NOT real anatomical coordinates (see SOURCES.md — the public
  hemibrain flat files don't include soma XYZ). Computed as a
  connectivity-informed layered layout per circuit. Each circuit's layout is
  centered at its own origin (no cross-circuit offset) — the frontend now
  renders each circuit on its own page (see app/api/routes/fly.py's `circuit`
  query param) rather than one shared scene, so there's no longer a reason to
  spatially separate them.
- **Neurotransmitter**: `dopamine` for DAN (PAM/PPL) neurons only — asserted
  by the hemibrain cell-type name itself. Everything else, including the new
  VPN/DN types, is `unknown` (no per-cell neurotransmitter source vendored).
- **cell_type**: the raw hemibrain `type` column (e.g. "LC4", "MBON01",
  "KCab") is now carried through as its own field (previously only folded
  into `name`/`categories_ko`) so the frontend can look up per-type
  descriptions precisely instead of guessing from an instance name.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path

SOURCES_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sources" / "drosophila"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "drosophila_connectome.json"

OLFACTORY_NEURONS_PATH = SOURCES_DIR / "olfactory_subset_neurons.csv"
OLFACTORY_CONNECTIONS_PATH = SOURCES_DIR / "olfactory_subset_connections.csv"
VISUAL_NEURONS_PATH = SOURCES_DIR / "visual_subset_neurons.csv"
VISUAL_CONNECTIONS_PATH = SOURCES_DIR / "visual_subset_connections.csv"
NAVIGATION_NEURONS_PATH = SOURCES_DIR / "navigation_subset_neurons.csv"
NAVIGATION_CONNECTIONS_PATH = SOURCES_DIR / "navigation_subset_connections.csv"
BRIDGE_CONNECTIONS_PATH = SOURCES_DIR / "cross_circuit_bridge_connections.csv"
BRIDGE_CONNECTIONS_NAV_PATH = SOURCES_DIR / "cross_circuit_bridge_connections_navigation.csv"

# Flow-axis (scene x) position per circuit stage, matching the frontend's
# existing camera convention where x is the long/horizontal axis (see
# build_connectome_dataset.py's _remap_to_scene comment for the C. elegans
# side of that convention). Both circuits reuse the same x range since each
# now renders on its own page (see module docstring) rather than sharing one
# scene.
_STAGE_X: dict[str, float] = {
    "ORN": -3.4,
    "PN": -2.2,
    "DAN": -0.6,  # modulatory, interleaved between PN and KC/MBON
    "KC": 0.0,
    "MBON": 2.2,
    "VPN": -2.2,
    "DN": 2.2,
    "ER": -3.4,
    "RING": -1.8,
    "PFN": 0.4,
    "PFL": 2.2,
}

_GLOMERULUS_RADIUS = 3.0
_JITTER_SCALE = 0.35


def _hash_unit(key: str) -> float:
    """Deterministic pseudo-random value in [-1, 1] from a stable hash of key."""
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    return (int(digest, 16) / 0xFFFFFFFF) * 2 - 1


def _jitter(body_id: str, salt: str, scale: float = _JITTER_SCALE) -> tuple[float, float, float]:
    return (
        _hash_unit(f"{body_id}:{salt}:x") * scale,
        _hash_unit(f"{body_id}:{salt}:y") * scale,
        _hash_unit(f"{body_id}:{salt}:z") * scale,
    )


_PN_GLOMERULUS_RE = re.compile(r"^(.+)_(ad|l|v)PN\d*$")


def pn_glomerulus(type_name: str) -> str:
    m = _PN_GLOMERULUS_RE.match(type_name)
    return m.group(1) if m else type_name


def _load_neuron_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_connection_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return [{"pre": r["bodyId_pre"], "post": r["bodyId_post"], "weight": int(r["weight"])} for r in csv.DictReader(f)]


def _weighted_centroid(
    edges: list[tuple[str, int]], allowed: set[str], positions: dict[str, dict[str, float]]
) -> tuple[float, float] | None:
    total_w = 0.0
    sy = sz = 0.0
    for other_id, w in edges:
        if other_id not in allowed or other_id not in positions:
            continue
        p = positions[other_id]
        sy += p["y"] * w
        sz += p["z"] * w
        total_w += w
    if total_w == 0:
        return None
    return sy / total_w, sz / total_w


def _fallback_spiral(index: int, total: int) -> tuple[float, float]:
    angle = 2 * math.pi * index / max(total, 1) * 3  # a few spiral wraps
    radius = _GLOMERULUS_RADIUS * (0.3 + 0.7 * (index / max(total - 1, 1)))
    return radius * math.cos(angle), radius * math.sin(angle)


def build_olfactory_positions(raw_neurons: list[dict], connections: list[dict]) -> dict[str, dict[str, float]]:
    by_class: dict[str, list[dict]] = {}
    for n in raw_neurons:
        by_class.setdefault(n["circuit_class"], []).append(n)

    incoming: dict[str, list[tuple[str, int]]] = {}
    outgoing: dict[str, list[tuple[str, int]]] = {}
    for c in connections:
        incoming.setdefault(c["post"], []).append((c["pre"], c["weight"]))
        outgoing.setdefault(c["pre"], []).append((c["post"], c["weight"]))

    positions: dict[str, dict[str, float]] = {}

    # 1. PN: evenly-spaced glomerulus circle.
    pn_neurons = by_class.get("PN", [])
    glomeruli = sorted({pn_glomerulus(n["type"]) for n in pn_neurons})
    glomerulus_angle = {g: 2 * math.pi * i / max(len(glomeruli), 1) for i, g in enumerate(glomeruli)}
    glomerulus_center: dict[str, tuple[float, float]] = {
        g: (_GLOMERULUS_RADIUS * math.cos(a), _GLOMERULUS_RADIUS * math.sin(a)) for g, a in glomerulus_angle.items()
    }
    for n in pn_neurons:
        g = pn_glomerulus(n["type"])
        cy, cz = glomerulus_center[g]
        jx, jy, jz = _jitter(n["bodyId"], "pn")
        positions[n["bodyId"]] = {"x": _STAGE_X["PN"] + jx * 0.3, "y": cy * 0.5 + jy, "z": cz + jz}

    # 2. ORN: near its matching glomerulus if the type encodes one, else centered.
    for n in by_class.get("ORN", []):
        m = re.match(r"^ORN_(.+)$", n["type"])
        g = m.group(1) if m else None
        cy, cz = glomerulus_center.get(g, (0.0, 0.0))
        jx, jy, jz = _jitter(n["bodyId"], "orn")
        positions[n["bodyId"]] = {"x": _STAGE_X["ORN"] + jx * 0.3, "y": cy * 0.5 + jy, "z": cz + jz}

    # 3. KC: weighted centroid of presynaptic PNs.
    pn_ids = {n["bodyId"] for n in pn_neurons}
    kc_neurons = by_class.get("KC", [])
    for i, n in enumerate(kc_neurons):
        body_id = n["bodyId"]
        centroid = _weighted_centroid(incoming.get(body_id, []), pn_ids, positions)
        jx, jy, jz = _jitter(body_id, "kc")
        cy, cz = centroid if centroid is not None else _fallback_spiral(i, len(kc_neurons))
        positions[body_id] = {"x": _STAGE_X["KC"] + jx * 0.3, "y": cy + jy, "z": cz + jz}

    # 4. MBON: weighted centroid of presynaptic KCs.
    kc_ids = {n["bodyId"] for n in kc_neurons}
    mbon_neurons = by_class.get("MBON", [])
    for i, n in enumerate(mbon_neurons):
        body_id = n["bodyId"]
        centroid = _weighted_centroid(incoming.get(body_id, []), kc_ids, positions)
        jx, jy, jz = _jitter(body_id, "mbon")
        cy, cz = centroid if centroid is not None else _fallback_spiral(i, len(mbon_neurons))
        positions[body_id] = {"x": _STAGE_X["MBON"] + jx * 0.3, "y": cy + jy, "z": cz + jz}

    # 5. DAN: weighted centroid of postsynaptic KC/MBON partners (DANs
    # modulate downstream, so their position is derived from what they
    # target rather than what targets them).
    kc_mbon_ids = kc_ids | {n["bodyId"] for n in mbon_neurons}
    dan_neurons = by_class.get("DAN", [])
    for i, n in enumerate(dan_neurons):
        body_id = n["bodyId"]
        centroid = _weighted_centroid(outgoing.get(body_id, []), kc_mbon_ids, positions)
        jx, jy, jz = _jitter(body_id, "dan")
        cy, cz = centroid if centroid is not None else _fallback_spiral(i, len(dan_neurons))
        positions[body_id] = {"x": _STAGE_X["DAN"] + jx * 0.4, "y": cy + jy, "z": cz + jz}

    return positions


def build_visual_positions(raw_neurons: list[dict], connections: list[dict]) -> dict[str, dict[str, float]]:
    by_class: dict[str, list[dict]] = {}
    for n in raw_neurons:
        by_class.setdefault(n["circuit_class"], []).append(n)

    incoming: dict[str, list[tuple[str, int]]] = {}
    for c in connections:
        incoming.setdefault(c["post"], []).append((c["pre"], c["weight"]))

    positions: dict[str, dict[str, float]] = {}

    # 1. VPN: evenly-spaced "column type" circle — same idea as the
    # olfactory PN glomerulus circle, since each hemibrain VPN `type` (LC4,
    # LPLC2, ...) plays the same "one distinct visual-feature channel" role a
    # glomerulus plays for odor.
    vpn_neurons = by_class.get("VPN", [])
    vpn_types = sorted({n["type"] for n in vpn_neurons})
    type_angle = {t: 2 * math.pi * i / max(len(vpn_types), 1) for i, t in enumerate(vpn_types)}
    type_center: dict[str, tuple[float, float]] = {
        t: (_GLOMERULUS_RADIUS * math.cos(a), _GLOMERULUS_RADIUS * math.sin(a)) for t, a in type_angle.items()
    }
    for n in vpn_neurons:
        cy, cz = type_center[n["type"]]
        jx, jy, jz = _jitter(n["bodyId"], "vpn")
        positions[n["bodyId"]] = {
            "x": _STAGE_X["VPN"] + jx * 0.3,
            "y": cy * 0.5 + jy,
            "z": cz + jz,
        }

    # 2. DN: weighted centroid of presynaptic VPNs (real direct edges exist —
    # see SOURCES.md — though most of a DN's real input is via un-modeled
    # local interneurons this subset deliberately excludes).
    vpn_ids = {n["bodyId"] for n in vpn_neurons}
    dn_neurons = by_class.get("DN", [])
    for i, n in enumerate(dn_neurons):
        body_id = n["bodyId"]
        centroid = _weighted_centroid(incoming.get(body_id, []), vpn_ids, positions)
        jx, jy, jz = _jitter(body_id, "dn")
        cy, cz = centroid if centroid is not None else _fallback_spiral(i, len(dn_neurons))
        positions[body_id] = {
            "x": _STAGE_X["DN"] + jx * 0.4,
            "y": cy + jy,
            "z": cz + jz,
        }

    return positions


def build_navigation_positions(raw_neurons: list[dict], connections: list[dict]) -> dict[str, dict[str, float]]:
    by_class: dict[str, list[dict]] = {}
    for n in raw_neurons:
        by_class.setdefault(n["circuit_class"], []).append(n)

    incoming: dict[str, list[tuple[str, int]]] = {}
    for c in connections:
        incoming.setdefault(c["post"], []).append((c["pre"], c["weight"]))

    positions: dict[str, dict[str, float]] = {}

    def _circle_by_type(neurons: list[dict], stage: str, salt: str) -> None:
        types = sorted({n["type"] for n in neurons})
        angle = {t: 2 * math.pi * i / max(len(types), 1) for i, t in enumerate(types)}
        center = {t: (_GLOMERULUS_RADIUS * math.cos(a), _GLOMERULUS_RADIUS * math.sin(a)) for t, a in angle.items()}
        for n in neurons:
            cy, cz = center[n["type"]]
            jx, jy, jz = _jitter(n["bodyId"], salt)
            positions[n["bodyId"]] = {"x": _STAGE_X[stage] + jx * 0.3, "y": cy * 0.5 + jy, "z": cz + jz}

    # 1. ER (ellipsoid-body ring neurons, real landmark input to the compass
    # ring — see SOURCES.md): circle by type (ER1-ER6 etc., each a distinct
    # visual-feature channel, same idea as the olfactory PN glomerulus circle).
    _circle_by_type(by_class.get("ER", []), "ER", "er")

    # 2. RING (EPG/PEN/PEG/Delta7, the core compass ring-attractor): circle
    # by type — a real ring in the biology too (protocerebral bridge wedges),
    # approximated here the same way as other stages rather than trying to
    # reconstruct exact wedge angles from instance names.
    ring_neurons = by_class.get("RING", [])
    _circle_by_type(ring_neurons, "RING", "ring")

    # 3. PFN (heading x internal-state integration): circle by type (many
    # named subtypes: PFNa/PFNd/PFNm/...).
    _circle_by_type(by_class.get("PFN", []), "PFN", "pfn")

    # 4. PFL (steering output): weighted centroid of presynaptic RING
    # partners (real direct EPG->PFL edges exist — see SOURCES.md).
    ring_ids = {n["bodyId"] for n in ring_neurons}
    pfl_neurons = by_class.get("PFL", [])
    for i, n in enumerate(pfl_neurons):
        body_id = n["bodyId"]
        centroid = _weighted_centroid(incoming.get(body_id, []), ring_ids, positions)
        jx, jy, jz = _jitter(body_id, "pfl")
        cy, cz = centroid if centroid is not None else _fallback_spiral(i, len(pfl_neurons))
        positions[body_id] = {"x": _STAGE_X["PFL"] + jx * 0.4, "y": cy + jy, "z": cz + jz}

    return positions


_NEURON_TYPE_BY_CLASS = {
    "ORN": "sensory",
    "PN": "inter",
    "KC": "inter",
    "DAN": "inter",
    "MBON": "motor",
    "VPN": "sensory",
    "DN": "motor",
    "ER": "sensory",
    "RING": "inter",
    "PFN": "inter",
    "PFL": "motor",
}
_CIRCUIT_CLASS_LABEL_KO = {
    "ORN": "후각수용뉴런(ORN)",
    "PN": "촉각엽 투사뉴런(PN)",
    "KC": "버섯체 켄욘세포(KC)",
    "DAN": "도파민성 뉴런(DAN)",
    "MBON": "버섯체 출력뉴런(MBON)",
    "VPN": "시각 투사뉴런(VPN)",
    "DN": "하행뉴런(DN)",
    "ER": "고리뉴런(ER)",
    "RING": "나침반 고리뉴런(EPG/PEN/PEG/Delta7)",
    "PFN": "헤딩-목표 통합뉴런(PFN)",
    "PFL": "조향 출력뉴런(PFL)",
}


def build() -> None:
    olf_raw = _load_neuron_csv(OLFACTORY_NEURONS_PATH)
    olf_conn = _load_connection_csv(OLFACTORY_CONNECTIONS_PATH)
    vis_raw = _load_neuron_csv(VISUAL_NEURONS_PATH)
    vis_conn = _load_connection_csv(VISUAL_CONNECTIONS_PATH)
    nav_raw = _load_neuron_csv(NAVIGATION_NEURONS_PATH)
    nav_conn = _load_connection_csv(NAVIGATION_CONNECTIONS_PATH)
    bridge_conn = _load_connection_csv(BRIDGE_CONNECTIONS_PATH)
    bridge_nav_conn = _load_connection_csv(BRIDGE_CONNECTIONS_NAV_PATH)

    positions = build_olfactory_positions(olf_raw, olf_conn)
    positions.update(build_visual_positions(vis_raw, vis_conn))
    positions.update(build_navigation_positions(nav_raw, nav_conn))

    tagged_neurons = (
        [(n, "olfactory") for n in olf_raw] + [(n, "visual") for n in vis_raw] + [(n, "navigation") for n in nav_raw]
    )
    connections = olf_conn + vis_conn + nav_conn + bridge_conn + bridge_nav_conn

    neurons_out = []
    for n, circuit in tagged_neurons:
        body_id = n["bodyId"]
        cls = n["circuit_class"]
        pos = positions[body_id]
        neurons_out.append(
            {
                "id": body_id,
                "name": n["instance"] or n["type"],
                "cell_type": n["type"],
                "circuit": circuit,
                "type": _NEURON_TYPE_BY_CLASS[cls],
                "neurotransmitter": "dopamine" if cls == "DAN" else "unknown",
                "description_en": None,
                "categories_ko": [_CIRCUIT_CLASS_LABEL_KO[cls]],
                "wormatlas_url": None,
                "position": {k: round(v, 4) for k, v in pos.items()},
            }
        )

    nt_by_id = {n["id"]: n["neurotransmitter"] for n in neurons_out}
    synapses_out = []
    for i, c in enumerate(connections):
        synapses_out.append(
            {
                "id": f"s{i}",
                "pre": c["pre"],
                "post": c["post"],
                "type": "chemical",  # hemibrain adjacency table doesn't identify gap junctions
                "neurotransmitter": nt_by_id[c["pre"]],
                "weight": c["weight"],
            }
        )

    dataset = {
        "organism": "drosophila",
        "neuron_count_total": len(neurons_out),
        "effector_count_total": 0,
        "is_placeholder": False,
        "neurons": neurons_out,
        "effectors": [],
        "synapses": synapses_out,
    }

    OUTPUT_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH} - {len(neurons_out)} neurons "
        f"({len(olf_raw)} olfactory + {len(vis_raw)} visual + {len(nav_raw)} navigation), 0 effectors, "
        f"{len(synapses_out)} synapses "
        f"({len(olf_conn)} olfactory + {len(vis_conn)} visual + {len(nav_conn)} navigation + "
        f"{len(bridge_conn)} bridge + {len(bridge_nav_conn)} nav-bridge)."
    )


if __name__ == "__main__":
    build()
