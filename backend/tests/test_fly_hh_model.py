"""Integration test for the Drosophila HH network (app/simulation/fly_hh_model.py).

Runs the real per-circuit Brian2 networks end to end (olfactory/visual/
navigation subsets, each simulated separately — see
`fly_hh_model._build_network`'s per-circuit scoping and
build_drosophila_dataset.py) — this is slow (see that module's docstring for
the measured cost / codegen-target notes), so only one command per circuit is
exercised here, in the same test function so each circuit's network build is
only paid for once (`_build_network` is `@lru_cache`d per circuit).
"""

from app.domain.schemas import HeadingCommand, OdorCommand, SimulationStage, VisualCommand
from app.simulation.fly_engine import _NAV_PATHWAYS, _PATHWAYS, _VISUAL_PATHWAYS
from app.simulation.fly_hh_model import run_hh_trace


def _assert_valid_trace(events, seed_neuron_id: str) -> None:
    assert events[0].stage == SimulationStage.COMMAND
    assert events[-1].stage == SimulationStage.MOVEMENT
    times = [e.t_ms for e in events]
    assert times == sorted(times)

    synapse_events = [e for e in events if e.stage == SimulationStage.SYNAPSE]
    assert synapse_events, "expected at least the directly stimulated neuron to spike"
    assert synapse_events[0].source == seed_neuron_id


def test_odor_visual_and_heading_commands_produce_chronological_traces_from_real_stimulus_neurons() -> None:
    odor_events = run_hh_trace(OdorCommand.DA1)
    _assert_valid_trace(odor_events, _PATHWAYS[OdorCommand.DA1].pn)

    visual_events = run_hh_trace(VisualCommand.LC4)
    _assert_valid_trace(visual_events, _VISUAL_PATHWAYS[VisualCommand.LC4].pre)

    heading_events = run_hh_trace(HeadingCommand.EPG_L4)
    _assert_valid_trace(heading_events, _NAV_PATHWAYS[HeadingCommand.EPG_L4].pre)
