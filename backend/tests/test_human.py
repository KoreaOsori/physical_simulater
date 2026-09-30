from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_human_macro_connectome_loads_real_data() -> None:
    response = client.get("/api/human/connectome/macro")
    assert response.status_code == 200
    body = response.json()
    # All seven Yeo-7 networks now vendored — region counts sum to exactly
    # 400, the real Schaefer 400-parcel atlas's full parcel count.
    assert set(body["networks"]) == {"Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default"}
    assert body["region_count_total"] == 400
    assert len(body["regions"]) == 400
    # docs/49: 원본 HCP 합의 행렬 전체(5,059개). 이전엔 네트워크 내부 간선 2,041개만 있었고 이 테스트도
    # "간선은 네트워크를 넘지 않는다"고 단정했었다 -- 원본엔 네트워크를 잇는 간선이 3,018개 있다.
    assert len(body["edges"]) == 5059
    names = {r["name"] for r in body["regions"]}
    assert "7Networks_LH_Vis_1" in names
    assert "7Networks_LH_Limbic_TempPole_1" in names
    assert any(n.startswith("7Networks_LH_Default_") for n in names)
    # every edge must reference a real region id in this same response
    regions_by_id = {r["id"]: r for r in body["regions"]}
    for e in body["edges"]:
        assert e["a"] in regions_by_id
        assert e["b"] in regions_by_id
    within = sum(regions_by_id[e["a"]]["network"] == regions_by_id[e["b"]]["network"] for e in body["edges"])
    assert (within, len(body["edges"]) - within) == (2041, 3018)
    # 400개 영역이 하나의 그래프로 이어져야 한다(이전엔 8조각)
    adj: dict[str, set[str]] = {rid: set() for rid in regions_by_id}
    for e in body["edges"]:
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])
    seen, stack = {"1"}, ["1"]
    while stack:
        for nb in adj[stack.pop()] - seen:
            seen.add(nb)
            stack.append(nb)
    assert len(seen) == 400

    # Every region should resolve to a real AAL anatomical label (all 400 did
    # in a full build — see SOURCES.md's "개별 영역 해부학 라벨" section) —
    # not fabricated per-parcel text, a real coordinate lookup.
    vis1 = next(r for r in body["regions"] if r["name"] == "7Networks_LH_Vis_1")
    assert vis1["anatomical_label"] is not None
    assert vis1["anatomical_note"]
    for r in body["regions"]:
        # a region is either honestly unresolved (both null) or fully labeled
        assert (r["anatomical_label"] is None) == (r["anatomical_note"] is None)


def test_human_macro_anatomy_mesh_is_real_and_consistent() -> None:
    body = client.get("/api/human/connectome/macro").json()
    anatomy = body["anatomy"]
    for layer_name in ("skin", "brain", "gray_matter"):
        layer = anatomy[layer_name]
        assert layer["vertex_count"] > 1000
        assert layer["triangle_count"] > 0
        assert len(layer["positions"]) == layer["vertex_count"] * 3
        assert len(layer["indices"]) == layer["triangle_count"] * 3
        assert max(layer["indices"]) < layer["vertex_count"]
    assert "MNI152NLin2009cAsym" in anatomy["source"]
    # the h01 hint must sit near the real region set (same scene scale), not
    # at some unrelated origin/placeholder
    hint = anatomy["h01_region_hint"]
    assert all(abs(hint[axis]) < 5 for axis in ("x", "y", "z"))


