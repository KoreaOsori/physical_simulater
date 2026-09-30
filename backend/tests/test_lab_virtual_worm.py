"""연구소(Lab) 가상 웜 폐루프 환경 테스트 (docs/41). 실제 Brian2 네트워크를
매 틱마다 돌리므로(restore 포함) 몇 초씩 걸리는 테스트가 있음 -- 이
프로젝트의 실측 검증 관행상(모킹으로는 못 잡는 버그가 실제로 여러 번
나왔음 -- 이번 기능도 "재시작 없는 연속 시뮬레이션이 통제 불능 고착
상태에 빠진다"는 실제 버그를 이 방식으로만 잡을 수 있었다) 실제로 돌려서
확인한다."""

import math
import threading

import pytest
from fastapi.testclient import TestClient

from app.api.routes import lab as lab_routes
from app.lab import virtual_worm
from app.lab.virtual_common import MAX_TRAIL_POINTS
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_worm_module_state():
    virtual_worm._state = None
    yield
    virtual_worm._state = None


def test_reset_returns_real_start_state_at_the_far_edge_of_the_arena() -> None:
    response = client.post("/api/lab/virtual-worm/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["tick"] == 0
    assert body["x_um"] == virtual_worm.START_POS_UM[0]
    assert body["y_um"] == virtual_worm.START_POS_UM[1]
    assert body["arena_radius_um"] == virtual_worm.ARENA_RADIUS_UM
    assert body["reached_source"] is False
    assert body["honesty_note"]


def test_state_auto_initializes_without_an_explicit_reset() -> None:
    response = client.get("/api/lab/virtual-worm/state")
    assert response.status_code == 200
    assert response.json()["tick"] == 0


def test_step_moves_the_worm_and_advances_the_tick_counter() -> None:
    client.post("/api/lab/virtual-worm/reset")
    response = client.post("/api/lab/virtual-worm/step", json={"n_ticks": 3})
    assert response.status_code == 200
    body = response.json()
    assert len(body["ticks"]) == 3
    assert body["state"]["tick"] == 3
    # 실제로 위치가 달라졌는지 (제자리 고정 버그 방지)
    assert (body["state"]["x_um"], body["state"]["y_um"]) != (
        virtual_worm.START_POS_UM[0],
        virtual_worm.START_POS_UM[1],
    )


def test_manual_pose_tick_senses_at_the_sent_position_and_normalizes_the_rate_by_elapsed_time() -> None:
    # 수동 조종(docs/45): 브라우저가 실시간으로 움직인 위치를 보내면 그 자리에서
    # 실제 네트워크가 감각을 계산한다. 광원에서 25mm 지점에서 1초(생물학적)에 걸쳐
    # 반대쪽으로 296μm 멀어졌다면, 틱(100ms)당 변화율로 환산해 자극해야 한다 --
    # 환산 없이 1초치 변화를 한 틱에 몰아 넣으면 자극이 10배 과장된다.
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    y0 = virtual_worm.SOURCE_POS_UM[1] - 25000.0
    st.x_um, st.y_um = 0.0, y0
    st.trail = [[0.0, y0]]
    st.prev_concentration = virtual_worm._concentration_at(st, 0.0, y0)
    y1 = y0 - virtual_worm.RUN_SPEED_UM_S  # 1초 동안 광원 반대쪽으로 이동
    pose = virtual_worm.VirtualOrganismPoseIn(x_um=0.0, y_um=y1, heading_deg=270.0, elapsed_bio_ms=1000.0, path=[[0.0, (y0 + y1) / 2]])

    tick = virtual_worm._run_manual_tick(st, pose)

    raw_delta = virtual_worm._concentration_at(st, 0.0, y1) - virtual_worm._concentration_at(st, 0.0, y0)
    assert tick.control == "manual"
    assert tick.delta_concentration == pytest.approx(raw_delta * 0.1)
    assert (tick.x_um, tick.y_um) == pytest.approx((0.0, y1))  # 이동은 보낸 위치 그대로
    assert any(s.spike_count > 0 for s in tick.sensory_activity)  # 실제 감각 발화
    assert st.stats.distance_um == pytest.approx(virtual_worm.RUN_SPEED_UM_S)
    if tick.event == "pirouette":
        assert tick.reflex is not None and tick.reflex.back_um > 0
    else:
        assert tick.reflex is None


def test_a_pose_from_before_a_reset_is_rejected_instead_of_teleporting_the_new_run() -> None:
    # 실제로 잡은 버그(docs/45): 수동 조종 중 보낸 위치 요청이 "다시 시작"보다 늦게
    # 처리되면, 옛 기록의 위치가 새 기록에 순간이동으로 들어가고 그 점프가 이동거리로
    # 쌓였다. 다시 시작마다 run_id를 새로 주고, 다른 run_id의 위치는 409로 거절한다.
    old = client.post("/api/lab/virtual-worm/reset").json()["run_id"]
    new_state = client.post("/api/lab/virtual-worm/reset").json()
    assert new_state["run_id"] != old
    stale = {"x_um": 20000.0, "y_um": 0.0, "heading_deg": 0.0, "run_id": old}
    assert client.post("/api/lab/virtual-worm/step", json={"n_ticks": 1, "manual": stale}).status_code == 409
    assert client.post("/api/lab/virtual-worm/pose", json=stale).status_code == 409
    state = client.get("/api/lab/virtual-worm/state").json()
    assert (state["x_um"], state["y_um"]) == (new_state["x_um"], new_state["y_um"])
    assert state["stats"]["distance_mm"] == 0


def test_manual_step_endpoint_requires_a_single_tick() -> None:
    body = {"n_ticks": 2, "manual": {"x_um": 0, "y_um": 0, "heading_deg": 90}}
    assert client.post("/api/lab/virtual-worm/step", json=body).status_code == 422


def test_moving_the_source_restarts_the_episode_and_does_not_fake_a_concentration_jump() -> None:
    client.post("/api/lab/virtual-worm/reset")
    client.post("/api/lab/virtual-worm/step", json={"n_ticks": 2})
    response = client.post("/api/lab/virtual-worm/source", json={"x_um": 10000.0, "y_um": -30000.0})
    assert response.status_code == 200
    state = response.json()
    assert (state["source_x_um"], state["source_y_um"]) == (10000.0, -30000.0)
    assert state["stats"]["auto_ticks"] == 0 and state["stats"]["bio_time_s"] == 0
    st = virtual_worm._state
    assert st.prev_concentration == pytest.approx(virtual_worm._concentration_at(st, st.x_um, st.y_um))
    # 아레나 밖으로 놓으면 안쪽으로 당겨진다
    far = client.post("/api/lab/virtual-worm/source", json={"x_um": 0.0, "y_um": 999999.0}).json()
    assert far["source_y_um"] == pytest.approx(virtual_worm.SOURCE_MAX_RADIUS_UM)


def test_pose_endpoint_sets_position_without_running_the_network() -> None:
    client.post("/api/lab/virtual-worm/reset")
    response = client.post("/api/lab/virtual-worm/pose", json={"x_um": 1000.0, "y_um": -20000.0, "heading_deg": 0.0, "elapsed_bio_ms": 500})
    state = response.json()
    assert response.status_code == 200
    assert (state["x_um"], state["y_um"], state["tick"]) == (1000.0, -20000.0, 0)
    assert state["stats"]["bio_time_s"] == pytest.approx(0.5)


def test_auto_ticks_report_auto_control() -> None:
    client.post("/api/lab/virtual-worm/reset")
    body = client.post("/api/lab/virtual-worm/step", json={"n_ticks": 1}).json()
    assert body["ticks"][0]["control"] == "auto"


def test_heading_toward_the_source_keeps_running_without_pirouettes() -> None:
    # 광원(+y) 쪽을 그대로 보고 있으면 매 틱 농도가 계속 증가해야 하고(가우시안 농도장의 단조성),
    # klinokinesis는 "감소"에 반응하므로 반전이 한 번도 없어야 한다. docs/47부터 기본 출발 방향이
    # 광원 반대쪽이라 여기선 광원 쪽으로 명시적으로 돌려 놓는다. (ASEL은 이제 실제처럼 농도 '증가'에
    # 반응하는 ON 세포라 오르막에서 ASEL이 켜지지만, 이 거리의 오르막 자극으론 반전이 나지 않아야 한다.)
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    st.heading_rad = math.pi / 2
    ticks = [virtual_worm._run_one_tick(st) for _ in range(5)]
    assert all(t.event == "run" for t in ticks)
    concentrations = [t.concentration for t in ticks]
    assert concentrations == sorted(concentrations)  # 단조 증가


def test_default_start_is_inside_the_sensing_band_and_facing_away() -> None:
    # docs/46 H7: 원래 출발점(70mm)은 감각 사각지대였다. docs/47: 40mm, 광원 반대쪽을 보고 출발 --
    # 두 번째 틱에(첫 틱은 비교할 이동이 없음) 실제로 농도 감소를 감지해 반전해야 한다.
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    assert virtual_worm._distance_to_source(st, st.x_um, st.y_um) == pytest.approx(40000.0)
    virtual_worm._run_one_tick(st)
    tick = virtual_worm._run_one_tick(st)
    assert tick.delta_concentration < 0
    assert tick.event == "pirouette"


def test_decreasing_concentration_triggers_a_real_pirouette_via_the_real_connectome() -> None:
    # 광원에 가까운 위치에서 광원 반대쪽(-y)을 보게 하면 첫 틱부터 농도가
    # 감소해야 하고, 실제 302개 뉴런 네트워크가 AWC/ASE -> ... -> AVA로
    # 이어지는 실제 회로를 통해 반전(AVA 발화 > AVB 발화)을 실제로
    # 만들어내는지 확인 -- 순수 계산 로직이 아니라 진짜 Brian2 실행 결과.
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    st.x_um, st.y_um = 0.0, 15000.0  # 광원에서 20mm -- 감지 구간(약 5-55mm) 한가운데
    st.heading_rad = -math.pi / 2  # 광원 반대 방향
    st.prev_concentration = virtual_worm._concentration_at(st, st.x_um, st.y_um)

    # 1틱째는 "직전 위치 대비 변화"를 재는 틱이라 직전=현재 위치라 dC=0
    # (설계상 당연함) -- 실제로 한 틱 이동해 위치가 바뀐 "다음" 틱에서야
    # 광원 반대쪽으로 실제 이동한 만큼 농도가 감소한다.
    virtual_worm._run_one_tick(st)
    tick = virtual_worm._run_one_tick(st)

    assert tick.delta_concentration < 0
    assert tick.event == "pirouette"
    assert tick.reverse_spikes > tick.forward_spikes
    assert any(s.spike_count > 0 for s in tick.sensory_activity)


def test_continuous_operation_does_not_lock_into_permanent_pirouette() -> None:
    # 실제로 잡았던 버그: 매 틱 restore("initial") 없이 막전위를 이어가면
    # 한 번의 강한 자극 후 네트워크 전체가 외부 입력과 무관하게 계속
    # 발화하는 고착 상태에 빠져 dC 부호와 상관없이 영원히 pirouette만
    # 나왔다. 틱마다 restore로 고쳤는지 회귀 확인 -- 광원을 향해 계속
    # 이동하면(농도 단조 증가) 최소 몇 틱은 다시 run으로 돌아와야 한다.
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    st.x_um, st.y_um = 0.0, 15000.0  # 광원에서 20mm -- 감지 구간(약 5-55mm) 한가운데
    st.heading_rad = -math.pi / 2
    st.prev_concentration = virtual_worm._concentration_at(st, st.x_um, st.y_um)

    events = [virtual_worm._run_one_tick(st).event for _ in range(6)]
    assert events.count("run") > 0, f"stuck in permanent pirouette: {events}"


def test_reaching_the_source_sets_the_flag_and_it_stays_true() -> None:
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    st.x_um, st.y_um = virtual_worm.SOURCE_POS_UM
    st.prev_concentration = virtual_worm._concentration_at(st, st.x_um, st.y_um)

    tick = virtual_worm._run_one_tick(st)
    assert tick.reached_source is True

    state = virtual_worm.get_virtual_worm_state()
    assert state.reached_source is True


def test_trail_is_capped_so_memory_does_not_grow_unbounded() -> None:
    virtual_worm._state = virtual_worm._fresh_state()
    st = virtual_worm._state
    st.trail = [[0.0, float(i)] for i in range(MAX_TRAIL_POINTS)]
    virtual_worm._run_one_tick(st)
    assert len(st.trail) == MAX_TRAIL_POINTS


def test_reset_during_an_in_flight_step_does_not_corrupt_the_shared_network(monkeypatch) -> None:
    # 실제로 잡았던 버그(라이브 Docker 백엔드에서 재현): FastAPI가 /reset과
    # /step을 각각 별도 스레드풀 스레드에서 처리하므로, "자동 재생" 도중
    # "다시 시작"을 누르는 등으로 reset()이 진행 중인 다중 틱 step() 루프
    # 도중 전역 _state를 재할당하면 Brian2가 실제로
    # StopIteration("Clock has reached the end of its available times.")를
    # 던지며 진행 중이던 요청이 503으로 실패했다. 락으로 고쳤는지 실제
    # 스레드 두 개로 재현해 확인 -- 모킹이 아니라 진짜 동시 요청.
    client.post("/api/lab/virtual-worm/reset")

    step_exceptions: list[BaseException] = []

    def run_long_step() -> None:
        try:
            response = client.post("/api/lab/virtual-worm/step", json={"n_ticks": 10})
            if response.status_code != 200:
                step_exceptions.append(RuntimeError(f"step returned {response.status_code}: {response.text}"))
        except BaseException as exc:  # noqa: BLE001 -- 스레드 예외를 메인 스레드에서 확인하기 위해 포착
            step_exceptions.append(exc)

    thread = threading.Thread(target=run_long_step)
    thread.start()
    reset_response = client.post("/api/lab/virtual-worm/reset")
    thread.join(timeout=120)

    assert not thread.is_alive(), "step thread did not finish -- possible deadlock from the lock fix"
    assert reset_response.status_code == 200
    assert step_exceptions == [], f"concurrent reset corrupted the in-flight step: {step_exceptions}"


def test_step_returns_503_instead_of_raw_500_on_simulation_failure(monkeypatch) -> None:
    def _boom(n_ticks, manual=None):
        raise RuntimeError("simulated Brian2 failure")

    monkeypatch.setattr(lab_routes, "step_virtual_worm", _boom)
    response = client.post("/api/lab/virtual-worm/step", json={"n_ticks": 1})
    assert response.status_code == 503
    assert "다시 시도" in response.json()["detail"]


def test_step_rejects_n_ticks_outside_the_documented_batch_range() -> None:
    assert client.post("/api/lab/virtual-worm/step", json={"n_ticks": 0}).status_code == 422
    assert client.post("/api/lab/virtual-worm/step", json={"n_ticks": 21}).status_code == 422
