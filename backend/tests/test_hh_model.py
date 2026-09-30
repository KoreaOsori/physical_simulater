from app.domain.schemas import Direction, SimulationStage
from app.simulation.engine import _PATHWAYS
from app.simulation.hh_model import run_hh_trace


def test_forward_command_produces_chronological_trace() -> None:
    events = run_hh_trace(Direction.FORWARD)
    assert events[0].stage == SimulationStage.COMMAND
    assert events[-1].stage == SimulationStage.MOVEMENT
    times = [e.t_ms for e in events]
    assert times == sorted(times)


def test_stimulated_neuron_is_the_real_pathway_source() -> None:
    events = run_hh_trace(Direction.FORWARD)
    synapse_events = [e for e in events if e.stage == SimulationStage.SYNAPSE]
    assert synapse_events, "expected at least the directly stimulated neuron to spike"
    assert synapse_events[0].source == _PATHWAYS[Direction.FORWARD].pre


def test_synapse_events_reference_distinct_neurons() -> None:
    events = run_hh_trace(Direction.FORWARD)
    sources = [e.source for e in events if e.stage == SimulationStage.SYNAPSE]
    assert len(sources) == len(set(sources))


def test_stop_command_has_no_stimulus_and_short_trace() -> None:
    events = run_hh_trace(Direction.STOP)
    assert [e.stage for e in events] == [SimulationStage.COMMAND, SimulationStage.MOVEMENT]
