"""Hodgkin-Huxley biophysical simulation of the imported C. elegans connectome.

Replaces the rule-based single-edge narration in `engine.py` with an actual
network simulation: every one of the 302 neurons is a Hodgkin-Huxley
compartment (Brian2), wired together by the *real* 5,806 neuron-to-neuron
synapses from `celegans_connectome.json` (chemical, conductance-based;
electrical, direct gap-junction coupling). A command injects a stimulus
current into that command's real source neuron (the same `pre` neuron
`engine.py` uses); the resulting network activity is recorded and converted
into the same `SimulationEvent` shape the API already streams, so nothing
downstream (API route, WebSocket, frontend) needs to change to switch engines.

Known simplifications (honesty over false precision, matching this project's
approach elsewhere — see app/data/sources/SOURCES.md):

- **C. elegans neurons are mostly non-spiking** (they signal via graded
  potentials, not classical all-or-none action potentials). Using a spiking
  Hodgkin-Huxley model was requested for v1 by the project owner as the
  target simulation fidelity; it is a deliberate modeling choice, not a claim
  that real C. elegans neurons fire like this.
- HH membrane parameters are the standard Pospischil et al. 2008 cortical-
  neuron values (as used in Brian2's own HH tutorial), not values measured
  from C. elegans — no per-neuron biophysical parameter set for this animal
  is publicly available at this granularity.
- Synaptic *weight* comes from real EM-reconstructed synapse counts, but the
  conversion from "synapse count" to "conductance in nS" (`_CHEM_NS_PER_WEIGHT`,
  `_GAP_NS_PER_WEIGHT` below) is a tuned-by-hand scale factor, not a measured
  quantity — nobody has published per-synapse conductance for this connectome.
- Chemical synapses are treated as excitatory (reversal 0 mV) unless the
  presynaptic neuron's neurotransmitter is GABA (reversal -70 mV, inhibitory).
  Real receptor pharmacology is more varied (e.g. some ACh receptors are
  inhibitory); this is a coarse but standard approximation. docs/46 showed
  this makes every input that reaches the command layer bias toward
  reversal; docs/47 adds an opt-in `sign_model="receptor_predicted"` that
  uses Fenyves et al. 2020's per-synapse polarity predictions (postsynaptic
  receptor expression) -- used by the virtual-worm closed loop only.
- Effectors (muscles etc.) are not simulated as HH compartments — they have
  no membrane dynamics here. A muscle is reported as activated if a neuron
  that spiked during the simulation window synapses onto it (using the real
  neuron -> effector edges), which is a presence/absence signal, not a
  contraction magnitude.

Codegen target (numpy vs. cython/C++) is auto-detected once per process by
`codegen_target.select_fastest_codegen_target()` — see that module's
docstring. At 302 neurons / ~100 ms this network is fast enough either way;
the C++ target mainly matters for the much larger Drosophila v2 network (see
fly_hh_model.py).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

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

from app.data.celegans_connectome import get_connectome
from app.domain.schemas import Direction, Neurotransmitter, SimulationEvent, SimulationStage
from app.simulation.codegen_target import select_fastest_codegen_target
from app.simulation.engine import _DIRECTION_LABELS, _PATHWAYS

SignModel = Literal["gaba_only", "receptor_predicted"]

select_fastest_codegen_target()
defaultclock.dt = 0.05 * ms

# --- Standard HH (Pospischil et al. 2008) cortical-neuron parameters, as used
# in Brian2's own HH tutorial ---
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

# Hand-tuned (not measured) conversion from "EM synapse count" to conductance.
#
# A real C. elegans-specific literature value DOES exist for this general
# quantity -- Wicks, Roehrig & Rankin 1996 (J Neurosci 16(12):4017-4031, the
# tap-withdrawal circuit model) report ~0.6 nS per individual chemical
# synaptic contact (scaled from Ascaris electrophysiology by body-length
# ratio) and a flat 5 nS per gap junction. It is deliberately NOT substituted
# in here: that value was calibrated against THEIR specific membrane model
# (a 2-compartment graded-potential neuron with leak conductance/capacitance
# also derived from Ascaris), not the generic Pospischil et al. 2008 cortical
# HH membrane parameters this file uses (_AREA/_CM/_GL/_G_NA/_G_KD above,
# also not C. elegans-specific). A conductance value is only physically
# meaningful relative to the membrane RC time constant it was fit against --
# dropping 0.6 nS into a differently-scaled membrane wouldn't make this model
# more real, just differently arbitrary. Searched and found real (see
# docs/22-worm-locomotion-real-speed-grounding.md), but honestly not
# portable without also re-deriving the membrane parameters to match, which
# is out of scope here.
_CHEM_NS_PER_WEIGHT = 0.28
_GAP_NS_PER_WEIGHT = 0.015
_MAX_EFFECTIVE_WEIGHT = 20  # clip outlier synapse counts (max in data is 142)
_TAU_SYN = 5 * ms
_E_EXCITATORY = 0 * mV
_E_INHIBITORY = -70 * mV

_HH_EQS = """
dv/dt = (gl*(El-v) - g_na*(m*m*m)*h*(v-ENa) - g_kd*(n*n*n*n)*(v-EK) + I + I_syn + I_gap)/Cm : volt
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
I_gap : amp
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

