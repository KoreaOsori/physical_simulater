from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_compare_summary_has_all_three_species() -> None:
    response = client.get("/api/compare/summary")
    assert response.status_code == 200
    species = response.json()["species"]
    ids = [s["species_id"] for s in species]
    assert ids == ["c_elegans", "drosophila", "human"]


def test_compare_summary_dataset_counts_match_real_datasets() -> None:
    """Guards against the comparison numbers drifting out of sync with the
    actual datasets each species route already serves (e.g. after a rebuild
    changes neuron/synapse counts) -- these should never be hand-maintained
    constants that silently go stale."""
    response = client.get("/api/compare/summary")
    by_id = {s["species_id"]: s for s in response.json()["species"]}

    worm = by_id["c_elegans"]
    assert worm["dataset_neuron_count"] == 302
    assert worm["is_dataset_complete"] is True
    assert worm["real_world_neuron_count"] == 302

    fly = by_id["drosophila"]
    assert fly["dataset_neuron_count"] == client.get("/api/fly/connectome").json()["neuron_count_total"]
    assert fly["is_dataset_complete"] is False

    human = by_id["human"]
    assert human["dataset_neuron_count"] == client.get("/api/human/connectome/micro").json()["neuron_count_total"]
    assert human["dataset_region_count"] == client.get("/api/human/connectome/macro").json()["region_count_total"]
    assert human["real_world_neuron_count"] == 86_000_000_000
    # The whole point of this field split: never let the real-world number
    # collapse into (or get confused with) what the dataset actually holds.
    assert human["real_world_neuron_count"] > human["dataset_neuron_count"] * 1000
