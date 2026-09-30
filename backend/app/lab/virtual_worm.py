"""가상 예쁜꼬마선충 폐루프 환경 시뮬레이션 (docs/41).

지금까지의 웜 시뮬레이션(`/api/simulation/command`, 연구소의 가상 실험)은
전부 "명령 1개 -> 약 100ms짜리 독립된 트레이스 1개"였다 -- 매 요청마다
`net.restore("initial")`로 완전히 초기화된다. 이 모듈은 처음으로 진짜
**폐루프**를 만든다: 실제 302개 뉴런 커넥톰이 환경(유인물질 농도 기울기)을
감각으로 받아들이고, 그 결과로 실제로 이동하고, 이동한 새 위치가 다시
감각 입력이 되는 순환을 매 틱마다 반복한다.

## 실제 생물학적 근거 (klinokinesis / "run and pirouette")

C. elegans의 화학주성은 문헌에서 두 가지 전략의 조합으로 기술된다
(Pierce-Shimomura, Morse & Lockery 1999, J Neurosci 19(21):9557; Iino &
Yoshida 2009, J Neurosci 29(17):5370):

1. **Klinokinesis (run-and-pirouette)**: 유인물질 농도가 "감소"할 때
   반전(reversal) + 재정향(reorientation) 확률이 높아지고, 농도가
   일정하거나 "증가"할 때는 곧게 전진(run)을 유지한다 -- 이 프로젝트가
   구현하는 **주 메커니즘**.
2. **Klinotaxis (weathervane)**: run 도중에도 몸을 미세하게 굽혀 농도가
   높아지는 쪽으로 진행 방향을 연속적으로 편향시키는 정밀 조향(AIY가
   관여). 이번 v1에서는 **의도적으로 구현하지 않는다** -- 아래 "범위
   밖" 참고.

감각뉴런 AWC/ASE는 농도가 "증가"할 때가 아니라 **"감소"(또는 자극
제거)할 때 켜지는 ON-response**를 보인다는 것이 실제 칼슘 이미징으로
확인되어 있다(Chalasani et al. 2007, Nature 450:63 -- AWC; Suzuki et al.
2008, Nature 454:114 -- ASE 비대칭). 이 모듈의 감각 자극 주입은 이 실제
극성을 그대로 따른다: `delta_concentration < 0`일 때만 AWC/ASE에 전류를
주입한다.

명령 인터뉴런은 이 프로젝트가 이미 실제 웜 페이지(`engine.py`의
`_PATHWAYS`)에서 쓰는 것과 동일한 매핑을 재사용한다 -- FORWARD의 실제
시드 뉴런이 AVBL, REVERSE의 실제 시드 뉴런이 AVAL이므로, 이 틱에서
AVA*(반전)가 AVB*(전진)보다 더 많이 발화하면 pirouette, 아니면 run으로
판정한다.

## 독립된 Brian2 네트워크

`hh_model._build_network()`는 `@lru_cache`된 단일 공유 인스턴스라
기존 명령 경로(`run_hh_trace`)와 이 폐루프가 같은 네트워크 객체를
동시에 건드리면 서로의 막전위/게이팅 변수 상태를 오염시킨다. 이 모듈은
`hh_model._construct_network_assets()`(이번 작업으로 새로 뽑아낸 순수
팩토리)를 직접 호출해 완전히 별도의 `_NetworkAssets`를 갖는다. 처음엔
막전위를 틱마다 이어 가려 했으나 한 번 자극받은 네트워크가 영구 고착
상태에 빠져(docs/41에서 실제로 재현), 지금은 **매 틱 `restore("initial")`로
막전위·게이팅 변수를 초기화**하고 환경 상태(위치·방향·궤적)만 파이썬
쪽에서 이어 간다.

## 수동 조종(docs/45)

수동 조종에서는 개체가 브라우저에서 실측 속도로 실시간 이동하고, 이 모듈은
보내온 "지금 위치"에서 감각을 1회 계산한다(`_run_manual_tick`). 직전 계산
이후 흐른 생물학적 시간이 100ms가 아니므로 ΔC를 틱당 변화율로 환산한다.
뇌가 pirouette를 결정하면 반사 동작(`reflex`)을 제안만 하고, 적용 여부는
사용자의 '반사 반응 허용' 설정이 정한다.

## 정직하게 밝히는 근사

- **감각 전류 이득(`_SENSORY_GAIN`)은 손튜닝값**이다. 실제 AWC/ASE가
  농도 변화율을 전류로 얼마나 변환하는지 측정한 값이 아니라, 이 모듈의
  가우시안 농도장(반경/시그마)에서 전형적인 틱당 농도 변화가 기존
  명령 경로가 이미 효과적이라고 검증한 자극 크기(`_STIMULUS_CURRENT=
  0.6nA`, `hh_model.py`)에 맞먹는 신호가 되도록 역산한 값이다.
- **농도장은 가우시안 근사**다 -- 실제 한천 배지 위 확산 방정식을 풀지
  않는다. 점 광원에서의 확산을 가우시안으로 근사하는 것은 C. elegans
  화학주성 시뮬레이션 문헌(예: Izquierdo & Lockery류 신경역학 모델)에서
  흔히 쓰이는 표준적 단순화다.
- **재정향 각도는 균등분포(-180~180도)**다. 실제 pirouette 재정향이
  완전히 무작위인지, 어느 정도 편향돼 있는지는 문헌에 정량 분포가 따로
  있지만 이번 범위에서는 재구현하지 않았다 -- 정성적으로 "넓게
  재정향한다"는 사실만 반영.
- **klinotaxis(AIY 기반 미세 조향)는 구현하지 않았다** -- run 도중
  진행 방향이 부드럽게 휘는 건 이 모델에 없다. pirouette 빈도 변조만으로
  생기는 편향된 무작위 걷기(biased random walk)만 구현했다 -- 이것만
  으로도 실제 문헌상 유인물질 쪽으로의 순이동은 일어나지만, 실제 웜보다
  덜 효율적인 경로를 그릴 것이다.
- **몸 전체 RFT 파동 이동(frontend rft-locomotion.ts)은 쓰지 않았다** --
  이 폐루프는 "run 구간 동안 실측 속도로 직진, pirouette 때 반전+재정향"
  이라는, 실제 화학주성 행동 문헌 자체가 채택하는 거친 입자(point
  particle) 수준에서 움직인다. RFT는 개별 명령 1회의 몸통 파형을
  프론트엔드에서 애니메이션으로 보여주기 위한 것이라 이 폐루프의 목적
  (신경회로 -> 행동 결정)과는 결이 다르다 -- 두 시스템을 억지로 합치지
  않았다.
"""

