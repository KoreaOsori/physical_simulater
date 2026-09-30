"""폐루프 가설 검증 실험 (docs/46). 실제 Brian2 네트워크를 가상 웜/초파리 폐루프
모듈(app/lab/virtual_worm.py, virtual_fly.py) 그대로 돌려 H7-H10을 검증한다.

사용 (백엔드 컨테이너 안, cython codegen):
    docker exec -w /app physical_simulater-backend-1 python -m scripts.closed_loop_hypotheses worm-sweep
    ... worm-subsets | worm-boundary | worm-episodes | fly-sweep | fly-boundary | fly-episodes

각 명령은 결과 JSON 한 줄을 stdout 마지막 줄에 출력한다(가설 노트에 원자료로 기록).
에피소드는 무작위 시드를 고정해 재현 가능하게 했고, 같은 시드를 실험군/대조군에 똑같이 쓴다.
"""

from __future__ import annotations

import json
import math
import multiprocessing as mp
import random
import sys
import time

import numpy as np
from brian2 import mV, nA, nS

WORKERS = 7


# ---------------------------------------------------------------- worm

def _worm_counts(st, ids: tuple[str, ...]) -> dict[str, int]:
    spike_i = st.assets.net["spikemon"].i[:]
    return {nid: int((spike_i == st.assets.index_of[nid]).sum()) for nid in ids if nid in st.assets.index_of}


def worm_sweep() -> dict:
    """감각 전류 비율 f(최대 0.6nA 대비)를 훑어 AWC/ASE 발화 문턱과 반전(AVA>AVB) 문턱을 찾는다."""
    from app.lab import virtual_worm as vw

    st = vw._fresh_state()
    rows = []
    for f in [0.0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.12, 0.14, 0.16, 0.18, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0]:
        fwd, rev, sensory = vw._run_network(st, -f / vw._SENSORY_GAIN)
        rows.append({"f": f, "sensory": sum(s.spike_count for s in sensory), "avb": fwd, "ava": rev, "pirouette": rev > fwd and rev > 0})
    # 결정론 확인: 같은 입력을 두 번 넣으면 같은 출력이어야 한다(매 틱 restore)
    again = [vw._run_network(st, -0.3 / vw._SENSORY_GAIN)[:2] for _ in range(2)]
    return {"rows": rows, "deterministic": again[0] == again[1]}


def worm_subsets() -> dict:
    """H8: 감각뉴런 부분집합만 자극했을 때 반전(AVA>AVB)이 나오는가."""
    from app.lab import virtual_worm as vw

    st = vw._fresh_state()
    subsets = {
        "AWCL+AWCR+ASEL+ASER": ("AWCL", "AWCR", "ASEL", "ASER"),
        "AWCL+AWCR": ("AWCL", "AWCR"),
        "ASEL+ASER": ("ASEL", "ASER"),
        "AWCL": ("AWCL",),
        "AWCR": ("AWCR",),
        "ASEL": ("ASEL",),
        "ASER": ("ASER",),
    }
    out = {}
    readouts = ("AVAL", "AVAR", "AVBL", "AVBR", "AIBL", "AIBR", "AIYL", "AIYR")
    for label, ids in subsets.items():
        per_f = []
        for f in (0.3, 0.6, 1.0):
            idx = [st.assets.index_of[n] for n in ids]
            st.stim.run_tick(idx, f * vw._SENSORY_CURRENT_MAX, vw.TICK_DURATION_MS)
            c = _worm_counts(st, readouts + ids)
            ava = c["AVAL"] + c["AVAR"]
            avb = c["AVBL"] + c["AVBR"]
            per_f.append({"f": f, "stimulated": {n: c[n] for n in ids}, "ava": ava, "avb": avb, "aib": c["AIBL"] + c["AIBR"], "aiy": c["AIYL"] + c["AIYR"], "pirouette": ava > avb and ava > 0})
        out[label] = per_f
    return out


