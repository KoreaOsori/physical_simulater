from fastapi.testclient import TestClient

from app.data.celegans_connectome import get_classic_ablations, get_connectome
from app.domain.schemas import Direction
from app.main import app
from app.simulation.hh_model import run_hh_trace

client = TestClient(app)


def test_classic_ablations_resolve_to_real_neuron_ids() -> None:
    connectome = get_connectome()
    neuron_ids = {n.id for n in connectome.neurons}
    ablations = get_classic_ablations()

    assert len(ablations) == 7
    for ablation in ablations:
        assert ablation.neuron_ids, f"{ablation.name} resolved to zero real neurons"
        for nid in ablation.neuron_ids:
            assert nid in neuron_ids, f"{ablation.name} references unknown neuron {nid}"


def test_classic_ablations_endpoint() -> None:
    response = client.get("/api/classic-ablations")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    names = {a["name"] for a in body}
    assert "후진 지휘 인터뉴런 (AVA/AVD/AVE)" in names


def test_silencing_the_stimulated_neuron_collapses_downstream_propagation() -> None:
    """The structural check this feature is actually for: silencing a
    neuron's outputs should measurably reduce how far the signal spreads,
    the same directional relationship a real laser ablation would produce
    -- not exact firing counts (no ground truth exists for those, see
    docs/18), just "silenced clearly propagates less than normal"."""
    baseline = run_hh_trace(Direction.FORWARD)
    baseline_neurons = {e.source for e in baseline if e.source}

    # AVBL is this pathway's actual stimulus source (engine.py) -- silencing
    # its own outputs should gut downstream propagation even though AVBL
    # itself still receives the injected current and still fires.
    silenced = run_hh_trace(Direction.FORWARD, silenced_neuron_ids=frozenset({"AVBL", "AVBR"}))
    silenced_neurons = {e.source for e in silenced if e.source}

    assert len(silenced_neurons) < len(baseline_neurons)


def test_silencing_unknown_neuron_id_is_a_harmless_noop() -> None:
    events = run_hh_trace(Direction.FORWARD, silenced_neuron_ids=frozenset({"NOT_A_REAL_NEURON"}))
    assert events[0].stage.value == "command"