from __future__ import annotations

import math
import random
import threading
from dataclasses import dataclass, field
from typing import Literal

from brian2 import nA, ms

from app.lab.schemas import (
    VirtualOrganismPoseIn,
    VirtualOrganismReflexOut,
    VirtualWormNeuronActivityOut,
    VirtualWormStateOut,
    VirtualWormStepResponse,
    VirtualWormTickOut,
)
from app.lab.virtual_common import (
    MAX_REFLEX_BACK_FRACTION,
    EpisodeStats,
    StaleRunError,
    StimulusSwitch,
    clamp_to_disc,
    extend_trail,
    next_run_id,
)
from app.simulation.hh_model import SignModel, _NetworkAssets, _construct_network_assets

# --- 환경 (WormBook Hart 2006 표준 화학주성 배지 -- 지름 약 9cm NGM
# 플레이트를 그대로 축척) ---
ARENA_RADIUS_UM = 45000.0
SOURCE_POS_UM = (0.0, 35000.0)  # 기본 유인물질 점 광원 -- 가장자리 근처(사용자가 옮길 수 있음, docs/45)
# 시작 위치(docs/47): 광원에서 40mm. 원래(docs/41)는 반대쪽 가장자리(70mm)였는데, docs/46 H7에서 그곳이
# 감각 문턱 때문에 기울기를 전혀 못 느끼는 사각지대(>약 55-58mm)라는 걸 확인했다 -- 그 자리에서는 감각을
# 끈 웜과 궤적이 똑같았다. 감지 구간(현재 설정에서 약 5-55mm, docs/47 재측정) 안쪽에 여유를 두고 놓는다.
START_POS_UM = (0.0, -5000.0)
# 시작 방향은 광원 '반대쪽'(-y). 원래는 광원을 정면으로 보고 출발해서, 광원에 닿는 것이 감각 덕인지 알 수
# 없었다. 반대로 출발하면 뇌가 농도 감소를 감지해 돌아서야만 광원에 갈 수 있다.
START_HEADING_RAD = -math.pi / 2
GRADIENT_SIGMA_UM = 25000.0  # 가우시안 확산 근사의 폭 -- 측정값 아님, 모델링 선택
REACHED_SOURCE_RADIUS_UM = 3000.0  # 약 4 체장(체장 ~722um, docs/22 EM 실측) 이내면 "도달"로 판정
SOURCE_MAX_RADIUS_UM = ARENA_RADIUS_UM * 0.95