def worm_signs() -> dict:
    """H8b: 반전 편향이 경로 특이적인가, 네트워크 전반의 성질인가 -- 실제 행동이 알려진 촉각
    뉴런으로 확인(Chalfie et al. 1985: 앞쪽 촉각 ALM/AVM -> 후진, 뒤쪽 촉각 PLM -> 전진).
    H8c: AWC->AIY 글루탐산 시냅스를 실제처럼 억제성(GluCl, Chalasani et al. 2007)으로 바꾸면
    AWC 자극 시 AIY 활동과 AVA/AVB 균형이 어떻게 바뀌는가."""
    from app.lab import virtual_worm as vw

    st = vw._fresh_state()
    readouts = ("AVAL", "AVAR", "AVBL", "AVBR", "AIYL", "AIYR", "AIBL", "AIBR")

    def stim(ids: tuple[str, ...], f: float) -> dict:
        idx = [st.assets.index_of[n] for n in ids if n in st.assets.index_of]
        st.stim.run_tick(idx, f * vw._SENSORY_CURRENT_MAX, vw.TICK_DURATION_MS)
        c = _worm_counts(st, readouts)
        ava, avb = c["AVAL"] + c["AVAR"], c["AVBL"] + c["AVBR"]
        return {"f": f, "ava": ava, "avb": avb, "aiy": c["AIYL"] + c["AIYR"], "aib": c["AIBL"] + c["AIBR"], "reverse_bias": ava > avb}

    touch = {}
    for label, ids in {"ALML+ALMR (앞 촉각)": ("ALML", "ALMR"), "AVM (앞 촉각)": ("AVM",), "PLML+PLMR (뒤 촉각)": ("PLML", "PLMR"), "AWAL+AWAR (유인 냄새 ON)": ("AWAL", "AWAR"), "ASHL+ASHR (유해 자극)": ("ASHL", "ASHR")}.items():
        touch[label] = [stim(ids, f) for f in (0.3, 1.0)]

    awc = ("AWCL", "AWCR")
    before = [stim(awc, f) for f in (0.3, 0.6, 1.0)]
    chem = st.assets.net["chem_syn"]
    pre, post = chem.i[:], chem.j[:]
    awc_idx = {st.assets.index_of[n] for n in awc}
    aiy_idx = {st.assets.index_of[n] for n in ("AIYL", "AIYR")}
    target = [k for k in range(len(pre)) if pre[k] in awc_idx and post[k] in aiy_idx]
    st.assets.net.restore("initial")
    esyn_mv = np.asarray(chem.Esyn[:] / mV)
    esyn_mv[target] = vw_inhibitory_mv()
    chem.Esyn = esyn_mv * mV
    st.assets.net.store("initial")
    after = [stim(awc, f) for f in (0.3, 0.6, 1.0)]
    return {"touch_and_other": touch, "awc_to_aiy_synapses_flipped": len(target), "awc_before": before, "awc_after_inhibitory_awc_aiy": after}


_SIGN_CONFIGS = {
    "A_gaba_only": ("gaba_only", "all_off"),
    "B_receptor": ("receptor_predicted", "all_off"),
    "C_receptor_biological": ("receptor_predicted", "biological"),
}