def test_human_macro_known_disorders_resolve_to_real_regions() -> None:
    body = client.get("/api/human/connectome/macro").json()
    disorders = body["known_disorders"]
    assert len(disorders) > 0
    region_ids = {r["id"] for r in body["regions"]}

    real_networks = set(body["networks"])
    real_lobes = {"frontal", "parietal", "temporal", "occipital"}
    categories = set()
    for d in disorders:
        assert d["category"] in ("focal", "complex")
        categories.add(d["category"])
        assert len(d["region_ids"]) > 0
        # every region_id must be a real region actually in this response —
        # never a fabricated/placeholder id
        for rid in d["region_ids"]:
            assert rid in region_ids
        assert "원인" in d["description"]  # every entry's honesty caveat mentions cause/complexity
        # focal -> a real single network (majority vote); complex -> always null
        if d["category"] == "focal":
            assert d["primary_network"] in real_networks
            # primary_lobe is null only when every matched region falls
            # outside the 4 classical lobes (e.g. an Insula-only entry) —
            # never forced into a lobe, but when set it must be real.
            if d["primary_lobe"] is not None:
                assert d["primary_lobe"] in real_lobes
        else:
            assert d["primary_network"] is None
            assert d["primary_lobe"] is None

    # both categories must be represented, and kept honestly distinct
    assert categories == {"focal", "complex"}

    # the user's own worked example: achromatopsia should implicate the real
    # Vis_1/Vis_4 regions (Fusiform/Lingual — real V4-adjacent color areas)
    # and, since the large majority of its regions are real Vis parcels,
    # should be grouped under the Vis network.
    achromatopsia = next(d for d in disorders if "Achromatopsia" in d["name"])
    region_names = {r["id"]: r["name"] for r in body["regions"]}
    implicated_names = {region_names[rid] for rid in achromatopsia["region_ids"]}
    assert "7Networks_LH_Vis_1" in implicated_names
    assert "7Networks_LH_Vis_4" in implicated_names
    assert achromatopsia["primary_network"] == "Vis"


def test_human_macro_known_disorders_cover_every_yeo7_network() -> None:
    # docs/33: SalVentAttn had zero disorders before this expansion — a real
    # gap the new Ageusia (insula) entry was specifically chosen to fill
    # (11 of ~18 real Insula-labeled parcels in this dataset fall in
    # SalVentAttn, confirmed by direct computation before writing this).
    body = client.get("/api/human/connectome/macro").json()
    focal_networks = {d["primary_network"] for d in body["known_disorders"] if d["category"] == "focal"}
    assert focal_networks == set(body["networks"])  # every real Yeo-7 network has at least one focal disorder now


def test_human_micro_sample_loads_real_data() -> None:
    response = client.get("/api/human/connectome/micro")
    assert response.status_code == 200
    body = response.json()
    assert body["source_region"] == "temporal_cortex"
    assert body["neuron_count_total"] == 104
    assert body["point_count_total"] == len(body["points"])
    assert body["point_count_total"] > 10000


def test_human_micro_synapses_are_real_and_correctly_placed() -> None:
    """Regression test for the empirically-verified coordinate correction in
    build_human_dataset.py (raw location.x/4, y/4, z as-is — see SOURCES.md's
    "실제 시냅스 접촉점" section): every synapse's real 3D position must land
    near its own neuron's real skeleton points, in the SAME scene frame — not
    off in unrelated space, which is what an unfixed 4x scale bug would look
    like."""
    body = client.get("/api/human/connectome/micro").json()
    assert body["synapse_count_total"] == len(body["synapses"])
    # Full 166-shard scan (fetch_h01_synapses.py), not an estimate: 166,216,068
    # real records scanned, 86,438 touch one of the 104 proofread neurons.
    assert body["synapse_count_total"] == 86438

    # The full scan found zero real synapses where BOTH sides are among the
    # 104 proofread neurons (see SOURCES.md) — confirms none of the 86,438
    # partners are proofread either, across the ENTIRE dataset, not a sample.
    assert all(not s["partner_is_proofread"] for s in body["synapses"])

    real_neuron_ids = {p["neuron_id"] for p in body["points"]}
    points_by_neuron: dict[str, list[dict]] = {}
    for p in body["points"]:
        points_by_neuron.setdefault(p["neuron_id"], []).append(p["position"])

    checked = 0
    for s in body["synapses"][:2000]:  # bound the check — thousands is plenty to catch a systematic transform bug
        assert s["role"] in ("AXON", "DENDRITE")
        assert s["neuron_id"] in real_neuron_ids
        neuron_points = points_by_neuron[s["neuron_id"]]
        xs = [p["x"] for p in neuron_points]
        ys = [p["y"] for p in neuron_points]
        zs = [p["z"] for p in neuron_points]
        margin = 0.5  # scene units — generous vs. the neuron's own real bounding box, still catches a 4x-off bug
        pos = s["position"]
        assert min(xs) - margin <= pos["x"] <= max(xs) + margin
        assert min(ys) - margin <= pos["y"] <= max(ys) + margin
        assert min(zs) - margin <= pos["z"] <= max(zs) + margin
        checked += 1
    assert checked > 0