# --- 실측 문헌에 도킹된 속도 (docs/22: Fang-Yen et al. 2010, PNAS
# 107:20323, 실측 크롤링 속도 200-400um/s -- 이 프로젝트가 이미 검증한 296.0um/s를 재사용) ---
RUN_SPEED_UM_S = 296.0
PIROUETTE_BACK_FRACTION = MAX_REFLEX_BACK_FRACTION  # 반전 단계에서 run 속도 대비 후진 거리 비율 -- 손튜닝

TICK_DURATION_MS = 100.0  # 틱당 실제 생물학적 시간 -- hh_model._SIM_DURATION(단일 명령 100ms)과 같은 자릿수
_SENSORY_STIM_MS = 20.0  # 감각 전류를 실제로 주입하는 구간 -- hh_model._STIMULUS_DURATION(=20ms/100ms)과 동일한 비율.
# 처음엔 틱 전체(100ms) 동안 계속 주입해봤는데, 재부팅(restore) 없이 이어지는 이 연속 시뮬레이션에서는
# 그러면 네트워크가 자극이 사라진 뒤에도 반전/전진 인터뉴런이 계속 수십 회씩 발화하는 고착 상태에
# 빠져 dC 부호와 무관하게 매 틱 pirouette로 고정되는 실제 문제가 있었다(직접 재현해 확인). 기존
# 단일 명령 모델이 이미 안정적으로 쓰는 "짧게 자극 -> 나머지는 휴지"(stim/relax) 패턴을 그대로
# 재사용해 해결 -- 이 네트워크의 결합 강도가 애초에 짧은 펄스 1회짜리 시나리오에 맞춰 손튜닝됐다는
# 뜻이기도 하다(모듈 docstring의 "정직하게 밝히는 근사" 참고).

SENSORY_NEURON_IDS: tuple[str, ...] = ("AWCL", "AWCR", "ASEL", "ASER")
# docs/47: 시냅스 부호 규칙과 감각 극성. "all_off"는 docs/41의 원래 방식(4개 모두 농도 감소에 반응),
# "biological"은 실제 문헌대로 ASEL만 농도 증가(ON)에 반응(Suzuki et al. 2008) -- 나머지는 감소(OFF).
# 기본값은 가장 생물학적인 조합(수용체 기반 부호 + 실제 극성). docs/46 H10에서 원래 부호 규칙으론
# 올바른 극성이 화학주성을 망가뜨렸지만(순이동 -0.26mm), 수용체 기반 부호와 함께면 +3.31mm(7/8)로
# 원래 방식(+3.44mm)과 거의 같게 동작함을 폐루프로 확인했다(docs/47).
SIGN_MODEL: SignModel = "receptor_predicted"
SENSORY_POLARITY: Literal["all_off", "biological"] = "biological"
ON_SENSORY_IDS: tuple[str, ...] = ("ASEL",)
FORWARD_READOUT_IDS: tuple[str, ...] = ("AVBL", "AVBR")
REVERSE_READOUT_IDS: tuple[str, ...] = ("AVAL", "AVAR")

_SENSORY_CURRENT_MAX = 0.6 * nA  # hh_model._STIMULUS_CURRENT와 동일한 크기 재사용
_SENSORY_GAIN = 600.0  # 손튜닝 -- 이 농도장에서 전형적인 틱당 감소폭을 0.6nA급 신호로 역산 (모듈 docstring 참고)

_HONESTY_NOTE = (
    "이것은 실제 관찰이 아니라 이 프로젝트의 시뮬레이션입니다 -- 실제 302개 뉴런 커넥톰(Brian2 HH 모델)으로 "
    "klinokinesis(농도 감소 시 반전+재정향 빈도 증가) 메커니즘만 구현했고, klinotaxis(정밀 조향)는 이번 범위에 "
    "포함되지 않았습니다. 농도장은 가우시안 근사이며 실제 한천 배지 확산을 풀지 않았습니다. 시냅스 흥분/억제는 "
    "수용체 발현 기반 예측(Fenyves et al. 2020)을 쓰고(예측이 없는 시냅스는 GABA만 억제성), 감각 극성은 실제대로 "
    "AWC·ASER=농도 감소, ASEL=농도 증가에 반응합니다(docs/47)."
)