_GAP_SYN_EQS = """
w : siemens
I_gap_post = w*(v_pre-v_post) : amp (summed)
"""


@dataclass
class _NetworkAssets:
    neuron_ids: list[str]
    index_of: dict[str, int]
    group: NeuronGroup
    net: Network
    neuron_to_effectors: dict[str, list[str]]  # for the post-hoc muscle stage
    # Source-neuron index per synapse, in the same order as chem_syn/gap_syn's
    # own connection order (Synapses.connect(i=..., j=...) preserves input
    # order) — lets run_hh_trace silence a neuron's OUTPUTS post-restore
    # without rebuilding the ~6,600-synapse network (see "ablation" below).
    chem_pre: np.ndarray
    gap_pre: np.ndarray


@lru_cache
def _receptor_predicted_signs() -> dict[str, str]:
    """Fenyves et al. 2020(PLOS Comput Biol 16:e1007974)의 시냅스별 극성 예측(docs/47).
    `scripts/build_synapse_signs.py`가 원 논문 S1 Data에서 그대로 옮긴 값."""
    path = Path(__file__).resolve().parents[1] / "data" / "celegans_synapse_signs.json"
    return json.loads(path.read_text(encoding="utf-8"))["signs"]


def _is_inhibitory(pre: str, post: str, neurotransmitter: Neurotransmitter, sign_model: SignModel) -> bool:
    """시냅스 부호 규칙.

    - "gaba_only"(기본, 기존 동작): GABA만 억제성.
    - "receptor_predicted"(docs/47, 가상 웜 폐루프 전용): 시냅스 후 수용체 발현 기반 예측이 "+"면
      흥분성, "-"면 억제성(글루탐산 개폐 염소채널 GluCl, 아세틸콜린 개폐 염소채널 ACC 등 --
      예: AWC->AIY는 "-"로 Chalasani et al. 2007과 일치). 예측이 "complex"(한 신경전달물질에
      흥분·억제 수용체가 둘 다 있음)거나 없으면 추측하지 않고 기존 규칙으로 둔다.
    """
    if sign_model == "receptor_predicted":
        sign = _receptor_predicted_signs().get(f"{pre}>{post}")
        if sign == "+":
            return False
        if sign == "-":
            return True
    return neurotransmitter == Neurotransmitter.GABA


