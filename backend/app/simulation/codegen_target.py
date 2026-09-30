"""Brian2 codegen target selection, shared by hh_model.py and fly_hh_model.py.

Brian2's default pure-Python ("numpy") target works everywhere but is slow;
its "cython" target compiles each simulation step to C++ and is much faster,
but needs a working C++ compiler on the machine actually running the backend
(MSVC on Windows, gcc/clang on Linux/macOS). This project's Docker image
installs build-essential for exactly this reason, but the native Windows dev
flow (running `uvicorn` directly against the local venv) has no compiler
installed — see docs/09-visual-circuit-and-codegen.md.

Rather than a config flag the user has to remember to flip per-environment,
this detects the *actual* capability once per process by really compiling and
running a throwaway one-neuron network — not just checking whether a
compiler binary happens to be on PATH, since a partially-broken toolchain
would otherwise pass a PATH-only check and then fail on every real request.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from brian2 import Network, NeuronGroup, prefs
from brian2.units import ms

logger = logging.getLogger(__name__)


@lru_cache
def select_fastest_codegen_target() -> str:
    """Set Brian2's global codegen target to the fastest one this machine can
    actually compile and run, and return its name ("cython" or "numpy")."""
    prefs.codegen.target = "cython"
    try:
        probe = NeuronGroup(1, "dv/dt = -v/(10*ms) : 1", method="euler", name="codegen_probe")
        Network(probe).run(0 * ms)
    except Exception as exc:
        logger.info(
            "Brian2 cython (C++) codegen unavailable (%s: %s) - falling back to the numpy codegen target.",
            type(exc).__name__,
            exc,
        )
        prefs.codegen.target = "numpy"
        return "numpy"
    logger.info("Brian2 cython (C++) codegen is available on this machine - using it for HH network simulation.")
    return "cython"