@dataclass
class _VirtualWormState:
    assets: _NetworkAssets
    tick: int = 0
    x_um: float = START_POS_UM[0]
    y_um: float = START_POS_UM[1]
    heading_rad: float = START_HEADING_RAD
    source_x_um: float = SOURCE_POS_UM[0]
    source_y_um: float = SOURCE_POS_UM[1]
    prev_concentration: float = 0.0
    trail: list[list[float]] = field(default_factory=list)
    reached_source: bool = False
    stats: EpisodeStats = field(default_factory=EpisodeStats)
    run_id: int = field(default_factory=next_run_id)
    stim: StimulusSwitch | None = None


_state: _VirtualWormState | None = None
# 실제로 잡은 버그: FastAPI가 /reset·/state·/step을 각각 별도 스레드풀 스레드에서
# 처리하므로(run_in_threadpool), "자동 재생" 도중 "다시 시작"을 누르는 등으로
# reset()이 step()의 다중 틱 루프 도중 전역 _state를 재할당하면 실제로 Brian2
# StopIteration("Clock has reached the end of its available times.")이 나면서
# 진행 중이던 요청이 503으로 실패했다 -- 라이브로 재현해 확인. 락으로
# read-modify-write를 원자적으로 만들어 고쳤다 -- 두 번째 요청은 깨지는 대신
# 첫 요청이 끝날 때까지 대기한다.
_lock = threading.Lock()


def _concentration_at(st: _VirtualWormState, x_um: float, y_um: float) -> float:
    dx = x_um - st.source_x_um
    dy = y_um - st.source_y_um
    return math.exp(-(dx * dx + dy * dy) / (2.0 * GRADIENT_SIGMA_UM**2))


def _distance_to_source(st: _VirtualWormState, x_um: float, y_um: float) -> float:
    return math.hypot(x_um - st.source_x_um, y_um - st.source_y_um)


def _clamp_to_arena(x_um: float, y_um: float, heading_rad: float) -> tuple[float, float, float]:
    r = math.hypot(x_um, y_um)
    if r <= ARENA_RADIUS_UM:
        return x_um, y_um, heading_rad
    # 벽에 닿음 -- 경계로 clamp하고 안쪽으로 재정향(실제 벽 접촉 물리는 아님, 화면 밖으로 나가지 않게 하는 편의적 처리)
    scale = ARENA_RADIUS_UM / r
    clamped_x, clamped_y = x_um * scale, y_um * scale
    inward_heading = math.atan2(-clamped_y, -clamped_x)
    jitter = random.uniform(-math.pi / 4, math.pi / 4)
    return clamped_x, clamped_y, inward_heading + jitter


def _fresh_state() -> _VirtualWormState:
    assets = _construct_network_assets(SIGN_MODEL)
    st = _VirtualWormState(assets=assets, stim=StimulusSwitch(assets, _SENSORY_STIM_MS))
    st.prev_concentration = _concentration_at(st, st.x_um, st.y_um)
    st.trail.append([st.x_um, st.y_um])
    st.stats.closest_um = _distance_to_source(st, st.x_um, st.y_um)
    return st


def _to_state_out(st: _VirtualWormState) -> VirtualWormStateOut:
    return VirtualWormStateOut(
        tick=st.tick,
        x_um=st.x_um,
        y_um=st.y_um,
        heading_deg=math.degrees(st.heading_rad) % 360.0,
        concentration=_concentration_at(st, st.x_um, st.y_um),
        arena_radius_um=ARENA_RADIUS_UM,
        source_x_um=st.source_x_um,
        source_y_um=st.source_y_um,
        gradient_sigma_um=GRADIENT_SIGMA_UM,
        trail=[list(p) for p in st.trail],
        reached_source=st.reached_source,
        stats=st.stats.to_out(),
        run_id=st.run_id,
        honesty_note=_HONESTY_NOTE,
    )


def _ensure_state() -> _VirtualWormState:
    global _state
    if _state is None:
        _state = _fresh_state()
    return _state


def reset_virtual_worm() -> VirtualWormStateOut:
    global _state
    with _lock:
        _state = _fresh_state()
        return _to_state_out(_state)


def get_virtual_worm_state() -> VirtualWormStateOut:
    with _lock:
        return _to_state_out(_ensure_state())


