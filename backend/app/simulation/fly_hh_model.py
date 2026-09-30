"""Hodgkin-Huxley biophysical simulation of the imported Drosophila hemibrain
subsets (mirrors app/simulation/hh_model.py's role for v1).

Every neuron (olfactory: ORN/PN/KC/MBON/DAN; visual: VPN/DN; navigation:
ER/RING/PFN/PFL, see build_drosophila_dataset.py) is a Hodgkin-Huxley
compartment (Brian2), wired together by the real chemical synapses from
`drosophila_connectome.json` (see app/data/sources/drosophila/SOURCES.md —
hemibrain's public adjacency table doesn't distinguish gap junctions, so
unlike the C. elegans model there is no separate electrical-synapse
population here). A command injects a stimulus current into that stimulus's
real source neuron (the same neuron `fly_engine.py` uses, whether that's an
odor's PN, a visual command's VPN, or a heading command's EPG); resulting
network activity becomes the same `SimulationEvent` trace shape the API
already streams.

**Network scope**: `_build_network` is scoped to *one circuit at a time*
(via `get_connectome_for_circuit`), not the full merged dataset — an odor
command only ever needs the ~2,452-neuron olfactory network, a visual
command only the ~3,007-neuron visual one, a heading command only the
~896-neuron navigation one. This matters for scaling: without this split,
every command would pay to simulate the *other* circuits' neurons too, and
that cost would keep growing every time another circuit
subset gets merged into the dataset.

Known simplifications, same honesty-over-false-precision approach as
hh_model.py and SOURCES.md:

- Same standard Pospischil et al. 2008 cortical HH parameters as the C.
  elegans model — no Drosophila-neuron-specific membrane parameters are used
  (none are readily available at this granularity either).
- Same hand-tuned (not measured) synapse-count -> conductance scale factor as
  the C. elegans model, reused for now rather than independently re-tuned for
  this connectome's different weight distribution — a real gap, not hidden.
- **Measured cost**: this network is much larger than the 302-neuron/~6,600-
  synapse C. elegans one (~2-3s/command). Codegen target (numpy vs. cython/
  C++) is auto-detected once per process — see codegen_target.py — since the
  faster C++ target needs a compiler this project's native Windows dev flow
  doesn't have (Docker's image does). Expect several seconds to build the
  network plus a per-command run that scales with neuron/synapse count; a
  genuine performance cost of the larger network, not a bug — documented
  rather than hidden, per the project's "정직하게 밝히기" convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from brian2 import (
    Clock,
    NeuronGroup,
    Synapses,
    SpikeMonitor,
    Network,
    defaultclock,
    ms,
    mV,
    nS,
    nA,
    ufarad,
    msiemens,
    siemens,
    cm,
    umetre,
)

from app.data.drosophila_connectome import get_connectome_for_circuit
from app.domain.schemas import (
    CircuitName,
    FlyStimulus,
    HeadingCommand,
    OdorCommand,
    SimulationEvent,
    SimulationStage,
    VisualCommand,
)
from app.simulation.codegen_target import select_fastest_codegen_target
from app.simulation.fly_engine import (
    _NAV_LABELS,
    _NAV_PATHWAYS,
    _ODOR_LABELS,
    _PATHWAYS,
    _VISUAL_LABELS,
    _VISUAL_PATHWAYS,
)

select_fastest_codegen_target()
defaultclock.dt = 0.05 * ms

# --- Standard HH (Pospischil et al. 2008) cortical-neuron parameters, as used
# in Brian2's own HH tutorial and hh_model.py ---
_AREA = 20000 * umetre**2
_CM = 1 * ufarad * cm**-2 * _AREA
_GL = 5e-5 * siemens * cm**-2 * _AREA
_EL = -65 * mV
_EK = -90 * mV
_ENA = 50 * mV
_G_NA = 100 * msiemens * cm**-2 * _AREA
_G_KD = 30 * msiemens * cm**-2 * _AREA
_VT = -63 * mV

_STIMULUS_CURRENT = 0.6 * nA
_STIMULUS_DURATION = 20 * ms
_SIM_DURATION = 100 * ms

_CHEM_NS_PER_WEIGHT = 0.28
_MAX_EFFECTIVE_WEIGHT = 20
_TAU_SYN = 5 * ms
_E_EXCITATORY = 0 * mV

_HH_EQS = """
dv/dt = (gl*(El-v) - g_na*(m*m*m)*h*(v-ENa) - g_kd*(n*n*n*n)*(v-EK) + I + I_syn)/Cm : volt
dm/dt = alpha_m*(1-m) - beta_m*m : 1
dn/dt = alpha_n*(1-n) - beta_n*n : 1
dh/dt = alpha_h*(1-h) - beta_h*h : 1
alpha_m = 0.32*(mV**-1)*(13*mV-v+VT)/(exp((13*mV-v+VT)/(4*mV))-1.)/ms : Hz
beta_m = 0.28*(mV**-1)*(v-VT-40*mV)/(exp((v-VT-40*mV)/(5*mV))-1)/ms : Hz
alpha_h = 0.128*exp((17*mV-v+VT)/(18*mV))/ms : Hz
beta_h = 4./(1+exp((40*mV-v+VT)/(5*mV)))/ms : Hz
alpha_n = 0.032*(mV**-1)*(15*mV-v+VT)/(exp((15*mV-v+VT)/(5*mV))-1.)/ms : Hz
beta_n = .5*exp((10*mV-v+VT)/(40*mV))/ms : Hz
I : amp
I_syn : amp
gl : siemens
Cm : farad
g_na : siemens
g_kd : siemens
El : volt
EK : volt
ENa : volt
VT : volt
"""

_CHEM_SYN_EQS = """
dg/dt = -g/tau_syn : siemens (clock-driven)
w : siemens
Esyn : volt
tau_syn : second
I_syn_post = g*(Esyn-v_post) : amp (summed)
"""


@dataclass
class _NetworkAssets:
    neuron_ids: list[str]
    index_of: dict[str, int]
    group: NeuronGroup
    net: Network


def _construct_network_assets(circuit: CircuitName) -> _NetworkAssets:
    """Builds one fresh, independent Brian2 network scoped to just that
    circuit's own neurons/synapses — not the full merged dataset. Pulled out
    of `_build_network()` (which `@lru_cache`s a single shared instance per
    circuit, reused by every request-scoped command) so a continuously-
    stepped simulation -- the virtual-fly closed loop in
    `app/lab/virtual_fly.py` -- can get its OWN `_NetworkAssets` instead of
    sharing membrane/gating state with `run_hh_trace`'s per-command
    singleton (same reasoning as hh_model.py's identical split for the C.
    elegans network, docs/41).

    Also gives each call its own dedicated `Clock` rather than the implicit
    process-global `defaultclock` -- real bug found while building this
    module's closed loop (docs/42): sharing one clock across many
    independently-constructed networks over a long-lived server process
    eventually made a live request fail with Brian2's
    `StopIteration("Clock has reached the end of its available times.")`.
    See hh_model.py's identical fix for the full writeup."""
    connectome = get_connectome_for_circuit(circuit)
    neuron_ids = [n.id for n in connectome.neurons]
    index_of = {nid: i for i, nid in enumerate(neuron_ids)}
    n = len(neuron_ids)

    clock = Clock(dt=defaultclock.dt)
    group = NeuronGroup(
        n,
        _HH_EQS,
        threshold="v > -20*mV",
        refractory="v > -20*mV",
        method="exponential_euler",
        name="fly_neurons",
        clock=clock,
    )
    group.v = _EL
    group.h = 1
    group.m = 0
    group.n = 0
    group.gl = _GL
    group.Cm = _CM
    group.g_na = _G_NA
    group.g_kd = _G_KD
    group.El = _EL
    group.EK = _EK
    group.ENa = _ENA
    group.VT = _VT

    chem_pre: list[int] = []
    chem_post: list[int] = []
    chem_w: list[float] = []
    for s in connectome.synapses:
        weight = min(s.weight, _MAX_EFFECTIVE_WEIGHT)
        chem_pre.append(index_of[s.pre])
        chem_post.append(index_of[s.post])
        chem_w.append(weight * _CHEM_NS_PER_WEIGHT)

    chem_synapses = Synapses(group, group, model=_CHEM_SYN_EQS, on_pre="g += w", method="exact", name="chem_syn", clock=clock)
    chem_synapses.connect(i=chem_pre, j=chem_post)
    chem_synapses.w = np.array(chem_w) * nS
    chem_synapses.tau_syn = _TAU_SYN
    chem_synapses.Esyn = _E_EXCITATORY

    spikes = SpikeMonitor(group, name="spikemon")  # follows group's own clock automatically
    net = Network(group, chem_synapses, spikes)
    net.store("initial")

    return _NetworkAssets(neuron_ids=neuron_ids, index_of=index_of, group=group, net=net)