def _construct_network_assets(sign_model: SignModel = "gaba_only") -> _NetworkAssets:
    """Build one fresh, independent Brian2 network over the real connectome.

    `sign_model` picks the chemical-synapse sign rule (see `_is_inhibitory`).
    The default keeps every existing, already-validated feature (worm page
    commands, virtual lab, classic ablations) on the original GABA-only rule;
    only callers that opt in get receptor-predicted signs (docs/47).

    Pulled out of `_build_network()` (which `@lru_cache`s a single shared
    instance reused by every request-scoped command in this file) so a
    long-lived, continuously-stepped simulation -- the virtual-worm closed
    loop in `app/lab/virtual_worm.py` -- can get its OWN `_NetworkAssets`
    instead of sharing state with `run_hh_trace`'s per-command singleton.
    Two independent `Network` objects can coexist in the same Brian2 process
    (each owns its own `NeuronGroup`/`Synapses` state); what Brian2 forbids
    is reusing one already-simulated `NeuronGroup` across networks.

    **Each call gets its own dedicated `Clock`** rather than the implicit
    process-global `defaultclock` every `NeuronGroup` uses by default. Real
    bug this fixes (found while building the Drosophila equivalent,
    docs/42): every network built by this function used to share ONE clock
    object across the whole process. After enough accumulated
    restore()+run() cycles across multiple independently-constructed
    networks in one long-lived server process (worm ticks, fly ticks, and
    the cached singleton's own commands all interleaving over a real
    session), a live request started failing with Brian2's
    `StopIteration("Clock has reached the end of its available times.")` --
    reproducible on the live Docker backend after normal repeated use, not
    just a one-off. A dedicated clock per constructed network removes the
    cross-network sharing entirely (each network's `store()`/`restore()`
    already snapshots ITS OWN clock's time, so this doesn't change any
    individual network's own dynamics -- only which Clock object tracks
    that time).
    """
    connectome = get_connectome()
    neuron_ids = [n.id for n in connectome.neurons]
    index_of = {nid: i for i, nid in enumerate(neuron_ids)}
    neuron_id_set = set(neuron_ids)
    n = len(neuron_ids)

    clock = Clock(dt=defaultclock.dt)
    group = NeuronGroup(
        n,
        _HH_EQS,
        threshold="v > -20*mV",
        refractory="v > -20*mV",
        method="exponential_euler",
        name="celegans_neurons",
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
    chem_inhibitory: list[bool] = []
    gap_pre: list[int] = []
    gap_post: list[int] = []
    gap_w: list[float] = []
    neuron_to_effectors: dict[str, list[str]] = {}

    for s in connectome.synapses:
        if s.post not in neuron_id_set:
            neuron_to_effectors.setdefault(s.pre, []).append(s.post)
            continue
        weight = min(s.weight, _MAX_EFFECTIVE_WEIGHT)
        if s.type == "electrical":
            gap_pre.append(index_of[s.pre])
            gap_post.append(index_of[s.post])
            gap_w.append(weight * _GAP_NS_PER_WEIGHT)
        else:
            chem_pre.append(index_of[s.pre])
            chem_post.append(index_of[s.post])
            chem_w.append(weight * _CHEM_NS_PER_WEIGHT)
            chem_inhibitory.append(_is_inhibitory(s.pre, s.post, s.neurotransmitter, sign_model))

    chem_synapses = Synapses(group, group, model=_CHEM_SYN_EQS, on_pre="g += w", method="exact", name="chem_syn", clock=clock)
    chem_synapses.connect(i=chem_pre, j=chem_post)
    chem_synapses.w = np.array(chem_w) * nS
    chem_synapses.tau_syn = _TAU_SYN
    chem_synapses.Esyn = np.where(chem_inhibitory, _E_INHIBITORY / mV, _E_EXCITATORY / mV) * mV

    gap_synapses = Synapses(group, group, model=_GAP_SYN_EQS, method="exact", name="gap_syn", clock=clock)
    gap_synapses.connect(i=gap_pre, j=gap_post)
    gap_synapses.w = np.array(gap_w) * nS

    spikes = SpikeMonitor(group, name="spikemon")  # follows group's own clock automatically
    net = Network(group, chem_synapses, gap_synapses, spikes)
    # A snapshot taken before anything has run: `run_hh_trace` restores to this
    # before every request so each command gets an independent ~100ms trace
    # (reusing this Network object rather than rebuilding ~6,600 synapse
    # connections on every API call). restore() resets state, time, and the
    # spike monitor together, which is why the Network is stored/reused
    # instead of recreated per call (Brian2 refuses to add an
    # already-simulated NeuronGroup to a brand new Network).
    net.store("initial")

    return _NetworkAssets(
        neuron_ids=neuron_ids,
        index_of=index_of,
        group=group,
        net=net,
        neuron_to_effectors=neuron_to_effectors,
        chem_pre=np.array(chem_pre, dtype=int),
        gap_pre=np.array(gap_pre, dtype=int),
    )


@lru_cache
def _build_network() -> _NetworkAssets:
    """The one shared network instance every existing command uses.

    `run_hh_trace`/`run_hh_trace_isolated` call this (not the factory
    directly) so their behavior -- and Brian2's process-wide codegen cache --
    is unchanged. New code that needs an independent, continuously-run
    network (not restored to "initial" between calls) should call
    `_construct_network_assets()` directly instead.
    """
    return _construct_network_assets()


# --- Habituation (docs/29-worm-habituation-plasticity.md) ---
#
# Real phenomenon: repeated tap stimulation of C. elegans produces a
# progressively smaller reversal response (Rankin, Beck & Chiba 1990, Behav
# Neural Biol 50:35 -- 40 taps at a 10s ISI, last response significantly
# smaller than the first), mechanistically attributed to homosynaptic
# depression at the stimulated sensory neuron's own output synapses (Wicks &
# Rankin 1997), and the response spontaneously recovers if stimulation stops
# for a while (one of the 9 parametric features catalogued in Rankin et al.
# 2009, "Habituation Revisited", Neurobiol Learn Mem 92:135).
#
# This project's minimal command-pathway model (_PATHWAYS: FORWARD->AVBL,
# REVERSE->AVAL) has no separate sensory-neuron-then-interneuron chain like
# the real tap-withdrawal circuit -- only the single stimulated neuron per
# direction. Honest simplification: depression is applied to THAT neuron's
# own outgoing synapses instead of a distinct upstream sensory neuron's.
#
# State lives in a plain module-level dict, deliberately OUTSIDE the Brian2
# Network object `_build_network()` builds -- Network.store("initial")/
# restore("initial") snapshots Synapses.w too, so anything meant to persist
# ACROSS calls (which restore() runs every time) has to live outside it, the
# same reason the ablation feature above (docs/26) mutates weights AFTER
# restore() rather than trying to make the mutation itself persist. This is
# process-lifetime global state (no session/per-user concept exists anywhere
# in this app -- see ws_manager.py's own global singletons), which matches
# this being a local single-user tool.
_MAX_HABITUATION = 0.7  # never fully blocks -- real habituation is partial, not total silence
_HABITUATION_INCREMENT = 0.35  # hand-tuned asymptotic step per stimulation, NOT fit to Rankin et al.'s real decrement curve
_HABITUATION_RECOVERY_TAU_S = 45.0  # hand-tuned spontaneous-recovery time constant, NOT measured from real recovery data

_habituation_state: dict[Direction, dict[str, float]] = {}


def _habituation_level_at(direction: Direction, now: float) -> float:
    """Current habituation level for `direction` (0 = naive), after applying
    spontaneous recovery for however much real time has passed since the
    last stimulation. Read-only -- does not mutate state, so it's safe to
    call for reporting (get_habituation_level) as well as internally."""
    state = _habituation_state.get(direction)
    if state is None:
        return 0.0
    elapsed_s = max(0.0, now - state["last_at"])
    return state["level"] * math.exp(-elapsed_s / _HABITUATION_RECOVERY_TAU_S)


def _record_stimulation(direction: Direction, level_before: float, now: float) -> None:
    new_level = level_before + (_MAX_HABITUATION - level_before) * _HABITUATION_INCREMENT
    _habituation_state[direction] = {"level": new_level, "last_at": now}


def get_habituation_level(direction: Direction) -> float:
    """Current habituation level (0-_MAX_HABITUATION) for `direction`, as of
    right now -- used by the API route to populate CommandResponse without
    changing run_hh_trace's own return shape."""
    return _habituation_level_at(direction, time.time())


def reset_habituation() -> None:
    """No reset UI/endpoint exists (matches this app having no session
    concept at all) -- exposed for tests only, so each test starts from a
    known naive state instead of depending on run order."""
    _habituation_state.clear()


def run_hh_trace(
    direction: Direction,
    max_synapse_events: int = 20,
    max_muscle_events: int = 8,
    silenced_neuron_ids: frozenset[str] | None = None,
    now: float | None = None,
) -> list[SimulationEvent]:
    """Simulate the real network for one command and return a SimulationEvent
    trace shaped exactly like `engine.build_trace`'s output.

    `silenced_neuron_ids` approximates a classic laser-ablation experiment
    (see app/data/celegans_classic_ablations.py) as OUTPUT silencing: every
    chemical/gap synapse whose SOURCE is one of these neurons gets its
    conductance zeroed for this run only, so the rest of the network can no
    longer hear it. This is not literal cell removal (the neuron's own
    membrane equations still run) -- silencing outputs is the closer, more
    honest analogy to what a real laser ablation actually blocks
    (this cell's ability to signal downstream), and it's far cheaper than
    rebuilding the ~6,600-synapse network per request. See
    docs/26-worm-classic-ablation-behavior.md.

    `now` overrides the wall-clock time habituation (see the block above)
    uses to compute spontaneous recovery -- tests inject this to simulate
    time passing without an actual sleep(); production callers leave it
    None (defaults to time.time()).
    """
    if now is None:
        now = time.time()
    pathway = _PATHWAYS.get(direction)
    label = _DIRECTION_LABELS[direction]
    habituation_level = _habituation_level_at(direction, now) if pathway is not None else 0.0
    command_message = f"'{label}' 명령이 감각-운동 회로에 입력되었습니다."
    if habituation_level > 0.01:
        command_message += f" (반복 자극으로 시냅스 습관화 {habituation_level / _MAX_HABITUATION:.0%} — Rankin et al. 1990)"
    events = [SimulationEvent(t_ms=0, stage=SimulationStage.COMMAND, message=command_message)]
    if pathway is None:
        events.append(SimulationEvent(t_ms=_SIM_DURATION / ms, stage=SimulationStage.MOVEMENT, message=f"{label} 운동이 발현되었습니다."))
        return events

    assets = _build_network()
    if pathway.pre not in assets.index_of:
        raise KeyError(f"Stimulus neuron {pathway.pre} not found in the simulated network")
    seed_index = assets.index_of[pathway.pre]

    # Every command gets an independent ~100ms trace: restore() resets
    # membrane state, gating variables, time, and the spike monitor back to
    # the just-built, never-run snapshot.
    assets.net.restore("initial")
    if habituation_level > 0.001:
        retain = 1.0 - habituation_level
        chem_syn = assets.net["chem_syn"]
        gap_syn = assets.net["gap_syn"]
        chem_self_mask = assets.chem_pre == seed_index
        if chem_self_mask.any():
            new_chem_w = chem_syn.w[:]
            new_chem_w[chem_self_mask] = new_chem_w[chem_self_mask] * retain
            chem_syn.w = new_chem_w
        gap_self_mask = assets.gap_pre == seed_index
        if gap_self_mask.any():
            new_gap_w = gap_syn.w[:]
            new_gap_w[gap_self_mask] = new_gap_w[gap_self_mask] * retain
            gap_syn.w = new_gap_w
    if silenced_neuron_ids:
        silenced_indices = {assets.index_of[nid] for nid in silenced_neuron_ids if nid in assets.index_of}
        if silenced_indices:
            chem_syn = assets.net["chem_syn"]
            gap_syn = assets.net["gap_syn"]
            chem_mask = np.isin(assets.chem_pre, list(silenced_indices))
            if chem_mask.any():
                new_chem_w = chem_syn.w[:]
                new_chem_w[chem_mask] = 0 * nS
                chem_syn.w = new_chem_w
            gap_mask = np.isin(assets.gap_pre, list(silenced_indices))
            if gap_mask.any():
                new_gap_w = gap_syn.w[:]
                new_gap_w[gap_mask] = 0 * nS
                gap_syn.w = new_gap_w
    assets.group.I[seed_index] = _STIMULUS_CURRENT
    assets.net.run(_STIMULUS_DURATION)
    assets.group.I[seed_index] = 0 * nA
    assets.net.run(_SIM_DURATION - _STIMULUS_DURATION)

    spikes = assets.net["spikemon"]
    spike_indices = np.array(spikes.i)
    spike_times = np.array(spikes.t / ms)
    order = np.argsort(spike_times)

    connectome = get_connectome()
    nt_by_id = {n.id: n.neurotransmitter for n in connectome.neurons}

    seen_neurons: set[str] = set()
    synapse_events = 0
    muscle_targets: dict[str, float] = {}

    for idx in order:
        if synapse_events >= max_synapse_events:
            break
        neuron_id = assets.neuron_ids[spike_indices[idx]]
        if neuron_id in seen_neurons:
            # Only the first spike per neuron is logged, so the 20 slots show
            # breadth of the cascade rather than one hub neuron firing repeatedly.
            continue
        t_ms = 12.4 + float(spike_times[idx])
        if neuron_id == pathway.pre:
            message = f"{neuron_id}: 자극 전류 주입으로 활동전위가 발생했습니다."
        else:
            message = f"{neuron_id}: 막전위가 역치를 넘어 활동전위가 발생했습니다 ({nt_by_id[neuron_id].value})."
        events.append(
            SimulationEvent(
                t_ms=round(t_ms, 1),
                stage=SimulationStage.SYNAPSE,
                source=neuron_id,
                neurotransmitter=nt_by_id[neuron_id],
                message=message,
            )
        )
        seen_neurons.add(neuron_id)
        synapse_events += 1

        for effector_id in assets.neuron_to_effectors.get(neuron_id, []):
            if effector_id not in muscle_targets:
                muscle_targets[effector_id] = t_ms

    for effector_id, t_ms in sorted(muscle_targets.items(), key=lambda kv: kv[1])[:max_muscle_events]:
        events.append(
            SimulationEvent(
                t_ms=round(t_ms + 4.0, 1),
                stage=SimulationStage.MUSCLE,
                target=effector_id,
                message=f"{effector_id} 근육/조직에 신경 신호가 도달했습니다.",
            )
        )

    events.append(
        SimulationEvent(t_ms=_SIM_DURATION / ms, stage=SimulationStage.MOVEMENT, message=f"{label} 운동이 발현되었습니다.")
    )
    # Record this stimulation for next time's spontaneous-recovery calc --
    # deliberately AFTER building the trace with this call's `habituation_level`
    # (the level that was actually applied above), not the just-incremented
    # one, so this response's own note reflects what happened to IT.
    _record_stimulation(direction, habituation_level, now)
    # Synapse and muscle events were appended in two separate passes above, so
    # re-sort into chronological order (command stays first, movement stays
    # last since both are pinned at the trace's start/end time).
    return [events[0]] + sorted(events[1:-1], key=lambda e: e.t_ms) + [events[-1]]


def run_hh_trace_isolated(
    direction: Direction,
    max_synapse_events: int = 20,
    max_muscle_events: int = 8,
    silenced_neuron_ids: frozenset[str] | None = None,
) -> list[SimulationEvent]:
    """Same real Brian2 simulation as `run_hh_trace`, but leaves the shared
    `_habituation_state` exactly as it found it afterward -- for 연구소(Lab)'s
    virtual experiment feature (docs/35), where a "what if I silence this
    arbitrary combination" run must never leak into, or be affected by, the
    real interactive worm page's habituation level for that direction (both
    read/write the same module-level state, keyed only by direction, with no
    concept of "which page called this"). Snapshots and restores
    `_habituation_state[direction]` around the call."""
    snapshot = _habituation_state.get(direction)
    try:
        return run_hh_trace(direction, max_synapse_events, max_muscle_events, silenced_neuron_ids)
    finally:
        if snapshot is None:
            _habituation_state.pop(direction, None)
        else:
            _habituation_state[direction] = snapshot
