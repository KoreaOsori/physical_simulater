"""연구소(Lab) 가상 초파리 폐루프 환경 테스트 (docs/42). 이 회로(~2,452개
뉴런, hemibrain olfactory subset)는 웜의 302개 뉴런 네트워크보다 틱당 연산
비용이 훨씬 커서(네이티브 개발환경에서 틱당 약 20초, Docker cython
codegen에서 약 5초) 테스트마다 최소한의 틱 수만 쓴다. 그래도 이 프로젝트의
실측 검증 관행상 실제로 돌려서 확인한다 -- 이 회로가 웜보다 훨씬 낮은
자극 문턱에서 전체 네트워크 흥분 상태로 전환된다는 실제 발견 자체가
모킹으로는 절대 못 잡았을 결과였다."""

import math
import threading

import pytest
from fastapi.testclient import TestClient

from app.api.routes import lab as lab_routes
from app.lab import virtual_fly
from app.lab.virtual_common import MAX_TRAIL_POINTS
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_fly_module_state():
    virtual_fly._state = None
    yield
    virtual_fly._state = None


def test_reset_returns_real_start_state() -> None:
    response = client.post("/api/lab/virtual-fly/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["tick"] == 0
    assert body["x_um"] == virtual_fly.START_POS_UM[0]
    assert body["y_um"] == virtual_fly.START_POS_UM[1]
    assert body["arena_radius_um"] == virtual_fly.ARENA_RADIUS_UM
    assert body["honesty_note"]


def test_state_auto_initializes_without_an_explicit_reset() -> None:
    response = client.get("/api/lab/virtual-fly/state")
    assert response.status_code == 200
    assert response.json()["tick"] == 0


def test_step_moves_the_fly_and_advances_the_tick_counter() -> None:
    client.post("/api/lab/virtual-fly/reset")
    response = client.post("/api/lab/virtual-fly/step", json={"n_ticks": 1})
    assert response.status_code == 200
    body = response.json()
    assert len(body["ticks"]) == 1
    assert body["state"]["tick"] == 1
    assert (body["state"]["x_um"], body["state"]["y_um"]) != (
        virtual_fly.START_POS_UM[0],
        virtual_fly.START_POS_UM[1],
    )


def test_low_concentration_start_produces_a_real_cruise_tick_with_no_mbon_response() -> None:
    # 시작 위치는 광원에서 충분히 멀어(농도 낮음) PN 자극이 문턱 아래여야
    # 하고, 실제로 MBON01이 발화하지 않아 cruise로 판정돼야 한다.
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    tick = virtual_fly._run_one_tick(st)
    assert tick.event == "cruise"
    assert tick.mbon01_spikes == 0


def test_high_concentration_near_source_triggers_a_real_avoidance_response() -> None:
    # 광원 바로 위(농도 약 1.0)에 놓으면 PN에 최대 자극(0.6nA)이 들어가고,
    # 실제 302 -> 아니 2,452개 뉴런 hemibrain 후각 회로를 통해 실제로
    # MBON01(y5B'2a)이 발화해 회피가 발동하는지 확인 -- 순수 계산 로직이
    # 아니라 진짜 Brian2 실행 결과.
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    st.x_um, st.y_um = virtual_fly.SOURCE_POS_UM

    tick = virtual_fly._run_one_tick(st)

    assert tick.pn_current_na > 0.5  # 거의 최대 자극(0.6nA)에 가까움
    assert tick.event == "avoidance"
    assert tick.mbon01_spikes > 0


def test_trail_is_capped_so_memory_does_not_grow_unbounded() -> None:
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    st.trail = [[0.0, float(i)] for i in range(MAX_TRAIL_POINTS)]
    virtual_fly._run_one_tick(st)
    assert len(st.trail) == MAX_TRAIL_POINTS


def test_reset_during_an_in_flight_step_does_not_corrupt_the_shared_network() -> None:
    # virtual_worm.py와 동일한 실제 동시성 버그(라이브 Docker에서 재현) --
    # 락으로 고쳤는지 실제 스레드 두 개로 확인.
    client.post("/api/lab/virtual-fly/reset")

    step_exceptions: list[BaseException] = []

    def run_long_step() -> None:
        try:
            response = client.post("/api/lab/virtual-fly/step", json={"n_ticks": 5})
            if response.status_code != 200:
                step_exceptions.append(RuntimeError(f"step returned {response.status_code}: {response.text}"))
        except BaseException as exc:  # noqa: BLE001
            step_exceptions.append(exc)

    thread = threading.Thread(target=run_long_step)
    thread.start()
    reset_response = client.post("/api/lab/virtual-fly/reset")
    thread.join(timeout=180)

    assert not thread.is_alive(), "step thread did not finish -- possible deadlock from the lock fix"
    assert reset_response.status_code == 200
    assert step_exceptions == [], f"concurrent reset corrupted the in-flight step: {step_exceptions}"


def test_step_returns_503_instead_of_raw_500_on_simulation_failure(monkeypatch) -> None:
    def _boom(n_ticks, manual=None):
        raise RuntimeError("simulated Brian2 failure")

    monkeypatch.setattr(lab_routes, "step_virtual_fly", _boom)
    response = client.post("/api/lab/virtual-fly/step", json={"n_ticks": 1})
    assert response.status_code == 503
    assert "다시 시도" in response.json()["detail"]


def test_manual_pose_at_the_source_runs_the_real_circuit_and_suggests_an_avoidance_reflex() -> None:
    # 수동 조종(docs/45): 광원 바로 위로 보내면 실제 MBON01이 발화해 뇌가 회피를
    # 결정하고, 이동은 보낸 위치 그대로 두되 반사 동작만 제안한다.
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    sx, sy = virtual_fly.SOURCE_POS_UM
    pose = virtual_fly.VirtualOrganismPoseIn(x_um=sx, y_um=sy, heading_deg=0.0, elapsed_bio_ms=300.0)

    tick = virtual_fly._run_manual_tick(st, pose)

    assert tick.control == "manual"
    assert tick.event == "avoidance"
    assert tick.mbon01_spikes > 0
    assert (tick.x_um, tick.y_um) == pytest.approx((sx, sy))
    assert tick.reflex is not None and tick.reflex.back_um > 0


def test_flying_high_above_the_source_dilutes_the_odor_below_the_real_threshold() -> None:
    # 비행 중 농도는 바닥 광원에서의 3D 거리(docs/45). 광원 바로 위라도 3σ 높이에선
    # 농도가 약 0.011로 떨어져, 실제 회로의 문턱(docs/42: 최대 자극의 ~10%) 아래라
    # MBON01이 발화하지 않아야 한다.
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    sx, sy = virtual_fly.SOURCE_POS_UM
    z = 3 * virtual_fly.GRADIENT_SIGMA_UM
    pose = virtual_fly.VirtualOrganismPoseIn(x_um=sx, y_um=sy, z_um=z, heading_deg=0.0)

    tick = virtual_fly._run_manual_tick(st, pose)

    assert tick.z_um == pytest.approx(z)
    assert tick.concentration == pytest.approx(math.exp(-4.5))
    assert tick.mbon01_spikes == 0
    assert tick.event == "cruise"


def test_altitude_is_clamped_to_the_chamber_and_auto_ticks_land_the_fly() -> None:
    client.post("/api/lab/virtual-fly/reset")
    state = client.post("/api/lab/virtual-fly/pose", json={"x_um": 0, "y_um": 0, "z_um": 999999, "heading_deg": 90}).json()
    assert state["z_um"] == virtual_fly.CHAMBER_HEIGHT_UM
    body = client.post("/api/lab/virtual-fly/step", json={"n_ticks": 1}).json()
    assert body["state"]["z_um"] == 0.0


def test_moving_the_fly_source_updates_state_and_restarts_stats() -> None:
    client.post("/api/lab/virtual-fly/reset")
    state = client.post("/api/lab/virtual-fly/source", json={"x_um": -5000.0, "y_um": 5000.0}).json()
    assert (state["source_x_um"], state["source_y_um"]) == (-5000.0, 5000.0)
    assert state["stats"]["manual_ticks"] == 0


def test_step_rejects_n_ticks_outside_the_documented_batch_range() -> None:
    assert client.post("/api/lab/virtual-fly/step", json={"n_ticks": 0}).status_code == 422
    assert client.post("/api/lab/virtual-fly/step", json={"n_ticks": 11}).status_code == 422


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def test_directed_avoidance_turns_back_when_entering_the_odor_and_retreats_outward() -> None:
    # docs/47: docs/46 H12의 '새는 구역'을 고친 회피 -- 직전 틱보다 농도가 올랐으면(냄새 쪽으로 들어가던 중)
    # 방향을 반대로(±30도) 돌려 그쪽으로 물러난다. 광원 위치는 쓰지 않고 현재/직전 농도만 쓴다.
    assert virtual_fly.AVOIDANCE_MODE == "directed"
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    sx, sy = virtual_fly.SOURCE_POS_UM
    st.x_um, st.y_um = sx, sy - 10000.0
    st.heading_rad = math.pi / 2  # 광원 쪽으로 들어가는 중
    st.prev_concentration = virtual_fly._concentration_at(st, st.x_um, st.y_um - 2800.0)  # 한 틱 전은 더 멀었다
    d_before = math.hypot(st.x_um - sx, st.y_um - sy)

    tick = virtual_fly._run_one_tick(st)

    assert tick.event == "avoidance"
    assert _angle_diff(st.heading_rad, -math.pi / 2) <= math.radians(30) + 1e-9
    assert math.hypot(st.x_um - sx, st.y_um - sy) > d_before


def test_directed_avoidance_keeps_going_when_already_leaving_the_odor() -> None:
    virtual_fly._state = virtual_fly._fresh_state()
    st = virtual_fly._state
    sx, sy = virtual_fly.SOURCE_POS_UM
    st.x_um, st.y_um = sx, sy - 10000.0
    st.heading_rad = -math.pi / 2  # 이미 광원에서 멀어지는 중
    st.prev_concentration = virtual_fly._concentration_at(st, st.x_um, st.y_um + 2800.0)  # 한 틱 전은 더 가까웠다
    d_before = math.hypot(st.x_um - sx, st.y_um - sy)

    tick = virtual_fly._run_one_tick(st)

    assert tick.event == "avoidance"
    assert _angle_diff(st.heading_rad, -math.pi / 2) <= math.radians(30) + 1e-9
    assert math.hypot(st.x_um - sx, st.y_um - sy) > d_before