@lru_cache
def _build_network(circuit: CircuitName) -> _NetworkAssets:
    """The one shared network instance every existing command uses (cached
    per circuit). `run_hh_trace` calls this, not the factory directly, so
    its behavior is unchanged. New code that needs an independent,
    continuously-run network should call `_construct_network_assets()`
    directly instead."""
    return _construct_network_assets(circuit)


def run_hh_trace(stimulus: FlyStimulus, max_synapse_events: int = 20) -> list[SimulationEvent]:
    """Simulate the real network for one odor/visual command and return a
    SimulationEvent trace shaped exactly like `fly_engine.build_trace`'s
    output."""
    if isinstance(stimulus, VisualCommand):
        pathway = _VISUAL_PATHWAYS[stimulus]
        label = _VISUAL_LABELS[stimulus]
        seed_neuron = pathway.pre
        command_message = f"'{label}' 시각 자극이 시엽(optic lobe) 출력 채널에 입력되었습니다."
        circuit: CircuitName = "visual"
    elif isinstance(stimulus, HeadingCommand):
        pathway = _NAV_PATHWAYS[stimulus]
        label = _NAV_LABELS[stimulus]
        seed_neuron = pathway.pre
        command_message = f"'{label}' 나침반 웨지에 헤딩 자극이 입력되었습니다."
        circuit = "navigation"
    else:
        pathway = _PATHWAYS[stimulus]
        label = _ODOR_LABELS[stimulus]
        seed_neuron = pathway.pn
        command_message = f"'{label}' 냄새 자극이 촉각엽(antennal lobe)에 입력되었습니다."
        circuit = "olfactory"

    events = [SimulationEvent(t_ms=0, stage=SimulationStage.COMMAND, message=command_message)]

    assets = _build_network(circuit)
    if seed_neuron not in assets.index_of:
        raise KeyError(f"Stimulus neuron {seed_neuron} not found in the simulated network")
    seed_index = assets.index_of[seed_neuron]

    assets.net.restore("initial")
    assets.group.I[seed_index] = _STIMULUS_CURRENT
    assets.net.run(_STIMULUS_DURATION)
    assets.group.I[seed_index] = 0 * nA
    assets.net.run(_SIM_DURATION - _STIMULUS_DURATION)

    spikes = assets.net["spikemon"]
    spike_indices = np.array(spikes.i)
    spike_times = np.array(spikes.t / ms)
    order = np.argsort(spike_times)

    seen_neurons: set[str] = set()
    synapse_events = 0

    for idx in order:
        if synapse_events >= max_synapse_events:
            break
        neuron_id = assets.neuron_ids[spike_indices[idx]]
        if neuron_id in seen_neurons:
            continue
        t_ms = 12.4 + float(spike_times[idx])
        if neuron_id == seed_neuron:
            message = f"{neuron_id}: 자극 전류 주입으로 활동전위가 발생했습니다."
        else:
            message = f"{neuron_id}: 막전위가 역치를 넘어 활동전위가 발생했습니다."
        events.append(
            SimulationEvent(
                t_ms=round(t_ms, 1),
                stage=SimulationStage.SYNAPSE,
                source=neuron_id,
                message=message,
            )
        )
        seen_neurons.add(neuron_id)
        synapse_events += 1

    if isinstance(stimulus, VisualCommand):
        final_message = f"{label}에 대한 도피/추적 행동 신호가 발현되었습니다."
    elif isinstance(stimulus, HeadingCommand):
        final_message = f"{label}에 대한 조향(steering) 신호가 발현되었습니다."
    else:
        final_message = f"{label}에 대한 행동 유의성(valence) 신호가 발현되었습니다."
    events.append(SimulationEvent(t_ms=_SIM_DURATION / ms, stage=SimulationStage.MOVEMENT, message=final_message))
    return [events[0]] + sorted(events[1:-1], key=lambda e: e.t_ms) + [events[-1]]
