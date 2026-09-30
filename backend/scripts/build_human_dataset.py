"""One-off build script: turns the vendored real human data in
`app/data/sources/human/` into three JSON files under `app/data/` that
`app.data.human_data` loads at runtime.

Run manually whenever the source files change. The macro build now also
bakes a dive-in-reveal anatomy mesh (see human_anatomy_mesh.py), which needs
nibabel/scikit-image installed first:

    cd backend
    ./.venv/Scripts/python -m pip install -r scripts/requirements-build.txt
    ./.venv/Scripts/python scripts/build_human_dataset.py

See app/data/sources/human/SOURCES.md for full provenance and honestly
documented limitations — most importantly, these are THREE separate,
differently-scaled real datasets (macro region network / micro EM sample /
gene map), not one unified "human connectome", because no whole-brain
neuron-level human connectome exists.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import human_anatomy_mesh
import human_anatomical_labels

SOURCES_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sources" / "human"
DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
CROSS_NETWORK_EDGES = SOURCES_DIR / "schaefer_cross_network_edges.csv"
SOURCE_SC_MATRIX = SOURCES_DIR / "liu2023_sc_cons_400_nosubc.npy"


def _verify_edges_match_source_matrix(edges: list[dict]) -> None:
    """재발 방지(docs/49): 벤더링한 간선 집합이 원본 400x400 이진 합의 행렬의 상삼각과 정확히 같아야
    빌드가 통과한다. 이전엔 '영역 수 합계 = 400'만 검증해서 간선의 60%가 빠진 걸 못 잡았다."""
    import numpy as np

    sc = np.load(SOURCE_SC_MATRIX)
    expected = {(i + 1, j + 1) for i in range(sc.shape[0]) for j in range(i + 1, sc.shape[0]) if sc[i, j]}
    actual = {tuple(sorted((int(e["a"]), int(e["b"])))) for e in edges}
    if len(actual) != len(edges):
        raise SystemExit(f"duplicate edges vendored: {len(edges)} rows but {len(actual)} unique")
    if actual != expected:
        raise SystemExit(f"vendored edges != source matrix: missing {len(expected - actual)}, extra {len(actual - expected)}")
    print(f"edge check: {len(actual)} edges == source consensus matrix upper triangle")

# One (regions CSV, edges CSV) pair per Yeo-7 network — all seven now
# vendored (see SOURCES.md's "6차 패스" section for the remaining five;
# Vis/Limbic were added in the 1st/2nd passes). Region counts sum to exactly
# 400 across all seven (61+26+77+46+47+52+91), confirming every one of the
# real Schaefer 400-parcel atlas's parcels is accounted for exactly once.
NETWORK_SOURCES = {
    "Vis": (SOURCES_DIR / "schaefer_vis_regions.csv", SOURCES_DIR / "schaefer_vis_edges.csv"),
    "SomMot": (SOURCES_DIR / "schaefer_sommot_regions.csv", SOURCES_DIR / "schaefer_sommot_edges.csv"),
    "DorsAttn": (SOURCES_DIR / "schaefer_dorsattn_regions.csv", SOURCES_DIR / "schaefer_dorsattn_edges.csv"),
    "SalVentAttn": (SOURCES_DIR / "schaefer_salventattn_regions.csv", SOURCES_DIR / "schaefer_salventattn_edges.csv"),
    "Limbic": (SOURCES_DIR / "schaefer_limbic_regions.csv", SOURCES_DIR / "schaefer_limbic_edges.csv"),
    "Cont": (SOURCES_DIR / "schaefer_cont_regions.csv", SOURCES_DIR / "schaefer_cont_edges.csv"),
    "Default": (SOURCES_DIR / "schaefer_default_regions.csv", SOURCES_DIR / "schaefer_default_edges.csv"),
}
MICRO_PATH = SOURCES_DIR / "h01_micro_sample_points.csv"
MICRO_SYNAPSES_PATH = SOURCES_DIR / "h01_micro_sample_synapses.csv"
# One CSV per real GO-term-derived gene set this pass vendors. Each row's
# own `go_tags` column already names which real GO term(s) it matched, so no
# extra "category" field is needed — the 2nd pass's "visual_perception" set
# (GO:0007601) only contains genes NOT already in the 1st pass's
# nervous-system set (GO:0007399 ∪ GO:0007268), so a gene with real
# annotations in both GO groups would only show up in the nervous-system
# file's tags, not both — see SOURCES.md for why that's an honestly
# documented simplification, not a claim that the two sets are disjoint in
# reality.
GENE_SOURCES = {
    "nervous_system": SOURCES_DIR / "human_nervous_system_genes.csv",
    "visual_perception": SOURCES_DIR / "human_visual_system_genes.csv",
}
CYTOBAND_PATH = SOURCES_DIR / "cytoband.txt"

MACRO_OUT = DATA_DIR / "human_macro_connectome.json"
MICRO_OUT = DATA_DIR / "human_micro_sample.json"
GENOME_OUT = DATA_DIR / "human_genome.json"


_MACRO_SCENE_SPAN = 6.0  # target world-space span (units) for the real brain bounding box's longest MNI axis


def build_macro() -> None:
    # Real MNI coordinates (R=right, A=anterior, S=superior, mm) across every
    # vendored network. Unlike the single-network v1 pass, the center/scale
    # is now derived from the real brain mask's own bounding box (see
    # human_anatomy_mesh.compute_reference_frame), not from whichever
    # region set happens to be loaded — so a Limbic region, a Vis region, and
    # the anatomy mesh shells around them all share one coordinate frame and
    # never drift relative to each other when a network is toggled.
    cr, ca, cs, scale = human_anatomy_mesh.compute_reference_frame(_MACRO_SCENE_SPAN)

    # Real coordinate-based anatomical label per region (see
    # human_anatomical_labels.py) — Schaefer names alone don't distinguish
    # individual Vis parcels ("Vis_1".."Vis_31" only), so every tooltip was
    # showing the same boilerplate. This looks up each parcel's real MNI
    # centroid in the AAL atlas instead.
    aal = human_anatomical_labels.AalLookup()

    regions = []
    temppole_mni: list[tuple[float, float, float]] = []
    unlabeled = 0
    for network, (regions_path, _edges_path) in NETWORK_SOURCES.items():
        with regions_path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                r_mni, a_mni, s_mni = float(r["mni_r"]), float(r["mni_a"]), float(r["mni_s"])
                aal_hit = aal.lookup(r_mni, a_mni, s_mni)
                if aal_hit is None:
                    unlabeled += 1
                regions.append(
                    {
                        "id": r["roi_label"],
                        "name": r["roi_name"],
                        "network": network,
                        # MNI S -> scene y (up), MNI A -> scene z (depth), MNI R -> scene x —
                        # only axis *labels* are remapped, not the underlying real values.
                        "position": {"x": (r_mni - cr) * scale, "y": (s_mni - cs) * scale, "z": (a_mni - ca) * scale},
                        # The literal, unscaled real MNI152 centroid (mm), in the
                        # standard (x=R, y=A, z=S) order literature reports it in —
                        # distinct from `position` above, which is this same point
                        # recentered+scaled for 3D scene framing and is NOT
                        # directly comparable to a published MNI coordinate. Added
                        # so a user can actually check a region's real coordinate
                        # against an atlas/paper (see docs/32).
                        "mni_coordinate_mm": {"x": r_mni, "y": a_mni, "z": s_mni},
                        "anatomical_label": aal_hit[0] if aal_hit else None,
                        "anatomical_note": aal_hit[1] if aal_hit else None,
                    }
                )
                if "Limbic_TempPole" in r["roi_name"]:
                    temppole_mni.append((r_mni, a_mni, s_mni))
    print(f"AAL anatomical labels: {len(regions) - unlabeled}/{len(regions)} resolved")

    edges = []
    for _network, (_regions_path, edges_path) in NETWORK_SOURCES.items():
        with edges_path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                edges.append({"a": r["roi_label_a"], "b": r["roi_label_b"], "weight": 1.0})
    # docs/49: 네트워크 '간' 간선. 1·2·6차 패스가 네트워크를 하나씩 추가하며 매번 그 네트워크 내부
    # 간선만 벤더링해서, 원본 합의 행렬 5,059개 중 네트워크를 잇는 3,018개가 처음부터 한 번도 들어간
    # 적이 없었다(그래프가 8조각 -- docs/48에서 발견). 같은 원본 행렬에서 뽑은 CSV로 채운다.
    with CROSS_NETWORK_EDGES.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            edges.append({"a": r["roi_label_a"], "b": r["roi_label_b"], "weight": 1.0})
    _verify_edges_match_source_matrix(edges)

    # Real MNI centroid of the temporal-pole parcels — the honest "closest
    # macro neighborhood" hint for where H01's temporal-cortex sample sits
    # (H01 itself has no MNI registration, so this is a neighborhood marker,
    # not a claim that the sample is AT this exact point — see schemas.py's
    # HeadAnatomy.h01_region_hint docstring and SOURCES.md).
    hint_world = tuple(sum(c) / len(temppole_mni) for c in zip(*temppole_mni))
    anatomy, _frame = human_anatomy_mesh.build_head_anatomy(_MACRO_SCENE_SPAN, hint_world)

    known_disorders = human_anatomical_labels.resolve_disorders(regions)
    print(f"known disorders: {len(known_disorders)} resolved to real regions in this dataset")

    dataset = {
        "networks": list(NETWORK_SOURCES.keys()),
        "region_count_total": len(regions),
        "regions": regions,
        "edges": edges,
        "anatomy": anatomy,
        "known_disorders": known_disorders,
    }
    MACRO_OUT.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {MACRO_OUT} - {len(regions)} regions, {len(edges)} edges, networks={list(NETWORK_SOURCES.keys())}")


_MICRO_SCENE_SPAN = 6.0  # target world-space span (units) for the sample's longest raw axis


def build_micro() -> None:
    raw = []
    with MICRO_PATH.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            raw.append((r["neuron_id"], float(r["x"]), float(r["y"]), float(r["z"]), float(r["radius"])))

    # The H01 skeletons are in raw EM voxel coordinates (0-100k+ range) — real
    # positions, but far too large for this project's scene scale. Center on
    # the sample's own centroid and apply ONE uniform scale factor (not a
    # different factor per axis, which would distort the real proportions)
    # so the longest raw axis spans _MICRO_SCENE_SPAN scene units.
    xs = [p[1] for p in raw]
    ys = [p[2] for p in raw]
    zs = [p[3] for p in raw]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    max_span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    scale = _MICRO_SCENE_SPAN / max_span

    # Axes kept as-is (x->x, y->y, z->z) — H01's own EM-volume axis
    # orientation isn't something this project has independently confirmed
    # maps to a specific real anatomical up/forward, so no axis swap is
    # applied here (unlike the macro MNI coordinates above, where R/A/S is a
    # documented standard).
    points = []
    neuron_ids: set[str] = set()
    for neuron_id, x, y, z, radius in raw:
        neuron_ids.add(neuron_id)
        points.append(
            {
                "neuron_id": neuron_id,
                "position": {"x": (x - cx) * scale, "y": (y - cy) * scale, "z": (z - cz) * scale},
                "radius": round(radius * scale, 5),
            }
        )

    # Real synapse contacts from fetch_h01_synapses.py — see that script's
    # module docstring for the empirically-verified coordinate correction
    # (`x/4, y/4, z as-is` puts a synapse inside its neuron's own real
    # skeleton bounding box in 99.7%+ of sampled rows) applied here, BEFORE
    # the same cx/cy/cz/scale as the skeleton points so both live in one
    # consistent scene frame. Optional: this file only exists once
    # fetch_h01_synapses.py has finished its full 166-shard pass.
    synapses = []
    if MICRO_SYNAPSES_PATH.exists():
        with MICRO_SYNAPSES_PATH.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                raw_x, raw_y, raw_z = float(r["x"]) / 4, float(r["y"]) / 4, float(r["z"])
                synapses.append(
                    {
                        "neuron_id": r["neuron_id"],
                        "role": r["role"],
                        "partner_neuron_id": r["partner_neuron_id"],
                        "partner_is_proofread": r["partner_is_proofread"] == "True",
                        "position": {"x": (raw_x - cx) * scale, "y": (raw_y - cy) * scale, "z": (raw_z - cz) * scale},
                        "confidence": float(r["confidence"]) if r["confidence"] else None,
                    }
                )

    dataset = {
        "source_region": "temporal_cortex",
        "neuron_count_total": len(neuron_ids),
        "point_count_total": len(points),
        "points": points,
        "synapse_count_total": len(synapses),
        "synapses": synapses,
    }
    MICRO_OUT.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {MICRO_OUT} - {len(neuron_ids)} neurons, {len(points)} decimated points, {len(synapses)} synapse contacts")


# A gene counts as "annotated" (real functional description on file) rather
# than "hypothetical" (sparse/no annotation — honestly flagged, not a guess)
# only if NCBI actually gave it a non-empty description and calls it
# protein-coding. See SOURCES.md's "미확인/가설 라벨 기준".
def _confidence(description: str, type_of_gene: str) -> str:
    if description and description != "-" and type_of_gene == "protein-coding":
        return "annotated"
    return "hypothetical"


def _gene_position_fraction(chromosome: str, map_location: str, bands_by_chrom: dict[str, list[dict]]) -> float | None:
    """0-1 position along `chromosome`, from the midpoint of the real UCSC
    cytoband matching this gene's `map_location` (e.g. "11p14.1" on
    chromosome "11" -> band "p14.1"). Real band lookup, not a guess — genes
    whose band can't be matched get None rather than a fabricated midpoint."""
    bands = bands_by_chrom.get(chromosome)
    if not bands or not map_location:
        return None
    band_part = map_location[len(chromosome):] if map_location.startswith(chromosome) else None
    if not band_part:
        return None
    band_part = band_part.split("|")[0].split(";")[0].strip()
    if not band_part:
        return None

    chrom_length = max(b["end"] for b in bands)
    match = next((b for b in bands if b["band"] == band_part), None)
    if match is None:
        match = next((b for b in bands if b["band"].startswith(band_part)), None)
    if match is None:
        return None
    midpoint = (match["start"] + match["end"]) / 2
    return midpoint / chrom_length