def set_virtual_worm_source(x_um: float, y_um: float) -> VirtualWormStateOut:
    """유인물질 광원을 옮긴다(docs/45). 농도장이 순간적으로 새 위치에서 다시
    형성된다고 가정하므로(가우시안 근사의 한계), 옮긴 순간의 농도 급변이
    가짜 ΔC 자극이 되지 않게 직전 농도를 새 값으로 맞추고 기록 구간을 새로 시작한다."""
    with _lock:
        st = _ensure_state()
        st.source_x_um, st.source_y_um = clamp_to_disc(x_um, y_um, SOURCE_MAX_RADIUS_UM)
        st.prev_concentration = _concentration_at(st, st.x_um, st.y_um)
        st.reached_source = False
        st.stats.restart(_distance_to_source(st, st.x_um, st.y_um))
        return _to_state_out(st)


def set_virtual_worm_pose(pose: VirtualOrganismPoseIn) -> VirtualWormStateOut:
    """신경 계산 없이 위치만 맞춘다 -- 수동 조종에서 자동으로 넘어갈 때, 브라우저에서
    움직인 마지막 위치를 서버 상태로 확정하는 용도. 감각 이력(직전 농도)도 새 위치로 맞춘다."""
    with _lock:
        st = _ensure_state()
        _check_run(st, pose)
        _apply_manual_pose(st, pose)
        st.prev_concentration = _concentration_at(st, st.x_um, st.y_um)
        return _to_state_out(st)


def _check_run(st, pose: VirtualOrganismPoseIn) -> None:
    if pose.run_id is not None and pose.run_id != st.run_id:
        raise StaleRunError(f"pose for run {pose.run_id}, current run is {st.run_id}")


def _apply_manual_pose(st: _VirtualWormState, pose: VirtualOrganismPoseIn) -> None:
    x, y = clamp_to_disc(pose.x_um, pose.y_um, ARENA_RADIUS_UM)
    moved = extend_trail(st.trail, [*pose.path, [x, y]])
    st.x_um, st.y_um = x, y
    st.heading_rad = math.radians(pose.heading_deg)
    st.stats.distance_um += moved
    st.stats.bio_ms += pose.elapsed_bio_ms
    _update_proximity(st)


def _update_proximity(st: _VirtualWormState) -> None:
    d = _distance_to_source(st, st.x_um, st.y_um)
    st.stats.closest_um = min(st.stats.closest_um, d)
    if d <= REACHED_SOURCE_RADIUS_UM and not st.reached_source:
        st.reached_source = True
        st.stats.reached_at_ms = st.stats.bio_ms


def _run_network(st: _VirtualWormState, delta_c_per_tick: float) -> tuple[int, int, list[VirtualWormNeuronActivityOut]]:
    """실제 302개 뉴런 네트워크를 한 틱(100ms) 돌린다 -- 매 틱 restore("initial")로
    막전위를 초기화한다(docs/41의 영구 고착 버그 수정). 자극은 ΔC<0일 때만(AWC/ASE의
    실제 OFF-response 극성)."""
    assets = st.assets
    off_current = min(1.0, max(0.0, -delta_c_per_tick) * _SENSORY_GAIN) * _SENSORY_CURRENT_MAX
    on_current = min(1.0, max(0.0, delta_c_per_tick) * _SENSORY_GAIN) * _SENSORY_CURRENT_MAX
    on_ids = ON_SENSORY_IDS if SENSORY_POLARITY == "biological" else ()
    currents = {}
    for nid in SENSORY_NEURON_IDS:
        if nid in assets.index_of:
            currents[assets.index_of[nid]] = on_current if nid in on_ids else off_current

    assert st.stim is not None
    st.stim.run_tick_currents(currents, TICK_DURATION_MS)
    tick_start_t = 0.0  # restore("initial") 직후라 이 틱의 시작 시각은 항상 0

    spikes = assets.net["spikemon"]
    spike_i = spikes.i[:]
    in_window = (spikes.t / ms) >= tick_start_t

    def _count(neuron_ids: tuple[str, ...]) -> int:
        total = 0
        for nid in neuron_ids:
            idx = assets.index_of.get(nid)
            if idx is not None:
                total += int(((spike_i == idx) & in_window).sum())
        return total

    sensory = [VirtualWormNeuronActivityOut(neuron_id=nid, spike_count=_count((nid,))) for nid in SENSORY_NEURON_IDS]
    return _count(FORWARD_READOUT_IDS), _count(REVERSE_READOUT_IDS), sensory


def _decide(forward_spikes: int, reverse_spikes: int) -> Literal["run", "pirouette"]:
    return "pirouette" if reverse_spikes > forward_spikes and reverse_spikes > 0 else "run"