def worm_signmodel() -> dict:
    """docs/47: 시냅스 부호 규칙별로 (1) 알려진 입력의 전진/후진 방향, (2) 화학주성 자극의 반전 문턱,
    (3) 오르막(ASEL ON) 자극이 무엇을 만드는지 비교한다."""
    from app.lab import virtual_worm as vw

    probes = {
        "ASEL": ("ASEL",), "ASER": ("ASER",), "AWC쌍": ("AWCL", "AWCR"), "AWA쌍(유인 ON)": ("AWAL", "AWAR"),
        "ASH쌍(유해)": ("ASHL", "ASHR"), "ALM쌍(앞 촉각)": ("ALML", "ALMR"), "PLM쌍(뒤 촉각)": ("PLML", "PLMR"),
    }
    readouts = ("AVAL", "AVAR", "AVBL", "AVBR", "AIYL", "AIYR", "AIBL", "AIBR")
    out = {}
    for label, (sign_model, polarity) in _SIGN_CONFIGS.items():
        vw.SIGN_MODEL, vw.SENSORY_POLARITY = sign_model, polarity
        st = vw._fresh_state()
        res = {"probes": {}, "down_sweep": [], "up_sweep": []}
        for name, ids in probes.items():
            rows = []
            for f in (0.3, 1.0):
                idx = [st.assets.index_of[n] for n in ids if n in st.assets.index_of]
                st.stim.run_tick(idx, f * vw._SENSORY_CURRENT_MAX, vw.TICK_DURATION_MS)
                c = _worm_counts(st, readouts)
                rows.append({"f": f, "ava": c["AVAL"] + c["AVAR"], "avb": c["AVBL"] + c["AVBR"], "aiy": c["AIYL"] + c["AIYR"], "aib": c["AIBL"] + c["AIBR"]})
            res["probes"][name] = rows
        # 폐루프가 실제로 쓰는 자극: 농도 감소(내리막) / 증가(오르막) 틱의 ΔC를 문턱 근처~최대까지
        for f in (0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.3, 0.5, 1.0):
            fwd, rev, _ = vw._run_network(st, -f / vw._SENSORY_GAIN)
            res["down_sweep"].append({"f": f, "avb": fwd, "ava": rev, "decision": vw._decide(fwd, rev)})
            fwd, rev, _ = vw._run_network(st, f / vw._SENSORY_GAIN)
            res["up_sweep"].append({"f": f, "avb": fwd, "ava": rev, "decision": vw._decide(fwd, rev)})
        out[label] = res
    return out


def _silence_chunk(args) -> list[dict]:
    """H2-1(docs/48): 뉴런 하나씩 출력을 막고(나가는 화학 시냅스 + 그 뉴런이 낀 전기 시냅스 가중치 0 --
    가상 실험실/run_hh_trace의 절제 방식과 같음) 폐루프가 실제로 쓰는 두 자극에서 명령 뉴런 반응을 잰다."""
    neuron_ids, f = args
    from app.lab import virtual_worm as vw

    st = vw._fresh_state()
    a = st.assets
    chem, gap = a.net["chem_syn"], a.net["gap_syn"]
    cpre = chem.i[:]
    gi, gj = gap.i[:], gap.j[:]
    idx_of = a.index_of
    off = [idx_of[n] for n in ("AWCL", "AWCR", "ASER")]
    on = [idx_of["ASEL"]]
    cur = f * vw._SENSORY_CURRENT_MAX

    def trial(silenced: int | None, stim_idx: list[int]) -> tuple[int, int, int]:
        a.net.restore("initial")
        if silenced is not None:
            w = chem.w[:]
            w[cpre == silenced] = 0 * w.unit if hasattr(w, "unit") else 0
            chem.w = w
            gw = gap.w[:]
            gw[(gi == silenced) | (gj == silenced)] = 0 * gw.unit if hasattr(gw, "unit") else 0
            gap.w = gw
        st.stim.indices = list(stim_idx)
        for i in stim_idx:
            a.group.I[i] = cur
        a.net.run(vw.TICK_DURATION_MS * vw.ms)
        for i in stim_idx:
            a.group.I[i] = 0 * nA
        st.stim.indices = []
        c = _worm_counts(st, ("AVAL", "AVAR", "AVBL", "AVBR"))
        return c["AVAL"] + c["AVAR"], c["AVBL"] + c["AVBR"], int(len(a.net["spikemon"].i[:]))

    base_down, base_up = trial(None, off), trial(None, on)
    out = [{"neuron": "__baseline__", "down": base_down, "up": base_up}]
    for nid in neuron_ids:
        out.append({"neuron": nid, "down": trial(idx_of[nid], off), "up": trial(idx_of[nid], on)})
    return out


def worm_silence_all(f: float = 0.3) -> dict:
    from app.data.celegans_connectome import get_connectome

    ids = [n.id for n in get_connectome().neurons]
    chunks = [ids[k::WORKERS] for k in range(WORKERS)]
    with mp.get_context("fork").Pool(WORKERS) as pool:
        parts = pool.map(_silence_chunk, [(c, f) for c in chunks])
    base = parts[0][0]
    rows = [r for p in parts for r in p if r["neuron"] != "__baseline__"]
    return {"f": f, "baseline": base, "baselines_consistent": all(p[0] == base for p in parts), "rows": rows}


