"""가상 초파리 폐루프 환경 시뮬레이션 (docs/42). [[virtual_worm.py]](docs/41)의
웜 폐루프와 같은 정신(환경 → 실제 감각 자극 → 실제 Brian2 네트워크 →
실제 명령 출력 판정 → 이동 → 환경)이지만, 종이 다르므로 메커니즘도 다른
실제 문헌에 각각 따로 근거한다 — 억지로 같은 메커니즘을 복붙하지 않았다.

## 실제 생물학적 근거: MBON 밸런스 기반 회피

이 프로젝트의 실제 후각 회로 데이터셋(`app/data/drosophila_connectome.json`,
hemibrain)에는 이미 검증된 실제 2단 경로가 있다(`fly_engine.py`의
`_PATHWAYS`): DA1(페로몬 cVA) 냄새는 실제 PN(`754538881`) → 실제
KC(`5813053885`) → 실제 MBON01(`612371421`, hemibrain 명명 `MBON01(y5B'2a)`)로
이어진다. Aso et al. 2014(eLife 3:e04577, "The neuronal architecture of the
mushroom body provides a logic for associative learning")는 γ5/β'2
구획(정확히 MBON01이 있는 구획)을 지배하는 글루타메이트성 MBON들이
**활성화 시 하풍(downwind) 이동과 회피(avoidance) 행동을 유도한다**고
직접 보고했다 — 이게 이 모듈이 구현하는 실제 근거다. 다른 33개 MBON
유형(MBON02-MBON35)은 이 프로젝트의 기존 경로 데이터가 검증된 밸런스
해석을 제공하지 않아 **의도적으로 쓰지 않았다** — 확인 안 된 유의성을
지어내지 않는다.

웜의 klinokinesis(농도 변화율 기반)와 달리, 이 모듈은 **농도 크기 자체**를
PN 자극 전류에 직접 매핑한다 — ORN/PN 발화율이 냄새 농도에 비례한다는
건 교과서 수준의 실제 소견(예: Hallem & Carlson 2006의 농도-반응
곡선류)이라 이쪽이 더 직접적인 근거다.

## 실제로 확인한 것: 이 네트워크는 매끄러운 비례 반응이 아니라 문턱형이다

PN 자극 전류를 0.02~1.0×(기존 검증된 최대 자극 0.6nA) 범위로 스윕해서
실제로 돌려본 결과, 이 회로(~2,452개 뉴런, hh_model.py의 302개짜리 웜
네트워크보다 훨씬 크고 조밀하게 연결됨)는 매끄러운 비례 반응이 아니라
뚜렷한 **문턱형(all-or-none에 가까운)** 반응을 보였다: 0.06nA(최대
자극의 10%) 이하에서는 자극받은 PN 자신도 전혀 발화하지 않다가, 0.06~
0.12nA(10~20%) 사이 어딘가에서 전체 네트워크가 한 번에 100ms 동안 약
4~5만 스파이크(뉴런당 평균 십여 회)라는 강한 활동으로 전환됐다(정확한
문턱값은 네트워크 상태에 따라 이 구간 안에서 조금씩 움직임 — 실제
폐루프 구동 중 0.087nA에서 회피가 발동한 사례도 이 구간과 일치) —
문턱 위에서는 자극을 더 세게 줘도(20%→100%) MBON01 발화 수가 오히려
크게 늘지 않았다(52~74회, 뚜렷한 추가 비례 없음). 이건 이 프로젝트가
웜 쪽에서 이미 발견한 "이 손튜닝
전도도값은 단발 펄스 시나리오에만 맞춰져 있다"([[virtual_worm.py]] 참고)는
사실의 또 다른 증거로 읽힌다 — 초파리 네트워크가 시냅스 수/연결
밀도가 더 커서 더 쉽게(더 낮은 문턱에서) 재귀적 흥분 폭주에 들어간다.

**이걸 버그로 보지 않고 설계에 그대로 활용했다**: 이 모듈의 행동 결정
자체가 이미 이진(회피 발동 여부)이라, "문턱을 넘었는가"를 그대로
회피 트리거로 쓰면 된다 — 오히려 실제 네트워크 동역학이 만들어낸
자연스러운 "탐지 반경"이 생긴다(임의로 정한 상수가 아니라 이 회로 자체의
실제 반응 곡선에서 나온 것). 가우시안 농도장의 시그마(`GRADIENT_SIGMA_UM`)를
아레나보다 충분히 작게 잡아, 탐지 반경이 아레나 전체를 뒤덮지 않고
"안전 지대"와 "냄새 근처"가 공존하도록 손튜닝했다 — 이 시그마 값 자체는
측정값이 아니라 데모 상 흥미로운 궤적이 나오게 고른 값임을 밝힌다.

## 실제로 다시 확인한 것: 재시작 없는 연속 시뮬레이션의 위험

[[virtual_worm.py]](docs/41)가 겪은 것과 같은 급의 문제(한 번 자극 후
네트워크가 외부 입력 없이도 계속 발화하는 영구 고착)를 이 회로에서도
예상해야 한다 — 오히려 위에서 확인했듯 이 네트워크는 웜보다 훨씬 쉽게
강한 흥분 상태로 전환된다. 따라서 웜과 동일한 해법을 **처음부터**
채택한다: 매 틱 감각 전류를 주입하기 직전 `net.restore("initial")`을
호출해 막전위·게이팅 변수를 재초기화하고, 환경 상태(위치·방향·궤적)만
파이썬 쪽에서 이어간다.

## 정직하게 밝히는 근사

- **회피 방향(docs/47에서 변경)**: 원래는 완전 무작위 재정향이었는데, docs/46 H12에서 그 방식이
  냄새 구역 안에서 무작위 걸음이 되어 오히려 깊이 들어가거나 갇히는 '새는' 배제 구역을 만든다는 걸
  확인했다. 지금은 직전 틱 대비 농도가 올랐으면 반대로(±30도), 이미 내려가는 중이면 그대로(±30도)
  물러난다 -- 뇌가 받는 입력(농도에 비례한 PN 전류)의 시간 비교만 쓰고 광원 위치는 쓰지 않는다.
  실제 보행 초파리도 냄새만으로 시작/소실에 따라 회전·속도를 바꾸지만, 바람 방향 같은 '절대 방향'
  선택엔 더듬이 기계감각이 필요하다고 보고됨(Álvarez-Salvado et al. 2018, eLife 7:e37815) --
  '반대로 돈다'는 규칙 자체는 이 모델의 단순화다. 아래는 원래(docs/42) 선택의 이유:
  광원 위치를 알고 그 반대쪽으로
  정확히 도망가게 만들지 않았다(웜의 pirouette와 동일한 선택: "실제
  회로가 아는 것"과 "시뮬레이션이 치트로 아는 것"을 섞지 않으려는
  의도적 선택). 실제로는 더 정교한 양측(좌우 ORN 비대칭) 조향 메커니즘이
  있을 수 있지만, 이 프로젝트의 후각 회로 데이터셋은 PN 1개만 자극하는
  구조라 좌우 비대칭 신호 자체가 없다 — 구현하지 않은 게 아니라 애초에
  이 데이터로는 만들 수 없다.
- **순항(cruise) 중 무작위 방향 전환(jitter)은 손튜닝값**이다 — 실제
  초파리가 자발적으로 탐색적 전환을 한다는 정성적 사실은 실제 문헌에
  있지만(예: 보행 중 saccade류 전환, Geurten et al. 2014), 이 모듈의
  틱당 ±12도 균등분포는 그 정량 분포를 재현한 게 아니라 데모용 손튜닝.
- **보행 속도(28,000μm/s)는 실측 문헌값**이다 — Mendes, Bartos, Akay,
  Márka & Mann 2013(eLife 2:e00231)의 자유보행 성체 초파리 실측
  대표속도(약 28mm/s, 범위 7.2-44.7mm/s)를 그대로 사용, 새로 지어내지
  않음.
- **MBON01 외 나머지 33개 MBON 유형은 이 모듈에 전혀 관여하지 않는다** —
  이 프로젝트의 기존 경로 데이터가 실제로 검증한 값은 MBON01/MBON05
  둘뿐이고, 그중 밸런스(회피/접근) 방향이 실제 문헌으로 확인된 건
  MBON01 하나뿐이었다.

## 수동 조종과 비행(docs/45)

수동 조종에서는 개체가 브라우저에서 실측 속도로 실시간 이동(보행 28mm/s,
비행 약 150mm/s -- Fry, Rohrseitz, Straw & Dickinson 2009, J Exp Biol
212:1120의 자유비행 평균 속도 0.15m/s)하고, 이 모듈은 보내온 위치에서
냄새를 1회 감지해 회로를 돌린다. 비행 중 농도는 바닥 광원에서의 3D 거리로
같은 가우시안을 확장해 계산한다(실제 냄새 플룸 모델 아님). 뇌가 회피를
결정하면 반사 동작(`reflex`)을 제안만 한다.
"""

