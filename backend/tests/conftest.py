import pytest

from app.simulation.hh_model import reset_habituation


@pytest.fixture(autouse=True)
def _reset_worm_habituation():
    """hh_model.py's habituation state (docs/29) is deliberate process-
    lifetime global state (no session concept exists in this app), which
    means it persists across tests in the same pytest run and would make
    tests order-dependent -- e.g. test_classic_ablations.py's baseline
    "forward" call would already be partially habituated by earlier tests'
    own "forward" calls. Reset before every test so each one starts from a
    known naive state."""
    reset_habituation()
    yield