def _run_one_tick(st: _VirtualWormState) -> VirtualWormTickOut:
    """자동(커넥톰) 틱: 뇌의 결정대로 실제로 움직인다."""
    current_c = _concentration_at(st, st.x_um, st.y_um)
    delta_c = current_c - st.prev_concentration
    forward_spikes, reverse_spikes, sensory = _run_network(st, delta_c)
    event = _decide(forward_spikes, reverse_spikes)

    tick_duration_s = TICK_DURATION_MS / 1000.0
    if event == "pirouette":
        back_dist = RUN_SPEED_UM_S * tick_duration_s * PIROUETTE_BACK_FRACTION
        new_x = st.x_um - back_dist * math.cos(st.heading_rad)
        new_y = st.y_um - back_dist * math.sin(st.heading_rad)
        new_heading = random.uniform(-math.pi, math.pi)
        st.stats.reorient_decisions += 1
    else:
        step_dist = RUN_SPEED_UM_S * tick_duration_s
        new_x = st.x_um + step_dist * math.cos(st.heading_rad)
        new_y = st.y_um + step_dist * math.sin(st.heading_rad)
        new_heading = st.heading_rad

    new_x, new_y, new_heading = _clamp_to_arena(new_x, new_y, new_heading)

    st.tick += 1
    st.stats.auto_ticks += 1
    st.stats.bio_ms += TICK_DURATION_MS
    st.stats.distance_um += extend_trail(st.trail, [[new_x, new_y]])
    st.x_um, st.y_um, st.heading_rad = new_x, new_y, new_heading
    st.prev_concentration = current_c
    _update_proximity(st)

    return VirtualWormTickOut(
        tick=st.tick,
        x_um=new_x,
        y_um=new_y,
        heading_deg=math.degrees(new_heading) % 360.0,
        concentration=_concentration_at(st, new_x, new_y),
        delta_concentration=delta_c,
        event=event,
        forward_spikes=forward_spikes,
        reverse_spikes=reverse_spikes,
        sensory_activity=sensory,
        reached_source=st.reached_source,
        control="auto",
        bio_time_s=st.stats.to_out().bio_time_s,
    )


def _run_manual_tick(st: _VirtualWormState, pose: VirtualOrganismPoseIn) -> VirtualWormTickOut:
    """수동 조종 틱(docs/45): 브라우저가 실시간으로 움직인 위치를 받아 그 자리에서 감각을
    계산한다. 직전 계산 이후 흐른 생물학적 시간이 100ms가 아니므로, 농도 변화를 틱(100ms)당
    변화율로 환산해 자동 틱과 같은 감각 이득(_SENSORY_GAIN) 기준에 맞춘다."""
    _apply_manual_pose(st, pose)
    current_c = _concentration_at(st, st.x_um, st.y_um)
    delta_c = (current_c - st.prev_concentration) * (TICK_DURATION_MS / max(1.0, pose.elapsed_bio_ms))
    forward_spikes, reverse_spikes, sensory = _run_network(st, delta_c)
    event = _decide(forward_spikes, reverse_spikes)

    reflex = None
    if event == "pirouette":
        st.stats.reorient_decisions += 1
        reflex = VirtualOrganismReflexOut(
            back_um=RUN_SPEED_UM_S * (TICK_DURATION_MS / 1000.0) * PIROUETTE_BACK_FRACTION,
            new_heading_deg=random.uniform(0.0, 360.0),
        )

    st.tick += 1
    st.stats.manual_ticks += 1
    st.prev_concentration = current_c

    return VirtualWormTickOut(
        tick=st.tick,
        x_um=st.x_um,
        y_um=st.y_um,
        heading_deg=math.degrees(st.heading_rad) % 360.0,
        concentration=current_c,
        delta_concentration=delta_c,
        event=event,
        forward_spikes=forward_spikes,
        reverse_spikes=reverse_spikes,
        sensory_activity=sensory,
        reached_source=st.reached_source,
        control="manual",
        reflex=reflex,
        bio_time_s=st.stats.to_out().bio_time_s,
    )


def step_virtual_worm(n_ticks: int = 1, manual: VirtualOrganismPoseIn | None = None) -> VirtualWormStepResponse:
    with _lock:
        st = _ensure_state()  # 락 안에서 한 번만 바인딩 -- 루프 도중 다른 요청이 전역을 바꿀 수 없다
        if manual is not None:
            _check_run(st, manual)
            ticks = [_run_manual_tick(st, manual)]
        else:
            ticks = [_run_one_tick(st) for _ in range(n_ticks)]
        return VirtualWormStepResponse(ticks=ticks, state=_to_state_out(st))
