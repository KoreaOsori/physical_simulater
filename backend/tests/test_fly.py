from fastapi.testclient import TestClient

from app.data.drosophila_connectome import get_connectome, get_connectome_for_circuit
from app.main import app
from app.simulation.fly_engine import _NAV_PATHWAYS, _PATHWAYS, _VISUAL_PATHWAYS

client = TestClient(app)


def test_fly_connectome_loads_real_dataset() -> None:
    response = client.get("/api/fly/connectome")
    assert response.status_code == 200
    body = response.json()
    assert body["organism"] == "drosophila"
    assert body["is_placeholder"] is False
    # 2,452 olfactory (ORN/PN/KC/MBON/DAN) + 3,007 visual (VPN/DN) +
    # 896 navigation (ER/RING/PFN/PFL) — see build_drosophila_dataset.py and
    # SOURCES.md.
    assert body["neuron_count_total"] == 6355
    assert len(body["neurons"]) == 6355
    assert body["effector_count_total"] == 0
    assert len(body["synapses"]) > 200000
    cell_types = {n["cell_type"] for n in body["neurons"]}
    assert "LC4" in cell_types
    assert "Giant Fiber" in cell_types
    assert "EPG" in cell_types
    assert "PFL2" in cell_types


def test_fly_connectome_filters_by_circuit() -> None:
    """Each per-circuit page (see app/api/routes/fly.py) fetches only its own
    circuit's neurons/synapses, so payload size stays flat as more circuits
    are added — this guards that filtering actually works and drops the
    cross-circuit bridge synapses (whose other endpoint isn't in the
    filtered neuron set)."""
    olfactory = client.get("/api/fly/connectome", params={"circuit": "olfactory"}).json()
    visual = client.get("/api/fly/connectome", params={"circuit": "visual"}).json()
    navigation = client.get("/api/fly/connectome", params={"circuit": "navigation"}).json()

    assert len(olfactory["neurons"]) == 2452
    assert all(n["circuit"] == "olfactory" for n in olfactory["neurons"])
    assert len(olfactory["synapses"]) == 139496

    assert len(visual["neurons"]) == 3007
    assert all(n["circuit"] == "visual" for n in visual["neurons"])
    assert len(visual["synapses"]) == 28216

    assert len(navigation["neurons"]) == 896
    assert all(n["circuit"] == "navigation" for n in navigation["neurons"])
    assert len(navigation["synapses"]) == 39964

    invalid = client.get("/api/fly/connectome", params={"circuit": "nope"})
    assert invalid.status_code == 422


def test_get_connectome_for_circuit_drops_cross_circuit_bridge_synapses() -> None:
    full = get_connectome()
    olfactory = get_connectome_for_circuit("olfactory")
    visual = get_connectome_for_circuit("visual")
    navigation = get_connectome_for_circuit("navigation")
    assert len(olfactory.neurons) + len(visual.neurons) + len(navigation.neurons) == len(full.neurons)
    # the real bridge synapses (see SOURCES.md) only appear in the
    # unfiltered dataset, since one endpoint always belongs to another circuit.
    assert len(olfactory.synapses) + len(visual.synapses) + len(navigation.synapses) < len(full.synapses)


def test_fly_command_returns_event_trace() -> None:
    response = client.post("/api/fly/simulation/command", json={"stimulus": "DA1"})
    assert response.status_code == 200
    events = response.json()["events"]
    stages = [event["stage"] for event in events]
    assert stages[0] == "command"
    assert stages[-1] == "movement"


def test_fly_visual_command_returns_event_trace() -> None:
    response = client.post("/api/fly/simulation/command", json={"stimulus": "LC4"})
    assert response.status_code == 200
    body = response.json()
    assert body["stimulus"] == "LC4"
    events = body["events"]
    stages = [event["stage"] for event in events]
    assert stages[0] == "command"
    assert stages[-1] == "movement"


def test_fly_heading_command_returns_event_trace() -> None:
    response = client.post("/api/fly/simulation/command", json={"stimulus": "EPG_L4"})
    assert response.status_code == 200
    body = response.json()
    assert body["stimulus"] == "EPG_L4"
    events = body["events"]
    stages = [event["stage"] for event in events]
    assert stages[0] == "command"
    assert stages[-1] == "movement"


def test_fly_engine_odor_pathways_are_real_edges() -> None:
    """Guards against the illustrative odor->synapse mapping in fly_engine.py
    drifting out of sync with the dataset (e.g. after a dataset rebuild)."""
    connectome = get_connectome()
    node_ids = {n.id for n in connectome.neurons}
    edge_pairs = {(s.pre, s.post) for s in connectome.synapses}

    for odor, pathway in _PATHWAYS.items():
        assert pathway.pn in node_ids, f"{odor}: unknown PN id {pathway.pn}"
        assert pathway.kc in node_ids, f"{odor}: unknown KC id {pathway.kc}"
        assert pathway.mbon in node_ids, f"{odor}: unknown MBON id {pathway.mbon}"
        assert (pathway.pn, pathway.kc) in edge_pairs, f"{odor}: no such PN->KC synapse in the dataset"
        assert (pathway.kc, pathway.mbon) in edge_pairs, f"{odor}: no such KC->MBON synapse in the dataset"


def test_fly_engine_visual_pathways_are_real_edges() -> None:
    """Same guard as above for the visual VPN->DN one-hop pathways."""
    connectome = get_connectome()
    node_ids = {n.id for n in connectome.neurons}
    edge_pairs = {(s.pre, s.post) for s in connectome.synapses}

    for visual, pathway in _VISUAL_PATHWAYS.items():
        assert pathway.pre in node_ids, f"{visual}: unknown VPN id {pathway.pre}"
        assert pathway.post in node_ids, f"{visual}: unknown DN id {pathway.post}"
        assert (pathway.pre, pathway.post) in edge_pairs, f"{visual}: no such VPN->DN synapse in the dataset"


def test_fly_engine_heading_pathways_are_real_edges() -> None:
    """Same guard as above for the navigation EPG->PFL one-hop pathways."""
    connectome = get_connectome()
    node_ids = {n.id for n in connectome.neurons}
    edge_pairs = {(s.pre, s.post) for s in connectome.synapses}

    for heading, pathway in _NAV_PATHWAYS.items():
        assert pathway.pre in node_ids, f"{heading}: unknown EPG id {pathway.pre}"
        assert pathway.post in node_ids, f"{heading}: unknown PFL id {pathway.post}"
        assert (pathway.pre, pathway.post) in edge_pairs, f"{heading}: no such EPG->PFL synapse in the dataset"


def test_fly_neuron_types_and_counts_by_circuit_class() -> None:
    connectome = get_connectome()
    nt_counts: dict[str, int] = {}
    for n in connectome.neurons:
        nt_counts[n.neurotransmitter.value] = nt_counts.get(n.neurotransmitter.value, 0) + 1
    # Only DAN (PAM/PPL) neurons are labeled with a known neurotransmitter
    # (dopamine) — see SOURCES.md for why everything else (including the new
    # VPN/DN visual-circuit types) is "unknown".
    assert nt_counts.get("dopamine") == 322
    assert nt_counts.get("unknown", 0) + nt_counts.get("dopamine", 0) == len(connectome.neurons)