def worm_avb_balance() -> dict:
    """H2-3(docs/48): docs/47이 찾은 구조적 편향(AVA 입력 ≈ AVB의 2배)이 반전 편향의 원인이라면, AVB로 들어오는
    시냅스 가중치만 k배로 키웠을 때 ASEL 단독·AWA(실제로 전진을 촉진) 자극이 전진 쪽으로 돌아서야 한다.
    동시에 폐루프에 필요한 '내리막(OFF) 자극 → 반전'은 유지되는지 본다. 반사실적 조작이지 실제 생물 수치가 아님."""
    from app.lab import virtual_worm as vw

    probes = {"ASEL": ("ASEL",), "AWA쌍": ("AWAL", "AWAR"), "ASH쌍": ("ASHL", "ASHR"), "PLM쌍": ("PLML", "PLMR"), "ALM쌍": ("ALML", "ALMR")}
    out = {}
    for k in (1.0, 1.5, 2.0, 2.5, 3.0):
        vw.SIGN_MODEL, vw.SENSORY_POLARITY = "receptor_predicted", "biological"
        st = vw._fresh_state()
        a = st.assets
        chem, gap = a.net["chem_syn"], a.net["gap_syn"]
        avb = [a.index_of["AVBL"], a.index_of["AVBR"]]
        cw = np.asarray(chem.w[:] / nS)
        cw[np.isin(chem.j[:], avb)] *= k
        chem.w = cw * nS
        gw = np.asarray(gap.w[:] / nS)
        gw[np.isin(gap.j[:], avb)] *= k  # 전기 시냅스는 양방향 쌍으로 들어가 있어 AVB 쪽으로 들어오는 방향만 키운다
        gap.w = gw * nS
        a.net.store("initial")
        res = {"probes": {}, "down": [], "up": []}
        for name, ids in probes.items():
            idx = [a.index_of[n] for n in ids]
            rows = []
            for f in (0.3, 1.0):
                st.stim.run_tick(idx, f * vw._SENSORY_CURRENT_MAX, vw.TICK_DURATION_MS)
                c = _worm_counts(st, ("AVAL", "AVAR", "AVBL", "AVBR"))
                rows.append({"f": f, "ava": c["AVAL"] + c["AVAR"], "avb": c["AVBL"] + c["AVBR"]})
            res["probes"][name] = rows
        for f in (0.15, 0.3, 1.0):
            fwd, rev, _ = vw._run_network(st, -f / vw._SENSORY_GAIN)
            res["down"].append({"f": f, "ava": rev, "avb": fwd, "decision": vw._decide(fwd, rev)})
            fwd, rev, _ = vw._run_network(st, f / vw._SENSORY_GAIN)
            res["up"].append({"f": f, "ava": rev, "avb": fwd, "decision": vw._decide(fwd, rev)})
        out[f"k={k}"] = res
    return out


def vw_inhibitory_mv() -> float:
    return -70.0  # hh_model._E_INHIBITORY와 같은 값(GABA 시냅스에 쓰는 억제성 역전위)


def worm_boundary(fine: int = 0) -> dict:
    """H7 검증: 광원에서 거리 r 지점에서 광원 반대쪽을 향해 실제로 두 틱 이동시켜, 두 번째 틱에
    감각 발화/반전이 나오는지 본다(첫 틱은 비교할 이동이 없어 ΔC=0)."""
    from app.lab import virtual_worm as vw

    st = vw._fresh_state()
    rows = []
    radii = [3.25, 3.5, 3.75, 4, 4.25, 4.5, 56, 56.5, 57, 57.5, 58, 58.5, 59, 59.5] if fine else [0.5, 1, 1.5, 2, 3, 5, 10, 20, 30, 40, 45, 50, 55, 60, 65, 70]
    for r_mm in radii:
        st.x_um, st.y_um = 0.0, vw.SOURCE_POS_UM[1] - r_mm * 1000.0
        st.heading_rad = -math.pi / 2
        st.trail = [[st.x_um, st.y_um]]
        st.prev_concentration = vw._concentration_at(st, st.x_um, st.y_um)
        vw._run_one_tick(st)
        if st.heading_rad != -math.pi / 2:  # 첫 틱에 방향이 바뀌었으면 다시 맞춘다(첫 틱은 ΔC=0이라 원래 안 바뀜)
            st.heading_rad = -math.pi / 2
        t = vw._run_one_tick(st)
        rows.append({"r_mm": r_mm, "dC_tick": t.delta_concentration, "sensory": sum(s.spike_count for s in t.sensory_activity), "ava": t.reverse_spikes, "avb": t.forward_spikes, "pirouette": t.event == "pirouette"})
    return {"rows": rows}