from __future__ import annotations

import math
import random
import threading
from dataclasses import dataclass, field
from typing import Literal

from brian2 import nA, ms

from app.lab.schemas import (
    VirtualFlyStateOut,
    VirtualFlyStepResponse,
    VirtualFlyTickOut,
    VirtualOrganismPoseIn,
    VirtualOrganismReflexOut,
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
from app.simulation.fly_hh_model import _NetworkAssets, _construct_network_assets

# --- 환경 -- 실제 초파리 보행 관찰용 소형 아레나 규모(수 cm 단위)를
# 모델링한 것으로, 특정 논문의 정확한 치수를 재현한 게 아님(웜 아레나가
# WormBook 표준 플레이트를 축척한 것과 달리 정직하게 다른 근거 수준) ---
ARENA_RADIUS_UM = 30000.0
CHAMBER_HEIGHT_UM = 40000.0  # docs/45: 비행을 위해 벽을 높인 투명 챔버 높이 -- 데모 규모 선택, 측정값 아님
SOURCE_POS_UM = (0.0, 22000.0)  # 기본 혐오 자극(DA1/cVA) 점 광원 -- 바닥(z=0)의 여과지, 사용자가 옮길 수 있음
START_POS_UM = (0.0, -10000.0)  # 광원을 향한 방향으로 순항을 시작해 탐지 반경 진입을 관찰할 수 있게 배치
GRADIENT_SIGMA_UM = 8000.0  # 실제 회로의 문턱형 반응(위 docstring)을 감안해, 탐지 반경이 아레나 일부에만 걸치도록 손튜닝
START_HEADING_DEG = 100.0  # 대략 광원 쪽을 향해 순항 시작
SOURCE_MAX_RADIUS_UM = ARENA_RADIUS_UM * 0.92

# Mendes, Bartos, Akay, Márka & Mann 2013 (eLife 2:e00231) — 자유보행
# 성체 초파리 실측 대표 속도(범위 7.2-44.7mm/s, 대표값 약 28mm/s)
RUN_SPEED_UM_S = 28000.0
AVOIDANCE_BACK_FRACTION = MAX_REFLEX_BACK_FRACTION  # virtual_worm.py의 pirouette 후진 비율과 동일한 손튜닝 관행 재사용
CRUISE_JITTER_DEG = 12.0  # 손튜닝 -- 실제 탐색적 방향전환의 정성적 근거는 있으나 정량 분포는 아님(모듈 docstring 참고)

# docs/47: 회피 방향 규칙. docs/46 H12에서 "완전 무작위 재정향"은 경계 감지는 정확해도 구역 안에서
# 1.4mm 보폭의 무작위 걸음이 되어 더 깊이 들어가거나 갇히는 '새는' 배제 구역을 만든다는 걸 확인했다.
# "directed"는 직전 틱 대비 농도가 올랐으면(냄새 쪽으로 들어가던 중) 방향을 반대로(±30도), 이미
# 내려가는 중이었으면 그 방향을 유지(±30도)한 채 물러난다 -- 뇌가 매 틱 실제로 받는 정보(현재/직전
# 농도에 비례한 PN 입력)만 쓰는 시간 비교이고, 웜 klinokinesis와 같은 종류의 정보다. 광원 위치를
# 몰래 쓰지 않는다(docs/42의 원칙 유지). 반대 방향 폭 ±30도는 손튜닝.
AVOIDANCE_MODE: Literal["random", "directed"] = "directed"
DIRECTED_AVOID_JITTER_DEG = 30.0


def _avoidance_turn(st: "_VirtualFlyState", current_c: float) -> tuple[float, bool]:
    """회피 시 새 방향과 '반대로 돌았는가'. random 모드는 docs/42 원래 동작."""
    if AVOIDANCE_MODE == "random":
        return random.uniform(-math.pi, math.pi), True
    rising = st.prev_concentration is None or current_c > st.prev_concentration
    jitter = math.radians(random.uniform(-DIRECTED_AVOID_JITTER_DEG, DIRECTED_AVOID_JITTER_DEG))
    if rising:
        return st.heading_rad + math.pi + jitter, True
    return st.heading_rad + jitter, False

TICK_DURATION_MS = 100.0
_SENSORY_STIM_MS = 20.0  # fly_hh_model._STIMULUS_DURATION과 동일 비율 -- virtual_worm.py가 이미 찾은 stim/relax 패턴 재사용

ODOR_PN_ID = "754538881"  # DA1(cVA) 사구체 PN -- fly_engine._PATHWAYS[OdorCommand.DA1]과 동일
MBON_AVOIDANCE_ID = "612371421"  # MBON01(y5B'2a) -- Aso et al. 2014, 활성화 시 회피/하풍 이동 유도로 보고됨

_STIMULUS_CURRENT_MAX = 0.6 * nA  # fly_hh_model._STIMULUS_CURRENT와 동일한 크기 재사용

_HONESTY_NOTE = (
    "이것은 실제 관찰이 아니라 이 프로젝트의 시뮬레이션입니다 -- 실제 초파리 후각 회로(hemibrain, ~2,452개 뉴런, "
    "Brian2 HH 모델)로 DA1(페로몬 cVA) 냄새 → PN → KC → MBON01 경로만 구현했고, MBON01(y5B'2a)이 활성화되면 "
    "회피 행동을 유도한다는 것만 Aso et al. 2014로 확인된 실제 근거입니다. 회피 방향은 직전 대비 냄새가 짙어지는 "
    "중이었으면 반대로, 옅어지는 중이었으면 그대로 물러나는 단순화된 규칙이며(광원 위치는 쓰지 않음, docs/47), "
    "농도장은 가우시안 근사입니다(비행 중엔 바닥 광원에서의 3D 거리로 확장)."
)


@dataclass
class _VirtualFlyState:
    assets: _NetworkAssets
    tick: int = 0
    x_um: float = START_POS_UM[0]
    y_um: float = START_POS_UM[1]
    z_um: float = 0.0
    heading_rad: float = math.radians(START_HEADING_DEG)
    source_x_um: float = SOURCE_POS_UM[0]
    source_y_um: float = SOURCE_POS_UM[1]
    trail: list[list[float]] = field(default_factory=list)
    stats: EpisodeStats = field(default_factory=EpisodeStats)
    run_id: int = field(default_factory=next_run_id)
    stim: StimulusSwitch | None = None
    # docs/47: 직전 틱에 감지한 농도 -- 회피 방향을 고를 때 "냄새 쪽으로 들어가는 중이었나"를 판단
    prev_concentration: float | None = None


_state: _VirtualFlyState | None = None
# virtual_worm.py와 동일한 실제 동시성 버그 수정(docs/43): "자동 재생" 도중
# "다시 시작"을 누르면 reset()이 step()의 다중 틱 루프 도중 전역 _state를
# 재할당해 Brian2 StopIteration으로 요청이 503 실패했다. 락으로
# read-modify-write를 원자적으로 만들었다.
_lock = threading.Lock()


def _concentration_at(st: _VirtualFlyState, x_um: float, y_um: float, z_um: float = 0.0) -> float:
    """바닥(z=0) 점 광원에서의 가우시안 -- 비행 중엔 같은 시그마로 높이까지 포함한
    3D 거리를 쓴다(2D 근사를 그대로 한 차원 확장한 것, 실제 기류/플룸 모델 아님)."""
    dx = x_um - st.source_x_um
    dy = y_um - st.source_y_um
    return math.exp(-(dx * dx + dy * dy + z_um * z_um) / (2.0 * GRADIENT_SIGMA_UM**2))


def _distance_to_source(st: _VirtualFlyState) -> float:
    return math.sqrt((st.x_um - st.source_x_um) ** 2 + (st.y_um - st.source_y_um) ** 2 + st.z_um**2)


def _clamp_to_arena(x_um: float, y_um: float, heading_rad: float) -> tuple[float, float, float]:
    r = math.hypot(x_um, y_um)
    if r <= ARENA_RADIUS_UM:
        return x_um, y_um, heading_rad
    scale = ARENA_RADIUS_UM / r
    clamped_x, clamped_y = x_um * scale, y_um * scale
    inward_heading = math.atan2(-clamped_y, -clamped_x)
    jitter = random.uniform(-math.pi / 4, math.pi / 4)
    return clamped_x, clamped_y, inward_heading + jitter


def _fresh_state() -> _VirtualFlyState:
    assets = _construct_network_assets("olfactory")
    st = _VirtualFlyState(assets=assets, stim=StimulusSwitch(assets, _SENSORY_STIM_MS))
    st.trail.append([st.x_um, st.y_um])
    st.stats.closest_um = _distance_to_source(st)
    return st


def _to_state_out(st: _VirtualFlyState) -> VirtualFlyStateOut:
    return VirtualFlyStateOut(
        tick=st.tick,
        x_um=st.x_um,
        y_um=st.y_um,
        z_um=st.z_um,
        heading_deg=math.degrees(st.heading_rad) % 360.0,
        concentration=_concentration_at(st, st.x_um, st.y_um, st.z_um),
        arena_radius_um=ARENA_RADIUS_UM,
        chamber_height_um=CHAMBER_HEIGHT_UM,
        source_x_um=st.source_x_um,
        source_y_um=st.source_y_um,
        gradient_sigma_um=GRADIENT_SIGMA_UM,
        trail=[list(p) for p in st.trail],
        stats=st.stats.to_out(),
        run_id=st.run_id,
        honesty_note=_HONESTY_NOTE,
    )


def _ensure_state() -> _VirtualFlyState:
    global _state
    if _state is None:
        _state = _fresh_state()
    return _state


def reset_virtual_fly() -> VirtualFlyStateOut:
    global _state
    with _lock:
        _state = _fresh_state()
        return _to_state_out(_state)


def get_virtual_fly_state() -> VirtualFlyStateOut:
    with _lock:
        return _to_state_out(_ensure_state())


def set_virtual_fly_source(x_um: float, y_um: float) -> VirtualFlyStateOut:
    with _lock:
        st = _ensure_state()
        st.source_x_um, st.source_y_um = clamp_to_disc(x_um, y_um, SOURCE_MAX_RADIUS_UM)
        st.stats.restart(_distance_to_source(st))
        st.prev_concentration = None  # 냄새장이 새 위치로 바뀌었으니 옛 비교 기준은 무효
        return _to_state_out(st)


def set_virtual_fly_pose(pose: VirtualOrganismPoseIn) -> VirtualFlyStateOut:
    with _lock:
        st = _ensure_state()
        _check_run(st, pose)
        _apply_manual_pose(st, pose)
        st.prev_concentration = _concentration_at(st, st.x_um, st.y_um, st.z_um)
        return _to_state_out(st)


def _check_run(st, pose: VirtualOrganismPoseIn) -> None:
    if pose.run_id is not None and pose.run_id != st.run_id:
        raise StaleRunError(f"pose for run {pose.run_id}, current run is {st.run_id}")


def _apply_manual_pose(st: _VirtualFlyState, pose: VirtualOrganismPoseIn) -> None:
    x, y = clamp_to_disc(pose.x_um, pose.y_um, ARENA_RADIUS_UM)
    st.stats.distance_um += extend_trail(st.trail, [*pose.path, [x, y]])
    st.x_um, st.y_um = x, y
    st.z_um = min(max(0.0, pose.z_um), CHAMBER_HEIGHT_UM)
    st.heading_rad = math.radians(pose.heading_deg)
    st.stats.bio_ms += pose.elapsed_bio_ms
    st.stats.closest_um = min(st.stats.closest_um, _distance_to_source(st))


def _run_network(st: _VirtualFlyState, concentration: float) -> tuple[float, int]:
    """실제 후각 회로를 한 틱 돌린다. PN 전류는 현재 농도에 비례(Hallem & Carlson 2006류)."""
    assets = st.assets
    pn_current = concentration * _STIMULUS_CURRENT_MAX
    pn_idx = assets.index_of.get(ODOR_PN_ID)
    mbon_idx = assets.index_of.get(MBON_AVOIDANCE_ID)

    assert st.stim is not None
    st.stim.run_tick([pn_idx] if pn_idx is not None else [], pn_current, TICK_DURATION_MS)

    mbon_spikes = 0
    if mbon_idx is not None:
        mbon_spikes = int((assets.net["spikemon"].i[:] == mbon_idx).sum())
    return float(pn_current / nA), mbon_spikes


def _run_one_tick(st: _VirtualFlyState) -> VirtualFlyTickOut:
    """자동(커넥톰) 틱. 자동 모드는 보행만 한다 -- 비행 중이었다면 먼저 착지한다
    (이 회로 데이터엔 비행 개시/제어 뉴런이 없어 뇌가 '날기'를 결정할 근거가 없음)."""
    st.z_um = 0.0
    current_c = _concentration_at(st, st.x_um, st.y_um)
    pn_current_na, mbon_spikes = _run_network(st, current_c)

    tick_duration_s = TICK_DURATION_MS / 1000.0
    event: Literal["cruise", "avoidance"]
    if mbon_spikes > 0:
        event = "avoidance"
        back_dist = RUN_SPEED_UM_S * tick_duration_s * AVOIDANCE_BACK_FRACTION
        new_heading, _ = _avoidance_turn(st, current_c)
        if AVOIDANCE_MODE == "random":
            # docs/42 원래 동작: 옛 방향의 뒤로 후진 + 무작위 재정향
            new_x = st.x_um - back_dist * math.cos(st.heading_rad)
            new_y = st.y_um - back_dist * math.sin(st.heading_rad)
        else:
            # 고른 방향(냄새에서 멀어지는 쪽)으로 물러난다
            new_x = st.x_um + back_dist * math.cos(new_heading)
            new_y = st.y_um + back_dist * math.sin(new_heading)
        st.stats.reorient_decisions += 1
    else:
        event = "cruise"
        new_heading = st.heading_rad + math.radians(random.uniform(-CRUISE_JITTER_DEG, CRUISE_JITTER_DEG))
        step_dist = RUN_SPEED_UM_S * tick_duration_s
        new_x = st.x_um + step_dist * math.cos(new_heading)
        new_y = st.y_um + step_dist * math.sin(new_heading)

    new_x, new_y, new_heading = _clamp_to_arena(new_x, new_y, new_heading)

    st.tick += 1
    st.stats.auto_ticks += 1
    st.stats.bio_ms += TICK_DURATION_MS
    st.stats.distance_um += extend_trail(st.trail, [[new_x, new_y]])
    st.x_um, st.y_um, st.heading_rad = new_x, new_y, new_heading
    st.stats.closest_um = min(st.stats.closest_um, _distance_to_source(st))
    st.prev_concentration = current_c

    return VirtualFlyTickOut(
        tick=st.tick,
        x_um=new_x,
        y_um=new_y,
        z_um=0.0,
        heading_deg=math.degrees(new_heading) % 360.0,
        concentration=_concentration_at(st, new_x, new_y),
        event=event,
        pn_current_na=pn_current_na,
        mbon01_spikes=mbon_spikes,
        control="auto",
        bio_time_s=st.stats.to_out().bio_time_s,
    )


def _run_manual_tick(st: _VirtualFlyState, pose: VirtualOrganismPoseIn) -> VirtualFlyTickOut:
    """수동 조종 틱(docs/45): 보내온 위치(비행 중이면 높이 포함)에서 냄새를 감지해
    실제 회로를 돌린다. 이 경로는 농도 '크기'에 반응하므로 경과 시간 환산이 필요 없다."""
    _apply_manual_pose(st, pose)
    current_c = _concentration_at(st, st.x_um, st.y_um, st.z_um)
    pn_current_na, mbon_spikes = _run_network(st, current_c)

    event: Literal["cruise", "avoidance"] = "avoidance" if mbon_spikes > 0 else "cruise"
    reflex = None
    if event == "avoidance":
        st.stats.reorient_decisions += 1
        new_heading, reversed_ = _avoidance_turn(st, current_c)
        # 프론트는 back_um만큼 '현재 방향의 뒤로' 물러난 뒤 new_heading으로 돈다 -- 이미 냄새에서
        # 멀어지던 중이면(반대로 돌지 않음) 뒤로 물러나면 오히려 냄새 쪽이므로 후진하지 않는다.
        reflex = VirtualOrganismReflexOut(
            back_um=RUN_SPEED_UM_S * (TICK_DURATION_MS / 1000.0) * AVOIDANCE_BACK_FRACTION if reversed_ else 0.0,
            new_heading_deg=math.degrees(new_heading) % 360.0,
        )

    st.prev_concentration = current_c
    st.tick += 1
    st.stats.manual_ticks += 1
    return VirtualFlyTickOut(
        tick=st.tick,
        x_um=st.x_um,
        y_um=st.y_um,
        z_um=st.z_um,
        heading_deg=math.degrees(st.heading_rad) % 360.0,
        concentration=current_c,
        event=event,
        pn_current_na=pn_current_na,
        mbon01_spikes=mbon_spikes,
        control="manual",
        reflex=reflex,
        bio_time_s=st.stats.to_out().bio_time_s,
    )


def step_virtual_fly(n_ticks: int = 1, manual: VirtualOrganismPoseIn | None = None) -> VirtualFlyStepResponse:
    with _lock:
        st = _ensure_state()  # 락 안에서 한 번만 바인딩 -- 루프 도중 다른 요청이 전역을 바꿀 수 없다
        if manual is not None:
            _check_run(st, manual)
            ticks = [_run_manual_tick(st, manual)]
        else:
            ticks = [_run_one_tick(st) for _ in range(n_ticks)]
        return VirtualFlyStepResponse(ticks=ticks, state=_to_state_out(st))
