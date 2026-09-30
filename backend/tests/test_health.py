from fastapi.testclient import TestClient

from app.data.celegans_connectome import get_connectome
from app.main import app
from app.simulation.engine import _PATHWAYS

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_connectome_loads_real_dataset() -> None:
    response = client.get("/api/connectome")
    assert response.status_code == 200
    body = response.json()
    assert body["organism"] == "c_elegans"
    assert body["is_placeholder"] is False
    assert body["neuron_count_total"] == 302
    assert len(body["neurons"]) == 302
    assert body["effector_count_total"] == len(body["effectors"])
    assert len(body["synapses"]) > 5000


def test_command_returns_event_trace() -> None:
    response = client.post("/api/simulation/command", json={"direction": "forward"})
    assert response.status_code == 200
    events = response.json()["events"]
    stages = [event["stage"] for event in events]
    assert stages[0] == "command"
    assert stages[-1] == "movement"


def test_neurons_have_wbbt_ontology_descriptions() -> None:
    """Guards the WormBase anatomy ontology (WBbt) import — every neuron
    should resolve to a real definition; only CANL/CANR are expected to lack
    category tags (they're isolated, uncategorized in the source ontology)."""
    connectome = get_connectome()
    missing_description = [n.id for n in connectome.neurons if not n.description_en]
    missing_categories = [n.id for n in connectome.neurons if not n.categories_ko]

    assert missing_description == []
    assert set(missing_categories) <= {"CANL", "CANR"}


def test_engine_pathways_are_real_edges() -> None:
    """Guards against the illustrative command->synapse mapping in engine.py
    drifting out of sync with the dataset (e.g. after a dataset rebuild)."""
    connectome = get_connectome()
    node_ids = {n.id for n in connectome.neurons} | {e.id for e in connectome.effectors}
    edge_pairs = {(s.pre, s.post) for s in connectome.synapses}

    for direction, pathway in _PATHWAYS.items():
        assert pathway.pre in node_ids, f"{direction}: unknown pre id {pathway.pre}"
        assert pathway.post in node_ids, f"{direction}: unknown post id {pathway.post}"
        assert (pathway.pre, pathway.post) in edge_pairs, f"{direction}: no such synapse in the dataset"