def _install_asel_on_polarity(vw) -> None:
    """H8d 조건: 감각 극성을 실제 문헌대로 -- AWC·ASER는 농도 감소(OFF), ASEL은 농도 증가(ON,
    Suzuki et al. 2008)에 반응하게 바꾼 `_run_network` 대체본. 같은 이득(_SENSORY_GAIN)."""
    from app.lab.schemas import VirtualWormNeuronActivityOut

    def run_network(st, delta):
        assets = st.assets
        off_cur = min(1.0, max(0.0, -delta) * vw._SENSORY_GAIN) * vw._SENSORY_CURRENT_MAX
        on_cur = min(1.0, max(0.0, delta) * vw._SENSORY_GAIN) * vw._SENSORY_CURRENT_MAX
        off_idx = [assets.index_of[n] for n in ("AWCL", "AWCR", "ASER")]
        on_idx = [assets.index_of["ASEL"]]
        net = assets.net
        net.restore("initial")
        st.stim.indices = off_idx + on_idx
        for i in off_idx:
            assets.group.I[i] = off_cur
        for i in on_idx:
            assets.group.I[i] = on_cur
        net.run(vw.TICK_DURATION_MS * vw.ms)
        for i in off_idx + on_idx:
            assets.group.I[i] = 0 * nA
        st.stim.indices = []
        c = _worm_counts(st, ("AVAL", "AVAR", "AVBL", "AVBR") + vw.SENSORY_NEURON_IDS)
        sensory = [VirtualWormNeuronActivityOut(neuron_id=n, spike_count=c[n]) for n in vw.SENSORY_NEURON_IDS]
        return c["AVBL"] + c["AVBR"], c["AVAL"] + c["AVAR"], sensory

    vw._run_network = run_network


def _worm_episode(args) -> dict:
    seed, condition, r0_mm, n_ticks = args
    from app.lab import virtual_worm as vw

    vw.ms = __import__("brian2").ms
    # 기준(docs/46) 조건은 원래 규칙으로 고정 -- 모듈 기본값이 바뀌어도(docs/47) 재현되도록
    vw.SIGN_MODEL, vw.SENSORY_POLARITY = "gaba_only", "all_off"
    if condition == "ablated":
        vw._SENSORY_GAIN = 0.0  # 대조군: 감각 입력 제거(같은 네트워크, 같은 시드)
    elif condition == "asel_on":
        _install_asel_on_polarity(vw)
    elif condition in _SIGN_CONFIG_BY_LETTER:
        vw.SIGN_MODEL, vw.SENSORY_POLARITY = _SIGN_CONFIG_BY_LETTER[condition]
    silence: list[str] = []
    if condition.startswith("cur") or condition.startswith("silence:"):
        # docs/48: 현재 기본 설정(수용체 부호 + 실제 극성)으로 -- "cur"는 그대로, "silence:A+B"는 그 뉴런들의 출력 차단
        vw.SIGN_MODEL, vw.SENSORY_POLARITY = "receptor_predicted", "biological"
        if condition.startswith("silence:"):
            silence = condition.split(":", 1)[1].split("+")
    random.seed(seed)
    st = vw._fresh_state()
    if silence:
        a = st.assets
        chem, gap = a.net["chem_syn"], a.net["gap_syn"]
        idx = [a.index_of[n] for n in silence]
        cw = np.asarray(chem.w[:] / nS)
        cw[np.isin(chem.i[:], idx)] = 0.0
        chem.w = cw * nS
        gw = np.asarray(gap.w[:] / nS)
        gw[np.isin(gap.i[:], idx) | np.isin(gap.j[:], idx)] = 0.0
        gap.w = gw * nS
        a.net.store("initial")  # 매 틱 restore되는 스냅샷에 절제 상태를 반영(아직 한 번도 돌지 않은 t=0)
    st.x_um, st.y_um = 0.0, vw.SOURCE_POS_UM[1] - r0_mm * 1000.0
    st.heading_rad = random.uniform(-math.pi, math.pi)
    st.trail = [[st.x_um, st.y_um]]
    st.prev_concentration = vw._concentration_at(st, st.x_um, st.y_um)
    d0 = vw._distance_to_source(st, st.x_um, st.y_um)
    pir = 0
    up_pir = 0  # 농도가 올라가던(광원 쪽으로 가던) 틱에서 나온 반전 -- 실패한 반전
    for _ in range(n_ticks):
        t = vw._run_one_tick(st)
        if t.event == "pirouette":
            pir += 1
            up_pir += t.delta_concentration > 0
    d1 = vw._distance_to_source(st, st.x_um, st.y_um)
    return {"seed": seed, "condition": condition, "r0_mm": r0_mm, "approach_mm": (d0 - d1) / 1000, "pirouettes": pir, "uphill_pirouettes": up_pir}