def build_genome() -> None:
    cytobands = []
    bands_by_chrom: dict[str, list[dict]] = {}
    with CYTOBAND_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            chrom, start, end, band, stain = row
            entry = {"chromosome": chrom.removeprefix("chr"), "start": int(start), "end": int(end), "band": band, "stain": stain}
            cytobands.append(entry)
            bands_by_chrom.setdefault(entry["chromosome"], []).append(entry)

    genes = []
    unmatched = 0
    for _category, genes_path in GENE_SOURCES.items():
        with genes_path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                pos_fraction = _gene_position_fraction(r["chromosome"], r["map_location"], bands_by_chrom)
                if pos_fraction is None:
                    unmatched += 1
                genes.append(
                    {
                        "id": r["gene_id"],
                        "symbol": r["symbol"],
                        "chromosome": r["chromosome"],
                        "map_location": r["map_location"],
                        "description": r["description"] if r["description"] not in ("-", "") else None,
                        "type_of_gene": r["type_of_gene"],
                        "go_tags": r["go_tags"].split("|") if r["go_tags"] else [],
                        "confidence": _confidence(r["description"], r["type_of_gene"]),
                        "position_fraction": pos_fraction,
                    }
                )
    print(f"gene band matching: {len(genes) - unmatched}/{len(genes)} matched to a real cytoband, sources={list(GENE_SOURCES.keys())}")

    dataset = {
        "gene_count_total": len(genes),
        "genes": genes,
        "cytobands": cytobands,
    }
    GENOME_OUT.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    annotated = sum(1 for g in genes if g["confidence"] == "annotated")
    print(f"Wrote {GENOME_OUT} - {len(genes)} genes ({annotated} annotated, {len(genes) - annotated} hypothetical), {len(cytobands)} cytobands")


def build() -> None:
    build_macro()
    build_micro()
    build_genome()


if __name__ == "__main__":
    build()
