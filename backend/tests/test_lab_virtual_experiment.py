"""연구소(Lab) 시뮬레이션 가상 실험실 테스트 (docs/35). 실제 Brian2
시뮬레이션을 두 번(기준선+실험) 돌리므로 테스트당 몇 초씩 걸림 -- 그래도
이 프로젝트의 실측 검증 관행상(모킹으로는 못 잡는 버그가 실제로 여러 번
나왔음, docs/17/24/29/34 등) 실제로 돌려서 확인한다."""

from fastapi.testclient import TestClient

from app.api.routes import lab as lab_routes
from app.domain.schemas import Direction
from app.main import app
from app.simulation import hh_model

client = TestClient(app)


def test_virtual_experiment_silencing_a_real_command_interneuron_changes_the_outcome() -> None:
    # AVB (forward command interneuron, already curated in docs/26's
    # classic ablation studies) silencing a real, dramatic behavioral
    # difference -- validates the mechanism produces a genuinely different
    # result, not just a no-op wrapper around the baseline.
    response = client.post(
        "/api/lab/virtual-experiment/worm",
        json={"direction": "forward", "silenced_neuron_ids": ["AVBL", "AVBR"]},
    )
    assert response.status_code == 200
    body = response.json()

    assert set(body["silenced_neuron_ids"]) == {"AVBL", "AVBR"}
    assert len(body["experiment_neurons_fired"]) < len(body["baseline_neurons_fired"])
    assert "AVBL" in body["silenced_but_would_have_fired"]
    assert "AVBR" in body["silenced_but_would_have_fired"]
    assert body["honesty_note"]


def test_virtual_experiment_ignores_unknown_neuron_ids() -> None:
    response = client.post(
        "/api/lab/virtual-experiment/worm",
        json={"direction": "forward", "silenced_neuron_ids": ["NOT_A_REAL_NEURON", "AVBL"]},
    )
    assert response.status_code == 200
    assert response.json()["silenced_neuron_ids"] == ["AVBL"]


def test_virtual_experiment_does_not_leak_into_shared_habituation_state() -> None:
    # Real risk this test pins: run_hh_trace mutates module-level
    # _habituation_state keyed only by direction, with no "which caller"
    # concept -- a virtual experiment must leave the real interactive worm
    # page's habituation level for that direction untouched.
    hh_model.reset_habituation()
    before = hh_model.get_habituation_level(Direction.FORWARD)
    assert before == 0.0

    response = client.post("/api/lab/virtual-experiment/worm", json={"direction": "forward", "silenced_neuron_ids": []})
    assert response.status_code == 200
    # An empty silence list runs the same real baseline twice -- no crash,
    # and honestly reports no difference (nothing was actually silenced).
    assert response.json()["silenced_but_would_have_fired"] == []

    after = hh_model.get_habituation_level(Direction.FORWARD)
    assert after == before  # unchanged despite two real HH runs happening inside that request


def test_virtual_experiment_returns_503_instead_of_raw_500_on_simulation_failure(monkeypatch) -> None:
    # 실제 버그(docs/38): 이 라우트는 원래 예외 처리가 전혀 없어서 Brian2가
    # 실패하면 가공되지 않은 500이 그대로 나갔다 -- 명확한 503 + 메시지로
    # 고쳤는지 확인.
    def _boom(direction, silenced_neuron_ids):
        raise RuntimeError("simulated Brian2 failure")

    monkeypatch.setattr(lab_routes, "run_virtual_experiment", _boom)

    response = client.post("/api/lab/virtual-experiment/worm", json={"direction": "forward", "silenced_neuron_ids": []})

    assert response.status_code == 503
    assert "다시 시도" in response.json()["detail"]