def test_human_genome_loads_real_data() -> None:
    response = client.get("/api/human/genome")
    assert response.status_code == 200
    body = response.json()
    assert body["gene_count_total"] == 646  # 511 nervous-system + 135 new visual-perception genes
    assert len(body["genes"]) == 646
    assert len(body["cytobands"]) > 0

    bdnf = next(g for g in body["genes"] if g["symbol"] == "BDNF")
    assert bdnf["chromosome"] == "11"
    assert bdnf["map_location"] == "11p14.1"
    assert bdnf["confidence"] == "annotated"
    assert bdnf["position_fraction"] is not None
    assert 0 <= bdnf["position_fraction"] <= 1

    # a real visual-perception (GO:0007601) gene not in the original 511 —
    # confirms the 2nd-pass category actually merged in, not just a count bump
    abca4 = next(g for g in body["genes"] if g["symbol"] == "ABCA4")
    assert "visual_perception" in abca4["go_tags"]

    # every gene's confidence label must be one of the two real, defensible
    # values — not something invented per-gene by this project (see
    # app/data/sources/human/SOURCES.md's "미확인/가설 라벨 기준").
    assert {g["confidence"] for g in body["genes"]} <= {"annotated", "hypothetical"}


def test_human_genome_bdnf_command_returns_event_trace() -> None:
    response = client.post("/api/human/genome/pathway/command", json={"stimulus": "BDNF_ACTIVATION"})
    assert response.status_code == 200
    body = response.json()
    assert body["stimulus"] == "BDNF_ACTIVATION"
    events = body["events"]
    stages = [e["stage"] for e in events]
    assert stages[0] == "command"
    assert stages[-1] == "movement"
    times = [e["t_ms"] for e in events]
    assert times == sorted(times)
    # the real gene IDs referenced must be the real NCBI GeneIDs for
    # BDNF/CREB1/NTRK2, verifiable against the genome endpoint
    genome = client.get("/api/human/genome").json()
    bdnf_id = next(g["id"] for g in genome["genes"] if g["symbol"] == "BDNF")
    sources_and_targets = {e["source"] for e in events if e["source"]} | {e["target"] for e in events if e["target"]}
    assert bdnf_id in sources_and_targets


def test_human_genome_arc_command_returns_event_trace() -> None:
    response = client.post("/api/human/genome/pathway/command", json={"stimulus": "ARC_PLASTICITY_ACTIVATION"})
    assert response.status_code == 200
    body = response.json()
    assert body["stimulus"] == "ARC_PLASTICITY_ACTIVATION"
    events = body["events"]
    stages = [e["stage"] for e in events]
    assert stages[0] == "command"
    assert stages[-1] == "movement"
    times = [e["t_ms"] for e in events]
    assert times == sorted(times)
    # GRIN2B is in the main gene pool (unlike CAMK2A/ARC, same situation as
    # CREB1/NTRK2 for BDNF above) -- verifiable against the genome endpoint.
    genome = client.get("/api/human/genome").json()
    grin2b_id = next(g["id"] for g in genome["genes"] if g["symbol"] == "GRIN2B")
    sources_and_targets = {e["source"] for e in events if e["source"]} | {e["target"] for e in events if e["target"]}
    assert grin2b_id in sources_and_targets
    # CAMK2A (815) and ARC (23237) -- real NCBI GeneIDs, see
    # app/data/sources/human/arc_plasticity_genes.csv.
    assert "815" in sources_and_targets
    assert "23237" in sources_and_targets