def _worm_default_episode(args) -> dict:
    """docs/47: 모듈 기본값 그대로(기본 출발점·방향·부호 규칙·극성) -- 실제 페이지의 '다시 시작'과 같은 조건."""
    seed, ablate, n_ticks = args
    from app.lab import virtual_worm as vw

    if ablate:
        vw._SENSORY_GAIN = 0.0
    random.seed(seed)
    st = vw._fresh_state()
    d0 = vw._distance_to_source(st, st.x_um, st.y_um)
    first_pir = None
    pir = 0
    for k in range(n_ticks):
        t = vw._run_one_tick(st)
        if t.event == "pirouette":
            pir += 1
            first_pir = k + 1 if first_pir is None else first_pir
    d1 = vw._distance_to_source(st, st.x_um, st.y_um)
    return {"seed": seed, "ablate": ablate, "d0_mm": d0 / 1000, "approach_mm": (d0 - d1) / 1000, "pirouettes": pir, "first_pirouette_tick": first_pir}


def worm_default_start(n: int = 7, n_ticks: int = 400) -> dict:
    jobs = [(s, ab, n_ticks) for ab in (False, True) for s in range(n)]
    with mp.get_context("fork").Pool(WORKERS) as pool:
        res = pool.map(_worm_default_episode, jobs)
    return {"n_ticks": n_ticks, "episodes": res}


_SIGN_CONFIG_BY_LETTER = {"B": ("receptor_predicted", "all_off"), "C": ("receptor_predicted", "biological")}


def worm_episodes(n: int = 8, n_ticks: int = 200, plan: str = "intact@30,ablated@30,asel_on@30,intact@70,ablated@70") -> dict:
    plan = [(c, float(r)) for c, r in (p.split("@") for p in plan.split(","))]
    jobs = [(s, cond, r0, n_ticks) for cond, r0 in plan for s in range(n)]
    with mp.get_context("fork").Pool(WORKERS) as pool:
        res = pool.map(_worm_episode, jobs)
    return {"n_ticks": n_ticks, "episodes": res}


# ---------------------------------------------------------------- fly

def fly_sweep() -> dict:
    from app.lab import virtual_fly as vf

    st = vf._fresh_state()
    rows = []
    for f in [0.0, 0.02, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.11, 0.12, 0.14, 0.16, 0.2, 0.3, 0.5, 1.0]:
        pn_na, mbon = vf._run_network(st, f)
        rows.append({"f": f, "pn_na": pn_na, "mbon01": mbon, "avoid": mbon > 0})
    again = [vf._run_network(st, 0.1)[1] for _ in range(2)]
    return {"rows": rows, "deterministic": again[0] == again[1]}


