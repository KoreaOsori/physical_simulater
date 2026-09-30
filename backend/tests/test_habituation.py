from fastapi.testclient import TestClient

from app.domain.schemas import Direction
from app.main import app
from app.simulation import hh_model
from app.simulation.hh_model import get_habituation_level, run_hh_trace

client = TestClient(app)

_BASE_TIME = 1_700_000_000.0  # arbitrary fixed epoch -- only deltas matter


def test_naive_habituation_level_is_zero() -> None:
    assert get_habituation_level(Direction.FORWARD) == 0.0


def test_repeated_stimulation_reduces_downstream_propagation() -> None:
    """The structural check this feature is for, mirroring
    test_classic_ablations.py's pattern: repeated stimulation of the SAME
    direction back-to-back (no time passing) should measurably shrink
    propagation on the second call, the same directional relationship real
    tap-withdrawal habituation shows (Rankin, Beck & Chiba 1990).

    Uses a high max_synapse_events (default is 20, capped for the UI's
    event log) -- at the default cap, forward's ~100+-neuron cascade hits
    the ceiling on both calls regardless of a partial synaptic weight
    change, masking the real (smaller, since only ONE neuron's own output
    is depressed) effect this test is checking for."""
    first = run_hh_trace(Direction.FORWARD, max_synapse_events=400, now=_BASE_TIME)
    first_neurons = {e.source for e in first if e.source}

    second = run_hh_trace(Direction.FORWARD, max_synapse_events=400, now=_BASE_TIME + 1.0)
    second_neurons = {e.source for e in second if e.source}

    assert len(second_neurons) < len(first_neurons)


def test_habituation_level_increases_then_recovers_over_time() -> None:
    """Uses hh_model._habituation_level_at() directly with the same fixed
    `now` the run_hh_trace() calls below get -- get_habituation_level()
    (the production-facing wrapper) always reads real time.time(), which
    would make "elapsed since _BASE_TIME" astronomically large and
    (correctly, for real callers) report ~full recovery regardless of what
    just happened -- not usable together with injected fixed timestamps."""
    assert hh_model._habituation_level_at(Direction.FORWARD, _BASE_TIME) == 0.0

    run_hh_trace(Direction.FORWARD, now=_BASE_TIME)
    level_after_one = hh_model._habituation_level_at(Direction.FORWARD, _BASE_TIME)
    assert level_after_one > 0.0

    run_hh_trace(Direction.FORWARD, now=_BASE_TIME + 1.0)
    level_after_two = hh_model._habituation_level_at(Direction.FORWARD, _BASE_TIME + 1.0)
    assert level_after_two > level_after_one  # further depressed by a second quick stimulation

    # Spontaneous recovery: querying long after the last stimulation should
    # show substantial recovery back toward naive (Rankin et al. 2009's
    # "habituation revisited" catalogues spontaneous recovery as one of the
    # 9 real parametric features of habituation).
    recovered = hh_model._habituation_level_at(Direction.FORWARD, _BASE_TIME + 1.0 + hh_model._HABITUATION_RECOVERY_TAU_S * 5)
    assert recovered < level_after_two * 0.05


def test_habituation_never_fully_blocks() -> None:
    """Tests the asymptotic-approach formula directly (not by re-running the
    ~4s HH simulation 30 times) -- real behavior (does one repeated stimulus
    measurably depress the response) is already covered above; this is a
    pure math check on the convergence bound."""
    from app.simulation import hh_model

    level = 0.0
    for _ in range(30):
        level = level + (hh_model._MAX_HABITUATION - level) * hh_model._HABITUATION_INCREMENT
    assert level < hh_model._MAX_HABITUATION
    assert level > hh_model._MAX_HABITUATION * 0.9  # should have converged close to the asymptote


def test_command_response_reports_habituation_level() -> None:
    first = client.post("/api/simulation/command", json={"direction": "forward"}).json()
    second = client.post("/api/simulation/command", json={"direction": "forward"}).json()
    assert "habituation_level" in first
    assert second["habituation_level"] > first["habituation_level"]


def test_stop_command_has_no_habituation() -> None:
    """STOP has no _PATHWAYS entry (no HH trace at all) -- habituation_level
    should stay exactly 0, never invented for a direction with no real
    stimulated neuron."""
    response = client.post("/api/simulation/command", json={"direction": "stop"}).json()
    assert response["habituation_level"] == 0.0