def fly_boundary() -> dict:
    """H10 검증: 광원에서 수평 거리 r(바닥) / 광원 바로 위 높이 z(비행)에서 한 번 감지해 회피 여부."""
    from app.lab import virtual_fly as vf

    st = vf._fresh_state()
    sx, sy = vf.SOURCE_POS_UM
    ground = []
    for r_mm in [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22]:
        c = vf._concentration_at(st, sx, sy - r_mm * 1000)
        ground.append({"r_mm": r_mm, "c": c, "avoid": vf._run_network(st, c)[1] > 0})
    air = []
    for z_mm in [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22]:
        c = vf._concentration_at(st, sx, sy, z_mm * 1000)
        air.append({"z_mm": z_mm, "c": c, "avoid": vf._run_network(st, c)[1] > 0})
    return {"ground": ground, "air": air}


def _fly_episode(args) -> dict:
    seed, condition, n_ticks, r_zone_mm = args
    from app.lab import virtual_fly as vf

    ablate = condition == "ablated"
    if ablate:
        vf._STIMULUS_CURRENT_MAX = 0.0 * nA  # 대조군: 냄새 입력 제거
    # docs/47: "random" = docs/42 원래 회피(H12 재현용), "directed" = 농도 시간 비교로 방향을 고르는 회피
    vf.AVOIDANCE_MODE = "random" if condition == "random" else "directed"
    random.seed(seed)
    st = vf._fresh_state()
    # 광원에서 25mm 이상 떨어진 무작위 시작점(아레나 안)
    while True:
        a = random.uniform(0, 2 * math.pi)
        rr = math.sqrt(random.random()) * vf.ARENA_RADIUS_UM * 0.9
        x, y = rr * math.cos(a), rr * math.sin(a)
        if math.hypot(x - vf.SOURCE_POS_UM[0], y - vf.SOURCE_POS_UM[1]) > 25000:
            break
    st.x_um, st.y_um = x, y
    st.heading_rad = random.uniform(-math.pi, math.pi)
    st.trail = [[x, y]]
    closest = math.inf
    in_zone = 0
    avoid = 0
    for _ in range(n_ticks):
        t = vf._run_one_tick(st)
        avoid += t.event == "avoidance"
        d = math.hypot(st.x_um - vf.SOURCE_POS_UM[0], st.y_um - vf.SOURCE_POS_UM[1])
        closest = min(closest, d)
        in_zone += d < r_zone_mm * 1000
    return {"seed": seed, "condition": condition, "ablate": ablate, "closest_mm": closest / 1000, "zone_frac": in_zone / n_ticks, "avoidances": avoid}


def fly_episodes(n: int = 7, n_ticks: int = 100, r_zone_mm: float = 15.0, conditions: str = "random,ablated") -> dict:
    jobs = [(s, cond, n_ticks, r_zone_mm) for cond in conditions.split(",") for s in range(n)]
    with mp.get_context("fork").Pool(WORKERS) as pool:
        res = pool.map(_fly_episode, jobs)
    return {"n_ticks": n_ticks, "r_zone_mm": r_zone_mm, "episodes": res}


COMMANDS = {
    "worm-sweep": worm_sweep,
    "worm-subsets": worm_subsets,
    "worm-boundary": worm_boundary,
    "worm-signs": worm_signs,
    "worm-signmodel": worm_signmodel,
    "worm-default-start": worm_default_start,
    "worm-silence-all": worm_silence_all,
    "worm-avb-balance": worm_avb_balance,
    "worm-episodes": worm_episodes,
    "fly-sweep": fly_sweep,
    "fly-boundary": fly_boundary,
    "fly-episodes": fly_episodes,
}

if __name__ == "__main__":
    import logging

    logging.getLogger("brian2").setLevel(logging.ERROR)
    name = sys.argv[1]
    def _parse(v: str):
        for cast in (int, float):
            try:
                return cast(v)
            except ValueError:
                pass
        return v

    kwargs = {k: _parse(v) for k, v in (a.split("=", 1) for a in sys.argv[2:])}
    t0 = time.time()
    result = COMMANDS[name](**kwargs)
    result["_elapsed_s"] = round(time.time() - t0, 1)
    print(json.dumps(result, ensure_ascii=False))
